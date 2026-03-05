"""
nimic inliner module
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Compile-time template inlining via AST rewriting.

Provides two decorators:
  @template           — registers a function as an inlinable template.
                        Functions returning `untyped` are stored as AST
                        fragments keyed by name in _n_templates.
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
import copy
import inspect
import textwrap
from functools import wraps

_n_templates = {}


def template(template_func):
    if (
        "return" in template_func.__annotations__
        and template_func.__annotations__["return"] == "untyped"
    ):
        # if the function is an untyped template
        try:
            template_source = inspect.getsource(template_func)
            template_source = textwrap.dedent(template_source)
            template_ast = ast.parse(template_source)
        except (TypeError, OSError) as e:
            raise TypeError(
                f"Could not get source code for template function '{template_func.__name__}'."
            ) from e

        template_def_node = template_ast.body[0]
        if not isinstance(template_def_node, ast.FunctionDef):
            raise TypeError("The template must be a standard Python function.")

        template_body_nodes = template_def_node.body
        template_params = [arg.arg for arg in template_def_node.args.args]

        _n_templates[template_func.__name__] = {
            "params": template_params,
            "body_nodes": template_body_nodes,
        }
    return template_func


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


class _TemplateInliner(ast.NodeTransformer):
    """
    An AST NodeTransformer that walks the syntax tree and replaces calls to a
    specific template function with the body of that function, after substituting
    its parameters with the call arguments.
    """

    def __init__(self, dict_with_templates):
        self.dict_with_templates = dict_with_templates

    def visit_Expr(self, node):
        """
        Visit an expression statement. We are looking for expressions that are
        calls to our template function.
        """
        if not isinstance(node.value, ast.Call):
            return self.generic_visit(node)

        call_node = node.value
        if (
            not isinstance(call_node.func, ast.Name)
            or call_node.func.id not in self.dict_with_templates
        ):
            return self.generic_visit(node)

        template_name = call_node.func.id
        template_params = self.dict_with_templates[template_name]["params"]
        template_body_nodes = self.dict_with_templates[template_name]["body_nodes"]
        # print(f"--- Found call to '{template_name}'. Inlining code. ---")

        # 1. Map the template's parameter names to the argument nodes from the call.
        call_args = call_node.args
        if len(call_args) != len(template_params):
            raise TypeError(
                f"{template_name}() takes {len(template_params)} positional arguments "
                f"but {len(call_args)} were given."
            )

        argument_map = dict(zip(template_params, call_args))

        # 2. For each node in the template's body, substitute the parameters.
        inlined_body = []
        parameter_replacer = _ParameterReplacer(argument_map)

        # We must deep-copy the body nodes before transforming them.
        original_body_nodes = [copy.deepcopy(n) for n in template_body_nodes]

        for body_node in original_body_nodes:
            # The replacer walks through each node in the template's body
            # and replaces parameter names with the actual arguments.
            transformed_node = parameter_replacer.visit(body_node)
            inlined_body.append(transformed_node)

        return inlined_body

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
                ):
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
    inliner = _TemplateInliner(_n_templates)
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
