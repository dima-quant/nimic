# Pure Nim translation of minimp4.h (muxer-only)
# Translated from https://github.com/lieff/minimp4
# Using c_malloc/cast/UncheckedArray/addr style per project convention
#
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from nimic.system.ansi_c import csize_t, cint, c_malloc, c_free, c_realloc, copy_mem, zero_mem, cmp_mem

# =========================================================================
# Constants
# =========================================================================

with const:
    MP4E_STATUS_OK = 0
    MP4E_STATUS_BAD_ARGUMENTS = -1
    MP4E_STATUS_NO_MEMORY = -2
    MP4E_STATUS_FILE_WRITE_ERROR = -3
    MP4E_STATUS_ONLY_ONE_DSI_ALLOWED = -4

    MP4E_SAMPLE_DEFAULT = 0
    MP4E_SAMPLE_RANDOM_ACCESS = 1
    MP4E_SAMPLE_CONTINUATION = 2

    MP4_OBJECT_TYPE_AUDIO_ISO_IEC_14496_3 = u32(0x40)
    MP4_OBJECT_TYPE_AVC = u32(0x21)
    MP4_OBJECT_TYPE_HEVC = u32(0x23)

    _MINIMP4_MAX_SPS = 32
    _MINIMP4_MAX_PPS = 256

    _HEVC_NAL_VPS = 32
    _HEVC_NAL_SPS = 33
    _HEVC_NAL_PPS = 34
    _HEVC_NAL_BLA_W_LP = 16
    _HEVC_NAL_CRA_NUT = 21

    _MOOV_TIMESCALE = u32(1000)

def _fourCC(a: char, b: char, c: char, d: char) -> uint32:
    """{.inline.}"""
    return (uint32(ord(a)) << 24) | (uint32(ord(b)) << 16) | (uint32(ord(c)) << 8) | uint32(ord(d))

# Box type constants
with let:
    _BOX_co64 = _fourCC(ch('c'),ch('o'),ch('6'),ch('4'))
    _BOX_stco = _fourCC(ch('s'),ch('t'),ch('c'),ch('o'))
    _BOX_ctts = _fourCC(ch('c'),ch('t'),ch('t'),ch('s'))
    _BOX_dinf = _fourCC(ch('d'),ch('i'),ch('n'),ch('f'))
    _BOX_dref = _fourCC(ch('d'),ch('r'),ch('e'),ch('f'))
    _BOX_edts = _fourCC(ch('e'),ch('d'),ch('t'),ch('s'))
    _BOX_elst = _fourCC(ch('e'),ch('l'),ch('s'),ch('t'))
    _BOX_free = _fourCC(ch('f'),ch('r'),ch('e'),ch('e'))
    _BOX_hdlr = _fourCC(ch('h'),ch('d'),ch('l'),ch('r'))
    _BOX_mdia = _fourCC(ch('m'),ch('d'),ch('i'),ch('a'))
    _BOX_mdat = _fourCC(ch('m'),ch('d'),ch('a'),ch('t'))
    _BOX_mdhd = _fourCC(ch('m'),ch('d'),ch('h'),ch('d'))
    _BOX_minf = _fourCC(ch('m'),ch('i'),ch('n'),ch('f'))
    _BOX_moov = _fourCC(ch('m'),ch('o'),ch('o'),ch('v'))
    _BOX_mvhd = _fourCC(ch('m'),ch('v'),ch('h'),ch('d'))
    _BOX_stsd = _fourCC(ch('s'),ch('t'),ch('s'),ch('d'))
    _BOX_stsz = _fourCC(ch('s'),ch('t'),ch('s'),ch('z'))
    _BOX_stbl = _fourCC(ch('s'),ch('t'),ch('b'),ch('l'))
    _BOX_stsc = _fourCC(ch('s'),ch('t'),ch('s'),ch('c'))
    _BOX_smhd = _fourCC(ch('s'),ch('m'),ch('h'),ch('d'))
    _BOX_stss = _fourCC(ch('s'),ch('t'),ch('s'),ch('s'))
    _BOX_stts = _fourCC(ch('s'),ch('t'),ch('t'),ch('s'))
    _BOX_trak = _fourCC(ch('t'),ch('r'),ch('a'),ch('k'))
    _BOX_tkhd = _fourCC(ch('t'),ch('k'),ch('h'),ch('d'))
    _BOX_udta = _fourCC(ch('u'),ch('d'),ch('t'),ch('a'))
    _BOX_vmhd = _fourCC(ch('v'),ch('m'),ch('h'),ch('d'))
    _BOX_url  = _fourCC(ch('u'),ch('r'),ch('l'),ch(' '))
    _BOX_ftyp = _fourCC(ch('f'),ch('t'),ch('y'),ch('p'))
    _BOX_esds = _fourCC(ch('e'),ch('s'),ch('d'),ch('s'))
    _BOX_mp4a = _fourCC(ch('m'),ch('p'),ch('4'),ch('a'))
    _BOX_mp4s = _fourCC(ch('m'),ch('p'),ch('4'),ch('s'))
    _BOX_avc1 = _fourCC(ch('a'),ch('v'),ch('c'),ch('1'))
    _BOX_avcC = _fourCC(ch('a'),ch('v'),ch('c'),ch('C'))
    _BOX_hvc1 = _fourCC(ch('h'),ch('v'),ch('c'),ch('1'))
    _BOX_hvcC = _fourCC(ch('h'),ch('v'),ch('c'),ch('C'))
    _BOX_nmhd = _fourCC(ch('n'),ch('m'),ch('h'),ch('d'))
    _BOX_mvex = _fourCC(ch('m'),ch('v'),ch('e'),ch('x'))
    _BOX_trex = _fourCC(ch('t'),ch('r'),ch('e'),ch('x'))
    _BOX_moof = _fourCC(ch('m'),ch('o'),ch('o'),ch('f'))
    _BOX_mfhd = _fourCC(ch('m'),ch('f'),ch('h'),ch('d'))
    _BOX_traf = _fourCC(ch('t'),ch('r'),ch('a'),ch('f'))
    _BOX_tfhd = _fourCC(ch('t'),ch('f'),ch('h'),ch('d'))
    _BOX_trun = _fourCC(ch('t'),ch('r'),ch('u'),ch('n'))
    _BOX_mehd = _fourCC(ch('m'),ch('e'),ch('h'),ch('d'))
    _BOX_meta = _fourCC(ch('m'),ch('e'),ch('t'),ch('a'))
    _BOX_ilst = _fourCC(ch('i'),ch('l'),ch('s'),ch('t'))
    _BOX_ccmt = _fourCC(ch('\xa9'),ch('c'),ch('m'),ch('t'))
    _BOX_data = _fourCC(ch('d'),ch('a'),ch('t'),ch('a'))


with const:
    _box_ftyp_data = array[24, uint8]([
  0, 0, 0, 0x18, ord(ch('f')), ord(ch('t')), ord(ch('y')), ord(ch('p')),
  ord(ch('m')), ord(ch('p')), ord(ch('4')), ord(ch('2')),
  0, 0, 0, 0,
  ord(ch('m')), ord(ch('p')), ord(ch('4')), ord(ch('2')),
  ord(ch('i')), ord(ch('s')), ord(ch('o')), ord(ch('m'))
])

# =========================================================================
# Types
# =========================================================================

class TrackMediaKind(NIntEnum):
    e_audio = 0
    e_video = 1
    e_private = 2

class MP4E_track_t(Object):
    object_type_indication: uint32
    language: array[4, uint8]
    track_media_kind: TrackMediaKind
    time_scale: uint32
    default_duration: uint32
    width: int32
    height: int32
    channelcount: uint32

class _MiniMp4Vector(Object):
    data: ptr[UncheckedArray[uint8]]
    bytes: nint
    capacity: nint

class _SampleT(Object):
    size: uint64
    offset: uint64
    duration: uint32
    flag_random_access: uint32

