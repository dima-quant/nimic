from __future__ import annotations
from nimic.ntypes import *
from lineinfos import *
from platform import *
from prefixmatches import *
from pathutils import *
from nimpaths import *

hasTinyCBackend = False # defined(tinyc)
useEffectSystem = True
useWriteTracking = False
hasFFI = False # defined(nimHasLibFFI)
copyrightYear = string("2026")
nimEnableCovariance = False

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

cmdBackends = Tset[Command]({Command.cmdCompileToC, Command.cmdCompileToCpp, Command.cmdCompileToOC, Command.cmdCompileToJS, Command.cmdCrun, Command.cmdCompileToNif})
cmdDocLike = Tset[Command]({Command.cmdDoc0, Command.cmdDoc, Command.cmdDoc2tex, Command.cmdJsondoc0, Command.cmdJsondoc, Command.cmdCtags, Command.cmdBuildindex})

TStringSeq = seq[string]

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

if comptime(__name__ == '__main__'):
    pass

from ncompiler.lineinfos import *

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

CfileList = seq[Cfile]

class SuggestInlayHintKind(NStrEnum):
    sihkType = "Type"
    sihkParameter = "Parameter"
    sihkException = "Exception"

class SuggestInlayHint(Object):
    kind: SuggestInlayHintKind
    line: int
    column: int
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
    line: int
    column: int
    doc: string
    forth: string
    quality: int
    isGlobal: bool
    contextFits: bool
    prefix: PrefixMatch
    symkind: int # byte
    scope: int
    localUsages: int
    globalUsages: int
    tokenLen: int
    version: int
    endLine: int # uint16
    endCol: int
    inlayHintInfo: SuggestInlayHint

Suggestions = seq[Suggest]

class ProfileInfo(Object):
    time: float
    count: int

ProfileData = Object # TableRef[TLineInfo, ProfileInfo]

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

@ref
class ConfigRef(Object):
    backend: TBackend
    target: Target
    linesCompiled: int
    options: TOptions
    globalOptions: TGlobalOptions
    macrosToExpand: Object # StringTableRef
    arcToExpand: Object # StringTableRef
    m: MsgConfig
    filenameOption: FilenameOption
    unitSep: string
    evalTemplateCounter: int
    evalMacroCounter: int
    exitcode: int # int8
    cmd: Command
    cmdInput: string
    projectIsCmd: bool
    implicitCmd: bool
    selectedGC: TGCMode
    exc: ExceptionSystem
    selectedStrings: StringsMode
    hintProcessingDots: bool
    verbosity: int
    numberOfProcessors: int
    lastCmdTime: float
    symbolFiles: SymbolFilesOption
    ic: bool
    spellSuggestMax: int

    cppDefines: Object # HashSet[string]
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
    mainPackageId: int
    errorCounter: int
    hintCounter: int
    warnCounter: int
    errorMax: int
    maxLoopIterationsVM: int
    maxCallDepthVM: int
    isVmTrace: bool
    configVars: Object # StringTableRef
    symbols: Object # StringTableRef
    packageCache: Object # StringTableRef
    nimblePaths: seq[AbsoluteDir]
    searchPaths: seq[AbsoluteDir]
    lazyPaths: seq[AbsoluteDir]
    outFile: RelativeFile
    outDir: AbsoluteDir
    jsonBuildFile: AbsoluteFile
    prefixDir: AbsoluteDir
    libpath: AbsoluteDir
    nimcacheDir: AbsoluteDir
    dllOverrides: Object
    moduleOverrides: Object
    cfileSpecificOptions: Object
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
    suggestionResultHook: Object
    suggestVersion: int
    suggestMaxResults: int
    lastLineInfo: TLineInfo
    writelnHook: Object
    structuredErrorHook: Object
    cppCustomNamespace: string
    nimMainPrefix: string
    vmProfileData: ProfileData

    expandProgress: bool
    expandLevels: int
    expandNodeResult: string
    expandPosition: TLineInfo

    currentConfigDir: string
    clientProcessId: int

def assignIfDefault(result: Object, val: Object, def_: Object = None) -> None:
    pass # needs to handle generic types, but Python has dynamic typing

