# Nimic Translation Rules — nimony / Nim 3 (`../nimony/src/` → `nnimony/`)

**The rules for the current work, all in one file:**
- §0–§12: the nimic language;
- §13: the conventions of nimony modules (layout, imports, build, tests, verification);
- §14: the Nim 3 constructs and nimic's support for them.

Rows marked **(Nim 2: ...)** describe Nim 2 behaviour that Nim 3 changes. Converted nimony code runs the
host-Nim (Nim 2) build for now, so those rows still apply, and §14 gives the Nim 3 version.

The plan and its reasons are in `ncompiler/conversion_plan.md`. The Nim 2 compiler conversion (frozen)
has its own file, `nimic_translation_rules_nim2.md`. Language changes are made here first.

This document serves as a comprehensive collection of translation rules and syntax mappings when transpiling from Nim syntax to Python syntax for the `nimic` transpiler. These rules correspond directly to the internal `rule:` definitions located in `nimic/transpiler.py`. The major requirement is that nimic code is valid Python that transpiles to valid Nim code with the same behavior (§0, unity principle). Expressions not explicitly mentioned as a rule are assumed to be translated directly to Python syntax. Nimic code should be marked by the meta-comment and typically makes havy use of annotations and nimic.ntypes:

```python
# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
```


| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `isNil`, `copyMem` | `is_nil`, `copy_mem` | Nimic follows the Python convention, replacing `camelCase` with `snake_case` for functions and attributes **(Nim 2: the Nim 3 version is in §14)** |
| `let x = 5` | `with let: x = 5` | Immutable assignments |

## 0. Unity principle — one source, one behavior

Every line of converted code — statements, declarations, imports and tests — is nimic: it runs in Python and
transpiles to Nim that behaves the same. Same behavior means the same output, results and raised errors under
the same build profile; `tests/verify_transpiled.py` checks it (Python run vs compiled Nim).

*Nimic* means the constructs of these rules and the API of `nimic.ntypes` and `nimic.std`. Other Python is not
nimic, even if it happens to run or to transpile: Python builtins, the standard library and idioms with no Nim
equivalent.

There is no code for only one side:
- no branches on the backend (`defined("c")`, `not defined("c")`);
- no `_py_*` copies or alternative implementations;
- no rebinding or monkey-patching (`Class.attr = proc`, `setattr`, `globals()[...]`);
- no Python builtins or idioms that have no Nim equivalent.

`if comptime(X)` is allowed only where it mirrors a `when X` of the original (§2.1). That isn't a split: Python
emulates one Nim build, the build profile aligned with `nim.cfg`.

Python implementations belong in the nimic core (`src/nimic/`) and in `nimic.std`, never in converted modules.

When nimic can't express a construct faithfully, don't work around it:
1. write the closest faithful code and mark it `# TODO: requires nimic feature <name>`;
2. report the gap (a proposal in `ncompiler/proposals/`, or the conversion report);
3. continue with the rest.

