# /// nimic
#
# ///
## std/packedsets and sequtils' insert in Python (the nimic shims) and in compiled Nim: incl / excl /
## containsOrIncl / missingOrExcl, items over several trunks and a negative element, len, `$`, the set
## operations, a distinct element type; insert at the front, the middle, past the end, of the seq itself
## (tests/verify_transpiled.py nimic compares the outputs). Elements are added in ascending order: Nim 2 iterates
## a small set in insertion order (and `excl` moves its last element into the hole), nimony by trunk.
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.packedsets import (
    PackedSet, initPackedSet, toPackedSet, union, intersection, difference, symmetricDifference, disjoint)
from nimic.std.sequtils import insert


@distinct
class FileNo(nint):
    pass


def show(s: PackedSet[nint]) -> string:
    with var:
        result = string("[")
    for x in items(s):
        if result.len > 1:
            result.add(string(" "))
        result.add(str(x))
    result.add(string("]"))
    return result


if comptime(__name__ == "__main__"):
    def _main():
        with var:
            a = initPackedSet[nint]()
        for x in [nint(1), nint(3), nint(600), nint(700), nint(-1)]:
            a.incl(x)
        echo(show(a), string(" len "), a.len, string(" "), nint(3) in a, string(" "), nint(4) in a)
        echo(string("containsOrIncl 3: "), a.containsOrIncl(nint(3)), string(", 5: "), a.containsOrIncl(nint(5)))
        echo(string("missingOrExcl 5: "), a.missingOrExcl(nint(5)), string(", again: "), a.missingOrExcl(nint(5)))
        a.excl(nint(-1))  # the last one: Nim 2 moves the last element into the hole of a small set
        a.excl(nint(9999))
        echo(show(a), string(" "), str(a))
        with let:
            b = toPackedSet([nint(3), nint(700), nint(800)])
        echo(string("union "), show(union(a, b)), string(" intersection "), show(intersection(a, b)))
        echo(string("difference "), show(difference(a, b)), string(" symmetric "), show(symmetricDifference(a, b)))
        echo(string("disjoint "), disjoint(a, b), string(" "), disjoint(a, toPackedSet([nint(2)])))
        echo(string("== "), a == a, string(" "), a == b, string(" <= "), intersection(a, b) <= a, string(" "), b <= a)
        with var:
            ids = initPackedSet[FileNo]()
        ids.incl(FileNo(2))
        ids.incl(FileNo(7))
        for id in items(ids):
            echo(string("FX_"), int(id))
        with var:
            s = seq[nint]([nint(1), nint(1), nint(1)])
        s.insert([nint(2), nint(2)], 1)
        echo(str(s))
        s.insert([nint(0)])
        s.insert([nint(9), nint(8)], 99)
        echo(str(s))
        with var:
            t = seq[string]([string("x"), string("y")])
        t.insert(t.copy(), 1)
        echo(str(t))

    _main()
