"""Nim system/io and os — file mode constants and OS utilities."""
from __future__ import annotations
import os as _os
from sys import stdout, stderr
import sys
from io import TextIOWrapper
from enum import Enum
from nimic.ntypes import char, string, dispatch

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
    _os.makedirs(dir, exist_ok=True)


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
        for entry in _os.scandir(str(path)):
            p = string(entry.name) if relative else string(entry.path)
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

create_dir = createDir

@dispatch
def removeDir(dir: string) -> None:
    if _os.path.exists(str(dir)):
        shutil.rmtree(str(dir))

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
    import shlex
    return string(shlex.quote(str(path)))

@dispatch
def copyFile(source: string, dest: string) -> None:
    shutil.copy2(str(source), str(dest))

@dispatch
def execShellCmd(cmd: string) -> int:
    return _os.system(str(cmd))

@dispatch
def findExe(exe: string) -> string:
    res = shutil.which(str(exe))
    return string(res) if res is not None else string("")

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
    import glob
    for p in glob.iglob(str(pattern)):
        if _os.path.isfile(p):
            yield string(p)

walk_files = walkFiles

def getCurrentCompilerExe() -> string:
    # mock
    return string(sys.executable)

get_current_compiler_exe = getCurrentCompilerExe

@dispatch
def isRelativeTo(path: string, base: string) -> bool:
    try:
        import pathlib
        return pathlib.Path(str(path)).is_relative_to(str(base))
    except (ValueError, Exception):
        return False

is_relative_to = isRelativeTo

@dispatch
def get_env(var: string, default: string = string("")) -> string:
    val = _os.environ.get(str(var))
    if val is None:
        return default
    return string(val)

getEnv = get_env
last_path_part = lastPathPart

@dispatch
def unix_to_native_path(path: string | str, drive: string | str = string("")) -> string:
    import sys
    p = str(path)
    if sys.platform == "win32":
        p = p.replace("/", "\\")
        if str(drive):
            p = str(drive) + ":" + p
    return string(p)

unixToNativePath = unix_to_native_path

@dispatch
def expand_tilde(path: string | str) -> string:
    return string(_os.path.expanduser(str(path)))

expandTilde = expand_tilde