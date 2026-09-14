# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from math import *
# Internal
from hittables import *
from materials import *
from cameras import *
from core import *
from primitives import *
from sampling import *

# Animated scene from book 1
# ------------------------------------------------------------------------
# Experimental physics ;)
# No lateral move, deformation, motion blur, ...
#
# For now separate from the rest as not in the book
# Reference: https://github.com/nwtgck/ray-tracing-iow-scala
#
# Note: This is only based on the first book
#       hence does not use the introduced moving spheres
#       or motion blur.

  # I can't do physics without checking units
# @distinct
# class _Mass(float32):
#     pass
@distinct
class _Velocity(float64):
  def __isub__(a: mut @ _Velocity, b: _Velocity):
      """{.borrow.}"""
      return super().__isub__(b)
  @template
  def __mul__(v: _Velocity, dt: ATime) -> _Distance:
      return _Distance(float64(v) * float64(dt))
  @template
  def __rmul__(v: _Velocity, k: float64) -> _Velocity:
      return _Velocity(float64(k) * float64(v))
@distinct
class _Distance(float64):
    def __iadd__(a: mut @ _Distance, b: _Distance):
      """{.borrow.}"""
      return super().__iadd__(b)
@distinct
class ATime(float32):   # Avoid conflict with the Time unit introduced in book 2
    def __iadd__(a: mut @ ATime, b: ATime):
      """{.borrow.}"""
      return super().__iadd__(b)
    @template
    def __lt__(a: ATime, b: ATime) -> bool:
        return float32(a) < float32(b)
@distinct
class  _Acceleration(float64):
    @template
    def __mul__(accel: _Acceleration, dt: ATime) -> _Velocity:
        return _Velocity(float64(accel) * float64(dt))

with const:
  SmallRadius = 0.2
  G = _Acceleration(9.80665) # Gravity

class _MovingSphere(Object):
    ## Import those are NOT the MovingSpheres from book2
    # Movement mutable
    velocity: _Velocity
    pos_y: _Distance

    # Movement constants
    coef_restitution: float64  # Velocity ratio after collision

    # Poor Man's threadsafe closure
    x: float64
    z: float64
    radius: float64
    material: Material

class Animation(Object):
    _nrows: int32
    _ncols: int32
    samples_per_pixel: int32
    gamma_correction: float32

    # Time constants
    _dt: ATime
    _t_min: ATime
    _t_max: ATime

    # Time dependent
    _t: ATime
    _lookFromAngle: Radians
    _movingSpheres: seq[_MovingSphere]

    def _stepCamera(self: mut @ Animation):
        self._lookFromAngle -= Radians(2.0 * pi / 1200.0)

    def _stepPhysics(self: mut @ Animation):
        self._t += self._dt
        for moving_sphere in self._movingSpheres.mitems:
            if float64(moving_sphere.velocity) < 0.0 and \
                float64(moving_sphere.pos_y) < SmallRadius:
                # Sphere is descending and hit the ground
                moving_sphere.velocity = -moving_sphere.coef_restitution * moving_sphere.velocity # bounce
            else:
                moving_sphere.velocity -= G * self._dt # Fundamental Principle of Dynamics

            moving_sphere.pos_y += moving_sphere.velocity * self._dt
            assert float64(moving_sphere.pos_y) >= 0.0

    def step(self: mut @ Animation):
        self._stepCamera()
        self._stepPhysics()

def random_moving_spheres(
       rng: mut @ Rng,
       height: int32, width: int32,
       dt: ATime, t_min: ATime, t_max: ATime
     ) -> Animation:

  result = Animation()
  result._nrows = height
  result._ncols = width
  result._dt = dt
  result._t_min = t_min
  result._t_max = t_max

  result._t = ATime(0)
  result._lookFromAngle = Radians(2 * pi)

  for a in range(-20, 20):
      for b in range(-20, 20):
          with let: center = point3(
              float64(a) + 0.9*random(rng, float64),
              SmallRadius,
              float64(b) + 0.9*random(rng, float64)
          )
          if (center - point3(4, SmallRadius, 0)).length() > 0.9:
              with let: choose_mat = random(rng, float64)
              if choose_mat < 0.65:
                  # Diffuse
                  with let: albedo = random(rng, Attenuation) * random(rng, Attenuation)

                  result._movingSpheres.add(_MovingSphere(
                      coef_restitution=0.6,
                      velocity=_Velocity(10.0 + (4 * random(rng, float32) - 2.0)),
                      x=center.x,
                      pos_y=_Distance(center.y),
                      z=center.z,
                      radius=SmallRadius,
                      material=material(lambertian(albedo))
                  ))
              elif choose_mat < 0.95:
                  # Metal
                  with let: albedo = random(rng, Attenuation, 0.5, 1.0)
                  with let: fuzz = random(rng, float64, 0.5)

                  result._movingSpheres.add(_MovingSphere(
                      coef_restitution=0.5,
                      velocity=_Velocity(10.0 + (4 * random(rng, float32) - 2.0)),
                      x=center.x,
                      pos_y=_Distance(center.y),
                      z=center.z,
                      radius=SmallRadius,
                      material=material(metal(albedo, fuzz))
                  ))
              else:
                  # Glass
                  result._movingSpheres.add(_MovingSphere(
                      coef_restitution=0.5,
                      velocity=_Velocity(10.0 + (4 * random(rng, float32) - 2.0)),
                      x=center.x,
                      pos_y=_Distance(center.y),
                      z=center.z,
                      radius=SmallRadius,
                      material=material(dielectric(refraction_index = 1.5))
                  ))
  return result
	

