import ncode/pydefs
import std/os
import std/paths
import std/strformat
import std/strutils
import primitives

proc exportToPPM*(canvas: Canvas, f: TextIOWrapper) =

  template local_conv(c: float64): nint =
    nint(256 * clamp(c, 0.0, 0.999))
  f.write(&"P3\n{canvas.ncols} {canvas.nrows}\n255\n")
  for i in countdown(canvas.nrows - 1, 0):
    for j in range(canvas.ncols):
      let
        pixel = canvas[i, j]
        r = pixel.x
        g = pixel.y
        b = pixel.z
      f.write(&"{local_conv(r)} {local_conv(g)} {local_conv(b)}\n")

proc exportToPPM*(canvas: Canvas, path: string, imageSeries: string, sceneID: nint) =

  template local_conv(c: float64): nint =
    nint(256 * clamp(c, 0.0, 0.999))
  let
    f = open($(Path(path) / Path(imageSeries + "_" + intToStr(sceneID, minchars=5) + ".ppm")), fmWrite)
  try:
    f.write(&"P3\n{canvas.ncols} {canvas.nrows}\n255\n")
    for i in countdown(canvas.nrows - 1, 0):
      for j in range(canvas.ncols):
        let
          pixel = canvas[i, j]
          r = pixel.x
          g = pixel.y
          b = pixel.z
        f.write(&"{local_conv(r)} {local_conv(g)} {local_conv(b)}\n")
  finally:
    f.close()