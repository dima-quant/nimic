# Nimic

Nimic allows using pure Python as a systems language with AOT compilation. It provides systems-level functionality directly within CPython (backed by the built-in `ctypes` module), while allowing the exact same code to compile Ahead-Of-Time (AOT) to an efficient native binary.

By closely following the Nim programming language, `nimic` includes emulation of native types, pointers and operations on them, multi-dispatch, operator overloading, templates and more. Nimic code is a statically typed Python subset (domain specific language) which transpiles to Nim, achieving C-level performance without leaving Python.

**Key principle:** `nimic` code is valid Python that runs unmodified in CPython *and* transpiles to equivalent Nim code.

## Projects built with nimic

- [Raytracer, including a ppm-to-mp4 converter](http://github.com/dima-quant/ndsl_raytracer)
- [Python module for preprocessing image data](/examples)

## Installation
```bash
python3 -m pip install nimic
```

## Why Nimic?
At the time of writing, Nimic is the only package that provides comprehensive systems language functionality running directly in CPython, while allowing the corresponding code to compile AOT to an efficient native binary or C-module. Why Nim? Its syntax maps well to Python, it is rather clear how to emulate its constructions in Python, and its performance is comparable to C (as it compiles to C).

- Because nimic code is just standard Python with type hints and ctypes shims, it is a fully valid CPython script, so you can use the Python REPL during development, drop a breakpoint in the middle of a heavy algorithmic loop and inspect the variables natively.
- Zero Lock-In: You don't need a special runtime engine. If the Nim compiler is not available, your script still runs (albeit slower than standard Python due to some emulation overhead) on any machine with CPython installed.
- Seamless Distribution: You can use this to develop high-performance logic natively in Python, debug it with Python tooling, and then compile to a native executable or C-extension via Nim.
- Benchmarking performed with the [raytracer](http://github.com/dima-quant/ndsl_raytracer) demonstrates the render time for a single 512x288 scene dropped from many hours in pure Python to just 10 minutes on a single M1 CPU core.

The module is still work in progress, currently it supports the following Nim types and features:
- Fixed-width integer and floating point types
- Structs and objects
- Enums
- Arrays and dynamic arrays (sequences)
- String
- Named tuples
- Variant types
- Multi-dispatch with generics
- Operator overloading and type distinctness
- Iterators
- Bitwise operations, references, pointer cast and pointer arithmetics
- Parts of Nim standard library
- Templates and compile time conditions

## Similar projects
Projects supporting Python code actually running in CPython runtime:
- Cython (https://github.com/cython/cython): Cython translates Python code to C/C++ code, but additionally supports calling C functions and declaring C types on variables and class attributes.
- Mypyc (https://github.com/python/mypy/tree/master/mypyc): Mypyc compiles Python modules to C extensions. It uses standard Python type hints to generate fast code.
- Pyccel (https://github.com/pyccel/pyccel): Python extension language using accelerators
- Shed Skin (https://github.com/shedskin/shedskin): a transpiler, that can translate pure, but implicitly statically typed Python 3 programs into optimized C++.
- Numba (https://github.com/numba/numba): NumPy aware dynamic Python compiler using LLVM.

Projects with a different language and runtime:
- SPy (https://github.com/spylang/spy) is a variant of Python specifically designed to be statically compilable while retaining a lot of the "useful" dynamic parts of Python.
- Codon (https://github.com/exaloop/codon) is a high-performance Python implementation that compiles to native machine code without any runtime overhead.
- Mojo (https://github.com/modular/modular/tree/main/mojo): a new programming language that bridges the gap between research and production by combining Python syntax and ecosystem with systems programming and metaprogramming features.


## Quick Example

*This example (adapting parts of the ppm-to-mp4 converter code) demonstrates `nimic`'s ability to handle low-level systems logic, such as memory allocation, pointer arithmetic, and struct casting, live inside the standard Python interpreter before compiling.*

```python
from __future__ import annotations
from nimic.ntypes import *
from nimic.system.ansi_c import c_malloc, c_free, csize_t

@ptr
class Frame(Object):
    Y: ptr[UncheckedArray[uint8]]
    Cb: ptr[UncheckedArray[uint8]]
    Cr: ptr[UncheckedArray[uint8]]
    lumaWidth: int32
    lumaHeight: int32
    size: int32
    buffer: UncheckedArray[uint8]

with var:
    width = 1920
    height = 1080
    size = width * height
    frame = cast[Frame](
        alloc_shared0(
            3 * sizeof(pointer) +
            3 * sizeof(int32) +
            size
        )
    )

frame.size = int32(size)
frame.lumaWidth = int32(width)
frame.lumaHeight = int32(height)
frame.Y = cast[ptr[UncheckedArray[uint8]]](addr(frame.buffer))
frame.Cb = frame.Y
frame.Y[0] = uint8(1)

assert frame.Cb[0] == uint8(1)

def fourCC(a: char, b: char, c: char, d: char) -> uint32:
    """{.inline.}"""
    return (uint32(ord(a)) << 24) | (uint32(ord(b)) << 16) | (uint32(ord(c)) << 8) | uint32(ord(d))

with var:
    stackBase = array[20, ptr[uint8]]()
    stack = cast[ptr[ptr[uint8]]](addr(stackBase[0]))
with let:
    indexBytes = 1024
    base = cast[ptr[uint8]](c_malloc(csize_t(indexBytes)))
with var:
    p = base.copy()  # copy pointer as mutable
with let:
    BOX_trak = fourCC(ch('t'),ch('r'),ch('a'),ch('k'))
    x = BOX_trak

cast[ptr[ptr[uint8]]](stack).contents = p  # save pointer p to stackBase
stack <<= cast[ptr[ptr[uint8]]](cast[intp](stack) + sizeof(pointer))  # update stack pointer
p <<= cast[ptr[uint8]](cast[intp](p) + 4)
p.contents = uint8((x >> 24) & 0xFF)
p <<= cast[ptr[uint8]](cast[intp](p) + 1)
p.contents = uint8((x >> 16) & 0xFF)
p <<= cast[ptr[uint8]](cast[intp](p) + 1)
p.contents = uint8((x >> 8) & 0xFF)
p <<= cast[ptr[uint8]](cast[intp](p) + 1)
p.contents = uint8(x & 0xFF)
p <<= cast[ptr[uint8]](cast[intp](p) + 1)
stack <<= cast[ptr[ptr[uint8]]](cast[intp](stack) - sizeof(pointer))  # restore stack pointer

with let:
    atomStart = cast[ptr[ptr[uint8]]](stack).contents

with let:
    xu = uint32(cast[intp](p) - cast[intp](atomStart))
    arr = cast[ptr[UncheckedArray[uint8]]](p)
    arr[0] = uint8((xu >> 24) & 0xFF)
    arr[1] = uint8((xu >> 16) & 0xFF)
    arr[2] = uint8((xu >> 8) & 0xFF)
    arr[3] = uint8(xu & 0xFF)

assert arr[3] == uint8(8)  # pointer offset
with let:
    arr = cast[ptr[UncheckedArray[uint8]]](atomStart)
assert arr[4] == uint8(ord(ch('t')))

c_free(base)
```

## Module Architecture

```
nimic/
├── ntypes.py       — Public API: re-exports type system + Nim keyword/builtin shims
├── ntypesystem.py  — Core type system (Object, NScalar, seq, dispatch, distinct, converter)
├── transpiler.py   — AST-based Python → Nim source code transpiler
├── inliner.py      — Template function inlining (@template, @template_expand)
├── ncode/          — Nim definitions (pydefs.nim, pystd/)
├── nimpy/          — API for generating Python libraries
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


