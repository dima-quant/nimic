# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/filelinecache.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Logic for mapping a (file, line, col) key to the file's content.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.syncio import *
from nimic.std.tables import *
from nimic.std.hashes import *
from nimic.std.strutils import *

if comptime(defined("nimony")):
    pragma('feature: "assumeSync"')  # compiler-internal globals; single threaded

include("compat2")


class CachedFile(Object):
    _content: string
    _lineStarts: seq[nint]


class FilePosition(Object):
    line: nint
    col: nint


class _FileLineCache(Object):
    _files: Table[string, CachedFile]


with var:
    _gFileLineCache = _FileLineCache()


def loadFile(filename: string):
    """{.canRaise.}"""
    with var:
        entry = CachedFile(_content=readFile(filename), _lineStarts=seq[nint]([0]))
        nl = find(entry._content, char('\n'))
    while nl > 0:
        entry._lineStarts.add(nl)
        nl = find(entry._content, char('\n'), nl + 1)
    _gFileLineCache._files[filename] = ensureMove(entry)


@dispatch
def extract(filename: string, start: FilePosition, finish: FilePosition) -> string:
    """{.canRaise.}"""
    if not _gFileLineCache._files.hasKey(filename):
        loadFile(filename)
    with let:
        entry: pragma("cursor") = _gFileLineCache._files[filename]
        startIdx = entry._lineStarts[start.line - 1] + start.col - 1
        finishIdx = entry._lineStarts[finish.line - 1] + finish.col - 1
    result = entry._content.substr(startIdx, finishIdx)
    return result


@dispatch
def extract(filename: string, start: FilePosition) -> string:
    """{.canRaise.}"""
    if not _gFileLineCache._files.hasKey(filename):
        loadFile(filename)
    with let:
        entry: pragma("cursor") = _gFileLineCache._files[filename]
        startIdx = entry._lineStarts[start.line - 1] + start.col - 1
    if start.line < len(entry._lineStarts):
        with let:
            finishIdx = entry._lineStarts[start.line] - 1
        result = entry._content.substr(startIdx, finishIdx)
    else:
        result = entry._content.substr(startIdx)
    return result


if comptime(__name__ == "__main__"):
    try:
        echo(extract(string("src/lib/filelinecache.nim"), FilePosition(line=1, col=9), FilePosition(line=3, col=2)))
        echo(extract(string("src/lib/filelinecache.nim"), FilePosition(line=1, col=9)))
    except:
        quit(string("failed to extract"))

    # Additional tests: extract with one and two positions, the last line, and a file loaded twice
    try:
        echo(extract(string("src/lib/filelinecache.nim"), FilePosition(line=2, col=1)))
        echo(extract(string("src/lib/filelinecache.nim"), FilePosition(line=4, col=1), FilePosition(line=4, col=7)))
        echo(extract(string("src/lib/filelinecache.nim"), FilePosition(line=64, col=1)))
        echo(extract(string("src/lib/filelinecache.nim"), FilePosition(line=1, col=1), FilePosition(line=1, col=7)))
    except:
        quit(string("failed in additional tests"))

    # getOrQuit (included from compat2): the var and the lent overloads, on a Table and an OrderedTable
    with var:
        tv = initTable[string, nint]()
        ov = initOrderedTable[string, nint]()
    tv[string("a")] = 1
    ov[string("b")] = 2
    with let:
        tl = tv
        ol = ov
    echo(getOrQuit(tv, string("a")))
    echo(getOrQuit(ov, string("b")))
    echo(getOrQuit(tl, string("a")))
    echo(getOrQuit(ol, string("b")))
