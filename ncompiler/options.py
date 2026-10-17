from __future__ import annotations
from nimic.ntypes import *
from .lineinfos import *
from .platform import *
from .prefixmatches import *
from .pathutils import *
from .nimpaths import *

from nimic.std.tables import *
from nimic.std.os import *
from nimic.std.strutils import *
from nimic.std.strtabs import *
from nimic.std.sets import *
importFrom("nimic.std.terminal", "isatty")
importFrom("nimic.std.times", "utc", "fromUnix", "local", "getTime", "format", "DateTime")
importFrom("nimic.std.private.globs", "nativeToUnixPath")

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.syncio import *
    from nimic.std.assertions import *

with const:
    hasTinyCBackend = defined("tinyc")
    useEffectSystem = True
    useWriteTracking = False
    hasFFI = defined("nimHasLibFFI")
    copyrightYear = string("2026")

    nimEnableCovariance = defined("nimEnableCovariance")


class TOption(NIntEnum):
    optNone = 0
    optObjCheck = auto()
    optFieldCheck = auto()
    optRangeCheck = auto()
    optBoundsCheck = auto()
    optOverflowCheck = auto()
    optRefCheck = auto()
    optNaNCheck = auto()
    optInfCheck = auto()
    optStaticBoundsCheck = auto()
    optStyleCheck = auto()
    optAssert = auto()
    optLineDir = auto()
    optWarns = auto()
    optHints = auto()
    optOptimizeSpeed = auto()
    optOptimizeSize = auto()
    optStackTrace = auto()
    optStackTraceMsgs = auto()
    optLineTrace = auto()
    optByRef = auto()
    optProfiler = auto()
    optImplicitStatic = auto()
    optTrMacros = auto()
    optMemTracker = auto()
    optSinkInference = auto()
    optCursorInference = auto()
    optImportHidden = auto()
    optQuirky = auto()

class TOptions(Tset[TOption]): pass

class TGlobalOption(NIntEnum):
    gloptNone = 0
    optForceFullMake = auto()
    optWasNimscript = auto()
    optListCmd = auto()
    optCompileOnly = auto()
    optNoLinking = auto()
    optCDebug = auto()
    optGenDynLib = auto()
    optGenStaticLib = auto()
    optGenGuiApp = auto()
    optGenScript = auto()
    optGenCDeps = auto()
    optGenMapping = auto()
    optRun = auto()
    optUseNimcache = auto()
    optStyleHint = auto()
    optStyleError = auto()
    optStyleWarning = auto()
    optStyleUsages = auto()
    optSkipSystemConfigFile = auto()
    optSkipProjConfigFile = auto()
    optSkipUserConfigFile = auto()
    optSkipParentConfigFiles = auto()
    optNoMain = auto()
    optUseColors = auto()
    optThreads = auto()
    optStdout = auto()
    optThreadAnalysis = auto()
    optTlsEmulation = auto()
    optGenIndex = auto()
    optGenIndexOnly = auto()
    optNoImportdoc = auto()
    optEmbedOrigSrc = auto()
    optIdeDebug = auto()
    optIdeTerse = auto()
    optIdeExceptionInlayHints = auto()
    optExcessiveStackTrace = auto()
    optShowAllMismatches = auto()
    optWholeProject = auto()
    optDocInternal = auto()
    optMixedMode = auto()
    optDeclaredLocs = auto()
    optNoNimblePath = auto()
    optHotCodeReloading = auto()
    optDynlibOverrideAll = auto()
    optSeqDestructors = auto()
    optTinyRtti = auto()
    optOwnedRefs = auto()
    optMultiMethods = auto()
    optBenchmarkVM = auto()
    optProduceAsm = auto()
    optPanics = auto()
    optSourcemap = auto()
    optProfileVM = auto()
    optEnableDeepCopy = auto()
    optShowNonExportedFields = auto()
    optJsBigInt64 = auto()
    optDocRaw = auto()
    optItaniumMangle = auto()
    optCompress = auto()
    optWithinConfigSystem = auto()

class TGlobalOptions(Tset[TGlobalOption]): pass

with const:
    harmlessOptions = TGlobalOptions({TGlobalOption.optForceFullMake, TGlobalOption.optNoLinking, TGlobalOption.optRun, TGlobalOption.optUseColors, TGlobalOption.optStdout})
    genSubDir = RelativeDir(string("nimcache"))
    NimExt = string("nim")
    RodExt = string("rod")
    HtmlExt = string("html")
    JsonExt = string("json")
    TagsExt = string("tags")
    TexExt = string("tex")
    IniExt = string("ini")
    DefaultConfig = RelativeFile(string("nim.cfg"))
    DefaultConfigNims = RelativeFile(string("config.nims"))
    DocConfig = RelativeFile(string("nimdoc.cfg"))
    DocTexConfig = RelativeFile(string("nimdoc.tex.cfg"))
    htmldocsDir = RelativeDir(htmldocsDirname)
    docRootDefault = string("@default")
    oKeepVariableNames = True
    spellSuggestSecretSauce = -1

class TBackend(NStrEnum):
    backendInvalid = ""
    backendC = "c"
    backendCpp = "cpp"
    backendJs = "js"
    backendObjc = "objc"
    backendNif = "nif"

class Command(NIntEnum):
    cmdNone = 0
    cmdUnknown = auto()
    cmdCompileToC = auto()
    cmdCompileToCpp = auto()
    cmdCompileToOC = auto()
    cmdCompileToJS = auto()
    cmdCrun = auto()
    cmdTcc = auto()
    cmdCheck = auto()
    cmdM = auto()
    cmdParse = auto()
    cmdIdeTools = auto()
    cmdNimscript = auto()
    cmdDoc0 = auto()
    cmdDoc = auto()
    cmdDoc2tex = auto()
    cmdRst2html = auto()
    cmdRst2tex = auto()
    cmdMd2html = auto()
    cmdMd2tex = auto()
    cmdJsondoc0 = auto()
    cmdJsondoc = auto()
    cmdCtags = auto()
    cmdBuildindex = auto()
    cmdGendepend = auto()
    cmdDump = auto()
    cmdInteractive = auto()
    cmdNop = auto()
    cmdJsonscript = auto()
    cmdCompileToNif = auto()
    cmdNifC = auto()
    cmdIc = auto()

with const:
    cmdBackends = Tset[Command]({Command.cmdCompileToC, Command.cmdCompileToCpp, Command.cmdCompileToOC, Command.cmdCompileToJS, Command.cmdCrun, Command.cmdCompileToNif})
    cmdDocLike = Tset[Command]({Command.cmdDoc0, Command.cmdDoc, Command.cmdDoc2tex, Command.cmdJsondoc0, Command.cmdJsondoc, Command.cmdCtags, Command.cmdBuildindex})

