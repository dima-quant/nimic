# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from .nodekinds import *
from .ropes import Rope, FormatStr, rope, prepend, addf
from nimic.std.intsets import IntSet, containsOrIncl

#
#
#           The Nim Compiler
#        (c) Copyright 2013 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# included from jsgen.nim

## Type info generation for the JS backend.

if comptime(__name__ == "__main__"):
    class TTypeKind(NIntEnum):
        tyNone = 0
        tyBool = auto()
        tyChar = auto()
        tyEmpty = auto()
        tyAlias = auto()
        tyNil = auto()
        tyUntyped = auto()
        tyTyped = auto()
        tyTypeDesc = auto()
        tyGenericInvocation = auto()
        tyGenericBody = auto()
        tyGenericInst = auto()
        tyGenericParam = auto()
        tyDistinct = auto()
        tyEnum = auto()
        tyOrdinal = auto()
        tyArray = auto()
        tyObject = auto()
        tyTuple = auto()
        tySet = auto()
        tyRange = auto()
        tyPtr = auto()
        tyRef = auto()
        tyVar = auto()
        tySequence = auto()
        tyProc = auto()
        tyPointer = auto()
        tyOpenArray = auto()
        tyString = auto()
        tyCstring = auto()
        tyForward = auto()
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
        tyOwned = auto()
        tySink = auto()
        tyLent = auto()
        tyVarargs = auto()
        tyUncheckedArray = auto()
        tyError = auto()
        tyBuiltInTypeClass = auto()
        tyUserTypeClass = auto()
        tyUserTypeClassInst = auto()
        tyCompositeTypeClass = auto()
        tyInferred = auto()
        tyAnd = auto()
        tyOr = auto()
        tyNot = auto()
        tyAnything = auto()
        tyStatic = auto()
        tyFromExpr = auto()
        tyConcept = auto()
        tyVoid = auto()
        tyIterable = auto()

    class TTypeFlag(NIntEnum):
        tfInheritable = 0

    class TSymKind(NIntEnum):
        skUnknown = 0
        skField = auto()
        skVar = auto()
        skProc = auto()

    with const:
        tyUserTypeClasses = Tset[TTypeKind]({
            TTypeKind.tyUserTypeClass,
            TTypeKind.tyUserTypeClassInst,
        })
        skipPtrs = Tset[TTypeKind]({
            TTypeKind.tyVar,
            TTypeKind.tyPtr,
            TTypeKind.tyRef,
            TTypeKind.tyGenericInst,
            TTypeKind.tyTypeDesc,
            TTypeKind.tyAlias,
            TTypeKind.tyInferred,
            TTypeKind.tySink,
            TTypeKind.tyLent,
            TTypeKind.tyOwned,
        })
    if not comptime(defined("c")):
        tyObject = TTypeKind.tyObject
        tyTuple = TTypeKind.tyTuple
        tfInheritable = TTypeFlag.tfInheritable

    class Int128(nint):
        pass

    @ref
    class TIdent(Object):
        s: string

    @ref
    class TLoc(Object):
        snippet: Rope

    @ref
    class PSym(Object):
        id: nint
        name: TIdent
        typ: PType
        position: nint
        ast: PNode
        loc: TLoc

    @ref
    class PNode(Object):
        kind: TNodeKind
        info: nint
        sym: PSym
        strVal: string
        intVal: nint
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
        id: nint
        kind: TTypeKind
        flags: Tset[TTypeFlag]
        sons: seq[PType]
        n: PNode
        baseClass: PType
        elementType: PType

        def __getitem__(self, i: nint) -> PType:
            return self.sons[i]

        def __setitem__(self, i: nint, v: PType):
            self.sons[i] = v

        @property
        def len(self) -> nint:
            return self.sons.len

        def skipModifier(self) -> PType:
            if self.elementType is not None:
                return self.elementType
            if self.sons.len > 0:
                return self.sons[self.sons.len - 1]
            return self

        def skipTypes(self, kinds: Tset[TTypeKind]) -> PType:
            with var:
                curr = self
            while curr is not None and curr.kind in kinds:
                if curr.elementType is not None:
                    curr = curr.elementType
                elif curr.sons.len > 0:
                    curr = curr.sons[curr.sons.len - 1]
                elif curr.baseClass is not None:
                    curr = curr.baseClass
                else:
                    break
            return curr

    @ref
    class PGlobals(Object):
        typeInfo: Rope
        constants: Rope
        code: Rope
        typeInfoGenerated: IntSet

    @ref
    class ConfigRef(Object):
        pass

    @ref
    class BModule(Object):
        module: PSym
        config: ConfigRef

    @ref
    class PProc(Object):
        module: BModule
        g: PGlobals

        @property
        def config(self) -> ConfigRef:
            return self.module.config

    def mangleName(m: BModule, s: PSym) -> Rope:
        if s.loc is not None and s.loc.snippet != string(""):
            return s.loc.snippet
        return rope(s.name.s)

    def makeJSString(s: string, escapeNonAscii: bool = True) -> Rope:
        with var:
            res = string("\"")
        for i in range(len(s)):
            with let:
                c = s[i]
            if c == ch("\\"):
                res.add(string("\\\\"))
            elif c == ch("\""):
                res.add(string("\\\""))
            elif c == ch("\n"):
                res.add(string("\\n"))
            elif c == ch("\r"):
                res.add(string("\\r"))
            elif c == ch("\t"):
                res.add(string("\\t"))
            else:
                res.add(c)
        res.add(string("\""))
        return rope(res)

    @dispatch
    def internalError(conf: ConfigRef, info: nint, msg: string) -> None:
        raiseAssert(msg)

    @dispatch
    def internalError(conf: ConfigRef, msg: string) -> None:
        raiseAssert(msg)

    def getOrdValue(n: PNode) -> Int128:
        return n.intVal

    def lengthOrd(conf: ConfigRef, t: PType) -> Int128:
        return t.len

    def lastSon(n: PNode) -> PNode:
        return n.sons[n.sons.len - 1]

