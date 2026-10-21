from __future__ import annotations
import builtins
import struct

from nimic.ntypesystem import (NIntEnum, NStrEnum, SomeFloat, SomeInteger, _n_item_type, char, cstring, dispatch,
                               nord, openArray, string)


class Hash(int):
    pass


_MASK64 = (1 << 64) - 1


@dispatch
def hash(x: SomeInteger) -> Hash:
    """Nim hash[T: Ordinal|enum](x) = hashWangYi1(uint64(ord(x)))."""
    return _hash_wang_yi1(int(x))


@dispatch
def hash(x: char) -> Hash:
    return _hash_wang_yi1(ord(x))


@dispatch
def hash(x: bool) -> Hash:
    return _hash_wang_yi1(int(x))


@dispatch
def hash(x: NIntEnum) -> Hash:
    return _hash_wang_yi1(nord(x))


@dispatch
def hash(x: NStrEnum) -> Hash:
    return _hash_wang_yi1(nord(x))


@dispatch
def hash(x: SomeFloat) -> Hash:
    """Nim hash(x: float) = hashWangYi1 of the bits of x + 0.0 (so -0.0 hashes as 0.0)."""
    return _hash_wang_yi1(struct.unpack("<Q", struct.pack("<d", float(x) + 0.0))[0])


@dispatch
def hash(x: string) -> Hash:
    """Nim hash(x: string) = hashFarm of its bytes."""
    return _to_hash(_hash_farm(_bytes_of(x)))


@dispatch
def hash(x: cstring) -> Hash:
    return _to_hash(_hash_farm(_bytes_of(x)))


@dispatch
def hash(x: str) -> Hash:
    return _to_hash(_hash_farm(_bytes_of(string(x))))


@dispatch
def hash(x: openArray) -> Hash:
    """Nim hash[A](x: openArray[A]): hashFarm of the bytes for chars, else the elements' hashes mixed."""
    if _n_item_type(type(x)) is char:
        return _to_hash(_hash_farm(bytes(ord(c) for c in x)))
    return _hash_items(x)


@dispatch
def hash(x: tuple) -> Hash:
    """Nim hash[T: tuple](x): the fields' hashes mixed."""
    return _hash_items(x)


@dispatch
def hash(x: object) -> Hash:
    return Hash(builtins.hash(x))


def _to_hash(u: int) -> Hash:
    """A 64-bit unsigned bit pattern as Nim's (signed) Hash."""
    u &= _MASK64
    return Hash(u - (1 << 64) if u >> 63 else u)


def _hash_items(items) -> Hash:
    h = 0
    for item in items:
        h = mix_hash(h, hash(item))
    return finish_hash(h)


def _bytes_of(s) -> bytes:
    """The bytes of a nimic string (Latin-1: one char per byte)."""
    return str(s).encode("latin-1")


def _hi_xor_lo(a: int, b: int) -> int:
    """The high and low 64 bits of the 128-bit product a * b, xor-ed (Nim hiXorLo)."""
    r = a * b
    return ((r >> 64) ^ r) & _MASK64


def _hash_wang_yi1(x: int) -> Hash:
    """Nim hashWangYi1(uint64(x)), the hash of the ordinal types."""
    p0, p1, p58 = 0xa0761d6478bd642f, 0xe7037ed1a0b428db, 0xeb44accab455d165 ^ 8
    return _to_hash(_hi_xor_lo(_hi_xor_lo(p0, (x & _MASK64) ^ p1), p58))


# Nim's hashFarm (std/hashes, Google's farmhash na / uo, 64 bits) on bytes
_K0, _K1, _K2 = 0xc3a5c85c97cb3127, 0xb492b66fbe98f273, 0x9ae16a3b2f90404f


def _load8(s: bytes, o: int = 0) -> int:
    return int.from_bytes(s[o:o + 8], "little")


def _load4(s: bytes, o: int = 0) -> int:
    return int.from_bytes(s[o:o + 4], "little")


def _shift_mix(v: int) -> int:
    return v ^ (v >> 47)


def _rot_r(v: int, bits: int) -> int:
    return ((v >> bits) | (v << (64 - bits))) & _MASK64


def _len16(u: int, v: int, mul: int) -> int:
    a = ((u ^ v) * mul) & _MASK64
    a ^= a >> 47
    b = ((v ^ a) * mul) & _MASK64
    b ^= b >> 47
    return (b * mul) & _MASK64


def _len0_16(s: bytes) -> int:
    n = len(s)
    if n >= 8:
        mul = _K2 + 2 * n
        a = (_load8(s) + _K2) & _MASK64
        b = _load8(s, n - 8)
        c = (_rot_r(b, 37) * mul + a) & _MASK64
        d = ((_rot_r(a, 25) + b) * mul) & _MASK64
        return _len16(c, d, mul)
    if n >= 4:
        mul = _K2 + 2 * n
        a = _load4(s)
        return _len16((n + (a << 3)) & _MASK64, _load4(s, n - 4), mul)
    if n > 0:
        a, b, c = s[0], s[n >> 1], s[n - 1]
        y = a + (b << 8)
        z = n + (c << 2)
        return (_shift_mix(((y * _K2) ^ (z * _K0)) & _MASK64) * _K2) & _MASK64
    return _K2


def _len17_32(s: bytes) -> int:
    n = len(s)
    mul = _K2 + 2 * n
    a = (_load8(s) * _K1) & _MASK64
    b = _load8(s, 8)
    c = (_load8(s, n - 8) * mul) & _MASK64
    d = (_load8(s, n - 16) * _K2) & _MASK64
    return _len16((_rot_r((a + b) & _MASK64, 43) + _rot_r(c, 30) + d) & _MASK64,
                  (a + _rot_r((b + _K2) & _MASK64, 18) + c) & _MASK64, mul)


