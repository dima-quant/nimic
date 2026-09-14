import ncode/pydefs
import system/ansi_c
const
  MP4E_STATUS_OK = 0
  MP4E_STATUS_BAD_ARGUMENTS = -1
  MP4E_STATUS_NO_MEMORY = -2
  MP4E_STATUS_FILE_WRITE_ERROR = -3
  MP4E_STATUS_ONLY_ONE_DSI_ALLOWED = -4
  MP4E_SAMPLE_DEFAULT = 0
  MP4E_SAMPLE_RANDOM_ACCESS = 1
  MP4E_SAMPLE_CONTINUATION = 2
  MP4_OBJECT_TYPE_AUDIO_ISO_IEC_14496_3 = 64'u32
  MP4_OBJECT_TYPE_AVC = 33'u32
  MP4_OBJECT_TYPE_HEVC = 35'u32
  local_MINIMP4_MAX_SPS = 32
  local_MINIMP4_MAX_PPS = 256
  local_HEVC_NAL_VPS = 32
  local_HEVC_NAL_SPS = 33
  local_HEVC_NAL_PPS = 34
  local_HEVC_NAL_BLA_W_LP = 16
  local_HEVC_NAL_CRA_NUT = 21
  local_MOOV_TIMESCALE = 1000'u32

proc local_fourCC(a: nint, b: nint, c: nint, d: nint): uint32 {.inline.} =
  return uint32(a) shl 24 or uint32(b) shl 16 or uint32(c) shl 8 or uint32(d)
let
  local_BOX_co64 = local_fourCC(99, 111, 54, 52)
  local_BOX_stco = local_fourCC(115, 116, 99, 111)
  local_BOX_ctts = local_fourCC(99, 116, 116, 115)
  local_BOX_dinf = local_fourCC(100, 105, 110, 102)
  local_BOX_dref = local_fourCC(100, 114, 101, 102)
  local_BOX_edts = local_fourCC(101, 100, 116, 115)
  local_BOX_elst = local_fourCC(101, 108, 115, 116)
  local_BOX_free = local_fourCC(102, 114, 101, 101)
  local_BOX_hdlr = local_fourCC(104, 100, 108, 114)
  local_BOX_mdia = local_fourCC(109, 100, 105, 97)
  local_BOX_mdat = local_fourCC(109, 100, 97, 116)
  local_BOX_mdhd = local_fourCC(109, 100, 104, 100)
  local_BOX_minf = local_fourCC(109, 105, 110, 102)
  local_BOX_moov = local_fourCC(109, 111, 111, 118)
  local_BOX_mvhd = local_fourCC(109, 118, 104, 100)
  local_BOX_stsd = local_fourCC(115, 116, 115, 100)
  local_BOX_stsz = local_fourCC(115, 116, 115, 122)
  local_BOX_stbl = local_fourCC(115, 116, 98, 108)
  local_BOX_stsc = local_fourCC(115, 116, 115, 99)
  local_BOX_smhd = local_fourCC(115, 109, 104, 100)
  local_BOX_stss = local_fourCC(115, 116, 115, 115)
  local_BOX_stts = local_fourCC(115, 116, 116, 115)
  local_BOX_trak = local_fourCC(116, 114, 97, 107)
  local_BOX_tkhd = local_fourCC(116, 107, 104, 100)
  local_BOX_udta = local_fourCC(117, 100, 116, 97)
  local_BOX_vmhd = local_fourCC(118, 109, 104, 100)
  local_BOX_url = local_fourCC(117, 114, 108, 32)
  local_BOX_ftyp = local_fourCC(102, 116, 121, 112)
  local_BOX_esds = local_fourCC(101, 115, 100, 115)
  local_BOX_mp4a = local_fourCC(109, 112, 52, 97)
  local_BOX_mp4s = local_fourCC(109, 112, 52, 115)
  local_BOX_avc1 = local_fourCC(97, 118, 99, 49)
  local_BOX_avcC = local_fourCC(97, 118, 99, 67)
  local_BOX_hvc1 = local_fourCC(104, 118, 99, 49)
  local_BOX_hvcC = local_fourCC(104, 118, 99, 67)
  local_BOX_nmhd = local_fourCC(110, 109, 104, 100)
  local_BOX_mvex = local_fourCC(109, 118, 101, 120)
  local_BOX_trex = local_fourCC(116, 114, 101, 120)
  local_BOX_moof = local_fourCC(109, 111, 111, 102)
  local_BOX_mfhd = local_fourCC(109, 102, 104, 100)
  local_BOX_traf = local_fourCC(116, 114, 97, 102)
  local_BOX_tfhd = local_fourCC(116, 102, 104, 100)
  local_BOX_trun = local_fourCC(116, 114, 117, 110)
  local_BOX_mehd = local_fourCC(109, 101, 104, 100)
  local_BOX_meta = local_fourCC(109, 101, 116, 97)
  local_BOX_ilst = local_fourCC(105, 108, 115, 116)
  local_BOX_ccmt = local_fourCC(169, 99, 109, 116)
  local_BOX_data = local_fourCC(100, 97, 116, 97)
const
  local_box_ftyp_data = array[24, uint8]([0'u8, 0'u8, 0'u8, 24'u8, 102'u8, 116'u8, 121'u8, 112'u8, 109'u8, 112'u8, 52'u8, 50'u8, 0'u8, 0'u8, 0'u8, 0'u8, 109'u8, 112'u8, 52'u8, 50'u8, 105'u8, 115'u8, 111'u8, 109'u8])
type
  TrackMediaKind* = enum 
    
    e_audio = 0, 
    e_video = 1, 
    e_private = 2

  MP4E_track_t* = object
    object_type_indication*: uint32
    language*: array[4, uint8]
    track_media_kind*: TrackMediaKind
    time_scale*: uint32
    default_duration*: uint32
    width*: int32
    height*: int32
    channelcount*: uint32

  local_MiniMp4Vector = object
    data*: ptr UncheckedArray[uint8]
    bytes*: nint
    capacity*: nint

  local_SampleT = object
    size*: uint64
    offset*: uint64
    duration*: uint32
    flag_random_access*: uint32

  local_TrackT = object
    info*: MP4E_track_t
    smpl*: local_MiniMp4Vector
    pending_sample*: local_MiniMp4Vector
    vsps*: local_MiniMp4Vector
    vpps*: local_MiniMp4Vector
    vvps*: local_MiniMp4Vector


type
  WriteCallback* = proc(offset: int64, buffer: pointer, size: csize_t, token: pointer): cint {.cdecl.}
type
  MP4E_mux_t* = object
    tracks*: local_MiniMp4Vector
    write_pos*: int64
    write_callback*: WriteCallback
    token*: pointer
    text_comment*: cstring
    sequential_mode_flag*: nint
    enable_fragmentation*: nint
    fragments_count*: nint

  local_BitReaderT = object
    cache*: uint32
    cache_free_bits*: nint
    buf*: ptr uint16
    origin*: ptr uint16
    origin_bytes*: uint32

  local_H264SpsIdPatcher = object
    sps_cache*: array[local_MINIMP4_MAX_SPS, pointer]
    pps_cache*: array[local_MINIMP4_MAX_PPS, pointer]
    sps_bytes*: array[local_MINIMP4_MAX_SPS, nint]
    pps_bytes*: array[local_MINIMP4_MAX_PPS, nint]
    map_sps*: array[local_MINIMP4_MAX_SPS, nint]
    map_pps*: array[local_MINIMP4_MAX_PPS, nint]

  mp4_h26x_writer_t* = object
    sps_patcher*: local_H264SpsIdPatcher
    mux*: ptr MP4E_mux_t
    mux_track_id*: nint
    is_hevc*: nint
    need_vps*: nint
    need_sps*: nint
    need_pps*: nint
    need_idr*: nint

  local_BsT = object
    shift*: nint
    cache*: uint32
    buf*: ptr uint32
    origin*: ptr uint32


