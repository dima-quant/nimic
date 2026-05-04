"""
nimic ntypesystem
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Core type system for the nimic DSL — imported by ntypes.py, which adds
keywords, builtins, and re-exports everything under a single public API.

Architecture (layers from low-level to high-level):

  Memory layer (ctypes-backed)
    Ntype              — base class wrapping a ctypes buffer + view for value semantics
    NTypeRegistry      — unified registry (types, c_types, variants, max_variants)
    BufferRegistry     — registry of ctypes buffers (shared memory).

  Scalar numerics (NScalar → NInteger / NFloat)
    Fixed-width integers: int8..int64, uint8..uint64, nint
    IEEE-754 floats: float16, float32, float64
    Arithmetic promotion via determine_common_type().
    All arithmetic, comparison, bitwise, in-place, and reflected operators
    are overloaded with proper type promotion and overflow/wrap semantics.

  Structured types (Object)
    Object             — Nim "object"; fields declared via annotations
                         (e.g. x: float64), backed by ctypes.Structure.
    NTuple             — Nim tuple; similar to Object, but with tuple-style unpacking.
    NIntEnum           — Nim integer enum; auto-registers in DICT_OF_TYPES.
    Variant types      — Nim "case object"; detected by the presence of a match/case block.

  Containers
    seq[T]             — Nim's growable sequence; ctypes array + cache.
    UncheckedArray[T]  — Nim's UncheckedArray; pointer-indexed.
    array[n, T]        — Nim's fixed size array.

  Dispatch
    @dispatch          — Nim-style multi-dispatch based on type annotations.
                         Supports concrete types, generic type classes
                         (SomeInteger, SomeFloat), and parameterized generics.
    DispDict/NMetaClass — automatic dispatch for duplicate method names
                          within class bodies (Nim's method overloading).

  Type modifiers
    @distinct          — marks a type alias as distinct; blocks inherited
                         methods unless explicitly borrowed ({.borrow.}).
    @converter         — registers a trivial type conversion (e.g.
                         UnitVector → Vec3). Distinct types with a converter
                         to a parent keep inherited methods. In dispatch,
                         converter-related types match parent signatures
                         directly (same memory layout, no wrapping).
    _n_aliases         — maps Python builtins to Nim native types.

  Utilities
    string             — str subclass with Nim-compatible & (via __and__),
                         isEmpty, and Template-based % formatting.
    copy, <<= (value assignment via __ilshift__)
"""

from __future__ import annotations

import ast
import bisect
import ctypes
import inspect as ins
import operator
import re
import struct
import sys
import textwrap
from enum import IntEnum
from string import Template
from typing import Sequence


# --- NilPtr sentinel ---

class NilPtr:
    """Nil pointer that preserves type information for dispatch.

    When an Object field is declared as ptr[SomeType] but not yet assigned,
    it is initialized as NilPtr("ptr[SomeType]") instead of plain None.
    This allows autorename() to recover the type name for dispatch resolution.
    """
    __slots__ = ('_type_name',)

    @property
    def is_nil(self) -> bool:
        return True

    def __init__(self, type_name: str):
        self._type_name = type_name

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other) -> bool:
        return other is None or isinstance(other, NilPtr)

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(None)

    def __repr__(self) -> str:
        return f"NilPtr({self._type_name!r})"

__resolved__ = {}

__dispatch_generic__ = {}

__dispatch_genericT__ = {}

__tdefs__ = {}

__arg_names__ = {}

# --- Generic Type Classes & Aliases ---

_n_generic_types = {
    "SomeInteger": (
        "nint",
        "int64",
        "uint64",
        "int32",
        "uint32",
        "int16",
        "uint16",
        "int8",
        "uint8",
    ),
    "SomeFloat": ("float64", "float32"),
}

# for now map Python types to native types
# should map from alias directly to native type
_n_aliases = {"float": "float64", "int": "int32", "str": "string", "NBool": "bool",
              "static[bool]": "bool", "static[int]": "int32",
              "static[float]": "float64", "static[str]": "string"}


def get_type_params(fn: callable) -> dict:
    lines = ins.getsource(fn).split("\n")
    for line in lines:
        if "def " in line:
            break
    T_str = line[line.find("[") + 1 : line.find("]")].split(", ")
    T_def = {}
    for expr in T_str:
        expr_sp = expr.split(":")
        if len(expr_sp) == 1:
            T_def[expr_sp[0].strip()] = ""
        else:
            T_def[expr_sp[0].strip()] = expr_sp[1].strip()
    return T_def


def _specialize_generic(fn: callable, T_var: dict[str, str]) -> callable:
    """Create a concrete specialization of a generic function.

    Given a generic function and a mapping of type parameter names to
    resolved type names (e.g. {"T": "int32"}), this function:
      1. Gets the source code of fn
      2. Parses it into an AST
      3. Replaces all occurrences of type parameter names with the
         resolved type names (in annotations, body, and subscripts)
      4. Removes the type parameter brackets from the def line
      5. Compiles and executes the new source in the caller's namespace
      6. Returns the newly created concrete function
    """
    src = ins.getsource(fn)
    src = textwrap.dedent(src)
    # Remove the @dispatch decorator line(s) from source
    lines = src.split("\n")
    filtered = []
    skip_next = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@dispatch") or stripped == "@dispatch":
            continue
        filtered.append(line)
    src = "\n".join(filtered)

    tree = ast.parse(src)
    func_def = tree.body[0]

    # Remove type_params (the [T] bracket) from the function def
    if hasattr(func_def, 'type_params'):
        func_def.type_params = []

    # Build suffix for unique function name
    suffix = "_" + "_".join(T_var.values())
    original_name = func_def.name
    func_def.name = original_name + suffix

    class _TypeReplacer(ast.NodeTransformer):
        """Replace all Name nodes matching type parameter names with resolved types."""
        def visit_Name(self, node):
            if node.id in T_var:
                node.id = T_var[node.id]
            return node

        def visit_Subscript(self, node):
            # Handle cases like seq[T] -> seq[int32]
            self.generic_visit(node)
            return node

        def visit_Attribute(self, node):
            self.generic_visit(node)
            return node

    _TypeReplacer().visit(tree)
    ast.fix_missing_locations(tree)

    # Compile in the caller's namespace
    code = compile(tree, ins.getfile(fn), "exec")
    # Build namespace with access to the module's globals
    ns = fn.__globals__.copy()
    ns.update(DICT_OF_TYPES)
    exec(code, ns)
    specialized_fn = ns[func_def.name]
    # Preserve the original function name for dispatch lookup
    specialized_fn.__qualname__ = original_name + suffix
    return specialized_fn


def autorename(x: object) -> str:
    if isinstance(x, NilPtr):
        return x._type_name
    type_name = type(x).__name__
    if type_name in _n_aliases:
        return _n_aliases[type_name]
    elif type_name == "type" or type_name == "NMetaClass":
        return f"type[{x.__name__}]"
    else:
        return type_name


def _match_generic_pattern(sig_type: str, arg_type: str, T_def: dict) -> dict | None:
    """Try to match arg_type against sig_type containing type variables from T_def.

    Returns dict of {T_name: resolved_type_name} if match succeeds, None otherwise.

    Example:
        _match_generic_pattern("ptr[UncheckedArray[T]]", "ptr[UncheckedArray[uint8]]", {"T": ""})
        → {"T": "uint8"}
    """
    # Find which T variables appear in this sig_type string
    t_vars_in_sig = [t for t in T_def if t in sig_type]
    if not t_vars_in_sig:
        return None

    # Build regex: escape the sig_type, then unescape each T variable
    # and replace it with a capture group that matches a type name
    # (including nested brackets like UncheckedArray[uint8])
    pattern = re.escape(sig_type)
    for t in t_vars_in_sig:
        # Replace the escaped T with a capture group
        pattern = pattern.replace(re.escape(t), r'([A-Za-z_]\w*(?:\[.*?\])?)', 1)

    m = re.fullmatch(pattern, arg_type)
    if m:
        result = {}
        for i, t in enumerate(t_vars_in_sig):
            result[t] = m.group(i + 1)
        return result
    return None


debugG = {}


# --- Multi-Dispatch ---


def _match_subtype(arg_type_name: str, sig_type_name: str) -> bool:
    """Check if arg_type matches sig_type, including subtype relationship.

    Returns True if arg_type_name == sig_type_name, or if the class registered
    for arg_type_name is a subclass of the class registered for sig_type_name.
    """
    if arg_type_name == sig_type_name:
        return True
    arg_cls = DICT_OF_TYPES.get(arg_type_name)
    sig_cls = DICT_OF_TYPES.get(sig_type_name)
    if arg_cls is not None and sig_cls is not None:
        try:
            return issubclass(arg_cls, sig_cls)
        except TypeError:
            return False
    return False


def _match_converter(arg_type_name: str, sig_type_name: str) -> bool:
    """Check if arg_type can be trivially converted to sig_type via __converters__."""
    if arg_type_name == sig_type_name:
        return True
    return sig_type_name in __converters__.get(arg_type_name, set())


