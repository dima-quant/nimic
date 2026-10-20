from __future__ import annotations
import builtins


from nimic.ntypesystem import dispatch


class Hash(int):
    pass


@dispatch
def hash(x: tuple) -> Hash:
    return Hash(builtins.hash(x))


@dispatch
def hash(x: str) -> Hash:
    return Hash(builtins.hash(x))


@dispatch
def hash(x: int) -> Hash:
    return Hash(builtins.hash(x))


@dispatch
def hash(x: object) -> Hash:
    return Hash(builtins.hash(x))


_MASK64 = (1 << 64) - 1


def _to_hash(u: int) -> Hash:
    """A 64-bit unsigned bit pattern as Nim's (signed) Hash."""
    u &= _MASK64
    return Hash(u - (1 << 64) if u >> 63 else u)


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
