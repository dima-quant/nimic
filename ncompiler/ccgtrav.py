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

class TTraversalClosure(Object):
    p: BProc
    visitorFrmt: string


@dispatch
def genTraverseProc(c: TTraversalClosure, accessor: Rope, typ: PType) -> None:
    pass


def genCaseRange(p: BProc, branch: PNode, info: mut@SwitchCaseBuilder) -> None:
    pass


def getTemp(p: BProc, t: PType, needsInit: bool = False) -> TLoc:
    pass


def visit(p: BProc, data: Snippet, visitor: Snippet) -> None:
    p.s(TCProcSection.cpsStmts).addCallStmt(cgsymValue(p.module, string("nimGCvisit")),
        cCast(CPointer, data),
        visitor)


@dispatch
def genTraverseProc(c: TTraversalClosure, accessor: Rope, n: PNode, typ: PType) -> None:
    if n is None:
        return
    match n.kind:
        case TNodeKind.nkRecList:
            for i in range(n.len):
                genTraverseProc(c, accessor, n[i], typ)
        case TNodeKind.nkRecCase:
            if n[0].kind != TNodeKind.nkSym:
                internalError(c.p.config, n.info, string("genTraverseProc"))
            with var:
                p = c.p
            with let:
                disc = n[0].sym
            if disc.loc.snippet == string(""):
                fillObjectFields(c.p.module, typ)
            if disc.loc.t is None:
                internalError(c.p.config, n.info, string("genTraverseProc()"))
            with let:
                discField = dotField(accessor, disc.loc.snippet)
            with p.s(TCProcSection.cpsStmts).addSwitchStmt(discField):
                for i in range(1, n.len):
                    with let:
                        branch = n[i]
                    assert branch.kind in {TNodeKind.nkOfBranch, TNodeKind.nkElse}
                    with var:
                        caseBuilder = SwitchCaseBuilder()
                    with p.s(TCProcSection.cpsStmts).addSwitchCase(caseBuilder):
                        if branch.kind == TNodeKind.nkOfBranch:
                            genCaseRange(c.p, branch, caseBuilder)
                        else:
                            p.s(TCProcSection.cpsStmts).addCaseElse(caseBuilder)
                        with do:
                            genTraverseProc(c, accessor, lastSon(branch), typ)
                            p.s(TCProcSection.cpsStmts).addBreak()
        case TNodeKind.nkSym:
            with let:
                field = n.sym
            if field.typ.kind == TTypeKind.tyVoid:
                return
            if field.loc.snippet == string(""):
                fillObjectFields(c.p.module, typ)
            if field.loc.t is None:
                internalError(c.p.config, n.info, string("genTraverseProc()"))
            genTraverseProc(c, dotField(accessor, field.loc.snippet), field.loc.t)
        case _:
            internalError(c.p.config, n.info, string("genTraverseProc()"))


@ufcs(string)
def parentObj(accessor: Rope, m: BModule) -> Rope:
    """{.inline.}"""
    if not m.compileToCpp:
        result = dotField(accessor, string("Sup"))
    else:
        result = accessor
    return result


def genTraverseProcSeq(c: TTraversalClosure, accessor: Rope, typ: PType) -> None:
    pass


