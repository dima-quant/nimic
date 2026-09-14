import ncode/pydefs
import ncode/pystd/math
import primitives
import rng
export
  rng

func random*(rng: var Rng, _: type[float64]): float64 {.inline.} =
  return rng.uniform(float64)

func random*(rng: var Rng, _: type[float64], max: float64): float64 {.inline.} =
  return rng.uniform(max)

func random*(rng: var Rng, _: type[float64], min: float64, max: float64): float64 {.inline.} =
  return rng.uniform(min, max)

func local_random(rng: var Rng, _: type[Vec3]): Vec3 {.inline.} =
  result = Vec3()
  result.x = random(rng, float64)
  result.y = random(rng, float64)
  result.z = random(rng, float64)
  return result

func local_random(rng: var Rng, _: type[Vec3], max: float64): Vec3 {.inline.} =
  result = Vec3()
  result.x = random(rng, float64, max)
  result.y = random(rng, float64, max)
  result.z = random(rng, float64, max)
  return result

func local_random(rng: var Rng, _: type[Vec3], min: float64, max: float64): Vec3 {.inline.} =
  result = Vec3()
  result.x = random(rng, float64, min, max)
  result.y = random(rng, float64, min, max)
  result.z = random(rng, float64, min, max)
  return result

func random_in_unit_sphere*(rng: var Rng, _: type[Vec3]): Vec3 =
  while true:
    let
      p = local_random(rng, Vec3, -1.0, 1.0)
    if p.length_squared() < 1.0:
      return p

func random*(rng: var Rng, _: type[UnitVector]): UnitVector =
  let
    a = random(rng, float64, 2 * pi)
  let
    z = random(rng, float64, -1.0, 1.0)
  let
    r = sqrt(1.0 - z * z)
  return vec3(r * cos(a), r * sin(a), z).toUV()

func random_in_hemisphere*(rng: var Rng, _: type[Vec3], normal: Vec3): Vec3 =
  let
    in_unit_sphere = random_in_unit_sphere(rng, Vec3)
  if in_unit_sphere.dot(normal) > 0.0:
    return in_unit_sphere
  else:
    return -in_unit_sphere

func random_in_unit_disk*(rng: var Rng, _: type[Vec3]): Vec3 =
  while true:
    result = vec3(random(rng, float64, -1.0, 1.0), random(rng, float64, -1.0, 1.0), 0)
    if result.length_squared() < 1:
      return result

func random*(rng: var Rng, _: type[Attenuation]): Attenuation {.inline.} =
  result = attenuation()
  result.x = random(rng, float64)
  result.y = random(rng, float64)
  result.z = random(rng, float64)
  return result

func random*(rng: var Rng, _: type[Attenuation], max: float64): Attenuation {.inline.} =
  result = attenuation()
  result.x = random(rng, float64, max)
  result.y = random(rng, float64, max)
  result.z = random(rng, float64, max)
  return result

func random*(rng: var Rng, _: type[Attenuation], min: float64, max: float64): Attenuation {.inline.} =
  result = attenuation()
  result.x = random(rng, float64, min, max)
  result.y = random(rng, float64, min, max)
  result.z = random(rng, float64, min, max)
  return result
when isMainModule:
  var
    local_rng = Rng()
  let
    timeSeed = 54
  local_rng.seed(timeSeed)
  echo(random(local_rng, float64))
  echo(random(local_rng, float64))
  echo(random(local_rng, float64, 1.0))
  echo(random(local_rng, float64, 1.0, 10.0))
  let
    v3 = random_in_hemisphere(local_rng, Vec3, vec3(0.0, 0.0, 1.0))
  echo(v3.x, v3.y, v3.z)
  echo(v3.x * v3.x + v3.y * v3.y + v3.z * v3.z)