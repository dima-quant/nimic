# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *

## This module is for compiler internal use only. For reliable error
## messages and range checks, the compiler needs a data type that can
## hold all from `low(BiggestInt)` to `high(BiggestUInt)`, This
## type is for that purpose.

importFrom("nimic.std.math", "trunc")

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *


class Int128(Object):
    _udata: array[4, uint32]

    @template
    def _sdata(arg: Int128, idx: nint) -> int32:
        # udata and sdata was supposed to be in a union, but unions are
        # handled incorrectly in the VM.
        return cast[ptr[int32]](unsafe_addr(arg._udata[idx])).contents

    @template
    def _isNegative(arg: Int128) -> bool:
        return arg._sdata(3) < 0

    def toInt32(arg: Int128) -> int32:
        if arg._isNegative():
            assert arg._sdata(3) == -1, "out of range"
            assert arg._sdata(2) == -1, "out of range"
            assert arg._sdata(1) == -1, "out of range"
        else:
            assert arg._sdata(3) == 0, "out of range"
            assert arg._sdata(2) == 0, "out of range"
            assert arg._sdata(1) == 0, "out of range"

        return arg._sdata(0)

    def toInt16(arg: Int128) -> int16:
        if arg._isNegative():
            assert arg._sdata(3) == -1, "out of range"
            assert arg._sdata(2) == -1, "out of range"
            assert arg._sdata(1) == -1, "out of range"
        else:
            assert arg._sdata(3) == 0, "out of range"
            assert arg._sdata(2) == 0, "out of range"
            assert arg._sdata(1) == 0, "out of range"

        return int16(arg._sdata(0))

    def toInt8(arg: Int128) -> int8:
        if arg._isNegative():
            assert arg._sdata(3) == -1, "out of range"
            assert arg._sdata(2) == -1, "out of range"
            assert arg._sdata(1) == -1, "out of range"
        else:
            assert arg._sdata(3) == 0, "out of range"
            assert arg._sdata(2) == 0, "out of range"
            assert arg._sdata(1) == 0, "out of range"

        return int8(arg._sdata(0))

    def toUInt32(arg: Int128) -> uint32:
        assert arg._udata[3] == 0
        assert arg._udata[2] == 0
        assert arg._udata[1] == 0
        return arg._udata[0]

    def toUInt16(arg: Int128) -> uint16:
        assert arg._udata[3] == 0
        assert arg._udata[2] == 0
        assert arg._udata[1] == 0
        return uint16(arg._udata[0])

    def toUInt8(arg: Int128) -> uint8:
        assert arg._udata[3] == 0
        assert arg._udata[2] == 0
        assert arg._udata[1] == 0
        return uint8(arg._udata[0])

    def inc(a: mut @ Int128, y: uint32 = u32(1)):
        a._udata[0] += y
        if unlikely(a._udata[0] < y):
            a._udata[1] += 1
            if unlikely(a._udata[1] == 0):
                a._udata[2] += 1
                if unlikely(a._udata[2] == 0):
                    a._udata[3] += 1
                    doAssert(a._sdata(3) != low(int32), "overflow")

    def cmp(a: Int128, b: Int128) -> nint:
        with let:
            tmp1 = cmp(a._sdata(3), b._sdata(3))
        if tmp1 != 0: return tmp1
        with let:
            tmp2 = cmp(a._udata[2], b._udata[2])
        if tmp2 != 0: return tmp2
        with let:
            tmp3 = cmp(a._udata[1], b._udata[1])
        if tmp3 != 0: return tmp3
        with let:
            tmp4 = cmp(a._udata[0], b._udata[0])
        return tmp4

    def __lt__(a: Int128, b: Int128) -> bool:
        return a.cmp(b) < 0

    def __le__(a: Int128, b: Int128) -> bool:
        return a.cmp(b) <= 0

    def __eq__(a: Int128, b: Int128) -> bool:
        if a._udata[0] != b._udata[0]: return False
        if a._udata[1] != b._udata[1]: return False
        if a._udata[2] != b._udata[2]: return False
        if a._udata[3] != b._udata[3]: return False
        return True


