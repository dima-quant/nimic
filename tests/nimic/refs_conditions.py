# /// nimic
#
# ///
## Ref types and condition forms in Python and in compiled Nim: a forward `type X = ref[T]` alias (Nim `X = ref T`
## ahead of `T = object`), `@ref class X(T): pass`, a `ref[T]` field, reference identity `a is b` (system.`==`),
## bindings in if / elif / while conditions (`(let x = e; cond)`) and stmtlist(...) (a statement list expression)
## (tests/verify_transpiled.py nimic compares the outputs).
from __future__ import annotations
from nimic.ntypes import *


class Kind(NIntEnum):
    kLeaf = 0
    kPair = 1
    kTriple = 2
    kQuad = 3


type Node = ref[NodeObj]


class NodeObj(Object):
    name: string
    kind: Kind
    match kind:
        case Kind.kLeaf:
            value: nint
        case _ if kind in inrange(Kind.kPair, Kind.kQuad):
            left: Node
            right: Node


class CounterObj(Object):
    hits: nint


@ref
class Counter(CounterObj):
    pass


class Walker(Object):
    counter: ref[CounterObj]
    pos: nint


def leaf(name: string, v: nint) -> Node:
    return Node(name=name, kind=Kind.kLeaf, value=v)


def sameNode(a: Node, b: Node) -> bool:
    if a is b:
        return True
    return False


def total(n: Node) -> nint:
    if (k := n.kind) == Kind.kLeaf:
        return n.value
    elif (l := total(n.left)) > nint(100):
        return l
    return total(n.left) + total(n.right)


def step(w: mut @ Walker) -> nint:
    w.counter.hits += 1
    w.pos += 1
    return w.pos


if comptime(__name__ == "__main__"):
    def _main():
        with let:
            a = leaf(string("a"), nint(3))
            b = leaf(string("b"), nint(4))
            p = Node(name=string("p"), kind=Kind.kTriple, left=a, right=b)
        with var:
            nodes = seq[Node]()
        nodes.add(p)
        nodes[0].name = string("shared")
        echo(p.name, string(" "), total(p), string(" "), sameNode(a, a), string(" "), sameNode(a, b),
             string(" "), a is not b)
        with let:
            c = Counter(hits=nint(0))
        with var:
            w = Walker(counter=c, pos=nint(0))
            w2 = w.copy()  # the copy shares the ref counter
        while (s := step(w)) < nint(3):
            echo(string("step "), s)
        w2.pos = nint(10)
        echo(c.hits, string(" "), w.pos, string(" "), w2.pos, string(" "), w2.counter.hits)
        with let:
            depth = stmtlist(d := w.pos * 2, _ := step(w), mut @ (e := d + w.pos), e) if w.pos > nint(0) else nint(-1)
        echo(depth, string(" "), w.pos, string(" "), c.hits)

    _main()
