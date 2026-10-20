# Conversion Plan: the Nim compiler in nimic, toward Nim 3 (nimony)

The queue (`conversion_queue.md`, generated) shows what to convert next. This document explains why.
Agreed 2026-10-19; the phases are tracked in `ncompiler/tools/dependencies.py` (`PHASE`, `BLOCKED`,
`DEFERRED`).

## Goals

1. **A mature nimic** (foremost). Converting real Nim code is how nimic finds out what it is missing.
2. **A Nim compiler in Python** that compiles to C, and possibly to LLVM, as numba does.
3. **Nim 3 (nimony) improvements**, such as the borrow checker, adopted without rewriting the project.

## Where the effort goes

- **The core comes first, for now.** A module is chosen when it survives into Nim 3 and exercises Nim
  features nimic lacks.
- **The balance tips as the core matures.** Small modules already convert without core changes (condsyms,
  nimlexbase by an agent). The large front-end modules still need core work (lexer: about 15 core features).
- **Indicator:** the share of conversions that need no core change. When most don't, conversion becomes
  the main effort, mostly done by agents.

## NIF as the pivot

Nim 3 is organised around NIF, a text format for the AST:
- **nifler:** parses Nim to NIF, with Nim 2's own parser;
- **nimony:** semantic checking on NIF;
- **hexer:** lowering;
- **nifc:** NIF to C.

So the parts of `compiler/` have different futures:

| Layer | Nim 3 fate | Decision |
|---|---|---|
| Infrastructure (options, msgs, lineinfos, pathutils, idents, ...) | partly kept | converted |
| Front end: lexer, astdef, ast, trees, astyaml, astalgo, parser, renderer, filters, filter_tmpl, syntaxes | **kept**: nifler uses Nim 2's parser | **Phase 1, now** |
| NIF libraries in nimony (`src/lib`: bitabs, nifstreams, nifreader, nifbuilder, ...) and nifler | the interface, fairly stable | Phase 2, pinned |
| nifc (NIF → C) | Nim 3's C backend | Phase 3, pinned |
| Nim 2 sem\*, transf and the other transforms, vm\* | replaced by nimony's sem and hexer | **deferred** (Phase 4: nimony's sem) |
| Nim 2 C backend (cgen, ccg\*, cbuilder\*) | replaced by nifc | **deferred**; the converted parts stay as test corpus |
| Nim 2 JS backend, driver, tools | replaced or not targeted | **deferred** |

The build is koch's bootstrap build (`define:nimKochBootstrap` in `ncompiler/nim.cfg`). It leaves out
ast2nif, nifgen, nifbackend and deps. Even so, typekeys (needed by modulegraphs) uses nimony's
`treemangler`/`modnames`, and a few modules use the `checksums` package.

## Phases

### Phase 1 — front end (current)
- **Order:** astdef → ast → trees, astyaml → astalgo → parser → renderer → filters, filter_tmpl → syntaxes.
  The lexer is done.
- **Milestone:** parser and renderer, run in Python, round-trip `compiler/*.nim` with the same output as
  the Nim build. Lex/parse time is measured.
- **Core gaps to expect:**
  - setter procs (`` `typ=` ``, `` `flags=` ``);
  - `[]`/`[]=` templates;
  - large object variants (PNode, PSym, PType);
  - **runtime speed:** Python lexing is about 9,000 times slower than compiled Nim
    (`review_lexer.md`).
- **Agents:** small modules that need no new core features (`debugutils`, brief ready).

### Phase 2 — NIF libraries and nifler (pinned nimony)
- **Fetch nimony at a pinned commit** into `dist/nimony`. This downloads code, so it needs the user's
  approval. Record the commit.
- **Imports from `dist/`:** add a core spelling for `../dist/...` imports (e.g. `from nimic.dist.nimony.lib.nifstreams
  import *`, with a transpiler path mapping), plus shims or conversions for `checksums` (md5, sha1). This unblocks
  gorgeimpl, nimblecmd, typekeys and modulegraphs.
- **Convert** nimony's `lib/` modules, then nifler.
- **Milestone:** NIF from the Python nifler is byte-identical to nimony's nifler at the pin.

### Phase 3 — backends
- **C:** nifc at the pin.
- **LLVM:** the LLVM C API through `@importc`. llvmlite is Python-only and would break the unity principle;
  `@importc` calls the C API through ctypes in Python and is a C import in Nim.
- **Milestone:** C from the Python nifc is byte-identical to nifc's, and the program compiles and runs.

### Phase 4 — semantic checking
- Convert nimony's sem, with the borrow checker, once it is stable (around Nim 3's release).
- Nim 2 sem is not converted.

## Following upstream without rewriting

- **Record the source.** Each converted module records its upstream file and commit in its `# /// nimic`
  header, e.g. `# source: nimony@<sha>:src/lib/bitabs.nim`.
- **Diff tool.** A tool (`ncompiler/tools/upstream.py`, to come) prints the upstream diff since that commit.
- **Updates are mechanical.** Conversions are line for line, so applying an upstream change keeps the same
  structure and names. That is work an agent can do.
- **Bumping.** Pins are bumped deliberately, only for modules whose upstream changed.

## Core roadmap, in order of need

1. **Phase 1 blockers:** setter procs, `[]`/`[]=` templates, what astdef/ast/parser reveal, runtime speed.
2. **`../dist/...` imports** and the checksums shims.
3. **Nim 3 compatibility of the transpiled output:** a nimony compile check in `verify_transpiled.py`
   once nimony is pinned.
4. **G17 macros:** needed by Nim 2 sem and msgs, much less by the front end, NIF libraries and nifc.
5. **G19, G20, G23, G24** as they block modules.

## Verification at every step

- **Core:** `test_ntypes`, `test_inliner`, `test_nvariants`, and the module loop (CLAUDE.md §3.5).
- **Python vs Nim:** `tests/verify_transpiled.py`, i.e. modules (`nim check`), fidelity, tests (Python vs
  compiled Nim), imports, raytracer, converters.
- **Against the original:** where the original module can be compiled with converted dependencies, its
  tests are also compared with the original Nim (done for the lexer).
