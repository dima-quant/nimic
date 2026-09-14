# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.os import *
from nimic.std.paths import *
from nimic.std.strformat import *
from nimic.std.strutils import *
from primitives import Canvas, clamp

@dispatch
def exportToPPM(canvas: Canvas, f: TextIOWrapper):
    @template
    def _conv(c: float64) -> nint:
        return nint(256 * clamp(c, 0.0, 0.999))

    f.write(f"P3\n{canvas.ncols} {canvas.nrows}\n255\n")

    for i in countdown(canvas.nrows-1, 0):
        for j in range(canvas.ncols):
            # Write the translated [0, 255] value of each color component
            with let:
                pixel = canvas[i, j]
                r = pixel.x
                g = pixel.y
                b = pixel.z
            f.write(f"{_conv(r)} {_conv(g)} {_conv(b)}\n")

@dispatch
def exportToPPM(canvas: Canvas, path: string, imageSeries: string, sceneID: nint):
    @template
    def _conv(c: float64) -> nint:
        return nint(256 * clamp(c, 0.0, 0.999))

    with let: f = open(
              str(Path(path) / Path(imageSeries + "_" + int_to_str(sceneID, minchars = 5) + ".ppm")),
              fmWrite
            )
    try:
        f.write(f"P3\n{canvas.ncols} {canvas.nrows}\n255\n")

        for i in countdown(canvas.nrows-1, 0):
            for j in range(canvas.ncols):
                # Write the translated [0, 255] value of each color component
                with let:
                    pixel = canvas[i, j]
                    r = pixel.x
                    g = pixel.y
                    b = pixel.z
                f.write(f"{_conv(r)} {_conv(g)} {_conv(b)}\n")
    finally:
        f.close()

# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # Stdlib
#   std/[strformat, os, strutils],
#   # internal
#   ../primitives

# proc exportToPPM*(canvas: Canvas, f: File) =
#   template conv(c: float64): int =
#     int(256 * clamp(c, 0.0, 0.999))

#   f.write &"P3\n{canvas.ncols} {canvas.nrows}\n255\n"

#   for i in countdown(canvas.nrows-1,0):
#     for j in 0 ..< canvas.ncols:
#       # Write the translated [0, 255] value of each color component
#       let pixel = canvas[i, j]
#       let r = pixel.x
#       let g = pixel.y
#       let b = pixel.z
#       f.write &"{conv(r)} {conv(g)} {conv(b)}\n"

# proc exportToPPM*(canvas: Canvas, path, imageSeries: string, sceneID: int) =
#   template conv(c: float64): int =
#     int(256 * clamp(c, 0.0, 0.999))

#   let f = open(
#             path / imageSeries & "_" &
#             intToStr(sceneID, minchars = 5) & ".ppm",
#             fmWrite
#           )
#   defer: f.close()

#   f.write &"P3\n{canvas.ncols} {canvas.nrows}\n255\n"

#   for i in countdown(canvas.nrows-1,0):
#     for j in 0 ..< canvas.ncols:
#       # Write the translated [0, 255] value of each color component
#       let pixel = canvas[i, j]
#       let r = pixel.x
#       let g = pixel.y
#       let b = pixel.z
#       f.write &"{conv(r)} {conv(g)} {conv(b)}\n"