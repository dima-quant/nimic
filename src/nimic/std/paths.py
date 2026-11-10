"""Nim std/paths — Path type with `/` operator for joining, backed by nimic string."""
from __future__ import annotations
from ..ntypes import string, comptime, defined
from ..ntypesystem import _n_join_path
from .os import changeFileExt as _os_changeFileExt

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'changeFileExt', 'Path'
]

class Path(string):
    def __init__(self, x: string | str = ""):
        super().__init__(str(x))

    # func `/`(head, tail: Path): Path {.inline, ....}
    def __truediv__(self, tail: string | Path | str) -> Path:
        """Nim's paths `/`: joinPath, normalized."""
        return Path(_n_join_path(str(self), str(tail)))

    def __str__(self) -> str:
        return str(self.data)



def changeFileExt(filename: Path, ext: string) -> Path:
    """Nim (nimony's std/paths): changeFileExt(filename, ext) — os' changeFileExt on a Path."""
    return Path(_os_changeFileExt(string(filename), ext))


if comptime(defined("nimony")):  # nimony's std/paths (Nim 2's has no `path`: lengc's compat2 defines one)
    __all__ += ['path']

    def path(s: string) -> Path:
        """Nim (nimony): path(s) — the Path of the raw string `s`."""
        return Path(s)
