"""
nimic ntypesystem
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Core type system for the nimic DSL — imported by ntypes.py, which adds
keywords, builtins, and re-exports everything under a single public API.

Architecture (layers from low-level to high-level):

  Memory layer (ctypes-backed)
    Ntype              — base class wrapping a ctypes buffer + view for value semantics
    NTypeRegistry      — unified registry (types, c_types)
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
    Variant types      — Nim "case object": `match <discriminator>:` after the field;
                         layout from the declaration (nvariants), FieldDefect on
                         inactive fields, `with uncheckedAssign:` for branch changes.

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
import collections
import collections.abc
import contextvars
import functools
import inspect as ins
import linecache
import operator
import re
import struct
import sys
import textwrap
import types
import warnings
from enum import IntEnum, StrEnum, Enum
from string import Template
from typing import Sequence, TypeAliasType

from nimic.nvariants import NCase, NField, NRecord, NVariantLayout, parse_record


# --- Defects and {.cast(uncheckedAssign).} ---

class Defect(Exception):
    """Nim: Defect — non-catchable-by-convention runtime error."""


class FieldDefect(Defect):
    """Nim: FieldDefect — access to a field of an inactive object branch, or a
    discriminator assignment that would change the active branch."""


class OverflowDefect(Defect):
    """Nim: OverflowDefect — a signed integer operation overflowed while overflow checks are on."""


class IndexDefect(Defect, IndexError):
    """Nim: IndexDefect — an index outside the bounds of an array (bound checks on)."""


class RangeDefect(Defect):
    """Nim: RangeDefect — a value outside its range type (range checks on), e.g. chr(256). Not a
    ValueError: Nim's `except ValueError` doesn't catch it."""


class BackwardsIndex(int):
    """Nim: BackwardsIndex, `^n` — the n-th element counted from the end (s[^1] is the last). Written
    back(n) in nimic (rule:namedops); string, seq, array and openArray resolve it with _n_from_end."""


def back(n) -> BackwardsIndex:
    """Nim: ^n — an index counted from the end: s[back(1)] is Nim's s[^1] (rule:namedops)."""
    return BackwardsIndex(int(n))


def _n_from_end(index, length: int, first: int = 0):
    """`index` as a forward index into a container of `length` elements starting at `first`, if it is a
    BackwardsIndex; any other index is returned unchanged."""
    return first + length - int(index) if isinstance(index, BackwardsIndex) else index


# --- Runtime checks (Nim: overflowChecks, boundChecks, ...) ---
# Whether a check is on comes from the build profile (nimic.nsystem registers the provider: config
# options such as `overflow_checks:off`, which `-d:danger` sets) and from `push` regions: code objects
# of procs defined inside `with push("overflowChecks: off"):` run unchecked, as with Nim's
# {.push overflowChecks: off.}. The question is asked only when a check actually fails, so checked
# code pays nothing for it.
_n_check_provider = None  # callable(name: str) -> bool, set by nimic.nsystem
_n_unchecked_codes: dict[str, set] = {}  # check name -> code objects of procs defined in push regions
_n_push_depth: dict[str, int] = {}  # check name -> nesting of push regions currently executing
_N_THIS_FILE = __file__
_N_RUNTIME_DIR = __file__.rsplit("/", 1)[0] + "/"  # nimic's runtime modules (skipped when resolving UFCS)


def _n_check_enabled(name: str) -> bool:
    """Whether the runtime check `name` (normalized, e.g. "overflowchecks") applies to the code that
    triggered it: the first caller frame outside nimic's runtime modules."""
    if _n_push_depth.get(name):
        return False
    codes = _n_unchecked_codes.get(name)
    if codes:
        frame = sys._getframe(1)
        while frame is not None and frame.f_code.co_filename == _N_THIS_FILE:
            frame = frame.f_back
        if frame is not None and frame.f_code in codes:
            return False
    return _n_check_provider(name) if _n_check_provider is not None else True


def _n_check_overflow(target_type: type, value) -> None:
    """Nim: signed integer arithmetic raises OverflowDefect when the result doesn't fit the type."""
    if getattr(target_type, "_n_signed", False) and isinstance(value, int):
        half = 1 << (target_type._n_bits - 1)
        if not -half <= value < half and _n_check_enabled("overflowchecks"):
            raise OverflowDefect(f"over- or underflow: {value} does not fit {target_type.__name__}")


_N_UNCHECKED_ASSIGN = contextvars.ContextVar("_N_UNCHECKED_ASSIGN", default=0)


class _UncheckedAssign:
    """`with uncheckedAssign:` ≙ Nim `{.cast(uncheckedAssign).}:` — discriminator
    assignments inside may change the active branch. Re-entrant (token stack)."""

    def __init__(self):
        self._n_tokens = []

    def __enter__(self):
        self._n_tokens.append(_N_UNCHECKED_ASSIGN.set(_N_UNCHECKED_ASSIGN.get() + 1))
        return self

    def __exit__(self, *exc):
        _N_UNCHECKED_ASSIGN.reset(self._n_tokens.pop())
        return False


uncheckedAssign = _UncheckedAssign()


def _n_unchecked_assign_active() -> bool:
    return _N_UNCHECKED_ASSIGN.get() > 0


# --- NilPtr sentinel ---

class NilPtr:
    """Nil pointer that preserves type information for dispatch.

    When an Object field is declared as ptr[SomeType] but not yet assigned,
    it is initialized as NilPtr("ptr[SomeType]") instead of plain None.
    This allows autorename() to recover the type name for dispatch resolution.
    """
    __slots__ = ('_n_type_name',)

    @property
    def is_nil(self) -> bool:
        return True

    def __init__(self, type_name: str):
        self._n_type_name = type_name

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other) -> bool:
        return other is None or isinstance(other, NilPtr)

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(None)

    def __repr__(self) -> str:
        return f"NilPtr({self._n_type_name!r})"

__resolved__ = {}

__dispatch_generic__ = {}

__dispatch_genericT__ = {}

__tdefs__ = {}

__arg_names__ = {}

# name -> {signature: {parameter: default}}: defaults per overload (not per last-decorated function)
__arg_defaults__ = {}

# rule:varargs: name -> [(fixed parameter types, element type, converter name or None, fn)] for procs with
# a `*args: T` parameter; tried when no overload matches the call's arity (Nim prefers non-varargs)
__dispatch_varargs__ = {}

# name -> the proc of that name a @dispatch overload set extends (Nim overloads system/imported procs):
# the module global (system, std, another module) or Python builtin it shadowed when first registered
_n_imported_procs: dict = {}
_n_imported_sigs: set = set()  # (name, call signature) served by the imported proc

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
    "SomeSignedInt": ("nint", "int64", "int32", "int16", "int8"),
    "SomeUnsignedInt": ("uint", "uint64", "uint32", "uint16", "uint8"),
}
_n_generic_types["SomeInteger"] += ("uint",)
_n_generic_types["SomeNumber"] = _n_generic_types["SomeInteger"] + _n_generic_types["SomeFloat"]


class _NTypeClass:
    """A Nim type class (SomeInteger, SomeUnsignedInt, ...): `isinstance(x, SomeUnsignedInt)` is Nim's
    `x is SomeUnsignedInt`, by the member type names of _n_generic_types (an integer or float literal is
    of type int32 / float64); dispatch reads the name."""

    def __init__(self, name: str):
        self.__name__ = name

    def __instancecheck__(self, instance) -> bool:
        return not isinstance(instance, bool) and autorename(instance) in _n_generic_types[self.__name__]

    def __subclasscheck__(self, cls) -> bool:
        return isinstance(cls, type) and _n_aliases.get(cls.__name__, cls.__name__) in _n_generic_types[self.__name__]

    def __repr__(self) -> str:
        return self.__name__


SomeInteger = _NTypeClass("SomeInteger")
SomeSignedInt = _NTypeClass("SomeSignedInt")
SomeUnsignedInt = _NTypeClass("SomeUnsignedInt")
SomeFloat = _NTypeClass("SomeFloat")
SomeNumber = _NTypeClass("SomeNumber")

# for now map Python types to native types
# should map from alias directly to native type
_n_aliases = {"float": "float64", "int": "int32", "str": "string", "NBool": "bool",
              "static[bool]": "bool", "static[int]": "int32",
              "static[float]": "float64", "static[str]": "string",
              "nint": "int64", "uint": "uint64", "RootObj": "Object"}

# Names of types marked with @distinct — excluded from issubclass-based dispatch matching
_n_distinct_types: set = set()

# Protocol/concept types → member types that satisfy them without class inheritance
_n_protocol_subtypes: dict = {
    "openArray": {"seq", "array", "list"},
}

# Inlined templates registry shared with nimic.inliner
_n_templates: dict = {}

# Nim `{.pragma: name, p1, p2.}`: module name -> {alias: the pragma items it stands for}
_n_pragma_aliases: dict[str, dict[str, list[str]]] = {}


def _n_pragma_items(text: str) -> list[str]:
    """The items of a pragma list `a, b: [c, d], e("x, y")`, split at its top-level commas (outside
    brackets, parentheses and string literals)."""
    items, depth, quote, start = [], 0, "", 0
    for i, c in enumerate(text):
        if quote:
            quote = "" if c == quote and text[i - 1] != "\\" else quote
        elif c in "\"'":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            items.append(text[start:i].strip())
            start = i + 1
    items.append(text[start:].strip())
    return [item for item in items if item]


def _n_pragma_name(item: str) -> str:
    """The name of a pragma item (`raises: [E]` -> raises, `nifEmits("D")` -> nifEmits)."""
    return re.split(r"[:(\s]", item, maxsplit=1)[0]


def _n_register_pragma(module: str, text: str) -> None:
    """A standalone pragma `{.text.}` executed in `module`: `pragma: name, p1, p2` defines the alias
    `name` (Nim's pragma pragma); other standalone pragmas (`feature: "x"`) only affect the Nim output."""
    items = _n_pragma_items(text)
    if items and _n_pragma_name(items[0]) == "pragma" and ":" in items[0]:
        alias = items[0].split(":", 1)[1].strip()
        _n_pragma_aliases.setdefault(module, {})[alias] = items[1:]


def _n_routine_pragmas(fn: callable) -> list[str]:
    """The pragma names of a routine: the `{.x, y.}` of its docstring (rule:pragma), with the pragma
    aliases of its module expanded."""
    doc = getattr(fn, "__doc__", None) or ""
    if "{." not in doc:
        return []
    aliases = _n_pragma_aliases.get(getattr(fn, "__module__", None), {})
    names = []

    def expand(items, seen):
        for item in items:
            name = _n_pragma_name(item)
            if name in aliases and name not in seen:
                expand(aliases[name], seen | {name})
            elif name not in aliases and name not in names:
                names.append(name)

    expand(_n_pragma_items(doc.split("{.", 1)[1].split(".}", 1)[0]), frozenset())
    return names


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
    func_def.decorator_list = []

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
    # Build namespace with access to the module's globals; registered types only fill names the module
    # lacks, globals and builtins alike (the module's `bool` is Python's bool, DICT_OF_TYPES["bool"] NBool)
    builtin_names = vars(sys.modules["builtins"])
    ns = {name: t for name, t in DICT_OF_TYPES.items() if name not in builtin_names}
    ns.update(fn.__globals__)
    exec(code, ns)
    specialized_fn = ns[func_def.name]
    # Preserve the original function name for dispatch lookup
    specialized_fn.__qualname__ = original_name + suffix
    return specialized_fn


