"""Nim std/math — re-exports Python's math module and adds Nim math types and functions."""
from math import *
import math as _math
import sys as _sys
from nimic.ntypes import NIntEnum, auto


class FloatClass(NIntEnum):
    """Describes the class a floating point value belongs to (Nim's members, in Nim's order)."""
    fcNormal = auto()     # value is an ordinary nonzero floating point value
    fcSubnormal = auto()  # value is a subnormal (a very small) floating point value
    fcZero = auto()       # value is zero
    fcNegZero = auto()    # value is the negative zero
    fcNan = auto()        # value is Not a Number (NaN)
    fcInf = auto()        # value is positive infinity
    fcNegInf = auto()     # value is negative infinity


fcNormal = FloatClass.fcNormal
fcSubnormal = FloatClass.fcSubnormal
fcZero = FloatClass.fcZero
fcNegZero = FloatClass.fcNegZero
fcNan = FloatClass.fcNan
fcInf = FloatClass.fcInf
fcNegInf = FloatClass.fcNegInf


def signbit(x: float) -> bool:
    """Nim: signbit — return true if the sign bit of x is set."""
    return _math.copysign(1.0, float(x)) < 0.0


def trunc(x: float) -> float:
    """Nim: trunc — x rounded toward zero, as a float (Python's math.trunc returns an int)."""
    return float(_math.trunc(float(x)))


def classify(x: float) -> FloatClass:
    """Nim: classify — classifies a float into FloatClass enum."""
    fx = float(x)
    if _math.isnan(fx):
        return fcNan
    if _math.isinf(fx):
        return fcNegInf if signbit(fx) else fcInf
    if fx == 0.0:
        return fcNegZero if signbit(fx) else fcZero
    if abs(fx) < _sys.float_info.min:
        return fcSubnormal
    return fcNormal


Inf = float("inf")
NaN = float("nan")