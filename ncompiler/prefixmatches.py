from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import toLowerAscii

class PrefixMatch(NIntEnum):
    None_ = 0   # no prefix detected
    Abbrev = auto()  # prefix is an abbreviation of the symbol
    Substr = auto()  # prefix is a substring of the symbol
    Prefix = auto()  # prefix does match the symbol

def prefixMatch(p: string, s: string) -> PrefixMatch:
    def eq(a: char, b: char) -> bool:
        return toLowerAscii(a) == toLowerAscii(b)
    
    if len(p) > len(s): return PrefixMatch.None_
    i = 0
    # check for prefix/contains:
    while i < len(s):
        if s[i] == '_': i += 1
        if i < len(s) and eq(s[i], p[0]):
            ii = i + 1
            jj = 1
            while ii < len(s) and jj < len(p):
                if p[jj] == '_': jj += 1
                if s[ii] == '_': ii += 1
                if not eq(s[ii], p[jj]): break
                ii += 1
                jj += 1
            
            if jj >= len(p):
                if i == 0: return PrefixMatch.Prefix
                else: return PrefixMatch.Substr
        i += 1
    # check for abbrev:
    if eq(s[0], p[0]):
        i = 1
        j = 1
        while i < len(s):
            if i < len(s) - 1 and s[i] == '_':
                if j < len(p) and eq(p[j], s[i + 1]): j += 1
                else: return PrefixMatch.None_
            if i < len(s) and s[i] >= 'A' and s[i] <= 'Z' and (s[i - 1] < 'A' or s[i - 1] > 'Z'):
                if j < len(p) and eq(p[j], s[i]): j += 1
                else: return PrefixMatch.None_
            i += 1
        if j >= len(p):
            return PrefixMatch.Abbrev
        else:
            return PrefixMatch.None_
    return PrefixMatch.None_

if comptime(__name__ == '__main__'):
    assert prefixMatch(string("foo"), string("foobar")) == PrefixMatch.Prefix
    assert prefixMatch(string("bar"), string("foobar")) == PrefixMatch.Substr
    assert prefixMatch(string("fb"), string("foo_bar")) == PrefixMatch.Abbrev
    assert prefixMatch(string("fB"), string("fooBar")) == PrefixMatch.Abbrev
    assert prefixMatch(string("xyz"), string("foobar")) == PrefixMatch.None_
    print("All prefixmatches tests passed.")
