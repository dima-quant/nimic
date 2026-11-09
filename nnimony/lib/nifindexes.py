# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lib/nifindexes.nim
# test-args: {tmp}/nifindexes_main.s.nif
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Create an index file for a NIF file.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.tables import initOrderedTable, OrderedTable, Table
from nimic.std import assertions
from nimic.std import hashes
from nimic.std import syncio
from nimic.std import strutils
from .bitabs import getOrIncl
from .nifreader import (
    close,
    decodeFilename,
    decodeInt,
    decodeStr,
    ExpandedToken,
    indexStartsAt,
    jumpTo,
    next,
    offset,
    Reader)
from . import nifreader
from .nifpools import (
    addDotToken, addIdent, addParLe, addParRi, addStrLit, addSymUse, createTokenBuf, Cursor,
    cursorTagId, globalTags, info, into, isDotToken, isIdent, isStringLit, isSymbol, isTagLit, isValid, loopInto,
    NifKind, NifLineInfo, NoLineInfo, NoNifLineInfo, parseFromBuffer, pool, skip, StrId, strId, SymId, symId,
    TagId, TokenBuf, toString, writeFile)  # writeFile: its set overloads syncio's
from .nifchecksums import updateLoop
from .symparser import changeModuleExt
from .vfs import vfsRead, vfsWrite
from . import stringviews  # its `add` is called as a method
importFrom(".lineinfos", "PackedLineInfo")  # only for NifIndexEntry.info (frozen Nim side)

if comptime(defined("nimony")):
    from nimic.std.sha1 import finalize, newSha1State, SecureHash, Sha1State, update
else:
    # See `nifchecksums.nim`: `std/sha1` is the portable choice that ships in
    # `lib/std` on every Nim 2.x (the `$nim/dist/checksums/...` path only exists in
    # a git/devel layout). Same SHA-1 fork → identical digests.
    with push("warning[Deprecated]: off"):
        from nimic.std.sha1 import finalize, newSha1State, SecureHash, Sha1State, update
from ..models.tags import TagEnum
from ..models.nifindex_tags import NifIndexKind, rawTagIsNifIndexKind

include("compat2")

importFrom(".nifcoreparse", "parse")


def _entryKind(tag: TagId) -> NifIndexKind:
    if rawTagIsNifIndexKind(cast[TagEnum](tag)):
        result = cast[NifIndexKind](tag)
    else:
        result = NifIndexKind.NoIndexTag
    return result


def _isImportant(s: string) -> bool:
    with var:
        c = nint(0)
    for ch in s:
        if ch == char('.'): c += 1
    result = c >= 2
    return result


