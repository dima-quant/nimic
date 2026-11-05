"""Rewrites the star imports of nimic modules into name imports (ncompiler/proposals/feature_module_scoped_dispatch.md
§5.1): `from .nifcore import *` becomes `from .nifcore import Cursor, TokenBuf, beginRead`, the names the module
uses that this import binds today. The star imports of nimic's std modules are rewritten the same way
(`from nimic.std.strutils import *` -> `from nimic.std.strutils import split, startsWith`); only the prelude,
`nimic.ntypes` (Nim's implicitly imported system), stays a star import.

    .venv/bin/python -m nnimony.tools.explicit_imports [--write] nnimony.lib.nifcore ncompiler.lexer ...

Without --write it only prints the report. Run it by hand and review the diff: it edits source files once, as a
formatter does; nothing rewrites code at import. For each name it picks:
- the module the original imports, when that module defines the name or re-exports it (export, exportFrom,
  exportExcept: its importers get the name through its `__getattr__`);
- otherwise (a star import leaked it: the module got it from a module that star-imported it without exporting it)
  the module that defines it, which adds an import to the Nim output. The report lists these.

The names come from the module's code (symtable: every global a scope reads), its annotations, the files it
includes (they run in its namespace), and the names its own @dispatch / @template sets extend. Method syntax of a
module-level proc is no name use: the call syntax follows the definition (`nnimony/tools/free_calls.py` rewrites
such calls into free calls first). The report also lists names that two of the module's imports bind to different
routines: Nim overloads them, Python binds the later one (`f = overloads(a.f, b.f)`, a decision for the reviewer).
"""

import argparse
import ast
import importlib
import importlib.util
import os
import symtable
import sys
import types

from nimic import transpiler
from nimic.imports import imports_of, included_trees, is_core, is_routine, nim_exports, visible
from nimic.valuecheck import is_nimic_file

_WIDTH = 120
PRELUDE = "nimic.ntypes"  # the one star import left: Nim's system module


def _is_target(name: str) -> bool:
    """A star import to rewrite: a nimic std module, or a nimic module that is not the core."""
    if name.startswith("nimic.std."):
        return True
    if is_core(name):
        return False
    spec = importlib.util.find_spec(name)
    return spec is not None and is_nimic_file(spec.origin or "")  # not Python's own (math)


def _star_targets(tree, package: str) -> list:
    """(node, module name) of the star imports to rewrite (`_is_target`), in source order."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.names[0].name == "*" and node.module != "__future__":
            name = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
            if _is_target(name):
                found.append((node, name))
    return sorted(found, key=lambda t: t[0].lineno)


def _all_star_imports(tree, package: str) -> list:
    """(line, module name) of every star import (core included), in source order."""
    found = [(n.lineno, importlib.util.resolve_name("." * n.level + (n.module or ""), package))
             for n in ast.walk(tree)
             if isinstance(n, ast.ImportFrom) and n.names[0].name == "*" and n.module != "__future__"]
    return sorted(found)


def _used_names(source: str, tree, path: str) -> set:
    """The globals the module's code reads (every scope) and the names in its annotations."""
    names = set()

    def walk(table):
        for sym in table.get_symbols():
            if sym.is_referenced() and sym.is_global():
                names.add(sym.get_name())
        for child in table.get_children():
            walk(child)

    walk(symtable.symtable(source, path, "exec"))
    annotations = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            annotations += [x.annotation for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]
                            if x is not None and x.annotation is not None]
            annotations += [node.returns] if node.returns is not None else []
            annotations += [t.bound for t in node.type_params if getattr(t, "bound", None) is not None]
        elif isinstance(node, ast.AnnAssign):
            annotations.append(node.annotation)
    for annotation in annotations:
        for n in ast.walk(annotation):
            if isinstance(n, ast.Name):
                names.add(n.id)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):  # a string annotation
                try:
                    names |= {m.id for m in ast.walk(ast.parse(n.value, mode="eval")) if isinstance(m, ast.Name)}
                except SyntaxError:
                    pass  # a docstring-like string, no annotation
    return names


def _decorator_name(node) -> str | None:
    """The name of a decorator (`@dispatch`, `@template(...)`)."""
    node = node.func if isinstance(node, ast.Call) else node
    return node.id if isinstance(node, ast.Name) else None


