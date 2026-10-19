# /// nimic
#
# ///
#
#
#           The Nim Compiler
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# Base Object of a lexer with efficient buffer handling. In fact
# I believe that this is the most efficient method of buffer
# handling that exists! Only at line endings checks are necessary
# if the buffer needs refilling.

from __future__ import annotations
from nimic.ntypes import *

from .llstream import *

from nimic.std.strutils import *

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *

with const:
    Lrz = ch(' ')
    Apo = ch('\'')
    Tabulator = ch('\x09')
    ESC = ch('\x1B')
    CR = ch('\x0D')
    FF = ch('\x0C')
    LF = ch('\x0A')
    BEL = ch('\x07')
    BACKSPACE = ch('\x08')
    VT = ch('\x0B')

with const:
    EndOfFile = ch('\0')        # end of file marker
                                # A little picture makes everything clear :-)
                                #  buf:
                                #  "Example Text\n ha!"   bufLen = 17
                                #   ^pos = 0     ^ sentinel = 12
                                #
    NewLines = Tset[char]({CR, LF})


class TBaseLexer(RootObj):
    bufpos: nint
    buf: cstring
    _bufStorage: string
    _bufLen: nint
    stream: PLLStream         # we read from this stream
    lineNumber: nint          # the current line number
                              # private data:
    sentinel: nint
    lineStart: nint           # index of last line start in buffer
    offsetBase: nint          # use ``offsetBase + bufpos`` to get the offset

    def openBaseLexer(L: mut@TBaseLexer, inputstream: PLLStream,
                      bufLen: nint = 8192):
        # 8K is a reasonable buffer size
        pass

    def closeBaseLexer(L: mut@TBaseLexer): pass
    def getCurrentLine(L: TBaseLexer, marker: bool = True) -> string: pass
    def getColNumber(L: TBaseLexer, pos: nint) -> nint: pass

    def handleCR(L: mut@TBaseLexer, pos: nint) -> nint:
        # Call this if you scanned over CR in the buffer; it returns the
        # position to continue the scanning from. `pos` must be the position
        # of the CR.
        pass

    def handleLF(L: mut@TBaseLexer, pos: nint) -> nint:
        # Call this if you scanned over LF in the buffer; it returns the
        # position to continue the scanning from. `pos` must be the position
        # of the LF.
        pass

    # implementation

    def closeBaseLexer(L: mut@TBaseLexer):
        L.stream.llStreamClose()

    def _fillBuffer(L: mut@TBaseLexer):
        with var:
            charsRead: nint = nint()
            toCopy: nint = nint()
            s: nint = nint()  # all are in characters,
                              # not bytes (in case this
                              # is not the same)
            oldBufLen: nint = nint()
        # we know here that pos == L.sentinel, but not if this proc
        # is called the first time by initBaseLexer()
        assert(L.sentinel < L._bufLen)
        toCopy = L._bufLen - L.sentinel - 1
        assert(toCopy >= 0)
        if toCopy > 0:
            moveMem(addr(L.buf[0]), addr(L.buf[L.sentinel + 1]), toCopy)
            # "moveMem" handles overlapping regions
        charsRead = L.stream.llStreamRead(addr(L.buf[toCopy]), L.sentinel + 1)
        s = toCopy + charsRead
        if charsRead < L.sentinel + 1:
            L.buf[s] = EndOfFile      # set end marker
            L.sentinel = s
        else:
            # compute sentinel:
            s -= 1                    # BUGFIX (valgrind)
            while True:
                assert(s < L._bufLen)
                while (s >= 0) and not (L.buf[s] in NewLines): s -= 1
                if s >= 0:
                    # we found an appropriate character for a sentinel:
                    L.sentinel = s
                    break
                else:
                    # rather than to give up here because the line is too long,
                    # double the buffer's size and try again:
                    oldBufLen = L._bufLen.copy()  # the field is changed below
                    L._bufLen = L._bufLen * 2
                    L._bufStorage.setLen(L._bufLen)
                    L.buf = L._bufStorage.cstring
                    assert(L._bufLen - oldBufLen == oldBufLen)
                    charsRead = L.stream.llStreamRead(addr(L.buf[oldBufLen]),
                                                      oldBufLen)
                    if charsRead < oldBufLen:
                        L.buf[oldBufLen + charsRead] = EndOfFile
                        L.sentinel = oldBufLen + charsRead
                        break
                    s = L._bufLen - 1

    def _fillBaseLexer(L: mut@TBaseLexer, pos: nint) -> nint:
        assert(pos <= L.sentinel)
        if pos < L.sentinel:
            result = pos + 1          # nothing to do
        else:
            L._fillBuffer()
            L.offsetBase += pos + 1
            L.bufpos = 0
            result = 0
        L.lineStart = result
        return result

    def handleCR(L: mut@TBaseLexer, pos: nint) -> nint:
        assert(L.buf[pos] == CR)
        L.lineNumber += 1
        result = L._fillBaseLexer(pos)
        if L.buf[result] == LF:
            result = L._fillBaseLexer(result)
        return result

    def handleLF(L: mut@TBaseLexer, pos: nint) -> nint:
        assert(L.buf[pos] == LF)
        L.lineNumber += 1
        result = L._fillBaseLexer(pos) #L.lastNL := result-1; // BUGFIX: was: result;
        return result

    def _skipUTF8BOM(L: mut@TBaseLexer):
        if L.buf[0] == ch('\xEF') and L.buf[1] == ch('\xBB') and L.buf[2] == ch('\xBF'):
            L.bufpos += 3
            L.lineStart += 3

    def openBaseLexer(L: mut@TBaseLexer, inputstream: PLLStream, bufLen: nint = 8192):
        assert(bufLen > 0)
        L.bufpos = 0
        L.offsetBase = 0
        L._bufStorage = newString(bufLen)
        L.buf = L._bufStorage.cstring
        L._bufLen = bufLen
        L.sentinel = bufLen - 1
        L.lineStart = 0
        L.lineNumber = 1            # lines start at 1
        L.stream = inputstream
        L._fillBuffer()
        L._skipUTF8BOM()

    def getColNumber(L: TBaseLexer, pos: nint) -> nint:
        result = abs(pos - L.lineStart)
        return result

    def getCurrentLine(L: TBaseLexer, marker: bool = True) -> string:
        result = string("")
        with var:
            i = L.lineStart.copy()
        while L.buf[i] not in Tset[char]({CR, LF, EndOfFile}):
            result.add(L.buf[i])
            i += 1
        result.add(string("\n"))
        if marker:
            result.add(spaces(L.getColNumber(L.bufpos)) + ch('^') + string("\n"))
        return result


