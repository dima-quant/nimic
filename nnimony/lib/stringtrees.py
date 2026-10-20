# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/stringtrees.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Helper logic for an efficient compile-time string to value/action mapping.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.assertions import *

# We split the set of strings into 2 sets of roughly the same size.
# The condition used for splitting is a (position, char) tuple.
# Every string of length > position for which s[position] <= char is in one
# set else it is in the other set.

Key = tuple[string, string]  # 2nd component is the enum field name as a string


@ufcs(seq)
def _addUnique(s: mut @ seq[char], x: char):
    """{.noSideEffect.}"""
    for y in items(s):
        if y == x: return
    s.add(x)


def _splitValue(a: openArray[Key], position: nint) -> tuple[char, float]:
    with var:
        cand: seq[char] = seq[char]([])
    for t in items(a):
        if t[0].len > position: cand._addUnique(t[0][position])

    result = (ch("\0"), -1.0)
    for disc in items(cand):
        with var:
            hits = 0
        for t in items(a):
            if t[0].len > position and t[0][position] <= disc:
                hits += 1
        # the split is the better, the more `hits` is close to `a.len / 2`:
        with let:
            grade = 100000.0 - abs(float(hits) - float(a.len) / 2.0)
        if grade > result[1]:
            result = (disc, grade)
    return result


def _tryAllPositions(a: openArray[Key]) -> tuple[char, nint]:
    with var:
        m = 0
    for t in items(a):
        m = max(m, t[0].len)

    result = (ch("\0"), -1)
    with var:
        best = -1.0
    for i in range(m):
        with let:
            current = _splitValue(a, i)
        if current[1] > best:
            best = current[1]
            result = (current[0], i)
    return result


class SearchKind(NIntEnum):
    LinearSearch = auto()
    ForkedSearch = auto()


class SearchNode(Object):
    kind: SearchKind
    match kind:
        case SearchKind.LinearSearch:
            choices: seq[Key]
        case SearchKind.ForkedSearch:
            _span: nint
            _best: tuple[char, nint]


class ForkedResult(Object):
    thenA: nint
    elseA: nint
    best: tuple[char, nint]


def forked(s: seq[SearchNode], i: nint) -> ForkedResult:
    with let:
        thenA = i + 1
        elseA = thenA + (1 if s[thenA].kind == SearchKind.LinearSearch else s[thenA]._span)
    result = ForkedResult(thenA=thenA, elseA=elseA, best=s[i]._best)
    return result


def _emitLinearSearch(a: openArray[Key], dest: mut @ seq[SearchNode]):
    with var:
        d = SearchNode(kind=SearchKind.LinearSearch, choices=seq[Key]([]))
    for x in a: d.choices.add(x)
    dest.add(d)


def _splitImpl(a: openArray[Key], dest: mut @ seq[SearchNode]):
    if a.len <= 2:
        _emitLinearSearch(a, dest)
    else:
        with let:
            best = _tryAllPositions(a)
        with var:
            groupA: seq[Key] = seq[Key]([])
            groupB: seq[Key] = seq[Key]([])
        for t in items(a):
            if t[0].len > best[1] and t[0][best[1]] <= best[0]:
                groupA.add(t)
            else:
                groupB.add(t)
        if groupA.len == 0 or groupB.len == 0:
            _emitLinearSearch(a, dest)
        else:
            with let:
                toPatch = dest.len
            dest.add(SearchNode(kind=SearchKind.ForkedSearch, _span=1, _best=best))
            _splitImpl(groupA, dest)
            _splitImpl(groupB, dest)
            with let:
                dist = dest.len - toPatch
            assert dist > 0
            dest[toPatch]._span = dist


def createSearchTree(a: openArray[Key]) -> seq[SearchNode]:
    result = seq[SearchNode]([])
    _splitImpl(a, result)
    return result


if comptime(__name__ == "__main__"):
    def _dumpTree(tree: seq[SearchNode]):
        echo("nodes=", tree.len)
        for i in range(tree.len):
            match tree[i].kind:
                case SearchKind.LinearSearch:
                    doAssert(tree[i].choices.len > 0)
                    for c in items(tree[i].choices):
                        echo(i, " ", tree[i].kind, " ", c[0], ":", c[1])
                case SearchKind.ForkedSearch:
                    with let:
                        f = forked(tree, i)
                    doAssert(f.thenA == i + 1)
                    doAssert(f.elseA > f.thenA)
                    echo(i, " ", tree[i].kind, " then=", f.thenA, " else=", f.elseA, " char=", f.best[0], " pos=", f.best[1])

    # 1. One key
    with let:
        t1 = createSearchTree(seq[Key]([(string("only"), string("kOnly"))]))
    doAssert(t1.len == 1)
    _dumpTree(t1)

    # 2. Keys sharing prefixes
    with let:
        t2 = createSearchTree(seq[Key]([
            (string("nifbuilder"), string("kBuilder")),
            (string("nifcore"), string("kCore")),
            (string("nifreader"), string("kReader")),
            (string("nifstreams"), string("kStreams")),
            (string("nimony"), string("kNimony")),
            (string("nimsem"), string("kNimsem")),
        ]))
    doAssert(t2.len > 1)
    _dumpTree(t2)

    # 3. Keys differing only at the end
    with let:
        t3 = createSearchTree(seq[Key]([
            (string("item1"), string("k1")),
            (string("item2"), string("k2")),
            (string("item3"), string("k3")),
            (string("item4"), string("k4")),
            (string("item5"), string("k5")),
        ]))
    doAssert(t3.len > 1)
    _dumpTree(t3)

    # 4. Unsplittable keys (> 2 equal strings)
    with let:
        t4 = createSearchTree(seq[Key]([
            (string("same"), string("kA")),
            (string("same"), string("kB")),
            (string("same"), string("kC")),
        ]))
    doAssert(t4.len == 1)
    _dumpTree(t4)
