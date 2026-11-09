"""Nim std/formatfloat — float formatting utilities."""
from __future__ import annotations
from nimic.ntypes import float32, float64, string, ufcs

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'add_float', 'add_float_roundtrip', 'addFloat', 'addFloatRoundtrip'
]


@ufcs(string, aliases=("addFloatRoundtrip",))
def add_float_roundtrip(result: string, f: float) -> None:
    """Nim: addFloatRoundtrip — appends the shortest round-trip representation of f, as Nim's `$` writes it
    (NFloat.__str__). Nim overloads it for `float | float32`: a float32 keeps its own digits, any other float is a
    float64."""
    result.add(str(f if isinstance(f, float32) else float64(f)))


addFloatRoundtrip = add_float_roundtrip



@ufcs(string, aliases=("addFloat",))
def add_float(result: string, x: float) -> None:
    """Nim: addFloat — appends the string representation of x (the shortest round trip, as `$x`)."""
    add_float_roundtrip(result, x)


addFloat = add_float
