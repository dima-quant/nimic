# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/llvmgenstmts.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

# included from llvmcodegen.nim
# Generates LLVM IR for statements.

from __future__ import annotations
from nimic.ntypes import *

with const:
    _RangeExpandThreshold = 32  # values <= this with literal lo/hi expand per-value; otherwise range-check


class _CaseBranch(Object):
    ## Used by genSwitchLLVM. Declared at module scope rather than inside
    ## the proc's `n.into:` block so the type isn't re-instantiated each
    ## time the template expands.
    _values: seq[LLValue]
    _label: string


def _getVirtualGuardLLVM(c: mut @ LLVMCode, n: Cursor) -> tuple[SymId, bool]:
    result = (SymId(0), False)
    with var:
        n = n.copy()
    if exprKind(n) == LengExpr.NotC:
        n.inc()
        with var:
            isLast = False
        if stmtKind(n) == LengStmt.LabS:
            isLast = True
            n.inc()
        elif kind(n) == NifKind.Symbol:
            if c._currentProc.vflags.contains(symId(n)):
                result = (symId(n), isLast)
    return result


def _genOnErrorLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        onErrInfo = _info(n)
        errPtr = llGlobalRef(string("LENGC_ERR_"), c.prim.ptrT)
        i8_ = c.prim.i8_
        errVal = emitLoad(c, errPtr, i8_)
        cond = c.nextTemp()
        condRes = llReg(cond, c.prim.i1)
    setLoc(c, onErrInfo)
    emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=condRes, icmpPred=string("ne"), icmpLhs=errVal, icmpRhs=llIntTextC(string("0"), c.prim.i8_)))
    with let:
        thenLabel = c.nextLabel()
        endLabel = c.nextLabel()
    emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=condRes, condBrTrue=thenLabel, condBrFalse=endLabel))
    _ = c.startBlock(thenLabel)
    _genStmtLLVM(c, n)
    if not c._currentProc.needsTerminator:
        setLoc(c, onErrInfo)
        emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
    _ = c.startBlock(endLabel)


def _genIfLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        ifInfo = _info(n)
    with var:
        endLabel = c.nextLabel()
        needsEnd = False
    for _ in loopInto(n):
        with let:
            branchInfo = _info(n)
        match substructureKind(n):
            case LengOther.ElifU:
                with into(n):
                    with var:
                        cond = default(LLValue)
                    _genCondLLVM(c, n, cond)
                    with let:
                        thenLabel = c.nextLabel()
                        elseLabel = c.nextLabel()
                    setLoc(c, branchInfo)
                    emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=cond, condBrTrue=thenLabel, condBrFalse=elseLabel))
                    _ = c.startBlock(thenLabel)
                    _genStmtLLVM(c, n)
                    if not c._currentProc.needsTerminator:
                        setLoc(c, branchInfo)
                        emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
                    _ = c.startBlock(elseLabel)
                    needsEnd = True
                    while n.hasMore(): skip(n)
            case LengOther.ElseU:
                with into(n):
                    _genStmtLLVM(c, n)
                    if not c._currentProc.needsTerminator:
                        setLoc(c, branchInfo)
                        emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
                    needsEnd = True
                    while n.hasMore(): skip(n)
            case _:
                _error(c._m, string("`if` expects `elif` or `else` but got: "), n)

    if needsEnd:
        if not c._currentProc.needsTerminator:
            setLoc(c, ifInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
        _ = c.startBlock(endLabel)


def _genIteLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        iteInfo = _info(n)
    with into(n):

        with let:
            (vflag, isLast) = _getVirtualGuardLLVM(c, n)
        if vflag != SymId(0):
            skip(n)
            _genStmtLLVM(c, n)
            if isLast:
                with let:
                    labelName = mangleToC(c._m.pool.symString(vflag))
                setLoc(c, iteInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=labelName))
                _ = c.startBlock(labelName)
            skip(n)
        else:
            with var:
                cond = default(LLValue)
            _genCondLLVM(c, n, cond)
            with let:
                thenLabel = c.nextLabel()
                elseLabel = c.nextLabel()
                endLabel = c.nextLabel()

            if kind(n) != NifKind.DotToken:
                setLoc(c, iteInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=cond, condBrTrue=thenLabel, condBrFalse=elseLabel))
            else:
                setLoc(c, iteInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=cond, condBrTrue=thenLabel, condBrFalse=endLabel))

            _ = c.startBlock(thenLabel)
            _genStmtLLVM(c, n)

            if not c._currentProc.needsTerminator:
                setLoc(c, iteInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))

            if kind(n) != NifKind.DotToken:
                _ = c.startBlock(elseLabel)
                _genStmtLLVM(c, n)
                if not c._currentProc.needsTerminator:
                    setLoc(c, iteInfo)
                    emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
            else:
                n.inc()

            _ = c.startBlock(endLabel)
        while n.hasMore(): skip(n)


