# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.tables import *

with const:
    F64_Bits = 64
    F64_MantissaBits = 52


def _pair(x: SomeInteger, y: SomeInteger) -> uint64:
    """{.inline,noSideEffect.}"""
    ## A simple way to produce a unique uint64
    ## from 2 integers
    ## Simpler and faster than
    ## - Cantor pairing: https://en.wikipedia.org/wiki/Pairing_function#Cantor_pairing_function
    ## - Szudzik pairing: http://szudzik.com/ElegantPairing.pdf
    ## for integers bounded to uint32.
    ## Beyond there is collision
    return (uint64(x) << 32) ^ uint64(y)

def _splitMix64(state: mut @ uint64) -> uint64:
    """{.noSideEffect.}"""
    state += u64(0x9e3779b97f4a7c15)
    # result = uint64(0)
    # result <<= state
    result = state.copy()
    result = (result ^ (result >> 30)) * u64(0xbf58476d1ce4e5b9)
    result = (result ^ (result >> 27)) * u64(0xbf58476d1ce4e5b9)
    result = result ^ (result >> 31)
    return result

def _rotl(x: uint64, k: static[int]) -> uint64:
    """{.inline,noSideEffect.}"""
    return (x << k) | (x >> (64 - k))


class Rng(Object):
    s0: uint64
    s1: uint64
    s2: uint64
    s3: uint64


    def seed(rng: mut @ Rng, x: SomeInteger):
        """{.noSideEffect.}"""
        ## Seed the random number generator with a fixed seed
        with var: sm64 = uint64(x)
        rng.s0 = _splitMix64(sm64)
        rng.s1 = _splitMix64(sm64)
        rng.s2 = _splitMix64(sm64)
        rng.s3 = _splitMix64(sm64)


    def seed(rng: mut @ Rng, x: SomeInteger, y: SomeInteger):
        """{.noSideEffect.}"""
        ## Seed the random number generator from 2 integers
        ## for example, the iteration variable
        with var: sm64 = _pair(x, y)
        rng.s0 = _splitMix64(sm64)
        rng.s1 = _splitMix64(sm64)
        rng.s2 = _splitMix64(sm64)
        rng.s3 = _splitMix64(sm64)

    def _next(rng: mut @ Rng) -> uint64:
        """{.noSideEffect.}"""
        ## Compute a random uint64 from the input state
        ## using xoshiro256+ algorithm by Vigna et al
        ## State is updated.
        ## The lowest 3-bit have low linear complexity
        ## For floating point use the 53 high bits
        result = rng.s0 + rng.s3
        with let: t = rng.s1 << 17

        rng.s2 = rng.s2 ^ rng.s0
        rng.s3 = rng.s3 ^ rng.s1
        rng.s1 = rng.s1 ^ rng.s2
        rng.s0 = rng.s0 ^ rng.s3

        rng.s2 = rng.s2 ^ t

        rng.s3 = _rotl(rng.s3, 45)

        return result


    def uniform(rng: mut @ Rng, minIncl: float64, maxExcl: float64) -> float64:
        """{.noSideEffect.}"""
        # Create a random mantissa with exponent of 1
        with let:
            mantissa = rng._next() >> (F64_Bits - F64_MantissaBits)
            fl = mantissa | cast[uint64](f64(1))
        # Debiaised by removing 1
            debiaised = cast[float64](fl) - f64(1)

        # Scale to the target range
        return max(
          minIncl,
          debiaised * (maxExcl - minIncl) + minIncl
        )


    def uniform(rng: mut @ Rng, _: type[float64]) -> float64:
        """{.noSideEffect.}"""
        with let: mantissa = rng._next() >> F64_Bits - F64_MantissaBits
        with let: fl = mantissa | cast[uint64](f64(1))
        # Debiaised by removing 1
        return cast[float64](fl) - f64(1)


    def uniform(rng: mut @ Rng, maxExcl: float64) -> float64:
        """{.noSideEffect.}"""
        # Create a random mantissa with exponent of 1
        with let:
            mantissa = rng._next() >> F64_Bits - F64_MantissaBits
            fl = mantissa | cast[uint64](f64(1))
            # Debiaised by removing 1
            debiaised = cast[float64](fl) - f64(1)

        # Scale to the target range
        return debiaised * maxExcl


    def uniform(rng: mut @ Rng, maxExcl: uint32) -> uint32:
        """{.noSideEffect.}"""
        ## Generate a random integer in 0 ..< maxExclusive
        ## Uses an unbiaised generation method
        ## See Lemire's algorithm modified by Melissa O'Neill
        ##   https://www.pcg-random.org/posts/bounded-rands.html
        ## - Unbiaised
        ## - Features only a single modulo operation
        assert maxExcl > 0
        with let: max = maxExcl
        with var:
            x = uint32(rng._next() >> 32) # The higher 32-bit are of higher quality with xoshiro256+
            m = uint64(x) * uint64(max)
            l = uint32(m)
        if l < max:
            with var: t = not(max) + 1 # -max
            if t >= max:
                t -= max
                if t >= max:
                    t = t.mod(max)
            while l < t:
                x = uint32(rng._next())
                m = uint64(x) * uint64(max)
                l = uint32(m)
        return uint32(m >> 32)


    def uniform[T: SomeInteger](rng: mut @ Rng, minIncl: T, maxExcl: T) -> T:
        """{.noSideEffect.}"""
        ## Return a random integer in the given range.
        ## The range bounds must fit in an int32.
        with let: maxExclusive = maxExcl - minIncl
        result = type(maxExcl)(rng.uniform(uint32(maxExclusive)))
        result += minIncl
        return result


