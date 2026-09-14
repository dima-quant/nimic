# /// nimic
#
# ///
# Test 4: Camera rotation (Radians -= constant)
from __future__ import annotations
from nimic.ntypes import *
from math import pi

from safe_math import Radians

def test_camera_rotation():
    with var: angle = Radians(2.0 * pi)
    with let: step = Radians(2.0 * pi / 1200.0)
    for i in range(1200):
        angle -= step
        if i % 100 == 0:
            print(i, " ", float64(angle))
    print("final ", float64(angle))

if comptime(__name__ == "__main__"):
    test_camera_rotation()