def setErrorMaxHighMaybe(conf: ConfigRef) -> None:
    if conf.errorMax == 0: # default
        import sys
        conf.errorMax = sys.maxsize

def setNoteDefaults(conf: ConfigRef, note: TNoteKind, enabled: bool = True) -> None:
    if enabled:
        conf.notes.add(note)
        conf.mainPackageNotes.add(note)
        conf.foreignPackageNotes.add(note)
    else:
        conf.notes.discard(note)
        conf.mainPackageNotes.discard(note)
        conf.foreignPackageNotes.discard(note)

def setNote(conf: ConfigRef, note: TNoteKind, enabled: bool = True) -> None:
    if note not in conf.cmdlineNotes:
        if enabled:
            conf.notes.add(note)
        else:
            conf.notes.discard(note)

def hasHint(conf: ConfigRef, note: TNoteKind) -> bool:
    if TOption.optHints not in conf.options:
        return False
    elif note in {TMsgKind.hintConf, TMsgKind.hintProcessing}:
        return note in conf.mainPackageNotes
    else:
        return note in conf.notes

import os
from datetime import datetime
import sys
# StringTableRef mocked
# Wait, std.strtabs is Nim's string table, I should use python's dict for now or mock it if not translated.
# I will use Object as a placeholder for StringTableRef.

def hasWarn(conf: ConfigRef, note: TNoteKind) -> bool:
    return TOption.optWarns in conf.options and note in conf.notes

def hcrOn(conf: ConfigRef) -> bool:
    return TGlobalOption.optHotCodeReloading in conf.globalOptions

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

def getSrcTimestamp() -> datetime:
    try:
        ts = int(os.environ.get("SOURCE_DATE_EPOCH", "not a number"))
        return datetime.utcfromtimestamp(ts)
    except ValueError:
        return datetime.utcnow()

def getDateStr() -> string:
    return string(getSrcTimestamp().strftime("%Y-%m-%d"))

def getClockStr() -> string:
    return string(getSrcTimestamp().strftime("%H:%M:%S"))

def newPackageCache() -> Object: # mock StringTableRef
    return Object()

def newProfileData() -> ProfileData:
    return ProfileData() # mock

foreignPackageNotesDefault = Tset[TNoteKind]({
  TMsgKind.hintProcessing, TMsgKind.warnUnknownMagic, TMsgKind.hintQuitCalled, TMsgKind.hintExecuting, TMsgKind.hintUser, TMsgKind.warnUser})

def initConfigRefCommon(conf: ConfigRef) -> None:
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
    result = ConfigRef()
    result.cCompiler = TSystemCC.ccGcc
    result.macrosToExpand = Object() # newStringTable
    result.arcToExpand = Object() # newStringTable
    # m: initMsgConfig() omitted because of cycle, will be done later
    result.cppDefines = Object() # initHashSet
    result.headerFile = string("")
    result.features = Tset[Feature]({})
    result.legacyFeatures = Tset[LegacyFeature]({})
    result.configVars = Object()
    result.symbols = Object()
    result.packageCache = newPackageCache()
    result.searchPaths = seq[AbsoluteDir]()
    result.lazyPaths = seq[AbsoluteDir]()
    result.outFile = RelativeFile(string(""))
    result.outDir = AbsoluteDir(string(""))
    result.prefixDir = AbsoluteDir(string(""))
    result.libpath = AbsoluteDir(string(""))
    result.nimcacheDir = AbsoluteDir(string(""))
    result.dllOverrides = Object()
    result.moduleOverrides = Object()
    result.cfileSpecificOptions = Object()
    result.projectName = string("")
    result.projectPath = AbsoluteDir(string(""))
    result.projectFull = AbsoluteFile(string(""))
    result.projectIsStdin = False
    result.stdinFile = AbsoluteFile(string("stdinfile"))
    result.projectMainIdx = FileIndex(0)
    result.command = string("")
    result.commandArgs = seq[string]()
    result.commandLine = string("")
    result.implicitImports = seq[string]()
    result.implicitIncludes = seq[string]()
    result.docSeeSrcUrl = string("")
    result.cIncludes = seq[AbsoluteDir]()
    result.cLibs = seq[AbsoluteDir]()
    result.cLinkedLibs = seq[string]()
    result.backend = TBackend.backendInvalid
    result.externalToLink = seq[string]()
    result.linkOptionsCmd = string("")
    result.compileOptionsCmd = seq[string]()
    result.linkOptions = string("")
    result.compileOptions = string("")
    result.cCompilerPath = string("")
    result.toCompile = CfileList()
    result.arguments = string("")
    result.suggestMaxResults = 10_000
    result.maxLoopIterationsVM = 10_000_000
    result.maxCallDepthVM = 2_000
    result.vmProfileData = newProfileData()
    result.spellSuggestMax = spellSuggestSecretSauce
    result.currentConfigDir = string("")
    
    initConfigRefCommon(result)
    setTargetFromSystem(result.target)
    # enable colors by default on terminals
    if sys.stderr.isatty():
        result.globalOptions.add(TGlobalOption.optUseColors)
    return result

