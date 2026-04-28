# Nimic

Nimic is a pure Python module that facilitates writing AOT compilable code with a subset of Python (domain specific language). Based on ctypes built-in module, it includes emulation of native types, pointers and operations on them, implementing dispatch, operator overloading, and templates. Nimic closely follows Nim programming language, to which nimic code transpiles.

**Key principle:** nimic code is valid Python that runs natively *and* transpiles to equivalent Nim code.

## Module Architecture

```
nimic/
├── ntypes.py       — Public API: re-exports type system + Nim keyword/builtin shims
├── ntypesystem.py  — Core type system (Object, NScalar, seq, dispatch, distinct, converter)
├── transpiler.py   — AST-based Python → Nim source code transpiler
├── inliner.py      — Template function inlining (@template, @template_expand)
├── ncode/          — Nim definitions (pydefs.nim, pystd/)
├── std/            — Python shims for Nim stdlib (math, options, os, paths, strformat, ...)
└── system/         — Python shims for Nim system modules (ansi_c)
```

### ntypesystem.py — Core Type System

Organized in layers from low-level memory to high-level abstractions:

| Layer | Classes | Purpose |
|-------|---------|---------|
| Memory | `Ntype`, `NTypeRegistry` | ctypes-backed buffers with value semantics |
| Scalars | `NScalar` → `NInteger` / `NFloat` | Fixed-width types (`int8`..`int64`, `uint8`..`uint64`, `float16`..`float64`) with arithmetic promotion |
| Structs | `Object` | Nim "object" — fields via annotations, backed by `ctypes.Structure` |
| Enums | `NIntEnum` | Nim integer enums with auto-registration |
| Variants | `Object` + `match kind:` | Nim "case object" — discriminated unions |
| Containers | `seq[T]`, `UncheckedArray[T]` | Growable sequence and pointer-indexed array |
| Dispatch | `@dispatch`, `DispDict`, `NMetaClass` | Nim-style multi-dispatch via type annotations |
| Modifiers | `@distinct`, `@converter` | Type distinctness and trivial type conversions |
| Strings | `string` | `str` subclass with Nim-compatible `&`, `%`, `isEmpty` |

### ntypes.py — Public API & Keywords

Re-exports all of `ntypesystem` and adds Nim keyword/builtin emulation:

- **Compiler hints** — `const`, `let`, `var`, `block`, `export`, `alias` (no-ops in Python, scoping in Nim)
- **Reference types** — `ref`, `ptr`, `mut@` (`@` operator returns identity)
- **Enum utilities** — `NStrEnum` with `succ`/`pred`/`ord`/`nrange`/`low`/`high`
- **Cast & memory** — `cast[T](x)`, `sizeof(x)`, `addr(x)`, `unsafe_addr(x)`
- **Type aliases** — `SomeInteger`, `SomeFloat`, `untyped`, `char`, `u64`, `i64`, `f64`
- **Iteration** — `fields(obj)`, `fields(a, b)`, `countdown(a, b)`
- **Compile-time** — `comptime(x)`, `defined(varname)`, `static`
- **Templates** — `@template`, `@template_expand` (re-exported from `inliner`)

### transpiler.py — Python → Nim Transpiler

A modified CPython `ast.py` where `_Unparser` is extended to emit Nim syntax.
Implements 30+ transformation rules for indentation, type definitions, function
signatures, operators, imports, and control flow.

### inliner.py — Template Inlining

`@template` + `@template_expand` decorators perform AST-level function inlining
for untyped templates, substituting parameter names with call arguments.

## DSL Conventions

Nimic uses Python syntax with specific conventions that have dual meaning — runtime behavior in Python and transpilation semantics for Nim:

| Convention | Example | Purpose |
|---|---|---|
| `with let/var/const:` | `with let: x = vec3(1,2,3)` | Variable declaration scope qualifier |
| `mut @` annotation | `def f(x: mut @ Vec3):` | Mutable argument (`var` in Nim) |
| `{.pragma.}` docstring | `"""{.inline.}"""` | Nim pragma (inline, borrow, noSideEffect) |
| `@dispatch` | `@dispatch` <br> `def f(x: float64):` | Multi-dispatch by argument types |
| `@distinct` | `@distinct` <br> `class Color(Vec3):` | Distinct type (no implicit conversion) |
| `@template` | `@template` <br> `def toUV(v):` | Template (inlined at call site) |
| `@converter` | `@converter` <br> `def toVec3(uv):` | Implicit type converter |
| `<<=` | `dst <<= -src` | Value assignment to mutable variable |
| `match kind:` | `match kind:` <br> &nbsp;&nbsp;`case K.a: ...` | Variant type definition (case object) |
| `comptime(expr)` | `if comptime(cond):` | Compile-time evaluation (`when` in Nim) |
| `fields(obj)` | `for f in fields(obj):` | Iterate over object fields |
| `with export:` | `with export: mod1, mod2` | Re-export modules |

## Quick Example

```python
from __future__ import annotations
from nimic.ntypes import *

# Struct definition (Nim object)
class Vec3(Object):
    x: float64
    y: float64
    z: float64

    def __add__(self: Vec3, v: Vec3) -> Vec3:
        """{.inline.}"""
        result = Vec3()
        result.x = self.x + v.x
        result.y = self.y + v.y
        result.z = self.z + v.z
        return result

# Distinct type
@distinct
class Point3(Vec3):
    """{.borrow: `.`.}"""

# Multi-dispatch
@dispatch
def point3(x: float64, y: float64, z: float64) -> Point3:
    result = Point3(Vec3())
    result.x = x; result.y = y; result.z = z
    return result

# Usage
with let:
    a = point3(1.0, 2.0, 3.0)
    b = point3(4.0, 5.0, 6.0)
    c = Vec3(a) + Vec3(b)
```
