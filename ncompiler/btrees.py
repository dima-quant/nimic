# /// nimic
# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2018 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

## BTree implementation with few features, but good enough for the
## Nim compiler's needs.

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *

with const:
    M = 512    # max children per B-tree node = M-1
               # (must be even and greater than 2)
    Mhalf = M // 2

@ref
class Node[Key, Val](Object):
    """{.acyclic.}"""
    entries: nint
    keys: array[M, Key]
    isInternal: bool = False
    match isInternal:
        case False:
            vals: array[M, Val]
        case True:
            links: array[M, Node[Key, Val]]

class BTree[Key, Val](Object):
    root: Node[Key, Val]
    entries: nint      ## number of key-value pairs

@generic
def initBTree[Key, Val]() -> BTree[Key, Val]:
    return BTree[Key, Val](root=Node[Key, Val](entries=0, isInternal=False), entries=0)

@template
def _less(a: untyped, b: untyped) -> bool:
    return cmp(a, b) < 0

@template
def _eq(a: untyped, b: untyped) -> bool:
    return cmp(a, b) == 0

def getOrDefault[Key, Val](b: BTree[Key, Val], key: Key) -> Val:
    result = default(Val)
    with var:
        x = b.root
    while x.isInternal:
        for j in range(0, x.entries):
            if j + 1 == x.entries or _less(key, x.keys[j + 1]):
                x = x.links[j]
                break
    assert not x.isInternal
    for j in range(0, x.entries):
        if _eq(key, x.keys[j]):
            return x.vals[j]
    return result

def contains[Key, Val](b: BTree[Key, Val], key: Key) -> bool:
    with var:
        x = b.root
    while x.isInternal:
        for j in range(0, x.entries):
            if j + 1 == x.entries or _less(key, x.keys[j + 1]):
                x = x.links[j]
                break
    assert not x.isInternal
    for j in range(0, x.entries):
        if _eq(key, x.keys[j]):
            return True
    return False

def _copyHalf[Key, Val](h: Node[Key, Val], result: Node[Key, Val]):
    for j in range(0, Mhalf):
        result.keys[j] = h.keys[Mhalf + j]
    if h.isInternal:
        for j in range(0, Mhalf):
            result.links[j] = h.links[Mhalf + j]
    else:
        for j in range(0, Mhalf):
            result.vals[j] = move(h.vals[Mhalf + j])

def _split[Key, Val](h: Node[Key, Val]) -> Node[Key, Val]:
    """split node in half"""
    result = Node[Key, Val](entries=Mhalf, isInternal=h.isInternal)
    h.entries = Mhalf
    _copyHalf(h, result)
    return result

def _insert[Key, Val](h: Node[Key, Val], key: Key, val: Val) -> Node[Key, Val]:
    #var t = Entry(key: key, val: val, next: nil)
    with var:
        newKey = key
        j = 0
    if not h.isInternal:
        while j < h.entries:
            if _eq(key, h.keys[j]):
                h.vals[j] = val
                return None
            if _less(key, h.keys[j]):
                break
            j += 1
        for i in countdown(h.entries, j + 1):
            h.vals[i] = move(h.vals[i - 1])
        h.vals[j] = val
    else:
        with var:
            newLink: Node[Key, Val] = None
        while j < h.entries:
            if j + 1 == h.entries or _less(key, h.keys[j + 1]):
                with let:
                    u = _insert(h.links[j], key, val)
                j += 1
                if u is None:
                    return None
                newKey = u.keys[0]
                newLink = u
                break
            j += 1
        for i in countdown(h.entries, j + 1):
            h.links[i] = h.links[i - 1]
        h.links[j] = newLink

    for i in countdown(h.entries, j + 1):
        h.keys[i] = h.keys[i - 1]
    h.keys[j] = newKey
    h.entries += 1
    return None if h.entries < M else _split(h)

def add[Key, Val](b: mut @ BTree[Key, Val], key: Key, val: Val):
    with let:
        u = _insert(b.root, key, val)
    b.entries += 1
    if u is None:
        return

    # need to split root
    with let:
        t = Node[Key, Val](entries=2, isInternal=True)
    t.keys[0] = b.root.keys[0]
    t.links[0] = b.root
    t.keys[1] = u.keys[0]
    t.links[1] = u
    b.root = t

