# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# Test scaffolding (nimic_translation_rules.md §2.1): the context that cgen.nim gives its include files
# (cbuilderexprs, cbuilderstmts, ccgthreadvars, ...), for the modules that are not converted yet.
# Included by the harnesses in ncompiler/tests first; cgen_procs and cgen_stmts
# follow at their places in cgen.nim's include order. Each section is a subset of the named Nim
# module; procs are copied line for line where they are used. Converted modules (options, lineinfos, msgs,
# nodekinds, ropes, int128, cbuilderbase, std/intsets) are imported by the harness.

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


class TSymKind(NIntEnum):
    skUnknown = 0
    skConditional = auto()
    skDynLib = auto()
    skParam = auto()
    skGenericParam = auto()
    skTemp = auto()
    skModule = auto()
    skType = auto()
    skVar = auto()
    skLet = auto()
    skConst = auto()
    skResult = auto()
    skProc = auto()
    skFunc = auto()
    skMethod = auto()
    skIterator = auto()
    skConverter = auto()
    skMacro = auto()
    skTemplate = auto()
    skField = auto()
    skEnumField = auto()
    skForVar = auto()
    skLabel = auto()
    skStub = auto()
    skPackage = auto()


class TSymFlag(NIntEnum):
    sfUsed = 0
    sfExported = auto()
    sfImportc = auto()
    sfMainModule = auto()
    sfCompileToCpp = auto()
    sfThread = auto()
    sfPure = auto()
    sfNoReturn = auto()
    sfRegister = auto()
    sfVolatile = auto()
    sfNoalias = auto()
    sfCodegenDecl = auto()
    sfCppNonPod = auto()


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
    tfUnion = auto()


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
    typ: PType
    sons: seq[PNode]

    # ast.nim accessors
    @property
    def len(self) -> nint:
        return len(self.sons)

    def __getitem__(self, i: nint) -> PNode:
        return self.sons[i]

    def __setitem__(self, i: nint, son: PNode) -> None:
        self.sons[i] = son

    def add(self, son: PNode) -> None:
        assert son is not None
        self.sons.add(son)


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
    owner: PSym

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

    @property
    def itemId(self) -> nint:
        # simplified: the id (an ItemId object in astdef)
        return self.id

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
    kind: TSymKind
    name: string  # stand-in for the PIdent
    typ: PType
    flags: Tset[TSymFlag]
    loc: TLoc
    owner: PSym
    info: TLineInfo
    ast: PNode
    position: nint
    alignment: nint
    bitsize: nint
    constraint: PNode


@ref
class IdGenerator(Object):
    module: int32
    symId: int32
    typeId: int32
    sealed: bool

    def nextSymId(x: IdGenerator) -> nint:
        # simplified: a number instead of an ItemId
        x.symId += 1
        return nint(x.symId)

    def nextTypeId(x: IdGenerator) -> nint:
        # simplified: a number instead of an ItemId
        x.typeId += 1
        return nint(x.typeId)


with const:
    paramsPos = 3
    bodyPos = 6  # position of body; use rodread.getBody() instead!
    resultPos = 7
    declarativeDefs = Tset[TNodeKind]({TNodeKind.nkProcDef, TNodeKind.nkFuncDef, TNodeKind.nkMethodDef,
                                       TNodeKind.nkIteratorDef, TNodeKind.nkConverterDef})
    routineDefs = declarativeDefs + Tset[TNodeKind]({TNodeKind.nkMacroDef, TNodeKind.nkTemplateDef})
    nkEffectList = TNodeKind.nkArgList


# --- ast.nim (subset: the procs the include files use; simplified for the stand-in fields) ---
@dispatch
def setOwner(s: PSym, owner: PSym) -> None:
    """{.inline.}"""
    s.owner = owner


@dispatch
def setOwner(s: PType, owner: PSym) -> None:
    """{.inline.}"""
    s.owner = owner


