"""
ncompiler/idents.py — Identifier cache and interning
Converted from compiler/idents.nim
"""
from __future__ import annotations
from ncompiler.wordrecg import findStr, TSpecialWord


# --- Hash type ---
Hash = int


def hashIgnoreStyle(s: str, start: int = 0, length: int = -1) -> Hash:
    """Nim-style identifier hash: case-insensitive, ignores underscores."""
    h = 0
    end = len(s) if length < 0 else min(start + length, len(s))
    i = start
    while i < end:
        c = s[i]
        if c == '_':
            i += 1
            continue
        if 'A' <= c <= 'Z':
            c = chr(ord(c) + 32)
        h = h ^ (h << 6) + (h >> 2) + ord(c) + 0x9e3779b9
        h &= 0xFFFFFFFF
        i += 1
    return h


def cmpIgnoreStyle(a: str, b: str) -> int:
    """Compare two identifiers Nim-style (case-insensitive, ignore underscores)."""
    ai, bi = 0, 0
    while True:
        while ai < len(a) and a[ai] == '_':
            ai += 1
        while bi < len(b) and b[bi] == '_':
            bi += 1
        if ai >= len(a):
            return 0 if bi >= len(b) else -1
        if bi >= len(b):
            return 1
        ca = a[ai].lower()
        cb = b[bi].lower()
        if ca != cb:
            return -1 if ca < cb else 1
        ai += 1
        bi += 1


# --- PIdent ---
class PIdent:
    """Interned identifier with cached hash and id."""
    __slots__ = ('id', 's', 'next', 'h')
    def __init__(self, s: str = "", h: Hash = 0, id: int = 0):
        self.s = s
        self.h = h
        self.id = id
        self.next: PIdent | None = None

    def __repr__(self):
        return f"PIdent({self.s!r}, id={self.id})"

    def __eq__(self, other):
        if other is None:
            return False
        if not isinstance(other, PIdent):
            return NotImplemented
        return self.id == other.id

    def __hash__(self):
        return self.id


# --- IdentCache ---
class IdentCache:
    """Hash-based identifier interning table."""
    def __init__(self):
        self._buckets: list[PIdent | None] = [None] * 4096
        self._uid = 0
        # Pre-register all special words from wordrecg
        for w in TSpecialWord:
            from ncompiler.wordrecg import specialWordToStr
            s = specialWordToStr(w)
            if s:
                self.getIdent(s)

    def getIdent(self, s: str, h: Hash | None = None) -> PIdent:
        """Intern a string, returning the canonical PIdent."""
        if h is None:
            h = hashIgnoreStyle(s)
        idx = h & (len(self._buckets) - 1)
        result = self._buckets[idx]
        while result is not None:
            if result.h == h and cmpIgnoreStyle(result.s, s) == 0:
                return result
            result = result.next
        # Not found — create new
        self._uid += 1
        new_ident = PIdent(s=s, h=h, id=self._uid)
        new_ident.next = self._buckets[idx]
        self._buckets[idx] = new_ident
        return new_ident

    def getIdentFromBytes(self, buf: bytes, start: int, length: int, h: Hash) -> PIdent:
        """Get ident from a byte buffer slice."""
        s = buf[start:start+length].decode('utf-8', errors='replace')
        return self.getIdent(s, h)


def newIdentCache() -> IdentCache:
    return IdentCache()


def whichKeyword(ident: PIdent) -> TSpecialWord:
    """Look up whether an identifier is a keyword."""
    return findStr(ident.s)
