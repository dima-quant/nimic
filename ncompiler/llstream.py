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

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import *

from pathutils import AbsoluteFile


if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.syncio import *

with const:
    # support `useGnuReadline`, `useLinenoise` for backwards compatibility
    hasRstdin = (defined("nimUseLinenoise") or defined("useLinenoise") or defined("useGnuReadline")) and not defined("windows")

if comptime(hasRstdin):
    from nimic.std.rdstdin import readLineFromStdin

with export:
    @calltype
    def TLLRepl(s: PLLStream, buf: pointer, bufLen: nint) -> nint: pass

    @calltype
    def OnPrompt():
        """{.closure.}"""
        pass

    class TLLStreamKind(NIntEnum):
        # enum of different stream implementations
        llsNone = auto()                  # null stream: reading and writing has no effect
        llsString = auto()                # stream encapsulates a string
        llsFile = auto()                  # stream encapsulates a file
        llsStdIn = auto()                 # stream encapsulates stdin

    class TLLStream(RootObj):
        kind: TLLStreamKind # accessible for low-level access (lexbase uses this)
        f: File
        s: string
        rd: nint
        wr: nint             # for string streams
        lineOffset: nint          # for fake stdin line numbers
        repl: TLLRepl            # gives stdin control to clients
        onPrompt: OnPrompt

    @ref
    class PLLStream(TLLStream): pass

with export:
    @dispatch
    def llStreamOpen(data: string) -> PLLStream:
        return PLLStream(kind=TLLStreamKind.llsString, s=data)

    @dispatch
    def llStreamOpen(f: File) -> PLLStream:
        return PLLStream(kind=TLLStreamKind.llsFile, f=f)

    @dispatch
    def llStreamOpen(filename: AbsoluteFile, mode: FileMode) -> PLLStream:
        with var:
            result = PLLStream(kind=TLLStreamKind.llsFile)
        if not open(result.f, string(filename), mode): result = None
        return result

    @dispatch
    def llStreamOpen() -> PLLStream:
        return PLLStream(kind=TLLStreamKind.llsNone)

def countTriples(s: string) -> nint:
    with var:
        result = 0
        i = 0
    while i + 2 < len(s):
        if s[i] == ch('"') and s[i+1] == ch('"') and s[i+2] == ch('"'):
            result += 1
            i += 2
        i += 1
    return result

with export:
    def endsWith(x: string, s: set[char]) -> bool:
        with var:
            i = len(x) - 1
            result = False
        while i >= 0 and x[i] == ch(' '): i -= 1
        if i >= 0 and x[i] in s:
            result = True
        else:
            result = False
        return result

with const:
    LineContinuationOprs = {ch('+'), ch('-'), ch('*'), ch('/'), ch('\\'), ch('<'), ch('>'), ch('!'), ch('?'), ch('^'),
                            ch('|'), ch('%'), ch('&'), ch('$'), ch('@'), ch('~'), ch(',')}
    AdditionalLineContinuationOprs = {ch('#'), ch(':'), ch('=')}
    LineContinuationTokens = array[22, string]([
        string("let"), string("var"), string("const"), string("type"),  # section
        string("object"), string("tuple"),
        # from ./layouter.oprSet
        string("div"), string("mod"), string("shl"), string("shr"), string("in"), string("notin"), string("is"),
        string("isnot"), string("not"), string("of"), string("as"), string("from"), string(".."), string("and"), string("or"), string("xor"), 
    ])  # must be all `nimIdentNormalized`-ed

def eqIdent(a: string, bNormalized: string) -> bool:
    return nimIdentNormalize(a) == bNormalized

def endsWithIdent(s: string, subs: string) -> bool:
    with let:
        le = len(subs)
    if le > len(s): return False
    return eqIdent(s[len(s) - le : len(s)], subs)

def continuesWithIdent(s: string, subs: string, start: nint) -> bool:
    return eqIdent(substr(s, start, start + len(subs) - 1), subs)

@dispatch
def endsWithIdent(s: string, subs: string, endIdx: mut@nint) -> bool:
    endIdx -= len(subs)
    with var:
        result = continuesWithIdent(s, subs, endIdx + 1)
    return result

@template_expand
def containsObjectOf(x: string) -> bool:
    with const:
        sep = ch(' ')
    with var:
        idx = x.rfind(sep)
        result = False
    if idx == -1: return result
    
    @template
    def eatWord(word: untyped):
        """{.dirty.}"""
        nonlocal idx, result
        while x[idx] == sep: idx -= 1
        result = endsWithIdent(x, word, idx)
        if not result: return
        
    eatWord(string("of"))
    eatWord(string("object"))
    result = True
    return result

def endsWithLineContinuationToken(x: string) -> bool:
    with var:
        result = False
    for tok in LineContinuationTokens:
        if endsWithIdent(x, tok):
            return True
    result = containsObjectOf(x)
    return result

with export:
    def endsWithOpr(x: string) -> bool:
        with var:
            result = endsWith(x, LineContinuationOprs)
        return result

