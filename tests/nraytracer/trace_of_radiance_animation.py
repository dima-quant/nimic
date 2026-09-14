# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.os import *
from nimic.std.strformat import *
from nimic.std.monotimes import *
from nimic.std.times import *
from primitives import newCanvas, point3, vec3, CTime, Degrees
from cameras import camera
from hittables import Scene  # this declaration should present because "list" function is defined in Scene
from render import render
from scenes_animated import random_moving_spheres, scenes, ATime
from sampling import Rng
from ppm import exportToPPM

# Animated scene from book 1
# ------------------------------------------------------------------------
# This is an extra after book 1
# An animated scene with a rudimentary physics engine
# And either PPM series or MP4 output (video encoding in pure Nim!)
# This does not incorporate motion blur from book 2 or acceleration structures
# to speed up compute.


def main_animation_ppm():
    # Animation is an extra added at the end of the first book
    # it's slow, and defines its own moving spheres
    # that are different from the second book
    # (which they used just for motion blur not animation)
    with const:
        aspect_ratio = 16.0 / 9.0
        image_width = 5 #512
        image_height = int32(image_width / aspect_ratio)
        samples_per_pixel = 100
        gamma_correction = 2.2
        max_depth = 50

    with const:
        dt = 0.005
        t_min = 0.0
        t_max = 6.0
        skip = 600  # Render every 6 physics update

    with const:
        destDir = string("build") / "rendered5"
        series = "animation"

    with var:
        worldRNG = Rng()
    worldRNG.seed(0xFACADE)

    with var:
        animation = random_moving_spheres(
            worldRNG,
            image_height, image_width,
            ATime(dt), ATime(t_min), ATime(t_max)
        )

    with var:
        canvas = newCanvas(
            image_height, image_width,
            samples_per_pixel,
            gamma_correction
        )

    try:
        create_dir(destDir)

        with let:
            totalScenes = nint((t_max - t_min) / (dt * skip))
        stderr.write(f"Total scenes: {totalScenes}")

        # init(Weave)
        with var:
            sceneID = nint(0)
            elapsed = Duration()
        for cam, scene in scenes(animation, skip=skip):
            with let:
                remaining = totalScenes - sceneID
                timeSpent = in_seconds(elapsed)
                timeLeft = remaining * timeSpent
            stderr.write(f"\rScenes remaining: {remaining:>5}, {timeSpent:>2} seconds/scene, estimated time left {timeLeft:>4} seconds")
            stderr.flush_file()
            print("flushed")
            with let:
                start = get_mono_time()
            render(canvas, cam, scene.list(), max_depth)
            print("rendered")
            # syncRoot(Weave)
            exportToPPM(canvas, destDir, series, sceneID)
            print("exported")
            sceneID += 1
            elapsed = get_mono_time() - start

        # exit(Weave)
    finally:
        canvas.delete()


# def main_animation_mp4():
#     # Animation is an extra added at the end of the first book
#     # it's slow, and defines its own moving spheres
#     # that are different from the second book
#     # (which they used just for motion blur not animation)
#     if comptime(True):  # Fast test
#         with const:
#             aspect_ratio = 16.0 / 9.0
#             image_width = 256  # so that we have multiples of 16 everywhere
#             image_height = int32(image_width / aspect_ratio)
#             samples_per_pixel = 10
#             gamma_correction = 2.2
#             max_depth = 50

#         with const:
#             dt = 0.005
#             t_min = 0.0
#             t_max = 1.0
#             skip = 6  # Render every 6 physics update
#     else:  # Full render
#         with const:
#             aspect_ratio = 16.0 / 9.0
#             image_width = 576  # so that we have multiples of 16 everywhere
#             image_height = int32(image_width / aspect_ratio)
#             samples_per_pixel = 300
#             gamma_correction = 2.2
#             max_depth = 50

#         with const:
#             dt = 0.005
#             t_min = 0.0
#             t_max = 6.0
#             skip = 6  # Render every 6 physics update

#     with const:
#         destDir = string("build") / "rendered"
#         series = "animation"

#     with var:
#         worldRNG = Rng()
#     worldRNG.seed(0xFACADE)

#     with var:
#         animation = random_moving_spheres(
#             worldRNG,
#             image_height, image_width,
#             ATime(dt), ATime(t_min), ATime(t_max)
#         )

#     with var:
#         canvas = newCanvas(
#             image_height, image_width,
#             samples_per_pixel,
#             gamma_correction
#         )

#     try:
#         create_dir(destDir)

#         # Encoding
#         # ----------------------------------------------------------------------
#         with let:
#             tmp264 = string(destDir) / (series + ".264")
#             out264 = open(tmp264, fmWrite)
#         with var:
#             encoder = H264Encoder.init(image_width, image_height, out264)
#         with let:
#             Y, Cb, Cr = encoder.getFrameBuffers()

