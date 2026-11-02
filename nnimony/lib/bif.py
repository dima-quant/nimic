# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/bif.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## bif — **B**inary N**IF**: direct binary load/store of a `nifcore.TokenBuf`.
##
## NIF on disk is a *textual* s-expression format: great for tooling, diffing and
## bootstrapping, but for a compiler **cache** the text is pure overhead. Loading
## a text NIF means a full tokenizer/parser pass, and the text is several times
## larger than the in-memory token stream — e.g. a Nimbus module measured at
## 890 MiB of text collapses to a 176 MiB `TokenBuf` (0.20×), of which 99.5 % is
## the flat `uint32` token array and < 1 MiB is the (already deduped) string
## pools. `bif` writes exactly that in-memory representation to disk and reads it
## straight back, so a cache load is one `readBuffer` of the token block plus a
## quick re-intern of the small pools — no parsing.
##
## Layout. A `.bif` file is stored **little-endian**: the token block and the
## `indexOffset` are raw host-endian dumps and BIF is *defined* to be
## little-endian (every supported target is), so the `Magic` carries a fixed
## endianness byte (`0` = little) plus a version, and a mismatched/foreign file is
## rejected rather than misread. The host word size does NOT appear — a token is
## always `uint32`. Every integer is a SQLite-style `varint`
## (`std/varints`) — most counts and lengths are small, so the header and the
## per-string/-entry length prefixes shrink to a byte or two. The SOLE exception
## is `indexOffset`, which is a **fixed 8-byte** little integer: it is written as
## a placeholder and patched in place once the tail offset is known, so it must
## keep a constant width (a varint would change size when patched):
##
## ```
##   Magic            8 bytes  ("NIFBIN" + endianness byte (0=little) + Version)
##   indexOffset      u64      -- FIXED 8 bytes; BYTE offset of the index (patched)
##   tokenCount       varint
##   nTags            varint
##   nStrings         varint
##   nSyms            varint
##   nFiles           varint
##   pad              0..3 zero bytes  -- align the token block to NifToken (4 B)
##   tokens           tokenCount * sizeof(NifToken)   -- one raw block
##   tags             nTags    * (varint len + bytes)
##   strings          nStrings * (varint len + bytes)
##   syms             nSyms    * (varint len + bytes)
##   filenames        nFiles   * (varint len + bytes)
##   index (@indexOffset)
##     nIndex         varint
##     entries        nIndex   * (varint symId, varint tokenPos, varint vis)
## ```
##
## The `index` is the binary analogue of a text NIF's embedded `(.index …)`:
## global `SymbolDef` -> declaration token position + visibility, so a loaded
## buffer can locate one symbol without scanning. It is ALWAYS present (a cache
## with no index would force a full rescan to find any declaration) and lives at
## the **end** of the file, exactly like the text format's trailing index. The
## single `indexOffset` header field is the binary `(.indexat …)`: the fixed
## 8-byte slot a reader follows to jump straight to the index. Because the offset
## is only known once the token block and pools have been written, `storeToFile`
## writes a placeholder, streams everything, then patches the slot — mirroring the
## text writer's `addHeader27` reservation + `patchIndexAt`. It stays a constant
## width precisely so that in-place patch keeps working. The index entries
## themselves are gathered in the single forward token traversal `buildIndex`,
## the way the text writer accumulates `(.index …)` entries while emitting tokens.
##
## The token block is stored verbatim. Every pool-referencing token embeds a
## *pool id* — `StrLit`/`Symbol`/`SymbolDef`/`Ident` (strings/syms id),
## `LineInfoLit` (a `FileId`) and `TagLit` (a 9-bit tag id) — and `nifcore`
## assigns those ids 1, 2, … in intern order. The pools are written in that same
## id order and re-interned in order on load, reproducing identical ids, so the
## raw token words stay valid **without any patching**.
##
## INVARIANT (important): that zero-patch property holds *only* because `load`
## interns into **empty, freshly minted** pools, so the first `getOrIncl` returns
## id 1 again. `load` therefore never loads into a shared/pre-populated pool:
## doing so would assign different ids to the same strings while the token words
## still carry the old ids — silent corruption.
##
## A consumer that must share ONE pool across modules — the compiler frontend
## uses `SymId` *equality* as symbol identity, so every buffer of one
## compilation has to speak the same pool — uses `loadInto` instead: it takes
## the caller's pools, maps the file's ids onto them (one `getOrIncl` per pool
## ENTRY, not per token) and translates the token stream through those maps. See
## "loading into caller-supplied pools" below. `nifcore.addSubtree` also
## re-interns properly, but decodes and re-hashes every literal.


from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    pragma('feature: "lenientnils"')

from nimic.std.syncio import *
from nimic.std.assertions import *
from nimic.std.strutils import *
from nimic.std.varints import *
from .nifcore import (
    add, addCharLit, addDotToken, addFloatLit, addIdent, addIntLit, addOrdered, addStrLit, addSymDef, addSymUse,
    addUIntLit, adoptForeignTokens, appendLineInfo, beginRead, buildTree, charLit, closeTag, combinedPayload,
    createTokenBuf, Cursor, cursorAt, cursorIsNil, cursorTagId, cursorToPosition, endRead, FileId, floatVal, getOrIncl,
    growRawUninit, hasMore, IdPayloadMax, inc, into, intVal, isInlineLit, isValid, kind, KindBits, len, LiFileMaxC,
    lineInfoFile, load, newPool, newTagPool, NifKind, NifLineInfo, NifToken, NoNifLineInfo, openTag, peekInto, Pool,
    rawLineInfo, rawTokenPtr, registerTag, StrId, strVal, sub, sym, SymId, symId, symName, symRecord, syms, symString,
    TagId, TagMask, tagName, TagPool, TokenBuf, toUniqueId, uintVal)
from .vfs import vfsOpenMmap, vfsWrite
from . import nifcore

include("compat2")   # `onRaiseQuit`: run a raising call and `quit` on failure; identity under Nim

# Bulk string data access. Under Nimony these come from `system`; a `string`'s
# payload cannot be reached with a bare `addr s[0]` (it may be inline-stored), so
# reads go through `readRawData` and bulk writes through `beginStore`/`endStore`.
# Host Nim has no such API, so shim it (guarded, matching `stringviews.nim`).
if comptime(not defined("nimony")):
    if comptime(not declared("readRawData")):
        def readRawData(s: string) -> ptr[UncheckedArray[char]]:
            """{.inline.}"""
            if s.len == 0: return None
            else: return cast[ptr[UncheckedArray[char]]](addr(s[0]))
    if comptime(not declared("beginStore")):
        def beginStore(s: mut @ string, newLen: nint, start: nint = 0) -> ptr[UncheckedArray[char]]:
            """{.inline.}"""
            s.setLen(newLen)
            if s.len == 0: return None
            else: return cast[ptr[UncheckedArray[char]]](addr(s[start]))
    if comptime(not declared("endStore")):
        def endStore(s: mut @ string):
            """{.inline.}"""
            return

with const:
    UnusedNameTag = string("unusedname")
    ## Text NIF carries reader *directives* outside the token stream; bif has no
    ## directive channel. The one directive the pipeline must preserve — the
    ## plugin protocol's `(.unusedname X)` gensym hint — is represented as a
    ## leading `(unusedname X)` tree in the stored buffer instead. Binary
    ## readers peel it off (`plugins.loadPluginTree`); `niftools nif2bif` lifts
    ## the directive into this tree when converting.
    DependencyTag = string("dependency")
    ## The plugin protocol's other sidecar tree, `(dependency STR+)`: the files
    ## the plugin read (`plugins.dependsOn`). Named here for the same reason as
    ## `UnusedNameTag`: a bif buffer carries its own tag table, so both sides
    ## look the tree up by name.
    _Version = u8(5)
    _MagicLen = 8
    _LittleEndianTag = u8(0)
    ## Endianness marker in the `Magic`. BIF stores the token block and the
    ## `indexOffset` as raw host-endian bytes and is *defined* to be
    ## little-endian (every supported target is), so this byte is fixed at 0 =
    ## little. It replaces a former `sizeof(int)` byte that guarded nothing: a
    ## token is always `uint32`, so the host word size never affects the layout.

# ── embedded index ──────────────────────────────────────────────────────────
# A text NIF carries a trailing `(.index …)` mapping every *global* `SymbolDef`
# to the BYTE offset of its declaration, so a reader can seek straight to one
# symbol without scanning. Byte offsets are meaningless in the binary token
# world, so `bif` persists its OWN index: each global symbol's SymId, the TOKEN
# POSITION of its declaration's enclosing tag, and its visibility. This is what
# lets a `bif`-loaded buffer back an on-demand symbol loader (no full scan).


