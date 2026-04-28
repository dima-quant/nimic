# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *

@dispatch
def sort(s: mut @ seq[string]):
    s.sort()