def _own_names(tree) -> tuple:
    """(names the module binds at its top level, its top-level @dispatch and @template routines)."""
    own, dispatched = set(), set()
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            own.add(node.name)
            if any(_decorator_name(d) in ("dispatch", "template") for d in getattr(node, "decorator_list", [])):
                dispatched.add(node.name)  # an overload set: it extends the proc of that name the module imports
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            own.add(node.id)
        stack.extend(ast.iter_child_nodes(node))
    return own, dispatched


def _bound_by_name(tree, package: str) -> tuple:
    """(names the module's name imports bind: `from m import a`, `import m`, importFrom, importExcept; the module
    names `from . import m` binds, as (level, module, leaf))."""
    names, modules = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.names[0].name != "*":
            names |= {a.asname or a.name for a in node.names}
            modules |= {(node.level, node.module or "", a.name) for a in node.names if not a.asname}
        elif isinstance(node, ast.Import):
            names |= {a.asname or a.name.split(".")[0] for a in node.names}
            modules |= {(0, "", a.name) for a in node.names if not a.asname}
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args
              and node.func.id in ("importFrom", "importExcept")
              and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args)):
            if node.func.id == "importFrom":  # it binds the module's name too
                names |= {a.value for a in node.args[1:]} | {node.args[0].value.rsplit(".", 1)[-1]}
            else:
                module = importlib.import_module(node.args[0].value.lstrip(".") if not node.args[0].value.startswith(".")
                                                 else importlib.util.resolve_name(node.args[0].value, package))
                names |= {n for n in vars(module) if not n.startswith("_")} - {a.value for a in node.args[1:]}
    return names, modules


def _relative(target: str, package: str) -> str:
    """`target` as a relative module spec from `package` (`nnimony.lib` -> `.nifcore`, `..models.tags`)."""
    t, p = target.split("."), package.split(".") if package else []
    common = 0
    while common < min(len(t), len(p)) and t[common] == p[common]:
        common += 1
    if common == 0:
        return target
    return "." * (len(p) - common + 1) + ".".join(t[common:])


def _defining_module(name: str, value: object, modules: list) -> str | None:
    """The loaded nimic module that defines `name` at its top level bound to `value`."""
    home = getattr(value, "__module__", None)
    if home in sys.modules and getattr(sys.modules[home], name, None) is value:
        return home
    for module in modules:
        path = getattr(module, "__file__", None) or ""
        if path.endswith(".py") and is_nimic_file(path) and getattr(module, name, None) is value:
            with open(path, encoding="utf-8") as f:
                if name in _own_names(ast.parse(f.read()))[0]:
                    return module.__name__
    return None


def _import_line(indent: str, spec: str, names: list, comment: str) -> str:
    """`from spec import a, b` wrapped at _WIDTH (parentheses, one indented continuation per line)."""
    head = f"{indent}from {spec} import "
    one = head + ", ".join(names) + comment
    if len(one) <= _WIDTH:
        return one
    lines, line = [], ""
    for n in names:
        piece = (", " if line else "") + n
        if len(indent) + 4 + len(line) + len(piece) + 1 > _WIDTH:
            lines.append(line + ",")
            line, piece = "", n
        line += piece
    lines.append(line)
    return f"{head}({comment}\n" + "\n".join(f"{indent}    {x}" for x in lines) + ")"


def plan(module_name: str) -> tuple:
    """(path, new source, report lines) for one module."""
    with transpiler.migrating_imports():  # its imports (and theirs) may still be star imports
        return _plan(module_name)