def dispatch(fn: callable) -> callable:
    """Decorator implementing Nim-style multi-dispatch based on argument type annotations.

    Registers function signatures in one of three global registries:
      __resolved__          — concrete type signatures (direct match)
      __dispatch_generic__  — signatures using generic type classes (SomeInteger, SomeFloat)
      __dispatch_genericT__ — signatures using parameterized generics [T: constraint]

    The returned wrapper (fn_dispatch) resolves calls at runtime:
    1. Check __resolved__ for an exact match on argument types.
    2. If not found, try __dispatch_generic__ (match arg type against type class tuples).
    3. If not found, try __dispatch_genericT__ (match with type parameter binding).
    4. On successful resolution, cache the result in __resolved__ for future calls.
    5. Raise NotImplementedError if no matching signature is found.
    """
    # No kwargs in dispatched functions. Types should match. TODO: Python types should be treated as literals
    # TODO properly remove prefix
    _annotations = {}
    if (
        fn.__code__.co_varnames
        and fn.__code__.co_varnames[0] == "self"
        and "self" not in fn.__annotations__
    ):
        qualnames = fn.__code__.co_qualname.split(".")
        if len(qualnames) > 1:
            _annotations.update({"self": qualnames[-2]})
    _annotations.update(fn.__annotations__)
    sig_list = [
        v.removeprefix("mut @ ") for k, v in _annotations.items() if k != "return"
    ]
    sig_list = [_n_aliases[v] if v in _n_aliases else v for v in sig_list]
    arg_count = fn.__code__.co_argcount
    arg_names = tuple(k for k in _annotations.keys() if k != "return")

    if not len(sig_list) == arg_count:
        sig_str = ", ".join(sig_list)
        raise Exception(
            f"type not found for all arguments of {fn.__name__}, only the following: {sig_str}"
        )
    generic = any((arg in _n_generic_types for arg in sig_list))
    genericT = len(fn.__type_params__) > 0
    # register signature
    if fn.__name__ not in __arg_names__:
        __arg_names__[fn.__name__] = {}

    if genericT:
        T_def = get_type_params(fn)
        # register T def
        # expand generic types
        sigs = tuple(
            (arg,) if arg not in _n_generic_types else _n_generic_types[arg]
            for arg in sig_list
        )
        if fn.__name__ in __dispatch_genericT__:
            __dispatch_genericT__[fn.__name__][sigs] = fn
            __tdefs__[fn.__name__][sigs] = T_def
        else:
            __dispatch_genericT__[fn.__name__] = {sigs: fn}
            __tdefs__[fn.__name__] = {sigs: T_def}
        __arg_names__[fn.__name__][sigs] = arg_names
    elif generic:
        # expand generic types
        sigs = tuple(
            (arg,) if arg not in _n_generic_types else _n_generic_types[arg]
            for arg in sig_list
        )
        if fn.__name__ in __dispatch_generic__:
            __dispatch_generic__[fn.__name__][sigs] = fn
        else:
            __dispatch_generic__[fn.__name__] = {sigs: fn}
        __arg_names__[fn.__name__][sigs] = arg_names
    else:
        sigs = tuple((arg,) for arg in sig_list)
        if fn.__name__ in __resolved__:
            __resolved__[fn.__name__][sigs] = fn
        else:
            __resolved__[fn.__name__] = {sigs: fn}
        __arg_names__[fn.__name__][sigs] = arg_names

    def fn_dispatch(*args, **kwargs):
        if kwargs:
            possible_sigs = __arg_names__.get(fn.__name__, {})
            candidate_args_list = []
            for sig_def, p_arg_names in possible_sigs.items():
                if len(args) + len(kwargs) == len(p_arg_names):
                    expected_kw_names = p_arg_names[len(args):]
                    if set(expected_kw_names) == set(kwargs.keys()):
                        full_args = list(args)
                        for name in expected_kw_names:
                            full_args.append(kwargs[name])
                        test_args = tuple(full_args)
                        test_fn_sig = tuple((autorename(arg),) for arg in test_args)

                        is_match = False
                        nm = fn.__name__
                        if nm in __resolved__ and sig_def in __resolved__[nm] and test_fn_sig == sig_def:
                            is_match = True
                        elif nm in __dispatch_generic__ and sig_def in __dispatch_generic__[nm]:
                            if len(test_fn_sig) == len(sig_def) and all(test_fn_sig[i][0] in sig_def[i] for i in range(len(test_fn_sig))):
                                is_match = True
                        elif nm in __dispatch_genericT__ and sig_def in __dispatch_genericT__[nm]:
                            is_match = True

                        if is_match and test_args not in candidate_args_list:
                            candidate_args_list.append(test_args)
            if not candidate_args_list:
                raise TypeError(f"Invalid keyword arguments for {fn.__name__}")

            for cand in candidate_args_list:
                try:
                    return fn_dispatch(*cand)
                except NotImplementedError:
                    pass
            raise NotImplementedError(f"Function not defined for keyword signature: {fn.__name__}")

        sigs = ((autorename(arg),) for arg in args)
        fn_sig = tuple(sigs)
        is_resolved = (
            fn.__name__ in __resolved__ and fn_sig in __resolved__[fn.__name__]
        )
        if is_resolved:
            return __resolved__[fn.__name__][fn_sig](*args)
        else:
            # try to resolve signature
            allow_subtype_matching = False
            if fn.__name__ in __dispatch_generic__:
                sig_defs = __dispatch_generic__[fn.__name__]
                for sig_def in sig_defs:
                    if len(fn_sig) == len(sig_def):
                        i = 0
                        while i < len(fn_sig) and fn_sig[i][0] in sig_def[i]:
                            i += 1
                        if i == len(fn_sig):
                            if fn.__name__ in __resolved__:
                                __resolved__[fn.__name__][fn_sig] = sig_defs[sig_def]
                            else:
                                __resolved__[fn.__name__] = {fn_sig: sig_defs[sig_def]}
                            break
            if fn.__name__ in __dispatch_genericT__:
                sig_defs = __dispatch_genericT__[fn.__name__]
                # Collect all matching candidates with specificity scores.
                # Higher specificity = more specific match.
                # compound pattern match (Case C) > bare T match (Case B) > exact match (Case A)
                best_match = None  # (specificity, sig_def, T_var)
                for sig_def in sig_defs:
                    if len(fn_sig) == len(sig_def):
                        i = 0
                        T_var = {}
                        T_def = __tdefs__[fn.__name__][sig_def]
                        specificity = 0  # sum of per-position specificity
                        while i < len(fn_sig):
                            arg_name = fn_sig[i][0]
                            sig_name = sig_def[i][0]
                            if arg_name in sig_def[i]:
                                # Case A: exact match (specificity 0)
                                pass
                            elif sig_name in T_def:
                                # Case B: bare type variable (specificity 1)
                                T_sym = sig_name
                                T_value = arg_name
                                if T_sym in T_var:
                                    if T_var[T_sym] != T_value:
                                        break
                                else:
                                    constraint = T_def[T_sym]
                                    if len(constraint) == 0:
                                        T_var[T_sym] = T_value
                                    elif constraint.startswith("not "):
                                        excluded = constraint[4:].strip()
                                        if T_value == excluded:
                                            break
                                        T_var[T_sym] = T_value
                                    elif T_value == constraint:
                                        T_var[T_sym] = T_value
                                    elif (
                                        constraint in _n_generic_types
                                        and T_value in _n_generic_types[constraint]
                                    ):
                                        T_var[T_sym] = T_value
                                    else:
                                        break
                                specificity += 1
                            else:
                                # Case C: compound type pattern (specificity 2)
                                matched = _match_generic_pattern(sig_name, arg_name, T_def)
                                if matched is not None:
                                    conflict = False
                                    for t_sym, t_val in matched.items():
                                        if t_sym in T_var:
                                            if T_var[t_sym] != t_val:
                                                conflict = True
                                                break
                                        else:
                                            constraint = T_def[t_sym]
                                            if len(constraint) == 0:
                                                T_var[t_sym] = t_val
                                            elif constraint.startswith("not "):
                                                excluded = constraint[4:].strip()
                                                if t_val == excluded:
                                                    conflict = True
                                                    break
                                                T_var[t_sym] = t_val
                                            elif t_val == constraint:
                                                T_var[t_sym] = t_val
                                            elif (
                                                constraint in _n_generic_types
                                                and t_val in _n_generic_types[constraint]
                                            ):
                                                T_var[t_sym] = t_val
                                            else:
                                                conflict = True
                                                break
                                    if conflict:
                                        break
                                    specificity += 2
                                else:
                                    break
                            i += 1
                        if i == len(fn_sig):
                            if best_match is None or specificity > best_match[0]:
                                best_match = (specificity, sig_def, T_var)
                if best_match is not None:
                    _, best_sig_def, best_T_var = best_match
                    generic_fn = sig_defs[best_sig_def]
                    specialized = _specialize_generic(generic_fn, best_T_var)
                    if fn.__name__ in __resolved__:
                        __resolved__[fn.__name__][fn_sig] = specialized
                    else:
                        __resolved__[fn.__name__] = {fn_sig: specialized}
        is_resolved = (
            fn.__name__ in __resolved__ and fn_sig in __resolved__[fn.__name__]
        )
        if not is_resolved:
            # try converter matching (trivial/same-layout conversions only)
            if fn.__name__ in __resolved__:
                for sig_def, sig_fn in __resolved__[fn.__name__].items():
                    if len(fn_sig) == len(sig_def):
                        if all(
                            _match_converter(fn_sig[i][0], sig_def[i][0])
                            for i in range(len(fn_sig))
                        ):
                            __resolved__[fn.__name__][fn_sig] = sig_fn
                            is_resolved = True
                            break
        if not is_resolved and allow_subtype_matching:
            # try subtype matching against all registered concrete signatures
            if fn.__name__ in __resolved__:
                for sig_def, sig_fn in __resolved__[fn.__name__].items():
                    if len(fn_sig) == len(sig_def):
                        if all(
                            _match_subtype(fn_sig[i][0], sig_def[i][0])
                            for i in range(len(fn_sig))
                        ):
                            __resolved__[fn.__name__][fn_sig] = sig_fn
                            is_resolved = True
                            break
        if is_resolved:
            return __resolved__[fn.__name__][fn_sig](*args)
        else:
            sig_str = ", ".join([sig[0] for sig in fn_sig])
            raise NotImplementedError(
                f"Function not defined for signature: {fn.__name__}({sig_str})"
            )

    # for debugging save in visible debugG
    for nm in __resolved__:
        debugG[nm] = __resolved__[nm].copy()
    return fn_dispatch


# --- Converter Registry ---

# Maps source_type_name → set of target_type_names
__converters__ = {}


def converter(fn: callable) -> callable:
    """Decorator that registers an implicit type conversion function.

    Inspects the function's annotations to extract the source type
    (first parameter) and target type (return annotation), then
    registers the pair in __converters__. Types related by a converter
    keep inherited methods even when @distinct is applied.
    """
    annotations = fn.__annotations__
    params = [v for k, v in annotations.items() if k != "return"]
    ret = annotations.get("return", None)
    if params and ret:
        source = (
            params[0]
            if isinstance(params[0], str)
            else getattr(params[0], "__name__", None)
        )
        target = ret if isinstance(ret, str) else getattr(ret, "__name__", None)
        if source and target:
            if source in __converters__:
                __converters__[source].add(target)
            else:
                __converters__[source] = {target}
    return fn


# Methods that should never be blocked by @distinct
_DISTINCT_KEEP = frozenset(
    {
        "__init__",
        "__init_subclass__",
        "__new__",
        "__del__",
        "__class__",
        "__dict__",
        "__doc__",
        "__module__",
        "__weakref__",
        "__repr__",
        "__str__",
        "__hash__",
        "__sizeof__",
        "__reduce__",
        "__reduce_ex__",
        "__getattribute__",
        "__setattr__",
        "__delattr__",
        "__dir__",
        "__format__",
        "__subclasshook__",
        "__class_getitem__",
        "__get__",
        "__set__",
        "__delete__",
        "__copy__",
        "__float__",
        "__int__",
        "__str__",
        "__bool__",
    }
)


def _make_blocker(cls_name: str, method_name: str) -> callable:
    """Create a method that raises AttributeError for blocked distinct operations."""

    def blocked(self, *args, **kwargs):
        raise AttributeError(
            f"'{cls_name}' is a distinct type — "
            f"'{method_name}' is not borrowed from parent"
        )

    return blocked


def distinct(cls: type) -> type:
    """Mark a type as distinct from its parent.

    Removes the type from _n_aliases and blocks inherited methods
    not explicitly re-declared in the class body. Internal _n_* methods
    and Python object protocol methods are never blocked.

    If a @converter exists from this type to a parent type, inherited
    methods are preserved (implicit conversion makes them accessible).
    """
    if cls.__name__ in _n_aliases:
        del _n_aliases[cls.__name__]

    # Check if a converter relates this type to any parent — if so,
    # keep all inherited methods (implicit conversion path exists)
    converter_targets = __converters__.get(cls.__name__, set())
    parent_names = {base.__name__ for base in cls.__mro__[1:]}
    if converter_targets & parent_names:
        return cls

    # Collect methods explicitly declared in this class body
    own_methods = set(cls.__dict__.keys())

    # Block inherited methods not re-declared in this class
    for base in cls.__mro__[1:]:
        if (
            base is object
            or base is Ntype
            or base is Object
            or base.__name__ in __native_types__
        ):
            break
        for name, attr in base.__dict__.items():
            if not callable(attr) and not isinstance(attr, (classmethod, staticmethod)):
                continue
            if name in own_methods:
                continue  # explicitly re-declared — keep it
            if name.startswith("_n_"):
                continue  # internal infrastructure
            if name in _DISTINCT_KEEP:
                continue  # Python object protocol
            setattr(cls, name, _make_blocker(cls.__name__, name))

    return cls


class NTypeRegistry:
    """Centralized registry for all nimic type information.

    Consolidates DICT_OF_TYPES, DICT_OF_C_TYPES, DICT_OF_VARIANTS,
    and DICT_OF_MAX_VARIANTS into a single object.
    """

    def __init__(self) -> None:
        self.types = {}  # name → Python class
        self.c_types = {}  # name → ctypes struct type
        self.variants = {}  # name → {kind_val: {field: type_name, ...}, ...}
        self.max_variants = {}  # name → kind_val of largest variant

    def get_or_eval_type(self, t_name: str, caller_globals: dict | None = None) -> type:
        if t_name in self.types:
            return self.types[t_name]
        # t_name is not in self.types, so needs to be resolved and registered.
        if "[" in t_name and t_name.endswith("]"):
            base, params = t_name[:-1].split("[", 1)
            if base == "array":
                n_str, _ntype = params.split(",", 1)
                # eval with caller's globals, so module-level constants are resolved
                eval_ns = dict(self.types)
                if caller_globals:
                    eval_ns.update(caller_globals)
                if n_str in eval_ns:
                    n = eval_ns[n_str]
                elif n_str.isdigit():
                    n = int(n_str)
                else:
                    n = eval(n_str, eval_ns)
                canonic_arr_name = f"array[{n}, {_ntype.strip()}]"
                if canonic_arr_name in self.types:
                    return self.types[canonic_arr_name]
                resolved = self.types[base][(n, self.get_or_eval_type(_ntype.strip(), caller_globals))]
                resolved._n_register_type()  # should be performed in __class_getitem__
                return resolved
            else:
                resolved = self.types[base][self.get_or_eval_type(params.strip(), caller_globals)]
                resolved._n_register_type()  # should be performed in __class_getitem__
                return resolved
        raise NameError(f"Type '{t_name}' not found")

_n_registry = NTypeRegistry()

# Backward-compatible aliases — these point to the same dict objects
DICT_OF_TYPES = _n_registry.types
DICT_OF_C_TYPES = _n_registry.c_types
DICT_OF_VARIANTS = _n_registry.variants
DICT_OF_MAX_VARIANTS = _n_registry.max_variants

# --- Base Memory Type (Ntype) ---


class BufferRegistry:
    """Central registry of all live ctypes buffers.

    Every ctypes allocation (Object structs, seq arrays, c_malloc, etc.)
    is registered here by its start address.  The registry keeps a strong
    reference so the buffer stays alive as long as it is registered.

    Address → (buffer_object, size_in_bytes)

    Sorting is lazy: the sorted address list is rebuilt only when
    ``find_buffer_for_address`` is called after mutations, since
    registrations vastly outnumber lookups in the pipeline.
    """

    def __init__(self):
        # Maps start_address → (buffer_object, size_in_bytes)
        self._buffers: dict[int, tuple[object, int]] = {}
        # Sorted cache — rebuilt lazily on lookup when _dirty is True
        self._sorted_addresses: list[int] = []
        self._dirty: bool = False

    # -- core API --

    def register(self, buffer_obj) -> int:
        """Register a ctypes buffer.  Returns its start address.  O(1)."""
        start_addr = ctypes.addressof(buffer_obj)
        size = ctypes.sizeof(buffer_obj)
        if start_addr not in self._buffers:
            self._dirty = True
        self._buffers[start_addr] = (buffer_obj, size)
        return start_addr

    def _ensure_sorted(self):
        """Rebuild the sorted address list if mutations have occurred."""
        if self._dirty:
            self._sorted_addresses = sorted(self._buffers.keys())
            self._dirty = False

    def find_buffer_for_address(self, query_addr: int):
        """Return the buffer object whose memory range contains *query_addr*,
        or ``None`` if no registered buffer covers that address.  O(log N)."""
        self._ensure_sorted()
        if not self._sorted_addresses:
            return None
        index = bisect.bisect_right(self._sorted_addresses, query_addr) - 1
        if index < 0:
            return None
        start_addr = self._sorted_addresses[index]
        buffer_obj, size = self._buffers[start_addr]
        if start_addr <= query_addr < (start_addr + size):
            return buffer_obj
        return None

    def update(self, old_addr: int, buffer_obj) -> int:
        """Re-register *buffer_obj* after a ``ctypes.resize``.

        If the address changed (``ctypes.resize`` may reallocate), the old
        entry is removed and a new one inserted.  Returns the new address.
        """
        new_addr = ctypes.addressof(buffer_obj)
        new_size = ctypes.sizeof(buffer_obj)
        if old_addr != new_addr:
            # address moved — remove old key
            if old_addr in self._buffers:
                del self._buffers[old_addr]
            self._buffers[new_addr] = (buffer_obj, new_size)
            self._dirty = True
        else:
            # same address, just update size
            self._buffers[old_addr] = (buffer_obj, new_size)
        return new_addr

    def free(self, buffer_or_addr) -> bool:
        """Unregister a buffer (by object or address).

        Drops the strong reference so the ctypes buffer becomes GC-eligible.
        Returns ``True`` if it was found, ``False`` otherwise.
        """
        if isinstance(buffer_or_addr, int):
            addr = buffer_or_addr
        else:
            addr = ctypes.addressof(buffer_or_addr)
        if addr in self._buffers:
            del self._buffers[addr]
            self._dirty = True
            return True
        return False

    def unregister(self, buffer_obj):
        """Legacy alias for ``free``."""
        return self.free(buffer_obj)

    # -- introspection --

    def __contains__(self, addr: int) -> bool:
        return addr in self._buffers

    def __len__(self) -> int:
        return len(self._buffers)

    def __repr__(self) -> str:
        return f"BufferRegistry({len(self._buffers)} buffers)"


