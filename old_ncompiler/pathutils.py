#
#
#           The Nim Compiler
#        (c) Copyright 2018 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

## Path handling utilities for Nim. Strictly typed code in order
## to avoid the never ending time sink in getting path handling right.

# import std/[os, pathnorm, strutils]
from __future__ import annotations
from nkeywords import *

# when defined(nimPreviewSlimSystem):
#   import std/[syncio, assertions]

# type
#   AbsoluteFile* = distinct string
#   AbsoluteDir* = distinct string
#   RelativeFile* = distinct string
#   RelativeDir* = distinct string
#   AnyPath* = AbsoluteFile|AbsoluteDir|RelativeFile|RelativeDir

class AbsoluteFile(string):
    def removeFile(x: AbsoluteFile):
        """{.borrow.}"""
        removeFile(x)

    def extractFilename(x: AbsoluteFile) -> string:
        """{.borrow.}"""
        return extractFilename(x)
    
    def fileExists(x: AbsoluteFile) -> bool:
        """{.borrow.}"""
        return fileExists(x)
    
    def quoteShell(x: AbsoluteFile) -> string:
        """{.borrow.}"""
        return quoteShell(x)
    
    def splitFile(x: AbsoluteFile) -> splitFiletype:
        (a, b, c) = splitFile(x.string)
        result = splitFiletype(dir=AbsoluteDir(a), name=b, ext=c)
        return result

class RelativeFile(string):
    def addFileExt(x: RelativeFile, ext: string) -> RelativeFile:
        """{.borrow.}"""
        return addFileExt(x, ext)

class AbsoluteDir(string):

    def dirExists(x: AbsoluteDir) -> bool:
        """{.borrow.}"""
        return dirExists(x)
    
    def addFileExt(x: AbsoluteDir, ext: string) -> AbsoluteDir:
        """{.borrow.}"""
        return addFileExt(x, ext)
    
    def writeFile(x: AbsoluteDir, content: str) -> None:
        """{.borrow.}"""
        writeFile(x, content)
    
    def quoteShell(x: AbsoluteDir) -> string:
        """{.borrow.}"""
        return quoteShell(x)
    
    def cmpPaths(x: AbsoluteDir, y: AbsoluteDir) -> int:
        """{.borrow.}"""
        return cmpPaths(x, y)
    
    def createDir(x: AbsoluteDir):
        """{.borrow.}"""
        createDir(x)

    def changeFileExt(x: AbsoluteDir, ext: string) -> AbsoluteDir:
        """{.borrow.}"""
        return changeFileExt(x, ext)
    
class RelativeDir(string):
    def changeFileExt(x: RelativeFile, ext: string) -> RelativeFile:
        """{.borrow.}"""
        return changeFileExt(x, ext)

type AnyPath = AbsoluteFile|AbsoluteDir|RelativeFile|RelativeDir

# proc isEmpty*(x: AnyPath): bool {.inline.} = x.string.len == 0

def isEmpty(x: AnyPath) -> bool:
    """{.inline.}""" 
    return len(string(x)) == 0

# proc copyFile*(source, dest: AbsoluteFile) =
#   os.copyFile(source.string, dest.string)

def copyFile(source: AbsoluteFile, dest: AbsoluteFile):
  os_copyFile(string(source), string(dest))

# proc removeFile*(x: AbsoluteFile) {.borrow.}

# proc splitFile*(x: AbsoluteFile): tuple[dir: AbsoluteDir, name, ext: string] =
#   let (a, b, c) = splitFile(x.string)
#   result = (dir: AbsoluteDir(a), name: b, ext: c)


class splitFiletype(NamedTuple):
    dir: AbsoluteDir
    name: string
    ext: string


# proc extractFilename*(x: AbsoluteFile): string {.borrow.}

# proc fileExists*(x: AbsoluteFile): bool {.borrow.}

# proc dirExists*(x: AbsoluteDir): bool {.borrow.}

