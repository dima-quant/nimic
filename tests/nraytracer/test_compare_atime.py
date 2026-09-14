# /// nimic
#
# ///
# Test 1: ATime (float32) accumulation precision
from __future__ import annotations
from nimic.ntypes import *

from scenes_animated import ATime

def test_atime_accumulation():
    with var: t = ATime(0.0)
    with let: dt = ATime(0.005)
    for i in range(400):
        t += dt
        if i % 50 == 0:
            print(i, " ", float32(t))
    print("final ", float32(t))

if comptime(__name__ == "__main__"):
    test_atime_accumulation()
