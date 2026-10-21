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
  Enum utilities       — NStrEnum with succ/pred/ord/subset/low/high.
  Cast & memory        — cast[T](x), sizeof(x), addr(x), unsafeAddr(x).
  Iteration helpers    — fields(obj), fields(obj1, obj2), countdown(a, b).
  Compile-time         — comptime(x), defined("sym"), declared("name"), static.
  Template inlining    — @template, @template_expand (re-exported from inliner).
"""

from __future__ import annotations

import contextlib
import ctypes as _ctypes  # underscore: not re-exported by `from nimic.ntypes import *`
from enum import auto

from nimic.inliner import template, template_expand, do, TemplateBlockError

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
    newString,
    new_cstring_of_cap,
    newCStringOfCap,
    Endianness,
    hostOS,
    hostCPU,
    substr,
    chr,
    ord,
    quit,
    defined,
    declared,
    echo,
    isNil,
    addInt,
    likely,
    unlikely,
    importc,
    stackTraceAvailable,
    writeStackTrace,
    getMaxMem,
    getTotalMem,
    getOccupiedMem,
    instantiationInfo,
    typeof,
    toFloat,
    toInt,
    shallowCopy,
    swap,
    toOpenArray,
    push,
    assign,
    reset,
    include,
    importExcept,
    importFrom,
    pragma,
    emit,
    block,
    static,
    breakBlock,
    _n_setup_stdio,
)
_n_setup_stdio()  # stdio is byte-transparent, like Nim's echo/readLine
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
    NInteger,
    low,
    nint,
    nbool,
    cell,
    NCell,
    uint,
    SomeInteger,
    SomeSignedInt,
    SomeUnsignedInt,
    SomeFloat,
    SomeNumber,
    nord,
    generic,
    openArray,
    pointer,
    pred,
    ptr,
    ref,
    mut,
    out,
    sink,
    lent,
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
    utf8,
    NimicEncodingError,
    ufcs,
    _n_default_value,
    Defect,
    FieldDefect,
    OverflowDefect,
    IndexDefect,
    RangeDefect,
    BackwardsIndex,
    back,
    uncheckedAssign,
)

# system's range types (Nim: Natural = range[0..high(int)], Positive = range[1..high(int)]); as annotations
Natural = Trange[0, high(nint)]
Positive = Trange[1, high(nint)]


class untyped:
    pass


class typed:
    """Nim `typed` (template parameter): marks e.g. a code block parameter of a template."""



BiggestInt = int64
BiggestUInt = uint64
BiggestFloat = float64
DICT_OF_TYPES["BiggestInt"] = int64
DICT_OF_TYPES["BiggestUInt"] = uint64
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


def default(T: type) -> object:
    """Nim: default(T) — the zero value of type T (0, "", nil for ref/ptr, low(T) for enums,
    default-filled arrays and objects). Delegates to the type system's per-type rule."""
    return _n_default_value(T)


discard = None

# compiler hints
const = contextlib.nullcontext()
let = contextlib.nullcontext()
var = contextlib.nullcontext()
Type = contextlib.nullcontext()
template_inline = contextlib.nullcontext()
export = contextlib.nullcontext()
alias = contextlib.nullcontext()


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




def new_exception(except_cls: type, msg: str):
    """Nim: newException — instantiate an exception with a message."""
    exc = except_cls(msg)
    exc.msg = msg
    return exc


newException = new_exception


def equalMem(a, b, size: int) -> bool:
    """Nim: equalMem — compare memory regions."""
    def _to_addr(p):
        if hasattr(p, '_n_addr'): return p._n_addr
        if hasattr(p, '_n_view'): return _ctypes.addressof(p._n_view)
        if hasattr(p, 'contents'):
            c = p.contents
            if hasattr(c, '_n_addr'): return c._n_addr
            if hasattr(c, '_n_view'): return _ctypes.addressof(c._n_view)
        if isinstance(p, int): return p
        try:
            return _ctypes.cast(p, _ctypes.c_void_p).value or 0
        except Exception:
            return 0
    addr_a = _to_addr(a)
    addr_b = _to_addr(b)
    s = int(size)
    if s == 0: return True
    if addr_a == 0 or addr_b == 0: return False
    buf_a = (_ctypes.c_char * s).from_address(addr_a).raw
    buf_b = (_ctypes.c_char * s).from_address(addr_b).raw
    return buf_a == buf_b


