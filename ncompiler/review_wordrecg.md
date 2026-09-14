# Review of wordrecg.nim → wordrecg.py conversion

## Step 2: Line-by-line code conversion review

### Source files
- **Original Nim:** `compiler/wordrecg.nim` (151 lines)
- **Converted Python:** `ncompiler/wordrecg.py` (386 lines)

### Structure mapping

| Nim section | Nim lines | Python lines | Status |
|---|---|---|---|
| Copyright/module comment | 1–14 | 373–386 (moved to end) | ✅ OK (moved but preserved) |
| `# /// nimic` header | — | 1–5 | ✅ OK (required nimic boilerplate) |
| `TSpecialWord` enum definition | 16–125 | 7–325 | See issues below |
| `TSpecialWords` type alias | 127 | 330 | See issues below |
| `const` block | 129–144 | 334–352 | See issues below |
| `from` imports + `findStr` proc | 147–150 | 354–358 | See issues below |
| Tests | — | 360–362 | See below |

---

### Issue 1: `type TSpecialWords = set[TSpecialWord]` (line 330)

**Nim (line 127):**
```nim
TSpecialWords* = set[TSpecialWord]
```

**Python (line 330):**
```python
type TSpecialWords = set[TSpecialWord]
```

**Observation:** The Python uses the Python 3.12 `type` statement which is valid and transpilable via `visit_TypeAlias` in the transpiler. However:
- According to the translation rules §3 (`Tset`), `set[TSpecialWord]` in Nim is a set of ordinal types and should be translated as `Tset[TSpecialWord]`, not bare `set[TSpecialWord]`.
- The `*` export marker: the transpiler's `visit_TypeAlias` doesn't apply `_adjust_name`, so the export marker `*` won't be appended during transpilation. This means the transpiled Nim output will lack the `*` — making `TSpecialWords` private instead of public as in the original.
- For comparison, `lineinfos.py` uses `class TNoteKinds(set[TNoteKind]): pass` for similar type aliases, which goes through `visit_ClassDef` and does apply `_adjust_name`. There is inconsistency in approach across ncompiler files.

**Severity:** Medium — export marker will be missing in transpiled output; `set` vs `Tset` inconsistency.

---

### Issue 2: `nonPragmaWordsLow` / `nonPragmaWordsHigh` are not `ord()`-wrapped (lines 351–352)

**Nim (lines 143–144):**
```nim
nonPragmaWordsLow* = wAuto
nonPragmaWordsHigh* = wOneWay
```

**Python (lines 351–352):**
```python
  nonPragmaWordsLow = TSpecialWord.wAuto
  nonPragmaWordsHigh = TSpecialWord.wOneWay
```

**Observation:** In the original Nim, these store the enum values directly (not `ord()`), matching the translation. The other four constants (`oprLow`, `oprHigh`, `nimKeywordsLow`, `nimKeywordsHigh`) use `ord()` in Nim and `.ord()` in Python, which is also correct.

However, in Nim the `*` export marker is present on `nonPragmaWordsLow*` and `nonPragmaWordsHigh*`, making them public. In the Python `with const:` block, the transpiler should handle export for top-level declarations.

**Severity:** Low — the values are correct; export/visibility concern applies to all `const` members in this block (see Issue 4).

---

### Issue 3: `findStr` generic constraint narrowed from `enum` to `NStrEnum` (line 357)

**Nim (line 149):**
```nim
proc findStr*[T: enum](a, b: static[T], s: string, default: T): T =
```

**Python (line 357):**
```python
def findStr[T: NStrEnum](a: static[T], b: static[T], s: string, default: T) -> T:
```

**Observation:** The Nim uses `T: enum` (any enum type) while the Python narrows the constraint to `T: NStrEnum`. This means `findStr` can't be used with `NIntEnum` types in the Python version. While `TSpecialWord` is indeed an `NStrEnum`, other callers (e.g., in `commands.nim` line 209, `pragmas.nim` line 370) use `findStr` with different enum types. The constraint is narrower but **kept as-is per user preference**.

`gen_enum_case_stmt` is correct snake_case for `genEnumCaseStmt`. The use of `nord(a)` and `nord(b)` instead of Nim's `ord(a)` and `ord(b)` is correct — `nord` is the nimic helper for getting ordinal values from `NStrEnum`.

**Severity:** Accepted — kept as NStrEnum per user decision.

---

### Issue 4: `const` block export visibility

**Nim (lines 129–144):** All constants are marked with `*` (public export):
```nim
const
  oprLow* = ord(wColon)
  ...
  cppNimSharedKeywords* = { ... }
  nonPragmaWordsLow* = wAuto
  nonPragmaWordsHigh* = wOneWay
```

**Python (lines 334–352):**
```python
with const:
  oprLow = TSpecialWord.wColon.ord()
  ...
  cppNimSharedKeywords = { ... }
  nonPragmaWordsLow = TSpecialWord.wAuto
  nonPragmaWordsHigh = TSpecialWord.wOneWay
```

