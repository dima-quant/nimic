# /// nimic
#
#
#           The Nim Compiler
#        (c) Copyright 2017 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import toLowerAscii

class PrefixMatch(NIntEnum):
    """{.pure.}"""
    None_ = 0   # no prefix detected
    Abbrev = auto()  # prefix is an abbreviation of the symbol
    Substr = auto()  # prefix is a substring of the symbol
    Prefix = auto()  # prefix does match the symbol

def prefixMatch(p: string, s: string) -> PrefixMatch:
    @template
    def _eq(a: char, b: char) -> bool:
        return toLowerAscii(a) == toLowerAscii(b)

    if len(p) > len(s): return PrefixMatch.None_
    with var:
        i = 0
    # check for prefix/contains:
    while i < len(s):
        if s[i] == ch('_'): i += 1
        if i < len(s) and _eq(s[i], p[0]):
            with var:
                ii = i + 1
                jj = 1
            while ii < len(s) and jj < len(p):
                if p[jj] == ch('_'): jj += 1
                if s[ii] == ch('_'): ii += 1
                if not _eq(s[ii], p[jj]): break
                ii += 1
                jj += 1

            if jj >= len(p):
                if i == 0: return PrefixMatch.Prefix
                else: return PrefixMatch.Substr
        i += 1
    # check for abbrev:
    if _eq(s[0], p[0]):
        i = 1
        with var:
            j = 1
        while i < len(s):
            if i < len(s) - 1 and s[i] == ch('_'):
                if j < len(p) and _eq(p[j], s[i + 1]): j += 1
                else: return PrefixMatch.None_
            if i < len(s) and s[i] >= ch('A') and s[i] <= ch('Z') and (s[i - 1] < ch('A') or s[i - 1] > ch('Z')):
                if j < len(p) and _eq(p[j], s[i]): j += 1
                else: return PrefixMatch.None_
            i += 1
        if j >= len(p):
            return PrefixMatch.Abbrev
        else:
            return PrefixMatch.None_
    return PrefixMatch.None_

if comptime(__name__ == '__main__'):
    # Enum ordinals
    assert nint(PrefixMatch.None_) == 0
    assert nint(PrefixMatch.Abbrev) == 1
    assert nint(PrefixMatch.Substr) == 2
    assert nint(PrefixMatch.Prefix) == 3

    # Basic prefix, substr, abbrev
    assert prefixMatch(string("foo"), string("foobar")) == PrefixMatch.Prefix
    assert prefixMatch(string("bar"), string("foobar")) == PrefixMatch.Substr
    assert prefixMatch(string("fb"), string("foo_bar")) == PrefixMatch.Abbrev
    assert prefixMatch(string("fB"), string("fooBar")) == PrefixMatch.Abbrev
    assert prefixMatch(string("xyz"), string("foobar")) == PrefixMatch.None_
    assert prefixMatch(string("foobar"), string("foo")) == PrefixMatch.None_
    assert prefixMatch(string("foobar"), string("foobar")) == PrefixMatch.Prefix
    assert prefixMatch(string("foobar"), string("foo_bar")) == PrefixMatch.Prefix
    assert prefixMatch(string("f"), string("foo")) == PrefixMatch.Prefix
    assert prefixMatch(string("o"), string("foo")) == PrefixMatch.Substr

    # Pattern with underscores
    assert prefixMatch(string("foo_b"), string("foo_bar")) == PrefixMatch.Prefix
    assert prefixMatch(string("f_b"), string("foo_bar")) == PrefixMatch.None_

    # Abbreviation failure branches
    assert prefixMatch(string("fx"), string("foo_bar")) == PrefixMatch.None_
    assert prefixMatch(string("fX"), string("fooBar")) == PrefixMatch.None_
    assert prefixMatch(string("fbar"), string("foo_bar")) == PrefixMatch.None_

    # Multi-word and CamelCase abbreviations
    assert prefixMatch(string("fbb"), string("foo_bar_baz")) == PrefixMatch.Abbrev
    assert prefixMatch(string("fBB"), string("fooBarBaz")) == PrefixMatch.Abbrev
    assert prefixMatch(string("pX"), string("parseXMLDoc")) == PrefixMatch.Abbrev

    # Symbol with leading/trailing underscores
    assert prefixMatch(string("bar"), string("_foo_bar_")) == PrefixMatch.Substr

    print("All prefixmatches tests passed.")
