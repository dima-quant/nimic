from __future__ import annotations
from nimic.ntypes import *

def ref(cls):
    cls._n_is_ref = True
    return cls

nobject = Object

class PIdent: pass

class TIdent(nobject):
    id: int
    s: string
    next: PIdent

@ref
class PIdent(TIdent):
    pass

class IdentCache(nobject):
    buckets: array[2, PIdent]

ic = IdentCache()
print("ic initialized successfully!")
print("ic.buckets[0]:", ic.buckets[0])
