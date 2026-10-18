"""Nim std/formatfloat — float formatting utilities."""
from __future__ import annotations
from nimic.ntypes import string, ufcs


@ufcs(string, aliases=("addFloatRoundtrip",))
def add_float_roundtrip(result: string, f: float) -> None:
    """Nim: addFloatRoundtrip — appends shortest roundtrip string representation of float f to result."""
    s = str(float(f))
    result.add(s)


addFloatRoundtrip = add_float_roundtrip



@ufcs(string, aliases=("addFloat",))
def add_float(result: string, x: float) -> None:
    """Nim: addFloat — appends the string representation of x (the shortest round trip, as `$x`)."""
    add_float_roundtrip(result, x)


addFloat = add_float
