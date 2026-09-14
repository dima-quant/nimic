"""
ncompiler/llstream.py — Low-level input streams
Converted from compiler/llstream.nim
"""
from __future__ import annotations
from nimic.ntypes import *


class TLLStreamKind(NIntEnum):
    llsNone = auto()
    llsString = auto()
    llsFile = auto()
    llsStdIn = auto()


class TLLStream:
    """Low-level stream — wraps a string or file for the lexer."""
    __slots__ = ('kind', 's', 'rd', 'wr', 'lineOffset', 'f')
    def __init__(self):
        self.kind = TLLStreamKind.llsNone
        self.s = ""
        self.rd = 0        # read position
        self.wr = 0
        self.lineOffset = 0
        self.f = None       # file handle

PLLStream = TLLStream  # pointer alias


def llStreamOpen(data: str) -> PLLStream:
    """Open a stream from a string."""
    result = TLLStream()
    result.kind = TLLStreamKind.llsString
    result.s = data
    result.rd = 0
    result.wr = len(data)
    return result


def llStreamOpenFile(filename: str) -> PLLStream:
    """Open a stream from a file."""
    try:
        f = open(filename, 'r')
        result = TLLStream()
        result.kind = TLLStreamKind.llsFile
        result.f = f
        result.s = f.read()
        result.rd = 0
        result.wr = len(result.s)
        f.close()
        return result
    except IOError:
        return None


def llStreamRead(s: PLLStream, buf: bytearray, bufLen: int) -> int:
    """Read up to bufLen bytes from stream into buf. Returns bytes read."""
    if s.kind == TLLStreamKind.llsString:
        avail = len(s.s) - s.rd
        count = min(avail, bufLen)
        if count > 0:
            data = s.s[s.rd:s.rd + count].encode('utf-8')
            actual = min(len(data), bufLen)
            buf[:actual] = data[:actual]
            s.rd += count
            return actual
        return 0
    return 0


def llStreamReadLine(s: PLLStream) -> tuple[str, bool]:
    """Read a line. Returns (line, success)."""
    if s.rd >= len(s.s):
        return ("", False)
    end = s.s.find('\n', s.rd)
    if end == -1:
        line = s.s[s.rd:]
        s.rd = len(s.s)
    else:
        line = s.s[s.rd:end]
        s.rd = end + 1
    return (line, True)


def llStreamReadAll(s: PLLStream) -> str:
    """Read remaining content."""
    result = s.s[s.rd:]
    s.rd = len(s.s)
    return result


def llStreamClose(s: PLLStream):
    """Close the stream."""
    if s is not None and s.f is not None:
        try:
            s.f.close()
        except:
            pass
    if s is not None:
        s.kind = TLLStreamKind.llsNone
