"""
nimic transpiler
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Transpiles a subset of Python (nimic DSL) into Nim source code.
This module is a modified copy of CPython's ``ast.py``, where the
``_Unparser`` visitor has been extended to emit Nim syntax instead of
Python syntax.  The transformation is driven by the rules listed below.

Transformation Rules
--------------------

Formatting:
  rule:doublespace -> change four spaces to double spaces for indentation
  rule:quote -> replace quotes to double quotes
  rule:slice -> slice [a:], [a:b] -> [a..^1], [a..<b]
  rule:discard -> assign to "_" is replaced by "discard"
  rule:pass -> replace "pass" by "discard"
  rule:nonlocal -> suppress "nonlocal" declarations (Nim closures capture by reference)

Scope qualifiers:
  rule:dropwith -> drop "with" for "const", "let", "var", "export", "block"
  rule:writeexport -> write no parentheses for "export" by assigning low priority
  feature:subscriptrename -> subscript can be renamed if in keywords_no_with context ("const", "let", "var", "export")

Type system:
  rule:classdef -> interpret class definition as type (object or tuple, depending on base class)
  rule:classdefseq -> combine consecutive class definitions into one type def.
    Move method definitions outside type definitions
  rule:typealias -> type alias (also register as alias for dispatch): class Time(float64) -> type Time* = float64
    and the assignment form: a module-level `Snippet = string` (value is a type) -> type Snippet* = string
  rule:typedistinct -> distinct type (decorated with "distinct"): class Time(float64) -> type Time* = distinct float64
  rule:annotateself -> if self is not annotated, it will be derived from the class name (as immutable)
  rule:instantiation -> call with capitalized name and named arguments is interpreted as instantiation ("=" -> ":").
    Classes instantiated with keywords should be named starting with a capital letter (preceeding by _ or local_)
  rule:enum -> "NIntEnum", "NStrEnum" rename to "Enum", drop "auto"
  rule:trange -> Trange[a, b] transpiles as range[a .. b] (Nim range subtype)
  rule:tuplelit -> NTuple subclass constructor calls transpile as Nim tuple literals (field: val, ...)
  rule:setlit -> Tset/set constructor calls transpile as Nim set literals {a, b, ...}
  rule:seqlit -> seq constructor calls transpile as Nim seq literals @[a, b, ...]

Function definitions:
  rule:funcdef -> adjust function definition according to Nim syntax as "proc" (or "func")
  rule:funcdefdecorated -> interpret decorators as definitions for "template", "iterator", "converter", "method".
    Other decorators are skipped (@dispatch, @ufcs, @importc: an importc proc's pragma docstring carries
    {.importc.}, and its `pass` body makes it body-less)
  rule:block -> function definition named "_block" is inserted as "block:" where called
  rule:templateinline -> "with template_inline" is replaced by template definition
  rule:funcdefyield -> definitions with yield or decorated with "iterator" are converted to iterators
  rule:funcdefmut -> arguments and return types denoted as "mut@" are mutable in function definition -> "var "
    (also in calltype signatures): def s(self: BProc) -> mut @ Builder -> proc s*(self: BProc): var Builder
  rule:funcdefout -> parameters annotated `out @ T` are Nim `out T` (in Python the same as mut @ T)
  rule:funcdefbody -> no body is written for function definition with "borrow" in pragma or only "pass"
  rule:funcdefinplace -> remove return ... from dunder defs for binary in-place operators __i...__, first argument is
    annotated as mutable if not done already
  rule:funcdefargswap -> arguments are swapped for binary operators "__radd__", "__rmul__", etc
  rule:funcdefrenamedunder -> rename binary operators __add__ -> "+", __sub__ -> "-", __getitem__ -> `[]`, etc
  rule:funcdefpackedtuple -> unpack tuples with "packed_tuple" in name
  rule:typedtemplate -> drop return from typed template or converter definition
  rule:pragma -> docstring with {.x.} is written as pragma {.x.}, if pragma contains "noSideEffect" func is defined
  rule:calltype -> def decorated with "calltype" emit as type alias: Name* = proc(...): T {.pragma.}

Control flow:
  rule:casereturn -> a proc body that ends with a match whose every branch is `return <value>` is a Nim
    case expression (the branch values without `return`)
  rule:matchcase -> adjust match case according to Nim syntax, also for variant types: in a class body,
    `field: T` followed by `match field:` is a record case `case field*: T` (discriminator default dropped),
    `case _` -> else, `A | B` -> of A, B; branch bodies are records, so cases nest
    In statements, `case _ if c in inrange(a, b) or c in S or c == v:` (c: the match subject, S a set) ->
    `of a .. b, S, v:`, and
    `case _ if cond:` with any other condition -> `elif cond:`
  rule:uncheckedassign -> with uncheckedAssign: block transpiles as {.cast(uncheckedAssign).}: block
  rule:pragmablock -> with pragma("p"): block transpiles as a pragma block {.p.}: block
  rule:inlineif -> write inline if according to Nim syntax
  rule:comptime -> the expression "if comptime(x)" is written as "when x" ("if" directly followed by "comptime"
    should be resolvable at comptime (is interpreted as "when")
  rule:main -> replace __name__ == "__main__" by isMainModule
  rule:comptimeexpr -> the expression `a if comptime(c) else b` is written as `when c: a else: b`
  rule:assigncall -> the statement assign(target, value) is written as `target = value`; used where Python
    can't assign, e.g. through a call returning var T: assign(p.s(cpsStmts), oldCode)
  rule:defined -> defined("identifier") transpiles as defined(identifier) without quotes; in Python it tests
    the build profile of the emulated Nim build (nsystem._BuildProfile), never "Python vs Nim"
  rule:declared -> declared("identifier") transpiles as declared(identifier) without quotes (dotted names allowed)
  rule:fortupleunpack -> tuple unpacking in for-loops emits parenthesized (a, b) syntax, except for Nim's
    multi-value magic iterators fields(a, b) / fieldPairs(x), which need bare `for a, b in`
  rule:templatereturn -> in templates, a "return expr" in tail position (end of every path: last statement, both
    arms of if/else, all arms of a match with case _) emits just the expression (template value); any other
    `return` stays, since in Nim it leaves the enclosing routine

Operators & renaming:
  rule:assign -> operator <<= is defined as value assignment to a mutable variable, i.e. a <<= b transpiles as a = b,
    for attributes and array elements not needed, can be just c.x = b or c[0] = b
  rule:bitwiserename -> bitwise operations get precedence adjusted and are renamed << -> shl, >> -> shr, & -> and,
    | -> or, ^ -> xor
  rule:lowercasebool -> True -> true, False -> false, "None" -> "nil"
  rule:nint -> the names nint and nbool (nimic's Nim int / mutable Nim bool) are Nim's int and bool
  rule:funcrename -> rename functions "print" to "echo", "str" to "$"
  rule:stringjoin -> replace "f" by "&"
  rule:literaltypes -> write as type suffix u64(0x9e3779b97f4a7c15) -> 0x9e3779b97f4a7c15'u64
  rule:char -> chars written as ch("#") transpile as char literals '#'; so does char("#") (a one-char
    string constant), the spelling where a local named `ch` shadows ch()
  rule:latin1literal -> str literals are byte views: chars 0x80-0xFF emit as \\xNN ("é" -> "\\xE9"),
    chars above 0xFF raise SyntaxError (use utf8()); applies to f-string literal parts too
  rule:utf8literal -> utf8("é") with a constant argument emits the raw Nim literal "é" (its UTF-8 bytes);
    a non-constant argument stays utf8(x) (identity template in pydefs.nim)
  rule:array -> add array type to the first array element
  rule:isnot -> write isnot according to Nim syntax
  rule:notin -> write notin according to Nim syntax
  rule:inrange -> inrange(a, b) transpiles as a .. b (Nim inclusive range literal)
  rule:strformat -> Python % transpiles as Nim % (strutils format) instead of mod when the left operand is a string
    (a literal, string(...) / FormatStr(...), a name declared as string or FormatStr in an enclosing scope, a call of
    a proc declared `-> string`) or the right one is a list / tuple or a name declared as a sequence of strings
  rule:nilident -> "is None" / "is not None" transpile as == nil / != nil
  rule:keywordescape -> trailing _ stripped from Python keyword clashes (None_ -> None, type_ -> type)
  rule:percentops -> plus_percent(a, b) / a.plus_percent(b) and minus_percent(a, b) / a.minus_percent(b) transpile as a +% b and a -% b; lt_percent, le_percent,
    gt_percent, ge_percent as a <% b, a <=% b, a >% b, a >=% b (comparison precedence)
  rule:dollarparens -> str(x) as the base of an index or attribute is parenthesized: ($(x))[i], ($(x)).f
  rule:exceptseveral -> `except (A, B):` transpiles as `except A, B:`
  rule:caseassign -> a match directly inside `with let:`/`with var:`/`with const:` whose every branch ends by
    assigning the same name (or with a raise / a call that doesn't return) is that name's case expression:
    `let x = case s of a: v ...`; the branches' assignments are written as their values
  rule:namedops -> Nim std operators that Python can't spell are named procs in nimic: std/hashes'
    mix_hash(h, v) is h !& v, finish_hash(h) is the prefix !$h; system's back(n) is ^n (s[back(1)] is s[^1])
  rule:isinstance -> isinstance(x, T) transpiles as x is T (type query), issubclass(T, X) as T is X
  rule:formatstr -> FormatStr(s) unwraps to string literal s in Nim (where string is FormatStr)
  rule:doblock -> with do: block translates as do: block in Nim
  rule:push -> with push("overflowChecks: off"): body  translates as {.push overflowChecks: off.} body {.pop.},
    the body at the level of the with statement (in Python, procs defined inside run with the check off)
  rule:tupletype -> tuple[T1, T2] slice translates as (T1, T2) tuple type in Nim
  rule:blockparam -> a typed/untyped (block) parameter's placeholder default `= None`, needed in Python after
    defaulted parameters, is not written: `kind: VarKind = Local, name = "", body: typed = None` is
    `kind: VarKind=Local, name="", body: typed`
  rule:varargs -> a parameter `*args: T` is `args: varargs[T]` (`*args: varargs[string, str]` is
    varargs[string, `$`]); a starred call argument f(a, *args) passes a varargs or seq on: f(a, args)

Imports:
  rule:import -> write import from as import, drop from __future__ import ...
  rule:nodoubleimport -> do not write import module if already imported
  rule:labeledblock -> with block("name"): ... is `block name:`; breakBlock("name") is `break name`
  rule:emit -> emit("C code") transpiles as an emit pragma {.emit: <triple-quoted C code>.} (raises if run in Python)
  rule:importexcept -> importExcept("..m", "a", "%") transpiles as `import ../m except a, `%``; in Python it
    binds the module's public names except those
  rule:importfrom -> importFrom("..m", "a", "%") transpiles as Nim's selective `from ../m import a, `%``; in
    Python it binds only those names (a Python `from m import a` is a full `import m`)
  rule:include -> include("x", "y") transpiles as `include x, y`; in Python the files run in the includer's
    namespace
  rule:modulepath -> nimic.x.y import paths transpile as x/y, with module renaming (e.g. syncio -> io)

Memory & variables:
  rule:dropbrackets -> remove brackets from what follows after "ptr" and "ref"
  rule:localname -> a private name _x transpiles to x (not exported); otherwise add "*" when definition,
    except for "result". Names starting with __ or _<digit> keep the old local_ prefix. Before transpiling,
    private_name_collisions() rejects modules where dropping the _ would change meaning (_x and x bound in
    one scope, or x used after a private value _x shadows it)
  rule:privatepragma -> a {.private.} docstring pragma keeps a proc (an operator, which can't take a _
    prefix) unexported; the pragma itself is not emitted
  rule:deref -> pointer dereference: ".contents" -> "[]"
  rule:copy -> value types are copied, drop .copy()
  rule:varini -> var initialization call without arguments with the same name as annotation is interpreted as
    declaration ("with var: a: Rng = Rng()" transpiles as "var a: Rng"), e.g. if the type is tuple. Also holds
    without annotation for registered classes or native types as array, openArray, etc. Ref types (registered
    with _n_is_ref or decorated @ref in the module) keep the constructor call, since `var x: T` would be nil.

The docstring for the original ``ast`` module is given below:

    ast
    ~~~

    The `ast` module helps Python applications to process trees of the Python
    abstract syntax grammar.  The abstract syntax itself might change with
    each Python release; this module helps to find out programmatically what
    the current grammar looks like and allows modifications of it.

    An abstract syntax tree can be generated by passing `ast.PyCF_ONLY_AST` as
    a flag to the `compile()` builtin function or by using the `parse()`
    function from this module.  The result will be a tree of objects whose
    classes all inherit from `ast.AST`.

    A modified abstract syntax tree can be compiled into a Python code object
    using the built-in `compile()` function.

    Additionally various helper functions are provided that make working with
    the trees simpler.  The main intention of the helper functions and this
    module in general is to provide an easy to use interface for libraries
    that work tightly with the python syntax (template engines for example).


    :copyright: Copyright 2008 by Armin Ronacher.
    :license: Python License.
"""
import argparse
import ast
import copy
import inspect
import keyword as pykeyword
import re
import sys
import warnings
from _ast import *
from collections import deque
from contextlib import contextmanager, nullcontext
from enum import IntEnum, _simple_enum, auto


def parse(source, filename='<unknown>', mode='exec', *,
          type_comments=False, feature_version=None):
    """
    Parse the source into an AST node.
    Equivalent to compile(source, filename, mode, PyCF_ONLY_AST).
    Pass type_comments=True to get back type comments where the syntax allows.
    """
    flags = PyCF_ONLY_AST
    if type_comments:
        flags |= PyCF_TYPE_COMMENTS
    if feature_version is None:
        feature_version = -1
    elif isinstance(feature_version, tuple):
        major, minor = feature_version  # Should be a 2-tuple.
        if major != 3:
            raise ValueError(f"Unsupported major version: {major}")
        feature_version = minor
    # Else it should be an int giving the minor version for 3.x.
    return compile(source, filename, mode, flags,
                   _feature_version=feature_version)


def literal_eval(node_or_string):
    """
    Evaluate an expression node or a string containing only a Python
    expression.  The string or node provided may only consist of the following
    Python literal structures: strings, bytes, numbers, tuples, lists, dicts,
    sets, booleans, and None.

    Caution: A complex expression can overflow the C stack and cause a crash.
    """
    if isinstance(node_or_string, str):
        node_or_string = parse(node_or_string.lstrip(" \t"), mode='eval')
    if isinstance(node_or_string, Expression):
        node_or_string = node_or_string.body
    def _raise_malformed_node(node):
        msg = "malformed node or string"
        if lno := getattr(node, 'lineno', None):
            msg += f' on line {lno}'
        raise ValueError(msg + f': {node!r}')
    def _convert_num(node):
        if not isinstance(node, Constant) or type(node.value) not in (int, float, complex):
            _raise_malformed_node(node)
        return node.value
    def _convert_signed_num(node):
        if isinstance(node, UnaryOp) and isinstance(node.op, (UAdd, USub)):
            operand = _convert_num(node.operand)
            if isinstance(node.op, UAdd):
                return + operand
            else:
                return - operand
        return _convert_num(node)
    def _convert(node):
        if isinstance(node, Constant):
            return node.value
        elif isinstance(node, Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, List):
            return list(map(_convert, node.elts))
        elif isinstance(node, Set):
            return set(map(_convert, node.elts))
        elif (isinstance(node, Call) and isinstance(node.func, Name) and
              node.func.id == 'set' and node.args == node.keywords == []):
            return set()
        elif isinstance(node, Dict):
            if len(node.keys) != len(node.values):
                _raise_malformed_node(node)
            return dict(zip(map(_convert, node.keys),
                            map(_convert, node.values)))
        elif isinstance(node, BinOp) and isinstance(node.op, (Add, Sub)):
            left = _convert_signed_num(node.left)
            right = _convert_num(node.right)
            if isinstance(left, (int, float)) and isinstance(right, complex):
                if isinstance(node.op, Add):
                    return left + right
                else:
                    return left - right
        return _convert_signed_num(node)
    return _convert(node_or_string)


