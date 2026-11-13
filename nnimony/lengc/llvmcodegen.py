# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/llvmcodegen.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

# We produce LLVM IR via a structured model (llvmirmodel.nim) which a
# serializer (llvmserializer.nim) renders to .ll text. All LLVM syntax
# knowledge lives in the serializer.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    # See llvmirmodel.nim: a nil `LLType` means "no type here"; the generators
    # (all `include`d into this module) rely on that throughout.
    pragma("feature: \"lenientnils\"")

from nimic.std import assertions, formatfloat, sequtils
from nimic.std.syncio import writeLine
from nimic.std.sets import HashSet
from nimic.std.strutils import parseInt
from nimic.std.tables import Table
importFrom("nimic.std.os", "changeFileExt", "splitFile", "extractFilename", "fileExists", "getCurrentDir", "absolutePath")
from ..lib.vfs import vfsWrite

from ..lib import nifcoreparse
from ..lib.nifcoreparse import (
    addSubtree, charLit, childCursor, createTokenBuf, CrucialOrigin, crucialOrigins, Cursor, FileId, floatVal,
    intVal, isCrucialFile, isValid, kind, NifKind, NifLineInfo, pool, realFile, StrId, strId, strVal, SymId,
    symId, tags, uintVal)  # re-exports nifcore
from ..lib.nifcdecl import (
    asTypeDecl, asUnionBranch, CallConv, callConvKind, exprKind, FieldDecl, into, isUnionBranch, LengExpr,
    LengOther, LengPragma, LengStmt, LengSym, LengType, LengTypeQualifier, loopInto, pragmaKind, skip,
    stmtKind, substructureKind, symKind, takeFieldDecl, takeParamDecl, takeProcDecl, takeProcType,
    takeVarDecl, typeKind, typeQual, UnionBranch)  # leng_model replacement
from .mangler import mangleToC
from .noptions import State
from ..lib.symparser import extractBasename
from . import typenav, nifmodules
from .typenav import (
    cBuiltinFor, createIntegralType, getNominalType, getType, intrinsicOfCallee, IntrinsicOp,
    navigateToObjectBody, typeOfField)
from .nifmodules import getDeclOrNil, MainModule
from . import llvmirmodel, llvmserializer
from .llvmirmodel import (
    LLAtomicOrdering, LLAtomicrmwOp, LLBlock, llDefaultZero, LLExternDecl, llFloatText, LLFunc, LLGlobal,
    llGlobalRef, LLInstr, LLInstrKind, llIntText, LLModule, LLNamedType, llNoneVal, llNull, llReg,
    LLStructField, LLType, LLTypeKind, llUndef, LLValue, LLValueKind, llZeroInit, newLLArrayType,
    newLLBinInstr, newLLFloatType, newLLFuncType, newLLIntType, newLLPtrType, newLLStructType, newLLVoidType)
from .llvmserializer import operand, serialize, serializeModule, serializeUnqualified
load = overloads(nifcoreparse.load, nifmodules.load)  # nifcore MainModule + getType (local)


# nifcore compatibility shims (see shoggoth/codegen.nim for rationale).
def _litId(c: Cursor) -> StrId:
    """{.inline.}"""
    return strId(c)


def _info(c: Cursor) -> NifLineInfo:
    """{.inline.}"""
    return c.rawLineInfo()


def _firstSon(c: Cursor) -> Cursor:
    """{.inline.}"""
    result = c.copy()
    result.inc()
    return result


def _toString(c: Cursor, spaces: bool) -> string:
    with var:
        buf = createTokenBuf(8, pool(c), tags(c))
    addSubtree(buf, c)
    result = nifcoreparse.toString(buf)
    return result


with const:
    InitFuncIdx = -1


class LLVMGenFlag(NIntEnum):
    gfMainModule = auto()


class LLVMCurrentProc(Object):
    funcIdx: nint  # index into module.funcs (InitFuncIdx for init func)
    dbgLoc: string  # current debug location for next instruction
    needsTerminator: bool
    breakStack: seq[string]  # loop-end labels for `break`
    vflags: HashSet[SymId]
    retType: LLType
    retTypeCursor: Cursor
    spName: string
    spLine: nint
    spScopeLine: nint
    subprogramId: nint
    subprogramFileId: nint
    retainedNodes: seq[nint]
    frameStack: seq[CrucialOrigin]  # active template expansions, outermost first;
                                    # pushed when the walk enters a node whose
                                    # head info carries a forged filename


class DebugInfo(Object):
    nextMetadataId: nint
    metadata: seq[string]  # accumulated metadata nodes
    fileIds: Table[nint, nint]  # FileId (as int) -> DIFile metadata id
    cuId: nint  # DICompileUnit metadata id
    diTypeCache: Table[SymId, nint]  # SymId -> DIType metadata id
    diBasicTypeCache: Table[string, nint]  # "i32"/"float"/… -> DIBasicType id
    compositeTypeDone: HashSet[SymId]  # symIds with fully built DICompositeType
    globalExprs: seq[nint]  # DIGlobalVariableExpression IDs for DICompileUnit globals
    fileIdsByName: Table[string, nint]  # source path -> DIFile meta
    inlineSpCache: Table[string, nint]  # expanded routine (mangled) -> spId
    nullSigId: nint  # shared `!DISubroutineType(types: !{null})` for template SPs


class PrimTypes(Object):
    voidT: LLType
    i1: LLType
    i8_: LLType
    i16_: LLType
    i32_: LLType
    i64_: LLType
    ptrT: LLType
    f32_: LLType
    f64_: LLType


