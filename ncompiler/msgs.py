from __future__ import annotations

from nimic.ntypes import *
from nimic.std.strutils import *
from nimic.std.os import *
from nimic.std.syncio import stdout, stderr, write, writeLine, flushFile, File, open, close, FileMode, lines
from nimic.std.tables import *

from .lineinfos import *
from .pathutils import *
from .options import *
from .ropes import *


class InstantiationInfo(NTuple):
    filename: string
    line: nint
    column: nint

def instLoc() -> InstantiationInfo:
    return InstantiationInfo(filename=string(""), line=0, column=0)



def toStdOrrKind(stdOrr: File) -> StdOrrKind:
    if stdOrr == stdout: return StdOrrKind.stdOrrStdout
    else: return StdOrrKind.stdOrrStderr

# toLowerAscii is already defined in nimic.std.strutils

def flushDot(conf: ConfigRef) -> None:
    with let:
        stdOrr = stdout if TGlobalOption.optStdout in conf.globalOptions else stderr
        stdOrrKind = toStdOrrKind(stdOrr)
    if stdOrrKind in conf.lastMsgWasDot:
        conf.lastMsgWasDot.excl(stdOrrKind)
        write(stdOrr, string("\n"))


def toCChar(c: char, result: mut @ string) -> None:
    with let:
        code = ord(c)
    if (code >= 0 and code <= 0x1F) or (code >= 0x7F and code <= 0xFF):
        result.add(string("\\"))
        result.add(toOctal(c))
    elif str(c) in ("'", '"', '\\', '?'):
        result.add(string("\\"))
        result.add(c)
    else:
        result.add(c)


def makeCString(s: string) -> Rope:
    with var:
        res = string("\"")
    for i in range(len(s)):
        toCChar(s[i], res)
    res.add(string("\""))
    return rope(res)

def newFileInfo(fullPath: AbsoluteFile, projPath: RelativeFile, kind: FileInfoKind = FileInfoKind.fikSource) -> TFileInfo:
    result = TFileInfo(
        fullPath=fullPath,
        projPath=projPath,
        shortName=extractFilename(fullPath),
        quotedFullName=makeCString(string(fullPath)),
        lines=seq[string](),
        kind=kind
    )
    result.quotedName = makeCString(result.shortName)
    if comptime(defined("nimpretty")):
        if not isEmpty(result.fullPath):
            try:
                with open(string(result.fullPath), 'r') as f:
                    result.fullContent = string(f.read())
            except IOError:
                result.fullContent = string("")
    return result

if comptime(defined("nimpretty")):
    def fileSection(conf: ConfigRef, fid: FileIndex, a: nint, b: nint) -> string:
        return substr(conf.m.fileInfos[nint(fid)].fullContent, a, b)

def canonicalCase(path: mut @ string) -> None:
    if not comptime(defined("FileSystemCaseSensitive")):
        path <<= toLowerAscii(path)

def fileInfoKnown(conf: ConfigRef, filename: AbsoluteFile) -> bool:
    with var:
        canon = filename
    try:
        canon = canonicalizePath(conf, filename)
    except OSError:
        canon = filename
    with var:
        c_str = string(canon)
    canonicalCase(c_str)
    return conf.m.filenameToIndexTbl.hasKey(c_str)

@dispatch
def fileInfoIdx(conf: ConfigRef, filename: AbsoluteFile, isKnownFile: mut @ bool) -> FileIndex:
    with var:
        pseudoPath = False
        canon = filename
    try:
        canon = canonicalizePath(conf, filename)
    except OSError:
        canon = filename
        pseudoPath = True

    with var:
        canon2 = string(canon)
    canonicalCase(canon2)

    if conf.m.filenameToIndexTbl.hasKey(canon2):
        isKnownFile <<= True
        return conf.m.filenameToIndexTbl[canon2]
    else:
        isKnownFile <<= False
        with var:
            res = FileIndex(len(conf.m.fileInfos))
        with let:
            projPath = RelativeFile(string(filename)) if pseudoPath else relativeTo(canon, conf.projectPath)
        conf.m.fileInfos.add(newFileInfo(canon, projPath))
        conf.m.filenameToIndexTbl[canon2] = res
        return res

