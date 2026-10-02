---
name: nimic-core-review
description: >-
  Review changes to the nimic core engine scripts (ntypes.py, ntypesystem.py, nsystem.py, transpiler.py)
  for structural quality, SOLID compliance, and ad hoc fix detection.
  Use after conversion and conversion-review cycles, or when core changes are suspected.
---

# Nimic Core Review Skill

Review changes introduced to the four nimic core scripts by conversion and conversion-review agents, ensuring they are implemented in a **proper, generic, and structured** manner rather than as ad hoc fixes. This review operates at the *engine* level — it is about the quality of the core infrastructure itself, not about individual module conversions.

## Core Files Under Review

| File | Responsibility |
|------|---------------|
| `src/nimic/ntypes.py` | Public API — re-exports all user-facing types, functions, and operators from the type system |
| `src/nimic/ntypesystem.py` | Type system engine — class definitions, `@dispatch`, type matching, scalar types, builtins (`high`, `low`, `len`, etc.) |
| `src/nimic/nsystem.py` | System primitives — `cast`, memory management, low-level runtime |
| `src/nimic/transpiler.py` | Python-to-Nim transpiler — AST transformation rules, code generation |

## Step 1 — Identify Changes

Determine the scope of changes since the last committed baseline:

```bash
cd /Users/dima/Documents/Scripts/Ndsl
git diff --stat HEAD -- src/nimic/ntypes.py src/nimic/ntypesystem.py src/nimic/nsystem.py src/nimic/transpiler.py
```

If there are no changes, report "No core engine changes detected" and stop.

For each changed file, extract the full diff for detailed review:

```bash
git diff HEAD -- src/nimic/[file].py
```

## Step 2 — Detect Ad Hoc Fixes

> [!CAUTION]
> **This is the most critical step.** Ad hoc fixes are the primary anti-pattern this review exists to catch. They pass tests in the short term but create maintenance debt and misalignment as more modules are converted.

For each change in the diff, classify it as one of:

### ✅ Proper Implementation
- Behavior is defined where the data lives (e.g. `high()` defined as a class method on the integer type itself)
- Uses existing extension points (`_n_high`, `_n_low`, `__len__`, class methods)
- Follows the Open/Closed Principle — adds capability without modifying existing code paths
- Is generic — works for any type that satisfies a protocol, not just specific named types

### ❌ Ad Hoc Fix — Flag and Remediate
An ad hoc fix is any change that bypasses proper architecture to make a specific conversion test pass. Common patterns:

#### Pattern 1: Hardcoded Type Names
```python
# BAD — hardcodes specific type names
def high(obj):
    name = getattr(obj, '__name__', '')
    if name in ('int8', 'i8'): return 127
    if name in ('int16', 'i16'): return 32767
    ...
```
**Proper fix**: Each integer class should define its own `_n_high` / `_n_low` class attributes or methods. The `high()` function should only dispatch to these, falling back to a protocol-based default.

#### Pattern 2: isinstance Chains for Known Types
```python
# BAD — couples the function to specific concrete types
def some_builtin(x):
    if isinstance(x, int): ...
    elif isinstance(x, float): ...
    elif isinstance(x, str): ...
```
**Proper fix**: Use `@dispatch` or duck-typing protocols. The class hierarchy should handle polymorphism.

#### Pattern 3: Quick-Fix Dispatch/Registry Patches
```python
# BAD — patching dispatch to work around missing inheritance support
if base_name in _special_inheritance_map:
    _n_registry.register(...)  # ad hoc registration
```
**Proper fix**: Implement proper Nim-style inheritance (via `RootObj` / `of` syntax) in the type system, with `_n_registry` naturally handling subtypes.

#### Pattern 4: Transpiler String Matching Instead of AST Patterns
```python
# BAD — fragile string matching
if "FormatStr" in ann_str or "string" in ann_str:
    func_name = "`%`"
```
**Proper fix**: Use AST node types and the type registry for semantic matching, not string heuristics.

#### Pattern 5: Module-Level Functions That Should Be Methods
```python
# BAD — top-level function hardcoding behavior for specific types
def sizeof(x):
    if x is int: return 8
    if x is float: return 8
```
**Proper fix**: Define `sizeof` as a class-level property or `_n_sizeof` attribute on each type that knows its own size.

#### Pattern 6: Copy-Paste Branches Instead of Generic Logic
```python
# BAD — duplicated logic for Tset, seq, Trange in class definitions
if base_val == "Tset":
    # 10 lines of set-specific handling
elif base_val == "seq":
    # 10 lines of nearly identical seq-specific handling
elif base_val == "Trange":
    # 10 lines of nearly identical range-specific handling
```
**Proper fix**: Extract a common handler parameterized by base type, or use a registry mapping base names to handler functions.

### Detection Checklist

For each change in the diff, answer these questions:

