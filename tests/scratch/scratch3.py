from __future__ import annotations
from nimic.ntypes import dispatch, int32, float64

@dispatch
def scrambled(a: int32, b: float64) -> float64:
    return a + b

@dispatch
def scrambled(b: int32, a: float64) -> float64:
    return b * a

print("Calling r1")
r1 = scrambled(b=int32(3), a=float64(4.0))
print(float(r1))
print("Calling r2")
r2 = scrambled(a=int32(3), b=float64(4.0))
print(float(r2))