# TODO, not enough research in float64 PRNG
# - Generating Random Floating-Point Numbers by Dividing Integers: a Case Study
#   Frédéric Goualard, 2020
#   http://frederic.goualard.net/publications/fpnglib1.pdf


# Sanity checks
# ------------------------------------------------------------
if comptime(__name__ == "__main__"):
    # from nimic.std.tables import CountDict
    # import std.times

    # # TODO: proper statistical tests

    def _uniform_uint():
        with var:
            rng = Rng()
        with let: timeSeed = 54 #uint32(getTime().toUnix() & (i64(1) << 32) - 1) # unixTime mod 2^32
        rng.seed(timeSeed)
        print("prng_sanity_checks - uint32 - xoshiro256+ seed: ", timeSeed)

        def _test[T](min: T, maxExcl: T):
            with var: c = initCountTable[nint]()
            for _ in range(1_000):
                c.inc(rng.uniform(min, maxExcl))
            print("1'000'000 pseudo-random outputs from ", min, " to ", maxExcl, " (excl): ", c)

        _test(0, 2)
        _test(0, 3)
        _test(1, 53)
        _test(-10, 11)

    _uniform_uint()
    # print("\n--------------------------------------------------------\n")

    def _uniform_f64():
        with var: rng = Rng()
        with let: timeSeed = 53 #uint32(getTime().toUnix() and (i64(1) << 32) - 1) # unixTime mod 2^32
        rng.seed(timeSeed)
        print("prng_sanity_checks - float64 - xoshiro256+ seed: ", timeSeed)

        def _bin(f: float64, bucketsWidth: float64, min: float64) -> nint:
              # Idea: we split the range into buckets
              # and we verify that the size of the buckets is similar
              return nint((f - min) / bucketsWidth)

        def _test[T](min: T, maxExcl: T, buckets: nint):
            with var: c = initCountTable[nint]()

            with let: bucketsWidth = (maxExcl - min) / float64(buckets)

            for _ in range(1_000):
                c.inc(_bin(rng.uniform(min, maxExcl), bucketsWidth, min))

            print("1'000'000 pseudo-random outputs from ", min, " to ", maxExcl, " (excl): ", c)

        _test(0.0, 2.0, 10)
        _test(0.0, 2.0, 20)
        _test(0.0, 3.0, 10)
        _test(0.0, 1.0, 10)
        _test(0.0, 1.0, 20)
        _test(-1.0, 1.0, 10)
        _test(-1.0, 1.0, 20)

    _uniform_f64()


# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# Random Number Generator
# ----------------------------------------------------------------------------------

