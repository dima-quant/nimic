# Nim Compiler → Nimic: Conversion Queue

> **Generated** by `python -m ncompiler.tools.dependencies` | **Total modules**: 163 | **Converted**: 36 | **Needs rework**: 1 | **Remaining**: 127

> **Frozen as test corpus** (2026-10-20): the work moved to nimony, see `nnimony/conversion_queue.md` and `ncompiler/conversion_plan.md`. The converted modules stay green in verification but are not extended; the phases below are where the Nim 2 conversion stood.

## Conversion Rules

1. **Convert in phase order, then tier order** — only modules of the current phase, and only when all their dependencies are converted. Blocked and deferred modules are not converted (see below).
2. **Include files** (`include x` in an includer) depend on everything their includer imports or includes before the include point, so they are placed after those modules (column *Included from*).
3. **No stubs** unless strictly necessary and no reordering is possible; stand-ins for unconverted dependencies belong to tests only (`nimic_translation_rules_nim2.md` §2.1).
4. **Missing `nimic.std` modules** can be created proactively.
5. **Review runs automatically** after every conversion.

## Ready to Convert (Phase 1)

Pending modules of the current phase whose dependencies are all converted, smallest first:

| Module | Tier | Size | Included from |
|---|---|---|---|
| — | | | none: frozen |

## Phase 1 — front end

Targets `parser`, `renderer`, `syntaxes`, `astalgo` and their dependencies: 17/27 converted.

| Module | Tier | Size | Missing dependencies | Status |
|---|---|---|---|---|
| `int128` | 0 | 16,767 bytes |  | ✅ Converted |
| `nimpaths` | 0 | 2,194 bytes |  | ✅ Converted + Reviewed |
| `nodekinds` | 0 | 9,756 bytes |  | ✅ Converted |
| `pathutils` | 0 | 5,089 bytes |  | ✅ Converted + Reviewed |
| `platform` | 0 | 14,313 bytes |  | ✅ Converted + Reviewed |
| `prefixmatches` | 0 | 1,543 bytes |  | ✅ Converted + Reviewed |
| `rodutils` | 0 | 4,802 bytes |  | ✅ Converted + Reviewed |
| `wordrecg` | 0 | 8,361 bytes |  | ✅ Converted + Reviewed |
| `idents` | 1 | 3,574 bytes |  | ✅ Converted + Reviewed |
| `llstream` | 1 | 7,399 bytes |  | ✅ Converted + Reviewed |
| `packagehandling` | 1 | 1,343 bytes |  | ✅ Converted + Reviewed |
| `ropes` | 1 | 4,172 bytes |  | ✅ Converted + Reviewed |
| `lineinfos` | 2 | 16,909 bytes |  | ✅ Converted + Reviewed |
| `nimlexbase` | 2 | 5,417 bytes |  | ✅ Converted |
| `options` | 3 | 42,863 bytes |  | ✅ Converted |
| `astdef` | 4 | 48,591 bytes |  | 🔲 Pending |
| `msgs` | 4 | 28,370 bytes |  | ✅ Converted (open gaps: G13 `??`, G17 styled output) |
| `ast` | 5 | 53,120 bytes | astdef | 🔲 Pending |
| `lexer` | 5 | 48,749 bytes |  | ✅ Converted |
| `astyaml` | 6 | 5,843 bytes | ast | 🔲 Pending |
| `parser` | 6 | 86,112 bytes | ast | 🔲 Pending |
| `trees` | 6 | 9,171 bytes | ast | 🔲 Pending |
| `astalgo` | 7 | 19,737 bytes | ast, astyaml | 🔲 Pending |
| `renderer` | 7 | 72,612 bytes | ast, trees | 🔲 Pending |
| `filters` | 8 | 2,779 bytes | ast, renderer | 🔲 Pending |
| `filter_tmpl` | 9 | 6,791 bytes | ast, filters | 🔲 Pending |
| `syntaxes` | 10 | 4,730 bytes | ast, filter_tmpl, filters, parser, renderer | 🔲 Pending |

## Blocked

Not convertible yet:

