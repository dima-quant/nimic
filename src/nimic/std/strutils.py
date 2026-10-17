"""Nim std/strutils — string utility functions."""
from __future__ import annotations
from nimic.ntypes import dispatch, ufcs, string, char, ch, Tset, nint, NIntEnum, auto
from nimic.ntypesystem import _n_addf

# Nim strutils.Whitespace (ASCII only: nimic strings are bytes)
Whitespace = " \t\v\r\n\f"


def int_to_str(i: int, minchars: int = 1):
    return str(i).zfill(minchars)


def parse_int(s: str | string) -> int:
    """Nim: parseInt — parse a string to integer."""
    return int(str(s).strip())

parseInt = parse_int


def normalize(s: str) -> str:
    """Nim: normalize — normalize string (remove underscores and to lowercase)."""
    return _n_lower_ascii(str(s).replace("_", ""))

def cmpIgnoreStyle(a: str, b: str) -> int:
    a_norm = normalize(str(a))
    b_norm = normalize(str(b))
    if a_norm == b_norm: return 0
    return -1 if a_norm < b_norm else 1

def _n_lower_ascii(s: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in s)


def isUpperAscii(c: char) -> bool:
    """Nim: isUpperAscii — c in 'A'..'Z'."""
    return "A" <= str(c) <= "Z"


def isLowerAscii(c: char) -> bool:
    """Nim: isLowerAscii — c in 'a'..'z'."""
    return "a" <= str(c) <= "z"


def toLowerAscii(c):
    """Nim: toLowerAscii — lowercases only A..Z; a char gives a char, anything else a string."""
    if isinstance(c, int):
        c = char(c)
    if isinstance(c, char):
        return char(_n_lower_ascii(c))
    return string(_n_lower_ascii(str(c)))


@ufcs(string)
@dispatch
def startsWith(s: string, prefix: string) -> bool:
    return str(s).startswith(str(prefix))

@ufcs(string)
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
    """Nim: nimIdentNormalize — keep the first char, lowercase (ASCII) the rest and drop '_'."""
    s_val = str(s)
    if not s_val:
        return string("")
    return string(s_val[0] + _n_lower_ascii(s_val[1:].replace("_", "")))

def find(s: string | str, sub: set | Tset | char | string | str, start: int = 0, last: int = -1) -> nint:
    """Nim: find — first index of sub in s[start..last] (last = -1: to the end), else -1."""
    s_str = str(s)
    end_pos = len(s_str) if last < 0 else last + 1
    if isinstance(sub, (set, frozenset, Tset)):
        char_set = {str(c) for c in sub}
        for i in range(start, min(len(s_str), end_pos)):
            if s_str[i] in char_set:
                return nint(i)
        return nint(-1)
    else:
        sub_str = str(sub)
        return nint(s_str.find(sub_str, start, end_pos))

def repeat(s: str | string | char, count: int) -> string:
    """Nim: repeat — returns a string of count copies of s."""
    return string(str(s) * int(count))


def to_octal(c: char | str | int) -> string:
    """Nim: toOctal — converts a character to its 3-digit octal representation."""
    val = ord(c)
    return string(f"{val:03o}")

toOctal = to_octal


def spaces(n: int) -> string:
    """Nim: spaces — returns a string of n spaces."""
    return repeat(' ', n)


def to_hex(n: int, length: int = 0) -> string:
    """Nim: toHex — converts integer to uppercase hexadecimal representation."""
    h = f"{int(n):X}"
    if length > len(h):
        h = h.zfill(length)
    return string(h)

toHex = to_hex


def strip(s: string | str, leading: bool = True, trailing: bool = True,
          chars: set | Tset | str = Whitespace) -> string:
    """Nim: strip — strip `chars` (default: ASCII Whitespace) from the ends of s."""
    s_str = str(s)
    char_set = "".join(str(c) for c in chars)
    if leading:
        s_str = s_str.lstrip(char_set)
    if trailing:
        s_str = s_str.rstrip(char_set)
    return string(s_str)


def r_find(s: string | str, sub: str | string | char, start: int = 0, last: int = -1) -> nint:
    """Nim: rfind — last index of sub in s[start..last] (last = -1: to the end), else -1."""
    s_str = str(s)
    end_pos = len(s_str) if last < 0 else last + 1
    return nint(s_str.rfind(str(sub), start, end_pos))

rfind = r_find


