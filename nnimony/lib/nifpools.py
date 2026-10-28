# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifpools.nim
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

from nimic.std.assertions import *
from .nifcore import *
from . import nifcore
from .comesfrom import *
from . import comesfrom
from .nifroles import *
from . import nifroles
with export:
    nifroles
# Template-expansion provenance rides in the line-info filename, so every
# consumer of a filename may need to strip it (`realFile`). Plain string
# handling with no NIF dependency of its own; re-exported here so it travels
# with the pool API rather than being imported separately everywhere.
with export:
    comesfrom
# Re-export nifcore verbatim except the two helpers whose shim versions below
# thread the global pool. `kind`/`NifKind`/its members are re-exported AS-IS:
# the sem port uses nifcore's own kind model directly (`TagLit`, `StrLit`,
# `hasMore` for end-of-scope) — there is no classic `NifKind` shim, because
# nimony's type-bound lookup makes `nifcore.kind(Cursor)` impossible to shadow.
exportExcept(nifcore, "createTokenBuf", "pool", "addIdent")
# nifcore re-exports bitabs and lineinfos.{FileId,NoFile,isValid} — all the
# lineinfos surface the frontend still needs. PackedLineInfo/LineInfoManager/
# pack/unpack stay out of scope here (nifstreams keeps them for the Nim side).
from ..models.tags import *   # TagEnum + TagData (the master tag namespace)

# ── Global pool / tags / line-info manager ───────────────────────────────


def _createMasterTagPool() -> TagPool:
    ## Seeded so each tag's `TagId` equals its master `TagEnum` ordinal
    ## (same pattern as nifcdecl.createLengTagPool).
    result = newTagPool()
    for e in inrange(low(TagEnum), high(TagEnum)):
        if e != TagEnum.InvalidTagId:
            with let:
                id = result.registerTag(TagData[e][0])
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
    return rawLineInfo(c)


def endInfo(c: Cursor) -> NifLineInfo:
    """{.inline.}"""
    return rawLineInfo(c)


def _emitInfo(dest: mut @ TokenBuf, info: NifLineInfo):
    """{.nifEmits: "None".}"""
    if info.isValid():
        appendLineInfo(dest, info)


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
    return hasMore(c) and kind(load(c)) == NifKind.TagLit


