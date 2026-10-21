# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/stringviews.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## A better stdlib would offer this...

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.hashes import *

if comptime(defined("nimony")):
    pragma('feature: "lenientnils"')

pchar = ptr[UncheckedArray[char]]


class StringView(Object):
    p: pchar
    len: nint

    @template
    def __getitem__(s: StringView, i: nint) -> char:
        return s.p[i]


if comptime(not defined("nimony")):
    pragma("pragma: untyped")


@template
def _eqImpl():
    """{.untyped.}"""
    if a.len == b.len:
        for i in range(a.len):
            if a[i] != b[i]: return False
        result = True
    else:
        result = False


@ufcs(StringView)
@dispatch
@template_expand
def __eq__(a: StringView, b: StringView) -> bool:
    _eqImpl()
    return result


@ufcs(StringView)
@dispatch
@template_expand
def __eq__(a: StringView, b: string) -> bool:
    _eqImpl()
    return result


def startsWith(s: StringView, prefix: string) -> bool:
    with let:
        prefixLen = prefix.len
        sLen = s.len
    with var:
        i = 0
    while True:
        if i >= prefixLen: return True
        if i >= sLen or s[i] != prefix[i]: return False
        i += 1
    return False


def add(s: mut @ string, b: StringView):
    with let:
        l = s.len
    s.setLen(l + b.len)
    for i in range(b.len):
        s[l + i] = b[i]


if comptime(not defined("nimony")):
    if comptime(not declared("readRawData")):
        @ufcs(string)
        def readRawData(s: string) -> ptr[UncheckedArray[char]]:
            """{.inline.}"""
            if s.len == 0:
                return None
            else:
                return cast[ptr[UncheckedArray[char]]](addr(s[0]))

    if comptime(not declared("beginStore")):
        def beginStore(s: mut @ string, newLen: nint, start = 0) -> ptr[UncheckedArray[char]]:
            """{.inline.}"""
            s.setLen(newLen)
            if s.len == 0:
                return None
            else:
                return cast[ptr[UncheckedArray[char]]](addr(s[start]))

    if comptime(not declared("endStore")):
        def endStore(s: mut @ string):
            """{.inline.}"""
            return


@ufcs(StringView)
def __str__(s: StringView) -> string:
    result = newString(s.len)
    if s.len > 0:
        copyMem(beginStore(result, s.len, 0), s.p, s.len)
        endStore(result)
    return result


def toStringViewUnsafe(s: string) -> StringView:
    # Watch out that the string lives longer than the string view!
    if s.len != 0:
        result = StringView(p=cast[pchar](s.readRawData()), len=s.len)
    else:
        result = StringView(p=None, len=0)
    return result


@dispatch
def hash(a: StringView) -> Hash:
    """{.inline.}"""
    if comptime(defined("nimony")):
        return hash(borrowCStringUnsafe(cast[cstring](a.p), a.len))
    else:
        return hash(toOpenArray(a.p, 0, a.len - 1))


if comptime(__name__ == "__main__"):
    with let:
        s1 = string("hello world")
        s2 = string("hello world")
        s3 = string("hello there")
        empty = string("")
        v1 = toStringViewUnsafe(s1)
        v2 = toStringViewUnsafe(s2)
        v3 = toStringViewUnsafe(s3)
        vEmpty = toStringViewUnsafe(empty)

    echo(v1.len, "|", v1[0], "|", v1[4], "|", vEmpty.len)
    echo(str(v1), "|", str(vEmpty))
    echo(v1 == v2, "|", v1 == v3, "|", v1 == vEmpty, "|", vEmpty == toStringViewUnsafe(string("")))
    echo(v1 == s1, "|", v1 == s3, "|", vEmpty == empty, "|", vEmpty == s1)
    echo(startsWith(v1, string("hello")), "|", startsWith(v1, string("world")), "|", startsWith(v1, string("")), "|", startsWith(v1, string("hello world!")))
    echo(startsWith(vEmpty, string("")), "|", startsWith(vEmpty, string("a")))

    with var:
        acc = string("prefix:")
    add(acc, v1)
    add(acc, vEmpty)
    echo(acc)

    echo(hash(v1) == hash(v2), "|", hash(vEmpty) == hash(toStringViewUnsafe(string(""))))
