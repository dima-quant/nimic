# /// nimic
#
# ///
## Slices of a string, seq, array and openArray (N82), in Python and in compiled Nim: `x[a:b]` is Nim's
## `x[a ..< b]`, `x[a:]` `x[a .. ^1]`, `x[inrange(a, b)]` `x[a .. b]`, and a bound may count from the end:
## `x[a:back(n)]` is `x[a ..< ^n]`, `x[inrange(a, back(n))]` `x[a .. ^n]`. A slice of a seq, array or openArray
## is a new seq of copies; an empty slice (b < a) is fine (tests/verify_transpiled.py nimic compares outputs).
from __future__ import annotations
from nimic.ntypes import *


def total(x: openArray[nint]) -> nint:
    with var:
        result = nint(0)
    for v in x[1:back(1)]:
        result += v
    echo(x[inrange(1, back(2))], string(" "), x[2:])
    return result


if comptime(__name__ == "__main__"):
    with var:
        s = string("abcdef")
        q = seq[nint]([nint(10), nint(11), nint(12), nint(13), nint(14), nint(15)])
        a = array[6, nint]([nint(20), nint(21), nint(22), nint(23), nint(24), nint(25)])
    echo(s[1:3], string("|"), s[1:], string("|"), s[1:back(1)], string("|"), s[inrange(1, back(3))], string("|"),
         s[inrange(2, 4)], string("|"), s[inrange(4, 3)], string("|"), s[back(2)])
    echo(q[1:3], string(" "), q[inrange(1, back(1))], string(" "), q[0:back(4)], string(" "), q[inrange(3, 2)])
    echo(a[1:back(2)], string(" "), a[inrange(4, back(1))], string(" "), a[inrange(0, 1)])
    with let:
        tq = total(q)
        ta = total(a)
    echo(tq, string(" "), ta)
    with var:
        part = q[inrange(1, back(4))]
    part[0] = nint(99)
    echo(part, string(" "), q[1])
