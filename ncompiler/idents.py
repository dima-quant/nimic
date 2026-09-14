from __future__ import annotations
from nimic.ntypes import *
from nimic.std.hashes import *

from wordrecg import *


class PIdent: pass

class TIdent(Object):
    """{.acyclic.}"""
    id: int # unique id; use this for comparisons and not the pointers
    s: string
    next: PIdent             # for hash-table chaining
    h: Hash                 # hash value of s

@ref
class PIdent(TIdent):
    def __eq__(self, other: object) -> bool:
        """{.inline.}"""
        if self is None or other is None:
            return self is other
        return self.id == other.id

@ref
class IdentCache(Object):
    buckets: array[8192, PIdent]
    wordCounter: int
    idAnon: PIdent
    idDelegator: PIdent
    emptyIdent: PIdent

def resetIdentCache() -> None:
    pass

def cmpIgnoreStyle(a: cstring, b: cstring, blen: int) -> int:
    if a[0] != b[0]: return 1
    i = 0
    j = 0
    result = 1
    while j < blen:
        while a[i] == '_': i += 1
        while b[j] == '_': j += 1
        # tolower inlined:
        aa = a[i]
        bb = b[j]
        if aa >= 'A' and aa <= 'Z': aa = chr(ord(aa) + (ord('a') - ord('A')))
        if bb >= 'A' and bb <= 'Z': bb = chr(ord(bb) + (ord('a') - ord('A')))
        result = ord(aa) - ord(bb)
        if (result != 0) or (aa == '\0'): break
        i += 1
        j += 1
    if result == 0:
        if a[i] != '\0': result = 1
    return result

def _cmpExact(a: cstring, b: cstring, blen: int) -> int:
    i = 0
    j = 0
    result = 1
    while j < blen:
        aa = a[i]
        bb = b[j]
        result = ord(aa) - ord(bb)
        if (result != 0) or (aa == '\0'): break
        i += 1
        j += 1
    if result == 0:
        if a[i] != '\0': result = 1
    return result

@dispatch
def getIdent(ic: IdentCache, identifier: cstring, length: int, h: Hash) -> PIdent:
    idx = int(h) & high(ic.buckets)
    result = ic.buckets[idx]
    last = None
    id = 0
    while result is not None:
        if _cmpExact(cstring(result.s), identifier, length) == 0:
            if last is not None:
                # make access to last looked up identifier faster:
                last.next = result.next
                result.next = ic.buckets[idx]
                ic.buckets[idx] = result
            return result
        elif cmpIgnoreStyle(cstring(result.s), identifier, length) == 0:
            assert (id == 0) or (id == result.id)
            id = result.id
        last = result
        result = result.next
    
    result = PIdent(
        h=h,
        s=string(str(identifier)[:length]),
        next=ic.buckets[idx]
    )
    ic.buckets[idx] = result
    if id == 0:
        ic.wordCounter += 1
        result.id = -ic.wordCounter
    else:
        result.id = id
    return result

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
    # initialize the keywords:
    for s in inrange(succ(low(TSpecialWord)), high(TSpecialWord)):
        getIdent(result, string(str(s)), hashIgnoreStyle(string(str(s)))).id = nord(s)
    return result

def whichKeyword(id: PIdent) -> TSpecialWord:
    if id.id < 0: return TSpecialWord.wInvalid
    else: return TSpecialWord(id.id)

@dispatch
def hash(x: PIdent) -> Hash:
    """{.inline.}"""
    return x.h

if comptime(__name__ == "__main__"):
    print("Running idents.py tests...")
    ic = newIdentCache()

    # Basic identifier creation and case-insensitive matching
    id1 = getIdent(ic, string("foo"))
    id2 = getIdent(ic, string("fOo"))
    assert id1.id == id2.id, f"style-insensitive ids should match: {id1.id} vs {id2.id}"
    assert id1 is not id2, "different strings should produce different PIdent objects"

    # Keyword recognition via whichKeyword
    keyword = getIdent(ic, string("yield"))
    assert whichKeyword(keyword) == TSpecialWord.wYield
    keyword2 = getIdent(ic, string("addr"))
    assert whichKeyword(keyword2) == TSpecialWord.wAddr

    # hash function
    assert hash(id1) == id1.h

    # PIdent equality — same id means equal
    assert id1 == id1
    assert id1 == id2, "identifiers with same id should be equal"
    id_different = getIdent(ic, string("bar"))
    assert not (id1 == id_different), "identifiers with different ids should not be equal"

    # whichKeyword with user-defined (negative id) identifier
    user_id = getIdent(ic, string("myCustomIdent"))
    assert user_id.id < 0, f"user-defined identifier should have negative id: {user_id.id}"
    assert whichKeyword(user_id) == TSpecialWord.wInvalid

    # cmpIgnoreStyle tests
    assert cmpIgnoreStyle(cstring("foo"), cstring("foo"), 3) == 0
    assert cmpIgnoreStyle(cstring("foo"), cstring("fOo"), 3) == 0
    assert cmpIgnoreStyle(cstring("foo"), cstring("bar"), 3) != 0
    assert cmpIgnoreStyle(cstring("foo_bar"), cstring("fooBar"), 6) == 0

    # cmpExact tests (renamed to _cmpExact — not exported in Nim)
    assert _cmpExact(cstring("foo"), cstring("foo"), 3) == 0
    assert _cmpExact(cstring("foo"), cstring("fOo"), 3) != 0
    assert _cmpExact(cstring("foo"), cstring("foobar"), 3) == 0, "only first blen chars compared"

    # Hash-table move-to-front: looking up same identifier again should work
    id1_again = getIdent(ic, string("foo"))
    assert id1_again is id1, "exact match should return same PIdent object"

    # IdentCache initialization IDs — now matching Nim init order
    assert ic.idAnon.id == -1, f"idAnon.id should be -1, got {ic.idAnon.id}"
    assert ic.idDelegator.id == -2, f"idDelegator.id should be -2, got {ic.idDelegator.id}"
    assert ic.emptyIdent.id == -3, f"emptyIdent.id should be -3, got {ic.emptyIdent.id}"

    # resetIdentCache (should be callable, is a no-op)
    resetIdentCache()

    print("idents.py extensive tests passed!")