def _processDeclForChecksum(dest: mut @ Sha1State, n: mut @ Cursor):
    ## Hashes the single tree/token at `n` — the declarations in it, to be
    ## exact — advancing past it. Private declarations count too: an importer
    ## instantiates an exported generic, or expands an exported template, whose
    ## body can name any of them.
    with let:
        inlineT = TagId(NifIndexKind.InlineIdx)
    if isTagLit(n):
        with var:
            foundInline = nbool(False)
        with let:
            k = _entryKind(cursorTagId(n))
        match k:
            case NifIndexKind.LetIdx | NifIndexKind.VarIdx | NifIndexKind.CursorIdx | NifIndexKind.ConstIdx | \
                    NifIndexKind.TypeIdx | NifIndexKind.GletIdx | NifIndexKind.TletIdx | NifIndexKind.GvarIdx | \
                    NifIndexKind.TvarIdx:
                with into(n):  # tag
                    updateLoop(dest, n, inlineT, foundInline)  # SymbolDef
                    updateLoop(dest, n, inlineT, foundInline)  # Export marker
                    updateLoop(dest, n, inlineT, foundInline)  # pragmas
                    updateLoop(dest, n, inlineT, foundInline)  # type
                    updateLoop(dest, n, inlineT, foundInline)  # value
                    while n.hasMore(): skip(n)
            case NifIndexKind.TemplateIdx | NifIndexKind.MacroIdx | NifIndexKind.IteratorIdx:
                # these always have inline semantics
                with into(n):  # tag
                    updateLoop(dest, n, inlineT, foundInline)  # SymbolDef
                    updateLoop(dest, n, inlineT, foundInline)  # Export marker
                    updateLoop(dest, n, inlineT, foundInline)  # pattern
                    updateLoop(dest, n, inlineT, foundInline)  # typevars
                    updateLoop(dest, n, inlineT, foundInline)  # params
                    updateLoop(dest, n, inlineT, foundInline)  # retType
                    updateLoop(dest, n, inlineT, foundInline)  # pragmas
                    updateLoop(dest, n, inlineT, foundInline)  # effects
                    updateLoop(dest, n, inlineT, foundInline)  # body
                    while n.hasMore(): skip(n)
            case NifIndexKind.ProcIdx | NifIndexKind.FuncIdx | NifIndexKind.MethodIdx | NifIndexKind.ConverterIdx:
                with into(n):  # tag
                    with var:
                        dummy = nbool(False)
                    updateLoop(dest, n, inlineT, dummy)  # SymbolDef
                    updateLoop(dest, n, inlineT, dummy)  # Export marker
                    updateLoop(dest, n, inlineT, dummy)  # pattern
                    # an importer instantiates a generic routine from its body; an
                    # instance holds `(at …)` here and was compiled in this module:
                    with let:
                        isGeneric = isTagLit(n) and cursorTagId(n) == TagId(TagEnum.TypevarsTagId)
                    updateLoop(dest, n, inlineT, dummy)  # typevars
                    updateLoop(dest, n, inlineT, dummy)  # params
                    updateLoop(dest, n, inlineT, dummy)  # retType
                    updateLoop(dest, n, inlineT, foundInline)  # pragmas
                    updateLoop(dest, n, inlineT, dummy)  # effects
                    if foundInline or isGeneric:
                        updateLoop(dest, n, inlineT, dummy)  # body
                    else:
                        skip(n)
                    while n.hasMore(): skip(n)
            case NifIndexKind.NoIndexTag | NifIndexKind.InlineIdx | NifIndexKind.KvIdx | NifIndexKind.VvIdx | \
                    NifIndexKind.BuildIdx | NifIndexKind.BundleIdx | NifIndexKind.IndexIdx | \
                    NifIndexKind.DependencyIdx | NifIndexKind.LinkIdx | NifIndexKind.OptionkeyIdx | \
                    NifIndexKind.ExportIdx | NifIndexKind.FromexportIdx | NifIndexKind.ExportexceptIdx:
                for _ in loopInto(n):
                    _processDeclForChecksum(dest, n)
    else:
        n.inc()


def _processForChecksum(dest: mut @ Sha1State, content: mut @ TokenBuf):
    with var:
        n = content.beginRead()
    _processDeclForChecksum(dest, n)


class HookIndexEntry(Object):
    typ: SymId
    hook_: SymId
    isGeneric: bool


class IndexSections(Object):
    converters: seq[tuple[SymId, SymId]]  # string is for compat with `methods`
    exportBuf: TokenBuf
    reexportedChecksums: seq[string]  ## the checksums of the modules
    ## `exportBuf` re-exports: an importer reads their declarations through
    ## this module, so they are part of its interface


def _getSymbolSection(tag: TagId, values: seq[tuple[SymId, SymId]]) -> TokenBuf:
    result = createTokenBuf(30)
    addParLe(result, tag)

    for value in values:
        with let:
            (key, sym) = value
        addParLe(result, TagId(NifIndexKind.KvIdx), NoLineInfo)
        if key == SymId(0):
            addDotToken(result, NoLineInfo)
        else:
            addSymUse(result, key, NoLineInfo)
        addSymUse(result, sym, NoLineInfo)
        addParRi(result)

    addParRi(result)
    return result


