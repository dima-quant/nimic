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

if comptime(__name__ == "__main__"):
    class TTypeKind(NIntEnum):
        tyNone = 0
        tyInt = auto()
        tySink = auto()
        tyOwned = auto()
        tyGenericInst = auto()
        tyUserTypeClassInst = auto()
        tyAlias = auto()
        tyRef = auto()
        tyPtr = auto()
        tyVar = auto()

    class TTypeFlag(NIntEnum):
        tfHasOwned = 0

    class TSymKind(NIntEnum):
        skUnknown = 0
        skParam = auto()
        skVar = auto()
        skLet = auto()
        skConst = auto()
        skField = auto()
        skProc = auto()

    class TSymFlag(NIntEnum):
        sfGlobal = 0
        sfThread = auto()
        sfCursor = auto()

    with const:
        abstractInst = {
            TTypeKind.tyGenericInst,
            TTypeKind.tyUserTypeClassInst,
            TTypeKind.tyAlias,
        }
        nkLiterals = {
            TNodeKind.nkCharLit,
            TNodeKind.nkIntLit,
            TNodeKind.nkInt8Lit,
            TNodeKind.nkInt16Lit,
            TNodeKind.nkInt32Lit,
            TNodeKind.nkInt64Lit,
            TNodeKind.nkUIntLit,
            TNodeKind.nkUInt8Lit,
            TNodeKind.nkUInt16Lit,
            TNodeKind.nkUInt32Lit,
            TNodeKind.nkUInt64Lit,
            TNodeKind.nkFloatLit,
            TNodeKind.nkFloat32Lit,
            TNodeKind.nkFloat64Lit,
            TNodeKind.nkFloat128Lit,
            TNodeKind.nkStrLit,
            TNodeKind.nkRStrLit,
            TNodeKind.nkTripleStrLit,
        }

    @ref
    class PType(Object):
        kind: TTypeKind
        flags: Tset[TTypeFlag]
        base: PType

    @ref
    class PSym(Object):
        id: nint
        name: string
        kind: TSymKind
        flags: Tset[TSymFlag]
        owner: PSym
        typ: PType

    @ref
    class PNode(Object):
        kind: TNodeKind
        sym: PSym
        typ: PType
        intVal: nint
        sons: seq[PNode]

        def __getitem__(self, i: nint) -> PNode:
            return self.sons[i]

        def __setitem__(self, i: nint, val: PNode):
            self.sons[i] = val

        @property
        def len(self) -> nint:
            return self.sons.len

    def makeType(kind: TTypeKind, flags: Tset[TTypeFlag] = Tset(), base: PType = None) -> PType:
        with var:
            t = PType()
        t.kind = kind
        t.flags = flags
        t.base = base
        return t

    def skipTypes(t: PType, kinds: Tset[TTypeKind]) -> PType:
        with var:
            curr = t
        while curr is not None and curr.kind in kinds:
            curr = curr.base
        return curr

    def isSinkParam(s: PSym) -> bool:
        return s.kind == TSymKind.skParam and (
            s.typ.kind == TTypeKind.tySink or (TTypeFlag.tfHasOwned in s.typ.flags)
        )

    def makeSym(id: nint, kind: TSymKind, name: string, owner: PSym = None, typ: PType = None) -> PSym:
        with var:
            s = PSym()
        s.id = id
        s.kind = kind
        s.name = name
        s.owner = owner
        s.typ = typ
        s.flags = Tset[TSymFlag]()
        return s

    def makeNode(kind: TNodeKind) -> PNode:
        with var:
            n = PNode()
        n.kind = kind
        n.sym = None
        n.typ = None
        n.intVal = 0
        n.sons = seq[PNode]()
        return n

    def makeNodeWithSons(kind: TNodeKind, sons: seq[PNode]) -> PNode:
        with var:
            n = PNode()
        n.kind = kind
        n.sym = None
        n.typ = None
        n.intVal = 0
        n.sons = sons
        return n

    def newSymNode(sym: PSym) -> PNode:
        with var:
            n = makeNode(TNodeKind.nkSym)
        n.sym = sym
        return n

    def newIntNode(val: nint) -> PNode:
        with var:
            n = makeNode(TNodeKind.nkIntLit)
        n.intVal = val
        return n

