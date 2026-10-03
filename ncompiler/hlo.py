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

# This include implements the high level optimization pass.
# included from sem.nim

if comptime(__name__ == "__main__"):
    class TSymKind(NIntEnum):
        skUnknown = 0
        skParam = auto()
        skVar = auto()
        skProc = auto()
        skMacro = auto()
        skTemplate = auto()

    class TSymFlag(NIntEnum):
        sfGlobal = 0
        sfPure = auto()

    class TOption(NIntEnum):
        optTrMacros = 0
        optOther = auto()

    class TEvalFlag(NIntEnum):
        efFromHlo = 0

    with const:
        evalTemplateLimit = 10
        renderNoComments = u8(1)
        hintPattern = u8(1)
        warnUser = u8(2)

    @ref
    class PType(Object):
        kind: nint

    @ref
    class PSym(Object):
        kind: TSymKind
        flags: Tset[TSymFlag]
        name: string

    @ref
    class PNode(Object):
        kind: TNodeKind
        sym: PSym
        typ: PType
        info: nint
        sons: seq[PNode]

        @property
        def safeLen(self) -> nint:
            if self.kind in {
                TNodeKind.nkNone,
                TNodeKind.nkEmpty,
                TNodeKind.nkIdent,
                TNodeKind.nkSym,
                TNodeKind.nkType,
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
                TNodeKind.nkNilLit,
            }:
                return 0
            return len(self.sons)

        @property
        def len(self) -> nint:
            return len(self.sons)

        def __getitem__(self, index: nint) -> PNode:
            return self.sons[index]

        def __setitem__(self, index: nint, value: PNode) -> None:
            self.sons[index] = value

    @ref
    class ModuleGraph(Object):
        pass

    @ref
    class IdGenerator(Object):
        pass

    @ref
    class ConfigRef(Object):
        options: Tset[TOption]
        evalTemplateCounter: nint
        hints: Tset[uint8]

        def hasHint(self, h: uint8) -> bool:
            return h in self.hints

    @ref
    class PContext(Object):
        config: ConfigRef
        patterns: seq[PNode]
        graph: ModuleGraph
        idgen: IdGenerator
        module: PSym

    def internalAssert(conf: ConfigRef, e: bool) -> None:
        assert e

    def renderTree(n: PNode, flags: Tset[uint8]) -> string:
        if n is None:
            return string("nil")
        elif n.kind == TNodeKind.nkSym and n.sym is not None:
            return string("sym(") + n.sym.name + string(")")
        elif n.kind == TNodeKind.nkCall:
            return string("call")
        else:
            return string("node")

    @ref
    class TestTracker(Object):
        macro_invoked: bool
        template_invoked: bool
        direct_op_invoked: bool
        last_message: string
        last_warning: string
        last_error: string
        fit_node_count: nint
        common_opt_count: nint

    with var:
        tracker = TestTracker()

    def semMacroExpr(c: PContext, n: PNode, orig: PNode, s: PSym) -> PNode:
        tracker.macro_invoked = True
        return n

    def semTemplateExpr(c: PContext, n: PNode, s: PSym, flags: Tset[TEvalFlag]) -> PNode:
        tracker.template_invoked = True
        return n

    def semDirectOp(c: PContext, n: PNode, flags: Tset[uint8]) -> PNode:
        tracker.direct_op_invoked = True
        return n

    def message(conf: ConfigRef, info: nint, msgKind: uint8, msgText: string) -> None:
        if msgKind == hintPattern:
            tracker.last_message = msgText
        elif msgKind == warnUser:
            tracker.last_warning = msgText

    def globalError(conf: ConfigRef, info: nint, msg: string) -> None:
        tracker.last_error = msg
        raise newException(ValueError, msg)

    def applyRule(c: PContext, pattern: PNode, n: PNode) -> PNode:
        if pattern is not None and n is not None and pattern.sym == n.sym:
            if pattern.kind == TNodeKind.nkStmtList:
                return pattern
            if pattern.len > 1 and pattern.sons[1] is not None:
                return pattern.sons[1]
            with var:
                replacement = PNode()
            replacement.kind = TNodeKind.nkCall
            replacement.sym = pattern.sym
            replacement.typ = n.typ
            replacement.info = 0
            with var:
                callee = PNode()
            callee.kind = TNodeKind.nkSym
            callee.sym = pattern.sym
            callee.typ = n.typ
            callee.info = 0
            callee.sons = seq[PNode]([])
            replacement.sons = seq[PNode]([callee])
            return replacement
        return None

    def flattenStmts(x: PNode) -> PNode:
        return x

    def isEmptyType(t: PType) -> bool:
        return t is None or t.kind == 0

    def fitNode(c: PContext, typ: PType, n: PNode, info: nint) -> PNode:
        tracker.fit_node_count += 1
        return n

    def commonOptimizations(graph: ModuleGraph, idgen: IdGenerator, module: PSym, n: PNode) -> PNode:
        tracker.common_opt_count += 1
        return n

