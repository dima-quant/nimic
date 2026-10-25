# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifcore.nim
# ///
## nifcore — in-memory NIF representation, builder, and cursor.
##
## Design summary
## ==============
##
## A NIF token is a `distinct uint32` (4 bytes) with the kind in the low
## 4 bits and a 28-bit kind-specific payload above.
##
## There is **no separate ParLe / ParRi** kind — a node is just a `TagLit`
## that carries (tag, jump), where `jump` counts the body tokens that
## follow. The matching close is implicit; iterators stop after consuming
## `jump` body tokens.
##
## ```
##   TagLit payload (28 bits):
##     [3..0]   kind = TagLit
##     [12..4]  tag  (9 bits, 0..511)
##     [31..13] jump (19 bits, 0..524287 body tokens)
## ```
##
## Atom kinds (`StrLit`, `IntLit`, `FloatLit`, …) put a 28-bit pool id (or
## a small inline value, e.g. `CharLit`) in the payload.
##
## **ExtendedSuffix** is the universal extension knob — one kind handles
## both literal overflow and jump overflow uniformly:
##
##   Atoms with wide payload:
##     [P]   StrLit(low28)
##     [P+1] ExtendedSuffix(high28)            ⇒ 56-bit combined id
##
##   TagLits with overflowing jump:
##     [P]   TagLit(tag, jump_low19)
##     [P+1] ExtendedSuffix(jump_high28)       ⇒ 47-bit combined jump
##     [P+2 .. P+1+combined_jump] body
##
## Putting the extension *after* the kinded token means a cursor always
## lands on the kinded token; `kind(c)` is one load + one mask (no
## branch). The suffix is only consulted by the helpers that actually
## need extended bits (`combinedPayload`, `cursorJump`, `tokenWidth`).
##
## Pool ownership is per-`TokenBuf` by default; pass `sharedPool` to
## `createTokenBuf` to thread the same intern tables through many trees.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    # Generic bodies (e.g. `createTags[E: enum]`) and `untyped`-pool templates
    # are sem-checked at instantiation, Nim-2 style — matches how this file
    # compiles under host Nim. Unknown pragma on host Nim, hence the guard.
    pragma('feature: "untyped"')
    # `ref` fields/returns are nilable here (e.g. `pool`/`tags` return nil for
    # an ownerless cursor); opt out of Nimony's strict not-nil analysis.
    pragma('feature: "lenientnils"')
    # The `fallbackPool`/`fallbackTags` globals are shared by every ownerless
    # `TokenBuf`; the compiler is single threaded.
    pragma('feature: "assumeSync"')
else:
    # Dual-compiled: nimony builds this for the compiler, host Nim for `nifler`.
    # `alwaysInline` is a nimony pragma; give host Nim the nearest thing it has.
    pragma("pragma: alwaysInline, inline")
    # `assertionsEnabled` comes from nimony's `std/assertions`; host Nim spells the
    # same question `compileOption`. (`raiseAssert` it already has, in `system`.)
    with const:
        assertionsEnabled = compileOption("assertions")

from nimic.std.assertions import *
from nimic.std.hashes import *
from .bitabs import *
from .lineinfos import *
from .nifroles import *
from . import bitabs, lineinfos, nifroles
with export:
    nifroles  # a `{.nifWrap.}` in a template body is resolved where it expands
with export:
    bitabs  # adapters touching pool.strings / tags need getOrIncl etc.
with export:
    lineinfos.FileId, lineinfos.NoFile, lineinfos.isValid, lineinfos.__eq__, lineinfos.hash


class NifKind(NIntEnum):
    DotToken = auto()
    CharLit = auto()
    StrLit = auto()
    IntLit = auto()
    UIntLit = auto()
    FloatLit = auto()
    Symbol = auto()
    SymbolDef = auto()
    Ident = auto()
    TagLit = auto()            # opening tag with body-token-count "jump"
    ExtendedSuffix = auto()    # supplies 28 extra high bits to the preceding token
    LineInfoLit = auto()       # trailing line-info suffix on a head token (file/line/col)
    # ── reader-level lexical kinds ────────────────────────────────────────
    # Produced only by the textual NIF reader (nifreader.ExpandedToken.tk);
    # they never occur in a binary token stream, where parens are implicit
    # (TagLit + jump) and EOF is `not hasMore`. Sharing ONE enum keeps every
    # token-kind consumer (including external ones like Nim's ast2nif.nim)
    # on a single type. The 16 members exactly fill the 4-bit kind field.
    UnknownToken = auto()      # lexical error / unclassified byte sequence
    EofToken = auto()          # end of input
    ParLe = auto()             # textual '('
    ParRi = auto()             # textual ')'


@distinct
class NifToken(uint32):
    def __eq__(a: NifToken, b: NifToken) -> bool:
        """{.borrow, noSideEffect.}"""
        return super().__eq__(b)


@distinct
class TagId(uint32):
    def __eq__(a: TagId, b: TagId) -> bool:
        """{.borrow, noSideEffect.}"""
        return super().__eq__(b)

    def hash(x: TagId) -> Hash:
        """{.borrow, noSideEffect.}"""
        return hash(uint32(x))

    def __str__(x: TagId) -> string:
        """{.borrow.}"""
        return string(str(uint32(x)))


@distinct
class StrId(uint32):
    def __eq__(a: StrId, b: StrId) -> bool:
        """{.borrow, noSideEffect.}"""
        return super().__eq__(b)

    def hash(x: StrId) -> Hash:
        """{.borrow, noSideEffect.}"""
        return hash(uint32(x))

    def __str__(x: StrId) -> string:
        """{.borrow.}"""
        return string(str(uint32(x)))


@distinct
class SymId(uint32):
    def __eq__(a: SymId, b: SymId) -> bool:
        """{.borrow, noSideEffect.}"""
        return super().__eq__(b)

    def hash(x: SymId) -> Hash:
        """{.borrow, noSideEffect.}"""
        return hash(uint32(x))

    def __str__(x: SymId) -> string:
        """{.borrow.}"""
        return string(str(uint32(x)))

# ── bit-packing constants ────────────────────────────────────────────────

with const:
    KindBits = u32(4)
    KindMask = (u32(1) << KindBits) - u32(1)       # 0x0F
    PayloadBits = u32(32) - KindBits                  # 28
    PayloadMask = (u32(1) << PayloadBits) - u32(1)    # 0x0FFFFFFF
    IdPayloadMax = PayloadMask >> u32(1)

    TagBits = u32(9)
    TagShift = KindBits                           # 4
    TagMask = (u32(1) << TagBits) - u32(1)        # 0x1FF
    JumpShift = KindBits + TagBits                 # 13
    JumpBits = u32(32) - JumpShift                 # 19
    InlineJumpCap = (u32(1) << JumpBits) - u32(1)     # 524287


@dispatch
def kind(n: NifToken) -> NifKind:
    """{.inline.}"""
    return NifKind(uint32(n) & KindMask)
    ## A `proc` (not a `template`) so downstream `export … except kind` can drop
    ## it — nimony's `except` cannot filter a name that has a template overload.


@template
def uoperand(n: NifToken) -> uint32:
    return uint32(n) >> KindBits


@template
def soperand(n: NifToken) -> int32:
    ## Sign-extended 28-bit payload (for inline signed values).
    return cast[int32](uint32(n)) >> int32(KindBits)


@template
def _toX(k: NifKind, operand: uint32) -> uint32:
    return uint32(k) | (operand << KindBits)

# ── atom constructors ────────────────────────────────────────────────────


def dotToken() -> NifToken:
    """{.inline.}"""
    return NifToken(uint32(NifKind.DotToken))

# ── assertion failure helpers ────────────────────────────────────────────
#
# An `assert` whose message is COMPUTED (`"… " & $n.kind`) puts the string
# building in the proc's body. The build is cold — `assert` only runs it on
# failure — but its mere presence makes the proc a NON-LEAF, and arkham then
# homes locals in callee-saved registers and pushes them on every call. Measured:
# `tagLitToken`, a shift and an or, made two calls and pushed all six
# callee-saved registers for 35 instructions per call.
#
# Hoisting the message into a `{.noinline, noreturn.}` proc fixes it without
# losing a single diagnostic: arkham does not treat a `noreturn` callee as a call
# point (see `analyser.noReturnCallees`), so the caller stays a leaf. The `when
# assertionsEnabled` keeps `-d:danger` / `-d:noAssertions` behaviour identical to
# the `assert` it replaces.


def _failKind(what: string, k: NifKind):
    """{.noinline, noreturn.}"""
    raiseAssert(what + str(k))


def _failVal(what: string, v: uint32, tail: string):
    """{.noinline, noreturn.}"""
    raiseAssert(what + str(v) + tail)


@template
def _checkKind(cond: bool, what: string, k: NifKind):
    if comptime(assertionsEnabled):
        if not cond:
            _failKind(what, k)


@template
def _checkVal(cond: bool, what: string, v: uint32, tail: string):
    if comptime(assertionsEnabled):
        if not cond:
            _failVal(what, v, tail)


def tagLitToken(t: TagId, jump: uint32 = u32(0)) -> NifToken:
    """{.inline.}"""
    with let:
        tagBits = uint32(t) & TagMask
    _checkVal(uint32(t) == tagBits, string("tag id "), uint32(t), string(" exceeds 9 bits"))
    assert jump <= InlineJumpCap, "use ExtendedSuffix for jump > InlineJumpCap"
    return NifToken(uint32(NifKind.TagLit) | (tagBits << TagShift) | (jump << JumpShift))


def charToken(ch: char) -> NifToken:
    """{.inline.}"""
    return NifToken(_toX(NifKind.CharLit, uint32(ch)))

# Raw pool-ref constructors. They do NOT apply the writer's inline rule (see
# "String/sym layout" below), so a name of at most `StrInlineMaxLen` bytes gets
# an encoding the builders would never produce. Reach for `internedSymToken` /
# the `add*` builders unless you own both ends of the encoding. The `IdPayloadMax`
# bound is `PayloadMask shr 1` because one bit goes to the inline/pool-ref flag,
# so a larger id would overflow the payload instead of widening into an
# `ExtendedSuffix` (which a single token cannot express).


def strLitToken(id: StrId) -> NifToken:
    """{.inline.}"""
    assert uint32(id) <= IdPayloadMax
    return NifToken(_toX(NifKind.StrLit, uint32(id) << u32(1)))    # bit 0 = 0 ⇒ pool ref


def symToken(id: SymId) -> NifToken:
    """{.inline.}"""
    assert uint32(id) <= IdPayloadMax
    return NifToken(_toX(NifKind.Symbol, uint32(id) << u32(1)))


def symdefToken(id: SymId) -> NifToken:
    """{.inline.}"""
    assert uint32(id) <= IdPayloadMax
    return NifToken(_toX(NifKind.SymbolDef, uint32(id) << u32(1)))


def identToken(id: StrId) -> NifToken:
    """{.inline.}"""
    assert uint32(id) <= IdPayloadMax
    return NifToken(_toX(NifKind.Ident, uint32(id) << u32(1)))


def extendedSuffixToken(high28: uint32) -> NifToken:
    """{.inline.}"""
    assert high28 <= PayloadMask
    return NifToken(_toX(NifKind.ExtendedSuffix, high28))

# ── Line info (LineInfoLit) ──────────────────────────────────────────────
# Line info is sparse: a `LineInfoLit` rides as a trailing suffix on a head
# token (after any value/jump `ExtendedSuffix`), emitted only where the
# position changes. The file is a `FileId` interned in `pool.filenames`;
# line/col are inline. Two fixed layouts of the (possibly suffix-extended)
# payload, chosen by whether the `LineInfoLit` carries its own trailing
# `ExtendedSuffix` (detected structurally — no flag bit):
#
#   Common (no suffix, 28 bits):  col 7 | file 7  | line 14
#   Overflow (one suffix, 56 bits): col 10 | file 14 | line 32
#
# Common matches nimony's `lineinfos` field sizes (line 14, col 7); file is
# trimmed 10→7. Any field past its common width bumps the whole value to the
# overflow layout.
#
# An optional `#comment#` decoration (a `StrId` into `pool.strings`) rides as
# one further `ExtendedSuffix` after the position word. To keep the layout
# selectable structurally (still no flag bit), a comment ALWAYS forces the
# overflow position layout, so the count `k` of `ExtendedSuffix` words trailing
# the `LineInfoLit` decodes unambiguously:
#   k == 0  →  common position, no comment
#   k == 1  →  overflow position, no comment   (the two pre-comment cases)
#   k >= 2  →  overflow position (word 0) + comment id in words 1.. (28-bit
#             chunks, low first; a 2nd word only for ids past 2^28)
# The head-skip walk (`tokenWidth`, `kind >= ExtendedSuffix`) already absorbs
# these extra words, so navigation needs no change.

with const:
    LiColBitsC = u32(7)
    LiFileBitsC = u32(7)
    LiLineBitsC = u32(14)
    LiColMaxC = (u32(1) << LiColBitsC) - u32(1)      # 127
    LiFileMaxC = (u32(1) << LiFileBitsC) - u32(1)     # 127
    LiLineMaxC = (u32(1) << LiLineBitsC) - u32(1)     # 16383

    _LiColBitsX = u64(10)
    _LiFileBitsX = u64(14)
    _LiColMaskX = (u64(1) << _LiColBitsX) - u64(1)
    _LiFileMaskX = (u64(1) << _LiFileBitsX) - u64(1)
    _LiLineMaskX = (u64(1) << u64(32)) - u64(1)


class NifLineInfo(Object):
    file: FileId
    line: int32
    col: int32
    comment: StrId
    ## Optional NIF `#…#` decoration on the head, interned in `pool.strings`
    ## (`StrId(0)` = none). Carried in the `LineInfoLit` suffix; see below.

    def isValid(x: NifLineInfo) -> bool:
        """{.inline.}"""
        return isValid(x.file)

    def __eq__(a: NifLineInfo, b: NifLineInfo) -> bool:
        """{.inline, noSideEffect.}"""
        ## Explicit because Nimony does not synthesize structural `==`/`hash` for
        ## objects (frontend code keeps infos in HashSets, e.g. error dedup).
        return (a.file == b.file and a.line == b.line and a.col == b.col and
                a.comment == b.comment)

    def hash(x: NifLineInfo) -> Hash:
        """{.inline, noSideEffect.}"""
        return hash((uint64(uint32(x.file)) << u64(32)) ^ (uint64(cast[uint32](x.line)) << u64(16)) ^
                    (uint64(cast[uint32](x.col)) << u64(8)) ^ uint64(uint32(x.comment)))


with const:
    NoNifLineInfo = NifLineInfo(file=NoFile, line=i32(0), col=i32(0),
                                comment=StrId(u32(0)))


def _fitsCommonLineInfo(file: FileId, line: int32, col: int32) -> bool:
    """{.inline.}"""
    return (uint32(file) <= LiFileMaxC and uint32(col) <= LiColMaxC and
            uint32(line) <= LiLineMaxC)


def _encodeLineInfoCommon(file: FileId, line: int32, col: int32) -> uint32:
    """{.inline.}"""
    return ((uint32(col) & LiColMaxC) |
            ((uint32(file) & LiFileMaxC) << LiColBitsC) |
            ((uint32(line) & LiLineMaxC) << (LiColBitsC + LiFileBitsC)))


def _encodeLineInfoWide(file: FileId, line: int32, col: int32) -> uint64:
    """{.inline.}"""
    return ((uint64(col) & _LiColMaskX) |
            ((uint64(file) & _LiFileMaskX) << _LiColBitsX) |
            ((uint64(line) & _LiLineMaskX) << (_LiColBitsX + _LiFileBitsX)))

# ── TagLit field accessors (raw — don't consult the suffix) ──────────────


def _rawJump(n: NifToken) -> uint32:
    """{.inline.}"""
    _checkKind(kind(n) == NifKind.TagLit, string("rawJump on "), kind(n))
    return uint32(n) >> JumpShift


def _rawTag(n: NifToken) -> TagId:
    """{.inline.}"""
    _checkKind(kind(n) == NifKind.TagLit, string("rawTag on "), kind(n))
    return TagId((uint32(n) >> TagShift) & TagMask)


def setJump(n: mut @ NifToken, j: uint32):
    """{.inline.}"""
    _checkKind(kind(n) == NifKind.TagLit, string("setJump on "), kind(n))
    _checkVal(j <= InlineJumpCap, string("jump "), j, string(" exceeds 19 bits"))
    with let:
        preserved = uint32(n) & ((u32(1) << JumpShift) - u32(1))  # kind+tag
    n <<= NifToken(preserved | (j << JumpShift))


def setTag(n: mut @ NifToken, t: TagId):
    """{.inline.}"""
    _checkKind(kind(n) == NifKind.TagLit, string("setTag on "), kind(n))
    with let:
        tagBits = uint32(t) & TagMask
    _checkVal(uint32(t) == tagBits, string("tag id "), uint32(t), string(" exceeds 9 bits"))
    n <<= NifToken((uint32(n) & ~(KindMask | (TagMask << TagShift))) |
                   uint32(NifKind.TagLit) | (tagBits << TagShift))

# ── Pool (literals) and TagPool (tags) ───────────────────────────────────
# Two refs, deliberately split:
#
# * `Pool` (literals) is sharable across adapters — a string is a string,
#   whether it came from JSON or HTML, and cross-format dedup is the
#   whole point.
# * `TagPool` is language-specific. Each adapter creates its own and
#   registers its tag enum in ordinal order at startup, so the resulting
#   TagId equals the enum ordinal and `cast[MyTag](c.cursorTagId.uint32)`
#   is a register-to-register move with no memory access. Sharing a tag
#   pool across adapters destroys that property and gives no benefit
#   (tag namespaces don't overlap meaningfully).

# ── Symbols are objects, not strings (#2457) ─────────────────────────────
#
# A NIF symbol is `<name>.<disamb>`, `<name>.<disamb>.<module>` or
# `<name>.<disamb>.<dedup>.<module>`, and the rest of the compiler used to take
# that apart again at every question it asked. The pool STORES the taken-apart
# form, so every question below is a field read and nothing re-derives anything.


