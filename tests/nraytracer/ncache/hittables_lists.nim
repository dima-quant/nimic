import ncode/pydefs
import hittables_variants
import core
import primitives
type
  HittableList* = object
    len*: nint
    objects*: ptr UncheckedArray[HittableVariant]

  Scene* = object
    objects*: seq[HittableVariant]


func hit*(self: HittableList, r: Ray, t_min: float64, t_max: float64, rec: var HitRecord): bool {.inline.} =
  result = false
  var
    closest_so_far = t_max
  for i in range(self.len):
    let
      hit = self.objects[i].hit(r, t_min, closest_so_far, rec)
    if hit:
      closest_so_far = rec.t
      result = true
  return result

func add*(self: var Scene, h: HittableVariant) {.inline.} =
  self.objects.add(h)

func add*[T](self: var Scene, h: T) {.inline.} =
  self.objects.add(toVariant(h))

func clear*(self: var Scene) {.inline.} =
  self.objects.set_len(0)

func list*(scene: Scene): HittableList {.inline.} =
  assert len(scene.objects) > 0
  result = HittableList()
  result.len = len(scene.objects)
  result.objects = cast[ptr UncheckedArray[HittableVariant]](unsafe_addr(scene.objects[0]))
  return result