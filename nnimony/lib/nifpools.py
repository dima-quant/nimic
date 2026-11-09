# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lib/nifpools.nim
# ///
## nifpools — nifcore plus the process-global literal/tag pools and the
## NifLineInfo bridge that nimsem/hexer are architected around. This is the
## module the frontend imports (usually via nifprelude); lengc-style code that
## manages its own pools imports nifcore/nifcoreparse directly. The Nim
## compiler's IC modules use the classic surface in nifstreams.nim instead.
##
## Two model bridges do the real work:
##
##  1. Global pool.  The frontend is architected around ONE global `pool`
##     (every intern table) + `globalTags` + `lineMan`; nifcore scopes pools
##     per-TokenBuf. We bridge by threading the globals through every
##     `createTokenBuf`, so ids are comparable across buffers. nifcore's
##     `Pool.strings/syms/filenames` are plain `BiTable[_,string]`s, so
##     `pool.strings[id]` is direct field access; symbols go through the
##     `sym*` accessors in nifcore (#2457).
##
##  2. Line info.  The frontend speaks nifcore's `NifLineInfo` struct
##     directly: `.info` reads decode the token's `LineInfoLit` suffix, the
##     info-carrying builders re-attach it via `appendLineInfo`. The classic
##     `PackedLineInfo`/`lineMan` bridge is gone from the frontend; it
##     survives only in nifstreams.nim for the frozen Nim-compiler side.
##     `NoLineInfo` is kept as the frontend's name for `NoNifLineInfo`.
##
## Inline literals need no bridge: nifcore stores int/uint/float inline and
## code reads `intVal`/`uintVal`/`floatVal` directly.
##
## The rest of the module is real API on top of nifcore: info-carrying
## builders (`addParLe`/`buildTree`/`copyInto`/`add*Lit`), safe node
## predicates (`isTagLit` & friends), raw-token accessors for the CF listing
## (`int28Token`/`getInt28`, `symId`/`strId`/`tagId` on `NifToken`), skip
## intents for the pass validator, and parse/render entry points.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    pragma('feature: "assumeSync"')  # compiler-internal globals; single threaded

from nimic.std import assertions
from .nifcore import (
    addIdent, addStrLit, addSubtree, addSymDef,
    addSymUse, charLit, createTokenBuf, Cursor, cursorTagId,
    endRead, enterScope, getOrIncl, initTokenBuf, internedSymToken, into,
    JumpShift, kind, KindBits, load, newPool, newTagPool, NifKind, NifLineInfo, NifToken, NoNifLineInfo,
    PayloadMask, Pool, registerTag, setJump, skip, soperand, StrId,
    subtreeWidth, SymId, symId, TagId, TagMask, TagPool, TagShift, TokenBuf,
    uoperand)
from . import nifcore
from . import comesfrom
from . import nifroles
export(nifroles)
# Template-expansion provenance rides in the line-info filename, so every
# consumer of a filename may need to strip it (`realFile`). Plain string
# handling with no NIF dependency of its own; re-exported here so it travels
# with the pool API rather than being imported separately everywhere.
export(comesfrom)
# Re-export nifcore verbatim except the two helpers whose shim versions below
# thread the global pool. `kind`/`NifKind`/its members are re-exported AS-IS:
# the sem port uses nifcore's own kind model directly (`TagLit`, `StrLit`,
# `hasMore` for end-of-scope) — there is no classic `NifKind` shim, because
# nimony's type-bound lookup makes `nifcore.kind(Cursor)` impossible to shadow.
exportExcept(nifcore, "createTokenBuf", "pool", "addIdent")
# nifcore re-exports bitabs and lineinfos.{FileId,NoFile,isValid} — all the
# lineinfos surface the frontend still needs. PackedLineInfo/LineInfoManager/
# pack/unpack stay out of scope here (nifstreams keeps them for the Nim side).
from ..models.tags import TagData, TagEnum  # TagEnum + TagData (the master tag namespace)

# ── Global pool / tags / line-info manager ───────────────────────────────


def _createMasterTagPool() -> TagPool:
    ## Seeded so each tag's `TagId` equals its master `TagEnum` ordinal
    ## (same pattern as nifcdecl.createLengTagPool).
    result = newTagPool()
    for e in inrange(low(TagEnum), high(TagEnum)):
        if e != TagEnum.InvalidTagId:
            with let:
                id = registerTag(result, TagData[e][0])
            assert uint32(id) == uint32(e), \
                string("tag pool misalignment for ") + TagData[e][0]
    return result


with var:
    globalTags: TagPool = _createMasterTagPool()

with const:
    NoLineInfo = NoNifLineInfo
    ## The frontend's classic name for "no line info". A plain `NifLineInfo`
    ## with `NoFile`; test with `isValid`, don't compare against it.