def newSym(symKind: TSymKind, name: string, idgen: IdGenerator, owner: PSym, info: TLineInfo) -> PSym:
    # simplified: no options, offsets or disambiguation
    result = PSym(name=name, kind=symKind, info=info, id=idgen.nextSymId(), owner=owner)
    return result


def copySym(s: PSym, idgen: IdGenerator) -> PSym:
    # simplified: the fields of the stand-in PSym
    result = newSym(s.kind, s.name, idgen, s.owner, s.info)
    result.typ = s.typ
    result.flags = s.flags
    result.position = s.position
    result.loc = s.loc
    return result


def newType(kind: TTypeKind, idgen: IdGenerator, owner: PSym) -> PType:
    # simplified: no size, alignment or unique id
    result = PType(kind=kind, owner=owner, id=idgen.nextTypeId())
    return result


def _assignType(dest: PType, src: PType) -> None:
    # simplified: the fields of the stand-in PType
    dest.kind = src.kind
    dest.flags = src.flags
    dest.callConvImpl = src.callConvImpl
    dest.n = src.n
    dest.sizeImpl = src.sizeImpl
    dest.sonsImpl = src.sonsImpl


def copyType(t: PType, idgen: IdGenerator, owner: PSym) -> PType:
    result = newType(t.kind, idgen, owner)
    _assignType(result, t)
    result.sym = t.sym  # backend-info should not be copied
    return result


def rawAddSon(father: PType, son: PType) -> None:
    # simplified: no propagation of type flags to the owner
    if father.kind != TTypeKind.tyProc or father.sonsImpl.len == 0:
        father.sonsImpl.add(son)


def newNode(kind: TNodeKind) -> PNode:
    ## new node with unknown line info, no type, and no children
    return PNode(kind=kind, info=unknownLineInfo)


def newNodeI(kind: TNodeKind, info: TLineInfo) -> PNode:
    ## new node with line info, no type, and no children
    return PNode(kind=kind, info=info)


@dispatch
def newSymNode(sym: PSym, info: TLineInfo) -> PNode:
    result = newNode(TNodeKind.nkSym)
    result.sym = sym
    result.typ = sym.typ
    result.info = info
    return result


@dispatch
def newSymNode(sym: PSym) -> PNode:
    result = newNode(TNodeKind.nkSym)
    result.sym = sym
    result.typ = sym.typ
    result.info = sym.info
    return result


def copyNode(src: PNode) -> PNode:
    # does not copy its sons!
    # simplified: no flags, comments or floats
    if src is None:
        return None
    result = newNode(src.kind)
    result.info = src.info
    result.typ = src.typ
    match src.kind:
        case _ if src.kind in inrange(TNodeKind.nkCharLit, TNodeKind.nkUInt64Lit):
            result.intVal = src.intVal
        case TNodeKind.nkSym:
            result.sym = src.sym
        case _ if src.kind in inrange(TNodeKind.nkStrLit, TNodeKind.nkTripleStrLit):
            result.strVal = src.strVal
        case _:
            discard
    return result


@dispatch
def shallowCopy(src: PNode) -> PNode:
    # does not copy its sons, but provides space for them:
    result = copyNode(src)
    result.sons = newSeq[PNode](src.len)
    return result


def copyTree(src: PNode) -> PNode:
    # copy a whole syntax tree; performs deep copying
    if src is None:
        return None
    result = copyNode(src)
    result.sons = newSeq[PNode](src.len)
    for i in range(src.len):
        result[i] = copyTree(src[i])
    return result


@dispatch
def addParam(procType: PType, param: PSym) -> None:
    param.position = procType.n.len - 1
    procType.n.add(newSymNode(param))
    rawAddSon(procType, param.typ)


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


def lacksMTypeField(typ: PType) -> bool:
    """{.inline.}"""
    ## Returns true if the type is an object that lacks a m_type field.
    ## It doesn't check base classes.
    return (typ.sym is not None and TSymFlag.sfPure in typ.sym.flags) or TTypeFlag.tfFinal in typ.flags


def getSize(conf: ConfigRef, typ: PType) -> BiggestInt:
    # simplified: the size is preset
    return typ.size