class _ReturnScenes(NTuple):
    cam: Camera
    scene: Scene

#iterator 
def scenes(anim: mut @ Animation, skip: int) -> _ReturnScenes:
    with let: aspect_ratio = anim._ncols / anim._nrows # truediv of two ints

    # Skip
    while anim._t < anim._t_min:
        anim.step()

    while anim._t < anim._t_max:
        with var: 
            result = _ReturnScenes()
        
        def _block():
            with const: r = sqrt(200.0)
            with let: lookFrom = point3(
                r * cos(float64(anim._lookFromAngle)),
                2.0,
                r * sin(float64(anim._lookFromAngle))
            )
            return camera(
                lookFrom,
                lookAt = point3(4, 1, 0),
                view_up = vec3(0,1,0),
                vertical_field_of_view = Degrees(20),
                aspect_ratio = aspect_ratio,
                aperture = 0.1,
                focus_distance = 10.0
            )
        result.cam = _block()


        # Ground
        result.scene.add(sphere(point3(0,-1000,0), 1000.0, lambertian(attenuation(0.5,0.5,0.5))))

        # Moving spheres
        for i in range(anim._movingSpheres.len): # TODO: Change when Nim iterators speed fix https://github.com/nim-lang/Nim/issues/14421
            with template_inline:
                """{.dirty.}"""
                _sph = anim._movingSpheres[i]
            result.scene.add(sphere( # Poor man's closure with "y" as the only dynamic param
                point3(_sph.x, float64(_sph.pos_y), _sph.z),
                _sph.radius,
                _sph.material
            ))

        # Big spheres
        result.scene.add(sphere(point3(0,1,0), 1.0, dielectric(1.5)))
        result.scene.add(sphere(point3(-4,1,0), 1.0, lambertian(attenuation(0.4, 0.2, 0.1))))
        result.scene.add(sphere(point3(4,1,0), 1.0, metal(attenuation(0.7, 0.6, 0.5), fuzz = 0.0)))

        yield result

        for _ in range(skip):
            anim.step()

# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # Stdlib
#   ./math,
#   # Internals
#   ./physics/[
#     hittables, materials,
#     cameras, core
#   ],
#   ./sampling,
#   ./primitives

# # Animated scene from book 1
# # ------------------------------------------------------------------------
# # Experimental physics ;)
# # No lateral move, deformation, motion blur, ...
# #
# # For now separate from the rest as not in the book
# # Reference: https://github.com/nwtgck/ray-tracing-iow-scala
# #
# # Note: This is only based on the first book
# #       hence does not use the introduced moving spheres
# #       or motion blur.

# type
#   # I can't do physics without checking units
#   Mass = distinct float32
#   Velocity = distinct float64
#   Distance = distinct float64
#   ATime* = distinct float32    # Avoid conflict with the Time unit introduced in book 2
#   Acceleration = distinct float64

#   MovingSphere = object
#     ## Import those are NOT the MovingSpheres from book2
#     # Movement mutable
#     velocity: Velocity
#     pos_y: Distance

#     # Movement constants
#     coef_restitution: float64  # Velocity ratio after collision

#     # Poor Man's threadsafe closure
#     x, z: float64
#     radius: float64
#     material: Material

#   Animation* = object
#     nrows, ncols: int32
#     samples_per_pixel*: int32
#     gamma_correction*: float32

#     # Time constants
#     dt: ATime
#     t_min, t_max: ATime

#     # Time dependent
#     t: ATime
#     lookFromAngle: Radians
#     movingSpheres: seq[MovingSphere]

# const
#   SmallRadius = 0.2
#   G = 9.80665.Acceleration # Gravity

# # workarounds https://github.com/nim-lang/Nim/issues/14440
# # so ugly ...
# func `+=`(a: var Distance, b: Distance) {.inline.}=
#   cast[var float64](a.addr) += b.float64
# func `-=`(a: var Velocity, b: Velocity) {.inline.}=
#   cast[var float64](a.addr) -= b.float64

# func `+=`(a: var ATime, b: ATime) {.inline.}=
#   cast[var float32](a.addr) += b.float32
# template `<`(a, b: ATime): bool =
#   a.float32 < b.float32

# template `*`(accel: Acceleration, dt: ATime): Velocity =
#   Velocity(accel.float64 * dt.float64)
# template `*`(v: Velocity, dt: ATime): Distance =
#   Distance(v.float64 * dt.float64)
# template `*`(k: float64, v: Velocity): Velocity =
#   Velocity(k * v.float64)