class _TrackT(Object):
    info: MP4E_track_t
    smpl: _MiniMp4Vector
    pending_sample: _MiniMp4Vector
    vsps: _MiniMp4Vector
    vpps: _MiniMp4Vector
    vvps: _MiniMp4Vector

@calltype
def WriteCallback(offset: int64, buffer: pointer, size: csize_t, token: pointer) -> cint:
    """{.cdecl.}"""
    pass

class MP4E_mux_t(Object):
    tracks: _MiniMp4Vector
    write_pos: int64
    write_callback: WriteCallback
    token: pointer
    text_comment: cstring
    sequential_mode_flag: nint
    enable_fragmentation: nint
    fragments_count: nint

class _BitReaderT(Object):
    cache: uint32
    cache_free_bits: nint
    buf: ptr[uint16]
    origin: ptr[uint16]
    origin_bytes: uint32

class _H264SpsIdPatcher(Object):
    sps_cache: array[_MINIMP4_MAX_SPS, pointer]
    pps_cache: array[_MINIMP4_MAX_PPS, pointer]
    sps_bytes: array[_MINIMP4_MAX_SPS, nint]
    pps_bytes: array[_MINIMP4_MAX_PPS, nint]
    map_sps: array[_MINIMP4_MAX_SPS, nint]
    map_pps: array[_MINIMP4_MAX_PPS, nint]

class mp4_h26x_writer_t(Object):
    sps_patcher: _H264SpsIdPatcher
    mux: ptr[MP4E_mux_t]
    mux_track_id: nint
    is_hevc: nint
    need_vps: nint
    need_sps: nint
    need_pps: nint
    need_idr: nint

class _BsT(Object):
    shift: nint
    cache: uint32
    buf: ptr[uint32]
    origin: ptr[uint32]

# =========================================================================
# Vector helpers
# =========================================================================

def _vectorInit(h: ptr[_MiniMp4Vector], capacity: nint) -> nint:
    h.bytes = 0
    h.capacity = capacity
    if capacity > 0:
        h.data = cast[ptr[UncheckedArray[uint8]]](c_malloc(csize_t(capacity)))
        if h.data == None: return 0
    else:
        h.data = None
    return 1

def _vectorReset(h: ptr[_MiniMp4Vector]):
    if h.data != None:
        c_free(h.data)
    zero_mem(h, sizeof(_MiniMp4Vector))

def _vectorGrow(h: ptr[_MiniMp4Vector], _bytes: nint) -> nint:
    with var:
        _newSize = h.capacity * 2 + 1024
    if _newSize < h.capacity + _bytes:
        _newSize = h.capacity + _bytes + 1024
    with let:
        _p = c_realloc(h.data, csize_t(_newSize))
    if _p == None: return 0
    h.data = cast[ptr[UncheckedArray[uint8]]](_p)
    h.capacity = _newSize
    return 1

def _vectorAllocTail(h: ptr[_MiniMp4Vector], _bytes: nint) -> ptr[uint8]:
    if h.data == None and _vectorInit(h, 2 * _bytes + 1024) == 0:
        return None
    if (h.capacity - h.bytes) < _bytes and _vectorGrow(h, _bytes) == 0:
        return None
    result = cast[ptr[uint8]](cast[intp](h.data) + h.bytes)
    h.bytes += _bytes
    return result

def _vectorPut(h: ptr[_MiniMp4Vector], buf: pointer, _bytes: nint) -> ptr[uint8]:
    with let:
        _tail = _vectorAllocTail(h, _bytes)
    if _tail != None:
        copy_mem(_tail, buf, _bytes)
    return _tail

# =========================================================================
# Write macros as templates
# =========================================================================

@template
def _WR1(p: mut@ptr[uint8], x: uint32):
    """{.dirty.}"""
    p.contents = uint8(x & 0xFF)
    p <<= cast[ptr[uint8]](cast[intp](p) + 1)

@template
def _WRITE_1(p: mut@ptr[uint8], x: uint32):
    """{.dirty.}"""
    _WR1(p, x)

@template
def _WRITE_2(p: mut@ptr[uint8], x: uint32):
    """{.dirty.}"""
    _WR1(p, (x >> 8))
    _WR1(p, x)

@template
def _WRITE_3(p: mut@ptr[uint8], x: uint32):
    """{.dirty.}"""
    _WR1(p, (x >> 16))
    _WR1(p, (x >> 8))
    _WR1(p, x)

@template
def _WRITE_4(p: mut@ptr[uint8], x: uint32):
    """{.dirty.}"""
    _WR1(p, (x >> 24))
    _WR1(p, (x >> 16))
    _WR1(p, (x >> 8))
    _WR1(p, x)

def _WR4(p: ptr[uint8], x: nint):
    with let:
        _xu = uint32(x)
        _arr = cast[ptr[UncheckedArray[uint8]]](p)
    _arr[0] = uint8((_xu >> 24) & 0xFF)
    _arr[1] = uint8((_xu >> 16) & 0xFF)
    _arr[2] = uint8((_xu >> 8) & 0xFF)
    _arr[3] = uint8(_xu & 0xFF)

@template
def _ATOM(p: mut@ptr[uint8], _stack: mut@ptr[ptr[uint8]], x: uint32):
    """{.dirty.}"""
    cast[ptr[ptr[uint8]]](_stack).contents = p
    _stack <<= cast[ptr[ptr[uint8]]](cast[intp](_stack) + sizeof(pointer))
    p <<= cast[ptr[uint8]](cast[intp](p) + 4)
    _WRITE_4(p, x)

@template
def _ATOM_FULL(p: mut@ptr[uint8], _stack: mut@ptr[ptr[uint8]], x: uint32, flag: uint32):
    """{.dirty.}"""
    _ATOM(p, _stack, x)
    _WRITE_4(p, flag)

@template
def _END_ATOM(p: mut@ptr[uint8], _stack: mut@ptr[ptr[uint8]]):
    """{.dirty.}"""
    _stack <<= cast[ptr[ptr[uint8]]](cast[intp](_stack) - sizeof(pointer))
    with block:
        with let:
            _atomStart = cast[ptr[ptr[uint8]]](_stack).contents
        _WR4(_atomStart, cast[intp](p) - cast[intp](_atomStart))

@template
def _ERR(expr: nint):
    """{.dirty.}"""
    with block:
        with let:
            _err = expr
        if _err != 0:
            return _err

def _ptrDiff(a: ptr[uint8], b: ptr[uint8]) -> nint:
    """{.inline.}"""
    return cast[intp](a) - cast[intp](b)

def _ptrAdd(p: ptr[uint8], n: nint) -> ptr[uint8]:
    """{.inline.}"""
    return cast[ptr[uint8]](cast[intp](p) + n)

# =========================================================================
# Helper functions
# =========================================================================

def _appendMem(v: ptr[_MiniMp4Vector], mem: pointer, _bytes: nint) -> nint:
    with var:
        _i = 0
    with let:
        _p = v.data
    while _i + 2 < v.bytes:
        with let:
            _cb = nint(_p[_i]) * 256 + nint(_p[_i + 1])
        if _cb == _bytes and cmp_mem(_ptrAdd(cast[ptr[uint8]](addr(_p[_i + 2])), 0), mem, _cb) == 0:
            return 1
        _i += 2 + _cb
    with var:
        _size = array[2, uint8]()
    _size[0] = uint8(_bytes >> 8)
    _size[1] = uint8(_bytes & 0xFF)
    result = nint(_vectorPut(v, addr(_size[0]), 2) != None and
                  _vectorPut(v, mem, _bytes) != None)
    return result

def _itemsCount(v: ptr[_MiniMp4Vector]) -> nint:
    with var:
        _i = 0
        _count = 0
    with let:
        _p = v.data
    while _i + 2 < v.bytes:
        with let:
            _cb = nint(_p[_i]) * 256 + nint(_p[_i + 1])
        _count += 1
        _i += 2 + _cb
    return _count