A gap closed in the core benefits every module; a workaround in a module splits it into a Python and a Nim
version.

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
| `var tY: uint16` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_tY = uint16()` | A module-level variable without `*` (also one in a module-level `when`) is written `_tY`: it transpiles to `tY`, not exported (`rule:localname`); without the `_` it would become the exported global `tY*`. Variables of a proc, loop or `block` (also `with block("name"):` at module level) are local and keep their names (`rule:dropwith`) |

## 2. Compile-Time and Metaprogramming (`rule:comptime`, `rule:templateinline`)
Compile-time metaprogramming relies on function calls or specific decorators. Generic Nim's macro definitions are not supported.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `when x < 5:` | `if comptime(x < 5):` | |
| `template foo()` | `@template`<br>`def foo()` | Template definition. Note: `@template_expand` is **only** needed on the *calling function* if you need to actually expand *untyped* templates inside it. Typed templates should have a `return` statement. |
| `template eatWord(word) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`while x[idx] == sep: idx.dec`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = ...`<br>&nbsp;&nbsp;&nbsp;&nbsp;`if not result: return` | `@template`<br>`def eatWord(word: untyped):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`while x[idx] == sep: idx -= 1`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = ...`<br>&nbsp;&nbsp;&nbsp;&nbsp;`if not result: return` | A statement template using the caller's variables (names that are not its parameters, its own `with var/let` locals or globals of its module) is expanded in callers decorated with `@template_expand`: no `{.dirty.}` (unless the original has it) and no `nonlocal`. Its bare `return` returns `result` from the caller |
| `template fun(op) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`conf.notes.op note`<br>`fun(incl)` | `@template`<br>`def fun(op: untyped):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`conf.notes.op(note)`<br>`fun(incl)` | A template parameter used as a routine, in call (`self(v, result)`) or method-call position, is substituted on expansion: `incl(conf.notes, note)` |
| `template impl() = result = 0; ...` shared by procs returning `int` and `BiggestInt` | `result <<= 0` in the template; each proc starts with `result = nint(0)` / `result = BiggestInt(0)` | `<<=` assigns in place and keeps the caller's result type (Nim `result = 0`) |
| `template _sph(): untyped {.dirty.} =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`moving_spheres[i]`  (used inline by attributes) | `with template_inline:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.dirty.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_sph = moving_spheres[i]` |  For substituting an expression accessed by attributes. |
| `when defined(windows):` | `if comptime(defined("windows")):` | `defined()` takes a string in Nimic (`rule:defined`); transpiler strips quotes for Nim. In Python it tests the *build profile* of the emulated Nim build: `c`, host OS/CPU (`macosx`, `posix`, `arm64`, ...), `gcOrc`, the compiler's feature symbols, the `define:` lines of the Nim configs Nim would read for the same main module (global config, `nim.cfg` files from the root down to the main module's directory, `<main>.nim.cfg`; `ncompiler/nim.cfg` links `compiler/nim.cfg`), and `NIMIC_DEFINES` (e.g. `NIMIC_DEFINES=danger`). So `defined("c")` is true in Python too |
| `when declared(signbit):` | `if comptime(declared("signbit")):` | `rule:declared`: the name (dotted allowed: `declared("system.getMaxMem")`) is looked up in the calling module's scope |
| `const x = when c: a else: b` | `with const:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x = a if comptime(c) else b` | `when` expression (`rule:comptimeexpr`) |
| `{.push overflowChecks: off.}`<br>`...`<br>`{.pop.}` | `with push("overflowChecks: off"):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...` | `rule:push`: emits the pragma, the body unindented, then `{.pop.}`. Python emulates the runtime checks `overflowChecks`, `boundChecks` and `checks` for procs defined inside the block; other pragmas only affect the Nim output |
| `when not compileOption("threads"):` | `if comptime(not compileOption("threads")):` | `not comptime(...)` is also handled correctly |
| `template addCast(b: var Builder, t: Snippet, body: typed) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...; body; ...`<br>`b.addCast(t): b.add(x)` | `@template`<br>`def addCast(b: mut@Builder, t: Snippet, body: typed):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...; body; ...`<br>`with b.addCast(t):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`b.add(x)` | Block template: trailing `typed`/`untyped` parameters used as bare statements are the code blocks of the call. A second block (`... : first do: second`) follows `with do:` *inside* the `with` body. Skipped, extra or missing blocks raise `TemplateBlockError`. A proc overload of the same name needs `@dispatch` |
| `template t(b: var Builder, kind = Local, name: string, body: typed)` | `def t(b: mut@Builder, kind: VarKind = VarKind.Local, name: string = string(""), body: typed = None)` | Python needs defaults after a defaulted parameter; the `= None` of a block parameter is not written to Nim (`rule:blockparam`) |
| `include cbuilderexprs, cbuilderstmts` | `include("cbuilderexprs", "cbuilderstmts")` | `rule:include`: the file runs in the includer's namespace. An include file has no imports of its own (only the nimic boilerplate) and no tests: it is tested through a harness in `ncompiler/tests/` that, like its real includer, imports the converted modules, includes stand-ins for the unconverted ones (`cgen_context`, ...) and the include files in the includer's order |
| `{.gcsafe.}:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`body` | `with pragma("gcsafe"):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`body` | Pragma block (`rule:pragmablock`), also `pragma("cast(gcsafe)")`; no effect in Python |
| `{.emit: """C code""".}` | `emit("""C code""")` | `rule:emit`; raises in Python, so it belongs in a `when` branch that is inactive in the emulated build |

### 2.1 Rule: `if comptime` must mirror a `when` of the original Nim

This rule applies the unity principle (§0) to compile-time branches.

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
| `{'-', '0'..'9'}` | `Tset[char](ch('-'), inrange(ch('0'), ch('9')))` or `Tset[char]({ch('-'), inrange(...)})` | Ranges in a set literal |
| `@[a, b, c]` | `seq[T]([a, b, c])` or `seq([a, b, c])` | Sequence literal (`rule:seqlit`) |
| `@[]` | `seq()` or `seq[T]()` | Empty sequence literal (`rule:seqlit`) |
| `[byte 1, 5]` | `array[2, byte]([1, 5])` | Arrays |
| `type T = object` with `case kind: K` | `class T(Object):` with `kind: K` + `match kind:` | Object variants, see §11 (`rule:matchcase`) **(Nim 2: the Nim 3 version is in §14)** |
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
`auto()` in a `NIntEnum` counts from 0 like Nim (the first member is 0, each next one more than the previous), so writing the first member `= 0` is not needed; `default(E)` and a zeroed field are the first member.
An enum with string values (`warnUser = "User"`) is a `NStrEnum`: `$` of an `auto()` member is its name, and members with equal texts (`warnUser = "User", hintUser = "User"`) are distinct members, ordered by declaration.
A member with an explicit ordinal and text (`Cdecl = (ord(CdeclTagId), "cdecl")`, the tag models) is written the same way in a `NStrEnum`: `Cdecl = (ord(TagEnum.CdeclTagId), "cdecl")`. Ordinals increase strictly and may leave holes. A member without one is the previous ordinal plus one (`"text"`, `auto()`). `ord`, `E(ordinal)`, comparisons and stored fields use the ordinal, and `succ`/iteration follow the declared members. An `NIntEnum` takes explicit values the same way (`a = 2`). As in Nim, an enum with holes is no ordinal type, so it can't index an array (`TypeError`). An array indexed by an enum spans `ord(low)..ord(high)`.

**Generic distinct objects** `BiTableFloat*[Id] = distinct BiTable[Id, uint64]` ➔ `@distinct class BiTableFloat[Id](BiTable[Id, uint64]): pass`. `BiTableFloat[uint32]` is distinct (procs of `BiTable` don't take it) and derives from `BiTable[uint32, uint64]`. A conversion between a distinct object and its base, or between an object and its base type (`BiTable[Id, uint64](t)`, `BiTableFloat[uint32](b)`), is a view of the same value, as Nim's l-value conversion: `BiTable[Id, uint64](t).getOrIncl(x)` changes `t`. To keep a separate value, `.copy()` it.

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
| `proc addOrdered(t: var B; v: sink T)`, ``proc `[]`(t: B; i: Id): lent T`` | `def addOrdered(t: mut @ B, v: sink @ T)`, `def __getitem__(t: B, i: Id) -> lent @ T` | `sink` parameter and `lent` return type (`rule:funcdefsink`); in Python the value itself |
| `type InstantiationInfo* = typeof(instantiationInfo())` | `InstantiationInfo = typeof(instantiationInfo())` | `typeof(x)` as a type alias (`rule:typealias`); `instantiationInfo(-2, fullPaths = true)` gives the call site in Python too |
| `proc canonicalCase(path: var string)` (not exported) | `def _canonicalCase(path: mut@string)` | A private proc or template has a leading `_`. It transpiles to the original Nim name without `*` (`proc canonicalCase(...)`), and Python star imports don't re-export it. A private overload of a public name is written the same way: `def _abs(a: int32)` next to a public `abs` is Nim's private `proc abs(a: int32)`, `_addToHex(uint32)` next to `addToHex(Int128)` |
| `udata: array[4, uint32]` (a private field) | `_udata: array[4, uint32]` | A private field has a leading `_`, also in constructors and accesses: `Int128(_udata=[...])`, `a._udata[0]` transpile to `Int128(udata: [...])`, `a.udata[0]` |
| `proc `*`(a: Int128, b: uint32): Int128` (private operator) | `def __mul__(a: Int128, b: uint32) -> Int128:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.private.}"""` | An operator can't take a `_`: the `{.private.}` docstring pragma (`rule:privatepragma`) keeps it unexported in Nim and is not emitted. In Python the overload stays visible to other modules (Nim would reject such a call) |
| `proc f(x: int): int` (forward declaration) | `def f(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pass` | A body of only `pass` (after an optional pragma docstring) is a forward declaration; the later definition replaces it in Python. Overloaded procs: both with `@dispatch` |
| `obj.f(a)` (method call syntax) | `obj.f(a)` | For an `Object`, `obj.f(a)` calls the proc `f(obj, a)` visible in the caller's scope, also a block template (`with b.addCast(t):`). For other types (`string`, ...) declare the proc with `@ufcs(string)`. A call without parentheses (`typ.elementType`) needs a `@property` in the class (transpiled as a proc) or the call form `elementType(typ)` |
| `foo(nil)` for `x: SomeRef` | `foo(None)` | `None` dispatches only to nilable parameter types: `@ref` classes, `ptr[T]`, `pointer`, `@calltype` procs. **(Nim 2: the Nim 3 version is in §14)** |
| `iterator myIter(x: int): int`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | |
| `proc foo(x:int)`<br>`proc foo(x:float)` | `@dispatch`<br>`def foo(...)` | "Static" dispatch. |
| `foo(x = 1)` | `foo(x = 1)` | Call and dispatch with keyword arguments. |
| `proc foo(x: int, y = 5)` | `@dispatch`<br>`def foo(x: nint, y = 5):` | Default parameter values are supported in `@dispatch`/`@template`; types are inferred and missing trailing arguments populated automatically. Arguments are bound per overload, so keyword calls may omit defaulted parameters (`addVar(b, kind=Local, name=n, typ=t)`), and an overload with defaults stays reachable when another overload has the call's arity. |
| `proc f(a: T, args: varargs[T])` | `def f(a: T, *args: T)` | `rule:varargs`; pass varargs or a seq on with `f(a, *args)` (Nim `f(a, args)`). A conversion, `varargs[string, $]`, is written `*args: varargs[string, str]` and needs `@dispatch` (it applies `$` to each argument) |
| `proc f(x: int \| int64 \| uint64)` | `def f(x: nint \| int64 \| uint64)` | A union is a type class for `@dispatch` (Nim `int or int64 or uint64`) |
| `p.s(cpsStmts) = oldCode` (a proc returning `var T`) | `assign(p.s(cpsStmts), oldCode)` | `rule:assigncall`: Python can't assign to a call; `assign` assigns in place like `<<=` **(Nim 2: the Nim 3 version is in §14)** |
| `proc cmp*(a, b: Int128): int`, `proc abs*(a: Int128)` (a new overload of a system/imported proc) | `@dispatch`<br>`def cmp(a: Int128, b: Int128) -> nint:` | The overload set extends the proc of that name the module imported (system, std, another module) or the builtins `abs`/`len`/`min`/`max`: calls no overload matches go to it, as in Nim |
| `template low*(t: typedesc[Int128]): Int128 = Min` | `@template`<br>`def low(t: typedesc[Int128]) -> Int128:` | A `typedesc[T]` parameter matches the type T itself (`low(Int128)`); other types still reach system `low` |
| `proc `<`*(a: BiggestInt, b: Int128): bool`, `proc `+`*(a: BiggestInt, b: Int128)` | `@ufcs(Int128)`<br>`@dispatch`<br>`def __lt__(a: BiggestInt, b: Int128) -> bool:` | Operators keep Nim's parameter order. `int64(3) < x` reaches the overload through Python's reflected call, and `x > y` / `x >= y` are `y < x` / `y <= x` (Nim's system templates). Operators that the methods rule keeps at module level are `@ufcs(T)`; a `$` (`__str__`) may return a nimic `string` |
| `when T is bool`, `when T is SomeUnsignedInt` (T a type parameter) | `if comptime(issubclass(T, bool)):` | `rule:isinstance` writes `T is X`; type classes `SomeInteger`, `SomeSignedInt`, `SomeUnsignedInt`, `SomeFloat`, `SomeNumber` work in `isinstance`/`issubclass` and dispatch. A union constraint `[T: SomeInteger \| bool]` is a type class |
| `proc ldexp(x: float64, exp: cint): float64 {.importc: "ldexp", header: "<math.h>".}` | `@importc`<br>`def _ldexp(x: float64, exp: cint) -> float64:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.importc: "ldexp", header: "<math.h>".}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pass` | In Python `@importc` calls that C function of the process (libc, libm) through ctypes, with the annotated scalar types; the transpiler drops the decorator |
| `f(5)` with `x: BiggestInt` | `f(5)` | A number literal takes the type of the parameter it is passed to (int64 here; for a generic `T` its binding) |
| `arg.sdata(3)` (a private proc or template) | `arg._sdata(3)` | Method-call syntax also finds private (`_`) procs of the caller's scope |
| `proc foo(...)` | `def foo(...)` | Methods of classes inheriting from `Object` are dispatched automatically. |
| `0 ..< a` | `range(a)` | Range syntax. |
| `a .. b` | `inrange(a, b)` | Inclusive range syntax, frequently used for sets (e.g. `Tset[TNoteKind](inrange(low, high))`). |
| `[a ..< b]`,  `[a ..^1]` | `[a:b]`, `[a:]` | Slicing syntax. Upper bound can not be negative. |
| `proc `+`(a: SomeType, b:int):` | `class SomeType(Object):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def __add__(self: static[SomeType], b: nint):` | Operator overloading via dunder methods. To avoid monkey-patching in Python, function definitions acting as operators or methods for a specific type should be included as methods within the class definition. The transpiler natively unpacks them to freestanding `proc`s. |
| `type T = object` ... `proc f*(x: T, k: int)`, `proc `==`*(a, b: T)` (procs of a type of the same module) | `class T(Object):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def f(x: T, k: nint):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def __eq__(a: T, b: T) -> bool:` | **Methods rule.** A proc, template or operator whose first parameter has a type defined in the same module is written as a method of that class, unless its body uses a module-level definition that comes after the type (a constant of the type, a later proc or template, an import placed later). The transpiler emits the methods as procs right after the type section, so they may use only what precedes the type, the type's fields and the methods before them in the class. Keep the original order among the methods. A method is called as a method everywhere in nimic, `x.f(1)` (Nim's `f(x, 1)` and `x.f(1)` are the same call, so the transpiled code doesn't change); several methods of the same name are an overload set. A proc that uses later definitions stays a module-level `def` at its original place; an operator or `$` there is `@ufcs(T)` (`@ufcs(T)` `@dispatch` adds overloads to an operator the class defines). Enum classes take their `$` (`__str__`) as a method too. Exceptions, which stay module-level: procs of a type alias (`Rope = string`, `TBitSet = seq[ElemType]`: methods would make the alias a new type); an overload set of which one overload must stay module-level (an overload set isn't split); a dirty template or one using its caller's variables (it is expanded at free call sites); a proc used as a value (`s.isNil` with `s` the proc); a proc whose first parameter only selects the operation (`cOp(op: TypedBinaryOp, ...)`). Test scaffolding follows the Nim module each stand-in comes from (`types.skipTypes` on `astdef.PType` is not a method) |
| `func foo(x:uint):` | `def foo(x:uint):` `"""{.noSideEffect.}"""` | function is proc without side effect **(Nim 2: the Nim 3 version is in §14)** |
| `proc `+`=(a: uint, b:uint):` | `def __iadd__(a: uint, b:uint):` | In-place operators in Python should return the modified object. |
| `proc `+`=(a: uint, b:uint):` | `def __radd__(a: uint, b:uint):` | Right-hand side binary operators swap arguments. |
| `converter toFloat(x: int): float` | `@converter`<br>`def toFloat(x: nint) -> float:` | Converter functions. |
| `iterator myIter(x: int): int = yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | Iterators are translated to generator functions. |
| `for (a, b) in pairs:` | `for (a, b) in pairs:` | Tuple unpacking in for-loops; parentheses preserved for Nim (`rule:fortupleunpack`) |
| `proc foo[T, U](): ...` | `@generic`<br>`def foo[T, U](): ...` | `@generic`: a generic proc called with explicit types, `foo[T, U]()`; the types bind `T` and `U` in its body (`BiTable[Id, T](...)` creates a `BiTable[uint32, string]`). Transpiler strips `@generic`. |
| `proc getKeyId[Id, T](t: BiTable[Id, T]; v: T): Id = ... Id(0)` | `@dispatch`<br>`def getKeyId[Id, T](t: BiTable[Id, T], v: T) -> Id:` | Nim instantiates every generic proc. In nimic `@dispatch` binds the type parameters from the arguments (structurally: `BiTable[Id, T]` matches `BiTable[uint32, string]`; a literal argument takes the bound type), so a body using them as values (`Id(0)`, `seq[Id]()`, `issubclass(T, string)`, `sizeof(T)`) needs `@dispatch`. An undecorated generic `def` runs with its type parameters unbound |
| `(T1, T2)` (tuple type) | `tuple[T1, T2]` | Tuple type annotations in function return or variable types, aliases (`Key = tuple[string, string]`), object fields and seq elements transpile as Nim parenthesized tuple types `(T1, T2)` (`rule:tupletype`). A field defaults to the tuple of its elements' zero values; assigning or adding a tuple copies its value elements |

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
| `addr x` | `addr(x)` | Maps natively using Nimic's variable aliasing mechanics. A standalone local integer or float gets storage of its own on `addr`, so pointers read and write it (`cast[ptr float32](addr(xi))[]` is `cast[ptr[float32]](addr(xi)).contents`) |
| `cast[cstring](addr(L.buf[i]))` | `cast[cstring](addr(L.buf[i]))` | A `char*` into the middle of a buffer: a cstring sharing the memory of the string or buffer that contains the address, from there to its end **(Nim 2: the Nim 3 version is in §14)** |
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
| `&"var: {x}"`, `fmt"var: {x}"` | `f"var: {x}"` | String interpolation (`rule:stringjoin`: `f` is written `&`); format specs (`{x:>5}`, `{f:.3f}`) mean the same in Python and Nim's strformat. Needs `from nimic.std.strformat import *` (Nim `import std/strformat`). `fmt"..."` is a raw literal in Nim, so a backslash in it is written `\\` in the f-string. A `bool` prints `True` in Python but `true` in Nim (G23) |
| `true`, `false`, `nil`, `Inf` |` True`, `False`, `None`, `inf` | Python's standard `inf` is `Inf` in Nim, bools transpile via `rule:lowercasebool`|
| `0x9e37...15'u64` | `u64(0x9e37...15)` | Numeric literal types |
| `'#'` | `ch("#")` | Char literal types. In a proc with a local named `ch` (which shadows `ch()` in Python), write `char("#")`: a one-char string constant is the same literal (`rule:char`); keep the local's name |
| `None` (Nim keyword) | `None_` | Trailing `_` stripped by transpiler for Python keyword clashes (`rule:keywordescape`) |
| `"format: $1" % [arg]` | `string("format: $1") % [arg]` | String `%` operator transpiles as Nim `%` (formatting), not `mod` (`rule:strformat`): the left operand is a string literal, `string(...)`/`FormatStr(...)`, a name declared `string`/`FormatStr` (parameter, annotated or `string(...)`-assigned variable, also in an enclosing scope), or a call of a proc declared `-> string`; or the right operand is a list/tuple or a name declared as a seq/openArray/array/varargs of `string` |
| `chr(i)` | `chr(i)` | nimic's `chr` gives a `char` (Python's builtin gives a `str`); `RangeDefect` outside 0..255 |
| `succ(c)`, `pred(' ')` (a char) | `succ(c)`, `pred(ch(' '))` | Also for chars; `RangeDefect` past `'\xFF'` or below `'\0'` |
| `$s` of a set, seq or array | `str(s)` | Nim's text: `{a, b}` (set, in ordinal order), `@[1, 2]` (seq), `[1, 2]` (array); strings and chars quoted with Nim's escapes (`@["a\"b"]`, `{'\n'}`) |
| `($x)[a..b]`, `($x).len` | `str(x)[a:b + 1]`, `str(x).len` | `rule:dollarparens`: a `str(...)` used as the base of an index or attribute is parenthesized in Nim |
| `except ValueError, OverflowDefect:` | `except (ValueError, OverflowDefect):` | Several exception types (`rule:exceptseveral`) |
| `Natural`, `Positive`, `range[0..4]` (parameter/return types) | `Natural`, `Positive`, `Trange[0, 4]` | Range types as annotations; values are not range-checked in Python yet (only `chr` and enum `succ`/`pred` raise `RangeDefect`) **(Nim 2: the Nim 3 version is in §14)** |
| `RangeDefect` | `RangeDefect` | A `Defect`, not a `ValueError`: `except ValueError` doesn't catch it, as in Nim **(Nim 2: the Nim 3 version is in §14)** |
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
| OS paths, env vars, `paramStr`, `getCurrentDir`, `walkDir` | `nimic.std.os` (the path procs are also method calls: `name.addFileExt(ExeExt)`, `p.isAbsolute()`, `p.changeFileExt("html")`) | Paths are bytes on disk: `utf8("café.txt")` names the same file Nim's `"café.txt"` does |
| `std/unicode` (runes) | — | Not yet available: Unicode handling is explicit on UTF-8 byte views |
| `newString(n)` | `newString(n)` | `n` NUL chars, to be written in place |
| `L.buf = s.cstring`, `cstring(s)` | the same | Points into `s`'s buffer: `c[i] = x`, `copyMem`/`moveMem(addr c[i], ...)` change `s`, and changes to `s` are seen through `c`. After `s.setLen` the buffer may move: take the cstring again, as in Nim. A cstring of anything else is a copy. Reads stop at the first NUL; past the buffer `c[i]` is `'\0'` **(Nim 2: the Nim 3 version is in §14)** |
| `moveMem(dst, src, n)` | `moveMem(dst, src, n)` | Overlapping regions allowed |

Runtime boundary helpers (in `ntypesystem.py`, for std shims only): `_n_from_text` (Unicode text → byte view), `_n_to_text` (byte view → text), `_n_os_arg`, `_n_os_result`.

## 7. Operators and Logic (`rule:bitwiserename`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `and`, `or`, etc (binary) | `&`, `\|`, etc | Nim binary operators map to Python bitwise |
| `s[i] = c` | `s[i] = c` | Writes the char in place (`IndexDefect` past the end) |
| `for c in mitems(s): c = x` | `for c in mitems(s):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`c <<= x` | `mitems` of a string yields chars bound to their slots; `<<=` writes back (transpiled `c = x`) |
| `"$1 [$#] ${name}" % [a, b]`, `format(f, a, b)`, `s.addf(f, a)` | the same | strutils `%`, `format`, `addf` with Nim semantics (`$1`, `$#`, `$-1`, `${n}`, `$name` key/value pairs, `$$`; `ValueError` if invalid) |
| `a <% b`, `a <=% b`, `a >% b`, `a >=% b` | `lt_percent(a, b)`, `le_percent`, `gt_percent`, `ge_percent` | Unsigned comparisons (`rule:percentops`) |
| `x.isNil`, `quit(1)`, `quit("msg")` | `isNil(x)`, `quit(1)`, `quit(string("msg"))` | system procs |
| `s.addInt(x)`, `s.addFloat(f)`, `likely(c)`, `unlikely(c)`, `uint`, `cint`, `cuint` | the same | system (`addFloat` from `std/formatfloat`, shortest round trip as `$`); `fastLog2` from `std/bitops`; `trunc` from `std/math` returns a float as in Nim |
| `for i, x in s:` (implicit pairs) | `for i, x in pairs(s):` | `(index, item)` of a seq, array or string; `(key, value)` of a table |
| `proc p(): tuple[dir: AbsoluteDir, name: string]` ... `result = (a, b)` | `class _SplitT(NTuple)` ..., `def p() -> _SplitT:` ... `return (a, b)` | A tuple literal returned from a proc declared to return a named tuple type becomes that type (`@dispatch`) |
| `$e`, `echo e` (enum member) | `str(e)`, `echo(e)` | The member's name (string-valued enums: the text) |
| `del t, key` | `t.del_(key)` | Python keyword: trailing `_` (`rule:keywordescape`) |
| `s.add((info, detail))` (seq of a named tuple) | `s.add((info, detail))` | A tuple literal becomes the seq's element tuple type |
| `MsgFlags* = set[MsgFlag]`, `flags: MsgFlags = {}` | `MsgFlags = Tset[MsgFlag]`, `flags: MsgFlags = MsgFlags()` | Calls of a set alias are set literals (`rule:setlit`) |
| `s[s.len]` | `s[s.len]` | A string is `'\0'`-terminated: with bound checks off (`-d:danger`, `push boundChecks: off`) it reads `'\0'`, otherwise `IndexDefect`. Don't add Python-only bounds guards **(Nim 2: the Nim 3 version is in §14)** |
| `toFloat(i)`, `toInt(f)` | `toFloat(i)`, `toInt(f)` | system procs |
| `a == b` (objects, tuples) | `a == b` | Field-wise, as Nim's default `==`; refs compare as references. Object constructors copy value arguments |
| `x = y` (value type) | `x = y.copy()` | Explicit copy of value types in Python, e.g. to create a mutable copy. `string`, `seq`, `array`, `Tset`, `Object` and the integer types (`nint`, `int64`, `uint8`, ...) have `.copy()`. Integers need it when the new variable is changed in place (`b = a.copy()` before `b -= 1` or passing `b` as `var`; Nim's `inc(b)` is `b += 1`), and when the source is changed while the new variable is still used: reading an object field gives a view of it, so `oldBufLen = L.bufLen.copy()` before `L.bufLen = L.bufLen * 2`. A parameter whose default is a Python literal has no `.copy()`: write `pos = nint(pos)`. A proc may return its argument itself (`abs(x)` of a non-negative `Int128`), so `var d = abs(d)` changed in place is `d = abs(d).copy()`, since in-place operators mutate the shared object; assigning an object, `a[i] = obj` and `s.add(v)` copy value fields/elements (strings, seqs, non-ref objects) and share refs, as Nim does |
| `x = y` through a `var` parameter | `x <<= y` | Works for objects, `string`, `seq`, `array`, `Tset` and the scalar cells (in place) |
| `var found = false` ... `p(found)` (`proc p(b: var bool)`), `var x = 0.0` passed as `var float` | `with var: found = nbool(False)` ... `p(found)`, `with var: x = float64(0.0)` | A Python `bool`/`float` can't be changed through a parameter: a variable passed as `var` is a cell, `nbool` (transpiles to `bool`, `rule:nint`) or `float64`, as `nint` is for `var int`. Object fields of type `bool` are cells already. Elsewhere Nim `bool` stays Python `bool` |
| `var res = osEmbedded` ... `findOS(name, res)` (`proc findOS(name: string; res: var TSystemOS)`) | `with var: res = cell(TSystemOS.osEmbedded)` ... `findOS(name, res)`; the callee assigns `res <<= i` | An enum member is immutable in Python: a variable passed as `var` of an enum type is a `cell` (`rule:cell`: transpiles to the member). It dispatches, compares, indexes arrays, prints and matches as its member, and storing it in a field, seq or array stores the member. `<<=` on a bare member raises `TypeError` instead of shifting. Ints, bools and floats have their own cells (`nint`, `nbool`, `float64`) |
| `echo a, b` | `echo(a, b)` | Nim semantics: `$` of each argument, no separator (`echo("n=", 3, true)` prints `n=3true`) |
| signed integer overflow | `a + b`, `a * b`, ... | Raises `OverflowDefect` like Nim with overflow checks on (the default build); off with `-d:danger` (`NIMIC_DEFINES=danger`) or inside `with push("overflowChecks: off"):`. Unsigned types, `+%`/`-%`, shifts and bitwise operations wrap. Array indexes out of bounds raise `IndexDefect` |
| `isnot`, `notin` | `is not`, `not in` | |
| `(width + 15) shr 4 - 1` | `((width + 15) >> 4) - 1` | In Python bitwise operators have lower precedance than arithmetic operators | 
| `for item in arr.mitems:` | `for item in arr.mitems:` | In-place mutation loops translate directly, do not replace with `enumerate`. |
| `data[i] == ' '` (chars) | `ord(data[i]) == 32` | Python string chars don't map smoothly to Nim `char`. Use `ord()` for comparisons. |
| `not x` (bitwise) | `~x` | Nim bitwise `not` maps to Python bitwise inversion `~` (`rule:bitwiserename`) |
| `a +% b` | `plus_percent(a, b)` or `a.plus_percent(b)` | Nim wrapping addition in the operand type's width (`NInteger.plus_percent`; a plain `int` adopts its `NInteger` peer's type, else Nim `int`) (`rule:percentops`) |
| `a -% b` | `minus_percent(a, b)` or `a.minus_percent(b)` | Nim wrapping subtraction in the operand type's width (`NInteger.minus_percent`) (`rule:percentops`) |
| `h !& v`, `!$h` (std/hashes) | `mix_hash(h, v)`, `finish_hash(h)` | Nim std operators Python can't spell are named procs that transpile back to the operator (`rule:namedops`); `hashIgnoreStyle` uses the same Nim algorithm, so a hash built with `mix_hash` matches it |
| `hash(x)` (std/hashes) | `hash(x)` | Nim's values (the host Nim 2 std/hashes): every integer type, char, bool and enum (hashWangYi1 of the ordinal), floats, strings and `openArray[char]` (hashFarm), tuples and other openArrays (the elements mixed). A distinct type borrows it: `return hash(uint32(a))`. Objects, seqs and sets still hash by Python identity (to do) |
| `proc `??`*(conf: ConfigRef; ...)` (a custom operator of a converted module) | `def qq(conf: ConfigRef, ...)` | Custom operators defined in converted code get a name in letters (precedent: saturate's `` `|+|` `` is `sat_plus`); the transpiled module defines and calls that name |
| `s[^1]`, `s[^n]` | `s[back(1)]`, `s[back(n)]` | Index counted from the end (`BackwardsIndex`, `rule:namedops`) for string, seq, array and openArray; a negative index is an `IndexDefect`, as in Nim |
| `ashr(x, y)` | `ashr(x, y)` | Arithmetic shift right of a signed integer, in `x`'s type (`NInteger.ashr`) |
| `a div b` | `a // b` | Nim integer division truncated toward zero (native on `NInteger`) |
| `a mod b` | `a % b` | Nim integer modulo truncated toward zero (native on `NInteger`) |
| `x is T` | `isinstance(x, T)` | Nim type query translates as `x is T` (`rule:isinstance`) |
| `cmp(a, b)` | `cmp(a, b)` | Standard three-way comparison `(a > b) - (a < b)` |
| `FormatStr(s)` | `FormatStr(s)` | Wraps format string for `%` operator; unwraps to string literal in Nim (`rule:formatstr`) |
| `move x` | `move(x)` | Nim ownership transfer; identity operation in Python runtime |
| `swap(t.keys, n)` | `swap(t._keys, n)` | system `swap`: both variables change in place (string, seq, array, set, object, field, the scalar cells); a Python literal or enum member is no variable (`TypeError`) |
| `toOpenArray(s, a, b)`, `toOpenArray(p, 0, n - 1)` (`p: ptr UncheckedArray[char]`) | the same | An `openArray[T]` view of positions `a..b` of a seq, array, string, openArray or ptr UncheckedArray; writes go to the source. Out of range: `IndexDefect` |
| `reset(x)` | `reset(x)` | `x` becomes `default(typeof(x))` in place (Object, string, seq, array, set, integer) |
| `inc(tok.tokType, 2)` (an enum) | `tok.tokType = succ(tok.tokType, 2)` | Nim's `inc` of an enum is `succ`; an integer's `inc(x, n)` is `x += n` |
| `shallowCopy(d, s)` | `shallowCopy(d, s)` | Assigns `s` to `d` in place (`d` must be a mutable nimic value) |

## 8. Exporting and Scope (`rule:writeexport`, `rule:localname`, `rule:modulepath`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `export` | `with export:` | |
| Private names | `_` prefix (operators: `{.private.}`) | Identifiers defined **without** `*` in Nim (procs, templates, types, fields, module variables) are written `_name`; they transpile to `name` without `*` (`rule:localname`). Names starting with `__` or `_<digit>` keep a `local_` prefix. The transpiler rejects a module where dropping the `_` changes meaning (`private_name_collisions`): `_x` and `x` both defined in one scope (except overloaded procs, and `_base = f(base)` for a parameter `base` not used afterwards, i.e. Nim's `let base = f(base)`), or `x` used as a value after a private value `_x` (calls `x(...)` still find the proc in Nim). Rename then, e.g. `_pkgConf` |
| `import std/tables` | `from nimic.std.tables import *` | Module paths are translated: `nimic.x.y` → `x/y`, with module renaming (`rule:modulepath`) |
| `import ../options` | `from ..options import *` | Relative imports keep their level: one `../` per extra dot |
| `msgs.message(...)`, `nimlexbase.EndOfFile` (qualified by module) | `from .msgs import *` plus `from . import msgs`, then `msgs.message(...)` | `from . import m` binds the module name in Python and emits nothing (Nim's `import m` makes `m.x` available). A method of another module's type is called as a method (`nimlexbase.handleCR(L, pos)` is `L.handleCR(pos)`) |
| `import std/times` | `from nimic.std.times import *` (or `import a, b` of it) | A Python `from m import ...` is a full Nim `import m`: a class comes with its methods, which are procs in Nim |
| `from std/times import utc, fromUnix` | `importFrom("nimic.std.times", "utc", "fromUnix")` | `rule:importfrom`: Nim's selective import; binds only those names |
| `import ropes except `%`` | `importExcept(".ropes", "%")` | `rule:importexcept`: the module's public names except the given ones (operators have no Python name) |


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

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `case c`<br>`of 'a'..'z', 'A'..'Z', '_':` | `match c:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`case _ if c in inrange(ch('a'), ch('z')) or c in inrange(ch('A'), ch('Z')) or c == ch('_'):` | Ranges, values and set constants (`c in routineDefs`) of one `of` branch: a guard on the subject joined with `or`. A char value needs a guard (`c == ch('_')`) since `case "_"` is a string |
| `of nkEmpty..pred(nkSym), succ(nkSym)..nkNilLit:` | `case _ if n.kind in inrange(TNodeKind.nkEmpty, pred(TNodeKind.nkSym)) or n.kind in inrange(succ(TNodeKind.nkSym), TNodeKind.nkNilLit):` | Enum ranges likewise |
| `elif cond:` (branch of a `case`) | `case _ if cond:` | Any other guard is an `elif` branch |
| `proc p(s: string): Cmd =`<br>&nbsp;&nbsp;`case s`<br>&nbsp;&nbsp;`of "sug": ideSug`<br>&nbsp;&nbsp;`else: ideNone` | `def p(s: string) -> Cmd:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`match s:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case "sug": return Cmd.ideSug`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case _: return Cmd.ideNone` | `case` expression as the proc's result (`rule:casereturn`): a body ending with a `match` whose every branch is `return <value>` |
| `let bitsPerDigit = case base`<br>&nbsp;&nbsp;`of base2: 1`<br>&nbsp;&nbsp;`else: raiseAssert "unreachable"` | `with let:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`match base:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case NumericalBase.base2: bitsPerDigit = 1`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case _: raiseAssert(string("unreachable"))` | `case` expression assigned to a variable (`rule:caseassign`): a `match` directly inside `with let:`/`with var:`/`with const:` whose every branch ends by assigning the same name, or with a raise or a call that doesn't return. Also for `var` |
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

## 13. nimony modules

### 13.1 Source and target

| | |
|---|---|
| Source | the nimony clone next to the project (`../nimony`, or `NIMONY_DIR`), at `3f56467ab15a46746c4f2b33a904809a2ffa0a12` (master, 2026-10-20); the pin is `NIMONY_PIN` in `nnimony/tools/queue.py` |
| Target | `nnimony/` mirrors `src/`: `src/lib/bitabs.nim` → `nnimony/lib/bitabs.py`, `src/models/tags.nim` → `nnimony/models/tags.py` |
| Queue | `nnimony/conversion_queue.md`, generated by `python -m nnimony.tools.queue` |
| Agent briefs | `nnimony/brief_<name>.md` |

### 13.2 Module layout

| Nim (nimony) | Python (nimic) | Notes |
| --- | --- | --- |
| a module `src/lib/bitabs.nim` | `nnimony/lib/bitabs.py`, starting with `# /// nimic`, `# source: nimony@<sha>:src/lib/bitabs.nim`, `# ///`, then the original header comments | Every module records the commit it was converted from. A re-pin is applied as upstream diffs since that commit |
| `import std/assertions`, `import std / [hashes, tables]` | `from nimic.std.assertions import *`, `from nimic.std.hashes import *` ... | nimony's `src/config.nims` makes a missing `std/` prefix an error (`StdPrefix`); nimic's std imports transpile with the prefix |
| `import bitabs` (a sibling) | `from .bitabs import *` | |
| `import ".." / models / [tags]`, `import ".." / lib / [vfs, nimversion]` | `from ..models.tags import *`, `from ..lib.vfs import *` | One `from` per module; paths keep nimony's directories |
| `when defined(nimony):` / `when not defined(nimony):` | `if comptime(defined("nimony")):` / `if comptime(not defined("nimony")):` | Converted with every branch, like any `when` (§2.1). Python runs the host-Nim (Nim 2) build, where `nimony` is not defined |
| `proc `!&`(h: UHash; val: uint32): UHash` (a custom operator) | `def _mix_hash(h: UHash, val: uint32) -> UHash:  # Nim: proc `!&`(...)` | Custom operators get letter names, private ones with `_` (example: `nnimony/lib/tinyhashes.py`) |

### 13.3 Build profile

- **`nnimony/nim.cfg`** mirrors nimony's `src/config.nims`: `define:nimPreviewSlimSystem` and
  `experimental:strictDefs`. Python runs read it as the `nim.cfg` of `nnimony/`.
- **The Nim checks** build in a copy of nimony's `src/`, which carries the original `config.nims`.

### 13.4 Tests and verification

- **Tests:** a module's tests go at the end, under `if comptime(__name__ == "__main__"):`, and print their
  results with `echo`. A `when isMainModule` block of the original is converted like any code; added
  tests come after it.
- **Use only names the original module has.** The verification appends the transpiled test block to the
  original module.
- **`tests/verify_transpiled.py nimony`** checks three things per converted module:
  1. **module:** `nim check` of the transpiled module in a copy of nimony's `src/`;
  2. **tests:** the output of Python and of the compiled transpiled module are equal;
  3. **original:** the output of Python and of the original nimony module, compiled with the transpiled
     test block appended, are equal. This is the check of fidelity to the source.

## 14. Nim 3 constructs

nimony's sources are written to compile with Nim 2 as well. In the host-Nim build, Nim 3-only code sits in
`when defined(nimony)` branches, or behind `compat2.nim`. nimic gains the Nim 3 constructs as conversions
need them. Until then a converted module writes them faithfully inside their inactive branch, or marks them
`# TODO: requires nimic feature <name>`.

| Nim 3 (nimony) | Replaces (Nim 2 rows of §0–§12) | nimic support |
| --- | --- | --- |
| `{.feature: "lenientnils".}`, `{.feature: "untyped".}`, `{.feature: "assumeSync".}` (module features), any standalone pragma `{.p.}` | — | `pragma('feature: "lenientnils"')` as a statement (`rule:pragmastmt`), usually in its `when defined(nimony)` branch. No effect in Python |
| `{.pragma: maybeDirty, dirty.}`, `{.pragma: untyped.}` (a pragma alias) | — | `pragma("pragma: maybeDirty, dirty")` (`rule:pragmastmt`). Defines the alias for the module's routines: `"""{.maybeDirty.}"""` on a template makes it dirty in Python too. An alias to nothing (`{.pragma: untyped.}`) is an empty pragma |
| `template nifEmits*(kind: string) {.pragma.}` (a custom pragma), `proc p() {.nifEmits: "D".}` | — | `@template`<br>`def nifEmits(kind: string):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.pragma.}"""` (the docstring is the whole body: no Nim body, `rule:funcdefbody`); used like any pragma, `"""{.nifEmits: "D".}"""`. Its `##` doc comment lines follow the docstring as comments. No effect in Python |
| `static:` blocks | — | `with static:` (`rule:dropwith`). Python runs the body when the module runs (Nim's compile time): a failing `assert` stops the import |
| Case-sensitive identifiers | style-insensitive names (`is_nil` row) | planned: `{.feature: "ignoreStyle".}` per module, or exact names |
| `nil ref T` / `nil ptr T` (refs are not nil by default) | `None` for nilable refs | planned: a nilable marker |
| `raise IOError`, `except IOError:` (no `as e`), `{.raises.}` opt-in; `ErrorCode` values | exceptions as classes with messages | planned |
| `case` inside `object`: the new syntax | the `match kind:` variant row | planned: transpiler output |
| explicit generic parameters (`proc f[T: SomeInteger](x: T)`), concepts | implicit generics (`x: SomeInteger`) | planned: always emit `[T: ...]` |
| strings without a terminating `'\0'`; `cstring` of a string copies | cstring rows, `s[s.len]` row | planned: a per-target string model |
| polymorphic accessors (`func [](x: C): var E`) | `var T` overloads | planned |
| `func` is `noSideEffect`, `proc` side-effecting, no inference; `{.cast(noSideEffect).}:` | `func` row | planned |
| unlabeled `break` leaves only a loop | — | already so: blocks are left with `breakBlock("name")` |
| compiler plugins | macros (G17) | later |
| `range` checked at compile time, no runtime checks | `Natural`/`RangeDefect` rows | to decide (Python can't prove) |