def newPartialConfigRef() -> ConfigRef:
    result = ConfigRef()
    initConfigRefCommon(result)
    return result

def cppDefine(c: ConfigRef, define: string) -> None:
    pass # c.cppDefines.add(define) - mock

from nimic.std.strutils import cmpIgnoreStyle

def isDefined(conf: ConfigRef, symbol: string) -> bool:
    # We mock conf.symbols.hasKey
    if hasattr(conf.symbols, "hasKey") and conf.symbols.hasKey(symbol):
        return True
    elif cmpIgnoreStyle(symbol, CPU[conf.target.targetCPU].name) == 0:
        return True
    elif cmpIgnoreStyle(symbol, OS[conf.target.targetOS].name) == 0:
        return True
    else:
        norm = str(symbol).lower() # simulate normalize
        if norm == "x86": return conf.target.targetCPU == TSystemCPU.cpuI386
        elif norm == "itanium": return conf.target.targetCPU == TSystemCPU.cpuIa64
        elif norm == "x8664": return conf.target.targetCPU == TSystemCPU.cpuAmd64
        elif norm in ("posix", "unix"):
            return conf.target.targetOS in {TSystemOS.osLinux, TSystemOS.osMorphos, TSystemOS.osSkyos, TSystemOS.osIrix, TSystemOS.osPalmos,
                                TSystemOS.osQnx, TSystemOS.osAtari, TSystemOS.osAix,
                                TSystemOS.osHaiku, TSystemOS.osVxWorks, TSystemOS.osSolaris, TSystemOS.osNetbsd,
                                TSystemOS.osFreebsd, TSystemOS.osOpenbsd, TSystemOS.osDragonfly, TSystemOS.osMacosx, TSystemOS.osIos,
                                TSystemOS.osAndroid, TSystemOS.osNintendoSwitch, TSystemOS.osFreeRTOS, TSystemOS.osCrossos, TSystemOS.osZephyr, TSystemOS.osNuttX}
        elif norm == "linux":
            return conf.target.targetOS in {TSystemOS.osLinux, TSystemOS.osAndroid}
        elif norm == "bsd":
            return conf.target.targetOS in {TSystemOS.osNetbsd, TSystemOS.osFreebsd, TSystemOS.osOpenbsd, TSystemOS.osDragonfly, TSystemOS.osCrossos}
        elif norm == "freebsd":
            return conf.target.targetOS in {TSystemOS.osFreebsd, TSystemOS.osCrossos}
        elif norm == "emulatedthreadvars":
            return TInfoOSProp.ospLacksThreadVars in OS[conf.target.targetOS].props
        elif norm == "msdos": return conf.target.targetOS == TSystemOS.osDos
        elif norm in ("mswindows", "win32"): return conf.target.targetOS == TSystemOS.osWindows
        elif norm == "macintosh":
            return conf.target.targetOS in {TSystemOS.osMacos, TSystemOS.osMacosx, TSystemOS.osIos}
        elif norm in ("osx", "macosx"):
            return conf.target.targetOS in {TSystemOS.osMacosx, TSystemOS.osIos}
        elif norm == "sunos": return conf.target.targetOS == TSystemOS.osSolaris
        elif norm == "nintendoswitch":
            return conf.target.targetOS == TSystemOS.osNintendoSwitch
        elif norm in ("freertos", "lwip"):
            return conf.target.targetOS == TSystemOS.osFreeRTOS
        elif norm == "zephyr":
            return conf.target.targetOS == TSystemOS.osZephyr
        elif norm == "nuttx":
            return conf.target.targetOS == TSystemOS.osNuttX
        elif norm == "littleendian": return CPU[conf.target.targetCPU].endian == TEndian.littleEndian
        elif norm == "bigendian": return CPU[conf.target.targetCPU].endian == TEndian.bigEndian
        elif norm == "cpu8": return CPU[conf.target.targetCPU].bit == 8
        elif norm == "cpu16": return CPU[conf.target.targetCPU].bit == 16
        elif norm == "cpu32": return CPU[conf.target.targetCPU].bit == 32
        elif norm == "cpu64": return CPU[conf.target.targetCPU].bit == 64
        elif norm == "nimrawsetjmp":
            return conf.target.targetOS in {TSystemOS.osSolaris, TSystemOS.osNetbsd, TSystemOS.osFreebsd, TSystemOS.osOpenbsd,
                                TSystemOS.osDragonfly, TSystemOS.osMacosx}
        else: return False

