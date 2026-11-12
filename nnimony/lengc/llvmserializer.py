# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/llvmserializer.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## LLVM IR serializer: turns the structured `LLModule` into `.ll` text.
##
## This is the *only* place that knows how LLVM IR is spelled. Because
## `LLValue` is a tagged union, value rendering switches on `kind` and never
## inspects string prefixes.

from __future__ import annotations
from nimic.ntypes import *
from .llvmirmodel import (
    LLAtomicOrdering, LLAtomicrmwOp, LLBlock, LLExternDecl, LLFunc, LLGlobal, LLInstr, LLInstrKind, LLModule,
    LLNamedType, LLType, LLTypeKind, LLValue, LLValueKind)


def _floatBinOpName(binOp: string) -> string:
    match binOp:
        case "add": return string("fadd")
        case "sub": return string("fsub")
        case "mul": return string("fmul")
        case "sdiv" | "udiv": return string("fdiv")
        case "srem" | "urem": return string("frem")
        case _: return binOp.copy()


with const:
    OrderingStr = array[LLAtomicOrdering, string]([string("unordered"), string("monotonic"), string("acquire"), string("release"), string("acq_rel"), string("seq_cst")])

with const:
    RmwOpStr = array[LLAtomicrmwOp, string]([string("xchg"), string("add"), string("sub"), string("and"), string("or"), string("xor"), string("nand"), string("min"), string("max"), string("umin"), string("umax")])


@dispatch
def serialize(typ: LLType, result: mut @ string):
    ## Append the LLVM type string to `result`. Uses `var string` to avoid
    ## exponential allocation when serializing nested pointer/array/struct types.
    if typ is None:
        result.add(string("ptr"))  # treat nil pointee as opaque ptr
    match typ.kind:
        case LLTypeKind.llVoid: result.add(string("void"))
        case LLTypeKind.llInt: result.add(string("i") + str(typ.intBits))
        case LLTypeKind.llFloat:
            match typ.floatBits:
                case 32: result.add(string("float"))
                case 64: result.add(string("double"))
                case 128: result.add(string("fp128"))
                case _: result.add(string("double"))
        case LLTypeKind.llPtr: result.add(string("ptr"))
        case LLTypeKind.llArray:
            result.add(string("[") + str(typ.arrLen) + string(" x "))
            serialize(typ.arrElem, result)
            result.add(string("]"))
        case LLTypeKind.llStruct:
            if typ.name.len > 0:
                result.add(string("%") + typ.name)
            else:
                result.add(string("{ "))
                for i in range(typ.structFields.len):
                    with let:
                        f = typ.structFields[i]
                    if i > 0: result.add(string(", "))
                    serialize(f.typ, result)
                result.add(string(" }"))
        case LLTypeKind.llUnion: serialize(typ.repType, result)
        case LLTypeKind.llFunc: result.add(string("ptr"))


@dispatch
def serialize(typ: LLType) -> string:
    ## Convenience overload. Prefer `serialize(typ, result)` when building into an
    ## existing string to avoid an extra allocation.
    result = string("")
    serialize(typ, result)
    return result


def appendParamList(params: openArray[LLType], isVarargs: bool, result: mut @ string):
    ## Append a parameter-type list `(t1, t2, ...)` — the shared spelling behind
    ## `declare` lines and varargs call annotations.
    result.add(string("("))
    for i, p in pairs(params):
        if i > 0: result.add(string(", "))
        serialize(p, result)
    if isVarargs:
        if params.len > 0: result.add(string(", "))
        result.add(string("..."))
    result.add(string(")"))


