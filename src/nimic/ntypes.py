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
from enum import auto

from nimic.inliner import template, template_expand

from nimic.nsystem import (
    alloc_shared0,
    dealloc_shared,
    write_bytes,
    cast,
    sizeof,
    countdown,
    fields,
    nrange,
    NStrEnum,
    newSeq,
    new_seq,
    low,
    high,
    pred,
    nord,
    subset,
)
from nimic.ntypesystem import (
    addr,
    unsafe_addr,
    NIntEnum,
    Object,
    NTuple,
    UncheckedArray,
    array,
    calltype,
    char,
    converter,
    dispatch,
    distinct,
    File,
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
    typedesc,
    intp,
    uintp,
    pointer,
    ptr,
    uint8,
    uint16,
    uint32,
    uint64,
    openArray,
    cstring,
)


class untyped:
    pass


SomeInteger = int
SomeFloat = float

type BiggestInt = int
type BiggestFloat = float


byte = uint8  # Nim: byte = uint8

def u8(x: int) -> uint8: return uint8(x)
def u16(x: int) -> uint16: return uint16(x)
def u32(x: int) -> uint32: return uint32(x)
def u64(x: int) -> uint64: return uint64(x)

def i8(x: int) -> int8: return int8(x)
def i16(x: int) -> int16: return int16(x)
def i32(x: int) -> int32: return int32(x)
def i64(x: int) -> int64: return int64(x)

def f16(x: float) -> float16: return float16(x)
def f32(x: float) -> float32: return float32(x)
def f64(x: float) -> float64: return float64(x)

def ch(x: str) -> char: return char(x)



# compiler hints
const = contextlib.nullcontext()
let = contextlib.nullcontext()
var = contextlib.nullcontext()
block = contextlib.nullcontext()
Type = contextlib.nullcontext()
template_inline = contextlib.nullcontext()
export = contextlib.nullcontext()
alias = contextlib.nullcontext()

static = set

def doAssert(cond: bool, msg: str = "") -> None:
    """
    Evaluates the condition. If it is false, raises an AssertionError with the provided message.
    Corresponds to Nim's `doAssert`.

    Args:
        cond (bool): The condition to evaluate.
        msg (str): The optional error message if the condition fails.
    """
    if not cond:
        raise AssertionError(msg)

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