class NifSymbol(Object):
    ## A NIF symbol, taken apart. The three names are ids into `Pool.strings`:
    ## a module suffix is repeated by every symbol that comes from that module
    ## (54 modules for 8044 symbols in a typical nimsem module), so asking
    ## "same module?" must not mean building two strings and comparing them.
    name: StrId
    disamb: int32
    ## `NoDisamb` when the spelling has none that is a NUMBER -- then `name`
    ## holds everything up to the module suffix, and the symbol round-trips
    ## unchanged. That covers an atom that is not a symbol at all (`[]=`) and
    ## the reserved disambiguators older artifacts still carry
    ## (`_exit.sys.mod`, `p.0h107`).
    dedup: StrId   ## `StrId(0)` unless the symbol is a generic instantiation
    module: StrId  ## `StrId(0)` for a local symbol

    def __eq__(a: NifSymbol, b: NifSymbol) -> bool:
        """{.inline.}"""
        return (a.name == b.name and a.disamb == b.disamb and
                a.dedup == b.dedup and a.module == b.module)

    def hash(s: NifSymbol) -> Hash:
        ## Four ids mixed, not a string walked: this is what the pool hashes on every
        ## intern, and the reason interning a symbol stopped costing a string hash.
        with var:
            h = uint64(uint32(s.name)) * u64(0x9E3779B97F4A7C15)
        h = (h ^ uint64(uint32(s.disamb))) * u64(0x9E3779B97F4A7C15)
        h = (h ^ uint64(uint32(s.dedup))) * u64(0x9E3779B97F4A7C15)
        h = (h ^ uint64(uint32(s.module))) * u64(0x9E3779B97F4A7C15)
        result = cast[Hash](h)
        return result


with const:
    NoDisamb = i32(-1)


@ref
class Pool(Object):
    ## Pool pool — only categories where dedup genuinely pays:
    ## strings and symbols. Integers / unsigned integers / floats are
    ## stored entirely inside the token stream (using a chain of
    ## `ExtendedSuffix` tokens to widen the carrier), so there's no
    ## pool for them — no hash lookups, no auto-tune machinery.
    strings:   BiTable[StrId, string]
    symbols:   BiTable[SymId, NifSymbol]
    filenames: BiTable[FileId, string]
    ## Source filenames referenced by `LineInfoLit` tokens. Line/col are
    ## encoded inline in the token; only the filename is interned here.


@ref
class TagPool(Object):
    tags: BiTable[TagId, string]
    ## Tag spelling ⇔ id, and NOT bounded by the 9-bit tag field: ids past
    ## `TagMask` are perfectly legal, they just cost a second token to spell
    ## (see `escapeTag`).
    escapeTag: TagId
    ## The **escape tag** of this adapter, or `0` if it has none.
    ##
    ## A tag id is 9 bits in the token (`TagBits`), so the first 511 tags cost
    ## one token. That is ample for a language vocabulary and hopeless for an
    ## instruction set: nativenif alone spells 282 machine mnemonics, and each
    ## further target (Cortex-M, RISC-V) wants a few hundred more.
    ##
    ## Rather than cap the pool there, an adapter may nominate one tag as the
    ## escape: an id that does not fit is then stored as `(<escapeTag> <id> …)`,
    ## the id carried by an ordinary inline `IntLit` first child. `openTag`
    ## does that itself and the serializers undo it, so the NIF *text* is
    ## unchanged, the binary token format is unchanged, and the pool is
    ## effectively unbounded. Only the ids past `TagMask` pay the extra token.
    ##
    ## What an adapter DOES have to know is that an escaped node's id is not
    ## `cursorTagId` (ask `resolvedTagId`) and that its operands start one
    ## token later.


def newPool() -> Pool:
    return Pool(strings=initBiTable[StrId, string](),
                symbols=initBiTable[SymId, NifSymbol](),
                filenames=initBiTable[FileId, string]())


def newTagPool() -> TagPool:
    ## All BiTable ids start at 1 (id 0 is the "not used" sentinel).
    ## Adapters whose enum has ordinal 0 as the first real value bridge
    ## the gap with a `+/- 1` shim in their `tagId` / `myKind` helpers
    ## (see jsonnif/htmlnif).
    return TagPool(tags=initBiTable[TagId, string](), escapeTag=TagId(u32(0)))


def registerTag(tp: TagPool, tag: string) -> TagId:
    ## Intern a tag string. Adapters call this in enum-ordinal order at
    ## startup so the returned TagId equals the enum ordinal (1-based).
    return tp.tags.getOrIncl(tag)


with const:
    FirstEscapeId = TagMask + u32(1)
    ## The first tag id that no longer fits the 9-bit tag field, hence the first
    ## one an adapter must spell through its `escapeTag`. Registering tags is
    ## otherwise unaffected: `registerTag` keeps counting.


@template
def hasEscapes(tp: TagPool) -> bool:
    return tp.escapeTag != TagId(u32(0))


@generic
def createTags[E: enum]() -> TagPool:
    ## One-shot tag-pool builder for an adapter's enum. Registers every
    ## value of `E` in ordinal order using its string form (`$e`), so the
    ## resulting TagIds are `1, 2, …` matching the `tagId` / `myKind`
    ## `+/- 1` shim. Replaces hand-rolled `createJsonTagPool` /
    ## `createHtmlTagPool` boilerplate.
    ##
    ## The assertion guards against an enum with holes or out-of-order
    ## ordinals — those would silently break the `cast[E](tagId-1)` path.
    result = newTagPool()
    for e in inrange(low(E), high(E)):
        with let:
            id = result.registerTag(str(e))
        assert uint32(id) == uint32(e) + u32(1), (
            string("createTags: enum/TagId misalignment for ") + str(e) + string(" (got id ") + str(id) + string(")"))
    return result


@template
def tagName(tp: TagPool, t: TagId) -> lent @ string:
    return tp.tags[t]
# Direct pool lookups (only meaningful for pool-mode payloads — inline
# strings/syms don't have ids). Prefer the cursor-side `strVal(c)` /
# `symName(c)` accessors which handle both modes transparently.


@template
def poolStr(p: Pool, s: StrId) -> lent @ string:
    return p.strings[s]

# ── Asking a symbol what it is ───────────────────────────────────────────


def sym(p: Pool, id: SymId) -> NifSymbol:
    """{.inline.}"""
    ## The symbol `id`, taken apart. A field read.
    return p.symbols[id]


def _strOrEmpty(p: Pool, s: StrId) -> string:
    """{.inline.}"""
    return string("") if s == StrId(u32(0)) else p.strings[s]


def symBasename(p: Pool, id: SymId) -> string:
    ## The identifier of `id`, without disambiguator, key or module suffix:
    ## `abc.12.Ikey.mod` gives `abc`. A name may contain dots itself
    ## (`Pool.Obj.0` gives `Pool.Obj`), and an atom that is not a symbol at all
    ## gives `""` -- it has no identifier to name.
    with let:
        s = p.symbols[id]
    return string("") if s.disamb == NoDisamb else p.strings[s.name]


def symNameId(p: Pool, id: SymId) -> StrId:
    """{.inline.}"""
    ## `symBasename` as an id -- the one to compare identifiers by.
    return p.symbols[id].name


def symVersionedBasename(p: Pool, id: SymId) -> string:
    ## The identifier AND its disambiguator, without key or module suffix:
    ## `abc.12.Ikey.mod` gives `abc.12`. That is a name for the ROUTINE, not for
    ## one instantiation of it -- `symWithoutModule` is the one that keeps the
    ## key. An atom that is not a symbol gives `""`.
    with let:
        s = p.symbols[id]
    if s.disamb == NoDisamb:
        result = string("")
    else:
        result = p.strings[s.name].copy()
        result.add(ch("."))
        result.addInt(s.disamb)
    return result


def symIsInstantiation(p: Pool, id: SymId) -> bool:
    ## Whether `id` carries a deduplication key -- the `Ikey` of
    ## `abc.12.Ikey.mod`, which every module needing that instantiation derives
    ## the same way. That is what makes `symWithoutModule` a cross-module
    ## identity for it and only for it.
    ##
    ## ONE key, spelled the way nimony spells one: a name with two of them
    ## (`foo.0.Ia.Ib.mod`) is not an instantiation of anything this toolchain
    ## minted, and nifasm merges symbols by this answer -- it once hand-rolled
    ## its own and merged such a name wrongly.
    with let:
        d = p.symbols[id].dedup
    if d == StrId(u32(0)):
        return False
    with let:
        key = p.strings[d]
    if key.len == 0 or key[0] != ch("I"):
        return False
    for c in key:
        if c == ch("."):
            return False
    result = True
    return result


def symWithoutModule(p: Pool, id: SymId) -> string:
    ## `id` minus its module suffix: `abc.12.Ikey.mod` gives `abc.12.Ikey`, and a
    ## local symbol gives itself. For an instantiation this is the name every
    ## module that needs it arrives at independently, so it is the key to merge
    ## the copies by -- DCE, the type-key builder and overload resolution all use
    ## it for exactly that.
    with let:
        s = p.symbols[id]
    result = p.strings[s.name].copy()
    if s.disamb != NoDisamb:
        result.add(ch("."))
        result.addInt(s.disamb)
    if s.dedup != StrId(u32(0)):
        result.add(ch("."))
        result.add(p.strings[s.dedup])
    return result


def symSameEntity(p: Pool, a: SymId, b: SymId) -> bool:
    ## Whether two DIFFERENT symbols name the same entity seen from two modules:
    ## both are instantiations and everything but the module suffix matches.
    if a == b:
        return True
    with let:
        sa = p.symbols[a]
    with let:
        sb = p.symbols[b]
    result = (sa.dedup != StrId(u32(0)) and sa.dedup == sb.dedup and
              sa.name == sb.name and sa.disamb == sb.disamb)
    return result


def symModule(p: Pool, id: SymId) -> string:
    """{.inline.}"""
    ## The module suffix of `id`, `""` when it is local. For the places that need
    ## the suffix as a string -- a table key, a file name, a `(strlit)` -- while
    ## `sym(p, id).module` is what a COMPARISON should use.
    return _strOrEmpty(p, p.symbols[id].module)


def symIsLocal(p: Pool, id: SymId) -> bool:
    """{.inline.}"""
    ## Whether `id` has no module suffix. A question about the module, never
    ## about how many dots the spelling has: real names contain dots
    ## (`Pool.Obj`, `dollar`.CaseMode`, `..<`).
    return p.symbols[id].module == StrId(u32(0))


def symModuleIs(p: Pool, id: SymId, suffix: string) -> bool:
    ## Whether `id` comes from the module `suffix`. Builds nothing.
    with let:
        m = p.symbols[id].module
    result = m != StrId(u32(0)) and p.strings[m] == suffix
    return result


def _digitCount(x: int32) -> nint:
    """{.inline.}"""
    result = 1
    with var:
        v = x // i32(10)
    while v > 0:
        result += 1
        v = v // i32(10)
    return result


def symSpellingLen(p: Pool, id: SymId) -> nint:
    ## How long `symString` would be, without building it. The token writers ask
    ## only to decide whether the name fits inside the token itself.
    with let:
        s = p.symbols[id]
    result = p.strings[s.name].len
    if s.disamb != NoDisamb:
        result += 1 + _digitCount(s.disamb)
    if s.dedup != StrId(u32(0)):
        result += 1 + p.strings[s.dedup].len
    if s.module != StrId(u32(0)):
        result += 1 + p.strings[s.module].len
    return result


@dispatch
def symString(p: Pool, s: NifSymbol) -> string:
    ## The spelling `s` would be interned under.
    result = p.strings[s.name].copy()
    if s.disamb != NoDisamb:
        result.add(ch("."))
        result.addInt(s.disamb)
    if s.dedup != StrId(u32(0)):
        result.add(ch("."))
        result.add(p.strings[s.dedup])
    if s.module != StrId(u32(0)):
        result.add(ch("."))
        result.add(p.strings[s.module])
    return result


@dispatch
def symString(p: Pool, id: SymId) -> string:
    """{.inline.}"""
    ## The whole spelling of `id`. Builds a string, so it is for the places that
    ## genuinely need one -- the C mangler, error messages, serialization -- and
    ## never for asking a question the accessors above answer.
    return symString(p, p.symbols[id])


with const:
    DisambMax = nint(high(int32))
    ## Largest disambiguator `NifSymbol.disamb` can hold.


def parseDisamb(s: string, start: nint, len: nint) -> nint:
    ## The value of the disambiguator spelled by `s[start ..< start+len]`, or -1
    ## when that is not how NIF spells a number:
    ##
    ## * digits only -- `p.0h107` names no `p` with a disambiguator;
    ## * no leading zero -- `d.00` is a NAME, and deliberately so: no user symbol
    ##   can collide with a field the compiler injects (`typenav.DataField`);
    ## * small enough to fit the field.
    ##
    ## A spelling that fails any of these keeps its tail inside the NAME, which is
    ## what lets every symbol round-trip through the pool unchanged. The reader's
    ## split-symbol path asks this too, so the two agree about the same bytes.
    if len == 0:
        return -1
    if len > 1 and s[start] == ch("0"):
        return -1
    result = 0
    for i in range(start, start + len):
        if s[i] not in Tset[char](inrange(ch("0"), ch("9"))):
            return -1
        result = result * 10 + (ord(s[i]) - ord(ch("0")))
        if result > DisambMax:
            return -1
    return result


class _Spelling(Object):
    ## Where each part of `<name>.<disamb>[.<dedup>].<module>` sits inside the
    ## string that spells it. Private: it exists to build a `NifSymbol` and to
    ## look one up, and both are here.
    _nameLen: nint
    _disamb: int32          ## `NoDisamb` when there is none that is a number
    _dedupStart: nint
    _dedupLen: nint
    _moduleStart: nint
    _moduleLen: nint


def _splitSpelling(s: string) -> _Spelling:
    ## The module is the LAST dot-separated component -- unless it STARTS with a
    ## digit, which makes it the disambiguator and the symbol local. `p.0h107` is
    ## a local whose disambiguator an inliner minted, not a symbol from a module
    ## called `0h107`.
    ##
    ## The name/disambiguator boundary needs the digit anchor, because a name may
    ## contain dots itself (`Pool.Obj.0`, `a.b.c.23`, `..<.3`) and only the digit
    ## tells the two apart. Everything not accounted for stays in the name.
    result = _Spelling(_nameLen=s.len, _disamb=NoDisamb,
                       _dedupStart=0, _dedupLen=0, _moduleStart=0, _moduleLen=0)
    with var:
        lastDot = -1
    for k in range(0, s.len):
        if s[k] == ch("."):
            lastDot = k
    with var:
        head = s.len
    if lastDot >= 0:
        if lastDot + 1 < s.len and s[lastDot + 1] not in Tset[char](inrange(ch("0"), ch("9"))):
            result._moduleStart = lastDot + 1
            result._moduleLen = s.len - (lastDot + 1)
            head = lastDot
        elif lastDot == s.len - 1:
            head = lastDot
    result._nameLen = head

    with var:
        i = head - 2
    while i > 0:
        if s[i] == ch(".") and s[i + 1] in Tset[char](inrange(ch("0"), ch("9"))):
            break
        i -= 1
    if i <= 0:
        return result  # no numeric disambiguator: the head is all name

    with var:
        d = i + 1
    while d < head and s[d] in Tset[char](inrange(ch("0"), ch("9"))):
        d += 1
    with var:
        disambLen = head - (i + 1)
    if d < head and s[d] == ch("."):
        disambLen = d - (i + 1)
    with let:
        v = parseDisamb(s, i + 1, disambLen)
    if v < 0:
        return result   # `p.0h107`, `d.00`: it belongs to the name
    result._nameLen = i
    result._disamb = int32(v)
    if d < head and s[d] == ch("."):
        result._dedupStart = d + 1
        result._dedupLen = head - (d + 1)
    return result


def symRecord(p: Pool, s: string) -> NifSymbol:
    ## Take a spelling apart into the record the pool stores, interning each
    ## component. Every spelling round-trips: one whose disambiguator is not a
    ## NUMBER keeps it inside the name (`NoDisamb`), so the reserved forms older
    ## artifacts carry (`_exit.sys.mod`, `p.0h107`) come back out unchanged.
    assert s.len == 0 or s[s.len - 1] != ch("."), (
        string("a symbol reaches the pool with its module suffix expanded, never as `") + s + string("`"))
    with let:
        sl = _splitSpelling(s)
    result = NifSymbol(name=p.strings.getOrIncl(substr(s, 0, sl._nameLen - 1)),
                       disamb=sl._disamb, dedup=StrId(u32(0)), module=StrId(u32(0)))
    if sl._dedupLen > 0:
        result.dedup = p.strings.getOrIncl(substr(s, sl._dedupStart,
                                                  sl._dedupStart + sl._dedupLen - 1))
    if sl._moduleLen > 0:
        result.module = p.strings.getOrIncl(substr(s, sl._moduleStart,
                                                   sl._moduleStart + sl._moduleLen - 1))
    return result


@dispatch
def symId(p: Pool, s: string) -> SymId:
    """{.inline.}"""
    ## Intern a symbol given its whole spelling. This is what the reader and the
    ## deserializers have; code that MINTS a symbol should say what its parts are
    ## instead (the overload below).
    return p.symbols.getOrIncl(symRecord(p, s))


@dispatch
def symId(p: Pool, name: string, disamb: nint, module: string = string(""), dedup: string = string("")) -> SymId:
    ## Intern a symbol from its parts. `module` empty means a local symbol.
    with var:
        r = NifSymbol(name=p.strings.getOrIncl(name), disamb=int32(disamb),
                      dedup=StrId(u32(0)), module=StrId(u32(0)))
    if dedup.len > 0:
        r.dedup = p.strings.getOrIncl(dedup)
    if module.len > 0:
        r.module = p.strings.getOrIncl(module)
    result = p.symbols.getOrIncl(r)
    return result


@dispatch
def symId(p: Pool, s: NifSymbol) -> SymId:
    """{.inline.}"""
    return p.symbols.getOrIncl(s)


def isLocal(s: NifSymbol) -> bool:
    """{.inline.}"""
    return s.module == StrId(u32(0))

# ── The classic string-shaped view of the symbol pool ────────────────────
#
# The Nim compiler's IC modules speak to the symbol pool as a
# `BiTable[SymId, string]`, and ask it exactly four things:
# `pool.syms.getOrIncl(name)`, `pool.syms[id]`, `pool.syms.getKeyId(name)` and
# `poolSym(pool, id)`. That is the surface `lib/nifstreams.nim` exists to keep
# working, and it must keep working THROUGH the flip (#2457): the pool stores
# `NifSymbol` records now, so `syms` is a view answering those questions with
# `symId` / `symString`.
#
# Twelve files in `nim/compiler` import this library, and CI is the only place
# they are COMPILED against it: its setup symlinks `nim/dist/nimony` to the
# nimony checkout, while a local Nim has a copy of its own. So a change to the
# names below builds green here and red there -- keep them, or fix Nim first.
#
# Nimony's own code does not use it: it asks the accessors above, which do not
# build a string to ask a question.


