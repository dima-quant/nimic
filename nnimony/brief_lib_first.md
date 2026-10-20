# Agent Brief — first nimony modules: `lib/stringtrees`, `lib/comesfrom`, `lib/symparser`

The first agent conversions of nimony (Nim 3) sources: three small modules of nimony's `src/lib` that
import only the standard library and use no construct nimic is known to lack. The goal is a line-for-line
conversion **without any change to nimic itself**. A clean result with recorded gaps is a success; a
passing result reached through workarounds is not.

Read first:
- `ncompiler/conversion_plan.md`: why nimony, the layout, the pins;
- `nnimony/conversion_queue.md`: the queue;
- `nimic_translation_rules_nimony.md` in full: the nimic language (§0–§12, starting with §0, the unity
  principle), the conventions of nimony modules (§13) and the Nim 3 constructs (§14).

## Sources

| # | Module | Source | Size |
|---|---|---|---|
| 1 | `lib/stringtrees` | `../nimony/src/lib/stringtrees.nim` | 104 lines |
| 2 | `lib/comesfrom` | `../nimony/src/lib/comesfrom.nim` | 126 lines |
| 3 | `lib/symparser` | `../nimony/src/lib/symparser.nim` | 265 lines (has its own `when isMainModule` tests) |

- **The nimony clone** is next to the project, at commit `3f56467ab15a46746c4f2b33a904809a2ffa0a12`.
  Don't change its checkout; read files with `git -C ../nimony show HEAD:src/lib/<m>.nim` or directly.
- **Order:** convert one module, verify it, report, then the next.
- **Worked example:** `nnimony/lib/tinyhashes.py`, converted by the reviewer.

## Procedure

Follow the `nimic-convert` skill (`.agents/skills/nimic-convert/SKILL.md`) with these overrides:

1. **Files you may create:** `nnimony/lib/<module>.py` only. Scratch files go in `.scratch/`.
2. **Files you must not edit:**
   - everything in `src/nimic/` (core and `std/`), `tests/`, `ncompiler/`, other `nnimony/` files;
   - the translation rules (`nimic_translation_rules_*.md`), `CLAUDE.md`, the skills;
   - the nimony clone.

   If something is missing in nimic, that is a gap, not something to add.
3. **Never** `git add`, `git commit` or `git push`.
4. **Do not trigger the review skill**; the reviewer reviews your result.

## Conventions for nimony modules

- **Header:** the module records its source, exactly like the example:

  ```python
  # /// nimic
  # source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/<module>.nim
  # ///
  ```

  It is followed by the original header comments, then `from __future__ import annotations` and
  `from nimic.ntypes import *`.
- **Imports keep nimony's paths:**
  - `import std/assertions` → `from nimic.std.assertions import *`;
  - a sibling `import x` → `from .x import *`;
  - `import ".." / models / [tags]` → `from ..models.tags import *`.
- **`when defined(nimony)` / `when not defined(nimony)`:** convert like any `when`, i.e. `if comptime(...)`
  with every branch, the inactive ones included. Python runs the host-Nim (Nim 2) build, where
  `defined("nimony")` is false.
- **Private names** (no `*`) are `_name`. Custom operators get letter names. In tinyhashes, `` `!&` `` is
  `_mix_hash`, with a `# Nim: proc `!&`(...)` comment.
- **Line for line, methods rule, case/match, copies, no Python idioms:** as in the rules, and as in the
  committed brief `ncompiler/brief_condsyms_nimlexbase.md` (section *Fidelity rules*).

## When nimic can't express something

Stop working around it. Instead:

1. Write the closest faithful code and mark it `# TODO: requires nimic feature <name>`.
2. Describe the gap in your report: the Nim construct, what you tried, and the error.
3. Continue with the rest of the module.

Do **not** add a Python-only branch, a stand-in in the module, a renamed proc, or a different algorithm.

**Known gaps:** the reviewer is working on standalone pragma statements (`{.pragma: x.}`,
`{.feature: ...}`), custom pragmas (`template x() {.pragma.}`) and `static:` blocks. These three modules
shouldn't need them. If one does, record it as a gap.

## Tests

Add `if comptime(__name__ == "__main__"):` tests at the end (valid nimic: `doAssert`, `echo`). Print the
results with `echo`. The verification compiles the **original** nimony module with your test block
appended and compares its output with Python's, so the printed lines are what is checked.

- **`stringtrees`:** `createSearchTree` on a few key sets (one key, keys sharing prefixes, keys differing
  only at the end). Echo the resulting nodes.
- **`comesfrom`:** build forged file names with the module's constructor and take them apart again
  (`isCrucialFile`, `crucialTail`, `realFile` and the declaration fields), including plain file names.
- **`symparser`:** convert the module's own `when isMainModule` tests as they are, and add cases for the
  edges you see in the code (empty and malformed symbols, if the module handles them).

Use only the module's public procs, and print values in a form both languages print alike: strings,
integers, enum names (`$`). Avoid floats in output unless the module computes them.

## Done when

```bash
.venv/bin/python -m nnimony.lib.<module>                  # Python tests pass
.venv/bin/python tests/verify_transpiled.py nimony        # module / tests / original: PASS for your module
```

All three lines must report PASS for your module:
- `nimony module`: `nim check` of the transpiled module;
- `nimony tests`: Python vs the compiled transpiled module;
- `nimony original`: Python vs the original nimony module with your tests.

`lib/tinyhashes` must stay PASS. Also run `.venv/bin/python -m nnimony.tools.queue` to update the queue.

## Report

For each module:
- the verification lines;
- every `TODO: requires nimic feature` with its gap description;
- every place where you were unsure the conversion is faithful.
