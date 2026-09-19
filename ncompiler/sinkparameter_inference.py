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
            if (arg.sym.kind == skParam) and \
               (arg.sym.owner == owner) and \
               (owner.typ != None) and (owner.typ.kind == tyProc) and \
               hasDestructor(arg.sym.typ) and \
               (arg.sym.typ.kind not in {tyVar, tySink, tyOwned}):
                # Watch out: cannot do this inference for procs with forward
                # declarations.
                if sfWasForwarded not in owner.flags:
                    with let:
                        argType = arg.sym.typ

                    with let:
                        sinkType = newType(tySink, idgen, owner)
                    sinkType.size = argType.size
                    sinkType.align = argType.align
                    sinkType.paddingAtEnd = argType.paddingAtEnd
                    sinkType.add(argType)

                    arg.sym.typ = sinkType
                    assert owner.typ.n[arg.sym.position + 1].sym == arg.sym

                    #message(config, arg.info, warnUser,
                    #  ("turned '$1' to a sink parameter") % [$arg])
                    #echo config $ arg.info, " turned into a sink parameter ", arg.sym.name.s
                elif sfWasForwarded not in arg.sym.flags:
                    # we only report every potential 'sink' parameter only once:
                    ensureMutable(arg.sym)
                    incl(arg.sym.flagsImpl, sfWasForwarded)
                    message(config, arg.info, hintPerformance,
                            string("could not turn '$1' to a sink parameter") % [arg.sym.name.s])
                #echo config $ arg.info, " candidate for a sink parameter here"
        case TNodeKind.nkStmtList | TNodeKind.nkStmtListExpr | TNodeKind.nkBlockStmt | TNodeKind.nkBlockExpr:
            if not isEmptyType(arg.typ):
                checkForSink(config, idgen, owner, arg.lastSon)
        case TNodeKind.nkIfStmt | TNodeKind.nkIfExpr | TNodeKind.nkWhen:
            for branch in arg:
                with let:
                    value = branch.lastSon
                if not isEmptyType(value.typ):
                    checkForSink(config, idgen, owner, value)
        case TNodeKind.nkCaseStmt:
            for i in range(1, len(arg)):
                with let:
                    value = arg[i].lastSon
                if not isEmptyType(value.typ):
                    checkForSink(config, idgen, owner, value)
        case TNodeKind.nkTryStmt:
            checkForSink(config, idgen, owner, arg[0])
        case _:
            _ = "nothing to do"

