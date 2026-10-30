"""Rewrites method-syntax calls of module-level procs into free calls (ncompiler/proposals/feature_module_scoped_
dispatch.md §5.4, phase 2): `tb.addIdent(s)` becomes `addIdent(tb, s)`, `with b.addCast(t):` becomes
`with addCast(b, t):`. A method of a class stays a method call; only a callable the class doesn't define, which
Object.__getattr__ found as a proc of the caller's scope (or of the receiver's module), is rewritten.

    .venv/bin/python -m nnimony.tools.free_calls [--write] LOG...

The sites come from a run log: each line `file:line<TAB>name<TAB>class<TAB>module of the proc reached`, written by
a temporary wrapper of ntypesystem._n_method_call_proc while the tests run (.scratch/p2/hook/sitecustomize.py). A
site the tests don't reach raises AttributeError once the proc search is gone, with the free call to write; Nim
accepts both spellings, so the transpiled code doesn't change meaning. Run it by hand and review the diff: it edits
source files once, as a formatter does.

A free call needs the name bound in the caller: when the caller didn't bind it (the call reached the receiver's
module), the name is added to the caller's import of that module, or a new name import is written.
"""

import argparse
import ast
import collections
import importlib.util
import os
import sys


def _sites(logs: list) -> tuple:
    """From the run logs: (file -> {(line, column where `recv.name` ends): (name, module of the proc)},
    (module, template) -> {name: module of the proc}). A call in an inlined template's body is logged in the
    expansion (`<template_expand nnimony.lib.nifcoreparse.parse>`): it is rewritten in the template's source,
    `__main__.parse` in each logged module defining the template parse."""
    found, templates = collections.defaultdict(dict), collections.defaultdict(dict)
    for log in logs:
        with open(log, encoding="utf-8") as f:
            for row in f:
                location, name, _cls, module = row.rstrip("\n").split("\t")
                path, line, col = location.rsplit(":", 2)
                path = os.path.normpath(path)
                if path.startswith("<template_expand ") and path.endswith(">"):
                    owner, _, template = path[len("<template_expand "):-1].rpartition(".")
                    templates[(owner, template)][name] = module
                else:
                    found[path][(int(line), int(col))] = (name, module)
    for (owner, template), names in list(templates.items()):
        if owner == "__main__":
            for (other, same), known in templates.items():
                if other != "__main__" and same == template:
                    known.update(names)
            del templates[(owner, template)]
    return found, templates


def _offset(lines: list, line: int, col: int) -> int:
    """The character offset of (line, col) (1-based line, 0-based UTF-8 byte column) in the joined source."""
    text = lines[line - 1]
    return sum(len(x) for x in lines[:line - 1]) + len(text.encode("utf-8")[:col].decode("utf-8"))


def _rewrite_one(source: str, wanted: dict, modules: set, templates: dict) -> tuple:
    """Rewrites the rightmost logged method-syntax call still in `source`: a logged site, or in the body of a
    template `templates` names (template -> {name: module}) a call of a logged name. Returns (source, name,
    module) or (source, None, None) when none is left."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    bodies = [(t.lineno, t.end_lineno, templates[t.name]) for t in tree.body
              if isinstance(t, (ast.FunctionDef, ast.AsyncFunctionDef)) and t.name in templates]
    calls = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)) or (
                isinstance(node.func.value, ast.Name) and node.func.value.id in modules):
            continue
        if wanted.get((node.func.end_lineno, node.func.end_col_offset), (None,))[0] == node.func.attr or any(
                first <= node.lineno <= last and node.func.attr in names for first, last, names in bodies):
            calls.append(node)
    if not calls:
        return source, None, None
    node = max(calls, key=lambda n: (n.func.end_lineno, n.func.end_col_offset))  # the rightmost first: the
    # sites left of it keep their positions
    name = node.func.attr
    start = _offset(lines, node.lineno, node.col_offset)  # also a receiver's parentheses: `(a + b).f(x)`
    value = node.func.value
    receiver = source[_offset(lines, value.lineno, value.col_offset):
                      _offset(lines, value.end_lineno, value.end_col_offset)]  # an argument needs no parentheses
    call_end = _offset(lines, node.end_lineno, node.end_col_offset)
    func_end = _offset(lines, node.func.end_lineno, node.func.end_col_offset)
    inner = source[source.index("(", func_end) + 1:call_end - 1]
    separator = ("," if inner.startswith(("\n", "\r")) else ", ") if inner.strip() else ""
    new = f"{name}({receiver}{separator}{inner})"
    key = (node.func.end_lineno, node.func.end_col_offset)
    if key in wanted:
        module = wanted.pop(key)[1]
    else:
        module = next(names[name] for first, last, names in bodies if first <= node.lineno <= last)
    return source[:start] + new + source[call_end:], name, module


def _bound_names(tree) -> set:
    """The names the module binds at its top level (definitions, assignments, imports)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {a.asname or a.name.split(".")[0] for a in node.names}
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "importFrom"
              and all(isinstance(a, ast.Constant) for a in node.args)):
            names |= {a.value for a in node.args[1:]}
    return names