def autorename(x: object) -> str:
    if isinstance(x, NilPtr):
        return x._n_type_name
    if isinstance(x, tuple) and not isinstance(x, NTuple):
        return f"tuple[{', '.join(autorename(elem) for elem in x)}]"
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

    for gt, members in _n_generic_types.items():
        if gt in sig_type:
            gt_pattern = "(?:" + "|".join(re.escape(m) for m in members) + ")"
            pattern = pattern.replace(re.escape(gt), gt_pattern)

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

    Returns True if:
    - Names are equal (exact match)
    - Names are equal after alias resolution
    - arg satisfies a protocol that sig declares (e.g. seq satisfies openArray)
    - arg is a class-hierarchy subtype of sig (inheritance / object-of)

    Returns False if:
    - arg is a @distinct type (distinct types only match via converter, not subtype)
    """
    if arg_type_name == sig_type_name:
        return True
    # Distinct types never match via subtype — only via converter
    if arg_type_name in _n_distinct_types:
        return False
    # Resolve aliases to canonical names (e.g. nint → int64, int → int32)
    arg_canonical = _n_aliases.get(arg_type_name, arg_type_name)
    sig_canonical = _n_aliases.get(sig_type_name, sig_type_name)
    if sig_canonical == "untyped":
        return True
    if arg_canonical == sig_canonical:
        return True
    # None (nil in Nim) matches the nilable types only: ref, ptr, pointer, proc
    if arg_canonical == "NoneType":
        return _n_is_nilable(DICT_OF_TYPES.get(sig_type_name))
    # Generic type classes (SomeInteger, SomeFloat)
    if sig_canonical in _n_generic_types and arg_canonical in _n_generic_types[sig_canonical]:
        return True
    # Protocol matching (e.g. openArray accepts seq, array, list)
    protocol_members = _n_protocol_subtypes.get(sig_canonical)
    if protocol_members and arg_canonical in protocol_members:
        return True
    # Parameterized protocol: openArray[T] matches seq[T], array[N,T]
    if sig_canonical.startswith("openArray") and any(
        arg_canonical.startswith(p) for p in ("seq", "array", "list")
    ):
        return True
    # Pointer protocol: pointer or ptr accepts any ptr[T]
    if sig_canonical in ("pointer", "ptr") and (
        arg_canonical.startswith("ptr[") or arg_canonical in ("ptr", "pointer")
    ):
        return True
    # Tuple matching: tuple[...] or bare tuple
    if sig_canonical == "tuple" and (arg_canonical.startswith("tuple[") or arg_canonical == "tuple"):
        return True
    if sig_canonical.startswith("tuple[") and arg_canonical.startswith("tuple["):
        sig_inner = sig_canonical[6:-1]
        arg_inner = arg_canonical[6:-1]
        sig_parts = [p.strip() for p in sig_inner.split(',')]
        arg_parts = [p.strip() for p in arg_inner.split(',')]
        if len(sig_parts) == len(arg_parts):
            if all(
                a == s or a in _n_generic_types.get(s, ()) or _match_subtype(a, s)
                for a, s in zip(arg_parts, sig_parts)
            ):
                return True
    if sig_canonical.startswith("tuple[") and arg_canonical == "tuple":
        return True
    # Class hierarchy (inheritance / object-of) — issubclass
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


def _n_resolve_type_aliases(ann: str, namespace: dict) -> str:
    """Resolve module-level type aliases in a string annotation through `namespace`
    (the function's globals): with `Snippet = string; varargs = seq`, the annotation
    "varargs[Snippet]" becomes "seq[string]". Only names bound to a class with a
    different __name__ are rewritten; otherwise the annotation is returned unchanged
    (also for forward references and non-type expressions such as `ptr @ T`).
    Names the type system already knows (aliases such as "static[bool]", generic type
    classes such as SomeInteger, registered types) are kept, and a name only resolves to
    a nimic class, never to the Python builtin it may alias (`static = set`, `SomeInteger = int`)."""
    if ann in _n_aliases or ann in _n_generic_types:
        return ann
    try:
        node = ast.parse(ann, mode="eval").body
    except SyntaxError:
        return ann
    changed = False

    def resolve(n):
        nonlocal changed
        if isinstance(n, ast.Name):
            if n.id in _n_aliases or n.id in _n_generic_types:
                return n.id
            registered = DICT_OF_TYPES.get(n.id)
            if registered is not None:
                if (isinstance(registered, type) and registered.__name__ != n.id
                        and registered.__name__ not in _n_aliases):  # BiggestInt -> int64 (not bool -> NBool)
                    changed = True
                    return registered.__name__
                return n.id
            obj = namespace.get(n.id)
            if isinstance(obj, type) and obj.__name__ != n.id and obj.__module__ != "builtins":
                changed = True
                return obj.__name__
            return n.id
        if isinstance(n, ast.Subscript):
            elts = n.slice.elts if isinstance(n.slice, ast.Tuple) else [n.slice]
            parts = [resolve(n.value)] + [resolve(e) for e in elts]
            if None in parts:
                return None
            return f"{parts[0]}[{', '.join(parts[1:])}]"
        if isinstance(n, ast.Constant) and isinstance(n.value, int):  # array[N, T]
            return str(n.value)
        return None

    resolved = resolve(node)
    return resolved if changed and resolved is not None else ann


def _n_has_arity(name: str, n: int) -> bool:
    return any(len(sig) == n for table in (__resolved__, __dispatch_generic__, __dispatch_genericT__)
               for sig in table.get(name, ()))


def _n_bind_overloads(name: str, args: tuple, kwargs: dict) -> list[tuple]:
    """Positional argument tuples obtained by binding `args` and `kwargs` to the parameters of each
    overload of `name` (keywords by name, missing trailing parameters from that overload's defaults),
    the ones needing fewer defaults first."""
    found = []
    defaults_of = __arg_defaults__.get(name, {})
    for sig, names in __arg_names__.get(name, {}).items():
        if len(args) > len(names):
            continue
        full, used, n_defaults = list(args), set(), 0
        for pname in names[len(args):]:
            if pname in kwargs:
                full.append(kwargs[pname])
                used.add(pname)
            elif pname in defaults_of.get(sig, {}):
                full.append(defaults_of[sig][pname])
                n_defaults += 1
            else:
                break
        else:
            if used == set(kwargs) and (kwargs or n_defaults):
                cand = tuple(full)
                if all(cand is not f and (len(cand) != len(f) or any(a is not b for a, b in zip(cand, f)))
                       for f, _ in found):
                    found.append((cand, n_defaults))
    return [cand for cand, _ in sorted(found, key=lambda item: item[1])]


def _n_union_type_class(ann: str, namespace: dict) -> str:
    """A union annotation `A | B | C` (Nim `A or B or C`) becomes a type class, like SomeInteger: its
    canonical name is registered in _n_generic_types with the member types (aliases resolved)."""
    if not isinstance(ann, str) or "|" not in ann:
        return ann
    try:
        node = ast.parse(ann, mode="eval").body
    except SyntaxError:
        return ann
    members = []

    def collect(n) -> bool:
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            return collect(n.left) and collect(n.right)
        name = _n_resolve_type_aliases(ast.unparse(n), namespace)
        name = _n_aliases.get(name, name)
        members.extend(_n_generic_types.get(name, (name,)))
        return True

    collect(node)
    key = " | ".join(members)
    _n_generic_types[key] = tuple(dict.fromkeys(members))
    return key


def _n_value_copy(value):
    """Nim assignment semantics for a field value: value types (string, seq, set, array, non-ref
    objects) are copied, refs, pointers, procs and scalars are shared."""
    if value is None or getattr(type(value), "_n_is_ref", False) or callable(value) and not hasattr(value, "copy"):
        return value
    if isinstance(value, (string, seq, Tset, array, _Object)) and callable(getattr(value, "copy", None)):
        return value.copy()
    if type(value) is tuple:  # an anonymous tuple (Nim `(a, b)`) is a value: its elements are copied
        return tuple(_n_value_copy(v) for v in value)
    return value


def _n_type_name(t: object) -> str:
    """The nimic spelling of type `t`: its class name, or for a generic alias of a Python type such as
    the anonymous tuple type `tuple[char, nint]` (whose `__name__` is just "tuple") the full spelling."""
    args = getattr(t, "__args__", None)
    if not isinstance(t, type) and isinstance(getattr(t, "__origin__", None), type) and args:
        return f"{t.__origin__.__name__}[{', '.join(_n_type_name(a) for a in args)}]"
    return getattr(t, "__name__", str(t))


def _n_split_type_args(params: str) -> list[str]:
    """The arguments of a type spelling's brackets, split at its top-level commas only
    (`seq[nint], tuple[nint, string]` -> two arguments)."""
    parts, depth, start = [], 0, 0
    for i, c in enumerate(params):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(params[start:i].strip())
            start = i + 1
    parts.append(params[start:].strip())
    return parts


def _n_dollar(x) -> str:
    """Nim `$x` as Python text: bools are true/false and nil is nil; nimic types define their own str()."""
    if isinstance(x, NBool):
        return str(x)
    if x is True:
        return "true"
    if x is False:
        return "false"
    if x is None:
        return "nil"
    return str(x)


def _n_escaped_char(c: str) -> str:
    """Nim addEscapedChar: the text of a char inside a quoted string or char literal."""
    escapes = {"\a": "\\a", "\b": "\\b", "\t": "\\t", "\n": "\\n", "\v": "\\v", "\f": "\\f", "\r": "\\c",
               "\x1b": "\\e", "\\": "\\\\", "'": "\\'", '"': '\\"'}
    if c in escapes:
        return escapes[c]
    return c if 32 <= ord(c) <= 126 else f"\\x{ord(c):02X}"


def _n_quoted(x) -> str:
    """Nim addQuoted: an element of `$` of a collection — strings and chars quoted and escaped, else `$x`."""
    if isinstance(x, char):
        return "'" + _n_escaped_char(str(x)) + "'"
    if isinstance(x, (string, cstring)):
        return '"' + "".join(_n_escaped_char(c) for c in str(x)) + '"'
    return _n_dollar(x)


def _n_collection_str(prefix: str, items, suffix: str) -> str:
    """Nim collectionToString: `$` of a set, seq or array."""
    return prefix + ", ".join(_n_quoted(x) for x in items) + suffix


def _n_vararg_type(ann, namespace: dict) -> tuple[str, str | None]:
    """Element type and converter of a `*args` annotation: `T`, or `varargs[T, conv]`."""
    text = ann if isinstance(ann, str) else getattr(ann, "__name__", str(ann))
    conv = None
    m = re.fullmatch(r"\s*varargs\[\s*(.+?)\s*(?:,\s*(\w+)\s*)?\]\s*", text)
    if m:
        text, conv = m.group(1), m.group(2)
    text = _n_resolve_type_aliases(text, namespace)
    return _n_aliases.get(text, text), conv


def _n_type_matches(arg_type: str, sig_type: str) -> bool:
    """Whether an argument of type `arg_type` can be passed to a parameter of type `sig_type`."""
    if arg_type == sig_type or sig_type == "untyped":
        return True
    if sig_type in _n_generic_types and arg_type in _n_generic_types[sig_type]:
        return True
    return _match_subtype(arg_type, sig_type) or _match_converter(arg_type, sig_type)


def _n_varargs_call(name: str, args: tuple):
    """A callable running the first varargs overload of `name` that matches `args`, or None."""
    for fixed, elem, conv, fn in __dispatch_varargs__.get(name, ()):
        if len(args) < len(fixed):
            continue
        if not all(_n_type_matches(autorename(a), t) for a, t in zip(args, fixed)):
            continue
        extra = args[len(fixed):]
        if conv is None:
            if not all(_n_type_matches(autorename(a), elem) for a in extra):
                continue
        else:
            converter = _n_dollar if conv == "str" else (fn.__globals__.get(conv) or getattr(sys.modules["builtins"], conv))
            extra = tuple(string(converter(a)) if elem == "string" else converter(a) for a in extra)
        return lambda fn=fn, call_args=tuple(args[:len(fixed)]) + tuple(extra): fn(*call_args)
    return None


class _DispatchedCallable:
    """Callable returned by @dispatch: forwards calls to the dispatcher and looks like
    the decorated function (name, annotations, code, type params, globals), so it can
    be re-dispatched (e.g. by DispDict) and bound as a method."""

    def __init__(self, target, orig_fn):
        functools.update_wrapper(self, orig_fn)  # copies __type_params__ (3.12+) and __dict__
        self._n_target = target
        self._n_fn = orig_fn
        # not covered by update_wrapper, but read by dispatch() on re-dispatch
        self.__code__ = getattr(orig_fn, "__code__", None)
        self.__defaults__ = getattr(orig_fn, "__defaults__", None)
        self.__globals__ = getattr(orig_fn, "__globals__", {})

    def __call__(self, *args, **kwargs):
        return self._n_target(*args, **kwargs)

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return types.MethodType(self, instance)

    def __getitem__(self, types_param):
        if self.__name__ == "__getitem__":
            if isinstance(types_param, tuple):
                return self._n_target(*types_param)
            return self._n_target(types_param)
        return self


def _n_named_tuple_result(fn: callable) -> callable:
    """A proc declared to return a named tuple type converts a returned tuple literal to it (Nim
    `result = (a, b)` for `tuple[x, y: T]`). Wrapped only when the annotation names an NTuple class
    already defined, so other procs pay nothing."""
    ann = getattr(fn, "__annotations__", {}).get("return")
    rtype = ann
    if isinstance(ann, str):  # the module's name, or a local one of the scope defining fn
        rtype = fn.__globals__.get(ann) or sys._getframe(2).f_locals.get(ann)
    if not (isinstance(rtype, type) and issubclass(rtype, NTuple)):
        return fn
    fields = rtype._n_fields

    @functools.wraps(fn)
    def named_tuple_result(*args, **kwargs):
        r = fn(*args, **kwargs)
        if type(r) is tuple and len(r) == len(fields):
            return rtype(**dict(zip(fields, r)))
        return r
    return named_tuple_result


def _n_typed_literals(fn: callable, targets: list) -> callable:
    """Nim types a number literal by the parameter it is passed to: `f(5)` with `x: BiggestInt` gets an
    int64. Wraps a resolved overload so Python int/float arguments become the nimic scalar type named
    at their position (`targets`); other arguments pass unchanged."""
    convert = {i: DICT_OF_TYPES.get(name) for i, name in enumerate(targets)}
    convert = {i: cls for i, cls in convert.items() if isinstance(cls, type) and issubclass(cls, NScalar)}
    if not convert:
        return fn

    @functools.wraps(fn)
    def typed(*args):
        return fn(*(convert[i](a) if i in convert and type(a) in (int, float) else a
                    for i, a in enumerate(args)))
    return typed


def _n_typedesc_sig(annotation: str) -> str:
    """`typedesc[T]` matches the type T itself: a class argument's signature is `type[T]` (autorename)."""
    if isinstance(annotation, str) and annotation.startswith("typedesc[") and annotation.endswith("]"):
        return f"type[{annotation[len('typedesc['):-1]}]"
    return annotation


# Python builtins that nimic code calls as Nim system procs (other builtins are no Nim procs to extend)
_N_SYSTEM_BUILTINS = frozenset({"abs", "len", "min", "max"})


def _n_register_imported_proc(fn: callable, fn_globals: dict) -> None:
    """Nim overloading spans modules: `proc cmp*(a, b: Int128)` adds an overload to system.cmp. When a
    @dispatch proc shadows a routine of the same name that is no overload set itself (a system or std
    proc imported into the module, or a builtin of _N_SYSTEM_BUILTINS such as abs), calls no overload matches go to it.
    A plain function of the same module (a forward declaration) is not such a routine."""
    if fn.__name__ in _n_imported_procs:
        return
    prior = fn_globals.get(fn.__name__)
    if prior is None and fn.__name__ in _N_SYSTEM_BUILTINS:
        prior = getattr(sys.modules["builtins"], fn.__name__)
    if (callable(prior) and not isinstance(prior, (type, _DispatchedCallable))
            and getattr(prior, "__module__", None) != fn.__module__):
        _n_imported_procs[fn.__name__] = prior


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
    if isinstance(fn, _DispatchedCallable):
        # re-dispatch (e.g. DispDict overloading an explicit @dispatch method): register the
        # original function; registering the wrapper would make it dispatch to itself forever
        fn = fn._n_fn
    fn = _n_named_tuple_result(fn)
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
    arg_count = fn.__code__.co_argcount
    raw_arg_names = fn.__code__.co_varnames[:arg_count]
    defaults = fn.__defaults__ or ()
    default_offset = arg_count - len(defaults)

    for i, name in enumerate(raw_arg_names):
        if name not in _annotations:
            if i >= default_offset:
                def_val = defaults[i - default_offset]
                def_type = type(def_val).__name__
                _annotations[name] = _n_aliases.get(def_type, def_type)
            elif fn.__name__ in _n_templates:
                _annotations[name] = "untyped"

    sig_list = [
        (_annotations[name].removeprefix("mut @ ").removeprefix("out @ ") if isinstance(_annotations[name], str) else getattr(_annotations[name], '__name__', str(_annotations[name])))
        for name in raw_arg_names
        if name in _annotations
    ]
    fn_globals = getattr(fn, "_n_globals", fn.__globals__)  # block template factories: the template's module
    sig_list = [_n_typedesc_sig(v) for v in sig_list]
    sig_list = [_n_resolve_type_aliases(v, fn_globals) for v in sig_list]
    sig_list = [_n_aliases[v] if v in _n_aliases else v for v in sig_list]
    sig_list = [_n_union_type_class(v, fn_globals) for v in sig_list]
    arg_names = tuple(name for name in raw_arg_names if name in _annotations)
    arg_defaults = {name: defaults[i - default_offset] for i, name in enumerate(raw_arg_names)
                    if i >= default_offset and name in _annotations}

    if not len(sig_list) == arg_count:
        sig_str = ", ".join(sig_list)
        raise Exception(
            f"type not found for all arguments of {fn.__name__}, only the following: {sig_str}"
        )
    if fn.__code__.co_flags & ins.CO_VARARGS:
        vararg_name = fn.__code__.co_varnames[arg_count + fn.__code__.co_kwonlyargcount]
        elem, conv = _n_vararg_type(fn.__annotations__.get(vararg_name, "untyped"), fn_globals)
        entries = __dispatch_varargs__.setdefault(fn.__name__, [])
        entries[:] = [e for e in entries if e[0] != tuple(sig_list)] + [(tuple(sig_list), elem, conv, fn)]
    _n_register_imported_proc(fn, fn_globals)
    generic = any((arg in _n_generic_types for arg in sig_list))
    genericT = len(fn.__type_params__) > 0
    # register signature
    if fn.__name__ not in __arg_names__:
        __arg_names__[fn.__name__] = {}

    if genericT:
        T_def = {t: _n_union_type_class(c, fn_globals) for t, c in get_type_params(fn).items()}  # `T: A | B` is a type class
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
        __arg_defaults__.setdefault(fn.__name__, {})[sigs] = arg_defaults
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
        __arg_defaults__.setdefault(fn.__name__, {})[sigs] = arg_defaults
    else:
        sigs = tuple((arg,) for arg in sig_list)
        if fn.__name__ in __resolved__:
            __resolved__[fn.__name__][sigs] = fn
        else:
            __resolved__[fn.__name__] = {sigs: fn}
        __arg_names__[fn.__name__][sigs] = arg_names
        __arg_defaults__.setdefault(fn.__name__, {})[sigs] = arg_defaults

    def fn_dispatch(*args, **kwargs):
        # a call already bound to one overload's parameters (keywords and defaults filled in): dispatch it
        # as it is; filling defaults again could bind it to another overload with shifted positions
        bound = kwargs.pop("_n_bound", False)
        if kwargs:
            # bind keywords (and defaults) to each overload's parameters, then dispatch positionally
            candidates = _n_bind_overloads(fn.__name__, args, kwargs)
            if not candidates and fn.__name__ in _n_imported_procs:
                return _n_imported_procs[fn.__name__](*args, **kwargs)
            if not candidates:
                raise TypeError(f"Invalid keyword arguments for {fn.__name__}")
            for cand in candidates:
                try:
                    return fn_dispatch(*cand, _n_bound=True)
                except NotImplementedError:
                    pass
            raise NotImplementedError(f"Function not defined for keyword signature: {fn.__name__}")

        if not bound and not _n_has_arity(fn.__name__, len(args)):
            # no overload takes exactly this many arguments: fill trailing defaults per overload
            for cand in _n_bind_overloads(fn.__name__, args, {}):
                try:
                    return fn_dispatch(*cand, _n_bound=True)
                except NotImplementedError:
                    pass

        sigs = ((autorename(arg),) for arg in args)
        fn_sig = tuple(sigs)
        if (fn.__name__, fn_sig) in _n_imported_sigs:
            return _n_imported_procs[fn.__name__](*args)
        is_resolved = (
            fn.__name__ in __resolved__ and fn_sig in __resolved__[fn.__name__]
        )
        if is_resolved:
            return __resolved__[fn.__name__][fn_sig](*args)
        else:
            # try to resolve signature
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
                                elif any(_match_subtype(arg_name, s) for s in sig_def[i]):
                                    specificity += 1
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
                    targets = [best_T_var.get(d[0], d[0]) if len(d) == 1 else a[0]
                               for d, a in zip(best_sig_def, fn_sig)]
                    specialized = _n_typed_literals(specialized, targets)
                    if fn.__name__ in __resolved__:
                        __resolved__[fn.__name__][fn_sig] = specialized
                    else:
                        __resolved__[fn.__name__] = {fn_sig: specialized}
        is_resolved = (
            fn.__name__ in __resolved__ and fn_sig in __resolved__[fn.__name__]
        )
        if not is_resolved:
            # try subtype and converter matching against registered concrete signatures
            if fn.__name__ in __resolved__:
                for sig_def, sig_fn in __resolved__[fn.__name__].items():
                    if len(fn_sig) == len(sig_def):
                        if all(
                            _match_subtype(fn_sig[i][0], sig_def[i][0])
                            or _match_converter(fn_sig[i][0], sig_def[i][0])
                            for i in range(len(fn_sig))
                        ):
                            __resolved__[fn.__name__][fn_sig] = _n_typed_literals(sig_fn, [d[0] for d in sig_def])
                            is_resolved = True
                            break
        if not is_resolved and not bound:
            # overloads of this arity didn't match the types: try overloads whose defaults fill the call
            for cand in _n_bind_overloads(fn.__name__, args, {}):
                if len(cand) > len(args):
                    try:
                        return fn_dispatch(*cand, _n_bound=True)
                    except NotImplementedError:
                        pass
        if not is_resolved:
            # a registered varargs overload wins over a method of the first argument (e.g. str.format)
            varargs_call = _n_varargs_call(fn.__name__, args)
            if varargs_call is not None:
                return varargs_call()
        if not is_resolved:
            # Check UFCS: if the first argument has a method with this function's name
            if len(args) >= 1 and not fn.__name__.startswith("__") and hasattr(args[0], fn.__name__):
                method = getattr(args[0], fn.__name__)
                if (callable(method) and getattr(method, "__func__", None) not in (fn, fn_dispatch)
                        and not isinstance(method, functools.partial)):  # not the UFCS lookup of a proc
                    try:
                        return method(*args[1:], **kwargs)
                    except AttributeError:
                        pass
        if is_resolved:
            return __resolved__[fn.__name__][fn_sig](*args)
        varargs_call = _n_varargs_call(fn.__name__, args)
        if varargs_call is not None:
            return varargs_call()
        if fn.__name__ in _n_imported_procs:
            # no overload of this set matches: the imported proc it extends (system `low`, builtin `abs`)
            _n_imported_sigs.add((fn.__name__, fn_sig))
            return _n_imported_procs[fn.__name__](*args)
        sig_str = ", ".join([sig[0] for sig in fn_sig])
        raise NotImplementedError(
            f"Function not defined for signature: {fn.__name__}({sig_str})"
        )

    # for debugging save in visible debugG
    for nm in __resolved__:
        debugG[nm] = __resolved__[nm].copy()

    return _DispatchedCallable(fn_dispatch, fn)


# --- UFCS (Nim method-call syntax) ---

# (class, method name) -> free proc installed by @ufcs
_n_ufcs_registry: dict = {}


def _n_str_method(fn: callable) -> callable:
    """A Nim `$` installed as __str__: Python's str() needs a builtin str, the proc returns a nimic string
    (str(x) is Python text in nimic, as for the builtin types)."""
    @functools.wraps(fn)
    def __str__(self) -> str:
        result = fn(self)
        return result if type(result) is str else _n_dollar(result)
    return __str__


def ufcs(*classes: type, aliases: tuple = ()) -> callable:
    """Nim method-call syntax for a free proc: after `@ufcs(string)` on `def f(s, ...)`,
    `s.f(...)` calls `f(s, ...)`. The proc is installed under its own name and each of
    `aliases` (e.g. the camelCase spelling). An operator (dunder) defined in another module for this
    class is installed even if the class inherits one (Nim: `proc `%`*(f: FormatStr, ...)` next to the
    type alias), and a @dispatch overload extends a method of the class's own; any other attribute the class
    already has is never shadowed (TypeError); re-registering a name installed by @ufcs (a further @dispatch
    overload, a module reload) replaces it. Returns the proc unchanged."""
    def install(fn):
        method = _n_str_method(fn) if fn.__name__ == "__str__" else fn
        for cls in classes:
            for name in (fn.__name__, *aliases):
                operator_override = name.startswith("__") and name.endswith("__") and name not in cls.__dict__
                own = cls.__dict__.get(name)
                if (isinstance(fn, _DispatchedCallable) and isinstance(own, types.FunctionType)
                        and (cls, name) not in _n_ufcs_registry):
                    # an overload of a method the class defines (e.g. `==` of two values in the class, a
                    # later `==` with an integer): the method joins the overload set
                    dispatch(own)
                elif hasattr(cls, name) and (cls, name) not in _n_ufcs_registry and not operator_override:
                    raise TypeError(f"@ufcs: {cls.__name__}.{name} already exists; "
                                    f"refusing to shadow it with the free proc {fn.__name__}")
                _n_ufcs_registry[(cls, name)] = fn
                setattr(cls, name, method)
        return fn
    return install


# --- Converter Registry ---

# Maps source_type_name → set of target_type_names
__converters__ = {
    # Implicit integer widening
    "int8": {"int16", "int32", "int64"},
    "int16": {"int32", "int64"},
    "int32": {"int64"},
    "uint8": {"uint16", "uint32", "uint64"},
    "uint16": {"uint32", "uint64"},
    "uint32": {"uint64"},
}


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

    Removes the type from _n_aliases, registers it in _n_distinct_types
    (so _match_subtype excludes it from inheritance-based dispatch), and
    blocks inherited methods not explicitly re-declared in the class body.
    Internal _n_* methods and Python object protocol methods are never blocked.

    If a @converter exists from this type to a parent type, inherited
    methods are preserved (implicit conversion makes them accessible).
    """
    # Register as distinct — excluded from issubclass-based dispatch matching
    _n_distinct_types.add(cls.__name__)
    cls._n_is_distinct = True

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

    DICT_OF_TYPES[cls.__name__] = cls
    for base in getattr(cls, '__mro__', [])[1:]:
        if base.__name__ in DICT_OF_C_TYPES:
            DICT_OF_C_TYPES[cls.__name__] = DICT_OF_C_TYPES[base.__name__]
            break
    return cls


class NTypeRegistry:
    """Centralized registry for all nimic type information.

    Consolidates DICT_OF_TYPES and DICT_OF_C_TYPES into a single object.
    """

    def __init__(self) -> None:
        self.types = {}  # name → Python class
        self.c_types = {}  # name → ctypes struct type

    def _ensure_registered(self, resolved: type) -> type:
        """Register a specialization unless it already is (Object specializations register
        themselves in __class_getitem__; registering twice would re-evaluate self-referential
        fields such as `links: array[M, Node[K, V]]` forever)."""
        if hasattr(resolved, '_n_register_type') and self.types.get(getattr(resolved, '__name__', None)) is not resolved:
            resolved._n_register_type()
        return resolved

    def get_or_eval_type(self, t_name: str, caller_globals: dict | None = None) -> type:
        if not isinstance(t_name, str):
            return t_name
        if t_name in self.types:
            return self.types[t_name]
        if caller_globals and t_name in caller_globals:
            return caller_globals[t_name]
        # t_name is not in self.types, so needs to be resolved and registered.
        if "[" in t_name and t_name.endswith("]"):
            base, params = t_name[:-1].split("[", 1)
            base_type = self.types.get(base)
            if base_type is None and caller_globals and base in caller_globals:
                base_type = caller_globals[base]
            if base_type is not None:
                if base == "array":
                    n_str, _ntype = _n_split_type_args(params)
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
                    resolved = base_type[(n, self.get_or_eval_type(_ntype.strip(), caller_globals))]
                    return self._ensure_registered(resolved)
                elif len(_n_split_type_args(params)) > 1:
                    param_types = tuple(self.get_or_eval_type(p, caller_globals) for p in _n_split_type_args(params))
                    resolved = base_type[param_types]
                    return self._ensure_registered(resolved)
                else:
                    resolved = base_type[self.get_or_eval_type(params.strip(), caller_globals)]
                    return self._ensure_registered(resolved)
        try:
            type_obj = eval(t_name, caller_globals or {})
            if isinstance(type_obj, type):
                return type_obj
        except Exception:
            pass
        if t_name.isidentifier():
            placeholder = type(t_name, (Object,), {'_n_forward': True})
            return placeholder
        raise NameError(f"Type '{t_name}' not found")

_n_registry = NTypeRegistry()

# (module, type name) -> [(owner class, field)]: fields typed with a placeholder for a type that is
# declared later in the same type section
_n_forward_fields: dict[tuple[str, str], list[tuple[type, str]]] = {}


def _n_resolve_forward_fields(cls: type) -> None:
    """Nim resolves the types of one `type` section together, so a field may name a type declared
    after its owner. get_or_eval_type returns a placeholder (`_n_forward`) for it; record such fields
    and, when the type itself registers, replace the placeholder by it, so the field gets the real
    type's zero value (nil for a ref) and type checks."""
    if cls.__dict__.get('_n_forward', False):
        return
    for key, field_cls in cls._n_field_types.items():
        if isinstance(field_cls, type) and field_cls.__dict__.get('_n_forward', False):
            _n_forward_fields.setdefault((cls.__module__, field_cls.__name__), []).append((cls, key))
    for owner, key in _n_forward_fields.pop((cls.__module__, cls.__name__), ()):
        owner._n_field_types[key] = cls

# Backward-compatible aliases — these point to the same dict objects
DICT_OF_TYPES = _n_registry.types
DICT_OF_C_TYPES = _n_registry.c_types

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
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        """auto(): a Nim enum counts from 0, each member one more than the previous one."""
        return last_values[-1] + 1 if last_values else 0

    def __str__(self) -> str:
        """Nim `$` of an enum member: its name."""
        return self.name

    def __format__(self, spec: str) -> str:
        return format(str(self), spec)  # `$`: the name, or the enum's own `$` (__str__)

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if "__str__" in cls.__dict__:
            cls.__str__ = _n_str_method(cls.__dict__["__str__"])  # a `$` defined in the enum
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


class _NEnumText(str):
    """The value of an NStrEnum member: its text, made unique by the member's ordinal, so members with
    equal texts (Nim `warnUser = "User", hintUser = "User"`) are distinct members, not aliases. It
    still equals the plain text."""

    def __new__(cls, text: str, ordinal: int):
        obj = super().__new__(cls, text)
        obj._n_ord = ordinal
        return obj

    def __eq__(self, other):
        if isinstance(other, _NEnumText):
            return str.__eq__(self, other) and self._n_ord == other._n_ord
        return str.__eq__(self, other)

    __hash__ = str.__hash__


class NStrEnum(StrEnum):
    """Nim enum whose members have string values: an ordinal enum whose `$` is the text (the member
    name for auto()). Members are distinct even when their texts are equal."""
    __n_members_tuple__ = None
    __n_indices__ = None

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name  # Nim: `$` of a member without a string value is its name

    def __new__(cls, value):
        member = str.__new__(cls, value)
        member._value_ = _NEnumText(value, len(cls._member_names_))
        return member

    def __eq__(self, other):
        if isinstance(other, Enum):
            return self is other
        return str.__eq__(self, other)

    def __ne__(self, other):
        return not self.__eq__(other)

    __hash__ = Enum.__hash__

    @classmethod
    def _missing_(cls, value):
        if not isinstance(value, (str, bytes)) and hasattr(value, "__index__"):
            value = value.__index__()  # E(ordinal) of any integer type (nint, int32, ...)
        if isinstance(value, int):
            if cls.__n_members_tuple__ is None:
                cls._n_set_indices()
            if 0 <= value < len(cls.__n_members_tuple__):
                return cls.__n_members_tuple__[value]
        return super()._missing_(value)

    @classmethod
    def _n_set_indices(cls) -> None:
        cls.__n_members_tuple__ = tuple(cls)
        cls.__n_indices__ = {val: ind for ind, val in enumerate(cls.__n_members_tuple__)}

    @classmethod
    def _n_low_bound(cls) -> StrEnum:
        if cls.__n_members_tuple__ is None:
            cls._n_set_indices()
        return cls.__n_members_tuple__[0]

    @classmethod
    def _n_high_bound(cls) -> StrEnum:
        if cls.__n_members_tuple__ is None:
            cls._n_set_indices()
        return cls.__n_members_tuple__[-1]

    @classmethod
    def _n_count(cls) -> int:
        if cls.__n_members_tuple__ is None:
            cls._n_set_indices()
        return len(cls.__n_members_tuple__)

    @classmethod
    def _n_range(cls, first: StrEnum, last: StrEnum) -> StrEnum:
        if cls.__n_members_tuple__ is None:
            cls._n_set_indices()
        members = cls.__n_members_tuple__
        indices = cls.__n_indices__
        first_ind = indices[first]
        last_ind = indices[last]
        return members[first_ind : last_ind + 1]

    def _n_inrange(item, last: StrEnum) -> StrEnum:
        cls = item.__class__
        if cls.__n_members_tuple__ is None:
            cls._n_set_indices()
        members = cls.__n_members_tuple__
        indices = cls.__n_indices__
        first_ind = indices[item]
        last_ind = indices[last]
        return members[first_ind : last_ind + 1]

    def succ(item, n: int = 1) -> StrEnum:
        cls = item.__class__
        if cls.__n_members_tuple__ is None:
            cls._n_set_indices()
        members = cls.__n_members_tuple__
        indices = cls.__n_indices__
        if item in members:
            ind = indices[item] + n
            if ind >= 0 and ind < len(members):
                res = members[ind]
            else:
                res = None
        else:
            res = None
        return res

    def ord(item) -> int:
        cls = item.__class__
        if cls.__n_members_tuple__ is None:
            cls._n_set_indices()
        ind = cls.__n_indices__[item]
        return ind

    def __int__(self) -> int:
        return self.ord()

    def __index__(self) -> int:
        return self.ord()

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self.ord() < other.ord()
        return super().__lt__(other)

    def __le__(self, other):
        if isinstance(other, self.__class__):
            return self.ord() <= other.ord()
        return super().__le__(other)

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self.ord() > other.ord()
        return super().__gt__(other)

    def __ge__(self, other):
        if isinstance(other, self.__class__):
            return self.ord() >= other.ord()
        return super().__ge__(other)




def succ(item, n: int = 1):
    if hasattr(item, 'succ'):
        return item.succ(n)
    if isinstance(item, Enum):
        cls = item.__class__
        if hasattr(cls, '_n_members_tuple'):
            members = cls._n_members_tuple
        elif hasattr(cls, '__members_tuple__'):
            members = cls.__members_tuple__
        else:
            members = list(cls)
        idx = members.index(item) + n
        if 0 <= idx < len(members):
            return members[idx]
        return None
    return item + n

def pred(item, n: int = 1):
    return succ(item, -n)

def nord(item) -> int:
    if hasattr(item, 'ord'):
        return item.ord()
    if isinstance(item, Enum):
        cls = item.__class__
        if hasattr(cls, '_n_members_tuple'):
            members = cls._n_members_tuple
        elif hasattr(cls, '__members_tuple__'):
            members = cls.__members_tuple__
        else:
            members = list(cls)
        return members.index(item)
    return int(item)


def inrange(first, last):
    if hasattr(first, '_n_inrange'):
        return first._n_inrange(last)
    if isinstance(first, Enum) and isinstance(last, Enum):
        cls = first.__class__
        if hasattr(cls, '_n_members_tuple'):
            members = cls._n_members_tuple
        elif hasattr(cls, '__members_tuple__'):
            members = cls.__members_tuple__
        else:
            members = list(cls)
        idx_a = members.index(first)
        idx_b = members.index(last)
        return members[idx_a : idx_b + 1]
    if isinstance(first, str):  # char: 'a'..'z' is a range of chars
        cls = type(first)
        return tuple(cls(c) for c in range(ord(first), ord(last) + 1))
    else:
        return range(int(first), int(last) + 1)


def subset(newname: str, first: NStrEnum, last: NStrEnum) -> type:
    cls = first.__class__
    return NStrEnum(newname, [(a.name, a.value) for a in inrange(first, last)])


def low(obj: object) -> object:
    if isinstance(obj, type):
        if issubclass(obj, Enum):
            members = list(obj)
            return members[0] if members else 0
        if hasattr(obj, '_n_low_bound'):
            return obj._n_low_bound()
        if hasattr(obj, '_n_low'):
            return obj._n_low
    if hasattr(obj, '__len__'):
        return 0
    if hasattr(obj, '_n_low_bound'):
        return obj._n_low_bound()
    return 0

def high(obj: object) -> object:
    if isinstance(obj, type):
        if issubclass(obj, Enum):
            members = list(obj)
            return members[-1] if members else 0
        if hasattr(obj, '_n_high_bound'):
            return obj._n_high_bound()
        if hasattr(obj, '_n_high'):
            return obj._n_high
    if hasattr(obj, '__len__'):
        return len(obj) - 1
    if hasattr(obj, '_n_high_bound'):
        return obj._n_high_bound()
    return 0


class NBool:
    """ctypes-backed bool — harmonizes with NScalar pattern for struct embedding. A field or array
    slot is a view (`_n_on_struct` / `_n_on_array`), a plain NBool holds its value; both are cells
    that `<<=` changes in place (a `var bool` parameter)."""

    def __init__(self, value=False):
        self._n_cell = bool(value)

    def _n_get_value(self):
        return self._n_cell

    def _n_set_value(self, value):
        self._n_cell = bool(value._n_get_value() if isinstance(value, NBool) else value)

    @property
    def _n_value(self):
        return self._n_get_value()

    def __int__(self):
        return int(self._n_value)

    def __float__(self):
        return float(self._n_value)

    def __bool__(self):
        return self._n_value

    def __repr__(self):
        return repr(self._n_value)

    def __str__(self):
        """Nim `$`: true / false."""
        return "true" if self._n_value else "false"

    def __eq__(self, other):
        if isinstance(other, NBool):
            return self._n_value == other._n_value
        return self._n_value == other

    def __ilshift__(self, other):
        """Assignment through a `var bool` parameter (`flag <<= True`): changes the caller's cell."""
        self._n_set_value(other)
        return self

    def copy(self):
        """A new cell with this value (`with var: b = a.copy()` before passing `b` as `var`)."""
        return NBool(self._n_value)

    @classmethod
    def _n_view(cls, getter, setter, value=None):
        """A cell reading and writing storage it doesn't own (the instance's accessors replace the
        class's; the class stays NBool, so dispatch and isinstance see a bool)."""
        self = cls.__new__(cls)
        self._n_get_value = getter
        self._n_set_value = lambda v: setter(bool(v._n_get_value() if isinstance(v, NBool) else v))
        if value is not None:
            self._n_set_value(value)
        return self

    @classmethod
    def _n_on_struct(cls, parent_elems, id, value=None):
        """Struct-embedded: reads/writes via ctypes struct field."""
        return cls._n_view(lambda: bool(getattr(parent_elems, id)),
                           lambda v: setattr(parent_elems, id, v), value)

    @classmethod
    def _n_on_array(cls, parent_elems, index, value=None):
        """Array-embedded: reads/writes via ctypes array slot."""
        return cls._n_view(lambda: bool(parent_elems[index]),
                           lambda v: parent_elems.__setitem__(index, v), value)

    @classmethod
    def _n_sizeof(cls):
        return ctypes.sizeof(ctypes.c_bool)


# A mutable Nim bool, for a variable passed as `var bool` (Nim `var b = false`: `with var: b = nbool(False)`),
# as nint is for `var int`; plain Nim bools are Python bools
nbool = NBool


# --- Dispatch Metaclass (DispDict / NMetaClass) ---


class _NUnset:
    """Value of an annotated class-body name that has no default (a variant
    discriminator read by `match kind:`). Equal to nothing, so no branch matches."""

    def __repr__(self) -> str:
        return "<unset discriminator>"

    def __eq__(self, other) -> bool:
        return False

    def __ne__(self, other) -> bool:
        return True

    __hash__ = object.__hash__


_N_UNSET = _NUnset()


class DispDict(dict):
    def __missing__(self, key: str):
        # class-body read of an annotated name without a default (`kind: K` then `match kind:`);
        # anything else falls through to globals/builtins (CPython LOAD_NAME honours __missing__)
        if key in dict.get(self, "__annotations__", {}):
            self._n_unset_read = True
            return _N_UNSET
        raise KeyError(key)

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

    def __new__(mcs, name: str, bases: tuple, namespace: DispDict, **kwargs):
        # set before type.__new__ so __init_subclass__ (type registration) can see them
        if getattr(namespace, "_n_unset_read", False):
            namespace["_n_body_has_case"] = True
        if "_n_caller_globals" not in namespace:
            # the defining module's globals: frame 1 runs the class statement
            frame = sys._getframe(1)
            namespace["_n_caller_globals"] = frame.f_globals
            if frame.f_locals is not frame.f_globals:  # class defined inside a function
                namespace["_n_caller_locals"] = dict(frame.f_locals)
        if isinstance(namespace.get("__str__"), types.FunctionType):
            dict.__setitem__(namespace, "__str__", _n_str_method(namespace["__str__"]))  # a `$` defined in the class
        return super().__new__(mcs, name, bases, dict(namespace), **kwargs)




class Trange:
    """Nim's ``range[low..high]`` subrange type. ``Trange[warnMin, hintMax]``
    returns a base class that carries the bounds. Subclass it to create a named
    range type::

        class TNoteKind(Trange[TMsgKind.errUnknown, TMsgKind.errFatal]): pass

    Supports ``low(TNoteKind)``, ``high(TNoteKind)``, and ``_n_count()`` for
    array sizing via ``array[Trange[...], T]``."""
    _n_cache: dict = {}

    def __class_getitem__(cls, params):
        lo, hi = params
        key = (id(lo), id(hi))
        if key not in cls._n_cache:
            name = f'Trange[{lo}, {hi}]'
            new_cls = type(name, (cls,), {
                '_n_low': lo,
                '_n_high': hi,
            })
            # the low()/high() protocol, and the number of values
            new_cls._n_low_bound = classmethod(lambda c: c._n_low)
            new_cls._n_high_bound = classmethod(lambda c: c._n_high)
            new_cls._n_count = classmethod(
                lambda c: nord(c._n_high) - nord(c._n_low) + 1
            )
            cls._n_cache[key] = new_cls
        return cls._n_cache[key]


class Tset(set):
    """Nim's ``set[T]`` for ordinal types. ``Tset[MyEnum]`` returns a proper
    ``set`` subclass that can be instantiated, used in ``isinstance()``, and
    inherited from.  Results are cached so ``Tset[X] is Tset[X]``."""
    _n_cache: dict = {}

    def __str__(self) -> str:
        """Nim `$` of a set: the elements in ordinal order, `{a, b}`."""
        key = lambda x: x._n_byte if isinstance(x, char) else nord(x)
        return _n_collection_str("{", sorted(self, key=key), "}")

    def __init__(self, *items):
        """Nim set constructor `{a, b..c}`: `Tset[T](a, inrange(b, c))` or `Tset[T]({a, inrange(b, c)})`;
        a single iterable argument (another set, `inrange(b, c)`, a char) gives its members."""
        if len(items) == 1 and isinstance(items[0], collections.abc.Iterable):
            items = items[0]
        members = []
        for item in items:
            if isinstance(item, (tuple, list, range, set, frozenset)):  # a range: elements are ordinals
                members.extend(item)
            else:
                members.append(item)
        super().__init__(members)

    def incl(self, elem):
        self.add(elem)

    def excl(self, elem):
        self.discard(elem)

    def contains_or_incl(self, elem):
        if elem in self:
            return True
        self.add(elem)
        return False

    def contains(self, elem):
        return elem in self

    def __ilshift__(self, other):
        """Value assignment (Nim `s = other` through a var parameter): replace the members in place."""
        if other is not self:
            self.clear()
            self.update(other)
        return self

    def copy(self):
        return type(self)(self)

    def __copy__(self):
        return type(self)(self)

    def __or__(self, other):
        return type(self)(super().__or__(other))

    def __and__(self, other):
        return type(self)(super().__and__(other))

    def __sub__(self, other):
        return type(self)(super().__sub__(other))

    def __xor__(self, other):
        return type(self)(super().__xor__(other))

    def __add__(self, other):
        return type(self)(set.__or__(self, other))

    def __radd__(self, other):
        return type(self)(set.__or__(self, other))

    def __mul__(self, other):
        return type(self)(set.__and__(self, other))

    def __rmul__(self, other):
        return type(self)(set.__and__(self, other))

    def __class_getitem__(cls, elem_type):
        if elem_type not in cls._n_cache:
            name = f'Tset[{elem_type.__name__}]'
            # Override set operations to preserve the subclass type
            def _make_op(op_name):
                def _op(self, other):
                    return type(self)(getattr(set, op_name)(self, other))
                return _op
            new_cls = type(name, (cls,), {
                '_elem_type': elem_type,
                '__sub__': _make_op('__sub__'),
                '__rsub__': lambda self, other: type(self)(set.__sub__(other, self)),
                '__and__': _make_op('__and__'),
                '__rand__': _make_op('__and__'),
                '__or__': _make_op('__or__'),
                '__ror__': _make_op('__or__'),
                '__xor__': _make_op('__xor__'),
                '__rxor__': _make_op('__xor__'),
                '__add__': _make_op('__or__'),
                '__radd__': _make_op('__or__'),
                '__mul__': _make_op('__and__'),
                '__rmul__': _make_op('__and__'),
            })
            cls._n_cache[elem_type] = new_cls
        return cls._n_cache[elem_type]


# --- Structured Objects (Object) ---

def _n_is_nilable(fc: object) -> bool:
    """True if `nil` is a valid value of type `fc`: ref, ptr, pointer and proc (calltype) types."""
    if getattr(fc, '_n_is_calltype', False) or getattr(fc, '_n_is_ref', False) or getattr(fc, '_n_is_ptr', False):
        return True
    _pointer = DICT_OF_TYPES.get("pointer")
    return bool(isinstance(fc, type) and _pointer and issubclass(fc, _pointer))


def _n_default_value(fc: object) -> object:
    """Nim's zero value for a field / element type `fc` (default(T))."""
    if isinstance(fc, TypeAliasType):  # `type D = dict[str, int]`
        return _n_default_value(fc.__value__)
    if not isinstance(fc, type) and getattr(fc, '__origin__', None) is tuple and getattr(fc, '__args__', None):
        return tuple(_n_default_value(a) for a in fc.__args__)  # anonymous tuple type `tuple[char, nint]`
    if not isinstance(fc, type) and isinstance(getattr(fc, '__origin__', None), type):
        return _n_default_value(fc.__origin__)  # generic alias such as dict[str, int]
    if not isinstance(fc, type):
        return None  # e.g. an unbound type variable
    if _n_is_nilable(fc):
        return None
    if issubclass(fc, Enum):
        return low(fc)
    if fc is bool:
        return False
    try:
        return fc()  # seq, Object, array, NBool, NScalar, string, ... default-construct
    except TypeError:  # type without a no-argument constructor
        return None


def _n_disc_ordinal(value: object) -> int:
    """Discriminator identity for branch selection: the stored integer value (what the
    ctypes view holds), so pattern values and raw view reads compare equal."""
    if isinstance(value, Enum) and not isinstance(value, int):
        return nord(value)  # e.g. NStrEnum: no integer value, use the member index
    return int(value)


_n_module_asts: dict = {}


def _n_class_def(cls: type) -> ast.ClassDef | None:
    """The ClassDef of `cls` in its source file, found by __qualname__ (also inside
    functions and `if comptime(...)` blocks). None when the source is unavailable.
    Each module is parsed once."""
    try:
        filename = ins.getsourcefile(cls)
    except (OSError, TypeError):
        return None
    if not filename:
        return None
    tree = _n_module_asts.get(filename)
    if tree is None:
        lines = linecache.getlines(filename)
        if not lines:
            return None
        tree = _n_module_asts[filename] = ast.parse("".join(lines))

    def scope_defs(stmts):
        for s in stmts:
            if isinstance(s, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                yield s
            else:  # if / with / try / for / while bodies stay in the same scope
                for field in ("body", "orelse", "finalbody", "handlers", "cases"):
                    sub = getattr(s, field, None)
                    if isinstance(sub, list):
                        yield from scope_defs(sub if field not in ("handlers", "cases")
                                              else [x for h in sub for x in h.body])

    nodes = [tree]
    for part in cls.__qualname__.split("."):
        if part == "<locals>":
            continue
        nodes = [d for n in nodes for d in scope_defs(n.body) if d.name == part]
        if not nodes:
            return None
    candidates = [n for n in nodes if isinstance(n, ast.ClassDef)]
    if not candidates:
        return None
    # same name defined more than once (e.g. under alternative `if comptime(...)` branches):
    # prefer the definition whose top-level fields match the class's own annotations
    own = set(cls.__dict__.get("__annotations__", {}))
    return max(candidates, key=lambda c: len(own & {s.target.id for s in c.body
                                                  if isinstance(s, ast.AnnAssign)
                                                  and isinstance(s.target, ast.Name)}))


def _n_subst_type_vars(type_str: object, T_map: dict) -> object:
    """Substitute type-parameter names in an annotation string (generic specialization)."""
    if not isinstance(type_str, str) or not T_map:
        return type_str
    # whole identifiers only: `V` must not rewrite the V inside `MockVariantNode`
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, T_map)) + r")\b")
    return pattern.sub(lambda m: T_map[m.group(1)], type_str)


