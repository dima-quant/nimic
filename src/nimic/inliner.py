"""
nimic inliner module
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Compile-time template inlining via AST rewriting.

Provides two decorators:
  @template           — registers a function as an inlinable template.
                        Functions returning `untyped` are stored as AST
                        fragments keyed by name in _n_templates.
                        A template whose trailing parameters are code blocks
                        (annotated typed/untyped and used as bare statements,
                        Nim `t(args): block` / `t(args): b1 do: b2`) becomes a
                        block template: calling it returns a context manager,
                        so `with t(args):` runs the template around the block.
  @template_expand    — rewrites the decorated function's AST, replacing
                        calls to registered templates with the template's
                        body (parameter names substituted with call args),
                        and `with t(args):` of a block template that uses its
                        caller's variables with its body around the block.

Internal machinery:
  _ParameterReplacer  — AST NodeTransformer that substitutes parameter
                        Name nodes with argument nodes from the call site.
  _TemplateInliner    — AST NodeTransformer that walks Expr statements,
                        detects calls to registered templates, and splices
                        in the transformed body.
"""

from __future__ import annotations

import ast
import builtins
import contextvars
import copy
import dis
import inspect
import linecache
import sys
import textwrap
import types
import warnings
from functools import wraps

from nimic.ntypesystem import (dispatch, _n_registry, _n_routine_pragmas, _n_templates, _n_template_codes,
                                _NGeneric)
from nimic.nsystem import _n_node_at
from nimic import valuecheck


class TemplateBlockError(RuntimeError):
    """A block template call whose blocks don't match its uses: a block the template would skip or run
    twice (not expressible with `with`), or a `with do:` block that the template doesn't take."""


# innermost-last stack of block template calls whose `with` body is running
_n_active_block_calls: contextvars.ContextVar = contextvars.ContextVar("_n_active_block_calls", default=())


class _BlockTemplateCall:
    """A call of a block template: the context manager behind `with t(args):` (and `with do:` for
    further blocks). The template runs as a generator that yields where its blocks go."""

    def __init__(self, gen_fn, args: tuple, n_blocks: int, name: str):
        self._gen_fn, self._args, self._n_blocks, self._name = gen_fn, args, n_blocks, name
        self._next_block = 0
        self._entered = False

    def _run_to_block(self) -> None:
        """Run the template up to its next block; the block must be the next one in order."""
        try:
            index = next(self._gen)
        except StopIteration:
            raise TemplateBlockError(
                f"template {self._name} skipped block {self._next_block + 1} of {self._n_blocks}: "
                "a template that may skip its block can't be called with `with`") from None
        if index != self._next_block:
            raise TemplateBlockError(f"template {self._name} runs block {index + 1} where block "
                                     f"{self._next_block + 1} is expected")
        self._next_block += 1

    def __enter__(self):
        self._entered = True
        self._gen = self._gen_fn(*self._args)
        self._token = _n_active_block_calls.set(_n_active_block_calls.get() + (self,))
        self._run_to_block()
        return None

    def _advance_do(self) -> None:
        """`with do:` inside the block: run the template between the blocks."""
        if self._next_block >= self._n_blocks:
            raise TemplateBlockError(f"template {self._name} takes {self._n_blocks} block(s); "
                                     "an extra `with do:` block was given")
        self._run_to_block()

    def __exit__(self, exc_type, exc, tb):
        _n_active_block_calls.reset(self._token)
        if exc_type is not None:
            try:
                self._gen.throw(exc)
            except StopIteration:
                return True  # the template handled the exception and finished
            except BaseException as raised:
                if raised is exc:
                    return False
                raise
            raise TemplateBlockError(f"template {self._name} continued after an exception in its block")
        if self._next_block != self._n_blocks:
            raise TemplateBlockError(f"template {self._name} takes {self._n_blocks} blocks, "
                                     f"{self._next_block} given (add `with do:` blocks)")
        try:
            next(self._gen)
        except StopIteration:
            return False
        raise TemplateBlockError(f"template {self._name} runs a block twice: not expressible with `with`")

    def __iter__(self):
        """`for _ in t(args):` — a template that runs its block in a loop (Nim `t(args): body` of a template
        such as `loopInto`): one iteration per run of the block. A `break` leaves the template's loop and
        the template finishes (Nim); a `return` or an exception leaves the template where it is (its
        `finally` clauses run). A `continue` resumes the template after the block (Nim would skip the rest
        of the template's loop body: the same when nothing follows the block there)."""
        if self._n_blocks != 1:
            raise TemplateBlockError(f"template {self._name} takes {self._n_blocks} blocks: `for` gives one")
        self._entered = True
        gen = self._gen_fn(*self._args)
        try:
            next(gen)
        except StopIteration:
            return  # the template didn't run its block
        while True:
            try:
                yield
            except GeneratorExit:
                if _n_closed_by_break(sys._getframe(1)):
                    try:
                        gen.send(True)
                    except StopIteration:
                        return
                    raise TemplateBlockError(f"template {self._name} runs its block after a `break` "
                                             "(the block is not in the template's innermost loop)") from None
                gen.close()
                raise
            try:
                next(gen)
            except StopIteration:
                return

    def __del__(self):
        if not self._entered:
            warnings.warn(f"block template {self._name} called without `with`: its block never ran",
                          RuntimeWarning, stacklevel=2)