1. **Is it type-name dependent?** Does it check string names of types (`__name__`, `id`) instead of using class hierarchy or protocols?
2. **Is it location-correct?** Is the behavior defined where the data/type lives, or far away from it?
3. **Is it generic?** Would it automatically work for a new type that satisfies the same contract, or does the new type need to be explicitly listed?
4. **Does it modify existing code paths?** Does it change existing working code to accommodate a new case, instead of extending via new code?
5. **Does it duplicate logic?** Is there near-identical code in multiple branches that could be unified?
6. **Does it violate SRP?** Does a single function/class now handle responsibilities that belong elsewhere?

## Step 3 — Review Transpiler Changes

> [!TIP]
> Consult the transpiler header docstring (lines 10–100 of `transpiler.py`) for the existing rule list, and `nimic_translation_rules.md` for the user-facing documentation.

For each transpiler change:

### 3a. Rule Labeling
Every new transpiler behavior must have:
1. A `# rule:<feature>` inline comment before the implementing code
2. A corresponding entry in the header docstring under the appropriate category:
   ```
   rule:<feature> -> short description
   ```

If any new behavior lacks a label, add it following the existing conventions.

### 3b. Structural Quality
Check transpiler changes for:
- **AST-level patterns** preferred over string matching (fragile)
- **Lookup tables/dictionaries** preferred over long if/elif chains
- **No hardcoded type names** — use `self._type_registry`, `self._aliases`, `self._declared_classes` etc.
- **Consistent with existing rules** — a new rule should not contradict or duplicate an existing one
- **Correct precedence** — new operators must have proper precedence entries in `binop_precedence` / `unop_precedence`

### 3c. Translation Rules Sync
Verify that any new transpiler capability is documented in `nimic_translation_rules.md`. If not, draft the missing entry.

## Step 4 — Review Type System Changes

For `ntypesystem.py` changes, check:

1. **Builtin functions** (`high`, `low`, `len`, `sizeof`, `ord`, `chr`, etc.):
   - Must dispatch via class attributes/methods, not hardcoded name checks
   - Preferred protocol: class defines `_n_high`, `_n_low`, `_n_sizeof`; the builtin function just reads the attribute
   - For `NScalar` subclasses, consider whether the implementation belongs on the `NScalar` base class

2. **`@dispatch` / type matching**:
   - Subtype matching must use the class hierarchy, not string comparisons
   - New type registrations should happen at class definition time, not patched in ad hoc
   - `_match_subtype` and `_match_converter` should remain generic — no type-specific special cases

3. **Class definitions** (new types or type modifications):
   - Must follow the existing pattern: `NScalar` → concrete types, `_SomeClass` → singleton instances
   - Inheritance must be properly modeled, not simulated by dispatch patches
   - Each class is responsible for its own properties (SRP)

4. **New exports**:
   - Must be added to `ntypes.py` if user-facing
   - Must follow naming convention: `snake_case` implementation + `camelCase` alias

## Step 5 — Verify Test Coverage

For each change to the core files:

1. Check if there is a corresponding test in `tests/nimic/test_ntypes.py`
2. Run the test suite:
   ```bash
   cd /Users/dima/Documents/Scripts/Ndsl
   .venv/bin/python -m pytest tests/nimic/test_ntypes.py -v
   ```
3. If a change lacks test coverage, **add tests** following the existing patterns in `test_ntypes.py`
4. Verify all 11+ converted compiler modules still work:
   ```bash
   for m in prefixmatches wordrecg idents platform pathutils nimpaths ropes llstream lineinfos options msgs; do
     .venv/bin/python -m ncompiler.$m || echo "FAIL: $m"
   done
   ```

## Step 6 — Remediate Issues

For each ad hoc fix identified in Step 2:

1. **Document** the issue in a review report (see template below)
2. **Propose** the proper generic implementation, following `nimic_add_feature.md`:
   - Draft test cases for the desired behavior
   - Identify the correct location for the implementation (which class/module)
   - Describe the generic approach
3. **Implement** the proper fix:
   - Add tests first
   - Implement the generic solution
   - Remove the ad hoc code
   - Verify all existing tests still pass
4. **If the proper fix is complex** (would require significant type system redesign), create a feature proposal using the `nimic-propose-feature` skill instead of implementing directly. In this case, document a minimal intermediate fix that is at least *correct* (not ad hoc) even if not fully generic.

## Step 7 — Write Review Report

Create `ncompiler/review_core_[date].md` (e.g. `review_core_2026_10_01.md`) with the following structure:

```markdown
# Nimic Core Review — [date]

## Scope
Files reviewed: [list files with non-zero diffs]
Changes triggered by: [which module conversions caused core changes]

## Ad Hoc Fixes Identified

### Issue 1: [title]
- **File**: `src/nimic/[file].py`
- **Location**: Lines X–Y
- **Pattern**: [which ad hoc pattern from Step 2]
- **Problem**: [what is wrong with the current implementation]
- **SOLID violation**: [which principle is violated and why]
- **Proper solution**: [what should be done instead]
- **Status**: Fixed / Proposed / Deferred

## Transpiler Rule Audit

### New Rules
- `rule:<name>` — [description] — ✅ Labeled / ❌ Missing label
- ...

### Translation Rules Sync
- [list any undocumented rules]

## Type System Audit
- [findings about class hierarchy, dispatch, builtins]

## Test Results
- `test_ntypes.py`: X/Y passed
- Module verification: all N modules pass / [list failures]

## Changes Made
- [list all changes this review introduced, with motivation]
```

