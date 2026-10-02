---
name: nimic-convert
description: >-
  Translate a Nim compiler source file (.nim) to Nimic Python (.py) line-for-line.
  Use when asked to convert, translate, or port a compiler module from Nim to Nimic.
---

# Nimic Conversion Skill

Translate a Nim compiler source file from `compiler/[filename].nim` to Nimic Python in `ncompiler/[filename].py`, then automatically trigger a review.

## Prerequisites

Before converting `[filename]`, check `compiler/dep.md` for its dependencies.
**All dependencies must already be converted** (exist as `.py` files in `ncompiler/`).
If a dependency is missing, convert it first. Only create minimal stubs when strictly necessary and no other ordering is possible.

If the file already exists in `ncompiler/`, re-verify the entire conversion from scratch — do not assume it is correct.

## Step 1 — Read the Source

1. Open `compiler/[filename].nim` and read the entire file.
2. Open `compiler/dep.md` and note the dependencies listed for `[filename]`.
3. Open `nimic_translation_rules.md` from the project root and keep it as your primary reference.

## Step 2 — Translate Line-for-Line

Create `ncompiler/[filename].py` with the nimic boilerplate header:

```python
# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
```

Translate every construct following `nimic_translation_rules.md`. Key rules to remember:

> [!TIP]
> **When unsure about Nimic syntax**, always consult these two resources first:
> 1. **`nimic_translation_rules.md`** (project root) — the authoritative reference for every Nim → Nimic mapping (variables, types, operators, functions, pointers, enums, etc.).
> 2. **`tests/nraytracer/`** — a complete, working Nimic project with 30+ modules demonstrating correct usage patterns for `mut @ T`, `@dispatch`, `Tset`, `seq`, `array`, `Object`, `NIntEnum`, `ref[T]`, `ptr[T]`, iterators, templates, and more.
>
> Do **not** guess or invent syntax. If the translation rules don't cover a construct, check nraytracer for a working example. If neither covers it, follow the "Missing Nimic Features" section below.

