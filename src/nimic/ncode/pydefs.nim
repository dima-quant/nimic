type
  nbool* = bool
  nint* = int
  uintp* = uint
  intp* = int

when defined(nimPreviewSlimSystem):
  # under a slim system File / assert / doAssert / raiseAssert are not in system:
  # every transpiled module imports this prelude, so re-export them
  import std/[syncio, assertions]
  export syncio, assertions

# Python enumerate(s): Nim's for-loop macro handles `for (i, x) in enumerate(s)` (emitted by
# rule:fortupleunpack) as well as `for i, x in ...`, over any iterable
import std/enumerate
export enumerate

type
  TextIOWrapper* = File

const
  inf* = Inf

template range*(a: untyped): untyped =
  0 ..< a
template range*(a, b: untyped): untyped =
  a ..< b
template str*(x: untyped): untyped =
  $ x
template `+`*(x: string, y: string): string =
  x & y
template `+`*(x: string, y: char): string =
  x & y
template `+`*(x: char, y: string): string =
  x & y
template `~`*(x: untyped): untyped =
  not x
template isinstance*(x, t: untyped): untyped =
  x is t
template utf8*(s: string): string =
  ## nimic utf8(text): Nim strings already hold UTF-8 bytes, so this is identity.
  s


template range3(t) {.dirty.} =
  iterator range*(a, b, c: t): t {.inline.} =
    ## A type specialized version of `..<` for convenience so that
    ## mixing integer types works better.
    var res = a
    while res*c < b*c:
      yield res
      res += c

range3(int64)
range3(int32)
range3(int)