@dispatch
def isDotToken(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.DotToken


@dispatch
def isIdent(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.Ident


@dispatch
def isSymbol(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.Symbol


@dispatch
def isSymbolDef(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.SymbolDef


@dispatch
def isStringLit(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.StrLit


@dispatch
def isIntLit(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.IntLit


@dispatch
def isUIntLit(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.UIntLit


@dispatch
def isFloatLit(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.FloatLit


@dispatch
def isCharLit(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.CharLit
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
    while hasMore(c): skip(c)


def isLastSon(n: Cursor) -> bool:
    ## True if `n` is the last child in its bounded scope.
    with var:
        c = n.copy()
    skip(c)
    result = not hasMore(c)
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
            c = readonlyCursorAt(dest, i)
        if kind(c) == NifKind.TagLit:
            with let:
                total = subtreeWidth(c)  # head + suffix + body
            if i + total > pos:          # this scope encloses the insertion point
                widenSealed(dest, i, growth)
                i += tokenWidth(c)         # descend into the body
            else:
                i += total                 # sealed subtree entirely before `pos`
        else:
            i += 1


@dispatch
def cursorToPosition(base: Cursor, c: Cursor) -> nint:
    """{.inline.}"""
    ## Token distance of `c` from `base` (classic took two cursors; nifcore's
    ## same-named proc takes a TokenBuf, hence this overload).
    return (toUniqueId(c) - toUniqueId(base)) // sizeof(NifToken)


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
    openTag(dest, tag)
    _emitInfo(dest, info)


@dispatch
def addParRi(dest: mut @ TokenBuf):
    """{.nifCloses.}"""
    closeTag(dest)


@dispatch
def addParRi(dest: mut @ TokenBuf, info: NifLineInfo):
    """{.nifCloses.}"""
    closeTag(dest)


@dispatch
def isUnknownToken(c: Cursor) -> bool:
    """{.inline.}"""
    return hasMore(c) and kind(load(c)) == NifKind.UnknownToken


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
    while hasMore(c):
        dest.addSubtree(c)
        skip(c)


@dispatch
def insert(dest: mut @ TokenBuf, src: Cursor, pos: nint):
    ## Insert the single subtree at `src` into `dest` at token position `pos`.
    with var:
        tmp = createTokenBuf(subtreeWidth(src) + 2)
    tmp.addSubtree(src)
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


@dispatch
def addDotToken(dest: mut @ TokenBuf, info: NifLineInfo):
    """{.nifEmits: "Dot".}"""
    nifcore.addDotToken(dest)
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


@dispatch
def addIntLit(dest: mut @ TokenBuf, v: int64, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    nifcore.addIntLit(dest, v)
    _emitInfo(dest, info)


@dispatch
def addUIntLit(dest: mut @ TokenBuf, v: uint64, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    nifcore.addUIntLit(dest, v)
    _emitInfo(dest, info)


@dispatch
def addFloatLit(dest: mut @ TokenBuf, v: float64, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    nifcore.addFloatLit(dest, v)
    _emitInfo(dest, info)


@dispatch
def addCharLit(dest: mut @ TokenBuf, v: char, info: NifLineInfo):
    """{.nifEmits: "LIT".}"""
    nifcore.addCharLit(dest, v)
    _emitInfo(dest, info)


@dispatch
def add(dest: mut @ TokenBuf, src: TokenBuf):
    """{.inline.}"""
    ## Append a whole buffer (classic `dest.add someTokenBuf`).
    addBufferSamePool(dest, src)


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
        while hasMore(n):
            if isTagLit(n):
                body
            inc(n)


@template
def copyInto(dest: mut @ TokenBuf, tag: TagId, info: NifLineInfo, body: untyped):
    pragma("nifWrap")
    addParLe(dest, tag, info)
    body
    closeTag(dest)


@template
def copyIntoUnchecked(dest: mut @ TokenBuf, tag: string, info: NifLineInfo, body: untyped):
    pragma("nifWrap")
    addParLe(dest, globalTags.registerTag(tag), info)
    body
    closeTag(dest)

# ── Subtree / token moves ────────────────────────────────────────────────


def takeTree(dest: mut @ TokenBuf, n: mut @ Cursor):
    """{.nifBalanced.}"""
    dest.addSubtree(n)
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
    inc(c)


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
    inc(c)


def consumeParRi(c: mut @ Cursor):
    """{.inline.}"""
    ## nifcore never materialises a close token — the scope end is implicit at
    ## `rem == 0`. There is nothing to advance past; this exists so classic
    ## `skipParRi` sites compile and stay no-ops.
    assert not hasMore(c), string("consumeParRi: cursor not at a (virtual) ParRi")


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
    from nimic.std.times import *

    def _showInfo(title: string, i: NifLineInfo):
        if i.isValid():
            echo(title, string(" "), pool.filenames[i.file], string(":"), i.line, string(":"), i.col)
        else:
            echo(title, string(" none"))

    def _showPredicates(title: string, c: Cursor):
        """Every cursor predicate at `c` (also at a scope's end)."""
        echo(title, string(": tag "), isTagLit(c), string(" dot "), isDotToken(c), string(" ident "), isIdent(c),
             string(" sym "), isSymbol(c), string(" symdef "), isSymbolDef(c), string(" str "), isStringLit(c),
             string(" int "), isIntLit(c), string(" uint "), isUIntLit(c), string(" float "), isFloatLit(c),
             string(" char "), isCharLit(c), string(" unknown "), isUnknownToken(c))

    def _showTokenPredicates(title: string, n: NifToken):
        """Every raw-token predicate of `n`."""
        echo(title, string(": "), kind(n), string(" tag "), isTagLit(n), string(" dot "), isDotToken(n),
             string(" ident "), isIdent(n), string(" sym "), isSymbol(n), string(" symdef "), isSymbolDef(n),
             string(" str "), isStringLit(n), string(" int "), isIntLit(n), string(" uint "), isUIntLit(n),
             string(" float "), isFloatLit(n), string(" char "), isCharLit(n), string(" unknown "),
             isUnknownToken(n))

    def _showBuf(title: string, b: TokenBuf):
        echo(title, string(" ("), len(b), string(" tokens):"))
        echo(toString(b))
        echo(toString(b, False))

    def _addedTests():
        # ── globalTags: the master tag pool, seeded in TagEnum order
        for e in array[5, TagEnum]([TagEnum.ErrTagId, TagEnum.SufTagId, TagEnum.AtTagId, TagEnum.DotTagId,
                                    high(TagEnum)]):
            echo(string("tag "), TagData[e][0], string(" ord "), ord(e), string(" id "),
                 uint32(globalTags.registerTag(TagData[e][0])), string(" name "),
                 globalTags.tagName(TagId(uint32(ord(e)))))
        echo(string("ErrT "), uint32(ErrT), string(" InlineInt "), InlineInt)
        with let:
            newTag = registerTag(string("nifpoolsTestTag"))
        echo(string("new tag "), uint32(newTag) == uint32(ord(high(TagEnum))) + 1, string(" again "),
             registerTag(string("nifpoolsTestTag")) == newTag, string(" name "), globalTags.tagName(newTag))

        # ── info-carrying builders, buildTree, copyInto, copyIntoUnchecked
        with let:
            f = pool.filenames.getOrIncl(string("a.nim"))
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
        echo(string("shares the global pools "), b.pool == pool, string(" "), b.tags == globalTags)
        with buildTree(b, TagEnum.StmtsTagId, i1):
            with buildTree(b, ErrT, i2):
                addIdent(b, string("x"))
                addIdent(b, string("y"), i1)
                addIdent(b, pool.strings.getOrIncl(string("zident")), i2)
                addStrLit(b, pool.strings.getOrIncl(string("pooled string")), i1)
                addStrLit(b, string("s"), i2)
                addStrLit(b, string("s none"), NoLineInfo)
                addIntLit(b, int64(-5), i1)
                addIntLit(b, int64(6))
                addUIntLit(b, u64(7), i2)
                addFloatLit(b, 2.5, i1)
                addCharLit(b, ch('q'), i2)
                addSymUse(b, sym, i1)
                addSymDef(b, sym2, i2)
                addDotToken(b, i1)
                addDotToken(b)
            with copyInto(b, TagId(ord(TagEnum.CallTagId)), i2):
                addIdent(b, string("inner"), i1)
            with copyIntoUnchecked(b, string("customtag"), i1):
                addIntLit(b, int64(1), NoLineInfo)
            addParLe(b, TagId(ord(TagEnum.RetTagId)))
            addIntLit(b, int64(0), i1)
            addParRi(b, i2)
        _showBuf(string("built"), b)
        with var:
            other = createTokenBuf()
        addIdent(other, string("appended"), i2)
        b.add(other)
        _showBuf(string("with add"), b)

        # ── predicates, line info and raw-token accessors at every position
        with var:
            c = b.beginRead()
        _showPredicates(string("root"), c)
        _showInfo(string("info root"), info(c))
        _showInfo(string("endInfo root"), endInfo(c))
        with c.into():
            with c.into():
                while hasMore(c):
                    _showPredicates(string("  "), c)
                    _showInfo(string("  info"), info(c))
                    skip(c)
                _showPredicates(string("at the scope's end"), c)
                consumeParRi(c)
            skipUntilEnd(c)
            _showPredicates(string("after skipUntilEnd"), c)
        c.endRead()
        for i in range(len(b)):
            _showTokenPredicates(string("token ") + string(str(i)), b[i])
            _showInfo(string("  raw info"), info(b[i]))
        echo(string("tagId of token 0 "), uint32(tagId(b[0])), string(" "), uint32(tagId(b[0])) == uint32(ord(TagEnum.StmtsTagId)))
        with var:
            d = b.beginRead()
        with d.into():
            with d.into():
                while hasMore(d):
                    if isIntLit(d):
                        echo(string("int: typebits "), typebits(load(d)), string(" getInt28 "), getInt28(d),
                             string(" soperand "), soperand(d), string(" uoperand "), uoperand(d))
                    elif isCharLit(d):
                        echo(string("char: "), charLit(load(d)), string(" uoperand "), uoperand(d))
                    else:
                        echo(kind(d), string(": typebits "), typebits(load(d)), string(" uoperand "), uoperand(d))
                    skip(d)
            skipUntilEnd(d)
        d.endRead()

        # ── int28Token / getInt28 / patchInt28Token
        for v in array[8, int32]([int32(0), int32(1), int32(-1), int32(123456), int32(-123456),
                                  int32(134217727), int32(-134217728), int32(-2)]):
            with var:
                t = int28Token(v, i1)
            echo(string("int28 "), v, string(": token "), uint32(t), string(" kind "), kind(t), string(" back "),
                 getInt28(t), string(" dot "), isDotToken(t))
            patchInt28Token(t, v // 2)
            echo(string("  patched "), getInt28(t))
        with var:
            cf = createTokenBuf()
        with buildTree(cf, ErrT, NoLineInfo):
            cf.add(int28Token(int32(-77), NoLineInfo))
            cf.add(int28Token(int32(0), NoLineInfo))
            addDotToken(cf, NoLineInfo)
        with var:
            g = cf.beginRead()
        with g.into():
            while hasMore(g):
                echo(string("cf getInt28 "), getInt28(g), string(" dot "), isDotToken(g))
                skip(g)
        g.endRead()

        # ── setSymId on raw tokens: the kind is kept
        with var:
            s = createTokenBuf()
        with buildTree(s, ErrT, NoLineInfo):
            addSymUse(s, sym, NoLineInfo)
            addSymDef(s, sym, NoLineInfo)
        _showBuf(string("syms before"), s)
        for k in inrange(1, 2):
            with var:
                tok = s[k].copy()
            setSymId(tok, sym2)
            s[k] = tok
        _showBuf(string("syms after setSymId"), s)

        # ── insert a subtree, then widen the enclosing sealed scopes
        with var:
            w = parseFromBuffer(string("(a (b 1) 2)"), string("w"))
        with var:
            src = parseFromBuffer(string("(new 9 8)"), string("w"))
        with let:
            growth = len(src)
        with var:
            sc = src.beginRead()
        w.insert(sc, 2)
        sc.endRead()
        widenEnclosingSealed(w, 2, growth)
        _showBuf(string("inserted into b"), w)
        with var:
            w2 = parseFromBuffer(string("(a (b 1) 2)"), string("w"))
        with var:
            sc2 = src.beginRead()
        w2.insert(sc2, 3)
        sc2.endRead()
        widenEnclosingSealed(w2, 3, growth)
        widenEnclosingSealed(w2, 3, 0)
        _showBuf(string("inserted after b"), w2)
        with var:
            w3 = parseFromBuffer(string("(a (b 1) 2)"), string("w"))
        w3.add(int28Token(int32(0), NoLineInfo))
        widenSealed(w3, 1, 0)
        echo(string("widenSealed by 0 keeps "), toString(w3, False))

        # ── cursorToPosition, isLastSon, linearScan, takeTree, addUnstructured, skip / inc with intents
        with var:
            t1 = parseFromBuffer(string("(r (p 1 (q 2)) (p 3) x (q (p 4)))"), string("t"))
        with var:
            base = t1.beginRead()
        with var:
            n = base.copy()
        inc(n)
        echo(string("after inc: position "), cursorToPosition(base, n), string(" last son "), isLastSon(n))
        skip(n, SkipIntent.SkipFull)
        echo(string("after skip SkipFull: position "), cursorToPosition(base, n), string(" last son "), isLastSon(n))
        skip(n, TagClass.AnyExpr)
        inc(n, SkipIntent.SkipName)
        echo(string("after skip AnyExpr, inc SkipName: position "), cursorToPosition(base, n), string(" last son "),
             isLastSon(n), string(" "), toString(n, False))
        inc(n, TagClass.Anything)
        echo(string("after inc Anything: position "), cursorToPosition(base, n), string(" "), toString(n, False))
        n.endRead()
        with var:
            scan = base.copy()
        for _ in linearScan(scan):
            echo(string("scan "), cursorToPosition(base, scan), string(" "), toString(scan, False))
        scan.endRead()
        with var:
            scan2 = base.copy()
        for _ in linearScan(scan2):
            if tagName(globalTags, cursorTagId(scan2)) == string("q"):
                break
        echo(string("scan stopped at "), cursorToPosition(base, scan2), string(" "), toString(scan2, False))
        scan2.endRead()
        with var:
            atom = parseFromBuffer(string("x"), string("t"))
        with var:
            ac = atom.beginRead()
        for _ in linearScan(ac):
            echo(string("scan of an atom runs its body"))
        echo(string("scan of an atom: "), toString(ac, False))
        ac.endRead()
        with var:
            moved = createTokenBuf()
        with var:
            tk = base.copy()
        inc(tk)
        takeTree(moved, tk)
        takeTree(moved, tk)
        echo(string("takeTree twice: "), toString(moved, False), string(" | then at "), toString(tk, False))
        tk.endRead()
        with var:
            rest = createTokenBuf()
        with var:
            ru = base.copy()
        inc(ru)
        skip(ru)
        with buildTree(rest, ErrT, NoLineInfo):
            addUnstructured(rest, ru)
        echo(string("addUnstructured: "), toString(rest, False))
        ru.endRead()
        base.endRead()

        # ── parse / render: nifpools' overloads, nifcoreparse's when qualified
        with var:
            pb = parseFromBuffer(string("(stmts@1,2,f.nim (call@1,1 foo 1) (ret@3,4 x))"), string("pm"))
        echo(string("parseFromBuffer shares the global pool "), pb.pool == pool, string(" "), pb.tags == globalTags)
        with var:
            own = nifcoreparse.parseFromBuffer(string("(stmts 1)"), string("pm"))
        echo(string("nifcoreparse.parseFromBuffer shares it "), own.pool == pool)
        _showBuf(string("parsed"), pb)
        with var:
            pc = pb.beginRead()
        echo(string("toString(c) "), toString(pc))
        echo(string("toString(c, false) "), toString(pc, False))
        echo(string("toString(c, produceLineInfo = false) "), toString(pc, produceLineInfo=False))
        echo(string("nifcoreparse.toString(c, includeLineInfo = false) "),
             nifcoreparse.toString(pc, includeLineInfo=False))
        pc.endRead()

        # ── writeFile in both modes, parseFromFile
        with let:
            path = getTempDir() + string("nifpools_test_module.nif")
        writeFile(pb, path)
        echo(string("written: "), vfsRead(path) == nifcoreparse.toModuleString(pb, string(".nifpools_test_module")))
        with var:
            pf = parseFromFile(path)
        echo(string("parseFromFile shares the global pool "), pf.pool == pool)
        _showBuf(string("from the file"), pf)
        with let:
            before = getLastModificationTime(path)
        pb.writeFile(path, FileWriteMode.OnlyIfChanged)
        echo(string("OnlyIfChanged, unchanged: not rewritten "), getLastModificationTime(path) == before)
        vfsWrite(path, string("(changed)"))
        pb.writeFile(path, FileWriteMode.OnlyIfChanged)
        echo(string("OnlyIfChanged, changed: rewritten "), vfsRead(path) == nifcoreparse.toModuleString(pb, string(".nifpools_test_module")))
        vfsWrite(path, string("(other 1)"))
        pb.writeFile(path, FileWriteMode.AlwaysWrite)
        with var:
            pf2 = parseFromFile(path, 4)
        _showBuf(string("from the file again"), pf2)
        removeFile(path)

    _addedTests()
