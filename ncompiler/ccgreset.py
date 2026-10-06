# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from .nodekinds import *

#
#
#           The Nim Compiler
#        (c) Copyright 2020 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# included from cgen.nim

## Code specialization instead of the old, incredibly slow 'genericReset'
## implementation.

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
        sfImportc = 0

    class TCProcSection(NIntEnum):
        cpsLocals = 0
        cpsInit = auto()
        cpsStmts = auto()

    class TSetType(NIntEnum):
        ctArray = 0
        ctInt8 = auto()
        ctInt16 = auto()
        ctInt32 = auto()
        ctInt64 = auto()

    class CallingConvention(NIntEnum):
        ccDefault = 0
        ccClosure = auto()

    if not comptime(defined("c")):
        cpsStmts = TCProcSection.cpsStmts
        ccClosure = CallingConvention.ccClosure
        ctArray = TSetType.ctArray
        ctInt8 = TSetType.ctInt8
        ctInt16 = TSetType.ctInt16
        ctInt32 = TSetType.ctInt32
        ctInt64 = TSetType.ctInt64

    with const:
        NimNil = string("NIM_NIL")
        CPointer = string("void*")
        unknownLineInfo = 0
        skipPtrs = {TTypeKind.tyPtr, TTypeKind.tyRef}

    @ref
    class SwitchCaseBuilder(Object):
        state: nint

    @ref
    class Builder(Object):
        lines: seq[string]

        def addCaseElse(self, info: SwitchCaseBuilder) -> None:
            self.lines.add(string("default:"))

        def addBreak(self) -> None:
            self.lines.add(string("break;"))

        def addCallStmt(self, fn: string, a1: string = string(""), a2: string = string("")) -> None:
            with var:
                s = fn + string("(") + a1
            if len(a2) > 0:
                s = s + string(", ") + a2
            s = s + string(");")
            self.lines.add(s)

        def addFieldAssignment(self, target: string, field: string, val: string) -> None:
            self.lines.add(target + string(".") + field + string(" = ") + val + string(";"))

        def addAssignment(self, target: string, val: string) -> None:
            self.lines.add(target + string(" = ") + val + string(";"))

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

        setattr(Builder, "__enter__", lambda self: self)
        setattr(Builder, "__exit__", lambda self, *args: False)

    @ref
    class ConfigRef(Object):
        pass

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
        elementType: PType
        indexType: PType
        baseClass: PType
        sons: seq[PType]
        n: PNode
        sym: PSym
        callConv: CallingConvention

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

    @ref
    class BProc(Object):
        module: BModule
        config: ConfigRef
        builder: Builder

        def s(self, sec: TCProcSection) -> Builder:
            return self.builder

    class Rope(string):
        pass

    def dotField(accessor: Rope, field: string) -> Rope:
        return accessor + string(".") + field

    def subscript(accessor: Rope, idx: string) -> Rope:
        return accessor + string("[") + idx + string("]")

    def parentObj(accessor: Rope, m: BModule) -> Rope:
        return accessor + string(".Sup")

    def cIntValue(val: nint) -> string:
        return string(str(val))

    def cgsymValue(m: BModule, name: string) -> string:
        return name

    def cCast(tp: string, expr: string) -> string:
        return string("(") + tp + string(")") + expr

    def ptrType(tp: string) -> string:
        return tp

    def cAddr(expr: string) -> string:
        return string("&") + expr

    def cSizeof(tp: string) -> string:
        return string("sizeof(") + tp + string(")")

    def getTypeDesc(m: BModule, t: PType) -> string:
        return string("TypeDesc")

    def getUniqueType(t: PType) -> PType:
        return t

    def lengthOrd(c: ConfigRef, t: PType) -> nint:
        return 10

    def getTemp(p: BProc, t: PType) -> TLoc:
        with var:
            loc = TLoc()
        loc.snippet = string("tmp_i")
        loc.t = t
        return loc

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
        discard

    def genCaseRange(p: BProc, branch: PNode, caseBuilder: SwitchCaseBuilder) -> None:
        p.s(cpsStmts).lines.add(string("genCaseRange"))

    def lastSon(n: PNode) -> PNode:
        return n.sons[n.sons.len - 1]

    def rdLoc(a: TLoc) -> Rope:
        return a.snippet

    def internalError(conf: ConfigRef, info: nint, msg: string) -> None:
        raiseAssert(msg)

    def mapSetType(conf: ConfigRef, t: PType) -> TSetType:
        return TSetType.ctArray if t.sons.len > 0 else TSetType.ctInt32

