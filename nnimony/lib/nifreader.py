# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifreader.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## High performance ("zero copies") NIF file reader.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.memfiles import *
from nimic.std.parseutils import *
from nimic.std import parseutils
from nimic.std.assertions import *
from .stringviews import *
from .vfs import *
from .nifcore import *  # the ONE token-kind enum, shared with the binary token model

with export:
    NifKind

with const:
    StringLit = NifKind.StrLit
    ## The reader's traditional name for the string-literal token kind.
if comptime(defined("nimony")):
    from nimic.std.syncio import *

    pragma('feature: "lenientnils"')

with const:
    _ControlChars = Tset(
        char("("),
        char(")"),
        char("["),
        char("]"),
        char("{"),
        char("}"),
        char("~"),
        char("#"),
        char("'"),
        char('"'),
        char(":"),
        char("@"),
    )
    _ControlCharsOrWhite = _ControlChars + Tset(
        char(" "), char("\n"), char("\t"), char("\r")
    )
    _HexChars = Tset(
        inrange(char("0"), char("9")), inrange(char("A"), char("F"))
    )  # lowercase letters are not in the NIF spec!
    _Digits = Tset(inrange(char("0"), char("9")))
    _B62Digits = Tset(
        inrange(char("0"), char("9")),
        inrange(char("A"), char("Z")),
        inrange(char("a"), char("z")),
    )


class FilePos(Object):
    col: int32
    line: int32


class SymbolPart(NIntEnum):
    """Which component of a split symbol an `ExtendedSuffix` token carries.
    A NIF symbol is `<name>.<disamb>[.<dedup>].<module>` (`<module>` is
    absent for a local symbol), so these are exactly the fields of the
    symbol object the compiler wants instead of a string."""

    SymDisamb = auto()  ## the `12` of `abc.12.Ikey.mod`
    SymDedup = (
        auto()
    )  ## the `Ikey`: the key a generic instantiation is deduplicated by
    SymModule = auto()  ## the `mod`: the module suffix


class _TokenFlag(NIntEnum):
    TokenHasEscapes = auto()
    FilenameHasEscapes = auto()
    TokenHasModuleSuffixExpansion = auto()
    CommentHasEscapes = auto()


class ExpandedToken(Object):
    tk: NifKind
    _flags: Tset[_TokenFlag]
    part: SymbolPart  ## for `ExtendedSuffix`: which component of the preceding symbol this is
    suffixes: uint8  ## for `Symbol`/`SymbolDef`: how many `ExtendedSuffix` tokens follow
    kind: uint16  # for clients to fill in ("known node kinds")
    data: StringView
    pos: FilePos
    filename: StringView
    comment: StringView  ## raw bytes between '#' and '#'; empty if absent

    def __str__(t: ExpandedToken) -> string:
        result = default(string)
        match t.tk:
            case NifKind.UnknownToken:
                result = string("<unknown token>")
            case NifKind.EofToken:
                result = string("<eof>")
            case NifKind.ParLe:
                result = string("(") + str(t.data)
            case NifKind.ParRi:
                result = string(")")
            case NifKind.DotToken:
                result = string(".")
            case (
                NifKind.Ident
                | NifKind.Symbol
                | NifKind.SymbolDef
                | NifKind.StrLit
                | NifKind.CharLit
                | NifKind.IntLit
                | NifKind.UIntLit
                | NifKind.FloatLit
            ):
                result = string(str(t.tk)) + string(":") + str(t.data)
            case NifKind.ExtendedSuffix:
                # a symbol component, in split mode; see `splitSymbols`
                result = string(str(t.part)) + string(":") + str(t.data)
            case NifKind.TagLit | NifKind.LineInfoLit:
                # binary-only kinds; the textual reader never produces them
                result = string("<") + str(t.tk) + string(">")
        return result


class Reader(Object):
    _p: pchar
    _eof: pointer  # so that <= uses the correct comparison, not the cstring crap
    _f: VfsBlob
    _buf: string
    thisModule: string
    line: int32  # file position within the NIF file, not affected by line annotations
    _indexAt: nint  # position of the index
    _unusedNameHint: ExpandedToken
    _splitSyms: bool
    # The components of the symbol that was returned last, minus its name, and
    # minus the components already handed out. `pendingTotal` is what the head
    # token announced in `suffixes`; `pendingLeft` counts down to zero.
    _pending: StringView
    _pendingLeft: int32
    _pendingTotal: int32
    _pendingFlags: Tset[_TokenFlag]
    _pendingHasDisamb: bool
    _pendingHasModule: bool
    # The optional line-based syntax (see `open`). `depth` counts the open `(`
    # of the current top-level node; `inLineNode` is true while that node is a
    # `LineNode`, whose `)` is the newline that ends it.
    _lineBased: bool
    _inLineNode: bool
    _depth: int32


@template
def _inc(p: pchar, diff=1):
    p = cast[pchar](cast[intp](p) + diff)


@operator("+!")
@template
def _plus_bang(p: pchar, diff: nint) -> pchar:
    return cast[pchar](cast[intp](p) + diff)


@operator("-!")
@template
def _minus_bang(a: pchar, b: pchar) -> nint:
    return cast[intp](a) - cast[intp](b)


@operator("^")
@template
def _deref(p: pchar) -> char:
    return p[0]


if comptime(not defined("nimony")):

    @ufcs(string)
    def readRawData(s: string) -> ptr[UncheckedArray[char]]:
        """{.inline.}"""
        assert len(s) > 0
        return cast[ptr[UncheckedArray[char]]](addr(s[0]))

    def readRawDataStable(s: mut @ string, start=0) -> ptr[UncheckedArray[char]]:
        """{.inline.}
        ## Nim strings are always heap-backed, so the data pointer is already stable
        ## across moves — no SSO promotion needed; this is just `readRawData`."""
        if len(s) == 0:
            return nil
        else:
            return cast[ptr[UncheckedArray[char]]](addr(s[start]))


def close(r: mut @ Reader):
    """Release the backend's read handle (mmap unmap, LMDB read txn
    close, …) via the explicit VfsBlob close API."""
    r._f.closeBlob()


if comptime(not defined("nimony")):
    pragma("pragma: untyped")


@template
def _useCpuRegisters(body: untyped):
    """{.untyped.}"""
    with var:
        p: pragma("inject") = (
            r._p
        )  # encourage the code generator to use a register for this.
    with let:
        eof: pragma("inject") = r._eof
    body
    r._p = p  # store back


@template_expand
def _skipWhitespace(r: mut @ Reader):
    with _useCpuRegisters():
        while p < eof:
            match _deref(p):
                case _ if (
                    _deref(p) == char(" ")
                    or _deref(p) == char("\t")
                    or _deref(p) == char("\r")
                ):
                    _inc(p)
                case _ if _deref(p) == char("\n"):
                    _inc(p)
                    r.line += 1
                case _:
                    break


@template_expand
def _captureComment(r: mut @ Reader, result: mut @ ExpandedToken):
    """{.inline.}
    ## Consume the bytes up to (and including) the closing `#` and record the
    ## inner span on `result.comment`. Tracks the `CommentHasEscapes` flag so
    ## downstream decoders can take the fast path when no escapes were present."""
    result.comment.p = r._p
    with _useCpuRegisters():
        with let:
            start = p
        while p < eof:
            if _deref(p) == char("#"):
                result.comment.len = cast[intp](p) - cast[intp](start)
                _inc(p)
                break
            elif _deref(p) == char("\n"):
                _inc(p)
                r.line += 1
            else:
                if _deref(p) == char("\\"):
                    result._flags.incl(_TokenFlag.CommentHasEscapes)
                _inc(p)


