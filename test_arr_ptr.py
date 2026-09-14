from __future__ import annotations
from nimic.ntypes import *
from nimic.std.hashes import *

class TIdent(Object):
    id: int
    s: string
    next: TIdent
    h: Hash

TIdent._n_python_fields.remove('next')

PIdent = TIdent

class IdentCache(Object):
    buckets: array[2, PIdent]

ic = IdentCache()
print("ic initialized successfully!")
print("ic.buckets[0].next:", getattr(ic.buckets[0], "next", None))
