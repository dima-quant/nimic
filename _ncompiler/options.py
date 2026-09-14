"""
ncompiler/options.py — Compiler options and ConfigRef
Converted from compiler/options.nim (extensible stub)

Only the types/fields actually referenced by the lexer and parser are
populated. The structure is extensible — add fields as needed.
"""
from __future__ import annotations
from nimic.ntypes import *
from ncompiler.lineinfos import (
    MsgConfig, initMsgConfig, TNoteKinds, TMsgKind,
    NotesVerbosity, TLineInfo, unknownLineInfo, ErrorOutput,
    hintMin, hintMax, warnMin, warnMax
)
from ncompiler.platform import Target, setTargetFromSystem
from ncompiler.pathutils import AbsoluteFile, AbsoluteDir, RelativeFile, RelativeDir


# --- TOption ---
class TOption(NIntEnum):
    optNone = auto(); optObjCheck = auto(); optFieldCheck = auto()
    optRangeCheck = auto(); optBoundsCheck = auto(); optOverflowCheck = auto()
    optRefCheck = auto(); optNaNCheck = auto(); optInfCheck = auto()
    optStaticBoundsCheck = auto(); optStyleCheck = auto(); optAssert = auto()
    optLineDir = auto(); optWarns = auto(); optHints = auto()
    optOptimizeSpeed = auto(); optOptimizeSize = auto()
    optStackTrace = auto(); optStackTraceMsgs = auto(); optLineTrace = auto()
    optByRef = auto(); optProfiler = auto(); optImplicitStatic = auto()
    optTrMacros = auto(); optMemTracker = auto(); optSinkInference = auto()
    optCursorInference = auto(); optImportHidden = auto(); optQuirky = auto()

TOptions = set  # set[TOption]


# --- TGlobalOption ---
class TGlobalOption(NIntEnum):
    gloptNone = auto(); optForceFullMake = auto()
    optWasNimscript = auto(); optListCmd = auto(); optCompileOnly = auto()
    optNoLinking = auto(); optCDebug = auto(); optGenDynLib = auto()
    optGenStaticLib = auto(); optGenGuiApp = auto(); optGenScript = auto()
    optGenCDeps = auto(); optGenMapping = auto(); optRun = auto()
    optUseNimcache = auto(); optStyleHint = auto(); optStyleError = auto()
    optStyleWarning = auto(); optStyleUsages = auto()
    optSkipSystemConfigFile = auto(); optSkipProjConfigFile = auto()
    optSkipUserConfigFile = auto(); optSkipParentConfigFiles = auto()
    optNoMain = auto(); optUseColors = auto(); optThreads = auto()
    optStdout = auto(); optThreadAnalysis = auto(); optTlsEmulation = auto()
    optGenIndex = auto(); optGenIndexOnly = auto(); optNoImportdoc = auto()
    optEmbedOrigSrc = auto(); optIdeDebug = auto(); optIdeTerse = auto()
    optIdeExceptionInlayHints = auto(); optExcessiveStackTrace = auto()
    optShowAllMismatches = auto(); optWholeProject = auto()
    optDocInternal = auto(); optMixedMode = auto(); optDeclaredLocs = auto()
    optNoNimblePath = auto(); optHotCodeReloading = auto()
    optDynlibOverrideAll = auto(); optSeqDestructors = auto()
    optTinyRtti = auto(); optOwnedRefs = auto(); optMultiMethods = auto()
    optBenchmarkVM = auto(); optProduceAsm = auto(); optPanics = auto()
    optSourcemap = auto(); optProfileVM = auto(); optEnableDeepCopy = auto()
    optShowNonExportedFields = auto(); optJsBigInt64 = auto()
    optDocRaw = auto(); optItaniumMangle = auto(); optCompress = auto()
    optWithinConfigSystem = auto()

TGlobalOptions = set  # set[TGlobalOption]


# --- Feature ---
class Feature(NIntEnum):
    dotOperators = auto(); callOperator = auto(); parallel = auto()
    destructor = auto(); notnil = auto(); dynamicBindSym = auto()
    forLoopMacros = auto(); caseStmtMacros = auto(); codeReordering = auto()
    compiletimeFFI = auto(); vmopsDanger = auto(); strictFuncs = auto()
    views = auto(); strictNotNil = auto(); overloadableEnums = auto()
    strictEffects = auto(); unicodeOperators = auto()
    flexibleOptionalParams = auto(); strictDefs = auto()
    strictCaseObjects = auto(); inferGenericTypes = auto()
    openSym = auto(); genericsOpenSym = auto(); vtables = auto()
    typeBoundOps = auto()


