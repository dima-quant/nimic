# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import *
from nimic.std.math import *
from nimic.std.formatfloat import *

#
#
#           The Nim Compiler
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

## Serialization utilities for the compiler.

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *

# bcc on windows doesn't have C99 functions
if comptime(defined("windows") and defined("bcc")):
    emit("""#if defined(_MSC_VER) && _MSC_VER < 1900
  #include <stdarg.h>
  static int c99_vsnprintf(char *outBuf, size_t size, const char *format, va_list ap) {
    int count = -1;
    if (size != 0) count = _vsnprintf_s(outBuf, size, _TRUNCATE, format, ap);
    if (count == -1) count = _vscprintf(format, ap);
    return count;
  }
  int snprintf(char *outBuf, size_t size, const char *format, ...) {
    int count;
    va_list ap;
    va_start(ap, format);
    count = c99_vsnprintf(outBuf, size, format, ap);
    va_end(ap);
    return count;
  }
  #endif
  """)

def _c_snprintf(s: cstring, n: uint, frmt: cstring) -> cint:
    """{.importc: "snprintf", header: "<stdio.h>", nodecl, varargs.}"""
    pass


if comptime(not declared("signbit")):
    def _c_signbit(x: SomeFloat) -> cint:
        """{.importc: "signbit", header: "<math.h>".}"""
        pass

    def signbit(x: SomeFloat) -> bool:
        """{.inline.}"""
        result = _c_signbit(x) != 0
        return result


def toStrMaxPrecision(f: BiggestFloat | float32) -> string:
    with const:
        literalPostfix = "f" if comptime(isinstance(f, float32)) else ""
    with let:
        c = classify(f)
    if c == fcNan:
        if signbit(f):
            result = string("-NAN")
        else:
            result = string("NAN")
    elif c == fcNegZero:
        result = string("-0.0")
        result.add(literalPostfix)
    elif c == fcZero:
        result = string("0.0")
        result.add(literalPostfix)
    elif c == fcInf:
        result = string("INF")
    elif c == fcNegInf:
        result = string("-INF")
    else:
        result = string("")
        result.addFloatRoundtrip(f)
        result.add(literalPostfix)
    return result



def encodeStr(s: string, result: mut @ string):
    for i in range(len(s)):
        with let:
            c = s[i]
        if (c >= char('a') and c <= char('z')) or (c >= char('A') and c <= char('Z')) or (c >= char('0') and c <= char('9')) or c == char('_'):
            result.add(c)
        else:
            result.add(char('\\'))
            result.add(toHex(ord(c), 2))


def _hexChar(c: char, xi: mut @ nint):
    if c >= char('0') and c <= char('9'):
        xi <<= (xi << 4) | (ord(c) - ord(char('0')))
    elif c >= char('a') and c <= char('f'):
        xi <<= (xi << 4) | (ord(c) - ord(char('a')) + 10)
    elif c >= char('A') and c <= char('F'):
        xi <<= (xi << 4) | (ord(c) - ord(char('A')) + 10)


def decodeStr(s: cstring, pos: mut @ nint) -> string:
    with var:
        i = pos.copy()
    result = string("")
    while True:
        with let:
            c = s[i]
        if c == char('\\'):
            i += 3
            with var:
                xi = nint(0)
            _hexChar(s[i - 2], xi)
            _hexChar(s[i - 1], xi)
            result.add(chr(int(xi)))
        elif (c >= char('a') and c <= char('z')) or (c >= char('A') and c <= char('Z')) or (c >= char('0') and c <= char('9')) or c == char('_'):
            result.add(c)
            i += 1
        else:
            break
    pos <<= i
    return result


with const:
    _chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

