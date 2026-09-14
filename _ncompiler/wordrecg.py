"""
ncompiler/wordrecg.py — Word recognizer / special words enum
Converted from compiler/wordrecg.nim
"""
# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *


class TSpecialWord(NIntEnum):
    wInvalid = auto()
    wAddr = auto()
    wAnd = auto()
    wAs = auto()
    wAsm = auto()
    wBind = auto()
    wBlock = auto()
    wBreak = auto()
    wCase = auto()
    wCast = auto()
    wConcept = auto()
    wConst = auto()
    wContinue = auto()
    wConverter = auto()
    wDefer = auto()
    wDiscard = auto()
    wDistinct = auto()
    wDiv = auto()
    wDo = auto()
    wElif = auto()
    wElse = auto()
    wEnd = auto()
    wEnum = auto()
    wExcept = auto()
    wExport = auto()
    wFinally = auto()
    wFor = auto()
    wFrom = auto()
    wFunc = auto()
    wIf = auto()
    wImport = auto()
    wIn = auto()
    wInclude = auto()
    wInterface = auto()
    wIs = auto()
    wIsnot = auto()
    wIterator = auto()
    wLet = auto()
    wMacro = auto()
    wMethod = auto()
    wMixin = auto()
    wMod = auto()
    wNil = auto()
    wNot = auto()
    wNotin = auto()
    wObject = auto()
    wOf = auto()
    wOr = auto()
    wOut = auto()
    wProc = auto()
    wPtr = auto()
    wRaise = auto()
    wRef = auto()
    wReturn = auto()
    wShl = auto()
    wShr = auto()
    wStatic = auto()
    wTemplate = auto()
    wTry = auto()
    wTuple = auto()
    wType = auto()
    wUsing = auto()
    wVar = auto()
    wWhen = auto()
    wWhile = auto()
    wXor = auto()
    wYield = auto()

    wColon = auto()
    wColonColon = auto()
    wEquals = auto()
    wDot = auto()
    wDotDot = auto()
    wStar = auto()
    wMinus = auto()
    wUnderscore = auto()

    wMagic = auto()
    wThread = auto()
    wFinal = auto()
    wProfiler = auto()
    wMemTracker = auto()
    wObjChecks = auto()
    wIntDefine = auto()
    wStrDefine = auto()
    wBoolDefine = auto()
    wCursor = auto()
    wNoalias = auto()
    wEffectsOf = auto()
    wUncheckedAssign = auto()
    wRunnableExamples = auto()

    wImmediate = auto()
    wConstructor = auto()
    wDestructor = auto()
    wDelegator = auto()
    wOverride = auto()
    wImportCpp = auto()
    wCppNonPod = auto()
    wImportObjC = auto()
    wImportCompilerProc = auto()
    wImportc = auto()
    wImportJs = auto()
    wExportc = auto()
    wExportCpp = auto()
    wExportNims = auto()
    wIncompleteStruct = auto()
    wCompleteStruct = auto()
    wRequiresInit = auto()
    wAlign = auto()
    wNodecl = auto()
    wPure = auto()
    wSideEffect = auto()
    wHeader = auto()
    wNoSideEffect = auto()
    wGcSafe = auto()
    wNoreturn = auto()
    wNosinks = auto()
    wLib = auto()
    wDynlib = auto()
    wCompilerProc = auto()
    wCore = auto()
    wProcVar = auto()
    wBase = auto()
    wUsed = auto()
    wFatal = auto()
    wError = auto()
    wWarning = auto()
    wHint = auto()
    wWarningAsError = auto()
    wHintAsError = auto()
    wLine = auto()
    wPush = auto()
    wPop = auto()
    wDefine = auto()
    wUndef = auto()
    wLineDir = auto()
    wStackTrace = auto()
    wLineTrace = auto()
    wLink = auto()
    wCompile = auto()
    wLinksys = auto()
    wDeprecated = auto()
    wVarargs = auto()
    wCallconv = auto()
    wDebugger = auto()
    wNimcall = auto()
    wStdcall = auto()
    wCdecl = auto()
    wSafecall = auto()
    wSyscall = auto()
    wInline = auto()
    wNoInline = auto()
    wFastcall = auto()
    wThiscall = auto()
    wClosure = auto()
    wNoconv = auto()
    wOn = auto()
    wOff = auto()
    wChecks = auto()
    wRangeChecks = auto()
    wBoundChecks = auto()
    wOverflowChecks = auto()
    wNilChecks = auto()
    wFloatChecks = auto()
    wNanChecks = auto()
    wInfChecks = auto()
    wStyleChecks = auto()
    wStaticBoundchecks = auto()
    wNonReloadable = auto()
    wExecuteOnReload = auto()
    wAssertions = auto()
    wPatterns = auto()
    wTrMacros = auto()
    wSinkInference = auto()
    wWarnings = auto()
    wHints = auto()
    wOptimization = auto()
    wRaises = auto()
    wWrites = auto()
    wReads = auto()
    wSize = auto()
    wEffects = auto()
    wTags = auto()
    wForbids = auto()
    wRequires = auto()
    wEnsures = auto()
    wInvariant = auto()
    wAssume = auto()
    wAssert = auto()
    wDeadCodeElimUnused = auto()
    wSafecode = auto()
    wPackage = auto()
    wNoForward = auto()
    wReorder = auto()
    wNoRewrite = auto()
    wNoDestroy = auto()
    wPragma = auto()
    wCompileTime = auto()
    wNoInit = auto()
    wPassc = auto()
    wPassl = auto()
    wLocalPassc = auto()
    wBorrow = auto()
    wDiscardable = auto()
    wFieldChecks = auto()
    wSubsChar = auto()
    wAcyclic = auto()
    wShallow = auto()
    wUnroll = auto()
    wLinearScanEnd = auto()
    wComputedGoto = auto()
    wExperimental = auto()
    wDoctype = auto()
    wWrite = auto()
    wGensym = auto()
    wInject = auto()
    wDirty = auto()
    wInheritable = auto()
    wThreadVar = auto()
    wEmit = auto()
    wAsmNoStackFrame = auto()
    wAsmSyntax = auto()
    wImplicitStatic = auto()
    wGlobal = auto()
    wCodegenDecl = auto()
    wUnchecked = auto()
    wGuard = auto()
    wLocks = auto()
    wPartial = auto()
    wExplain = auto()
    wLiftLocals = auto()
    wEnforceNoRaises = auto()
    wSystemRaisesDefect = auto()
    wRedefine = auto()
    wCallsite = auto()
    wQuirky = auto()

    # codegen keywords that are also pragmas
    wExtern = auto()
    wGoto = auto()
    wRegister = auto()
    wUnion = auto()
    wPacked = auto()
    wVirtual = auto()
    wVolatile = auto()
    wMember = auto()
    wByCopy = auto()
    wByRef = auto()

    # codegen keywords but not pragmas
    wAuto = auto()
    wBool = auto()
    wCatch = auto()
    wChar = auto()
    wClass = auto()
    wCompl = auto()
    wConstCast = auto()
    wDefault = auto()
    wDelete = auto()
    wDouble = auto()
    wDynamicCast = auto()
    wExplicit = auto()
    wFalse = auto()
    wFloat = auto()
    wFriend = auto()
    wInt = auto()
    wLong = auto()
    wMutable = auto()
    wNamespace = auto()
    wNew = auto()
    wOperator = auto()
    wPrivate = auto()
    wProtected = auto()
    wPublic = auto()
    wReinterpretCast = auto()
    wRestrict = auto()
    wShort = auto()
    wSigned = auto()
    wSizeof = auto()
    wStaticCast = auto()
    wStruct = auto()
    wSwitch = auto()
    wThis = auto()
    wThrow = auto()
    wTrue = auto()
    wTypedef = auto()
    wTypeid = auto()
    wTypeof = auto()
    wTypename = auto()
    wUnsigned = auto()
    wVoid = auto()

    wAlignas = auto()
    wAlignof = auto()
    wConstexpr = auto()
    wDecltype = auto()
    wNullptr = auto()
    wNoexcept = auto()
    wThreadLocal = auto()
    wStaticAssert = auto()
    wChar16 = auto()
    wChar32 = auto()
    wWchar = auto()

    wStdIn = auto()
    wStdOut = auto()
    wStdErr = auto()

    wInOut = auto()
    wOneWay = auto()

    wBitsize = auto()
    wImportHidden = auto()
    wSendable = auto()