BUFFER_REGISTRY = BufferRegistry()

class Ntype:
    _n_view: object = None  # ctypes view of the memory
    _n_type: type  # type of the value

    def __init__(self) -> None:
        self._n_view = None
        self._n_type = None

    @classmethod
    def _n_on_struct(cls, buffer: object, name: str, value: object) -> Ntype:
        raise NotImplementedError

    @classmethod
    def _n_on_array(cls, buffer: object, name: str, value: object) -> Ntype:
        raise NotImplementedError

    def _n_get_value(self) -> object:
        raise NotImplementedError

    def _n_set_value(self, value: object) -> None:
        raise NotImplementedError



# --- Integer Enums (NIntEnum) ---


class NIntEnum(IntEnum):
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._n_register_type()

    @classmethod
    def _n_set_indices(cls) -> None:
        cls._n_members_tuple = tuple(cls)
        cls._n_indices = {val: ind for ind, val in enumerate(cls._n_members_tuple)}

    @classmethod
    def _n_on_struct(
        cls, parent_elems: ctypes.Structure, id: str, enum_value: int | None = None
    ) -> NIntEnum:
        get_value = lambda: getattr(parent_elems, id)
        set_value = lambda value: setattr(parent_elems, id, value)
        if enum_value is not None:
            value = int(enum_value)
        else:
            value = get_value()
        inst = cls(value)
        inst._n_get_value = get_value
        inst._n_set_value = set_value
        if enum_value is not None:
            inst._n_set_value(value)
        return inst

    @classmethod
    def _n_register_type(cls) -> None:
        cls._n_set_indices()
        DICT_OF_TYPES[cls.__name__] = cls
        DICT_OF_C_TYPES[cls.__name__] = ctypes.c_uint64


class NBool:
    """ctypes-backed bool — harmonizes with NScalar pattern for struct embedding."""

    def __init__(self, value=False):
        self._value = bool(value)

    def _n_get_value(self):
        return self._value

    def _n_set_value(self, value):
        if isinstance(value, NBool):
            self._value = value._value
        else:
            self._value = bool(value)

    def __int__(self):
        return int(self._value)

    def __float__(self):
        return float(self._value)

    def __bool__(self):
        return self._value

    def __repr__(self):
        return repr(self._value)

    def __eq__(self, other):
        if isinstance(other, NBool):
            return self._value == other._value
        return self._value == other

    @classmethod
    def _n_on_struct(cls, parent_elems, id, value=None):
        """Struct-embedded: reads/writes via ctypes struct field."""
        self = cls.__new__(cls)
        # Bind to parent struct field
        self._n_get_value = lambda: bool(getattr(parent_elems, id))
        self._n_set_value = lambda v: setattr(parent_elems, id, bool(v._value if isinstance(v, NBool) else v))
        self._value = bool(getattr(parent_elems, id))
        if value is not None:
            self._n_set_value(value)
        # Override _value property to always read from struct
        self.__class__ = type('NBool_bound', (NBool,), {
            '_value': property(
                lambda s: bool(getattr(parent_elems, id)),
                lambda s, v: setattr(parent_elems, id, bool(v))
            )
        })
        return self

    @classmethod
    def _n_on_array(cls, parent_elems, index, value=None):
        """Array-embedded: reads/writes via ctypes array slot."""
        self = cls.__new__(cls)
        self._n_get_value = lambda: bool(parent_elems[index])
        self._n_set_value = lambda v: parent_elems.__setitem__(index, bool(v._value if isinstance(v, NBool) else v))
        self._value = bool(parent_elems[index])
        if value is not None:
            self._n_set_value(value)
        self.__class__ = type('NBool_bound', (NBool,), {
            '_value': property(
                lambda s: bool(parent_elems[index]),
                lambda s, v: parent_elems.__setitem__(index, bool(v))
            )
        })
        return self

    @classmethod
    def _n_sizeof(cls):
        return ctypes.sizeof(ctypes.c_bool)


# --- Dispatch Metaclass (DispDict / NMetaClass) ---


class DispDict(dict):
    def __setitem__(self, key: str, fn: callable) -> None:
        # apply dispatch to all duplicate methods within a class definition
        if key in self:
            if key == self[key].__name__:
                # not yet overloaded
                dispatch(self[key])
            if key == fn.__name__:
                # not yet overloaded
                super().__setitem__(key, dispatch(fn))
        else:
            super().__setitem__(key, fn)


class NMetaClass(type):
    @classmethod
    def __prepare__(mcs, name: str, bases: tuple) -> DispDict:
        return DispDict()


# --- Structured Objects (Object) ---

