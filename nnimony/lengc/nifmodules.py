# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/nifmodules.nim
# ///
#
#
#        Lengc set-of-modules handling — nifcore port
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## NIF set-of-modules handling on the **nifcore** stack — the nifcore port of
## `lengc/nifmodules.nim`. Loads foreign declarations lazily, IC-style: a
## module's `.nif` file is opened once, its embedded index (`(.index (x sym
## offset) …)`) read, and each requested declaration materialized on demand by
## seeking the reader to the indexed offset and parsing exactly one subtree.
##
## Compared to the nifcursors original this is simpler: `nifcoreparse.parse`
## replaces the hand-rolled recursive token copier, and `nifstreams` drops out
## entirely — `nifreader.Reader` already provides `jumpTo`/`offset`, and the
## embedded index is read at the raw-token level with no pool involvement.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    # `TypeScope.parent` is a nilable linked list: the outermost scope has none.
    pragma("feature: \"lenientnils\"")

from nimic.std import assertions, syncio
from nimic.std.tables import initTable, Table
  # syncio: `quit`
importFrom("nimic.std.os", "fileExists")  # NOT a whole `os` import: it exports a
                                          # `FileId` that collides with nifcore's
from ..lib import nifcoreparse
from ..lib.nifcoreparse import (
    addSymDef, addSymUse, charLit, createTokenBuf, Cursor, cursorTagId, FileId, floatVal, getOrIncl, intVal,
    kind, NifKind, NifLineInfo, NoNifLineInfo, Pool, pool, registerTag, StrId, strVal, SymId, symId, symName,
    TagId, TagPool, TokenBuf, uintVal)
from ..lib.nifcdecl import (
    asTypeDecl, createLengTagPool, inc, into, LengOther, LengPragma, LengStmt, LengSym, pragmaKind, skip,
    stmtKind, substructureKind, symKind)  # stmtKind/symKind/pragmaKind, decls
from ..lib import nifreader as rd  # Reader, jumpTo, indexStartsAt
from ..lib.symparser import splitModulePath, SplittedModulePath  # splitModulePath
from ..lib.foreignmodules import ForeignModule, openForeignModule  # shared lazy loader (ForeignModule)
from ..lib import bif
from ..lib.bif import getOrQuit, isBifFile  # binary NIF: isBifFile probe + load
from .noptions import ConfigRef  # ConfigRef
from ..lib.nifcore import addIdent, addStrLit  # re-exports nifcore + parse


class Definition(Object):
    pos: Cursor  ## points into the owning ForeignModule's decl buffer
    kind: LengSym
    extern: StrId  ## importc/exportc name, cached (frequently queried)
    isImport: bool  ## true for importc/importcpp, false for exportc-only
    bareImport: bool  ## `importc` with neither `header` nor `nodecl`: the
                      ## C backend declares it itself, under its MANGLED
                      ## name with an `__asm__` label, so the declaration
                      ## can never collide with a header prototype for the
                      ## same libc identifier in the same TU (splices move
                      ## such references into arbitrary modules)


class _NifProgram(Object):
    _mods: Table[string, ForeignModule]  ## module suffix -> lazily-opened module
    _scheme: SplittedModulePath


@ref
class TypeScope(Object):
    """{.acyclic.}"""
    locals: Table[SymId, Cursor]
    parent: TypeScope


