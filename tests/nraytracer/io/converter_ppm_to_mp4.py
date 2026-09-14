# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.strutils import *
from nimic.std.strformat import *
from nimic.std.algorithm import *
from h264 import H264Encoder
from mp4 import MP4Muxer
from color_conversions import RGB_Raw, initChannelDesc, rgbRaw_to_ycbcr420, YCbCrKind

# class RGB_Raw(Object):
#     r: uint8
#     g: uint8
#     b: uint8

with const:
    RenderedDir = "build/rendered16"
    Width = 512
    Height = 288
    FPS = 30

# Parse a P3 PPM file into a flat array of RGB bytes (r,g,b,r,g,b,...)
def readPPM(path: string) -> seq[uint8]:
    with let:
        content = readFile(path)
    with var:
        pos = 0
        lineNum = 0
        width = 0
        height = 0
        maxVal = 0

    # Parse header
    for line in content.splitLines():
        if len(line) == 0 or str(line[0]) == "#":
            pos += len(line) + 1
            continue
        match lineNum:
            case 0:
                assert line == "P3", "Expected P3 format, got: " + line
            case 1:
                with let: 
                    parts = line.strip().split()
                width = parseInt(parts[0])
                height = parseInt(parts[1])
            case 2:
                maxVal = parseInt(line.strip())
                assert maxVal == 255
                pos += len(line) + 1
                lineNum += 1
                break
            case _:
                discard
        lineNum += 1
        pos += len(line) + 1

    # Parse pixel data
    result = newSeq[uint8](width * height * 3)
    with var:
        idx = 0
    with let:
        rest = content[pos :]
    for tok in rest.splitWhitespace():
        if idx < len(result):
            result[idx] = uint8(parseInt(tok))
            idx += 1
    return result


def main():
    print("Reference MP4 Generator")
    print(f"Reading PPM frames from {RenderedDir}/")

    # Collect and sort PPM files
    with var:
        ppmFiles = seq[string]()
    for f in walkDir(RenderedDir):
        if f.kind == pcFile and f.path.endsWith(".ppm"):
            ppmFiles.add(f.path)
    ppmFiles.sort()

    print(f"Found {len(ppmFiles)} PPM frames ({Width}x{Height})")
    if len(ppmFiles) == 0:
        print("No PPM files found!")
        quit(1)

    with let:
        tmp264 = RenderedDir / "reference.264"
        out264 = open(tmp264, fmWrite)
    print(f"Opened file: {tmp264}")
        
    with var:
        encoder = H264Encoder.init(Width, Height, out264)
    print(f"Encoder initialized: {encoder}")
    with let:
        (Y, Cb, Cr) = encoder.getFrameBuffers()
        yD  = initChannelDesc(Y, Width, subsampled=False)
        uD  = initChannelDesc(Cb, Width, subsampled=True)
        vD  = initChannelDesc(Cr, Width, subsampled=True)
    print(f"Frame buffers initialized: {yD}, {uD}, {vD}")
    # Encode each frame
    for i, ppmPath in enumerate(ppmFiles):
        print(f"\rEncoding frame {i+1}/{len(ppmFiles)}: {extractFilename(ppmPath)}")
        stderr.write(f"\rEncoding frame {i+1}/{len(ppmFiles)}: {extractFilename(ppmPath)}")

        # Read PPM to raw RGB
        with let:
            rgbData = readPPM(ppmPath)
        assert len(rgbData) == Width * Height * 3, f"Expected {Width*Height*3} bytes, got {len(rgbData)}"
        print(f"Read {len(rgbData)} bytes from {ppmPath}")
        # Convert RGB -> YCbCr420
        with let:
            rgbDesc = initChannelDesc(
                cast[ptr[UncheckedArray[RGB_Raw]]](unsafeAddr(rgbData[0])),
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
        encoder.flushFrame()

    stderr.write("\n")
    encoder.finish()
    out264.close()
    print(f"H264 written to {tmp264}")

    # Mux .264 -> .mp4
    with let:
        mp4Path = RenderedDir / "reference_py.mp4"
    with var:
        muxer: MP4Muxer
    with let:
        mp4File = open(mp4Path, fmWrite)
    muxer.initialize(mp4File, int32(Width), int32(Height))
    muxer.writeMP4_from(tmp264)
    muxer.close()
    mp4File.close()

    print(f"Reference MP4 written to {mp4Path}")
    print("Please verify playback before proceeding to Phase 1.")

if __name__ == "__main__":
    main()