def specializeResetT(p: BProc, accessor: Rope, typ: PType) -> None:
    pass

def specializeResetN(p: BProc, accessor: Rope, n: PNode, typ: PType) -> None:
    if n is None:
        return
    match n.kind:
        case TNodeKind.nkRecList:
            for i in range(n.len):
                specializeResetN(p, accessor, n[i], typ)
        case TNodeKind.nkRecCase:
            if n[0].kind != TNodeKind.nkSym:
                internalError(p.config, n.info, string("specializeResetN"))
            with let:
                disc = n[0].sym
            if disc.loc.snippet == string(""):
                fillObjectFields(p.module, typ)
            if disc.loc.t is None:
                internalError(p.config, n.info, string("specializeResetN()"))
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
                            genCaseRange(p, branch, caseBuilder)
                        else:
                            p.s(cpsStmts).addCaseElse(caseBuilder)
                        with do:
                            specializeResetN(p, accessor, lastSon(branch), typ)
                            p.s(cpsStmts).addBreak()
            specializeResetT(p, discField, disc.loc.t)
        case TNodeKind.nkSym:
            with let:
                field = n.sym
            if field.typ.kind == TTypeKind.tyVoid:
                return
            if field.loc.snippet == string(""):
                fillObjectFields(p.module, typ)
            if field.loc.t is None:
                internalError(p.config, n.info, string("specializeResetN()"))
            specializeResetT(p, dotField(accessor, field.loc.snippet), field.loc.t)
        case _:
            internalError(p.config, n.info, string("specializeResetN()"))

