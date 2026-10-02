import sys
sys.path.insert(0, 'tests/nraytracer')
from tests.nimic.test_ntypes import TestNTypes
import nimic.ntypesystem as nsys

original_ptr_cast = nsys._Object._n_ptr_cast

@classmethod
def patched_ptr_cast(cls, instance):
    try:
        return original_ptr_cast.__func__(cls, instance)
    except Exception as e:
        import traceback, ctypes
        if isinstance(instance, nsys.ByteAddress):
            address = instance._n_view
            print(f"DEBUG info: instance is ByteAddress, address={address}, type(address)={type(address)}")
        raise e

nsys._Object._n_ptr_cast = patched_ptr_cast

TestNTypes('test_pointer_arithmetic_cast').test_pointer_arithmetic_cast()
