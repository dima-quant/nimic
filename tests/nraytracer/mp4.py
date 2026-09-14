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

from nimic.std.os import *
from nimic.std.strformat import *
from nimic.system.ansi_c import *
from nimic.std.syncio import read_file, write_buffer, set_file_pos
from minimp4 import MP4E_mux_t, mp4_h26x_writer_t, MP4E_close, mp4_h26x_write_close, MP4E_STATUS_OK, mp4_h26x_write_nal, MP4E_open, mp4_h26x_write_init

class MP4Muxer(Object):
    _muxer: ptr[MP4E_mux_t]
    _writer: ptr[mp4_h26x_writer_t]

def close(m: mut@MP4Muxer):
    _ = MP4E_close(m._muxer)
    m._muxer = None
    mp4_h26x_write_close(m._writer)
    c_free(m._writer)

def writeToFile(offset: int64, buffer: pointer, size: csize_t, token: pointer) -> cint:
    """{.cdecl, gcsafe.}"""
    with let:
        file = cast[File](token)
    set_file_pos(file, offset)
    with let:
        bytesWritten = write_buffer(file, buffer, size)

    if csize_t(bytesWritten) != size:
        return -50
    return 0

def writeMP4_from(self: mut@MP4Muxer, src: string):
    with let:
        _buffer = read_file(src)
        data = cast[ptr[UncheckedArray[uint8]]](addr(_buffer[0]))
        dataLen = len(_buffer)
    with let:
        ok = mp4_h26x_write_nal(self._writer, data, dataLen, uint32(90000 // 30))
    doAssert(ok == MP4E_STATUS_OK, "error: mp4_h26x_write_nal failed, code=" + str(ok))

def initialize(self: mut@MP4Muxer, file: File, width: int32, height: int32):
    doAssert(self._muxer.is_nil, "Already initialized")
    doAssert(self._writer.is_nil, "Already initialized")
    self._muxer = MP4E_open(0, 0, cast[pointer](file), writeToFile)
    doAssert(self._muxer.is_nil == False, "MP4E_open returned NULL! muxer init failed!")
    self._writer = cast[ptr[mp4_h26x_writer_t]](c_malloc(csize_t(sizeof(mp4_h26x_writer_t))))
    with let:
        ok = mp4_h26x_write_init(self._writer, self._muxer, nint(width), nint(height), 0)
    doAssert(ok == MP4E_STATUS_OK, "error: mp4_h26x_write_init failed")

if comptime(__name__ == "__main__"):
    def main():
        with let:
            exeName = extractFilename(getAppFilename())
        with var:
            source: string
            destination: string
        if paramCount() != 2:
            print(f"Usage: {exeName} <source> <destination>")
            quit(1)
        else:
            source = paramStr(1)
            destination = paramStr(2)

        with var:
            mP4Muxer = MP4Muxer()
        with let:
            dst = open(destination, fmWrite)
        mP4Muxer.initialize(dst, 576, 324)
        mP4Muxer.writeMP4_from(source)
        mP4Muxer.close()
        dst.close()

    main()