class MainModule(Object):
    src: TokenBuf
    pool: Pool
    tags: TagPool
    types: seq[Cursor]  ## points into MainModule.src
    filename: string
    config: ConfigRef
    builtinTypes: Table[string, Cursor]
    current: TypeScope
    _defs: Table[SymId, Definition]
    _typeBodyToDecl: Table[nint, Cursor]  ## body `toUniqueId` -> its `(type …)` decl
    _prog: _NifProgram
    requestedForeignSyms: seq[Cursor]

    def _loadForeign(c: mut @ MainModule, s: SymId) -> Cursor:
        ## Resolve a foreign symbol's declaration through the shared `ForeignModule`
        ## lazy loader: open (and cache) the owning module, then jump to the symbol's
        ## indexed offset and parse just that one decl. The cursor stays valid because
        ## the `ForeignModule` owns the per-decl buffer.
        with let:
            module = c.pool.symModule(s)
        if module == "":
            raiseAssert(string("Cannot lookup declaration without module name: ") + c.pool.symString(s))
        with var:
            m = ForeignModule()
        if c._prog._mods.hasKey(module):
            m = getOrQuit(c._prog._mods, module)
        else:
            c._prog._scheme.name = module
            m = openForeignModule(str(c._prog._scheme))
            c._prog._mods[module] = m
        with let:
            key = c.pool.symString(s)
        if not m.hasDecl(key):
            raiseAssert(string("Symbol not found in NIF module: ") + key)
        result = m.getDecl(key, c.tags, c.pool)  # share the main module's pool (SymId-keyed)
        return result

    def _registerTypeBody(c: mut @ MainModule, declPos: Cursor):
        ## Map a `(type …)` decl's body position to the decl, so `tracebackTypeC` can
        ## recover the decl from a body cursor without walking the buffer backwards.
        c._typeBodyToDecl[asTypeDecl(declPos).body.toUniqueId()] = declPos

    def tracebackTypeC(c: mut @ MainModule, n: Cursor) -> Cursor:
        ## The nifcore replacement for the nifcursors backward walk: given a type
        ## *body* cursor, return its enclosing `(type …)` declaration. Returns
        ## `default(Cursor)` for an unregistered body (e.g. an anonymous inline type).
        return c._typeBodyToDecl.getOrDefault(n.toUniqueId(), default(Cursor))

    def canLoadForeign(c: mut @ MainModule, s: SymId) -> bool:
        ## True when `getDeclOrNil` would find a declaration for `s` — i.e. the owning
        ## module's file exists AND its embedded index names `s`. `getDeclOrNil`
        ## *asserts* on either failure, which is right for a consumer that needs the
        ## declaration to proceed; a consumer that is merely ASKING (an optimizer
        ## looking for a function summary) needs "no" to be an answer. Warms the
        ## module cache, so a following `getDeclOrNil` costs one table hit.
        if c._defs.hasKey(s): return True
        with let:
            module = c.pool.symModule(s)
        if module == "": return False
        with var:
            m = ForeignModule()
        if c._prog._mods.hasKey(module):
            m = getOrQuit(c._prog._mods, module)
        else:
            c._prog._scheme.name = module
            if not fileExists(str(c._prog._scheme)): return False
            m = openForeignModule(str(c._prog._scheme))
            c._prog._mods[module] = m
        result = m.hasDecl(c.pool.symString(s))
        return result

    def getExtern(c: mut @ MainModule, s: SymId) -> StrId:
        with let:
            d = getDeclOrNil(c, s)
        result = d.extern if not isNil(d) else StrId(0)
        return result

    def registerLocal(c: mut @ MainModule, s: SymId, typ: Cursor):
        c.current.locals[s] = typ

    def openScope(c: mut @ MainModule):
        c.current = TypeScope(locals=initTable[SymId, Cursor](), parent=c.current)

    def closeScope(c: mut @ MainModule):
        c.current = c.current.parent


def _firstChild(c: Cursor) -> Cursor:
    """{.inline.}"""
    result = c.copy()
    result.inc()
    return result


def externName(s: SymId, n: Cursor) -> StrId:
    ## Extract the importc/exportc name from a pragma node `n` (or fall back to the
    ## symbol's basename). Pool-free: uses the cursor's own buffer pool.
    with let:
        nn = _firstChild(n)
        p = pool(n)
    if kind(nn) == NifKind.StrLit:
        result = getOrIncl(p.strings, strVal(nn, p))
    else:
        result = p.symNameId(s)
    return result


def _extractExtern(c: mut @ MainModule, n: mut @ Cursor, pragmasAt: nint, isImport: mut @ bool, bareImport: mut @ bool) -> StrId:
    result = StrId(0)
    isImport <<= False
    bareImport <<= False
    with var:
        sawImportC = False
        sawHeaderish = False
    with into(n):  # enter the toplevel (type/proc/var/…)
        if kind(n) != NifKind.SymbolDef:
            raiseAssert(string("Expected SymbolDef after toplevel declaration"))
        with let:
            symId = nifcoreparse.symId(n)
        n.inc()
        for i in range(1, pragmasAt): skip(n)
        if substructureKind(n) == LengOther.PragmasU:
            with into(n):
                while n.hasMore():
                    with let:
                        pk = pragmaKind(n)
                    if pk in Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP, LengPragma.ExportcP):
                        result = externName(symId, n)
                        if pk in Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP):
                            isImport <<= True
                        if pk == LengPragma.ImportcP:
                            sawImportC = True
                    elif pk in Tset[LengPragma](LengPragma.HeaderP, LengPragma.NodeclP):
                        sawHeaderish = True
                    skip(n)
        elif kind(n) == NifKind.DotToken:
            _ = "ok"
        else:
            raiseAssert(string("pragmas not at the correct position"))
        while n.hasMore():
            skip(n)
    bareImport <<= sawImportC and not sawHeaderish
    return result


