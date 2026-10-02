---
name: nimic-review
description: >-
  Independently review a Nim-to-Nimic Python conversion for correctness.
  Use when asked to review a converted module, or when automatically triggered after conversion.
---

# Nimic Review Skill

Independently verify the correctness of a converted `ncompiler/[filename].py` against its original `compiler/[filename].nim`. This review must be performed by a different agent than the one that did the conversion.

## Step 1 — Create Review Log

Create `ncompiler/review_[filename].md` to store all findings. Use this structure:

```markdown
# Review of [filename].nim → [filename].py conversion

## Step 2: Line-by-line review

### Imports (lines X–Y)
...

### Issue N: [description]
**Nim (line X):** ...
**Python (line Y):** ...
**Observation:** ...
**Severity:** High/Medium/Low

## Step 3: Test coverage review
...

## Step 4: Issue resolution
...

## Step 5: Nim execution verification
...

## Step 6: Core engine changes audit
...
```

See existing reviews for reference: `ncompiler/review_wordrecg.md`, `ncompiler/review_idents.md`, `ncompiler/review_pathutils.md`, `ncompiler/review_nodejs.md`.

## Step 2 — Line-by-Line Verification

Compare `compiler/[filename].nim` against `ncompiler/[filename].py` **line by line**, verifying:

> [!TIP]
> **When verifying syntax**, use these two authoritative references:
> 1. **`nimic_translation_rules.md`** (project root) — the definitive mapping for every Nim → Nimic construct.
> 2. **`tests/nraytracer/`** — a working Nimic project with 30+ modules showing correct patterns for `mut @ T`, `@dispatch`, `Tset`, `seq`, `array`, `Object`, `NIntEnum`, `ref[T]`, `ptr[T]`, iterators, templates, etc.
>
> If the converted code uses syntax not found in either resource, flag it as a potential issue.

1. **Direct correspondence**: Every Nim construct has a matching Nimic Python expression such that the transpiler can restore equivalent Nim code.
2. **Translation rules compliance**: All mappings follow `nimic_translation_rules.md`. Check especially:
   - No Python builtins used where `nimic.std` equivalents exist
   - No Python idioms replacing Nim loops (no list comprehensions, no `enumerate` replacing `mitems`, etc.)
   - Correct use of `Tset` vs `set`, `nint` vs `int` (verify that Python's built-in `int` is never shadowed, and `nint` is used for Nim's `int` in type annotations, fields, parameters, return types, and explicit casts; int literals like `0`, `1` are allowed), `string` vs `str`
   - Export markers: public Nim identifiers (with `*`) must NOT have `_` prefix; private ones MUST have `_` prefix
   - No extra module qualification beyond what the original Nim uses
   - `result` variable pattern: no redundant `result = Type()` before immediate assignment
   - Correct `with var:`/`with let:`/`with const:` usage
   - Correct operator mappings (`and`→`&`, `or`→`|`, `shr`→`>>`, etc.)
   - Correct pointer/memory primitives (`ptr[T]`, `p.contents`, `addr(x)`)
3. **Completeness**: No Nim code was accidentally skipped or summarized.
4. **No Python-mode-only code**: All code, including tests, must be valid Nimic that compiles and runs in Nim after transpiling. Flag any of these violations:
   - `f-string` formatting (must use `string("...") % [args]`)
   - Python `with open(...) as f:` (must use `open(f, path, mode)`)
   - Python `list` instead of `seq` for typed sequences
   - Python `isinstance()` where Nim uses type dispatch
   - Chained comparisons like `0 <= x <= 10` (must use `x >= 0 and x <= 10`)
   - Python `unittest` / `pytest` / `assert` with f-strings in tests
   - Any construct that would not survive transpilation to valid Nim

**Log all observations to the review file.** Do NOT make corrections during this step — only log.

Perform the verification of the **entire file** from start to finish. Do not stop partway through.

## Step 3 — Test Coverage Review

