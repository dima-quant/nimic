from nimic.ntypesystem import ByteAddress, intp, pointer, _Object, cstring, NilPtr, DICT_OF_C_TYPES

# Let's see what address ByteAddress gives.

def patched_n_ptr_cast(cls, instance):
    import ctypes
    if isinstance(instance, NilPtr) or instance is None:
        return NilPtr(cls.__name__)
    if isinstance(instance, pointer):
        if not hasattr(instance, 'contents') or getattr(instance.contents, '_n_view', None) is None:
            return NilPtr(cls.__name__)
        address = ctypes.addressof(instance.contents._n_view)
    elif isinstance(instance, ByteAddress):
        if isinstance(instance._n_view, int):
            address = instance._n_view
        elif hasattr(instance._n_view, 'value') and isinstance(instance._n_view.value, int):
            address = instance._n_view.value
        else:
            address = ctypes.addressof(instance._n_view)
    else:
        address = ctypes.addressof(instance)
    
    class_name = cls.__name__
    if class_name in DICT_OF_C_TYPES:
        c_type = DICT_OF_C_TYPES[class_name]
        c_instance = c_type.from_address(address)
        obj = cls.__new__(cls)
        obj._n_buffer = instance.contents._n_buffer if hasattr(instance, 'contents') and hasattr(instance.contents, '_n_buffer') else getattr(instance, '_n_buffer', None)
        obj._n_view = c_instance
        obj._n_has_c_type = True
        obj._n_annotations = cls.__annotations__
        return obj
    return None

import nothing # this will fail, it's ok, just to check if syntax is good
