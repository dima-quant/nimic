# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/nifbuilder.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Support code for generating NIF code.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    # The write cursor (`Builder.raw`) is a raw payload pointer that is nil between
    # `finish` and the next `reserve`; the nil analysis cannot follow that through
    # `beginStore`. Same reason `bif` sets it.
    pragma('feature: "lenientnils"')

from nimic.std import assertions
from nimic.std import syncio
from nimic.std import formatfloat
from nimic.std.math import classify, FloatClass, Inf, NaN
importFrom("nimic.std.strutils", "endsWith")
from .vfs import FileWriteMode, vfsExists, vfsMtime, vfsRead, vfsRemove, vfsWrite
from . import vfs
exportFrom(vfs, "FileWriteMode")


class _Mode(NIntEnum):
    UsesMem = auto()
    UsesFile = auto()


class Builder(Object):
    ## A builder can be in-memory or directly write into a file.
    ## In the end either `extract` or `close` must be called.
    ## File-mode builders accumulate into `buffer` and flush
    ## once at `close()` via `vfsWrite`, so the destination
    ## (real disk, in-memory cache, sandbox-rejected, …) is
    ## decided by the active VFS relays at close time.
    _buffer: string
    ## Storage, NOT the result: `buffer.len` is the *capacity*, `offs` is how
    ## much of it is written. `finish` truncates it back to `offs`.
    _raw: ptr[UncheckedArray[char]]
    ## Write cursor into `buffer`'s payload. Kept in the object because the
    ## alternative — `buffer.add c` per byte — cost 54 instructions per output
    ## byte natively (a call, a COW check, a capacity check and an inline-cache
    ## sync), which was the single biggest item in the `emit` benchmark. The
    ## pointer is stable across moves of the Builder because `reserve` keeps
    ## the string in its *long* (heap) representation; see `MinCapacity`.
    _cap: nint
    _mode: _Mode
    _writeMode: FileWriteMode
    _compact: bool
    _filename: string
    _nesting: nint
    _offs: nint

    def attachedToFile(b: Builder) -> bool:
        """{.inline.}"""
        return b._mode == _Mode.UsesFile

    def _drainPending(b: mut @ Builder):
        ## No-op kept for source compatibility; both modes now buffer in
        ## memory until `close`.
        return

    def _undoWhitespace(b: mut @ Builder):
        with var:
            i = b._offs - 1
        while i >= 0 and b._raw[i] in Tset[char](ch(' '), ch('\n')):
            i -= 1
        b._offs = i + 1

    def patchIndexAt(b: mut @ Builder, patchPos: nint, indexAt: nint):
        with var:
            s = string("")
        s.addInt(indexAt)
        for i in range(s.len):
            b._raw[patchPos + i] = s[i]

    def offset(b: Builder) -> nint:
        """{.inline.}"""
        ## Returns the current offset for index generation. The produced value might point to
        ## whitespace that must first be skipped before the desired element is reached but
        ## the nifreader will skip the whitespace automatically, so no harm is done.
        result = b._offs.copy()
        return result


with const:
    _MinCapacity = 64
    ## Also the reason `raw` is safe: a string this long is heap-allocated, so
    ## its payload address does not move when the Builder object does.


@hook("copy")
def _copyBuilder(dest: mut @ Builder, src: Builder):
    """{.error.}"""
    pass


# `beginStore`/`endStore` are the Nimony bulk-write API: resize without zeroing,
# then sync the SSO inline prefix cache. Host Nim has neither, so shim them
# privately (a `*`-exported shim would collide with `bif`'s copy in modules that
# import both).
if comptime(defined("nimony")):
    def _grabBuf(s: mut @ string, newLen: nint) -> ptr[UncheckedArray[char]]:
        """{.inline.}"""
        return beginStore(s, newLen, 0)

    def _syncBuf(s: mut @ string):
        """{.inline.}"""
        endStore(s)
else:
    def _grabBuf(s: mut @ string, newLen: nint) -> ptr[UncheckedArray[char]]:
        """{.inline.}"""
        s.setLen(newLen)
        return cast[ptr[UncheckedArray[char]]](addr(s[0]))

    def _syncBuf(s: mut @ string):
        """{.inline.}"""
        return

    def _readRawData(s: string) -> ptr[UncheckedArray[char]]:
        """{.inline.}"""
        if s.len == 0:
            return None
        else:
            return cast[ptr[UncheckedArray[char]]](addr(s[0]))