with const:
    PathKinds0 = {
        TNodeKind.nkDotExpr,
        TNodeKind.nkCheckedFieldExpr,
        TNodeKind.nkBracketExpr,
        TNodeKind.nkDerefExpr,
        TNodeKind.nkHiddenDeref,
        TNodeKind.nkAddr,
        TNodeKind.nkHiddenAddr,
        TNodeKind.nkObjDownConv,
        TNodeKind.nkObjUpConv,
    }
    PathKinds1 = {
        TNodeKind.nkHiddenStdConv,
        TNodeKind.nkHiddenSubConv,
    }

def skipConvDfa(n: PNode) -> PNode:
    result = n
    while True:
        match result.kind:
            case TNodeKind.nkObjDownConv | TNodeKind.nkObjUpConv:
                result = result[0]
            case TNodeKind.nkHiddenStdConv | TNodeKind.nkHiddenSubConv:
                result = result[1]
            case _:
                break
    return result

def isAnalysableFieldAccess(orig: PNode, owner: PSym) -> bool:
    with var:
        n = orig
    while True:
        match n.kind:
            case (
                TNodeKind.nkDotExpr
                | TNodeKind.nkCheckedFieldExpr
                | TNodeKind.nkBracketExpr
                | TNodeKind.nkAddr
                | TNodeKind.nkHiddenAddr
                | TNodeKind.nkObjDownConv
                | TNodeKind.nkObjUpConv
            ):
                n = n[0]
            case TNodeKind.nkHiddenStdConv | TNodeKind.nkHiddenSubConv:
                n = n[1]
            case TNodeKind.nkHiddenDeref | TNodeKind.nkDerefExpr:
                # We "own" sinkparam[].loc but not ourVar[].location as it is a nasty
                # pointer indirection.
                # bug #14159, we cannot reason about sinkParam[].location as it can
                # still be shared for tyRef.
                n = n[0]
                return (
                    n.kind == TNodeKind.nkSym
                    and n.sym.owner == owner
                    and (skipTypes(n.sym.typ, abstractInst - {TTypeKind.tyOwned}).kind in {TTypeKind.tyOwned})
                )
            case _:
                break
    # XXX Allow closure deref operations here if we know
    # the owner controlled the closure allocation?
    result = (
        n.kind == TNodeKind.nkSym
        and n.sym.owner == owner
        and ({TSymFlag.sfGlobal, TSymFlag.sfThread, TSymFlag.sfCursor} * n.sym.flags == Tset())
        and (n.sym.kind != TSymKind.skParam or isSinkParam(n.sym))  # or n.sym.typ.kind == tyVar)
    )
    # Note: There is a different move analyzer possible that checks for
    # consume(param.key); param.key = newValue  for all paths. Then code like
    #
    #   let splited = split(move self.root, x)
    #   self.root = merge(splited.lower, splited.greater)
    #
    # could be written without the ``move self.root``. However, this would be
    # wrong! Then the write barrier for the ``self.root`` assignment would
    # free the old data and all is lost! Lesson: Don't be too smart, trust the
    # lower level C++ optimizer to specialize this code.
    return result

class AliasKind(NIntEnum):
    yes = 0
    no = auto()
    maybe = auto()

def _collect_important_nodes(n: PNode, outNodes: mut @ seq[PNode]) -> bool:
    with var:
        curr = n
    while True:
        match curr.kind:
            case (
                TNodeKind.nkCheckedFieldExpr
                | TNodeKind.nkAddr
                | TNodeKind.nkHiddenAddr
                | TNodeKind.nkObjDownConv
                | TNodeKind.nkObjUpConv
            ):
                curr = curr[0]
            case TNodeKind.nkHiddenStdConv | TNodeKind.nkHiddenSubConv:
                curr = curr[1]
            case (
                TNodeKind.nkDotExpr
                | TNodeKind.nkBracketExpr
                | TNodeKind.nkDerefExpr
                | TNodeKind.nkHiddenDeref
            ):
                outNodes.add(curr)
                curr = curr[0]
            case TNodeKind.nkSym:
                outNodes.add(curr)
                break
            case _:
                return False
    return True

