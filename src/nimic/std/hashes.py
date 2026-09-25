from __future__ import annotations
import builtins


from nimic.ntypesystem import dispatch


class Hash(int):
    pass


@dispatch
def hash(x: tuple) -> Hash:
    return Hash(builtins.hash(x))


@dispatch
def hash(x: str) -> Hash:
    return Hash(builtins.hash(x))


@dispatch
def hash(x: int) -> Hash:
    return Hash(builtins.hash(x))


@dispatch
def hash(x: object) -> Hash:
    return Hash(builtins.hash(x))


def hashIgnoreStyle(x) -> Hash:
    s = str(x).replace("_", "").lower()
    return Hash(builtins.hash(s))


hash_ignore_style = hashIgnoreStyle
