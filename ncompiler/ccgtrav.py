# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2013 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

## Generates traversal procs for the C backend.

# included from cgen.nim (tests: ncompiler/tests/test_ccg.py)

class _TTraversalClosure(Object):
    _p: BProc
    _visitorFrmt: string


@dispatch
def _genTraverseProc(c: _TTraversalClosure, accessor: Rope, typ: PType) -> None:
    pass


def _genCaseRange(p: BProc, branch: PNode, info: mut@_SwitchCaseBuilder) -> None:
    pass


def _getTemp(p: BProc, t: PType, needsInit: bool = False) -> TLoc:
    pass


def _visit(p: BProc, data: Snippet, visitor: Snippet) -> None:
    p.s(TCProcSection.cpsStmts)._addCallStmt(cgsymValue(p.module, string("nimGCvisit")),
        _cCast(CPointer, data),
        visitor)


@dispatch
def _genTraverseProc(c: _TTraversalClosure, accessor: Rope, n: PNode, typ: PType) -> None:
    if n is None:
        return
    match n.kind:
        case TNodeKind.nkRecList:
            for i in range(n.len):
                _genTraverseProc(c, accessor, n[i], typ)
        case TNodeKind.nkRecCase:
            if n[0].kind != TNodeKind.nkSym:
                internalError(c._p.config, n.info, string("genTraverseProc"))
            with var:
                p = c._p
            with let:
                disc = n[0].sym
            if disc.loc.snippet == string(""):
                fillObjectFields(c._p.module, typ)
            if disc.loc.t is None:
                internalError(c._p.config, n.info, string("genTraverseProc()"))
            with let:
                discField = _dotField(accessor, disc.loc.snippet)
            with p.s(TCProcSection.cpsStmts)._addSwitchStmt(discField):
                for i in range(1, n.len):
                    with let:
                        branch = n[i]
                    assert branch.kind in {TNodeKind.nkOfBranch, TNodeKind.nkElse}
                    with var:
                        caseBuilder = _SwitchCaseBuilder()
                    with p.s(TCProcSection.cpsStmts)._addSwitchCase(caseBuilder):
                        if branch.kind == TNodeKind.nkOfBranch:
                            _genCaseRange(c._p, branch, caseBuilder)
                        else:
                            p.s(TCProcSection.cpsStmts)._addCaseElse(caseBuilder)
                        with do:
                            _genTraverseProc(c, accessor, lastSon(branch), typ)
                            p.s(TCProcSection.cpsStmts)._addBreak()
        case TNodeKind.nkSym:
            with let:
                field = n.sym
            if field.typ.kind == TTypeKind.tyVoid:
                return
            if field.loc.snippet == string(""):
                fillObjectFields(c._p.module, typ)
            if field.loc.t is None:
                internalError(c._p.config, n.info, string("genTraverseProc()"))
            _genTraverseProc(c, _dotField(accessor, field.loc.snippet), field.loc.t)
        case _:
            internalError(c._p.config, n.info, string("genTraverseProc()"))


@ufcs(string)
def _parentObj(accessor: Rope, m: BModule) -> Rope:
    """{.inline.}"""
    if not m.compileToCpp:
        result = _dotField(accessor, string("Sup"))
    else:
        result = accessor
    return result


def _genTraverseProcSeq(c: _TTraversalClosure, accessor: Rope, typ: PType) -> None:
    pass


