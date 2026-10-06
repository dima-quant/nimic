# Nimic Translation Rules (Nim -> Python Nimic)

This document serves as a comprehensive collection of translation rules and syntax mappings when transpiling from Nim syntax to Python syntax for the `nimic` transpiler. These rules correspond directly to the internal `rule:` definitions located in `nimic/transpiler.py`. The major requirement is that nimic code should be a valid Python that transpiles to valid Nim code. Expressions not explicitly mentioned as a rule are assumed to be translated directly to Python syntax. Nimic code should be marked by the meta-comment and typically makes havy use of annotations and nimic.ntypes:

```python
# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
```


| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `isNil`, `copyMem` | `is_nil`, `copy_mem` | Nimic follows the Python convention, replacing `camelCase` with `snake_case` for functions and attributes |
| `let x = 5` | `with let: x = 5` | Immutable assignments |

## 1. Variable Declarations (`rule:varini`, `rule:dropwith`)
Nim variable declarations are mapped to Python context managers to encapsulate scoping and mutability semantics. The transpiler strips the `with` block and generates standard Nim variable sections.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `var x: SomeType` | `with var: x = SomeType()` | Declaration and initializatoin |
| `var a: array[2, uint8]` | `with var: a = array[2, uint8]()` | Declaration and initializatoin |
| `let x = 5` | `with let: x = 5` | Immutable assignments |
| `const x = 5` | `with const: x = 5` | Compile-time constants |
| `var x, y: int` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x = nint(0)`<br>&nbsp;&nbsp;&nbsp;&nbsp;`y = nint(0)` | Groups declarations |
| `var tY: uint16` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_tY = uint16()` | Local variable, declared outside function or inner block in Nim, should be named as a local variable with prefix `_` to avoid being mistranslated as exported globals `tY*` after transpiling |

## 2. Compile-Time and Metaprogramming (`rule:comptime`, `rule:templateinline`)
Compile-time metaprogramming relies on function calls or specific decorators. Generic Nim's macro definitions are not supported.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `when x < 5:` | `if comptime(x < 5):` | |
| `template foo()` | `@template`<br>`def foo()` | Template definition. Note: `@template_expand` is **only** needed on the *calling function* if you need to actually expand *untyped* templates inside it. Typed templates should have a `return` statement. |
| `template _sph(): untyped {.dirty.} =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`moving_spheres[i]`  (used inline by attributes) | `with template_inline:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.dirty.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_sph = moving_spheres[i]` |  For substituting an expression accessed by attributes. |
| `when defined(windows):` | `if comptime(defined("windows")):` | `defined()` takes a string in Nimic (`rule:defined`); transpiler strips quotes for Nim |
| `when not compileOption("threads"):` | `if comptime(not compileOption("threads")):` | `not comptime(...)` is also handled correctly |

**Template return** (`rule:templatereturn`): Inside a typed template, `return expr` is transpiled as just `expr` (no `return` keyword), matching Nim's template result semantics. In Nimic, write `return result` normally — the transpiler handles the transformation.

## 3. Structural Definitions (`rule:classdef`, `rule:typealias`, `rule:typedistinct`)
Classes and objects use standard Python `class` definitions but employ specific parent classes to signal type semantics to Nimic.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `type SomeType = object` | `class SomeType(Object):` | Base object type definition (`RootObj = Object`). |
| `type SomeType = object of BaseType` | `class SomeType(BaseType):` | Object inheritance via RootObj. Automatically inherits all fields from `BaseType` in MRO order. Supports subtype polymorphism in `@dispatch`. |
| `type SomeType = ptr object` | `@ptr class SomeType(Object):` | class definition should be decorated by `@ptr` for pointer types |
| `SomeType(x: 1, y: 2)` | `SomeType(x=1, y=2)` | Object instantiation |
| `type Time* = float64` | `Time = float64` or `class Time(float64): pass` | Type Alias. Bidirectionally interchangeable with the target type in `@dispatch`. |
| `type range[warnMin .. hintMax]` | `class MyRange(Trange[warnMin, hintMax]): pass` | Range subtyping definition (`rule:trange`) |
| `type set[TNoteKind]` | `class MySet(Tset[TNoteKind]): pass` | Sets of ordinal types definition |
| `type seq[string]` | `class MySeq(seq[string]): pass` | Sequence type alias |
| `(x: 1, y: 2)` | `SomeTuple(x=1, y=2)` | NTuple constructor transpiles to Nim tuple literal (`rule:tuplelit`) |
| `{}` | `Tset[T]()` or `Tset()` | Empty set literal (`rule:setlit`) |
| `{a, b, c}` | `Tset[T](a, b, c)` or `Tset(a, b, c)` | Set literal with elements (`rule:setlit`) |
| `@[a, b, c]` | `seq[T]([a, b, c])` or `seq([a, b, c])` | Sequence literal (`rule:seqlit`) |
| `@[]` | `seq()` or `seq[T]()` | Empty sequence literal (`rule:seqlit`) |
| `[byte 1, 5]` | `array[2, byte]([1, 5])` | Arrays |
| `ar: array[1, string] = [0: "some"]` | `ar = array[1, string]({0: string("some")})` | Arrays initialized with a dictionary |
| `SomeTuple = tuple[x: int, y: float]` | `class SomeTuple(NTuple):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x: nint`<br>&nbsp;&nbsp;&nbsp;&nbsp;`y: float64` | Tuples should be defined as Named Tuple with an alias |

**distinct type** `type SomeType = distinct int` ➔ Must be decorated by `@distinct` on a class that inherits from the base type (`nint` for Nim `int`).
A distinct type is excluded from subtype matching in `@dispatch` (functions expecting the base type will reject it unless an explicit `@converter` is defined). Borrowed procs are declared as methods with `"""{.borrow.}"""` and can be called directly or via free-function UFCS dispatch:
```nim
  type otherint = distinct int
  proc `*`*(self: otherint, scalar: float64): otherint {.borrow.}
