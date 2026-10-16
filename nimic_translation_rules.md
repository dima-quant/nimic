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
| `var x = RefType()` | `with var: x = RefType()` | For a `ref` type (`@ref` class) the constructor call is kept, since `var x: RefType` would be `nil` (`rule:varini`) |
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
| `when defined(windows):` | `if comptime(defined("windows")):` | `defined()` takes a string in Nimic (`rule:defined`); transpiler strips quotes for Nim. In Python it tests the *build profile* of the emulated Nim build: `c`, host OS/CPU (`macosx`, `posix`, `arm64`, ...), `gcOrc`, the compiler's feature symbols, the `define:` lines of the Nim configs Nim would read for the same main module (global config, `nim.cfg` files from the root down to the main module's directory, `<main>.nim.cfg`; `ncompiler/nim.cfg` links `compiler/nim.cfg`), and `NIMIC_DEFINES` (e.g. `NIMIC_DEFINES=danger`). So `defined("c")` is true in Python too |
| `when declared(signbit):` | `if comptime(declared("signbit")):` | `rule:declared`: the name (dotted allowed: `declared("system.getMaxMem")`) is looked up in the calling module's scope |
| `const x = when c: a else: b` | `with const:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x = a if comptime(c) else b` | `when` expression (`rule:comptimeexpr`) |
| `{.push overflowChecks: off.}`<br>`...`<br>`{.pop.}` | `with push("overflowChecks: off"):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...` | `rule:push`: emits the pragma, the body unindented, then `{.pop.}`. Python emulates the runtime checks `overflowChecks`, `boundChecks` and `checks` for procs defined inside the block; other pragmas only affect the Nim output |
| `when not compileOption("threads"):` | `if comptime(not compileOption("threads")):` | `not comptime(...)` is also handled correctly |
| `template addCast(b: var Builder, t: Snippet, body: typed) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...; body; ...`<br>`b.addCast(t): b.add(x)` | `@template`<br>`def addCast(b: mut@Builder, t: Snippet, body: typed):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...; body; ...`<br>`with b.addCast(t):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`b.add(x)` | Block template: trailing `typed`/`untyped` parameters used as bare statements are the code blocks of the call. A second block (`... : first do: second`) follows `with do:` *inside* the `with` body. Skipped, extra or missing blocks raise `TemplateBlockError`. A proc overload of the same name needs `@dispatch` |
| `template t(b: var Builder, kind = Local, name: string, body: typed)` | `def t(b: mut@Builder, kind: VarKind = VarKind.Local, name: string = string(""), body: typed = None)` | Python needs defaults after a defaulted parameter; the `= None` of a block parameter is not written to Nim (`rule:blockparam`) |
| `include cbuilderexprs, cbuilderstmts` | `include("cbuilderexprs", "cbuilderstmts")` | `rule:include`: the file runs in the includer's namespace. An include file has no imports of its own (only the nimic boilerplate) and no tests: it is tested through a harness in `ncompiler/tests/` that, like its real includer, imports the converted modules, includes stand-ins for the unconverted ones (`cgen_context`, ...) and the include files in the includer's order |
| `{.emit: """C code""".}` | `emit("""C code""")` | `rule:emit`; raises in Python, so it belongs in a `when` branch that is inactive in the emulated build |

### 2.1 Rule: `if comptime` must mirror a `when` of the original Nim

Every `if comptime(X)` in a converted module, with its `elif comptime(...)` and `else` branches, must correspond one to one to a `when X` (`elif`, `else`) of the original Nim source: same position, same condition in nimic spelling, every branch converted. The only exception is test code that the original source does not contain.

- **Keep every branch.** Convert all branches of the original `when`, including branches that are inactive on your machine or in the default build (`when defined(windows)`, GC- or backend-specific branches) and `when false:` / `when true:` (`if comptime(False):` / `if comptime(True):`). Do not resolve a `when` at conversion time by keeping one branch, and do not turn it into a runtime `if`: `when f is float32` is `if comptime(isinstance(f, float32))`, not `if isinstance(f, float32)`.
- **Same condition.** Translate the condition as written: `defined(x)` → `defined("x")`, a constant stays a constant (`when FileSystemCaseSensitive:` → `if comptime(FileSystemCaseSensitive):`, not `defined("FileSystemCaseSensitive")`), `isMainModule` → `__name__ == "__main__"`, `declared(x)` → `declared("x")`.
- **Exception: added tests.** Tests that the original does not contain, and the scaffolding they need (stand-in types and procs for dependencies that are not converted yet), go under `if comptime(__name__ == "__main__"):`, and only under that condition. They must run identically in Python and in the transpiled Nim, must not redefine, rebind or monkey-patch converted code (no `_py_*` copies, no `Class.method = ...`, no `setattr`/`globals()`), and must not shadow names that the module's imports provide. A `when isMainModule:` block of the original is converted like any other code; added tests come after it. Include files are the exception: they have no test section, their tests live in a harness (see `include` above).
- **Never tell Python and Nim apart.** A condition whose purpose is to run different code in Python and in Nim is forbidden: `defined("c")` / `not defined("c")` (Python mode emulates the C-backend Nim build; `defined` is not a Python/Nim switch), `declared(X)` to supply missing types, `not (__name__ == "__main__")`, or any branch that exists for only one language. Needing such a switch means nimic lacks a feature: mark the spot `# TODO: requires nimic feature <name>`, write a proposal (`nimic-propose-feature` skill) and keep the original Nim structure.
- **Review check.** List every `comptime(...)` of the converted module and every `when` of the original; apart from the `__name__ == "__main__"` test guard they must pair up one to one. Run the module's tests in Python and as compiled Nim: the outputs must be identical.

