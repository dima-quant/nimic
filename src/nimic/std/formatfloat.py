"""Nim std/formatfloat — float formatting utilities."""
from __future__ import annotations
from nimic.ntypes import string


def add_float_roundtrip(result: string, f: float) -> None:
    """Nim: addFloatRoundtrip — appends shortest roundtrip string representation of float f to result."""
    s = str(float(f))
    result.add(s)


addFloatRoundtrip = add_float_roundtrip

# Bind onto string for UFCS in Python
string.addFloatRoundtrip = add_float_roundtrip
