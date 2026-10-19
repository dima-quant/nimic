# /// nimic

# ///
from __future__ import annotations
#
#
#           The Nim Compiler
#        (c) Copyright 2013 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

from nimic.ntypes import *
from nimic.std.strutils import *
from nimic.std.os import *
from nimic.std.tables import *
from nimic.std.terminal import *
from nimic.std.times import *
from nimic.std.private.miscdollars import *
from .options import *
from .lineinfos import *
from .pathutils import *
# TODO: requires nimic feature macros (G17): import std/macros

importExcept(".ropes", "%")

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.syncio import *
    from nimic.std.assertions import *


InstantiationInfo = typeof(instantiationInfo())


@template
def instLoc() -> InstantiationInfo:
    return instantiationInfo(-2, fullPaths=True)


@template
def _toStdOrrKind(stdOrr: untyped) -> untyped:
    return StdOrrKind.stdOrrStdout if stdOrr == stdout else StdOrrKind.stdOrrStderr


def _toLowerAscii(a: mut@string) -> None:
    """{.inline.}"""
    for c in mitems(a):
        if isUpperAscii(c):
            c <<= char(uint8(c) ^ uint8(0b0010_0000))


def flushDot(conf: ConfigRef) -> None:
    ## safe to call multiple times
    with let:
        stdOrr = stdout if TGlobalOption.optStdout in conf.globalOptions else stderr
        stdOrrKind = _toStdOrrKind(stdOrr)
    if stdOrrKind in conf.lastMsgWasDot:
        conf.lastMsgWasDot.excl(stdOrrKind)
        write(stdOrr, string("\n"))


def toCChar(c: char, result: mut@string) -> None:
    """{.inline.}"""
    match c:
        case _ if c in inrange(ch('\0'), ch('\x1F')) or c in inrange(ch('\x7F'), ch('\xFF')):
            result.add(ch('\\'))
            result.add(toOctal(c))
        case _ if c == ch('\'') or c == ch('"') or c == ch('\\') or c == ch('?'):
            result.add(ch('\\'))
            result.add(c)
        case _:
            result.add(c)


def makeCString(s: string) -> Rope:
    result = newStringOfCap(int(toFloat(s.len) * 1.1) + 1)
    result.add(string("\""))
    for i in range(s.len):
        # line wrapping of string literals in cgen'd code was a bad idea, e.g. causes: bug #16265
        # It also makes reading c sources or grepping harder, for zero benefit.
        # const MaxLineLength = 64
        # if (i + 1) mod MaxLineLength == 0:
        #   res.add("\"\L\"")
        toCChar(s[i], result)
    result.add(ch('\"'))
    return result


def _newFileInfo(fullPath: AbsoluteFile, projPath: RelativeFile, kind: FileInfoKind = FileInfoKind.fikSource) -> TFileInfo:
    result = TFileInfo(fullPath=fullPath, projPath=projPath,
                       shortName=fullPath.extractFilename(),
                       quotedFullName=makeCString(string(fullPath)),
                       lines=seq[string](),
                       kind=kind)
    result.quotedName = makeCString(result.shortName)
    if comptime(defined("nimpretty")):
        if not isEmpty(result.fullPath):
            try:
                result.fullContent = readFile(string(result.fullPath))
            except IOError:
                #rawMessage(errCannotOpenFile, result.fullPath)
                # XXX fixme
                result.fullContent = string("")
    return result


if comptime(defined("nimpretty")):
    def fileSection(conf: ConfigRef, fid: FileIndex, a: nint, b: nint) -> string:
        return substr(conf.m.fileInfos[int(fid)].fullContent, a, b)


def _canonicalCase(path: mut@string) -> None:
    """{.inline.}"""
    ## the idea is to only use this for checking whether a path is already in
    ## the table but otherwise keep the original case
    if comptime(FileSystemCaseSensitive):
        discard
    else:
        _toLowerAscii(path)


def fileInfoKnown(conf: ConfigRef, filename: AbsoluteFile) -> bool:
    with var:
        canon = AbsoluteFile()
    try:
        canon = conf.canonicalizePath(filename)
    except OSError:
        canon = filename
    _canonicalCase(string(canon))
    result = conf.m.filenameToIndexTbl.hasKey(string(canon))
    return result


@dispatch
def fileInfoIdx(conf: ConfigRef, filename: AbsoluteFile, isKnownFile: mut@bool) -> FileIndex:
    with var:
        canon = AbsoluteFile()
        pseudoPath = False

    try:
        canon = conf.canonicalizePath(filename)
    except OSError:
        canon = filename
        # The compiler uses "filenames" such as `command line` or `stdin`
        # This flag indicates that we are working with such a path here
        pseudoPath = True

    with var:
        canon2 = string(canon).copy()
    _canonicalCase(canon2)

    if conf.m.filenameToIndexTbl.hasKey(canon2):
        isKnownFile <<= True
        result = conf.m.filenameToIndexTbl[canon2]
    else:
        isKnownFile <<= False
        result = FileIndex(conf.m.fileInfos.len)
        conf.m.fileInfos.add(_newFileInfo(canon, RelativeFile(filename) if pseudoPath
                                          else relativeTo(canon, conf.projectPath)))
        conf.m.filenameToIndexTbl[canon2] = result
    return result


@dispatch
def fileInfoIdx(conf: ConfigRef, filename: AbsoluteFile) -> FileIndex:
    with var:
        dummy: bool = False
    result = fileInfoIdx(conf, filename, dummy)
    return result


@dispatch
def fileInfoIdx(conf: ConfigRef, filename: RelativeFile, isKnownFile: mut@bool) -> FileIndex:
    return fileInfoIdx(conf, AbsoluteFile(expandFilename(string(filename))), isKnownFile)


