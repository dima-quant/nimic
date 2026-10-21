# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/bitabs.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## A BiTable is a table that can be seen as an optimized pair
## of `(Table[Id, Val], Table[Val, Id])`.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    pragma('feature: "untyped"')
    from nimic.std.hashes import *
    from nimic.std.assertions import *
else:
    from nimic.std.hashes import *

    if comptime(defined("nimPreviewSlimSystem")):
        from nimic.std.assertions import *


class BiTable[Id, T](Object):  # Id must be an int/uint or a distinct type thereof
                               # that is convertible to `uint32`. `Id(0)` must mean "not used".
    _vals: seq[T]  # indexed by LitId
    _keys: seq[Id]  # indexed by hash(val)


@generic
def initBiTable[Id, T]() -> BiTable[Id, T]:
    return BiTable[Id, T](_vals=seq[T]([]), _keys=seq[Id]([]))


def _nextTry(h: Hash, maxHash: Hash) -> Hash:
    """{.inline.}"""
    result = (h + 1) & maxHash
    return result


@template
def _maxHash(t) -> untyped:
    return Hash(high(t._keys))


@template
def _isFilled(x: untyped) -> bool:
    return uint32(x) > u32(0)


@dispatch
def len[Id, T](t: BiTable[Id, T]) -> nint:
    return t._vals.len


