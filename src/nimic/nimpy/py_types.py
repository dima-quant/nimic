"""nimpy/py_types — Python shims for Nim's nimpy py_types module.

Provides Py_ssize_t and buffer protocol flag constants.
"""
import ctypes
from nimic.ntypesystem import NInteger, DICT_OF_TYPES, DICT_OF_C_TYPES


class Py_ssize_t(NInteger):
    """Nim's Py_ssize_t — platform signed size type (maps to ssize_t)."""
    _n_bits, _n_signed, _n_rank = 64, True, 8

# Manually register since NInteger direct subclasses skip auto-registration
DICT_OF_TYPES["Py_ssize_t"] = Py_ssize_t
DICT_OF_C_TYPES["Py_ssize_t"] = ctypes.c_int64


# Buffer protocol flags (CPython values)
PyBUF_SIMPLE   = 0x0000
PyBUF_WRITABLE = 0x0001
PyBUF_ND       = 0x0008