def _n_closed_by_break(frame) -> bool:
    """Whether the `for` loop running in `frame` drops its iterator because of a `break` (not a `return` or
    an exception): the statement at the current instruction is the `break`, or the iterator is popped and
    a jump follows. (A `break` inside `try`/`finally` that ends the function compiles like a `return`.)"""
    if _n_node_at(frame, ast.Break) is not None:
        return True
    ops = list(dis.get_instructions(frame.f_code))
    at = next((i for i, op in enumerate(ops) if op.offset == frame.f_lasti), None)
    return (at is not None and ops[at].opname in ("POP_TOP", "POP_ITER") and at + 1 < len(ops)
            and ops[at + 1].opname.startswith("JUMP"))


class _DoBlock:
    """`with do:` — the next block of the innermost block template call (Nim `do:`)."""

    def __enter__(self):
        calls = _n_active_block_calls.get()
        if not calls:
            raise TemplateBlockError("`with do:` outside the block of a block template call")
        calls[-1]._advance_do()
        return None

    def __exit__(self, *exc):
        return False


do = _DoBlock()


def _n_block_params(func_def: ast.FunctionDef, annotations: dict) -> list[str]:
    """The trailing parameters of a template that are code blocks: annotated typed/untyped and used as
    bare statements (`body`, or `return body` in templates written with -> untyped)."""
    params = [a.arg for a in func_def.args.args]
    used = set()
    for node in ast.walk(func_def):
        if isinstance(node, (ast.Expr, ast.Return)) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
    blocks = []
    for name in reversed(params):
        ann = annotations.get(name)
        ann = ann if isinstance(ann, str) else getattr(ann, "__name__", "")
        if ann in ("typed", "untyped") and name in used:
            blocks.insert(0, name)
        else:
            break
    return blocks


class _BlockYields(ast.NodeTransformer):
    """Replace the bare statements `block` (and `return block`) by `yield <block index>`. Inside a loop of
    the template it is `if (yield <index>): break`: a `break` in the block of `for _ in t():` leaves the
    template's loop, as Nim's `break` in the expanded body does (_BlockTemplateCall.__iter__ sends True)."""

    def __init__(self, blocks: list[str]):
        self.index = {name: i for i, name in enumerate(blocks)}
        self.loops = 0

    def _maybe(self, node):
        if isinstance(node.value, ast.Name) and node.value.id in self.index:
            yield_ = ast.Yield(ast.Constant(self.index[node.value.id]))
            if self.loops:
                return ast.copy_location(ast.If(test=yield_, body=[ast.Break()], orelse=[]), node)
            return ast.copy_location(ast.Expr(yield_), node)
        return node

    visit_Expr = _maybe
    visit_Return = _maybe

    def _loop(self, node):
        self.loops += 1
        node.body = [self.visit(stmt) for stmt in node.body]
        self.loops -= 1
        node.orelse = [self.visit(stmt) for stmt in node.orelse]
        return node

    visit_While = visit_For = _loop

    def visit_FunctionDef(self, node):  # nested procs keep their own statements
        return node


