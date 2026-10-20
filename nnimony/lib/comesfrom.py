# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/comesfrom.nim
# ///
#       Nimony
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

from __future__ import annotations
from nimic.ntypes import *

## Expansion provenance encoded in a line-info filename.
##
## Code produced by expanding a template does not get its own wrapper node.
## Instead the tokens carry a *forged* filename that records what they came
## from, so a debug backend can emit them as DWARF inlined frames:
##
##   __crucial\0setElem.0.foo\1foo.nim\116\0[]=.0.system\1system.nim\134\0system.nim
##   ^prefix    ^-------- outermost -------^ ^--------- innermost --------^ ^real file
##
## The chain runs outermost-first, so its length is the inlining depth. Each
## entry is `<sym>\1<declfile>\1<declline>`: the symbol names the expanded
## routine, and the declaration site is carried because it cannot be recovered
## later - a template declaration does not survive into the backend, and the
## expanded code's own line info points at wherever the body came from, not at
## the template. Everything after the last NUL is the real filename, which is
## what a consumer that does not care about frames should use.
##
## A filename cannot otherwise contain a NUL or a `\1`, which is what makes the
## encoding unambiguous - note that `|` would not do, since Nim lets an operator
## be named `|`. `nifbuilder.needsEscape` covers `c < ' '`, so both control
## characters survive text NIF as `\00` / `\01`; `bif` writes filenames
## length-prefixed, so binary is fine.
##
## Deliberately free of any NIF dependency: it is plain string handling, so the
## front end, the C backend and the LLVM backend can all reach it without
## pulling in a cursor API.

with const:
    CrucialPrefix = string("__crucial\0")
    ## Marks a forged filename that carries template-expansion provenance.
    CrucialFieldSep = ch("\1")
    ## Separates `<sym>`, `<declfile>` and `<declline>` inside one chain entry.


class CrucialOrigin(Object):  ## One level of an expansion chain.
    sym: string        ## the expanded routine, mangled (`setElem.0.foo`)
    declFile: string   ## where it was declared; "" when unknown
    declLine: int32    ## its declaration line; 0 when unknown


def isCrucialFile(fname: string) -> bool:
    """{.noSideEffect.}"""
    ## True when `fname` carries expansion provenance rather than being a plain
    ## source path. Cheap enough to call per token: the `\0` at the end of the
    ## prefix is checked first, and a real path never has one.
    if fname.len <= CrucialPrefix.len: return False
    if fname[CrucialPrefix.len - 1] != ch('\0'): return False
    for i in range(0, CrucialPrefix.len):
        if fname[i] != CrucialPrefix[i]: return False
    result = True
    return result


@ufcs(string)
def addCrucialInfo(dest: mut @ string, sym: string, declFile: string,
                   declLine: int32):
    """{.noSideEffect.}"""
    ## Append one expansion entry to a forged filename under construction.
    ## Entries are written outermost first; what follows the last one is the real
    ## filename. `dest` starts as `CrucialPrefix`, so building a name is
    ##
    ##   var f = CrucialPrefix
    ##   f.addCrucialInfo(sym, declFile, declLine)
    ##   f.add crucialTail(oldName)
    ##
    ## which prepends onto whatever chain `oldName` already had without parsing
    ## it back out.
    dest.add(sym)
    dest.add(CrucialFieldSep)
    dest.add(declFile)
    dest.add(CrucialFieldSep)
    dest.add(str(declLine))
    dest.add(ch('\0'))


def crucialTail(fname: string) -> string:
    """{.noSideEffect.}"""
    ## Everything of `fname` that follows `CrucialPrefix`: its existing entries
    ## plus the real filename, in the exact form they must keep. For a plain
    ## filename that is the name itself, so appending this after some entries
    ## works whether or not `fname` was already forged.
    return fname.substr(CrucialPrefix.len) if isCrucialFile(fname) else fname


