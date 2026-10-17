"""Nim std/private/miscdollars."""
from __future__ import annotations
from nimic.ntypes import string


def toLocation(result: string, file: string, line: int, col: int) -> None:
    """Nim: toLocation — appends `file(line, col)` to result (a var string); the column only when > 0,
    the parentheses only when line > 0."""
    result.add(file)
    if int(line) > 0:
        result.add("(")
        result.add(str(int(line)))
        if int(col) > 0:
            result.add(", ")
            result.add(str(int(col)))
        result.add(")")
