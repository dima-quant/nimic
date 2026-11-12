# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/nifler2/niflerout.nim
# ///
#
#
#           Nifler2: Nim to NIF
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## Writes the parsed buffer as nifler writes it, byte for byte.
##
## `nifcoreparse`'s writer is the canonical NIF one and cannot be used: it
## gives a token without line info the info of the token before it, and it
## writes an index. nifler's rules are simpler and they are what the rest of
## the toolchain has seen so far:
##
## * The header is `(.nif27)`, `(.vendor "Nifler")`, `(.dialect "nim-parsed")`
##   and there is no index.
## * A position is written relative to the enclosing tag and left out when it
##   is the same. A token that has no position of its own -- a `.`, the `x`
##   export marker -- writes none and so has its tag's. nifler computes the
##   difference against the node's parent in *Nim's* AST, which is not always
##   the enclosing NIF tag; but a written difference decodes to exactly one
##   absolute position, so storing the position nifler's output decodes to and
##   encoding it against the NIF parent gives the same bytes.
## * The root carries the file, relative to the current directory
##   (`--portablePaths`), else absolute.
## * `addEmpty(n)` writes `n` dots without separators, and bridge.nim calls it
##   with `n > 1` in exactly three places: the first four and the last two
##   slots of a `proctype`/`itertype`, the four empty slots of a `for` loop's
##   tuple variable, and the type and value slots of every other `let` that
##   unpacks a tuple.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import syncio, assertions
from ..lib import nifbuilder
from ..lib.nifbuilder import addEmpty, addHeader, addRaw, addTree, attachLineInfo, Builder, endTree, extract
from ..lib import nifpools
from ..lib.nifpools import NoLineInfo, writeFile
from .parserrt import (
    charVal, childCount, FileId, floatVal, intVal, isValid, kind, NifKind, NiflerKind, NifLineInfo, Node,
    Pool, strId, tag, TagPool, uintVal)
addIdent = overloads(nifbuilder.addIdent, nifpools.addIdent)
addStrLit = overloads(nifbuilder.addStrLit, nifpools.addStrLit)
addCharLit = overloads(nifbuilder.addCharLit, nifpools.addCharLit)
addIntLit = overloads(nifbuilder.addIntLit, nifpools.addIntLit)
addUIntLit = overloads(nifbuilder.addUIntLit, nifpools.addUIntLit)
addFloatLit = overloads(nifbuilder.addFloatLit, nifpools.addFloatLit)


class _Writer(Object):
    _b: Builder
    _file: string  ## the root's file, as it is written
    _rootFile: FileId
    _pool: Pool  ## where a cell's names were interned
    _tags: TagPool  ## where a cell's `TagId` gets its spelling
    _noLineInfo: bool  ## the deps file carries no positions

    def _lineInfo(w: mut @ _Writer, info: NifLineInfo, reference: NifLineInfo):
        ## bridge.nim's `relLineInfo`: absolute with the file at the root, else the
        ## difference to the reference, and nothing when that is zero.
        if w._noLineInfo or not isValid(info.file): return
        if not isValid(reference.file) or info.file != reference.file:
            # absolute, with the file: the root, and an empty node's `???`
            with let:
                name = w._file if info.file == w._rootFile else w._pool.filenames[info.file]
            # an empty node's position is `unknownLineInfo`, column -1; nifcore
            # clamps a stored column at 0, so it is restored here
            with let:
                col = i32(-1) if name == "???" else info.col
            attachLineInfo(w._b, col, info.line, name)
        else:
            attachLineInfo(w._b, info.col - reference.col, info.line - reference.line, string(""))

    def _tagName(w: _Writer, n: Node) -> string:
        """{.inline.}"""
        return w._tags.tags[tag(n)].copy()


def _tagKind(n: Node) -> NiflerKind:
    """{.inline.}"""
    ## Every tag in the tree came from a `NiflerKind` (`parserrt.tagId`).
    return cast[NiflerKind](tag(n))