# We use the high bits of xoshiro256+
# as we are focused on floating points.
#
# http://prng.di.unimi.it/
#
# We initialize the RNG with SplitMix64

# type Rng* = object
#   s0, s1, s2, s3: uint64

# func pair(x, y: SomeInteger): uint64 {.inline.} =
#   ## A simple way to produce a unique uint64
#   ## from 2 integers
#   ## Simpler and faster than
#   ## - Cantor pairing: https://en.wikipedia.org/wiki/Pairing_function#Cantor_pairing_function
#   ## - Szudzik pairing: http://szudzik.com/ElegantPairing.pdf
#   ## for integers bounded to uint32.
#   ## Beyond there is collision
#   (x.uint64 shl 32) xor y.uint64

# func splitMix64(state: var uint64): uint64 =
#   state += 0x9e3779b97f4a7c15'u64
#   result = state
#   result = (result xor (result shr 30)) * 0xbf58476d1ce4e5b9'u64
#   result = (result xor (result shr 27)) * 0xbf58476d1ce4e5b9'u64
#   result = result xor (result shr 31)

# func seed*(rng: var Rng, x: SomeInteger) =
#   ## Seed the random number generator with a fixed seed
#   var sm64 = uint64(x)
#   rng.s0 = splitMix64(sm64)
#   rng.s1 = splitMix64(sm64)
#   rng.s2 = splitMix64(sm64)
#   rng.s3 = splitMix64(sm64)

# func seed*(rng: var Rng, x, y: SomeInteger) =
#   ## Seed the random number generator from 2 integers
#   ## for example, the iteration variable
#   var sm64 = pair(x, y)
#   rng.s0 = splitMix64(sm64)
#   rng.s1 = splitMix64(sm64)
#   rng.s2 = splitMix64(sm64)
#   rng.s3 = splitMix64(sm64)

# func rotl(x: uint64, k: static int): uint64 {.inline.} =
#   return (x shl k) or (x shr (64 - k))

# func next(rng: var Rng): uint64 =
#   ## Compute a random uint64 from the input state
#   ## using xoshiro256+ algorithm by Vigna et al
#   ## State is updated.
#   ## The lowest 3-bit have low linear complexity
#   ## For floating point use the 53 high bits
#   result = rng.s0 + rng.s3
#   let t = rng.s1 shl 17

#   rng.s2 = rng.s2 xor rng.s0
#   rng.s3 = rng.s3 xor rng.s1
#   rng.s1 = rng.s1 xor rng.s2
#   rng.s0 = rng.s0 xor rng.s3

#   rng.s2 = rng.s2 xor t

#   rng.s3 = rotl(rng.s3, 45)

# func uniform*(rng: var Rng, maxExcl: uint32): uint32 =
#   ## Generate a random integer in 0 ..< maxExclusive
#   ## Uses an unbiaised generation method
#   ## See Lemire's algorithm modified by Melissa O'Neill
#   ##   https://www.pcg-random.org/posts/bounded-rands.html
#   ## - Unbiaised
#   ## - Features only a single modulo operation
#   assert maxExcl > 0
#   let max = maxExcl
#   var x = uint32 (rng.next() shr 32) # The higher 32-bit are of higher quality with xoshiro256+
#   var m = x.uint64 * max.uint64
#   var l = uint32 m
#   if l < max:
#     var t = not(max) + 1 # -max
#     if t >= max:
#       t -= max
#       if t >= max:
#         t = t mod max
#     while l < t:
#       x = uint32 rng.next()
#       m = x.uint64 * max.uint64
#       l = uint32 m
#   return uint32(m shr 32)

# func uniform*[T: SomeInteger](rng: var Rng, minIncl, maxExcl: T): T =
#   ## Return a random integer in the given range.
#   ## The range bounds must fit in an int32.
#   let maxExclusive = maxExcl - minIncl
#   result = T(rng.uniform(uint32 maxExclusive))
#   result += minIncl

# # TODO, not enough research in float64 PRNG
# # - Generating Random Floating-Point Numbers by Dividing Integers: a Case Study
# #   Frédéric Goualard, 2020
# #   http://frederic.goualard.net/publications/fpnglib1.pdf

