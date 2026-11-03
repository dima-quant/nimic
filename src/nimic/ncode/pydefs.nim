type
  nbool* = bool
  nint* = int
  uintp* = uint
  intp* = int

# `"""{.nimicModuleLevel.}"""`: a routine the methods rule would make a method, kept module-level because
# of a call outside the modules converted when it was decided (rules §4, methods rule). A marker for
# nimicgen, kept after that module is converted; no effect
template nimicModuleLevel*() {.pragma.}

when defined(nimPreviewSlimSystem) or defined(nimony):
  # under a slim system (nimony's is always slim) File / echo / assert / raiseAssert are not in
  # system: every transpiled module imports this prelude, so re-export them
  import std/[syncio, assertions]
  export syncio, assertions

when defined(nimony):
  # nimic's isNil (Nim 2 system's) for every nilable type; nimony's system has it for cstring only
  template isNil*[T](p: ptr T): bool = p == nil
  template isNil*[T](p: ref T): bool = p == nil
  template isNil*(p: pointer): bool = p == nil
  # Nim 2's doAssert: an assert that -d:danger keeps
  template doAssert*(cond: bool; msg = "") =
    if not cond: failedAssertImpl(msg)
  # `$` nimony's system lacks; echo's arguments are `$`-converted by rule:echodollar
  func `$`*(c: char): string =
    result = newString(1)
    result[0] = c
  func `$`*(x: cstring): string =
    result = ""
    if x != nil:
      var i = 0
      while x[i] != '\0':
        result.add x[i]
        inc i

when not defined(nimony):
  # Python enumerate(s): Nim's for-loop macro handles `for (i, x) in enumerate(s)` (emitted by
  # rule:fortupleunpack) as well as `for i, x in ...`, over any iterable. nimony has no macros and
  # no std/enumerate: a module using enumerate doesn't compile there yet
  import std/enumerate
  export enumerate

type
  TextIOWrapper* = File

const
  inf* = Inf

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
