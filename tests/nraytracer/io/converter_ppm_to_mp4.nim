# Reference MP4 Generator
# Creates a reference MP4 from existing PPM frames using the C-backed minimp4
# Usage: nim c -d:danger --outdir:build test_mp4_reference.nim && ./build/test_mp4_reference

import std/[os, strutils, strformat, algorithm]
import h264, mp4, color_conversions
import system/ansi_c

type RGB_Raw = object
  r, g, b: uint8

const
  RenderedDir = "build/rendered16"
  Width = 512
  Height = 288
  FPS = 30

# Parse a P3 PPM file into a flat array of RGB bytes (r,g,b,r,g,b,...)
proc readPPM(path: string): seq[uint8] =
  let content = readFile(path)
  var
    pos = 0
    lineNum = 0
    width, height, maxVal: int

  # Parse header
  for line in content.splitLines():
    if line.len == 0 or line[0] == '#':
      pos += line.len + 1
      continue
    case lineNum
    of 0:
      assert line == "P3", "Expected P3 format, got: " & line
    of 1:
      let parts = line.strip().split()
      width = parseInt(parts[0])
      height = parseInt(parts[1])
    of 2:
      maxVal = parseInt(line.strip())
      assert maxVal == 255
      pos += line.len + 1
      inc lineNum
      break
    else: discard
    inc lineNum
    pos += line.len + 1

  # Parse pixel data
  result = newSeq[uint8](width * height * 3)
  var idx = 0
  let rest = content[pos .. ^1]
  for tok in rest.splitWhitespace():
    if idx < result.len:
      result[idx] = uint8(parseInt(tok))
      inc idx

proc main() =
  echo "Reference MP4 Generator"
  echo &"Reading PPM frames from {RenderedDir}/"

  # Collect and sort PPM files
  var ppmFiles: seq[string]
  for f in walkDir(RenderedDir):
    if f.kind == pcFile and f.path.endsWith(".ppm"):
      ppmFiles.add(f.path)
  ppmFiles.sort()

  echo &"Found {ppmFiles.len} PPM frames ({Width}x{Height})"
  if ppmFiles.len == 0:
    echo "No PPM files found!"
    quit 1

  # Initialize H264 encoder
  let tmp264 = RenderedDir / "reference.264"
  let out264 = open(tmp264, fmWrite)
  var encoder = H264Encoder.init(Width, Height, out264)
  let (Y, Cb, Cr) = encoder.getFrameBuffers()

  # Channel descriptors for color conversion
  let yD  = Y.initChannelDesc(Width, subsampled=false)
  let uD  = Cb.initChannelDesc(Width, subsampled=true)
  let vD  = Cr.initChannelDesc(Width, subsampled=true)

  # Encode each frame
  for i, ppmPath in ppmFiles:
    stderr.write &"\rEncoding frame {i+1}/{ppmFiles.len}: {extractFilename(ppmPath)}"

    # Read PPM to raw RGB
    let rgbData = readPPM(ppmPath)
    assert rgbData.len == Width * Height * 3,
      &"Expected {Width*Height*3} bytes, got {rgbData.len}"

    # Convert RGB -> YCbCr420
    let rgbDesc = cast[ptr UncheckedArray[RGB_Raw]](unsafeAddr rgbData[0])
      .initChannelDesc(Width, subsampled=false)
    rgbRaw_to_ycbcr420(
      Width.int32, Height.int32,
      rgb = rgbDesc,
      luma = yD,
      chromaBlue = uD,
      chromaRed = vD,
      ycbcrKind = BT601
    )

    if i == 0:
      echo "\nFirst frame debug:"
      echo &"  RGB[0,0] = {rgbData[0]}, {rgbData[1]}, {rgbData[2]}"
      let ptrY = Y
      let ptrU = Cb
      let ptrV = Cr
      echo &"  Y[0,0] = {ptrY[0]}, {ptrY[1]}"
      echo &"  U[0,0] = {ptrU[0]}"
      echo &"  V[0,0] = {ptrV[0]}"

    # Encode frame
    encoder.flushFrame()

  stderr.write "\n"
  encoder.finish()
  out264.close()
  echo &"H264 written to {tmp264}"

  # Mux .264 -> .mp4
  let mp4Path = RenderedDir / "reference.mp4"
  var muxer: MP4Muxer
  let mp4File = open(mp4Path, fmWrite)
  muxer.initialize(mp4File, Width.int32, Height.int32)
  muxer.writeMP4_from(tmp264)
  muxer.close()
  mp4File.close()

  echo &"Reference MP4 written to {mp4Path}"
  echo "Please verify playback before proceeding to Phase 1."

main()