class TStringSeq(seq[string]): pass

class TGCMode(NStrEnum):
    gcUnselected = "unselected"
    gcNone = "none"
    gcBoehm = "boehm"
    gcRegions = "regions"
    gcArc = "arc"
    gcOrc = "orc"
    gcYrc = "yrc"
    gcAtomicArc = "atomicArc"
    gcMarkAndSweep = "markAndSweep"
    gcHooks = "hooks"
    gcRefc = "refc"
    gcGo = "go"

class IdeCmd(NIntEnum):
    ideNone = 0
    ideSug = auto()
    ideCon = auto()
    ideDef = auto()
    ideUse = auto()
    ideDus = auto()
    ideChk = auto()
    ideChkFile = auto()
    ideMod = auto()
    ideHighlight = auto()
    ideOutline = auto()
    ideKnown = auto()
    ideMsg = auto()
    ideProject = auto()
    ideGlobalSymbols = auto()
    ideRecompile = auto()
    ideChanged = auto()
    ideType = auto()
    ideDeclaration = auto()
    ideExpand = auto()
    ideInlayHints = auto()

class Feature(NIntEnum):
    dotOperators = 0
    callOperator = auto()
    parallel = auto()
    destructor = auto()
    notnil = auto()
    dynamicBindSym = auto()
    forLoopMacros = auto()
    caseStmtMacros = auto()
    codeReordering = auto()
    compiletimeFFI = auto()
    vmopsDanger = auto()
    strictFuncs = auto()
    views = auto()
    strictNotNil = auto()
    overloadableEnums = auto()
    strictEffects = auto()
    unicodeOperators = auto()
    flexibleOptionalParams = auto()
    strictDefs = auto()
    strictCaseObjects = auto()
    inferGenericTypes = auto()
    openSym = auto()
    genericsOpenSym = auto()
    vtables = auto()
    typeBoundOps = auto()

class LegacyFeature(NIntEnum):
    allowSemcheckedAstModification = 0
    checkUnsignedConversions = auto()

class SymbolFilesOption(NIntEnum):
    disabledSf = 0
    writeOnlySf = auto()
    readOnlySf = auto()
    v2Sf = auto()
    stressTest = auto()

class TSystemCC(NIntEnum):
    ccNone = 0
    ccGcc = auto()
    ccNintendoSwitch = auto()
    ccLLVM_Gcc = auto()
    ccCLang = auto()
    ccBcc = auto()
    ccVcc = auto()
    ccTcc = auto()
    ccEnv = auto()
    ccIcl = auto()
    ccIcc = auto()
    ccClangCl = auto()
    ccHipcc = auto()
    ccNvcc = auto()

class StringsMode(NStrEnum):
    stringDefault = "default"
    stringSso = "sso"

class ExceptionSystem(NIntEnum):
    excNone = 0
    excSetjmp = auto()
    excCpp = auto()
    excGoto = auto()
    excQuirky = auto()

class CfileFlag(NIntEnum):
    Cached = 0
    External = auto()

class Cfile(Object):
    nimname: string
    cname: AbsoluteFile
    obj: AbsoluteFile
    flags: Tset[CfileFlag]
    customArgs: string

class CfileList(seq[Cfile]): pass

class SuggestInlayHintKind(NStrEnum):
    sihkType = "Type"
    sihkParameter = "Parameter"
    sihkException = "Exception"

class SuggestInlayHint(Object):
    kind: SuggestInlayHintKind
    line: nint
    column: nint
    label: string
    paddingLeft: bool
    paddingRight: bool
    allowInsert: bool
    tooltip: string

class Suggest(Object):
    section: IdeCmd
    qualifiedPath: seq[string]
    name: ptr[string]
    filePath: string
    line: nint
    column: nint
    doc: string
    forth: string
    quality: nint
    isGlobal: bool
    contextFits: bool
    prefix: PrefixMatch
    symkind: nint # byte
    scope: nint
    localUsages: nint
    globalUsages: nint
    tokenLen: nint
    version: nint
    endLine: nint # uint16
    endCol: nint
    inlayHintInfo: SuggestInlayHint

class Suggestions(seq[Suggest]): pass

class ProfileInfo(Object):
    time: float
    count: nint

@ref
@ref
class ProfileData(Object):
    data: TableRef[TLineInfo, ProfileInfo]

class StdOrrKind(NIntEnum):
    stdOrrStdout = 0
    stdOrrStderr = auto()

class FilenameOption(NIntEnum):
    foAbs = 0
    foRelProject = auto()
    foCanonical = auto()
    foLegacyRelProj = auto()
    foName = auto()
    foStacktrace = auto()

@calltype
def SuggestionResultHook(result: Suggest) -> None:
    """{.closure.}"""
    pass

@calltype
def WritelnHook(output: string) -> None:
    """{.closure, gcsafe.}"""
    pass

@calltype
def StructuredErrorHook(config: ConfigRef, info: TLineInfo, msg: string, severity: Severity) -> None:
    """{.closure, gcsafe.}"""
    pass

