# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from math import tan
from primitives import Point3, Vec3, CTime, Ray, ray, Degrees, degToRad
from sampling import Rng, random_in_unit_disk, random

class Camera(Object):
    origin: Point3
    lower_left_corner: Point3
    horizontal: Vec3
    vertical: Vec3
    u: Vec3
    v: Vec3
    w: Vec3   # Orthonormal basis that describe camera orientation
    lens_radius: float64
    shutterOpen: CTime
    shutterClose: CTime

    def ray(self: Camera, s: float64, t: float64, var_rng: mut @ Rng) -> Ray:
        with let:
            rd = self.lens_radius * random_in_unit_disk(var_rng, Vec3)
            offset = self.u*rd.x + self.v*rd.y
        result = ray(
            origin = self.origin + offset,
            direction = self.lower_left_corner +
                        s*self.horizontal +
                        t*self.vertical -
                        self.origin - offset,
            time = random(var_rng, float64, self.shutterOpen, self.shutterClose)
        )
        return result

def camera(lookFrom: Point3, lookAt: Point3, view_up: Vec3,
             vertical_field_of_view: Degrees, aspect_ratio: float64,
             aperture: float64, focus_distance: float64,
             shutterOpen = CTime(0.0), shutterClose = CTime(0.0)
            ) -> Camera:
    with let:
        theta = degToRad(vertical_field_of_view)
        h = tan(theta/2.0)
        viewport_height = 2.0 * h
        viewport_width = aspect_ratio * viewport_height

    result = Camera()
    result.w = (lookFrom - lookAt).unit_vector()
    result.u = (view_up.cross(result.w)).unit_vector()
    result.v = result.w.cross(result.u)
    result.origin = lookFrom
    result.horizontal = focus_distance * viewport_width * result.u
    result.vertical = focus_distance * viewport_height * result.v
    result.lower_left_corner = result.origin - result.horizontal/2 - result.vertical/2 - focus_distance*result.w
    result.lens_radius = aperture/2
    result.shutterOpen = shutterOpen
    result.shutterClose = shutterClose

    return result

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
#   ../primitives,
#   ../sampling

# type Camera* = object
#   origin: Point3
#   lower_left_corner: Point3
#   horizontal: Vec3
#   vertical: Vec3
#   u, v, w: Vec3   # Orthonormal basis that describe camera orientation
#   lens_radius: float64
#   shutterOpen, shutterClose: Time

# func camera*(lookFrom, lookAt: Point3, view_up: Vec3,
#              vertical_field_of_view: Degrees, aspect_ratio: float64,
#              aperture, focus_distance: float64,
#              shutterOpen, shutterClose = Time(0.0)
#             ): Camera =
#   let theta = vertical_field_of_view.degToRad()
#   let h = tan(theta/2.0)
#   let viewport_height = 2.0 * h
#   let viewport_width = aspect_ratio * viewport_height

#   result.w = unit_vector(lookFrom - lookAt)
#   result.u = unit_vector(view_up.cross(result.w))
#   result.v = result.w.cross(result.u)

#   result.origin = lookFrom
#   result.horizontal = focus_distance * viewport_width * result.u
#   result.vertical = focus_distance * viewport_height * result.v
#   result.lower_left_corner = result.origin - result.horizontal/2 -
#                              result.vertical/2 - focus_distance*result.w
#   result.lens_radius = aperture/2
#   result.shutterOpen = shutterOpen
#   result.shutterClose = shutterClose

# func ray*(self: Camera, s, t: float64, rng: var Rng): Ray =
#   let rd = self.lens_radius * rng.random_in_unit_disk(Vec3)
#   let offset = self.u*rd.x + self.v*rd.y
#   ray(
#     origin = self.origin + offset,
#     direction = self.lower_left_corner +
#                   s*self.horizontal +
#                   t*self.vertical -
#                   self.origin - offset,
#     time = rng.random(float64, self.shutterOpen, self.shutterClose)
#   )
