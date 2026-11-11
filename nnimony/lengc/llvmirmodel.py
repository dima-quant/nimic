# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/llvmirmodel.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## Structured LLVM IR data model.
##
## This module is a pure data layer sitting between NIF traversal and the `.ll`
## text serializer. All LLVM syntax knowledge lives in `llvmserializer.nim`;
## nothing here knows how an instruction is spelled. Types are interned `ref`
## objects so identity is pointer-equality. Values are tagged unions so the
## serializer switches on `kind` instead of parsing string prefixes.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    # `nil` is the model's "type not known / not applicable" marker -- it travels
    # through `LLType` fields, params and locals all over the LLVM backend.
    pragma("feature: \"lenientnils\"")


class LLTypeKind(NIntEnum):
    llVoid = auto()
    llInt = auto()
    llFloat = auto()
    llPtr = auto()
    llArray = auto()
    llStruct = auto()
    llUnion = auto()
    llFunc = auto()


class LLTypeObj(Object):
    name: string  # e.g. "Person", "" for anonymous
    kind: LLTypeKind
    match kind:
        case LLTypeKind.llVoid:
            pass
        case LLTypeKind.llInt:
            intBits: nint
        case LLTypeKind.llFloat:
            floatBits: nint
        case LLTypeKind.llPtr:
            ptrPointee: LLType
        case LLTypeKind.llArray:
            arrLen: nint
            arrElem: LLType
        case LLTypeKind.llStruct:
            structFields: seq[LLStructField]
            structSizeBits: nint
            structAlignBits: nint
            structPacked: bool
        case LLTypeKind.llUnion:
            unionMembers: seq[LLUnionMember]  # all branches (for GEP reference)
            repType: LLType  # the LLVM struct actually emitted
        case LLTypeKind.llFunc:
            funcRetType: LLType
            funcParamTypes: seq[LLType]
            funcIsVarargs: bool

@ref
class LLType(LLTypeObj):
    pass


class LLStructField(Object):
    name: string
    typ: LLType
    offsetBits: nint  # 0 unless bitfield


class LLUnionMember(Object):
    typ: LLType
    sizeBits: nint
    alignBits: nint


class LLAtomicOrdering(NIntEnum):
    llaoUnordered = auto()
    llaoMonotonic = auto()
    llaoAcquire = auto()
    llaoRelease = auto()
    llaoAcqRel = auto()
    llaoSeqCst = auto()


class LLAtomicrmwOp(NIntEnum):
    llrmwXchg = auto()
    llrmwAdd = auto()
    llrmwSub = auto()
    llrmwAnd = auto()
    llrmwOr = auto()
    llrmwXor = auto()
    llrmwNand = auto()
    llrmwMin = auto()
    llrmwMax = auto()
    llrmwUmin = auto()
    llrmwUmax = auto()


class LLValueKind(NIntEnum):
    llvNone = auto()  # no value (for void results) — MUST be first = zero default
    llvReg = auto()  # result of an instruction: %t5
    llvInt = auto()  # integer literal: stored textually (e.g. "42", "-1")
    llvFloat = auto()  # float/double literal: stored textually
    llvBool = auto()  # boolean literal (true/false) emitted as i8 0/1 by codegen
    llvGlobal = auto()  # @name — reference to a global
    llvNull = auto()  # null
    llvUndef = auto()  # undef
    llvZero = auto()  # zeroinitializer
    llvPoison = auto()  # poison
    llvCString = auto()  # c"..." string constant
    llvRawText = auto()  # pre-formatted text (complex constant initializers)


class LLValue(Object):
    typ: LLType  # type of this value
    kind: LLValueKind
    match kind:
        case LLValueKind.llvReg:
            regName: string  # stored WITHOUT the leading %
        case LLValueKind.llvInt:
            intText: string  # canonical integer text
        case LLValueKind.llvFloat:
            floatText: string  # canonical float text (may be 0x... hex)
        case LLValueKind.llvBool:
            boolVal: bool
        case LLValueKind.llvGlobal:
            globalName: string  # stored WITHOUT the leading @
        case LLValueKind.llvCString:
            strVal: string
        case LLValueKind.llvRawText:
            rawText: string
        case LLValueKind.llvNull | LLValueKind.llvUndef | LLValueKind.llvZero | LLValueKind.llvPoison | LLValueKind.llvNone:
            pass


