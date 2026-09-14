# /// nimic
#
# ///
# Trace of Radiance
# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)

from __future__ import annotations
from nimic.ntypes import *

from primitives import Canvas, clamp

class RGB_Raw(Object):
    r: uint8
    g: uint8
    b: uint8

def toRGB_Raw(canvas: Canvas) -> seq[RGB_Raw]:
    @template
    def _conv(c: float64) -> uint8:
        return uint8(256 * clamp(c, 0.0, 0.999))

    result.newSeq(canvas.nrows * canvas.ncols)

    for i in countdown(canvas.nrows - 1, 0):
        for j in range(canvas.ncols):
            result[i * canvas.ncols + j].r = _conv(canvas[canvas.nrows - i, j].x)
            result[i * canvas.ncols + j].g = _conv(canvas[canvas.nrows - i, j].y)
            result[i * canvas.ncols + j].b = _conv(canvas[canvas.nrows - i, j].z)

    return result

# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # internal
#   ../primitives

# type RGB_Raw* = object
#   ## Gamma-corrected RGB
#   ## Stored in RGB RGB RGB order
#   r*, g*, b*: uint8

# func toRGB_Raw*(canvas: Canvas): seq[RGB_Raw] =
#   ## Export a canvas to a raw RGB buffer
#   ## with data stored in RGB RGB RGB order

#   template conv(c: float64): uint8 =
#     uint8(256 * clamp(c, 0.0, 0.999))

#   result.newSeq(canvas.nrows * canvas.ncols)

#   for i in countdown(canvas.nrows-1, 0):
#     for j in 0 ..< canvas.ncols:
#       # Write the translated [0, 255] value of each color component
#       result[i*canvas.ncols + j].r = canvas[canvas.nrows-i, j].x.conv()
#       result[i*canvas.ncols + j].g = canvas[canvas.nrows-i, j].y.conv()
#       result[i*canvas.ncols + j].b = canvas[canvas.nrows-i, j].z.conv()