## SOLID Principles Quick Reference

Apply these when evaluating whether a change is properly structured:

| Principle | Application to Nimic Core |
|-----------|--------------------------|
| **S — Single Responsibility** | Each type class defines its own properties (`_n_high`, `_n_low`, `_n_sizeof`). Builtin functions only dispatch, they don't hardcode type knowledge. |
| **O — Open/Closed** | Adding a new integer type should NOT require modifying `high()`, `low()`, or `sizeof()`. The type class itself provides the values. |
| **L — Liskov Substitution** | A subtype must be usable wherever its parent is expected. If `int32` subclasses `NScalar`, it must satisfy the `NScalar` contract. |
| **I — Interface Segregation** | Don't force types to implement interfaces they don't need. Not every type needs `_n_high` — only ordinal/integer types do. |
| **D — Dependency Inversion** | Builtin functions depend on abstractions (protocols like `_n_high`), not on concrete types (`int8`, `int16`, etc.). |
## Adding a Feature to Nimic Core

A new feature introduced — for example during Nim-to-nimic translation — should be added according to the following steps:

### Step A — Tests First

Add a few tests for the desired behaviour in `tests/nimic/test_ntypes.py` **before** implementing the feature. Tests use `unittest.TestCase` and live inside the `TestNTypes` class. Run with:

```bash
cd /Users/dima/Documents/Scripts/Ndsl
.venv/bin/python -m tests.nimic.test_ntypes
```

### Step B — Implement in the Correct Location

Implement the feature in the appropriate core file:

| Feature kind | Target file |
|-------------|-------------|
| Type, dispatch, builtins (`high`, `low`, `len`, etc.), class definitions | `src/nimic/ntypesystem.py` |
| Public re-exports, user-facing aliases, convenience functions | `src/nimic/ntypes.py` |
| System primitives (`cast`, memory, `ord`, `quit`, `hostOS`) | `src/nimic/nsystem.py` |
| Transpiler rules (AST transform, code generation) | `src/nimic/transpiler.py` |

Verify all tests pass after implementation.

### Step C — Document in Translation Rules

If the feature is exposed to the user of the nimic DSL, update `nimic_translation_rules.md` with a new entry in the corresponding section table.

### Example 1: Adding `test_keyword_dispatch`

1. **Tests**: `test_keyword_dispatch` added to `tests/nimic/test_ntypes.py` — tests positional + named args, out-of-order named args, and bad kwarg errors.
2. **Implementation**: dispatch logic extended in the `fn_dispatch` subfunction of `src/nimic/ntypesystem.py` to handle non-empty `kwargs` by matching argument names to signature parameters and reordering.
3. **Rule**: entry added to `nimic_translation_rules.md` table in the *Functions and Arguments* section.

### Example 2: Remediating `high()` / `low()` (core review 2026-10-01)

1. **Tests**: `test_high_low_signed_integers`, `test_high_low_unsigned_integers`, `test_high_low_enum`, `test_high_low_on_seq`, `test_high_low_on_array` added to `tests/nimic/test_ntypes.py` — covering all integer types, enums, and collections.
2. **Implementation**: dead hardcoded type-name branches removed from `high()` and `low()` in `src/nimic/ntypesystem.py`. The functions now dispatch purely via the `first()`/`last()` classmethods (defined on `NInteger`) and the `_n_high`/`_n_low` protocol (defined on `Trange`), following the Open/Closed and Dependency Inversion principles.
3. **Rule**: not applicable — `high`/`low` are existing builtins, no new user-facing syntax.

### Anti-Pattern: Skipping Tests

> [!CAUTION]
> Never implement a feature directly in core without tests. Ad hoc fixes that "just make the module run" are the primary failure mode this review exists to catch. If a conversion agent adds core changes without corresponding tests, this review must flag them and add tests retroactively.

## Reference Files

- Feature addition protocol: `nimic_add_feature.md` (project root)
- Translation rules: `nimic_translation_rules.md` (project root)
- Conversion approach: `nimic_convertion_approach.md` (project root)
- Transpiler rules header: `src/nimic/transpiler.py` (lines 10–100)
- Type system: `src/nimic/ntypesystem.py`
- Public API: `src/nimic/ntypes.py`
- System primitives: `src/nimic/nsystem.py`
- Test suite: `tests/nimic/test_ntypes.py`
- Example nimic project: `tests/nraytracer/`
- Existing reviews: `ncompiler/review_*.md`
- Feature proposals: `ncompiler/proposals/`