@ref
class ConfigRef(Object):
    backend: TBackend
    target: Target
    linesCompiled: nint
    options: TOptions
    globalOptions: TGlobalOptions
    macrosToExpand: StringTableRef
    arcToExpand: StringTableRef
    m: MsgConfig
    filenameOption: FilenameOption
    unitSep: string
    evalTemplateCounter: nint
    evalMacroCounter: nint
    exitcode: nint # int8
    cmd: Command
    cmdInput: string
    projectIsCmd: bool
    implicitCmd: bool
    selectedGC: TGCMode
    exc: ExceptionSystem
    selectedStrings: StringsMode
    hintProcessingDots: bool
    verbosity: nint
    numberOfProcessors: nint
    lastCmdTime: float
    symbolFiles: SymbolFilesOption
    ic: bool
    spellSuggestMax: nint

    cppDefines: HashSet[string]
    headerFile: string
    nimbasePattern: string
    features: Tset[Feature]
    legacyFeatures: Tset[LegacyFeature]
    arguments: string
    ideCmd: IdeCmd
    cCompiler: TSystemCC
    modifiedyNotes: TNoteKinds
    cmdlineNotes: TNoteKinds
    foreignPackageNotes: TNoteKinds
    notes: TNoteKinds
    warningAsErrors: TNoteKinds
    mainPackageNotes: TNoteKinds
    mainPackageId: nint
    errorCounter: nint
    hintCounter: nint
    warnCounter: nint
    errorMax: nint
    maxLoopIterationsVM: nint
    maxCallDepthVM: nint
    isVmTrace: bool
    configVars: StringTableRef
    symbols: StringTableRef
    packageCache: StringTableRef
    nimblePaths: seq[AbsoluteDir]
    searchPaths: seq[AbsoluteDir]
    lazyPaths: seq[AbsoluteDir]
    outFile: RelativeFile
    outDir: AbsoluteDir
    jsonBuildFile: AbsoluteFile
    prefixDir: AbsoluteDir
    libpath: AbsoluteDir
    nimcacheDir: AbsoluteDir
    dllOverrides: StringTableRef
    moduleOverrides: StringTableRef
    cfileSpecificOptions: StringTableRef
    projectName: string
    projectPath: AbsoluteDir
    projectFull: AbsoluteFile
    projectIsStdin: bool
    stdinFile: AbsoluteFile
    lastMsgWasDot: Tset[StdOrrKind]
    projectMainIdx: FileIndex
    projectMainIdx2: FileIndex
    command: string
    commandArgs: seq[string]
    commandLine: string
    extraCmds: seq[string]
    implicitImports: seq[string]
    implicitIncludes: seq[string]
    docSeeSrcUrl: string
    docRoot: string
    docCmd: string

    configFiles: seq[AbsoluteFile]
    cIncludes: seq[AbsoluteDir]
    cLibs: seq[AbsoluteDir]
    cLinkedLibs: seq[string]

    externalToLink: seq[string]
    linkOptionsCmd: string
    compileOptionsCmd: seq[string]
    linkOptions: string
    compileOptions: string
    cCompilerPath: string
    toCompile: CfileList
    suggestionResultHook: SuggestionResultHook
    suggestVersion: nint
    suggestMaxResults: nint
    lastLineInfo: TLineInfo
    writelnHook: WritelnHook
    structuredErrorHook: StructuredErrorHook
    cppCustomNamespace: string
    nimMainPrefix: string
    vmProfileData: ProfileData

    expandProgress: bool
    expandLevels: nint
    expandNodeResult: string
    expandPosition: TLineInfo

    currentConfigDir: string
    clientProcessId: nint

# TODO: requires nimic feature generic default parameters (`def = default(T)`): proc assignIfDefault*[T]
def assignIfDefault(result: mut@nint, val: nint, def_: nint = nint(0)) -> None:
    ## if `result` was already assigned to a value (that wasn't `def`), this is a noop.
    if result == def_:
        result <<= val


@template
def setErrorMaxHighMaybe(conf: ConfigRef):
    ## do not stop after first error (but honor --errorMax if provided)
    assignIfDefault(conf.errorMax, high(nint))

@template_expand
def setNoteDefaults(conf: ConfigRef, note: TNoteKind, enabled: bool = True) -> None:
    @template
    def fun(op: untyped):
        conf.notes.op(note)
        conf.mainPackageNotes.op(note)
        conf.foreignPackageNotes.op(note)
    if enabled:
        fun(incl)
    else:
        fun(excl)

def setNote(conf: ConfigRef, note: TNoteKind, enabled: bool = True) -> None:
    # see also `prepareConfigNotes` which sets notes
    if note not in conf.cmdlineNotes:
        if enabled:
            conf.notes.incl(note)
        else:
            conf.notes.excl(note)

def hasHint(conf: ConfigRef, note: TNoteKind) -> bool:
    # ternary states instead of binary states would simplify logic
    if TOption.optHints not in conf.options:
        return False
    elif note in {TMsgKind.hintConf, TMsgKind.hintProcessing}:
        # could add here other special notes like hintSource
        # these notes apply globally.
        return note in conf.mainPackageNotes
    else:
        return note in conf.notes


def hasWarn(conf: ConfigRef, note: TNoteKind) -> bool:
    """{.inline.}"""
    return TOption.optWarns in conf.options and note in conf.notes

def hcrOn(conf: ConfigRef) -> bool:
    return TGlobalOption.optHotCodeReloading in conf.globalOptions

if comptime(False):
    @template
    def depConfigFields(fn: untyped):
        """{.dirty.}"""
        # deadcode
        fn(target)
        fn(options)
        fn(globalOptions)
        fn(selectedGC)

with const:
    oldExperimentalFeatures = Tset[Feature]({Feature.dotOperators, Feature.callOperator, Feature.parallel})
    ChecksOptions = Tset[TOption]({TOption.optObjCheck, TOption.optFieldCheck, TOption.optRangeCheck,
        TOption.optOverflowCheck, TOption.optBoundsCheck, TOption.optAssert, TOption.optNaNCheck, TOption.optInfCheck,
        TOption.optStyleCheck})
    DefaultOptions = Tset[TOption]({TOption.optObjCheck, TOption.optFieldCheck, TOption.optRangeCheck,
        TOption.optBoundsCheck, TOption.optOverflowCheck, TOption.optAssert, TOption.optWarns, TOption.optRefCheck,
        TOption.optHints, TOption.optStackTrace, TOption.optLineTrace,
        TOption.optTrMacros, TOption.optStyleCheck, TOption.optCursorInference})
    DefaultGlobalOptions = Tset[TGlobalOption]({TGlobalOption.optThreadAnalysis, TGlobalOption.optExcessiveStackTrace,
        TGlobalOption.optJsBigInt64, TGlobalOption.optItaniumMangle})

def _getSrcTimestamp() -> DateTime:
    try:
        result = utc(fromUnix(parseInt(getEnv(string("SOURCE_DATE_EPOCH"),
                                              string("not a number")))))
    except ValueError:
        # Environment variable malformed.
        # https://reproducible-builds.org/specs/source-date-epoch/: "If the
        # value is malformed, the build process SHOULD exit with a non-zero
        # error code", which this doesn't do. This uses local time, because
        # that maintains compatibility with existing usage.
        result = utc(getTime())
    return result

def getDateStr() -> string:
    return format(_getSrcTimestamp(), string("yyyy-MM-dd"))

def getClockStr() -> string:
    return format(_getSrcTimestamp(), string("HH:mm:ss"))

@template
def newPackageCache() -> untyped:
    return newStringTable(StringTableMode.modeCaseInsensitive if comptime(FileSystemCaseSensitive)
                          else StringTableMode.modeCaseSensitive)


def _newProfileData() -> ProfileData:
    return ProfileData(data=newTable[TLineInfo, ProfileInfo]())


with const:
    foreignPackageNotesDefault = Tset[TNoteKind]({
        TMsgKind.hintProcessing, TMsgKind.warnUnknownMagic, TMsgKind.hintQuitCalled, TMsgKind.hintExecuting, TMsgKind.hintUser, TMsgKind.warnUser})


