# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# Test scaffolding (nimic_translation_rules.md §2.1): the context that cgen.nim gives its include files
# (cbuilderexprs, cbuilderstmts, ccgthreadvars, ...), for the modules that are not converted yet.
# Included by the harnesses in ncompiler/tests first; cbuilderdecls_subset, cgen_procs and cgen_stmts
# follow at their places in cgen.nim's include order. Each section is a subset of the named Nim
# module; procs are copied line for line where they are used. Converted modules (options, lineinfos, msgs,
# nodekinds, ropes, std/intsets) are imported by the harness.

# --- int128.nim (subset) ---
class Int128(Object):
    udata: array[4, uint32]

    def __str__(self) -> string:
        # simplified: non-negative values below 2^64
        return str((uint64(self.udata[1]) << 32) | uint64(self.udata[0]))


def toInt128(arg: int64) -> Int128:
    # simplified: non-negative values below 2^63
    result = Int128()
    result.udata[0] = uint32(arg & 0xFFFFFFFF)
    result.udata[1] = uint32(arg >> 32)
    return result


# --- cbuilderbase.nim (subset) ---
Snippet = string


class Builder(Object):
    buf: string
    indents: nint

    def add(self: mut@Builder, s: string) -> None:
        self.buf.add(s)

    def add(self: mut@Builder, s: char) -> None:
        self.buf.add(s)

    def addNewline(self: mut@Builder) -> None:
        self.add(ch("\n"))
        for i in range(self.indents):
            self.add(ch("\t"))

    def addLineEnd(self: mut@Builder, s: string) -> None:
        self.add(s)
        self.addNewline()

    def addLineEndIndent(self: mut@Builder, s: string) -> None:
        self.indents += 1
        self.add(s)
        self.addNewline()

    def addDedent(self: mut@Builder, s: string) -> None:
        if len(self.buf) > 0 and self.buf[len(self.buf) - 1] == ch("\t"):
            self.buf.setLen(len(self.buf) - 1)
        self.add(s)
        self.indents -= 1

    def addLineEndDedent(self: mut@Builder, s: string) -> None:
        self.addDedent(s)
        self.addNewline()

    def addIntValue(self: mut@Builder, val: nint) -> None:
        self.buf.add(string(str(val)))

    def addIntValue(self: mut@Builder, val: int64) -> None:
        self.buf.add(string(str(val)))

    def addIntValue(self: mut@Builder, val: uint64) -> None:
        self.buf.add(string(str(val)))

    def addIntValue(self: mut@Builder, val: Int128) -> None:
        self.buf.add(string("Int128"))


def newBuilder(s: string) -> Builder:
    return Builder(buf=s)


def extract(builder: Builder) -> Snippet:
    return builder.buf


@dispatch
def cIntValue(val: nint) -> Snippet:
    return string(str(val))


@dispatch
def cIntValue(val: int64) -> Snippet:
    return string(str(val))


@dispatch
def cIntValue(val: Int128) -> Snippet:
    return string(str(val))


class IfBuilderState(NIntEnum):
    WaitingIf = 0
    WaitingElseIf = auto()
    InBlock = auto()


class IfBuilder(Object):
    state: IfBuilderState


with const:
    NimInt = string("NI")
    NimUint = string("NU")
    NimChar = string("NIM_CHAR")
    NimNil = string("NIM_NIL")
    NimStrlitFlag = string("NIM_STRLIT_FLAG")
    CVoid = string("void")
    CPointer = string("void*")
    CChar = string("char")


# --- astdef.nim (subset) ---
class TCallingConvention(NIntEnum):
    ccNimCall = 0
    ccStdCall = auto()
    ccCDecl = auto()
    ccSafeCall = auto()
    ccSysCall = auto()
    ccInline = auto()
    ccNoInline = auto()
    ccFastCall = auto()
    ccThisCall = auto()
    ccClosure = auto()
    ccNoConvention = auto()
    ccMember = auto()


class TSymFlag(NIntEnum):
    sfUsed = 0
    sfExported = auto()
    sfImportc = auto()
    sfMainModule = auto()
    sfCompileToCpp = auto()
    sfThread = auto()


class TLocFlag(NIntEnum):
    lfIndirect = 0
    lfNoDeepCopy = auto()
    lfNoDecl = auto()
    lfDynamicLib = auto()
    lfExportLib = auto()


