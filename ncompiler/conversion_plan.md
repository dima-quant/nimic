# Conversion Plan: nimony (Nim 3) in nimic

The translation rules:
- `nimic_translation_rules_nimony.md`: this conversion, complete; the nimic language evolves here;
- `nimic_translation_rules_nim2.md`: the frozen Nim 2 one.

The queues are generated:
- `nnimony/conversion_queue.md`: current work;
- `ncompiler/conversion_queue.md`: the frozen Nim 2 corpus.

This document explains the plan. It was re-planned on 2026-10-20 (it first targeted the Nim 2 compiler;
see *History*).

## Goals

1. **A mature nimic** (foremost). Converting real Nim code is how nimic finds out what it is missing.
2. **A Nim compiler in Python** that compiles to C, and possibly to LLVM, as numba does.
3. **Nim 3**, with its improvements (such as the borrow checker), without rewriting the project later.

## Decision: nimony is the main project

- **nimony is Nim 3.**
  - It compiles itself: `hastur boot` is a multi-stage self-host of nimony, nimsem, shoggoth and lengc.
  - It has C, native x86-64 and JS/wasm backends.
  - Its sources are written to compile with Nim 2 as well (`src/lib/compat2.nim`), so nimic's current
    Nim 2 output can carry them now.
- **The Nim 2 front end is being retired.** nifler2 (designed 2026-09-12) replaces nifler, specifically to
  drop the toolchain's dependency on Nim 2's `compiler/parser.nim`. Nim 2's AST (PNode, PSym, PType object
  variants) has no future in Nim 3, which works on NIF token buffers.
- **Consequence:** nimony's sources become the main driver of nimic core work. The converted Nim 2
  modules (`ncompiler/`, 37 modules: infrastructure, the lexer, C-builder includes) are **frozen as test
  corpus**: they stay green in verification, but are not extended.

## Sources and pins

| Source | Commit | Use |
|---|---|---|
| nimony (github.com/nim-lang/nimony) | `3f56467ab15a46746c4f2b33a904809a2ffa0a12` (master, 2026-10-20) | converted into `nnimony/`; pin in `nnimony/tools/queue.py` |
| Nim compiler (`compiler/`) | `f0c60b06e5cff8064bf0a9a32ec2d2bc14a694d9` (devel, 2026-05-09) | the frozen corpus `ncompiler/` |
| checksums (github.com/nim-lang/checksums) | `0b8e46379c5bc1bf73d8b3011908389c60fb9b98` (2.0.1) | `ChecksumsStableCommit` of that compiler's `koch.nim` |

**Layout.**
- nimony and checksums are cloned next to the project (`../nimony`, `../checksums`). The project's own
  `dist/` is nimic's wheel output.
- `tests/verify_transpiled.py` links the clones into its scratch area as `dist/<name>`, where `compiler/`
  expects them (`../dist/...`).
- With them, the Nim 2 originals of typekeys, gorgeimpl, nimblecmd, modulegraphs and deps type-check
  (checked 2026-10-20).

**Re-pinning nimony.**
- nimony moves fast: 603 commits in the 5.5 months before this pin, and `src/lib` more than doubled.
- So every converted module records its source commit from the start:
  `# source: nimony@<sha>:src/lib/bitabs.nim`.
- A re-pin is applied as upstream diffs to the converted modules, done by `nnimony/tools/upstream.py` (to
  come; needed from the first re-pin on).
- Re-pin deliberately, e.g. when a component is complete.

## Layout of the conversion

- `nnimony/` mirrors nimony's `src/`. `src/lib/bitabs.nim` becomes `nnimony/lib/bitabs.py`, and
  `src/models/tags.nim` becomes `nnimony/models/tags.py`.
- Imports keep their paths: `import bitabs` becomes `from .bitabs import *`, and
  `import ".." / lib / [vfs]` becomes `from ..lib.vfs import *`.
- Converted code transpiles back to the same paths.

## Phases (nimony components)

| Phase | Component | Lines (at the pin) | Notes |
|---|---|---|---|
| **A, current** | `src/lib` (+ the `src/models` it needs) | 12k (+ models) | NIF data structures, reader/builder, streams, cursors. Many small modules import only the standard library: the first agent tasks |
| B | `src/nifler2` | 7k | the parser, generated from a grammar; a nimony program (uses Nim 3 features) |
| C | `src/lengc` | 23k | the C backend. The milestone: C from the Python lengc is byte-identical to lengc's |
| D | `src/hexer` | 24k | lowering (shoggoth) |
| E | `src/nimony` | 50k | semantic checking (nimsem) and the driver: nimony in Python |
| F | the raytracer and nimic itself | | the raytracer compiles with nimony; nimic drops Nim 2-only features |

**Milestones.**
- **Phase A:** converted modules round-trip NIF files identically in Python and compiled Nim. For example,
  read a `.nif` file with nifreader and write it back with nifbuilder.
