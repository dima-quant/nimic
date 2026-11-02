## nimic.std.os (rule:stdbridge): Nim's std/os. nimony keeps removeFile / removeDir / createDir in std/files and
## std/dirs, on `Path`: under nimony this module adds the `string` forms of std/os, which nimic's os has.
import std/os
export os

when defined(nimony):
  import std/[paths, files, dirs]

  proc removeFile*(file: string) {.raises.} =
    files.removeFile(path(file))

  proc removeDir*(dir: string) {.raises.} =
    dirs.removeDir(path(dir))

  proc createDir*(dir: string) {.raises.} =
    dirs.createDir(path(dir))
