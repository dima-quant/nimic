# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/foreignmodules.nim
# ///
#
#           Shared foreign-module loader for the nifcore backends
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this distribution.
#

## Lazy, on-demand loader for foreign NIF modules over the **nifcore** API — the
## single mechanism shared across backends (lengc's C/LLVM codegen as well as
## the nativenif tools: arkham codegen, nifasm assembler/linker) so the whole
## pipeline resolves cross-module symbols the same way.
##
## Originally `nativenif/src/common/nifmodules.nim`; promoted here so nimony's
## lengc and the nativenif tools share one implementation (the nativenif tools
## already reach into `nimony/src/lib` for `nifcore`/`nifreader` — they now do
## so for this too).
##
## Every NIF module carries an embedded `.indexat`/`.index` (hexer output;
## `nimony/tools/reindex.nim` ensures even hand-written fixtures have one). We
## keep the module's `Reader` open and parse just the *one* requested
## declaration by `jumpTo`-ing its indexed byte offset — O(1) per symbol, so a
## 400 KB module is never parsed whole. The per-decl buffers are owned by the
## `ForeignModule` so the cursors into them stay valid for its lifetime.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.tables import *
from .nifcore import *
from .nifcoreparse import *
from .nifreader import *
from . import nifreader
from .stringviews import *
from .bif import *
from . import bif


@ref
class ForeignModule(Object):
    r: Reader                           ## open reader (lazy per-symbol jumps)
    index: Table[string, nint]          ## symbol → absolute byte offset (text)
                                        ## or token position (bif)
    decls: Table[string, Cursor]        ## parsed-decl cache
    declBufs: seq[TokenBuf]             ## per-decl buffers, kept alive
    hasEmbeddedIndex: bool              ## false → the file carried no `.indexat`
    _rootOffset: nint                   ## text only: byte offset of the toplevel
                                        ## `(stmts)` head, for `withLineInfo`
    isBif: bool                         ## binary module: decls come from `bifBuf`
    bifBuf: TokenBuf                    ## bif only: the whole module, resident
                                        ## (zero-copy mmap; its own fresh pools)

    def hasDecl(m: ForeignModule, name: string) -> bool:
        return m.decls.hasKey(name) or m.index.hasKey(name)

    def getDecl(m: ForeignModule, name: string, tags: TagPool, pool: Pool = None,
                withLineInfo=False) -> Cursor:
        ## The declaration cursor for `name` (precondition: `hasDecl`). `jumpTo`s the
        ## symbol's byte offset and parses just that one tree into its own buffer
        ## (kept alive in `declBufs`). Cached.
        ##
        ## `withLineInfo`: for consumers that COPY the decl's line info into their own
        ## output (the inter-module inliner splices foreign bodies). A decl's first
        ## token holds only a position delta against its parent, the module's
        ## toplevel `(stmts)`, so the parse is seeded with that root's absolute info
        ## (`peekRootInfo`) — the same seeding `programs.tryLoadSym` does — and the
        ## info is stored densely, as a whole-file `parseFromFile` would have it.
        ##
        ## `pool`: pass `nil` (the default) to intern the decl's symbols in a fresh
        ## per-decl pool — fine for **string-keyed** consumers (arkham/nifasm compare
        ## symbols by name). Pass the *caller's shared pool* for **SymId-keyed**
        ## consumers (lengc keys `defs`/scopes by `SymId`, so foreign decls must intern
        ## into the same pool or their ids won't line up with the main module's).
        # `[]` is `.raises` (KeyError) under Nimony; `getOrQuit` is the non-raising
        # accessor for the keys the precondition already guarantees are present.
        if m.decls.hasKey(name): return getOrQuit(m.decls, name)
        with let:
            pos = getOrQuit(m.index, name)
        with var:
            buf = createTokenBuf(64, pool, tags)
        if m.isBif:
            # The decl subtree is already resident; `addSubtree` re-interns literals,
            # tag names and line-info filenames across pools (the bif buffer keeps its
            # own fresh pools), so the copy lands in the caller's `tags`/`pool` world.
            buf.addSubtree(cursorAt(m.bifBuf, pos))
        else:
            if withLineInfo:
                m.r.jumpTo(m._rootOffset)
                with let:
                    seed = peekRootInfo(m.r, buf.pool)
                m.r.jumpTo(pos)
                parse(m.r, buf, parentSeed=seed, denseLineInfo=True)
            else:
                m.r.jumpTo(pos)
                parse(m.r, buf)                         # exactly one balanced decl tree
        # Take the cursor on the LOCAL buffer *before* moving it into `declBufs`
        # (the leng/nimony pattern, see nifmodules.getDeclOrNil): `beginRead` installs
        # the buffer's ref-counted cursor owner, which then travels with the buffer
        # when `declBufs` later grows and relocates its elements. Doing `beginRead` on
        # the already-stored seq element instead corrupts the heap once a second decl
        # forces the seq to reallocate.
        result = beginRead(buf)
        m.declBufs.add(ensureMove(buf))
        m.decls[name] = result
        return result