class LLVMCode(Object):
    _m: MainModule
    module: LLModule
    currentBlockIdx: nint
    nextTempCounter: nint
    nextLabelCounter: nint
    prim: PrimTypes
    _bits: nint
    _flags: Tset[LLVMGenFlag]
    requestedSyms: HashSet[SymId]
    declaredExterns: HashSet[string]  # to avoid duplicate extern declarations
    emittedConsts: HashSet[SymId]  # local consts emitted as global constants
    _inToplevel: bool
    _currentProc: LLVMCurrentProc
    strLitCounter: nint  # global counter for string literal names
    debug: DebugInfo

    def llIntBits(c: LLVMCode, n: nint) -> LLType:
        match n:
            case 1: return c.prim.i1
            case 8: return c.prim.i8_
            case 16: return c.prim.i16_
            case 32: return c.prim.i32_
            case 64: return c.prim.i64_
            case _: return newLLIntType(n)

    def _pushExpansionFrames(c: mut @ LLVMCode, info: NifLineInfo) -> nint:
        ## Enter the template expansions named by `info`'s filename, if it is a
        ## forged one, and return how many levels were pushed so the caller can pop
        ## exactly that many. Zero for ordinary code, which is the common case.
        ##
        ## The frame is a property of a *region* of the tree, not of one token: the
        ## front end marks only the head of an expansion (see
        ## `templates.forgeExpansionInfo`), and everything the walk reaches while
        ## that head is open belongs to the same expansion. Instructions lowered
        ## from inside it therefore get the frame even though their own tokens carry
        ## plain line info.
        result = 0
        if not info.isValid() or not isValid(info.file): return result
        with let:
            fname = c._m.pool.filenames[info.file]
        if not isCrucialFile(fname): return result
        for origin in crucialOrigins(fname):
            c._currentProc.frameStack.add(origin)
            result += 1
        return result

    def _popExpansionFrames(c: mut @ LLVMCode, n: nint):
        """{.inline.}"""
        for i in range(n): _ = c._currentProc.frameStack.pop()

    @template
    def _withExpansionFrames(c: mut @ LLVMCode, info: NifLineInfo, body: untyped):
        ## Run `body` with `info`'s expansion frames active. The pop is unconditional
        ## rather than in a `finally`: the generator quits the process on error, so
        ## there is no unwinding path to protect against.
        with let:
            pushed = c._pushExpansionFrames(info)
        body
        c._popExpansionFrames(pushed)

    def _funcByIndex(c: mut @ LLVMCode, idx: nint) -> mut @ LLFunc:
        """{.inline.}"""
        if idx == InitFuncIdx:
            result = c.module.initFunc
        else:
            result = c.module.funcs[idx]
        return result

    @template
    def _currentFunc(c: mut @ LLVMCode) -> mut @ LLFunc:
        return c._funcByIndex(c._currentProc.funcIdx)

    @template
    def _currentBlock(c: mut @ LLVMCode) -> mut @ LLBlock:
        return c._currentFunc().blocks[c.currentBlockIdx]

    def nextTemp(c: mut @ LLVMCode) -> string:
        """{.inline.}"""
        result = string("t") + str(c.nextTempCounter)
        c.nextTempCounter += 1
        return result

    def nextLabel(c: mut @ LLVMCode) -> string:
        """{.inline.}"""
        result = string("L") + str(c.nextLabelCounter)
        c.nextLabelCounter += 1
        return result

    def newBlock(c: mut @ LLVMCode, label: string) -> nint:
        """{.inline.}"""
        ## Append a new block to the current function, return its index.
        c._currentFunc().blocks.add(LLBlock(label=label))
        result = c._currentFunc().blocks.high
        return result

    def switchToBlock(c: mut @ LLVMCode, idx: nint):
        """{.inline.}"""
        c.currentBlockIdx = idx

    def startBlock(c: mut @ LLVMCode, label: string) -> nint:
        """{.inline.}"""
        ## Create a new block, switch to it, reset terminator state. Returns index.
        result = c.newBlock(label)
        c.currentBlockIdx = result
        c._currentProc.needsTerminator = False
        return result

    def emitRaw(c: mut @ LLVMCode, text: string):
        with var:
            instr = LLInstr(kind=LLInstrKind.llRaw, rawText=text)
        instr.dbgLoc = c._currentProc.dbgLoc
        c._currentBlock().instrs.add(instr)

    def emitAlloca(c: mut @ LLVMCode, name: string, typ: LLType, align: int64 = 0):
        with var:
            instr = LLInstr(kind=LLInstrKind.llAlloca, result=llReg(name, c.prim.ptrT), allocaType=typ, allocaAlign=nint(align))
        c._currentFunc().entryAllocas.add(instr)

    def _mangleSym(c: mut @ LLVMCode, s: SymId) -> string:
        ## extern name if declared, else mangleToC. Shared-SymId locals (inlined copies
        ## of one source var) are dedup'd at the alloca site, not here.
        with let:
            x = getDeclOrNil(c._m, s)
        if not isNil(x) and x.extern != StrId(0):
            result = c._m.pool.strings[x.extern].copy()
        else:
            result = mangleToC(c._m.pool.symString(s))
        return result

    def nifSymBaseName(c: mut @ LLVMCode, symId: SymId) -> string:
        ## Extract the original Nim identifier from a NIF symbol like
        ## ``myVar.0.module`` → ``myVar``.
        result = c._m.pool.symBasename(symId)
        if result.len == 0:
            result = c._m.pool.symString(symId)
        return result


def initPrimTypes() -> PrimTypes:
    result = default(PrimTypes)
    result.voidT = newLLVoidType()
    result.i1 = newLLIntType(1)
    result.i8_ = newLLIntType(8)
    result.i16_ = newLLIntType(16)
    result.i32_ = newLLIntType(32)
    result.i64_ = newLLIntType(64)
    result.ptrT = newLLPtrType()
    result.f32_ = newLLFloatType(32)
    result.f64_ = newLLFloatType(64)
    return result


