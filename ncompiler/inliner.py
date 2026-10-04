# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.tables import initTable, Table
from .nodekinds import *

#
#
#           The Nim Compiler
#        (c) Copyright 2015 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# included from cgen.nim

if comptime(__name__ == "__main__"):
    class TSymKind(NIntEnum):
        skUnknown = 0
        skParam = auto()
        skVar = auto()
        skProc = auto()
        skResult = auto()

    class TSymFlag(NIntEnum):
        sfGlobal = 0

    with const:
        paramsPos = 3
        resultPos = 7

    @ref
    class IdGenerator(Object):
        lastId: nint

        def nextId(self) -> nint:
            self.lastId += 1
            return self.lastId

    @ref
    class PType(Object):
        kind: nint
        owner: PSym
        n: PNode
        sons: seq[PType]

    @ref
    class PSym(Object):
        id: nint
        kind: TSymKind
        name: string
        typ: PType
        info: nint
        owner: PSym
        flags: Tset[TSymFlag]
        ast: PNode
        position: nint

    @ref
    class PNode(Object):
        kind: TNodeKind
        sym: PSym
        typ: PType
        info: nint
        sons: seq[PNode]

        @property
        def len(self) -> nint:
            return len(self.sons)

        def __getitem__(self, index: nint) -> PNode:
            return self.sons[index]

        def __setitem__(self, index: nint, value: PNode) -> None:
            self.sons[index] = value

        def add(self, son: PNode) -> None:
            self.sons.add(son)

    def setOwner(s: PSym, owner: PSym) -> None:
        s.owner = owner

    def copySym(s: PSym, idgen: IdGenerator) -> PSym:
        with var:
            res = PSym()
        res.id = idgen.nextId()
        res.kind = s.kind
        res.name = s.name
        res.typ = s.typ
        res.info = s.info
        res.owner = s.owner
        res.flags = s.flags.copy()
        res.ast = s.ast
        res.position = s.position
        return res

    def newSymNode(s: PSym, info: nint) -> PNode:
        with var:
            res = PNode()
        res.kind = TNodeKind.nkSym
        res.sym = s
        res.info = info
        res.sons = seq[PNode]([])
        return res

    def shallowCopy(n: PNode) -> PNode:
        if n is None:
            return None
        with var:
            res = PNode()
        res.kind = n.kind
        res.sym = n.sym
        res.typ = n.typ
        res.info = n.info
        res.sons = seq[PNode]([])
        for s in n.sons:
            res.sons.add(s)
        return res

    def copyNode(n: PNode) -> PNode:
        if n is None:
            return None
        with var:
            res = PNode()
        res.kind = n.kind
        res.sym = n.sym
        res.typ = n.typ
        res.info = n.info
        res.sons = seq[PNode]([])
        return res

    def copyTree(n: PNode) -> PNode:
        if n is None:
            return None
        with var:
            res = PNode()
        res.kind = n.kind
        res.sym = n.sym
        res.typ = n.typ
        res.info = n.info
        res.sons = seq[PNode]([])
        for s in n.sons:
            res.sons.add(copyTree(s))
        return res

    def newNodeI(kind: TNodeKind, info: nint) -> PNode:
        with var:
            res = PNode()
        res.kind = kind
        res.info = info
        res.sons = seq[PNode]([])
        return res

    def copyType(t: PType, idgen: IdGenerator, owner: PSym) -> PType:
        if t is None:
            return None
        with var:
            res = PType()
        res.kind = t.kind
        res.owner = owner
        res.sons = seq[PType]([])
        for s in t.sons:
            res.sons.add(s)
        if t.n is not None:
            res.n = copyTree(t.n)
        else:
            res.n = None
        return res

    def makeType(kind: nint = 1) -> PType:
        with var:
            res = PType()
            pn = PNode()
        res.kind = kind
        res.sons = seq[PType]([])
        pn.kind = TNodeKind.nkFormalParams
        pn.info = 0
        pn.sons = seq[PNode]([])
        res.n = pn
        return res

    def addParam(procType: PType, param: PSym) -> None:
        param.position = procType.n.len - 1
        procType.n.add(newSymNode(param, 0))
        procType.sons.add(param.typ)

