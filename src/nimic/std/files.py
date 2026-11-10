"""Nim std/files — files by Path: removeFile (Nim 2's and nimony's); under nimony also tryRemoveFile (an ErrorCode)
and the re-exports of paths' Path, path."""
from __future__ import annotations
import os as _os
from nimic.ntypes import comptime, defined
from nimic.std.paths import Path
from nimic.ntypesystem import _n_os_arg

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'removeFile'
]


def removeFile(file: Path) -> None:
    """Nim: removeFile(file) — removes `file` (a symlink itself, never its target); a missing file is fine,
    another failure raises OSError."""
    try:
        _os.unlink(_n_os_arg(file))
    except FileNotFoundError:
        pass


if comptime(defined("nimony")):  # nimony's std/files
    from nimic.std.paths import path
    from nimic.std.private.errorcodes import ErrorCode, posixToErrorCode

    _reexports = ('Path', 'path')  # Nim: export paths.Path, paths.path
    __all__ += ['tryRemoveFile'] + list(_reexports)

    def tryRemoveFile(file: Path) -> ErrorCode:
        """Nim (nimony): tryRemoveFile(file) — removes `file` (a symlink itself, never its target); the OS's
        error as an ErrorCode, Success when removed (Nim 2's os.tryRemoveFile gives a bool)."""
        try:
            _os.unlink(_n_os_arg(file))
        except OSError as e:
            return posixToErrorCode(e.errno) if e.errno else ErrorCode.Failure
        return ErrorCode.Success
