# /// nimic
#
# ///
# Test 3: Mixed-precision multiplication
from __future__ import annotations
from nimic.ntypes import *

from scenes_animated import ATime, _Velocity, _Acceleration, G

def test_mixed_precision_mul():
    for i in range(20):
        with let: dt = ATime(0.001 * float32(i + 1))
        with let: result = G * dt
        print(i, " ", float64(result))

if comptime(__name__ == "__main__"):
    test_mixed_precision_mul()
