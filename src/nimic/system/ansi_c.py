"""Nim system/ansi_c — C interop types: csize_t, CPointer, c_malloc, c_free."""
import ctypes
# from ctypes import c_size_t
from ..ntypesystem import Ntype, NInteger

class csize_t(NInteger): _n_bits, _n_signed, _n_rank = 64, False, 7

class CPointer(Ntype):
    """
    Create Ntype wrapper around ctype buffer
    """
    def __init__(self, x):
        self._n_buffer = x
        self._n_view = x

def c_malloc(size: csize_t):
    return CPointer((ctypes.c_char * size._n_get_value())())

def c_free(p: CPointer):
    p._n_buffer = None