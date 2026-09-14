type
  nbool* = bool
  nint* = int

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