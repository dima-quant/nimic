# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from .nodekinds import *

#
#
#           The Nim Compiler
#        (c) Copyright 2013 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

## Generates traversal procs for the C backend.

# included from cgen.nim

if comptime(__name__ == "__main__"):
    class TTypeKind(NIntEnum):
        tyNone = 0
        tyBool = auto()
        tyChar = auto()
        tyEmpty = auto()
        tyNil = auto()
        tyUntyped = auto()
        tyTyped = auto()
        tyGenericInvocation = auto()
        tyGenericParam = auto()
        tyOrdinal = auto()
        tyOpenArray = auto()
        tyForward = auto()
        tyVarargs = auto()
        tyUncheckedArray = auto()
        tyError = auto()
        tyBuiltInTypeClass = auto()
        tyUserTypeClass = auto()
        tyUserTypeClassInst = auto()
        tyCompositeTypeClass = auto()
        tyAnd = auto()
        tyOr = auto()
        tyNot = auto()
        tyAnything = auto()
        tyStatic = auto()
        tyFromExpr = auto()
        tyConcept = auto()
        tyVoid = auto()
        tyIterable = auto()
        tyEnum = auto()
        tyRange = auto()
        tyInt = auto()
        tyInt8 = auto()
        tyInt16 = auto()
        tyInt32 = auto()
        tyInt64 = auto()
        tyFloat = auto()
        tyFloat32 = auto()
        tyFloat64 = auto()
        tyFloat128 = auto()
        tyUInt = auto()
        tyUInt8 = auto()
        tyUInt16 = auto()
        tyUInt32 = auto()
        tyUInt64 = auto()
        tyCstring = auto()
        tyPointer = auto()
        tyPtr = auto()
        tyVar = auto()
        tyLent = auto()
        tySet = auto()
        tyGenericInst = auto()
        tyGenericBody = auto()
        tyTypeDesc = auto()
        tyAlias = auto()
        tyDistinct = auto()
        tyInferred = auto()
        tySink = auto()
        tyOwned = auto()
        tyArray = auto()
        tyObject = auto()
        tyTuple = auto()
        tyString = auto()
        tyRef = auto()
        tySequence = auto()
        tyProc = auto()

    class TSymFlag(NIntEnum):
        sfThread = 0
        sfCompileToCpp = auto()
        sfImportc = auto()

    class TTypeFlag(NIntEnum):
        tfHasAsgn = 0

    class TCProcSection(NIntEnum):
        cpsLocals = 0
        cpsInit = auto()
        cpsStmts = auto()

    class TCFileSection(NIntEnum):
        cfsProcHeaders = 0
        cfsProcs = auto()
        cfsDynLibInit = auto()
        cfsVars = auto()
        cfsSeqTypes = auto()
        cfsCount = auto()

    class TCallingConvention(NIntEnum):
        ccDefault = 0
        ccNimCall = auto()
        ccClosure = auto()

    class TGlobalOption(NIntEnum):
        optSeqDestructors = 0
        optThreads = auto()
        optTlsEmulation = auto()

    class DeclVisibility(NIntEnum):
        None_ = 0
        Extern = auto()
        ExternC = auto()
        ExportLibVar = auto()
        Private = auto()
        StaticProc = auto()

    class VarKind(NIntEnum):
        Local = 0
        Threadvar = auto()

    if not comptime(defined("c")):
        cpsLocals = TCProcSection.cpsLocals
        cpsInit = TCProcSection.cpsInit
        cpsStmts = TCProcSection.cpsStmts
        cfsProcHeaders = TCFileSection.cfsProcHeaders
        cfsProcs = TCFileSection.cfsProcs
        cfsDynLibInit = TCFileSection.cfsDynLibInit
        ccClosure = TCallingConvention.ccClosure
        ccNimCall = TCallingConvention.ccNimCall
        StaticProc = DeclVisibility.StaticProc
        Local = VarKind.Local
        optSeqDestructors = TGlobalOption.optSeqDestructors
        optThreads = TGlobalOption.optThreads
        optTlsEmulation = TGlobalOption.optTlsEmulation
        tfHasAsgn = TTypeFlag.tfHasAsgn
        sfThread = TSymFlag.sfThread

    with const:
        NimNil = string("NIM_NIL")
        CPointer = string("void*")
        CVoid = string("void")
        NimInt = string("NI")
        unknownLineInfo = 0
        skipPtrs = Tset[TTypeKind]({TTypeKind.tyPtr, TTypeKind.tyRef})
        abstractInstOwned = Tset[TTypeKind]({
            TTypeKind.tyGenericInst,
            TTypeKind.tyGenericBody,
            TTypeKind.tyDistinct,
            TTypeKind.tyAlias,
            TTypeKind.tySink,
            TTypeKind.tyOwned,
        })
        typedescInst = Tset[TTypeKind]({
            TTypeKind.tyGenericInst,
            TTypeKind.tyDistinct,
            TTypeKind.tyAlias,
        })

    if comptime(defined("c")):
        class Rope(string):
            pass

        class Snippet(string):
            pass

        class SigHash(uint64):
            pass

        class TLineInfo(nint):
            pass

    if not comptime(defined("c")):
        Rope = string
        Snippet = string
        SigHash = uint64
        TLineInfo = nint

    @ref
    class SwitchCaseBuilder(Object):
        state: nint

    @ref
    class ProcParamBuilder(Object):
        needsComma: bool

    class Builder(Object):
        lines: seq[string]
        buf: string
        indents: nint

        def add(self: mut@Builder, s: string) -> None:
            self.lines.add(s)
            self.buf = self.buf + s

        def addCallStmt(self: mut@Builder, fn: string, a1: string = string(""), a2: string = string("")) -> None:
            with var:
                s = fn + string("(") + a1
            if len(a2) > 0:
                s = s + string(", ") + a2
            s = s + string(");")
            self.lines.add(s)
            self.buf = self.buf + s

        def addVar(self: mut@Builder, kind: VarKind, name: string, typ: string) -> None:
            self.lines.add(string("var ") + name + string(": ") + typ)

        def addAssignment(self: mut@Builder, target: string, val: string) -> None:
            self.lines.add(target + string(" = ") + val + string(";"))

        def addProcVar(self: mut@Builder, callConv: TCallingConvention, name: string, params: string, rettype: string) -> None:
            self.lines.add(string("procVar ") + name)

        def addCall(self: mut@Builder, fn: string, a1: string = string(""), a2: string = string(""), a3: string = string(""), a4: string = string("")) -> None:
            with var:
                s = fn + string("(") + a1
            if len(a2) > 0:
                s = s + string(", ") + a2
            if len(a3) > 0:
                s = s + string(", ") + a3
            if len(a4) > 0:
                s = s + string(", ") + a4
            s = s + string(")")
            self.lines.add(s)

        def addCaseElse(self: mut@Builder, info: SwitchCaseBuilder) -> None:
            self.lines.add(string("default:"))

        def addBreak(self: mut@Builder) -> None:
            self.lines.add(string("break;"))

        def finishProcHeaderAsProto(self: mut@Builder) -> None:
            self.lines.add(string("proto;"))

        def addParam(self: mut@Builder, paramBuilder: ProcParamBuilder, name: string, typ: string) -> None:
            self.lines.add(string("param ") + name + string(": ") + typ)

        def addUnnamedParam(self: mut@Builder, paramBuilder: ProcParamBuilder, typ: string) -> None:
            self.lines.add(string("unnamedParam ") + typ)

        def copy(self) -> Builder:
            with var:
                res = Builder()
            res.lines = seq[string]()
            for l in self.lines:
                res.lines.add(l)
            res.buf = self.buf
            res.indents = self.indents
            return res

    if comptime(defined("c")):
        @template
        def addSwitchStmt(self: Builder, disc: untyped, body: untyped) -> untyped:
            self.lines.add(string("switch (") + disc + string(")"))
            return body

        @template
        def addForRangeExclusive(self: Builder, iterName: untyped, start: untyped, stop: untyped, body: untyped) -> untyped:
            self.lines.add(string("for (") + iterName + string("; ") + start + string("; ") + stop + string(")"))
            return body

        @template
        def addSwitchCase(self: Builder, info: untyped, caseBody: untyped, body: untyped) -> untyped:
            self.lines.add(string("case"))
            caseBody
            return body

        @template
        def addProcHeaderWithParams(self: Builder, callConv: untyped, name: untyped, rettype: untyped, body: untyped) -> untyped:
            self.lines.add(string("header(") + name + string(")"))
            return body

        @template
        def addProcParams(self: Builder, paramBuilder: untyped, body: untyped) -> untyped:
            return body

        @template
        def addDeclWithVisibility(self: Builder, vis: untyped, body: untyped) -> untyped:
            return body

        @template
        def finishProcHeaderWithBody(self: Builder, body: untyped) -> untyped:
            return body

        @template
        def addAssignmentWithValue(self: Builder, target: untyped, body: untyped) -> untyped:
            self.lines.add(string("assignWithValue ") + target)
            return body

        @template
        def addCast(self: Builder, typ: untyped, body: untyped) -> untyped:
            self.lines.add(string("cast ") + typ)
            return body

    if not comptime(defined("c")):
        def _py_addSwitchStmt(self: Builder, disc: string) -> Builder:
            self.lines.add(string("switch (") + disc + string(")"))
            return self
        Builder.addSwitchStmt = _py_addSwitchStmt

        def _py_addForRangeExclusive(self: Builder, iterName: string, start: string, stop: string) -> Builder:
            self.lines.add(string("for (") + iterName + string("; ") + start + string("; ") + stop + string(")"))
            return self
        Builder.addForRangeExclusive = _py_addForRangeExclusive

        def _py_addSwitchCase(self: Builder, info: SwitchCaseBuilder) -> Builder:
            self.lines.add(string("case"))
            return self
        Builder.addSwitchCase = _py_addSwitchCase

        def _py_addProcHeaderWithParams(self: Builder, callConv: TCallingConvention, name: string, rettype: string) -> Builder:
            self.lines.add(string("header(") + name + string(")"))
            return self
        Builder.addProcHeaderWithParams = _py_addProcHeaderWithParams

        def _py_addProcParams(self: Builder, paramBuilder: ProcParamBuilder) -> Builder:
            return self
        Builder.addProcParams = _py_addProcParams

        def _py_addDeclWithVisibility(self: Builder, vis: DeclVisibility) -> Builder:
            return self
        Builder.addDeclWithVisibility = _py_addDeclWithVisibility

        def _py_finishProcHeaderWithBody(self: Builder) -> Builder:
            return self
        Builder.finishProcHeaderWithBody = _py_finishProcHeaderWithBody

        def _py_addAssignmentWithValue(self: Builder, target: string) -> Builder:
            self.lines.add(string("assignWithValue ") + target)
            return self
        Builder.addAssignmentWithValue = _py_addAssignmentWithValue

        def _py_addCast(self: Builder, typ: string) -> Builder:
            self.lines.add(string("cast ") + typ)
            return self
        Builder.addCast = _py_addCast

        setattr(Builder, "__enter__", lambda self: self)
        setattr(Builder, "__exit__", lambda self, *args: False)

    @ref
    class ConfigRef(Object):
        globalOptions: Tset[TGlobalOption]

    @ref
    class TLoc(Object):
        snippet: string
        t: PType

    @ref
    class PSym(Object):
        typ: PType
        loc: TLoc
        flags: Tset[TSymFlag]

    @ref
    class PNode(Object):
        kind: TNodeKind
        info: nint
        sym: PSym
        sons: seq[PNode]

        def __getitem__(self, i: nint) -> PNode:
            return self.sons[i]

        def __setitem__(self, i: nint, v: PNode):
            self.sons[i] = v

        @property
        def len(self) -> nint:
            return self.sons.len

    @ref
    class PType(Object):
        kind: TTypeKind
        flags: Tset[TTypeFlag]
        elementType: PType
        indexType: PType
        baseClass: PType
        sons: seq[PType]
        n: PNode
        sym: PSym
        callConv: TCallingConvention

    def ikids(t: PType) -> tuple[nint, PType]:
        for i in range(t.sons.len):
            yield (i, t.sons[i])

    @ref
    class BGraph(Object):
        pass

    @ref
    class BModuleList(Object):
        graph: BGraph

    @ref
    class BModule(Object):
        g: BModuleList
        config: ConfigRef
        hcrOn: bool
        compileToCpp: bool
        s: array[TCFileSection, Builder]

    @ref
    class BProc(Object):
        module: BModule
        config: ConfigRef
        builder: Builder
        sections: array[TCProcSection, Builder]

        def s(self, sec: TCProcSection) -> mut @ Builder:
            return self.sections[sec]

    def dotField(accessor: Rope, field: string) -> Rope:
        return accessor + string(".") + field

    def subscript(accessor: Rope, idx: string) -> Rope:
        return accessor + string("[") + idx + string("]")

    def cIntValue(val: nint) -> string:
        return string(str(val))

    def cgsymValue(m: BModule, name: string) -> string:
        return name

    def cCast(tp: string, expr: string) -> string:
        return string("(") + tp + string(")") + expr

    def cDeref(expr: string) -> string:
        return string("(*") + expr + string(")")

    def derefField(field: string, sLoc: Rope) -> Rope:
        return field + string("->") + sLoc

    def getTypeDesc(m: BModule, t: PType) -> string:
        return string("TypeDesc")

    def getTypeName(m: BModule, origTyp: PType, sig: SigHash) -> string:
        return string("TypeName")

    def getUniqueType(t: PType) -> PType:
        return t

    def lengthOrd(c: ConfigRef, t: PType) -> nint:
        return 10

    def getTemp(p: BProc, t: PType, needsInit: bool = False) -> TLoc:
        with var:
            loc = TLoc()
        loc.snippet = string("tmp_i")
        loc.t = t
        return loc

    def getTempName(m: BModule) -> Rope:
        return string("tmp_global")

    def getSysType(g: BGraph, info: nint, kind: TTypeKind) -> PType:
        with var:
            t = PType()
        t.kind = kind
        t.sons = seq[PType]()
        return t

    def skipModifier(t: PType) -> PType:
        return t.elementType if t.elementType is not None else t

    def skipTypes(t: PType, kinds: Tset[TTypeKind]) -> PType:
        with var:
            curr = t
        while curr is not None and curr.kind in kinds:
            curr = curr.elementType
        return curr

    def fillObjectFields(m: BModule, typ: PType) -> None:
        return

    def genCaseRange(p: BProc, branch: PNode, caseBuilder: SwitchCaseBuilder) -> None:
        p.s(cpsStmts).lines.add(string("genCaseRange"))

    def lastSon(n: PNode) -> PNode:
        return n.sons[n.sons.len - 1]

    def rdLoc(a: TLoc) -> Rope:
        return a.snippet

    def internalError(conf: ConfigRef, info: nint, msg: string) -> None:
        raiseAssert(msg)

    def containsGarbageCollectedRef(t: PType) -> bool:
        if t is None:
            return False
        return t.kind in {TTypeKind.tyRef, TTypeKind.tySequence, TTypeKind.tyString}

    def lenExpr(p: BProc, a: TLoc) -> string:
        return string("len(") + a.snippet + string(")")

    def dataField(p: BProc, accessor: Rope) -> Rope:
        return accessor + string(".data")

    def newProc(prc: PSym, module: BModule) -> BProc:
        with var:
            p = BProc()
        p.module = module
        p.config = module.config
        with var:
            s_arr = array[TCProcSection, Builder]()
        s_arr[cpsLocals] = Builder()
        s_arr[cpsLocals].lines = seq[string]()
        s_arr[cpsLocals].buf = string("")
        s_arr[cpsInit] = Builder()
        s_arr[cpsInit].lines = seq[string]()
        s_arr[cpsInit].buf = string("")
        s_arr[cpsStmts] = Builder()
        s_arr[cpsStmts].lines = seq[string]()
        s_arr[cpsStmts].buf = string("")
        p.sections = s_arr
        return p

    def newBuilder(s: string) -> Builder:
        with var:
            b = Builder()
        b.lines = seq[string]()
        b.buf = s
        b.indents = 0
        return b

    def extract(builder: Builder) -> string:
        return builder.buf

    def rope(s: string) -> Rope:
        return s

    def procPtrTypeUnnamed(callConv: TCallingConvention, rettype: string, params: string) -> string:
        return string("procPtr")

    def getModuleDllPath(m: BModule) -> string:
        return string("mod.dll")

    def genTypeInfoV1(m: BModule, t: PType, info: TLineInfo) -> Rope:
        return string("TypeInfo")

    def emulatedThreadVars(conf: ConfigRef) -> bool:
        return (optThreads in conf.globalOptions) and (optTlsEmulation in conf.globalOptions)

    def accessThreadLocalVar(p: BProc, s: PSym) -> None:
        return