class SymPool(Object):
    # NOT named `p`: the constructor below is written inside a template whose
    # parameter would then substitute the FIELD name too, and the expansion
    # stops parsing.
    _pool: Pool

    def getOrIncl(s: SymPool, name: string) -> SymId:
        """{.inline.}"""
        return symId(s._pool, name)

    def __getitem__(s: SymPool, id: SymId) -> string:
        """{.inline.}"""
        return symString(s._pool, id)

    @property
    def len(s: SymPool) -> nint:
        """{.inline.}"""
        return len(s._pool.symbols)

    def getKeyId(s: SymPool, name: string) -> SymId:
        ## The id `name` already has, or `SymId(0)` when the pool does not hold it.
        ## Looks up without interning ANYTHING: a component this pool never saw is
        ## proof the symbol is not in it, which is the answer the caller wanted.
        ensureIndexed(s._pool.strings)
        ensureIndexed(s._pool.symbols)
        with let:
            sl = _splitSpelling(name)
        with var:
            r = NifSymbol(name=s._pool.strings.getKeyId(substr(name, 0, sl._nameLen - 1)),
                          disamb=sl._disamb, dedup=StrId(u32(0)), module=StrId(u32(0)))
        if sl._dedupLen > 0:
            r.dedup = s._pool.strings.getKeyId(substr(name, sl._dedupStart,
                                                      sl._dedupStart + sl._dedupLen - 1))
            if r.dedup == StrId(u32(0)):
                return SymId(u32(0))
        if sl._moduleLen > 0:
            r.module = s._pool.strings.getKeyId(substr(name, sl._moduleStart,
                                                       sl._moduleStart + sl._moduleLen - 1))
            if r.module == StrId(u32(0)):
                return SymId(u32(0))
        if r.name == StrId(u32(0)):
            return SymId(u32(0))
        result = s._pool.symbols.getKeyId(r)
        return result


@template
def syms(p: Pool) -> SymPool:
    return SymPool(_pool=p)


@template
def poolSym(p: Pool, s: SymId) -> string:
    return symString(p, s)
    ## The classic name for `symString`, and the fourth thing the Nim compiler's
    ## IC modules ask (`ast2nif.indexFromBif`). It used to yield `lent string`
    ## straight out of the pool; the pool has no string to lend now, so this
    ## builds one -- the callers all wanted a copy anyway (a table key, a name to
    ## re-emit).

# ── Storage / CursorOwner / Cursor ───────────────────────────────────────

_Storage = ptr[UncheckedArray[NifToken]]


class _CursorOwnerObj(Object):
    _rc: nint
    _data: _Storage
    _pool: Pool      ## literals (sharable across adapters)
    _tags: TagPool   ## tag space (per-adapter)
    ## Both ref-tracked manually via GC_ref/GC_unref since this object
    ## lives in raw `alloc`'d memory and ARC won't trace ref fields here.


_CursorOwner = ptr[_CursorOwnerObj]


class Cursor(Object):
    _owner: _CursorOwner
    _p: ptr[NifToken]
    _rem: nint


class CursorScope(Object):  ## Saved outer bounds for bounded cursor traversal.
    _savedP: ptr[NifToken]
    _savedRem: nint
    _bodyLen: nint


def _decRcAndFree(owner: _CursorOwner):
    ## A proc, NOT a template and deliberately NOT `.inline`: this is the cold
    ## free path behind every `=destroy`/`=dup` hook. As a template it was
    ## expanded into the hooks' bodies, so the (correctly) `.inline` hooks
    ## dragged the whole ORC free machinery into every splice site — the single
    ## largest source of backend IR blowup. As an out-of-line proc the hooks
    ## splice as the few tokens they read as: a nil test and a call.
    owner._rc -= 1
    if owner._rc == 0:
        if not isNil(owner._data):
            dealloc(owner._data)
        if owner._pool is not None:
            GC_unref(owner._pool)
            owner._pool = None
        if owner._tags is not None:
            GC_unref(owner._tags)
            owner._tags = None
        dealloc(owner)


if comptime(defined("nimonyPlugin")):
    # ── The plugin build's process-wide pools ──────────────────────────────
    #
    # A nimony PLUGIN is an executable that transforms one tree in one tag
    # namespace, and `plugins.NifBuilder` is a plain alias for `TokenBuf`, so a
    # plugin author can hand the API a builder `createTree` never minted: an
    # object field, a `default(...)`, a `seq` slot. That API is public and stays
    # total, so the plugin build keeps a process-wide default to bind such a
    # buffer to — `src/nimony/lib/plugins.nim` installs it at module init.
    #
    # `-d:nimonyPlugin` is set by `semos.pluginCompileCmd` for every plugin
    # sub-compile and by nothing else, so the compiler's own nifcore — the
    # subject of nim-lang/nimony#2456 — contains no mutable module-level state
    # whatsoever, and every buffer in it carries pools threaded in at
    # construction.
    with var:
        fallbackPool: Pool = None
        ## Plugin-process default literals pool; nil in every other build.
        fallbackTags: TagPool = None
        ## Plugin-process default tag pool, same contract as `fallbackPool`.

    @template
    def _defaultPool() -> Pool:
        return fallbackPool

    @template
    def _defaultTags() -> TagPool:
        return fallbackTags
else:
    @template
    def _defaultPool() -> Pool:
        return None

    @template
    def _defaultTags() -> TagPool:
        return None


def pool(c: Cursor) -> Pool:
    """{.inline.}"""
    ## Literals pool the cursor's underlying buffer was built against, or the
    ## plugin build's default (`nil` everywhere else) when it carries none.
    return c._owner._pool if not isNil(c._owner) and c._owner._pool is not None else _defaultPool()


def tags(c: Cursor) -> TagPool:
    """{.inline.}"""
    ## Tag pool the cursor's underlying buffer was built against, or the plugin
    ## build's default (`nil` everywhere else) when it carries none. Adapter code
    ## is expected to know which TagPool layout to expect, so callers typically
    ## reach for `cast[MyTag](c.cursorTagId.uint32)` instead of consulting
    ## `c.tags`.
    return c._owner._tags if not isNil(c._owner) and c._owner._tags is not None else _defaultTags()


def escapeTagOf(c: Cursor) -> TagId:
    """{.inline.}"""
    ## The adapter's escape tag, or `TagId(0)` when it declares none — which is
    ## also what a cursor with no tag pool at all answers, since "no escape space"
    ## is exactly what `TagId(0)` means.
    ##
    ## Exists to be read WITHOUT `tags`. `tags` returns the pool BY VALUE, and a
    ## `ref` returned by value is an owned temporary: ARC pairs every call with an
    ## incRef and a decRef, and the decRef has to carry the pool's whole destructor
    ## behind it — a `BiTable` of strings — so the one-line accessor lowers to
    ## several thousand tokens of Leng and stops being inlinable at all. On nifbench
    ## `tags` plus that destructor cost more than `skip` and `symId` together, for a
    ## pool that outlives the program. Reading the field through the raw owner
    ## pointer takes no reference and reaches no hook.
    if not isNil(c._owner) and c._owner._tags is not None:
        result = c._owner._tags.escapeTag
    else:
        result = TagId(u32(0))
        if comptime(defined("nimonyPlugin")):
            if fallbackTags is not None:
                result = fallbackTags.escapeTag
    return result


def toUniqueId(c: Cursor) -> nint:
    """{.inline.}"""
    ## A stable identity for the cursor's *position*: two cursors over the same
    ## buffer at the same token share it, distinct positions differ. Suitable as a
    ## `HashSet[int]`/`IntSet` key (e.g. type-traversal dedup). Not stable across
    ## buffers or runs — it is the underlying token pointer reinterpreted.
    return cast[intp](c._p)


if comptime(defined("nimAllowNonVarDestructor") and defined("gcDestructors")):
    @hook("destroy")
    def destroyCursor(c: Cursor):
        """{.inline.}"""
        if not isNil(c._owner):
            _decRcAndFree(c._owner)
else:
    @hook("destroy")
    def destroyCursor(c: mut @ Cursor):
        """{.inline.}"""
        if not isNil(c._owner):
            _decRcAndFree(c._owner)


@hook("wasMoved")
def wasMovedCursor(c: mut @ Cursor):
    """{.inline.}"""
    c._owner = None
    c._p = None
    c._rem = 0


@hook("copy")
def copyCursor(dest: mut @ Cursor, src: Cursor):
    """{.inline.}"""
    if dest._owner != src._owner or dest._p != src._p:
        destroyCursor(dest)
        if not isNil(src._owner):
            src._owner._rc += 1
        dest._owner = src._owner
        dest._p = src._p
    dest._rem = src._rem


@hook("dup")
def dupCursor(src: Cursor) -> Cursor:
    """{.nodestroy, inline.}"""
    result = Cursor(_owner=src._owner, _p=src._p, _rem=src._rem)
    if not isNil(result._owner):
        result._owner._rc += 1
    return result

# ── Cursor primitives ────────────────────────────────────────────────────


with const:
    nifcoreChecks = defined("nifcoreChecks")
    ## Internal cursor invariants (`load`, `kind`) are checked only when this is
    ## explicitly requested, NOT under plain `-d:release`.
    ##
    ## `load` is the single most executed routine in the whole toolchain — every
    ## `kind`, `tokenWidth`, `combinedPayload` and literal decode bottoms out in
    ## it. Its two-condition assert was more than the check: it made `load`'s NIFC
    ## body 131 tokens, over the inliner's 100-token bound, so `load` AND its
    ## callers stayed real calls — 28 instructions for `kind`, whose body is two.
    ## The invariant it guards (a cursor is non-nil and has tokens left) is an
    ## internal one: a violation is a nifcore bug, and every walk re-establishes it
    ## structurally. Build with `-d:nifcoreChecks` to get it back.


def load(c: Cursor) -> NifToken:
    """{.inline.}"""
    if comptime(nifcoreChecks):
        assert not isNil(c._p) and c._rem > 0
    return c._p.contents


@template
def _peekAhead(c: Cursor, offset: nint) -> NifToken:
    return cast[ptr[NifToken]](cast[uintp](c._p) +
                               uint(offset) * uint(sizeof(NifToken))).contents


@template
def _advanceBy(c: mut @ Cursor, n: nint):
    # Capture `n` once — callers pass `tokenWidth(c)`, which reads c.p, and
    # re-evaluating after we move c.p would read the wrong token.
    with let:
        advance = n
    c._p = cast[ptr[NifToken]](cast[uintp](c._p) +
                               uint(advance) * uint(sizeof(NifToken)))
    if c._rem > 0:
        c._rem = c._rem - advance if c._rem >= advance else 0


def cursorIsNil(c: Cursor) -> bool:
    """{.inline.}"""
    return isNil(c._p)


@dispatch
def kind(c: Cursor) -> NifKind:
    """{.inline.}"""
    ## Effective kind of the value at the cursor. Always one load + one
    ## mask — the cursor lands on the kinded token; any `ExtendedSuffix`
    ## sits *after* it and is only consulted when extended bits are needed.
    return kind(load(c))


def tokenWidth(c: Cursor) -> nint:
    """{.alwaysInline.}"""
    ## Tokens occupied by the head of the current value — the kinded
    ## token plus any consecutive `ExtendedSuffix` tokens chained behind
    ## it. NOT including a TagLit's body.
    ##
    ## Chains are unbounded in principle; in practice the writers in
    ## nifcore emit at most 2 suffixes (enough to cover int64/float64 /
    ## 47-bit jumps / 55-bit pool ids). The hot path — no suffix at all
    ## — is one peek + one branch.
    ##
    ## Written as NESTED `if`s ending in `break`s rather than a `while` over a
    ## conjunction, and deliberately WITHOUT a `noinline` slow-path helper.
    ##
    ## Do NOT give this one the hot/cold treatment `combinedPayload` gets, even
    ## though the two look alike. Measured on nifbench: splitting `combinedPayload`
    ## is −0.68 % instructions, splitting THIS is **+6.5 M (a loss)**, and doing
    ## both is only −0.46 % — the loss here eats a third of the win there. The hot
    ## path returns a *constant*, so the call it saves is already the cheapest kind
    ## while the wrapper still costs a branch at all 10 M call sites. Reasons:
    ##  * a conjunction whose second operand contains a call cannot be handed to
    ##    the backend as branches, so it materialises a bool in an if/else
    ##    diamond — 9 x86 instructions and ~90 NIFC tokens for two compares;
    ##  * factoring the chain walk into a helper made this routine a NON-LEAF,
    ##    and arkham then homes its locals in callee-saved registers and pushes
    ##    them in the prologue on EVERY call, including the overwhelmingly common
    ##    no-suffix path. That cost more than the loop it removed (`parse` +8%).
    ##
    ## `{.alwaysInline.}` is load-bearing for the native backend. Hexer's
    ## inliner ignores `.inline` (it only auto-splices bodies ≤ 100 tokens, and
    ## this one is larger once `peekAhead` expands) while GCC `-O3` inlines the
    ## `static inline` C anyway. Without the force-splice, `skip`/`inc` call
    ## this and copy the 24-byte Cursor onto the stack for the by-value
    ## argument — the dominant arkham-vs-GCC gap on nifbench's walk/parse.
    ##
    ## Measured, not assumed: at 262 asm-NIF tokens this sits
    ## above `InlineTinyBound`, so the size heuristic never took it, and it is the
    ## one shape that pays — scalar in, scalar out, few live values, so the callee's
    ## push/pop and call/ret vanish and the caller adds no spill traffic. Measured
    ## on nimsem (128-invocation `check`, `-d:danger`): 55.320 G → 55.035 G Ir,
    ## **−0.51 %**, for +4 KB of image.
    ##
    ## The two neighbours that looked like the same shape on nifbench do NOT
    ## survive this measurement — do not annotate them: `inc` on top of this one is
    ## −0.36 % (i.e. it gives back a third of the win, while nifbench said it added
    ## to it), and `rawLineInfo` is **+0.22 %, a loss** — it returns an aggregate
    ## and holds ~20 live values, so the push/pop it removes comes straight back as
    ## frame traffic in every caller.
    result = 1
    if c._rem > 1:
        if kind(_peekAhead(c, 1)) >= NifKind.ExtendedSuffix:
            result = 2
            while c._rem > result:
                if kind(_peekAhead(c, result)) < NifKind.ExtendedSuffix:
                    break
                result += 1
    return result


def _combinedPayloadSlow(c: Cursor) -> uint64:
    """{.noinline.}"""
    ## The suffix chain walk — see `tokenWidthSlow` for why it is `.noinline`.
    result = uint64(uoperand(load(c)))
    with var:
        i = 1
    with var:
        shift = PayloadBits.copy()
    while True:
        result = result | (uint64(uoperand(_peekAhead(c, i))) << shift)
        i += 1
        shift += PayloadBits
        if shift >= u32(64):
            break
        if c._rem <= i:
            break
        if kind(_peekAhead(c, i)) != NifKind.ExtendedSuffix:
            break
    assert not (c._rem > i and kind(_peekAhead(c, i)) == NifKind.ExtendedSuffix), (
        "too many ExtendedSuffix tokens!")
    return result


def combinedPayload(c: Cursor) -> uint64:
    """{.alwaysInline.}"""
    ## Combine the kinded token's 28-bit payload with any chained
    ## ExtendedSuffix tokens. Each suffix supplies the next 28 high bits.
    ##
    ## HOT PATH INLINE, COLD PATH OUT OF LINE. 7.3 M calls per nifbench run at 29
    ## instructions each, for a common case that is one load and one branch — 12
    ## of those 29 were callee-saved pushes and pops for registers only the chain
    ## walk uses. `{.alwaysInline.}` because the wrapper is 269 NIFC tokens once
    ## hexer has flattened it, far past `InlineTinyBound`; `combinedPayloadSlow`
    ## is `{.noinline.}` because otherwise it gets spliced back in here and the
    ## wrapper stops being worth inlining. **Both pragmas are load-bearing.**
    ## nifbench −0.68 % instructions, self-hosted compiler unchanged.
    ##
    ## `tokenWidth` looks like the same shape but must NOT get the same treatment
    ## — see the measurement in its doc comment.
    if c._rem > 1 and kind(_peekAhead(c, 1)) == NifKind.ExtendedSuffix:
        result = _combinedPayloadSlow(c)
    else:
        result = uint64(uoperand(load(c)))
    return result

# String/sym layout (StrLit, Ident, Symbol, SymbolDef):
#   bit 0      mode (1 = inline-short, 0 = pool ref)
#   inline:
#     bits 1..2   length (0..3)
#     bits 3..10  char 0 (if length ≥ 1)
#     bits 11..18 char 1 (if length ≥ 2)
#     bits 19..26 char 2 (if length ≥ 3)
#     bit 27      unused
#   pool ref:
#     bits 1..27  pool id (27 bits, or up to 55 with one ExtendedSuffix)
#
# Writer rule: `s.len <= 3` always goes inline, longer goes pool. That
# preserves the same-string ⇒ same-payload invariant (no string is
# encodable both ways in the same tree), so a token-payload equality
# test remains a valid same-pool string-equality fast path.


with const:
    StrInlineFlag = u32(1)                 ## bit 0 = inline mode
    StrLengthShift = u32(1)
    StrLengthMask = u32(3)                 ## bits 1..2
    StrDataShift = u32(3)                  ## bits 3..26 hold up to 3 bytes
    StrInlineMaxLen = 3                    ## bytes that fit inline


def isInlineLit(c: Cursor) -> bool:
    """{.inline.}"""
    ## True if a StrLit/Ident/Symbol/SymbolDef stores its bytes inline.
    return (uoperand(load(c)) & StrInlineFlag) != u32(0)


def _inlineStrLen(payload: uint32) -> nint:
    """{.inline.}"""
    return nint((payload >> StrLengthShift) & StrLengthMask)