```
translates to
```python
  # Python Nimic
  @distinct
  class otherint(nint):
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
| **Implicit `result` Variable** | `def foo() -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = nint(5)`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return result` | Nim's `result` variable is implicitly declared and returned. In Nimic, you must explicitly assign `result = ...` and write `return result` at the end. Note: There is no need to declare a default instantiation `result = Type()` if the value is defined or overwritten immediately on the next line! |
| `discard foo()` | `_ = foo()` | Discarding a function call result |
| `proc foo(x: var SomeType)` | `def foo(x: mut@SomeType):` | Assigning new value requires `<<=`, e.g., `x <<= y` (not needed for attributes and array elements). |
| `iterator myIter(x: int): int`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | |
| `proc foo(x:int)`<br>`proc foo(x:float)` | `@dispatch`<br>`def foo(...)` | "Static" dispatch. |
| `foo(x = 1)` | `foo(x = 1)` | Call and dispatch with keyword arguments. |
| `proc foo(x: int, y = 5)` | `@dispatch`<br>`def foo(x: nint, y = 5):` | Default parameter values are supported in `@dispatch`/`@template`; types are inferred and missing trailing arguments populated automatically. |
| `proc foo(...)` | `def foo(...)` | Methods of classes inheriting from `Object` are dispatched automatically. |
| `0 ..< a` | `range(a)` | Range syntax. |
| `a .. b` | `inrange(a, b)` | Inclusive range syntax, frequently used for sets (e.g. `Tset[TNoteKind](inrange(low, high))`). |
| `[a ..< b]`,  `[a ..^1]` | `[a:b]`, `[a:]` | Slicing syntax. Upper bound can not be negative. |
| `proc `+`(a: SomeType, b:int):` | `class SomeType(Object):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def __add__(self: static[SomeType], b: nint):` | Operator overloading via dunder methods. To avoid monkey-patching in Python, function definitions acting as operators or methods for a specific type should be included as methods within the class definition. The transpiler natively unpacks them to freestanding `proc`s. |
| `func foo(x:uint):` | `def foo(x:uint):` `"""{.noSideEffect.}"""` | function is proc without side effect |
| `proc `+`=(a: uint, b:uint):` | `def __iadd__(a: uint, b:uint):` | In-place operators in Python should return the modified object. |
| `proc `+`=(a: uint, b:uint):` | `def __radd__(a: uint, b:uint):` | Right-hand side binary operators swap arguments. |
| `converter toFloat(x: int): float` | `@converter`<br>`def toFloat(x: nint) -> float:` | Converter functions. |
| `iterator myIter(x: int): int = yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | Iterators are translated to generator functions. |
| `for (a, b) in pairs:` | `for (a, b) in pairs:` | Tuple unpacking in for-loops; parentheses preserved for Nim (`rule:fortupleunpack`) |
| `proc foo[T, U](): ...` | `@generic`<br>`def foo[T, U](): ...` | `@generic` decorator allows 0-arg generic functions to be parameterized via `foo[T, U]()` in Python runtime. Transpiler strips `@generic`. |
| `(T1, T2)` (tuple type) | `tuple[T1, T2]` | Tuple type annotations in function return or variable types transpile as Nim parenthesized tuple types `(T1, T2)` (`rule:tupletype`). |

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
| `p: ptr` | `p: ptr` | Bare `ptr` protocol in `@dispatch` matches any `ptr[T]`. |
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
| `bool` | `bool` | |
| `int` | `nint` | Nimic must NOT shadow Python's built-in `int` type. Use `nint` for Nim `int` type annotations, field types, parameter types, return types, and conversions (e.g. `nint(x)`). Integer literals (e.g. `0`, `1`, `42`) are standard Python literals and are allowed. Transpiles to Nim `int` (`rule:nint`). |
| `string` | `string` | `string` should be used instead of Python's `str` |
| `str1 / str2` (Paths) | `string(str1) / str2` | |
| `str1 & str2` | `str1 + str2` | String concatenation |
| `&"var: {x}"` | `f"var: {x}"` | String interpolation |
| `true`, `false`, `nil`, `Inf` |` True`, `False`, `None`, `inf` | Python's standard `inf` is `Inf` in Nim, bools transpile via `rule:lowercasebool`|
| `0x9e37...15'u64` | `u64(0x9e37...15)` | Numeric literal types |
| `'#'` | `ch("#")` | Char literal types |
| `None` (Nim keyword) | `None_` | Trailing `_` stripped by transpiler for Python keyword clashes (`rule:keywordescape`) |
| `"format: $1" % [arg]` | `string("format: $1") % [arg]` | String `%` operator transpiles as Nim `%` (formatting), not `mod` (`rule:strformat`) |
| `readFile(f)` | `read_file(f)` / `readFile(f)` | Reads binary-safe byte buffer into Nimic `string`. |
| `Path(str)` | `Path(str)` | `from nimic.std.paths import Path`. Supports `/` (`__truediv__`) and `os.PathLike` (`__fspath__`). |
| `== nil` / `!= nil` | `is None` / `is not None` | Python identity checks transpile as Nim nil comparisons (`rule:nilident`) |

