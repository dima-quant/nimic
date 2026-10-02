# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.hashes import *

from .wordrecg import *


class TIdent(Object):
    """{.acyclic.}"""
    id: nint # unique id; use this for comparisons and not the pointers
    s: string
    next: PIdent             # for hash-table chaining
    h: Hash                 # hash value of s

@ref
class PIdent(TIdent): pass

@ref
class IdentCache(Object):
    buckets: array[8192, PIdent]
    wordCounter: nint
    idAnon: PIdent
    idDelegator: PIdent
    emptyIdent: PIdent

def resetIdentCache() -> None:
    discard

def cmpIgnoreStyle(a: cstring, b: cstring, blen: nint) -> nint:
    if a[0] != b[0]: return 1
    with var:
        i = 0
        j = 0
    result = 1
    while j < blen:
        while a[i] == ch('_'): i += 1
        while b[j] == ch('_'): j += 1
        with var:
            aa = a[i]
            bb = b[j]
        if aa >= ch('A') and aa <= ch('Z'): aa = chr(ord(aa) + (ord(ch('a')) - ord(ch('A'))))
        if bb >= ch('A') and bb <= ch('Z'): bb = chr(ord(bb) + (ord(ch('a')) - ord(ch('A'))))
        result = ord(aa) - ord(bb)
        if (result != 0) or (aa == ch('\0')): break
        i += 1
        j += 1
    if result == 0:
        if a[i] != ch('\0'): result = 1
    return result

def _cmpExact(a: cstring, b: cstring, blen: nint) -> nint:
    with var:
        i = 0
        j = 0
    result = 1
    while j < blen:
        with var:
            aa = a[i]
            bb = b[j]
        result = ord(aa) - ord(bb)
        if (result != 0) or (aa == ch('\0')): break
        i += 1
        j += 1
    if result == 0:
        if a[i] != ch('\0'): result = 1
    return result

@dispatch
def getIdent(ic: IdentCache, identifier: cstring, length: nint, h: Hash) -> PIdent:
    with var:
        idx = nint(h) & high(ic.buckets)
        res = ic.buckets[idx]
        last: PIdent = None
        id = 0
    while res is not None:
        if _cmpExact(cstring(res.s), identifier, length) == 0:
            if last is not None:
                last.next = res.next
                res.next = ic.buckets[idx]
                ic.buckets[idx] = res
            return res
        elif cmpIgnoreStyle(cstring(res.s), identifier, length) == 0:
            assert (id == 0) or (id == res.id)
            id = res.id
        last = res
        res = res.next

    with var:
        new_res = PIdent(
            h=h,
            s=substr(str(identifier), 0, length - 1),
            next=ic.buckets[idx]
        )
    ic.buckets[idx] = new_res
    if id == 0:
        ic.wordCounter += 1
        new_res.id = -ic.wordCounter
    else:
        new_res.id = id
    return new_res

@dispatch
def getIdent(ic: IdentCache, identifier: string) -> PIdent:
    return getIdent(ic, cstring(identifier), len(identifier), hashIgnoreStyle(identifier))

@dispatch
def getIdent(ic: IdentCache, identifier: string, h: Hash) -> PIdent:
    return getIdent(ic, cstring(identifier), len(identifier), h)

def newIdentCache() -> IdentCache:
    result = IdentCache(wordCounter=0)
    result.idAnon = getIdent(result, string(":anonymous"))
    result.wordCounter = 1
    result.idDelegator = getIdent(result, string(":delegator"))
    result.emptyIdent = getIdent(result, string(""))
    for s in inrange(succ(low(TSpecialWord)), high(TSpecialWord)):
        getIdent(result, string(str(s)), hashIgnoreStyle(string(str(s)))).id = ord(s)
    return result

def whichKeyword(id: PIdent) -> TSpecialWord:
    if id.id < 0: return TSpecialWord.wInvalid
    else: return TSpecialWord(id.id)

@dispatch
def hash(x: PIdent) -> Hash:
    """{.inline.}"""
    return x.h

if comptime(__name__ == "__main__"):
    with var:
        ic = newIdentCache()
        id1 = getIdent(ic, string("foo"))
        id2 = getIdent(ic, string("fOo"))
    assert id1.id == id2.id
    assert id1.s != id2.s

    with var:
        keyword = getIdent(ic, string("yield"))
    assert whichKeyword(keyword) == TSpecialWord.wYield
    with var:
        keyword2 = getIdent(ic, string("addr"))
    assert whichKeyword(keyword2) == TSpecialWord.wAddr

    assert hash(id1) == id1.h

    with var:
        id_different = getIdent(ic, string("bar"))
    assert id1.id != id_different.id

    with var:
        user_id = getIdent(ic, string("myCustomIdent"))
    assert user_id.id < 0
    assert whichKeyword(user_id) == TSpecialWord.wInvalid

    assert cmpIgnoreStyle(cstring("foo"), cstring("foo"), 3) == 0
    assert cmpIgnoreStyle(cstring("foo"), cstring("fOo"), 3) == 0
    assert cmpIgnoreStyle(cstring("foo"), cstring("bar"), 3) != 0
    assert cmpIgnoreStyle(cstring("foo_bar"), cstring("fooBar"), 6) == 0

    assert _cmpExact(cstring("foo"), cstring("foo"), 3) == 0
    assert _cmpExact(cstring("foo"), cstring("fOo"), 3) != 0
    assert _cmpExact(cstring("foo"), cstring("foobar"), 3) == 0

    with var:
        id1_again = getIdent(ic, string("foo"))
    assert id1_again.id == id1.id

    assert ic.idAnon.id == -1
    assert ic.idDelegator.id == -2
    assert ic.emptyIdent.id == -3

    resetIdentCache()
    echo("idents tests passed!")
