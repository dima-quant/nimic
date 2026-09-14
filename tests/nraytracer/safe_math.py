# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
# Stdlib
from math import degrees, radians


def clamp(x: float64, min: float64, max: float64) -> float64:
    """{.inline, noSideEffect.}"""
    # Nim builtin clamp is not inline :/
    if x < min: return min
    if x > max: return max
    return x

# Angles
# ------------------------------------------------------
# We prevent mismatch between degrees and radians
# via compiler-enforced type-checking

@distinct
class  Degrees(float64):
    pass

@distinct
class  Radians(float64):
    def __isub__(a: mut @ Radians, b: Radians):
      """{.borrow.}"""
      return super().__isub__(b)

    # For now we don't create our full safe unit library
    # with proper cos/sin/tan radians enforcing
    # and auto-convert to float
    @converter
    def toF64(rad: Radians) -> float64:
        """{.inline.}"""
        return float64(rad)


@template
def degToRad(deg: Degrees) -> Radians:
    return Radians(radians(float64(deg)))

@template
def radToDeg(rad: Radians) -> Degrees:
    return Degrees(degrees(float64(rad)))


# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import std/math

# func clamp*(x, min, max: float64): float64 {.inline.} =
#   # Nim builtin clamp is not inline :/
#   if x < min: return min
#   if x > max: return max
#   return x

# # Angles
# # ------------------------------------------------------
# # We prevent mismatch between degrees and radians
# # via compiler-enforced type-checking

# type
#   Degrees* = distinct float64
#   Radians* = distinct float64

# template degToRad*(deg: Degrees): Radians =
#   Radians degToRad float64 deg

# template radToDeg*(rad: Radians): Degrees =
#   Degrees radToDeg float64 rad

# # For now we don't create our full safe unit library
# # with proper cos/sin/tan radians enforcing
# # and auto-convert to float
# converter toF64*(rad: Radians): float64 {.inline.} =
#   float64 rad

# func `-=`*(a: var Radians, b: Radians) {.inline.} =
#   # workaround https://github.com/nim-lang/Nim/issues/14440
#   cast[var float64](a.addr) -= b.float64