# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifcoreparse.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## NIF text parser producing a `nifcore.TokenBuf`.
##
## Reuses the existing `nifreader`, whose `ExpandedToken` is independent of
## the in-memory representation: its `ParLe`/`ParRi` events drive nifcore's
## `openTag`/`closeTag`, and atoms drive the builder. The reader's relative
## line positions are resolved to absolute file/line/col (against a parent
## stack, exactly like `nifstreams.rawNext`) and emitted as a sparse
## `LineInfoLit` suffix only where the position changes. Callers that need
## random-access effective locations can request dense line info while parsing.
##
## Note: NIF `#comment#` decorations are not carried into the token buffer —
## the codegen path has no use for them.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.assertions import *
from nimic.std.math import *
from .nifcore import *
from . import nifcore
from . import nifreader as rd
from .nifbuilder import *
from . import nifbuilder
from .stringviews import *
from .lineinfos import *  # for `==`(FileId) used by NifLineInfo's structural `==`

with export:
    nifcore
from .comesfrom import *
from . import comesfrom

# Travels with the reader for the same reason it travels with the pool API:
# any consumer of a line-info filename may need `realFile` to strip the
# template-expansion provenance the front end forged into it.
with export:
    comesfrom


class _Parent(NTuple):
    file: FileId
    line: int32
    col: int32


def _resolveInfo(b: mut @ TokenBuf, tok: rd.ExpandedToken,
                 parents: seq[_Parent]) -> NifLineInfo:
    """{.inline.}"""
    ## Absolute file/line/col for `tok`, plus any `#…#` comment. Absolute when
    ## the token carries a filename; otherwise relative to the enclosing tag
    ## (parents[^1]). A comment is only carried when the file resolves (line info
    ## is the comment's vehicle); in the IC use it always rides a positioned sym.
    with var:
        comment = StrId(0)
    if tok.comment.len != 0:
        comment = b.pool.strings.getOrIncl(rd.decodeComment(tok))
    if tok.filename.len != 0:
        with let:
            f = b.pool.filenames.getOrIncl(rd.decodeFilename(tok))
        result = NifLineInfo(file=f, line=tok.pos.line, col=tok.pos.col,
                             comment=comment)
    else:
        with let:
            p = parents[back(1)]
        result = NifLineInfo(file=p.file,
                             line=p.line + tok.pos.line,
                             col=p.col + tok.pos.col,
                             comment=comment)
    return result


def peekRootInfo(r: mut @ rd.Reader, pool: Pool) -> NifLineInfo:
    ## Absolute line info of the next token — typically a module's toplevel
    ## `(stmts)` head, which carries the file explicitly — without consuming it.
    ## Index-jumped decl reads pass this as `parse`'s `parentSeed` so their
    ## file-less child position deltas resolve against the module root (a decl's
    ## parent in the original tree IS the toplevel `(stmts)` node).
    with let:
        start = rd.offset(r)
    with var:
        tok = default(rd.ExpandedToken)
    rd.next(r, tok)
    if tok.filename.len != 0:
        result = NifLineInfo(file=pool.filenames.getOrIncl(rd.decodeFilename(tok)),
                             line=tok.pos.line, col=tok.pos.col)
    else:
        result = NoNifLineInfo
    rd.jumpTo(r, start)
    return result


def _internPart(b: mut @ TokenBuf, r: rd.Reader, t: rd.ExpandedToken) -> StrId:
    ## One component of a split symbol, interned. When the bytes ARE the value --
    ## no escape, no module suffix to append, which is the overwhelming case --
    ## they go into the string pool straight from the reader's mapped file.
    if rd.needsDecoding(t):
        return b.pool.strings.getOrIncl(rd.decodeStr(r, t))
    else:
        return b.pool.strings.getOrInclFromView(t.data)


