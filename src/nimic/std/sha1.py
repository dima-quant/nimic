"""Nim std/sha1 — SHA-1 (the API of Nim 2.2.4's lib/std/sha1.nim, deprecated there in favor of the checksums
package, but what nimony imports): Sha1State, newSha1State, update, finalize, Sha1Digest, SecureHash, secureHash,
secureHashFile, `$`, parseSecureHash, `==`, isValidSha1Hash. The digest is computed by Python's hashlib (SHA-1
is SHA-1: the same bytes as Nim's)."""
from __future__ import annotations
import hashlib as _hashlib

from nimic.ntypes import Object, array, distinct, string, uint8
from nimic.ntypesystem import _n_encode_str

Sha1DigestSize = 20

Sha1Digest = array[Sha1DigestSize, uint8]


@distinct
class SecureHash(Sha1Digest):
    """A SHA-1 hash (distinct Sha1Digest); `$` is its hexadecimal spelling."""

    def __str__(self) -> str:
        """Nim: `$` — the hash as 40 uppercase hexadecimal digits."""
        return "".join(f"{int(v):02X}" for v in self)

    def __eq__(self, other) -> bool:
        """Nim: `==` — the same 20 bytes."""
        return isinstance(other, SecureHash) and [int(v) for v in self] == [int(v) for v in other]

    __hash__ = None


class Sha1State(Object):
    """The state of a SHA-1 computation (update, then finalize)."""


def _n_hasher(ctx: Sha1State):
    h = ctx.__dict__.get("_n_sha1")
    if h is None:
        h = ctx.__dict__["_n_sha1"] = _hashlib.sha1()
    return h


def newSha1State() -> Sha1State:
    """Creates a Sha1State."""
    return Sha1State()


def _n_bytes(data) -> bytes:
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, str):
        return _n_encode_str(data)
    return bytes(ord(str(c)) if not isinstance(c, int) else c for c in data)  # an openArray[char]


def update(ctx: Sha1State, data) -> None:
    """Updates the state with the chars of data (a string or an openArray[char])."""
    _n_hasher(ctx).update(_n_bytes(data))


def finalize(ctx: Sha1State) -> Sha1Digest:
    """Finalizes the state and returns the Sha1Digest."""
    digest = _n_hasher(ctx).digest()
    return Sha1Digest([uint8(b) for b in digest])


def _n_secure(digest) -> SecureHash:
    return SecureHash([uint8(int(b)) for b in digest])


def secureHash(str_: object) -> SecureHash:
    """Generates the SecureHash of a string (or openArray[char])."""
    state = newSha1State()
    update(state, str_)
    return _n_secure(finalize(state))


def secureHashFile(filename: string) -> SecureHash:
    """Generates the SecureHash of a file's content."""
    with open(str(filename), "rb") as f:
        return _n_secure(_hashlib.sha1(f.read()).digest())


def parseSecureHash(hash: string) -> SecureHash:
    """Converts a hexadecimal spelling (40 digits) to a SecureHash."""
    text = str(hash)
    return _n_secure(int(text[i * 2:i * 2 + 2], 16) for i in range(Sha1DigestSize))


def isValidSha1Hash(s: string) -> bool:
    """Checks if a string is a valid sha1 hash sum: 40 hexadecimal digits."""
    text = str(s)
    return len(text) == 40 and all(c in "0123456789abcdefABCDEF" for c in text)
