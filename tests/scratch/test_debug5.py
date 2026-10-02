import sys
sys.path.insert(0, 'tests/nraytracer')
from h264 import *
from minimp4 import *
from nimic.ntypes import cast
from nimic.ntypesystem import pointer, intp, uint8, ByteAddress, addr

v = _MiniMp4Vector()
pv = addr(v)
_ = _vectorInit(pv, 1024)

print("h.data:", pv.contents.data)
ip = cast[intp](pv.contents.data)
print("intp:", ip)
ip2 = ip + pv.contents.bytes
print("ip2:", ip2)
try:
    print('Testing uint8._n_ptr_cast directly:')
    print(uint8._n_ptr_cast(ip2))
except Exception as e:
    import traceback
    traceback.print_exc()

try:
    print("Doing cast[ptr[uint8]]...")
    result = cast[ptr[uint8]](ip2)
    print("result:", result)
except Exception as e:
    import traceback
    traceback.print_exc()