# proc quoteShell*(x: AbsoluteFile): string {.borrow.}

# proc quoteShell*(x: AbsoluteDir): string {.borrow.}

# proc cmpPaths*(x, y: AbsoluteDir): int {.borrow.}

# proc createDir*(x: AbsoluteDir) {.borrow.}

# proc toAbsoluteDir*(path: string): AbsoluteDir =
#   result = if path.isAbsolute: AbsoluteDir(path)
#            else: AbsoluteDir(getCurrentDir() / path)

def toAbsoluteDir(path: string) -> AbsoluteDir:
  result = AbsoluteDir(path) if isAbsolute(path) else AbsoluteDir(getCurrentDir() / path)
  return result

# proc `$`*(x: AnyPath): string = x.string

def s_(x: AnyPath) -> string: return string(x)

# when true:
#   proc eqImpl(x, y: string): bool {.inline.} =
#     result = cmpPaths(x, y) == 0

#   proc `==`*[T: AnyPath](x, y: T): bool = eqImpl(x.string, y.string)

#   template postProcessBase(base: AbsoluteDir): untyped =
#     # xxx: as argued here https://github.com/nim-lang/Nim/pull/10018#issuecomment-448192956
#     # empty paths should not mean `cwd` so the correct behavior would be to throw
#     # here and make sure `outDir` is always correctly initialized; for now
#     # we simply preserve pre-existing external semantics and treat it as `cwd`
#     when false:
#       doAssert isAbsolute(base.string), base.string
#       base
#     else:
#       if base.isEmpty: getCurrentDir().AbsoluteDir else: base

#   proc `/`*(base: AbsoluteDir; f: RelativeFile): AbsoluteFile =
#     let base = postProcessBase(base)
#     assert(not isAbsolute(f.string), f.string)
#     result = AbsoluteFile newStringOfCap(base.string.len + f.string.len)
#     var state = 0
#     addNormalizePath(base.string, result.string, state)
#     addNormalizePath(f.string, result.string, state)

#   proc `/`*(base: AbsoluteDir; f: RelativeDir): AbsoluteDir =
#     let base = postProcessBase(base)
#     assert(not isAbsolute(f.string))
#     result = AbsoluteDir newStringOfCap(base.string.len + f.string.len)
#     var state = 0
#     addNormalizePath(base.string, result.string, state)
#     addNormalizePath(f.string, result.string, state)

#   proc relativeTo*(fullPath: AbsoluteFile, baseFilename: AbsoluteDir;
#                    sep = DirSep): RelativeFile =
#     # this currently fails for `tests/compilerapi/tcompilerapi.nim`
#     # it's needed otherwise would returns an absolute path
#     # assert not baseFilename.isEmpty, $fullPath
#     result = RelativeFile(relativePath(fullPath.string, baseFilename.string, sep))

#   proc toAbsolute*(file: string; base: AbsoluteDir): AbsoluteFile =
#     if isAbsolute(file): result = AbsoluteFile(file)
#     else: result = base / RelativeFile file

#   proc changeFileExt*(x: AbsoluteFile; ext: string): AbsoluteFile {.borrow.}

#   proc changeFileExt*(x: RelativeFile; ext: string): RelativeFile {.borrow.}

#   proc addFileExt*(x: AbsoluteFile; ext: string): AbsoluteFile {.borrow.}

#   proc addFileExt*(x: RelativeFile; ext: string): RelativeFile {.borrow.}

#   proc writeFile*(x: AbsoluteFile; content: string) {.borrow.}