| Module | Size | Reason |
|---|---|---|
| `ast2nif` | 60,319 bytes | Nim 3 NIF writer (nimony); not in the bootstrap build |
| `deps` | 18,153 bytes | nimony libraries; not in the bootstrap build |
| `gorgeimpl` | 2,279 bytes | needs `checksums` (sha1) from dist/: Phase 2 import support |
| `nifbackend` | 5,570 bytes | Nim 3 NIF backend (nimony); not in the bootstrap build |
| `nifgen` | 49,570 bytes | Nim 3 NIF generation (nimony); not in the bootstrap build |
| `nimblecmd` | 5,510 bytes | needs `checksums` (sha1) from dist/: Phase 2 import support |
| `tccgen` | 2,914 bytes | needs tinyc (a binding of the Tiny C Compiler) |
| `typekeys` | 8,978 bytes | needs nimony's treemangler/modnames: Phase 2 |

## Deferred

Nim 2 parts that Nim 3 replaces: not converted. Already converted ones (marked *corpus*) stay as test corpus and are not extended.

- **Nim 2 semantic checking: replaced by nimony's sem (Phase 4)** (55 modules, 1,390,352 bytes): `aliasanalysis` *(corpus)*, `aliases`, `astmsgs`, `concepts`, `dfa`, `enumtostr`, `errorhandling`, `evaltempl`, `expanddefaults`, `guards`, `hlo` *(corpus)*, `importer`, `isolation_check`, `layeredtable`, `liftlocals`, `linter`, `lookups`, `magicsys`, `nilcheck`, `nimsets`, `optimizer`, `parampatterns`, `patterns`, `pragmas`, `procfind`, `pushpoppragmas`, `reorder`, `sem`, `semcall`, `semdata`, `semexprs`, `semfields`, `semfold`, `semgnrc`, `seminst`, `semmacrosanity`, `semmagic`, `semobjconstr`, `semparallel`, `sempass2`, `semstmts`, `semstrictfuncs`, `semtempl`, `semtypes`, `semtypinst`, `sighashes`, `sigmatch`, `sinkparameter_inference` *(corpus)*, `sizealignoffsetimpl`, `suggest`, `suggestsymdb`, `treetab`, `typeallowed`, `types`, `typesrenderer`
- **Nim 2 transforms: replaced by nimony's hexer (Phase 4)** (9 modules, 327,780 bytes): `closureiters`, `injectdestructors`, `lambdalifting`, `liftdestructors`, `lowerings`, `spawn`, `transf`, `varpartitions`, `vtables`
- **Nim 2 VM: replaced in Nim 3** (13 modules, 271,416 bytes): `evalffi`, `macrocacheimpl`, `nimeval`, `scriptconfig`, `vm`, `vmconv`, `vmdef`, `vmdeps`, `vmgen`, `vmhooks`, `vmmarshal`, `vmops`, `vmprofiler`
- **Nim 2 C backend: replaced by nifc (Phase 3)** (21 modules, 619,491 bytes): `cbuilderbase` *(corpus)*, `cbuilderdecls` *(corpus)*, `cbuilderexprs` *(corpus)*, `cbuilderstmts` *(corpus)*, `ccgcalls`, `ccgexprs`, `ccgliterals` *(corpus)*, `ccgmerge_unused`, `ccgreset` *(corpus)*, `ccgstmts`, `ccgthreadvars` *(corpus)*, `ccgtrav` *(corpus)*, `ccgtypes`, `ccgutils`, `cgen`, `cgendata`, `cgmeth`, `debuginfo`, `extccomp`, `inliner` *(corpus)*, `mangleutils`
- **Nim 2 JS backend: not targeted** (4 modules, 124,236 bytes): `jsgen`, `jstypes` *(corpus)*, `nodejs` *(corpus)*, `sourcemap` *(corpus)*
- **Nim 2 driver and tools: decide in Phase 2 (nimony's driver)** (21 modules, 266,699 bytes): `cmdlinehelper`, `commands`, `debugutils`, `depends`, `docgen`, `docgen2`, `index`, `layouter`, `main`, `modulegraphs`, `modulepaths`, `modules`, `nim`, `nimconf`, `packages`, `passaux`, `passes`, `pipelines`, `pipelineutils`, `pluginsupport`, `renderverbatim`

## Planned (outside compiler/)

- **Phase 2:** nimony `src/lib`: bitabs, nifstreams, nifreader, nifbuilder, ... (at a pinned commit)
- **Phase 2:** nifler (Nim → NIF, on Nim 2's parser)
- **Phase 2:** `checksums` (md5, sha1) and nimony's treemangler/modnames, unblocking typekeys and modulegraphs
- **Phase 3:** nifc (NIF → C), at the pin
- **Phase 3:** an LLVM backend through the LLVM C API (`@importc`)
- **Phase 4:** nimony's sem and hexer, once stable

## Needs Rework

See `ncompiler/review_core_2026_10_16.md` and `ncompiler/proposals/feature_line_for_line_fidelity.md`.

| Module | Tier | Status | Missing dependencies |
|---|---|---|---|
| `aliasanalysis` | 6 | ⚠️ Needs reconversion | ast |

## Progress by Tier

| Tier | Modules | Converted | Remaining |
|---|---|---|---|
| 0 | 14 | 14 | 0 |
| 1 | 4 | 4 | 0 |
| 2 | 3 | 3 | 0 |
| 3 | 1 | 1 | 0 |
| 4 | 4 | 2 | 2 |
| 5 | 7 | 1 | 6 |
| 6 | 9 | 0 | 9 |
| 7 | 2 | 0 | 2 |
| 8 | 8 | 0 | 8 |
| 9 | 8 | 0 | 8 |
| 10 | 9 | 1 | 8 |
| 11 | 19 | 3 | 16 |
| 12 | 10 | 0 | 10 |
| 13 | 3 | 1 | 2 |
| 14 | 8 | 2 | 6 |
| 15 | 7 | 0 | 7 |
| 16 | 6 | 2 | 4 |
| 17 | 4 | 0 | 4 |
| 18 | 2 | 0 | 2 |
| 19 | 2 | 0 | 2 |
| 20 | 3 | 0 | 3 |
| 21 | 5 | 1 | 4 |
| 22 | 5 | 1 | 4 |
| 23 | 5 | 0 | 5 |
| 24 | 2 | 0 | 2 |
| 25 | 1 | 0 | 1 |
| 26 | 1 | 0 | 1 |
| 27 | 1 | 0 | 1 |
| 28 | 2 | 0 | 2 |
| 29 | 2 | 0 | 2 |
| 30 | 2 | 0 | 2 |
| 31 | 2 | 0 | 2 |
| 32 | 1 | 0 | 1 |
| 33 | 1 | 0 | 1 |

## Full Tier Breakdown

Scope: `P1` current phase, `done` converted, `corpus` converted Nim 2 part that Nim 3 replaces, `blocked`, `deferred` (see above).

### Tier 0 (14/14 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `bitsets` | 2,754 bytes |  |  | done | ✅ Converted + Reviewed |
| `btrees` | 5,048 bytes |  |  | done | ✅ Converted + Reviewed |
| `int128` | 16,767 bytes |  |  | P1 | ✅ Converted |
| `nimpaths` | 2,194 bytes |  |  | P1 | ✅ Converted + Reviewed |
| `nodejs` | 347 bytes |  |  | corpus | ✅ Converted + Reviewed |
| `nodekinds` | 9,756 bytes |  |  | P1 | ✅ Converted |
| `nversion` | 764 bytes |  |  | done | ✅ Converted + Reviewed |
| `pathutils` | 5,089 bytes |  |  | P1 | ✅ Converted + Reviewed |
| `platform` | 14,313 bytes |  |  | P1 | ✅ Converted + Reviewed |
| `prefixmatches` | 1,543 bytes |  |  | P1 | ✅ Converted + Reviewed |
| `rodutils` | 4,802 bytes |  |  | P1 | ✅ Converted + Reviewed |
| `saturate` | 2,189 bytes |  |  | done | ✅ Converted + Reviewed |
| `sourcemap` | 7,591 bytes |  |  | corpus | ✅ Converted + Reviewed |
| `wordrecg` | 8,361 bytes |  |  | P1 | ✅ Converted + Reviewed |

### Tier 1 (4/4 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `idents` | 3,574 bytes | wordrecg |  | P1 | ✅ Converted + Reviewed |
| `llstream` | 7,399 bytes | pathutils |  | P1 | ✅ Converted + Reviewed |
| `packagehandling` | 1,343 bytes | pathutils | options | P1 | ✅ Converted + Reviewed |
| `ropes` | 4,172 bytes | pathutils |  | P1 | ✅ Converted + Reviewed |

### Tier 2 (3/3 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `cbuilderbase` | 4,152 bytes | int128, ropes |  | corpus | ✅ Converted |
| `lineinfos` | 16,909 bytes | pathutils, ropes |  | P1 | ✅ Converted + Reviewed |
| `nimlexbase` | 5,417 bytes | llstream |  | P1 | ✅ Converted |

### Tier 3 (1/1 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `options` | 42,863 bytes | lineinfos, nimpaths, packagehandling, pathutils, platform +1 more |  | P1 | ✅ Converted |

### Tier 4 (2/4 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `astdef` | 48,591 bytes | idents, int128, lineinfos, nodekinds, options +1 more |  | P1 | 🔲 Pending |
| `condsyms` | 6,460 bytes | lineinfos, options |  | done | ✅ Converted |
| `debugutils` | 2,192 bytes | options |  | deferred | 🔲 Pending |
| `msgs` | 28,370 bytes | lineinfos, options, pathutils, ropes |  | P1 | ✅ Converted (open gaps: G13 `??`, G17 styled output) |

### Tier 5 (1/7 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `ast` | 53,120 bytes | astdef, idents, int128, lineinfos, nodekinds +2 more |  | P1 | 🔲 Pending |
| `deps` | 18,153 bytes | lineinfos, msgs, options, pathutils |  | blocked | 🔲 Pending |
| `gorgeimpl` | 2,279 bytes | lineinfos, msgs, options, pathutils |  | blocked | 🔲 Pending |
| `lexer` | 48,749 bytes | idents, lineinfos, llstream, msgs, nimlexbase +4 more |  | P1 | ✅ Converted |
| `nimblecmd` | 5,510 bytes | lineinfos, msgs, options, pathutils |  | blocked | 🔲 Pending |
| `tccgen` | 2,914 bytes | lineinfos, msgs, options |  | blocked | 🔲 Pending |
| `typekeys` | 8,978 bytes | astdef, idents, lineinfos, msgs, options |  | blocked | 🔲 Pending |

### Tier 6 (0/9 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `aliasanalysis` | 4,352 bytes | ast |  | corpus | ⚠️ Needs reconversion |
| `ast2nif` | 60,319 bytes | astdef, idents, lineinfos, msgs, options +2 more |  | blocked | 🔲 Pending |
| `astmsgs` | 1,970 bytes | ast, msgs, options |  | deferred | 🔲 Pending |
| `astyaml` | 5,843 bytes | ast, lineinfos, msgs, options, rodutils |  | P1 | 🔲 Pending |
| `layouter` | 19,550 bytes | ast, idents, lexer, lineinfos, llstream +3 more |  | deferred | 🔲 Pending |
| `packages` | 1,799 bytes | ast, idents, lineinfos, msgs, options +1 more |  | deferred | 🔲 Pending |
| `parser` | 86,112 bytes | ast, idents, lexer, lineinfos, llstream +3 more |  | P1 | 🔲 Pending |
| `suggestsymdb` | 7,101 bytes | ast, lineinfos, msgs |  | deferred | 🔲 Pending |
| `trees` | 9,171 bytes | ast, idents, wordrecg |  | P1 | 🔲 Pending |

### Tier 7 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `astalgo` | 19,737 bytes | ast, astyaml, idents, lineinfos, msgs +2 more |  | P1 | 🔲 Pending |
| `renderer` | 72,612 bytes | ast, idents, lexer, lineinfos, msgs +3 more |  | P1 | 🔲 Pending |

### Tier 8 (0/8 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `dfa` | 13,105 bytes | aliasanalysis, ast, lineinfos, renderer |  | deferred | 🔲 Pending |
| `evaltempl` | 8,317 bytes | ast, astalgo, idents, lineinfos, msgs +3 more |  | deferred | 🔲 Pending |
| `filters` | 2,779 bytes | ast, idents, llstream, msgs, options +2 more |  | P1 | 🔲 Pending |
| `layeredtable` | 3,220 bytes | ast, astalgo |  | deferred | 🔲 Pending |
| `modulegraphs` | 29,119 bytes | ast, astalgo, btrees, idents, lineinfos +7 more |  | deferred | 🔲 Pending |
| `modulepaths` | 4,195 bytes | ast, idents, lineinfos, msgs, options +2 more |  | deferred | 🔲 Pending |
| `optimizer` | 8,219 bytes | ast, idents, renderer, trees |  | deferred | 🔲 Pending |
| `renderverbatim` | 4,389 bytes | ast, astalgo, msgs, options, renderer |  | deferred | 🔲 Pending |

### Tier 9 (0/8 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `cgendata` | 11,199 bytes | ast, cbuilderbase, lineinfos, modulegraphs, options +2 more |  | deferred | 🔲 Pending |
| `depends` | 3,135 bytes | ast, lineinfos, modulegraphs, msgs, options +2 more |  | deferred | 🔲 Pending |
| `extccomp` | 47,774 bytes | condsyms, lineinfos, modulepaths, msgs, options +3 more |  | deferred | 🔲 Pending |
| `filter_tmpl` | 6,791 bytes | ast, filters, lineinfos, llstream, msgs +2 more |  | P1 | 🔲 Pending |
| `mangleutils` | 1,570 bytes | ast, modulegraphs |  | deferred | 🔲 Pending |
| `pipelineutils` | 1,133 bytes | ast, lineinfos, modulegraphs, msgs, options +2 more |  | deferred | 🔲 Pending |
| `sizealignoffsetimpl` | 17,025 bytes | ast, int128, lineinfos, modulegraphs, msgs +3 more | types | deferred | 🔲 Pending |
| `vmdef` | 11,634 bytes | ast, idents, lineinfos, modulegraphs, options |  | deferred | 🔲 Pending |

### Tier 10 (1/9 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `cbuilderexprs` | 6,794 bytes | ast, cbuilderbase, cgendata | cgen | corpus | ✅ Converted |
| `ccgmerge_unused` | 8,140 bytes | ast, cgendata, llstream, modulegraphs, nimlexbase +4 more |  | deferred | 🔲 Pending |
| `commands` | 53,094 bytes | ast, condsyms, extccomp, lineinfos, msgs +6 more |  | deferred | 🔲 Pending |
| `macrocacheimpl` | 1,375 bytes | ast, lineinfos, vmdef |  | deferred | 🔲 Pending |
| `syntaxes` | 4,730 bytes | ast, filter_tmpl, filters, idents, lexer +7 more |  | P1 | 🔲 Pending |
| `types` | 62,513 bytes | ast, astalgo, astmsgs, int128, lineinfos +8 more |  | deferred | 🔲 Pending |
| `vmconv` | 1,723 bytes | ast, astalgo, idents, lineinfos, vmdef |  | deferred | 🔲 Pending |
| `vmhooks` | 2,334 bytes | ast, btrees, lineinfos, options, pathutils +2 more | vm | deferred | 🔲 Pending |
| `vmprofiler` | 1,366 bytes | ast, lineinfos, msgs, options, vmdef |  | deferred | 🔲 Pending |

### Tier 11 (3/19 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `aliases` | 6,452 bytes | ast, astalgo, trees, types |  | deferred | 🔲 Pending |
| `cbuilderdecls` | 22,463 bytes | ast, astalgo, cbuilderbase, cbuilderexprs, cgendata +7 more | cgen | corpus | ✅ Converted |
| `cbuilderstmts` | 9,403 bytes | ast, astalgo, cbuilderbase, cbuilderexprs, cgendata +1 more | cgen | corpus | ✅ Converted |
| `ccgutils` | 5,474 bytes | ast, cgendata, mangleutils, msgs, options +5 more |  | deferred | 🔲 Pending |
| `errorhandling` | 2,419 bytes | ast, options, renderer, types |  | deferred | 🔲 Pending |
| `evalffi` | 17,708 bytes | ast, lineinfos, msgs, options, types |  | deferred | 🔲 Pending |
| `expanddefaults` | 4,655 bytes | ast, lineinfos, types |  | deferred | 🔲 Pending |
| `isolation_check` | 7,161 bytes | ast, renderer, types |  | deferred | 🔲 Pending |
| `jstypes` | 6,158 bytes | ast, idents, lineinfos, modulegraphs, msgs +4 more | jsgen | corpus | ✅ Converted + Reviewed |
| `magicsys` | 6,205 bytes | ast, idents, lineinfos, modulegraphs, msgs +2 more |  | deferred | 🔲 Pending |
| `nifgen` | 49,570 bytes | ast, astalgo, idents, lineinfos, modulegraphs +4 more |  | blocked | 🔲 Pending |
| `nimsets` | 4,476 bytes | ast, astalgo, bitsets, lineinfos, options +1 more |  | deferred | 🔲 Pending |
| `parampatterns` | 12,813 bytes | ast, idents, msgs, options, renderer +3 more |  | deferred | 🔲 Pending |
| `reorder` | 13,966 bytes | ast, idents, lineinfos, modulegraphs, modulepaths +4 more |  | deferred | 🔲 Pending |
| `sighashes` | 15,004 bytes | ast, modulegraphs, msgs, options, pathutils +2 more |  | deferred | 🔲 Pending |
| `treetab` | 3,672 bytes | ast, types |  | deferred | 🔲 Pending |
| `typesrenderer` | 5,110 bytes | ast, renderer, types |  | deferred | 🔲 Pending |
| `vmdeps` | 13,802 bytes | ast, idents, lineinfos, msgs, options +2 more |  | deferred | 🔲 Pending |
| `vmmarshal` | 9,895 bytes | ast, astalgo, idents, lineinfos, msgs +2 more |  | deferred | 🔲 Pending |

### Tier 12 (0/10 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `debuginfo` | 2,052 bytes | sighashes |  | deferred | 🔲 Pending |
| `docgen` | 78,864 bytes | ast, idents, lexer, lineinfos, msgs +12 more |  | deferred | 🔲 Pending |
| `enumtostr` | 3,800 bytes | ast, idents, lineinfos, magicsys, modulegraphs |  | deferred | 🔲 Pending |
| `guards` | 37,907 bytes | ast, astalgo, idents, int128, lineinfos +9 more |  | deferred | 🔲 Pending |
| `lowerings` | 12,401 bytes | ast, astalgo, idents, lineinfos, magicsys +4 more |  | deferred | 🔲 Pending |
| `modules` | 2,488 bytes | ast, idents, lexer, lineinfos, magicsys +5 more |  | deferred | 🔲 Pending |
| `nilcheck` | 44,931 bytes | ast, idents, lineinfos, msgs, options +2 more |  | deferred | 🔲 Pending |
| `semfold` | 31,536 bytes | ast, commands, idents, lineinfos, magicsys +9 more |  | deferred | 🔲 Pending |
| `semmacrosanity` | 6,152 bytes | ast, msgs, nimsets, options, trees +1 more |  | deferred | 🔲 Pending |
| `vmops` | 14,897 bytes | ast, btrees, gorgeimpl, idents, int128 +9 more | vm | deferred | 🔲 Pending |

### Tier 13 (1/3 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `ccgliterals` | 13,946 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +12 more | cgen | corpus | ✅ Converted |
| `docgen2` | 2,211 bytes | ast, docgen, lineinfos, modulegraphs, msgs +3 more |  | deferred | 🔲 Pending |
| `semdata` | 31,097 bytes | ast, astalgo, idents, layeredtable, lineinfos +11 more |  | deferred | 🔲 Pending |

### Tier 14 (2/8 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `ccgtrav` | 8,380 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +14 more | ccgtypes | corpus | ✅ Converted |
| `liftdestructors` | 57,474 bytes | ast, ccgutils, idents, lineinfos, lowerings +9 more |  | deferred | 🔲 Pending |
| `linter` | 6,704 bytes | ast, astmsgs, idents, lineinfos, modulegraphs +5 more |  | deferred | 🔲 Pending |
| `lookups` | 33,183 bytes | ast, astalgo, astmsgs, idents, lineinfos +7 more |  | deferred | 🔲 Pending |
| `pluginsupport` | 943 bytes | ast, idents, semdata |  | deferred | 🔲 Pending |
| `semtypinst` | 34,068 bytes | ast, astalgo, layeredtable, lineinfos, magicsys +6 more |  | deferred | 🔲 Pending |
| `sinkparameter_inference` | 2,393 bytes | ast, astalgo, guards, idents, lineinfos +7 more | sempass2 | corpus | ✅ Converted + Reviewed |
| `typeallowed` | 10,737 bytes | ast, options, renderer, semdata, types |  | deferred | 🔲 Pending |

### Tier 15 (0/7 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `ccgtypes` | 84,300 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +19 more | cgen | deferred | 🔲 Pending |
| `concepts` | 22,764 bytes | ast, idents, layeredtable, lineinfos, lookups +4 more |  | deferred | 🔲 Pending |
| `procfind` | 3,474 bytes | ast, astalgo, lookups, msgs, semdata +2 more |  | deferred | 🔲 Pending |
| `semstrictfuncs` | 1,688 bytes | aliasanalysis, ast, renderer, trees, typeallowed |  | deferred | 🔲 Pending |
| `spawn` | 19,073 bytes | ast, idents, liftdestructors, lowerings, magicsys +6 more |  | deferred | 🔲 Pending |
| `suggest` | 36,588 bytes | ast, astalgo, idents, lexer, lineinfos +10 more | sigmatch | deferred | 🔲 Pending |
| `varpartitions` | 37,399 bytes | ast, isolation_check, lineinfos, modulegraphs, msgs +5 more |  | deferred | 🔲 Pending |

### Tier 16 (2/6 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `ccgcalls` | 33,985 bytes | aliasanalysis, aliases, ast, astalgo, cbuilderbase +15 more | cgen | deferred | 🔲 Pending |
| `ccgreset` | 4,536 bytes | ast, cbuilderbase, cbuilderexprs, cbuilderstmts, ccgliterals +12 more | cgen | corpus | ✅ Converted |
| `ccgthreadvars` | 2,429 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +9 more | cgen | corpus | ✅ Converted |
| `injectdestructors` | 54,800 bytes | aliasanalysis, ast, astalgo, dfa, idents +15 more |  | deferred | 🔲 Pending |
| `semparallel` | 17,154 bytes | ast, astalgo, guards, idents, lineinfos +9 more |  | deferred | 🔲 Pending |
| `sigmatch` | 122,192 bytes | ast, astalgo, concepts, idents, layeredtable +16 more |  | deferred | 🔲 Pending |

### Tier 17 (0/4 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `importer` | 14,526 bytes | ast, idents, lineinfos, lookups, modulegraphs +6 more |  | deferred | 🔲 Pending |
| `patterns` | 10,598 bytes | aliases, ast, idents, parampatterns, semdata +3 more |  | deferred | 🔲 Pending |
| `pragmas` | 52,923 bytes | ast, astalgo, condsyms, extccomp, idents +15 more |  | deferred | 🔲 Pending |
| `semcall` | 44,523 bytes | ast, astalgo, astmsgs, idents, int128 +14 more | sem | deferred | 🔲 Pending |

### Tier 18 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `liftlocals` | 2,355 bytes | ast, idents, lineinfos, lowerings, msgs +5 more |  | deferred | 🔲 Pending |
| `pushpoppragmas` | 2,049 bytes | ast, idents, lineinfos, options, pragmas +3 more |  | deferred | 🔲 Pending |

### Tier 19 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `ccgstmts` | 71,794 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +20 more | cgen | deferred | 🔲 Pending |
| `sempass2` | 71,677 bytes | ast, astalgo, errorhandling, guards, idents +19 more |  | deferred | 🔲 Pending |

### Tier 20 (0/3 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `ccgexprs` | 163,248 bytes | aliases, ast, astalgo, astmsgs, bitsets +26 more | cgen | deferred | 🔲 Pending |
| `cgmeth` | 11,076 bytes | ast, astalgo, idents, lineinfos, magicsys +6 more |  | deferred | 🔲 Pending |
| `seminst` | 18,919 bytes | ast, astalgo, extccomp, idents, int128 +16 more | sem | deferred | 🔲 Pending |

### Tier 21 (1/5 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `closureiters` | 51,781 bytes | ast, idents, lambdalifting, lineinfos, lowerings +5 more |  | deferred | 🔲 Pending |
| `inliner` | 4,217 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderstmts +8 more | cgen | corpus | ✅ Converted + Reviewed |
| `lambdalifting` | 38,285 bytes | ast, astalgo, idents, liftdestructors, lineinfos +9 more |  | deferred | 🔲 Pending |
| `transf` | 49,864 bytes | ast, astalgo, cgmeth, closureiters, idents +12 more |  | deferred | 🔲 Pending |
| `vtables` | 6,703 bytes | ast, cgmeth, lineinfos, magicsys, modulegraphs +2 more |  | deferred | 🔲 Pending |

### Tier 22 (1/5 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `cgen` | 102,559 bytes | aliases, ast, astalgo, astmsgs, bitsets +44 more |  | deferred | 🔲 Pending |
| `hlo` | 3,811 bytes | ast, astalgo, evaltempl, idents, int128 +12 more | sem | corpus | ✅ Converted + Reviewed |
| `jsgen` | 110,140 bytes | ast, astmsgs, cgmeth, idents, injectdestructors +19 more |  | deferred | 🔲 Pending |
| `semtypes` | 106,643 bytes | ast, astalgo, concepts, enumtostr, idents +29 more | sem | deferred | 🔲 Pending |
| `vmgen` | 86,949 bytes | ast, astmsgs, evalffi, lineinfos, lowerings +10 more |  | deferred | 🔲 Pending |

### Tier 23 (0/5 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `nifbackend` | 5,570 bytes | ast, ast2nif, cgen, cgendata, extccomp +8 more |  | blocked | 🔲 Pending |
| `semfields` | 6,625 bytes | ast, astalgo, idents, int128, layeredtable +15 more | semstmts | deferred | 🔲 Pending |
| `semgnrc` | 24,878 bytes | ast, astalgo, idents, int128, lineinfos +14 more | sem | deferred | 🔲 Pending |
| `semtempl` | 31,451 bytes | ast, astalgo, idents, int128, lineinfos +18 more | sem | deferred | 🔲 Pending |
| `vm` | 95,117 bytes | ast, btrees, evalffi, evaltempl, gorgeimpl +23 more |  | deferred | 🔲 Pending |

### Tier 24 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `semmagic` | 27,519 bytes | aliases, ast, astalgo, idents, int128 +22 more | semexprs | deferred | 🔲 Pending |
| `semstmts` | 117,249 bytes | ast, astalgo, cgmeth, hlo, idents +27 more | sem | deferred | 🔲 Pending |

### Tier 25 (0/1 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `semobjconstr` | 23,372 bytes | ast, astalgo, astmsgs, idents, int128 +18 more | semexprs | deferred | 🔲 Pending |

### Tier 26 (0/1 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `semexprs` | 142,092 bytes | ast, astalgo, astmsgs, evaltempl, idents +35 more | sem | deferred | 🔲 Pending |

### Tier 27 (0/1 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `sem` | 35,019 bytes | aliases, ast, astalgo, astmsgs, cgmeth +51 more |  | deferred | 🔲 Pending |

### Tier 28 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `passes` | 8,340 bytes | ast, idents, lineinfos, llstream, modulegraphs +10 more |  | deferred | 🔲 Pending |
| `pipelines` | 15,252 bytes | ast, cgen, cgendata, depends, docgen2 +23 more |  | deferred | 🔲 Pending |

### Tier 29 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `passaux` | 942 bytes | ast, lineinfos, modulegraphs, msgs, options +1 more |  | deferred | 🔲 Pending |
| `scriptconfig` | 8,169 bytes | ast, commands, condsyms, idents, llstream +8 more |  | deferred | 🔲 Pending |

### Tier 30 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `nimconf` | 11,746 bytes | ast, commands, idents, lexer, lineinfos +6 more |  | deferred | 🔲 Pending |
| `nimeval` | 6,447 bytes | ast, condsyms, idents, lineinfos, llstream +8 more |  | deferred | 🔲 Pending |

### Tier 31 (0/2 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `cmdlinehelper` | 3,134 bytes | commands, condsyms, extccomp, idents, lineinfos +5 more |  | deferred | 🔲 Pending |
| `main` | 17,538 bytes | ast, cgen, condsyms, depends, docgen +16 more |  | deferred | 🔲 Pending |

### Tier 32 (0/1 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `nim` | 6,157 bytes | cmdlinehelper, commands, extccomp, idents, lineinfos +7 more |  | deferred | 🔲 Pending |

### Tier 33 (0/1 converted)

| Module | Size | Dependencies | Included from | Scope | Status |
|---|---|---|---|---|---|
| `index` | 478 bytes | nim |  | deferred | 🔲 Pending |
