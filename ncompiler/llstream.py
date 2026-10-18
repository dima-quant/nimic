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

from .pathutils import *


if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.syncio import *

with const:
    # support `useGnuReadline`, `useLinenoise` for backwards compatibility
    hasRstdin = (defined("nimUseLinenoise") or defined("useLinenoise") or defined("useGnuReadline")) and not defined("windows")

if comptime(hasRstdin):
    from nimic.std.rdstdin import *

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
class PLLStream(TLLStream):
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
                    copyMem(buf, addr(s.s[s.rd]), result)
                    s.rd += result
            case TLLStreamKind.llsFile:
                result = readBuffer(s.f, buf, bufLen)
            case TLLStreamKind.llsStdIn:
                if s.onPrompt != None: s.onPrompt()
                result = s.repl(s, buf, bufLen)
        return result

    def llStreamReadLine(s: PLLStream, line: mut@string) -> bool:
        setLen(line, 0)
        match s.kind:
            case TLLStreamKind.llsNone:
                result = True
            case TLLStreamKind.llsString:
                while s.rd < s.s.len:
                    match s.s[s.rd]:
                        case _ if s.s[s.rd] == ch('\r'):
                            s.rd += 1
                            if s.s[s.rd] == ch('\n'): s.rd += 1
                            break
                        case _ if s.s[s.rd] == ch('\n'):
                            s.rd += 1
                            break
                        case _:
                            line.add(s.s[s.rd])
                            s.rd += 1
                result = line.len > 0 or s.rd < s.s.len
            case TLLStreamKind.llsFile:
                result = readLine(s.f, line)
            case TLLStreamKind.llsStdIn:
                result = readLine(stdin, line)
        return result

    def llStreamWrite(s: PLLStream, data: string):
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsStdIn:
                pass
            case TLLStreamKind.llsString:
                s.s.add(data)
                s.wr += len(data)
            case TLLStreamKind.llsFile:
                write(s.f, data)

    def llStreamWriteln(s: PLLStream, data: string):
        s.llStreamWrite(data)
        s.llStreamWrite(string("\n"))

    def llStreamWrite(s: PLLStream, data: char):
        with var:
            c: char
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsStdIn:
                pass
            case TLLStreamKind.llsString:
                s.s.add(data)
                s.wr += 1
            case TLLStreamKind.llsFile:
                c = data
                _ = writeBuffer(s.f, addr(c), sizeof(c))

    def llStreamWrite(s: PLLStream, buf: pointer, buflen: nint):
        match s.kind:
            case TLLStreamKind.llsNone | TLLStreamKind.llsStdIn:
                pass
            case TLLStreamKind.llsString:
                if buflen > 0:
                    setLen(s.s, len(s.s) + buflen)
                    copyMem(addr(s.s[s.wr]), buf, buflen)
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
    LineContinuationOprs = Tset[char]({ch('+'), ch('-'), ch('*'), ch('/'), ch('\\'), ch('<'), ch('>'), ch('!'), ch('?'), ch('^'),
                            ch('|'), ch('%'), ch('&'), ch('$'), ch('@'), ch('~'), ch(',')})
    AdditionalLineContinuationOprs = Tset[char]({ch('#'), ch(':'), ch('=')})
    LineContinuationTokens = array[22, string]([
        string("let"), string("var"), string("const"), string("type"),  # section
        string("object"), string("tuple"),
        # from ./layouter.oprSet
        string("div"), string("mod"), string("shl"), string("shr"), string("in"), string("notin"), string("is"),
        string("isnot"), string("not"), string("of"), string("as"), string("from"), string(".."), string("and"), string("or"), string("xor"),
    ])  # must be all `nimIdentNormalized`-ed

def eqIdent(a: string, bNormalized: string) -> bool:
    return nimIdentNormalize(a) == bNormalized

@dispatch
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
        idx = rfind(x, sep)
        result = False
    if idx == -1: return result

    @template
    def eatWord(word: untyped):
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

def endsWithOpr(x: string) -> bool:
    with var:
        result = endsWith(x, LineContinuationOprs)
    return result

def continueLine(line: string, inTripleString: bool) -> bool:
    """{.inline.}"""
    with var:
        result = inTripleString or (len(line) > 0 and (
            line[0] == ch(' ') or
            endsWith(line, LineContinuationOprs + AdditionalLineContinuationOprs) or
            endsWithLineContinuationToken(line)
        ))
    return result

if comptime(not declared("readLineFromStdin")):
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
        s.s.add(line)
        s.s.add(string("\n"))
        triples += countTriples(line)
        if not continueLine(line, (triples & 1) == 1): break
    s.lineOffset += 1
    result = min(bufLen, len(s.s) - s.rd)
    if result > 0:
        copyMem(buf, addr(s.s[s.rd]), result)
        s.rd += result
    return result

