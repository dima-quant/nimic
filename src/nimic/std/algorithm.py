# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'sort'
]

@dispatch
def sort(s: mut @ seq[string]):
    s.sort()
