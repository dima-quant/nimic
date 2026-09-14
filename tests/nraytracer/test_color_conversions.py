# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from color_conversions import (
    RGB_Raw, YCbCrKind, rgbRaw_to_ycbcr420, initChannelDesc, ChannelDescriptor
)
from nimic.system.ansi_c import c_malloc, uintp, csize_t
from nimic.std.syncio import read_file

class IntPair(Object):
    a: nint
    b: nint

def next_int(data: string, start: nint) -> IntPair:
    with var: i = start
    while i < len(data) and (ord(data[i]) == 32 or ord(data[i]) == 10 or ord(data[i]) == 13):
        i += 1
    if i >= len(data):
        result = IntPair()
        result.a = 0
        result.b = i
        return result
    if ord(data[i]) == 35:
        while i < len(data) and ord(data[i]) != 10:
            i += 1
        return next_int(data, i)
    
    with var: val = 0
    while i < len(data) and 48 <= ord(data[i]) and ord(data[i]) <= 57:
        val = val * 10 + (ord(data[i]) - 48)
        i += 1
    
    result = IntPair()
    result.a = val
    result.b = i
    return result


def parse_ppm_and_convert(filepath: string):
    # Rudimentary PPM P3 parser for testing
    with let: data = read_file(filepath)
    with var: i = 0
    
    # Skip 'P3'
    while i < len(data) and ord(data[i]) != 32 and ord(data[i]) != 10 and ord(data[i]) != 13:
        i += 1
        
    with var:
        width = 0
        height = 0
        max_col = 0
        result: IntPair
    
    result = next_int(data, i)
    width = result.a
    i = result.b
    
    result = next_int(data, i)
    height = result.a
    i = result.b
    
    result = next_int(data, i)
    max_col = result.a
    i = result.b
    
    with let:
        w_int32 = int32(width)
        h_int32 = int32(height)
        rgb_size = w_int32 * h_int32 * int32(3)
        y_size = w_int32 * h_int32
        uv_size = (w_int32 * h_int32) // int32(4) + int32(1)

    with var:
        rgb_buf = c_malloc(csize_t(rgb_size))
        y_buf = c_malloc(csize_t(y_size))
        u_buf = c_malloc(csize_t(uv_size))
        v_buf = c_malloc(csize_t(uv_size))

    with var: rgb_ptr = cast[ptr[UncheckedArray[RGB_Raw]]](rgb_buf)
    for idx in range(width * height):
        for c in range(3):
            result = next_int(data, i)
            with let: val = result.a
            i = result.b
            if c == 0: rgb_ptr[idx].r = uint8(val)
            elif c == 1: rgb_ptr[idx].g = uint8(val)
            elif c == 2: rgb_ptr[idx].b = uint8(val)

    with let:
        rgbD = initChannelDesc[RGB_Raw](cast[ptr[RGB_Raw]](rgb_buf), w_int32, False)
        yD = initChannelDesc[uint8](cast[ptr[uint8]](y_buf), w_int32, False)
        uD = initChannelDesc[uint8](cast[ptr[uint8]](u_buf), w_int32, True)
        vD = initChannelDesc[uint8](cast[ptr[uint8]](v_buf), w_int32, True)

    rgbRaw_to_ycbcr420(w_int32, h_int32, rgbD, yD, uD, vD, YCbCrKind.BT601)

    # Print some output to verify
    with var: y_out = cast[ptr[UncheckedArray[uint8]]](y_buf)
    with var: u_out = cast[ptr[UncheckedArray[uint8]]](u_buf)
    with var: v_out = cast[ptr[UncheckedArray[uint8]]](v_buf)
    
    print("Parsed PPM: ", width, "x", height, " max_color=", max_col)
    print("Y channel first 10 pixels:")
    for j in range(10):
        print(int32(y_out[j]))
        
    print("U channel first 2 pixels:")
    for j in range(2):
        print(int32(u_out[j]))
        
    print("V channel first 2 pixels:")
    for j in range(2):
        print(int32(v_out[j]))

if comptime(__name__ == "__main__"):
    # parse_ppm_and_convert("ncache/build/rendered16/animation_00000.ppm")
    parse_ppm_and_convert("tests/nraytracer/ncache/build/rendered16/animation_00000.ppm")