def specializeResetT(p: BProc, accessor: Rope, typ: PType) -> None:
    if typ is None:
        return

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
            specializeResetT(p, accessor, skipModifier(typ))
        case TTypeKind.tyArray:
            with let:
                arraySize = lengthOrd(p.config, typ.indexType)
            with var:
                i: TLoc = getTemp(p, getSysType(p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
            with p.s(cpsStmts).addForRangeExclusive(i.snippet, cIntValue(0), cIntValue(arraySize)):
                specializeResetT(p, subscript(accessor, i.snippet), typ.elementType)
        case TTypeKind.tyObject:
            with var:
                x = typ.baseClass
            if x is not None:
                x = skipTypes(x, skipPtrs)
            specializeResetT(p, parentObj(accessor, p.module), x)
            if typ.n is not None:
                if typ.sym is not None and TSymFlag.sfImportc in typ.sym.flags:
                    # imported C struct, nimZeroMem
                    p.s(cpsStmts).addCallStmt(
                        cgsymValue(p.module, string("nimZeroMem")),
                        cCast(ptrType(CPointer), cAddr(accessor)),
                        cSizeof(getTypeDesc(p.module, typ)),
                    )
                else:
                    specializeResetN(p, accessor, typ.n, typ)
        case TTypeKind.tyTuple:
            with let:
                uTyp = getUniqueType(typ)
            for i, a in ikids(uTyp):
                specializeResetT(p, dotField(accessor, string("Field") + string(str(i))), a)
        case TTypeKind.tyString | TTypeKind.tyRef | TTypeKind.tySequence:
            p.s(cpsStmts).addCallStmt(
                cgsymValue(p.module, string("unsureAsgnRef")),
                cCast(ptrType(CPointer), cAddr(accessor)),
                NimNil,
            )
        case TTypeKind.tyProc:
            if typ.callConv == ccClosure:
                p.s(cpsStmts).addCallStmt(
                    cgsymValue(p.module, string("unsureAsgnRef")),
                    cCast(ptrType(CPointer), cAddr(dotField(accessor, string("ClE_0")))),
                    NimNil,
                )
                p.s(cpsStmts).addFieldAssignment(accessor, string("ClP_0"), NimNil)
            else:
                p.s(cpsStmts).addAssignment(accessor, NimNil)
        case (
            TTypeKind.tyChar
            | TTypeKind.tyBool
            | TTypeKind.tyEnum
            | TTypeKind.tyRange
            | TTypeKind.tyInt
            | TTypeKind.tyInt8
            | TTypeKind.tyInt16
            | TTypeKind.tyInt32
            | TTypeKind.tyInt64
            | TTypeKind.tyFloat
            | TTypeKind.tyFloat32
            | TTypeKind.tyFloat64
            | TTypeKind.tyFloat128
            | TTypeKind.tyUInt
            | TTypeKind.tyUInt8
            | TTypeKind.tyUInt16
            | TTypeKind.tyUInt32
            | TTypeKind.tyUInt64
        ):
            p.s(cpsStmts).addAssignment(accessor, cIntValue(0))
        case (
            TTypeKind.tyCstring
            | TTypeKind.tyPointer
            | TTypeKind.tyPtr
            | TTypeKind.tyVar
            | TTypeKind.tyLent
        ):
            p.s(cpsStmts).addAssignment(accessor, NimNil)
        case TTypeKind.tySet:
            match mapSetType(p.config, typ):
                case TSetType.ctArray:
                    with let:
                        t = getTypeDesc(p.module, typ)
                    p.s(cpsStmts).addCallStmt(
                        cgsymValue(p.module, string("nimZeroMem")),
                        accessor,
                        cSizeof(t),
                    )
                case (
                    TSetType.ctInt8
                    | TSetType.ctInt16
                    | TSetType.ctInt32
                    | TSetType.ctInt64
                ):
                    p.s(cpsStmts).addAssignment(accessor, cIntValue(0))
                case _:
                    raiseAssert(string("unexpected set type kind"))
        case _:
            discard

def specializeReset(p: BProc, a: TLoc) -> None:
    specializeResetT(p, rdLoc(a), a.t)

if comptime(__name__ == "__main__"):
    # Unit tests
    with var:
        b = Builder()
    b.lines = seq[string]()

    with var:
        graph = BGraph()
        mList = BModuleList()
    mList.graph = graph

    with var:
        module = BModule()
    module.g = mList

    with var:
        conf = ConfigRef()
        procObj = BProc()
    procObj.module = module
    procObj.config = conf
    procObj.builder = b

    # Helper factories
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

    # Test 1: specializeReset on primitive int
    with var:
        intType = PType()
    intType.kind = TTypeKind.tyInt
    intType.sons = seq[PType]()

    with var:
        locInt = TLoc()
    locInt.snippet = string("x")
    locInt.t = intType

    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 1)
    doAssert(b.lines[0] == string("x = 0;"))

    # Test 2: specializeReset on pointer/ref/string
    with var:
        strType = PType()
    strType.kind = TTypeKind.tyString
    strType.sons = seq[PType]()
    locInt.t = strType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 2)
    doAssert(b.lines[1] == string("unsureAsgnRef((void*)&x, NIM_NIL);"))

    # Test 3: specializeReset on closure proc
    with var:
        procType = PType()
    procType.kind = TTypeKind.tyProc
    procType.callConv = ccClosure
    procType.sons = seq[PType]()
    locInt.t = procType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 4)
    doAssert(b.lines[2] == string("unsureAsgnRef((void*)&x.ClE_0, NIM_NIL);"))
    doAssert(b.lines[3] == string("x.ClP_0 = NIM_NIL;"))

    # Test 4: specializeReset on non-closure proc
    procType.callConv = CallingConvention.ccDefault
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 5)
    doAssert(b.lines[4] == string("x = NIM_NIL;"))

    # Test 5: specializeReset on tuple
    with var:
        tupleType = PType()
    tupleType.kind = TTypeKind.tyTuple
    tupleType.sons = seq[PType]([intType, strType])
    locInt.t = tupleType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 7)
    doAssert(b.lines[5] == string("x.Field0 = 0;"))
    doAssert(b.lines[6] == string("unsureAsgnRef((void*)&x.Field1, NIM_NIL);"))

    # Test 6: specializeReset on array
    with var:
        arrType = PType()
    arrType.kind = TTypeKind.tyArray
    arrType.elementType = intType
    arrType.indexType = intType
    arrType.sons = seq[PType]()
    locInt.t = arrType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 9)
    doAssert(b.lines[7] == string("for (tmp_i; 0; 10)"))
    doAssert(b.lines[8] == string("x[tmp_i] = 0;"))

    # Test 7: specializeReset on record list & case
    with var:
        field1 = makeSymNode(string("a"), intType, string("a"))
        recList = PNode()
    recList.kind = TNodeKind.nkRecList
    recList.sons = seq[PNode]([field1])

    with var:
        objType = PType()
    objType.kind = TTypeKind.tyObject
    objType.n = recList
    objType.sons = seq[PType]()
    locInt.t = objType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 10)
    doAssert(b.lines[9] == string("x.a = 0;"))

    # Test 8: specializeReset on record case with ofBranch and elseBranch
    with var:
        discSymNode = makeSymNode(string("kind"), intType, string("kind"))
        ofBranch = PNode()
    ofBranch.kind = TNodeKind.nkOfBranch
    ofBranch.sons = seq[PNode]([makeSymNode(string("ofF"), strType, string("ofF"))])

    with var:
        elseBranch = PNode()
    elseBranch.kind = TNodeKind.nkElse
    elseBranch.sons = seq[PNode]([makeSymNode(string("elseF"), intType, string("elseF"))])

    with var:
        recCase = PNode()
    recCase.kind = TNodeKind.nkRecCase
    recCase.sons = seq[PNode]([discSymNode, ofBranch, elseBranch])

    objType.n = recCase
    specializeReset(procObj, locInt)
    # Checks that switch was emitted, case, default, break, and discField reset
    doAssert(b.lines[10] == string("switch (x.kind)"))
    doAssert(b.lines[11] == string("case"))
    doAssert(b.lines[12] == string("genCaseRange"))
    doAssert(b.lines[13] == string("unsureAsgnRef((void*)&x.ofF, NIM_NIL);"))
    doAssert(b.lines[14] == string("break;"))
    doAssert(b.lines[15] == string("case"))
    doAssert(b.lines[16] == string("default:"))
    doAssert(b.lines[17] == string("x.elseF = 0;"))
    doAssert(b.lines[18] == string("break;"))
    doAssert(b.lines[19] == string("x.kind = 0;"))

    # Test 9: specializeReset on float types
    with var:
        floatType = PType()
    floatType.kind = TTypeKind.tyFloat
    floatType.sons = seq[PType]()
    locInt.t = floatType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 21)
    doAssert(b.lines[20] == string("x = 0;"))

    floatType.kind = TTypeKind.tyFloat64
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 22)
    doAssert(b.lines[21] == string("x = 0;"))

    # Test 10: specializeReset with skipModifier
    with var:
        distinctType = PType()
    distinctType.kind = TTypeKind.tyDistinct
    distinctType.elementType = intType
    distinctType.sons = seq[PType]()
    locInt.t = distinctType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 23)
    doAssert(b.lines[22] == string("x = 0;"))

    with var:
        sinkType = PType()
    sinkType.kind = TTypeKind.tySink
    sinkType.elementType = strType
    sinkType.sons = seq[PType]()
    locInt.t = sinkType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 24)
    doAssert(b.lines[23] == string("unsureAsgnRef((void*)&x, NIM_NIL);"))

    # Test 11: specializeReset on object with baseClass inheritance
    with var:
        baseObjType = PType()
        baseField = makeSymNode(string("baseF"), intType, string("baseF"))
        baseRecList = PNode()
    baseRecList.kind = TNodeKind.nkRecList
    baseRecList.sons = seq[PNode]([baseField])
    baseObjType.kind = TTypeKind.tyObject
    baseObjType.n = baseRecList
    baseObjType.sons = seq[PType]()

    with var:
        derivedObjType = PType()
    derivedObjType.kind = TTypeKind.tyObject
    derivedObjType.baseClass = baseObjType
    derivedObjType.sons = seq[PType]()
    locInt.t = derivedObjType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 25)
    doAssert(b.lines[24] == string("x.Sup.baseF = 0;"))

    # Test 12: specializeReset on object with sfImportc
    with var:
        importcSym = PSym()
    importcSym.flags = {TSymFlag.sfImportc}
    with var:
        importcObjType = PType()
    importcObjType.kind = TTypeKind.tyObject
    importcObjType.sym = importcSym
    importcObjType.n = recList
    importcObjType.sons = seq[PType]()
    locInt.t = importcObjType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 26)
    doAssert(b.lines[25] == string("nimZeroMem((void*)&x, sizeof(TypeDesc));"))

    # Test 13: specializeReset on tySet
    with var:
        setArrayType = PType()
    setArrayType.kind = TTypeKind.tySet
    setArrayType.sons = seq[PType]([intType])
    locInt.t = setArrayType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 27)
    doAssert(b.lines[26] == string("nimZeroMem(x, sizeof(TypeDesc));"))

    with var:
        setIntType = PType()
    setIntType.kind = TTypeKind.tySet
    setIntType.sons = seq[PType]()
    locInt.t = setIntType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 28)
    doAssert(b.lines[27] == string("x = 0;"))

    # Test 14: specializeReset on pointer, ptr, cstring, var, lent
    with var:
        ptrTypeObj = PType()
    ptrTypeObj.kind = TTypeKind.tyPtr
    ptrTypeObj.sons = seq[PType]()
    locInt.t = ptrTypeObj
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 29)
    doAssert(b.lines[28] == string("x = NIM_NIL;"))

    ptrTypeObj.kind = TTypeKind.tyCstring
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 30)
    doAssert(b.lines[29] == string("x = NIM_NIL;"))

    # Test 15: specializeReset on bool, char, enum, range, uint
    with var:
        primType = PType()
    primType.kind = TTypeKind.tyBool
    primType.sons = seq[PType]()
    locInt.t = primType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 31)
    doAssert(b.lines[30] == string("x = 0;"))

    primType.kind = TTypeKind.tyUInt32
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 32)
    doAssert(b.lines[31] == string("x = 0;"))

    # Test 16: tyVoid field in object is skipped
    with var:
        voidType = PType()
    voidType.kind = TTypeKind.tyVoid
    voidType.sons = seq[PType]()
    with var:
        voidField = makeSymNode(string("v"), voidType, string("v"))
        recListVoid = PNode()
    recListVoid.kind = TNodeKind.nkRecList
    recListVoid.sons = seq[PNode]([voidField])
    with var:
        objVoidType = PType()
    objVoidType.kind = TTypeKind.tyObject
    objVoidType.n = recListVoid
    objVoidType.sons = seq[PType]()
    locInt.t = objVoidType
    specializeReset(procObj, locInt)
    doAssert(b.lines.len == 32)  # No new line emitted because void field is skipped

    echo(string("All ccgreset tests passed successfully."))
