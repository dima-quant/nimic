from __future__ import annotations
import sys
import os
from datetime import datetime

from nimic.ntypes import *
from nimic.std.strutils import *

from lineinfos import *
from pathutils import *
from options import *
from ropes import *


class InstantiationInfo(NTuple):
    filename: string
    line: int
    column: int

def instLoc() -> InstantiationInfo:
    return InstantiationInfo(string(""), 0, 0) # Mock instLoc


def toStdOrrKind(stdOrr) -> StdOrrKind:
    if stdOrr == sys.stdout: return StdOrrKind.stdOrrStdout
    else: return StdOrrKind.stdOrrStderr

# toLowerAscii is already defined in nimic.std.strutils

def flushDot(conf: ConfigRef) -> None:
    stdOrr = sys.stdout if TGlobalOption.optStdout in conf.globalOptions else sys.stderr
    stdOrrKind = toStdOrrKind(stdOrr)
    if stdOrrKind in conf.lastMsgWasDot:
        conf.lastMsgWasDot.discard(stdOrrKind)
        stdOrr.write("\n")

def toCChar(c: char, result: string) -> None:
    # mock
    result += c

def makeCString(s: string) -> Rope:
    result = string("\"")
    for i in range(len(s)):
        toCChar(s[i], result)
    result += string("\"")
    return rope(result)