class IndexVis(NIntEnum):
    ivHidden = auto()    ## not importable as a bare identifier (the `.` marker)
    ivExported = auto()  ## importable (`x` marker)


class IndexEntry(Object):
    sym: SymId    ## the global symbol (resolve its name via `buf.pool.syms`)
    pos: int32    ## token index of the declaration's enclosing tag
    vis: IndexVis


class _DeclarationsT(NTuple):
    name: string
    visibility: IndexVis
    declaration: Cursor


class BifModule(Object):
    ## A loaded `.bif`: the token buffer plus its symbol index.
    buf: TokenBuf
    index: seq[IndexEntry]

    def findDeclaration(module: mut @ BifModule, name: string) -> Cursor:
        ## Returns the indexed declaration for ``name``, or a nil cursor when absent.
        result = default(Cursor)
        for entry in module.index:
            if symString(module.buf.pool, entry.sym) == name:
                return cursorAt(module.buf, entry.pos)
        return result

    def declarations(module: mut @ BifModule) -> _DeclarationsT:
        """{.sideEffect.}"""
        # `.sideEffect`: Nimony defaults iterators to `.noSideEffect`, but `cursorAt`
        # installs the buffer's cursor owner (a refcount write).
        ## Iterates all indexed global declarations in storage order.
        for entry in module.index:
            yield (symString(module.buf.pool, entry.sym), entry.vis,
                   cursorAt(module.buf, entry.pos))


def _isGlobalSymbol(s: string, dottedSuffix: string) -> bool:
    ## Mirror of `nifbuilder.addSymbolDefRetIsGlobal`: a symbol is "global" (gets
    ## an index entry) when its name — with a self-module `dottedSuffix` compressed
    ## to a single trailing dot — has >= 2 dots (`addSymbolImpl` counts dots from
    ## index 1).
    with var:
        lim = s.len
    if dottedSuffix.len > 0 and s.endsWith(dottedSuffix):
        lim = s.len - dottedSuffix.len + 1
    if lim > s.len: lim = s.len
    with var:
        dots = 0
    for i in range(1, lim):
        if s[i] == ch('.'): dots += 1
    return dots >= 2


def buildIndex(b: mut @ TokenBuf, dottedSuffix: string = string("")) -> seq[IndexEntry]:
    ## Scan `b` for global `SymbolDef`s and record, for each, its SymId, the token
    ## position of the most-recently-opened tag (the declaration's `(`, mirroring
    ## `nifcoreparse.toModuleString`'s `mostRecentOffset`), and its visibility
    ## (hidden when the marker after the def is a `DotToken`, else exported).
    result = seq[IndexEntry]([])
    if b.len == 0: return result
    with var:
        c = beginRead(b)
        mostRecentTagPos = i32(0)
    while hasMore(c):
        match kind(c):
            case NifKind.TagLit:
                mostRecentTagPos = int32(cursorToPosition(b, c))
                inc(c)                        # descend into the body (visit every token)
            case NifKind.SymbolDef:
                with let:
                    isG = _isGlobalSymbol(symName(c), dottedSuffix)
                    sid = symId(c)
                    tagPos = mostRecentTagPos
                inc(c)                        # advance to the marker / next sibling
                if isG:
                    with let:
                        vis = IndexVis.ivHidden if hasMore(c) and kind(c) == NifKind.DotToken else IndexVis.ivExported
                    result.add(IndexEntry(sym=sid, pos=tagPos, vis=vis))
            case _:
                inc(c)
    endRead(c)
    return result


def _magic() -> array[_MagicLen, char]:
    result = array[_MagicLen, char]([ch('N'), ch('I'), ch('F'), ch('B'), ch('I'), ch('N'), char(_LittleEndianTag), char(_Version)])
    return result

# A `.bif` file is a machine-local cache; a read/write/seek error is unrecoverable
# here. Under Nimony the syncio primitives are `{.raises.}`, so rather than thread
# `raises` through the whole module we funnel every raising call through these thin
# wrappers and `quit` on failure (via compat2's `onRaiseQuit`, an identity on host
# Nim). Everything above this line is pure; everything below only does I/O via
# these four wrappers, so no `.raises` call ever escapes.


def _readBytes(f: File, p: pointer, n: nint) -> nint: return onRaiseQuit(f.readBuffer(p, n))
def _getPos(f: File) -> int64: return onRaiseQuit(getFilePos(f))
def _setPos(f: File, pos: int64): onRaiseQuit(setFilePos(f, pos))


def _writeExact(f: File, p: pointer, n: nint):
    with let:
        written = onRaiseQuit(f.writeBuffer(p, n))
    assert written == n


def _readExact(f: File, p: pointer, n: nint):
    with let:
        got = _readBytes(f, p, n)
    assert got == n


def isBifFile(filename: string) -> bool:
    ## Cheap format probe: does `filename` start with the BIF magic name? Only the
    ## 6 name bytes are compared — NOT endianness/version — so that a
    ## wrong-version `.bif` is still routed to `load` and rejected with the
    ## precise "bad magic / incompatible" message instead of being fed to the
    ## text parser. Pipeline files keep their `.nif` names regardless of content;
    ## this probe is how a reader picks the decoder.
    result = False
    with var:
        f = default(File)
    if not open(f, filename, fmRead): return False
    with var:
        m = default(array[_MagicLen, char])
    if _readBytes(f, addr(m[0]), _MagicLen) == _MagicLen:
        result = True
        for i in range(_MagicLen - 2):   # compare "NIFBIN" only
            if m[i] != string("NIFBIN")[i]:
                result = False
                break
    close(f)
    return result

# `indexOffset` is the one fixed-width field: a placeholder that gets patched in
# place, so it must always occupy exactly 8 bytes (a varint would resize on patch).


def _readU64(f: File) -> uint64:
    result = u64(0)
    _readExact(f, addr(result), 8)
    return result

# Everything else is a varint. `varintLen` recovers a varint's total byte length
# from its first byte (mirrors `readVu64`'s `int(z[0]-246)` length check), so a
# file reader can pull the first byte, then the remaining `n-1`, then decode.


def _varintLen(b0: byte) -> nint:
    if b0 <= 240: return 1
    elif b0 <= 248: return 2
    else: return nint(b0) - 246


def _readVarint(f: File) -> uint64:
    with var:
        buf = default(array[maxVarIntLen, byte])
    _readExact(f, addr(buf[0]), 1)
    with let:
        n = _varintLen(buf[0])
    if n > 1:
        _readExact(f, addr(buf[1]), n - 1)
    result = u64(0)
    _ = readVu64(buf, result)
    return result


