import ncode/pydefs
import scenes_animated

proc test_atime_accumulation*() =
  var
    t = ATime(0.0)
  let
    dt = ATime(0.005)
  for i in range(400):
    t += dt
    if i mod 50 == 0:
      echo(i, " ", float32(t))
  echo("final ", float32(t))
when isMainModule:
  test_atime_accumulation()