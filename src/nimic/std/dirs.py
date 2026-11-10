"""Nim std/dirs — directories by Path: createDir, removeDir, walkDir; re-exports PathComponent (Nim 2's and nimony's
std/dirs both have these). Under nimony (`defined("nimony")`) also tryCreateFinalDir, tryRemoveFinalDir (ErrorCode
results) and the re-exports of paths' Path, path and files' removeFile, tryRemoveFile."""
from __future__ import annotations
import os as _os
import shutil as _shutil
from nimic.ntypes import comptime, defined
from nimic.std.paths import Path
from nimic.std.os import PathComponent
from nimic.ntypesystem import _n_os_arg

_reexports = ('PathComponent',)  # Nim: export PathComponent

__all__ = [  # the module's own names and its stated re-exports (N92)
    'createDir', 'removeDir', 'walkDir'
] + list(_reexports)


class _NDirEntry(tuple):
    """walkDir's `tuple[kind: PathComponent, path: Path]`."""
    def __new__(cls, kind: PathComponent, path: Path):
        return super().__new__(cls, (kind, path))

    @property
    def kind(self) -> PathComponent:
        return self[0]

    @property
    def path(self) -> Path:
        return self[1]


def walkDir(dir: Path, relative: bool = False, checkDir: bool = False, skipSpecial: bool = False):
    """Nim (nimony): iterator walkDir(dir, relative, checkDir, skipSpecial) — the entries of `dir` as
    `(kind, path)`, `.` and `..` skipped, the path `dir / name` (`name` with `relative`); a symlink is
    pcLinkToDir / pcLinkToFile by its target; a FIFO, socket or device is pcFile, skipped with `skipSpecial`.
    A directory that can't be opened yields nothing, or raises with `checkDir`."""
    try:
        entries = list(_os.scandir(_n_os_arg(dir)))
    except OSError:
        if checkDir:
            raise
        return
    for entry in entries:
        if entry.is_symlink():
            kind = PathComponent.pcLinkToDir if entry.is_dir() else PathComponent.pcLinkToFile
        elif entry.is_dir(follow_symlinks=False):
            kind = PathComponent.pcDir
        else:
            if skipSpecial and not entry.is_file(follow_symlinks=False):
                continue
            kind = PathComponent.pcFile
        name = Path(entry.name)
        yield _NDirEntry(kind, name if relative else Path(dir) / name)


def createDir(dir: Path) -> None:
    """Nim: createDir(dir) — creates `dir` and its missing parents; an existing directory is fine."""
    _os.makedirs(_n_os_arg(dir), exist_ok=True)


def removeDir(dir: Path, checkDir: bool = False) -> None:
    """Nim: removeDir(dir, checkDir = false) — removes `dir` recursively (symlinks as links); a missing `dir`
    raises only with `checkDir`."""
    path = _n_os_arg(dir)
    if not _os.path.lexists(path):
        if checkDir:
            raise OSError(f"directory not found: {path}")
        return
    _shutil.rmtree(path)


if comptime(defined("nimony")):  # nimony's std/dirs
    from nimic.std.paths import path
    from nimic.std.files import removeFile, tryRemoveFile
    from nimic.std.private.errorcodes import ErrorCode, posixToErrorCode

    # Nim: export paths.Path, paths.path; export files.removeFile, files.tryRemoveFile
    _reexports += ('Path', 'path', 'removeFile', 'tryRemoveFile')
    __all__ += ['tryCreateFinalDir', 'tryRemoveFinalDir', 'Path', 'path', 'removeFile', 'tryRemoveFile']

    def _n_error_code(e: OSError) -> ErrorCode:
        return posixToErrorCode(e.errno) if e.errno else ErrorCode.Failure

    def tryCreateFinalDir(dir: Path) -> ErrorCode:
        """Nim (nimony): tryCreateFinalDir(dir) — creates the single directory `dir`, not its parents; the OS's
        error as an ErrorCode (NameExists when it exists), Success when created."""
        try:
            _os.mkdir(_n_os_arg(dir), 0o777)
        except OSError as e:
            return _n_error_code(e)
        return ErrorCode.Success

    def tryRemoveFinalDir(dir: Path) -> ErrorCode:
        """Nim (nimony): tryRemoveFinalDir(dir) — removes the single directory `dir` if it is empty; the OS's
        error as an ErrorCode, Success when removed."""
        try:
            _os.rmdir(_n_os_arg(dir))
        except OSError as e:
            return _n_error_code(e)
        return ErrorCode.Success
