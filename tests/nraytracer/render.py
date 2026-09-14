# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from math import inf
# Internals
from primitives import Canvas, Color, Ray, color, draw, attenuation
from sampling import Rng, random
from core import HitRecord
from hittables import HittableList
from cameras import Camera
from materials import scatter

# Rendering routines
# ------------------------------------------------------------------------

def radiance(ray: Ray, world: HittableList, max_depth: nint, rng: mut @ Rng) -> Color:
    with var:
        _attenuation = attenuation(1.0, 1.0, 1.0)
        ray = ray.copy() # create mutable copy

    for _ in range(max_depth):
        # Hit surface?
        with var:
           rec = HitRecord()
        with let:
           maybeRec = world.hit(ray, 0.001, inf, rec)
        if maybeRec:
            with var:
                materialAttenuation = attenuation()
                scattered = Ray()
            with let:
                maybeScatter = scatter(rec.material, ray, rec, rng, materialAttenuation, scattered)
            # Bounce on surface
            if maybeScatter:
                _attenuation *= materialAttenuation
                ray = scattered
                continue
            return color(0, 0, 0)

        # No hit
        with let:
            unit_direction = ray.direction.unit_vector()
            t = 0.5 * unit_direction.y + 1.0
        result = (1.0 - t) * color(1, 1, 1) + t * color(0.5, 0.7, 1)
        result *= _attenuation
        return result

    return color(0, 0, 0)

def render(canvas: mut @ Canvas, cam: Camera, world: HittableList, max_depth: nint):

    with let:
        canvas = addr(canvas) # Mutable
        #cam = unsafeAddr(cam) # Too big for capture

    #parallelFor row in 0 ..< canvas.nrows:
    for row in range(canvas.nrows):
        # captures: {canvas, cam, world, max_depth}
        #parallelFor col in 0 ..< canvas.ncols:
        for col in range(canvas.ncols):
            # captures: {row, canvas, cam, world, max_depth}
            with var:
                rng = Rng()   # We reseed per pixel to be able to parallelize the outer loops
            rng.seed(row, col) # And use a "perfect hash" as the seed
            with var:
                pixel = color(0, 0, 0)
            for _ in range(canvas.samples_per_pixel):
                # loadBalance(Weave)
                with let:
                    u = (float64(col) + random(rng, float64)) / float64(canvas.ncols - 1)
                    v = (float64(row) + random(rng, float64)) / float64(canvas.nrows - 1)
                    r = cam.ray(u, v, rng)
                    rad = radiance(r, world, max_depth, rng)
                pixel += rad
            draw(canvas.contents, row, col, pixel)


# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # Standard library

#   # 3rd party
#   weave,
#   # Internal
#   ./primitives,
#   ./sampling,
#   ./physics/[core, hittables, cameras, materials]

# # Rendering routines
# # ------------------------------------------------------------------------

# func radiance*(ray: Ray, world: Hittable, max_depth: int, rng: var Rng): Color =
#   var attenuation = attenuation(1.0, 1.0, 1.0)
#   var ray = ray

#   for _ in 0 ..< max_depth:
#     # Hit surface?
#     var rec: HitRecord
#     let maybeRec = world.hit(ray, 0.001, Inf, rec)
#     if maybeRec:
#       var materialAttenuation: Attenuation
#       var scattered: Ray
#       let maybeScatter = rec.material.scatter(ray, rec, rng, materialAttenuation, scattered)
#       # Bounce on surface
#       if maybeScatter:
#         attenuation *= materialAttenuation
#         ray = scattered
#         continue
#       return color(0, 0, 0)

#     # No hit
#     let unit_direction = ray.direction.unit_vector()
#     let t = 0.5 * unit_direction.y + 1.0
#     result = (1.0 - t) * color(1, 1, 1) + t*color(0.5, 0.7, 1)
#     result *= attenuation
#     return

#   return color(0, 0, 0)

# proc render*(canvas: var Canvas, cam: Camera, world: HittableList, max_depth: int) =


#   let canvas = canvas.addr # Mutable
#   let cam = cam.unsafeAddr # Too big for capture

#   parallelFor row in 0 ..< canvas.nrows:
#     captures: {canvas, cam, world, max_depth}
#     parallelFor col in 0 ..< canvas.ncols:
#       captures: {row, canvas, cam, world, max_depth}
#       var rng: Rng   # We reseed per pixel to be able to parallelize the outer loops
#       rng.seed(row, col) # And use a "perfect hash" as the seed
#       var pixel = color(0, 0, 0)
#       for _ in 0 ..< canvas.samples_per_pixel:
#         loadBalance(Weave)
#         let u = (col.float64 + rng.random(float64)) / float64(canvas.ncols - 1)
#         let v = (row.float64 + rng.random(float64)) / float64(canvas.nrows - 1)
#         let r = cam[].ray(u, v, rng)
#         pixel += radiance(r, world, max_depth, rng)
#       canvas[].draw(row, col, pixel)

