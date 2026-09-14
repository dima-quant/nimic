# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

import
  std/[strutils, os],
  system/ansi_c,
  ./minimp4

# High-Level API
# ------------------------------------------------------

type MP4Muxer* = object
  muxer: ptr MP4E_mux_t
  writer: ptr mp4_h26x_writer_t

proc `=`*(dst: var MP4Muxer, src: MP4Muxer) {.error: "An MP4Muxer cannot be copied".}

proc close*(m: var MP4Muxer) =
  discard MP4E_close(m.muxer)
  m.muxer = nil
  mp4_h26x_write_close(m.writer)
  c_free(m.writer)

{.push stackTrace: off.}
proc writeToFile(
       offset: int64,
       buffer: pointer,
       size: csize_t,
       token: pointer
     ): cint {.cdecl, gcsafe.} =
  let file = cast[File](token)
  file.setFilePos(offset)
  let bytesWritten = file.writeBuffer(buffer, size)
  if bytesWritten.csize_t != size:
    return -50
  return 0
{.pop.}

proc writeMP4_from*(
       self: var MP4Muxer,
       src: string
     ) =
  let buffer = src.readFile()
  let data = cast[ptr UncheckedArray[byte]](buffer[0].unsafeAddr)
  let dataLen = buffer.len
  let ok = mp4_h26x_write_nal(
    self.writer, data, dataLen, uint32(90000 div 30)
  )
  doAssert ok == MP4E_STATUS_OK, "error: mp4_h26x_write_nal failed, code=" & $ok

proc initialize*(
       self: var MP4Muxer,
       file: File,
       width, height: int32
     ) =
  doAssert self.muxer.isNil, "Already initialized"
  doAssert self.writer.isNil, "Already initialized"
  self.muxer = MP4E_open(
    sequential_mode_flag = 0,
    enable_fragmentation = 0,
    token = pointer(file),
    write_callback = writeToFile
  )
  doAssert not self.muxer.isNil, "MP4E_open returned NULL! muxer init failed!"

  self.writer = cast[typeof self.writer](
    c_malloc(csize_t sizeof(mp4_h26x_writer_t))
  )

  let ok = self.writer.mp4_h26x_write_init(
    self.muxer,
    width.int, height.int,
    is_hevc = 0
  )
  doAssert ok == MP4E_STATUS_OK, "error: mp4_h26x_write_init failed"

# Sanity checks
# ------------------------------------------------------

when isMainModule:
  import strformat

  proc main() =
    let exeName = getAppFilename().extractFilename()
    var source, destination: string
    if paramCount() != 2:
      echo &"Usage: {exeName} <source> <destination>"
      quit 1
    else:
      source = paramStr(1)
      destination = paramStr(2)

    var mP4Muxer: MP4Muxer
    let dst = open(destination, fmWrite)
    mP4Muxer.initialize(dst, 576, 324)
    mP4Muxer.writeMP4_from(source)
    mP4Muxer.close()
    dst.close()

  main()