@dispatch
def fileInfoIdx(conf: ConfigRef, filename: AbsoluteFile) -> FileIndex:
    with var:
        dummy = False
    return fileInfoIdx(conf, filename, dummy)

@dispatch
def fileInfoIdx(conf: ConfigRef, filename: RelativeFile, isKnownFile: mut @ bool) -> FileIndex:
    return fileInfoIdx(conf, AbsoluteFile(expandFilename(string(filename))), isKnownFile)

@dispatch
def fileInfoIdx(conf: ConfigRef, filename: RelativeFile) -> FileIndex:
    with var:
        dummy = False
    return fileInfoIdx(conf, AbsoluteFile(expandFilename(string(filename))), dummy)

@dispatch
def registerNifSuffix(conf: ConfigRef, suffix: string, isKnownFile: mut @ bool) -> FileIndex:
    with var:
        canon = string(suffix)
    canonicalCase(canon)
    if conf.m.filenameToIndexTbl.hasKey(canon):
        isKnownFile <<= True
        return conf.m.filenameToIndexTbl[canon]
    else:
        isKnownFile <<= False
        with var:
            res = FileIndex(len(conf.m.fileInfos))
        conf.m.fileInfos.add(newFileInfo(AbsoluteFile(suffix), RelativeFile(suffix), FileInfoKind.fikNifModule))
        conf.m.filenameToIndexTbl[canon] = res
        return res

@dispatch
def registerNifSuffix(conf: ConfigRef, suffix: string) -> FileIndex:
    with var:
        dummy = False
    return registerNifSuffix(conf, suffix, dummy)

def fileInfoKind(conf: ConfigRef, fileIdx: FileIndex) -> FileInfoKind:
    if nint(fileIdx) >= 0 and nint(fileIdx) < len(conf.m.fileInfos):
        return conf.m.fileInfos[nint(fileIdx)].kind
    else:
        return FileInfoKind.fikSource

@dispatch
def newLineInfo(fileInfoIdx: FileIndex, line: nint, col: nint) -> TLineInfo:
    result = TLineInfo()
    result.fileIndex = fileInfoIdx
    if line < 65535:
        result.line = uint16(line)
    else:
        result.line = uint16(65535)
    if col < 32767:
        result.col = int16(col)
    else:
        result.col = int16(-1)
    return result

@dispatch
def newLineInfo(conf: ConfigRef, filename: AbsoluteFile, line: nint, col: nint) -> TLineInfo:
    return newLineInfo(fileInfoIdx(conf, filename), line, col)

with const:
    gCmdLineInfo = newLineInfo(commandLineIdx, 1, 1)

def concat(strings: seq[string]) -> string:
    with var:
        res = string("")
    for s in strings:
        res.add(s)
    return res

def suggestWriteln(conf: ConfigRef, s: string) -> None:
    if TErrorOutput.eStdOut in conf.m.errorOutputs:
        if conf.writelnHook is None:
            writeLine(stdout, s)
            flushFile(stdout)
        else:
            conf.writelnHook(s)

def msgQuit(x: nint) -> None:
    quit(x)

def msgQuitStr(x: string) -> None:
    quit(string(x))


class ESuggestDone(ValueError): pass

def suggestQuit() -> None:
    raise newException(ESuggestDone, string("suggest done"))

with const:
    KindFormat = string(" [$1]")
    KindColor = string("fgCyan")
    ErrorTitle = string("Error: ")
    ErrorColor = string("fgRed")
    WarningTitle = string("Warning: ")
    WarningColor = string("fgYellow")
    HintTitle = string("Hint: ")
    HintColor = string("fgGreen")
    ColOffset = 1
    commandLineDesc = string("command line")

def getInfoContextLen(conf: ConfigRef) -> nint:
    return len(conf.m.msgContext)