def continueLine(line: string, inTripleString: bool) -> bool:
    """{.inline.}"""
    with var:
        result = inTripleString or (len(line) > 0 and (
            line[0] == ch(' ') or
            endsWith(line, LineContinuationOprs | AdditionalLineContinuationOprs) or
            endsWithLineContinuationToken(line)
        ))
    return result

if not comptime(hasRstdin):
    # fallback implementation:
    def readLineFromStdin(prompt: string, line: mut@string) -> bool:
        stdout.write(prompt)
        stdout.flushFile()
        with var:
            result = readLine(stdin, line)
        if not result:
            stdout.write(string("\n"))
            quit(0)
        return result

def llReadFromStdin(s: PLLStream, buf: pointer, bufLen: nint) -> nint:
    s.s = string("")
    s.rd = 0
    with var:
        line = newStringOfCap(120)
        triples = 0
        result = 0
    while True:
        if not readLineFromStdin(string(">>> ") if len(s.s) == 0 else string("... "), line):
            # now readLineFromStdin meets EOF (ctrl-D/Z) or ctrl-C
            quit()
        s.s += line
        s.s += string("\n")
        triples += countTriples(line)
        if not continueLine(line, (triples & 1) == 1): break
    s.lineOffset += 1
    result = min(bufLen, len(s.s) - s.rd)
    if result > 0:
        copy_mem(buf, readRawData(s.s, s.rd), result)
        s.rd += result
    return result

with export:
    def llStreamOpenStdIn(r: TLLRepl = llReadFromStdin, onPrompt: OnPrompt = None) -> PLLStream:
        return PLLStream(kind=TLLStreamKind.llsStdIn, s=string(""), lineOffset=-1, repl=r, onPrompt=onPrompt)

    def llStreamClose(s: PLLStream):
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsString | TLLStreamKind.llsStdIn:
                pass
            case TLLStreamKind.llsFile:
                close(s.f)

    def llStreamRead(s: PLLStream, buf: pointer, bufLen: nint) -> nint:
        with var:
            result = 0
        match s.kind:
            case TLLStreamKind.llsNone:
                result = 0
            case TLLStreamKind.llsString:
                result = min(bufLen, len(s.s) - s.rd)
                if result > 0:
                    copy_mem(buf, readRawData(s.s, s.rd), result)
                    s.rd += result
            case TLLStreamKind.llsFile:
                result = readBuffer(s.f, buf, bufLen)
            case TLLStreamKind.llsStdIn:
                if s.onPrompt != None: s.onPrompt()
                result = s.repl(s, buf, bufLen)
        return result

    def llStreamReadLine(s: PLLStream, line: mut@string) -> bool:
        setLen(line, 0)
        with var:
            result = False
        match s.kind:
            case TLLStreamKind.llsNone:
                result = True
            case TLLStreamKind.llsString:
                while s.rd < len(s.s):
                    match s.s[s.rd]:
                        case ch('\r'):
                            s.rd += 1
                            if s.s[s.rd] == ch('\n'): s.rd += 1
                            break
                        case ch('\n'):
                            s.rd += 1
                            break
                        case _:
                            line += s.s[s.rd]
                            s.rd += 1
                result = len(line) > 0 or s.rd < len(s.s)
            case TLLStreamKind.llsFile:
                result = readLine(s.f, line)
            case TLLStreamKind.llsStdIn:
                result = readLine(stdin, line)
        return result

    @dispatch
    def llStreamWrite(s: PLLStream, data: string):
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsStdIn:
                pass
            case TLLStreamKind.llsString:
                s.s += data
                s.wr += len(data)
            case TLLStreamKind.llsFile:
                write(s.f, data)

    def llStreamWriteln(s: PLLStream, data: string):
        llStreamWrite(s, data)
        llStreamWrite(s, string("\n"))

    @dispatch
    def llStreamWrite(s: PLLStream, data: char):
        with var:
            c = char('\0')
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsStdIn:
                pass
            case TLLStreamKind.llsString:
                s.s += data
                s.wr += 1
            case TLLStreamKind.llsFile:
                c = data
                _ = writeBuffer(s.f, addr(c), sizeof(c))

    @dispatch
    def llStreamWrite(s: PLLStream, buf: pointer, buflen: nint):
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsStdIn:
                pass
            case TLLStreamKind.llsString:
                if buflen > 0:
                    setLen(s.s, len(s.s) + buflen)
                    copy_mem(addr(s.s[0 + s.wr]), buf, buflen)
                    s.wr += buflen
            case TLLStreamKind.llsFile:
                _ = writeBuffer(s.f, buf, buflen)

    def llStreamReadAll(s: PLLStream) -> string:
        with const:
            bufSize = 2048
        with var:
            result = string("")
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsStdIn:
                result = string("")
            case TLLStreamKind.llsString:
                if s.rd == 0: result = s.s
                else: result = substr(s.s, s.rd)
                s.rd = len(s.s)
            case TLLStreamKind.llsFile:
                result = newString(bufSize)
                with var:
                    bytes = readBuffer(s.f, addr(result[0]), bufSize)
                    i = bytes
                while bytes == bufSize:
                    setLen(result, i + bufSize)
                    bytes = readBuffer(s.f, addr(result[i + 0]), bufSize)
                    i += bytes
                setLen(result, i)
        return result
