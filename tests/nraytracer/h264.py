# /// nimic
#
# ///
# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

from __future__ import annotations
from nimic.ntypes import *
from nimic.system.ansi_c import c_malloc, c_free, zero_mem
from nimic.std.endians import big_endian32
# from nimic.std.syncio import File

class BitBuffer(Object):
    shift: nint
    cache: uint32
    buf: ptr[UncheckedArray[byte]]
    cursor: nint

@ptr
class Frame(Object):
    Y: ptr[UncheckedArray[uint8]]
    Cb: ptr[UncheckedArray[uint8]]
    Cr: ptr[UncheckedArray[uint8]]
    lumaWidth: int32
    lumaHeight: int32
    size: int32
    buffer: UncheckedArray[uint8]


# class Frame(FrameObject): pass

class H264Encoder(Object):
    sps: seq[byte]
    pps: seq[byte]
    slice_header: seq[byte]
    needCropping: bool
    output: File
    frame: Frame

with const:
    _PPS = array[8, byte]([0x00, 0x00, 0x00, 0x01, 0x68, 0xce, 0x38, 0x80])
    _SliceHeader = array[9, byte]([0x00, 0x00, 0x00, 0x01, 0x05, 0x88, 0x84, 0x21, 0xa0])
    _MacroblockHeader = array[2, byte]([0x0d, 0x00])
    _SliceStopBit = uint8(0x80)

# Accessors Pointer arithmetics
@template
def luma(frame: Frame, x: nint, y: nint) -> uint8:
    return frame.Y[x * frame.lumaWidth + y]

@template
def chromaB(frame: Frame, x: nint, y: nint) -> uint8:
    return frame.Cb[x * (frame.lumaWidth >> 1) + y]

@template
def chromaR(frame: Frame, x: nint, y: nint) -> uint8:
    return frame.Cr[x * (frame.lumaWidth >> 1) + y]

@template
def offset(p: ptr, bytes_count: nint) -> ptr:
    return cast[type(p)](cast[intp](p) + bytes_count)
# template offset*(p: ptr, bytes: int): ptr =
#   cast[typeof(p)](cast[ByteAddress](p) +% bytes)

# Initialization
def put(bb: mut@BitBuffer, n: nint, val: uint32):
    assert (val >> n) == 0, "Value does not fit in the number of bits"
    bb.shift -= n
    assert n <= 32
    if bb.shift < 0:
        assert -bb.shift < 32
        bb.cache = bb.cache | (val >> -bb.shift)
        big_endian32(addr(bb.buf[bb.cursor]), addr(bb.cache))
        bb.cursor += 4
        bb.shift += 32
        bb.cache = uint32(0)
    bb.cache = bb.cache | (val << bb.shift)

def putGolomb(bb: mut@BitBuffer, val: uint32):
    with var:
        size = 1
        t = val + 1
    t = t >> 1
    while t != 0:
        size += 1
        t = t >> 1
    put(bb, 2 * size - 1, val + 1)

def flush(bb: mut@BitBuffer):
    big_endian32(addr(bb.buf[bb.cursor]), addr(bb.cache))
    bb.cursor += 4

@template
def U(nbits: nint, val: uint32):
    """{.dirty.}"""
    put(bb, nbits, val)

@template
def UE(val: SomeInteger):
    """{.dirty.}"""
    putGolomb(bb, uint32(val))