def _addSplitSymbol(b: mut @ TokenBuf, r: mut @ rd.Reader,
                    head: rd.ExpandedToken, isDef: bool):
    ## Emit the symbol whose `<name>` is `head` and whose remaining components
    ## follow it as `ExtendedSuffix` tokens (see `nifreader.splitSymbols`). The
    ## pool stores exactly those components, so the common shape is interned
    ## straight from the reader's bytes: the spelling is never assembled and
    ## never parsed back apart.
    ##
    ## Three shapes fall back to handing `symId` a spelling, because only it can
    ## decide where the name ends: a disambiguator that is not a number, a name
    ## carrying two keys (`foo.0.Ia.Ib.mod`), and one short enough to live inside
    ## the token, which the pool must not gain an entry for.
    with var:
        disambTok = default(rd.ExpandedToken)
    with var:
        dedupTok = default(rd.ExpandedToken)
    with var:
        moduleTok = default(rd.ExpandedToken)
    with var:
        dedupStr = string("")
    with var:
        dedups = 0
    with var:
        hasDisamb = False
    with var:
        rawLen = head.data.len.copy()
    for _ in inrange(1, nint(head.suffixes)):
        with var:
            t = default(rd.ExpandedToken)
        rd.next(r, t)
        rawLen += 1 + t.data.len
        match t.part:
            case rd.SymbolPart.SymDisamb:
                disambTok = t
                hasDisamb = True
            case rd.SymbolPart.SymDedup:
                dedups += 1
                if dedups == 1:
                    dedupTok = t
                else:
                    if dedups == 2: dedupStr = rd.decodeStr(r, dedupTok)
                    dedupStr.add(char('.'))
                    dedupStr.add(rd.decodeStr(r, t))
            case rd.SymbolPart.SymModule:
                moduleTok = t

    with var:
        disamb = -1
    with var:
        disambText = string("")
    if hasDisamb:
        disambText = rd.decodeStr(r, disambTok)  # 1-3 bytes, and the value is needed
        disamb = parseDisamb(disambText, 0, disambText.len)

    # `rawLen` is an upper bound on the spelling (an escape shrinks, and a module
    # suffix to expand only ever grows it past this test anyway), so it is a sound
    # way to ask "could this fit inside the token?".
    if (hasDisamb and disamb < 0) or dedups > 1 or rawLen <= StrInlineMaxLen:
        with var:
            spelling = rd.decodeStr(r, head)
        if hasDisamb:
            spelling.add(char('.'))
            spelling.add(disambText)
        if dedups == 1:
            spelling.add(char('.'))
            spelling.add(rd.decodeStr(r, dedupTok))
        elif dedups > 1:
            spelling.add(char('.'))
            spelling.add(dedupStr)
        if moduleTok.tk == NifKind.ExtendedSuffix:
            spelling.add(char('.'))
            spelling.add(rd.decodeStr(r, moduleTok))
        if isDef: b.addSymDef(spelling)
        else: b.addSymUse(spelling)
        return

    with var:
        s = NifSymbol(name=_internPart(b, r, head), disamb=int32(disamb),
                      dedup=StrId(0), module=StrId(0))
    if not hasDisamb: s.disamb = NoDisamb
    if dedups == 1: s.dedup = _internPart(b, r, dedupTok)
    if moduleTok.tk == NifKind.ExtendedSuffix: s.module = _internPart(b, r, moduleTok)
    with let:
        id = symId(b.pool, s)
    if isDef: b.addSymDef(id)
    else: b.addSymUse(id)


@template_expand
def parse(r: mut @ rd.Reader, b: mut @ TokenBuf,
          parentSeed: NifLineInfo = NoNifLineInfo,
          denseLineInfo=False):
    ## Read one complete NIF tree (or until EOF) from `r` into `b`. `parentSeed`
    ## seeds the parent line-info stack so the first token's relative position
    ## resolves against the right origin (index-jumped reads pass the indexed
    ## compound's parent info; whole-file reads pass `NoNifLineInfo`).
    ## With `denseLineInfo`, every positioned value receives its effective
    ## location instead of only changes in the location stream.
    # Symbols arrive taken apart, so their components go into the pool directly
    # (see `readSymbol`). Idempotent, and `jumpTo` drops any components a caller
    # skipped over.
    rd.splitSymbols(r)
    with var:
        parents = seq[_Parent]([_Parent(file=parentSeed.file, line=parentSeed.line,
                                        col=parentSeed.col)])
    with var:
        last = NoNifLineInfo
    with var:
        nested = 0
    with var:
        tok = default(rd.ExpandedToken)

    @template
    def emit(info: NifLineInfo):
        if info.isValid() and (denseLineInfo or info != last):
            b.appendLineInfo(info)
            last = info

    while True:
        rd.next(r, tok)
        match tok.tk:
            case (rd.NifKind.EofToken | rd.NifKind.UnknownToken | NifKind.TagLit | NifKind.ExtendedSuffix |
                  NifKind.LineInfoLit):
                # `TagLit`/`LineInfoLit` are binary-only kinds the textual reader never
                # yields. An `ExtendedSuffix` never reaches HERE either: `readSymbol`
                # consumes a split symbol's components as part of the symbol.
                break
            case rd.NifKind.ParLe:
                with let:
                    info = _resolveInfo(b, tok, parents)
                # No escape handling here: `openTag` folds an id that does not fit the
                # 9-bit tag field into the adapter's escape tag by itself, and the
                # line-info suffix lands on the head either way.
                b.openTag(b.tags.tags.getOrInclFromView(tok.data))
                emit(info)
                parents.add((info.file, info.line, info.col))
                nested += 1
            case rd.NifKind.ParRi:
                b.closeTag()
                if parents.len > 1: _ = parents.pop()
                nested -= 1
                if nested == 0: break
            case rd.NifKind.DotToken:
                with let:
                    info = _resolveInfo(b, tok, parents)
                b.addDotToken(); emit(info)
            case rd.NifKind.Ident:
                with let:
                    info = _resolveInfo(b, tok, parents)
                b.addIdent(rd.decodeStr(r, tok)); emit(info)
            case rd.NifKind.Symbol:
                with let:
                    info = _resolveInfo(b, tok, parents)
                if tok.suffixes > u8(0): _addSplitSymbol(b, r, tok, isDef=False)
                else: b.addSymUse(rd.decodeStr(r, tok))
                emit(info)
            case rd.NifKind.SymbolDef:
                with let:
                    info = _resolveInfo(b, tok, parents)
                if tok.suffixes > u8(0): _addSplitSymbol(b, r, tok, isDef=True)
                else: b.addSymDef(rd.decodeStr(r, tok))
                emit(info)
            case rd.StringLit:
                with let:
                    info = _resolveInfo(b, tok, parents)
                b.addStrLit(rd.decodeStr(r, tok)); emit(info)
            case rd.NifKind.CharLit:
                with let:
                    info = _resolveInfo(b, tok, parents)
                b.addCharLit(rd.decodeChar(tok)); emit(info)
            case rd.NifKind.IntLit:
                with let:
                    info = _resolveInfo(b, tok, parents)
                b.addIntLit(rd.decodeInt(tok)); emit(info)
            case rd.NifKind.UIntLit:
                with let:
                    info = _resolveInfo(b, tok, parents)
                b.addUIntLit(rd.decodeUInt(tok)); emit(info)
            case rd.NifKind.FloatLit:
                with let:
                    info = _resolveInfo(b, tok, parents)
                b.addFloatLit(rd.decodeFloat(tok)); emit(info)
        if nested == 0 and tok.tk not in Tset(rd.NifKind.ParLe):
            # A bare top-level atom is a complete "tree" on its own.
            break