def _n_make_block_template(template_func, func_def: ast.FunctionDef, blocks: list[str]):
    """The generator of a block template and the factory (signature without the block parameters)
    that dispatch registers; the factory returns the context manager for `with`. A generic template's
    factory is generic (dispatch binds its type parameters), and calls the generator specialized with them."""
    gen_def = copy.deepcopy(func_def)
    gen_def.decorator_list = []
    gen_def.returns = None
    type_params, gen_def.type_params = gen_def.type_params, []  # compiled plain, specialized from its source
    # block parameters may carry placeholder defaults (`body: typed = None` after defaulted parameters)
    first_default = len(gen_def.args.args) - len(gen_def.args.defaults)
    gen_def.args.defaults = [d for i, d in enumerate(gen_def.args.defaults, first_default)
                             if gen_def.args.args[i].arg not in blocks]
    gen_def.args.args = [a for a in gen_def.args.args if a.arg not in blocks]
    yields = _BlockYields(blocks)
    gen_def.body = [yields.visit(stmt) for stmt in gen_def.body]
    freevars = template_func.__code__.co_freevars
    if freevars:
        # a template nested in a proc: compile it inside a wrapper declaring the captured names, so they
        # stay free variables bound to the original closure cells
        wrapper = ast.FunctionDef(name="__n_wrapper", args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[],
                                  kw_defaults=[], defaults=[]), body=[
            *(ast.Assign(targets=[ast.Name(id=v, ctx=ast.Store())], value=ast.Constant(None)) for v in freevars),
            gen_def, ast.Return(value=ast.Name(id=gen_def.name, ctx=ast.Load()))], decorator_list=[], returns=None,
            type_params=[])
        module = ast.Module(body=[wrapper], type_ignores=[])
    else:
        module = ast.Module(body=[gen_def], type_ignores=[])
    ast.fix_missing_locations(module)
    ast.increment_lineno(module, template_func.__code__.co_firstlineno - 1)
    code = compile(module, inspect.getsourcefile(template_func) or "<template>", "exec")
    valuecheck.watch(code, module, code.co_filename)  # its bindings are checked (rule:valuecheck)
    if freevars:
        code = next(c for c in code.co_consts if isinstance(c, types.CodeType) and c.co_name == "__n_wrapper")
    gen_code = next(c for c in code.co_consts if isinstance(c, types.CodeType) and c.co_name == gen_def.name)
    defaults = template_func.__defaults__
    if defaults:
        kept = len(gen_def.args.args)
        first_default = len(func_def.args.args) - len(defaults)
        defaults = tuple(d for i, d in enumerate(defaults, first_default) if i < kept) or None
    closure = None
    if gen_code.co_freevars:
        cells = dict(zip(template_func.__code__.co_freevars, template_func.__closure__ or ()))
        closure = tuple(cells.get(name) or types.CellType() for name in gen_code.co_freevars)
    gen_fn = types.FunctionType(gen_code, template_func.__globals__, gen_def.name, defaults, closure)
    name = template_func.__name__
    n_blocks = len(blocks)
    param_names = [a.arg for a in gen_def.args.args]
    arg_tuple = "(" + "".join(f"{n}, " for n in param_names) + ")"
    gen, type_list = "_gen", ""
    if type_params:
        gen_def.type_params = type_params
        gen_fn._n_source = ast.unparse(gen_def)
        gen_fn.__type_params__ = template_func.__type_params__
        gen_fn = _NGeneric(gen_fn)
        type_list = "[" + ", ".join(ast.unparse(t) for t in type_params) + "]"
        gen = "_gen[" + ", ".join(t.name for t in type_params) + "]"
    factory_ns = {"_call": _BlockTemplateCall, "_gen": gen_fn, "_n": n_blocks}
    factory_src = (f"def {name}{type_list}({', '.join(param_names)}):\n"
                   f"    return _call({gen}, {arg_tuple}, _n, {name!r})\n")
    exec(factory_src, factory_ns)
    factory = factory_ns[name]
    if type_params:
        factory._n_source = factory_src  # dispatch reads the type parameters and specializes from it
    factory.__defaults__ = defaults
    factory.__annotations__ = {k: template_func.__annotations__.get(k, "untyped") for k in param_names}
    factory.__module__ = template_func.__module__
    factory.__qualname__ = template_func.__qualname__
    factory.__doc__ = template_func.__doc__
    factory._n_globals = template_func.__globals__  # dispatch resolves annotations in the template's module
    factory._n_block_params = tuple(blocks)
    _n_registry.block_templates.add(name)  # the transpiler writes `for _ in t(...):` as `t(...):`
    return factory