def _add_import(source: str, name: str, module: str, package: str) -> str:
    """Adds `name` to the module's top-level name import of `module`, or writes a new one after its last import."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    last = 0
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module != "__future__":
            base = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
            last = node.end_lineno
            if base == module and node.names[0].name != "*":
                names = sorted({a.name for a in node.names} | {name}, key=lambda n: (n.lower(), n))
                if any(a.asname for a in node.names):
                    continue
                text = lines[node.lineno - 1]
                indent = text[:len(text) - len(text.lstrip())]
                spec = "." * node.level + (node.module or "")
                line = f"{indent}from {spec} import " + ", ".join(names)
                if len(line) > 120:
                    line = f"{indent}from {spec} import (\n    " + ",\n    ".join(names) + ")"
                lines[node.lineno - 1:node.end_lineno] = [line + "\n"]
                return "".join(lines)
        elif isinstance(node, ast.Import):
            last = node.end_lineno
    spec = module
    if package and module.split(".")[0] == package.split(".")[0]:
        common = 0
        p, t = package.split("."), module.split(".")
        while common < min(len(p), len(t)) and p[common] == t[common]:
            common += 1
        spec = "." * (len(p) - common + 1) + ".".join(t[common:])
    lines.insert(last, f"from {spec} import {name}\n")
    return "".join(lines)


def rewrite(path: str, wanted: dict, package: str, templates: dict | None = None) -> tuple:
    """(new source, report lines) for one file; `templates`: template name -> {name: module} of its body's calls."""
    with open(path, encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    modules = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
               for a in n.names if n.module is None or isinstance(n, ast.Import)}
    report, imports = [], {}
    count = 0
    while True:
        source, name, module = _rewrite_one(source, wanted, modules, templates or {})
        if name is None:
            break
        count += 1
        imports.setdefault(name, module)
    bound = _bound_names(ast.parse(source))
    for name, module in sorted(imports.items()):
        if name not in bound and module and module not in ("?", "__main__"):  # __main__: the program's own
            source = _add_import(source, name, module, package)
            report.append(f"  + {name}: imported from {module} (the call reached the receiver's module)")
    report.insert(0, f"  {count} call(s) rewritten")
    return source, report


def _package_of(path: str) -> str:
    """The package of a file, from its directory relative to the current directory (the repository root, where
    nnimony and ncompiler are namespace packages); "" outside it."""
    folder = os.path.relpath(os.path.dirname(os.path.abspath(path)))
    return "" if folder.startswith("..") or folder == "." else folder.replace(os.sep, ".")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help="rewrite the source files")
    parser.add_argument("--package", action="append", default=[],
                        help="path=package for files whose package isn't found from sys.path (path prefix)")
    parser.add_argument("logs", nargs="+", help="run logs")
    args = parser.parse_args(argv)
    packages = dict(p.split("=", 1) for p in args.package)
    sites, templates = _sites(args.logs)
    by_file = collections.defaultdict(dict)  # file -> template -> names
    for (owner, template), names in templates.items():
        spec = importlib.util.find_spec(owner)
        if spec is not None and spec.origin:
            by_file[spec.origin][template] = names
    for path in sorted(set(sites) | set(by_file)):
        if "/site-packages/" in path or "/src/nimic/" in path:
            continue  # Python's and nimic's own code
        package = next((pkg for prefix, pkg in packages.items() if path.startswith(prefix)), None)
        if package is None:
            package = _package_of(path)
        new, report = rewrite(path, sites.get(path, {}), package, by_file.get(path))
        print(path)
        for line in report:
            print(line)
        if args.write:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