def serializeNamedTypeDef(nt: LLNamedType, result: mut @ string):
    ## Render `%Name = type <body>` (or `= type opaque` for forward refs). The
    ## only place that spells named-type-definition syntax.
    result.add(string("%") + nt.name + string(" = type "))
    if nt.body is None:
        result.add(string("opaque"))
    elif nt.body.kind == LLTypeKind.llFunc:
        # function-pointer type definition: `ret (params)*`
        serialize(nt.body.funcRetType, result)
        result.add(string(" ("))
        for i in range(nt.body.funcParamTypes.len):
            with let:
                p = nt.body.funcParamTypes[i]
            if i > 0: result.add(string(", "))
            serialize(p, result)
        result.add(string(")*"))
    else:
        with var:
            bodyStr = string("")
        serialize(nt.body, bodyStr)
        if nt.packed: result.add(string("<") + bodyStr + string(">"))
        else: result.add(bodyStr)
    result.add(string("\n"))


def serializeUnqualified(v: LLValue, result: mut @ string):
    ## Append the bare value text WITHOUT its type prefix.
    match v.kind:
        case LLValueKind.llvReg: result.add(string("%") + v.regName)
        case LLValueKind.llvInt: result.add(v.intText)
        case LLValueKind.llvFloat: result.add(v.floatText)
        case LLValueKind.llvBool: result.add((string("1") if v.boolVal else string("0")))
        case LLValueKind.llvGlobal: result.add(string("@") + v.globalName)
        case LLValueKind.llvNull: result.add(string("null"))
        case LLValueKind.llvUndef: result.add(string("undef"))
        case LLValueKind.llvZero: result.add(string("zeroinitializer"))
        case LLValueKind.llvPoison: result.add(string("poison"))
        case LLValueKind.llvCString: result.add(string("c\"") + v.strVal + string("\""))
        case LLValueKind.llvRawText: result.add(v.rawText)
        case LLValueKind.llvNone: pass


def operand(v: LLValue, result: mut @ string):
    ## Append typed operand: "<type> <value>".
    if v.kind == LLValueKind.llvNone: return
    serialize(v.typ, result)
    result.add(string(" "))
    serializeUnqualified(v, result)


def _resultPrefix(i: LLInstr, result: mut @ string):
    if i.result.kind != LLValueKind.llvNone:
        result.add(string("%") + i.result.regName + string(" = "))