def _n_c_field_type(field_cls: object) -> object:
    """ctypes type of a ctypes-backed field, or None."""
    is_class = isinstance(field_cls, type)
    _pointer = DICT_OF_TYPES.get("pointer")
    _ua = DICT_OF_TYPES.get("UncheckedArray")
    if is_class and ((_pointer and issubclass(field_cls, _pointer)) or getattr(field_cls, '_n_is_ref', False)):
        return ctypes.c_void_p  # pointer, ptr[X] or ref object
    if getattr(field_cls, '__name__', None) in DICT_OF_C_TYPES:
        return DICT_OF_C_TYPES[field_cls.__name__]  # scalars, cstring, Object structs, arrays
    if getattr(field_cls, '_n_is_calltype', False):
        return ctypes.c_void_p  # proc type → opaque pointer
    if is_class and _ua and issubclass(field_cls, _ua):
        return ctypes.c_uint8 * 0  # flexible array member
    return None


def _n_build_c_fields(items: tuple, field_types: dict, python_fields: set, prefix: str) -> tuple[list, list]:
    """ctypes `_fields_` and `_anonymous_` for record items (Nim C layout, N2): common
    fields in order; each case = its discriminator, then an anonymous union of one
    anonymous struct per branch, so branch fields are promoted with correct offsets."""
    fields, anonymous = [], []
    for it in items:
        if isinstance(it, NField):
            if it.name not in python_fields:
                ct = _n_c_field_type(field_types.get(it.name))
                if ct is not None:
                    fields.append((it.name, ct))
            continue
        disc = it.discriminator.name
        if disc not in python_fields:
            ct = _n_c_field_type(field_types.get(disc))
            if ct is not None:
                fields.append((disc, ct))
        members = []
        for i, br in enumerate(it.branches):
            b_fields, b_anon = _n_build_c_fields(br.items, field_types, python_fields, f"{prefix}_{disc}_b{i}")
            members.append((f"_n_b{i}", type(f"{prefix}_{disc}_b{i}", (ctypes.Structure,),
                                              {"_anonymous_": tuple(b_anon), "_fields_": b_fields})))
        union = type(f"{prefix}_u_{disc}", (ctypes.Union,),
                     {"_anonymous_": tuple(name for name, _ in members), "_fields_": members})
        fields.append((f"_n_u_{disc}", union))
        anonymous.append(f"_n_u_{disc}")
    return fields, anonymous


