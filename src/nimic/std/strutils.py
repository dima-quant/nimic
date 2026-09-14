"""Nim std/strutils — string utility functions."""
from __future__ import annotations
from nimic.ntypes import dispatch, string, char


def int_to_str(i: int, minchars: int = 1):
    return str(i).zfill(minchars)


def parse_int(s: str) -> int:
    """Nim: parseInt — parse a string to integer."""
    return int(s.strip())


def normalize(s: str) -> str:
    """Nim: normalize — normalize string (remove underscores and to lowercase)."""
    return str(s).replace("_", "").lower()

def cmpIgnoreStyle(a: str, b: str) -> int:
    a_norm = normalize(str(a))
    b_norm = normalize(str(b))
    if a_norm == b_norm: return 0
    return -1 if a_norm < b_norm else 1

def toLowerAscii(c) -> str:
    if isinstance(c, str):
        return c.lower()
    return chr(c).lower() if isinstance(c, int) else str(c).lower()


@dispatch
def startsWith(s: string, prefix: string) -> bool:
    return str(s).startswith(str(prefix))

@dispatch
def endsWith(s: string, suffix: string) -> bool:
    return str(s).endswith(str(suffix))


@dispatch
def continuesWith(s: string, substr: string, start: int) -> bool:
    """Nim: continuesWith — check if s[start..] starts with substr."""
    return str(s)[start:].startswith(str(substr))


@dispatch
def replace(s: string, sub: string, by: string) -> string:
    """Nim: replace — replace all occurrences of sub with by."""
    return string(str(s).replace(str(sub), str(by)))

@dispatch
def replace(s: string, sub: char, by: char) -> string:
    """Nim: replace — replace all occurrences of char sub with char by."""
    return string(str(s).replace(str(sub), str(by)))