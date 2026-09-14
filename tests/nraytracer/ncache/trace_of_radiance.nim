import ncode/pydefs
import std/os
import std/strformat
import std/monotimes
import std/times
import primitives
import cameras
import hittables
import render
import scenes
import sampling
import ppm

proc main*() =
  const
    aspect_ratio = 16.0 / 9.0
    image_width = 5
    image_height = nint(image_width / aspect_ratio)
    samples_per_pixel = 100
    gamma_correction = 2.2
    max_depth = 50
  var
    worldRNG: Rng
  worldRNG.seed(16435934)
  let
    world = random_scene(worldRNG)
  let
    lookFrom = point3(13, 2, 3)
    lookAt = point3(0, 0, 0)
    vup = vec3(0, 1, 0)
    dist_to_focus = 10.0
    aperture = 0.1
  let
    cam = camera(lookFrom, lookAt, vup, Degrees(20), aspect_ratio, aperture, dist_to_focus, shutterOpen=CTime(0.0), shutterClose=CTime(1.0))
  var
    canvas = newCanvas(image_height, image_width, samples_per_pixel, gamma_correction)
  try:
    let
      start = get_mono_time()
    render(canvas, cam, world.list(), max_depth)
    let
      stop = get_mono_time()
    exportToPPM(canvas, stdout)
    stderr.write("\nDone.\n")
    let
      elapsed = in_milliseconds(stop - start)
    stderr.write(&"Time spent: {float64(elapsed) * 0.001:>6.3f} s\n")
  finally:
    canvas.delete()
when isMainModule:
  main()