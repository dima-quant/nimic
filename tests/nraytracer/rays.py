# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
# Stdlib
from math import sqrt
# Internal
from vec3s import Vec3, UnitVector
from point3s import Point3
from timing import CTime

class Ray(Object):
    origin: Point3
    direction: Vec3
    time: CTime

    def at(ray: Ray, t: float64) -> Point3:
        """{.inline.}"""
        return ray.origin + t * ray.direction

def ray(origin: Point3, direction: Vec3, time = CTime(0.0)) -> Ray:
    """{.inline.}"""
    result = Ray()
    result.origin = origin
    result.direction = direction
    result.time = time
    return result


def reflect(u: Vec3, n: Vec3) -> Vec3:
    """{.inline.}"""
    return u - 2*u.dot(n)*n

def refract(uv: UnitVector, n: Vec3, etaI_over_etaT: float64) -> Vec3:
    ## Snell's Law:
    ##    η sin θ = η′ sin θ′
    ## uv: unit_vector
    with let:
        cos_theta = -uv.dot(n)
        r_out_parallel = etaI_over_etaT * (uv.toVec3() + cos_theta * n)
        r_out_perpendicular = -sqrt(1.0 - r_out_parallel.length_squared()) * n
    return r_out_parallel + r_out_perpendicular


# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # Stdlib
#   std/math,
#   # Internal
#   ./vec3s, ./point3s, ./time

# type Ray* = object
#   origin*: Point3
#   direction*: Vec3
#   time*: Time

# func ray*(origin: Point3, direction: Vec3, time = Time(0.0)): Ray {.inline.} =
#   result.origin = origin
#   result.direction = direction
#   result.time = time

# func at*(ray: Ray, t: float64): Point3 {.inline.} =
#   ray.origin + t * ray.direction

# func reflect*(u, n: Vec3): Vec3 {.inline.} =
#   u - 2*dot(u, n)*n

# func refract*(uv: UnitVector, n: Vec3, etaI_over_etaT: float64): Vec3 =
#   ## Snell's Law:
#   ##    η sin θ = η′ sin θ′
#   ## uv: unit_vector
#   let cos_theta = dot(-uv, n)
#   let r_out_parallel = etaI_over_etaT * (uv + cos_theta * n)
#   let r_out_perpendicular = -sqrt(1.0 - r_out_parallel.length_squared()) * n
#   return r_out_parallel + r_out_perpendicular