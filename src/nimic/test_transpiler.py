from __future__ import annotations
import inspect as ins

from nimic import transpiler
from nimic.ntypes import *
   
def foo():
    with var:
        a = array[int, 10]()
        b = ch("#")
    return a

@ptr
class Frame(Object):
    Y: nint

src = ins.getsource(foo)
aast = transpiler.parse(src)

nim_src, modules_names = transpiler.unparse(aast)
print(nim_src)
pass