def _genWhileLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        whileInfo = _info(n)
    with into(n):
        with let:
            condLabel = c.nextLabel()
            bodyLabel = c.nextLabel()
            endLabel = c.nextLabel()

        setLoc(c, whileInfo)
        emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=condLabel))
        _ = c.startBlock(condLabel)

        with var:
            cond = default(LLValue)
        _genCondLLVM(c, n, cond)
        setLoc(c, whileInfo)
        emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=cond, condBrTrue=bodyLabel, condBrFalse=endLabel))

        _ = c.startBlock(bodyLabel)
        c._currentProc.breakStack.add(endLabel)
        _genStmtLLVM(c, n)
        _ = c._currentProc.breakStack.pop()

        if not c._currentProc.needsTerminator:
            setLoc(c, whileInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=condLabel))

        _ = c.startBlock(endLabel)
        while n.hasMore(): skip(n)


def _genLoopLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    ## `(loop body)`: infinite, left only by a `break`/`jmp` inside the body.
    with let:
        loopInfo = _info(n)
    with into(n):
        with let:
            headerLabel = c.nextLabel()
            endLabel = c.nextLabel()

        setLoc(c, loopInfo)
        emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=headerLabel))
        _ = c.startBlock(headerLabel)

        c._currentProc.breakStack.add(endLabel)
        _genStmtLLVM(c, n)
        _ = c._currentProc.breakStack.pop()

        if not c._currentProc.needsTerminator:
            setLoc(c, loopInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=headerLabel))

        _ = c.startBlock(endLabel)
        while n.hasMore(): skip(n)


def _emitRangeCheck(c: mut @ LLVMCode, info: NifLineInfo, switchVal: LLValue, lo: LLValue, hi: LLValue, switchTK: LengType, branchLabel: string):
    ## Lowers a range to a `switchVal in [lo,hi]` condbr (LLVM switch has no range case);
    ## opens a fresh block for the next range-check or the switch.
    with let:
        predLo = string("uge") if switchTK in Tset[LengType](LengType.UT, LengType.CT, LengType.BoolT) else string("sge")
        predHi = string("ule") if switchTK in Tset[LengType](LengType.UT, LengType.CT, LengType.BoolT) else string("sle")
    setLoc(c, info)
    with let:
        loOk = llReg(c.nextTemp(), c.prim.i1)
    emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=loOk, icmpPred=predLo, icmpLhs=switchVal, icmpRhs=lo))
    with let:
        hiOk = llReg(c.nextTemp(), c.prim.i1)
    emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=hiOk, icmpPred=predHi, icmpLhs=switchVal, icmpRhs=hi))
    with let:
        inRange = llReg(c.nextTemp(), c.prim.i1)
    emit_(c, LLInstr(kind=LLInstrKind.llBinOp, result=inRange, binOp=string("and"), binLhs=loOk, binRhs=hiOk))
    with let:
        nextChk = c.nextLabel()
    emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=inRange, condBrTrue=branchLabel, condBrFalse=nextChk))
    _ = c.startBlock(nextChk)