#         with let:
#             yD = Y.initChannelDesc(image_width, subsampled=False)
#             uD = Cb.initChannelDesc(image_width, subsampled=True)
#             vD = Cr.initChannelDesc(image_width, subsampled=True)

#         # Rendering
#         # ----------------------------------------------------------------------
#         with let:
#             totalScenes = nint((t_max - t_min) / (dt * skip))
#         stderr.write(f"Total scenes: {totalScenes}")

#         # init(Weave)
#         with var:
#             sceneID = 0
#             elapsed = Duration()
#         for cam, scene in scenes(animation, skip=6):
#             with let:
#                 remaining = totalScenes - sceneID
#                 timeSpent = in_microseconds(elapsed)
#                 timeLeft = float64(remaining) * float64(timeSpent) * 1e-6
#                 throughput = 1e6 / float64(timeSpent)
#             stderr.write(f"\rScenes remaining: {remaining:>5}, {throughput:>7.4f} scene(s)/second, estimated time left {timeLeft:>10.3f} seconds")
#             stderr.flush_file()
#             with let:
#                 start = get_mono_time()
#             render(canvas, cam, scene.list(), max_depth)
#             # syncRoot(Weave)

#             # Video
#             with let:
#                 rgb = canvas.toRGB_Raw()
#                 rgbD = unsafe_addr(rgb[0]).initChannelDesc(image_width, subsampled=False)
#             rgbRaw_to_ycbcr420(
#                 image_width, image_height,
#                 rgb=rgbD,
#                 luma=yD,
#                 chromaBlue=uD,
#                 chromaRed=vD,
#                 BT601=BT601
#             )
#             encoder.flushFrame()

#             sceneID += 1
#             elapsed = get_mono_time() - start

#         # exit(Weave)
#         encoder.finish()
#         out264.close()
#         print("\nFinished writing temporary \"", string(destDir) / (series + ".264"), "\".\nMuxing into MP4")

#         with var:
#             mP4Muxer = MP4Muxer()
#         with let:
#             mp4 = open(string(destDir) / (series + ".mp4"), fmWrite)
#         mP4Muxer.initialize(mp4, image_width, image_height)
#         mP4Muxer.writeMP4_from(tmp264)

#         mP4Muxer.close()
#         mp4.close()
#         # removeFile(tmp264)
#         print("Finished! Rendering available at \"", string(destDir) / (series + ".mp4"), "\"")
#     finally:
#         canvas.delete()

if comptime(__name__ == "__main__"):
    main_animation_ppm()

#  main_animation_mp4()


# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import
#   # Standard library
#   std/[os, strformat, monotimes],
#   # 3rd party
#   weave,
#   # Internals
#   ./trace_of_radiance/[
#     primitives,
#     physics/hittables,
#     render,
#     sampling,
#     io/ppm
#   ],
#   # Extra
#   ./trace_of_radiance/scenes_animated,
#   ./trace_of_radiance/io/[
#     color_conversions,
#     h264,
#     mp4,
#     rgb
#   ]

# import times except Time

# # Animated scene from book 1
# # ------------------------------------------------------------------------
# # This is an extra after book 1
# # An animated scene with a rudimentary physics engine
# # And either PPM series or MP4 output (video encoding in pure Nim!)
# # This does not incorporate motion blur from book 2 or acceleration structures
# # to speed up compute.

# proc main_animation_ppm() =
#   # Animation is an extra added at the end of the first book
#   # it's slow, and defines its own moving spheres
#   # that are different from the second book
#   # (which they used just for motion blur not animation)
#   const aspect_ratio = 16.0 / 9.0
#   const image_width = 384
#   const image_height = int32(image_width / aspect_ratio)
#   const samples_per_pixel = 100
#   const gamma_correction = 2.2
#   const max_depth = 50

#   const
#     dt = 0.005
#     t_min = 0.0
#     t_max = 2.0
#     skip = 6 # Render every 6 physics update

#   const
#     destDir = "build"/"rendered"
#     series = "animation"

#   var worldRNG: Rng
#   worldRNG.seed 0xFACADE

#   var animation = worldRNG.random_moving_spheres(
#     image_height, image_width, dt.ATime, t_min.ATime, t_max.ATime
#   )

#   var canvas = newCanvas(
#                  image_height, image_width,
#                  samples_per_pixel,
#                  gamma_correction
#                )
#   defer: canvas.delete()

#   createDir(destDir)

#   let totalScenes = int((t_max - t_min)/(dt*skip))
#   stderr.write &"Total scenes: {totalScenes}"