def _reserve(b: mut @ Builder, extra: nint):
    ## Make room for `extra` more bytes. Grows geometrically and re-acquires the
    ## cursor, which the resize may have invalidated.
    if b._offs + extra > b._cap:
        with var:
            newCap = max(b._cap * 2, _MinCapacity)
        while newCap < b._offs + extra: newCap = newCap * 2
        b._raw = _grabBuf(b._buffer, newCap)
        b._cap = newCap


def _finish(b: mut @ Builder):
    ## Cut the storage back to what was actually written and re-sync the SSO
    ## prefix cache, so `buffer` is a valid `string` again. Must run before
    ## anything reads `buffer` as a string (`extract`, `close`).
    b._buffer.setLen(b._offs)
    _syncBuf(b._buffer)
    b._cap = b._offs
    b._raw = None


@dispatch
def open(filename: string, compact = False, writeMode: FileWriteMode = FileWriteMode.AlwaysWrite) -> Builder:
    ## Opens a new builder attached to some output path. Writes are
    ## buffered in memory and flushed via `vfsWrite` at `close()`.
    ## With `writeMode = OnlyIfChanged` the close compares the buffered
    ## bytes to the existing file and skips the write (preserving mtime)
    ## when they match — useful for tools whose output should not bump
    ## downstream mtimes when nothing actually changed (e.g. nifler).
    result = Builder(_buffer=string(""), _mode=_Mode.UsesFile, _writeMode=writeMode,
                     _compact=compact, _filename=filename)
    _reserve(result, _MinCapacity)
    return result


@dispatch
def open(sizeHint: nint, compact = False) -> Builder:
    ## Opens a new builder with the intent to keep the produced
    ## code in memory. `sizeHint` bytes are reserved exactly, not rounded up to a
    ## power of two: a good estimate is what keeps a large module's text small.
    result = Builder(_buffer=string(""), _mode=_Mode.UsesMem, _compact=compact)
    with let:
        cap = max(sizeHint, _MinCapacity)
    result._raw = _grabBuf(result._buffer, cap)
    result._cap = cap
    return result


@ufcs(Builder)
def extract(b: sink @ Builder) -> string:
    ## Extracts the buffer from the builder.
    ## The builder should not be used afterwards.
    if comptime(not defined("showBroken")):
        assert b._nesting == 0, string("unpaired '(' or ')'") + str(b._nesting)
    assert b._mode == _Mode.UsesMem, "cannot extract from a file"
    _finish(b)
    result = move(b._buffer)
    return result


@dispatch
def close(b: mut @ Builder):
    if b._mode == _Mode.UsesFile:
        _finish(b)
        if b._writeMode == FileWriteMode.OnlyIfChanged and vfsExists(b._filename) and \
                vfsRead(b._filename) == b._buffer:
            pass
        else:
            vfsWrite(b._filename, b._buffer)
    if comptime(not defined("showBroken")):
        assert b._nesting == 0, "unpaired '(' or ')'"


@dispatch
def _put(b: mut @ Builder, s: string):
    with let:
        n = s.len
    if n > 0:
        _reserve(b, n)
        copyMem(cast[pointer](addr(b._raw[b._offs])), cast[pointer](_readRawData(s)), n)
        b._offs += n


@template
def _put(b: mut @ Builder, s: char):
    ## A TEMPLATE, not an `{.inline.}` proc: at ~5.7M calls per emitted module
    ## this is the most executed routine in the builder, and a call costs 28
    ## instructions around a body of three. Nothing here evaluates `b` in a way
    ## that repeating it could matter — every call site passes the builder
    ## variable itself.
    if b._offs >= b._cap: _reserve(b, 1)
    b._raw[b._offs] = s
    b._offs += 1


def _putPending(b: mut @ Builder, s: string):
    """{.inline.}"""
    _put(b, s)


with const:
    ControlChars = Tset[char](ch('('), ch(')'), ch('['), ch(']'), ch('{'), ch('}'), ch('~'), ch('#'), ch("'"), ch('"'), ch('\\'), ch(':'), ch('@'))