def initLLVMCode(m: sink @ MainModule, flags: Tset[LLVMGenFlag], bits: nint) -> LLVMCode:
    result = LLVMCode(_m=m, _flags=flags, _bits=bits, _inToplevel=True, prim=initPrimTypes())
    return result


def _errorAt(m: MainModule, msg: string, n: Cursor):
    """{.noreturn.}"""
    ## `error` without the trailing render of `n`, for a message that already names
    ## what is wrong in prose (the render would append the raw mangled symbol).
    with let:
        info = n.rawLineInfo()
    if info.isValid():
        write(stdout, realFile(m.pool.filenames[info.file]))
        write(stdout, string("(") + str(info.line) + string(", ") + str(info.col + 1) + string(") "))
    # `Error: `, not the `[Error] ` of the rendering `error` above: this is a
    # user-facing diagnostic, and that is the spelling every other user-facing
    # nimony error uses (the test harness keys the expected exit code off it).
    write(stdout, string("Error: "))
    writeLine(stdout, msg)
    if comptime(defined("debug")):
        echo(getStackTrace())
    quit(1)


def _error(m: MainModule, msg: string, n: Cursor):
    """{.noreturn.}"""
    with let:
        info = n.rawLineInfo()
    if info.isValid():
        write(stdout, realFile(m.pool.filenames[info.file]))
        write(stdout, string("(") + str(info.line) + string(", ") + str(info.col + 1) + string(") "))
    write(stdout, string("[Error] "))
    write(stdout, msg)
    writeLine(stdout, _toString(n, False))
    if comptime(defined("debug")):
        echo(getStackTrace())
    quit(1)

# `strutils.parseInt` and `os.absolutePath` are `.raises` (ValueError) under
# Nimony. Their inputs here come from the front end (digit strings) and from the
# file table, so a failure is an internal error -- catch it locally instead of
# spreading `raises` through the whole generator (see doc/porting.md).


def _parseIntOrQuit(s: string) -> nint:
    result = 0
    try:
        result = parseInt(s)
    except:
        quit(string("lengc: expected an integer literal but got: '") + s + string("'"))
    return result


def _absoluteDirOrQuit(dir: string) -> string:
    ## Absolute spelling of `dir`, the current directory for an empty one. Both
    ## `getCurrentDir` and `absolutePath` (whose `root` default calls it) raise.
    result = string("")
    try:
        result = getCurrentDir() if dir == "" else absolutePath(dir)
    except:
        quit(string("lengc: cannot resolve the absolute path of: '") + dir + string("'"))
    return result

# ---- Block / emission helpers ----


def _dbgLocation(c: mut @ LLVMCode, info: NifLineInfo) -> string:
    pass


def setLoc(c: mut @ LLVMCode, info: NifLineInfo):
    c._currentProc.dbgLoc = _dbgLocation(c, info)


with const:
    _Terminators = Tset[LLInstrKind](LLInstrKind.llBr, LLInstrKind.llCondBr, LLInstrKind.llSwitch, LLInstrKind.llRet, LLInstrKind.llUnreachable)


@dispatch
def emit_(c: mut @ LLVMCode, instr: sink @ LLInstr):
    instr.dbgLoc = c._currentProc.dbgLoc
    c._currentBlock().instrs.add(instr)
    if instr.kind in _Terminators:
        c._currentProc.needsTerminator = True


def emitGEP(c: mut @ LLVMCode, baseType: LLType, base: LLValue, indices: openArray[LLValue], inbounds=True) -> LLValue:
    with let:
        t = c.nextTemp()
    result = llReg(t, c.prim.ptrT)
    with var:
        idxs: seq[LLValue] = seq[LLValue]([])
    for x in indices: idxs.add(x)
    emit_(c, LLInstr(kind=LLInstrKind.llGep, result=result, gepBaseType=baseType, gepBase=base, gepIndices=idxs, gepInbounds=inbounds))
    return result


def emitLoad(c: mut @ LLVMCode, ptrVal: LLValue, typ: LLType) -> LLValue:
    with let:
        t = c.nextTemp()
    result = llReg(t, typ)
    emit_(c, LLInstr(kind=LLInstrKind.llLoad, result=result, loadPtr=ptrVal))
    return result


def emitStore(c: mut @ LLVMCode, value: LLValue, ptrVal: LLValue):
    emit_(c, LLInstr(kind=LLInstrKind.llStore, storeValue=value, storePtr=ptrVal))


def llIntTextC(text: string, typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvInt, intText=text, typ=typ)

# ---- Type / value helpers ----


def typeEq(a: LLType, b: LLType) -> bool:
    """{.inline.}"""
    ## Structural type equality. Fast path on pointer identity for interned types.
    if a is b: return True
    if a is None or b is None: return False
    return serialize(a) == serialize(b)


def withType(v: LLValue, typ: LLType) -> LLValue:
    """{.inline.}"""
    result = v.copy()
    result.typ = typ
    return result


def disp(v: LLValue) -> string:
    """{.inline.}"""
    ## Display text of a value (for building callee names / signatures).
    result = string("")
    serializeUnqualified(v, result)
    return result

# ---- Pragma / type helpers ----


def _extractWasPragma(n: Cursor) -> string:
    result = string("")
    if substructureKind(n) == LengOther.PragmasU:
        with var:
            p = n.copy()
        for _ in loopInto(p):
            if pragmaKind(p) == LengPragma.WasP:
                with into(p):
                    if kind(p) in Tset[NifKind](NifKind.StrLit, NifKind.Ident):
                        result = strVal(p)
                    while p.hasMore(): skip(p)
                return result
            skip(p)
    return result


