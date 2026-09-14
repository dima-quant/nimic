import sys
sys.path.insert(0, '../../src')
from nimic.ntypesystem import uint8, Ntype, NScalar, DICT_OF_C_TYPES, pointer, addr

parent = (DICT_OF_C_TYPES['uint8'] * 2)()
obj = uint8._n_on_array(parent, 1)

p = addr(obj)
print("hasattr p:", hasattr(p, '_n_view'))
if hasattr(p, '_n_view'):
    print("_n_view p:", p._n_view)
    import ctypes
    # test addressof
    try:
        print("addressof:", ctypes.addressof(p._n_view))
    except Exception as e:
        print("Error ctypes:", e)
else:
    print("No _n_view on p")
