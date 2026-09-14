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

- **Naming**: Use `snake_case` for functions/attributes (Nim's `camelCase` → Python `snake_case`).
- **Imports**: Do NOT use extra module qualification if the original Nim source did not use it. If Nim writes `Table` directly, import it directly (`from nimic.std.tables import Table`), not `std.tables.Table`.
- **Variables**: `var` → `with var:`, `let` → `with let:`, `const` → `with const:`.
- **Result variable**: No need to declare `result = Type()` if the value is defined by the very next line.
- **Loops**: Convert Nim loops as Python loops. Do not use Python expressions or idioms (no list comprehensions replacing loops).
- **Ranges**: Inclusive ranges `a..b` → `inrange(a, b)`. Half-open ranges `0 ..<a` → `range(a)`.
- **Sets**: `set[T]` → `Tset[T]`. Initialize with `Tset[T](inrange(low(T), high(T)))`.
- **Types**: `int` → `nint`, `string` → `string`, `bool` → `bool`. Char literals: `'#'` → `ch("#")`.
- **Operators**: Nim binary `and`/`or` → Python `&`/`|`. Bitwise shift `shr`/`shl` → `>>`/`<<`.
- **Local variables**: Variables without `*` export marker should be prefixed with `_` to prevent transpiling as public.
- **Pointers**: `ptr T` → `ptr[T]`, `p[]` → `p.contents`, `addr x` → `addr(x)`.
- **Enums**: `type E = enum` → `class E(NIntEnum):` with `auto()` values.
- **Objects**: `type T = object` → `class T(Object):`.
- **Case/match**: Nim `case` → Python `match`.
- **Templates**: `template foo()` → `@template def foo()`.
- **Compile-time**: `when` → `if comptime(...)`.
- **Discard**: `discard foo()` → `_ = foo()`.

### Missing `nimic.std` modules

If the Nim source imports a `std/` module not yet in `src/nimic/std/`, create a basic implementation proactively. Add the necessary types and functions that the current file uses, following the patterns in existing `src/nimic/std/*.py` files.

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

## Step 4 — Run Tests

Run the tests:
```bash
cd /Users/dima/Documents/Scripts/Ndsl
python -c "from ncompiler import [filename]"
```

If tests fail, debug and fix. If the failure is due to a missing Nimic feature, create a proposal (see above).

## Step 5 — Transpile Verification

Use the transpiler to verify round-trip fidelity:

```python
from nimic import transpiler
from nimic.ntypesystem import _n_registry
import ncompiler.[filename] as mod
import inspect

src = inspect.getsource(mod)
aast = transpiler.parse(src)
nim_src, _ = transpiler.unparse(aast, _n_registry)
print(nim_src)
```

Verify the transpiled output is recognizable as valid Nim that corresponds to the original `compiler/[filename].nim`. It does not need to compile (dependencies may not be available), but it should be structurally equivalent.

## Step 6 — Trigger Review

After conversion is complete, **automatically** invoke the `nimic-review` skill on the same `[filename]` using a separate subagent. The review must be performed independently — do not review your own conversion.

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
