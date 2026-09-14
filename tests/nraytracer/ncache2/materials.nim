import ncode/pydefs
import ncode/pystd/math
import core
import primitives
import sampling

func lambertian*(albedo: Attenuation): Lambertian {.inline.} =
  result = Lambertian()
  result.albedo = albedo
  return result

func local_scatter(self: Lambertian, r_in: Ray, rec: HitRecord, rng: var Rng, attenuation: var Attenuation, scattered: var Ray): bool {.inline.} =
  let
    scatter_direction = rec.normal + random(rng, UnitVector).toVec3()
  scattered = ray(rec.p, scatter_direction, r_in.time)
  attenuation = self.albedo
  return true

func metal*(albedo: Attenuation, fuzz: float64): Metal {.inline.} =
  result = Metal()
  result.albedo = albedo
  result.fuzz = min(fuzz, 1)
  return result

func local_scatter(self: Metal, r_in: Ray, rec: HitRecord, rng: var Rng, attenuation: var Attenuation, scattered: var Ray): bool =
  let
    reflected = reflect(r_in.direction.unit_vector(), rec.normal)
  scattered = ray(rec.p, reflected + self.fuzz * random_in_unit_sphere(rng, Vec3))
  if scattered.direction.dot(rec.normal) > 0:
    attenuation = self.albedo
    return true
  return false

func dielectric*(refraction_index: float64): Dielectric {.inline.} =
  result = Dielectric()
  result.refraction_index = refraction_index
  return result

func local_schlick(cosine: float64, refraction_index: float64): float64 =
  var
    r0 = (1 - refraction_index) / (1 + refraction_index)
  r0 *= r0
  return r0 + (1 - r0) * pow(1 - cosine, 5)

func local_scatter(self: Dielectric, r_in: Ray, rec: HitRecord, rng: var Rng, local_attenuation: var Attenuation, scattered: var Ray): bool =
  local_attenuation = attenuation(1.0, 1.0, 1.0)
  let
    etaI_over_etaT = if rec.front_face: 1.0 / self.refraction_index else: self.refraction_index
  let
    unit_direction = r_in.direction.unit_vector()
    cos_theta = min(-unit_direction.dot(rec.normal), 1.0)
    sin_theta = sqrt(1.0 - cos_theta * cos_theta)
  if etaI_over_etaT * sin_theta > 1.0:
    let
      reflected = reflect(unit_direction, rec.normal)
    scattered = ray(rec.p, reflected)
    return true
  let
    reflect_prob = local_schlick(cos_theta, etaI_over_etaT)
  if random(rng, float64) < reflect_prob:
    let
      reflected = reflect(unit_direction, rec.normal)
    scattered = ray(rec.p, reflected)
    return true
  let
    refracted = refract(unit_direction, rec.normal, etaI_over_etaT)
  scattered = ray(rec.p, refracted)
  return true

proc scatter*(self: Material, r_in: Ray, rec: HitRecord, rng: var Rng, attenuation: var Attenuation, scattered: var Ray): bool =
  case self.kind:
    of MaterialKind.kMetal:
      result = local_scatter(self.fMetal, r_in, rec, rng, attenuation, scattered)
    of MaterialKind.kLambertian:
      result = local_scatter(self.fLambertian, r_in, rec, rng, attenuation, scattered)
    of MaterialKind.kDielectric:
      result = local_scatter(self.fDielectric, r_in, rec, rng, attenuation, scattered)
  return result