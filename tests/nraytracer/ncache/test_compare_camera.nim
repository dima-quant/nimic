import ncode/pydefs
import ncode/pystd/math
import safe_math

proc test_camera_rotation*() =
  var
    angle = Radians(2.0 * pi)
  let
    step = Radians(2.0 * pi / 1200.0)
  for i in range(1200):
    angle -= step
    if i mod 100 == 0:
      echo(i, " ", float64(angle))
  echo("final ", float64(angle))
when isMainModule:
  test_camera_rotation()