class TTypeKind(NIntEnum):
    tyNone = 0
    tyBool = auto()
    tyChar = auto()
    tyEmpty = auto()
    tyAlias = auto()
    tyNil = auto()
    tyUntyped = auto()
    tyTyped = auto()
    tyTypeDesc = auto()
    tyGenericInvocation = auto()
    tyGenericBody = auto()
    tyGenericInst = auto()
    tyGenericParam = auto()
    tyDistinct = auto()
    tyEnum = auto()
    tyOrdinal = auto()
    tyArray = auto()
    tyObject = auto()
    tyTuple = auto()
    tySet = auto()
    tyRange = auto()
    tyPtr = auto()
    tyRef = auto()
    tyVar = auto()
    tySequence = auto()
    tyProc = auto()
    tyPointer = auto()
    tyOpenArray = auto()
    tyString = auto()
    tyCstring = auto()
    tyForward = auto()
    tyInt = auto()
    tyInt8 = auto()
    tyInt16 = auto()
    tyInt32 = auto()
    tyInt64 = auto()
    tyFloat = auto()
    tyFloat32 = auto()
    tyFloat64 = auto()
    tyFloat128 = auto()
    tyUInt = auto()
    tyUInt8 = auto()
    tyUInt16 = auto()
    tyUInt32 = auto()
    tyUInt64 = auto()
    tyOwned = auto()
    tySink = auto()
    tyLent = auto()
    tyVarargs = auto()
    tyUncheckedArray = auto()
    tyError = auto()
    tyBuiltInTypeClass = auto()
    tyUserTypeClass = auto()
    tyUserTypeClassInst = auto()
    tyCompositeTypeClass = auto()
    tyInferred = auto()
    tyAnd = auto()
    tyOr = auto()
    tyNot = auto()
    tyAnything = auto()
    tyStatic = auto()
    tyFromExpr = auto()
    tyConcept = auto()
    tyVoid = auto()
    tyIterable = auto()


TTypeKinds = Tset[TTypeKind]


class TTypeFlag(NIntEnum):
    tfVarargs = 0
    tfNoSideEffect = auto()
    tfFinal = auto()
    tfInheritable = auto()
    tfHasOwned = auto()
    tfEnumHasHoles = auto()
    tfShallow = auto()
    tfThread = auto()
    tfFromGeneric = auto()
    tfUnresolved = auto()
    tfResolved = auto()
    tfRetType = auto()
    tfCapturesEnv = auto()
    tfByCopy = auto()
    tfByRef = auto()
    tfIterator = auto()
    tfPartial = auto()
    tfNotNil = auto()
    tfRequiresInit = auto()
    tfNeedsFullInit = auto()
    tfVarIsPtr = auto()
    tfHasMeta = auto()
    tfHasGCedMem = auto()
    tfPacked = auto()
    tfHasStatic = auto()
    tfGenericTypeParam = auto()
    tfImplicitTypeParam = auto()
    tfInferrableStatic = auto()
    tfConceptMatchedTypeSym = auto()
    tfExplicit = auto()
    tfWildcard = auto()
    tfHasAsgn = auto()


with const:
    GcTypeKinds = TTypeKinds({TTypeKind.tyRef, TTypeKind.tySequence, TTypeKind.tyString})
    abstractInst = TTypeKinds({TTypeKind.tyGenericInst, TTypeKind.tyDistinct, TTypeKind.tyOrdinal,
                               TTypeKind.tyTypeDesc, TTypeKind.tyAlias, TTypeKind.tyInferred, TTypeKind.tySink,
                               TTypeKind.tyOwned})


@ref
class PNode(Object):
    kind: TNodeKind
    info: TLineInfo
    intVal: BiggestInt
    strVal: string
    sym: PSym
    sons: seq[PNode]

    # ast.nim accessors
    @property
    def len(self) -> nint:
        return len(self.sons)

    def __getitem__(self, i: nint) -> PNode:
        return self.sons[i]