@dispatch
def _genTraverseProc(c: _TTraversalClosure, accessor: Rope, typ: PType) -> None:
    if typ is None:
        return

    with var:
        p = c._p
    match typ.kind:
        case (TTypeKind.tyGenericInst | TTypeKind.tyGenericBody | TTypeKind.tyTypeDesc | TTypeKind.tyAlias |
              TTypeKind.tyDistinct | TTypeKind.tyInferred | TTypeKind.tySink | TTypeKind.tyOwned):
            _genTraverseProc(c, accessor, skipModifier(typ))
        case TTypeKind.tyArray:
            with let:
                arraySize = lengthOrd(c._p.config, typ.indexType)
            with var:
                i: TLoc = _getTemp(p, getSysType(c._p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
                oldCode = p.s(TCProcSection.cpsStmts).copy()
                oldLen = nint(0)
                newLen = nint(0)
            with p.s(TCProcSection.cpsStmts)._addForRangeExclusive(i.snippet, cIntValue(0), cIntValue(arraySize)):
                oldLen = p.s(TCProcSection.cpsStmts).buf.len
                _genTraverseProc(c, _subscript(accessor, i.snippet), typ.elementType)
                newLen = p.s(TCProcSection.cpsStmts).buf.len
            if oldLen == newLen:
                # do not emit dummy long loops for faster debug builds:
                assign(p.s(TCProcSection.cpsStmts), oldCode)
        case TTypeKind.tyObject:
            with var:
                x = typ.baseClass
            if x is not None:
                x = x.skipTypes(skipPtrs)
            _genTraverseProc(c, accessor._parentObj(c._p.module), x)
            if typ.n is not None:
                _genTraverseProc(c, accessor, typ.n, typ)
        case TTypeKind.tyTuple:
            with let:
                typ = getUniqueType(typ)
            for i, a in typ.ikids():
                _genTraverseProc(c, _dotField(accessor, string("Field") + string(str(i))), a)
        case TTypeKind.tyRef:
            _visit(p, accessor, c._visitorFrmt)
        case TTypeKind.tySequence:
            if TGlobalOption.optSeqDestructors not in c._p.module.config.globalOptions:
                _visit(p, accessor, c._visitorFrmt)
            elif containsGarbageCollectedRef(typ.elementType):
                # destructor based seqs are themselves not traced but their data is, if
                # they contain a GC'ed type:
                p.s(TCProcSection.cpsStmts)._addCallStmt(cgsymValue(p.module, string("nimGCvisitSeq")),
                    _cCast(CPointer, accessor),
                    c._visitorFrmt)
                # genTraverseProcSeq(c, accessor, typ)
        case TTypeKind.tyString:
            if TTypeFlag.tfHasAsgn not in typ.flags:
                _visit(p, accessor, c._visitorFrmt)
        case TTypeKind.tyProc:
            if typ.callConv == TCallingConvention.ccClosure:
                _visit(p, _dotField(accessor, string("ClE_0")), c._visitorFrmt)
        case _:
            discard


def _genTraverseProcSeq(c: _TTraversalClosure, accessor: Rope, typ: PType) -> None:
    with var:
        p = c._p
    assert typ.kind == TTypeKind.tySequence
    with var:
        i = _getTemp(p, getSysType(c._p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
        oldCode = p.s(TCProcSection.cpsStmts).copy()
        oldLen = nint(0)
        newLen = nint(0)
        a = TLoc(snippet=accessor)
    with let:
        le = lenExpr(c._p, a)

    with p.s(TCProcSection.cpsStmts)._addForRangeExclusive(i.snippet, cIntValue(0), le):
        oldLen = p.s(TCProcSection.cpsStmts).buf.len
        _genTraverseProc(c, _subscript(dataField(c._p, accessor), i.snippet), typ.elementType)
        newLen = p.s(TCProcSection.cpsStmts).buf.len
    if newLen == oldLen:
        # do not emit dummy long loops for faster debug builds:
        assign(p.s(TCProcSection.cpsStmts), oldCode)


@dispatch
def _genTraverseProc(m: BModule, origTyp: PType, sig: SigHash) -> Rope:
    with var:
        p = newProc(None, m)
    result = string("Marker_") + getTypeName(m, origTyp, sig)
    with let:
        hcrOn = m.hcrOn
        typ = origTyp.skipTypes(abstractInstOwned)
        markerName = result + string("_actual") if hcrOn else result
        t = getTypeDesc(m, typ)

    p.s(TCProcSection.cpsLocals)._addVar(kind=_VarKind.Local, name=string("a"), typ=t)
    p.s(TCProcSection.cpsInit)._addAssignment(string("a"), _cCast(t, string("p")))

    with var:
        c = _TTraversalClosure(_p=p,
            _visitorFrmt=string("op")  # "#nimGCvisit((void*)$1, op);$n"
            )

    assert typ.kind != TTypeKind.tyTypeDesc
    if typ.kind == TTypeKind.tySequence:
        _genTraverseProcSeq(c, rope(string("a")), typ)
    else:
        if skipTypes(typ.elementType, typedescInst + TTypeKinds({TTypeKind.tyOwned})).kind == TTypeKind.tyArray:
            # C's arrays are broken beyond repair:
            _genTraverseProc(c, rope(string("a")), typ.elementType)
        else:
            _genTraverseProc(c, _cDeref(string("a")), typ.elementType)

    with var:
        headerBuilder = newBuilder(string(""))
    with headerBuilder._addProcHeaderWithParams(TCallingConvention.ccNimCall, markerName, CVoid):
        with var:
            paramBuilder = _ProcParamBuilder()
        with headerBuilder._addProcParams(paramBuilder):
            headerBuilder._addParam(paramBuilder, name=string("p"), typ=CPointer)
            headerBuilder._addParam(paramBuilder, name=string("op"), typ=NimInt)
    with let:
        header = headerBuilder.extract()

    with m.s[TCFileSection.cfsProcHeaders]._addDeclWithVisibility(_DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcHeaders].add(header)
        m.s[TCFileSection.cfsProcHeaders]._finishProcHeaderAsProto()
    with m.s[TCFileSection.cfsProcs]._addDeclWithVisibility(_DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcs].add(header)
        with m.s[TCFileSection.cfsProcs]._finishProcHeaderWithBody():
            m.s[TCFileSection.cfsProcs].add(p.s(TCProcSection.cpsLocals).extract())
            m.s[TCFileSection.cfsProcs].add(p.s(TCProcSection.cpsInit).extract())
            m.s[TCFileSection.cfsProcs].add(p.s(TCProcSection.cpsStmts).extract())

    if hcrOn:
        with var:
            desc = newBuilder(string(""))
            unnamedParamBuilder = _ProcParamBuilder()
        with desc._addProcParams(unnamedParamBuilder):
            desc._addUnnamedParam(unnamedParamBuilder, CPointer)
            desc._addUnnamedParam(unnamedParamBuilder, NimInt)
        with let:
            unnamedParams = desc.extract()
        m.s[TCFileSection.cfsProcHeaders]._addProcVar(TCallingConvention.ccNimCall, result, unnamedParams, CVoid)
        with m.s[TCFileSection.cfsDynLibInit]._addAssignmentWithValue(result):
            with m.s[TCFileSection.cfsDynLibInit]._addCast(_procPtrTypeUnnamed(TCallingConvention.ccNimCall, CVoid,
                                                                             unnamedParams)):
                m.s[TCFileSection.cfsDynLibInit]._addCall(string("hcrRegisterProc"),
                    getModuleDllPath(m),
                    string("\"") + result + string("\""),
                    _cCast(CPointer, markerName))
    return result


def _genTraverseProcForGlobal(m: BModule, s: PSym, info: TLineInfo) -> Rope:
    _ = genTypeInfoV1(m, s.loc.t, info)

    with var:
        p = newProc(None, m)
        sLoc = rdLoc(s.loc)
    result = getTempName(m)

    if TSymFlag.sfThread in s.flags and _emulatedThreadVars(m.config):
        _accessThreadLocalVar(p, s)
        sLoc = _derefField(string("NimTV_"), sLoc)

    with var:
        c = _TTraversalClosure(_p=p,
            _visitorFrmt=cIntValue(0)  # "#nimGCvisit((void*)$1, 0);$n"
            )

    _genTraverseProc(c, sLoc, s.loc.t)

    with var:
        headerBuilder = newBuilder(string(""))
    with headerBuilder._addProcHeaderWithParams(TCallingConvention.ccNimCall, result, CVoid):
        with var:
            paramBuilder = _ProcParamBuilder()
        with headerBuilder._addProcParams(paramBuilder):
            # (void)
            discard
    with let:
        header = headerBuilder.extract()

    with m.s[TCFileSection.cfsProcHeaders]._addDeclWithVisibility(_DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcHeaders].add(header)
        m.s[TCFileSection.cfsProcHeaders]._finishProcHeaderAsProto()
    with m.s[TCFileSection.cfsProcs]._addDeclWithVisibility(_DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcs].add(header)
        with m.s[TCFileSection.cfsProcs]._finishProcHeaderWithBody():
            m.s[TCFileSection.cfsProcs].add(p.s(TCProcSection.cpsLocals).extract())
            m.s[TCFileSection.cfsProcs].add(p.s(TCProcSection.cpsInit).extract())
            m.s[TCFileSection.cfsProcs].add(p.s(TCProcSection.cpsStmts).extract())
    return result
