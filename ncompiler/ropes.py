# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *

from pathutils import AbsoluteFile

if comptime(defined("nimPreviewSlimSystem")):
    import nimic.std.assertions
    import nimic.std.syncio
    import nimic.std.formatfloat

class Rope(string):
    pass

class FormatStr(string):
    def __mod__(self: static[FormatStr], args: openArray[Rope]) -> Rope:
        result = Rope()
        result = runtimeFormat(self, args)
        return result

def newRopeAppender(cap: nint = 80) -> string:
    """{.inline.}"""
    result = string()
    result = string("")
    return result

def freeze(r: Rope) -> None:
    """{.inline.}"""
    pass

def resetRopeCache() -> None:
    pass

@template
def rope(s: string) -> string:
    return s

@dispatch
def rope(i: int64) -> Rope:
    result = Rope()
    result = rope(string(str(i)))
    return result

@dispatch
def rope(f: float64) -> Rope:
    result = Rope()
    result = rope(string(str(f)))
    return result

@dispatch
def writeRope(f: File, r: Rope) -> None:
    f.write(r)

@dispatch
def writeRope(head: Rope, filename: AbsoluteFile) -> bool:
    result = bool()
    with var:
        f = default(File)
    if f.open(filename.string, fmWrite):
        writeRope(f, head)
        f.close()
        result = True
    else:
        result = False
    return result

@template
def prepend(a: mut @ Rope, b: string) -> untyped:
    a = Rope(b + a)

def runtimeFormat(frmt: FormatStr, args: openArray[Rope]) -> Rope:
    result = Rope()
    with var:
        i = 0
    result = newRopeAppender()
    with var:
        num = 0
    while i < len(frmt):
        if frmt[i] == ch('$'):
            i += 1
            if frmt[i] == ch('$'):
                result += string("$")
                i += 1
            elif frmt[i] == ch('#'):
                i += 1
                result += args[num]
                num += 1
            elif ch('0') <= frmt[i] <= ch('9'):
                with var:
                    j = 0
                while True:
                    j = j * 10 + ord(frmt[i]) - ord(ch('0'))
                    i += 1
                    if i >= len(frmt) or not (ch('0') <= frmt[i] <= ch('9')):
                        break
                num = j
                if j > high(args) + 1:
                    doAssert(False, string("invalid format string: ") + frmt)
                else:
                    result += args[j-1]
            elif frmt[i] == ch('{'):
                i += 1
                with var:
                    j = 0
                while ch('0') <= frmt[i] <= ch('9'):
                    j = j * 10 + ord(frmt[i]) - ord(ch('0'))
                    i += 1
                num = j
                if frmt[i] == ch('}'):
                    i += 1
                else:
                    doAssert(False, string("invalid format string: ") + frmt)

                if j > high(args) + 1:
                    doAssert(False, string("invalid format string: ") + frmt)
                else:
                    result += args[j-1]
            elif frmt[i] == ch('n'):
                result.add(string("\n"))
                i += 1
            elif frmt[i] == ch('N'):
                result += string("\n")
                i += 1
            else:
                doAssert(False, string("invalid format string: ") + frmt)
        else:
            result += frmt[i]
            i += 1
    return result



@template
def addf(c: mut @ Rope, frmt: FormatStr, args: openArray[Rope]) -> untyped:
    c += (frmt % args)

with const:
    bufSize = 1024

@dispatch
def equalsFile(s: Rope, f: File) -> bool:
    result = bool()
    with var:
        buf = default(array[bufSize, char])
        bpos = len(buf)
        blen = len(buf)
        btotal = 0
        rtotal = 0

    if comptime(True):
        with var:
            spos = 0
        rtotal += len(s)
        while spos < len(s):
            if bpos == blen:
                bpos = 0
                blen = readBuffer(f, addr(buf[0]), len(buf))
                btotal += blen
                if blen == 0:
                    result = False
                    return result
            with let:
                n = min(blen - bpos, len(s) - spos)
            if not equalMem(addr(buf[bpos]), cast[pointer](cast[intp](cstring(s)) + spos), n):
                result = False
                return result
            spos += n
            bpos += n

    result = readBuffer(f, addr(buf[0]), 1) == 0 and btotal == rtotal
    return result

@dispatch
def equalsFile(r: Rope, filename: AbsoluteFile) -> bool:
    result = bool()
    with var:
        f = default(File)
    result = open(f, filename.string)
    if result:
        result = equalsFile(r, f)
        close(f)
    return result

if comptime(__name__ == "__main__"):
    @template_expand
    def run_tests():
        r1 = rope(string("Hello"))
        r2 = rope(int64(123))
        r3 = rope(float64(45.67))
        
        doAssert(str(r1) == "Hello", string("r1 failed: " + str(r1)))
        doAssert(str(r2) == "123", string("r2 failed: " + str(r2)))
        doAssert(str(r3) == "45.67", string("r3 failed: " + str(r3)))
        
        # Test prepending
        r_prep = rope(string("world"))
        prepend(r_prep, string("Hello "))
        doAssert(str(r_prep) == "Hello world", string("prep failed: " + str(r_prep)))
        
        # Test runtimeFormat
        f_str = FormatStr("Value: $1, another: $2")
        res = runtimeFormat(f_str, [rope(string("A")), rope(string("B"))])
        doAssert(str(res) == "Value: A, another: B", string("runtimeFormat failed: " + str(res)))
        
        # Test __mod__
        res_mod = f_str % [rope(string("A")), rope(string("B"))]
        doAssert(str(res_mod) == "Value: A, another: B", string("mod failed: " + str(res_mod)))
        
        print("All ropes tests passed.")
    
    run_tests()
