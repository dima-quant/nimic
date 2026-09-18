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
```

See existing reviews for reference: `ncompiler/review_wordrecg.md`, `ncompiler/review_idents.md`, `ncompiler/review_pathutils.md`, `ncompiler/review_nodejs.md`.

## Step 2 — Line-by-Line Verification

Compare `compiler/[filename].nim` against `ncompiler/[filename].py` **line by line**, verifying:

1. **Direct correspondence**: Every Nim construct has a matching Nimic Python expression such that the transpiler can restore equivalent Nim code.
2. **Translation rules compliance**: All mappings follow `nimic_translation_rules.md`. Check especially:
   - No Python builtins used where `nimic.std` equivalents exist
   - No Python idioms replacing Nim loops (no list comprehensions, no `enumerate` replacing `mitems`, etc.)
   - Correct use of `Tset` vs `set`, `nint` vs `int`, `string` vs `str`
   - Export markers: public Nim identifiers (with `*`) must NOT have `_` prefix; private ones MUST have `_` prefix
   - No extra module qualification beyond what the original Nim uses
   - `result` variable pattern: no redundant `result = Type()` before immediate assignment
   - Correct `with var:`/`with let:`/`with const:` usage
   - Correct operator mappings (`and`→`&`, `or`→`|`, `shr`→`>>`, etc.)
   - Correct pointer/memory primitives (`ptr[T]`, `p.contents`, `addr(x)`)
3. **Completeness**: No Nim code was accidentally skipped or summarized.

**Log all observations to the review file.** Do NOT make corrections during this step — only log.

Perform the verification of the **entire file** from start to finish. Do not stop partway through.

## Step 3 — Test Coverage Review

1. Check `compiler/dep_tree.md` for modules that import `[filename]` (listed in square brackets).
2. Examine how those downstream modules typically use the functionality.
3. Review the test cases after `if comptime(__name__ == "__main__"):`:
   - Do they cover the most important functions and types?
   - Do they test non-trivial logic (edge cases, boundary conditions)?
   - Are there critical APIs used by downstream modules that lack tests?
4. If test coverage is insufficient, **add new test cases**.
5. Run all tests:
   ```bash
   cd /Users/dima/Documents/Scripts/Ndsl
   python -c "from ncompiler import [filename]"
   ```
6. Log test results (pass/fail) in the review file. If tests fail, log the failure details but **do not attempt to fix them yet**.

## Step 4 — Resolve Issues

If issues were found in Steps 2–3:

1. Start fixing them one by one, following `nimic_convertion_approach.md` and `nimic_translation_rules.md`.
2. After each fix, write progress in the review file.
3. For complex issues with no obvious fix:
   - Present 2–3 possible approaches with pros and cons of each.
   - If a fix doesn't work, **revert it** and document what was tried and why it failed.
4. If a fix requires a Nimic feature that doesn't exist yet, create a proposal using the `nimic-propose-feature` skill.

If no issues were found, write "No issues found" in the review file.

## Reference Files

- Translation rules: `nimic_translation_rules.md` (project root)
- Conversion approach: `nimic_convertion_approach.md` (project root)
- Feature addition protocol: `nimic_add_feature.md` (project root)
- Dependency order: `compiler/dep.md`
- Downstream consumers: `compiler/dep_tree.md`
- Example nimic project: `tests/nraytracer/`
- Existing reviews: `ncompiler/review_*.md`