@ufcs(string, aliases=("splitLines",))
def split_lines(s: string | str) -> list[string]:
    """Nim: splitLines — split string into lines."""
    s_val = str(s)
    lines = []
    i = 0
    start = 0
    while i < len(s_val):
        if s_val[i] == '\r':
            lines.append(string(s_val[start:i]))
            if i + 1 < len(s_val) and s_val[i + 1] == '\n':
                i += 1
            i += 1
            start = i
        elif s_val[i] == '\n':
            lines.append(string(s_val[start:i]))
            i += 1
            start = i
        else:
            i += 1
    if start <= len(s_val):
        lines.append(string(s_val[start:]))
    return lines

splitLines = split_lines


IdentStartChars = Tset[char]({ch(chr(c)) for c in range(ord('a'), ord('z') + 1)} |
                             {ch(chr(c)) for c in range(ord('A'), ord('Z') + 1)} |
                             {ch('_')})

IdentChars = Tset[char](set(IdentStartChars) |
                        {ch(chr(c)) for c in range(ord('0'), ord('9') + 1)})



# --- format strings (Nim strutils.addf, `%`, format) ---
@dispatch
def addf(s: string, formatstr: string, *a: varargs[string, str]) -> None:
    """Nim: addf — `s.add(formatstr % a)`."""
    s.add(string(_n_addf(str(formatstr), list(a))))


@dispatch
def format(formatstr: string, *a: varargs[string, str]) -> string:
    """Nim: format — `formatstr % a` with `$` applied to each argument (an overload of times.format)."""
    return string(_n_addf(str(formatstr), list(a)))


# --- floating point formatting ---
class FloatFormatMode(NIntEnum):
    """Nim: FloatFormatMode — the different modes of floating point formatting."""
    ffDefault = 0  # use the shorter floating point notation
    ffDecimal = auto()  # use decimal floating point notation
    ffScientific = auto()  # use scientific notation (using `e` character)


ffDefault = FloatFormatMode.ffDefault
ffDecimal = FloatFormatMode.ffDecimal
ffScientific = FloatFormatMode.ffScientific


def formatBiggestFloat(f: float, format: FloatFormatMode = ffDefault, precision: int = 16,
                       decimalSep: char = ch(".")) -> string:
    """Nim: formatBiggestFloat — C snprintf with %#.*g / %#.*f / %#.*e (precision -1: %g / %f / %e)."""
    code = "gfe"[int(format)]
    text = (f"%#.*{code}" % (int(precision), float(f))) if int(precision) >= 0 else (f"%{code}" % float(f))
    return string("".join(str(decimalSep) if c in ".," else c for c in text))


def formatFloat(f: float, format: FloatFormatMode = ffDefault, precision: int = 16,
                decimalSep: char = ch(".")) -> string:
    """Nim: formatFloat."""
    return formatBiggestFloat(f, format, precision, decimalSep)


def trimZeros(x: string, decimalSep: char = ch(".")) -> None:
    """Nim: trimZeros — trim trailing zeros from a formatted float `x` (a var string)."""
    text = str(x)
    sPos = text.find(str(decimalSep))
    if sPos >= 0:
        last = text.find("e", sPos)
        last = last - 1 if last >= 0 else len(text) - 1
        pos = last
        while pos >= 0 and text[pos] == "0":
            pos -= 1
        if pos > sPos:
            pos += 1
        if last >= pos:
            x <<= text[:pos] + text[last + 1:]


class BinaryPrefixMode(NIntEnum):
    """Nim: BinaryPrefixMode — the different names for binary prefixes."""
    bpIEC = 0  # use the IEC/ISO standard prefixes such as kibi
    bpColloquial = auto()  # use the colloquial kilo, mega etc


bpIEC = BinaryPrefixMode.bpIEC
bpColloquial = BinaryPrefixMode.bpColloquial


def formatSize(bytes: int, decimalSep: char = ch("."), prefix: BinaryPrefixMode = bpIEC,
               includeSpace: bool = False) -> string:
    """Nim: formatSize — rounds and formats `bytes` (1024 -> 1KiB)."""
    iecPrefixes = ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi", "Yi"]
    collPrefixes = ["", "k", "M", "G", "T", "P", "E", "Z", "Y"]
    b = int(bytes)
    xb = b
    matchedIndex = 0
    prefixes = collPrefixes if prefix == bpColloquial else iecPrefixes
    for index in range(1, len(prefixes)):
        lastXb = xb
        xb = int(b / (1 << (index * 10))) if b < 0 else b // (1 << (index * 10))
        matchedIndex = index
        if xb == 0:
            xb = lastXb
            matchedIndex = index - 1
            break
    fbytes = float(b) / float(1 << (matchedIndex * 10))
    result = formatFloat(fbytes, format=ffDecimal, precision=3, decimalSep=decimalSep)
    trimZeros(result, decimalSep)
    if includeSpace:
        result.add(" ")
    result.add(prefixes[matchedIndex])
    result.add("B")
    return result
