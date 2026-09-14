# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.hashes import hash as std_hash, Hash
from nimic.std.tables import Table

from ropes import Rope
from pathutils import AbsoluteFile, RelativeFile


with const:
    explanationsBaseUrl = "https://nim-lang.github.io/Nim"
    # was: "https://nim-lang.org/docs" but we're now usually showing devel docs
    # instead of latest release docs.

def createDocLink(urlSuffix: string) -> string:
    # os.`/` is not appropriate for urls.
    result = string(explanationsBaseUrl)
    if len(urlSuffix) > 0 and ord(urlSuffix[0]) == ord('/'):
        result += urlSuffix
    else:
        result += string("/") + urlSuffix
    return result

class TMsgKind(NStrEnum):
    # fatal errors
    errUnknown = auto()
    errFatal = auto()
    errInternal = auto()
    # non-fatal errors
    errIllFormedAstX = auto()
    errCannotOpenFile = auto()
    errXExpected = auto()
    errRstMissingClosing = auto()
    errRstGridTableNotImplemented = auto()
    errRstMarkdownIllformedTable = auto()
    errRstIllformedTable = auto()
    errRstNewSectionExpected = auto()
    errRstGeneralParseError = auto()
    errRstInvalidDirectiveX = auto()
    errRstInvalidField = auto()
    errRstFootnoteMismatch = auto()
    errRstSandboxedDirective = auto()
    errProveInit = auto() # deadcode
    errGenerated = auto()
    errFailedMove = auto()
    errUser = auto()
    # warnings
    warnCannotOpenFile = "CannotOpenFile"
    warnOctalEscape = "OctalEscape"
    warnXIsNeverRead = "XIsNeverRead"
    warnXmightNotBeenInit = "XmightNotBeenInit"
    warnDeprecated = "Deprecated"
    warnConfigDeprecated = "ConfigDeprecated"
    warnDotLikeOps = "DotLikeOps"
    warnSmallLshouldNotBeUsed = "SmallLshouldNotBeUsed"
    warnUnknownMagic = "UnknownMagic"
    warnRstRedefinitionOfLabel = "RedefinitionOfLabel"
    warnRstUnknownSubstitutionX = "UnknownSubstitutionX"
    warnRstAmbiguousLink = "AmbiguousLink"
    warnRstBrokenLink = "BrokenLink"
    warnRstLanguageXNotSupported = "LanguageXNotSupported"
    warnRstFieldXNotSupported = "FieldXNotSupported"
    warnRstUnusedImportdoc = "UnusedImportdoc"
    warnRstStyle = "warnRstStyle"
    warnCommentXIgnored = "CommentXIgnored"
    warnTypelessParam = "TypelessParam"
    warnUseBase = "UseBase"
    warnWriteToForeignHeap = "WriteToForeignHeap"
    warnUnsafeCode = "UnsafeCode"
    warnUnusedImportX = "UnusedImport"
    warnInheritFromException = "InheritFromException"
    warnEachIdentIsTuple = "EachIdentIsTuple"
    warnUnsafeSetLen = "UnsafeSetLen"
    warnUnsafeDefault = "UnsafeDefault"
    warnProveInit = "ProveInit"
    warnProveField = "ProveField"
    warnProveIndex = "ProveIndex"
    warnUnreachableElse = "UnreachableElse"
    warnUnreachableCode = "UnreachableCode"
    warnStaticIndexCheck = "IndexCheck"
    warnGcUnsafe = "GcUnsafe"
    warnGcUnsafe2 = "GcUnsafe2"
    warnUninit = "Uninit"
    warnGcMem = "GcMem"
    warnDestructor = "Destructor"
    warnLockLevel = "LockLevel" # deadcode
    warnResultShadowed = "ResultShadowed"
    warnInconsistentSpacing = "Spacing"
    warnCaseTransition = "CaseTransition"
    warnCycleCreated = "CycleCreated"
    warnObservableStores = "ObservableStores"
    warnStrictNotNil = "StrictNotNil"
    warnResultUsed = "ResultUsed"
    warnCannotOpen = "CannotOpen"
    warnFileChanged = "FileChanged"
    warnSuspiciousEnumConv = "EnumConv"
    warnAnyEnumConv = "AnyEnumConv"
    warnHoleEnumConv = "HoleEnumConv"
    warnCstringConv = "CStringConv"
    warnPtrToCstringConv = "PtrToCstringConv"
    warnEffect = "Effect"
    warnCastSizes = "CastSizes" # deadcode
    warnAboveMaxSizeSet = "AboveMaxSizeSet"
    warnImplicitTemplateRedefinition = "ImplicitTemplateRedefinition"
    warnUnnamedBreak = "UnnamedBreak"
    warnStmtListLambda = "StmtListLambda"
    warnBareExcept = "BareExcept"
    warnImplicitDefaultValue = "ImplicitDefaultValue"
    warnIgnoredSymbolInjection = "IgnoredSymbolInjection"
    warnStdPrefix = "StdPrefix"
    warnUnknownNotes = "UnknownNotes"
    warnLongLiterals = "LongLiterals"
    warnUser = "User"
    warnGlobalVarConstructorTemporary = "GlobalVarConstructorTemporary"
    warnImplicitRangeConversion = "ImplicitRangeConversion"
    warnSystemRangeConversion = "SystemRangeConversion"
    # hints
    hintSuccess = "Success"
    hintSuccessX = "SuccessX"
    hintCC = "CC"
    hintXDeclaredButNotUsed = "XDeclaredButNotUsed"
    hintDuplicateModuleImport = "DuplicateModuleImport"
    hintXCannotRaiseY = "XCannotRaiseY"
    hintConvToBaseNotNeeded = "ConvToBaseNotNeeded"
    hintConvFromXtoItselfNotNeeded = "ConvFromXtoItselfNotNeeded"
    hintExprAlwaysX = "ExprAlwaysX"
    hintQuitCalled = "QuitCalled"
    hintProcessing = "Processing"
    hintProcessingStmt = "ProcessingStmt"
    hintCodeBegin = "CodeBegin"
    hintCodeEnd = "CodeEnd"
    hintConf = "Conf"
    hintPath = "Path"
    hintConditionAlwaysTrue = "CondTrue"
    hintConditionAlwaysFalse = "CondFalse"
    hintName = "Name"
    hintPattern = "Pattern"
    hintExecuting = "Exec"
    hintLinking = "Link"
    hintDependency = "Dependency"
    hintSource = "Source"
    hintPerformance = "Performance"
    hintStackTrace = "StackTrace"
    hintGCStats = "GCStats"
    hintGlobalVar = "GlobalVar"
    hintExpandMacro = "ExpandMacro"
    hintUser = "User"
    hintUserRaw = "UserRaw"
    hintExtendedContext = "ExtendedContext"
    hintUnknownRaises = "UnknownRaises"
    hintMsgOrigin = "MsgOrigin" # since 1.3.5
    hintDeclaredLoc = "DeclaredLoc" # since 1.5.1