def quitOrRaise(conf: ConfigRef, msg: string = string("")) -> None:
    if isDefined(conf, string("nimDebug")):
        assert False, str(msg)
    else:
        sys.exit(str(msg))

def importantComments(conf: ConfigRef) -> bool:
    return conf.cmd in (cmdDocLike | Tset[Command]({Command.cmdIdeTools}))

def usesWriteBarrier(conf: ConfigRef) -> bool:
    return conf.selectedGC >= TGCMode.gcRefc

def usesSso(conf: ConfigRef) -> bool:
    return conf.selectedStrings == StringsMode.stringSso

def optPreserveOrigSource(conf: ConfigRef) -> bool:
    return TGlobalOption.optEmbedOrigSrc in conf.globalOptions

def mainCommandArg(conf: ConfigRef) -> string:
    if len(conf.commandArgs) > 0:
        return conf.commandArgs[0]
    else:
        return conf.projectName

def existsConfigVar(conf: ConfigRef, key: string) -> bool:
    pass # mock
    return False

def getConfigVar(conf: ConfigRef, key: string, default: string = string("")) -> string:
    pass # mock
    return default

def setConfigVar(conf: ConfigRef, key: string, val: string) -> None:
    pass # mock

def getOutFile(conf: ConfigRef, filename: RelativeFile, ext: string) -> AbsoluteFile:
    assert len(str(conf.outDir)) > 0
    return conf.outDir / filename.changeFileExt(ext)

def absOutFile(conf: ConfigRef) -> AbsoluteFile:
    assert not isEmpty(conf.outDir)
    assert not isEmpty(conf.outFile)
    result = conf.outDir / conf.outFile
    # mock posix directory check omitted
    return result


# packagehandling.nim inclusion
def myParentDirs(p: string) -> string: # iterator
    current = p
    while True:
        current = parentDir(current)
        if len(current) == 0:
            break
        yield current

def getNimbleFile(conf: ConfigRef, path: string) -> string:
    result = string("")
    parents = 0
    # packageSearch block
    found = False
    for d in myParentDirs(path):
        if hasattr(conf.packageCache, "hasKey") and conf.packageCache.hasKey(d):
            return conf.packageCache[d]
        parents += 1
        for file in walkFiles(d / string("*.nimble")):
            result = file
            found = True
            break
        if found:
            break
    
    for d in myParentDirs(path):
        conf.packageCache[d] = result
        parents -= 1
        if parents <= 0:
            break
    return result

def getPackageName(conf: ConfigRef, path: string) -> string:
    nimble_path = getNimbleFile(conf, path)
    if len(nimble_path) > 0:
        return splitFile(nimble_path)[1] # name is the 2nd element
    else:
        return string("unknown")

def prepareToWriteOutput(conf: ConfigRef) -> AbsoluteFile:
    result = absOutFile(conf)
    createDir(string(result).parentDir()) # wait, parentDir is a function in os, not a method
    return result