def _extractAlignValue(pragmas: Cursor) -> int64:
    result = 0
    if substructureKind(pragmas) == LengOther.PragmasU:
        with var:
            p = pragmas.copy()
        for _ in loopInto(p):
            if pragmaKind(p) == LengPragma.AlignP:
                with into(p):
                    result = intVal(p)
                    while p.hasMore(): skip(p)
                return result
            skip(p)
    return result


def _extractBitfieldBits(pragmas: Cursor) -> int64:
    result = 0
    if substructureKind(pragmas) == LengOther.PragmasU:
        with var:
            p = pragmas.copy()
        for _ in loopInto(p):
            if pragmaKind(p) == LengPragma.BitsP:
                with into(p):
                    result = intVal(p)
                    while p.hasMore(): skip(p)
                return result
            skip(p)
    return result


def baseTypeOfObject(m: mut @ MainModule, objBody: Cursor) -> Cursor:
    ## For an object type with inheritance, return the cursor to the base type symbol.
    result = default(Cursor)
    if typeKind(objBody) == LengType.ObjectT:
        with var:
            body = objBody.copy()
        body.inc()
        if kind(body) == NifKind.Symbol:
            result = body
    return result

# ---- Forward declarations (visible to included files) ----


def _genStmtLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    pass


def _genStmtBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    pass


def _genExprLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    pass


def _genExprBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    pass


def _genLvalueLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    pass


def _genCondLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    pass


def _genOnErrorLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    pass


def _genTypeLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> LLType:
    pass


def _genTypeLLVMReadOnly(c: mut @ LLVMCode, n: Cursor) -> LLType:
    pass


def _genDITypeReadOnly(c: mut @ LLVMCode, n: Cursor) -> nint:
    pass


def _genGlobalConstr(c: mut @ LLVMCode, n: mut @ Cursor, declaredType: Cursor) -> LLValue:
    pass


def _coerceValueLLVM(c: mut @ LLVMCode, val: LLValue, srcTypeCursor: Cursor, destTypeCursor: Cursor, result: mut @ LLValue):
    pass


def _genCallWithType(c: mut @ LLVMCode, n: mut @ Cursor, retType: LLType, result: mut @ LLValue):
    pass


def _genCallExprLLVM(c: mut @ LLVMCode, n: mut @ Cursor, result: mut @ LLValue):
    pass


def _llFloatHexText(f: float64) -> string:
    # LLVM float literal as hex: `0x` + IEEE-754 bits — exact, avoids the decimal-point rule.
    # Spelled out rather than via `strutils.toHex`, which Nimony does not have.
    with const:
        HexChars = string("0123456789ABCDEF")
    with let:
        bits = cast[uint64](f)
    result = string("0x")
    for i in countdown(15, 0):
        result.add(HexChars[nint((bits >> (i * 4)) & u64(0xF))])
    return result

# ---- Type generation ----


include("llvmgentypes")

# ---- Func type helper (used by genexprs call-site) ----


def genFuncTypeLLVM(c: mut @ LLVMCode, procDecl: Cursor) -> LLType:
    ## Build an llFunc type signature from a ProcS decl (type only).
    with var:
        n = procDecl.copy()
    with let:
        prc = takeProcDecl(n)
    with var:
        retType = LLType()
    if kind(prc.returnType) == NifKind.DotToken:
        retType = c.prim.voidT
    else:
        with var:
            rt = prc.returnType.copy()
        retType = _genTypeLLVM(c, rt)
    with var:
        paramTypes: seq[LLType] = seq[LLType]([])
        isVarargs = False
    if kind(prc.params) != NifKind.DotToken:
        with var:
            p = prc.params.copy()
        for _ in loopInto(p):
            with var:
                d = takeParamDecl(p)
            if typeKind(d.typ) == LengType.VarargsT:
                isVarargs = True
            else:
                with var:
                    t = d.typ.copy()
                paramTypes.add(_genTypeLLVM(c, t))
    result = newLLFuncType(retType, paramTypes, isVarargs)
    return result

# ---- DWARF debug info (metadata infra + type generation) ----


include("llvmdebug")

# ---- Expression generation ----

include("llvmgenexprs")

# ---- Variable declarations (needed by stmts) ----


def _genVarPragmasLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> Tset[LengPragma]:
    result = Tset[LengPragma]()
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            with let:
                pk = pragmaKind(n)
            match pk:
                case LengPragma.AlignP | LengPragma.AttrP | LengPragma.WasP:
                    skip(n)
                case LengPragma.HeaderP:
                    with into(n):
                        if kind(n) == NifKind.StrLit:
                            n.inc()
                        else:
                            _error(c._m, string("expected string literal in header pragma but got: "), n)
                        while n.hasMore(): skip(n)
                case LengPragma.StaticP | LengPragma.ImportcP | LengPragma.ImportcppP | LengPragma.ExportcP | LengPragma.NodeclP:
                    result.incl(pk)
                    skip(n)
                case _:
                    _error(c._m, string("invalid pragma: "), n)
    else:
        _error(c._m, string("expected pragmas but got: "), n)
    return result


class _VarKindLLVM(NIntEnum):
    IsLocal = auto()
    IsGlobal = auto()
    IsThreadlocal = auto()
    IsConst = auto()


