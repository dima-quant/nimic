"""
nimic ntypes module
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Public API for the nimic DSL, a Python-embedded DSL that emulates Nim's
type semantics. Re-exports the core type system from ntypesystem (dispatch,
converter, distinct, Object, NIntEnum, seq, UncheckedArray, scalar types, string)
and adds Nim keyword shims, builtins, and compiler hints so that nimic code can
run in Python. Code written using these types and keywords runs natively in Python AND
transpiles to equivalent Nim code via the nimic transpiler.

Contents:

  Re-exports           — all core types and decorators from ntypesystem.
  Type aliases         — SomeInteger, SomeFloat, BiggestInt, BiggestFloat,
                         untyped, u64, i64, f64.
  Compiler hints       — const, let, var, block, export, alias
                         Implemented as contextlib.nullcontext() (no-ops in
                         Python, transpiled to Nim scope qualifiers).
  Reference types      — ref, ptr, mut (SomeRefClass instances)
                         The @ operator returns identity; transpiled to
                         Nim ref/ptr/var annotations.
  Enum utilities       — NStrEnum with succ/pred/ord/nrange/subset/low/high.
  Cast & memory        — cast[T](x), sizeof(x), addr(x), unsafeAddr(x).
  Iteration helpers    — fields(obj), fields(obj1, obj2), countdown(a, b).
  Compile-time         — comptime(x), defined(varname), static.
  Template inlining    — @template, @template_expand (re-exported from inliner).
"""

from __future__ import annotations

import contextlib
from enum import StrEnum, auto
from typing import Generator, TypeVar

from nimic.inliner import template, template_expand
from nimic.ntypesystem import (
    NIntEnum,
    Object,
    NTuple,
    UncheckedArray,
    converter,
    dispatch,
    distinct,
    float16,
    float32,
    float64,
    int8,
    int16,
    int32,
    int64,
    nint,
    seq,
    string,
    uint8,
    uint16,
    uint32,
    uint64,
)


class untyped:
    pass


SomeInteger = int
SomeFloat = float

type BiggestInt = int
type BiggestFloat = float


def u64(x: int) -> uint64:
    return uint64(x)


def i64(x: int) -> int64:
    return int64(x)


def f64(x: float) -> float64:
    return float64(x)


class NStrEnum(StrEnum):
    __members_tuple__ = None
    __indices__ = None

    @classmethod
    def _set_indices(cls) -> None:
        cls.__members_tuple__ = tuple(cls)
        cls.__indices__ = {val: ind for ind, val in enumerate(cls.__members_tuple__)}

    @classmethod
    def first(cls) -> StrEnum:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        return cls.__members_tuple__[0]

    @classmethod
    def last(cls) -> StrEnum:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        return cls.__members_tuple__[-1]

    @classmethod
    def nitems(cls) -> int:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        return len(cls.__members_tuple__)

    @classmethod
    def nrange(cls, first: StrEnum, last: StrEnum) -> StrEnum:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        members = cls.__members_tuple__
        indices = cls.__indices__
        first_ind = indices[first]
        last_ind = indices[last]
        return members[first_ind : last_ind + 1]

    def nrange(item, last: StrEnum) -> StrEnum:
        cls = item.__class__
        if cls.__members_tuple__ is None:
            cls._set_indices()
        members = cls.__members_tuple__
        indices = cls.__indices__
        first_ind = indices[item]
        last_ind = indices[last]
        return members[first_ind : last_ind + 1]

    def succ(item, n: int = 1) -> StrEnum:
        cls = item.__class__
        if cls.__members_tuple__ is None:
            cls._set_indices()
        members = cls.__members_tuple__
        indices = cls.__indices__
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
        if cls.__members_tuple__ is None:
            cls._set_indices()
        ind = cls.__indices__[item]
        return ind


def succ(item: StrEnum, n: int = 1) -> StrEnum:
    return item.succ(n)


def pred(item: StrEnum, n: int = 1) -> StrEnum:
    return succ(item, -n)


def nord(item: StrEnum) -> int:
    return item.ord()


def nrange(first: StrEnum, last: StrEnum) -> list[StrEnum]:
    return first.nrange(last)


def subset(newname: str, first: NStrEnum, last: NStrEnum) -> type:
    cls = first.__class__
    return NStrEnum(newname, [(a.name, a.value) for a in nrange(first, last)])


def low[T: StrEnum](cls: T) -> T:
    return cls.first()


def high[T: StrEnum](cls: T) -> T:
    return cls.last()


class _SomeRefClass:
    def __matmul__(self, other: object) -> object:
        return other

    def __call__(self, other: object) -> object:
        return other

    def __getitem__(self, other: object) -> object:
        return other


ref = _SomeRefClass()
ptr = _SomeRefClass()
# reserve keyword for modifiable variables
mut = _SomeRefClass()

# compiler hints
const = contextlib.nullcontext()
let = contextlib.nullcontext()
var = contextlib.nullcontext()
block = contextlib.nullcontext()
Type = contextlib.nullcontext()
context_template = contextlib.contextmanager
export = contextlib.nullcontext()
alias = contextlib.nullcontext()

static = set


class _SomeCastClass:
    def __getitem__(self, other_cls: type) -> callable:
        if isinstance(other_cls, TypeVar):
            fun = lambda x: x
        else:
            fun = lambda x: other_cls.cast(x)
        return fun


cast = _SomeCastClass()


def sizeof(x: type) -> int:
    return x._n_sizeof()


def make_pointer(x: object) -> object:
    x._n_ref_count += 1
    return x


def addr(x: object) -> object:
    return make_pointer(x)


def unsafe_addr(x: object) -> object:
    return make_pointer(x)


#  presense of comptime in "if" expression forces aot evaluation
def comptime(x: object) -> object:
    return x


def defined(varname: str) -> bool:
    """
    Check if a variable with the given name is defined in the global scope.

    Args:
        varname (str): The name of the variable to check.

    Returns:
        bool: True if the variable is defined in the global scope, False otherwise.
    """
    return varname in globals()


def fields(x: object, y: object | None = None) -> object:
    if y is None:
        for name in x._n_fields:
            yield getattr(x, name)
    else:
        for name in x._n_fields:
            yield getattr(x, name), getattr(y, name)


def countdown(a: int, b: int) -> Generator:
    for i in range(a, b - 1, -1):
        yield i