def getPrefixDir(conf: ConfigRef) -> AbsoluteDir:
    if not isEmpty(conf.prefixDir):
        return conf.prefixDir
    else:
        binParent = AbsoluteDir(splitPath(getAppDir())[0]) # head
        if comptime(defined("posix")):
            if binParent == AbsoluteDir(string("/usr")):
                return AbsoluteDir(string("/usr/lib/nim"))
            elif binParent == AbsoluteDir(string("/usr/local")):
                return AbsoluteDir(string("/usr/local/lib/nim"))
            else:
                return binParent
        else:
            return binParent

def setDefaultLibpath(conf: ConfigRef) -> None:
    if isEmpty(conf.libpath):
        prefix = getPrefixDir(conf)
        conf.libpath = prefix / RelativeDir(string("lib"))
        
        realNimPath = findExe(string("nim"))
        parentNimLibPath = parentDir(parentDir(realNimPath)) / string("lib")
        if not fileExists(string(conf.libpath) / string("system.nim")) and fileExists(parentNimLibPath / string("system.nim")):
            conf.libpath = AbsoluteDir(parentNimLibPath)

def canonicalizePath(conf: ConfigRef, path: AbsoluteFile) -> AbsoluteFile:
    return AbsoluteFile(expandFilename(string(path)))

def setFromProjectName(conf: ConfigRef, projectName: string) -> None:
    try:
        conf.projectFull = canonicalizePath(conf, AbsoluteFile(projectName))
    except OSError:
        conf.projectFull = AbsoluteFile(projectName)
    
    p = splitFile(conf.projectFull)
    dir_val = AbsoluteDir(getCurrentDir()) if isEmpty(p[0]) else p[0]
    try:
        conf.projectPath = AbsoluteDir(canonicalizePath(conf, AbsoluteFile(string(dir_val))))
    except OSError:
        conf.projectPath = dir_val
    conf.projectName = p[1]

def removeTrailingDirSep(path: string) -> string:
    if len(path) > 0 and path[-1] == DirSep:
        return substr(path, 0, len(path) - 2)
    else:
        return path

def disableNimblePath(conf: ConfigRef) -> None:
    conf.globalOptions.add(TGlobalOption.optNoNimblePath)
    conf.lazyPaths.setLen(0)
    conf.nimblePaths.setLen(0)

def clearNimblePath(conf: ConfigRef) -> None:
    conf.lazyPaths.setLen(0)
    conf.nimblePaths.setLen(0)

def getOsCacheDir() -> string:
    if comptime(defined("posix")):
        return getEnv(string("XDG_CACHE_HOME"), getHomeDir() / string(".cache")) / string("nim")
    else:
        return getHomeDir() / string(genSubDir) # genSubDir is from nimpaths

def getNimcacheDir(conf: ConfigRef) -> AbsoluteDir:
    def nimcacheSuffix(conf: ConfigRef) -> string:
        if conf.cmd == Command.cmdCheck:
            return string("_check")
        elif isDefined(conf, string("release")) or isDefined(conf, string("danger")):
            return string("_r")
        else:
            return string("_d")
            
    if not isEmpty(conf.nimcacheDir):
        return conf.nimcacheDir
    elif conf.backend == TBackend.backendJs:
        if isEmpty(conf.outDir):
            return conf.projectPath / RelativeDir(string(genSubDir))
        else:
            return conf.outDir / RelativeDir(string(genSubDir))
    else:
        return AbsoluteDir(getOsCacheDir() / splitFile(AbsoluteFile(conf.projectName))[1] + nimcacheSuffix(conf))

def pathSubs(conf: ConfigRef, p: string, config: string) -> string:
    home = removeTrailingDirSep(getHomeDir())
    # python string formatting for %
    # wait, nim % operator is different. We should use python replace for now, or mock.
    res = p.replace("$nim", string(getPrefixDir(conf)))
    res = res.replace("$lib", string(conf.libpath))
    res = res.replace("$home", home)
    res = res.replace("$config", config)
    res = res.replace("$projectname", conf.projectName)
    res = res.replace("$projectpath", string(conf.projectPath))
    res = res.replace("$projectdir", string(conf.projectPath))
    res = res.replace("$nimcache", string(getNimcacheDir(conf)))
    return expandTilde(unixToNativePath(res))

