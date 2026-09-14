import ncode/pydefs
import std/os
import std/strutils
import std/strformat
import std/algorithm
import h264
import mp4
import color_conversions
const
  RenderedDir* = string("build/rendered_test")
  Width* = 512
  Height* = 288
  FPS* = 30

proc readPPM*(path: string): seq[uint8] =
  let
    content = read_file(path)
  var
    pos = 0
    lineNum = 0
    width = 0
    height = 0
    maxVal = 0
  for line in string(content).splitlines():
    if len(line) == 0 or $(line[0]) == "#":
      pos += len(line) + 1
      continue
    case lineNum:
      of 0:
        assert line == "P3", "Expected P3 format, got: " + line
      of 1:
        let
          parts = string(line).strip().split()
        width = parse_int(parts[0])
        height = parse_int(parts[1])
      of 2:
        maxVal = parse_int(string(line).strip())
        assert maxVal == 255
        pos += len(line) + 1
        lineNum += 1
        break
      else:
        discard
    lineNum += 1
    pos += len(line) + 1
  result = new_seq[uint8](width * height * 3)
  var
    idx = 0
  let
    rest = string(content[pos..^1])
  for tok in rest.split_whitespace():
    if idx < len(result):
      result[idx] = uint8(parse_int(tok))
      idx += 1
  return result

proc main*() =
  echo("Reference MP4 Generator")
  echo(&"Reading PPM frames from {RenderedDir}/")
  var
    ppmFiles: seq[string]
  for f in walk_dir(RenderedDir):
    if f.kind == pcFile and string(f.path).endswith(".ppm"):
      ppmFiles.add(string(f.path))
  ppmFiles.sort()
  echo(&"Found {len(ppmFiles)} PPM frames ({Width}x{Height})")
  if len(ppmFiles) == 0:
    echo("No PPM files found!")
    quit(1)
  let
    tmp264 = RenderedDir / "reference.264"
    out264 = open(tmp264, fmWrite)
  echo(&"Opened file: {tmp264}")
  var
    encoder = init(H264Encoder, Width, Height, out264)
  echo(&"Encoder initialized: {encoder}")
  let
    (Y, Cb, Cr) = getFrameBuffers(encoder)
    yD = initChannelDesc(Y, Width, subsampled=false)
    uD = initChannelDesc(Cb, Width, subsampled=true)
    vD = initChannelDesc(Cr, Width, subsampled=true)
  echo(&"Frame buffers initialized: {yD}, {uD}, {vD}")
  for i, ppmPath in ppmFiles:
    echo(&"\rEncoding frame {i + 1}/{len(ppmFiles)}: {extract_filename(ppmPath)}")
    stderr.write(&"\rEncoding frame {i + 1}/{len(ppmFiles)}: {extract_filename(ppmPath)}")
    let
      rgbData = readPPM(ppmPath)
    assert len(rgbData) == Width * Height * 3, &"Expected {Width * Height * 3} bytes, got {len(rgbData)}"
    echo(&"Read {len(rgbData)} bytes from {ppmPath}")
    let
      rgbDesc = initChannelDesc(cast[ptr UncheckedArray[RGB_Raw]](unsafe_addr(rgbData[0])), Width, subsampled=false)
    rgbRaw_to_ycbcr420(int32(Width), int32(Height), rgbDesc, yD, uD, vD, YCbCrKind.BT601)
    echo(&"\nFrame {i} debug:")
    echo(&"  RGB[0,0] = {rgbData[0]}, {rgbData[1]}, {rgbData[2]}")
    let
      ptrY = Y
      ptrU = Cb
      ptrV = Cr
    echo(&"  Y[0:2, 0:2] = {ptrY[0]}, {ptrY[1]}, {ptrY[2]}, {ptrY[3]}")
    echo(&"  U[0:2, 0:2] = {ptrU[0]}, {ptrU[1]}, {ptrU[2]}, {ptrU[3]}")
    echo(&"  V[0:2, 0:2] = {ptrV[0]}, {ptrV[1]}, {ptrV[2]}, {ptrV[3]}")
    echo(&"  Y[-1, -2, -3, -4] = {ptrY[encoder.frame.lumaWidth * encoder.frame.lumaHeight - 1]},            {ptrY[encoder.frame.lumaWidth * encoder.frame.lumaHeight - 2]},            {ptrY[encoder.frame.lumaWidth * encoder.frame.lumaHeight - 3]},            {ptrY[encoder.frame.lumaWidth * encoder.frame.lumaHeight - 4]}")
    flushFrame(encoder)
  stderr.write("\n")
  finish(encoder)
  out264.close()
  echo(&"H264 written to {tmp264}")
  let
    mp4Path = RenderedDir / "reference.mp4"
  var
    muxer: MP4Muxer
  let
    mp4File = open(mp4Path, fmWrite)
  initialize(muxer, mp4File, int32(Width), int32(Height))
  writeMP4_from(muxer, tmp264)
  close(muxer)
  mp4File.close()
  echo(&"Reference MP4 written to {mp4Path}")
  echo("Please verify playback before proceeding to Phase 1.")
if isMainModule:
  main()