def aliases(obj: PNode, field: PNode) -> AliasKind:
    # obj -> field:
    # x -> x: true
    # x -> x.f: true
    # x.f -> x: false
    # x.f -> x.f: true
    # x.f -> x.v: false
    # x -> x[]: true
    # x[] -> x: false
    # x -> x[0]: true
    # x[0] -> x: false
    # x[0] -> x[0]: true
    # x[0] -> x[1]: false
    # x -> x[i]: true
    # x[i] -> x: false
    # x[i] -> x[i]: maybe; Further analysis could make this return true when i is a runtime-constant
    # x[i] -> x[j]: maybe; also returns maybe if only one of i or j is a compiletime-constant
    with var:
        objImportantNodes: seq[PNode] = seq[PNode]()
        fieldImportantNodes: seq[PNode] = seq[PNode]()

    if not _collect_important_nodes(obj, objImportantNodes):
        return AliasKind.no
    if not _collect_important_nodes(field, fieldImportantNodes):
        return AliasKind.no

    # If field is less nested than obj, then it cannot be part of/aliased by obj
    if fieldImportantNodes.len < objImportantNodes.len:
        return AliasKind.no

    result = AliasKind.yes
    for i in inrange(1, objImportantNodes.len):
        # We compare the nodes leading to the location of obj and field
        # with each other.
        # We continue until they diverge, in which case we return no, or
        # until we reach the location of obj, in which case we do not need
        # to look further, since field must be part of/aliased by obj now.
        # If we encounter an element access using an index which is a runtime value,
        # we simply return maybe instead of yes; should further nodes not diverge.
        with let:
            currFieldPath = fieldImportantNodes[fieldImportantNodes.len - i]
            currObjPath = objImportantNodes[objImportantNodes.len - i]

        if currFieldPath.kind != currObjPath.kind:
            return AliasKind.no

        match currFieldPath.kind:
            case TNodeKind.nkSym:
                if currFieldPath.sym != currObjPath.sym:
                    return AliasKind.no
            case TNodeKind.nkDotExpr:
                if currFieldPath[1].sym != currObjPath[1].sym:
                    return AliasKind.no
            case TNodeKind.nkDerefExpr | TNodeKind.nkHiddenDeref:
                discard
            case TNodeKind.nkBracketExpr:
                if currFieldPath[1].kind in nkLiterals and currObjPath[1].kind in nkLiterals:
                    if currFieldPath[1].intVal != currObjPath[1].intVal:
                        return AliasKind.no
                else:
                    result = AliasKind.maybe
            case _:
                assert False  # unreachable
    return result

