"""
ncompiler/prefixmatches.py — Prefix matching for IDE suggestions
Converted from compiler/prefixmatches.nim
"""
from __future__ import annotations
from nimic.ntypes import *

class PrefixMatch(NIntEnum):
    None_ = auto()
    Abbrev = auto()
    Substr = auto()
    Prefix = auto()

def prefixMatch(p: str, s: str) -> PrefixMatch:
    if len(p) > len(s):
        return PrefixMatch.None_
    def eq(a, b):
        return a.lower() == b.lower()
    i = 0
    while i < len(s):
        if s[i] == '_':
            i += 1
        if i < len(s) and eq(s[i], p[0]):
            ii, jj = i + 1, 1
            while ii < len(s) and jj < len(p):
                if p[jj] == '_': jj += 1
                if s[ii] == '_': ii += 1
                if ii < len(s) and jj < len(p) and not eq(s[ii], p[jj]):
                    break
                ii += 1; jj += 1
            if jj >= len(p):
                return PrefixMatch.Prefix if i == 0 else PrefixMatch.Substr
        i += 1
    if len(s) > 0 and eq(s[0], p[0]):
        i, j = 1, 1
        while i < len(s):
            if i < len(s) - 1 and s[i] == '_':
                if j < len(p) and eq(p[j], s[i+1]): j += 1
                else: return PrefixMatch.None_
            if i < len(s) and s[i].isupper() and not s[i-1].isupper():
                if j < len(p) and eq(p[j], s[i]): j += 1
                else: return PrefixMatch.None_
            i += 1
        if j >= len(p): return PrefixMatch.Abbrev
    return PrefixMatch.None_