class _Object(Ntype):
    # Cache for specialized generic classes
    _n_specializations = {}

    def __class_getitem__(cls, params) -> type:
        """Create a specialized subclass with resolved type annotations.

        E.g. ChannelDescriptor[uint8] creates a subclass where
        buffer: ptr[UncheckedArray[T]] becomes buffer: ptr[UncheckedArray[uint8]].
        """
        type_params = getattr(cls, '__type_params__', ())
        if not type_params:
            return cls

        # Normalize params to tuple
        if not isinstance(params, tuple):
            params = (params,)

        # Build T_name → concrete_name mapping
        T_map = {}
        for tp, concrete in zip(type_params, params):
            if isinstance(concrete, str):
                T_map[tp.__name__] = concrete
            elif hasattr(concrete, '__name__'):
                T_map[tp.__name__] = concrete.__name__
            else:
                T_map[tp.__name__] = str(concrete)

        # Cache key
        cache_key = (cls, tuple(T_map.items()))
        if cache_key in _Object._n_specializations:
            return _Object._n_specializations[cache_key]

        # Resolve annotations by replacing type variable names
        resolved = {}
        for attr_name, type_str in cls.__annotations__.items():
            new_str = type_str
            for t_name, t_concrete in T_map.items():
                new_str = new_str.replace(t_name, t_concrete)
            resolved[attr_name] = new_str

        # Create specialized subclass
        suffix = "_".join(T_map.values())
        specialized_name = f"{cls.__name__}[{suffix}]"
        specialized = type(specialized_name, (cls,), {'__annotations__': resolved})
        specialized._n_register_type()
        _Object._n_specializations[cache_key] = specialized
        return specialized

    @property
    def is_nil(self) -> bool:
        """Nim: isNil — check if pointer-type object is nil."""
        return getattr(self, '_n_view', None) is None

    @classmethod
    def _n_ptr_cast(cls, instance: pointer | ByteAddress) -> pointer:
        """Cast raw pointer/memory to this Object type."""
        if isinstance(instance, NilPtr) or instance is None:
            return NilPtr(cls.__name__)
        if isinstance(instance, pointer):
            if instance._n_addr == 0:
                return NilPtr(cls.__name__)
            address = instance._n_addr
        elif isinstance(instance, ByteAddress):
            address = _resolve_addr(instance)
            if address == 0:
                return NilPtr(cls.__name__)
        else:
            address = ctypes.addressof(instance)
        # Create Object backed by this memory
        class_name = cls.__name__
        if class_name in DICT_OF_C_TYPES:
            c_type = DICT_OF_C_TYPES[class_name]
            c_instance = c_type.from_address(address)
            obj = cls.__new__(cls)
            obj._n_view = c_instance
            obj._n_annotations = cls.__annotations__
            obj._n_fields = list(cls.__annotations__.keys())
            obj._n_setup(None)
            return obj
        return instance

    @classmethod
    def cast(cls, instance):
        """Cast generic memory/object to this Object type."""
        if isinstance(instance, NilPtr) or instance is None:
            return NilPtr(cls.__name__)
        if isinstance(instance, pointer):
            if instance._n_addr == 0:
                return NilPtr(cls.__name__)
            address = instance._n_addr
        elif isinstance(instance, ByteAddress):
            address = _resolve_addr(instance)
            if address == 0:
                return NilPtr(cls.__name__)
        elif hasattr(instance, '_n_view') and getattr(instance, '_n_view') is not None:
            address = ctypes.addressof(instance._n_view)
        else:
            address = ctypes.addressof(instance)

        class_name = cls.__name__
        if class_name in DICT_OF_C_TYPES:
            c_type = DICT_OF_C_TYPES[class_name]
            c_instance = c_type.from_address(address)
            obj = cls.__new__(cls)
            obj._n_view = c_instance
            if hasattr(instance, '_n_buffer'):
                obj._n_buffer = instance._n_buffer
            obj._n_annotations = cls.__annotations__
            obj._n_fields = list(cls.__annotations__.keys())
            obj._n_setup(None)
            return obj
        return instance

    def __init__(self, _n_value: Object | None = None, **kwargs: object) -> None:
        """_n_value is an instance of Object or an object with the same structure or None"""
        python_fields = getattr(self.__class__, '_n_python_fields', set())
        field_types = getattr(self.__class__, '_n_field_types', {})
        _seq = DICT_OF_TYPES.get("seq")
        # Initialize python-side fields (seq and Object subclasses without ctypes backing)
        for name in python_fields:
            fc = field_types.get(name)
            if fc is not None and isinstance(fc, type):
                if _seq and issubclass(fc, _seq):
                    setattr(self, name, fc())
                elif issubclass(fc, _Object):
                    setattr(self, name, fc())
        _has_c_type = type(self).__name__ in DICT_OF_C_TYPES
        if kwargs:
            for attribute in kwargs:
                setattr(self, attribute, kwargs[attribute])
            attributes = list(kwargs.keys())
            self._n_fields = attributes
            value = self
        else:
            value = _n_value
        if _has_c_type:
            class_name = type(self).__name__
            if value and isinstance(value, Object) and not kwargs:
                self._n_view = value._n_get_value()
            else:
                _buf = DICT_OF_C_TYPES[class_name]()
                self._n_owned_addr = BUFFER_REGISTRY.register(_buf)
                self._n_view = _buf
            self._n_setup(value)
        else:
            # No ctypes backing — still need _n_fields for attribute access
            if not kwargs:
                self._n_fields = list(self.__annotations__)
                self._n_annotations = self.__annotations__

    @classmethod
    def _n_on_array(
        cls, parent_elems: object, id: int, value: Object | None = None
    ) -> Object:
        self = cls.__new__(cls)
        self._n_view = parent_elems[id]
        self._n_setup(value)
        return self

    def __del__(self):
        addr = getattr(self, '_n_owned_addr', None)
        if addr is not None:
            BUFFER_REGISTRY.free(addr)

    @classmethod
    def _n_on_struct(
        cls, parent_elems: object, id: str, value: Object | None = None
    ) -> Object:
        self = cls.__new__(cls)
        self._n_view = getattr(parent_elems, id)
        self._n_setup(value)
        return self

    def _n_setup(self, value: Object | None = None) -> None:
        """Initialize object fields after construction.

        Detects variant types (objects with a 'kind' field) and resolves
        the appropriate variant layout from DICT_OF_VARIANTS. For non-variant
        types, directly initializes fields by calling _n_set_value.
        """
        attributes = list(self.__annotations__)
        set_fields = True
        class_name = type(self).__name__
        if class_name in DICT_OF_VARIANTS:
            if value and hasattr(value, 'kind'):
                kind = value.kind
            elif value:
                # value is a sub-type (e.g. Sphere) — find which kind matches
                value_type_name = type(value).__name__
                kind = None
                for k, ann in DICT_OF_VARIANTS[class_name].items():
                    for _field_name, _field_type in ann.items():
                        if _field_type == value_type_name:
                            kind = k
                            break
                    if kind is not None:
                        break
                if kind is None:
                    kind = DICT_OF_MAX_VARIANTS[class_name]
            else:
                kind = self._n_view.kind
            var_class_name = class_name + f"_kind_{int(kind)}"
            if var_class_name not in DICT_OF_C_TYPES:
                kind = DICT_OF_MAX_VARIANTS[class_name]
                var_class_name = class_name + f"_kind_{int(kind)}"
                set_fields = False
            self._n_view = (DICT_OF_C_TYPES[var_class_name]).from_address(
                ctypes.addressof(self._n_view)
            )
            # Write the resolved kind into the ctypes struct
            self._n_view.kind = int(kind)
            self._n_annotations = DICT_OF_VARIANTS[class_name][int(kind)]
            attributes = list(self._n_annotations.keys())
            # If value is a sub-type without 'kind', wrap it for _n_set_value
            if value and not hasattr(value, 'kind'):
                # Find which field in the variant matches this sub-type
                value_type_name = type(value).__name__
                _wrapped = type('_VariantProxy', (), {'kind': kind})()
                for _field_name, _field_type in self._n_annotations.items():
                    if _field_type == value_type_name:
                        setattr(_wrapped, _field_name, value)
                        break
                value = _wrapped
        else:
            self._n_annotations = self.__annotations__
        self._n_fields = attributes
        if set_fields:
            self._n_set_value(value)

    def __setattr__(self, name: str, value: object) -> None:
        attr_exists = (
            hasattr(self, name)
            and hasattr(self, "_n_fields")
            and name in self._n_fields
        )
        if attr_exists:
            attr = getattr(self, name)
            # For @ptr classes, sync ptr field addresses back to ctypes struct
            ptr_fields = getattr(self.__class__, '_n_ptr_fields', set())
            if ptr_fields and name in ptr_fields and hasattr(self, '_n_view') and self._n_view is not None:
                # Store address in ctypes c_void_p field + keep Python reference
                if isinstance(value, NilPtr) or value is None:
                    setattr(self._n_view, name, 0)
                elif hasattr(value, '_n_addr'):
                    setattr(self._n_view, name, value._n_addr)
                elif hasattr(value, '_n_view') and value._n_view is not None:
                    setattr(self._n_view, name, ctypes.addressof(value._n_view))
                super().__setattr__(name, value)
                return
            if attr is not None:
                if type(attr).__name__ in DICT_OF_VARIANTS:
                    _val = type(attr)._n_on_struct(self._n_view, name, value)
                    super().__setattr__(name, _val)
                elif isinstance(attr, bool):
                    super().__setattr__(name, value)
                elif hasattr(attr, "_n_set_value"):
                    attr._n_set_value(value)
                else:
                    super().__setattr__(name, value)
            else:
                super().__setattr__(name, value)
        else:
            super().__setattr__(name, value)

    def __getitem__(self, name: str) -> object:
        if name not in self._n_fields:
            raise KeyError
        return getattr(self, name)

    def __setitem__(self, name: str, value: object) -> None:
        if name not in self._n_fields:
            raise KeyError
        setattr(self, name, value)

    def _n_get_value(self) -> object:
        return self._n_view

    def _n_set_value(self, other: Object | None) -> None:
        """Initialize or update object fields.

        Three paths:
          A. UncheckedArray trailing fields (offset-based)
          B. Ctypes-backed fields with _n_on_struct (scalars, arrays, Object structs, NBool)
          C. Python-side fields (pointers, seq, calltypes, etc.)
        """
        python_fields = getattr(self.__class__, '_n_python_fields', set())
        field_types = getattr(self.__class__, '_n_field_types', {})
        _ua = DICT_OF_TYPES.get("UncheckedArray")

        for name in self._n_fields:
            field_cls = field_types.get(name)
            # Variant fields may not be in _n_field_types (only max-size variant is registered)
            if field_cls is None:
                type_name = self._n_annotations[name]
                field_cls = DICT_OF_TYPES.get(type_name)
            is_class = field_cls is not None and isinstance(field_cls, type)

            # A. UncheckedArray trailing fields
            if is_class and _ua and issubclass(field_cls, _ua):
                if hasattr(self, '_n_view') and self._n_view is not None:
                    field_desc = getattr(type(self._n_view), name, None)
                    offset = field_desc.offset if field_desc is not None else ctypes.sizeof(type(self._n_view))  # Trailing
                    base_addr = ctypes.addressof(self._n_view) + offset
                    arr_view = (ctypes.c_uint8 * 1).from_address(base_addr)
                    arr_ptr = field_cls.__new__(field_cls)
                    arr_ptr._n_view = arr_view
                    setattr(self, name, arr_ptr)
                else:
                    setattr(self, name, NilPtr(self._n_annotations.get(name, '')))
                continue

            # B. Ctypes-backed fields with _n_on_struct
            if name not in python_fields and hasattr(field_cls, '_n_on_struct'):
                val = getattr(other, name, None) if other else None
                if val is not None:
                    setattr(self, name, field_cls._n_on_struct(self._n_view, name, val))
                else:
                    setattr(self, name, field_cls._n_on_struct(self._n_view, name))
                continue

            # C. Python-side fields (pointers→NilPtr, calltypes→None, seq→already init'd, etc.)
            if other and hasattr(other, name):
                super(_Object, self).__setattr__(name, getattr(other, name))
            elif getattr(field_cls, '_n_is_calltype', False):
                super(_Object, self).__setattr__(name, None)
            elif is_class and DICT_OF_TYPES.get('pointer') and issubclass(field_cls, pointer):
                super(_Object, self).__setattr__(name, NilPtr(self._n_annotations.get(name, '')))
            elif name not in python_fields and field_cls is not None:
                # Non-seq python field with a default constructor
                super(_Object, self).__setattr__(name, field_cls())

    def _n_get_address(self) -> object:
        return self._n_view

    def __ilshift__(self, other: Object) -> Object:
        self._n_set_value(other)
        return self

    def copy(self, deep: bool = True) -> Object:
        cls = self.__class__
        result = cls()
        result._n_set_value(self)
        return result


    @classmethod
    def _n_resolve_variant(
        cls, dict_of_types: dict[str, type], dict_of_c_types: dict[str, type]
    ) -> dict[str, str]:
        """Parse the match/case AST in the class source to build variant layouts.

        Reads the class source code, extracts case branches with their
        kind values and field types, and returns:
          _annotations — dict of fields for the largest variant
        """
        src = ins.getsource(cls)
        aast = ast.parse(textwrap.dedent(src))
        variant_type_suspected = (
            isinstance(aast.body[0].body[0], ast.AnnAssign)
            and len(aast.body[0].body) > 1
        )
        variant_type = variant_type_suspected and isinstance(
            aast.body[0].body[1], ast.Match
        )
        if not variant_type:
            _annotations = cls.__annotations__
        else:
            dc = {}
            maxsize = 0
            # the first field is the kind
            kind_alias = aast.body[0].body[0].target.id
            kind_type_name = aast.body[0].body[0].annotation.id
            kind_type = dict_of_types[kind_type_name]
            cases = aast.body[0].body[1].cases
            for cs in cases:
                type_name = cs.body[0].annotation.id
                attr_name = cs.body[0].target.id
                kind_val = cs.pattern.value.value
                if not isinstance(kind_val, int):
                    kind_attr = cs.pattern.value.attr
                    kind_val = int(getattr(kind_type, kind_attr))
                dc[kind_val] = {kind_alias: kind_type_name, attr_name: type_name}
                size = dict_of_types[type_name]._n_sizeof()
                if size > maxsize:
                    maxsize = size
                    max_type = type_name
                    max_attr = attr_name
                    max_kind = kind_val
            _annotations = {kind_alias: kind_type_name, max_attr: max_type}
            class_name = cls.__name__
            DICT_OF_VARIANTS[class_name] = dc
            DICT_OF_MAX_VARIANTS[class_name] = max_kind
            for kind_num, ann in dc.items():
                var_class_name = class_name + f"_kind_{kind_num}"
                c_class_name = "c_" + var_class_name
                f_list = [
                    (key, dict_of_c_types[value])
                    for key, value in ann.items()
                    if value in dict_of_c_types
                ]
                _c_type = type(c_class_name, (ctypes.Structure,), {"_fields_": f_list})
                dict_of_c_types[var_class_name] = _c_type
        return _annotations

    @classmethod
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(cls._n_c_type())  # get type size in bytes

    @classmethod
    def _n_register_type(cls) -> None:
        """Register this Object subclass in the global type registries.

        Called automatically via __init_subclass__. Handles:
          - Alias/distinct types (no annotations → inherit from base)
          - Variant types (builds per-variant ctypes)
          - Regular structs (builds a ctypes.Structure with _fields_)
        """
        dict_of_types, dict_of_c_types = DICT_OF_TYPES, DICT_OF_C_TYPES
        caller_globals = cls._n_caller_globals
        if len(cls.__annotations__) == 0:
            # this should be distinct or alias type
            cls.__annotations__ = cls.__bases__[0].__annotations__
            # assume it is alias (distinct removes it if not)
            if cls.__bases__[0].__name__ in _n_aliases:
                _n_aliases[cls.__name__] = _n_aliases[cls.__bases__[0].__name__]
            else:
                _n_aliases[cls.__name__] = cls.__bases__[0].__name__
        class_name = cls.__name__
        attributes = list(cls.__annotations__)
        # variant type is suspected if there is only one attribute in annotations
        if len(attributes) == 1:
            _annotations = cls._n_resolve_variant(dict_of_types, dict_of_c_types)
        else:
            _annotations = cls.__annotations__
        dict_of_types[class_name] = cls  # add to dict for resolver
        # resolve types. Generic types, such as ptr[UncheckedArray[T]], should be specialized first
        # TODO: for variants it only resolves the largest variant, need to resolve all variants
        cls._n_field_types = {key: _n_registry.get_or_eval_type(_type_name, caller_globals)
            for key, _type_name in _annotations.items()}
        # Resolve base type classes for issubclass checks (safe if not yet defined)
        _pointer = dict_of_types.get("pointer")
        _seq = dict_of_types.get("seq")
        _ua = dict_of_types.get("UncheckedArray")

        def _has_c_backing(field_cls):
            """Check if a field type has ctypes struct backing."""
            c_name = field_cls.__name__
            if c_name in dict_of_c_types:
                return True
            is_class = isinstance(field_cls, type)
            if is_class and _pointer and issubclass(field_cls, _pointer):
                return True  # pointer/ptr[X] → c_void_p
            if getattr(field_cls, '_n_is_calltype', False):
                return True  # calltype → c_void_p
            if is_class and _ua and issubclass(field_cls, _ua):
                return True  # UncheckedArray → flexible array member
            return False

        # Classify fields: ctypes-backed vs Python-side (seq or no ctypes backing)
        python_fields = set()
        for key, field_cls in cls._n_field_types.items():
            is_class = isinstance(field_cls, type)
            if is_class and _seq and issubclass(field_cls, _seq):
                python_fields.add(key)
            elif not _has_c_backing(field_cls):
                python_fields.add(key)
        cls._n_python_fields = python_fields
        # Cache set of pointer/UncheckedArray field names for fast __setattr__ sync
        cls._n_ptr_fields = {name for name, fc in cls._n_field_types.items()
            if isinstance(fc, type) and (
                (_pointer and issubclass(fc, _pointer)) or
                (_ua and issubclass(fc, _ua))
            )}
        dict_of_types[class_name] = cls
        has_c_type = len(python_fields) < len(_annotations)
        if has_c_type:
            c_class_name = "c_" + class_name
            f_list = []
            for key, field_cls in cls._n_field_types.items():
                if key in python_fields:
                    continue
                is_class = isinstance(field_cls, type)
                c_name = field_cls.__name__
                if c_name in dict_of_c_types:
                    # Direct ctypes mapping (scalars, cstring, Object structs, arrays)
                    f_list.append((key, dict_of_c_types[c_name]))
                elif is_class and _pointer and issubclass(field_cls, _pointer):
                    # pointer or ptr[X] → c_void_p
                    f_list.append((key, ctypes.c_void_p))
                elif getattr(field_cls, '_n_is_calltype', False):
                    # Calltype (proc type) → opaque pointer
                    f_list.append((key, ctypes.c_void_p))
                elif is_class and _ua and issubclass(field_cls, _ua):
                    # Flexible array member at end of struct
                    f_list.append((key, ctypes.c_uint8 * 0))
            _c_type = type(c_class_name, (ctypes.Structure,), {"_fields_": f_list})
            dict_of_c_types[class_name] = _c_type

    @classmethod
    def _n_c_type(cls) -> type:
        return DICT_OF_C_TYPES[cls.__name__]

class Object(_Object, metaclass=NMetaClass):
    def __init_subclass__(cls) -> None:
        # Capture the defining module's globals so that eval() in
        # get_or_eval_type can resolve constants used in type annotations
        # (e.g. array[_MINIMP4_MAX_SPS, pointer]).
        caller_globals = sys._getframe(1).f_globals
        cls._n_caller_globals = caller_globals
        type_params = getattr(cls, '__type_params__', ())
        if not type_params:
            cls._n_register_type()
        else:
            # Type parameters not resolved yet, just register the class
            _n_registry.types[cls.__name__] = cls


class NTuple(_Object):
    def __init_subclass__(cls) -> None:
        caller_globals = sys._getframe(1).f_globals
        cls._n_caller_globals = caller_globals
        type_params = getattr(cls, '__type_params__', ())
        if not type_params:
            cls._n_register_type()
        else:
            _n_registry.types[cls.__name__] = cls

    def __iter__(self):
        """Yield field values in definition order, enabling tuple-style unpacking."""
        for name in self._n_fields:
            yield getattr(self, name)

# --- UncheckedArray ---