def nimbleSubs(conf: ConfigRef, p: string) -> string: # iterator
    pl = toLowerAscii(p)
    if string("$nimblepath") in pl or string("$nimbledir") in pl:
        for i in range(len(conf.nimblePaths) - 1, -1, -1):
            nimblePath = removeTrailingDirSep(string(conf.nimblePaths[i]))
            res = p.replace("$nimblepath", nimblePath)
            res = res.replace("$nimbledir", nimblePath)
            yield res
    else:
        yield p

def toGeneratedFile(conf: ConfigRef, path: AbsoluteFile, ext: string) -> AbsoluteFile:
    return getNimcacheDir(conf) / changeFileExt(RelativeFile(splitPath(string(path))[1]), ext)

def completeGeneratedFilePath(conf: ConfigRef, f: AbsoluteFile, createSubDir: bool = True) -> AbsoluteFile:
    subdir = getNimcacheDir(conf)
    if createSubDir:
        try:
            createDir(string(subdir))
        except OSError:
            quitOrRaise(conf, string("cannot create directory: ") + string(subdir))
    return subdir / RelativeFile(splitPath(string(f))[1])

def patchModule(conf: ConfigRef, result: AbsoluteFile) -> AbsoluteFile:
    if not isEmpty(result) and len(conf.moduleOverrides) > 0:
        key = getPackageName(conf, string(result)) + string("_") + splitFile(result)[1]
        if hasattr(conf.moduleOverrides, "hasKey") and conf.moduleOverrides.hasKey(key):
            ov = conf.moduleOverrides[key]
            if len(ov) > 0:
                result = AbsoluteFile(ov)
    return result

def rawFindFile(conf: ConfigRef, f: RelativeFile, suppressStdlib: bool) -> AbsoluteFile:
    for it in conf.searchPaths:
        if suppressStdlib and string(it).startswith(string(conf.libpath)):
            continue
        result = it / f
        if fileExists(string(result)):
            return canonicalizePath(conf, result)
    return AbsoluteFile(string(""))

def rawFindFile2(conf: ConfigRef, f: RelativeFile) -> AbsoluteFile:
    for i in range(len(conf.lazyPaths)):
        it = conf.lazyPaths[i]
        result = it / f
        if fileExists(string(result)):
            for j in range(i, 0, -1):
                conf.lazyPaths[j], conf.lazyPaths[j-1] = conf.lazyPaths[j-1], conf.lazyPaths[j]
            return canonicalizePath(conf, result)
    return AbsoluteFile(string(""))

stdlibDirs = [
    string("pure"), string("core"), string("arch"),
    string("pure/collections"),
    string("pure/concurrency"),
    string("pure/unidecode"), string("impure"),
    string("wrappers"), string("wrappers/linenoise"),
    string("windows"), string("posix"), string("js"),
    string("deprecated/pure")
]

pkgPrefix = string("pkg/")
stdPrefix = string("std/")

def getRelativePathFromConfigPath(conf: ConfigRef, f: AbsoluteFile, isTitle: bool = False) -> RelativeFile:
    result = RelativeFile(string(""))
    f_str = string(f)
    if isTitle:
        for dir in stdlibDirs:
            path = string(conf.libpath) / dir / extractFilename(f_str)
            if cmpPaths(path, f_str) == 0:
                return RelativeFile(stdPrefix + splitFile(f)[1])
    
    for _, it in conf.searchPaths:
        it_str = string(it)
        if f_str.startswith(it_str): # mock isRelativeTo
            return RelativeFile(relativePath(f_str, it_str))
    for _, it in conf.lazyPaths:
        it_str = string(it)
        if f_str.startswith(it_str):
            return RelativeFile(relativePath(f_str, it_str))
    return result

def findFile(conf: ConfigRef, f: string, suppressStdlib: bool = False) -> AbsoluteFile:
    if isAbsolute(f):
        result = AbsoluteFile(f) if fileExists(f) else AbsoluteFile(string(""))
    else:
        result = rawFindFile(conf, RelativeFile(f), suppressStdlib)
        if isEmpty(result):
            result = rawFindFile(conf, RelativeFile(toLowerAscii(f)), suppressStdlib)
            if isEmpty(result):
                result = rawFindFile2(conf, RelativeFile(f))
                if isEmpty(result):
                    result = rawFindFile2(conf, RelativeFile(toLowerAscii(f)))
    return patchModule(conf, result)