def _handleHex(p: pchar) -> char:
    result = default(char)
    with var:
        output = 0
    match p[0]:
        case _ if p[0] in inrange(char("0"), char("9")):
            output = (output << 4) | (ord(p[0]) - ord(char("0")))
        case _ if p[0] in inrange(char("A"), char("F")):
            output = (output << 4) | (ord(p[0]) - ord(char("A")) + 10)
        case _:
            pass
    match p[1]:
        case _ if p[1] in inrange(char("0"), char("9")):
            output = (output << 4) | (ord(p[1]) - ord(char("0")))
        case _ if p[1] in inrange(char("A"), char("F")):
            output = (output << 4) | (ord(p[1]) - ord(char("A")) + 10)
        case _:
            pass
    result = char(output)
    return result


@template_expand
def _decodeEscape(p: mut @ pchar) -> char:
    """{.inline.}
    ## Decode a single NIF27 escape body. Caller has already advanced past the
    ## leading `\\`. On return, `p` points just past the escape (advanced by 1
    ## for a shortcut, 2 for a hex pair). The shortcut bodies (`n`, `t`, `r`,
    ## `|`, `^`) are deliberately chosen so that none of them is a hex digit
    ## or a NIF control character, which lets a one-byte look-ahead pick the
    ## form unambiguously."""
    result = default(char)
    match _deref(p):
        case _ if _deref(p) == char("n"):
            result = char("\x0a")
            _inc(p)
        case _ if _deref(p) == char("t"):
            result = char("\x09")
            _inc(p)
        case _ if _deref(p) == char("r"):
            result = char("\x0d")
            _inc(p)
        case _ if _deref(p) == char("|"):
            result = char("\x5c")
            _inc(p)
        case _ if _deref(p) == char("^"):
            result = char("\x22")
            _inc(p)
        case _:
            result = _handleHex(p)
            _inc(p, 2)
    return result


@template_expand
def decodeChar(t: ExpandedToken) -> char:
    result = default(char)
    assert t.tk == NifKind.CharLit
    result = _deref(t.data.p)
    if result == char("\\"):
        with var:
            p = t.data.p
        _inc(p)
        result = _decodeEscape(p)
    return result


@ufcs(Reader)
@template_expand
def decodeStr(r: Reader, t: ExpandedToken) -> string:
    result = default(string)
    if _TokenFlag.TokenHasEscapes in t._flags:
        result = string("")
        with var:
            p = t.data.p
        with let:
            sentinel = _plus_bang(p, t.data.len)
        while p < sentinel:
            if _deref(p) == char("\\"):
                _inc(p)
                result.add(_decodeEscape(p))
            else:
                result.add(_deref(p))
                _inc(p)
        # Handle module suffix expansion after decoding escapes
        if _TokenFlag.TokenHasModuleSuffixExpansion in t._flags:
            assert len(r.thisModule) > 0
            result.add(r.thisModule)
    elif _TokenFlag.TokenHasModuleSuffixExpansion in t._flags:
        assert len(r.thisModule) > 0
        result = newString(t.data.len + len(r.thisModule))
        if t.data.len > 0:
            copyMem(beginStore(result, len(result)), t.data.p, t.data.len)
        # The module suffix is copied even when there is nothing before it: in the
        # reader's split-symbol mode the expanding component is the module and
        # nothing else, so its `data` is empty.
        copyMem(
            beginStore(result, len(result), t.data.len),
            r.thisModule.readRawData(),
            len(r.thisModule),
        )
        endStore(result)
    else:
        result = newString(t.data.len)
        if t.data.len > 0:
            copyMem(beginStore(result, len(result)), t.data.p, t.data.len)
            endStore(result)
    return result


def needsDecoding(t: ExpandedToken) -> bool:
    """{.inline.}
    ## Whether `decodeStr` would do anything but copy `t.data`: an escape to
    ## expand, or a module suffix to append. When it is false the bytes ARE the
    ## value, so a client that interns them (`getOrInclFromView`) can skip
    ## building a string at all."""
    return (
        _TokenFlag.TokenHasEscapes in t._flags
        or _TokenFlag.TokenHasModuleSuffixExpansion in t._flags
    )


@template_expand
def decodeComment(t: ExpandedToken) -> string:
    """Decode the captured `#…#` comment, expanding `\\HH` escapes. Returns "" if
    no comment is attached."""
    result = default(string)
    if t.comment.len == 0:
        return string("")
    if _TokenFlag.CommentHasEscapes not in t._flags:
        result = newString(t.comment.len)
        copyMem(beginStore(result, len(result)), t.comment.p, t.comment.len)
        endStore(result)
        return result
    result = string("")
    with var:
        p = t.comment.p
    with let:
        sentinel = _plus_bang(p, t.comment.len)
    while p < sentinel:
        if _deref(p) == char("\\"):
            _inc(p)
            result.add(_decodeEscape(p))
        else:
            result.add(_deref(p))
            _inc(p)
    return result


@template_expand
def decodeFilename(t: ExpandedToken) -> string:
    result = default(string)
    if _TokenFlag.FilenameHasEscapes in t._flags:
        result = string("")
        with var:
            p = t.filename.p
        with let:
            sentinel = _plus_bang(p, t.filename.len)
        while p < sentinel:
            if _deref(p) == char("\\"):
                _inc(p)
                result.add(_decodeEscape(p))
            else:
                result.add(_deref(p))
                _inc(p)
    else:
        result = newString(t.filename.len)
        copyMem(beginStore(result, len(result)), t.filename.p, t.filename.len)
        endStore(result)
    return result


def decodeFloat(t: ExpandedToken) -> BiggestFloat:
    result = default(BiggestFloat)
    result = BiggestFloat(0.0)
    assert t.tk == NifKind.FloatLit
    with let:
        res = parseutils.parseBiggestFloat(
            toOpenArray(t.data.p, 0, t.data.len - 1), result
        )
    assert res == t.data.len
    return result


def decodeUInt(t: ExpandedToken) -> BiggestUInt:
    result = default(BiggestUInt)
    result = BiggestUInt(0)
    assert t.tk == NifKind.UIntLit
    with let:
        res = parseutils.parseBiggestUInt(
            toOpenArray(t.data.p, 0, t.data.len - 1), result
        )
    assert res == t.data.len
    return result


def decodeInt(t: ExpandedToken) -> BiggestInt:
    result = default(BiggestInt)
    result = BiggestInt(0)
    assert t.tk == NifKind.IntLit
    with let:
        res = parseutils.parseBiggestInt(
            toOpenArray(t.data.p, 0, t.data.len - 1), result
        )
    assert res == t.data.len
    return result


def decodeDisamb(t: ExpandedToken) -> nint:
    """The value of a `SymDisamb` component: `abc.12.mod` gives 12. Only the
    leading digits are read (a well-formed symbol has nothing else there)."""
    result = default(nint)
    assert t.tk == NifKind.ExtendedSuffix and t.part == SymbolPart.SymDisamb
    result = 0
    with var:
        i = 0
    while i < t.data.len and t.data[i] in _Digits:
        result = result * 10 + (ord(t.data[i]) - ord(char("0")))
        i += 1
    return result