def getDeclOrNil(c: mut @ MainModule, s: SymId) -> ptr[Definition]:
    if not c._defs.hasKey(s):
        if c.pool.symIsLocal(s): return None
        with let:
            pos = c._loadForeign(s)
        if kind(_firstChild(pos)) == NifKind.SymbolDef:
            with let:
                sk = symKind(pos)
            with var:
                extern = StrId(0)
                isImport = nbool(False)
                bareImport = nbool(False)
                n = pos.copy()
            match sk:
                case LengSym.TypeY:
                    c.types.add(pos)
                    c._registerTypeBody(pos)
                    extern = _extractExtern(c, n, 1, isImport, bareImport)
                case LengSym.ProcY:
                    extern = _extractExtern(c, n, 3, isImport, bareImport)
                case LengSym.VarY | LengSym.ConstY | LengSym.GvarY | LengSym.TvarY:
                    extern = _extractExtern(c, n, 1, isImport, bareImport)
                case _: pass
            c._defs[s] = Definition(pos=pos, kind=sk, extern=extern, isImport=isImport, bareImport=bareImport)
            c.requestedForeignSyms.add(pos)
        else:
            raiseAssert(string("Expected SymbolDef after toplevel declaration"))
    result = addr(getOrQuit(c._defs, s))
    return result

# ---- scopes ---------------------------------------------------------------

# ---- module loading -------------------------------------------------------


def _processToplevelDecl(c: mut @ MainModule, n: mut @ Cursor, kind: LengSym, pragmasAt: nint):
    with let:
        decl = n.copy()
        s = symId(_firstChild(decl))
    with var:
        isImport = nbool(False)
        bareImport = nbool(False)
    with let:
        extern = _extractExtern(c, n, pragmasAt, isImport, bareImport)
    c._defs[s] = Definition(pos=decl, kind=kind, extern=extern, isImport=isImport, bareImport=bareImport)


def _detectToplevelDecls(c: mut @ MainModule):
    with var:
        n = c.src.cursorAt(0)
    if kind(n) != NifKind.TagLit: return
    # the src buffer starts with a (stmts …) wrapper; walk its children.
    with into(n):
        while n.hasMore():
            if kind(n) == NifKind.TagLit:
                match stmtKind(n):
                    case LengStmt.TypeS:
                        c.types.add(n)
                        c._registerTypeBody(n)
                        _processToplevelDecl(c, n, LengSym.TypeY, 1)
                    case LengStmt.ProcS:
                        _processToplevelDecl(c, n, LengSym.ProcY, 3)
                    case _:
                        match symKind(n):
                            case LengSym.VarY | LengSym.ConstY | LengSym.GvarY | LengSym.TvarY:
                                _processToplevelDecl(c, n, symKind(n), 1)
                            case _:
                                skip(n)
            else:
                n.inc()


class _DensifyRemap(Object):
    ## Id translation for densifying a buffer whose pools differ from `dest`'s
    ## (the `.bif` load path: bif mints fresh pools — its INVARIANT — while the
    ## backends need the canonical Leng tag pool for `stmtKind` & co to decode).
    ## Inactive (empty `tagMap`) when source and dest share pools: densify's
    ## string-based re-adds (`strVal`/`symName` resolve against the *cursor's*
    ## pool) are already cross-pool safe; only the two raw ids — the `TagId`
    ## passed to `openTag` and the `FileId`/comment inside a `NifLineInfo` —
    ## need mapping.
    _tagMap: seq[TagId]  # source TagId -> dest TagId; 1-based, [0] unused
    _fileMap: seq[FileId]  # source FileId -> dest FileId; 1-based, [0] unused
    _srcPool: Pool  # for re-interning the rare line-info comment StrId


def _buildDensifyRemap(dest: mut @ TokenBuf, src: TokenBuf) -> _DensifyRemap:
    result = _DensifyRemap(_srcPool=src.pool)
    result._tagMap = newSeq[TagId](src.tags.tags.len + 1)
    for i in inrange(1, src.tags.tags.len):
        result._tagMap[i] = registerTag(dest.tags, src.tags.tags[TagId(i)])
    result._fileMap = newSeq[FileId](src.pool.filenames.len + 1)
    for i in inrange(1, src.pool.filenames.len):
        result._fileMap[i] = getOrIncl(dest.pool.filenames, src.pool.filenames[FileId(i)])
    return result


def _mapInfo(dest: mut @ TokenBuf, info: NifLineInfo, remap: _DensifyRemap) -> NifLineInfo:
    result = info.copy()
    if remap._tagMap.len > 0 and info.isValid():
        result.file = remap._fileMap[nint(info.file)]
        if result.comment != StrId(0):
            result.comment = getOrIncl(dest.pool.strings, remap._srcPool.strings[result.comment])
    return result


