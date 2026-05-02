from __future__ import annotations
"""nimpy/raw_buffers — Python shim for Nim's nimpy/raw_buffers module.

Provides RawPyBuffer and the getBuffer / release helpers.
In Nim, `image.getBuffer(buf, flags)` is UFCS for `getBuffer(image, buf, flags)`.
In nimic Python we define `getBuffer` as a standalone function so the transpiler
emits the correct Nim UFCS call.
"""
import ctypes

from nimic.ntypesystem import Object, pointer
from nimic.nimpy.py_types import Py_ssize_t


class RawPyBuffer(Object):
    """Nim nimpy.RawPyBuffer — wraps CPython's Py_buffer struct.

    Fields:
        buf:   pointer to raw data
        shape: pointer to shape array (cast to ptr[UncheckedArray[Py_ssize_t]])
    """
    buf: pointer
    shape: pointer


def getBuffer(obj, buf, flags=0):
    """Populate *buf* from *obj*'s buffer protocol (numpy ndarray or memoryview).

    Transpiles to Nim's ``obj.getBuffer(buf, flags)`` via UFCS.
    """
    # --- numpy path (most common) ---
    if hasattr(obj, 'ctypes') and hasattr(obj, 'shape'):
        data_addr = obj.ctypes.data                     # int address
        ndim = obj.ndim

        # Create a ctypes array holding the shape dimensions
        ShapeArray = ctypes.c_ssize_t * ndim
        shape_arr = ShapeArray(*obj.shape)

        # Populate buf fields
        data_ptr = pointer()
        data_ptr._n_addr = data_addr
        buf.buf = data_ptr

        shape_ptr = pointer()
        shape_ptr._n_addr = ctypes.addressof(shape_arr)
        buf.shape = shape_ptr

        # prevent GC of the backing shape array
        buf._shape_backing = shape_arr
        return

    # --- generic buffer-protocol path (memoryview) ---
    mv = memoryview(obj)
    c_buf = (ctypes.c_char * mv.nbytes).from_buffer(mv)

    data_ptr = pointer()
    data_ptr._n_addr = ctypes.addressof(c_buf)
    buf.buf = data_ptr

    shape_tuple = mv.shape
    ShapeArray = ctypes.c_ssize_t * len(shape_tuple)
    shape_arr = ShapeArray(*shape_tuple)

    shape_ptr = pointer()
    shape_ptr._n_addr = ctypes.addressof(shape_arr)
    buf.shape = shape_ptr

    # prevent GC — these are views, not owned allocations
    buf._shape_backing = shape_arr
    buf._mv_backing = c_buf


def release(buf):
    """Release the buffer references.  Transpiles to ``buf.release()``."""
    buf._shape_backing = None
    buf._mv_backing = None
