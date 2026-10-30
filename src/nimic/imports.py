"""
nimic imports
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

The import graph of nimic modules, read from their source: what a module imports and what Nim's import of a module
makes visible (its own names and its exports). Python's star import re-exports every name of a module, also those of
its own star imports; Nim's import doesn't. The transpiler's checks (rule:methodcall) use it; nothing here imports
the type system, so the type system can use it too.
"""

import ast
import importlib.util
import os
import sys
import types

from nimic.valuecheck import is_nimic_file

_trees: dict = {}  # path -> the source tree of a nimic module


def nimic_tree(module: types.ModuleType) -> ast.Module | None:
    """The source tree of a nimic module (`# /// nimic` header); None for any other (nimic.ntypes, a std shim)."""
    path = getattr(module, "__file__", None) or ""
    if not (path.endswith(".py") and is_nimic_file(path)):
        return None
    if path not in _trees:
        with open(path, encoding="utf-8") as f:
            _trees[path] = ast.parse(f.read(), path)
    return _trees[path]


def module_level_routines(tree) -> set:
    """The names of the routines a module defines at its top level, also in `when` branches and `with` blocks
    (not in a proc or class): from the source, so they count before their `def` has run."""
    names = set()
    stack = list(tree.body) if isinstance(tree, ast.Module) else [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif not isinstance(node, (ast.ClassDef, ast.Lambda)):
            stack.extend(child for child in ast.iter_child_nodes(node) if isinstance(child, ast.stmt))
    return names


def _resolve(name: str, module: types.ModuleType) -> types.ModuleType | None:
    """The loaded module `name` (relative to `module`'s package for leading dots); None when not loaded (an import
    in a branch that didn't run)."""
    return sys.modules.get(importlib.util.resolve_name(name, module.__package__ or ""))


def star_imports(tree, module: types.ModuleType) -> list:
    """The modules the module's star imports bind (`from .nifcore import *`), those that ran."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.names[0].name == "*" and node.module != "__future__":
            imported = _resolve("." * node.level + (node.module or ""), module)
            if imported is not None:
                found.append(imported)
    return found


def module_exports(tree, module: types.ModuleType) -> tuple:
    """What a nimic module re-exports, from its source: (modules, names, hidden). `export(m1, m2)` exports the
    modules bound to `m1`, `m2`; `exportFrom(m, "X")` the name X; `exportExcept(m, "a")` exports `m` but hides `a`
    (hidden: module name -> names)."""
    modules, names, hidden = [], set(), {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args
                and node.func.id in ("export", "exportFrom", "exportExcept")):
            continue
        strings = {a.value for a in node.args[1:] if isinstance(a, ast.Constant) and isinstance(a.value, str)}
        bound = [getattr(module, a.id, None) for a in node.args if isinstance(a, ast.Name)]
        if node.func.id == "export":
            modules += [m for m in bound if isinstance(m, types.ModuleType)]
        elif node.func.id == "exportFrom":
            names |= strings
        elif bound and isinstance(bound[0], types.ModuleType):
            modules.append(bound[0])
            hidden[bound[0].__name__] = strings
    return modules, names, hidden


def _top_level(tree):
    """The statements a module runs at its top level: also those in `when` branches, `with` and `try` blocks, not
    those in a proc or class."""
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            stack.extend(child for child in ast.iter_child_nodes(node) if isinstance(child, ast.stmt))


def included_trees(tree, path: str) -> list:
    """The source trees of the files `include("x", ...)` runs in the module's namespace (nested includes too)."""
    found, paths = [], [path]
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "include"
                and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args)):
            for arg in node.args:
                included = os.path.join(os.path.dirname(path), *arg.value.split("/")) + ".py"
                if os.path.exists(included) and included not in paths:
                    paths.append(included)
                    with open(included, encoding="utf-8") as f:
                        sub = ast.parse(f.read(), included)
                    found += [sub, *included_trees(sub, included)]
    return found


def is_overloads(node) -> bool:
    """Whether `node` is `f = overloads(a.f, b.f)` (rule:overloads): it binds imported procs, it defines nothing."""
    return (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name) and node.value.func.id == "overloads")


def module_level_names(tree) -> set:
    """The names a module defines at its top level (routines, classes, variables and constants), from the source.
    An `overloads(...)` assignment defines nothing."""
    names = set()
    for node in _top_level(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and not is_overloads(node):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names |= {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}
    return names


def _own_names(module: types.ModuleType, tree) -> set:
    path = module.__file__
    if path not in _own:
        _own[path] = set().union(*(module_level_names(t) for t in [tree, *included_trees(tree, path)]))
    return _own[path]


_own: dict = {}  # path -> the names a nimic module defines (also in the files it includes)


def nim_exports(module: types.ModuleType, name: str, proc, seen: frozenset = frozenset()) -> bool:
    """Whether Nim's `import module` brings `proc` as `name`: the names the module defines (also in the files it
    includes) and what it re-exports (`export`, `exportFrom`, `exportExcept`), not what it only imports (by a star
    import or by name). Python's star import re-exports all of a module's names, also those of its imports
    (nifcoreparse's `from .nifbuilder import *` brings nifbuilder's `offset` to its importers; Nim's nifcoreparse
    doesn't export nifbuilder). A module that isn't nimic counts as exporting all its names."""
    tree = nimic_tree(module)
    if tree is None or module.__name__ in seen or name in _own_names(module, tree):
        return True
    modules, names, hidden = module_exports(tree, module)
    return name in names or any(
        getattr(m, name, None) is proc and name not in hidden.get(m.__name__, ())
        and nim_exports(m, name, proc, seen | {module.__name__}) for m in modules)