def _readInlineStr(payload: uint32) -> string:
    with let:
        length = _inlineStrLen(payload)
    result = newString(length)
    with let:
        chars = payload >> StrDataShift
    for i in range(0, length):
        result[i] = char((chars >> (uint32(i) * u32(8))) & u32(0xFF))
    return result


@dispatch
def strVal(c: Cursor, pool: Pool) -> string:
    ## Decode a StrLit/Ident at the cursor into a `string`. Handles the
    ## inline-short path (no pool touch) and the pool-ref path (with or
    ## without an ExtendedSuffix extending the pool id).
    _checkKind(kind(c) in Tset[NifKind](NifKind.StrLit, NifKind.Ident), string("strVal on "), kind(c))
    with let:
        payload = uoperand(load(c))
    if (payload & StrInlineFlag) != u32(0):
        return _readInlineStr(payload)
    else:
        return pool.strings[StrId(uint32(combinedPayload(c) >> 1))]

# The one-argument accessors below spell the pool lookup out rather than calling
# `pool(c)`. `pool` returns the pool BY VALUE, and a `ref` returned by value is an
# owned temporary — ARC pairs the call with an incRef and a decRef, and the decRef
# carries the `Pool`'s whole destructor (three `BiTable`s) behind it, for a pool
# that outlives the program. Passed as an ARGUMENT the same field is borrowed and
# costs nothing, so the branch is written here where the value is consumed
# immediately. Same reasoning as `escapeTagOf`; measured together on nifbench.


@dispatch
def strVal(c: Cursor) -> string:
    """{.inline.}"""
    if comptime(defined("nimonyPlugin")):
        if not isNil(c._owner) and c._owner._pool is not None:
            return strVal(c, c._owner._pool)
        else:
            return strVal(c, fallbackPool)
    else:
        assert not isNil(c._owner) and c._owner._pool is not None, (
            "strVal on a cursor with no literals pool")
        return strVal(c, c._owner._pool)


@dispatch
def strId(c: Cursor, pool: Pool) -> StrId:
    ## Stable pool id of the StrLit/Ident at `c` — the inverse of `strVal`.
    ## A pool-ref token already carries its id, so use it directly; only an inline
    ## short string (stored in the token itself) has to be interned. Mirrors
    ## `symId` and avoids the decode-then-reintern round trip of `strings[strVal]`.
    _checkKind(kind(c) in Tset[NifKind](NifKind.StrLit, NifKind.Ident), string("strId on "), kind(c))
    with let:
        payload = uoperand(load(c))
    if (payload & StrInlineFlag) != u32(0):
        return pool.strings.getOrIncl(_readInlineStr(payload))
    else:
        return StrId(uint32(combinedPayload(c) >> 1))


@dispatch
def strId(c: Cursor) -> StrId:
    """{.inline.}"""
    if comptime(defined("nimonyPlugin")):
        if not isNil(c._owner) and c._owner._pool is not None:
            return strId(c, c._owner._pool)
        else:
            return strId(c, fallbackPool)
    else:
        assert not isNil(c._owner) and c._owner._pool is not None, (
            "strId on a cursor with no literals pool")
        return strId(c, c._owner._pool)


@dispatch
def symName(c: Cursor, pool: Pool) -> string:
    _checkKind(kind(c) in Tset[NifKind](NifKind.Symbol, NifKind.SymbolDef), string("symName on "), kind(c))
    with let:
        payload = uoperand(load(c))
    if (payload & StrInlineFlag) != u32(0):
        return _readInlineStr(payload)
    else:
        return symString(pool, SymId(uint32(combinedPayload(c) >> 1)))


@dispatch
def symName(c: Cursor) -> string:
    """{.inline.}"""
    if comptime(defined("nimonyPlugin")):
        if not isNil(c._owner) and c._owner._pool is not None:
            return symName(c, c._owner._pool)
        else:
            return symName(c, fallbackPool)
    else:
        assert not isNil(c._owner) and c._owner._pool is not None, (
            "symName on a cursor with no literals pool")
        return symName(c, c._owner._pool)


@dispatch
def symId(c: Cursor, pool: Pool) -> SymId:
    ## Stable pool id of the Symbol/SymbolDef at `c` — the inverse of `symName`.
    ## A pool-ref token already carries its id, so use it directly; only an inline
    ## short name (stored in the token itself) has to be interned.
    _checkKind(kind(c) in Tset[NifKind](NifKind.Symbol, NifKind.SymbolDef), string("symId on "), kind(c))
    with let:
        payload = uoperand(load(c))
    if (payload & StrInlineFlag) != u32(0):
        return symId(pool, _readInlineStr(payload))
    else:
        return SymId(uint32(combinedPayload(c) >> 1))


@dispatch
def symId(c: Cursor) -> SymId:
    """{.inline.}"""
    if comptime(defined("nimonyPlugin")):
        if not isNil(c._owner) and c._owner._pool is not None:
            return symId(c, c._owner._pool)
        else:
            return symId(c, fallbackPool)
    else:
        assert not isNil(c._owner) and c._owner._pool is not None, (
            "symId on a cursor with no literals pool")
        return symId(c, c._owner._pool)

# Int/UInt/Float: pure-inline via chainable ExtendedSuffix.
#
#   IntLit  payload: 28-bit signed (one token); 56-bit signed with one
#                    suffix; 84-bit (covers int64) with two suffixes.
#   UIntLit payload: 28-bit unsigned; widens the same way.
#   FloatLit payload: cast[uint64](float64); 0 / 1 / 2 suffixes depending
#                     on which 28-bit chunk is the highest set bit.
#
# No flag bit, no pool — Pool.integers / Pool.uintegers / Pool.floats
# are gone. The reader's per-call cost is the same as before in the
# common case (no suffix → one peek + one branch).


def valueWidth(c: Cursor) -> nint:
    """{.inline.}"""
    ## Tokens carrying value bits — the kinded token plus consecutive
    ## `ExtendedSuffix` tokens. Excludes trailing LineInfoLit (which
    ## `tokenWidth` does include for advance-past purposes). This is the
    ## width sign-extension wants for IntLit; it lines up exactly with
    ## what `combinedPayload` chooses to OR together.
    result = 1
    while c._rem > result and kind(_peekAhead(c, result)) == NifKind.ExtendedSuffix:
        result += 1
    return result


def intVal(c: Cursor) -> int64:
    """{.inline.}"""
    assert kind(c) == NifKind.IntLit
    with let:
        width = uint32(valueWidth(c)) * PayloadBits      # 28, 56, or 84
    with let:
        combined = combinedPayload(c)
    if width >= u32(64):
        return cast[int64](combined)                              # int64 fully used
    else:
        with let:
            shift = uint64(u32(64) - width)
        return cast[int64](combined << shift) >> shift          # sign-extend


def uintVal(c: Cursor) -> uint64:
    """{.inline.}"""
    assert kind(c) == NifKind.UIntLit
    return combinedPayload(c)                                   # no sign extension


def floatVal(c: Cursor) -> float64:
    """{.inline.}"""
    assert kind(c) == NifKind.FloatLit
    return cast[float64](combinedPayload(c))


def charLit(c: Cursor) -> char:
    """{.inline.}"""
    ## Returns the character stored in the `CharLit` at `c`.
    assert kind(c) == NifKind.CharLit
    return char(uoperand(load(c)))

# TagLit accessors — the tag is always in the kinded token; the jump
# extends via the suffix when present.


def cursorTagId(c: Cursor) -> TagId:
    """{.inline.}"""
    assert kind(c) == NifKind.TagLit
    return _rawTag(load(c))


def cursorJump(c: Cursor) -> uint64:
    """{.alwaysInline.}"""
    ## Body tokens following this TagLit. 19 bits if unsuffixed; with one
    ## ExtendedSuffix the field widens to 47 bits (further chaining would
    ## extend it further, but no plausible jump needs that). The unified
    ## `combinedPayload` handles the suffix walk for us; we just discard
    ## the low 9 tag bits to expose the jump.
    assert kind(c) == NifKind.TagLit
    return combinedPayload(c) >> TagBits

# ── Line info reader ─────────────────────────────────────────────────────


def rawLineInfo(c: Cursor) -> NifLineInfo:
    ## Decode the `LineInfoLit` trailing the value at `c`, if present, returning
    ## a `FileId` (resolve against `pool.filenames`) plus line/col, and an
    ## optional `comment` `StrId` (a NIF `#…#` decoration; `StrId(0)` = none).
    ## Returns `NoNifLineInfo` when the head carries no line info. The
    ## `LineInfoLit` sits after the value's `ExtendedSuffix` chain (`valueWidth`);
    ## file and comment are interned, so cross-pool readers must map them via the
    ## right pool. Layout is selected structurally by the count `k` of
    ## `ExtendedSuffix` words trailing the `LineInfoLit` (see the section header):
    ## `k==0` common/no-comment, `k==1` wide/no-comment, `k>=2` wide + comment.
    # Walk past the value carrier's own ExtendedSuffix chain.
    with var:
        off = 1
    while c._rem > off and kind(_peekAhead(c, off)) == NifKind.ExtendedSuffix:
        off += 1
    if c._rem <= off or kind(_peekAhead(c, off)) != NifKind.LineInfoLit:
        return NoNifLineInfo
    with let:
        lit = _peekAhead(c, off)
    # Count the ExtendedSuffix words trailing the LineInfoLit (position + comment).
    with var:
        ext = off + 1
    while c._rem > ext and kind(_peekAhead(c, ext)) == NifKind.ExtendedSuffix:
        ext += 1
    with let:
        extCount = ext - (off + 1)
    if extCount == 0:
        # common layout: col 7 | file 7 | line 14 in 28 bits
        with let:
            p = uoperand(lit)
        result = NifLineInfo(
            col=int32(p & LiColMaxC),
            file=FileId((p >> LiColBitsC) & LiFileMaxC),
            line=int32((p >> (LiColBitsC + LiFileBitsC)) & LiLineMaxC))
    else:
        # overflow layout: col 10 | file 14 | line 32 across 56 bits (lit + word 0)
        with let:
            combined = (uint64(uoperand(lit)) |
                        (uint64(uoperand(_peekAhead(c, off + 1))) << PayloadBits))
        result = NifLineInfo(
            col=int32(combined & _LiColMaskX),
            file=FileId((combined >> _LiColBitsX) & _LiFileMaskX),
            line=int32((combined >> (_LiColBitsX + _LiFileBitsX)) & _LiLineMaskX))
        # Words 1.. hold the comment StrId as 28-bit chunks, low first.
        if extCount >= 2:
            with var:
                cid = u64(0)
            with var:
                shift = u64(0)
            for i in range(1, extCount):
                cid = cid | (uint64(uoperand(_peekAhead(c, off + 1 + i))) << shift)
                shift += uint64(PayloadBits)
            result.comment = StrId(cid)
    return result


def lineInfoFile(c: Cursor) -> string:
    ## The filename for the value's line info, resolved against `c.pool.filenames`.
    ## Empty string when there is no line info.
    with let:
        li = rawLineInfo(c)
    return pool(c).filenames[li.file] if isValid(li.file) and pool(c) is not None else string("")

# ── inc / skip / into ────────────────────────────────────────────────────


def inc(c: mut @ Cursor):
    """{.inline, nifAdvance.}"""
    ## Advance past the *head* of the current value (kinded token plus its
    ## suffix, if any). For a TagLit this lands at the first body token;
    ## use `skip` to jump past the whole subtree.
    assert c._rem != 0, "advancing past end of scope"
    _advanceBy(c, tokenWidth(c))


def skip(c: mut @ Cursor):
    """{.nifAdvance.}"""
    ## Advance past the current value, including all descendants of a TagLit.
    if kind(c) == NifKind.TagLit:
        with let:
            span = nint(uint64(tokenWidth(c)) + cursorJump(c))
        _advanceBy(c, span)
    else:
        _advanceBy(c, tokenWidth(c))


@template
def hasMore(c: Cursor) -> bool:
    ## True while there are more tokens in the current bounded scope. No
    ## sentinel: `rem` does all the work.
    return c._rem > 0


def enterScope(c: mut @ Cursor) -> CursorScope:
    ## Enters the current `TagLit` body and returns its saved outer bounds.
    ## Pair with `leaveScope` after consuming every child.
    assert kind(load(c)) == NifKind.TagLit, "into requires cursor at TagLit"
    result = CursorScope(_savedP=c._p, _savedRem=c._rem,
                         _bodyLen=nint(cursorJump(c)))
    with let:
        headWidth = tokenWidth(c)
    c._p = cast[ptr[NifToken]](cast[uintp](c._p) +
                               uint(headWidth) * uint(sizeof(NifToken)))
    c._rem = result._bodyLen
    return result


def leaveScope(c: mut @ Cursor, scope: CursorScope):
    ## Leaves a scope opened by `enterScope`.
    ## The cursor must have consumed the complete bounded body.
    assert c._rem == 0, (string("into: body did not consume all ") + str(scope._bodyLen) +
                         string(" children (left ") + str(c._rem) + string(")"))
    with let:
        consumed = nint((cast[uintp](c._p) - cast[uintp](scope._savedP)) //
                        uint(sizeof(NifToken)))
    c._rem = (scope._savedRem - consumed if scope._savedRem >= consumed else
              0)


def sub(c: Cursor) -> Cursor:
    ## Read-only descent: returns a bounded cursor over the children of the
    ## `TagLit` at `c`, leaving `c` itself untouched. Use it for a throwaway
    ## walk of a node's body (`while result.hasMore: …`) where there is no dest
    ## to preserve into and hence no scope to `leaveScope`. Replaces the old
    ## `var t = c; discard enterScope(t)` idiom.
    assert kind(load(c)) == NifKind.TagLit, "sub requires cursor at TagLit"
    result = c.copy()
    _ = enterScope(result)
    return result


def _isEscapedBody(c: Cursor) -> bool:
    """{.noinline.}"""
    ## The last conjunct of `isEscapedTag`, out of line. Reached only once the tag
    ## at `c` IS the adapter's escape tag, which on nifbench is never: an adapter
    ## that declares no escape space answers `TagId(0)` and the first conjunct is
    ## already false. Keeping the `sub` here is what lets the caller be spliced —
    ## `sub` enters a scope, so inlining this half would drag `enterScope` (and the
    ## temp cursor's destructor) into every site, and on AArch64 the call alone
    ## forces a frame: `bl` delivers the return address in x30, so a proc holding
    ## one anywhere must spill lr on every entry to reach a branch not taken.
    ##
    ## `c.load.kind == TagLit` is the caller's second conjunct and therefore a
    ## precondition here — it is what `sub`'s own assert wants.
    with let:
        body = sub(c)
    result = hasMore(body) and kind(load(body)) == NifKind.IntLit
    return result


def isEscapedTag(c: Cursor) -> bool:
    """{.alwaysInline.}"""
    ## Is the node at `c` spelled through its adapter's escape tag — i.e. does its
    ## real id sit in a leading `IntLit` child, one token in front of the operands?
    ##
    ## `{.alwaysInline.}` rather than `{.inline.}`, which `computeInlineInfo` does
    ## not consult: what is left here is `escapeTagOf` plus two comparisons, and it
    ## has five call sites. See `isEscapedBody` for what was taken out to make that
    ## true.
    with let:
        esc = escapeTagOf(c)
    result = (esc != TagId(u32(0)) and kind(load(c)) == NifKind.TagLit and
              cursorTagId(c) == esc and _isEscapedBody(c))
    return result


def resolvedTagId(c: Cursor) -> TagId:
    ## The tag id of the node at `c`, undoing the escape. Equal to `cursorTagId`
    ## for everything that fits the 9-bit field, which is every tag of an adapter
    ## that declares no escape space — so this is the accessor to reach for, and
    ## `cursorTagId` the one for when you truly mean the token.
    if isEscapedTag(c):
        with let:
            body = sub(c)
        result = TagId(uint32(intVal(body)))
    else:
        result = cursorTagId(c)
    return result


@template
def into(c: mut @ Cursor, body: untyped):
    pragma("nifWrap")
    ## Enters the current `TagLit`, runs `body`, then restores the outer bounds.
    ## `body` must consume every child.
    with let:
        cursorScope = enterScope(c)
    body
    leaveScope(c, cursorScope)


@template
def loopInto(c: mut @ Cursor, body: untyped):
    pragma("nifWrap")
    with into(c):
        while hasMore(c):
            body


def leaveScopePartial(c: mut @ Cursor, scope: CursorScope):
    ## Leaves a scope opened by `enterScope` **without** requiring the body to
    ## have been fully consumed: rewinds to the scope head and skips the whole
    ## subtree. The early-out counterpart to `leaveScope`.
    c._p = scope._savedP
    c._rem = scope._savedRem
    skip(c)


@template
def peekInto(c: mut @ Cursor, body: untyped):
    pragma("nifWrap")
    ## Like `into`, but `body` need not consume every child — any unconsumed
    ## remainder is skipped. Use for early-out searches over a node's children
    ## (e.g. `break` out on the first match). The finish is a single `skip`
    ## from the rewound scope head, so it does not depend on where `body`
    ## stopped; `body` still sees a bounded scope so `hasMore` terminates.
    with let:
        cursorScope = enterScope(c)
    body
    leaveScopePartial(c, cursorScope)


def rootOf(c: Cursor) -> SymId:
    ## The access root of an lvalue: the first `Symbol` in the subtree at `c`
    ## — `x` in `x.f[i]` — or `SymId(0)` if there is none.
    if not hasMore(c):
        return SymId(u32(0))
    match kind(c):
        case NifKind.Symbol:
            result = symId(c)
        case NifKind.TagLit:
            result = SymId(u32(0))
            with var:
                n = c.copy()
            for _ in n.loopInto():
                if result == SymId(u32(0)):
                    with let:
                        inner = rootOf(n)
                    if inner != SymId(u32(0)):
                        result = inner
                skip(n)
        case _:
            result = SymId(u32(0))
    return result

# ── TokenBuf ─────────────────────────────────────────────────────────────


class TokenBuf(Object):
    _data: _Storage
    _len: nint
    _cap: nint
    _owner: _CursorOwner
    _openTags: seq[nint]            # build-time stack of unsealed TagLit positions
    pool: Pool                     # literals (typically shared by an app)
    tags: TagPool                  # tags (typically per-adapter)


@hook("copy")
def _copyTokenBuf(dest: mut @ TokenBuf, src: TokenBuf):
    """{.error.}"""
    pass


