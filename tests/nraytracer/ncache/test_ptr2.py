from __future__ import annotations
import sys
sys.path.insert(0, '../../../src')
from nimic.ntypesystem import *
from nimic.ntypes import *

class MyObj(Object):
    x: int32
    y: int32

obj = MyObj(x=10, y=20)
p = addr(obj)
print("type of p:", type(p))
print("p.x =", p.x)
up = uintp(p)
print("uintp created via ByteAddress successfully!")
