import ncode/pydefs
import ncode/pystd/math
import core
import primitives
type
  MovingSphere* = object
    center0*: Point3
    center1*: Point3
    time0*: CTime
    time1*: CTime
    radius*: float64
    material*: Material


proc center*(self: MovingSphere, time: CTime): Point3 =
  return self.center0 + (time - self.time0) / (self.time1 - self.time0) * (self.center1 - self.center0)

proc hit*(self: MovingSphere, r: Ray, t_min: float64, t_max: float64, rec: var HitRecord): bool =
  let
    oc = r.origin - self.center(r.time)
    a = r.direction.length_squared()
    half_b = oc.dot(r.direction)
    c = oc.length_squared() - self.radius * self.radius
    discriminant = half_b * half_b - a * c
  if discriminant > 0:
    let
      root = sqrt(discriminant)

    template local_checkSol(root: untyped): untyped {.dirty.} =
      block:
        let
          sol = root
        if t_min < sol and sol < t_max:
          rec.t = sol
          rec.p = r.at(rec.t)
          let
            outward_normal = (rec.p - self.center(r.time)) / self.radius
          rec.set_face_normal(r, outward_normal)
          rec.material = self.material
          return true
    local_checkSol((-half_b - root) / a)
    local_checkSol((-half_b + root) / a)
  return false

proc movingSphere*(center0: Point3, time0: CTime, center1: Point3, time1: CTime, radius: float64, material: Material): MovingSphere {.inline.} =
  result = MovingSphere()
  result.center0 = center0
  result.center1 = center1
  result.time0 = time0
  result.time1 = time1
  result.radius = radius
  result.material = material
  return result

proc movingSphere*[T](center0: Point3, time0: CTime, center1: Point3, time1: CTime, radius: float64, materialKind: T): MovingSphere {.inline.} =
  return movingSphere(center0, time0, center1, time1, radius, material(materialKind))