def _n_declared_locals(func_def: ast.FunctionDef) -> set[str]:
    """Names a template body declares itself (`with var:`/`with let:`/`with const:` blocks, `for` loop
    variables): Nim gensyms them, they are not the caller's."""
    names = set()
    for node in ast.walk(func_def):
        if isinstance(node, ast.For):
            names |= {n.id for n in ast.walk(node.target) if isinstance(n, ast.Name)}
        if isinstance(node, ast.With) and any(isinstance(i.context_expr, ast.Name)
                                              and i.context_expr.id in ("var", "let", "const") for i in node.items):
            for stmt in node.body:
                targets = stmt.targets if isinstance(stmt, ast.Assign) else [getattr(stmt, "target", None)]
                names |= {t.id for t in targets if isinstance(t, ast.Name)}
    return names


def _n_uses_caller_scope(func_def: ast.FunctionDef, module_globals: dict) -> bool:
    """A statement template (no return type) whose body assigns a name that is not its own, assigns one of
    its parameters, or reads a name that is neither a parameter, its own local, a global of its module nor
    a builtin. Nim binds such open symbols at the call site, and a parameter stands for the call's
    argument (`template inc(p) = p = ...` assigns the caller's `p`), so the template is expanded in the
    caller (@template_expand) like a {.dirty.} one; this also covers the locals of an enclosing proc."""
    if func_def.returns is not None:
        return False
    a = func_def.args
    params = {arg.arg for arg in a.posonlyargs + a.args + a.kwonlyargs}
    blocks = set(_n_block_params(func_def, _n_ast_annotations(func_def)))
    own = params | _n_declared_locals(func_def) | {t.name for t in func_def.type_params}
    for stmt in func_def.body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Name):
                continue
            if isinstance(node.ctx, ast.Store) and node.id in params - blocks:
                return True
            if node.id in own:
                continue
            if isinstance(node.ctx, ast.Store):
                return True
            if node.id not in module_globals and not hasattr(builtins, node.id):
                return True
    return False


def _n_ast_annotations(func_def: ast.FunctionDef) -> dict:
    """The parameter annotations of a definition, as source text."""
    return {a.arg: ast.unparse(a.annotation) for a in func_def.args.args if a.annotation is not None}


def _n_template_entry(func_def: ast.FunctionDef, blocks=(), module_globals: dict | None = None) -> dict:
    """What expansion needs of a template: its parameters, their defaults (AST nodes, aligned to the last
    parameters), its body, its code blocks, and the globals of its module when it is expanded because it
    uses its caller's scope (checked again at expansion, when the module's later globals are defined)."""
    return {
        "params": [arg.arg for arg in func_def.args.args],
        "defaults": list(func_def.args.defaults),
        "body_nodes": func_def.body,
        "blocks": list(blocks),
        "globals": module_globals,
        "def": func_def,
    }


_n_template_defs: dict = {}  # code object -> the template's parsed FunctionDef (None without source)
_n_template_caller_scope: dict = {}  # code object -> whether the template uses its caller's variables


def _n_template_def(template_func):
    """The parsed definition of a template, cached by its code object: a template defined inside a proc is
    decorated on every call of the proc, and its source doesn't change. Expansion copies the nodes."""
    code = template_func.__code__
    if code not in _n_template_defs:
        try:
            _n_template_defs[code] = ast.parse(textwrap.dedent(inspect.getsource(template_func))).body[0]
        except (TypeError, OSError, IndexError):
            _n_template_defs[code] = None
    return _n_template_defs[code]


