# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/treemangler.nim
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
        while i >= 0 and b._buf[i] == ch('S'):
            i -= 1
        b._buf.setLen(i + 1)

    def _escape(b: mut @ Mangler, c: char):
        with const:
            _HexChars = string("0123456789abcdef")
        with var:
            n = nint(c)
        b._put(ch('X'))
        b._put(_HexChars[(n >> 4) & 0xF])
        b._put(_HexChars[n & 0xF])

    def addRaw(b: mut @ Mangler, s: string):
        b._put(s)

    def _addSep(b: mut @ Mangler):
        if len(b._buf) > 0 and b._buf[len(b._buf) - 1] == ch('Z'):
            pass  # space not required
        b._put(ch('S'))

    def _addBegin(b: mut @ Mangler):
        if len(b._buf) > 0 and b._buf[len(b._buf) - 1] == ch('S'):
            b._buf[len(b._buf) - 1] = ch('A')
        else:
            b._put(ch('A'))

    def _referencePrevious(b: mut @ Mangler, s: string) -> bool:
        result = False
        if len(s) > 2:
            with let:
                existing = b._seen.getOrDefault(s)
                oldLen = len(b._buf)
            if existing == 0:
                b._seen[s] = oldLen
            else:
                b._buf.add(ch('R'))
                b._buf.addInt(existing - 1)
                if len(b._buf) - oldLen >= len(s):
                    # undo, it was a pessimization!
                    b._buf.setLen(oldLen)
                else:
                    result = True
        return result

    def addEmpty(b: mut @ Mangler, count: nint = 1):
        b._addSep()
        for i in inrange(1, count):
            b._put(ch('E'))

    def addIntLit(b: mut @ Mangler, i: BiggestInt):
        b._addSep()
        b._put(str(i))

    def addUIntLit(b: mut @ Mangler, u: BiggestUInt):
        b._addSep()
        b._put(str(u))

    def endTree(b: mut @ Mangler):
        assert b._nesting > 0, "generating ')' would produce a syntax error"
        b._nesting -= 1
        b._undoWhitespace()
        b._put(ch('Z'))


@hook("copy")
def _copyMangler(dest: mut @ Mangler, src: Mangler):
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
    while i > 0 and b._buf[i] == ch('Z'):
        i -= 1
    b._buf.setLen(i + 1)
    result = move(b._buf)
    return result


with const:
    _ControlLetters = Tset[char](ch('A'), ch('Z'), ch('E'), ch('S'), ch('O'), ch('U'), ch('X'), ch('R'))  # not yet necessary: 'K'


@template
def _needsEscape(c: char) -> bool:
    return c not in (Tset[char](inrange(ch('a'), ch('z')), inrange(ch('0'), ch('9')), ch('_')) - _ControlLetters)


#  ------------ Atoms ------------------------


def putTag(b: mut @ Mangler, tag: string):
    if not b._referencePrevious(tag):
        for c in tag:
            if _needsEscape(c):
                b._escape(c)
            else:
                b._put(c)


def addIdent(b: mut @ Mangler, s: string):
    b._addSep()
    if not b._referencePrevious(s):
        for c in s:
            if c == ch('.') or _needsEscape(c):
                b._escape(c)
            else:
                b._put(c)


def _addSymbolBody(b: mut @ Mangler, s: string):
    for part in s.split(ch('.')):
        if not b._referencePrevious(part):
            for c in part:
                if _needsEscape(c):
                    b._escape(c)
                else:
                    b._put(c)


def addSymbol(b: mut @ Mangler, s: string):
    b._addSep()
    if not b._referencePrevious(s):
        _addSymbolBody(b, s)


def addSymbolDef(b: mut @ Mangler, s: string):
    b._addSep()
    b._put(ch('O'))
    if not b._referencePrevious(s):
        _addSymbolBody(b, s)


def addStrLit(b: mut @ Mangler, s: string):
    b._addSep()
    b._put(ch('U'))
    for c in s:
        if _needsEscape(c):
            b._escape(c)
        else:
            b._put(c)
    b._put(ch('U'))


def addCharLit(b: mut @ Mangler, c: char):
    b._addSep()
    b._escape(ch("'"))
    if _needsEscape(c):
        b._escape(c)
    else:
        b._put(c)
    b._escape(ch("'"))


def addFloatLit(b: mut @ Mangler, f: BiggestFloat):
    b._addSep()
    with var:
        x = string("")
    x.addFloat(f)
    for c in x:
        if c == ch('e'):
            b._put(ch('E'))
        elif _needsEscape(c):
            b._escape(c)
        else:
            b._put(c)


def addKeyw(b: mut @ Mangler, keyw: string):
    ## Adds a complete compound node that has no children like `(nil)`.
    b._addBegin()
    putTag(b, keyw)
    b._put(ch('Z'))


def addTree(b: mut @ Mangler, kind: string):
    ## Starts a new compound node. Must be closed with `endTree`.
    ## See also `withTree`.
    ## `kind` is allowed to start with a dot. This emits a directive then.
    b._addBegin()
    putTag(b, kind)
    b._nesting += 1


@template
def withTree(b: mut @ Mangler, kind: string, body: untyped = None):
    ## Convenience template that wraps `body` around `addTree` and `endTree`
    ## calls.
    addTree(b, kind)
    body
    b.endTree()


if comptime(__name__ == "__main__"):
    from nimic.std.syncio import *

    def _test(b: sink @ Mangler):
        with withTree(b, string("stmts")):
            with withTree(b, string("call")):
                addSymbol(b, string("foo.3.mymod"))
                b.addIntLit(3423)
                addFloatLit(b, 50.4)

        echo(extract(b))

        # (array (range 0 9) (array (range 0 4 (i 8))))
        with var:
            m = createMangler(60)
        with withTree(m, string("array")):
            with withTree(m, string("range")):
                m.addIntLit(0)
                m.addIntLit(9)
            with withTree(m, string("array")):
                with withTree(m, string("range")):
                    m.addIntLit(0)
                    m.addIntLit(4)
                with withTree(m, string("i")):
                    m.addIntLit(8)

        assert extract(m) == "AarrayArangeS0S9ZAR0AR6S0S4ZAiS8"

    def _main():
        with var:
            b = createMangler(10)
        _test(b)

    _main()
