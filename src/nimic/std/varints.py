"""Nim std/varints — variable length integers (SQLite4's encoding) and zigzag encoding, ported line for line from
Nim 2.2.4's lib/std/varints.nim. `z` is an openArray[byte] (array[N, byte], seq[byte], a toOpenArray view);
readVu64's `pResult` is a `var uint64`: a uint64 cell, assigned with `<<=`."""
from __future__ import annotations

from nimic.ntypes import int64, nint, uint8, uint64

maxVarIntLen = 9  # the maximal number of bytes a varint can take

_M64 = (1 << 64) - 1


def _b(z, i: int) -> int:
    return int(z[i])


def readVu64(z, pResult: uint64) -> nint:
    """Decodes the varint at the start of z into pResult; the number of bytes read, 0 if z is too short."""
    z0 = _b(z, 0)
    if z0 <= 240:
        pResult <<= uint64(z0)
        return nint(1)
    if z0 <= 248:
        if len(z) < 2:
            return nint(0)
        pResult <<= uint64((z0 - 241) * 256 + _b(z, 1) + 240)
        return nint(2)
    if len(z) < z0 - 246:
        return nint(0)
    if z0 == 249:
        pResult <<= uint64(2288 + 256 * _b(z, 1) + _b(z, 2))
        return nint(3)
    if z0 == 250:
        pResult <<= uint64((_b(z, 1) << 16) + (_b(z, 2) << 8) + _b(z, 3))
        return nint(4)
    x = (_b(z, 1) << 24) + (_b(z, 2) << 16) + (_b(z, 3) << 8) + _b(z, 4)
    if z0 == 251:
        pResult <<= uint64(x)
        return nint(5)
    if z0 == 252:
        pResult <<= uint64(((x << 8) + _b(z, 5)) & _M64)
        return nint(6)
    if z0 == 253:
        pResult <<= uint64(((x << 16) + (_b(z, 5) << 8) + _b(z, 6)) & _M64)
        return nint(7)
    if z0 == 254:
        pResult <<= uint64(((x << 24) + (_b(z, 5) << 16) + (_b(z, 6) << 8) + _b(z, 7)) & _M64)
        return nint(8)
    pResult <<= uint64(((x << 32) + (0xffffffff & ((_b(z, 5) << 24) + (_b(z, 6) << 16) + (_b(z, 7) << 8)
                                                   + _b(z, 8)))) & _M64)
    return nint(9)


def _varintWrite32(z, start: int, y: int) -> None:
    z[start] = uint8((y >> 24) & 255)
    z[start + 1] = uint8((y >> 16) & 255)
    z[start + 2] = uint8((y >> 8) & 255)
    z[start + 3] = uint8(y & 255)


def writeVu64(z, x) -> nint:
    """Encodes x as a varint into z (at least maxVarIntLen bytes); the number of bytes written."""
    x = int(x) & _M64
    if x <= 240:
        z[0] = uint8(x)
        return nint(1)
    if x <= 2287:
        y = (x - 240) & 0xffffffff
        z[0] = uint8(((y >> 8) + 241) & 255)
        z[1] = uint8(y & 255)
        return nint(2)
    if x <= 67823:
        y = (x - 2288) & 0xffffffff
        z[0] = uint8(249)
        z[1] = uint8((y >> 8) & 255)
        z[2] = uint8(y & 255)
        return nint(3)
    y = x & 0xffffffff
    w = x >> 32
    if w == 0:
        if y <= 16777215:
            z[0] = uint8(250)
            z[1] = uint8((y >> 16) & 255)
            z[2] = uint8((y >> 8) & 255)
            z[3] = uint8(y & 255)
            return nint(4)
        z[0] = uint8(251)
        _varintWrite32(z, 1, y)
        return nint(5)
    if w <= 255:
        z[0] = uint8(252)
        z[1] = uint8(w)
        _varintWrite32(z, 2, y)
        return nint(6)
    if w <= 65535:
        z[0] = uint8(253)
        z[1] = uint8((w >> 8) & 255)
        z[2] = uint8(w & 255)
        _varintWrite32(z, 3, y)
        return nint(7)
    if w <= 16777215:
        z[0] = uint8(254)
        z[1] = uint8((w >> 16) & 255)
        z[2] = uint8((w >> 8) & 255)
        z[3] = uint8(w & 255)
        _varintWrite32(z, 4, y)
        return nint(8)
    z[0] = uint8(255)
    _varintWrite32(z, 1, w)
    _varintWrite32(z, 5, y)
    return nint(9)


def encodeZigzag(x) -> uint64:
    """Nim: encodeZigzag — (x shl 1) xor (x shr 63) on the bits of x as uint64."""
    xu = int(x) & _M64
    return uint64((((xu << 1) & _M64) ^ (xu >> 63)) & _M64)


def decodeZigzag(x) -> int64:
    """Nim: decodeZigzag — cast[int64]((x shr 1) xor (x shl 63)), as Nim 2.2.4 writes it."""
    xu = int(x) & _M64
    bits = ((xu >> 1) ^ ((xu << 63) & _M64)) & _M64
    return int64(bits - (1 << 64) if bits >= 1 << 63 else bits)
