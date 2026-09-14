# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *

from nimic.std.os import *
from nimic.std.strformat import *
from nimic.std.monotimes import *
from nimic.std.times import *
from primitives import newCanvas, point3, vec3, CTime, Degrees
from cameras import camera
from hittables import Scene # this declaration should present because "list" function is defined in Scene
from render import render
from scenes import random_scene
from sampling import Rng
from ppm import exportToPPM


def main():
    """
    Entry point for the program.

    This function renders a 3D scene and exports it to the standard output in PPM format.
    It also prints the time it took to render to the standard error.

    The 3D scene is randomly generated using the `random_scene` function.
    The camera position, vertical field of view, aspect ratio, aperture, and shutter open/close times
    are all hard-coded.

    The scene is rendered using the `render` function and the time it takes to render is measured using the
    `get_mono_time` function.

    The rendered image is exported to the standard output using the `exportToPPM` function.
    The time it took to render is printed to the standard error using the `write` function.
    """
    with const:
        aspect_ratio = 16.0 / 9.0
        image_width = 5#384
        image_height = nint(image_width / aspect_ratio)
        samples_per_pixel = 100
        gamma_correction = 2.2
        max_depth = 50

    with var:
        worldRNG = Rng()
    worldRNG.seed(0xFACADE)

    with let:
        world = random_scene(worldRNG)

    with let:
        lookFrom = point3(13,2,3)
        lookAt = point3(0,0,0)
        vup = vec3(0,1,0)
        dist_to_focus = 10.0
        aperture = 0.1

    with let:
        cam = camera(
              lookFrom,
              lookAt,
              vup, #view_up = vup,
              Degrees(20), #vertical_field_of_view = Degrees(20),
              aspect_ratio,
              aperture,
              dist_to_focus,
              shutterOpen = CTime(0.0),
              shutterClose = CTime(1.0)
            )
    with var:
        canvas = newCanvas(
                 image_height, image_width,
                 samples_per_pixel,
                 gamma_correction
               )

    try:
        with let: start = get_mono_time()
        # init(Weave)
        render(canvas, cam, world.list(), max_depth)
        # exit(Weave)
        with let: stop = get_mono_time()
        exportToPPM(canvas, stdout)
        stderr.write("\nDone.\n")
        with let: elapsed = in_milliseconds(stop - start)
        stderr.write(f"Time spent: {float64(elapsed) * 1e-3:>6.3f} s\n")
    finally:
        canvas.delete()

if comptime(__name__ == "__main__"):
    main()


# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # Standard library
#   std/[os, strformat, monotimes],
#   # 3rd party
#   weave,
#   # Internals
#   ./trace_of_radiance/[
#     primitives,
#     physics/cameras,
#     physics/hittables,
#     render,
#     scenes,
#     sampling,
#     io/ppm
#   ]

# import times except Time

# proc main() =
#   const aspect_ratio = 16.0 / 9.0
#   const image_width = 384
#   const image_height = int(image_width / aspect_ratio)
#   const samples_per_pixel = 100
#   const gamma_correction = 2.2
#   const max_depth = 50

#   var worldRNG: Rng
#   worldRNG.seed 0xFACADE
#   let world = worldRNG.random_scene()

#   let
#     lookFrom = point3(13,2,3)
#     lookAt = point3(0,0,0)
#     vup = vec3(0,1,0)
#     dist_to_focus = 10.0
#     aperture = 0.1

#   let cam = camera(
#               lookFrom, lookAt,
#               view_up = vup,
#               vertical_field_of_view = 20.Degrees,
#               aspect_ratio, aperture, dist_to_focus,
#               shutterOpen = 0.0.Time, shutterClose = 1.0.Time
#             )

#   var canvas = newCanvas(
#                  image_height, image_width,
#                  samples_per_pixel,
#                  gamma_correction
#                )
#   defer: canvas.delete()

#   let start = getMonoTime()
#   init(Weave)
#   canvas.render(cam, world.list(), max_depth)
#   exit(Weave)
#   let stop = getMonoTime()

#   canvas.exportToPPM stdout
#   stderr.write "\nDone.\n"
#   let elapsed = inMilliSeconds(stop - start)
#   stderr.write &"Time spent: {elapsed.float64 * 1e-3:>6.3f} s\n"

# main()