@hook("wasMoved")
def _wasMovedTokenBuf(dest: mut @ TokenBuf):
    """{.nodestroy, inline.}"""
    # `nodestroy`: this hook establishes the moved-from state and may run on
    # uninitialized storage (Nimony does not zero-init `result`), so the field
    # writes below must be raw stores — never destroy the prior (garbage) value.
    dest._data = None
    dest._len = 0
    dest._cap = 0
    dest._owner = None
    dest.pool = None
    dest.tags = None
    dest._openTags = seq[nint]([])


if comptime(defined("nimAllowNonVarDestructor") and defined("gcDestructors")):
    @hook("destroy")
    def _destroyTokenBuf(dest: TokenBuf):
        """{.inline.}"""
        if not isNil(dest._owner):
            _decRcAndFree(dest._owner)
        elif not isNil(dest._data):
            dealloc(dest._data)
else:
    @hook("destroy")
    def _destroyTokenBuf(dest: mut @ TokenBuf):
        """{.inline.}"""
        if not isNil(dest._owner):
            _decRcAndFree(dest._owner)
        elif not isNil(dest._data):
            dealloc(dest._data)


@template
def requirePools(b: mut @ TokenBuf):
    ## A buffer the interning builders and the cross-pool copy are about to write
    ## through must carry both of its pools. They are THREADED in at construction
    ## (`createTokenBuf` / `initTokenBuf`) and never invented here: a literals
    ## pool decides what a token's payload id means and a tag pool is the
    ## buffer's whole kind space, so substituting a fresh one for either silently
    ## reinterprets everything already in the buffer. `default(TokenBuf)` is not
    ## a usable buffer; `initTokenBuf` is the zero-allocation way to spell one.
    ##
    ## The plugin build is the exception, and only there: it binds its
    ## process-wide pools rather than reject the buffer, because
    ## `plugins.NifBuilder` is a public alias whose `default` shape must keep
    ## working. See the `nimonyPlugin` block above.
    if comptime(defined("nimonyPlugin")):
        if b.pool is None:
            b.pool = fallbackPool
        if b.tags is None:
            b.tags = fallbackTags
    assert b.pool is not None, "TokenBuf has no literals pool"
    assert b.tags is not None, "TokenBuf has no tag pool"


def createTokenBuf(cap: nint = 16, sharedPool: Pool = None,
                   sharedTags: TagPool = None) -> TokenBuf:
    ## Mint a new buffer. Pass `sharedPool` to thread a single literals
    ## pool through multiple buffers (cross-format dedup). Pass
    ## `sharedTags` only if you want multiple buffers to use the same
    ## tag namespace — adapters typically create their own fresh
    ## `TagPool` per buffer so `cast[Enum](c.cursorTagId.uint32)` lines
    ## up with the adapter's enum ordinals.
    # `cap == 0` must NOT reach `alloc(0)`: Nim's allocator maps a zero-sized
    # request to size class 0, which hands the SAME address to every caller and
    # (on Nim <= 2.2.x) releases the whole page on the first `dealloc` — every
    # other live zero-cap buffer is then a dangling pointer into a recycled page.
    with let:
        cap = max(cap, 1)
    result = TokenBuf(
        _data=cast[_Storage](alloc(sizeof(NifToken) * cap)),
        _len=0, _cap=cap,
        pool=(sharedPool if sharedPool is not None else newPool()),
        tags=(sharedTags if sharedTags is not None else newTagPool())
    )
    return result


def initTokenBuf(sharedPool: Pool, sharedTags: TagPool) -> TokenBuf:
    """{.inline.}"""
    ## A buffer bound to `sharedPool`/`sharedTags` that owns NO storage yet — the
    ## first `add` allocates it. This is what an object field, a `seq` slot or any
    ## other buffer that used to be spelled `default(TokenBuf)` must be
    ## initialized with: the tag pool is a buffer's whole kind space, so it is
    ## THREADED in at construction and never fallen back to.
    return TokenBuf(_data=None, _len=0, _cap=0, pool=sharedPool, tags=sharedTags)


def adoptForeignTokens(data: pointer, count: nint,
                       sharedPool: Pool = None, sharedTags: TagPool = None) -> TokenBuf:
    ## Build a buffer whose `count` tokens are BORROWED from `data` (e.g. an mmap'd
    ## `.bif` region) rather than copied into a heap allocation — a zero-copy load.
    ## The buffer reads like any other. It NEVER frees `data`: the block is handed to
    ## an eagerly-created cursor owner seeded with an EXTRA, permanent reference
    ## (`rc = 2` = the buffer's own ref plus one keep-alive), so `decRcAndFree` never
    ## reaches 0 and never `dealloc`s the borrowed storage. A *mutation* still works
    ## unchanged: because the owner is shared (`rc > 1`), `prepareMutation` forks a
    ## private heap copy and abandons the borrowed block — no special-casing anywhere
    ## else. The buffer does NOT own the mapping's lifetime: `data` must stay valid
    ## (and aligned for `NifToken`, 4 bytes) for as long as the buffer or any cursor
    ## over it lives. The caller keeps the backing store resident — typically for the
    ## whole process; an mmap left mapped costs only address space, reclaimed at exit.
    assert (cast[uintp](data) & (uint(sizeof(NifToken)) - uint(1))) == 0, (
        "adoptForeignTokens: misaligned token block")
    result = TokenBuf(
        _data=cast[_Storage](data),
        _len=count, _cap=count,
        pool=(sharedPool if sharedPool is not None else newPool()),
        tags=(sharedTags if sharedTags is not None else newTagPool())
    )
    # Pin the borrowed block for the buffer's whole life via an owner seeded with a
    # permanent extra ref — same shape `ensureOwner` builds, but `rc = 2` so it is
    # never collected. (Mirrors `ensureOwner`, inlined because that proc is declared
    # further down and this one needs the non-default seed.)
    result._owner = cast[_CursorOwner](alloc0(sizeof(_CursorOwnerObj)))
    result._owner._data = cast[_Storage](data)
    result._owner._pool = result.pool
    result._owner._tags = result.tags
    GC_ref(result._owner._pool)
    GC_ref(result._owner._tags)
    result._owner._rc = 2
    return result


@dispatch
def len(b: TokenBuf) -> nint:
    """{.inline.}"""
    return b._len


@ufcs(TokenBuf)
@dispatch
def __getitem__(b: TokenBuf, i: nint) -> NifToken:
    """{.inline.}"""
    assert i >= 0 and i < b._len
    return b._data[i]


@ufcs(TokenBuf)
@dispatch
def __setitem__(b: mut @ TokenBuf, i: nint, v: NifToken):
    """{.inline.}"""
    assert i >= 0 and i < b._len
    b._data[i] = v


def prepareMutation(b: mut @ TokenBuf):
    """{.inline.}"""
    if not isNil(b._owner):
        if b._owner._rc == 1:
            # Reclaim the owner header; b.data keeps its allocation. Detach
            # data first so decRcAndFree's data-dealloc path doesn't free
            # what the TokenBuf is about to keep using.
            b._owner._data = None
            _decRcAndFree(b._owner)
            b._owner = None
        else:
            # `max(.., 1)`: never `alloc(0)` — see `createTokenBuf`. A borrowed
            # zero-token block (`adoptForeignTokens(_, 0)`) reaches this with cap 0.
            with let:
                newData = cast[_Storage](alloc(sizeof(NifToken) * max(b._cap, 1)))
            copyMem(newData, b._data, sizeof(NifToken) * b._len)
            _decRcAndFree(b._owner)
            b._owner = None
            b._data = newData


def expectUnique(b: mut @ TokenBuf):
    """{.inline.}"""
    if comptime(defined("debug")):
        assert isNil(b._owner) or b._owner._rc == 1, (
            "TokenBuf has live cursors; missing endRead before mutation")


