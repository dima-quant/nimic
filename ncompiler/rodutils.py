# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import toHex
from nimic.std.math import (
    classify,
    signbit,
    fcNan,
    fcNegZero,
    fcZero,
    fcInf,
    fcNegInf,
    Inf,
    NaN,
)
from nimic.std.formatfloat import addFloatRoundtrip

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


def toStrMaxPrecision(f: BiggestFloat | float32) -> string:
    with var:
        literalPostfix = ""
    if isinstance(f, float32):
        literalPostfix = "f"
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
        if (c >= ch('a') and c <= ch('z')) or (c >= ch('A') and c <= ch('Z')) or (c >= ch('0') and c <= ch('9')) or c == ch('_'):
            result.add(c)
        else:
            result.add(ch('\\'))
            result.add(toHex(ord(c), 2))


def _hexChar(c: char, xi: mut @ nint):
    if c >= ch('0') and c <= ch('9'):
        xi <<= (xi << 4) | (ord(c) - ord(ch('0')))
    elif c >= ch('a') and c <= ch('f'):
        xi <<= (xi << 4) | (ord(c) - ord(ch('a')) + 10)
    elif c >= ch('A') and c <= ch('F'):
        xi <<= (xi << 4) | (ord(c) - ord(ch('A')) + 10)


def decodeStr(s: cstring, pos: mut @ nint) -> string:
    with var:
        i = nint(pos)
    result = string("")
    while True:
        with let:
            c = s[i]
        if c == ch('\\'):
            i += 3
            with var:
                xi = nint(0)
            _hexChar(s[i - 2], xi)
            _hexChar(s[i - 1], xi)
            result.add(chr(int(xi)))
        elif (c >= ch('a') and c <= ch('z')) or (c >= ch('A') and c <= ch('Z')) or (c >= ch('0') and c <= ch('9')) or c == ch('_'):
            result.add(c)
            i += 1
        else:
            break
    pos <<= i
    return result


with const:
    _chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    _vintDelta = 5


def _encodeVBiggestIntAux(x: BiggestInt, result: mut @ string):
    """encode a biggest int as a variable length base 190 int."""
    with var:
        d = ch('\0')
        v = x
        rem = v % 190
    if rem < 0:
        result.add(ch('-'))
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
        _encodeVBiggestIntAux(v, result)
    result.add(d)


def encodeVBiggestInt(x: BiggestInt, result: mut @ string):
    """encode a biggest int as a variable length base 190 int."""
    _encodeVBiggestIntAux(plus_percent(x, _vintDelta), result)


def _encodeVIntAux(x: nint, result: mut @ string):
    """encode an int as a variable length base 190 int."""
    with var:
        d = ch('\0')
        v = x
        rem = v % 190
    if rem < 0:
        result.add(ch('-'))
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
        _encodeVIntAux(v, result)
    result.add(d)


def encodeVInt(x: nint, result: mut @ string):
    """encode an int as a variable length base 190 int."""
    _encodeVIntAux(plus_percent(x, _vintDelta), result)


def decodeVInt(s: cstring, pos: mut @ nint) -> nint:
    with var:
        i = nint(pos)
        sign = -1
    result = nint(0)
    with let:
        c0 = s[i]
    assert (c0 >= ch('a') and c0 <= ch('z')) or (c0 >= ch('A') and c0 <= ch('Z')) or (c0 >= ch('0') and c0 <= ch('9')) or c0 == ch('-') or (ord(c0) >= 128 and ord(c0) <= 255)
    if c0 == ch('-'):
        i += 1
        sign = 1
    while True:
        with let:
            c = s[i]
        if c >= ch('0') and c <= ch('9'):
            result = result * 190 - (ord(c) - ord(ch('0')))
        elif c >= ch('a') and c <= ch('z'):
            result = result * 190 - (ord(c) - ord(ch('a')) + 10)
        elif c >= ch('A') and c <= ch('Z'):
            result = result * 190 - (ord(c) - ord(ch('A')) + 36)
        elif ord(c) >= 128 and ord(c) <= 255:
            result = result * 190 - (ord(c) - 128 + 62)
        else:
            break
        i += 1
    result = minus_percent(result * sign, _vintDelta)
    pos <<= i
    return result


def decodeVBiggestInt(s: cstring, pos: mut @ nint) -> BiggestInt:
    with var:
        i = nint(pos)
        sign = -1
    result = BiggestInt(0)
    with let:
        c0 = s[i]
    assert (c0 >= ch('a') and c0 <= ch('z')) or (c0 >= ch('A') and c0 <= ch('Z')) or (c0 >= ch('0') and c0 <= ch('9')) or c0 == ch('-') or (ord(c0) >= 128 and ord(c0) <= 255)
    if c0 == ch('-'):
        i += 1
        sign = 1
    while True:
        with let:
            c = s[i]
        if c >= ch('0') and c <= ch('9'):
            result = result * 190 - (ord(c) - ord(ch('0')))
        elif c >= ch('a') and c <= ch('z'):
            result = result * 190 - (ord(c) - ord(ch('a')) + 10)
        elif c >= ch('A') and c <= ch('Z'):
            result = result * 190 - (ord(c) - ord(ch('A')) + 36)
        elif ord(c) >= 128 and ord(c) <= 255:
            result = result * 190 - (ord(c) - 128 + 62)
        else:
            break
        i += 1
    result = minus_percent(result * sign, _vintDelta)
    pos <<= i
    return result




def decodeVIntArray(s: cstring) -> nint:
    with var:
        i = nint(0)
    while s[i] != ch('\0'):
        yield decodeVInt(s, i)
        if s[i] == ch(' '):
            i += 1


def decodeStrArray(s: cstring) -> string:
    with var:
        i = nint(0)
    while s[i] != ch('\0'):
        yield decodeStr(s, i)
        if s[i] == ch(' '):
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
            arr_buf.add(ch(' '))
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
            sarr_buf.add(ch(' '))
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