def _escape(b: mut @ Builder, c: char):
    with const:
        _HexChars = string("0123456789ABCDEF")
    with var:
        n = nint(c)
    _put(b, ch('\\'))
    _put(b, _HexChars[(n >> 4) & 0xF])
    _put(b, _HexChars[n & 0xF])


@ufcs(char)
@template
def _needsEscape(c: char) -> bool:
    return c < ch(' ') or c in ControlChars


def addRaw(b: mut @ Builder, s: string):
    _put(b, s)


def _addSep(b: mut @ Builder):
    ## Insert a token separator if the previous byte isn't already one. NIF27
    ## bare numbers (`123` instead of the legacy `+123`) carry no leading
    ## sign-byte to act as an implicit separator, so adjacent atoms at top
    ## level (e.g. `"foo"123u`) would otherwise glue together — emit a space
    ## even when nesting is zero.
    if b._offs == 0:
        pass
    elif b._raw[b._offs - 1] in Tset[char](ch('\n'), ch(' '), ch('('), ch(')')):
        _ = "no separator required"
    else:
        _put(b, ch(' '))


def addNumber(b: mut @ Builder, s: string):
    _addSep(b)
    _put(b, s)


#  ------------ Atoms ------------------------

def addIdent(b: mut @ Builder, s: string):
    _addSep(b)
    with let:
        sLen = s.len
    if sLen > 0:
        with let:
            src = _readRawData(s)
            c0 = src[0]
        if c0 < ch(' ') or c0 in Tset[char](ch('.'), inrange(ch('0'), ch('9')), ch('+'), ch('-'), ch('~')) or c0._needsEscape():
            _escape(b, c0)
        else:
            _put(b, c0)
        for i in range(1, sLen):
            with let:
                c = src[i]
            if c < ch(' ') or (c in (ControlChars + Tset[char](ch('.')))):
                _escape(b, c)
            else:
                _put(b, c)


def _addSymbolImpl(b: mut @ Builder, s: string, len: nint) -> nint:
    """{.inline.}"""
    ## Returns the number of dots in the symbol.
    result = nint(0)
    if s.len > 0:
        with let:
            src = _readRawData(s)
            c0 = src[0]
        if c0 in Tset[char](ch('.'), inrange(ch('0'), ch('9')), ch('+'), ch('-'), ch('~')) or c0._needsEscape():
            _escape(b, c0)
        else:
            _put(b, c0)
        for i in range(1, len):
            with let:
                c = src[i]
            # Symbols imported from C can have a space like "struct foo".
            if c == ch(' ') or c._needsEscape():
                _escape(b, c)
            else:
                if c == ch('.'): result += 1
                _put(b, c)
    return result


@dispatch
def addSymbol(b: mut @ Builder, s: string):
    _addSep(b)
    _ = _addSymbolImpl(b, s, s.len)


def addSymbolDef(b: mut @ Builder, s: string):
    _addSep(b)
    _put(b, ch(':'))
    _ = _addSymbolImpl(b, s, s.len)


@dispatch
def addSymbol(b: mut @ Builder, s: string, dottedSuffix: string):
    _addSep(b)
    with var:
        L = nint(s.len)
    if dottedSuffix.len > 0 and s.endsWith(dottedSuffix):
        L -= dottedSuffix.len
        L += 1
    _ = _addSymbolImpl(b, s, L)


def addSymbolDefRetIsGlobal(b: mut @ Builder, s: string, dottedSuffix = string("")) -> bool:
    ## Returns true if the symbol is global.
    _addSep(b)
    _put(b, ch(':'))
    with var:
        L = nint(s.len)
    if dottedSuffix.len > 0 and s.endsWith(dottedSuffix):
        L -= dottedSuffix.len
        L += 1
    result = _addSymbolImpl(b, s, L) >= 2
    return result


@dispatch
def addStrLit(b: mut @ Builder, s: string):
    _addSep(b)
    _put(b, ch('"'))
    for c in s:
        if _needsEscape(c):
            _escape(b, c)
        else:
            _put(b, c)
    _put(b, ch('"'))


def addEmpty(b: mut @ Builder, count = 1):
    _addSep(b)
    for i in inrange(1, count):
        _put(b, ch('.'))