def _getDuration(tr: ptr[_TrackT]) -> uint32:
    with var:
        _sumDuration = uint32(0)
    with let:
        _s = cast[ptr[UncheckedArray[_SampleT]]](tr.smpl.data)
        _count = tr.smpl.bytes // sizeof(_SampleT)
    for _i in range(_count):
        _sumDuration += _s[_i].duration
    return _sumDuration

@template_expand
def _writePendingData(mux: ptr[MP4E_mux_t], tr: ptr[_TrackT]) -> nint:
    if tr.pending_sample.bytes > 0 and tr.smpl.bytes >= sizeof(_SampleT):
        with var:
            _base = array[8, uint8]()
        with var:
            p = cast[ptr[uint8]](addr(_base[0]))
        _WRITE_4(p, uint32(tr.pending_sample.bytes + 8))
        _WRITE_4(p, _BOX_mdat)
        _ERR(mux.write_callback(mux.write_pos, addr(_base[0]), csize_t(_ptrDiff(p, cast[ptr[uint8]](addr(_base[0])))), mux.token))
        mux.write_pos += _ptrDiff(p, cast[ptr[uint8]](addr(_base[0])))
        with let:
            _smplDesc = cast[ptr[_SampleT]](cast[intp](_vectorAllocTail(addr(tr.smpl), 0)) - sizeof(_SampleT))
        _smplDesc.size = uint64(tr.pending_sample.bytes)
        _smplDesc.offset = uint64(mux.write_pos)
        _ERR(mux.write_callback(mux.write_pos, tr.pending_sample.data, csize_t(tr.pending_sample.bytes), mux.token))
        mux.write_pos += tr.pending_sample.bytes
        tr.pending_sample.bytes = 0
    return MP4E_STATUS_OK

@template_expand
def _addSampleDescriptor(mux: ptr[MP4E_mux_t], tr: ptr[_TrackT],
                          _dataBytes: nint, _duration: nint, _kind: nint) -> nint:
    with var:
        _smp = _SampleT()
    _smp.size = uint64(_dataBytes)
    _smp.offset = uint64(mux.write_pos)
    _smp.duration = uint32(_duration) if _duration != 0 else tr.info.default_duration
    _smp.flag_random_access = uint32(nint(_kind == MP4E_SAMPLE_RANDOM_ACCESS))
    return nint(_vectorPut(addr(tr.smpl), addr(_smp), sizeof(_SampleT)) != None)

def _odSizeOfSize(_size: nint) -> nint:
    result = 1
    with var:
        _i = _size
    while _i > 0x7F:
        result += 1
        _i -= 0x7F
    return result


# =========================================================================
# mp4eFlushIndex — write moov box with all indexes (placed before callers)
# =========================================================================

with const:
    _MP4E_HANDLER_TYPE_VIDE = u32(0x76696465)
    _MP4E_HANDLER_TYPE_SOUN = u32(0x736F756E)
    _MP4E_HANDLER_TYPE_GESM = u32(0x6765736D)
    _MP4E_HANDLER_TYPE_MDIR = u32(0x6D646972)
    _FILE_HEADER_BYTES = 256
    _TRACK_HEADER_BYTES = 512

