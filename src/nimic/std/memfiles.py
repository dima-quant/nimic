"""Nim std/memfiles — memory mapped files, ported from Nim 2.2.4's lib/pure/memfiles.nim (POSIX side): the file
is opened with open(2) and mapped with the C library's mmap, so `mem` is the address of the mapping, PROT_READ
for fmRead as in Nim (writing to it crashes, as in Nim). Windows is not supported (OSError).

MemFile, open, close, flush, mapMem, unmapMem, resize, MemSlice (== and $), memSlices, lines."""
from __future__ import annotations
import ctypes as _ctypes
import mmap as _mmap
import os as _os
import sys as _sys

from nimic.ntypes import Object, char, cint, dispatch, nint, pointer, string
from nimic.std.syncio import lines  # memfiles' lines overloads extend syncio's (Nim: overloads)

if _sys.platform == "win32":
    raise OSError("nimic std/memfiles: Windows is not supported (POSIX mmap only)")

_libc = _ctypes.CDLL(None, use_errno=True)
_libc.mmap.restype = _ctypes.c_void_p
_libc.mmap.argtypes = (_ctypes.c_void_p, _ctypes.c_size_t, _ctypes.c_int, _ctypes.c_int, _ctypes.c_int,
                       _ctypes.c_long)
_libc.munmap.argtypes = (_ctypes.c_void_p, _ctypes.c_size_t)
_libc.msync.argtypes = (_ctypes.c_void_p, _ctypes.c_size_t, _ctypes.c_int)
_libc.memchr.restype = _ctypes.c_void_p
_libc.memchr.argtypes = (_ctypes.c_void_p, _ctypes.c_int, _ctypes.c_size_t)

_PROT_READ, _PROT_WRITE = _mmap.PROT_READ, _mmap.PROT_WRITE
_MAP_SHARED, _MAP_PRIVATE = _mmap.MAP_SHARED, _mmap.MAP_PRIVATE
_MAP_FAILED = _ctypes.c_void_p(-1).value
_MS_SYNC, _MS_INVALIDATE = (0x10, 0x2) if _sys.platform == "darwin" else (4, 2)


def _n_mode(mode) -> str:
    """A file mode's value ("r", "w+", ...): syncio's FileMode members and os' strings alike."""
    return getattr(mode, "value", mode)


def _raise_os_error() -> None:
    err = _ctypes.get_errno()
    raise OSError(err, _os.strerror(err))


class MemFile(Object):
    """Represents a memory mapped file."""
    mem: pointer  # a pointer to the memory mapped file; nil when it is closed
    size: nint  # size of the memory mapped file
    handle: cint  # (POSIX) the file's descriptor while remapping is allowed, else -1
    _flags: cint


def _setFileSize(fh: int, newFileSize: int = -1, oldSize: int = -1) -> None:
    if newFileSize < 0 or newFileSize == oldSize:
        return
    # grow or shrink (posix_fallocate where it exists, as Nim; ftruncate otherwise)
    if newFileSize > oldSize and hasattr(_os, "posix_fallocate"):
        try:
            _os.posix_fallocate(fh, 0, newFileSize)
            return
        except OSError:
            pass
    _os.ftruncate(fh, newFileSize)


def mapMem(m: MemFile, mode=None, mappedSize: int = -1, offset: int = 0, mapFlags: int = -1) -> pointer:
    """Nim: mapMem — map a part of an opened (allowRemap = true) file; mappedSize > 0."""
    mode = _n_mode(mode if mode is not None else "r")
    if mode == "a":
        raise IOError("The append mode is not supported.")
    readonly = mode == "r"
    assert int(mappedSize) > 0
    flags = _MAP_SHARED if int(mapFlags) == -1 else int(mapFlags)
    if flags & _MAP_PRIVATE == 0:
        flags |= _MAP_SHARED
    m._flags = flags
    result = _libc.mmap(None, int(mappedSize), _PROT_READ if readonly else _PROT_READ | _PROT_WRITE, flags,
                        int(m.handle), int(offset))
    if result == _MAP_FAILED:
        _raise_os_error()
    return pointer(result)


def unmapMem(f: MemFile, p: pointer, size: int) -> None:
    """Nim: unmapMem — unmap a part mapped with mapMem."""
    if _libc.munmap(p._n_addr, int(size)) != 0:
        _raise_os_error()


