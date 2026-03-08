"""Nim std/strutils — string utility functions (int_to_str, etc.)."""
def int_to_str(i: int, minchars: int = 1):
    return str(i).zfill(minchars)