if comptime(True):
  def eqImpl(x, y: string) -> bool:
    """{.inline.}"""
    result = cmpPaths(x, y) == 0
    return result

  proc `==`*[T: AnyPath](x, y: T): bool = eqImpl(x.string, y.string)

  @template 
  def postProcessBase(base: AbsoluteDir) -> untyped:
    # xxx: as argued here https://github.com/nim-lang/Nim/pull/10018#issuecomment-448192956
    # empty paths should not mean `cwd` so the correct behavior would be to throw
    # here and make sure `outDir` is always correctly initialized; for now
    # we simply preserve pre-existing external semantics and treat it as `cwd`
    if comptime(False):
      assert isAbsolute(string(base)), string(base)
      return base
    else:
      return AbsoluteDir(getCurrentDir()) if base.isEmpty() else base

  proc `/`*(base: AbsoluteDir; f: RelativeFile): AbsoluteFile =
    let base = postProcessBase(base)
    assert(not isAbsolute(f.string), f.string)
    result = AbsoluteFile newStringOfCap(base.string.len + f.string.len)
    var state = 0
    addNormalizePath(base.string, result.string, state)
    addNormalizePath(f.string, result.string, state)

  proc `/`*(base: AbsoluteDir; f: RelativeDir): AbsoluteDir =
    let base = postProcessBase(base)
    assert(not isAbsolute(f.string))
    result = AbsoluteDir newStringOfCap(base.string.len + f.string.len)
    var state = 0
    addNormalizePath(base.string, result.string, state)
    addNormalizePath(f.string, result.string, state)

  def relativeTo(fullPath: AbsoluteFile, baseFilename: AbsoluteDir,
                   sep = DirSep) -> RelativeFile:
    # this currently fails for `tests/compilerapi/tcompilerapi.nim`
    # it's needed otherwise would returns an absolute path
    # assert not baseFilename.isEmpty, $fullPath
    result = RelativeFile(relativePath(fullPath.string, baseFilename.string, sep))
    return result

#   proc toAbsolute*(file: string; base: AbsoluteDir): AbsoluteFile =
#     if isAbsolute(file): result = AbsoluteFile(file)
#     else: result = base / RelativeFile file


  def toAbsolute(file: string, base: AbsoluteDir) -> AbsoluteFile:
    if isAbsolute(file): result = AbsoluteFile(file)
    else: result = base / RelativeFile(file)
    return result

  proc changeFileExt*(x: AbsoluteFile; ext: string): AbsoluteFile {.borrow.}

  proc changeFileExt*(x: RelativeFile; ext: string): RelativeFile {.borrow.}

  proc addFileExt*(x: AbsoluteFile; ext: string): AbsoluteFile {.borrow.}

  proc addFileExt*(x: RelativeFile; ext: string): RelativeFile {.borrow.}

  proc writeFile*(x: AbsoluteFile; content: string) {.borrow.}


# proc skipHomeDir(x: string): int =
#   when defined(windows):
#     if x.continuesWith("Users/", len("C:/")):
#       result = 3
#     else:
#       result = 0
#   else:
#     if x.startsWith("/home/") or x.startsWith("/Users/"):
#       result = 3
#     elif x.startsWith("/mnt/") and x.continuesWith("/Users/", len("/mnt/c")):
#       result = 5
#     else:
#       result = 0

# proc relevantPart(s: string; afterSlashX: int): string =
#   result = newStringOfCap(s.len - 8)
#   var slashes = afterSlashX
#   for i in 0..<s.len:
#     if slashes == 0:
#       result.add s[i]
#     elif s[i] == '/':
#       dec slashes

# template canonSlashes(x: string): string =
#   when defined(windows):
#     x.replace('\\', '/')
#   else:
#     x

# proc customPathImpl(x: string): string =
#   # Idea: Encode a "protocol" via "//protocol/path" which is not ambiguous
#   # as path canonicalization would have removed the double slashes.
#   # /mnt/X/Users/Y
#   # X:\\Users\Y
#   # /home/Y
#   # -->
#   # //user/
#   if not isAbsolute(x):
#     result = customPathImpl(canonSlashes(getCurrentDir() / x))
#   else:
#     let slashes = skipHomeDir(x)
#     if slashes > 0:
#       result = "//user/" & relevantPart(x, slashes)
#     else:
#       result = x

# proc customPath*(x: string): string =
#   customPathImpl canonSlashes x
