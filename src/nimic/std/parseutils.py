"""Nim std/parseutils — parsing utility functions."""
from __future__ import annotations
from nimic.ntypes import string, nint, char, ch, Tset, mut, ufcs
from .strutils import IdentStartChars, IdentChars, Whitespace


@ufcs(string, aliases=("skipWhitespace",))
def skip_whitespace(s: string | str, start: nint | int = 0) -> nint:
    """Nim: skipWhitespace — number of ASCII whitespace chars at s[start..]."""
    s_val = str(s)
    idx = int(start)
    count = 0
    while idx < len(s_val) and s_val[idx] in Whitespace:
        count += 1
        idx += 1
    return nint(count)

skipWhitespace = skip_whitespace


@ufcs(string, aliases=("skipUntil",))
def skip_until(s: string | str, until: set | Tset | str, start: nint | int = 0) -> nint:
    """Nim: skipUntil — skips characters until a character in `until` is reached."""
    s_val = str(s)
    idx = int(start)
    count = 0
    while idx < len(s_val):
        c = ch(s_val[idx])
        if c in until:
            break
        count += 1
        idx += 1
    return nint(count)

skipUntil = skip_until


@ufcs(string, aliases=("parseIdent",))
def parse_ident(s: string | str, ident: mut@string, start: nint | int = 0) -> nint:
    """Nim: parseIdent — extracts an identifier (IdentStartChars, then IdentChars)."""
    s_val = str(s)
    first = int(start)
    idx = first
    if idx < len(s_val) and ch(s_val[idx]) in IdentStartChars:
        idx += 1
        while idx < len(s_val) and ch(s_val[idx]) in IdentChars:
            idx += 1
    ident <<= string(s_val[first:idx])
    return nint(idx - first)

parseIdent = parse_ident


@ufcs(string, aliases=("parseHex",))
def parse_hex(s: string | str, number: mut@nint, start: nint | int = 0, max_len: nint | int = 0) -> nint:
    """Nim: parseHex — parses a hex integer with optional `0x`/`#` prefix and `_` separators
    from at most max_len chars (0: unlimited). Returns the chars consumed, 0 (and leaves
    `number` untouched) if no hex digit was found."""
    s_val = str(s)
    first = int(start)
    last = len(s_val) if int(max_len) == 0 else min(first + int(max_len), len(s_val))
    i = first
    if i + 1 < last and s_val[i] == "0" and s_val[i + 1] in "xX":
        i += 2
    elif i < last and s_val[i] == "#":
        i += 1
    output = 0
    found_digit = False
    while i < last:
        c = s_val[i]
        if c in "0123456789abcdefABCDEF":
            output = (output << 4) | int(c, 16)
            found_digit = True
        elif c != "_":
            break
        i += 1
    if not found_digit:
        return nint(0)
    number <<= nint(output)
    return nint(i - first)

parseHex = parse_hex
