import ncode/pydefs
import scenes_animated

proc test_mixed_precision_mul*() =
  for i in range(20):
    let
      dt = ATime(0.001 * float32(i + 1))
    let
      result = G * dt
    echo(i, " ", float64(result))
when isMainModule:
  test_mixed_precision_mul()