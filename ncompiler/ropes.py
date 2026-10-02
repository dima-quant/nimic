# /// nimic
#
#
#           The Nim Compiler
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# Ropes for the C code generator. Ropes are mapped to `string` directly nowadays.
# ///

from __future__ import annotations
from nimic.ntypes import *
from .pathutils import AbsoluteFile
from nimic.std.syncio import readBuffer, close, open, fmWrite, fmRead

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *
    from nimic.std.syncio import *
    from nimic.std.formatfloat import *

class FormatStr(string):
    # later we may change it to CString for better
    # performance of the code generator (assignments
    # copy the format strings
    # though it is not necessary)
    pass

class Rope(string):
    pass


def newRopeAppender(cap: nint = 80) -> string:
    """{.inline.}"""
    return newStringOfCap(cap)

def freeze(r: Rope) -> None:
    """{.inline.}"""
    discard

def resetRopeCache() -> None:
    discard

@template
def rope(s: string) -> Rope:
    return Rope(s)

@dispatch
def rope(i: BiggestInt) -> Rope:
    """## Converts an int to a rope."""
    return rope(string(str(i)))

@dispatch
def rope(f: BiggestFloat) -> Rope:
    """## Converts a float to a rope."""
    return rope(string(str(f)))

@dispatch
def writeRope(f: File, r: Rope) -> None:
    """## writes a rope to a file."""
    f.write(r)

@dispatch
def writeRope(head: Rope, filename: AbsoluteFile) -> bool:
    with var:
        f = default(File)
    if open(f, filename.string, fmWrite):
        writeRope(f, head)
        close(f)
        return True
    else:
        return False

def prepend(a: mut @ Rope, b: string) -> None:
    a <<= b + a


def runtimeFormat(frmt: FormatStr, args: openArray[Rope]) -> Rope:
    with var:
        i = 0
    result = newRopeAppender()
    with var:
        num = 0
    while i < len(frmt):
        if frmt[i] == ch('$'):
            i += 1
            if i >= len(frmt):
                raiseAssert(string("invalid format string: ") + frmt)
            if frmt[i] == ch('$'):
                result.add(string("$"))
                i += 1
            elif frmt[i] == ch('#'):
                i += 1
                result.add(args[num])
                num += 1
            elif frmt[i] >= ch('0') and frmt[i] <= ch('9'):
                with var:
                    j = 0
                while True:
                    j = j * 10 + ord(frmt[i]) - ord(ch('0'))
                    i += 1
                    if i >= len(frmt) or not (frmt[i] >= ch('0') and frmt[i] <= ch('9')):
                        break
                num = j
                if j > high(args) + 1:
                    raiseAssert(string("invalid format string: ") + frmt)
                else:
                    result.add(args[j - 1])
            elif frmt[i] == ch('{'):
                i += 1
                with var:
                    j = 0
                while i < len(frmt) and frmt[i] >= ch('0') and frmt[i] <= ch('9'):
                    j = j * 10 + ord(frmt[i]) - ord(ch('0'))
                    i += 1
                num = j
                if i < len(frmt) and frmt[i] == ch('}'):
                    i += 1
                else:
                    raiseAssert(string("invalid format string: ") + frmt)

                if j > high(args) + 1:
                    raiseAssert(string("invalid format string: ") + frmt)
                else:
                    result.add(args[j - 1])
            elif frmt[i] == ch('n'):
                result.add(string("\n"))
                i += 1
            elif frmt[i] == ch('N'):
                result.add(string("\n"))
                i += 1
            else:
                raiseAssert(string("invalid format string: ") + frmt)
        else:
            result.add(frmt[i])
            i += 1
    return result

def __mod__(frmt: static[FormatStr], args: openArray[Rope]) -> Rope:
    return runtimeFormat(frmt, args)

FormatStr.__mod__ = __mod__

@template
def addf(c: mut @ Rope, frmt: FormatStr, args: openArray[Rope]) -> untyped:
    """## shortcut for ``add(c, frmt % args)``."""
    c.add(frmt % args)

with const:
    _bufSize = 1024

@dispatch
def equalsFile(s: Rope, f: File) -> bool:
    """## returns true if the contents of the file `f` equal `r`."""
    with var:
        buf = default(array[_bufSize, char])
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
                    return False
            with let:
                n = min(blen - bpos, len(s) - spos)
            if not equalMem(addr(buf[bpos]), cast[pointer](cast[intp](cstring(s)) + spos), n):
                return False
            spos += n
            bpos += n

    return readBuffer(f, addr(buf[0]), 1) == 0 and btotal == rtotal

@dispatch
def equalsFile(r: Rope, filename: AbsoluteFile) -> bool:
    """## returns true if the contents of the file `f` equal `r`. If `f` does not exist, false is returned."""
    with var:
        f = default(File)
    result = open(f, filename.string)
    if result:
        result = equalsFile(r, f)
        close(f)
    return result