class _EmptyRuns(Object):
    ## Where `addEmpty(n)` wrote more than one dot in a single call. Two slots
    ## are enough: `emptyRuns` never marks more, and every other child index
    ## is one dot of its own.
    _s1: nint
    _n1: nint
    _s2: nint
    _n2: nint

    def _runAt(r: _EmptyRuns, i: nint) -> nint:
        ## How many dots the call starting at child `i` wrote; 0 when `i` was
        ## swallowed by an earlier run. The runs are tested before the ranges they
        ## span, because a later run may start inside an earlier one.
        if i == r._s1: return copy(r._n1)
        elif i == r._s2: return copy(r._n2)
        elif i > r._s1 and i < r._s1 + r._n1: return 0
        elif i > r._s2 and i < r._s2 + r._n2: return 0
        else: return 1


def _emptyRuns(n: Node, tag: NiflerKind, parentTag: NiflerKind, inForTuple: bool) -> _EmptyRuns:
    result = _EmptyRuns(_s1=-1, _n1=0, _s2=-1, _n2=0)
    match tag:
        case NiflerKind.ProctypeL | NiflerKind.ItertypeL:
            with let:
                kids = childCount(n)
            if kids >= 4:
                result._s1 = 0
                result._n1 = 4
            if kids >= 2:
                result._s2 = kids - 2
                result._n2 = 2
        case NiflerKind.LetL | NiflerKind.VarL | NiflerKind.ConstL:  # the section of a tuple unpacking
            if parentTag == NiflerKind.UnpacktupL and inForTuple:
                if childCount(n) == 5:
                    result._s1 = 1
                    result._n1 = 4
            elif parentTag == NiflerKind.UnpacktupL or parentTag == NiflerKind.UnpackflatL:
                if childCount(n) == 5:
                    result._s1 = 3
                    result._n1 = 2
        case _: pass
    return result


def _isDecl(k: NiflerKind) -> bool:
    match k:
        case NiflerKind.TypeL | NiflerKind.VarL | NiflerKind.LetL | NiflerKind.ConstL | NiflerKind.FldL | NiflerKind.ParamL | NiflerKind.TypevarL | NiflerKind.ProcL | NiflerKind.FuncL | NiflerKind.IteratorL | NiflerKind.MethodL | NiflerKind.MacroL | NiflerKind.TemplateL | NiflerKind.ConverterL: return True
        case _: return False


def _isRoutine(k: NiflerKind) -> bool:
    match k:
        case NiflerKind.ProcL | NiflerKind.FuncL | NiflerKind.IteratorL | NiflerKind.MethodL | NiflerKind.MacroL | NiflerKind.TemplateL | NiflerKind.ConverterL | NiflerKind.ProctypeL | NiflerKind.ItertypeL | NiflerKind.DoL: return True
        case _: return False


