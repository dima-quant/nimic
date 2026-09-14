# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from math import sqrt
from errors import ensureWithinRelTol


# Operation generators
# -------------------------------------------------

class  Vec3(Object):
    x: float64
    y: float64
    z: float64

    # Operations
# -------------------------------------------------
# For Vec3, Point3 and Color

    def __iadd__(u: mut @ Vec3, v: Vec3):
        """{.inline.}"""
        for dst, src in fields(u, v):
            dst += src
        return u

    def __isub__(u: mut @ Vec3, v: Vec3):
        """{.inline.}"""
        for dst, src in fields(u, v):
            dst -= src
        return u

    def __imul__(u: mut @ Vec3, scalar: float64):
        """{.inline.}"""
        for dst in fields(u):
            dst *= scalar
        return u

    def __itruediv__(u: mut @ Vec3, scalar: float64):
        """{.inline.}"""
        for dst in fields(u):
            dst /= scalar
        return u

    def __add__(self: Vec3, v: Vec3) -> Vec3:
        """{.inline.}"""
        result = type(self)()
        result.x = self.x + v.x
        result.y = self.y + v.y
        result.z = self.z + v.z
        return result

    def __sub__(self: Vec3, v: Vec3) -> Vec3:
        """{.inline.}"""
        result = type(self)()
        result.x = self.x - v.x
        result.y = self.y - v.y
        result.z = self.z - v.z
        return result

    def length_squared(u: Vec3) -> float64:
        """{.inline.}"""
        return u.x * u.x + u.y * u.y + u.z * u.z

    def length(u: Vec3) -> float64:
        """{.inline.}"""
        return sqrt(u.length_squared())

    @template
    def toUV(v: Vec3) -> UnitVector:
        ## In debug mode we check conversion
        ensureWithinRelTol(v.length_squared(), 1.0)
        return UnitVector(v)

    def __neg__(u: Vec3) -> Vec3:
        """{.inline.}"""
        result = type(u)()
        for dst, src in fields(result, u):
            dst <<= - src
        return result

    def __mul__(u: Vec3, scalar: float64) -> Vec3:
        """{.inline.}"""
        result = type(u)()
        for dst, src in fields(result, u):
            dst <<= src * scalar
        return result

    def __rmul__(u: Vec3, scalar: float64) -> Vec3:
        """{.inline.}"""
        return u * scalar

    def __truediv__(self, scalar: float64) -> Vec3:
        """{.inline.}"""
        return self * (1.0 / scalar)

    def dot(u: Vec3, v: Vec3) -> float64:
        """{.inline.}"""
        ## Dot product of vector u and v
        return u.x * v.x + u.y * v.y + u.z * v.z

    def cross(u: Vec3, v: Vec3) -> Vec3:
        """{.inline.}"""
        ## Cross product of vector u and v
        result = type(u)()
        result.x = u.y * v.z - u.z * v.y
        result.y = u.z * v.x - u.x * v.z
        result.z = u.x * v.y - u.y * v.x
        return result

    # if self is not annotated, it will be derived from the class name (as not mutable)
    def unit_vector(self) -> UnitVector:
        """{.inline.}"""
        return UnitVector(self / self.length())


@distinct
class UnitVector(Vec3):
    """{.borrow:`.`.}"""
    ## Enforce explicit tagging of unit vectors
    ## to prevent misuse. (The borrow allow access to fields)

# Properties
# -------------------------------------------------


# Conversion
# -------------------------------------------------
    @converter
    def toVec3(uv: UnitVector) -> Vec3:
        """{.inline.}"""
        ## UnitVector are seamlessly convertible to Vec3 (but not the otherway around)
        return Vec3(uv)

# Init
# -------------------------------------------------

def vec3(x: float64, y: float64, z: float64) -> Vec3:
    """{.inline.}"""
    result = Vec3()
    result.x = x
    result.y = y
    result.z = z
    return result


# sd = vec3(1.0, 2.0, 3.0)
# sr = vec3(1.0, 0.0, 4.0)
# a = 2*sd
# print(a.z)
# a /= 10
# print(a.z)
# sd += a
# print(sd.z)
# print(a.z)
# a /= a.length()
# u = a.toUV()

# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   std/math,
#   ../support/errors

# type
#   Vec3* = object
#     x*, y*, z*: float64

#   UnitVector* {.borrow:`.`.} = distinct Vec3
#     ## Enforce explicit tagging of unit vectors
#     ## to prevent misuse. (The borrow allow access to fields)

# # Properties
# # -------------------------------------------------

# func length_squared*(u: Vec3): float64 {.inline.} =
#   u.x * u.x + u.y * u.y + u.z * u.z

# func length*(u: Vec3): float64 {.inline.} =
#   u.length_squared().sqrt()

# # Conversion
# # -------------------------------------------------

# converter toVec3*(uv: UnitVector): Vec3 {.inline.} =
#   ## UnitVector are seamlessly convertible to Vec3 (but not the otherway around)
#   Vec3(uv)

# template toUV*(v: Vec3): UnitVector =
#   ## In debug mode we check conversion
#   ensureWithinRelTol(v.length_squared(), 1.0)
#   UnitVector(v)

# # Init
# # -------------------------------------------------

# func vec3*(x, y, z: float64): Vec3 {.inline.} =
#   result.x = x
#   result.y = y
#   result.z = z

# # Operation generators
# # -------------------------------------------------

# template genInplace(op: untyped): untyped =
#   ## Generate an in-place elementwise operation
#   func op*(u: var Vec3, v: Vec3) {.inline.} =
#     for dst, src in fields(u, v):
#       op(dst, src)

# template genInfix(op: untyped): untyped =
#   ## Generate an infix elementwise operation
#   func op*(u: Vec3, v: Vec3): Vec3 {.inline.} =
#     result.x = op(u.x, v.x)
#     result.y = op(u.y, v.y)
#     result.z = op(u.z, v.z)

# template genInplaceBroadcastScalar(op: untyped): untyped =
#   ## Generate an in-place scalar broadcast operation
#   func op*(u: var Vec3, scalar: float64) {.inline.} =
#     for dst in fields(u):
#       op(dst, scalar)

# # Operations
# # -------------------------------------------------
# # For Vec3, Point3 and Color

# genInplace(`+=`)
# genInplace(`-=`)
# genInplaceBroadcastScalar(`*=`)
# genInplaceBroadcastScalar(`/=`)
# genInfix(`+`)
# genInfix(`-`)

# func `-`*(u: Vec3): Vec3 {.inline.} =
#   for dst, src in fields(result, u):
#     dst = -src

# func `*`*(u: Vec3, scalar: float64): Vec3 {.inline.} =
#   for dst, src in fields(result, u):
#     dst = src * scalar

# func `*`*(scalar: float64, u: Vec3): Vec3 {.inline.} =
#   u * scalar

# func `/`*(u: Vec3, scalar: float64): Vec3 {.inline.} =
#   u * (1.0 / scalar)

# func dot*(u, v: Vec3): float64 {.inline.} =
#   ## Dot product of vector u and v
#   u.x * v.x + u.y * v.y + u.z * v.z

# func cross*(u, v: Vec3): Vec3 {.inline.} =
#   ## Cross product of vector u and v
#   result.x = u.y * v.z - u.z * v.y
#   result.y = u.z * v.x - u.x * v.z
#   result.z = u.x * v.y - u.y * v.x

# func unit_vector*(u: Vec3): UnitVector {.inline.} =
#   UnitVector(u / u.length())