proc local_vectorInit(h: ptr local_MiniMp4Vector, capacity: nint): nint =
  h[].bytes = 0
  h[].capacity = capacity
  if capacity > 0:
    h[].data = cast[ptr UncheckedArray[uint8]](c_malloc(csize_t(capacity)))
    if h[].data == nil:
      return 0
  else:
    h[].data = nil
  return 1

proc local_vectorReset(h: ptr local_MiniMp4Vector) =
  if h[].data != nil:
    c_free(h[].data)
  zero_mem(h, sizeof(local_MiniMp4Vector))

proc local_vectorGrow(h: ptr local_MiniMp4Vector, local_bytes: nint): nint =
  var
    local_newSize = h[].capacity * 2 + 1024
  if local_newSize < h[].capacity + local_bytes:
    local_newSize = h[].capacity + local_bytes + 1024
  let
    local_p = c_realloc(h[].data, csize_t(local_newSize))
  if local_p == nil:
    return 0
  h[].data = cast[ptr UncheckedArray[uint8]](local_p)
  h[].capacity = local_newSize
  return 1

proc local_vectorAllocTail(h: ptr local_MiniMp4Vector, local_bytes: nint): ptr uint8 =
  if h[].data == nil and local_vectorInit(h, 2 * local_bytes + 1024) == 0:
    return nil
  if h[].capacity - h[].bytes < local_bytes and local_vectorGrow(h, local_bytes) == 0:
    return nil
  result = cast[ptr uint8](cast[intp](h[].data) + h[].bytes)
  h[].bytes += local_bytes
  return result

proc local_vectorPut(h: ptr local_MiniMp4Vector, buf: pointer, local_bytes: nint): ptr uint8 =
  let
    local_tail = local_vectorAllocTail(h, local_bytes)
  if local_tail != nil:
    copy_mem(local_tail, buf, local_bytes)
  return local_tail

template local_WR1(p: var ptr uint8, x: uint32) {.dirty.} =
  p[] = uint8(x and 255)
  p = cast[ptr uint8](cast[intp](p) + 1)

template local_WRITE_1(p: var ptr uint8, x: uint32) {.dirty.} =
  local_WR1(p, x)

template local_WRITE_2(p: var ptr uint8, x: uint32) {.dirty.} =
  local_WR1(p, x shr 8)
  local_WR1(p, x)

template local_WRITE_3(p: var ptr uint8, x: uint32) {.dirty.} =
  local_WR1(p, x shr 16)
  local_WR1(p, x shr 8)
  local_WR1(p, x)

template local_WRITE_4(p: var ptr uint8, x: uint32) {.dirty.} =
  local_WR1(p, x shr 24)
  local_WR1(p, x shr 16)
  local_WR1(p, x shr 8)
  local_WR1(p, x)

proc local_WR4(p: ptr uint8, x: nint) =
  let
    local_xu = uint32(x)
    local_arr = cast[ptr UncheckedArray[uint8]](p)
  local_arr[0] = uint8(local_xu shr 24 and 255)
  local_arr[1] = uint8(local_xu shr 16 and 255)
  local_arr[2] = uint8(local_xu shr 8 and 255)
  local_arr[3] = uint8(local_xu and 255)

template local_ATOM(p: var ptr uint8, local_stack: var ptr ptr uint8, x: uint32) {.dirty.} =
  cast[ptr ptr uint8](local_stack)[] = p
  local_stack = cast[ptr ptr uint8](cast[intp](local_stack) + sizeof(pointer))
  p = cast[ptr uint8](cast[intp](p) + 4)
  local_WRITE_4(p, x)

template local_ATOM_FULL(p: var ptr uint8, local_stack: var ptr ptr uint8, x: uint32, flag: uint32) {.dirty.} =
  local_ATOM(p, local_stack, x)
  local_WRITE_4(p, flag)

template local_END_ATOM(p: var ptr uint8, local_stack: var ptr ptr uint8) {.dirty.} =
  local_stack = cast[ptr ptr uint8](cast[intp](local_stack) - sizeof(pointer))
  let
    local_atomStart = cast[ptr ptr uint8](local_stack)[]
  local_WR4(local_atomStart, cast[intp](p) - cast[intp](local_atomStart))

template local_ERR(expr: nint) {.dirty.} =
  block:
    let
      local_err = expr
    if local_err != 0:
      return local_err

proc local_ptrDiff(a: ptr uint8, b: ptr uint8): nint {.inline.} =
  return cast[intp](a) - cast[intp](b)

proc local_ptrAdd(p: ptr uint8, n: nint): ptr uint8 {.inline.} =
  return cast[ptr uint8](cast[intp](p) + n)

proc local_appendMem(v: ptr local_MiniMp4Vector, mem: pointer, local_bytes: nint): nint =
  var
    local_i = 0
  let
    local_p = v[].data
  while local_i + 2 < v[].bytes:
    let
      local_cb = nint(local_p[local_i]) * 256 + nint(local_p[local_i + 1])
    if local_cb == local_bytes and cmp_mem(local_ptrAdd(cast[ptr uint8](addr(local_p[local_i + 2])), 0), mem, local_cb) == 0:
      return 1
    local_i += 2 + local_cb
  var
    local_size: array[2, uint8]
  local_size[0] = uint8(local_bytes shr 8)
  local_size[1] = uint8(local_bytes and 255)
  result = nint(local_vectorPut(v, addr(local_size[0]), 2) != nil and local_vectorPut(v, mem, local_bytes) != nil)
  return result

proc local_itemsCount(v: ptr local_MiniMp4Vector): nint =
  var
    local_i = 0
    local_count = 0
  let
    local_p = v[].data
  while local_i + 2 < v[].bytes:
    let
      local_cb = nint(local_p[local_i]) * 256 + nint(local_p[local_i + 1])
    local_count += 1
    local_i += 2 + local_cb
  return local_count

proc local_getDuration(tr: ptr local_TrackT): uint32 =
  var
    local_sumDuration = uint32(0)
  let
    local_s = cast[ptr UncheckedArray[local_SampleT]](tr[].smpl.data)
    local_count = tr[].smpl.bytes div sizeof(local_SampleT)
  for local_i in range(local_count):
    local_sumDuration += local_s[local_i].duration
  return local_sumDuration

proc local_writePendingData(mux: ptr MP4E_mux_t, tr: ptr local_TrackT): nint =
  if tr[].pending_sample.bytes > 0 and tr[].smpl.bytes >= sizeof(local_SampleT):
    var
      local_base: array[8, uint8]
    var
      p = cast[ptr uint8](addr(local_base[0]))
    local_WRITE_4(p, uint32(tr[].pending_sample.bytes + 8))
    local_WRITE_4(p, local_BOX_mdat)
    local_ERR(mux[].write_callback(mux[].write_pos, addr(local_base[0]), csize_t(local_ptrDiff(p, cast[ptr uint8](addr(local_base[0])))), mux[].token))
    mux[].write_pos += local_ptrDiff(p, cast[ptr uint8](addr(local_base[0])))
    let
      local_smplDesc = cast[ptr local_SampleT](cast[intp](local_vectorAllocTail(addr(tr[].smpl), 0)) - sizeof(local_SampleT))
    local_smplDesc[].size = uint64(tr[].pending_sample.bytes)
    local_smplDesc[].offset = uint64(mux[].write_pos)
    local_ERR(mux[].write_callback(mux[].write_pos, tr[].pending_sample.data, csize_t(tr[].pending_sample.bytes), mux[].token))
    mux[].write_pos += tr[].pending_sample.bytes
    tr[].pending_sample.bytes = 0
  return MP4E_STATUS_OK