def open(filename: string, mode=None, mappedSize: int = -1, offset: int = 0, newFileSize: int = -1,  # noqa: A001
         allowRemap: bool = False, mapFlags: int = -1) -> MemFile:
    """Nim: memfiles.open — open a memory mapped file (fmRead: read only). newFileSize >= 0 creates or
    truncates it to that size (not with fmRead). mappedSize = -1 maps the whole file. allowRemap keeps the
    descriptor open for mapMem / resize."""
    result = MemFile()
    result.handle = -1
    mode = _n_mode(mode if mode is not None else "r")
    if mode == "a":
        raise IOError("The append mode is not supported.")
    assert int(newFileSize) == -1 or mode != "r"
    readonly = mode == "r"

    def fail(err: OSError):
        result.mem = None
        result.size = 0
        if int(result.handle) != -1:
            _os.close(int(result.handle))
        raise err

    flags = (_os.O_RDONLY if readonly else _os.O_RDWR) | _os.O_CLOEXEC
    try:
        if int(newFileSize) != -1:
            result.handle = _os.open(str(filename), flags | _os.O_CREAT | _os.O_TRUNC, 0o600)
            try:
                _setFileSize(int(result.handle), int(newFileSize))
            except OSError as e:
                fail(e)
        else:
            result.handle = _os.open(str(filename), flags)
    except OSError as e:
        if int(result.handle) == -1:
            fail(e)
        raise
    if int(mappedSize) != -1:
        result.size = int(mappedSize)
    else:
        try:
            result.size = _os.fstat(int(result.handle)).st_size
        except OSError as e:
            fail(e)
    mflags = _MAP_SHARED if int(mapFlags) == -1 else int(mapFlags)
    if mflags & _MAP_PRIVATE == 0:
        mflags |= _MAP_SHARED
    result._flags = mflags
    address = _libc.mmap(None, int(result.size), _PROT_READ if readonly else _PROT_READ | _PROT_WRITE, mflags,
                         int(result.handle), int(offset))
    if address == _MAP_FAILED:
        err = _ctypes.get_errno()
        fail(OSError(err, _os.strerror(err)))
    result.mem = pointer(address)
    if not allowRemap and int(result.handle) != -1:
        _os.close(int(result.handle))
        result.handle = -1
    return result


def flush(f: MemFile, attempts: int = 3) -> None:
    """Nim: flush — write the mapping's changes to the file (msync), retrying while it is busy."""
    for _ in range(int(attempts)):
        if _libc.msync(f.mem._n_addr, int(f.size), _MS_SYNC | _MS_INVALIDATE) == 0:
            return
        err = _ctypes.get_errno()
        if err != 16:  # EBUSY
            raise OSError(err, "error flushing mapping: " + _os.strerror(err))


def resize(f: MemFile, newFileSize: int) -> None:
    """Nim: resize — resize the file and remap it (needs allowRemap = true)."""
    if int(newFileSize) < 1:
        raise IOError("Cannot resize MemFile to < 1 byte")
    if int(f.handle) == -1:
        raise IOError("Cannot resize MemFile opened with allowRemap=false")
    if int(newFileSize) != int(f.size):
        _setFileSize(int(f.handle), int(newFileSize), int(f.size))
    if _libc.munmap(f.mem._n_addr, int(f.size)) != 0:
        _raise_os_error()
    address = _libc.mmap(None, int(newFileSize), _PROT_READ | _PROT_WRITE, int(f._flags), int(f.handle), 0)
    if address == _MAP_FAILED:
        _raise_os_error()
    f.mem = pointer(address)
    f.size = int(newFileSize)


def close(f: MemFile) -> None:
    """Nim: memfiles.close — unmap the file (and close its descriptor if kept open)."""
    error = None
    if f.mem is not None and getattr(f.mem, "_n_addr", 0):
        if _libc.munmap(f.mem._n_addr, int(f.size)) != 0:
            err = _ctypes.get_errno()
            error = OSError(err, _os.strerror(err))
    if int(f.handle) != -1:
        try:
            _os.close(int(f.handle))
        except OSError as e:
            error = error or e
    f.size = 0
    f.mem = None
    f.handle = -1
    if error is not None:
        raise error


class MemSlice(Object):
    """A slice of a MemFile, for iteration over delimited lines / records."""
    data: pointer
    size: nint


def _n_slice_bytes(ms: MemSlice) -> bytes:
    return _ctypes.string_at(ms.data._n_addr, int(ms.size)) if int(ms.size) > 0 else b""


def _memslice_eq(x: MemSlice, y: MemSlice) -> bool:
    """Nim: `==` of two MemSlices — the same size and bytes."""
    return int(x.size) == int(y.size) and _n_slice_bytes(x) == _n_slice_bytes(y)


def _memslice_str(ms: MemSlice) -> str:
    """Nim: `$` of a MemSlice — a string copy of its bytes."""
    return str(string(_n_slice_bytes(ms)))


MemSlice.__eq__ = _memslice_eq
MemSlice.__hash__ = None
MemSlice.__str__ = _memslice_str


def memSlices(mfile: MemFile, delim: char = char("\n"), eat: char = char("\r")):
    """Nim: memSlices — the slices between `delim`s (not included); a trailing `eat` char is trimmed."""
    delim_b, eat_b = ord(str(delim)), ord(str(eat))
    base = mfile.mem._n_addr if mfile.mem is not None else 0
    data = base
    remaining = int(mfile.size)
    while remaining > 0:
        ending = _libc.memchr(data, delim_b, remaining)
        if not ending:  # unterminated final slice
            yield MemSlice(data=pointer(data), size=remaining)
            break
        size = ending - data
        if eat_b != 0 and size > 0 and _ctypes.string_at(data + size - 1, 1)[0] == eat_b:
            size -= 1
        yield MemSlice(data=pointer(data), size=size)
        data = ending + 1
        remaining = int(mfile.size) - (data - base)


@dispatch
def lines(mfile: MemFile, buf: string, delim: char = char("\n"), eat: char = char("\r")):
    """Nim: lines(mfile, buf) — each line copied into `buf` (yields buf)."""
    for ms in memSlices(mfile, delim, eat):
        buf.setLen(0)
        buf.add(string(_n_slice_bytes(ms)))
        yield buf


@dispatch
def lines(mfile: MemFile, delim: char = char("\n"), eat: char = char("\r")):
    """Nim: lines(mfile) — each line as a new string."""
    for ms in memSlices(mfile, delim, eat):
        yield string(_n_slice_bytes(ms))