def isDefined(conf: ConfigRef, symbol: string) -> bool:
    pass


if comptime(defined("nimDebugUtils")):
    # this allows inserting debugging utilties in all modules that import `options`
    # with a single switch, which is useful when debugging compiler.
    from .debugutils import *
    with export:
        debugutils


def _initConfigRefCommon(conf: ConfigRef) -> None:
    conf.selectedGC = TGCMode.gcUnselected
    conf.verbosity = 1
    conf.hintProcessingDots = True
    conf.options = DefaultOptions.copy()
    conf.globalOptions = DefaultGlobalOptions.copy()
    conf.filenameOption = FilenameOption.foAbs
    conf.foreignPackageNotes = foreignPackageNotesDefault.copy()
    conf.notes = NotesVerbosity[1].copy()
    conf.mainPackageNotes = NotesVerbosity[1].copy()


def newConfigRef() -> ConfigRef:
    result = ConfigRef(
        cCompiler=TSystemCC.ccGcc,
        macrosToExpand=newStringTable(StringTableMode.modeStyleInsensitive),
        arcToExpand=newStringTable(StringTableMode.modeStyleInsensitive),
        m=initMsgConfig(),
        cppDefines=initHashSet[string](),
        headerFile=string(""), features=Tset[Feature](), legacyFeatures=Tset[LegacyFeature](),
        configVars=newStringTable(StringTableMode.modeStyleInsensitive),
        symbols=newStringTable(StringTableMode.modeStyleInsensitive),
        packageCache=newPackageCache(),
        searchPaths=seq[AbsoluteDir](),
        lazyPaths=seq[AbsoluteDir](),
        outFile=RelativeFile(string("")),
        outDir=AbsoluteDir(string("")),
        prefixDir=AbsoluteDir(string("")),
        libpath=AbsoluteDir(string("")), nimcacheDir=AbsoluteDir(string("")),
        dllOverrides=newStringTable(StringTableMode.modeCaseInsensitive),
        moduleOverrides=newStringTable(StringTableMode.modeStyleInsensitive),
        cfileSpecificOptions=newStringTable(StringTableMode.modeCaseSensitive),
        projectName=string(""),  # holds a name like 'nim'
        projectPath=AbsoluteDir(string("")),  # holds a path like /home/alice/projects/nim/compiler/
        projectFull=AbsoluteFile(string("")),  # projectPath/projectName
        projectIsStdin=False,  # whether we're compiling from stdin
        stdinFile=AbsoluteFile(string("stdinfile")),
        projectMainIdx=FileIndex(int32(0)),  # the canonical path id of the main module
        command=string(""),  # the main command (e.g. cc, check, scan, etc)
        commandArgs=seq[string](),  # any arguments after the main command
        commandLine=string(""),
        implicitImports=seq[string](),  # modules that are to be implicitly imported
        implicitIncludes=seq[string](),  # modules that are to be implicitly included
        docSeeSrcUrl=string(""),
        cIncludes=seq[AbsoluteDir](),  # directories to search for included files
        cLibs=seq[AbsoluteDir](),  # directories to search for lib files
        cLinkedLibs=seq[string](),  # libraries to link
        backend=TBackend.backendInvalid,
        externalToLink=seq[string](),
        linkOptionsCmd=string(""),
        compileOptionsCmd=seq[string](),
        linkOptions=string(""),
        compileOptions=string(""),
        cCompilerPath=string(""),
        toCompile=CfileList(),
        arguments=string(""),
        suggestMaxResults=10_000,
        maxLoopIterationsVM=10_000_000,
        maxCallDepthVM=2_000,
        vmProfileData=_newProfileData(),
        spellSuggestMax=spellSuggestSecretSauce,
        currentConfigDir=string("")
    )
    _initConfigRefCommon(result)
    setTargetFromSystem(result.target)
    # enable colors by default on terminals
    if isatty(stderr):
        incl(result.globalOptions, TGlobalOption.optUseColors)
    if comptime(defined("nimDebugUtils")):
        onNewConfigRef(result)
    return result


def newPartialConfigRef() -> ConfigRef:
    ## create a new ConfigRef that is only good enough for error reporting.
    if comptime(defined("nimDebugUtils")):
        result = getConfigRef()
    else:
        result = ConfigRef()
        _initConfigRefCommon(result)
    return result


def cppDefine(c: ConfigRef, define: string) -> None:
    c.cppDefines.incl(define)

def isDefined(conf: ConfigRef, symbol: string) -> bool:
    if conf.symbols.hasKey(symbol):
        result = True
    elif cmpIgnoreStyle(symbol, CPU[conf.target.targetCPU].name) == 0:
        result = True
    elif cmpIgnoreStyle(symbol, OS[conf.target.targetOS].name) == 0:
        result = True
    else:
        match normalize(symbol):
            case "x86": result = conf.target.targetCPU == TSystemCPU.cpuI386
            case "itanium": result = conf.target.targetCPU == TSystemCPU.cpuIa64
            case "x8664": result = conf.target.targetCPU == TSystemCPU.cpuAmd64
            case "posix" | "unix":
                result = conf.target.targetOS in {TSystemOS.osLinux, TSystemOS.osMorphos, TSystemOS.osSkyos, TSystemOS.osIrix, TSystemOS.osPalmos,
                                    TSystemOS.osQnx, TSystemOS.osAtari, TSystemOS.osAix,
                                    TSystemOS.osHaiku, TSystemOS.osVxWorks, TSystemOS.osSolaris, TSystemOS.osNetbsd,
                                    TSystemOS.osFreebsd, TSystemOS.osOpenbsd, TSystemOS.osDragonfly, TSystemOS.osMacosx, TSystemOS.osIos,
                                    TSystemOS.osAndroid, TSystemOS.osNintendoSwitch, TSystemOS.osFreeRTOS, TSystemOS.osCrossos, TSystemOS.osZephyr, TSystemOS.osNuttX}
            case "linux":
                result = conf.target.targetOS in {TSystemOS.osLinux, TSystemOS.osAndroid}
            case "bsd":
                result = conf.target.targetOS in {TSystemOS.osNetbsd, TSystemOS.osFreebsd, TSystemOS.osOpenbsd, TSystemOS.osDragonfly, TSystemOS.osCrossos}
            case "freebsd":
                result = conf.target.targetOS in {TSystemOS.osFreebsd, TSystemOS.osCrossos}
            case "emulatedthreadvars":
                result = OS[conf.target.targetOS].props.contains(TInfoOSProp.ospLacksThreadVars)
            case "msdos": result = conf.target.targetOS == TSystemOS.osDos
            case "mswindows" | "win32": result = conf.target.targetOS == TSystemOS.osWindows
            case "macintosh":
                result = conf.target.targetOS in {TSystemOS.osMacos, TSystemOS.osMacosx, TSystemOS.osIos}
            case "osx" | "macosx":
                result = conf.target.targetOS in {TSystemOS.osMacosx, TSystemOS.osIos}
            case "sunos": result = conf.target.targetOS == TSystemOS.osSolaris
            case "nintendoswitch":
                result = conf.target.targetOS == TSystemOS.osNintendoSwitch
            case "freertos" | "lwip":
                result = conf.target.targetOS == TSystemOS.osFreeRTOS
            case "zephyr":
                result = conf.target.targetOS == TSystemOS.osZephyr
            case "nuttx":
                result = conf.target.targetOS == TSystemOS.osNuttX
            case "littleendian": result = CPU[conf.target.targetCPU].endian == Endianness.littleEndian
            case "bigendian": result = CPU[conf.target.targetCPU].endian == Endianness.bigEndian
            case "cpu8": result = CPU[conf.target.targetCPU].bit == 8
            case "cpu16": result = CPU[conf.target.targetCPU].bit == 16
            case "cpu32": result = CPU[conf.target.targetCPU].bit == 32
            case "cpu64": result = CPU[conf.target.targetCPU].bit == 64
            case "nimrawsetjmp":
                result = conf.target.targetOS in {TSystemOS.osSolaris, TSystemOS.osNetbsd, TSystemOS.osFreebsd, TSystemOS.osOpenbsd,
                                    TSystemOS.osDragonfly, TSystemOS.osMacosx}
            case _: result = False
    return result