# Map from TSpecialWord to its string representation
# Only Nim keywords need string values; the rest use the enum name
_SPECIAL_WORD_STRINGS = {
    TSpecialWord.wInvalid: "",
    TSpecialWord.wAddr: "addr", TSpecialWord.wAnd: "and",
    TSpecialWord.wAs: "as", TSpecialWord.wAsm: "asm",
    TSpecialWord.wBind: "bind", TSpecialWord.wBlock: "block",
    TSpecialWord.wBreak: "break", TSpecialWord.wCase: "case",
    TSpecialWord.wCast: "cast", TSpecialWord.wConcept: "concept",
    TSpecialWord.wConst: "const", TSpecialWord.wContinue: "continue",
    TSpecialWord.wConverter: "converter", TSpecialWord.wDefer: "defer",
    TSpecialWord.wDiscard: "discard", TSpecialWord.wDistinct: "distinct",
    TSpecialWord.wDiv: "div", TSpecialWord.wDo: "do",
    TSpecialWord.wElif: "elif", TSpecialWord.wElse: "else",
    TSpecialWord.wEnd: "end", TSpecialWord.wEnum: "enum",
    TSpecialWord.wExcept: "except", TSpecialWord.wExport: "export",
    TSpecialWord.wFinally: "finally", TSpecialWord.wFor: "for",
    TSpecialWord.wFrom: "from", TSpecialWord.wFunc: "func",
    TSpecialWord.wIf: "if", TSpecialWord.wImport: "import",
    TSpecialWord.wIn: "in", TSpecialWord.wInclude: "include",
    TSpecialWord.wInterface: "interface", TSpecialWord.wIs: "is",
    TSpecialWord.wIsnot: "isnot", TSpecialWord.wIterator: "iterator",
    TSpecialWord.wLet: "let", TSpecialWord.wMacro: "macro",
    TSpecialWord.wMethod: "method", TSpecialWord.wMixin: "mixin",
    TSpecialWord.wMod: "mod", TSpecialWord.wNil: "nil",
    TSpecialWord.wNot: "not", TSpecialWord.wNotin: "notin",
    TSpecialWord.wObject: "object", TSpecialWord.wOf: "of",
    TSpecialWord.wOr: "or", TSpecialWord.wOut: "out",
    TSpecialWord.wProc: "proc", TSpecialWord.wPtr: "ptr",
    TSpecialWord.wRaise: "raise", TSpecialWord.wRef: "ref",
    TSpecialWord.wReturn: "return", TSpecialWord.wShl: "shl",
    TSpecialWord.wShr: "shr", TSpecialWord.wStatic: "static",
    TSpecialWord.wTemplate: "template", TSpecialWord.wTry: "try",
    TSpecialWord.wTuple: "tuple", TSpecialWord.wType: "type",
    TSpecialWord.wUsing: "using", TSpecialWord.wVar: "var",
    TSpecialWord.wWhen: "when", TSpecialWord.wWhile: "while",
    TSpecialWord.wXor: "xor", TSpecialWord.wYield: "yield",
    TSpecialWord.wColon: ":", TSpecialWord.wColonColon: "::",
    TSpecialWord.wEquals: "=", TSpecialWord.wDot: ".",
    TSpecialWord.wDotDot: "..", TSpecialWord.wStar: "*",
    TSpecialWord.wMinus: "-", TSpecialWord.wUnderscore: "_",
}


