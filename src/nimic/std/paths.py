"""Nim std/paths — Path type with `/` operator for joining, backed by nimic string."""
from __future__ import annotations
import os.path as path
from ..ntypes import string

class Path(string):
    def __init__(self: Path, x: string):
        self = x
    # func `/`(head, tail: Path): Path {.inline, ....}
    def __truediv__(self: Path, tail: string) -> Path:
        return path.join(self, tail)
    
    def __str__(self: Path) -> string:
        return self