class UncheckedArray(Ntype):
    def __init__(self, data_ptr: ctypes.c_void_p=None) -> None:
        # data_ptr can be a ctypes array (e.g. c_int_Array_1) or a pointer to a structure
        self._n_view = data_ptr
        self._n_cache = {}

    @property
    def is_nil(self):
        return self._n_view is None

    def __getitem__(self, _index: int) -> object:
        index = int(_index)
        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        return self._n_cache[index]

    def __setitem__(self, _index: int, _value: object) -> None:
        index = int(_index)
        value = _value._n_get_value()
        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index, value)
        else:
            self._n_cache[index]._n_set_value(value)

    def __class_getitem__(cls, _ntype: type) -> type:
        if _ntype.__name__ not in DICT_OF_TYPES:
            _ntype._n_register_type()
        class_name = f"UncheckedArray[{_ntype.__name__}]"
        arr_type = type(class_name, (UncheckedArray,), {"_n_type": _ntype})
        arr_type._n_register_type()
        return arr_type

    @classmethod
    def _n_register_type(cls) -> None:
        DICT_OF_TYPES[cls.__name__] = cls

    @classmethod
    def _n_ptr_cast(cls, instance) -> Ntype:
        if isinstance(instance, pointer):
            address = instance._n_addr
        elif isinstance(instance, ByteAddress):
            address = _resolve_addr(instance)
        else:
            address = _resolve_addr(instance)
        if hasattr(cls, "_n_type"):
            type_name = cls._n_type.__name__
            if type_name not in DICT_OF_C_TYPES:
                cls._n_type._n_register_type()
            c_elem_type = DICT_OF_C_TYPES[type_name]
            ptr_c_type = ctypes.POINTER(c_elem_type)
            data_ptr = ctypes.c_void_p(address)
            c_data_ptr = ctypes.cast(data_ptr, ptr_c_type)
            arr = cls(c_data_ptr)
            return arr # addr(arr)
        else:
            raise Exception("Type not specified")

UncheckedArray._n_register_type()

class array(Ntype):
    """Fixed-size array: array[N, T] → Nim array[N, T].

    Backed by a ctypes buffer of exactly N elements of type T.
    """
    _n_size: int = 0

    def __init__(self, it: Sequence | None = None) -> None:
        self._n_cache = {}
        if hasattr(self, "_n_type") and hasattr(self, "_n_size"):
            class_name = f"array[{self._n_size}, {self._n_type.__name__}]"
            if class_name in DICT_OF_C_TYPES:
                self._n_backing = DICT_OF_C_TYPES[class_name]()
                self._n_owned_addr = BUFFER_REGISTRY.register(self._n_backing)
                self._n_view = DICT_OF_C_TYPES[class_name].from_address(
                    ctypes.addressof(self._n_backing)
                )
                if it is not None:
                    for index in range(self._n_size):
                        self._n_view[index] = it[index]
            else:
                # Scalar/simple types: use a plain Python list as backing store
                if it is not None:
                    for index in range(self._n_size):
                        self._n_cache[index] = it[index]
                else:
                    self._n_cache = {j: self._n_type() for j in range(self._n_size)}
                self._n_backing = None
                self._n_view = None
        else:
            raise Exception("array type or size not specified")

    def __del__(self):
        addr = getattr(self, '_n_owned_addr', None)
        if addr is not None:
            BUFFER_REGISTRY.free(addr)

    @classmethod
    def _n_on_struct(cls, struct_view, name, value: Object | None = None):
        self = cls.__new__(cls)
        self._n_view = getattr(struct_view, name)
        self._n_cache = {}
        if value is not None:
            for index in range(self._n_size):
                self[index] = value[index]
        return self

    def _n_sizeof(self) -> int:
        return self._n_size * self._n_type._n_sizeof()

    def __len__(self) -> int:
        return self._n_size

    def __getitem__(self, index: int) -> object:
        index = int(index)
        if index not in self._n_cache and self._n_view is not None:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        return self._n_cache[index]

    def __setitem__(self, index: int, value: object) -> None:
        index = int(index)
        if self._n_view is None:
            self._n_cache[index] = value
            return

        if hasattr(value, '_n_get_value'):
            val = value._n_get_value()
        else:
            val = value

        self._n_view[index] = val

        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        elif hasattr(self._n_cache[index], '_n_set_value'):
            self._n_cache[index]._n_set_value(val)
        elif hasattr(self._n_cache[index], '__ilshift__'):
            self._n_cache[index] <<= value

    def __class_getitem__(cls, params) -> type:
        """array[N, T] → fixed-size array type."""
        n, _ntype = params
        # n can be ordinal
        if _ntype.__name__ not in DICT_OF_TYPES and hasattr(_ntype, '_n_register_type'):
            _ntype._n_register_type()
        class_name = f"array[{n}, {_ntype.__name__}]"
        # also register array[N, T] in DICT_OF_TYPES and DICT_OF_C_TYPES
        arr_type = type(class_name, (array,), {"_n_type": _ntype, "_n_size": n})
        arr_type._n_register_type()
        return arr_type

    @classmethod
    def _n_register_type(cls) -> None:
        if cls._n_type.__name__ in DICT_OF_C_TYPES:
            DICT_OF_C_TYPES[cls.__name__] = DICT_OF_C_TYPES[cls._n_type.__name__] * cls._n_size
        elif isinstance(cls._n_type, pointer):
            # TODO: is this true for typed pointer?
            DICT_OF_C_TYPES[cls.__name__] = ctypes.c_void_p * cls._n_size
        # TODO: check if this is needed?
        elif cls._n_type.__name__ == "pointer" or cls._n_type.__name__.startswith("ptr["):
            DICT_OF_C_TYPES[cls.__name__] = ctypes.c_void_p * cls._n_size
        DICT_OF_TYPES[cls.__name__] = cls



# --- Sequences (seq) ---


class seq(Ntype):
    _n_is_list = False  # True for types without ctypes backing (e.g. string)

    def __init__(self, c_base: object | None = None) -> None:
        self._n_cache = {}
        self.len = 0
        self._n_reserved = 1
        if hasattr(self, "_n_type"):
            type_name = self._n_type.__name__
            if not hasattr(self._n_type, '_n_on_array'):
                # List-based mode for non-ctypes types (e.g. string)
                self._n_is_list = True
                self._n_list = []
                return
            if type_name not in DICT_OF_C_TYPES:
                self._n_type._n_register_type()
            if c_base:
                self._n_backing = c_base
            else:
                self._n_backing = (DICT_OF_C_TYPES[type_name] * self._n_reserved)()
                self._n_owned_addr = BUFFER_REGISTRY.register(self._n_backing)
            self._n_view = (self._n_backing._type_ * self._n_reserved).from_address(
                ctypes.addressof(self._n_backing)
            )
        else:
            raise Exception("Seq type not specified")

    def __del__(self):
        addr = getattr(self, '_n_owned_addr', None)
        if addr is not None:
            BUFFER_REGISTRY.free(addr)

    @property
    def is_nil(self):
        return self._n_view is None

    def __len__(self) -> int:
        if self._n_is_list:
            return len(self._n_list)
        return self.len

    def _n_resize(self) -> None:
        old_addr = ctypes.addressof(self._n_backing)
        ctypes.resize(self._n_backing, self._n_reserved * self._n_type._n_sizeof())
        self._n_owned_addr = BUFFER_REGISTRY.update(old_addr, self._n_backing)
        self._n_view = (self._n_view._type_ * self._n_reserved).from_address(
            ctypes.addressof(self._n_backing)
        )
        # invalidate cache
        self._n_cache = {}

    def __getitem__(self, index: int) -> object:
        if self._n_is_list:
            return self._n_list[index]
        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        return self._n_cache[index]

    def __setitem__(self, index, value: object) -> None:
        if isinstance(index, slice):
            # Slice assignment: seq[a:b] = array/seq
            start, stop, step = index.indices(self.len if not self._n_is_list else len(self._n_list))
            if self._n_is_list:
                for i, idx in enumerate(range(start, stop, step)):
                    self._n_list[idx] = value[i]
            else:
                # Copy bytes directly into the ctypes buffer
                src_addr = ctypes.addressof(value._n_view) if hasattr(value, '_n_view') else ctypes.addressof(value)
                dst_addr = ctypes.addressof(self._n_view) + start * self._n_type._n_sizeof()
                n_bytes = (stop - start) * self._n_type._n_sizeof()
                ctypes.memmove(dst_addr, src_addr, n_bytes)
                # Invalidate cache for affected indices
                for i in range(start, stop, step):
                    self._n_cache.pop(i, None)
            return
        if self._n_is_list:
            self._n_list[index] = value
            return
        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index, value)
        else:
            self._n_cache[index]._n_set_value(value)

    def __class_getitem__(cls, _ntype: type) -> type:
        if _ntype.__name__ not in DICT_OF_TYPES:
            _ntype._n_register_type()
        class_name = f"seq[{_ntype.__name__}]"
        _seq = type(class_name, (seq,), {"_n_type": _ntype})
        _seq._n_register_type()
        return _seq

    def add(self, value: object) -> None:
        if self._n_is_list:
            self._n_list.append(value)
            return
        if self.len == self._n_reserved:
            self._n_reserved = self._n_reserved * 2
            self._n_resize()
        self._n_cache[self.len] = self._n_type._n_on_array(
            self._n_view, self.len, value
        )
        self.len += 1

    @property
    def len(self) -> int:
        if getattr(self, '_n_is_list', False):
            return len(self._n_list)
        return getattr(self, '_n_len', 0)

    @len.setter
    def len(self, value: int):
        self._n_len = value

    def set_len(self, new_len: int) -> None:
        """Set logical length, resizing buffer if needed."""
        if new_len > self._n_reserved:
            self._n_reserved = new_len
            self._n_resize()
        self.len = new_len

    setLen = set_len

    def new_seq(self, new_len: int) -> None:
        """Nim: newSeq — allocate and set length (zero-initialized)."""
        if self._n_is_list:
            self._n_list = [self._n_type() for _ in range(new_len)]
            return
        self._n_reserved = max(new_len, 1)
        type_name = self._n_type.__name__
        self._n_backing = (DICT_OF_C_TYPES[type_name] * self._n_reserved)()
        self._n_owned_addr = BUFFER_REGISTRY.register(self._n_backing)
        self._n_view = (self._n_backing._type_ * self._n_reserved).from_address(
            ctypes.addressof(self._n_backing)
        )
        self._n_cache = {}
        self.len = new_len

    newSeq = new_seq

    def sort(self) -> None:
        """Sort the seq in place."""
        if self._n_is_list:
            self._n_list.sort()
        else:
            # For ctypes-backed seqs, collect values, sort, write back
            values = [self[i] for i in range(self.len)]
            values.sort()
            for i, v in enumerate(values):
                self[i] = v

    @property
    def items(self):
        """Yield immutable copies of elements (Nim's items)."""
        for i in range(len(self)):
            val = self[i]
            yield val.copy() if hasattr(val, 'copy') else val

    @property
    def mitems(self):
        """Yield mutable ctypes-backed views of elements (Nim's mitems)."""
        for i in range(len(self)):
            yield self[i]

    def __iter__(self):
        # We yield (index, item) so that transpiled loops like `for i, x in myseq:`
        # can unpack correctly natively, though it will break `for x in myseq:`
        for i in range(len(self)):
            val = self[i]
            yield (i, val.copy() if hasattr(val, 'copy') else val)

    @classmethod
    def _n_register_type(cls, class_name: str | None = None) -> None:
        if class_name is None:
            _class_name = cls.__name__
            if _class_name not in DICT_OF_TYPES:
                DICT_OF_TYPES[_class_name] = cls
        elif class_name.startswith("seq[") and class_name.endswith("]"):
            elem_name = class_name[4:-1]
            elem_class = DICT_OF_TYPES[elem_name]
            seq_type = seq[elem_class]  # create and register seq type
            # If the element name is an alias (e.g. "byte" -> uint8),
            # the seq type name will differ (seq[uint8]). Register the alias too.
            if class_name not in DICT_OF_TYPES:
                DICT_OF_TYPES[class_name] = seq_type


class openArray(Ntype):
    """Nim's openArray[T] — accepts array[N,T] or seq[T] transparently.

    In Python: thin wrapper that delegates indexing to the underlying container.
    In Nim: transpiles to `openArray[T]`.
    """
    _n_type = None

    def __init__(self, source=None):
        if source is not None:
            self._n_view = source._n_view if hasattr(source, '_n_view') else source
            self._n_source = source  # keep reference for len() fallback
        else:
            self._n_view = []
            self._n_source = None

    def __getitem__(self, index):
        return self._n_view[index]

    def __setitem__(self, index, value):
        if hasattr(value, '_n_addr'):
            self._n_view[index] = value._n_addr
        elif hasattr(value, '_n_get_value'):
            self._n_view[index] = value._n_get_value()
        else:
            self._n_view[index] = value

    def __len__(self):
        if hasattr(self._n_view, '__len__'):
            return len(self._n_view)
        src = getattr(self, '_n_source', None)
        return src._n_size if hasattr(src, '_n_size') else 0

    @classmethod
    def __class_getitem__(cls, _ntype):
        if hasattr(_ntype, '__name__') and _ntype.__name__ not in DICT_OF_TYPES:
            if hasattr(_ntype, '_n_register_type'):
                _ntype._n_register_type()
        class_name = f"openArray[{_ntype.__name__}]"
        return type(class_name, (openArray,), {"_n_type": _ntype})


def calltype(fn):
    """Decorator: transpiles to `type Name* = proc(...): T {.pragma.}`"""
    fn._n_is_calltype = True
    DICT_OF_TYPES[fn.__name__] = fn
    return fn


# --- Type Aliases & Convenience Constructors ---