# encoding least significant int first (like LittleEndian)

with const:
    Zero = Int128(_udata=[u32(0), 0, 0, 0])
    One = Int128(_udata=[u32(1), 0, 0, 0])
    Ten = Int128(_udata=[u32(10), 0, 0, 0])
    _Min = Int128(_udata=[u32(0), 0, 0, u32(0x80000000)])
    _Max = Int128(_udata=[high(uint32), high(uint32), high(uint32), uint32(high(int32))])
    NegOne = Int128(_udata=[u32(0xffffffff), u32(0xffffffff), u32(0xffffffff), u32(0xffffffff)])


@template
def low(t: typedesc[Int128]) -> Int128:
    return _Min


@template
def high(t: typedesc[Int128]) -> Int128:
    return _Max


@ufcs(Int128)
def __str__(a: Int128) -> string:
    pass


@dispatch
def toInt128[T: SomeInteger | bool](arg: T) -> Int128:
    with pragma("noSideEffect"):
        result = Zero.copy()
        if comptime(issubclass(T, bool)):
            assign(result._sdata(0), int32(arg))
        elif comptime(issubclass(T, SomeUnsignedInt)):
            if comptime(sizeof(arg) <= 4):
                result._udata[0] = uint32(arg)
            else:
                result._udata[0] = uint32(arg & T(0xffffffff))
                result._udata[1] = uint32(arg >> 32)
        elif comptime(sizeof(arg) <= 4):
            assign(result._sdata(0), int32(arg))
            if arg < 0:  # sign extend
                assign(result._sdata(1), int32(-1))
                assign(result._sdata(2), int32(-1))
                assign(result._sdata(3), int32(-1))
        else:
            with let:
                tmp = int64(arg)
            result._udata[0] = uint32(tmp & 0xffffffff)
            assign(result._sdata(1), int32(tmp >> 32))
            if arg < 0:  # sign extend
                assign(result._sdata(2), int32(-1))
                assign(result._sdata(3), int32(-1))
    return result


def _bitconcat(a: uint32, b: uint32) -> uint64:
    return (uint64(a) << 32) | uint64(b)


def toInt64(arg: Int128) -> int64:
    if arg._isNegative():
        assert arg._sdata(3) == -1, "out of range"
        assert arg._sdata(2) == -1, "out of range"
    else:
        assert arg._sdata(3) == 0, "out of range"
        assert arg._sdata(2) == 0, "out of range"

    return cast[int64](_bitconcat(arg._udata[1], arg._udata[0]))


def toInt64Checked(arg: Int128, onError: int64) -> int64:
    if arg._isNegative():
        if arg._sdata(3) != -1 or arg._sdata(2) != -1:
            return onError
    else:
        if arg._sdata(3) != 0 or arg._sdata(2) != 0:
            return onError
    return cast[int64](_bitconcat(arg._udata[1], arg._udata[0]))


def toInt(arg: Int128) -> nint:
    if comptime(sizeof(nint) == 4):
        return cast[nint](arg.toInt32())
    else:
        return cast[nint](toInt64(arg))


def toUInt64(arg: Int128) -> uint64:
    assert arg._udata[3] == 0
    assert arg._udata[2] == 0
    return _bitconcat(arg._udata[1], arg._udata[0])


def toUInt(arg: Int128) -> uint:
    if comptime(sizeof(nint) == 4):
        return cast[uint](arg.toInt32())
    else:
        return cast[uint](toInt64(arg))


def castToInt64(arg: Int128) -> int64:
    ## Conversion to int64 without range check.
    return cast[int64](_bitconcat(arg._udata[1], arg._udata[0]))


def castToUInt64(arg: Int128) -> uint64:
    ## Conversion to uint64 without range check.
    return cast[uint64](_bitconcat(arg._udata[1], arg._udata[0]))


# Nim: proc addToHex(result: var string; arg: uint32), a private overload of the exported addToHex
def _addToHex(result: mut @ string, arg: uint32):
    for i in range(8):
        with let:
            idx = (arg >> ((7 - i) * 4)) & 0xf
        result.add(string("0123456789abcdef")[idx])