def _len33_64(s: bytes) -> int:
    n = len(s)
    mul = _K2 + 2 * n
    a = (_load8(s) * _K2) & _MASK64
    b = _load8(s, 8)
    c = (_load8(s, n - 8) * mul) & _MASK64
    d = (_load8(s, n - 16) * _K2) & _MASK64
    y = (_rot_r((a + b) & _MASK64, 43) + _rot_r(c, 30) + d) & _MASK64
    z = _len16(y, (a + _rot_r((b + _K2) & _MASK64, 18) + c) & _MASK64, mul)
    e = (_load8(s, 16) * mul) & _MASK64
    f = _load8(s, 24)
    g = ((y + _load8(s, n - 32)) * mul) & _MASK64
    h = ((z + _load8(s, n - 24)) * mul) & _MASK64
    return _len16((_rot_r((e + f) & _MASK64, 43) + _rot_r(g, 30) + h) & _MASK64,
                  (e + _rot_r((f + a) & _MASK64, 18) + g) & _MASK64, mul)


def _weak_len32_with_seeds(s: bytes, o: int, a: int, b: int) -> tuple[int, int]:
    w, x, y, z = _load8(s, o), _load8(s, o + 8), _load8(s, o + 16), _load8(s, o + 24)
    a = (a + w) & _MASK64
    b = _rot_r((b + a + z) & _MASK64, 21)
    c = a
    a = (a + x + y) & _MASK64
    b = (b + _rot_r(a, 44)) & _MASK64
    return (a + z) & _MASK64, (b + c) & _MASK64


def _hash_farm(s: bytes) -> int:
    n = len(s)
    if n <= 16:
        return _len0_16(s)
    if n <= 32:
        return _len17_32(s)
    if n <= 64:
        return _len33_64(s)
    seed = 81
    o = 0
    x = seed
    y = (seed * _K1 + 113) & _MASK64
    z = (_shift_mix((y * _K2 + 113) & _MASK64) * _K2) & _MASK64
    v = w = (0, 0)
    x = (x * _K2 + _load8(s)) & _MASK64
    eos = ((n - 1) // 64) * 64
    last64 = eos + ((n - 1) & 63) - 63
    while True:
        x = (_rot_r((x + y + v[0] + _load8(s, o + 8)) & _MASK64, 37) * _K1) & _MASK64
        y = (_rot_r((y + v[1] + _load8(s, o + 48)) & _MASK64, 42) * _K1) & _MASK64
        x ^= w[1]
        y = (y + v[0] + _load8(s, o + 40)) & _MASK64
        z = (_rot_r((z + w[0]) & _MASK64, 33) * _K1) & _MASK64
        v = _weak_len32_with_seeds(s, o, (v[1] * _K1) & _MASK64, (x + w[0]) & _MASK64)
        w = _weak_len32_with_seeds(s, o + 32, (z + w[1]) & _MASK64, (y + _load8(s, o + 16)) & _MASK64)
        z, x = x, z
        o += 64
        if o == eos:
            break
    mul = (_K1 + ((z & 0xff) << 1)) & _MASK64
    o = last64
    w = ((w[0] + ((n - 1) & 63)) & _MASK64, w[1])
    v = ((v[0] + w[0]) & _MASK64, v[1])
    w = ((w[0] + v[0]) & _MASK64, w[1])
    x = (_rot_r((x + y + v[0] + _load8(s, o + 8)) & _MASK64, 37) * mul) & _MASK64
    y = (_rot_r((y + v[1] + _load8(s, o + 48)) & _MASK64, 42) * mul) & _MASK64
    x ^= (w[1] * 9) & _MASK64
    y = (y + v[0] * 9 + _load8(s, o + 40)) & _MASK64
    z = (_rot_r((z + w[0]) & _MASK64, 33) * mul) & _MASK64
    v = _weak_len32_with_seeds(s, o, (v[1] * mul) & _MASK64, (x + w[0]) & _MASK64)
    w = _weak_len32_with_seeds(s, o + 32, (z + w[1]) & _MASK64, (y + _load8(s, o + 16)) & _MASK64)
    z, x = x, z
    return _len16((_len16(v[0], w[0], mul) + _shift_mix(y) * _K0 + z) & _MASK64,
                  (_len16(v[1], w[1], mul) + x) & _MASK64, mul)


def mix_hash(h, val) -> Hash:
    """Nim: h !& val — mixes a hash value `h` with `val` (unsigned 64-bit arithmetic, as Nim)."""
    res = (int(h) + int(val)) & _MASK64
    res = (res + (res << 10)) & _MASK64
    res ^= res >> 6
    return _to_hash(res)


def finish_hash(h) -> Hash:
    """Nim: !$h — finishes the computation of the hash value."""
    u = int(h) & _MASK64
    res = (u + (u << 3)) & _MASK64
    res ^= res >> 11
    res = (res + (res << 15)) & _MASK64
    return _to_hash(res)


def hashIgnoreStyle(x) -> Hash:
    """Nim: hashIgnoreStyle(x) — Nim's algorithm: '_' skipped, 'A'..'Z' lowered, mixed with mix_hash."""
    h = 0
    for c in str(x):
        if c == "_":
            continue
        if "A" <= c <= "Z":
            c = chr(ord(c) + (ord("a") - ord("A")))
        h = mix_hash(h, ord(c))
    return finish_hash(h)


hash_ignore_style = hashIgnoreStyle
