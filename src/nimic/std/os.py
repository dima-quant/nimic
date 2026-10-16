"""Nim system/io and os — file mode constants and OS utilities."""
from __future__ import annotations
import glob as _glob
import os as _os
import pathlib as _pathlib
import shlex as _shlex
import shutil as _shutil
from sys import stdout, stderr
import sys
from io import TextIOWrapper
from enum import Enum
from nimic.ntypes import char, string, dispatch, defined
from nimic.ntypesystem import _n_os_arg, _n_os_result

from nimic.std.syncio import read_file, read_file_bytes, write_buffer, set_file_pos, open

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
    _os.makedirs(_n_os_arg(dir), exist_ok=True)


class PathComponent(Enum):
    pcFile = "pcFile"
    pcLinkToFile = "pcLinkToFile"
    pcDir = "pcDir"
    pcLinkToDir = "pcLinkToDir"

pcFile = PathComponent.pcFile
pcLinkToFile = PathComponent.pcLinkToFile
pcDir = PathComponent.pcDir
pcLinkToDir = PathComponent.pcLinkToDir


class _WalkEntry(tuple):
    def __new__(cls, kind, path):
        return super().__new__(cls, (kind, path))
    @property
    def kind(self):
        return self[0]
    @property
    def path(self):
        return self[1]


def walk_dir(path: string | str, relative: bool = False, check_dir: bool = False):
    """Iterate over directory entries (Nim: os.walkDir)."""
    try:
        for entry in _os.scandir(_n_os_arg(path)):
            p = _n_os_result(entry.name if relative else entry.path)
            if entry.is_symlink():
                k = pcLinkToDir if entry.is_dir() else pcLinkToFile
            elif entry.is_dir():
                k = pcDir
            else:
                k = pcFile
            yield _WalkEntry(k, p)
    except OSError:
        pass

walkDir = walk_dir



def extract_filename(path: str | string) -> string:
    """Extract filename from path (Nim: os.extractFilename)."""
    return string(_os.path.basename(str(path)))

def expandFilename(path: string) -> string:
    return _n_os_result(_os.path.abspath(_n_os_arg(path)))



def param_count() -> int:
    """Number of command-line arguments (Nim: os.paramCount)."""
    return len(sys.argv) - 1


def param_str(i: int) -> string:
    """Get i-th command-line argument (Nim: os.paramStr)."""
    return _n_os_result(sys.argv[i])


if _os.name == 'nt':
    DirSep = char('\\')
    AltSep = char('/')
else:
    DirSep = char('/')
    AltSep = char('\\')

def getCurrentDir() -> string:
    """Get the current directory (Nim: os.getCurrentDir)."""
    return _n_os_result(_os.getcwd())


def get_app_filename() -> string:
    """Get the application filename (Nim: os.getAppFilename)."""
    return _n_os_result(sys.argv[0])




import os.path
import shutil

@dispatch
def isAbsolute(path: string) -> bool:
    return os.path.isabs(str(path))

class _SplitFileTuple(tuple):
    @property
    def dir(self) -> string:
        return self[0]
    @property
    def name(self) -> string:
        return self[1]
    @property
    def ext(self) -> string:
        return self[2]

@dispatch
def splitFile(path: string) -> _SplitFileTuple:
    d, f = os.path.split(str(path))
    n, e = os.path.splitext(f)
    return _SplitFileTuple((string(d), string(n), string(e)))

split_file = splitFile

def relativePath(path: string, base: string = string("."), sep: char = DirSep) -> string:
    res = os.path.relpath(_n_os_arg(path), _n_os_arg(base))  # resolves against the cwd
    if str(sep) != _os.sep:
        res = res.replace(_os.sep, str(sep))
    return _n_os_result(res)

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
    if os.path.exists(_n_os_arg(file)):
        _os.remove(_n_os_arg(file))

@dispatch
def fileExists(file: string) -> bool:
    return os.path.isfile(_n_os_arg(file))

@dispatch
def dirExists(dir: string) -> bool:
    return os.path.isdir(_n_os_arg(dir))

@dispatch
def createDir(dir: string) -> None:
    _os.makedirs(_n_os_arg(dir), exist_ok=True)

create_dir = createDir

@dispatch
def removeDir(dir: string) -> None:
    if _os.path.exists(_n_os_arg(dir)):
        shutil.rmtree(_n_os_arg(dir))

remove_dir = removeDir

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
def lastPathPart(path: string) -> string:
    s = str(path).rstrip('/\\')
    return string(os.path.basename(s))

@dispatch
def quoteShell(path: string) -> string:
    return string(_shlex.quote(str(path)))

@dispatch
def copyFile(source: string, dest: string) -> None:
    shutil.copy2(_n_os_arg(source), _n_os_arg(dest))

@dispatch
def execShellCmd(cmd: string) -> int:
    return _os.system(_n_os_arg(cmd))

@dispatch
def findExe(exe: string) -> string:
    res = shutil.which(_n_os_arg(exe))
    return _n_os_result(res) if res is not None else string("")

find_exe = findExe

@dispatch
def parentDir(path: string) -> string:
    s = str(path)
    if not s or s == "/" or s == "\\":
        return string("")
    res = _os.path.dirname(s)
    if res == s:
        return string("")
    return string(res)

parent_dir = parentDir

def walkFiles(pattern: string | str):
    for p in _glob.iglob(_n_os_arg(pattern)):
        if _os.path.isfile(p):
            yield _n_os_result(p)

walk_files = walkFiles

def getCurrentCompilerExe() -> string:
    """Nim: getCurrentCompilerExe() — the path of the Nim compiler. In a compiled program this is the
    compiler that built it ({.compileTime.}), so Python returns the `nim` of the emulated build:
    NIMIC_NIM if set, else `nim` on PATH (symlinks resolved, as Nim reports it)."""
    exe = _os.environ.get("NIMIC_NIM") or _shutil.which("nim") or ""
    return _n_os_result(_os.path.realpath(exe) if exe else "")

get_current_compiler_exe = getCurrentCompilerExe

# Nim (std/private/osseps): true if the file system is case sensitive; used by cmpPaths
FileSystemCaseSensitive = not (defined("macos") or defined("macosx") or defined("windows") or defined("OS2")
                               or defined("DOS") or defined("vxworks") or defined("PalmOS") or defined("MorphOS"))

@dispatch
def isRelativeTo(path: string, base: string) -> bool:
    return _pathlib.PurePath(str(path)).is_relative_to(str(base))

is_relative_to = isRelativeTo

@dispatch
def get_env(var: string, default: string = string("")) -> string:
    val = _os.environ.get(_n_os_arg(var))
    if val is None:
        return default
    return _n_os_result(val)

getEnv = get_env
last_path_part = lastPathPart

@dispatch
def unix_to_native_path(path: string | str, drive: string | str = string("")) -> string:
    p = str(path)
    if sys.platform == "win32":
        p = p.replace("/", "\\")
        if str(drive):
            p = str(drive) + ":" + p
    return string(p)

unixToNativePath = unix_to_native_path

@dispatch
def expand_tilde(path: string | str) -> string:
    return _n_os_result(_os.path.expanduser(_n_os_arg(path)))  # reads $HOME

expandTilde = expand_tilde