# Pure Nim translation of minimp4.h (muxer-only)
# Translated from https://github.com/lieff/minimp4
# Using c_malloc/cast/UncheckedArray/addr style per project convention

import system/ansi_c

# =========================================================================
# Constants
# =========================================================================

const
  MP4E_STATUS_OK* = 0
  MP4E_STATUS_BAD_ARGUMENTS* = -1
  MP4E_STATUS_NO_MEMORY* = -2
  MP4E_STATUS_FILE_WRITE_ERROR* = -3
  MP4E_STATUS_ONLY_ONE_DSI_ALLOWED* = -4

  MP4E_SAMPLE_DEFAULT* = 0
  MP4E_SAMPLE_RANDOM_ACCESS* = 1
  MP4E_SAMPLE_CONTINUATION* = 2

  MP4_OBJECT_TYPE_AUDIO_ISO_IEC_14496_3* = 0x40'u32
  MP4_OBJECT_TYPE_AVC* = 0x21'u32
  MP4_OBJECT_TYPE_HEVC* = 0x23'u32

  MINIMP4_MAX_SPS = 32
  MINIMP4_MAX_PPS = 256

  HEVC_NAL_VPS = 32
  HEVC_NAL_SPS = 33
  HEVC_NAL_PPS = 34
  HEVC_NAL_BLA_W_LP = 16
  HEVC_NAL_CRA_NUT = 21

  MOOV_TIMESCALE = 1000'u32

proc fourCC(a, b, c, d: char): uint32 {.inline.} =
  (uint32(a.uint8) shl 24) or (uint32(b.uint8) shl 16) or
  (uint32(c.uint8) shl 8) or uint32(d.uint8)

# Box type constants
let
  BOX_co64 = fourCC('c','o','6','4')
  BOX_stco = fourCC('s','t','c','o')
  BOX_ctts = fourCC('c','t','t','s')
  BOX_dinf = fourCC('d','i','n','f')
  BOX_dref = fourCC('d','r','e','f')
  BOX_edts = fourCC('e','d','t','s')
  BOX_elst = fourCC('e','l','s','t')
  BOX_free = fourCC('f','r','e','e')
  BOX_hdlr = fourCC('h','d','l','r')
  BOX_mdia = fourCC('m','d','i','a')
  BOX_mdat = fourCC('m','d','a','t')
  BOX_mdhd = fourCC('m','d','h','d')
  BOX_minf = fourCC('m','i','n','f')
  BOX_moov = fourCC('m','o','o','v')
  BOX_mvhd = fourCC('m','v','h','d')
  BOX_stsd = fourCC('s','t','s','d')
  BOX_stsz = fourCC('s','t','s','z')
  BOX_stbl = fourCC('s','t','b','l')
  BOX_stsc = fourCC('s','t','s','c')
  BOX_smhd = fourCC('s','m','h','d')
  BOX_stss = fourCC('s','t','s','s')
  BOX_stts = fourCC('s','t','t','s')
  BOX_trak = fourCC('t','r','a','k')
  BOX_tkhd = fourCC('t','k','h','d')
  BOX_udta = fourCC('u','d','t','a')
  BOX_vmhd = fourCC('v','m','h','d')
  BOX_url  = fourCC('u','r','l',' ')
  BOX_ftyp = fourCC('f','t','y','p')
  BOX_esds = fourCC('e','s','d','s')
  BOX_mp4a = fourCC('m','p','4','a')
  BOX_mp4s = fourCC('m','p','4','s')
  BOX_avc1 = fourCC('a','v','c','1')
  BOX_avcC = fourCC('a','v','c','C')
  BOX_hvc1 = fourCC('h','v','c','1')
  BOX_hvcC = fourCC('h','v','c','C')
  BOX_nmhd = fourCC('n','m','h','d')
  BOX_mvex = fourCC('m','v','e','x')
  BOX_trex = fourCC('t','r','e','x')
  BOX_moof = fourCC('m','o','o','f')
  BOX_mfhd = fourCC('m','f','h','d')
  BOX_traf = fourCC('t','r','a','f')
  BOX_tfhd = fourCC('t','f','h','d')
  BOX_trun = fourCC('t','r','u','n')
  BOX_mehd = fourCC('m','e','h','d')
  BOX_meta = fourCC('m','e','t','a')
  BOX_ilst = fourCC('i','l','s','t')
  BOX_ccmt = fourCC('\xa9','c','m','t')
  BOX_data = fourCC('d','a','t','a')

const box_ftyp_data: array[24, byte] = [
  0'u8, 0, 0, 0x18, ord('f').byte, ord('t').byte, ord('y').byte, ord('p').byte,
  ord('m').byte, ord('p').byte, ord('4').byte, ord('2').byte,
  0, 0, 0, 0,
  ord('m').byte, ord('p').byte, ord('4').byte, ord('2').byte,
  ord('i').byte, ord('s').byte, ord('o').byte, ord('m').byte
]

# =========================================================================
# Types
# =========================================================================

type
  TrackMediaKind* = enum
    e_audio, e_video, e_private

  MP4E_track_t* = object
    object_type_indication*: uint32
    language*: array[4, byte]
    track_media_kind*: TrackMediaKind
    time_scale*: uint32
    default_duration*: uint32
    # Union: for video width/height, for audio channelcount
    width*: int32
    height*: int32
    channelcount*: uint32

  MiniMp4Vector = object
    data: ptr UncheckedArray[byte]
    bytes: int
    capacity: int

  SampleT = object
    size: uint64      # boxsize_t
    offset: uint64
    duration: uint32
    flag_random_access: uint32

  TrackT = object
    info: MP4E_track_t
    smpl: MiniMp4Vector
    pending_sample: MiniMp4Vector
    vsps: MiniMp4Vector
    vpps: MiniMp4Vector
    vvps: MiniMp4Vector

  WriteCallback* = proc(offset: int64, buffer: pointer, size: csize_t,
                         token: pointer): cint {.cdecl.}

  MP4E_mux_t* = object
    tracks: MiniMp4Vector
    write_pos*: int64
    write_callback: WriteCallback
    token: pointer
    text_comment: cstring
    sequential_mode_flag: int
    enable_fragmentation: int
    fragments_count: int

  BitReaderT = object
    cache: uint32
    cache_free_bits: int
    buf: ptr uint16
    origin: ptr uint16
    origin_bytes: uint32

  H264SpsIdPatcher = object
    sps_cache: array[MINIMP4_MAX_SPS, pointer]
    pps_cache: array[MINIMP4_MAX_PPS, pointer]
    sps_bytes: array[MINIMP4_MAX_SPS, int]
    pps_bytes: array[MINIMP4_MAX_PPS, int]
    map_sps: array[MINIMP4_MAX_SPS, int]
    map_pps: array[MINIMP4_MAX_PPS, int]

  mp4_h26x_writer_t* = object
    sps_patcher: H264SpsIdPatcher
    mux*: ptr MP4E_mux_t
    mux_track_id*: int
    is_hevc*: int
    need_vps*: int
    need_sps*: int
    need_pps*: int
    need_idr*: int

  BsT = object
    shift: int
    cache: uint32
    buf: ptr uint32
    origin: ptr uint32

