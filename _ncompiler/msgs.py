"""
ncompiler/msgs.py — Message reporting (extensible stub)
Converted from compiler/msgs.nim

Provides the error/warning/hint reporting functions used by the lexer
and parser. Simplified — no terminal colors, no nimsuggest hooks.
"""
from __future__ import annotations
import sys
from ncompiler.lineinfos import (
    TMsgKind, TLineInfo, FileIndex, TFileInfo, MsgConfig,
    InvalidFileIdx, commandLineIdx, unknownLineInfo,
    Severity, ErrorOutput, fatalMsgs,
    errMin, errMax, warnMin, warnMax, hintMin, hintMax,
    FileInfoKind
)
from ncompiler.pathutils import AbsoluteFile, RelativeFile, relativeTo
from ncompiler.ropes import Rope
import os

# --- Constants ---
ColOffset = 1
commandLineDesc = "command line"


# --- File info management ---
def _newFileInfo(fullPath: AbsoluteFile, projPath: RelativeFile, kind=0) -> TFileInfo:
    fi = TFileInfo(fullPath=fullPath, projPath=projPath,
                   shortName=os.path.basename(str(fullPath)), kind=kind)
    return fi


def fileInfoIdx(conf, filename: AbsoluteFile, isKnownFile: list = None) -> FileIndex:
    """Register or look up a file, return its FileIndex."""
    try:
        canon = AbsoluteFile(os.path.realpath(str(filename)))
    except OSError:
        canon = filename
    key = str(canon)
    if key in conf.m.filenameToIndexTbl:
        if isKnownFile is not None:
            isKnownFile.append(True)
        return conf.m.filenameToIndexTbl[key]
    if isKnownFile is not None:
        isKnownFile.append(False)
    idx = FileIndex(len(conf.m.fileInfos))
    conf.m.fileInfos.append(_newFileInfo(canon, RelativeFile(str(filename))))
    conf.m.filenameToIndexTbl[key] = idx
    return idx


def newLineInfo(fileIdx: FileIndex, line: int, col: int) -> TLineInfo:
    return TLineInfo(fileIndex=fileIdx, line=min(line, 65535), col=min(col, 32767))


# --- Filename resolution ---
def toFilename(conf, fileIdx: FileIndex) -> str:
    if int(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else "???"
    return conf.m.fileInfos[int(fileIdx)].shortName

def toFullPath(conf, fileIdx: FileIndex) -> str:
    if int(fileIdx) < 0 or conf is None:
        return commandLineDesc if fileIdx == commandLineIdx else "???"
    return str(conf.m.fileInfos[int(fileIdx)].fullPath)

def toFileLineCol(conf, info: TLineInfo) -> str:
    if info == unknownLineInfo:
        return "???"
    fname = toFilename(conf, info.fileIndex)
    return f"{fname}({info.line}, {info.col + ColOffset})"


# --- Message output ---
class TErrorHandling:
    doNothing = 0
    doAbort = 1
    doRaise = 2


class RecoverableError(Exception):
    pass


def msgWriteln(conf, s: str, flags=None):
    if conf.writelnHook is not None:
        conf.writelnHook(s)
    else:
        print(s, file=sys.stderr)


def liMessage(conf, info: TLineInfo, msg: TMsgKind, arg: str,
              eh: int = TErrorHandling.doNothing):
    """Core message routine — simplified version."""
    if msg.value >= errMin.value and msg.value <= errMax.value:
        title = "Error: "
        conf.errorCounter += 1
        conf.exitcode = 1
    elif msg.value >= warnMin.value and msg.value <= warnMax.value:
        if not conf.hasWarn(msg):
            return
        title = "Warning: "
        conf.warnCounter += 1
    elif msg.value >= hintMin.value and msg.value <= hintMax.value:
        if not conf.hasHint(msg):
            return
        title = "Hint: "
        conf.hintCounter += 1
    else:
        title = ""

    loc = toFileLineCol(conf, info) + " " if info != unknownLineInfo else ""
    s = f"{loc}{title}{arg}"
    msgWriteln(conf, s)

    if msg in fatalMsgs:
        raise SystemExit(s)
    if eh == TErrorHandling.doAbort:
        raise SystemExit(s)
    if eh == TErrorHandling.doRaise:
        raise RecoverableError(s)


# --- Public message templates ---
def rawMessage(conf, msg: TMsgKind, arg: str = ""):
    liMessage(conf, unknownLineInfo, msg, arg, TErrorHandling.doAbort)

def message(conf, info: TLineInfo, msg: TMsgKind, arg: str = ""):
    liMessage(conf, info, msg, arg, TErrorHandling.doNothing)

def localError(conf, info: TLineInfo, msg_or_str, arg: str = ""):
    if isinstance(msg_or_str, TMsgKind):
        liMessage(conf, info, msg_or_str, arg, TErrorHandling.doNothing)
    else:
        liMessage(conf, info, TMsgKind.errGenerated, str(msg_or_str), TErrorHandling.doNothing)

def globalError(conf, info: TLineInfo, msg_or_str, arg: str = ""):
    if isinstance(msg_or_str, TMsgKind):
        liMessage(conf, info, msg_or_str, arg, TErrorHandling.doRaise)
    else:
        liMessage(conf, info, TMsgKind.errGenerated, str(msg_or_str), TErrorHandling.doRaise)

def internalError(conf, info_or_msg, msg: str = ""):
    if isinstance(info_or_msg, TLineInfo):
        liMessage(conf, info_or_msg, TMsgKind.errInternal, msg, TErrorHandling.doAbort)
    else:
        liMessage(conf, unknownLineInfo, TMsgKind.errInternal, str(info_or_msg), TErrorHandling.doAbort)

def lintReport(conf, info: TLineInfo, beau: str, got: str, extraMsg: str = ""):
    m = f"'{got}' should be: '{beau}'{extraMsg}"
    liMessage(conf, info, TMsgKind.hintName, m, TErrorHandling.doNothing)