class File:
    """Nim File type — wraps a Python file handle.

    Supports cast[pointer](file) and cast[File](token) round-tripping
    via an id-based registry, so File handles can be passed through
    opaque pointer parameters (e.g. C callback tokens).
    """
    _registry: dict[int, 'File'] = {}  # id → File instance

    __slots__ = ('_handle', '_id')

    def __init__(self, handle=None):
        self._handle = handle
        self._id = id(self)
        if handle is not None:
            File._registry[self._id] = self

    # --- delegate file operations to the underlying handle ---

    def seek(self, pos, *args):
        return self._handle.seek(pos, *args)

    def write(self, data):
        if isinstance(data, char):
            return self._handle.write(bytes(data))
        if isinstance(data, str) and hasattr(self._handle, 'mode') and 'b' in self._handle.mode:
            data = data.encode('utf-8')
        return self._handle.write(data)

    def read(self, *args):
        return self._handle.read(*args)

    def close(self):
        File._registry.pop(self._id, None)
        return self._handle.close()

    def flush(self):
        return self._handle.flush()

    @property
    def buffer(self):
        return getattr(self._handle, 'buffer', self._handle)

    # --- cast support ---

    @classmethod
    def cast(cls, source):
        """Recover a File from an opaque pointer token.

        The pointer's _n_token_id stores the registry key set by
        pointer.cast(file_instance).
        """
        if isinstance(source, File):
            return source
        if isinstance(source, pointer):
            token_id = getattr(source, '_n_token_id', None)
            if token_id is not None and token_id in cls._registry:
                return cls._registry[token_id]
        raise TypeError(f"Cannot cast {type(source)} to File")

    def __eq__(self, other):
        if other is None:
            return self._handle is None
        return NotImplemented

    def __ne__(self, other):
        if other is None:
            return self._handle is not None
        return NotImplemented

    def __repr__(self):
        return f"File({self._handle!r})"

class byte_buffer(Ntype):
    def __init__(self, backing, _n_view=None):
        if _n_view is None:
            addr = ctypes.addressof(backing)
            self._n_view = (ctypes.c_char * ctypes.sizeof(backing)).from_address(addr)
        else:
            self._n_view = _n_view

    def __getitem__(self, index):
        return self._n_view[index]

    def __setitem__(self, index, value):
        self._n_view[index] = value


class pointer(Ntype):
    """Pointer type — stores address, lazily materializes content on access.

    In Nim, cast[ptr[T]](addr) creates a pointer holding just an address.
    The T object is only materialized when the pointer is dereferenced.
    This class mirrors that behavior.
    """
    _n_contents_type = None

    @classmethod
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(ctypes.c_void_p)

    # --- construction ---

    def __init__(self, x=None):
        if x is None:
            self._n_addr = 0
            self._n_contents_cache = None
        elif isinstance(x, int):
            self._n_addr = x
            self._n_contents_cache = None
        elif hasattr(x, '_n_view') and x._n_view is not None:
            self._n_addr = ctypes.addressof(x._n_view)
            self._n_contents_cache = x  # already materialized
        else:
            # Fallback: store as-is (e.g. byte_buffer, opaque objects)
            self._n_addr = 0
            self._n_contents_cache = x

    def _n_get_value(self):
        """A pointer's value is the address it holds."""
        return self._n_view[0] if self._n_view else self._n_addr

    def _n_set_value(self, address: int):
        """Set the address the pointer points to. Address must be an int."""
        self._n_addr = address
        if self._n_view is not None:
            self._n_view[0] = address

    # --- lazy contents ---

    @property
    def contents(self):
        """Lazily materialize the pointed-to object on first access."""
        if self._n_contents_cache is not None:
            return self._n_contents_cache
        if self._n_addr == 0:
            return None
        # Lazy materialization via _n_ptr_cast
        ct = type(self)._n_contents_type
        if ct is not None and hasattr(ct, '_n_ptr_cast'):
            self._n_contents_cache = ct._n_ptr_cast(self)
        return self._n_contents_cache

    @contents.setter
    def contents(self, value):
        if self._n_addr != 0:
            ct = type(self)._n_contents_type
            if ct is not None and hasattr(ct, '__name__'):
                type_name = ct.__name__
                if type_name not in DICT_OF_C_TYPES and hasattr(ct, '_n_register_type'):
                    ct._n_register_type()
                # set the value backing to the contents's backing buffer, replace by cast?
                if type_name in DICT_OF_C_TYPES:
                    c_elem_type = DICT_OF_C_TYPES[type_name]
                    ptr_c_type = ctypes.POINTER(c_elem_type)
                    c_data = ctypes.cast(ctypes.c_void_p(self._n_addr), ptr_c_type)

                    if value is None or isinstance(value, NilPtr):
                        c_data[0] = getattr(c_elem_type, '_type_', ctypes.c_void_p)(0) if issubclass(c_elem_type, ctypes._SimpleCData) else 0 # Just a safe default
                        self._n_contents_cache = None
                    elif hasattr(ct, '_n_on_array'):
                        _value = value._n_get_value()
                        self._n_contents_cache = ct._n_on_array(c_data, 0, _value)
                    else:
                        raise ValueError(f"Cannot set contents of pointer to type {ct}")
                    return

        # Fallback for addr=0 or non C mapped
        self._n_contents_cache = value

    # --- properties ---

    @property
    def is_nil(self) -> bool:
        return self._n_addr == 0 and self._n_contents_cache is None

    def copy(self):
        result = type(self)()
        result._n_addr = self._n_addr
        result._n_contents_cache = self._n_contents_cache
        return result

    # --- cast (address-only, no eager _n_ptr_cast) ---

    @classmethod
    def cast(cls, instance):
        """Cast any pointer/memory to this pointer type.  Address-only — no
        eager object creation.  The content is materialized lazily on first
        ``.contents`` access.
        """
        result = cls.__new__(cls)
        result._n_contents_cache = None
        if isinstance(instance, NilPtr) or instance is None:
            result._n_addr = 0
            return result
        elif isinstance(instance, pointer):
            result._n_addr = instance._n_addr
            # Propagate token id for File ↔ pointer round-trips
            token_id = getattr(instance, '_n_token_id', None)
            if token_id is not None:
                result._n_token_id = token_id
            return result
        elif isinstance(instance, ByteAddress):
            result._n_addr = _resolve_addr(instance)
            return result
        elif hasattr(instance, '_n_view') and instance._n_view is not None:
            result._n_addr = ctypes.addressof(instance._n_view)
            return result
        elif hasattr(instance, '_id') and hasattr(type(instance), 'cast'):
            # Opaque handle (e.g. File) — store token id for recovery
            result._n_addr = 0
            result._n_token_id = instance._id
            return result
        else:
            addr = _resolve_addr(instance)
            if addr != 0:
                result._n_addr = addr
                return result
            raise TypeError(f"Cannot cast {type(instance)} to pointer")

    # --- struct / array embedding ---

    @classmethod
    def _n_on_struct(cls, parent_view, field_name, value=None):
        """Struct-embedded pointer: reads address from parent's c_void_p field."""
        self = cls.__new__(cls)
        self._n_contents_cache = None
        self._n_slot_addr = ctypes.addressof(parent_view) + getattr(type(parent_view), field_name).offset
        c_ptr = ctypes.cast(ctypes.c_void_p(self._n_slot_addr), ctypes.POINTER(ctypes.c_void_p))
        self._n_view = c_ptr
        if value is not None:
            self._n_set_value(value._n_get_value() if hasattr(value, '_n_get_value') else int(value))
        else:
            raw = getattr(parent_view, field_name, 0)
            self._n_addr = int(raw) if raw else 0
        return self

    @classmethod
    def _n_on_array(cls, parent_elems, index, value: int=None):
        """Array-embedded pointer: reads address from parent's ctypes array slot."""
        self = cls.__new__(cls)
        self._n_contents_cache = None
        base_addr = ctypes.addressof(parent_elems.contents) if hasattr(parent_elems, 'contents') else ctypes.addressof(parent_elems)
        self._n_slot_addr = base_addr + index * ctypes.sizeof(parent_elems._type_)
        c_ptr = ctypes.cast(ctypes.c_void_p(self._n_slot_addr), ctypes.POINTER(ctypes.c_void_p))
        self._n_view = c_ptr
        if value is not None:
            self._n_set_value(value._n_get_value() if hasattr(value, '_n_get_value') else int(value))
        else:
            raw = parent_elems[index]
            self._n_addr = int(raw) if raw else 0
        return self

    # --- operators ---

    def __getitem__(self, index: int):
        """Dereference at offset: ptr[i]"""
        return self.contents[index]

    def __setitem__(self, index: int, value):
        """Assign at offset: ptr[i] = val"""
        self.contents[index] = value

    def __getattr__(self, name):
        # directly access user exposed field names without .contents
        if name not in self.__dict__ and name != "contents" and not name.startswith("_n_"):
            return getattr(self.contents, name)
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        # directly set user exposed field names without .contents
        if name not in self.__dict__ and name != "contents" and not name.startswith("_n_"):
            setattr(self.contents, name, value)
        else:
            super().__setattr__(name, value)

    def __ilshift__(self, value):
        """<<= (value assignment) support."""
        if value is None or isinstance(value, NilPtr):
            self._n_set_value(0)
            self._n_contents_cache = None
        elif isinstance(value, pointer):
            self._n_set_value(value._n_get_value())
            self._n_contents_cache = value._n_contents_cache
        else:
            raise TypeError(f"Cannot assign {type(value)} to pointer")
        return self

    @classmethod
    def _n_ptr_cast(cls, instance):
        if hasattr(instance, '_n_addr') and instance._n_addr != 0:
            # if eager contents, addr = instance.contents._n_get_value()
            addr = ctypes.cast(ctypes.c_void_p(instance._n_addr), ctypes.POINTER(ctypes.c_void_p))[0]
            if addr is None:
                addr = 0
            p = cls.__new__(cls)
            p._n_addr = addr
            p._n_contents_cache = None
            return p
        raise ValueError("Cannot read pointer contents from nil pointer")

    @classmethod
    def _n_register_type(cls) -> None:
        DICT_OF_TYPES[cls.__name__] = cls
        DICT_OF_C_TYPES[cls.__name__] = ctypes.c_void_p


def _resolve_addr(instance) -> int:
    """Extract a raw memory address from various nimic source types."""
    if isinstance(instance, int):
        return instance
    v = getattr(instance, '_n_view', instance)
    if v is None:
        return 0
    if isinstance(v, int):
        return v
    if hasattr(v, 'value') and isinstance(v.value, int):
        return v.value
    return ctypes.addressof(v)


def addr(x: object) -> pointer:
    """For a variable of type T, addr(x) returns a pointer of type ptr[T],
    such that addr(x).contents is x"""
    if hasattr(x, '_n_slot_addr') and x._n_slot_addr != 0:
        p = ptr[type(x)]()
        p._n_addr = x._n_slot_addr
        return p

    if hasattr(x, '_n_view') and x._n_view is not None:
        p = ptr[type(x)](x)
        return p
    raise ValueError(f"Cannot make pointer from {type(x)}")


def unsafe_addr(obj: object) -> pointer:
    return addr(obj)


class ByteAddress(Ntype):
    """Base class for uintp and intp."""
    _n_is_ptr = True

    @classmethod
    def cast(cls, instance):
        return cls(instance)

    @classmethod
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(ctypes.c_void_p)

    def __init__(self, x=None):
        if x is None:
            self._n_view = None
        elif isinstance(x, ByteAddress):
            self._n_view = getattr(x, '_n_view', None)
        elif isinstance(x, pointer):
            if x._n_addr != 0:
                self._n_view = (ctypes.c_char * 1).from_address(x._n_addr)
            else:
                self._n_view = None
        elif hasattr(x, '_n_view'):
            self._n_view = x._n_view
        else:
            self._n_view = x

    @property
    def is_nil(self) -> bool:
        return self._n_view is None

    def __add__(self, offset: int):
        result = self.__class__.__new__(self.__class__)
        if getattr(self, '_n_view', None) is not None:
            addr = ctypes.addressof(self._n_view) + int(offset)
            c_type = ctypes.c_char * 1
            # # Bounds checking via registry (optional — C pointers don't bounds-check)
            # buf = BUFFER_REGISTRY.find_buffer_for_address(addr)
            # if buf is None:
            #     pass  # Allow like C, but could warn
            result._n_view = c_type.from_address(addr)
        else:
            result._n_view = None
        return result

    def __sub__(self, other):
        if isinstance(other, ByteAddress):
            if getattr(self, '_n_view', None) and getattr(other, '_n_view', None):
                return ctypes.addressof(self._n_view) - ctypes.addressof(other._n_view)
            return 0
        elif isinstance(other, pointer):
            if getattr(self, '_n_view', None) and other._n_addr != 0:
                return ctypes.addressof(self._n_view) - other._n_addr
            return 0
        elif hasattr(other, '__int__'):
            return self.__add__(-int(other))
        return 0

    def _n_get_value(self):
        """A ByteAddress's value is the memory address it wraps."""
        return ctypes.addressof(self._n_view) if self._n_view is not None else 0

    def __int__(self):
        return self._n_get_value()

    def __eq__(self, other):
        if isinstance(other, ByteAddress):
            return self._n_get_value() == other._n_get_value()
        if hasattr(other, '__int__'):
            return self._n_get_value() == int(other)
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, ByteAddress):
            return self._n_get_value() < other._n_get_value()
        return self._n_get_value() < int(other)

    def __le__(self, other):
        if isinstance(other, ByteAddress):
            return self._n_get_value() <= other._n_get_value()
        return self._n_get_value() <= int(other)

    def __gt__(self, other):
        if isinstance(other, ByteAddress):
            return self._n_get_value() > other._n_get_value()
        return self._n_get_value() > int(other)

    def __ge__(self, other):
        if isinstance(other, ByteAddress):
            return self._n_get_value() >= other._n_get_value()
        return self._n_get_value() >= int(other)

    def __ilshift__(self, value):
        if isinstance(value, ByteAddress):
            self._n_view = getattr(value, '_n_view', None)
        elif isinstance(value, pointer):
            if value._n_addr != 0:
                self._n_view = (ctypes.c_char * 1).from_address(value._n_addr)
            else:
                self._n_view = None
        else:
            self._n_view = value
        return self


