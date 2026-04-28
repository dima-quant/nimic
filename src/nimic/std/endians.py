"""Nim std/endians — byte-order conversion."""
import struct
import ctypes
from nimic.ntypesystem import uintp, pointer

def _get_addr(obj):
    # If the obj itself is a pointer (from addr() or cast[pointer]()), we just take its integer address
    if isinstance(obj, pointer):
        return obj._n_addr
    
    # If it's some other numeric value passed directly, return it
    if isinstance(obj, int):
        return obj
    
    # Check if object has _n_view (like an Object, seq, or UncheckedArray)
    if hasattr(obj, '_n_view') and obj._n_view is not None:
        return ctypes.addressof(obj._n_view)
    
    # For actual ctypes instances passed directly
    if hasattr(obj, 'value') and isinstance(obj.value, int):
        return obj.value
        
    return ctypes.addressof(obj)

def big_endian32(dst: pointer, src: pointer):
    src_addr = _get_addr(src)
    dst_addr = _get_addr(dst)
    
    val = ctypes.cast(src_addr, ctypes.POINTER(ctypes.c_uint32))[0]
    # In struct: '<I' is little-endian, '>I' is big-endian
    # We want to ensure the memory at dst has big-endian bytes of the value at src (assuming host is little-endian)
    val_swapped = struct.unpack('<I', struct.pack('>I', val))[0]
    ctypes.cast(dst_addr, ctypes.POINTER(ctypes.c_uint32))[0] = val_swapped

def little_endian32(dst: pointer, src: pointer):
    src_addr = _get_addr(src)
    dst_addr = _get_addr(dst)
    
    val = ctypes.cast(src_addr, ctypes.POINTER(ctypes.c_uint32))[0]
    # Assuming host is little-endian, little_endian32 is basically a memory copy of 4 bytes
    ctypes.cast(dst_addr, ctypes.POINTER(ctypes.c_uint32))[0] = val
