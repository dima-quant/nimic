from __future__ import annotations
import ctypes
from enum import StrEnum, auto
from typing import Generator, TypeVar

from nimic.system.ansi_c import c_malloc, c_free
from nimic.ntypesystem import char, seq, NIntEnum

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


class Endianness(NIntEnum):
    littleEndian = 0
    bigEndian = auto()


def _detect_host_os():
    import sys
    from nimic.ntypesystem import string
    if sys.platform == "darwin":
        return string("macosx")
    elif sys.platform == "win32":
        return string("windows")
    elif sys.platform.startswith("linux"):
        return string("linux")
    elif sys.platform.startswith("freebsd"):
        return string("freebsd")
    elif sys.platform.startswith("openbsd"):
        return string("openbsd")
    elif sys.platform.startswith("netbsd"):
        return string("netbsd")
    elif sys.platform.startswith("solaris") or sys.platform.startswith("sunos"):
        return string("solaris")
    elif sys.platform.startswith("aix"):
        return string("aix")
    return string("any")


def _detect_host_cpu():
    import os
    from nimic.ntypesystem import string
    if hasattr(os, "uname"):
        arch = os.uname().machine.lower()
    else:
        import os as _os
        arch = _os.environ.get("PROCESSOR_ARCHITECTURE", "any").lower()
    if arch in ["x86_64", "amd64"]:
        return string("amd64")
    elif arch in ["i386", "i686", "x86"]:
        return string("i386")
    elif arch in ["arm64", "aarch64"]:
        return string("arm64")
    elif arch.startswith("arm"):
        return string("arm")
    elif arch.startswith("mips64"):
        return string("mips64")
    elif arch.startswith("mips"):
        return string("mips")
    elif arch.startswith("riscv32"):
        return string("riscv32")
    elif arch.startswith("riscv64"):
        return string("riscv64")
    elif arch.startswith("powerpc64") or arch.startswith("ppc64"):
        return string("powerpc64")
    elif arch.startswith("powerpc") or arch.startswith("ppc"):
        return string("powerpc")
    elif arch.startswith("sparc64"):
        return string("sparc64")
    elif arch.startswith("sparc"):
        return string("sparc")
    elif arch.startswith("s390x"):
        return string("s390x")
    return string("any")


hostOS = _detect_host_os()
hostCPU = _detect_host_cpu()


def substr(s, first: int = 0, last: int | None = None):
    """Nim: substr — slice string from `first` to `last` (inclusive)."""
    from nimic.ntypesystem import string
    s_val = str(s)
    f = max(int(first), 0)
    if last is None:
        l = len(s_val) - 1
    else:
        l = min(int(last), len(s_val) - 1)
    if f <= l:
        return string(s_val[f:l + 1])
    return string("")


import builtins as _builtins

def ord(x) -> int:
    """Nim: ord(x) — returns ordinal integer of an enum, char, int, bool, or StrEnum."""
    if hasattr(x, 'ord'):
        return x.ord()
    if hasattr(x, 'value') and isinstance(x.value, int):
        return x.value
    if isinstance(x, (int, bool)):
        return int(x)
    return _builtins.ord(x)


def quit(error: int | str = 0) -> None:
    """Nim: quit — exit process with exit code or message."""
    import sys
    if isinstance(error, int):
        sys.exit(error)
    else:
        sys.exit(str(error))

