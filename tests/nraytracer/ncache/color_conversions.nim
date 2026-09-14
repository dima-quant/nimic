import ncode/pydefs
type
  RGB_to_YCbCr_Coefs* = object
    kr*: uint8
    kg*: uint8
    kb*: uint8
    fb*: uint8
    fr*: uint8
    y_scale*: uint8
    y_min*: uint8

  RGB_Raw* = object
    r*: uint8
    g*: uint8
    b*: uint8

  ChannelDescriptor*[T] = object
    buffer*: ptr UncheckedArray[T]
    stride*: int32

  ChannelLossless*[T] = object
    buffer*: ptr UncheckedArray[T]
    stride*: int32

  ChannelSubSampled*[T] = object
    buffer*: ptr UncheckedArray[T]
    stride*: int32

  YCbCrKind* = enum 
    
    BT601 = 0


template `[]`*[T](channel: ChannelLossless[T], row: SomeInteger, col: SomeInteger): T =
  channel.buffer[row * channel.stride + col]

template `[]=`*[T](channel: var ChannelLossless[T], row: SomeInteger, col: SomeInteger, value: T) =
  channel.buffer[row * channel.stride + col] = value

template `[]=`*[T](channel: var ChannelSubSampled[T], row: SomeInteger, col: SomeInteger, value: T) =
  channel.buffer[row shr 1 * channel.stride + col shr 1] = value

template toFixedPoint*(x: float64, I: typedesc[SomeInteger], precision: int): untyped =
  I(x * float64(1 shl precision) + 0.5)

proc compute_RGB_to_YCbCr_Coefs*(kr: float64, kb: float64, ymin: float64, ymax: float64, cbCrRange: float64): RGB_to_YCbCr_Coefs =
  result = RGB_to_YCbCr_Coefs()
  result.kr = toFixedPoint(kr, uint8, 8)
  result.kb = toFixedPoint(kb, uint8, 8)
  result.kg = uint8(256 - result.kr - result.kb)
  result.fb = toFixedPoint(cbCrRange / 255.0 / (2.0 * (1.0 - kb)), uint8, 8)
  result.fr = toFixedPoint(cbCrRange / 255.0 / (2.0 * (1.0 - kr)), uint8, 8)
  result.y_scale = toFixedPoint((ymax - ymin) / 255.0, uint8, 7)
  result.y_min = uint8(ymin)
  return result
const
  RGB_YCbCr_Coefs* = [compute_RGB_to_YCbCr_Coefs(0.299, 0.114, 16.0, 235.0, 240.0 - 16.0)]

proc initChannelDesc*[T](buffer: var T, width: SomeInteger, subsampled: static[bool]): ChannelDescriptor[T] {.inline.} =
  result = ChannelDescriptor[T]()
  result.buffer = cast[ptr UncheckedArray[T]](addr(buffer))
  when subsampled:
    result.stride = int32((width + 1) div 2)
  else:
    result.stride = int32(width)
  return result

proc initChannelDesc*[T](buffer: ptr UncheckedArray[T], width: SomeInteger, subsampled: static[bool]): ChannelDescriptor[T] {.inline.} =
  result = ChannelDescriptor[T]()
  result.buffer = buffer
  when subsampled:
    result.stride = int32((width + 1) div 2)
  else:
    result.stride = int32(width)
  return result

proc initChannelDesc*[T: not UncheckedArray](buffer: ptr T, width: SomeInteger, subsampled: static[bool]): ChannelDescriptor[T] {.inline.} =
  result = ChannelDescriptor[T]()
  result.buffer = cast[ptr UncheckedArray[T]](buffer)
  when subsampled:
    result.stride = int32((width + 1) div 2)
  else:
    result.stride = int32(width)
  return result

proc rgbRaw_to_ycbcr420*(width: int32, height: int32, rgb: ChannelDescriptor[RGB_Raw], luma: ChannelDescriptor[uint8], chromaBlue: ChannelDescriptor[uint8], chromaRed: ChannelDescriptor[uint8], ycbcrKind: static[YCbCrKind]) =
  let
    coefs = RGB_YCbCr_Coefs[int32(ycbcrKind)]
  assert width mod 2 == 0, "Width must be a multiple of 2"
  assert height mod 2 == 0, "Height must be a multiple of 2"
  let
    rgb_lossless = cast[ChannelLossless[RGB_Raw]](rgb)
  var
    Y = cast[ChannelLossless[uint8]](luma)
    U = cast[ChannelSubSampled[uint8]](chromaBlue)
    V = cast[ChannelSubSampled[uint8]](chromaRed)
  for ii in range(0, height, 2):
    for jj in range(0, width, 2):
      var
        tY = uint16(0)
        tU = int16(0)
        tV = int16(0)
        c_rgb: RGB_Raw
      c_rgb = rgb_lossless[ii, jj]
      tY = (uint16(coefs.kr) * uint16(c_rgb.r) + uint16(coefs.kg) * uint16(c_rgb.g) + uint16(coefs.kb) * uint16(c_rgb.b)) shr 8
      tU += int16(c_rgb.b) - int16(tY)
      tV += int16(c_rgb.r) - int16(tY)
      Y[ii, jj] = uint8(uint16(tY) * uint16(coefs.y_scale) shr 7) + coefs.y_min
      c_rgb = rgb_lossless[ii, jj + 1]
      tY = (uint16(coefs.kr) * uint16(c_rgb.r) + uint16(coefs.kg) * uint16(c_rgb.g) + uint16(coefs.kb) * uint16(c_rgb.b)) shr 8
      tU += int16(c_rgb.b) - int16(tY)
      tV += int16(c_rgb.r) - int16(tY)
      Y[ii, jj + 1] = uint8(uint16(tY) * uint16(coefs.y_scale) shr 7) + coefs.y_min
      c_rgb = rgb_lossless[ii + 1, jj]
      tY = (uint16(coefs.kr) * uint16(c_rgb.r) + uint16(coefs.kg) * uint16(c_rgb.g) + uint16(coefs.kb) * uint16(c_rgb.b)) shr 8
      tU += int16(c_rgb.b) - int16(tY)
      tV += int16(c_rgb.r) - int16(tY)
      Y[ii + 1, jj] = uint8(uint16(tY) * uint16(coefs.y_scale) shr 7) + coefs.y_min
      c_rgb = rgb_lossless[ii + 1, jj + 1]
      tY = (uint16(coefs.kr) * uint16(c_rgb.r) + uint16(coefs.kg) * uint16(c_rgb.g) + uint16(coefs.kb) * uint16(c_rgb.b)) shr 8
      tU += int16(c_rgb.b) - int16(tY)
      tV += int16(c_rgb.r) - int16(tY)
      Y[ii + 1, jj + 1] = uint8(uint16(tY) * uint16(coefs.y_scale) shr 7) + coefs.y_min
      U[ii, jj] = uint8(tU shr 2 * int16(coefs.fb) shr 8 + 128)
      V[ii, jj] = uint8(tV shr 2 * int16(coefs.fr) shr 8 + 128)