@template
def quitOrRaise(conf: ConfigRef, msg: string = string("")):
    # xxx in future work, consider whether to also intercept `msgQuit` calls
    if isDefined(conf, string("nimDebug")):
        raiseAssert(msg)
    else:
        quit(msg)  # quits with QuitFailure


def importantComments(conf: ConfigRef) -> bool:
    """{.inline.}"""
    return conf.cmd in cmdDocLike + Tset[Command]({Command.cmdIdeTools})


def usesWriteBarrier(conf: ConfigRef) -> bool:
    """{.inline.}"""
    return conf.selectedGC >= TGCMode.gcRefc


def usesSso(conf: ConfigRef) -> bool:
    """{.inline.}"""
    return conf.selectedStrings == StringsMode.stringSso


@template
def compilationCachePresent(conf: ConfigRef) -> untyped:
    return False
    #  conf.symbolFiles in {v2Sf, writeOnlySf}


@template
def optPreserveOrigSource(conf: ConfigRef) -> untyped:
    return TGlobalOption.optEmbedOrigSrc in conf.globalOptions


def mainCommandArg(conf: ConfigRef) -> string:
    ## This is intended for commands like check or parse
    ## which will work on the main project file unless
    ## explicitly given a specific file argument
    if conf.commandArgs.len > 0:
        result = conf.commandArgs[0]
    else:
        result = conf.projectName
    return result


def existsConfigVar(conf: ConfigRef, key: string) -> bool:
    result = hasKey(conf.configVars, key)
    return result


def getConfigVar(conf: ConfigRef, key: string, default: string = string("")) -> string:
    result = conf.configVars.getOrDefault(key, default)
    return result


def setConfigVar(conf: ConfigRef, key: string, val: string) -> None:
    conf.configVars[key] = val


def getOutFile(conf: ConfigRef, filename: RelativeFile, ext: string) -> AbsoluteFile:
    # explains regression https://github.com/nim-lang/Nim/issues/6583#issuecomment-625711125
    # Yet another reason why "" should not mean ".";  `""/something` should raise
    # instead of implying "" == "." as it's bug prone.
    doAssert(string(conf.outDir).len > 0)
    result = conf.outDir / changeFileExt(filename, ext)
    return result


def absOutFile(conf: ConfigRef) -> AbsoluteFile:
    doAssert(not isEmpty(conf.outDir))
    doAssert(not isEmpty(conf.outFile))
    result = conf.outDir / conf.outFile
    if comptime(defined("posix")):
        if dirExists(string(result)):
            string(result).add(string(".out"))
    return result


def prepareToWriteOutput(conf: ConfigRef) -> AbsoluteFile:
    ## Create the output directory and returns a full path to the output file
    result = absOutFile(conf)
    createDir(parentDir(string(result)))
    return result


def getPrefixDir(conf: ConfigRef) -> AbsoluteDir:
    ## Gets the prefix dir, usually the parent directory where the binary resides.
    ##
    ## This is overridden by some tools (namely nimsuggest) via the ``conf.prefixDir``
    ## field.
    ## This should resolve to root of nim sources, whether running nim from a local
    ##  clone or using installed nim, so that these exist: `result/doc/advopt.txt`
    ## and `result/lib/system.nim`
    if not isEmpty(conf.prefixDir):
        result = conf.prefixDir
    else:
        with let:
            binParent = AbsoluteDir(splitPath(getAppDir()).head)
        if comptime(defined("posix")):
            if binParent == AbsoluteDir(string("/usr")):
                result = AbsoluteDir(string("/usr/lib/nim"))
            elif binParent == AbsoluteDir(string("/usr/local")):
                result = AbsoluteDir(string("/usr/local/lib/nim"))
            else:
                result = binParent
        else:
            result = binParent
    return result


def setDefaultLibpath(conf: ConfigRef) -> None:
    # set default value (can be overwritten):
    if isEmpty(conf.libpath):
        # choose default libpath:
        with var:
            prefix = getPrefixDir(conf)
        conf.libpath = prefix / RelativeDir(string("lib"))

        # Special rule to support other tools (nimble) which import the compiler
        # modules and make use of them.
        with let:
            realNimPath = findExe(string("nim"))
        # Find out if $nim/../../lib/system.nim exists.
        with let:
            parentNimLibPath = parentDir(parentDir(realNimPath)) / string("lib")
        if not fileExists(string(conf.libpath) / string("system.nim")) and \
                fileExists(parentNimLibPath / string("system.nim")):
            conf.libpath = AbsoluteDir(parentNimLibPath)


def canonicalizePath(conf: ConfigRef, path: AbsoluteFile) -> AbsoluteFile:
    result = AbsoluteFile(expandFilename(string(path)))
    return result