def addCharLit(b: mut @ Builder, c: char):
    _addSep(b)
    _put(b, ch("'"))
    if c._needsEscape():
        _escape(b, c)
    else:
        _put(b, c)
    _put(b, ch("'"))


def addIntLit(b: mut @ Builder, i: int64):
    _addSep(b)
    _put(b, str(i))


@dispatch
def addUIntLit(b: mut @ Builder, u: uint64):
    _addSep(b)
    _put(b, str(u))
    _put(b, ch('u'))


def attachLineInfo(b: mut @ Builder, col: int32, line: int32, file = string("")):
    pass


def addFloatLit(b: mut @ Builder, f: float64, col: int32 = 0, line: int32 = 0, file = string("")):
    ## Emit a float literal. Special values (`inf`, `nan`, `neginf`) are emitted
    ## as compounds; for those, `(col, line, file)` if non-zero is attached as a
    ## suffix on the inner tag (the only place a NIF27 line-info suffix can go).
    ## For finite values the caller is expected to call `attachLineInfo`
    ## separately; the args here are honored as a convenience.
    _addSep(b)
    with let:
        hasInfo = col != 0 or line != 0 or file.len > 0
    match classify(f):
        case FloatClass.fcInf:
            _put(b, string("(inf"))
            if hasInfo: attachLineInfo(b, col, line, file)
            _put(b, ch(')'))
        case FloatClass.fcNan:
            _put(b, string("(nan"))
            if hasInfo: attachLineInfo(b, col, line, file)
            _put(b, ch(')'))
        case FloatClass.fcNegInf:
            _put(b, string("(neginf"))
            if hasInfo: attachLineInfo(b, col, line, file)
            _put(b, ch(')'))
        case FloatClass.fcNegZero:
            _put(b, string("-0.0"))
            if hasInfo: attachLineInfo(b, col, line, file)
        case FloatClass.fcNormal | FloatClass.fcSubnormal | FloatClass.fcZero:
            # Format into a scratch string: the builder's storage is capacity-sized, so
            # `addFloat` cannot append to it directly.
            with var:
                tmp = string("")
            tmp.addFloat(f)
            with let:
                myLen = b._offs.copy()
            _put(b, tmp)
            for i in range(myLen, b._offs):
                if b._raw[i] == ch('e'): b._raw[i] = ch('E')
            if hasInfo: attachLineInfo(b, col, line, file)


def _b62Char(d: nint) -> char:
    """{.inline.}"""
    if d < 10: return char(ord(ch('0')) + d)
    elif d < 36: return char(ord(ch('A')) + d - 10)
    else: return char(ord(ch('a')) + d - 36)


def _addB62Unsigned(b: mut @ Builder, n0: uint64):
    ## Emit `n0` as base62 digits (most-significant first). Always emits at
    ## least one digit (even for zero) so the line-info parser sees a non-empty
    ## diff segment.
    if n0 == 0:
        _put(b, ch('0'))
    else:
        with var:
            buf: pragma("noinit") @ array[12, char] = array[12, char]()  # 62^12 > 2^64
            i = nint(0)
            n = n0
        while n > u64(0):
            buf[i] = _b62Char(nint(n % u64(62)))
            n = n // u64(62)
            i += 1
        while i > 0:
            i -= 1
            _put(b, buf[i])


def _addLineDiff(b: mut @ Builder, x: int32, emitZero: bool):
    """{.inline.}"""
    ## Emit one base62 line-info diff. If `emitZero` is false and `x == 0`,
    ## emit nothing (the segment is implicitly zero between two commas).
    if x < 0:
        _put(b, ch('~'))
        _addB62Unsigned(b, uint64(-int64(x)))
    elif x > 0:
        _addB62Unsigned(b, uint64(x))
    elif emitZero:
        _put(b, ch('0'))