class uintp(ByteAddress):
    """Pointer-sized unsigned integer for pointer arithmetic."""
    pass


class intp(ByteAddress):
    """Pointer-sized signed integer for pointer arithmetic."""
    pass



def make_pointer_type(t: type, class_name: str = None) -> type:
    if class_name is None:
        class_name = t.__name__
    ptr_type = type(class_name, (pointer,), {"_n_contents_type": t, "_n_is_ptr": True})
    ptr_type._n_register_type()
    return ptr_type

class _SomeRefClass:
    def __call__(cls, other: object) -> object:
        """When used as @ptr decorator on a class, mark it as pointer type,
        i.e. ctypes backing is a pointer to a struct
        the class exists only as a pointer type and should be equivalent
        to ptr[other] when other is not decorated"""
        if isinstance(other, type):
            original_name = other.__name__
            # keep the bare class by an alias in the DICT_OF_TYPES
            other.__name__ = f"_n_bare_{original_name}"
            DICT_OF_TYPES[other.__name__] = other
            # Re-register to rebuild ctypes struct with ptr fields included
            if hasattr(other, "_n_register_type"):
                other._n_register_type()
            ptr_type = make_pointer_type(other, class_name=original_name)
        return ptr_type

    def __getitem__(self, _ntype: type) -> type:
        """ptr[T] returns and registers class of pointer to type T, implementing cast and contents methods"""
        if _ntype.__name__ not in DICT_OF_TYPES:
            # this is probably redundant?
            _ntype._n_register_type()
        class_name = f"ptr[{_ntype.__name__}]"
        if class_name in DICT_OF_TYPES:
            ptr_type = DICT_OF_TYPES[class_name]
        else:
            ptr_type = make_pointer_type(_ntype, class_name=class_name)
        return ptr_type


ref = _SomeRefClass()
ptr = _SomeRefClass()
typedesc = _SomeRefClass()

class _SomeMutClass:
    def __matmul__(self, other: object) -> object:
        return other
# reserve keyword for modifiable variables
mut = _SomeMutClass()


def determine_common_type(type_a: type, type_b: type) -> type:
    """Implements C-style 'Usual Arithmetic Conversions' for NScalar types.

    Rules: floats beat integers (higher rank wins among floats),
    among integers of the same signedness the higher rank wins,
    for mixed signed/unsigned the unsigned wins if its rank >= signed.
    """
    if issubclass(type_a, NFloat) or issubclass(type_b, NFloat):
        return max([type_a, type_b], key=lambda t: getattr(t, "_n_rank", 0))

    if type_a == type_b:
        return type_a

    if type_a._n_signed == type_b._n_signed:
        return type_a if type_a._n_rank > type_b._n_rank else type_b

    unsigned_t = type_a if not type_a._n_signed else type_b
    signed_t = type_b if not type_a._n_signed else type_a

    if unsigned_t._n_rank >= signed_t._n_rank:
        return unsigned_t

    if signed_t._n_rank > unsigned_t._n_rank:
        return signed_t

    return unsigned_t


# --- Scalar Numerics (NScalar) ---


