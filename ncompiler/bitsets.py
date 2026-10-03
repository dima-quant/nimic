# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# this unit handles Nim sets; it implements bit sets
# the code here should be reused in the Nim standard library

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *

class ElemType(byte): pass
class TBitSet(seq[ElemType]): pass    # we use byte here to avoid issues with
                                      # cross-compiling; uint would be more efficient
                                      # however

with const:
    ElemSize = 8
    _one = ElemType(1)
    _zero = ElemType(0)

@template
def _modElemSize(arg: untyped) -> untyped:
    return arg & 7

@template
def _divElemSize(arg: untyped) -> untyped:
    return arg >> 3

def bitSetIn(x: TBitSet, e: BiggestInt) -> bool:
    result = (x[nint(_divElemSize(e))] & (_one << _modElemSize(e))) != _zero
    return result

def bitSetIncl(x: mut@TBitSet, elem: BiggestInt):
    assert elem >= 0
    x[nint(_divElemSize(elem))] = x[nint(_divElemSize(elem))] | (_one << _modElemSize(elem))

def bitSetExcl(x: mut@TBitSet, elem: BiggestInt):
    x[nint(_divElemSize(elem))] = x[nint(_divElemSize(elem))] & ~(_one << _modElemSize(elem))

def bitSetInit(b: mut@TBitSet, length: nint):
    newSeq(b, length)

def bitSetUnion(x: mut@TBitSet, y: TBitSet):
    for i in inrange(0, high(x)):
        x[i] = x[i] | y[i]

def bitSetDiff(x: mut@TBitSet, y: TBitSet):
    for i in inrange(0, high(x)):
        x[i] = x[i] & ~y[i]

def bitSetSymDiff(x: mut@TBitSet, y: TBitSet):
    for i in inrange(0, high(x)):
        x[i] = x[i] ^ y[i]

def bitSetIntersect(x: mut@TBitSet, y: TBitSet):
    for i in inrange(0, high(x)):
        x[i] = x[i] & y[i]

def bitSetEquals(x: TBitSet, y: TBitSet) -> bool:
    for i in inrange(0, high(x)):
        if x[i] != y[i]:
            return False
    result = True
    return result

def bitSetContains(x: TBitSet, y: TBitSet) -> bool:
    for i in inrange(0, high(x)):
        if (x[i] & ~y[i]) != _zero:
            return False
    result = True
    return result

# Number of set bits for all values of int8
def _block():
    with var:
        _arr = array[uint8, uint8]()

    def _countSetBits(x: uint8) -> uint8:
        return (
            (x & u8(0b00000001)) +
            ((x & u8(0b00000010)) >> 1) +
            ((x & u8(0b00000100)) >> 2) +
            ((x & u8(0b00001000)) >> 3) +
            ((x & u8(0b00010000)) >> 4) +
            ((x & u8(0b00100000)) >> 5) +
            ((x & u8(0b01000000)) >> 6) +
            ((x & u8(0b10000000)) >> 7)
        )

    for it in inrange(low(uint8), high(uint8)):
        _arr[it] = _countSetBits(cast[uint8](it))

    return _arr

with const:
    _populationCount: array[uint8, uint8] = _block()

def bitSetCard(x: TBitSet) -> BiggestInt:
    result = BiggestInt(0)
    for it in x:
        result += nint(_populationCount[it])
    return result

def bitSetToWord(s: TBitSet, size: nint) -> BiggestUInt:
    result = BiggestUInt(0)
    for j in range(size):
        if j < len(s):
            result = result | (BiggestUInt(s[j]) << (j * 8))
    return result