def _emit(w: mut @ _Writer, n: Node, reference: NifLineInfo, parentTag: NiflerKind, inForTuple: bool, forLoop: bool):
    ## `reference` is what bridge.nim computes this node's position against: its
    ## parent in Nim's AST, which is usually but not always the enclosing tag.
    with let:
        info = n.info
    match kind(n):
        case NifKind.TagLit:
            with let:
                tg = _tagKind(n)
                first = n.down
            # `nkLambda` writes its position after the name placeholder:
            # `(proc .@5,1 . . . (params) ...)`
            with let:
                lambda_ = tg == NiflerKind.ProcL and not isNil(first) and kind(first) == NifKind.DotToken
            # `nkStmtListExpr` writes none on `expr` and its own on the `stmts`
            with let:
                stmtListExpr = tg == NiflerKind.ExprL
            addTree(w._b, w._tagName(n))
            if not lambda_ and not stmtListExpr:
                w._lineInfo(info, reference)
            with let:
                own = info if info.isValid() else reference
                childInForTuple = tg == NiflerKind.UnpacktupL and forLoop
                childForLoop = tg == NiflerKind.ForL or tg == NiflerKind.UnpackflatL
                routine = _isRoutine(tg)
                runs = _emptyRuns(n, tg, parentTag, inForTuple)
            with var:
                i = nint(0)
                prevParams = NoLineInfo
                k = n.down
            while not isNil(k):
                # the child's reference in bridge.nim
                with var:
                    childRef = own
                if routine and prevParams.isValid():
                    childRef = prevParams  # the result type is `n[0]` of the params
                elif tg == NiflerKind.TupleL:
                    childRef = reference  # `(kv` uses the tuple's own parent
                elif stmtListExpr and i == 0:
                    childRef = reference
                prevParams = NoLineInfo
                if kind(k) == NifKind.Ident and i == 1 and _isDecl(tg) and w._pool.strings[strId(k)] == "x":
                    addRaw(w._b, string(" x"))  # bridge.nim's export marker, verbatim:
                                                # a space even after a `)`
                elif kind(k) == NifKind.DotToken:
                    with let:
                        dots = runs._runAt(i)
                    if dots > 0:
                        addEmpty(w._b, dots)
                        if lambda_ and i == 0: w._lineInfo(info, reference)
                else:
                    if routine and kind(k) == NifKind.TagLit and _tagKind(k) == NiflerKind.ParamsL:
                        with let:
                            pinfo = k.info
                        _emit(w, k, childRef, tg, childInForTuple, childForLoop)
                        prevParams = pinfo
                    else:
                        _emit(w, k, childRef, tg, childInForTuple, childForLoop)
                i += 1
                k = k.next
            endTree(w._b)
        case NifKind.DotToken:
            addEmpty(w._b)
        case NifKind.Ident:
            addIdent(w._b, w._pool.strings[strId(n)])
            w._lineInfo(info, reference)
        case NifKind.StrLit:
            addStrLit(w._b, w._pool.strings[strId(n)])
            w._lineInfo(info, reference)
        case NifKind.CharLit:
            addCharLit(w._b, charVal(n))
            w._lineInfo(info, reference)
        case NifKind.IntLit:
            addIntLit(w._b, intVal(n))
            w._lineInfo(info, reference)
        case NifKind.UIntLit:
            addUIntLit(w._b, uintVal(n))
            w._lineInfo(info, reference)
        case NifKind.FloatLit:
            # nifbuilder puts the position inside `(inf)` itself
            if info.isValid() and reference.isValid():
                addFloatLit(w._b, floatVal(n), info.col - reference.col, info.line - reference.line)
            else:
                addFloatLit(w._b, floatVal(n))
        case _:
            assert False, string("nifler2 writes no ") + str(kind(n))


def writeNifler(first: Node, pool: Pool, tags: TagPool, sizeHint: nint, outfile: string, file: string):
    """{.raises.}"""
    ## `file` is the module's path as nifler writes it: relative to the current
    ## directory (`--portablePaths`) or absolute.
    with var:
        w = _Writer(_b=nifbuilder.open(sizeHint), _file=file, _pool=pool, _tags=tags)
    addHeader(w._b, string("Nifler"), string("nim-parsed"))
    if not isNil(first): w._rootFile = first.info.file
    with var:
        n = first
    while not isNil(n):
        _emit(w, n, NoLineInfo, NiflerKind.None_, False, False)
        n = n.next
    writeFile(outfile, extract(w._b))

# --------------------------------------------------------------- deps file
#
# `nifler --deps` writes a second file next to the parsed module: the module's
# dependencies, which is what nimony's build graph is made of. bridge.nim
# emits it while it translates, into a second builder with positions off;
# everything it needs is in the finished tree, so here it is a walk over that.
#
# * `import`, `importexcept`, `fromimport`, `include`, `export` and
#   `exportexcept` are copied wherever they occur, a proc body included.
# * Inside the branches of a `when` each of them carries a `(when COND...)`
#   marker right after its tag: the conditions of every enclosing branch, an
#   `else` branch contributing `(prefix not COND)` for each earlier condition
#   -- so the dependency scanner can skip what is statically dead.
# * `{.plugin: "name".}` is `(plugin (when...)? "name")`: a program the build
#   has to produce before the module can be checked.
# * Nothing inside `runnableExamples` counts.


def _isDep(k: NiflerKind) -> bool:
    match k:
        case NiflerKind.ImportL | NiflerKind.ImportexceptL | NiflerKind.FromimportL | NiflerKind.IncludeL | NiflerKind.ExportL | NiflerKind.ExportexceptL: return True
        case _: return False


class _WhenCond(Object):
    _cond: Node
    _negated: bool