@ref
class PType(Object):
    id: nint
    name: string  # stand-in: the C type that getTypeDesc returns
    kind: TTypeKind
    callConvImpl: TCallingConvention
    sonsImpl: seq[PType]
    n: PNode
    sym: PSym
    sizeImpl: BiggestInt
    flags: Tset[TTypeFlag]

    # ast.nim accessors
    @property
    def callConv(self) -> TCallingConvention:
        return self.callConvImpl

    @property
    def size(self) -> BiggestInt:
        return self.sizeImpl

    @property
    def len(self) -> nint:
        return len(self.sonsImpl)

    def __getitem__(self, i: nint) -> PType:
        return self.sonsImpl[i]

    @property
    def last(self) -> PType:
        return self.sonsImpl[len(self.sonsImpl) - 1]

    @property
    def elementType(self) -> PType:
        return self.sonsImpl[len(self.sonsImpl) - 1]

    @property
    def indexType(self) -> PType:
        return self.sonsImpl[0]

    @property
    def baseClass(self) -> PType:
        return self.sonsImpl[0]

    def ikids(self) -> tuple[nint, PType]:
        for i in range(self.len):
            yield (i, self[i])


class TLoc(Object):
    lode: PNode
    snippet: string
    t: PType
    flags: Tset[TLocFlag]


@ref
class PSym(Object):
    id: nint
    typ: PType
    flags: Tset[TSymFlag]
    loc: TLoc


def skipModifier(n: PType) -> PType:
    return n.sonsImpl[len(n.sonsImpl) - 1]


def lastSon(n: PNode) -> PNode:
    return n.sons[len(n.sons) - 1]


def skipTypes(t: PType, kinds: TTypeKinds) -> PType:
    ## Used throughout the compiler code to test whether a type tree contains or
    ## doesn't contain a specific type/types - it is often the case that only the
    ## last child nodes of a type tree need to be searched. This is a really hot
    ## path within the compiler!
    result = t
    while result.kind in kinds:
        result = result.last
    return result


# --- types.nim (subset) ---
with const:
    abstractInstOwned = abstractInst + TTypeKinds({TTypeKind.tyOwned})
    skipPtrs = TTypeKinds({TTypeKind.tyVar, TTypeKind.tyPtr, TTypeKind.tyRef, TTypeKind.tyGenericInst,
                           TTypeKind.tyTypeDesc, TTypeKind.tyAlias, TTypeKind.tyInferred, TTypeKind.tySink,
                           TTypeKind.tyLent, TTypeKind.tyOwned})
    typedescInst = abstractInst + TTypeKinds({TTypeKind.tyTypeDesc, TTypeKind.tyOwned, TTypeKind.tyUserTypeClass})


def containsGarbageCollectedRef(typ: PType) -> bool:
    # returns true if typ contains a reference, sequence or string (all the
    # things that are garbage-collected)
    # simplified: searchTypeFor(typ, isGCRef) without the object fields
    result = typ.kind in GcTypeKinds
    for i, a in typ.ikids():
        if a is not None and containsGarbageCollectedRef(a):
            result = True
    return result


def getSize(conf: ConfigRef, typ: PType) -> BiggestInt:
    # simplified: the size is preset
    return typ.size


def lengthOrd(conf: ConfigRef, t: PType) -> Int128:
    # simplified: t is a range type (lastOrd - firstOrd + 1)
    return toInt128(t.n[1].intVal - t.n[0].intVal + 1)


# --- modulegraphs.nim, magicsys.nim (subset) ---
@ref
class ModuleGraph(Object):
    config: ConfigRef


def getSysType(g: ModuleGraph, info: TLineInfo, kind: TTypeKind) -> PType:
    # simplified: a fresh type of the kind; NI for tyInt
    return PType(kind=kind, name=string("NI"))


# --- treetab.nim (subset) ---
class TNodeTable(Object):
    # simplified: string literal nodes, searched linearly
    keys: seq[string]
    vals: seq[nint]


def nodeTableTestOrSet(t: mut@TNodeTable, key: PNode, val: nint) -> nint:
    # simplified: a linear search by strVal
    for i in range(t.keys.len):
        if t.keys[i] == key.strVal:
            return t.vals[i]
    t.keys.add(key.strVal)
    t.vals.add(val)
    return val


# --- sighashes.nim (subset) ---
class SigHash(Object):
    # simplified: the digest as text
    digest: string

    def __str__(self) -> string:
        return str(self.digest)


# --- ccgutils.nim (subset) ---
def getUniqueType(key: PType) -> PType:
    return key


# --- cgendata.nim (subset) ---
TLabel = string


