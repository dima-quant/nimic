# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from math import pi, sqrt, sin, cos
# Internal
from primitives import Vec3, vec3, UnitVector, Attenuation, attenuation
from rng import Rng

import rng
with export:
    rng

# Random routines
# ------------------------------------------------------
@dispatch
def random(rng: mut @ Rng, _: type[float32]) -> float32:
    """{.inline, noSideEffect.}"""
    return float32(rng.uniform(float64)) # TODO: check if there is a better way to do this

@dispatch
def random(rng: mut @ Rng, _: type[float64]) -> float64:
    """{.inline, noSideEffect.}"""
    return rng.uniform(float64)

@dispatch
def random(rng: mut @ Rng, _: type[float64], max: float64) -> float64:
    """{.inline, noSideEffect.}"""
    return rng.uniform(max)

@dispatch
def random(rng: mut @ Rng, _: type[float64], min: float64, max: float64) -> float64:
    """{.inline, noSideEffect.}"""
    return rng.uniform(min, max)

# Vector
# ------------------------------------------------------
@dispatch
def _random(rng: mut @ Rng, _: type[Vec3]) -> Vec3:
    """{.inline, noSideEffect.}"""
    result = Vec3()
    result.x = random(rng, float64)
    result.y = random(rng, float64)
    result.z = random(rng, float64)
    return result

@dispatch
def _random(rng: mut @ Rng, _: type[Vec3], max: float64) -> Vec3:
    """{.inline, noSideEffect.}"""
    result = Vec3()
    result.x = random(rng, float64, max)
    result.y = random(rng, float64, max)
    result.z = random(rng, float64, max)
    return result

@dispatch
def _random(rng: mut @ Rng,  _: type[Vec3], min: float64, max: float64) -> Vec3:
    """{.inline, noSideEffect.}"""
    result = Vec3()
    result.x = random(rng, float64, min, max)
    result.y = random(rng, float64, min, max)
    result.z = random(rng, float64, min, max)
    return result

def random_in_unit_sphere(rng: mut @ Rng, _: type[Vec3]) -> Vec3:
    """{.noSideEffect.}"""
    while True:
        with let: p = _random(rng, Vec3, -1.0, 1.0)
        if p.length_squared() < 1.0:
            return p

@dispatch
def random(rng: mut @ Rng, _: type[UnitVector]) -> UnitVector:
    """{.noSideEffect.}"""
    with let: a = random(rng, float64, 2*pi)
    with let: z = random(rng, float64, -1.0, 1.0)
    with let: r = sqrt(1.0 - z*z)
    return vec3(r*cos(a), r*sin(a), z).toUV()

def random_in_hemisphere(rng: mut @ Rng, _: type[Vec3], normal: Vec3) -> Vec3:
    """{.noSideEffect.}"""
    with let: in_unit_sphere = random_in_unit_sphere(rng, Vec3)
    if in_unit_sphere.dot(normal) > 0.0: # In the same hemisphere as normal
        return in_unit_sphere
    else:
        return -in_unit_sphere

def random_in_unit_disk(rng: mut @ Rng, _: type[Vec3]) -> Vec3:
    """{.noSideEffect.}"""
    while True:
        result = vec3(random(rng, float64, -1.0, 1.0), random(rng, float64, -1.0, 1.0), 0)
        if result.length_squared() < 1:
            return result

# Color
# ------------------------------------------------------

@dispatch
def random(rng: mut @ Rng, _: type[Attenuation]) -> Attenuation:
    """{.inline, noSideEffect.}"""
    result = attenuation()
    result.x = random(rng, float64)
    result.y = random(rng, float64)
    result.z = random(rng, float64)
    return result

@dispatch
def random(rng: mut @ Rng, _: type[Attenuation], max: float64) -> Attenuation:
    """{.inline, noSideEffect.}"""
    result = attenuation()
    result.x = random(rng, float64, max)
    result.y = random(rng, float64, max)
    result.z = random(rng, float64, max)
    return result

@dispatch
def random(rng: mut @ Rng, _: type[Attenuation], min: float64, max: float64) -> Attenuation:
    """{.inline, noSideEffect.}"""
    result = attenuation()
    result.x = random(rng, float64, min, max)
    result.y = random(rng, float64, min, max)
    result.z = random(rng, float64, min, max)
    return result