def template(template_func):
    _n_template_codes.add(template_func.__code__)  # astToStr(param) in its body names the call's argument
    func_def = _n_template_def(template_func)
    if isinstance(func_def, ast.FunctionDef):
        blocks = _n_block_params(func_def, template_func.__annotations__)
        if blocks:
            # rule: templates with code blocks run around the `with` body (Nim `t(args): block`)
            factory = dispatch(_n_make_block_template(template_func, func_def, blocks))
            # one using its caller's variables (or {.dirty.}) is expanded at `with t(args):` in
            # @template_expand callers, its block spliced in: Nim's {.inject.} locals are the caller's
            dirty = "dirty" in _n_routine_pragmas(template_func)
            if dirty or _n_uses_caller_scope(func_def, template_func.__globals__):
                _n_templates[template_func.__name__] = _n_template_entry(
                    func_def, blocks, None if dirty else template_func.__globals__)
            return factory
    is_untyped = (
        "return" in template_func.__annotations__
        and template_func.__annotations__["return"] == "untyped"
    )
    # Also check for Nim-style {.dirty.} templates (always untyped), also through a pragma alias
    if not is_untyped and "dirty" in _n_routine_pragmas(template_func):
        is_untyped = True
    # and for templates that use the caller's variables
    if not is_untyped and isinstance(func_def, ast.FunctionDef):
        code = template_func.__code__  # cached like the definition: decided on the first application
        if code not in _n_template_caller_scope:
            _n_template_caller_scope[code] = _n_uses_caller_scope(func_def, template_func.__globals__)
        is_untyped = _n_template_caller_scope[code]
    if is_untyped:
        # if the function is an untyped template
        if func_def is None:
            raise TypeError(f"Could not get source code for template function '{template_func.__name__}'.")
        template_def_node = func_def
        if not isinstance(template_def_node, ast.FunctionDef):
            raise TypeError("The template must be a standard Python function.")

        _n_templates[template_func.__name__] = _n_template_entry(template_def_node)
    return dispatch(template_func)


class _ParameterReplacer(ast.NodeTransformer):
    """
    An AST NodeTransformer that replaces parameter names (ast.Name nodes)
    with the actual argument nodes from a function call.
    """

    def __init__(self, arg_map):
        # arg_map is a dictionary mapping parameter names to argument AST nodes
        self.arg_map = arg_map

    def visit_Name(self, node):
        """
        Visits a Name node (e.g., a variable). If the variable name is one
        of our template's parameters, we replace this node with the
        corresponding argument node that was passed to the call.
        """
        if node.id in self.arg_map:
            # Return a deep copy of the argument node to avoid side-effects
            # if the same argument is used for multiple parameters.
            return copy.deepcopy(self.arg_map[node.id])
        return node

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Name) and node.func.id == "astToStr" and len(node.args) == 1
                and isinstance(node.args[0], ast.Name) and node.args[0].id in self.arg_map):
            # Nim's astToStr of a template parameter: the text of the call's argument (nsystem.astToStr)
            text = ast.unparse(self.arg_map[node.args[0].id])
            return ast.copy_location(ast.Call(func=ast.Name(id="string", ctx=ast.Load()),
                                              args=[ast.Constant(text)], keywords=[]), node)
        return self._visit_routine_param(node)

    def _visit_routine_param(self, node):
        """A parameter used as a routine in method-call position: with `fun(incl)`, `conf.notes.op(note)`
        is `incl(conf.notes, note)` (Nim method call syntax). Call position (`self(v, result)`) is a
        plain Name and handled by visit_Name."""
        self.generic_visit(node)
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(self.arg_map.get(func.attr), ast.Name):
            routine = ast.Name(id=self.arg_map[func.attr].id, ctx=ast.Load())
            return ast.copy_location(ast.Call(func=routine, args=[func.value, *node.args],
                                              keywords=node.keywords), node)
        return node


class _ReturnResult(ast.NodeTransformer):
    """`return` without a value in an expanded template body is `return result` (Nim: a proc's
    `return` returns `result`); nested functions keep their own returns."""

    def visit_Return(self, node):
        if node.value is None:
            return ast.copy_location(ast.Return(value=ast.Name(id="result", ctx=ast.Load())), node)
        return node

    def visit_FunctionDef(self, node):
        return node

    visit_AsyncFunctionDef = visit_Lambda = visit_FunctionDef


class _ParamStores(ast.NodeTransformer):
    """`p = x` in a template body whose parameter `p` is bound to a `mut @` parameter of the caller is
    `p <<= x`: Nim assigns through the `var` parameter, nimic writes that in place (rules §4)."""

    def __init__(self, names: set[str]):
        self.names = names

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in self.names:
            return ast.copy_location(ast.AugAssign(target=node.targets[0], op=ast.LShift(), value=node.value), node)
        return node

    def visit_FunctionDef(self, node):  # nested procs keep their own statements
        return node

    visit_AsyncFunctionDef = visit_Lambda = visit_FunctionDef