@template_expand
def _handleNumber(r: mut @ Reader, result: mut @ ExpandedToken):
    with _useCpuRegisters():
        if p < eof and _deref(p) in _Digits:
            result.tk = NifKind.IntLit  # overwritten if we detect a float or unsigned
            while p < eof and _deref(p) in _Digits:
                _inc(p)
                result.data.len += 1

            if p < eof and _deref(p) == char("."):
                result.tk = NifKind.FloatLit
                _inc(p)
                result.data.len += 1
                while p < eof and _deref(p) in _Digits:
                    _inc(p)
                    result.data.len += 1

            if p < eof and _deref(p) == char("E"):
                result.tk = NifKind.FloatLit
                _inc(p)
                result.data.len += 1
                if p < eof:
                    if _deref(p) == char("-") or _deref(p) == char("+"):
                        _inc(p)
                        result.data.len += 1
                while p < eof and _deref(p) in _Digits:
                    _inc(p)
                    result.data.len += 1

            if p < eof and _deref(p) == char("u"):
                result.tk = NifKind.UIntLit
                _inc(p)
                # ignore the suffix 'u'


def _decodeB62(c: char) -> nint:
    """{.inline.}
    ## Decode a single base62 digit (0-9, A-Z, a-z) to its numeric value 0..61.
    ## Caller must guarantee `c` is in `B62Digits`."""
    result = default(nint)
    if c <= char("9"):
        result = ord(c) - ord(char("0"))
    elif c <= char("Z"):
        result = ord(c) - ord(char("A")) + 10
    else:
        result = ord(c) - ord(char("a")) + 36
    return result


@template_expand
def _handleLineInfo(r: mut @ Reader, result: mut @ ExpandedToken):
    """Parse the body of a line-info suffix. The leading `@`, if any, has already
    been consumed by the caller; a leading `~` (negative-first shorthand) has
    **not** been consumed."""

    def integerOutOfRangeError():
        """{.noinline, noreturn.}"""
        quit("Parsed integer outside of valid range")

    with _useCpuRegisters():
        with var:
            col = 0
        with var:
            negative = False
        if p < eof and _deref(p) == char("~"):
            _inc(p)
            negative = True
        while p < eof and _deref(p) in _B62Digits:
            with let:
                c = _decodeB62(_deref(p))
            if col >= (low(nint) + c) // 62:
                col = col * 62 - c
            else:
                integerOutOfRangeError()
            _inc(p)
        if not negative:
            if col == low(nint):
                integerOutOfRangeError()
            col = -col

        with var:
            line = 0
        negative = False

        if p < eof and _deref(p) == char(","):
            _inc(p)
            if p < eof and _deref(p) == char("~"):
                _inc(p)
                negative = True
            while p < eof and _deref(p) in _B62Digits:
                with let:
                    c = _decodeB62(_deref(p))
                if line >= (low(nint) + c) // 62:
                    line = line * 62 - c
                else:
                    integerOutOfRangeError()
                _inc(p)
            if not negative:
                if line == low(nint):
                    integerOutOfRangeError()
                line = -line

        result.pos = FilePos(col=int32(col), line=int32(line))

        if p < eof and _deref(p) == char(","):
            _inc(p)
            result.filename.p = p
            while p < eof:
                with let:
                    ch = _deref(p)
                if ch in _ControlCharsOrWhite:
                    break
                elif ch == char("\\"):
                    result._flags.incl(_TokenFlag.FilenameHasEscapes)
                elif ch == char("\n"):
                    r.line += 1
                result.filename.len += 1
                _inc(p)


@template_expand
def _handleSuffix(r: mut @ Reader, result: mut @ ExpandedToken):
    """{.inline.}
    ## After consuming an atom or a tag name, parse the optional postfix
    ## `@<info>` (or `~<neg-info>` shorthand) followed by an optional `#comment#`.
    ## No whitespace is allowed between the atom/tag and the suffix introducer,
    ## nor between the line info and the comment."""
    if r._p < r._eof:
        with let:
            ch = _deref(r._p)
        if ch == char("@"):
            _inc(r._p)
            _handleLineInfo(r, result)
        elif ch == char("~"):
            _handleLineInfo(r, result)
    if r._p < r._eof and _deref(r._p) == char("#"):
        _inc(r._p)  # consume the opening '#'
        _captureComment(r, result)  # consumes through the closing '#'


@ufcs(Reader)
def splitSymbols(r: mut @ Reader, enable=True):
    """{.inline.}
    ## Turn the split-symbol parsing mode on or off (default: off).
    ##
    ## A NIF symbol is not a string but an object: `<name>.<disamb>.<module>`,
    ## or `<name>.<disamb>.<dedup>.<module>` for a generic instantiation, or
    ## just `<name>.<disamb>` for a local symbol. Handing the whole thing to a
    ## client as one string is what makes the rest of the compiler take it
    ## apart again, over and over.
    ##
    ## In split mode the reader takes it apart ONCE, while it still has the
    ## raw bytes: a `Symbol`/`SymbolDef` token carries only `<name>`, and its
    ## `suffixes` field says how many `ExtendedSuffix` tokens follow — one per
    ## remaining component, in order, each tagged with its `part`. So
    ## `abc.12.Ikey.mod` arrives as
    ##
    ##   Symbol "abc" (suffixes: 3), SymDisamb "12", SymDedup "Ikey", SymModule "mod"
    ##
    ## `ExtendedSuffix` is the binary model's "more bits for the token before
    ## me" kind; a symbol component is exactly that, so no new token kind is
    ## needed and every existing `case` over `NifKind` still compiles.
    ##
    ## An atom with no dot to split on at all -- an operator definition such as
    ## `[]=` -- is left whole: `suffixes` is 0 and the token is what it always
    ## was. A symbol whose disambiguator is not a number (arkham's legacy
    ## `_exit.sys.mod`) still yields its module; only the name/disambiguator
    ## boundary needs the digit, so everything but the module is the name."""
    r._splitSyms = enable


@ufcs(Reader)
def symbolsAreSplit(r: Reader) -> bool:
    """{.inline.}"""
    return r._splitSyms


def _hasEscapes(data: StringView, first: nint, last: nint) -> bool:
    result = default(bool)
    with var:
        i = first
    while i <= last:
        if data[i] == char("\\"):
            return True
        i += 1
    result = False
    return result


def _splitSymbol(r: mut @ Reader, result: mut @ ExpandedToken):
    """Cut the just-lexed symbol into its `<name>` and the components that
    follow it, which subsequent `next` calls hand out as `ExtendedSuffix`
    tokens. `result.data` is shortened to the name.

    Same grammar as `nifcore.splitSpelling`, applied to the RAW bytes, where
    an escaped dot (`\\2E`) is still three bytes and so cannot be mistaken for
    a separator: the module is the last dot-separated component unless it
    STARTS with a digit (`p.0h107` is a local symbol, not one from a module
    called `0h107`), and the name ends at the last `.` followed by a digit,
    because a name may contain dots itself (`a.b.c.23`)."""
    with let:
        origLen = result.data.len.copy()
    with var:
        lastDot = -1
    with var:
        k = 0
    while k < origLen:
        if result.data[k] == char("."):
            lastDot = k
        k += 1

    with var:
        head = origLen
    with var:
        moduleStart = -1
    if lastDot >= 0:
        if lastDot + 1 < origLen:
            if result.data[lastDot + 1] not in _Digits:
                moduleStart = lastDot + 1
                head = lastDot
        else:
            # a trailing dot is the "my own module" shorthand: the module is there,
            # spelled as nothing at all
            moduleStart = lastDot + 1
            head = lastDot

    with var:
        i = head - 2
    while i > 0:
        if result.data[i] == char(".") and result.data[i + 1] in _Digits:
            break
        i -= 1

    with var:
        start = 0
    if i > 0:
        r._pendingHasDisamb = True
        start = i + 1
        result.data.len = i
    elif moduleStart >= 0:
        # no numeric disambiguator (`_exit.sys.mod`): everything but the module is
        # the name, which is what `splitSymName` has always answered here
        r._pendingHasDisamb = False
        start = moduleStart
        result.data.len = head
    else:
        return  # not a symbol at all; leave it whole

    r._pendingHasModule = moduleStart >= 0
    # `result.data.len` is the name by now; the components run from `start` to the
    # symbol's ORIGINAL end.
    r._pending = StringView(p=_plus_bang(result.data.p, start), len=origLen - start)
    with var:
        comps = int32(1)
    for j in range(0, r._pending.len):
        if r._pending[j] == char("."):
            comps += 1
    r._pendingTotal = comps
    r._pendingLeft = comps
    r._pendingFlags = result._flags
    result.suffixes = uint8(comps)
    # The name keeps only the flags that are about the name: a trailing dot
    # (module suffix expansion) belongs to the last component, and escapes
    # only to the components that actually contain a backslash.
    result._flags.excl(_TokenFlag.TokenHasModuleSuffixExpansion)
    if _TokenFlag.TokenHasEscapes in result._flags and not _hasEscapes(
        result.data, 0, result.data.len - 1
    ):
        result._flags.excl(_TokenFlag.TokenHasEscapes)


