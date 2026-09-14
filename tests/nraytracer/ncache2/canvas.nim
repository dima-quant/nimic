import ncode/pydefs
import std/math
import system/ansi_c
import colors
type
  Canvas* = object
    pixels*: ptr UncheckedArray[Color]
    nrows*: int32
    ncols*: int32
    samples_per_pixel*: int32
    gamma_correction*: float32


proc `[]`*(canvas: Canvas, row: SomeInteger, col: SomeInteger): Color {.inline.} =
  return canvas.pixels[row * canvas.ncols + col]

proc delete*(canvas: var Canvas) {.inline.} =
  if not canvas.pixels.isNil:
    c_free(canvas.pixels)

proc newCanvas*(height: SomeInteger, width: SomeInteger, samples_per_pixel: SomeInteger, gamma_correction: SomeFloat): Canvas =
  result = Canvas()
  result.nrows = int32(height)
  result.ncols = int32(width)
  result.samples_per_pixel = int32(samples_per_pixel)
  result.pixels = cast[ptr UncheckedArray[Color]](c_malloc(csize_t(height * width * sizeof(Color))))
  result.gamma_correction = float32(gamma_correction)
  return result

proc draw*(canvas: var Canvas, row: SomeInteger, col: SomeInteger, pixel: Color) {.inline.} =
  let
    scale = 1.0 / float64(canvas.samples_per_pixel)
    gamma = 1.0 / float64(canvas.gamma_correction)
    pos = row * canvas.ncols + col
  echo(pos, pixel.x, pixel.y, pixel.z)
  canvas.pixels[pos].x = pow(scale * pixel.x, gamma)
  canvas.pixels[pos].y = pow(scale * pixel.y, gamma)
  canvas.pixels[pos].z = pow(scale * pixel.z, gamma)