def dump(node, annotate_fields=True, include_attributes=False, *, indent=None):
    """
    Return a formatted dump of the tree in node.  This is mainly useful for
    debugging purposes.  If annotate_fields is true (by default),
    the returned string will show the names and the values for fields.
    If annotate_fields is false, the result string will be more compact by
    omitting unambiguous field names.  Attributes such as line
    numbers and column offsets are not dumped by default.  If this is wanted,
    include_attributes can be set to true.  If indent is a non-negative
    integer or string, then the tree will be pretty-printed with that indent
    level. None (the default) selects the single line representation.
    """
    def _format(node, level=0):
        if indent is not None:
            level += 1
            prefix = '\n' + indent * level
            sep = ',\n' + indent * level
        else:
            prefix = ''
            sep = ', '
        if isinstance(node, AST):
            cls = type(node)
            args = []
            allsimple = True
            keywords = annotate_fields
            for name in node._fields:
                try:
                    value = getattr(node, name)
                except AttributeError:
                    keywords = True
                    continue
                if value is None and getattr(cls, name, ...) is None:
                    keywords = True
                    continue
                value, simple = _format(value, level)
                allsimple = allsimple and simple
                if keywords:
                    args.append('%s=%s' % (name, value))
                else:
                    args.append(value)
            if include_attributes and node._attributes:
                for name in node._attributes:
                    try:
                        value = getattr(node, name)
                    except AttributeError:
                        continue
                    if value is None and getattr(cls, name, ...) is None:
                        continue
                    value, simple = _format(value, level)
                    allsimple = allsimple and simple
                    args.append('%s=%s' % (name, value))
            if allsimple and len(args) <= 3:
                return '%s(%s)' % (node.__class__.__name__, ', '.join(args)), not args
            return '%s(%s%s)' % (node.__class__.__name__, prefix, sep.join(args)), False
        elif isinstance(node, list):
            if not node:
                return '[]', True
            return '[%s%s]' % (prefix, sep.join(_format(x, level)[0] for x in node)), False
        return repr(node), True

    if not isinstance(node, AST):
        raise TypeError('expected AST, got %r' % node.__class__.__name__)
    if indent is not None and not isinstance(indent, str):
        indent = ' ' * indent
    return _format(node)[0]


def copy_location(new_node, old_node):
    """
    Copy source location (`lineno`, `col_offset`, `end_lineno`, and `end_col_offset`
    attributes) from *old_node* to *new_node* if possible, and return *new_node*.
    """
    for attr in 'lineno', 'col_offset', 'end_lineno', 'end_col_offset':
        if attr in old_node._attributes and attr in new_node._attributes:
            value = getattr(old_node, attr, None)
            # end_lineno and end_col_offset are optional attributes, and they
            # should be copied whether the value is None or not.
            if value is not None or (
                hasattr(old_node, attr) and attr.startswith("end_")
            ):
                setattr(new_node, attr, value)
    return new_node


def fix_missing_locations(node):
    """
    When you compile a node tree with compile(), the compiler expects lineno and
    col_offset attributes for every node that supports them.  This is rather
    tedious to fill in for generated nodes, so this helper adds these attributes
    recursively where not already set, by setting them to the values of the
    parent node.  It works recursively starting at *node*.
    """
    def _fix(node, lineno, col_offset, end_lineno, end_col_offset):
        if 'lineno' in node._attributes:
            if not hasattr(node, 'lineno'):
                node.lineno = lineno
            else:
                lineno = node.lineno
        if 'end_lineno' in node._attributes:
            if getattr(node, 'end_lineno', None) is None:
                node.end_lineno = end_lineno
            else:
                end_lineno = node.end_lineno
        if 'col_offset' in node._attributes:
            if not hasattr(node, 'col_offset'):
                node.col_offset = col_offset
            else:
                col_offset = node.col_offset
        if 'end_col_offset' in node._attributes:
            if getattr(node, 'end_col_offset', None) is None:
                node.end_col_offset = end_col_offset
            else:
                end_col_offset = node.end_col_offset
        for child in iter_child_nodes(node):
            _fix(child, lineno, col_offset, end_lineno, end_col_offset)
    _fix(node, 1, 0, 1, 0)
    return node


def increment_lineno(node, n=1):
    """
    Increment the line number and end line number of each node in the tree
    starting at *node* by *n*. This is useful to "move code" to a different
    location in a file.
    """
    for child in walk(node):
        # TypeIgnore is a special case where lineno is not an attribute
        # but rather a field of the node itself.
        if isinstance(child, TypeIgnore):
            child.lineno = getattr(child, 'lineno', 0) + n
            continue

        if 'lineno' in child._attributes:
            child.lineno = getattr(child, 'lineno', 0) + n
        if (
            "end_lineno" in child._attributes
            and (end_lineno := getattr(child, "end_lineno", 0)) is not None
        ):
            child.end_lineno = end_lineno + n
    return node


def iter_fields(node):
    """
    Yield a tuple of ``(fieldname, value)`` for each field in ``node._fields``
    that is present on *node*.
    """
    for field in node._fields:
        try:
            yield field, getattr(node, field)
        except AttributeError:
            pass


def iter_child_nodes(node):
    """
    Yield all direct child nodes of *node*, that is, all fields that are nodes
    and all items of fields that are lists of nodes.
    """
    for name, field in iter_fields(node):
        if isinstance(field, AST):
            yield field
        elif isinstance(field, list):
            for item in field:
                if isinstance(item, AST):
                    yield item


def get_docstring(node, clean=True):
    """
    Return the docstring for the given node or None if no docstring can
    be found.  If the node provided does not have docstrings a TypeError
    will be raised.

    If *clean* is `True`, all tabs are expanded to spaces and any whitespace
    that can be uniformly removed from the second line onwards is removed.
    """
    if not isinstance(node, (AsyncFunctionDef, FunctionDef, ClassDef, Module)):
        raise TypeError("%r can't have docstrings" % node.__class__.__name__)
    if not(node.body and isinstance(node.body[0], Expr)):
        return None
    node = node.body[0].value
    if isinstance(node, Constant) and isinstance(node.value, str):
        text = node.value
    else:
        return None
    if clean:
        text = inspect.cleandoc(text)
    return text


_line_pattern = re.compile(r"(.*?(?:\r\n|\n|\r|$))")
def _splitlines_no_ff(source, maxlines=None):
    """Split a string into lines ignoring form feed and other chars.

    This mimics how the Python parser splits source code.
    """
    lines = []
    for lineno, match in enumerate(_line_pattern.finditer(source), 1):
        if maxlines is not None and lineno > maxlines:
            break
        lines.append(match[0])
    return lines


def _pad_whitespace(source):
    r"""Replace all chars except '\f\t' in a line with spaces."""
    result = ''
    for c in source:
        if c in '\f\t':
            result += c
        else:
            result += ' '
    return result


def get_source_segment(source, node, *, padded=False):
    """Get source code segment of the *source* that generated *node*.

    If some location information (`lineno`, `end_lineno`, `col_offset`,
    or `end_col_offset`) is missing, return None.

    If *padded* is `True`, the first line of a multi-line statement will
    be padded with spaces to match its original position.
    """
    try:
        if node.end_lineno is None or node.end_col_offset is None:
            return None
        lineno = node.lineno - 1
        end_lineno = node.end_lineno - 1
        col_offset = node.col_offset
        end_col_offset = node.end_col_offset
    except AttributeError:
        return None

    lines = _splitlines_no_ff(source, maxlines=end_lineno+1)
    if end_lineno == lineno:
        return lines[lineno].encode()[col_offset:end_col_offset].decode()

    if padded:
        padding = _pad_whitespace(lines[lineno].encode()[:col_offset].decode())
    else:
        padding = ''

    first = padding + lines[lineno].encode()[col_offset:].decode()
    last = lines[end_lineno].encode()[:end_col_offset].decode()
    lines = lines[lineno+1:end_lineno]

    lines.insert(0, first)
    lines.append(last)
    return ''.join(lines)


def walk(node):
    """
    Recursively yield all descendant nodes in the tree starting at *node*
    (including *node* itself), in no specified order.  This is useful if you
    only want to modify nodes in place and don't care about the context.
    """
    todo = deque([node])
    while todo:
        node = todo.popleft()
        todo.extend(iter_child_nodes(node))
        yield node


class NodeVisitor(object):
    """
    A node visitor base class that walks the abstract syntax tree and calls a
    visitor function for every node found.  This function may return a value
    which is forwarded by the `visit` method.

    This class is meant to be subclassed, with the subclass adding visitor
    methods.

    Per default the visitor functions for the nodes are ``'visit_'`` +
    class name of the node.  So a `TryFinally` node visit function would
    be `visit_TryFinally`.  This behavior can be changed by overriding
    the `visit` method.  If no visitor function exists for a node
    (return value `None`) the `generic_visit` visitor is used instead.

    Don't use the `NodeVisitor` if you want to apply changes to nodes during
    traversing.  For this a special visitor exists (`NodeTransformer`) that
    allows modifications.
    """

    def visit(self, node):
        """Visit a node."""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node."""
        for field, value in iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, AST):
                        self.visit(item)
            elif isinstance(value, AST):
                self.visit(value)

    def visit_Constant(self, node):
        value = node.value
        type_name = _const_node_type_names.get(type(value))
        if type_name is None:
            for cls, name in _const_node_type_names.items():
                if isinstance(value, cls):
                    type_name = name
                    break
        if type_name is not None:
            method = 'visit_' + type_name
            try:
                visitor = getattr(self, method)
            except AttributeError:
                pass
            else:
                warnings.warn(f"{method} is deprecated; add visit_Constant",
                              DeprecationWarning, 2)
                return visitor(node)
        return self.generic_visit(node)


class NodeTransformer(NodeVisitor):
    """
    A :class:`NodeVisitor` subclass that walks the abstract syntax tree and
    allows modification of nodes.

    The `NodeTransformer` will walk the AST and use the return value of the
    visitor methods to replace or remove the old node.  If the return value of
    the visitor method is ``None``, the node will be removed from its location,
    otherwise it is replaced with the return value.  The return value may be the
    original node in which case no replacement takes place.

    Here is an example transformer that rewrites all occurrences of name lookups
    (``foo``) to ``data['foo']``::

       class RewriteName(NodeTransformer):

           def visit_Name(self, node):
               return Subscript(
                   value=Name(id='data', ctx=Load()),
                   slice=Constant(value=node.id),
                   ctx=node.ctx
               )

    Keep in mind that if the node you're operating on has child nodes you must
    either transform the child nodes yourself or call the :meth:`generic_visit`
    method for the node first.

    For nodes that were part of a collection of statements (that applies to all
    statement nodes), the visitor may also return a list of nodes rather than
    just a single node.

    Usually you use the transformer like this::

       node = YourTransformer().visit(node)
    """

    def generic_visit(self, node):
        for field, old_value in iter_fields(node):
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                old_value[:] = new_values
            elif isinstance(old_value, AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node


_DEPRECATED_VALUE_ALIAS_MESSAGE = (
    "{name} is deprecated and will be removed in Python {remove}; use value instead"
)
_DEPRECATED_CLASS_MESSAGE = (
    "{name} is deprecated and will be removed in Python {remove}; "
    "use ast.Constant instead"
)


# If the ast module is loaded more than once, only add deprecated methods once
if not hasattr(Constant, 'n'):
    # The following code is for backward compatibility.
    # It will be removed in future.

    def _n_getter(self):
        """Deprecated. Use value instead."""
        warnings._deprecated(
            "Attribute n", message=_DEPRECATED_VALUE_ALIAS_MESSAGE, remove=(3, 14)
        )
        return self.value

    def _n_setter(self, value):
        warnings._deprecated(
            "Attribute n", message=_DEPRECATED_VALUE_ALIAS_MESSAGE, remove=(3, 14)
        )
        self.value = value

    def _s_getter(self):
        """Deprecated. Use value instead."""
        warnings._deprecated(
            "Attribute s", message=_DEPRECATED_VALUE_ALIAS_MESSAGE, remove=(3, 14)
        )
        return self.value

    def _s_setter(self, value):
        warnings._deprecated(
            "Attribute s", message=_DEPRECATED_VALUE_ALIAS_MESSAGE, remove=(3, 14)
        )
        self.value = value

    Constant.n = property(_n_getter, _n_setter)
    Constant.s = property(_s_getter, _s_setter)

class _ABC(type):

    def __init__(cls, *args):
        cls.__doc__ = """Deprecated AST node class. Use ast.Constant instead"""

    def __instancecheck__(cls, inst):
        if cls in _const_types:
            warnings._deprecated(
                f"ast.{cls.__qualname__}",
                message=_DEPRECATED_CLASS_MESSAGE,
                remove=(3, 14)
            )
        if not isinstance(inst, Constant):
            return False
        if cls in _const_types:
            try:
                value = inst.value
            except AttributeError:
                return False
            else:
                return (
                    isinstance(value, _const_types[cls]) and
                    not isinstance(value, _const_types_not.get(cls, ()))
                )
        return type.__instancecheck__(cls, inst)

def _new(cls, *args, **kwargs):
    for key in kwargs:
        if key not in cls._fields:
            # arbitrary keyword arguments are accepted
            continue
        pos = cls._fields.index(key)
        if pos < len(args):
            raise TypeError(f"{cls.__name__} got multiple values for argument {key!r}")
    if cls in _const_types:
        warnings._deprecated(
            f"ast.{cls.__qualname__}", message=_DEPRECATED_CLASS_MESSAGE, remove=(3, 14)
        )
        return Constant(*args, **kwargs)
    return Constant.__new__(cls, *args, **kwargs)

class Num(Constant, metaclass=_ABC):
    _fields = ('n',)
    __new__ = _new

class Str(Constant, metaclass=_ABC):
    _fields = ('s',)
    __new__ = _new

class Bytes(Constant, metaclass=_ABC):
    _fields = ('s',)
    __new__ = _new

class NameConstant(Constant, metaclass=_ABC):
    __new__ = _new

class Ellipsis(Constant, metaclass=_ABC):
    _fields = ()

    def __new__(cls, *args, **kwargs):
        if cls is _ast_Ellipsis:
            warnings._deprecated(
                "ast.Ellipsis", message=_DEPRECATED_CLASS_MESSAGE, remove=(3, 14)
            )
            return Constant(..., *args, **kwargs)
        return Constant.__new__(cls, *args, **kwargs)

# Keep another reference to Ellipsis in the global namespace
# so it can be referenced in Ellipsis.__new__
# (The original "Ellipsis" name is removed from the global namespace later on)
_ast_Ellipsis = Ellipsis

_const_types = {
    Num: (int, float, complex),
    Str: (str,),
    Bytes: (bytes,),
    NameConstant: (type(None), bool),
    Ellipsis: (type(...),),
}
_const_types_not = {
    Num: (bool,),
}

_const_node_type_names = {
    bool: 'NameConstant',  # should be before int
    type(None): 'NameConstant',
    int: 'Num',
    float: 'Num',
    complex: 'Num',
    str: 'Str',
    bytes: 'Bytes',
    type(...): 'Ellipsis',
}

class slice(AST):
    """Deprecated AST node class."""

class Index(slice):
    """Deprecated AST node class. Use the index value directly instead."""
    def __new__(cls, value, **kwargs):
        return value

class ExtSlice(slice):
    """Deprecated AST node class. Use ast.Tuple instead."""
    def __new__(cls, dims=(), **kwargs):
        return Tuple(list(dims), Load(), **kwargs)

# If the ast module is loaded more than once, only add deprecated methods once
if not hasattr(Tuple, 'dims'):
    # The following code is for backward compatibility.
    # It will be removed in future.

    def _dims_getter(self):
        """Deprecated. Use elts instead."""
        return self.elts

    def _dims_setter(self, value):
        self.elts = value

    Tuple.dims = property(_dims_getter, _dims_setter)

class Suite(mod):
    """Deprecated AST node class.  Unused in Python 3."""

class AugLoad(expr_context):
    """Deprecated AST node class.  Unused in Python 3."""

class AugStore(expr_context):
    """Deprecated AST node class.  Unused in Python 3."""

class Param(expr_context):
    """Deprecated AST node class.  Unused in Python 3."""


# Large float and imaginary literals get turned into infinities in the AST.
# We unparse those infinities to INFSTR.
_INFSTR = "1e" + repr(sys.float_info.max_10_exp + 1)

@_simple_enum(IntEnum)
class _Precedence:
    """Precedence table that originated from python grammar."""

    NAMED_EXPR = auto()      # <target> := <expr1>
    TUPLE = auto()           # <expr1>, <expr2>
    YIELD = auto()           # 'yield', 'yield from'
    TEST = auto()            # 'if'-'else', 'lambda'
    OR = auto()              # 'or'
    AND = auto()             # 'and'
    NOT = auto()             # 'not'
    CMP = auto()             # '<', '>', '==', '>=', '<=', '!=',
                             # 'in', 'not in', 'is', 'is not'
    EXPR = auto()
    BOR = EXPR               # '|'
    BXOR = auto()            # '^'
    BAND = auto()            # '&'
    SHIFT = auto()           # '<<', '>>'
    ARITH = auto()           # '+', '-'
    TERM = auto()            # '*', '@', '/', '%', '//'
    FACTOR = auto()          # unary '+', '-', '~'
    POWER = auto()           # '**'
    AWAIT = auto()           # 'await'
    ATOM = auto()

    def next(self):
        try:
            return self.__class__(self + 1)
        except ValueError:
            return self


_SINGLE_QUOTES = ('"',)  # rule:quote — Nim uses double quotes only
_MULTI_QUOTES = ('"""',)
_ALL_QUOTES = (*_SINGLE_QUOTES, *_MULTI_QUOTES)