def _readCount(f: File, elemSize = 1) -> nint:
    ## A count or length from the file. A corrupt one must not wrap around when
    ## it is converted to `int` or multiplied by `elemSize`.
    with let:
        v = _readVarint(f)
    assert v <= uint64(high(nint) // elemSize), "bif: corrupt count"
    result = nint(v)
    return result


def _readStr(f: File) -> string:
    with let:
        n = _readCount(f)
    result = newString(n)
    if n > 0:
        _readExact(f, cast[pointer](beginStore(result, n)), n)
        endStore(result)
    return result


def _tokenPad(pos: nint) -> nint:
    ## Number of zero bytes to insert after the (variable-width varint) header so
    ## the token block begins `NifToken`-aligned. The mmap loader borrows that block
    ## in place and `adoptForeignTokens` asserts it is aligned; the fixed-header
    ## format got this for free, but a varint header can end on any byte. Writer and
    ## every reader compute this from the SAME post-header position, so they agree.
    with let:
        a = sizeof(NifToken)
    return (a - (pos & (a - 1))) & (a - 1)

# ── store ─────────────────────────────────────────────────────────────────
# The writer renders into a string: `storeToString` is the single source of
# truth for the byte layout, and the file writers dump its result in one
# `writeBuffer`. In-memory rendering exists because some callers need the
# bytes *before* a filename is known — the compiler checksums a plugin input
# to derive its content-addressed cache filename.


def _appendRaw(s: mut @ string, p: pointer, n: nint):
    if n > 0:
        with let:
            old = s.len
        copyMem(cast[pointer](beginStore(s, old + n, old)), p, n)
        # Writing at `old` is past the 7-byte inline prefix once the string is long,
        # so `endStore` would recopy a prefix that did not change.
        if old < 8:
            endStore(s)


def _appendU64(s: mut @ string, x: uint64):
    with var:
        v = x
    _appendRaw(s, addr(v), 8)


def _appendVarint(s: mut @ string, x: uint64):
    with var:
        buf = default(array[maxVarIntLen, byte])
    with let:
        n = writeVu64(buf, x)
    _appendRaw(s, addr(buf[0]), n)


def _appendStr(s: mut @ string, v: string):
    _appendVarint(s, uint64(v.len))
    if v.len > 0:
        _appendRaw(s, cast[pointer](readRawData(v)), v.len)


def storeToString(b: mut @ TokenBuf, dottedSuffix: string = string("")) -> string:
    ## Render `b` (token stream + pools + symbol index) in the exact `.bif`
    ## on-disk byte layout. The pools are written whole, in id order. If `b`
    ## shares a pool with other buffers, the *entire* shared pool is written
    ## (still correct — ids stay dense and load reproduces them — but larger
    ## than this module needs). For a compact, self-contained result — and for
    ## DETERMINISTIC bytes, which content-addressed callers require — build the
    ## buffer against its own private pool. `dottedSuffix` is the self-module
    ## suffix used to decide which symbols are global (it gets the same
    ## compression as the text writer).
    # The index is built in a single forward traversal of the token stream and is
    # always emitted — see the module doc.
    with let:
        index = buildIndex(b, dottedSuffix)
    result = string("")
    with var:
        m = _magic()
    _appendRaw(result, addr(m[0]), _MagicLen)
    # Reserve the `indexOffset` slot. We can only fill it once tokens and pools
    # are written, so append a placeholder now and patch it at the end — the
    # binary equivalent of `addHeader27`'s `(.indexat …)` reservation +
    # `patchIndexAt`. It is the one fixed-width (8-byte) field, so the in-place
    # patch overwrites exactly it.
    _appendU64(result, u64(0))
    _appendVarint(result, uint64(b.len))
    _appendVarint(result, uint64(len(b.tags.tags)))
    _appendVarint(result, uint64(len(b.pool.strings)))
    _appendVarint(result, uint64(syms(b.pool).len))
    _appendVarint(result, uint64(len(b.pool.filenames)))
    # Pad to NifToken alignment so the mmap loader can borrow the token block in
    # place (see `tokenPad`).
    for _ in inrange(1, _tokenPad(result.len)):
        result.add(ch('\0'))
    # token stream: one contiguous block.
    if b.len > 0:
        _appendRaw(result, rawTokenPtr(b), b.len * sizeof(NifToken))
    # pools, each in id order (ids are 1-based, dense up to len).
    for i in inrange(1, len(b.tags.tags)):      _appendStr(result, b.tags.tags[TagId(i)])
    for i in inrange(1, len(b.pool.strings)):   _appendStr(result, b.pool.strings[StrId(i)])
    for i in inrange(1, syms(b.pool).len):      _appendStr(result, symString(b.pool, SymId(i)))
    for i in inrange(1, len(b.pool.filenames)): _appendStr(result, b.pool.filenames[FileId(i)])
    # symbol index — self-contained at the offset we now know. `pos` is a token
    # index (always >= 0) and `vis` a 0/1 enum, so plain varints suffice.
    with let:
        indexOffset = result.len
    _appendVarint(result, uint64(index.len))
    for e in index:
        _appendVarint(result, uint64(e.sym))
        _appendVarint(result, uint64(e.pos))
        _appendVarint(result, uint64(ord(e.vis)))
    # Patch the fixed-width header slot to point at the index.
    with var:
        io = uint64(indexOffset)
    copyMem(cast[pointer](beginStore(result, result.len, _MagicLen)), addr(io), 8)
    endStore(result)
    return result


def storeToFile(b: mut @ TokenBuf, f: File, dottedSuffix: string = string("")):
    ## Write `b` (token stream + pools + symbol index) to an already-open binary
    ## file. See `storeToString` for the layout and the private-pool advice.
    with let:
        s = storeToString(b, dottedSuffix)
    _writeExact(f, cast[pointer](readRawData(s)), s.len)


def store(b: mut @ TokenBuf, filename: string, dottedSuffix: string = string("")):
    ## Write `b` to `filename` in binary `.bif` form (with its symbol index).
    vfsWrite(filename, storeToString(b, dottedSuffix))

# ── load ──────────────────────────────────────────────────────────────────


def _checkMagic(f: File):
    with var:
        m = default(array[_MagicLen, char])
    with let:
        want = _magic()
    _readExact(f, addr(m[0]), _MagicLen)
    for i in range(_MagicLen):
        if m[i] != want[i]:
            quit(string("bif: bad magic / incompatible format or word size"))


def _readIndex(f: File) -> seq[IndexEntry]:
    ## Read the self-contained index section (`nIndex` followed by the entries),
    ## assuming `f` is already positioned at its start.
    with let:
        nIndex = _readCount(f)
    result = newSeq[IndexEntry](nIndex)
    for i in range(nIndex):
        with let:
            sym = SymId(_readVarint(f))
            pos = int32(_readVarint(f))
            v = nint(_readVarint(f))
        result[i] = IndexEntry(sym=sym, pos=pos, vis=IndexVis(v))
    return result


def loadIndexFromFile(f: File) -> seq[IndexEntry]:
    ## Read ONLY the symbol index, by following the header's `indexOffset` and
    ## seeking straight to the trailing index section — the token block and pools
    ## are never touched. This is the binary analogue of `nifindexes` jumping to a
    ## text NIF's `(.indexat …)` target. NOTE: each entry's `sym` is a `SymId`
    ## that is only meaningful together with the buffer's `syms` pool, so a fully
    ## standalone consumer must also load that pool (or use the names another way).
    _checkMagic(f)
    with let:
        indexOffset = _readU64(f)
    _setPos(f, int64(indexOffset))
    result = _readIndex(f)
    return result


def loadIndex(filename: string) -> seq[IndexEntry]:
    ## Read just the symbol index of a `.bif` file (see `loadIndexFromFile`).
    with var:
        f = open(filename, fmRead)
    result = loadIndexFromFile(f)
    close(f)
    return result


def containsSym(filename: string, name: string) -> bool:
    ## Cheap membership probe: does the `.bif` at `filename` reference the symbol
    ## `name`? Reads ONLY the trailing symbol table — seeking past the (large) token
    ## block and the tags/strings tables to reach `syms`, which it scans comparing
    ## just the equal-length entries. No token block is mapped and no pool `BiTable`
    ## is built, so a module that never mentions `name` is rejected far more cheaply
    ## than a full `load`.
    ##
    ## NOTE: nothing calls this yet. It exists for a whole-project symbol query
    ## (`idetools.usages` is the candidate — it currently scans every file it is
    ## handed) and is covered by the self-test below, not by a consumer.
    ##
    ## A symbol is in `syms` iff it is stored by pool id — i.e. any name longer than
    ## `StrInlineMaxLen`, which a mangled `ident.disamb.suffix` always is; shorter
    ## inline-encoded names never reach the table, so only use this for such pooled
    ## names. A foreign or truncated file yields `false` ("skip it").
    result = False                        # every non-match path falls through to this
    with var:
        f = default(File)
    if not open(f, filename, fmRead): return False
    try:
        with var:
            m = default(array[_MagicLen, char])
        if _readBytes(f, addr(m[0]), _MagicLen) != _MagicLen or m != _magic(): return False
        _ = _readU64(f)                  # indexOffset (fixed 8 bytes)
        with let:
            tokenCount = _readCount(f, sizeof(NifToken))
            nTags      = _readCount(f)
            nStrings   = _readCount(f)
            nSyms      = _readCount(f)
        _ = _readVarint(f)               # nFiles
        # Skip the alignment pad, the token block and the tags/strings tables to reach `syms`.
        with let:
            pad = _tokenPad(nint(_getPos(f)))
        _setPos(f, _getPos(f) + int64(pad) + int64(tokenCount) * sizeof(NifToken))
        for _ in inrange(1, nTags + nStrings):
            with let:
                n = _readCount(f)              # read length first, THEN skip the bytes
            _setPos(f, _getPos(f) + n)
        # Scan the syms table; only entries of matching length can be `name`.
        for _ in inrange(1, nSyms):
            with let:
                n = _readCount(f)
            if n == name.len:
                with var:
                    s = newString(n)
                if n > 0:
                    if _readBytes(f, cast[pointer](beginStore(s, n)), n) != n: return False
                    endStore(s)
                if s == name: return True
            else:
                _setPos(f, _getPos(f) + n)
        result = False
    finally:
        close(f)
    return result


def loadFromFile(f: File) -> BifModule:
    ## Read a `BifModule` (token buffer + symbol index) from an already-open binary
    ## file. Always mints FRESH pools — see the INVARIANT in the module doc: the
    ## raw token words embed pool ids that are only reproduced by interning into
    ## empty pools from id 1, so loading into a shared/pre-populated pool is
    ## deliberately not supported. Quits on a magic/version mismatch.
    result = BifModule()
    _checkMagic(f)
    _ = _readU64(f)               # indexOffset — only `loadIndex*` follows it;
                                  # a full load reaches the index sequentially.
    with let:
        tokenCount = _readCount(f, sizeof(NifToken))
        nTags      = _readCount(f)
        nStrings   = _readCount(f)
        nSyms      = _readCount(f)
        nFiles     = _readCount(f)
    # Skip the alignment pad the writer inserted before the token block.
    with let:
        pad = _tokenPad(nint(_getPos(f)))
    if pad > 0: _setPos(f, _getPos(f) + int64(pad))

    result.buf = createTokenBuf(max(tokenCount, 16))   # fresh pools — see INVARIANT
    # token stream: read straight into the storage in one block.
    if tokenCount > 0:
        with let:
            dest = growRawUninit(result.buf, tokenCount)
            bytes = tokenCount * sizeof(NifToken)
        _readExact(f, dest, bytes)
    # pools: append in stored (id) order so ids 1,2,… match the token refs. No
    # hashing — `addOrdered` leaves the reverse index unbuilt, and `getOrIncl` (or
    # an explicit `ensureIndexed`, for `getKeyId`) builds it if one ever comes.
    for _ in inrange(1, nTags):    _ = addOrdered(result.buf.tags.tags, _readStr(f))
    for _ in inrange(1, nStrings): _ = addOrdered(result.buf.pool.strings, _readStr(f))
    for _ in inrange(1, nSyms):
        _ = addOrdered(result.buf.pool.symbols, symRecord(result.buf.pool, _readStr(f)))
    for _ in inrange(1, nFiles):   _ = addOrdered(result.buf.pool.filenames, _readStr(f))
    # symbol index (we are now positioned exactly at indexOffset).
    result.index = _readIndex(f)
    return result

# ── mmap-backed load (zero-copy token block) ────────────────────────────────
# `load` maps the whole `.bif` with `vfs.vfsOpenMmap` and BORROWS its token block
# straight into the returned `TokenBuf` via `adoptForeignTokens` — no multi-hundred
# -MB `readBuffer` into the heap. The pages are file-backed and read-only, so every
# process that maps the same cache file shares one physical copy (the whole point
# for the parallel IC backend, where dozens of workers reload `system.s.bif` & co).
# Only the small pools + index are copied out, so they don't pin the mapping. The
# mapping is intentionally never unmapped (see `adoptForeignTokens`): a `.bif` load
# feeds a short-lived backend process and is reclaimed wholesale at exit.


class _BifReader(Object):
    _base: uintp    # start of the mapped bytes
    _pos: nint      # cursor within [0, size)
    _size: nint

    def _rU64(r: mut @ _BifReader) -> uint64:
        assert r._pos + 8 <= r._size, "bif: truncated header"
        result = cast[ptr[uint64]](r._base + uint(r._pos)).contents
        r._pos += 8
        return result

    def _rVarint(r: mut @ _BifReader) -> uint64:
        assert r._pos + 1 <= r._size, "bif: truncated varint"
        with let:
            b0 = cast[ptr[byte]](r._base + uint(r._pos)).contents
            n = _varintLen(b0)
        assert r._pos + n <= r._size, "bif: truncated varint"
        with var:
            buf = default(array[maxVarIntLen, byte])
            i = 0
        while i < n:
            buf[i] = cast[ptr[byte]](r._base + uint(r._pos + i)).contents
            i += 1
        r._pos += n
        result = u64(0)
        _ = readVu64(buf, result)
        return result

    def _rCount(r: mut @ _BifReader, elemSize = 1) -> nint:
        ## A count or length from the file, checked against the bytes that are left:
        ## every element takes at least `elemSize` of them, so a larger count is a
        ## corrupt file — and checked by division, not by `pos + n * elemSize`,
        ## which a corrupt count would overflow.
        with let:
            v = r._rVarint()
        assert v <= uint64((r._size - r._pos) // elemSize), "bif: count exceeds file"
        result = nint(v)
        return result

    def _rStr(r: mut @ _BifReader) -> string:
        with let:
            n = r._rCount()
        # `newString(n)` zeros the payload that we immediately overwrite; GCC DSE's
        # that store, arkham emits both. `newStringOfCap` reserves without zeroing.
        result = newStringOfCap(n)
        if n > 0:
            copyMem(cast[pointer](beginStore(result, n)), cast[pointer](r._base + uint(r._pos)), n)
            endStore(result)
            r._pos += n
        return result


@dispatch
def load(filename: string) -> BifModule:
    ## Read a `BifModule` from a binary `.bif` file, memory-mapping it and BORROWING
    ## the token block (zero-copy — see `adoptForeignTokens`). Mints fresh pools (the
    ## bif INVARIANT). The mapping stays resident for the process lifetime.
    with let:
        blob = vfsOpenMmap(filename)          # left mapped for the buffer's lifetime
    with var:
        r = _BifReader(_base=cast[uintp](blob.data), _pos=0, _size=blob.size)
    with block:                               # magic
        with let:
            want = _magic()
        assert r._size >= _MagicLen, "bif: file too small"
        for i in range(_MagicLen):
            if cast[ptr[char]](r._base + uint(i)).contents != want[i]:
                quit(string("bif: bad magic / incompatible format or word size"))
    r._pos = _MagicLen
    _ = r._rU64()                    # indexOffset — a full load reaches it linearly
    with let:
        tokenCount = r._rCount(sizeof(NifToken))
        nTags      = r._rCount()
        nStrings   = r._rCount()
        nSyms      = r._rCount()
        nFiles     = r._rCount()
    # Skip the alignment pad so the borrowed token block is NifToken-aligned. The
    # mapping's base is page-aligned, so aligning `r.pos` aligns the absolute address.
    r._pos += _tokenPad(r._pos)
    # token block follows the varint header and is borrowed straight from the mapping.
    result = BifModule()
    assert r._pos <= r._size and tokenCount <= (r._size - r._pos) // sizeof(NifToken), \
        "bif: truncated token block"
    with let:
        tokenBytes = tokenCount * sizeof(NifToken)
    result.buf = adoptForeignTokens(cast[pointer](r._base + uint(r._pos)), tokenCount)
    r._pos += tokenBytes
    # pools: append in stored (id) order so ids 1,2,… match the token refs. No
    # hashing — `addOrdered` leaves the reverse index unbuilt, and `getOrIncl` (or
    # an explicit `ensureIndexed`, for `getKeyId`) builds it if one ever comes.
    for _ in inrange(1, nTags):    _ = addOrdered(result.buf.tags.tags, r._rStr())
    for _ in inrange(1, nStrings): _ = addOrdered(result.buf.pool.strings, r._rStr())
    for _ in inrange(1, nSyms):
        _ = addOrdered(result.buf.pool.symbols, symRecord(result.buf.pool, r._rStr()))
    for _ in inrange(1, nFiles):   _ = addOrdered(result.buf.pool.filenames, r._rStr())
    # symbol index (we are now positioned exactly at indexOffset).
    with let:
        nIndex = r._rCount()
    result.index = newSeq[IndexEntry](nIndex)
    for i in range(nIndex):
        with let:
            sym = SymId(r._rVarint())
            pos = int32(r._rVarint())
            v = nint(r._rVarint())
        result.index[i] = IndexEntry(sym=sym, pos=pos, vis=IndexVis(v))
    return result

# ── loading into caller-supplied pools ──────────────────────────────────────
# `load` mints fresh pools because the stored token words carry raw pool ids
# (see the INVARIANT). The compiler frontend cannot use that: it compares
# `SymId`s for symbol identity, so all its buffers must share one `Pool` (and
# one `TagPool`, since `kind` queries cast a `TagId` straight to a tag enum).
#
# `loadInto` bridges the two worlds. It maps the file's pools onto the caller's
# — one `getOrIncl` per stored pool ENTRY, i.e. per distinct string, not per
# token — and then rewrites the token stream through those maps.
#
# Rewriting cannot be an in-place patch of the id fields: a `LineInfoLit` packs
# the `FileId` in 7 bits and only widens to a 14-bit layout by growing a token,
# and the frontend's shared pool routinely holds more than 127 filenames. So the
# translation re-emits the stream through the builder API, which re-derives
# every tag `jump` for the (few) heads that changed width. It stays linear, does
# no hashing and no string decoding — ids come from the maps.


class PoolRemap(Object):
    ## File id → caller-pool id, indexed by the file id. Slot 0 is unused: every
    ## `BiTable` id is 1-based (`Id(0)` means "not used").
    tags: seq[TagId]
    strings: seq[StrId]
    syms: seq[SymId]
    files: seq[FileId]
    identity: bool
    ## True when every map is the identity — the caller's pools already agree
    ## with the file's ids (typically: loading the first module into empty
    ## pools), so the token stream needs no rewrite at all.

    def _mapStr(m: PoolRemap, id: StrId) -> StrId:
        with let:
            i = nint(uint32(id))
        if i <= 0 or i >= m.strings.len: quit(string("bif: string id ") + str(id) + string(" out of range"))
        return m.strings[i]

    def _mapSym(m: PoolRemap, id: SymId) -> SymId:
        with let:
            i = nint(uint32(id))
        if i <= 0 or i >= m.syms.len: quit(string("bif: symbol id ") + str(id) + string(" out of range"))
        return m.syms[i]

    def _mapFile(m: PoolRemap, id: FileId) -> FileId:
        with let:
            i = nint(uint32(id))
        if i <= 0 or i >= m.files.len: quit(string("bif: file id ") + str(i) + string(" out of range"))
        return m.files[i]

    def _mapTag(m: PoolRemap, id: TagId) -> TagId:
        with let:
            i = nint(uint32(id))
        if i <= 0 or i >= m.tags.len: quit(string("bif: tag id ") + str(id) + string(" out of range"))
        return m.tags[i]


def buildRemap(src: mut @ TokenBuf, pool: Pool, tags: TagPool) -> PoolRemap:
    ## Intern every entry of `src`'s pools into `pool` / `tags` and record the
    ## resulting ids. `src` is a freshly `load`ed buffer, so its ids are dense
    ## `1 .. len` and the maps are plain seqs.
    result = PoolRemap(tags=seq[TagId]([]), strings=seq[StrId]([]), syms=seq[SymId]([]), files=seq[FileId]([]),
                       identity=True)
    with let:
        nTags = len(src.tags.tags)
    result.tags = newSeq[TagId](nTags + 1)
    for i in inrange(1, nTags):
        with let:
            id = getOrIncl(tags.tags, src.tags.tags[TagId(i)])
        if uint32(id) > TagMask:
            quit(utf8("bif: tag pool overflow — '") + src.tags.tags[TagId(i)] +
                 string("' got id ") + str(id) + string(", but a TagLit holds only 9 bits"))
        result.tags[i] = id
        if uint32(id) != uint32(i): result.identity = False
    with let:
        nStrings = len(src.pool.strings)
    result.strings = newSeq[StrId](nStrings + 1)
    for i in inrange(1, nStrings):
        with let:
            id = getOrIncl(pool.strings, src.pool.strings[StrId(i)])
        result.strings[i] = id
        if uint32(id) != uint32(i): result.identity = False
    with let:
        nSyms = syms(src.pool).len
    result.syms = newSeq[SymId](nSyms + 1)
    for i in inrange(1, nSyms):
        with let:
            id = symId(pool, symString(src.pool, SymId(i)))
        result.syms[i] = id
        if uint32(id) != uint32(i): result.identity = False
    with let:
        nFiles = len(src.pool.filenames)
    result.files = newSeq[FileId](nFiles + 1)
    for i in inrange(1, nFiles):
        with let:
            id = getOrIncl(pool.filenames, src.pool.filenames[FileId(i)])
        result.files[i] = id
        if uint32(id) != uint32(i): result.identity = False
    return result


def _remapLineInfo(c: Cursor, m: PoolRemap) -> NifLineInfo:
    ## The head's trailing line info with its `FileId` (and `#comment#` `StrId`)
    ## moved to the caller's pool. `NoNifLineInfo` when the head carries none.
    with let:
        li = rawLineInfo(c)
    if not li.isValid(): return NoNifLineInfo
    with var:
        comment = StrId(0)
    if uint32(li.comment) != u32(0): comment = m._mapStr(li.comment)
    result = NifLineInfo(file=m._mapFile(li.file), line=li.line, col=li.col,
                         comment=comment)
    return result


def _poolRefToken(k: NifKind, id: uint32) -> NifToken:
    ## A `StrLit`/`Ident`/`Symbol`/`SymbolDef` token in pool-ref mode (bit 0 = 0).
    ## Ids past 2^27 would need an `ExtendedSuffix` chain; no compiler run comes
    ## anywhere near that, and emitting a wider carrier silently is worse than
    ## stopping, so this is a hard error rather than an `assert`.
    if id > IdPayloadMax:
        quit(string("bif: pool id ") + str(id) + string(" too large to remap (27-bit carrier)"))
    return NifToken(uint32(k) | ((id << 1) << KindBits))


class _Translator(Object):
    ## State threaded through the recursive re-emit: the id maps plus the
    ## bookkeeping that moves the symbol index's token positions along.
    _m: PoolRemap
    _entries: seq[IndexEntry]   ## source index, in non-decreasing `pos` order
    _newPos: seq[int32]         ## destination position per entry
    _k: nint                    ## entries resolved so far
    _srcBase: uintp             ## address of source token 0

    def _noteTagPos(t: mut @ _Translator, c: Cursor, destPos: nint):
        ## Called just before the `TagLit` at `c` is re-emitted at `destPos`. Index
        ## entries point at the enclosing tag of a declaration, `buildIndex` records
        ## them in forward order, and this walk visits every tag in that same order —
        ## so one shared cursor over `entries` suffices.
        if t._k >= t._entries.len: return
        with let:
            srcPos = int32((cast[uintp](toUniqueId(c)) - t._srcBase) //
                           uint(sizeof(NifToken)))
        while t._k < t._entries.len and t._entries[t._k].pos <= srcPos:
            t._newPos[t._k] = int32(destPos)
            t._k += 1


def _remapValue(dest: mut @ TokenBuf, c: mut @ Cursor, t: mut @ _Translator):
    ## Copy one value (atom or whole `TagLit` subtree) from `c` into `dest`,
    ## translating every pool reference. Shaped like `nifcore.addAcrossPools`, but
    ## where that one decodes each literal to a `string` and re-interns it, this
    ## one looks the new id up in the map.
    with let:
        destLi = _remapLineInfo(c, t._m)
    match kind(c):
        case NifKind.TagLit:
            with let:
                destPos = dest.len.copy()
            t._noteTagPos(c, destPos)
            openTag(dest, t._m._mapTag(cursorTagId(c)))
            appendLineInfo(dest, destLi)          # right after the tag head
            with into(c):
                while hasMore(c):
                    _remapValue(dest, c, t)
            with let:
                lenBefore = dest.len.copy()
            closeTag(dest)
            if dest.len != lenBefore:
                # The body outgrew the 19-bit jump field, so `closeTag` spliced an
                # `ExtendedSuffix` at `destPos + 1` and shifted everything behind it.
                # Recorded positions past the splice move with it.
                for i in range(t._k):
                    if t._newPos[i] > int32(destPos): t._newPos[i] = t._newPos[i] + i32(1)
        case NifKind.StrLit | NifKind.Ident | NifKind.Symbol | NifKind.SymbolDef:
            # An inline-stored short literal carries its bytes in the token itself —
            # no pool involved, so it copies verbatim (Cursor discipline: never read a
            # `strId`/`symId` off such a token).
            if isInlineLit(c):
                add(dest, load(c))
            elif kind(c) == NifKind.Symbol or kind(c) == NifKind.SymbolDef:
                add(dest, _poolRefToken(kind(c), uint32(t._m._mapSym(SymId(combinedPayload(c) >> 1)))))
            else:
                add(dest, _poolRefToken(kind(c), uint32(t._m._mapStr(StrId(combinedPayload(c) >> 1)))))
            appendLineInfo(dest, destLi)
            inc(c)
        case NifKind.IntLit:     addIntLit(dest, intVal(c));     appendLineInfo(dest, destLi); inc(c)
        case NifKind.UIntLit:    addUIntLit(dest, uintVal(c));   appendLineInfo(dest, destLi); c.inc()
        case NifKind.FloatLit:   addFloatLit(dest, floatVal(c)); appendLineInfo(dest, destLi); inc(c)
        case NifKind.CharLit:    addCharLit(dest, charLit(c));   appendLineInfo(dest, destLi); inc(c)
        case NifKind.DotToken:   addDotToken(dest);            appendLineInfo(dest, destLi); inc(c)
        case NifKind.LineInfoLit:
            dest.add(load(c)); c.inc()                    # defensive: not a valid head token
        case NifKind.ExtendedSuffix:
            quit(string("bif: ExtendedSuffix cannot be a head token"))
        case NifKind.UnknownToken | NifKind.EofToken | NifKind.ParLe | NifKind.ParRi:
            quit(string("bif: lexical token kind in a binary token stream"))


def _remapInto(raw: mut @ BifModule, pool: Pool, tags: TagPool,
               canBorrow: bool) -> BifModule:
    ## Translate a freshly loaded (fresh-pool) `BifModule` into `pool` / `tags`.
    ## `canBorrow` says whether `raw`'s token block may be handed on by reference
    ## — true only for the mmap loader, whose mapping outlives everything; a
    ## file-read block dies with `raw`.
    result = BifModule()
    with let:
        m = buildRemap(raw.buf, pool, tags)
        n = raw.buf.len
    if m.identity:
        # The caller's pools already assign exactly these ids, so the stored token
        # words are valid as they are (the usual case for the first module loaded
        # into empty pools).
        if canBorrow:
            result.buf = adoptForeignTokens(rawTokenPtr(raw.buf), n, pool, tags)
        else:
            result.buf = createTokenBuf(max(n, 16), pool, tags)
            if n > 0:
                copyMem(growRawUninit(result.buf, n), rawTokenPtr(raw.buf),
                        n * sizeof(NifToken))
        result.index = raw.index          # ids and positions both unchanged
        return result
    with var:
        t = _Translator(_m=m, _entries=raw.index,
                        _newPos=newSeq[int32](raw.index.len), _k=0,
                        _srcBase=cast[uintp](rawTokenPtr(raw.buf)))
    # Slack for the heads that widen (line infos moving to the 14-bit file layout).
    result.buf = createTokenBuf(max(n + (n >> 3), 16), pool, tags)
    if n > 0:
        with var:
            c = beginRead(raw.buf)
        while hasMore(c):
            _remapValue(result.buf, c, t)
        endRead(c)
    result.index = newSeq[IndexEntry](raw.index.len)
    for i in range(raw.index.len):
        result.index[i] = IndexEntry(sym=m._mapSym(raw.index[i].sym),
                                     pos=t._newPos[i], vis=raw.index[i].vis)
    return result


def loadInto(filename: string, pool: Pool, tags: TagPool) -> BifModule:
    ## Read a `.bif` and translate it into the CALLER's pools, so the result can
    ## share one `Pool`/`TagPool` with every other buffer of the run — which is
    ## what makes `SymId` equality a valid symbol-identity test across modules.
    ## The returned `index` is translated too (its `sym`s are caller-pool ids, its
    ## `pos`itions point into the returned buffer).
    ##
    ## Cost: one `getOrIncl` per stored pool entry plus one linear pass over the
    ## token stream — no parsing, no per-token hashing. When the ids happen to
    ## line up (empty target pools) even that pass is skipped and the mmap'd token
    ## block is borrowed, exactly as in `load`.
    with var:
        raw = load(filename)
    result = _remapInto(raw, pool, tags, canBorrow=True)
    return result


def loadFromFileInto(f: File, pool: Pool, tags: TagPool) -> BifModule:
    ## `loadInto` from an already-open file, without the memory mapping (the token
    ## block is always copied). See `loadInto` for the translation contract.
    with var:
        raw = loadFromFile(f)
    result = _remapInto(raw, pool, tags, canBorrow=False)
    return result

# ── self-test ───────────────────────────────────────────────────────────────

if comptime(__name__ == "__main__"):
    if comptime(defined("nimony")):
        # Nimony's `system` has `assert` but not `doAssert`; the self-test wants an
        # always-on check, so provide the two arities it uses.
        @template
        def _doAssert(cond: bool):
            if not cond: quit(string("bif self-test: assertion failed"))

        @template
        def _doAssert(cond: bool, msg: string):
            if not cond: quit(string("bif self-test: ") + msg)

    def _sameTokens(a: TokenBuf, b: TokenBuf) -> bool:
        if a.len != b.len: return False
        for i in range(a.len):
            if not (a[i] == b[i]): return False
        return True

    # Structural (not bitwise) comparison: `loadInto` re-emits the stream, so a
    # remapped buffer is only required to *mean* the same thing — token widths
    # legitimately differ when a line info moves to the wide file layout.
    def _sameValue(a: Cursor, b: Cursor) -> bool:
        if kind(a) != kind(b): return False
        with let:
            la = rawLineInfo(a)
            lb = rawLineInfo(b)
        if la.line != lb.line or la.col != lb.col: return False
        if lineInfoFile(a) != lineInfoFile(b): return False
        match kind(a):
            case NifKind.TagLit:                       return nifcore.tags(a).tags[cursorTagId(a)] == nifcore.tags(b).tags[cursorTagId(b)]
            case NifKind.StrLit | NifKind.Ident:       return strVal(a) == strVal(b)
            case NifKind.Symbol | NifKind.SymbolDef:   return symName(a) == symName(b)
            case NifKind.IntLit:                       return intVal(a) == intVal(b)
            case NifKind.UIntLit:                      return uintVal(a) == uintVal(b)
            case NifKind.FloatLit:                     return floatVal(a) == floatVal(b)
            case NifKind.CharLit:                      return charLit(a) == charLit(b)
            case NifKind.DotToken:                     return True
            case _:                                    return False

    def _sameTree(a: mut @ Cursor, b: mut @ Cursor) -> bool:
        result = True
        while hasMore(a) and hasMore(b):
            if not _sameValue(a, b): return False
            if kind(a) == NifKind.TagLit:
                with var:
                    ok = True
                with peekInto(a):
                    with peekInto(b):
                        ok = _sameTree(a, b)
                if not ok: return False
            else:
                inc(a)
                inc(b)
        result = hasMore(a) == hasMore(b)
        return result

    with block("round_trip"):
        # Build a buffer exercising every pool + inline/overflow paths, then
        # store → load and require token-identical + pool-identical results.
        with var:
            src = createTokenBuf(16)
        with let:
            tFoo = registerTag(src.tags, string("foo"))
            tBar = registerTag(src.tags, string("bar"))
            f = getOrIncl(src.pool.filenames, string("some/where.nim"))
        with buildTree(src, tFoo):
            appendLineInfo(src, f, i32(10), i32(2))
            with buildTree(src, tBar):
                addStrLit(src, string("hi"))                         # inline (<=3)
                addStrLit(src, string("a longer interned string"))   # pool
                addSymUse(src, string("some.long.symbol.name.0"))    # sym pool
                addSymDef(src, string("another.symbol.def.1"))
                addIntLit(src, 42)
                addIntLit(src, i64(1) << 40)                         # suffix-extended
                addUIntLit(src, u64(0))
                addFloatLit(src, 3.14)
                addIdent(src, string("ident_name"))

        with let:
            tmp = string("/tmp/bif_selftest.bif")
        store(src, tmp)
        with var:
            m = load(tmp)
        doAssert(_sameTokens(src, m.buf), string("token streams differ after round-trip"))
        # pools must match value-for-value (so ids line up)
        doAssert(len(m.buf.tags.tags) == len(src.tags.tags))
        doAssert(len(m.buf.pool.strings) == len(src.pool.strings))
        doAssert(syms(m.buf.pool).len == syms(src.pool).len)
        doAssert(len(m.buf.pool.filenames) == len(src.pool.filenames))
        # spot-check a decoded value via a cursor
        with var:
            c = beginRead(m.buf)
        doAssert(kind(c) == NifKind.TagLit)
        doAssert(tagName(m.buf.tags, cursorTagId(c)) == string("foo"))

        # the non-mmap File reader must decode byte-for-byte the same buffer as the
        # mmap path (it walks the same varint header + alignment pad).
        with var:
            ff = open(tmp, fmRead)
        with let:
            fm = loadFromFile(ff)
        close(ff)
        doAssert(_sameTokens(src, fm.buf), string("loadFromFile disagrees with mmap load"))
        doAssert(syms(fm.buf.pool).len == syms(src.pool).len)

        # containsSym probes only the syms table (skipping header, pad, tokens, tags,
        # strings); it must find a pooled name and reject an absent one.
        doAssert(containsSym(tmp, string("some.long.symbol.name.0")))
        doAssert(containsSym(tmp, string("another.symbol.def.1")))
        doAssert(not containsSym(tmp, string("no.such.symbol.here.9")))

    with block("embedded_index"):
        # A module-shaped buffer: a global exported def, a global hidden def, and a
        # purely-local def (< 2 dots) which must NOT be indexed.
        with var:
            src = createTokenBuf(16)
        with let:
            tStmts = registerTag(src.tags, string("stmts"))
            tSdef = registerTag(src.tags, string("sdef"))
        with buildTree(src, tStmts):
            with buildTree(src, tSdef):                 # exported global: `x` marker
                addSymDef(src, string("foo.3.mymod"))
                addIdent(src, string("x"))
            with buildTree(src, tSdef):                 # hidden global: `.` marker
                addSymDef(src, string("bar.4.mymod"))
                addDotToken(src)
            with buildTree(src, tSdef):                 # local (1 dot) -> not indexed
                addSymDef(src, string("loc.0"))
                addIdent(src, string("x"))

        with let:
            tmp = string("/tmp/bif_index_selftest.bif")
        store(src, tmp, dottedSuffix=string(".mymod"))
        with var:
            m = load(tmp)
        doAssert(m.index.len == 2, string("expected 2 global syms, got ") + str(m.index.len))
        # entry 0: foo, exported; its pos points at the enclosing (sdef tag.
        with let:
            e0 = m.index[0]
        doAssert(symString(m.buf.pool, e0.sym) == string("foo.3.mymod"))
        doAssert(e0.vis == IndexVis.ivExported)
        with var:
            c = cursorAt(m.buf, nint(e0.pos))
        doAssert(kind(c) == NifKind.TagLit and tagName(m.buf.tags, cursorTagId(c)) == string("sdef"))
        # entry 1: bar, hidden.
        doAssert(symString(m.buf.pool, m.index[1].sym) == string("bar.4.mymod"))
        doAssert(m.index[1].vis == IndexVis.ivHidden)

        with let:
            foo = m.findDeclaration(string("foo.3.mymod"))
        doAssert(not cursorIsNil(foo))
        doAssert(kind(foo) == NifKind.TagLit and tagName(m.buf.tags, cursorTagId(foo)) == string("sdef"))
        doAssert(cursorIsNil(m.findDeclaration(string("missing.0.mymod"))))
        with var:
            declarationCount = 0
        for name, visibility, declaration in m.declarations():
            doAssert(name in array[2, string]([string("foo.3.mymod"), string("bar.4.mymod")]))
            doAssert(visibility in Tset[IndexVis](IndexVis.ivExported, IndexVis.ivHidden))
            doAssert(kind(declaration) == NifKind.TagLit)
            declarationCount += 1
        doAssert(declarationCount == 2)

        # jump-only load: following indexOffset must yield exactly the same entries
        # the full load produced, without touching the token block or pools.
        with let:
            idx = loadIndex(tmp)
        doAssert(idx.len == m.index.len)
        for i in range(idx.len):
            doAssert(idx[i].sym == m.index[i].sym)
            doAssert(idx[i].pos == m.index[i].pos)
            doAssert(idx[i].vis == m.index[i].vis)

    def _buildModule(selfSym: string, sharedSym: string, fileName: string) -> TokenBuf:
        ## A module-shaped buffer: `(stmts (sdef <selfSym> x (call <sharedSym> …)))`,
        ## with line info on several heads so the remap has filenames to move.
        result = createTokenBuf(16)
        with let:
            tStmts = registerTag(result.tags, string("stmts"))
            tSdef = registerTag(result.tags, string("sdef"))
            tCall = registerTag(result.tags, string("call"))
            f = getOrIncl(result.pool.filenames, fileName)
        with buildTree(result, tStmts):
            appendLineInfo(result, f, i32(1), i32(0))
            with buildTree(result, tSdef):
                appendLineInfo(result, f, i32(12), i32(4))
                addSymDef(result, selfSym)
                addIdent(result, string("x"))
                with buildTree(result, tCall):
                    addSymUse(result, sharedSym)
                    addStrLit(result, string("hi"))                        # inline (<= 3 bytes)
                    addStrLit(result, string("a longer interned string"))  # pool ref
                    appendLineInfo(result, f, i32(13), i32(8))
                    addIntLit(result, 42)
                    addFloatLit(result, 3.14)
                    addCharLit(result, ch('q'))
                    addDotToken(result)
        return result

    with block("remap_into_shared_pools"):
        with var:
            src = _buildModule(string("foo.3.mymod"), string("shared.1.othermod"), string("some/where.nim"))
        with let:
            tmp = string("/tmp/bif_remap_selftest.bif")
        store(src, tmp, dottedSuffix=string(".mymod"))

        # Pools that are already busy, so no id can line up by accident. The 200
        # filenames matter: the loaded line infos referenced file id 1 (7-bit
        # layout) and must widen to the 14-bit layout on the way in.
        with let:
            pool = newPool()
            tags = newTagPool()
        _ = registerTag(tags, string("unrelated"))
        _ = getOrIncl(pool.strings, string("some other string"))
        _ = symId(pool, string("prior.symbol.0.othermod"))
        for i in range(200): _ = getOrIncl(pool.filenames, string("file") + str(i) + string(".nim"))

        with var:
            m = loadInto(tmp, pool, tags)
        doAssert(m.buf.pool == pool, string("loaded buffer does not carry the caller's pool"))
        doAssert(m.buf.tags == tags, string("loaded buffer does not carry the caller's tags"))
        doAssert(uint32(getOrIncl(pool.filenames, string("some/where.nim"))) > LiFileMaxC,
                 string("test setup: the file id did not exceed the 7-bit layout"))

        with var:
            a = beginRead(src)
            b = beginRead(m.buf)
        doAssert(_sameTree(a, b), string("remapped tree differs from the source"))
        endRead(a)
        endRead(b)
        # The wide file layout costs one extra token per line info, so the rewrite
        # provably ran (and provably could not have been an in-place id patch).
        doAssert(m.buf.len > src.len,
                 utf8("line infos did not widen — the remap path was not exercised"))

        # The point of the exercise: ids in the loaded buffer ARE the caller pool's
        # ids, so `SymId` equality is a valid identity test against anything else
        # interned there.
        doAssert(m.index.len == 1, string("expected 1 global sym, got ") + str(m.index.len))
        doAssert(m.index[0].sym == symId(pool, string("foo.3.mymod")))
        doAssert(m.index[0].vis == IndexVis.ivExported)
        with var:
            decl = cursorAt(m.buf, nint(m.index[0].pos))
        doAssert(kind(decl) == NifKind.TagLit and tags.tags[cursorTagId(decl)] == string("sdef"),
                 string("index position does not point at the declaration's tag"))
        with var:
            body = sub(decl)
        doAssert(kind(body) == NifKind.SymbolDef)
        doAssert(symId(body, pool) == m.index[0].sym)

        # A second module translated into the SAME pools must agree on the symbol
        # they share — the relation the whole translation exists for.
        with var:
            src2 = _buildModule(string("bar.7.other"), string("shared.1.othermod"), string("else/where.nim"))
        with let:
            tmp2 = string("/tmp/bif_remap_selftest2.bif")
        store(src2, tmp2, dottedSuffix=string(".other"))
        with var:
            m2 = loadInto(tmp2, pool, tags)

        def firstSymUse(mo: mut @ BifModule) -> SymId:
            with var:
                c = beginRead(mo.buf)
            result = SymId(0)
            while hasMore(c):
                if kind(c) == NifKind.Symbol:
                    result = symId(c, mo.buf.pool)
                    break
                inc(c)
            endRead(c)
            return result
        doAssert(uint32(firstSymUse(m)) != u32(0))
        doAssert(firstSymUse(m) == firstSymUse(m2),
                 string("the shared symbol got different SymIds in two modules"))
        doAssert(firstSymUse(m) == symId(pool, string("shared.1.othermod")))
        # …and the tag pools agree too, which is what makes `cursorTagId` castable.
        doAssert(m2.buf.tags == tags)
        # Guard against a vacuous comparator: two genuinely different modules must
        # NOT compare equal.
        with var:
            d1 = beginRead(src)
            d2 = beginRead(m2.buf)
        doAssert(not _sameTree(d1, d2), string("sameTree does not detect a difference"))
        endRead(d1)
        endRead(d2)

    with block("remap_identity_and_file_reader"):
        # Empty target pools: the file's ids are reproduced exactly, so the token
        # stream is handed over untouched (and the mmap block is borrowed).
        with let:
            tmp = string("/tmp/bif_remap_selftest.bif")
            pool = newPool()
            tags = newTagPool()
        with var:
            m = loadInto(tmp, pool, tags)
            plain = load(tmp)
        doAssert(_sameTokens(plain.buf, m.buf), string("identity remap rewrote the stream"))
        doAssert(m.index.len == plain.index.len)
        for i in range(m.index.len):
            doAssert(m.index[i].sym == plain.index[i].sym)
            doAssert(m.index[i].pos == plain.index[i].pos)
        doAssert(m.buf.pool == pool)

        # The file (non-mmap) reader must reach the same result, and must NOT hand
        # out a token block that dies with the temporary buffer.
        with let:
            pool2 = newPool()
            tags2 = newTagPool()
        _ = symId(pool2, string("prior.symbol.0.othermod"))   # force a rewrite
        with var:
            ff = open(tmp, fmRead)
            fm = loadFromFileInto(ff, pool2, tags2)
        close(ff)
        with var:
            a = beginRead(m.buf)
            b = beginRead(fm.buf)
        doAssert(_sameTree(a, b), string("loadFromFileInto disagrees with loadInto"))
        endRead(a)
        endRead(b)
        doAssert(fm.index[0].sym == symId(pool2, string("foo.3.mymod")))

    echo(string("bif self-tests passed"))


if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir", "removeFile")

    def _hexOf(s: string) -> string:
        result = string("")
        for c in s:
            result.add(toHex(ord(c), 2))
        return result

    def _samePools(a: TokenBuf, b: TokenBuf) -> bool:
        if len(a.tags.tags) != len(b.tags.tags) or len(a.pool.strings) != len(b.pool.strings) or \
                syms(a.pool).len != syms(b.pool).len or len(a.pool.filenames) != len(b.pool.filenames):
            return False
        for i in inrange(1, len(a.tags.tags)):
            if a.tags.tags[TagId(i)] != b.tags.tags[TagId(i)]: return False
        for i in inrange(1, len(a.pool.strings)):
            if a.pool.strings[StrId(i)] != b.pool.strings[StrId(i)]: return False
        for i in inrange(1, syms(a.pool).len):
            if symString(a.pool, SymId(i)) != symString(b.pool, SymId(i)): return False
        for i in inrange(1, len(a.pool.filenames)):
            if a.pool.filenames[FileId(i)] != b.pool.filenames[FileId(i)]: return False
        return True

    def _echoModule(label: string, m: mut @ BifModule):
        echo(label, string(": tokens "), m.buf.len, string(" tags "), len(m.buf.tags.tags),
             string(" strings "), len(m.buf.pool.strings), string(" syms "), syms(m.buf.pool).len,
             string(" files "), len(m.buf.pool.filenames), string(" index "), m.index.len)
        for e in m.index:
            echo(string("  "), symString(m.buf.pool, e.sym), string(" sym "), uint32(e.sym), string(" pos "), e.pos,
                 string(" "), e.vis)
        for name, visibility, declaration in m.declarations():
            echo(string("  decl "), name, string(" "), visibility, string(" "),
                 tagName(m.buf.tags, cursorTagId(declaration)))

    def _sameAs(label: string, src: mut @ TokenBuf, m: mut @ BifModule):
        with var:
            a = beginRead(src)
            b = beginRead(m.buf)
        echo(label, string(": same tree "), _sameTree(a, b), string(", same tokens "), _sameTokens(src, m.buf),
             string(", same pools "), _samePools(src, m.buf))
        endRead(a)
        endRead(b)

    def _test():
        echo(UnusedNameTag, string(" "), DependencyTag)
        with let:
            tmpDir = getTempDir()
            p1 = tmpDir + string("nimic_bif_test_store.bif")
            p2 = tmpDir + string("nimic_bif_test_file.bif")
            pText = tmpDir + string("nimic_bif_test_text.nif")
            pMissing = tmpDir + string("nimic_bif_test_missing.bif")
            pShort = tmpDir + string("nimic_bif_test_short.bif")
            pCut = tmpDir + string("nimic_bif_test_cut.bif")
        with var:
            src = _buildModule(string("foo.3.mymod"), string("shared.1.othermod"), string("some/where.nim"))
        # buildIndex: the self-module suffix decides which symbols are global
        echo(string("buildIndex: "), buildIndex(src).len, string(" "), buildIndex(src, string(".mymod")).len,
             string(" "), buildIndex(src, dottedSuffix=string(".3.mymod")).len)

        # the three writers write the same bytes
        with let:
            bytes = storeToString(src, string(".mymod"))
            hx = _hexOf(bytes)
        echo(string("storeToString: "), bytes.len, string(" bytes"))
        with var:
            i = 0
        while i < hx.len:
            echo(string("  "), substr(hx, i, min(i + 63, hx.len - 1)))
            i += 64
        store(src, p1, dottedSuffix=string(".mymod"))
        with var:
            f = open(p2, fmWrite)
        storeToFile(src, f, string(".mymod"))
        close(f)
        echo(string("store == storeToString: "), readFile(p1) == bytes)
        echo(string("storeToFile == storeToString: "), readFile(p2) == bytes)

        # isBifFile: a bif file, a text NIF file, a missing file, a file shorter than the magic
        writeFile(pText, string("(.nif27)\n(stmts)\n"))
        writeFile(pShort, substr(bytes, 0, 4))
        echo(string("isBifFile: "), isBifFile(p1), string(" "), isBifFile(pText), string(" "),
             isBifFile(pMissing), string(" "), isBifFile(pShort))

        # every loader on the same file gives the same tokens and pools
        with var:
            m1 = load(p1)
        _echoModule(string("load"), m1)
        _sameAs(string("load"), src, m1)
        f = open(p1, fmRead)
        with var:
            m2 = loadFromFile(f)
        close(f)
        _echoModule(string("loadFromFile"), m2)
        _sameAs(string("loadFromFile"), src, m2)
        with var:
            m3 = loadInto(p1, newPool(), newTagPool())
        _echoModule(string("loadInto (empty pools)"), m3)
        _sameAs(string("loadInto (empty pools)"), src, m3)
        with let:
            busyPool = newPool()
            busyTags = newTagPool()
        _ = registerTag(busyTags, string("unrelated"))
        _ = symId(busyPool, string("prior.symbol.0.othermod"))
        _ = getOrIncl(busyPool.strings, string("some other string"))
        with var:
            m4 = loadInto(p1, busyPool, busyTags)
        _echoModule(string("loadInto (busy pools)"), m4)
        _sameAs(string("loadInto (busy pools)"), src, m4)
        f = open(p1, fmRead)
        with var:
            m5 = loadFromFileInto(f, busyPool, busyTags)
        close(f)
        _echoModule(string("loadFromFileInto (same busy pools)"), m5)
        _sameAs(string("loadFromFileInto (same busy pools)"), src, m5)
        echo(string("busy pools shared: "), m4.buf.pool == busyPool, string(" "), m5.buf.tags == busyTags,
             string(", same index: "), m4.index[0].sym == m5.index[0].sym, string(" "),
             m4.index[0].pos == m5.index[0].pos)

        # buildRemap: identity into empty pools, a real map into busy ones
        with let:
            rm1 = buildRemap(m1.buf, newPool(), newTagPool())
            rm2 = buildRemap(m1.buf, busyPool, busyTags)
        echo(string("remap identity: "), rm1.identity, string(" "), rm2.identity)
        for i in range(1, rm2.tags.len): echo(string("  tag "), i, string(" -> "), uint32(rm2.tags[i]))
        for i in range(1, rm2.strings.len): echo(string("  string "), i, string(" -> "), uint32(rm2.strings[i]))
        for i in range(1, rm2.syms.len): echo(string("  sym "), i, string(" -> "), uint32(rm2.syms[i]))
        for i in range(1, rm2.files.len): echo(string("  file "), i, string(" -> "), uint32(rm2.files[i]))

        # findDeclaration on a loaded module
        with let:
            decl = m1.findDeclaration(string("foo.3.mymod"))
        echo(string("findDeclaration: "), kind(decl), string(" "), tagName(m1.buf.tags, cursorTagId(decl)),
             string(" "), cursorIsNil(m1.findDeclaration(string("shared.1.othermod"))))

        # loadIndex / loadIndexFromFile / containsSym
        with let:
            idx = loadIndex(p1)
        echo(string("loadIndex: "), idx.len)
        for e in idx: echo(string("  sym "), uint32(e.sym), string(" pos "), e.pos, string(" "), e.vis)
        f = open(p1, fmRead)
        with let:
            idx2 = loadIndexFromFile(f)
        close(f)
        echo(string("loadIndexFromFile: "), idx2.len, string(" "), idx2[0].sym == idx[0].sym,
             string(" "), idx2[0].pos == idx[0].pos)
        echo(string("containsSym: "), containsSym(p1, string("foo.3.mymod")), string(" "),
             containsSym(p1, string("shared.1.othermod")), string(" "),
             containsSym(p1, string("shared.1.othermoe")), string(" "),
             containsSym(p1, string("x")), string(" "),
             containsSym(pText, string("foo.3.mymod")), string(" "),
             containsSym(pMissing, string("foo.3.mymod")), string(" "),
             containsSym(pShort, string("foo.3.mymod")))
        # a file cut inside the last symbol: the symbols before the cut are found, the cut one is not
        with let:
            at = find(bytes, string("shared.1.othermod"))
        writeFile(pCut, substr(bytes, 0, at + 4))
        echo(string("containsSym (cut): "), containsSym(pCut, string("foo.3.mymod")), string(" "),
             containsSym(pCut, string("shared.1.othermod")))

        removeFile(p1)
        removeFile(p2)
        removeFile(pText)
        removeFile(pShort)
        removeFile(pCut)

    _test()
