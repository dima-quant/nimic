# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

# Stdlib
from math import pow, sqrt
# Internal
from core import Lambertian, Metal, Dielectric, HitRecord, Material, MaterialKind
from primitives import Attenuation, attenuation, reflect, refract, Ray, ray, Vec3, UnitVector
from sampling import Rng, random, random_in_unit_sphere


# Lambert / Diffuse Materials
# ------------------------------------------------------------------------------------------

def lambertian(albedo: Attenuation) -> Lambertian:
    """{.noSideEffect,inline.}"""
    result = Lambertian()
    result.albedo = albedo
    return result

@dispatch
def _scatter(self: Lambertian, r_in: Ray,
              rec: HitRecord, rng: mut @ Rng,
              attenuation: mut @ Attenuation, scattered: mut @ Ray) -> bool:
    """{.noSideEffect,inline.}"""
    with let:
        scatter_direction = rec.normal + random(rng, UnitVector).toVec3()
    scattered <<= ray(rec.p, scatter_direction, r_in.time)
    attenuation <<= self.albedo
    return True

# Metal Materials
# ------------------------------------------------------------------------------------------

def metal(albedo: Attenuation, fuzz: float64) -> Metal:
    """{.noSideEffect,inline.}"""
    result = Metal()
    result.albedo = albedo
    result.fuzz = min(fuzz, 1)
    return result

@dispatch
def _scatter(self: Metal, r_in: Ray,
              rec: HitRecord, rng: mut @ Rng,
              attenuation: mut @ Attenuation, scattered: mut @ Ray) -> bool:
    """{.noSideEffect.}"""
    with let:
        reflected = reflect(r_in.direction.unit_vector(), rec.normal)
    scattered <<= ray(rec.p, reflected + self.fuzz * random_in_unit_sphere(rng, Vec3))
    if scattered.direction.dot(rec.normal) > 0:
        attenuation <<= self.albedo
        return True
    return False

# Dielectric / Glass Materials
# ------------------------------------------------------------------------------------------

def dielectric(refraction_index: float64) -> Dielectric:
    """{.noSideEffect,inline.}"""
    result = Dielectric()
    result.refraction_index = refraction_index
    return result

def _schlick(cosine: float64, refraction_index: float64) -> float64:
    """{.noSideEffect.}"""
    ## Glass reflectivity depends on the angle (i.e. it may become a mirror)
    ## This is a polynomial approximation of that
    with var:
        r0 = (1-refraction_index) / (1+refraction_index)
    r0 *= r0
    return r0 + (1-r0)*pow(1-cosine, 5)

@dispatch
def _scatter(self: Dielectric, r_in: Ray,
              rec: HitRecord, rng: mut @ Rng,
              _attenuation: mut @ Attenuation, scattered: mut @ Ray) -> bool:
    """{.noSideEffect.}"""
    _attenuation <<= attenuation(1.0, 1.0, 1.0)
    with let:
         etaI_over_etaT = 1.0 / self.refraction_index if rec.front_face else self.refraction_index

    with let:
        unit_direction = r_in.direction.unit_vector()
        cos_theta = min(-unit_direction.dot(rec.normal), 1.0)
        sin_theta = sqrt(1.0 - cos_theta*cos_theta)

    if etaI_over_etaT * sin_theta > 1.0:
        with let:
            reflected = reflect(unit_direction, rec.normal)
        scattered <<= ray(rec.p, reflected)
        return True

    with let:
        reflect_prob = _schlick(cos_theta, etaI_over_etaT)
    if random(rng, float64) < reflect_prob:
        with let:
            reflected = reflect(unit_direction,rec.normal)
        scattered <<= ray(rec.p, reflected)
        return True

    with let:
        refracted = refract(unit_direction, rec.normal, etaI_over_etaT)
    scattered <<= ray(rec.p, refracted)
    return True

