# /// nimic
#
# ///
#
#
#           The Nim Compiler
#        (c) Copyright 2018 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.os import *
from nimic.std.pathnorm import *
from nimic.std.strutils import *

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.syncio import *
    from nimic.std.assertions import *

@distinct
class AbsoluteFile(string):
    def removeFile(self):
        """{.borrow.}"""
        removeFile(string(self))

    def extractFilename(self) -> string:
        """{.borrow.}"""
        return extractFilename(string(self))

    def fileExists(self) -> bool:
        """{.borrow.}"""
        return fileExists(string(self))

    def quoteShell(self) -> string:
        """{.borrow.}"""
        return quoteShell(string(self))

    def changeFileExt(self, ext: string) -> AbsoluteFile:
        """{.borrow.}"""
        return AbsoluteFile(changeFileExt(string(self), ext))

    def addFileExt(self, ext: string) -> AbsoluteFile:
        """{.borrow.}"""
        return AbsoluteFile(addFileExt(string(self), ext))

    def writeFile(self, content: string):
        """{.borrow.}"""
        writeFile(string(self), content)

@distinct
class AbsoluteDir(string):
    def dirExists(self) -> bool:
        """{.borrow.}"""
        return dirExists(string(self))

    def quoteShell(self) -> string:
        """{.borrow.}"""
        return quoteShell(string(self))

    def cmpPaths(self, y: AbsoluteDir) -> nint:
        """{.borrow.}"""
        return cmpPaths(string(self), string(y))

    def createDir(self):
        """{.borrow.}"""
        createDir(string(self))

    @dispatch
    def __truediv__(self: AbsoluteDir, f: RelativeFile) -> AbsoluteFile:
        with let:
            _base = postProcessBase(self)
        doAssert(not isAbsolute(string(f)), string(f))
        result = AbsoluteFile(newStringOfCap(len(string(_base)) + len(string(f))))
        with var:
            state = 0
        addNormalizePath(string(_base), string(result), state)
        addNormalizePath(string(f), string(result), state)
        return result

    @dispatch
    def __truediv__(self: AbsoluteDir, f: RelativeDir) -> AbsoluteDir:
        with let:
            _base = postProcessBase(self)
        doAssert(not isAbsolute(string(f)))
        result = AbsoluteDir(newStringOfCap(len(string(_base)) + len(string(f))))
        with var:
            state = 0
        addNormalizePath(string(_base), string(result), state)
        addNormalizePath(string(f), string(result), state)
        return result

@distinct
class RelativeFile(string):
    def changeFileExt(self, ext: string) -> RelativeFile:
        """{.borrow.}"""
        return RelativeFile(changeFileExt(string(self), ext))

    def addFileExt(self, ext: string) -> RelativeFile:
        """{.borrow.}"""
        return RelativeFile(addFileExt(string(self), ext))

@distinct
class RelativeDir(string): pass

type AnyPath = AbsoluteFile | AbsoluteDir | RelativeFile | RelativeDir

def isEmpty(x: AnyPath) -> bool:
    """{.inline.}"""
    return len(string(x)) == 0

def copyFile(source: AbsoluteFile, dest: AbsoluteFile):
    copyFile(string(source), string(dest))

class _SplitFileTuple(NTuple):
    dir: AbsoluteDir
    name: string
    ext: string

@dispatch
def splitFile(x: AbsoluteFile) -> _SplitFileTuple:
    with let:
        a, b, c = splitFile(string(x))
        result = (AbsoluteDir(a), b, c)
    return result

def toAbsoluteDir(path: string) -> AbsoluteDir:
    if isAbsolute(path):
        result = AbsoluteDir(path)
    else:
        result = AbsoluteDir(getCurrentDir() / path)
    return result

def __str__(x: AnyPath) -> string:
    return string(x)

if comptime(True):
    def eqImpl(x: string, y: string) -> bool:
        """{.inline.}"""
        result = cmpPaths(x, y) == 0
        return result

    def __eq__[T: AnyPath](x: T, y: T) -> bool:
        return eqImpl(string(x), string(y))

    @template
    def postProcessBase(base: AbsoluteDir) -> AbsoluteDir:
        if comptime(False):
            doAssert(isAbsolute(string(base)), string(base))
            return base
        else:
            if isEmpty(base):
                return AbsoluteDir(getCurrentDir())
            else:
                return base



    def relativeTo(fullPath: AbsoluteFile, baseFilename: AbsoluteDir, sep: char = DirSep) -> RelativeFile:
        with var:
            result = RelativeFile(relativePath(string(fullPath), string(baseFilename), sep))
        return result

    def toAbsolute(file: string, base: AbsoluteDir) -> AbsoluteFile:
        if isAbsolute(file):
            result = AbsoluteFile(file)
        else:
            result = base / RelativeFile(file)
        return result

def skipHomeDir(x: string) -> nint:
    with var:
        result = 0
    if comptime(defined("windows")):
        if continuesWith(x, string("Users/"), len(string("C:/"))):
            result = 3
        else:
            result = 0
    else:
        if startsWith(x, string("/home/")) or startsWith(x, string("/Users/")):
            result = 3
        elif startsWith(x, string("/mnt/")) and continuesWith(x, string("/Users/"), len(string("/mnt/c"))):
            result = 5
        else:
            result = 0
    return result

def relevantPart(s: string, afterSlashX: nint) -> string:
    with var:
        result = newStringOfCap(len(s) - 8)
        slashes = afterSlashX
    for i in range(len(s)):
        if slashes == 0:
            result += s[i]
        elif s[i] == ch('/'):
            slashes -= 1
    return result

@template
def canonSlashes(x: string) -> string:
    if comptime(defined("windows")):
        return x.replace(ch('\\'), ch('/'))
    else:
        return x

def customPathImpl(x: string) -> string:
    with var:
        result = string("")
    if not isAbsolute(x):
        result = customPathImpl(canonSlashes(getCurrentDir() / x))
    else:
        with let:
            slashes = skipHomeDir(x)
        if slashes > 0:
            result = string("//user/") + relevantPart(x, slashes)
        else:
            result = x
    return result

def customPath(x: string) -> string:
    return customPathImpl(canonSlashes(x))

if comptime(__name__ == "__main__"):
    doAssert(isEmpty(AbsoluteFile("")))
    doAssert(not isEmpty(AbsoluteFile("foo.txt")))

    abs_dir = toAbsoluteDir("foo/bar")
    doAssert(isAbsolute(string(abs_dir)))

    base = AbsoluteDir("/home/user")
    rel = RelativeFile("doc.txt")
    res = base / rel
    doAssert(string(res) == "/home/user/doc.txt" or string(res) == "\\home\\user\\doc.txt")

    d, n, e = splitFile(AbsoluteFile("/home/user/doc.txt"))
    doAssert(string(d) == "/home/user" or string(d) == "\\home\\user")
    doAssert(string(n) == "doc")
    doAssert(string(e) == ".txt")

    rel_path = relativeTo(AbsoluteFile("/home/user/doc.txt"), AbsoluteDir("/home/user"))
    doAssert(string(rel_path) == "doc.txt")

    f1 = AbsoluteFile("/home/user/doc.txt")
    f2 = f1.changeFileExt("md")
    doAssert(string(f2) == "/home/user/doc.md" or string(f2) == "\\home\\user\\doc.md")

    cp = customPath("/home/user/doc.txt")

    print("All pathutils tests passed.")