def setInfoContextLen(conf: ConfigRef, L: nint) -> None:
    conf.m.msgContext.setLen(L)

def pushInfoContext(conf: ConfigRef, info: TLineInfo, detail: string = string("")) -> None:
    with let:
        tup = class_msgContext_1(info=info, detail=detail)
    conf.m.msgContext.add(tup)


def popInfoContext(conf: ConfigRef) -> None:
    conf.m.msgContext.setLen(len(conf.m.msgContext) - 1)

def getInfoContext(conf: ConfigRef, index: nint) -> TLineInfo:
    with let:
        i = len(conf.m.msgContext) + index if index < 0 else index
    if i >= len(conf.m.msgContext):
        return unknownLineInfo
    else:
        return conf.m.msgContext[i].info

def toFilename(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if nint(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return conf.m.fileInfos[nint(fileIdx)].shortName

def toProjPath(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if nint(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return string(conf.m.fileInfos[nint(fileIdx)].projPath)

def toFullPath(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if nint(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return string(conf.m.fileInfos[nint(fileIdx)].fullPath)

def setDirtyFile(conf: ConfigRef, fileIdx: FileIndex, filename: AbsoluteFile) -> None:
    assert nint(fileIdx) >= 0
    conf.m.fileInfos[nint(fileIdx)].dirtyFile = filename
    conf.m.fileInfos[nint(fileIdx)].lines.setLen(0)

def setHash(conf: ConfigRef, fileIdx: FileIndex, hash: string) -> None:
    assert nint(fileIdx) >= 0
    conf.m.fileInfos[nint(fileIdx)].hash = hash

def getHash(conf: ConfigRef, fileIdx: FileIndex) -> string:
    assert nint(fileIdx) >= 0
    return conf.m.fileInfos[nint(fileIdx)].hash


def toFullPathConsiderDirty(conf: ConfigRef, fileIdx: FileIndex) -> AbsoluteFile:
    if nint(fileIdx) < 0:
        return AbsoluteFile(commandLineDesc if fileIdx == commandLineIdx else string("???"))
    elif not isEmpty(conf.m.fileInfos[nint(fileIdx)].dirtyFile):
        return conf.m.fileInfos[nint(fileIdx)].dirtyFile
    else:
        return conf.m.fileInfos[nint(fileIdx)].fullPath

def toFilenameInfo(conf: ConfigRef, info: TLineInfo) -> string:
    return toFilename(conf, info.fileIndex)

def toProjPathInfo(conf: ConfigRef, info: TLineInfo) -> string:
    return toProjPath(conf, info.fileIndex)

def toFullPathInfo(conf: ConfigRef, info: TLineInfo) -> string:
    return toFullPath(conf, info.fileIndex)

def toFullPathConsiderDirtyInfo(conf: ConfigRef, info: TLineInfo) -> string:
    return string(toFullPathConsiderDirty(conf, info.fileIndex))

def toFilenameOption(conf: ConfigRef, fileIdx: FileIndex, opt: FilenameOption) -> string:
    if opt == FilenameOption.foAbs:
        return toFullPath(conf, fileIdx)
    elif opt == FilenameOption.foRelProject:
        return toProjPath(conf, fileIdx)
    elif opt == FilenameOption.foCanonical:
        with let:
            absPath = toFullPath(conf, fileIdx)
        return canonicalImportAux(conf, AbsoluteFile(absPath))
    elif opt == FilenameOption.foName:
        return extractFilename(toProjPath(conf, fileIdx))
    elif opt == FilenameOption.foLegacyRelProj:
        with let:
            absPath = toFullPath(conf, fileIdx)
            relPath = toProjPath(conf, fileIdx)
        if len(relPath) > len(absPath) or relPath.count(string("..")) > 2:
            return absPath
        else:
            return relPath
    elif opt == FilenameOption.foStacktrace:
        if TGlobalOption.optExcessiveStackTrace in conf.globalOptions:
            return toFilenameOption(conf, fileIdx, FilenameOption.foAbs)
        else:
            return toFilenameOption(conf, fileIdx, FilenameOption.foName)


def toMsgFilename(conf: ConfigRef, fileIdx: FileIndex) -> string:
    return toFilenameOption(conf, fileIdx, conf.filenameOption)

def toMsgFilenameInfo(conf: ConfigRef, info: TLineInfo) -> string:
    return toMsgFilename(conf, info.fileIndex)

def toLinenumber(info: TLineInfo) -> nint:
    return nint(info.line)

def toColumn(info: TLineInfo) -> nint:
    return nint(info.col)

def toLocation(res: string, filename: string, line: nint, col: nint) -> string:
    # mock nim's toLocation
    if line > 0:
        return res + filename + string("(") + string(str(line)) + string(", ") + string(str(col)) + string(")")
    return res + filename

def toFileLineColInst(info: InstantiationInfo) -> string:
    return toLocation(string(""), info.filename, info.line, info.column + ColOffset)

def toFileLineCol(conf: ConfigRef, info: TLineInfo) -> string:
    return toLocation(string(""), toMsgFilenameInfo(conf, info), nint(info.line), nint(info.col) + ColOffset)

def lineInfoToStr(conf: ConfigRef, info: TLineInfo) -> string:
    return toFileLineCol(conf, info)

class MsgFlag(NIntEnum):
    msgStdout = 0
    msgSkipHook = auto()
    msgNoUnitSep = auto()

class MsgFlags(Tset[MsgFlag]): pass

def msgWriteln(conf: ConfigRef, s: string, flags: Tset[MsgFlag] = MsgFlags()) -> None:
    with let:
        sep = conf.unitSep if MsgFlag.msgNoUnitSep not in flags else string("")
    if conf.writelnHook is not None and MsgFlag.msgSkipHook not in flags:
        conf.writelnHook(s + sep)
    elif TGlobalOption.optStdout in conf.globalOptions or MsgFlag.msgStdout in flags:
        if TErrorOutput.eStdOut in conf.m.errorOutputs:
            flushDot(conf)
            write(stdout, s)
            writeLine(stdout, sep)
            flushFile(stdout)
    else:
        if TErrorOutput.eStdErr in conf.m.errorOutputs:
            flushDot(conf)
            write(stderr, s)
            writeLine(stderr, sep)
            if comptime(defined("windows")):
                flushFile(stderr)

def msgWrite(conf: ConfigRef, s: string) -> None:
    if len(conf.m.errorOutputs) > 0:
        with let:
            stdOrr = stdout if TGlobalOption.optStdout in conf.globalOptions else stderr
        write(stdOrr, s)
        flushFile(stdOrr)
        conf.lastMsgWasDot.incl(toStdOrrKind(stdOrr))


def styledMsgWriteln(conf: ConfigRef, s: string) -> None:
    # Mocking styledMsgWriteln, just calls msgWriteln
    msgWriteln(conf, s)

def msgKindToString(kind: TMsgKind) -> string:
    return MsgKindToStr[kind]

def getMessageStr(msg: TMsgKind, arg: string) -> string:
    # % [arg] substitution mock
    return msgKindToString(msg).replace(string("$1"), arg)

class TErrorHandling(NIntEnum):
    doNothing = 0
    doAbort = auto()
    doRaise = auto()

def logMsg(s: string) -> None:
    with var:
        f = File()
    if open(f, string(getHomeDir()) / string("nimsuggest.log"), FileMode.fmAppend):
        writeLine(f, s)
        close(f)

def quitConf(conf: ConfigRef, msg: TMsgKind) -> None:
    if isDefined(conf, string("nimDebug")):
        quitOrRaise(conf, string(str(msg)))
    elif defined("debug") or msg == TMsgKind.errInternal or hasHint(conf, TMsgKind.hintStackTrace):
        if conf.writelnHook is None:
            # mock writeStackTrace
            pass
        else:
            styledMsgWriteln(conf, string("No stack traceback available\n"))
    quit(1)


def handleError(conf: ConfigRef, msg: TMsgKind, eh: TErrorHandling, s: string, ignoreMsg: bool) -> None:
    if msg in fatalMsgs:
        if conf.cmd == Command.cmdIdeTools:
            logMsg(s)
        if conf.cmd != Command.cmdIdeTools or msg != TMsgKind.errFatal:
            quitConf(conf, msg)
    if (msg >= errMin and msg <= errMax) or (msg >= warnMin and msg <= hintMax and msg in conf.warningAsErrors and not ignoreMsg):
        conf.errorCounter += 1
        conf.exitcode = 1
        if conf.errorCounter >= conf.errorMax:
            if conf.ideCmd == IdeCmd.ideNone:
                if comptime(defined("nimsuggest")):
                    raiseRecoverableError(s)
                else:
                    quitConf(conf, msg)
        elif eh == TErrorHandling.doAbort and conf.cmd != Command.cmdIdeTools:
            quitConf(conf, msg)
        elif eh == TErrorHandling.doRaise:
            raiseRecoverableError(s)

def eqTLineInfo(a: TLineInfo, b: TLineInfo) -> bool:
    return a.line == b.line and a.fileIndex == b.fileIndex

def exactEquals(a: TLineInfo, b: TLineInfo) -> bool:
    return a.fileIndex == b.fileIndex and a.line == b.line and a.col == b.col

def writeContext(conf: ConfigRef, lastinfo: TLineInfo) -> None:
    with let:
        instantiationFrom = string("template/generic instantiation from here")
        instantiationOfFrom = string("template/generic instantiation of `$1` from here")
    with var:
        info = lastinfo
    for i in range(len(conf.m.msgContext)):
        with let:
            context = conf.m.msgContext[i]
        if not eqTLineInfo(context.info, lastinfo) and not eqTLineInfo(context.info, info):
            if conf.structuredErrorHook is not None:
                # mock
                pass
            else:
                with let:
                    message = instantiationFrom if context.detail == string("") else instantiationOfFrom.replace(string("$1"), context.detail)
                styledMsgWriteln(conf, toFileLineCol(conf, context.info) + string(" ") + message)
        info = context.info

def ignoreMsgBecauseOfIdeTools(conf: ConfigRef, msg: TMsgKind) -> bool:
    return msg >= TMsgKind.errGenerated and conf.cmd == Command.cmdIdeTools and TGlobalOption.optIdeDebug not in conf.globalOptions


def addSourceLine(conf: ConfigRef, fileIdx: FileIndex, line: string) -> None:
    conf.m.fileInfos[nint(fileIdx)].lines.add(line)

def numLines(conf: ConfigRef, fileIdx: FileIndex) -> nint:
    with var:
        res = len(conf.m.fileInfos[nint(fileIdx)].lines)
    if res == 0:
        try:
            for line in lines(string(toFullPathConsiderDirty(conf, fileIdx))):
                addSourceLine(conf, fileIdx, line)
        except IOError:
            pass
        res = len(conf.m.fileInfos[nint(fileIdx)].lines)
    return res

def sourceLine(conf: ConfigRef, i: TLineInfo) -> string:
    if nint(i.fileIndex) < 0: return string("")
    with let:
        num = numLines(conf, i.fileIndex)
    if nint(i.line) > num: return string("")
    return conf.m.fileInfos[nint(i.fileIndex)].lines[nint(i.line) - 1]

def getSurroundingSrc(conf: ConfigRef, info: TLineInfo) -> string:
    if hasHint(conf, TMsgKind.hintSource) and not eqTLineInfo(info, unknownLineInfo):
        with let:
            indent = string("  ")
        with var:
            res = string("\n") + indent + sourceLine(conf, info)
        if info.col >= 0:
            res.add(string("\n") + indent + spaces(info.col) + string("^"))
        return res
    else:
        return string("")

def formatMsg(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string) -> string:
    with let:
        title = WarningTitle if (msg >= warnMin and msg <= warnMax) else (HintTitle if (msg >= hintMin and msg <= hintMax) else ErrorTitle)
    return toFileLineCol(conf, info) + string(" ") + title + getMessageStr(msg, arg)

def liMessage(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string, eh: TErrorHandling, info2: InstantiationInfo, isRaw: bool = False, ignoreError: bool = False) -> None:
    with var:
        ignoreMsg = False
        errorOutputsOld = conf.m.errorOutputs.copy()
        kind = string(str(msg)) if (msg >= warnMin and msg <= hintMax and msg != TMsgKind.hintUserRaw) else string("")
        title = string("")
    if msg in fatalMsgs:
        conf.m.errorOutputs = Tset[TErrorOutput]({TErrorOutput.eStdOut, TErrorOutput.eStdErr})

    if msg >= errMin and msg <= errMax:
        writeContext(conf, info)
        title = ErrorTitle
        if not eqTLineInfo(info, unknownLineInfo):
            conf.m.lastError = info
    elif msg >= warnMin and msg <= warnMax:
        ignoreMsg = not hasWarn(conf, msg)
        if not ignoreMsg and msg in conf.warningAsErrors:
            title = ErrorTitle
        else:
            title = WarningTitle
        if not ignoreMsg: writeContext(conf, info)
        conf.warnCounter += 1
    elif msg >= hintMin and msg <= hintMax:
        ignoreMsg = not hasHint(conf, msg)
        if not ignoreMsg and msg in conf.warningAsErrors:
            title = ErrorTitle
        else:
            title = HintTitle
        conf.hintCounter += 1
    else:
        title = string("")

    with let:
        s = arg if isRaw else getMessageStr(msg, arg)
    if not ignoreMsg:
        with let:
            loc = toFileLineCol(conf, info) + string(" ") if not eqTLineInfo(info, unknownLineInfo) else string("")
            kindmsg = KindFormat.replace(string("$1"), kind) if len(kind) > 0 else string("")
        if conf.structuredErrorHook is not None:
            pass # mock
        if not ignoreMsgBecauseOfIdeTools(conf, msg):
            if msg == TMsgKind.hintProcessing and conf.hintProcessingDots:
                msgWrite(conf, string("."))
            else:
                styledMsgWriteln(conf, loc + title + s + kindmsg + getSurroundingSrc(conf, info) + conf.unitSep)
                if TMsgKind.hintMsgOrigin in conf.mainPackageNotes:
                    styledMsgWriteln(conf, toFileLineColInst(info2) + string(" compiler msg initiated here") + KindFormat.replace(string("$1"), string(str(TMsgKind.hintMsgOrigin))) + conf.unitSep)
    if not ignoreError:
        handleError(conf, msg, eh, s, ignoreMsg)
    if msg in fatalMsgs:
        conf.m.errorOutputs = errorOutputsOld

@dispatch
def rawMessage(conf: ConfigRef, msg: TMsgKind, args: openArray[string]) -> None:
    with var:
        arg = msgKindToString(msg)
    if len(args) % 2 == 0:
        for i in range(0, len(args), 2):
            with let:
                key = str(args[i])
                val = args[i + 1]
            arg = arg.replace(string("$" + key), val)
    else:
        for i in range(len(args)):
            arg = arg.replace(string("$") + str(i + 1), args[i])
    liMessage(conf, unknownLineInfo, msg, arg, TErrorHandling.doAbort, instLoc(), True)

@dispatch
def rawMessage(conf: ConfigRef, msg: TMsgKind, arg: string) -> None:
    liMessage(conf, unknownLineInfo, msg, arg, TErrorHandling.doAbort, instLoc())

def fatal(conf: ConfigRef, info: TLineInfo, arg: string = string(""), msg: TMsgKind = TMsgKind.errFatal) -> None:
    liMessage(conf, info, msg, arg, TErrorHandling.doAbort, instLoc())

def globalError(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")) -> None:
    liMessage(conf, info, msg, arg, TErrorHandling.doRaise, instLoc())

def globalErrorStr(conf: ConfigRef, info: TLineInfo, arg: string) -> None:
    liMessage(conf, info, TMsgKind.errGenerated, arg, TErrorHandling.doRaise, instLoc())

def localError(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")) -> None:
    liMessage(conf, info, msg, arg, TErrorHandling.doNothing, instLoc())

def localErrorStr(conf: ConfigRef, info: TLineInfo, arg: string) -> None:
    liMessage(conf, info, TMsgKind.errGenerated, arg, TErrorHandling.doNothing, instLoc())

def message(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")) -> None:
    liMessage(conf, info, msg, arg, TErrorHandling.doNothing, instLoc())

def warningDeprecated(conf: ConfigRef, info: TLineInfo = gCmdLineInfo, msg: string = string("")) -> None:
    message(conf, info, TMsgKind.warnDeprecated, msg)

def internalErrorImpl(conf: ConfigRef, info: TLineInfo, errMsg: string, info2: InstantiationInfo) -> None:
    if conf.cmd in {Command.cmdIdeTools, Command.cmdCheck} and conf.structuredErrorHook is None: return
    writeContext(conf, info)
    liMessage(conf, info, TMsgKind.errInternal, errMsg, TErrorHandling.doAbort, info2)

def internalError(conf: ConfigRef, info: TLineInfo, errMsg: string) -> None:
    internalErrorImpl(conf, info, errMsg, instLoc())

def internalErrorStr(conf: ConfigRef, errMsg: string) -> None:
    internalErrorImpl(conf, unknownLineInfo, errMsg, instLoc())

def internalAssert(conf: ConfigRef, e: bool) -> None:
    if not e:
        with let:
            info2 = instLoc()
            arg = toFileLineColInst(info2)
        internalErrorImpl(conf, unknownLineInfo, arg, info2)

def lintReport(conf: ConfigRef, info: TLineInfo, beau: string, got: string, extraMsg: string = string("")) -> None:
    with let:
        m = string("'$1' should be: '$2'$3").replace(string("$1"), got).replace(string("$2"), beau).replace(string("$3"), extraMsg)
        msg = TMsgKind.errGenerated if TGlobalOption.optStyleError in conf.globalOptions else (TMsgKind.warnUser if TGlobalOption.optStyleWarning in conf.globalOptions else TMsgKind.hintName)
    liMessage(conf, info, msg, m, TErrorHandling.doNothing, instLoc())

def quotedFilenameFI(conf: ConfigRef, fi: FileIndex) -> Rope:
    if nint(fi) < 0:
        return makeCString(string("???"))
    elif TGlobalOption.optExcessiveStackTrace in conf.globalOptions:
        return conf.m.fileInfos[nint(fi)].quotedFullName
    else:
        return conf.m.fileInfos[nint(fi)].quotedName

def quotedFilename(conf: ConfigRef, i: TLineInfo) -> Rope:
    return quotedFilenameFI(conf, i.fileIndex)

def listWarnings(conf: ConfigRef) -> None:
    msgWriteln(conf, string("Warnings:"), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))
    for a in inrange(warnMin, warnMax):
        with let:
            x = string("x") if a in conf.notes else string(" ")
        msgWriteln(conf, string("  [$1] $2").replace(string("$1"), x).replace(string("$2"), string(str(a))), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))

def listHints(conf: ConfigRef) -> None:
    msgWriteln(conf, string("Hints:"), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))
    for a in inrange(hintMin, hintMax):
        with let:
            x = string("x") if a in conf.notes else string(" ")
        msgWriteln(conf, string("  [$1] $2").replace(string("$1"), x).replace(string("$2"), string(str(a))), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))

def genSuccessX(conf: ConfigRef) -> None:
    with let:
        mem = string("0 peakmem")
        loc = string(str(conf.linesCompiled))
        build = string("")
        sec = string("0.000")
        project = string(conf.projectFull) if conf.filenameOption == FilenameOption.foAbs else conf.projectName
    with var:
        output = string("unknownOutput")
    if not isEmpty(conf.outFile):
        output = string(absOutFile(conf))
    if conf.filenameOption != FilenameOption.foAbs:
        output = extractFilename(output)
    rawMessage(conf, TMsgKind.hintSuccessX, [
        string("build"), build,
        string("loc"), loc,
        string("sec"), sec,
        string("mem"), mem,
        string("project"), project,
        string("output"), output,
    ])

if comptime(__name__ == '__main__'):
    def test_msgs():
        echo("Running msgs.py tests...")

        with var:
            # 1. ConfigRef initialization
            conf = newConfigRef()
            captured = seq[string]()

        assert len(conf.m.errorOutputs) > 0
        conf.projectPath = AbsoluteDir(string("/path/to"))

        # 2. File info creation and indexing
        with let:
            abs_file = AbsoluteFile(string("/path/to/mock.nim"))
            rel_file = RelativeFile(string("mock.nim"))
            fi = newFileInfo(abs_file, rel_file)
        assert string(fi.shortName) == string("mock.nim")
        assert fi.kind == FileInfoKind.fikSource

        with let:
            idx = fileInfoIdx(conf, abs_file)
        assert nint(idx) == 0
        assert fileInfoKnown(conf, abs_file)
        assert fileInfoKind(conf, idx) == FileInfoKind.fikSource

        # 3. Line info creation & formatting
        with let:
            li = newLineInfo(idx, 10, 5)
        assert nint(li.line) == 10
        assert nint(li.col) == 5
        assert toLinenumber(li) == 10
        assert toColumn(li) == 5

        with let:
            flc = toFileLineCol(conf, li)
        assert string("mock.nim(10, 6)") in string(flc)
        assert lineInfoToStr(conf, li) == flc

        # 4. Context push/pop
        assert getInfoContextLen(conf) == 0
        pushInfoContext(conf, li, string("in template foo"))
        assert getInfoContextLen(conf) == 1
        with let:
            ctx = getInfoContext(conf, 0)
        assert eqTLineInfo(ctx, li)
        popInfoContext(conf)
        assert getInfoContextLen(conf) == 0

        # 5. toOctal, toCChar, makeCString
        assert toOctal(ch('\n')) == string("012")
        with let:
            c_rope = makeCString(string("hello\nworld\""))
        assert string(c_rope) == string('"hello\\012world\\""')

        # 6. Message strings & formatting
        assert msgKindToString(TMsgKind.errGenerated) == string("$1")
        with let:
            msgStr = getMessageStr(TMsgKind.errGenerated, string("foo"))
        assert msgStr == string("foo")
        with let:
            fmsg = formatMsg(conf, li, TMsgKind.errGenerated, string("test error"))
        assert string("Error: test error") in string(fmsg)

        # 7. MsgFlag and MsgFlags
        with let:
            flags = MsgFlags({MsgFlag.msgStdout, MsgFlag.msgNoUnitSep})
        assert MsgFlag.msgStdout in flags
        assert MsgFlag.msgNoUnitSep in flags

        # 8. Path queries
        assert string(toFullPath(conf, idx)) == string("/path/to/mock.nim")
        assert string(toFilename(conf, idx)) == string("mock.nim")

        # 9. Message capture with writelnHook
        def testHook(s: string):
            captured.add(s)
        conf.writelnHook = testHook

        msgWriteln(conf, string("test log line"))
        assert len(captured) == 1
        assert string("test log line") in captured[0]

        def hasLine(cap: seq[string], s: string) -> bool:
            for line in cap:
                if s in line:
                    return True
            return False

        # 10. Warnings and Hints listing
        listWarnings(conf)
        assert hasLine(captured, string("Warnings:"))
        listHints(conf)
        assert hasLine(captured, string("Hints:"))

        # 11. genSuccessX output
        genSuccessX(conf)
        assert hasLine(captured, string("[SuccessX]"))

        echo("msgs.py extensive tests passed!")

    test_msgs()

