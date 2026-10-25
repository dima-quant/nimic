"""Nim value semantics checked for Python name bindings (rule:valuecheck, nimic_translation_rules_nimony.md §1.1).

Nim copies a value on assignment: after `var y = x`, `result = o.f` or `y = s[i]`, changing one leaves the other
alone. Python binds the same object. Stores already copy (constructor, field, `seq.add`: _n_value_copy); a binding
copies only where the code says so, `y = x.copy()` (the transpiler drops `.copy()`, rule:copy). Nimic checks that
the copies are there, without changing the code (it runs as written, under a debugger and in the REPL too):

- when a nimic module loads (`analyze`, syntax only): the bindings that may need a copy, `Site`s: a name bound to
  an l-value (`y = x`, `y = o.f`, `y = s[i]`) or to a call's result, without `.copy()`, where one of the two
  names may change the value later while the other still reads it (a store into it, `+=`, a method call, an
  argument of a call, a closure or a global). A local's last use (Nim moves it), literals, constructors' and
  operators' results, and names that are never changed are left alone;
- at run time (sys.monitoring, on a site's first executions): a binding whose value is a value type another
  location still holds (the l-value it was read from, or a part of a call's inputs: `Policy`, from the type
  system) is armed in its frame; then each statement that may change the value (the analysis lists them) is
  watched: if it changed the value (a fingerprint before and after) while both locations still hold it, Python
  and Nim now certainly differ, and ValueCopyError names the binding, the write and the copy to write. A binding
  whose sharing is only possible (a getter's result, a value no write changes) is not an error.

The mode is NIMIC_VALUECHECK: `error` (the default), `warn` (printed once per site), `lint` (also prints the
possible differences: the bindings and `-> T` returns that may need a copy, from the syntax and the callees'
annotations) or `off`. NIMIC_VALUECHECK_REPORT appends the sites' report (`report()`), with those that never ran.
"""
import ast
import atexit
import dis
import json
import os
import sys
import types
from typing import Callable, NamedTuple

HEADER = "# /// nimic"
_nimic_files: dict = {}  # path -> whether its leading comments hold the nimic header


def is_nimic_file(path: str) -> bool:
    """Whether the file's leading comments hold the `# /// nimic` block (after a license header, too)."""
    if path not in _nimic_files:
        found = False
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\r\n")
                    if line == HEADER:
                        found = True
                    if found or line and not line.startswith("#"):
                        break
        except (OSError, UnicodeDecodeError):
            pass
        _nimic_files[path] = found
    return _nimic_files[path]


def alias_annotation(text: str | None) -> bool:
    """A return annotation whose value is an alias of an existing location: Nim's `var T` / `lent T` (`mut @ T`,
    `lent @ T`), or a template's `untyped` / `typed` expression."""
    if not text:
        return False
    text = text.replace(" ", "")
    return text.startswith(("mut@", "lent@")) or text in ("untyped", "typed")


def mutable_annotation(text: str | None) -> bool:
    """A parameter annotation through which the callee may change the argument: `mut @ T` (Nim `var T`), or a
    template's `untyped` / `typed` parameter (substituted into its body)."""
    if not text:
        return False
    text = text.replace(" ", "")
    return text.startswith("mut@") or text in ("untyped", "typed")


def is_template_decorator(decorator: ast.expr) -> bool:
    """`@template` (also `@nimic.template`, `@template(...)`)."""
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    return (isinstance(decorator, ast.Name) and decorator.id == "template"
            or isinstance(decorator, ast.Attribute) and decorator.attr == "template")


def _pure(expr: ast.expr) -> bool:
    """An expression that can be evaluated again without effects: a name, an attribute chain, a generic instance
    (`cast[ptr T]`, `seq[nint]`)."""
    if isinstance(expr, ast.Name | ast.Constant):
        return True
    if isinstance(expr, ast.Attribute):
        return _pure(expr.value)
    if isinstance(expr, ast.Subscript):
        return _pure(expr.value) and _pure(expr.slice)
    if isinstance(expr, ast.Tuple):
        return all(_pure(e) for e in expr.elts)
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.MatMult):
        return _pure(expr.left) and _pure(expr.right)  # `ptr @ T` in a type argument
    return False


def _root(expr: ast.expr) -> str | None:
    """The variable an l-value is a part of: `x` of `x`, `x.f`, `x[i].g`."""
    while isinstance(expr, (ast.Attribute, ast.Subscript, ast.Starred)):
        expr = expr.value
    return expr.id if isinstance(expr, ast.Name) else None


def _path(expr: ast.expr) -> tuple:
    """The fields an l-value selects in its variable: `("f", "*", "g")` of `x.f[i].g` (`*`: any item)."""
    parts = []
    while isinstance(expr, (ast.Attribute, ast.Subscript, ast.Starred)):
        parts.append(expr.attr if isinstance(expr, ast.Attribute) else "*")
        expr = expr.value
    return tuple(reversed(parts))


def _overlap(a: tuple | None, b: tuple | None) -> bool:
    """Whether two paths in one variable may select the same value (a prefix of the other); None: all of it."""
    if a is None or b is None:
        return True
    return all(x == y or "*" in (x, y) for x, y in zip(a, b))