@template
def _ensureCap(b: mut @ TokenBuf):
    if b._len >= b._cap:
        b._cap = max(b._cap // 2 + b._cap, 8)
        b._data = cast[_Storage](realloc(b._data, sizeof(NifToken) * b._cap))


@dispatch
def add(b: mut @ TokenBuf, t: NifToken):
    """{.inline.}"""
    ## Plain append. Use `openTag` / `closeTag` for nested TagLits.
    if not isNil(b._owner):
        prepareMutation(b)
    _ensureCap(b)
    b._data[b._len] = t
    b._len += 1

# ── Raw bulk token access (for binary serialization, see bif.nim) ────────
# These expose the contiguous token storage for direct block I/O. They bypass
# all structural bookkeeping (jumps, openTags, suffix chains) — the caller must
# hand over / consume a stream that is already well-formed. The pools are
# serialized separately; because token payloads only reference *pool ids*
# (assigned 1,2,… in intern order), a loader that re-interns the pool values in
# the same order reproduces identical ids, so the raw token words stay valid.


def shrink(b: mut @ TokenBuf, newLen: nint):
    ## Truncate to `newLen` tokens. Any still-open tags at or past the cut are
    ## discarded from the build-time stack so later `closeTag` calls keep
    ## sealing the right opens (rollback-past-an-open-tag pattern).
    assert newLen >= 0 and newLen <= b._len
    if not isNil(b._owner):
        prepareMutation(b)
    while b._openTags.len > 0 and b._openTags[back(1)] >= newLen:
        b._openTags.setLen(b._openTags.len - 1)
    b._len = newLen


def rawTokenPtr(b: TokenBuf) -> pointer:
    """{.inline.}"""
    ## Pointer to the first token word; `len(b) * sizeof(NifToken)` bytes follow.
    return b._data


def growRawUninit(b: mut @ TokenBuf, count: nint) -> pointer:
    ## Grow storage to hold exactly `count` tokens, set `len = count`, and return
    ## the storage pointer so the caller can fill it directly (e.g. `readBuffer`).
    ## The contents are left uninitialized. Binary loaders only.
    if not isNil(b._owner):
        prepareMutation(b)
    if count > b._cap:
        b._cap = count
        b._data = cast[_Storage](realloc(b._data, sizeof(NifToken) * b._cap))
    b._len = count
    return b._data


def subtreeWidth(c: Cursor) -> nint:
    ## Total tokens occupied by the value at `c` (head + body).
    if kind(c) == NifKind.TagLit:
        return nint(uint64(tokenWidth(c)) + cursorJump(c))
    else:
        return tokenWidth(c)


def replace(dest: mut @ TokenBuf, by: Cursor, pos: nint):
    ## Replace the sealed subtree at `pos` with the sealed subtree `by`.
    if not isNil(dest._owner):
        prepareMutation(dest)
    with var:
        at = Cursor(_p=cast[ptr[NifToken]](cast[uintp](dest._data) +
                       uint(pos) * uint(sizeof(NifToken))), _rem=dest._len - pos)
    with let:
        actualLen = min(subtreeWidth(at), dest._len - pos)
    with let:
        byLen = subtreeWidth(by)
    with let:
        oldLen = dest._len.copy()
    with let:
        delta = byLen - actualLen
    if delta != 0:
        for k in range(0, dest._openTags.len):
            if dest._openTags[k] >= pos + actualLen:
                dest._openTags[k] += delta
    if delta > 0:
        _ = growRawUninit(dest, oldLen + delta)
        for i in countdown(oldLen - 1, pos + actualLen):
            dest._data[i + delta] = dest._data[i]
    elif delta < 0:
        for i in range(pos + actualLen, oldLen):
            dest._data[i + delta] = dest._data[i]
        dest._len = oldLen + delta
    for i in range(0, byLen):
        dest._data[pos + i] = cast[ptr[NifToken]](cast[uintp](by._p) +
                                uint(i) * uint(sizeof(NifToken))).contents


def insert(dest: mut @ TokenBuf, src: TokenBuf, pos: nint):
    ## Splice `src`'s tokens into `dest` at index `pos` (raw). Enclosing sealed
    ## scopes' jumps are NOT adjusted — the caller must `widenSealed` them.
    assert pos >= 0 and pos <= dest._len
    with let:
        n = src._len
    if n == 0:
        return
    with let:
        oldLen = dest._len.copy()
    if not isNil(dest._owner):
        prepareMutation(dest)
    _ = growRawUninit(dest, oldLen + n)
    for i in countdown(oldLen - 1, pos):
        dest._data[i + n] = dest._data[i]
    for i in range(0, n):
        dest._data[pos + i] = src._data[i]

# ── Builder API (interns, emits suffix on overflow) ──────────────────────


@dispatch
def appendLineInfo(b: mut @ TokenBuf, file: FileId, line: int32, col: int32,
                   comment: StrId = StrId(u32(0))):
    ## Append a `LineInfoLit` suffix (plus one `ExtendedSuffix` on overflow) to
    ## the head token / `openTag` just emitted — call it *immediately* after, so
    ## it lands as that head's trailing suffix. Implements no policy: the caller
    ## decides when the position actually changed (emit-on-change). No-op when
    ## `file` is invalid. The filename must already be interned in `b.pool.filenames`.
    ## Optionally attach `comment` (a `StrId` into `b.pool.strings`, `StrId(0)` =
    ## none) — a NIF `#…#` decoration on this head. A non-zero comment forces the
    ## overflow position layout and rides as one further `ExtendedSuffix` (a second
    ## only for ids past 2^28), so `rawLineInfo` recovers it unambiguously.
    requirePools(b)
    if not isValid(file):
        return
    with var:
        line = line
    with var:
        col = col
    if line < i32(0):
        line = i32(0)
    if col < i32(0):
        col = i32(0)
    with let:
        cid = uint32(comment)
    if cid == u32(0) and _fitsCommonLineInfo(file, line, col):
        b.add(NifToken(_toX(NifKind.LineInfoLit, _encodeLineInfoCommon(file, line, col))))
    else:
        assert uint64(uint32(file)) <= _LiFileMaskX, "too many files for LineInfoLit"
        with let:
            combined = _encodeLineInfoWide(file, line, col)
        b.add(NifToken(_toX(NifKind.LineInfoLit, uint32(combined & uint64(PayloadMask)))))
        b.add(extendedSuffixToken(uint32((combined >> PayloadBits) & uint64(PayloadMask))))
        if cid != u32(0):
            b.add(extendedSuffixToken(cid & PayloadMask))
            if uint64(cid) > uint64(PayloadMask):
                b.add(extendedSuffixToken(cid >> PayloadBits))


@dispatch
def appendLineInfo(b: mut @ TokenBuf, info: NifLineInfo):
    """{.inline.}"""
    appendLineInfo(b, info.file, info.line, info.col, info.comment)


@template
def _addSuffixIfNeeded(b: mut @ TokenBuf, payload: uint64):
    ## Emit an ExtendedSuffix token carrying `payload`'s high 28 bits if
    ## the value doesn't fit in 28 bits. `payload` is uint64 because the
    ## shifted-by-1 pool ids used by IntLit/UIntLit can overflow uint32.
    if payload > uint64(PayloadMask):
        b.add(extendedSuffixToken(uint32(payload >> PayloadBits)))


@template
def _lowBits(x: uint32) -> uint32:
    return x & PayloadMask


@template
def _lowBits(x: uint64) -> uint32:
    return uint32(x & uint64(PayloadMask))


def addDotToken(b: mut @ TokenBuf):
    """{.inline, nifEmits: "Dot".}"""
    ## Appends an empty dot placeholder.
    b.add(dotToken())


def addCharLit(b: mut @ TokenBuf, c: char):
    """{.inline, nifEmits: "LIT".}"""
    ## Appends a character literal.
    b.add(charToken(c))


def _encodeInlineStr(s: string) -> uint32:
    """{.inline.}"""
    ## Pack up to 3 bytes of `s` into the inline-string layout.
    result = StrInlineFlag | (uint32(s.len) << StrLengthShift)
    for i in range(0, s.len):
        result = result | (uint32(byte(s[i])) << (StrDataShift + uint32(i) * u32(8)))
    return result


@template
def _addStringLike(b: mut @ TokenBuf, kind: NifKind, s: string, pool: untyped):
    ## Shared body for StrLit/Ident/Symbol/SymbolDef. Inlines bytes for
    ## `s.len <= 3`; otherwise interns in the given `pool` BiTable.
    requirePools(b)
    if s.len <= StrInlineMaxLen:
        b.add(NifToken(_toX(kind, _encodeInlineStr(s))))
    else:
        with let:
            id = uint32(pool.getOrIncl(s))
        with let:
            payload = uint64(id) << u64(1)               # bit 0 = 0 ⇒ pool ref
        b.add(NifToken(_toX(kind, _lowBits(payload))))
        _addSuffixIfNeeded(b, payload)


@dispatch
def addStrLit(b: mut @ TokenBuf, s: string):
    """{.nifEmits: "LIT".}"""
    ## Appends a string literal, using inline storage when possible.
    _addStringLike(b, NifKind.StrLit, s, b.pool.strings)


def _encodeInlineStrView(s: openArray[char]) -> uint32:
    """{.inline.}"""
    result = StrInlineFlag | (uint32(s.len) << StrLengthShift)
    for i in range(0, s.len):
        result = result | (uint32(byte(s[i])) << (StrDataShift + uint32(i) * u32(8)))
    return result


@dispatch
def addStrLit(b: mut @ TokenBuf, s: openArray[char]):
    """{.nifEmits: "LIT".}"""
    ## Appends a string literal taken straight from a byte view. For a parser
    ## reading someone else's buffer this saves cutting a slice out of it first:
    ## a short value costs nothing at all, and a long one costs the single copy
    ## the pool was going to make anyway.
    requirePools(b)
    if s.len <= StrInlineMaxLen:
        b.add(NifToken(_toX(NifKind.StrLit, _encodeInlineStrView(s))))
    else:
        with var:
            tmp = newString(s.len)
        for i in range(0, s.len):
            tmp[i] = s[i]
        with let:
            id = uint32(b.pool.strings.getOrIncl(tmp))
        with let:
            payload = uint64(id) << u64(1)               # bit 0 = 0 => pool ref
        b.add(NifToken(_toX(NifKind.StrLit, _lowBits(payload))))
        _addSuffixIfNeeded(b, payload)


def addIdent(b: mut @ TokenBuf, s: string):
    """{.nifEmits: "Y".}"""
    ## Appends an identifier, using inline storage when possible.
    _addStringLike(b, NifKind.Ident, s, b.pool.strings)


@template
def _addSymLike(b: mut @ TokenBuf, kind: NifKind, s: string):
    ## `addStringLike` for the SYMBOL pool, which does not take a spelling: the
    ## pool stores the taken-apart form, so interning goes through `symId`.
    requirePools(b)
    if s.len <= StrInlineMaxLen:
        b.add(NifToken(_toX(kind, _encodeInlineStr(s))))
    else:
        with let:
            payload = uint64(uint32(symId(b.pool, s))) << u64(1)  # bit 0 = 0 => pool ref
        b.add(NifToken(_toX(kind, _lowBits(payload))))
        _addSuffixIfNeeded(b, payload)


@dispatch
def addSymUse(b: mut @ TokenBuf, s: string):
    """{.nifEmits: "Y".}"""
    ## Appends a symbol use, interning `s` when it does not fit inline.
    _addSymLike(b, NifKind.Symbol, s)


@dispatch
def addSymDef(b: mut @ TokenBuf, s: string):
    """{.nifEmits: "D".}"""
    ## Appends a symbol definition, interning `s` when it does not fit inline.
    _addSymLike(b, NifKind.SymbolDef, s)


def _addInternedSymbol(b: mut @ TokenBuf, kind: NifKind, id: SymId):
    requirePools(b)
    # `symSpellingLen` rather than `symString`: this runs on every emitted
    # symbol, and only the rare name short enough to live inside the token is
    # worth building.
    if symSpellingLen(b.pool, id) <= StrInlineMaxLen:
        b.add(NifToken(_toX(kind, _encodeInlineStr(symString(b.pool, id)))))
    else:
        with let:
            payload = uint64(uint32(id)) << u64(1)
        b.add(NifToken(_toX(kind, _lowBits(payload))))
        _addSuffixIfNeeded(b, payload)


def internedSymToken(p: Pool, kind: NifKind, id: SymId) -> NifToken:
    ## The single token `addSymUse` / `addSymDef` would emit for `id`: inline when
    ## the name fits in `StrInlineMaxLen` bytes, a pool ref otherwise. Patching a
    ## Symbol/SymbolDef token IN PLACE must go through this — a raw `symToken` for
    ## a short name gives one symbol two different payloads within a tree, which
    ## breaks the same-string ⇒ same-payload invariant the writer rule
    ## establishes (and hence every payload-level equality test).
    assert kind == NifKind.Symbol or kind == NifKind.SymbolDef, string("not a symbol kind: ") + str(kind)
    if symSpellingLen(p, id) <= StrInlineMaxLen:
        return NifToken(_toX(kind, _encodeInlineStr(symString(p, id))))
    else:
        assert uint32(id) <= IdPayloadMax, (
            string("symbol id ") + str(id) + string(" needs an ExtendedSuffix chain: no single token fits"))
        return NifToken(_toX(kind, uint32(id) << u32(1)))


@dispatch
def addSymDef(b: mut @ TokenBuf, id: SymId):
    """{.nifEmits: "D".}"""
    ## Emits a symbol definition already interned in `b.pool`.
    _addInternedSymbol(b, NifKind.SymbolDef, id)


@dispatch
def addSymUse(b: mut @ TokenBuf, id: SymId):
    """{.nifEmits: "Y".}"""
    ## Emit a symbol already interned in `b.pool`. Short symbols remain inline;
    ## longer symbols reuse `id` without a second hash-table lookup.
    _addInternedSymbol(b, NifKind.Symbol, id)


@template
def _emitChained(b: mut @ TokenBuf, kind: NifKind, bits: uint64):
    ## Emit a value carrier (kinded token plus 0/1/2 ExtendedSuffix
    ## tokens) holding `bits`. Picks the minimum chain length whose
    ## carrier width covers all the set bits.
    b.add(NifToken(_toX(kind, uint32(bits & uint64(PayloadMask)))))
    if bits > uint64(PayloadMask):
        b.add(extendedSuffixToken(uint32((bits >> PayloadBits) &
                                         uint64(PayloadMask))))
        if bits >> (PayloadBits * u32(2)) != u64(0):
            b.add(extendedSuffixToken(uint32(bits >> (PayloadBits * u32(2)))))


def addIntLit(b: mut @ TokenBuf, v: int64):
    """{.nifEmits: "LIT".}"""
    ## Pure inline. Writer picks the shortest carrier whose SIGNED width holds `v`:
    ##   28-bit (one token)    for v in [-2^27, 2^27),
    ##   56-bit (two tokens)   for v in [-2^55, 2^55),
    ##   84-bit (three tokens) otherwise.
    ## The token COUNT must follow the chosen *signed* width, not `v`'s unsigned
    ## magnitude: a positive `v` whose top carrier bit is set (e.g. 2^27 ≤ v < 2^28)
    ## still needs the wider carrier, or the reader's sign-extend-from-width would
    ## read it back negative. (Hence this does NOT go through `emitChained`, which
    ## trims by magnitude — correct for unsigned/float, wrong for signed.)
    with let:
        bits = cast[uint64](v)
    b.add(NifToken(_toX(NifKind.IntLit, uint32(bits & uint64(PayloadMask)))))
    if v >= -(i64(1) << 27) and v < (i64(1) << 27):
        pass                                   # 28-bit: one token suffices
    elif v >= -(i64(1) << 55) and v < (i64(1) << 55):
        b.add(extendedSuffixToken(uint32((bits >> PayloadBits) & uint64(PayloadMask))))
    else:
        b.add(extendedSuffixToken(uint32((bits >> PayloadBits) & uint64(PayloadMask))))
        b.add(extendedSuffixToken(uint32(bits >> (PayloadBits * u32(2)))))


def addUIntLit(b: mut @ TokenBuf, v: uint64):
    """{.nifEmits: "LIT".}"""
    ## Appends an unsigned integer literal using the shortest token chain.
    _emitChained(b, NifKind.UIntLit, v)


def addFloatLit(b: mut @ TokenBuf, v: float64):
    """{.nifEmits: "LIT".}"""
    ## Appends a floating-point literal using its exact bit representation.
    _emitChained(b, NifKind.FloatLit, cast[uint64](v))

# ── Open / close tags (the only mutations that touch `openTags`) ─────────


def _openTagEscaped(b: mut @ TokenBuf, t: TagId):
    ## Slow path of `openTag`: a tag id past the 9-bit field, spelled
    ## `(<escapeTag> <id> …)` — see `TagPool.escapeTag`. The id is an ordinary
    ## child, so `closeTag`'s jump counts it and every cursor walk works
    ## unchanged; what an adapter must know is that operands start one token
    ## later.
    assert b.tags is not None and b.tags.escapeTag != TagId(u32(0)), (
        string("tag id ") + str(uint32(t)) + string(" exceeds the 9-bit tag field and this tag pool ") +
        string("declares no escape tag"))
    _ensureCap(b)
    b._openTags.add(b._len)
    b._data[b._len] = tagLitToken(b.tags.escapeTag, u32(0))
    b._len += 1
    b.addIntLit(int64(uint32(t)))


def openTag(b: mut @ TokenBuf, t: TagId):
    """{.inline, nifOpens.}"""
    ## Begin a new tagged subtree. The matching `closeTag` patches the
    ## emitted TagLit's jump in place (or splices in an `ExtendedSuffix`
    ## right after the TagLit if the body overflows the 19-bit jump field).
    ##
    ## An id past `TagMask` does not fit the token and goes through the adapter's
    ## escape tag instead; callers never have to sort the two apart.
    if not isNil(b._owner):
        prepareMutation(b)
    if uint32(t) >= FirstEscapeId:
        _openTagEscaped(b, t)
        return
    _ensureCap(b)
    b._openTags.add(b._len)
    b._data[b._len] = tagLitToken(t, u32(0))
    b._len += 1


def reopenLastTree(b: mut @ TokenBuf, pos: nint):
    ## Reopen the finished tree headed by the TagLit at `pos` so more children can
    ## be appended; close it again with `closeTag` (which recomputes the jump over
    ## the old + new children). The tree's subtree must be the last content of `b`.
    if not isNil(b._owner):
        prepareMutation(b)
    assert kind(b._data[pos]) == NifKind.TagLit, "reopenLastTree: no TagLit at pos"
    b._openTags.add(pos)


def closeTag(b: mut @ TokenBuf):
    """{.nifCloses.}"""
    ## Seal the most recently opened tag.
    if not isNil(b._owner):
        prepareMutation(b)
    assert b._openTags.len > 0, "closeTag with no matching openTag"
    with let:
        p = b._openTags.pop()
    # The TagLit at `p` may already carry trailing suffix tokens (a
    # `LineInfoLit`, and its own `ExtendedSuffix` on overflow, appended by
    # `openTag`). Those belong to the head — `tokenWidth` counts them — not to
    # the body, so the jump must exclude them. Find where the body starts.
    with var:
        headWidth = 1
    while p + headWidth < b._len and kind(b._data[p + headWidth]) >= NifKind.ExtendedSuffix:
        headWidth += 1
    with let:
        count = uint64(b._len - p - headWidth)
    if count <= uint64(InlineJumpCap):
        setJump(b._data[p], uint32(count))
    else:
        # Body too big for the 19-bit jump field. Splice a jump `ExtendedSuffix`
        # immediately after the TagLit (before any line-info suffix), shifting the
        # rest right by one. The TagLit keeps the low 19 bits of `count`; the
        # suffix carries the high bits. `tokenWidth` already counts that spliced
        # suffix as head, so the jump still encodes just the body `count` (no +1).
        # Still-open outer ancestors have positions < p, so their stored positions
        # stay valid — they see the extra token in their own count when they close.
        with let:
            highBits = uint32(count >> JumpBits)
        with let:
            lowBits = uint32(count & uint64(InlineJumpCap))
        assert highBits <= PayloadMask, (
            string("subtree exceeds 47-bit jump (size ") + str(count) + string(")"))
        _ensureCap(b)
        # Shift [p+1 .. b.len-1] right by one to make a hole at p+1.
        for i in countdown(b._len, p + 2):
            b._data[i] = b._data[i - 1]
        b._len += 1
        setJump(b._data[p], lowBits)
        b._data[p + 1] = extendedSuffixToken(highBits)


@template
def buildTree(b: mut @ TokenBuf, tag: TagId, body: untyped):
    b.openTag(tag)
    body
    b.closeTag()

# ── Cursor construction ──────────────────────────────────────────────────


def _ensureOwner(b: mut @ TokenBuf):
    """{.inline.}"""
    ## Lazily allocate the CursorOwner header, taking tracked references on
    ## both pool and tag pool so they stay alive for cursors even if the
    ## TokenBuf is freed first. Idempotent.
    if isNil(b._owner):
        b._owner = cast[_CursorOwner](alloc0(sizeof(_CursorOwnerObj)))
        b._owner._data = b._data
        b._owner._pool = b.pool
        b._owner._tags = b.tags
        GC_ref(b._owner._pool)
        GC_ref(b._owner._tags)
        b._owner._rc = 1


def unclosedTagPositions(b: TokenBuf) -> seq[nint]:
    ## Debug helper: build-time stack of still-open TagLit positions.
    return b._openTags


def beginRead(b: mut @ TokenBuf) -> Cursor:
    assert b._openTags.len == 0, "beginRead with unclosed tags"
    _ensureOwner(b)
    b._owner._rc += 1
    result = Cursor(_owner=b._owner,
                    _p=addr(b._data[0]),
                    _rem=b._len)
    return result


def childCursor(c: Cursor) -> Cursor:
    ## Returns a bounded cursor over the children of the `TagLit` at `c`.
    ## The input cursor is not advanced.
    assert kind(c) == NifKind.TagLit, "childCursor requires cursor at TagLit"
    result = c.copy()
    with let:
        headWidth = tokenWidth(result)
    result._p = cast[ptr[NifToken]](cast[uintp](result._p) +
                                    uint(headWidth) * uint(sizeof(NifToken)))
    result._rem = nint(cursorJump(c))
    return result


def endRead(c: mut @ Cursor):
    """{.inline.}"""
    if not isNil(c._owner):
        _decRcAndFree(c._owner)
    wasMovedCursor(c)


def cursorAt(b: mut @ TokenBuf, i: nint) -> Cursor:
    assert i >= 0 and i < b._len
    _ensureOwner(b)
    b._owner._rc += 1
    result = Cursor(_owner=b._owner,
                    _p=addr(b._data[i]),
                    _rem=b._len - i)
    return result


def cursorTailAt(b: mut @ TokenBuf, i: nint) -> Cursor:
    ## Like `cursorAt` but accepts `i == b.len` (a sealed tree's implicit close
    ## can leave the next position at end-of-buffer). Then `rem == 0` and the
    ## cursor reports a virtual close — only `kind`-style probes are valid.
    assert i >= 0 and i <= b._len
    _ensureOwner(b)
    b._owner._rc += 1
    result = Cursor(_owner=b._owner,
                    _p=cast[ptr[NifToken]](cast[uintp](b._data) +
                         uint(i) * uint(sizeof(NifToken))),
                    _rem=b._len - i)
    return result


def cursorToPosition(b: TokenBuf, c: Cursor) -> nint:
    """{.inline.}"""
    ## Token index of `c` within `b` (inverse of `cursorAt`). Stable key for
    ## per-expression tables (e.g. a register allocator's location map).
    return (cast[intp](c._p) - cast[intp](b._data)) // sizeof(NifToken)


def readonlyCursorAt(b: TokenBuf, i: nint) -> Cursor:
    ## Like `cursorAt` but does not require `var b`.
    ##
    ## The `CursorOwner` header is minted on demand — through a cast, since `b`
    ## is only borrowed here. It has to be: the owner is where a cursor's pools
    ## live, so an ownerless cursor answers `nil` for both `pool` and `tags` and
    ## every pool-backed payload read and every `addSubtree` off it would have to
    ## guess which pool world it came from. That guess is what the compiler's
    ## former `fallbackPool`/`fallbackTags` globals used to make. Minting the
    ## header also
    ## makes the cursor keep the tokens alive like any other cursor instead of
    ## dangling the moment `b` dies.
    ##
    ## The header costs one small allocation, and only for a buffer that has none
    ## yet; a following mutation reclaims it on the cheap `rc == 1` path.
    assert i >= 0 and i < b._len
    with let:
        mb = cast[ptr[TokenBuf]](unsafe_addr(b))
    _ensureOwner(mb.contents)
    mb._owner._rc += 1
    result = Cursor(_owner=mb._owner,
                    _p=cast[ptr[NifToken]](unsafe_addr(b._data[i])),
                    _rem=b._len - i)
    return result


@operator("+!")
def plus_bang(c: Cursor, diff: nint) -> Cursor:
    """{.inline.}"""
    ## Advance `c` by `diff` tokens, keeping the bounded `rem` correct (used by CF
    ## goto navigation). `diff` must not exceed `rem`.
    result = Cursor(_p=cast[ptr[NifToken]](cast[uintp](c._p) +
                       uint(diff) * uint(sizeof(NifToken))),
                    _rem=c._rem - diff)
    if not isNil(c._owner):
        c._owner._rc += 1
        result._owner = c._owner
    return result


def hasCurrentToken(c: Cursor) -> bool:
    """{.inline.}"""
    ## True if `c` points at a readable token (pointer + bound check). Prefer
    ## `hasMore` in regular traversal; this survives malformed input.
    return not isNil(c._p) and c._rem > 0


def unsafeDec(c: mut @ Cursor):
    """{.inline.}"""
    ## Move one token backwards (no bounds check). Only valid on a cursor known
    ## to sit past a real token; used by backward scans over a raw buffer.
    c._p = cast[ptr[NifToken]](cast[uintp](c._p) - uint(sizeof(NifToken)))
    c._rem += 1


def peekPastEnd(n: Cursor) -> Cursor:
    ## A loosely-bounded cursor at the token following the fully-consumed bounded
    ## scope `n` (`rem == 0`; the close is implicit). Read-only peek at a sibling
    ## the caller KNOWS exists.
    result = n.copy()
    result._rem = high(nint)
    return result


def sharesPools(c: Cursor, p: Pool, t: TagPool) -> bool:
    """{.inline.}"""
    ## `p == c.pool and t == c.tags`, WITHOUT materializing either of the cursor's
    ## pools. `pool`/`tags` return a `ref` by value, which is an owned temporary —
    ## an incRef, a decRef, and the pool's whole destructor behind the decRef — so
    ## the fast-path test in `addSubtree`, whose entire job is to compare two
    ## pointers, was paying for two of those per copied subtree. Read through the
    ## raw owner pointer instead: as `==` operands both sides are borrowed paths.
    ## The `nil` fallbacks are what `pool`/`tags` answer, spelled out.
    return ((p == c._owner._pool if not isNil(c._owner) and c._owner._pool is not None
             else p == _defaultPool()) and
            (t == c._owner._tags if not isNil(c._owner) and c._owner._tags is not None
             else t == _defaultTags()))

# ── Subtree copy ─────────────────────────────────────────────────────────


def _reinternLineInfo(dest: mut @ TokenBuf, c: Cursor,
                      srcPool: Pool) -> NifLineInfo:
    ## Map the source head's trailing line info into `dest`'s pools — the filename
    ## and, if present, the `#comment#` string. Returns `NoNifLineInfo` when none.
    ##
    ## Takes the source pool rather than asking `c` for it: as a parameter the ref
    ## is borrowed, while `c.pool` would return an owned temporary and pay an
    ## incRef/decRef — twice, here — per token copied. See `sharesPools`.
    requirePools(dest)
    with let:
        li = rawLineInfo(c)
    if not li.isValid():
        return NoNifLineInfo
    with let:
        fname = srcPool.filenames[li.file] if srcPool is not None else string("")
    with var:
        comment = StrId(u32(0))
    if uint32(li.comment) != u32(0) and srcPool is not None:
        comment = dest.pool.strings.getOrIncl(srcPool.strings[li.comment])
    result = NifLineInfo(file=dest.pool.filenames.getOrIncl(fname),
                         line=li.line, col=li.col, comment=comment)
    return result


def _addAcrossPools(dest: mut @ TokenBuf, c: mut @ Cursor,
                    srcPool: Pool, srcTags: TagPool):
    ## Internal: copy one value (atom or whole TagLit subtree) from `c`
    ## into `dest`, re-interning literals (via the literals pool), tag names
    ## (via the tag pool) and line-info filenames. Recurses through children.
    ## The trailing `LineInfoLit` is part of the head's width (skipped by
    ## `c.inc`), so it is re-emitted explicitly via `appendLineInfo`.
    ##
    ## The source pools are THREADED, not re-read: they are the same for every node
    ## of one subtree, and `let srcPool = c.pool` at each level cost an owned `ref`
    ## — an incRef, a decRef, and the pool's destructor behind the decRef — per
    ## token. The public wrapper below reads them once.
    with let:
        destLi = _reinternLineInfo(dest, c, srcPool)
    match kind(c):
        case NifKind.TagLit:
            with let:
                tagStr = srcTags.tags[cursorTagId(c)]
            with let:
                newTag = dest.tags.tags.getOrIncl(tagStr)
            dest.openTag(TagId(newTag))
            dest.appendLineInfo(destLi)          # right after the tag head
            with c.into():
                while hasMore(c):
                    _addAcrossPools(dest, c, srcPool, srcTags)
            dest.closeTag()
        case NifKind.StrLit:
            dest.addStrLit(strVal(c, srcPool)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.IntLit:
            dest.addIntLit(intVal(c)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.UIntLit:
            dest.addUIntLit(uintVal(c)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.FloatLit:
            dest.addFloatLit(floatVal(c)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.Symbol:
            dest.addSymUse(symName(c, srcPool)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.SymbolDef:
            dest.addSymDef(symName(c, srcPool)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.Ident:
            dest.addIdent(strVal(c, srcPool)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.CharLit:
            dest.addCharLit(charLit(c)); dest.appendLineInfo(destLi); inc(c)
        case NifKind.DotToken:
            dest.addDotToken(); dest.appendLineInfo(destLi); inc(c)
        case NifKind.LineInfoLit:
            dest.add(load(c)); inc(c)              # defensive: not a valid head token
        case NifKind.ExtendedSuffix:
            assert False, "ExtendedSuffix cannot be a head token"
        case NifKind.UnknownToken | NifKind.EofToken | NifKind.ParLe | NifKind.ParRi:
            assert False, "reader-level lexical kind cannot appear in a token buffer"


def addSubtree(dest: mut @ TokenBuf, c: Cursor):
    """{.nifEmits: "Any".}"""
    ## Copy the subtree rooted at `c` into `dest`. When both pools AND
    ## both tag pools match, this is a single bulk `copyMem`; otherwise
    ## the source's literals and tag names are re-interned into `dest`'s
    ## pools token-by-token. Callers don't need to know which case applies.
    if sharesPools(c, dest.pool, dest.tags):
        with let:
            n = subtreeWidth(c)
        if not isNil(dest._owner):
            prepareMutation(dest)
        if dest._len + n > dest._cap:
            dest._cap = max(dest._cap // 2 + dest._cap, dest._len + n)
            dest._data = cast[_Storage](realloc(dest._data, sizeof(NifToken) * dest._cap))
        copyMem(addr(dest._data[dest._len]), c._p, n * sizeof(NifToken))
        dest._len += n
    else:
        assert pool(c) is not None and tags(c) is not None
        # Read the source pools ONCE for the whole subtree and hand them down; see
        # `addAcrossPools`. These two are still owned locals — a mutable `c` may not
        # be passed alongside anything read out of it — but that is now one
        # incRef/decRef pair per SUBTREE where it used to be one per token.
        with let:
            srcPool = pool(c)
        with let:
            srcTags = tags(c)
        with var:
            cc = c.copy()
        _addAcrossPools(dest, cc, srcPool, srcTags)


def addBufferSamePool(dest: mut @ TokenBuf, src: TokenBuf):
    """{.nifEmits: "Any".}"""
    ## Append a closed buffer that shares `dest`'s literal and tag pools.
    ##
    ## The source is borrowed and remains usable. Matching pools make the
    ## append one bulk copy without constructing a read cursor.
    assert src._openTags.len == 0, "addBufferSamePool with unclosed source tags"
    if src._len == 0:
        # an empty buffer may never have been written to, leaving its pool
        # refs nil — nothing to copy, nothing to check
        return
    assert dest._data != src._data, "cannot append a TokenBuf to itself"
    # Both buffers carry their pools from construction (a plugin build's may be
    # the process defaults), so this is a plain identity test — a bulk copy is
    # only valid when the two interned id spaces are literally the same objects.
    requirePools(dest)
    with let:
        spool = (src.pool if src.pool is not None else _defaultPool())
    with let:
        stags = (src.tags if src.tags is not None else _defaultTags())
    assert dest.pool == spool and dest.tags == stags, (
        "addBufferSamePool requires matching pools")
    if not isNil(dest._owner):
        prepareMutation(dest)
    if dest._len + src._len > dest._cap:
        dest._cap = max(dest._cap // 2 + dest._cap, dest._len + src._len)
        dest._data = cast[_Storage](
            realloc(dest._data, sizeof(NifToken) * dest._cap))
    copyMem(addr(dest._data[dest._len]), src._data,
            src._len * sizeof(NifToken))
    dest._len += src._len


def addBuffer(dest: mut @ TokenBuf, src: mut @ TokenBuf):
    """{.nifEmits: "Any".}"""
    ## Append all complete top-level values from `src` to `dest`.
    ##
    ## Matching pools permit one bulk copy. Otherwise values are re-interned
    ## through `addSubtree`. `dest` and `src` must be distinct buffers.
    assert src._openTags.len == 0, "addBuffer with unclosed source tags"
    assert dest._data != src._data, "cannot append a TokenBuf to itself"
    if src._len == 0:
        return
    if dest.pool == src.pool and dest.tags == src.tags:
        dest.addBufferSamePool(src)
    else:
        with var:
            c = src.beginRead()
        while hasMore(c):
            dest.addSubtree(c)
            c.skip()


def _addWithSparseLineInfo(dest: mut @ TokenBuf, c: mut @ Cursor,
                           last: mut @ NifLineInfo):
    with let:
        info = rawLineInfo(c)
    if kind(c) == NifKind.TagLit:
        dest.openTag(cursorTagId(c))
        if info.isValid() and info != last:
            dest.appendLineInfo(info)
            last <<= info
        with c.into():
            while hasMore(c):
                _addWithSparseLineInfo(dest, c, last)
        dest.closeTag()
    else:
        for i in range(0, valueWidth(c)):
            dest.add(_peekAhead(c, i))
        if info.isValid() and info != last:
            dest.appendLineInfo(info)
            last <<= info
        inc(c)


def withSparseLineInfo(src: mut @ TokenBuf) -> TokenBuf:
    ## A copy of `src`, in the same pools, that keeps a `LineInfoLit` only where
    ## the location changes in stream order — exactly what a `parse` without
    ## `denseLineInfo` stores. The inverse of a densifying load.
    ##
    ## Passes that measure code in raw tokens (shoggoth's unswitch bound) see
    ## line-info suffixes too, so the same program is "bigger" when its info is
    ## dense; this lets a consumer that was calibrated on sparse input keep
    ## seeing sparse input without a render-and-reparse round trip.
    result = createTokenBuf(src._len, src.pool, src.tags)
    with var:
        c = beginRead(src)
    with var:
        last = NoNifLineInfo.copy()
    while hasMore(c):
        _addWithSparseLineInfo(result, c, last)
    endRead(c)
    return result

# ── Self-test ────────────────────────────────────────────────────────────

if comptime(__name__ == "__main__"):
    from nimic.std.formatfloat import *  # nimPreviewSlimSystem: `$`/echo of float64

    @template
    def test(a: untyped, b: untyped):
        with let:
            xx = a
        if xx != b:
            echo(string("test failed "), astToStr(a), string(": got "), xx, string(" expected "), b)
            quit(1)

    # In a proc, not at module level: host Nim rejects the `{.nifWrap.}` statement of `into` /
    # `peekInto` expanded at module level ("custom pragmas are not supported for modules").
    def _selfTest():
        with block("bit_layout"):
            with let:
                tp = newTagPool()
            with let:
                tFoo = tp.registerTag(string("foo"))
            with var:
                n = tagLitToken(tFoo, u32(0))
            test(kind(n), NifKind.TagLit)
            test(_rawTag(n), tFoo)
            test(_rawJump(n), u32(0))
            setJump(n, u32(42))
            test(_rawTag(n), tFoo)
            test(_rawJump(n), u32(42))

        with block("round_trip_sealed"):
            # (foo (bar "hi" 42) 3.14) — pure TagLits, no closers in the buffer.
            with var:
                b = createTokenBuf(8)
            with let:
                tFoo = b.tags.registerTag(string("foo"))
            with let:
                tBar = b.tags.registerTag(string("bar"))
            with b.buildTree(tFoo):
                with b.buildTree(tBar):
                    b.addStrLit(string("hi"))
                    b.addIntLit(42)
                b.addFloatLit(3.14)
            # 1 foo + (1 bar + 1 "hi" + 1 (small int 42)) + 3 (3.14 needs 3 tokens
            # for the full float64 bit pattern) = 7 tokens.
            test(b._len, 7)

            with var:
                c = b.beginRead()
            test(kind(c), NifKind.TagLit)
            test(cursorTagId(c), tFoo)
            test(cursorJump(c), u64(6))
            with c.into():
                test(kind(c), NifKind.TagLit)
                test(cursorTagId(c), tBar)
                test(cursorJump(c), u64(2))
                with c.into():
                    test(kind(c), NifKind.StrLit)
                    test(strVal(c), string("hi")); inc(c)
                    test(kind(c), NifKind.IntLit)
                    test(intVal(c), 42); inc(c)
                test(kind(c), NifKind.FloatLit)
                test(floatVal(c), 3.14); inc(c)

        with block("add_subtree_cross_pool"):
            with var:
                src = createTokenBuf(4)
            with let:
                tFoo = src.tags.registerTag(string("foo"))
            with src.buildTree(tFoo):
                src.addStrLit(string("hello"))
                src.addIntLit(7)
            with var:
                dest = createTokenBuf(4)
            test((src.pool == dest.pool), False)
            test((src.tags == dest.tags), False)
            with var:
                c = src.beginRead()
            dest.addSubtree(c)                       # re-interns via cross-pool path
            with var:
                d = dest.beginRead()
            test(kind(d), NifKind.TagLit)
            test(dest.tags.tagName(cursorTagId(d)), string("foo"))
            with d.into():
                test(strVal(d), string("hello")); inc(d)
                test(intVal(d), 7); inc(d)

        with block("add_subtree_same_pools"):
            # Both pools shared → bulk copyMem.
            with let:
                p = newPool()
            with let:
                tp = newTagPool()
            with var:
                src = createTokenBuf(4, p, tp)
            with let:
                tBar = tp.registerTag(string("bar"))
            with src.buildTree(tBar):
                src.addStrLit(string("longish"))   # > 3 bytes → pool path, exercises sharing
                src.addIntLit(9)
            with var:
                dest = createTokenBuf(4, p, tp)
            test((src.pool == dest.pool), True)
            test((src.tags == dest.tags), True)
            with let:
                srcStrId = uint32(p.strings.getOrIncl(string("longish")))
            with var:
                c = src.beginRead()
            dest.addSubtree(c)
            with var:
                d = dest.beginRead()
            test(kind(d), NifKind.TagLit)
            with d.into():
                # Same pool → bulk-copied; the token payload's pool id is preserved.
                test((uoperand(load(d)) >> 1), srcStrId)
                inc(d)
                inc(d)

        with block("add_subtree_shared_literals_different_tags"):
            # Real-world cross-format use: jsonnif and htmlnif share a literals
            # pool but keep separate tag pools.
            with let:
                p = newPool()
            with var:
                src = createTokenBuf(4, p)            # gets its own fresh tag pool
            with let:
                tJ = src.tags.registerTag(string("oconstr"))
            with src.buildTree(tJ):
                src.addStrLit(string("sharedlonger"))
            with var:
                dest = createTokenBuf(4, p)           # different tag pool
            with var:
                c = src.beginRead()
            dest.addSubtree(c)                          # must re-intern the tag…
            with var:
                d = dest.beginRead()
            test(dest.tags.tagName(cursorTagId(d)), string("oconstr"))
            # …but the literal "sharedlonger" stays at the same StrId in p.
            with d.into():
                test((uoperand(load(d)) >> 1), uint32(p.strings.getOrIncl(string("sharedlonger"))))
                inc(d)

        with block("inline_short_str"):
            # Strings ≤ 3 bytes inline directly into the token. No pool touch.
            with var:
                b = createTokenBuf(8)
            b.addStrLit(string(""))
            b.addStrLit(string("x"))
            b.addStrLit(string("ab"))
            b.addStrLit(string("abc"))
            b.addStrLit(string("abcd"))   # length 4 → pool
            test(len(b.pool.strings), 1)     # only "abcd" interned
            with var:
                c = b.beginRead()
            test(isInlineLit(c), True);  test(strVal(c, b.pool), string(""));    inc(c)
            test(isInlineLit(c), True);  test(strVal(c, b.pool), string("x"));   inc(c)
            test(isInlineLit(c), True);  test(strVal(c, b.pool), string("ab"));  inc(c)
            test(isInlineLit(c), True);  test(strVal(c, b.pool), string("abc")); inc(c)
            test(isInlineLit(c), False); test(strVal(c, b.pool), string("abcd")); inc(c)

        with block("inline_int_chain"):
            # 28-bit signed → 1 token; 56-bit → 2 tokens; > 56-bit → 3 tokens.
            # Pool.integers is gone — verify by tokens-per-value via len bookkeeping.
            with var:
                b = createTokenBuf(16)
            with let:
                beforeShort = b._len.copy()
            b.addIntLit(0);                  test(b._len - beforeShort, 1)
            with let:
                beforeSmall = b._len.copy()
            b.addIntLit(1_000_000);          test(b._len - beforeSmall, 1)
            with let:
                beforeWide = b._len.copy()
            b.addIntLit(i64(1) << 40);       test(b._len - beforeWide, 2)
            with let:
                beforeVeryWide = b._len.copy()
            b.addIntLit(high(int64));        test(b._len - beforeVeryWide, 3)
            with let:
                beforeNeg = b._len.copy()
            b.addIntLit(low(int64));         test(b._len - beforeNeg, 3)

            with var:
                c = b.beginRead()
            test(intVal(c), i64(0));            inc(c)
            test(intVal(c), i64(1_000_000));    inc(c)
            test(intVal(c), i64(1) << 40);     inc(c)
            test(intVal(c), high(int64));      inc(c)
            test(intVal(c), low(int64));       inc(c)

        with block("inline_uint_chain"):
            with var:
                b = createTokenBuf(8)
            b.addUIntLit(u64(0))
            b.addUIntLit(u64(1) << 27)         # 2 tokens (just past 28-bit unsigned cap)
            b.addUIntLit(u64(1) << 50)         # 2 tokens
            b.addUIntLit(high(uint64))         # 3 tokens
            with var:
                c = b.beginRead()
            test(uintVal(c), u64(0));            inc(c)
            test(uintVal(c), u64(1) << 27);     inc(c)
            test(uintVal(c), u64(1) << 50);     inc(c)
            test(uintVal(c), high(uint64));     inc(c)

        with block("inline_float_chain"):
            with var:
                b = createTokenBuf(6)
            b.addFloatLit(0.0)     # all-zero bit pattern → 1 token
            b.addFloatLit(3.14)    # all 64 bits used → 3 tokens
            b.addFloatLit(-0.5)    # 3 tokens
            with var:
                c = b.beginRead()
            test(floatVal(c), 0.0);  inc(c)
            test(floatVal(c), 3.14); inc(c)
            test(floatVal(c), -0.5); inc(c)

        with block("extended_suffix_jump"):
            # Build a subtree larger than InlineJumpCap so `closeTag` splices an
            # ExtendedSuffix right after the TagLit.
            with let:
                big = nint(InlineJumpCap) + 1   # 524288 body tokens
            with var:
                b = createTokenBuf(big + 4)
            with let:
                tT = b.tags.registerTag(string("t"))
            with b.buildTree(tT):
                for _ in range(0, big):
                    b.addDotToken()
            # After splice: 1 (TagLit) + 1 (suffix) + big body = big + 2
            test(b._len, big + 2)
            test(kind(b[0]), NifKind.TagLit)
            test(_rawTag(b[0]), tT)
            test(kind(b[1]), NifKind.ExtendedSuffix)

            with var:
                c = b.beginRead()
            test(kind(c), NifKind.TagLit)                          # one load, no branch
            test(cursorTagId(c), tT)
            test(cursorJump(c), uint64(big))               # body count (suffix is head)
            c.skip()
            test(c._rem, 0)

        with block("line_info_common_and_overflow"):
            with var:
                b = createTokenBuf(16)
            with let:
                fA = b.pool.filenames.getOrIncl(string("a.nim"))
            with let:
                fB = b.pool.filenames.getOrIncl(string("b.nim"))
            # common layout (fits 7/7/14)
            b.addStrLit(string("x"));  b.appendLineInfo(fA, i32(100), i32(12))
            # a value with its own ExtendedSuffix chain, plus line info after it
            b.addIntLit(i64(1) << 40);  b.appendLineInfo(fA, i32(101), i32(1))
            # overflow layout (line beyond 14 bits → wide)
            b.addStrLit(string("y"));  b.appendLineInfo(fB, i32(200000), i32(5))
            # a head with no line info
            b.addCharLit(ch("z"))

            with var:
                c = b.beginRead()
            with block:
                test(kind(c), NifKind.StrLit); test(strVal(c), string("x"))
                with let:
                    li = rawLineInfo(c)
                test(uint32(li.file), uint32(fA)); test(li.line, i32(100)); test(li.col, i32(12))
                test(lineInfoFile(c), string("a.nim"))
                inc(c)
            with block:
                test(kind(c), NifKind.IntLit); test(intVal(c), i64(1) << 40)
                with let:
                    li = rawLineInfo(c)            # info read past the value's suffix
                test(uint32(li.file), uint32(fA)); test(li.line, i32(101)); test(li.col, i32(1))
                inc(c)
            with block:
                test(kind(c), NifKind.StrLit); test(strVal(c), string("y"))
                with let:
                    li = rawLineInfo(c)            # overflow (wide) layout
                test(uint32(li.file), uint32(fB)); test(li.line, i32(200000)); test(li.col, i32(5))
                test(lineInfoFile(c), string("b.nim"))
                inc(c)
            with block:
                test(kind(c), NifKind.CharLit); test(charLit(c), ch("z"))
                test(rawLineInfo(c).isValid(), False)    # no line info present
                inc(c)

        with block("line_info_with_comment"):
            with var:
                b = createTokenBuf(16)
            with let:
                f = b.pool.filenames.getOrIncl(string("c.nim"))
            with let:
                doc = b.pool.strings.getOrIncl(string("## a doc comment"))
            # comment on a head whose position would fit the common layout → forced wide
            b.addStrLit(string("x"));          b.appendLineInfo(f, i32(10), i32(4), doc)
            # comment alongside a value that has its OWN ExtendedSuffix chain
            b.addIntLit(i64(1) << 40); b.appendLineInfo(f, i32(11), i32(2), doc)
            # line info without a comment still reports comment 0
            b.addStrLit(string("y"));          b.appendLineInfo(f, i32(12), i32(1))

            with var:
                c = b.beginRead()
            with block:
                test(kind(c), NifKind.StrLit); test(strVal(c), string("x"))
                with let:
                    li = rawLineInfo(c)
                test(uint32(li.file), uint32(f)); test(li.line, i32(10)); test(li.col, i32(4))
                test(uint32(li.comment), uint32(doc))
                test(b.pool.strings[li.comment], string("## a doc comment"))
                inc(c)
            with block:
                test(kind(c), NifKind.IntLit); test(intVal(c), i64(1) << 40)
                with let:
                    li = rawLineInfo(c)            # comment read past the value's suffix
                test(li.line, i32(11)); test(li.col, i32(2)); test(uint32(li.comment), uint32(doc))
                inc(c)
            with block:
                test(kind(c), NifKind.StrLit); test(strVal(c), string("y"))
                with let:
                    li = rawLineInfo(c)
                test(li.line, i32(12)); test(uint32(li.comment), u32(0))   # no comment
                inc(c)

            # cross-pool copy of the first value must re-intern the comment string
            with var:
                dest = createTokenBuf(16)
            with var:
                cc = b.beginRead()
            dest.addSubtree(cc)                    # different pools → addAcrossPools
            with var:
                d = dest.beginRead()
            test(kind(d), NifKind.StrLit); test(strVal(d), string("x"))
            with let:
                dli = rawLineInfo(d)
            test((uint32(dli.comment) != u32(0)), True)
            test(dest.pool.strings[dli.comment], string("## a doc comment"))
            test(dli.line, i32(10)); test(dli.col, i32(4))

        with block("line_info_on_tags_and_cross_pool"):
            with var:
                src = createTokenBuf(8)
            with let:
                t = src.tags.registerTag(string("stmt"))
            with let:
                f = src.pool.filenames.getOrIncl(string("m.nim"))
            src.openTag(t)
            src.appendLineInfo(f, i32(7), i32(3))       # line info on the tag head
            src.addIntLit(42)
            src.closeTag()
            # tag jump must count only the body (the IntLit), not the LineInfoLit head
            with block:
                with var:
                    c = src.beginRead()
                test(kind(c), NifKind.TagLit); test(cursorJump(c), u64(1))
                with let:
                    li = rawLineInfo(c)
                test(li.line, i32(7)); test(li.col, i32(3)); test(lineInfoFile(c), string("m.nim"))
                with c.into():
                    test(intVal(c), i64(42)); inc(c)       # into must land past the tag head
            # cross-pool copy must re-intern the filename and preserve line/col
            with var:
                dest = createTokenBuf(8)
            with block:
                with var:
                    c = src.beginRead()
                dest.addSubtree(c)                       # different pools → addAcrossPools
            with var:
                d = dest.beginRead()
            test(kind(d), NifKind.TagLit)
            test(dest.tags.tagName(cursorTagId(d)), string("stmt"))
            with let:
                dli = rawLineInfo(d)
            test(dli.line, i32(7)); test(dli.col, i32(3))
            test(lineInfoFile(d), string("m.nim"))
            with d.into():
                test(intVal(d), i64(42)); inc(d)

        echo(string("nifcore self-tests passed"))

    _selfTest()


# ── Added tests ──────────────────────────────────────────────────────────

if comptime(__name__ == "__main__"):
    class _Color(NIntEnum):
        red = auto()
        green = auto()
        blue = auto()

    def _rc(b: TokenBuf) -> nint:
        return 0 if isNil(b._owner) else b._owner._rc

    def _addedTests():  # in a proc for the same reason as _selfTest
        # reference counts: beginRead, a copied cursor, endRead, mutation while reading,
        # reclaiming the owner, childCursor
        with block("ownership"):
            with var:
                b = createTokenBuf(4)
            b.addIntLit(10)
            b.addIntLit(20)
            echo(string("built: rc "), _rc(b))
            with var:
                c = beginRead(b)
            echo(string("after beginRead: rc "), _rc(b))

            with block:  # the copy is destroyed at the end of the block
                with var:
                    cc = c.copy()
                inc(cc)
                echo(string("with copied cursor: rc "), _rc(b), string(", copy at "), intVal(cc))
            echo(string("after copied cursor gone: rc "), _rc(b))
            endRead(c)
            echo(string("after endRead: rc "), _rc(b))

            # a mutation while a cursor reads: prepareMutation copies, the old owner stays with the cursor
            with var:
                c2 = beginRead(b)
            b.addIntLit(30)
            echo(string("mutation while reading: buffer rc "), _rc(b), string(", cursor rc "), c2._owner._rc,
                 string(", cursor still reads "), intVal(c2))
            endRead(c2)

            # a mutation without cursors reclaims the owner header
            with var:
                c3 = beginRead(b)
            endRead(c3)
            echo(string("before reclaim: rc "), _rc(b))
            b.addIntLit(40)
            echo(string("after reclaim: rc "), _rc(b), string(", len "), len(b))

            with var:
                b2 = createTokenBuf(4)
            with let:
                t = b2.tags.registerTag(string("t"))
            with b2.buildTree(t):
                b2.addIntLit(1)
                b2.addIntLit(2)
            with var:
                tree = beginRead(b2)
            with var:
                child = childCursor(tree)
            echo(string("childCursor: rc "), _rc(b2), string(", rem "), child._rem, string(", first "), intVal(child))
            with var:
                second = child.plus_bang(1)
            echo(string("+!: rc "), _rc(b2), string(", rem "), second._rem, string(", value "), intVal(second))
            endRead(second)
            endRead(child)
            endRead(tree)
            echo(string("after all cursors ended: rc "), _rc(b2))

        # the ids: `$`, `==`, hash; NifLineInfo and NifSymbol: ==, hash
        with block("ids_and_hashes"):
            echo(TagId(u32(3)), string(" "), StrId(u32(4)), string(" "), SymId(u32(5)))
            echo(TagId(u32(3)) == TagId(u32(3)), string(" "), hash(StrId(u32(4))) == hash(StrId(u32(4))))
            with let:
                li = NifLineInfo(file=FileId(u32(2)), line=i32(10), col=i32(3), comment=StrId(u32(0)))
            echo(li == NifLineInfo(file=FileId(u32(2)), line=i32(10), col=i32(3), comment=StrId(u32(0))),
                 string(" "), li == NoNifLineInfo, string(" "), li.isValid(), string(" "), NoNifLineInfo.isValid())
            echo(hash(li), string(" "), hash(NoNifLineInfo))
            with let:
                s = NifSymbol(name=StrId(u32(1)), disamb=i32(12), dedup=StrId(u32(0)), module=StrId(u32(2)))
            echo(hash(s), string(" "), s == s, string(" "), isLocal(s))

        # token constructors and raw accessors
        with block("tokens"):
            with var:
                n = tagLitToken(TagId(u32(3)), u32(5))
            setTag(n, TagId(u32(7)))
            echo(_rawTag(n), string(" "), _rawJump(n), string(" "), kind(n))
            echo(kind(dotToken()), string(" "), kind(charToken(ch("a"))), string(" "), uoperand(charToken(ch("a"))))
            echo(kind(strLitToken(StrId(u32(9)))), string(" "), uoperand(symToken(SymId(u32(9)))),
                 string(" "), kind(symdefToken(SymId(u32(9)))), string(" "), kind(identToken(StrId(u32(9)))))
            with var:
                b = createTokenBuf(4)
            b.addIntLit(-5)
            echo(soperand(b[0]), string(" "), kind(b[0]))

        # the symbol API
        with block("symbols"):
            with let:
                p = newPool()
            with let:
                id = symId(p, string("abc.12.Ikey.mod"))
            echo(symString(p, id), string("|"), symBasename(p, id), string("|"), symVersionedBasename(p, id),
                 string("|"), symWithoutModule(p, id), string("|"), symModule(p, id))
            echo(symIsInstantiation(p, id), string(" "), symIsLocal(p, id), string(" "), symModuleIs(p, id, string("mod")),
                 string(" "), symModuleIs(p, id, string("other")), string(" "), symSpellingLen(p, id),
                 string(" "), symString(p, id).len)
            with let:
                other = symId(p, string("abc"), 12, string("other"), string("Ikey"))
            echo(symSameEntity(p, id, other), string(" "), symSameEntity(p, id, id), string(" "), symString(p, other))
            with let:
                local = symId(p, string("p.0h107"))
            echo(symString(p, local), string("|"), symBasename(p, local), string("|"), symIsLocal(p, local),
                 string("|"), symIsInstantiation(p, local), string("|"), symModule(p, local))
            with let:
                twoKeys = symId(p, string("foo.0.Ia.Ib.mod"))
            echo(symIsInstantiation(p, twoKeys), string(" "), sym(p, twoKeys).disamb, string(" "), symNameId(p, id) == sym(p, id).name)
            echo(parseDisamb(string("x.12"), 2, 2), string(" "), parseDisamb(string("00"), 0, 2), string(" "),
                 parseDisamb(string("0"), 0, 1), string(" "), parseDisamb(string("1a"), 0, 2), string(" "),
                 parseDisamb(string(""), 0, 0))
            with let:
                sp = syms(p)
            echo(sp.getKeyId(string("abc.12.Ikey.mod")) == id, string(" "), sp.getKeyId(string("abc.12.Ikey.nomod")),
                 string(" "), sp.getKeyId(string("zzz.1")), string(" "), sp[id], string(" "), sp.len,
                 string(" "), sp.getOrIncl(string("abc.12.Ikey.mod")) == id, string(" "), poolSym(p, local))

        # tag pools: createTags, hasEscapes, escaped tags
        with block("tag_pools"):
            with let:
                tp = createTags[_Color]()
            echo(tp.tagName(TagId(u32(1))), string(" "), tp.tagName(TagId(u32(3))), string(" "), hasEscapes(tp))
            with let:
                esc = newTagPool()
            esc.escapeTag = esc.registerTag(string("esc"))
            with var:
                b = createTokenBuf(4, None, esc)
            b.openTag(TagId(FirstEscapeId + u32(5)))
            b.addIntLit(999)
            b.closeTag()
            with var:
                c = beginRead(b)
            echo(hasEscapes(esc), string(" "), isEscapedTag(c), string(" "), uint32(resolvedTagId(c)),
                 string(" "), uint32(cursorTagId(c)), string(" "), escapeTagOf(c))
            endRead(c)

        # the builder API, positions, partial scopes
        with block("builders_and_positions"):
            with var:
                b = createTokenBuf(4)
            b.addDotToken()
            b.addCharLit(ch("k"))
            b.addIdent(string("myIdent"))
            with let:
                sid = symId(b.pool, string("sym.0"))
            b.addSymUse(sid)
            b.addSymDef(sid)
            b.addSymUse(string("use.1"))
            b.addSymDef(string("def.2"))
            b.addUIntLit(u64(100))
            echo(string("builder tokens: len "), len(b))
            with var:
                c = cursorAt(b, 2)
            echo(kind(c), string(" "), strVal(c), string(" "), strId(c) == b.pool.strings.getOrIncl(string("myIdent")),
                 string(" "), cursorToPosition(b, c), string(" "), toUniqueId(c) == toUniqueId(cursorAt(b, 2)))
            inc(c)
            echo(symName(c), string(" "), symId(c) == sid, string(" "), internedSymToken(b.pool, NifKind.Symbol, sid) == load(c))
            unsafeDec(c)
            echo(cursorToPosition(b, c), string(" "), c._rem, string(" "), hasCurrentToken(c), string(" "), cursorIsNil(c))
            with var:
                tail = cursorTailAt(b, len(b))
            echo(tail._rem, string(" "), hasCurrentToken(tail), string(" "), sharesPools(c, b.pool, b.tags),
                 string(" "), sharesPools(c, newPool(), b.tags), string(" "), pool(c) == b.pool, string(" "), tags(c) == b.tags)
            endRead(c)
            endRead(tail)
            b.shrink(len(b) - 2)
            echo(string("after shrink: len "), len(b))

            with var:
                b2 = createTokenBuf(4)
            b2.addIntLit(111)
            b2.addIntLit(222)
            b.insert(b2, 1)
            echo(string("after insert: len "), len(b), string(", at 1: "), intVal(cursorAt(b, 1)))

            # readonlyCursorAt on a buffer that already has an owner
            with var:
                cInit = beginRead(b)
            endRead(cInit)
            with var:
                cro = readonlyCursorAt(b, 1)
            echo(string("readonlyCursorAt: "), kind(cro), string(" "), intVal(cro))
            endRead(cro)
            # on a fresh buffer: the owner is minted through the cast view of `b`, and both cursors share it
            with var:
                fresh = createTokenBuf(4)
            fresh.addIntLit(5)
            fresh.addIntLit(6)
            with var:
                ro1 = readonlyCursorAt(fresh, 0)
            with var:
                ro2 = readonlyCursorAt(fresh, 1)
            echo(string("readonlyCursorAt on a fresh buffer: rc "), _rc(fresh), string(", "), intVal(ro1),
                 string(" "), intVal(ro2), string(", pools "), pool(ro1) == fresh.pool)
            endRead(ro1)
            endRead(ro2)
            echo(string("after both ended: rc "), _rc(fresh))

        # reopenLastTree, replace, sub, peekInto, peekPastEnd, subtreeWidth
        with block("trees"):
            with var:
                b = createTokenBuf(8)
            with let:
                t = b.tags.registerTag(string("t"))
            with let:
                u = b.tags.registerTag(string("u"))
            with b.buildTree(t):
                b.addIntLit(1)
            b.reopenLastTree(0)
            b.addIntLit(2)
            b.closeTag()
            b.addIntLit(3)
            with var:
                c = beginRead(b)
            echo(string("reopened jump "), cursorJump(c), string(", width "), subtreeWidth(c))
            with let:
                body = sub(c)
            echo(string("sub: rem "), body._rem, string(", first "), intVal(body), string(", c still at "), kind(c))
            with var:
                first = body.copy()
            skip(first)
            skip(first)
            echo(string("peekPastEnd: "), intVal(peekPastEnd(first)))
            with c.peekInto():
                echo(string("peekInto first child "), intVal(c))
            echo(string("after peekInto: "), intVal(c), string(" rem "), c._rem)
            endRead(c)

            with var:
                by = createTokenBuf(4, b.pool, b.tags)
            with by.buildTree(u):
                by.addIntLit(7)
                by.addIntLit(8)
                by.addIntLit(9)
            with var:
                cb = beginRead(by)
            b.replace(cb, 0)
            endRead(cb)
            with var:
                r = beginRead(b)
            echo(string("replace: len "), len(b), string(", tag "), b.tags.tagName(cursorTagId(r)), string(", jump "), cursorJump(r))
            skip(r)
            echo(string("after replaced tree: "), intVal(r))
            endRead(r)

            # rootOf: the first Symbol of a subtree (a loop template: `for _ in n.loopInto():`)
            with var:
                lv = createTokenBuf(8)
            with let:
                dot = lv.tags.registerTag(string("dot"))
            with let:
                bracket = lv.tags.registerTag(string("at"))
            with lv.buildTree(dot):
                lv.addIntLit(1)
                with lv.buildTree(bracket):
                    lv.addSymUse(string("abcd.1"))
                lv.addSymUse(string("zz.2"))
            lv.addIntLit(5)
            with var:
                lc = beginRead(lv)
            echo(string("rootOf: "), symString(lv.pool, rootOf(lc)))
            skip(lc)
            echo(string("rootOf an atom: "), rootOf(lc))
            endRead(lc)

        # adoptForeignTokens borrows the block, a mutation forks it; growRawUninit
        with block("foreign_tokens"):
            with var:
                src = createTokenBuf(4)
            src.addIntLit(5)
            src.addIntLit(6)
            with var:
                adopted = adoptForeignTokens(rawTokenPtr(src), len(src), src.pool, src.tags)
            echo(string("adopted: len "), len(adopted), string(", rc "), _rc(adopted), string(", same block "),
                 rawTokenPtr(adopted) == rawTokenPtr(src))
            adopted.addIntLit(7)
            echo(string("after mutation: rc "), _rc(adopted), string(", same block "), rawTokenPtr(adopted) == rawTokenPtr(src),
                 string(", len "), len(adopted), string(", src len "), len(src))
            with var:
                g = createTokenBuf(1)
            with let:
                raw = growRawUninit(g, 3)
            echo(string("growRawUninit: len "), len(g), string(", nil "), isNil(raw))
            g.shrink(0)
            echo(string("shrunk: len "), len(g))

        # addBuffer, addBufferSamePool, withSparseLineInfo (and the constant NoNifLineInfo stays untouched)
        with block("buffers_and_sparse_info"):
            with var:
                srcB = createTokenBuf(4)
            srcB.addStrLit(string("hello_buf"))
            with var:
                dstB = createTokenBuf(4)
            dstB.addBuffer(srcB)
            with var:
                same = createTokenBuf(4, srcB.pool, srcB.tags)
            same.addBufferSamePool(srcB)
            with var:
                cd = beginRead(dstB)
            with var:
                cs = beginRead(same)
            echo(string("addBuffer: "), strVal(cd), string(", addBufferSamePool: "), strVal(cs))
            endRead(cd)
            endRead(cs)

            with var:
                dense = createTokenBuf(8)
            with let:
                f = dense.pool.filenames.getOrIncl(string("s.nim"))
            dense.addIntLit(1); dense.appendLineInfo(f, i32(7), i32(1))
            dense.addIntLit(2); dense.appendLineInfo(f, i32(7), i32(1))
            dense.addIntLit(3); dense.appendLineInfo(f, i32(8), i32(1))
            with var:
                sparse = withSparseLineInfo(dense)
            echo(string("withSparseLineInfo: len "), len(dense), string(" -> "), len(sparse))
            echo(string("NoNifLineInfo unchanged: "), NoNifLineInfo.line, string(" "), uint32(NoNifLineInfo.file))

    _addedTests()