def _genGlobalVarDeclLLVM(c: mut @ LLVMCode, n: mut @ Cursor, vk: _VarKindLLVM, toExtern=False):
    with let:
        varInfo = _info(n)
    with var:
        d = takeVarDecl(n)
    if kind(d.name) == NifKind.SymbolDef:
        with let:
            lit = symId(d.name)
        c._m.registerLocal(lit, d.typ)
        with var:
            diType = 0
        if not toExtern:
            diType = _genDITypeReadOnly(c, d.typ)

        with var:
            externName = StrId(0)
            isImport = False
            isNodecl = False
        with let:
            alignVal = _extractAlignValue(d.pragmas)
        if substructureKind(d.pragmas) == LengOther.PragmasU:
            with var:
                p = d.pragmas.copy()
            for _ in loopInto(p):
                match pragmaKind(p):
                    case LengPragma.ImportcP | LengPragma.ImportcppP:
                        externName = nifmodules.externName(lit, p)
                        isImport = True
                    case LengPragma.ExportcP:
                        externName = nifmodules.externName(lit, p)
                    case LengPragma.NodeclP:
                        isNodecl = True
                    case LengPragma.HeaderP:
                        pass
                    case _: pass
                skip(p)

        with let:
            flags = _genVarPragmasLLVM(c, d.pragmas)
        if isNodecl and isImport and externName != StrId(0):
            with let:
                extName = c._m.pool.strings[externName].copy()
            with var:
                t = d.typ.copy()
            with let:
                typ = _genTypeLLVM(c, t)
            with const:
                AtomicOrderNames = [string("__ATOMIC_RELAXED"), string("__ATOMIC_CONSUME"), string("__ATOMIC_ACQUIRE"), string("__ATOMIC_RELEASE"), string("__ATOMIC_ACQ_REL"), string("__ATOMIC_SEQ_CST")]
            with var:
                idx = -1
            for i, nm in pairs(AtomicOrderNames):
                if nm == extName:
                    idx = i
                    break
            if idx >= 0:
                # In C these are predefined macros, so there is no symbol at all.
                # But if we made it public, we would get duplicate symbols, so it's private.
                c.module.globals.add(LLGlobal(name=extName, typ=typ, initVal=llIntText(str(idx), typ), isConstant=True, isPrivate=True))
            skip(d.value)
            return

        with let:
            name = c._m.pool.strings[externName].copy() if externName != StrId(0) else mangleToC(c._m.pool.symString(lit))

        with var:
            t = d.typ.copy()
        with let:
            typ = _genTypeLLVM(c, t)

        with let:
            dbgvSuffix = _emitGlobalDbgVar(c, name, varInfo, lit, diType) if not toExtern and not isImport else string("")
        if toExtern or isImport:
            with var:
                g = LLGlobal(name=name, typ=typ, isExternal=True, isThreadLocal=(vk == _VarKindLLVM.IsThreadlocal), align=nint(alignVal), dbgLoc=dbgvSuffix)
            g.initVal = llZeroInit(typ)
            c.module.globals.add(g)
        else:
            # Module-private constants (plain `const`, string literals) hide their
            # global; exportc/importc/template keep external linkage.
            with let:
                isPriv = vk == _VarKindLLVM.IsConst and externName == StrId(0) and not c._inToplevel
            if kind(d.value) != NifKind.DotToken:
                with var:
                    v = d.value.copy()
                with let:
                    initVal = _genGlobalConstr(c, v, d.typ)
                c.module.globals.add(LLGlobal(name=name, typ=initVal.typ, initVal=initVal, isThreadLocal=(vk == _VarKindLLVM.IsThreadlocal), isConstant=(vk == _VarKindLLVM.IsConst), isPrivate=isPriv, align=nint(alignVal), dbgLoc=dbgvSuffix))
            else:
                skip(d.value)
                with let:
                    zeroVal = llDefaultZero(typ)
                c.module.globals.add(LLGlobal(name=name, typ=typ, initVal=zeroVal, isThreadLocal=(vk == _VarKindLLVM.IsThreadlocal), isConstant=(vk == _VarKindLLVM.IsConst), isPrivate=isPriv, align=nint(alignVal), dbgLoc=dbgvSuffix))
        if vk == _VarKindLLVM.IsConst:
            c.emittedConsts.incl(lit)
    else:
        _error(c._m, string("expected SymbolDef but got: "), d.name)


def _genLocalVarDeclLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    with let:
        varInfo = _info(n)
    with var:
        d = takeVarDecl(n)
    if kind(d.name) == NifKind.SymbolDef:
        with let:
            lit = symId(d.name)
        c._m.registerLocal(lit, d.typ)

        with let:
            wasName = _extractWasPragma(d.pragmas)
            alignVal = _extractAlignValue(d.pragmas)
            flags = _genVarPragmasLLVM(c, d.pragmas)
        if LengPragma.NodeclP in flags:
            skip(d.value)
            return

        with let:
            name = c._mangleSym(lit)
        with var:
            t = d.typ.copy()
        with let:
            diType = _genDITypeReadOnly(c, t)
            typ = _genTypeLLVM(c, t)
            localName = string("%") + name
        c.emitAlloca(name, typ, alignVal)
        _emitDbgDeclare(c, localName, lit, wasName, varInfo, diType, llvmTyp=typ)

        if kind(d.value) != NifKind.DotToken:
            if stmtKind(d.value) == LengStmt.OnerrS:
                with var:
                    onErr = d.value.copy()
                onErr.inc()
                with var:
                    onErrAction = onErr.copy()
                    val = default(LLValue)
                _genCallExprLLVM(c, d.value, val)
                setLoc(c, varInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llStore, storeValue=val, storePtr=llReg(name, c.prim.ptrT)))
                if kind(onErrAction) != NifKind.DotToken:
                    _genOnErrorLLVM(c, onErrAction)
            else:
                with let:
                    srcType = getType(c._m, d.value)
                with var:
                    val = default(LLValue)
                _genExprLLVM(c, d.value, val)
                _coerceInPlace(c, val, srcType, d.typ)
                setLoc(c, varInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llStore, storeValue=val, storePtr=llReg(name, c.prim.ptrT)))
        else:
            d.value.inc()
            with let:
                zeroVal = llDefaultZero(typ)
            setLoc(c, varInfo)
            emit_(c, LLInstr(kind=LLInstrKind.llStore, storeValue=zeroVal, storePtr=llReg(name, c.prim.ptrT)))
    else:
        _error(c._m, string("expected SymbolDef but got: "), d.name)

