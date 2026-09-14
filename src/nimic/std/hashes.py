from __future__ import annotations
import builtins
from nimic.ntypesystem import dispatch

class Hash(int):
    pass

@dispatch
def hash(x: object) -> Hash:
    return Hash(builtins.hash(x))

@dispatch
def hashIgnoreStyle(x: string) -> Hash:
    s = str(x).replace("_", "").lower()
    return Hash(builtins.hash(s))