def newFileInfo(fullPath: AbsoluteFile, projPath: RelativeFile, kind: FileInfoKind = FileInfoKind.fikSource) -> TFileInfo:
    result = TFileInfo(
        fullPath=fullPath,
        projPath=projPath,
        shortName=extractFilename(string(fullPath)),
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
    def fileSection(conf: ConfigRef, fid: FileIndex, a: int, b: int) -> string:
        return substr(conf.m.fileInfos[int(fid)].fullContent, a, b)

def canonicalCase(path: string) -> None:
    if not comptime(defined("FileSystemCaseSensitive")):
        toLowerAscii(path)

def fileInfoKnown(conf: ConfigRef, filename: AbsoluteFile) -> bool:
    try:
        canon = canonicalizePath(conf, filename)
    except OSError:
        canon = filename
    c_str = string(canon)
    canonicalCase(c_str)
    return hasattr(conf.m.filenameToIndexTbl, "hasKey") and conf.m.filenameToIndexTbl.hasKey(c_str)

def fileInfoIdx(conf: ConfigRef, filename: AbsoluteFile, isKnownFile: list[bool] = None) -> FileIndex:
    pseudoPath = False
    try:
        canon = canonicalizePath(conf, filename)
    except OSError:
        canon = filename
        pseudoPath = True

    canon2 = string(canon)
    canonicalCase(canon2)

    if hasattr(conf.m.filenameToIndexTbl, "hasKey") and conf.m.filenameToIndexTbl.hasKey(canon2):
        if isKnownFile is not None: isKnownFile[0] = True
        return conf.m.filenameToIndexTbl[canon2]
    else:
        if isKnownFile is not None: isKnownFile[0] = False
        res = FileIndex(len(conf.m.fileInfos))
        projPath = RelativeFile(string(filename)) if pseudoPath else relativeTo(canon, conf.projectPath)
        conf.m.fileInfos.add(newFileInfo(canon, projPath))
        conf.m.filenameToIndexTbl[canon2] = res
        return res

def fileInfoIdx2(conf: ConfigRef, filename: AbsoluteFile) -> FileIndex:
    return fileInfoIdx(conf, filename)

def fileInfoIdxRel(conf: ConfigRef, filename: RelativeFile, isKnownFile: list[bool] = None) -> FileIndex:
    return fileInfoIdx(conf, AbsoluteFile(expandFilename(string(filename))), isKnownFile)

def fileInfoIdxRel2(conf: ConfigRef, filename: RelativeFile) -> FileIndex:
    return fileInfoIdxRel(conf, filename)

def registerNifSuffix(conf: ConfigRef, suffix: string, isKnownFile: list[bool]) -> FileIndex:
    res = conf.m.filenameToIndexTbl.getOrDefault(suffix, InvalidFileIdx)
    if res == InvalidFileIdx:
        isKnownFile[0] = False
        res = FileIndex(len(conf.m.fileInfos))
        conf.m.fileInfos.add(newFileInfo(AbsoluteFile(suffix), RelativeFile(suffix), FileInfoKind.fikNifModule))
        conf.m.filenameToIndexTbl[suffix] = res
    else:
        isKnownFile[0] = True
    return res

def fileInfoKind(conf: ConfigRef, fileIdx: FileIndex) -> FileInfoKind:
    if int(fileIdx) >= 0 and int(fileIdx) < len(conf.m.fileInfos):
        return conf.m.fileInfos[int(fileIdx)].kind
    else:
        return FileInfoKind.fikSource

def newLineInfo(fileInfoIdx: FileIndex, line: int, col: int) -> TLineInfo:
    result = TLineInfo()
    result.fileIndex = fileInfoIdx
    if line < 65535:
        result.line = line
    else:
        result.line = 65535
    if col < 32767:
        result.col = col
    else:
        result.col = -1
    return result

def newLineInfoConf(conf: ConfigRef, filename: AbsoluteFile, line: int, col: int) -> TLineInfo:
    return newLineInfo(fileInfoIdx2(conf, filename), line, col)

gCmdLineInfo = newLineInfo(commandLineIdx, 1, 1)

def concat(strings: seq[string]) -> string:
    res = string("")
    for s in strings:
        res += s
    return res

def suggestWriteln(conf: ConfigRef, s: string) -> None:
    if TErrorOutput.eStdOut in conf.m.errorOutputs:
        if conf.writelnHook is None:
            sys.stdout.write(str(s) + "\n")
            sys.stdout.flush()
        else:
            conf.writelnHook(s)

def msgQuit(x: int) -> None:
    sys.exit(x)

def msgQuitStr(x: string) -> None:
    sys.exit(str(x))

def suggestQuit() -> None:
    raise Exception("suggest done")

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

def getInfoContextLen(conf: ConfigRef) -> int:
    return len(conf.m.msgContext)

def setInfoContextLen(conf: ConfigRef, L: int) -> None:
    conf.m.msgContext.setLen(L)

def pushInfoContext(conf: ConfigRef, info: TLineInfo, detail: string = string("")) -> None:
    tup = InstantiationInfo(info, detail) # Wait, TLineInfo and detail as a tuple. Nim: (info, detail)
    conf.m.msgContext.add(tup)

def popInfoContext(conf: ConfigRef) -> None:
    conf.m.msgContext.setLen(len(conf.m.msgContext) - 1)

def getInfoContext(conf: ConfigRef, index: int) -> TLineInfo:
    i = len(conf.m.msgContext) + index if index < 0 else index
    if i >= len(conf.m.msgContext):
        return unknownLineInfo
    else:
        return conf.m.msgContext[i].info

def toFilename(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if int(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return conf.m.fileInfos[int(fileIdx)].shortName

def toProjPath(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if int(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return string(conf.m.fileInfos[int(fileIdx)].projPath)

def toFullPath(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if int(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return string(conf.m.fileInfos[int(fileIdx)].fullPath)

def setDirtyFile(conf: ConfigRef, fileIdx: FileIndex, filename: AbsoluteFile) -> None:
    assert int(fileIdx) >= 0
    conf.m.fileInfos[int(fileIdx)].dirtyFile = filename
    conf.m.fileInfos[int(fileIdx)].lines.setLen(0)

def setHash(conf: ConfigRef, fileIdx: FileIndex, hash: string) -> None:
    assert int(fileIdx) >= 0
    conf.m.fileInfos[int(fileIdx)].hash = hash

def getHash(conf: ConfigRef, fileIdx: FileIndex) -> string:
    assert int(fileIdx) >= 0
    return conf.m.fileInfos[int(fileIdx)].hash


def toFullPathConsiderDirty(conf: ConfigRef, fileIdx: FileIndex) -> AbsoluteFile:
    if int(fileIdx) < 0:
        return AbsoluteFile(commandLineDesc if fileIdx == commandLineIdx else string("???"))
    elif not isEmpty(conf.m.fileInfos[int(fileIdx)].dirtyFile):
        return conf.m.fileInfos[int(fileIdx)].dirtyFile
    else:
        return conf.m.fileInfos[int(fileIdx)].fullPath

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
        absPath = toFullPath(conf, fileIdx)
        return canonicalImportAux(conf, AbsoluteFile(absPath))
    elif opt == FilenameOption.foName:
        return extractFilename(toProjPath(conf, fileIdx))
    elif opt == FilenameOption.foLegacyRelProj:
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

def toLinenumber(info: TLineInfo) -> int:
    return int(info.line)

def toColumn(info: TLineInfo) -> int:
    return int(info.col)

def toLocation(res: string, filename: string, line: int, col: int) -> string:
    # mock nim's toLocation
    if line > 0:
        return res + filename + string("(") + string(str(line)) + string(", ") + string(str(col)) + string(")")
    return res + filename

def toFileLineColInst(info: InstantiationInfo) -> string:
    return toLocation(string(""), info.filename, info.line, info.column + ColOffset)

def toFileLineCol(conf: ConfigRef, info: TLineInfo) -> string:
    return toLocation(string(""), toMsgFilenameInfo(conf, info), int(info.line), int(info.col) + ColOffset)

def lineInfoToStr(conf: ConfigRef, info: TLineInfo) -> string:
    return toFileLineCol(conf, info)

class MsgFlag(NIntEnum):
    msgStdout = 0
    msgSkipHook = auto()
    msgNoUnitSep = auto()

def msgWriteln(conf: ConfigRef, s: string, flags: Tset[MsgFlag] = Tset[MsgFlag]()) -> None:
    sep = conf.unitSep if MsgFlag.msgNoUnitSep not in flags else string("")
    if conf.writelnHook is not None and MsgFlag.msgSkipHook not in flags:
        conf.writelnHook(s + sep)
    elif TGlobalOption.optStdout in conf.globalOptions or MsgFlag.msgStdout in flags:
        if TErrorOutput.eStdOut in conf.m.errorOutputs:
            flushDot(conf)
            sys.stdout.write(str(s))
            sys.stdout.write(str(sep) + "\n")
            sys.stdout.flush()
    else:
        if TErrorOutput.eStdErr in conf.m.errorOutputs:
            flushDot(conf)
            sys.stderr.write(str(s))
            sys.stderr.write(str(sep) + "\n")
            if comptime(defined("windows")):
                sys.stderr.flush()

def msgWrite(conf: ConfigRef, s: string) -> None:
    if len(conf.m.errorOutputs) > 0:
        stdOrr = sys.stdout if TGlobalOption.optStdout in conf.globalOptions else sys.stderr
        stdOrr.write(str(s))
        stdOrr.flush()
        conf.lastMsgWasDot.add(toStdOrrKind(stdOrr))

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
    logPath = string(getHomeDir()) / string("nimsuggest.log")
    with open(str(logPath), "a") as f:
        f.write(str(s) + "\n")

class RecoverableError(Exception):
    pass

def raiseRecoverableError(s: string) -> None:
    raise RecoverableError(str(s))

def quitConf(conf: ConfigRef, msg: TMsgKind) -> None:
    if isDefined(conf, string("nimDebug")):
        quitOrRaise(conf, string(str(msg)))
    elif comptime(defined("debug")) or msg == TMsgKind.errInternal or hasHint(conf, TMsgKind.hintStackTrace):
        if conf.writelnHook is None:
            # mock writeStackTrace
            pass
        else:
            styledMsgWriteln(conf, string("No stack traceback available\n"))
    sys.exit(1)

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
    instantiationFrom = string("template/generic instantiation from here")
    instantiationOfFrom = string("template/generic instantiation of `$1` from here")
    info = lastinfo
    for i in range(len(conf.m.msgContext)):
        context = conf.m.msgContext[i]
        if not eqTLineInfo(context.info, lastinfo) and not eqTLineInfo(context.info, info):
            if conf.structuredErrorHook is not None:
                # mock
                pass
            else:
                message = instantiationFrom if isEmpty(context.detail) else instantiationOfFrom.replace(string("$1"), context.detail)
                styledMsgWriteln(conf, toFileLineCol(conf, context.info) + string(" ") + message)
        info = context.info

def ignoreMsgBecauseOfIdeTools(conf: ConfigRef, msg: TMsgKind) -> bool:
    return msg >= errGenerated and conf.cmd == Command.cmdIdeTools and TGlobalOption.optIdeDebug not in conf.globalOptions

def addSourceLine(conf: ConfigRef, fileIdx: FileIndex, line: string) -> None:
    conf.m.fileInfos[int(fileIdx)].lines.add(line)

def numLines(conf: ConfigRef, fileIdx: FileIndex) -> int:
    res = len(conf.m.fileInfos[int(fileIdx)].lines)
    if res == 0:
        try:
            with open(str(toFullPathConsiderDirty(conf, fileIdx)), 'r') as f:
                for line in f:
                    addSourceLine(conf, fileIdx, string(line.rstrip('\n')))
        except IOError:
            pass
        res = len(conf.m.fileInfos[int(fileIdx)].lines)
    return res

def sourceLine(conf: ConfigRef, i: TLineInfo) -> string:
    if int(i.fileIndex) < 0: return string("")
    num = numLines(conf, i.fileIndex)
    if int(i.line) > num: return string("")
    return conf.m.fileInfos[int(i.fileIndex)].lines[int(i.line) - 1]

def getSurroundingSrc(conf: ConfigRef, info: TLineInfo) -> string:
    if hasHint(conf, TMsgKind.hintSource) and not eqTLineInfo(info, unknownLineInfo):
        indent = string("  ")
        res = string("\n") + indent + sourceLine(conf, info)
        if info.col >= 0:
            res += string("\n") + indent + string(" " * info.col) + string("^")
        return res
    else:
        return string("")

def formatMsg(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string) -> string:
    if msg >= warnMin and msg <= warnMax:
        title = WarningTitle
    elif msg >= hintMin and msg <= hintMax:
        title = HintTitle
    else:
        title = ErrorTitle
    return toFileLineCol(conf, info) + string(" ") + title + getMessageStr(msg, arg)

def liMessage(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string, eh: TErrorHandling, info2: InstantiationInfo, isRaw: bool = False, ignoreError: bool = False) -> None:
    ignoreMsg = False
    errorOutputsOld = conf.m.errorOutputs.copy()
    if msg in fatalMsgs:
        conf.m.errorOutputs = Tset[TErrorOutput]({TErrorOutput.eStdOut, TErrorOutput.eStdErr})
    
    kind = string(str(msg)) if (msg >= warnMin and msg <= hintMax and msg != TMsgKind.hintUserRaw) else string("")
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

    s = arg if isRaw else getMessageStr(msg, arg)
    if not ignoreMsg:
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

def rawMessageArgs(conf: ConfigRef, msg: TMsgKind, args: seq[string]) -> None:
    arg = msgKindToString(msg)
    # mock replacement of multiple args
    liMessage(conf, unknownLineInfo, msg, arg, TErrorHandling.doAbort, instLoc(), True)

def rawMessage(conf: ConfigRef, msg: TMsgKind, arg: string) -> None:
    liMessage(conf, unknownLineInfo, msg, arg, TErrorHandling.doAbort, instLoc())

def fatal(conf: ConfigRef, info: TLineInfo, arg: string = string(""), msg: TMsgKind = TMsgKind.errFatal) -> None:
    liMessage(conf, info, msg, arg, TErrorHandling.doAbort, instLoc())

def globalError(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")) -> None:
    liMessage(conf, info, msg, arg, TErrorHandling.doRaise, instLoc())

def globalErrorStr(conf: ConfigRef, info: TLineInfo, arg: string) -> None:
    liMessage(conf, info, errGenerated, arg, TErrorHandling.doRaise, instLoc())

def localError(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")) -> None:
    liMessage(conf, info, msg, arg, TErrorHandling.doNothing, instLoc())

def localErrorStr(conf: ConfigRef, info: TLineInfo, arg: string) -> None:
    liMessage(conf, info, errGenerated, arg, TErrorHandling.doNothing, instLoc())

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
        info2 = instLoc()
        arg = toFileLineColInst(info2)
        internalErrorImpl(conf, unknownLineInfo, arg, info2)

def lintReport(conf: ConfigRef, info: TLineInfo, beau: string, got: string, extraMsg: string = string("")) -> None:
    m = string("'$1' should be: '$2'$3").replace(string("$1"), got).replace(string("$2"), beau).replace(string("$3"), extraMsg)
    msg = errGenerated if TGlobalOption.optStyleError in conf.globalOptions else (TMsgKind.warnUser if TGlobalOption.optStyleWarning in conf.globalOptions else TMsgKind.hintName)
    liMessage(conf, info, msg, m, TErrorHandling.doNothing, instLoc())

def quotedFilenameFI(conf: ConfigRef, fi: FileIndex) -> Rope:
    if int(fi) < 0:
        return makeCString(string("???"))
    elif TGlobalOption.optExcessiveStackTrace in conf.globalOptions:
        return conf.m.fileInfos[int(fi)].quotedFullName
    else:
        return conf.m.fileInfos[int(fi)].quotedName

def quotedFilename(conf: ConfigRef, i: TLineInfo) -> Rope:
    return quotedFilenameFI(conf, i.fileIndex)

def listWarnings(conf: ConfigRef) -> None:
    msgWriteln(conf, string("Warnings:"), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))
    for a in inrange(warnMin, warnMax):
        x = string("x") if a in conf.notes else string(" ")
        msgWriteln(conf, string("  [$1] $2").replace(string("$1"), x).replace(string("$2"), string(str(a))), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))

def listHints(conf: ConfigRef) -> None:
    msgWriteln(conf, string("Hints:"), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))
    for a in inrange(hintMin, hintMax):
        x = string("x") if a in conf.notes else string(" ")
        msgWriteln(conf, string("  [$1] $2").replace(string("$1"), x).replace(string("$2"), string(str(a))), Tset[MsgFlag]({MsgFlag.msgNoUnitSep}))

def genSuccessX(conf: ConfigRef) -> None:
    # minimal mock for genSuccessX
    pass

if comptime(__name__ == '__main__'):
    print("Running msgs.py tests...")
    
    # Setup mock conf
    conf = ConfigRef()
    conf.globalOptions = Tset[TGlobalOption]()
    conf.m = MsgConfig()
    conf.m.errorOutputs = Tset[TErrorOutput]({TErrorOutput.eStdOut, TErrorOutput.eStdErr})
    conf.m.fileInfos = seq[TFileInfo]()
    conf.m.filenameToIndexTbl = Table[string, FileIndex]()
    conf.m.msgContext = seq[InstantiationInfo]()
    conf.projectPath = AbsoluteDir(string("/path/to"))
    
    # Test file info creation
    abs_file = AbsoluteFile(string("/path/to/mock.nim"))
    rel_file = RelativeFile(string("mock.nim"))
    fi = newFileInfo(abs_file, rel_file)
    assert string(fi.shortName) == string("mock.nim")
    
    # Test line info creation
    idx = fileInfoIdx(conf, abs_file)
    assert int(idx) == 0
    li = newLineInfo(idx, 10, 5)
    assert int(li.line) == 10
    
    # Test message strings
    assert msgKindToString(TMsgKind.errGenerated) == string("$1")
    msgStr = getMessageStr(TMsgKind.errGenerated, string("foo"))
    assert msgStr == string("foo")
    
    # Test MsgFlag
    flags = Tset[MsgFlag]({MsgFlag.msgStdout})
    assert MsgFlag.msgStdout in flags
    
    # Test getting full path
    path = toFullPath(conf, idx)
    assert string(path) == string("/path/to/mock.nim")
    
    print("msgs.py extensive tests passed!")