@dispatch
def fileInfoIdx(conf: ConfigRef, filename: RelativeFile) -> FileIndex:
    with var:
        dummy: bool = False
    return fileInfoIdx(conf, AbsoluteFile(expandFilename(string(filename))), dummy)


@dispatch
def registerNifSuffix(conf: ConfigRef, suffix: string, isKnownFile: mut@bool) -> FileIndex:
    result = conf.m.filenameToIndexTbl.getOrDefault(suffix, InvalidFileIdx)
    if result == InvalidFileIdx:
        isKnownFile <<= False
        result = FileIndex(conf.m.fileInfos.len)
        conf.m.fileInfos.add(_newFileInfo(AbsoluteFile(suffix), RelativeFile(suffix), FileInfoKind.fikNifModule))
        conf.m.filenameToIndexTbl[suffix] = result
    else:
        isKnownFile <<= True
    return result


def fileInfoKind(conf: ConfigRef, fileIdx: FileIndex) -> FileInfoKind:
    ## Returns the kind of a FileIndex (source file or NIF module suffix).
    if int(fileIdx) >= 0 and int(fileIdx) < conf.m.fileInfos.len:
        result = conf.m.fileInfos[int(fileIdx)].kind
    else:
        result = FileInfoKind.fikSource  # Default to source for unknown indices
    return result


@dispatch
def newLineInfo(fileInfoIdx: FileIndex, line: nint, col: nint) -> TLineInfo:
    result = TLineInfo(fileIndex=fileInfoIdx)
    if line < int(high(uint16)):
        result.line = uint16(line)
    else:
        result.line = high(uint16)
    if col < int(high(int16)):
        result.col = int16(col)
    else:
        result.col = -1
    return result


@dispatch
def newLineInfo(conf: ConfigRef, filename: AbsoluteFile, line: nint, col: nint) -> TLineInfo:
    """{.inline.}"""
    result = newLineInfo(fileInfoIdx(conf, filename), line, col)
    return result


with const:
    gCmdLineInfo = newLineInfo(commandLineIdx, 1, 1)


def _concat(strings: openArray[string]) -> string:
    with var:
        totalLen = 0
    for s in strings:
        totalLen += s.len
    result = newStringOfCap(totalLen)
    for s in strings:
        result.add(s)
    return result


def suggestWriteln(conf: ConfigRef, s: string) -> None:
    if TErrorOutput.eStdOut in conf.m.errorOutputs:
        if isNil(conf.writelnHook):
            writeLine(stdout, s)
            flushFile(stdout)
        else:
            conf.writelnHook(s)


@dispatch
def msgQuit(x: int8) -> None:
    quit(x)


@dispatch
def msgQuit(x: string) -> None:
    quit(x)


def suggestQuit() -> None:
    raise newException(ESuggestDone, string("suggest done"))


# this format is understood by many text editors: it is the same that
# Borland and Freepascal use
with const:
    _KindFormat = string(" [$1]")
    _KindColor = ForegroundColor.fgCyan
    _ErrorTitle = string("Error: ")
    _ErrorColor = ForegroundColor.fgRed
    _WarningTitle = string("Warning: ")
    _WarningColor = ForegroundColor.fgYellow
    _HintTitle = string("Hint: ")
    _HintColor = ForegroundColor.fgGreen
    # NOTE: currently line info line numbers start with 1,
    # but column numbers start with 0, however most editors expect
    # first column to be 1, so we need to +1 here
    ColOffset = 1
    commandLineDesc = string("command line")


def getInfoContextLen(conf: ConfigRef) -> nint:
    return conf.m.msgContext.len


def setInfoContextLen(conf: ConfigRef, L: nint) -> None:
    setLen(conf.m.msgContext, L)


def pushInfoContext(conf: ConfigRef, info: TLineInfo, detail: string = string("")) -> None:
    conf.m.msgContext.add((info, detail))


def popInfoContext(conf: ConfigRef) -> None:
    setLen(conf.m.msgContext, conf.m.msgContext.len - 1)


def getInfoContext(conf: ConfigRef, index: nint) -> TLineInfo:
    with let:
        i = conf.m.msgContext.len + index if index < 0 else index
    if ge_percent(i, conf.m.msgContext.len):
        result = unknownLineInfo
    else:
        result = conf.m.msgContext[i].info
    return result