# =========================================================================
# Vector helpers
# =========================================================================

proc vectorInit(h: ptr MiniMp4Vector, capacity: int): int =
  h.bytes = 0
  h.capacity = capacity
  if capacity > 0:
    h.data = cast[ptr UncheckedArray[byte]](c_malloc(csize_t capacity))
    if h.data == nil: return 0
  else:
    h.data = nil
  return 1

proc vectorReset(h: ptr MiniMp4Vector) =
  if h.data != nil:
    c_free(h.data)
  zeroMem(h, sizeof(MiniMp4Vector))

proc vectorGrow(h: ptr MiniMp4Vector, bytes: int): int =
  var newSize = h.capacity * 2 + 1024
  if newSize < h.capacity + bytes:
    newSize = h.capacity + bytes + 1024
  let p = c_realloc(h.data, csize_t newSize)
  if p == nil: return 0
  h.data = cast[ptr UncheckedArray[byte]](p)
  h.capacity = newSize
  return 1

proc vectorAllocTail(h: ptr MiniMp4Vector, bytes: int): ptr byte =
  if h.data == nil and vectorInit(h, 2 * bytes + 1024) == 0:
    return nil
  if (h.capacity - h.bytes) < bytes and vectorGrow(h, bytes) == 0:
    return nil
  result = addr h.data[h.bytes]
  h.bytes += bytes

proc vectorPut(h: ptr MiniMp4Vector, buf: pointer, bytes: int): ptr byte =
  let tail = vectorAllocTail(h, bytes)
  if tail != nil:
    copyMem(tail, buf, bytes)
  return tail

# =========================================================================
# Write macros as templates
# =========================================================================

template WR1(p: var ptr byte, x: uint32) =
  p[] = byte(x and 0xFF)
  p = cast[ptr byte](cast[uint](p) + 1)

template WRITE_1(p: var ptr byte, x: uint32) =
  WR1(p, x)

template WRITE_2(p: var ptr byte, x: uint32) =
  WR1(p, (x shr 8))
  WR1(p, x)

template WRITE_3(p: var ptr byte, x: uint32) =
  WR1(p, (x shr 16))
  WR1(p, (x shr 8))
  WR1(p, x)

template WRITE_4(p: var ptr byte, x: uint32) =
  WR1(p, (x shr 24))
  WR1(p, (x shr 16))
  WR1(p, (x shr 8))
  WR1(p, x)

proc WR4(p: ptr byte, x: int) =
  let xu = uint32(x)
  let arr = cast[ptr UncheckedArray[byte]](p)
  arr[0] = byte((xu shr 24) and 0xFF)
  arr[1] = byte((xu shr 16) and 0xFF)
  arr[2] = byte((xu shr 8) and 0xFF)
  arr[3] = byte(xu and 0xFF)

template ATOM(p: var ptr byte, stack: var ptr ptr byte, x: uint32) =
  (cast[ptr ptr byte](stack))[] = p
  stack = cast[ptr ptr byte](cast[uint](stack) + uint(sizeof(pointer)))
  p = cast[ptr byte](cast[uint](p) + 4)
  WRITE_4(p, x)

template ATOM_FULL(p: var ptr byte, stack: var ptr ptr byte, x: uint32, flag: uint32) =
  ATOM(p, stack, x)
  WRITE_4(p, flag)

template END_ATOM(p: var ptr byte, stack: var ptr ptr byte) =
  stack = cast[ptr ptr byte](cast[uint](stack) - uint(sizeof(pointer)))
  let atomStart = (cast[ptr ptr byte](stack))[]
  WR4(atomStart, cast[int](p) - cast[int](atomStart))

template ERR(expr: int): untyped =
  block:
    let err = expr
    if err != 0:
      return err

proc ptrDiff(a, b: ptr byte): int {.inline.} =
  cast[int](a) - cast[int](b)

proc ptrAdd(p: ptr byte, n: int): ptr byte {.inline.} =
  cast[ptr byte](cast[uint](p) + uint(n))

# =========================================================================
# Helper functions
# =========================================================================

proc appendMem(v: ptr MiniMp4Vector, mem: pointer, bytes: int): int =
  var i = 0
  let p = v.data
  while i + 2 < v.bytes:
    let cb = int(p[i]) * 256 + int(p[i + 1])
    if cb == bytes and cmpMem(ptrAdd(cast[ptr byte](addr p[i + 2]), 0), mem, cb) == 0:
      return 1
    i += 2 + cb
  var size: array[2, byte]
  size[0] = byte(bytes shr 8)
  size[1] = byte(bytes and 0xFF)
  result = int(vectorPut(v, addr size[0], 2) != nil and
               vectorPut(v, mem, bytes) != nil)

proc itemsCount(v: ptr MiniMp4Vector): int =
  var i = 0
  var count = 0
  let p = v.data
  while i + 2 < v.bytes:
    let cb = int(p[i]) * 256 + int(p[i + 1])
    count += 1
    i += 2 + cb
  return count

proc getDuration(tr: ptr TrackT): uint32 =
  var sumDuration: uint32 = 0
  let s = cast[ptr UncheckedArray[SampleT]](tr.smpl.data)
  let count = tr.smpl.bytes div sizeof(SampleT)
  for i in 0 ..< count:
    sumDuration += s[i].duration
  return sumDuration

proc writePendingData(mux: ptr MP4E_mux_t, tr: ptr TrackT): int =
  if tr.pending_sample.bytes > 0 and tr.smpl.bytes >= sizeof(SampleT):
    var base: array[8, byte]
    var p = cast[ptr byte](addr base[0])
    WRITE_4(p, uint32(tr.pending_sample.bytes + 8))
    WRITE_4(p, BOX_mdat)
    ERR(mux.write_callback(mux.write_pos, addr base[0], csize_t(ptrDiff(p, cast[ptr byte](addr base[0]))), mux.token))
    mux.write_pos += ptrDiff(p, cast[ptr byte](addr base[0]))
    # Update last sample descriptor
    let smplDesc = cast[ptr SampleT](cast[uint](vectorAllocTail(addr tr.smpl, 0)) - uint(sizeof(SampleT)))
    smplDesc.size = uint64(tr.pending_sample.bytes)
    smplDesc.offset = uint64(mux.write_pos)
    ERR(mux.write_callback(mux.write_pos, tr.pending_sample.data, csize_t(tr.pending_sample.bytes), mux.token))
    mux.write_pos += tr.pending_sample.bytes
    tr.pending_sample.bytes = 0
  return MP4E_STATUS_OK

proc addSampleDescriptor(mux: ptr MP4E_mux_t, tr: ptr TrackT,
                          dataBytes: int, duration: int, kind: int): int =
  var smp: SampleT
  smp.size = uint64(dataBytes)
  smp.offset = uint64(mux.write_pos)
  smp.duration = if duration != 0: uint32(duration) else: tr.info.default_duration
  smp.flag_random_access = uint32(ord(kind == MP4E_SAMPLE_RANDOM_ACCESS))
  return int(vectorPut(addr tr.smpl, addr smp, sizeof(SampleT)) != nil)

proc odSizeOfSize(size: int): int =
  result = 1
  var i = size
  while i > 0x7F:
    result += 1
    i -= 0x7F