def _n_coerce_int_field(cls: type, name: str, value: object) -> object:
    """A plain int stored in a Python-side integer field becomes the field's declared type (a
    mutable NInteger, so the field can be passed as `var int`)."""
    if type(value) is int and name in getattr(cls, "_n_python_fields", ()):
        ft = getattr(cls, "_n_field_types", {}).get(name)
        if isinstance(ft, type) and issubclass(ft, NInteger):
            return ft(value)
    return value


def _n_nim_operator(obj: object, name: str, a: object, b: object) -> object:
    """Calls the operator `name` of obj's type as `name(a, b)` (Nim order); NotImplemented when the type
    defines no such operator, so Python raises its TypeError."""
    op = getattr(type(obj), name, None)
    if op is None or op is getattr(object, name, None):
        return NotImplemented
    return op(a, b)


class _Object(Ntype):
    # Cache for specialized generic classes
    _n_specializations = {}

    def __eq__(self, other) -> bool:
        """Nim `==` of objects and tuples: the same type and equal fields (the active ones of a
        variant); refs compare as references. A user-defined `==` (__eq__) replaces this."""
        if self is other:
            return True
        if not isinstance(other, _Object):
            return NotImplemented
        if type(other) is not type(self) or getattr(type(self), "_n_is_ref", False):
            return False
        names = type(self).__dict__.get("_n_fields") or getattr(type(self), "_n_fields", [])
        if getattr(type(self), "_n_variant_layout", None) is not None:
            active = set(self.__dict__.get("_n_fields", names))
            if active != set(other.__dict__.get("_n_fields", names)):
                return False
            names = [n for n in names if n in active]
        return all(getattr(self, n) == getattr(other, n) for n in names)

    __hash__ = object.__hash__  # Nim's `hash` is independent of `==`

    # Nim has no reflected operators: `proc +(a: BiggestInt, b: T)` is an ordinary overload with that
    # parameter order, and `>` / `>=` are system templates for `<` / `<=` with swapped arguments.
    # Python calls these methods when the left operand (e.g. an int64) does not handle the right one, or
    # for `a > b`: they call the operator overload in Nim's order.
    def __gt__(self, other):
        return _n_nim_operator(self, "__lt__", other, self)

    def __ge__(self, other):
        return _n_nim_operator(self, "__le__", other, self)

    def __radd__(self, other):
        return _n_nim_operator(self, "__add__", other, self)

    def __rsub__(self, other):
        return _n_nim_operator(self, "__sub__", other, self)

    def __rmul__(self, other):
        return _n_nim_operator(self, "__mul__", other, self)

    def __rtruediv__(self, other):
        return _n_nim_operator(self, "__truediv__", other, self)

    def __rfloordiv__(self, other):
        return _n_nim_operator(self, "__floordiv__", other, self)

    def __rmod__(self, other):
        return _n_nim_operator(self, "__mod__", other, self)

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
        resolved = {attr_name: _n_subst_type_vars(type_str, T_map)
                    for attr_name, type_str in cls.__annotations__.items()}
        record = getattr(cls, '_n_record', None)

        # Create specialized subclass. Registration is deferred until the class is
        # cached, so self-referential fields (links: array[M, Node[K, V]]) resolve to it.
        suffix = "_".join(T_map.values())
        specialized_name = f"{cls.__name__}[{suffix}]"
        caller_globals = getattr(cls, '_n_caller_globals', {})
        specialized = type(specialized_name, (cls,), {
            '__annotations__': resolved,
            '_n_caller_globals': caller_globals,
            '_n_caller_locals': getattr(cls, '_n_caller_locals', None),
            '_n_record': record.map_annotations(lambda a: _n_subst_type_vars(a, T_map)) if record else None,
            '_n_defer_register': True,
        })
        _Object._n_specializations[cache_key] = specialized
        specialized._n_register_type()
        return specialized

    @classmethod
    def _n_build_record(cls) -> NRecord | None:
        """The record (declaration tree) of this class, parsed once from its source and
        cached as cls._n_record. A subclass appends its own fields to a variant base's
        record (Nim inheritance); a class without own fields inherits the base record.
        Specializations receive the record from __class_getitem__."""
        if "_n_record" in cls.__dict__:
            return cls.__dict__["_n_record"]
        base_record = next((b.__dict__["_n_record"] for b in cls.__mro__[1:]
                            if b.__dict__.get("_n_record") is not None), None)
        own_record = None
        if cls.__dict__.get("__annotations__") or cls.__dict__.get("_n_body_has_case"):
            class_def = _n_class_def(cls)
            if class_def is not None:
                own_record = parse_record(class_def)
            elif cls.__dict__.get("_n_body_has_case"):
                raise TypeError(f"variant object {cls.__name__} needs its source (define it in a .py file)")
        if own_record is None:
            record = base_record if base_record is not None and base_record.is_variant else None
        elif base_record is not None and base_record.is_variant:
            record = NRecord(base_record.items + own_record.items)
        else:
            record = own_record
        cls._n_record = record
        return record

    def _n_field_defect_msg(self, name: str) -> str:
        """Nim: field 'x' is not accessible for type 'T' using 'kind = k'."""
        layout = type(self)._n_variant_layout
        case = layout.owner_case(name)
        if case is None:
            return f"field '{name}' is not accessible for type '{type(self).__name__}'"
        disc = case.discriminator.name
        value = self._n_typed_disc(disc, self.__dict__.get("_n_discs", {}).get(disc))
        return (f"field '{name}' is not accessible for type '{type(self).__name__}' "
                f"using '{disc} = {getattr(value, 'name', value)}'")

    def __getattr__(self, name: str) -> object:
        # only reached when normal lookup fails: an inactive variant field never lives in
        # __dict__ (python-side) nor is bound to the view (ctypes-side)
        layout = getattr(type(self), "_n_variant_layout", None)
        if (layout is not None and name in layout.fields and "_n_discs" in self.__dict__
                and name not in self.__dict__.get("_n_fields", ())):
            raise FieldDefect(self._n_field_defect_msg(name))
        if not name.startswith(("__", "_n_")):
            # Nim method-call syntax (UFCS): `obj.f(args)` calls the proc `f(obj, args)` visible in the
            # caller's scope (e.g. `builder.addArgumentSeparator()`, `b.addCast(t):` for a template),
            # private procs (`_sdata`) included; dunders and nimic internals (`_n_*`) are never procs
            frame = sys._getframe(1)
            while frame is not None and frame.f_code.co_filename.startswith(_N_RUNTIME_DIR):
                frame = frame.f_back
            if frame is not None:
                proc = frame.f_locals.get(name, frame.f_globals.get(name))
                if callable(proc) and not isinstance(proc, type):
                    return functools.partial(proc, self)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

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
    def _n_cast(cls, instance):
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
        if getattr(type(self), '_n_variant_layout', None) is not None:
            self._n_init_variant(_n_value, kwargs)
            return
        python_fields = getattr(self.__class__, '_n_python_fields', set())
        field_types = getattr(self.__class__, '_n_field_types', {})
        # Initialize python-side fields (seq and Object subclasses without ctypes backing)
        for name in python_fields:
            setattr(self, name, _n_default_value(field_types.get(name)))

        _has_c_type = type(self).__name__ in DICT_OF_C_TYPES
        if kwargs:
            for attribute in kwargs:
                # Nim object constructors copy values (strings, seqs, objects) and share refs
                setattr(self, attribute, _n_value_copy(kwargs[attribute]))
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

    # --- object variants (case objects) ---

    def _n_init_variant(self, _n_value: Object | None, kwargs: dict) -> None:
        """Nim N3: discriminators first (given, or their zero value), then only the fields of
        the selected branches are initialized; a field of another branch is an error."""
        cls = type(self)
        layout = cls._n_variant_layout
        field_types = cls._n_field_types
        if _n_value is not None and not kwargs:
            discs = dict(_n_value._n_discs) if '_n_discs' in getattr(_n_value, '__dict__', {}) else \
                {d: getattr(_n_value, d) for d in layout.discriminators}
        else:
            discs = {d: kwargs[d] if d in kwargs else _n_default_value(field_types.get(d))
                     for d in layout.discriminators}
        active = layout.active_fields(discs)
        set_attr = super(_Object, self).__setattr__
        set_attr('_n_discs', discs)
        set_attr('_n_fields', list(active))
        set_attr('_n_annotations', cls.__annotations__)
        for name in kwargs:
            if name in layout.fields and name not in active:
                raise FieldDefect(self._n_field_defect_msg(name))
        python_fields = cls._n_python_fields
        for name in active:
            if name in python_fields:
                set_attr(name, _n_default_value(field_types.get(name)))
        if cls.__name__ in DICT_OF_C_TYPES:
            _buf = DICT_OF_C_TYPES[cls.__name__]()
            self._n_owned_addr = BUFFER_REGISTRY.register(_buf)
            self._n_view = _buf
            disc_source = types.SimpleNamespace(**discs)  # discriminators are written, not read
            for name in active:
                self._n_bind_field(name, disc_source if name in discs else None)
        else:
            for d in layout.discriminators:
                if d in active:
                    setattr(self, d, discs[d])
        source = _n_value if _n_value is not None and not kwargs else None
        for name in active:
            if name in kwargs:
                setattr(self, name, _n_value_copy(kwargs[name]))
            elif source is not None and name not in layout.discriminators:
                setattr(self, name, getattr(source, name))

    def _n_typed_disc(self, name: str, raw: object) -> object:
        """A discriminator value as its declared type (an enum member rather than an int)."""
        ft = type(self)._n_field_types.get(name)
        if isinstance(ft, type) and issubclass(ft, Enum) and not isinstance(raw, ft) and raw is not None:
            try:
                return ft(raw)
            except ValueError:
                return raw
        return raw

    def _n_disc_values(self, value: Object | None) -> dict:
        """Discriminators of a view-backed object: from `value` when given, else from the view."""
        layout = type(self)._n_variant_layout
        if value is not None:
            if '_n_discs' in getattr(value, '__dict__', {}):
                return dict(value._n_discs)
            return {d: getattr(value, d) for d in layout.discriminators}
        view = getattr(self, '_n_view', None)
        field_types = type(self)._n_field_types
        discs = {}
        for d in layout.discriminators:
            if view is not None and d not in type(self)._n_python_fields:
                value = self._n_typed_disc(d, getattr(view, d))
                ft = field_types.get(d)
                if isinstance(ft, type) and issubclass(ft, Enum) and not isinstance(value, ft):
                    # zero-initialized memory of an enum without a 0 member (e.g. auto() starting
                    # at 1): Nim's default(K) is low(K); store it so the view is consistent
                    value = _n_default_value(ft)
                    setattr(view, d, _n_disc_ordinal(value))
                discs[d] = value
            else:
                discs[d] = _n_default_value(field_types.get(d))
        return discs

    def _n_switch_branch(self, new_discs: dict) -> None:
        """Make the branches selected by `new_discs` active: drop the python-side fields of
        deactivated branches, default the newly active python-side fields, and bind the
        newly active ctypes fields WITHOUT zeroing (the union memory is reused, as in Nim)."""
        cls = type(self)
        old_active = set(self._n_fields)
        new_active = cls._n_variant_layout.active_fields(new_discs)
        for name in old_active.difference(new_active):
            self.__dict__.pop(name, None)
        set_attr = super(_Object, self).__setattr__
        set_attr('_n_discs', dict(new_discs))
        set_attr('_n_fields', list(new_active))
        for name in new_active:
            if name in old_active:
                continue
            if name in cls._n_python_fields:
                set_attr(name, _n_default_value(cls._n_field_types.get(name)))
            elif getattr(self, '_n_view', None) is not None:
                self._n_bind_field(name, None)

    def _n_check_variant_access(self, name: str, value: object) -> None:
        """Nim N4/N5/N7 for an assignment to field `name` of a variant object."""
        layout = type(self)._n_variant_layout
        discs = self._n_discs
        if name not in self._n_fields:
            raise FieldDefect(self._n_field_defect_msg(name))
        if name in layout.discriminators:
            new_discs = {**discs, name: value}
            if layout.branch_key(new_discs) != layout.branch_key(discs):
                if not _n_unchecked_assign_active():
                    raise FieldDefect("assignment to discriminant changes object branch")
                self._n_switch_branch(new_discs)
            else:
                discs[name] = value

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
        """Initialize object fields after construction (view-backed or copied objects).

        Variant objects first determine their discriminators (from `value`, else from the
        view) and expose only the fields of the active branches."""
        layout = getattr(type(self), '_n_variant_layout', None)
        if layout is not None:
            discs = self._n_disc_values(value if value is not self else None)
            set_attr = super(_Object, self).__setattr__
            set_attr('_n_discs', discs)
            set_attr('_n_annotations', self.__annotations__)
            set_attr('_n_fields', list(layout.active_fields(discs)))
        else:
            self._n_annotations = self.__annotations__
            self._n_fields = list(self.__annotations__)
        self._n_set_value(value)

    def __setattr__(self, name: str, value: object) -> None:
        layout = type(self).__dict__.get('_n_variant_layout') or getattr(type(self), '_n_variant_layout', None)
        if layout is not None and name in layout.fields and '_n_discs' in self.__dict__:
            self._n_check_variant_access(name, value)
        attr_exists = (
            hasattr(self, name)
            and hasattr(self, "_n_fields")
            and name in self._n_fields
        )
        if attr_exists:
            python_fields = getattr(self.__class__, '_n_python_fields', set())
            if (python_fields and name in python_fields) or not hasattr(self, '_n_view') or self._n_view is None:
                super().__setattr__(name, _n_coerce_int_field(type(self), name, value))
                return

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
                if isinstance(attr, bool):
                    super().__setattr__(name, value)
                elif isinstance(attr, NIntEnum):
                    if hasattr(attr, "_n_set_value"):
                        attr._n_set_value(int(value))
                    if hasattr(self, "_n_view") and self._n_view is not None:
                        _val = type(attr)._n_on_struct(self._n_view, name, int(value))
                    else:
                        _val = type(attr)(int(value))
                    super().__setattr__(name, _val)
                elif hasattr(attr, "_n_set_value") and getattr(type(attr), "_n_set_value", None) is not Ntype._n_set_value:
                    attr._n_set_value(value)
                else:
                    super().__setattr__(name, value)
            else:
                super().__setattr__(name, _n_coerce_int_field(type(self), name, value))
        else:
            super().__setattr__(name, _n_coerce_int_field(type(self), name, value))

    def __getitem__(self, name: str) -> object:
        if name not in self._n_fields:
            layout = getattr(type(self), '_n_variant_layout', None)
            if layout is not None and name in layout.fields:
                raise FieldDefect(self._n_field_defect_msg(name))
            raise KeyError(name)
        return getattr(self, name)

    def __setitem__(self, name: str, value: object) -> None:
        if name not in self._n_fields:
            layout = getattr(type(self), '_n_variant_layout', None)
            if layout is not None and name in layout.fields:
                raise FieldDefect(self._n_field_defect_msg(name))
            raise KeyError(name)
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
        layout = getattr(type(self), '_n_variant_layout', None)
        if layout is not None and other is not None and other is not self and '_n_discs' in self.__dict__:
            # Nim N6: replacing the whole object selects the other object's branches
            self._n_switch_branch(self._n_disc_values(other))
        for name in list(self._n_fields):
            self._n_bind_field(name, other)

    def _n_bind_field(self, name: str, other: Object | None) -> None:
        """Bind field `name` to the view (ctypes-side) or set it (python-side), copying the
        value from `other` when given."""
        python_fields = getattr(self.__class__, '_n_python_fields', set())
        field_types = getattr(self.__class__, '_n_field_types', {})
        _ua = DICT_OF_TYPES.get("UncheckedArray")
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
            return

        # B. Ctypes-backed fields with _n_on_struct
        if name not in python_fields and hasattr(field_cls, '_n_on_struct') and not getattr(field_cls, '_n_is_ref', False):
            val = getattr(other, name, None) if other else None
            if val is not None:
                setattr(self, name, field_cls._n_on_struct(self._n_view, name, val))
            else:
                setattr(self, name, field_cls._n_on_struct(self._n_view, name))
            return

        # C. Python-side fields (pointers→NilPtr, calltypes→None, seq→already init'd, etc.)
        if other and (hasattr(other, name) if other is not self else name in other.__dict__):
            value = getattr(other, name)
            if other is not self:
                value = _n_value_copy(value)  # Nim assignment copies values (string, seq, objects)
            super(_Object, self).__setattr__(name, value)
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
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(cls._n_c_type())  # get type size in bytes

    @classmethod
    def _n_register_type(cls) -> None:
        """Register this Object subclass in the global type registries.

        Called automatically via __init_subclass__. Handles:
          - Object inheritance: inherits base class fields in MRO order
          - Alias types: @ref or _n_is_alias with no annotations
          - Variant types (object variants): all branch fields from the declaration
            record, NVariantLayout, ctypes anonymous unions per case
          - Regular structs: builds a ctypes.Structure with _fields_
        """
        dict_of_types, dict_of_c_types = DICT_OF_TYPES, DICT_OF_C_TYPES
        caller_globals = cls._n_caller_globals

        # Collect inherited annotations from base Object classes (base first, derived last)
        inherited_annotations = {}
        for base in reversed(cls.__mro__[1:]):
            if base is not object and base is not Ntype and issubclass(base, _Object):
                ann = getattr(base, '_n_annotations', getattr(base, '__annotations__', {}))
                inherited_annotations.update(ann)

        own_annotations = getattr(cls, '__annotations__', {})
        class_name = cls.__name__

        if len(own_annotations) == 0 and len(cls.__bases__) > 0 and issubclass(cls.__bases__[0], _Object):
            base_name = cls.__bases__[0].__name__
            # Only treat as alias if it's explicitly a reference type (e.g. @ref PLLStream)
            # or if marked with _n_is_alias. Normal subclasses are genuine Object subtypes!
            if getattr(cls, '_n_is_ref', False) or getattr(cls, '_n_is_alias', False):
                if base_name in _n_aliases:
                    _n_aliases[cls.__name__] = _n_aliases[base_name]
                else:
                    _n_aliases[cls.__name__] = base_name

        record = getattr(cls, '_n_record', None)
        is_variant = record is not None and record.is_variant
        if is_variant:
            # the declaration is the source of truth: every field of every branch is part
            # of the type (N1); own __annotations__ may hold branch fields leaked by a
            # legacy dummy discriminator default, and miss the other branches
            own_annotations = {name: f.annotation for name, f in record.all_fields().items()}
            inherited_annotations = {k: v for k, v in inherited_annotations.items()
                                     if k not in own_annotations}

        # Merge base annotations + own annotations
        merged_annotations = dict(inherited_annotations)
        merged_annotations.update(own_annotations)
        cls.__annotations__ = merged_annotations

        _annotations = cls.__annotations__
        cls._n_annotations = _annotations
        cls._n_fields = list(_annotations.keys())
        dict_of_types[class_name] = cls  # add to dict for resolver

        # resolve types. Generic types, such as ptr[UncheckedArray[T]], should be specialized first
        cls._n_field_types = {key: _n_registry.get_or_eval_type(_type_name, caller_globals)
            for key, _type_name in _annotations.items()}
        _n_resolve_forward_fields(cls)
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
            if is_class and ((_pointer and issubclass(field_cls, _pointer)) or getattr(field_cls, '_n_is_ref', False)):
                return True  # pointer/ptr[X] or ref object → c_void_p
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
                (_ua and issubclass(fc, _ua)) or
                getattr(fc, '_n_is_ref', False)
            )}
        dict_of_types[class_name] = cls
        if is_variant:
            caller_locals = getattr(cls, '_n_caller_locals', None)
            cls._n_variant_layout = NVariantLayout(
                record, eval_value=lambda src: eval(src, caller_globals, caller_locals),
                ordinal=_n_disc_ordinal)
            cls._n_check_exhaustive()
        else:
            cls._n_variant_layout = None
        has_c_type = len(python_fields) < len(_annotations)
        if has_c_type:
            c_class_name = "c_" + class_name
            if is_variant:
                # common fields of inherited (non-record) bases first, then the record (N2)
                flat = tuple(NField(k, v) for k, v in inherited_annotations.items())
                f_list, anonymous = _n_build_c_fields(flat + record.items, cls._n_field_types,
                                                      python_fields, c_class_name)
            else:
                flat = tuple(NField(k, v) for k, v in _annotations.items())
                f_list, anonymous = _n_build_c_fields(flat, cls._n_field_types, python_fields, c_class_name)
            _c_type = type(c_class_name, (ctypes.Structure,), {"_anonymous_": tuple(anonymous), "_fields_": f_list})
            dict_of_c_types[class_name] = _c_type

    @classmethod
    def _n_check_exhaustive(cls) -> None:
        """Nim N8: a case on an enum/bool discriminator must cover every value or have
        `case _`; for other ordinal types a missing `case _` only warns."""
        layout = cls._n_variant_layout
        for case in layout.record.cases():
            disc = case.discriminator.name
            ft = cls._n_field_types.get(disc)
            if isinstance(ft, type) and issubclass(ft, Enum):
                all_values = {_n_disc_ordinal(m) for m in ft}
            elif ft is bool or (isinstance(ft, type) and issubclass(ft, NBool)):
                all_values = {0, 1}
            else:
                if all(br.values is not None for br in case.branches):
                    warnings.warn(f"{cls.__name__}: case on '{disc}' has no `case _`; "
                                  f"values without a branch have no fields", stacklevel=4)
                continue
            try:
                exhaustive = layout.is_exhaustive(case, all_values)
            except NameError:
                continue  # a pattern names something defined later: checked on first use
            if not exhaustive:
                raise TypeError(f"{cls.__name__}: case on '{disc}' does not cover all values of "
                                f"{getattr(ft, '__name__', ft)}; add the missing branches or `case _`")

    @classmethod
    def _n_c_type(cls) -> type:
        return DICT_OF_C_TYPES[cls.__name__]

