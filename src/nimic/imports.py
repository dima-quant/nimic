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
from typing import NamedTuple

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


_export_calls: dict = {}  # id(tree) -> (tree, its export calls: (function, the names it passes, its strings))


def _export_calls_of(tree) -> list:
    """The `export` / `exportFrom` / `exportExcept` calls of a tree, walked once per tree (the import checks ask
    for each name they look up)."""
    entry = _export_calls.get(id(tree))
    if entry is None or entry[0] is not tree:
        calls = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args
                    and node.func.id in ("export", "exportFrom", "exportExcept")):
                calls.append((node.func.id, [a.id for a in node.args if isinstance(a, ast.Name)],
                              frozenset(a.value for a in node.args[1:]
                                        if isinstance(a, ast.Constant) and isinstance(a.value, str))))
        entry = _export_calls[id(tree)] = (tree, calls)
    return entry[1]


def module_exports(tree, module: types.ModuleType) -> list:
    """What a nimic module re-exports, from its source: (module, names, hidden) per call. `export(m1, m2)` exports
    the modules bound to `m1`, `m2` (names None: all); `exportFrom(m, "X")` the name X of `m`; `exportExcept(m, "a")`
    all of `m` but `a`."""
    found = []
    for function, passed, strings in _export_calls_of(tree):
        bound = [getattr(module, n, None) for n in passed]
        if function == "export":
            found += [(m, None, frozenset()) for m in bound if isinstance(m, types.ModuleType)]
        elif bound and isinstance(bound[0], types.ModuleType):
            found.append((bound[0], strings, frozenset()) if function == "exportFrom"
                         else (bound[0], None, strings))
    return found


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
        elif isinstance(node, ast.TypeAlias):
            names.add(node.name.id)
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
    doesn't export nifbuilder). A private name (`_x`) is never exported; a module that isn't nimic counts as exporting
    all its other names."""
    if name.startswith("_") and not (name.startswith("__") and name.endswith("__")):
        return False  # a private name (`_readBytes`) is never exported
    tree = nimic_tree(module)
    if tree is None or module.__name__ in seen or name in _own_names(module, tree):
        return True
    return any((names is None or name in names) and name not in hidden and getattr(m, name, None) is proc
               and nim_exports(m, name, proc, seen | {module.__name__})
               for m, names, hidden in module_exports(tree, module))


def exported(module: types.ModuleType, name: str, seen: frozenset = frozenset()) -> list:
    """Nim's `module.name`: the objects named `name` that the module exports, one per distinct object: its own and,
    recursively, those it re-exports. A module that isn't nimic exports what it binds."""
    tree = nimic_tree(module)
    if tree is None or module.__name__ in seen:
        return [getattr(module, name)] if hasattr(module, name) else []
    found = {}
    if name in _own_names(module, tree) and name in vars(module):
        found[id(vars(module)[name])] = vars(module)[name]
    for m, names, hidden in module_exports(tree, module):
        if (names is None or name in names) and name not in hidden:
            for obj in exported(m, name, seen | {module.__name__}):
                found.setdefault(id(obj), obj)
    return list(found.values())


# --- Name resolution (nimic_translation_rules_nimony.md §8.1) ---

def is_core(name: str) -> bool:
    """The nimic core (nimic.ntypes, nimic.std.*): imported by star imports, it plays Nim's system and std."""
    return name == "nimic" or name.startswith("nimic.")


def is_routine(value) -> bool:
    """A proc, template or overload set (not a type, module or value)."""
    return callable(value) and not isinstance(value, (type, types.ModuleType))


def reaches(binding, obj) -> bool:
    """Whether a call of Python's `binding` can reach `obj`: the same object, or one an overload set includes (its
    `_n_includes` protocol: its overloads, the sets it includes, the proc it extends)."""
    return binding is obj or bool(getattr(binding, "_n_includes", lambda _: False)(obj))


class Import(NamedTuple):
    """One import of a module, as Nim sees it: `module` imported whole (names None) or only `names` (importFrom),
    minus `hidden` (importExcept). `bound` is what the statement binds in Python: (name, attribute) pairs; `star`
    a star import."""
    line: int
    module: types.ModuleType
    names: frozenset | None
    hidden: frozenset
    bound: tuple
    star: bool


def is_main_block(stmt) -> bool:
    """Whether `stmt` is `if comptime(__name__ == "__main__"):` or `if __name__ == "__main__":` (rule:main)."""
    if not isinstance(stmt, ast.If):
        return False
    test = stmt.test
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "comptime" and test.args:
        test = test.args[0]
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__"
            and len(test.comparators) == 1 and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__")


def _comptime_taken(node, namespace: dict) -> list | None:
    """The branch an `if comptime(cond):` statement (Nim `when cond:`) ran, evaluated in the loaded module's
    `namespace`; None for another statement, or when the module's namespace can't tell: a condition naming what
    only a routine binds (a generic parameter: NameError), or calling `declared`, whose answer depends on the point
    of the module (`when not declared(f): def f` is true before the def runs, false after)."""
    test = node.test if isinstance(node, ast.If) else None
    if not (isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "comptime"
            and len(test.args) == 1):
        return None
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "declared"
           for n in ast.walk(test)):
        return None
    try:
        taken = eval(compile(ast.Expression(test.args[0]), "<comptime>", "eval"), namespace)
    except NameError:
        return None
    return node.body if taken else node.orelse