def setFromProjectName(conf: ConfigRef, projectName: string) -> None:
    try:
        conf.projectFull = canonicalizePath(conf, AbsoluteFile(projectName))
    except OSError:
        conf.projectFull = AbsoluteFile(projectName)
    with let:
        p = splitFile(conf.projectFull)
        dir = AbsoluteDir(getCurrentDir()) if isEmpty(p.dir) else p.dir
    try:
        conf.projectPath = AbsoluteDir(canonicalizePath(conf, AbsoluteFile(dir)))
    except OSError:
        conf.projectPath = dir
    conf.projectName = p.name


def removeTrailingDirSep(path: string) -> string:
    if (path.len > 0) and (path[path.len - 1] == DirSep):
        result = substr(path, 0, path.len - 2)
    else:
        result = path
    return result


def disableNimblePath(conf: ConfigRef) -> None:
    incl(conf.globalOptions, TGlobalOption.optNoNimblePath)
    conf.lazyPaths.setLen(0)
    conf.nimblePaths.setLen(0)


def clearNimblePath(conf: ConfigRef) -> None:
    conf.lazyPaths.setLen(0)
    conf.nimblePaths.setLen(0)


include("packagehandling")


def _getOsCacheDir() -> string:
    if comptime(defined("posix")):
        result = getEnv(string("XDG_CACHE_HOME"), getHomeDir() / string(".cache")) / string("nim")
    else:
        result = getHomeDir() / string(genSubDir)
    return result


def getNimcacheDir(conf: ConfigRef) -> AbsoluteDir:
    def nimcacheSuffix(conf: ConfigRef) -> string:
        if conf.cmd == Command.cmdCheck:
            return string("_check")
        elif isDefined(conf, string("release")) or isDefined(conf, string("danger")):
            return string("_r")
        else:
            return string("_d")

    # XXX projectName should always be without a file extension!
    result = (conf.nimcacheDir if not isEmpty(conf.nimcacheDir)
              else (conf.projectPath / genSubDir if isEmpty(conf.outDir) else conf.outDir / genSubDir)
              if conf.backend == TBackend.backendJs
              else AbsoluteDir(_getOsCacheDir() / splitFile(conf.projectName).name +
                               nimcacheSuffix(conf)))
    return result


def pathSubs(conf: ConfigRef, p: string, config: string) -> string:
    with let:
        home = removeTrailingDirSep(getHomeDir())
    result = expandTilde(unixToNativePath(p % [
        string("nim"), string(getPrefixDir(conf)),
        string("lib"), string(conf.libpath),
        string("home"), home,
        string("config"), config,
        string("projectname"), conf.projectName,
        string("projectpath"), string(conf.projectPath),
        string("projectdir"), string(conf.projectPath),
        string("nimcache"), string(getNimcacheDir(conf))]))
    return result


def nimbleSubs(conf: ConfigRef, p: string) -> string:
    with let:
        pl = toLowerAscii(p)
    if string("$nimblepath") in pl or string("$nimbledir") in pl:
        for i in range(conf.nimblePaths.len - 1, -1, -1):
            with let:
                nimblePath = removeTrailingDirSep(string(conf.nimblePaths[i]))
            yield p % [string("nimblepath"), nimblePath, string("nimbledir"), nimblePath]
    else:
        yield p


def toGeneratedFile(conf: ConfigRef, path: AbsoluteFile, ext: string) -> AbsoluteFile:
    ## converts "/home/a/mymodule.nim", "rod" to "/home/a/nimcache/mymodule.rod"
    result = getNimcacheDir(conf) / RelativeFile(changeFileExt(splitPath(string(path)).tail, ext))
    return result


def completeGeneratedFilePath(conf: ConfigRef, f: AbsoluteFile, createSubDir: bool = True) -> AbsoluteFile:
    ## Return an absolute path of a generated intermediary file.
    ## Optionally creates the cache directory if `createSubDir` is `true`.
    with let:
        subdir = getNimcacheDir(conf)
    if createSubDir:
        try:
            createDir(string(subdir))
        except OSError:
            quitOrRaise(conf, string("cannot create directory: ") + string(subdir))
    result = subdir / RelativeFile(splitPath(string(f)).tail)
    return result


def _rawFindFile(conf: ConfigRef, f: RelativeFile, suppressStdlib: bool) -> AbsoluteFile:
    for it in conf.searchPaths:
        if suppressStdlib and startsWith(string(it), string(conf.libpath)):
            continue
        result = it / f
        if fileExists(result):
            return canonicalizePath(conf, result)
    result = AbsoluteFile(string(""))
    return result


def _rawFindFile2(conf: ConfigRef, f: RelativeFile) -> AbsoluteFile:
    for i, it in pairs(conf.lazyPaths):
        result = it / f
        if fileExists(result):
            # bring to front
            for j in range(i, 0, -1):
                (conf.lazyPaths[j], conf.lazyPaths[j - 1]) = (conf.lazyPaths[j - 1], conf.lazyPaths[j])

            return canonicalizePath(conf, result)
    result = AbsoluteFile(string(""))
    return result


@template
def _patchModule(conf: ConfigRef):
    """{.dirty.}"""
    if not isEmpty(result) and conf.moduleOverrides.len > 0:
        with let:
            key = getPackageName(conf, string(result)) + string("_") + splitFile(result).name
        if conf.moduleOverrides.hasKey(key):
            with let:
                ov = conf.moduleOverrides[key]
            if ov.len > 0:
                result = AbsoluteFile(ov)


with const:
    stdlibDirs = [
        string("pure"), string("core"), string("arch"),
        string("pure/collections"),
        string("pure/concurrency"),
        string("pure/unidecode"), string("impure"),
        string("wrappers"), string("wrappers/linenoise"),
        string("windows"), string("posix"), string("js"),
        string("deprecated/pure")]

with const:
    _pkgPrefix = string("pkg/")
    stdPrefix = string("std/")


@template_expand
def getRelativePathFromConfigPath(conf: ConfigRef, f: AbsoluteFile, isTitle: bool = False) -> RelativeFile:
    result = RelativeFile(string(""))
    with let:
        f_str = string(f)
    if isTitle:
        for dir in stdlibDirs:
            with let:
                path = string(conf.libpath) / dir / lastPathPart(f_str)
            if cmpPaths(path, f_str) == 0:
                return RelativeFile(stdPrefix + splitFile(f_str)[1])

    @template
    def search(paths: untyped):
        for it in paths:
            with let:
                it_str = string(it)
            if isRelativeTo(f_str, it_str):
                return RelativeFile(relativePath(f_str, it_str))
    search(conf.searchPaths)
    search(conf.lazyPaths)
    return result