def copySymdef(n: PNode, locals: mut @ Table[nint, PSym], idgen: IdGenerator, owner: PSym) -> PNode:
    if n.kind >= TNodeKind.nkEmpty and n.kind <= TNodeKind.nkNilLit and n.kind != TNodeKind.nkSym:
        result = n
    elif n.kind == TNodeKind.nkSym:
        with let:
            oldSym = n.sym
            newSym = copySym(oldSym, idgen)
        setOwner(newSym, owner)
        locals[oldSym.id] = newSym
        result = newSymNode(newSym, oldSym.info)
    else:
        result = shallowCopy(n)
        for i in range(n.len):
            result[i] = copySymdef(n[i], locals, idgen, owner)
    return result

def copyInlineProcBody(n: PNode, locals: mut @ Table[nint, PSym], idgen: IdGenerator, owner: PSym) -> PNode:
    if n.kind >= TNodeKind.nkEmpty and n.kind <= TNodeKind.nkNilLit and n.kind != TNodeKind.nkSym:
        result = n
    elif n.kind == TNodeKind.nkSym:
        with let:
            sym = locals.getOrDefault(n.sym.id)
        if sym is not None:
            result = newSymNode(sym, n.info)
        else:
            result = n
    elif n.kind in {TNodeKind.nkLetSection, TNodeKind.nkVarSection}:
        result = shallowCopy(n)
        for i in range(n.len):
            with let:
                it = n[i]
            if it.kind == TNodeKind.nkCommentStmt:
                result[i] = it
            elif it.kind in {TNodeKind.nkIdentDefs, TNodeKind.nkConstDef}:
                result[i] = shallowCopy(it)
                for j in range(0, it.len - 2):
                    result[i][j] = copySymdef(it[j], locals, idgen, owner)
                for j in range(it.len - 2, it.len):
                    result[i][j] = copyInlineProcBody(it[j], locals, idgen, owner)
            else:
                assert it.kind == TNodeKind.nkVarTuple
                result[i] = shallowCopy(it)
                for j in range(0, it.len - 2):
                    assert it[j].kind == TNodeKind.nkSym
                    with let:
                        oldSym = it[j].sym
                        newSym = copySym(oldSym, idgen)
                    setOwner(newSym, owner)
                    locals[oldSym.id] = newSym
                    result[i][j] = newSymNode(newSym, oldSym.info)
                for j in range(it.len - 2, it.len):
                    result[i][j] = copyInlineProcBody(it[j], locals, idgen, owner)
    elif n.kind in {TNodeKind.nkForStmt, TNodeKind.nkParForStmt}:
        result = shallowCopy(n)
        for i in range(0, n.len - 2):
            assert n[i].kind == TNodeKind.nkSym
            with let:
                oldSym = n[i].sym
                newSym = copySym(oldSym, idgen)
            setOwner(newSym, owner)
            locals[oldSym.id] = newSym
            result[i] = newSymNode(newSym, oldSym.info)
        result[n.len - 2] = copyInlineProcBody(n[n.len - 2], locals, idgen, owner)
        result[n.len - 1] = copyInlineProcBody(n[n.len - 1], locals, idgen, owner)
    elif n.kind in {
        TNodeKind.nkProcDef,
        TNodeKind.nkFuncDef,
        TNodeKind.nkMethodDef,
        TNodeKind.nkIteratorDef,
        TNodeKind.nkConverterDef,
        TNodeKind.nkMacroDef,
        TNodeKind.nkTemplateDef,
        TNodeKind.nkTypeSection,
        TNodeKind.nkTypeOfExpr,
        TNodeKind.nkMixinStmt,
        TNodeKind.nkBindStmt,
        TNodeKind.nkConstSection,
    }:
        result = n
    else:
        result = shallowCopy(n)
        for i in range(n.len):
            result[i] = copyInlineProcBody(n[i], locals, idgen, owner)
    return result