def _plan(module_name: str) -> tuple:
    module = importlib.import_module(module_name)
    path = module.__file__
    package = module.__package__ or ""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, path)
    stars = _star_targets(tree, package)
    report = []
    if not stars:
        return path, source, report
    used = _used_names(source, tree, path)
    for included in included_trees(tree, path):
        text = ast.unparse(included)
        used |= _used_names(text, included, path)
    own, dispatched = _own_names(tree)
    named, module_imports = _bound_by_name(tree, package)
    own |= named - dispatched
    namespace = vars(module)
    every_star = []
    for line, name in _all_star_imports(tree, package):
        if name not in sys.modules and importlib.util.find_spec(name) is None:
            report.append(f"  ~ line {line}: {name} doesn't exist (an inactive `when` branch): left as it is")
            continue
        importlib.import_module(name)  # a star import of the main block, or of a `when` branch, didn't run
        every_star.append((line, name))
    stars = [(node, name) for node, name in stars if name in sys.modules]
    loaded = [m for m in list(sys.modules.values()) if isinstance(m, types.ModuleType)]
    imports = imports_of(tree, module)
    chosen = {name: [] for _, name in stars}  # star-imported module -> names
    extra = {}  # defining module -> names (leaks)
    candidates = used | dispatched
    for u in sorted(candidates):
        if (u in own and u not in dispatched) or (u.startswith("__") and u.endswith("__")):
            continue  # the module's own name; a module attribute (`__name__`)
        providers = [(line, m) for line, m in every_star if hasattr(sys.modules[m], u)]
        if not providers:
            continue
        line, provider = providers[-1]  # Python binds the last star import's
        value = getattr(sys.modules[provider], u)
        if any(m == PRELUDE and getattr(sys.modules[m], u, None) is value for _, m in providers):
            continue  # the prelude's star import binds it (another star import may re-export it)
        routines = {m.__name__ for obj, m in visible(imports, u) if is_routine(obj)}  # Nim's view: name resolution, rules 8.1
        if len(routines) > 1:
            report.append(f"  ! {u}: routines of {', '.join(sorted(routines))} (Nim overloads them; "
                          f"Python binds {getattr(value, '__module__', provider)}'s)")
        # every star import binding this object; Nim's import of which brings it (its own name, or re-exported)
        exporters = [m for _, m in providers
                     if getattr(sys.modules[m], u) is value and nim_exports(sys.modules[m], u, value)]
        if exporters:
            defining = [m for m in exporters if getattr(value, "__module__", None) == m]
            chosen[(defining or exporters)[-1]].append(u)
            continue
        # a leak: Python binds a name Nim's imports don't bring (a star import of a star import)
        others = [m for _, m in providers if getattr(sys.modules[m], u) is not value
                  and nim_exports(sys.modules[m], u, getattr(sys.modules[m], u))]
        core = [m for m in others if m == PRELUDE]
        if core:
            report.append(f"  ~ {u}: was {provider}'s leak, now {core[-1]}'s (the prelude's star import; Nim's)")
        elif others and u in dispatched:
            chosen.setdefault(others[-1], []).append(u)
            report.append(f"  ~ {u}: the module's @dispatch extends {others[-1]}'s (Nim's), not {provider}'s leak")
        else:
            home = _defining_module(u, value, loaded)
            if home is None:
                report.append(f"  ? {u}: leaked by {provider}, its defining module not found: listed from it")
                chosen[provider].append(u)
            else:
                extra.setdefault(home, []).append(u)
                report.append(f"  + {u}: leaked by {provider}; imported from {home} (an added Nim import)")
    lines = source.splitlines(keepends=True)
    for node, name in reversed(stars):
        text = lines[node.lineno - 1]
        indent = text[:len(text) - len(text.lstrip())]
        comment = text.rstrip("\n")[node.end_col_offset:]
        comment = "  " + comment.strip() if comment.strip() else ""
        spec = "." * node.level + (node.module or "")
        new = []
        names = sorted(set(chosen[name]), key=lambda n: (n.lower(), n))
        if names:
            new.append(_import_line(indent, spec, names, comment))
        else:
            head, _, leaf = (node.module or "").rpartition(".")
            parent = "." * node.level + head  # `from .ea import *` -> `from . import ea`
            level = node.level
            # `from nimic.std import syncio` (rules §8: `import std/syncio`), not `import nimic.std.syncio`
            statement = f"from {parent} import {leaf}" if node.level or head else f"import {spec}"
            if (level, parent.lstrip("."), leaf) in module_imports or (not node.level and (0, "", spec) in module_imports):
                report.append(f"  - {spec}: no name used; the module already has `{statement}`")
            else:
                new.append(f"{indent}{statement}{comment}")
                report.append(f"  - {spec}: no name used; kept as `{statement}` (Nim's import)")
        if node is stars[-1][0]:
            for home, homenames in sorted(extra.items()):
                new.append(_import_line(indent, _relative(home, package), sorted(set(homenames)), ""))
        lines[node.lineno - 1:node.end_lineno] = [x + "\n" for x in new]
    return path, "".join(lines), report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="rewrite the source files")
    parser.add_argument("modules", nargs="+", help="dotted module names (nnimony.lib.nifcore)")
    args = parser.parse_args(argv)
    for name in args.modules:
        path, new, report = plan(name)
        with open(path, encoding="utf-8") as f:
            old = f.read()
        print(f"{name}: {'rewritten' if new != old and args.write else 'changes' if new != old else 'unchanged'}")
        for line in report:
            print(line)
        if args.write and new != old:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