@dispatch
def parseFromBuffer(input: string, thisModule: sink @ string,
                    sizeHint=100, sharedPool: Pool = None,
                    sharedTags: TagPool = None,
                    denseLineInfo=False) -> TokenBuf:
    with var:
        r = rd.openFromBuffer(input.copy(), thisModule)
    result = createTokenBuf(sizeHint, sharedPool, sharedTags)
    parse(r, result, denseLineInfo=denseLineInfo)
    return result


@dispatch
def parseFromBuffer(input: string, thisModule: sink @ string,
                    unusedName: mut @ string, sizeHint=100,
                    sharedPool: Pool = None, sharedTags: TagPool = None,
                    denseLineInfo=False) -> TokenBuf:
    ## Parses NIF text and returns its `.unusedname` directive via `unusedName`.
    with var:
        r = rd.openFromBuffer(input.copy(), thisModule)
    unusedName <<= r.firstUnusedName()
    result = createTokenBuf(sizeHint, sharedPool, sharedTags)
    parse(r, result, denseLineInfo=denseLineInfo)
    return result


@dispatch
def parseFromFile(filename: string, sizeHint=100,
                  sharedPool: Pool = None,
                  sharedTags: TagPool = None,
                  denseLineInfo=False) -> TokenBuf:
    with var:
        r = rd.open(filename)
    _ = rd.processDirectives(r)
    result = createTokenBuf(sizeHint, sharedPool, sharedTags)
    parse(r, result, denseLineInfo=denseLineInfo)
    rd.close(r)   # the reader mmaps the file; a leak keeps it locked on Windows
    return result


@dispatch
def parseFromFile(filename: string, unusedName: mut @ string,
                  sizeHint=100, sharedPool: Pool = None,
                  sharedTags: TagPool = None,
                  denseLineInfo=False) -> TokenBuf:
    ## Parses a NIF file and returns its `.unusedname` directive via `unusedName`.
    with var:
        r = rd.open(filename)
    unusedName <<= r.firstUnusedName()
    result = createTokenBuf(sizeHint, sharedPool, sharedTags)
    parse(r, result, denseLineInfo=denseLineInfo)
    rd.close(r)
    return result

# ── toString ─────────────────────────────────────────────────────────────


def _emitRelLineInfo(bld: mut @ Builder, abs: NifLineInfo, parent: NifLineInfo, pool: Pool,
                     emitComment=True):
    ## Emit a NIF27 line-info suffix for `abs`, relative to the enclosing tag's
    ## `parent` info when they share a file (absolute, with filename, otherwise).
    ## Mirrors `nifstreams.emitLineInfo`. When `abs` carries a `comment` and
    ## `emitComment` is set, also append it as a `#…#` decoration (the embedded
    ## index passes `emitComment = false` to keep its format comment-free).
    if not isValid(abs.file): return
    with var:
        line = abs.line
    with var:
        col = abs.col
    with var:
        fileStr = string("")
    if isValid(parent.file):
        if abs.file != parent.file: fileStr = pool.filenames[abs.file]
        if fileStr.len == 0:                 # same file → relative diff
            line = abs.line - parent.line
            col = abs.col - parent.col
    else:
        fileStr = pool.filenames[abs.file]
    bld.attachLineInfo(col, line, fileStr)
    if emitComment and uint32(abs.comment) != u32(0):
        bld.attachComment(pool.strings[abs.comment])


def _emitFloatLit(bld: mut @ Builder, v: float64, abs: NifLineInfo, parent: NifLineInfo,
                  pool: Pool):
    ## `nifbuilder` spells a non-finite float as a compound -- `(inf)`, `(nan)`,
    ## `(neginf)` -- and a line-info suffix may only follow an atom or a tag
    ## *name*. Attached after the closing `)` it is not NIF: the reader stops
    ## there and the rest of the module is lost. So the compound is written
    ## here, with the suffix on its tag.
    with let:
        fc = classify(v)
    match fc:
        case FloatClass.fcInf | FloatClass.fcNan | FloatClass.fcNegInf:
            bld.addTree(string("inf") if fc == FloatClass.fcInf else string("nan") if fc == FloatClass.fcNan else
                        string("neginf"))
            _emitRelLineInfo(bld, abs, parent, pool)
            bld.endTree()
        case _:
            bld.addFloatLit(v)
            _emitRelLineInfo(bld, abs, parent, pool)


