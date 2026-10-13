"""Nim std/strscans — scanf implementation."""
from __future__ import annotations
import re
from typing import Any
from nimic.ntypes import string, nint, ufcs

# Nim scanf matchers: `$x` -> (regex, conversion or None when nothing is captured)
_MATCHERS = {
    "i": (r"([-+]?\d+)", lambda v: nint(int(v))),
    "f": (r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", float),
    "w": (r"([A-Za-z_][A-Za-z0-9_]*)", string),
    "s": (r"[ \t\v\r\n\f]*", None),  # skips optional whitespace, consumes no argument
    ".": (r"$", None),               # end of input
    "$": (re.escape("$"), None),
}


@ufcs(string)
def scanf(input_str: string | str, pattern: string | str, *args: Any) -> bool:
    """Nim: scanf — matches a prefix of input_str against pattern ($i, $f, $w, $s, $+, $*, $., $$)
    and assigns each captured value to the next `var` argument. Returns false on no match."""
    pat = str(pattern)
    regex_parts = []
    converters = []
    i = 0
    while i < len(pat):
        if pat[i] == "$" and i + 1 < len(pat):
            kind = pat[i + 1]
            i += 2
            if kind in "+*":
                # until the token following it; at the end of the pattern: the rest of the input
                quant = "+" if kind == "+" else "*"
                regex_parts.append(f"(.{quant}?)" if i < len(pat) else f"(.{quant})")
                converters.append(string)
            elif kind in _MATCHERS:
                regex, conv = _MATCHERS[kind]
                regex_parts.append(regex)
                if conv is not None:
                    converters.append(conv)
            else:
                raise ValueError(f"scanf: unsupported matcher ${kind} in pattern {pat!r}")
        else:
            j = pat.find("$", i + 1) if pat[i] == "$" else pat.find("$", i)
            j = len(pat) if j == -1 else j
            regex_parts.append(re.escape(pat[i:j]))
            i = j
    m = re.match("".join(regex_parts), str(input_str), re.DOTALL)
    if not m:
        return False
    for arg, conv, val in zip(args, converters, m.groups()):
        arg <<= conv(val)
    return True
