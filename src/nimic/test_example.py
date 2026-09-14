# /// nimic
#
# ///
from __future__ import annotations

from nimic.ntypes import *

# Struct definition (Nim object)
class Vec3(Object):
    x: float64
    y: float64
    z: float64

    def __add__(self: Vec3, v: Vec3) -> Vec3:
        """{.inline.}"""
        result = Vec3()
        result.x = self.x + v.x
        result.y = self.y + v.y
        result.z = self.z + v.z
        return result

# Distinct type
@distinct
class Point3(Vec3):
    """{.borrow: `.`.}"""

# Multi-dispatch
@dispatch
def point3(x: float64, y: float64, z: float64) -> Point3:
    result = Point3(Vec3())
    result.x = x; result.y = y; result.z = z
    return result

# Usage
with let:
    a = point3(1.0, 2.0, 3.0)
    b = point3(4.0, 5.0, 6.0)
    c = Vec3(a) + Vec3(b)

print(c)

from nimic.system.ansi_c import c_malloc, c_free, csize_t

def _fourCC(a: char, b: char, c: char, d: char) -> uint32:
    """{.inline.}"""
    return (uint32(ord(a)) << 24) | (uint32(ord(b)) << 16) | (uint32(ord(c)) << 8) | uint32(ord(d))

with var:
    _stackBase = array[20, ptr[uint8]]()
    _stack = cast[ptr[ptr[uint8]]](addr(_stackBase[0]))
pass