class _BlockSplicer(ast.NodeTransformer):
    """The bare statements `block` (and `return block`) of a template body replaced by the statements of
    the call's code blocks (Nim substitutes the block where the template uses it)."""

    def __init__(self, blocks: dict[str, list]):
        self.blocks = blocks

    def _maybe(self, node):
        if isinstance(node.value, ast.Name) and node.value.id in self.blocks:
            return [copy.deepcopy(stmt) for stmt in self.blocks[node.value.id]] or [ast.copy_location(ast.Pass(), node)]
        return node

    visit_Expr = visit_Return = _maybe

    def visit_FunctionDef(self, node):  # nested procs keep their own statements
        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def _n_split_blocks(body: list, n_blocks: int, name: str) -> list[list]:
    """The code blocks of `with t(args):` (the body) and of the `with do:` statements that end it, in order."""
    blocks = []
    while True:
        last = body[-1] if body else None
        is_do = (isinstance(last, ast.With) and len(last.items) == 1
                 and isinstance(last.items[0].context_expr, ast.Name) and last.items[0].context_expr.id == "do")
        if len(blocks) + 1 == n_blocks:
            if is_do:
                raise TemplateBlockError(f"template {name} takes {n_blocks} block(s); an extra `with do:` block "
                                         "was given")
            blocks.append(body)
            return blocks
        if not is_do:
            raise TemplateBlockError(f"template {name} takes {n_blocks} blocks, {len(blocks) + 1} given "
                                     "(add `with do:` blocks)")
        blocks.append(body[:-1])
        body = last.body


_N_MAX_EXPANSION_DEPTH = 64  # templates expanded inside expanded templates (Nim: a recursive template is an error)