def _nextSymbolPart(r: mut @ Reader, result: mut @ ExpandedToken):
    """Hand out the next component of the symbol returned earlier."""
    result <<= default(ExpandedToken)
    result.tk = NifKind.ExtendedSuffix
    if r._pendingLeft == r._pendingTotal and r._pendingHasDisamb:
        result.part = SymbolPart.SymDisamb
    elif r._pendingLeft == 1 and r._pendingHasModule:
        result.part = SymbolPart.SymModule
    else:
        result.part = SymbolPart.SymDedup
    with var:
        n = 0
    while n < r._pending.len and r._pending[n] != char("."):
        n += 1
    result.data = StringView(p=r._pending.p, len=n)
    if _TokenFlag.TokenHasEscapes in r._pendingFlags and _hasEscapes(
        result.data, 0, n - 1
    ):
        result._flags.incl(_TokenFlag.TokenHasEscapes)
    r._pendingLeft -= 1
    if r._pendingLeft == 0:
        # `abc.12.` means "the module I am being read from"; the empty last
        # component is the one that expands to it.
        if _TokenFlag.TokenHasModuleSuffixExpansion in r._pendingFlags:
            result._flags.incl(_TokenFlag.TokenHasModuleSuffixExpansion)
        r._pending = StringView(p=nil, len=0)
    else:
        r._pending = StringView(
            p=_plus_bang(r._pending.p, n + 1), len=r._pending.len - (n + 1)
        )


# ── Line-based syntax (optional NIF extension) ────────────────────────────
#
# A top-level line that does not start with `(` is read as `(tag arg1 ...)`,
# and a number, identifier or symbol that continues with `-`, `/` or `:`
# extends up to the next whitespace, parenthesis or suffix and is a string
# literal instead. The reader produces the very same tokens as for the
# parenthesized form: a `ParLe` for the tag and a `ParRi` (with empty `data`)
# for the newline that ends the node.

with const:
    _IdentStartChars = Tset(
        inrange(char("a"), char("z")),
        inrange(char("A"), char("Z")),
        char("_"),
        char("\\"),
        inrange(char("\x80"), char("\xff")),
    )
    _IdentChars = _IdentStartChars + _Digits
    _LineStrStart = Tset(char("-"), char("/"), char(":"))
    _LineStrEnd = Tset(
        char(" "),
        char("\t"),
        char("\n"),
        char("\r"),
        char("("),
        char(")"),
        char("@"),
        char("~"),
        char("#"),
    )
    # where an identifier or symbol ends in line mode: `-` and `/` are no
    # control characters, but they start a string
    _LineWordEnd = _ControlCharsOrWhite + Tset(char("-"), char("/"))


@template
def _continuesAsStr(r: Reader) -> bool:
    """Line mode: the number, identifier or symbol just read continues with
    `-`, `/` or `:` and so is the start of a string literal."""
    return r._lineBased and r._p < r._eof and _deref(r._p) in _LineStrStart


@template_expand
def _lineStr(r: mut @ Reader, result: mut @ ExpandedToken):
    """Extend the token that starts at `result.data.p` up to the next whitespace,
    parenthesis or suffix (`@`, `~`, `#`) and turn it into a string literal."""
    with _useCpuRegisters():
        while p < eof and _deref(p) not in _LineStrEnd:
            if _deref(p) == char("\\"):
                result._flags.incl(_TokenFlag.TokenHasEscapes)
            _inc(p)
        result.data.len = _minus_bang(p, result.data.p)
    result.tk = StringLit
    result._flags.excl(_TokenFlag.TokenHasModuleSuffixExpansion)
    _handleSuffix(r, result)


@template_expand
def _lineHead(r: mut @ Reader, result: mut @ ExpandedToken):
    """The `TagHead` that starts a `LineNode`. A line that does not start with
    an identifier is surfaced as one `UnknownToken` spanning the rest of it."""
    with _useCpuRegisters():
        result.data.p = p
        if _deref(p) in _IdentStartChars:
            while p < eof and _deref(p) in _IdentChars:
                # an escape's body may be a shortcut such as `\|`
                with let:
                    n = 2 if _deref(p) == char("\\") and _plus_bang(p, 1) < eof else 1
                result.data.len += n
                _inc(p, n)
        if result.data.len > 0 and (p >= eof or _deref(p) in _ControlCharsOrWhite):
            result.tk = NifKind.ParLe
        else:
            while p < eof and _deref(p) != char("\n"):
                _inc(p)
            result.data.len = _minus_bang(p, result.data.p)
    if result.tk == NifKind.ParLe:
        r._inLineNode = True
        _handleSuffix(r, result)


@template_expand
def _linePrelude(r: mut @ Reader, tok: mut @ ExpandedToken) -> bool:
    """The line-based syntax's part of `next`, run instead of skipping the
    whitespace. Returns true when it produced the token itself; otherwise the
    ordinary tokenizer takes over at `r.p`."""
    result = default(bool)
    if r._inLineNode and r._depth == 0:
        # the newline is significant here
        with _useCpuRegisters():
            while p < eof and _deref(p) in Tset(char(" "), char("\t"), char("\r")):
                _inc(p)
        if r._p >= r._eof or _deref(r._p) == char("\n"):
            # the `)` of the line node; the newline itself is skipped next time
            tok.tk = NifKind.ParRi
            tok.data = StringView(p=r._p, len=0)
            r._inLineNode = False
            return True
    else:
        _skipWhitespace(r)
        if r._p >= r._eof:
            return False
    result = False
    match _deref(r._p):
        case _ if _deref(r._p) == char("("):
            r._depth += 1
        case _ if _deref(r._p) == char(")"):
            if r._depth > 0:
                r._depth -= 1
        case _:
            if not r._inLineNode and r._depth == 0:
                _lineHead(r, tok)
                result = True
    return result