def _genSwitchLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with into(n):
        with let:
            switchExpr = n
            switchSrcType = getType(c._m, switchExpr)
            switchTK = _scalarTypeKind(c, switchSrcType)
        with var:
            switchVal = default(LLValue)
        _genExprLLVM(c, n, switchVal)
        with let:
            endLabel = c.nextLabel()
        with var:
            defaultLabel = endLabel

        with var:
            branches: seq[_CaseBranch] = seq[_CaseBranch]([])
            defaultBranch = string("")
            savedPos = n.copy()

        while n.hasMore():
            match substructureKind(n):
                case LengOther.OfU:
                    with into(n):
                        with var:
                            branch = _CaseBranch(_label=c.nextLabel())
                        if substructureKind(n) == LengOther.RangesU:
                            with into(n):
                                while n.hasMore():
                                    if substructureKind(n) == LengOther.RangeU:
                                        with into(n):
                                            with let:
                                                rangeInfo = _info(n)
                                            with var:
                                                lo = default(LLValue)
                                            _genExprLLVM(c, n, lo)
                                            with var:
                                                hi = default(LLValue)
                                            _genExprLLVM(c, n, hi)
                                            if lo.kind == LLValueKind.llvInt and hi.kind == LLValueKind.llvInt:
                                                with let:
                                                    loN = _parseIntOrQuit(lo.intText)
                                                    hiN = _parseIntOrQuit(hi.intText)
                                                    span = hiN - loN + 1
                                                if span >= 0 and span <= _RangeExpandThreshold:
                                                    # small dense literal range: expand per value to keep switch jump-table
                                                    with var:
                                                        v = copy(loN)
                                                    while v <= hiN:
                                                        branch._values.add(llIntTextC(str(v), switchVal.typ))
                                                        v += 1
                                                else:
                                                    # large range: short-circuit via range-check
                                                    _emitRangeCheck(c, rangeInfo, switchVal, llIntTextC(lo.intText, switchVal.typ), llIntTextC(hi.intText, switchVal.typ), switchTK, branch._label)
                                            else:
                                                # non-literal range: must range-check (old code dropped hi)
                                                _emitRangeCheck(c, rangeInfo, switchVal, lo, hi, switchTK, branch._label)
                                            while n.hasMore(): skip(n)
                                    else:
                                        with var:
                                            val = default(LLValue)
                                        _genExprLLVM(c, n, val)
                                        branch._values.add(val)
                                while n.hasMore(): skip(n)
                        branches.add(branch)
                        skip(n)
                        while n.hasMore(): skip(n)
                case LengOther.ElseU:
                    with into(n):
                        defaultLabel = c.nextLabel()
                        defaultBranch = defaultLabel
                        skip(n)
                        while n.hasMore(): skip(n)
                case _:
                    _error(c._m, string("`case` expects `of` or `else` but got: "), n)

        # branch.values holds only per-value entries (single values + expanded
        # small ranges); range-checked ranges short-circuit above, not here.
        with var:
            cases: seq[tuple[LLValue, string]] = seq[tuple[LLValue, string]]([])
        for branch in branches:
            for v in branch._values:
                cases.add((v, branch._label))
        emit_(c, LLInstr(kind=LLInstrKind.llSwitch, switchValType=switchVal.typ, switchVal=switchVal, switchDefault=defaultLabel, switchCases=cases))

        n <<= savedPos
        with var:
            branchIdx = nint(0)
        c._currentProc.breakStack.add(endLabel)
        while n.hasMore():
            with let:
                branchInfo = _info(n)
            match substructureKind(n):
                case LengOther.OfU:
                    with into(n):
                        skip(n)
                        _ = c.startBlock(branches[branchIdx]._label)
                        _genStmtLLVM(c, n)
                        if not c._currentProc.needsTerminator:
                            setLoc(c, branchInfo)
                            emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
                        while n.hasMore(): skip(n)
                    branchIdx += 1
                case LengOther.ElseU:
                    with into(n):
                        _ = c.startBlock(defaultBranch)
                        _genStmtLLVM(c, n)
                        if not c._currentProc.needsTerminator:
                            setLoc(c, branchInfo)
                            emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
                        while n.hasMore(): skip(n)
                case _:
                    _error(c._m, string("`case` expects `of` or `else` but got: "), n)
        _ = c._currentProc.breakStack.pop()

        _ = c.startBlock(endLabel)


def _genLabelLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        labelInfo = _info(n)
    with into(n):
        if kind(n) == NifKind.SymbolDef:
            with let:
                name = mangleToC(c._m.pool.symString(symId(n)))
            if not c._currentProc.needsTerminator:
                setLoc(c, labelInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=name))
            _ = c.startBlock(name)
            n.inc()
        else:
            _error(c._m, string("expected SymbolDef but got: "), n)
        while n.hasMore(): skip(n)


def _genGotoLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        gotoInfo = _info(n)
    with into(n):
        if kind(n) == NifKind.Symbol:
            with let:
                name = mangleToC(c._m.pool.symString(symId(n)))
            setLoc(c, gotoInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=name))
            c._currentProc.needsTerminator = True
            n.inc()
        else:
            _error(c._m, string("expected Symbol but got: "), n)
        while n.hasMore(): skip(n)


