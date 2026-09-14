from __future__ import annotations
import sys
from nimic.ntypes import *

def check():
    cg = sys._getframe(1).f_globals
    try:
        print("EVAL:", eval('int', cg))
    except Exception as e:
        print("EVAL ERROR:", repr(e))

check()