@template_expand
def _mp4eFlushIndex(mux: ptr[MP4E_mux_t]) -> nint:
    with var:
        _stackBase = array[20, ptr[uint8]]()
    with var:
        _stack = cast[ptr[ptr[uint8]]](addr(_stackBase[0]))
    with let:
        _ntracks = mux.tracks.bytes // sizeof(_TrackT)
    with var:
        _indexBytes = _FILE_HEADER_BYTES
    if mux.text_comment != None:
        _indexBytes += 128 + len(str(mux.text_comment))
    for _ntr in range(_ntracks):
        with let:
            _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + _ntr * sizeof(_TrackT))
        _indexBytes += _TRACK_HEADER_BYTES
        _indexBytes += _tr.smpl.bytes * (sizeof(_SampleT) + 4 + 4) // sizeof(_SampleT)
        _indexBytes += _tr.vsps.bytes
        _indexBytes += _tr.vpps.bytes
        _ERR(_writePendingData(mux, _tr))
    with let:
        _base = cast[ptr[uint8]](c_malloc(csize_t(_indexBytes)))
    if _base == None: return MP4E_STATUS_NO_MEMORY
    with var:
        p = _base.copy()

    if mux.sequential_mode_flag == 0:
        with let:
            _size = mux.write_pos - int64(sizeof(_box_ftyp_data))
            _sizeLimit = int64(u64(0xFFFFFFFE))
        if _size > _sizeLimit:
            _WRITE_4(p, u32(1))
            _WRITE_4(p, _BOX_mdat)
            _WRITE_4(p, uint32((_size >> 32) & 0xFFFFFFFF))
            _WRITE_4(p, uint32(_size & 0xFFFFFFFF))
        else:
            _WRITE_4(p, u32(8))
            _WRITE_4(p, _BOX_free)
            _WRITE_4(p, uint32(_size - 8))
            _WRITE_4(p, _BOX_mdat)
        _ERR(mux.write_callback(int64(sizeof(_box_ftyp_data)), _base, csize_t(_ptrDiff(p, _base)), mux.token))
        p = _base.copy()

    # moov
    _ATOM(p, _stack, _BOX_moov)
    _ATOM_FULL(p, _stack, _BOX_mvhd, u32(0))
    _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
    if _ntracks > 0:
        with let:
            _tr0 = cast[ptr[_TrackT]](mux.tracks.data)
        with var:
            _dur = _getDuration(_tr0)
        _dur = uint32(uint64(_dur) * uint64(_MOOV_TIMESCALE) // uint64(_tr0.info.time_scale))
        _WRITE_4(p, _MOOV_TIMESCALE)
        _WRITE_4(p, _dur)
    _WRITE_4(p, u32(0x00010000)); _WRITE_2(p, u32(0x0100))
    _WRITE_2(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
    _WRITE_4(p, u32(0x00010000)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
    _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0x00010000)); _WRITE_4(p, u32(0))
    _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0x40000000))
    for _i in range(6): _WRITE_4(p, u32(0))
    _WRITE_4(p, uint32(_ntracks + 1))
    _END_ATOM(p, _stack)

    for _ntr in range(_ntracks):
        with let:
            _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + _ntr * sizeof(_TrackT))
            _duration = _getDuration(_tr)
        with var:
            _samplesCount = _tr.smpl.bytes // sizeof(_SampleT)
        with let:
            _sample = cast[ptr[UncheckedArray[_SampleT]]](_tr.smpl.data)
        with var:
            _handlerType = uint32(0)
            _handlerAscii = string("")

        if mux.enable_fragmentation != 0:
            _samplesCount = 0
        elif _samplesCount <= 0:
            continue

        match _tr.info.track_media_kind:
            case TrackMediaKind.e_audio:
                _handlerType = _MP4E_HANDLER_TYPE_SOUN
                _handlerAscii = string("SoundHandler")
            case TrackMediaKind.e_video:
                _handlerType = _MP4E_HANDLER_TYPE_VIDE
                _handlerAscii = string("VideoHandler")
            case TrackMediaKind.e_private:
                _handlerType = _MP4E_HANDLER_TYPE_GESM
                _handlerAscii = string("")

        _ATOM(p, _stack, _BOX_trak)
        _ATOM_FULL(p, _stack, _BOX_tkhd, u32(7))
        _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
        _WRITE_4(p, uint32(_ntr + 1)); _WRITE_4(p, u32(0))
        _WRITE_4(p, uint32(uint64(_duration) * uint64(_MOOV_TIMESCALE) // uint64(_tr.info.time_scale)))
        _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
        _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0))
        _WRITE_2(p, u32(0x0100)); _WRITE_2(p, u32(0))
        _WRITE_4(p, u32(0x00010000)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
        _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0x00010000)); _WRITE_4(p, u32(0))
        _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0x40000000))
        if _tr.info.track_media_kind == TrackMediaKind.e_audio or _tr.info.track_media_kind == TrackMediaKind.e_private:
            _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
        else:
            _WRITE_4(p, uint32(_tr.info.width) * u32(0x10000))
            _WRITE_4(p, uint32(_tr.info.height) * u32(0x10000))
        _END_ATOM(p, _stack)

        _ATOM(p, _stack, _BOX_mdia)
        _ATOM_FULL(p, _stack, _BOX_mdhd, u32(0))
        _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
        _WRITE_4(p, _tr.info.time_scale)
        _WRITE_4(p, _duration)
        with block:
            with let:
                _langCode = uint32(((nint(_tr.info.language[0]) & 31) << 10) |
                                   ((nint(_tr.info.language[1]) & 31) << 5) |
                                   (nint(_tr.info.language[2]) & 31))
            _WRITE_2(p, _langCode)
        _WRITE_2(p, u32(0))
        _END_ATOM(p, _stack)

        _ATOM_FULL(p, _stack, _BOX_hdlr, u32(0))
        _WRITE_4(p, u32(0)); _WRITE_4(p, _handlerType)
        _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
        if len(_handlerAscii) > 0:
            for _i in range(len(_handlerAscii)):
                _WRITE_1(p, uint32(ord(_handlerAscii[_i])))
            _WRITE_1(p, u32(0))
        else:
            _WRITE_4(p, u32(0))
        _END_ATOM(p, _stack)

        _ATOM(p, _stack, _BOX_minf)
        if _tr.info.track_media_kind == TrackMediaKind.e_audio:
            _ATOM_FULL(p, _stack, _BOX_smhd, u32(0))
            _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0))
            _END_ATOM(p, _stack)
        if _tr.info.track_media_kind == TrackMediaKind.e_video:
            _ATOM_FULL(p, _stack, _BOX_vmhd, u32(1))
            _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0))
            _END_ATOM(p, _stack)
        _ATOM(p, _stack, _BOX_dinf)
        _ATOM_FULL(p, _stack, _BOX_dref, u32(0))
        _WRITE_4(p, u32(1))
        _ATOM_FULL(p, _stack, _BOX_url, u32(1))
        _END_ATOM(p, _stack); _END_ATOM(p, _stack); _END_ATOM(p, _stack)

        _ATOM(p, _stack, _BOX_stbl)
        _ATOM_FULL(p, _stack, _BOX_stsd, u32(0))
        _WRITE_4(p, u32(1))

        if _tr.info.track_media_kind == TrackMediaKind.e_audio or _tr.info.track_media_kind == TrackMediaKind.e_private:
            if _tr.info.track_media_kind == TrackMediaKind.e_audio:
                _ATOM(p, _stack, _BOX_mp4a)
            else:
                _ATOM(p, _stack, _BOX_mp4s)
            _WRITE_4(p, u32(0)); _WRITE_2(p, u32(0)); _WRITE_2(p, u32(1))
            if _tr.info.track_media_kind == TrackMediaKind.e_audio:
                _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
                _WRITE_2(p, uint32(_tr.info.channelcount)); _WRITE_2(p, u32(16))
                _WRITE_4(p, u32(0)); _WRITE_4(p, _tr.info.time_scale << 16)
            _ATOM_FULL(p, _stack, _BOX_esds, u32(0))
            if _tr.vsps.bytes > 0:
                with let:
                    _dsiBytes = _tr.vsps.bytes - 2
                with var:
                    _dsiBytesVar = _dsiBytes
                with let:
                    _dsiSizeSize = _odSizeOfSize(_dsiBytes)
                    _dcdBytes = _dsiBytes + _dsiSizeSize + 1 + (1 + 1 + 3 + 4 + 4)
                with var:
                    _dcdBytesVar = _dcdBytes
                with let:
                    _dcdSizeSize = _odSizeOfSize(_dcdBytes)
                with var:
                    _esdBytes = _dcdBytes + _dcdSizeSize + 1 + 3
                _WRITE_1(p, u32(3))
                while _esdBytes > 0x7F:
                    _esdBytes -= 0x7F; _WRITE_1(p, u32(0x00FF))
                _WRITE_1(p, uint32(_esdBytes))
                _WRITE_2(p, u32(0)); _WRITE_1(p, u32(0)); _WRITE_1(p, u32(4))
                while _dcdBytesVar > 0x7F:
                    _dcdBytesVar -= 0x7F; _WRITE_1(p, u32(0x00FF))
                _WRITE_1(p, uint32(_dcdBytesVar))
                if _tr.info.track_media_kind == TrackMediaKind.e_audio:
                    _WRITE_1(p, uint32(MP4_OBJECT_TYPE_AUDIO_ISO_IEC_14496_3)); _WRITE_1(p, u32(5) << 2)
                else:
                    _WRITE_1(p, u32(208)); _WRITE_1(p, u32(32) << 2)
                _WRITE_3(p, uint32(_tr.info.channelcount * 6144 // 8))
                _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_1(p, u32(5))
                while _dsiBytesVar > 0x7F:
                    _dsiBytesVar -= 0x7F; _WRITE_1(p, u32(0x00FF))
                _WRITE_1(p, uint32(_dsiBytesVar))
                for _i in range(_dsiBytes):
                    _WRITE_1(p, uint32(_tr.vsps.data[2 + _i]))
            _END_ATOM(p, _stack); _END_ATOM(p, _stack)

        if _tr.info.track_media_kind == TrackMediaKind.e_video and (MP4_OBJECT_TYPE_AVC == _tr.info.object_type_indication or MP4_OBJECT_TYPE_HEVC == _tr.info.object_type_indication):
            with let:
                _numSPS = _itemsCount(addr(_tr.vsps))
                _numPPS = _itemsCount(addr(_tr.vpps))
            if MP4_OBJECT_TYPE_AVC == _tr.info.object_type_indication:
                _ATOM(p, _stack, _BOX_avc1)
            else:
                _ATOM(p, _stack, _BOX_hvc1)
            _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0)); _WRITE_2(p, u32(1))
            _WRITE_2(p, u32(0)); _WRITE_2(p, u32(0))
            _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
            _WRITE_2(p, uint32(_tr.info.width)); _WRITE_2(p, uint32(_tr.info.height))
            _WRITE_4(p, u32(0x00480000)); _WRITE_4(p, u32(0x00480000))
            _WRITE_4(p, u32(0)); _WRITE_2(p, u32(1))
            for _i in range(32): _WRITE_1(p, u32(0))
            _WRITE_2(p, u32(24)); _WRITE_2(p, u32(0xFFFF))
            if MP4_OBJECT_TYPE_AVC == _tr.info.object_type_indication:
                _ATOM(p, _stack, _BOX_avcC)
                _WRITE_1(p, u32(1))
                _WRITE_1(p, uint32(_tr.vsps.data[2+1])); _WRITE_1(p, uint32(_tr.vsps.data[2+2])); _WRITE_1(p, uint32(_tr.vsps.data[2+3]))
                _WRITE_1(p, u32(255)); _WRITE_1(p, uint32(0xE0 | _numSPS))
                for _i in range(_tr.vsps.bytes): _WRITE_1(p, uint32(_tr.vsps.data[_i]))
                _WRITE_1(p, uint32(_numPPS))
                for _i in range(_tr.vpps.bytes): _WRITE_1(p, uint32(_tr.vpps.data[_i]))
            else:
                with let:
                    _numVPS = _itemsCount(addr(_tr.vvps))
                _ATOM(p, _stack, _BOX_hvcC)
                _WRITE_1(p, u32(1)); _WRITE_1(p, u32(1))
                _WRITE_4(p, u32(0x60000000)); _WRITE_2(p, u32(0))
                _WRITE_4(p, u32(0)); _WRITE_1(p, u32(0)); _WRITE_2(p, u32(0xF000))
                _WRITE_1(p, u32(0xFC)); _WRITE_1(p, u32(0xFC)); _WRITE_1(p, u32(0xF8)); _WRITE_1(p, u32(0xF8))
                _WRITE_2(p, u32(0)); _WRITE_1(p, u32(3)); _WRITE_1(p, u32(3))
                _WRITE_1(p, uint32((1 << 7) | (_HEVC_NAL_VPS & 0x3F))); _WRITE_2(p, uint32(_numVPS))
                for _i in range(_tr.vvps.bytes): _WRITE_1(p, uint32(_tr.vvps.data[_i]))
                _WRITE_1(p, uint32((1 << 7) | (_HEVC_NAL_SPS & 0x3F))); _WRITE_2(p, uint32(_numSPS))
                for _i in range(_tr.vsps.bytes): _WRITE_1(p, uint32(_tr.vsps.data[_i]))
                _WRITE_1(p, uint32((1 << 7) | (_HEVC_NAL_PPS & 0x3F))); _WRITE_2(p, uint32(_numPPS))
                for _i in range(_tr.vpps.bytes): _WRITE_1(p, uint32(_tr.vpps.data[_i]))
            _END_ATOM(p, _stack); _END_ATOM(p, _stack)
        _END_ATOM(p, _stack)  # stsd

        _ATOM_FULL(p, _stack, _BOX_stts, u32(0))
        with block:
            with let:
                _pentryCount = cast[ptr[uint8]](p)
            with var:
                _cnt = 1
                _entryCount = 0
            _WRITE_4(p, u32(0))
            for _i in range(_samplesCount):
                if _i == (_samplesCount - 1) or _sample[_i].duration != _sample[_i + 1].duration:
                    _WRITE_4(p, uint32(_cnt)); _WRITE_4(p, _sample[_i].duration)
                    _cnt = 0; _entryCount += 1
                _cnt += 1
            _WR4(_pentryCount, _entryCount)
        _END_ATOM(p, _stack)

        _ATOM_FULL(p, _stack, _BOX_stsc, u32(0))
        if mux.enable_fragmentation != 0:
            _WRITE_4(p, u32(0))
        else:
            _WRITE_4(p, u32(1)); _WRITE_4(p, u32(1)); _WRITE_4(p, u32(1)); _WRITE_4(p, u32(1))
        _END_ATOM(p, _stack)

        _ATOM_FULL(p, _stack, _BOX_stsz, u32(0))
        _WRITE_4(p, u32(0)); _WRITE_4(p, uint32(_samplesCount))
        for _i in range(_samplesCount): _WRITE_4(p, uint32(_sample[_i].size))
        _END_ATOM(p, _stack)

        with var:
            _is64bit = False
        if _samplesCount > 0 and _sample[_samplesCount - 1].offset > u64(0xFFFFFFFF):
            _is64bit = True
        if not _is64bit:
            _ATOM_FULL(p, _stack, _BOX_stco, u32(0))
            _WRITE_4(p, uint32(_samplesCount))
            for _i in range(_samplesCount): _WRITE_4(p, uint32(_sample[_i].offset))
        else:
            _ATOM_FULL(p, _stack, _BOX_co64, u32(0))
            _WRITE_4(p, uint32(_samplesCount))
            for _i in range(_samplesCount):
                _WRITE_4(p, uint32((_sample[_i].offset >> 32) & u64(0xFFFFFFFF)))
                _WRITE_4(p, uint32(_sample[_i].offset & u64(0xFFFFFFFF)))
        _END_ATOM(p, _stack)

        with block:
            with var:
                _raCount = 0
            for _i in range(_samplesCount):
                if _sample[_i].flag_random_access != 0: _raCount += 1
            if _raCount != _samplesCount:
                _ATOM_FULL(p, _stack, _BOX_stss, u32(0))
                _WRITE_4(p, uint32(_raCount))
                for _i in range(_samplesCount):
                    if _sample[_i].flag_random_access != 0: _WRITE_4(p, uint32(_i + 1))
                _END_ATOM(p, _stack)

        _END_ATOM(p, _stack); _END_ATOM(p, _stack); _END_ATOM(p, _stack); _END_ATOM(p, _stack)

    if mux.text_comment != None:
        with let:
            _comment = str(mux.text_comment)
        _ATOM(p, _stack, _BOX_udta)
        _ATOM_FULL(p, _stack, _BOX_meta, u32(0))
        _ATOM_FULL(p, _stack, _BOX_hdlr, u32(0))
        _WRITE_4(p, u32(0)); _WRITE_4(p, _MP4E_HANDLER_TYPE_MDIR)
        _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0)); _WRITE_4(p, u32(0))
        _END_ATOM(p, _stack)
        _ATOM(p, _stack, _BOX_ilst); _ATOM(p, _stack, _BOX_ccmt); _ATOM(p, _stack, _BOX_data)
        _WRITE_4(p, u32(1)); _WRITE_4(p, u32(0))
        for _i in range(len(_comment) + 1):
            if _i < len(_comment): _WRITE_1(p, uint32(ord(_comment[_i])))
            else: _WRITE_1(p, u32(0))
        _END_ATOM(p, _stack); _END_ATOM(p, _stack); _END_ATOM(p, _stack); _END_ATOM(p, _stack); _END_ATOM(p, _stack)

    _END_ATOM(p, _stack)  # moov
    with let:
        _err2 = mux.write_callback(mux.write_pos, _base, csize_t(_ptrDiff(p, _base)), mux.token)
    mux.write_pos += _ptrDiff(p, _base)
    c_free(_base)
    return _err2

