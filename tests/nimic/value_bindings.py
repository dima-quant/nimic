# /// nimic
#
# ///
## Nim's value semantics of assignment in Python (rule:valuecheck): the code writes each copy Nim's assignment makes
## where the difference shows, and nimic checks it when it runs (without a copy, each of them is a ValueCopyError:
## the write changes a value both locations hold). A variable declared from an l-value or re-assigned, and a proc's
## `-> T` result (`return p.copy()`) get a copy of a value-type value; a `var` / `lent` result, a template's l-value
## and a core or std proc's result (`min` returns an argument, `getOrDefault` an entry) are aliases, copied by the
## variable bound to them; a nimic proc's `-> T` result that is a copy is its own. A swap and a variable's
## last use (Nim moves it) need no copy: a type with a `=copy` hook runs it only where Nim copies
## (tests/verify_transpiled.py nimic compares the outputs with compiled Nim).
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.tables import *


class Point(Object):
    x: nint
    tags: seq[nint]


class Holder(Object):
    p: Point
    name: string


def same(p: Point) -> Point:
    return p.copy()


def viaResult(p: Point) -> Point:
    result = p.copy()
    return result


def tagsOf(p: Point) -> seq[nint]:
    return p.tags.copy()


def slot(h: mut @ Holder) -> mut @ Point:
    return h.p


def peek(h: Holder) -> lent @ Point:
    return h.p


@template
def pointOf(h: Holder) -> Point:
    return h.p


class Counter(Object):
    copies: nint


with var:
    _counter = Counter(copies=nint(0))


class Tracked(Object):
    n: nint


@hook("copy")
def _copyTracked(dest: mut @ Tracked, src: Tracked):
    _counter.copies += 1
    dest.n = src.n


def moves():
    with var:
        t = Tracked(n=nint(1))
        kept = t.copy()
    kept.n += 1
    echo(string("tracked: t.n="), t.n, string(" kept.n="), kept.n, string(" copies="), _counter.copies)
    with var:
        last = kept
    last.n += 10
    echo(string("moved: last.n="), last.n, string(" copies="), _counter.copies)


if comptime(__name__ == "__main__"):
    def _main():
        with var:
            a = Point(x=nint(1), tags=seq[nint]([nint(1)]))
            b = a.copy()
            n = a.x.copy()
            fromSame = same(a)
            fromResult = viaResult(a)
            tags = tagsOf(a)
        b.x += 1
        n += 5
        fromSame.x += 10
        fromResult.x += 100
        tags.add(nint(7))
        echo(string("declared: a.x="), a.x, string(" b.x="), b.x, string(" n="), n, string(" same="), fromSame.x,
             string(" result="), fromResult.x, string(" a.tags="), len(a.tags), string(" tags="), len(tags))

        with var:
            lo = min(a.x, b.x).copy()
            shown = astToStr(a.x)
        lo += 1000
        echo(string("core procs: a.x="), a.x, string(" lo="), lo, string(" shown="), shown)

        with var:
            table = initTable[string, seq[nint]]()
        table[string("k")] = seq[nint]([nint(1)])
        with var:
            entry = table.getOrDefault(string("k")).copy()
        entry.add(nint(2))
        echo(string("std procs: stored="), len(table[string("k")]), string(" entry="), len(entry))

        with var:
            c = Point(x=nint(2), tags=seq[nint]())
        c = a.copy()
        c.x = nint(50)
        echo(string("re-assigned: a.x="), a.x, string(" c.x="), c.x)

        with var:
            u = Point(x=nint(3), tags=seq[nint]())
            w = Point(x=nint(4), tags=seq[nint]())
        (u, w) = (w, u)
        u.x += 1000
        echo(string("swapped: u.x="), u.x, string(" w.x="), w.x)

        with var:
            h = Holder(p=Point(x=nint(5), tags=seq[nint]()), name=string("h"))
            s = h.name.copy()
        s.add(string("!"))
        slot(h).x = nint(6)
        pointOf(h).x += 1
        with var:
            mine = slot(h).copy()
            seen = peek(h).copy()
            got = pointOf(h).copy()
        mine.x = nint(70)
        seen.x = nint(80)
        got.x = nint(90)
        echo(string("aliases: h.p.x="), h.p.x, string(" h.name="), h.name, string(" s="), s,
             string(" mine="), mine.x, string(" seen="), seen.x, string(" got="), got.x)
        moves()

    _main()