if comptime(__name__ == "__main__"):
    # Tests

    # 0. Test PathKinds0, PathKinds1, and AliasKind
    assert TNodeKind.nkDotExpr in PathKinds0
    assert TNodeKind.nkCheckedFieldExpr in PathKinds0
    assert TNodeKind.nkBracketExpr in PathKinds0
    assert TNodeKind.nkDerefExpr in PathKinds0
    assert TNodeKind.nkHiddenDeref in PathKinds0
    assert TNodeKind.nkAddr in PathKinds0
    assert TNodeKind.nkHiddenAddr in PathKinds0
    assert TNodeKind.nkObjDownConv in PathKinds0
    assert TNodeKind.nkObjUpConv in PathKinds0
    assert len(PathKinds0) == 9

    assert TNodeKind.nkHiddenStdConv in PathKinds1
    assert TNodeKind.nkHiddenSubConv in PathKinds1
    assert len(PathKinds1) == 2

    assert TNodeKind.nkHiddenStdConv not in PathKinds0
    assert TNodeKind.nkDotExpr not in PathKinds1

    assert nint(AliasKind.yes) == 0
    assert nint(AliasKind.no) == 1
    assert nint(AliasKind.maybe) == 2

    # 1. Test skipConvDfa
    with var:
        targetNode = makeNode(TNodeKind.nkIdent)
        downConvNode = makeNodeWithSons(TNodeKind.nkObjDownConv, seq[PNode]([targetNode]))
        upConvNode = makeNodeWithSons(TNodeKind.nkObjUpConv, seq[PNode]([downConvNode]))
        stdConvNode = makeNodeWithSons(TNodeKind.nkHiddenStdConv, seq[PNode]([makeNode(TNodeKind.nkEmpty), upConvNode]))
        subConvNode = makeNodeWithSons(TNodeKind.nkHiddenSubConv, seq[PNode]([makeNode(TNodeKind.nkEmpty), stdConvNode]))
    assert skipConvDfa(subConvNode) == targetNode
    assert skipConvDfa(targetNode) == targetNode

    # 2. Test isAnalysableFieldAccess
    with var:
        ownerProc = makeSym(1, TSymKind.skProc, string("myProc"))
        otherProc = makeSym(2, TSymKind.skProc, string("otherProc"))

        # Owned local variable
        localSym = makeSym(10, TSymKind.skVar, string("locVar"), owner=ownerProc, typ=makeType(TTypeKind.tyInt))
        localSymNode = newSymNode(localSym)

        fieldSym = makeSym(11, TSymKind.skField, string("f"))
        dotNode = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([localSymNode, newSymNode(fieldSym)]))

    assert isAnalysableFieldAccess(dotNode, ownerProc) == True
    # Wrong owner
    assert isAnalysableFieldAccess(dotNode, otherProc) == False

    # Disallowed flags: sfGlobal, sfThread, sfCursor
    localSym.flags.incl(TSymFlag.sfGlobal)
    assert isAnalysableFieldAccess(dotNode, ownerProc) == False
    localSym.flags.excl(TSymFlag.sfGlobal)

    localSym.flags.incl(TSymFlag.sfThread)
    assert isAnalysableFieldAccess(dotNode, ownerProc) == False
    localSym.flags.excl(TSymFlag.sfThread)

    localSym.flags.incl(TSymFlag.sfCursor)
    assert isAnalysableFieldAccess(dotNode, ownerProc) == False
    localSym.flags.excl(TSymFlag.sfCursor)

    # Param without sink
    with var:
        paramSym = makeSym(20, TSymKind.skParam, string("p"), owner=ownerProc, typ=makeType(TTypeKind.tyInt))
        paramDot = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([newSymNode(paramSym), newSymNode(fieldSym)]))
    assert isAnalysableFieldAccess(paramDot, ownerProc) == False

    # Sink param
    paramSym.typ = makeType(TTypeKind.tySink)
    assert isAnalysableFieldAccess(paramDot, ownerProc) == True

    # tfHasOwned flag
    paramSym.typ = makeType(TTypeKind.tyInt, flags=Tset({TTypeFlag.tfHasOwned}))
    assert isAnalysableFieldAccess(paramDot, ownerProc) == True

    # Deref expression: requires owned type
    with var:
        ownedType = makeType(TTypeKind.tyOwned)
        aliasType = makeType(TTypeKind.tyAlias, base=ownedType)
        sinkDerefSym = makeSym(30, TSymKind.skVar, string("sDeref"), owner=ownerProc, typ=aliasType)
        derefNode = makeNodeWithSons(TNodeKind.nkDerefExpr, seq[PNode]([newSymNode(sinkDerefSym)]))
        fieldDerefNode = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([derefNode, newSymNode(fieldSym)]))
    assert isAnalysableFieldAccess(fieldDerefNode, ownerProc) == True

    # Deref with non-owned type fails
    sinkDerefSym.typ = makeType(TTypeKind.tyRef)
    assert isAnalysableFieldAccess(fieldDerefNode, ownerProc) == False

    # Deref with mismatched owner fails
    sinkDerefSym.typ = aliasType
    sinkDerefSym.owner = otherProc
    assert isAnalysableFieldAccess(fieldDerefNode, ownerProc) == False
    sinkDerefSym.owner = ownerProc

    # Deref with non-sym base fails
    with var:
        badDerefNode = makeNodeWithSons(TNodeKind.nkDerefExpr, seq[PNode]([newIntNode(42)]))
    assert isAnalysableFieldAccess(badDerefNode, ownerProc) == False

    # Base node not nkSym fails
    with var:
        callBaseNode = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([newIntNode(42), newSymNode(fieldSym)]))
    assert isAnalysableFieldAccess(callBaseNode, ownerProc) == False

    # Path traversal: checked field, addr, hidden addr, obj down/up conv, hidden std/sub conv
    with var:
        checkedNode = makeNodeWithSons(TNodeKind.nkCheckedFieldExpr, seq[PNode]([localSymNode, newSymNode(fieldSym)]))
        addrNode = makeNodeWithSons(TNodeKind.nkAddr, seq[PNode]([dotNode]))
        hAddrNode = makeNodeWithSons(TNodeKind.nkHiddenAddr, seq[PNode]([dotNode]))
        downConvDotNode = makeNodeWithSons(TNodeKind.nkObjDownConv, seq[PNode]([dotNode]))
        upConvDotNode = makeNodeWithSons(TNodeKind.nkObjUpConv, seq[PNode]([dotNode]))
        hStdConvNode = makeNodeWithSons(TNodeKind.nkHiddenStdConv, seq[PNode]([makeNode(TNodeKind.nkEmpty), dotNode]))
        hSubConvNode = makeNodeWithSons(TNodeKind.nkHiddenSubConv, seq[PNode]([makeNode(TNodeKind.nkEmpty), dotNode]))
    assert isAnalysableFieldAccess(checkedNode, ownerProc) == True
    assert isAnalysableFieldAccess(addrNode, ownerProc) == True
    assert isAnalysableFieldAccess(hAddrNode, ownerProc) == True
    assert isAnalysableFieldAccess(downConvDotNode, ownerProc) == True
    assert isAnalysableFieldAccess(upConvDotNode, ownerProc) == True
    assert isAnalysableFieldAccess(hStdConvNode, ownerProc) == True
    assert isAnalysableFieldAccess(hSubConvNode, ownerProc) == True

    # 3. Test aliases
    # Setup base symbol x
    with var:
        symX = makeSym(100, TSymKind.skVar, string("x"))
        nodeX = newSymNode(symX)

        symF = makeSym(101, TSymKind.skField, string("f"))
        symV = makeSym(102, TSymKind.skField, string("v"))

        nodeX_f = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeX, newSymNode(symF)]))
        nodeX_v = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeX, newSymNode(symV)]))

        nodeX_deref = makeNodeWithSons(TNodeKind.nkDerefExpr, seq[PNode]([nodeX]))

        nodeX_0 = makeNodeWithSons(TNodeKind.nkBracketExpr, seq[PNode]([nodeX, newIntNode(0)]))
        nodeX_1 = makeNodeWithSons(TNodeKind.nkBracketExpr, seq[PNode]([nodeX, newIntNode(1)]))

        varI = makeSym(103, TSymKind.skVar, string("i"))
        varJ = makeSym(104, TSymKind.skVar, string("j"))
        nodeX_i = makeNodeWithSons(TNodeKind.nkBracketExpr, seq[PNode]([nodeX, newSymNode(varI)]))
        nodeX_j = makeNodeWithSons(TNodeKind.nkBracketExpr, seq[PNode]([nodeX, newSymNode(varJ)]))

    # x -> x: yes
    assert aliases(nodeX, nodeX) == AliasKind.yes
    # x -> x.f: yes
    assert aliases(nodeX, nodeX_f) == AliasKind.yes
    # x.f -> x: no
    assert aliases(nodeX_f, nodeX) == AliasKind.no
    # x.f -> x.f: yes
    assert aliases(nodeX_f, nodeX_f) == AliasKind.yes
    # x.f -> x.v: no
    assert aliases(nodeX_f, nodeX_v) == AliasKind.no

    # x -> x[]: yes
    assert aliases(nodeX, nodeX_deref) == AliasKind.yes
    # x[] -> x: no
    assert aliases(nodeX_deref, nodeX) == AliasKind.no

    # x -> x[0]: yes
    assert aliases(nodeX, nodeX_0) == AliasKind.yes
    # x[0] -> x: no
    assert aliases(nodeX_0, nodeX) == AliasKind.no
    # x[0] -> x[0]: yes
    assert aliases(nodeX_0, nodeX_0) == AliasKind.yes
    # x[0] -> x[1]: no
    assert aliases(nodeX_0, nodeX_1) == AliasKind.no

    # x -> x[i]: yes
    assert aliases(nodeX, nodeX_i) == AliasKind.yes
    # x[i] -> x: no
    assert aliases(nodeX_i, nodeX) == AliasKind.no
    # x[i] -> x[i]: maybe
    assert aliases(nodeX_i, nodeX_i) == AliasKind.maybe
    # x[i] -> x[j]: maybe
    assert aliases(nodeX_i, nodeX_j) == AliasKind.maybe

    # Symbol mismatch
    with var:
        symY = makeSym(105, TSymKind.skVar, string("y"))
        nodeY = newSymNode(symY)
    assert aliases(nodeX, nodeY) == AliasKind.no
    assert aliases(nodeX, makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeY, newSymNode(symF)]))) == AliasKind.no

    # Nested subpath aliasing: x.f.g vs x.f.h vs x.f
    with var:
        symG = makeSym(106, TSymKind.skField, string("g"))
        symH = makeSym(107, TSymKind.skField, string("h"))
        nodeX_f_g = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeX_f, newSymNode(symG)]))
        nodeX_f_h = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeX_f, newSymNode(symH)]))
    # x.f -> x.f.g: yes
    assert aliases(nodeX_f, nodeX_f_g) == AliasKind.yes
    # x.f.g -> x.f: no (field is less nested)
    assert aliases(nodeX_f_g, nodeX_f) == AliasKind.no
    # x.f.g -> x.f.h: no (divergence at field)
    assert aliases(nodeX_f_g, nodeX_f_h) == AliasKind.no
    # x.f.g -> x.f.g: yes
    assert aliases(nodeX_f_g, nodeX_f_g) == AliasKind.yes

    # Indexed access combined with fields
    with var:
        nodeX_0_f = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeX_0, newSymNode(symF)]))
        nodeX_1_f = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeX_1, newSymNode(symF)]))
        nodeX_i_f = makeNodeWithSons(TNodeKind.nkDotExpr, seq[PNode]([nodeX_i, newSymNode(symF)]))
    # x[0].f -> x[0].f: yes
    assert aliases(nodeX_0_f, nodeX_0_f) == AliasKind.yes
    # x[0].f -> x[1].f: no
    assert aliases(nodeX_0_f, nodeX_1_f) == AliasKind.no
    # x[i].f -> x[i].f: maybe
    assert aliases(nodeX_i_f, nodeX_i_f) == AliasKind.maybe
    # x[0].f -> x[i].f: maybe
    assert aliases(nodeX_0_f, nodeX_i_f) == AliasKind.maybe
    # x -> x[0].f: yes
    assert aliases(nodeX, nodeX_0_f) == AliasKind.yes
    # x[0] -> x[0].f: yes
    assert aliases(nodeX_0, nodeX_0_f) == AliasKind.yes
    # x[0].f -> x[0]: no
    assert aliases(nodeX_0_f, nodeX_0) == AliasKind.no

    # Hidden deref
    with var:
        nodeX_hidden_deref = makeNodeWithSons(TNodeKind.nkHiddenDeref, seq[PNode]([nodeX]))
    assert aliases(nodeX, nodeX_hidden_deref) == AliasKind.yes
    assert aliases(nodeX_hidden_deref, nodeX) == AliasKind.no

    # Path-transparent nodes: nkAddr, nkObjDownConv
    with var:
        addrNodeX_f = makeNodeWithSons(TNodeKind.nkAddr, seq[PNode]([nodeX_f]))
        downConvNodeX_f = makeNodeWithSons(TNodeKind.nkObjDownConv, seq[PNode]([nodeX_f]))
    assert aliases(nodeX_f, addrNodeX_f) == AliasKind.yes
    assert aliases(addrNodeX_f, nodeX_f) == AliasKind.yes
    assert aliases(downConvNodeX_f, nodeX_f_g) == AliasKind.yes

    # Non-analysable node kinds (e.g. nkCall)
    with var:
        callNode = makeNode(TNodeKind.nkCall)
    assert aliases(nodeX, callNode) == AliasKind.no
    assert aliases(callNode, nodeX) == AliasKind.no

    echo(string("All aliasanalysis tests passed successfully."))