NimVersion = "2.2.4"


class _SystemNamespace:
    """Nim's `system` module, always in scope: `system.x` is nimic's system name x (this module's
    globals), e.g. system.NimVersion, system.getMaxMem; declared("system.x") checks it."""

    def __getattr__(self, name: str) -> object:
        try:
            return globals()[name]
        except KeyError:
            raise AttributeError(f"system has no '{name}'") from None


system = _SystemNamespace()

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
    readFile,
    writeFile,
    readBuffer,
    write_buffer,
    stdin,
    stdout,
    stderr,
)


def incl(s: set, elem: object) -> None:
    """Nim: incl — include an element into a set (a container's own incl, e.g. IntSet's, wins)."""
    own = getattr(type(s), "incl", None)
    if own is not None:
        own(s, elem)
    else:
        s.add(elem)


def excl(s: set, elem: object) -> None:
    """Nim: excl — exclude an element from a set (a container's own excl wins)."""
    own = getattr(type(s), "excl", None)
    if own is not None:
        own(s, elem)
    else:
        s.discard(elem)


def contains_or_incl(s: set, elem: object) -> bool:
    """Nim: containsOrIncl — returns True if elem was already in s, else adds elem and returns False.
    The overloads of other modules (std/intsets) coexist in Nim: a container's own operation wins."""
    own = getattr(type(s), "containsOrIncl", None) or getattr(type(s), "contains_or_incl", None)
    if own is not None:
        return own(s, elem)
    if elem in s:
        return True
    s.add(elem)
    return False


containsOrIncl = contains_or_incl


def items(coll):
    """Nim: items — iterator over elements of a collection."""
    return iter(coll)


def pairs(coll):
    """Nim: pairs — (index, item) of a seq, array or string; a collection's own pairs (tables:
    (key, value))."""
    own = getattr(coll, "pairs", None)
    if callable(own):
        return own()
    return ((nint(i), x) for i, x in enumerate(coll))


def mitems(coll):
    """Nim: mitems — elements that can be assigned in place (`x <<= v`; objects: `x.field = v`)."""
    return coll.mitems


from nimic.system.ansi_c import copy_mem, move_mem, cint, cuint
copyMem = copy_mem
moveMem = move_mem


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


def plus_percent(a, b):
    """Nim: a +% b — wrapping addition. Delegates to NInteger.plus_percent;
    a plain int operand adopts the type of its NInteger peer (else Nim int)."""
    return NInteger._n_lift(a, b).plus_percent(b)


def ashr(x, y):
    """Nim: ashr(x, y) — arithmetic shift right of a signed integer (NInteger.ashr); a plain int is Nim int."""
    return NInteger._n_lift(x).ashr(y)


def minus_percent(a, b):
    """Nim: a -% b — wrapping subtraction. Delegates to NInteger.minus_percent;
    a plain int operand adopts the type of its NInteger peer (else Nim int)."""
    return NInteger._n_lift(a, b).minus_percent(b)


def lt_percent(a, b) -> bool:
    """Nim: a <% b — unsigned comparison in the operand type's width (NInteger.lt_percent)."""
    return NInteger._n_lift(a, b).lt_percent(b)


def le_percent(a, b) -> bool:
    """Nim: a <=% b — unsigned comparison (NInteger.le_percent)."""
    return NInteger._n_lift(a, b).le_percent(b)


def gt_percent(a, b) -> bool:
    """Nim: a >% b — unsigned comparison (NInteger.gt_percent)."""
    return NInteger._n_lift(a, b).gt_percent(b)


def ge_percent(a, b) -> bool:
    """Nim: a >=% b — unsigned comparison (NInteger.ge_percent)."""
    return NInteger._n_lift(a, b).ge_percent(b)


def move(x):
    """Nim: move — move value / transfer ownership."""
    return x




def cmp(x, y) -> int:
    """Nim: cmp — three-way comparison (-1 if x < y, 0 if x == y, 1 if x > y)."""
    return (x > y) - (x < y)


