"""Nim std/syncio — file I/O operations.

Provides Python equivalents of Nim's File I/O: read_file, write_file,
write_buffer, set_file_pos, open (with Nim file modes from std/os).
"""
from __future__ import annotations
from enum import Enum
import builtins
import ctypes
import os
from enum import auto
from nimic.ntypes import File, NIntEnum, ufcs, int64
from nimic.ntypesystem import string, _n_encode_str, _n_decode_bytes, _n_os_arg



class FileMode(str, Enum):
    fmRead = "r"
    fmWrite = "w"
    fmAppend = "a"
    fmReadWrite = "w+"
    fmReadWriteExisting = "r+"

fmRead = FileMode.fmRead
fmWrite = FileMode.fmWrite
fmAppend = FileMode.fmAppend
fmReadWrite = FileMode.fmReadWrite
fmReadWriteExisting = FileMode.fmReadWriteExisting


class FileSeekPos(NIntEnum):
    """Nim: FileSeekPos, what setFilePos's position is relative to (the ordinals are Python's whence)."""
    fspSet = auto()  # the start of the file
    fspCur = auto()  # the current position
    fspEnd = auto()  # the end of the file

fspSet = FileSeekPos.fspSet
fspCur = FileSeekPos.fspCur
fspEnd = FileSeekPos.fspEnd

def open(*args):
    """Nim-style open — supports both open(path, mode) and open(f, path, mode)."""
    _binary_map = {"w": "wb", "a": "ab", "r+": "r+b", "w+": "w+b", "r": "rb"}
    if len(args) >= 2 and isinstance(args[0], File):
        f = args[0]
        filename = _n_os_arg(args[1])
        raw_mode = args[2] if len(args) > 2 else "r"
        mode = str(raw_mode.value if hasattr(raw_mode, "value") else raw_mode)
        actual_mode = _binary_map.get(mode, mode)
        try:
            handle = builtins.open(filename, actual_mode)
            f._n_handle = handle
            f._n_id = id(f)
            File._n_files[f._n_id] = f
            return True
        except Exception:
            return False
    elif len(args) >= 1:
        path = _n_os_arg(args[0])
        raw_mode = args[1] if len(args) > 1 else "r"
        mode = str(raw_mode.value if hasattr(raw_mode, "value") else raw_mode)
        actual_mode = _binary_map.get(mode, mode)
        handle = builtins.open(path, actual_mode)
        return File(handle)


def read_file(path: str | string) -> string:
    """Read entire file contents as a string."""
    with builtins.open(_n_os_arg(path), 'rb') as f:
        return string(f.read())


def lines(filename: str | string):
    """Nim: lines — iterates over lines in filename (raw bytes, no decoding)."""
    with builtins.open(_n_os_arg(filename), 'rb') as f:
        for line in f:
            yield string(line.rstrip(b'\r\n'))



def read_file_bytes(path: str | string) -> bytes:
    """Read entire file contents as bytes."""
    with builtins.open(_n_os_arg(path), 'rb') as f:
        return f.read()


def write_file(path: str | string, content: str | string) -> None:
    """Write string content to a file."""
    with builtins.open(_n_os_arg(path), 'wb') as f:
        f.write(_n_encode_str(content))


readFile = read_file
writeFile = write_file


@ufcs(File, aliases=("writeBuffer",))
def write_buffer(f, buffer, size: int) -> int:
    """Write `size` bytes from `buffer` to file `f`.
    Returns number of bytes written."""
    if hasattr(buffer, '_n_addr'):
        addr = buffer._n_addr
        data = bytes((ctypes.c_char * int(size)).from_address(addr))
    elif hasattr(buffer, '_n_view') or hasattr(buffer, 'contents'):
        v = getattr(buffer, 'contents', buffer)
        v = getattr(v, '_n_view', v)
        if isinstance(v, int):
            addr = v
        elif hasattr(v, 'value') and isinstance(v.value, int):
            addr = v.value
        else:
            addr = ctypes.addressof(v)
        data = bytes((ctypes.c_char * int(size)).from_address(addr))
    elif isinstance(buffer, (bytes, bytearray)):
        data = buffer[:size]
    else:
        data = bytes(buffer)[:size]
    return f.write(data)


