# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import *
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
        tyProc = auto()
        tyVar = auto()
        tySink = auto()
        tyOwned = auto()
        tyVoid = auto()
        tyTyped = auto()

    class TSymKind(NIntEnum):
        skUnknown = 0
        skParam = auto()
        skVar = auto()
        skProc = auto()
        skOwner = auto()

    class TSymFlag(NIntEnum):
        sfWasForwarded = 0

    with const:
        hintPerformance = 1

    @ref
    class ConfigRef(Object):
        pass

    @ref
    class IdGenerator(Object):
        pass

    @ref
    class SymName(Object):
        s: string

    @ref
    class PType(Object):
        kind: TTypeKind
        size: nint
        align: nint
        paddingAtEnd: nint
        sons: seq[PType]
        n: seq[PNode]
        flags: Tset[TSymFlag]
        hasDestructorVal: bool

        def add(self, son: PType) -> None:
            self.sons.add(son)

    @ref
    class PSym(Object):
        kind: TSymKind
        owner: PSym
        typ: PType
        flagsImpl: Tset[TSymFlag]
        position: nint
        name: SymName

        @property
        def flags(self) -> Tset[TSymFlag]:
            return self.flagsImpl

    @ref
    class PNode(Object):
        kind: TNodeKind
        sym: PSym
        typ: PType
        sons: seq[PNode]
        info: nint

        @property
        def lastSon(self) -> PNode:
            return self.sons[len(self.sons) - 1]

        def __getitem__(self, index: nint) -> PNode:
            return self.sons[index]

        @property
        def len(self) -> nint:
            return len(self.sons)

    def items(n: PNode) -> PNode:
        for s in n.sons:
            yield s

    def newSymName(s: string) -> SymName:
        with var:
            res = SymName()
        res.s = s
        return res

    def newPType(kind: TTypeKind, size: nint = 8, align: nint = 8, hasDestructor: bool = True) -> PType:
        with var:
            res = PType()
        res.kind = kind
        res.size = size
        res.align = align
        res.paddingAtEnd = 0
        res.hasDestructorVal = hasDestructor
        res.sons = seq[PType]([])
        res.n = seq[PNode]([])
        res.flags = Tset[TSymFlag]()
        return res

    def newPSym(kind: TSymKind, owner: PSym = None, typ: PType = None, name: string = string("p"), position: nint = 0) -> PSym:
        with var:
            res = PSym()
        res.kind = kind
        res.owner = owner
        res.typ = typ
        res.flagsImpl = Tset[TSymFlag]()
        res.position = position
        res.name = newSymName(name)
        return res

    def newPNode(kind: TNodeKind, sym: PSym = None, typ: PType = None) -> PNode:
        with var:
            res = PNode()
        res.kind = kind
        res.sym = sym
        res.typ = typ
        res.sons = seq[PNode]([])
        return res

    def newPNodeWithSons(kind: TNodeKind, typ: PType, sons: seq[PNode]) -> PNode:
        with var:
            res = PNode()
        res.kind = kind
        res.typ = typ
        res.sons = sons
        return res

    def hasDestructor(t: PType) -> bool:
        return t.hasDestructorVal if t is not None else False

    def isEmptyType(t: PType) -> bool:
        return t is None or t.kind in {TTypeKind.tyVoid, TTypeKind.tyTyped}

    def newType(kind: TTypeKind, idgen: IdGenerator, owner: PSym) -> PType:
        return newPType(kind=kind, size=0, align=0)

    def ensureMutable(s: PSym) -> None:
        discard

    with var:
        _messages = seq[string]()

    def message(conf: ConfigRef, info: nint, msgKind: nint, msgText: string) -> None:
        _messages.add(msgText)