# The old global `pool` (a nifstreams `Literals`) IS a nifcore `Pool` here, so
# `pool.strings` / `pool.syms` / `pool.filenames` resolve to real BiTable fields
# — `pool.strings.getOrIncl`, `.len`, `[id]` all work unchanged. Tags live in a
# separate `TagPool`, and int/float have no pool, so `pool.tags` / `.files` /
# `.integers` / `.man` are accessors (below, after the proxy types).
with var:
    pool: Pool = newPool()

# ── Type aliases ─────────────────────────────────────────────────────────

# ── Buffer construction: thread the global pool + tags ───────────────────


@dispatch
def createTokenBuf(cap=16) -> TokenBuf:
    ## Every shim buffer shares the one global literals + tag namespace, so ids
    ## are comparable across buffers (the nifstreams global-`pool` invariant).
    return nifcore.createTokenBuf(cap, sharedPool=pool, sharedTags=globalTags)


@dispatch
def initTokenBuf() -> TokenBuf:
    """{.inline.}"""
    ## `createTokenBuf` without the eager storage allocation: the buffer is bound
    ## to the global pools, the first `add` allocates. Use it wherever a buffer
    ## used to be left as `default(TokenBuf)` — an object field, a `seq` slot —
    ## and would otherwise reach the builders with no tag pool at all.
    return nifcore.initTokenBuf(pool, globalTags)


@dispatch
def registerTag(tag: string) -> TagId:
    return registerTag(globalTags, tag)


with const:
    ErrT = TagId(ord(TagEnum.ErrTagId))  ## the `(err …)` tag id (classic nifstreams.ErrT)


def typebits(n: NifToken) -> nint:
    """{.inline.}"""
    ## Bit width stored in an int-literal type token (classic nifstreams had this).
    ## nifcore keeps small ints inline, so the value is the signed operand.
    return nint(soperand(n)) if kind(n) == NifKind.IntLit else 0

# ── Line info: nifcore's NifLineInfo, read and written directly ──────────


@dispatch
def info(c: Cursor) -> NifLineInfo:
    """{.inline.}"""
    return c.rawLineInfo()


def endInfo(c: Cursor) -> NifLineInfo:
    """{.inline.}"""
    return c.rawLineInfo()


def _emitInfo(dest: mut @ TokenBuf, info: NifLineInfo):
    """{.nifEmits: "None".}"""
    if info.isValid():
        dest.appendLineInfo(info)