# func random_moving_spheres*(
#        rng: var Rng,
#        height, width: int32,
#        dt, t_min, t_max: ATime
#      ): Animation =

#   result.nrows = height
#   result.ncols = width
#   result.dt = dt
#   result.t_min = t_min
#   result.t_max = t_max

#   result.t = 0.ATime
#   result.lookFromAngle = Radians(2 * PI)

#   for a in -20 ..< 20:
#     for b in -20 ..< 20:
#       let center = point3(
#         a.float64 + 0.9*rng.random(float64),
#         SmallRadius,
#         b.float64 + 0.9*rng.random(float64)
#       )

#       if length(center - point3(4, SmallRadius, 0)) > 0.9:
#         let choose_mat = rng.random(float64)

#         if choose_mat < 0.65:
#           # Diffuse
#           let albedo = rng.random(Attenuation) * rng.random(Attenuation)

#           result.movingSpheres.add MovingSphere(
#             coef_restitution: 0.6,
#             velocity: Velocity(10.0 + (4 * rng.random(float32) - 2.0)),
#             x: center.x,
#             pos_y: center.y.Distance,
#             z: center.z,
#             radius: SmallRadius,
#             material: material lambertian albedo
#           )
#         elif choose_mat < 0.95:
#           # Metal
#           let albedo = rng.random(Attenuation, 0.5, 1)
#           let fuzz = rng.random(float64, max = 0.5)

#           result.movingSpheres.add MovingSphere(
#             coef_restitution: 0.5,
#             velocity: Velocity(10.0 + (4 * rng.random(float32) - 2.0)),
#             x: center.x,
#             pos_y: center.y.Distance,
#             z: center.z,
#             radius: SmallRadius,
#             material: material metal(albedo, fuzz)
#           )

#         else:
#           # Glass
#           result.movingSpheres.add MovingSphere(
#             coef_restitution: 0.5,
#             velocity: Velocity(10.0 + (4 * rng.random(float32) - 2.0)),
#             x: center.x,
#             pos_y: center.y.Distance,
#             z: center.z,
#             radius: SmallRadius,
#             material: material dielectric(refraction_index = 1.5)
#           )

# func stepCamera(self: var Animation) =
#   self.lookFromAngle -= Radians(2.0 * PI / 1200.0)

# func stepPhysics(self: var Animation) =
#   self.t += self.dt
#   for movingSphere in self.movingSpheres.mitems:
#     if movingSphere.velocity.float64 < 0.0 and
#          movingSphere.pos_y.float64 < SmallRadius:
#       # Sphere is descending and hit the ground
#       movingSphere.velocity = -movingSphere.coef_restitution * movingSphere.velocity # bounce
#     else:
#       movingSphere.velocity -= G * self.dt # Fundamental Principle of Dynamics

#     moving_sphere.pos_y += moving_sphere.velocity * self.dt
#     assert moving_sphere.pos_y.float64 >= 0.0

# func step(self: var Animation) =
#   self.stepCamera()
#   self.stepPhysics()

# iterator scenes*(anim: var Animation, skip: int): tuple[cam: Camera, scene: Scene] =

#   let aspect_ratio = anim.ncols / anim.nrows

#   # Skip
#   while anim.t < anim.t_min:
#     anim.step()

#   while anim.t < anim.t_max:
#     var result: tuple[cam: Camera, scene: Scene]

#     result.cam = block:
#       const r = sqrt(200.0)
#       let lookFrom = point3(
#         r * anim.lookFromAngle.float64.cos(),
#         2.0,
#         r * anim.lookFromAngle.float64.sin()
#       )
#       camera(
#         lookFrom,
#         lookAt = point3(4, 1, 0),
#         view_up = vec3(0,1,0),
#         vertical_field_of_view = 20.Degrees,
#         aspect_ratio,
#         aperture = 0.1,
#         focus_distance = 10.0
#       )

#     # Ground
#     result.scene.add sphere(center = point3(0,-1000,0), 1000, lambertian attenuation(0.5,0.5,0.5))

#     # Moving spheres
#     for i in 0 ..< anim.movingSpheres.len: # TODO: Change when Nim iterators speed fix https://github.com/nim-lang/Nim/issues/14421
#       template sphere(): untyped {.dirty.} =
#         anim.movingSpheres[i]
#       result.scene.add sphere( # Poor man's closure with "y" as the only dynamic param
#         center = point3(sphere.x, sphere.pos_y.float64, sphere.z),
#         radius = sphere.radius,
#         material = sphere.material
#       )

#     # Big spheres
#     result.scene.add sphere(center = point3(0,1,0), 1.0, dielectric 1.5)
#     result.scene.add sphere(center = point3(-4,1,0), 1.0, lambertian attenuation(0.4, 0.2, 0.1))
#     result.scene.add sphere(center = point3(4,1,0), 1.0, metal(attenuation(0.7, 0.6, 0.5), fuzz = 0.0))

#     yield result

#     for _ in 0 ..< skip:
#       anim.step()