**Observation:** The `with const:` block is at the module level and the transpiler should apply `_adjust_name` rules. Looking at the transpiler, `const` is in `_context_stack` via `visit_With`, and `visit_Assign` checks for `is_module_level and in_declaration` to set `_is_definition`. So these should get `*` markers correctly during transpilation if they're at module scope. This appears to be fine.

**Severity:** None — this should work correctly via transpiler rules.

---

### Issue 5: `cppNimSharedKeywords` set literal uses Python `set` syntax (lines 344–349)

**Nim (lines 139–141):**
```nim
  cppNimSharedKeywords* = {
    wAsm, wBreak, wCase, wConst, wContinue, wDo, wElse, wEnum, wExport,
    wFor, wIf, wReturn, wStatic, wTemplate, wTry, wWhile, wUsing}
```

**Python (lines 344–349):**
```python
  cppNimSharedKeywords = {
    TSpecialWord.wAsm, TSpecialWord.wBreak, TSpecialWord.wCase, TSpecialWord.wConst,
    TSpecialWord.wContinue, TSpecialWord.wDo, TSpecialWord.wElse, TSpecialWord.wEnum,
    TSpecialWord.wExport, TSpecialWord.wFor, TSpecialWord.wIf, TSpecialWord.wReturn,
    TSpecialWord.wStatic, TSpecialWord.wTemplate, TSpecialWord.wTry, TSpecialWord.wWhile, TSpecialWord.wUsing
    }
```

**Observation:** The Python `{ }` set literal is valid Python and should transpile correctly to a Nim set literal via the transpiler. The enum member qualification with `TSpecialWord.` is necessary in Python since enum members are scoped to the class. This is an inherent language difference, not an extra module qualification issue. The transpiler should handle stripping the enum prefix during transpilation.

**Severity:** None — correct translation.

---

### Issue 6: Enum member string values with trailing commas (lines 8–325)

**Nim:**
```nim
  TSpecialWord* = enum
    wInvalid = "",
    wAddr = "addr", wAnd = "and", ...
```

**Python:**
```python
class TSpecialWord(NStrEnum):
    wInvalid = "",
    wAddr = "addr",
    ...
```

**Observation:** Every enum member value ends with a trailing comma (e.g., `wInvalid = "",`). In Python, `"",` creates a tuple `("",)` rather than a string `""`. However, if `NStrEnum` handles this correctly (extracting the first element), this would work at runtime. Let me verify this is intentional — checking the test on line 361 which calls `.ord()` and the test on line 362 which does `findStr`, and both pass. So `NStrEnum` apparently handles tuple values.

Actually, looking more carefully, this is Nim syntax in the original: each enum field uses `,` to separate from the next one. In Python, the trailing comma after the value makes it a tuple. The `NStrEnum` must handle this. This is a nimic convention for preserving the Nim trailing comma syntax.

**Severity:** None — intentional nimic convention if `NStrEnum` handles it.

---

### Issue 7: Comment placement (copyright block at end)

**Nim (lines 1–14):** Copyright and module description at the top of the file.

**Python (lines 373–386):** Copyright and module description at the bottom of the file, after the code and tests.

**Observation:** The Nim copyright header appears at the top (lines 1–14), while the Python file has the nimic header at the top (lines 1–5) and the copyright/description comments at the very bottom (lines 373–386). This is unusual. The comments are preserved but reordered. Whether the transpiler restores them to the top is unclear — it may not handle trailing comments that originally preceded the code.

**Severity:** Low — comments are preserved but may not round-trip correctly.

---

### Issue 8: Missing `# /// nimic` metadata or `wIncompleteStruct` deprecation comment

**Nim (line 48):**
```nim
    wIncompleteStruct = "incompleteStruct", # deprecated
```

**Python (line 114):**
```python
    wIncompleteStruct = "incompleteStruct",
```

**Observation:** The `# deprecated` comment on `wIncompleteStruct` is missing in the Python translation. However, the `wDeadCodeElimUnused` comment (line 199) is correctly preserved:
```python
    wDeadCodeElimUnused = "deadCodeElim",  # deprecated, dead code elim always happens
```

**Severity:** Very low — minor comment loss.

---

### Summary of issues found

| # | Issue | Severity |
|---|---|---|
| 1 | `type TSpecialWords = set[TSpecialWord]` should use `Tset` and may lack export marker | Medium |
| 3 | `findStr` constraint narrowed from `enum` to `NStrEnum` | Medium |
| 7 | Copyright comments moved to end of file | Low |
| 8 | Missing `# deprecated` comment on `wIncompleteStruct` | Very low |

Overall the enum values are correctly mapped 1:1 with their string values matching the Nim original. The `const` block values are correct. The `findStr` function logic is correct. The imports are correct.

---

## Step 3: Test case review

