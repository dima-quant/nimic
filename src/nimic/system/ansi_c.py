"""Nim system/ansi_c — C interop types: csize_t, cint, cuint, c_malloc, c_free, c_realloc, copy_mem, zero_mem, cmp_mem."""
import ctypes
from ..ntypesystem import Ntype, NInteger, pointer, byte_buffer, BUFFER_REGISTRY


class csize_t(NInteger): _n_bits, _n_signed, _n_rank = 64, False, 7
class cint(NInteger): _n_bits, _n_signed, _n_rank = 32, True, 4
class cuint(NInteger): _n_bits, _n_signed, _n_rank = 32, False, 4


def c_malloc(size):
    n = int(size._n_get_value()) if hasattr(size, '_n_get_value') else int(size)
    buf = (ctypes.c_char * n)()
    BUFFER_REGISTRY.register(buf)
    return pointer(byte_buffer(buf))

def c_free(p):
    if isinstance(p, pointer) and p._n_addr != 0:
        BUFFER_REGISTRY.free(p._n_addr)
        p._n_addr = 0
        p._n_contents_cache = None

def c_realloc(p, size):
    """Allocate new buffer, copy old data, return new pointer."""
    n = int(size._n_get_value()) if hasattr(size, '_n_get_value') else int(size)
    new_buf = (ctypes.c_char * n)()
    BUFFER_REGISTRY.register(new_buf)
    if isinstance(p, pointer) and p._n_addr != 0:
        # Find old buffer to determine copy size
        old_buf = BUFFER_REGISTRY.find_buffer_for_address(p._n_addr)
        if old_buf is not None:
            old_size = ctypes.sizeof(old_buf)
            copy_size = min(old_size, n)
            ctypes.memmove(new_buf, p._n_addr, copy_size)
        BUFFER_REGISTRY.free(p._n_addr)
    return pointer(byte_buffer(new_buf))

def copy_mem(dst, src, size: int):
    """Copy size bytes from src to dst."""
    n = int(size._n_get_value()) if hasattr(size, '_n_get_value') else int(size)
    dst_addr = dst._n_addr if isinstance(dst, pointer) else ctypes.addressof(dst)
    src_addr = src._n_addr if isinstance(src, pointer) else ctypes.addressof(src)
    ctypes.memmove(dst_addr, src_addr, n)

def zero_mem(dst, size: int):
    """Zero size bytes at dst."""
    n = int(size._n_get_value()) if hasattr(size, '_n_get_value') else int(size)
    dst_addr = dst._n_addr if isinstance(dst, pointer) else ctypes.addressof(dst)
    ctypes.memset(dst_addr, 0, n)

def cmp_mem(a, b, size: int) -> int:
    """Compare size bytes — returns 0 if equal, nonzero otherwise."""
    n = int(size._n_get_value()) if hasattr(size, '_n_get_value') else int(size)
    a_addr = a._n_addr if isinstance(a, pointer) else ctypes.addressof(a)
    b_addr = b._n_addr if isinstance(b, pointer) else ctypes.addressof(b)
    a_bytes = (ctypes.c_char * n).from_address(a_addr)
    b_bytes = (ctypes.c_char * n).from_address(b_addr)
    for i in range(n):
        if a_bytes[i] != b_bytes[i]:
            return 1 if a_bytes[i] > b_bytes[i] else -1
    return 0

def alloc_shared0(size):
    """Nim: allocShared0 — allocate zero-initialized shared memory."""
    return c_malloc(size)

def dealloc_shared(p):
    """Nim: deallocShared — free shared memory."""
    c_free(p)

# camelCase aliases for Nim compatibility ??
allocShared0 = alloc_shared0
deallocShared = dealloc_shared