# ---- Statement generation ----


include("llvmgenstmts")

# ---- Proc and toplevel generation ----


class _PragmaInfo(Object):
    _flags: Tset[LengPragma]
    _extern: StrId
    _callConv: CallConv
    _wasName: string


def _parseProcPragmasLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> _PragmaInfo:
    result = _PragmaInfo()
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            with let:
                pk = pragmaKind(n)
            match pk:
                case LengPragma.NoPragma | LengPragma.AlignP | LengPragma.BitsP | LengPragma.VectorP | LengPragma.StaticP | LengPragma.PackedP:
                    if callConvKind(n) != CallConv.NoCallConv:
                        result._callConv = callConvKind(n)
                        skip(n)
                    else:
                        _error(c._m, string("invalid proc pragma: "), n)
                case LengPragma.NodeclP:
                    result._flags.incl(LengPragma.NodeclP)
                    skip(n)
                case LengPragma.DynlibP:
                    # Static-import library annotation for the NATIVE backend (arkham);
                    # meaningless for LLVM output — the linker resolves the symbol.
                    skip(n)
                case LengPragma.ConstrefP:
                    # A PARAMETER pragma; never legal on a proc.
                    _error(c._m, string("invalid proc pragma: "), n)
                case LengPragma.ImportjsP:
                    # As in codegen.parseProcPragmas: the splice template is jorogumo's
                    # question, and there is nothing to lower it to here.
                    _errorAt(c._m, string("importjs is a JS-backend pragma and has no LLVM lowering"), n)
                case LengPragma.ImportcppP | LengPragma.ImportcP | LengPragma.ExportcP:
                    with into(n):
                        if kind(n) == NifKind.StrLit:
                            result._extern = _litId(n)
                            n.inc()
                        result._flags.incl(pk)
                        while n.hasMore(): skip(n)
                case LengPragma.HeaderP:
                    with into(n):
                        if kind(n) != NifKind.StrLit:
                            _error(c._m, string("expected string literal in header pragma but got: "), n)
                        else:
                            n.inc()
                        while n.hasMore(): skip(n)
                case LengPragma.SelectanyP:
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.InstructionP | LengPragma.IntrinsicP:
                    # An intrinsic declares a machine instruction, not a callable: there is
                    # nothing to emit for the declaration itself.
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.InterruptP:
                    # No interrupt table here either; see the C backend's `parseProcPragmas`.
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.AssemblerP | LengPragma.NakedP | LengPragma.RegisterP | LengPragma.StackP:
                    # `{.assembler.}` bodies are arkham's; the location pins are assertions
                    # inside one. See the C backend's `parseProcPragmas` for the reasoning.
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.WasP:
                    with into(n):
                        result._wasName = _toString(n, False)
                        while n.hasMore(): skip(n)
                case LengPragma.ErrsP | LengPragma.RaisesP | LengPragma.SmryP:
                    skip(n)
                case LengPragma.InlineP:
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.AlwaysInlineP | LengPragma.NoinlineP:
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.AttrP:
                    skip(n)
    else:
        _error(c._m, string("expected proc pragmas but got: "), n)
    return result


def _genSymDefLLVM(c: mut @ LLVMCode, n: Cursor, prag: _PragmaInfo) -> string:
    if kind(n) == NifKind.SymbolDef:
        with let:
            lit = symId(n)
        if Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP, LengPragma.ExportcP) * prag._flags != Tset[LengPragma]():
            if prag._extern != StrId(0):
                result = c._m.pool.strings[prag._extern].copy()
            else:
                result = c._m.pool.symBasename(lit)
        else:
            result = mangleToC(c._m.pool.symString(lit))
    else:
        result = string("")
        _error(c._m, string("expected SymbolDef but got: "), n)
    return result


def _genParamPragmasLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            match pragmaKind(n):
                case LengPragma.AttrP | LengPragma.WasP:
                    skip(n)
                case LengPragma.ConstrefP:
                    # Provenance only (see `doc/tags.md`): the pointer stands for a
                    # by-value source parameter. Nothing to emit — it exists for
                    # `funcsummary`/the optimizer.
                    skip(n)
                case _:
                    _error(c._m, string("invalid pragma: "), n)
    else:
        _error(c._m, string("expected pragmas but got: "), n)