# Forward declaration
proc mp4eFlushIndex(mux: ptr MP4E_mux_t): int

# =========================================================================
# MP4E API
# =========================================================================

proc MP4E_open*(sequential_mode_flag: int, enable_fragmentation: int,
                token: pointer, write_callback: WriteCallback): ptr MP4E_mux_t =
  if write_callback(0, unsafeAddr box_ftyp_data[0], csize_t(sizeof(box_ftyp_data)), token) != 0:
    return nil
  let mux = cast[ptr MP4E_mux_t](c_malloc(csize_t sizeof(MP4E_mux_t)))
  if mux == nil: return nil
  mux.sequential_mode_flag = if (sequential_mode_flag != 0 or enable_fragmentation != 0): 1 else: 0
  mux.enable_fragmentation = enable_fragmentation
  mux.fragments_count = 0
  mux.write_callback = write_callback
  mux.token = token
  mux.text_comment = nil
  mux.write_pos = int64(sizeof(box_ftyp_data))
  if mux.sequential_mode_flag == 0:
    if mux.write_callback(mux.write_pos, unsafeAddr box_ftyp_data[0], 8, mux.token) != 0:
      c_free(mux)
      return nil
    mux.write_pos += 16
  discard vectorInit(addr mux.tracks, 2 * sizeof(TrackT))
  return mux

proc MP4E_add_track*(mux: ptr MP4E_mux_t, track_data: ptr MP4E_track_t): int =
  if mux == nil or track_data == nil:
    return MP4E_STATUS_BAD_ARGUMENTS
  let ntr = mux.tracks.bytes div sizeof(TrackT)
  let trp = vectorAllocTail(addr mux.tracks, sizeof(TrackT))
  if trp == nil: return MP4E_STATUS_NO_MEMORY
  let tr = cast[ptr TrackT](trp)
  zeroMem(tr, sizeof(TrackT))
  copyMem(addr tr.info, track_data, sizeof(MP4E_track_t))
  if vectorInit(addr tr.smpl, 256) == 0: return MP4E_STATUS_NO_MEMORY
  discard vectorInit(addr tr.vsps, 0)
  discard vectorInit(addr tr.vpps, 0)
  discard vectorInit(addr tr.pending_sample, 0)
  return ntr

proc MP4E_set_dsi*(mux: ptr MP4E_mux_t, track_id: int, dsi: pointer, bytes: int): int =
  let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(track_id * sizeof(TrackT)))
  if tr.vsps.bytes != 0: return MP4E_STATUS_ONLY_ONE_DSI_ALLOWED
  if appendMem(addr tr.vsps, dsi, bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_set_vps*(mux: ptr MP4E_mux_t, track_id: int, vps: pointer, bytes: int): int =
  let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(track_id * sizeof(TrackT)))
  if appendMem(addr tr.vvps, vps, bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_set_sps*(mux: ptr MP4E_mux_t, track_id: int, sps: pointer, bytes: int): int =
  let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(track_id * sizeof(TrackT)))
  if appendMem(addr tr.vsps, sps, bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_set_pps*(mux: ptr MP4E_mux_t, track_id: int, pps: pointer, bytes: int): int =
  let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(track_id * sizeof(TrackT)))
  if appendMem(addr tr.vpps, pps, bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_put_sample*(mux: ptr MP4E_mux_t, track_num: int, data: pointer,
                      data_bytes: int, duration: int, kind: int): int =
  if mux == nil or data == nil: return MP4E_STATUS_BAD_ARGUMENTS
  let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(track_num * sizeof(TrackT)))
  if mux.enable_fragmentation != 0:
    if mux.fragments_count == 0:
      ERR(mp4eFlushIndex(mux))
    mux.fragments_count += 1
    #ERR(mp4eWriteFragmentHeader(mux, track_num, data_bytes, duration, kind))
    # Fragment mode not needed for our use case — skip
    return MP4E_STATUS_OK
  if kind != MP4E_SAMPLE_CONTINUATION:
    if mux.sequential_mode_flag != 0:
      ERR(writePendingData(mux, tr))
    if addSampleDescriptor(mux, tr, data_bytes, duration, kind) == 0:
      return MP4E_STATUS_NO_MEMORY
  else:
    if mux.sequential_mode_flag == 0:
      if tr.smpl.bytes < sizeof(SampleT):
        return MP4E_STATUS_NO_MEMORY
      let smplDesc = cast[ptr SampleT](cast[uint](tr.smpl.data) + uint(tr.smpl.bytes) - uint(sizeof(SampleT)))
      smplDesc.size += uint64(data_bytes)
  if mux.sequential_mode_flag != 0:
    if vectorPut(addr tr.pending_sample, data, data_bytes) == nil:
      return MP4E_STATUS_NO_MEMORY
  else:
    ERR(mux.write_callback(mux.write_pos, data, csize_t(data_bytes), mux.token))
    mux.write_pos += data_bytes
  return MP4E_STATUS_OK

# =========================================================================
# mp4eFlushIndex — write moov box with all indexes
# =========================================================================

const
  MP4E_HANDLER_TYPE_VIDE = 0x76696465'u32
  MP4E_HANDLER_TYPE_SOUN = 0x736F756E'u32
  MP4E_HANDLER_TYPE_GESM = 0x6765736D'u32
  MP4E_HANDLER_TYPE_MDIR = 0x6D646972'u32
  FILE_HEADER_BYTES = 256
  TRACK_HEADER_BYTES = 512

