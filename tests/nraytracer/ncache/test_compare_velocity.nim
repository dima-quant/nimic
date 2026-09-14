import ncode/pydefs
import scenes_animated

proc test_velocity_borrow_sub*() =
  var
    v = local_Velocity(5.0)
  let
    dt = ATime(0.005)
  for i in range(200):
    v -= G * dt
    if i mod 20 == 0:
      echo(i, " ", float64(v))
  echo("final ", float64(v))
when isMainModule:
  test_velocity_borrow_sub()