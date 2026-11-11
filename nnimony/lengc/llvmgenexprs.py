# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/llvmgenexprs.nim
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
# Generates LLVM IR for expressions. Each expression returns an LLValue
# and may emit LLInstr instructions to the current block.

from __future__ import annotations
from nimic.ntypes import *


def _zeroVal(typ: LLType) -> LLValue:
    """{.inline.}"""
    return llNull(typ) if typ is not None and typ.kind == LLTypeKind.llPtr else llIntTextC(string("0"), typ)


def _isFloatType(t: LLType) -> bool:
    """{.inline.}"""
    return t is not None and t.kind == LLTypeKind.llFloat


def _scalarTypeKind(c: mut @ LLVMCode, typ: Cursor) -> LengType:
    with var:
        t = navigateToObjectBody(c._m, typ)
    if typeKind(t) == LengType.EnumT:
        t.inc()
        t = navigateToObjectBody(c._m, t)
    result = typeKind(t)
    return result


def _pointeeType(c: mut @ LLVMCode, typ: Cursor) -> Cursor:
    with let:
        t = navigateToObjectBody(c._m, typ)
    if typeKind(t) in Tset[LengType](LengType.PtrT, LengType.AptrT, LengType.FlexarrayT):
        result = _firstSon(t)
    else:
        result = default(Cursor)
    return result


def _coerceInPlace(c: mut @ LLVMCode, val: mut @ LLValue, srcTypeCursor: Cursor, destTypeCursor: Cursor):
    ## Coerce `val` to `destTypeCursor`, overwriting it. `coerceValueLLVM` returns
    ## through a `var` out-param, and handing it the same variable as both the
    ## (immutable) input and the output aliases the two -- route it through a
    ## temporary instead.
    with var:
        coerced = default(LLValue)
    _coerceValueLLVM(c, val, srcTypeCursor, destTypeCursor, coerced)
    val <<= coerced


def _signedBinOp(c: mut @ LLVMCode, n: mut @ Cursor, op: string, result: mut @ LLValue):
    with into(n):
        with let:
            typCursor = n.copy()
            typLL = _genTypeLLVM(c, n)
            srcLhs = getType(c._m, n)
        with var:
            lhs = default(LLValue)
        _genExprLLVM(c, n, lhs)
        with let:
            srcRhs = getType(c._m, n)
        with var:
            rhs = default(LLValue)
        _genExprLLVM(c, n, rhs)
        if not typeEq(lhs.typ, typLL):
            _coerceInPlace(c, lhs, srcLhs, typCursor)
        if not typeEq(rhs.typ, typLL):
            _coerceInPlace(c, rhs, srcRhs, typCursor)
        with let:
            t = c.nextTemp()
            res = llReg(t, typLL)
        emit_(c, newLLBinInstr(res=res, binOp=op, binLhs=lhs, binRhs=rhs))
        result <<= res
        while n.hasMore(): skip(n)


def _unsignedBinOp(c: mut @ LLVMCode, n: mut @ Cursor, signedOp: string, unsignedOp: string, result: mut @ LLValue):
    with into(n):
        with let:
            isUnsigned = typeKind(n) == LengType.UT
            typCursor = n.copy()
            typLL = _genTypeLLVM(c, n)
            srcLhs = getType(c._m, n)
        with var:
            lhs = default(LLValue)
        _genExprLLVM(c, n, lhs)
        with let:
            srcRhs = getType(c._m, n)
        with var:
            rhs = default(LLValue)
        _genExprLLVM(c, n, rhs)
        if not typeEq(lhs.typ, typLL):
            _coerceInPlace(c, lhs, srcLhs, typCursor)
        if not typeEq(rhs.typ, typLL):
            _coerceInPlace(c, rhs, srcRhs, typCursor)
        with let:
            op = unsignedOp if isUnsigned else signedOp
            t = c.nextTemp()
            res = llReg(t, typLL)
        emit_(c, newLLBinInstr(res=res, binOp=op, binLhs=lhs, binRhs=rhs))
        result <<= res
        while n.hasMore(): skip(n)


def _cmpOp(c: mut @ LLVMCode, n: mut @ Cursor, signedPred: string, unsignedPred: string, result: mut @ LLValue):
    with let:
        cmpInfo = _info(n)
    with into(n):
        with let:
            lhsExpr = n
            lhsType = getType(c._m, lhsExpr)
            lhsTK = _scalarTypeKind(c, lhsType)
        with var:
            lhs = default(LLValue)
        _genExprLLVM(c, n, lhs)
        with let:
            rhsExpr = n
            rhsType = getType(c._m, rhsExpr)
        with var:
            rhs = default(LLValue)
        _genExprLLVM(c, n, rhs)
        # LLVM cmp needs both operands at one type: widen the narrower one.
        if not typeEq(lhs.typ, rhs.typ):
            if _typeSizeBits(c, lhsType) < _typeSizeBits(c, rhsType):
                _coerceInPlace(c, lhs, lhsType, rhsType)
            else:
                _coerceInPlace(c, rhs, rhsType, lhsType)
        with let:
            t = c.nextTemp()
        if _isFloatType(lhs.typ):
            with let:
                match signedPred:
                    case "eq": fpPred = string("oeq")
                    case "ne": fpPred = string("one")
                    case "slt": fpPred = string("olt")
                    case "sle": fpPred = string("ole")
                    case _: fpPred = signedPred
                res = llReg(t, c.prim.i1)
            setLoc(c, cmpInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llFcmp, result=res, fcmpPred=fpPred, fcmpLhs=lhs, fcmpRhs=rhs))
            result <<= res
        else:
            with let:
                pred = unsignedPred if unsignedPred != "" and lhsTK in Tset[LengType](LengType.UT, LengType.CT, LengType.BoolT) else signedPred
                res = llReg(t, c.prim.i1)
            setLoc(c, cmpInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=res, icmpPred=pred, icmpLhs=lhs, icmpRhs=rhs))
            result <<= res
        while n.hasMore(): skip(n)


def _genBoolCmpOp(c: mut @ LLVMCode, n: mut @ Cursor, signedPred: string, unsignedPred: string, result: mut @ LLValue):
    with var:
        cmp = default(LLValue)
    _cmpOp(c, n, signedPred, unsignedPred, cmp)
    with let:
        t = c.nextTemp()
        res = llReg(t, c.prim.i8_)
    emit_(c, LLInstr(kind=LLInstrKind.llZext, result=res, castOp=string("zext"), castSrc=cmp, castDstType=c.prim.i8_))
    result <<= res


def _getExternName(c: mut @ LLVMCode, s: SymId) -> string:
    with let:
        d = getDeclOrNil(c._m, s)
    if not isNil(d) and d.extern != StrId(0) and d.isImport:
        result = c._m.pool.strings[d.extern].copy()
    else:
        result = string("")
    return result


def _memoryOrderToLLVM(val: LLValue) -> LLAtomicOrdering:
    result = LLAtomicOrdering.llaoSeqCst
    return result


def _atomicAlign(c: mut @ LLVMCode, typ: LLType) -> nint:
    """{.inline.}"""
    if typ is None: return c._bits // 8
    elif typ.kind == LLTypeKind.llPtr: return c._bits // 8
    elif typ.kind == LLTypeKind.llInt:
        match typ.intBits:
            case 8: return 1
            case 16: return 2
            case 32: return 4
            case 64: return 8
            case _: return c._bits // 8
    else: return c._bits // 8


def _declareExtern(c: mut @ LLVMCode, e: LLExternDecl):
    if e.name not in c.declaredExterns:
        c.declaredExterns.incl(e.name)
        c.module.externs.add(e)


