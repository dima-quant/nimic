"""Nim std/strutils — string utility functions (intToStr, etc.)."""
def intToStr(i: int, minchars: int = 1):
    return str(i).zfill(minchars)