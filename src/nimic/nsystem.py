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