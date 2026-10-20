# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/tinyhashes.nim
# ///
# --------------------------------------------------
# Fast&sufficient string hashing. We use custom code here so that we're independent
# from Nim's hashing implementation. Stability is more important as these checksums
# will end up in every NIF file.

from __future__ import annotations
from nimic.ntypes import *

UHash = uint32


def _mix_hash(h: UHash, val: uint32) -> UHash:  # Nim: proc `!&`(h: UHash; val: uint32): UHash
    """{.inline.}
    Mixes a hash value `h` with `val` to produce a new hash value."""
    result = h + val
    result = result + (result << u32(10))
    result = result ^ (result >> u32(6))
    return result


def _finish_hash(h: UHash) -> UHash:  # Nim: proc `!$`(h: UHash): UHash
    """{.inline.}
    Finishes the computation of the hash value."""
    result = h + (h << u32(3))
    result = result ^ (result >> u32(11))
    result = result + (result << u32(15))
    return result


def uhash(s: string) -> UHash:
    result = u32(0)
    for c in items(s): result = _mix_hash(result, uint32(c))
    result = _finish_hash(result)
    return result


if comptime(__name__ == "__main__"):
    for _s in [string(""), string("a"), string("abc"), string("nifcore"), string("(.nif24)"), utf8("ü€")]:
        echo(_s.len, " ", uhash(_s))
