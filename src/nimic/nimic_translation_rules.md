# Nimic Translation Rules (Nim -> Python Nimic)

This document serves as a comprehensive collection of translation rules and syntax mappings when transpiling from Nim syntax to Python syntax for the `nimic` transpiler. These rules correspond directly to the internal `rule:` definitions located in `nimic/transpiler.py`. The major requirement is that nimic code should be a valid Python that transpiles to valid Nim code. Expressions not explicitly mentioned as a rule are assumed to be translated directly to Python syntax.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `isNil` | `is_nil` |  |
| `let x = 5` | `with let: x = 5` | Immutable assignments |

## 1. Variable Declarations (`rule:varini`, `rule:dropwith`)
Nim variable declarations are mapped to Python context managers to encapsulate scoping and mutability semantics. The transpiler strips the `with` block and generates standard Nim variable sections.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `var x: SomeType` | `with var: x = SomeType()` | Declaration and initializatoin |
| `var a: array[2, uint8]` | `with var: a = array[2, uint8]()` | Declaration and initializatoin |
| `let x = 5` | `with let: x = 5` | Immutable assignments |
| `const x = 5` | `with const: x = 5` | Compile-time constants |
| `var x, y: int` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x = 0`<br>&nbsp;&nbsp;&nbsp;&nbsp;`y = 0` | Groups declarations |
| `var tY: uint16` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_tY = uint16()` | Local variable, declared outside function or inner block in Nim, should be named as a local variable with prefix `_` to avoid being mistranslated as exported globals `tY*` after transpiling |

## 2. Compile-Time and Metaprogramming (`rule:comptime`, `rule:templateinline`)
Compile-time metaprogramming relies on function calls or specific decorators. Generic Nim's macro definitions are not supported.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `when x < 5:` | `if comptime(x < 5):` | |
| `template foo()` | `@template`<br>`def foo()` | Template definition. Note: `@template_expand` is **only** needed on the *calling function* if you need to actually expand *untyped* templates inside it. Typed templates should have a `return` statement. |
| `template _sph(): untyped {.dirty.} =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`moving_spheres[i]`  (used inline by attributes) | `with template_inline:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.dirty.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_sph = moving_spheres[i]` |  For substituting an expression accessed by attributes. |

## 3. Structural Definitions (`rule:classdef`, `rule:typealias`, `rule:typedistinct`)
Classes and objects use standard Python `class` definitions but employ specific parent classes to signal type semantics to Nimic.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `type SomeType = object` | `class SomeType(Object):` | |
| `type SomeType = object of BaseType` | `class SomeType(BaseType):` | |
| `type SomeType = ptr object` | `@ptr class SomeType(Object):` | class definition should be decorated by `@ptr` for pointer types |
| `SomeType(x: 1, y: 2)` | `SomeType(x=1, y=2)` | Object instantiation |
| `type Time* = float64` | `class Time(float64): pass` | Type Alias |
| `[byte 1, 5]` | `array[2, byte]([1, 5])` | Arrays |
| `SomeTuple = tuple[x: int, y: float]` | `class SomeTuple(NTuple):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x: int`<br>&nbsp;&nbsp;&nbsp;&nbsp;`y: float` | Tuples should be defined as Named Tuple with an alias |

**distinct type** `type SomeType = distinct int` ➔ Must be decorated by `@distinct` on a class that inherits from the base type,
```nim
  type otherint = distinct int
  proc `*`*(self: otherint, scalar: float64): otherint {.borrow.}
```
translates to
```python
  # Python Nimic
  @distinct
  class otherint(int):
    def __mul__(self: otherint, scalar: float64) -> otherint:
      """{.borrow.}"""
      return super().__mul__(scalar)
```
**Enums (`rule:enum`) `type SomeEnum = enum`** ➔ `class SomeEnum(NIntEnum):`, e.g., for enumerations
```python
  # Python Nimic
  class SomeEnum(NIntEnum):
    sort1 = auto()
    sort2 = auto()
    sort3 = auto()
