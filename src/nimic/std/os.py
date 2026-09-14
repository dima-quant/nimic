"""Nim system/io and os — file mode constants and OS utilities."""
from __future__ import annotations
import os as _os
from sys import stdout, stderr
import sys
from io import TextIOWrapper
from enum import Enum
from nimic.ntypes import char, string, dispatch

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

def expandFilename(path: string) -> string:
    return string(_os.path.abspath(str(path)))



def param_count() -> int:
    """Number of command-line arguments (Nim: os.paramCount)."""
    return len(sys.argv) - 1


def param_str(i: int) -> str:
    """Get i-th command-line argument (Nim: os.paramStr)."""
    return sys.argv[i]


if _os.name == 'nt':
    DirSep = char('\\')
    AltSep = char('/')
else:
    DirSep = char('/')
    AltSep = char('\\')

def getCurrentDir() -> string:
    """Get the current directory (Nim: os.getCurrentDir)."""
    return string(_os.getcwd())


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

import os.path
import shutil

@dispatch
def isAbsolute(path: string) -> bool:
    return os.path.isabs(str(path))

@dispatch
def splitFile(path: string) -> tuple[string, string, string]:
    d, f = os.path.split(str(path))
    n, e = os.path.splitext(f)
    return string(d), string(n), string(e)

def relativePath(path: string, base: string = string("."), sep: char = DirSep) -> string:
    res = os.path.relpath(str(path), str(base))
    if str(sep) != _os.sep:
        res = res.replace(_os.sep, str(sep))
    return string(res)

@dispatch
def changeFileExt(filename: string, ext: string) -> string:
    n, _ = os.path.splitext(str(filename))
    ext_str = str(ext)
    if not ext_str.startswith('.'):
        ext_str = '.' + ext_str
    return string(n + ext_str)

@dispatch
def addFileExt(filename: string, ext: string) -> string:
    _, e = os.path.splitext(str(filename))
    if e: return string(filename)
    ext_str = str(ext)
    if not ext_str.startswith('.'):
        ext_str = '.' + ext_str
    return string(str(filename) + ext_str)

@dispatch
def removeFile(file: string) -> None:
    if os.path.exists(str(file)):
        _os.remove(str(file))

@dispatch
def fileExists(file: string) -> bool:
    return os.path.isfile(str(file))

@dispatch
def dirExists(dir: string) -> bool:
    return os.path.isdir(str(dir))

@dispatch
def createDir(dir: string) -> None:
    _os.makedirs(str(dir), exist_ok=True)

@dispatch
def cmpPaths(pathA: string, pathB: string) -> int:
    a = os.path.normcase(os.path.normpath(str(pathA)))
    b = os.path.normcase(os.path.normpath(str(pathB)))
    if a < b: return -1
    elif a > b: return 1
    else: return 0

@dispatch
def extractFilename(path: string) -> string:
    return string(os.path.basename(str(path)))

@dispatch
def quoteShell(path: string) -> string:
    import shlex
    return string(shlex.quote(str(path)))

@dispatch
def copyFile(source: string, dest: string) -> None:
    shutil.copy2(str(source), str(dest))

@dispatch
def execShellCmd(cmd: string) -> int:
    return _os.system(str(cmd))


def getCurrentCompilerExe() -> string:
    # mock
    return string(sys.executable)