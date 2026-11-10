"""Nim std/sequtils (nimony's lib/std/sequtils) — the routines converted modules use: `insert`."""
from __future__ import annotations
from nimic.ntypes import nint, seq, ufcs
from nimic.ntypesystem import _n_value_copy

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'insert'
]


@ufcs(seq)
def insert(dest: seq, src, pos: nint = 0) -> None:
    """Nim: insert(dest, src, pos = 0) — inserts copies of the elements of `src` (an openArray) into `dest` at
    `pos` (at most dest.len), in place: the tail moves up by src.len."""
    items = [_n_value_copy(x) for x in src]  # taken first: `src` may be `dest` itself
    n = len(items)
    if n == 0:
        return
    old_len = len(dest)
    at = min(int(pos), old_len)
    dest.set_len(old_len + n)
    for i in range(old_len - 1, at - 1, -1):  # every slot moved from is written again below
        dest[i + n] = dest[i]
    for k, x in enumerate(items):
        dest[at + k] = x