def _genAtomicCall(c: mut @ LLVMCode, externName: string, args: seq[LLValue], retType: LLType, result: mut @ LLValue):
    with let:
        ordering = _memoryOrderToLLVM(args[back(1)])
        align = _atomicAlign(c, retType)
    match externName:
        case "__atomic_load_n":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llLoad, result=res, loadPtr=args[0], loadAtomic=True, loadOrdering=ordering, loadAlign=align))
            result <<= res
        case "__atomic_store_n":
            emit_(c, LLInstr(kind=LLInstrKind.llStore, storeValue=args[1], storePtr=args[0], storeAtomic=True, storeOrdering=ordering, storeAlign=_atomicAlign(c, args[1].typ)))
            result <<= llNoneVal()
        case "__atomic_exchange_n":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwXchg, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            result <<= res
        case "__atomic_compare_exchange_n":
            with let:
                valTyp = args[2].typ
                valAlign = _atomicAlign(c, valTyp)
                le = c.nextTemp()
                leRes = llReg(le, valTyp)
            emit_(c, LLInstr(kind=LLInstrKind.llLoad, result=leRes, loadPtr=args[1]))
            with let:
                t = c.nextTemp()
                aggTyp = LLType(kind=LLTypeKind.llStruct, structFields=seq[LLStructField]([LLStructField(typ=valTyp), LLStructField(typ=c.prim.i1)]))
                cmpxRes = llReg(t, aggTyp)
            emit_(c, LLInstr(kind=LLInstrKind.llCmpxchg, result=cmpxRes, cxPtr=args[0], cxExpected=leRes, cxDesired=args[2], cxAggType=aggTyp, cxSuccessOrdering=ordering, cxFailureOrdering=ordering, cxAlign=valAlign))
            with let:
                success = c.nextTemp()
                succRes = llReg(success, c.prim.i1)
            emit_(c, LLInstr(kind=LLInstrKind.llExtractValue, result=succRes, evAggregate=cmpxRes, evAggType=aggTyp, evIndex=1))
            with let:
                oldVal = c.nextTemp()
                oldRes = llReg(oldVal, valTyp)
            emit_(c, LLInstr(kind=LLInstrKind.llExtractValue, result=oldRes, evAggregate=cmpxRes, evAggType=aggTyp, evIndex=0))
            c.emitStore(oldRes, args[1])
            with let:
                r = c.nextTemp()
                rRes = llReg(r, c.prim.i8_)
            emit_(c, LLInstr(kind=LLInstrKind.llZext, result=rRes, castOp=string("zext"), castSrc=succRes, castDstType=c.prim.i8_))
            result <<= rRes
        case "__atomic_add_fetch":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwAdd, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            with let:
                r = c.nextTemp()
                rRes = llReg(r, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llBinOp, result=rRes, binOp=string("add"), binLhs=res, binRhs=args[1]))
            result <<= rRes
        case "__atomic_sub_fetch":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwSub, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            with let:
                r = c.nextTemp()
                rRes = llReg(r, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llBinOp, result=rRes, binOp=string("sub"), binLhs=res, binRhs=args[1]))
            result <<= rRes
        case "__atomic_fetch_add":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwAdd, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            result <<= res
        case "__atomic_fetch_sub":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwSub, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            result <<= res
        case "__atomic_fetch_and":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwAnd, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            result <<= res
        case "__atomic_fetch_or":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwOr, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            result <<= res
        case "__atomic_fetch_xor":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwXor, armwPtr=args[0], armwVal=args[1], armwOrdering=ordering, armwAlign=align))
            result <<= res
        case "__atomic_test_and_set":
            with let:
                t = c.nextTemp()
                res = llReg(t, c.prim.i8_)
            emit_(c, LLInstr(kind=LLInstrKind.llAtomicrmw, result=res, armwOp=LLAtomicrmwOp.llrmwXchg, armwPtr=args[0], armwVal=llIntTextC(string("1"), c.prim.i8_), armwOrdering=ordering, armwAlign=1))
            with let:
                r = c.nextTemp()
                rRes = llReg(r, c.prim.i1)
            emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=rRes, icmpPred=string("ne"), icmpLhs=res, icmpRhs=llIntTextC(string("0"), c.prim.i8_)))
            with let:
                r2 = c.nextTemp()
                r2Res = llReg(r2, c.prim.i8_)
            emit_(c, LLInstr(kind=LLInstrKind.llZext, result=r2Res, castOp=string("zext"), castSrc=rRes, castDstType=c.prim.i8_))
            result <<= r2Res
        case "__atomic_clear":
            emit_(c, LLInstr(kind=LLInstrKind.llStore, storeValue=llIntTextC(string("0"), c.prim.i8_), storePtr=args[0], storeAtomic=True, storeOrdering=ordering, storeAlign=1))
            result <<= llNoneVal()
        case "__atomic_thread_fence":
            emit_(c, LLInstr(kind=LLInstrKind.llFence, fenceOrdering=ordering))
            result <<= llNoneVal()
        case "__atomic_signal_fence":
            emit_(c, LLInstr(kind=LLInstrKind.llFence, fenceOrdering=ordering, fenceSyncscope=string("singlethread")))
            result <<= llNoneVal()
        case _:
            with var:
                argStr = string("")
            for i, a in pairs(args):
                if i > 0: argStr.add(string(", "))
                operand(a, argStr)
            if retType.kind == LLTypeKind.llVoid:
                emit_(c, LLInstr(kind=LLInstrKind.llCall, callCallee=llGlobalRef(externName, c.prim.ptrT), callRetType=retType, callArgs=args))
                result <<= llNoneVal()
            else:
                with let:
                    t = c.nextTemp()
                    res = llReg(t, retType)
                emit_(c, LLInstr(kind=LLInstrKind.llCall, result=res, callCallee=llGlobalRef(externName, c.prim.ptrT), callRetType=retType, callArgs=args))
                result <<= res


def _sizeToI64(c: mut @ LLVMCode, v: LLValue) -> LLValue:
    ## The `llvm.mem*` intrinsics take an `i64` length; a Leng size expression
    ## is whatever integer the target's `int` is. Sizes are never negative, so a
    ## narrower one zero-extends.
    if v.kind == LLValueKind.llvInt or (v.typ.kind == LLTypeKind.llInt and v.typ.intBits == 64):
        result = withType(v, c.prim.i64_)
    else:
        with let:
            t = c.nextTemp()
        result = llReg(t, c.prim.i64_)
        emit_(c, LLInstr(kind=LLInstrKind.llZext, result=result, castOp=string("zext"), castSrc=v, castDstType=c.prim.i64_))
    return result


def _genMemIntrinsicCall(c: mut @ LLVMCode, externName: string, args: seq[LLValue], retType: LLType, result: mut @ LLValue):
    match externName:
        case "memcpy":
            emit_(c, LLInstr(kind=LLInstrKind.llCall, callCallee=llGlobalRef(string("llvm.memcpy.p0.p0.i64"), c.prim.ptrT), callRetType=c.prim.voidT, callArgs=seq[LLValue]([args[0], args[1], args[2], llIntTextC(string("0"), c.prim.i1)])))
            _declareExtern(c, LLExternDecl(name=string("llvm.memcpy.p0.p0.i64"), raw=string("declare void @llvm.memcpy.p0.p0.i64(ptr noalias nocapture writeonly, ptr noalias nocapture readonly, i64, i1 immarg)")))
            result <<= withType(args[0], c.prim.ptrT)
        case "memmove":
            emit_(c, LLInstr(kind=LLInstrKind.llCall, callCallee=llGlobalRef(string("llvm.memmove.p0.p0.i64"), c.prim.ptrT), callRetType=c.prim.voidT, callArgs=seq[LLValue]([args[0], args[1], args[2], llIntTextC(string("0"), c.prim.i1)])))
            _declareExtern(c, LLExternDecl(name=string("llvm.memmove.p0.p0.i64"), raw=string("declare void @llvm.memmove.p0.p0.i64(ptr nocapture writeonly, ptr nocapture readonly, i64, i1 immarg)")))
            result <<= withType(args[0], c.prim.ptrT)
        case "memset":
            with let:
                val8 = c.nextTemp()
                val8Res = llReg(val8, c.prim.i8_)
            emit_(c, LLInstr(kind=LLInstrKind.llTrunc, result=val8Res, castOp=string("trunc"), castSrc=args[1], castDstType=c.prim.i8_))
            emit_(c, LLInstr(kind=LLInstrKind.llCall, callCallee=llGlobalRef(string("llvm.memset.p0.i64"), c.prim.ptrT), callRetType=c.prim.voidT, callArgs=seq[LLValue]([args[0], val8Res, args[2], llIntTextC(string("0"), c.prim.i1)])))
            _declareExtern(c, LLExternDecl(name=string("llvm.memset.p0.i64"), raw=string("declare void @llvm.memset.p0.i64(ptr nocapture writeonly, i8, i64, i1 immarg)")))
            result <<= withType(args[0], c.prim.ptrT)
        case "memcmp":
            with let:
                t = c.nextTemp()
                res = llReg(t, c.prim.i32_)
            emit_(c, LLInstr(kind=LLInstrKind.llCall, result=res, callCallee=llGlobalRef(string("memcmp"), c.prim.ptrT), callRetType=c.prim.i32_, callArgs=seq[LLValue]([args[0], args[1], args[2]])))
            _declareExtern(c, LLExternDecl(name=string("memcmp"), raw=string("declare i32 @memcmp(ptr nocapture, ptr nocapture, i64)")))
            result <<= res
        case _:
            with var:
                argStr = string("")
            for i, a in pairs(args):
                if i > 0: argStr.add(string(", "))
                operand(a, argStr)
            if retType.kind == LLTypeKind.llVoid:
                emit_(c, LLInstr(kind=LLInstrKind.llCall, callCallee=llGlobalRef(externName, c.prim.ptrT), callRetType=retType, callArgs=args))
                result <<= llNoneVal()
            else:
                with let:
                    t = c.nextTemp()
                    res = llReg(t, retType)
                emit_(c, LLInstr(kind=LLInstrKind.llCall, result=res, callCallee=llGlobalRef(externName, c.prim.ptrT), callRetType=retType, callArgs=args))
                result <<= res