@ufcs(File, aliases=("readBuffer",))
def read_buffer(f, buffer, size: int) -> int:
    """Read up to `size` bytes from file `f` into `buffer`.
    Returns number of bytes read."""
    data = f.read(int(size))
    if not data:
        return 0
    if isinstance(data, str):
        data = _n_encode_str(data)
    n = len(data)
    if hasattr(buffer, '_n_addr'):
        addr = buffer._n_addr
        ctypes.memmove(addr, data, n)
    elif hasattr(buffer, '_n_view') or hasattr(buffer, 'contents'):
        v = getattr(buffer, 'contents', buffer)
        v = getattr(v, '_n_view', v)
        if isinstance(v, int):
            addr = v
        elif hasattr(v, 'value') and isinstance(v.value, int):
            addr = v.value
        else:
            addr = ctypes.addressof(v)
        ctypes.memmove(addr, data, n)
    elif isinstance(buffer, int):
        ctypes.memmove(buffer, data, n)
    elif isinstance(buffer, (bytearray, list)):
        for i in range(n):
            buffer[i] = data[i]
    return n

readBuffer = read_buffer
writeBuffer = write_buffer


@ufcs(File, aliases=("setFilePos",))
def set_file_pos(f, pos: int, relativeTo: FileSeekPos = FileSeekPos.fspSet) -> None:
    """Nim: setFilePos — seek to `pos`, relative to the start (fspSet), the current position or the end."""
    f.seek(int(pos), int(relativeTo))


setFilePos = set_file_pos


@ufcs(File, aliases=("getFilePos",))
def get_file_pos(f) -> int64:
    """Nim: getFilePos — the current position in the file."""
    return int64(getattr(f, '_n_handle', f).tell())


getFilePos = get_file_pos


def close(f: File) -> None:
    """Close file handle."""
    f_handle = getattr(f, '_n_handle', f)
    if hasattr(f_handle, 'close'):
        f_handle.close()


import sys
stdin = sys.stdin
stdout = sys.stdout
stderr = sys.stderr


def _n_write_view(f_handle, s: str) -> None:
    """Write byte view `s` to a binary handle as its bytes, or to a text stream
    as-is (nimic reconfigures stdio to Latin-1, so the bytes come out unchanged)."""
    if 'b' in getattr(f_handle, 'mode', ''):
        f_handle.write(_n_encode_str(s))
    else:
        try:
            f_handle.write(s)
        except TypeError:  # binary handle without a `mode` attribute
            f_handle.write(_n_encode_str(s))


def write(f, data) -> None:
    """Nim: write(f, data) — write string or char to file f."""
    f_handle = getattr(f, '_n_handle', f)
    s = data.data if hasattr(data, 'data') else str(data)
    _n_write_view(f_handle, s)


def read_line(f, line=None):
    """Nim: readLine(f, line: var string): bool or readLine(f): string."""
    f_handle = getattr(f, '_n_handle', f)
    raw = f_handle.readline()
    if not raw:
        if line is not None:
            return False
        return string("")
    if isinstance(raw, bytes):
        raw = _n_decode_bytes(raw)
    if raw.endswith('\r\n'):
        raw = raw[:-2]
    elif raw.endswith('\n') or raw.endswith('\r'):
        raw = raw[:-1]
    if line is not None:
        if hasattr(line, 'data'):
            line.data = raw
        return True
    return string(raw)

readLine = read_line


def write_line(f, *args) -> None:
    """Nim: writeLine(f, *args) — write strings followed by newline."""
    f_handle = getattr(f, '_n_handle', f)
    s = "".join(a.data if hasattr(a, 'data') else str(a) for a in args) + "\n"
    _n_write_view(f_handle, s)

writeLine = write_line


def flush_file(f) -> None:
    """Nim: flushFile(f) — flush file buffer."""
    f_handle = getattr(f, '_n_handle', f)
    if hasattr(f_handle, 'flush'):
        f_handle.flush()

flushFile = flush_file



