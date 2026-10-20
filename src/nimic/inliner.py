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
                        body (parameter names substituted with call args).

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
import inspect
import textwrap
import types
import warnings
from functools import wraps

from nimic.ntypesystem import dispatch, _n_routine_pragmas, _n_templates


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

    def __del__(self):
        if not self._entered:
            warnings.warn(f"block template {self._name} called without `with`: its block never ran",
                          RuntimeWarning, stacklevel=2)


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
    """Replace the bare statements `block` (and `return block`) by `yield <block index>`."""

    def __init__(self, blocks: list[str]):
        self.index = {name: i for i, name in enumerate(blocks)}

    def _maybe(self, node):
        if isinstance(node.value, ast.Name) and node.value.id in self.index:
            return ast.copy_location(ast.Expr(ast.Yield(ast.Constant(self.index[node.value.id]))), node)
        return node

    visit_Expr = _maybe
    visit_Return = _maybe

    def visit_FunctionDef(self, node):  # nested procs keep their own statements
        return node


def _n_make_block_template(template_func, func_def: ast.FunctionDef, blocks: list[str]):
    """The generator of a block template and the factory (signature without the block parameters)
    that dispatch registers; the factory returns the context manager for `with`."""
    gen_def = copy.deepcopy(func_def)
    gen_def.decorator_list = []
    gen_def.returns = None
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
    factory_ns = {"_call": _BlockTemplateCall, "_gen": gen_fn, "_n": n_blocks}
    exec(f"def {name}({', '.join(param_names)}):\n    return _call(_gen, {arg_tuple}, _n, {name!r})\n", factory_ns)
    factory = factory_ns[name]
    factory.__defaults__ = defaults
    factory.__annotations__ = {k: template_func.__annotations__.get(k, "untyped") for k in param_names}
    factory.__module__ = template_func.__module__
    factory.__qualname__ = template_func.__qualname__
    factory.__doc__ = template_func.__doc__
    factory._n_globals = template_func.__globals__  # dispatch resolves annotations in the template's module
    factory._n_block_params = tuple(blocks)
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
    """A statement template (no return type) whose body assigns a name that is not its own, or reads a
    name that is neither a parameter, its own local, a global of its module nor a builtin. Nim binds
    such open symbols at the call site, so the template is expanded in the caller (@template_expand)
    like a {.dirty.} one; this also covers the locals of an enclosing proc."""
    if func_def.returns is not None:
        return False
    a = func_def.args
    own = {arg.arg for arg in a.posonlyargs + a.args + a.kwonlyargs} | _n_declared_locals(func_def)
    for stmt in func_def.body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Name) or node.id in own:
                continue
            if isinstance(node.ctx, ast.Store):
                return True
            if node.id not in module_globals and not hasattr(builtins, node.id):
                return True
    return False


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
    func_def = _n_template_def(template_func)
    if isinstance(func_def, ast.FunctionDef):
        blocks = _n_block_params(func_def, template_func.__annotations__)
        if blocks:
            # rule: templates with code blocks run around the `with` body (Nim `t(args): block`)
            return dispatch(_n_make_block_template(template_func, func_def, blocks))
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

        template_body_nodes = template_def_node.body
        template_params = [arg.arg for arg in template_def_node.args.args]

        _n_templates[template_func.__name__] = {
            "params": template_params,
            "body_nodes": template_body_nodes,
        }
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


class _TemplateInliner(ast.NodeTransformer):
    """
    An AST NodeTransformer that walks the syntax tree and replaces calls to a
    specific template function with the body of that function, after substituting
    its parameters with the call arguments.
    """

    def __init__(self, dict_with_templates, module_globals: dict | None = None, caller_has_result: bool = False):
        self.dict_with_templates = dict_with_templates
        self.module_globals = module_globals or {}
        # a bare `return` of an expanded template returns from the caller: with Nim's `result`
        self.caller_has_result = caller_has_result

    def _inline_call(self, call_node, targets=None):
        if (
            not isinstance(call_node.func, ast.Name)
            or call_node.func.id not in self.dict_with_templates
        ):
            return None

        template_name = call_node.func.id
        template_params = self.dict_with_templates[template_name]["params"]
        template_body_nodes = self.dict_with_templates[template_name]["body_nodes"]

        call_args = call_node.args
        if len(call_args) != len(template_params):
            raise TypeError(
                f"{template_name}() takes {len(template_params)} positional arguments "
                f"but {len(call_args)} were given."
            )

        argument_map = dict(zip(template_params, call_args))
        inlined_body = []
        parameter_replacer = _ParameterReplacer(argument_map)
        original_body_nodes = [copy.deepcopy(n) for n in template_body_nodes]

        for i, body_node in enumerate(original_body_nodes):
            transformed_node = parameter_replacer.visit(body_node)
            if self.caller_has_result:
                transformed_node = _ReturnResult().visit(transformed_node)
            if targets is not None and i == len(original_body_nodes) - 1:
                # Convert final Expr/Return to Assign using original targets
                if isinstance(transformed_node, ast.Expr):
                    transformed_node = ast.Assign(targets=targets, value=transformed_node.value)
                elif isinstance(transformed_node, ast.Return) and transformed_node.value is not None:
                    transformed_node = ast.Assign(targets=targets, value=transformed_node.value)
            inlined_body.append(transformed_node)

        return inlined_body

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
        _n_templates[node.name] = {
            "params": [arg.arg for arg in node.args.args],
            "body_nodes": node.body,
        }


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
    inliner = _TemplateInliner(_n_templates, target_func.__globals__, has_result)
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
    exec(new_source_code, exec_namespace)

    new_func = exec_namespace[target_func.__name__]
    if not new_func.__code__.co_freevars:
        # run in the module's own globals (not the copy), so it sees names defined after it
        new_func = types.FunctionType(new_func.__code__, target_func.__globals__, new_func.__name__,
                                      new_func.__defaults__)
        new_func.__kwdefaults__ = exec_namespace[target_func.__name__].__kwdefaults__
    return wraps(target_func)(new_func)


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
