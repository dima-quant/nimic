# /// nimic
#
# ///


from __future__ import annotations
from nimic.ntypes import *

class RGB_to_YCbCr_Coefs(Object):
    kr: uint8
    kg: uint8
    kb: uint8
    fb: uint8
    fr: uint8
    y_scale: uint8
    y_min: uint8


class RGB_Raw(Object):
    r: uint8
    g: uint8
    b: uint8


class ChannelDescriptor[T](Object):
    buffer: ptr[UncheckedArray[T]]
    stride: int32


class ChannelLossless[T](Object):
    buffer: ptr[UncheckedArray[T]]
    stride: int32

    @template
    def __getitem__[T](channel: ChannelLossless[T], packed_tuple: tuple[SomeInteger, SomeInteger]) -> T:
        row, col = packed_tuple
        return channel.buffer[row * channel.stride + col]

    @template
    def __setitem__[T](channel: mut @ ChannelLossless[T], packed_tuple: tuple[SomeInteger, SomeInteger], value: T):
        row, col = packed_tuple
        channel.buffer[row * channel.stride + col] = value


class ChannelSubSampled[T](Object):
    buffer: ptr[UncheckedArray[T]]
    stride: int32

    @template
    def __setitem__[T](channel: mut @ ChannelSubSampled[T], packed_tuple: tuple[SomeInteger, SomeInteger], value: T):
        row, col = packed_tuple
        channel.buffer[(row >> 1) * channel.stride + (col >> 1)] = value

class YCbCrKind(NIntEnum):
    BT601 = 0


@template
def toFixedPoint(x: float64, I: typedesc[SomeInteger], precision: int) -> untyped:
    I(x * float64(1 << precision) + 0.5)


@template_expand
def compute_RGB_to_YCbCr_Coefs(
    kr: float64, kb: float64, ymin: float64, ymax: float64, cbCrRange: float64
) -> RGB_to_YCbCr_Coefs:
    result = RGB_to_YCbCr_Coefs()
    result.kr = toFixedPoint(kr, uint8, 8)
    result.kb = toFixedPoint(kb, uint8, 8)
    result.kg = uint8(256 - result.kr - result.kb)
    result.fb = toFixedPoint((cbCrRange / 255.0) / (2.0 * (1.0 - kb)), uint8, 8)
    result.fr = toFixedPoint((cbCrRange / 255.0) / (2.0 * (1.0 - kr)), uint8, 8)
    result.y_scale = toFixedPoint((ymax - ymin) / 255.0, uint8, 7)
    result.y_min = uint8(ymin)
    return result


with const:
    RGB_YCbCr_Coefs = [
        compute_RGB_to_YCbCr_Coefs(0.299, 0.114, 16.0, 235.0, 240.0 - 16.0)
    ]