class NScalar:
    def _n_bind(
        self, get_value: callable, set_value: callable, get_addr: callable
    ) -> None:
        """Bind the value access closures for this scalar instance."""
        self._n_type = type(self)
        self._n_get_value = get_value
        self._n_set_value = set_value
        addr_val = get_addr()
        if addr_val is not None:
            c_type = DICT_OF_C_TYPES[self._n_type.__name__]
            self._n_view = c_type.from_address(addr_val)
        else:
            self._n_view = None

    def __init__(self, data: float = 0.0) -> None:
        """Initialize a standalone NScalar value with its own _n_value attribute."""
        # if ctype backing is needed for scalar types not on array or struct, it should be implemented here
        self._n_value = self._n_normalize(data)
        self._n_bind(
            get_value=lambda: getattr(self, "_n_value"),
            set_value=lambda value: setattr(
                self,
                "_n_value",
                value._n_get_value() if isinstance(value, NScalar) else value,
            ),
            get_addr=lambda: None,
        )

    def _n_normalize(self, val: object) -> object:
        raise NotImplementedError

    @classmethod
    def _n_on_array(
        cls, parent_elems: object, id: int, value: NScalar | None = None
    ) -> NScalar:
        """Array-embedded: reads/writes via ctypes array indexing on `parent_elems` at index `id`."""
        # parent_elems is expected to be a ctypes array (e.g. from seq[int32]) or a pointer (to array),
        # e.g. from UncheckedArray
        self = cls.__new__(cls)
        offset = id * cls._n_sizeof()
        self._n_bind(
            get_value=lambda: parent_elems[id],
            set_value=lambda _value: parent_elems.__setitem__(
                id, _value._n_get_value() if isinstance(_value, NScalar) else _value
            ),
            get_addr=lambda: (ctypes.addressof(parent_elems.contents) if hasattr(parent_elems, 'contents') else ctypes.addressof(parent_elems)) + offset,
        )
        if value is not None:
            self._n_set_value(value)
        return self

    @classmethod
    def _n_on_struct(
        cls, parent_elems: object, id: str, value: NScalar | None = None
    ) -> NScalar:
        """Struct-embedded: reads/writes via ctypes struct field on `parent_elems` with field name `id`."""
        self = cls.__new__(cls)
        offset = 0
        i = 0
        list_fields = [x for (x, t) in parent_elems._fields_]
        while not id == list_fields[i]:
            offset += ctypes.sizeof(parent_elems._fields_[i][1])
            i += 1
        self._n_bind(
            get_value=lambda: getattr(parent_elems, id),
            set_value=lambda _value: setattr(
                parent_elems,
                id,
                _value._n_get_value() if isinstance(_value, NScalar) else _value,
            ),
            get_addr=lambda: ctypes.addressof(parent_elems) + offset,
        )
        if value is not None:
            self._n_set_value(value)
        return self

    @classmethod
    def cast(cls, value: NScalar) -> NScalar:
        return cls.from_bytes(value.to_bytes())

    @classmethod
    def _n_ptr_cast(cls, value) -> NScalar:
        if isinstance(value, pointer):
            address = value._n_addr
        elif isinstance(value, ByteAddress):
            address = _resolve_addr(value)
        else:
            address = _resolve_addr(value)

        c_type = DICT_OF_C_TYPES.get(cls.__name__)
        if not c_type:
            raise Exception(f"Cannot translate {cls.__name__} to C type")
        c_instance = c_type.from_address(address)

        self = cls.__new__(cls)
        # registry keeps original pointer's buffer alive
        self._n_bind(
            get_value=lambda: c_instance.value,
            set_value=lambda _val: setattr(c_instance, 'value', getattr(_val, 'value', _val) if hasattr(_val, '_n_get_value') else _val),
            get_addr=lambda: ctypes.addressof(c_instance)
        )
        return self

    @classmethod
    def _n_c_type(cls) -> type:
        return DICT_OF_C_TYPES[cls.__name__]

    @classmethod
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(cls._n_c_type())

    @classmethod
    def _n_register_type(cls) -> None:
        # register alias
        dict_of_types, dict_of_c_types = DICT_OF_TYPES, DICT_OF_C_TYPES
        dict_of_types[cls.__name__] = cls
        _c_type = dict_of_c_types[cls.__bases__[0].__name__]
        dict_of_c_types[cls.__name__] = _c_type
        # assume it is alias (distinct removes it if not)
        if cls.__bases__[0].__name__ in _n_aliases:
            _n_aliases[cls.__name__] = _n_aliases[cls.__bases__[0].__name__]
        else:
            _n_aliases[cls.__name__] = cls.__bases__[0].__name__

    def __ilshift__(self, other: NScalar) -> NScalar:
        """assignment"""
        if isinstance(other, NScalar):
            self._n_set_value(other._n_get_value())
        else:
            self._n_set_value(other)
        return self

    def copy(self) -> NScalar:
        return type(self)(self._n_get_value())

    # def copy(self, deep=True):
    #     cls = self.__class__
    #     # result = cls.__new__(cls)
    #     result = cls.__init__(self._n_get_value())
    #     return result

    # Internal dispatch for operations
    def _n_op(self, other: NScalar | int | float, op_func: callable) -> NScalar:
        if isinstance(other, NScalar):
            target_type = determine_common_type(self._n_type, other._n_type)
            res_val = op_func(self._n_get_value(), other._n_get_value())
            return target_type(res_val)
        elif hasattr(other, "__float__"):  # numeric literal or other scalar
            # Promote int types to float64 when operating with a float literal
            if isinstance(other, float) and not issubclass(self._n_type, NFloat):
                target_type = float64
            else:
                target_type = self._n_type
            res_val = op_func(self._n_get_value(), other)
            return target_type(res_val)
        return op_func(self._n_get_value(), other)

    def _n_rop(self, other: NScalar | int | float, op_func: callable) -> NScalar:
        if isinstance(other, NScalar):
            target_type = determine_common_type(self._n_type, other._n_type)
            res_val = op_func(other._n_get_value(), self._n_get_value())
            return target_type(res_val)
        elif hasattr(other, "__float__"):  # numeric literal or other scalar
            # Promote int types to float64 when operating with a float literal
            if isinstance(other, float) and not issubclass(self._n_type, NFloat):
                target_type = float64
            else:
                target_type = self._n_type
            res_val = op_func(other, self._n_get_value())
            return target_type(res_val)
        return op_func(other, self._n_get_value())

    def _n_iop(self, other: NScalar | int | float, op_func: callable) -> None:
        if isinstance(other, NScalar):
            res_val = op_func(self._n_get_value(), other._n_get_value())
            self._n_set_value(self._n_normalize(res_val))
        elif hasattr(other, "__float__"):  # check if numeric literal or other scalar
            res_val = op_func(self._n_get_value(), other)
            self._n_set_value(self._n_normalize(res_val))

    # --- Unary Operations ---
    def __neg__(self):
        return self._n_type(-self._n_get_value())

    def __pos__(self):
        return self._n_type(+self._n_get_value())

    def __abs__(self):
        return self._n_type(abs(self._n_get_value()))

    # --- Binary Operations ---
    def __add__(self, other):
        return self._n_op(other, operator.add)

    def __sub__(self, other):
        return self._n_op(other, operator.sub)

    def __mul__(self, other):
        return self._n_op(other, operator.mul)

    def __truediv__(self, other):
        # Nim: int / int returns float
        if not issubclass(self._n_type, NFloat):
            if isinstance(other, NScalar):
                return float64(operator.truediv(self._n_get_value(), other._n_get_value()))
            elif hasattr(other, "__float__"):
                return float64(operator.truediv(self._n_get_value(), other))
        return self._n_op(other, operator.truediv)

    def __floordiv__(self, other):
        return self._n_op(other, operator.floordiv)

    def __mod__(self, other):
        return self._n_op(other, operator.mod)

    def __pow__(self, other):
        return self._n_op(other, operator.pow)

    # --- Reflected Binary Operations ---
    def __radd__(self, other):
        return self._n_rop(other, operator.add)

    def __rsub__(self, other):
        return self._n_rop(other, operator.sub)

    def __rdiv__(self, other):
        return self._n_rop(other, operator.div)

    def __rmul__(self, other):
        return self._n_rop(other, operator.mul)

    def __rtruediv__(self, other):
        # Nim: int / int returns float
        if not issubclass(self._n_type, NFloat):
            if isinstance(other, NScalar):
                return float64(operator.truediv(other._n_get_value(), self._n_get_value()))
            elif hasattr(other, "__float__"):
                return float64(operator.truediv(other, self._n_get_value()))
        return self._n_rop(other, operator.truediv)

    def __rfloordiv__(self, other):
        return self._n_rop(other, operator.floordiv)

    def __rpow__(self, other):
        return self._n_rop(other, operator.pow)

    def __rmod__(self, other):
        return self._n_rop(other, operator.mod)

    # --- In-place Operations
    def __iadd__(self, other):
        self._n_iop(other, operator.add)
        return self

    def __isub__(self, other):
        self._n_iop(other, operator.sub)
        return self

    def __imul__(self, other):
        self._n_iop(other, operator.mul)
        return self

    def __idiv__(self, other):
        self._n_iop(other, operator.div)
        return self

    def __ifloordiv__(self, other):
        self._n_iop(other, operator.floordiv)
        return self

    def __itruediv__(self, other):
        self._n_iop(other, operator.truediv)
        return self

    def __imod__(self, other):
        self._n_iop(other, operator.mod)
        return self

    def __ipow__(self, other):
        self._n_iop(other, operator.pow)
        return self

    # --- Boolean and Comparison Operations ---
    def __lt__(self, other):
        return self._n_get_value() < (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __le__(self, other):
        return self._n_get_value() <= (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __gt__(self, other):
        return self._n_get_value() > (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __ge__(self, other):
        return self._n_get_value() >= (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __eq__(self, other):
        return self._n_get_value() == (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __ne__(self, other):
        return self._n_get_value() != (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __bool__(self):
        return bool(self._n_get_value())

    def __nonzero__(self):
        return self.__bool__()

    # --- Type Conversions and Formatting ---
    def __int__(self):
        return int(self._n_get_value())

    def __float__(self):
        return float(self._n_get_value())

    def __str__(self):
        return str(self._n_get_value())

    def __repr__(self):
        return f"<{self._n_type.__name__}: {self._n_get_value()}>"

    def __format__(self, format_spec):
        return format(self._n_get_value(), format_spec)

    def __trunc__(self):
        return int(self._n_get_value())

    def __round__(self, ndigits=None):
        return round(self._n_get_value(), ndigits)

    def __hash__(self):
        return hash(self._n_get_value())


# --- Floating Point (NFloat) ---


class NFloat(NScalar):
    _n_format = ""  # struct format character
    _n_rank = 10

    def __init_subclass__(cls):
        if cls.__bases__[0].__name__ != "NFloat":
            cls._n_register_type()

    def _n_normalize(self, val):
        try:
            return struct.unpack(
                self._n_format, struct.pack(self._n_format, float(val))
            )[0]
        except (OverflowError, struct.error):
            return float("inf") if val > 0 else float("-inf")

    def to_bytes(self, byteorder=sys.byteorder):
        if byteorder == "big":
            prefix = ">" + self._n_format
        else:
            prefix = "<" + self._n_format
        out = struct.pack(prefix, self._n_get_value())
        return bytes(out)

    @classmethod
    def from_bytes(cls, bytes, byteorder=sys.byteorder):
        if byteorder == "big":
            prefix = ">" + cls._n_format
        else:
            prefix = "<" + cls._n_format
        val = struct.unpack(prefix, bytes)[0]
        return cls(val)


# --- Integers (NInteger) ---


class NInteger(NScalar):
    def __init_subclass__(cls):
        if cls._n_signed:
            _mask = (1 << cls._n_bits) - 1
            offset = 1 << (cls._n_bits - 1)

            def _normalize(self, val):
                return ((int(val) + offset) & _mask) - offset
        else:
            _mask = (1 << cls._n_bits) - 1

            def _normalize(self, val):
                return int(val) & _mask

        cls._n_normalize = _normalize
        if cls.__bases__[0].__name__ != "NInteger":
            cls._n_register_type()

    def to_bytes(self, length=None, byteorder=sys.byteorder):
        if length is None:
            length = (self._n_bits + 7) // 8

        return int(self).to_bytes(
                length, byteorder=byteorder, signed=self._n_signed
        )

    @classmethod
    def from_bytes(cls, bytes, byteorder=sys.byteorder, signed=None):
        if signed is None:
            signed = cls._n_signed
        val = int.from_bytes(bytes, byteorder=byteorder, signed=signed)
        return cls(val)

    def __lshift__(self, other):
        return self._n_op(other, operator.lshift)

    def __rshift__(self, other):
        return self._n_op(other, operator.rshift)

    def __and__(self, other):
        return self._n_op(other, operator.and_)

    def __xor__(self, other):
        return self._n_op(other, operator.xor)

    def __or__(self, other):
        return self._n_op(other, operator.or_)

    def __rlshift__(self, other):
        return self._n_rop(other, operator.lshift)

    def __rrshift__(self, other):
        return self._n_rop(other, operator.rshift)

    def __rand__(self, other):
        return self._n_rop(other, operator.and_)

    def __rxor__(self, other):
        return self._n_rop(other, operator.xor)

    def __ror__(self, other):
        return self._n_rop(other, operator.or_)

    # def __ilshift__(self, other): self._iop(other, operator.ilshift); return self
    def __irshift__(self, other):
        self._n_iop(other, operator.irshift)
        return self

    def __iand__(self, other):
        self._n_iop(other, operator.and_)
        return self

    def __ixor__(self, other):
        self._n_iop(other, operator.xor)
        return self

    def __ior__(self, other):
        self._n_iop(other, operator.or_)
        return self

    def __invert__(self):
        return self._n_type(~self._n_get_value())

    def __index__(self):
        return self._n_get_value().__index__()


# Unsigned Integers
class uint8(NInteger):
    _n_bits, _n_signed, _n_rank = 8, False, 1


class uint16(NInteger):
    _n_bits, _n_signed, _n_rank = 16, False, 3


class uint32(NInteger):
    _n_bits, _n_signed, _n_rank = 32, False, 5


class uint64(NInteger):
    _n_bits, _n_signed, _n_rank = 64, False, 7


# Signed Integers
class int8(NInteger):
    _n_bits, _n_signed, _n_rank = 8, True, 2


class int16(NInteger):
    _n_bits, _n_signed, _n_rank = 16, True, 4


class int32(NInteger):
    _n_bits, _n_signed, _n_rank = 32, True, 6


class int64(NInteger):
    _n_bits, _n_signed, _n_rank = 64, True, 8


class nint(NInteger):
    _n_bits, _n_signed, _n_rank = 64, True, 8


# # --- Floating Point Logic (using struct for IEEE-754) ---


class float16(NFloat):
    _n_format, _n_rank = "e", 11


class float32(NFloat):
    _n_format, _n_rank = "f", 12


class float64(NFloat):
    _n_format, _n_rank = "d", 13

    def _n_normalize(self, val):
        return float(val)


# class nbool:
#     def __init__ (self, value=False):
#         self.value = value

#     def __bool__ (self):
#         return self.value

#     def __neg__ (self):
#         return not self.value

#     @classmethod
#     def _n_on_struct(cls, parent_elems, id, value=None):
#         if value is None:
#             return cls()
#         else:
#             return cls(value)


class cstring:
    """Nim cstring — a nullable pointer to a null-terminated char buffer.

    In Nim, cstring is pointer-sized (char*), can be nil, does not own
    its data.  In nimic it is ctypes-backed as c_char_p inside Object
    structs (correct layout for c_malloc / pointer arithmetic).

    Python-side it stores either None (nil) or a bytes value, and
    provides len(), str(), __eq__(None), and c_free compatibility.
    """
    __slots__ = ('_value',)

    def __init__(self, value=None):
        if isinstance(value, int):
            # new_string(length) path
            self._value = b'\x00' * value
        elif isinstance(value, str):
            self._value = value.encode('utf-8')
        elif isinstance(value, bytes):
            self._value = value
        elif value is None:
            self._value = None
        else:
            self._value = bytes(value)

    # --- Object field integration ---

    @classmethod
    def _n_on_struct(cls, parent_elems, id, value=None):
        """Read/create a cstring backed by a c_char_p field in a ctypes struct."""
        raw = getattr(parent_elems, id)  # c_char_p → bytes or None
        inst = cls.__new__(cls)
        if value is not None:
            if isinstance(value, cstring):
                inst._value = value._value
            elif isinstance(value, bytes):
                inst._value = value
            elif isinstance(value, str):
                inst._value = value.encode('utf-8')
            elif value is None:
                inst._value = None
            else:
                inst._value = bytes(value)
            setattr(parent_elems, id, inst._value)
        else:
            inst._value = raw
        return inst

    def _n_set_value(self, value):
        if isinstance(value, cstring):
            self._value = value._value
        elif value is None:
            self._value = None
        elif isinstance(value, str):
            self._value = value.encode('utf-8')
        elif isinstance(value, bytes):
            self._value = value
        else:
            self._value = bytes(value)

    @classmethod
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(ctypes.c_char_p)

    # --- Nim-compatible interface ---

    def __eq__(self, other):
        if other is None:
            return self._value is None
        if isinstance(other, cstring):
            return self._value == other._value
        if isinstance(other, (str, bytes)):
            cmp = other.encode('utf-8') if isinstance(other, str) else other
            return self._value == cmp
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        return eq if eq is NotImplemented else not eq

    def __bool__(self):
        return self._value is not None

    def __len__(self):
        if self._value is None:
            return 0
        return len(self._value)

    def __str__(self):
        if self._value is None:
            return ""
        return self._value.decode('utf-8', errors='replace')

    def __repr__(self):
        if self._value is None:
            return "cstring(nil)"
        return f"cstring({self._value!r})"


def new_string(length: int) -> cstring:
    return cstring(length)


# def string(s) -> String:
#     return s.value

# --- String Type ---


class char(str):
    """Nim-compatible char type — a single byte character.

    Construction:
        char(65)        — from int ordinal (Nim's chr())
        char('A')       — from single-character string
        char('A', addr) — from string indexing with backing address
    """
    def __new__(cls, value=0, addr: int = 0):
        if isinstance(value, int):
            # chr(65) → char from ordinal
            byte_val = value & 0xFF
            obj = super().__new__(cls, struct.pack('B', byte_val).decode('latin-1'))
            obj._n_byte = byte_val
        else:
            # char('A') or char('A', addr)
            ch = value[:1] if value else '\x00'
            obj = super().__new__(cls, ch)
            obj._n_byte = ord(ch)
        obj._n_slot_addr = addr
        return obj

    def __int__(self):
        return self._n_byte

    def __index__(self):
        return self._n_byte

    def __bytes__(self):
        """Single-byte representation for binary file writing."""
        return bytes([self._n_byte])

    @classmethod
    def _n_register_type(cls):
        DICT_OF_TYPES[cls.__name__] = cls
        DICT_OF_C_TYPES[cls.__name__] = ctypes.c_char

class string(str):
    """Nim-compatible string with C-buffer backing to support addr()."""
    def __new__(cls, bs: bytes | str = ""):
        if isinstance(bs, str):
            bs = bs.encode('utf-8', errors='replace')
        obj = super().__new__(cls, bs.decode('utf-8', errors='replace'))
        obj._n_view = (ctypes.c_char * len(bs)).from_buffer_copy(bs)
        if len(bs) > 0:
            BUFFER_REGISTRY.register(obj._n_view)
        return obj

    def __len__(self):
        return len(self._n_view) if hasattr(self, '_n_view') and self._n_view is not None else super().__len__()

    def __getitem__(self, index):
        if isinstance(index, slice):
            return super().__getitem__(index)
        val = super().__getitem__(index)
        if hasattr(self, '_n_view') and self._n_view is not None:
            return char(val, ctypes.addressof(self._n_view) + index)
        return val

    def __and__(self, other):
        return string(str(self) + str(other))

    def _substitute(self, **kwargs):
        return string(Template(self).substitute(**kwargs))

    def __mod__(self, itr):
        set_key = True
        kwargs = {}
        for item in itr:
            if set_key:
                key = item
                set_key = False
            else:
                kwargs[key] = item
                set_key = True
        return self._substitute(**kwargs)

    def is_empty(self) -> bool:
        return len(self) == 0

    def __truediv__(self: string, tail: string | str) -> string:
        return f"{self}/{tail}"

    # Nim-compatible string methods (snake_case = Nim style-insensitive)
    def splitlines(self) -> list[str]:
        """Nim: splitLines — split string into lines."""
        return super().splitlines()

    def split_whitespace(self) -> list[str]:
        """Nim: splitWhitespace — split string on whitespace."""
        return super().split()

    def endswith(self, suffix: str) -> bool:
        """Nim: endsWith — check if string ends with suffix."""
        return super().endswith(suffix)

    def startswith(self, prefix: str) -> bool:
        """Nim: startsWith — check if string starts with prefix."""
        return super().startswith(prefix)

# remove when in Nim
to_string = string
_s = string

# --- Type Registry Initialization ---
def get_c_char(w: bool = False) -> ctypes.c_char | ctypes.c_wchar:
    return ctypes.c_wchar if w else ctypes.c_char

def get_c_char_p(w: bool = False) -> ctypes.c_char_p | ctypes.c_wchar_p:
    return ctypes.c_wchar_p if w else ctypes.c_char_p

c_char = get_c_char()
c_char_p = get_c_char_p()


DICT_OF_C_TYPES.update(
    {
        "float64": ctypes.c_double,
        "float32": ctypes.c_float,
        "int8": ctypes.c_int8,
        "int16": ctypes.c_int16,
        "int32": ctypes.c_int,
        "int64": ctypes.c_long,
        "nint": ctypes.c_long,
        "uint8": ctypes.c_uint8,
        "uint16": ctypes.c_uint16,
        "uint32": ctypes.c_uint,
        "uint64": ctypes.c_ulong,
        "bool": ctypes.c_bool,
        "nbool": ctypes.c_bool,
        "NBool": ctypes.c_bool,
        "byte": ctypes.c_uint8,
        "cstring": c_char_p,
        "string": c_char_p,
        "char": c_char,
        "pointer": ctypes.c_void_p,
    }
)


__native_types__ = {
    "bool": NBool,
    "float64": float64,
    "float32": float32,
    "nint": nint,
    "int8": int8,
    "int16": int16,
    "int32": int32,
    "int64": int64,
    "byte": uint8,
    "uint8": uint8,
    "uint16": uint16,
    "uint32": uint32,
    "uint64": uint64,
    "string": string,
    "char": char,
    "cstring": cstring,
    "pointer": pointer,
    "array": array,
    "openArray": openArray,
    "seq": seq,
    "UncheckedArray": UncheckedArray,
    "ptr": ptr,
    "ref": ref,
    "typedesc": typedesc,
    "File": File,
}


DICT_OF_TYPES.update(__native_types__)