def addToHex(result: mut @ string, arg: Int128):
    with var:
        i = 3
    while i >= 0:
        _addToHex(result, arg._udata[i])
        i -= 1


def toHex(arg: Int128) -> string:
    result = string("")
    addToHex(result, arg)
    return result


@dispatch
def bitnot(a: Int128) -> Int128:
    result = Zero.copy()
    result._udata[0] = ~a._udata[0]
    result._udata[1] = ~a._udata[1]
    result._udata[2] = ~a._udata[2]
    result._udata[3] = ~a._udata[3]
    return result


@dispatch
def bitand(a: Int128, b: Int128) -> Int128:
    result = Zero.copy()
    result._udata[0] = a._udata[0] & b._udata[0]
    result._udata[1] = a._udata[1] & b._udata[1]
    result._udata[2] = a._udata[2] & b._udata[2]
    result._udata[3] = a._udata[3] & b._udata[3]
    return result


@dispatch
def bitor(a: Int128, b: Int128) -> Int128:
    result = Zero.copy()
    result._udata[0] = a._udata[0] | b._udata[0]
    result._udata[1] = a._udata[1] | b._udata[1]
    result._udata[2] = a._udata[2] | b._udata[2]
    result._udata[3] = a._udata[3] | b._udata[3]
    return result


@dispatch
def bitxor(a: Int128, b: Int128) -> Int128:
    result = Zero.copy()
    result._udata[0] = a._udata[0] ^ b._udata[0]
    result._udata[1] = a._udata[1] ^ b._udata[1]
    result._udata[2] = a._udata[2] ^ b._udata[2]
    result._udata[3] = a._udata[3] ^ b._udata[3]
    return result


@ufcs(Int128)
def __rshift__(a: Int128, b: nint) -> Int128:
    result = Zero.copy()
    with let:
        b = b & 127
    if b < 32:
        assign(result._sdata(3), a._sdata(3) >> b)
        result._udata[2] = cast[uint32](_bitconcat(a._udata[3], a._udata[2]) >> b)
        result._udata[1] = cast[uint32](_bitconcat(a._udata[2], a._udata[1]) >> b)
        result._udata[0] = cast[uint32](_bitconcat(a._udata[1], a._udata[0]) >> b)
    elif b < 64:
        if a._isNegative():
            assign(result._sdata(3), int32(-1))
        assign(result._sdata(2), a._sdata(3) >> (b & 31))
        result._udata[1] = cast[uint32](_bitconcat(a._udata[3], a._udata[2]) >> (b & 31))
        result._udata[0] = cast[uint32](_bitconcat(a._udata[2], a._udata[1]) >> (b & 31))
    elif b < 96:
        if a._isNegative():
            assign(result._sdata(3), int32(-1))
            assign(result._sdata(2), int32(-1))
        assign(result._sdata(1), a._sdata(3) >> (b & 31))
        result._udata[0] = cast[uint32](_bitconcat(a._udata[3], a._udata[2]) >> (b & 31))
    else:  # b < 128
        if a._isNegative():
            assign(result._sdata(3), int32(-1))
            assign(result._sdata(2), int32(-1))
            assign(result._sdata(1), int32(-1))
        assign(result._sdata(0), a._sdata(3) >> (b & 31))
    return result


@ufcs(Int128)
def __lshift__(a: Int128, b: nint) -> Int128:
    result = Zero.copy()
    with let:
        b = b & 127
    if b < 32:
        result._udata[0] = a._udata[0] << b
        result._udata[1] = cast[uint32]((_bitconcat(a._udata[1], a._udata[0]) << b) >> 32)
        result._udata[2] = cast[uint32]((_bitconcat(a._udata[2], a._udata[1]) << b) >> 32)
        result._udata[3] = cast[uint32]((_bitconcat(a._udata[3], a._udata[2]) << b) >> 32)
    elif b < 64:
        result._udata[0] = 0
        result._udata[1] = a._udata[0] << (b & 31)
        result._udata[2] = cast[uint32]((_bitconcat(a._udata[1], a._udata[0]) << (b & 31)) >> 32)
        result._udata[3] = cast[uint32]((_bitconcat(a._udata[2], a._udata[1]) << (b & 31)) >> 32)
    elif b < 96:
        result._udata[0] = 0
        result._udata[1] = 0
        result._udata[2] = a._udata[0] << (b & 31)
        result._udata[3] = cast[uint32]((_bitconcat(a._udata[1], a._udata[0]) << (b & 31)) >> 32)
    else:
        result._udata[0] = 0
        result._udata[1] = 0
        result._udata[2] = 0
        result._udata[3] = a._udata[0] << (b & 31)
    return result