@dispatch
def rope(arg: Int128) -> Rope:
    return rope(str(arg))

def genTypeInfo(p: PProc, typ: PType) -> Rope:
    pass

def genObjectFields(p: PProc, typ: PType, n: PNode) -> Rope:
    with var:
        s = Rope("")
        u = Rope("")
        field = default(PSym)
        b = default(PNode)
    result = Rope("")
    match n.kind:
        case TNodeKind.nkRecList:
            if n.len == 1:
                result = genObjectFields(p, typ, n[0])
            else:
                s = Rope("")
                for i in range(n.len):
                    if i > 0:
                        s.add(string(", \n"))
                    s.add(genObjectFields(p, typ, n[i]))
                result = FormatStr(
                    "{kind: 2, len: $1, offset: 0, typ: null, name: null, sons: [$2]}"
                ) % [rope(n.len), s]
        case TNodeKind.nkSym:
            field = n.sym
            s = genTypeInfo(p, field.typ)
            result = FormatStr(
                "{kind: 1, offset: \"$1\", len: 0, typ: $2, name: $3, sons: null}"
            ) % [mangleName(p.module, field), s, makeJSString(field.name.s)]
        case TNodeKind.nkRecCase:
            if n[0].kind != TNodeKind.nkSym:
                internalError(p.config, n.info, string("genObjectFields"))
            field = n[0].sym
            s = genTypeInfo(p, field.typ)
            for i in range(1, n.len):
                b = n[i]  # branch
                u = Rope("")
                match b.kind:
                    case TNodeKind.nkOfBranch:
                        if b.len < 2:
                            internalError(p.config, b.info, string("genObjectFields; nkOfBranch broken"))
                        for j in range(b.len - 1):
                            if u != string(""):
                                u.add(string(", "))
                            if b[j].kind == TNodeKind.nkRange:
                                u.addf(FormatStr("[$1, $2]"), [rope(getOrdValue(b[j][0])), rope(getOrdValue(b[j][1]))])
                            else:
                                u.add(rope(getOrdValue(b[j])))
                    case TNodeKind.nkElse:
                        u = rope(lengthOrd(p.config, field.typ))
                    case _:
                        internalError(p.config, n.info, string("genObjectFields(nkRecCase)"))
                if result != string(""):
                    result.add(string(", \n"))
                result.addf(FormatStr("[setConstr($1), $2]"), [u, genObjectFields(p, typ, lastSon(b))])
            result = FormatStr(
                "{kind: 3, offset: \"$1\", len: $3, typ: $2, name: $4, sons: [$5]}"
            ) % [
                mangleName(p.module, field),
                s,
                rope(lengthOrd(p.config, field.typ)),
                makeJSString(field.name.s),
                result,
            ]
        case _:
            internalError(p.config, n.info, string("genObjectFields"))
    return result