with push("overflowChecks: off"):
    # since negative numbers require a leading '-' they use up 1 byte. Thus we
    # subtract/add `vintDelta` here to save space for small negative numbers
    # which are common in ROD files:
    with const:
        _vintDelta = 5


    @template
    def _encodeIntImpl(self: untyped):
        with var:
            d = char('\0')
            v = x
            rem = v % 190
        if rem < 0:
            result.add(char('-'))
            v = -(v // 190)
            rem = -rem
        else:
            v = v // 190
        with var:
            idx = int(rem)
        if idx < 62:
            d = _chars[idx]
        else:
            d = chr(idx - 62 + 128)
        if v != 0:
            self(v, result)
        result.add(d)


    @template_expand
    def _encodeVBiggestIntAux(x: BiggestInt, result: mut @ string):
        """encode a biggest int as a variable length base 190 int."""
        _encodeIntImpl(_encodeVBiggestIntAux)


    def encodeVBiggestInt(x: BiggestInt, result: mut @ string):
        """encode a biggest int as a variable length base 190 int."""
        _encodeVBiggestIntAux(plus_percent(x, _vintDelta), result)
        #  encodeIntImpl(encodeVBiggestInt)


    @template_expand
    def _encodeVIntAux(x: nint, result: mut @ string):
        """encode an int as a variable length base 190 int."""
        _encodeIntImpl(_encodeVIntAux)


    def encodeVInt(x: nint, result: mut @ string):
        """encode an int as a variable length base 190 int."""
        _encodeVIntAux(plus_percent(x, _vintDelta), result)


    @template
    def _decodeIntImpl():
        with var:
            i = pos.copy()
            sign = -1
        with let:
            c0 = s[i]
        assert (c0 >= char('a') and c0 <= char('z')) or (c0 >= char('A') and c0 <= char('Z')) or (c0 >= char('0') and c0 <= char('9')) or c0 == char('-') or (ord(c0) >= 128 and ord(c0) <= 255)
        if c0 == char('-'):
            i += 1
            sign = 1
        result <<= 0
        while True:
            match s[i]:
                case _ if s[i] in inrange(char('0'), char('9')):
                    result = result * 190 - (ord(s[i]) - ord(char('0')))
                case _ if s[i] in inrange(char('a'), char('z')):
                    result = result * 190 - (ord(s[i]) - ord(char('a')) + 10)
                case _ if s[i] in inrange(char('A'), char('Z')):
                    result = result * 190 - (ord(s[i]) - ord(char('A')) + 36)
                case _ if s[i] in inrange(char('\x80'), char('\xFF')):
                    result = result * 190 - (ord(s[i]) - 128 + 62)
                case _:
                    break
            i += 1
        result = minus_percent(result * sign, _vintDelta)
        pos <<= i


    @template_expand
    def decodeVInt(s: cstring, pos: mut @ nint) -> nint:
        result = nint(0)
        _decodeIntImpl()
        return result


    @template_expand
    def decodeVBiggestInt(s: cstring, pos: mut @ nint) -> BiggestInt:
        result = BiggestInt(0)
        _decodeIntImpl()
        return result

def decodeVIntArray(s: cstring) -> nint:
    with var:
        i = nint(0)
    while s[i] != char('\0'):
        yield decodeVInt(s, i)
        if s[i] == char(' '):
            i += 1


def decodeStrArray(s: cstring) -> string:
    with var:
        i = nint(0)
    while s[i] != char('\0'):
        yield decodeStr(s, i)
        if s[i] == char(' '):
            i += 1


if comptime(__name__ == "__main__"):
    import math

    # 1. toStrMaxPrecision tests
    doAssert(toStrMaxPrecision(0.0) == string("0.0"))
    doAssert(toStrMaxPrecision(-0.0) == string("-0.0"))
    doAssert(toStrMaxPrecision(Inf) == string("INF"))
    doAssert(toStrMaxPrecision(-Inf) == string("-INF"))
    doAssert(toStrMaxPrecision(NaN) == string("NAN"))
    doAssert(toStrMaxPrecision(-NaN) == string("-NAN"))
    doAssert(toStrMaxPrecision(1.0) == string("1.0"))
    doAssert(toStrMaxPrecision(1.5) == string("1.5"))
    doAssert(toStrMaxPrecision(float32(0.0)) == string("0.0f"))
    doAssert(toStrMaxPrecision(float32(-0.0)) == string("-0.0f"))
    doAssert(toStrMaxPrecision(float32(1.5)) == string("1.5f"))
    doAssert(toStrMaxPrecision(float32(-1.5)) == string("-1.5f"))


    # 2. encodeStr / decodeStr tests
    with var:
        s_res = string("")
    encodeStr(string("hello_world_123"), s_res)
    doAssert(s_res == string("hello_world_123"))

    with var:
        p1 = nint(0)
    doAssert(decodeStr(cstring(s_res), p1) == string("hello_world_123"))
    doAssert(p1 == nint(len(s_res)))

    s_res.setLen(0)
    encodeStr(string("hello world!"), s_res)
    doAssert(s_res == string("hello\\20world\\21"))

    with var:
        p2 = nint(0)
    doAssert(decodeStr(cstring(s_res), p2) == string("hello world!"))
    doAssert(p2 == nint(len(s_res)))

    # 3. encodeVInt / decodeVInt roundtrip
    with var:
        v_buf = string("")
    with let:
        test_ints = [
            0, 1, -1, 4, 5, -5, -6, 42, -42, 189, 190, 191, -190, 1000, -1000, 1000000, -1000000
        ]
    for val in test_ints:
        v_buf.setLen(0)
        encodeVInt(val, v_buf)
        with var:
            pos_v = nint(0)
        with let:
            decoded_val = decodeVInt(cstring(v_buf), pos_v)
        doAssert(decoded_val == val)
        doAssert(pos_v == nint(len(v_buf)))

    # 4. encodeVBiggestInt / decodeVBiggestInt roundtrip
    with let:
        test_bigs = [
            0, 1, -1, 42, -42, 1000000, -1000000, 1 << 40, -(1 << 40)
        ]
    for val in test_bigs:
        v_buf.setLen(0)
        encodeVBiggestInt(val, v_buf)
        with var:
            pos_b = nint(0)
        with let:
            decoded_b = decodeVBiggestInt(cstring(v_buf), pos_b)
        doAssert(decoded_b == val)
        doAssert(pos_b == nint(len(v_buf)))

    # 5. decodeVIntArray test
    with var:
        arr_buf = string("")
    with let:
        sample_ints = [10, -5, 42, 100]
    for i in range(len(sample_ints)):
        if i > 0:
            arr_buf.add(char(' '))
        encodeVInt(sample_ints[i], arr_buf)

    with var:
        decoded_ints = seq[int]()
    for item in decodeVIntArray(cstring(arr_buf)):
        decoded_ints.add(int(item))
    doAssert(len(decoded_ints) == 4)
    doAssert(decoded_ints[0] == 10)
    doAssert(decoded_ints[1] == -5)
    doAssert(decoded_ints[2] == 42)
    doAssert(decoded_ints[3] == 100)

    # 6. decodeStrArray test
    with var:
        sarr_buf = string("")
    with let:
        sample_strs = [string("alpha"), string("beta gamma"), string("delta_1")]
    for i in range(len(sample_strs)):
        if i > 0:
            sarr_buf.add(char(' '))
        encodeStr(sample_strs[i], sarr_buf)

    with var:
        decoded_strs = seq[string]()
    for item in decodeStrArray(cstring(sarr_buf)):
        decoded_strs.add(item)
    doAssert(len(decoded_strs) == 3)
    doAssert(decoded_strs[0] == string("alpha"))
    doAssert(decoded_strs[1] == string("beta gamma"))
    doAssert(decoded_strs[2] == string("delta_1"))

    # 7. Empty array iteration tests
    with var:
        empty_ints = seq[int]()
    for item in decodeVIntArray(cstring("")):
        empty_ints.add(int(item))
    doAssert(len(empty_ints) == 0)

    with var:
        empty_strs = seq[string]()
    for item in decodeStrArray(cstring("")):
        empty_strs.add(item)
    doAssert(len(empty_strs) == 0)

    echo("SUCCESS: rodutils tests passed!")