#   init(Weave)
#   var sceneID = 0
#   var elapsed: Duration
#   for camera, scene in scenes(animation, skip = 6):
#     let remaining = totalScenes-sceneID
#     let timeSpent = inSeconds(elapsed)
#     let timeLeft = remaining * timeSpent
#     stderr.write &"\rScenes remaining: {remaining:>5}, {timeSpent:>2} seconds/scene, estimated time left {timeLeft:>4} seconds"
#     stderr.flushFile()
#     let start = getMonoTime()
#     canvas.render(camera, scene.list(), maxdepth)
#     syncRoot(Weave)

#     canvas.exportToPPM destDir, series, sceneID

#     inc sceneID
#     elapsed = getMonoTime() - start

#   exit(Weave)

# proc main_animation_mp4() =
#   # Animation is an extra added at the end of the first book
#   # it's slow, and defines its own moving spheres
#   # that are different from the second book
#   # (which they used just for motion blur not animation)
#   when true: # Fast test
#     const aspect_ratio = 16.0 / 9.0
#     const image_width = 256 # so that we have multiples of 16 everywhere
#     const image_height = int32(image_width / aspect_ratio)
#     const samples_per_pixel = 10
#     const gamma_correction = 2.2
#     const max_depth = 50

#     const
#       dt = 0.005
#       t_min = 0.0
#       t_max = 1.0
#       skip = 6 # Render every 6 physics update

#   else: # Full render
#     const aspect_ratio = 16.0 / 9.0
#     const image_width = 576 # so that we have multiples of 16 everywhere
#     const image_height = int32(image_width / aspect_ratio)
#     const samples_per_pixel = 300
#     const gamma_correction = 2.2
#     const max_depth = 50

#     const
#       dt = 0.005
#       t_min = 0.0
#       t_max = 6.0
#       skip = 6 # Render every 6 physics update

#   const
#     destDir = "build"/"rendered"
#     series = "animation"

#   var worldRNG: Rng
#   worldRNG.seed 0xFACADE

#   var animation = worldRNG.random_moving_spheres(
#     image_height, image_width, dt.ATime, t_min.ATime, t_max.ATime
#   )

#   var canvas = newCanvas(
#                  image_height, image_width,
#                  samples_per_pixel,
#                  gamma_correction
#                )
#   defer: canvas.delete()

#   createDir(destDir)

#   # Encoding
#   # ----------------------------------------------------------------------
#   let tmp264 = destDir/(series & ".264")
#   let out264 = open(tmp264, fmWrite)
#   var encoder = H264Encoder.init(image_width, image_height, out264)
#   let (Y, Cb, Cr) = encoder.getFrameBuffers()

#   let yD = Y.initChannelDesc(image_width, subsampled = false)
#   let uD = Cb.initChannelDesc(image_width, subsampled = true)
#   let vD = Cr.initChannelDesc(image_width, subsampled = true)

#   # Rendering
#   # ----------------------------------------------------------------------
#   let totalScenes = int((t_max - t_min)/(dt*skip))
#   stderr.write &"Total scenes: {totalScenes}"

#   init(Weave)
#   var sceneID = 0
#   var elapsed: Duration
#   for camera, scene in scenes(animation, skip = 6):
#     let remaining = totalScenes-sceneID
#     let timeSpent = inMicroSeconds(elapsed)
#     let timeLeft = remaining.float64 * timeSpent.float64 * 1e-6
#     let throughput = 1e6/timeSpent.float64
#     stderr.write &"\rScenes remaining: {remaining:>5}, {throughput:>7.4f} scene(s)/second, estimated time left {timeLeft:>10.3f} seconds"
#     stderr.flushFile()
#     let start = getMonoTime()
#     canvas.render(camera, scene.list(), maxdepth)
#     syncRoot(Weave)


#     # Video
#     let rgb = canvas.toRGB_Raw()
#     let rgbD = rgb[0].unsafeAddr.initChannelDesc(image_width, subsampled = false)
#     rgbRaw_to_ycbcr420(
#       image_width, image_height,
#       rgb = rgbD,
#       luma = yD,
#       chromaBlue = uD,
#       chromaRed = vD,
#       BT601
#     )
#     encoder.flushFrame()

#     inc sceneID
#     elapsed = getMonoTime() - start

#   exit(Weave)
#   encoder.finish()
#   out264.close()
#   echo "\nFinished writing temporary \"", destDir/(series & ".264"),"\".\nMuxing into MP4"

#   var mP4Muxer: MP4Muxer
#   let mp4 = open(destDir/(series & ".mp4"), fmWrite)
#   mP4Muxer.initialize(mp4, image_width, image_height)
#   mP4Muxer.writeMP4_from(tmp264)

#   mP4Muxer.close()
#   mp4.close()
#   # removeFile(tmp264)
#   echo "Finished! Rendering available at \"", destDir/(series & ".mp4"),"\""

# # main_animation_ppm()
# main_animation_mp4()