def _emitValueWithLineInfo(bld: mut @ Builder, c: mut @ Cursor,
                           cur: mut @ NifLineInfo,
                           parents: mut @ seq[NifLineInfo],
                           tags: TagPool, pool: Pool):
    ## Emit one value (atom or whole TagLit subtree), advancing `c` past it.
    ## `cur` is the running absolute line info (a head with no `LineInfoLit`
    ## inherits it); `parents` holds enclosing-tag infos for relative encoding.
    with let:
        li = rawLineInfo(c)
    with let:
        abs = li if li.isValid() else cur
    if li.isValid():
        cur <<= li
        cur.comment = StrId(0)   # a comment is a one-shot decoration, never inherited
    match kind(c):
        case NifKind.TagLit:
            with let:
                escaped = isEscapedTag(c)
            bld.addTree(tags.tags[resolvedTagId(c)])
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            parents.add(abs)
            with c.into():
                if escaped: inc(c)               # the escaped id IS the tag name above
                while hasMore(c):
                    _emitValueWithLineInfo(bld, c, cur, parents, tags, pool)
            _ = parents.pop()
            bld.endTree()
        case NifKind.DotToken:
            bld.addEmpty(); _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.Ident:
            bld.addIdent(strVal(c, pool))
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
        case NifKind.StrLit:
            bld.addStrLit(strVal(c, pool))
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
        case NifKind.Symbol:
            bld.addSymbol(symName(c, pool))
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
        case NifKind.SymbolDef:
            bld.addSymbolDef(symName(c, pool))
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
        case NifKind.CharLit:
            bld.addCharLit(charLit(c))
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
        case NifKind.IntLit:
            bld.addIntLit(intVal(c))
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
        case NifKind.UIntLit:
            bld.addUIntLit(uintVal(c))
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
        case NifKind.FloatLit:
            _emitFloatLit(bld, floatVal(c), abs, parents[back(1)], pool)
            inc(c)
        case (NifKind.ExtendedSuffix | NifKind.LineInfoLit | NifKind.UnknownToken | NifKind.EofToken |
              NifKind.ParLe | NifKind.ParRi):
            assert False, "suffix token is not a value head"


def _emitValueWithoutLineInfo(bld: mut @ Builder, c: mut @ Cursor,
                              tags: TagPool, pool: Pool):
    ## Fast diagnostic serializer: no location decoding or parent stack.
    match kind(c):
        case NifKind.TagLit:
            with let:
                escaped = isEscapedTag(c)
            bld.addTree(tags.tags[resolvedTagId(c)])
            with c.into():
                if escaped: inc(c)
                while hasMore(c):
                    _emitValueWithoutLineInfo(bld, c, tags, pool)
            bld.endTree()
        case NifKind.DotToken:
            bld.addEmpty(); inc(c)
        case NifKind.Ident:
            bld.addIdent(strVal(c, pool)); inc(c)
        case NifKind.StrLit:
            bld.addStrLit(strVal(c, pool)); inc(c)
        case NifKind.Symbol:
            bld.addSymbol(symName(c, pool)); inc(c)
        case NifKind.SymbolDef:
            bld.addSymbolDef(symName(c, pool)); inc(c)
        case NifKind.CharLit:
            bld.addCharLit(charLit(c)); inc(c)
        case NifKind.IntLit:
            bld.addIntLit(intVal(c)); inc(c)
        case NifKind.UIntLit:
            bld.addUIntLit(uintVal(c)); inc(c)
        case NifKind.FloatLit:
            bld.addFloatLit(floatVal(c)); inc(c)
        case (NifKind.ExtendedSuffix | NifKind.LineInfoLit | NifKind.UnknownToken | NifKind.EofToken |
              NifKind.ParLe | NifKind.ParRi):
            assert False, "suffix token is not a value head"


def appendTo(b: mut @ TokenBuf, dest: mut @ Builder,
             includeLineInfo=True):
    ## Appends canonical NIF text for the whole buffer to `dest`.
    with var:
        c = b.beginRead()
    if includeLineInfo:
        with var:
            cur = NoNifLineInfo.copy()
        with var:
            parents = seq[NifLineInfo]([NoNifLineInfo])
        while hasMore(c):
            _emitValueWithLineInfo(dest, c, cur, parents, b.tags, b.pool)
    else:
        while hasMore(c):
            _emitValueWithoutLineInfo(dest, c, b.tags, b.pool)


@dispatch
def toString(b: mut @ TokenBuf, sizeHint=0,
             includeLineInfo=True) -> string:
    ## Canonical NIF text for the whole buffer (one or more top-level values).
    ## Set `includeLineInfo` to false for location-free diagnostic rendering.
    with var:
        bld = nifbuilder.open(sizeHint if sizeHint > 0 else len(b) * 8)
    b.appendTo(bld, includeLineInfo)
    result = bld.extract()
    return result


@dispatch
def toString(node: Cursor, sizeHint=0,
             includeLineInfo=True) -> string:
    ## Canonical NIF text for the value or subtree at `node`.
    if not hasMore(node):
        return string("")
    with var:
        bld = nifbuilder.open(
            sizeHint if sizeHint > 0 else subtreeWidth(node) * 8)
    with var:
        c = node.copy()
    if includeLineInfo:
        with var:
            cur = NoNifLineInfo.copy()
        with var:
            parents = seq[NifLineInfo]([NoNifLineInfo])
        _emitValueWithLineInfo(bld, c, cur, parents, tags(node), pool(node))
    else:
        _emitValueWithoutLineInfo(bld, c, tags(node), pool(node))
    result = bld.extract()
    return result

