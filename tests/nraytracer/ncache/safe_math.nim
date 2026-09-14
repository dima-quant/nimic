import ncode/pydefs
import ncode/pystd/math

func clamp*(x: float64, min: float64, max: float64): float64 {.inline.} =
  if x < min:
    return min
  if x > max:
    return max
  return x
type
  Degrees* = distinct float64

  Radians* = distinct float64


proc `-=`*(a: var Radians, b: Radians) {.borrow.}

converter toF64*(rad: Radians): float64 {.inline.} =
  float64(rad)

template degToRad*(deg: Degrees): Radians =
  Radians(radians(float64(deg)))

template radToDeg*(rad: Radians): Degrees =
  Degrees(degrees(float64(rad)))