proc local_addSampleDescriptor(mux: ptr MP4E_mux_t, tr: ptr local_TrackT, local_dataBytes: nint, local_duration: nint, local_kind: nint): nint =
  var
    local_smp: local_SampleT
  local_smp.size = uint64(local_dataBytes)
  local_smp.offset = uint64(mux[].write_pos)
  local_smp.duration = if local_duration != 0: uint32(local_duration) else: tr[].info.default_duration
  local_smp.flag_random_access = uint32(nint(local_kind == MP4E_SAMPLE_RANDOM_ACCESS))
  return nint(local_vectorPut(addr(tr[].smpl), addr(local_smp), sizeof(local_SampleT)) != nil)

proc local_odSizeOfSize(local_size: nint): nint =
  result = 1
  var
    local_i = local_size
  while local_i > 127:
    result += 1
    local_i -= 127
  return result
const
  local_MP4E_HANDLER_TYPE_VIDE = 1986618469'u32
  local_MP4E_HANDLER_TYPE_SOUN = 1936684398'u32
  local_MP4E_HANDLER_TYPE_GESM = 1734701933'u32
  local_MP4E_HANDLER_TYPE_MDIR = 1835297138'u32
  local_FILE_HEADER_BYTES = 256
  local_TRACK_HEADER_BYTES = 512