class Object(_Object, metaclass=NMetaClass):
    def __init_subclass__(cls) -> None:
        if "__eq__" in cls.__dict__ and cls.__dict__.get("__hash__", 0) is None:
            # Python drops __hash__ when a class defines __eq__; in Nim `==` and `hash` are independent
            # procs, so an overloaded `==` keeps the inherited hashing (e.g. PIdent's `==`)
            cls.__hash__ = next(b.__hash__ for b in cls.__mro__[1:] if b.__dict__.get("__hash__") is not None)
        # Capture the defining module's globals so that eval() in
        # get_or_eval_type can resolve constants used in type annotations
        # (e.g. array[_MINIMP4_MAX_SPS, pointer]).
        if "_n_caller_globals" not in cls.__dict__:
            cls._n_caller_globals = sys._getframe(1).f_globals
        cls._n_build_record()  # generic classes too: specializations map its annotations
        if cls.__dict__.get("_n_defer_register"):
            return  # specialization: __class_getitem__ registers it once it is cached
        type_params = getattr(cls, '__type_params__', ())
        if not type_params:
            cls._n_register_type()
        else:
            # Type parameters not resolved yet, just register the class
            _n_registry.types[cls.__name__] = cls

DICT_OF_TYPES["Object"] = Object
DICT_OF_TYPES["RootObj"] = Object
DICT_OF_TYPES["_Object"] = _Object