# =========================================================================
# MP4E API
# =========================================================================

#@template_expand
def MP4E_open(sequential_mode_flag: nint, enable_fragmentation: nint,
              token: pointer, write_callback: WriteCallback) -> ptr[MP4E_mux_t]:
    if write_callback(0, unsafe_addr(_box_ftyp_data[0]), csize_t(sizeof(_box_ftyp_data)), token) != 0:
        return None
    with let:
        mux = cast[ptr[MP4E_mux_t]](c_malloc(csize_t(sizeof(MP4E_mux_t))))
    if mux == None: return None
    mux.sequential_mode_flag = 1 if (sequential_mode_flag != 0 or enable_fragmentation != 0) else 0
    mux.enable_fragmentation = enable_fragmentation
    mux.fragments_count = 0
    mux.write_callback = write_callback
    mux.token = token
    mux.text_comment = None
    mux.write_pos = int64(sizeof(_box_ftyp_data))
    if mux.sequential_mode_flag == 0:
        if mux.write_callback(mux.write_pos, unsafe_addr(_box_ftyp_data[0]), csize_t(8), mux.token) != 0:
            c_free(mux)
            return None
        mux.write_pos += 16
    with let:
        _dummy = _vectorInit(addr(mux.tracks), 2 * sizeof(_TrackT))
    return mux

@template_expand
def MP4E_add_track(mux: ptr[MP4E_mux_t], track_data: ptr[MP4E_track_t]) -> nint:
    if mux == None or track_data == None:
        return MP4E_STATUS_BAD_ARGUMENTS
    with let:
        _ntr = mux.tracks.bytes // sizeof(_TrackT)
        _trp = _vectorAllocTail(addr(mux.tracks), sizeof(_TrackT))
    if _trp == None: return MP4E_STATUS_NO_MEMORY
    with let:
        _tr = cast[ptr[_TrackT]](_trp)
    zero_mem(_tr, sizeof(_TrackT))
    copy_mem(addr(_tr.info), track_data, sizeof(MP4E_track_t))
    if _vectorInit(addr(_tr.smpl), 256) == 0: return MP4E_STATUS_NO_MEMORY
    _ = _vectorInit(addr(_tr.vsps), 0)
    _ = _vectorInit(addr(_tr.vpps), 0)
    _ = _vectorInit(addr(_tr.pending_sample), 0)
    return _ntr

def MP4E_set_dsi(mux: ptr[MP4E_mux_t], track_id: nint, dsi: pointer, _bytes: nint) -> nint:
    with let:
        _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + track_id * sizeof(_TrackT))
    if _tr.vsps.bytes != 0: return MP4E_STATUS_ONLY_ONE_DSI_ALLOWED
    return MP4E_STATUS_OK if _appendMem(addr(_tr.vsps), dsi, _bytes) != 0 else MP4E_STATUS_NO_MEMORY

