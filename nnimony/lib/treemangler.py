# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/treemangler.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Turn NIF trees into identifiers. See the spec section "NIF trees as identifiers"
## for the used algorithm.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.assertions import *
from nimic.std.hashes import *
from nimic.std.tables import *
from nimic.std.formatfloat import *
from nimic.std.strutils import *


class Mangler(Object):
    ## In the end `extract` must be called.
    _buf: string
    _nesting: nint
    _seen: Table[string, nint]
    bits: nint


@hook("copy")
def _copy(dest: mut @ Mangler, src: Mangler):
    """{.error.}"""
    pass


def createMangler(sizeHint: nint, bits: nint = -1) -> Mangler:
    return Mangler(_buf=newStringOfCap(sizeHint), bits=bits)


def extract(b: sink @ Mangler) -> string:
    ## Extracts the buffer from the mangler.
    ## The mangler should not be used afterwards.
    assert b._nesting == 0, "unpaired '(' or ')'"
    with var:
        i = len(b._buf) - 1
    while i > 0 and b._buf[i] == char('Z'):
        i -= 1
    b._buf.setLen(i + 1)
    result = move(b._buf)
    return result


@dispatch
def _put(b: mut @ Mangler, s: string):
    """{.inline.}"""
    b._buf.add(s)


@dispatch
def _put(b: mut @ Mangler, s: char):
    """{.inline.}"""
    b._buf.add(s)


def _undoWhitespace(b: mut @ Mangler):
    with var:
        i = len(b._buf) - 1
    while i >= 0 and b._buf[i] == char('S'):
        i -= 1
    b._buf.setLen(i + 1)


def _escape(b: mut @ Mangler, c: char):
    with const:
        _HexChars = string("0123456789abcdef")
    with var:
        n = nint(c)
    _put(b, char('X'))
    _put(b, _HexChars[(n >> 4) & 0xF])
    _put(b, _HexChars[n & 0xF])


with const:
    _ControlLetters = Tset[char](char('A'), char('Z'), char('E'), char('S'), char('O'), char('U'), char('X'), char('R'))  # not yet necessary: 'K'


@template
def _needsEscape(c: char) -> bool:
    return c not in (Tset[char](inrange(char('a'), char('z')), inrange(char('0'), char('9')), char('_')) - _ControlLetters)


def addRaw(b: mut @ Mangler, s: string):
    _put(b, s)


def _addSep(b: mut @ Mangler):
    if len(b._buf) > 0 and b._buf[len(b._buf) - 1] == char('Z'):
        pass  # space not required
    _put(b, char('S'))


def _addBegin(b: mut @ Mangler):
    if len(b._buf) > 0 and b._buf[len(b._buf) - 1] == char('S'):
        b._buf[len(b._buf) - 1] = char('A')
    else:
        _put(b, char('A'))


def _referencePrevious(b: mut @ Mangler, s: string) -> bool:
    result = False
    if len(s) > 2:
        with let:
            existing = b._seen.getOrDefault(s)
            oldLen = len(b._buf)
        if existing == 0:
            b._seen[s] = oldLen
        else:
            b._buf.add(char('R'))
            b._buf.addInt(existing - 1)
            if len(b._buf) - oldLen >= len(s):
                # undo, it was a pessimization!
                b._buf.setLen(oldLen)
            else:
                result = True
    return result


#  ------------ Atoms ------------------------


def putTag(b: mut @ Mangler, tag: string):
    if not _referencePrevious(b, tag):
        for c in tag:
            if _needsEscape(c):
                _escape(b, c)
            else:
                _put(b, c)


def addIdent(b: mut @ Mangler, s: string):
    _addSep(b)
    if not _referencePrevious(b, s):
        for c in s:
            if c == char('.') or _needsEscape(c):
                _escape(b, c)
            else:
                _put(b, c)


def _addSymbolBody(b: mut @ Mangler, s: string):
    for part in s.split(char('.')):
        if not _referencePrevious(b, part):
            for c in part:
                if _needsEscape(c):
                    _escape(b, c)
                else:
                    _put(b, c)


def addSymbol(b: mut @ Mangler, s: string):
    _addSep(b)
    if not _referencePrevious(b, s):
        _addSymbolBody(b, s)


def addSymbolDef(b: mut @ Mangler, s: string):
    _addSep(b)
    _put(b, char('O'))
    if not _referencePrevious(b, s):
        _addSymbolBody(b, s)


def addStrLit(b: mut @ Mangler, s: string):
    _addSep(b)
    _put(b, char('U'))
    for c in s:
        if _needsEscape(c):
            _escape(b, c)
        else:
            _put(b, c)
    _put(b, char('U'))


def addEmpty(b: mut @ Mangler, count: nint = 1):
    _addSep(b)
    for i in inrange(1, count):
        _put(b, char('E'))


def addCharLit(b: mut @ Mangler, c: char):
    _addSep(b)
    _escape(b, char("'"))
    if _needsEscape(c):
        _escape(b, c)
    else:
        _put(b, c)
    _escape(b, char("'"))


def addIntLit(b: mut @ Mangler, i: BiggestInt):
    _addSep(b)
    _put(b, str(i))


def addUIntLit(b: mut @ Mangler, u: BiggestUInt):
    _addSep(b)
    _put(b, str(u))


def addFloatLit(b: mut @ Mangler, f: BiggestFloat):
    _addSep(b)
    with var:
        x = string("")
    x.addFloat(f)
    for c in x:
        if c == char('e'):
            _put(b, char('E'))
        elif _needsEscape(c):
            _escape(b, c)
        else:
            _put(b, c)


def addKeyw(b: mut @ Mangler, keyw: string):
    ## Adds a complete compound node that has no children like `(nil)`.
    _addBegin(b)
    putTag(b, keyw)
    _put(b, char('Z'))


def addTree(b: mut @ Mangler, kind: string):
    ## Starts a new compound node. Must be closed with `endTree`.
    ## See also `withTree`.
    ## `kind` is allowed to start with a dot. This emits a directive then.
    _addBegin(b)
    putTag(b, kind)
    b._nesting += 1


def endTree(b: mut @ Mangler):
    assert b._nesting > 0, "generating ')' would produce a syntax error"
    b._nesting -= 1
    _undoWhitespace(b)
    _put(b, char('Z'))


@template
def withTree(b: mut @ Mangler, kind: string, body: untyped = None):
    ## Convenience template that wraps `body` around `addTree` and `endTree`
    ## calls.
    addTree(b, kind)
    body
    endTree(b)


if comptime(__name__ == "__main__"):
    from nimic.std.syncio import *

    def _test(b: sink @ Mangler):
        with b.withTree(string("stmts")):
            with b.withTree(string("call")):
                b.addSymbol(string("foo.3.mymod"))
                b.addIntLit(3423)
                b.addFloatLit(50.4)

        echo(extract(b))

        # (array (range 0 9) (array (range 0 4 (i 8))))
        with var:
            m = createMangler(60)
        with m.withTree(string("array")):
            with m.withTree(string("range")):
                m.addIntLit(0)
                m.addIntLit(9)
            with m.withTree(string("array")):
                with m.withTree(string("range")):
                    m.addIntLit(0)
                    m.addIntLit(4)
                with m.withTree(string("i")):
                    m.addIntLit(8)

        assert extract(m) == string("AarrayArangeS0S9ZAR0AR6S0S4ZAiS8")

    def _main():
        with var:
            b = createMangler(10)
        _test(b)

    _main()