def _genScopeLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with into(n):
        c._m.openScope()
        while n.hasMore():
            _genStmtLLVM(c, n)
            if c._currentProc.needsTerminator:
                while n.hasMore() and stmtKind(n) != LengStmt.LabS: skip(n)
        c._m.closeScope()


def _genMflagDeclLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with into(n):
        if kind(n) == NifKind.SymbolDef:
            with let:
                s = symId(n)
            c._m.registerLocal(s, createIntegralType(c._m, string("(bool)")))
            with let:
                name = mangleToC(c._m.pool.symString(s))
                i8_ = c.prim.i8_
            c.emitAlloca(name, i8_)
            emitStore(c, llIntTextC(string("0"), c.prim.i8_), llReg(name, c.prim.ptrT))
            n.inc()
        else:
            _error(c._m, string("expected SymbolDef but got: "), n)
        while n.hasMore(): skip(n)


def _genVflagDeclLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with into(n):
        if kind(n) == NifKind.SymbolDef:
            with let:
                s = symId(n)
            c._m.registerLocal(s, createIntegralType(c._m, string("(bool)")))
            c._currentProc.vflags.incl(s)
            n.inc()
        else:
            _error(c._m, string("expected SymbolDef but got: "), n)
        while n.hasMore(): skip(n)


def _genJtrueLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        jtrueInfo = _info(n)
    for _ in loopInto(n):
        if kind(n) == NifKind.Symbol:
            with let:
                s = symId(n)
            if not c._currentProc.vflags.contains(s):
                _error(c._m, string("virtual flag not declared: "), n)
            n.inc()
            if not n.hasMore():
                with let:
                    name = mangleToC(c._m.pool.symString(s))
                setLoc(c, jtrueInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=name))
                c._currentProc.needsTerminator = True
        else:
            _error(c._m, string("expected Symbol but got: "), n)


def _genKeepOverflowLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        ovfInfo = _info(n)
    with var:
        typ: LLType = None
        intrinsic = string("")
        bitsStr = str(c._bits)
        lhs = default(LLValue)
        rhs = default(LLValue)
        target = default(LLValue)
    for _ in into(n):
        with let:
            op = exprKind(n)

        intrinsic = string("llvm.")
        match op:
            case LengExpr.AddC: intrinsic.add(string("sadd"))
            case LengExpr.SubC: intrinsic.add(string("ssub"))
            case LengExpr.MulC: intrinsic.add(string("smul"))
            case _:
                # A rewrite left a value that cannot overflow (see the C backend's
                # `genKeepOverflow`): store it and clear the flag.
                with var:
                    value = default(LLValue)
                _genExprLLVM(c, n, value)
                _genLvalueLLVM(c, n, target)
                while n.hasMore(): skip(n)
                emitStore(c, value, target)
                emitStore(c, llIntTextC(string("0"), c.prim.i8_), llGlobalRef(string("LENGC_OVF_"), c.prim.ptrT))
                return

        with into(n):
            with let:
                isUnsigned = typeKind(n) == LengType.UT
            if isUnsigned:
                intrinsic = intrinsic.replace(string("sadd"), string("uadd")).replace(string("ssub"), string("usub")).replace(string("smul"), string("umul"))

            with into(n):
                if kind(n) == NifKind.IntLit:
                    with let:
                        bits = intVal(n)
                    if bits != -1:
                        bitsStr = str(bits)
                    n.inc()
                while n.hasMore(): skip(n)

            typ = c.llIntBits(_parseIntOrQuit(bitsStr))
            intrinsic.add(string(".with.overflow."))
            serialize(typ, intrinsic)

            _genExprLLVM(c, n, lhs)
            _genExprLLVM(c, n, rhs)
            while n.hasMore(): skip(n)

        _genLvalueLLVM(c, n, target)
        while n.hasMore(): skip(n)

    with let:
        aggTyp = LLType(kind=LLTypeKind.llStruct, structFields=seq[LLStructField]([LLStructField(typ=typ), LLStructField(typ=c.prim.i1)]))
        rs = c.nextTemp()
        rsRes = llReg(rs, aggTyp)
    emit_(c, LLInstr(kind=LLInstrKind.llCall, result=rsRes, callCallee=llGlobalRef(intrinsic, c.prim.ptrT), callRetType=aggTyp, callArgs=seq[LLValue]([lhs, rhs])))
    with let:
        resultVal = c.nextTemp()
        rvRes = llReg(resultVal, typ)
    emit_(c, LLInstr(kind=LLInstrKind.llExtractValue, result=rvRes, evAggregate=rsRes, evAggType=aggTyp, evIndex=0))
    emitStore(c, rvRes, target)
    with let:
        ovfFlag = c.nextTemp()
        ovfRes = llReg(ovfFlag, c.prim.i1)
    emit_(c, LLInstr(kind=LLInstrKind.llExtractValue, result=ovfRes, evAggregate=rsRes, evAggType=aggTyp, evIndex=1))
    # Not sticky: the flag is this operation's verdict alone.
    with let:
        newOvfByte = c.nextTemp()
        nobRes = llReg(newOvfByte, c.prim.i8_)
    setLoc(c, ovfInfo)
    emit_(c, LLInstr(kind=LLInstrKind.llZext, result=nobRes, castOp=string("zext"), castSrc=ovfRes, castDstType=c.prim.i8_))
    emitStore(c, nobRes, llGlobalRef(string("LENGC_OVF_"), c.prim.ptrT))

    _declareExtern(c, LLExternDecl(name=intrinsic, retType=aggTyp, params=seq[LLType]([typ, typ])))