def MP4E_set_vps(mux: ptr[MP4E_mux_t], track_id: nint, vps: pointer, _bytes: nint) -> nint:
    with let:
        _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + track_id * sizeof(_TrackT))
    return MP4E_STATUS_OK if _appendMem(addr(_tr.vvps), vps, _bytes) != 0 else MP4E_STATUS_NO_MEMORY

def MP4E_set_sps(mux: ptr[MP4E_mux_t], track_id: nint, sps: pointer, _bytes: nint) -> nint:
    with let:
        _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + track_id * sizeof(_TrackT))
    return MP4E_STATUS_OK if _appendMem(addr(_tr.vsps), sps, _bytes) != 0 else MP4E_STATUS_NO_MEMORY

def MP4E_set_pps(mux: ptr[MP4E_mux_t], track_id: nint, pps: pointer, _bytes: nint) -> nint:
    with let:
        _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + track_id * sizeof(_TrackT))
    return MP4E_STATUS_OK if _appendMem(addr(_tr.vpps), pps, _bytes) != 0 else MP4E_STATUS_NO_MEMORY

@template_expand
def MP4E_put_sample(mux: ptr[MP4E_mux_t], track_num: nint, data: pointer,
                    data_bytes: nint, _duration: nint, _kind: nint) -> nint:
    if mux == None or data == None: return MP4E_STATUS_BAD_ARGUMENTS
    with let:
        _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + track_num * sizeof(_TrackT))
    if mux.enable_fragmentation != 0:
        if mux.fragments_count == 0:
            _ERR(_mp4eFlushIndex(mux))
        mux.fragments_count += 1
        return MP4E_STATUS_OK
    if _kind != MP4E_SAMPLE_CONTINUATION:
        if mux.sequential_mode_flag != 0:
            _ERR(_writePendingData(mux, _tr))
        if _addSampleDescriptor(mux, _tr, data_bytes, _duration, _kind) == 0:
            return MP4E_STATUS_NO_MEMORY
    else:
        if mux.sequential_mode_flag == 0:
            if _tr.smpl.bytes < sizeof(_SampleT):
                return MP4E_STATUS_NO_MEMORY
            with let:
                _smplDesc = cast[ptr[_SampleT]](cast[intp](_tr.smpl.data) + _tr.smpl.bytes - sizeof(_SampleT))
            _smplDesc.size += uint64(data_bytes)
    if mux.sequential_mode_flag != 0:
        if _vectorPut(addr(_tr.pending_sample), data, data_bytes) == None:
            return MP4E_STATUS_NO_MEMORY
    else:
        _ERR(mux.write_callback(mux.write_pos, data, csize_t(data_bytes), mux.token))
        mux.write_pos += data_bytes
    return MP4E_STATUS_OK

def MP4E_close(mux: ptr[MP4E_mux_t]) -> nint:
    with var:
        _err = MP4E_STATUS_OK
    if mux == None: return MP4E_STATUS_BAD_ARGUMENTS
    if mux.enable_fragmentation == 0:
        _err = _mp4eFlushIndex(mux)
    if mux.text_comment != None:
        c_free(mux.text_comment)
    with let:
        _ntracks = mux.tracks.bytes // sizeof(_TrackT)
    for _ntr in range(_ntracks):
        with let:
            _tr = cast[ptr[_TrackT]](cast[intp](mux.tracks.data) + _ntr * sizeof(_TrackT))
        _vectorReset(addr(_tr.vsps))
        _vectorReset(addr(_tr.vpps))
        _vectorReset(addr(_tr.smpl))
        _vectorReset(addr(_tr.pending_sample))
    _vectorReset(addr(mux.tracks))
    c_free(mux)
    return _err

# =========================================================================
# Bit reader / writer for SPS ID transcoding
# =========================================================================

def _loadShort(x: uint16) -> uint16:
    """{.inline.}"""
    return (x << 8) | (x >> 8)

def _showBits(bs: ptr[_BitReaderT], n: nint) -> uint32:
    return bs.cache >> (32 - n)

def _flushBits(bs: ptr[_BitReaderT], n: nint):
    bs.cache = bs.cache << n
    bs.cache_free_bits += n
    if bs.cache_free_bits >= 0:
        bs.cache = bs.cache | (uint32(_loadShort(bs.buf.contents)) << bs.cache_free_bits)
        bs.buf <<= cast[ptr[uint16]](cast[intp](bs.buf) + 2)
        bs.cache_free_bits -= 16

def _getBits(bs: ptr[_BitReaderT], n: nint) -> uint32:
    result = _showBits(bs, n)
    _flushBits(bs, n)
    return result

