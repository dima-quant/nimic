# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifbuilder.nim
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

from nimic.std.assertions import *
from nimic.std.syncio import *
from nimic.std.formatfloat import *
from nimic.std.math import *
importFrom("nimic.std.strutils", "endsWith")
from .vfs import *
from . import vfs
with export:
    vfs.FileWriteMode


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


with const:
    _MinCapacity = 64
    ## Also the reason `raw` is safe: a string this long is heap-allocated, so
    ## its payload address does not move when the Builder object does.


@hook("copy")
def _copy(dest: mut @ Builder, src: Builder):
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
    b._cap = b._offs.copy()
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


def attachedToFile(b: Builder) -> bool:
    """{.inline.}"""
    return b._mode == _Mode.UsesFile


def extract(b: sink @ Builder) -> string:
    ## Extracts the buffer from the builder.
    ## The builder should not be used afterwards.
    if comptime(not defined("showBroken")):
        assert b._nesting == 0, string("unpaired '(' or ')'") + str(b._nesting)
    assert b._mode == _Mode.UsesMem, "cannot extract from a file"
    _finish(b)
    result = move(b._buffer)
    return result


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


def _drainPending(b: mut @ Builder):
    ## No-op kept for source compatibility; both modes now buffer in
    ## memory until `close`.
    return


def _undoWhitespace(b: mut @ Builder):
    with var:
        i = b._offs - 1
    while i >= 0 and b._raw[i] in Tset[char](char(' '), char('\n')):
        i -= 1
    b._offs = i + 1


with const:
    ControlChars = Tset[char](char('('), char(')'), char('['), char(']'), char('{'), char('}'), char('~'), char('#'), char("'"), char('"'), char('\\'), char(':'), char('@'))


def _escape(b: mut @ Builder, c: char):
    with const:
        _HexChars = string("0123456789ABCDEF")
    with var:
        n = nint(c)
    b._put(char('\\'))
    b._put(_HexChars[(n >> 4) & 0xF])
    b._put(_HexChars[n & 0xF])


@ufcs(char)
@template
def _needsEscape(c: char) -> bool:
    return c < char(' ') or c in ControlChars


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
    elif b._raw[b._offs - 1] in Tset[char](char('\n'), char(' '), char('('), char(')')):
        _ = string("no separator required")
    else:
        b._put(char(' '))


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
        if c0 < char(' ') or c0 in Tset[char](char('.'), inrange(char('0'), char('9')), char('+'), char('-'), char('~')) or c0._needsEscape():
            b._escape(c0)
        else:
            b._put(c0)
        for i in range(1, sLen):
            with let:
                c = src[i]
            if c < char(' ') or (c in (ControlChars + Tset[char](char('.')))):
                b._escape(c)
            else:
                b._put(c)


def _addSymbolImpl(b: mut @ Builder, s: string, len: nint) -> nint:
    """{.inline.}"""
    ## Returns the number of dots in the symbol.
    result = nint(0)
    if s.len > 0:
        with let:
            src = _readRawData(s)
            c0 = src[0]
        if c0 in Tset[char](char('.'), inrange(char('0'), char('9')), char('+'), char('-'), char('~')) or c0._needsEscape():
            b._escape(c0)
        else:
            b._put(c0)
        for i in range(1, len):
            with let:
                c = src[i]
            # Symbols imported from C can have a space like "struct foo".
            if c == char(' ') or c._needsEscape():
                b._escape(c)
            else:
                if c == char('.'): result += 1
                b._put(c)
    return result


@dispatch
def addSymbol(b: mut @ Builder, s: string):
    _addSep(b)
    _ = _addSymbolImpl(b, s, s.len)


def addSymbolDef(b: mut @ Builder, s: string):
    _addSep(b)
    b._put(char(':'))
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
    b._put(char(':'))
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
    b._put(char('"'))
    for c in s:
        if _needsEscape(c):
            b._escape(c)
        else:
            b._put(c)
    b._put(char('"'))


def addEmpty(b: mut @ Builder, count = 1):
    _addSep(b)
    for i in inrange(1, count):
        b._put(char('.'))


def addCharLit(b: mut @ Builder, c: char):
    _addSep(b)
    b._put(char("'"))
    if c._needsEscape():
        _escape(b, c)
    else:
        b._put(c)
    b._put(char("'"))


def addIntLit(b: mut @ Builder, i: int64):
    _addSep(b)
    b._put(str(i))


@dispatch
def addUIntLit(b: mut @ Builder, u: uint64):
    _addSep(b)
    b._put(str(u))
    b._put(char('u'))


def attachLineInfo(b: mut @ Builder, col: int32, line: int32, file = string("")):
    pass