# const
#   F64_Bits = 64
#   F64_MantissaBits = 52

# func uniform*(rng: var Rng, minIncl, maxExcl: float64): float64 =
#   # Create a random mantissa with exponent of 1
#   let mantissa = rng.next() shr (F64_Bits - F64_MantissaBits)
#   let fl = mantissa or cast[uint64](1'f64)
#   # Debiaised by removing 1
#   let debiaised = cast[float64](fl) - 1'f64

#   # Scale to the target range
#   return max(
#     minIncl,
#     debiaised * (maxExcl - minIncl) + minIncl
#   )

# func uniform*(rng: var Rng, _: type float64): float64 =
#   let mantissa = rng.next() shr (F64_Bits - F64_MantissaBits)
#   let fl = mantissa or cast[uint64](1'f64)
#   # Debiaised by removing 1
#   return cast[float64](fl) - 1'f64

# func uniform*(rng: var Rng, maxExcl: float64): float64 =
#   # Create a random mantissa with exponent of 1
#   let mantissa = rng.next() shr (F64_Bits - F64_MantissaBits)
#   let fl = mantissa or cast[uint64](1'f64)
#   # Debiaised by removing 1
#   let debiaised = cast[float64](fl) - 1'f64

#   # Scale to the target range
#   return debiaised * maxExcl

# # Sanity checks
# # ------------------------------------------------------------

# when isMainModule:
#   import std/[tables, times]
#   # TODO: proper statistical tests

#   proc uniform_uint() =
#     var rng: Rng
#     let timeSeed = uint32(getTime().toUnix() and (1'i64 shl 32 - 1)) # unixTime mod 2^32
#     rng.seed(timeSeed)
#     echo "prng_sanity_checks - uint32 - xoshiro256+ seed: ", timeSeed

#     proc test[T](min, maxExcl: T) =
#       var c = initCountTable[int]()

#       for _ in 0 ..< 1_000_000:
#         c.inc(rng.uniform(min, maxExcl))

#       echo "1'000'000 pseudo-random outputs from ", min, " to ", maxExcl, " (excl): ", c

#     test(0, 2)
#     test(0, 3)
#     test(1, 53)
#     test(-10, 11)

#   uniform_uint()
#   echo "\n--------------------------------------------------------\n"

#   proc uniform_f64() =
#     var rng: Rng
#     let timeSeed = uint32(getTime().toUnix() and (1'i64 shl 32 - 1)) # unixTime mod 2^32
#     rng.seed(timeSeed)
#     echo "prng_sanity_checks - float64 - xoshiro256+ seed: ", timeSeed

#     proc bin(f, bucketsWidth, min: float64): int =
#       # Idea: we split the range into buckets
#       # and we verify that the size of the buckets is similar
#       int((f - min) / bucketsWidth)

#     proc test[T](min, maxExcl: T, buckets: int) =

#       var c = initCountTable[int]()

#       let bucketsWidth = (maxExcl - min) / float64(buckets)

#       for _ in 0 ..< 1_000_000:
#         c.inc(rng.uniform(min, maxExcl).bin(bucketsWidth, min))

#       echo "1'000'000 pseudo-random outputs from ", min, " to ", maxExcl, " (excl): ", c

#     test(0.0, 2.0, 10)
#     test(0.0, 2.0, 20)
#     test(0.0, 3.0, 10)
#     test(0.0, 1.0, 10)
#     test(0.0, 1.0, 20)
#     test(-1.0, 1.0, 10)
#     test(-1.0, 1.0, 20)

#   uniform_f64()