if comptime(__name__ == "__main__"):
    with var:
        _L = TBaseLexer()
    _L.openBaseLexer(llStreamOpen(string("ab\ncd\r\nef")))
    assert _L.lineNumber == 1
    assert _L.getColNumber(_L.bufpos) == 0
    assert _L.getCurrentLine(False) == string("ab\n")
    assert _L.getCurrentLine(True) == string("ab\n^\n")
    _L.bufpos = 1
    assert _L.getColNumber(_L.bufpos) == 1
    assert _L.getCurrentLine(True) == string("ab\n ^\n")
    _L.bufpos = _L.handleLF(2)
    assert _L.lineNumber == 2
    assert _L.getColNumber(_L.bufpos) == 0
    assert _L.getCurrentLine(False) == string("cd\n")
    assert _L.getCurrentLine(True) == string("cd\n^\n")
    _L.bufpos = _L.handleCR(5)
    assert _L.lineNumber == 3
    assert _L.getColNumber(_L.bufpos) == 0
    assert _L.getCurrentLine(False) == string("ef\n")
    _L.bufpos += 1
    assert _L.getColNumber(_L.bufpos) == 1
    assert _L.getCurrentLine(True) == string("ef\n ^\n")
    _L.closeBaseLexer()

    with var:
        _Lbom = TBaseLexer()
    _Lbom.openBaseLexer(llStreamOpen(string("\xEF\xBB\xBFhello\n")))
    assert _Lbom.bufpos == 3
    assert _Lbom.lineStart == 3
    assert _Lbom.getColNumber(_Lbom.bufpos) == 0
    assert _Lbom.getCurrentLine(False) == string("hello\n")
    _Lbom.closeBaseLexer()

    with var:
        _Lgrow = TBaseLexer()
    _Lgrow.openBaseLexer(llStreamOpen(string("abcdefghij\nkl\n")), 4)
    assert _Lgrow.getCurrentLine(False) == string("abcdefghij\n")
    _Lgrow.bufpos = _Lgrow.handleLF(10)
    assert _Lgrow.lineNumber == 2
    assert _Lgrow.getCurrentLine(False) == string("kl\n")
    _Lgrow.closeBaseLexer()

    # refill at the sentinel: the rest of the buffer is moved to its start (moveMem), offsetBase grows
    # (values checked against the original nimlexbase.nim)
    for _bl in [4, 6, 8, 64]:
        with var:
            _Lfill = TBaseLexer()
            _lines = string("")
        _Lfill.openBaseLexer(llStreamOpen(string("ab\ncdef\r\ng\n\nhijklmnop\nq")), _bl)
        with var:
            _pos = _Lfill.bufpos.copy()
        while _Lfill.buf[_pos] != EndOfFile:
            if _Lfill.buf[_pos] == LF:
                _lines.add(_Lfill.getCurrentLine(False))
                _pos = _Lfill.handleLF(_pos)
                _Lfill.bufpos = _pos
            elif _Lfill.buf[_pos] == CR:
                _lines.add(_Lfill.getCurrentLine(False))
                _pos = _Lfill.handleCR(_pos)
                _Lfill.bufpos = _pos
            else:
                _pos += 1
        assert _lines == string("ab\ncdef\ng\n\nhijklmnop\n")
        assert _Lfill.lineNumber == 6
        assert _Lfill.offsetBase == (12 if _bl < 64 else 0)
        assert _Lfill.getCurrentLine(False) == string("q\n")
        _Lfill.closeBaseLexer()

    echo(string("nimlexbase: all tests passed!"))