def addFloatLit(b: mut @ Builder, f: float, col: int32 = 0, line: int32 = 0, file = string("")):
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
            b._put(string("(inf"))
            if hasInfo: b.attachLineInfo(col, line, file)
            b._put(char(')'))
        case FloatClass.fcNan:
            b._put(string("(nan"))
            if hasInfo: b.attachLineInfo(col, line, file)
            b._put(char(')'))
        case FloatClass.fcNegInf:
            b._put(string("(neginf"))
            if hasInfo: b.attachLineInfo(col, line, file)
            b._put(char(')'))
        case FloatClass.fcNegZero:
            b._put(string("-0.0"))
            if hasInfo: b.attachLineInfo(col, line, file)
        case FloatClass.fcNormal | FloatClass.fcSubnormal | FloatClass.fcZero:
            # Format into a scratch string: the builder's storage is capacity-sized, so
            # `addFloat` cannot append to it directly.
            with var:
                tmp = string("")
            tmp.addFloat(f)
            with let:
                myLen = b._offs.copy()
            b._put(tmp)
            for i in range(myLen, b._offs):
                if b._raw[i] == char('e'): b._raw[i] = char('E')
            if hasInfo: b.attachLineInfo(col, line, file)


def _b62Char(d: nint) -> char:
    """{.inline.}"""
    if d < 10: return char(ord(char('0')) + d)
    elif d < 36: return char(ord(char('A')) + d - 10)
    else: return char(ord(char('a')) + d - 36)


def _addB62Unsigned(b: mut @ Builder, n0: uint64):
    ## Emit `n0` as base62 digits (most-significant first). Always emits at
    ## least one digit (even for zero) so the line-info parser sees a non-empty
    ## diff segment.
    if n0 == 0:
        b._put(char('0'))
    else:
        with var:
            buf: pragma("noinit") @ array[12, char] = array[12, char]()  # 62^12 > 2^64
            i = nint(0)
            n = n0.copy()
        while n > u64(0):
            buf[i] = _b62Char(nint(n % u64(62)))
            n = n // u64(62)
            i += 1
        while i > 0:
            i -= 1
            b._put(buf[i])


def _addLineDiff(b: mut @ Builder, x: int32, emitZero: bool):
    """{.inline.}"""
    ## Emit one base62 line-info diff. If `emitZero` is false and `x == 0`,
    ## emit nothing (the segment is implicitly zero between two commas).
    if x < 0:
        b._put(char('~'))
        b._addB62Unsigned(uint64(-int64(x)))
    elif x > 0:
        b._addB62Unsigned(uint64(x))
    elif emitZero:
        b._put(char('0'))


def attachLineInfo(b: mut @ Builder, col: int32, line: int32, file = string("")):
    ## Append a NIF27 line-information suffix to the most recently emitted atom
    ## or tag name. There must be no whitespace between the atom/tag and this
    ## call (do not call `addSep`, `addEmpty`, or any `add*Lit` between them).
    ## A no-op when all components are zero/empty.
    if col == 0 and line == 0 and file.len == 0:
        return
    _drainPending(b)
    if col < 0:
        # Use the bare-`~` shorthand (no `@` introducer).
        b._put(char('~'))
        b._addB62Unsigned(uint64(-int64(col)))
    else:
        b._put(char('@'))
        if col > 0:
            b._addB62Unsigned(uint64(col))
        # else: empty first diff segment, allowed by `B62Digit*` in the grammar.
    if line != 0 or file.len > 0:
        b._put(char(','))
        b._addLineDiff(line, emitZero=False)
    if file.len > 0:
        b._put(char(','))
        for c in file:
            if c._needsEscape():
                b._escape(c)
            else:
                b._put(c)


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
    _drainPending(b)
    b._put(char('#'))
    for c in s:
        if c._needsEscape():
            b._escape(c)
        else:
            b._put(c)
    b._put(char('#'))


def addKeyw(b: mut @ Builder, keyw: string):
    ## Adds a complete compound node that has no children like `(nil)`.
    _drainPending(b)
    b._put(char('('))
    b._put(keyw)
    b._put(char(')'))


def addTree(b: mut @ Builder, kind: string):
    ## Starts a new compound node. Must be closed with `endTree`.
    ## See also `withTree`.
    ## `kind` is allowed to start with a dot. This emits a directive then.
    _drainPending(b)
    if not b._compact:
        if b._nesting > 0:
            b._put(string("\n"))
            for i in inrange(1, b._nesting): b._put(char(' '))
        b._put(char('('))
    else:
        b._put(string("\n("))
    b._put(kind)
    b._nesting += 1


def endTree(b: mut @ Builder):
    if comptime(not defined("showBroken")):
        assert b._nesting > 0, "generating ')' would produce a syntax error"
    if b._nesting >= 0:
        b._nesting -= 1
    _undoWhitespace(b)
    b._put(char(')'))


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
    b.addTree(string("suf"))
    if col != 0 or line != 0 or file.len > 0:
        b.attachLineInfo(col, line, file)
    b.addUIntLit(u)
    b.addStrLit(suffix)
    b.endTree()


@dispatch
def addStrLit(b: mut @ Builder, s: string, suffix: string,
              col: int32 = 0, line: int32 = 0, file = string("")):
    b.addTree(string("suf"))
    if col != 0 or line != 0 or file.len > 0:
        b.attachLineInfo(col, line, file)
    b.addStrLit(s)
    b.addStrLit(suffix)
    b.endTree()