```

## 4. Functions and Arguments
Functions use standard Python `def` definitions but might employ specific decorators to mimic Nim semantics.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| **Implicit `result` Variable** | `def foo() -> int:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = int()`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = 5`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return result` | Nim's `result` variable is implicitly declared and returned. In Nimic, you must explicitly declare `result = ...` and write `return result` at the end of the script! |
| `discard foo()` | `_ = foo()` | Discarding a function call result |
| `proc foo(x: var SomeType)` | `def foo(x: mut@SomeType):` | Assigning new value requires `<<=`, e.g., `x <<= y` (not needed for attributes and array elements). |
| `iterator myIter(x: int): int`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | `def myIter(x: int) -> int:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | |
| `proc foo(x:int)`<br>`proc foo(x:float)` | `@dispatch`<br>`def foo(...)` | "Static" dispatch. |
| `proc foo(...)` | `def foo(...)` | Methods of classes inheriting from `Object` are dispatched automatically. |
| `0 ..< a` | `range(a)` | Range syntax. |
| `[a ..< b]`,  `[a ..^1]` | `[a:b]`, `[a:]` | Slicing syntax. Upper bound can not be negative. |
| `proc `+`(a: uint, b:uint):` | `def __add__(a: uint, b:uint):` | Operator overloading via dunder methods. |
| `func foo(x:uint):` | `def foo(x:uint):` `"""{.noSideEffect.}"""` | function is proc without side effect |
| `proc `+`=(a: uint, b:uint):` | `def __iadd__(a: uint, b:uint):` | In-place operators in Python should return the modified object. |
| `proc `+`=(a: uint, b:uint):` | `def __radd__(a: uint, b:uint):` | Right-hand side binary operators swap arguments. |
| `converter toFloat(x: int): float` | `@converter`<br>`def toFloat(x: nint) -> float:` | Converter functions. |
| `iterator myIter(x: int): int = yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | Iterators are translated to generator functions. |

**Get/Set Operators (`rule:funcdefrenamedunder`)** Nim get/set operators map to Python dunder (magic) methods.
  - `[]=` ➔ `__setitem__`
  - `[]` ➔ `__getitem__`, for multi-argument operators, the arguments are packed into a tuple
  ```nim
  proc `[]`*(canvas: Canvas, row: SomeInteger, col: SomeInteger): Color {.inline.} =
    return canvas.pixels[row * canvas.ncols + col]
  ```
  ```python
    def __getitem__(canvas: Canvas, packed_tuple: tuple[SomeInteger, SomeInteger]) -> Color:
      """{.inline.}"""
      row, col = packed_tuple
      return canvas.pixels[row * canvas.ncols + col]
  ```

## 5. Memory and Pointers (`rule:dropbrackets`)
Memory primitives are strongly enforced to mirror Nim.
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `ptr SomeType` | `ptr[SomeType]` | |
| `ptr UncheckedArray[T]` | `ptr[UncheckedArray[T]]` | Bare `ptr[T]` cannot be indexed. |
| `pointer` | `pointer` | Untyped void pointer |
| `c_malloc(csize_t(size))` | `c_malloc(csize_t(size))` | allocators |
| `allocShared0(size)` | `alloc_shared0(size)` | shared memory allocator |
| `deallocShared(p)` | `dealloc_shared(p)` | shared memory deallocator |
| `writeBytes(f, data, 0, len)` | `write_bytes(f, data, 0, len)` | writing bytes to file |
| `cast[int](p) + 4` | `cast[intp](p) + 4` | `intp` supports pointer arithmetic in nimic. |
| `cast[uint](p) + 4` | `cast[uintp](p) + 4` | `uintp` supports pointer arithmetic in nimic. |
| `p[]`, `p[] = x` | `p.contents`, `p.contents = x` | Pointer dereferencing |
| `array[3, float64]([1, 2, 3])`| `array[3, float64]([1.0, 2.0, 3.0])` | Nimic arrays use iterables as initialization payloads. |
| `addr x` | `addr(x)` | Maps natively using Nimic's variable aliasing mechanics. |
| `unsafeAddr x` | `unsafe_addr(x)` | Equivalent to `addr x` in Nimic logic. |

## 6. Primitives & Typing
Because the transpiler is sensitive to Python's internal logic versus Nim's system macros, specific mappings apply:
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `bool`, `int` | `bool`, `nint` |
| `string` | `string` | `string` should be used instead of Python's `str` |
| `str1 / str2` (Paths) | `string(str1) / str2` | |
| `str1 & str2` | `str1 + str2` | String concatenation |
| `&"var: {x}"` | `f"var: {x}"` | String interpolation |
| `true`, `false`, `nil`, `Inf` |` True`, `False`, `None`, `inf` | Python's standard `inf` is `Inf` in Nim, bools transpile via `rule:lowercasebool`|
| `0x9e37...15'u64` | `u64(0x9e37...15)` | Numeric literal types |
| `'#'` | `ch("#")` | Char literal types |

## 7. Operators and Logic (`rule:bitwiserename`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `and`, `or`, etc (binary) | `&`, `\|`, etc | Nim binary operators map to Python bitwise |
| `x = y` (value type) | `x = y.copy()` | Explicit copy of value types in Python, e.g. to create a mutable copy. |
| `isnot`, `notin` | `is not`, `not in` | |
| `(width + 15) shr 4 - 1` | `((width + 15) >> 4) - 1` | In Python bitwise operators have lower precedance than arithmetic operators | 
| `for item in arr.mitems:` | `for item in arr.mitems:` | In-place mutation loops translate directly, do not replace with `enumerate`. |
| `data[i] == ' '` (chars) | `ord(data[i]) == 32` | Python string chars don't map smoothly to Nim `char`. Use `ord()` for comparisons. |

## 8. Exporting and Scope (`rule:writeexport`, `rule:localname`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `export` | `with export:` | |
| Local variables | `_` or `local_` prefix | Identifiers defined **without** `*` in Nim should be prefixed in Nimic to prevent transpiling as public with `*`. |


## 9. Callable type (`rule:calltype`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `type`<br>`Name* = proc(x: int): int` | `@calltype`<br>`def Name(x: int) -> int: pass` | |

## 10. Block Statements (`rule:block`, `rule:dropwith`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `block:` (statement) | `with block:` | Prevent variable leaking |
| `block:` (value return) | `def _block():`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return val`<br>`result = _block()` | Emulate value-returning blocks with immediately invoked localized functions. |


## 11. Variant type and `case` statements
- **`case` statements** ➔ `match` statements
- **variant types** ➔ `Object` with `match` statement
```nim
  HittableVariant* = object
    case kind*: HittableVariantKind
      of HittableVariantKind.kSphere:
        fSphere*: Sphere
      of HittableVariantKind.kMovingSphere:
        fMovingSphere*: MovingSphere
```
translates in nimic Python as
```python
class HittableVariant(Object):
    kind: HittableVariantKind = None
    match kind:
        case HittableVariantKind.kSphere:
            fSphere: Sphere
        case HittableVariantKind.kMovingSphere:
            fMovingSphere: MovingSphere
```
