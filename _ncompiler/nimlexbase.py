"""
ncompiler/nimlexbase.py — Base lexer with buffer management
Converted from compiler/nimlexbase.nim

Uses a bytearray buffer with '\0' sentinel for EndOfFile,
matching the Nim compiler's cstring-based buffer model.
"""
from __future__ import annotations
from ncompiler.llstream import PLLStream, TLLStreamKind

EndOfFile = '\0'
NewLines = {'\r', '\n'}

# Buffer size for reading chunks
_BUF_SIZE = 8192


class TBaseLexer:
    """Base lexer providing buffer management and line/column tracking."""
    __slots__ = ('buf', 'bufLen', 'bufpos', 'input', 'lineNumber',
                 'lineStart', 'offsetBase')
    def __init__(self):
        self.buf: str = ""        # full source as a string + '\0' sentinel
        self.bufLen: int = 0
        self.bufpos: int = 0
        self.input: PLLStream | None = None
        self.lineNumber: int = 1
        self.lineStart: int = 0
        self.offsetBase: int = 0


def openBaseLexer(L: TBaseLexer, inputstream: PLLStream):
    """Initialize the base lexer from a stream."""
    L.input = inputstream
    # Read all content into a single string buffer with '\0' sentinel
    if inputstream.kind == TLLStreamKind.llsString:
        content = inputstream.s
    else:
        content = ""
    L.buf = content + EndOfFile
    L.bufLen = len(content)
    L.bufpos = 0
    L.lineNumber = 1
    L.lineStart = 0


def closeBaseLexer(L: TBaseLexer):
    """Close the base lexer."""
    L.buf = EndOfFile
    L.bufLen = 0


def getColNumber(L: TBaseLexer, pos: int) -> int:
    """Get 0-based column number for position."""
    return pos - L.lineStart


def handleCR(L: TBaseLexer, pos: int) -> int:
    """Handle a CR character, advance past CR+LF if present."""
    assert L.buf[pos] == '\r'
    L.lineNumber += 1
    result = pos + 1
    if result < len(L.buf) and L.buf[result] == '\n':
        result += 1
    L.lineStart = result
    return result


def handleLF(L: TBaseLexer, pos: int) -> int:
    """Handle an LF character."""
    assert L.buf[pos] == '\n'
    L.lineNumber += 1
    result = pos + 1
    L.lineStart = result
    return result


def handleCRLF(L: TBaseLexer, pos: int) -> int:
    """Handle CR, LF, or CRLF at pos."""
    c = L.buf[pos]
    if c == '\r':
        return handleCR(L, pos)
    elif c == '\n':
        return handleLF(L, pos)
    return pos


def getCurrentLine(L: TBaseLexer, marker: bool = True) -> str:
    """Get the current line being lexed."""
    result = []
    i = L.lineStart
    while i < len(L.buf) and L.buf[i] not in ('\r', '\n', EndOfFile):
        result.append(L.buf[i])
        i += 1
    line = "".join(result)
    if marker:
        col = L.bufpos - L.lineStart
        line += "\n" + " " * col + "^"
    return line
