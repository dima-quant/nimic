import ncode/pydefs
import primitives
import core
import spheres
import moving_spheres
type
  HittableVariantKind* = enum 
    kSphere, kMovingSphere

  HittableVariant* = object
    case kind*: HittableVariantKind
      of HittableVariantKind.kSphere:
        fSphere*: Sphere
      of HittableVariantKind.kMovingSphere:
        fMovingSphere*: MovingSphere


func hit*(self: HittableVariant, r: Ray, t_min: float64, t_max: float64, rec: var HitRecord): bool {.inline.} =
  case self.kind:
    of HittableVariantKind.kSphere:
      result = self.fSphere.hit(r, t_min, t_max, rec)
    of HittableVariantKind.kMovingSphere:
      result = self.fMovingSphere.hit(r, t_min, t_max, rec)
  return result

func toVariant*(subtype: Sphere): HittableVariant {.inline.} =
  result = HittableVariant(kind:HittableVariantKind.kSphere, fSphere:subtype)
  return result

func toVariant*(subtype: MovingSphere): HittableVariant {.inline.} =
  result = HittableVariant(kind:HittableVariantKind.kMovingSphere, fMovingSphere:subtype)
  return result