with const:
    MsgKindToStr = array[TMsgKind, string]({
        TMsgKind.errUnknown: string("unknown error"),
        TMsgKind.errFatal: string("fatal error: $1"),
        TMsgKind.errInternal: string("internal error: $1"),
        TMsgKind.errIllFormedAstX: string("illformed AST: $1"),
        TMsgKind.errCannotOpenFile: string("cannot open '$1'"),
        TMsgKind.errXExpected: string("'$1' expected"),
        TMsgKind.errRstMissingClosing: string("$1"),
        TMsgKind.errRstGridTableNotImplemented: string("grid table is not implemented"),
        TMsgKind.errRstMarkdownIllformedTable: string("illformed delimiter row of a markdown table"),
        TMsgKind.errRstIllformedTable: string("Illformed table: $1"),
        TMsgKind.errRstNewSectionExpected: string("new section expected $1"),
        TMsgKind.errRstGeneralParseError: string("general parse error"),
        TMsgKind.errRstInvalidDirectiveX: string("invalid directive: '$1'"),
        TMsgKind.errRstInvalidField: string("invalid field: $1"),
        TMsgKind.errRstFootnoteMismatch: string("number of footnotes and their references don't match: $1"),
        TMsgKind.errRstSandboxedDirective: string("disabled directive: '$1'"),
        TMsgKind.errProveInit: string("Cannot prove that '$1' is initialized."),  # deadcode
        TMsgKind.errGenerated: string("$1"),
        TMsgKind.errFailedMove: string("$1"),
        TMsgKind.errUser: string("$1"),
        TMsgKind.warnCannotOpenFile: string("cannot open '$1'"),
        TMsgKind.warnOctalEscape: string("octal escape sequences do not exist; leading zero is ignored"),
        TMsgKind.warnXIsNeverRead: string("'$1' is never read"),
        TMsgKind.warnXmightNotBeenInit: string("'$1' might not have been initialized"),
        TMsgKind.warnDeprecated: string("$1"),
        TMsgKind.warnConfigDeprecated: string("config file '$1' is deprecated"),
        TMsgKind.warnDotLikeOps: string("$1"),
        TMsgKind.warnSmallLshouldNotBeUsed: string("'l' should not be used as an identifier; may look like '1' (one)"),
        TMsgKind.warnUnknownMagic: string("unknown magic '$1' might crash the compiler"),
        TMsgKind.warnRstRedefinitionOfLabel: string("redefinition of label '$1'"),
        TMsgKind.warnRstUnknownSubstitutionX: string("unknown substitution '$1'"),
        TMsgKind.warnRstAmbiguousLink: string("ambiguous doc link $1"),
        TMsgKind.warnRstBrokenLink: string("broken link '$1'"),
        TMsgKind.warnRstLanguageXNotSupported: string("language '$1' not supported"),
        TMsgKind.warnRstFieldXNotSupported: string("field '$1' not supported"),
        TMsgKind.warnRstUnusedImportdoc: string("importdoc for '$1' is not used"),
        TMsgKind.warnRstStyle: string("RST style: $1"),
        TMsgKind.warnCommentXIgnored: string("comment '$1' ignored"),
        TMsgKind.warnTypelessParam: string(""), # deadcode
        TMsgKind.warnUseBase: string("use {.base.} for base methods; baseless methods are deprecated"),
        TMsgKind.warnWriteToForeignHeap: string("write to foreign heap"),
        TMsgKind.warnUnsafeCode: string("unsafe code: '$1'"),
        TMsgKind.warnUnusedImportX: string("imported and not used: '$1'"),
        TMsgKind.warnInheritFromException: string("inherit from a more precise exception type like ValueError, IOError or OSError. If these don't suit, inherit from CatchableError or Defect."),
        TMsgKind.warnEachIdentIsTuple: string("each identifier is a tuple"),
        TMsgKind.warnUnsafeSetLen: string("setLen can potentially expand the sequence, but the element type '$1' doesn't have a valid default value"),
        TMsgKind.warnUnsafeDefault: string("The '$1' type doesn't have a valid default value"),
        TMsgKind.warnProveInit: string("Cannot prove that '$1' is initialized. This will become a compile time error in the future."),
        TMsgKind.warnProveField: string("cannot prove that field '$1' is accessible"),
        TMsgKind.warnProveIndex: string("cannot prove index '$1' is valid"),
        TMsgKind.warnUnreachableElse: string("unreachable else, all cases are already covered"),
        TMsgKind.warnUnreachableCode: string("unreachable code after 'return' statement or '{.noReturn.}' proc"),
        TMsgKind.warnStaticIndexCheck: string("$1"),
        TMsgKind.warnGcUnsafe: string("not GC-safe: '$1'"),
        TMsgKind.warnGcUnsafe2: string("$1"),
        TMsgKind.warnUninit: string("use explicit initialization of '$1' for clarity"),
        TMsgKind.warnGcMem: string("'$1' uses GC'ed memory"),
        TMsgKind.warnDestructor: string("usage of a type with a destructor in a non destructible context. This will become a compile time error in the future."),
        TMsgKind.warnLockLevel: string("$1"), # deadcode
        TMsgKind.warnResultShadowed: string("Special variable 'result' is shadowed."),
        TMsgKind.warnInconsistentSpacing: string("Number of spaces around '$#' is not consistent"),
        TMsgKind.warnCaseTransition: string("Potential object case transition, instantiate new object instead"),
        TMsgKind.warnCycleCreated: string("$1"),
        TMsgKind.warnObservableStores: string("observable stores to '$1'"),
        TMsgKind.warnStrictNotNil: string("$1"),
        TMsgKind.warnResultUsed: string("used 'result' variable"),
        TMsgKind.warnCannotOpen: string("cannot open: $1"),
        TMsgKind.warnFileChanged: string("file changed: $1"),
        TMsgKind.warnSuspiciousEnumConv: string("$1"),
        TMsgKind.warnAnyEnumConv: string("$1"),
        TMsgKind.warnHoleEnumConv: string("$1"),
        TMsgKind.warnCstringConv: string("$1"),
        TMsgKind.warnPtrToCstringConv: string("unsafe conversion to 'cstring' from '$1'; Use a `cast` operation like `cast[cstring](x)`; this will become a compile time error in the future"),
        TMsgKind.warnEffect: string("$1"),
        TMsgKind.warnCastSizes: string("$1"), # deadcode
        TMsgKind.warnAboveMaxSizeSet: string("$1"),
        TMsgKind.warnImplicitTemplateRedefinition: string("template '$1' is implicitly redefined; this is deprecated, add an explicit .redefine pragma"),
        TMsgKind.warnUnnamedBreak: string("Using an unnamed break in a block is deprecated; Use a named block with a named break instead"),
        TMsgKind.warnStmtListLambda: string("statement list expression assumed to be anonymous proc; this is deprecated, use `do (): ...` or `proc () = ...` instead"),
        TMsgKind.warnBareExcept: string("$1"),
        TMsgKind.warnImplicitDefaultValue: string("$1"),
        TMsgKind.warnIgnoredSymbolInjection: string("$1"),
        TMsgKind.warnStdPrefix: string("$1 needs the 'std' prefix"),
        TMsgKind.warnUnknownNotes: string("$1"),
        TMsgKind.warnLongLiterals: string("$1"),
        TMsgKind.warnUser: string("$1"),
        TMsgKind.warnGlobalVarConstructorTemporary: string("global variable '$1' initialization requires a temporary variable"),
        TMsgKind.warnImplicitRangeConversion: string("implicit range conversion $1"),
        TMsgKind.warnSystemRangeConversion: string("implicit range conversion $1"),
        TMsgKind.hintSuccess: string("operation successful: $#"),
        # keep in sync with `testament.isSuccess`
        TMsgKind.hintSuccessX: string("$build\n$loc lines; ${sec}s; $mem; proj: $project; out: $output"),
        TMsgKind.hintCC: string("CC: $1"),
        TMsgKind.hintXDeclaredButNotUsed: string("'$1' is declared but not used"),
        TMsgKind.hintDuplicateModuleImport: string("$1"),
        TMsgKind.hintXCannotRaiseY: string("$1"),
        TMsgKind.hintConvToBaseNotNeeded: string("conversion to base object is not needed"),
        TMsgKind.hintConvFromXtoItselfNotNeeded: string("conversion from $1 to itself is pointless"),
        TMsgKind.hintExprAlwaysX: string("expression evaluates always to '$1'"),
        TMsgKind.hintQuitCalled: string("quit() called"),
        TMsgKind.hintProcessing: string("$1"),
        TMsgKind.hintProcessingStmt: string("$1"),
        TMsgKind.hintCodeBegin: string("generated code listing:"),
        TMsgKind.hintCodeEnd: string("end of listing"),
        TMsgKind.hintConf: string("used config file '$1'"),
        TMsgKind.hintPath: string("added path: '$1'"),
        TMsgKind.hintConditionAlwaysTrue: string("condition is always true: '$1'"),
        TMsgKind.hintConditionAlwaysFalse: string("condition is always false: '$1'"),
        TMsgKind.hintName: string("$1"),
        TMsgKind.hintPattern: string("$1"),
        TMsgKind.hintExecuting: string("$1"),
        TMsgKind.hintLinking: string("$1"),
        TMsgKind.hintDependency: string("$1"),
        TMsgKind.hintSource: string("$1"),
        TMsgKind.hintPerformance: string("$1"),
        TMsgKind.hintStackTrace: string("$1"),
        TMsgKind.hintGCStats: string("$1"),
        TMsgKind.hintGlobalVar: string("global variable declared here"),
        TMsgKind.hintExpandMacro: string("expanded macro: $1"),
        TMsgKind.hintUser: string("$1"),
        TMsgKind.hintUserRaw: string("$1"),
        TMsgKind.hintExtendedContext: string("$1"),
        TMsgKind.hintUnknownRaises: string("$1 is a forward declaration without explicit .raises, assuming it can raise anything"),
        TMsgKind.hintMsgOrigin: string("$1"),
        TMsgKind.hintDeclaredLoc: string("$1")
    })

