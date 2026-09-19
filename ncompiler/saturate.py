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

## Saturated arithmetic routines. XXX Make part of the stdlib?

def sat_plus(a: BiggestInt, b: BiggestInt) -> BiggestInt:
    """saturated addition."""
    result = int64(uint64(a) + uint64(b))
    if ((result ^ a) >= i64(0)) | ((result ^ b) >= i64(0)):
        return result
    if (a < 0) | (b < 0):
        result = low(type(result))
    else:
        result = high(type(result))
    return result

def sat_minus(a: BiggestInt, b: BiggestInt) -> BiggestInt:
    """saturated subtraction."""
    result = int64(uint64(a) - uint64(b))
    if ((result ^ a) >= i64(0)) | ((result ^ ~b) >= i64(0)):
        return result
    if b > 0:
        result = low(type(result))
    else:
        result = high(type(result))
    return result

def sat_abs(a: BiggestInt) -> BiggestInt:
    """saturated absolute value."""
    if a != low(int64):
        if a >= 0:
            result = a
        else:
            result = -a
    else:
        result = low(int64)
    return result

def sat_div(a: BiggestInt, b: BiggestInt) -> BiggestInt:
    """saturated division."""
    # (0..5) div (0..4) == (0..5) div (1..4) == (0 div 4)..(5 div 1)
    if b == 0:
        # make the same as ``div 1``:
        result = a
    elif (a == low(int64)) & (b == -1):
        result = high(int64)
    else:
        result = a // b
    return result

def sat_mod(a: BiggestInt, b: BiggestInt) -> BiggestInt:
    """saturated modulo."""
    if b == 0:
        result = a
    else:
        result = a % b
    return result

def sat_mul(a: BiggestInt, b: BiggestInt) -> BiggestInt:
    """saturated multiplication."""
    with var:
        _resAsFloat = float64(0.0)
        _floatProd = float64(0.0)
    result = int64(uint64(a) * uint64(b))
    _floatProd = float64(a)  # conversion
    _floatProd = _floatProd * float64(b)
    _resAsFloat = float64(result)

    # Fast path for normal case: small multiplicands, and no info
    # is lost in either method.
    if _resAsFloat == _floatProd:
        return result

    # Somebody somewhere lost info. Close enough, or way off? Note
    # that a != 0 and b != 0 (else resAsFloat == floatProd == 0).
    # The difference either is or isn't significant compared to the
    # true value (of which floatProd is a good approximation).

    # abs(diff)/abs(prod) <= 1/32 iff
    #   32 * abs(diff) <= abs(prod) -- 5 good bits is "close enough"
    if 32.0 * abs(_resAsFloat - _floatProd) <= abs(_floatProd):
        return result

    if _floatProd >= 0.0:
        result = high(int64)
    else:
        result = low(int64)
    return result

if comptime(__name__ == "__main__"):
    # Test saturated addition
    assert sat_plus(3, 4) == 7
    assert sat_plus(-3, -4) == -7
    assert sat_plus(0, 0) == 0

    # Test saturated subtraction
    assert sat_minus(7, 3) == 4
    assert sat_minus(3, 7) == -4
    assert sat_minus(0, 0) == 0

    # Test saturated absolute value
    assert sat_abs(5) == 5
    assert sat_abs(-5) == 5
    assert sat_abs(0) == 0

    # Test saturated division
    assert sat_div(10, 3) == 3
    assert sat_div(10, 0) == 10  # div by zero returns a
    assert sat_div(-10, -3) == 3
    assert (sat_div(-10, 3) == -4) | (sat_div(-10, 3) == -3)  # Python floor vs Nim truncating div

    # Test saturated modulo
    assert sat_mod(10, 3) == 1
    assert sat_mod(10, 0) == 10  # mod by zero returns a

    # Test saturated multiplication
    assert sat_mul(3, 4) == 12
    assert sat_mul(-3, 4) == -12
    assert sat_mul(0, 100) == 0

    # Test overflow saturation
    with let:
        _max_val = int(high(int64))
        _min_val = int(low(int64))
    assert sat_plus(_max_val, 1) == _max_val  # saturates to max
    assert sat_plus(_min_val, -1) == _min_val  # saturates to min
    assert sat_plus(_max_val, -10) == _max_val - 10  # within bounds
    assert sat_plus(_min_val, 10) == _min_val + 10  # within bounds

    assert sat_minus(_min_val, 1) == _min_val  # saturates to min
    assert sat_minus(_max_val, -1) == _max_val  # saturates to max
    assert sat_minus(_max_val, 10) == _max_val - 10  # within bounds
    assert sat_minus(_min_val, -10) == _min_val + 10  # within bounds

    assert sat_abs(_min_val) == _min_val  # can't negate min int64
    assert sat_div(_min_val, -1) == _max_val  # special case

    # Saturated multiplication overflow
    assert sat_mul(_max_val, 2) == _max_val  # saturates to max
    assert sat_mul(_max_val, -2) == _min_val  # saturates to min
    assert sat_mul(_min_val, 2) == _min_val  # saturates to min
    assert sat_mul(_min_val, -1) == _max_val  # saturates to max

    echo("All saturate tests passed!")