def readEmbeddedIndex(r: mut @ Reader) -> Table[string, nint]:
    ## Read the embedded `(.index (h sym Δoff) (x sym Δoff) …)` section located by
    ## the `.indexat` directive, returning `symbol → absolute byte offset`. Offsets
    ## are stored delta-encoded (cumulative); `h`=hidden, `x`=exported (we keep
    ## both). Mirrors `nifindexes.readEmbeddedIndex`, but over the nifcore reader.
    result = initTable[string, nint]()
    with let:
        indexPos = indexStartsAt(r)
    if indexPos <= 0: return result
    r.jumpTo(indexPos)
    with var:
        prev = nint(0)
    with var:
        t = default(ExpandedToken)
    next(r, t)                                  # `(.index`
    if not (t.tk == NifKind.ParLe and t.data == ".index"): return result
    next(r, t)
    while t.tk != NifKind.EofToken and t.tk != NifKind.ParRi:
        if t.tk == NifKind.ParLe:                         # entry: `(h sym Δoff)` / `(x sym Δoff)`
            next(r, t)                              # the symbol
            with var:
                key = string("")
            if t.tk == NifKind.Symbol: key = decodeStr(r, t)
            next(r, t)                              # the (delta) offset
            if t.tk == NifKind.IntLit:
                with let:
                    off = nint(decodeInt(t)) + prev
                if key.len > 0: result[key] = off
                prev = off
            next(r, t)                              # closing `)`
            if t.tk == NifKind.ParRi: next(r, t)
        else:
            next(r, t)
    return result


def openForeignModule(path: string) -> ForeignModule:
    ## Open a module file: read its directives, locate the embedded `.indexat`
    ## index, and keep the reader open for lazy per-symbol jumps. The returned
    ## module's `hasEmbeddedIndex` is false when the file carried no index — the
    ## caller decides how to report that (lengc/arkham/nifasm phrase the error).
    ## The file header is sniffed: a binary `.bif` (still named `.nif` in the
    ## pipeline) is loaded whole (zero-copy mmap) and its embedded index — token
    ## positions instead of byte offsets — fills `index` under the same key type.
    if isBifFile(path):
        result = ForeignModule(isBif=True,
                               index=initTable[string, nint](),
                               decls=initTable[string, Cursor](),
                               hasEmbeddedIndex=True)  # a bif always carries one
        with var:
            bm = bif.load(path)
        for e in bm.index:
            result.index[symString(bm.buf.pool, e.sym)] = nint(e.pos)
        result.bifBuf = ensureMove(bm.buf)
    else:
        result = ForeignModule(r=nifreader.open(path),
                               index=initTable[string, nint](),
                               decls=initTable[string, Cursor]())
        # `open` has consumed the directives: the reader now sits on the root.
        result._rootOffset = offset(result.r)
        if indexStartsAt(result.r) > 0:
            result.hasEmbeddedIndex = True
            result.index = readEmbeddedIndex(result.r)
    return result