if comptime(__name__ == "__main__"):
    from nimic.std.os import removeFile, fileExists
    from nimic.std.strutils import repeat

    # 1. newRopeAppender, freeze, resetRopeCache
    with var:
        app = newRopeAppender(50)
    assert len(app) == 0
    freeze(rope(string("test")))
    resetRopeCache()

    # 2. Basic rope conversions
    with var:
        r1 = rope(string("Hello"))
        r2 = rope(BiggestInt(123))
        r2_i64 = rope(int64(456))
        r2_neg = rope(BiggestInt(-999))
        r3 = rope(BiggestFloat(45.67))
        r3_f64 = rope(float64(89.01))
    assert str(r1) == "Hello"
    assert str(r2) == "123"
    assert str(r2_i64) == "456"
    assert str(r2_neg) == "-999"
    assert str(r3) == "45.67"
    assert str(r3_f64) == "89.01"

    # 3. Prepend
    with var:
        r_prep = rope(string("world"))
    prepend(r_prep, string("Hello "))
    assert str(r_prep) == "Hello world"

    # 4. runtimeFormat and % operator
    with var:
        f_str = FormatStr("Value: $1, another: $2")
        res = runtimeFormat(f_str, [rope(string("A")), rope(string("B"))])
    assert str(res) == "Value: A, another: B"

    with var:
        res_mod = FormatStr("Value: $1, another: $2") % [rope(string("A")), rope(string("B"))]
    assert str(res_mod) == "Value: A, another: B"

    # Auto-increment format $#
    with var:
        res_auto = FormatStr("$# + $# = $#") % [rope(string("1")), rope(string("2")), rope(string("3"))]
    assert str(res_auto) == "1 + 2 = 3"

    # Escaped $$
    with var:
        res_esc = FormatStr("Cost is $$5") % []
    assert str(res_esc) == "Cost is $5"

    # Bracket format ${1}
    with var:
        res_bracket = FormatStr("Item: ${1}") % [rope(string("Widget"))]
    assert str(res_bracket) == "Item: Widget"

    # Multi-digit specifiers: $10 and ${10}
    with var:
        ten_args = [
            rope(string("1")), rope(string("2")), rope(string("3")),
            rope(string("4")), rope(string("5")), rope(string("6")),
            rope(string("7")), rope(string("8")), rope(string("9")),
            rope(string("10")), rope(string("11"))
        ]
        res_multi = FormatStr("tenth is $10 and eleventh is ${11}") % ten_args
    assert str(res_multi) == "tenth is 10 and eleventh is 11"

    # Newlines $n and $N
    with var:
        res_nl = FormatStr("Line 1$nLine 2$NLine 3") % []
    assert str(res_nl) == "Line 1\nLine 2\nLine 3"

    # Empty format string
    assert str(FormatStr("") % []) == ""

    # Plain format string without specifiers
    assert str(FormatStr("Just some plain text") % []) == "Just some plain text"

    # Consecutive specifiers
    with var:
        f_consec = FormatStr("$1$2$3")
    assert str(f_consec % [rope(string("X")), rope(string("Y")), rope(string("Z"))]) == "XYZ"

    # addf template
    with var:
        accum = Rope(string("Start: "))
    addf(accum, FormatStr("$1 $2"), [rope(string("Alpha")), rope(string("Beta"))])
    assert str(accum) == "Start: Alpha Beta"

    # 5. Error conditions for runtimeFormat
    with var:
        raised = False
    try:
        _ = FormatStr("too high: $5") % [rope(string("A")), rope(string("B"))]
    except Exception:
        raised = True
    assert raised, "Expected exception for index > args length"

    raised = False
    try:
        _ = FormatStr("too high: ${5}") % [rope(string("A")), rope(string("B"))]
    except Exception:
        raised = True
    assert raised, "Expected exception for ${index} > args length"

    raised = False
    try:
        _ = FormatStr("trailing $") % []
    except Exception:
        raised = True
    assert raised, "Expected exception for trailing $"

    raised = False
    try:
        _ = FormatStr("unclosed ${1") % [rope(string("A"))]
    except Exception:
        raised = True
    assert raised, "Expected exception for unclosed ${"

    raised = False
    try:
        _ = FormatStr("invalid $z") % []
    except Exception:
        raised = True
    assert raised, "Expected exception for invalid specifier $z"

    # 6. File I/O operations
    with var:
        tmp_path = string(".scratch/test_rope_tmp.txt")
        abs_file = AbsoluteFile(tmp_path)
        test_rope = Rope(string("Rope content for file test\nLine 2"))
    assert writeRope(test_rope, abs_file) == True
    assert equalsFile(test_rope, abs_file) == True
    assert equalsFile(Rope(string("Different content")), abs_file) == False

    with var:
        f_direct = default(File)
    assert open(f_direct, tmp_path, fmWrite) == True
    writeRope(f_direct, Rope(string("Direct File write")))
    close(f_direct)

    assert open(f_direct, tmp_path, fmRead) == True
    assert equalsFile(Rope(string("Direct File write")), f_direct) == True
    close(f_direct)

    with var:
        large_content = repeat(string("X"), 2500)
        large_rope = Rope(large_content)
    assert writeRope(large_rope, abs_file) == True
    assert equalsFile(large_rope, abs_file) == True

    with var:
        diff_in_buf2 = Rope(repeat(string("X"), 1500) + string("Y") + repeat(string("X"), 999))
    assert equalsFile(diff_in_buf2, abs_file) == False

    with var:
        shorter_rope = Rope(repeat(string("X"), 2400))
    assert equalsFile(shorter_rope, abs_file) == False

    with var:
        longer_rope = Rope(repeat(string("X"), 2600))
    assert equalsFile(longer_rope, abs_file) == False

    # Non-existent file operations
    with var:
        non_existent = AbsoluteFile(string("/nonexistent_dir_12345/no_such_file.txt"))
    assert equalsFile(test_rope, non_existent) == False
    assert writeRope(test_rope, non_existent) == False

    if fileExists(tmp_path):
        removeFile(tmp_path)

    echo("All ropes tests passed.")
