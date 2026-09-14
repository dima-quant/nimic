# /// nimic
#
# ///
# Test 2: Velocity borrow subtraction chain
from __future__ import annotations
from nimic.ntypes import *

from scenes_animated import ATime, _Velocity, _Acceleration, G

def test_velocity_borrow_sub():
    with var: v = _Velocity(5.0)
    with let: dt = ATime(0.005)
    for i in range(200):
        v -= G * dt
        if i % 20 == 0:
            print(i, " ", float64(v))
    print("final ", float64(v))

if comptime(__name__ == "__main__"):
    test_velocity_borrow_sub()