class LLInstrKind(NIntEnum):
    llBinOp = auto()
    llIcmp = auto()
    llFcmp = auto()
    llZext = auto()
    llSext = auto()
    llTrunc = auto()
    llFpext = auto()
    llFptrunc = auto()
    llSitofp = auto()
    llUitofp = auto()
    llFptosi = auto()
    llFptoui = auto()
    llBitcast = auto()
    llInttoptr = auto()
    llPtrtoint = auto()
    llAlloca = auto()
    llLoad = auto()
    llStore = auto()
    llGep = auto()
    llCall = auto()
    llExtractValue = auto()
    llInsertValue = auto()
    llPhi = auto()
    llSelect = auto()
    llFneg = auto()
    llBr = auto()
    llCondBr = auto()
    llSwitch = auto()
    llRet = auto()
    llUnreachable = auto()
    llAtomicrmw = auto()
    llCmpxchg = auto()
    llFence = auto()
    llRaw = auto()  # escape hatch for intrinsics mixing values + metadata


class LLInstr(Object):
    result: LLValue  # result register; llvNone when void
    dbgLoc: string  # ", !dbg !N" suffix, empty if none
    kind: LLInstrKind
    match kind:
        case LLInstrKind.llBinOp:
            binOp: string  # "add", "sub", ... (allows nuw/nsw via flags)
            binLhs: LLValue
            binRhs: LLValue
            binNuw: bool
            binNsw: bool
        case LLInstrKind.llIcmp:
            icmpPred: string  # "eq", "ne", "slt", ...
            icmpLhs: LLValue
            icmpRhs: LLValue
        case LLInstrKind.llFcmp:
            fcmpPred: string
            fcmpLhs: LLValue
            fcmpRhs: LLValue
        case _ if kind in inrange(LLInstrKind.llZext, LLInstrKind.llPtrtoint):
            castOp: string  # "zext", "sext", ...
            castSrc: LLValue
            castDstType: LLType
        case LLInstrKind.llAlloca:
            allocaType: LLType
            allocaAlign: nint
            allocaNumElts: LLValue  # llvNone for single-element alloca
        case LLInstrKind.llLoad:
            loadPtr: LLValue
            loadAtomic: bool
            loadOrdering: LLAtomicOrdering
            loadAlign: nint
        case LLInstrKind.llStore:
            storeValue: LLValue
            storePtr: LLValue
            storeAtomic: bool
            storeOrdering: LLAtomicOrdering
            storeAlign: nint
        case LLInstrKind.llGep:
            gepBaseType: LLType
            gepBase: LLValue
            gepIndices: seq[LLValue]
            gepInbounds: bool
        case LLInstrKind.llCall:
            callCallee: LLValue  # llvGlobal (@name) for direct, llvReg for indirect
                                 # callee.typ is llFunc when signature is known
            callRetType: LLType
            callArgs: seq[LLValue]
        case LLInstrKind.llExtractValue:
            evAggregate: LLValue
            evAggType: LLType  # the aggregate type, e.g. { i32, i1 }
            evIndex: nint
        case LLInstrKind.llInsertValue:
            ivAggregate: LLValue
            ivElement: LLValue
            ivAggType: LLType
            ivIndex: nint
        case LLInstrKind.llPhi:
            phiIncoming: seq[tuple[LLValue, string]]  # (value, label)
        case LLInstrKind.llSelect:
            selCond: LLValue
            selTrue: LLValue
            selFalse: LLValue
        case LLInstrKind.llFneg:
            fnegVal: LLValue
        case LLInstrKind.llRet:
            retVal: LLValue  # llvNone if void
        case LLInstrKind.llBr:
            brTarget: string
        case LLInstrKind.llCondBr:
            condBrCond: LLValue
            condBrTrue: string
            condBrFalse: string
        case LLInstrKind.llSwitch:
            switchValType: LLType  # the value's type
            switchVal: LLValue
            switchDefault: string
            switchCases: seq[tuple[LLValue, string]]  # (value, label)
        case LLInstrKind.llUnreachable:
            pass
        case LLInstrKind.llAtomicrmw:
            armwOp: LLAtomicrmwOp
            armwPtr: LLValue
            armwVal: LLValue
            armwOrdering: LLAtomicOrdering
            armwSyncscope: string  # "" default, "singlethread" for signal fence
            armwAlign: nint
        case LLInstrKind.llCmpxchg:
            cxPtr: LLValue
            cxExpected: LLValue
            cxDesired: LLValue
            cxAggType: LLType  # the {T, i1} aggregate type
            cxSuccessOrdering: LLAtomicOrdering
            cxFailureOrdering: LLAtomicOrdering
            cxWeak: bool
            cxSyncscope: string
            cxAlign: nint
        case LLInstrKind.llFence:
            fenceOrdering: LLAtomicOrdering
            fenceSyncscope: string
        case LLInstrKind.llRaw:
            rawText: string  # fully-formatted line (dbg intrinsics, etc.)


class LLBlock(Object):
    label: string
    instrs: seq[LLInstr]


class LLFuncMetadata(Object):
    subprogramId: nint
    fileId: nint
    paramDITypes: seq[nint]
    retainedNodeIds: seq[nint]


