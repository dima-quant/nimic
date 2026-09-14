# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from vec3s import Vec3

# Colors
# -----------------------------------------------------
# We use Nim distinct types to model Color after Vec3 (via "borrow")
# but ensuring we don't mismatch usage

@distinct
class Color(Vec3):
    """{.borrow: `.`.}"""

    def __eq__(a: Color, b: Color) -> bool:
        """{.inline.}"""
        return Vec3(a) == Vec3(b)

    def __str__(a: Color) -> string:
        """{.inline.}"""
        return str(Vec3(a))


    def __imul__(self: mut @ Color, scalar: float64):
        """{.borrow.}"""
        return super().__imul__(scalar)

    def __mul__(self: Color, scalar: float64) -> Color:
        """{.borrow.}"""
        return super().__mul__(scalar)

    def __rmul__(self: Color, scalar: float64) -> Color:
        """{.borrow.}"""
        return super().__rmul__(scalar)

    def __iadd__(self: mut @ Color, other: Color):
        """{.borrow.}"""
        return super().__iadd__(other)

    def __add__(self: Color, other: Color) -> Color:
        """{.borrow.}"""
        return super().__add__(other)

    def __sub__(self: Color, other: Color) -> Color:
        """{.borrow.}"""
        return super().__sub__(other)

    def __imul__(self: mut @ Color, b: Attenuation):
        """{.inline.}"""
        # Multiply a color by a per-channel attenuation factor
        self.x *= b.x
        self.y *= b.y
        self.z *= b.z
        return self

    # func `*`*(a, b: Color): Color {.error: "Multiplying 2 Colors doesn't make physical sense".}

# Attenuation
# -----------------------------------------------------
# We use Nim distinct types to model Attenuation after Color (via "borrow")
# but ensuring we don't mismatch usage

@distinct
class Attenuation(Color):
    """{.borrow: `.`.}"""
    def __imul__(a: mut @ Attenuation, b: Attenuation):
        """{.inline.}"""
        # Multiply a color by a per-channel attenuation factor
        a.x *= b.x
        a.y *= b.y
        a.z *= b.z
        return a

    def __mul__(a: Attenuation, b: Attenuation) -> Attenuation:
        """{.inline.}"""
        # Multiply a color by a per-channel attenuation factor
        result = Attenuation(Color(Vec3()))
        result.x = a.x * b.x
        result.y = a.y * b.y
        result.z = a.z * b.z
        return result

@dispatch
def attenuation(x: float64, y: float64, z: float64) -> Attenuation:
    """"{.inline.}"""
    result = Attenuation(Color(Vec3()))
    result.x = x
    result.y = y
    result.z = z
    return result

@dispatch
def attenuation() -> Attenuation:
    """"{.inline.}"""
    result = Attenuation(Color(Vec3()))
    return result

def color(x: float64, y: float64, z: float64) -> Color:
    """"{.inline.}"""
    result = Color(Vec3())
    result.x = x
    result.y = y
    result.z = z
    return result


# sd = color(1.0, 2.0, 3.0)
# sr = color(1.0, 0.0, 4.0)
# att = attenuation(1.0, 2.0, 13.0)
# b = sr + sd
# print(sd.z)
# a = 2*sd
# print(b.z)
# sd *= 3.0
# print(sd.z)
# sd *= att
# print(sd.z)


# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import ./vec3s

# # Colors
# # -----------------------------------------------------
# # We use Nim distinct types to model Color after Vec3 (via "borrow")
# # but ensuring we don't mismatch usage

# type Color* {.borrow: `.`.} = distinct Vec3

# func color*(x, y, z: float64): Color {.inline.} =
#   result.x = x
#   result.y = y
#   result.z = z

# func `==`*(a, b: Color): bool {.inline.} =
#   Vec3(a) == Vec3(b)

# func `$`*(a: Color): string {.inline.} =
#   $Vec3(a)

# func `*=`*(a: var Color, scalar: float64) {.borrow.}
# func `*`*(a: Color, scalar: float64): Color {.borrow.}
# func `*`*(scalar: float64, a: Color): Color {.borrow.}

# func `+=`*(a: var Color, b: Color) {.borrow.}
# func `+`*(a, b: Color): Color {.borrow.}
# func `-`*(a, b: Color): Color {.borrow.}

# func `*`*(a, b: Color): Color {.error: "Multiplying 2 Colors doesn't make physical sense".}

# # Attenuation
# # -----------------------------------------------------
# # We use Nim distinct types to model Attenuation after Color (via "borrow")
# # but ensuring we don't mismatch usage

# type Attenuation* {.borrow: `.`.} = distinct Color

# func attenuation*(x, y, z: float64): Attenuation {.inline.} =
#   result.x = x
#   result.y = y
#   result.z = z

# func `*=`*(a: var Attenuation, b: Attenuation) {.inline.} =
#   # Multiply a color by a per-channel attenuation factor
#   a.x *= b.x
#   a.y *= b.y
#   a.z *= b.z

# func `*`*(a, b: Attenuation): Attenuation {.inline.} =
#   # Multiply a color by a per-channel attenuation factor
#   result.x = a.x * b.x
#   result.y = a.y * b.y
#   result.z = a.z * b.z

# func `*=`*(a: var Color, b: Attenuation) {.inline.} =
#   # Multiply a color by a per-channel attenuation factor
#   a.x *= b.x
#   a.y *= b.y
#   a.z *= b.z