# 1'000'000 pseudo-random outputs from  0  to  2  (excl):  {'0': 502, '1': 498}
# 1'000'000 pseudo-random outputs from  0  to  3  (excl):  {'1': 344, '0': 327, '2': 329}
# 1'000'000 pseudo-random outputs from  1  to  53  (excl):  {'3': 12, '21': 26, '37': 21, '12': 16, '5': 18, '40': 23, '7': 16, '47': 18, '26': 18, '44': 24, '51': 17, '30': 21, '28': 17, '11': 25, '19': 14, '38': 30, '50': 18, '34': 21, '13': 15, '24': 19, '48': 31, '42': 21, '2': 12, '1': 16, '46': 22, '14': 22, '23': 17, '15': 17, '35': 12, '52': 13, '49': 24, '33': 28, '9': 19, '27': 29, '43': 20, '18': 15, '41': 18, '10': 22, '29': 16, '39': 22, '36': 17, '32': 25, '16': 21, '31': 21, '4': 19, '20': 13, '25': 13, '8': 18, '22': 15, '6': 16, '45': 17, '17': 20}
# 1'000'000 pseudo-random outputs from  -10  to  11  (excl):  {'-2': 43, '-4': 52, '10': 65, '-1': 36, '-7': 55, '4': 65, '-10': 43, '6': 39, '-8': 54, '9': 37, '7': 43, '-5': 53, '-6': 40, '5': 55, '3': 45, '8': 37, '-3': 32, '-9': 56, '0': 53, '2': 50, '1': 47}
# prng_sanity_checks - float64 - xoshiro256+ seed:  53
# 1'000'000 pseudo-random outputs from  0.0  to  2.0  (excl):  {'nint(5)': 108, 'nint(8)': 114, 'nint(9)': 100, 'nint(0)': 100, 'nint(3)': 95, 'nint(2)': 92, 'nint(7)': 96, 'nint(1)': 103, 'nint(4)': 107, 'nint(6)': 85}
# 1'000'000 pseudo-random outputs from  0.0  to  2.0  (excl):  {'nint(11)': 59, 'nint(10)': 38, 'nint(16)': 64, 'nint(17)': 42, 'nint(14)': 47, 'nint(19)': 44, 'nint(18)': 55, 'nint(2)': 51, 'nint(8)': 45, 'nint(7)': 56, 'nint(12)': 47, 'nint(5)': 55, 'nint(6)': 48, 'nint(0)': 59, 'nint(13)': 42, 'nint(9)': 60, 'nint(3)': 49, 'nint(15)': 53, 'nint(4)': 46, 'nint(1)': 40}
# 1'000'000 pseudo-random outputs from  0.0  to  3.0  (excl):  {'nint(5)': 98, 'nint(6)': 96, 'nint(7)': 112, 'nint(9)': 106, 'nint(3)': 101, 'nint(2)': 104, 'nint(8)': 90, 'nint(4)': 95, 'nint(1)': 99, 'nint(0)': 99}
# 1'000'000 pseudo-random outputs from  0.0  to  1.0  (excl):  {'nint(4)': 103, 'nint(5)': 104, 'nint(1)': 106, 'nint(6)': 103, 'nint(2)': 100, 'nint(0)': 95, 'nint(8)': 97, 'nint(3)': 101, 'nint(9)': 92, 'nint(7)': 99}
# 1'000'000 pseudo-random outputs from  0.0  to  1.0  (excl):  {'nint(16)': 56, 'nint(10)': 53, 'nint(4)': 57, 'nint(5)': 54, 'nint(13)': 57, 'nint(1)': 54, 'nint(2)': 55, 'nint(3)': 46, 'nint(19)': 67, 'nint(17)': 49, 'nint(7)': 39, 'nint(12)': 54, 'nint(11)': 63, 'nint(9)': 40, 'nint(8)': 41, 'nint(15)': 31, 'nint(0)': 45, 'nint(18)': 45, 'nint(6)': 36, 'nint(14)': 58}
# 1'000'000 pseudo-random outputs from  -1.0  to  1.0  (excl):  {'nint(2)': 102, 'nint(6)': 98, 'nint(4)': 94, 'nint(5)': 102, 'nint(9)': 120, 'nint(3)': 86, 'nint(1)': 108, 'nint(7)': 98, 'nint(0)': 102, 'nint(8)': 90}
# 1'000'000 pseudo-random outputs from  -1.0  to  1.0  (excl):  {'nint(4)': 64, 'nint(7)': 51, 'nint(19)': 45, 'nint(16)': 42, 'nint(12)': 55, 'nint(14)': 53, 'nint(18)': 51, 'nint(9)': 53, 'nint(2)': 67, 'nint(8)': 43, 'nint(10)': 48, 'nint(13)': 47, 'nint(1)': 52, 'nint(6)': 48, 'nint(11)': 48, 'nint(3)': 51, 'nint(0)': 51, 'nint(5)': 53, 'nint(17)': 35, 'nint(15)': 43}