def findModule(conf: ConfigRef, modulename: string, currentModule: string) -> AbsoluteFile:
    m = addFileExt(modulename, string(NimExt))
    hasRelativeDot = False
    if m.startswith(pkgPrefix):
        result = findFile(conf, substr(m, len(pkgPrefix)), suppressStdlib=True)
    else:
        if m.startswith(stdPrefix):
            result = AbsoluteFile(string(""))
            stripped = substr(m, len(stdPrefix))
            for candidate in stdlibDirs:
                path = string(conf.libpath) / candidate / stripped
                if fileExists(path):
                    result = AbsoluteFile(path)
                    break
        else:
            currentPath = splitFile(AbsoluteFile(currentModule))[0]
            result = currentPath / RelativeFile(m)
            if m.startswith(string(".")) and not fileExists(string(result)):
                result = AbsoluteFile(string(""))
                hasRelativeDot = True
        
        if not fileExists(string(result)) and not hasRelativeDot:
            result = findFile(conf, m)
    return patchModule(conf, result)

def findProjectNimFile(conf: ConfigRef, pkg: string) -> string:
    extensions = [string(".nims"), string(".cfg"), string(".nimcfg"), string(".nimble")]
    candidates = seq[string]()
    dir = pkg
    prev = dir
    nimblepkg = string("")
    pkgname = extractFilename(pkg)
    while True:
        # mock walkDir
        for k, f in walkDir(dir, relative=True):
            if k == pcFile and f != string("config.nims"):
                p = splitFile(AbsoluteFile(f))
                if p[2] in extensions:
                    x = changeFileExt(dir / p[1], string(".nim"))
                    if fileExists(x):
                        candidates.add(x)
                    if p[2] == string(".nimble"):
                        if len(nimblepkg) == 0:
                            nimblepkg = changeFileExt(dir / p[1], string(".nim"))
        if len(candidates) > 0:
            return candidates[0]
        if len(nimblepkg) > 0:
            return nimblepkg
        prev = dir
        dir = parentDir(dir)
        if prev == dir:
            break
    return string("")


def canonicalImportAux(conf: ConfigRef, file: AbsoluteFile) -> string:
    ret = getRelativePathFromConfigPath(conf, file, isTitle=True)
    dir_val = AbsoluteDir(parentDir(getNimbleFile(conf, string(file))))
    if not isEmpty(dir_val):
        relPath = relativeTo(file, dir_val)
        if not isEmpty(relPath) and (isEmpty(ret) or len(string(relPath)) < len(string(ret))):
            ret = relPath
    if isEmpty(ret):
        ret = relativeTo(file, conf.projectPath)
    return string(ret)

def canonicalImport(conf: ConfigRef, file: AbsoluteFile) -> string:
    ret = canonicalImportAux(conf, file)
    return changeFileExt(nativeToUnixPath(ret), string(""))

def canonDynlibName(s: string) -> string:
    start = 3 if s.startswith(string("lib")) else 0
    ende = find(s, {ch('('), ch(')'), ch('.')})
    if ende >= 0:
        return substr(s, start, ende - 1)
    else:
        return substr(s, start)

def inclDynlibOverride(conf: ConfigRef, lib: string) -> None:
    # mock dllOverrides map access
    conf.dllOverrides[canonDynlibName(lib)] = string("true")

def isDynlibOverride(conf: ConfigRef, lib: string) -> bool:
    if TGlobalOption.optDynlibOverrideAll in conf.globalOptions:
        return True
    return hasattr(conf.dllOverrides, "hasKey") and conf.dllOverrides.hasKey(canonDynlibName(lib))

def showNonExportedFields(conf: ConfigRef) -> None:
    conf.globalOptions.add(TGlobalOption.optShowNonExportedFields)

def docRawOutput(conf: ConfigRef) -> None:
    conf.globalOptions.add(TGlobalOption.optDocRaw)

def expandDone(conf: ConfigRef) -> bool:
    return conf.ideCmd == IdeCmd.ideExpand and conf.expandLevels == 0 and conf.expandProgress

