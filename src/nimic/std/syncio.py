"""Nim std/syncio — file I/O operations.

Provides Python equivalents of Nim's File I/O: read_file, write_file,
write_buffer, set_file_pos, open (with Nim file modes from std/os).
"""
from __future__ import annotations
from enum import Enum
import ctypes
import os
from nimic.ntypes import File



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

def open(*args):
    """Nim-style open — supports both open(path, mode) and open(f, path, mode)."""
    from nimic.ntypes import File
    import builtins
    _binary_map = {"w": "wb", "a": "ab", "r+": "r+b", "w+": "w+b", "r": "rb"}
    if len(args) >= 2 and isinstance(args[0], File):
        f = args[0]
        filename = str(args[1])
        raw_mode = args[2] if len(args) > 2 else "r"
        mode = str(raw_mode.value if hasattr(raw_mode, "value") else raw_mode)
        actual_mode = _binary_map.get(mode, mode)
        try:
            handle = builtins.open(filename, actual_mode)
            f._handle = handle
            f._id = id(f)
            File._registry[f._id] = f
            return True
        except Exception:
            return False
    elif len(args) >= 1:
        path = str(args[0])
        raw_mode = args[1] if len(args) > 1 else "r"
        mode = str(raw_mode.value if hasattr(raw_mode, "value") else raw_mode)
        actual_mode = _binary_map.get(mode, mode)
        handle = builtins.open(path, actual_mode)
        return File(handle)


def read_file(path: str | string) -> string:
    """Read entire file contents as a string."""
    from nimic.ntypesystem import string
    import builtins
    with builtins.open(str(path), 'r') as f:
        return string(f.read())


def lines(filename: str | string):
    """Nim: lines — iterates over lines in filename."""
    from nimic.ntypesystem import string
    import builtins
    with builtins.open(str(filename), 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            yield string(line.rstrip('\r\n'))



def read_file_bytes(path: str | string) -> bytes:
    """Read entire file contents as bytes."""
    with open(str(path), 'rb') as f:
        return f.read()


def write_file(path: str | string, content: str | string) -> None:
    """Write string content to a file."""
    with open(str(path), 'w') as f:
        f.write(str(content))


readFile = read_file
writeFile = write_file


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


def read_buffer(f, buffer, size: int) -> int:
    """Read up to `size` bytes from file `f` into `buffer`.
    Returns number of bytes read."""
    data = f.read(int(size))
    if not data:
        return 0
    if isinstance(data, str):
        data = data.encode('utf-8')
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


def set_file_pos(f, pos: int) -> None:
    """Seek to absolute position in file."""
    f.seek(pos)


def close(f) -> None:
    """Close file handle."""
    f_handle = getattr(f, '_handle', f)
    if hasattr(f_handle, 'close'):
        f_handle.close()


import sys
stdin = sys.stdin
stdout = sys.stdout
stderr = sys.stderr


def write(f, data) -> None:
    """Nim: write(f, data) — write string or char to file f."""
    f_handle = getattr(f, '_handle', f)
    s = data.data if hasattr(data, 'data') else str(data)
    if hasattr(f_handle, 'mode') and 'b' in getattr(f_handle, 'mode', ''):
        f_handle.write(s.encode('utf-8') if isinstance(s, str) else bytes(s))
    else:
        try:
            f_handle.write(s)
        except TypeError:
            f_handle.write(s.encode('utf-8'))


def read_line(f, line=None):
    """Nim: readLine(f, line: var string): bool or readLine(f): string."""
    from nimic.ntypesystem import string
    f_handle = getattr(f, '_handle', f)
    raw = f_handle.readline()
    if not raw:
        if line is not None:
            return False
        return string("")
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')
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
    f_handle = getattr(f, '_handle', f)
    s = "".join(a.data if hasattr(a, 'data') else str(a) for a in args) + "\n"
    if hasattr(f_handle, 'mode') and 'b' in getattr(f_handle, 'mode', ''):
        f_handle.write(s.encode('utf-8'))
    else:
        try:
            f_handle.write(s)
        except TypeError:
            f_handle.write(s.encode('utf-8'))

writeLine = write_line


def flush_file(f) -> None:
    """Nim: flushFile(f) — flush file buffer."""
    f_handle = getattr(f, '_handle', f)
    if hasattr(f_handle, 'flush'):
        f_handle.flush()

flushFile = flush_file



