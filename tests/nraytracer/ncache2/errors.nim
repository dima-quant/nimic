import ncode/pydefs
const
  Tolerance = 1e-05

proc relative_error*[T: SomeFloat](y: T, y_true: T): T {.inline.} =
  let
    denom = max(abs(y_true), abs(y))
  if denom == cast[T](0):
    return cast[T](0)
  result = abs(y_true - y) / denom
  return result

proc absolute_error*[T: SomeFloat](y: T, y_true: T): T {.inline.} =
  result = abs(y_true - y)
  return result

template ensureWithinRelTol*[T: SomeFloat](y: T, y_true: T, tol=Tolerance): untyped =
  assert relative_error(y, y_true) <= tol

template ensureWithinAbsTol*[T: SomeFloat](y: T, y_true: T, tol=Tolerance): untyped =
  assert absolute_error(y, y_true) <= tol