def _genProcDeclLLVM(c: mut @ LLVMCode, n: mut @ Cursor, isExtern: bool):
    c._m.openScope()
    c._inToplevel = False
    with let:
        oldProc = c._currentProc.copy()
        oldBlock = copy(c.currentBlockIdx)
    c._currentProc = LLVMCurrentProc(funcIdx=0, needsTerminator=False)
    c.nextTempCounter = 0
    c.nextLabelCounter = 0

    with let:
        procInfo = _info(n)
    with var:
        prc = takeProcDecl(n)
    with let:
        prag = _parseProcPragmasLLVM(c, prc.pragmas)
    if prag._flags * Tset[LengPragma](LengPragma.InstructionP, LengPragma.IntrinsicP) != Tset[LengPragma]():
        # An intrinsic declares an instruction, not a callable: there is nothing to
        # emit for the declaration itself, and its body slot is empty. Falling
        # through would build an `LLFunc` with an entry block and no terminator —
        # invalid IR. The C backend has the same guard in `genProcDecl`.
        c._m.closeScope()
        c._inToplevel = True
        c._currentProc = oldProc
        c.currentBlockIdx = oldBlock
        return
    if prag._flags * Tset[LengPragma](LengPragma.AssemblerP, LengPragma.NakedP) != Tset[LengPragma]():
        # Same reasoning as the C backend (see its `genProcDecl`): an `{.assembler.}`
        # body names machine registers and promises a one-to-one instruction mapping,
        # which no IR-level backend can honour. Refuse it by name instead of emitting
        # a body that silently means something else.
        _errorAt(c._m, string("the LLVM backend cannot compile an `{.assembler.}` proc; it must ") + string("be assembled by arkham and linked as an object (see doc/asm-c-interop.md)"), prc.name)
    if LengPragma.InterruptP in prag._flags:
        _errorAt(c._m, string("the LLVM backend has no interrupt table to install an ") + string("`{.interrupt.}` handler in; use `{.exportc: \"...\".}` to bind one by name ") + string("against a startup file, or compile it with arkham"), prc.name)
    if Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP) * prag._flags != Tset[LengPragma]() and LengPragma.InlineP not in prag._flags and kind(prc.body) != NifKind.DotToken:
        # The back end emits only a declaration for an imported proc; a body here
        # is a hexer bug, not something to drop silently.
        _errorAt(c._m, string("BUG: imported proc reached Leng with a body"), prc.name)

    with let:
        name = _genSymDefLLVM(c, prc.name, prag)

    with var:
        retType = LLType()
    if kind(prc.returnType) == NifKind.DotToken:
        retType = c.prim.voidT
    else:
        with var:
            rt = prc.returnType.copy()
        retType = _genTypeLLVM(c, rt)

    with var:
        isVarargs = False
        paramTypes: seq[LLType] = seq[LLType]([])
        paramNames: seq[string] = seq[string]([])
        paramWasNames: seq[string] = seq[string]([])
        paramSyms: seq[SymId] = seq[SymId]([])
        paramDITypes: seq[nint] = seq[nint]([])
    if kind(prc.params) != NifKind.DotToken:
        with var:
            p = prc.params.copy()
        for _ in loopInto(p):
            assert substructureKind(p) == LengOther.ParamU
            with var:
                d = takeParamDecl(p)
            if kind(d.name) == NifKind.SymbolDef:
                with let:
                    s = symId(d.name)
                c._m.registerLocal(s, d.typ)
                with var:
                    t = d.typ.copy()
                with let:
                    paramType = _genTypeLLVM(c, t)
                if typeKind(d.typ) != LengType.VarargsT:
                    paramTypes.add(paramType)
                    with let:
                        paramName = mangleToC(c._m.pool.symString(s))
                    paramNames.add(paramName)
                    paramWasNames.add(_extractWasPragma(d.pragmas))
                    paramSyms.add(s)
                    with var:
                        pdi = _genDITypeReadOnly(c, d.typ)
                    if pdi == 0:
                        with let:
                            bits = _bitsFromLLVMType(paramType, c._bits)
                        pdi = _genDIBasicType(c, string("int ") + str(bits), bits, _DW_ATE_signed)
                    paramDITypes.add(pdi)
                    _genParamPragmasLLVM(c, d.pragmas)
                else:
                    isVarargs = True
            else:
                _error(c._m, string("expected SymbolDef but got: "), d.name)

    if Tset[LengPragma](LengPragma.NodeclP, LengPragma.HeaderP) * prag._flags != Tset[LengPragma]():
        pass
    elif isExtern or Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP) * prag._flags != Tset[LengPragma]():
        with let:
            externName = name
        if externName not in c.declaredExterns:
            c.declaredExterns.incl(externName)
            c.module.externs.add(LLExternDecl(name=externName, retType=retType, params=paramTypes, isVarargs=isVarargs))
    else:
        # Function definition: build an LLFunc
        with let:
            displayName = prag._wasName if prag._wasName.len > 0 else name
            spId = _createSubprogram(c, displayName, procInfo)
        c._currentProc.subprogramId = spId

        with var:
            f = LLFunc(name=name, retType=retType, isVarargs=isVarargs, alwaysInline=(LengPragma.InlineP in prag._flags), noInline=(LengPragma.NoinlineP in prag._flags))
            params: seq[tuple[string, LLType]] = seq[tuple[string, LLType]]([])
        for i, pn in pairs(paramNames):
            params.add((pn, paramTypes[i]))
        f.params = move(params)
        f.metadata.subprogramId = spId
        f.blocks.add(LLBlock(label=string("entry")))  # entry block
        c.module.funcs.add(f)
        c._currentProc.funcIdx = c.module.funcs.high
        c._currentProc.retType = retType
        c._currentProc.retTypeCursor = prc.returnType
        c.currentBlockIdx = 0

        # Alloca + store for each parameter
        for i, pn in pairs(paramNames):
            c.emitAlloca(pn, paramTypes[i])
            with let:
                paramVal = llReg(pn + string(".param"), paramTypes[i])
            emit_(c, LLInstr(kind=LLInstrKind.llStore, storeValue=paramVal, storePtr=llReg(pn, c.prim.ptrT)))
            with let:
                pdi = paramDITypes[i] if i < paramDITypes.len else 0
                psym = paramSyms[i] if i < paramSyms.len else SymId(0)
            _emitDbgDeclare(c, string("%") + pn, psym, paramWasNames[i], procInfo, pdi, argNo=i + 1, llvmTyp=paramTypes[i])

        # Generate body
        _genStmtLLVM(c, prc.body)

        with let:
            retainedNodes = c._currentProc.retainedNodes.copy()
        _finalizeSubprogram(c, spId, paramDITypes, retainedNodes)

        if not c._currentProc.needsTerminator:
            if kind(prc.returnType) == NifKind.DotToken:
                setLoc(c, procInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llRet, retVal=llNoneVal()))
            else:
                with let:
                    zeroVal = llDefaultZero(retType)
                setLoc(c, procInfo)
                emit_(c, LLInstr(kind=LLInstrKind.llRet, retVal=zeroVal))

    c._m.closeScope()
    c._inToplevel = True
    c._currentProc = oldProc
    c.currentBlockIdx = oldBlock