@ufcs(Int128)
@dispatch
def __add__(a: Int128, b: Int128) -> Int128:
    result = Zero.copy()
    with let:
        tmp0 = uint64(a._udata[0]) + uint64(b._udata[0])
    result._udata[0] = cast[uint32](tmp0)
    with let:
        tmp1 = uint64(a._udata[1]) + uint64(b._udata[1]) + (tmp0 >> 32)
    result._udata[1] = cast[uint32](tmp1)
    with let:
        tmp2 = uint64(a._udata[2]) + uint64(b._udata[2]) + (tmp1 >> 32)
    result._udata[2] = cast[uint32](tmp2)
    with let:
        tmp3 = uint64(a._udata[3]) + uint64(b._udata[3]) + (tmp2 >> 32)
    result._udata[3] = cast[uint32](tmp3)
    return result


@ufcs(Int128)
def __iadd__(a: mut @ Int128, b: Int128):
    a <<= a + b
    return a


@ufcs(Int128)
def __neg__(a: Int128) -> Int128:
    result = bitnot(a)
    result.inc()
    return result


@ufcs(Int128)
@dispatch
def __sub__(a: Int128, b: Int128) -> Int128:
    return a + (-b)


@ufcs(Int128)
def __isub__(a: mut @ Int128, b: Int128):
    a <<= a - b
    return a


@dispatch
def abs(a: Int128) -> Int128:
    if a._isNegative():
        return -a
    else:
        return a


def _abs(a: int32) -> nint:
    return nint(-a) if a < 0 else nint(a)  # -a in int32, as Nim (abs(low(int32)) overflows)


@ufcs(Int128)
@dispatch
def __mul__(a: Int128, b: uint32) -> Int128:
    """{.private.}"""
    result = Zero.copy()
    with let:
        tmp0 = uint64(a._udata[0]) * uint64(b)
        tmp1 = uint64(a._udata[1]) * uint64(b)
        tmp2 = uint64(a._udata[2]) * uint64(b)
        tmp3 = uint64(a._udata[3]) * uint64(b)

    if unlikely(tmp3 > uint64(high(int32))):
        assert False, "overflow"

    result._udata[0] = cast[uint32](tmp0)
    result._udata[1] = cast[uint32](tmp1) + cast[uint32](tmp0 >> 32)
    result._udata[2] = cast[uint32](tmp2) + cast[uint32](tmp1 >> 32)
    result._udata[3] = cast[uint32](tmp3) + cast[uint32](tmp2 >> 32)
    return result


@ufcs(Int128)
@dispatch
def __mul__(a: Int128, b: int32) -> Int128:
    result = a * cast[uint32](_abs(b))
    if b < 0:
        result = -result
    return result


@ufcs(Int128)
@dispatch
def __imul__(a: mut @ Int128, b: int32):
    """{.private.}"""
    a <<= a * b
    return a


def _makeInt128(high: uint64, low: uint64) -> Int128:
    result = Zero.copy()
    result._udata[0] = cast[uint32](low)
    result._udata[1] = cast[uint32](low >> 32)
    result._udata[2] = cast[uint32](high)
    result._udata[3] = cast[uint32](high >> 32)
    return result


def _high64(a: Int128) -> uint64:
    return _bitconcat(a._udata[3], a._udata[2])


def _low64(a: Int128) -> uint64:
    return _bitconcat(a._udata[1], a._udata[0])