@ufcs(Reader)
@dispatch
@template_expand
def next(r: mut @ Reader, result: mut @ ExpandedToken):
    if r._pendingLeft > 0:
        _nextSymbolPart(r, result)
        return
    result <<= default(ExpandedToken)
    # In the unified NifKind, ordinal 0 is DotToken, not UnknownToken — the
    # classification branches below rely on `tk` starting out as "unknown"
    # (e.g. the char-literal branch leaves it untouched on a lex error).
    result.tk = NifKind.UnknownToken
    if r._lineBased:
        if _linePrelude(r, result):
            return
    else:
        _skipWhitespace(r)
    if r._p >= r._eof:
        result.tk = NifKind.EofToken
        return

    match _deref(r._p):
        case _ if _deref(r._p) == char("("):
            result.tk = NifKind.ParLe
            with _useCpuRegisters():
                _inc(p)
                result.data.p = p
                result.data.len = 0
                while p < eof and _deref(p) not in _ControlCharsOrWhite:
                    result.data.len += 1
                    _inc(p)
            _handleSuffix(r, result)

        case _ if _deref(r._p) == char(")"):
            result.tk = NifKind.ParRi
            result.data.p = r._p
            result.data.len += 1
            _inc(r._p)
        case _ if _deref(r._p) == char("."):
            result.tk = NifKind.DotToken
            result.data.p = r._p
            result.data.len += 1
            _inc(r._p)
            _handleSuffix(r, result)
        case _ if _deref(r._p) == char('"'):
            with _useCpuRegisters():
                _inc(p)
                result.tk = StringLit
                result.data.p = p
                result.data.len = 0
                while p < eof:
                    with let:
                        ch = _deref(p)
                    if ch == char('"'):
                        _inc(p)
                        break
                    elif ch == char("\\"):
                        result._flags.incl(_TokenFlag.TokenHasEscapes)
                    elif ch == char("\n"):
                        r.line += 1
                    result.data.len += 1
                    _inc(p)
            _handleSuffix(r, result)
        case _ if _deref(r._p) == char("'"):
            _inc(r._p)
            result.data.p = r._p
            if _deref(r._p) == char("\\"):
                result._flags.incl(_TokenFlag.TokenHasEscapes)
                _inc(r._p)
                if r._p[0] in _HexChars and r._p[1] in _HexChars:
                    _inc(r._p, 2)
                    if _deref(r._p) == char("'"):
                        _inc(r._p)
                        result.tk = NifKind.CharLit  # now valid
            elif _deref(r._p) in _ControlChars:
                discard("keep it as UnknownToken")
            else:
                _inc(r._p)
                if _deref(r._p) == char("'"):
                    _inc(r._p)
                    result.tk = NifKind.CharLit  # only now valid
            if result.tk == NifKind.CharLit:
                _handleSuffix(r, result)

        case _ if _deref(r._p) == char(":"):
            with _useCpuRegisters():
                _inc(p)
                result.data.p = p
                while p < eof and _deref(p) not in _ControlCharsOrWhite:
                    if _deref(p) == char("\\"):
                        result._flags.incl(_TokenFlag.TokenHasEscapes)
                    result.data.len += 1
                    _inc(p)
            if result.data.len > 0:
                result.tk = NifKind.SymbolDef
                if result.data[result.data.len - 1] == char("."):
                    result._flags.incl(_TokenFlag.TokenHasModuleSuffixExpansion)
                if r._splitSyms:
                    _splitSymbol(r, result)
                _handleSuffix(r, result)

        case _ if _deref(r._p) == char("-"):
            # negative number; '+' is no longer a number prefix in NIF27.
            result.data.p = r._p
            _inc(r._p)
            result.data.len += 1
            _handleNumber(r, result)
            if _continuesAsStr(r):
                _lineStr(r, result)
            else:
                _handleSuffix(r, result)

        case _ if _deref(r._p) in inrange(char("0"), char("9")):
            # bare-digit number (NIF27): no sign prefix on positives.
            with _useCpuRegisters():
                result.data.p = p
                result.data.len = 0
            _handleNumber(r, result)
            if _continuesAsStr(r):
                _lineStr(r, result)  # `2024-08-12`, `14:05`
            else:
                _handleSuffix(r, result)

        case _:
            with var:
                hasDot = False

            @template
            def scanWord(wordEnd: Tset[char]):
                with _useCpuRegisters():
                    result.data.p = p
                    while p < eof and _deref(p) not in wordEnd:
                        if _deref(p) == char("\\"):
                            result._flags.incl(_TokenFlag.TokenHasEscapes)
                        elif _deref(p) == char("."):
                            hasDot = True
                        result.data.len += 1
                        _inc(p)

            if r._lineBased:
                scanWord(_LineWordEnd)
            else:
                scanWord(_ControlCharsOrWhite)

            if _continuesAsStr(r):
                _lineStr(r, result)  # `a/b.txt`, `x-y`, `https://x`, `/usr/bin`
            elif result.data.len > 0:
                if hasDot:
                    result.tk = NifKind.Symbol
                    if result.data[result.data.len - 1] == char("."):
                        result._flags.incl(_TokenFlag.TokenHasModuleSuffixExpansion)
                    if r._splitSyms:
                        _splitSymbol(r, result)
                else:
                    result.tk = NifKind.Ident
                _handleSuffix(r, result)
            else:
                # Stray control character we don't otherwise handle (e.g. `[`, `]`, `~`).
                # Consume it to avoid an infinite loop and surface it as UnknownToken so
                # callers can flag the malformed input.
                result.data.p = r._p
                result.data.len = 1
                _inc(r._p)


@ufcs(Reader)
@dispatch
def next(r: mut @ Reader) -> ExpandedToken:
    """{.deprecated: "use the other next instead".}"""
    result = default(ExpandedToken)
    next(r, result)
    return result


class DirectivesResult(NIntEnum):
    WrongHeader = auto()
    WrongMeta = auto()
    Success = auto()


@ufcs(Reader)
@template_expand
def startsWith(r: Reader, prefix: string) -> bool:
    result = default(bool)
    with let:
        prefixLen = len(prefix)
    with var:
        i = 0
    with var:
        p = r._p
    while True:
        if i >= prefixLen:
            return True
        if p >= r._eof or _deref(p) != prefix[i]:
            return False
        _inc(p)
        i += 1
    return False


def _readDirectives(r: mut @ Reader):
    with var:
        tok = default(ExpandedToken)
    while True:
        _skipWhitespace(r)
        if r.startsWith(string("(.")):
            next(r, tok)
            assert tok.tk == NifKind.ParLe
            if tok.data == string(".indexat"):
                next(r, tok)
                if tok.tk == NifKind.IntLit:
                    r._indexAt = nint(decodeInt(tok))
            elif tok.data == string(".unusedname"):
                next(r, tok)
                if tok.tk == NifKind.Symbol:
                    r._unusedNameHint = tok
            # skip the rest of the directive:
            with var:
                nested = 0
            while True:
                next(r, tok)
                match tok.tk:
                    case NifKind.ParLe:
                        nested += 1
                    case NifKind.ParRi:
                        if nested == 0:
                            break
                        nested -= 1
                    case NifKind.EofToken:
                        break
                    case _:
                        pass
        else:
            break


def extractModuleSuffix(filename: string) -> string:
    result = default(string)
    result = string("")
    with var:
        skip = False
    for c in filename:
        if c == char("/") or c == char("\\"):
            result.setLen(0)
            skip = False
        elif c == char("."):
            skip = True
        elif not skip:
            result.add(c)
    return result


def open(filename: string, lineBased=False) -> Reader:
    """With `lineBased`, the reader accepts NIF's optional line-based syntax:
    a top-level line not starting with `(` is a node `(tag args...)` that ends
    at the newline, and a number, identifier or symbol that continues with
    `-`, `/` or `:` is a string literal (`a/b.txt`, `2024-08-12`, `14:05`).
    Such a module is a flat list of top-level nodes; `next` returns them one
    after another until `EofToken`."""
    result = default(Reader)

    with let:
        try:
            f = vfsOpenMmap(filename)
        except:
            if comptime(defined("debug") and not defined("nimony")):
                writeStackTrace()
            quit(string("[Error] cannot open: ") + filename)
    result = Reader(
        _f=f, _p=nil, thisModule=extractModuleSuffix(filename), _lineBased=lineBased
    )
    result._p = cast[pchar](result._f.data)
    result._eof = _plus_bang(result._p, result._f.size)
    _readDirectives(result)
    return result