@dispatch
def createIndex(infile: string, root: NifLineInfo, buildChecksum: bool, sections: IndexSections):
    """{.canRaise.}"""
    # Mirror the doc-mode cache split: `foo.sc.nif` → `foo.sc.idx.nif`, the regular
    # `foo.s.nif` → `foo.s.idx.nif`. Keeps both populations valid in parallel.
    with let:
        isDocMode = infile.endsWith(string(".sc.nif"))
    with let:
        idxExt = string(".sc.idx.nif") if isDocMode else string(".s.idx.nif")
    with let:
        indexName = changeModuleExt(infile, idxExt)
    with var:
        content = string("(.nif27)\n(index\n")

    if sections.converters.len != 0:
        with let:
            converterSectionBuf = _getSymbolSection(TagId(NifIndexKind.ConverterIdx), sections.converters)

        content.add(toString(converterSectionBuf))
        content.add(string("\n"))

    if sections.exportBuf.len != 0:
        content.add(toString(sections.exportBuf))
        content.add(string("\n"))

    if buildChecksum:
        with var:
            r = nifreader.open(infile)
        with var:
            buf = createTokenBuf()
        nifcoreparse.parse(r, buf)
        # Close eagerly: the reader mmaps `infile`, and a leaked mapping keeps the
        # file locked on Windows — a later rewrite of the same file (e.g. repeated
        # `runEval` const folds writing the same tco<hash>.p.nif) then fails.
        nifreader.close(r)
        with var:
            checksum = newSha1State()
        _processForChecksum(checksum, buf)
        for cs in sections.reexportedChecksums:
            update(checksum, cs)
        with let:
            final = SecureHash(finalize(checksum))
        content.add(string("(checksum \"") + str(final) + string("\")"))
    content.add(string("\n)\n"))
    # The module's interface file (doc/internals/ic.md): importers' nimsem and
    # hexer depend on this file, not on `.s.nif`. When a module's interface and
    # inline-proc bodies are unchanged, its checksum is identical, so we keep
    # the old mtime to avoid cascading rebuilds through importers. nifmake's
    # `needsRebuild` uses the freshest of a node's outputs (max), so the
    # always-written `.s.nif` still proves "we ran since the inputs changed"
    # for nimsem's own staleness check.
    with let:
        try:
            existingContent = vfsRead(indexName)
        except:
            existingContent = string("")
    if existingContent != content:
        vfsWrite(indexName, content)


@dispatch
def createIndex(infile: string, buildChecksum: bool, root: NifLineInfo):
    """{.canRaise.}"""
    createIndex(infile, root, buildChecksum, IndexSections())


def writeFileAndIndex(outfile: string, content: TokenBuf):
    """{.canRaise.}"""
    vfsWrite(outfile, toString(content, True))
    with var:
        c = cast[ptr[TokenBuf]](unsafe_addr(content)).contents.cursorAt(0)
    createIndex(outfile, True, info(c))


class IndexVisibility(NIntEnum):
    Hidden = auto()
    Exported = auto()


class NifIndexEntry(Object):
    offset: nint
    info: PackedLineInfo    ## kept for the frozen Nim-compiler side
                            ## (ast2nif's position index); unused here
    parentInfo: NifLineInfo  ## absolute info of the decl's write-time parent
                             ## node; seeds `parse` on an index-jumped load so
                             ## file-less relative infos resolve correctly
    vis: IndexVisibility


class NifIndex(Object):
    converters: seq[tuple[string, string]]  # map of dest types to converter symbols
    exports: seq[tuple[string, NifIndexKind, seq[StrId]]]  # module, export kind, filtered names
    checksum: string  ## the interface checksum, "" when the index has none


def _symOrIdentOrDot(n: mut @ Cursor) -> string:
    if isSymbol(n): result = pool.symString(symId(n))
    elif isIdent(n): result = pool.strings[strId(n)].copy()
    elif isDotToken(n): result = string(".")
    else: result = string("")
    skip(n)
    return result


