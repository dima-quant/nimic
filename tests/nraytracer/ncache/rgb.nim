import ncode/pydefs
import primitives
type
  RGB_Raw* = object
    r*: uint8
    g*: uint8
    b*: uint8


proc toRGB_Raw*(canvas: Canvas): seq[RGB_Raw] =

  template local_conv(c: float64): uint8 =
    uint8(256 * clamp(c, 0.0, 0.999))
  result.newSeq(canvas.nrows * canvas.ncols)
  for i in countdown(canvas.nrows - 1, 0):
    for j in range(canvas.ncols):
      result[i * canvas.ncols + j].r = local_conv(canvas[canvas.nrows - i, j].x)
      result[i * canvas.ncols + j].g = local_conv(canvas[canvas.nrows - i, j].y)
      result[i * canvas.ncols + j].b = local_conv(canvas[canvas.nrows - i, j].z)
  return result