def openFromBuffer(
    buf: sink @ string, thisModule: sink @ string, lineBased=False
) -> Reader:
    """The Reader keeps `buf` alive as the owner of the source bytes. `buf` may be
    a short SSO string whose chars live *inline* in the string object; a plain
    `readRawData` pointer into it would dangle the moment the Reader is moved
    into its caller (and into the wrapping Stream), since the inline bytes move
    with the object. `readRawDataStable` pins `buf` to its heap representation,
    whose payload address survives those moves, so the cached `r.p`/`r.eof`
    stay valid for as long as the Reader (and thus `buf`) is alive.
    See `open` for `lineBased`."""
    result = default(Reader)
    result = Reader(
        _buf=ensureMove(buf),
        thisModule=ensureMove(thisModule),
        _lineBased=lineBased,
    )
    with let:
        n = len(result._buf)
    result._p = readRawDataStable(result._buf)
    result._eof = _plus_bang(result._p, n)
    result._f = initBlob(cast[pointer](result._p), n)
    _readDirectives(result)
    return result


@ufcs(Reader)
def processDirectives(r: mut @ Reader) -> DirectivesResult:
    result = default(DirectivesResult)
    result = DirectivesResult.Success
    return result


@ufcs(Reader)
def fileSize(r: mut @ Reader) -> nint:
    """{.inline.}"""
    return r._f.size


@ufcs(Reader)
def offset(r: mut @ Reader) -> nint:
    """{.inline.}"""
    result = default(nint)
    result = _minus_bang(r._p, cast[pchar](r._f.data))
    return result


@ufcs(Reader)
def jumpTo(r: mut @ Reader, offset: nint):
    """{.inline.}"""
    r._p = _plus_bang(cast[pchar](r._f.data), offset)
    assert cast[pointer](r._p) >= r._f.data and r._p < r._eof
    # `offset` is the position AFTER the whole symbol, so a jump abandons the
    # components of a split symbol that were not asked for.
    r._pendingLeft = int32(0)
    r._pending = StringView(p=nil, len=0)
    # In the line-based syntax, a jump target is taken to be a top-level node.
    r._inLineNode = False
    r._depth = int32(0)


@ufcs(Reader)
def indexStartsAt(r: Reader) -> nint:
    return r._indexAt


@ufcs(Reader)
def firstUnusedName(r: Reader) -> string:
    """Returns the symbol supplied by the `.unusedname` directive, or `""`."""
    result = default(string)
    result = string("")
    if r._unusedNameHint.tk == NifKind.Symbol:
        result = decodeStr(r, r._unusedNameHint)
    return result