if comptime(__name__ == "__main__"):
    from nimic.std.os import *
    from nimic.std.syncio import *
    from nimic.std.algorithm import *
    from nimic.std.strutils import *

    def _sortedKeys(t: Table[string, nint]) -> seq[string]:
        result = seq[string]()
        for k in t.keys():
            result.add(k)
        sort(result)
        return result

    def _firstInfo(c: Cursor) -> string:
        with let:
            info = rawLineInfo(c)
        result = lineInfoFile(c) + string(":") + str(info.line) + string(",") + str(info.col)
        return result

    def _showModule(label: string, m: ForeignModule):
        echo(label, string(": isBif="), m.isBif, string(" hasEmbeddedIndex="), m.hasEmbeddedIndex,
             string(" entries="), m.index.len)
        for k in _sortedKeys(m.index):
            echo(string("  "), k)

    def _addedTests():
        with let:
            dir = getTempDir()
            textFile = dir + string("nimic_foreignmodules_m.s.nif")
            bifFile = dir + string("nimic_foreignmodules_m.bif")
            plainFile = dir + string("nimic_foreignmodules_plain.s.nif")
        # a module of many decls, so that `declBufs` grows several times
        with var:
            src = string("(stmts@1,1,m.nim")
        for i in range(24):
            src.add(string(" (proc@0,") + str(i + 2) + string(" :p") + str(i + 10) + string(".0.m x . . (params) . . . (stmts")
                    + string(" (call@2,1 q.1.m ") + str(i) + string(" \"s") + str(i) + string("\")))"))
        src.add(string(" (type@0,30,inc.nim :T.0.m x . . (object .)) (var@0,31 :v.0.m . . (i +32) 5)"))
        src.add(string(" (const@0,32 :c.0.m . . . 'z') (let@0,33 :loc.0 . . . 1))"))
        with var:
            mb = parseFromBuffer(src, string("m"))
        writeFile(textFile, toModuleString(mb))
        bif.store(mb, bifFile)

        with var:
            tm = openForeignModule(textFile)
        with var:
            bm = openForeignModule(bifFile)
        _showModule(string("text"), tm)
        _showModule(string("bif"), bm)
        echo(string("same keys: "), _sortedKeys(tm.index) == _sortedKeys(bm.index))

        # hasDecl
        echo(string("hasDecl p10: "), tm.hasDecl(string("p10.0.m")), string(" "), bm.hasDecl(string("p10.0.m")))
        echo(string("hasDecl missing: "), tm.hasDecl(string("nope.0.m")), string(" "), bm.hasDecl(string("nope.0.m")))
        echo(string("hasDecl local: "), tm.hasDecl(string("loc.0")), string(" "), bm.hasDecl(string("loc.0")))

        # getDecl of every symbol: the same tree from the text and the bif module
        with let:
            tags = newTagPool()
        with var:
            first = seq[string]()
        for k in _sortedKeys(tm.index):
            with let:
                ts = toString(tm.getDecl(k, tags), includeLineInfo=False)
                bs = toString(bm.getDecl(k, tags), includeLineInfo=False)
            echo(k, string(": "), ts)
            if ts != bs: echo(string("  MISMATCH bif: "), bs)
            echo(string("  text info: "), toString(tm.getDecl(k, tags)))
            echo(string("  bif info:  "), toString(bm.getDecl(k, tags)))
            first.add(ts)
        echo(string("declBufs: "), tm.declBufs.len, string(" "), bm.declBufs.len)
        # cached: every cursor read again after `declBufs` grew, no new buffer
        with var:
            same = True
        with var:
            i = 0
        for k in _sortedKeys(tm.index):
            if toString(tm.getDecl(k, tags), includeLineInfo=False) != first[i]: same = False
            if toString(bm.getDecl(k, tags), includeLineInfo=False) != first[i]: same = False
            i += 1
        echo(string("cached same: "), same, string(" declBufs: "), tm.declBufs.len, string(" "), bm.declBufs.len)

        # withLineInfo: the decl's first token, with and without the root's seed
        with var:
            plainM = openForeignModule(textFile)
        with var:
            infoM = openForeignModule(textFile)
        for k in [string("p10.0.m"), string("p33.0.m"), string("T.0.m"), string("c.0.m")]:
            echo(k, string(" withLineInfo=false "), _firstInfo(plainM.getDecl(k, tags)),
                 string(" withLineInfo=true "), _firstInfo(infoM.getDecl(k, tags, withLineInfo=True)))
        echo(string("dense: "), toString(infoM.getDecl(string("p11.0.m"), tags)))

        # pool: nil (a fresh pool per decl) vs the caller's shared pool
        with let:
            shared = newPool()
        _ = symId(shared, string("dummy.0.x"))
        _ = symId(shared, string("dummy.1.x"))
        for path in [textFile, bifFile]:
            with var:
                fresh = openForeignModule(path)
            with var:
                pooled = openForeignModule(path)
            with var:
                a = fresh.getDecl(string("p12.0.m"), tags).copy()
            with var:
                b = pooled.getDecl(string("p12.0.m"), tags, shared).copy()
            inc(a)
            inc(b)
            echo(string("pool nil: "), symName(a), string(" matches shared "), symId(a) == symId(shared, string("p12.0.m")),
                 string(" | shared pool: "), symName(b), string(" matches shared "), symId(b) == symId(shared, string("p12.0.m")))

        # a text file without `.indexat`
        writeFile(plainFile, string("(.nif27)\n(stmts (proc :a.0.m x . . (params) . . . (stmts)))\n"))
        with var:
            pm = openForeignModule(plainFile)
        echo(string("plain: hasEmbeddedIndex="), pm.hasEmbeddedIndex, string(" entries="), pm.index.len,
             string(" hasDecl a: "), pm.hasDecl(string("a.0.m")))

        # readEmbeddedIndex on a reader: the offsets are absolute (the deltas summed up) and increase in the
        # order of the decls, each one the start of its decl
        with var:
            r = nifreader.open(textFile)
        with var:
            tab = readEmbeddedIndex(r)
        echo(string("readEmbeddedIndex: "), tab.len, string(" == "), tm.index.len)
        with var:
            prev = 0
        with var:
            increasing = True
        for k in _sortedKeys(tab):
            if k.startsWith(string("p")):
                if getOrQuit(tab, k) <= prev: increasing = False
                prev = getOrQuit(tab, k)
            echo(string("  "), k, string(" offset="), getOrQuit(tab, k))
        echo(string("increasing: "), increasing)
        with var:
            one = createTokenBuf(16, None, tags)
        r.jumpTo(getOrQuit(tab, string("v.0.m")))
        parse(r, one)
        echo(string("at v.0.m: "), toString(one, includeLineInfo=False))
        r.close()

        removeFile(textFile)
        removeFile(bifFile)
        removeFile(plainFile)

    _addedTests()