@template_expand
def initSPS(enc: mut@H264Encoder, width: nint, height: nint):
    enc.sps.newSeq(32) # A hack to avoid realloc
    # enc.sps.setLen(32)
    with var:
        bb = BitBuffer(
            shift=0,
            cache=0,
            buf=cast[ptr[UncheckedArray[uint8]]](addr(enc.sps[0])),
            cursor=0
        )

    # Start
    enc.sps[0:4] = array[4, byte]([0x00, 0x00, 0x00, 0x01])

    bb.shift = 32
    bb.cursor = 4

    # SPS:
    U(1, uint32(0))  # forbidden_zero_bit
    U(2, uint32(3))  # nal_ref_idc
    U(5, uint32(7))  # nal_unit_type

    U(8, uint32(66)) # Baseline profile

    # Constraints
    U(1, uint32(0))  # constraint_set0_flag
    U(1, uint32(0))  # constraint_set1_flag
    U(1, uint32(0))  # constraint_set2_flag
    U(1, uint32(0))  # constraint_set3_flag

    U(4, uint32(0))  # reserved_zero_4bits
    U(8, uint32(10)) # level_idc
    UE(0)    # seq_parameter_set_id
    UE(0)    # log2_max_frame_num_minus4
    UE(0)    # pic_order_cnt_type
    UE(0)    # log2_max_pic_order_cnt_lsb_minus4

    UE(0)    # num_ref_frames
    U(1, uint32(0))  # gaps_in_frame_num_value_allowed_flag
    # in Python bitwise operators have lower precedance than arithmetic operators
    UE(((width + 15) >> 4) - 1)  # pic_width_in_mbs_minus_1
    UE(((height + 15) >> 4) - 1) # pic_height_in_map_units_minus_1
    U(1, uint32(1))  # frame_mbs_only_flag
    U(1, uint32(0))  # direct_8x8_inference_flag
    U(1, uint32(enc.needCropping)) # frame_cropping_flag

    if enc.needCropping:
        UE(0)
        UE((enc.frame.lumaWidth - width) >> 1)
        UE(0)
        UE((enc.frame.lumaHeight - height) >> 1)

    U(1, uint32(0))  # vui_parameters_present_flag
    U(1, uint32(1))  # Stop bit

    flush(bb)
    enc.sps.setLen(bb.cursor - (bb.shift // 8))

def initialize(frame: mut@Frame, width: nint, height: nint):
    assert frame.is_nil, "Frame must be nil"

    with let:
        fullSized = width * height
        halfSized = ((width + 1) >> 1) * ((height + 1) >> 1)
        size = fullSized + halfSized + halfSized

    frame <<= cast[Frame](
        alloc_shared0(
            3 * sizeof(pointer) +
            3 * sizeof(int32) +
            size
        )
    )
    #zero_mem(frame, 3 * sizeof(pointer) + 3 * sizeof(int32) + size)

    frame.size = int32(size)
    frame.lumaWidth = int32(width)
    frame.lumaHeight = int32(height)
    frame.Y = cast[ptr[UncheckedArray[uint8]]](addr(frame.buffer))
    frame.Cb = offset(addr(frame.buffer), fullSized)
    frame.Cr = offset(frame.Cb, halfSized)

def init(_: type[H264Encoder], width: nint, height: nint, output: File) -> H264Encoder:
    result = H264Encoder()
    initialize(result.frame, width, height)
    initSPS(result, width, height)
    result.output = output

    _ = write_bytes(result.output, result.sps, 0, len(result.sps))
    _ = write_bytes(result.output, _PPS, 0, len(_PPS))

    return result

def finish(enc: mut@H264Encoder):
    dealloc_shared(enc.frame)
    #c_free(enc.frame)

# Encoding
def encodeMacroblock(enc: mut@H264Encoder, i: nint, j: nint):
    if not (i == 0 and j == 0):
        _ = write_bytes(enc.output, _MacroblockHeader, 0, len(_MacroblockHeader))

    for x in range(i * 16, (i + 1) * 16):
        for y in range(j * 16, (j + 1) * 16):
            enc.output.write(char(int(luma(enc.frame, x, y))))

    for x in range(i * 8, (i + 1) * 8):
        for y in range(j * 8, (j + 1) * 8):
            enc.output.write(char(int(chromaB(enc.frame, x, y))))

    for x in range(i * 8, (i + 1) * 8):
        for y in range(j * 8, (j + 1) * 8):
            enc.output.write(char(int(chromaR(enc.frame, x, y))))

# API
class _FrameBuffers(NTuple):
    Y: ptr[UncheckedArray[uint8]]
    Cb: ptr[UncheckedArray[uint8]]
    Cr: ptr[UncheckedArray[uint8]]

def getFrameBuffers(enc: mut@H264Encoder) -> _FrameBuffers:
    return (enc.frame.Y, enc.frame.Cb, enc.frame.Cr)

def getFrameBuffer(enc: mut@H264Encoder) -> ptr[UncheckedArray[uint8]]:
    return addr(enc.frame.buffer)

def getFrameBufferSize(enc: mut@H264Encoder) -> int32:
    return enc.frame.size

def getWidth(enc: mut@H264Encoder) -> int32:
    return enc.frame.lumaWidth

def getHeight(enc: mut@H264Encoder) -> int32:
    return enc.frame.lumaHeight

def flushFrame(enc: mut@H264Encoder):
    _ = write_bytes(enc.output, _SliceHeader, 0, len(_SliceHeader))

    for i in range(enc.frame.lumaHeight // 16):
        for j in range(enc.frame.lumaWidth // 16):
            encodeMacroblock(enc, i, j)

    enc.output.write(char(int(_SliceStopBit)))
