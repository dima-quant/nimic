import ncode/pydefs
import std/os
import std/strformat
import system/ansi_c
import std/syncio
import minimp4
type
  MP4Muxer* = object
    local_muxer: ptr MP4E_mux_t
    local_writer: ptr mp4_h26x_writer_t


proc close*(m: var MP4Muxer) =
  discard MP4E_close(m.local_muxer)
  m.local_muxer = nil
  mp4_h26x_write_close(m.local_writer)
  c_free(m.local_writer)

proc writeToFile*(offset: int64, buffer: pointer, size: csize_t, token: pointer): cint {.cdecl, gcsafe.} =
  let
    file = cast[File](token)
  set_file_pos(file, offset)
  let
    bytesWritten = write_buffer(file, buffer, size)
  if csize_t(bytesWritten) != size:
    return -50
  return 0

proc writeMP4_from*(self: var MP4Muxer, src: string) =
  let
    local_buffer = read_file(src)
    data = cast[ptr UncheckedArray[uint8]](addr(local_buffer[0]))
    dataLen = len(local_buffer)
    ok = mp4_h26x_write_nal(self.local_writer, data, dataLen, uint32(90000 div 30))
  doAssert(ok == MP4E_STATUS_OK, "error: mp4_h26x_write_nal failed, code=" + $(ok))

proc initialize*(self: var MP4Muxer, file: File, width: int32, height: int32) =
  doAssert(self.local_muxer.is_nil, "Already initialized")
  doAssert(self.local_writer.is_nil, "Already initialized")
  self.local_muxer = MP4E_open(0, 0, cast[pointer](file), writeToFile)
  doAssert(self.local_muxer.is_nil == false, "MP4E_open returned NULL! muxer init failed!")
  self.local_writer = cast[ptr mp4_h26x_writer_t](c_malloc(csize_t(sizeof(mp4_h26x_writer_t))))
  let
    ok = mp4_h26x_write_init(self.local_writer, self.local_muxer, nint(width), nint(height), 0)
  doAssert(ok == MP4E_STATUS_OK, "error: mp4_h26x_write_init failed")
when isMainModule:

  proc main*() =
    let
      exeName = extractFilename(getAppFilename())
    var
      source: string
      destination: string
    if paramCount() != 2:
      echo(&"Usage: {exeName} <source> <destination>")
      quit(1)
    else:
      source = paramStr(1)
      destination = paramStr(2)
    var
      mP4Muxer: MP4Muxer
    let
      dst = open(destination, fmWrite)
    mP4Muxer.initialize(dst, 576, 324)
    mP4Muxer.writeMP4_from(source)
    mP4Muxer.close()
    dst.close()
  main()