if comptime(__name__ == "__main__"):
    with var: _rng = Rng()
    with let: timeSeed = 54
    _rng.seed(timeSeed)
    print(random(_rng, float64))
    print(random(_rng, float64))
    print(random(_rng, float64, 1.0))
    print(random(_rng, float64, 1.0, 10.0))

    # print(_random(_rng, Vec3))
    # print(_random(_rng, Vec3, 1.0))
    # print(_random(_rng, Vec3, 1.0, 10.0))

    # print(random(_rng, UnitVector))
    # print(random(_rng, Attenuation))
    # print(random(_rng, Attenuation, 1.0))
    # print(random(_rng, Attenuation, 1.0, 10.0))
    with let: v3 = random_in_hemisphere(_rng, Vec3, vec3(0.0, 0.0, 1.0))
    print(v3.x, v3.y, v3.z)
    print(v3.x*v3.x+v3.y*v3.y+v3.z*v3.z)


    # Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   std/math,
#   ./primitives,
#   ./support/rng

# export rng

# # Random routines
# # ------------------------------------------------------

# func random*(rng: var Rng, _: type float64): float64 {.inline.} =
#   rng.uniform(float64)

# func random*(rng: var Rng, _: type float64, max: float64): float64 {.inline.} =
#   rng.uniform(max)

# func random*(rng: var Rng, _: type float64, min, max: float64): float64 {.inline.} =
#   rng.uniform(min, max)

# # Vector
# # ------------------------------------------------------

# func random(rng: var Rng, _: type Vec3): Vec3 {.inline.} =
#   result.x = rng.random(float64)
#   result.y = rng.random(float64)
#   result.z = rng.random(float64)

# func random(rng: var Rng, _: type Vec3, max: float64): Vec3 {.inline.} =
#   result.x = rng.random(float64, max)
#   result.y = rng.random(float64, max)
#   result.z = rng.random(float64, max)

# func random(rng: var Rng,  _: type Vec3, min, max: float64): Vec3 {.inline.} =
#   result.x = rng.random(float64, min, max)
#   result.y = rng.random(float64, min, max)
#   result.z = rng.random(float64, min, max)

# func random_in_unit_sphere*(rng: var Rng, _: type Vec3): Vec3 =
#   while true:
#     let p = rng.random(Vec3, -1, 1)
#     if p.length_squared() < 1.0:
#       return p

# func random*(rng: var Rng, _: type UnitVector): UnitVector =
#   let a = rng.random(float64, 2*PI)
#   let z = rng.random(float64, -1.0, 1.0)
#   let r = sqrt(1.0 - z*z)
#   return toUV(vec3(r*cos(a), r*sin(a), z))

# func random_in_hemisphere*(rng: var Rng, _: type Vec3, normal: Vec3): Vec3 =
#   let in_unit_sphere = rng.random_in_unit_sphere(Vec3)
#   if in_unit_sphere.dot(normal) > 0.0: # In the same hemisphere as normal
#     return in_unit_sphere
#   else:
#     return -in_unit_sphere

# func random_in_unit_disk*(rng: var Rng, _: type Vec3): Vec3 =
#   while true:
#     result = vec3(rng.random(float64, -1.0, 1.0), rng.random(float64, -1.0, 1.0), 0)
#     if result.length_squared() < 1:
#       return

# # Color
# # ------------------------------------------------------

# func random*(rng: var Rng, _: type Attenuation): Attenuation {.inline.} =
#   result.x = rng.random(float64)
#   result.y = rng.random(float64)
#   result.z = rng.random(float64)

# func random*(rng: var Rng, _: type Attenuation, max: float64): Attenuation {.inline.} =
#   result.x = rng.random(float64, max)
#   result.y = rng.random(float64, max)
#   result.z = rng.random(float64, max)

# func random*(rng: var Rng, _: type Attenuation, min, max: float64): Attenuation {.inline.} =
#   result.x = rng.random(float64, min, max)
#   result.y = rng.random(float64, min, max)
#   result.z = rng.random(float64, min, max)