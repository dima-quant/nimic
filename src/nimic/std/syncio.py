"""Nim std/syncio — file I/O operations.

Provides Python equivalents of Nim's File I/O: read_file, write_file,
write_buffer, set_file_pos, open (with Nim file modes from std/os).
"""
from __future__ import annotations
import os



def read_file(path: str) -> str:
    """Read entire file contents as a string."""
    from nimic.ntypesystem import string
    with open(path, 'rb') as f:
        return string(f.read())


def read_file_bytes(path: str) -> bytes:
    """Read entire file contents as bytes."""
    with open(path, 'rb') as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    """Write string content to a file."""
    with open(path, 'w') as f:
        f.write(content)


def write_buffer(f, buffer, size: int) -> int:
    """Write `size` bytes from `buffer` to file `f`.
    Returns number of bytes written."""
    if hasattr(buffer, '_n_addr'):
        import ctypes
        addr = buffer._n_addr
        data = bytes((ctypes.c_char * int(size)).from_address(addr))
    elif hasattr(buffer, '_n_view') or hasattr(buffer, 'contents'):
        import ctypes
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


def set_file_pos(f, pos: int) -> None:
    """Seek to absolute position in file."""
    f.seek(pos)
