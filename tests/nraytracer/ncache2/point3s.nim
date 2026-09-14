import ncode/pydefs
import vec3s
type
  Point3* {.borrow: `.`.} = distinct Vec3


proc `*=`*(a: var Point3, scalar: float64) {.borrow.}

proc `*`*(a: var Point3, scalar: float64): Point3 {.borrow.}

proc `*`*(scalar: float64, a: var Point3): Point3 {.borrow.}

proc `==`*(a: Point3, b: Point3): bool {.inline.} =
  return Vec3(a) == Vec3(b)

proc `$`*(a: Point3): string {.inline.} =
  return $(Vec3(a))

proc `-`*(a: Point3, b: Point3): Vec3 {.inline.} =
  result = Vec3()
  result.x = a.x - b.x
  result.y = a.y - b.y
  result.z = a.z - b.z
  return result

template `+`*(p: Point3, v: Vec3): Point3 =
  Point3(Vec3(p) + v)

template `-`*(p: Point3, v: Vec3): Point3 =
  Point3(Vec3(p) - v)

proc point3*(x: float64, y: float64, z: float64): Point3 {.inline.} =
  result = Point3(Vec3())
  result.x = x
  result.y = y
  result.z = z
  return result