def _densify(dest: mut @ TokenBuf, n: mut @ Cursor, cur: mut @ NifLineInfo, remap: _DensifyRemap):
    ## Copy the tree at `n` into `dest`, stamping *every* head token with its
    ## effective line info. nifcore stores line info sparsely (only when it
    ## changes); the nifcursors world propagated it to every node, and the
    ## backends rely on `info(n)` being valid at each statement/expression (e.g.
    ## LLVM `!dbg` / C `#line`). Densifying once at load restores that invariant
    ## for all backends with no per-call-site changes. `cur` is the running
    ## sequential (depth-first) line info, matching how nifcursors propagated it —
    ## a node inherits the most recent info *in stream order*, not its parent's.
    with let:
        raw = n.rawLineInfo()
    if raw.isValid(): cur <<= raw
    with let:
        eff = _mapInfo(dest, cur, remap)
    match kind(n):
        case NifKind.TagLit:
            with var:
                tag = cursorTagId(n)
            if remap._tagMap.len > 0: tag = remap._tagMap[nint(tag)]
            dest.openTag(tag)
            if eff.isValid(): dest.appendLineInfo(eff)
            with into(n):
                while n.hasMore(): _densify(dest, n, cur, remap)
            dest.closeTag()
        case NifKind.DotToken:
            dest.addDotToken()
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.Ident:
            addIdent(dest, strVal(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.Symbol:
            addSymUse(dest, symName(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.SymbolDef:
            addSymDef(dest, symName(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.StrLit:
            addStrLit(dest, strVal(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.CharLit:
            dest.addCharLit(charLit(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.IntLit:
            dest.addIntLit(intVal(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.UIntLit:
            dest.addUIntLit(uintVal(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.FloatLit:
            dest.addFloatLit(floatVal(n))
            if eff.isValid(): dest.appendLineInfo(eff)
            n.inc()
        case NifKind.ExtendedSuffix | NifKind.LineInfoLit | NifKind.UnknownToken | NifKind.EofToken | NifKind.ParLe | NifKind.ParRi:
            n.inc()  # absorbed into the head token's own value/info; never freestanding


def load(filename: string, pool: Pool = None, tags: TagPool = None) -> MainModule:
    ## Load the main module, sniffing the file header for the actual format:
    ## filenames stay `.nif` throughout the pipeline, the content decides.
    ## Text is parsed with a canonical Leng tag pool so interned TagIds equal the
    ## master ordinals that `stmtKind`/`typeKind`/`symKind` decode against; a
    ## `.bif` is loaded zero-copy with its own fresh pools (the bif INVARIANT)
    ## and translated to the canonical pools during the densify copy below.
    ##
    ## `pool`/`tags`: intern into these instead of fresh ones, so the module's
    ## SymIds line up with buffers the caller already holds (shoggoth optimizes a
    ## buffer the inter-module inliner produced in nifpools' global pools). `tags`
    ## must be seeded by master ordinal, as `createLengTagPool` does.
    with let:
        fromBif = isBifFile(filename)
    with var:
        raw = default(TokenBuf)
    if fromBif:
        with var:
            bm = bif.load(filename)  # mmap; the index is not needed here, we rescan
        raw = ensureMove(bm.buf)
    else:
        with var:
            r = rd.open(filename)
        match rd.processDirectives(r):
            case rd.DirectivesResult.Success: pass
            case rd.DirectivesResult.WrongHeader: quit(string("nif files must start with Version directive"))
            case rd.DirectivesResult.WrongMeta: quit(string("the format of meta information is wrong!"))
        with let:
            nodeCount = rd.fileSize(r) // 7
        raw = createTokenBuf(nodeCount, pool, tags if tags is not None else createLengTagPool())
        nifcoreparse.parse(r, raw)
        rd.close(r)
    # Densify line info so `info(n)` is valid at every node (see `densify`). The
    # densified buffer shares `raw`'s pool/tags in the text case; in the bif case
    # it gets its own canonical pools and `DensifyRemap` translates the raw ids
    # (tags, line-info FileIds) — strings/symbols re-intern by value anyway.
    # `config` is a not-nil ref, so it has no default value and the constructor
    # owes it one: `codegen.generateCode` overwrites it with the driver's config
    # (`m.config = s.config`) before anything reads a field off it.
    result = MainModule(current=TypeScope(locals=initTable[SymId, Cursor]()), filename=filename, config=ConfigRef(), _prog=_NifProgram(_scheme=splitModulePath(filename)))
    with var:
        remap = default(_DensifyRemap)
    if fromBif:
        result.src = createTokenBuf(raw.len, pool, tags if tags is not None else createLengTagPool())
        remap = _buildDensifyRemap(result.src, raw)
    else:
        result.src = createTokenBuf(raw.len, raw.pool, raw.tags)
    with var:
        rc = raw.beginRead()
        curInfo = NoNifLineInfo.copy()
    _densify(result.src, rc, curInfo, remap)
    result.pool = result.src.pool
    result.tags = result.src.tags
    _detectToplevelDecls(result)
    return result