@template
def toFilename(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if int32(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return conf.m.fileInfos[int32(fileIdx)].shortName


@dispatch
def toProjPath(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if int32(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        return string(conf.m.fileInfos[int32(fileIdx)].projPath)


@dispatch
def toFullPath(conf: ConfigRef, fileIdx: FileIndex) -> string:
    if int32(fileIdx) < 0 or conf is None:
        result = commandLineDesc if fileIdx == commandLineIdx else string("???")
    else:
        result = string(conf.m.fileInfos[int32(fileIdx)].fullPath)
    return result


def setDirtyFile(conf: ConfigRef, fileIdx: FileIndex, filename: AbsoluteFile) -> None:
    assert int32(fileIdx) >= 0
    conf.m.fileInfos[int32(fileIdx)].dirtyFile = filename
    setLen(conf.m.fileInfos[int32(fileIdx)].lines, 0)


def setHash(conf: ConfigRef, fileIdx: FileIndex, hash: string) -> None:
    assert int32(fileIdx) >= 0
    if comptime(defined("gcArc") or defined("gcOrc") or defined("gcAtomicArc") or defined("gcYrc")):
        conf.m.fileInfos[int32(fileIdx)].hash = hash
    else:
        shallowCopy(conf.m.fileInfos[int32(fileIdx)].hash, hash)


def getHash(conf: ConfigRef, fileIdx: FileIndex) -> string:
    assert int32(fileIdx) >= 0
    if comptime(defined("gcArc") or defined("gcOrc") or defined("gcAtomicArc") or defined("gcYrc")):
        result = conf.m.fileInfos[int32(fileIdx)].hash
    else:
        result = string("")
        shallowCopy(result, conf.m.fileInfos[int32(fileIdx)].hash)
    return result


@dispatch
def toFullPathConsiderDirty(conf: ConfigRef, fileIdx: FileIndex) -> AbsoluteFile:
    if int32(fileIdx) < 0:
        result = AbsoluteFile(commandLineDesc if fileIdx == commandLineIdx else string("???"))
    elif not isEmpty(conf.m.fileInfos[int32(fileIdx)].dirtyFile):
        result = conf.m.fileInfos[int32(fileIdx)].dirtyFile
    else:
        result = conf.m.fileInfos[int32(fileIdx)].fullPath
    return result


@template
def toFilename(conf: ConfigRef, info: TLineInfo) -> string:
    return toFilename(conf, info.fileIndex)


@template
def toProjPath(conf: ConfigRef, info: TLineInfo) -> string:
    return toProjPath(conf, info.fileIndex)


@template
def toFullPath(conf: ConfigRef, info: TLineInfo) -> string:
    return toFullPath(conf, info.fileIndex)


@template
def toFullPathConsiderDirty(conf: ConfigRef, info: TLineInfo) -> string:
    return string(toFullPathConsiderDirty(conf, info.fileIndex))


def toFilenameOption(conf: ConfigRef, fileIdx: FileIndex, opt: FilenameOption) -> string:
    match opt:
        case FilenameOption.foAbs:
            result = toFullPath(conf, fileIdx)
        case FilenameOption.foRelProject:
            result = toProjPath(conf, fileIdx)
        case FilenameOption.foCanonical:
            with let:
                absPath = toFullPath(conf, fileIdx)
            result = canonicalImportAux(conf, AbsoluteFile(absPath))
        case FilenameOption.foName:
            result = lastPathPart(toProjPath(conf, fileIdx))
        case FilenameOption.foLegacyRelProj:
            with let:
                absPath = toFullPath(conf, fileIdx)
                relPath = toProjPath(conf, fileIdx)
            result = absPath if (relPath.len > absPath.len) or (relPath.count(string("..")) > 2) else relPath
        case FilenameOption.foStacktrace:
            if TGlobalOption.optExcessiveStackTrace in conf.globalOptions:
                result = toFilenameOption(conf, fileIdx, FilenameOption.foAbs)
            else:
                result = toFilenameOption(conf, fileIdx, FilenameOption.foName)
    return result


@dispatch
def toMsgFilename(conf: ConfigRef, fileIdx: FileIndex) -> string:
    return toFilenameOption(conf, fileIdx, conf.filenameOption)


@template
def toMsgFilename(conf: ConfigRef, info: TLineInfo) -> string:
    return toMsgFilename(conf, info.fileIndex)


def toLinenumber(info: TLineInfo) -> nint:
    """{.inline.}"""
    result = int(info.line)
    return result


def toColumn(info: TLineInfo) -> nint:
    """{.inline.}"""
    result = info.col
    return result


@dispatch
def toFileLineCol(info: InstantiationInfo) -> string:
    """{.inline.}"""
    result = string("")
    toLocation(result, info.filename, info.line, info.column + ColOffset)
    return result


@dispatch
def toFileLineCol(conf: ConfigRef, info: TLineInfo) -> string:
    """{.inline.}"""
    result = string("")
    toLocation(result, toMsgFilename(conf, info), int(info.line), int(info.col) + ColOffset)
    return result


# TODO: requires nimic feature `$` with two parameters (G13): proc `$`*(conf: ConfigRef; info: TLineInfo): string
def _lineInfoToStr(conf: ConfigRef, info: TLineInfo) -> string:
    return toFileLineCol(conf, info)


# TODO: requires nimic feature {.error.} procs (G17): proc `$`*(info: TLineInfo): string {.error.} = discard
# TODO: requires nimic feature custom operators (G13): proc `??`*(conf: ConfigRef; info: TLineInfo, filename: string): bool


class MsgFlag(NIntEnum):
    ## flags altering msgWriteln behavior
    msgStdout = 0  ## force writing to stdout, even stderr is default
    msgSkipHook = auto()  ## skip message hook even if it is present
    msgNoUnitSep = auto()  ## the message is a complete "paragraph".


MsgFlags = Tset[MsgFlag]


def msgWriteln(conf: ConfigRef, s: string, flags: MsgFlags = MsgFlags()) -> None:
    ## Writes given message string to stderr by default.
    ## If ``--stdout`` option is given, writes to stdout instead. If message hook
    ## is present, then it is used to output message rather than stderr/stdout.
    ## This behavior can be altered by given optional flags.

    ## This is used for 'nim dump' etc. where we don't have nimsuggest
    ## support.
    #if conf.cmd == cmdIdeTools and optCDebug notin gGlobalOptions: return
    with let:
        sep = conf.unitSep if MsgFlag.msgNoUnitSep not in flags else string("")
    if not isNil(conf.writelnHook) and MsgFlag.msgSkipHook not in flags:
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
            # On Windows stderr is fully-buffered when piped, regardless of C std.
            if comptime(defined("windows")):
                flushFile(stderr)


# TODO: requires nimic feature macros (G17): macro callIgnoringStyle(theProc: typed, first: typed,
#   args: varargs[typed]): untyped -- calls theProc(first, args) without the style/color arguments


# TODO: requires nimic feature macros (G17): macro callStyledWriteLineStderr(args: varargs[typed]): untyped --
#   styledWriteLine(stderr, args); contains `when false: ... resetAttributes(stderr)`


@template
def _callWritelnHook(*args: varargs[string, str]):
    conf.writelnHook(_concat(args))


def _msgWrite(conf: ConfigRef, s: string) -> None:
    if conf.m.errorOutputs != Tset[TErrorOutput]():
        with let:
            stdOrr = stdout if TGlobalOption.optStdout in conf.globalOptions else stderr
        write(stdOrr, s)
        flushFile(stdOrr)
        conf.lastMsgWasDot.incl(_toStdOrrKind(stdOrr))  # subsequent writes need `flushDot`


# TODO: requires nimic feature macros (G17): template styledMsgWriteln(args: varargs[typed]) writes the
# style and color arguments with callStyledWriteLineStderr when optUseColors is on, and calls
# callIgnoringStyle otherwise. Stand-in: the message text without styles, as the template writes it
# without colors (`when defined(windows): flushFile(stderr)` is part of the template).
def _styledMsgWriteln(conf: ConfigRef, s: string) -> None:
    if not isNil(conf.writelnHook):
        conf.writelnHook(s)  # callIgnoringStyle(callWritelnHook, nil, args)
    elif TGlobalOption.optStdout in conf.globalOptions:
        if TErrorOutput.eStdOut in conf.m.errorOutputs:
            flushDot(conf)
            writeLine(stdout, s)
            flushFile(stdout)
    elif TErrorOutput.eStdErr in conf.m.errorOutputs:
        flushDot(conf)
        writeLine(stderr, s)


def msgKindToString(kind: TMsgKind) -> string:
    return MsgKindToStr[kind]
    # later versions may provide translated error messages


def _getMessageStr(msg: TMsgKind, arg: string) -> string:
    return msgKindToString(msg) % [arg]


class TErrorHandling(NIntEnum):
    doNothing = 0
    doAbort = auto()
    doRaise = auto()


def log(s: string) -> None:
    with var:
        f: File = default(File)
    if open(f, getHomeDir() / string("nimsuggest.log"), FileMode.fmAppend):
        writeLine(f, s)
        close(f)


def _quit(conf: ConfigRef, msg: TMsgKind) -> None:
    """{.gcsafe.}"""
    if conf.isDefined(string("nimDebug")):
        quitOrRaise(conf, string(str(msg)))
    elif defined("debug") or msg == TMsgKind.errInternal or conf.hasHint(TMsgKind.hintStackTrace):
        with pragma("gcsafe"):
            if stackTraceAvailable() and isNil(conf.writelnHook):
                writeStackTrace()
            else:
                # TODO: requires nimic feature macros (G17): styledMsgWriteln(fgRed, ..., conf.unitSep)
                _styledMsgWriteln(conf, string("""
No stack traceback available
To create a stacktrace, rerun compilation with './koch temp $1 <file>', see $2 for details""") %
                    [conf.command, createDocLink(string("intern.html#debugging-the-compiler"))] + conf.unitSep)
    quit(1)


def _handleError(conf: ConfigRef, msg: TMsgKind, eh: TErrorHandling, s: string, ignoreMsg: bool) -> None:
    if msg in fatalMsgs:
        if conf.cmd == Command.cmdIdeTools:
            log(s)
        if conf.cmd != Command.cmdIdeTools or msg != TMsgKind.errFatal:
            _quit(conf, msg)
    if (msg >= errMin and msg <= errMax or
            (msg in inrange(warnMin, hintMax) and msg in conf.warningAsErrors and not ignoreMsg)):
        conf.errorCounter += 1
        conf.exitcode = int8(1)
        if conf.errorCounter >= conf.errorMax:
            # only really quit when we're not in the new 'nim check --def' mode:
            if conf.ideCmd == IdeCmd.ideNone:
                if comptime(defined("nimsuggest")):
                    #we need to inform the user that something went wrong when initializing NimSuggest
                    raiseRecoverableError(s)
                else:
                    _quit(conf, msg)
        elif eh == TErrorHandling.doAbort and conf.cmd != Command.cmdIdeTools:
            _quit(conf, msg)
        elif eh == TErrorHandling.doRaise:
            raiseRecoverableError(s)


@ufcs(TLineInfo)
def __eq__(a: TLineInfo, b: TLineInfo) -> bool:
    result = a.line == b.line and a.fileIndex == b.fileIndex
    return result


def exactEquals(a: TLineInfo, b: TLineInfo) -> bool:
    result = a.fileIndex == b.fileIndex and a.line == b.line and a.col == b.col
    return result


def _writeContext(conf: ConfigRef, lastinfo: TLineInfo) -> None:
    with const:
        instantiationFrom = string("template/generic instantiation from here")
        instantiationOfFrom = string("template/generic instantiation of `$1` from here")
    with var:
        info = lastinfo.copy()
    for i in range(conf.m.msgContext.len):
        with let:
            context = conf.m.msgContext[i]
        if context.info != lastinfo and context.info != info:
            if conf.structuredErrorHook is not None:
                conf.structuredErrorHook(conf, context.info, instantiationFrom,
                                         Severity.Hint)
            else:
                with let:
                    message = (instantiationFrom if context.detail == string("")
                               else format(instantiationOfFrom, context.detail))
                # TODO: requires nimic feature macros (G17): styledMsgWriteln(styleBright, conf.toFileLineCol(context.info), " ", resetStyle, message)
                _styledMsgWriteln(conf, toFileLineCol(conf, context.info) + string(" ") + message)
        info = context.info


def _ignoreMsgBecauseOfIdeTools(conf: ConfigRef, msg: TMsgKind) -> bool:
    return msg >= TMsgKind.errGenerated and conf.cmd == Command.cmdIdeTools and TGlobalOption.optIdeDebug not in conf.globalOptions


def _addSourceLine(conf: ConfigRef, fileIdx: FileIndex, line: string) -> None:
    conf.m.fileInfos[int32(fileIdx)].lines.add(line)


def numLines(conf: ConfigRef, fileIdx: FileIndex) -> nint:
    ## xxx there's an off by 1 error that should be fixed; if a file ends with "foo" or "foo\n"
    ## it will return same number of lines (ie, a trailing empty line is discounted)
    result = conf.m.fileInfos[int32(fileIdx)].lines.len
    if result == 0:
        try:
            for line in lines(string(toFullPathConsiderDirty(conf, fileIdx))):
                _addSourceLine(conf, fileIdx, line)
        except IOError:
            discard
        result = conf.m.fileInfos[int32(fileIdx)].lines.len
    return result


def sourceLine(conf: ConfigRef, i: TLineInfo) -> string:
    ## 1-based index (matches editor line numbers); 1st line is for i.line = 1
    ## last valid line is `numLines` inclusive
    if int32(i.fileIndex) < 0:
        return string("")
    with let:
        num = numLines(conf, i.fileIndex)
    # can happen if the error points to EOF:
    if int(i.line) > num:
        return string("")

    result = conf.m.fileInfos[int32(i.fileIndex)].lines[int(i.line) - 1]
    return result


def _getSurroundingSrc(conf: ConfigRef, info: TLineInfo) -> string:
    if conf.hasHint(TMsgKind.hintSource) and info != unknownLineInfo:
        with const:
            indent = string("  ")
        result = string("\n") + indent + string(str(sourceLine(conf, info)))
        if info.col >= 0:
            result.add(string("\n") + indent + spaces(info.col) + ch('^'))
    else:
        result = string("")
    return result


def formatMsg(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string) -> string:
    # TODO: requires nimic feature case expressions in a `let` (G15): `let title = case msg of warnMin..warnMax: ...`
    with let:
        title = (_WarningTitle if msg in inrange(warnMin, warnMax)
                 else _HintTitle if msg in inrange(hintMin, hintMax)
                 else _ErrorTitle)
    return toFileLineCol(conf, info) + string(" ") + title + _getMessageStr(msg, arg)


def liMessage(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string,
              eh: TErrorHandling, info2: InstantiationInfo, isRaw: bool = False,
              ignoreError: bool = False) -> None:
    """{.gcsafe, noinline.}"""
    with var:
        title = string()
        color = ForegroundColor.fgBlack
        ignoreMsg = False
        sev = Severity.Hint
    with let:
        errorOutputsOld = conf.m.errorOutputs.copy()
    if msg in fatalMsgs:
        # don't gag, refs bug #7080, bug #18278; this can happen with `{.fatal.}`
        # or inside a `tryConstExpr`.
        conf.m.errorOutputs = Tset[TErrorOutput]({TErrorOutput.eStdOut, TErrorOutput.eStdErr})

    with let:
        kind = string(str(msg)) if msg in inrange(warnMin, hintMax) and msg != TMsgKind.hintUserRaw else string("")  # xxx not sure why hintUserRaw is special
    match msg:
        case _ if msg in inrange(errMin, errMax):
            sev = Severity.Error
            _writeContext(conf, info)
            title = _ErrorTitle
            color = _ErrorColor
            if comptime(False):
                # we try to filter error messages so that not two error message
                # in the same file and line are produced:
                # xxx `lastError` is only used in this disabled code; but could be useful to revive
                ignoreMsg = conf.m.lastError == info and info != unknownLineInfo and eh != TErrorHandling.doAbort
            if info != unknownLineInfo:
                conf.m.lastError = info
        case _ if msg in inrange(warnMin, warnMax):
            sev = Severity.Warning
            ignoreMsg = not conf.hasWarn(msg)
            if not ignoreMsg and msg in conf.warningAsErrors:
                title = _ErrorTitle
                color = _ErrorColor
            else:
                title = _WarningTitle
                color = _WarningColor
            if not ignoreMsg:
                _writeContext(conf, info)
            conf.warnCounter += 1
        case _ if msg in inrange(hintMin, hintMax):
            sev = Severity.Hint
            ignoreMsg = not conf.hasHint(msg)
            if not ignoreMsg and msg in conf.warningAsErrors:
                title = _ErrorTitle
                color = _ErrorColor
            else:
                title = _HintTitle
                color = _HintColor
            conf.hintCounter += 1

    with let:
        s = arg if isRaw else _getMessageStr(msg, arg)
    if not ignoreMsg:
        with let:
            loc = toFileLineCol(conf, info) + string(" ") if info != unknownLineInfo else string("")
        # we could also show `conf.cmdInput` here for `projectIsCmd`
        with var:
            kindmsg = _KindFormat % kind if kind.len > 0 else string("")
        if conf.structuredErrorHook is not None:
            conf.structuredErrorHook(conf, info, s + kindmsg, sev)
        if not _ignoreMsgBecauseOfIdeTools(conf, msg):
            if msg == TMsgKind.hintProcessing and conf.hintProcessingDots:
                _msgWrite(conf, string("."))
            else:
                # TODO: requires nimic feature macros (G17): styledMsgWriteln(styleBright, loc, resetStyle,
                #   color, title, resetStyle, s, KindColor, kindmsg, resetStyle, conf.getSurroundingSrc(info), conf.unitSep)
                _styledMsgWriteln(conf, loc + title + s + kindmsg + _getSurroundingSrc(conf, info) + conf.unitSep)
                if TMsgKind.hintMsgOrigin in conf.mainPackageNotes:
                    # xxx needs a bit of refactoring to honor `conf.filenameOption`
                    # TODO: requires nimic feature macros (G17): styledMsgWriteln(styleBright, toFileLineCol(info2),
                    #   resetStyle, " compiler msg initiated here", KindColor, KindFormat % $hintMsgOrigin, resetStyle, conf.unitSep)
                    _styledMsgWriteln(conf, toFileLineCol(info2) + string(" compiler msg initiated here") +
                                      _KindFormat % string(str(TMsgKind.hintMsgOrigin)) + conf.unitSep)
    if not ignoreError:
        _handleError(conf, msg, eh, s, ignoreMsg)
    if msg in fatalMsgs:
        # most likely would have died here but just in case, we restore state
        conf.m.errorOutputs = errorOutputsOld


@template
def rawMessage(conf: ConfigRef, msg: TMsgKind, args: openArray[string]):
    with let:
        arg = msgKindToString(msg) % args
    liMessage(conf, unknownLineInfo, msg, arg, eh=TErrorHandling.doAbort, info2=instLoc(), isRaw=True)


@template
def rawMessage(conf: ConfigRef, msg: TMsgKind, arg: string):
    liMessage(conf, unknownLineInfo, msg, arg, eh=TErrorHandling.doAbort, info2=instLoc())


@template
def fatal(conf: ConfigRef, info: TLineInfo, arg: string = string(""), msg: TMsgKind = TMsgKind.errFatal):
    liMessage(conf, info, msg, arg, TErrorHandling.doAbort, instLoc())


# TODO: requires nimic feature astToStr (G17): template globalAssert*(conf: ConfigRef; cond: untyped,
#   info: TLineInfo = unknownLineInfo, arg = "") -- "'$1' failed" % [astToStr(cond)]


@template
def globalError(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")):
    ## `local` means compilation keeps going until errorMax is reached (via `doNothing`),
    ## `global` means it stops.
    liMessage(conf, info, msg, arg, TErrorHandling.doRaise, instLoc())


@template
def globalError(conf: ConfigRef, info: TLineInfo, arg: string):
    liMessage(conf, info, TMsgKind.errGenerated, arg, TErrorHandling.doRaise, instLoc())


@template
def localError(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")):
    liMessage(conf, info, msg, arg, TErrorHandling.doNothing, instLoc())


@template
def localError(conf: ConfigRef, info: TLineInfo, arg: string):
    liMessage(conf, info, TMsgKind.errGenerated, arg, TErrorHandling.doNothing, instLoc())


@template
def message(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string = string("")):
    liMessage(conf, info, msg, arg, TErrorHandling.doNothing, instLoc())


def warningDeprecated(conf: ConfigRef, info: TLineInfo = gCmdLineInfo, msg: string = string("")) -> None:
    """{.inline.}"""
    message(conf, info, TMsgKind.warnDeprecated, msg)


def _internalErrorImpl(conf: ConfigRef, info: TLineInfo, errMsg: string, info2: InstantiationInfo) -> None:
    if conf.cmd in {Command.cmdIdeTools, Command.cmdCheck} and isNil(conf.structuredErrorHook):
        return
    _writeContext(conf, info)
    liMessage(conf, info, TMsgKind.errInternal, errMsg, TErrorHandling.doAbort, info2)


@template
def internalError(conf: ConfigRef, info: TLineInfo, errMsg: string):
    _internalErrorImpl(conf, info, errMsg, instLoc())


@template
def internalError(conf: ConfigRef, errMsg: string):
    _internalErrorImpl(conf, unknownLineInfo, errMsg, instLoc())


@template
def internalAssert(conf: ConfigRef, e: bool):
    # xxx merge with `globalAssert`
    if not e:
        with const:
            info2 = instLoc()
        with let:
            arg = toFileLineCol(info2)
        _internalErrorImpl(conf, unknownLineInfo, arg, info2)


@template
def lintReport(conf: ConfigRef, info: TLineInfo, beau: string, got: string, extraMsg: string = string("")):
    with let:
        m = string("'$1' should be: '$2'$3") % [got, beau, extraMsg]
        msg = (TMsgKind.errGenerated if TGlobalOption.optStyleError in conf.globalOptions
               else TMsgKind.warnUser if TGlobalOption.optStyleWarning in conf.globalOptions
               else TMsgKind.hintName)
    liMessage(conf, info, msg, m, TErrorHandling.doNothing, instLoc())


@dispatch
def quotedFilename(conf: ConfigRef, fi: FileIndex) -> Rope:
    if int32(fi) < 0:
        result = makeCString(string("???"))
    elif TGlobalOption.optExcessiveStackTrace in conf.globalOptions:
        result = conf.m.fileInfos[int32(fi)].quotedFullName
    else:
        result = conf.m.fileInfos[int32(fi)].quotedName
    return result


@dispatch
def quotedFilename(conf: ConfigRef, i: TLineInfo) -> Rope:
    return quotedFilename(conf, i.fileIndex)


@template
def _listMsg(title: untyped, r: untyped):
    msgWriteln(conf, title, MsgFlags({MsgFlag.msgNoUnitSep}))
    for a in r:
        msgWriteln(conf, string("  [$1] $2") % [string("x") if a in conf.notes else string(" "), string(str(a))],
                   MsgFlags({MsgFlag.msgNoUnitSep}))


@template_expand
def listWarnings(conf: ConfigRef) -> None:
    _listMsg(string("Warnings:"), inrange(warnMin, warnMax))


@template_expand
def listHints(conf: ConfigRef) -> None:
    _listMsg(string("Hints:"), inrange(hintMin, hintMax))


def genSuccessX(conf: ConfigRef) -> None:
    with let:
        mem = (formatSize(getMaxMem()) + string(" peakmem") if comptime(declared("system.getMaxMem"))
               else formatSize(getTotalMem()) + string(" totmem"))
        loc = string(str(conf.linesCompiled))
    with var:
        build = string("")
        flags = string("")
    with const:
        debugModeHints = string("none (DEBUG BUILD, `-d:release` generates faster code)")
    if conf.cmd in cmdBackends:
        if conf.backend != TBackend.backendJs:
            build.add(string("mm: $#; ") % string(str(conf.selectedGC)))
            if TGlobalOption.optThreads in conf.globalOptions:
                build.add(string("threads: on; "))
            build.add(string("opt: "))
            if TOption.optOptimizeSpeed in conf.options:
                build.add(string("speed"))
            elif TOption.optOptimizeSize in conf.options:
                build.add(string("size"))
            else:
                build.add(debugModeHints)
                # pending https://github.com/timotheecour/Nim/issues/752, point to optimization.html
            if conf.isDefined(string("danger")):
                flags.add(string(" -d:danger"))
            elif conf.isDefined(string("release")):
                flags.add(string(" -d:release"))
        else:
            build.add(string("opt: "))
            if conf.isDefined(string("danger")):
                build.add(string("speed"))
                flags.add(string(" -d:danger"))
            elif conf.isDefined(string("release")):
                build.add(string("speed"))
                flags.add(string(" -d:release"))
            else:
                build.add(debugModeHints)
        if flags.len > 0:
            build.add(string("; options:") + flags)
    with let:
        sec = formatFloat(epochTime() - conf.lastCmdTime, ffDecimal, 3)
        project = string(str(conf.projectFull)) if conf.filenameOption == FilenameOption.foAbs else string(str(conf.projectName))
        # xxx honor conf.filenameOption more accurately
    with var:
        output = string()
    if TGlobalOption.optCompileOnly in conf.globalOptions and conf.cmd != Command.cmdJsonscript:
        output = string(str(conf.jsonBuildFile))
    elif isEmpty(conf.outFile) and conf.cmd not in Tset[Command]({Command.cmdJsonscript}) + cmdDocLike + cmdBackends:
        # for some cmd we expect a valid absOutFile
        output = string("unknownOutput")
    elif TGlobalOption.optStdout in conf.globalOptions:
        output = string("stdout")
    else:
        output = string(str(conf.absOutFile()))
    if conf.filenameOption != FilenameOption.foAbs:
        output = AbsoluteFile(output).extractFilename()
        # xxx honor filenameOption more accurately
    rawMessage(conf, TMsgKind.hintSuccessX, [
        string("build"), build,
        string("loc"), loc,
        string("sec"), sec,
        string("mem"), mem,
        string("project"), project,
        string("output"), output,
        ])


if comptime(__name__ == "__main__"):
    def test_msgs() -> None:
        with var:
            conf = newConfigRef()
            captured = seq[string]()
            hookInfos = seq[Severity]()
        conf.projectPath = AbsoluteDir(string("/path/to"))

        def testHook(s: string) -> None:
            captured.add(s)

        def lastLine() -> string:
            return captured[captured.len - 1]

        # 1. C strings
        doAssert(makeCString(string("hello\nworld\"?")) == string("\"hello\\012world\\\"\\?\""))
        with var:
            cc = string("")
        toCChar(ch('\x01'), cc)
        toCChar(ch('a'), cc)
        doAssert(cc == string("\\001a"))

        # 2. file infos: absolute, relative, pseudo paths, NIF suffixes
        with let:
            absFile = AbsoluteFile(string("/path/to/mock.nim"))
            idx = fileInfoIdx(conf, absFile)
        doAssert(int(idx) == 0)
        doAssert(fileInfoKnown(conf, absFile))
        doAssert(not fileInfoKnown(conf, AbsoluteFile(string("/path/to/other.nim"))))
        doAssert(fileInfoIdx(conf, absFile) == idx)
        doAssert(fileInfoKind(conf, idx) == FileInfoKind.fikSource)
        doAssert(fileInfoKind(conf, FileIndex(99)) == FileInfoKind.fikSource)
        doAssert(conf.m.fileInfos[0].shortName == string("mock.nim"))
        # a path that doesn't exist can't be canonicalized: a pseudo path, kept as given
        doAssert(string(conf.m.fileInfos[0].projPath) == string("/path/to/mock.nim"))
        with var:
            known = False
        with let:
            nifIdx = registerNifSuffix(conf, string("sysma2dyk"), known)
        doAssert(int(nifIdx) == 1 and fileInfoKind(conf, nifIdx) == FileInfoKind.fikNifModule)
        doAssert(registerNifSuffix(conf, string("sysma2dyk"), known) == nifIdx)

        # 3. line infos
        with let:
            li = newLineInfo(idx, 10, 5)
            li2 = newLineInfo(conf, absFile, 10, 7)
        doAssert(toLinenumber(li) == 10 and toColumn(li) == 5)
        doAssert(newLineInfo(idx, 70000, 40000).line == high(uint16))
        doAssert(newLineInfo(idx, 1, 40000).col == -1)
        doAssert(li == li2 and not exactEquals(li, li2))
        doAssert(li != newLineInfo(idx, 11, 5))
        doAssert(gCmdLineInfo.fileIndex == commandLineIdx)

        # 4. info context
        doAssert(getInfoContextLen(conf) == 0)
        pushInfoContext(conf, li, string("foo"))
        pushInfoContext(conf, li2)
        doAssert(getInfoContext(conf, -1) == li2 and getInfoContext(conf, 0) == li)
        doAssert(getInfoContext(conf, 5) == unknownLineInfo)
        popInfoContext(conf)
        setInfoContextLen(conf, 0)
        doAssert(getInfoContextLen(conf) == 0)

        # 5. paths and file names
        doAssert(toFilename(conf, idx) == string("mock.nim") and toFilename(conf, li) == string("mock.nim"))
        doAssert(toFullPath(conf, li) == string("/path/to/mock.nim"))
        doAssert(toProjPath(conf, idx) == string("/path/to/mock.nim"))
        doAssert(toFullPath(conf, commandLineIdx) == commandLineDesc)
        doAssert(toFilename(conf, InvalidFileIdx) == string("???"))
        doAssert(toFullPathConsiderDirty(conf, li) == string("/path/to/mock.nim"))
        setDirtyFile(conf, idx, AbsoluteFile(string("/tmp/dirty.nim")))
        doAssert(toFullPathConsiderDirty(conf, idx) == AbsoluteFile(string("/tmp/dirty.nim")))
        setDirtyFile(conf, idx, AbsoluteFile(string("")))
        setHash(conf, idx, string("abc"))
        doAssert(getHash(conf, idx) == string("abc"))
        doAssert(toFilenameOption(conf, idx, FilenameOption.foAbs) == string("/path/to/mock.nim"))
        doAssert(toFilenameOption(conf, idx, FilenameOption.foName) == string("mock.nim"))
        doAssert(toFilenameOption(conf, idx, FilenameOption.foLegacyRelProj) == string("/path/to/mock.nim"))
        doAssert(TGlobalOption.optExcessiveStackTrace in conf.globalOptions)  # a default global option
        doAssert(toFilenameOption(conf, idx, FilenameOption.foStacktrace) == string("/path/to/mock.nim"))
        doAssert(toMsgFilename(conf, li) == toFilenameOption(conf, idx, conf.filenameOption))
        doAssert(toFileLineCol(conf, li) == toMsgFilename(conf, idx) + string("(10, 6)"))
        doAssert(_lineInfoToStr(conf, li) == toFileLineCol(conf, li))
        doAssert(quotedFilename(conf, li) == string("\"/path/to/mock.nim\""))
        doAssert(quotedFilename(conf, InvalidFileIdx) == string("\"\\?\\?\\?\""))

        # 6. message strings
        doAssert(msgKindToString(TMsgKind.errGenerated) == string("$1"))
        doAssert(formatMsg(conf, li, TMsgKind.errGenerated, string("bad")) == toFileLineCol(conf, li) + string(" Error: bad"))
        doAssert(formatMsg(conf, li, TMsgKind.warnUser, string("w")) == toFileLineCol(conf, li) + string(" Warning: w"))

        # 7. output through the writeln hook
        conf.writelnHook = testHook
        msgWriteln(conf, string("plain"))
        doAssert(lastLine() == string("plain") + conf.unitSep)
        msgWriteln(conf, string("para"), MsgFlags({MsgFlag.msgNoUnitSep}))
        doAssert(lastLine() == string("para"))
        suggestWriteln(conf, string("sug"))
        doAssert(lastLine() == string("sug"))

        # 8. messages: warnings, hints, errors, context lines, the structured hook
        conf.errorMax = 100  # errors up to errorMax don't quit
        with let:
            before = captured.len
        message(conf, li, TMsgKind.warnUser, string("careful"))
        doAssert(lastLine() == toFileLineCol(conf, li) + string(" Warning: careful [User]") + conf.unitSep)
        doAssert(conf.warnCounter == 1)
        conf.notes.excl(TMsgKind.warnUser)
        message(conf, li, TMsgKind.warnUser, string("hidden"))
        doAssert(captured.len == before + 1 and conf.warnCounter == 2)
        conf.notes.incl(TMsgKind.hintUser)
        message(conf, li, TMsgKind.hintUser, string("note"))
        doAssert(lastLine() == toFileLineCol(conf, li) + string(" Hint: note [User]") + conf.unitSep)
        pushInfoContext(conf, li2, string("tmpl"))
        localError(conf, newLineInfo(idx, 3, 0), string("oops"))
        doAssert(captured[captured.len - 2] == toFileLineCol(conf, li2) +
                 string(" template/generic instantiation of `tmpl` from here"))
        doAssert(lastLine() == toFileLineCol(conf, newLineInfo(idx, 3, 0)) + string(" Error: oops") + conf.unitSep)
        doAssert(conf.errorCounter == 1 and conf.exitcode == 1)
        popInfoContext(conf)
        with var:
            raised = False
        try:
            globalError(conf, li, string("stop"))
        except ERecoverableError:
            raised = True
        doAssert(raised and conf.errorCounter == 2)
        warningDeprecated(conf, li, string("old"))
        doAssert(lastLine().endsWith(string("old [Deprecated]") + conf.unitSep))

        def sevHook(c: ConfigRef, info: TLineInfo, msg: string, sev: Severity) -> None:
            hookInfos.add(sev)
        conf.structuredErrorHook = sevHook
        message(conf, li, TMsgKind.hintUser, string("w2"))
        doAssert(hookInfos.len == 1 and hookInfos[0] == Severity.Hint)
        conf.structuredErrorHook = None
        conf.cmd = Command.cmdCheck
        with let:
            beforeInternal = captured.len
        internalError(conf, li, string("ignored in check mode without a structured hook"))
        doAssert(captured.len == beforeInternal)
        conf.cmd = Command.cmdNone

        # 9. lint reports, lists, the success message
        conf.notes.incl(TMsgKind.warnUser)
        conf.globalOptions.incl(TGlobalOption.optStyleWarning)
        lintReport(conf, li, string("fooBar"), string("foo_bar"))
        doAssert(lastLine().endsWith(string("'foo_bar' should be: 'fooBar' [User]") + conf.unitSep))
        listWarnings(conf)
        doAssert(string("Warnings:") in captured)
        listHints(conf)
        doAssert(string("Hints:") in captured)
        conf.notes.incl(TMsgKind.hintSuccessX)
        genSuccessX(conf)
        doAssert(lastLine().endsWith(string("[SuccessX]") + conf.unitSep))
        doAssert(string(" totmem") in lastLine() or string(" peakmem") in lastLine())

        # 10. source lines around a message
        with let:
            src = AbsoluteFile(getTempDir() + string("nimic_msgs_test.nim"))
        writeFile(string(src), string("let a = 1\nlet b = 2\n"))
        with let:
            srcIdx = fileInfoIdx(conf, src)
        doAssert(numLines(conf, srcIdx) == 2)
        doAssert(sourceLine(conf, newLineInfo(srcIdx, 2, 4)) == string("let b = 2"))
        doAssert(sourceLine(conf, newLineInfo(srcIdx, 9, 0)) == string(""))
        conf.notes.incl(TMsgKind.hintSource)
        message(conf, newLineInfo(srcIdx, 2, 4), TMsgKind.hintUser, string("here"))
        doAssert(lastLine().endsWith(string("\n  let b = 2\n      ^") + conf.unitSep))
        removeFile(string(src))
        echo(string("msgs.py tests passed"))

    test_msgs()