class NTuple(_Object):
    def __init_subclass__(cls) -> None:
        if "_n_caller_globals" not in cls.__dict__:
            cls._n_caller_globals = sys._getframe(1).f_globals
        if cls.__dict__.get("_n_defer_register"):
            return  # specialization: __class_getitem__ registers it once it is cached
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
        if index not in self._n_cache or self._n_cache[index] is None:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index, value)
        elif hasattr(self._n_cache[index], '_n_set_value'):
            self._n_cache[index]._n_set_value(value)
        elif hasattr(self._n_cache[index], '__ilshift__'):
            self._n_cache[index] <<= value

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
    _n_first: int = 0

    def __init__(self, it: Sequence | dict | None = None) -> None:
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
                    if isinstance(it, dict):
                        for key, value in it.items():
                            self[self._n_normalize_index(key)] = value
                    else:
                        for index in range(min(len(it), self._n_size)):
                            self[self._n_first + index] = it[index]
            else:
                # Scalar/simple types: use a plain Python list as backing store
                if it is not None:
                    if isinstance(it, dict):
                        self._n_cache = {self._n_first + j: _n_default_value(self._n_type) for j in range(self._n_size)}
                        for key, value in it.items():
                            self._n_cache[self._n_normalize_index(key)] = value
                    else:
                        for index in range(min(len(it), self._n_size)):
                            self._n_cache[self._n_first + index] = it[index]
                else:
                    # Nim default(T) per element: ref/ptr elements are nil, not constructed objects
                    self._n_cache = {self._n_first + j: _n_default_value(self._n_type) for j in range(self._n_size)}
                self._n_backing = None
                self._n_view = None
        else:
            raise Exception("array type or size not specified")

    @staticmethod
    def _n_normalize_index(index: object) -> int:
        if isinstance(index, NStrEnum):
            cls = index.__class__
            if cls.__n_members_tuple__ is None:
                cls._n_set_indices()
            return cls.__n_indices__[index]
        if hasattr(index, 'value'):
            v = index.value
            if isinstance(v, int):
                return v
        return int(index)

    def __del__(self):
        addr = getattr(self, '_n_owned_addr', None)
        if addr is not None:
            BUFFER_REGISTRY.free(addr)

    @classmethod
    def _n_low_bound(cls):
        return cls._n_first

    @classmethod
    def _n_high_bound(cls):
        return cls._n_first + cls._n_size - 1

    @classmethod
    def _n_on_struct(cls, struct_view, name, value: Object | None = None):
        self = cls.__new__(cls)
        self._n_view = getattr(struct_view, name)
        self._n_cache = {}
        if value is not None:
            for index in range(self._n_size):
                self[cls._n_first + index] = value[cls._n_first + index]
        return self

    def _n_sizeof(self) -> int:
        return self._n_size * self._n_type._n_sizeof()

    def __len__(self) -> int:
        return self._n_size

    def __str__(self) -> str:
        """Nim `$` of an array: `[a, b]`, strings and chars quoted."""
        return _n_collection_str("[", (self[i] for i in range(self._n_first, self._n_first + self._n_size)), "]")

    def __iter__(self):
        """Nim: items(a) — the elements in index order."""
        for pos in range(self._n_size):
            yield self[self._n_first + pos]

    def _n_check_index(self, index: int) -> None:
        """Nim raises IndexDefect for an index outside low(a)..high(a)."""
        if not 0 <= index - self._n_first < self._n_size and _n_check_enabled("boundchecks"):
            raise IndexDefect(f"index {index} not in {self._n_first} .. {self._n_first + self._n_size - 1}")

    def __getitem__(self, index: int) -> object:
        index = self._n_normalize_index(_n_from_end(index, self._n_size, self._n_first))
        self._n_check_index(index)
        if self._n_view is not None:
            if hasattr(self, '_n_type') and isinstance(self._n_type, type) and issubclass(self._n_type, (char, NScalar, bool)):
                return self._n_type._n_on_array(self._n_view, index - self._n_first)
            if index not in self._n_cache:
                self._n_cache[index] = self._n_type._n_on_array(self._n_view, index - self._n_first)
            return self._n_cache[index]
        return self._n_cache[index]

    def __setitem__(self, index: int, value: object) -> None:
        index = self._n_normalize_index(_n_from_end(index, self._n_size, self._n_first))
        self._n_check_index(index)
        if self._n_view is None:
            self._n_cache[index] = value
            return
        cached = self._n_cache.get(index)
        if cached is not None and cached is value:
            return  # `a[i] <<= v` has already assigned the element in place
        if isinstance(value, _Object):
            # whole-object assignment: copy ctypes-side and python-side fields (string, seq, ...)
            element = cached if cached is not None else self[index]
            element._n_set_value(value)
            return

        if hasattr(value, '_n_get_value'):
            val = value._n_get_value()
        else:
            val = value

        self._n_view[index - self._n_first] = val

        if index not in self._n_cache or self._n_cache[index] is None:
            if hasattr(self._n_type, '_n_on_array'):
                self._n_cache[index] = self._n_type._n_on_array(self._n_view, index - self._n_first)
            else:
                self._n_cache[index] = value
        elif hasattr(self._n_cache[index], '_n_set_value'):
            self._n_cache[index]._n_set_value(val)
        elif hasattr(self._n_cache[index], '__ilshift__'):
            self._n_cache[index] <<= value

    def __class_getitem__(cls, params) -> type:
        """array[N, T] → fixed-size array type."""
        n, _ntype = params
        first_val = 0
        # n can be ordinal
        if isinstance(n, type) and issubclass(n, Enum):
            n_val = len(n)
        elif isinstance(n, type) and issubclass(n, Trange):
            first_val = int(n._n_low_bound())
            n_val = int(n._n_high_bound()) - int(n._n_low_bound()) + 1
        elif isinstance(n, type) and issubclass(n, NInteger):
            first_val = int(low(n))
            n_val = int(high(n)) - int(low(n)) + 1
        else:
            n_val = int(n)

        if _ntype.__name__ not in DICT_OF_TYPES and hasattr(_ntype, '_n_register_type'):
            _ntype._n_register_type()
        n_name = n.__name__ if hasattr(n, '__name__') else str(n)
        class_name = f"array[{n_name}, {_ntype.__name__}]"
        # also register array[N, T] in DICT_OF_TYPES and DICT_OF_C_TYPES
        arr_type = type(class_name, (array,), {"_n_type": _ntype, "_n_size": n_val, "_n_first": first_val})
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

    def copy(self):
        """A copy of the value (Nim arrays are values)."""
        result = type(self)()
        result <<= self
        return result

    def __ilshift__(self, other):
        """Value assignment (Nim `a = other` through a var parameter): copy all elements in place."""
        if other is self:
            return self
        if hasattr(self, "_n_view") and hasattr(other, "_n_view"):
            ctypes.memmove(ctypes.addressof(self._n_view), ctypes.addressof(other._n_view),
                           ctypes.sizeof(self._n_view))
            self._n_cache = {}
            _n_carry_held_fields(self, dict(getattr(other, "_n_cache", {})))
        else:
            for i, item in enumerate(other):
                self[self._n_first + i] = item
        return self



# --- Sequences (seq) ---


class seq(Ntype):
    _n_is_list = False  # True for types without ctypes backing (e.g. string)

    def __init__(self, c_base: object | None = None) -> None:
        self._n_cache = {}
        self.len = 0
        self._n_reserved = 1
        if hasattr(self, "_n_type"):
            ntype = self._n_type
            if isinstance(ntype, str) and ntype in _n_registry.types:
                ntype = _n_registry.types[ntype]
                self._n_type = ntype
            type_name = ntype.__name__ if hasattr(ntype, '__name__') else str(ntype)
            if (isinstance(ntype, type) and issubclass(ntype, string)) or not hasattr(ntype, '_n_on_array') or getattr(ntype, '_n_is_ref', False) or bool(getattr(ntype, '_n_python_fields', None)):
                # List-based mode for non-ctypes types (e.g. string, ref types, structs with python fields)
                self._n_is_list = True
                self._n_list = list(c_base) if isinstance(c_base, (list, tuple)) else []
                return
            if type_name not in DICT_OF_C_TYPES:
                if hasattr(ntype, '_n_register_type'):
                    ntype._n_register_type()
                else:
                    for base in getattr(ntype, '__mro__', [])[1:]:
                        if base.__name__ in DICT_OF_C_TYPES:
                            DICT_OF_C_TYPES[type_name] = DICT_OF_C_TYPES[base.__name__]
                            break
            if type_name not in DICT_OF_C_TYPES:
                self._n_is_list = True
                self._n_list = list(c_base) if isinstance(c_base, (list, tuple)) else []
                return
            items = None
            if isinstance(c_base, (list, tuple)):  # seq literal `seq[T]([a, b])` (Nim @[a, b])
                items, c_base = c_base, None
            if c_base:
                self._n_backing = c_base
            else:
                self._n_backing = (DICT_OF_C_TYPES[type_name] * self._n_reserved)()
                self._n_owned_addr = BUFFER_REGISTRY.register(self._n_backing)
            self._n_view = (self._n_backing._type_ * self._n_reserved).from_address(
                ctypes.addressof(self._n_backing)
            )
            for item in items or ():
                self.add(item)
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

    def __str__(self) -> str:
        """Nim `$` of a seq: `@[a, b]`, strings and chars quoted."""
        return _n_collection_str("@[", (self[i] for i in range(len(self))), "]")

    def _n_resize(self) -> None:
        old_addr = ctypes.addressof(self._n_backing)
        ctypes.resize(self._n_backing, self._n_reserved * self._n_type._n_sizeof())
        self._n_owned_addr = BUFFER_REGISTRY.update(old_addr, self._n_backing)
        self._n_view = (self._n_view._type_ * self._n_reserved).from_address(
            ctypes.addressof(self._n_backing)
        )
        # rebuild the cached elements on the new memory: ctypes-backed fields are read from it, fields
        # held on the Python side (strings, refs: their pointer slots are not written) are carried over
        old_cache = self._n_cache
        self._n_cache = {}
        _n_carry_held_fields(self, {i: e for i, e in old_cache.items() if i < self.len})

    def __getitem__(self, index: int) -> object:
        index = int(_n_from_end(index, len(self)))
        if not 0 <= index < len(self) and _n_check_enabled("boundchecks"):
            raise IndexDefect(f"index {index} not in 0 .. {len(self) - 1}")
        if self._n_is_list:
            return self._n_list[index]
        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        return self._n_cache[index]

    def __setitem__(self, index, value: object) -> None:
        index = _n_from_end(index, len(self))
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
                source_cache = getattr(value, "_n_cache", {})
                _n_carry_held_fields(self, {j: source_cache.get(j) for j in range(stop - start)
                                            if source_cache.get(j) is not None}, offset=start)
            return
        index = int(index)
        value = self._n_coerce(value)
        if self._n_is_list:
            if self._n_list[index] is not value:  # `s[i] <<= v` already assigned in place
                self._n_list[index] = _n_value_copy(value)
            return
        if self._n_cache.get(index) is value:
            return
        if index not in self._n_cache or self._n_cache[index] is None:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index, value)
        elif hasattr(self._n_cache[index], '_n_set_value'):
            self._n_cache[index]._n_set_value(value)
        elif hasattr(self._n_cache[index], '__ilshift__'):
            self._n_cache[index] <<= value

    def __class_getitem__(cls, _ntype: type) -> type:
        if _ntype.__name__ not in DICT_OF_TYPES:
            if hasattr(_ntype, '_n_register_type'):
                _ntype._n_register_type()
            elif isinstance(_ntype, type):  # not a generic alias: tuple[A, B] is named "tuple"
                DICT_OF_TYPES[_ntype.__name__] = _ntype
        class_name = f"seq[{_n_type_name(_ntype)}]"
        _seq = type(class_name, (seq,), {"_n_type": _ntype})
        _seq._n_register_type()
        return _seq

    def _n_coerce(self, value: object) -> object:
        """A tuple literal for a seq of a named tuple type is that tuple (fields in order)."""
        elem = getattr(self, "_n_type", None)
        if (type(value) is tuple and isinstance(elem, type) and issubclass(elem, NTuple)
                and len(value) == len(elem._n_fields)):
            return elem(**dict(zip(elem._n_fields, value)))
        return value

    def add(self, value: object) -> None:
        value = self._n_coerce(value)
        if self._n_is_list:
            self._n_list.append(_n_value_copy(value))  # Nim add copies values, shares refs
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

    def copy(self):
        """A copy of the value (Nim seqs are values; `.copy()` is dropped by rule:copy)."""
        result = type(self)()
        result <<= self
        return result

    def __ilshift__(self, other):
        """Value assignment (Nim `s = other` through a var parameter): replace length and elements
        in place. Value elements are copied, ref elements are shared, as Nim's seq assignment does."""
        if other is self:
            return self
        items = [other[i] for i in range(len(other))]
        self.set_len(len(items))
        for i, item in enumerate(items):
            if self._n_is_list and not getattr(type(item), "_n_is_ref", False) and callable(getattr(item, "copy", None)):
                item = item.copy()
            self[i] = item
        return self

    def set_len(self, new_len: int) -> None:
        """Set logical length, resizing buffer if needed."""
        if getattr(self, '_n_is_list', False):
            if new_len < len(self._n_list):
                del self._n_list[new_len:]
            elif new_len > len(self._n_list):
                factory = getattr(self, '_n_type', None)
                for _ in range(new_len - len(self._n_list)):
                    self._n_list.append(factory() if callable(factory) else None)
            return
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

    def find(self, item: object) -> nint:
        """Nim: find — returns the index of the first occurrence of item, or -1."""
        if getattr(self, '_n_is_list', False):
            try:
                return nint(self._n_list.index(item))
            except ValueError:
                return nint(-1)
        for i in range(self.len):
            if self[i] == item:
                return nint(i)
        return nint(-1)

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
        """Yield mutable ctypes-backed views of elements (Nim's mitems)."""
        for i in range(len(self)):
            yield self[i]
        # # We yield (index, item) so that transpiled loops like `for i, x in myseq:`
        # # can unpack correctly natively, though it will break `for x in myseq:`
        # for i in range(len(self)):
        #     val = self[i]
        #     yield (i, val.copy() if hasattr(val, 'copy') else val)

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
        return self._n_view[_n_from_end(index, len(self))]

    def __setitem__(self, index, value):
        index = _n_from_end(index, len(self))
        if hasattr(value, '_n_addr'):
            self._n_view[index] = value._n_addr
        elif hasattr(value, '_n_get_value'):
            self._n_view[index] = value._n_get_value()
        else:
            self._n_view[index] = value

    def __len__(self):
        """Nim len(openArray): the source's length (a seq's view may have spare capacity)."""
        src = getattr(self, '_n_source', None)
        if src is not None and hasattr(src, '__len__'):
            return len(src)
        if hasattr(self._n_view, '__len__'):
            return len(self._n_view)
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
    _n_files: dict[int, 'File'] = {}  # id → File instance

    __slots__ = ('_n_handle', '_n_id')

    def __init__(self, handle=None):
        self._n_handle = handle
        self._n_id = id(self)
        if handle is not None:
            File._n_files[self._n_id] = self

    def open(self, filename: str, mode: str = "r") -> bool:
        _binary_map = {"w": "wb", "a": "ab", "r+": "r+b", "w+": "w+b", "r": "rb"}
        actual_mode = _binary_map.get(str(mode), str(mode))
        try:
            path = _n_os_arg(filename)
            self._n_handle = __builtins__["open"](path, actual_mode) if isinstance(__builtins__, dict) else __builtins__.open(path, actual_mode)
            self._n_id = id(self)
            File._n_files[self._n_id] = self
            return True
        except Exception:
            return False

    # --- delegate file operations to the underlying handle ---

    def seek(self, pos, *args):
        return self._n_handle.seek(pos, *args)

    def write(self, data):
        if hasattr(self._n_handle, 'mode') and 'b' in self._n_handle.mode:
            if isinstance(data, str) or hasattr(data, 'data'):  # str, char, string byte views
                data = _n_encode_str(data)
        return self._n_handle.write(data)

    def read(self, *args):
        return self._n_handle.read(*args)

    def close(self):
        File._n_files.pop(self._n_id, None)
        return self._n_handle.close()

    def flush(self):
        return self._n_handle.flush()

    def __enter__(self):
        if self._n_handle is not None and hasattr(self._n_handle, "__enter__"):
            self._n_handle.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._n_handle is not None and hasattr(self._n_handle, "__exit__"):
            return self._n_handle.__exit__(exc_type, exc_val, exc_tb)
        self.close()


    @property
    def buffer(self):
        return getattr(self._n_handle, 'buffer', self._n_handle)

    # --- cast support ---

    @classmethod
    def _n_cast(cls, source):
        """Recover a File from an opaque pointer token.

        The pointer's _n_token_id stores the registry key set by
        pointer._n_cast(file_instance).
        """
        if isinstance(source, File):
            return source
        if isinstance(source, pointer):
            token_id = getattr(source, '_n_token_id', None)
            if token_id is not None and token_id in cls._n_files:
                return cls._n_files[token_id]
        raise TypeError(f"Cannot cast {type(source)} to File")

    def __eq__(self, other):
        if other is None:
            return self._n_handle is None
        return NotImplemented

    def __ne__(self, other):
        if other is None:
            return self._n_handle is not None
        return NotImplemented

    def __repr__(self):
        return f"File({self._n_handle!r})"

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

    def __init__(self, x=None, **kwargs):
        if x is None and not kwargs:
            self._n_addr = 0
            self._n_contents_cache = None
        elif kwargs and x is None:
            obj = self._n_contents_type(**kwargs)
            self._n_addr = ctypes.addressof(obj._n_view) if hasattr(obj, '_n_view') else 0
            self._n_contents_cache = obj
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
    def _n_cast(cls, instance):
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
        elif hasattr(instance, '_n_id') and hasattr(type(instance), '_n_cast'):
            # Opaque handle (e.g. File) — store token id for recovery
            result._n_addr = 0
            result._n_token_id = instance._n_id
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
    if hasattr(x, '_n_ensure_view'):
        x._n_ensure_view()  # a standalone scalar gets storage of its own
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
    def _n_cast(cls, instance):
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
            #ptr_type = make_pointer_type(other, class_name=original_name)
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