def _readSymbolSectionC(n: mut @ Cursor, tab: mut @ seq[tuple[string, string]]):
    ## Cursor walk of a `(converter (kv key value) …)` section.
    with into(n):
        while n.hasMore():
            if isTagLit(n) and cursorTagId(n) == TagId(NifIndexKind.KvIdx):
                with into(n):
                    with let:
                        key = _symOrIdentOrDot(n)
                    with let:
                        value = _symOrIdentOrDot(n)
                    tab.add((key, value))
            else:
                skip(n)


def readIndex(indexName: string) -> NifIndex:
    with var:
        r = nifreader.open(indexName)
    with var:
        buf = createTokenBuf()
    nifcoreparse.parse(r, buf)   # reads directives + the `(index …)` tree
    close(r)
    result = default(NifIndex)
    with var:
        n = buf.beginRead()
    if not (isTagLit(n) and cursorTagId(n) == TagId(NifIndexKind.IndexIdx)):
        assert False, "expected 'index' tag"
        return result
    with into(n):
        while n.hasMore():
            if isTagLit(n):
                with let:
                    t = cursorTagId(n)
                if t == TagId(NifIndexKind.ConverterIdx):
                    _readSymbolSectionC(n, result.converters)
                elif t == TagId(NifIndexKind.ExportIdx) or t == TagId(NifIndexKind.FromexportIdx) or \
                        t == TagId(NifIndexKind.ExportexceptIdx):
                    with let:
                        kind = cast[NifIndexKind](cursorTagId(n))
                    with into(n):
                        assert isStringLit(n)
                        with let:
                            path = pool.strings[strId(n)]
                        skip(n)
                        with var:
                            names: seq[StrId] = seq[StrId]([])  # Nim: `= @[]` (nimony: initialized)
                        while n.hasMore():
                            if isIdent(n): names.add(strId(n))
                            skip(n)
                        result.exports.add((path, kind, names))
                elif globalTags.tags[t] == "checksum":
                    with into(n):
                        if isStringLit(n): result.checksum = pool.strings[strId(n)]
                        while n.hasMore(): skip(n)
                else:
                    skip(n)
            else:
                skip(n)
    return result


def readEmbeddedIndex(r: mut @ Reader) -> OrderedTable[string, NifIndexEntry]:
    ## Reader-based twin of the classic streaming version (mirrors
    ## `foreignmodules.readEmbeddedIndex`, but keeps visibility). ORDERED because
    ## the overload sets built from it are iterated in table order, and a plain
    ## `Table` does not agree with itself across builds of the compiler: nimony's
    ## `Table` keeps its payload in a `seq` and iterates it in insertion order,
    ## Nim's walks the bucket array. So a host-Nim built compiler and a
    ## self-hosted one would list overloads differently. Each entry's
    ## line-info suffix records the indexed decl's PARENT absolute info (written
    ## relative to the `.index` head's root anchor when the file matches, see
    ## `emitValueIndexed`); resolve it here so an index-jumped `parse` can seed
    ## its parent stack with it — a decl whose file switch sits on an ancestor
    ## node (e.g. code from an `include` file) would otherwise resolve file-less
    ## relative infos to the module's own file.
    result = initOrderedTable[string, NifIndexEntry]()
    with let:
        indexPos = indexStartsAt(r)
    if indexPos <= 0: return result
    with let:
        contentPos = offset(r)
    jumpTo(r, indexPos)
    with var:
        previousOffset = nint(0)
    with var:
        t = default(ExpandedToken)
    next(r, t)                                   # `(.index`
    if t.tk == NifKind.ParLe and t.data == ".index":
        with var:
            root = NoNifLineInfo
        if t.filename.len != 0:
            root = NifLineInfo(file=getOrIncl(pool.filenames, decodeFilename(t)),
                               line=t.pos.line, col=t.pos.col)
        next(r, t)
        while t.tk != NifKind.EofToken and t.tk != NifKind.ParRi:
            if t.tk == NifKind.ParLe:
                with let:
                    vis = IndexVisibility.Exported if t.data == "x" else IndexVisibility.Hidden
                with var:
                    parentInfo = NoNifLineInfo
                if t.filename.len != 0:
                    parentInfo = NifLineInfo(file=getOrIncl(pool.filenames, decodeFilename(t)),
                                             line=t.pos.line, col=t.pos.col)
                elif isValid(root.file):  # Nim: root.file.isValid (the method form fails: AttributeError)
                    parentInfo = NifLineInfo(file=root.file,
                                             line=root.line + t.pos.line,
                                             col=root.col + t.pos.col)
                next(r, t)                             # the symbol
                with var:
                    key = string("")
                if t.tk == NifKind.Symbol: key = decodeStr(r, t)
                next(r, t)                             # the (delta) offset
                if t.tk == NifKind.IntLit:
                    with let:
                        off = nint(decodeInt(t)) + previousOffset
                    if key.len > 0:
                        result[key] = NifIndexEntry(offset=off, parentInfo=parentInfo, vis=vis)
                    previousOffset = off
                next(r, t)                             # closing `)`
                if t.tk == NifKind.ParRi: next(r, t)
            else:
                next(r, t)
    jumpTo(r, contentPos)
    return result


