import sys
sys.path.insert(0, 'tests/nraytracer')
from nimic.ntypesystem import ByteAddress, intp, pointer, UncheckedArray, cstring, NilPtr, DICT_OF_C_TYPES

original_ptr_cast = UncheckedArray._n_ptr_cast

@classmethod
def patched_ptr_cast(cls, instance):
    import ctypes
    if isinstance(instance, pointer):
        v = getattr(instance.contents, '_n_view', None)
    else:
        v = getattr(instance, '_n_view', None)
    
    if v is None:
        print(f"DEBUG info: instance is {instance}, type is {type(instance)}, v is None")
    
    try:
        return original_ptr_cast.__func__(cls, instance)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e

UncheckedArray._n_ptr_cast = patched_ptr_cast

import converter_ppm_to_mp4
converter_ppm_to_mp4.main()