class _Unparser(NodeVisitor):
    """Methods in this class recursively traverse an AST and
    output source code for the abstract syntax; original formatting
    is disregarded."""

    def __init__(self, *, type_registry: dict[str, ] | None = None, _avoid_backslashes=False):
        self._scope_depth = 0
        self._source = []
        self._precedences = {}
        self._type_ignores = {}
        self._indent = 0
        self._avoid_backslashes = _avoid_backslashes
        self._in_try_star = False
        self._aliases = {"Object": "object", "NTuple": "tuple"}
        self._tuple_types = set()
        self._string_names = [set()]  # rule:strformat: names declared as string / FormatStr, per scope
        self._string_seq_names = [set()]  # rule:strformat: names declared as seq/openArray/array/varargs of string
        self._ref_types = set()
        self._set_types = set()
        self._seq_types = set()
        self._native_type_subscript = ["array", "openArray", "seq"]
        self.renamed_keywords = {}
        self.module_names = []
        self._module_rename = {"ntypes": "ncode/pydefs", "nimpy": "ncode/nimpy"}
        self._module_std = ["math"]
        self._type_registry = type_registry
        if self._type_registry is not None:
            types_dict = getattr(self._type_registry, "types", self._type_registry)
            if isinstance(types_dict, dict):
                for name, tp in types_dict.items():
                    if isinstance(tp, type):
                        if tp.__name__ == "NTuple" or any(base.__name__ == "NTuple" for base in getattr(tp, "__mro__", [])):
                            self._tuple_types.add(name)
                        if getattr(tp, "_n_is_ref", False):
                            self._ref_types.add(name)
        self._no_bracket_subscript = ["ptr", "ref"]  # rule:dropbrackets
        self._keywords_no_with = ["const", "let", "var", "export"]  # rule:dropwith
        self._template_tail_returns = []  # rule:templatereturn, one set of Return ids per open template
        self._keywords_rename = {}
        self._keywords_no_with_colon = ["block"]  # rule:dropwith
        self._context_stack = []
        self._match_subjects = []  # rule:matchcase: subjects of the enclosing match statements
        self._case_assign_values = []  # rule:caseassign: ids of the assignments written as branch values
        self._block_nodes = []
        self._attribute_replace = {"copy": "", "contents": "[]"}
        self._set_low_precedence = ["export"]
        self._class_def_methods = []
        self._type_suffixes = ["i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64", "f32", "f64"] #, "u", "f", "d"]
        self._func_rename = {"print": "echo", "str": "$"}
        self._subscript_rename = {} # if var or let context
        self._const_rename = {"True": "true", "False": "false", "None": "nil"}  # rule:lowercasebool
        self._enums = ["NIntEnum", "NStrEnum"]
        self._def_decorators = ["template", "iterator", "converter", "method", "calltype"]
        self._declared_classes = set()

    def interleave(self, inter, f, seq):
        """Call f on each item in seq, calling inter() in between."""
        seq = iter(seq)
        try:
            f(next(seq))
        except StopIteration:
            pass
        else:
            for x in seq:
                inter()
                f(x)

    def items_view(self, traverser, items):
        """Traverse and separate the given *items* with a comma and append it to
        the buffer. If *items* is a single item sequence, a trailing comma
        will be added."""
        if len(items) == 1:
            traverser(items[0])
            self.write(",")
        else:
            self.interleave(lambda: self.write(", "), traverser, items)

    def maybe_newline(self):
        """Adds a newline if it isn't the start of generated source"""
        if self._source:
            self.write("\n")

    def fill(self, text=""):
        """Indent a piece of text and append it, according to the current
        indentation level"""
        self.maybe_newline()
        # rule:doublespace
        self.write("  " * self._indent + text)

    def write(self, *text):
        """Add new source parts"""
        self._source.extend(text)

    @contextmanager
    def buffered(self, buffer = None):
        if buffer is None:
            buffer = []

        original_source = self._source
        self._source = buffer
        yield buffer
        self._source = original_source

    @contextmanager
    def block(self, *, extra = None, start = ":"):
        """A context manager for preparing the source for blocks. It adds
        the character':', increases the indentation on enter and decreases
        the indentation on exit. If *extra* is given, it will be directly
        appended after the colon character.
        """
        self.write(start)  # rule:dropwith
        if extra:
            self.write(extra)
        self._indent += 1
        yield
        self._indent -= 1

    @contextmanager
    def delimit(self, start, end):
        """A context manager for preparing the source for expressions. It adds
        *start* to the buffer and enters, after exit it adds *end*."""

        self.write(start)
        yield
        self.write(end)

    def delimit_if(self, start, end, condition):
        if condition:
            return self.delimit(start, end)
        else:
            return nullcontext()

    def require_parens(self, precedence, node):
        """Shortcut to adding precedence related parens"""
        return self.delimit_if("(", ")", self.get_precedence(node) > precedence)

    def get_precedence(self, node):
        return self._precedences.get(node, _Precedence.TEST)

    def set_precedence(self, precedence, *nodes):
        for node in nodes:
            self._precedences[node] = precedence

    def get_raw_docstring(self, node):
        """If a docstring node is found in the body of the *node* parameter,
        return that docstring node, None otherwise.

        Logic mirrored from ``_PyAST_GetDocString``."""
        if not isinstance(
            node, (AsyncFunctionDef, FunctionDef, ClassDef, Module)
        ) or len(node.body) < 1:
            return None
        node = node.body[0]
        if not isinstance(node, Expr):
            return None
        node = node.value
        if isinstance(node, Constant) and isinstance(node.value, str):
            return node

    def get_type_comment(self, node):
        comment = self._type_ignores.get(node.lineno) or node.type_comment
        if comment is not None:
            return f" # type: {comment}"

    # rule:typealias (assignment form): type constructors and nimic builtin type names
    _type_constructors = {"seq", "array", "Tset", "ptr", "ref", "openArray", "Trange", "UncheckedArray",
                          "varargs", "tuple", "set"}
    _builtin_type_names = {"string", "cstring", "char", "bool", "byte", "nint", "int8", "int16", "int32", "int64",
                           "uint", "uint8", "uint16", "uint32", "uint64", "float16", "float32", "float64",
                           "pointer", "BiggestInt", "BiggestUInt", "BiggestFloat", "Hash"}

    def _is_type_expr(self, node) -> bool:
        if isinstance(node, Name):
            if node.id in self._declared_classes or node.id in self._builtin_type_names:
                return True
            types = getattr(self._type_registry, "types", None) if self._type_registry is not None else None
            return isinstance(types, dict) and isinstance(types.get(node.id), type)
        if isinstance(node, Subscript) and isinstance(node.value, Name):
            return node.value.id in self._type_constructors or node.value.id in self._declared_classes
        if isinstance(node, Call) and isinstance(node.func, Name) and node.func.id == "typeof":
            return True  # `T = typeof(expr)`
        return False

    def _is_type_alias(self, item) -> bool:
        """rule:typealias: a module-level `Name = T` whose value is a type is a type alias."""
        return (isinstance(item, Assign) and len(item.targets) == 1 and isinstance(item.targets[0], Name)
                and self._scope_depth == 0 and not self._context_stack and self._is_type_expr(item.value))

    def _is_type_def(self, item):
        if isinstance(item, ClassDef) or self._is_type_alias(item):
            return True
        if isinstance(item, (FunctionDef, AsyncFunctionDef)):
            for d in item.decorator_list:
                if (isinstance(d, Name) and d.id == "calltype") or (isinstance(d, Call) and isinstance(d.func, Name) and d.func.id == "calltype"):
                    return True
        return False

    def traverse(self, node):
        # rule:classdefseq
        _prev_type_def = False
        if isinstance(node, list):
            for item in node:
                type_def = self._is_type_def(item)
                if type_def and not _prev_type_def:
                    # start type def
                    self.fill("type")
                    self._indent += 1
                if not type_def and _prev_type_def:
                    # end type def
                    self._indent -= 1
                    if len(self._class_def_methods) > 0:
                        self.traverse(self._class_def_methods)
                        # assume for now no nested class defs
                        self._class_def_methods = []
                self.traverse(item)
                _prev_type_def = type_def
            if len(node) > 0 and _prev_type_def: # if the last item was a type def
                # end type def
                self._indent -= 1
                if len(self._class_def_methods) > 0:
                    self.traverse(self._class_def_methods)
                    # assume for now no nested class defs
                    self._class_def_methods = []
        else:
            super().visit(node)

    # Note: as visit() resets the output text, do NOT rely on
    # NodeVisitor.generic_visit to handle any nodes (as it calls back in to
    # the subclass visit() method, which resets self._source to an empty list)
    def visit(self, node):
        """Outputs a source code string that, if converted back to an ast
        (using ast.parse) will generate an AST equivalent to *node*"""
        self._source = []
        self.traverse(node)
        return "".join(self._source)

    def _write_docstring_and_traverse_body(self, node):
        if (docstring := self.get_raw_docstring(node)):
            self._write_docstring(docstring)
            self.traverse(node.body[1:])
        else:
            self.traverse(node.body)

    def visit_Module(self, node):
        self._type_ignores = {
            ignore.lineno: f"ignore{ignore.tag}"
            for ignore in node.type_ignores
        }
        self._write_docstring_and_traverse_body(node)
        self._type_ignores.clear()

    def visit_FunctionType(self, node):
        with self.delimit("(", ")"):
            self.interleave(
                lambda: self.write(", "), self.traverse, node.argtypes
            )

        self.write(" -> ")
        self.traverse(node.returns)

    def visit_Expr(self, node):
        value = node.value
        if (isinstance(value, Call) and isinstance(value.func, Name) and value.func.id == "breakBlock"
                and len(value.args) == 1 and isinstance(value.args[0], Constant)):
            # rule:labeledblock -> breakBlock("name") is `break name`
            self.fill(f"break {value.args[0].value}")
            return
        if (isinstance(value, Call) and isinstance(value.func, Name) and value.func.id == "emit" and len(value.args) == 1
                and isinstance(value.args[0], Constant) and isinstance(value.args[0].value, str)):
            # rule:emit -> emit("code") is {.emit: """code""".}
            self.fill('{.emit: """' + value.args[0].value + '""".}')
            return
        if (isinstance(value, Call) and isinstance(value.func, Name) and value.func.id == "include" and value.args
                and all(isinstance(a, Constant) and isinstance(a.value, str) for a in value.args)):
            # rule:include -> include("x", "y") is `include x, y` (textual inclusion)
            names = [a.value for a in value.args]
            self.fill("include " + ", ".join(names))
            self.module_names += [n.split("/")[-1] for n in names]
            return
        if (isinstance(value, Call) and isinstance(value.func, Name) and value.func.id in ("importExcept", "importFrom")
                and value.args and all(isinstance(a, Constant) and isinstance(a.value, str) for a in value.args)):
            # rule:importexcept -> importExcept("..m", "a", "%") is `import ../m except a, `%``
            # rule:importfrom -> importFrom("..m", "a", "%") is `from ../m import a, `%``
            module = value.args[0].value
            level = len(module) - len(module.lstrip("."))
            names = ", ".join(n if n.isidentifier() else f"`{n}`" for n in (a.value for a in value.args[1:]))
            path = self._import_path(module.lstrip("."), level)
            self.fill(f"import {path} except {names}" if value.func.id == "importExcept" else f"from {path} import {names}")
            return
        if (isinstance(value, Call) and isinstance(value.func, Name) and value.func.id == "assign"
                and len(value.args) == 2 and not value.keywords):
            # rule:assigncall -> assign(p.s(sec), x) is `p.s(sec) = x` (assignment through a var T result)
            self.fill()
            self.traverse(value.args[0])
            self.write(" = ")
            self.traverse(value.args[1])
            return
        self.fill()
        # rule:writeexport
        if self._context_stack and self._context_stack[-1] in self._set_low_precedence:
            self.set_precedence(_Precedence.NAMED_EXPR, node.value)
        else:
            self.set_precedence(_Precedence.YIELD, node.value)
        self.traverse(node.value)

    def visit_NamedExpr(self, node):
        with self.require_parens(_Precedence.NAMED_EXPR, node):
            self.set_precedence(_Precedence.ATOM, node.target, node.value)
            self.traverse(node.target)
            self.write(" := ")
            self.traverse(node.value)

    def visit_Import(self, node):
        # rule:nodoubleimport
        refined_list = [n for n in node.names if n.name not in self.module_names]
        if refined_list:
            self.fill("import ")
            self.interleave(lambda: self.write(", "), self.traverse, refined_list)
            self.module_names += [n.name for n in refined_list]

    def _import_path(self, module_name: str, level: int) -> str:
        """rule:import -> the Nim path of an imported module: nimic.x.y is x/y (with module renaming), a
        relative import keeps its directory: `from ..options import *` is `import ../options`."""
        module_name_split = module_name.split(".")
        if module_name in self._module_std:
            return "ncode/pystd/" + module_name
        if module_name_split[0] == "nimic":
            if module_name_split[1] in self._module_rename:
                module_name_split[1] = self._module_rename[module_name_split[1]]
            return "/".join(module_name_split[1:])
        self.module_names.append(module_name)
        return "../" * max(level - 1, 0) + module_name.replace(".", "/")

    def visit_ImportFrom(self, node):
        # rule:import -> `from m import ...` is `import m` (a class comes with its methods, which are procs
        # in Nim); Nim's selective `from m import a` is importFrom("m", "a") (rule:importfrom)
        if node.module and not node.module in ["__future__"]:
            self.fill("import " + self._import_path(node.module, node.level or 0))
        # self.write("import ")
        # self.interleave(lambda: self.write(", "), self.traverse, node.names)

    def _write_block_body(self):
        # rule:block
        self.write(" = block:")
        if self._block_nodes:
            func_node = self._block_nodes.pop()
            body = func_node.body
            with self.block(start=""):
                if isinstance(body, list) and isinstance(body[-1], Return):
                    if body[:-1]:
                        self.traverse(body[:-1])
                    if body[-1].value:
                        # do not print "return"
                        self.fill()
                        self.traverse(body[-1].value)

    def visit_Assign(self, node):
        if isinstance(node.value, Call) and isinstance(node.value.func, Name) and node.value.func.id == "string":
            # rule:strformat -> a name assigned string(...) is a string
            self._string_names[-1].update(t.id for t in node.targets if isinstance(t, Name))
        if self._case_assign_values and id(node) in self._case_assign_values[-1]:
            # rule:caseassign -> a branch's value
            self.fill()
            self.traverse(node.value)
            return
        if self._is_type_alias(node):
            # rule:typealias -> module-level `Snippet = string` is `type Snippet* = string`
            target = node.targets[0]
            if isinstance(node.value, Subscript) and isinstance(node.value.value, Name) and node.value.value.id == "Tset":
                self._set_types.add(target.id)  # rule:setlit applies to `MsgFlags()` / `MsgFlags({a})`
            target._is_definition = True
            self.fill()
            self.traverse(target)
            target._is_definition = False
            self.write(" = ")
            self.traverse(node.value)
            return
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], Attribute)
            and isinstance(node.targets[0].value, Name)
            and (
                node.targets[0].value.id in self._declared_classes
                or (self._type_registry and node.targets[0].value.id in self._type_registry.types)
                or node.targets[0].value.id in self._aliases
            )
        ):
            return
        self.fill()
        if len(node.targets) == 1 and isinstance(node.targets[0], Name) and getattr(node.targets[0], "id", "") == "_":
            # rule:discard
            self.write("discard ")
            self.traverse(node.value)
            return
        for target in node.targets:
            if isinstance(target, Name):
                is_module_level = (self._scope_depth == 0)
                in_declaration = any(x in self._context_stack for x in ("var", "let", "const"))
                if is_module_level and in_declaration:
                    target._is_definition = True
            # self.set_precedence(_Precedence.TUPLE, target)
            self.traverse(target)
            target._is_definition = False
        if (
            isinstance(node.value, Call)
            and isinstance(node.value.func, Name)
            and not node.value.args and not node.value.keywords
        ):
            if node.value.func.id == "_block":
                # rule:block
                self._write_block_body()
            elif (
                "var" in self._context_stack
                and self._type_registry is not None
                and node.value.func.id in self._type_registry.types
                and node.value.func.id not in self._ref_types  # rule:varini, a ref type must allocate: x = T()
            ):
                type_name = self._adjust_name(node.value.func.id, definition=False)
                self.write(": " + type_name) # needed for tuple declaration
            else:
                self.write(" = ")
                self.traverse(node.value)
        elif (
            isinstance(node.value, Call)
            and isinstance(node.value.func, Subscript)
            and not node.value.args and not node.value.keywords
        ):
            if "var" in self._context_stack and node.value.func.value.id in self._native_type_subscript:
                self.write(": ") # needed for array/openArray declaration
                self.traverse(node.value.func)
            else:
                self.write(" = ")
                self.traverse(node.value)
        elif (
            isinstance(node.value, Call)
            and isinstance(node.value.func, Subscript)
            and isinstance(node.value.func.value, Name)
            and node.value.func.value.id == "array"
            and len(node.value.args) == 1
            and isinstance(node.value.args[0], (List, Dict))
            # `name: array[N, T] = [...]` is a declaration: only for a variable being declared,
            # not for `x.s[0:4] = array[...](...)` or a plain reassignment (rule:array call form)
            and len(node.targets) == 1 and isinstance(node.targets[0], Name)
            and any(x in self._context_stack for x in ("var", "let", "const"))
        ):
            self.write(": ")
            self.traverse(node.value.func)
            self.write(" = ")
            if isinstance(node.value.args[0], List):
                self.traverse(node.value.args[0])
            else:
                with self.delimit("[", "]"):
                    def write_dict_item(item):
                        k, v = item
                        self.traverse(k)
                        self.write(": ")
                        self.traverse(v)
                    self.interleave(
                        lambda: self.write(", "), write_dict_item, zip(node.value.args[0].keys, node.value.args[0].values)
                    )
        else:
            self.write(" = ")
            self.traverse(node.value)
        if type_comment := self.get_type_comment(node):
            self.write(type_comment)

    def visit_AugAssign(self, node):
        self.fill()
        self.traverse(node.target)
        self.write(" " + self.ibinop[node.op.__class__.__name__] + "= ")  # rule:assign
        self.traverse(node.value)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, Name) and self._is_string_annotation(node.annotation):
            self._string_names[-1].add(node.target.id)  # rule:strformat
        if isinstance(node.target, Name) and self._is_string_seq_annotation(node.annotation):
            self._string_seq_names[-1].add(node.target.id)  # rule:strformat
        self.fill()
        set_annotation = isinstance(node.annotation, Set)
        if node.simple and isinstance(node.target, Name) and not set_annotation:
            target_name = node.target.id
            if (not self._context_stack or self._context_stack[-1] != "tuple") and target_name != "result":
                is_module_level = (self._scope_depth == 0)
                in_declaration = True
                # class def or any(x in self._context_stack for x in ("var", "let", "const"))
                # rule:localname
                node.target.id = self._adjust_name(target_name, definition=(is_module_level and in_declaration))
        with self.delimit_if("(", ")", not node.simple and isinstance(node.target, Name)):
            self.traverse(node.target)
        self.write(": ")
        self.traverse(node.annotation)
        var_declaration = False # rule:varini
        if "var" in self._context_stack:
            # check this is a default class init that should be declared
            # if value is a empty call with the same name as annotation then this is a declaration
            if isinstance(node.value, Call) and len(node.value.args) == 0:
                var_declaration = isinstance(node.value.func, Name) and node.value.func.id == node.annotation.id
        if (
            isinstance(node.value, Call)
            and isinstance(node.value.func, Name)
            and not node.value.args and not node.value.keywords
            and node.value.func.id == "_block"
        ):
            # rule:block
            self._write_block_body()
        elif node.value and not var_declaration:
            self.write(" = ")
            self.traverse(node.value)

    def visit_Return(self, node):
        # rule:templatereturn -> a `return x` in tail position of a template is its value: emit just x
        if self._template_tail_returns and id(node) in self._template_tail_returns[-1]:
            self.fill()
            self.traverse(node.value)
            return
        self.fill("return")
        if node.value:
            self.write(" ")
            self.traverse(node.value)

    def visit_Pass(self, node):
        # rule:pass
        self.fill("discard")

    def visit_Break(self, node):
        self.fill("break")

    def visit_Continue(self, node):
        self.fill("continue")

    def visit_Delete(self, node):
        self.fill("del ")
        self.interleave(lambda: self.write(", "), self.traverse, node.targets)

    def visit_Assert(self, node):
        self.fill("assert ")
        self.traverse(node.test)
        if node.msg:
            self.write(", ")
            self.traverse(node.msg)

    def visit_Global(self, node):
        self.fill("global ")
        self.interleave(lambda: self.write(", "), self.write, node.names)

    def visit_Nonlocal(self, node):
        # rule:nonlocal -> Nim closures capture by reference; suppress nonlocal
        pass

    def visit_Await(self, node):
        with self.require_parens(_Precedence.AWAIT, node):
            self.write("await")
            if node.value:
                self.write(" ")
                self.set_precedence(_Precedence.ATOM, node.value)
                self.traverse(node.value)

    def visit_Yield(self, node):
        with self.require_parens(_Precedence.YIELD, node):
            self.write("yield")
            if node.value:
                self.write(" ")
                self.set_precedence(_Precedence.ATOM, node.value)
                self.traverse(node.value)

    def visit_YieldFrom(self, node):
        with self.require_parens(_Precedence.YIELD, node):
            self.write("yield from ")
            if not node.value:
                raise ValueError("Node can't be used without a value attribute.")
            self.set_precedence(_Precedence.ATOM, node.value)
            self.traverse(node.value)

    def visit_Raise(self, node):
        self.fill("raise")
        if not node.exc:
            if node.cause:
                raise ValueError(f"Node can't use cause without an exception.")
            return
        self.write(" ")
        self.traverse(node.exc)
        if node.cause:
            self.write(" from ")
            self.traverse(node.cause)

    def do_visit_try(self, node):
        self.fill("try")
        with self.block():
            self.traverse(node.body)
        for ex in node.handlers:
            self.traverse(ex)
        if node.orelse:
            self.fill("else")
            with self.block():
                self.traverse(node.orelse)
        if node.finalbody:
            self.fill("finally")
            with self.block():
                self.traverse(node.finalbody)

    def visit_Try(self, node):
        prev_in_try_star = self._in_try_star
        self._scope_depth += 1  # try/except bodies are scopes in Nim
        try:
            self._in_try_star = False
            self.do_visit_try(node)
        finally:
            self._in_try_star = prev_in_try_star
            self._scope_depth -= 1

    def visit_TryStar(self, node):
        prev_in_try_star = self._in_try_star
        try:
            self._in_try_star = True
            self.do_visit_try(node)
        finally:
            self._in_try_star = prev_in_try_star

    def visit_ExceptHandler(self, node):
        self.fill("except*" if self._in_try_star else "except")
        if node.type:
            self.write(" ")
            if isinstance(node.type, Tuple):
                # rule:exceptseveral -> `except (A, B):` is Nim's `except A, B:`
                self.interleave(lambda: self.write(", "), self.traverse, node.type.elts)
            else:
                self.traverse(node.type)
        if node.name:
            self.write(" as ")
            self.write(node.name)
        with self.block():
            self.traverse(node.body)

    def _adjust_name(self, name, definition=True):
        # rule:localname
        # rule:keywordescape -> strip trailing _ from Python keyword clashes (None_ -> None)
        if len(name) > 1 and name.endswith("_") and pykeyword.iskeyword(name[:-1]):
            name = name[:-1]
        # rule:nint -> nint transpiles to Nim int (nimic does not shadow Python int), nbool to bool
        if not definition and name in ("nint", "nbool"):
            return "int" if name == "nint" else "bool"
        if len(name) > 1 and name[0] == "_":
            # private names keep their Nim name, unexported; __x / _1 are no Nim identifiers without a prefix
            _str = "local" + name if name[1] == "_" or name[1].isdigit() else name[1:]
        elif definition and not name[0].startswith("local_"):
            _str = name + "*"
        else:
            _str = name
        return _str

    def _unparse_names(self, node):
        """ast.unparse of a type expression, with rule:localname applied to its names (seq[_T] -> seq[T])."""
        node = copy.deepcopy(node)
        for n in walk(node):
            if isinstance(n, Name):
                n.id = self._adjust_name(n.id, definition=False)
        return ast.unparse(node)

    def visit_ClassDef(self, node):
        self._declared_classes.add(node.name)
        # rule:classdef
        if node.decorator_list:
            deco = node.decorator_list[0].id
            if deco == "ref":
                self._ref_types.add(node.name)  # rule:varini, module-local @ref classes
        else:
            deco = ""
        # for deco in node.decorator_list:
        #     self.fill("@")
        #     self.traverse(deco)
        # rule:pragma
        body, pragma = self._get_body_and_pragma(node)
        type_str = self._adjust_name(node.name) # rule:localname
        _pass = isinstance(body[0], Pass) if body else False
        no_attr = (_pass or all(isinstance(b, (FunctionDef, AsyncFunctionDef, Pass)) for b in body)) if body else False # no attributes, i.e. pass or only methods
        # deco in ["ref", "ptr", "distinct"]
        no_object = no_attr or deco
        enum = False  # rule:enum
        if not node.bases:
            raise ValueError(
                f"Class '{node.name}' has no base class. All Nimic class definitions must specify an explicit base (e.g. 'class {node.name}(Object):')."
            )
        if isinstance(node.bases[0], Subscript):
            base_val = getattr(node.bases[0].value, "id", "")
            if base_val == "Tset":
                base = "set[" + self._unparse_names(node.bases[0].slice) + "]"
                from_object = base
                no_object = True
                self._set_types.add(node.name)
                self._set_types.add(type_str)
            elif base_val == "seq":
                base = "seq[" + self._unparse_names(node.bases[0].slice) + "]"
                from_object = base
                no_object = True
                self._seq_types.add(node.name)
                self._seq_types.add(type_str)
            elif base_val == "Trange":
                slice_node = node.bases[0].slice
                if isinstance(slice_node, Tuple) and len(slice_node.elts) == 2:
                    low_str = self._unparse_names(slice_node.elts[0])
                    high_str = self._unparse_names(slice_node.elts[1])
                    base = f"range[{low_str} .. {high_str}]"
                else:
                    base = "range[" + self._unparse_names(slice_node) + "]"
                from_object = base
                no_object = True
            else:
                base = self._unparse_names(node.bases[0])
                from_object = base
                no_object = True
        elif hasattr(node.bases[0], "id"):
            base = self._adjust_name(node.bases[0].id, definition=False)  # rule:localname
        elif hasattr(node.bases[0], "attr"):
            base = node.bases[0].attr
        else:
            base = "Object"
        if base in self._aliases:
            from_object = self._aliases[base]
            if base == "NTuple":
                self._tuple_types.add(node.name)
                self._tuple_types.add(type_str)
        elif base in self._enums:
            from_object = "enum "
            enum = True
        elif no_object and not (base in ("Exception", "Defect", "CatchableError", "ValueError", "KeyError", "IOError", "OSError") or base.endswith(("Error", "Exception", "Defect"))):
            # rule:typealias or rule:typedistinct
            from_object = base
        else:
            from_object = "object of " + base
        self.fill(type_str)
        if hasattr(node, "type_params"):
            self._type_params_helper(node.type_params)
        if pragma:
            self.write(" {." + pragma + ".}")
        self.write(" =")
        if deco:
            self.write(" " + deco)
        self.write(" " + from_object)
        # with self.delimit_if("(", ")", condition = node.bases or node.keywords):
        #     comma = False
        #     for e in node.bases:
        #         if comma:
        #             self.write(", ")
        #         else:
        #             comma = True
        #         self.traverse(e)
        #     for e in node.keywords:
        #         if comma:
        #             self.write(", ")
        #         else:
        #             comma = True
        #         self.traverse(e)
        if not _pass:
            # rule:classdefseq, split body into attributes and methods
            body_rest = []
            if not isinstance(body, list):
                body = [body]
            for b in body:
                if isinstance(b, FunctionDef) or isinstance(b, AsyncFunctionDef):
                    # check if self is annotated
                    if b.args.args and b.args.args[0].arg == "self" and b.args.args[0].annotation is None:
                        # rule:annotateself
                        type_name = self._adjust_name(node.name, definition=False)
                        b.args.args[0].annotation = Name(id=type_name, ctx=Load())
                    self._class_def_methods.append(b)
                else:
                    if enum and isinstance(b, Assign) and isinstance(b.value, Call) and \
                        isinstance(b.value.func, Name) and b.value.func.id == "auto":
                        body_rest.append(b.targets[0])
                    else:
                        body_rest.append(b)
            if body_rest:
                with self.block(start=""):
                    if enum:
                        self.fill()
                        self.interleave(lambda: self.write(", "), self.traverse, body_rest)
                    else:
                        self._context_stack.append(from_object)
                        self._traverse_record_items(body_rest)
                        self._context_stack.pop()
        self.maybe_newline()

    def _traverse_record_items(self, items):
        """Object fields, where `field: T` followed by `match field:` is a Nim record case
        (`case field*: T` with `of` / `else` branches). Branch bodies are records too,
        so cases nest. The discriminator's default value is a nimic artifact and is dropped."""
        i = 0
        while i < len(items):
            b = items[i]
            # rule:matchcase, check for variant types
            if (
                i + 1 < len(items)
                and isinstance(b, AnnAssign)
                and isinstance(b.target, Name)
                and isinstance(items[i + 1], Match)
                and isinstance(items[i + 1].subject, Name)
                and items[i + 1].subject.id == b.target.id
            ):
                discriminator_name = self._adjust_name(b.target.id)  # rule:localname
                self.fill(f"case {discriminator_name}: ")
                self.traverse(b.annotation)
                with self.block(start=""):
                    for case in items[i + 1].cases:
                        self._write_record_branch(case)
                i += 2
            else:
                self.traverse(b)
                i += 1

    def _write_record_branch(self, case):
        # rule:matchcase: `case _` -> else, `A | B` -> of A, B (via visit_MatchOr)
        if isinstance(case.pattern, MatchAs) and case.pattern.name is None and case.pattern.pattern is None:
            self.fill("else")
        else:
            self.fill("of ")
            self.traverse(case.pattern)
        with self.block():
            self._traverse_record_items(case.body)

    @staticmethod
    def _is_string_annotation(ann) -> bool:
        """rule:strformat -> `string`, `FormatStr`, or `mut @ string` (a var parameter)."""
        if isinstance(ann, BinOp) and isinstance(ann.op, MatMult):
            ann = ann.right
        return isinstance(ann, Name) and ann.id in ("string", "FormatStr")

    @classmethod
    def _is_string_seq_annotation(cls, ann) -> bool:
        """rule:strformat -> `seq[string]`, `openArray[string]`, `array[N, string]`, `varargs[string]`."""
        if isinstance(ann, BinOp) and isinstance(ann.op, MatMult):
            ann = ann.right
        if not (isinstance(ann, Subscript) and isinstance(ann.value, Name)
                and ann.value.id in ("seq", "openArray", "array", "varargs")):
            return False
        elt = ann.slice.elts[-1] if isinstance(ann.slice, Tuple) else ann.slice
        return cls._is_string_annotation(elt)

    def _is_string_name(self, name: str) -> bool:
        return any(name in names for names in self._string_names)

    def _is_string_operand(self, node) -> bool:
        """rule:strformat -> a string literal, string(...) / FormatStr(...), a name declared as a string, or a
        call of a proc declared `-> string` (in this module, before the call)."""
        if isinstance(node, Constant):
            return isinstance(node.value, str)
        if isinstance(node, Name):
            return self._is_string_name(node.id)
        return isinstance(node, Call) and isinstance(node.func, Name) and (
            node.func.id in ("string", "FormatStr") or self._is_string_name(node.func.id + "()"))

    def visit_FunctionDef(self, node):
        if self._is_string_annotation(node.returns):
            self._string_names[-1].add(node.name + "()")  # rule:strformat: a proc returning a string
        self._scope_depth += 1
        params = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        self._string_names.append({x.arg for x in params if self._is_string_annotation(x.annotation)})
        self._string_seq_names.append({x.arg for x in params if self._is_string_seq_annotation(x.annotation)})
        self._function_helper(node, "")
        self._string_names.pop()
        self._string_seq_names.pop()
        self._scope_depth -= 1

    def visit_AsyncFunctionDef(self, node):
        self._scope_depth += 1
        self._function_helper(node, "async ")
        self._scope_depth -= 1

    def _check_packed_tuple(self, node_arg_args, body):
        # rule:funcdefpackedtuple
        for i, arg in enumerate(node_arg_args):
            if isinstance(arg.annotation, Subscript) and isinstance(arg.annotation.slice, Tuple) and\
                arg.arg.startswith("packed_tuple"):
                ast_name = arg.annotation.value
                if isinstance(ast_name, Name) and ast_name.id == "tuple":
                    tuple_name = arg.arg
                    types = arg.annotation.slice.elts
                    drop_j = -1
                    for j, item in enumerate(body):
                        if isinstance(item, Assign) and isinstance(item.value, Name) and item.value.id == tuple_name:
                            if isinstance(item.targets[0], Tuple):
                                defs = [elt.id + ": " + tp.id for elt, tp in zip(item.targets[0].elts, types)]
                                ast_name.id = ", ".join(defs)
                                node_arg_args[i] = ast_name
                                drop_j = j
                    if drop_j > -1:
                        body.pop(drop_j)

    def _has_yield(self, node):
        for x in node:
            for child in walk(x):
                if isinstance(child, (Yield, YieldFrom)):
                    return True
        return False


    def _function_helper(self, node, fill_suffix):
        if node.name == "_block":
            self._block_nodes.append(node)
            return
        # rule:funcdef
        self.maybe_newline()
        decl_str = "proc"
        # rule:funcdefdecorated
        for deco in node.decorator_list:
            if isinstance(deco, Name) and deco.id in self._def_decorators:
                decl_str = deco.id
        # rule:pragma
        body, pragma = self._get_body_and_pragma(node)
        is_private = False
        # rule:funcdefbody
        write_body = not isinstance(body[0], Pass)
        if pragma:
            parsed_pragma = pragma.replace(" ", "").split(",")
            write_body = write_body and "borrow" not in parsed_pragma
            if "noSideEffect" in parsed_pragma and decl_str == "proc":
                decl_str = "func"
                parsed_pragma = [x for x in parsed_pragma if x != "noSideEffect"]
                pragma = ",".join(parsed_pragma)
            if "private" in parsed_pragma:  # rule:privatepragma
                is_private = True
                pragma = ",".join([x for x in parsed_pragma if x != "private"])
        func_name = node.name
        do_arg_swap = False  # rule:funcdefargswap
        inplace = False  # rule:funcdefinplace
        no_return = False  # rule:typedtemplate
        if func_name[0:2] == "__" and func_name in self.dunder_ops:
            do_arg_swap = func_name in self.binpops_with_arg_swap
            # rule:funcdefinplace: __i<op>__ mapped to an assignment operator (`+=`, `<<=`, ...);
            # excludes other __i...__ dunders such as __invert__ / __iter__ / __index__
            inplace = func_name.startswith("__i") and self.dunder_ops[func_name].endswith("=`")
            func_name = self.dunder_ops[func_name]   # rule:funcdefrenamedunder
            if func_name == "`mod`" and node.args.args and node.args.args[0].annotation:
                ann_str = ast.unparse(node.args.args[0].annotation)
                if "FormatStr" in ann_str or "string" in ann_str:
                    func_name = "`%`"
        # rule:funcdefyield
        if decl_str != "iterator" and self._has_yield(body):
           decl_str = "iterator"
        is_module_level = (self._scope_depth <= 1)
        name_str = self._adjust_name(func_name, definition=is_module_level and not is_private)  # rule:localname
        # rule:calltype — emit as type alias: Name* = proc(...): T {.pragma.}
        if decl_str == "calltype":
            self.fill(name_str + " = proc")
            with self.delimit("(", ")"):
                self.traverse(node.args)
            if node.returns and not isinstance(node.returns, Constant):
                self.write(": ")
                self._write_annotation(node.returns)  # rule:funcdefmut
            if pragma:
                self.write(" {." + pragma + ".}")
            return
        def_str = fill_suffix + decl_str + " " + name_str
        if inplace and isinstance(node.args.args[0].annotation, Name):
            node.args.args[0].annotation.id = "var " + node.args.args[0].annotation.id
        if do_arg_swap:
            node.args.args[0], node.args.args[1] = node.args.args[1], node.args.args[0]
        self._check_packed_tuple(node.args.args, body) # rule:funcdefpackedtuple
        self.fill(def_str)
        if hasattr(node, "type_params"):
            self._type_params_helper(node.type_params)
        with self.delimit("(", ")"):
            self.traverse(node.args)
        if node.returns and not isinstance(node.returns, Constant) and not inplace:
            self.write(": ")
            self._write_annotation(node.returns)  # rule:funcdefmut
            typed_template = decl_str == "template"
            no_return = typed_template or decl_str == "converter"
        if pragma:
            self.write(" {." + pragma + ".}")
        if write_body:
            if decl_str == "template":
                self._context_stack.append("template")
                self._template_tail_returns.append(self._tail_returns(body if isinstance(body, list) else [body]))
            case_expr = decl_str != "template" and self._case_expression_returns(body)
            if case_expr:
                self._template_tail_returns.append(case_expr)
            with self.block(extra=self.get_type_comment(node), start=" ="):
                if isinstance(body, list) and isinstance(body[-1], Return):
                    if body[:-1]:
                        self.traverse(body[:-1])
                    if no_return:
                        if body[-1].value:
                            # do not print "return"
                            self.fill()
                            self.traverse(body[-1].value)
                    elif not inplace:
                        self.traverse(body[-1])
                else:
                    self.traverse(body)
            if decl_str == "template":
                self._context_stack.pop()
                self._template_tail_returns.pop()
            if case_expr:
                self._template_tail_returns.pop()

    @staticmethod
    def _case_expression_returns(body) -> set:
        """rule:casereturn -> a proc body ending with a match whose every branch is `return <value>` is a
        Nim case expression as the proc's result: the ids of those returns (written as values), or an
        empty set."""
        last = body[-1] if isinstance(body, list) and body else None
        if not isinstance(last, Match) or not all(
                len(c.body) == 1 and isinstance(c.body[0], Return) and c.body[0].value is not None
                for c in last.cases):
            return set()
        return {id(c.body[0]) for c in last.cases}

    def _tail_returns(self, stmts) -> set:
        """ids of the `return` statements in tail position of a template body: the template's
        value on every path (last statement, or the tails of an if/else or a match with `case _`
        that is itself in tail position). Other returns leave the enclosing routine, as in Nim."""
        if not stmts:
            return set()
        last = stmts[-1]
        if isinstance(last, Return):
            return {id(last)} if last.value is not None else set()
        if isinstance(last, If) and last.orelse:
            body, orelse = self._tail_returns(last.body), self._tail_returns(last.orelse)
            return body | orelse if body and orelse else set()
        if isinstance(last, Match) and last.cases and isinstance(last.cases[-1].pattern, MatchAs) \
                and last.cases[-1].pattern.pattern is None:
            tails = [self._tail_returns(c.body) for c in last.cases]
            return set().union(*tails) if all(tails) else set()
        if isinstance(last, With):
            return self._tail_returns(last.body)
        return set()

    def _get_pragma(self, docstring_value):
        doc = docstring_value
        if "{." in doc:
            pragma = doc.split("{.")[1].split(".}")[0]
        else:
            pragma = ""
        return pragma

    def _get_body_and_pragma(self, node):
        if (docstring := self.get_raw_docstring(node)):
            # check if pragma {. .} is present
            pragma = self._get_pragma(docstring.value)
            body = node.body[1:]
        else:
            pragma = ""
            body = node.body
        return body, pragma

    def _type_params_helper(self, type_params):
        if type_params is not None and len(type_params) > 0:
            with self.delimit("[", "]"):
                self.interleave(lambda: self.write(", "), self.traverse, type_params)

    def visit_TypeVar(self, node):
        self.write(node.name)
        if node.bound:
            self.write(": ")
            self.traverse(node.bound)

    def visit_TypeVarTuple(self, node):
        self.write("*" + node.name)

    def visit_ParamSpec(self, node):
        self.write("**" + node.name)

    def visit_TypeAlias(self, node):
        self.fill("type ")
        self.write(self._adjust_name(node.name.id, definition=self._scope_depth == 0))  # rule:localname
        self._type_params_helper(node.type_params)
        self.write(" = ")
        self.traverse(node.value)

    def visit_For(self, node):
        self._for_helper("for ", node)

    def visit_AsyncFor(self, node):
        self._for_helper("async for ", node)

    def _for_helper(self, fill, node):
        self.fill(fill)
        # rule:fortupleunpack -> Python unpacks each item, which in Nim is `for (a, b) in xs`
        # (bare `for a, b in xs` would mean pairs: index + item). Nim's magic iterators
        # fields(a, b) / fieldPairs(x) yield separate values, not a tuple: they need bare names.
        if isinstance(node.target, Tuple) and not (
                isinstance(node.iter, Call) and isinstance(node.iter.func, Name)
                and node.iter.func.id in self._multi_value_iterators):
            with self.delimit("(", ")"):
                self.items_view(self.traverse, node.target.elts)
        elif isinstance(node.target, Tuple):
            self.items_view(self.traverse, node.target.elts)
        else:
            self.set_precedence(_Precedence.TUPLE, node.target)
            self.traverse(node.target)
        self.write(" in ")
        self.traverse(node.iter)

        with self.block(extra=self.get_type_comment(node)):
            self._scope_depth += 1  # a loop body is a scope in Nim: its variables are not exported
            self.traverse(node.body)
            self._scope_depth -= 1
        if node.orelse:
            self.fill("else")
            with self.block():
                self.traverse(node.orelse)

    def _check_comptime(self, test_node):
        if isinstance(test_node, Call) and isinstance(test_node.func, Name) and test_node.func.id == "comptime":
            return True, test_node.args[0]
        if isinstance(test_node, UnaryOp) and isinstance(test_node.op, Not):
            inner_comptime, inner_arg = self._check_comptime(test_node.operand)
            if inner_comptime:
                return True, UnaryOp(op=test_node.op, operand=inner_arg)
        return False, test_node

    def visit_If(self, node):
        # rule:comptime
        comptime, test_expr = self._check_comptime(node.test)
        if comptime:
            self.fill("when ")
            self.traverse(test_expr)
        else:
            self.fill("if ")
            self.traverse(test_expr)
        # a `when` is no scope: at module level its symbols are module-level (exported with `*`)
        depth = 0 if comptime else 1
        with self.block():
            self._scope_depth += depth
            self.traverse(node.body)
            self._scope_depth -= depth
        # collapse nested ifs into equivalent elifs.
        while node.orelse and len(node.orelse) == 1 and isinstance(node.orelse[0], If):
            next_comptime, next_test = self._check_comptime(node.orelse[0].test)
            if comptime != next_comptime:
                break
            node = node.orelse[0]
            self.fill("elif ")
            self.traverse(next_test)
            with self.block():
                self._scope_depth += depth
                self.traverse(node.body)
                self._scope_depth -= depth
        # final else
        if node.orelse:
            self.fill("else")
            with self.block():
                self._scope_depth += depth
                self.traverse(node.orelse)
                self._scope_depth -= depth

    def visit_While(self, node):
        self.fill("while ")
        self.traverse(node.test)
        with self.block():
            self._scope_depth += 1  # a loop body is a scope in Nim
            self.traverse(node.body)
            self._scope_depth -= 1
        if node.orelse:
            self.fill("else")
            with self.block():
                self.traverse(node.orelse)

    def write_template_inline(self, node):
        if isinstance(node.body[0], Assign):
            assign = node.body[0]
            pragma_str = ""
        else:
            assign = node.body[1]
            pragma = self._get_pragma(node.body[0].value.value)
            pragma_str = "{." + pragma + ".} "
        tname = assign.targets[0].id
        # apply rule:localname
        self.fill(f"template {self._adjust_name(tname)}(): untyped {pragma_str}=")
        with self.block(start=""):
            self.fill()
            self.traverse(assign.value)

    def visit_With(self, node):
        ctx = node.items[0].context_expr
        if (isinstance(ctx, Call) and isinstance(ctx.func, Name) and ctx.func.id == "block" and len(ctx.args) == 1
                and isinstance(ctx.args[0], Constant) and isinstance(ctx.args[0].value, str)):
            # rule:labeledblock -> with block("name"): body  is  block name: body
            self.fill(f"block {ctx.args[0].value}")
            with self.block():
                self.traverse(node.body)
            return
        if (isinstance(ctx, Call) and isinstance(ctx.func, Name) and ctx.func.id == "push"
                and len(ctx.args) == 1 and isinstance(ctx.args[0], Constant) and isinstance(ctx.args[0].value, str)):
            # rule:push -> with push("p"): body  is  {.push p.} body {.pop.} (Nim's push is not a block)
            self.fill(f"{{.push {ctx.args[0].value}.}}")
            self.traverse(node.body)
            self.fill("{.pop.}")
            return
        if (isinstance(ctx, Call) and isinstance(ctx.func, Name) and ctx.func.id == "pragma"
                and len(ctx.args) == 1 and isinstance(ctx.args[0], Constant) and isinstance(ctx.args[0].value, str)):
            # rule:pragmablock -> with pragma("p"): body  is  {.p.}: body
            self.fill(f"{{.{ctx.args[0].value}.}}")
            with self.block(start=":"):
                self.traverse(node.body)
            return
        # rule:dropwith
        name = None
        cont_pop = False
        start = ":"
        if isinstance(node.items[0].context_expr, Name):
            name = node.items[0].context_expr.id
            if name in self._keywords_no_with:
                self.fill()
                self._context_stack.append(name)
                cont_pop = True
                start = ""
            elif name in self._keywords_no_with_colon:
                self.fill()
                self._context_stack.append(name)
                cont_pop = True
            elif name == "uncheckedAssign":
                # rule:uncheckedassign -> with uncheckedAssign: is a {.cast(uncheckedAssign).}: block
                self.fill("{.cast(uncheckedAssign).}")
                with self.block(start=":"):
                    self.traverse(node.body)
                return
            elif name == "do":
                # rule:doblock -> with do: block translates as do: block in Nim
                self._indent -= 1
                self.fill("do")
                with self.block(start=":"):
                    self.traverse(node.body)
                self._indent += 1
                return
            if name in self._keywords_rename:
                node.items[0].context_expr.id = self._keywords_rename[name]
        else:
            self.fill()
        if name == "template_inline":
            # rule:templateinline
            self.write_template_inline(node)
        else:
            self.interleave(lambda: self.write(", "), self.traverse, node.items)
            with self.block(extra=self.get_type_comment(node), start=start):
                self.traverse(node.body)
            if cont_pop:
                self._context_stack.pop()

    def visit_AsyncWith(self, node):
        self.fill("async with ")
        self.interleave(lambda: self.write(", "), self.traverse, node.items)
        with self.block(extra=self.get_type_comment(node)):
            self.traverse(node.body)

    def _str_literal_helper(
        self, string, *, quote_types=_ALL_QUOTES, escape_special_whitespace=False
    ):
        """Helper for writing string literals, minimizing escapes.
        Returns the tuple (string literal to write, possible quote types).
        """
        def escape_char(c):
            # \n and \t are non-printable, but we only escape them if
            # escape_special_whitespace is True
            if not escape_special_whitespace and c in "\n\t":
                return c
            # Always escape backslashes and other non-printable characters
            if c == "\\" or not c.isprintable():
                return c.encode("unicode_escape").decode("ascii")
            return c

        escaped_string = "".join(map(escape_char, string))
        possible_quotes = quote_types
        if "\n" in escaped_string:
            possible_quotes = [q for q in possible_quotes if q in _MULTI_QUOTES]
        possible_quotes = [q for q in possible_quotes if q not in escaped_string]
        if not possible_quotes:
            # If there aren't any possible_quotes, fallback to using repr
            # on the original string. Try to use a quote from quote_types,
            # e.g., so that we use triple quotes for docstrings.
            string = repr(string)
            quote = next((q for q in quote_types if string[0] in q), string[0])
            return string[1:-1], [quote]
        if escaped_string:
            # Sort so that the trailing-quote escape uses the less common option
            possible_quotes.sort(key=lambda q: q[0] == escaped_string[-1])
            # If we're using triple quotes and we'd need to escape a final
            # quote, escape it
            if possible_quotes[0][0] == escaped_string[-1]:
                assert len(possible_quotes[0]) == 3
                escaped_string = escaped_string[:-1] + "\\" + escaped_string[-1]
        return escaped_string, possible_quotes

    def _write_str_avoiding_backslashes(self, string, *, quote_types=_ALL_QUOTES):
        """Write string literal value with a best effort attempt to avoid backslashes."""
        string, quote_types = self._str_literal_helper(string, quote_types=quote_types)
        quote_type = quote_types[0]
        self.write(f"{quote_type}{string}{quote_type}")

    def visit_JoinedStr(self, node):
        self.write("&")  # rule:stringjoin

        fstring_parts = []
        for value in node.values:
            with self.buffered() as buffer:
                self._write_fstring_inner(value)
            fstring_parts.append(
                ("".join(buffer), isinstance(value, Constant))
            )

        new_fstring_parts = []
        quote_types = list(_ALL_QUOTES)
        fallback_to_repr = False
        for value, is_constant in fstring_parts:
            if is_constant:
                value, new_quote_types = self._str_literal_helper(
                    value,
                    quote_types=quote_types,
                    escape_special_whitespace=True,
                )
                value = self._latin1_escape(value)  # rule:latin1literal
                if set(new_quote_types).isdisjoint(quote_types):
                    fallback_to_repr = True
                    break
                quote_types = new_quote_types
            elif "\n" in value:  # rule:quote
                quote_types = [q for q in quote_types if q in _MULTI_QUOTES]
                assert quote_types
            new_fstring_parts.append(value)

        if fallback_to_repr:
            # If we weren't able to find a quote type that works for all parts
            # of the JoinedStr, fallback to triple double quotes.
            quote_types = ['"""']
            new_fstring_parts.clear()
            for value, is_constant in fstring_parts:
                if is_constant:
                    # Escape inner double quotes for triple-double-quoted string
                    value = value.replace("\\", "\\\\")
                    value = value.replace('"', '\\"')
                    value = self._latin1_escape(value)  # rule:latin1literal
                new_fstring_parts.append(value)

        value = "".join(new_fstring_parts)
        quote_type = quote_types[0]
        self.write(f"{quote_type}{value}{quote_type}")

    def _write_fstring_inner(self, node, is_format_spec=False):
        if isinstance(node, JoinedStr):
            # for both the f-string itself, and format_spec
            for value in node.values:
                self._write_fstring_inner(value, is_format_spec=is_format_spec)
        elif isinstance(node, Constant) and isinstance(node.value, str):
            value = node.value.replace("{", "{{").replace("}", "}}")

            if is_format_spec:
                value = value.replace("\\", "\\\\")
                value = value.replace("'", "\\'")
                value = value.replace('"', '\\"')
                value = value.replace("\n", "\\n")
            self.write(value)
        elif isinstance(node, FormattedValue):
            self.visit_FormattedValue(node)
        else:
            raise ValueError(f"Unexpected node inside JoinedStr, {node!r}")

    def visit_FormattedValue(self, node):
        def unparse_inner(inner):
            unparser = type(self)()
            unparser.set_precedence(_Precedence.TEST.next(), inner)
            return unparser.visit(inner)

        with self.delimit("{", "}"):
            expr = unparse_inner(node.value)
            if expr.startswith("{"):
                # Separate pair of opening brackets as "{ {"
                self.write(" ")
            self.write(expr)
            if node.conversion != -1:
                self.write(f"!{chr(node.conversion)}")
            if node.format_spec:
                self.write(":")
                self._write_fstring_inner(node.format_spec, is_format_spec=True)

    def visit_Name(self, node):
        name = self._adjust_name(node.id, definition=getattr(node, "_is_definition", False)) # rule:localname
        self.write(name)

    def _write_docstring(self, node):
        self.fill()
        if node.kind == "u":
            self.write("u")
        self._write_str_avoiding_backslashes(node.value, quote_types=_MULTI_QUOTES)

    @staticmethod
    def _latin1_escape(text):
        """rule:latin1literal -> a nimic str literal is a byte view: chars 0x80-0xFF are
        the bytes themselves and become Nim \\xNN escapes; chars above 0xFF are no bytes."""
        out = []
        for c in text:
            o = ord(c)
            if o > 0xFF:
                raise SyntaxError(
                    f"character {c!r} (U+{o:04X}) in a string literal cannot be a Nim byte; "
                    f"use utf8(\"...\") for UTF-8 text or escape bytes explicitly")
            out.append(f"\\x{o:02X}" if o >= 0x80 else c)
        return "".join(out)

    def _nim_str_literal(self, value, *, utf8=False):
        """Nim double-quoted literal for str constant `value`. Byte semantics by
        default (rule:latin1literal); utf8=True keeps the text raw, since Nim source
        is UTF-8 and the literal then holds its UTF-8 bytes (rule:utf8literal)."""
        # Escape inner double quotes and special chars, wrap in double quotes
        escaped = value.replace("\\", "\\\\")
        escaped = escaped.replace('"', '\\"')
        escaped = escaped.replace("\n", "\\n")
        escaped = escaped.replace("\t", "\\t")
        escaped = escaped.replace("\r", "\\r")
        escaped = escaped.replace("\0", "\\0")
        if not utf8:
            escaped = self._latin1_escape(escaped)  # rule:latin1literal
        return f'"{escaped}"'

    def _write_constant(self, value):
        if isinstance(value, (float, complex)):
            # Substitute overflowing decimal literal for AST infinities,
            # and inf - inf for NaNs.
            self.write(
                repr(value)
                .replace("inf", _INFSTR)
                .replace("nan", f"({_INFSTR}-{_INFSTR})")
            )
        elif self._avoid_backslashes and isinstance(value, str):
            self._write_str_avoiding_backslashes(value)
        else:
            # rule:quote
            if isinstance(value, str):
                repr_value = self._nim_str_literal(value)
            else:
                repr_value = repr(value)
            if repr_value in self._const_rename:
                # rule:lowercasebool
                self.write(self._const_rename[repr_value])
            else:
                self.write(repr_value)

    def visit_Constant(self, node):
        value = node.value
        if isinstance(value, tuple):
            with self.delimit("(", ")"):
                self.items_view(self._write_constant, value)
        elif value is ...:
            self.write("...")
        else:
            if node.kind == "u":
                self.write("u")
            self._write_constant(node.value)

    def visit_List(self, node):
        with self.delimit("[", "]"):
            self.interleave(lambda: self.write(", "), self.traverse, node.elts)

    def visit_ListComp(self, node):
        with self.delimit("[", "]"):
            self.traverse(node.elt)
            for gen in node.generators:
                self.traverse(gen)

    def visit_GeneratorExp(self, node):
        with self.delimit("(", ")"):
            self.traverse(node.elt)
            for gen in node.generators:
                self.traverse(gen)

    def visit_SetComp(self, node):
        with self.delimit("{", "}"):
            self.traverse(node.elt)
            for gen in node.generators:
                self.traverse(gen)

    def visit_DictComp(self, node):
        with self.delimit("{", "}"):
            self.traverse(node.key)
            self.write(": ")
            self.traverse(node.value)
            for gen in node.generators:
                self.traverse(gen)

    def visit_comprehension(self, node):
        if node.is_async:
            self.write(" async for ")
        else:
            self.write(" for ")
        self.set_precedence(_Precedence.TUPLE, node.target)
        self.traverse(node.target)
        self.write(" in ")
        self.set_precedence(_Precedence.TEST.next(), node.iter, *node.ifs)
        self.traverse(node.iter)
        for if_clause in node.ifs:
            self.write(" if ")
            self.traverse(if_clause)

    def visit_IfExp(self, node):
        with self.require_parens(_Precedence.TEST, node):
            self.set_precedence(_Precedence.TEST.next(), node.body, node.test)
            # rule:inlineif; rule:comptimeexpr -> `a if comptime(c) else b` is `when c: a else: b`
            comptime, test_expr = self._check_comptime(node.test)
            self.write("when " if comptime else "if ")
            self.traverse(test_expr)
            self.write(": ")
            self.traverse(node.body)
            self.write(" else: ")
            self.set_precedence(_Precedence.TEST.next(), node.orelse)
            self.traverse(node.orelse)

    def visit_Set(self, node):
        if node.elts:
            with self.delimit("{", "}"):
                self.interleave(lambda: self.write(", "), self.traverse, node.elts)
        else:
            # `{}` would be interpreted as a dictionary literal, and
            # `set` might be shadowed. Thus:
            self.write('{*()}')

    def visit_Dict(self, node):
        def write_key_value_pair(k, v):
            self.traverse(k)
            self.write(": ")
            self.traverse(v)

        def write_item(item):
            k, v = item
            if k is None:
                # for dictionary unpacking operator in dicts {**{'y': 2}}
                # see PEP 448 for details
                self.write("**")
                self.set_precedence(_Precedence.EXPR, v)
                self.traverse(v)
            else:
                write_key_value_pair(k, v)

        with self.delimit("{", "}"):
            self.interleave(
                lambda: self.write(", "), write_item, zip(node.keys, node.values)
            )

    def visit_Tuple(self, node):
        with self.delimit_if(
            "(",
            ")",
            len(node.elts) == 0 or self.get_precedence(node) > _Precedence.TUPLE
        ):
            self.items_view(self.traverse, node.elts)

    unop = {"Invert": "not", "Not": "not", "UAdd": "+", "USub": "-"}
    unop_precedence = {
        "not": _Precedence.FACTOR,
        "~": _Precedence.FACTOR,
        "+": _Precedence.FACTOR,
        "-": _Precedence.FACTOR,
    }

    def visit_UnaryOp(self, node):
        operator = self.unop[node.op.__class__.__name__]
        operator_precedence = self.unop_precedence[operator]
        with self.require_parens(operator_precedence, node):
            self.write(operator)
            # factor prefixes (+, -) shouldn't be separated
            # from the value they belong, (e.g: +1 instead of + 1), but "not" always needs a space
            if operator not in ("+", "-"):
                self.write(" ")
            self.set_precedence(operator_precedence, node.operand)
            self.traverse(node.operand)
    # rule:assign
    ibinop = {
        "Add": "+",
        "Sub": "-",
        "Mult": "*",
        "MatMult": "@",
        "Div": "/",
        "Mod": "%",
        "LShift": "", # "<<",
        "RShift": ">>",
        "BitOr": "|",
        "BitXor": "^",
        "BitAnd": "&",
        "FloorDiv": "//",
        "Pow": "**",
    }
    # rule:bitwiserename
    binop = {
        "Add": "+",
        "Sub": "-",
        "Mult": "*",
        "MatMult": "@",
        "Div": "/",
        "Mod": "mod",
        "LShift": "shl",
        "RShift": "shr",
        "BitOr": "or",
        "BitXor": "xor",
        "BitAnd": "and",
        "FloorDiv": "div",
        "Pow": "^",
    }
    # rule:funcdefargswap
    binpops_with_arg_swap = ["__radd__", "__rmul__", "__rmatmul__", "__rdiv__", "__rfloordiv__"]
    # rule:funcdefrenamedunder
    # Nim magic iterators yielding several values (not a tuple) per step (rule:fortupleunpack)
    _multi_value_iterators = frozenset({"fields", "fieldPairs"})

    dunder_ops = {
        # unops
        "__str__": "`$`",
        "__getitem__": "`[]`",
        "__setitem__": "`[]=`",
        # "__invert__": "`~`",
        "__not__": "`not`",
        "__pos__": "`+`",
        "__neg__": "`-`",
        # binops
        "__eq__": "`==`",
        "__add__": "`+`",
        "__radd__": "`+`",
        "__sub__": "`-`",
        "__mul__": "`*`",
        "__rmul__": "`*`",
        "__matmul__": "`@`",
        "__truediv__": "`/`",
        "__floordiv__": "`div`",
        "__mod__": "`mod`",
        "__pow__": "`^`",
        "__lshift__": "`shl`",
        "__rshift__": "`shr`",
        "__and__": "`and`",
        "__xor__": "`xor`",
        "__or__": "`|`",
        "__iadd__": "`+=`",
        "__isub__": "`-=`",
        "__imul__": "`*=`",
        "__imatmul__": "`@=`",
        "__itruediv__": "`/=`",
        "__ifloordiv__": "`//=`",
        "__imod__": "`%=`",
        "__ipow__": "`**=`",
        "__ilshift__": "`<<=`",
        "__irshift__": "`>>=`",
        "__iand__": "`&=`",
        "__ixor__": "`^=`",
        "__ior__": "`|=`",
        "__lt__": "`<`",
        "__le__": "`<=`",
        "__gt__": "`>`",
        "__ge__": "`>=`",
        "__ne__": "`!=`",
    }
