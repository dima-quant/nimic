import std/strformat

type
  Person = object
    name: string
    age: Natural # Ensures the age is positive

type
  Vec3* = object
    x*: float64
    y*: float64
    z*: float64

let people = [
  Person(name: "John", age: 45),
  Person(name: "Kate", age: 30)
]

func vec3*(x, y, z: float64): Vec3 {.inline.} =
  result = Vec3()
  result.x = x
  result.y = y
  result.z = z
  return result



type
  Point3* {.borrow: `.`.} = distinct Vec3

proc point3*(x: float64, y: float64, z: float64): Point3 {.inline.} =
  result = Point3(Vec3())
  result.x = x
  result.y = y
  result.z = z
  return result

var p3 = point3(1,2,3)

for person in people:
  # Type-safe string interpolation,
  # evaluated at compile time.
  echo(fmt"{person.name} is {person.age} years old")


# Thanks to Nim's 'iterator' and 'yield' constructs,
# iterators are as easy to write as ordinary
# functions. They are compiled to inline loops.
iterator oddNumbers[Idx, T](a: array[Idx, T]): T =
  for x in a:
    if x mod 2 == 1:
      yield x

for odd in oddNumbers([3, 6, 9, 12, 15, 18]):
  echo odd