def objHasTypeField(t: PType) -> bool:
    """{.inline.}"""
    return tfInheritable in t.flags or t.baseClass is not None

def genObjectInfo(p: PProc, typ: PType, name: Rope) -> None:
    with let:
        kind = tyObject if objHasTypeField(typ) else tyTuple
    with var:
        s = FormatStr(
            "var $1 = {size: 0, kind: $2, base: null, node: null, finalizer: null};$n"
        ) % [name, rope(ord(kind))]
    prepend(p.g.typeInfo, s)
    p.g.typeInfo.addf(FormatStr("var NNI$1 = $2;$n"), [rope(typ.id), genObjectFields(p, typ, typ.n)])
    p.g.typeInfo.addf(FormatStr("$1.node = NNI$2;$n"), [name, rope(typ.id)])
    if (typ.kind == tyObject) and (typ.baseClass is not None):
        p.g.typeInfo.addf(
            FormatStr("$1.base = $2;$n"),
            [name, genTypeInfo(p, typ.baseClass.skipTypes(skipPtrs))],
        )

def genTupleFields(p: PProc, typ: PType) -> Rope:
    with var:
        s = Rope("")
    for i in range(typ.len):
        if i > 0:
            s.add(string(", \n"))
        s.addf(
            FormatStr(
                "{kind: 1, offset: \"Field$1\", len: 0, typ: $2, name: \"Field$1\", sons: null}"
            ),
            [rope(i), genTypeInfo(p, typ[i])],
        )
    result = FormatStr(
        "{kind: 2, len: $1, offset: 0, typ: null, name: null, sons: [$2]}"
    ) % [rope(typ.len), s]
    return result

def genTupleInfo(p: PProc, typ: PType, name: Rope) -> None:
    with var:
        s = FormatStr(
            "var $1 = {size: 0, kind: $2, base: null, node: null, finalizer: null};$n"
        ) % [name, rope(ord(typ.kind))]
    prepend(p.g.typeInfo, s)
    p.g.typeInfo.addf(FormatStr("var NNI$1 = $2;$n"), [rope(typ.id), genTupleFields(p, typ)])
    p.g.typeInfo.addf(FormatStr("$1.node = NNI$2;$n"), [name, rope(typ.id)])

def genEnumInfo(p: PProc, typ: PType, name: Rope) -> None:
    with var:
        s = Rope("")
    for i in range(typ.n.len):
        if typ.n[i].kind != TNodeKind.nkSym:
            internalError(p.config, typ.n.info, string("genEnumInfo"))
        with let:
            field = typ.n[i].sym
        if i > 0:
            s.add(string(", \n"))
        with let:
            extName = field.name.s if field.ast is None else field.ast.strVal
        s.addf(
            FormatStr("\"$1\": {kind: 1, offset: $1, typ: $2, name: $3, len: 0, sons: null}"),
            [rope(field.position), name, makeJSString(extName)],
        )
    with var:
        n = FormatStr(
            "var NNI$1 = {kind: 2, offset: 0, typ: null, name: null, len: $2, sons: {$3}};$n"
        ) % [rope(typ.id), rope(typ.n.len), s]
    s = FormatStr(
        "var $1 = {size: 0, kind: $2, base: null, node: null, finalizer: null};$n"
    ) % [name, rope(ord(typ.kind))]
    prepend(p.g.typeInfo, s)
    p.g.typeInfo.add(n)
    p.g.typeInfo.addf(FormatStr("$1.node = NNI$2;$n"), [name, rope(typ.id)])
    if typ.baseClass is not None:
        p.g.typeInfo.addf(FormatStr("$1.base = $2;$n"), [name, genTypeInfo(p, typ.baseClass)])