class LLFunc(Object):
    name: string
    retType: LLType
    params: seq[tuple[string, LLType]]
    isVarargs: bool
    entryAllocas: seq[LLInstr]  # allocas hoisted into the entry block
    blocks: seq[LLBlock]
    alwaysInline: bool
    noInline: bool
    metadata: LLFuncMetadata


class LLGlobal(Object):
    name: string  # WITHOUT leading @
    typ: LLType
    initVal: LLValue
    isThreadLocal: bool
    isConstant: bool
    isExternal: bool
    isPrivate: bool
    align: nint
    dbgLoc: string  # ", !dbg !N" suffix, empty if none


class LLExternDecl(Object):
    name: string  # bare extern name (WITHOUT @; for dedup)
    retType: LLType  # return type (used when raw == "")
    params: seq[LLType]  # parameter types (used when raw == "")
    isVarargs: bool
    raw: string  # non-empty => emit this declare line verbatim
                 # (for builtins whose attributes don't fit the model)


class LLNamedType(Object):
    ## A named type definition: `%Name = type <body>`.
    name: string  # WITHOUT leading %
    body: LLType  # nil => emit `= type opaque`
    packed: bool


class LLModule(Object):
    typeDefs: seq[LLNamedType]  # named type definitions (dedup by name)
    globals: seq[LLGlobal]
    externs: seq[LLExternDecl]
    funcs: seq[LLFunc]
    initFunc: LLFunc  # the @lengc_init global constructor
    hasInitBody: bool
    metadata: seq[string]  # raw metadata nodes (final, handed to serializer)
    cuId: nint  # DICompileUnit metadata id
    dwarfVerId: nint  # !"Dwarf Version" module.flags id
    diVerId: nint  # !"Debug Info Version" module.flags id
    globalExprIds: seq[nint]  # DIGlobalVariableExpression ids

# ---- Value constructors ----


def llReg(name: string, typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvReg, regName=name, typ=typ)


def llIntText(text: string, typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvInt, intText=text, typ=typ)


def llFloatText(text: string, typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvFloat, floatText=text, typ=typ)


def llBoolVal(b: bool, typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvBool, boolVal=b, typ=typ)


def llGlobalRef(name: string, typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvGlobal, globalName=name, typ=typ)


def llNull(typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvNull, typ=typ)


def llUndef(typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvUndef, typ=typ)


def llZeroInit(typ: LLType) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvZero, typ=typ)


def llDefaultZero(typ: LLType) -> LLValue:
    """{.inline.}"""
    ## Zero value for default initialization: pointers get `null`, everything
    ## else `zeroinitializer`. After genTypeLLVM every pointer-ish source type
    ## (PtrT/AptrT/ProctypeT) has collapsed to `llPtr`, so this is the only
    ## distinction that matters.
    return llNull(typ) if typ is not None and typ.kind == LLTypeKind.llPtr else llZeroInit(typ)


def llNoneVal() -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvNone)


def llCString(s: string) -> LLValue:
    """{.inline.}"""
    return LLValue(kind=LLValueKind.llvCString, strVal=s)

# ---- Type constructors ----


def newLLVoidType() -> LLType:
    return LLType(kind=LLTypeKind.llVoid)


def newLLIntType(bits: nint) -> LLType:
    return LLType(kind=LLTypeKind.llInt, intBits=bits)


def newLLFloatType(bits: nint) -> LLType:
    return LLType(kind=LLTypeKind.llFloat, floatBits=bits)


def newLLPtrType(pointee: LLType = None) -> LLType:
    return LLType(kind=LLTypeKind.llPtr, ptrPointee=pointee)


def newLLArrayType(len: nint, elem: LLType) -> LLType:
    return LLType(kind=LLTypeKind.llArray, arrLen=len, arrElem=elem)


def newLLStructType(fields: seq[LLStructField], packed=False) -> LLType:
    return LLType(kind=LLTypeKind.llStruct, structFields=fields, structPacked=packed)


def newLLNamedType(name: string) -> LLType:
    return LLType(kind=LLTypeKind.llStruct, name=name)


def newLLUnionType(members: seq[LLUnionMember], repType: LLType) -> LLType:
    return LLType(kind=LLTypeKind.llUnion, unionMembers=members, repType=repType)


def newLLFuncType(retType: LLType, params: seq[LLType], isVarargs=False) -> LLType:
    return LLType(kind=LLTypeKind.llFunc, funcRetType=retType, funcParamTypes=params, funcIsVarargs=isVarargs)

# ---- Instruction constructors ----


def newLLBinInstr(res: LLValue, binOp: string, binLhs: LLValue, binRhs: LLValue, dbgLoc=string("")) -> LLInstr:
    ## Construct a binary-op instruction.
    result = LLInstr()
    _ = LLInstr(result=res, dbgLoc=dbgLoc, kind=LLInstrKind.llBinOp, binOp=binOp, binLhs=binLhs, binRhs=binRhs)
    return result
