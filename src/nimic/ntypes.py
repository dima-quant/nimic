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
    newSeq,
    new_seq,
    new_string_of_cap,
    newStringOfCap,
    new_cstring_of_cap,
    newCStringOfCap,
    Endianness,
    hostOS,
    hostCPU,
    substr,
    ord,
    quit,
)
from nimic.ntypesystem import (
    DICT_OF_TYPES,
    addr,
    unsafe_addr,
    NIntEnum,
    NStrEnum,
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
    high,
    inrange,
    int8,
    int16,
    int32,
    int64,
    low,
    nint,
    nord,
    openArray,
    pointer,
    pred,
    ptr,
    ref,
    mut,
    seq,
    string,
    subset,
    succ,
    Trange,
    Tset,
    typedesc,
    intp,
    uintp,
    uint8,
    uint16,
    uint32,
    uint64,
    cstring,
)


class untyped:
    pass


SomeInteger = int
SomeFloat = float

BiggestInt = int64
BiggestFloat = float64
DICT_OF_TYPES["BiggestInt"] = int64
DICT_OF_TYPES["BiggestFloat"] = float64

RootObj = Object
nil = None


from enum import Enum as enum
DICT_OF_TYPES["enum"] = enum

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

from nimic._nkeywords import default
discard = None

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

def raiseAssert(msg: str = "") -> None:
    """Raises an AssertionError with the provided message. Corresponds to Nim raiseAssert."""
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


echo = print


def new_exception(except_cls: type, msg: str):
    """Nim: newException — instantiate an exception with a message."""
    exc = except_cls(msg)
    exc.msg = msg
    return exc


newException = new_exception


def writeFile(filename: str | string, content: str | string) -> None:
    """Nim: writeFile — write string content to a file."""
    with open(str(filename), 'w') as f:
        f.write(str(content))


def readFile(filename: str | string) -> string:
    """Nim: readFile — read entire file contents as string."""
    with open(str(filename), 'rb') as f:
        return string(f.read())


def equalMem(a, b, size: int) -> bool:
    """Nim: equalMem — compare memory regions."""
    import ctypes
    def _to_addr(p):
        if hasattr(p, '_n_addr'): return p._n_addr
        if hasattr(p, '_n_view'): return ctypes.addressof(p._n_view)
        if hasattr(p, 'contents'):
            c = p.contents
            if hasattr(c, '_n_addr'): return c._n_addr
            if hasattr(c, '_n_view'): return ctypes.addressof(c._n_view)
        if isinstance(p, int): return p
        try:
            return ctypes.cast(p, ctypes.c_void_p).value or 0
        except Exception:
            return 0
    addr_a = _to_addr(a)
    addr_b = _to_addr(b)
    s = int(size)
    if s == 0: return True
    if addr_a == 0 or addr_b == 0: return False
    buf_a = (ctypes.c_char * s).from_address(addr_a).raw
    buf_b = (ctypes.c_char * s).from_address(addr_b).raw
    return buf_a == buf_b


class _SystemNamespace:
    NimVersion = "2.2.4"
    hostOS = hostOS
    hostCPU = hostCPU


system = _SystemNamespace()
NimVersion = system.NimVersion

from nimic.std.syncio import (
    FileMode,
    fmRead,
    fmWrite,
    fmAppend,
    fmReadWrite,
    fmReadWriteExisting,
    open,
    close,
    write,
    readLine,
    readBuffer,
    write_buffer,
    stdin,
    stdout,
    stderr,
)


def incl(s: set, elem: object) -> None:
    """Nim: incl — include an element into a set."""
    s.add(elem)


def excl(s: set, elem: object) -> None:
    """Nim: excl — exclude an element from a set."""
    s.discard(elem)


def contains_or_incl(s: set, elem: object) -> bool:
    """Nim: containsOrIncl — returns True if elem was already in s, else adds elem and returns False."""
    if elem in s:
        return True
    s.add(elem)
    return False


containsOrIncl = contains_or_incl


def items(coll):
    """Nim: items — iterator over elements of a collection."""
    return iter(coll)


from nimic.system.ansi_c import copy_mem
copyMem = copy_mem


def setLen(s, new_len: int) -> None:
    """Nim: setLen — set length of string or seq."""
    if hasattr(s, 'setLen'):
        s.setLen(new_len)
    elif hasattr(s, 'set_len'):
        s.set_len(new_len)
    elif isinstance(s, list):
        nl = int(new_len)
        if nl <= len(s):
            del s[nl:]
        else:
            s.extend([None] * (nl - len(s)))

