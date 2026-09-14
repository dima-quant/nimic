import ncode/pydefs
import std/tables
const
  F64_Bits* = 64
  F64_MantissaBits* = 52

func local_pair(x: SomeInteger, y: SomeInteger): uint64 {.inline.} =
  return uint64(x) shl 32 xor uint64(y)

func local_splitMix64(state: var uint64): uint64 =
  state += 11400714819323198485'u64
  result = state
  result = (result xor result shr 30) * 13787848793156543929'u64
  result = (result xor result shr 27) * 13787848793156543929'u64
  result = result xor result shr 31
  return result

func local_rotl(x: uint64, k: static[int]): uint64 {.inline.} =
  return x shl k or x shr (64 - k)
type
  Rng* = object
    s0*: uint64
    s1*: uint64
    s2*: uint64
    s3*: uint64


func seed*(rng: var Rng, x: SomeInteger) =
  var
    sm64 = uint64(x)
  rng.s0 = local_splitMix64(sm64)
  rng.s1 = local_splitMix64(sm64)
  rng.s2 = local_splitMix64(sm64)
  rng.s3 = local_splitMix64(sm64)

func seed*(rng: var Rng, x: SomeInteger, y: SomeInteger) =
  var
    sm64 = local_pair(x, y)
  rng.s0 = local_splitMix64(sm64)
  rng.s1 = local_splitMix64(sm64)
  rng.s2 = local_splitMix64(sm64)
  rng.s3 = local_splitMix64(sm64)

func local_next(rng: var Rng): uint64 =
  result = rng.s0 + rng.s3
  let
    t = rng.s1 shl 17
  rng.s2 = rng.s2 xor rng.s0
  rng.s3 = rng.s3 xor rng.s1
  rng.s1 = rng.s1 xor rng.s2
  rng.s0 = rng.s0 xor rng.s3
  rng.s2 = rng.s2 xor t
  rng.s3 = local_rotl(rng.s3, 45)
  return result

func uniform*(rng: var Rng, minIncl: float64, maxExcl: float64): float64 =
  let
    mantissa = rng.local_next() shr (F64_Bits - F64_MantissaBits)
    fl = mantissa or cast[uint64](1'f64)
    debiaised = cast[float64](fl) - 1'f64
  return max(minIncl, debiaised * (maxExcl - minIncl) + minIncl)

func uniform*(rng: var Rng, _: type[float64]): float64 =
  let
    mantissa = rng.local_next() shr (F64_Bits - F64_MantissaBits)
  let
    fl = mantissa or cast[uint64](1'f64)
  return cast[float64](fl) - 1'f64

func uniform*(rng: var Rng, maxExcl: float64): float64 =
  let
    mantissa = rng.local_next() shr (F64_Bits - F64_MantissaBits)
    fl = mantissa or cast[uint64](1'f64)
    debiaised = cast[float64](fl) - 1'f64
  return debiaised * maxExcl

func uniform*(rng: var Rng, maxExcl: uint32): uint32 =
  assert maxExcl > 0
  let
    max = maxExcl
  var
    x = uint32(rng.local_next() shr 32)
    m = uint64(x) * uint64(max)
    l = uint32(m)
  if l < max:
    var
      t = not max + 1
    if t >= max:
      t -= max
      if t >= max:
        t = t.mod(max)
    while l < t:
      x = uint32(rng.local_next())
      m = uint64(x) * uint64(max)
      l = uint32(m)
  return uint32(m shr 32)

func uniform*[T: SomeInteger](rng: var Rng, minIncl: T, maxExcl: T): T =
  let
    maxExclusive = maxExcl - minIncl
  result = type(maxExcl)(rng.uniform(uint32(maxExclusive)))
  result += minIncl
  return result
when isMainModule:

  proc local_uniform_uint() =
    var
      rng: Rng
    let
      timeSeed = 54
    rng.seed(timeSeed)
    echo("prng_sanity_checks - uint32 - xoshiro256+ seed: ", timeSeed)

    proc local_test[T](min: T, maxExcl: T) =
      var
        c = initCountTable[nint]()
      for _ in range(1000):
        c.inc(rng.uniform(min, maxExcl))
      echo("1'000'000 pseudo-random outputs from ", min, " to ", maxExcl, " (excl): ", c)
    local_test(0, 2)
    local_test(0, 3)
    local_test(1, 53)
    local_test(-10, 11)
  local_uniform_uint()

  proc local_uniform_f64() =
    var
      rng: Rng
    let
      timeSeed = 53
    rng.seed(timeSeed)
    echo("prng_sanity_checks - float64 - xoshiro256+ seed: ", timeSeed)

    proc local_bin(f: float64, bucketsWidth: float64, min: float64): nint =
      return nint((f - min) / bucketsWidth)

    proc local_test[T](min: T, maxExcl: T, buckets: nint) =
      var
        c = initCountTable[nint]()
      let
        bucketsWidth = (maxExcl - min) / float64(buckets)
      for _ in range(1000):
        c.inc(local_bin(rng.uniform(min, maxExcl), bucketsWidth, min))
      echo("1'000'000 pseudo-random outputs from ", min, " to ", maxExcl, " (excl): ", c)
    local_test(0.0, 2.0, 10)
    local_test(0.0, 2.0, 20)
    local_test(0.0, 3.0, 10)
    local_test(0.0, 1.0, 10)
    local_test(0.0, 1.0, 20)
    local_test(-1.0, 1.0, 10)
    local_test(-1.0, 1.0, 20)
  local_uniform_f64()