1. Check `compiler/dep_tree.md` for modules that import `[filename]` (listed in square brackets).
2. Examine how those downstream modules typically use the functionality.
3. Review the test cases after `if comptime(__name__ == "__main__"):`:
   - Do they cover the most important functions and types?
   - Do they test non-trivial logic (edge cases, boundary conditions)?
   - Are there critical APIs used by downstream modules that lack tests?
   - **Are all tests written in valid Nimic** (using `doAssert`, `echo`, `string()` — no Python-only constructs)?
4. If test coverage is insufficient, **add new test cases** — written in valid Nimic.
5. Run all tests in Python mode:
   ```bash
   cd /Users/dima/Documents/Scripts/Ndsl
   .venv/bin/python -m ncompiler.[filename]
   ```
6. Log test results (pass/fail) in the review file. If tests fail, log the failure details but **do not attempt to fix them yet**.

## Step 4 — Resolve Issues

If issues were found in Steps 2–3:

1. Start fixing them one by one, following `nimic_convertion_approach.md` and `nimic_translation_rules.md`. When unsure about correct Nimic syntax for a fix, check `tests/nraytracer/` for working examples.
2. After each fix, write progress in the review file.
3. For complex issues with no obvious fix:
   - Present 2–3 possible approaches with pros and cons of each.
   - If a fix doesn't work, **revert it** and document what was tried and why it failed.
4. If a fix requires a Nimic feature that doesn't exist yet, create a proposal using the `nimic-propose-feature` skill.

If no issues were found, write "No issues found" in the review file.

## Step 5 — Nim Execution Verification

> [!IMPORTANT]
> After all issues are resolved, the converted module **must** be transpiled and executed in native Nim.

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

3. **Compare output**: The Nim execution output must match the Python-mode test output.

4. **Log results** in the review file under "Step 5: Nim execution verification":
   - Python test output
   - Nim compilation status (success / errors)
   - Nim execution output
   - Any discrepancies

If Nim compilation or execution fails:
- Debug and fix the Nimic source (not the transpiler unless absolutely necessary).
- Common issues: missing export `*`, chained comparisons, Python-only constructs, scope depth problems.
- Re-run both Python and Nim after each fix.
- Document all fixes in the review file.

**The review is not complete until both Python and Nim execution pass with matching output.**

## Step 6 — Core Engine Changes Summary

> [!IMPORTANT]
> After finalizing all fixes, check whether any changes were introduced to the nimic core scripts during this conversion/review cycle.

```bash
cd /Users/dima/Documents/Scripts/Ndsl
git diff --stat HEAD -- src/nimic/ntypes.py src/nimic/ntypesystem.py src/nimic/nsystem.py src/nimic/transpiler.py
```

If changes exist:

1. **Log a summary** in the review file under "Step 6: Core engine changes". For each modified file, document: what changed, why it was needed, and a brief code example.

2. **Verify std module naming**: Any new functions added to `src/nimic/std/*.py` must use **`snake_case`** with a **`camelCase` alias** (e.g., `toOctal = to_octal`).

3. **Flag for core review**: Note in the review file that a `nimic-core-review` should be triggered to audit these changes for proper structure, SOLID compliance, and ad hoc fix detection.

If no core changes were made, write "No core engine changes" in this section.

## Reference Files

- Translation rules: `nimic_translation_rules.md` (project root)
- Conversion approach: `nimic_convertion_approach.md` (project root)
- Feature addition protocol: `nimic_add_feature.md` (project root)
- Dependency order: `compiler/dep.md`
- Downstream consumers: `compiler/dep_tree.md`
- Example nimic project: `tests/nraytracer/`
- Existing reviews: `ncompiler/review_*.md`
- Nimic core scripts: `src/nimic/ntypes.py`, `src/nimic/ntypesystem.py`, `src/nimic/nsystem.py`, `src/nimic/transpiler.py`
- Core review skill: `.agents/skills/nimic-core-review/SKILL.md`

