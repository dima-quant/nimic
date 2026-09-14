import nimic/pydefs
type
  Vec3* = object
    x*: float64
    y*: float64
    z*: float64

  Point3* {.borrow: `.`.} = distinct Vec3


proc `+`*(self: Vec3, v: Vec3): Vec3 {.inline.} =
  result = Vec3()
  result.x = self.x + v.x
  result.y = self.y + v.y
  result.z = self.z + v.z
  return result

proc point3*(x: float64, y: float64, z: float64): Point3 =
  result = Point3(Vec3())
  result.x = x
  result.y = y
  result.z = z
  return result
let
  a = point3(1.0, 2.0, 3.0)
  b = point3(4.0, 5.0, 6.0)
  c = Vec3(a) + Vec3(b)
echo(c)