with const:
    _AtomicBuiltins = [string("__atomic_load_n"), string("__atomic_store_n"), string("__atomic_exchange_n"), string("__atomic_compare_exchange_n"), string("__atomic_add_fetch"), string("__atomic_sub_fetch"), string("__atomic_fetch_add"), string("__atomic_fetch_sub"), string("__atomic_fetch_and"), string("__atomic_fetch_or"), string("__atomic_fetch_xor"), string("__atomic_test_and_set"), string("__atomic_clear"), string("__atomic_thread_fence"), string("__atomic_signal_fence")]
    _MemIntrinsics = [string("memcpy"), string("memmove"), string("memset"), string("memcmp")]
    _GccBuiltins = [string("__builtin_ctzll"), string("__builtin_ctz"), string("__builtin_clzll"), string("__builtin_clz"), string("__builtin_popcountll"), string("__builtin_popcount"), string("__builtin_bswap16"), string("__builtin_bswap32"), string("__builtin_bswap64"), string("__builtin_expect")]


@template_expand
def _genGccBuiltinCall(c: mut @ LLVMCode, externName: string, args: seq[LLValue], retType: LLType, result: mut @ LLValue):
    with let:
        isI32 = retType.kind == LLTypeKind.llInt and retType.intBits == 32
    @template
    def callIntrinsic(iname: string, rtype: LLType) -> LLValue:
        with let:
            t = c.nextTemp()
            res = llReg(t, rtype)
        emit_(c, LLInstr(kind=LLInstrKind.llCall, result=res, callCallee=llGlobalRef(iname, c.prim.ptrT), callRetType=rtype, callArgs=seq[LLValue]([args[0], llIntTextC(string("0"), c.prim.i1)])))
        return res
    match externName:
        case "__builtin_ctzll":
            with let:
                r = callIntrinsic(string("llvm.cttz.i64"), c.prim.i64_)
            if isI32:
                with let:
                    t = c.nextTemp()
                    res = llReg(t, c.prim.i32_)
                emit_(c, LLInstr(kind=LLInstrKind.llTrunc, result=res, castOp=string("trunc"), castSrc=r, castDstType=c.prim.i32_))
                result <<= res
            else: result <<= r
        case "__builtin_ctz":
            result <<= callIntrinsic(string("llvm.cttz.i32"), c.prim.i32_)
        case "__builtin_clzll":
            with let:
                r = callIntrinsic(string("llvm.ctlz.i64"), c.prim.i64_)
            if isI32:
                with let:
                    t = c.nextTemp()
                    res = llReg(t, c.prim.i32_)
                emit_(c, LLInstr(kind=LLInstrKind.llTrunc, result=res, castOp=string("trunc"), castSrc=r, castDstType=c.prim.i32_))
                result <<= res
            else: result <<= r
        case "__builtin_clz":
            result <<= callIntrinsic(string("llvm.ctlz.i32"), c.prim.i32_)
        case "__builtin_popcountll":
            with let:
                r = callIntrinsic(string("llvm.ctpop.i64"), c.prim.i64_)
            if isI32:
                with let:
                    t = c.nextTemp()
                    res = llReg(t, c.prim.i32_)
                emit_(c, LLInstr(kind=LLInstrKind.llTrunc, result=res, castOp=string("trunc"), castSrc=r, castDstType=c.prim.i32_))
                result <<= res
            else: result <<= r
        case "__builtin_popcount":
            result <<= callIntrinsic(string("llvm.ctpop.i32"), c.prim.i32_)
        case "__builtin_bswap16":
            result <<= callIntrinsic(string("llvm.bswap.i16"), c.prim.i16_)
        case "__builtin_bswap32":
            result <<= callIntrinsic(string("llvm.bswap.i32"), c.prim.i32_)
        case "__builtin_bswap64":
            result <<= callIntrinsic(string("llvm.bswap.i64"), c.prim.i64_)
        case "__builtin_expect":
            result <<= args[0]
        case "__builtin_sqrt" | "__builtin_sqrtf":
            with let:
                t = c.nextTemp()
                res = llReg(t, retType)
            emit_(c, LLInstr(kind=LLInstrKind.llCall, result=res, callCallee=llGlobalRef(string("llvm.sqrt.f32") if externName == "__builtin_sqrtf" else string("llvm.sqrt.f64"), c.prim.ptrT), callRetType=retType, callArgs=seq[LLValue]([args[0]])))
            result <<= res
        case _:
            pass


def _genInstrLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    # A portable row lowers exactly like the GCC builtin it stands for, and
    # `genGccBuiltinCall` already emits those: the `llvm.cttz`/`ctlz`/`ctpop`/
    # `bswap` call, the `i1 is_zero_poison` operand, and the i64→i32 truncation.
    # It is keyed on the builtin NAME, which is what `cBuiltinFor` returns, so
    # `(instr …)` needs no lowering of its own — resolve the row and reuse it.
    # A target-pinned row has no portable spelling by construction, so there
    # `cBuiltinFor` yields "" and this rejects rather than substituting.
    with let:
        start = n.copy()
        retType = _genTypeLLVMReadOnly(c, getType(c._m, start))
    with into(n):
        with var:
            bits = nint(0)
        with let:
            op = intrinsicOfCallee(c._m, n, bits)  # `n` is at the callee symbol
        if op == IntrinsicOp.NoIntrinsicOp:
            _error(c._m, string("callee of (instr ...) carries no instruction/intrinsic pragma: "), start)

        with var:
            args: seq[LLValue] = seq[LLValue]([])
        skip(n)  # the callee symbol
        while n.hasMore():
            with var:
                a = default(LLValue)
            _genExprLLVM(c, n, a)
            args.add(a)

        setLoc(c, _info(start))
        if op.isAtomic():
            _genAtomicCall(c, cBuiltinFor(op, bits), args, retType, result)
        elif op.isMemOp():
            # the same lowering as a call to the importc'd C function of that name
            args[2] = _sizeToI64(c, args[2])
            with let:
                match op:
                    case IntrinsicOp.MemsetOp: name = string("memset")
                    case IntrinsicOp.MemcpyOp: name = string("memcpy")
                    case _: name = string("memcmp")
            _genMemIntrinsicCall(c, name, args, retType, result)
        else:
            with let:
                builtin = cBuiltinFor(op, bits)
            if builtin.len == 0:
                # We can't find gcc builtin for it, but it means that intrinsic is
                # target specific and currently unsupported

                _error(c._m, string("the LLVM backend has no lowering for this instruction: "), start)

            _genGccBuiltinCall(c, builtin, args, retType, result)