def specialWordToStr(w: TSpecialWord) -> str:
    """Get the string representation of a TSpecialWord."""
    if w in _SPECIAL_WORD_STRINGS:
        return _SPECIAL_WORD_STRINGS[w]
    return w.name[1:].lower()  # strip 'w' prefix, lowercase


oprLow = TSpecialWord.wColon.value
oprHigh = TSpecialWord.wDotDot.value

nimKeywordsLow = TSpecialWord.wAsm.value
nimKeywordsHigh = TSpecialWord.wYield.value

ccgKeywordsLow = TSpecialWord.wExtern.value
ccgKeywordsHigh = TSpecialWord.wOneWay.value

nonPragmaWordsLow = TSpecialWord.wAuto
nonPragmaWordsHigh = TSpecialWord.wOneWay


def _nimIdentNormalize(s: str) -> str:
    """Normalize a Nim identifier: lowercase, strip underscores (except first char)."""
    if len(s) == 0:
        return s
    result = [s[0].lower()]
    i = 1
    while i < len(s):
        c = s[i]
        if c != '_':
            result.append(c.lower())
        i += 1
    return "".join(result)


# Build reverse lookup: normalized string -> TSpecialWord
_STRING_TO_SPECIAL_WORD = {}
for _w in TSpecialWord:
    _s = specialWordToStr(_w)
    if _s:
        _STRING_TO_SPECIAL_WORD[_nimIdentNormalize(_s)] = _w


def findStr(s: str) -> TSpecialWord:
    """Find a TSpecialWord by its string representation (nim-identifier-normalized)."""
    return _STRING_TO_SPECIAL_WORD.get(_nimIdentNormalize(s), TSpecialWord.wInvalid)
