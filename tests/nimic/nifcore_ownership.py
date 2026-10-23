# /// nimic
#
# ///
## nifcore's buffer ownership (nimony src/lib/nifcore.nim: Storage, CursorOwner, Cursor, TokenBuf), ported
## proc for proc with plain int64 tokens: a TokenBuf shares its storage with the cursors reading it through a
## reference-counted CursorOwner block in raw memory, with the pool kept alive by GC_ref; the lifetime hooks keep
## the count, and prepareMutation copies on write while cursors are alive.
##
## Run in Python and as transpiled Nim, the output must be the same: the counts and the frees happen at the same
## points (ncompiler/proposals/feature_lifetime_hooks_runtime.md, H7).
from __future__ import annotations
from nimic.ntypes import *

NifToken = int64

Storage = ptr[UncheckedArray[NifToken]]


@ref
class Pool(Object):
    name: string


class CursorOwnerObj(Object):
    rc: nint
    data: Storage
    pool: Pool  # kept alive with GC_ref / GC_unref: ARC doesn't trace ref fields in alloc'd memory


CursorOwner = ptr[CursorOwnerObj]


class Cursor(Object):
    owner: CursorOwner
    p: ptr[NifToken]
    rem: nint


class TokenBuf(Object):
    data: Storage
    len: nint
    cap: nint
    owner: CursorOwner
    pool: Pool


class _Stats(Object):
    frees: nint  # owner blocks freed, so the output shows when it happens


with var:
    _gStats = _Stats()


def _decRcAndFree(owner: CursorOwner):
    owner.rc -= 1
    if owner.rc == 0:
        if not isNil(owner.data):
            dealloc(owner.data)
        if owner.pool is not None:
            GC_unref(owner.pool)
            owner.pool = None
        dealloc(owner)
        _gStats.frees += 1


@hook("destroy")
def _destroyCursor(c: mut @ Cursor):
    if not isNil(c.owner):
        _decRcAndFree(c.owner)


@hook("wasMoved")
def _wasMovedCursor(c: mut @ Cursor):
    c.owner = None
    c.p = None
    c.rem = 0


@hook("copy")
def _copyCursor(dest: mut @ Cursor, src: Cursor):
    if dest.owner != src.owner or dest.p != src.p:
        _destroyCursor(dest)
        if not isNil(src.owner):
            src.owner.rc += 1
        dest.owner = src.owner
        dest.p = src.p
    dest.rem = src.rem


@hook("dup")
def _dupCursor(src: Cursor) -> Cursor:
    """{.nodestroy.}"""
    result = Cursor(owner=src.owner, p=src.p, rem=src.rem)
    if not isNil(result.owner):
        result.owner.rc += 1
    return result


@hook("copy")
def _copyTokenBuf(dest: mut @ TokenBuf, src: TokenBuf):
    """{.error.}"""
    pass


@hook("wasMoved")
def _wasMovedTokenBuf(dest: mut @ TokenBuf):
    """{.nodestroy.}"""
    dest.data = None
    dest.len = 0
    dest.cap = 0
    dest.owner = None
    dest.pool = None


@hook("destroy")
def _destroyTokenBuf(dest: mut @ TokenBuf):
    if not isNil(dest.owner):
        _decRcAndFree(dest.owner)
    elif not isNil(dest.data):
        dealloc(dest.data)


def createTokenBuf(cap: nint) -> TokenBuf:
    return TokenBuf(data=cast[Storage](alloc(sizeof(NifToken) * cap)), len=0, cap=cap, pool=Pool(name=string("p")))


def rc(b: TokenBuf) -> nint:
    """The owner block's count, 0 without one."""
    if isNil(b.owner):
        return 0
    return b.owner.rc


def prepareMutation(b: mut @ TokenBuf):
    if not isNil(b.owner):
        if b.owner.rc == 1:
            # reclaim the owner header; b.data keeps its allocation
            b.owner.data = None
            _decRcAndFree(b.owner)
            b.owner = None
        else:
            with let:
                newData = cast[Storage](alloc(sizeof(NifToken) * max(b.cap, 1)))
            copyMem(newData, b.data, sizeof(NifToken) * b.len)
            _decRcAndFree(b.owner)
            b.owner = None
            b.data = newData


def add(b: mut @ TokenBuf, t: NifToken):
    prepareMutation(b)
    if b.len >= b.cap:
        b.cap = max(b.cap // 2 + b.cap, 8)
        b.data = cast[Storage](realloc(b.data, sizeof(NifToken) * b.cap))
    b.data[b.len] = t
    b.len += 1


def _ensureOwner(b: mut @ TokenBuf):
    if isNil(b.owner):
        b.owner = cast[CursorOwner](alloc0(sizeof(CursorOwnerObj)))
        b.owner.data = b.data
        b.owner.pool = b.pool
        GC_ref(b.owner.pool)
        b.owner.rc = 1


def beginRead(b: mut @ TokenBuf) -> Cursor:
    _ensureOwner(b)
    b.owner.rc += 1
    return Cursor(owner=b.owner, p=addr(b.data[0]), rem=b.len)


def endRead(c: mut @ Cursor):
    if not isNil(c.owner):
        _decRcAndFree(c.owner)
    _wasMovedCursor(c)


def load(c: Cursor) -> NifToken:
    return c.p.contents


def _peek(b: TokenBuf, c: Cursor) -> NifToken:
    """A copy of a cursor that is used later (a parameter): Nim copies it (=dup) and destroys it at the end."""
    with let:
        d = c.copy()
    echo(string("  peek: rc ") + str(rc(b)) + string(", token ") + str(load(d)))
    return load(d)


def _consume(b: sink @ TokenBuf) -> nint:
    """A sink parameter: the buffer moves in and dies at the end of the proc."""
    return b.len


if comptime(__name__ == "__main__"):
    def _main():
        with var:
            b = createTokenBuf(4)
        for i in range(3):
            b.add(NifToken(i * 10))
        echo(string("built: rc ") + str(rc(b)))
        with var:
            c = beginRead(b)
        echo(string("one cursor: rc ") + str(rc(b)))
        _ = _peek(b, c)
        echo(string("after peek: rc ") + str(rc(b)))
        # a mutation while a cursor reads: the buffer copies its tokens and lets go of the owner
        b.add(NifToken(30))
        echo(string("after add: owner nil "), isNil(b.owner), string(", cursor still reads "), load(c))
        with var:
            c2 = beginRead(b)
        echo(string("second owner: rc ") + str(rc(b)) + string(", frees ") + str(_gStats.frees))
        endRead(c)
        echo(string("after endRead: frees "), _gStats.frees, string(", owner nil "), isNil(c.owner))
        endRead(c2)
        # no cursor left: a mutation reclaims the owner header in place
        b.add(NifToken(40))
        echo(string("reclaimed: owner nil "), isNil(b.owner), string(", frees "), _gStats.frees, string(", len "), b.len)
        with var:
            moved = move(b)
        echo(string("moved: len ") + str(moved.len) + string(", source len ") + str(b.len))
        echo(string("consumed: ") + str(_consume(move(moved))))

    _main()
    echo(string("at exit: frees ") + str(_gStats.frees))
