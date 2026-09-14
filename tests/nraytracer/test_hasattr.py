import sys
sys.path.insert(0, '../../src')
from nimic.ntypesystem import uint8, Ntype, NScalar, DICT_OF_C_TYPES

parent = (DICT_OF_C_TYPES['uint8'] * 2)()
obj = uint8._n_on_array(parent, 1)

print("hasattr:", hasattr(obj, '_n_view'))
if hasattr(obj, '_n_view'):
    print("_n_view:", obj._n_view)
else:
    print("No _n_view")
