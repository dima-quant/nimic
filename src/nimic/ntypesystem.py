"""
nimic ntypesystem
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Core type system for the nimic DSL — imported by ntypes.py, which adds
keywords, builtins, and re-exports everything under a single public API.

Architecture (layers from low-level to high-level):

  Memory layer (ctypes-backed)
    Ntype              — base class wrapping a ctypes buffer + view for value semantics
    NTypeRegistry      — unified registry (types, c_types, variants, max_variants)

  Scalar numerics (NScalar → NInteger / NFloat)
    Fixed-width integers: int8..int64, uint8..uint64, nint
    IEEE-754 floats: float16, float32, float64
    Arithmetic promotion via determine_common_type().
    All arithmetic, comparison, bitwise, in-place, and reflected operators
    are overloaded with proper type promotion and overflow/wrap semantics.

  Structured types (Object)
    Object             — Nim "object"; fields declared via annotations
                         (e.g. x: float64), backed by ctypes.Structure.
    NIntEnum           — Nim integer enum; auto-registers in DICT_OF_TYPES.
    Variant types      — Nim "case object"; detected by the presence of a
                         "kind" field with a match/case block.

  Containers
    seq[T]             — Nim's growable sequence; ctypes array + cache.
    UncheckedArray[T]  — Nim's UncheckedArray; pointer-indexed.

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
import ctypes
import inspect as ins
import operator
import struct
import sys
import textwrap
from enum import IntEnum
from string import Template

__resolved__ = {}

__dispatch_generic__ = {}

__dispatch_genericT__ = {}

__tdefs__ = {}

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
_n_aliases = {"float": "float64", "int": "int32", "str": "string"}


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


def autorename(x: object) -> str:
    type_name = type(x).__name__
    if type_name in _n_aliases:
        return _n_aliases[type_name]
    elif type_name == "type" or type_name == "NMetaClass":
        return f"type[{x.__name__}]"
    else:
        return type_name


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

    if not len(sig_list) == arg_count:
        sig_str = ", ".join(sig_list)
        raise Exception(
            f"type not found for all arguments of {fn.__name__}, only the following: {sig_str}"
        )
    generic = any((arg in _n_generic_types for arg in sig_list))
    genericT = len(fn.__type_params__) > 0
    # register signature
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
    else:
        sigs = tuple((arg,) for arg in sig_list)
        if fn.__name__ in __resolved__:
            __resolved__[fn.__name__][sigs] = fn
        else:
            __resolved__[fn.__name__] = {sigs: fn}

    def fn_dispatch(*args):
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
                for sig_def in sig_defs:
                    if len(fn_sig) == len(sig_def):
                        i = 0
                        T_var = {}
                        T_def = __tdefs__[fn.__name__][sig_def]
                        while i < len(fn_sig) and (
                            fn_sig[i][0] in sig_def[i] or sig_def[i][0] in T_def
                        ):
                            if sig_def[i][0] in T_def:
                                T_sym = sig_def[i][0]
                                # check if T already in t_var
                                T_value = fn_sig[i][0]
                                if T_sym in T_var:
                                    if not T_var[T_sym] == T_value:
                                        break
                                else:
                                    # validate the value of T according to T_def if any
                                    if len(T_def[T_sym]) == 0:
                                        T_var[T_sym] = T_value
                                    else:
                                        if T_value in T_def[T_sym]:
                                            T_var[T_sym] = T_value
                                        elif (
                                            T_def[T_sym] in _n_generic_types
                                            and T_value
                                            in _n_generic_types[T_def[T_sym]]
                                        ):
                                            T_var[T_sym] = T_value
                                        else:
                                            break
                            i += 1
                        if i == len(fn_sig):
                            if fn.__name__ in __resolved__:
                                __resolved__[fn.__name__][fn_sig] = sig_defs[sig_def]
                            else:
                                __resolved__[fn.__name__] = {fn_sig: sig_defs[sig_def]}
                            break
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


_n_registry = NTypeRegistry()

# Backward-compatible aliases — these point to the same dict objects
DICT_OF_TYPES = _n_registry.types
DICT_OF_C_TYPES = _n_registry.c_types
DICT_OF_VARIANTS = _n_registry.variants
DICT_OF_MAX_VARIANTS = _n_registry.max_variants

# --- Base Memory Type (Ntype) ---


class Ntype:
    _n_buffer: object  # ctypes buffer
    _n_view: object = None  # ctypes buffer or value
    _n_type: type  # type of the value
    _n_ref_count: int = 0

    def __init__(self) -> None:
        self._n_buffer = None
        self._n_view = None
        self._n_type = None
        self._n_ref_count = 0

    @classmethod
    def _n_on_struct(cls, buffer: object, name: str, value: object) -> Ntype:
        pass

    @classmethod
    def _n_on_array(cls, buffer: object, name: str, value: object) -> Ntype:
        pass

    def _n_get_value(self) -> object:
        pass

    def _n_set_value(self, value: object) -> None:
        pass

    def _n_get_address(self) -> object:
        return self._n_view

    @classmethod
    def cast(cls, instance: Ntype) -> Ntype:
        address = ctypes.addressof(instance._n_view)
        if hasattr(cls, "_n_type"):
            type_name = cls._n_type.__name__
            if type_name not in DICT_OF_C_TYPES:
                cls._n_type._n_register_type()
            c_elem_type = DICT_OF_C_TYPES[type_name]
            ptr_c_type = ctypes.POINTER(c_elem_type)
            data_ptr = ctypes.c_void_p(address)
            c_data = ctypes.cast(data_ptr, ptr_c_type)
            self = cls(c_data)
            if hasattr(instance, "_n_buffer"):
                self._n_buffer = instance._n_buffer  # new reference to the buffer
            return self
        else:
            raise Exception("Type not specified")


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

    # def next(self):
    #     try:
    #         return self.__class__(self + 1)
    #     except ValueError:
    #         return self


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


class Object(Ntype, metaclass=NMetaClass):
    def __init_subclass__(cls) -> None:
        cls._n_register_type()

    def __init__(self, _n_value: Object | None = None, **kwargs: object) -> None:
        """_n_value is an instance of Object or an object with the same structure or None"""
        _has_c_type = False
        for attr_name, _type_name in self.__annotations__.items():
            # check if at least one field is not a sequence
            _has_c_type = _has_c_type or not _type_name.startswith("seq[")
            if _type_name.startswith("seq["):
                seq._n_register_type(_type_name)
                setattr(self, attr_name, DICT_OF_TYPES[_type_name]())
        self._n_has_c_type = _has_c_type
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
                self._n_view = value._n_get_value()  # copy also _n_buffer?
            else:
                self._n_buffer = DICT_OF_C_TYPES[class_name]()
                self._n_view = self._n_buffer
            self._n_setup(value)

    @classmethod
    def _n_on_array(
        cls, parent_elems: object, id: int, value: Object | None = None
    ) -> Object:
        self = cls.__new__(cls)
        self._n_view = parent_elems[id]
        self._n_has_c_type = True
        self._n_setup(value)
        return self

    @classmethod
    def _n_on_struct(
        cls, parent_elems: object, id: str, value: Object | None = None
    ) -> Object:
        self = cls.__new__(cls)
        self._n_view = getattr(parent_elems, id)
        self._n_has_c_type = True
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
            if value:
                kind = value.kind
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
            self._n_annotations = DICT_OF_VARIANTS[class_name][int(kind)]
            attributes = list(self._n_annotations.keys())
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

    @property
    def contents(self):
        return self

    def _n_get_value(self) -> object:
        return self._n_view

    def _n_set_value(self, other: Object | None) -> None:
        # create attributes with corresponding/default values
        for name in self._n_fields:
            type_name = self._n_annotations[name]
            # type of each field should be already in the dict of types
            if type_name in DICT_OF_TYPES and not type_name.startswith("seq["):
                if other:
                    _value = getattr(other, name)
                    setattr(
                        self,
                        name,
                        DICT_OF_TYPES[type_name]._n_on_struct(
                            self._n_view, name, _value
                        ),
                    )
                elif type_name == "bool":
                    # TO DO implement bool properly
                    setattr(self, name, DICT_OF_TYPES[type_name]())
                else:
                    setattr(
                        self,
                        name,
                        DICT_OF_TYPES[type_name]._n_on_struct(self._n_view, name),
                    )
            elif type_name.startswith("ptr["):
                setattr(self, name, None)

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
    def _n_check_type(cls) -> bool:
        class_name = cls.__name__
        has_c_type = not class_name.startswith("seq[")
        has_c_type = has_c_type and not class_name.startswith("tuple")
        return has_c_type

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
        if len(cls.__annotations__) == 0:
            # this should be distinct or alias type
            cls.__annotations__ = cls.__bases__[0].__annotations__
            # assume it is alias (distinct removes it if not)
            if cls.__bases__[0].__name__ in _n_aliases:
                _n_aliases[cls.__name__] = _n_aliases[cls.__bases__[0].__name__]
            else:
                _n_aliases[cls.__name__] = cls.__bases__[0].__name__
        class_name = cls.__name__
        dict_of_types[class_name] = cls
        has_c_type = cls._n_check_type()
        attributes = list(cls.__annotations__)
        # variant type is suspected if there is only one attribute in annotations
        if len(attributes) == 1:
            _annotations = cls._n_resolve_variant(dict_of_types, dict_of_c_types)
        else:
            _annotations = cls.__annotations__
        # check if at least one field is a not a sequence and at least one is a sequence
        _has_c_type = False
        for key, _type_name in _annotations.items():
            _has_c_type = _has_c_type or not _type_name.startswith("seq[")
            if _type_name.startswith("seq["):
                seq._n_register_type(_type_name)
        has_c_type = has_c_type and _has_c_type
        if has_c_type:
            c_class_name = "c_" + class_name
            # check if all fields have corresponding types registered
            for key, value in _annotations.items():
                if not value.startswith("seq[") and not value.startswith("ptr["):
                    assert value in dict_of_types
            f_list = [
                (key, dict_of_c_types[value])
                for key, value in _annotations.items()
                if value in dict_of_c_types
            ]
            _c_type = type(c_class_name, (ctypes.Structure,), {"_fields_": f_list})
            dict_of_c_types[class_name] = _c_type

    @classmethod
    def _n_c_type(cls) -> type:
        return DICT_OF_C_TYPES[cls.__name__]


# --- UncheckedArray ---


class UncheckedArray(Ntype):
    def __init__(self, data_ptr: int) -> None:
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
        class_name = f"ptr[UncheckedArray[{_ntype.__name__}]]"
        return type(class_name, (UncheckedArray,), {"_n_type": _ntype})


# --- Sequences (seq) ---


class seq(Ntype):
    def __init__(self, c_base: object | None = None) -> None:
        self._n_cache = {}
        self.len = 0
        self._n_reserved = 1
        if hasattr(self, "_n_type"):
            type_name = self._n_type.__name__
            if type_name not in DICT_OF_C_TYPES:
                self._n_type._n_register_type()
            if c_base:
                self._n_buffer = c_base
            else:
                self._n_buffer = (DICT_OF_C_TYPES[type_name] * self._n_reserved)()
            self._n_view = (self._n_buffer._type_ * self._n_reserved).from_address(
                ctypes.addressof(self._n_buffer)
            )
        else:
            raise Exception("Seq type not specified")

    @property
    def is_nil(self):
        return self._n_view is None

    def __len__(self) -> int:
        return self.len

    def _n_resize(self) -> None:
        ctypes.resize(self._n_buffer, self._n_reserved * self._n_type._n_sizeof())
        self._n_view = (self._n_view._type_ * self._n_reserved).from_address(
            ctypes.addressof(self._n_buffer)
        )
        # invalidate cache
        self._n_cache = {}

    def __getitem__(self, index: int) -> object:
        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        return self._n_cache[index]

    def __setitem__(self, index: int, value: object) -> None:
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
        if self.len == self._n_reserved:
            self._n_reserved = self._n_reserved * 2
            self._n_resize()
        self._n_cache[self.len] = self._n_type._n_on_array(
            self._n_view, self.len, value
        )
        self.len += 1

    def set_len(self, len: int) -> None:
        self.len = len

    @classmethod
    def _n_register_type(cls, class_name: str | None = None) -> None:
        if class_name is None:
            _class_name = cls.__name__
            if _class_name not in DICT_OF_TYPES:
                DICT_OF_TYPES[_class_name] = cls
        elif class_name.startswith("seq[") and class_name.endswith("]"):
            elem_class = DICT_OF_TYPES[class_name[4:-1]]
            seq[elem_class]  # create and register seq type


# --- Type Aliases & Convenience Constructors ---


def determine_common_type(type_a: type, type_b: type) -> type:
    """Implements C-style 'Usual Arithmetic Conversions' for NScalar types.

    Rules: floats beat integers (higher rank wins among floats),
    among integers of the same signedness the higher rank wins,
    for mixed signed/unsigned the unsigned wins if its rank >= signed.
    """
    if issubclass(type_a, NFloat) or issubclass(type_b, NFloat):
        return max([type_a, type_b], key=lambda t: getattr(t, "RANK", 0))

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
        self._n_get_address = get_addr

    def __init__(self, data: float = 0.0) -> None:
        """Initialize a standalone NScalar value with its own _n_value attribute."""
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
        self = cls.__new__(cls)
        offset = id * ctypes.sizeof(parent_elems)
        self._n_bind(
            get_value=lambda: parent_elems[id],
            set_value=lambda _value: parent_elems.__setitem__(
                id, _value._n_get_value() if isinstance(_value, NScalar) else _value
            ),
            get_addr=lambda: ctypes.addressof(parent_elems) + offset,
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
    def _n_c_type(cls) -> type:
        return DICT_OF_C_TYPES[cls.__name__]

    @classmethod
    def _n_sizeof(cls) -> int:
        return ctypes.sizeof(cls._n_c_type())

    @classmethod
    def c_type(cls) -> type:
        return DICT_OF_C_TYPES[cls.__name__]

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
        self._n_set_value(other._n_get_value())
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
        elif hasattr(other, "__float__"):  # check if numeric literal or other scalar
            target_type = self._n_type
            res_val = op_func(self._n_get_value(), other)
            return target_type(res_val)
            # For raw Python scalars, we treat the scalar as the same type as self
            # for basic interaction, though C would promote.
        return op_func(self._n_get_value(), other)

    def _n_rop(self, other: NScalar | int | float, op_func: callable) -> NScalar:
        if isinstance(other, NScalar):
            target_type = determine_common_type(self._n_type, other._n_type)
            res_val = op_func(other._n_get_value(), self._n_get_value())
            return target_type(res_val)
        elif hasattr(other, "__float__"):  # check if numeric literal or other scalar
            target_type = self._n_type
            res_val = op_func(other, self._n_get_value())
            return target_type(res_val)
            # For raw Python scalars, we treat the scalar as the same type as self
            # for basic interaction, though C would promote.
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
    def __init__(self, length: int):
        self = new_string(length)


def new_string(length: int) -> cstring:
    return ctypes.create_string_buffer(length)


# def string(s) -> String:
#     return s.value

# --- String Type ---


class string(str):
    def __and__(self, other):
        return self + other

    def _substitute(self, **kwargs):
        return Template(self).substitute(**kwargs)

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

# remove when in Nim
to_string = string
_s = string

# --- Type Registry Initialization ---

DICT_OF_C_TYPES.update(
    {
        "float64": ctypes.c_double,
        "float32": ctypes.c_float,
        "int32": ctypes.c_int,
        "int64": ctypes.c_long,
        "nint": ctypes.c_long,
        "uint32": ctypes.c_uint,
        "uint64": ctypes.c_ulong,
        "bool": ctypes.c_bool,
    }
)


__native_types__ = {
    "bool": bool,
    "float64": float64,
    "float32": float32,
    "nint": nint,
    "int32": int32,
    "int64": int64,
    "uint32": uint32,
    "uint64": uint64,
    "string": string,
    "list": list,
}


DICT_OF_TYPES.update(__native_types__)