class _SomeManagedRefClass:
    def __call__(self, cls: type) -> type:
        """When used as @ref decorator, mark class as a managed reference type.
        This prevents C-backing for arrays, allowing them to store None and behave
        like managed Python references."""
        cls._n_is_ref = True
        class_name = cls.__name__
        if class_name in DICT_OF_C_TYPES:
            del DICT_OF_C_TYPES[class_name]
        # With no ctypes struct, ALL fields must be python-side so they get
        # initialized in __init__ (otherwise ctypes-classified fields like
        # `s: string` are never set and access raises AttributeError).
        field_types = getattr(cls, '_n_field_types', {})
        if field_types:
            cls._n_python_fields = set(field_types.keys())
        return cls

    def __getitem__(self, _ntype: type) -> type:
        return _ntype

ref = _SomeManagedRefClass()
ptr = _SomeRefClass()
typedesc = _SomeRefClass()

class _SomeMutClass:
    def __matmul__(self, other: object) -> object:
        return other
# reserve keyword for modifiable variables
mut = _SomeMutClass()
# Nim `out T` parameter (assigned by the proc before use); in Python the same as mut
out = _SomeMutClass()


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


def _n_is_number(x: object) -> bool:
    """A scalar or Python number an NScalar operator computes with; other operands (objects) get
    NotImplemented, so Python calls their reflected operator with the scalar itself."""
    return isinstance(x, NScalar) or hasattr(x, "__float__")


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
            self._n_view = c_type.from_address(int(addr_val))
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

    def _n_ensure_view(self) -> None:
        """Gives a standalone scalar ctypes storage of its own (Nim: a local variable has an address), so
        addr(x) points at it; reads and writes go through that storage from then on."""
        if self._n_view is not None:
            return
        storage = DICT_OF_C_TYPES[type(self).__name__](self._n_get_value())
        BUFFER_REGISTRY.register(storage)
        self._n_bind(
            get_value=lambda: storage.value,
            set_value=lambda value: setattr(
                storage, "value", value._n_get_value() if isinstance(value, NScalar) else value),
            get_addr=lambda: ctypes.addressof(storage),
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
        id = int(id)
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
        # the field descriptor knows the real offset: alignment padding included, and
        # fields promoted from anonymous unions/structs (variant branches) are found too
        offset = getattr(type(parent_elems), id).offset
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
    def _n_cast(cls, value: NScalar) -> NScalar:
        if not isinstance(value, NScalar):  # a Python number is a Nim literal: int or float64
            value = nint(value) if isinstance(value, int) else float64(value)
        return cls._n_from_bytes(value._n_to_bytes())

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
    # `checked`: the operation is one of Nim's overflow-checked ones (+, -, *, div, unary -, abs);
    # +%/-%, shifts and bitwise operations wrap and pass checked=False.
    def _n_op(self, other: NScalar | int | float, op_func: callable, checked: bool = False) -> NScalar:
        if isinstance(other, NScalar):
            target_type = determine_common_type(self._n_type, other._n_type)
            res_val = op_func(self._n_get_value(), other._n_get_value())
            if checked:
                _n_check_overflow(target_type, res_val)
            return target_type(res_val)
        elif hasattr(other, "__float__"):  # numeric literal or other scalar
            # Promote int types to float64 when operating with a float literal
            if isinstance(other, float) and not issubclass(self._n_type, NFloat):
                target_type = float64
            else:
                target_type = self._n_type
            res_val = op_func(self._n_get_value(), other)
            if checked:
                _n_check_overflow(target_type, res_val)
            return target_type(res_val)
        return NotImplemented  # not a number: Python asks the other operand (Nim overload order)

    def _n_rop(self, other: NScalar | int | float, op_func: callable, checked: bool = False) -> NScalar:
        if isinstance(other, NScalar):
            target_type = determine_common_type(self._n_type, other._n_type)
            res_val = op_func(other._n_get_value(), self._n_get_value())
            if checked:
                _n_check_overflow(target_type, res_val)
            return target_type(res_val)
        elif hasattr(other, "__float__"):  # numeric literal or other scalar
            # Promote int types to float64 when operating with a float literal
            if isinstance(other, float) and not issubclass(self._n_type, NFloat):
                target_type = float64
            else:
                target_type = self._n_type
            res_val = op_func(other, self._n_get_value())
            if checked:
                _n_check_overflow(target_type, res_val)
            return target_type(res_val)
        return NotImplemented  # not a number: Python asks the other operand (Nim overload order)

    def _n_iop(self, other: NScalar | int | float, op_func: callable, checked: bool = False) -> None:
        if isinstance(other, NScalar):
            res_val = op_func(self._n_get_value(), other._n_get_value())
        elif hasattr(other, "__float__"):  # check if numeric literal or other scalar
            res_val = op_func(self._n_get_value(), other)
        else:
            return
        if checked:
            _n_check_overflow(self._n_type, res_val)
        self._n_set_value(self._n_normalize(res_val))

    # --- Unary Operations ---
    def __neg__(self):
        res_val = -self._n_get_value()
        _n_check_overflow(self._n_type, res_val)
        return self._n_type(res_val)

    def __pos__(self):
        return self._n_type(+self._n_get_value())

    def __abs__(self):
        res_val = abs(self._n_get_value())
        _n_check_overflow(self._n_type, res_val)
        return self._n_type(res_val)

    # --- Binary Operations ---
    def __add__(self, other):
        return self._n_op(other, operator.add, checked=True)

    def __sub__(self, other):
        return self._n_op(other, operator.sub, checked=True)

    def __mul__(self, other):
        return self._n_op(other, operator.mul, checked=True)

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
        return self._n_rop(other, operator.add, checked=True)

    def __rsub__(self, other):
        return self._n_rop(other, operator.sub, checked=True)

    def __rdiv__(self, other):
        return self._n_rop(other, operator.div)

    def __rmul__(self, other):
        return self._n_rop(other, operator.mul, checked=True)

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
        self._n_iop(other, operator.add, checked=True)
        return self

    def __isub__(self, other):
        self._n_iop(other, operator.sub, checked=True)
        return self

    def __imul__(self, other):
        self._n_iop(other, operator.mul, checked=True)
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
        if not _n_is_number(other):
            return NotImplemented  # e.g. an object with `proc <(a: int64, b: T)`: Python asks it
        return self._n_get_value() < (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __le__(self, other):
        if not _n_is_number(other):
            return NotImplemented  # e.g. an object with `proc <=(a: int64, b: T)`: Python asks it
        return self._n_get_value() <= (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __gt__(self, other):
        if not _n_is_number(other):
            return NotImplemented  # e.g. an object with `proc >(a: int64, b: T)`: Python asks it
        return self._n_get_value() > (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __ge__(self, other):
        if not _n_is_number(other):
            return NotImplemented  # e.g. an object with `proc >=(a: int64, b: T)`: Python asks it
        return self._n_get_value() >= (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __eq__(self, other):
        if not _n_is_number(other):
            return NotImplemented  # e.g. an object with `proc ==(a: int64, b: T)`: Python asks it
        return self._n_get_value() == (
            other._n_get_value() if isinstance(other, NScalar) else other
        )

    def __ne__(self, other):
        if not _n_is_number(other):
            return NotImplemented  # e.g. an object with `proc !=(a: int64, b: T)`: Python asks it
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

    def _n_to_bytes(self, byteorder=sys.byteorder):
        if byteorder == "big":
            prefix = ">" + self._n_format
        else:
            prefix = "<" + self._n_format
        out = struct.pack(prefix, self._n_get_value())
        return bytes(out)

    @classmethod
    def _n_from_bytes(cls, bytes, byteorder=sys.byteorder):
        if byteorder == "big":
            prefix = ">" + cls._n_format
        else:
            prefix = "<" + cls._n_format
        val = struct.unpack(prefix, bytes)[0]
        return cls(val)


def _n_trunc_div(a, b):
    ia, ib = int(a), int(b)
    q = abs(ia) // abs(ib)
    return -q if (ia < 0) ^ (ib < 0) else q


def _n_trunc_mod(a, b):
    ia, ib = int(a), int(b)
    r = abs(ia) % abs(ib)
    return -r if ia < 0 else r


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

    def _n_to_bytes(self, length=None, byteorder=sys.byteorder):
        if length is None:
            length = (self._n_bits + 7) // 8

        return int(self).to_bytes(
                length, byteorder=byteorder, signed=self._n_signed
        )

    @classmethod
    def _n_from_bytes(cls, bytes, byteorder=sys.byteorder, signed=None):
        if signed is None:
            signed = cls._n_signed
        val = int.from_bytes(bytes, byteorder=byteorder, signed=signed)
        return cls(val)

    def __floordiv__(self, other):
        return self._n_op(other, _n_trunc_div, checked=True)

    def __rfloordiv__(self, other):
        return self._n_rop(other, _n_trunc_div, checked=True)

    def __ifloordiv__(self, other):
        self._n_iop(other, _n_trunc_div, checked=True)
        return self

    def __mod__(self, other):
        return self._n_op(other, _n_trunc_mod)

    def __rmod__(self, other):
        return self._n_rop(other, _n_trunc_mod)

    def __imod__(self, other):
        self._n_iop(other, _n_trunc_mod)
        return self

    # --- Wrapping arithmetic (Nim: +%, -%) ---
    # Values are always reduced modulo 2**_n_bits by _n_normalize, so wrapping
    # is a property of the type itself. These go through _n_op (not __add__ /
    # __sub__) so they stay wrapping even if ordinary +/- gain overflow checks.
    def plus_percent(self, other):
        """Nim: self +% other — wrapping addition in this type's width."""
        return self._n_op(other, operator.add)

    def minus_percent(self, other):
        """Nim: self -% other — wrapping subtraction in this type's width."""
        return self._n_op(other, operator.sub)

    def ashr(self, y):
        """Nim: ashr(self, y) — arithmetic shift right, copies of the sign bit shifted in. Nim defines it
        for signed integers only."""
        if not self._n_signed:
            raise TypeError(f"ashr: Nim defines ashr for signed integers only, not {type(self).__name__}")
        return type(self)(int(self) >> int(y))

    # --- Unsigned comparisons (Nim: <%, <=%, >%, >=%) in this type's width ---
    def _n_unsigned_pair(self, other) -> tuple[int, int]:
        mask = (1 << self._n_bits) - 1
        return int(self) & mask, int(other) & mask

    def lt_percent(self, other) -> bool:
        """Nim: self <% other — unsigned less than."""
        a, b = self._n_unsigned_pair(other)
        return a < b

    def le_percent(self, other) -> bool:
        """Nim: self <=% other — unsigned less than or equal."""
        a, b = self._n_unsigned_pair(other)
        return a <= b

    def gt_percent(self, other) -> bool:
        """Nim: self >% other — unsigned greater than."""
        a, b = self._n_unsigned_pair(other)
        return a > b

    def ge_percent(self, other) -> bool:
        """Nim: self >=% other — unsigned greater than or equal."""
        a, b = self._n_unsigned_pair(other)
        return a >= b

    @staticmethod
    def _n_lift(value, peer=None) -> NInteger:
        """Return `value` as an NInteger: kept as is if it already is one, otherwise
        converted to the type of an NInteger `peer` (Nim literal conversion),
        or to Nim `int` (nint) when there is no typed peer."""
        if isinstance(value, NInteger):
            return value
        target = type(peer) if isinstance(peer, NInteger) else nint
        return target(value)

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

    @classmethod
    def _n_low_bound(cls):
        """Return the minimum representable value for this integer type."""
        if cls._n_signed:
            return cls(-(1 << (cls._n_bits - 1)))
        else:
            return cls(0)

    @classmethod
    def _n_high_bound(cls):
        """Return the maximum representable value for this integer type."""
        if cls._n_signed:
            return cls((1 << (cls._n_bits - 1)) - 1)
        else:
            return cls((1 << cls._n_bits) - 1)


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


class uint(NInteger):
    """Nim uint: the unsigned machine word (dispatches as uint64, as nint does as int64)."""
    _n_bits, _n_signed, _n_rank = 64, False, 7


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


# --- Byte-string codec (single source of truth) ---
#
# Nim strings are bytes. nimic holds them as a Python `str` *view* in which
# every char is one byte (code point 0..0xFF, i.e. Latin-1). Unicode text only
# meets byte strings at I/O boundaries (stdio, files, OS paths, Python-library
# text), and those boundaries convert via _n_from_text / _n_to_text (UTF-8).
# Every other encode/decode in the runtime goes through these helpers.


class NimicEncodingError(ValueError):
    """A char above 0xFF was stored into a Nim byte string (string/cstring/char)."""


def _n_encode_str(s) -> bytes | None:
    """Byte view -> bytes (strict Latin-1). bytes/bytearray pass through, objects
    with `.data` are unwrapped, None stays None. Inverse: _n_decode_bytes."""
    if s is None:
        return None
    if isinstance(s, (bytes, bytearray)):
        return bytes(s)
    if hasattr(s, 'data'):
        s = s.data
    val = str(s)
    try:
        return val.encode('latin-1')
    except UnicodeEncodeError as e:
        i = e.start
        c = val[i]
        raise NimicEncodingError(
            f"character {c!r} (U+{ord(c):04X}) at index {i} cannot be stored in a Nim byte string; "
            f"nimic strings are bytes (Latin-1 view). Use utf8({val!r}) for UTF-8 text "
            f"or escape bytes explicitly") from None


def _n_decode_bytes(raw: bytes) -> str:
    """Bytes -> byte view (Latin-1, one char per byte; never fails)."""
    return raw.decode('latin-1')


def _n_from_text(text: str) -> str:
    """Unicode text -> byte view of its UTF-8 bytes (I/O boundary helper).
    surrogateescape restores undecodable bytes produced by _n_to_text / os APIs."""
    return str(text).encode('utf-8', 'surrogateescape').decode('latin-1')


def _n_to_text(view) -> str:
    """Byte view (str or string) -> Unicode text by decoding its bytes as UTF-8
    (I/O boundary helper). Invalid UTF-8 bytes become lone surrogates, so
    _n_from_text(_n_to_text(v)) == v for any bytes."""
    return _n_encode_str(view).decode('utf-8', 'surrogateescape')


def utf8(text) -> 'string':
    """Nim string literal semantics for Unicode text: utf8("é") is the 2-byte
    string C3 A9, exactly like the Nim literal "é" (a bare "é" is the byte E9)."""
    return string(_n_from_text(text))


def _n_os_arg(p) -> str:
    """Byte-view path/name/env value -> text for Python's os APIs, which
    fsencode it back to exactly the same bytes (surrogateescape)."""
    return _n_to_text(p)


def _n_os_result(s) -> 'string':
    """Path/name/env text returned by Python's os APIs -> nimic byte string."""
    return string(_n_from_text(s))


class cstring:
    """Nim cstring — a nullable pointer to a null-terminated char buffer.

    In Nim, cstring is pointer-sized (char*), can be nil, does not own its data. In nimic it is
    ctypes-backed as c_char_p inside Object structs (correct layout for c_malloc / pointer
    arithmetic).

    Python-side it holds a ctypes char buffer (`_n_view`, None for nil). `cstring(s)` / `s.cstring`
    of a `string` points into the string's buffer, so writes through either are seen by both (Nim
    `L.buf = L.bufStorage.cstring`); other values are copied into a buffer of their own. Reads stop at
    the first NUL (strlen) and index past the buffer gives the terminator '\\0'.
    str(cs) is the Latin-1 byte view (one char per byte), as for `string`.
    """
    __slots__ = ('_n_view',)

    def __init__(self, value=None):
        if isinstance(value, (string, cstring)):
            self._n_view = value._n_view  # the same buffer: a pointer, no copy
        elif isinstance(value, int):
            self._n_view = (ctypes.c_char * value)()  # new_cstring_of_cap(length): zero-filled
        else:
            self._n_value = value

    @property
    def _n_value(self) -> bytes | None:
        """The bytes up to the first NUL, None for nil."""
        if self._n_view is None:
            return None
        raw = bytes(self._n_view)
        return raw.split(b'\0', 1)[0]

    @_n_value.setter
    def _n_value(self, value) -> None:
        """Points the cstring at a new buffer holding a copy of value (None: nil)."""
        if value is None:
            self._n_view = None
            return
        data = value if isinstance(value, bytes) else _n_encode_str(value)
        self._n_view = (ctypes.c_char * len(data)).from_buffer_copy(data)

    @classmethod
    def _n_cast(cls, source) -> cstring:
        """Nim cast[cstring](p): a cstring at address p (char*), over the registered buffer that contains
        it (a string's), from p to the buffer's end; the memory is shared. A nil pointer gives nil."""
        address = int(source._n_addr if hasattr(source, '_n_addr') else source)
        inst = cls.__new__(cls)
        if address == 0:
            inst._n_view = None
            return inst
        buf = BUFFER_REGISTRY.find_buffer_for_address(address)
        if buf is None:
            raise ValueError(f"cast[cstring]: address {address:#x} is not inside a nimic buffer")
        offset = address - ctypes.addressof(buf)
        inst._n_view = (ctypes.c_char * (ctypes.sizeof(buf) - offset)).from_buffer(buf, offset)
        return inst

    # --- Object field integration ---

    @classmethod
    def _n_on_struct(cls, parent_elems, id, value=None):
        """Read/create a cstring backed by a c_char_p field in a ctypes struct."""
        inst = cls.__new__(cls)
        if value is not None:
            inst._n_set_value(value)
            setattr(parent_elems, id, inst._n_value)
        else:
            inst._n_value = getattr(parent_elems, id)  # c_char_p → bytes or None
        return inst

    def _n_set_value(self, value):
        if isinstance(value, cstring):
            self._n_view = value._n_view
        else:
            self._n_value = value

    @classmethod
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(ctypes.c_char_p)

    # --- Nim-compatible interface ---

    def __eq__(self, other):
        if other is None:
            return self._n_view is None
        if isinstance(other, cstring):
            return self._n_value == other._n_value
        if isinstance(other, (str, bytes)):
            try:
                return self._n_value == _n_encode_str(other)
            except NimicEncodingError:
                return False  # chars above 0xFF never equal a byte string
        return NotImplemented

    def __ne__(self, other):
        eq = self.__eq__(other)
        return eq if eq is NotImplemented else not eq

    def __bool__(self):
        return self._n_view is not None

    def __len__(self):
        value = self._n_value
        return 0 if value is None else len(value)

    def __str__(self):
        value = self._n_value
        return "" if value is None else _n_decode_bytes(value)

    def __repr__(self):
        value = self._n_value
        return "cstring(nil)" if value is None else f"cstring({value!r})"

    def __getitem__(self, index):
        """Nim cstring indexing: the char in the buffer, bound to its address (addr(c[i])); past the
        buffer the terminator '\\0'. A slice is a cstring copy."""
        if self._n_view is None:
            raise IndexError("cstring is nil")
        if isinstance(index, slice):
            return cstring(bytes(self._n_view)[index])
        idx = int(index)
        if 0 <= idx < len(self._n_view):
            return char(self._n_view[idx], addr=ctypes.addressof(self._n_view) + idx)
        return char("\0")

    def __setitem__(self, index, value) -> None:
        """Nim `c[i] = x`: writes into the buffer (the string's, for a cstring of a string)."""
        if self._n_view is None:
            raise IndexError("cstring is nil")
        idx = int(index)
        if not 0 <= idx < len(self._n_view):
            raise IndexError(f"cstring index {idx} outside its buffer of {len(self._n_view)} chars")
        self._n_view[idx] = bytes([int(char(value))])


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
    def succ(self, n: int = 1) -> char:
        """Nim: succ(c, n) / pred(c, n) — the char n ordinals later (earlier for n < 0); RangeDefect outside
        '\\0'..'\\xFF'."""
        i = self._n_byte + int(n)
        if not 0 <= i <= 255:
            raise RangeDefect(f"value out of range: {i} notin 0 .. 255")
        return char(i)

    def __new__(cls, value=0, addr: int = 0):
        if not isinstance(value, (str, bytes, bytearray)) and hasattr(value, "__index__"):
            value = value.__index__()  # char(x) of any ordinal (uint8, nint, ...)
        if isinstance(value, int):
            # chr(65) → char from ordinal
            byte_val = value & 0xFF
            obj = super().__new__(cls, struct.pack('B', byte_val).decode('latin-1'))
            obj._n_byte = byte_val
        elif isinstance(value, (bytes, bytearray)):
            byte_val = value[0] if len(value) > 0 else 0
            obj = super().__new__(cls, chr(byte_val))
            obj._n_byte = byte_val
        else:
            # char('A') or char('A', addr)
            ch = value[:1] if value else '\x00'
            obj = super().__new__(cls, ch)
            obj._n_byte = _n_encode_str(ch)[0]  # raises NimicEncodingError above 0xFF
        obj._n_slot_addr = addr
        return obj

    def __ilshift__(self, other):
        """`c <<= x` (Nim `c = x` for a var char, e.g. from mitems(s)): writes x into the string slot
        the char came from; a char without a slot just becomes x."""
        owner = getattr(self, "_n_owner", None)
        if owner is not None:
            owner[self._n_index] = other
            return owner._n_slot_char(self._n_index)
        return char(other)

    def __int__(self):
        return self._n_byte

    def _n_get_value(self):
        return bytes([self._n_byte])

    def __index__(self):
        return self._n_byte

    def __bytes__(self):
        """Single-byte representation for binary file writing."""
        return bytes([self._n_byte])

    @classmethod
    def _n_sizeof(cls) -> int:
        return 1

    @classmethod
    def _n_on_array(cls, parent_elems, index, value=None):
        addr = ctypes.addressof(parent_elems) + index
        if value is not None:
            parent_elems[index] = ord(value) if isinstance(value, str) else int(value)
        val = parent_elems[index]
        return cls(val, addr=addr)

    @classmethod
    def _n_register_type(cls):
        DICT_OF_TYPES[cls.__name__] = cls
        DICT_OF_C_TYPES[cls.__name__] = ctypes.c_char

class string(collections.UserString):
    """Nim-compatible string with C-buffer backing to support addr().

    A Nim string is a sequence of bytes. `.data` is its Latin-1 *byte view*:
    one Python char (code point 0..0xFF) per byte, so len(s) is the byte count
    and s[i] is byte i. A char above 0xFF raises NimicEncodingError; use
    utf8(text) to get the UTF-8 bytes of Unicode text (Nim literal semantics).
    """
    
    def __init_subclass__(cls, **kwargs):
        """rule:typealias: `class Snippet(string): pass` is `type Snippet* = string`, so for dispatch it is
        an alias of string, as NScalar subclasses are (@distinct removes the alias)."""
        super().__init_subclass__(**kwargs)
        own = [k for k, v in vars(cls).items() if not k.startswith("__") and not k.startswith("_n_")]
        if own or any(callable(v) for k, v in vars(cls).items() if k not in ("__module__", "__qualname__", "__doc__")):
            return  # a class with members of its own (e.g. std/paths.Path, distinct in Nim) is no alias
        base = cls.__bases__[0].__name__
        _n_aliases[cls.__name__] = _n_aliases.get(base, base)
        DICT_OF_TYPES[cls.__name__] = cls

    @property
    def _n_view(self):
        return self._n_view_ref[0] if hasattr(self, '_n_view_ref') else None

    @_n_view.setter
    def _n_view(self, val):
        if not hasattr(self, '_n_view_ref'):
            self._n_view_ref = [val]
        else:
            self._n_view_ref[0] = val

    def __init__(self, bs=""):
        if isinstance(bs, string) and hasattr(bs, '_n_view_ref'):
            self._n_view_ref = bs._n_view_ref
            self._n_len = getattr(bs, '_n_len', None)
            return
        if isinstance(bs, int):
            cap = bs
            self._n_len = 0
            self._n_view_ref = [(ctypes.c_char * cap)()]
            if cap > 0:
                BUFFER_REGISTRY.register(self._n_view_ref[0])
            return
            
        bs_bytes = _n_encode_str(bs) or b""  # Nim strings are never nil
            
        self._n_len = len(bs_bytes)
        self._n_view_ref = [(ctypes.c_char * len(bs_bytes)).from_buffer_copy(bs_bytes)]
        if len(bs_bytes) > 0:
            BUFFER_REGISTRY.register(self._n_view_ref[0])

    @property
    def data(self):
        if hasattr(self, '_n_view_ref') and self._n_view_ref[0] is not None:
            if hasattr(self, '_n_len') and self._n_len is not None:
                raw = bytes(self._n_view_ref[0])[:self._n_len]
            else:
                raw = bytes(self._n_view_ref[0]).split(b'\0', 1)[0]
            return _n_decode_bytes(raw)
        return ""

    @property
    def string(self) -> 'string':
        return self

    @property
    def cstring(self) -> 'cstring':
        """Nim `s.cstring`: a cstring pointing into this string's buffer."""
        return cstring(self)
        
    @data.setter
    def data(self, value):
        bs_bytes = _n_encode_str(value)
        if hasattr(self, '_n_view_ref') and self._n_view_ref[0] is not None:
            BUFFER_REGISTRY.unregister(self._n_view_ref[0])
        self._n_len = len(bs_bytes)
        self._n_view_ref = [(ctypes.c_char * len(bs_bytes)).from_buffer_copy(bs_bytes)]
        if len(bs_bytes) > 0:
            BUFFER_REGISTRY.register(self._n_view_ref[0])

    def __ilshift__(self, other):
        self.data = other.data if hasattr(other, 'data') else str(other)
        return self

    def __setitem__(self, index, value) -> None:
        """Nim `s[i] = c`: writes the char in place (other references to the string see it)."""
        idx = int(_n_from_end(index, len(self.data)))
        n = len(self)
        if not 0 <= idx < n:
            if _n_check_enabled("boundchecks"):
                raise IndexDefect(f"index {idx} not in 0 .. {n - 1}")
            return  # without bound checks: the terminator or memory past it, not modelled
        self._n_view_ref[0][idx] = bytes([int(char(value))])

    def _n_slot_char(self, index: int) -> 'char':
        """The char at index, bound to its slot: `c <<= x` writes back (Nim var iteration)."""
        c = char(self.data[index])
        c._n_owner = self
        c._n_index = index
        return c

    @property
    def mitems(self):
        """Nim mitems: chars bound to their slots, assigned with `c <<= x`."""
        for i in range(len(self)):
            yield self._n_slot_char(i)

    @property
    def len(self) -> int:
        """Nim `s.len` (as seq.len)."""
        return len(self)

    def copy(self):
        """A copy of the value with its own buffer (Nim strings are values; `.copy()` is dropped by
        rule:copy). Note: string(other) shares other's buffer."""
        return type(self)(str(self.data))

    __copy__ = copy

    def __iadd__(self, other):
        s_other = other.data if hasattr(other, 'data') else str(other)
        self.data = self.data + s_other
        return self

    def __fspath__(self) -> str:
        # os re-encodes this text (fsencode) to exactly the string's bytes
        return _n_to_text(self)

    def setLen(self, new_len: int) -> None:
        nl = int(new_len)
        curr = self.data
        if nl <= len(curr):
            self.data = curr[:nl]
        else:
            self.data = curr + '\x00' * (nl - len(curr))

    set_len = setLen

    def _n_ensure_capacity(self, new_cap):
        if self._n_view is None:
            self._n_view = (ctypes.c_char * new_cap)()
            BUFFER_REGISTRY.register(self._n_view)
        elif len(self._n_view) < new_cap:
            BUFFER_REGISTRY.unregister(self._n_view)
            new_size = max(len(self._n_view) * 2, new_cap)
            new_arr = (ctypes.c_char * new_size)()
            ctypes.memmove(new_arr, self._n_view, len(self._n_view))
            self._n_view = new_arr
            BUFFER_REGISTRY.register(self._n_view)

    def add(self, other):
        other_bytes = _n_encode_str(other)
        cur_bytes = _n_encode_str(self.data)
        new_len = len(cur_bytes) + len(other_bytes) + 1
        self._n_ensure_capacity(new_len)
        
        for i, b in enumerate(other_bytes):
            self._n_view[len(cur_bytes) + i] = b
        self._n_view[len(cur_bytes) + len(other_bytes)] = 0
        self._n_len = len(cur_bytes) + len(other_bytes)

    def _n_get_value(self):
        return _n_encode_str(self.data)

    def __str__(self):
        return self.data

    def __len__(self):
        return len(self.data)

    def __eq__(self, other):
        if isinstance(other, string):
            return self.data == other.data
        if isinstance(other, str):
            return self.data == other
        return NotImplemented
        
    def __hash__(self):
        return hash(self.data)

    def __and__(self, other):
        return string(self.data + str(other))

    def _n_substitute(self, **kwargs):
        return string(Template(self.data).substitute(**kwargs))

    def __mod__(self, itr):
        """Nim strutils `%` (formatstr % [a, b] or % a) for a format string with `$`; otherwise
        Python's % formatting."""
        if '$' in self.data:
            single = isinstance(itr, (str, bytes, string)) or not hasattr(itr, '__iter__')
            items = [itr] if single else list(itr)
            return string(_n_addf(self.data, items))
        if hasattr(itr, '__iter__') and not isinstance(itr, (str, bytes)):
            return string(self.data % tuple(itr))
        return string(self.data % itr)

    def is_empty(self) -> bool:
        return len(self.data) == 0

    def __truediv__(self, tail) -> 'string':
        tail_str = tail.data if hasattr(tail, 'data') else str(tail)
        return string(f"{self.data}/{tail_str}")

    def splitlines(self):
        return [string(x) for x in self.data.splitlines()]

    def split_whitespace(self):
        return [string(x) for x in self.data.split()]
        
    def endswith(self, suffix: str | string | tuple) -> bool:
        if isinstance(suffix, tuple):
            return self.data.endswith(tuple(str(x) for x in suffix))
        return self.data.endswith(str(suffix))
        
    def startswith(self, prefix: str | string | tuple) -> bool:
        if isinstance(prefix, tuple):
            return self.data.startswith(tuple(str(x) for x in prefix))
        return self.data.startswith(str(prefix))

    @classmethod
    def _n_on_array(cls, parent_elems, index, value=None):
        if value is not None:
            b_val = _n_encode_str(value)
            if isinstance(index, str):
                setattr(parent_elems, index, b_val)
            else:
                parent_elems[index] = b_val
        raw = getattr(parent_elems, index) if isinstance(index, str) else parent_elems[index]
        if raw is None:
            return cls("")
        if isinstance(raw, bytes):
            return cls(raw)
        return cls(str(raw))
        
    def __getitem__(self, index):
        if isinstance(index, slice):
            return string(self.data[index])
        index = _n_from_end(index, len(self.data))
        if hasattr(self, '_n_view') and self._n_view is not None:
            idx = int(index)
            if 0 <= idx < len(self._n_view):
                return char(self._n_view[idx], addr=ctypes.addressof(self._n_view) + idx)
            elif idx < len(self.data):
                return char(self.data[idx], addr=ctypes.addressof(self._n_view) + idx)
        if not isinstance(index, slice) and int(index) >= len(self.data):
            # Nim strings end with '\0': s[s.len] reads it when bound checks are off
            if _n_check_enabled("boundchecks"):
                raise IndexDefect(f"index {int(index)} not in 0 .. {len(self.data) - 1}")
            if int(index) == len(self.data):
                return char("\0")
        return char(self.data[index])


def _n_carry_held_fields(target, source_cache: dict, offset: int = 0) -> None:
    """After element memory of `target` (seq/array) was written by a raw copy, rebuild its cached
    elements at index + offset from `source_cache` ({index: element}): ctypes fields come from the
    target memory, Python-held fields (strings, refs) from the source elements."""
    elem_type = getattr(target, "_n_type", None)
    held = _n_python_held_fields(elem_type)
    if not held:
        return
    for i, src in source_cache.items():
        if src is None:
            continue
        elem = elem_type._n_on_array(target._n_view, i + offset)
        for name in held:
            if name in src.__dict__:
                elem.__dict__[name] = src.__dict__[name]
        target._n_cache[i + offset] = elem


def _n_python_held_fields(cls: type) -> tuple:
    """Fields of an Object type whose values live on the Python side of an element: declared
    python-side fields and pointer slots (c_char_p strings, c_void_p refs) that hold no data."""
    c_type = getattr(cls, "_n_c_type", None)
    if not isinstance(cls, type) or c_type is None:
        return ()
    try:
        fields = c_type()._fields_
    except (TypeError, AttributeError):
        return ()
    names = {name for name, ct, *_ in fields if ct in (ctypes.c_char_p, ctypes.c_void_p)}
    return tuple(names | set(getattr(cls, "_n_python_fields", ())))


def _n_addf(formatstr: str, a: list) -> str:
    """Nim strutils.addf/`%`: $1..$n, $-n, $#, ${n}, ${name}/$name (key/value pairs of `a`, compared
    style-insensitively), $$; ValueError for an invalid format string. Returns the formatted text."""
    args = [x.data if hasattr(x, "data") else str(x) for x in a]

    def invalid():
        raise ValueError("invalid format string: " + formatstr)

    def find_normalized(x: str) -> int:
        norm = x.replace("_", "").lower()
        i = 0
        while i < len(args) - 1:
            if args[i].replace("_", "").lower() == norm:
                return i
            i += 2
        return -1

    pattern = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_") | {chr(c) for c in range(128, 256)}
    out = []
    i = num = 0
    n = len(formatstr)
    while i < n:
        if formatstr[i] == "$" and i + 1 < n:
            c = formatstr[i + 1]
            if c == "#":
                if num > len(args) - 1:
                    invalid()
                out.append(args[num])
                i += 2
                num += 1
            elif c == "$":
                out.append("$")
                i += 2
            elif "1" <= c <= "9" or c == "-":
                j = 0
                i += 1
                negative = formatstr[i] == "-"
                if negative:
                    i += 1
                while i < n and formatstr[i].isdigit():
                    j = j * 10 + ord(formatstr[i]) - ord("0")
                    i += 1
                idx = j - 1 if not negative else len(args) - j
                if idx < 0 or idx > len(args) - 1:
                    invalid()
                out.append(args[idx])
            elif c == "{":
                j = i + 2
                k = 0
                negative = j < n and formatstr[j] == "-"
                if negative:
                    j += 1
                is_number = 0
                while j < n and formatstr[j] not in ("\0", "}"):
                    if formatstr[j].isdigit():
                        k = k * 10 + ord(formatstr[j]) - ord("0")
                        if is_number == 0:
                            is_number = 1
                    else:
                        is_number = -1
                    j += 1
                if is_number == 1:
                    idx = k - 1 if not negative else len(args) - k
                    if idx < 0 or idx > len(args) - 1:
                        invalid()
                    out.append(args[idx])
                else:
                    x = find_normalized(formatstr[i + 2:j])
                    if 0 <= x < len(args) - 1:
                        out.append(args[x + 1])
                    else:
                        invalid()
                i = j + 1
            elif c in pattern and not c.isdigit():
                j = i + 1
                while j < n and formatstr[j] in pattern:
                    j += 1
                x = find_normalized(formatstr[i + 1:j])
                if 0 <= x < len(args) - 1:
                    out.append(args[x + 1])
                else:
                    invalid()
                i = j
            else:
                invalid()
        else:
            out.append(formatstr[i])
            i += 1
    return "".join(out)


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
        "uint": ctypes.c_ulong,
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
    "uint": uint,
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
    "tuple": tuple,  # anonymous tuple types: tuple[char, nint] (Nim `(char, int)`)
}


DICT_OF_TYPES.update(__native_types__)
