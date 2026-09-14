import ncode/pydefs
import ncode/pystd/math
import vec3s
import point3s
import timing
type
  Ray* = object
    origin*: Point3
    direction*: Vec3
    time*: Time


proc at*(ray: Ray, t: float64): Point3 {.inline.} =
  return ray.origin + t * ray.direction

proc ray*(origin: Point3, direction: Vec3, time=Time(0.0)): Ray {.inline.} =
  result = Ray()
  result.origin = origin
  result.direction = direction
  result.time = time
  return result

proc reflect*(u: Vec3, n: Vec3): Vec3 {.inline.} =
  return u - 2 * u.dot(n) * n

proc refract*(uv: UnitVector, n: Vec3, etaI_over_etaT: float64): Vec3 =
  let
    cos_theta = -uv.dot(n)
    r_out_parallel = etaI_over_etaT * (uv.toVec3() + cos_theta * n)
    r_out_perpendicular = -sqrt(1.0 - r_out_parallel.length_squared()) * n
  return r_out_parallel + r_out_perpendicular