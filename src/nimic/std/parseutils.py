"""Nim std/parseutils — parsing utility functions."""
from __future__ import annotations
from nimic.ntypes import (string, nint, char, ch, Tset, mut, ufcs, BiggestInt, uint64, BiggestFloat,
                          openArray)
from .strutils import IdentStartChars, IdentChars, Whitespace

_POWTENS = (
    1e0, 1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9,
    1e10, 1e11, 1e12, 1e13, 1e14, 1e15, 1e16, 1e17, 1e18, 1e19,
    1e20, 1e21, 1e22,
)
_MASK64 = (1 << 64) - 1
_IDENT_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _as_str(s: string | str | openArray) -> str:
    if isinstance(s, (str, string)):
        return str(s)
    return "".join(chr(ord(s[i])) for i in range(len(s)))


@ufcs(string, openArray, aliases=("skipWhitespace",))
def skip_whitespace(s: string | str | openArray, start: nint | int = 0) -> nint:
    """Nim: skipWhitespace — number of ASCII whitespace chars at s[start..]."""
    s_val = _as_str(s)
    idx = int(start)
    count = 0
    while idx < len(s_val) and s_val[idx] in Whitespace:
        count += 1
        idx += 1
    return nint(count)

skipWhitespace = skip_whitespace


@ufcs(string, openArray, aliases=("skipUntil",))
def skip_until(s: string | str | openArray, until: set | Tset | str, start: nint | int = 0) -> nint:
    """Nim: skipUntil — skips characters until a character in `until` is reached."""
    s_val = _as_str(s)
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


@ufcs(string, openArray, aliases=("parseIdent",))
def parse_ident(s: string | str | openArray, ident: mut@string, start: nint | int = 0) -> nint:
    """Nim: parseIdent — extracts an identifier (IdentStartChars, then IdentChars)."""
    s_val = _as_str(s)
    first = int(start)
    idx = first
    if idx < len(s_val) and ch(s_val[idx]) in IdentStartChars:
        idx += 1
        while idx < len(s_val) and ch(s_val[idx]) in IdentChars:
            idx += 1
    ident <<= string(s_val[first:idx])
    return nint(idx - first)

parseIdent = parse_ident


@ufcs(string, openArray, aliases=("parseHex",))
def parse_hex(s: string | str | openArray, number: mut@nint, start: nint | int = 0, max_len: nint | int = 0) -> nint:
    """Nim: parseHex — parses a hex integer with optional `0x`/`#` prefix and `_` separators
    from at most max_len chars (0: unlimited). Returns the chars consumed, 0 (and leaves
    `number` untouched) if no hex digit was found."""
    s_val = _as_str(s)
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


@ufcs(string, openArray, aliases=("parseBiggestInt",))
def parse_biggest_int(s: string | str | openArray, number: mut@BiggestInt, start: nint | int = 0) -> nint:
    """Nim: parseBiggestInt — an optionally signed decimal integer (`_` allowed) at `start`: the number of
    chars parsed, 0 (number untouched) if there is none; ValueError if out of BiggestInt's range."""
    text, first = _as_str(s), int(start)
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


@ufcs(string, openArray, aliases=("parseBiggestUInt",))
def parse_biggest_uint(s: string | str | openArray, number: mut@uint64, start: nint | int = 0) -> nint:
    """Nim: parseBiggestUInt — an unsigned decimal integer (`_` allowed, a leading `+`) at `start`: the number
    of chars parsed, 0 (number untouched) if there is none; ValueError for a negative number or above
    high(BiggestUInt)."""
    text, first = _as_str(s), int(start)
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


