"""Nim std/paths — Path type with `/` operator for joining, backed by nimic string."""
from __future__ import annotations
import os.path as path
from ..ntypes import string

class Path(string):
    def __init__(self, x: string | str = ""):
        super().__init__(str(x))

    # func `/`(head, tail: Path): Path {.inline, ....}
    def __truediv__(self, tail: string | Path | str) -> Path:
        return Path(path.join(str(self), str(tail)))

    def __fspath__(self) -> str:
        return str(self.data)

    def __str__(self) -> str:
        return str(self.data)