# rule:bitwiserename
    binop_precedence = {
        "+": _Precedence.ARITH,
        "-": _Precedence.ARITH,
        "*": _Precedence.TERM,
        "@": _Precedence.TERM,
        "/": _Precedence.TERM,
        "mod": _Precedence.TERM,
        "shl": _Precedence.TERM, #_Precedence.SHIFT,
        "shr": _Precedence.TERM, #_Precedence.SHIFT,
        "or": _Precedence.OR,
        "xor": _Precedence.OR,
        "and": _Precedence.AND,
        "div": _Precedence.TERM,
        "^": _Precedence.POWER,
        "%": _Precedence.TERM,
    }

    binop_rassoc = frozenset(("**",))
    def visit_BinOp(self, node):
        # rule:strformat -> Python % on string operands transpiles as Nim % (format) instead of mod
        is_str_mod = node.op.__class__.__name__ == "Mod" and (
            self._is_string_operand(node.left) or isinstance(node.right, (List, Tuple)) or
            isinstance(node.right, Name) and any(node.right.id in names for names in self._string_seq_names)
        )
        if is_str_mod:
            operator = "%"
        else:
            operator = self.binop[node.op.__class__.__name__]
        operator_precedence = self.binop_precedence[operator]
        with self.require_parens(operator_precedence, node):
            if operator in self.binop_rassoc:
                left_precedence = operator_precedence.next()
                right_precedence = operator_precedence
            else:
                left_precedence = operator_precedence
                right_precedence = operator_precedence.next()

            self.set_precedence(left_precedence, node.left)
            self.traverse(node.left)
            self.write(f" {operator} ")
            self.set_precedence(right_precedence, node.right)
            self.traverse(node.right)

    # rule:percentops -> Nim wrapping operators, spelled as calls / NInteger methods in nimic.
    # Nim derives operator precedence from the first character, so +% / -% bind like + / -.
    percent_ops = {
        "plus_percent": ("+%", _Precedence.ARITH),
        "minus_percent": ("-%", _Precedence.ARITH),
        "lt_percent": ("<%", _Precedence.CMP),
        "le_percent": ("<=%", _Precedence.CMP),
        "gt_percent": (">%", _Precedence.CMP),
        "ge_percent": (">=%", _Precedence.CMP),
        # rule:namedops -> std/hashes; Nim's precedence of `!&` is that of `!`, a comparison
        "mix_hash": ("!&", _Precedence.CMP),
    }
    # rule:namedops -> prefix operators spelled as calls
    prefix_named_ops = {"finish_hash": "!$", "back": "^"}  # back(n): Nim's ^n (BackwardsIndex)

    def _write_infix(self, operator, precedence, node, left, right):
        """Emit `left operator right` for a call-spelled binary operator (left-associative),
        parenthesized when the surrounding context binds tighter."""
        with self.require_parens(precedence, node):
            self.set_precedence(precedence, left)
            self.traverse(left)
            self.write(f" {operator} ")
            self.set_precedence(precedence.next(), right)
            self.traverse(right)

    cmpops = {
        "Eq": "==",
        "NotEq": "!=",
        "Lt": "<",
        "LtE": "<=",
        "Gt": ">",
        "GtE": ">=",
        "Is": "is",
        "IsNot": "isnot",  # rule:isnot
        "In": "in",
        "NotIn": "notin",  # rule:notin
    }

    def visit_Compare(self, node):
        with self.require_parens(_Precedence.CMP, node):
            self.set_precedence(_Precedence.CMP.next(), node.left, *node.comparators)
            # rule:main, check for "__name__ == __main__"
            if isinstance(node.left, Name) and node.left.id == "__name__" and isinstance(node.ops[0], Eq) and \
                isinstance(node.comparators[0], Constant) and node.comparators[0].value == "__main__":
                self.write("isMainModule")
            else:
                self.traverse(node.left)
                for o, e in zip(node.ops, node.comparators):
                    op_name = o.__class__.__name__
                    # rule:nilident -> "is None" / "is not None" transpile as == nil / != nil
                    if op_name == "Is" and isinstance(e, Constant) and e.value is None:
                        self.write(" == ")
                    elif op_name == "IsNot" and isinstance(e, Constant) and e.value is None:
                        self.write(" != ")
                    else:
                        self.write(" " + self.cmpops[op_name] + " ")
                    if op_name in ("In", "NotIn") and isinstance(e, Tuple):
                        with self.delimit("[", "]"):
                            self.interleave(lambda: self.write(", "), self.traverse, e.elts)
                    else:
                        self.traverse(e)

    boolops = {"And": "and", "Or": "or"}
    boolop_precedence = {"and": _Precedence.AND, "or": _Precedence.OR}

    def visit_BoolOp(self, node):
        operator = self.boolops[node.op.__class__.__name__]
        operator_precedence = self.boolop_precedence[operator]

        def increasing_level_traverse(node):
            nonlocal operator_precedence
            operator_precedence = operator_precedence.next()
            self.set_precedence(operator_precedence, node)
            self.traverse(node)

        with self.require_parens(operator_precedence, node):
            s = f" {operator} "
            self.interleave(lambda: self.write(s), increasing_level_traverse, node.values)

    def visit_Attribute(self, node):
        self.set_precedence(_Precedence.ATOM, node.value)
        self.traverse(node.value)
        # Special case: 3.__abs__() is a syntax error, so if node.value
        # is an integer literal then we need to either parenthesize
        # it or add an extra space to get 3 .__abs__().
        if isinstance(node.value, Constant) and isinstance(node.value.value, int):
            self.write(" ")
        if node.attr in self._attribute_replace:
            # rule:deref and rule:copy
            self.write(self._attribute_replace[node.attr])
        else:
            self.write(".")
            attr = self._adjust_name(node.attr, definition=False) # rule:localname
            self.write(attr)

    def visit_Call(self, node):
        if isinstance(node.func, Name) and node.func.id in ("str", "$") and self.get_precedence(node) > _Precedence.FACTOR:
            # rule:dollarparens -> `$` is a prefix operator: as the base of an index or attribute, str(x)[i] and
            # str(x).f are ($(x))[i] and ($(x)).f
            self.set_precedence(_Precedence.FACTOR, node)
            with self.delimit("(", ")"):
                self.visit_Call(node)
            return
        self.set_precedence(_Precedence.ATOM, node.func)
        if isinstance(node.func, Name) and node.func.id in self._type_suffixes:
            # rule:literaltypes
            self.traverse(node.args[0]) # should be only one argument
            self.write("'")
            self.traverse(node.func)
        elif isinstance(node.func, Name) and (node.func.id == "ch" or (
                node.func.id == "char" and len(node.args) == 1 and isinstance(node.args[0], Constant)
                and isinstance(node.args[0].value, str) and len(node.args[0].value) == 1)):
            # rule:char
            val = node.args[0].value
            char_escapes = {
                "'": r"'\''",
                "\\": r"'\\'",
                "\n": r"'\n'",
                "\t": r"'\t'",
                "\r": r"'\r'",
                "\0": r"'\0'",
            }
            if val in char_escapes:
                self.write(char_escapes[val])
            elif val.isascii() and val.isprintable():
                self.write(f"'{val}'")
            else:
                st = val.encode("Latin-1").hex()
                self.write(f"'\\x{st}'")
        elif (isinstance(node.func, Name) and node.func.id == "utf8" and len(node.args) == 1
              and isinstance(node.args[0], Constant) and isinstance(node.args[0].value, str)):
            # rule:utf8literal -> utf8("é") emits the raw Nim literal "é" (its UTF-8 bytes)
            self.write(self._nim_str_literal(node.args[0].value, utf8=True))
        elif isinstance(node.func, Name) and node.func.id == "FormatStr" and len(node.args) == 1:
            # rule:formatstr -> FormatStr(s) unwraps to s in Nim (where string is FormatStr)
            self.traverse(node.args[0])
        elif isinstance(node.func, Name) and node.func.id == "inrange" and len(node.args) == 2:
            # rule:inrange -> inrange(a, b) translates to a .. b in Nim
            self.traverse(node.args[0])
            self.write(" .. ")
            self.traverse(node.args[1])
        elif isinstance(node.func, Name) and node.func.id in self.percent_ops and len(node.args) == 2:
            # rule:percentops -> plus_percent(a, b) / minus_percent(a, b) translate to a +% b / a -% b
            self._write_infix(*self.percent_ops[node.func.id], node, node.args[0], node.args[1])
        elif isinstance(node.func, Name) and node.func.id in self.prefix_named_ops and len(node.args) == 1:
            # rule:namedops -> finish_hash(h) translates to !$h
            self.write(self.prefix_named_ops[node.func.id])
            self.set_precedence(_Precedence.ATOM, node.args[0])
            self.traverse(node.args[0])
        elif isinstance(node.func, Attribute) and node.func.attr in self.percent_ops and len(node.args) == 1:
            # rule:percentops -> method form a.plus_percent(b) / a.minus_percent(b) (NInteger methods)
            self._write_infix(*self.percent_ops[node.func.attr], node, node.func.value, node.args[0])
        elif isinstance(node.func, Attribute) and node.func.attr in self._attribute_replace and not node.args:
            # rule:deref and rule:copy
            self.traverse(node.func.value)
            self.write(self._attribute_replace[node.func.attr])
        elif isinstance(node.func, Name) and node.func.id in ("defined", "declared") and len(node.args) == 1 and isinstance(node.args[0], Constant) and isinstance(node.args[0].value, str):
            # rule:defined -> defined("identifier") translates to defined(identifier) in Nim
            # rule:declared -> declared("identifier") translates to declared(identifier) in Nim
            self.write(f"{node.func.id}({node.args[0].value})")
        elif isinstance(node.func, Name) and node.func.id in ("isinstance", "issubclass") and len(node.args) == 2:
            # rule:isinstance -> isinstance(x, T) translates to x is T in Nim, issubclass(T, X) (a type
            # parameter, `when T is bool`) to T is X
            self.traverse(node.args[0])
            self.write(" is ")
            self.traverse(node.args[1])
        # rule:tuplelit -> NTuple subclass constructor calls transpile as Nim tuple literals
        elif isinstance(node.func, Name) and node.func.id in self._tuple_types:
            with self.delimit("(", ")"):
                comma = False
                for e in node.args:
                    if comma:
                        self.write(", ")
                    else:
                        comma = True
                    self.traverse(e)
                for e in node.keywords:
                    if comma:
                        self.write(", ")
                    else:
                        comma = True
                    self.write(e.arg + ": ")
                    self.traverse(e.value)
        # rule:setlit -> Tset/set constructor calls transpile as Nim set literals {a, b, ...}
        elif (
            (isinstance(node.func, Name) and (node.func.id in self._set_types or node.func.id in ("set", "Tset")))
            or (isinstance(node.func, Subscript) and isinstance(node.func.value, Name) and node.func.value.id in ("Tset", "set"))
        ):
            if not node.args and not node.keywords:
                self.write("{}")
            elif len(node.args) == 1 and (isinstance(node.args[0], Set) or (isinstance(node.args[0], Dict) and not node.args[0].keys)):
                if isinstance(node.args[0], Set):
                    self.traverse(node.args[0])
                else:
                    self.write("{}")
            else:
                self.write("{")
                self.interleave(lambda: self.write(", "), self.traverse, node.args)
                self.write("}")
        # rule:seqlit -> seq constructor calls transpile as Nim seq literals @[a, b, ...]
        elif (
            (isinstance(node.func, Name) and (node.func.id in self._seq_types or node.func.id == "seq"))
            or (isinstance(node.func, Subscript) and isinstance(node.func.value, Name) and node.func.value.id == "seq")
        ):
            if not node.args and not node.keywords:
                self.write("@[]")
            elif len(node.args) == 1 and isinstance(node.args[0], List):
                self.write("@")
                self.traverse(node.args[0])
            else:
                self.write("@")
                with self.delimit("[", "]"):
                    self.interleave(lambda: self.write(", "), self.traverse, node.args)
        else:
            pop = False
            func_name = None
            if isinstance(node.func, Name):
                func_name = node.func.id
            elif isinstance(node.func, Subscript) and isinstance(node.func.value, Name):
                func_name = node.func.value.id

            if func_name is not None:
                _name = func_name
                is_local_class = _name.startswith("_") and len(_name) > 1 and _name[1].isupper() or \
                    _name.startswith("local_") and len(_name) > 6 and _name[6].isupper()
                if _name[0].isupper() or is_local_class:
                    # rule:instantiation, classes instantiated with keywords should be named starting with a capital letter
                    self._context_stack.append("instance")
                else:
                    self._context_stack.append("call")
                pop = True
                # rule:funcrename
                if isinstance(node.func, Name) and _name in self._func_rename:
                    node.func.id = self._func_rename[_name]
            # rule:array (indexed form): array[I, T]({k: v, ...}) is the Nim array constructor [k: v, ...]
            if (isinstance(node.func, Subscript) and isinstance(node.func.value, Name) and node.func.value.id == "array"
                    and len(node.args) == 1 and isinstance(node.args[0], Dict) and not node.keywords):
                with self.delimit("[", "]"):
                    def write_item(item):
                        k, v = item
                        self.traverse(k)
                        self.write(": ")
                        self.traverse(v)
                    self.interleave(lambda: self.write(", "), write_item, zip(node.args[0].keys, node.args[0].values))
                if pop:
                    self._context_stack.pop()
                return
            # independent of the call-context branch above (array[N, T] calls also set func_name)
            if (
                isinstance(node.func, Subscript)
                and node.args
                and isinstance(node.args[0], List)
                and node.func.value.id in self._native_type_subscript
                and len(node.func.slice.elts) == 2
                and node.args[0].elts
                and isinstance(node.args[0].elts[0], Constant)
            ):
                # rule:array
                array_type = node.func.slice.elts[1].id
                call_node = Call(func=Name(id=array_type), args=[Constant(value=node.args[0].elts[0].value)], keywords=[])
                node.args[0].elts[0] = call_node
            self.traverse(node.func)
            with self.delimit("(", ")"):
                comma = False
                for e in node.args:
                    if comma:
                        self.write(", ")
                    else:
                        comma = True
                    self.traverse(e)
                for e in node.keywords:
                    if comma:
                        self.write(", ")
                    else:
                        comma = True
                    self.traverse(e)
            if pop:
                self._context_stack.pop()

    def visit_Subscript(self, node):
        def is_non_empty_tuple(slice_value):
            return (
                isinstance(slice_value, Tuple)
                and slice_value.elts
            )

        # rule:trange -> Trange[a, b] translates to range[a .. b] in Nim
        if isinstance(node.value, Name) and node.value.id == "Trange":
            self.write("range[")
            if isinstance(node.slice, Tuple) and len(node.slice.elts) == 2:
                self.traverse(node.slice.elts[0])
                self.write(" .. ")
                self.traverse(node.slice.elts[1])
            else:
                self.traverse(node.slice)
            self.write("]")
            return

        # rule:tupletype -> tuple[T1, T2] slice translates as (T1, T2) tuple type in Nim
        if isinstance(node.value, Name) and node.value.id == "tuple":
            with self.delimit("(", ")"):
                if is_non_empty_tuple(node.slice):
                    self.items_view(self.traverse, node.slice.elts)
                else:
                    self.traverse(node.slice)
            return

        if isinstance(node.value, Name) and node.value.id == "Tset":
            node.value.id = "set"

        self.set_precedence(_Precedence.ATOM, node.value)
        # feature:subscriptrename
        if isinstance(node.value, Name) and node.value.id in self._subscript_rename and self._context_stack:
            if self._context_stack[-1] in self._keywords_no_with:
                node.value.id = self._subscript_rename[node.value.id]
        self.traverse(node.value)
        # rule:dropbrackets, ptr[] -> ptr
        if isinstance(node.value, Name) and node.value.id in self._no_bracket_subscript:
            self.write(" ")
            self.traverse(node.slice)
        else:
            with self.delimit("[", "]"):
                if is_non_empty_tuple(node.slice):
                    # parentheses can be omitted if the tuple isn't empty
                    self.items_view(self.traverse, node.slice.elts)
                else:
                    self.traverse(node.slice)

    def visit_Starred(self, node):
        # rule:varargs -> a starred call argument f(a, *args) passes a varargs/seq on: f(a, args)
        self.set_precedence(_Precedence.EXPR, node.value)
        self.traverse(node.value)

    def visit_Ellipsis(self, node):
        self.write("...")

    def visit_Slice(self, node):
        # rule:slice
        if node.lower:
            self.traverse(node.lower)
        else:
            self.write("0")
        if node.upper:
            self.write("..<")
            self.traverse(node.upper)
            # negative upper bound is not allowed, also not literals
        else:
            self.write("..^1")
        if node.step:
            self.write(":")
            self.traverse(node.step)

    @staticmethod
    def _case_assign_target(node):
        """rule:caseassign -> the name every branch of match `node` assigns last (a branch may instead end
        with a raise or a call that doesn't return, like raiseAssert), with the ids of those assignments;
        None if the match is an ordinary case statement."""
        name, assigns = None, set()
        for case in node.cases:
            last = case.body[-1]
            if isinstance(last, Assign) and len(last.targets) == 1 and isinstance(last.targets[0], Name):
                if name not in (None, last.targets[0].id):
                    return None
                name = last.targets[0].id
                assigns.add(id(last))
            elif not (isinstance(last, Raise) or isinstance(last, Expr) and isinstance(last.value, Call)):
                return None
        return (name, assigns) if name else None

    def visit_Match(self, node):
        # rule:caseassign
        if self._context_stack and self._context_stack[-1] in ("var", "let", "const") \
                and (target := self._case_assign_target(node)):
            name, assigns = target
            self.fill(self._adjust_name(name, definition=self._scope_depth == 0) + " = ")
            self._case_assign_values.append(assigns)
            self.write("case ")
            self.traverse(node.subject)
            self._match_subjects.append(node.subject)
            with self.block(start=""):
                for case in node.cases:
                    self.traverse(case)
            self._match_subjects.pop()
            self._case_assign_values.pop()
            return
        # rule:matchcase
        self.fill("case ")
        self.traverse(node.subject)
        self._match_subjects.append(node.subject)
        with self.block():
            for case in node.cases:
                self.traverse(case)
        self._match_subjects.pop()

    @staticmethod
    def _case_labels(guard, subject):
        """rule:matchcase -> the `of` labels of a guard `subject in inrange(a, b) or subject == v ...`,
        or None if the guard is another condition (an `elif` branch of the case)."""
        terms = guard.values if isinstance(guard, BoolOp) and isinstance(guard.op, Or) else [guard]
        labels = []
        for term in terms:
            if not (isinstance(term, Compare) and len(term.ops) == 1
                    and ast.dump(term.left) == ast.dump(subject)):
                return None
            op, value = term.ops[0], term.comparators[0]
            if isinstance(op, In):  # a range `inrange(a, b)` or a set constant (`routineDefs`, `{a, b}`)
                labels.append(value)
            elif isinstance(op, Eq):
                labels.append(value)
            else:
                return None
        return labels

    def visit_arg(self, node):
        _name = self._adjust_name(node.arg, definition=False) # rule:localname
        self.write(_name)
        if node.annotation:
            self.write(": ")
            self._write_annotation(node.annotation)

    def _write_annotation(self, ann):
        """Parameter or return type annotation; `mut @ T` is written as `var T`."""
        # rule:funcdefmut, check if annotated as mutable "mut @"
        if isinstance(ann, BinOp) and isinstance(ann.op, MatMult) and \
            isinstance(ann.left, Name) and ann.left.id in ("mut", "out"):
            self.write("var " if ann.left.id == "mut" else "out ")  # rule:funcdefmut, rule:funcdefout
            self.traverse(ann.right)
        else:
            self.traverse(ann)

    @staticmethod
    def _is_block_param_placeholder(arg, default) -> bool:
        """rule:blockparam -> `body: typed = None`: a block (typed/untyped) parameter after defaulted
        parameters needs a default in Python only; Nim block parameters have none."""
        ann = arg.annotation
        return (isinstance(ann, Name) and ann.id in ("typed", "untyped")
                and isinstance(default, Constant) and default.value is None)

    def visit_arguments(self, node):
        first = True
        # normal arguments
        all_args = node.posonlyargs + node.args
        defaults = [None] * (len(all_args) - len(node.defaults)) + node.defaults
        for index, elements in enumerate(zip(all_args, defaults), 1):
            a, d = elements
            if first:
                first = False
            else:
                self.write(", ")
            self.traverse(a)
            if d and not self._is_block_param_placeholder(a, d):
                self.write("=")
                self.traverse(d)
            if index == len(node.posonlyargs):
                self.write(", /")

        # varargs, or bare '*' if no varargs but keyword-only arguments present
        if node.vararg or node.kwonlyargs:
            if first:
                first = False
            else:
                self.write(", ")
            if node.vararg:
                # rule:varargs -> `*args: T` is `args: varargs[T]`; `*args: varargs[string, str]` keeps the
                # conversion: `args: varargs[string, `$`]`
                self.write(node.vararg.arg + ": ")
                ann = node.vararg.annotation
                if ann is None:
                    raise ValueError(f"varargs parameter '*{node.vararg.arg}' needs an element type annotation")
                if isinstance(ann, Subscript) and isinstance(ann.value, Name) and ann.value.id == "varargs":
                    elts = ann.slice.elts if isinstance(ann.slice, Tuple) else [ann.slice]
                    self.write("varargs[")
                    self.traverse(elts[0])
                    for conv in elts[1:]:
                        self.write(", ")
                        if isinstance(conv, Name) and conv.id in self._func_rename:
                            self.write(f"`{self._func_rename[conv.id]}`")
                        else:
                            self.traverse(conv)
                    self.write("]")
                else:
                    self.write("varargs[")
                    self.traverse(ann)
                    self.write("]")
            else:
                self.write("*")

        # keyword-only arguments
        if node.kwonlyargs:
            for a, d in zip(node.kwonlyargs, node.kw_defaults):
                self.write(", ")
                self.traverse(a)
                if d:
                    self.write("=")
                    self.traverse(d)

        # kwargs
        if node.kwarg:
            if first:
                first = False
            else:
                self.write(", ")
            self.write("**" + node.kwarg.arg)
            if node.kwarg.annotation:
                self.write(": ")
                self.traverse(node.kwarg.annotation)

    def visit_keyword(self, node):
        if node.arg is None:
            self.write("**")
        else:
            self.write(self._adjust_name(node.arg, definition=False))  # rule:localname, a private field/param
            # rule:instantiation
            if self._context_stack and self._context_stack[-1] == "instance":
                self.write(": ")
            else:
                self.write("=")
        self.traverse(node.value)

    def visit_Lambda(self, node):
        with self.require_parens(_Precedence.TEST, node):
            self.write("lambda")
            with self.buffered() as buffer:
                self.traverse(node.args)
            if buffer:
                self.write(" ", *buffer)
            self.write(": ")
            self.set_precedence(_Precedence.TEST, node.body)
            self.traverse(node.body)

    def visit_alias(self, node):
        # rule:modulepath -> nimic.x.y -> x/y, with module renaming
        name = node.name
        name_split = name.split(".")
        if name_split[0] == "nimic":
            if name_split[1] in self._module_rename:
                name_split[1] = self._module_rename[name_split[1]]
            name = "/".join(name_split[1:])
        self.write(name)
        if node.asname:
            self.write(" as " + node.asname)

    def visit_withitem(self, node):
        self.traverse(node.context_expr)
        if node.optional_vars:
            self.write(" as ")
            self.traverse(node.optional_vars)

    def visit_match_case(self, node):
        # rule:matchcase
        wildcard = isinstance(node.pattern, MatchAs) and node.pattern.name is None and node.pattern.pattern is None
        if wildcard and node.guard is not None and self._match_subjects:
            # `case _ if c in inrange(a, b) or c == v:` -> `of a .. b, v:`; another guard -> `elif cond:`
            labels = self._case_labels(node.guard, self._match_subjects[-1])
            if labels is not None:
                self.fill("of ")
                self.interleave(lambda: self.write(", "), self.traverse, labels)
            else:
                self.fill("elif ")
                self.traverse(node.guard)
            with self.block():
                self.traverse(node.body)
            return
        if wildcard:
            self.fill("else")
        else:
            self.fill("of ")
            self.traverse(node.pattern)

        if node.guard:
            self.write(" if ")
            self.traverse(node.guard)
        with self.block():
            self.traverse(node.body)

    def visit_MatchValue(self, node):
        self.traverse(node.value)

    def visit_MatchSingleton(self, node):
        self._write_constant(node.value)

    def visit_MatchSequence(self, node):
        with self.delimit("[", "]"):
            self.interleave(
                lambda: self.write(", "), self.traverse, node.patterns
            )

    def visit_MatchStar(self, node):
        name = node.name
        if name is None:
            name = "_"
        self.write(f"*{name}")

    def visit_MatchMapping(self, node):
        def write_key_pattern_pair(pair):
            k, p = pair
            self.traverse(k)
            self.write(": ")
            self.traverse(p)

        with self.delimit("{", "}"):
            keys = node.keys
            self.interleave(
                lambda: self.write(", "),
                write_key_pattern_pair,
                zip(keys, node.patterns, strict=True),
            )
            rest = node.rest
            if rest is not None:
                if keys:
                    self.write(", ")
                self.write(f"**{rest}")

    def visit_MatchClass(self, node):
        self.set_precedence(_Precedence.ATOM, node.cls)
        self.traverse(node.cls)
        with self.delimit("(", ")"):
            patterns = node.patterns
            self.interleave(
                lambda: self.write(", "), self.traverse, patterns
            )
            attrs = node.kwd_attrs
            if attrs:
                def write_attr_pattern(pair):
                    attr, pattern = pair
                    self.write(f"{attr}=")
                    self.traverse(pattern)

                if patterns:
                    self.write(", ")
                self.interleave(
                    lambda: self.write(", "),
                    write_attr_pattern,
                    zip(attrs, node.kwd_patterns, strict=True),
                )

    def visit_MatchAs(self, node):
        name = node.name
        pattern = node.pattern
        if name is None:
            self.write("_")
        elif pattern is None:
            self.write(node.name)
        else:
            with self.require_parens(_Precedence.TEST, node):
                self.set_precedence(_Precedence.BOR, node.pattern)
                self.traverse(node.pattern)
                self.write(f" as {node.name}")

    def visit_MatchOr(self, node):
        with self.require_parens(_Precedence.BOR, node):
            self.set_precedence(_Precedence.BOR.next(), *node.patterns)
            self.interleave(lambda: self.write(", "), self.traverse, node.patterns)

