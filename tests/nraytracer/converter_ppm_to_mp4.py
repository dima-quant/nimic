# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.strutils import *
from nimic.std.strformat import *
from nimic.std.algorithm import *
from h264 import H264Encoder, init, getFrameBuffers, flushFrame, finish
from mp4 import *
from color_conversions import RGB_Raw, initChannelDesc, rgbRaw_to_ycbcr420, YCbCrKind

# class RGB_Raw(Object):
#     r: uint8
#     g: uint8
#     b: uint8

with const:
    #RenderedDir = string("build/rendered_test")
    RenderedDir = string("tests/nraytracer/ncache/build/rendered16") # debug
    Width = 512
    Height = 288
    FPS = 30

# Parse a P3 PPM file into a flat array of RGB bytes (r,g,b,r,g,b,...)
def readPPM(path: string) -> seq[uint8]:
    with let:
        content = read_file(path)
    with var:
        pos = 0
        lineNum = 0
        width = 0
        height = 0
        maxVal = 0

    # Parse header
    for line in string(content).splitlines():
        if len(line) == 0 or str(line[0]) == "#":
            pos += len(line) + 1
            continue
        match lineNum:
            case 0:
                assert line == "P3", "Expected P3 format, got: " + line
            case 1:
                with let:
                    parts = string(line).strip().split()
                width = parse_int(parts[0])
                height = parse_int(parts[1])
            case 2:
                maxVal = parse_int(string(line).strip())
                assert maxVal == 255
                pos += len(line) + 1
                lineNum += 1
                break
            case _:
                pass
        lineNum += 1
        pos += len(line) + 1

    # Parse pixel data
    result = new_seq[uint8](width * height * 3)
    with var:
        idx = 0
    with let:
        rest = string(content[pos :])
    for tok in rest.split_whitespace():
        if idx < len(result):
            result[idx] = uint8(parse_int(tok))
            idx += 1
    return result


def main():
    print("Reference MP4 Generator")
    print(f"Reading PPM frames from {RenderedDir}/")

    # Collect and sort PPM files
    with var:
        ppmFiles = seq[string]()
    for f in walk_dir(RenderedDir):
        if f.kind == pcFile and string(f.path).endswith(".ppm"):
            ppmFiles.add(string(f.path))
    ppmFiles.sort()

    print(f"Found {len(ppmFiles)} PPM frames ({Width}x{Height})")
    if len(ppmFiles) == 0:
        print("No PPM files found!")
        quit(1)

    with let:
        tmp264 = RenderedDir / "reference_py.264"
        out264 = open(tmp264, fmWrite)
    print(f"Opened file: {tmp264}")

    with var:
        encoder = init(H264Encoder, Width, Height, out264)
    print(f"Encoder initialized: {encoder}")
    with let:
        (Y, Cb, Cr) = getFrameBuffers(encoder)
        yD  = initChannelDesc(Y, Width, subsampled=False)
        uD  = initChannelDesc(Cb, Width, subsampled=True)
        vD  = initChannelDesc(Cr, Width, subsampled=True)
    print(f"Frame buffers initialized: {yD}, {uD}, {vD}")
    # Encode each frame
    for i, ppmPath in ppmFiles:
        print(f"\rEncoding frame {i+1}/{len(ppmFiles)}: {extract_filename(ppmPath)}")
        stderr.write(f"\rEncoding frame {i+1}/{len(ppmFiles)}: {extract_filename(ppmPath)}")

        # Read PPM to raw RGB
        with let:
            rgbData = readPPM(ppmPath)
        assert len(rgbData) == Width * Height * 3, f"Expected {Width*Height*3} bytes, got {len(rgbData)}"
        print(f"Read {len(rgbData)} bytes from {ppmPath}")
        # Convert RGB -> YCbCr420
        with let:
            rgbDesc = initChannelDesc(
                cast[ptr[UncheckedArray[RGB_Raw]]](unsafe_addr(rgbData[0])),
                Width, subsampled=False
            )
        rgbRaw_to_ycbcr420(
            int32(Width), int32(Height),
            rgbDesc,
            yD,
            uD,
            vD,
            YCbCrKind.BT601
        )

        if i == 0:
            print("\nFirst frame debug:")
            print(f"  RGB[0,0] = {rgbData[0]}, {rgbData[1]}, {rgbData[2]}")
            with let:
                ptrY = Y
                ptrU = Cb
                ptrV = Cr
            print(f"  Y[0,0] = {ptrY[0]}, {ptrY[1]}")
            print(f"  U[0,0] = {ptrU[0]}")
            print(f"  V[0,0] = {ptrV[0]}")

        # Encode frame
        flushFrame(encoder)

    stderr.write("\n")
    finish(encoder)
    out264.close()
    print(f"H264 written to {tmp264}")

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