# ── toModuleString (full file with embedded index) ─────────────────────────


def _emitValueIndexed(bld: mut @ Builder, c: mut @ Cursor, cur: mut @ NifLineInfo,
                      parents: mut @ seq[NifLineInfo], tags: TagPool, pool: Pool,
                      index: mut @ Builder, dottedSuffix: string,
                      mostRecentOffset: mut @ nint, previousOffset: mut @ nint,
                      rootInfo: NifLineInfo):
    ## Like `emitValue`, but also records an index entry for every *global*
    ## SymbolDef. The recorded offset is that of the most recently opened tag (the
    ## declaration's `(`), delta-encoded against the previous entry — mirroring
    ## `nifstreams.toModuleString` so the embedded index is byte-compatible with the
    ## canonical reader (`nifindexes.readEmbeddedIndex`).
    with let:
        li = rawLineInfo(c)
    with let:
        abs = li if li.isValid() else cur
    if li.isValid():
        cur <<= li
        cur.comment = StrId(0)   # a comment is a one-shot decoration, never inherited
    match kind(c):
        case NifKind.TagLit:
            mostRecentOffset <<= bld.offset()            # offset of this `(`
            with let:
                escaped = isEscapedTag(c)
            bld.addTree(tags.tags[resolvedTagId(c)])
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            parents.add(abs)
            with c.into():
                if escaped: inc(c)
                while hasMore(c):
                    _emitValueIndexed(bld, c, cur, parents, tags, pool, index, dottedSuffix,
                                      mostRecentOffset, previousOffset, rootInfo)
            _ = parents.pop()
            bld.endTree()
        case NifKind.SymbolDef:
            with let:
                name = symName(c, pool)
            with let:
                isGlobal = bld.addSymbolDefRetIsGlobal(name, dottedSuffix)
            _emitRelLineInfo(bld, abs, parents[back(1)], pool)
            inc(c)
            if isGlobal:
                # Hidden if the next sibling is the empty export marker (`.`), else exported.
                if kind(c) == NifKind.DotToken: index.addTree(string("h"))
                else: index.addTree(string("x"))
                # Record the indexed compound's PARENT info (parents[^2]); on lookup `parse`
                # seeds its parent stack with this and the first token it reads — the
                # compound's `(` — carries the diff. (See nifstreams.toModuleString.)
                with let:
                    parentInfo = parents[back(2)] if parents.len >= 2 else rootInfo
                _emitRelLineInfo(index, parentInfo, rootInfo, pool, emitComment=False)
                index.addSymbol(name, dottedSuffix)
                index.addIntLit(mostRecentOffset - previousOffset)
                previousOffset <<= mostRecentOffset
                index.endTree()
        case NifKind.Symbol:
            bld.addSymbol(symName(c, pool), dottedSuffix)
            _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.DotToken:
            bld.addEmpty(); _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.Ident:
            bld.addIdent(strVal(c, pool)); _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.StrLit:
            bld.addStrLit(strVal(c, pool)); _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.CharLit:
            bld.addCharLit(charLit(c)); _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.IntLit:
            bld.addIntLit(intVal(c)); _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.UIntLit:
            bld.addUIntLit(uintVal(c)); _emitRelLineInfo(bld, abs, parents[back(1)], pool); inc(c)
        case NifKind.FloatLit:
            _emitFloatLit(bld, floatVal(c), abs, parents[back(1)], pool); inc(c)
        case (NifKind.ExtendedSuffix | NifKind.LineInfoLit | NifKind.UnknownToken | NifKind.EofToken |
              NifKind.ParLe | NifKind.ParRi):
            assert False, "suffix token is not a value head"