def _is_private(name):
    return len(name) > 1 and name[0] == "_" and name[1] != "_" and not name[1].isdigit()


def private_name_collisions(tree):
    """rule:localname: a private _x transpiles to x. Returns (line, scope, message) for each place where that
    changes meaning: _x and x bound in one scope (except overloaded procs, or a parameter x shadowed by a
    later _x, as Nim's `let x = f(x)`), or x used as a value after a private value _x is bound (Nim's x would
    then be _x). Calls x(...) are fine: Nim's `var x = x(1)` still calls the proc x afterwards."""
    found = []

    def scan_scope(label, body, params=(), start=(0, 0)):
        bound = {p: ("param", start) for p in params}  # name -> (kind, position after which it is bound)
        used = []  # (name, position) of uses as a value
        callees = set()  # ids of Name nodes called, x(...)

        def bind(name, kind, pos):
            if name not in bound:
                bound[name] = (kind, pos)
            elif kind != bound[name][0] == "proc":  # a proc name also bound as a value
                bound[name] = ("value", bound[name][1])

        for stmt in body:
            end = (stmt.end_lineno, stmt.end_col_offset)
            stack = [stmt]
            while stack:
                n = stack.pop()
                if isinstance(n, (FunctionDef, AsyncFunctionDef)):
                    bind(n.name, "proc", (n.lineno, n.col_offset))
                    a = n.args
                    ps = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
                    ps += [x.arg for x in (a.vararg, a.kwarg) if x]
                    scan_scope("def " + n.name, n.body, ps, (n.lineno, n.col_offset))
                    stack.extend(n.decorator_list + [d for d in a.defaults + a.kw_defaults if d])
                    continue
                if isinstance(n, ClassDef):
                    bind(n.name, "value", (n.lineno, n.col_offset))
                    scan_scope("class " + n.name, n.body, (), (n.lineno, n.col_offset))
                    stack.extend(n.decorator_list + n.bases)
                    continue
                if isinstance(n, Call) and isinstance(n.func, Name):
                    callees.add(id(n.func))
                if isinstance(n, Name):
                    if isinstance(n.ctx, Store):
                        bind(n.id, "value", end)
                    elif id(n) not in callees:
                        used.append((n.id, (n.lineno, n.col_offset)))
                stack.extend(iter_child_nodes(n))
        for name, (kind, pos) in bound.items():
            if not _is_private(name):
                continue
            twin = name[1:]
            if twin in bound:
                twin_kind = bound[twin][0]
                if not (kind == twin_kind == "proc" or twin_kind == "param"):  # overloads; Nim's let x = f(x)
                    found.append((pos[0], label, f"{name} and {twin} are both defined"))
                    continue
            if kind != "proc":
                later = [p for n_, p in used if n_ == twin and p > pos]
                if later:
                    found.append((later[0][0], label, f"{twin} is used after {name}, which transpiles to {twin}"))

    scan_scope("module", tree.body if isinstance(tree, Module) else [tree])
    return sorted(found)