def checkForSink(config: ConfigRef, idgen: IdGenerator, owner: PSym, arg: PNode) -> None:
    # Patterns we seek to detect:
    #
    # someLocation = p # ---> p: sink T
    # passToSink(p)    # p: sink
    # ObjConstr(fieldName: p)
    # [p, q] # array construction
    #
    # # Open question:
    # var local = p # sink parameter?
    # passToSink(local)
    match arg.kind:
        case TNodeKind.nkSym:
            if (arg.sym.kind == TSymKind.skParam) and \
               (arg.sym.owner == owner) and \
               (owner.typ is not None) and (owner.typ.kind == TTypeKind.tyProc) and \
               hasDestructor(arg.sym.typ) and \
               (arg.sym.typ.kind not in {TTypeKind.tyVar, TTypeKind.tySink, TTypeKind.tyOwned}):
                # Watch out: cannot do this inference for procs with forward
                # declarations.
                if TSymFlag.sfWasForwarded not in owner.flags:
                    with let:
                        argType = arg.sym.typ

                    with let:
                        sinkType = newType(TTypeKind.tySink, idgen, owner)
                    sinkType.size = argType.size
                    sinkType.align = argType.align
                    sinkType.paddingAtEnd = argType.paddingAtEnd
                    sinkType.add(argType)

                    arg.sym.typ = sinkType
                    assert owner.typ.n[arg.sym.position + 1].sym == arg.sym

                    #message(config, arg.info, warnUser,
                    #  ("turned '$1' to a sink parameter") % [$arg])
                    #echo config $ arg.info, " turned into a sink parameter ", arg.sym.name.s
                elif TSymFlag.sfWasForwarded not in arg.sym.flags:
                    # we only report every potential 'sink' parameter only once:
                    ensureMutable(arg.sym)
                    incl(arg.sym.flagsImpl, TSymFlag.sfWasForwarded)
                    message(config, arg.info, hintPerformance,
                            string("could not turn '$1' to a sink parameter") % [arg.sym.name.s])
                #echo config $ arg.info, " candidate for a sink parameter here"
        case TNodeKind.nkStmtList | TNodeKind.nkStmtListExpr | TNodeKind.nkBlockStmt | TNodeKind.nkBlockExpr:
            if not isEmptyType(arg.typ):
                checkForSink(config, idgen, owner, arg.lastSon)
        case TNodeKind.nkIfStmt | TNodeKind.nkIfExpr | TNodeKind.nkWhenStmt:
            for branch in arg:
                with let:
                    value = branch.lastSon
                if not isEmptyType(value.typ):
                    checkForSink(config, idgen, owner, value)
        case TNodeKind.nkCaseStmt:
            for i in range(1, arg.len):
                with let:
                    value = arg[i].lastSon
                if not isEmptyType(value.typ):
                    checkForSink(config, idgen, owner, value)
        case TNodeKind.nkTryStmt:
            checkForSink(config, idgen, owner, arg[0])
        case _:
            _ = "nothing to do"