Background and the list of nimic features still missing for this rule: `ncompiler/review_core_2026_10_16.md`.

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
| `type T = object` with `case kind: K` | `class T(Object):` with `kind: K` + `match kind:` | Object variants, see §11 (`rule:matchcase`) |
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

**Types of one type section.** Consecutive classes are one Nim `type` section (methods are written after it), so a field may name a type declared later in the section (`PType.sym: PSym` before `class PSym`): the field resolves when the later type is defined, with that type's zero value (`nil` for a `@ref`).

## 4. Functions and Arguments
Functions use standard Python `def` definitions but might employ specific decorators to mimic Nim semantics.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| **Implicit `result` Variable** | `def foo() -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = nint(5)`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return result` | Nim's `result` variable is implicitly declared and returned. In Nimic, you must explicitly assign `result = ...` and write `return result` at the end. Note: There is no need to declare a default instantiation `result = Type()` if the value is defined or overwritten immediately on the next line! |
| `discard foo()` | `_ = foo()` | Discarding a function call result |
| `proc foo(x: var SomeType)` | `def foo(x: mut@SomeType):` | Assigning new value requires `<<=`, e.g., `x <<= y` (not needed for attributes and array elements). |
| `proc s(p: BProc): var Builder` | `def s(p: BProc) -> mut@Builder:` | Mutable (`var`) return type, also in `@calltype` signatures (`rule:funcdefmut`). |
| `proc init(x: out T)` | `def init(x: out@T):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x <<= T(...)` | `out` parameter (`rule:funcdefout`) |
| `proc f(x: int): int` (forward declaration) | `def f(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pass` | A body of only `pass` (after an optional pragma docstring) is a forward declaration; the later definition replaces it in Python. Overloaded procs: both with `@dispatch` |
| `obj.f(a)` (method call syntax) | `obj.f(a)` | For an `Object`, `obj.f(a)` calls the proc `f(obj, a)` visible in the caller's scope, also a block template (`with b.addCast(t):`). For other types (`string`, ...) declare the proc with `@ufcs(string)`. A call without parentheses (`typ.elementType`) needs a `@property` in the class (transpiled as a proc) or the call form `elementType(typ)` |
| `foo(nil)` for `x: SomeRef` | `foo(None)` | `None` dispatches only to nilable parameter types: `@ref` classes, `ptr[T]`, `pointer`, `@calltype` procs. |
| `iterator myIter(x: int): int`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | |
| `proc foo(x:int)`<br>`proc foo(x:float)` | `@dispatch`<br>`def foo(...)` | "Static" dispatch. |
| `foo(x = 1)` | `foo(x = 1)` | Call and dispatch with keyword arguments. |
| `proc foo(x: int, y = 5)` | `@dispatch`<br>`def foo(x: nint, y = 5):` | Default parameter values are supported in `@dispatch`/`@template`; types are inferred and missing trailing arguments populated automatically. Arguments are bound per overload, so keyword calls may omit defaulted parameters (`addVar(b, kind=Local, name=n, typ=t)`), and an overload with defaults stays reachable when another overload has the call's arity. |
| `proc f(a: T, args: varargs[T])` | `def f(a: T, *args: T)` | `rule:varargs`; pass varargs or a seq on with `f(a, *args)` (Nim `f(a, args)`). A conversion, `varargs[string, $]`, is written `*args: varargs[string, str]` and needs `@dispatch` (it applies `$` to each argument) |
| `proc f(x: int \| int64 \| uint64)` | `def f(x: nint \| int64 \| uint64)` | A union is a type class for `@dispatch` (Nim `int or int64 or uint64`) |
| `p.s(cpsStmts) = oldCode` (a proc returning `var T`) | `assign(p.s(cpsStmts), oldCode)` | `rule:assigncall`: Python can't assign to a call; `assign` assigns in place like `<<=` |
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
| `s.skipWhitespace(i)` (UFCS on a std proc) | `s.skipWhitespace(i)` | Works when the Python std shim declares the proc with `@ufcs(string, aliases=("skipWhitespace",))`; std shims must not `setattr` methods onto core types. Python's own `str` methods (`find`, `rfind`, `strip`, …) are never shadowed — call the strutils proc as a function (`rfind(s, c)`) when Nim semantics differ |
| `type Snippet = string` | `Snippet = string` | `rule:typealias` (assignment form): a module-level `Name = <type>` is emitted in a `type` section (`type Snippet* = string`); `@dispatch` resolves it through the defining module's globals. `class Snippet(string): pass` is an alias too (a `string` subclass without members) |
| `== nil` / `!= nil` | `is None` / `is not None` | Python identity checks transpile as Nim nil comparisons (`rule:nilident`) |

### 6.1 Strings are bytes (`rule:latin1literal`, `rule:utf8literal`)
A Nim `string` is a sequence of bytes. A nimic `string`/`cstring`/`char` holds those bytes as a Python `str` *byte view*: one char per byte (code points 0–0xFF, i.e. Latin-1).

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `string` = bytes, `len` = byte count, `s[i]` = byte i | `s.data` is the Latin-1 byte view | `len(s)` and `s[i]` are byte-exact |
| `"\xE9"` (one byte) | `"é"` or `"\xe9"` | A bare non-ASCII char ≤ 0xFF *is* that byte; transpiles as `"\xE9"` (`rule:latin1literal`) |
| `"é"` (UTF-8 bytes `C3 A9`) | `utf8("é")` | `utf8(text)` gives the UTF-8 bytes of Unicode text; a constant argument transpiles as the raw literal `"é"` (`rule:utf8literal`) |
| — | `"€"` (char > 0xFF) | Not a byte: `string("€")` raises `NimicEncodingError` (a `ValueError`); the transpiler raises `SyntaxError`. Use `utf8("€")` |
| `echo`, `readLine`, `write` (byte-transparent) | `print`/`echo`, stdio | Importing `nimic.ntypes` reconfigures stdin/stdout/stderr to Latin-1, so byte views are written as their exact bytes. Python-side text > 0xFF is still written as UTF-8. Opt out with env `NIMIC_NO_STDIO_RECONFIGURE=1` |
| `readFile`, `writeFile`, `lines`, `File` | same names | Binary I/O, no decoding |
| OS paths, env vars, `paramStr`, `getCurrentDir`, `walkDir` | `nimic.std.os` | Paths are bytes on disk: `utf8("café.txt")` names the same file Nim's `"café.txt"` does |
| `std/unicode` (runes) | — | Not yet available: Unicode handling is explicit on UTF-8 byte views |

Runtime boundary helpers (in `ntypesystem.py`, for std shims only): `_n_from_text` (Unicode text → byte view), `_n_to_text` (byte view → text), `_n_os_arg`, `_n_os_result`.

## 7. Operators and Logic (`rule:bitwiserename`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `and`, `or`, etc (binary) | `&`, `\|`, etc | Nim binary operators map to Python bitwise |
| `x = y` (value type) | `x = y.copy()` | Explicit copy of value types in Python, e.g. to create a mutable copy. `string`, `seq`, `array`, `Tset` and `Object` have `.copy()`; assigning an object, `a[i] = obj` and `s.add(v)` copy value fields/elements (strings, seqs, non-ref objects) and share refs, as Nim does |
| `x = y` through a `var` parameter | `x <<= y` | Works for objects, `string`, `seq`, `array` and `Tset` (in place) |
| `echo a, b` | `echo(a, b)` | Nim semantics: `$` of each argument, no separator (`echo("n=", 3, true)` prints `n=3true`) |
| signed integer overflow | `a + b`, `a * b`, ... | Raises `OverflowDefect` like Nim with overflow checks on (the default build); off with `-d:danger` (`NIMIC_DEFINES=danger`) or inside `with push("overflowChecks: off"):`. Unsigned types, `+%`/`-%`, shifts and bitwise operations wrap. Array indexes out of bounds raise `IndexDefect` |
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
| `shallowCopy(d, s)` | `shallowCopy(d, s)` | Assigns `s` to `d` in place (`d` must be a mutable nimic value) |

## 8. Exporting and Scope (`rule:writeexport`, `rule:localname`, `rule:modulepath`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `export` | `with export:` | |
| Local variables | `_` or `local_` prefix | Identifiers defined **without** `*` in Nim should be prefixed in Nimic to prevent transpiling as public with `*`. |
| `import std/tables` | `from nimic.std.tables import *` | Module paths are translated: `nimic.x.y` → `x/y`, with module renaming (`rule:modulepath`) |
| `import ../options` | `from ..options import *` | Relative imports keep their level: one `../` per extra dot |


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
| `block search:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`... break search` | `with block("search"):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`... breakBlock("search")` | Labeled block (`rule:labeledblock`) |


## 11. Variant type and `case` statements (`rule:matchcase`, `rule:uncheckedassign`)
- **`case` statements** ➔ `match` statements
- **variant types (case objects)** ➔ `Object` with a `match` on the field declared immediately before it
```nim
  NodeObj* = object
    info*: int
    case kind*: NodeKind
      of nkInt: intVal*: int
      of nkAdd, nkSub:
        leftOp*, rightOp*: Node
      of nkIf:
        cond*: Node
        case hasElse*: bool
        of true: elsePart*: Node
        of false: discard
      else: discard
    tail*: int
```
translates in nimic Python as
```python
class NodeObj(Object):
    info: nint
    kind: NodeKind              # no dummy default needed
    match kind:
        case NodeKind.nkInt:
            intVal: nint
        case NodeKind.nkAdd | NodeKind.nkSub:
            leftOp: Node
            rightOp: Node
        case NodeKind.nkIf:
            cond: Node
            hasElse: bool
            match hasElse:
                case True:
                    elsePart: Node
                case False:
                    pass
        case _:
            pass
    tail: nint
```

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `case kind*: K` | `kind: K` then `match kind:` | The discriminator needs no default (a legacy `= None` is accepted and dropped by the transpiler) |
| `of A, B:` | `case K.A \| K.B:` | |
| `else:` | `case _:` | Must be the last branch |
| `discard` (empty branch) | `pass` | |
| nested `case` inside a branch | nested `match` inside a `case` | |
| — | — | Every field of every branch is part of the type; names must be unique across branches. Methods and guards are not allowed inside branches. The class must live in a `.py` file (its source is read once at definition) |
| `T(kind: nkAdd, leftOp: x)` | `T(kind=K.nkAdd, leftOp=x)` | Discriminators are set first; an omitted one takes its zero value (`low(K)`, `False`); only the selected branch's fields exist and are zero-initialized |
| `FieldDefect` | `FieldDefect` | Reading/writing a field of an inactive branch, or passing it to the constructor: `field 'x' is not accessible for type 'T' using 'kind = nkInt'` |
| `x.kind = nkSub` (same branch) | `x.kind = K.nkSub` | Allowed when the active branch does not change; otherwise `FieldDefect("assignment to discriminant changes object branch")` |
| `x[] = T(kind: nkInt, ...)` | `x <<= T(kind=K.nkInt, ...)` | Replacing the whole object may change the branch (also `copy()`) |
| `{.cast(uncheckedAssign).}:` | `with uncheckedAssign:` | Branch-changing discriminator assignment; union memory is reused, newly active python-side fields are defaulted (`rule:uncheckedassign`) |
| C layout | — | Common fields, the discriminator, then a union of one struct per branch: `sizeof` = common + largest branch; `seq[T]` elements share that stride |
| `of 'a'..'z':` (range branch) | — | Not supported yet |

## 12. Closures and Nonlocal Scope (`rule:nonlocal`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| (implicit capture) | `nonlocal x` | Nim closures capture outer scope variables by reference automatically. In Python, mutating captured outer variables requires `nonlocal x`, which the transpiler suppresses (`rule:nonlocal`). |