proc local_mp4eFlushIndex(mux: ptr MP4E_mux_t): nint =
  var
    local_stackBase: array[20, ptr uint8]
  var
    local_stack = cast[ptr ptr uint8](addr(local_stackBase[0]))
  let
    local_ntracks = mux[].tracks.bytes div sizeof(local_TrackT)
  var
    local_indexBytes = local_FILE_HEADER_BYTES
  if mux[].text_comment != nil:
    local_indexBytes += 128 + len(string(mux[].text_comment))
  for local_ntr in range(local_ntracks):
    let
      local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + local_ntr * sizeof(local_TrackT))
    local_indexBytes += local_TRACK_HEADER_BYTES
    local_indexBytes += local_tr[].smpl.bytes * (sizeof(local_SampleT) + 4 + 4) div sizeof(local_SampleT)
    local_indexBytes += local_tr[].vsps.bytes
    local_indexBytes += local_tr[].vpps.bytes
    local_ERR(local_writePendingData(mux, local_tr))
  let
    local_base = cast[ptr uint8](c_malloc(csize_t(local_indexBytes)))
  if local_base == nil:
    return MP4E_STATUS_NO_MEMORY
  var
    p = local_base
  if mux[].sequential_mode_flag == 0:
    let
      local_size = mux[].write_pos - int64(sizeof(local_box_ftyp_data))
      local_sizeLimit = int64(4294967294'u64)
    if local_size > local_sizeLimit:
      local_WRITE_4(p, 1'u32)
      local_WRITE_4(p, local_BOX_mdat)
      local_WRITE_4(p, uint32(local_size shr 32 and 4294967295))
      local_WRITE_4(p, uint32(local_size and 4294967295))
    else:
      local_WRITE_4(p, 8'u32)
      local_WRITE_4(p, local_BOX_free)
      local_WRITE_4(p, uint32(local_size - 8))
      local_WRITE_4(p, local_BOX_mdat)
    local_ERR(mux[].write_callback(int64(sizeof(local_box_ftyp_data)), local_base, csize_t(local_ptrDiff(p, local_base)), mux[].token))
    p = local_base
  local_ATOM(p, local_stack, local_BOX_moov)
  local_ATOM_FULL(p, local_stack, local_BOX_mvhd, 0'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 0'u32)
  if local_ntracks > 0:
    let
      local_tr0 = cast[ptr local_TrackT](mux[].tracks.data)
    var
      local_dur = local_getDuration(local_tr0)
    local_dur = uint32(uint64(local_dur) * uint64(local_MOOV_TIMESCALE) div uint64(local_tr0[].info.time_scale))
    local_WRITE_4(p, local_MOOV_TIMESCALE)
    local_WRITE_4(p, local_dur)
  local_WRITE_4(p, 65536'u32)
  local_WRITE_2(p, 256'u32)
  local_WRITE_2(p, 0'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 65536'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 65536'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, 1073741824'u32)
  for local_i in range(6):
    local_WRITE_4(p, 0'u32)
  local_WRITE_4(p, uint32(local_ntracks + 1))
  local_END_ATOM(p, local_stack)
  for local_ntr in range(local_ntracks):
    let
      local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + local_ntr * sizeof(local_TrackT))
      local_duration = local_getDuration(local_tr)
    var
      local_samplesCount = local_tr[].smpl.bytes div sizeof(local_SampleT)
    let
      local_sample = cast[ptr UncheckedArray[local_SampleT]](local_tr[].smpl.data)
    var
      local_handlerType = uint32(0)
      local_handlerAscii = string("")
    if mux[].enable_fragmentation != 0:
      local_samplesCount = 0
    elif local_samplesCount <= 0:
      continue
    case local_tr[].info.track_media_kind:
      of TrackMediaKind.e_audio:
        local_handlerType = local_MP4E_HANDLER_TYPE_SOUN
        local_handlerAscii = string("SoundHandler")
      of TrackMediaKind.e_video:
        local_handlerType = local_MP4E_HANDLER_TYPE_VIDE
        local_handlerAscii = string("VideoHandler")
      of TrackMediaKind.e_private:
        local_handlerType = local_MP4E_HANDLER_TYPE_GESM
        local_handlerAscii = string("")
    local_ATOM(p, local_stack, local_BOX_trak)
    local_ATOM_FULL(p, local_stack, local_BOX_tkhd, 7'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, uint32(local_ntr + 1))
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, uint32(uint64(local_duration) * uint64(local_MOOV_TIMESCALE) div uint64(local_tr[].info.time_scale)))
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_2(p, 0'u32)
    local_WRITE_2(p, 0'u32)
    local_WRITE_2(p, 256'u32)
    local_WRITE_2(p, 0'u32)
    local_WRITE_4(p, 65536'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 65536'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 1073741824'u32)
    if local_tr[].info.track_media_kind == TrackMediaKind.e_audio or local_tr[].info.track_media_kind == TrackMediaKind.e_private:
      local_WRITE_4(p, 0'u32)
      local_WRITE_4(p, 0'u32)
    else:
      local_WRITE_4(p, uint32(local_tr[].info.width) * 65536'u32)
      local_WRITE_4(p, uint32(local_tr[].info.height) * 65536'u32)
    local_END_ATOM(p, local_stack)
    local_ATOM(p, local_stack, local_BOX_mdia)
    local_ATOM_FULL(p, local_stack, local_BOX_mdhd, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, local_tr[].info.time_scale)
    local_WRITE_4(p, local_duration)
    block:
      let
        local_langCode = uint32((nint(local_tr[].info.language[0]) and 31) shl 10 or (nint(local_tr[].info.language[1]) and 31) shl 5 or nint(local_tr[].info.language[2]) and 31)
      local_WRITE_2(p, local_langCode)
    local_WRITE_2(p, 0'u32)
    local_END_ATOM(p, local_stack)
    local_ATOM_FULL(p, local_stack, local_BOX_hdlr, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, local_handlerType)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    if len(local_handlerAscii) > 0:
      for local_i in range(len(local_handlerAscii)):
        local_WRITE_1(p, uint32(ord(local_handlerAscii[local_i])))
      local_WRITE_1(p, 0'u32)
    else:
      local_WRITE_4(p, 0'u32)
    local_END_ATOM(p, local_stack)
    local_ATOM(p, local_stack, local_BOX_minf)
    if local_tr[].info.track_media_kind == TrackMediaKind.e_audio:
      local_ATOM_FULL(p, local_stack, local_BOX_smhd, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_END_ATOM(p, local_stack)
    if local_tr[].info.track_media_kind == TrackMediaKind.e_video:
      local_ATOM_FULL(p, local_stack, local_BOX_vmhd, 1'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_END_ATOM(p, local_stack)
    local_ATOM(p, local_stack, local_BOX_dinf)
    local_ATOM_FULL(p, local_stack, local_BOX_dref, 0'u32)
    local_WRITE_4(p, 1'u32)
    local_ATOM_FULL(p, local_stack, local_BOX_url, 1'u32)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_ATOM(p, local_stack, local_BOX_stbl)
    local_ATOM_FULL(p, local_stack, local_BOX_stsd, 0'u32)
    local_WRITE_4(p, 1'u32)
    if local_tr[].info.track_media_kind == TrackMediaKind.e_audio or local_tr[].info.track_media_kind == TrackMediaKind.e_private:
      if local_tr[].info.track_media_kind == TrackMediaKind.e_audio:
        local_ATOM(p, local_stack, local_BOX_mp4a)
      else:
        local_ATOM(p, local_stack, local_BOX_mp4s)
      local_WRITE_4(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 1'u32)
      if local_tr[].info.track_media_kind == TrackMediaKind.e_audio:
        local_WRITE_4(p, 0'u32)
        local_WRITE_4(p, 0'u32)
        local_WRITE_2(p, uint32(local_tr[].info.channelcount))
        local_WRITE_2(p, 16'u32)
        local_WRITE_4(p, 0'u32)
        local_WRITE_4(p, local_tr[].info.time_scale shl 16)
      local_ATOM_FULL(p, local_stack, local_BOX_esds, 0'u32)
      if local_tr[].vsps.bytes > 0:
        let
          local_dsiBytes = local_tr[].vsps.bytes - 2
        var
          local_dsiBytesVar = local_dsiBytes
        let
          local_dsiSizeSize = local_odSizeOfSize(local_dsiBytes)
          local_dcdBytes = local_dsiBytes + local_dsiSizeSize + 1 + (1 + 1 + 3 + 4 + 4)
        var
          local_dcdBytesVar = local_dcdBytes
        let
          local_dcdSizeSize = local_odSizeOfSize(local_dcdBytes)
        var
          local_esdBytes = local_dcdBytes + local_dcdSizeSize + 1 + 3
        local_WRITE_1(p, 3'u32)
        while local_esdBytes > 127:
          local_esdBytes -= 127
          local_WRITE_1(p, 255'u32)
        local_WRITE_1(p, uint32(local_esdBytes))
        local_WRITE_2(p, 0'u32)
        local_WRITE_1(p, 0'u32)
        local_WRITE_1(p, 4'u32)
        while local_dcdBytesVar > 127:
          local_dcdBytesVar -= 127
          local_WRITE_1(p, 255'u32)
        local_WRITE_1(p, uint32(local_dcdBytesVar))
        if local_tr[].info.track_media_kind == TrackMediaKind.e_audio:
          local_WRITE_1(p, uint32(MP4_OBJECT_TYPE_AUDIO_ISO_IEC_14496_3))
          local_WRITE_1(p, 5'u32 shl 2)
        else:
          local_WRITE_1(p, 208'u32)
          local_WRITE_1(p, 32'u32 shl 2)
        local_WRITE_3(p, uint32(local_tr[].info.channelcount * 6144 div 8))
        local_WRITE_4(p, 0'u32)
        local_WRITE_4(p, 0'u32)
        local_WRITE_1(p, 5'u32)
        while local_dsiBytesVar > 127:
          local_dsiBytesVar -= 127
          local_WRITE_1(p, 255'u32)
        local_WRITE_1(p, uint32(local_dsiBytesVar))
        for local_i in range(local_dsiBytes):
          local_WRITE_1(p, uint32(local_tr[].vsps.data[2 + local_i]))
      local_END_ATOM(p, local_stack)
      local_END_ATOM(p, local_stack)
    if local_tr[].info.track_media_kind == TrackMediaKind.e_video and (MP4_OBJECT_TYPE_AVC == local_tr[].info.object_type_indication or MP4_OBJECT_TYPE_HEVC == local_tr[].info.object_type_indication):
      let
        local_numSPS = local_itemsCount(addr(local_tr[].vsps))
        local_numPPS = local_itemsCount(addr(local_tr[].vpps))
      if MP4_OBJECT_TYPE_AVC == local_tr[].info.object_type_indication:
        local_ATOM(p, local_stack, local_BOX_avc1)
      else:
        local_ATOM(p, local_stack, local_BOX_hvc1)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 1'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_2(p, 0'u32)
      local_WRITE_4(p, 0'u32)
      local_WRITE_4(p, 0'u32)
      local_WRITE_4(p, 0'u32)
      local_WRITE_2(p, uint32(local_tr[].info.width))
      local_WRITE_2(p, uint32(local_tr[].info.height))
      local_WRITE_4(p, 4718592'u32)
      local_WRITE_4(p, 4718592'u32)
      local_WRITE_4(p, 0'u32)
      local_WRITE_2(p, 1'u32)
      for local_i in range(32):
        local_WRITE_1(p, 0'u32)
      local_WRITE_2(p, 24'u32)
      local_WRITE_2(p, 65535'u32)
      if MP4_OBJECT_TYPE_AVC == local_tr[].info.object_type_indication:
        local_ATOM(p, local_stack, local_BOX_avcC)
        local_WRITE_1(p, 1'u32)
        local_WRITE_1(p, uint32(local_tr[].vsps.data[2 + 1]))
        local_WRITE_1(p, uint32(local_tr[].vsps.data[2 + 2]))
        local_WRITE_1(p, uint32(local_tr[].vsps.data[2 + 3]))
        local_WRITE_1(p, 255'u32)
        local_WRITE_1(p, uint32(224 or local_numSPS))
        for local_i in range(local_tr[].vsps.bytes):
          local_WRITE_1(p, uint32(local_tr[].vsps.data[local_i]))
        local_WRITE_1(p, uint32(local_numPPS))
        for local_i in range(local_tr[].vpps.bytes):
          local_WRITE_1(p, uint32(local_tr[].vpps.data[local_i]))
      else:
        let
          local_numVPS = local_itemsCount(addr(local_tr[].vvps))
        local_ATOM(p, local_stack, local_BOX_hvcC)
        local_WRITE_1(p, 1'u32)
        local_WRITE_1(p, 1'u32)
        local_WRITE_4(p, 1610612736'u32)
        local_WRITE_2(p, 0'u32)
        local_WRITE_4(p, 0'u32)
        local_WRITE_1(p, 0'u32)
        local_WRITE_2(p, 61440'u32)
        local_WRITE_1(p, 252'u32)
        local_WRITE_1(p, 252'u32)
        local_WRITE_1(p, 248'u32)
        local_WRITE_1(p, 248'u32)
        local_WRITE_2(p, 0'u32)
        local_WRITE_1(p, 3'u32)
        local_WRITE_1(p, 3'u32)
        local_WRITE_1(p, uint32(1 shl 7 or local_HEVC_NAL_VPS and 63))
        local_WRITE_2(p, uint32(local_numVPS))
        for local_i in range(local_tr[].vvps.bytes):
          local_WRITE_1(p, uint32(local_tr[].vvps.data[local_i]))
        local_WRITE_1(p, uint32(1 shl 7 or local_HEVC_NAL_SPS and 63))
        local_WRITE_2(p, uint32(local_numSPS))
        for local_i in range(local_tr[].vsps.bytes):
          local_WRITE_1(p, uint32(local_tr[].vsps.data[local_i]))
        local_WRITE_1(p, uint32(1 shl 7 or local_HEVC_NAL_PPS and 63))
        local_WRITE_2(p, uint32(local_numPPS))
        for local_i in range(local_tr[].vpps.bytes):
          local_WRITE_1(p, uint32(local_tr[].vpps.data[local_i]))
      local_END_ATOM(p, local_stack)
      local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_ATOM_FULL(p, local_stack, local_BOX_stts, 0'u32)
    block:
      let
        local_pentryCount = p
      var
        local_cnt = 1
        local_entryCount = 0
      local_WRITE_4(p, 0'u32)
      for local_i in range(local_samplesCount):
        if local_i == local_samplesCount - 1 or local_sample[local_i].duration != local_sample[local_i + 1].duration:
          local_WRITE_4(p, uint32(local_cnt))
          local_WRITE_4(p, local_sample[local_i].duration)
          local_cnt = 0
          local_entryCount += 1
        local_cnt += 1
      local_WR4(local_pentryCount, local_entryCount)
    local_END_ATOM(p, local_stack)
    local_ATOM_FULL(p, local_stack, local_BOX_stsc, 0'u32)
    if mux[].enable_fragmentation != 0:
      local_WRITE_4(p, 0'u32)
    else:
      local_WRITE_4(p, 1'u32)
      local_WRITE_4(p, 1'u32)
      local_WRITE_4(p, 1'u32)
      local_WRITE_4(p, 1'u32)
    local_END_ATOM(p, local_stack)
    local_ATOM_FULL(p, local_stack, local_BOX_stsz, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, uint32(local_samplesCount))
    for local_i in range(local_samplesCount):
      local_WRITE_4(p, uint32(local_sample[local_i].size))
    local_END_ATOM(p, local_stack)
    var
      local_is64bit = false
    if local_samplesCount > 0 and local_sample[local_samplesCount - 1].offset > 4294967295'u64:
      local_is64bit = true
    if not local_is64bit:
      local_ATOM_FULL(p, local_stack, local_BOX_stco, 0'u32)
      local_WRITE_4(p, uint32(local_samplesCount))
      for local_i in range(local_samplesCount):
        local_WRITE_4(p, uint32(local_sample[local_i].offset))
    else:
      local_ATOM_FULL(p, local_stack, local_BOX_co64, 0'u32)
      local_WRITE_4(p, uint32(local_samplesCount))
      for local_i in range(local_samplesCount):
        local_WRITE_4(p, uint32(local_sample[local_i].offset shr 32 and 4294967295'u64))
        local_WRITE_4(p, uint32(local_sample[local_i].offset and 4294967295'u64))
    local_END_ATOM(p, local_stack)
    block:
      var
        local_raCount = 0
      for local_i in range(local_samplesCount):
        if local_sample[local_i].flag_random_access != 0:
          local_raCount += 1
      if local_raCount != local_samplesCount:
        local_ATOM_FULL(p, local_stack, local_BOX_stss, 0'u32)
        local_WRITE_4(p, uint32(local_raCount))
        for local_i in range(local_samplesCount):
          if local_sample[local_i].flag_random_access != 0:
            local_WRITE_4(p, uint32(local_i + 1))
        local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
  if mux[].text_comment != nil:
    let
      local_comment = string(mux[].text_comment)
    local_ATOM(p, local_stack, local_BOX_udta)
    local_ATOM_FULL(p, local_stack, local_BOX_meta, 0'u32)
    local_ATOM_FULL(p, local_stack, local_BOX_hdlr, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, local_MP4E_HANDLER_TYPE_MDIR)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_WRITE_4(p, 0'u32)
    local_END_ATOM(p, local_stack)
    local_ATOM(p, local_stack, local_BOX_ilst)
    local_ATOM(p, local_stack, local_BOX_ccmt)
    local_ATOM(p, local_stack, local_BOX_data)
    local_WRITE_4(p, 1'u32)
    local_WRITE_4(p, 0'u32)
    for local_i in range(len(local_comment) + 1):
      if local_i < len(local_comment):
        local_WRITE_1(p, uint32(ord(local_comment[local_i])))
      else:
        local_WRITE_1(p, 0'u32)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
    local_END_ATOM(p, local_stack)
  local_END_ATOM(p, local_stack)
  let
    local_err2 = mux[].write_callback(mux[].write_pos, local_base, csize_t(local_ptrDiff(p, local_base)), mux[].token)
  mux[].write_pos += local_ptrDiff(p, local_base)
  c_free(local_base)
  return local_err2

proc MP4E_open*(sequential_mode_flag: nint, enable_fragmentation: nint, token: pointer, write_callback: WriteCallback): ptr MP4E_mux_t =
  if write_callback(0, unsafe_addr(local_box_ftyp_data[0]), csize_t(sizeof(local_box_ftyp_data)), token) != 0:
    return nil
  let
    mux = cast[ptr MP4E_mux_t](c_malloc(csize_t(sizeof(MP4E_mux_t))))
  if mux == nil:
    return nil
  mux[].sequential_mode_flag = if sequential_mode_flag != 0 or enable_fragmentation != 0: 1 else: 0
  mux[].enable_fragmentation = enable_fragmentation
  mux[].fragments_count = 0
  mux[].write_callback = write_callback
  mux[].token = token
  mux[].text_comment = nil
  mux[].write_pos = int64(sizeof(local_box_ftyp_data))
  if mux[].sequential_mode_flag == 0:
    if mux[].write_callback(mux[].write_pos, unsafe_addr(local_box_ftyp_data[0]), csize_t(8), mux[].token) != 0:
      c_free(mux)
      return nil
    mux[].write_pos += 16
  _ = local_vectorInit(addr(mux[].tracks), 2 * sizeof(local_TrackT))
  return mux

proc MP4E_add_track*(mux: ptr MP4E_mux_t, track_data: ptr MP4E_track_t): nint =
  if mux == nil or track_data == nil:
    return MP4E_STATUS_BAD_ARGUMENTS
  let
    local_ntr = mux[].tracks.bytes div sizeof(local_TrackT)
    local_trp = local_vectorAllocTail(addr(mux[].tracks), sizeof(local_TrackT))
  if local_trp == nil:
    return MP4E_STATUS_NO_MEMORY
  let
    local_tr = cast[ptr local_TrackT](local_trp)
  zero_mem(local_tr, sizeof(local_TrackT))
  copy_mem(addr(local_tr[].info), track_data, sizeof(MP4E_track_t))
  if local_vectorInit(addr(local_tr[].smpl), 256) == 0:
    return MP4E_STATUS_NO_MEMORY
  _ = local_vectorInit(addr(local_tr[].vsps), 0)
  _ = local_vectorInit(addr(local_tr[].vpps), 0)
  _ = local_vectorInit(addr(local_tr[].pending_sample), 0)
  return local_ntr

proc MP4E_set_dsi*(mux: ptr MP4E_mux_t, track_id: nint, dsi: pointer, local_bytes: nint): nint =
  let
    local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + track_id * sizeof(local_TrackT))
  if local_tr[].vsps.bytes != 0:
    return MP4E_STATUS_ONLY_ONE_DSI_ALLOWED
  return if local_appendMem(addr(local_tr[].vsps), dsi, local_bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_set_vps*(mux: ptr MP4E_mux_t, track_id: nint, vps: pointer, local_bytes: nint): nint =
  let
    local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + track_id * sizeof(local_TrackT))
  return if local_appendMem(addr(local_tr[].vvps), vps, local_bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_set_sps*(mux: ptr MP4E_mux_t, track_id: nint, sps: pointer, local_bytes: nint): nint =
  let
    local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + track_id * sizeof(local_TrackT))
  return if local_appendMem(addr(local_tr[].vsps), sps, local_bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_set_pps*(mux: ptr MP4E_mux_t, track_id: nint, pps: pointer, local_bytes: nint): nint =
  let
    local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + track_id * sizeof(local_TrackT))
  return if local_appendMem(addr(local_tr[].vpps), pps, local_bytes) != 0: MP4E_STATUS_OK else: MP4E_STATUS_NO_MEMORY

proc MP4E_put_sample*(mux: ptr MP4E_mux_t, track_num: nint, data: pointer, data_bytes: nint, local_duration: nint, local_kind: nint): nint =
  if mux == nil or data == nil:
    return MP4E_STATUS_BAD_ARGUMENTS
  let
    local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + track_num * sizeof(local_TrackT))
  if mux[].enable_fragmentation != 0:
    if mux[].fragments_count == 0:
      local_ERR(local_mp4eFlushIndex(mux))
    mux[].fragments_count += 1
    return MP4E_STATUS_OK
  if local_kind != MP4E_SAMPLE_CONTINUATION:
    if mux[].sequential_mode_flag != 0:
      local_ERR(local_writePendingData(mux, local_tr))
    if local_addSampleDescriptor(mux, local_tr, data_bytes, local_duration, local_kind) == 0:
      return MP4E_STATUS_NO_MEMORY
  elif mux[].sequential_mode_flag == 0:
    if local_tr[].smpl.bytes < sizeof(local_SampleT):
      return MP4E_STATUS_NO_MEMORY
    let
      local_smplDesc = cast[ptr local_SampleT](cast[intp](local_tr[].smpl.data) + local_tr[].smpl.bytes - sizeof(local_SampleT))
    local_smplDesc[].size += uint64(data_bytes)
  if mux[].sequential_mode_flag != 0:
    if local_vectorPut(addr(local_tr[].pending_sample), data, data_bytes) == nil:
      return MP4E_STATUS_NO_MEMORY
  else:
    local_ERR(mux[].write_callback(mux[].write_pos, data, csize_t(data_bytes), mux[].token))
    mux[].write_pos += data_bytes
  return MP4E_STATUS_OK

proc MP4E_close*(mux: ptr MP4E_mux_t): nint =
  var
    local_err = MP4E_STATUS_OK
  if mux == nil:
    return MP4E_STATUS_BAD_ARGUMENTS
  if mux[].enable_fragmentation == 0:
    local_err = local_mp4eFlushIndex(mux)
  if mux[].text_comment != nil:
    c_free(mux[].text_comment)
  let
    local_ntracks = mux[].tracks.bytes div sizeof(local_TrackT)
  for local_ntr in range(local_ntracks):
    let
      local_tr = cast[ptr local_TrackT](cast[intp](mux[].tracks.data) + local_ntr * sizeof(local_TrackT))
    local_vectorReset(addr(local_tr[].vsps))
    local_vectorReset(addr(local_tr[].vpps))
    local_vectorReset(addr(local_tr[].smpl))
    local_vectorReset(addr(local_tr[].pending_sample))
  local_vectorReset(addr(mux[].tracks))
  c_free(mux)
  return local_err

proc local_loadShort(x: uint16): uint16 {.inline.} =
  return x shl 8 or x shr 8

proc local_showBits(bs: ptr local_BitReaderT, n: nint): uint32 =
  return bs[].cache shr (32 - n)

proc local_flushBits(bs: ptr local_BitReaderT, n: nint) =
  bs[].cache = bs[].cache shl n
  bs[].cache_free_bits += n
  if bs[].cache_free_bits >= 0:
    bs[].cache = bs[].cache or uint32(local_loadShort(bs[].buf[])) shl bs[].cache_free_bits
    bs[].buf = cast[ptr uint16](cast[intp](bs[].buf) + 2)
    bs[].cache_free_bits -= 16

proc local_getBits(bs: ptr local_BitReaderT, n: nint): uint32 =
  result = local_showBits(bs, n)
  local_flushBits(bs, n)
  return result

proc local_setPosBits(bs: ptr local_BitReaderT, local_posBits: uint32) =
  bs[].buf = cast[ptr uint16](cast[intp](bs[].origin) + local_posBits div 16 * 2)
  bs[].cache = uint32(0)
  bs[].cache_free_bits = 16
  local_flushBits(bs, 0)
  local_flushBits(bs, nint(local_posBits and 15))

proc local_getPosBits(bs: ptr local_BitReaderT): uint32 =
  return uint32(cast[intp](bs[].buf) - cast[intp](bs[].origin)) div 2 * 16 - uint32(16 - bs[].cache_free_bits)

proc local_remainingBits(bs: ptr local_BitReaderT): nint =
  return nint(bs[].origin_bytes) * 8 - nint(local_getPosBits(bs))

proc local_initBits(bs: ptr local_BitReaderT, data: pointer, local_dataBytes: nint) =
  bs[].origin = cast[ptr uint16](data)
  bs[].origin_bytes = uint32(local_dataBytes)
  local_setPosBits(bs, uint32(0))

proc local_ueBits(bs: ptr local_BitReaderT): nint =
  var
    local_clz = 0
  while local_getBits(bs, 1) == 0:
    local_clz += 1
  return 1 shl local_clz - 1 + (if local_clz > 0: nint(local_getBits(bs, local_clz)) else: 0)

proc local_swap32(x: uint32): uint32 {.inline.} =
  return x shr 24 and 255 or x shr 8 and 65280 or x shl 8 and 16711680 or (x and 255) shl 24

proc local_bsPutBits(bs: ptr local_BsT, n: nint, val: uint32) =
  bs[].shift -= n
  if bs[].shift < 0:
    bs[].cache = bs[].cache or val shr -bs[].shift
    bs[].buf[] = local_swap32(bs[].cache)
    bs[].buf = cast[ptr uint32](cast[intp](bs[].buf) + 4)
    bs[].shift = 32 + bs[].shift
    bs[].cache = uint32(0)
  bs[].cache = bs[].cache or val shl bs[].shift

proc local_bsFlush(bs: ptr local_BsT) =
  bs[].buf[] = local_swap32(bs[].cache)

proc local_bsGetPosBits(bs: ptr local_BsT): uint32 =
  return uint32((cast[intp](bs[].buf) - cast[intp](bs[].origin)) div 4 * 32) + uint32(32 - bs[].shift)

proc local_bsByteAlign(bs: ptr local_BsT): uint32 =
  let
    local_pos = nint(local_bsGetPosBits(bs))
  local_bsPutBits(bs, -local_pos and 7, uint32(0))
  return uint32(local_pos + (-local_pos and 7))

proc local_bsPutGolomb(bs: ptr local_BsT, val: uint32) =
  var
    local_size = 0
    local_t = val + 1
  while local_t != 0:
    local_size += 1
    local_t = local_t shr 1
  local_bsPutBits(bs, 2 * local_size - 1, val + 1)

proc local_bsInitBits(bs: ptr local_BsT, data: pointer) =
  bs[].origin = cast[ptr uint32](data)
  bs[].buf = bs[].origin
  bs[].shift = 32
  bs[].cache = uint32(0)

proc local_findMemCache(cache: var openArray[pointer], local_cacheBytes: var openArray[nint], local_cacheSize: nint, mem: pointer, local_bytes: nint): nint =
  if local_bytes == 0:
    return -1
  for local_i in range(local_cacheSize):
    if local_cacheBytes[local_i] == local_bytes and cmp_mem(cache[local_i], mem, local_bytes) == 0:
      return local_i
  for local_i in range(local_cacheSize):
    if local_cacheBytes[local_i] == 0:
      cache[local_i] = c_malloc(csize_t(local_bytes))
      if cache[local_i] != nil:
        copy_mem(cache[local_i], mem, local_bytes)
        local_cacheBytes[local_i] = local_bytes
      return local_i
  return -1

proc local_removeNalEscapes(dst: ptr UncheckedArray[uint8], src: ptr UncheckedArray[uint8], local_h264DataBytes: nint): nint =
  var
    local_i = 0
    local_zeroCnt = 0
    local_j = 0
  while local_j < local_h264DataBytes:
    if local_zeroCnt == 2 and src[local_j] <= 3:
      if src[local_j] == 3:
        if local_j == local_h264DataBytes - 1:
          pass
        elif src[local_j + 1] <= 3:
          local_j += 1
          local_zeroCnt = 0
        else:
          pass
      else:
        return 0
    dst[local_i] = src[local_j]
    local_i += 1
    if src[local_j] != 0:
      local_zeroCnt = 0
    else:
      local_zeroCnt += 1
    local_j += 1
  return local_i

proc local_nalPutEsc(d: ptr UncheckedArray[uint8], s: ptr UncheckedArray[uint8], n: nint): nint =
  var
    local_j = 4
    local_cntz = 0
  d[0] = uint8(0)
  d[1] = uint8(0)
  d[2] = uint8(0)
  d[3] = uint8(1)
  for local_i in range(n):
    let
      local_b = s[local_i]
    if local_cntz == 2 and local_b <= 3:
      d[local_j] = uint8(3)
      local_j += 1
      local_cntz = 0
    if local_b != 0:
      local_cntz = 0
    else:
      local_cntz += 1
    d[local_j] = local_b
    local_j += 1
  return local_j

proc local_copyBits(bs: ptr local_BitReaderT, bd: ptr local_BsT) =
  var
    local_bitCount = local_remainingBits(bs)
  while local_bitCount > 7:
    let
      local_cb = min(local_bitCount - 7, 8)
      local_bits = local_getBits(bs, local_cb)
    local_bsPutBits(bd, local_cb, local_bits)
    local_bitCount -= local_cb
  var
    local_bits2 = local_getBits(bs, local_bitCount)
  while local_bitCount > 0 and local_bits2 and 1 == 0:
    local_bits2 = local_bits2 shr 1
    local_bitCount -= 1
  if local_bitCount > 0:
    local_bsPutBits(bd, local_bitCount, local_bits2)

proc local_changeSpsId(bs: ptr local_BitReaderT, bd: ptr local_BsT, local_newId: nint, local_oldId: var nint): nint =
  for local_i in range(3):
    let
      local_bits = local_getBits(bs, 8)
    local_bsPutBits(bd, 8, local_bits)
  let
    local_spsId = local_ueBits(bs)
  local_oldId = local_spsId
  local_bsPutGolomb(bd, uint32(local_newId))
  local_copyBits(bs, bd)
  result = nint(local_bsByteAlign(bd)) div 8
  local_bsFlush(bd)
  return result

proc local_patchPps(h: ptr local_H264SpsIdPatcher, bs: ptr local_BitReaderT, bd: ptr local_BsT, local_newPpsId: nint, local_oldId: var nint): nint =
  let
    local_ppsId = local_ueBits(bs)
    local_spsId = local_ueBits(bs)
  local_oldId = local_ppsId
  let
    local_mappedSps = h[].map_sps[local_spsId]
  local_bsPutGolomb(bd, uint32(local_newPpsId))
  local_bsPutGolomb(bd, uint32(local_mappedSps))
  local_copyBits(bs, bd)
  result = nint(local_bsByteAlign(bd)) div 8
  local_bsFlush(bd)
  return result

proc local_patchSliceHeader(h: ptr local_H264SpsIdPatcher, bs: ptr local_BitReaderT, bd: ptr local_BsT) =
  let
    local_firstMbInSlice = local_ueBits(bs)
    local_sliceType = local_ueBits(bs)
    local_ppsId = local_ueBits(bs)
    local_mappedPps = h[].map_pps[local_ppsId]
  local_bsPutGolomb(bd, uint32(local_firstMbInSlice))
  local_bsPutGolomb(bd, uint32(local_sliceType))
  local_bsPutGolomb(bd, uint32(local_mappedPps))
  local_copyBits(bs, bd)

proc local_transcodeNalu(h: ptr local_H264SpsIdPatcher, src: ptr UncheckedArray[uint8], local_naluBytes: nint, dst: ptr UncheckedArray[uint8]): nint =
  var
    local_oldId = 0
    local_bst: local_BitReaderT
    local_bs: local_BitReaderT
    local_bdt: local_BsT
    local_bd: local_BsT
  let
    local_payloadType = nint(src[0]) and 31
  dst[0] = src[0]
  local_bsInitBits(addr(local_bd), local_ptrAdd(cast[ptr uint8](dst), 1))
  local_initBits(addr(local_bs), local_ptrAdd(cast[ptr uint8](src), 1), local_naluBytes - 1)
  local_bsInitBits(addr(local_bdt), local_ptrAdd(cast[ptr uint8](dst), 1))
  local_initBits(addr(local_bst), local_ptrAdd(cast[ptr uint8](src), 1), local_naluBytes - 1)
  case local_payloadType:
    of 7:
      let
        local_cb = local_changeSpsId(addr(local_bst), addr(local_bdt), 0, local_oldId)
        local_id = local_findMemCache(h[].sps_cache, h[].sps_bytes, local_MINIMP4_MAX_SPS, local_ptrAdd(cast[ptr uint8](dst), 1), local_cb)
      if local_id == -1:
        return 0
      h[].map_sps[local_oldId] = local_id
      _ = local_changeSpsId(addr(local_bs), addr(local_bd), local_id, local_oldId)
    of 8:
      let
        local_cb = local_patchPps(h, addr(local_bst), addr(local_bdt), 0, local_oldId)
        local_id = local_findMemCache(h[].pps_cache, h[].pps_bytes, local_MINIMP4_MAX_PPS, local_ptrAdd(cast[ptr uint8](dst), 1), local_cb)
      if local_id == -1:
        return 0
      h[].map_pps[local_oldId] = local_id
      _ = local_patchPps(h, addr(local_bs), addr(local_bd), local_id, local_oldId)
    of 1 | 2 | 5:
      local_patchSliceHeader(h, addr(local_bs), addr(local_bd))
    of _:
      copy_mem(dst, src, local_naluBytes)
      return local_naluBytes
  result = 1 + nint(local_bsByteAlign(addr(local_bd))) div 8
  local_bsFlush(addr(local_bd))
  return result

proc local_findStartCode(local_h264Data: ptr UncheckedArray[uint8], local_h264DataBytes: nint, local_zcount: var nint): ptr UncheckedArray[uint8] =
  let
    local_eof = cast[intp](local_h264Data) + local_h264DataBytes
  var
    local_pos = cast[intp](local_h264Data)
  while local_pos < local_eof:
    var
      local_zeroCnt = 1
      local_found = local_pos
    while local_found < local_eof and cast[ptr UncheckedArray[uint8]](local_found)[0] != 0:
      local_found += 1
    if local_found >= local_eof:
      local_zcount = 0
      return cast[ptr UncheckedArray[uint8]](local_eof)
    local_pos = local_found
    while local_pos + local_zeroCnt < local_eof and cast[ptr UncheckedArray[uint8]](local_pos)[local_zeroCnt] == 0:
      local_zeroCnt += 1
    if local_zeroCnt >= 2 and local_pos + local_zeroCnt < local_eof and (cast[ptr UncheckedArray[uint8]](local_pos)[local_zeroCnt] == 1):
      local_zcount = local_zeroCnt + 1
      return cast[ptr UncheckedArray[uint8]](local_pos + local_zeroCnt + 1)
    local_pos += local_zeroCnt
  local_zcount = 0
  return cast[ptr UncheckedArray[uint8]](local_eof)

proc local_findNalUnit(local_h264Data: ptr UncheckedArray[uint8], local_h264DataBytes: nint, local_pnalUnitBytes: var nint): ptr UncheckedArray[uint8] =
  let
    local_eof = cast[intp](local_h264Data) + local_h264DataBytes
  var
    local_zcount = 0
  let
    local_start = local_findStartCode(local_h264Data, local_h264DataBytes, local_zcount)
  var
    local_stop = local_start
  if local_start != nil:
    let
      local_startAddr = cast[intp](local_start)
    local_stop = local_findStartCode(local_start, nint(local_eof - local_startAddr), local_zcount)
    var
      local_stopAddr = cast[intp](local_stop)
    while local_stopAddr > local_startAddr and cast[ptr UncheckedArray[uint8]](local_stopAddr - 1)[0] == 0:
      local_stopAddr -= 1
    local_stop = cast[ptr UncheckedArray[uint8]](local_stopAddr)
  local_pnalUnitBytes = nint(cast[intp](local_stop) - cast[intp](local_start)) - local_zcount
  return local_start

proc mp4_h26x_write_init*(h: ptr mp4_h26x_writer_t, mux: ptr MP4E_mux_t, width: nint, height: nint, is_hevc: nint): nint =
  var
    local_tr: MP4E_track_t
  local_tr.track_media_kind = TrackMediaKind.e_video
  local_tr.language[0] = uint8(117)
  local_tr.language[1] = uint8(110)
  local_tr.language[2] = uint8(100)
  local_tr.language[3] = uint8(0)
  local_tr.object_type_indication = if is_hevc != 0: MP4_OBJECT_TYPE_HEVC else: MP4_OBJECT_TYPE_AVC
  local_tr.time_scale = uint32(90000)
  local_tr.default_duration = uint32(0)
  local_tr.width = int32(width)
  local_tr.height = int32(height)
  h[].mux_track_id = MP4E_add_track(mux, addr(local_tr))
  h[].mux = mux
  h[].is_hevc = is_hevc
  h[].need_vps = is_hevc
  h[].need_sps = 1
  h[].need_pps = 1
  h[].need_idr = 1
  zero_mem(addr(h[].sps_patcher), sizeof(local_H264SpsIdPatcher))
  return MP4E_STATUS_OK

proc mp4_h26x_write_close*(h: ptr mp4_h26x_writer_t) =
  let
    local_p = addr(h[].sps_patcher)
  for local_i in range(local_MINIMP4_MAX_SPS):
    if local_p[].sps_cache[local_i] != nil:
      c_free(local_p[].sps_cache[local_i])
  for local_i in range(local_MINIMP4_MAX_PPS):
    if local_p[].pps_cache[local_i] != nil:
      c_free(local_p[].pps_cache[local_i])
  zero_mem(h, sizeof(mp4_h26x_writer_t))

proc mp4_h26x_write_nal*(h: ptr mp4_h26x_writer_t, nal: ptr UncheckedArray[uint8], length: nint, local_timeStamp90kHz_next: uint32): nint =
  let
    local_eof = cast[intp](nal) + length
  var
    local_err = MP4E_STATUS_OK
    local_curNal = nal
  while true:
    var
      local_sizeofNal = 0
    local_curNal = local_findNalUnit(local_curNal, nint(local_eof - cast[intp](local_curNal)), local_sizeofNal)
    if local_sizeofNal == 0:
      break
    let
      local_payloadType = nint(local_curNal[0]) and 31
    if local_payloadType == 9:
      return local_err
    let
      local_nal1 = cast[ptr UncheckedArray[uint8]](c_malloc(csize_t(local_sizeofNal * 17 div 16 + 32)))
    if local_nal1 == nil:
      return MP4E_STATUS_NO_MEMORY
    let
      local_nal2 = cast[ptr UncheckedArray[uint8]](c_malloc(csize_t(local_sizeofNal * 17 div 16 + 32)))
    if local_nal2 == nil:
      c_free(local_nal1)
      return MP4E_STATUS_NO_MEMORY
    var
      local_escapedSize = local_removeNalEscapes(local_nal2, local_curNal, local_sizeofNal)
    if local_escapedSize == 0:
      c_free(local_nal1)
      c_free(local_nal2)
      return MP4E_STATUS_BAD_ARGUMENTS
    local_escapedSize = local_transcodeNalu(addr(h[].sps_patcher), local_nal2, local_escapedSize, local_nal1)
    local_escapedSize = local_nalPutEsc(local_nal2, local_nal1, local_escapedSize)
    case local_payloadType:
      of 7:
        _ = MP4E_set_sps(h[].mux, h[].mux_track_id, local_ptrAdd(cast[ptr uint8](local_nal2), 4), local_escapedSize - 4)
        h[].need_sps = 0
      of 8:
        if h[].need_sps != 0:
          c_free(local_nal1)
          c_free(local_nal2)
          return MP4E_STATUS_BAD_ARGUMENTS
        _ = MP4E_set_pps(h[].mux, h[].mux_track_id, local_ptrAdd(cast[ptr uint8](local_nal2), 4), local_escapedSize - 4)
        h[].need_pps = 0
      of 5:
        if h[].need_sps != 0:
          c_free(local_nal1)
          c_free(local_nal2)
          return MP4E_STATUS_BAD_ARGUMENTS
        h[].need_idr = 0
        if h[].need_pps == 0 and h[].need_idr == 0:
          var
            local_bs: local_BitReaderT
          local_initBits(addr(local_bs), local_ptrAdd(cast[ptr uint8](local_curNal), 1), local_sizeofNal - 4 - 1)
          let
            local_firstMbInSlice = local_ueBits(addr(local_bs))
          var
            local_sampleKind = MP4E_SAMPLE_DEFAULT
          local_nal2[0] = uint8((local_escapedSize - 4) shr 24)
          local_nal2[1] = uint8((local_escapedSize - 4) shr 16)
          local_nal2[2] = uint8((local_escapedSize - 4) shr 8)
          local_nal2[3] = uint8(local_escapedSize - 4)
          if local_firstMbInSlice != 0:
            local_sampleKind = MP4E_SAMPLE_CONTINUATION
          elif local_payloadType == 5:
            local_sampleKind = MP4E_SAMPLE_RANDOM_ACCESS
          local_err = MP4E_put_sample(h[].mux, h[].mux_track_id, local_nal2, local_escapedSize, nint(local_timeStamp90kHz_next), local_sampleKind)
      of _:
        if h[].need_sps != 0:
          c_free(local_nal1)
          c_free(local_nal2)
          return MP4E_STATUS_BAD_ARGUMENTS
        if h[].need_pps == 0 and h[].need_idr == 0:
          var
            local_bs: local_BitReaderT
          local_initBits(addr(local_bs), local_ptrAdd(cast[ptr uint8](local_curNal), 1), local_sizeofNal - 4 - 1)
          let
            local_firstMbInSlice = local_ueBits(addr(local_bs))
          var
            local_sampleKind = MP4E_SAMPLE_DEFAULT
          local_nal2[0] = uint8((local_escapedSize - 4) shr 24)
          local_nal2[1] = uint8((local_escapedSize - 4) shr 16)
          local_nal2[2] = uint8((local_escapedSize - 4) shr 8)
          local_nal2[3] = uint8(local_escapedSize - 4)
          if local_firstMbInSlice != 0:
            local_sampleKind = MP4E_SAMPLE_CONTINUATION
          elif local_payloadType == 5:
            local_sampleKind = MP4E_SAMPLE_RANDOM_ACCESS
          local_err = MP4E_put_sample(h[].mux, h[].mux_track_id, local_nal2, local_escapedSize, nint(local_timeStamp90kHz_next), local_sampleKind)
    c_free(local_nal1)
    c_free(local_nal2)
    if local_err != 0:
      break
    local_curNal = cast[ptr UncheckedArray[uint8]](cast[intp](local_curNal) + 1)
  return local_err