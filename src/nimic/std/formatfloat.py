"""Nim std/formatfloat — float formatting utilities."""
from __future__ import annotations
from nimic.ntypes import string, ufcs


@ufcs(string, aliases=("addFloatRoundtrip",))
def add_float_roundtrip(result: string, f: float) -> None:
    """Nim: addFloatRoundtrip — appends shortest roundtrip string representation of float f to result."""
    s = str(float(f))
    result.add(s)


addFloatRoundtrip = add_float_roundtrip

