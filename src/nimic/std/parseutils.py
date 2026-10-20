"""Nim std/parseutils — parsing utility functions."""
from __future__ import annotations
from nimic.ntypes import string, nint, char, ch, Tset, mut, ufcs, BiggestInt, uint64
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


def _parse_digits(s: str, i: int) -> tuple[int, int]:
    """Decimal digits at s[i:] with `_` ignored after a digit (Nim's rawParse*): (value, end index)."""
    value = 0
    while i < len(s) and s[i] in "0123456789":
        value = value * 10 + ord(s[i]) - ord("0")
        i += 1
        while i < len(s) and s[i] == "_":
            i += 1
    return value, i


@ufcs(string, aliases=("parseBiggestInt",))
def parse_biggest_int(s: string | str, number: mut@BiggestInt, start: nint | int = 0) -> nint:
    """Nim: parseBiggestInt — an optionally signed decimal integer (`_` allowed) at `start`: the number of
    chars parsed, 0 (number untouched) if there is none; ValueError if out of BiggestInt's range."""
    text, first = str(s), int(start)
    i, sign = first, 1
    if i < len(text) and text[i] in "+-":
        sign = -1 if text[i] == "-" else 1
        i += 1
    if not (i < len(text) and text[i] in "0123456789"):
        return nint(0)
    value, i = _parse_digits(text, i)
    value *= sign
    if not -(1 << 63) <= value < (1 << 63):
        raise ValueError("Parsed integer outside of valid range")
    number <<= BiggestInt(value)
    return nint(i - first)


@ufcs(string, aliases=("parseBiggestUInt",))
def parse_biggest_uint(s: string | str, number: mut@uint64, start: nint | int = 0) -> nint:
    """Nim: parseBiggestUInt — an unsigned decimal integer (`_` allowed, a leading `+`) at `start`: the number
    of chars parsed, 0 (number untouched) if there is none; ValueError for a negative number or above
    high(BiggestUInt)."""
    text, first = str(s), int(start)
    i = first
    if i + 1 < len(text) and text[i] == "-" and text[i + 1] in "0123456789":
        raise ValueError("Parsed integer outside of valid range")
    if i < len(text) and text[i] == "+":
        i += 1
    if not (i < len(text) and text[i] in "0123456789"):
        return nint(0)
    value, i = _parse_digits(text, i)
    if value >= 1 << 64:
        raise ValueError("Parsed integer outside of valid range")
    number <<= uint64(value)
    return nint(i - first)


parseBiggestInt = parse_biggest_int
parseBiggestUInt = parse_biggest_uint
