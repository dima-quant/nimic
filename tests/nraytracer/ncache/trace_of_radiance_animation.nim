import ncode/pydefs
import std/os
import std/strformat
import std/monotimes
import std/times
import primitives
import cameras
import hittables
import render
import scenes_animated
import sampling
import ppm

proc main_animation_ppm*() =
  const
    aspect_ratio = 16.0 / 9.0
    image_width = 5
    image_height = int32(image_width / aspect_ratio)
    samples_per_pixel = 100
    gamma_correction = 2.2
    max_depth = 50
  const
    dt = 0.005
    t_min = 0.0
    t_max = 6.0
    skip = 600
  const
    destDir = string("build") / "rendered5"
    series = "animation"
  var
    worldRNG: Rng
  worldRNG.seed(16435934)
  var
    animation = random_moving_spheres(worldRNG, image_height, image_width, ATime(dt), ATime(t_min), ATime(t_max))
  var
    canvas = newCanvas(image_height, image_width, samples_per_pixel, gamma_correction)
  try:
    create_dir(destDir)
    let
      totalScenes = nint((t_max - t_min) / (dt * skip))
    stderr.write(&"Total scenes: {totalScenes}")
    var
      sceneID = nint(0)
      elapsed = Duration()
    for cam, scene in scenes(animation, skip=skip):
      let
        remaining = totalScenes - sceneID
        timeSpent = in_seconds(elapsed)
        timeLeft = remaining * timeSpent
      stderr.write(&"\rScenes remaining: {remaining:>5}, {timeSpent:>2} seconds/scene, estimated time left {timeLeft:>4} seconds")
      stderr.flush_file()
      echo("flushed")
      let
        start = get_mono_time()
      render(canvas, cam, scene.list(), max_depth)
      echo("rendered")
      exportToPPM(canvas, destDir, series, sceneID)
      echo("exported")
      sceneID += 1
      elapsed = get_mono_time() - start
  finally:
    canvas.delete()
when isMainModule:
  main_animation_ppm()