class TCFileSection(NIntEnum):
    cfsHeaders = 0
    cfsFrameDefines = auto()
    cfsForwardTypes = auto()
    cfsTypes = auto()
    cfsSeqTypes = auto()
    cfsTypeInfo = auto()
    cfsProcHeaders = auto()
    cfsStrData = auto()
    cfsData = auto()
    cfsVars = auto()
    cfsProcs = auto()
    cfsInitProc = auto()
    cfsDatInitProc = auto()
    cfsTypeInit1 = auto()
    cfsTypeInit3 = auto()
    cfsDynLibInit = auto()


class TCProcSection(NIntEnum):
    cpsLocals = 0
    cpsInit = auto()
    cpsStmts = auto()


class TCProcFlag(NIntEnum):
    beforeRetNeeded = 0
    threadVarAccessed = auto()
    hasCurFramePointer = auto()
    noSafePoints = auto()
    nimErrorFlagAccessed = auto()
    nimErrorFlagDeclared = auto()
    nimErrorFlagDisabled = auto()


class TCTypeKind(NIntEnum):
    ctVoid = 0
    ctChar = auto()
    ctBool = auto()
    ctInt = auto()
    ctInt8 = auto()
    ctInt16 = auto()
    ctInt32 = auto()
    ctInt64 = auto()
    ctFloat = auto()
    ctFloat32 = auto()
    ctFloat64 = auto()
    ctFloat128 = auto()
    ctUInt = auto()
    ctUInt8 = auto()
    ctUInt16 = auto()
    ctUInt32 = auto()
    ctUInt64 = auto()
    ctArray = auto()
    ctPtrToArray = auto()
    ctStruct = auto()
    ctPtr = auto()
    ctNimStr = auto()
    ctNimSeq = auto()
    ctProc = auto()
    ctCString = auto()


class CodegenFlag(NIntEnum):
    preventStackTrace = 0
    usesThreadVars = auto()
    frameDeclared = auto()
    isHeaderFile = auto()
    includesStringh = auto()
    objHasKidsValid = auto()
    useAliveDataFromDce = auto()


@ref
class BModuleList(Object):
    config: ConfigRef
    graph: ModuleGraph
    nimtv: Builder
    nimtvDeps: seq[PType]
    nimtvDeclared: IntSet


@ref
class BModule(Object):
    g: BModuleList
    flags: Tset[CodegenFlag]
    module: PSym
    tmpBase: Rope
    labels: nint
    dataCache: TNodeTable
    s: array[TCFileSection, Builder]
    typeDescs: seq[string]

    @property
    def config(self) -> ConfigRef:
        return self.g.config

    # cgen.nim
    @property
    def compileToCpp(self) -> bool:
        return self.config.backend == TBackend.backendCpp or TSymFlag.sfCompileToCpp in self.module.flags

    @property
    def hcrOn(self) -> bool:
        return hcrOn(self.config)


@ref
class BProc(Object):
    prc: PSym
    module: BModule
    labels: nint
    flags: Tset[TCProcFlag]
    sections: array[TCProcSection, Builder]

    @property
    def config(self) -> ConfigRef:
        return self.module.g.config

    def procSec(self, s: TCProcSection) -> mut @ Builder:
        return self.sections[s]


@ufcs(BProc)
def s(p: BProc, s: TCProcSection) -> mut @ Builder:
    """{.inline.}"""
    # simplified: one block
    return p.sections[s]


def newProc(prc: PSym, module: BModule) -> BProc:
    # simplified: no options, one block
    result = BProc(prc=prc, module=module)
    return result


# --- cgen.nim (subset, before the C builders) ---
def getTempName(m: BModule) -> Rope:
    result = m.tmpBase + rope(m.labels)
    m.labels += 1
    return result


# --- ccgtypes.nim, cgen.nim (stubs used by the include files) ---
def getTypeDesc(m: BModule, t: PType) -> Snippet:
    m.typeDescs.add(t.name)
    return t.name


def finishTypeDescriptions(m: BModule) -> None:
    discard


def cgsym(m: BModule, name: string) -> None:
    # simplified: no compiler procs to generate
    discard


def cgsymValue(m: BModule, name: string) -> Snippet:
    return name


def newModuleForTest(config: ConfigRef) -> BModule:
    result = BModule(g=BModuleList(config=config, graph=ModuleGraph(config=config)), module=PSym(),
                     tmpBase=rope(string("TM__1_")))
    return result


def newProcForTest(m: BModule) -> BProc:
    result = BProc(module=m)
    return result