with const:
    fatalMsgs = Tset[TMsgKind]({TMsgKind.errUnknown, TMsgKind.errFatal, TMsgKind.errInternal})
    errMin = TMsgKind.errUnknown
    errMax = TMsgKind.errUser
    warnMin = TMsgKind.warnCannotOpenFile
    warnMax = pred(TMsgKind.hintSuccess)
    hintMin = TMsgKind.hintSuccess
    hintMax = high(TMsgKind)
    rstWarnings = Tset[TMsgKind]({TMsgKind.warnRstRedefinitionOfLabel, TMsgKind.warnRstUnknownSubstitutionX, TMsgKind.warnRstAmbiguousLink, TMsgKind.warnRstBrokenLink, TMsgKind.warnRstLanguageXNotSupported, TMsgKind.warnRstFieldXNotSupported, TMsgKind.warnRstUnusedImportdoc, TMsgKind.warnRstStyle})

class TNoteKind(TMsgKind): pass
class TNoteKinds(Tset[TNoteKind]): pass

def computeNotesVerbosity() -> array[4, TNoteKinds]:
    result = array[4, TNoteKinds]()
    result = default(array[4, TNoteKinds])
    result[3] = Tset[TNoteKind](inrange(low(TNoteKind), high(TNoteKind))) - Tset[TNoteKind]({TMsgKind.warnObservableStores, TMsgKind.warnResultUsed, TMsgKind.warnAnyEnumConv, TMsgKind.warnBareExcept, TMsgKind.warnStdPrefix, TMsgKind.warnSystemRangeConversion})
    result[2] = result[3] - Tset[TNoteKind]({TMsgKind.hintStackTrace, TMsgKind.hintExtendedContext, TMsgKind.hintDeclaredLoc, TMsgKind.hintProcessingStmt})
    result[1] = result[2] - Tset[TNoteKind]({TMsgKind.warnImplicitRangeConversion, TMsgKind.warnProveField, TMsgKind.warnProveIndex, TMsgKind.warnGcUnsafe, TMsgKind.hintPath, TMsgKind.hintDependency, TMsgKind.hintCodeBegin, TMsgKind.hintCodeEnd, TMsgKind.hintSource, TMsgKind.hintGlobalVar, TMsgKind.hintGCStats, TMsgKind.hintMsgOrigin, TMsgKind.hintPerformance})
    result[0] = result[1] - Tset[TNoteKind]({TMsgKind.hintSuccessX, TMsgKind.hintSuccess, TMsgKind.hintConf, TMsgKind.hintProcessing, TMsgKind.hintPattern, TMsgKind.hintExecuting, TMsgKind.hintLinking, TMsgKind.hintCC})
    return result

