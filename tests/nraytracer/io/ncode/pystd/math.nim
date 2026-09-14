import
  std/math

template radians*(deg: float64): float64 =
  degToRad deg

template degrees*(rad: float64): float64 =
  radToDeg rad

const
  pi* = PI

export
  math