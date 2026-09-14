# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.strutils import *
from nimic.std.strformat import *
from nimic.std.algorithm import *
from mp4 import *


with const:
    # RenderedDir = string("build/rendered16")
    RenderedDir = string("tests/nraytracer/ncache/build/rendered_test") # debug
    Width = 512
    Height = 288
    FPS = 30



def main():
    with let:
        tmp264 = RenderedDir / "reference.264"

    # Mux .264 -> .mp4
    with let:
        mp4Path = RenderedDir / "reference_py.mp4"
    with var:
        muxer = MP4Muxer()
    with let:
        mp4File = open(mp4Path, fmWrite)
    initialize(muxer, mp4File, int32(Width), int32(Height))
    writeMP4_from(muxer, tmp264)
    close(muxer)
    mp4File.close()

    print(f"Reference MP4 written to {mp4Path}")
    print("Please verify playback before proceeding to Phase 1.")

if __name__ == "__main__":
    main()
