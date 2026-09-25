"""Nim std/strutils — string utility functions."""
from __future__ import annotations
from nimic.ntypes import dispatch, string, char, Tset


def int_to_str(i: int, minchars: int = 1):
    return str(i).zfill(minchars)


def parse_int(s: str | string) -> int:
    """Nim: parseInt — parse a string to integer."""
    return int(str(s).strip())

parseInt = parse_int


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


def nimIdentNormalize(s: string | str) -> string:
    """Nim: nimIdentNormalize — normalize identifier (lowercase and strip underscores)."""
    s_val = str(s)
    res = [c.lower() for c in s_val if c != '_']
    return string("".join(res))

def find(s: string | str, sub: set | Tset | char | string | str, start: int = 0, last: int = 0) -> int:
    s_str = str(s)
    end_pos = len(s_str) if last <= 0 else last + 1
    if isinstance(sub, (set, frozenset, Tset)):
        char_set = {str(c) for c in sub}
        for i in range(start, min(len(s_str), end_pos)):
            if s_str[i] in char_set:
                return i
        return -1
    else:
        sub_str = str(sub)
        return s_str.find(sub_str, start, end_pos)

def repeat(s: str | string | char, count: int) -> string:
    """Nim: repeat — returns a string of count copies of s."""
    if isinstance(s, char):
        return string(s.val * count)
    return string(str(s) * count)


def to_octal(c: char | str | int) -> string:
    """Nim: toOctal — converts a character to its 3-digit octal representation."""
    val = ord(c)
    return string(f"{val:03o}")

toOctal = to_octal


def spaces(n: int) -> string:
    """Nim: spaces — returns a string of n spaces."""
    return repeat(' ', n)