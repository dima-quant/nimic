"""Nim std/math — re-exports Python's math module and adds Nim math types and functions."""
from math import *
import math as _math
from enum import Enum


class FloatClass(Enum):
    fcNan = "fcNan"
    fcNegZero = "fcNegZero"
    fcZero = "fcZero"
    fcNegInf = "fcNegInf"
    fcInf = "fcInf"
    fcNegNormal = "fcNegNormal"
    fcNormal = "fcNormal"
    fcNegSubnormal = "fcNegSubnormal"
    fcSubnormal = "fcSubnormal"


fcNan = FloatClass.fcNan
fcNegZero = FloatClass.fcNegZero
fcZero = FloatClass.fcZero
fcNegInf = FloatClass.fcNegInf
fcInf = FloatClass.fcInf
fcNegNormal = FloatClass.fcNegNormal
fcNormal = FloatClass.fcNormal
fcNegSubnormal = FloatClass.fcNegSubnormal
fcSubnormal = FloatClass.fcSubnormal


def signbit(x: float) -> bool:
    """Nim: signbit — return true if the sign bit of x is set."""
    return _math.copysign(1.0, float(x)) < 0.0


def classify(x: float) -> FloatClass:
    """Nim: classify — classifies a float into FloatClass enum."""
    fx = float(x)
    if _math.isnan(fx):
        return fcNan
    if _math.isinf(fx):
        return fcNegInf if signbit(fx) else fcInf
    if fx == 0.0:
        return fcNegZero if signbit(fx) else fcZero
    return fcNegNormal if signbit(fx) else fcNormal


Inf = float("inf")
NaN = float("nan")