@ufcs(Int128)
@dispatch
def __mul__(lhs: Int128, rhs: Int128) -> Int128:
    with let:
        a32 = uint64(lhs._udata[1])
        a00 = uint64(lhs._udata[0])
        b32 = uint64(rhs._udata[1])
        b00 = uint64(rhs._udata[0])
    result = _makeInt128(_high64(lhs) * _low64(rhs) + _low64(lhs) * _high64(rhs) + a32 * b32, a00 * b00)
    result += toInt128(a32 * b00) << 32
    result += toInt128(a00 * b32) << 32
    return result


@ufcs(Int128)
@dispatch
def __imul__(a: mut @ Int128, b: Int128):
    a <<= a * b
    return a


from nimic.std.bitops import *


@dispatch
def fastLog2(a: Int128) -> nint:
    result = 0
    if a._udata[3] != 0:
        return 96 + fastLog2(a._udata[3])
    if a._udata[2] != 0:
        return 64 + fastLog2(a._udata[2])
    if a._udata[1] != 0:
        return 32 + fastLog2(a._udata[1])
    if a._udata[0] != 0:
        return fastLog2(a._udata[0])
    return result


class _DivModResult(NTuple):
    quotient: Int128
    remainder: Int128


def divMod(dividend: Int128, divisor: Int128) -> _DivModResult:
    assert divisor != Zero
    result = _DivModResult(quotient=Zero, remainder=Zero)  # Nim: result = (Zero, Zero)

    with let:
        isNegativeA = dividend._isNegative()
        isNegativeB = divisor._isNegative()

    with var:
        dividend = abs(dividend).copy()
    with let:
        divisor = abs(divisor)

    if divisor > dividend:
        result.quotient = Zero
        if isNegativeA:
            result.remainder = -dividend
        else:
            result.remainder = dividend
        return result

    if divisor == dividend:
        if isNegativeA ^ isNegativeB:
            result.quotient = NegOne
        else:
            result.quotient = One
        result.remainder = Zero
        return result

    with var:
        denominator = divisor
    with var:
        quotient = Zero

    # Left aligns the MSB of the denominator and the dividend.
    with let:
        shift = fastLog2(dividend) - fastLog2(denominator)
    denominator = denominator << shift

    # Uses shift-subtract algorithm to divide dividend by denominator. The
    # remainder will be left in dividend.
    for i in inrange(0, shift):
        quotient = quotient << 1
        if dividend >= denominator:
            dividend -= denominator
            quotient = bitor(quotient, One)

        denominator = denominator >> 1

    if isNegativeA ^ isNegativeB:
        result.quotient = -quotient
    else:
        result.quotient = quotient
    if isNegativeA:
        result.remainder = -dividend
    else:
        result.remainder = dividend
    return result


@ufcs(Int128)
def __floordiv__(a: Int128, b: Int128) -> Int128:
    with let:
        (a, _) = divMod(a, b)
    return a


@ufcs(Int128)
def __mod__(a: Int128, b: Int128) -> Int128:
    with let:
        (_, b) = divMod(a, b)
    return b


def addInt128(result: mut @ string, value: Int128):
    with let:
        initialSize = result.len
    if value == Zero:
        result.add(ch('0'))
    elif value == low(Int128):
        result.add(string("-170141183460469231731687303715884105728"))
    else:
        with let:
            isNegative = value._isNegative()
        with var:
            value = abs(value)
        while value > Zero:
            with let:
                (quot, rem) = divMod(value, Ten)
            result.add(string("0123456789")[toInt64(rem)])
            value = quot
        if isNegative:
            result.add(ch('-'))

        with var:
            i = initialSize
            j = high(result)
        while i < j:
            with let:
                tmp = result[i]
            result[i] = result[j]
            result[j] = tmp
            i += 1
            j -= 1


@ufcs(Int128)
def __str__(a: Int128) -> string:
    # "-170141183460469231731687303715884105728".len == 41
    result = newStringOfCap(41)
    addInt128(result, a)
    return result


