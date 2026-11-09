"""Nim std/widestrs — UTF-16 strings for the Windows API: newWideCString(s) (Nim 2.2.4's
lib/std/widestrs.nim), `$` back to a string. A WideCStringObj holds its NUL-terminated UTF-16 buffer (ctypes:
`value` is what a `wchar_t*` parameter of std/winlean takes on Windows)."""
from __future__ import annotations
import ctypes as _ctypes

from nimic.ntypes import nint
from nimic.ntypesystem import _n_encode_str


class WideCStringObj:
    """Nim: WideCStringObj (a WideCString that owns its buffer)."""

    def __init__(self, text: str) -> None:
        self._n_text = text
        self._n_buffer = _ctypes.create_unicode_buffer(text)

    @property
    def value(self):
        """The buffer, for a `wchar_t*` argument."""
        return self._n_buffer

    def len(self) -> nint:
        """Nim: the number of UTF-16 code units, without the terminating 0."""
        return nint(len(self._n_text.encode("utf-16-le")) // 2)

    def __str__(self) -> str:
        """Nim: `$` (str(w))."""
        return self._n_text


WideCString = WideCStringObj


def newWideCString(s) -> WideCStringObj:
    """Nim: newWideCString — s (UTF-8 bytes, as a Nim string holds them) as a NUL-terminated UTF-16 string."""
    return WideCStringObj(_n_encode_str(s).decode("utf-8", errors="replace"))

