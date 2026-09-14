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
# Internals
from core import HitRecord, Material, material
from primitives import Point3, CTime


class MovingSphere(Object):
  # From book 2
    center0: Point3
    center1: Point3
    time0: CTime
    time1: CTime
    radius: float64
    material: Material

    def center(self: MovingSphere, time: CTime) -> Point3:
        return self.center0 + (time - self.time0) / (self.time1 - self.time0) * (self.center1 - self.center0)
    
    @template_expand
    def hit(self: MovingSphere, r: Ray, t_min: float64, t_max: float64, rec: mut @ HitRecord) -> bool:
        with let:
            oc = r.origin - self.center(r.time)
            a = r.direction.length_squared()
            half_b = oc.dot(r.direction)
            c = oc.length_squared() - self.radius*self.radius
            discriminant = half_b*half_b - a*c

        if discriminant > 0:
            with let:
                root = sqrt(discriminant)    
            @template 
            def _checkSol(root: untyped) -> untyped:
                """{.dirty.}"""
                with block:
                    with let:
                        sol = root
                    if t_min < sol and sol < t_max:
                        rec.t = sol
                        rec.p = r.at(rec.t)
                        with let:
                            outward_normal = (rec.p - self.center(r.time)) / self.radius
                        rec.set_face_normal(r, outward_normal)
                        rec.material = self.material
                        return True
            _checkSol((-half_b - root)/a)
            _checkSol((-half_b + root)/a)
        return False
    

@dispatch
def movingSphere(
       center0: Point3, time0: CTime,
       center1: Point3, time1: CTime,
       radius: float64, material: Material) -> MovingSphere:
    """{.inline.}"""
    result = MovingSphere()
    result.center0 = center0
    result.center1 = center1
    result.time0 = time0
    result.time1 = time1
    result.radius = radius
    result.material = material
    return result

@dispatch
def movingSphere[T](
       center0: Point3, time0: CTime,
       center1: Point3, time1: CTime,
       radius: float64, materialKind: T) -> MovingSphere:
    """{.inline.}"""
    return movingSphere(center0, time0, center1, time1, radius, material(materialKind))

# Sanity checks
# -----------------------------------------------------
# assert Hittable.is_concept_of(MovingSphere)

# static: doAssert MovingSphere is Hittable



# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # Stdlib
#   std/math,
#   # Internals
#   ../core,
#   ../../primitives

# type MovingSphere* = object
#   # From book 2
#   center0, center1*: Point3
#   time0, time1: Time
#   radius*: float64
#   material*: Material

# func movingSphere*(
#        center0: Point3, time0: Time,
#        center1: Point3, time1: Time,
#        radius: float64, material: Material): MovingSphere {.inline.} =
#   result.center0 = center0
#   result.center1 = center1
#   result.time0 = time0
#   result.time1 = time1
#   result.radius = radius
#   result.material = material

# func movingSphere*[T](
#        center0: Point3, time0: Time,
#        center1: Point3, time1: Time,
#        radius: float64, materialKind: T): MovingSphere {.inline.} =
#   movingSphere(center0, time0, center1, time1, radius, material(materialKind))

# func center*(self: MovingSphere, time: Time): Point3 =
#   self.center0 +
#     (
#       (time - self.time0) / (self.time1 - self.time0) *
#       (self.center1 - self.center0)
#     )

# func hit*(self: MovingSphere, r: Ray, t_min, t_max: float64, rec: var HitRecord): bool =
#   let oc = r.origin - self.center(r.time)
#   let a = r.direction.length_squared()
#   let half_b = oc.dot(r.direction)
#   let c = oc.length_squared() - self.radius*self.radius
#   let discriminant = half_b*half_b - a*c

#   if discriminant > 0:
#     let root = discriminant.sqrt()
#     template checkSol(root: untyped): untyped {.dirty.} =
#       block:
#         let sol = root
#         if t_min < sol and sol < t_max:
#           rec.t = sol
#           rec.p = r.at(rec.t)
#           let outward_normal = (rec.p - self.center(r.time)) / self.radius
#           rec.set_face_normal(r, outward_normal)
#           rec.material = self.material
#           return true
#     checkSol((-half_b - root)/a)
#     checkSol((-half_b + root)/a)
#   return false

# # Sanity checks
# # -----------------------------------------------------

# static: doAssert MovingSphere is Hittable