@dispatch
def genTraverseProc(c: TTraversalClosure, accessor: Rope, typ: PType) -> None:
    if typ is None:
        return

    with var:
        p = c.p
    match typ.kind:
        case (TTypeKind.tyGenericInst | TTypeKind.tyGenericBody | TTypeKind.tyTypeDesc | TTypeKind.tyAlias |
              TTypeKind.tyDistinct | TTypeKind.tyInferred | TTypeKind.tySink | TTypeKind.tyOwned):
            genTraverseProc(c, accessor, skipModifier(typ))
        case TTypeKind.tyArray:
            with let:
                arraySize = lengthOrd(c.p.config, typ.indexType)
            with var:
                i: TLoc = getTemp(p, getSysType(c.p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
                oldCode = p.s(TCProcSection.cpsStmts).copy()
                oldLen = nint(0)
                newLen = nint(0)
            with p.s(TCProcSection.cpsStmts).addForRangeExclusive(i.snippet, cIntValue(0), cIntValue(arraySize)):
                oldLen = p.s(TCProcSection.cpsStmts).buf.len
                genTraverseProc(c, subscript(accessor, i.snippet), typ.elementType)
                newLen = p.s(TCProcSection.cpsStmts).buf.len
            if oldLen == newLen:
                # do not emit dummy long loops for faster debug builds:
                assign(p.s(TCProcSection.cpsStmts), oldCode)
        case TTypeKind.tyObject:
            with var:
                x = typ.baseClass
            if x is not None:
                x = x.skipTypes(skipPtrs)
            genTraverseProc(c, accessor.parentObj(c.p.module), x)
            if typ.n is not None:
                genTraverseProc(c, accessor, typ.n, typ)
        case TTypeKind.tyTuple:
            with let:
                typ = getUniqueType(typ)
            for i, a in typ.ikids():
                genTraverseProc(c, dotField(accessor, string("Field") + string(str(i))), a)
        case TTypeKind.tyRef:
            visit(p, accessor, c.visitorFrmt)
        case TTypeKind.tySequence:
            if TGlobalOption.optSeqDestructors not in c.p.module.config.globalOptions:
                visit(p, accessor, c.visitorFrmt)
            elif containsGarbageCollectedRef(typ.elementType):
                # destructor based seqs are themselves not traced but their data is, if
                # they contain a GC'ed type:
                p.s(TCProcSection.cpsStmts).addCallStmt(cgsymValue(p.module, string("nimGCvisitSeq")),
                    cCast(CPointer, accessor),
                    c.visitorFrmt)
                # genTraverseProcSeq(c, accessor, typ)
        case TTypeKind.tyString:
            if TTypeFlag.tfHasAsgn not in typ.flags:
                visit(p, accessor, c.visitorFrmt)
        case TTypeKind.tyProc:
            if typ.callConv == TCallingConvention.ccClosure:
                visit(p, dotField(accessor, string("ClE_0")), c.visitorFrmt)
        case _:
            discard


def genTraverseProcSeq(c: TTraversalClosure, accessor: Rope, typ: PType) -> None:
    with var:
        p = c.p
    assert typ.kind == TTypeKind.tySequence
    with var:
        i = getTemp(p, getSysType(c.p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
        oldCode = p.s(TCProcSection.cpsStmts).copy()
        oldLen = nint(0)
        newLen = nint(0)
        a = TLoc(snippet=accessor)
    with let:
        le = lenExpr(c.p, a)

    with p.s(TCProcSection.cpsStmts).addForRangeExclusive(i.snippet, cIntValue(0), le):
        oldLen = p.s(TCProcSection.cpsStmts).buf.len
        genTraverseProc(c, subscript(dataField(c.p, accessor), i.snippet), typ.elementType)
        newLen = p.s(TCProcSection.cpsStmts).buf.len
    if newLen == oldLen:
        # do not emit dummy long loops for faster debug builds:
        assign(p.s(TCProcSection.cpsStmts), oldCode)


@dispatch
def genTraverseProc(m: BModule, origTyp: PType, sig: SigHash) -> Rope:
    with var:
        p = newProc(None, m)
    result = string("Marker_") + getTypeName(m, origTyp, sig)
    with let:
        hcrOn = m.hcrOn
        typ = origTyp.skipTypes(abstractInstOwned)
        markerName = result + string("_actual") if hcrOn else result
        t = getTypeDesc(m, typ)

    p.s(TCProcSection.cpsLocals).addVar(kind=VarKind.Local, name=string("a"), typ=t)
    p.s(TCProcSection.cpsInit).addAssignment(string("a"), cCast(t, string("p")))

    with var:
        c = TTraversalClosure(p=p,
            visitorFrmt=string("op")  # "#nimGCvisit((void*)$1, op);$n"
            )

    assert typ.kind != TTypeKind.tyTypeDesc
    if typ.kind == TTypeKind.tySequence:
        genTraverseProcSeq(c, rope(string("a")), typ)
    else:
        if skipTypes(typ.elementType, typedescInst + TTypeKinds({TTypeKind.tyOwned})).kind == TTypeKind.tyArray:
            # C's arrays are broken beyond repair:
            genTraverseProc(c, rope(string("a")), typ.elementType)
        else:
            genTraverseProc(c, cDeref(string("a")), typ.elementType)

    with var:
        headerBuilder = newBuilder(string(""))
    with headerBuilder.addProcHeaderWithParams(TCallingConvention.ccNimCall, markerName, CVoid):
        with var:
            paramBuilder = ProcParamBuilder()
        with headerBuilder.addProcParams(paramBuilder):
            headerBuilder.addParam(paramBuilder, name=string("p"), typ=CPointer)
            headerBuilder.addParam(paramBuilder, name=string("op"), typ=NimInt)
    with let:
        header = extract(headerBuilder)

    with m.s[TCFileSection.cfsProcHeaders].addDeclWithVisibility(DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcHeaders].add(header)
        m.s[TCFileSection.cfsProcHeaders].finishProcHeaderAsProto()
    with m.s[TCFileSection.cfsProcs].addDeclWithVisibility(DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcs].add(header)
        with m.s[TCFileSection.cfsProcs].finishProcHeaderWithBody():
            m.s[TCFileSection.cfsProcs].add(extract(p.s(TCProcSection.cpsLocals)))
            m.s[TCFileSection.cfsProcs].add(extract(p.s(TCProcSection.cpsInit)))
            m.s[TCFileSection.cfsProcs].add(extract(p.s(TCProcSection.cpsStmts)))

    if hcrOn:
        with var:
            desc = newBuilder(string(""))
            unnamedParamBuilder = ProcParamBuilder()
        with desc.addProcParams(unnamedParamBuilder):
            desc.addUnnamedParam(unnamedParamBuilder, CPointer)
            desc.addUnnamedParam(unnamedParamBuilder, NimInt)
        with let:
            unnamedParams = extract(desc)
        m.s[TCFileSection.cfsProcHeaders].addProcVar(TCallingConvention.ccNimCall, result, unnamedParams, CVoid)
        with m.s[TCFileSection.cfsDynLibInit].addAssignmentWithValue(result):
            with m.s[TCFileSection.cfsDynLibInit].addCast(procPtrTypeUnnamed(TCallingConvention.ccNimCall, CVoid,
                                                                             unnamedParams)):
                m.s[TCFileSection.cfsDynLibInit].addCall(string("hcrRegisterProc"),
                    getModuleDllPath(m),
                    string("\"") + result + string("\""),
                    cCast(CPointer, markerName))
    return result


def genTraverseProcForGlobal(m: BModule, s: PSym, info: TLineInfo) -> Rope:
    _ = genTypeInfoV1(m, s.loc.t, info)

    with var:
        p = newProc(None, m)
        sLoc = rdLoc(s.loc)
    result = getTempName(m)

    if TSymFlag.sfThread in s.flags and emulatedThreadVars(m.config):
        accessThreadLocalVar(p, s)
        sLoc = derefField(string("NimTV_"), sLoc)

    with var:
        c = TTraversalClosure(p=p,
            visitorFrmt=cIntValue(0)  # "#nimGCvisit((void*)$1, 0);$n"
            )

    genTraverseProc(c, sLoc, s.loc.t)

    with var:
        headerBuilder = newBuilder(string(""))
    with headerBuilder.addProcHeaderWithParams(TCallingConvention.ccNimCall, result, CVoid):
        with var:
            paramBuilder = ProcParamBuilder()
        with headerBuilder.addProcParams(paramBuilder):
            # (void)
            discard
    with let:
        header = extract(headerBuilder)

    with m.s[TCFileSection.cfsProcHeaders].addDeclWithVisibility(DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcHeaders].add(header)
        m.s[TCFileSection.cfsProcHeaders].finishProcHeaderAsProto()
    with m.s[TCFileSection.cfsProcs].addDeclWithVisibility(DeclVisibility.StaticProc):
        m.s[TCFileSection.cfsProcs].add(header)
        with m.s[TCFileSection.cfsProcs].finishProcHeaderWithBody():
            m.s[TCFileSection.cfsProcs].add(extract(p.s(TCProcSection.cpsLocals)))
            m.s[TCFileSection.cfsProcs].add(extract(p.s(TCProcSection.cpsInit)))
            m.s[TCFileSection.cfsProcs].add(extract(p.s(TCProcSection.cpsStmts)))
    return result