def parseDecimalInt128(arg: string, pos: nint = 0) -> Int128:
    assert pos < arg.len
    assert arg[pos] in Tset[char]({ch('-'), inrange(ch('0'), ch('9'))})

    with var:
        isNegative = False
    with var:
        pos = nint(pos)  # a copy (a literal default has no .copy())
    if arg[pos] == ch('-'):
        isNegative = True
        pos += 1

    result = Zero.copy()
    while pos < arg.len and arg[pos] in inrange(ch('0'), ch('9')):
        result = result * Ten
        result.inc(uint32(arg[pos]) - uint32(ch('0')))
        pos += 1

    if isNegative:
        result = -result
    return result

# fluff

@ufcs(Int128)
@dispatch
def __lt__(a: Int128, b: BiggestInt) -> bool:
    return a.cmp(toInt128(b)) < 0


@ufcs(Int128)
@dispatch
def __lt__(a: BiggestInt, b: Int128) -> bool:
    return toInt128(a).cmp(b) < 0


@ufcs(Int128)
@dispatch
def __le__(a: Int128, b: BiggestInt) -> bool:
    return a.cmp(toInt128(b)) <= 0


@ufcs(Int128)
@dispatch
def __le__(a: BiggestInt, b: Int128) -> bool:
    return toInt128(a).cmp(b) <= 0


@ufcs(Int128)
@dispatch
def __eq__(a: Int128, b: BiggestInt) -> bool:
    return a == toInt128(b)


@ufcs(Int128)
@dispatch
def __eq__(a: BiggestInt, b: Int128) -> bool:
    return toInt128(a) == b


@ufcs(Int128)
@dispatch
def __sub__(a: BiggestInt, b: Int128) -> Int128:
    return toInt128(a) - b


@ufcs(Int128)
@dispatch
def __sub__(a: Int128, b: BiggestInt) -> Int128:
    return a - toInt128(b)


@ufcs(Int128)
@dispatch
def __add__(a: BiggestInt, b: Int128) -> Int128:
    return toInt128(a) + b


@ufcs(Int128)
@dispatch
def __add__(a: Int128, b: BiggestInt) -> Int128:
    return a + toInt128(b)


def toFloat64(arg: Int128) -> float64:
    with let:
        isNegative = arg._isNegative()
    with let:
        arg = abs(arg)

    with let:
        a = float64(_bitconcat(arg._udata[1], arg._udata[0]))
    with let:
        b = float64(_bitconcat(arg._udata[3], arg._udata[2]))

    result = a + f64(18446744073709551616.0) * b  # a + 2^64 * b
    if isNegative:
        result = -result
    return result


@importc
def _ldexp(x: float64, exp: cint) -> float64:
    """{.importc: "ldexp", header: "<math.h>".}"""
    pass


@template
def _bitor(a: Int128, b: Int128, c: Int128) -> Int128:
    return bitor(bitor(a, b), c)


@dispatch
def toInt128(arg: float64) -> Int128:
    with let:
        isNegative = arg < 0
    with let:
        v0 = _ldexp(abs(arg), -100)
    with let:
        w0 = uint64(trunc(v0))
    with let:
        v1 = _ldexp(v0 - float64(w0), 50)
    with let:
        w1 = uint64(trunc(v1))
    with let:
        v2 = _ldexp(v1 - float64(w1), 50)
    with let:
        w2 = uint64(trunc(v2))

    with let:
        res = _bitor(toInt128(w0) << 100, toInt128(w1) << 50, toInt128(w2))
    if isNegative:
        return -res
    else:
        return res


def maskUInt64(arg: Int128) -> Int128:
    """{.noinit, inline.}"""
    result = Zero.copy()
    result._udata[0] = arg._udata[0]
    result._udata[1] = arg._udata[1]
    result._udata[2] = 0
    result._udata[3] = 0
    return result


def maskUInt32(arg: Int128) -> Int128:
    """{.noinit, inline.}"""
    result = Zero.copy()
    result._udata[0] = arg._udata[0]
    result._udata[1] = 0
    result._udata[2] = 0
    result._udata[3] = 0
    return result


