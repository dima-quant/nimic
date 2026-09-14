from __future__ import annotations
import sys
sys.path.insert(0, '../../../src')
from nimic.ntypesystem import *
from nimic.ntypes import *
import ctypes

class MyObj(Object):
    x: int32
    y: int32

try:
    obj = MyObj(x=10, y=20)
    p = addr(obj)
    print("p.contents.x =", p.contents.x)
    print("p.x =", p.x) # Transparent deref

    up = uintp(p)
    print("uintp created!")
except Exception as e:
    import traceback
    traceback.print_exc()