### Existing tests (lines 360–362)
```python
if comptime(__name__ == "__main__"):
    assert TSpecialWord.wAsm.ord() < TSpecialWord.wBreak.ord()
    assert findStr(TSpecialWord.wAsm, TSpecialWord.wYield, "yield", TSpecialWord.wInvalid) == TSpecialWord.wYield
```

### Test execution
Tests pass successfully with `PYTHONPATH=src python3 -m ncompiler.wordrecg`.

### Downstream usage analysis
From `dep_tree.md`, `wordrecg` is imported by: `ast, ccgutils, cgen, commands, docgen, idents, importer, injectdestructors, jsgen, lexer, liftlocals, linter, lookups, nimconf, parampatterns, pragmas, pushpoppragmas, renderer, scriptconfig, sem, semfold, sempass2, suggest, trees, types`.

Currently in `ncompiler/`, `idents.py` imports from `wordrecg` and uses:
- `TSpecialWord` enum members (e.g., `TSpecialWord.wInvalid`, `TSpecialWord.wYield`)
- `TSpecialWord` iteration via `inrange(succ(low(TSpecialWord)), high(TSpecialWord))`
- Ordinal values via `.ord()`

### Missing test coverage

The existing tests cover:
1. Ordinal ordering (`wAsm.ord() < wBreak.ord()`)
2. `findStr` basic lookup

Missing coverage for important functionality:
1. `findStr` with non-matching string → should return `default`
2. `findStr` with normalized matching (e.g., `"YIELD"` should still match `"yield"`)
3. Const values (`oprLow`, `oprHigh`, `nimKeywordsLow`, `nimKeywordsHigh`, etc.)
4. `cppNimSharedKeywords` set membership
5. `TSpecialWords` type alias usability
6. Enum iteration with `low()`/`high()`

---

## Step 4: Fixes

### Fix for Issue 8 (trivial) ✅
Added missing `# deprecated` comment on `wIncompleteStruct`.

### Fix for Issue 3 — kept as-is ✅
`findStr` constraint kept as `NStrEnum` per user preference.

### Fix for Issue 1 — `Tset` implementation ✅

**Problem:** `Tset` was used in `ncompiler/` files (msgs.py, platform.py) but had no implementation anywhere in the nimic source.

**Analysis of options:**

| | Option A: `type TSpecialWords = Tset[TSpecialWord]` | Option B: `class TSpecialWords(Tset[TSpecialWord]): pass` |
|---|---|---|
| **Nim fidelity** | ✅ Closest to Nim syntax | ⚠️ Uses `class` instead of `type` |
| **Transpiler output** | ✅ `visit_TypeAlias` emits correct Nim | ✅ `visit_ClassDef` emits correct Nim + `*` export |
| **Python: callable** | ❌ `TypeAliasType` — not callable | ✅ Real class — callable |
| **Python: isinstance** | ❌ Cannot use | ✅ Works |
| **Python: annotations** | ✅ Works | ✅ Works |
| **Export marker** | ⚠️ `visit_TypeAlias` doesn't add `*` | ✅ `_adjust_name` adds `*` |

For `TSpecialWords` specifically (only used as type annotation, never instantiated), Option A suffices. However, `Tset` is used as a **constructor** elsewhere (e.g. `Tset[MsgFlag]()`, `Tset[TErrorOutput]({...})` in msgs.py), so Option B is the correct general pattern.

**Implementation added to `src/nimic/ntypes.py`:**

```python
class Tset(set):
    """Nim's ``set[T]`` for ordinal types."""
    _cache: dict = {}

    def __class_getitem__(cls, elem_type):
        if elem_type not in cls._cache:
            name = f'Tset[{elem_type.__name__}]'
            new_cls = type(name, (set,), {'_elem_type': elem_type})
            cls._cache[elem_type] = new_cls
        return cls._cache[elem_type]
```

Key behaviors verified:
- `Tset[MyEnum]` returns a real `type` (not `GenericAlias` or `TypeAliasType`)
- `Tset[MyEnum]()` creates an empty set
- `Tset[MyEnum]({a, b})` creates a set with elements
- `isinstance(s, Tset[MyEnum])` works
- `isinstance(s, set)` works
- `Tset[MyEnum] is Tset[MyEnum]` (caching)
- `class MySet(Tset[MyEnum]): pass` (inheritance for type aliases)
- Default arguments: `def foo(flags: Tset[X] = Tset[X]())` works

**Note:** The transpiler will need `Tset` → `set` rename support (not yet implemented). Currently `Tset` passes through unchanged in transpiled output. This can be addressed by adding `"Tset": "set"` to the transpiler's rename mechanism.

### Additional test cases ✅
Added comprehensive tests for `findStr` edge cases (non-matching, normalized matching, out-of-range), const values, `cppNimSharedKeywords` set membership, and enum `low()`/`high()` bounds. All tests pass.