class _DepsWalker(Object):
    _w: _Writer
    _conds: seq[_WhenCond]

    def _whenMarker(d: mut @ _DepsWalker):
        if d._conds.len == 0: return
        addTree(d._w._b, string("when"))
        for entry in d._conds:
            if entry._negated:
                addTree(d._w._b, string("prefix"))
                addIdent(d._w._b, string("not"))
                _emit(d._w, entry._cond, NoLineInfo, NiflerKind.None_, False, False)
                endTree(d._w._b)
            else:
                _emit(d._w, entry._cond, NoLineInfo, NiflerKind.None_, False, False)
        endTree(d._w._b)

    def _isPlugin(d: _DepsWalker, kv: Node, name: mut @ string) -> bool:
        ## `plugin: "name"`; a raw or triple-quoted string is written plain.
        if kind(kv) != NifKind.TagLit or _tagKind(kv) != NiflerKind.KvL: return False
        with let:
            k = kv.down
        if isNil(k) or kind(k) != NifKind.Ident or d._w._pool.strings[strId(k)] != "plugin":
            return False
        with let:
            v = k.next
        if isNil(v): return False
        if kind(v) == NifKind.StrLit:
            name <<= d._w._pool.strings[strId(v)]
            return True
        if kind(v) == NifKind.TagLit and _tagKind(v) == NiflerKind.SufL:
            with let:
                s = v.down
            if not isNil(s) and kind(s) == NifKind.StrLit:
                name <<= d._w._pool.strings[strId(s)]
                return True
        return False

    def _walkDeps(d: mut @ _DepsWalker, n: Node, inObject: bool):
        if kind(n) != NifKind.TagLit: return
        with let:
            tg = _tagKind(n)
        if _isDep(tg):
            addTree(d._w._b, d._w._tagName(n))
            d._whenMarker()
            with var:
                k = n.down
            while not isNil(k):
                _emit(d._w, k, NoLineInfo, tg, False, False)
                k = k.next
            endTree(d._w._b)
            return
        if tg == NiflerKind.CallL or tg == NiflerKind.CmdL:
            with let:
                f = n.down
            if not isNil(f) and kind(f) == NifKind.Ident and d._w._pool.strings[strId(f)] == "runnableExamples": return
        if tg == NiflerKind.PragmasL:
            with var:
                k = n.down
            while not isNil(k):
                with var:
                    name = string("")
                if d._isPlugin(k, name):
                    addTree(d._w._b, string("plugin"))
                    d._whenMarker()
                    addStrLit(d._w._b, name)
                    endTree(d._w._b)
                elif kind(k) == NifKind.Ident and d._w._pool.strings[strId(k)] == "enableTrace":
                    # the memory management runtime collects cycles (`deps.processDep`)
                    addTree(d._w._b, string("enableTrace"))
                    d._whenMarker()
                    endTree(d._w._b)
                k = k.next
            return
        if tg == NiflerKind.WhenL and not inObject:
            # `nkWhenStmt`: each branch's condition covers its body, and an `else`
            # is covered by the negation of all of them
            with var:
                prior: seq[Node] = seq[Node]([])
                br = n.down
            while not isNil(br):
                if kind(br) == NifKind.TagLit and _tagKind(br) == NiflerKind.ElifL:
                    with let:
                        cond = br.down
                    if not isNil(cond):
                        d._walkDeps(cond, inObject)
                        d._conds.add(_WhenCond(_cond=cond, _negated=False))
                        with var:
                            k = cond.next
                        while not isNil(k):
                            d._walkDeps(k, inObject)
                            k = k.next
                        d._conds.setLen(d._conds.len - 1)
                        prior.add(cond)
                else:
                    for cond in prior: d._conds.add(_WhenCond(_cond=cond, _negated=True))
                    d._walkDeps(br, inObject)
                    d._conds.setLen(d._conds.len - prior.len)
                br = br.next
            return
        with let:
            nowInObject = inObject or tg == NiflerKind.ObjectL
        with var:
            k = n.down
        while not isNil(k):
            d._walkDeps(k, nowInObject)
            k = k.next


def writeDeps(first: Node, pool: Pool, tags: TagPool, outfile: string):
    """{.raises.}"""
    with var:
        d = _DepsWalker(_w=_Writer(_b=nifbuilder.open(1024), _pool=pool, _tags=tags, _noLineInfo=True), _conds=seq[_WhenCond]([]))
    addHeader(d._w._b, string("Nifler"), string("nim-deps"))
    addTree(d._w._b, string("stmts"))
    with var:
        n = first
    while not isNil(n):
        d._walkDeps(n, False)
        n = n.next
    endTree(d._w._b)
    writeFile(outfile, extract(d._w._b))