def hlo(c: PContext, n: PNode, loopDetector: nint) -> PNode:
    pass

def evalPattern(c: PContext, n: PNode, orig: PNode) -> PNode:
    internalAssert(c.config, n.kind == TNodeKind.nkCall and n[0].kind == TNodeKind.nkSym)
    # we need to ensure that the resulting AST is semchecked. However, it's
    # awful to semcheck before macro invocation, so we don't and treat
    # templates and macros as immediate in this context.
    with var:
        rule: string = (
            renderTree(n, {renderNoComments})
            if c.config.hasHint(hintPattern)
            else string("")
        )
    with let:
        s = n[0].sym
    match s.kind:
        case TSymKind.skMacro:
            result = semMacroExpr(c, n, orig, s)
        case TSymKind.skTemplate:
            result = semTemplateExpr(c, n, s, {TEvalFlag.efFromHlo})
        case _:
            result = semDirectOp(c, n, Tset())
    if c.config.hasHint(hintPattern):
        message(
            c.config,
            orig.info,
            hintPattern,
            rule + string(" --> '") + renderTree(result, {renderNoComments}) + string("'"),
        )
    return result

def applyPatterns(c: PContext, n: PNode) -> PNode:
    result = n
    # we apply the last pattern first, so that pattern overriding is possible;
    # however the resulting AST would better not trigger the old rule then
    # anymore ;-)
    for i in countdown(c.patterns.len - 1, 0):
        with let:
            pattern = c.patterns[i]
        if pattern is not None:
            with let:
                x = applyRule(c, pattern, result)
            if x is not None:
                assert x.kind in {TNodeKind.nkStmtList, TNodeKind.nkCall}
                # better be safe than sorry, so check evalTemplateCounter too:
                c.config.evalTemplateCounter += 1
                if c.config.evalTemplateCounter > evalTemplateLimit:
                    globalError(c.config, n.info, string("template instantiation too nested"))
                # deactivate this pattern:
                c.patterns[i] = None
                if x.kind == TNodeKind.nkStmtList:
                    assert x.len == 3
                    x[1] = evalPattern(c, x[1], result)
                    result = flattenStmts(x)
                else:
                    result = evalPattern(c, x, result)
                c.config.evalTemplateCounter -= 1
                # activate this pattern again:
                c.patterns[i] = pattern
    return result

