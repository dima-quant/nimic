import ncode/pydefs
import ncode/pystd/math
import hittables
import materials
import cameras
import core
import primitives
import sampling
type
  local_Velocity = distinct float64

  local_Distance = distinct float64

  ATime* = distinct float32

  local_Acceleration = distinct float64


proc `-=`*(a: var local_Velocity, b: local_Velocity) {.borrow.}

template `*`*(v: local_Velocity, dt: ATime): local_Distance =
  local_Distance(float64(v) * float64(dt))

template `*`*(k: float64, v: local_Velocity): local_Velocity =
  local_Velocity(float64(k) * float64(v))

proc `+=`*(a: var local_Distance, b: local_Distance) {.borrow.}

proc `+=`*(a: var ATime, b: ATime) {.borrow.}

template `<`*(a: ATime, b: ATime): bool =
  float32(a) < float32(b)

template `*`*(accel: local_Acceleration, dt: ATime): local_Velocity =
  local_Velocity(float64(accel) * float64(dt))
const
  SmallRadius* = 0.2
  G* = local_Acceleration(9.80665)
type
  local_MovingSphere = object
    velocity*: local_Velocity
    pos_y*: local_Distance
    coef_restitution*: float64
    x*: float64
    z*: float64
    radius*: float64
    material*: Material

  Animation* = object
    local_nrows: int32
    local_ncols: int32
    samples_per_pixel*: int32
    gamma_correction*: float32
    local_dt: ATime
    local_t_min: ATime
    local_t_max: ATime
    local_t: ATime
    local_lookFromAngle: Radians
    local_movingSpheres: seq[local_MovingSphere]


proc local_stepCamera(self: var Animation) =
  self.local_lookFromAngle -= Radians(2.0 * pi / 1200.0)

proc local_stepPhysics(self: var Animation) =
  self.local_t += self.local_dt
  for moving_sphere in self.local_movingSpheres.mitems:
    if float64(moving_sphere.velocity) < 0.0 and float64(moving_sphere.pos_y) < SmallRadius:
      moving_sphere.velocity = -moving_sphere.coef_restitution * moving_sphere.velocity
    else:
      moving_sphere.velocity -= G * self.local_dt
    moving_sphere.pos_y += moving_sphere.velocity * self.local_dt
    assert float64(moving_sphere.pos_y) >= 0.0

proc step*(self: var Animation) =
  self.local_stepCamera()
  self.local_stepPhysics()

proc random_moving_spheres*(rng: var Rng, height: int32, width: int32, dt: ATime, t_min: ATime, t_max: ATime): Animation =
  result = Animation()
  result.local_nrows = height
  result.local_ncols = width
  result.local_dt = dt
  result.local_t_min = t_min
  result.local_t_max = t_max
  result.local_t = ATime(0)
  result.local_lookFromAngle = Radians(2 * pi)
  for a in range(-20, 20):
    for b in range(-20, 20):
      let
        center = point3(float64(a) + 0.9 * random(rng, float64), SmallRadius, float64(b) + 0.9 * random(rng, float64))
      if (center - point3(4, SmallRadius, 0)).length() > 0.9:
        let
          choose_mat = random(rng, float64)
        if choose_mat < 0.65:
          let
            albedo = random(rng, Attenuation) * random(rng, Attenuation)
          result.local_movingSpheres.add(local_MovingSphere(coef_restitution:0.6, velocity:local_Velocity(10.0 + (4 * random(rng, float32) - 2.0)), x:center.x, pos_y:local_Distance(center.y), z:center.z, radius:SmallRadius, material:material(lambertian(albedo))))
        elif choose_mat < 0.95:
          let
            albedo = random(rng, Attenuation, 0.5, 1.0)
          let
            fuzz = random(rng, float64, 0.5)
          result.local_movingSpheres.add(local_MovingSphere(coef_restitution:0.5, velocity:local_Velocity(10.0 + (4 * random(rng, float32) - 2.0)), x:center.x, pos_y:local_Distance(center.y), z:center.z, radius:SmallRadius, material:material(metal(albedo, fuzz))))
        else:
          result.local_movingSpheres.add(local_MovingSphere(coef_restitution:0.5, velocity:local_Velocity(10.0 + (4 * random(rng, float32) - 2.0)), x:center.x, pos_y:local_Distance(center.y), z:center.z, radius:SmallRadius, material:material(dielectric(refraction_index=1.5))))
  return result
type
  local_ReturnScenes = tuple
    cam: Camera
    scene: Scene


iterator scenes*(anim: var Animation, skip: int): local_ReturnScenes =
  let
    aspect_ratio = anim.local_ncols / anim.local_nrows
  while anim.local_t < anim.local_t_min:
    anim.step()
  while anim.local_t < anim.local_t_max:
    var
      result: local_ReturnScenes
    result.cam = block:
      const
        r = sqrt(200.0)
      let
        lookFrom = point3(r * cos(float64(anim.local_lookFromAngle)), 2.0, r * sin(float64(anim.local_lookFromAngle)))
      camera(lookFrom, lookAt=point3(4, 1, 0), view_up=vec3(0, 1, 0), vertical_field_of_view=Degrees(20), aspect_ratio=aspect_ratio, aperture=0.1, focus_distance=10.0)
    result.scene.add(sphere(point3(0, -1000, 0), 1000.0, lambertian(attenuation(0.5, 0.5, 0.5))))
    for i in range(anim.local_movingSpheres.len):
      template local_sph(): untyped {.dirty.} =
        anim.local_movingSpheres[i]
      result.scene.add(sphere(point3(local_sph.x, float64(local_sph.pos_y), local_sph.z), local_sph.radius, local_sph.material))
    result.scene.add(sphere(point3(0, 1, 0), 1.0, dielectric(1.5)))
    result.scene.add(sphere(point3(-4, 1, 0), 1.0, lambertian(attenuation(0.4, 0.2, 0.1))))
    result.scene.add(sphere(point3(4, 1, 0), 1.0, metal(attenuation(0.7, 0.6, 0.5), fuzz=0.0)))
    yield result
    for _ in range(skip):
      anim.step()