proc mp4eFlushIndex(mux: ptr MP4E_mux_t): int =
  var stackBase: array[20, ptr byte]
  var stack = cast[ptr ptr byte](addr stackBase[0])
  let ntracks = mux.tracks.bytes div sizeof(TrackT)
  # Calculate index buffer size
  var indexBytes = FILE_HEADER_BYTES
  if mux.text_comment != nil:
    indexBytes += 128 + len($mux.text_comment)
  for ntr in 0 ..< ntracks:
    let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(ntr * sizeof(TrackT)))
    indexBytes += TRACK_HEADER_BYTES
    indexBytes += tr.smpl.bytes * (sizeof(SampleT) + 4 + 4) div sizeof(SampleT)
    indexBytes += tr.vsps.bytes
    indexBytes += tr.vpps.bytes
    ERR(writePendingData(mux, tr))
  let base = cast[ptr byte](c_malloc(csize_t indexBytes))
  if base == nil: return MP4E_STATUS_NO_MEMORY
  var p = base

  if mux.sequential_mode_flag == 0:
    let size = mux.write_pos - int64(sizeof(box_ftyp_data))
    let sizeLimit = int64(0xFFFFFFFE'u64)
    if size > sizeLimit:
      WRITE_4(p, 1'u32)
      WRITE_4(p, BOX_mdat)
      WRITE_4(p, uint32((size shr 32) and 0xFFFFFFFF))
      WRITE_4(p, uint32(size and 0xFFFFFFFF))
    else:
      WRITE_4(p, 8'u32)
      WRITE_4(p, BOX_free)
      WRITE_4(p, uint32(size - 8))
      WRITE_4(p, BOX_mdat)
    ERR(mux.write_callback(int64(sizeof(box_ftyp_data)), base, csize_t(ptrDiff(p, base)), mux.token))
    p = base

  # moov
  ATOM(p, stack, BOX_moov)
  ATOM_FULL(p, stack, BOX_mvhd, 0'u32)
  WRITE_4(p, 0'u32) # creation_time
  WRITE_4(p, 0'u32) # modification_time
  if ntracks > 0:
    let tr = cast[ptr TrackT](mux.tracks.data)
    var duration = getDuration(tr)
    duration = uint32(uint64(duration) * uint64(MOOV_TIMESCALE) div uint64(tr.info.time_scale))
    WRITE_4(p, MOOV_TIMESCALE)
    WRITE_4(p, duration)
  WRITE_4(p, 0x00010000'u32) # rate
  WRITE_2(p, 0x0100'u32)     # volume
  WRITE_2(p, 0'u32)
  WRITE_4(p, 0'u32); WRITE_4(p, 0'u32) # reserved
  # matrix[9]
  WRITE_4(p, 0x00010000'u32); WRITE_4(p, 0'u32); WRITE_4(p, 0'u32)
  WRITE_4(p, 0'u32); WRITE_4(p, 0x00010000'u32); WRITE_4(p, 0'u32)
  WRITE_4(p, 0'u32); WRITE_4(p, 0'u32); WRITE_4(p, 0x40000000'u32)
  # pre_defined[6]
  for i in 0 ..< 6: WRITE_4(p, 0'u32)
  WRITE_4(p, uint32(ntracks + 1)) # next_track_ID
  END_ATOM(p, stack)

  for ntr in 0 ..< ntracks:
    let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(ntr * sizeof(TrackT)))
    let duration = getDuration(tr)
    var samplesCount = tr.smpl.bytes div sizeof(SampleT)
    let sample = cast[ptr UncheckedArray[SampleT]](tr.smpl.data)
    var handlerType: uint32
    var handlerAscii: string

    if mux.enable_fragmentation != 0:
      samplesCount = 0
    elif samplesCount <= 0:
      continue

    case tr.info.track_media_kind
    of e_audio:
      handlerType = MP4E_HANDLER_TYPE_SOUN
      handlerAscii = "SoundHandler"
    of e_video:
      handlerType = MP4E_HANDLER_TYPE_VIDE
      handlerAscii = "VideoHandler"
    of e_private:
      handlerType = MP4E_HANDLER_TYPE_GESM
      handlerAscii = ""

    # trak
    ATOM(p, stack, BOX_trak)
    ATOM_FULL(p, stack, BOX_tkhd, 7'u32)
    WRITE_4(p, 0'u32) # creation_time
    WRITE_4(p, 0'u32) # modification_time
    WRITE_4(p, uint32(ntr + 1)) # track_ID
    WRITE_4(p, 0'u32) # reserved
    WRITE_4(p, uint32(uint64(duration) * uint64(MOOV_TIMESCALE) div uint64(tr.info.time_scale)))
    WRITE_4(p, 0'u32); WRITE_4(p, 0'u32) # reserved
    WRITE_2(p, 0'u32) # layer
    WRITE_2(p, 0'u32) # alternate_group
    WRITE_2(p, 0x0100'u32) # volume
    WRITE_2(p, 0'u32) # reserved
    # matrix[9]
    WRITE_4(p, 0x00010000'u32); WRITE_4(p, 0'u32); WRITE_4(p, 0'u32)
    WRITE_4(p, 0'u32); WRITE_4(p, 0x00010000'u32); WRITE_4(p, 0'u32)
    WRITE_4(p, 0'u32); WRITE_4(p, 0'u32); WRITE_4(p, 0x40000000'u32)
    if tr.info.track_media_kind == e_audio or tr.info.track_media_kind == e_private:
      WRITE_4(p, 0'u32); WRITE_4(p, 0'u32)
    else:
      WRITE_4(p, uint32(tr.info.width) * 0x10000'u32)
      WRITE_4(p, uint32(tr.info.height) * 0x10000'u32)
    END_ATOM(p, stack)

    # mdia
    ATOM(p, stack, BOX_mdia)
    ATOM_FULL(p, stack, BOX_mdhd, 0'u32)
    WRITE_4(p, 0'u32); WRITE_4(p, 0'u32) # creation/modification
    WRITE_4(p, tr.info.time_scale)
    WRITE_4(p, duration)
    block:
      let langCode = uint32(((int(tr.info.language[0]) and 31) shl 10) or
                            ((int(tr.info.language[1]) and 31) shl 5) or
                            (int(tr.info.language[2]) and 31))
      WRITE_2(p, langCode)
    WRITE_2(p, 0'u32) # pre_defined
    END_ATOM(p, stack)

    ATOM_FULL(p, stack, BOX_hdlr, 0'u32)
    WRITE_4(p, 0'u32) # pre_defined
    WRITE_4(p, handlerType)
    WRITE_4(p, 0'u32); WRITE_4(p, 0'u32); WRITE_4(p, 0'u32) # reserved
    if handlerAscii.len > 0:
      for i in 0 ..< handlerAscii.len:
        WRITE_1(p, uint32(handlerAscii[i]))
      WRITE_1(p, 0'u32) # null terminator
    else:
      WRITE_4(p, 0'u32)
    END_ATOM(p, stack)

    # minf
    ATOM(p, stack, BOX_minf)
    if tr.info.track_media_kind == e_audio:
      ATOM_FULL(p, stack, BOX_smhd, 0'u32)
      WRITE_2(p, 0'u32); WRITE_2(p, 0'u32)
      END_ATOM(p, stack)
    if tr.info.track_media_kind == e_video:
      ATOM_FULL(p, stack, BOX_vmhd, 1'u32)
      WRITE_2(p, 0'u32); WRITE_2(p, 0'u32); WRITE_2(p, 0'u32); WRITE_2(p, 0'u32)
      END_ATOM(p, stack)

    # dinf
    ATOM(p, stack, BOX_dinf)
    ATOM_FULL(p, stack, BOX_dref, 0'u32)
    WRITE_4(p, 1'u32) # entry_count
    ATOM_FULL(p, stack, BOX_url, 1'u32)
    END_ATOM(p, stack)
    END_ATOM(p, stack)
    END_ATOM(p, stack)

    # stbl
    ATOM(p, stack, BOX_stbl)
    ATOM_FULL(p, stack, BOX_stsd, 0'u32)
    WRITE_4(p, 1'u32) # entry_count

    if tr.info.track_media_kind == e_audio or tr.info.track_media_kind == e_private:
      if tr.info.track_media_kind == e_audio:
        ATOM(p, stack, BOX_mp4a)
      else:
        ATOM(p, stack, BOX_mp4s)
      WRITE_4(p, 0'u32); WRITE_2(p, 0'u32) # reserved
      WRITE_2(p, 1'u32) # data_reference_index
      if tr.info.track_media_kind == e_audio:
        WRITE_4(p, 0'u32); WRITE_4(p, 0'u32)
        WRITE_2(p, uint32(tr.info.channelcount))
        WRITE_2(p, 16'u32)
        WRITE_4(p, 0'u32)
        WRITE_4(p, tr.info.time_scale shl 16)
      ATOM_FULL(p, stack, BOX_esds, 0'u32)
      if tr.vsps.bytes > 0:
        let dsiBytes = tr.vsps.bytes - 2
        var dsiBytesVar = dsiBytes
        let dsiSizeSize = odSizeOfSize(dsiBytes)
        let dcdBytes = dsiBytes + dsiSizeSize + 1 + (1 + 1 + 3 + 4 + 4)
        var dcdBytesVar = dcdBytes
        let dcdSizeSize = odSizeOfSize(dcdBytes)
        var esdBytes = dcdBytes + dcdSizeSize + 1 + 3
        WRITE_1(p, 3'u32) # OD_ESD
        # WRITE_OD_LEN
        while esdBytes > 0x7F:
          esdBytes -= 0x7F
          WRITE_1(p, 0x00FF'u32)
        WRITE_1(p, uint32(esdBytes))
        WRITE_2(p, 0'u32) # ES_ID
        WRITE_1(p, 0'u32) # flags
        WRITE_1(p, 4'u32) # OD_DCD
        while dcdBytesVar > 0x7F:
          dcdBytesVar -= 0x7F
          WRITE_1(p, 0x00FF'u32)
        WRITE_1(p, uint32(dcdBytesVar))
        if tr.info.track_media_kind == e_audio:
          WRITE_1(p, uint32(MP4_OBJECT_TYPE_AUDIO_ISO_IEC_14496_3))
          WRITE_1(p, 5'u32 shl 2)
        else:
          WRITE_1(p, 208'u32)
          WRITE_1(p, 32'u32 shl 2)
        WRITE_3(p, uint32(tr.info.channelcount * 6144 div 8))
        WRITE_4(p, 0'u32); WRITE_4(p, 0'u32)
        WRITE_1(p, 5'u32) # OD_DSI
        while dsiBytesVar > 0x7F:
          dsiBytesVar -= 0x7F
          WRITE_1(p, 0x00FF'u32)
        WRITE_1(p, uint32(dsiBytesVar))
        for i in 0 ..< dsiBytes:
          WRITE_1(p, uint32(tr.vsps.data[2 + i]))
      END_ATOM(p, stack)
      END_ATOM(p, stack)

    if tr.info.track_media_kind == e_video and
       (MP4_OBJECT_TYPE_AVC == tr.info.object_type_indication or
        MP4_OBJECT_TYPE_HEVC == tr.info.object_type_indication):
      let numSPS = itemsCount(addr tr.vsps)
      let numPPS = itemsCount(addr tr.vpps)
      if MP4_OBJECT_TYPE_AVC == tr.info.object_type_indication:
        ATOM(p, stack, BOX_avc1)
      else:
        ATOM(p, stack, BOX_hvc1)
      # VisualSampleEntry
      WRITE_2(p, 0'u32); WRITE_2(p, 0'u32); WRITE_2(p, 0'u32) # reserved
      WRITE_2(p, 1'u32) # data_reference_index
      WRITE_2(p, 0'u32); WRITE_2(p, 0'u32) # pre_defined, reserved
      WRITE_4(p, 0'u32); WRITE_4(p, 0'u32); WRITE_4(p, 0'u32) # pre_defined
      WRITE_2(p, uint32(tr.info.width))
      WRITE_2(p, uint32(tr.info.height))
      WRITE_4(p, 0x00480000'u32) # horiz resolution
      WRITE_4(p, 0x00480000'u32) # vert resolution
      WRITE_4(p, 0'u32) # reserved
      WRITE_2(p, 1'u32) # frame_count
      for i in 0 ..< 32: WRITE_1(p, 0'u32) # compressorname
      WRITE_2(p, 24'u32)     # depth
      WRITE_2(p, 0xFFFF'u32) # pre_defined = -1

      if MP4_OBJECT_TYPE_AVC == tr.info.object_type_indication:
        ATOM(p, stack, BOX_avcC)
        WRITE_1(p, 1'u32) # configurationVersion
        WRITE_1(p, uint32(tr.vsps.data[2 + 1]))
        WRITE_1(p, uint32(tr.vsps.data[2 + 2]))
        WRITE_1(p, uint32(tr.vsps.data[2 + 3]))
        WRITE_1(p, 255'u32) # NALU_len
        WRITE_1(p, uint32(0xE0 or numSPS))
        for i in 0 ..< tr.vsps.bytes:
          WRITE_1(p, uint32(tr.vsps.data[i]))
        WRITE_1(p, uint32(numPPS))
        for i in 0 ..< tr.vpps.bytes:
          WRITE_1(p, uint32(tr.vpps.data[i]))
      else:
        let numVPS = itemsCount(addr tr.vvps)
        ATOM(p, stack, BOX_hvcC)
        WRITE_1(p, 1'u32); WRITE_1(p, 1'u32)
        WRITE_4(p, 0x60000000'u32); WRITE_2(p, 0'u32)
        WRITE_4(p, 0'u32); WRITE_1(p, 0'u32); WRITE_2(p, 0xF000'u32)
        WRITE_1(p, 0xFC'u32); WRITE_1(p, 0xFC'u32)
        WRITE_1(p, 0xF8'u32); WRITE_1(p, 0xF8'u32)
        WRITE_2(p, 0'u32); WRITE_1(p, 3'u32)
        WRITE_1(p, 3'u32) # Num Of Arrays
        WRITE_1(p, uint32((1 shl 7) or (HEVC_NAL_VPS and 0x3F)))
        WRITE_2(p, uint32(numVPS))
        for i in 0 ..< tr.vvps.bytes: WRITE_1(p, uint32(tr.vvps.data[i]))
        WRITE_1(p, uint32((1 shl 7) or (HEVC_NAL_SPS and 0x3F)))
        WRITE_2(p, uint32(numSPS))
        for i in 0 ..< tr.vsps.bytes: WRITE_1(p, uint32(tr.vsps.data[i]))
        WRITE_1(p, uint32((1 shl 7) or (HEVC_NAL_PPS and 0x3F)))
        WRITE_2(p, uint32(numPPS))
        for i in 0 ..< tr.vpps.bytes: WRITE_1(p, uint32(tr.vpps.data[i]))
      END_ATOM(p, stack) # avcC/hvcC
      END_ATOM(p, stack) # avc1/hvc1
    END_ATOM(p, stack) # stsd

    # stts — Time to Sample
    ATOM_FULL(p, stack, BOX_stts, 0'u32)
    block:
      let pentryCount = p
      var cnt = 1
      var entryCount = 0
      WRITE_4(p, 0'u32) # placeholder
      for i in 0 ..< samplesCount:
        if i == (samplesCount - 1) or sample[i].duration != sample[i + 1].duration:
          WRITE_4(p, uint32(cnt))
          WRITE_4(p, sample[i].duration)
          cnt = 0
          entryCount += 1
        cnt += 1
      WR4(pentryCount, entryCount)
    END_ATOM(p, stack)

    # stsc — Sample To Chunk
    ATOM_FULL(p, stack, BOX_stsc, 0'u32)
    if mux.enable_fragmentation != 0:
      WRITE_4(p, 0'u32)
    else:
      WRITE_4(p, 1'u32); WRITE_4(p, 1'u32); WRITE_4(p, 1'u32); WRITE_4(p, 1'u32)
    END_ATOM(p, stack)

    # stsz — Sample Size
    ATOM_FULL(p, stack, BOX_stsz, 0'u32)
    WRITE_4(p, 0'u32) # sample_size
    WRITE_4(p, uint32(samplesCount))
    for i in 0 ..< samplesCount:
      WRITE_4(p, uint32(sample[i].size))
    END_ATOM(p, stack)

    # stco/co64 — Chunk Offset
    var is64bit = false
    if samplesCount > 0 and sample[samplesCount - 1].offset > 0xFFFFFFFF'u64:
      is64bit = true
    if not is64bit:
      ATOM_FULL(p, stack, BOX_stco, 0'u32)
      WRITE_4(p, uint32(samplesCount))
      for i in 0 ..< samplesCount:
        WRITE_4(p, uint32(sample[i].offset))
    else:
      ATOM_FULL(p, stack, BOX_co64, 0'u32)
      WRITE_4(p, uint32(samplesCount))
      for i in 0 ..< samplesCount:
        WRITE_4(p, uint32((sample[i].offset shr 32) and 0xFFFFFFFF'u64))
        WRITE_4(p, uint32(sample[i].offset and 0xFFFFFFFF'u64))
    END_ATOM(p, stack)

    # stss — Sync Sample
    block:
      var raCount = 0
      for i in 0 ..< samplesCount:
        if sample[i].flag_random_access != 0: raCount += 1
      if raCount != samplesCount:
        ATOM_FULL(p, stack, BOX_stss, 0'u32)
        WRITE_4(p, uint32(raCount))
        for i in 0 ..< samplesCount:
          if sample[i].flag_random_access != 0:
            WRITE_4(p, uint32(i + 1))
        END_ATOM(p, stack)

    END_ATOM(p, stack) # stbl
    END_ATOM(p, stack) # minf
    END_ATOM(p, stack) # mdia
    END_ATOM(p, stack) # trak
  # end tracks loop

  if mux.text_comment != nil:
    let comment = $mux.text_comment
    ATOM(p, stack, BOX_udta)
    ATOM_FULL(p, stack, BOX_meta, 0'u32)
    ATOM_FULL(p, stack, BOX_hdlr, 0'u32)
    WRITE_4(p, 0'u32)
    WRITE_4(p, MP4E_HANDLER_TYPE_MDIR)
    WRITE_4(p, 0'u32); WRITE_4(p, 0'u32); WRITE_4(p, 0'u32)
    WRITE_4(p, 0'u32)
    END_ATOM(p, stack)
    ATOM(p, stack, BOX_ilst)
    ATOM(p, stack, BOX_ccmt)
    ATOM(p, stack, BOX_data)
    WRITE_4(p, 1'u32); WRITE_4(p, 0'u32)
    for i in 0 ..< comment.len + 1:
      if i < comment.len:
        WRITE_1(p, uint32(comment[i]))
      else:
        WRITE_1(p, 0'u32)
    END_ATOM(p, stack)
    END_ATOM(p, stack)
    END_ATOM(p, stack)
    END_ATOM(p, stack)
    END_ATOM(p, stack)

  END_ATOM(p, stack) # moov

  let err = mux.write_callback(mux.write_pos, base, csize_t(ptrDiff(p, base)), mux.token)
  mux.write_pos += ptrDiff(p, base)
  c_free(base)
  return err

proc MP4E_close*(mux: ptr MP4E_mux_t): int =
  var err = MP4E_STATUS_OK
  if mux == nil: return MP4E_STATUS_BAD_ARGUMENTS
  if mux.enable_fragmentation == 0:
    err = mp4eFlushIndex(mux)
  if mux.text_comment != nil:
    c_free(mux.text_comment)
  let ntracks = mux.tracks.bytes div sizeof(TrackT)
  for ntr in 0 ..< ntracks:
    let tr = cast[ptr TrackT](cast[uint](mux.tracks.data) + uint(ntr * sizeof(TrackT)))
    vectorReset(addr tr.vsps)
    vectorReset(addr tr.vpps)
    vectorReset(addr tr.smpl)
    vectorReset(addr tr.pending_sample)
  vectorReset(addr mux.tracks)
  c_free(mux)
  return err

# =========================================================================
# Bit reader / writer for SPS ID transcoding
# =========================================================================

proc loadShort(x: uint16): uint16 {.inline.} =
  (x shl 8) or (x shr 8)

proc showBits(bs: ptr BitReaderT, n: int): uint32 =
  bs.cache shr (32 - n)

proc flushBits(bs: ptr BitReaderT, n: int) =
  bs.cache = bs.cache shl n
  bs.cache_free_bits += n
  if bs.cache_free_bits >= 0:
    bs.cache = bs.cache or (uint32(loadShort(bs.buf[])) shl bs.cache_free_bits)
    bs.buf = cast[ptr uint16](cast[uint](bs.buf) + 2)
    bs.cache_free_bits -= 16

proc getBits(bs: ptr BitReaderT, n: int): uint32 =
  result = showBits(bs, n)
  flushBits(bs, n)

proc setPosBits(bs: ptr BitReaderT, posBits: uint32) =
  bs.buf = cast[ptr uint16](cast[uint](bs.origin) + uint(posBits div 16) * 2)
  bs.cache = 0
  bs.cache_free_bits = 16
  flushBits(bs, 0)
  flushBits(bs, int(posBits and 15))

proc getPosBits(bs: ptr BitReaderT): uint32 =
  uint32(cast[uint](bs.buf) - cast[uint](bs.origin)) div 2 * 16 - uint32(16 - bs.cache_free_bits)

proc remainingBits(bs: ptr BitReaderT): int =
  int(bs.origin_bytes) * 8 - int(getPosBits(bs))

proc initBits(bs: ptr BitReaderT, data: pointer, dataBytes: int) =
  bs.origin = cast[ptr uint16](data)
  bs.origin_bytes = uint32(dataBytes)
  setPosBits(bs, 0)

proc ueBits(bs: ptr BitReaderT): int =
  var clz = 0
  while getBits(bs, 1) == 0: clz += 1
  (1 shl clz) - 1 + (if clz > 0: int(getBits(bs, clz)) else: 0)

# Output bitstream
proc swap32(x: uint32): uint32 {.inline.} =
  ((x shr 24) and 0xFF) or ((x shr 8) and 0xFF00) or
  ((x shl 8) and 0xFF0000) or ((x and 0xFF) shl 24)

proc bsPutBits(bs: ptr BsT, n: int, val: uint32) =
  bs.shift -= n
  if bs.shift < 0:
    bs.cache = bs.cache or (val shr (-bs.shift))
    bs.buf[] = swap32(bs.cache)
    bs.buf = cast[ptr uint32](cast[uint](bs.buf) + 4)
    bs.shift = 32 + bs.shift
    bs.cache = 0
  bs.cache = bs.cache or (val shl bs.shift)

proc bsFlush(bs: ptr BsT) =
  bs.buf[] = swap32(bs.cache)

proc bsGetPosBits(bs: ptr BsT): uint32 =
  uint32((cast[uint](bs.buf) - cast[uint](bs.origin)) div 4 * 32) + uint32(32 - bs.shift)

proc bsByteAlign(bs: ptr BsT): uint32 =
  let pos = int(bsGetPosBits(bs))
  bsPutBits(bs, (-pos) and 7, 0)
  uint32(pos + ((-pos) and 7))

proc bsPutGolomb(bs: ptr BsT, val: uint32) =
  var size = 0
  var t = val + 1
  while t != 0:
    size += 1
    t = t shr 1
  bsPutBits(bs, 2 * size - 1, val + 1)

proc bsInitBits(bs: ptr BsT, data: pointer) =
  bs.origin = cast[ptr uint32](data)
  bs.buf = bs.origin
  bs.shift = 32
  bs.cache = 0

proc findMemCache(cache: var openArray[pointer], cacheBytes: var openArray[int],
                   cacheSize: int, mem: pointer, bytes: int): int =
  if bytes == 0: return -1
  for i in 0 ..< cacheSize:
    if cacheBytes[i] == bytes and cmpMem(cache[i], mem, bytes) == 0:
      return i
  for i in 0 ..< cacheSize:
    if cacheBytes[i] == 0:
      cache[i] = c_malloc(csize_t bytes)
      if cache[i] != nil:
        copyMem(cache[i], mem, bytes)
        cacheBytes[i] = bytes
      return i
  return -1

proc removeNalEscapes(dst: ptr UncheckedArray[byte], src: ptr UncheckedArray[byte],
                       h264DataBytes: int): int =
  var i = 0
  var zeroCnt = 0
  var j = 0
  while j < h264DataBytes:
    if zeroCnt == 2 and src[j] <= 3:
      if src[j] == 3:
        if j == h264DataBytes - 1:
          discard # cabac_zero_word
        elif src[j + 1] <= 3:
          j += 1
          zeroCnt = 0
        else:
          discard
      else:
        return 0
    dst[i] = src[j]
    i += 1
    if src[j] != 0: zeroCnt = 0 else: zeroCnt += 1
    j += 1
  return i

proc nalPutEsc(d: ptr UncheckedArray[byte], s: ptr UncheckedArray[byte], n: int): int =
  var j = 4
  var cntz = 0
  d[0] = 0; d[1] = 0; d[2] = 0; d[3] = 1
  for i in 0 ..< n:
    let b = s[i]
    if cntz == 2 and b <= 3:
      d[j] = 3; j += 1; cntz = 0
    if b != 0: cntz = 0 else: cntz += 1
    d[j] = b; j += 1
  return j

proc copyBits(bs: ptr BitReaderT, bd: ptr BsT) =
  var bitCount = remainingBits(bs)
  while bitCount > 7:
    let cb = min(bitCount - 7, 8)
    let bits = getBits(bs, cb)
    bsPutBits(bd, cb, bits)
    bitCount -= cb
  var bits = getBits(bs, bitCount)
  while bitCount > 0 and (bits and 1) == 0:
    bits = bits shr 1
    bitCount -= 1
  if bitCount > 0:
    bsPutBits(bd, bitCount, bits)

proc changeSpsId(bs: ptr BitReaderT, bd: ptr BsT, newId: int, oldId: var int): int =
  for i in 0 ..< 3:
    let bits = getBits(bs, 8)
    bsPutBits(bd, 8, bits)
  let spsId = ueBits(bs)
  oldId = spsId
  bsPutGolomb(bd, uint32(newId))
  copyBits(bs, bd)
  result = int(bsByteAlign(bd)) div 8
  bsFlush(bd)

proc patchPps(h: ptr H264SpsIdPatcher, bs: ptr BitReaderT, bd: ptr BsT,
              newPpsId: int, oldId: var int): int =
  let ppsId = ueBits(bs)
  let spsId = ueBits(bs)
  oldId = ppsId
  let mappedSps = h.map_sps[spsId]
  bsPutGolomb(bd, uint32(newPpsId))
  bsPutGolomb(bd, uint32(mappedSps))
  copyBits(bs, bd)
  result = int(bsByteAlign(bd)) div 8
  bsFlush(bd)

proc patchSliceHeader(h: ptr H264SpsIdPatcher, bs: ptr BitReaderT, bd: ptr BsT) =
  let firstMbInSlice = ueBits(bs)
  let sliceType = ueBits(bs)
  let ppsId = ueBits(bs)
  let mappedPps = h.map_pps[ppsId]
  bsPutGolomb(bd, uint32(firstMbInSlice))
  bsPutGolomb(bd, uint32(sliceType))
  bsPutGolomb(bd, uint32(mappedPps))
  copyBits(bs, bd)

proc transcodeNalu(h: ptr H264SpsIdPatcher, src: ptr UncheckedArray[byte],
                   naluBytes: int, dst: ptr UncheckedArray[byte]): int =
  var oldId: int
  var bst, bs: BitReaderT
  var bdt, bd: BsT
  let payloadType = int(src[0]) and 31
  dst[0] = src[0]
  bsInitBits(addr bd, ptrAdd(cast[ptr byte](dst), 1))
  initBits(addr bs, ptrAdd(cast[ptr byte](src), 1), naluBytes - 1)
  bsInitBits(addr bdt, ptrAdd(cast[ptr byte](dst), 1))
  initBits(addr bst, ptrAdd(cast[ptr byte](src), 1), naluBytes - 1)
  case payloadType
  of 7:
    let cb = changeSpsId(addr bst, addr bdt, 0, oldId)
    let id = findMemCache(h.sps_cache, h.sps_bytes, MINIMP4_MAX_SPS,
                           ptrAdd(cast[ptr byte](dst), 1), cb)
    if id == -1: return 0
    h.map_sps[oldId] = id
    discard changeSpsId(addr bs, addr bd, id, oldId)
  of 8:
    let cb = patchPps(h, addr bst, addr bdt, 0, oldId)
    let id = findMemCache(h.pps_cache, h.pps_bytes, MINIMP4_MAX_PPS,
                           ptrAdd(cast[ptr byte](dst), 1), cb)
    if id == -1: return 0
    h.map_pps[oldId] = id
    discard patchPps(h, addr bs, addr bd, id, oldId)
  of 1, 2, 5:
    patchSliceHeader(h, addr bs, addr bd)
  else:
    copyMem(dst, src, naluBytes)
    return naluBytes
  result = 1 + int(bsByteAlign(addr bd)) div 8
  bsFlush(addr bd)

# =========================================================================
# NAL unit finder
# =========================================================================

proc findStartCode(h264Data: ptr UncheckedArray[byte], h264DataBytes: int,
                    zcount: var int): ptr UncheckedArray[byte] =
  let eof = cast[uint](h264Data) + uint(h264DataBytes)
  var pos = cast[uint](h264Data)
  while pos < eof:
    var zeroCnt = 1
    # Find first zero
    var found = pos
    while found < eof and cast[ptr UncheckedArray[byte]](found)[0] != 0:
      found += 1
    if found >= eof:
      zcount = 0
      return cast[ptr UncheckedArray[byte]](eof)
    pos = found
    while pos + uint(zeroCnt) < eof and cast[ptr UncheckedArray[byte]](pos)[zeroCnt] == 0:
      zeroCnt += 1
    if zeroCnt >= 2 and pos + uint(zeroCnt) < eof and
       cast[ptr UncheckedArray[byte]](pos)[zeroCnt] == 1:
      zcount = zeroCnt + 1
      return cast[ptr UncheckedArray[byte]](pos + uint(zeroCnt) + 1)
    pos += uint(zeroCnt)
  zcount = 0
  return cast[ptr UncheckedArray[byte]](eof)

proc findNalUnit(h264Data: ptr UncheckedArray[byte], h264DataBytes: int,
                  pnalUnitBytes: var int): ptr UncheckedArray[byte] =
  let eof = cast[uint](h264Data) + uint(h264DataBytes)
  var zcount: int
  let start = findStartCode(h264Data, h264DataBytes, zcount)
  var stop = start
  if start != nil:
    let startAddr = cast[uint](start)
    stop = findStartCode(start, int(eof - startAddr), zcount)
    var stopAddr = cast[uint](stop)
    while stopAddr > startAddr and cast[ptr UncheckedArray[byte]](stopAddr - 1)[0] == 0:
      stopAddr -= 1
    stop = cast[ptr UncheckedArray[byte]](stopAddr)
  pnalUnitBytes = int(cast[uint](stop) - cast[uint](start)) - zcount
  return start

# =========================================================================
# mp4_h26x_write_init / nal / close
# =========================================================================

proc mp4_h26x_write_init*(h: ptr mp4_h26x_writer_t, mux: ptr MP4E_mux_t,
                           width: int, height: int, is_hevc: int): int =
  var tr: MP4E_track_t
  tr.track_media_kind = e_video
  tr.language[0] = byte('u'); tr.language[1] = byte('n')
  tr.language[2] = byte('d'); tr.language[3] = 0
  tr.object_type_indication = if is_hevc != 0: MP4_OBJECT_TYPE_HEVC else: MP4_OBJECT_TYPE_AVC
  tr.time_scale = 90000
  tr.default_duration = 0
  tr.width = int32(width)
  tr.height = int32(height)
  h.mux_track_id = MP4E_add_track(mux, addr tr)
  h.mux = mux
  h.is_hevc = is_hevc
  h.need_vps = is_hevc
  h.need_sps = 1
  h.need_pps = 1
  h.need_idr = 1
  zeroMem(addr h.sps_patcher, sizeof(H264SpsIdPatcher))
  return MP4E_STATUS_OK

proc mp4_h26x_write_close*(h: ptr mp4_h26x_writer_t) =
  let p = addr h.sps_patcher
  for i in 0 ..< MINIMP4_MAX_SPS:
    if p.sps_cache[i] != nil: c_free(p.sps_cache[i])
  for i in 0 ..< MINIMP4_MAX_PPS:
    if p.pps_cache[i] != nil: c_free(p.pps_cache[i])
  zeroMem(h, sizeof(mp4_h26x_writer_t))

proc mp4_h26x_write_nal*(h: ptr mp4_h26x_writer_t, nal: ptr UncheckedArray[byte],
                          length: int, timeStamp90kHz_next: uint32): int =
  let eof = cast[uint](nal) + uint(length)
  var err = MP4E_STATUS_OK
  var curNal = nal
  while true:
    var sizeofNal: int
    curNal = findNalUnit(curNal, int(eof - cast[uint](curNal)), sizeofNal)
    if sizeofNal == 0: break

    let payloadType = int(curNal[0]) and 31
    if payloadType == 9:
      return err # access unit delimiter

    # SPS ID transcoding path
    let nal1 = cast[ptr UncheckedArray[byte]](c_malloc(csize_t(sizeofNal * 17 div 16 + 32)))
    if nal1 == nil: return MP4E_STATUS_NO_MEMORY
    let nal2 = cast[ptr UncheckedArray[byte]](c_malloc(csize_t(sizeofNal * 17 div 16 + 32)))
    if nal2 == nil:
      c_free(nal1)
      return MP4E_STATUS_NO_MEMORY

    var escapedSize = removeNalEscapes(nal2, curNal, sizeofNal)
    if escapedSize == 0:
      c_free(nal1)
      c_free(nal2)
      return MP4E_STATUS_BAD_ARGUMENTS

    escapedSize = transcodeNalu(addr h.sps_patcher, nal2, escapedSize, nal1)
    escapedSize = nalPutEsc(nal2, nal1, escapedSize)

    case payloadType
    of 7:
      discard MP4E_set_sps(h.mux, h.mux_track_id,
                            ptrAdd(cast[ptr byte](nal2), 4), escapedSize - 4)
      h.need_sps = 0
    of 8:
      if h.need_sps != 0:
        c_free(nal1); c_free(nal2)
        return MP4E_STATUS_BAD_ARGUMENTS
      discard MP4E_set_pps(h.mux, h.mux_track_id,
                            ptrAdd(cast[ptr byte](nal2), 4), escapedSize - 4)
      h.need_pps = 0
    of 5:
      if h.need_sps != 0:
        c_free(nal1); c_free(nal2)
        return MP4E_STATUS_BAD_ARGUMENTS
      h.need_idr = 0
      # fall through to default
      if h.need_pps == 0 and h.need_idr == 0:
        var bs: BitReaderT
        initBits(addr bs, ptrAdd(cast[ptr byte](curNal), 1), sizeofNal - 4 - 1)
        let firstMbInSlice = ueBits(addr bs)
        var sampleKind = MP4E_SAMPLE_DEFAULT
        nal2[0] = byte((escapedSize - 4) shr 24)
        nal2[1] = byte((escapedSize - 4) shr 16)
        nal2[2] = byte((escapedSize - 4) shr 8)
        nal2[3] = byte(escapedSize - 4)
        if firstMbInSlice != 0:
          sampleKind = MP4E_SAMPLE_CONTINUATION
        elif payloadType == 5:
          sampleKind = MP4E_SAMPLE_RANDOM_ACCESS
        err = MP4E_put_sample(h.mux, h.mux_track_id, nal2, escapedSize,
                               int(timeStamp90kHz_next), sampleKind)
    else:
      if h.need_sps != 0:
        c_free(nal1); c_free(nal2)
        return MP4E_STATUS_BAD_ARGUMENTS
      if h.need_pps == 0 and h.need_idr == 0:
        var bs: BitReaderT
        initBits(addr bs, ptrAdd(cast[ptr byte](curNal), 1), sizeofNal - 4 - 1)
        let firstMbInSlice = ueBits(addr bs)
        var sampleKind = MP4E_SAMPLE_DEFAULT
        nal2[0] = byte((escapedSize - 4) shr 24)
        nal2[1] = byte((escapedSize - 4) shr 16)
        nal2[2] = byte((escapedSize - 4) shr 8)
        nal2[3] = byte(escapedSize - 4)
        if firstMbInSlice != 0:
          sampleKind = MP4E_SAMPLE_CONTINUATION
        elif payloadType == 5:
          sampleKind = MP4E_SAMPLE_RANDOM_ACCESS
        err = MP4E_put_sample(h.mux, h.mux_track_id, nal2, escapedSize,
                               int(timeStamp90kHz_next), sampleKind)

    c_free(nal1)
    c_free(nal2)
    if err != 0: break
    curNal = cast[ptr UncheckedArray[byte]](cast[uint](curNal) + 1)
  return err
