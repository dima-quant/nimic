---
name: nimic-propose-feature
description: >-
  Create a markdown proposal for a new Nimic feature needed during translation.
  Use when a Nim construct cannot be expressed with current Nimic capabilities.
---

# Nimic Feature Proposal Skill

When a Nim construct is encountered during conversion that cannot be expressed with the current Nimic DSL, transpiler, or type system, create a structured proposal for user review. **Do NOT implement the feature** until the user approves the proposal.

## When to Use

- A Nim language construct has no mapping in `nimic_translation_rules.md`
- A required type is missing from `src/nimic/ntypesystem.py`
- The transpiler (`src/nimic/transpiler.py`) lacks a rule for a needed pattern
- A `nimic.std` module needs a function/type not yet implemented (note: basic `std` stubs can be created proactively without a proposal — this is for non-trivial additions)

## Step 1 — Create Proposal File

Create `ncompiler/proposals/feature_[name].md` where `[name]` is a short descriptive identifier (e.g., `feature_generic_procs.md`, `feature_openarray_type.md`).

## Step 2 — Document the Problem

```markdown
# Feature Proposal: [descriptive name]

## Context
- **Encountered during conversion of**: `compiler/[filename].nim`
- **Nim source line(s)**: [line numbers and code]

## Problem
[Describe the Nim construct that cannot be expressed in current Nimic]

## Nim Code
```nim
[The original Nim code that needs to be translated]
`` `

## Desired Nimic Python
```python
[The Python expression you would like to write]
`` `

## Expected Transpiled Nim Output
```nim
[What the transpiler should produce from the Python above]
`` `
```

## Step 3 — Propose Implementation

Following the protocol in `nimic_add_feature.md`:

### 3a. Test Cases
Draft test cases that should be added to `tests/nimic/test_ntypes.py`:
```python
def test_[feature_name]():
    # Test the desired behavior
    ...
```

### 3b. Implementation Location
Identify where the change goes:
- **Type system** (`src/nimic/ntypesystem.py`): for new types, operators, or runtime behavior
- **Transpiler** (`src/nimic/transpiler.py`): for new syntax transformation rules
- **Std library** (`src/nimic/std/[module].py`): for standard library additions
- **Other** (`src/nimic/[file].py`): specify which file

### 3c. Translation Rule
If this is a user-facing DSL feature, draft the row for `nimic_translation_rules.md`:

| Nim | Python (Nimic) | Notes |
|-----|-----------------|-------|
| `[Nim syntax]` | `[Nimic Python syntax]` | [explanation] |

### 3d. Impact Assessment
- Which already-converted files (if any) would need updating?
- Does this change any existing transpiler behavior?
- Are there alternative approaches? List pros/cons of each.

## Step 4 — Stop and Request User Review

After writing the proposal:
1. **Do NOT implement the feature.**
2. Notify the user that a proposal has been created at `ncompiler/proposals/feature_[name].md`.
3. Summarize the proposal in 2–3 sentences.
4. Wait for the user to approve, reject, or request modifications.

## After User Approval

Once approved, implementation follows `nimic_add_feature.md`:
1. Add tests to `tests/nimic/test_ntypes.py`
2. Implement in the identified location (`ntypesystem.py`, `transpiler.py`, etc.)
3. Verify tests pass: `python -m pytest tests/nimic/test_ntypes.py`
4. Update `nimic_translation_rules.md` if applicable
5. Return to the conversion that triggered this proposal and complete it

## Reference Files

- Feature addition protocol: `nimic_add_feature.md` (project root)
- Translation rules: `nimic_translation_rules.md` (project root)
- Type system: `src/nimic/ntypesystem.py`
- Transpiler: `src/nimic/transpiler.py`
- Existing tests: `tests/nimic/test_ntypes.py`