def lengthOrd(conf: ConfigRef, t: PType) -> Int128:
    # simplified: t is a range type (lastOrd - firstOrd + 1)
    return toInt128(t.n[1].intVal - t.n[0].intVal + 1)


# --- extccomp.nim (subset) ---
class TInfoCCProp(NIntEnum):  # properties of the C compiler:
    hasSwitchRange = 0  # CC allows ranges in switch statements (GNU C)
    hasComputedGoto = auto()  # CC has computed goto (GNU C extension)
    hasCpp = auto()  # CC is/contains a C++ compiler
    hasAssume = auto()  # CC has __assume (Visual C extension)
    hasGcGuard = auto()  # CC supports GC_GUARD to keep stack roots
    hasGnuAsm = auto()  # CC's asm uses the absurd GNU assembler syntax
    hasDeclspec = auto()  # CC has __declspec(X)
    hasAttribute = auto()  # CC has __attribute__((X))
    hasBuiltinUnreachable = auto()  # CC has __builtin_unreachable


TInfoCCProps = Tset[TInfoCCProp]


class TInfoCC(NTuple):
    # simplified: the name and the properties of the compiler
    name: string
    props: TInfoCCProps


with const:
    _gccProps = TInfoCCProps({TInfoCCProp.hasSwitchRange, TInfoCCProp.hasComputedGoto, TInfoCCProp.hasCpp,
                              TInfoCCProp.hasGcGuard, TInfoCCProp.hasGnuAsm, TInfoCCProp.hasAttribute,
                              TInfoCCProp.hasBuiltinUnreachable})
    _vccProps = TInfoCCProps({TInfoCCProp.hasCpp, TInfoCCProp.hasAssume, TInfoCCProp.hasDeclspec})
    # simplified: gcc-like compilers have gcc's properties, Visual C-like ones vcc's
    CC = array[TSystemCC, TInfoCC]([
        TInfoCC(name=string("none"), props=TInfoCCProps()),
        TInfoCC(name=string("gcc"), props=_gccProps),
        TInfoCC(name=string("switch_gcc"), props=_gccProps),
        TInfoCC(name=string("llvm_gcc"), props=_gccProps),
        TInfoCC(name=string("clang"), props=_gccProps),
        TInfoCC(name=string("bcc"), props=TInfoCCProps({TInfoCCProp.hasSwitchRange, TInfoCCProp.hasComputedGoto,
                                                        TInfoCCProp.hasCpp, TInfoCCProp.hasGcGuard,
                                                        TInfoCCProp.hasAttribute})),
        TInfoCC(name=string("vcc"), props=_vccProps),
        TInfoCC(name=string("tcc"), props=TInfoCCProps({TInfoCCProp.hasSwitchRange, TInfoCCProp.hasComputedGoto,
                                                        TInfoCCProp.hasGnuAsm})),
        TInfoCC(name=string("env"), props=TInfoCCProps({TInfoCCProp.hasGnuAsm})),
        TInfoCC(name=string("icl"), props=_vccProps),
        TInfoCC(name=string("icc"), props=_gccProps),
        TInfoCC(name=string("clang_cl"), props=_vccProps),
        TInfoCC(name=string("hipcc"), props=_gccProps),
        TInfoCC(name=string("nvcc"), props=_gccProps),
    ])


# --- modulegraphs.nim, magicsys.nim (subset) ---
@ref
class ModuleGraph(Object):
    config: ConfigRef
    memberProcsPerType: Table[nint, seq[PSym]]  # simplified: keyed by the type id (an ItemId in Nim)


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
        return self.config.hcrOn()


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



# a module-level proc, not a method: ccgliterals.genStringLiteralV1 uses `s` itself as a value (`s.isNil`)
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
def isNoReturn(m: BModule, s: PSym) -> bool:
    """{.inline.}"""
    return TSymFlag.sfNoReturn in s.flags and m.config.exc != ExceptionSystem.excGoto


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