def attachLineInfo(b: mut @ Builder, col: int32, line: int32, file = string("")):
    ## Append a NIF27 line-information suffix to the most recently emitted atom
    ## or tag name. There must be no whitespace between the atom/tag and this
    ## call (do not call `addSep`, `addEmpty`, or any `add*Lit` between them).
    ## A no-op when all components are zero/empty.
    if col == 0 and line == 0 and file.len == 0:
        return
    b._drainPending()
    if col < 0:
        # Use the bare-`~` shorthand (no `@` introducer).
        _put(b, ch('~'))
        _addB62Unsigned(b, uint64(-int64(col)))
    else:
        _put(b, ch('@'))
        if col > 0:
            _addB62Unsigned(b, uint64(col))
        # else: empty first diff segment, allowed by `B62Digit*` in the grammar.
    if line != 0 or file.len > 0:
        _put(b, ch(','))
        _addLineDiff(b, line, emitZero=False)
    if file.len > 0:
        _put(b, ch(','))
        for c in file:
            if c._needsEscape():
                _escape(b, c)
            else:
                _put(b, c)


@template
def addLineInfo(b: mut @ Builder, col: int32, line: int32, file = string("")):
    ## Backwards-compatible alias for `attachLineInfo`. Callers must invoke
    ## this **after** the atom or tag whose info they want to record — there
    ## is no buffering, no "pending" state.
    attachLineInfo(b, col, line, file)


def attachComment(b: mut @ Builder, s: string):
    ## Append a NIF27 comment suffix `#<s>#` to the most recently emitted atom
    ## or tag name (or directly after a preceding `attachLineInfo`). No
    ## whitespace allowed before the `#`.
    b._drainPending()
    _put(b, ch('#'))
    for c in s:
        if c._needsEscape():
            _escape(b, c)
        else:
            _put(b, c)
    _put(b, ch('#'))


def addKeyw(b: mut @ Builder, keyw: string):
    ## Adds a complete compound node that has no children like `(nil)`.
    b._drainPending()
    _put(b, ch('('))
    _put(b, keyw)
    _put(b, ch(')'))


def addTree(b: mut @ Builder, kind: string):
    ## Starts a new compound node. Must be closed with `endTree`.
    ## See also `withTree`.
    ## `kind` is allowed to start with a dot. This emits a directive then.
    b._drainPending()
    if not b._compact:
        if b._nesting > 0:
            _put(b, string("\n"))
            for i in inrange(1, b._nesting): _put(b, ch(' '))
        _put(b, ch('('))
    else:
        _put(b, string("\n("))
    _put(b, kind)
    b._nesting += 1


def endTree(b: mut @ Builder):
    if comptime(not defined("showBroken")):
        assert b._nesting > 0, "generating ')' would produce a syntax error"
    if b._nesting >= 0:
        b._nesting -= 1
    b._undoWhitespace()
    _put(b, ch(')'))


@template
def withTree(b: mut @ Builder, kind: string, body: untyped = None):
    ## Convenience template that wraps `body` around `addTree` and `endTree`
    ## calls.
    addTree(b, kind)
    body
    endTree(b)


@dispatch
def addUIntLit(b: mut @ Builder, u: uint64, suffix: string,
               col: int32 = 0, line: int32 = 0, file = string("")):
    addTree(b, string("suf"))
    if col != 0 or line != 0 or file.len > 0:
        attachLineInfo(b, col, line, file)
    addUIntLit(b, u)
    addStrLit(b, suffix)
    endTree(b)


@dispatch
def addStrLit(b: mut @ Builder, s: string, suffix: string,
              col: int32 = 0, line: int32 = 0, file = string("")):
    addTree(b, string("suf"))
    if col != 0 or line != 0 or file.len > 0:
        attachLineInfo(b, col, line, file)
    addStrLit(b, s)
    addStrLit(b, suffix)
    endTree(b)


def addHeader(b: mut @ Builder, vendor = string(""), dialect = string("")):
    _put(b, string("(.nif27)\n"))
    if vendor.len > 0:
        _put(b, string("(.vendor "))
        addStrLit(b, vendor)
        _put(b, string(")\n"))
    if dialect.len > 0:
        _put(b, string("(.dialect "))
        addStrLit(b, dialect)
        _put(b, string(")\n"))


def addHeader27(b: mut @ Builder) -> nint:
    ## Returns the patch position for the indexat overwrite.
    _put(b, string("(.nif27)\n"))
    result = b._offs + len(string("(.indexat "))
    _put(b, string("(.indexat                  )\n"))
    #                 ^ whitespace essential here for patching without reallocations!
    return result