- **Naming**: Use `snake_case` for functions/attributes (Nim's `camelCase` → Python `snake_case`).
- **Imports**: Do NOT use extra module qualification if the original Nim source did not use it. If Nim writes `Table` directly, import it directly (`from nimic.std.tables import Table`), not `std.tables.Table`.
- **Variables**: `var` → `with var:`, `let` → `with let:`, `const` → `with const:`.
- **Result variable**: No need to declare `result = Type()` if the value is defined by the very next line.
- **Loops**: Convert Nim loops as Python loops. Do not use Python expressions or idioms (no list comprehensions replacing loops).
- **Ranges**: Inclusive ranges `a..b` → `inrange(a, b)`. Half-open ranges `0 ..<a` → `range(a)`.
- **Sets**: `set[T]` → `Tset[T]`. Initialize with `Tset[T](inrange(low(T), high(T)))`.
- **Types**: `int` → `nint`, `string` → `string`, `bool` → `bool`. Char literals: `'#'` → `ch("#")`. **Do not shadow Python's `int`**: always use `nint` for Nim `int` (in type annotations, field types, parameter types, return types, and explicit casts like `nint(x)`). Standard Python integer literals (e.g. `0`, `1`, `42`) are allowed.
- **Operators**: Nim binary `and`/`or` → Python `&`/`|`. Bitwise shift `shr`/`shl` → `>>`/`<<`.
- **Local variables**: Variables without `*` export marker should be prefixed with `_` to prevent transpiling as public.
- **Pointers**: `ptr T` → `ptr[T]`, `p[]` → `p.contents`, `addr x` → `addr(x)`.
- **Enums**: `type E = enum` → `class E(NIntEnum):` with `auto()` values.
- **Objects**: `type T = object` → `class T(Object):`.
- **Case/match**: Nim `case` → Python `match`.
- **Templates**: `template foo()` → `@template def foo()`.
- **Compile-time**: `when` → `if comptime(...)`.
- **Discard**: `discard foo()` → `_ = foo()`.

### No Python-Mode-Only Code

> [!IMPORTANT]
> **All code — including test cases — must be valid Nimic that compiles and runs in Nim after transpiling.**
> Do not use Python builtins, idioms, or workarounds that would not survive transpilation. Every line must be dual-mode: runnable as Python via `python -m ncompiler.[filename]` **and** compilable/runnable as Nim via `nim r` on the transpiled output.
>
> Common violations to avoid:
> - Using `f-string` formatting (use `string("...") % [args]` instead)
> - Using Python `with open(...) as f:` (use `var f: File; open(f, path, fmWrite)` pattern instead)
> - Using Python `list` instead of `seq` for typed sequences
> - Using `isinstance()` or other Python reflection where Nim uses type dispatch
> - Using chained comparisons like `0 <= x <= 10` (use `x >= 0 and x <= 10` instead)

### Missing `nimic.std` modules

If the Nim source imports a `std/` module not yet in `src/nimic/std/`, create a basic implementation proactively. Add the necessary types and functions that the current file uses, following the patterns in existing `src/nimic/std/*.py` files.

### Naming Convention for `nimic.std` Functions

> [!IMPORTANT]
> Every new function added to any `src/nimic/std/*.py` module **must** follow this convention:
> 1. Implement the function with a **Pythonic `snake_case` name** (e.g., `to_octal`, `split_whitespace`, `walk_dir`).
> 2. Create a **`camelCase` alias** immediately after (e.g., `toOctal = to_octal`, `splitWhitespace = split_whitespace`, `walkDir = walk_dir`).
>
> This ensures the function is accessible via both naming conventions — `snake_case` for Python-native callers and `camelCase` for Nim-idiomatic callers.

### Custom Operators with Limited Scope

Nim allows defining operators with backtick-quoted names (e.g., `` proc `|+|`*(a, b: BiggestInt) ``). When such operators **cannot** be represented as Python operators (no dunder mapping) and are **only used within the compiler codebase** (not in Nim's stdlib or user-facing API), rename them to regular function names everywhere:

| Nim operator | Python function name |
|---|---|
| `` `\|+\|` `` | `sat_plus` |
| `` `\|-\|` `` | `sat_minus` |
| `` `\|abs\|` `` | `sat_abs` |
| `` `\|div\|` `` | `sat_div` |
| `` `\|mod\|` `` | `sat_mod` |
| `` `\|*\|` `` | `sat_mul` |

**General rule**: Any operator with a limited scope that cannot be expressed as a Python operator should be converted to a descriptively named function. The downstream call sites (consumers listed in `compiler/dep_tree.md`) must also be updated to use the new function name.

### Legacy Unsigned Wrap-around Operators (`+%`, `-%`, `*%`)

These operators perform unsigned 64-bit wrapping arithmetic. They are legacy Nim operators rarely used in modern Nim. Replace them with **explicit unsigned type conversions** using the nimic type system:

| Nim | Python (Nimic) |
|---|---|
| `a +% b` | `int64(uint64(a) + uint64(b))` |
| `a -% b` | `int64(uint64(a) - uint64(b))` |
| `a *% b` | `int64(uint64(a) * uint64(b))` |

This works because `uint64` and `int64` in nimic are `NInteger` subclasses that handle overflow wrapping via `_n_normalize`. If a variable has only a limited local scope, it can be directly defined as having the unsigned type instead of casting back and forth.

### Nimic Type System Awareness

The nimic type system is defined in `src/nimic/ntypesystem.py`. Key types available for conversions:
- **Integer types**: `int8`, `int16`, `int32`, `int64`, `uint8`, `uint16`, `uint32`, `uint64`, `nint`
- **Float types**: `float16`, `float32`, `float64`
- **Type aliases**: `BiggestInt = int` (Python int, unbounded), `BiggestFloat = float`
- **Shorthand constructors**: `u64(x)`, `i64(x)`, `u32(x)`, `i32(x)`, etc.
- All `NInteger` subclasses handle overflow wrapping automatically via `_n_normalize`

Refer to `src/nimic/ntypesystem.py` for the full type hierarchy and `tests/nraytracer/` for a working medium-size nimic project that demonstrates correct usage patterns.

### Missing Nimic Features

If you encounter a Nim construct that **cannot** be expressed with current Nimic capabilities and is not covered by `nimic_translation_rules.md`:

1. **Do not hack around it** with Python builtins or workarounds.
2. Instead, create a feature proposal following the `nimic-propose-feature` skill.
3. Mark the location in the converted file with a `# TODO: requires nimic feature [name]` comment.
4. Continue converting the rest of the file.

## Step 3 — Add Tests

At the end of `ncompiler/[filename].py`, add:

```python
if comptime(__name__ == "__main__"):
    # Test cases here
```

Write test cases that exercise the most important and non-trivial functionality of the module. Consult `compiler/dep_tree.md` to see which modules import this one, and what functionality they typically use — test those APIs.

> [!IMPORTANT]
> **Tests must be valid Nimic** — they must survive transpilation and execute correctly in Nim via `nim r`.
> - Do not use Python-only testing constructs (`unittest`, `pytest`, `assert` with f-strings, etc.).
> - Use `doAssert(condition, string("message"))` for assertions.
> - Use `echo(string("..."))` for output.
> - Wrap test code in a `def test_[filename]():` function if callbacks or closures are needed, to ensure they satisfy Nim's `{.closure, gcsafe.}` requirements.

## Step 4 — Run Tests in Python

Run the tests in Python mode:
```bash
cd /Users/dima/Documents/Scripts/Ndsl
.venv/bin/python -m ncompiler.[filename]
```

If tests fail, debug and fix. If the failure is due to a missing Nimic feature, create a proposal (see above).

## Step 5 — Transpile and Execute in Nim

> [!IMPORTANT]
> This step verifies that the converted code actually compiles and runs as native Nim.

1. **Transpile** to Nim source:
   ```bash
   .venv/bin/python -c '
   from nimic import transpiler
   from nimic.ntypesystem import _n_registry
   import ncompiler.[filename] as mod
   import inspect, pathlib
   src = inspect.getsource(mod)
   aast = transpiler.parse(src)
   nim_src, _ = transpiler.unparse(aast, _n_registry)
   pathlib.Path(".scratch/[filename].nim").write_text(nim_src)
   print(nim_src[:500])
   '
   ```

2. **Compile and run** the transpiled Nim:
   ```bash
   nim r --hints:off --path:.scratch --path:src/nimic --path:compiler .scratch/[filename].nim
   ```

3. **Verify** that the output matches the Python-mode test output exactly.

If Nim compilation fails, debug and fix the Nimic source. Common issues:
- Missing export asterisks (functions wrapped in extra scope blocks)
- Chained comparisons (`0 <= x <= 10` must be split to `x >= 0 and x <= 10`)
- Python-only constructs that don't transpile
- String formatting using f-strings instead of `%` operator

## Step 6 — Trigger Review

After conversion is complete and **both Python and Nim execution pass**, **automatically** invoke the `nimic-review` skill on the same `[filename]` using a separate subagent. The review must be performed independently — do not review your own conversion.

## Reference Files

- Translation rules: `nimic_translation_rules.md` (project root)
- Feature addition protocol: `nimic_add_feature.md` (project root)  
- Dependency order: `compiler/dep.md`
- Downstream consumers: `compiler/dep_tree.md`
- Example nimic project: `tests/nraytracer/`
- Already converted files: `ncompiler/*.py`
- Nimic std library: `src/nimic/std/`
- Nimic type system: `src/nimic/ntypesystem.py`
- Nimic transpiler: `src/nimic/transpiler.py`
