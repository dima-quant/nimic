import ncode/pydefs
import system/ansi_c
import std/endians
type
  BitBuffer* = object
    shift*: nint
    cache*: uint32
    buf*: ptr UncheckedArray[byte]
    cursor*: nint

  Frame* = ptr object
    Y*: ptr UncheckedArray[uint8]
    Cb*: ptr UncheckedArray[uint8]
    Cr*: ptr UncheckedArray[uint8]
    lumaWidth*: int32
    lumaHeight*: int32
    size*: int32
    buffer*: UncheckedArray[uint8]

  H264Encoder* = object
    sps*: seq[byte]
    pps*: seq[byte]
    slice_header*: seq[byte]
    needCropping*: bool
    output*: File
    frame*: Frame

const
  local_PPS = array[8, byte]([byte(0), 0, 0, 1, 104, 206, 56, 128])
  local_SliceHeader = array[9, byte]([byte(0), 0, 0, 1, 5, 136, 132, 33, 160])
  local_MacroblockHeader = array[2, byte]([byte(13), 0])
  local_SliceStopBit = uint8(128)

template luma*(frame: Frame, x: nint, y: nint): uint8 =
  frame.Y[x * frame.lumaWidth + y]

template chromaB*(frame: Frame, x: nint, y: nint): uint8 =
  frame.Cb[x * (frame.lumaWidth shr 1) + y]

template chromaR*(frame: Frame, x: nint, y: nint): uint8 =
  frame.Cr[x * (frame.lumaWidth shr 1) + y]

template offset*(p: ptr, bytes_count: nint): ptr =
  cast[type(p)](cast[intp](p) + bytes_count)

proc put*(bb: var BitBuffer, n: nint, val: uint32) =
  assert val shr n == 0, "Value does not fit in the number of bits"
  bb.shift -= n
  assert n <= 32
  if bb.shift < 0:
    assert -bb.shift < 32
    bb.cache = bb.cache or val shr -bb.shift
    big_endian32(addr(bb.buf[bb.cursor]), addr(bb.cache))
    bb.cursor += 4
    bb.shift += 32
    bb.cache = uint32(0)
  bb.cache = bb.cache or val shl bb.shift

proc putGolomb*(bb: var BitBuffer, val: uint32) =
  var
    size = 1
    t = val + 1
  t = t shr 1
  while t != 0:
    size += 1
    t = t shr 1
  put(bb, 2 * size - 1, val + 1)

proc flush*(bb: var BitBuffer) =
  big_endian32(addr(bb.buf[bb.cursor]), addr(bb.cache))
  bb.cursor += 4

template U*(nbits: nint, val: uint32) {.dirty.} =
  put(bb, nbits, val)

template UE*(val: SomeInteger) {.dirty.} =
  putGolomb(bb, uint32(val))

proc initSPS*(enc: var H264Encoder, width: nint, height: nint) =
  enc.sps.newSeq(32)
  var
    bb = BitBuffer(shift:0, cache:0, buf:cast[ptr UncheckedArray[uint8]](addr(enc.sps[0])), cursor:0)
  enc.sps[0..<4] = array[4, byte]([byte(0), 0, 0, 1])
  bb.shift = 32
  bb.cursor = 4
  U(1, uint32(0))
  U(2, uint32(3))
  U(5, uint32(7))
  U(8, uint32(66))
  U(1, uint32(0))
  U(1, uint32(0))
  U(1, uint32(0))
  U(1, uint32(0))
  U(4, uint32(0))
  U(8, uint32(10))
  UE(0)
  UE(0)
  UE(0)
  UE(0)
  UE(0)
  U(1, uint32(0))
  UE((width + 15) shr 4 - 1)
  UE((height + 15) shr 4 - 1)
  U(1, uint32(1))
  U(1, uint32(0))
  U(1, uint32(enc.needCropping))
  if enc.needCropping:
    UE(0)
    UE((enc.frame.lumaWidth - width) shr 1)
    UE(0)
    UE((enc.frame.lumaHeight - height) shr 1)
  U(1, uint32(0))
  U(1, uint32(1))
  flush(bb)
  enc.sps.setLen(bb.cursor - bb.shift div 8)

proc initialize*(frame: var Frame, width: nint, height: nint) =
  assert frame.is_nil, "Frame must be nil"
  let
    fullSized = width * height
    halfSized = (width + 1) shr 1 * ((height + 1) shr 1)
    size = fullSized + halfSized + halfSized
  frame = cast[Frame](allocShared0(3 * sizeof(pointer) + 3 * sizeof(int32) + size))
  frame.size = int32(size)
  frame.lumaWidth = int32(width)
  frame.lumaHeight = int32(height)
  frame.Y = cast[ptr UncheckedArray[uint8]](addr(frame.buffer))
  frame.Cb = offset(addr(frame.buffer), fullSized)
  frame.Cr = offset(frame.Cb, halfSized)

proc init*(_: type[H264Encoder], width: nint, height: nint, output: File): H264Encoder =
  result = H264Encoder()
  initialize(result.frame, width, height)
  initSPS(result, width, height)
  result.output = output
  discard writeBytes(result.output, result.sps, 0, len(result.sps))
  discard writeBytes(result.output, local_PPS, 0, len(local_PPS))
  return result

proc finish*(enc: var H264Encoder) =
  deallocShared(enc.frame)

proc encodeMacroblock*(enc: var H264Encoder, i: nint, j: nint) =
  if not (i == 0 and j == 0):
    discard writeBytes(enc.output, local_MacroblockHeader, 0, len(local_MacroblockHeader))
  for x in range(i * 16, (i + 1) * 16):
    for y in range(j * 16, (j + 1) * 16):
      enc.output.write(chr(int(luma(enc.frame, x, y))))
  for x in range(i * 8, (i + 1) * 8):
    for y in range(j * 8, (j + 1) * 8):
      enc.output.write(chr(int(chromaB(enc.frame, x, y))))
  for x in range(i * 8, (i + 1) * 8):
    for y in range(j * 8, (j + 1) * 8):
      enc.output.write(chr(int(chromaR(enc.frame, x, y))))
type
  local_FrameBuffers = tuple
    Y: ptr UncheckedArray[uint8]
    Cb: ptr UncheckedArray[uint8]
    Cr: ptr UncheckedArray[uint8]


proc getFrameBuffers*(enc: var H264Encoder): local_FrameBuffers =
  return (enc.frame.Y, enc.frame.Cb, enc.frame.Cr)

proc getFrameBuffer*(enc: var H264Encoder): ptr UncheckedArray[uint8] =
  return addr(enc.frame.buffer)

proc getFrameBufferSize*(enc: var H264Encoder): int32 =
  return enc.frame.size

proc getWidth*(enc: var H264Encoder): int32 =
  return enc.frame.lumaWidth

proc getHeight*(enc: var H264Encoder): int32 =
  return enc.frame.lumaHeight

proc flushFrame*(enc: var H264Encoder) =
  discard writeBytes(enc.output, local_SliceHeader, 0, len(local_SliceHeader))
  for i in range(enc.frame.lumaHeight div 16):
    for j in range(enc.frame.lumaWidth div 16):
      encodeMacroblock(enc, i, j)
  enc.output.write(chr(int(local_SliceStopBit)))