def copyParams(n: PNode, locals: mut @ Table[nint, PSym], idgen: IdGenerator, owner: PSym) -> PNode:
    result = shallowCopy(n)
    result[0] = n[0]  # return type
    for i in range(1, n.len):
        with let:
            it = n[i]
        assert it.kind == TNodeKind.nkIdentDefs
        result[i] = shallowCopy(it)
        for j in range(0, it.len - 2):
            assert it[j].kind == TNodeKind.nkSym
            with let:
                oldSym = it[j].sym
                newSym = copySym(oldSym, idgen)
            setOwner(newSym, owner)
            locals[oldSym.id] = newSym
            result[i][j] = newSymNode(newSym, oldSym.info)
            addParam(owner.typ, newSym)
        for j in range(it.len - 2, it.len):
            result[i][j] = copyInlineProcBody(it[j], locals, idgen, owner)
    return result

def copyInlineProc(prc: PSym, idgen: IdGenerator) -> PSym:
    result = copySym(prc, idgen)
    with var:
        locals = initTable[nint, PSym]()
        a = shallowCopy(prc.ast)
    if resultPos < prc.ast.len and prc.ast[resultPos].kind == TNodeKind.nkSym:
        with let:
            oldRes = prc.ast[resultPos].sym
            newRes = copySym(oldRes, idgen)
        setOwner(newRes, result)
        locals[oldRes.id] = newRes
        a[resultPos] = newSymNode(newRes, oldRes.info)

    result.typ = copyType(prc.typ, idgen, result)
    result.typ.n = newNodeI(prc.typ.n.kind, prc.typ.n.info)
    if prc.typ.n.len > 0:
        result.typ.n.add(copyNode(prc.typ.n[0]))
        for i in range(1, prc.typ.n.len):
            with let:
                it = prc.typ.n[i]
            assert it.kind == TNodeKind.nkSym
            with let:
                oldSym = it.sym
                newSym = copySym(oldSym, idgen)
            setOwner(newSym, result)
            locals[oldSym.id] = newSym
            addParam(result.typ, newSym)

    for i in range(prc.ast.len):
        if i == paramsPos:
            a[i] = copyTree(prc.ast[i])
        elif i == resultPos and prc.ast[i].kind == TNodeKind.nkSym:
            _ = "handled above"
        else:
            a[i] = copyInlineProcBody(prc.ast[i], locals, idgen, result)
    result.ast = a
    return result