def _call_roots(expr: ast.expr, into: set) -> None:
    """The variables a call's result may share a value with: its receiver's and arguments' (nested calls' too)."""
    root = _root(expr)
    if root is not None:
        into.add(root)
    elif isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Attribute):
            _call_roots(expr.func.value, into)
        for arg in (*expr.args, *(k.value for k in expr.keywords)):
            _call_roots(arg, into)
    elif isinstance(expr, (ast.Tuple, ast.List)):
        for element in expr.elts:
            _call_roots(element, into)
    elif isinstance(expr, ast.IfExp):
        _call_roots(expr.body, into)
        _call_roots(expr.orelse, into)


def _is_copy(expr: ast.expr) -> bool:
    return (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "copy"
            and not expr.args and not expr.keywords)


class Source(NamedTuple):
    """What a binding binds: an `lvalue` (shares its value; `root` and `path` locate it), a `part` of one
    (unpacked from it), or a `call`'s result (`callee` is its source text when it can be evaluated again, else
    None: it may share; `inputs` the texts of its receiver and arguments that can be)."""
    kind: str
    text: str
    callee: str | None
    root: str | None = None
    path: tuple = ()
    inputs: tuple = ()


def _sources(value: ast.expr, target: str | None = None) -> list[Source]:
    """What `value` binds (a binding of `target`: its own value is not one of a call's inputs)."""
    if _is_copy(value):
        return []
    if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Slice):
        return []  # a slice is a new value (Nim `s[a..b]`)
    if isinstance(value, (ast.Name, ast.Attribute, ast.Subscript)):
        return [Source("lvalue", ast.unparse(value), None, _root(value), _path(value))]
    if isinstance(value, ast.Starred):
        return _sources(value.value, target)
    if isinstance(value, ast.Call):
        func = value.func
        inputs = [func.value] if isinstance(func, ast.Attribute) else []
        inputs += [*value.args, *(k.value for k in value.keywords)]
        return [Source("call", ast.unparse(value), ast.unparse(func) if _pure(func) else None,
                       inputs=tuple(ast.unparse(e) for e in inputs if _pure(e) and (target is None or _root(e) != target)))]
    if isinstance(value, ast.IfExp):
        return _sources(value.body, target) + _sources(value.orelse, target)
    return []  # a literal or an operator's result is a new value


def _roots(value: ast.expr) -> set:
    roots = set()
    if isinstance(value, ast.IfExp):
        return _roots(value.body) | _roots(value.orelse)
    if isinstance(value, ast.Call):
        _call_roots(value, roots)
    elif (root := _root(value)) is not None:
        roots.add(root)
    return roots


class Mutation(NamedTuple):
    """A place that may change a variable's value: a `store` into it (`x.f = v`, `x += v`, `del x[i]`), a
    `method` call on it (`receiver.name(...)`), an `arg`ument of a call (`name` the callee's source, or None;
    `position` / `keyword`, None for `*args`), or `unknown` (a closure or another module may change it). `root`
    is the variable changed, `path` the part of it (None: any part); `start` to `stop` the lines of the statement
    it runs in (a compound statement's header)."""
    line: int
    text: str
    kind: str
    root: str
    path: tuple | None = None
    receiver: str | None = None
    name: str | None = None
    position: int | None = None
    keyword: str | None = None
    start: int | None = None
    stop: int | None = None


class Site:
    """A binding that may need a copy (`target` is its variable), or a `return` (`target` None) of a proc whose
    `-> T` result is a value of its own; checked at run time on its first execution."""
    __slots__ = ("file", "line", "end_line", "target", "text", "sources", "mutations", "state", "runs", "writes",
                 "certain")

    def __init__(self, file: str, stmt: ast.AST, target: str | None, sources: list, mutations: list) -> None:
        self.file, self.line, self.end_line = file, stmt.lineno, stmt.end_lineno
        self.target, self.sources, self.mutations = target, tuple(sources), tuple(mutations)
        self.text = ast.unparse(stmt.value) if target is None else sources[0].text
        self.state = None  # the possible difference (lint): None, not checked yet; "ok"; "error"
        self.runs = self.writes = 0  # the executions checked, of the binding and of the writes after it
        self.certain = None  # "error": a write changed the value while both locations held it

    def __repr__(self) -> str:
        return f"Site({os.path.basename(self.file)}:{self.line} {self.target or 'return'} {self.text})"


def _bound_names(target: ast.expr, into: set) -> None:
    if isinstance(target, ast.Name):
        into.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            _bound_names(element, into)
    elif isinstance(target, ast.Starred):
        _bound_names(target.value, into)


def _owned_locals(func: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset:
    """The variables of `func` that hold values of their own: bound only by assignments. Parameters, loop and
    `with` variables, and global / nonlocal names may be aliases of values others read."""
    assigned, other = set(), {a.arg for a in ast.walk(func.args) if isinstance(a, ast.arg)}
    for node in _scope_nodes(func.body):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            other.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                _bound_names(target, assigned)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            _bound_names(node.target, assigned)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            _bound_names(node.target, other)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            _bound_names(node.optional_vars, other)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            other.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            other.update(node.names)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            other.update((a.asname or a.name).split(".")[0] for a in node.names)
    return frozenset(assigned - other)


_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _scope_nodes(body: list):
    """The nodes of a scope's own code; a nested function, class or lambda is yielded, not entered."""
    stack = list(reversed(body))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, _NESTED):
            stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _position(node: ast.AST) -> tuple:
    return node.lineno, node.col_offset


def _end(node: ast.AST) -> tuple:
    return node.end_lineno, node.end_col_offset