def maskUInt16(arg: Int128) -> Int128:
    """{.noinit, inline.}"""
    result = Zero.copy()
    result._udata[0] = arg._udata[0] & 0xffff
    result._udata[1] = 0
    result._udata[2] = 0
    result._udata[3] = 0
    return result


def maskUInt8(arg: Int128) -> Int128:
    """{.noinit, inline.}"""
    result = Zero.copy()
    result._udata[0] = arg._udata[0] & 0xff
    result._udata[1] = 0
    result._udata[2] = 0
    result._udata[3] = 0
    return result


def maskBytes(arg: Int128, numbytes: nint) -> Int128:
    """{.noinit.}"""
    match numbytes:
        case 1:
            return maskUInt8(arg)
        case 2:
            return maskUInt16(arg)
        case 4:
            return maskUInt32(arg)
        case 8:
            return maskUInt64(arg)
        case _:
            raiseAssert(string("masking only implemented for 1, 2, 4 and 8 bytes"))


if comptime(__name__ == "__main__"):
    def test_int128():
        # $ and parseDecimalInt128 round trip (parsing low(Int128) overflows: it parses 2^127 first)
        for s in [string("0"), string("1"), string("-1"), string("4294967296"), string("-18446744073709551616"),
                  string("170141183460469231731687303715884105727"),
                  string("123456789012345678901234567890")]:
            doAssert(str(parseDecimalInt128(s)) == s, string("round trip ") + s)
        doAssert(str(low(Int128)) == "-170141183460469231731687303715884105728", string("low"))
        doAssert(str(high(Int128)) == "170141183460469231731687303715884105727", string("high"))
        doAssert(low(Int128) < high(Int128), string("low < high"))

        # conversions from the integer types and bool, sign extension
        doAssert(toInt128(True) == One, string("bool"))
        doAssert(str(toInt128(int8(-5))) == "-5", string("int8"))
        doAssert(str(toInt128(int64(-9223372036854775807) - 1)) == "-9223372036854775808", string("low(int64)"))
        doAssert(str(toInt128(high(uint64))) == "18446744073709551615", string("high(uint64)"))
        doAssert(str(toInt128(u32(4000000000))) == "4000000000", string("uint32"))
        doAssert(toInt64(toInt128(int64(-42))) == -42, string("toInt64"))
        doAssert(toInt128(int32(-7)).toInt32() == -7, string("toInt32"))
        doAssert(toUInt64(toInt128(high(uint64))) == high(uint64), string("toUInt64"))
        doAssert(toInt64Checked(parseDecimalInt128(string("18446744073709551616")), int64(-1)) == -1,
                 string("toInt64Checked"))
        doAssert(castToInt64(NegOne) == -1, string("castToInt64"))
        doAssert(toHex(NegOne) == "ffffffffffffffffffffffffffffffff", string("toHex"))
        doAssert(toHex(toInt128(int64(255))) == "000000000000000000000000000000ff", string("toHex 255"))

        # arithmetic
        with let:
            a = parseDecimalInt128(string("123456789012345678901"))
            b = parseDecimalInt128(string("-987654321987654321"))
        doAssert(str(a + b) == "122469134690358024580", string("+"))
        doAssert(str(a - b) == "124444443334333333222", string("-"))
        doAssert(str(a * b) == "-121932631246761163237079713333251181221", string("*"))
        doAssert(str(a // b) == "-124", string("div"))
        doAssert(str(a % b) == "987653085876543097", string("mod"))
        doAssert(str(b // toInt128(int64(7))) == "-141093474569664903", string("div negative"))
        doAssert(str(b % toInt128(int64(7))) == "0", string("mod negative"))
        doAssert(str(-a) == "-123456789012345678901", string("unary -"))
        doAssert(str(abs(b)) == "987654321987654321", string("abs"))
        doAssert(str(a * int32(-3)) == "-370370367037037036703", string("* int32"))
        with var:
            c = Zero.copy()
        c += a
        c -= One
        c *= int32(2)
        doAssert(str(c) == "246913578024691357800", string("+= -= *="))
        c.inc(u32(8))
        doAssert(str(c) == "246913578024691357808", string("inc"))

        # shifts and bit operations
        doAssert(str(One << 100) == "1267650600228229401496703205376", string("shl"))
        doAssert(str((One << 100) >> 99) == "2", string("shr"))
        doAssert(str(NegOne >> 64) == "-1", string("shr sign"))
        doAssert(str(bitand(a, toInt128(int64(0xffff)))) == "27701", string("bitand"))
        doAssert(str(bitxor(One, toInt128(int64(3)))) == "2", string("bitxor"))
        doAssert(bitnot(Zero) == NegOne, string("bitnot"))
        doAssert(fastLog2(One << 77) == 77, string("fastLog2"))

        # comparisons with BiggestInt in both orders
        doAssert(a > 5 and BiggestInt(5) < a and a == a, string("compare"))
        doAssert(toInt128(int64(3)) == BiggestInt(3) and BiggestInt(3) == toInt128(int64(3)), string("== BiggestInt"))
        doAssert(str(BiggestInt(10) - One) == "9" and str(BiggestInt(10) + One) == "11", string("BiggestInt +-"))
        doAssert(a.cmp(b) > 0 and b.cmp(a) < 0 and a.cmp(a) == 0, string("cmp"))

        # floats
        doAssert(toFloat64(parseDecimalInt128(string("-1180591620717411303424"))) == -1.180591620717411303424e21,
                 string("toFloat64"))
        doAssert(str(toInt128(-123456789.0)) == "-123456789", string("toInt128(float)"))
        doAssert(str(toInt128(1.5e30)) == "1499999999999999889089448902656", string("toInt128(1.5e30)"))

        # masks
        doAssert(str(maskBytes(NegOne, 1)) == "255", string("mask 1"))
        doAssert(str(maskBytes(NegOne, 2)) == "65535", string("mask 2"))
        doAssert(str(maskBytes(NegOne, 4)) == "4294967295", string("mask 4"))
        doAssert(str(maskBytes(NegOne, 8)) == "18446744073709551615", string("mask 8"))
        # conversions to the smaller types
        doAssert(toInt128(int16(-300)).toInt16() == -300 and toInt128(int8(-5)).toInt8() == -5, string("toInt16/8"))
        doAssert(toInt128(u32(4000000000)).toUInt32() == u32(4000000000), string("toUInt32"))
        doAssert(toInt128(u16(65535)).toUInt16() == u16(65535) and toInt128(u8(200)).toUInt8() == u8(200),
                 string("toUInt16/8"))
        doAssert(toInt(toInt128(int64(-9))) == -9 and toUInt(toInt128(int64(9))) == uint(9), string("toInt/toUInt"))
        doAssert(castToUInt64(toInt128(int64(-2))) == u64(18446744073709551614), string("castToUInt64"))

        # divMod: |dividend| < |divisor| with a negative dividend, and |dividend| == |divisor|
        with let:
            dm1 = divMod(toInt128(int64(-3)), toInt128(int64(10)))
            dm2 = divMod(toInt128(int64(-7)), toInt128(int64(7)))
            dm3 = divMod(toInt128(int64(7)), toInt128(int64(-7)))
        doAssert(str(dm1.quotient) == "0" and str(dm1.remainder) == "-3", string("divMod |a| < |b|"))
        doAssert(str(dm2.quotient) == "-1" and str(dm2.remainder) == "0", string("divMod -a == b"))
        doAssert(str(dm3.quotient) == "-1" and str(dm3.remainder) == "0", string("divMod a == -b"))

        # Int128 first, BiggestInt second
        doAssert(not (a <= BiggestInt(123456789012345678)) and One <= BiggestInt(1), string("<= BiggestInt"))
        doAssert(str(One + BiggestInt(1)) == "2" and str(One - BiggestInt(3)) == "-2", string("+- BiggestInt"))

        # `*` by low(int32): abs of the int32 overflows, as in Nim
        with var:
            overflowed = False
        try:
            _ = One * low(int32)
        except OverflowDefect:
            overflowed = True
        doAssert(overflowed, string("abs(low(int32)) overflows"))
        echo(string("int128 tests passed"))

    test_int128()