class TTraversalClosure(Object):
    p: BProc
    visitorFrmt: string


@dispatch
def genTraverseProc(c: TTraversalClosure, accessor: Rope, typ: PType) -> None:
    pass


if comptime(not (__name__ == "__main__")):
    def genCaseRange(p: BProc, branch: PNode, info: mut@SwitchCaseBuilder) -> None:
        pass

    def getTemp(p: BProc, t: PType, needsInit: bool = False) -> TLoc:
        pass


if comptime(defined("c")):
    @template
    def restore(a: untyped, b: untyped) -> untyped:
        a = b

if not comptime(defined("c")):
    def restore(a: Builder, b: Builder) -> None:
        a.buf = b.buf
        a.indents = b.indents
        with var:
            new_lines = seq[string]()
        for l in b.lines:
            new_lines.add(l)
        a.lines = new_lines


def visit(p: BProc, data: Snippet, visitor: Snippet) -> None:
    p.s(cpsStmts).addCallStmt(
        cgsymValue(p.module, string("nimGCvisit")),
        cCast(CPointer, data),
        visitor,
    )


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
            with p.s(cpsStmts).addSwitchStmt(discField):
                for i in inrange(1, n.len - 1):
                    with let:
                        branch = n[i]
                    assert branch.kind in {TNodeKind.nkOfBranch, TNodeKind.nkElse}
                    with var:
                        caseBuilder = SwitchCaseBuilder()
                    with p.s(cpsStmts).addSwitchCase(caseBuilder):
                        if branch.kind == TNodeKind.nkOfBranch:
                            genCaseRange(c.p, branch, caseBuilder)
                        else:
                            p.s(cpsStmts).addCaseElse(caseBuilder)
                        with do:
                            genTraverseProc(c, accessor, lastSon(branch), typ)
                            p.s(cpsStmts).addBreak()
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
        case (
            TTypeKind.tyGenericInst
            | TTypeKind.tyGenericBody
            | TTypeKind.tyTypeDesc
            | TTypeKind.tyAlias
            | TTypeKind.tyDistinct
            | TTypeKind.tyInferred
            | TTypeKind.tySink
            | TTypeKind.tyOwned
        ):
            genTraverseProc(c, accessor, skipModifier(typ))
        case TTypeKind.tyArray:
            with let:
                arraySize = lengthOrd(c.p.config, typ.indexType)
            with var:
                i: TLoc = getTemp(p, getSysType(c.p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
                oldCode = p.s(cpsStmts).copy()
                oldLen = 0
                newLen = 0
            with p.s(cpsStmts).addForRangeExclusive(i.snippet, cIntValue(0), cIntValue(arraySize)):
                oldLen = len(p.s(cpsStmts).buf)
                genTraverseProc(c, subscript(accessor, i.snippet), typ.elementType)
                newLen = len(p.s(cpsStmts).buf)
            if oldLen == newLen:
                # do not emit dummy long loops for faster debug builds:
                restore(p.s(cpsStmts), oldCode)
        case TTypeKind.tyObject:
            with var:
                x = typ.baseClass
            if x is not None:
                x = skipTypes(x, skipPtrs)
            genTraverseProc(c, parentObj(accessor, c.p.module), x)
            if typ.n is not None:
                genTraverseProc(c, accessor, typ.n, typ)
        case TTypeKind.tyTuple:
            with let:
                u_typ = getUniqueType(typ)
            for i, a in ikids(u_typ):
                genTraverseProc(c, dotField(accessor, string("Field") + string(str(i))), a)
        case TTypeKind.tyRef:
            visit(p, accessor, c.visitorFrmt)
        case TTypeKind.tySequence:
            if optSeqDestructors not in c.p.module.config.globalOptions:
                visit(p, accessor, c.visitorFrmt)
            elif containsGarbageCollectedRef(typ.elementType):
                # destructor based seqs are themselves not traced but their data is, if
                # they contain a GC'ed type:
                p.s(cpsStmts).addCallStmt(
                    cgsymValue(p.module, string("nimGCvisitSeq")),
                    cCast(CPointer, accessor),
                    c.visitorFrmt,
                )
                # genTraverseProcSeq(c, accessor, typ)
        case TTypeKind.tyString:
            if tfHasAsgn not in typ.flags:
                visit(p, accessor, c.visitorFrmt)
        case TTypeKind.tyProc:
            if typ.callConv == ccClosure:
                visit(p, dotField(accessor, string("ClE_0")), c.visitorFrmt)
        case _:
            pass


def genTraverseProcSeq(c: TTraversalClosure, accessor: Rope, typ: PType) -> None:
    with var:
        p = c.p
    assert typ.kind == TTypeKind.tySequence
    with var:
        i = getTemp(p, getSysType(c.p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
        oldCode = p.s(cpsStmts).copy()
        oldLen = 0
        newLen = 0
        a = TLoc(snippet=accessor)
    with let:
        le = lenExpr(c.p, a)

    with p.s(cpsStmts).addForRangeExclusive(i.snippet, cIntValue(0), le):
        oldLen = len(p.s(cpsStmts).buf)
        genTraverseProc(c, subscript(dataField(c.p, accessor), i.snippet), typ.elementType)
        newLen = len(p.s(cpsStmts).buf)
    if newLen == oldLen:
        # do not emit dummy long loops for faster debug builds:
        restore(p.s(cpsStmts), oldCode)


@dispatch
def genTraverseProc(m: BModule, origTyp: PType, sig: SigHash) -> Rope:
    with var:
        p = newProc(None, m)
    result = string("Marker_") + getTypeName(m, origTyp, sig)
    with let:
        hcrOn = m.hcrOn
        typ = skipTypes(origTyp, abstractInstOwned)
        markerName = (result + string("_actual")) if hcrOn else result
        t = getTypeDesc(m, typ)

    p.s(cpsLocals).addVar(kind=Local, name=string("a"), typ=t)
    p.s(cpsInit).addAssignment(string("a"), cCast(t, string("p")))

    with var:
        c = TTraversalClosure(p=p, visitorFrmt=string("op"))

    assert typ.kind != TTypeKind.tyTypeDesc
    if typ.kind == TTypeKind.tySequence:
        genTraverseProcSeq(c, rope(string("a")), typ)
    else:
        if skipTypes(typ.elementType, typedescInst + Tset[TTypeKind]({TTypeKind.tyOwned})).kind == TTypeKind.tyArray:
            # C's arrays are broken beyond repair:
            genTraverseProc(c, rope(string("a")), typ.elementType)
        else:
            genTraverseProc(c, cDeref(string("a")), typ.elementType)

    with var:
        headerBuilder = newBuilder(string(""))
    with headerBuilder.addProcHeaderWithParams(ccNimCall, markerName, CVoid):
        with var:
            paramBuilder = ProcParamBuilder()
        with headerBuilder.addProcParams(paramBuilder):
            headerBuilder.addParam(paramBuilder, name=string("p"), typ=CPointer)
            headerBuilder.addParam(paramBuilder, name=string("op"), typ=NimInt)
    with let:
        header = extract(headerBuilder)

    with m.s[cfsProcHeaders].addDeclWithVisibility(StaticProc):
        m.s[cfsProcHeaders].add(header)
        m.s[cfsProcHeaders].finishProcHeaderAsProto()
    with m.s[cfsProcs].addDeclWithVisibility(StaticProc):
        m.s[cfsProcs].add(header)
        with m.s[cfsProcs].finishProcHeaderWithBody():
            m.s[cfsProcs].add(extract(p.s(cpsLocals)))
            m.s[cfsProcs].add(extract(p.s(cpsInit)))
            m.s[cfsProcs].add(extract(p.s(cpsStmts)))

    if hcrOn:
        with var:
            desc = newBuilder(string(""))
            unnamedParamBuilder = ProcParamBuilder()
        with desc.addProcParams(unnamedParamBuilder):
            desc.addUnnamedParam(unnamedParamBuilder, CPointer)
            desc.addUnnamedParam(unnamedParamBuilder, NimInt)
        with let:
            unnamedParams = extract(desc)
        m.s[cfsProcHeaders].addProcVar(ccNimCall, result, unnamedParams, CVoid)
        with m.s[cfsDynLibInit].addAssignmentWithValue(result):
            with m.s[cfsDynLibInit].addCast(procPtrTypeUnnamed(ccNimCall, CVoid, unnamedParams)):
                m.s[cfsDynLibInit].addCall(
                    string("hcrRegisterProc"),
                    getModuleDllPath(m),
                    string("\"") + result + string("\""),
                    cCast(CPointer, markerName),
                )
    return result


def genTraverseProcForGlobal(m: BModule, s: PSym, info: TLineInfo) -> Rope:
    _ = genTypeInfoV1(m, s.loc.t, info)

    with var:
        p = newProc(None, m)
        sLoc = rdLoc(s.loc)
    result = getTempName(m)

    if sfThread in s.flags and emulatedThreadVars(m.config):
        accessThreadLocalVar(p, s)
        sLoc = derefField(string("NimTV_"), sLoc)

    with var:
        c = TTraversalClosure(p=p, visitorFrmt=cIntValue(0))

    genTraverseProc(c, sLoc, s.loc.t)

    with var:
        headerBuilder = newBuilder(string(""))
    with headerBuilder.addProcHeaderWithParams(ccNimCall, result, CVoid):
        with var:
            paramBuilder = ProcParamBuilder()
        with headerBuilder.addProcParams(paramBuilder):
            # (void)
            pass
    with let:
        header = extract(headerBuilder)

    with m.s[cfsProcHeaders].addDeclWithVisibility(StaticProc):
        m.s[cfsProcHeaders].add(header)
        m.s[cfsProcHeaders].finishProcHeaderAsProto()
    with m.s[cfsProcs].addDeclWithVisibility(StaticProc):
        m.s[cfsProcs].add(header)
        with m.s[cfsProcs].finishProcHeaderWithBody():
            m.s[cfsProcs].add(extract(p.s(cpsLocals)))
            m.s[cfsProcs].add(extract(p.s(cpsInit)))
            m.s[cfsProcs].add(extract(p.s(cpsStmts)))
    return result


if comptime(__name__ == "__main__"):
    echo(string("Running ccgtrav tests..."))

    # Factory helpers for tests
    def makeSymNode(name: string, typ: PType, snippet: string) -> PNode:
        with var:
            loc = TLoc()
            sym = PSym()
            n = PNode()
        loc.snippet = snippet
        loc.t = typ
        sym.typ = typ
        sym.loc = loc
        sym.flags = Tset[TSymFlag]()
        n.kind = TNodeKind.nkSym
        n.sym = sym
        n.sons = seq[PNode]()
        return n

    with var:
        graph = BGraph()
        mList = BModuleList()
    mList.graph = graph

    with var:
        conf = ConfigRef()
    conf.globalOptions = Tset[TGlobalOption]()

    with var:
        module = BModule()
    module.g = mList
    module.config = conf
    module.hcrOn = False
    module.compileToCpp = False
    with var:
        s_arr = array[TCFileSection, Builder]()
    for s_idx in [
        cfsProcHeaders,
        cfsProcs,
        cfsDynLibInit,
        TCFileSection.cfsVars,
        TCFileSection.cfsSeqTypes,
        TCFileSection.cfsCount,
    ]:
        s_arr[s_idx] = Builder()
        s_arr[s_idx].lines = seq[string]()
        s_arr[s_idx].buf = string("")
    module.s = s_arr

    with var:
        procObj = newProc(None, module)
        closure = TTraversalClosure(p=procObj, visitorFrmt=string("op"))

    # Test 1: visit procedure
    visit(procObj, string("dataPtr"), string("visitorOp"))
    doAssert(procObj.s(cpsStmts).lines.len == 1, string("visit lines count"))
    doAssert(
        procObj.s(cpsStmts).lines[0] == string("nimGCvisit((void*)dataPtr, visitorOp);"),
        string("visit output"),
    )

    # Test 2: parentObj procedure
    doAssert(parentObj(string("acc"), module) == string("acc.Sup"), string("parentObj C"))
    module.compileToCpp = True
    doAssert(parentObj(string("acc"), module) == string("acc"), string("parentObj C++"))
    module.compileToCpp = False

    # Test 3: genTraverseProc for ref type
    with var:
        refType = PType()
    refType.kind = TTypeKind.tyRef
    refType.sons = seq[PType]()
    genTraverseProc(closure, string("x"), refType)
    doAssert(procObj.s(cpsStmts).lines.len == 2, string("tyRef lines count"))
    doAssert(
        procObj.s(cpsStmts).lines[1] == string("nimGCvisit((void*)x, op);"),
        string("tyRef output"),
    )

    # Test 4: genTraverseProc for tyString (without and with tfHasAsgn)
    with var:
        strType = PType()
    strType.kind = TTypeKind.tyString
    strType.flags = Tset[TTypeFlag]()
    strType.sons = seq[PType]()
    genTraverseProc(closure, string("s1"), strType)
    doAssert(procObj.s(cpsStmts).lines.len == 3, string("tyString without tfHasAsgn"))
    doAssert(
        procObj.s(cpsStmts).lines[2] == string("nimGCvisit((void*)s1, op);"),
        string("tyString output"),
    )

    strType.flags = {tfHasAsgn}
    genTraverseProc(closure, string("s2"), strType)
    doAssert(procObj.s(cpsStmts).lines.len == 3, string("tyString with tfHasAsgn should be skipped"))

    # Test 5: genTraverseProc for tyProc (closure vs non-closure)
    with var:
        procType = PType()
    procType.kind = TTypeKind.tyProc
    procType.callConv = ccClosure
    procType.sons = seq[PType]()
    genTraverseProc(closure, string("prc"), procType)
    doAssert(procObj.s(cpsStmts).lines.len == 4, string("tyProc closure lines"))
    doAssert(
        procObj.s(cpsStmts).lines[3] == string("nimGCvisit((void*)prc.ClE_0, op);"),
        string("tyProc closure output"),
    )

    procType.callConv = TCallingConvention.ccDefault
    genTraverseProc(closure, string("prc2"), procType)
    doAssert(procObj.s(cpsStmts).lines.len == 4, string("tyProc non-closure skipped"))

    # Test 6: genTraverseProc for tyTuple
    with var:
        tupleType = PType()
    tupleType.kind = TTypeKind.tyTuple
    tupleType.sons = seq[PType]([refType, procType])
    genTraverseProc(closure, string("tup"), tupleType)
    doAssert(procObj.s(cpsStmts).lines.len == 5, string("tyTuple lines"))
    doAssert(
        procObj.s(cpsStmts).lines[4] == string("nimGCvisit((void*)tup.Field0, op);"),
        string("tyTuple output"),
    )

    # Test 7: genTraverseProc for tySequence without optSeqDestructors
    with var:
        seqType = PType()
    seqType.kind = TTypeKind.tySequence
    seqType.elementType = refType
    seqType.sons = seq[PType]()
    genTraverseProc(closure, string("sq"), seqType)
    doAssert(procObj.s(cpsStmts).lines.len == 6, string("tySequence optSeqDestructors off"))
    doAssert(
        procObj.s(cpsStmts).lines[5] == string("nimGCvisit((void*)sq, op);"),
        string("tySequence output"),
    )

    # Test 8: genTraverseProc for tySequence with optSeqDestructors and GC'ed element
    conf.globalOptions = {optSeqDestructors}
    genTraverseProc(closure, string("sq2"), seqType)
    doAssert(procObj.s(cpsStmts).lines.len == 7, string("tySequence with optSeqDestructors"))
    doAssert(
        procObj.s(cpsStmts).lines[6] == string("nimGCvisitSeq((void*)sq2, op);"),
        string("nimGCvisitSeq output"),
    )

    # Test 9: genTraverseProc for tySequence with optSeqDestructors and non-GC element (e.g. tyInt)
    with var:
        intType = PType()
    intType.kind = TTypeKind.tyInt
    intType.sons = seq[PType]()
    with var:
        intSeqType = PType()
    intSeqType.kind = TTypeKind.tySequence
    intSeqType.elementType = intType
    intSeqType.sons = seq[PType]()
    genTraverseProc(closure, string("sq3"), intSeqType)
    doAssert(procObj.s(cpsStmts).lines.len == 7, string("tySequence non-GC element skipped"))
    conf.globalOptions = Tset[TGlobalOption]()

    # Test 10: genTraverseProc on tyArray with dummy rollback
    with var:
        arrType = PType()
    arrType.kind = TTypeKind.tyArray
    arrType.elementType = intType
    arrType.indexType = intType
    arrType.sons = seq[PType]()
    with var:
        lenBefore = procObj.s(cpsStmts).lines.len
    genTraverseProc(closure, string("arr1"), arrType)
    doAssert(procObj.s(cpsStmts).lines.len == lenBefore, string("tyArray dummy loop rolled back"))

    # Test 11: genTraverseProc on tyArray with ref element
    arrType.elementType = refType
    genTraverseProc(closure, string("arr2"), arrType)
    doAssert(procObj.s(cpsStmts).lines.len == lenBefore + 2, string("tyArray active loop emitted"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore] == string("for (tmp_i; 0; 10)"), string("array loop header"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 1] == string("nimGCvisit((void*)arr2[tmp_i], op);"), string("array element visit"))

    # Test 12: genTraverseProc on AST (nkRecList and nkSym)
    with var:
        field1 = makeSymNode(string("f1"), refType, string("f1"))
        fieldVoid = makeSymNode(string("fVoid"), PType(kind=TTypeKind.tyVoid, sons=seq[PType]()), string("fVoid"))
        recList = PNode()
    recList.kind = TNodeKind.nkRecList
    recList.sons = seq[PNode]([field1, fieldVoid])

    with var:
        objType = PType()
    objType.kind = TTypeKind.tyObject
    objType.n = recList
    objType.sons = seq[PType]()

    lenBefore = procObj.s(cpsStmts).lines.len
    genTraverseProc(closure, string("o"), recList, objType)
    doAssert(procObj.s(cpsStmts).lines.len == lenBefore + 1, string("nkRecList visit count"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore] == string("nimGCvisit((void*)o.f1, op);"), string("nkRecList f1"))

    # Test 13: genTraverseProc on AST (nkRecCase with nkOfBranch and nkElse)
    with var:
        discSym = makeSymNode(string("kind"), intType, string("kind"))
        ofBranch = PNode()
    ofBranch.kind = TNodeKind.nkOfBranch
    ofBranch.sons = seq[PNode]([makeSymNode(string("branchF"), refType, string("branchF"))])

    with var:
        elseBranch = PNode()
    elseBranch.kind = TNodeKind.nkElse
    elseBranch.sons = seq[PNode]([makeSymNode(string("elseF"), refType, string("elseF"))])

    with var:
        recCase = PNode()
    recCase.kind = TNodeKind.nkRecCase
    recCase.sons = seq[PNode]([discSym, ofBranch, elseBranch])

    lenBefore = procObj.s(cpsStmts).lines.len
    genTraverseProc(closure, string("o"), recCase, objType)
    doAssert(procObj.s(cpsStmts).lines[lenBefore] == string("switch (o.kind)"), string("switch discField"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 1] == string("case"), string("case header"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 2] == string("genCaseRange"), string("genCaseRange call"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 3] == string("nimGCvisit((void*)o.branchF, op);"), string("branch visit"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 4] == string("break;"), string("branch break"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 5] == string("case"), string("else case header"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 6] == string("default:"), string("else default"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 7] == string("nimGCvisit((void*)o.elseF, op);"), string("else visit"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 8] == string("break;"), string("else break"))

    # Test 14: genTraverseProc on object with baseClass inheritance
    with var:
        baseObjType = PType()
    baseObjType.kind = TTypeKind.tyObject
    baseObjType.n = recList
    baseObjType.sons = seq[PType]()

    with var:
        derivedObjType = PType()
    derivedObjType.kind = TTypeKind.tyObject
    derivedObjType.baseClass = baseObjType
    derivedObjType.sons = seq[PType]()

    lenBefore = procObj.s(cpsStmts).lines.len
    genTraverseProc(closure, string("o"), derivedObjType)
    doAssert(procObj.s(cpsStmts).lines.len == lenBefore + 1, string("baseClass inheritance traversal"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore] == string("nimGCvisit((void*)o.Sup.f1, op);"), string("Sup traversal"))

    # Test 15: genTraverseProcSeq directly
    lenBefore = procObj.s(cpsStmts).lines.len
    genTraverseProcSeq(closure, string("mySeq"), seqType)
    doAssert(procObj.s(cpsStmts).lines.len == lenBefore + 2, string("genTraverseProcSeq active loop"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore] == string("for (tmp_i; 0; len(mySeq))"), string("seq for loop"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore + 1] == string("nimGCvisit((void*)mySeq.data[tmp_i], op);"), string("seq item visit"))

    # Test 16: genTraverseProc(m, origTyp, sig) without HCR
    with var:
        rootType = PType()
    rootType.kind = TTypeKind.tyObject
    rootType.elementType = refType
    rootType.sons = seq[PType]()

    with var:
        marker = genTraverseProc(module, rootType, u64(12345))
    doAssert(marker == string("Marker_TypeName"), string("marker name"))
    doAssert(module.s[cfsProcHeaders].lines.len >= 1, string("procHeaders populated"))
    doAssert(module.s[cfsProcs].lines.len >= 1, string("procs populated"))

    # Test 17: genTraverseProc(m, origTyp, sig) with HCR enabled
    module.hcrOn = True
    with var:
        markerHcr = genTraverseProc(module, rootType, u64(12345))
    doAssert(markerHcr == string("Marker_TypeName"), string("markerHcr name"))
    doAssert(module.s[cfsDynLibInit].lines.len >= 1, string("cfsDynLibInit populated with HCR"))
    module.hcrOn = False

    # Test 18: genTraverseProcForGlobal without thread vars
    with var:
        globalSym = PSym()
    globalSym.flags = Tset[TSymFlag]()
    globalSym.loc = TLoc(snippet=string("gVar"), t=refType)
    with var:
        globRes = genTraverseProcForGlobal(module, globalSym, 0)
    doAssert(globRes == string("tmp_global"), string("genTraverseProcForGlobal result"))

    # Test 19: genTraverseProcForGlobal with emulated thread vars
    conf.globalOptions = {optThreads, optTlsEmulation}
    globalSym.flags = {sfThread}
    globRes = genTraverseProcForGlobal(module, globalSym, 0)
    doAssert(globRes == string("tmp_global"), string("genTraverseProcForGlobal thread result"))

    # Test 20: skipModifier with tyDistinct and tySink
    with var:
        distinctType = PType()
    distinctType.kind = TTypeKind.tyDistinct
    distinctType.elementType = refType
    distinctType.sons = seq[PType]()
    lenBefore = procObj.s(cpsStmts).lines.len
    genTraverseProc(closure, string("dist"), distinctType)
    doAssert(procObj.s(cpsStmts).lines.len == lenBefore + 1, string("tyDistinct traversed"))
    doAssert(procObj.s(cpsStmts).lines[lenBefore] == string("nimGCvisit((void*)dist, op);"), string("distinct visit"))

    # Test 21: genTraverseProc(m, origTyp, sig) for tySequence
    with var:
        markerSeq = genTraverseProc(module, seqType, u64(999))
    doAssert(markerSeq == string("Marker_TypeName"), string("markerSeq name"))

    # Test 22: genTraverseProc(m, origTyp, sig) for tyArray element
    with var:
        arrContainerType = PType()
    arrContainerType.kind = TTypeKind.tyObject
    arrContainerType.elementType = arrType
    arrContainerType.sons = seq[PType]()
    with var:
        markerArr = genTraverseProc(module, arrContainerType, u64(888))
    doAssert(markerArr == string("Marker_TypeName"), string("markerArr name"))

    # Test 23: AST traversal with empty loc snippet triggering fillObjectFields
    with var:
        unfilledSym = makeSymNode(string("unfilled"), refType, string(""))
        unfilledRecList = PNode()
    unfilledRecList.kind = TNodeKind.nkRecList
    unfilledRecList.sons = seq[PNode]([unfilledSym])
    genTraverseProc(closure, string("o"), unfilledRecList, objType)

    echo(string("All ccgtrav tests passed successfully!"))