if comptime(__name__ == "__main__" and not defined("nimony")):

    def _tokens(input: string, split: bool) -> seq[string]:
        """Every token of `input`, rendered as "<what>:<decoded text>"."""
        result = default(seq[string])
        with var:
            r = openFromBuffer(input, string("ThisMod"))
        r.splitSymbols(split)
        result = seq[string]()
        with var:
            tok = default(ExpandedToken)
        while True:
            r.next(tok)
            match tok.tk:
                case NifKind.EofToken:
                    break
                case NifKind.Symbol:
                    result.add(
                        string("sym")
                        + str(tok.suffixes)
                        + string(":")
                        + r.decodeStr(tok)
                    )
                case NifKind.SymbolDef:
                    result.add(
                        string("def")
                        + str(tok.suffixes)
                        + string(":")
                        + r.decodeStr(tok)
                    )
                case NifKind.ExtendedSuffix:
                    with var:
                        s = string(str(tok.part)) + string(":") + r.decodeStr(tok)
                    if tok.part == SymbolPart.SymDisamb:
                        s.add(string("=") + str(decodeDisamb(tok)))
                    result.add(s)
                case NifKind.ParLe:
                    result.add(string("(") + str(tok.data))
                case NifKind.ParRi:
                    result.add(string(")"))
                case _:
                    result.add(string(str(tok.tk)) + string(":") + r.decodeStr(tok))
        close(r)
        return result

    # Off by default: a symbol is one token carrying the whole string, exactly
    # as every existing client expects.
    assert _tokens(
        string("(stmts abc.12.Ikey.mod :def.1.mod tmp.14)"), False
    ) == seq[string](
        [string("(stmts"),
        string("sym0:abc.12.Ikey.mod"),
        string("def0:def.1.mod"),
        string("sym0:tmp.14"),
        string(")")],
    )

    # On: the reader takes the symbol apart and reports the components as
    # `ExtendedSuffix` tokens following the head.
    assert _tokens(string("abc.12.Ikey.mod"), True) == seq[string](
        [string("sym3:abc"),
        string("SymDisamb:12=12"),
        string("SymDedup:Ikey"),
        string("SymModule:mod")],
    )
    assert _tokens(string("abc.12.mod"), True) == seq[string](
        [string("sym2:abc"),
        string("SymDisamb:12=12"),
        string("SymModule:mod")],
    )
    # A local symbol has no module.
    assert _tokens(string("tmp.14"), True) == seq[string](
        [string("sym1:tmp"),
        string("SymDisamb:14=14")],
    )
    # A symbol definition splits the same way.
    assert _tokens(string(":def.1.mod"), True) == seq[string](
        [string("def2:def"),
        string("SymDisamb:1=1"),
        string("SymModule:mod")],
    )
    # A trailing dot is the "my own module" shorthand: it is the last component
    # that expands, not the name.
    assert _tokens(string("x.3."), True) == seq[string](
        [string("sym2:x"),
        string("SymDisamb:3=3"),
        string("SymModule:ThisMod")],
    )
    # Only the disambiguator's dot ends the name; the name may contain dots.
    assert _tokens(string("a.b.c.23.mod"), True) == seq[string](
        [string("sym2:a.b.c"),
        string("SymDisamb:23=23"),
        string("SymModule:mod")],
    )
    # An escaped dot is `\2E` in the raw bytes and so cannot be mistaken for a
    # separator; the escapes stay with the component that has them.
    assert _tokens(string("a\\2Eb.5.mod"), True) == seq[string](
        [string("sym2:a.b"),
        string("SymDisamb:5=5"),
        string("SymModule:mod")],
    )
    # An operator definition has no dot to split on and is left whole.
    assert _tokens(string("foo.bar"), True) == seq[string](
        [string("sym1:foo"),
        string("SymModule:bar")],
    )
    assert _tokens(string(":\\5B\\5D="), True) == seq[string]([string("def0:[]=")])
    # A disambiguator the inliner minted is NOT a module, however non-numeric it
    # looks after its first character.
    assert _tokens(string("p.0h107"), True) == seq[string](
        [string("sym1:p"),
        string("SymDisamb:0h107=0")],
    )
    # ...and one with no numeric part at all (arkham's legacy syproc names) still
    # yields its module; everything before it is the name.
    assert _tokens(string("_exit.sys.sysvq0asl"), True) == seq[string](
        [string("sym1:_exit.sys"),
        string("SymModule:sysvq0asl")],
    )
    # Line info and comments ride on the head, as before.
    assert _tokens(string("abc.12.mod@3,4#hi#"), True) == seq[string](
        [string("sym2:abc"),
        string("SymDisamb:12=12"),
        string("SymModule:mod")],
    )

    if True:  # a jump abandons the components nobody asked for
        with var:
            r = openFromBuffer(string("abc.12.mod tail.1"), string("ThisMod"))
        r.splitSymbols()
        assert r.symbolsAreSplit()
        with var:
            tok = default(ExpandedToken)
        with let:
            start = offset(r)
        r.next(tok)
        assert tok.tk == NifKind.Symbol and tok.suffixes == uint8(2)
        r.jumpTo(start)
        r.next(tok)
        assert r.decodeStr(tok) == string("abc")
        r.next(tok)
        assert tok.tk == NifKind.ExtendedSuffix and tok.part == SymbolPart.SymDisamb
        close(r)

    def _lineTokens(input: string) -> seq[string]:
        """Like `tokens`, for the line-based syntax; string literals are quoted."""
        result = default(seq[string])
        with var:
            r = openFromBuffer(input, string("ThisMod"), lineBased=True)
        result = seq[string]()
        with var:
            tok = default(ExpandedToken)
        while True:
            r.next(tok)
            match tok.tk:
                case NifKind.EofToken:
                    break
                case NifKind.ParLe:
                    result.add(string("(") + str(tok.data))
                case NifKind.ParRi:
                    result.add(string(")"))
                case NifKind.StrLit:
                    result.add(string('"') + r.decodeStr(tok) + string('"'))
                case NifKind.UnknownToken:
                    result.add(string("?") + str(tok.data))
                case _:
                    result.add(r.decodeStr(tok))
        close(r)
        return result

    if True:  # line-based syntax
        assert _lineTokens(
            string('copy a/b.txt dest/b.txt\nwarn 2024-08-12 "permission denied"')
        ) == seq[string](
            [string("(copy"),
            string('"a/b.txt"'),
            string('"dest/b.txt"'),
            string(")"),
            string("(warn"),
            string('"2024-08-12"'),
            string('"permission denied"'),
            string(")")],
        )
        # the same AST as the parenthesized form
        assert _lineTokens(string("copy a/b.txt dest/b.txt\n")) == _lineTokens(
            string('(copy "a/b.txt" "dest/b.txt")')
        )
        # both forms mix; directives keep their form and are skipped as usual
        assert _lineTokens(
            string(
                '(.nif27)\ninfo 2024-08-12T09:14:03Z "server started" (port 8080)\n'
            )
        ) == seq[string](
            [string("(info"),
            string('"2024-08-12T09:14:03Z"'),
            string('"server started"'),
            string("(port"),
            string("8080"),
            string(")"),
            string(")")],
        )
        assert _lineTokens(string("(a x) b c\n(d)")) == seq[string](
            [string("(a"),
            string("x"),
            string(")"),
            string("(b"),
            string("c"),
            string(")"),
            string("(d"),
            string(")")],
        )
        # a parenthesized argument (and a string) continues the line
        assert _lineTokens(string('a (b\n  c) "x\ny"\n  d')) == seq[string](
            [string("(a"),
            string("(b"),
            string("c"),
            string(")"),
            string('"x\ny"'),
            string(")"),
            string("(d"),
            string(")")],
        )
        # empty and blank lines, indentation, CRLF, a line with just a tag
        assert _lineTokens(string("\n  \t\n  ls\r\n\r\nls x\r\n")) == seq[string](
            [string("(ls"),
            string(")"),
            string("(ls"),
            string("x"),
            string(")")],
        )
        assert _lineTokens(string("")) == newSeq[string]()
        # the string rule applies at every nesting level of a line-based module
        assert _lineTokens(string("a (b x/y)\n(c x/y)")) == seq[string](
            [string("(a"),
            string("(b"),
            string('"x/y"'),
            string(")"),
            string(")"),
            string("(c"),
            string('"x/y"'),
            string(")")],
        )
        # a number that continues with `-`, `/` or `:` extends to the whitespace
        assert _lineTokens(
            string(
                "t 2024-08-12 2024-08-12T14:05:09.25+02:00 2024-08-12x 1/2 14:05 12:00Z"
            )
        ) == seq[string](
            [string("(t"),
            string('"2024-08-12"'),
            string('"2024-08-12T14:05:09.25+02:00"'),
            string('"2024-08-12x"'),
            string('"1/2"'),
            string('"14:05"'),
            string('"12:00Z"'),
            string(")")],
        )
        # other numbers stay numbers
        assert _lineTokens(string("t 42 -7 1.5 1.5E-3 x.1")) == seq[string](
            [string("(t"),
            string("42"),
            string("-7"),
            string("1.5"),
            string("1.5E-3"),
            string("x.1"),
            string(")")],
        )
        # so do identifiers and symbols; once one continues with `-`, `/` or `:`,
        # control characters other than parentheses and suffix introducers are
        # part of the string
        assert _lineTokens(
            string(
                'get x-y /usr/bin a/b.txt my\\20dir/a.txt dest/x. a/b:c"d#e# (p a/b)'
            )
        ) == seq[string](
            [string("(get"),
            string('"x-y"'),
            string('"/usr/bin"'),
            string('"a/b.txt"'),
            string('"my dir/a.txt"'),
            string('"dest/x."'),
            string('"a/b:c"d"'),
            string("(p"),
            string('"a/b"'),
            string(")"),
            string(")")],
        )
        assert _lineTokens(
            string("get https://nim-lang.org C:/tmp/x.txt key: a.b:c")
        ) == seq[string](
            [string("(get"),
            string('"https://nim-lang.org"'),
            string('"C:/tmp/x.txt"'),
            string('"key:"'),
            string('"a.b:c"'),
            string(")")],
        )
        # an auto string carries a suffix like every other atom
        if True:
            with var:
                r = openFromBuffer(
                    string("t src/main.nim@0,3#c# 2024-08-12~2 12@3,4"),
                    string("ThisMod"),
                    lineBased=True,
                )
            with var:
                tok = default(ExpandedToken)
            r.next(tok)
            r.next(tok)
            assert tok.tk == StringLit and r.decodeStr(tok) == string("src/main.nim")
            assert tok.pos.line == int32(3) and decodeComment(tok) == string("c")
            r.next(tok)
            assert (
                tok.tk == StringLit
                and r.decodeStr(tok) == string("2024-08-12")
                and tok.pos.col == int32(-2)
            )
            r.next(tok)
            assert (
                tok.tk == NifKind.IntLit
                and tok.pos.col == int32(3)
                and tok.pos.line == int32(4)
            )
            close(r)
        # `-` without digits is an empty number: `--color` continues with `-`
        assert _lineTokens(string("ls --color -3")) == seq[string](
            [string("(ls"),
            string('"--color"'),
            string("-3"),
            string(")")],
        )
        # `..` alone is still two empty nodes
        assert _lineTokens(string("up ..")) == seq[string](
            [string("(up"),
            string("."),
            string("."),
            string(")")],
        )
        # the tag carries a suffix
        if True:
            with var:
                r = openFromBuffer(
                    string("warn@0,1#disk#  2024-08-12"),
                    string("ThisMod"),
                    lineBased=True,
                )
            with var:
                tok = default(ExpandedToken)
            r.next(tok)
            assert (
                tok.tk == NifKind.ParLe
                and tok.data == string("warn")
                and tok.pos.line == int32(1)
            )
            assert decodeComment(tok) == string("disk")
            close(r)
        # a line that does not start with an identifier is one error token
        assert _lineTokens(string("./run.sh x\nok")) == seq[string](
            [string("?./run.sh x"),
            string("(ok"),
            string(")")],
        )
        # line tracking is unaffected
        if True:
            with var:
                r = openFromBuffer(
                    string("a\n\nb\n"), string("ThisMod"), lineBased=True
                )
            with var:
                tok = default(ExpandedToken)
            while True:
                r.next(tok)
                if tok.tk == NifKind.EofToken:
                    break
            assert r.line == int32(3)
            close(r)
        # off by default: plain NIF is read exactly as before
        assert _tokens(string("(a) b"), False) == seq[string](
            [string("(a"),
            string(")"),
            string("Ident:b")],
        )

    echo("nifreader: OK")