if comptime(__name__ == "__main__"):
    def makeNode(kind: TNodeKind) -> PNode:
        with var:
            res = PNode()
        res.kind = kind
        res.info = 0
        res.sons = seq[PNode]([])
        return res

    def makeNodeWithSons(kind: TNodeKind, sons: seq[PNode]) -> PNode:
        with var:
            res = PNode()
        res.kind = kind
        res.info = 0
        res.sons = sons
        return res

    def makeSym(id: nint, kind: TSymKind, name: string) -> PSym:
        with var:
            res = PSym()
        res.id = id
        res.kind = kind
        res.name = name
        res.flags = Tset[TSymFlag]()
        return res

    # --- Test 1: copySymdef ---
    with var:
        idgen = IdGenerator()
    idgen.lastId = 100
    with var:
        callerProc = makeSym(1, TSymKind.skProc, string("caller"))
        locals1 = initTable[nint, PSym]()

    # Atom leaves return n unchanged
    with var:
        identNode = makeNode(TNodeKind.nkIdent)
        intLitNode = makeNode(TNodeKind.nkIntLit)
        nilNode = makeNode(TNodeKind.nkNilLit)
    assert copySymdef(identNode, locals1, idgen, callerProc) == identNode
    assert copySymdef(intLitNode, locals1, idgen, callerProc) == intLitNode
    assert copySymdef(nilNode, locals1, idgen, callerProc) == nilNode

    # nkSym clones symbol, sets owner, and records in locals
    with var:
        varSym = makeSym(10, TSymKind.skVar, string("myLocal"))
        symNode = newSymNode(varSym, 42)
    with let:
        newSymNodeRes = copySymdef(symNode, locals1, idgen, callerProc)
    assert newSymNodeRes.kind == TNodeKind.nkSym
    assert newSymNodeRes.sym.id == 101
    assert newSymNodeRes.sym.name == string("myLocal")
    assert newSymNodeRes.sym.owner == callerProc
    assert locals1.hasKey(10)
    assert locals1[10] == newSymNodeRes.sym

    # --- Test 2: copyInlineProcBody on nkSym ---
    with var:
        locals2 = initTable[nint, PSym]()
        clonedVar = makeSym(201, TSymKind.skVar, string("clonedVar"))
    locals2[10] = clonedVar
    # Found in locals
    with let:
        bodySymFound = copyInlineProcBody(symNode, locals2, idgen, callerProc)
    assert bodySymFound.kind == TNodeKind.nkSym
    assert bodySymFound.sym == clonedVar

    # Not found in locals
    with var:
        otherSym = makeSym(99, TSymKind.skVar, string("globalVar"))
        otherSymNode = newSymNode(otherSym, 0)
    with let:
        bodySymNotFound = copyInlineProcBody(otherSymNode, locals2, idgen, callerProc)
    assert bodySymNotFound == otherSymNode

    # --- Test 3: copyInlineProcBody on nkVarSection (identDefs) ---
    with var:
        locals3 = initTable[nint, PSym]()
        vSym = makeSym(20, TSymKind.skVar, string("x"))
        vSymNode = newSymNode(vSym, 0)
        vTypeNode = makeNode(TNodeKind.nkEmpty)
        vValNode = makeNode(TNodeKind.nkIntLit)
        identDefs = makeNodeWithSons(TNodeKind.nkIdentDefs, seq[PNode]([vSymNode, vTypeNode, vValNode]))
        varSection = makeNodeWithSons(TNodeKind.nkVarSection, seq[PNode]([identDefs]))

    with let:
        copiedVarSection = copyInlineProcBody(varSection, locals3, idgen, callerProc)
    assert copiedVarSection.kind == TNodeKind.nkVarSection
    assert copiedVarSection.len == 1
    assert copiedVarSection[0].kind == TNodeKind.nkIdentDefs
    assert copiedVarSection[0][0].sym.id != 20
    assert locals3.hasKey(20)
    assert locals3[20] == copiedVarSection[0][0].sym

    # --- Test 4: copyInlineProcBody on nkForStmt ---
    with var:
        locals4 = initTable[nint, PSym]()
        forVarSym = makeSym(30, TSymKind.skVar, string("i"))
        forVarNode = newSymNode(forVarSym, 0)
        iterCall = makeNode(TNodeKind.nkCall)
        loopBody = makeNode(TNodeKind.nkStmtList)
        forStmt = makeNodeWithSons(TNodeKind.nkForStmt, seq[PNode]([forVarNode, iterCall, loopBody]))

    with let:
        copiedForStmt = copyInlineProcBody(forStmt, locals4, idgen, callerProc)
    assert copiedForStmt.kind == TNodeKind.nkForStmt
    assert copiedForStmt[0].sym.id != 30
    assert locals4.hasKey(30)
    assert locals4[30] == copiedForStmt[0].sym

    # --- Test 5: copyInlineProcBody skips routineDefs & type sections ---
    with var:
        innerProc = makeNode(TNodeKind.nkProcDef)
        innerType = makeNode(TNodeKind.nkTypeSection)
    assert copyInlineProcBody(innerProc, locals4, idgen, callerProc) == innerProc
    assert copyInlineProcBody(innerType, locals4, idgen, callerProc) == innerType

    # --- Test 6: copyParams ---
    with var:
        locals6 = initTable[nint, PSym]()
        owner6 = makeSym(50, TSymKind.skProc, string("targetProc"))
        ownerTyp6 = makeType(1)
    owner6.typ = ownerTyp6

    with var:
        paramSym = makeSym(60, TSymKind.skParam, string("a"))
        paramSymNode = newSymNode(paramSym, 0)
        retTypeNode = makeNode(TNodeKind.nkIdent)
        paramDefs = makeNodeWithSons(TNodeKind.nkIdentDefs, seq[PNode]([paramSymNode, makeNode(TNodeKind.nkEmpty), makeNode(TNodeKind.nkEmpty)]))
        paramsNode = makeNodeWithSons(TNodeKind.nkFormalParams, seq[PNode]([retTypeNode, paramDefs]))

    with let:
        copiedParams = copyParams(paramsNode, locals6, idgen, owner6)
    assert copiedParams[0] == retTypeNode
    assert copiedParams[1][0].sym.id != 60
    assert locals6.hasKey(60)
    assert locals6[60].owner == owner6

    # --- Test 7: copyInlineProc (full integration) ---
    with var:
        idgen7 = IdGenerator()
    idgen7.lastId = 500

    with var:
        origProc = makeSym(70, TSymKind.skProc, string("inlineCandidate"))
        origTyp = makeType(1)
        origParamSym = makeSym(71, TSymKind.skParam, string("x"))
    origParamSym.typ = makeType(1)
    origTyp.n.sons = seq[PNode]([makeNode(TNodeKind.nkEmpty), newSymNode(origParamSym, 0)])
    origProc.typ = origTyp

    # Build proc AST: 8 children [name, pattern, genericParams, params, pragmas, misc, body, result]
    with var:
        astSons: seq[PNode] = seq[PNode]()
    for k in range(8):
        astSons.add(makeNode(TNodeKind.nkEmpty))

    # params at paramsPos (3)
    astSons[paramsPos] = makeNode(TNodeKind.nkFormalParams)

    # body at bodyPos (6) with a reference to paramSym 71 and resultSym 72
    with var:
        resultSym = makeSym(72, TSymKind.skResult, string("result"))
    astSons[resultPos] = newSymNode(resultSym, 0)

    with var:
        bodyRefParam = newSymNode(origParamSym, 0)
        bodyRefResult = newSymNode(resultSym, 0)
        asgnStmt = makeNodeWithSons(TNodeKind.nkAsgn, seq[PNode]([bodyRefResult, bodyRefParam]))
        bodyList = makeNodeWithSons(TNodeKind.nkStmtList, seq[PNode]([asgnStmt]))
    astSons[6] = bodyList

    origProc.ast = makeNodeWithSons(TNodeKind.nkProcDef, astSons)

    with let:
        clonedProc = copyInlineProc(origProc, idgen7)
    assert clonedProc.id != origProc.id
    assert clonedProc.ast.len == 8
    # result symbol cloned
    assert clonedProc.ast[resultPos].sym.id != 72
    assert clonedProc.ast[resultPos].sym.owner == clonedProc
    # body rewritten
    with let:
        clonedBody = clonedProc.ast[6]
        clonedAsgn = clonedBody[0]
    assert clonedAsgn[0].sym == clonedProc.ast[resultPos].sym
    # parameter rewritten in body
    assert clonedAsgn[1].sym.id != 71
    assert clonedAsgn[1].sym.owner == clonedProc

    # --- Test 8: copyInlineProcBody on nkLetSection with comment, constDef, and varTuple ---
    with var:
        locals8 = initTable[nint, PSym]()
        owner8 = makeSym(80, TSymKind.skProc, string("owner8"))
        commentNode = makeNode(TNodeKind.nkCommentStmt)
        # constDef
        cSym = makeSym(81, TSymKind.skVar, string("MY_CONST"))
        cSymNode = newSymNode(cSym, 0)
        cTypeNode = makeNode(TNodeKind.nkEmpty)
        cValNode = makeNode(TNodeKind.nkIntLit)
        constDef = makeNodeWithSons(TNodeKind.nkConstDef, seq[PNode]([cSymNode, cTypeNode, cValNode]))
        # varTuple: let (t1, t2) = tupleExpr
        t1Sym = makeSym(82, TSymKind.skVar, string("t1"))
        t2Sym = makeSym(83, TSymKind.skVar, string("t2"))
        t1Node = newSymNode(t1Sym, 0)
        t2Node = newSymNode(t2Sym, 0)
        tTypeNode = makeNode(TNodeKind.nkEmpty)
        tValNode = makeNode(TNodeKind.nkCall)
        varTuple = makeNodeWithSons(TNodeKind.nkVarTuple, seq[PNode]([t1Node, t2Node, tTypeNode, tValNode]))
        letSection = makeNodeWithSons(TNodeKind.nkLetSection, seq[PNode]([commentNode, constDef, varTuple]))

    with let:
        copiedLetSection = copyInlineProcBody(letSection, locals8, idgen, owner8)
    assert copiedLetSection.kind == TNodeKind.nkLetSection
    assert copiedLetSection.len == 3
    # Comment preserved directly
    assert copiedLetSection[0] == commentNode
    # constDef symbol cloned
    assert copiedLetSection[1].kind == TNodeKind.nkConstDef
    assert copiedLetSection[1][0].sym.id != 81
    assert locals8.hasKey(81)
    assert locals8[81].owner == owner8
    # varTuple symbols cloned
    assert copiedLetSection[2].kind == TNodeKind.nkVarTuple
    assert copiedLetSection[2][0].sym.id != 82
    assert copiedLetSection[2][1].sym.id != 83
    assert locals8.hasKey(82)
    assert locals8.hasKey(83)
    assert locals8[82].owner == owner8
    assert locals8[83].owner == owner8

    # --- Test 9: copyInlineProcBody on nkParForStmt ---
    with var:
        locals9 = initTable[nint, PSym]()
        parForVarSym = makeSym(90, TSymKind.skVar, string("idx"))
        parForVarNode = newSymNode(parForVarSym, 0)
        parIterCall = makeNode(TNodeKind.nkCall)
        parLoopBody = makeNode(TNodeKind.nkStmtList)
        parForStmt = makeNodeWithSons(TNodeKind.nkParForStmt, seq[PNode]([parForVarNode, parIterCall, parLoopBody]))

    with let:
        copiedParFor = copyInlineProcBody(parForStmt, locals9, idgen, callerProc)
    assert copiedParFor.kind == TNodeKind.nkParForStmt
    assert copiedParFor[0].sym.id != 90
    assert locals9.hasKey(90)
    assert locals9[90] == copiedParFor[0].sym

    # --- Test 10: copyInlineProcBody skips all routineDefs and syntax sections ---
    with var:
        funcDef = makeNode(TNodeKind.nkFuncDef)
        methodDef = makeNode(TNodeKind.nkMethodDef)
        iterDef = makeNode(TNodeKind.nkIteratorDef)
        convDef = makeNode(TNodeKind.nkConverterDef)
        macroDef = makeNode(TNodeKind.nkMacroDef)
        templDef = makeNode(TNodeKind.nkTemplateDef)
        typeOfExpr = makeNode(TNodeKind.nkTypeOfExpr)
        mixinStmt = makeNode(TNodeKind.nkMixinStmt)
        bindStmt = makeNode(TNodeKind.nkBindStmt)
        constSection = makeNode(TNodeKind.nkConstSection)
    assert copyInlineProcBody(funcDef, locals9, idgen, callerProc) == funcDef
    assert copyInlineProcBody(methodDef, locals9, idgen, callerProc) == methodDef
    assert copyInlineProcBody(iterDef, locals9, idgen, callerProc) == iterDef
    assert copyInlineProcBody(convDef, locals9, idgen, callerProc) == convDef
    assert copyInlineProcBody(macroDef, locals9, idgen, callerProc) == macroDef
    assert copyInlineProcBody(templDef, locals9, idgen, callerProc) == templDef
    assert copyInlineProcBody(typeOfExpr, locals9, idgen, callerProc) == typeOfExpr
    assert copyInlineProcBody(mixinStmt, locals9, idgen, callerProc) == mixinStmt
    assert copyInlineProcBody(bindStmt, locals9, idgen, callerProc) == bindStmt
    assert copyInlineProcBody(constSection, locals9, idgen, callerProc) == constSection

    # --- Test 11: recursive copySymdef on non-atoms ---
    with var:
        locals11 = initTable[nint, PSym]()
        childSym = makeSym(110, TSymKind.skVar, string("c1"))
        childSymNode = newSymNode(childSym, 0)
        leafLit = makeNode(TNodeKind.nkIntLit)
        callNode = makeNodeWithSons(TNodeKind.nkCall, seq[PNode]([childSymNode, leafLit]))
    with let:
        copiedCall = copySymdef(callNode, locals11, idgen, callerProc)
    assert copiedCall.kind == TNodeKind.nkCall
    assert copiedCall.len == 2
    assert copiedCall[0].sym.id != 110
    assert copiedCall[0].sym.owner == callerProc
    assert locals11.hasKey(110)
    assert copiedCall[1] == leafLit

    # --- Test 12: copyParams with multiple parameters in single identDefs ---
    with var:
        locals12 = initTable[nint, PSym]()
        owner12 = makeSym(120, TSymKind.skProc, string("multiParamProc"))
        ownerTyp12 = makeType(1)
    owner12.typ = ownerTyp12
    with var:
        p1Sym = makeSym(121, TSymKind.skParam, string("p1"))
        p2Sym = makeSym(122, TSymKind.skParam, string("p2"))
        p1Node = newSymNode(p1Sym, 0)
        p2Node = newSymNode(p2Sym, 0)
        pTypeNode = makeNode(TNodeKind.nkIdent)
        pDefValNode = makeNode(TNodeKind.nkEmpty)
        multiDefs = makeNodeWithSons(TNodeKind.nkIdentDefs, seq[PNode]([p1Node, p2Node, pTypeNode, pDefValNode]))
        retNode = makeNode(TNodeKind.nkEmpty)
        formalParams = makeNodeWithSons(TNodeKind.nkFormalParams, seq[PNode]([retNode, multiDefs]))
    with let:
        copiedMultiParams = copyParams(formalParams, locals12, idgen, owner12)
    assert copiedMultiParams[0] == retNode
    assert copiedMultiParams[1][0].sym.id != 121
    assert copiedMultiParams[1][1].sym.id != 122
    assert locals12.hasKey(121)
    assert locals12.hasKey(122)
    assert locals12[121].owner == owner12
    assert locals12[122].owner == owner12
    assert owner12.typ.sons.len == 2

    # --- Test 13: copyInlineProc on void procedure ---
    with var:
        voidProc = makeSym(130, TSymKind.skProc, string("voidProc"))
        voidTyp = makeType(1)
    voidProc.typ = voidTyp
    with var:
        voidAstSons: seq[PNode] = seq[PNode]()
    for k in range(8):
        voidAstSons.add(makeNode(TNodeKind.nkEmpty))
    voidAstSons[paramsPos] = makeNode(TNodeKind.nkFormalParams)
    voidAstSons[resultPos] = makeNode(TNodeKind.nkEmpty)
    voidAstSons[6] = makeNode(TNodeKind.nkStmtList)
    voidProc.ast = makeNodeWithSons(TNodeKind.nkProcDef, voidAstSons)

    with let:
        clonedVoidProc = copyInlineProc(voidProc, idgen)
    assert clonedVoidProc.id != voidProc.id
    assert clonedVoidProc.ast[resultPos].kind == TNodeKind.nkEmpty
    assert clonedVoidProc.ast[6].kind == TNodeKind.nkStmtList

    echo(string("All inliner tests passed successfully."))
