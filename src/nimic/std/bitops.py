"""Nim std/bitops — bit manipulation of the integer types (the procs used by the converted compiler)."""
from __future__ import annotations
from nimic.ntypes import nint


def fast_log2(x) -> nint:
    """Nim: fastLog2 — floor(log2(x)) of a positive integer; -1 for 0 (undefined in Nim)."""
    v = int(x)
    if v < 0:
        v &= (1 << (8 * x._n_sizeof())) - 1  # the bits of a signed value, as Nim reads them
    return nint(v.bit_length() - 1)


fastLog2 = fast_log2