if comptime(__name__ == "__main__"):

    def _test_nifreader_extra():
        # extractModuleSuffix
        assert extractModuleSuffix(string("foo/bar/baz.s.nif")) == string("baz")
        assert extractModuleSuffix(string("dir\\modname.nif")) == string("modname")
        assert extractModuleSuffix(string("simple")) == string("simple")

        # directives, fileSize, indexStartsAt, firstUnusedName, processDirectives, startsWith
        with var:
            r = openFromBuffer(
                string(
                    "(.nif24) (.indexat 128) (.unusedname unused.1.MyMod) (stmts . 'A' '\\41' 42 -17 99u 3.25 \"hi\\n\\t\\r\\|\\^\\21\"@10,~2,path\\20name.nim#cmt\\21# :local.1. sym.2.)"
                ),
                string("MyMod"),
            )
        assert r.processDirectives() == DirectivesResult.Success
        assert r.indexStartsAt() == 128
        assert r.firstUnusedName() == string("unused.1.MyMod")
        assert r.fileSize() > 0
        assert r.startsWith(string("(stmts"))

        with var:
            tok = default(ExpandedToken)
        r.next(tok)
        assert tok.tk == NifKind.ParLe and str(tok) == string("(stmts")

        r.next(tok)
        assert tok.tk == NifKind.DotToken and str(tok) == string(".")

        r.next(tok)
        assert tok.tk == NifKind.CharLit and decodeChar(tok) == char("A")
        assert str(tok) == string("CharLit:")

        r.next(tok)
        assert tok.tk == NifKind.CharLit and decodeChar(tok) == char("A")

        r.next(tok)
        assert tok.tk == NifKind.IntLit and decodeInt(tok) == BiggestInt(42)
        assert str(tok) == string("IntLit:42")

        r.next(tok)
        assert tok.tk == NifKind.IntLit and decodeInt(tok) == BiggestInt(-17)

        r.next(tok)
        assert tok.tk == NifKind.UIntLit and decodeUInt(tok) == BiggestUInt(99)

        r.next(tok)
        assert tok.tk == NifKind.FloatLit and decodeFloat(tok) == BiggestFloat(3.25)

        r.next(tok)
        assert tok.tk == StringLit
        assert needsDecoding(tok)
        assert r.decodeStr(tok) == string('hi\n\t\r\\"!'), r.decodeStr(tok)
        assert tok.pos.col == int32(62) and tok.pos.line == int32(-2)
        assert decodeFilename(tok) == string("path name.nim")
        assert decodeComment(tok) == string("cmt!")

        r.next(tok)
        assert tok.tk == NifKind.SymbolDef
        assert needsDecoding(tok)
        assert r.decodeStr(tok) == string("local.1.MyMod")

        r.next(tok)
        assert tok.tk == NifKind.Symbol
        assert needsDecoding(tok)
        assert r.decodeStr(tok) == string("sym.2.MyMod")

        r.next(tok)
        assert tok.tk == NifKind.ParRi and str(tok) == string(")")

        r.next(tok)
        assert tok.tk == NifKind.EofToken and str(tok) == string("<eof>")

        with var:
            tagTok = default(ExpandedToken)
        tagTok.tk = NifKind.TagLit
        assert str(tagTok) == string("<TagLit>")
        tagTok.tk = NifKind.LineInfoLit
        assert str(tagTok) == string("<LineInfoLit>")
        tagTok.tk = NifKind.UnknownToken
        assert str(tagTok) == string("<unknown token>")

        close(r)

    _test_nifreader_extra()

    importFrom("nimic.std.os", "getTempDir", "removeFile")
    importFrom("nimic.std.syncio", "writeFile")
    from nimic.std.formatfloat import *  # `$` of a float (nimony builds with a slim system)

    def _show(r: Reader, tok: ExpandedToken) -> string:
        """A token as `<kind> <decoded value>`, then its suffix: `@col,line`, the filename, the comment, the flags
        that say whether it needs decoding, and for a split symbol's component its part."""
        with var:
            result = string(str(tok.tk))
        match tok.tk:
            case NifKind.CharLit:
                result.add(string(" ") + str(ord(decodeChar(tok))))
            case NifKind.IntLit:
                result.add(string(" ") + str(decodeInt(tok)))
            case NifKind.UIntLit:
                result.add(string(" ") + str(decodeUInt(tok)))
            case NifKind.FloatLit:
                with let:
                    f = decodeFloat(tok)
                result.add(string(" ") + str(f) + string(" bits=") + str(cast[uint64](f)))
            case NifKind.ParLe | NifKind.ParRi | NifKind.DotToken | NifKind.EofToken | NifKind.UnknownToken:
                result.add(string(" ") + str(tok.data))
            case NifKind.Symbol | NifKind.SymbolDef:
                result.add(string(" ") + r.decodeStr(tok) + string(" suffixes=") + str(tok.suffixes))
            case NifKind.ExtendedSuffix:
                result.add(string(" ") + str(tok.part) + string(" ") + r.decodeStr(tok))
            case _:
                result.add(string(" ") + r.decodeStr(tok))
        result.add(string(" @") + str(tok.pos.col) + string(",") + str(tok.pos.line))
        if tok.filename.len > 0:
            result.add(string(" file=") + decodeFilename(tok))
        if tok.comment.len > 0:
            result.add(string(" #") + decodeComment(tok) + string("#"))
        if needsDecoding(tok):
            result.add(string(" (decoded)"))
        return result

    def _dump(r: mut @ Reader):
        with var:
            tok = default(ExpandedToken)
        while True:
            r.next(tok)
            echo(_show(r, tok))
            if tok.tk == NifKind.EofToken:
                break

    def _test_nifreader_dump():
        with let:
            text = string(
                "(.nif27)\n(.indexat 77)\n(.unusedname tmp.9.)\n"
                "(stmts@1,2,a\\2Eb.nim 'x' '\\0A' 0 -0 123 -9223372036854775808 9223372036854775807\n"
                "  0u 18446744073709551615u 0.1 1E300 5E-324 -0.0 2.5E-3 1.7976931348623157E308\n"
                "  123456789012345678901234567890.5 \"q\\^x\\|y\\n\\t\\r\\41\" ident sym.12.mod :def.3.\n"
                "  x.1~5,~7 y.2@Z,a z.3@,5 w.4@3,,f.nim .#a\\23b# abc.12.Ikey.mod p.0h107 _exit.sys.m\n"
                "  [ ~ )"
            )
            path = getTempDir() + string("nimic_nifreader_test.nif")
        writeFile(path, text)
        # through vfs (an mmap'd file); the module suffix comes from the file name
        with var:
            r = open(path)
        echo(string("file: size="), r.fileSize(), string(" len="), len(text), string(" indexat="), r.indexStartsAt(),
             string(" unused="), r.firstUnusedName(), string(" directives="), r.processDirectives(),
             string(" startsWith="), r.startsWith(string("(stmts")), string(" "), r.startsWith(string("(.nif")))
        with let:
            start = r.offset()
        _dump(r)
        # back to the first node: the same tokens again
        r.jumpTo(start)
        with var:
            tok = default(ExpandedToken)
        r.next(tok)
        echo(string("jumped: "), _show(r, tok), string(" offset="), r.offset() - start)
        close(r)
        removeFile(path)
        # from a buffer, with the symbols split
        with var:
            b = openFromBuffer(text, string("Buf"))
        b.splitSymbols()
        echo(string("split: "), b.symbolsAreSplit(), string(" unused="), b.firstUnusedName())
        _dump(b)
        close(b)

    _test_nifreader_dump()
