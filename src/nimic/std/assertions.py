from __future__ import annotations

def raiseAssert(msg: str):
    raise AssertionError(msg)

def failedAssertImpl(msg: str):
    raise AssertionError(msg)

def doAssertRaises(exception: type, code):
    pass