if comptime(__name__ == "__main__" and not defined("nimony")):
    def test(b: sink @ Builder):
        addHeader(b, string("tester"), string("niftest"))
        addTree(b, string("stmts"))
        attachLineInfo(b, 4, 5, string("mymodb.nim"))
        with block:
            addTree(b, string("call"))
            attachLineInfo(b, 1, 3, string("mymod.nim"))
            addSymbolDef(b, string("oh.0.my.god"))
            addSymbol(b, string("foo.3.mymod"))
            addIntLit(b, 3423)
            addFloatLit(b, 50.4)
            # issue #1313
            addFloatLit(b, -0.0)
            endTree(b)
        endTree(b)

        if b.attachedToFile():
            close(b)
        else:
            echo(b.extract())

    def main():
        #var b = open(10)
        #test b

        with var:
            b2 = open(string("builder_example.nif"))
        test(b2)

    main()


if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir")

    def addedTests():
        if vfsExists(string("builder_example.nif")):
            echo(vfsRead(string("builder_example.nif")))
            vfsRemove(string("builder_example.nif"))

        with var:
            bm = open(10)
        echo(bm.attachedToFile())
        addHeader(bm, string("v"), string("d"))
        with withTree(bm, string("stmts")):
            addLineInfo(bm, 1, 2, string("a.nim"))
            attachComment(bm, string("hello #1"))
            addRaw(bm, string(" "))
            addNumber(bm, string("42"))
            addIdent(bm, string("my_ident"))
            addIdent(bm, string("9bad.id"))
            addSymbol(bm, string("sym.1.mod"))
            addSymbol(bm, string("sym.1.mod"), string(".mod"))
            addSymbol(bm, string("struct foo.1.c"))
            addSymbolDef(bm, string("def.0.mod"))
            echo(addSymbolDefRetIsGlobal(bm, string("loc.0")))
            echo(addSymbolDefRetIsGlobal(bm, string("glob.0.mod")))
            echo(addSymbolDefRetIsGlobal(bm, string("glob.0.mod"), string(".mod")))
            addStrLit(bm, string("hi \"world\"\n"))
            addStrLit(bm, string("raw"), string("R"), 2, 3, string("s.nim"))
            addEmpty(bm, 2)
            addCharLit(bm, ch('x'))
            addCharLit(bm, ch('\n'))
            addIntLit(bm, i64(-12345))
            addUIntLit(bm, u64(999))
            addUIntLit(bm, u64(42), string("u8"), -3, -4, string("u.nim"))
            addKeyw(bm, string("nil"))
            addFloatLit(bm, 0.1)
            addFloatLit(bm, -1.5)
            addFloatLit(bm, 1e300)
            addFloatLit(bm, -0.0)
            addFloatLit(bm, 5e-324)
            addFloatLit(bm, Inf, 1, 1)
            addFloatLit(bm, -Inf, 0, -2)
            addFloatLit(bm, NaN)
        echo(extract(bm))

        with var:
            bc = open(16, compact=True)
        with let:
            patchPos = addHeader27(bc)
        with withTree(bc, string("top")):
            with withTree(bc, string("inner")):
                addIntLit(bc, i64(7))
        with let:
            idxOff = bc.offset()
        bc.patchIndexAt(patchPos, idxOff)
        echo(idxOff)
        echo(extract(bc))

        with let:
            tmpFile = getTempDir() + string("nimic_nifbuilder_test.nif")
        if vfsExists(tmpFile):
            vfsRemove(tmpFile)
        with var:
            bf1 = open(tmpFile, compact=False, writeMode=FileWriteMode.OnlyIfChanged)
        echo(bf1.attachedToFile())
        with withTree(bf1, string("filetest")):
            addIntLit(bf1, i64(100))
        close(bf1)
        echo(vfsRead(tmpFile))
        with let:
            mtime1 = vfsMtime(tmpFile)
        with var:
            bf2 = open(tmpFile, compact=False, writeMode=FileWriteMode.OnlyIfChanged)
        with withTree(bf2, string("filetest")):
            addIntLit(bf2, i64(100))
        close(bf2)
        with let:
            mtime2 = vfsMtime(tmpFile)
        echo(mtime1 == mtime2)
        vfsRemove(tmpFile)

    addedTests()
