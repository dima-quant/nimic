import ncode/pydefs
import ncode/pystd/math
import primitives
import sampling
type
  Camera* = object
    origin*: Point3
    lower_left_corner*: Point3
    horizontal*: Vec3
    vertical*: Vec3
    u*: Vec3
    v*: Vec3
    w*: Vec3
    lens_radius*: float64
    shutterOpen*: Time
    shutterClose*: Time


proc ray*(self: Camera, s: float64, t: float64, var_rng: var Rng): Ray =
  let
    rd = self.lens_radius * random_in_unit_disk(var_rng, Vec3)
    offset = self.u * rd.x + self.v * rd.y
  result = ray(origin=self.origin + offset, direction=self.lower_left_corner + s * self.horizontal + t * self.vertical - self.origin - offset, time=random(var_rng, float64, self.shutterOpen, self.shutterClose))
  return result

proc camera*(lookFrom: Point3, lookAt: Point3, view_up: Vec3, vertical_field_of_view: Degrees, aspect_ratio: float64, aperture: float64, focus_distance: float64, shutterOpen=Time(0.0), shutterClose=Time(0.0)): Camera =
  let
    theta = degToRad(vertical_field_of_view)
    h = tan(theta / 2.0)
    viewport_height = 2.0 * h
    viewport_width = aspect_ratio * viewport_height
  result = Camera()
  result.w = (lookFrom - lookAt).unit_vector()
  result.u = view_up.cross(result.w).unit_vector()
  result.v = result.w.cross(result.u)
  result.origin = lookFrom
  result.horizontal = focus_distance * viewport_width * result.u
  result.vertical = focus_distance * viewport_height * result.v
  result.lower_left_corner = result.origin - result.horizontal / 2 - result.vertical / 2 - focus_distance * result.w
  result.lens_radius = aperture / 2
  result.shutterOpen = shutterOpen
  result.shutterClose = shutterClose
  return result