@ufcs(string, openArray, aliases=("parseBiggestFloat",))
def parse_biggest_float(s: string | str | openArray, number: mut@BiggestFloat, start: nint | int = 0) -> nint:
    """Nim: parseBiggestFloat (system/strmantle.nim nimParseBiggestFloat) — parses a float at `start` into
    `number` and returns the number of processed chars, or 0 (leaving `number` untouched) on error."""
    text = _as_str(s)[int(start):]
    n = len(text)
    i = 0
    sign = 1.0
    kdigits = 0
    fdigits = 0
    exponent = 0
    integer = 0
    frac_exponent = 0
    exp_sign = 1
    first_digit = -1
    has_sign = False

    # Sign?
    if i < n and (text[i] == "+" or text[i] == "-"):
        has_sign = True
        if text[i] == "-":
            sign = -1.0
        i += 1

    # NaN?
    if i + 2 < n and (text[i] == "N" or text[i] == "n"):
        if text[i + 1] == "A" or text[i + 1] == "a":
            if text[i + 2] == "N" or text[i + 2] == "n":
                if i + 3 >= n or text[i + 3] not in _IDENT_CHARS:
                    number <<= BiggestFloat(float("nan"))
                    return nint(i + 3)
        return nint(0)

    # Inf?
    if i + 2 < n and (text[i] == "I" or text[i] == "i"):
        if text[i + 1] == "N" or text[i + 1] == "n":
            if text[i + 2] == "F" or text[i + 2] == "f":
                if i + 3 >= n or text[i + 3] not in _IDENT_CHARS:
                    number <<= BiggestFloat(float("inf") * sign)
                    return nint(i + 3)
        return nint(0)

    if i < n and "0" <= text[i] <= "9":
        first_digit = ord(text[i]) - ord("0")
    # Integer part?
    while i < n and "0" <= text[i] <= "9":
        kdigits += 1
        integer = (integer * 10 + (ord(text[i]) - ord("0"))) & _MASK64
        i += 1
        while i < n and text[i] == "_":
            i += 1

    # Fractional part?
    if i < n and text[i] == ".":
        i += 1
        # if no integer part, Skip leading zeros
        if kdigits <= 0:
            while i < n and text[i] == "0":
                frac_exponent += 1
                i += 1
                while i < n and text[i] == "_":
                    i += 1

        if first_digit == -1 and i < n and "0" <= text[i] <= "9":
            first_digit = ord(text[i]) - ord("0")
        # get fractional part
        while i < n and "0" <= text[i] <= "9":
            fdigits += 1
            frac_exponent += 1
            integer = (integer * 10 + (ord(text[i]) - ord("0"))) & _MASK64
            i += 1
            while i < n and text[i] == "_":
                i += 1

    # if has no digits: return error
    if kdigits + fdigits <= 0 and (i == 0 or (i == 1 and has_sign)):
        return nint(0)

    if i + 1 < n and (text[i] == "e" or text[i] == "E"):
        i += 1
        if text[i] == "+" or text[i] == "-":
            if text[i] == "-":
                exp_sign = -1
            i += 1
        if i >= n or not ("0" <= text[i] <= "9"):
            return nint(0)
        while i < n and "0" <= text[i] <= "9":
            exponent = exponent * 10 + (ord(text[i]) - ord("0"))
            i += 1
            while i < n and text[i] == "_":
                i += 1

    real_exponent = exp_sign * exponent - frac_exponent
    exp_negative = real_exponent < 0
    abs_exponent = abs(real_exponent)

    # if exponent greater than can be represented: +/- zero or infinity
    if abs_exponent > 999:
        if integer == 0:
            number <<= BiggestFloat(0.0)
        elif exp_negative:
            number <<= BiggestFloat(0.0 * sign)
        else:
            number <<= BiggestFloat(float("inf") * sign)
        return nint(i)

    # if integer is representable in 53 bits: fast path
    # max fast path integer is 1<<53 - 1 or 8999999999999999 (16 digits)
    digits = kdigits + fdigits
    if digits <= 15 or (digits <= 16 and first_digit <= 8):
        # max float power of ten with set bits above the 53th bit is 10^22
        if abs_exponent <= 22:
            if exp_negative:
                number <<= BiggestFloat(sign * float(integer) / _POWTENS[abs_exponent])
            else:
                number <<= BiggestFloat(sign * float(integer) * _POWTENS[abs_exponent])
            return nint(i)

        # if exponent is greater try to fit extra exponent above 22 by multiplying
        # integer part if there is space left.
        slop = 15 - kdigits - fdigits
        if abs_exponent <= 22 + slop and not exp_negative:
            number <<= BiggestFloat(sign * float(integer) * _POWTENS[slop] * _POWTENS[abs_exponent - slop])
            return nint(i)

    # if failed: slow path with strtod.
    maxlen = 499 - len("e+000")  # reserve enough space for exponent (t: array[500, char])
    t: list[str] = []
    end_pos = i
    i = 0
    # re-parse without error checking, any error should be handled by the code above.
    if i < end_pos and text[i] == ".":
        i += 1
    while i < end_pos and text[i] in "0123456789+-":
        if len(t) < maxlen:
            t.append(text[i])
        i += 1
        while i < end_pos and (text[i] == "." or text[i] == "_"):
            i += 1

    # insert exponent
    t.append("E")
    t.append("-" if exp_negative else "+")
    # insert adjusted exponent
    t.append(chr(ord("0") + (abs_exponent // 100) % 10))
    t.append(chr(ord("0") + (abs_exponent // 10) % 10))
    t.append(chr(ord("0") + abs_exponent % 10))
    number <<= BiggestFloat(float("".join(t)))
    return nint(end_pos)


parseBiggestInt = parse_biggest_int
parseBiggestUInt = parse_biggest_uint
parseBiggestFloat = parse_biggest_float
