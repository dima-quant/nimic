from __future__ import annotations
import ctypes
from enum import StrEnum
from typing import Generator, TypeVar

from nimic.system.ansi_c import c_malloc, c_free
from nimic.ntypesystem import char, seq

class _SomeCastClass:
    def __getitem__(self, other_cls: type) -> callable:
        # cast from value type to value type: convert object to bytes, construct from bytes
        # cast from pointer to pointer: ctypes pointer cast
        # cast from pointer to uintp: pointer that supports arithmetics
        # cast from uintp to pointer: ctypes cast from address to pointer
        # all pointer casts should keep the buffer reference to prevent GC
        if isinstance(other_cls, TypeVar):
            fun = lambda x: x
        else:
            fun = lambda x: other_cls.cast(x)
        return fun


cast = _SomeCastClass()


def sizeof(x: type) -> int:
    return x._n_sizeof()



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

# --- Nim system builtins ---

def alloc_shared0(size):
    """Nim: allocShared0 — allocate zero-initialized shared memory."""
    return c_malloc(size)

def dealloc_shared(p):
    """Nim: deallocShared — free shared memory."""
    c_free(p)

allocShared0 = alloc_shared0
deallocShared = dealloc_shared


def write_bytes(f, data, start: int, count: int) -> int:
    """Nim: writeBytes — write count bytes from data starting at offset start to file f.
    Returns number of bytes written."""
    if hasattr(data, '_n_view'):
        # seq or array with ctypes backing
        buf_addr = ctypes.addressof(data._n_view)
        raw = (ctypes.c_char * (start + count)).from_address(buf_addr)
        b = bytes(raw[start:start + count])
    elif isinstance(data, (bytes, bytearray)):
        b = data[start:start + count]
    else:
        b = bytes(int(data[i]) for i in range(start, start + count))
    return f.buffer.write(b) if hasattr(f, 'buffer') else f.write(b)

writeBytes = write_bytes


class _NewSeqHelper:
    """Nim: newSeq[T](n) — create a seq[T] of length n."""
    def __getitem__(self, _ntype: type):
        def _make(n: int):
            s = seq[_ntype]()
            s.new_seq(n)
            return s
        return _make

newSeq = _NewSeqHelper()
new_seq = newSeq


def new_string_of_cap(cap: int):
    """Nim: newStringOfCap — create a string with a zero-filled buffer of
    *cap* bytes.  The resulting string is empty (len 0 in str terms) but its
    ``_n_view`` ctypes buffer has *cap* bytes available for in-place writes."""
    from nimic.ntypesystem import string
    return string(cap)

newStringOfCap = new_string_of_cap


def new_cstring_of_cap(cap: int):
    """Create a cstring with a zero-filled buffer of *cap* bytes."""
    from nimic.ntypesystem import cstring
    return cstring(cap)

newCStringOfCap = new_cstring_of_cap
