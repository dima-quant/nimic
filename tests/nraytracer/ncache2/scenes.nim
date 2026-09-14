import ncode/pydefs
import hittables
import materials
import primitives
import sampling

proc random_scene*(rng: var Rng): Scene =
  result = Scene()
  let
    ground_material = lambertian(attenuation(0.5, 0.5, 0.5))
  result.add(sphere(point3(0, -1000, 0), 1000.0, ground_material))
  for a in range(-11, 11):
    for b in range(-11, 11):
      let
        center = point3(float64(a) + 0.9 * random(rng, float64), 0.2, float64(b) + 0.9 * random(rng, float64))
      if (center - point3(4, 0.2, 0)).length() > 0.9:
        let
          choose_mat = random(rng, float64)
        if choose_mat < 0.8:
          let
            albedo = random(rng, Attenuation) * random(rng, Attenuation)
            sphere_material = lambertian(albedo)
            center2 = center + vec3(0, random(rng, float64, 0.5), 0)
          result.add(movingSphere(center, Time(0.0), center2, Time(1.0), 0.2, sphere_material))
        elif choose_mat < 0.95:
          let
            albedo = random(rng, Attenuation, 0.5, 1.0)
            fuzz = random(rng, float64, 0.5)
            sphere_material = metal(albedo, fuzz)
          result.add(sphere(center, 0.2, sphere_material))
        else:
          let
            sphere_material = dielectric(1.5)
          result.add(sphere(center, 0.2, sphere_material))
  result.add(sphere(point3(0, 1, 0), 1.0, dielectric(1.5)))
  result.add(sphere(point3(-4, 1, 0), 1.0, lambertian(attenuation(0.4, 0.2, 0.1))))
  result.add(sphere(point3(4, 1, 0), 1.0, metal(attenuation(0.7, 0.6, 0.5), fuzz=0.0)))
  return result
when isMainModule:
  var
    worldRNG*: Rng
  worldRNG.seed(16435934)
  let
    world = random_scene(worldRNG)