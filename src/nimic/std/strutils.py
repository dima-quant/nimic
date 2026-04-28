"""Nim std/strutils — string utility functions."""


def int_to_str(i: int, minchars: int = 1):
    return str(i).zfill(minchars)


def parse_int(s: str) -> int:
    """Nim: parseInt — parse a string to integer."""
    return int(s.strip())