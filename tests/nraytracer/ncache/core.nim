import ncode/pydefs
import primitives
type
  Lambertian* = object
    albedo*: Attenuation

  Metal* = object
    albedo*: Attenuation
    fuzz*: float64

  Dielectric* = object
    refraction_index*: float64

  MaterialKind* = enum 
    kMetal, kLambertian, kDielectric

  Material* = object
    case kind*: MaterialKind
      of MaterialKind.kMetal:
        fMetal*: Metal
      of MaterialKind.kLambertian:
        fLambertian*: Lambertian
      of MaterialKind.kDielectric:
        fDielectric*: Dielectric


func material*(subtype: Metal): Material {.inline.} =
  result = Material(kind:MaterialKind.kMetal, fMetal:subtype)
  return result

func material*(subtype: Lambertian): Material {.inline.} =
  result = Material(kind:MaterialKind.kLambertian, fLambertian:subtype)
  return result

func material*(subtype: Dielectric): Material {.inline.} =
  result = Material(kind:MaterialKind.kDielectric, fDielectric:subtype)
  return result
type
  HitRecord* = object
    p*: Point3
    normal*: Vec3
    material*: Material
    t*: float64
    front_face*: bool


func set_face_normal*(rec: var HitRecord, r: Ray, outward_normal: Vec3) {.inline.} =
  rec.front_face = r.direction.dot(outward_normal) < 0
  rec.normal = if rec.front_face: outward_normal else: -outward_normal