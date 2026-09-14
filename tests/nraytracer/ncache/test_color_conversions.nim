import ncode/pydefs
import color_conversions
import system/ansi_c
import std/syncio
type
  IntPair* = object
    a*: nint
    b*: nint


proc next_int*(data: string, start: nint): IntPair =
  var
    i = start
  while i < len(data) and (ord(data[i]) == 32 or ord(data[i]) == 10 or ord(data[i]) == 13):
    i += 1
  if i >= len(data):
    result = IntPair()
    result.a = 0
    result.b = i
    return result
  if ord(data[i]) == 35:
    while i < len(data) and ord(data[i]) != 10:
      i += 1
    return next_int(data, i)
  var
    val = 0
  while i < len(data) and 48 <= ord(data[i]) and (ord(data[i]) <= 57):
    val = val * 10 + (ord(data[i]) - 48)
    i += 1
  result = IntPair()
  result.a = val
  result.b = i
  return result

proc parse_ppm_and_convert*(filepath: string) =
  let
    data = read_file(filepath)
  var
    i = 0
  while i < len(data) and ord(data[i]) != 32 and (ord(data[i]) != 10) and (ord(data[i]) != 13):
    i += 1
  var
    width = 0
    height = 0
    max_col = 0
    result: IntPair
  result = next_int(data, i)
  width = result.a
  i = result.b
  result = next_int(data, i)
  height = result.a
  i = result.b
  result = next_int(data, i)
  max_col = result.a
  i = result.b
  let
    w_int32 = int32(width)
    h_int32 = int32(height)
    rgb_size = w_int32 * h_int32 * int32(3)
    y_size = w_int32 * h_int32
    uv_size = w_int32 * h_int32 div int32(4) + int32(1)
  var
    rgb_buf = c_malloc(csize_t(rgb_size))
    y_buf = c_malloc(csize_t(y_size))
    u_buf = c_malloc(csize_t(uv_size))
    v_buf = c_malloc(csize_t(uv_size))
  var
    rgb_ptr = cast[ptr UncheckedArray[RGB_Raw]](rgb_buf)
  for idx in range(width * height):
    for c in range(3):
      result = next_int(data, i)
      let
        val = result.a
      i = result.b
      if c == 0:
        rgb_ptr[idx].r = uint8(val)
      elif c == 1:
        rgb_ptr[idx].g = uint8(val)
      elif c == 2:
        rgb_ptr[idx].b = uint8(val)
  let
    rgbD = initChannelDesc[RGB_Raw](cast[ptr RGB_Raw](rgb_buf), w_int32, false)
    yD = initChannelDesc[uint8](cast[ptr uint8](y_buf), w_int32, false)
    uD = initChannelDesc[uint8](cast[ptr uint8](u_buf), w_int32, true)
    vD = initChannelDesc[uint8](cast[ptr uint8](v_buf), w_int32, true)
  rgbRaw_to_ycbcr420(w_int32, h_int32, rgbD, yD, uD, vD, YCbCrKind.BT601)
  var
    y_out = cast[ptr UncheckedArray[uint8]](y_buf)
  var
    u_out = cast[ptr UncheckedArray[uint8]](u_buf)
  var
    v_out = cast[ptr UncheckedArray[uint8]](v_buf)
  echo("Parsed PPM: ", width, "x", height, " max_color=", max_col)
  echo("Y channel first 10 pixels:")
  for j in range(10):
    echo(int32(y_out[j]))
  echo("U channel first 2 pixels:")
  for j in range(2):
    echo(int32(u_out[j]))
  echo("V channel first 2 pixels:")
  for j in range(2):
    echo(int32(v_out[j]))
when isMainModule:
  parse_ppm_and_convert("tests/nraytracer/ncache/build/rendered16/animation_00000.ppm")