def addHeader(b: mut @ Builder, vendor = string(""), dialect = string("")):
    b._put(string("(.nif27)\n"))
    if vendor.len > 0:
        b._put(string("(.vendor "))
        b.addStrLit(vendor)
        b._put(string(")\n"))
    if dialect.len > 0:
        b._put(string("(.dialect "))
        b.addStrLit(dialect)
        b._put(string(")\n"))


def addHeader27(b: mut @ Builder) -> nint:
    ## Returns the patch position for the indexat overwrite.
    b._put(string("(.nif27)\n"))
    result = b._offs + len(string("(.indexat "))
    b._put(string("(.indexat                  )\n"))
    #                 ^ whitespace essential here for patching without reallocations!
    return result


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


if comptime(__name__ == "__main__" and not defined("nimony")):
    def _test(b: sink @ Builder):
        b.addHeader(string("tester"), string("niftest"))
        b.addTree(string("stmts"))
        b.attachLineInfo(4, 5, string("mymodb.nim"))
        with block:
            b.addTree(string("call"))
            b.attachLineInfo(1, 3, string("mymod.nim"))
            b.addSymbolDef(string("oh.0.my.god"))
            b.addSymbol(string("foo.3.mymod"))
            b.addIntLit(3423)
            b.addFloatLit(50.4)
            # issue #1313
            b.addFloatLit(-0.0)
            b.endTree()
        b.endTree()

        if b.attachedToFile():
            b.close()
        else:
            echo(b.extract())

    def _main():
        #var b = open(10)
        #test b

        with var:
            b2 = open(string("builder_example.nif"))
        _test(b2)

    _main()


if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir")

    def _addedTests():
        if vfsExists(string("builder_example.nif")):
            echo(vfsRead(string("builder_example.nif")))
            vfsRemove(string("builder_example.nif"))

        with var:
            bm = open(10)
        echo(bm.attachedToFile())
        bm.addHeader(string("v"), string("d"))
        with bm.withTree(string("stmts")):
            bm.addLineInfo(1, 2, string("a.nim"))
            bm.attachComment(string("hello #1"))
            bm.addRaw(string(" "))
            bm.addNumber(string("42"))
            bm.addIdent(string("my_ident"))
            bm.addIdent(string("9bad.id"))
            bm.addSymbol(string("sym.1.mod"))
            bm.addSymbol(string("sym.1.mod"), string(".mod"))
            bm.addSymbol(string("struct foo.1.c"))
            bm.addSymbolDef(string("def.0.mod"))
            echo(bm.addSymbolDefRetIsGlobal(string("loc.0")))
            echo(bm.addSymbolDefRetIsGlobal(string("glob.0.mod")))
            echo(bm.addSymbolDefRetIsGlobal(string("glob.0.mod"), string(".mod")))
            bm.addStrLit(string("hi \"world\"\n"))
            bm.addStrLit(string("raw"), string("R"), 2, 3, string("s.nim"))
            bm.addEmpty(2)
            bm.addCharLit(char('x'))
            bm.addCharLit(char('\n'))
            bm.addIntLit(i64(-12345))
            bm.addUIntLit(u64(999))
            bm.addUIntLit(u64(42), string("u8"), -3, -4, string("u.nim"))
            bm.addKeyw(string("nil"))
            bm.addFloatLit(0.1)
            bm.addFloatLit(-1.5)
            bm.addFloatLit(1e300)
            bm.addFloatLit(-0.0)
            bm.addFloatLit(5e-324)
            bm.addFloatLit(Inf, 1, 1)
            bm.addFloatLit(-Inf, 0, -2)
            bm.addFloatLit(NaN)
        echo(bm.extract())

        with var:
            bc = open(16, compact=True)
        with let:
            patchPos = bc.addHeader27()
        with bc.withTree(string("top")):
            with bc.withTree(string("inner")):
                bc.addIntLit(i64(7))
        with let:
            idxOff = bc.offset()
        bc.patchIndexAt(patchPos, idxOff)
        echo(idxOff)
        echo(bc.extract())

        with let:
            tmpFile = getTempDir() + string("nimic_nifbuilder_test.nif")
        if vfsExists(tmpFile):
            vfsRemove(tmpFile)
        with var:
            bf1 = open(tmpFile, compact=False, writeMode=FileWriteMode.OnlyIfChanged)
        echo(bf1.attachedToFile())
        with bf1.withTree(string("filetest")):
            bf1.addIntLit(i64(100))
        bf1.close()
        echo(vfsRead(tmpFile))
        with let:
            mtime1 = vfsMtime(tmpFile)
        with var:
            bf2 = open(tmpFile, compact=False, writeMode=FileWriteMode.OnlyIfChanged)
        with bf2.withTree(string("filetest")):
            bf2.addIntLit(i64(100))
        bf2.close()
        with let:
            mtime2 = vfsMtime(tmpFile)
        echo(mtime1 == mtime2)
        vfsRemove(tmpFile)

    _addedTests()