with const:
    NotesVerbosity = computeNotesVerbosity()
    errXMustBeCompileTime = "'$1' can only be used in compile-time context"
    errArgsNeedRunOption = "arguments can only be given if the '--run' option is selected"
    errFloatToString = "cannot convert '$1' to '$2'"

class FileInfoKind(NIntEnum):
    fikSource = 0      ## A real source file path
    fikNifModule = auto()   ## A NIF module suffix (not a real path)

class TFileInfo(Object):
    fullPath: AbsoluteFile    # This is a canonical full filesystem path
    projPath: RelativeFile    # This is relative to the project's root
    shortName: string         # short name of the module
    quotedName: Rope          # cached quoted short name for codegen
                            # purposes
    quotedFullName: Rope      # cached quoted full name for codegen
                            # purposes

    lines: seq[string]        # the source code of the module
                            #   used for better error messages and
                            #   embedding the original source in the
                            #   generated code
    dirtyFile: AbsoluteFile   # the file that is actually read into memory
                            # and parsed; usually "" but is used
                            # for 'nimsuggest'
    hash: string              # the checksum of the file
    dirty: bool               # for 'nimpretty' like tooling
    kind: FileInfoKind        # distinguishes real files from NIF suffixes
    if comptime(defined("nimpretty")):
        fullContent: string