## 7. Operators and Logic (`rule:bitwiserename`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `and`, `or`, etc (binary) | `&`, `\|`, etc | Nim binary operators map to Python bitwise |
| `x = y` (value type) | `x = y.copy()` | Explicit copy of value types in Python, e.g. to create a mutable copy. |
| `isnot`, `notin` | `is not`, `not in` | |
| `(width + 15) shr 4 - 1` | `((width + 15) >> 4) - 1` | In Python bitwise operators have lower precedance than arithmetic operators | 
| `for item in arr.mitems:` | `for item in arr.mitems:` | In-place mutation loops translate directly, do not replace with `enumerate`. |
| `data[i] == ' '` (chars) | `ord(data[i]) == 32` | Python string chars don't map smoothly to Nim `char`. Use `ord()` for comparisons. |
| `not x` (bitwise) | `~x` | Nim bitwise `not` maps to Python bitwise inversion `~` (`rule:bitwiserename`) |
| `a +% b` | `plus_percent(a, b)` or `a.plus_percent(b)` | Nim wrapping addition in the operand type's width (`NInteger.plus_percent`; a plain `int` adopts its `NInteger` peer's type, else Nim `int`) (`rule:percentops`) |
| `a -% b` | `minus_percent(a, b)` or `a.minus_percent(b)` | Nim wrapping subtraction in the operand type's width (`NInteger.minus_percent`) (`rule:percentops`) |
| `a div b` | `a // b` | Nim integer division truncated toward zero (native on `NInteger`) |
| `a mod b` | `a % b` | Nim integer modulo truncated toward zero (native on `NInteger`) |
| `x is T` | `isinstance(x, T)` | Nim type query translates as `x is T` (`rule:isinstance`) |
| `cmp(a, b)` | `cmp(a, b)` | Standard three-way comparison `(a > b) - (a < b)` |
| `FormatStr(s)` | `FormatStr(s)` | Wraps format string for `%` operator; unwraps to string literal in Nim (`rule:formatstr`) |
| `move x` | `move(x)` | Nim ownership transfer; identity operation in Python runtime |
| `shallowCopy(d, s)` | `shallowCopy(d, s)` | Nim shallow copy; returns source in Python runtime |

## 8. Exporting and Scope (`rule:writeexport`, `rule:localname`, `rule:modulepath`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `export` | `with export:` | |
| Local variables | `_` or `local_` prefix | Identifiers defined **without** `*` in Nim should be prefixed in Nimic to prevent transpiling as public with `*`. |
| `import std/tables` | `from nimic.std.tables import *` | Module paths are translated: `nimic.x.y` → `x/y`, with module renaming (`rule:modulepath`) |


## 9. Callable type (`rule:calltype`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `type`<br>`Name* = proc(x: int): int` | `@calltype`<br>`def Name(x: nint) -> nint: pass` | |

## 10. Block Statements (`rule:block`, `rule:dropwith`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `block:` (statement) | `with block:` | Prevent variable leaking |
| `block:` (value return) | `def _block():`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return val`<br>`result = _block()` | Emulate value-returning blocks with immediately invoked localized functions. |
| `do:` | `with do:` | Nim `do:` block statement (`rule:doblock`) |


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

## 12. Closures and Nonlocal Scope (`rule:nonlocal`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| (implicit capture) | `nonlocal x` | Nim closures capture outer scope variables by reference automatically. In Python, mutating captured outer variables requires `nonlocal x`, which the transpiler suppresses (`rule:nonlocal`). |