def _genCallWithType(c: mut @ LLVMCode, n: mut @ Cursor, retType: LLType, result: mut @ LLValue):
    with let:
        callInfo = _info(n)
    with into(n):

        with var:
            callee = default(LLValue)
            calleeExtern = string("")
        if kind(n) == NifKind.Symbol:
            with let:
                calleeSym = symId(n)
            c.requestedSyms.incl(calleeSym)
            calleeExtern = _getExternName(c, calleeSym)
            with let:
                decl = getDeclOrNil(c._m, calleeSym)
            if not isNil(decl) and decl.kind == LengSym.ProcY:
                with let:
                    bare = c._mangleSym(calleeSym)
                    ftype = genFuncTypeLLVM(c, decl.pos)
                callee = llGlobalRef(bare, ftype)
                n.inc()
            else:
                _genExprLLVM(c, n, callee)
        else:
            _genExprLLVM(c, n, callee)

        with var:
            args: seq[LLValue] = seq[LLValue]([])
        while n.hasMore():
            with var:
                arg = default(LLValue)
            _genExprLLVM(c, n, arg)
            args.add(arg)
        while n.hasMore(): skip(n)

    if calleeExtern != "":
        if calleeExtern in _AtomicBuiltins:
            _genAtomicCall(c, calleeExtern, args, retType, result)
            return
        if calleeExtern in _MemIntrinsics:
            _genMemIntrinsicCall(c, calleeExtern, args, retType, result)
            return
        if calleeExtern in _GccBuiltins:
            _genGccBuiltinCall(c, calleeExtern, args, retType, result)
            return

    if retType.kind == LLTypeKind.llVoid:
        setLoc(c, callInfo)
        emit_(c, LLInstr(kind=LLInstrKind.llCall, callCallee=callee, callRetType=retType, callArgs=args))
        result <<= llNoneVal()
    else:
        with let:
            t = c.nextTemp()
            res = llReg(t, retType)
        setLoc(c, callInfo)
        emit_(c, LLInstr(kind=LLInstrKind.llCall, result=res, callCallee=callee, callRetType=retType, callArgs=args))
        result <<= res


def _genCallLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with let:
        ptrT = c.prim.ptrT
    _genCallWithType(c, n, ptrT, result)


def _genCallExprLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    _genCallLLVM(c, n, result)


def _isLengInt(tk: LengType) -> bool:
    """{.inline.}"""
    return tk in Tset[LengType](LengType.IT, LengType.UT, LengType.CT, LengType.BoolT, LengType.EnumT)


def _isLengFloat(tk: LengType) -> bool:
    """{.inline.}"""
    return tk == LengType.FT


def _isLengPtr(tk: LengType) -> bool:
    """{.inline.}"""
    return tk in Tset[LengType](LengType.PtrT, LengType.AptrT, LengType.ProctypeT)


def _coerceValueLLVM(c: mut @ LLVMCode, val: LLValue, srcTypeCursor: Cursor, destTypeCursor: Cursor, result: mut @ LLValue):
    with let:
        destTyp = _genTypeLLVMReadOnly(c, destTypeCursor)
    if typeEq(val.typ, destTyp):
        result <<= val
        return

    with let:
        srcTK = _scalarTypeKind(c, srcTypeCursor)
        destTK = _scalarTypeKind(c, destTypeCursor)
        t = c.nextTemp()

    if _isLengPtr(srcTK) and _isLengPtr(destTK):
        result <<= withType(val, destTyp)
        return
    elif _isLengPtr(destTK) and _isLengInt(srcTK):
        with let:
            res = llReg(t, destTyp)
        emit_(c, LLInstr(kind=LLInstrKind.llInttoptr, result=res, castOp=string("inttoptr"), castSrc=val, castDstType=destTyp))
        result <<= res
    elif _isLengInt(destTK) and _isLengPtr(srcTK):
        with let:
            res = llReg(t, destTyp)
        emit_(c, LLInstr(kind=LLInstrKind.llPtrtoint, result=res, castOp=string("ptrtoint"), castSrc=val, castDstType=destTyp))
        result <<= res
    elif _isLengFloat(srcTK) and _isLengFloat(destTK):
        with let:
            srcBits = _typeSizeBits(c, srcTypeCursor)
            destBits = _typeSizeBits(c, destTypeCursor)
            res = llReg(t, destTyp)
        if srcBits < destBits:
            emit_(c, LLInstr(kind=LLInstrKind.llFpext, result=res, castOp=string("fpext"), castSrc=val, castDstType=destTyp))
        else:
            emit_(c, LLInstr(kind=LLInstrKind.llFptrunc, result=res, castOp=string("fptrunc"), castSrc=val, castDstType=destTyp))
        result <<= res
    elif _isLengFloat(srcTK) and _isLengInt(destTK):
        with let:
            res = llReg(t, destTyp)
        if destTK in Tset[LengType](LengType.UT, LengType.CT, LengType.BoolT):
            emit_(c, LLInstr(kind=LLInstrKind.llFptoui, result=res, castOp=string("fptoui"), castSrc=val, castDstType=destTyp))
        else:
            emit_(c, LLInstr(kind=LLInstrKind.llFptosi, result=res, castOp=string("fptosi"), castSrc=val, castDstType=destTyp))
        result <<= res
    elif _isLengInt(srcTK) and _isLengFloat(destTK):
        with let:
            res = llReg(t, destTyp)
        if srcTK in Tset[LengType](LengType.UT, LengType.CT, LengType.BoolT):
            emit_(c, LLInstr(kind=LLInstrKind.llUitofp, result=res, castOp=string("uitofp"), castSrc=val, castDstType=destTyp))
        else:
            emit_(c, LLInstr(kind=LLInstrKind.llSitofp, result=res, castOp=string("sitofp"), castSrc=val, castDstType=destTyp))
        result <<= res
    elif _isLengInt(srcTK) and _isLengInt(destTK):
        # Constant integer casts fold to the target type with no instruction.
        if val.kind == LLValueKind.llvInt:
            result <<= withType(val, destTyp)
            return
        with let:
            srcBits = _typeSizeBits(c, srcTypeCursor)
            destBits = _typeSizeBits(c, destTypeCursor)
        if srcBits < destBits:
            with let:
                res = llReg(t, destTyp)
            if srcTK in Tset[LengType](LengType.UT, LengType.CT, LengType.BoolT):
                emit_(c, LLInstr(kind=LLInstrKind.llZext, result=res, castOp=string("zext"), castSrc=val, castDstType=destTyp))
            else:
                emit_(c, LLInstr(kind=LLInstrKind.llSext, result=res, castOp=string("sext"), castSrc=val, castDstType=destTyp))
            result <<= res
        elif srcBits > destBits:
            with let:
                res = llReg(t, destTyp)
            emit_(c, LLInstr(kind=LLInstrKind.llTrunc, result=res, castOp=string("trunc"), castSrc=val, castDstType=destTyp))
            result <<= res
        else:
            result <<= withType(val, destTyp)
            return
    else:
        with var:
            destResolved = navigateToObjectBody(c._m, destTypeCursor)
        with let:
            anonDestType = _genTypeLLVMReadOnly(c, destResolved)
        if typeEq(anonDestType, val.typ):
            result <<= withType(val, destTyp)
            return

        # scalars already checked
        # This means that frontend forgot to generate memcpy
        # and old bitcast generation in this branch was wrong
        _error(c._m, string("the LLVM backend cannot convert ") + serialize(val.typ) + string(" to: "), destTypeCursor)