def hlo(c: PContext, n: PNode, loopDetector: nint) -> PNode:
    # simply stop and do not perform any further transformations:
    if loopDetector > 300:
        message(c.config, n.info, warnUser, string("term rewrite macro instantiation too nested"))
        return n
    match n.kind:
        case (
            TNodeKind.nkMacroDef
            | TNodeKind.nkTemplateDef
            | TNodeKind.nkLambda
            | TNodeKind.nkDo
            | TNodeKind.nkProcDef
            | TNodeKind.nkFuncDef
            | TNodeKind.nkMethodDef
            | TNodeKind.nkIteratorDef
            | TNodeKind.nkConverterDef
        ):
            # already processed (special cases in semstmts.nim)
            result = n
        case _:
            if (
                n.kind in {TNodeKind.nkFastAsgn, TNodeKind.nkAsgn, TNodeKind.nkSinkAsgn, TNodeKind.nkIdentDefs, TNodeKind.nkVarTuple}
                and n[0].kind == TNodeKind.nkSym
                and ({TSymFlag.sfGlobal, TSymFlag.sfPure} <= n[0].sym.flags)
            ):
                # do not optimize 'var g {.global} = re(...)' again!
                return n
            result = applyPatterns(c, n)
            if result == n:
                # no optimization applied, try subtrees:
                for i in range(result.safeLen):
                    with let:
                        a = result[i]
                        h = hlo(c, a, loopDetector)
                    if h != a:
                        result[i] = h
            else:
                # perform type checking, so that the replacement still fits:
                if isEmptyType(n.typ) and isEmptyType(result.typ):
                    discard
                else:
                    result = fitNode(c, n.typ, result, n.info)
                # optimization has been applied so check again:
                result = commonOptimizations(c.graph, c.idgen, c.module, result)
                result = hlo(c, result, loopDetector + 1)
                result = commonOptimizations(c.graph, c.idgen, c.module, result)
    return result

def hloBody(c: PContext, n: PNode) -> PNode:
    # fast exit:
    if c.patterns.len == 0 or TOption.optTrMacros not in c.config.options:
        return n
    result = hlo(c, n, 0)
    return result

def hloStmt(c: PContext, n: PNode) -> PNode:
    # fast exit:
    if c.patterns.len == 0 or TOption.optTrMacros not in c.config.options:
        return n
    result = hlo(c, n, 0)
    return result