def parseIdeCmd(s: string) -> IdeCmd:
    if s == string("sug"): return IdeCmd.ideSug
    elif s == string("con"): return IdeCmd.ideCon
    elif s == string("def"): return IdeCmd.ideDef
    elif s == string("use"): return IdeCmd.ideUse
    elif s == string("dus"): return IdeCmd.ideDus
    elif s == string("chk"): return IdeCmd.ideChk
    elif s == string("chkFile"): return IdeCmd.ideChkFile
    elif s == string("mod"): return IdeCmd.ideMod
    elif s == string("highlight"): return IdeCmd.ideHighlight
    elif s == string("outline"): return IdeCmd.ideOutline
    elif s == string("known"): return IdeCmd.ideKnown
    elif s == string("msg"): return IdeCmd.ideMsg
    elif s == string("project"): return IdeCmd.ideProject
    elif s == string("globalSymbols"): return IdeCmd.ideGlobalSymbols
    elif s == string("recompile"): return IdeCmd.ideRecompile
    elif s == string("changed"): return IdeCmd.ideChanged
    elif s == string("type"): return IdeCmd.ideType
    else: return IdeCmd.ideNone

# since `__str__` inside IdeCmd class is already defined or handled by default python enum if we don't override, we'll just implement ideCmdToStr to act as `$c`
def ideCmdToStr(c: IdeCmd) -> string:
    if c == IdeCmd.ideSug: return string("sug")
    elif c == IdeCmd.ideCon: return string("con")
    elif c == IdeCmd.ideDef: return string("def")
    elif c == IdeCmd.ideUse: return string("use")
    elif c == IdeCmd.ideDus: return string("dus")
    elif c == IdeCmd.ideChk: return string("chk")
    elif c == IdeCmd.ideChkFile: return string("chkFile")
    elif c == IdeCmd.ideMod: return string("mod")
    elif c == IdeCmd.ideNone: return string("none")
    elif c == IdeCmd.ideHighlight: return string("highlight")
    elif c == IdeCmd.ideOutline: return string("outline")
    elif c == IdeCmd.ideKnown: return string("known")
    elif c == IdeCmd.ideMsg: return string("msg")
    elif c == IdeCmd.ideProject: return string("project")
    elif c == IdeCmd.ideGlobalSymbols: return string("globalSymbols")
    elif c == IdeCmd.ideDeclaration: return string("declaration")
    elif c == IdeCmd.ideExpand: return string("expand")
    elif c == IdeCmd.ideRecompile: return string("recompile")
    elif c == IdeCmd.ideChanged: return string("changed")
    elif c == IdeCmd.ideType: return string("type")
    elif c == IdeCmd.ideInlayHints: return string("inlayHints")
    return string("")

def floatInt64Align(conf: ConfigRef) -> int:
    if conf is not None and conf.target.targetCPU == TSystemCPU.cpuI386:
        if conf.target.targetOS != TSystemOS.osWindows:
            return 4
    return 8

if comptime(__name__ == "__main__"):
    print("Running options.py tests...")
    conf = ConfigRef()
    conf.globalOptions = Tset[TGlobalOption]()
    conf.ideCmd = IdeCmd.ideNone
    # Test Enums and Options
    assert conf.ideCmd == IdeCmd.ideNone
    conf.globalOptions.add(TGlobalOption.optShowAllMismatches)
    assert TGlobalOption.optShowAllMismatches in conf.globalOptions
    
    # Test IDE commands parsing
    cmd = parseIdeCmd(string("sug"))
    assert cmd == IdeCmd.ideSug
    assert ideCmdToStr(cmd) == string("sug")
    
    # Test alignments
    assert floatInt64Align(conf) == 8
    
    # Test Path Operations
    conf.projectFull = AbsoluteFile(string("/path/to/project.nim"))
    conf.projectPath = AbsoluteDir(string("/path/to"))
    
    # mock getNimbleFile just to pass
    conf.projectName = string("project")
    conf.searchPaths.add(AbsoluteDir(string("/path/to")))
    
    rel = getRelativePathFromConfigPath(conf, AbsoluteFile(string("/path/to/foo.nim")))
    assert string(rel) == string("foo.nim")
    
    print("options.py extensive tests passed!")