class _TemplateInliner(ast.NodeTransformer):
    """
    An AST NodeTransformer that walks the syntax tree and replaces calls to a
    specific template function with the body of that function, after substituting
    its parameters with the call arguments. A block template's call `with t(args):` is
    replaced by its body with the code blocks spliced in. Expanded code is expanded
    again (templates calling templates).
    """

    def __init__(self, dict_with_templates, module_globals: dict | None = None, caller_has_result: bool = False,
                 mut_params: set[str] | frozenset = frozenset()):
        self.dict_with_templates = dict_with_templates
        self.module_globals = module_globals or {}
        # a bare `return` of an expanded template returns from the caller: with Nim's `result`
        self.caller_has_result = caller_has_result
        self.mut_params = mut_params  # the caller's `mut @` / `out @` parameters
        self._depth = 0

    def _entry(self, call_node, with_blocks: bool):
        """The registered template a call expands, or None."""
        if not isinstance(call_node, ast.Call) or not isinstance(call_node.func, ast.Name):
            return None
        entry = self.dict_with_templates.get(call_node.func.id)
        if entry is None or bool(entry.get("blocks")) != with_blocks:
            return None
        if entry.get("globals") is not None and not _n_uses_caller_scope(entry["def"], entry["globals"]):
            return None  # its open names are globals of its module defined after it: a call runs it
        return entry

    @staticmethod
    def _bind_arguments(entry, call_node) -> dict:
        """The call's argument for each (non-block) parameter: positional, keyword, else the default."""
        name = call_node.func.id
        blocks = entry.get("blocks", [])
        params = [p for p in entry["params"] if p not in blocks]
        defaults = entry.get("defaults", [])
        default_map = dict(zip(entry["params"][len(entry["params"]) - len(defaults):], defaults))
        if len(call_node.args) > len(params):
            raise TypeError(f"{name}() takes {len(params)} positional arguments but {len(call_node.args)} were given.")
        argument_map = dict(zip(params, call_node.args))
        for kw in call_node.keywords:
            if kw.arg not in params or kw.arg in argument_map:
                raise TypeError(f"{name}() got an unexpected or repeated argument {kw.arg!r}")
            argument_map[kw.arg] = kw.value
        for param in params:
            if param not in argument_map:
                if param not in default_map:
                    raise TypeError(f"{name}() missing argument {param!r}")
                argument_map[param] = copy.deepcopy(default_map[param])
        return argument_map

    def _expand_again(self, nodes: list, name: str) -> list:
        """Expand the templates that the expanded statements call."""
        self._depth += 1
        if self._depth > _N_MAX_EXPANSION_DEPTH:
            raise RecursionError(f"template {name} expands itself (Nim: recursive template)")
        result = []
        for node in nodes:
            visited = self.visit(node)
            if visited is None:
                continue
            result.extend(visited if isinstance(visited, list) else [visited])
        self._depth -= 1
        return result

    def _substituted_body(self, entry, argument_map: dict) -> list:
        """A copy of the template's body with its parameters replaced by the call's arguments."""
        stores = {param for param, arg in argument_map.items()
                  if isinstance(arg, ast.Name) and arg.id in self.mut_params}
        parameter_replacer = _ParameterReplacer(argument_map)
        body = []
        for body_node in entry["body_nodes"]:
            node = copy.deepcopy(body_node)
            if stores:
                node = _ParamStores(stores).visit(node)
            node = parameter_replacer.visit(node)
            if self.caller_has_result:
                node = _ReturnResult().visit(node)
            body.append(node)
        return body

    def _inline_call(self, call_node, targets=None):
        entry = self._entry(call_node, with_blocks=False)
        if entry is None:
            return None
        inlined_body = self._substituted_body(entry, self._bind_arguments(entry, call_node))
        if targets is not None and inlined_body:
            # Convert final Expr/Return to Assign using original targets
            last = inlined_body[-1]
            if isinstance(last, ast.Expr) or isinstance(last, ast.Return) and last.value is not None:
                inlined_body[-1] = ast.Assign(targets=targets, value=last.value)
        return self._expand_again(inlined_body, call_node.func.id)

    def visit_Expr(self, node):
        """
        Visit an expression statement. We are looking for expressions that are
        calls to our template function.
        """
        if not isinstance(node.value, ast.Call):
            return self.generic_visit(node)

        inlined = self._inline_call(node.value)
        return inlined if inlined is not None else self.generic_visit(node)

    def visit_Assign(self, node):
        """
        Visit an assignment statement. If the right-hand side is a call to a
        registered template, inline it and assign the result.
        """
        if not isinstance(node.value, ast.Call):
            return self.generic_visit(node)

        inlined = self._inline_call(node.value, node.targets)
        return inlined if inlined is not None else self.generic_visit(node)

    def visit_With(self, node):
        """`with t(args):` of a block template using its caller's variables: the template's body with the
        `with` body (and the `with do:` blocks) in place of its block parameters."""
        call = node.items[0].context_expr if len(node.items) == 1 and node.items[0].optional_vars is None else None
        entry = self._entry(call, with_blocks=True)
        if entry is None:
            return self.generic_visit(node)
        name = call.func.id
        body = self._substituted_body(entry, self._bind_arguments(entry, call))
        blocks = dict(zip(entry["blocks"], _n_split_blocks(node.body, len(entry["blocks"]), name)))
        body = [stmt for node_ in body for stmt in _n_as_list(_BlockSplicer(blocks).visit(node_))]
        return self._expand_again(body, name)

    def visit_FunctionDef(self, node):
        # Check if the function is an untyped template
        untyped_template = False
        for deco in node.decorator_list:
            if isinstance(deco, ast.Name) and deco.id == "template":
                returns = node.returns
                if (
                    returns
                    and isinstance(returns, ast.Name)
                    and returns.id == "untyped"
                ) or _n_uses_caller_scope(node, self.module_globals):
                    untyped_template = True
        if not untyped_template:
            return self.generic_visit(node)
        _n_templates[node.name] = _n_template_entry(node, _n_block_params(node, _n_ast_annotations(node)))


def _n_as_list(node) -> list:
    return [] if node is None else node if isinstance(node, list) else [node]


def _n_mut_params(func_def) -> frozenset:
    """The parameters of a definition annotated `mut @ T` / `out @ T` (Nim `var T` / `out T`)."""
    if not isinstance(func_def, ast.FunctionDef):
        return frozenset()
    a = func_def.args
    return frozenset(arg.arg for arg in a.posonlyargs + a.args + a.kwonlyargs
                     if isinstance(arg.annotation, ast.BinOp) and isinstance(arg.annotation.op, ast.MatMult)
                     and isinstance(arg.annotation.left, ast.Name) and arg.annotation.left.id in ("mut", "out"))