def _header(stmt: ast.AST) -> tuple:
    """The lines a statement's own code runs on: a compound statement's header (up to its body)."""
    first = stmt.pattern.lineno if isinstance(stmt, ast.match_case) else stmt.lineno
    body = getattr(stmt, "body", None)
    if isinstance(body, list) and body:
        return first, max(first, body[0].lineno - 1)
    return first, stmt.end_lineno


_STATEMENTS = (ast.stmt, ast.excepthandler, ast.match_case)


def _immutable_block(node: ast.With) -> bool:
    """`with let:` / `with const:`: its variables can't be changed (Nim rejects it)."""
    return any(isinstance(item.context_expr, ast.Name) and item.context_expr.id in ("let", "const")
               for item in node.items)


class _Scope:
    """What the analysis knows of a function's (or a module's) own code."""

    def __init__(self, file: str, node: ast.AST, body: list, module: bool) -> None:
        self.file, self.module = file, module
        self.owned = frozenset() if module else _owned_locals(node)
        self.reads, self.mutations, self.captured = {}, {}, set()
        self.bindings, self.returns, self.loops, self.immutable = [], [], [], set()
        self.declared = set()  # global / nonlocal
        self._lines = None  # the lines of the statement being visited (_header)
        for child in _scope_nodes(body):  # pre-order: an expression follows the statement it is in
            if isinstance(child, _STATEMENTS):
                self._lines = _header(child)
            self._visit(child)

    def _mutation(self, place: ast.expr, node: ast.AST, kind: str, **fields) -> None:
        root = _root(place)
        if root is not None:
            text = ast.unparse(node)
            start, stop = self._lines or (node.lineno, node.end_lineno)
            self.mutations.setdefault(root, []).append(
                (_position(node), Mutation(node.lineno, text if len(text) <= 60 else text[:57] + "...", kind, root,
                                           _path(place), **fields, start=start, stop=stop)))

    def _store_targets(self, target: ast.expr, stmt: ast.stmt) -> None:
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            self._mutation(target, stmt, "store")
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._store_targets(element, stmt)

    def _pairs(self, target: ast.expr, value: ast.expr, stmt: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self.bindings.append((stmt, target.id, value, True))
        elif isinstance(target, (ast.Tuple, ast.List)):
            if (isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts)
                    and not any(isinstance(e, ast.Starred) for e in (*target.elts, *value.elts))):
                for t, v in zip(target.elts, value.elts):
                    self._pairs(t, v, stmt)
            else:
                names = set()
                _bound_names(target, names)
                for name in sorted(names):  # each one an element of the value
                    self.bindings.append((stmt, name, value, False))

    def _visit(self, node: ast.AST) -> None:
        if isinstance(node, _NESTED):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name):
                    self.captured.add(inner.id)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            self.reads.setdefault(node.id, []).append(_position(node))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            self.loops.append((_position(node), _end(node)))
        elif isinstance(node, ast.With) and _immutable_block(node):
            for inner in ast.walk(node):
                if isinstance(inner, (ast.Assign, ast.AnnAssign)):
                    for target in getattr(inner, "targets", [getattr(inner, "target", None)]):
                        _bound_names(target, self.immutable)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.declared.update(node.names)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                self._store_targets(target, node)
                self._pairs(target, node.value, node)
        elif isinstance(node, ast.AnnAssign):
            self._store_targets(node.target, node)
            if node.value is not None:
                self._pairs(node.target, node.value, node)
        elif isinstance(node, ast.NamedExpr):
            self._pairs(node.target, node.value, node)
        elif isinstance(node, ast.AugAssign):
            self._mutation(node.target, node, "store")  # `x += v` changes a value-type x in place
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                self._store_targets(target, node)
        elif isinstance(node, ast.Return) and node.value is not None:
            self.returns.append(node)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and not _is_copy(node):
                self._mutation(func.value, node, "method", receiver=ast.unparse(func.value), name=func.attr)
            callee = ast.unparse(func) if _pure(func) else None
            for position, arg in enumerate(node.args):
                if isinstance(arg, ast.Starred):
                    self._mutation(arg.value, node, "arg", name=callee)
                else:
                    self._mutation(arg, node, "arg", name=callee, position=position)
            for keyword in node.keywords:
                self._mutation(keyword.value, node, "arg", name=callee, keyword=keyword.arg)

    def _unknown(self, name: str) -> bool:
        """Whether code elsewhere (a closure, another function, another module) may change or read `name`."""
        if name in self.immutable:
            return False
        return name in self.captured or name in self.declared  # a module's global: a function of it uses it

    def _region(self, stmt: ast.AST) -> Callable:
        """Whether a position runs after `stmt`: later in the scope, or anywhere in a loop around it."""
        end = _end(stmt)
        loops = [(start, stop) for start, stop in self.loops if start <= _position(stmt) and end <= stop]
        return lambda pos: pos >= end or any(start <= pos <= stop for start, stop in loops)

    def _sees(self, stmt: ast.AST, change: tuple, read: tuple) -> bool:
        """Whether a read at `read` may run after a change at `change`, both after `stmt`, before `stmt` binds
        again: later in the same pass, or in the next pass of a loop around it before `stmt`."""
        start, end = _position(stmt), _end(stmt)
        loop = next(((a, b) for a, b in self.loops if a <= start and end <= b), None)  # the outermost
        # `stmt`'s own reads count: in the next pass they read the changed value (`c = toStrip` after `c -= 1`)
        if change >= end:
            return read > change or loop is not None and loop[0] <= read < end
        return change < read < end or loop is not None and read > loop[1]

    def _observed(self, name: str, stmt: ast.AST, change: tuple | None) -> bool:
        """Whether `name` may be read after a change (None: a change elsewhere, at any time)."""
        if self._unknown(name):
            return True
        after = self._region(stmt)
        return any(after(pos) and (change is None or self._sees(stmt, change, pos)) for pos in self.reads.get(name, ()))

    def sites(self) -> list[Site]:
        found = []
        for stmt, target, value, whole in self.bindings:
            sources = _sources(value, target)
            if not whole:  # a part of the value: no longer the source's object itself
                sources = [s._replace(kind="part") if s.kind == "lvalue" else s for s in sources]
            if not sources:
                continue
            after = self._region(stmt)
            roots = _roots(value) - {target}
            mutations = []
            # the bound variable changes while a source variable is read (one that isn't a local is read elsewhere)
            changes = [] if target in self.immutable else [
                (pos, m) for pos, m in self.mutations.get(target, ()) if after(pos)]
            if self._unknown(target):
                changes.append((None, Mutation(stmt.lineno, f"{target} (read and changed elsewhere)", "unknown", target)))
            mutations += [m for pos, m in changes
                          if any(root not in self.owned or self._observed(root, stmt, pos) for root in roots)]
            # a source variable changes (where it may select the bound value: `o.f` is not `o.g`) while the bound
            # variable is read
            paths = {}
            for source in sources:
                paths.setdefault(source.root, []).append(source.path if source.kind == "lvalue" else None)
            for root in roots:
                selected = paths.get(root, []) + paths.get(None, []) or [None]
                changes = [(pos, m) for pos, m in self.mutations.get(root, ())
                           if after(pos) and any(_overlap(m.path, p) for p in selected)]
                if self._unknown(root) and root not in self.immutable:
                    changes.append((None, Mutation(stmt.lineno, f"{root} (changed elsewhere)", "unknown", root)))
                mutations += [m for pos, m in changes if self._observed(target, stmt, pos)]
            if mutations:
                found.append(Site(self.file, stmt, target, sources, mutations))
        return found

    def returned(self, value: ast.expr | None = None) -> tuple:
        """The sources of the values the function returns (or `value`, a returned value) that may be shared with
        another location: a parameter, a global, a part of either, a call's result, or a local bound from one of
        these."""
        local_values = {}
        for _, target, bound_value, _ in self.bindings:
            local_values.setdefault(target, []).append(bound_value)
        shared, seen = [], set()

        def visit(value: ast.expr) -> None:
            if isinstance(value, (ast.Tuple, ast.List)):
                for element in value.elts:
                    visit(element)
            elif isinstance(value, ast.IfExp):
                visit(value.body)
                visit(value.orelse)
            elif isinstance(value, (ast.Name, ast.Attribute, ast.Subscript)) and _root(value) in self.owned:
                root = _root(value)  # a local's own value is moved out: what the local was bound to decides
                if root not in seen:
                    seen.add(root)
                    for bound in local_values.get(root, ()):
                        visit(bound)
            else:
                shared.extend(_sources(value))

        for returned in ([value] if value is not None else [r.value for r in self.returns]):
            visit(returned)
        return tuple(dict.fromkeys(shared))

    def return_sites(self) -> list[Site]:
        """The returns of a value that may be shared: Nim's `-> T` result is a copy, so the proc writes
        `return x.copy()` (or returns `lent @ T`); its callers then bind a value of their own."""
        return [Site(self.file, ret, None, sources, []) for ret in self.returns if (sources := self.returned(ret.value))]