# --- Command ---
class Command(NIntEnum):
    cmdNone = auto(); cmdUnknown = auto()
    cmdCompileToC = auto(); cmdCompileToCpp = auto(); cmdCompileToOC = auto()
    cmdCompileToJS = auto(); cmdCrun = auto(); cmdTcc = auto()
    cmdCheck = auto(); cmdM = auto(); cmdParse = auto()
    cmdIdeTools = auto(); cmdNimscript = auto()
    cmdDoc0 = auto(); cmdDoc = auto(); cmdDoc2tex = auto()
    cmdRst2html = auto(); cmdRst2tex = auto()
    cmdMd2html = auto(); cmdMd2tex = auto()
    cmdJsondoc0 = auto(); cmdJsondoc = auto(); cmdCtags = auto()
    cmdBuildindex = auto(); cmdGendepend = auto(); cmdDump = auto()
    cmdInteractive = auto(); cmdNop = auto(); cmdJsonscript = auto()
    cmdCompileToNif = auto(); cmdNifC = auto(); cmdIc = auto()

cmdDocLike = {Command.cmdDoc0, Command.cmdDoc, Command.cmdDoc2tex,
              Command.cmdJsondoc0, Command.cmdJsondoc, Command.cmdCtags,
              Command.cmdBuildindex}


# --- IdeCmd ---
class IdeCmd(NIntEnum):
    ideNone = auto(); ideSug = auto(); ideCon = auto(); ideDef = auto()
    ideUse = auto(); ideDus = auto(); ideChk = auto(); ideChkFile = auto()
    ideMod = auto(); ideHighlight = auto(); ideOutline = auto()
    ideKnown = auto(); ideMsg = auto(); ideProject = auto()
    ideGlobalSymbols = auto(); ideRecompile = auto(); ideChanged = auto()
    ideType = auto(); ideDeclaration = auto(); ideExpand = auto()
    ideInlayHints = auto()


# --- ConfigRef ---
DefaultOptions = {
    TOption.optObjCheck, TOption.optFieldCheck, TOption.optRangeCheck,
    TOption.optBoundsCheck, TOption.optOverflowCheck, TOption.optAssert,
    TOption.optWarns, TOption.optRefCheck, TOption.optHints,
    TOption.optStackTrace, TOption.optLineTrace,
    TOption.optTrMacros, TOption.optStyleCheck, TOption.optCursorInference,
}

DefaultGlobalOptions = {
    TGlobalOption.optThreadAnalysis, TGlobalOption.optExcessiveStackTrace,
    TGlobalOption.optJsBigInt64, TGlobalOption.optItaniumMangle,
}


class ConfigRef:
    """Compiler configuration — extensible stub."""
    def __init__(self):
        self.target = Target()
        self.options: set = set(DefaultOptions)
        self.globalOptions: set = set(DefaultGlobalOptions)
        self.m = initMsgConfig()
        self.cmd = Command.cmdNone
        self.errorCounter = 0
        self.errorMax = 0
        self.warnCounter = 0
        self.hintCounter = 0
        self.exitcode = 0
        self.verbosity = 1
        self.notes: set = set(NotesVerbosity[1]) if len(NotesVerbosity[1]) > 0 else set()
        self.mainPackageNotes: set = set()
        self.foreignPackageNotes: set = set()
        self.warningAsErrors: set = set()
        self.features: set = set()
        self.ideCmd = IdeCmd.ideNone
        self.symbols: dict[str, str] = {}
        self.writelnHook = None
        self.structuredErrorHook = None
        self.unitSep = ""
        self.projectPath = AbsoluteDir("")
        self.projectName = ""
        self.projectFull = AbsoluteFile("")

    def hasHint(self, note) -> bool:
        if TOption.optHints not in self.options:
            return False
        return note in self.notes

    def hasWarn(self, note) -> bool:
        return TOption.optWarns in self.options and note in self.notes

    def isDefined(self, symbol: str) -> bool:
        return symbol in self.symbols


def newConfigRef() -> ConfigRef:
    conf = ConfigRef()
    setTargetFromSystem(conf.target)
    return conf

def importantComments(conf: ConfigRef) -> bool:
    return conf.cmd in cmdDocLike or conf.cmd == Command.cmdIdeTools
