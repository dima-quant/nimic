# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from primitives import Point3, Vec3, Attenuation, Ray

# Type declarations
# ------------------------------------------------------------------------------------------

class Lambertian(Object):
    albedo: Attenuation
class Metal(Object):
    albedo: Attenuation
    fuzz: float64
class Dielectric(Object):
    refraction_index: float64


class MaterialKind(NIntEnum):
    kMetal = auto()
    kLambertian = auto()
    kDielectric = auto()


class Material(Object):
    kind: MaterialKind = None
    match kind:
        case MaterialKind.kMetal:
            fMetal: Metal

        case MaterialKind.kLambertian:
            fLambertian: Lambertian

        case MaterialKind.kDielectric:
            fDielectric: Dielectric

@dispatch
def material(subtype: Metal) -> Material:
    """{.inline, noSideEffect.}"""
    result = Material(kind=MaterialKind.kMetal, fMetal=subtype)
    return result

@dispatch
def material(subtype: Lambertian) -> Material:
    """{.inline, noSideEffect.}"""
    result = Material(kind=MaterialKind.kLambertian, fLambertian=subtype)
    return result

@dispatch
def material(subtype: Dielectric) -> Material:
    """{.inline, noSideEffect.}"""
    result = Material(kind=MaterialKind.kDielectric, fDielectric=subtype)
    return result

class HitRecord(Object):
    p: Point3
    normal: Vec3
    material: Material
    t: float64        # t_min < t < t_max, the ray position
    front_face: bool

    def set_face_normal(rec: mut @ HitRecord, r: Ray, outward_normal: Vec3):
        """{.noSideEffect,inline.}"""
        rec.front_face = r.direction.dot(outward_normal) < 0
        rec.normal = outward_normal if rec.front_face  else -outward_normal

# Routines
# ------------------------------------------------------------------------------------------

# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   ../primitives,
#   ../support/emulate_classes_with_ADTs

# # Type declarations
# # ------------------------------------------------------------------------------------------

# type
#   Lambertian* = object
#     albedo*: Attenuation
#   Metal* = object
#     albedo*: Attenuation
#     fuzz*: float64
#   Dielectric* = object
#     refraction_index*: float64

# declareClass(Material)
# registerSubType(Material, Lambertian)
# registerSubType(Material, Metal)
# registerSubType(Material, Dielectric)
# generateClass(Material, material)

# type
#   HitRecord* = object
#     p*: Point3
#     normal*: Vec3
#     material*: Material
#     t*: float64        # t_min < t < t_max, the ray position
#     front_face*: bool

#   Hittable* = concept self
#     # All hittables implement
#     # func hit(self: Hittable, r: Ray, t_min: float64, t_max: float64): Option[HitRecord]
#     # We use Option instead of passing a mutable reference like in the tutorial.
#     self.hit(Ray, float64, float64, var HitRecord) is bool

# # Routines
# # ------------------------------------------------------------------------------------------

# func set_face_normal*(rec: var HitRecord, r: Ray, outward_normal: Vec3) {.inline.} =
#   rec.front_face = r.direction.dot(outward_normal) < 0
#   rec.normal = if rec.front_face: outward_normal else: -outward_normal

  # Output

  # # Compile-time
  # # -------------------------------------------
  # type
  #   MaterialKind = enum
  #     kMetal, kLambertian, kDielectric
  #   Material = object case kind*: MaterialKind
  #   of kMetal:
  #       fMetal: Metal

  #   of kLambertian:
  #       fLambertian: Lambertian

  #   of kDielectric:
  #       fDielectric: Dielectric

  # func material(subtype: Metal): Material {.inline.} =
  #   result = Material(kind: kMetal, fMetal: subtype)

  # func material(subtype: Lambertian): Material {.inline.} =
  #   result = Material(kind: kLambertian, fLambertian: subtype)

  # func material(subtype: Dielectric): Material {.inline.} =
  #   result = Material(kind: kDielectric, fDielectric: subtype)

  # func scatter(self: Material; r_in: Ray; rec: HitRecord): Option[
  #     tuple[attenuation: Color, scattered: Ray]] =
  #   result = case self.kind
  #   of kMetal:
  #     scatter(self.fMetal, r_in, rec)
  #   of kLambertian:
  #     scatter(self.fLambertian, r_in, rec)
  #   of kDielectric:
  #     scatter(self.fDielectric, r_in, rec)

  # # Runtime
  # # -------------------------------------------
  # Scatter on Lambertian
