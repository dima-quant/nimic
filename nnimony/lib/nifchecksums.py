# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifchecksums.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.formatfloat import *

from .bitabs import *
from .nifreader import *
from .nifpools import *

if comptime(defined("nimony")):
    from nimic.std.sha1 import *
else:
    # `std/sha1` is `{.deprecated.}` in favor of the `checksums` package, but it is
    # the only SHA-1 module guaranteed to ship in `lib/std` on every Nim 2.x and
    # devel install. The previous `$nim/dist/checksums/...` path only exists in a
    # git/devel layout, so a released Nim 2 (as the docs require) failed with
    # "cannot open file". It is the same SHA-1 fork, so digests are identical.
    with push("warning[Deprecated]: off"):
        from nimic.std.sha1 import *


def _updateAtom(dest: mut @ Sha1State, n: Cursor):
    ## Hashes one leaf token (build-agnostic: the hashed content is the tag/sym
    ## name, string, or numeric value, so the digest matches classic byte-for-byte).
    if n.isSymbolDef():
        update(dest, " :"); update(dest, pool.symString(n.symId()))
    elif n.isSymbol():
        update(dest, " "); update(dest, pool.symString(n.symId()))
    elif n.isIdent():
        update(dest, " "); update(dest, pool.strings[n.strId()])
    elif n.isIntLit():
        update(dest, " "); update(dest, str(n.intVal()))
    elif n.isUIntLit():
        update(dest, " "); update(dest, str(n.uintVal()))
    elif n.isFloatLit():
        update(dest, " "); update(dest, str(n.floatVal()))
    elif n.isStringLit():
        update(dest, " "); update(dest, pool.strings[n.strId()])
    elif n.isCharLit():
        update(dest, " "); update(dest, str(n.uoperand()))
    elif n.isDotToken():
        update(dest, ".")


def updateLoop(dest: mut @ Sha1State, n: mut @ Cursor, inlineT: TagId, foundInline: mut @ bool):
    ## Hashes the single tree/token at `n`, advancing past it. The digest is
    ## the same with and without ParRi elision: the close is hashed as ")"
    ## whether or not its token physically exists.
    if n.isTagLit():
        update(dest, "(")
        update(dest, globalTags.tags[n.cursorTagId()])
        if n.cursorTagId() == inlineT: foundInline <<= True
        with n.into():
            while n.hasMore():
                updateLoop(dest, n, inlineT, foundInline)
        update(dest, ")")
    else:
        _updateAtom(dest, n)
        inc(n)


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
        final = SecureHash(checksum.finalize())
    result = string(str(final))
    return result


@dispatch
def computeChecksum(s: string) -> string:
    with var:
        state = newSha1State()
    state.update(s)
    return string(str(SecureHash(state.finalize())))


if comptime(__name__ == "__main__"):
    def _checksumOf(text: string) -> string:
        with var:
            b = parseFromBuffer(text, string("cs"))
        with var:
            c = b.beginRead()
        result = computeChecksum(c)
        c.endRead()
        return result

    def _hashedText(text: string, inlineT: TagId) -> string:
        # the digest of updateLoop, plus whether the inline tag was seen
        with var:
            b = parseFromBuffer(text, string("cs"))
        with var:
            c = b.beginRead()
        with var:
            st = newSha1State()
        with var:
            found = nbool(False)
        echo(string("  foundInline before: "), found)
        updateLoop(st, c, inlineT, found)
        echo(string("  foundInline after: "), found, string(" at end: "), not c.hasMore())
        c.endRead()
        return string(str(SecureHash(st.finalize())))

    def _testChecksums():
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
            echo(t, string(" -> "), _checksumOf(t))

        # the same tree with and without line info hashes the same
        echo(string("line info ignored: "),
             _checksumOf(string("(stmts@1,2,f.nim (call@1,1 foo 1))")) == _checksumOf(string("(stmts (call foo 1))")))

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
            fb.addCharLit(ch("z"))
        echo(string("built: "), toString(fb, False))
        with var:
            fc = fb.beginRead()
        echo(string("built -> "), computeChecksum(fc))
        fc.endRead()

        # inline tag found / not found
        with let:
            inl = registerTag(string("inl"))
        echo(string("inline found:"))
        echo(string("  "), _hashedText(string("(stmts (inl 1) 2)"), inl))
        echo(string("inline not found:"))
        echo(string("  "), _hashedText(string("(stmts (call 1) 2)"), inl))
        echo(string("inline with NoInlineTag:"))
        echo(string("  "), _hashedText(string("(stmts (inl 1) 2)"), _NoInlineTag))

        # strings
        for s in [string(""), string("abc"), string("hello world"), string("(stmts 1)")]:
            echo(string("\""), s, string("\" -> "), computeChecksum(s))

    _testChecksums()
