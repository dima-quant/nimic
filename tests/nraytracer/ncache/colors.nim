import ncode/pydefs
import vec3s
type
  Color* {.borrow: `.`.} = distinct Vec3

  Attenuation* {.borrow: `.`.} = distinct Color


proc `==`*(a: Color, b: Color): bool {.inline.} =
  return Vec3(a) == Vec3(b)

proc `$`*(a: Color): string {.inline.} =
  return $(Vec3(a))

proc `*=`*(self: var Color, scalar: float64) {.borrow.}

proc `*`*(self: Color, scalar: float64): Color {.borrow.}

proc `*`*(scalar: float64, self: Color): Color {.borrow.}

proc `+=`*(self: var Color, other: Color) {.borrow.}

proc `+`*(self: Color, other: Color): Color {.borrow.}

proc `-`*(self: Color, other: Color): Color {.borrow.}

proc `*=`*(self: var Color, b: Attenuation) {.inline.} =
  self.x *= b.x
  self.y *= b.y
  self.z *= b.z

proc `*=`*(a: var Attenuation, b: Attenuation) {.inline.} =
  a.x *= b.x
  a.y *= b.y
  a.z *= b.z

proc `*`*(a: Attenuation, b: Attenuation): Attenuation {.inline.} =
  result = Attenuation(Color(Vec3()))
  result.x = a.x * b.x
  result.y = a.y * b.y
  result.z = a.z * b.z
  return result

proc attenuation*(x: float64, y: float64, z: float64): Attenuation {.inline.} =
  result = Attenuation(Color(Vec3()))
  result.x = x
  result.y = y
  result.z = z
  return result

proc attenuation*(): Attenuation {.inline.} =
  result = Attenuation(Color(Vec3()))
  return result

proc color*(x: float64, y: float64, z: float64): Color {.inline.} =
  result = Color(Vec3())
  result.x = x
  result.y = y
  result.z = z
  return result