def _mustRehash(length: nint, counter: nint) -> bool:
    """{.inline.}"""
    assert length > counter
    result = (length < counter // 2 + counter) or (length - counter < 4)
    return result


with const:
    _idStart = 1


@template
def _idToIdx(x: untyped) -> nint:
    return nint(x) - _idStart


@dispatch
def hasId[Id, T](t: BiTable[Id, T], x: Id) -> bool:
    """{.inline.}"""
    with let:
        idx = _idToIdx(x)
    result = idx >= 0 and idx < t._vals.len
    return result


@dispatch
def _enlarge[Id, T](t: mut @ BiTable[Id, T]):
    with var:
        n = seq[Id]()
    newSeq(n, len(t._keys) * 2)
    swap(t._keys, n)
    for i in inrange(0, high(n)):
        with let:
            eh = n[i]
        if _isFilled(eh):
            with var:
                j = hash(t._vals[_idToIdx(eh)]) & _maxHash(t)
            while _isFilled(t._keys[j]):
                j = _nextTry(j, _maxHash(t))
            t._keys[j] = move(n[i])


@dispatch
def _rebuildIndex[Id, T](t: mut @ BiTable[Id, T]):
    # Build `keys` from `vals` for a table filled by `addOrdered`, which leaves
    # none. Sized as `enlarge` would have left it after that many inserts, so the
    # load factor matches a table that was built by interning all along.
    with var:
        cap = 16
    # `mustRehash` asserts `length > counter`, so the capacity has to clear
    # `vals.len` before the load-factor question can even be asked.
    while cap <= t._vals.len: cap = cap * 2
    while _mustRehash(cap, t._vals.len): cap = cap * 2
    t._keys = newSeq[Id](cap)
    for i in range(t._vals.len):
        with var:
            j = hash(t._vals[i]) & _maxHash(t)
        while _isFilled(t._keys[j]):
            j = _nextTry(j, _maxHash(t))
        t._keys[j] = Id(i + _idStart)


@dispatch
def isIndexed[Id, T](t: BiTable[Id, T]) -> bool:
    """{.inline.}"""
    # Whether the reverse (value -> id) index exists. It does not, and only does
    # not, between an `addOrdered` fill and the first thing that needs it.
    return t._keys.len != 0 or t._vals.len == 0


@dispatch
def ensureIndexed[Id, T](t: mut @ BiTable[Id, T]):
    # Build the reverse index if `addOrdered` left it unbuilt. Idempotent, and
    # free for a table that was interned into normally.
    #
    # `getOrIncl` calls this itself. `getKeyId` cannot — it takes the table
    # immutably and changing that would break every caller in the ecosystem for
    # the sake of the rare one — so a caller that looks up BY VALUE in a table
    # that might have been filled with `addOrdered` calls this first. Getting it
    # wrong is an assertion in `getKeyId`, not a wrong answer.
    if not t.isIndexed(): _rebuildIndex(t)


@dispatch
def addOrdered[Id, T](t: mut @ BiTable[Id, T], v: sink @ T) -> Id:
    # Append `v` under the next id WITHOUT hashing it.
    #
    # For a table deserialized in id order, every entry's id is its position, so
    # the reverse index costs a hash and an insert per entry to reproduce
    # something the file already states. `bif.load` fills four pools that way,
    # and on a 68-module `--ic:on` build of the Nim compiler that was 451ms of a
    # 637ms `load`, nearly all of it the symbol pool.
    #
    # The table is still a BiTable: `getOrIncl` builds the index on demand (and
    # `ensureIndexed` does it explicitly for `getKeyId`), so a pool that does get
    # interned into behaves exactly as before — it just pays for the index at the
    # point something needs it rather than always. Callers that only ever map
    # id -> value never pay at all.
    t._vals.add(v)
    result = Id(t._vals.len - 1 + _idStart)
    return result


@dispatch
def getKeyId[Id, T](t: BiTable[Id, T], v: T) -> Id:
    assert t.isIndexed(), "getKeyId on a table filled by addOrdered: call ensureIndexed first"
    with let:
        origH = hash(v)
    with var:
        h = origH & _maxHash(t)
    if t._keys.len != 0:
        while True:
            with let:
                strId = t._keys[h]
            if not _isFilled(strId): break
            if v == t._vals[_idToIdx(strId)]: return strId
            h = _nextTry(h, _maxHash(t))
    return Id(0)


pragma("pragma: maybeDirty, dirty")


@template
def _getOrInclImpl():
    """{.maybeDirty.}"""
    ensureIndexed(t)
    with let:
        origH = hash(v)
    with var:
        h = origH & _maxHash(t)
    if t._keys.len != 0:
        while True:
            with let:
                strId = t._keys[h]
            if not _isFilled(strId): break
            if v == t._vals[_idToIdx(strId)]: return strId
            h = _nextTry(h, _maxHash(t))
        # not found, we need to insert it:
        if _mustRehash(t._keys.len, t._vals.len):
            _enlarge(t)
            # recompute where to insert:
            h = origH & _maxHash(t)
            while True:
                with let:
                    strId = t._keys[h]
                if not _isFilled(strId): break
                h = _nextTry(h, _maxHash(t))
    else:
        setLen(t._keys, 16)
        h = origH & _maxHash(t)


@dispatch
@template_expand
def getOrIncl[Id, T](t: mut @ BiTable[Id, T], v: T) -> Id:
    _getOrInclImpl()
    result = Id(t._vals.len + _idStart)
    t._keys[h] = result
    t._vals.add(v)
    return result


@dispatch
@template_expand
def getOrInclFromView[Id, T, View](t: mut @ BiTable[Id, T], v: View) -> Id:
    # Optimized version that only materializes from the view `v` if the value does
    # not exist yet.
    _getOrInclImpl()
    result = Id(t._vals.len + _idStart)
    t._keys[h] = result
    t._vals.add(str(v))
    return result


if comptime(defined("nimony")):
    @ufcs(BiTable)
    @dispatch
    def __getitem__[Id, T](t: BiTable[Id, T], strId: Id) -> mut @ T:
        """{.inline.}"""
        with let:
            idx = _idToIdx(strId)
        assert idx < t._vals.len
        result = t._vals[idx]
        return result
else:
    @ufcs(BiTable)
    @dispatch
    def __getitem__[Id, T](t: mut @ BiTable[Id, T], strId: Id) -> mut @ T:
        """{.inline.}"""
        with let:
            idx = _idToIdx(strId)
        assert idx < t._vals.len
        result = t._vals[idx]
        return result

    @ufcs(BiTable)
    @dispatch
    def __getitem__[Id, T](t: BiTable[Id, T], strId: Id) -> lent @ T:
        """{.inline.}"""
        with let:
            idx = _idToIdx(strId)
        assert idx < t._vals.len
        result = t._vals[idx]
        return result


@dispatch
def hash[Id, T](t: BiTable[Id, T]) -> Hash:
    # as the keys are hashes of the values, we simply use them instead
    with var:
        h: Hash = 0
    for i, n in pairs(t._keys):
        h = mix_hash(h, hash((i, n)))
    result = finish_hash(h)
    return result


@dispatch
def memSize[Id, T](t: BiTable[Id, T]) -> nint:
    if comptime(issubclass(T, string)):
        with var:
            shorts = 0
        result = 0
        for x in items(t._vals):
            if x.len <= 3: shorts += 1
            result += x.len
        result += t._vals.len * sizeof(T) + t._keys.len * sizeof(Id)
        echo("SHORT STRINGS ", shorts)
    else:
        result = t._vals.len * sizeof(T) + t._keys.len * sizeof(Id)
    return result


# we need to distinguish `0.0` and `-0.0` even if `0.0 == -0.0`
# as signbit and copySign procs returns the different value.
@distinct
class BiTableFloat[Id](BiTable[Id, uint64]):
    pass


@dispatch
def getOrIncl[Id](t: mut @ BiTableFloat[Id], v: float64) -> Id:
    """{.inline.}"""
    return BiTable[Id, uint64](t).getOrIncl(cast[uint64](v))


@ufcs(BiTableFloat)
@dispatch
def __getitem__[Id](t: BiTableFloat[Id], strId: Id) -> float64:
    """{.inline.}"""
    return cast[float64](BiTable[Id, uint64](t)[strId])


if comptime(__name__ == "__main__"):
    if comptime(defined("nimony")):
        from nimic.std.syncio import *
    with var:
        t = initBiTable[uint32, string]()

    assert getOrIncl(t, string("hello")) == u32(1)

    assert getOrIncl(t, string("hello")) == u32(1)
    assert getOrIncl(t, string("hello3")) == u32(2)
    assert getOrIncl(t, string("hello4")) == u32(3)
    assert getOrIncl(t, string("helloasfasdfdsa")) == u32(4)
    assert getOrIncl(t, string("hello")) == u32(1)
    assert getKeyId(t, string("hello")) == u32(1)
    assert getKeyId(t, string("none")) == u32(0)

    for i in range(100_000):
        _ = t.getOrIncl(str(i) + "___" + str(i))

    for i in range(100_000):
        assert _idToIdx(t.getOrIncl(str(i) + "___" + str(i))) == i + 4
    assert t._vals.len == 100004

    assert t._vals[0] == string("hello")
    assert t._vals[1004] == string("1000___1000")

    with var:
        tf = initBiTable[uint32, float64]()

    _ = tf.getOrIncl(0.4)
    _ = tf.getOrIncl(16.4)
    _ = tf.getOrIncl(32.4)
    assert getKeyId(tf, 32.4) == u32(3)

    # `addOrdered` must be indistinguishable from having interned all along, and
    # the interesting part is the table it leaves BEHIND: the reverse index is
    # unbuilt, so every lookup path has to notice and build it. A duplicate id
    # handed out here would be silent corruption for a `bif` pool, since the
    # token stream already refers to the first one.
    with block("orderedFill"):
        with var:
            a = initBiTable[uint32, string]()
        for i in range(5_000):
            assert _idToIdx(a.addOrdered("s" + str(i))) == i     # same ids getOrIncl gives
        assert a._vals.len == 5_000
        assert a[uint32(1)] == string("s0")                              # id -> value, no index yet
        assert a[uint32(5_000)] == string("s4999")

        # `getKeyId` needs the index, and says so rather than answering wrongly
        assert not a.isIndexed()
        a.ensureIndexed()
        assert a.isIndexed()
        a.ensureIndexed()                                                # idempotent
        assert getKeyId(a, string("s0")) == u32(1)
        assert getKeyId(a, string("s4999")) == u32(5_000)
        assert getKeyId(a, string("nope")) == u32(0)
        for i in range(5_000):
            assert _idToIdx(getKeyId(a, "s" + str(i))) == i

        # and interning must now REUSE those ids rather than append duplicates
        for i in range(5_000):
            assert _idToIdx(a.getOrIncl("s" + str(i))) == i
        assert a._vals.len == 5_000
        assert _idToIdx(a.getOrIncl(string("fresh"))) == 5_000
        assert a._vals.len == 5_001

    with block("orderedThenIncl"):
        # `getOrIncl` builds the index itself, so it needs no `ensureIndexed`
        with var:
            b = initBiTable[uint32, string]()
        for i in range(100): _ = b.addOrdered("t" + str(i))
        assert not b.isIndexed()
        assert _idToIdx(b.getOrIncl(string("t42"))) == 42
        assert b.isIndexed()
        assert b._vals.len == 100
        assert getKeyId(b, string("t99")) == u32(100)

    with block("indexedFromTheStart"):
        # a normally interned table is `isIndexed` throughout, so `ensureIndexed`
        # costs it nothing and `getKeyId` never trips its assertion
        with var:
            d = initBiTable[uint32, string]()
        assert d.isIndexed()                                             # empty counts as indexed
        _ = d.getOrIncl(string("only"))
        assert d.isIndexed()
        d.ensureIndexed()
        assert getKeyId(d, string("only")) == u32(1)

    echo("success")

    # Additional tests: a few dozen values (forcing rehash), hasId, insertion order, BiTableFloat
    with var:
        tab = initBiTable[uint32, string]()
    for i in range(40):
        with let:
            id = tab.getOrIncl("item_" + str(i))
        doAssert(id == uint32(i + 1))
    doAssert(len(tab) == 40)
    doAssert(tab.getOrIncl(string("item_0")) == u32(1))
    doAssert(tab.getOrIncl(string("item_25")) == u32(26))
    doAssert(not hasId(tab, u32(0)))
    doAssert(hasId(tab, u32(1)))
    doAssert(hasId(tab, u32(40)))
    doAssert(not hasId(tab, u32(41)))
    echo(len(tab), "|", tab[u32(1)], "|", tab[u32(26)], "|", tab[u32(40)])

    with var:
        ft = BiTableFloat[uint32](initBiTable[uint32, uint64]())
    with let:
        fid1 = getOrIncl(ft, 0.0)
        fid2 = getOrIncl(ft, -0.0)
        fid3 = getOrIncl(ft, 1.5)
        fid4 = getOrIncl(ft, 1.5)
    doAssert(fid1 == u32(1))
    doAssert(fid2 == u32(2))
    doAssert(fid3 == u32(3))
    doAssert(fid4 == u32(3))
    doAssert(ft[fid3] == 1.5)
    echo(fid1, "|", fid2, "|", fid3, "|", fid4)