def scatter(self: Material, r_in: Ray,
            rec: HitRecord, rng: mut @ Rng,
            attenuation: mut @ Attenuation, scattered: mut @ Ray) -> bool:
    match self.kind:
        case MaterialKind.kMetal:
            result = _scatter(self.fMetal, r_in, rec, rng, attenuation, scattered)
        case MaterialKind.kLambertian:
            result = _scatter(self.fLambertian, r_in, rec, rng, attenuation, scattered)
        case MaterialKind.kDielectric:
            result = _scatter(self.fDielectric, r_in, rec, rng, attenuation, scattered)
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
#   # Internal
#   ./core,
#   ../primitives,
#   ../sampling,
#   # Utils
#   ../support/emulate_classes_with_ADTs

# # Lambert / Diffuse Materials
# # ------------------------------------------------------------------------------------------

# func lambertian*(albedo: Attenuation): Lambertian {.inline.} =
#   result.albedo = albedo

# func scatter(self: Lambertian, r_in: Ray,
#               rec: HitRecord, rng: var Rng,
#               attenuation: var Attenuation, scattered: var Ray): bool =
#   let scatter_direction = rec.normal + rng.random(UnitVector)
#   scattered = ray(rec.p, scatter_direction, r_in.time)
#   attenuation = self.albedo
#   return true

# # Metal Materials
# # ------------------------------------------------------------------------------------------

# func metal*(albedo: Attenuation, fuzz: float64): Metal {.inline.} =
#   result.albedo = albedo
#   result.fuzz = min(fuzz, 1)

# func scatter(self: Metal, r_in: Ray,
#               rec: HitRecord, rng: var Rng,
#               attenuation: var Attenuation, scattered: var Ray): bool =
#   let reflected = r_in.direction.unit_vector().reflect(rec.normal)
#   scattered = ray(rec.p, reflected + self.fuzz * rng.random_in_unit_sphere(Vec3))
#   if scattered.direction.dot(rec.normal) > 0:
#     attenuation = self.albedo
#     return true
#   return false

# # Dielectric / Glass Materials
# # ------------------------------------------------------------------------------------------

# func dielectric*(refraction_index: float64): Dielectric {.inline.} =
#   result.refraction_index = refraction_index

# func schlick(cosine, refraction_index: float64): float64 =
#   ## Glass reflectivity depends on the angle (i.e. it may become a mirror)
#   ## This is a polynomial approximation of that
#   var r0 = (1-refraction_index) / (1+refraction_index)
#   r0 *= r0
#   return r0 + (1-r0)*pow(1-cosine, 5)

# func scatter(self: Dielectric, r_in: Ray,
#               rec: HitRecord, rng: var Rng,
#               attenuation: var Attenuation, scattered: var Ray): bool =
#   attenuation = attenuation(1, 1, 1)
#   let etaI_over_etaT = if rec.front_face: 1.0 / self.refraction_index
#                        else: self.refraction_index

#   let unit_direction = unit_vector(r_in.direction)
#   let cos_theta = min(dot(-unit_direction, rec.normal), 1.0)
#   let sin_theta = sqrt(1.0 - cos_theta*cos_theta)

#   if etaI_over_etaT * sin_theta > 1.0:
#     let reflected = unit_direction.reflect(rec.normal)
#     scattered = ray(rec.p, reflected)
#     return true

#   let reflect_prob = schlick(cos_theta, etaI_over_etaT)
#   if rng.random(float64) < reflect_prob:
#     let reflected = unit_direction.reflect(rec.normal)
#     scattered = ray(rec.p, reflected)
#     return true

#   let refracted = unit_direction.refract(rec.normal, etaI_over_etaT)
#   scattered = ray(rec.p, refracted)
#   return true

# # Generate ADT
# # ------------------------------------------------------------------------------------------

# registerRoutine(Material):
#   func scatter*(self: Material, r_in: Ray, rec: HitRecord,
#                 rng: var Rng,
#                 attenuation: var Attenuation, scattered: var Ray): bool

# generateRoutines(Material)