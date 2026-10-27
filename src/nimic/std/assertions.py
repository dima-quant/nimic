from __future__ import annotations
from nimic.ntypes import raiseAssert  # system's (Nim 2 moved it here): one proc, not a second copy

def failedAssertImpl(msg: str):
    raise AssertionError(msg)

def doAssertRaises(exception: type, code):
    pass