def _setPosBits(bs: ptr[_BitReaderT], _posBits: uint32):
    bs.buf <<= cast[ptr[uint16]](cast[intp](bs.origin) + intp((_posBits // 16) * 2))
    bs.cache = uint32(0)
    bs.cache_free_bits = 16
    _flushBits(bs, 0)
    _flushBits(bs, nint(_posBits & 15))

def _getPosBits(bs: ptr[_BitReaderT]) -> uint32:
    return uint32(cast[intp](bs.buf) - cast[intp](bs.origin)) // 2 * 16 - uint32(16 - bs.cache_free_bits)

def _remainingBits(bs: ptr[_BitReaderT]) -> nint:
    return nint(bs.origin_bytes) * 8 - nint(_getPosBits(bs))

def _initBits(bs: ptr[_BitReaderT], data: pointer, _dataBytes: nint):
    bs.origin = cast[ptr[uint16]](data)
    bs.origin_bytes = uint32(_dataBytes)
    _setPosBits(bs, uint32(0))

def _ueBits(bs: ptr[_BitReaderT]) -> nint:
    with var:
        _clz = 0
    while _getBits(bs, 1) == 0: _clz += 1
    return (1 << _clz) - 1 + (nint(_getBits(bs, _clz)) if _clz > 0 else 0)

# Output bitstream
def _swap32(x: uint32) -> uint32:
    """{.inline.}"""
    return ((x >> 24) & 0xFF) | ((x >> 8) & 0xFF00) | ((x << 8) & 0xFF0000) | ((x & 0xFF) << 24)

def _bsPutBits(bs: ptr[_BsT], n: nint, val: uint32):
    bs.shift -= n
    if bs.shift < 0:
        bs.cache = bs.cache | (val >> (-bs.shift))
        bs.buf.contents = _swap32(bs.cache)
        bs.buf <<= cast[ptr[uint32]](cast[intp](bs.buf) + 4)
        bs.shift = 32 + bs.shift
        bs.cache = uint32(0)
    bs.cache = bs.cache | (val << bs.shift)

def _bsFlush(bs: ptr[_BsT]):
    bs.buf.contents = _swap32(bs.cache)

def _bsGetPosBits(bs: ptr[_BsT]) -> uint32:
    return uint32((cast[intp](bs.buf) - cast[intp](bs.origin)) // 4 * 32) + uint32(32 - bs.shift)

def _bsByteAlign(bs: ptr[_BsT]) -> uint32:
    with let:
        _pos = nint(_bsGetPosBits(bs))
    _bsPutBits(bs, (-_pos) & 7, uint32(0))
    return uint32(_pos + ((-_pos) & 7))

def _bsPutGolomb(bs: ptr[_BsT], val: uint32):
    with var:
        _size = 0
        _t = val + 1
    while _t != 0:
        _size += 1
        _t = _t >> 1
    _bsPutBits(bs, 2 * _size - 1, val + 1)

def _bsInitBits(bs: ptr[_BsT], data: pointer):
    bs.origin = cast[ptr[uint32]](data)
    bs.buf <<= bs.origin
    bs.shift = 32
    bs.cache = uint32(0)

def _findMemCache(cache: mut@openArray[pointer], _cacheBytes: mut@openArray[nint],
                   _cacheSize: nint, mem: pointer, _bytes: nint) -> nint:
    if _bytes == 0: return -1
    for _i in range(_cacheSize):
        if _cacheBytes[_i] == _bytes and cmp_mem(cache[_i], mem, _bytes) == 0:
            return _i
    for _i in range(_cacheSize):
        if _cacheBytes[_i] == 0:
            cache[_i] = c_malloc(csize_t(_bytes))
            if cache[_i] != None:
                copy_mem(cache[_i], mem, _bytes)
                _cacheBytes[_i] = _bytes
            return _i
    return -1

def _removeNalEscapes(dst: ptr[UncheckedArray[uint8]], src: ptr[UncheckedArray[uint8]],
                       _h264DataBytes: nint) -> nint:
    with var:
        _i = 0
        _zeroCnt = 0
        _j = 0
    while _j < _h264DataBytes:
        if _zeroCnt == 2 and src[_j] <= 3:
            if src[_j] == 3:
                if _j == _h264DataBytes - 1:
                    pass  # cabac_zero_word
                elif src[_j + 1] <= 3:
                    _j += 1
                    _zeroCnt = 0
                else:
                    pass
            else:
                return 0
        dst[_i] = src[_j]
        _i += 1
        if src[_j] != 0: _zeroCnt = 0
        else: _zeroCnt += 1
        _j += 1
    return _i

def _nalPutEsc(d: ptr[UncheckedArray[uint8]], s: ptr[UncheckedArray[uint8]], n: nint) -> nint:
    with var:
        _j = 4
        _cntz = 0
    d[0] = uint8(0); d[1] = uint8(0); d[2] = uint8(0); d[3] = uint8(1)
    for _i in range(n):
        with let:
            _b = s[_i]
        if _cntz == 2 and _b <= 3:
            d[_j] = uint8(3); _j += 1; _cntz = 0
        if _b != 0: _cntz = 0
        else: _cntz += 1
        d[_j] = _b; _j += 1
    return _j

def _copyBits(bs: ptr[_BitReaderT], bd: ptr[_BsT]):
    with var:
        _bitCount = _remainingBits(bs)
    while _bitCount > 7:
        with let:
            _cb = min(_bitCount - 7, 8)
            _bits = _getBits(bs, _cb)
        _bsPutBits(bd, _cb, _bits)
        _bitCount -= _cb
    with var:
        _bits2 = _getBits(bs, _bitCount)
    while _bitCount > 0:
        with let:
            _bit0 = _bits2 & 1
        if _bit0 != 0:
            break
        _bits2 = _bits2 >> 1
        _bitCount -= 1
    if _bitCount > 0:
        _bsPutBits(bd, _bitCount, _bits2)

def _changeSpsId(bs: ptr[_BitReaderT], bd: ptr[_BsT], _newId: nint, _oldId: mut@nint) -> nint:
    for _i in range(3):
        with let:
            _bits = _getBits(bs, 8)
        _bsPutBits(bd, 8, _bits)
    with let:
        _spsId = _ueBits(bs)
    _oldId <<= _spsId
    _bsPutGolomb(bd, uint32(_newId))
    _copyBits(bs, bd)
    result = nint(_bsByteAlign(bd)) // 8
    _bsFlush(bd)
    return result

def _patchPps(h: ptr[_H264SpsIdPatcher], bs: ptr[_BitReaderT], bd: ptr[_BsT],
              _newPpsId: nint, _oldId: mut@nint) -> nint:
    with let:
        _ppsId = _ueBits(bs)
        _spsId = _ueBits(bs)
    _oldId <<= _ppsId
    with let:
        _mappedSps = h.map_sps[_spsId]
    _bsPutGolomb(bd, uint32(_newPpsId))
    _bsPutGolomb(bd, uint32(_mappedSps))
    _copyBits(bs, bd)
    result = nint(_bsByteAlign(bd)) // 8
    _bsFlush(bd)
    return result

def _patchSliceHeader(h: ptr[_H264SpsIdPatcher], bs: ptr[_BitReaderT], bd: ptr[_BsT]):
    with let:
        _firstMbInSlice = _ueBits(bs)
        _sliceType = _ueBits(bs)
        _ppsId = _ueBits(bs)
        _mappedPps = h.map_pps[_ppsId]
    _bsPutGolomb(bd, uint32(_firstMbInSlice))
    _bsPutGolomb(bd, uint32(_sliceType))
    _bsPutGolomb(bd, uint32(_mappedPps))
    _copyBits(bs, bd)

def _transcodeNalu(h: ptr[_H264SpsIdPatcher], src: ptr[UncheckedArray[uint8]],
                   _naluBytes: nint, dst: ptr[UncheckedArray[uint8]]) -> nint:
    with var:
        _oldId = nint(0)
        _bst = _BitReaderT()
        _bs = _BitReaderT()
        _bdt = _BsT()
        _bd = _BsT()
    with let:
        _payloadType = nint(src[0]) & 31
    dst[0] = src[0]
    _bsInitBits(addr(_bd), _ptrAdd(cast[ptr[uint8]](dst), 1))
    _initBits(addr(_bs), _ptrAdd(cast[ptr[uint8]](src), 1), _naluBytes - 1)
    _bsInitBits(addr(_bdt), _ptrAdd(cast[ptr[uint8]](dst), 1))
    _initBits(addr(_bst), _ptrAdd(cast[ptr[uint8]](src), 1), _naluBytes - 1)
    match _payloadType:
        case 7:
            with let:
                _cb = _changeSpsId(addr(_bst), addr(_bdt), 0, _oldId)
                _id = _findMemCache(h.sps_cache, h.sps_bytes, _MINIMP4_MAX_SPS, _ptrAdd(cast[ptr[uint8]](dst), 1), _cb)
            if _id == -1: return 0
            h.map_sps[_oldId] = _id
            _ = _changeSpsId(addr(_bs), addr(_bd), _id, _oldId)
        case 8:
            with let:
                _cb = _patchPps(h, addr(_bst), addr(_bdt), 0, _oldId)
                _id = _findMemCache(h.pps_cache, h.pps_bytes, _MINIMP4_MAX_PPS, _ptrAdd(cast[ptr[uint8]](dst), 1), _cb)
            if _id == -1: return 0
            h.map_pps[_oldId] = _id
            _ = _patchPps(h, addr(_bs), addr(_bd), _id, _oldId)
        case 1 | 2 | 5:
            _patchSliceHeader(h, addr(_bs), addr(_bd))
        case _:
            copy_mem(dst, src, _naluBytes)
            return _naluBytes
    result = 1 + nint(_bsByteAlign(addr(_bd))) // 8
    _bsFlush(addr(_bd))
    return result

# =========================================================================
# NAL unit finder
# =========================================================================

def _findStartCode(_h264Data: ptr[UncheckedArray[uint8]], _h264DataBytes: nint,
                    _zcount: mut@nint) -> ptr[UncheckedArray[uint8]]:
    with let:
        _eof = cast[intp](_h264Data) + _h264DataBytes
    with var:
        _pos = cast[intp](_h264Data)
    while _pos < _eof:
        with var:
            _zeroCnt = 1
            _found = _pos
        while _found < _eof and cast[ptr[UncheckedArray[uint8]]](_found)[0] != 0:
            _found += 1
        if _found >= _eof:
            _zcount <<= 0
            return cast[ptr[UncheckedArray[uint8]]](_eof)
        _pos = _found
        while _pos + _zeroCnt < _eof and cast[ptr[UncheckedArray[uint8]]](_pos)[_zeroCnt] == 0:
            _zeroCnt += 1
        if _zeroCnt >= 2 and _pos + _zeroCnt < _eof and cast[ptr[UncheckedArray[uint8]]](_pos)[_zeroCnt] == 1:
            _zcount <<= _zeroCnt + 1
            return cast[ptr[UncheckedArray[uint8]]](_pos + _zeroCnt + 1)
        _pos += _zeroCnt
    _zcount <<= 0
    return cast[ptr[UncheckedArray[uint8]]](_eof)

def _findNalUnit(_h264Data: ptr[UncheckedArray[uint8]], _h264DataBytes: nint,
                  _pnalUnitBytes: mut@nint) -> ptr[UncheckedArray[uint8]]:
    with let:
        _eof = cast[intp](_h264Data) + _h264DataBytes
    with var:
        _zcount = nint(0)
    with let:
        _start = _findStartCode(_h264Data, _h264DataBytes, _zcount)
    with var:
        _stop = _start
    if _start != None:
        with let:
            _startAddr = cast[intp](_start)
        _stop = _findStartCode(_start, nint(_eof - _startAddr), _zcount)
        with var:
            _stopAddr = cast[intp](_stop)
        while _stopAddr > _startAddr and cast[ptr[UncheckedArray[uint8]]](_stopAddr - 1)[0] == 0:
            _stopAddr -= 1
        _stop = cast[ptr[UncheckedArray[uint8]]](_stopAddr)
    _pnalUnitBytes <<= nint(cast[intp](_stop) - cast[intp](_start)) - _zcount
    return _start

# =========================================================================
# mp4_h26x_write_init / nal / close
# =========================================================================

def mp4_h26x_write_init(h: ptr[mp4_h26x_writer_t], mux: ptr[MP4E_mux_t],
                         width: nint, height: nint, is_hevc: nint) -> nint:
    with var:
        _tr = MP4E_track_t()
    _tr.track_media_kind = TrackMediaKind.e_video
    _tr.language[0] = uint8(117); _tr.language[1] = uint8(110)
    _tr.language[2] = uint8(100); _tr.language[3] = uint8(0)
    _tr.object_type_indication = MP4_OBJECT_TYPE_HEVC if is_hevc != 0 else MP4_OBJECT_TYPE_AVC
    _tr.time_scale = uint32(90000)
    _tr.default_duration = uint32(0)
    _tr.width = int32(width)
    _tr.height = int32(height)
    h.mux_track_id = MP4E_add_track(mux, addr(_tr))
    h.mux = mux
    h.is_hevc = is_hevc
    h.need_vps = is_hevc
    h.need_sps = 1
    h.need_pps = 1
    h.need_idr = 1
    zero_mem(addr(h.sps_patcher), sizeof(_H264SpsIdPatcher))
    return MP4E_STATUS_OK

def mp4_h26x_write_close(h: ptr[mp4_h26x_writer_t]):
    with let:
        _p = addr(h.sps_patcher)
    for _i in range(_MINIMP4_MAX_SPS):
        if _p.sps_cache[_i] != None: c_free(_p.sps_cache[_i])
    for _i in range(_MINIMP4_MAX_PPS):
        if _p.pps_cache[_i] != None: c_free(_p.pps_cache[_i])
    zero_mem(h, sizeof(mp4_h26x_writer_t))

def mp4_h26x_write_nal(h: ptr[mp4_h26x_writer_t], nal: ptr[UncheckedArray[uint8]],
                        length: nint, _timeStamp90kHz_next: uint32) -> nint:
    with let:
        _eof = cast[intp](nal) + length
    with var:
        _err = MP4E_STATUS_OK
        _curNal = nal
    while True:
        with var:
            _sizeofNal = nint(0)
        _curNal <<= _findNalUnit(_curNal, nint(_eof - cast[intp](_curNal)), _sizeofNal)
        if _sizeofNal == 0: break

        with let:
            _payloadType = nint(_curNal[0]) & 31
        if _payloadType == 9:
            return _err

        with let:
            _nal1 = cast[ptr[UncheckedArray[uint8]]](c_malloc(csize_t(_sizeofNal * 17 // 16 + 32)))
        if _nal1 == None: return MP4E_STATUS_NO_MEMORY
        with let:
            _nal2 = cast[ptr[UncheckedArray[uint8]]](c_malloc(csize_t(_sizeofNal * 17 // 16 + 32)))
        if _nal2 == None:
            c_free(_nal1)
            return MP4E_STATUS_NO_MEMORY

        with var:
            _escapedSize = _removeNalEscapes(_nal2, _curNal, _sizeofNal)
        if _escapedSize == 0:
            c_free(_nal1); c_free(_nal2)
            return MP4E_STATUS_BAD_ARGUMENTS

        _escapedSize = _transcodeNalu(addr(h.sps_patcher), _nal2, _escapedSize, _nal1)
        _escapedSize = _nalPutEsc(_nal2, _nal1, _escapedSize)


        match _payloadType:
            case 7:
                _ = MP4E_set_sps(h.mux, h.mux_track_id,
                                 _ptrAdd(cast[ptr[uint8]](_nal2), 4), _escapedSize - 4)
                h.need_sps = 0
            case 8:
                if h.need_sps != 0:
                    c_free(_nal1); c_free(_nal2)
                    return MP4E_STATUS_BAD_ARGUMENTS
                _ = MP4E_set_pps(h.mux, h.mux_track_id,
                                 _ptrAdd(cast[ptr[uint8]](_nal2), 4), _escapedSize - 4)
                h.need_pps = 0
            case 5:
                if h.need_sps != 0:
                    c_free(_nal1); c_free(_nal2)
                    return MP4E_STATUS_BAD_ARGUMENTS
                h.need_idr = 0
                if h.need_pps == 0 and h.need_idr == 0:
                    with var:
                        _bs = _BitReaderT()
                    _initBits(addr(_bs), _ptrAdd(cast[ptr[uint8]](_curNal), 1), _sizeofNal - 4 - 1)
                    with let:
                        _firstMbInSlice = _ueBits(addr(_bs))
                    with var:
                        _sampleKind = MP4E_SAMPLE_DEFAULT
                    _nal2[0] = uint8((_escapedSize - 4) >> 24)
                    _nal2[1] = uint8((_escapedSize - 4) >> 16)
                    _nal2[2] = uint8((_escapedSize - 4) >> 8)
                    _nal2[3] = uint8(_escapedSize - 4)
                    if _firstMbInSlice != 0:
                        _sampleKind = MP4E_SAMPLE_CONTINUATION
                    elif _payloadType == 5:
                        _sampleKind = MP4E_SAMPLE_RANDOM_ACCESS
                    _err = MP4E_put_sample(h.mux, h.mux_track_id, _nal2, _escapedSize,
                                           nint(_timeStamp90kHz_next), _sampleKind)
            case _:
                if h.need_sps != 0:
                    c_free(_nal1); c_free(_nal2)
                    return MP4E_STATUS_BAD_ARGUMENTS
                if h.need_pps == 0 and h.need_idr == 0:
                    with var:
                        _bs = _BitReaderT()
                    _initBits(addr(_bs), _ptrAdd(cast[ptr[uint8]](_curNal), 1), _sizeofNal - 4 - 1)
                    with let:
                        _firstMbInSlice = _ueBits(addr(_bs))
                    with var:
                        _sampleKind = MP4E_SAMPLE_DEFAULT
                    _nal2[0] = uint8((_escapedSize - 4) >> 24)
                    _nal2[1] = uint8((_escapedSize - 4) >> 16)
                    _nal2[2] = uint8((_escapedSize - 4) >> 8)
                    _nal2[3] = uint8(_escapedSize - 4)
                    if _firstMbInSlice != 0:
                        _sampleKind = MP4E_SAMPLE_CONTINUATION
                    elif _payloadType == 5:
                        _sampleKind = MP4E_SAMPLE_RANDOM_ACCESS
                    _err = MP4E_put_sample(h.mux, h.mux_track_id, _nal2, _escapedSize,
                                           nint(_timeStamp90kHz_next), _sampleKind)

        c_free(_nal1); c_free(_nal2)
        if _err != 0: break
        _curNal <<= cast[ptr[UncheckedArray[uint8]]](cast[intp](_curNal) + 1)
    return _err