def _genEmitStmtLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with into(n):
        with var:
            comment = string("; emit: ")
        while n.hasMore():
            if kind(n) == NifKind.StrLit:
                comment.add(c._m.pool.strings[_litId(n)])
                n.inc()
            else:
                skip(n)
        c.emitRaw(comment)


def _genStmtLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    # A statement whose head carries a forged filename opens a template
    # expansion; everything lowered from inside it belongs to that frame, so the
    # push spans the whole subtree rather than a single `setLoc` (#1987).
    with c._withExpansionFrames(_info(n)):
        _genStmtBodyLLVM(c, n)


def _genStmtBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    match stmtKind(n):
        case LengStmt.NoStmt:
            if kind(n) == NifKind.DotToken:
                n.inc()
            else:
                _error(c._m, string("expected statement but got: "), n)
        case LengStmt.StmtsS | LengStmt.AlwaysS:
            for _ in loopInto(n):
                _genStmtLLVM(c, n)
                if c._currentProc.needsTerminator:
                    while n.hasMore() and stmtKind(n) != LengStmt.LabS: skip(n)
        case LengStmt.ScopeS:
            _genScopeLLVM(c, n)
        case LengStmt.InstrS:
            with var:
                instrResult = default(LLValue)
            _genInstrLLVM(c, n, instrResult)
        case LengStmt.CallS:
            with var:
                saved = n.copy()
            saved.inc()
            with let:
                calleeType = getType(c._m, saved)
            with var:
                retType = c.prim.voidT
            if typeKind(calleeType) == LengType.ProctypeT or symKind(calleeType) == LengSym.ProcY:
                with var:
                    ct = calleeType.copy()
                if typeKind(ct) == LengType.ProctypeT or symKind(ct) == LengSym.ProcY:
                    ct.inc()
                    skip(ct)
                if typeKind(ct) == LengType.ParamsT:
                    with var:
                        params = ct.copy()
                    skip(params)
                    retType = _genTypeLLVMReadOnly(c, params)
            with var:
                callResult = default(LLValue)
            _genCallWithType(c, n, retType, callResult)
        case LengStmt.VarS:
            _genLocalVarDeclLLVM(c, n)
        case LengStmt.GvarS:
            _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsGlobal)
        case LengStmt.TvarS:
            _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsThreadlocal)
        case LengStmt.ConstS:
            _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsConst)
        case LengStmt.MflagS:
            _genMflagDeclLLVM(c, n)
        case LengStmt.VflagS:
            _genVflagDeclLLVM(c, n)
        case LengStmt.EmitS:
            _genEmitStmtLLVM(c, n)
        case LengStmt.AsgnS:
            with let:
                asgnInfo = _info(n)
            with into(n):
                with let:
                    slotType = getType(c._m, n)
                with var:
                    lval = default(LLValue)
                _genLvalueLLVM(c, n, lval)
                with let:
                    srcType = getType(c._m, n)
                with var:
                    rval = default(LLValue)
                _genExprLLVM(c, n, rval)
                _coerceInPlace(c, rval, srcType, slotType)
                setLoc(c, asgnInfo)
                emitStore(c, rval, lval)
                while n.hasMore(): skip(n)
        case LengStmt.IfS:
            _genIfLLVM(c, n)
        case LengStmt.IteS | LengStmt.ItecS:
            _genIteLLVM(c, n)
        case LengStmt.WhileS:
            _genWhileLLVM(c, n)
        case LengStmt.LoopS:
            _genLoopLLVM(c, n)
        case LengStmt.BreakS:
            with let:
                breakInfo = _info(n)
            with into(n):
                if c._currentProc.breakStack.len > 0:
                    with let:
                        target = c._currentProc.breakStack[back(1)].copy()
                    setLoc(c, breakInfo)
                    emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=target))
                else:
                    emit_(c, LLInstr(kind=LLInstrKind.llUnreachable))
                c._currentProc.needsTerminator = True
                while n.hasMore(): skip(n)
        case LengStmt.JtrueS:
            _genJtrueLLVM(c, n)
        case LengStmt.CaseS:
            _genSwitchLLVM(c, n)
        case LengStmt.LabS:
            _genLabelLLVM(c, n)
        case LengStmt.JmpS:
            _genGotoLLVM(c, n)
        case LengStmt.RetS:
            with let:
                retInfo = _info(n)
            with into(n):
                if kind(n) != NifKind.DotToken:
                    with let:
                        valueExpr = n
                        valueType = getType(c._m, valueExpr)
                    with var:
                        val = default(LLValue)
                    _genExprLLVM(c, n, val)
                    with var:
                        coerced = default(LLValue)
                    with let:
                        retType = c._currentProc.retTypeCursor.copy()
                    _coerceValueLLVM(c, val, valueType, retType, coerced)
                    setLoc(c, retInfo)
                    emit_(c, LLInstr(kind=LLInstrKind.llRet, retVal=coerced))
                else:
                    n.inc()
                    setLoc(c, retInfo)
                    emit_(c, LLInstr(kind=LLInstrKind.llRet, retVal=llNoneVal()))
                c._currentProc.needsTerminator = True
                while n.hasMore(): skip(n)
        case LengStmt.DiscardS:
            with into(n):
                with var:
                    discardVal = default(LLValue)
                _genExprLLVM(c, n, discardVal)
                while n.hasMore(): skip(n)
        case LengStmt.TryS:
            with into(n):
                _genStmtLLVM(c, n)
                if kind(n) != NifKind.DotToken: skip(n)
                else: n.inc()
                if kind(n) != NifKind.DotToken: skip(n)
                else: n.inc()
                while n.hasMore(): skip(n)
        case LengStmt.RaiseS:
            with into(n):
                if kind(n) != NifKind.DotToken:
                    with var:
                        raiseVal = default(LLValue)
                    _genExprLLVM(c, n, raiseVal)
                else:
                    n.inc()
                emit_(c, LLInstr(kind=LLInstrKind.llCall, callCallee=llGlobalRef(string("llvm.trap"), c.prim.ptrT), callRetType=c.prim.voidT, callArgs=seq()))
                emit_(c, LLInstr(kind=LLInstrKind.llUnreachable))
                c._currentProc.needsTerminator = True
                _declareExtern(c, LLExternDecl(name=string("llvm.trap"), raw=string("declare void @llvm.trap() noreturn nounwind")))
                while n.hasMore(): skip(n)
        case LengStmt.OnerrS:
            with var:
                onErrAction = n.copy()
            onErrAction.inc()
            with var:
                saved = n.copy()
            saved.inc()
            with let:
                calleeType = getType(c._m, saved)
            with var:
                retType = c.prim.voidT
            if typeKind(calleeType) == LengType.ProctypeT or symKind(calleeType) == LengSym.ProcY:
                with var:
                    ct = calleeType.copy()
                if typeKind(ct) == LengType.ProctypeT or symKind(ct) == LengSym.ProcY:
                    ct.inc()
                    skip(ct)
                if typeKind(ct) == LengType.ParamsT:
                    with var:
                        params = ct.copy()
                    skip(params)
                    retType = _genTypeLLVMReadOnly(c, params)
            with var:
                onErrCallResult = default(LLValue)
            _genCallWithType(c, n, retType, onErrCallResult)
            if kind(onErrAction) != NifKind.DotToken:
                _genOnErrorLLVM(c, onErrAction)
        case LengStmt.ProcS | LengStmt.TypeS:
            _error(c._m, string("expected statement but got: "), n)
        case LengStmt.KeepovfS:
            _genKeepOverflowLLVM(c, n)