def _walk_running(node, namespace: dict):
    """ast.walk of `node`, entering only the branch each `if comptime(...)` in it ran (_comptime_taken)."""
    taken = _comptime_taken(node, namespace)
    if taken is not None:
        for stmt in taken:
            yield from _walk_running(stmt, namespace)
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _walk_running(child, namespace)


def _running(tree, module: types.ModuleType):
    """The module's nodes that ran: without its main block when the module isn't the main program, and without
    the branches of `if comptime(...)` statements (Nim `when`) not taken (_comptime_taken). A module an untaken
    branch imports may be loaded by another module: its import didn't run here."""
    main = module.__name__ == "__main__"
    for stmt in tree.body:
        if main or not is_main_block(stmt):
            yield from _walk_running(stmt, vars(module))


def imports_of(tree, module: types.ModuleType) -> list:
    """The module's imports that ran (their modules are loaded; not those of its main block when it is imported),
    in source order. Every Python import of a module
    is a full Nim import of it (`from .nifcore import TokenBuf` is `import nifcore`); `from . import m` and
    `import m` import the module m; importFrom(".m", "a") is Nim's `from m import a`, importExcept(".m", "a")
    `import m except a`."""
    found = []
    package = module.__package__ or ""
    for node in _running(tree, module):
        if isinstance(node, ast.ImportFrom) and node.module != "__future__":
            base = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
            source = sys.modules.get(base)
            if node.names[0].name == "*":
                if source is not None:
                    found.append(Import(node.lineno, source, None, frozenset(), (), True))
                continue
            attrs = []
            for alias in node.names:
                sub = sys.modules.get(f"{base}.{alias.name}")
                if sub is not None and getattr(source, alias.name, sub) is sub:  # a module of a package
                    found.append(Import(node.lineno, sub, None, frozenset(), ((alias.asname or alias.name, None),),
                                        False))
                elif source is not None:
                    attrs.append((alias.asname or alias.name, alias.name))
            if attrs:
                found.append(Import(node.lineno, source, None, frozenset(), tuple(attrs), False))
        elif isinstance(node, ast.Import):
            found += [Import(node.lineno, sys.modules[a.name], None, frozenset(), ((a.asname or a.name, None),), False)
                      for a in node.names if a.name in sys.modules]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args
              and node.func.id in ("importFrom", "importExcept")
              and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args)):
            source = sys.modules.get(importlib.util.resolve_name(node.args[0].value, package))
            if source is None:
                continue
            names = frozenset(a.value for a in node.args[1:])
            if node.func.id == "importFrom":
                found.append(Import(node.lineno, source, names, frozenset(),  # an enum member is no attribute
                                    tuple((n, n) for n in sorted(names) if n.isidentifier() and hasattr(source, n)),
                                    False))
            else:  # the core's: star-like; another nimic module's: binds the module's name only
                core = is_core(source.__name__)
                found.append(Import(node.lineno, source, None, names,
                                    () if core else ((node.args[0].value.rsplit(".", 1)[-1], None),), core))
    return sorted(found, key=lambda i: i.line)


def visible(imports: list, name: str) -> list:
    """Nim's view of `name` through the module's imports (its own definitions aside): (object, module) per distinct
    object that an imported module exports under that name (nim_exports), within the import's names."""
    found = {}
    for imp in imports:
        if (imp.names is not None and name not in imp.names) or name in imp.hidden or not hasattr(imp.module, name):
            continue
        obj = getattr(imp.module, name)
        if not isinstance(obj, types.ModuleType) and nim_exports(imp.module, name, obj):
            found.setdefault(id(obj), (obj, imp.module))
    return list(found.values())


def _when_not_declared(node) -> str | None:
    """The name of an `if comptime(not declared("name")):` statement (Nim `when not declared(name)`), or None."""
    test = node.test if isinstance(node, ast.If) else None
    if (isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "comptime"
            and len(test.args) == 1 and isinstance(test.args[0], ast.UnaryOp) and isinstance(test.args[0].op, ast.Not)):
        inner = test.args[0].operand
        if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "declared"
                and len(inner.args) == 1 and isinstance(inner.args[0], ast.Constant)
                and isinstance(inner.args[0].value, str)):
            return inner.args[0].value
    return None


def own_definitions(tree) -> dict:
    """How the module defines a name at its top level, from its source: "plain" (a def without an overload
    decorator), "set" (@dispatch or @template: an overload set extending the name's binding before it), "value"
    (a class, a variable or constant), "overloads" (`f = overloads(...)`). A set wins over a plain def of the name
    (a forward declaration and its overloads). A def under `if comptime(not declared("f")):` (Nim `when not
    declared(f)`) defines nothing where an import binds the name: it isn't counted."""
    rank = {"value": 0, "plain": 1, "overloads": 2, "set": 3}
    found = {}
    undeclared = {id(stmt) for node in _top_level(tree) if _when_not_declared(node)
                  for stmt in ast.walk(node) if getattr(stmt, "name", None) == _when_not_declared(node)}

    def note(name, kind):
        if rank[kind] >= rank.get(found.get(name), -1):
            found[name] = kind

    for node in _top_level(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and id(node) not in undeclared:
            decorators = {(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list}
            note(node.name, "set" if any(isinstance(d, ast.Name) and d.id in ("dispatch", "template")
                                         for d in decorators) else "plain")
        elif isinstance(node, ast.ClassDef):
            note(node.name, "value")
        elif isinstance(node, ast.TypeAlias):  # `type Node = ptr[LinkedToken]`, a type of the module
            note(node.name.id, "value")
        elif is_overloads(node):
            note(node.targets[0].id, "overloads")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for n in (n for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)):
                note(n.id, "value")
    return found
