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
    _M = 512    # max children per B-tree node = M-1
               # (must be even and greater than 2)
    _Mhalf = _M // 2

@ref
class _Node[Key, Val](Object):
    """{.acyclic.}"""
    _entries: nint
    _keys: array[_M, Key]
    _isInternal: bool
    match _isInternal:
        case False:
            _vals: array[_M, Val]
        case True:
            _links: array[_M, _Node[Key, Val]]

class BTree[Key, Val](Object):
    _root: _Node[Key, Val]
    _entries: nint      ## number of key-value pairs

@generic
def initBTree[Key, Val]() -> BTree[Key, Val]:
    return BTree[Key, Val](_root=_Node[Key, Val](_entries=0, _isInternal=False), _entries=0)

@template
def _less(a: untyped, b: untyped) -> bool:
    return cmp(a, b) < 0

@template
def _eq(a: untyped, b: untyped) -> bool:
    return cmp(a, b) == 0

def getOrDefault[Key, Val](b: BTree[Key, Val], key: Key) -> Val:
    result = default(Val)
    with var:
        x = b._root
    while x._isInternal:
        for j in range(0, x._entries):
            if j + 1 == x._entries or _less(key, x._keys[j + 1]):
                x = x._links[j]
                break
    assert not x._isInternal
    for j in range(0, x._entries):
        if _eq(key, x._keys[j]):
            return x._vals[j]
    return result

def contains[Key, Val](b: BTree[Key, Val], key: Key) -> bool:
    with var:
        x = b._root
    while x._isInternal:
        for j in range(0, x._entries):
            if j + 1 == x._entries or _less(key, x._keys[j + 1]):
                x = x._links[j]
                break
    assert not x._isInternal
    for j in range(0, x._entries):
        if _eq(key, x._keys[j]):
            return True
    return False

def _copyHalf[Key, Val](h: _Node[Key, Val], result: _Node[Key, Val]):
    for j in range(0, _Mhalf):
        result._keys[j] = h._keys[_Mhalf + j]
    if h._isInternal:
        for j in range(0, _Mhalf):
            result._links[j] = h._links[_Mhalf + j]
    else:
        for j in range(0, _Mhalf):
            if comptime(defined("gcArc") or defined("gcOrc") or defined("gcAtomicArc") or defined("gcYrc")):
                result._vals[j] = move(h._vals[_Mhalf + j])
            else:
                shallowCopy(result._vals[j], h._vals[_Mhalf + j])

def _split[Key, Val](h: _Node[Key, Val]) -> _Node[Key, Val]:
    """split node in half"""
    result = _Node[Key, Val](_entries=_Mhalf, _isInternal=h._isInternal)
    h._entries = _Mhalf
    _copyHalf(h, result)
    return result

def _insert[Key, Val](h: _Node[Key, Val], key: Key, val: Val) -> _Node[Key, Val]:
    #var t = Entry(key: key, val: val, next: nil)
    with var:
        newKey = key
        j = 0
    if not h._isInternal:
        while j < h._entries:
            if _eq(key, h._keys[j]):
                h._vals[j] = val
                return None
            if _less(key, h._keys[j]):
                break
            j += 1
        for i in countdown(h._entries, j + 1):
            if comptime(defined("gcArc") or defined("gcOrc") or defined("gcAtomicArc") or defined("gcYrc")):
                h._vals[i] = move(h._vals[i - 1])
            else:
                shallowCopy(h._vals[i], h._vals[i - 1])
        h._vals[j] = val
    else:
        with var:
            newLink: _Node[Key, Val] = None
        while j < h._entries:
            if j + 1 == h._entries or _less(key, h._keys[j + 1]):
                with let:
                    u = _insert(h._links[j], key, val)
                j += 1
                if u is None:
                    return None
                newKey = u._keys[0]
                newLink = u
                break
            j += 1
        for i in countdown(h._entries, j + 1):
            h._links[i] = h._links[i - 1]
        h._links[j] = newLink

    for i in countdown(h._entries, j + 1):
        h._keys[i] = h._keys[i - 1]
    h._keys[j] = newKey
    h._entries += 1
    return None if h._entries < _M else _split(h)

def add[Key, Val](b: mut @ BTree[Key, Val], key: Key, val: Val):
    with let:
        u = _insert(b._root, key, val)
    b._entries += 1
    if u is None:
        return

    # need to split root
    with let:
        t = _Node[Key, Val](_entries=2, _isInternal=True)
    t._keys[0] = b._root._keys[0]
    t._links[0] = b._root
    t._keys[1] = u._keys[0]
    t._links[1] = u
    b._root = t

def _toString[Key, Val](h: _Node[Key, Val], indent: string, result: mut @ string):
    if not h._isInternal:
        for j in range(0, h._entries):
            result.add(indent)
            result.add(str(h._keys[j]) + " " + str(h._vals[j]) + "\n")
    else:
        for j in range(0, h._entries):
            if j > 0:
                result.add(indent + "(" + str(h._keys[j]) + ")\n")
            _toString(h._links[j], string(indent + "   "), result)

def __str__[Key, Val](b: BTree[Key, Val]) -> string:
    """{.private.}"""
    result = string("")
    _toString(b._root, string(""), result)
    return result

def hasNext[Key, Val](b: BTree[Key, Val], index: nint) -> bool:
    return index < b._entries

def _countSubTree[Key, Val](it: _Node[Key, Val]) -> nint:
    if it._isInternal:
        result = 0
        for k in range(0, it._entries):
            result += _countSubTree(it._links[k])
        return result
    else:
        return it._entries

def next[Key, Val](b: BTree[Key, Val], index: nint) -> tuple[Key, Val, nint]:
    with var:
        it = b._root
        i = index
    # navigate to the right leaf:
    while it._isInternal:
        with var:
            sum = 0
        for k in range(0, it._entries):
            with let:
                c = _countSubTree(it._links[k])
            sum += c
            if sum > i:
                it = it._links[k]
                i -= (sum - c)
                break
    return (it._keys[i], it._vals[i], index + 1)

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
    return b._entries

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