@dispatch
def initChannelDesc[T](buffer: mut @ T, width: SomeInteger,
    subsampled: static[bool]) -> ChannelDescriptor[T]:
    """
    Create a descriptor for a color channel.
    Use subsampled == true for a subsambpled channel
    Assumes that images are stored with "width" laid out contiguously

    Note: ensure that the buffer lifetime is greater than
    the color conversion routines.
    {.inline.}
    """
    result = ChannelDescriptor[T]()
    result.buffer = cast[ptr[UncheckedArray[T]]](addr(buffer))
    if comptime(subsampled):
        result.stride = int32((width + 1) // 2)
    else:
        result.stride = int32(width)
    return result

@dispatch
def initChannelDesc[T](buffer: ptr[UncheckedArray[T]], width: SomeInteger,
    subsampled: static[bool]) -> ChannelDescriptor[T]:
    """
    Create a descriptor for a color channel.
    Use subsampled == true for a subsambpled channel
    Assumes that images are stored with "width" laid out contiguously

    Note: ensure that the buffer lifetime is greater than
    the color conversion routines.
    {.inline.}
    """
    result = ChannelDescriptor[T]()
    result.buffer = buffer
    if comptime(subsampled):
        result.stride = int32((width + 1) // 2)
    else:
        result.stride = int32(width)
    return result

@dispatch
def initChannelDesc[T: not UncheckedArray](buffer: ptr[T], width: SomeInteger,
    subsampled: static[bool]) -> ChannelDescriptor[T]:
    """
    Create a descriptor for a color channel.
    Use subsampled == true for a subsambpled channel
    Assumes that images are stored with "width" laid out contiguously

    Note: ensure that the buffer lifetime is greater than
    the color conversion routines.
    {.inline.}
    """
    result = ChannelDescriptor[T]()
    result.buffer = cast[ptr[UncheckedArray[T]]](buffer)
    if comptime(subsampled):
        result.stride = int32((width + 1) // 2)
    else:
        result.stride = int32(width)
    return result


def rgbRaw_to_ycbcr420(
    width: int32,
    height: int32,
    rgb: ChannelDescriptor[RGB_Raw],
    luma: ChannelDescriptor[uint8],
    chromaBlue: ChannelDescriptor[uint8],
    chromaRed: ChannelDescriptor[uint8],
    ycbcrKind: static[YCbCrKind]
):
    with let:
        coefs = RGB_YCbCr_Coefs[int32(ycbcrKind)]

    assert (width % 2) == 0, "Width must be a multiple of 2"
    assert (height % 2) == 0, "Height must be a multiple of 2"

    with let:
        rgb_lossless = cast[ChannelLossless[RGB_Raw]](rgb)
    with var:
        Y = cast[ChannelLossless[uint8]](luma)
        U = cast[ChannelSubSampled[uint8]](chromaBlue)
        V = cast[ChannelSubSampled[uint8]](chromaRed)

    for ii in range(0, height, 2):
        for jj in range(0, width, 2):
            with var:
                tY = uint16(0)
                tU = int16(0)
                tV = int16(0)
                c_rgb = RGB_Raw()

            c_rgb = rgb_lossless[ii, jj]
            tY = (uint16(coefs.kr) * uint16(c_rgb.r) +
                  uint16(coefs.kg) * uint16(c_rgb.g) +
                  uint16(coefs.kb) * uint16(c_rgb.b)) >> 8
            tU += int16(c_rgb.b) - int16(tY)
            tV += int16(c_rgb.r) - int16(tY)
            Y[ii, jj] = uint8((uint16(tY) * uint16(coefs.y_scale)) >> 7) + coefs.y_min

            c_rgb = rgb_lossless[ii, jj + 1]
            tY = (uint16(coefs.kr) * uint16(c_rgb.r) +
                  uint16(coefs.kg) * uint16(c_rgb.g) +
                  uint16(coefs.kb) * uint16(c_rgb.b)) >> 8
            tU += int16(c_rgb.b) - int16(tY)
            tV += int16(c_rgb.r) - int16(tY)
            Y[ii, jj + 1] = uint8((uint16(tY) * uint16(coefs.y_scale)) >> 7) + coefs.y_min

            c_rgb = rgb_lossless[ii + 1, jj]
            tY = (uint16(coefs.kr) * uint16(c_rgb.r) +
                  uint16(coefs.kg) * uint16(c_rgb.g) +
                  uint16(coefs.kb) * uint16(c_rgb.b)) >> 8
            tU += int16(c_rgb.b) - int16(tY)
            tV += int16(c_rgb.r) - int16(tY)
            Y[ii + 1, jj] = uint8((uint16(tY) * uint16(coefs.y_scale)) >> 7) + coefs.y_min

            c_rgb = rgb_lossless[ii + 1, jj + 1]
            tY = (uint16(coefs.kr) * uint16(c_rgb.r) +
                  uint16(coefs.kg) * uint16(c_rgb.g) +
                  uint16(coefs.kb) * uint16(c_rgb.b)) >> 8
            tU += int16(c_rgb.b) - int16(tY)
            tV += int16(c_rgb.r) - int16(tY)
            Y[ii + 1, jj + 1] = uint8((uint16(tY) * uint16(coefs.y_scale)) >> 7) + coefs.y_min

            U[ii, jj] = uint8((((tU >> 2) * int16(coefs.fb)) >> 8) + 128)
            V[ii, jj] = uint8((((tV >> 2) * int16(coefs.fr)) >> 8) + 128)


# # E'R, E'G, E'B and E'Y range is [0:1], while E'Cb and E'Cr range is [-0.5:0.5]
# # R, G, B, Y, Cb and Cr refer to the digitalized values
# # The digitalized values can use their full range ([0:255] for 8bit values),
# # or a subrange (typically [16:235] for Y and [16:240] for CbCr).
# # We assume here that RGB range is always [0:255], since it is the case for
# # most digitalized images.
# # For 8bit values :
# # * Y = round((YMax-YMin)*E'Y + YMin)
# # * Cb = round((CbRange)*E'Cb + 128)
# # * Cr = round((CrRange)*E'Cr + 128)
# # Where *Min and *Max are the range of each channel
# #
# # In the analog domain , the RGB to YCbCr transformation is defined as:
# # * E'Y = Rf*E'R + Gf*E'G + Bf*E'B
# # Where Rf, Gf and Bf are constants defined in each standard, with
# # Rf + Gf + Bf = 1 (necessary to ensure that E'Y range is [0:1])
# # * E'Cb = (E'B - E'Y) / CbNorm
# # * E'Cr = (E'R - E'Y) / CrNorm
# # Where CbNorm and CrNorm are constants, dependent of Rf, Gf, Bf, computed
# # to normalize to a [-0.5:0.5] range : CbNorm=2*(1-Bf) and CrNorm=2*(1-Rf)
# #
# # Algorithms
# #
# # Most operations will be made in a fixed point format for speed, using
# # N bits of precision. In next section the [x] convention is used for
# # a fixed point rounded value, that is (int being the c type conversion)
# # * [x] = int(x*(2^N)+0.5)
# # N can be different for each factor, we simply use the highest value
# # that will not overflow in 16 bits intermediate variables.
# #
# # For RGB to YCbCr conversion, we start by generating a pseudo Y value
# # (noted Y') in fixed point format, using the full range for now.
# # * Y' = ([Rf]*R + [Gf]*G + [Bf]*B)>>N
# # We can then compute Cb and Cr by
# # * Cb = ((B - Y')*[CbRange/(255*CbNorm)])>>N + 128
# # * Cr = ((R - Y')*[CrRange/(255*CrNorm)])>>N + 128
# # And finally, we normalize Y to its digital range
# # * Y = (Y'*[(YMax-YMin)/255])>>N + YMin
# #
# # For YCbCr to RGB conversion, we first compute the full range Y' value :
# # * Y' = ((Y-YMin)*[255/(YMax-YMin)])>>N
# # We can then compute B and R values by :
# # * B = ((Cb-128)*[(255*CbNorm)/CbRange])>>N + Y'
# # * R = ((Cr-128)*[(255*CrNorm)/CrRange])>>N + Y'
# # And finally, for G we know that:
# # * G = (Y' - (Rf*R + Bf*B)) / Gf
# # From above:
# # * G = (Y' - Rf * ((Cr-128)*(255*CrNorm)/CrRange + Y') - Bf * ((Cb-128)*(255*CbNorm)/CbRange + Y')) / Gf
# # Since 1-Rf-Bf=Gf, we can take Y' out of the division by Gf, and we get:
# # * G = Y' - (Cr-128)*Rf/Gf*(255*CrNorm)/CrRange - (Cb-128)*Bf/Gf*(255*CbNorm)/CbRange
# # That we can compute, with fixed point arithmetic, by
# # * G = Y' - ((Cr-128)*[Rf/Gf*(255*CrNorm)/CrRange] + (Cb-128)*[Bf/Gf*(255*CbNorm)/CbRange])>>N
# #
# # Note : in ITU-T T.871(JPEG), Y=Y', so that part could be optimized out

# # Sanity checks
# # ------------------------------------------------------

# when isMainModule:
#   # We test vs yuv2rgb which was tested against FFMPEG
#   # https://github.com/descampsa/yuv2rgb
#   # TODO: more thorough testing like libYUV

#   import std/[strutils, os, sequtils, random]

#   const
#     yuv_rgb_Path = currentSourcePath.rsplit(DirSep, 1)[0]

#   {.localPassC: "-I" & yuv_rgb_Path.}
#   {.pragma: yuv_rgb, importc, header: yuv_rgb_Path / "yuv_rgb.h".}
#   {.compile: "yuv_rgb.c".}

#   type YCbCrType {.size: sizeof(cint).} = enum
#     YCbCr_JPEG,
#     YCbCr_601
#     YCbCr_709

#   type RGB_Raw = object
#     r, g, b: uint8

#   static: doAssert: RGB_Raw is RGB_Concept

#   # Note: The standard C implementation has a factor bug
#   #       correct it before testing
#   # https://github.com/descampsa/yuv2rgb/issues/15

#   proc rgb24_yuv420_std(
#          width, height: uint32,
#          rgb: pointer, rgb_stride: uint32,
#          y, u, v: pointer,
#          y_stride, uv_stride: uint32,
#          yuv_type: YCbCrType
#        ) {.yuv_rgb.}


#   proc randRGB(rng: var Rand): RGB_Raw =
#     result.r = uint8 rng.rand(255)
#     result.g = uint8 rng.rand(255)
#     result.b = uint8 rng.rand(255)

#   proc main() =

#     for width in [16, 32, 64, 96, 384, 512, 1024]:
#       for height in [16, 32, 64, 96, 384, 512, 1024]:
#         let width = 16  # * 64  # 1024
#         let height = 16 #  * 10 # 160
#         var rng = initRand(0xFACADE)

#         let rgb = newSeqWith(width * height, rng.randRGB())

#         var y_ref = newSeq[uint8](width*height)
#         var u_ref = newSeq[uint8](width*height div 4 + 1) # An extra 1 initialized to 0 to catch overflow
#         var v_ref = newSeq[uint8](width*height div 4 + 1) # An extra 1 initialized to 0 to catch overflow

#         rgb24_yuv420_std(
#           width.uint32, height.uint32,
#           rgb[0].unsafeAddr, rgb_stride = width.uint32 * 3,
#           y_ref[0].addr, u_ref[0].addr, v_ref[0].addr,
#           y_stride = width.uint32, uv_stride = uint32(width+1) div 2,
#           YCbCr_601
#         )

#         # echo "Y: ", y_ref
#         # echo "U: ", u_ref
#         # echo "V: ", v_ref

#         # echo "-----------------------------------------------------"

#         var y_cc = newSeq[uint8](width*height)
#         var u_cc = newSeq[uint8](width*height div 4 + 1) # An extra 1 initialized to 0 to catch overflow
#         var v_cc = newSeq[uint8](width*height div 4 + 1) # An extra 1 initialized to 0 to catch overflow

#         let rgbD = initChannelDesc(rgb[0].unsafeAddr, width, subsampled = false)
#         let yD = initChannelDesc(y_cc[0].addr, width, subsampled = false)
#         let uD = initChannelDesc(u_cc[0].addr, width, subsampled = true)
#         let vD = initChannelDesc(v_cc[0].addr, width, subsampled = true)

#         rgbRaw_to_ycbcr420(
#           width.int32, height.int32, rgbD, yD, uD, vD,
#           BT601
#         )

#         # echo "Y: ", y_cc
#         # echo "U: ", u_cc
#         # echo "V: ", v_cc

#         doAssert: y_cc == y_ref
#         doAssert: u_cc == u_ref
#         doAssert: v_cc == v_ref

#     echo "SUCCESS"

#   main()


#   import std/[times, monotimes]

#   proc bench() =
#     let width = 1920
#     let height = 1080
#     let samples = 1000

#     var rng = initRand(0xFACADE)

#     let rgb = newSeqWith(width * height, rng.randRGB())

#     block:
#       var y_ref = newSeq[uint8](width*height)
#       var u_ref = newSeq[uint8](width*height div 4)
#       var v_ref = newSeq[uint8](width*height div 4)

#       let start = getMonotime()
#       for _ in 0 ..< samples:
#         rgb24_yuv420_std(
#           width.uint32, height.uint32,
#           rgb[0].unsafeAddr, rgb_stride = width.uint32 * 3,
#           y_ref[0].addr, u_ref[0].addr, v_ref[0].addr,
#           y_stride = width.uint32, uv_stride = uint32(width+1) div 2,
#           YCbCr_601
#         )
#       let stop = getMonotime()

#       let elapsed = inMilliseconds(stop - start)
#       echo "ref elapsed: ", elapsed, " ms"
#       echo "ref throughput (",width,"x",height,"): ", samples.float64 * 1e3 / elapsed.float64, " conversions/second"

#     block:
#       var y_cc = newSeq[uint8](width*height)
#       var u_cc = newSeq[uint8](width*height div 4 + 1) # An extra 1 initialized to 0 to catch overflow
#       var v_cc = newSeq[uint8](width*height div 4 + 1) # An extra 1 initialized to 0 to catch overflow

#       let rgbD = initChannelDesc(rgb[0].unsafeAddr, width, subsampled = false)
#       let yD = initChannelDesc(y_cc[0].addr, width, subsampled = false)
#       let uD = initChannelDesc(u_cc[0].addr, width, subsampled = true)
#       let vD = initChannelDesc(v_cc[0].addr, width, subsampled = true)

#       let start = getMonotime()
#       for _ in 0 ..< samples:
#         rgbRaw_to_ycbcr420(
#           width.int32, height.int32, rgbD, yD, uD, vD,
#           BT601
#         )
#       let stop = getMonotime()

#       let elapsed = inMilliseconds(stop - start)
#       echo "cc elapsed: ", elapsed, " ms"
#       echo "cc throughput (",width,"x",height,"): ", samples.float64 * 1000'f64 / elapsed.float64, " conversions/second"

#   bench()