def unparse(ast_obj, type_registry: dict[str, ] | None = None):
    if collisions := private_name_collisions(ast_obj):  # rule:localname
        raise ValueError("private names collide with their Nim names (_x transpiles to x):\n" +
                         "\n".join(f"  line {line} [{scope}]: {msg}" for line, scope, msg in collisions))
    unparser = _Unparser(type_registry=type_registry)
    return unparser.visit(ast_obj), unparser.module_names


_deprecated_globals = {
    name: globals().pop(name)
    for name in ('Num', 'Str', 'Bytes', 'NameConstant', 'Ellipsis')
}

def __getattr__(name):
    if name in _deprecated_globals:
        globals()[name] = value = _deprecated_globals[name]
        warnings._deprecated(
            f"ast.{name}", message=_DEPRECATED_CLASS_MESSAGE, remove=(3, 14)
        )
        return value
    raise AttributeError(f"module 'ast' has no attribute '{name}'")


def main():

    parser = argparse.ArgumentParser(prog='python -m ast')
    parser.add_argument('infile', type=argparse.FileType(mode='rb'), nargs='?',
                        default='-',
                        help='the file to parse; defaults to stdin')
    parser.add_argument('-m', '--mode', default='exec',
                        choices=('exec', 'single', 'eval', 'func_type'),
                        help='specify what kind of code must be parsed')
    parser.add_argument('--no-type-comments', default=True, action='store_false',
                        help="don't add information about type comments")
    parser.add_argument('-a', '--include-attributes', action='store_true',
                        help='include attributes such as line numbers and '
                             'column offsets')
    parser.add_argument('-i', '--indent', type=int, default=3,
                        help='indentation of nodes (number of spaces)')
    args = parser.parse_args()

    with args.infile as infile:
        source = infile.read()
    tree = parse(source, args.infile.name, args.mode, type_comments=args.no_type_comments)
    print(dump(tree, include_attributes=args.include_attributes, indent=args.indent))

if __name__ == '__main__':
    main()