- **Every phase:** a module's tests produce the same output in Python, in the transpiled module, and in the
  original nimony module compiled with the same test code. This is the check done for the lexer.

## nimic alignment with Nim 3

nimony's own code is the target: the subset of the language that compiles with both Nim 2 and nimony.
Alignment follows the conversions, item by item, when a module needs it. Until Phase F nothing Nim 2-only
is added to the core.

| Nim 3 change | Effect on nimic | Effort |
|---|---|---|
| Case-sensitive identifiers | Python and converted code are case-sensitive already. The transpiler's snake_case names for Nim std procs (`set_len`, `is_nil`) rely on Nim 2's style insensitivity: emit `{.feature: "ignoreStyle".}`, or the exact names | S–M |
| Strings: no terminating `'\0'`, no conversion to `cstring` without a copy | nimic's cstring as a view of a string's buffer and `s[len] == '\0'` are Nim 2 semantics: a per-target string model | M |
| Refs not nil by default (`nil ref T` explicit) | a nilable marker for `@ref` types, fields and parameters, emitted as `nil ref T` | M |
| Exceptions: `ErrorCode` values, `raise IOError`, `except IOError:` without `as e`, non-raising by default (`{.raises.}`) | nimic's exception model follows | L |
| New `case`-object syntax | the transpiler's variant output | S–M |
| No implicit generics, type-checked generics with concepts | emit explicit `[T: ...]` | S–M |
| Macros replaced by compiler plugins | G17 retargeted to the plugin API | L, later |
| `var T` overloading gone, `break` leaves loops only, side-effect defaults, no closure iterators | small transpiler adjustments | S |
| nimony's standard library (`lib/std`, 64k lines) | std shims for Nim 3 where it differs, as modules need them | M–L |
| Verification | a `nimony c` check in `verify_transpiled` (build nimony with hastur next to the project) | S–M |

## Core roadmap, in order of need

1. **What Phase A needs:**
   - nimony module paths under `nnimony/`;
   - verification of `nnimony` modules (transpile into a copy of nimony's `src/`, `nim check`, Python vs
     compiled Nim);
   - the missing std shims (memfiles, atomics, parseopt, varints, posix);
   - and whatever the modules reveal.
2. **The upstream tool,** before the first re-pin.
3. **The `nimony c` check,** and the Nim 3 alignment items in the order the modules hit them.
4. **Runtime speed.** Python mode is about 9,000 times slower than compiled Nim (`ncompiler/review_lexer.md`).
5. **G17 as compiler plugins**, later.

## Idea for later: a nimic backend for nimony

A nimony backend, written in Nim, that writes nimic Python from Nim code: the reverse of the transpiler.

- **Uses.**
  - A round-trip test of the nimic rules: nimic → Nim → nimic over the converted corpus (`ncompiler/`,
    `nnimony/`, `tests/nimic`, the raytracer) must give back the source in a canonical form; every
    difference is an ambiguous, lossy or undocumented rule.
  - Mechanical conversion of nimony (and the pure-Nim std modules), with agents filling only the gaps it
    reports: none of the agent mistakes the reviews find (dropped comments, workarounds in modules,
    public private names, renames).
  - Plugins (the Nim 3 macros): nimic → Nim → NIF → plugin (in nimic, on the converted nifcore /
    nifreader) → NIF → nimic run by Python, cached by an import hook. Only modules that use plugins pay
    for it (a nimony binary and a build step).
- **What it needs first.**
  - A one-to-one mapping: today `.copy()` (dropped by `rule:copy`), the methods rule, `@dispatch`,
    `@template_expand`, `mut @`, `cell()` and `nint` vs sized integers carry what Nim leaves to sema, so
    the backend needs types and scopes (the parsed tree for structure plus sema's side tables), and
    free choices (`x.f(1)` vs `f(x, 1)`, `with let:` grouping) need a canonical form.
  - Comments: plain `#` comments are probably lost by the parser; merge them back from the source by
    line info (the NIF `#…#` decoration may help).
  - The std: convert only pure-Nim algorithmic modules; keep the Python shims at the system boundary
    (faster, and system code can't run in Python).
- **When.** Not during Phase A: the `src/lib` batches still change the rules (batch 6 found 15 core gaps),
  and a backend built now would freeze today's quirks. Revisit before Phase B / C, where the line counts
  (7k–50k per component) make a mechanical conversion pay.

## History

- **2026-10-19: first plan.** It targeted the Nim 2 compiler (`compiler/`), front end first, then nimony's
  NIF libraries.
- **What it produced:**
  - 37 converted modules (infrastructure, int128, the C builders, the lexer, condsyms, nimlexbase);
  - most of today's core features;
  - the build profile `nimKochBootstrap`.
- **What changed it:** nimony's nifler2 retires the Nim 2 parser, and nimony self-hosts. The work moved to
  nimony on 2026-10-20.