def llStreamOpenStdIn(r: TLLRepl = llReadFromStdin, onPrompt: OnPrompt = None) -> PLLStream:
    return PLLStream(kind=TLLStreamKind.llsStdIn, s=string(""), lineOffset=-1, repl=r, onPrompt=onPrompt)


if comptime(__name__ == "__main__"):
    from nimic.std.os import removeFile, fileExists

    # 0. containsObjectOf: a line ending in `object of` (the template eatWord walks back over words)
    assert containsObjectOf(string("T = object of ")) == True
    assert containsObjectOf(string("T = object  of  ")) == True
    assert containsObjectOf(string("T = obj of ")) == False
    assert containsObjectOf(string("T = object in ")) == False
    assert containsObjectOf(string("x")) == False
    assert endsWithLineContinuationToken(string("type T = object of ")) == True

    # 1. Null stream
    with var:
        s = llStreamOpen()
    assert s.kind == TLLStreamKind.llsNone
    s.llStreamWrite(string("noop"))
    s.llStreamWriteln(string("noop"))
    s.llStreamWrite(ch("x"))
    with var:
        line = string("")
    assert s.llStreamReadLine(line) == True
    assert line == string("")
    assert s.llStreamReadAll() == string("")
    s.llStreamClose()

    # 2. String stream reading
    with var:
        s2 = llStreamOpen(string("first\nsecond\r\nthird"))
    assert s2.kind == TLLStreamKind.llsString
    assert s2.llStreamReadLine(line) == True
    assert line == string("first")
    assert s2.llStreamReadLine(line) == True
    assert line == string("second")
    assert s2.llStreamReadLine(line) == True
    assert line == string("third")
    assert s2.llStreamReadLine(line) == False
    with var:
        s2r = llStreamOpen(string("a\rb\n"))
    assert s2r.llStreamReadLine(line) == True and line == string("a")
    assert s2r.llStreamReadLine(line) == True and line == string("b")
    assert s2r.llStreamReadLine(line) == False

    # 3. String stream writing
    with var:
        s3 = llStreamOpen(string(""))
    s3.llStreamWrite(string("abc"))
    s3.llStreamWriteln(string("def"))
    s3.llStreamWrite(ch("!"))
    assert s3.s == string("abcdef\n!")
    assert s3.wr == 8

    # 4. String stream buffer read and write
    with var:
        s4 = llStreamOpen(string("ABCDEFGH"))
        buf = array[4, char]()
        n = s4.llStreamRead(addr(buf[0]), 4)
    assert n == 4
    assert buf[0] == ch("A") and buf[1] == ch("B") and buf[2] == ch("C") and buf[3] == ch("D")
    with var:
        rem = s4.llStreamReadAll()
    assert rem == string("EFGH")

    with var:
        s5 = llStreamOpen(string(""))
    s5.llStreamWrite(addr(buf[0]), 4)
    assert s5.s == string("ABCD")
    s5.llStreamWrite(addr(buf[0]), 2)
    assert s5.s == string("ABCDAB")

    # 5. Stdin stream and callbacks
    with var:
        called = [False, False]

    def my_prompt():
        called[0] = True

    def my_repl(s: PLLStream, buf: pointer, bufLen: nint) -> nint:
        called[1] = True
        return 42

    with var:
        s_stdin = llStreamOpenStdIn(r=my_repl, onPrompt=my_prompt)
    assert s_stdin.kind == TLLStreamKind.llsStdIn
    with var:
        res = s_stdin.llStreamRead(None, 0)
    assert res == 42
    assert called[0] == True and called[1] == True
    s_stdin.llStreamClose()

    # 6. Helpers
    assert countTriples(string('"""hello"""')) == 2
    assert countTriples(string('""hello""')) == 0
    assert endsWith(string("x + "), LineContinuationOprs) == True
    assert endsWith(string("x ; "), LineContinuationOprs) == False
    assert endsWithOpr(string("a +")) == True
    assert endsWithOpr(string("a ;")) == False
    assert continueLine(string("  indent"), False) == True
    assert continueLine(string("foo ="), False) == True
    assert continueLine(string("foo"), False) == False
    assert continueLine(string("foo"), True) == True

    # 7. File stream read/write
    with var:
        tf_name = string(".scratch/test_llstream_tmp.txt")
        sf = llStreamOpen(AbsoluteFile(tf_name), FileMode.fmWrite)
    assert sf is not None
    sf.llStreamWriteln(string("line 1"))
    sf.llStreamWriteln(string("line 2"))
    sf.llStreamClose()

    with var:
        sf_in = llStreamOpen(AbsoluteFile(tf_name), FileMode.fmRead)
    assert sf_in is not None
    with var:
        fline = string("")
    assert sf_in.llStreamReadLine(fline) == True
    assert fline == string("line 1")
    assert sf_in.llStreamReadLine(fline) == True
    assert fline == string("line 2")
    sf_in.llStreamClose()

    if fileExists(tf_name):
        removeFile(tf_name)

    echo(string("llstream: all tests passed!"))

