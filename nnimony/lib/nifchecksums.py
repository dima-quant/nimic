# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/nifchecksums.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std import formatfloat

from . import bitabs
from . import nifreader
from .nifpools import (
    buildTree, createTokenBuf, Cursor, cursorTagId, endRead, ErrT, floatVal, globalTags, into, intVal, isCharLit,
    isDotToken, isFloatLit, isIdent, isIntLit, isStringLit, isSymbol, isSymbolDef, isTagLit, isUIntLit, NoLineInfo,
    parseFromBuffer, pool, registerTag, strId, symId, TagId, toString, uintVal, uoperand)

if comptime(defined("nimony")):
    from nimic.std.sha1 import finalize, newSha1State, SecureHash, Sha1State, update
else:
    # `std/sha1` is `{.deprecated.}` in favor of the `checksums` package, but it is
    # the only SHA-1 module guaranteed to ship in `lib/std` on every Nim 2.x and
    # devel install. The previous `$nim/dist/checksums/...` path only exists in a
    # git/devel layout, so a released Nim 2 (as the docs require) failed with
    # "cannot open file". It is the same SHA-1 fork, so digests are identical.
    with push("warning[Deprecated]: off"):
        from nimic.std.sha1 import finalize, newSha1State, SecureHash, Sha1State, update


def _updateAtom(dest: mut @ Sha1State, n: Cursor):
    ## Hashes one leaf token (build-agnostic: the hashed content is the tag/sym
    ## name, string, or numeric value, so the digest matches classic byte-for-byte).
    if isSymbolDef(n):
        update(dest, string(" :")); update(dest, pool.symString(symId(n)))
    elif isSymbol(n):
        update(dest, string(" ")); update(dest, pool.symString(symId(n)))
    elif isIdent(n):
        update(dest, string(" ")); update(dest, pool.strings[strId(n)])
    elif isIntLit(n):
        update(dest, string(" ")); update(dest, str(intVal(n)))
    elif isUIntLit(n):
        update(dest, string(" ")); update(dest, str(uintVal(n)))
    elif isFloatLit(n):
        update(dest, string(" ")); update(dest, str(floatVal(n)))
    elif isStringLit(n):
        update(dest, string(" ")); update(dest, pool.strings[strId(n)])
    elif isCharLit(n):
        update(dest, string(" ")); update(dest, str(uoperand(n)))
    elif isDotToken(n):
        update(dest, string("."))


def updateLoop(dest: mut @ Sha1State, n: mut @ Cursor, inlineT: TagId, foundInline: mut @ bool):
    ## Hashes the single tree/token at `n`, advancing past it. The digest is
    ## the same with and without ParRi elision: the close is hashed as ")"
    ## whether or not its token physically exists.
    if isTagLit(n):
        update(dest, string("("))
        update(dest, globalTags.tags[cursorTagId(n)])
        if cursorTagId(n) == inlineT: foundInline <<= True
        with into(n):
            while n.hasMore():
                updateLoop(dest, n, inlineT, foundInline)
        update(dest, string(")"))
    else:
        _updateAtom(dest, n)
        n.inc()


with const:
    _NoInlineTag = TagId(high(uint32))  ## never matches a real tag


@dispatch
def computeChecksum(n: Cursor) -> string:
    with var:
        checksum = newSha1State()
    with var:
        n = n.copy()
    with var:
        dummy = nbool(False)
    updateLoop(checksum, n, _NoInlineTag, dummy)
    with let:
        final = SecureHash(finalize(checksum))
    result = string(str(final))
    return result


@dispatch
def computeChecksum(s: string) -> string:
    with var:
        state = newSha1State()
    update(state, s)
    return string(str(SecureHash(finalize(state))))


if comptime(__name__ == "__main__"):
    def checksumOf(text: string) -> string:
        with var:
            b = parseFromBuffer(text, string("cs"))
        with var:
            c = b.beginRead()
        result = computeChecksum(c)
        endRead(c)
        return result

    def hashedText(text: string, inlineT: TagId) -> string:
        # the digest of updateLoop, plus whether the inline tag was seen
        with var:
            b = parseFromBuffer(text, string("cs"))
        with var:
            c = b.beginRead()
        with var:
            st = newSha1State()
        with var:
            found = nbool(False)
        echo("  foundInline before: ", found)
        updateLoop(st, c, inlineT, found)
        echo("  foundInline after: ", found, " at end: ", not c.hasMore())
        endRead(c)
        return string(str(SecureHash(finalize(st))))

    def testChecksums():
        # every atom kind, nested tags
        with let:
            trees = [
                string("(stmts)"),
                string("(stmts (call foo 1) (ret x))"),
                string("(a (b (c (d 1))))"),
                string("(s :x.0.cs x.0.cs ident \"str lit\" 'c' .)"),
                string("(ints 0 -1 -9223372036854775808 9223372036854775807 123456789)"),
                string("(uints 0u 1u 18446744073709551615u)"),
                string("(floats 0.1 1.0 -0.0 0.0 1e100 2.5e-3)"),
                string("x"),
                string("\"just a string\""),
            ]
        for t in trees:
            echo(t, " -> ", checksumOf(t))

        # the same tree with and without line info hashes the same
        echo("line info ignored: ",
             checksumOf(string("(stmts@1,2,f.nim (call@1,1 foo 1))")) == checksumOf(string("(stmts (call foo 1))")))

        # floats the parser may not spell: built with addFloatLit
        with var:
            fb = createTokenBuf(8)
        with buildTree(fb, ErrT, NoLineInfo):
            fb.addFloatLit(0.1)
            fb.addFloatLit(1e100)
            fb.addFloatLit(-0.0)
            fb.addFloatLit(1.0)
            fb.addFloatLit(1e309)
            fb.addFloatLit(-1e309)
            fb.addFloatLit(1e309 - 1e309)
            fb.addIntLit(int64(-42))
            fb.addUIntLit(high(uint64))
            fb.addCharLit(char("z"))
        echo("built: ", toString(fb, False))
        with var:
            fc = fb.beginRead()
        echo("built -> ", computeChecksum(fc))
        endRead(fc)

        # inline tag found / not found
        with let:
            inl = registerTag(string("inl"))
        echo("inline found:")
        echo("  ", hashedText(string("(stmts (inl 1) 2)"), inl))
        echo("inline not found:")
        echo("  ", hashedText(string("(stmts (call 1) 2)"), inl))
        echo("inline with NoInlineTag:")
        echo("  ", hashedText(string("(stmts (inl 1) 2)"), _NoInlineTag))

        # strings
        for s in [string(""), string("abc"), string("hello world"), string("(stmts 1)")]:
            echo("\"", s, "\" -> ", computeChecksum(s))

    testChecksums()