if comptime(__name__ == "__main__"):
    from nimic.std.os import fileExists, getTempDir, paramStr, removeFile
    try:
        createIndex(paramStr(1), False, NoLineInfo)
    except:
        quit(string("createIndex failed"))


if comptime(__name__ == "__main__"):
    def echoIndex(idx: NifIndex):
        echo("converters: ", idx.converters.len)
        for (k, v) in idx.converters:
            echo("  ", k, " -> ", v)
        echo("exports: ", idx.exports.len)
        for (path, kind, names) in idx.exports:
            echo("  ", path, " ", kind, " ", names.len)
            for nm in names:
                echo("    ", pool.strings[nm])

    def indexText(infile: string) -> string:
        result = readFile(changeModuleExt(infile, string(".s.idx.nif")))
        return result

    def checksumOf(path: string, text: string) -> string:
        writeFile(path, text)
        createIndex(path, True, NoLineInfo)
        result = indexText(path)
        return result

    def addedTests():
        # the original's block wrote an index without a checksum
        echo(indexText(paramStr(1)))
        echoIndex(readIndex(changeModuleExt(paramStr(1), string(".s.idx.nif"))))

        # private helpers
        echo(_isImportant(string("a.b")), " ", _isImportant(string("a.b.c")), " ",
             _isImportant(string("")))
        echo(_entryKind(TagId(TagEnum.ProcTagId)), " ", _entryKind(TagId(TagEnum.InlineTagId)), " ",
             _entryKind(TagId(TagEnum.StmtsTagId)))

        with let:
            dir = getTempDir()

        # converter and export sections, no checksum
        with var:
            sections = default(IndexSections)  # initialized: nimony adds to its fields only then
        sections.converters.add((symId(pool, string("MyInt.0.m")), symId(pool, string("toMyInt.0.m"))))
        sections.converters.add((SymId(0), symId(pool, string("anyConv.1.m"))))
        sections.exportBuf = createTokenBuf()
        addParLe(sections.exportBuf, TagId(NifIndexKind.ExportIdx), NoLineInfo)
        addStrLit(sections.exportBuf, string("std/strutils"), NoLineInfo)
        addParRi(sections.exportBuf)
        addParLe(sections.exportBuf, TagId(NifIndexKind.FromexportIdx), NoLineInfo)
        addStrLit(sections.exportBuf, string("mymod"), NoLineInfo)
        addIdent(sections.exportBuf, string("foo"), NoLineInfo)
        addIdent(sections.exportBuf, string("bar"), NoLineInfo)
        addParRi(sections.exportBuf)
        addParLe(sections.exportBuf, TagId(NifIndexKind.ExportexceptIdx), NoLineInfo)
        addStrLit(sections.exportBuf, string("other"), NoLineInfo)
        addIdent(sections.exportBuf, string("hidden"), NoLineInfo)
        addParRi(sections.exportBuf)
        with let:
            secFile = dir + string("nimic_nifindexes_sec.s.nif")
        createIndex(secFile, NoLineInfo, False, sections)
        echo(indexText(secFile))
        echoIndex(readIndex(changeModuleExt(secFile, string(".s.idx.nif"))))
        removeFile(changeModuleExt(secFile, string(".s.idx.nif")))
        # doc mode: `.sc.nif` -> `.sc.idx.nif`
        with let:
            docFile = dir + string("nimic_nifindexes_doc.sc.nif")
        createIndex(docFile, False, NoLineInfo)
        echo(fileExists(changeModuleExt(docFile, string(".sc.idx.nif"))))
        removeFile(changeModuleExt(docFile, string(".sc.idx.nif")))

        # the checksum: which changes count
        with let:
            ckFile = dir + string("nimic_nifindexes_ck.s.nif")
        with let:
            base = checksumOf(ckFile, string(
                string("(.nif27)\n(stmts (proc :f.0.m x . . (params (param :a.0 . . (i +32))) (i +32) . . (stmts (ret a.0)))") +
                string(" (proc :g.0.m x . . (params) . (pragmas (inline)) . (stmts (call f.0.m 1)))") +
                string(" (proc :h.0.m x . (typevars (typevar :T.0 . . . .)) (params) . . . (stmts (ret 1)))") +
                string(" (template :t.0.m x . . (params) . . . (stmts 1))") +
                string(" (var :v.0.m x . (i +32) 5) (type :T.0.m x . . (object .)))")))
        echo(base)
        with let:
            body = checksumOf(ckFile, string(
                string("(.nif27)\n(stmts (proc :f.0.m x . . (params (param :a.0 . . (i +32))) (i +32) . . (stmts (ret 42)))") +
                string(" (proc :g.0.m x . . (params) . (pragmas (inline)) . (stmts (call f.0.m 1)))") +
                string(" (proc :h.0.m x . (typevars (typevar :T.0 . . . .)) (params) . . . (stmts (ret 1)))") +
                string(" (template :t.0.m x . . (params) . . . (stmts 1))") +
                string(" (var :v.0.m x . (i +32) 5) (type :T.0.m x . . (object .)))")))
        echo("non-inline body: ", body == base)
        with let:
            inl = checksumOf(ckFile, string(
                string("(.nif27)\n(stmts (proc :f.0.m x . . (params (param :a.0 . . (i +32))) (i +32) . . (stmts (ret a.0)))") +
                string(" (proc :g.0.m x . . (params) . (pragmas (inline)) . (stmts (call f.0.m 2)))") +
                string(" (proc :h.0.m x . (typevars (typevar :T.0 . . . .)) (params) . . . (stmts (ret 1)))") +
                string(" (template :t.0.m x . . (params) . . . (stmts 1))") +
                string(" (var :v.0.m x . (i +32) 5) (type :T.0.m x . . (object .)))")))
        echo("inline body: ", inl == base)
        with let:
            gen = checksumOf(ckFile, string(
                string("(.nif27)\n(stmts (proc :f.0.m x . . (params (param :a.0 . . (i +32))) (i +32) . . (stmts (ret a.0)))") +
                string(" (proc :g.0.m x . . (params) . (pragmas (inline)) . (stmts (call f.0.m 1)))") +
                string(" (proc :h.0.m x . (typevars (typevar :T.0 . . . .)) (params) . . . (stmts (ret 2)))") +
                string(" (template :t.0.m x . . (params) . . . (stmts 1))") +
                string(" (var :v.0.m x . (i +32) 5) (type :T.0.m x . . (object .)))")))
        echo("generic body: ", gen == base)
        with let:
            tmpl = checksumOf(ckFile, string(
                string("(.nif27)\n(stmts (proc :f.0.m x . . (params (param :a.0 . . (i +32))) (i +32) . . (stmts (ret a.0)))") +
                string(" (proc :g.0.m x . . (params) . (pragmas (inline)) . (stmts (call f.0.m 1)))") +
                string(" (proc :h.0.m x . (typevars (typevar :T.0 . . . .)) (params) . . . (stmts (ret 1)))") +
                string(" (template :t.0.m x . . (params) . . . (stmts 2))") +
                string(" (var :v.0.m x . (i +32) 5) (type :T.0.m x . . (object .)))")))
        echo("template body: ", tmpl == base)
        with let:
            vv = checksumOf(ckFile, string(
                string("(.nif27)\n(stmts (proc :f.0.m x . . (params (param :a.0 . . (i +32))) (i +32) . . (stmts (ret a.0)))") +
                string(" (proc :g.0.m x . . (params) . (pragmas (inline)) . (stmts (call f.0.m 1)))") +
                string(" (proc :h.0.m x . (typevars (typevar :T.0 . . . .)) (params) . . . (stmts (ret 1)))") +
                string(" (template :t.0.m x . . (params) . . . (stmts 1))") +
                string(" (var :v.0.m x . (i +32) 6) (type :T.0.m x . . (object .)))")))
        echo("var value: ", vv == base)
        # the index file is kept when its content is unchanged
        writeFile(changeModuleExt(ckFile, string(".s.idx.nif")), string("by hand"))
        createIndex(ckFile, True, NoLineInfo)
        echo("rewritten: ", indexText(ckFile) == vv)
        removeFile(ckFile)
        removeFile(changeModuleExt(ckFile, string(".s.idx.nif")))

        # writeFileAndIndex
        with let:
            outFile = dir + string("nimic_nifindexes_out.s.nif")
        with var:
            content = parseFromBuffer(string("(stmts@1,1,m.nim (let :x.0.m x . (i +32) 1) (proc :p.0.m . . . (params) . . . (stmts)))"),
                                      string("m"))
        writeFileAndIndex(outFile, content)
        echo(readFile(outFile))
        echo(indexText(outFile))
        removeFile(outFile)
        removeFile(changeModuleExt(outFile, string(".s.idx.nif")))

        # readEmbeddedIndex: a module file written with its `.index`
        with let:
            embFile = dir + string("nimic_nifindexes_emb.s.nif")
        with var:
            emb = parseFromBuffer(string(
                string("(stmts@1,1,m.nim (let@0,2 :x.0.m x . (i +32) 1) (proc@0,3 :p.0.m . . . (params) . . . (stmts") +
                string(" (let@2,1 :loc.0 . . . 2)))") +
                string(" (type@0,5,inc.nim :T.0.m x . . (object .)) (var@0,6 :w.1.m x . . 3)") +
                string(" (stmts@0,9,inc.nim (var@0,1 :z.0.m x . . 4)))")), string("m"))
        writeFile(emb, embFile)
        echo(readFile(embFile))
        with var:
            r = nifreader.open(embFile)
        with var:
            tab = readEmbeddedIndex(r)
        echo("entries: ", tab.len, " offset after: ", offset(r))
        for k, e in pairs(tab):  # in the order the index lists them
            echo(k, " offset=", e.offset, " vis=", e.vis, " parent=", e.parentInfo.line,
                 ",", e.parentInfo.col, " ",
                 pool.filenames[e.parentInfo.file] if isValid(e.parentInfo.file) else string("-"))
        echo("loc.0 indexed: ", tab.hasKey(string("loc.0")))
        close(r)
        removeFile(embFile)
        # a file without an embedded index
        with let:
            plainFile = dir + string("nimic_nifindexes_plain.s.nif")
        writeFile(plainFile, string("(.nif27)\n(stmts 1)\n"))
        with var:
            rp = nifreader.open(plainFile)
        echo("plain entries: ", len(readEmbeddedIndex(rp)))
        close(rp)
        removeFile(plainFile)

    addedTests()