if comptime(__name__ == "__main__"):
    # Test Suite for checkForSink
    with let:
        _conf = ConfigRef()
        _idgen = IdGenerator()
        _owner = newPSym(kind=TSymKind.skProc)
        _proc_typ = newPType(kind=TTypeKind.tyProc)

    _owner.typ = _proc_typ
    with let:
        _param_type = newPType(kind=TTypeKind.tyInt, size=8, align=8, hasDestructor=True)
        _param_sym = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("myParam"), position=0)

    _proc_typ.n = seq[PNode]([newPNode(kind=TNodeKind.nkNone), newPNode(kind=TNodeKind.nkSym, sym=_param_sym)])

    # Test 1: Basic sink parameter inference
    with let:
        _arg_node = newPNode(kind=TNodeKind.nkSym, sym=_param_sym)

    checkForSink(_conf, _idgen, _owner, _arg_node)
    assert _param_sym.typ.kind == TTypeKind.tySink
    assert _param_sym.typ.size == 8
    assert _param_sym.typ.align == 8
    assert len(_param_sym.typ.sons) == 1
    assert _param_sym.typ.sons[0] == _param_type

    # Test 2: Forwarded proc warning
    with let:
        _owner_fwd = newPSym(kind=TSymKind.skProc)
    _owner_fwd.typ = _proc_typ
    incl(_owner_fwd.flagsImpl, TSymFlag.sfWasForwarded)

    with let:
        _param_sym_fwd = newPSym(kind=TSymKind.skParam, owner=_owner_fwd, typ=_param_type, name=string("forwardedParam"), position=0)
    _proc_typ.n[1].sym = _param_sym_fwd

    with let:
        _arg_node_fwd = newPNode(kind=TNodeKind.nkSym, sym=_param_sym_fwd)

    _messages.setLen(0)
    checkForSink(_conf, _idgen, _owner_fwd, _arg_node_fwd)
    assert _param_sym_fwd.typ.kind != TTypeKind.tySink
    assert TSymFlag.sfWasForwarded in _param_sym_fwd.flagsImpl
    assert len(_messages) == 1
    assert _messages[0] == "could not turn 'forwardedParam' to a sink parameter"

    # Test 3: Statement list recursion
    with let:
        _param_sym3 = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("p3"), position=0)
    _proc_typ.n[1].sym = _param_sym3
    with let:
        _leaf = newPNode(kind=TNodeKind.nkSym, sym=_param_sym3)
        _stmt_list = newPNodeWithSons(TNodeKind.nkStmtList, _param_type, seq[PNode]([_leaf]))

    checkForSink(_conf, _idgen, _owner, _stmt_list)
    assert _param_sym3.typ.kind == TTypeKind.tySink

    # Test 4: If statement branches
    with let:
        _param_sym4 = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("p4"), position=0)
    _proc_typ.n[1].sym = _param_sym4
    with let:
        _leaf4 = newPNode(kind=TNodeKind.nkSym, sym=_param_sym4, typ=_param_type)
        _branch1 = newPNodeWithSons(TNodeKind.nkElifBranch, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _leaf4]))
        _if_stmt = newPNodeWithSons(TNodeKind.nkIfStmt, _param_type, seq[PNode]([_branch1]))

    checkForSink(_conf, _idgen, _owner, _if_stmt)
    assert _param_sym4.typ.kind == TTypeKind.tySink

    # Test 5: Case statement branches
    with let:
        _param_sym5 = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("p5"), position=0)
    _proc_typ.n[1].sym = _param_sym5
    with let:
        _leaf5 = newPNode(kind=TNodeKind.nkSym, sym=_param_sym5, typ=_param_type)
        _case_branch = newPNodeWithSons(TNodeKind.nkOfBranch, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _leaf5]))
        _case_stmt = newPNodeWithSons(TNodeKind.nkCaseStmt, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _case_branch]))

    checkForSink(_conf, _idgen, _owner, _case_stmt)
    assert _param_sym5.typ.kind == TTypeKind.tySink

    # Test 6: Try statement
    with let:
        _param_sym6 = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("p6"), position=0)
    _proc_typ.n[1].sym = _param_sym6
    with let:
        _leaf6 = newPNode(kind=TNodeKind.nkSym, sym=_param_sym6)
        _try_stmt = newPNodeWithSons(TNodeKind.nkTryStmt, _param_type, seq[PNode]([_leaf6]))

    checkForSink(_conf, _idgen, _owner, _try_stmt)
    assert _param_sym6.typ.kind == TTypeKind.tySink

    # Test 7: Non-sink parameter (no destructor)
    with let:
        _no_destruct_type = newPType(kind=TTypeKind.tyInt, size=8, align=8, hasDestructor=False)
        _param_no_destruct = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_no_destruct_type, name=string("pNoDestruct"), position=0)
    _proc_typ.n[1].sym = _param_no_destruct
    with let:
        _arg_no_destruct = newPNode(kind=TNodeKind.nkSym, sym=_param_no_destruct)

    checkForSink(_conf, _idgen, _owner, _arg_no_destruct)
    assert _param_no_destruct.typ.kind != TTypeKind.tySink

    # Test 8: Non-candidate node kind (e.g. nkIntLit)
    with let:
        _int_node = newPNode(kind=TNodeKind.nkIntLit)
    checkForSink(_conf, _idgen, _owner, _int_node)

    # Test 9: Forwarded proc warning deduplication (only report once)
    checkForSink(_conf, _idgen, _owner_fwd, _arg_node_fwd)
    assert len(_messages) == 1

    # Test 10: Parameter that already has sfWasForwarded flag initially
    with let:
        _param_already_fwd = newPSym(kind=TSymKind.skParam, owner=_owner_fwd, typ=_param_type, name=string("pAlreadyFwd"), position=0)
    incl(_param_already_fwd.flagsImpl, TSymFlag.sfWasForwarded)
    _proc_typ.n[1].sym = _param_already_fwd
    with let:
        _arg_already_fwd = newPNode(kind=TNodeKind.nkSym, sym=_param_already_fwd)

    _messages.setLen(0)
    checkForSink(_conf, _idgen, _owner_fwd, _arg_already_fwd)
    assert len(_messages) == 0

    # Test 11: Statement lists and blocks (nkStmtListExpr, nkBlockStmt, nkBlockExpr, isEmptyType guard)
    with let:
        _param_stmt_void = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pStmtVoid"), position=0)
    _proc_typ.n[1].sym = _param_stmt_void
    with let:
        _leaf_stmt_void = newPNode(kind=TNodeKind.nkSym, sym=_param_stmt_void)
        _stmt_void = newPNodeWithSons(TNodeKind.nkStmtList, newPType(kind=TTypeKind.tyVoid), seq[PNode]([_leaf_stmt_void]))

    checkForSink(_conf, _idgen, _owner, _stmt_void)
    assert _param_stmt_void.typ.kind != TTypeKind.tySink

    # nkStmtListExpr
    with let:
        _param_stmt_expr = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pStmtExpr"), position=0)
    _proc_typ.n[1].sym = _param_stmt_expr
    with let:
        _leaf_stmt_expr = newPNode(kind=TNodeKind.nkSym, sym=_param_stmt_expr)
        _stmt_expr = newPNodeWithSons(TNodeKind.nkStmtListExpr, _param_type, seq[PNode]([_leaf_stmt_expr]))

    checkForSink(_conf, _idgen, _owner, _stmt_expr)
    assert _param_stmt_expr.typ.kind == TTypeKind.tySink

    # nkBlockStmt
    with let:
        _param_block_stmt = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pBlockStmt"), position=0)
    _proc_typ.n[1].sym = _param_block_stmt
    with let:
        _leaf_block_stmt = newPNode(kind=TNodeKind.nkSym, sym=_param_block_stmt)
        _block_stmt = newPNodeWithSons(TNodeKind.nkBlockStmt, _param_type, seq[PNode]([_leaf_block_stmt]))

    checkForSink(_conf, _idgen, _owner, _block_stmt)
    assert _param_block_stmt.typ.kind == TTypeKind.tySink

    # nkBlockExpr
    with let:
        _param_block_expr = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pBlockExpr"), position=0)
    _proc_typ.n[1].sym = _param_block_expr
    with let:
        _leaf_block_expr = newPNode(kind=TNodeKind.nkSym, sym=_param_block_expr)
        _block_expr = newPNodeWithSons(TNodeKind.nkBlockExpr, _param_type, seq[PNode]([_leaf_block_expr]))

    checkForSink(_conf, _idgen, _owner, _block_expr)
    assert _param_block_expr.typ.kind == TTypeKind.tySink

    # Test 12: If expressions, When statements, and isEmptyType on branch
    with let:
        _param_if_expr = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pIfExpr"), position=0)
    _proc_typ.n[1].sym = _param_if_expr
    with let:
        _leaf_if_expr = newPNode(kind=TNodeKind.nkSym, sym=_param_if_expr, typ=_param_type)
        _branch_if_expr = newPNodeWithSons(TNodeKind.nkElifExpr, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _leaf_if_expr]))
        _if_expr = newPNodeWithSons(TNodeKind.nkIfExpr, _param_type, seq[PNode]([_branch_if_expr]))

    checkForSink(_conf, _idgen, _owner, _if_expr)
    assert _param_if_expr.typ.kind == TTypeKind.tySink

    with let:
        _param_when = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pWhen"), position=0)
    _proc_typ.n[1].sym = _param_when
    with let:
        _leaf_when = newPNode(kind=TNodeKind.nkSym, sym=_param_when, typ=_param_type)
        _branch_when = newPNodeWithSons(TNodeKind.nkElifBranch, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _leaf_when]))
        _when_stmt = newPNodeWithSons(TNodeKind.nkWhenStmt, _param_type, seq[PNode]([_branch_when]))

    checkForSink(_conf, _idgen, _owner, _when_stmt)
    assert _param_when.typ.kind == TTypeKind.tySink

    with let:
        _param_branch_void = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pBranchVoid"), position=0)
    _proc_typ.n[1].sym = _param_branch_void
    with let:
        _leaf_branch_void = newPNode(kind=TNodeKind.nkSym, sym=_param_branch_void, typ=newPType(kind=TTypeKind.tyVoid))
        _branch_void = newPNodeWithSons(TNodeKind.nkElifBranch, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _leaf_branch_void]))
        _if_void_stmt = newPNodeWithSons(TNodeKind.nkIfStmt, _param_type, seq[PNode]([_branch_void]))

    checkForSink(_conf, _idgen, _owner, _if_void_stmt)
    assert _param_branch_void.typ.kind != TTypeKind.tySink

    # Test 13: Case statement boundary conditions
    with let:
        _case_empty = newPNodeWithSons(TNodeKind.nkCaseStmt, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent)]))
    checkForSink(_conf, _idgen, _owner, _case_empty)

    with let:
        _param_case_void = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_param_type, name=string("pCaseVoid"), position=0)
    _proc_typ.n[1].sym = _param_case_void
    with let:
        _leaf_case_void = newPNode(kind=TNodeKind.nkSym, sym=_param_case_void, typ=newPType(kind=TTypeKind.tyVoid))
        _case_branch_void = newPNodeWithSons(TNodeKind.nkOfBranch, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _leaf_case_void]))
        _case_void_stmt = newPNodeWithSons(TNodeKind.nkCaseStmt, _param_type, seq[PNode]([newPNode(kind=TNodeKind.nkIdent), _case_branch_void]))

    checkForSink(_conf, _idgen, _owner, _case_void_stmt)
    assert _param_case_void.typ.kind != TTypeKind.tySink

    # Test 14: Disqualification checks on candidate symbol
    with let:
        _var_sym = newPSym(kind=TSymKind.skVar, owner=_owner, typ=_param_type, name=string("myVar"), position=0)
        _arg_var = newPNode(kind=TNodeKind.nkSym, sym=_var_sym)
    checkForSink(_conf, _idgen, _owner, _arg_var)
    assert _var_sym.typ.kind != TTypeKind.tySink

    with let:
        _other_owner = newPSym(kind=TSymKind.skProc)
    _other_owner.typ = _proc_typ
    with let:
        _mismatched_sym = newPSym(kind=TSymKind.skParam, owner=_other_owner, typ=_param_type, name=string("otherParam"), position=0)
        _arg_mismatched = newPNode(kind=TNodeKind.nkSym, sym=_mismatched_sym)
    checkForSink(_conf, _idgen, _owner, _arg_mismatched)
    assert _mismatched_sym.typ.kind != TTypeKind.tySink

    with let:
        _owner_no_typ = newPSym(kind=TSymKind.skProc)
    _owner_no_typ.typ = None
    with let:
        _param_no_owner_typ = newPSym(kind=TSymKind.skParam, owner=_owner_no_typ, typ=_param_type, name=string("pNoOwnerTyp"), position=0)
        _arg_no_owner_typ = newPNode(kind=TNodeKind.nkSym, sym=_param_no_owner_typ)
    checkForSink(_conf, _idgen, _owner_no_typ, _arg_no_owner_typ)
    assert _param_no_owner_typ.typ.kind != TTypeKind.tySink

    with let:
        _owner_not_proc = newPSym(kind=TSymKind.skProc)
    _owner_not_proc.typ = newPType(kind=TTypeKind.tyInt)
    with let:
        _param_not_proc = newPSym(kind=TSymKind.skParam, owner=_owner_not_proc, typ=_param_type, name=string("pNotProc"), position=0)
        _arg_not_proc = newPNode(kind=TNodeKind.nkSym, sym=_param_not_proc)
    checkForSink(_conf, _idgen, _owner_not_proc, _arg_not_proc)
    assert _param_not_proc.typ.kind != TTypeKind.tySink

    for excluded_kind in [TTypeKind.tyVar, TTypeKind.tySink, TTypeKind.tyOwned]:
        with let:
            _excl_type = newPType(kind=excluded_kind, size=8, align=8, hasDestructor=True)
            _param_excl = newPSym(kind=TSymKind.skParam, owner=_owner, typ=_excl_type, name=string("pExcl"), position=0)
        _proc_typ.n[1].sym = _param_excl
        with let:
            _arg_excl = newPNode(kind=TNodeKind.nkSym, sym=_param_excl)
        checkForSink(_conf, _idgen, _owner, _arg_excl)
        assert _param_excl.typ.kind == excluded_kind

    echo("All sinkparameter_inference tests passed successfully!")