# 1'000'000 pseudo-random outputs from 0 to 2 (excl): {0: 502, 1: 498}
# 1'000'000 pseudo-random outputs from 0 to 3 (excl): {2: 329, 0: 327, 1: 344}
# 1'000'000 pseudo-random outputs from 1 to 53 (excl): {4: 19, 5: 18, 11: 25, 39: 22, 3: 12, 49: 24, 2: 12, 26: 18, 38: 30, 22: 15, 29: 16, 32: 25, 19: 14, 46: 22, 16: 21, 52: 13, 6: 16, 47: 18, 12: 16, 51: 17, 28: 17, 48: 31, 41: 18, 30: 21, 13: 15, 50: 18, 1: 16, 43: 20, 20: 13, 14: 22, 9: 19, 35: 12, 7: 16, 37: 21, 36: 17, 31: 21, 17: 20, 33: 28, 18: 15, 25: 13, 34: 21, 44: 24, 27: 29, 10: 22, 24: 19, 23: 17, 15: 17, 21: 26, 40: 23, 42: 21, 8: 18, 45: 17}
# 1'000'000 pseudo-random outputs from -10 to 11 (excl): {-10: 43, -3: 32, 4: 65, 9: 37, -8: 54, 7: 43, 5: 55, -6: 40, 3: 45, -5: 53, 2: 50, -9: 56, 6: 39, 10: 65, 0: 53, -2: 43, -4: 52, -7: 55, 8: 37, -1: 36, 1: 47}
# prng_sanity_checks - float64 - xoshiro256+ seed: 53
# 1'000'000 pseudo-random outputs from 0.0 to 2.0 (excl): {9: 100, 4: 107, 5: 108, 7: 96, 3: 95, 2: 92, 6: 85, 0: 100, 8: 114, 1: 103}
# 1'000'000 pseudo-random outputs from 0.0 to 2.0 (excl): {14: 47, 9: 60, 4: 46, 7: 56, 5: 55, 11: 59, 3: 49, 2: 51, 17: 42, 18: 55, 19: 44, 16: 64, 6: 48, 10: 38, 0: 59, 12: 47, 15: 53, 8: 45, 13: 42, 1: 40}
# 1'000'000 pseudo-random outputs from 0.0 to 3.0 (excl): {9: 106, 4: 95, 5: 98, 7: 112, 3: 101, 2: 104, 6: 96, 0: 99, 8: 90, 1: 99}
# 1'000'000 pseudo-random outputs from 0.0 to 1.0 (excl): {4: 103, 9: 92, 5: 104, 7: 99, 3: 101, 2: 100, 6: 103, 0: 95, 8: 97, 1: 106}
# 1'000'000 pseudo-random outputs from 0.0 to 1.0 (excl): {14: 58, 4: 57, 9: 40, 5: 54, 7: 39, 11: 63, 3: 46, 2: 55, 17: 49, 18: 45, 19: 67, 16: 56, 6: 36, 10: 53, 0: 45, 12: 54, 15: 31, 13: 57, 8: 41, 1: 54}
# 1'000'000 pseudo-random outputs from -1.0 to 1.0 (excl): {4: 94, 9: 120, 5: 102, 7: 98, 3: 86, 2: 102, 6: 98, 0: 102, 8: 90, 1: 108}
# 1'000'000 pseudo-random outputs from -1.0 to 1.0 (excl): {14: 53, 4: 64, 9: 53, 7: 51, 5: 53, 11: 48, 3: 51, 2: 67, 17: 35, 18: 51, 19: 45, 16: 42, 6: 48, 10: 48, 0: 51, 12: 55, 15: 43, 8: 43, 13: 47, 1: 52}