def _genImportedSymsLLVM(c: mut @ LLVMCode):
    while True:
        with let:
            fsyms = move(c._m.requestedForeignSyms)
        if fsyms.len == 0: break
        for fsym in fsyms:
            with var:
                n = fsym.copy()
            match stmtKind(fsym):
                case LengStmt.ProcS:
                    _genProcDeclLLVM(c, n, True)
                case LengStmt.VarS:
                    pass
                case LengStmt.GvarS:
                    _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsGlobal, True)
                case LengStmt.TvarS:
                    _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsThreadlocal, True)
                case LengStmt.ConstS:
                    _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsConst, True)
                case _:
                    pass


def _genToplevelLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    match stmtKind(n):
        case LengStmt.ProcS: _genProcDeclLLVM(c, n, False)
        case LengStmt.GvarS:
            _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsGlobal)
        case LengStmt.TvarS:
            _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsThreadlocal)
        case LengStmt.ConstS:
            _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsConst)
        case LengStmt.VarS:
            _genGlobalVarDeclLLVM(c, n, _VarKindLLVM.IsGlobal)
        case LengStmt.TypeS:
            _ = "handled in a different pass"
            skip(n)
        case LengStmt.EmitS:
            skip(n)
        case LengStmt.DiscardS | LengStmt.AsgnS | LengStmt.KeepovfS | LengStmt.ScopeS | LengStmt.IfS | LengStmt.WhileS | LengStmt.CaseS | LengStmt.LabS | LengStmt.JmpS | LengStmt.TryS | LengStmt.RaiseS | LengStmt.CallS | LengStmt.OnerrS:
            # Route into the init function.
            with let:
                savedFunc = copy(c._currentProc.funcIdx)
                savedBlock = copy(c.currentBlockIdx)
                savedLoc = c._currentProc.dbgLoc.copy()
            if not c.module.hasInitBody:
                c.module.initFunc.blocks.add(LLBlock(label=string("entry")))
                c.module.hasInitBody = True
            c._currentProc.funcIdx = InitFuncIdx
            c._currentProc.needsTerminator = False
            c.currentBlockIdx = c.module.initFunc.blocks.high
            _genStmtLLVM(c, n)
            c._currentProc.funcIdx = savedFunc
            c.currentBlockIdx = savedBlock
            c._currentProc.dbgLoc = savedLoc
        case LengStmt.StmtsS:
            for _ in loopInto(n): _genToplevelLLVM(c, n)
        case _:
            _error(c._m, string("expected top level construct but got: "), n)


def _traverseCodeLLVM(c: mut @ LLVMCode, n: mut @ Cursor):
    if stmtKind(n) == LengStmt.StmtsS:
        for _ in loopInto(n): _genToplevelLLVM(c, n)
        _genImportedSymsLLVM(c)
    else:
        _error(c._m, string("expected `stmts` but got: "), n)

# Named types are registered lazily by genTypeLLVM via ensureTypeDef
# (see llvmgentypes.nim) — no separate type-emission pass.


def generateLLVMCode(s: mut @ State, inp: string, outp: string, flags: Tset[LLVMGenFlag]):
    with var:
        m = load(inp)
    m.config = s.config
    with var:
        c = initLLVMCode(m, flags, s.bits)
    c._m.openScope()

    _initDebugInfo(c, inp)

    with var:
        n = c._m.src.beginRead()
    _traverseCodeLLVM(c, n)

    # Add runtime globals as structured LLGlobal
    with let:
        isMain = LLVMGenFlag.gfMainModule in c._flags
    c.module.globals.add(LLGlobal(name=string("LENGC_ERR_"), typ=c.prim.i8_, isThreadLocal=True, isExternal=not isMain, initVal=llIntText(string("0"), c.prim.i8_)))
    c.module.globals.add(LLGlobal(name=string("LENGC_OVF_"), typ=c.prim.i8_, isThreadLocal=True, isExternal=not isMain, initVal=llIntText(string("0"), c.prim.i8_)))

    # Patch debug metadata onto the module before serialization
    if c.debug.metadata.len > 0:
        if c.debug.globalExprs.len > 0:
            with var:
                gList = string("")
            for i, gid in pairs(c.debug.globalExprs):
                if i > 0: gList.add(string(", "))
                gList.add(string("!") + str(gid))
            with let:
                globalsId = _addMetadata(c, string("!{") + gList + string("}"))
                oldCu = c.debug.metadata[c.debug.cuId].copy()
            c.debug.metadata[c.debug.cuId] = oldCu[inrange(0, back(2))] + string(", globals: !") + str(globalsId) + string(", splitDebugInlining: false)")

        with let:
            dwarfId = _addMetadata(c, string("!{i32 7, !\"Dwarf Version\", i32 4}"))
            diVersionId = _addMetadata(c, string("!{i32 2, !\"Debug Info Version\", i32 3}"))
        c.module.cuId = c.debug.cuId
        c.module.dwarfVerId = dwarfId
        c.module.diVerId = diVersionId
        c.module.metadata = move(c.debug.metadata)
        c.module.globalExprIds = move(c.debug.globalExprs)

    if c.module.hasInitBody:
        c.module.initFunc.name = string("lengc_init")
        c.module.initFunc.retType = c.prim.voidT

    with let:
        llText = serializeModule(c.module)

    # Always written, as the C backend's `.c` (doc/internals/ic.md).
    vfsWrite(outp, llText)

    c._m.closeScope()
