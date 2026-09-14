"""
ncompiler/pathutils.py — Strict path types
Converted from compiler/pathutils.nim
"""
from __future__ import annotations
import os

class AbsoluteFile(str):
    """A distinct string type for absolute file paths."""
    def isEmpty(self) -> bool:
        return len(self) == 0
    def extractFilename(self) -> str:
        return os.path.basename(self)
    @property
    def string(self) -> str:
        return str(self)

class AbsoluteDir(str):
    def isEmpty(self) -> bool:
        return len(self) == 0
    @property
    def string(self) -> str:
        return str(self)
    def __truediv__(self, other) -> 'AbsoluteFile | AbsoluteDir':
        if isinstance(other, RelativeFile):
            return AbsoluteFile(os.path.join(str(self), str(other)))
        elif isinstance(other, RelativeDir):
            return AbsoluteDir(os.path.join(str(self), str(other)))
        return AbsoluteFile(os.path.join(str(self), str(other)))

class RelativeFile(str):
    def isEmpty(self) -> bool:
        return len(self) == 0
    @property
    def string(self) -> str:
        return str(self)
    def changeFileExt(self, ext: str) -> 'RelativeFile':
        base, _ = os.path.splitext(str(self))
        return RelativeFile(base + ext)

class RelativeDir(str):
    def isEmpty(self) -> bool:
        return len(self) == 0
    @property
    def string(self) -> str:
        return str(self)

def relativeTo(fullpath: AbsoluteFile, base: AbsoluteDir) -> RelativeFile:
    return RelativeFile(os.path.relpath(str(fullpath), str(base)))

def toAbsolute(file: str, base: AbsoluteDir) -> AbsoluteFile:
    if os.path.isabs(file):
        return AbsoluteFile(file)
    return AbsoluteFile(os.path.join(str(base), file))

def canonicalImportAux(conf, absPath: AbsoluteFile) -> str:
    return str(absPath)