@dispatch
def addStrLit(dest: mut @ TokenBuf, s: StrId, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    nifcore.addStrLit(dest, pool.strings[s])
    _emitInfo(dest, info)


@dispatch
def addStrLit(dest: mut @ TokenBuf, s: string, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    nifcore.addStrLit(dest, s)
    _emitInfo(dest, info)

# ── End-of-scope / node predicates ───────────────────────────────────────
#
# nifcore has no ParLe/ParRi kind: a node is a `TagLit`, and a scope's end is
# `rem == 0` (`hasMore` false). `nifcore.kind` ASSERTS at rem == 0, so the sem
# port replaces the classic sentinels with these safe predicates:
#   `n.kind == ParLe`  → `n.isTagLit`      (also false at scope end / on atoms)
#   `n.kind != ParLe`  → `not n.isTagLit`
#   `n.kind == ParRi`  → `not n.hasMore`
#   `n.kind != ParRi`  → `n.hasMore`
# Inside a scope, `n.kind` (nifcore's) is safe and callers compare to `TagLit`,
# `StrLit`, `DotToken`, … directly.


@dispatch
def isTagLit(c: Cursor) -> bool:
    """{.inline.}"""
    ## True when the cursor is inside its scope and sits on a tag (compound) node
    ## — the nifcore-safe replacement for the classic `n.kind == ParLe`.
    return c.hasMore() and kind(load(c)) == NifKind.TagLit


@dispatch
def isDotToken(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.DotToken


@dispatch
def isIdent(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.Ident


@dispatch
def isSymbol(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.Symbol


@dispatch
def isSymbolDef(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.SymbolDef


@dispatch
def isStringLit(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.StrLit


@dispatch
def isIntLit(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.IntLit


@dispatch
def isUIntLit(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.UIntLit


@dispatch
def isFloatLit(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.FloatLit


@dispatch
def isCharLit(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.CharLit
    ## Build-agnostic token predicates (also defined in nifcursors_classic): the
    ## sem port uses these instead of `n.kind == ParLe/DotToken/…` so one source
    ## compiles under both the classic and the `-d:useNifcore` (nifcore) builds.

# (OpenTagKind/StrLitKind aliases are gone: call sites say TagLit/StrLit.)

# ── Raw-token (NifToken) accessors for the CF-listing / raw index walks ───
# Best-effort for pool-ref tokens (nifcore may inline short strings/syms; the
# control-flow buffer uses pool refs). `InlineInt`/`int28Token`/`getInt28`
# re-encode the CF's 28-bit goto operand onto nifcore's `ExtendedSuffix` kind
# (the classic CF repurposed `UnknownToken`; nifcore has no such spare atom).
with const:
    InlineInt = NifKind.ExtendedSuffix


def int28Token(operand: int32, info: NifLineInfo) -> NifToken:
    """{.inline.}"""
    ## CF goto/jump carrier: a DotToken with a 28-bit signed inline payload.
    ## It must NOT be an `ExtendedSuffix`: cursor `tokenWidth` greedily counts
    ## consecutive suffix tokens, so an ExtendedSuffix goto would be glued to
    ## whatever token precedes it (or to the previous goto) and every cursor
    ## walk over the CF stream would misalign. A DotToken is always its own
    ## one-token value; a REAL DotToken has payload 0, so CF walkers treat a
    ## zero `getInt28` as the plain no-op dot.
    ## `soperand` sign-extends the payload's top bit on read.
    return NifToken(((cast[uint32](operand) & PayloadMask) << KindBits) |
                    uint32(NifKind.DotToken))


@dispatch
def getInt28(n: NifToken) -> int32:
    """{.inline.}"""
    return soperand(n)


@dispatch
def getInt28(c: Cursor) -> int32:
    """{.inline.}"""
    return soperand(load(c))

# NO token-level `symId` / `strId`. A bare `NifToken` cannot be decoded to a
# pool id: a name of at most `StrInlineMaxLen` bytes is stored INSIDE the token,
# and turning those packed bytes into an id requires a pool to intern them in.
# The old `SymId(uoperand(n) shr 1)` pair silently returned garbage for exactly
# that case while sitting in the same overload set as the correct `Cursor`
# versions, so `buf[i].strId` compiled and read plausibly. Use a Cursor
# (`readonlyCursorAt(buf, i).strId`), which handles both encodings.


@dispatch
def charLit(n: NifToken) -> char:
    """{.inline.}"""
    return char(nifcore.uoperand(n) & 0xFF)
    ## Safe on a raw token: `CharLit` has no inline/pool duality.


def tagId(n: NifToken) -> TagId:
    """{.inline.}"""
    return TagId((uint32(n) >> TagShift) & TagMask)


def skipUntilEnd(c: mut @ Cursor):
    ## Skip a bounded cursor's remaining children (stops at the virtual close).
    while c.hasMore(): skip(c)


def isLastSon(n: Cursor) -> bool:
    ## True if `n` is the last child in its bounded scope.
    with var:
        c = n.copy()
    skip(c)
    result = not c.hasMore()
    return result


def patchInt28Token(n: mut @ NifToken, operand: int32):
    """{.inline.}"""
    n <<= int28Token(operand, NoLineInfo)


def setSymId(dest: mut @ NifToken, sym: SymId):
    """{.inline.}"""
    ## Rewrite a Symbol/SymbolDef token's id in place (kind preserved). Goes
    ## through `internedSymToken` so a short name lands in the inline encoding the
    ## builders would have produced, rather than a pool ref only this path emits.
    dest <<= internedSymToken(pool, (NifKind.SymbolDef if kind(dest) == NifKind.SymbolDef else NifKind.Symbol), sym)

# `buildTree` with an explicit info argument (classic signature). nifcore's own
# `buildTree` takes no info; these thread it through `addParLe`.


@template
def buildTree(dest: mut @ TokenBuf, tag: TagId, info: NifLineInfo, body: untyped):
    addParLe(dest, tag, info)
    body
    addParRi(dest)


@template
def buildTree[T: enum](dest: mut @ TokenBuf, tag: T, info: NifLineInfo, body: untyped):
    addParLe(dest, cast[TagId](uint32(ord(tag))), info)
    body
    addParRi(dest)


@dispatch
def info(n: NifToken) -> NifLineInfo:
    """{.inline.}"""
    return NoLineInfo
    ## Classic tokens carried their line info inline; a bare 4-byte nifcore token
    ## cannot. Reading it back yields `NoLineInfo` — matching the constructors
    ## above, which drop the passed info for the same reason. Callers that need
    ## real positions must use the buffer-level `add*` builders or cursors.


def widenSealed(dest: mut @ TokenBuf, enclosing: nint, growth: nint):
    ## After an insert/replace grew a *sealed* scope's contents, widen its jump.
    ## Handles only the in-field (non-overflow) case; asserts otherwise.
    if growth <= 0: return
    with var:
        tok = dest[enclosing].copy()
    with let:
        cur = uint32(tok) >> JumpShift
    setJump(tok, cur + uint32(growth))
    dest[enclosing] = tok


def widenEnclosingSealed(dest: mut @ TokenBuf, pos: nint, growth: nint):
    ## Widen the jump of EVERY sealed scope enclosing `pos` after inserting
    ## `growth` tokens there (classic-name mirror; see nifcursors_classic).
    if growth <= 0: return
    with var:
        i = 0
    while i < pos:
        with let:
            c = dest.readonlyCursorAt(i)
        if kind(c) == NifKind.TagLit:
            with let:
                total = subtreeWidth(c)  # head + suffix + body
            if i + total > pos:          # this scope encloses the insertion point
                widenSealed(dest, i, growth)
                i += c.tokenWidth()         # descend into the body
            else:
                i += total                 # sealed subtree entirely before `pos`
        else:
            i += 1


def cursorToPosition(base: Cursor, c: Cursor) -> nint:
    """{.inline.}"""
    ## Token distance of `c` from `base` (classic took two cursors; nifcore's
    ## same-named proc takes a TokenBuf, hence this overload).
    return (c.toUniqueId() - base.toUniqueId()) // sizeof(NifToken)


@dispatch
def isTagLit(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.TagLit


@dispatch
def isDotToken(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.DotToken


@dispatch
def isIdent(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.Ident


@dispatch
def isSymbol(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.Symbol


@dispatch
def isSymbolDef(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.SymbolDef


@dispatch
def isStringLit(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.StrLit


@dispatch
def isIntLit(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.IntLit


@dispatch
def isUIntLit(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.UIntLit


@dispatch
def isFloatLit(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.FloatLit


@dispatch
def isCharLit(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.CharLit

# ── Structural navigation ────────────────────────────────────────────────

# ── TokenBuf building: openTag/closeTag bridge with line info ─────────────


def addParLe(dest: mut @ TokenBuf, tag: TagId, info=NoLineInfo):
    """{.nifOpens.}"""
    dest.openTag(tag)
    _emitInfo(dest, info)


@dispatch
def addParRi(dest: mut @ TokenBuf):
    """{.nifCloses.}"""
    dest.closeTag()


@dispatch
def addParRi(dest: mut @ TokenBuf, info: NifLineInfo):
    """{.nifCloses.}"""
    dest.closeTag()


@dispatch
def isUnknownToken(c: Cursor) -> bool:
    """{.inline.}"""
    return c.hasMore() and kind(load(c)) == NifKind.UnknownToken


@dispatch
def isUnknownToken(n: NifToken) -> bool:
    """{.inline.}"""
    return kind(n) == NifKind.UnknownToken


def addUnstructured(dest: mut @ TokenBuf, c: Cursor):
    """{.nifEmits: "Any".}"""
    ## Copy the remaining forest under `c` verbatim, preserving each subtree's
    ## suffixes (line info). Handles a sequence of top-level trees/atoms.
    with var:
        c = c.copy()
    while c.hasMore():
        addSubtree(dest, c)
        skip(c)


def insert(dest: mut @ TokenBuf, src: Cursor, pos: nint):
    ## Insert the single subtree at `src` into `dest` at token position `pos`.
    with var:
        tmp = createTokenBuf(subtreeWidth(src) + 2)
    addSubtree(tmp, src)
    dest.insert(tmp, pos)
    ## nifcore has no close-token info; the arg is accepted for compatibility.

# ── Atom builders carrying line info (classic `dest.add xToken(v, info)`) ──
# nifcore builds an atom then attaches its line info as a trailing suffix, so
# these are add-then-`emitInfo`, not a single info-bearing token.


@dispatch
def addSymUse(dest: mut @ TokenBuf, s: SymId, info: NifLineInfo):
    """{.nifEmits: "Y".}"""
    nifcore.addSymUse(dest, s)
    _emitInfo(dest, info)


@dispatch
def addSymDef(dest: mut @ TokenBuf, s: SymId, info: NifLineInfo):
    """{.nifEmits: "D".}"""
    nifcore.addSymDef(dest, s)
    _emitInfo(dest, info)


def addDotToken(dest: mut @ TokenBuf, info: NifLineInfo):
    """{.nifEmits: "Dot".}"""
    dest.addDotToken()
    _emitInfo(dest, info)


@dispatch
def addIdent(dest: mut @ TokenBuf, s: StrId, info: NifLineInfo):
    """{.nifEmits: "Y".}"""
    nifcore.addIdent(dest, pool.strings[s])
    _emitInfo(dest, info)


@dispatch
def addIdent(dest: mut @ TokenBuf, s: string, info=NoLineInfo):
    """{.nifEmits: "Y".}"""
    nifcore.addIdent(dest, s)
    _emitInfo(dest, info)


def addIntLit(dest: mut @ TokenBuf, v: int64, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    dest.addIntLit(v)
    _emitInfo(dest, info)


def addUIntLit(dest: mut @ TokenBuf, v: uint64, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    dest.addUIntLit(v)
    _emitInfo(dest, info)


def addFloatLit(dest: mut @ TokenBuf, v: float64, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    dest.addFloatLit(v)
    _emitInfo(dest, info)


def addCharLit(dest: mut @ TokenBuf, v: char, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    dest.addCharLit(v)
    _emitInfo(dest, info)


def add(dest: mut @ TokenBuf, src: TokenBuf):
    """{.inline.}"""
    ## Append a whole buffer (classic `dest.add someTokenBuf`).
    dest.addBufferSamePool(src)


importFrom(".nifcoreparse")
importFrom(".nifreader")
importFrom(".vfs", "FileWriteMode", "AlwaysWrite", "OnlyIfChanged", "vfsRead", "vfsWrite")

# Custom pragmas don't cross module boundaries, so re-declare `canRaise` locally
# (mirrors compat2.nim).
if comptime(defined("nimony")):
    pragma("pragma: canRaise, raises")
else:
    pragma("pragma: canRaise")


@dispatch
def writeFile(b: mut @ TokenBuf, filename: string, mode: FileWriteMode = AlwaysWrite):
    """{.canRaise.}"""
    ## Serialize the buffer to a textual `.nif` module file (nifcore renderer).
    with let:
        content = nifcoreparse.toModuleString(b, string(".") + nifreader.extractModuleSuffix(filename))
    if mode == OnlyIfChanged:
        with let:
            try:
                existingContent = vfsRead(filename)
            except:
                existingContent = string("")
        if existingContent == content: return
    vfsWrite(filename, content)


def parseFromFile(filename: string, sizeHint=100) -> TokenBuf:
    ## Whole-file read (classic nifcursors.parseFromFile) via the nifcore reader.
    result = createTokenBuf(sizeHint)
    with var:
        r = nifreader.open(filename)
    _ = nifreader.processDirectives(r)
    # dense: classic code reads `n.info` on ANY token (import origins, error
    # positions); sparse change-stream info would come back NoLineInfo there
    nifcoreparse.parse(r, result, denseLineInfo=True)
    nifreader.close(r)
    return result


def parseFromBuffer(input: string, thisModule: sink @ string, sizeHint=100) -> TokenBuf:
    ## Parse NIF text into a buffer sharing the global pool/tags (shim invariant).
    return nifcoreparse.parseFromBuffer(input, thisModule, sizeHint,
                                        sharedPool=pool, sharedTags=globalTags,
                                        denseLineInfo=True)


@dispatch
def toString(c: Cursor, produceLineInfo=True) -> string:
    """{.inline.}"""
    ## Classic `toString(Cursor, produceLineInfo)`; nifcore's is keyword-arg
    ## based. The default matches classic nifcursors (`true`) — plugin inputs
    ## and written NIF files rely on it.
    return nifcoreparse.toString(c, includeLineInfo=produceLineInfo)


@dispatch
def toString(b: TokenBuf, produceLineInfo=True) -> string:
    """{.inline.}"""
    ## Read-only render (the nifcore renderer wants `var` for its cursor, but only
    ## reads); safe to alias an immutable buffer. Accepts both `var` and immutable.
    return nifcoreparse.toString(cast[ptr[TokenBuf]](unsafe_addr(b)).contents, includeLineInfo=produceLineInfo)


@template
def linearScan(n: mut @ Cursor, body: untyped):
    pragma("nifWrap")
    ## Pre-order visit of every tag (`TagLit`) node strictly inside `n`'s subtree,
    ## `n` positioned at each; `body` may `break` (leaving `n` at the match) and
    ## must not advance `n`. `inc` gives pre-order over the flat token stream
    ## (enters tags, steps atoms; suffixes are skipped by `tokenWidth`).
    if isTagLit(n):
        _ = enterScope(n)   # bound to the children; n now at the first child
        while n.hasMore():
            if isTagLit(n):
                body
            n.inc()


@template
def copyInto(dest: mut @ TokenBuf, tag: TagId, info: NifLineInfo, body: untyped):
    pragma("nifWrap")
    addParLe(dest, tag, info)
    body
    dest.closeTag()


@template
def copyIntoUnchecked(dest: mut @ TokenBuf, tag: string, info: NifLineInfo, body: untyped):
    pragma("nifWrap")
    addParLe(dest, registerTag(globalTags, tag), info)
    body
    dest.closeTag()

# ── Subtree / token moves ────────────────────────────────────────────────


def takeTree(dest: mut @ TokenBuf, n: mut @ Cursor):
    """{.nifBalanced.}"""
    addSubtree(dest, n)
    skip(n)

# ── Skip intents / structural helpers ────────────────────────────────────


class SkipIntent(NIntEnum):
    SkipTag = auto()        ## advance past a ParLe tag (entering a node to rewrite children)
    SkipParRi = auto()      ## advance past a closing paren
    SkipName = auto()       ## skip a name/SymbolDef child
    SkipExport = auto()     ## skip an export marker child
    SkipPragmas = auto()    ## skip a pragmas section
    SkipType = auto()       ## skip a type child
    SkipExpr = auto()       ## skip an expression child
    SkipStmt = auto()       ## skip a statement child
    SkipValue = auto()      ## skip a value/expression child
    SkipGenParams = auto()  ## skip generic parameters
    SkipCond = auto()       ## skip a condition expression
    SkipBody = auto()       ## skip a body/stmts section
    SkipEffects = auto()    ## skip an effects section
    SkipResult = auto()     ## skip a result that has been handled separately
    SkipFull = auto()       ## skip an entire subtree being dropped or replaced


@template
def skip(c: mut @ Cursor, intent: SkipIntent):
    """{.nifAdvance.}"""
    ## The intent is documentation only in the nifcore port (the classic runtime
    ## predicate depended on the ParLe/ParRi model). `skip` advances one subtree.
    skip(c)


@template
def inc(c: mut @ Cursor, intent: SkipIntent):
    """{.nifAdvance.}"""
    ## As `skip(c, intent)` but advances past the head only (`inc`).
    c.inc()


class TagClass(NIntEnum):
    Anything = auto()
    AnyExpr = auto()
    AnyStmt = auto()
    AnyType = auto()


@template
def skip(c: mut @ Cursor, expected: TagClass):
    """{.nifAdvance.}"""
    skip(c)
    ## Categorical skip intent — documentation only in the nifcore port.


@template
def inc(c: mut @ Cursor, expected: TagClass):
    """{.nifAdvance.}"""
    c.inc()


def consumeParRi(c: mut @ Cursor):
    """{.inline.}"""
    ## nifcore never materialises a close token — the scope end is implicit at
    ## `rem == 0`. There is nothing to advance past; this exists so classic
    ## `skipParRi` sites compile and stay no-ops.
    assert not c.hasMore(), "consumeParRi: cursor not at a (virtual) ParRi"


@dispatch
def uoperand(c: Cursor) -> uint32:
    """{.inline.}"""
    return nifcore.uoperand(load(c))


@dispatch
def soperand(c: Cursor) -> int32:
    """{.inline.}"""
    return nifcore.soperand(load(c))


if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir", "removeFile", "getLastModificationTime")
    from nimic.std import times

    def showInfo(title: string, i: NifLineInfo):
        if i.isValid():
            echo(title, " ", pool.filenames[i.file], ":", i.line, ":", i.col)
        else:
            echo(title, " none")

    def showPredicates(title: string, c: Cursor):
        """Every cursor predicate at `c` (also at a scope's end)."""
        echo(title, ": tag ", isTagLit(c), " dot ", isDotToken(c), " ident ", isIdent(c),
             " sym ", isSymbol(c), " symdef ", isSymbolDef(c), " str ", isStringLit(c),
             " int ", isIntLit(c), " uint ", isUIntLit(c), " float ", isFloatLit(c),
             " char ", isCharLit(c), " unknown ", isUnknownToken(c))

    def showTokenPredicates(title: string, n: NifToken):
        """Every raw-token predicate of `n`."""
        echo(title, ": ", kind(n), " tag ", isTagLit(n), " dot ", isDotToken(n),
             " ident ", isIdent(n), " sym ", isSymbol(n), " symdef ", isSymbolDef(n),
             " str ", isStringLit(n), " int ", isIntLit(n), " uint ", isUIntLit(n),
             " float ", isFloatLit(n), " char ", isCharLit(n), " unknown ",
             isUnknownToken(n))

    def showBuf(title: string, b: TokenBuf):
        echo(title, " (", len(b), " tokens):")
        echo(toString(b))
        echo(toString(b, False))

    def addedTests():
        # ── globalTags: the master tag pool, seeded in TagEnum order
        for e in array[5, TagEnum]([TagEnum.ErrTagId, TagEnum.SufTagId, TagEnum.AtTagId, TagEnum.DotTagId,
                                    high(TagEnum)]):
            echo("tag ", TagData[e][0], " ord ", ord(e), " id ",
                 uint32(registerTag(globalTags, TagData[e][0])), " name ",
                 globalTags.tagName(TagId(uint32(ord(e)))))
        echo("ErrT ", uint32(ErrT), " InlineInt ", InlineInt)
        with let:
            newTag = registerTag(string("nifpoolsTestTag"))
        echo("new tag ", uint32(newTag) == uint32(ord(high(TagEnum))) + 1, " again ",
             registerTag(string("nifpoolsTestTag")) == newTag, " name ", globalTags.tagName(newTag))

        # ── info-carrying builders, buildTree, copyInto, copyIntoUnchecked
        with let:
            f = getOrIncl(pool.filenames, string("a.nim"))
        with let:
            i1 = NifLineInfo(file=f, line=int32(3), col=int32(4))
        with let:
            i2 = NifLineInfo(file=f, line=int32(5), col=int32(1))
        with let:
            sym = symId(pool, string("foo"), 7, string("modx"))
        with let:
            sym2 = symId(pool, string("barbazquux"), 2, string("mody"))
        with var:
            b = createTokenBuf()
        echo("shares the global pools ", b.pool == pool, " ", b.tags == globalTags)
        with buildTree(b, TagEnum.StmtsTagId, i1):
            with buildTree(b, ErrT, i2):
                addIdent(b, string("x"))
                addIdent(b, string("y"), i1)
                addIdent(b, getOrIncl(pool.strings, string("zident")), i2)
                addStrLit(b, getOrIncl(pool.strings, string("pooled string")), i1)
                addStrLit(b, string("s"), i2)
                addStrLit(b, string("s none"), NoLineInfo)
                addIntLit(b, int64(-5), i1)
                b.addIntLit(int64(6))
                addUIntLit(b, u64(7), i2)
                addFloatLit(b, 2.5, i1)
                addCharLit(b, char('q'), i2)
                addSymUse(b, sym, i1)
                addSymDef(b, sym2, i2)
                addDotToken(b, i1)
                b.addDotToken()
            with copyInto(b, TagId(ord(TagEnum.CallTagId)), i2):
                addIdent(b, string("inner"), i1)
            with copyIntoUnchecked(b, string("customtag"), i1):
                addIntLit(b, int64(1), NoLineInfo)
            addParLe(b, TagId(ord(TagEnum.RetTagId)))
            addIntLit(b, int64(0), i1)
            addParRi(b, i2)
        showBuf(string("built"), b)
        with var:
            other = createTokenBuf()
        addIdent(other, string("appended"), i2)
        add(b, other)
        showBuf(string("with add"), b)

        # ── predicates, line info and raw-token accessors at every position
        with var:
            c = b.beginRead()
        showPredicates(string("root"), c)
        showInfo(string("info root"), info(c))
        showInfo(string("endInfo root"), endInfo(c))
        with into(c):
            with into(c):
                while c.hasMore():
                    showPredicates(string("  "), c)
                    showInfo(string("  info"), info(c))
                    skip(c)
                showPredicates(string("at the scope's end"), c)
                consumeParRi(c)
            skipUntilEnd(c)
            showPredicates(string("after skipUntilEnd"), c)
        endRead(c)
        for i in range(len(b)):
            showTokenPredicates(string("token ") + string(str(i)), b[i])
            showInfo(string("  raw info"), info(b[i]))
        echo("tagId of token 0 ", uint32(tagId(b[0])), " ", uint32(tagId(b[0])) == uint32(ord(TagEnum.StmtsTagId)))
        with var:
            d = b.beginRead()
        with into(d):
            with into(d):
                while d.hasMore():
                    if isIntLit(d):
                        echo("int: typebits ", typebits(load(d)), " getInt28 ", getInt28(d),
                             " soperand ", soperand(d), " uoperand ", uoperand(d))
                    elif isCharLit(d):
                        echo("char: ", charLit(load(d)), " uoperand ", uoperand(d))
                    else:
                        echo(kind(d), ": typebits ", typebits(load(d)), " uoperand ", uoperand(d))
                    skip(d)
            skipUntilEnd(d)
        endRead(d)

        # ── int28Token / getInt28 / patchInt28Token
        for v in array[8, int32]([int32(0), int32(1), int32(-1), int32(123456), int32(-123456),
                                  int32(134217727), int32(-134217728), int32(-2)]):
            with var:
                t = int28Token(v, i1)
            echo("int28 ", v, ": token ", uint32(t), " kind ", kind(t), " back ",
                 getInt28(t), " dot ", isDotToken(t))
            patchInt28Token(t, v // 2)
            echo("  patched ", getInt28(t))
        with var:
            cf = createTokenBuf()
        with buildTree(cf, ErrT, NoLineInfo):
            cf.add(int28Token(int32(-77), NoLineInfo))
            cf.add(int28Token(int32(0), NoLineInfo))
            addDotToken(cf, NoLineInfo)
        with var:
            g = cf.beginRead()
        with into(g):
            while g.hasMore():
                echo("cf getInt28 ", getInt28(g), " dot ", isDotToken(g))
                skip(g)
        endRead(g)

        # ── setSymId on raw tokens: the kind is kept
        with var:
            s = createTokenBuf()
        with buildTree(s, ErrT, NoLineInfo):
            addSymUse(s, sym, NoLineInfo)
            addSymDef(s, sym, NoLineInfo)
        showBuf(string("syms before"), s)
        for k in inrange(1, 2):
            with var:
                tok = s[k].copy()
            setSymId(tok, sym2)
            s[k] = tok
        showBuf(string("syms after setSymId"), s)

        # ── insert a subtree, then widen the enclosing sealed scopes
        with var:
            w = parseFromBuffer(string("(a (b 1) 2)"), string("w"))
        with var:
            src = parseFromBuffer(string("(new 9 8)"), string("w"))
        with let:
            growth = len(src)
        with var:
            sc = src.beginRead()
        insert(w, sc, 2)
        endRead(sc)
        widenEnclosingSealed(w, 2, growth)
        showBuf(string("inserted into b"), w)
        with var:
            w2 = parseFromBuffer(string("(a (b 1) 2)"), string("w"))
        with var:
            sc2 = src.beginRead()
        insert(w2, sc2, 3)
        endRead(sc2)
        widenEnclosingSealed(w2, 3, growth)
        widenEnclosingSealed(w2, 3, 0)
        showBuf(string("inserted after b"), w2)
        with var:
            w3 = parseFromBuffer(string("(a (b 1) 2)"), string("w"))
        w3.add(int28Token(int32(0), NoLineInfo))
        widenSealed(w3, 1, 0)
        echo("widenSealed by 0 keeps ", toString(w3, False))

        # ── cursorToPosition, isLastSon, linearScan, takeTree, addUnstructured, skip / inc with intents
        with var:
            t1 = parseFromBuffer(string("(r (p 1 (q 2)) (p 3) x (q (p 4)))"), string("t"))
        with var:
            base = t1.beginRead()
        with var:
            n = base.copy()
        n.inc()
        echo("after inc: position ", cursorToPosition(base, n), " last son ", isLastSon(n))
        skip(n, SkipIntent.SkipFull)
        echo("after skip SkipFull: position ", cursorToPosition(base, n), " last son ", isLastSon(n))
        skip(n, TagClass.AnyExpr)
        inc(n, SkipIntent.SkipName)
        echo("after skip AnyExpr, inc SkipName: position ", cursorToPosition(base, n), " last son ",
             isLastSon(n), " ", toString(n, False))
        inc(n, TagClass.Anything)
        echo("after inc Anything: position ", cursorToPosition(base, n), " ", toString(n, False))
        endRead(n)
        with var:
            scan = base.copy()
        for _ in linearScan(scan):
            echo("scan ", cursorToPosition(base, scan), " ", toString(scan, False))
        endRead(scan)
        with var:
            scan2 = base.copy()
        for _ in linearScan(scan2):
            if globalTags.tagName(cursorTagId(scan2)) == "q":
                break
        echo("scan stopped at ", cursorToPosition(base, scan2), " ", toString(scan2, False))
        endRead(scan2)
        with var:
            atom = parseFromBuffer(string("x"), string("t"))
        with var:
            ac = atom.beginRead()
        for _ in linearScan(ac):
            echo("scan of an atom runs its body")
        echo("scan of an atom: ", toString(ac, False))
        endRead(ac)
        with var:
            moved = createTokenBuf()
        with var:
            tk = base.copy()
        tk.inc()
        takeTree(moved, tk)
        takeTree(moved, tk)
        echo("takeTree twice: ", toString(moved, False), " | then at ", toString(tk, False))
        endRead(tk)
        with var:
            rest = createTokenBuf()
        with var:
            ru = base.copy()
        ru.inc()
        skip(ru)
        with buildTree(rest, ErrT, NoLineInfo):
            addUnstructured(rest, ru)
        echo("addUnstructured: ", toString(rest, False))
        endRead(ru)
        endRead(base)

        # ── parse / render: nifpools' overloads, nifcoreparse's when qualified
        with var:
            pb = parseFromBuffer(string("(stmts@1,2,f.nim (call@1,1 foo 1) (ret@3,4 x))"), string("pm"))
        echo("parseFromBuffer shares the global pool ", pb.pool == pool, " ", pb.tags == globalTags)
        with var:
            own = nifcoreparse.parseFromBuffer(string("(stmts 1)"), string("pm"))
        echo("nifcoreparse.parseFromBuffer shares it ", own.pool == pool)
        showBuf(string("parsed"), pb)
        with var:
            pc = pb.beginRead()
        echo("toString(c) ", toString(pc))
        echo("toString(c, false) ", toString(pc, False))
        echo("toString(c, produceLineInfo = false) ", toString(pc, produceLineInfo=False))
        echo("nifcoreparse.toString(c, includeLineInfo = false) ",
             nifcoreparse.toString(pc, includeLineInfo=False))
        endRead(pc)

        # ── writeFile in both modes, parseFromFile
        with let:
            path = getTempDir() + string("nifpools_test_module.nif")
        writeFile(pb, path)
        echo("written: ", vfsRead(path) == nifcoreparse.toModuleString(pb, string(".nifpools_test_module")))
        with var:
            pf = parseFromFile(path)
        echo("parseFromFile shares the global pool ", pf.pool == pool)
        showBuf(string("from the file"), pf)
        with let:
            before = getLastModificationTime(path)
        writeFile(pb, path, FileWriteMode.OnlyIfChanged)
        echo("OnlyIfChanged, unchanged: not rewritten ", getLastModificationTime(path) == before)
        vfsWrite(path, string("(changed)"))
        writeFile(pb, path, FileWriteMode.OnlyIfChanged)
        echo("OnlyIfChanged, changed: rewritten ", vfsRead(path) == nifcoreparse.toModuleString(pb, string(".nifpools_test_module")))
        vfsWrite(path, string("(other 1)"))
        writeFile(pb, path, FileWriteMode.AlwaysWrite)
        with var:
            pf2 = parseFromFile(path, 4)
        showBuf(string("from the file again"), pf2)
        removeFile(path)

    addedTests()
