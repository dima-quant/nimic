import ncode/pydefs
import ncode/pystd/math
import primitives
import sampling
import core
import hittables
import cameras
import materials

proc radiance*(ray: Ray, world: HittableList, max_depth: nint, rng: var Rng): Color =
  var
    local_attenuation = attenuation(1.0, 1.0, 1.0)
    ray = ray
  for _ in range(max_depth):
    var
      rec: HitRecord
    let
      maybeRec = world.hit(ray, 0.001, inf, rec)
    if maybeRec:
      var
        materialAttenuation = attenuation()
        scattered: Ray
      let
        maybeScatter = scatter(rec.material, ray, rec, rng, materialAttenuation, scattered)
      if maybeScatter:
        local_attenuation *= materialAttenuation
        ray = scattered
        continue
      return color(0, 0, 0)
    let
      unit_direction = ray.direction.unit_vector()
      t = 0.5 * unit_direction.y + 1.0
    result = (1.0 - t) * color(1, 1, 1) + t * color(0.5, 0.7, 1)
    result *= local_attenuation
    return result
  return color(0, 0, 0)

proc render*(canvas: var Canvas, cam: Camera, world: HittableList, max_depth: nint) =
  let
    canvas = addr(canvas)
  for row in range(canvas.nrows):
    for col in range(canvas.ncols):
      var
        rng: Rng
      rng.seed(row, col)
      var
        pixel = color(0, 0, 0)
      for _ in range(canvas.samples_per_pixel):
        let
          u = (float64(col) + random(rng, float64)) / float64(canvas.ncols - 1)
          v = (float64(row) + random(rng, float64)) / float64(canvas.nrows - 1)
          r = cam.ray(u, v, rng)
          rad = radiance(r, world, max_depth, rng)
        pixel += rad
      draw(canvas[], row, col, pixel)