if comptime(__name__ == "__main__"):
    def newNode(kind: TNodeKind) -> PNode:
        with var:
            res = PNode()
        res.kind = kind
        res.info = 0
        res.sons = seq[PNode]([])
        return res

    def newNodeWithSons(kind: TNodeKind, sons: seq[PNode]) -> PNode:
        with var:
            res = PNode()
        res.kind = kind
        res.info = 0
        res.sons = sons
        return res

    def newSym(kind: TSymKind, name: string) -> PSym:
        with var:
            res = PSym()
        res.kind = kind
        res.name = name
        res.flags = Tset[TSymFlag]()
        return res

    def newSymWithFlags(kind: TSymKind, name: string, flags: Tset[TSymFlag]) -> PSym:
        with var:
            res = PSym()
        res.kind = kind
        res.name = name
        res.flags = flags
        return res

    def newContext() -> PContext:
        with var:
            res = PContext()
            conf = ConfigRef()
        conf.options = Tset[TOption]({TOption.optTrMacros})
        conf.evalTemplateCounter = 0
        conf.hints = Tset[uint8]()
        res.config = conf
        res.patterns = seq[PNode]([])
        res.graph = ModuleGraph()
        res.idgen = IdGenerator()
        res.module = newSym(TSymKind.skProc, string("testMod"))
        return res

    # --- Test 1: Fast exit when patterns are empty ---
    with var:
        c1 = newContext()
        symNode = newNode(TNodeKind.nkSym)
    symNode.sym = newSym(TSymKind.skVar, string("x"))
    with var:
        callNode = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([symNode]))

    assert hloBody(c1, callNode) == callNode
    assert hloStmt(c1, callNode) == callNode

    # --- Test 2: Fast exit when optTrMacros is disabled ---
    with var:
        c2 = newContext()
        patSym = newSym(TSymKind.skProc, string("pat"))
        patSymNode = newNode(TNodeKind.nkSym)
    patSymNode.sym = patSym
    with var:
        patNode = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([patSymNode]))
    patNode.sym = patSym
    c2.patterns.add(patNode)
    c2.config.options = Tset[TOption]() # remove optTrMacros

    assert hloBody(c2, callNode) == callNode
    assert hloStmt(c2, callNode) == callNode

    # --- Test 3: Loop detector recursion limit ---
    with var:
        c3 = newContext()
    tracker.last_warning = string("")
    with let:
        loopRes = hlo(c3, callNode, 301)
    assert loopRes == callNode
    assert len(tracker.last_warning) > 0

    # --- Test 4: Skip routine definitions ---
    with var:
        c4 = newContext()
        procNode = newNode(TNodeKind.nkProcDef)
        macroNode = newNode(TNodeKind.nkMacroDef)
        templNode = newNode(TNodeKind.nkTemplateDef)
        lambdaNode = newNode(TNodeKind.nkLambda)
    c4.patterns.add(patNode)

    assert hlo(c4, procNode, 0) == procNode
    assert hlo(c4, macroNode, 0) == macroNode
    assert hlo(c4, templNode, 0) == templNode
    assert hlo(c4, lambdaNode, 0) == lambdaNode

    # --- Test 5: Skip global pure variables ---
    with var:
        c5 = newContext()
        globPureSym = newSymWithFlags(TSymKind.skVar, string("g"), Tset[TSymFlag]({TSymFlag.sfGlobal, TSymFlag.sfPure}))
        globPureSymNode = newNode(TNodeKind.nkSym)
    globPureSymNode.sym = globPureSym
    with var:
        intLitNode = newNode(TNodeKind.nkIntLit)
        asgnNode = newNodeWithSons(TNodeKind.nkAsgn, seq[PNode]([globPureSymNode, intLitNode]))
    c5.patterns.add(patNode)

    assert hlo(c5, asgnNode, 0) == asgnNode

    # --- Test 6: evalPattern macro, template, directOp and hints ---
    with var:
        c6 = newContext()
        macroSym = newSym(TSymKind.skMacro, string("myMacro"))
        macroSymNode = newNode(TNodeKind.nkSym)
    macroSymNode.sym = macroSym
    with var:
        macroCall = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([macroSymNode]))
    tracker.macro_invoked = False
    with let:
        rMacro = evalPattern(c6, macroCall, macroCall)
    assert tracker.macro_invoked
    assert rMacro == macroCall

    with var:
        templSym = newSym(TSymKind.skTemplate, string("myTempl"))
        templSymNode = newNode(TNodeKind.nkSym)
    templSymNode.sym = templSym
    with var:
        templCall = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([templSymNode]))
    tracker.template_invoked = False
    with let:
        rTempl = evalPattern(c6, templCall, templCall)
    assert tracker.template_invoked
    assert rTempl == templCall

    with var:
        procSym = newSym(TSymKind.skProc, string("myProc"))
        procSymNode = newNode(TNodeKind.nkSym)
    procSymNode.sym = procSym
    with var:
        procCall = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([procSymNode]))
    tracker.direct_op_invoked = False
    with let:
        rProc = evalPattern(c6, procCall, procCall)
    assert tracker.direct_op_invoked
    assert rProc == procCall

    # Hint reporting
    c6.config.hints = Tset[uint8]({hintPattern})
    tracker.last_message = string("")
    with let:
        rProcHint = evalPattern(c6, procCall, procCall)
    assert len(tracker.last_message) > 0

    # --- Test 7: Subtree optimization when result == n ---
    with var:
        c7 = newContext()
        child1 = newNode(TNodeKind.nkIdent)
        child2 = newNode(TNodeKind.nkIdent)
        parent = newNodeWithSons(TNodeKind.nkStmtList, seq[PNode]([child1, child2]))
    # No pattern matches parent or children
    with let:
        resTree = hlo(c7, parent, 0)
    assert resTree == parent

    # --- Test 8: applyPatterns and fitNode execution on match ---
    with var:
        c8 = newContext()
        matchSym = newSym(TSymKind.skProc, string("matchP"))
        matchSymNode = newNode(TNodeKind.nkSym)
    matchSymNode.sym = matchSym
    with var:
        matchNode = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([matchSymNode]))
        targetTyp = PType()
    targetTyp.kind = 1
    matchNode.sym = matchSym
    matchNode.typ = targetTyp

    with var:
        pRuleSymNode = newNode(TNodeKind.nkSym)
    pRuleSymNode.sym = matchSym
    with var:
        pRule = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([pRuleSymNode]))
    pRule.sym = matchSym
    c8.patterns.add(pRule)

    tracker.fit_node_count = 0
    tracker.common_opt_count = 0
    with let:
        resOpt = hlo(c8, matchNode, 0)
    assert resOpt.kind == TNodeKind.nkCall
    assert tracker.fit_node_count > 0
    assert tracker.common_opt_count > 0

    # --- Test 9: applyPatterns with nkStmtList replacement (len == 3) ---
    with var:
        c9 = newContext()
        stmtSym = newSym(TSymKind.skProc, string("stmtP"))
        stmtSymNode = newNode(TNodeKind.nkSym)
    stmtSymNode.sym = stmtSym
    with var:
        stmtNode = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([stmtSymNode]))
        targetTyp9 = PType()
    targetTyp9.kind = 1
    stmtNode.sym = stmtSym
    stmtNode.typ = targetTyp9

    with var:
        sListDirect = PNode()
        callSonDirect = PNode()
        calleeSymDirect = PNode()
    calleeSymDirect.kind = TNodeKind.nkSym
    calleeSymDirect.sym = stmtSym
    calleeSymDirect.typ = targetTyp9
    calleeSymDirect.info = 0
    calleeSymDirect.sons = seq[PNode]([])

    callSonDirect.kind = TNodeKind.nkCall
    callSonDirect.sym = stmtSym
    callSonDirect.typ = targetTyp9
    callSonDirect.info = 0
    callSonDirect.sons = seq[PNode]([calleeSymDirect])

    sListDirect.kind = TNodeKind.nkStmtList
    sListDirect.typ = targetTyp9
    sListDirect.info = 0
    sListDirect.sons = seq[PNode]([newNode(TNodeKind.nkEmpty), callSonDirect, newNode(TNodeKind.nkEmpty)])
    sListDirect.sym = stmtSym

    # Verify applyPatterns executes the nkStmtList branch (len == 3, evalPattern on son[1], flattenStmts)
    c9.patterns.add(sListDirect)
    with let:
        resStmt = applyPatterns(c9, stmtNode)
    assert resStmt == sListDirect
    assert resStmt.len == 3

    # --- Test 10: Nested template limit exceeded ---
    with var:
        c10 = newContext()
    c10.config.evalTemplateCounter = 11 # > evalTemplateLimit (10)
    with var:
        nestSym = newSym(TSymKind.skProc, string("nestP"))
        nestSymNode1 = newNode(TNodeKind.nkSym)
    nestSymNode1.sym = nestSym
    with var:
        nestSymNode2 = newNode(TNodeKind.nkSym)
    nestSymNode2.sym = nestSym
    with var:
        nestNode = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([nestSymNode1]))
        nestRule = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([nestSymNode2]))
    nestNode.sym = nestSym
    nestRule.sym = nestSym
    c10.patterns.add(nestRule)

    with var:
        limitRaised = False
    try:
        with let:
            _dummy = applyPatterns(c10, nestNode)
    except ValueError:
        limitRaised = True
    assert limitRaised

    # --- Test 11: Subtree child replacement in hlo ---
    with var:
        c11 = newContext()
        childSym = newSym(TSymKind.skProc, string("childToReplace"))
        childSymNode = newNode(TNodeKind.nkSym)
    childSymNode.sym = childSym
    with var:
        childCall = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([childSymNode]))
        tTyp11 = PType()
    tTyp11.kind = 1
    childCall.sym = childSym
    childCall.typ = tTyp11

    with var:
        pRuleChildNode = newNode(TNodeKind.nkSym)
    pRuleChildNode.sym = childSym
    with var:
        pRuleChild = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([pRuleChildNode]))
    pRuleChild.sym = childSym
    c11.patterns.add(pRuleChild)

    with var:
        parentTree = newNodeWithSons(TNodeKind.nkStmtList, seq[PNode]([newNode(TNodeKind.nkEmpty), childCall]))
    with let:
        resTreeOpt = hlo(c11, parentTree, 0)
    assert resTreeOpt == parentTree
    assert resTreeOpt[1] != childCall
    assert resTreeOpt[1].kind == TNodeKind.nkCall

    # --- Test 12: isEmptyType skips fitNode ---
    with var:
        c12 = newContext()
        emptyTypeSym = newSym(TSymKind.skProc, string("emptyTypeP"))
        emptyTypeSymNode = newNode(TNodeKind.nkSym)
    emptyTypeSymNode.sym = emptyTypeSym
    with var:
        emptyTypeNode = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([emptyTypeSymNode]))
    emptyTypeNode.sym = emptyTypeSym
    emptyTypeNode.typ = None

    with var:
        pRuleEmptyNode = newNode(TNodeKind.nkSym)
    pRuleEmptyNode.sym = emptyTypeSym
    with var:
        pRuleEmpty = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([pRuleEmptyNode]))
    pRuleEmpty.sym = emptyTypeSym
    c12.patterns.add(pRuleEmpty)

    tracker.fit_node_count = 0
    with let:
        resEmptyOpt = hlo(c12, emptyTypeNode, 0)
    assert resEmptyOpt.kind == TNodeKind.nkCall
    assert tracker.fit_node_count == 0

    # --- Test 13: Assignment without sfGlobal and sfPure is not skipped ---
    with var:
        c13 = newContext()
        localSym = newSymWithFlags(TSymKind.skVar, string("localV"), Tset[TSymFlag]({TSymFlag.sfGlobal}))
        localSymNode = newNode(TNodeKind.nkSym)
    localSymNode.sym = localSym
    with var:
        localAsgnNode = newNodeWithSons(TNodeKind.nkAsgn, seq[PNode]([localSymNode, newNode(TNodeKind.nkIntLit)]))
    c13.patterns.add(patNode)
    with let:
        asgnRes = hlo(c13, localAsgnNode, 0)
    assert asgnRes == localAsgnNode

    # --- Test 14: Pattern overriding in applyPatterns (last added pattern takes precedence) ---
    with var:
        c14 = newContext()
        ovSym = newSym(TSymKind.skProc, string("ovP"))
        ovSymNode = newNode(TNodeKind.nkSym)
    ovSymNode.sym = ovSym
    with var:
        ovNode = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([ovSymNode]))
        ovTyp = PType()
    ovTyp.kind = 1
    ovNode.sym = ovSym
    ovNode.typ = ovTyp

    # Rule 1 produces repl1
    with var:
        replSym1 = newSym(TSymKind.skProc, string("repl1"))
        replSymNode1 = newNode(TNodeKind.nkSym)
    replSymNode1.sym = replSym1
    with var:
        replNode1 = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([replSymNode1]))
        r1SymNode = newNode(TNodeKind.nkSym)
    replNode1.sym = replSym1
    r1SymNode.sym = ovSym
    with var:
        rule1 = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([r1SymNode, replNode1]))
    rule1.sym = ovSym

    # Rule 2 produces repl2 (added last, should override rule 1)
    with var:
        replSym2 = newSym(TSymKind.skProc, string("repl2"))
        replSymNode2 = newNode(TNodeKind.nkSym)
    replSymNode2.sym = replSym2
    with var:
        replNode2 = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([replSymNode2]))
        r2SymNode = newNode(TNodeKind.nkSym)
    replNode2.sym = replSym2
    r2SymNode.sym = ovSym
    with var:
        rule2 = newNodeWithSons(TNodeKind.nkCall, seq[PNode]([r2SymNode, replNode2]))
    rule2.sym = ovSym

    c14.patterns.add(rule1)
    c14.patterns.add(rule2)

    with let:
        ovRes = applyPatterns(c14, ovNode)
    assert ovRes == replNode2
    assert ovRes != replNode1

    echo(string("All hlo tests passed successfully."))