def template_expand(target_func):
    """
    A decorator that replaces calls to `template_func` within a decorated
    function with the actual source code of `template_func`.
    The actual decorator that transforms the target function."""

    try:
        target_source = inspect.getsource(target_func)
        target_source = textwrap.dedent(target_source)
        target_ast = ast.parse(target_source)
    except (TypeError, OSError) as e:
        raise TypeError(
            f"Could not get source code for target function '{target_func.__name__}'."
        ) from e

    # Remove the @template_expand decorator from the generated source code.
    func_def_node = target_ast.body[0]
    if isinstance(func_def_node, ast.FunctionDef):
        func_def_node.decorator_list = []

    # Transform the target AST by inlining the template.
    has_result = isinstance(func_def_node, ast.FunctionDef) and any(
        isinstance(n, ast.Name) and n.id == "result" and isinstance(n.ctx, ast.Store) for n in ast.walk(func_def_node))
    inliner = _TemplateInliner(_n_templates, target_func.__globals__, has_result, _n_mut_params(func_def_node))
    transformed_ast = inliner.visit(target_ast)

    ast.fix_missing_locations(transformed_ast)

    try:
        new_source_code = ast.unparse(transformed_ast)
    except AttributeError:
        raise RuntimeError(
            "This decorator requires Python 3.9+ for the `ast.unparse` function."
        )

    # print("--- Generated Transformed Code: ---")
    # print(textwrap.indent(new_source_code, '    '))
    # print("------------------------------------")

    exec_namespace = target_func.__globals__.copy()
    # the expanded source under a name of its own, so tracebacks and astToStr (call positions) can read it
    filename = f"<template_expand {target_func.__module__}.{target_func.__qualname__}>"
    linecache.cache[filename] = (len(new_source_code), None, new_source_code.splitlines(True), filename)
    code = compile(new_source_code, filename, "exec")
    # its bindings are checked (rule:valuecheck), as its module's are
    valuecheck.watch(code, new_source_code, filename, valuecheck.is_nimic_file(inspect.getsourcefile(target_func) or ""))
    exec(code, exec_namespace)

    new_func = exec_namespace[target_func.__name__]
    if not new_func.__code__.co_freevars:
        # run in the module's own globals (not the copy), so it sees names defined after it
        new_func = types.FunctionType(new_func.__code__, target_func.__globals__, new_func.__name__,
                                      new_func.__defaults__)
        new_func.__kwdefaults__ = exec_namespace[target_func.__name__].__kwdefaults__
    new_func = wraps(target_func)(new_func)
    new_func._n_source = new_source_code  # its source: inspect.getsource would give the unexpanded original
    return new_func


if __name__ == "__main__":
    # --- Example Usage ---
    class untyped:
        pass

    @template
    def log_operation2(level, message) -> untyped:
        """A simple template for logging."""
        prefix = f"[{level.upper()}]"
        print(f"{prefix} {message}")
        print(f"{prefix} Operation complete.")

    # 2. Apply the decorator to a target function.
    @template_expand
    def process_data(user_id, data_payload):
        """
        This is the main function where work happens.
        We want to replace calls to 'log_operation' with its code.
        """

        # 1. Define a "template" function. This is the function we want to inline.
        @template
        def log_operation(level, message) -> untyped:
            """A simple template for logging."""
            prefix = f"[{level.upper()}]"
            print(f"{prefix} {message}")
            print(f"{prefix} Operation complete.")

        print(f"Starting process for user: {user_id}")

        # This call will be replaced by the body of log_operation
        log_operation("INFO", f"Processing payload of size {len(data_payload)}")

        # Some more work...
        processed_data = data_payload.upper()

        # This call will also be replaced
        log_operation2("DEBUG", f"Finished processing for {user_id}")

        print("Main process finished.")
        return processed_data

    print(">>> Calling the decorated function 'process_data'...")
    result = process_data("user-123", "some important data")
    print("\n>>> Function call finished.")
    print(f"Result: {result}")

    print("\n" + "=" * 50 + "\n")

    print(">>> Verifying the function's metadata:")
    print(f"Function name: {process_data.__name__}")
    print(f"Function docstring: {process_data.__doc__.strip()}")