@template_expand
def findFile(conf: ConfigRef, f: string, suppressStdlib: bool = False) -> AbsoluteFile:
    if isAbsolute(f):
        result = AbsoluteFile(f) if fileExists(f) else AbsoluteFile(string(""))
    else:
        result = _rawFindFile(conf, RelativeFile(f), suppressStdlib)
        if isEmpty(result):
            result = _rawFindFile(conf, RelativeFile(toLowerAscii(f)), suppressStdlib)
            if isEmpty(result):
                result = _rawFindFile2(conf, RelativeFile(f))
                if isEmpty(result):
                    result = _rawFindFile2(conf, RelativeFile(toLowerAscii(f)))
    _patchModule(conf)
    return result


@template_expand
def findModule(conf: ConfigRef, modulename: string, currentModule: string) -> AbsoluteFile:
    # returns path to module
    with var:
        m = addFileExt(modulename, NimExt)
        hasRelativeDot = False
    if startsWith(m, _pkgPrefix):
        result = findFile(conf, substr(m, _pkgPrefix.len), suppressStdlib=True)
    else:
        if startsWith(m, stdPrefix):
            result = AbsoluteFile(string(""))
            with let:
                stripped = substr(m, stdPrefix.len)
            for candidate in stdlibDirs:
                with let:
                    path = (string(conf.libpath) / candidate / stripped)
                if fileExists(path):
                    result = AbsoluteFile(path)
                    break
        else:  # If prefixed with std/ why would we add the current module path!
            with let:
                currentPath = splitFile(currentModule).dir
            result = AbsoluteFile(currentPath / m)
            if startsWith(m, ch('.')) and not fileExists(result):
                result = AbsoluteFile(string(""))
                hasRelativeDot = True

        if not fileExists(result) and not hasRelativeDot:
            result = findFile(conf, m)
    _patchModule(conf)
    return result


def findProjectNimFile(conf: ConfigRef, pkg: string) -> string:
    with const:
        extensions = [string(".nims"), string(".cfg"), string(".nimcfg"), string(".nimble")]
    with var:
        candidates: seq[string] = seq[string]()
        dir = pkg.copy()
        prev = dir.copy()
        nimblepkg = string("")
    with let:
        pkgname = lastPathPart(pkg)
    while True:
        for k, f in walkDir(dir, relative=True):
            if k == pcFile and f != string("config.nims"):
                with let:
                    (_, name, ext) = splitFile(f)
                if ext in extensions:
                    with let:
                        x = changeFileExt(dir / name, string(".nim"))
                    if fileExists(x):
                        candidates.add(x)
                    if ext == string(".nimble"):
                        if nimblepkg.len == 0:
                            nimblepkg = name
                            # Since nimble packages can have their source in a subfolder,
                            # check the last folder we were in for a possible match.
                            if dir != prev:
                                with let:
                                    x = prev / extractFilename(x)
                                if fileExists(x):
                                    candidates.add(x)
                        else:
                            # If we found more than one nimble file, chances are that we
                            # missed the real project file, or this is an invalid nimble
                            # package. Either way, bailing is the better choice.
                            return string("")
        with let:
            pkgname = nimblepkg if nimblepkg.len > 0 else pkgname
        for c in candidates:
            if pkgname in extractFilename(c):
                return c
        if candidates.len > 0:
            return candidates[0]
        prev = dir
        dir = parentDir(dir)
        if dir == string(""):
            break
    return string("")


def canonicalImportAux(conf: ConfigRef, file: AbsoluteFile) -> string:
    ##[
    ## Shows the canonical module import, e.g.:
    ## system, std/tables, fusion/pointers, system/assertions, std/private/asciitables
    ##]##
    with var:
        ret = getRelativePathFromConfigPath(conf, file, isTitle=True)
    with let:
        dir = AbsoluteDir(parentDir(getNimbleFile(conf, string(str(file)))))
    if not isEmpty(dir):
        with let:
            relPath = relativeTo(file, dir)
        if not isEmpty(relPath) and (isEmpty(ret) or string(relPath).len < string(ret).len):
            ret = relPath
    if isEmpty(ret):
        ret = relativeTo(file, conf.projectPath)
    result = string(ret)
    return result


def canonicalImport(conf: ConfigRef, file: AbsoluteFile) -> string:
    with let:
        ret = canonicalImportAux(conf, file)
    result = changeFileExt(nativeToUnixPath(ret), string(""))
    return result


def _canonDynlibName(s: string) -> string:
    with let:
        start = 3 if startsWith(s, string("lib")) else 0
        ende = find(s, Tset[char]({ch('('), ch(')'), ch('.')}))
    if ende >= 0:
        result = substr(s, start, ende - 1)
    else:
        result = substr(s, start)
    return result


def inclDynlibOverride(conf: ConfigRef, lib: string) -> None:
    conf.dllOverrides[_canonDynlibName(lib)] = string("true")


def isDynlibOverride(conf: ConfigRef, lib: string) -> bool:
    result = (TGlobalOption.optDynlibOverrideAll in conf.globalOptions or
              conf.dllOverrides.hasKey(_canonDynlibName(lib)))
    return result


def showNonExportedFields(conf: ConfigRef) -> None:
    incl(conf.globalOptions, TGlobalOption.optShowNonExportedFields)


def docRawOutput(conf: ConfigRef) -> None:
    incl(conf.globalOptions, TGlobalOption.optDocRaw)


def expandDone(conf: ConfigRef) -> bool:
    result = conf.ideCmd == IdeCmd.ideExpand and conf.expandLevels == 0 and conf.expandProgress
    return result


def parseIdeCmd(s: string) -> IdeCmd:
    match s:
        case "sug": return IdeCmd.ideSug
        case "con": return IdeCmd.ideCon
        case "def": return IdeCmd.ideDef
        case "use": return IdeCmd.ideUse
        case "dus": return IdeCmd.ideDus
        case "chk": return IdeCmd.ideChk
        case "chkFile": return IdeCmd.ideChkFile
        case "mod": return IdeCmd.ideMod
        case "highlight": return IdeCmd.ideHighlight
        case "outline": return IdeCmd.ideOutline
        case "known": return IdeCmd.ideKnown
        case "msg": return IdeCmd.ideMsg
        case "project": return IdeCmd.ideProject
        case "globalSymbols": return IdeCmd.ideGlobalSymbols
        case "recompile": return IdeCmd.ideRecompile
        case "changed": return IdeCmd.ideChanged
        case "type": return IdeCmd.ideType
        case _: return IdeCmd.ideNone