def _genConvOrCast(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with into(n):
        with let:
            destTypeCursor = n.copy()
        skip(n)
        with let:
            srcTypeCursor = getType(c._m, n)
        with var:
            val = default(LLValue)
        _genExprLLVM(c, n, val)
        _coerceValueLLVM(c, val, srcTypeCursor, destTypeCursor, result)
        while n.hasMore(): skip(n)


def _genAddrLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with var:
        lval = default(LLValue)
    with into(n):
        _genLvalueLLVM(c, n, lval)
        if n.hasMore() and typeQual(n) == LengTypeQualifier.CpprefQ:
            skip(n)
        while n.hasMore(): skip(n)
    result <<= withType(lval, c.prim.ptrT)


def _genFieldPtrLLVM(c: mut @ LLVMCode, objBody: Cursor, fldSym: SymId, gepType: LLType, gepTarget: LLValue) -> LLValue:
    with let:
        access = _fieldAccessLLVM(c, objBody, fldSym)
        idx0 = llIntTextC(string("0"), c.prim.i32_)
    if access.isBranch:
        with let:
            unionPtr = c.emitGEP(gepType, gepTarget, [idx0, llIntTextC(str(access.index), c.prim.i32_)])
        result = c.emitGEP(access.branchType, unionPtr, [idx0, llIntTextC(str(access.branchIndex), c.prim.i32_)])
    else:
        result = c.emitGEP(gepType, gepTarget, [idx0, llIntTextC(str(access.index), c.prim.i32_)])
    return result


def _emitBaseGEP(c: mut @ LLVMCode, objType: LLType, baseValue: LLValue, nifBody: mut @ Cursor, inhDepth: nint) -> tuple[LLType, LLValue]:
    result = (objType, baseValue)
    with var:
        curBody = nifBody.copy()
    for i in range(inhDepth):
        with let:
            baseTypeCursor = baseTypeOfObject(c._m, curBody)
        result = (_genTypeLLVMReadOnly(c, baseTypeCursor), c.emitGEP(result[0], result[1], [llIntTextC(string("0"), c.prim.i32_), llIntTextC(string("0"), c.prim.i32_)]))
        if not baseTypeCursor.cursorIsNil():
            curBody = navigateToObjectBody(c._m, baseTypeCursor)
    nifBody <<= curBody
    return result


def _genDotLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with var:
        objType = Cursor()
        obj = default(LLValue)
        fldSym = SymId()
        inhDepth = 0
    with into(n):
        objType = getNominalType(c._m, n)
        _genLvalueLLVM(c, n, obj)
        fldSym = symId(n)
        skip(n)
        if kind(n) == NifKind.IntLit:
            inhDepth = nint(intVal(n))
            n.inc()
        while n.hasMore(): skip(n)

    with var:
        curType = objType
        curBody = navigateToObjectBody(c._m, curType)
    with let:
        objTypeLL = _genTypeLLVMReadOnly(c, curType)
    with var:
        gepTarget = obj
        gepType = objTypeLL
    for i in range(inhDepth):
        gepTarget = c.emitGEP(gepType, gepTarget, [llIntTextC(string("0"), c.prim.i32_), llIntTextC(string("0"), c.prim.i32_)])
        with let:
            baseTypeCursor = baseTypeOfObject(c._m, curBody)
        if not baseTypeCursor.cursorIsNil():
            curType = baseTypeCursor
            curBody = navigateToObjectBody(c._m, curType)
            gepType = _genTypeLLVMReadOnly(c, curType)
    result <<= withType(_genFieldPtrLLVM(c, curBody, fldSym, gepType, gepTarget), c.prim.ptrT)


def _isAddressableExpr(n: Cursor) -> bool:
    """{.inline.}"""
    ## True iff `genLvalueLLVM` can take `n`'s address directly; false ⇒ it's a
    ## pure rvalue (aconstr/oconstr/par/call) that must be materialised into a temp.
    match exprKind(n):
        case LengExpr.NoExpr: result = kind(n) == NifKind.Symbol
        case LengExpr.DerefC | LengExpr.AtC | LengExpr.PatC | LengExpr.DotC | LengExpr.ErrvC | LengExpr.OvfC | LengExpr.BaseobjC: result = True
        case _: result = False
    return result


def _genIndexLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    ## C's integer promotion (`byte` 200 must not become -56).
    ## Other backends also do it, but integer promotion might be incorrect.
    with let:
        typ = _scalarTypeKind(c, getType(c._m, n))
    _genExprLLVM(c, n, result)
    if typ in Tset[LengType](LengType.UT, LengType.CT, LengType.BoolT) and result.typ.kind == LLTypeKind.llInt and result.typ.intBits < c._bits:
        with let:
            wide = llReg(c.nextTemp(), c.llIntBits(c._bits))
        emit_(c, LLInstr(kind=LLInstrKind.llZext, result=wide, castOp=string("zext"), castSrc=result, castDstType=wide.typ))
        result <<= wide


def _genAtLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with var:
        arrType = Cursor()
        arr = default(LLValue)
        idx = default(LLValue)
    with into(n):
        arrType = getType(c._m, n)
        if _isAddressableExpr(n):
            _genLvalueLLVM(c, n, arr)
        else:
            # Rvalue base has no address (only an SSA value) — alloca + store to give
            # it a home, then address that.
            with var:
                val = default(LLValue)
            _genExprLLVM(c, n, val)
            with let:
                typ = _genTypeLLVMReadOnly(c, arrType)
                tmp = c.nextTemp()
            c.emitAlloca(tmp, typ)
            c.emitStore(val, llReg(tmp, c.prim.ptrT))
            arr = llReg(tmp, c.prim.ptrT)
        _genIndexLLVM(c, n, idx)
        while n.hasMore(): skip(n)
    with let:
        arrTypeName = _genTypeLLVMReadOnly(c, arrType)
    result <<= withType(c.emitGEP(arrTypeName, arr, [llIntTextC(string("0"), c.prim.i32_), idx]), c.prim.ptrT)


def _genPatLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with var:
        baseType = Cursor()
        base = default(LLValue)
        idx = default(LLValue)
    with into(n):
        baseType = getType(c._m, n)
        _genExprLLVM(c, n, base)
        _genIndexLLVM(c, n, idx)
        while n.hasMore(): skip(n)
    with let:
        elemCursor = _pointeeType(c, baseType)
    if elemCursor.cursorIsNil():
        _error(c._m, string("expected pointer type for `pat` but got: "), baseType)
    with let:
        elemType = _genTypeLLVMReadOnly(c, elemCursor)
    result <<= withType(c.emitGEP(elemType, base, [idx], inbounds=False), c.prim.ptrT)


def _genSizeofLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with var:
        typ = LLType()
    with into(n):
        typ = _genTypeLLVM(c, n)
        while n.hasMore(): skip(n)
    with let:
        t1 = c.emitGEP(typ, llNull(c.prim.ptrT), [llIntTextC(string("1"), c.prim.i32_)], inbounds=False)
        t2 = c.nextTemp()
        res = llReg(t2, c.llIntBits(c._bits))
    emit_(c, LLInstr(kind=LLInstrKind.llPtrtoint, result=res, castOp=string("ptrtoint"), castSrc=t1, castDstType=c.llIntBits(c._bits)))
    result <<= res


def _isGlobalSym(c: mut @ LLVMCode, s: SymId) -> bool:
    with let:
        d = getDeclOrNil(c._m, s)
    result = (not isNil(d) and d.kind in Tset[LengSym](LengSym.GvarY, LengSym.TvarY, LengSym.ConstY, LengSym.ProcY)) or s in c.emittedConsts
    return result


def _genLvalueLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    match exprKind(n):
        case LengExpr.NoExpr:
            if kind(n) == NifKind.Symbol:
                with let:
                    s = symId(n)
                c.requestedSyms.incl(s)
                with let:
                    name = c._mangleSym(s)
                n.inc()
                if _isGlobalSym(c, s):
                    result <<= llGlobalRef(name, c.prim.ptrT)
                else:
                    result <<= llReg(name, c.prim.ptrT)
            else:
                _error(c._m, string("expected expression but got: "), n)
        case LengExpr.DerefC:
            with var:
                ptrVal = default(LLValue)
            with into(n):
                _genExprLLVM(c, n, ptrVal)
                if n.hasMore() and typeQual(n) == LengTypeQualifier.CpprefQ:
                    skip(n)
                while n.hasMore(): skip(n)
            result <<= withType(ptrVal, c.prim.ptrT)
        case LengExpr.AtC:
            _genAtLLVM(c, n, result)
        case LengExpr.PatC:
            _genPatLLVM(c, n, result)
        case LengExpr.DotC:
            _genDotLLVM(c, n, result)
        case LengExpr.ErrvC:
            result <<= llGlobalRef(string("LENGC_ERR_"), c.prim.ptrT)
            skip(n)
        case LengExpr.OvfC:
            result <<= llGlobalRef(string("LENGC_OVF_"), c.prim.ptrT)
            skip(n)
        case LengExpr.BaseobjC:
            with into(n):
                skip(n)
                skip(n)
                _genLvalueLLVM(c, n, result)
                while n.hasMore(): skip(n)
        case LengExpr.SufC | LengExpr.ParC | LengExpr.AddrC | LengExpr.HaddrC | LengExpr.NilC | LengExpr.InfC | LengExpr.NeginfC | LengExpr.NanC | LengExpr.FalseC | LengExpr.TrueC | LengExpr.AndC | LengExpr.OrC | LengExpr.NotC | LengExpr.NegC | LengExpr.SizeofC | LengExpr.AlignofC | LengExpr.OffsetofC | LengExpr.OconstrC | LengExpr.AconstrC | LengExpr.AddC | LengExpr.SubC | LengExpr.MulC | LengExpr.DivC | LengExpr.ModC | LengExpr.ShrC | LengExpr.ShlC | LengExpr.BitandC | LengExpr.BitorC | LengExpr.BitxorC | LengExpr.BitnotC | LengExpr.EqC | LengExpr.NeqC | LengExpr.LeC | LengExpr.LtC | LengExpr.CastC | LengExpr.ConvC | LengExpr.CallC | LengExpr.InstrC:
            _error(c._m, string("not an lvalue: "), n)


def _genExprLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    # Expression-producing templates are the common case (`>=` is one), so the
    # frame has to open here too, not just on statements (#1987).
    with c._withExpansionFrames(_info(n)):
        _genExprBodyLLVM(c, n, result)


def _genExprBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    match exprKind(n):
        case LengExpr.NoExpr:
            match kind(n):
                case NifKind.IntLit:
                    with let:
                        i = intVal(n)
                    n.inc()
                    result <<= llIntTextC(str(i), c.llIntBits(c._bits))
                case NifKind.UIntLit:
                    with let:
                        i = uintVal(n)
                    n.inc()
                    result <<= llIntTextC(str(i), c.llIntBits(c._bits))
                case NifKind.FloatLit:
                    with let:
                        f = floatVal(n)
                    n.inc()
                    result <<= LLValue(kind=LLValueKind.llvFloat, floatText=_llFloatHexText(f), typ=c.prim.f64_)
                case NifKind.CharLit:
                    with let:
                        ch = charLit(n)
                    n.inc()
                    result <<= llIntTextC(str(ord(ch)), c.prim.i8_)
                case NifKind.StrLit:
                    with let:
                        s = c._m.pool.strings[_litId(n)]
                    n.inc()
                    with let:
                        globalName = string(".str.") + str(c.strLitCounter)
                    c.strLitCounter += 1
                    with var:
                        escaped = newStringOfCap(s.len + 10)
                    for ch in s:
                        with let:
                            o = ord(ch)
                        if o < 32 or o > 126 or ch == char('"') or ch == char('\\'):
                            escaped.add(char('\\'))
                            escaped.add(string("0123456789ABCDEF")[o >> 4])
                            escaped.add(string("0123456789ABCDEF")[o & 0xF])
                        else:
                            escaped.add(ch)
                    with let:
                        arrTyp = newLLArrayType(s.len + 1, c.prim.i8_)
                    c.module.globals.add(LLGlobal(name=globalName, typ=arrTyp, initVal=LLValue(kind=LLValueKind.llvCString, strVal=escaped + string("\\00"), typ=arrTyp), isConstant=True, isPrivate=True))
                    result <<= llGlobalRef(globalName, c.prim.ptrT)
                case NifKind.Symbol:
                    with let:
                        s = symId(n)
                    c.requestedSyms.incl(s)
                    with let:
                        name = c._mangleSym(s)
                        symType = getType(c._m, n)
                        decl = getDeclOrNil(c._m, s)
                    n.inc()
                    if typeKind(symType) == LengType.EnumT and not isNil(decl) and decl.kind not in Tset[LengSym](LengSym.VarY, LengSym.GvarY, LengSym.TvarY):
                        with var:
                            enumBody = symType.copy()
                        enumBody.inc()
                        with let:
                            baseTyp = _genTypeLLVMReadOnly(c, enumBody)
                        skip(enumBody)
                        while enumBody.hasMore():
                            if substructureKind(enumBody) == LengOther.EfldU:
                                for _ in into(enumBody):
                                    if kind(enumBody) == NifKind.SymbolDef and symId(enumBody) == s:
                                        enumBody.inc()
                                        if kind(enumBody) == NifKind.IntLit:
                                            result <<= llIntTextC(str(intVal(enumBody)), baseTyp)
                                        elif kind(enumBody) == NifKind.UIntLit:
                                            result <<= llIntTextC(str(uintVal(enumBody)), baseTyp)
                                        else:
                                            result <<= llIntTextC(string("0"), baseTyp)
                                        return
                                    while enumBody.hasMore(): skip(enumBody)
                            else:
                                skip(enumBody)
                        result <<= llIntTextC(string("0"), baseTyp)
                        return
                    if not isNil(decl) and decl.kind == LengSym.ProcY:
                        # A proc value is a function pointer — plain `ptr` under opaque pointers.
                        # `getType` of a proc symbol returns its `params` cursor, not a type, so
                        # don't feed it to genTypeLLVM (it rejects ParamsT).
                        result <<= llGlobalRef(name, c.prim.ptrT)
                        return
                    with let:
                        typ = _genTypeLLVMReadOnly(c, symType)
                        prefix = string("@") if _isGlobalSym(c, s) else string("%")
                        base = llGlobalRef(name, c.prim.ptrT) if prefix == "@" else llReg(name, c.prim.ptrT)
                    result <<= c.emitLoad(base, typ)
                case _:
                    with let:
                        exprType = getType(c._m, n)
                        typ = _genTypeLLVMReadOnly(c, exprType)
                    with var:
                        lval = default(LLValue)
                    _genLvalueLLVM(c, n, lval)
                    result <<= c.emitLoad(lval, typ)
        case LengExpr.FalseC:
            skip(n)
            result <<= llIntTextC(string("0"), c.prim.i8_)
        case LengExpr.TrueC:
            skip(n)
            result <<= llIntTextC(string("1"), c.prim.i8_)
        case LengExpr.NilC:
            skip(n)
            result <<= llNull(c.prim.ptrT)
        case LengExpr.InfC:
            skip(n)
            result <<= LLValue(kind=LLValueKind.llvFloat, floatText=string("0x7FF0000000000000"), typ=c.prim.f64_)
        case LengExpr.NeginfC:
            skip(n)
            result <<= LLValue(kind=LLValueKind.llvFloat, floatText=string("0xFFF0000000000000"), typ=c.prim.f64_)
        case LengExpr.NanC:
            skip(n)
            result <<= LLValue(kind=LLValueKind.llvFloat, floatText=string("0x7FF8000000000000"), typ=c.prim.f64_)
        case LengExpr.AddC: _signedBinOp(c, n, string("add"), result)
        case LengExpr.SubC: _signedBinOp(c, n, string("sub"), result)
        case LengExpr.MulC: _signedBinOp(c, n, string("mul"), result)
        case LengExpr.DivC: _unsignedBinOp(c, n, string("sdiv"), string("udiv"), result)
        case LengExpr.ModC: _unsignedBinOp(c, n, string("srem"), string("urem"), result)
        case LengExpr.ShlC: _signedBinOp(c, n, string("shl"), result)
        case LengExpr.ShrC: _unsignedBinOp(c, n, string("ashr"), string("lshr"), result)
        case LengExpr.BitandC: _signedBinOp(c, n, string("and"), result)
        case LengExpr.BitorC: _signedBinOp(c, n, string("or"), result)
        case LengExpr.BitxorC: _signedBinOp(c, n, string("xor"), result)
        case LengExpr.BitnotC:
            with var:
                typ = LLType()
                val = default(LLValue)
            with into(n):
                typ = _genTypeLLVM(c, n)
                _genExprLLVM(c, n, val)
                while n.hasMore(): skip(n)
            with let:
                t = c.nextTemp()
                res = llReg(t, typ)
            emit_(c, LLInstr(kind=LLInstrKind.llBinOp, result=res, binOp=string("xor"), binLhs=val, binRhs=llIntTextC(string("-1"), typ)))
            result <<= res
        case LengExpr.NegC:
            with var:
                typ = LLType()
                val = default(LLValue)
            with into(n):
                typ = _genTypeLLVM(c, n)
                _genExprLLVM(c, n, val)
                while n.hasMore(): skip(n)
            with let:
                t = c.nextTemp()
                res = llReg(t, typ)
            if _isFloatType(typ):
                emit_(c, LLInstr(kind=LLInstrKind.llFneg, result=res, fnegVal=val))
                result <<= res
            else:
                emit_(c, LLInstr(kind=LLInstrKind.llBinOp, result=res, binOp=string("sub"), binLhs=llIntTextC(string("0"), typ), binRhs=val))
                result <<= res
        case LengExpr.EqC: _genBoolCmpOp(c, n, string("eq"), string("eq"), result)
        case LengExpr.NeqC: _genBoolCmpOp(c, n, string("ne"), string("ne"), result)
        case LengExpr.LeC: _genBoolCmpOp(c, n, string("sle"), string("ule"), result)
        case LengExpr.LtC: _genBoolCmpOp(c, n, string("slt"), string("ult"), result)
        case LengExpr.AndC:
            with let:
                andInfo = _info(n)
                resName = c.nextTemp()
            with var:
                lhs = default(LLValue)
                rhs = default(LLValue)
            with into(n):
                with let:
                    i8_ = c.prim.i8_
                c.emitAlloca(resName, i8_)
                c.emitStore(llIntTextC(string("0"), c.prim.i8_), llReg(resName, c.prim.ptrT))
                _genExprLLVM(c, n, lhs)
                with let:
                    lhsBool = c.nextTemp()
                    lhsBoolRes = llReg(lhsBool, c.prim.i1)
                setLoc(c, andInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=lhsBoolRes, icmpPred=string("ne"), icmpLhs=lhs, icmpRhs=_zeroVal(lhs.typ)))
                with let:
                    rhsLabel = c.nextLabel()
                    endLabel = c.nextLabel()
                emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=lhsBoolRes, condBrTrue=rhsLabel, condBrFalse=endLabel))
                _ = c.startBlock(rhsLabel)
                _genExprLLVM(c, n, rhs)
                with let:
                    rhsBool = c.nextTemp()
                    rhsBoolRes = llReg(rhsBool, c.prim.i1)
                setLoc(c, andInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=rhsBoolRes, icmpPred=string("ne"), icmpLhs=rhs, icmpRhs=_zeroVal(rhs.typ)))
                with let:
                    rhsExt = c.nextTemp()
                    rhsExtRes = llReg(rhsExt, c.prim.i8_)
                emit_(c, LLInstr(kind=LLInstrKind.llZext, result=rhsExtRes, castOp=string("zext"), castSrc=rhsBoolRes, castDstType=c.prim.i8_))
                c.emitStore(rhsExtRes, llReg(resName, c.prim.ptrT))
                setLoc(c, andInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
                _ = c.startBlock(endLabel)
                result <<= c.emitLoad(llReg(resName, c.prim.ptrT), i8_)
                while n.hasMore(): skip(n)
        case LengExpr.OrC:
            with let:
                orInfo = _info(n)
                resName = c.nextTemp()
            with var:
                lhs = default(LLValue)
                rhs = default(LLValue)
            with into(n):
                with let:
                    i8_ = c.prim.i8_
                c.emitAlloca(resName, i8_)
                c.emitStore(llIntTextC(string("1"), c.prim.i8_), llReg(resName, c.prim.ptrT))
                _genExprLLVM(c, n, lhs)
                with let:
                    lhsBool = c.nextTemp()
                    lhsBoolRes = llReg(lhsBool, c.prim.i1)
                setLoc(c, orInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=lhsBoolRes, icmpPred=string("ne"), icmpLhs=lhs, icmpRhs=_zeroVal(lhs.typ)))
                with let:
                    rhsLabel = c.nextLabel()
                    endLabel = c.nextLabel()
                emit_(c, LLInstr(kind=LLInstrKind.llCondBr, condBrCond=lhsBoolRes, condBrTrue=endLabel, condBrFalse=rhsLabel))
                _ = c.startBlock(rhsLabel)
                _genExprLLVM(c, n, rhs)
                with let:
                    rhsBool = c.nextTemp()
                    rhsBoolRes = llReg(rhsBool, c.prim.i1)
                setLoc(c, orInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=rhsBoolRes, icmpPred=string("ne"), icmpLhs=rhs, icmpRhs=_zeroVal(rhs.typ)))
                with let:
                    rhsExt = c.nextTemp()
                    rhsExtRes = llReg(rhsExt, c.prim.i8_)
                emit_(c, LLInstr(kind=LLInstrKind.llZext, result=rhsExtRes, castOp=string("zext"), castSrc=rhsBoolRes, castDstType=c.prim.i8_))
                c.emitStore(rhsExtRes, llReg(resName, c.prim.ptrT))
                setLoc(c, orInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llBr, brTarget=endLabel))
                _ = c.startBlock(endLabel)
                result <<= c.emitLoad(llReg(resName, c.prim.ptrT), i8_)
                while n.hasMore(): skip(n)
        case LengExpr.NotC:
            with let:
                notInfo = _info(n)
            with var:
                val = default(LLValue)
            with into(n):
                _genExprLLVM(c, n, val)
                while n.hasMore(): skip(n)
            with let:
                t1 = c.nextTemp()
                t1Res = llReg(t1, c.prim.i1)
            setLoc(c, notInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=t1Res, icmpPred=string("eq"), icmpLhs=val, icmpRhs=_zeroVal(val.typ)))
            with let:
                t2 = c.nextTemp()
                t2Res = llReg(t2, c.prim.i8_)
            emit_(c, LLInstr(kind=LLInstrKind.llZext, result=t2Res, castOp=string("zext"), castSrc=t1Res, castDstType=c.prim.i8_))
            result <<= t2Res
        case LengExpr.CastC | LengExpr.ConvC:
            _genConvOrCast(c, n, result)
        case LengExpr.CallC:
            with let:
                retTypeCursor = getType(c._m, n)
                retType = _genTypeLLVMReadOnly(c, retTypeCursor)
            _genCallWithType(c, n, retType, result)
        case LengExpr.InstrC:
            _genInstrLLVM(c, n, result)
        case LengExpr.AddrC | LengExpr.HaddrC:
            _genAddrLLVM(c, n, result)
        case LengExpr.DerefC:
            with let:
                derefType = getType(c._m, n)
                loadType = _genTypeLLVMReadOnly(c, derefType)
            with var:
                ptrVal = default(LLValue)
            with into(n):
                _genExprLLVM(c, n, ptrVal)
                if n.hasMore() and typeQual(n) == LengTypeQualifier.CpprefQ:
                    skip(n)
                while n.hasMore(): skip(n)
            result <<= c.emitLoad(ptrVal, loadType)
        case LengExpr.AtC:
            with let:
                elemType = getType(c._m, n)
                loadType = _genTypeLLVMReadOnly(c, elemType)
            with var:
                lval = default(LLValue)
            _genAtLLVM(c, n, lval)
            result <<= c.emitLoad(lval, loadType)
        case LengExpr.PatC:
            with let:
                elemType = getType(c._m, n)
                loadType = _genTypeLLVMReadOnly(c, elemType)
            with var:
                lval = default(LLValue)
            _genPatLLVM(c, n, lval)
            result <<= c.emitLoad(lval, loadType)
        case LengExpr.DotC:
            with let:
                fldType = getType(c._m, n)
                loadType = _genTypeLLVMReadOnly(c, fldType)
            with var:
                lval = default(LLValue)
            _genDotLLVM(c, n, lval)
            if typeKind(fldType) == LengType.FlexarrayT:
                result <<= withType(lval, c.prim.ptrT)
            else:
                result <<= c.emitLoad(lval, loadType)
        case LengExpr.SizeofC:
            _genSizeofLLVM(c, n, result)
        case LengExpr.AlignofC:
            _genSizeofLLVM(c, n, result)
        case LengExpr.OffsetofC:
            with var:
                typCursor = Cursor()
                fldSym = SymId()
                typ = LLType()
            with into(n):
                typCursor = n.copy()
                typ = _genTypeLLVM(c, n)
                fldSym = symId(n)
                n.inc()
                while n.hasMore(): skip(n)
            with let:
                objBody = navigateToObjectBody(c._m, typCursor)
                fldIdx = _fieldIndex(c, objBody, fldSym)
                t1 = c.emitGEP(typ, llNull(c.prim.ptrT), [llIntTextC(string("0"), c.prim.i32_), llIntTextC(str(fldIdx), c.prim.i32_)], inbounds=False)
                t2 = c.nextTemp()
                res = llReg(t2, c.llIntBits(c._bits))
            emit_(c, LLInstr(kind=LLInstrKind.llPtrtoint, result=res, castOp=string("ptrtoint"), castSrc=t1, castDstType=c.llIntBits(c._bits)))
            result <<= res
        case LengExpr.ParC:
            with into(n):
                _genExprLLVM(c, n, result)
                while n.hasMore(): skip(n)
        case LengExpr.SufC:
            with var:
                value = Cursor()
                suffix = Cursor()
                suffixStr = string()
            with into(n):
                value = n.copy()
                skip(n)
                suffix = n
                suffixStr = c._m.pool.strings[_litId(suffix)].copy()
                while n.hasMore(): skip(n)
            if kind(value) == NifKind.StrLit:
                _genExprLLVM(c, value, result)
            else:
                with var:
                    val = default(LLValue)
                _genExprLLVM(c, value, val)
                with var:
                    targetTyp = c.prim.i64_
                match suffixStr:
                    case "i64" | "u64": targetTyp = c.prim.i64_
                    case "i32" | "u32": targetTyp = c.prim.i32_
                    case "i16" | "u16": targetTyp = c.prim.i16_
                    case "i8" | "u8": targetTyp = c.prim.i8_
                    case "f64": targetTyp = c.prim.f64_
                    case "f32": targetTyp = c.prim.f32_
                    case _: pass
                if typeEq(val.typ, targetTyp):
                    result <<= val
                else:
                    with let:
                        t = c.nextTemp()
                        res = llReg(t, targetTyp)
                    if _isFloatType(targetTyp):
                        # Pick the opcode by the source value's kind: float→float
                        # narrows/widens (fptrunc/fpext), int→float is sitofp.
                        with let:
                            srcIsFloat = _isFloatType(val.typ)
                        if srcIsFloat and val.typ.floatBits > targetTyp.floatBits:
                            emit_(c, LLInstr(kind=LLInstrKind.llFptrunc, result=res, castOp=string("fptrunc"), castSrc=val, castDstType=targetTyp))
                        elif srcIsFloat:
                            emit_(c, LLInstr(kind=LLInstrKind.llFpext, result=res, castOp=string("fpext"), castSrc=val, castDstType=targetTyp))
                        else:
                            emit_(c, LLInstr(kind=LLInstrKind.llSitofp, result=res, castOp=string("sitofp"), castSrc=val, castDstType=targetTyp))
                    else:
                        with let:
                            match suffixStr:
                                case "i8" | "u8": destBits = 8
                                case "i16" | "u16": destBits = 16
                                case "i32" | "u32": destBits = 32
                                case _: destBits = 64
                        if c._bits < destBits:
                            emit_(c, LLInstr(kind=LLInstrKind.llSext, result=res, castOp=string("sext"), castSrc=val, castDstType=targetTyp))
                        elif c._bits > destBits:
                            emit_(c, LLInstr(kind=LLInstrKind.llTrunc, result=res, castOp=string("trunc"), castSrc=val, castDstType=targetTyp))
                        else:
                            result <<= val
                            return
                    result <<= res
        case LengExpr.OconstrC:
            with var:
                objTypeCursor = Cursor()
                typ = LLType()
                tmpName = string()
            with into(n):
                objTypeCursor = n.copy()
                typ = _genTypeLLVM(c, n)
                tmpName = c.nextTemp()
                c.emitAlloca(tmpName, typ)
                c.emitStore(llZeroInit(typ), llReg(tmpName, c.prim.ptrT))
                while n.hasMore():
                    if substructureKind(n) == LengOther.KvU:
                        with into(n):
                            with let:
                                fldSym = symId(n)
                            skip(n)
                            with let:
                                srcType = getType(c._m, n)
                            with var:
                                fieldVal = default(LLValue)
                            _genExprLLVM(c, n, fieldVal)
                            with let:
                                inhDepth = stmtlist(d := nint(intVal(n)), skip(n), d) if n.hasMore() and kind(n) == NifKind.IntLit else 0
                            with var:
                                curType = objTypeCursor
                                curBody = navigateToObjectBody(c._m, curType)
                                gepType = _genTypeLLVMReadOnly(c, curType)
                                gepTarget = llReg(tmpName, c.prim.ptrT)
                            for i in range(inhDepth):
                                gepTarget = c.emitGEP(gepType, gepTarget, [llIntTextC(string("0"), c.prim.i32_), llIntTextC(string("0"), c.prim.i32_)])
                                with let:
                                    baseTypeCursor = baseTypeOfObject(c._m, curBody)
                                if not baseTypeCursor.cursorIsNil():
                                    curType = baseTypeCursor
                                    curBody = navigateToObjectBody(c._m, curType)
                                    gepType = _genTypeLLVMReadOnly(c, curType)
                            with let:
                                fldPtr = _genFieldPtrLLVM(c, curBody, fldSym, gepType, gepTarget)
                                fldType = typeOfField(c._m, curBody, fldSym)
                            _coerceInPlace(c, fieldVal, srcType, fldType)
                            c.emitStore(fieldVal, fldPtr)
                            while n.hasMore(): skip(n)
                    else:
                        with var:
                            baseVal = default(LLValue)
                        _genExprLLVM(c, n, baseVal)
                        with let:
                            basePtr = c.emitGEP(typ, llReg(tmpName, c.prim.ptrT), [llIntTextC(string("0"), c.prim.i32_), llIntTextC(string("0"), c.prim.i32_)])
                        c.emitStore(baseVal, basePtr)
                result <<= c.emitLoad(llReg(tmpName, c.prim.ptrT), typ)
        case LengExpr.AconstrC:
            with var:
                arrayTypeCursor = Cursor()
                typ = LLType()
                expectedLen = nint()
            with into(n):
                arrayTypeCursor = n.copy()
                typ = _genTypeLLVM(c, n)
                expectedLen = _fixedArrayLen(c, arrayTypeCursor)
                with var:
                    elemBody = navigateToObjectBody(c._m, arrayTypeCursor)
                elemBody.inc()
                with let:
                    elemTyp = _genTypeLLVMReadOnly(c, elemBody)
                with var:
                    current = llUndef(typ)
                    idx = nint(0)
                while n.hasMore():
                    with var:
                        elemVal = default(LLValue)
                    _genExprLLVM(c, n, elemVal)
                    if elemVal.kind == LLValueKind.llvInt:
                        elemVal.typ = elemTyp
                    with let:
                        t = c.nextTemp()
                        res = llReg(t, typ)
                    emit_(c, LLInstr(kind=LLInstrKind.llInsertValue, result=res, ivAggregate=current, ivElement=elemVal, ivAggType=typ, ivIndex=idx))
                    current = res
                    idx += 1
                if expectedLen >= 0 and idx != expectedLen:
                    _error(c._m, string("array literal element count does not match its declared length: "), arrayTypeCursor)
                result <<= current
        case LengExpr.BaseobjC:
            with let:
                loadType = _genTypeLLVMReadOnly(c, getType(c._m, n))
            with var:
                lval = default(LLValue)
            _genLvalueLLVM(c, n, lval)
            result <<= c.emitLoad(lval, loadType)
        case LengExpr.ErrvC | LengExpr.OvfC:
            with var:
                lval = default(LLValue)
            _genLvalueLLVM(c, n, lval)
            with let:
                i8_ = c.prim.i8_
            result <<= c.emitLoad(lval, i8_)


def _genCondLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    with let:
        condInfo = _info(n)
    _genExprLLVM(c, n, result)
    if result.typ == c.prim.i1:
        return
    with let:
        t = c.nextTemp()
        res = llReg(t, c.prim.i1)
    setLoc(c, condInfo)
    emit_(c, LLInstr(kind=LLInstrKind.llIcmp, result=res, icmpPred=string("ne"), icmpLhs=result, icmpRhs=_zeroVal(result.typ)))
    result <<= res