@distinct
class FileIndex(int32):
    def __eq__(self: static[FileIndex], b: FileIndex) -> bool:
        """{.borrow.}"""
        return super().__eq__(b)

class TLineInfo(Object):
    line: uint16
    col: int16
    fileIndex: FileIndex
    if comptime(defined("nimpretty")):
        offsetA: nint
        offsetB: nint
        commentOffsetA: nint
        commentOffsetB: nint

class TErrorOutput(NIntEnum):
    eStdOut = auto()
    eStdErr = auto()

class TErrorOutputs(Tset[TErrorOutput]): pass

class ERecoverableError(ValueError): pass
class ESuggestDone(ValueError): pass

def hash(i: TLineInfo) -> Hash:
    return std_hash((int(i.line), int(i.col), int(i.fileIndex)))

def raiseRecoverableError(msg: string):
    """{.noinline, noreturn.}"""
    raise ERecoverableError(msg)

with const:
    InvalidFileIdx = FileIndex(-1)
    unknownLineInfo = TLineInfo(line=0, col=-1, fileIndex=InvalidFileIdx)

class Severity(NIntEnum):
    """{.pure.}"""
    Hint = auto()
    Warning = auto()
    Error = auto()

with const:
    trackPosInvalidFileIdx = FileIndex(-2)
    commandLineIdx = FileIndex(-3)