if comptime(__name__ == "__main__"):
    # Mock types for standalone testing
    class TTypeKind(NIntEnum):
        tyNone = auto()
        tyInt = auto()
        tyProc = auto()
        tyVar = auto()
        tySink = auto()
        tyOwned = auto()
        tyVoid = auto()
        tyTyped = auto()

    tyProc = TTypeKind.tyProc
    tyVar = TTypeKind.tyVar
    tySink = TTypeKind.tySink
    tyOwned = TTypeKind.tyOwned
    tyVoid = TTypeKind.tyVoid
    tyTyped = TTypeKind.tyTyped

    class TSymKind(NIntEnum):
        skUnknown = auto()
        skParam = auto()
        skVar = auto()
        skProc = auto()

    skParam = TSymKind.skParam

    class TSymFlag(NIntEnum):
        sfWasForwarded = auto()

    sfWasForwarded = TSymFlag.sfWasForwarded

    hintPerformance = 1

    class ConfigRef(Object):
        pass

    class IdGenerator(Object):
        pass

    class SymName(Object):
        def __init__(self, s: str):
            self.s = string(s)

    class PType(Object):
        def __init__(self, kind: TTypeKind, size: int = 8, align: int = 8, hasDestructor: bool = True):
            self.kind = kind
            self.size = size
            self.align = align
            self.paddingAtEnd = 0
            self.sons = []
            self.n = []
            self.flags = set()
            self._hasDestructor = hasDestructor

        @property
        def hasDestructor(self) -> bool:
            return self._hasDestructor

        def add(self, son: PType) -> None:
            self.sons.append(son)

    class PSym(Object):
        def __init__(self, kind: TSymKind, owner: PSym = None, typ: PType = None, name: str = "p", position: int = 0):
            self.kind = kind
            self.owner = owner
            self.typ = typ
            self.flagsImpl = set()
            self.flags = self.flagsImpl
            self.position = position
            self.name = SymName(name)

    class PNode(Object):
        def __init__(self, kind: TNodeKind, sym: PSym = None, typ: PType = None, sons: list = None):
            self.kind = kind
            self.sym = sym
            self.typ = typ
            self.sons = sons if sons is not None else []
            self.info = None

        @property
        def lastSon(self) -> PNode:
            return self.sons[-1] if self.sons else None

        def __getitem__(self, index: int) -> PNode:
            return self.sons[index]

        def __len__(self) -> int:
            return len(self.sons)

        def __iter__(self):
            return iter(self.sons)

    def hasDestructor(t: PType) -> bool:
        return t.hasDestructor if t is not None else False

    def isEmptyType(t: PType) -> bool:
        return t is None or t.kind in {tyVoid, tyTyped}

    def newType(kind: TTypeKind, idgen: IdGenerator, owner: PSym) -> PType:
        return PType(kind=kind, size=0, align=0)

    def ensureMutable(s: PSym) -> None:
        pass

    _messages = []
    def message(conf: ConfigRef, info: object, msgKind: int, msgText: string) -> None:
        _messages.append((msgKind, msgText))

    # Test 1: Successful inference of parameter to sink
    with let:
        _conf = ConfigRef()
        _idgen = IdGenerator()
        _owner = PSym(kind=TSymKind.skProc)
        _proc_typ = PType(kind=tyProc)
        _owner.typ = _proc_typ

        _param_type = PType(kind=TTypeKind.tyInt, size=8, align=8, hasDestructor=True)
        _param_sym = PSym(kind=skParam, owner=_owner, typ=_param_type, name="myParam", position=0)

        # owner.typ.n has [returnTypeNode, param1Node, ...]
        _proc_typ.n = [PNode(kind=TNodeKind.nkNone), PNode(kind=TNodeKind.nkSym, sym=_param_sym)]

        _arg_node = PNode(kind=TNodeKind.nkSym, sym=_param_sym)

    checkForSink(_conf, _idgen, _owner, _arg_node)

    assert _param_sym.typ.kind == tySink
    assert _param_sym.typ.size == 8
    assert _param_sym.typ.align == 8
    assert len(_param_sym.typ.sons) == 1
    assert _param_sym.typ.sons[0] == _param_type

    # Test 2: Proc with forward declaration -> warning emitted, not converted
    with let:
        _owner_fwd = PSym(kind=TSymKind.skProc)
        _owner_fwd.flags.add(sfWasForwarded)
        _owner_fwd.typ = _proc_typ

        _param_sym_fwd = PSym(kind=skParam, owner=_owner_fwd, typ=_param_type, name="forwardedParam", position=0)
        _proc_typ.n[1].sym = _param_sym_fwd
        _arg_node_fwd = PNode(kind=TNodeKind.nkSym, sym=_param_sym_fwd)

    _messages.clear()
    checkForSink(_conf, _idgen, _owner_fwd, _arg_node_fwd)

    assert _param_sym_fwd.typ.kind != tySink
    assert sfWasForwarded in _param_sym_fwd.flagsImpl
    assert len(_messages) == 1
    assert "could not turn 'forwardedParam' to a sink parameter" in str(_messages[0][1])

    # Test 3: Nested expressions (nkStmtList)
    with let:
        _param_sym3 = PSym(kind=skParam, owner=_owner, typ=_param_type, name="p3", position=0)
        _proc_typ.n[1].sym = _param_sym3
        _leaf = PNode(kind=TNodeKind.nkSym, sym=_param_sym3)
        _stmt_list = PNode(kind=TNodeKind.nkStmtList, typ=_param_type, sons=[_leaf])

    checkForSink(_conf, _idgen, _owner, _stmt_list)
    assert _param_sym3.typ.kind == tySink

    # Test 4: If statement branches
    with let:
        _param_sym4 = PSym(kind=skParam, owner=_owner, typ=_param_type, name="p4", position=0)
        _proc_typ.n[1].sym = _param_sym4
        _leaf4 = PNode(kind=TNodeKind.nkSym, sym=_param_sym4, typ=_param_type)
        _branch1 = PNode(kind=TNodeKind.nkElifBranch, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _leaf4])
        _if_stmt = PNode(kind=TNodeKind.nkIfStmt, typ=_param_type, sons=[_branch1])

    checkForSink(_conf, _idgen, _owner, _if_stmt)
    assert _param_sym4.typ.kind == tySink

    # Test 5: Case statement branches
    with let:
        _param_sym5 = PSym(kind=skParam, owner=_owner, typ=_param_type, name="p5", position=0)
        _proc_typ.n[1].sym = _param_sym5
        _leaf5 = PNode(kind=TNodeKind.nkSym, sym=_param_sym5, typ=_param_type)
        _case_branch = PNode(kind=TNodeKind.nkOfBranch, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _leaf5])
        _case_stmt = PNode(kind=TNodeKind.nkCaseStmt, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _case_branch])

    checkForSink(_conf, _idgen, _owner, _case_stmt)
    assert _param_sym5.typ.kind == tySink

    # Test 6: Try statement
    with let:
        _param_sym6 = PSym(kind=skParam, owner=_owner, typ=_param_type, name="p6", position=0)
        _proc_typ.n[1].sym = _param_sym6
        _leaf6 = PNode(kind=TNodeKind.nkSym, sym=_param_sym6)
        _try_stmt = PNode(kind=TNodeKind.nkTryStmt, typ=_param_type, sons=[_leaf6])

    checkForSink(_conf, _idgen, _owner, _try_stmt)
    assert _param_sym6.typ.kind == tySink

    # Test 7: Non-sink parameter (no destructor)
    with let:
        _no_destruct_type = PType(kind=TTypeKind.tyInt, size=8, align=8, hasDestructor=False)
        _param_no_destruct = PSym(kind=skParam, owner=_owner, typ=_no_destruct_type, name="pNoDestruct", position=0)
        _proc_typ.n[1].sym = _param_no_destruct
        _arg_no_destruct = PNode(kind=TNodeKind.nkSym, sym=_param_no_destruct)

    checkForSink(_conf, _idgen, _owner, _arg_no_destruct)
    assert _param_no_destruct.typ.kind != tySink

    # Test 8: Non-candidate node kind (e.g. nkIntLit)
    with let:
        _int_node = PNode(kind=TNodeKind.nkIntLit)
    checkForSink(_conf, _idgen, _owner, _int_node)

    # Test 9: Forwarded proc warning deduplication (only report once)
    checkForSink(_conf, _idgen, _owner_fwd, _arg_node_fwd)
    assert len(_messages) == 1  # No second message emitted

    # Test 10: Parameter that already has sfWasForwarded flag initially
    with let:
        _param_already_fwd = PSym(kind=skParam, owner=_owner_fwd, typ=_param_type, name="pAlreadyFwd", position=0)
        _param_already_fwd.flagsImpl.add(sfWasForwarded)
        _proc_typ.n[1].sym = _param_already_fwd
        _arg_already_fwd = PNode(kind=TNodeKind.nkSym, sym=_param_already_fwd)

    _messages.clear()
    checkForSink(_conf, _idgen, _owner_fwd, _arg_already_fwd)
    assert len(_messages) == 0  # No message emitted

    # Test 11: Statement lists and blocks (nkStmtListExpr, nkBlockStmt, nkBlockExpr, isEmptyType guard)
    with let:
        _param_stmt_void = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pStmtVoid", position=0)
        _proc_typ.n[1].sym = _param_stmt_void
        _leaf_stmt_void = PNode(kind=TNodeKind.nkSym, sym=_param_stmt_void)
        _stmt_void = PNode(kind=TNodeKind.nkStmtList, typ=PType(kind=tyVoid), sons=[_leaf_stmt_void])

    checkForSink(_conf, _idgen, _owner, _stmt_void)
    assert _param_stmt_void.typ.kind != tySink

    # nkStmtListExpr
    with let:
        _param_stmt_expr = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pStmtExpr", position=0)
        _proc_typ.n[1].sym = _param_stmt_expr
        _leaf_stmt_expr = PNode(kind=TNodeKind.nkSym, sym=_param_stmt_expr)
        _stmt_expr = PNode(kind=TNodeKind.nkStmtListExpr, typ=_param_type, sons=[_leaf_stmt_expr])

    checkForSink(_conf, _idgen, _owner, _stmt_expr)
    assert _param_stmt_expr.typ.kind == tySink

    # nkBlockStmt
    with let:
        _param_block_stmt = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pBlockStmt", position=0)
        _proc_typ.n[1].sym = _param_block_stmt
        _leaf_block_stmt = PNode(kind=TNodeKind.nkSym, sym=_param_block_stmt)
        _block_stmt = PNode(kind=TNodeKind.nkBlockStmt, typ=_param_type, sons=[_leaf_block_stmt])

    checkForSink(_conf, _idgen, _owner, _block_stmt)
    assert _param_block_stmt.typ.kind == tySink

    # nkBlockExpr
    with let:
        _param_block_expr = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pBlockExpr", position=0)
        _proc_typ.n[1].sym = _param_block_expr
        _leaf_block_expr = PNode(kind=TNodeKind.nkSym, sym=_param_block_expr)
        _block_expr = PNode(kind=TNodeKind.nkBlockExpr, typ=_param_type, sons=[_leaf_block_expr])

    checkForSink(_conf, _idgen, _owner, _block_expr)
    assert _param_block_expr.typ.kind == tySink

    # Test 12: If expressions, When statements, and isEmptyType on branch
    # nkIfExpr
    with let:
        _param_if_expr = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pIfExpr", position=0)
        _proc_typ.n[1].sym = _param_if_expr
        _leaf_if_expr = PNode(kind=TNodeKind.nkSym, sym=_param_if_expr, typ=_param_type)
        _branch_if_expr = PNode(kind=TNodeKind.nkElifExpr, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _leaf_if_expr])
        _if_expr = PNode(kind=TNodeKind.nkIfExpr, typ=_param_type, sons=[_branch_if_expr])

    checkForSink(_conf, _idgen, _owner, _if_expr)
    assert _param_if_expr.typ.kind == tySink

    # nkWhen
    with let:
        _param_when = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pWhen", position=0)
        _proc_typ.n[1].sym = _param_when
        _leaf_when = PNode(kind=TNodeKind.nkSym, sym=_param_when, typ=_param_type)
        _branch_when = PNode(kind=TNodeKind.nkElifBranch, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _leaf_when])
        _when_stmt = PNode(kind=TNodeKind.nkWhen, typ=_param_type, sons=[_branch_when])

    checkForSink(_conf, _idgen, _owner, _when_stmt)
    assert _param_when.typ.kind == tySink

    # Branch with empty type (should not convert)
    with let:
        _param_branch_void = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pBranchVoid", position=0)
        _proc_typ.n[1].sym = _param_branch_void
        _leaf_branch_void = PNode(kind=TNodeKind.nkSym, sym=_param_branch_void, typ=PType(kind=tyVoid))
        _branch_void = PNode(kind=TNodeKind.nkElifBranch, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _leaf_branch_void])
        _if_void_stmt = PNode(kind=TNodeKind.nkIfStmt, typ=_param_type, sons=[_branch_void])

    checkForSink(_conf, _idgen, _owner, _if_void_stmt)
    assert _param_branch_void.typ.kind != tySink

    # Test 13: Case statement boundary conditions
    # nkCaseStmt with only selector (len == 1)
    with let:
        _case_empty = PNode(kind=TNodeKind.nkCaseStmt, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent)])
    checkForSink(_conf, _idgen, _owner, _case_empty)

    # nkCaseStmt branch with empty type (should not convert)
    with let:
        _param_case_void = PSym(kind=skParam, owner=_owner, typ=_param_type, name="pCaseVoid", position=0)
        _proc_typ.n[1].sym = _param_case_void
        _leaf_case_void = PNode(kind=TNodeKind.nkSym, sym=_param_case_void, typ=PType(kind=tyVoid))
        _case_branch_void = PNode(kind=TNodeKind.nkOfBranch, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _leaf_case_void])
        _case_void_stmt = PNode(kind=TNodeKind.nkCaseStmt, typ=_param_type, sons=[PNode(kind=TNodeKind.nkIdent), _case_branch_void])

    checkForSink(_conf, _idgen, _owner, _case_void_stmt)
    assert _param_case_void.typ.kind != tySink

    # Test 14: Disqualification checks on candidate symbol
    # 14a: Not skParam (e.g. skVar)
    with let:
        _var_sym = PSym(kind=TSymKind.skVar, owner=_owner, typ=_param_type, name="myVar", position=0)
        _arg_var = PNode(kind=TNodeKind.nkSym, sym=_var_sym)
    checkForSink(_conf, _idgen, _owner, _arg_var)
    assert _var_sym.typ.kind != tySink

    # 14b: Mismatched owner
    with let:
        _other_owner = PSym(kind=TSymKind.skProc)
        _other_owner.typ = _proc_typ
        _mismatched_sym = PSym(kind=skParam, owner=_other_owner, typ=_param_type, name="otherParam", position=0)
        _arg_mismatched = PNode(kind=TNodeKind.nkSym, sym=_mismatched_sym)
    checkForSink(_conf, _idgen, _owner, _arg_mismatched)
    assert _mismatched_sym.typ.kind != tySink

    # 14c: Owner typ is None
    with let:
        _owner_no_typ = PSym(kind=TSymKind.skProc)
        _owner_no_typ.typ = None
        _param_no_owner_typ = PSym(kind=skParam, owner=_owner_no_typ, typ=_param_type, name="pNoOwnerTyp", position=0)
        _arg_no_owner_typ = PNode(kind=TNodeKind.nkSym, sym=_param_no_owner_typ)
    checkForSink(_conf, _idgen, _owner_no_typ, _arg_no_owner_typ)
    assert _param_no_owner_typ.typ.kind != tySink

    # 14d: Owner typ is not tyProc
    with let:
        _owner_not_proc = PSym(kind=TSymKind.skProc)
        _owner_not_proc.typ = PType(kind=TTypeKind.tyInt)
        _param_not_proc = PSym(kind=skParam, owner=_owner_not_proc, typ=_param_type, name="pNotProc", position=0)
        _arg_not_proc = PNode(kind=TNodeKind.nkSym, sym=_param_not_proc)
    checkForSink(_conf, _idgen, _owner_not_proc, _arg_not_proc)
    assert _param_not_proc.typ.kind != tySink

    # 14e: Param type already tyVar, tySink, or tyOwned
    for excluded_kind in (tyVar, tySink, tyOwned):
        with let:
            _excl_type = PType(kind=excluded_kind, size=8, align=8, hasDestructor=True)
            _param_excl = PSym(kind=skParam, owner=_owner, typ=_excl_type, name="pExcl", position=0)
            _proc_typ.n[1].sym = _param_excl
            _arg_excl = PNode(kind=TNodeKind.nkSym, sym=_param_excl)
        checkForSink(_conf, _idgen, _owner, _arg_excl)
        assert _param_excl.typ.kind == excluded_kind

    echo("All sinkparameter_inference tests passed successfully!")