@ufcs(IdeCmd)
def __str__(c: IdeCmd) -> string:
    match c:
        case IdeCmd.ideSug: return "sug"
        case IdeCmd.ideCon: return "con"
        case IdeCmd.ideDef: return "def"
        case IdeCmd.ideUse: return "use"
        case IdeCmd.ideDus: return "dus"
        case IdeCmd.ideChk: return "chk"
        case IdeCmd.ideChkFile: return "chkFile"
        case IdeCmd.ideMod: return "mod"
        case IdeCmd.ideNone: return "none"
        case IdeCmd.ideHighlight: return "highlight"
        case IdeCmd.ideOutline: return "outline"
        case IdeCmd.ideKnown: return "known"
        case IdeCmd.ideMsg: return "msg"
        case IdeCmd.ideProject: return "project"
        case IdeCmd.ideGlobalSymbols: return "globalSymbols"
        case IdeCmd.ideDeclaration: return "declaration"
        case IdeCmd.ideExpand: return "expand"
        case IdeCmd.ideRecompile: return "recompile"
        case IdeCmd.ideChanged: return "changed"
        case IdeCmd.ideType: return "type"
        case IdeCmd.ideInlayHints: return "inlayHints"


def floatInt64Align(conf: ConfigRef) -> int16:
    ## Returns either 4 or 8 depending on reasons.
    if conf is not None and conf.target.targetCPU == TSystemCPU.cpuI386:
        #on Linux/BSD i386, double are aligned to 4bytes (except with -malign-double)
        if conf.target.targetOS != TSystemOS.osWindows:
            # on i386 for all known POSIX systems, 64bits ints are aligned
            # to 4bytes (except with -malign-double)
            return int16(4)
    return int16(8)

if comptime(__name__ == "__main__"):
    echo("Running options.py tests...")
    with var:
        # 1. newConfigRef initialization
        conf = newConfigRef()
        pconf = newPartialConfigRef()
        rel = RelativeFile(string(""))


    assert conf.cCompiler == TSystemCC.ccGcc
    assert conf.verbosity == 1
    assert conf.hintProcessingDots == True
    assert TOption.optObjCheck in conf.options
    assert TGlobalOption.optThreadAnalysis in conf.globalOptions
    assert len(conf.m.errorOutputs) > 0
    assert len(conf.notes) > 0

    # 2. newPartialConfigRef
    assert pconf.verbosity == 1
    assert len(pconf.m.errorOutputs) == 0  # only good enough for error reporting: no initMsgConfig
    assert pconf.filenameOption == FilenameOption.foAbs


    # 3. Notes manipulation
    setNoteDefaults(conf, TMsgKind.hintProcessing, True)
    assert hasHint(conf, TMsgKind.hintProcessing)
    assert TMsgKind.hintProcessing in conf.mainPackageNotes and TMsgKind.hintProcessing in conf.foreignPackageNotes
    setNoteDefaults(conf, TMsgKind.hintProcessing, False)
    assert TMsgKind.hintProcessing not in conf.notes and TMsgKind.hintProcessing not in conf.foreignPackageNotes
    setNoteDefaults(conf, TMsgKind.hintProcessing, True)
    setNote(conf, TMsgKind.warnUser, True)
    assert hasWarn(conf, TMsgKind.warnUser)
    setNote(conf, TMsgKind.warnUser, False)
    assert not hasWarn(conf, TMsgKind.warnUser)

    # 4. ErrorMax
    conf.errorMax = 0
    setErrorMaxHighMaybe(conf)
    assert conf.errorMax == high(nint)
    conf.errorMax = 3
    setErrorMaxHighMaybe(conf)  # honors --errorMax
    assert conf.errorMax == 3

    # 5. IDE commands parsing & formatting
    for name, expected in [
        (string("sug"), IdeCmd.ideSug),
        (string("con"), IdeCmd.ideCon),
        (string("def"), IdeCmd.ideDef),
        (string("use"), IdeCmd.ideUse),
        (string("dus"), IdeCmd.ideDus),
        (string("chk"), IdeCmd.ideChk),
        (string("mod"), IdeCmd.ideMod),
        (string("none"), IdeCmd.ideNone),
    ]:
        with var:
            cmd = parseIdeCmd(name)
        assert cmd == expected
        assert str(cmd) == name

    # 6. Alignments
    assert floatInt64Align(conf) == 8
    conf.target.targetCPU = TSystemCPU.cpuI386
    conf.target.targetOS = TSystemOS.osLinux
    assert floatInt64Align(conf) == 4
    conf.target.targetOS = TSystemOS.osWindows
    assert floatInt64Align(conf) == 8

    # 7. isDefined
    conf.target.targetCPU = TSystemCPU.cpuAmd64
    conf.target.targetOS = TSystemOS.osLinux
    assert isDefined(conf, string("amd64"))
    assert isDefined(conf, string("linux"))
    assert isDefined(conf, string("posix"))

    # 8. Dynlib overrides
    assert _canonDynlibName(string("libssl.so.1.1")) == string("ssl")
    assert _canonDynlibName(string("libcrypto(3)")) == string("crypto")
    assert _canonDynlibName(string("zlib.dll")) == string("zlib")

    # 9. Path operations
    conf.projectFull = AbsoluteFile(string("/path/to/project.nim"))
    conf.projectPath = AbsoluteDir(string("/path/to"))
    conf.projectName = string("project")
    conf.searchPaths.add(AbsoluteDir(string("/path/to")))

    rel = getRelativePathFromConfigPath(conf, AbsoluteFile(string("/path/to/foo.nim")))
    assert string(rel) == string("foo.nim")
    conf.lazyPaths.add(AbsoluteDir(string("/lazy")))
    assert string(getRelativePathFromConfigPath(conf, AbsoluteFile(string("/lazy/a/b.nim")))) == string("a/b.nim")
    assert string(getRelativePathFromConfigPath(conf, AbsoluteFile(string("/other/c.nim")))) == string("")

    # 10. Global options flags
    assert not hcrOn(conf)
    conf.globalOptions.incl(TGlobalOption.optHotCodeReloading)
    assert hcrOn(conf)

    showNonExportedFields(conf)
    assert TGlobalOption.optShowNonExportedFields in conf.globalOptions

    docRawOutput(conf)
    assert TGlobalOption.optDocRaw in conf.globalOptions

    # 11. Timestamps
    assert len(getDateStr()) == 10
    assert len(getClockStr()) == 8

    echo("options.py extensive tests passed!")

    # packagehandling (included): nimble file / package lookup, cached per directory
    with var:
        _pconf = newConfigRef()
    with let:
        _pkgName = getPackageName(_pconf, string(getCurrentDir()) / string("ncompiler") / string("options.py"))
    doAssert(len(_pkgName) > 0, string("getPackageName"))
    doAssert(getPackageName(_pconf, string(getCurrentDir()) / string("ncompiler") / string("options.py")) == _pkgName,
             string("getPackageName cached"))
    echo(string("packagehandling tests passed"))