def _toString[Key, Val](h: Node[Key, Val], indent: string, result: mut @ string):
    if not h.isInternal:
        for j in range(0, h.entries):
            result.add(indent)
            result.add(str(h.keys[j]) + " " + str(h.vals[j]) + "\n")
    else:
        for j in range(0, h.entries):
            if j > 0:
                result.add(indent + "(" + str(h.keys[j]) + ")\n")
            _toString(h.links[j], string(indent + "   "), result)

def __str__[Key, Val](b: BTree[Key, Val]) -> string:
    result = string("")
    _toString(b.root, string(""), result)
    return result

def hasNext[Key, Val](b: BTree[Key, Val], index: nint) -> bool:
    return index < b.entries

def _countSubTree[Key, Val](it: Node[Key, Val]) -> nint:
    if it.isInternal:
        result = 0
        for k in range(0, it.entries):
            result += _countSubTree(it.links[k])
        return result
    else:
        return it.entries

def next[Key, Val](b: BTree[Key, Val], index: nint) -> tuple[Key, Val, nint]:
    with var:
        it = b.root
        i = index
    # navigate to the right leaf:
    while it.isInternal:
        with var:
            sum = 0
        for k in range(0, it.entries):
            with let:
                c = _countSubTree(it.links[k])
            sum += c
            if sum > i:
                it = it.links[k]
                i -= (sum - c)
                break
    return (it.keys[i], it.vals[i], index + 1)

def pairs[Key, Val](b: BTree[Key, Val]) -> tuple[Key, Val]:
    with var:
        i = 0
    while hasNext(b, i):
        with let:
            (k, v, i2) = next(b, i)
        i = i2
        yield (k, v)

def len[Key, Val](b: BTree[Key, Val]) -> nint:
    """{.inline.}"""
    return b.entries

if comptime(__name__ == "__main__"):
    # Empty BTree tests
    with var:
        empty_b = initBTree[string, nint]()
    doAssert(len(empty_b) == 0)
    doAssert(not contains(empty_b, string("nonexistent")))
    _ = getOrDefault(empty_b, string("nonexistent"))
    doAssert(not hasNext(empty_b, 0))
    with var:
        empty_count = 0
    for k, v in pairs(empty_b):
        empty_count += 1
    doAssert(empty_count == 0)

    # Populated BTree tests (1200 items -> multi-level splits)
    with var:
        b = initBTree[string, nint]()
    doAssert(len(b) == 0)

    for i in range(1200):
        with let:
            k = "k" + str(i)
        add(b, k, i * 10)

    doAssert(len(b) == 1200)
    doAssert(contains(b, string("k0")))
    doAssert(contains(b, string("k500")))
    doAssert(contains(b, string("k1199")))
    doAssert(not contains(b, string("k9999")))

    doAssert(getOrDefault(b, string("k0")) == 0)
    doAssert(getOrDefault(b, string("k500")) == 5000)
    doAssert(getOrDefault(b, string("k1199")) == 11990)
    _ = getOrDefault(b, string("k9999"))

    # Direct testing of hasNext and next (as used by compiler/vm.nim)
    with var:
        vm_idx = 0
        direct_count = 0
    while hasNext(b, vm_idx):
        with let:
            (dk, dv, next_idx) = next(b, vm_idx)
        vm_idx = next_idx
        direct_count += 1
    doAssert(direct_count == 1200)

    with var:
        count = 0
    for k, v in pairs(b):
        count += 1
    doAssert(count == 1200)

    with let:
        s = str(b)
    doAssert(s != "")

    # Non-string key type test (nint -> string)
    with var:
        int_tree = initBTree[nint, string]()
    for i in range(100):
        add(int_tree, i, "val" + str(i))
    doAssert(len(int_tree) == 100)
    doAssert(contains(int_tree, 42))
    doAssert(getOrDefault(int_tree, 42) == "val42")
    doAssert(not contains(int_tree, 999))
    _ = getOrDefault(int_tree, 999)

    echo("SUCCESS: btrees tests passed!")