def realFile(fname: string) -> string:
    """{.noSideEffect.}"""
    ## The actual source file, with any expansion provenance stripped. Returns
    ## `fname` unchanged when it carries none, so every consumer can call it.
    if not isCrucialFile(fname): return fname
    with var:
        last = -1
    for i in range(0, fname.len):
        if fname[i] == ch('\0'): last = i
    return fname if last < 0 else fname.substr(last + 1)


def _parseCrucialOrigin(entry: string) -> CrucialOrigin:
    """{.noSideEffect.}"""
    ## Split one `<sym>\1<declfile>\1<declline>` entry. Tolerates a bare symbol
    ## with no declaration site, so a partially-known chain still names its
    ## frames instead of being discarded.
    result = CrucialOrigin(sym=entry, declFile=string(""), declLine=i32(0))
    with var:
        first = -1
        second = -1
    for i in range(0, entry.len):
        if entry[i] == CrucialFieldSep:
            if first < 0: first = i
            elif second < 0: second = i
    if first < 0: return result
    result.sym = entry.substr(0, first - 1)
    if second < 0:
        result.declFile = entry.substr(first + 1)
        return result
    result.declFile = entry.substr(first + 1, second - 1)
    with var:
        line = i32(0)
    for i in range(second + 1, entry.len):
        with let:
            ch = entry[i]
        if ch < char('0') or ch > char('9'): return result
        line = line * i32(10) + int32(ord(ch) - ord(char('0')))
    result.declLine = line
    return result


def crucialOrigins(fname: string) -> CrucialOrigin:
    """{.noSideEffect.}"""
    ## The expanded routines `fname` came from, outermost first. Yields nothing
    ## for a plain filename.
    if isCrucialFile(fname):
        with var:
            start = CrucialPrefix.len
            i = start
        while i < fname.len:
            if fname[i] == ch('\0'):
                yield _parseCrucialOrigin(fname.substr(start, i - 1))
                start = i + 1
            i += 1
        # the tail after the last NUL is the real filename, not an origin


if comptime(__name__ == "__main__"):
    for _plain in [string(""), string("system.nim"), string("__crucial"), string("__crucialXsystem.nim"), string("__cruciaX\0system.nim")]:
        echo(isCrucialFile(_plain), "|", crucialTail(_plain) == _plain, "|", realFile(_plain) == _plain)
        with var:
            _cnt = 0
        for _o in crucialOrigins(_plain):
            _cnt += 1
        echo(_cnt)

    with var:
        _f1 = CrucialPrefix.copy()
    _f1.addCrucialInfo(string("[]=.0.system"), string("system.nim"), i32(34))
    _f1.add(crucialTail(string("system.nim")))
    echo(isCrucialFile(_f1), "|", realFile(_f1), "|", crucialTail(_f1).len)
    for _o in crucialOrigins(_f1):
        echo(_o.sym, "|", _o.declFile, "|", _o.declLine)

    with var:
        _f2 = CrucialPrefix.copy()
    _f2.addCrucialInfo(string("setElem.0.foo"), string("foo.nim"), i32(16))
    _f2.add(crucialTail(_f1))
    echo(isCrucialFile(_f2), "|", realFile(_f2), "|", crucialTail(_f2).len)
    for _o in crucialOrigins(_f2):
        echo(_o.sym, "|", _o.declFile, "|", _o.declLine)

    with let:
        _bare = CrucialPrefix + string("bareSym.0.mod\0real.nim")
        _noLine = CrucialPrefix + string("symFile.0.mod") + CrucialFieldSep + string("decl.nim\0real.nim")
        _badLine = CrucialPrefix + string("symBad.0.mod") + CrucialFieldSep + string("decl.nim") + CrucialFieldSep + string("42x\0real.nim")
    for _forged in [_bare, _noLine, _badLine]:
        echo(isCrucialFile(_forged), "|", realFile(_forged))
        for _o in crucialOrigins(_forged):
            echo(_o.sym, "|", _o.declFile, "|", _o.declLine)
