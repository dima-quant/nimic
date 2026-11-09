"""Nim std/paths — Path type with `/` operator for joining, backed by nimic string."""
from __future__ import annotations
from ..ntypes import string
from ..ntypesystem import _n_join_path

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'Path'
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