def genTypeInfo(p: PProc, typ: PType) -> Rope:
    with let:
        t = typ.skipTypes(
            Tset[TTypeKind]({
                TTypeKind.tyGenericInst,
                TTypeKind.tyDistinct,
                TTypeKind.tyAlias,
                TTypeKind.tySink,
                TTypeKind.tyOwned,
            })
            + tyUserTypeClasses
        )
    result = FormatStr("NTI$1") % [rope(t.id)]
    if containsOrIncl(p.g.typeInfoGenerated, t.id):
        return result
    match t.kind:
        case TTypeKind.tyDistinct:
            result = genTypeInfo(p, t.skipModifier())
        case (
            TTypeKind.tyPointer
            | TTypeKind.tyProc
            | TTypeKind.tyBool
            | TTypeKind.tyChar
            | TTypeKind.tyCstring
            | TTypeKind.tyString
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
            with var:
                s = FormatStr(
                    "var $1 = {size: 0,kind: $2,base: null,node: null,finalizer: null};$n"
                ) % [result, rope(ord(t.kind))]
            prepend(p.g.typeInfo, s)
        case (
            TTypeKind.tyVar
            | TTypeKind.tyLent
            | TTypeKind.tyRef
            | TTypeKind.tyPtr
            | TTypeKind.tySequence
            | TTypeKind.tyRange
            | TTypeKind.tySet
            | TTypeKind.tyOpenArray
        ):
            with var:
                s = FormatStr(
                    "var $1 = {size: 0, kind: $2, base: null, node: null, finalizer: null};$n"
                ) % [result, rope(ord(t.kind))]
            prepend(p.g.typeInfo, s)
            p.g.typeInfo.addf(FormatStr("$1.base = $2;$n"), [result, genTypeInfo(p, t.elementType)])
        case TTypeKind.tyArray:
            with var:
                s = FormatStr(
                    "var $1 = {size: 0, kind: $2, base: null, node: null, finalizer: null};$n"
                ) % [result, rope(ord(t.kind))]
            prepend(p.g.typeInfo, s)
            p.g.typeInfo.addf(FormatStr("$1.base = $2;$n"), [result, genTypeInfo(p, t.elementType)])
        case TTypeKind.tyEnum:
            genEnumInfo(p, t, result)
        case TTypeKind.tyObject:
            genObjectInfo(p, t, result)
        case TTypeKind.tyTuple:
            genTupleInfo(p, t, result)
        case TTypeKind.tyStatic:
            if t.n is not None:
                result = genTypeInfo(p, t.skipModifier())
            else:
                internalError(p.config, string("genTypeInfo(") + string(str(t.kind)) + string(")"))
        case _:
            internalError(p.config, string("genTypeInfo(") + string(str(t.kind)) + string(")"))
    return result

if comptime(__name__ == "__main__"):
    def makeProc() -> PProc:
        with var:
            p = PProc()
            m = BModule()
            g = PGlobals()
        m.config = ConfigRef()
        g.typeInfo = Rope("")
        g.constants = Rope("")
        g.code = Rope("")
        g.typeInfoGenerated = IntSet()
        p.module = m
        p.g = g
        return p

    def makeType(id: nint, kind: TTypeKind, elemType: PType = None) -> PType:
        with var:
            t = PType()
        t.id = id
        t.kind = kind
        t.flags = Tset[TTypeFlag]()
        t.sons = seq[PType]()
        t.elementType = elemType
        return t

    def makeIdent(s: string) -> TIdent:
        with var:
            id = TIdent()
        id.s = s
        return id

    def makeSym(id: nint, name: string, typ: PType, pos: nint = 0) -> PSym:
        with var:
            s = PSym()
            loc = TLoc()
        s.id = id
        s.name = makeIdent(name)
        s.typ = typ
        s.position = pos
        s.ast = None
        loc.snippet = rope(name)
        s.loc = loc
        return s

    def makeSymNode(sym: PSym) -> PNode:
        with var:
            n = PNode()
        n.kind = TNodeKind.nkSym
        n.sym = sym
        n.sons = seq[PNode]()
        return n

    def containsStr(s: string, sub: string) -> bool:
        if len(sub) == 0:
            return True
        if len(s) < len(sub):
            return False
        for i in range(len(s) - len(sub) + 1):
            with var:
                found = True
            for j in range(len(sub)):
                if s[i + j] != sub[j]:
                    found = False
                    break
            if found:
                return True
        return False

    # --- Test 1: rope(Int128) ---
    with let:
        r1 = rope(12345)
    doAssert(str(r1) == "12345")
    with let:
        r2 = rope(-99)
    doAssert(str(r2) == "-99")

    # --- Test 2: objHasTypeField ---
    with var:
        tInherit = makeType(1, TTypeKind.tyObject)
    tInherit.flags.incl(TTypeFlag.tfInheritable)
    doAssert(objHasTypeField(tInherit) == True)

    with var:
        tBase = makeType(2, TTypeKind.tyObject)
        tSub = makeType(3, TTypeKind.tyObject)
    tSub.baseClass = tBase
    doAssert(objHasTypeField(tSub) == True)

    with var:
        tPlain = makeType(4, TTypeKind.tyObject)
    doAssert(objHasTypeField(tPlain) == False)

    # --- Test 3: genTypeInfo primitive types ---
    with var:
        proc1 = makeProc()
        tInt = makeType(10, TTypeKind.tyInt)
    with let:
        ntiInt = genTypeInfo(proc1, tInt)
    doAssert(str(ntiInt) == "NTI10")
    doAssert(containsStr(proc1.g.typeInfo, string("var NTI10 = {size: 0,kind: 31,base: null,node: null,finalizer: null};\n")))

    # Deduplication test: calling again should not re-generate
    with let:
        lenBefore = len(str(proc1.g.typeInfo))
        ntiInt2 = genTypeInfo(proc1, tInt)
    doAssert(str(ntiInt2) == "NTI10")
    doAssert(len(str(proc1.g.typeInfo)) == lenBefore)

    # tyBool
    with var:
        proc2 = makeProc()
        tBool = makeType(11, TTypeKind.tyBool)
    with let:
        ntiBool = genTypeInfo(proc2, tBool)
    doAssert(str(ntiBool) == "NTI11")
    doAssert(containsStr(proc2.g.typeInfo, string("var NTI11 = {size: 0,kind: 1,base: null,node: null,finalizer: null};\n")))

    # tyString and tyCstring
    with var:
        tStr = makeType(12, TTypeKind.tyString)
        ntiStr = genTypeInfo(proc2, tStr)
    doAssert(str(ntiStr) == "NTI12")
    doAssert(containsStr(proc2.g.typeInfo, string("var NTI12 = {size: 0,kind: 28,base: null,node: null,finalizer: null};\n")))

    # --- Test 4: genTypeInfo compound types (ref, ptr, seq, array) ---
    with var:
        proc3 = makeProc()
        tRefInt = makeType(20, TTypeKind.tyRef, tInt)
    with let:
        ntiRef = genTypeInfo(proc3, tRefInt)
    doAssert(str(ntiRef) == "NTI20")
    # Base should point to NTI10
    doAssert(containsStr(proc3.g.typeInfo, string("NTI20.base = NTI10;\n")))

    # tyArray
    with var:
        procArray = makeProc()
        tArr = makeType(21, TTypeKind.tyArray, tInt)
    with let:
        ntiArr = genTypeInfo(procArray, tArr)
    doAssert(str(ntiArr) == "NTI21")
    doAssert(containsStr(procArray.g.typeInfo, string("NTI21.base = NTI10;\n")))

    # --- Test 5: genTypeInfo on tyDistinct ---
    with var:
        procDist = makeProc()
        tDistinct = makeType(25, TTypeKind.tyDistinct, tInt)
    with let:
        ntiDist = genTypeInfo(procDist, tDistinct)
    # Distinct gets unwrapped via skipModifier to tInt
    doAssert(str(ntiDist) == "NTI10")

    # --- Test 6: genEnumInfo ---
    with var:
        procEnum = makeProc()
        tEnum = makeType(30, TTypeKind.tyEnum)
        enumRec = PNode()
    enumRec.kind = TNodeKind.nkRecList
    enumRec.sons = seq[PNode]()

    with var:
        fieldA = makeSym(31, string("Alpha"), tInt, 0)
        fieldB = makeSym(32, string("Beta"), tInt, 1)
        nodeA = makeSymNode(fieldA)
        nodeB = makeSymNode(fieldB)
    enumRec.sons.add(nodeA)
    enumRec.sons.add(nodeB)
    tEnum.n = enumRec

    with let:
        ntiEnum = genTypeInfo(procEnum, tEnum)
    doAssert(str(ntiEnum) == "NTI30")
    doAssert(containsStr(procEnum.g.typeInfo, string("var NNI30 = {kind: 2, offset: 0, typ: null, name: null, len: 2, sons: {")))
    doAssert(containsStr(procEnum.g.typeInfo, string("\"0\": {kind: 1, offset: 0, typ: NTI30, name: \"Alpha\", len: 0, sons: null}")))
    doAssert(containsStr(procEnum.g.typeInfo, string("\"1\": {kind: 1, offset: 1, typ: NTI30, name: \"Beta\", len: 0, sons: null}")))
    doAssert(containsStr(procEnum.g.typeInfo, string("NTI30.node = NNI30;\n")))

    # Enum field with custom AST string value
    with var:
        procEnumAst = makeProc()
        tEnumAst = makeType(35, TTypeKind.tyEnum)
        enumRecAst = PNode()
        customStrNode = PNode()
    customStrNode.kind = TNodeKind.nkStrLit
    customStrNode.strVal = string("CustomBeta")
    fieldB.ast = customStrNode
    enumRecAst.kind = TNodeKind.nkRecList
    enumRecAst.sons = seq[PNode]([nodeA, nodeB])
    tEnumAst.n = enumRecAst
    with let:
        ntiEnumAst = genTypeInfo(procEnumAst, tEnumAst)
    doAssert(containsStr(procEnumAst.g.typeInfo, string("\"CustomBeta\"")))

    # --- Test 7: genTupleInfo ---
    with var:
        procTup = makeProc()
        tTuple = makeType(40, TTypeKind.tyTuple)
    tTuple.sons = seq[PType]([tInt, tBool])
    with let:
        ntiTup = genTypeInfo(procTup, tTuple)
    doAssert(str(ntiTup) == "NTI40")
    doAssert(containsStr(procTup.g.typeInfo, string("var NNI40 = {kind: 2, len: 2, offset: 0, typ: null, name: null, sons: [")))
    doAssert(containsStr(procTup.g.typeInfo, string("{kind: 1, offset: \"Field0\", len: 0, typ: NTI10, name: \"Field0\", sons: null}")))
    doAssert(containsStr(procTup.g.typeInfo, string("{kind: 1, offset: \"Field1\", len: 0, typ: NTI11, name: \"Field1\", sons: null}")))
    doAssert(containsStr(procTup.g.typeInfo, string("NTI40.node = NNI40;\n")))

    # --- Test 8: genObjectInfo (simple object fields) ---
    with var:
        procObj = makeProc()
        tObj = makeType(50, TTypeKind.tyObject)
        objRec = PNode()
    objRec.kind = TNodeKind.nkRecList
    objRec.sons = seq[PNode]()

    with var:
        objField1 = makeSym(51, string("x"), tInt, 0)
        objField2 = makeSym(52, string("y"), tBool, 1)
        nodeF1 = makeSymNode(objField1)
        nodeF2 = makeSymNode(objField2)
    objRec.sons.add(nodeF1)
    objRec.sons.add(nodeF2)
    tObj.n = objRec

    with let:
        ntiObj = genTypeInfo(procObj, tObj)
    doAssert(str(ntiObj) == "NTI50")
    doAssert(containsStr(procObj.g.typeInfo, string("var NNI50 = {kind: 2, len: 2, offset: 0, typ: null, name: null, sons: [")))
    doAssert(containsStr(procObj.g.typeInfo, string("{kind: 1, offset: \"x\", len: 0, typ: NTI10, name: \"x\", sons: null}")))
    doAssert(containsStr(procObj.g.typeInfo, string("{kind: 1, offset: \"y\", len: 0, typ: NTI11, name: \"y\", sons: null}")))
    doAssert(containsStr(procObj.g.typeInfo, string("NTI50.node = NNI50;\n")))

    # Object with single field nkRecList
    with var:
        procObjSingle = makeProc()
        tObjSingle = makeType(55, TTypeKind.tyObject)
        objRecSingle = PNode()
    objRecSingle.kind = TNodeKind.nkRecList
    objRecSingle.sons = seq[PNode]([nodeF1])
    tObjSingle.n = objRecSingle
    with let:
        ntiObjSingle = genTypeInfo(procObjSingle, tObjSingle)
    doAssert(containsStr(procObjSingle.g.typeInfo, string("var NNI55 = {kind: 1, offset: \"x\", len: 0, typ: NTI10, name: \"x\", sons: null};\n")))

    # Object with inheritance (baseClass)
    with var:
        procObjInh = makeProc()
        tBaseObj = makeType(60, TTypeKind.tyObject)
        tSubObj = makeType(61, TTypeKind.tyObject)
        baseRec = PNode()
    baseRec.kind = TNodeKind.nkRecList
    baseRec.sons = seq[PNode]([nodeF1])
    tBaseObj.n = baseRec
    tSubObj.n = objRecSingle
    tSubObj.baseClass = tBaseObj
    with let:
        ntiSubObj = genTypeInfo(procObjInh, tSubObj)
    doAssert(containsStr(procObjInh.g.typeInfo, string("NTI61.base = NTI60;\n")))

    # --- Test 9: genObjectFields with nkRecCase (variant objects) ---
    with var:
        procCase = makeProc()
        tCaseObj = makeType(70, TTypeKind.tyObject)
        caseRoot = PNode()
    caseRoot.kind = TNodeKind.nkRecCase
    caseRoot.sons = seq[PNode]()

    with var:
        discSym = makeSym(71, string("kind"), tInt, 0)
        discNode = makeSymNode(discSym)
    caseRoot.sons.add(discNode)

    # Branch 1: of 0 (single value)
    with var:
        val0Node = PNode()
        branch1 = PNode()
    val0Node.kind = TNodeKind.nkIntLit
    val0Node.intVal = 0
    branch1.kind = TNodeKind.nkOfBranch
    branch1.sons = seq[PNode]([val0Node, nodeF1])
    caseRoot.sons.add(branch1)

    # Branch 2: of 1..5 (range)
    with var:
        rangeStart = PNode()
        rangeEnd = PNode()
        rangeNode = PNode()
        branch2 = PNode()
    rangeStart.kind = TNodeKind.nkIntLit
    rangeStart.intVal = 1
    rangeEnd.kind = TNodeKind.nkIntLit
    rangeEnd.intVal = 5
    rangeNode.kind = TNodeKind.nkRange
    rangeNode.sons = seq[PNode]([rangeStart, rangeEnd])
    branch2.kind = TNodeKind.nkOfBranch
    branch2.sons = seq[PNode]([rangeNode, nodeF2])
    caseRoot.sons.add(branch2)

    # Branch 3: else
    with var:
        branchElse = PNode()
    branchElse.kind = TNodeKind.nkElse
    branchElse.sons = seq[PNode]([nodeF1])
    caseRoot.sons.add(branchElse)

    tCaseObj.n = caseRoot
    with let:
        ntiCase = genTypeInfo(procCase, tCaseObj)
    doAssert(str(ntiCase) == "NTI70")
    doAssert(containsStr(procCase.g.typeInfo, string("[setConstr(0), {kind: 1, offset: \"x\"")))
    doAssert(containsStr(procCase.g.typeInfo, string("[setConstr([1, 5]), {kind: 1, offset: \"y\"")))
    doAssert(containsStr(procCase.g.typeInfo, string("{kind: 3, offset: \"kind\", len: 0, typ: NTI10, name: \"kind\", sons: [")))

    # --- Test 10: genTypeInfo on tyStatic ---
    with var:
        procStatic = makeProc()
        tStatic = makeType(80, TTypeKind.tyStatic)
        staticSon = PNode()
    staticSon.kind = TNodeKind.nkIntLit
    staticSon.intVal = 42
    tStatic.n = staticSon
    tStatic.elementType = tInt
    with let:
        ntiStatic = genTypeInfo(procStatic, tStatic)
    doAssert(str(ntiStatic) == "NTI10")

    # --- Test 11: genTypeInfo compound types (tySequence and tySet) ---
    with var:
        procSeq = makeProc()
        tSeq = makeType(90, TTypeKind.tySequence, tInt)
    with let:
        ntiSeq = genTypeInfo(procSeq, tSeq)
    doAssert(str(ntiSeq) == "NTI90")
    doAssert(containsStr(procSeq.g.typeInfo, string("NTI90.base = NTI10;\n")))

    with var:
        procSet = makeProc()
        tSet = makeType(91, TTypeKind.tySet, tInt)
    with let:
        ntiSet = genTypeInfo(procSet, tSet)
    doAssert(str(ntiSet) == "NTI91")
    doAssert(containsStr(procSet.g.typeInfo, string("NTI91.base = NTI10;\n")))

    # --- Test 12: genTypeInfo skipping tyGenericInst and tyAlias ---
    with var:
        procSkip = makeProc()
        tAlias = makeType(100, TTypeKind.tyAlias, tInt)
        tGenericInst = makeType(101, TTypeKind.tyGenericInst, tAlias)
    with let:
        ntiSkip = genTypeInfo(procSkip, tGenericInst)
    doAssert(str(ntiSkip) == "NTI10")

    # --- Test 13: genEnumInfo with baseClass ---
    with var:
        procEnumBase = makeProc()
        tEnumBase = makeType(110, TTypeKind.tyEnum)
        tEnumChild = makeType(111, TTypeKind.tyEnum)
        enumRecBase = PNode()
    enumRecBase.kind = TNodeKind.nkRecList
    enumRecBase.sons = seq[PNode]([nodeA])
    tEnumBase.n = enumRecBase
    tEnumChild.n = enumRecBase
    tEnumChild.baseClass = tEnumBase

    with let:
        ntiEnumChild = genTypeInfo(procEnumBase, tEnumChild)
    doAssert(str(ntiEnumChild) == "NTI111")
    doAssert(containsStr(procEnumBase.g.typeInfo, string("NTI111.base = NTI110;\n")))

    # --- Test 14: genTypeInfo primitive types (tyFloat, tyPointer, tyProc) ---
    with var:
        procPrim = makeProc()
        tFloat = makeType(120, TTypeKind.tyFloat)
        tPtr = makeType(121, TTypeKind.tyPointer)
        tPrc = makeType(122, TTypeKind.tyProc)
    with let:
        ntiFloat = genTypeInfo(procPrim, tFloat)
        ntiPtr = genTypeInfo(procPrim, tPtr)
        ntiPrc = genTypeInfo(procPrim, tPrc)
    doAssert(str(ntiFloat) == "NTI120")
    doAssert(str(ntiPtr) == "NTI121")
    doAssert(str(ntiPrc) == "NTI122")
    doAssert(containsStr(procPrim.g.typeInfo, string("var NTI120 = {size: 0,kind: ")))
    doAssert(containsStr(procPrim.g.typeInfo, string("var NTI121 = {size: 0,kind: ")))
    doAssert(containsStr(procPrim.g.typeInfo, string("var NTI122 = {size: 0,kind: ")))

    echo(string("All jstypes tests passed successfully."))
