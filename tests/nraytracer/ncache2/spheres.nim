import ncode/pydefs
import ncode/pystd/math
import core
import primitives
type
  Sphere* = object
    center*: Point3
    radius*: float64
    material*: Material


proc hit*(self: Sphere, r: Ray, t_min: float64, t_max: float64, rec: var HitRecord): bool =
  let
    oc = r.origin - self.center
    a = r.direction.length_squared()
    half_b = oc.dot(r.direction)
    c = oc.length_squared() - self.radius * self.radius
    discriminant = half_b * half_b - a * c
  if discriminant > 0:
    let
      root = sqrt(discriminant)
    block:
      let
        sol = (-half_b - root) / a
      if t_min < sol and sol < t_max:
        rec.t = sol
        rec.p = r.at(rec.t)
        let
          outward_normal = (rec.p - self.center) / self.radius
        rec.set_face_normal(r, outward_normal)
        rec.material = self.material
        return true
    block:
      let
        sol = (-half_b + root) / a
      if t_min < sol and sol < t_max:
        rec.t = sol
        rec.p = r.at(rec.t)
        let
          outward_normal = (rec.p - self.center) / self.radius
        rec.set_face_normal(r, outward_normal)
        rec.material = self.material
        return true
  return false

proc sphere*(center: Point3, radius: float64, material: Material): Sphere {.inline.} =
  result = Sphere()
  result.center = center
  result.radius = radius
  result.material = material
  return result

proc sphere*[T](center: Point3, radius: float64, materialKind: T): Sphere {.inline.} =
  return sphere(center, radius, material(materialKind))