class class_msgContext_1(NTuple):
    info: TLineInfo
    detail: string

class MsgConfig(Object):
    trackPos: TLineInfo
    trackPosAttached: bool

    errorOutputs: TErrorOutputs
    msgContext: seq[class_msgContext_1]
    lastError: TLineInfo
    filenameToIndexTbl: Table[string, FileIndex]
    fileInfos: seq[TFileInfo]
    systemFileIdx: FileIndex

def initMsgConfig() -> MsgConfig:
    result = MsgConfig(msgContext=seq[class_msgContext_1](), lastError=unknownLineInfo, filenameToIndexTbl=Table[string, FileIndex](), fileInfos=seq[TFileInfo](), errorOutputs=TErrorOutputs({TErrorOutput.eStdOut, TErrorOutput.eStdErr}))
    result.filenameToIndexTbl[string("???")] = FileIndex(-1)
    return result

if comptime(__name__ == '__main__'):
    import nimic.std.assertions

    link = createDocLink(string("foo"))
    assert link == string("https://nim-lang.github.io/Nim/foo")

    link2 = createDocLink(string("/bar"))
    assert link2 == string("https://nim-lang.github.io/Nim/bar")

    msgConfig = initMsgConfig()
    assert msgConfig.lastError == unknownLineInfo
    assert string("???") in msgConfig.filenameToIndexTbl
    assert msgConfig.filenameToIndexTbl[string("???")] == FileIndex(-1)

    assert MsgKindToStr[TMsgKind.errUnknown] == string("unknown error")

    print("All lineinfos tests passed.")