def toModuleString(b: mut @ TokenBuf, dottedSuffix=string(""), sizeHint=0,
                   compact=False) -> string:
    ## Like `toString` but emits a full module file: the `(.nif27)` header with a
    ## patched `.indexat`, the body, and a trailing `(.index …)` mapping each global
    ## SymbolDef to its declaration's byte offset. `dottedSuffix` (e.g. `.mymod`)
    ## compresses self-module symbol suffixes to a trailing dot (the reader re-
    ## expands via its `thisModule`). Mirrors `nifstreams.toModuleString` so the
    ## output is byte-compatible with the canonical tooling (`reindex`).
    ##
    ## `compact` drops the layout whitespace (`nifbuilder`'s compact mode). The
    ## result parses identically — indentation is decoration — and is what a text
    ## NIF costs when it is treated as a cache rather than as something to read.
    # A module file takes 8-10 bytes per token, its index included (the index is
    # appended to the same string, so this reservation holds both).
    with var:
        bld = nifbuilder.open(sizeHint if sizeHint > 0 else len(b) * 10, compact)
    with let:
        patchPos = bld.addHeader27()
    with var:
        c = b.beginRead()
    with var:
        cur = NoNifLineInfo.copy()
    with var:
        parents = seq[NifLineInfo]([NoNifLineInfo])
    with var:
        index = nifbuilder.open(len(b) // 2)
    index.addTree(string(".index"))
    with let:
        rootInfo = rawLineInfo(c)
    if rootInfo.isValid():
        _emitRelLineInfo(index, rootInfo, NoNifLineInfo, b.pool)
    with var:
        mostRecentOffset = nint(0)
    with var:
        previousOffset = nint(0)
    while hasMore(c):
        _emitValueIndexed(bld, c, cur, parents, b.tags, b.pool, index, dottedSuffix,
                          mostRecentOffset, previousOffset, rootInfo)
    bld.patchIndexAt(patchPos, bld.offset())
    result = bld.extract()
    index.endTree()
    result.add(index.extract())
    return result


if comptime(__name__ == "__main__"):
    from nimic.std.syncio import *
    from nimic.std.strutils import *

    def _sameTokens(a: mut @ TokenBuf, b: mut @ TokenBuf) -> bool:
        if len(a) != len(b): return False
        for i in range(len(a)):
            if not (a[i] == b[i]): return False
        return True

    def _roundTrips(b1: mut @ TokenBuf) -> bool:
        ## parse → toString → parse must be byte-identical (idempotent).
        with let:
            txt = toString(b1)
        with var:
            b2 = parseFromBuffer(txt, string("t"))
        result = _sameTokens(b1, b2)
        if not result: echo(string("round-trip MISMATCH:\n"), txt)
        return result

    # In a proc, not at module level: host Nim rejects the `{.nifWrap.}` statement of `into` expanded at
    # module level ("custom pragmas are not supported for modules"), as in nifcore's self-test.
    def _selfTest():
        with block("samples"):
            for s in array[4, string]([
                    string("(stmts (call foo 42 \"hi\") (asgn x 3.14) (ret -7))"),
                    string("(proc :myproc.0 . . (params (param x.1 (i +32))) (i +32) (stmts (ret 0)))"),
                    string("(x \"longer than three bytes\" 'a' +18446744073709551615u -9223372036854775808)"),
                    string("(nested (a (b (c (d .)))))")]):
                with var:
                    b1 = parseFromBuffer(s, string("t"))
                doAssert(_roundTrips(b1), s)

        with block("overflow_jump"):
            # subtree larger than the 19-bit jump → ExtendedSuffix splice, then text round-trip
            with var:
                b1 = createTokenBuf(nint(InlineJumpCap) + 16)
            with let:
                t = b1.tags.registerTag(string("big"))
            b1.openTag(t)
            for i in range(nint(InlineJumpCap) + 5): b1.addIntLit(int64(i & 7))
            b1.closeTag()
            doAssert(_roundTrips(b1))

        with block("line_info"):
            # build a tree carrying line info, then text round-trip (file/line/col survive)
            with var:
                b1 = createTokenBuf(16)
            with let:
                t = b1.tags.registerTag(string("stmts"))
            with let:
                f = b1.pool.filenames.getOrIncl(string("test.nim"))
            b1.openTag(t);            b1.appendLineInfo(f, i32(1), i32(1))
            b1.addIdent(string("a"));         b1.appendLineInfo(f, i32(2), i32(3))
            b1.addIntLit(99);         b1.appendLineInfo(f, i32(2), i32(5))   # same line, new col
            b1.addStrLit(string("z"));        b1.appendLineInfo(f, i32(40000), i32(9))  # wide layout
            b1.closeTag()
            doAssert(_roundTrips(b1))

        with block("escape_space"):
            # An adapter whose vocabulary outgrew the 9-bit tag field. `registerTag`
            # just keeps counting; the ids past `TagMask` cost a second token and
            # nothing else. The escape must be invisible in BOTH directions — the text
            # never says `other`, and parsing that text back yields the same tokens.
            def escTags() -> TagPool:
                result = newTagPool()
                result.escapeTag = result.registerTag(string("other"))
                _ = result.registerTag(string("stmts"))
                _ = result.registerTag(string("mov"))
                # Pad the pool out to the edge of the tag field, so the next two
                # spellings genuinely do not fit and take the escape.
                while uint32(len(result.tags)) < TagMask: _ = result.registerTag(string("pad") + str(len(result.tags)))
                doAssert(uint32(result.registerTag(string("movzx"))) == FirstEscapeId)
                doAssert(uint32(result.registerTag(string("syscall"))) == FirstEscapeId + u32(1))
                return result

            with let:
                src = string("(stmts (mov (rax) +1) (movzx (rax) (rbx) +8) (syscall))")
            with var:
                b1 = parseFromBuffer(src, string("t"), sharedTags=escTags())
            # In the BUFFER the two overflowing tags are escape headers carrying their
            # id inline; `mov` is untouched, so a tag that fits still costs one token.
            with var:
                c = b1.beginRead()
            with var:
                seen = 0
            with c.into():
                while hasMore(c):
                    if isEscapedTag(c):
                        doAssert(uint32(resolvedTagId(c)) >= FirstEscapeId)
                        seen += 1
                    else:
                        doAssert(uint32(resolvedTagId(c)) == uint32(cursorTagId(c)))
                    skip(c)
            doAssert(seen == 2, string("expected two escaped nodes, got ") + str(seen))
            with let:
                txt = toString(b1)
            doAssert(txt.find(string("other")) < 0, txt)
            doAssert(txt.find(string("movzx")) >= 0 and txt.find(string("syscall")) >= 0, txt)
            with var:
                b2 = parseFromBuffer(txt, string("t"), sharedTags=escTags())
            doAssert(_sameTokens(b1, b2), txt)
            # The escape survives the indexed (full-module) serializer too.
            with var:
                b3 = parseFromBuffer(toModuleString(b1), string("t"), sharedTags=escTags())
            doAssert(_sameTokens(b1, b3))

    _selfTest()

    echo(string("nifcoreparse self-tests passed"))

if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir", "removeFile")

    def _showTree(title: string, b: mut @ TokenBuf):
        """`b` as text with and without line info, its token count and whether it round-trips."""
        echo(title, string(": "), len(b), string(" tokens, round trip "), _roundTrips(b))
        echo(toString(b))
        echo(toString(b, includeLineInfo=False))

    def _showValues(b: mut @ TokenBuf):
        """Every child of the top-level node, through `toString` of a cursor."""
        with var:
            c = b.beginRead()
        with c.into():
            while hasMore(c):
                echo(string("  "), kind(c), string(" "), toString(c), string(" | "), toString(c, includeLineInfo=False))
                skip(c)
        echo(string("  after the last value: ["), toString(c), string("]"))

    def _addedTests():
        # every atom kind, nesting, escapes, line info (absolute with an escaped filename, relative, negative,
        # base62, an empty column or line) and comments
        with var:
            b1 = parseFromBuffer(string(
                "(stmts@1,2,a\\2Eb.nim (call@2,1 foo.1. 42 -7 +3 18446744073709551615u 0u 3.25 -0.0 \"hi\\0A\\22x\\20\" 'c' '\\0A'"
                " ident . :def.3. x.1~5,~7 y.2@Z,a z.3@,5 w.4@3,,f.nim) (ret@3,4,other.nim -9223372036854775808#note#)"
                " (nested (a (b (c@1,1 (d .#a\\23b#))))))"), string("t"))
        _showTree(string("atoms"), b1)
        _showValues(b1)

        # split symbols: interned components, two dedup keys, a non-numeric disambiguator, short spellings
        with var:
            b2 = parseFromBuffer(string(
                "(s abc.12.Ikey.mod foo.0.Ia.Ib.mod p.0h107 _exit.sys.m :longname.33.modname longername.4."
                " x.1 :y.2. :q.7.Ik.)"), string("thismod"))
        _showTree(string("symbols"), b2)
        _showValues(b2)

        # a bare top-level atom is a tree of its own; the second one is not read
        with var:
            b3 = parseFromBuffer(string("5 (a)"), string("t"))
        _showTree(string("bare atom"), b3)

        # the `.unusedname` overload, positional and with keywords
        with let:
            modText = string("(.nif27)\n(.unusedname tmp.9.)\n(stmts@1,1,m.nim (a@2,1 x) (b y))")
        with var:
            unused = string("")
        with var:
            b4 = parseFromBuffer(modText, string("Mod"), unused)
        echo(string("unusedName: "), unused)
        _showTree(string("with unusedName"), b4)
        unused = string("")
        with var:
            b5 = parseFromBuffer(modText, string("Mod"), unused, sizeHint=4, denseLineInfo=True)
        echo(string("unusedName (keywords): "), unused)
        _showTree(string("with unusedName, dense"), b5)
        with var:
            b6 = parseFromBuffer(modText, string("Mod"), sizeHint=4)
        _showTree(string("without unusedName"), b6)

        # denseLineInfo off and on: children without their own line info inherit the head's
        with let:
            denseText = string("(a@1,1,f.nim b c (d e@2,0 f) g)")
        with var:
            sparse = parseFromBuffer(denseText, string("t"))
        with var:
            dense = parseFromBuffer(denseText, string("t"), denseLineInfo=True)
        _showTree(string("sparse"), sparse)
        _showTree(string("dense"), dense)

        # shared pools: the second buffer reuses the first one's strings, filenames and tags
        with var:
            shared = parseFromBuffer(denseText, string("t"), sharedPool=sparse.pool, sharedTags=sparse.tags)
        echo(string("shared pools: "), shared.pool == sparse.pool, string(" "), shared.tags == sparse.tags,
             string(" filenames "), len(sparse.pool.filenames), string(" tags "), len(sparse.tags.tags))

        # parseFromFile, both overloads; the module suffix comes from the file name
        with let:
            path = getTempDir() + string("nimic_nifcoreparse_test.nif")
        writeFile(path, modText)
        with var:
            f1 = parseFromFile(path)
        _showTree(string("file"), f1)
        unused = string("")
        with var:
            f2 = parseFromFile(path, unused)
        echo(string("file unusedName: "), unused)
        _showTree(string("file with unusedName"), f2)
        with var:
            f3 = parseFromFile(path, sizeHint=2, denseLineInfo=True)
        _showTree(string("file, dense"), f3)
        removeFile(path)

        # peekRootInfo does not consume the token, and seeds `parse` for a jump into the module
        with var:
            pr = createTokenBuf()
        with var:
            r = rd.openFromBuffer(modText.copy(), string("Mod"))
        with let:
            before = rd.offset(r)
        with let:
            root = peekRootInfo(r, pr.pool)
        echo(string("root: "), pr.pool.filenames[root.file], string(" "), root.line, string(","), root.col,
             string(" offset unchanged "), rd.offset(r) == before)
        rd.jumpTo(r, modText.find(string("(b y)")))
        parse(r, pr, parentSeed=root)
        _showTree(string("seeded"), pr)
        with var:
            noFile = rd.openFromBuffer(string("(x@1,1 y)"), string("t"))
        with let:
            none = peekRootInfo(noFile, pr.pool)
        echo(string("root without a file: valid "), none.isValid(), string(", same as NoNifLineInfo "),
             none == NoNifLineInfo)
        # a seed with a file resolves the relative positions of a file-less text
        with var:
            seeded = createTokenBuf()
        with let:
            sf = seeded.pool.filenames.getOrIncl(string("seed.nim"))
        with var:
            sr = rd.openFromBuffer(string("(x@2,3 y@1,1 (z w@~1,~2))"), string("t"))
        parse(sr, seeded, parentSeed=NifLineInfo(file=sf, line=i32(10), col=i32(20)))
        _showTree(string("seed with a file"), seeded)

        # floats through toString: the non-finite ones are compounds that carry the line info on their tag
        with var:
            fl = createTokenBuf()
        with let:
            ff = fl.pool.filenames.getOrIncl(string("float.nim"))
        fl.openTag(fl.tags.registerTag(string("floats"))); fl.appendLineInfo(ff, i32(1), i32(1))
        fl.addFloatLit(Inf); fl.appendLineInfo(ff, i32(2), i32(3))
        fl.addFloatLit(NaN); fl.appendLineInfo(ff, i32(2), i32(4))
        fl.addFloatLit(-Inf); fl.appendLineInfo(ff, i32(3), i32(1))
        fl.addFloatLit(-0.0)
        fl.addFloatLit(0.1); fl.appendLineInfo(ff, i32(4), i32(1))
        fl.addFloatLit(5e-324)
        fl.closeTag()
        echo(string("floats: "), len(fl), string(" tokens"))
        echo(toString(fl))
        echo(toString(fl, includeLineInfo=False))
        with let:
            flText = toString(fl)
        with var:
            fl2 = parseFromBuffer(flText, string("t"))
        echo(string("floats parsed back: "), toString(fl2))
        _showValues(fl)

        # appendTo a builder of our own
        with var:
            bld = nifbuilder.open(8)
        b1.appendTo(bld, includeLineInfo=False)
        bld.addRaw(string("\n"))
        appendTo(dense, bld)
        echo(string("appendTo: "), bld.extract())

        # toModuleString: the header with `.indexat`, the body and the index of the global symbol definitions
        with let:
            src = string(
                "(stmts@1,1,m.nim (proc@2,1 :foo.0.m . (params) (stmts (call bar.1.m 1.5)))"
                " (proc@1,5 :bar.1.m x (params)) (var@1,7,other.nim :local.2 . .) (const@1,9 :c.3.m . 'z'#doc#))")
        with var:
            mb = parseFromBuffer(src, string("m"))
        with let:
            ms1 = toModuleString(mb)
        echo(string("module:\n"), ms1)
        with let:
            ms2 = toModuleString(mb, string(".m"))
        echo(string("module, dottedSuffix:\n"), ms2)
        with let:
            ms3 = toModuleString(mb, dottedSuffix=string(".m"), compact=True)
        echo(string("module, compact:\n"), ms3)
        with let:
            ms4 = toModuleString(mb, sizeHint=16)
        echo(string("module, sizeHint: same "), ms4 == ms1)
        # the module text parses back to the same tokens, with and without the dotted suffix
        with var:
            back1 = parseFromBuffer(ms1, string("m"))
        with var:
            back2 = parseFromBuffer(ms2, string("m"))
        with var:
            back3 = parseFromBuffer(ms3, string("m"))
        echo(string("module parsed back: "), _sameTokens(mb, back1), string(" "), _sameTokens(mb, back2),
             string(" "), _sameTokens(mb, back3))
        # the indexed form: each entry of the index gives a declaration's offset (delta-encoded) and the line
        # info its `parse` is seeded with, as an index lookup does
        with var:
            ir = rd.openFromBuffer(ms2.copy(), string("m"))
        echo(string("indexat "), rd.indexStartsAt(ir), string(": "), ms2.substr(rd.indexStartsAt(ir)))
        with var:
            idx = createTokenBuf()
        rd.jumpTo(ir, rd.indexStartsAt(ir))
        parse(ir, idx)
        with var:
            e = idx.beginRead()
        with var:
            offs = nint(0)
        with let:
            indexInfo = rawLineInfo(e)
        with e.into():
            while hasMore(e):
                with let:
                    entryTag = idx.tags.tags[cursorTagId(e)]
                # an entry without line info of its own inherits the index's
                with let:
                    seed = rawLineInfo(e) if rawLineInfo(e).isValid() else indexInfo
                with var:
                    name = string("")
                with e.into():
                    name = symName(e)
                    inc(e)
                    offs += nint(intVal(e))
                    inc(e)
                with var:
                    decl = createTokenBuf(sharedPool=idx.pool)
                rd.jumpTo(ir, offs)
                parse(ir, decl, parentSeed=seed)
                echo(string("index "), entryTag, string(" "), name, string(" at "), offs, string(": "),
                     toString(decl, includeLineInfo=False))
                echo(toString(decl))

    _addedTests()
