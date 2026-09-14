import ncode/pydefs
import ncode/pystd/math
import errors
type
  Vec3* = object
    x*: float64
    y*: float64
    z*: float64

  UnitVector* {.borrow:`.`.} = distinct Vec3


proc `+=`*(u: var Vec3, v: Vec3) {.inline.} =
  for dst, src in fields(u, v):
    dst += src

proc `-=`*(u: var Vec3, v: Vec3) {.inline.} =
  for dst, src in fields(u, v):
    dst -= src

proc `*=`*(u: var Vec3, scalar: float64) {.inline.} =
  for dst in fields(u):
    dst *= scalar

proc `/=`*(u: var Vec3, scalar: float64) {.inline.} =
  for dst in fields(u):
    dst /= scalar

proc `+`*(self: Vec3, v: Vec3): Vec3 {.inline.} =
  result = type(self)()
  result.x = self.x + v.x
  result.y = self.y + v.y
  result.z = self.z + v.z
  return result

proc `-`*(self: Vec3, v: Vec3): Vec3 {.inline.} =
  result = type(self)()
  result.x = self.x - v.x
  result.y = self.y - v.y
  result.z = self.z - v.z
  return result

proc length_squared*(u: Vec3): float64 {.inline.} =
  return u.x * u.x + u.y * u.y + u.z * u.z

proc length*(u: Vec3): float64 {.inline.} =
  return sqrt(u.length_squared())

template toUV*(v: Vec3): UnitVector =
  ensureWithinRelTol(v.length_squared(), 1.0)
  UnitVector(v)

proc `-`*(u: Vec3): Vec3 {.inline.} =
  result = type(u)()
  for dst, src in fields(result, u):
    dst = -src
  return result

proc `*`*(u: Vec3, scalar: float64): Vec3 {.inline.} =
  result = type(u)()
  for dst, src in fields(result, u):
    dst = src * scalar
  return result

proc `*`*(scalar: float64, u: Vec3): Vec3 {.inline.} =
  return u * scalar

proc `/`*(self: Vec3, scalar: float64): Vec3 {.inline.} =
  return self * (1.0 / scalar)

proc dot*(u: Vec3, v: Vec3): float64 {.inline.} =
  return u.x * v.x + u.y * v.y + u.z * v.z

proc cross*(u: Vec3, v: Vec3): Vec3 {.inline.} =
  result = type(u)()
  result.x = u.y * v.z - u.z * v.y
  result.y = u.z * v.x - u.x * v.z
  result.z = u.x * v.y - u.y * v.x
  return result

proc unit_vector*(self: Vec3): UnitVector {.inline.} =
  return UnitVector(self / self.length())

converter toVec3*(uv: UnitVector): Vec3 {.inline.} =
  Vec3(uv)

proc vec3*(x: float64, y: float64, z: float64): Vec3 {.inline.} =
  result = Vec3()
  result.x = x
  result.y = y
  result.z = z
  return result