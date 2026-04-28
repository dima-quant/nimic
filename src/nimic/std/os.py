"""Nim system/io and os — file mode constants and OS utilities."""
from __future__ import annotations
import os as _os
from sys import stdout, stderr
import sys
from io import TextIOWrapper
from enum import Enum

from nimic.std.syncio import read_file, read_file_bytes, write_buffer, set_file_pos

    # "r", "rb":
fmRead = "r"
    # "w", "wb":
fmWrite = "w"
    # "a", "ab":
fmAppend = "a"
    # "r+", "rb+":
fmReadWriteExisting = "r+"
    # "w+", "wb+":
fmReadWrite = "w+"

stderr.flush_file = stderr.flush
stdout.flush_file = stdout.flush

def create_dir(dir: str) -> None:
    """Create directory and parents if needed (Nim: os.createDir)."""
    _os.makedirs(dir, exist_ok=True)


class PathComponent(Enum):
    pcFile = "pcFile"
    pcDir = "pcDir"
    pcLinkToFile = "pcLinkToFile"
    pcLinkToDir = "pcLinkToDir"

pcFile = PathComponent.pcFile
pcDir = PathComponent.pcDir


class _WalkEntry:
    __slots__ = ('kind', 'path')
    def __init__(self, kind, path):
        self.kind = kind
        self.path = path


def walk_dir(path: str):
    """Iterate over directory entries (Nim: os.walkDir)."""
    for entry in _os.scandir(path):
        if entry.is_file():
            yield _WalkEntry(pcFile, entry.path)
        elif entry.is_dir():
            yield _WalkEntry(pcDir, entry.path)


def extract_filename(path: str) -> str:
    """Extract filename from path (Nim: os.extractFilename)."""
    return _os.path.basename(path)


def param_count() -> int:
    """Number of command-line arguments (Nim: os.paramCount)."""
    return len(sys.argv) - 1


def param_str(i: int) -> str:
    """Get i-th command-line argument (Nim: os.paramStr)."""
    return sys.argv[i]


def get_app_filename() -> str:
    """Get the application filename (Nim: os.getAppFilename)."""
    return sys.argv[0]


def open(path: str, mode: str = "r"):
    """Nim-style open — returns a File wrapper.

    Nim's File is always binary, so write/append modes are forced to
    binary (\"wb\", \"ab\", \"r+b\", \"w+b\") to match Nim semantics.
    Read mode keeps text unless explicitly requested as binary.
    """
    from nimic.ntypes import File
    # Nim files are binary for write/append modes
    _binary_map = {"w": "wb", "a": "ab", "r+": "r+b", "w+": "w+b"}
    actual_mode = _binary_map.get(mode, mode)
    handle = __builtins__["open"](path, actual_mode) if isinstance(__builtins__, dict) else __builtins__.open(path, actual_mode)
    return File(handle)