@dispatch
def serialize(i: LLInstr, result: mut @ string):
    ## Append a single instruction WITHOUT leading indentation or trailing
    ## newline. The caller adds those.
    match i.kind:
        case LLInstrKind.llBinOp:
            _resultPrefix(i, result)
            with let:
                isFloat = i.binLhs.typ is not None and i.binLhs.typ.kind == LLTypeKind.llFloat
            result.add((_floatBinOpName(i.binOp) if isFloat else i.binOp))
            if not isFloat:
                if i.binNuw: result.add(string(" nuw"))
                if i.binNsw: result.add(string(" nsw"))
            result.add(string(" "))
            operand(i.binLhs, result)
            result.add(string(", "))
            serializeUnqualified(i.binRhs, result)
        case LLInstrKind.llIcmp:
            _resultPrefix(i, result)
            result.add(string("icmp ") + i.icmpPred + string(" "))
            operand(i.icmpLhs, result)
            result.add(string(", "))
            serializeUnqualified(i.icmpRhs, result)
        case LLInstrKind.llFcmp:
            _resultPrefix(i, result)
            result.add(string("fcmp ") + i.fcmpPred + string(" "))
            operand(i.fcmpLhs, result)
            result.add(string(", "))
            serializeUnqualified(i.fcmpRhs, result)
        case LLInstrKind.llZext | LLInstrKind.llSext | LLInstrKind.llTrunc | LLInstrKind.llFpext | LLInstrKind.llFptrunc | LLInstrKind.llSitofp | LLInstrKind.llUitofp | LLInstrKind.llFptosi | LLInstrKind.llFptoui | LLInstrKind.llBitcast | LLInstrKind.llInttoptr | LLInstrKind.llPtrtoint:
            _resultPrefix(i, result)
            result.add(i.castOp + string(" "))
            operand(i.castSrc, result)
            result.add(string(" to "))
            serialize(i.castDstType, result)
        case LLInstrKind.llAlloca:
            _resultPrefix(i, result)
            result.add(string("alloca "))
            serialize(i.allocaType, result)
            if i.allocaNumElts.kind != LLValueKind.llvNone:
                result.add(string(", "))
                serialize(i.allocaType, result)
                result.add(string(" "))
                serializeUnqualified(i.allocaNumElts, result)
            if i.allocaAlign > 0:
                result.add(string(", align ") + str(i.allocaAlign))
        case LLInstrKind.llLoad:
            _resultPrefix(i, result)
            result.add(string("load"))
            if i.loadAtomic: result.add(string(" atomic"))
            result.add(string(" "))
            serialize(i.result.typ, result)
            result.add(string(", ptr "))
            serializeUnqualified(i.loadPtr, result)
            if i.loadAtomic:
                result.add(string(" ") + OrderingStr[i.loadOrdering])
                if i.loadAlign > 0: result.add(string(", align ") + str(i.loadAlign))
        case LLInstrKind.llStore:
            result.add(string("store"))
            if i.storeAtomic: result.add(string(" atomic"))
            result.add(string(" "))
            operand(i.storeValue, result)
            result.add(string(", ptr "))
            serializeUnqualified(i.storePtr, result)
            if i.storeAtomic:
                result.add(string(" ") + OrderingStr[i.storeOrdering])
                if i.storeAlign > 0: result.add(string(", align ") + str(i.storeAlign))
        case LLInstrKind.llGep:
            _resultPrefix(i, result)
            result.add(string("getelementptr "))
            if i.gepInbounds: result.add(string("inbounds "))
            serialize(i.gepBaseType, result)
            result.add(string(", ptr "))
            serializeUnqualified(i.gepBase, result)
            for idx in i.gepIndices:
                result.add(string(", "))
                operand(idx, result)
        case LLInstrKind.llCall:
            if i.result.kind != LLValueKind.llvNone:
                result.add(string("%") + i.result.regName + string(" = "))
            result.add(string("call "))
            serialize(i.callRetType, result)
            if i.callCallee.typ is not None and i.callCallee.typ.kind == LLTypeKind.llFunc and i.callCallee.typ.funcIsVarargs:
                result.add(string(" "))
                appendParamList(i.callCallee.typ.funcParamTypes, i.callCallee.typ.funcIsVarargs, result)
            result.add(string(" "))
            serializeUnqualified(i.callCallee, result)
            result.add(string("("))
            for j, a in pairs(i.callArgs):
                if j > 0: result.add(string(", "))
                operand(a, result)
            result.add(string(")"))
        case LLInstrKind.llExtractValue:
            _resultPrefix(i, result)
            result.add(string("extractvalue "))
            serialize(i.evAggType, result)
            result.add(string(" "))
            serializeUnqualified(i.evAggregate, result)
            result.add(string(", ") + str(i.evIndex))
        case LLInstrKind.llInsertValue:
            _resultPrefix(i, result)
            result.add(string("insertvalue "))
            serialize(i.ivAggType, result)
            result.add(string(" "))
            serializeUnqualified(i.ivAggregate, result)
            result.add(string(", "))
            operand(i.ivElement, result)
            result.add(string(", ") + str(i.ivIndex))
        case LLInstrKind.llPhi:
            _resultPrefix(i, result)
            result.add(string("phi "))
            serialize(i.result.typ, result)
            for j, (val, label) in pairs(i.phiIncoming):
                if j > 0: result.add(string(", "))
                result.add(string(" [ "))
                serializeUnqualified(val, result)
                result.add(string(", %") + label + string(" ]"))
        case LLInstrKind.llSelect:
            _resultPrefix(i, result)
            result.add(string("select i1 "))
            serializeUnqualified(i.selCond, result)
            result.add(string(", "))
            operand(i.selTrue, result)
            result.add(string(", "))
            operand(i.selFalse, result)
        case LLInstrKind.llFneg:
            _resultPrefix(i, result)
            result.add(string("fneg "))
            operand(i.fnegVal, result)
        case LLInstrKind.llRet:
            result.add(string("ret"))
            if i.retVal.kind == LLValueKind.llvNone:
                result.add(string(" void"))
            else:
                result.add(string(" "))
                operand(i.retVal, result)
        case LLInstrKind.llBr:
            result.add(string("br label %") + i.brTarget)
        case LLInstrKind.llCondBr:
            result.add(string("br i1 "))
            serializeUnqualified(i.condBrCond, result)
            result.add(string(", label %") + i.condBrTrue + string(", label %") + i.condBrFalse)
        case LLInstrKind.llSwitch:
            result.add(string("switch "))
            serialize(i.switchValType, result)
            result.add(string(" "))
            serializeUnqualified(i.switchVal, result)
            result.add(string(", label %") + i.switchDefault)
            result.add(string(" [\n"))
            for (cv, label) in i.switchCases:
                result.add(string("    "))
                serialize(i.switchValType, result)
                result.add(string(" "))
                serializeUnqualified(cv, result)
                result.add(string(", label %") + label + string("\n"))
            result.add(string("  ]"))
        case LLInstrKind.llUnreachable:
            result.add(string("unreachable"))
        case LLInstrKind.llAtomicrmw:
            _resultPrefix(i, result)
            result.add(string("atomicrmw ") + RmwOpStr[i.armwOp])
            if i.armwSyncscope.len > 0:
                result.add(string(" syncscope(\"") + i.armwSyncscope + string("\")"))
            result.add(string(" ptr "))
            serializeUnqualified(i.armwPtr, result)
            result.add(string(", "))
            operand(i.armwVal, result)
            result.add(string(" ") + OrderingStr[i.armwOrdering])
            if i.armwAlign > 0: result.add(string(", align ") + str(i.armwAlign))
        case LLInstrKind.llCmpxchg:
            _resultPrefix(i, result)
            result.add(string("cmpxchg"))
            if i.cxSyncscope.len > 0:
                result.add(string(" syncscope(\"") + i.cxSyncscope + string("\")"))
            result.add(string(" ptr "))
            serializeUnqualified(i.cxPtr, result)
            result.add(string(", "))
            operand(i.cxExpected, result)
            result.add(string(", "))
            operand(i.cxDesired, result)
            result.add(string(" ") + OrderingStr[i.cxSuccessOrdering])
            result.add(string(" ") + OrderingStr[i.cxFailureOrdering])
            if i.cxWeak: result.add(string(" weak"))
            if i.cxAlign > 0: result.add(string(", align ") + str(i.cxAlign))
        case LLInstrKind.llFence:
            result.add(string("fence"))
            if i.fenceSyncscope.len > 0:
                result.add(string(" syncscope(\"") + i.fenceSyncscope + string("\")"))
            result.add(string(" ") + OrderingStr[i.fenceOrdering])
        case LLInstrKind.llRaw:
            result.add(i.rawText)