def _returns_value(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a function's result is a value of its own (Nim `-> T`): not an alias (`mut @ T`, `lent @ T`,
    `untyped`), a template's, an iterator's, or a Python protocol method's (`__iadd__` returns self)."""
    if func.name.startswith("__") and func.name.endswith("__"):
        return False
    if any(is_template_decorator(d) for d in func.decorator_list):
        return False
    if func.returns is not None and alias_annotation(ast.unparse(func.returns)):
        return False
    return not any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in _scope_nodes(func.body))


def _first_line(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """The line its code object starts at (`co_firstlineno`): its first decorator's."""
    return func.decorator_list[0].lineno if func.decorator_list else func.lineno


def _module_sites(file: str, tree: ast.AST) -> list[Site]:
    body = tree.body if isinstance(tree, (ast.Module, ast.Interactive)) else [tree]
    return _Scope(file, tree, [n for n in body if not isinstance(n, ast.ClassDef)], module=True).sites()


def _function_sites(file: str, func: ast.FunctionDef | ast.AsyncFunctionDef, returns: bool = True) -> list[Site]:
    scope = _Scope(file, func, func.body, module=False)
    return scope.sites() + (scope.return_sites() if returns and _returns_value(func) else [])


class Analysis:
    """A module's (or a compiled tree's) sites, and what its functions return, all at once (the checks
    analyze a function when it first runs)."""

    def __init__(self, tree: ast.AST, file: str) -> None:
        self.file = file
        self.sites: list[Site] = _module_sites(file, tree)
        self.returns: dict = {}  # (first line, name) -> Source tuple
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.sites += _function_sites(file, node)
                self.returns[(_first_line(node), node.name)] = _Scope(file, node, node.body, module=False).returned()


def analyze(tree: ast.AST, file: str) -> Analysis:
    return Analysis(tree, file)


class _Index:
    """A file's functions and lambdas, and what they return (computed on the first question)."""

    def __init__(self, tree: ast.AST | None, file: str) -> None:
        self.file, self.functions, self.lambdas, self.returns = file, {}, {}, {}
        for node in ast.walk(tree) if tree is not None else ():
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[(_first_line(node), node.name)] = node
            elif isinstance(node, ast.Lambda):  # its body is its result (`cast[T]` is `lambda x: T._n_cast(x)`)
                key = (node.lineno, "<lambda>")
                self.lambdas[key] = tuple(dict.fromkeys(self.lambdas.get(key, ()) + tuple(_sources(node.body))))

    def returned(self, key: tuple) -> tuple | None:
        if key not in self.returns:
            node = self.functions.get(key)
            self.returns[key] = (self.lambdas.get(key) if node is None
                                 else _Scope(self.file, node, node.body, module=False).returned())
        return self.returns[key]


_indexes: dict = {}  # file -> _Index
_trees: dict = {}  # file -> its tree, parsed by `watch` (indexed on the first question)


def _index(file: str) -> _Index:
    if file not in _indexes:
        tree = _trees.pop(file, None)
        if tree is None:
            try:
                with open(file, encoding="utf-8") as f:
                    tree = ast.parse(f.read(), file)
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
                pass
        _indexes[file] = _Index(tree, file)
    return _indexes[file]


def returned_sources(code) -> tuple | None:
    """What a function returns that may be shared (`_Scope.returned`): a nimic template's, or any other Python
    code's (core and std procs); None if its source can't be read."""
    return _index(code.co_filename).returned((code.co_firstlineno, code.co_name))


# --- Run time ---

class ValueCopyError(Exception):
    """A value-type value bound without the copy Nim's assignment makes, and then changed while both locations
    held it: Python and Nim now hold different values."""


class Policy(NamedTuple):
    """The type system's answers (nimic.ntypesystem): whether assigning `value` copies it in Nim; whether a
    call's result may share a value-type value with another location; whether a call may change an argument
    (`position`, `keyword`; the receiver of a bound method is position -1); whether a value is a view of
    storage it shares (an array slot's scalar: each read is a new view); whether a value is an object or a view
    of its storage; a plain snapshot of what a value holds (equal snapshots: the same value)."""
    is_value: Callable
    may_alias: Callable
    mutates: Callable
    is_view: Callable
    shares: Callable
    fingerprint: Callable


INPUTS = "inputs"  # Policy.may_alias: shared only when the result is one of the call's inputs or a part of one
MODES = ("error", "warn", "lint", "off")

_STORES = frozenset(("STORE_FAST", "STORE_NAME", "STORE_GLOBAL", "STORE_DEREF", "STORE_FAST_STORE_FAST",
                     "STORE_FAST_LOAD_FAST"))
_STORE, _AFTER = 0, 1
_MISSING = object()
_RUNS = 64  # the executions of a binding checked (then its instructions are no longer watched)
_WRITES = 64  # the writes checked after a binding's executions

_policy: Policy | None = None
_mode = "off"
_tool = None
_watched: dict = {}  # code -> {offset: [(role, site)]}
_watched_returns: dict = {}  # code -> {offset of a RETURN_VALUE: [site]} (lint)
_stores: dict = {}  # id(frame) -> {site: id of the target's value before the store}: checked on the next instruction
_sites: list = []  # every watched site (report)
_lazy: dict = {}  # code -> (file, its FunctionDef): analyzed when it first runs
_started: set = set()
_compiled: dict = {}  # expression text -> code
_writes_at: dict = {}  # code -> {first line of a statement: [(site, a mutation of it the statement runs)]}
_base_events: dict = {}  # code -> its local events while none of its frames is armed
_armed: dict = {}  # id(frame) -> _Armed
_armed_codes: dict = {}  # code -> the number of its armed frames (LINE events on while there is one)
_unwind_watched = False


class _Armed:
    """A frame's bindings whose value another location holds too: `sites` maps a site to (the value, the
    source holding it); `pending` the writes started, compared when their statement is done."""
    __slots__ = ("frame", "sites", "pending")

    def __init__(self, frame) -> None:
        self.frame, self.sites, self.pending = frame, {}, []


class _Write(NamedTuple):
    site: Site
    mutation: Mutation
    value: object
    source: Source
    before: object  # the value's fingerprint before the statement


def installed() -> bool:
    return _tool is not None


def install(policy: Policy, mode: str = "error") -> None:
    """Starts checking (sys.monitoring, a tool of its own: a debugger or coverage tool runs beside it)."""
    global _policy, _mode, _tool
    if mode not in MODES:
        raise ValueError(f"NIMIC_VALUECHECK={mode!r}: one of {', '.join(MODES)}")
    _policy, _mode = policy, mode
    if _tool is not None or mode == "off":
        return
    monitoring = sys.monitoring
    for tool in (4, 3):
        if monitoring.get_tool(tool) is None:
            monitoring.use_tool_id(tool, "nimic valuecheck")
            _tool = tool
            break
    else:
        return  # every free tool id is taken: no checks
    events = monitoring.events
    monitoring.register_callback(_tool, events.INSTRUCTION, _on_instruction)
    monitoring.register_callback(_tool, events.PY_RETURN, _on_return)
    monitoring.register_callback(_tool, events.PY_START, _on_start)
    monitoring.register_callback(_tool, events.LINE, _on_line)
    monitoring.register_callback(_tool, events.PY_UNWIND, _on_unwind)
    atexit.register(_report_at_exit)


def watch(code, source: str | ast.AST, file: str, nimic: bool | None = None) -> None:
    """Checks the sites of a nimic module's code (`source` is its text or tree): its module-level code now, each
    function (nested code objects) when it first runs (PY_START). `nimic` tells whether it is nimic code when
    `file` can't (generated code); by default the file's header."""
    if nimic is not None:
        _nimic_files[file] = nimic  # generated code (`<template_expand ...>`): its procs are nimic procs
    if _tool is None or not is_nimic_file(file):
        return
    tree = ast.parse(source, file) if isinstance(source, str) else source
    if (isinstance(source, str) or file.startswith("<")) and file not in _indexes:
        _trees[file] = tree  # the module's own tree (a specialized generic's is not the file's)
    functions = {(_first_line(n), n.name): n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    _attach(code, _module_sites(file, tree))
    stack = [c for c in code.co_consts if hasattr(c, "co_code")]
    while stack:
        current = stack.pop()
        stack.extend(c for c in current.co_consts if hasattr(c, "co_code"))
        func = functions.get((current.co_firstlineno, current.co_name))
        if func is not None and current not in _lazy:
            _lazy[current] = (file, func)
            sys.monitoring.set_local_events(_tool, current, sys.monitoring.events.PY_START)


def _on_start(code, offset):
    entry = _lazy.pop(code, None)
    if entry is not None:
        _started.add(code)
        _attach(code, _function_sites(*entry, returns=_mode == "lint"))
    return sys.monitoring.DISABLE


def _attach(code, sites: list) -> None:
    """Watches the stores and returns of `sites` in `code` (not its nested code)."""
    if not sites:
        return
    by_name = {}
    for site in sites:
        by_name.setdefault(site.target, []).append(site)
    matched = set()
    offsets, returns = {}, {}
    instructions = list(dis.get_instructions(code))
    for index, ins in enumerate(instructions):
        if ins.line_number is None:
            continue
        if ins.opname == "RETURN_VALUE":
            for site in by_name.get(None, ()):
                if site.line <= ins.line_number <= site.end_line:
                    returns.setdefault(ins.offset, []).append(site)
                    matched.add(site)
        elif ins.opname in _STORES and index + 1 < len(instructions):
            names = ins.argval if isinstance(ins.argval, tuple) else (ins.argval,)
            if ins.opname == "STORE_FAST_LOAD_FAST":
                names = names[:1]
            for name in names:
                for site in by_name.get(name, ()):
                    if site.line <= ins.line_number <= site.end_line:
                        offsets.setdefault(ins.offset, []).append((_STORE, site))
                        offsets.setdefault(instructions[index + 1].offset, []).append((_AFTER, site))
                        matched.add(site)
    writes = {}
    for site in matched:
        for mutation in site.mutations:
            if site.target is not None and mutation.start is not None:
                writes.setdefault(mutation.start, []).append((site, mutation))
    if writes:
        _writes_at[code] = writes
    events = sys.monitoring.events
    if offsets:
        _watched[code] = offsets
    if returns:
        _watched_returns[code] = returns
    _base_events[code] = (events.INSTRUCTION if offsets else 0) | (events.PY_RETURN if returns else 0)
    _set_events(code)
    _sites.extend(site for site in sites if site in matched)


def _set_events(code) -> None:
    """`code`'s local events: its own, and LINE and PY_RETURN while a frame of it is armed (setting them anew
    enables the locations a callback disabled)."""
    events = _base_events.get(code, 0)
    if _armed_codes.get(code):
        events |= sys.monitoring.events.LINE | sys.monitoring.events.PY_RETURN
    sys.monitoring.set_local_events(_tool, code, 0)
    sys.monitoring.set_local_events(_tool, code, events)


def _on_instruction(code, offset):
    entries = _watched.get(code, {}).get(offset)
    if not entries:
        return sys.monitoring.DISABLE
    frame = None
    active = False
    for role, site in entries:
        if site.runs >= _RUNS or site.certain is not None:
            continue
        active = True
        frame = frame or sys._getframe(1)
        if role == _STORE:
            _stores.setdefault(id(frame), {})[site] = id(_lookup(frame, site.target))
        else:
            stored = _stores.get(id(frame))
            if stored and site in stored:
                before = stored.pop(site)
                if not stored:
                    del _stores[id(frame)]
                _bound(site, frame, before)
                line = frame.f_lineno
                if line is not None and not site.line <= line <= site.end_line:
                    _at_line(frame, code, line)  # its LINE event came before the binding was armed
    return None if active else sys.monitoring.DISABLE


def _bound(site: Site, frame, before: int) -> None:
    """After a binding: arms it when its value is a value type another location holds too."""
    value = _lookup(frame, site.target)
    if value is _MISSING:
        return  # not bound (another path): checked on the next execution
    site.runs += 1
    if _mode == "lint" and site.state is None:
        _check_possible(site, frame, before, value)
    if id(value) == before:
        return  # bound to the value it held (`pos = f(pos)` returning its argument)
    entry = _armed.get(id(frame))
    if entry is not None:
        entry.sites.pop(site, None)  # bound anew: the earlier value no longer counts
    if not _policy.is_value(value):
        return
    source = next((s for s in site.sources if _holds(s, frame, value)), None)
    if source is not None:
        _arm(frame, site, value, source)


def _arm(frame, site: Site, value, source: Source) -> None:
    global _unwind_watched
    entry = _armed.get(id(frame))
    if entry is None:
        entry = _armed[id(frame)] = _Armed(frame)
        code = frame.f_code
        _armed_codes[code] = _armed_codes.get(code, 0) + 1
        if _armed_codes[code] == 1:
            _set_events(code)
        if not _unwind_watched:  # an exception leaving an armed frame disarms it (a global event)
            _unwind_watched = True
            sys.monitoring.set_events(_tool, sys.monitoring.get_events(_tool) | sys.monitoring.events.PY_UNWIND)
    entry.sites[site] = (value, source)


def _disarm(frame) -> _Armed:
    entry = _armed.pop(id(frame))
    code = frame.f_code
    _armed_codes[code] -= 1
    if not _armed_codes[code]:
        del _armed_codes[code]
        _set_events(code)
    return entry


def _armed_entry(frame) -> _Armed | None:
    entry = _armed.get(id(frame))
    return entry if entry is not None and entry.frame is frame else None


def _on_line(code, line):
    _at_line(sys._getframe(1), code, line)
    return None  # (another frame of this code may be armed)


def _at_line(frame, code, line: int) -> None:
    """A line starts in `frame`: the bindings stored before it are checked, the writes whose statement is done
    compared, and the writes starting here fingerprinted."""
    stored = _stores.pop(id(frame), None)
    if stored:  # the instruction after the store is on this line: its event comes after this one
        for site, before in stored.items():
            _bound(site, frame, before)
    entry = _armed_entry(frame)
    if entry is None:
        return
    if entry.pending:
        done = [w for w in entry.pending if not w.mutation.start <= line <= w.mutation.stop]
        if done:
            entry.pending = [w for w in entry.pending if w.mutation.start <= line <= w.mutation.stop]
            for write in done:
                _compare(write, frame)
    for site, mutation in _writes_at.get(code, {}).get(line, ()):
        armed = entry.sites.get(site)
        if armed is None or site.certain is not None or site.writes >= _WRITES:
            continue
        if any(w.site is site and w.mutation is mutation for w in entry.pending):
            continue  # the statement runs this line again (a call's arguments on the next lines)
        value, source = armed
        if _lookup(frame, site.target) is value and _holds(source, frame, value):
            site.writes += 1
            entry.pending.append(_Write(site, mutation, value, source, _policy.fingerprint(value)))


def _on_return(code, offset, value):
    frame = sys._getframe(1)
    entry = _armed_entry(frame)
    if entry is not None:
        _disarm(frame)
        for write in entry.pending:
            _compare(write, frame)
    sites = _watched_returns.get(code, {}).get(offset)
    if sites:
        for site in sites:
            if site.state is None:
                _check_return(site, frame, value)
        if any(site.state is None for site in sites):
            return None
    return None if code in _armed_codes else sys.monitoring.DISABLE


def _on_unwind(code, offset, exception):
    if _armed:
        frame = sys._getframe(1)
        if _armed_entry(frame) is not None:
            _disarm(frame)  # the write raised, or a later statement: its changes are not compared


def _eval(text: str, frame):
    code = _compiled.get(text)
    if code is None:
        code = _compiled[text] = compile(text, "<valuecheck>", "eval")
    return eval(code, frame.f_globals, frame.f_locals)


def _lookup(frame, name: str):
    value = frame.f_locals.get(name, _MISSING)
    return frame.f_globals.get(name, _MISSING) if value is _MISSING else value


def _holds(source: Source, frame, value) -> bool:
    """Whether the location the value was bound from holds it now: the l-value is the object (or a view of the
    same storage), or the object is a part of the l-value (unpacked from it) or of a call's inputs."""
    try:
        if source.kind == "lvalue":
            held = _eval(source.text, frame)
            return held is value or _policy.shares(value, held)
        roots = [_eval(source.text, frame)] if source.kind == "part" else [_eval(t, frame) for t in source.inputs]
    except Exception:  # not readable here now (a later binding, an index out of range): not shown to hold it
        return False
    return _reachable(value, roots, beyond=False)


def _compare(write: _Write, frame) -> None:
    """After a write's statement: a changed value both locations still hold is a certain difference."""
    site, value = write.site, write.value
    if site.certain is not None or _policy.fingerprint(value) == write.before:
        return
    if _lookup(frame, site.target) is not value or not _holds(write.source, frame, value):
        return
    site.certain = "error"
    mutation, source = write.mutation, write.source
    held = source.text if source.kind != "call" else f"an input of {source.text} ({', '.join(source.inputs)})"
    callee = (f" (or return a copy from {source.callee}: its `-> T` result is a value of its own)"
              if source.kind == "call" and source.callee else "")
    message = (f"{site.file}:{site.line}: `{site.target} = {site.text}` binds the {type(value).__name__} that "
               f"{held} holds, and line {mutation.line} (`{mutation.text}`) changed it while both held it: Nim's "
               f"assignment copies the value, so in Nim only one of them changed; write "
               f"`{site.target} = {site.text}.copy()`{callee}")
    if _mode == "error":
        raise ValueCopyError(message)
    print(f"nimic valuecheck: {message}", file=sys.stderr)


# --- lint: possible differences (NIMIC_VALUECHECK=lint) ---

def _shares(source: Source, frame, value) -> bool:
    """Whether the bound value may be shared with another location."""
    if source.kind == "lvalue":
        # the location still holds it (not `(u, w) = (w, u)`, which swaps, sharing nothing), or a view of it
        try:
            return _eval(source.text, frame) is value or _policy.is_view(value)
        except Exception:  # not readable here (a local of another path): it may share
            return True
    if source.kind == "part" or source.callee is None:
        return True
    try:
        may = _policy.may_alias(_eval(source.callee, frame))
    except Exception:  # the callee can't be evaluated again here: it may share
        return True
    if may != INPUTS:
        return bool(may)
    try:
        inputs = [_eval(text, frame) for text in source.inputs]
    except Exception:  # an input is no longer readable: it may share
        return True
    return _reachable(value, inputs)


_LEAVES = (int, float, complex, str, bytes, bool, type(None), types.ModuleType, types.FunctionType,
           types.BuiltinFunctionType, types.MethodType)


def _reachable(value, roots: list, depth: int = 3, limit: int = 20000, beyond: bool = True) -> bool:
    """Whether `value` is one of `roots` or a part of one (or a view of its storage, Policy.shares): a field, an
    item, an item's field (`__dict__` values and container items, `depth` levels down); `beyond` answers for a
    larger graph than `limit` objects."""
    seen, frontier = set(), list(roots)
    for _ in range(depth + 1):
        following = []
        for obj in frontier:
            if obj is value or _policy.shares(value, obj):
                return True
            if isinstance(obj, _LEAVES) or id(obj) in seen:
                continue
            seen.add(id(obj))
            if len(seen) > limit:
                return beyond
            if isinstance(obj, dict):
                following.extend(obj.values())
            elif isinstance(obj, (list, tuple, set, frozenset)):
                following.extend(obj)
            else:
                fields = getattr(obj, "__dict__", None)
                if isinstance(fields, (dict, types.MappingProxyType)):
                    following.extend(v for v in fields.values() if not callable(v) or hasattr(v, "copy"))
        frontier = following
    return False


_UNCHANGING = (type, types.FunctionType, types.BuiltinFunctionType)  # namespaces of types and procs, not data


def _changes(mutation: Mutation, frame) -> bool:
    """Whether `mutation` may change the value (resolved with the callees the frame sees)."""
    if isinstance(_lookup(frame, mutation.root), _UNCHANGING):
        return False  # `Enum.member`, a proc passed along
    if mutation.kind in ("store", "unknown"):
        return True
    try:
        if mutation.kind == "method":
            return _policy.mutates(getattr(_eval(mutation.receiver, frame), mutation.name), -1, None)
        if mutation.name is None:
            return True
        return _policy.mutates(_eval(mutation.name, frame), mutation.position, mutation.keyword)
    except Exception:  # not resolvable here (a later name, an index out of range): it may change it
        return True


def _check_possible(site: Site, frame, before: int, value) -> None:
    """lint: a binding that may differ from Nim (a shared value-type value a later line may change)."""
    site.state = "ok"
    if id(value) == before or not _policy.is_value(value):
        return  # bound to the value it held (`pos = f(pos)` returning its argument), or not a value type
    source = next((s for s in site.sources if _shares(s, frame, value)), None)
    if source is None:
        return
    mutation = next((m for m in site.mutations if _changes(m, frame)), None)
    if mutation is None:
        return
    site.state = "error"
    print(f"nimic valuecheck (lint): {site.file}:{site.line}: `{site.target} = {site.text}` binds a "
          f"{type(value).__name__} that {'the call may share with' if source.kind == 'call' else 'is shared with'} "
          f"another location, and line {mutation.line} (`{mutation.text}`) may change one of them while the other "
          f"is read: Nim's assignment copies the value; write `{site.target} = {site.text}.copy()`", file=sys.stderr)


def _check_return(site: Site, frame, value) -> None:
    """lint: a `-> T` proc returning a value another location holds (a getter: Nim returns a copy)."""
    site.state = "ok"
    if not _policy.is_value(value):
        return
    source = next((s for s in site.sources if _shares(s, frame, value)), None)
    if source is None:
        return
    site.state = "error"
    print(f"nimic valuecheck (lint): {site.file}:{site.line}: `return {site.text}` returns a "
          f"{type(value).__name__} {'that the call ' + source.text + ' may share' if source.kind == 'call' else 'shared'} "
          f"with another location ({source.text}), but the proc's `-> T` result is a value of its own in Nim: write "
          f"`return {site.text}.copy()`, or declare the result `lent @ T` / `mut @ T`", file=sys.stderr)


def report() -> dict:
    """The watched sites: how many ran, the certain differences (`errors`), the possible ones (`possible`, lint)
    and the sites that never ran."""
    ran = [site for site in _sites if site.runs or site.state is not None]
    unchecked = [f"{site.file}:{site.line}" for site in _sites if not (site.runs or site.state is not None)]
    unchecked += [f"{site.file}:{site.line}" for file, func in _lazy.values()  # functions that never ran
                  for site in _function_sites(file, func, returns=_mode == "lint")]
    return {"sites": len(ran) + len(unchecked),
            "ran": len(ran),
            "errors": [f"{site.file}:{site.line}" for site in _sites if site.certain == "error"],
            "possible": [f"{site.file}:{site.line}" for site in _sites if site.state == "error"],
            "unchecked": unchecked}


def _report_at_exit() -> None:
    path = os.environ.get("NIMIC_VALUECHECK_REPORT")
    if not path:
        return
    entry = {"program": sys.argv[0] if sys.argv else "", **report()}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