if comptime(__name__ == "__main__"):
    assert ElemSize == 8

    with var:
        s1: TBitSet = TBitSet()
        s2: TBitSet = TBitSet()
        s3: TBitSet = TBitSet()

    bitSetInit(s1, 4)
    bitSetInit(s2, 4)
    bitSetInit(s3, 4)
    assert len(s1) == 4
    assert len(s2) == 4

    assert not bitSetIn(s1, 0)
    assert not bitSetIn(s1, 15)
    assert not bitSetIn(s1, 31)

    bitSetIncl(s1, 0)
    bitSetIncl(s1, 7)
    bitSetIncl(s1, 8)
    bitSetIncl(s1, 31)
    assert bitSetIn(s1, 0)
    assert bitSetIn(s1, 7)
    assert bitSetIn(s1, 8)
    assert bitSetIn(s1, 31)
    assert not bitSetIn(s1, 1)
    assert not bitSetIn(s1, 6)
    assert not bitSetIn(s1, 9)
    assert not bitSetIn(s1, 30)

    bitSetExcl(s1, 7)
    assert not bitSetIn(s1, 7)
    assert bitSetIn(s1, 0)
    assert bitSetIn(s1, 8)
    assert bitSetIn(s1, 31)

    bitSetIncl(s1, 7)

    bitSetIncl(s2, 0)
    bitSetIncl(s2, 1)
    bitSetIncl(s2, 8)
    bitSetIncl(s2, 9)

    bitSetInit(s3, 4)
    bitSetIncl(s3, 0)
    bitSetIncl(s3, 7)
    bitSetIncl(s3, 8)
    bitSetIncl(s3, 31)
    assert bitSetEquals(s1, s3)
    assert not bitSetEquals(s1, s2)

    bitSetUnion(s3, s2)
    assert bitSetIn(s3, 0)
    assert bitSetIn(s3, 1)
    assert bitSetIn(s3, 7)
    assert bitSetIn(s3, 8)
    assert bitSetIn(s3, 9)
    assert bitSetIn(s3, 31)
    assert not bitSetIn(s3, 2)

    bitSetIntersect(s3, s1)
    assert bitSetEquals(s3, s1)

    bitSetDiff(s3, s2)
    assert bitSetIn(s3, 7)
    assert bitSetIn(s3, 31)
    assert not bitSetIn(s3, 0)
    assert not bitSetIn(s3, 8)

    bitSetSymDiff(s3, s1)
    assert bitSetIn(s3, 0)
    assert bitSetIn(s3, 8)
    assert not bitSetIn(s3, 7)
    assert not bitSetIn(s3, 31)

    # bitSetContains(x, y) checks if x is subset of y (i.e. y contains x)
    assert bitSetContains(s3, s1)
    assert not bitSetContains(s1, s3)

    assert bitSetCard(s1) == 4
    assert bitSetCard(s3) == 2

    with var:
        s_empty: TBitSet = TBitSet()
    bitSetInit(s_empty, 4)
    assert bitSetCard(s_empty) == 0

    with var:
        s_full: TBitSet = TBitSet()
    bitSetInit(s_full, 1)
    for i in inrange(0, 7):
        bitSetIncl(s_full, i)
    assert bitSetCard(s_full) == 8

    with var:
        w_set: TBitSet = TBitSet()
    bitSetInit(w_set, 4)
    bitSetIncl(w_set, 1)
    bitSetIncl(w_set, 4)
    bitSetIncl(w_set, 10)
    bitSetIncl(w_set, 12)
    bitSetIncl(w_set, 13)
    assert bitSetToWord(w_set, 2) == u64(0x3412)
    assert bitSetToWord(w_set, 1) == u64(0x12)

    # Additional edge cases and boundary tests:
    # 1. bitSetExcl on non-included element within bounds (no-op)
    bitSetExcl(s1, 20)
    assert bitSetIn(s1, 0)
    assert not bitSetIn(s1, 20)

    # 2. bitSetExcl on boundary elements (0 and 31)
    bitSetExcl(s1, 0)
    assert not bitSetIn(s1, 0)
    bitSetExcl(s1, 31)
    assert not bitSetIn(s1, 31)
    bitSetIncl(s1, 0)
    bitSetIncl(s1, 31)
    assert bitSetIn(s1, 0)
    assert bitSetIn(s1, 31)

    # 3. bitSetEquals reflexivity and empty sets
    with var:
        s_empty2: TBitSet = TBitSet()
    bitSetInit(s_empty2, 4)
    assert bitSetEquals(s1, s1)
    assert bitSetEquals(s_empty, s_empty2)

    # 4. bitSetContains reflexivity and empty set properties
    assert bitSetContains(s1, s1)
    assert bitSetContains(s_empty, s1)      # empty set is subset of s1
    assert not bitSetContains(s1, s_empty)  # s1 is not subset of empty set
    assert bitSetContains(s_empty, s_empty2)

    # 5. Union and intersect with empty set
    with var:
        s_copy: TBitSet = TBitSet()
    bitSetInit(s_copy, 4)
    bitSetUnion(s_copy, s1)
    assert bitSetEquals(s_copy, s1)
    bitSetUnion(s_copy, s_empty)
    assert bitSetEquals(s_copy, s1)
    bitSetIntersect(s_copy, s_empty)
    assert bitSetEquals(s_copy, s_empty)

    # 6. bitSetToWord edge cases: size == 0, size == 4, size > len(s)
    assert bitSetToWord(w_set, 0) == u64(0)
    assert bitSetToWord(w_set, 4) == u64(0x3412)
    assert bitSetToWord(w_set, 8) == u64(0x3412)  # size > len(w_set), boundary check

    # 7. Additional bitSetCard verification
    with var:
        s_patterns: TBitSet = TBitSet()
    bitSetInit(s_patterns, 2)
    # Byte 0: 0b10101010 (4 bits set: 1, 3, 5, 7)
    bitSetIncl(s_patterns, 1)
    bitSetIncl(s_patterns, 3)
    bitSetIncl(s_patterns, 5)
    bitSetIncl(s_patterns, 7)
    # Byte 1: 0b11111111 (8 bits set: 8..15)
    for i in inrange(8, 15):
        bitSetIncl(s_patterns, i)
    assert bitSetCard(s_patterns) == 12

    echo(string("All bitsets tests passed!"))