@dispatch
def serialize(blk: LLBlock, result: mut @ string):
    result.add(blk.label + string(":\n"))
    for instr in blk.instrs:
        result.add(string("  "))
        serialize(instr, result)
        if instr.kind != LLInstrKind.llRaw:
            result.add(instr.dbgLoc)
        result.add(string("\n"))


def _paramText(f: LLFunc, result: mut @ string):
    for i, (name, typ) in pairs(f.params):
        if i > 0: result.add(string(", "))
        serialize(typ, result)
        result.add(string(" %") + name + string(".param"))
    if f.isVarargs:
        if f.params.len > 0: result.add(string(", "))
        result.add(string("..."))


@dispatch
def serialize(f: LLFunc, result: mut @ string):
    result.add(string("define "))
    serialize(f.retType, result)
    result.add(string(" @") + f.name + string("("))
    _paramText(f, result)
    result.add(string(")"))
    if f.alwaysInline: result.add(string(" alwaysinline"))
    if f.noInline: result.add(string(" noinline"))
    if f.metadata.subprogramId != 0:
        result.add(string(" !dbg !") + str(f.metadata.subprogramId))
    result.add(string(" {\n"))
    for i, blk in pairs(f.blocks):
        if i == 0:
            result.add(blk.label + string(":\n"))
            for a in f.entryAllocas:
                result.add(string("  "))
                serialize(a, result)
                result.add(a.dbgLoc)
                result.add(string("\n"))
            for instr in blk.instrs:
                result.add(string("  "))
                serialize(instr, result)
                if instr.kind != LLInstrKind.llRaw:
                    result.add(instr.dbgLoc)
                result.add(string("\n"))
        else:
            serialize(blk, result)
    result.add(string("}\n"))


@dispatch
def serialize(g: LLGlobal, result: mut @ string):
    result.add(string("@") + g.name + string(" = "))
    if g.isPrivate: result.add(string("private "))
    if g.isExternal:
        result.add(string("external "))
        if g.isThreadLocal: result.add(string("thread_local "))
        result.add(string("global "))
        serialize(g.typ, result)
    else:
        if g.isThreadLocal: result.add(string("thread_local "))
        result.add((string("constant ") if g.isConstant else string("global ")))
        serialize(g.typ, result)
        result.add(string(" "))
        serializeUnqualified(g.initVal, result)
    if g.align > 0: result.add(string(", align ") + str(g.align))
    if g.dbgLoc.len > 0: result.add(g.dbgLoc)


def serializeExtern(e: LLExternDecl, result: mut @ string):
    ## Append a `declare` line. Builtins whose attributes (nocapture/immarg/...)
    ## don't fit the structured form carry a verbatim `raw` line.
    if e.raw.len > 0:
        result.add(e.raw)
    else:
        result.add(string("declare "))
        serialize(e.retType, result)
        result.add(string(" @") + e.name)
        appendParamList(e.params, e.isVarargs, result)


# We use the normal ABI from platforms, so we don't need a datalayout, LLVM infers this info from the triple
with const:
    _TargetTriple = string("x86_64-pc-linux-gnu") if comptime(defined("linux") and defined("amd64")) else string("aarch64-unknown-linux-gnu") if comptime(defined("linux") and defined("arm64")) else string("arm64-apple-macosx") if comptime(defined("macosx") and defined("arm64")) else string("x86_64-apple-macosx") if comptime(defined("macosx") and defined("amd64")) else string("x86_64-w64-windows-gnu") if comptime(defined("windows") and defined("amd64")) else string("")


def serializeModule(llmod: LLModule) -> string:
    ## Render the whole `.ll` module — the single owner of top-level structure
    ## (header, target, section ordering, metadata emission). Codegen builds the
    ## `LLModule` and hands it here.
    result = string("; LLVM IR generated by Lengc\n")
    if _TargetTriple.len > 0:
        result.add(string("target triple = \"") + _TargetTriple + string("\"\n"))
    else:
        result.add(string("; target triple should be set for your platform\n"))
    result.add(string("\n"))

    for td in llmod.typeDefs:
        serializeNamedTypeDef(td, result)
    if llmod.typeDefs.len > 0: result.add(string("\n"))

    for e in llmod.externs:
        serializeExtern(e, result)
        result.add(string("\n"))
    if llmod.externs.len > 0: result.add(string("\n"))

    for g in llmod.globals:
        serialize(g, result)
        result.add(string("\n"))
    if llmod.globals.len > 0: result.add(string("\n"))

    for fn in llmod.funcs:
        serialize(fn, result)
        result.add(string("\n\n"))

    if llmod.hasInitBody:
        serialize(llmod.initFunc, result)
        result.add(string("\n"))
        result.add(string("@llvm.global_ctors = appending global [1 x { i32, ptr, ptr }] [{ i32, ptr, ptr } { i32 65535, ptr @lengc_init, ptr null }]\n"))

    if llmod.metadata.len > 0:
        result.add(string("\n"))
        result.add(string("!llvm.dbg.cu = !{!") + str(llmod.cuId) + string("}\n"))
        result.add(string("!llvm.module.flags = !{!") + str(llmod.dwarfVerId) + string(", !") + str(llmod.diVerId) + string("}\n"))
        for i, md in pairs(llmod.metadata):
            result.add(string("!") + str(i) + string(" = ") + md + string("\n"))
    return result
