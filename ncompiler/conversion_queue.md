# Nim Compiler → Nimic: Conversion Queue

> **Generated**: 2026-09-15 | **Total modules**: 164 | **Converted**: 18 | **Remaining**: 146

## Progress Summary

| Tier | Modules | Converted | Remaining | Description |
|------|---------|-----------|-----------|-------------|
| 0 | 37 | 12 | 25 | No dependencies (leaf modules) |
| 1 | 7 | 3 | 4 | Single-tier dependencies |
| 2 | 3 | 1 | 2 | Depends on Tiers 0–1 |
| 3 | 11 | 2 | 9 | Core infrastructure (options, msgs, trees) |
| 4–6 | 8 | 0 | 8 | Lexer, AST foundation |
| 7–10 | 26 | 0 | 26 | Renderer, parser, types, modulegraphs |
| 11–15 | 43 | 0 | 43 | Type analysis, semantic data |
| 16–22 | 20 | 0 | 20 | Semantic analysis, code generation |
| 23–28 | 9 | 0 | 9 | VM, sem, pipelines, main |
| **Total** | **164** | **18** | **146** | |

## Conversion Rules

1. **Convert in tier order** — only convert a module when all its dependencies are already converted
2. **Re-verify existing conversions** — files already in `ncompiler/` must be re-checked
3. **No stubs** unless strictly necessary and no reordering is possible
4. **Missing `nimic.std` modules** can be created proactively
5. **Review runs automatically** after every conversion

## Immediate Next Actions (Ready to Convert)

These are Tier 0 modules not yet converted, sorted by file size (smallest first):

| Priority | Module | Size | Notes |
|----------|--------|------|-------|
| 1 | `bitsets` | 2,754 bytes | Bit set operations |
| 2 | `hlo` | 3,811 bytes | High-level optimizer |
| 6 | `inliner` | 4,217 bytes | Inlining |
| 7 | `aliasanalysis` | 4,352 bytes | Alias analysis |
| 8 | `ccgreset` | 4,536 bytes | C gen reset |
| 9 | `rodutils` | 4,802 bytes | Rod file utilities |
| 10 | `btrees` | 5,048 bytes | B-tree implementation |
| 11 | `jstypes` | 6,158 bytes | JS type gen |
| 12 | `cbuilderexprs` | 6,794 bytes | C builder expressions |
| 13 | `sourcemap` | 7,591 bytes | Source maps |
| 14 | `ccgtrav` | 8,380 bytes | C gen traversal |
| 15 | `cbuilderstmts` | 9,403 bytes | C builder statements |
| 16 | `ccgliterals` | 13,946 bytes | C gen literals |
| 17 | `int128` | 16,767 bytes | 128-bit integer |
| 18 | `sizealignoffsetimpl` | 17,025 bytes | Size/align computation |
| 19 | `cbuilderdecls` | 22,463 bytes | C builder declarations |
| 20 | `semobjconstr` | 23,372 bytes | Object construction (sem) |
| 21 | `semgnrc` | 24,878 bytes | Generic sem |
| 22 | `semmagic` | 27,519 bytes | Magic sem |
| 23 | `semtempl` | 31,451 bytes | Template sem |
| 24 | `semcall` | 44,523 bytes | Call sem |
| 25 | `semfields` | 6,625 bytes | Field sem |
| 26 | `seminst` | 18,919 bytes | Instantiation sem |
| 27 | `ccgstmts` | 71,794 bytes | C gen statements (large) |
| 28 | `semtypes` | 106,643 bytes | Type sem (very large) |

### Already Converted & Reviewed

| Module | Tier | Review Log | Status |
|--------|------|------------|--------|
| `wordrecg` | 0 | `ncompiler/review_wordrecg.md` | ✅ Complete |
| `pathutils` | 0 | `ncompiler/review_pathutils.md` | ✅ Complete |
| `nimpaths` | 0 | `ncompiler/review_nimpaths.md` | ✅ Complete |
| `nodekinds` | 0 | `ncompiler/review_nodekinds.md` | ✅ Complete |
| `platform` | 0 | `ncompiler/review_platform.md` | ✅ Complete |
| `prefixmatches` | 0 | `ncompiler/review_prefixmatches.md` | ✅ Complete |
| `saturate` | 0 | `ncompiler/review_saturate.md` | ✅ Complete |
| `nodejs` | 0 | `ncompiler/review_nodejs.md` | ✅ Complete |
| `nversion` | 0 | `ncompiler/review_nversion.md` | ✅ Complete |
| `packagehandling` | 0 | `ncompiler/review_packagehandling.md` | ✅ Complete |
| `sinkparameter_inference` | 0 | `ncompiler/review_sinkparameter_inference.md` | ✅ Complete |
| `ccgthreadvars` | 0 | `ncompiler/review_ccgthreadvars.md` | ✅ Complete |
| `idents` | 1 | `ncompiler/review_idents.md` | ✅ Complete |
| `llstream` | 1 | `ncompiler/review_llstream.md` | ✅ Complete |
| `ropes` | 1 | `ncompiler/review_ropes.md` | ✅ Complete |
| `lineinfos` | 2 | `ncompiler/review_lineinfos.md` | ✅ Complete |
| `msgs` | 3 | `ncompiler/review_msgs.md` | ✅ Complete |
| `options` | 3 | `ncompiler/review_options.md` | ✅ Complete |

---

## Full Tier Breakdown

### Tier 0 — No dependencies (6/37 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `aliasanalysis` | 4,352 bytes |  | 🔲 Pending |
| `bitsets` | 2,754 bytes |  | 🔲 Pending |
| `btrees` | 5,048 bytes |  | 🔲 Pending |
| `cbuilderdecls` | 22,463 bytes |  | 🔲 Pending |
| `cbuilderexprs` | 6,794 bytes |  | 🔲 Pending |
| `cbuilderstmts` | 9,403 bytes |  | 🔲 Pending |
| `ccgliterals` | 13,946 bytes |  | 🔲 Pending |
| `ccgreset` | 4,536 bytes |  | 🔲 Pending |
| `ccgstmts` | 71,794 bytes |  | 🔲 Pending |
| `ccgthreadvars` | 2,429 bytes |  | ✅ Converted + Reviewed |
| `ccgtrav` | 8,380 bytes |  | 🔲 Pending |
| `hlo` | 3,811 bytes |  | 🔲 Pending |
| `inliner` | 4,217 bytes |  | 🔲 Pending |
| `int128` | 16,767 bytes |  | 🔲 Pending |
| `jstypes` | 6,158 bytes |  | 🔲 Pending |
| `nimpaths` | 2,194 bytes |  | ✅ Converted + Reviewed |
| `nodejs` | 347 bytes |  | ✅ Converted + Reviewed |
| `nodekinds` | 9,756 bytes |  | ✅ Converted |
| `nversion` | 764 bytes |  | ✅ Converted + Reviewed |
| `packagehandling` | 1,343 bytes |  | ✅ Converted + Reviewed |
| `pathutils` | 5,089 bytes |  | ✅ Converted + Reviewed |
| `platform` | 14,313 bytes |  | ✅ Converted + Reviewed |
| `prefixmatches` | 1,543 bytes |  | ✅ Converted + Reviewed |
| `rodutils` | 4,802 bytes |  | 🔲 Pending |
| `saturate` | 2,189 bytes |  | ✅ Converted + Reviewed |
| `semcall` | 44,523 bytes |  | 🔲 Pending |
| `semfields` | 6,625 bytes |  | 🔲 Pending |
| `semgnrc` | 24,878 bytes |  | 🔲 Pending |
| `seminst` | 18,919 bytes |  | 🔲 Pending |
| `semmagic` | 27,519 bytes |  | 🔲 Pending |
| `semobjconstr` | 23,372 bytes |  | 🔲 Pending |
| `semtempl` | 31,451 bytes |  | 🔲 Pending |
| `semtypes` | 106,643 bytes |  | 🔲 Pending |
| `sinkparameter_inference` | 2,393 bytes |  | ✅ Converted + Reviewed |
| `sizealignoffsetimpl` | 17,025 bytes |  | 🔲 Pending |
| `sourcemap` | 7,591 bytes |  | 🔲 Pending |
| `wordrecg` | 8,361 bytes |  | ✅ Converted + Reviewed |

### Tier 1 — Depends on Tiers 0–0 (4/7 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `ccgcalls` | 33,985 bytes | aliasanalysis | 🔲 Pending |
| `idents` | 3,574 bytes | wordrecg | ✅ Converted + Reviewed |
| `llstream` | 7,399 bytes | pathutils | ✅ Converted + Reviewed |
| `ropes` | 4,172 bytes | pathutils | ✅ Converted + Reviewed |
| `semexprs` | 142,092 bytes | semmagic, semobjconstr | 🔲 Pending |
| `semstmts` | 117,249 bytes | semfields | 🔲 Pending |
| `vmhooks` | 2,334 bytes | pathutils | 🔲 Pending |

### Tier 2 — Depends on Tiers 0–1 (1/3 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `cbuilderbase` | 4,152 bytes | ropes, int128 | 🔲 Pending |
| `lineinfos` | 16,909 bytes | ropes, pathutils | ✅ Converted + Reviewed |
| `nimlexbase` | 5,417 bytes | llstream | 🔲 Pending |

### Tier 3 — Depends on Tiers 0–2 (2/11 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `astdef` | 48,591 bytes | lineinfos, options, ropes, idents, int128 +1 more | 🔲 Pending |
| `ccgexprs` | 163,248 bytes | parampatterns | 🔲 Pending |
| `ccgtypes` | 84,300 bytes | sighashes, ccgtrav | 🔲 Pending |
| `condsyms` | 6,460 bytes | options, lineinfos | 🔲 Pending |
| `debuginfo` | 2,052 bytes | sighashes | 🔲 Pending |
| `debugutils` | 2,192 bytes | options | 🔲 Pending |
| `index` | 478 bytes | nim | 🔲 Pending |
| `msgs` | 28,370 bytes | options, lineinfos, pathutils, ropes | ✅ Converted + Reviewed |
| `options` | 42,863 bytes | lineinfos, platform, prefixmatches, pathutils, nimpaths +2 more | ✅ Converted + Reviewed |
| `suggest` | 36,588 bytes | prefixmatches, suggestsymdb, wordrecg, pathutils | 🔲 Pending |
| `trees` | 9,171 bytes | ast, wordrecg, idents | 🔲 Pending |

### Tier 4 — Depends on Tiers 0–3 (0/6 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `deps` | 18,153 bytes | options, msgs, lineinfos, pathutils | 🔲 Pending |
| `gorgeimpl` | 2,279 bytes | msgs, options, lineinfos, pathutils | 🔲 Pending |
| `lexer` | 48,749 bytes | options, msgs, platform, idents, nimlexbase +4 more | 🔲 Pending |
| `nimblecmd` | 5,510 bytes | options, msgs, lineinfos, pathutils | 🔲 Pending |
| `tccgen` | 2,914 bytes | options, msgs, lineinfos | 🔲 Pending |
| `typekeys` | 8,978 bytes | astdef, idents, options, lineinfos, msgs +1 more | 🔲 Pending |

### Tier 5 — Depends on Tiers 0–4 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `ast2nif` | 60,319 bytes | astdef, idents, msgs, options, pathutils +2 more | 🔲 Pending |

### Tier 6 — Depends on Tiers 0–5 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `ast` | 53,120 bytes | lineinfos, options, idents, int128, wordrecg +3 more | 🔲 Pending |

### Tier 7 — Depends on Tiers 0–6 (0/6 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `astmsgs` | 1,970 bytes | options, ast, msgs | 🔲 Pending |
| `astyaml` | 5,843 bytes | ast, lineinfos, msgs, options, rodutils | 🔲 Pending |
| `layouter` | 19,550 bytes | idents, lexer, ast, lineinfos, llstream +3 more | 🔲 Pending |
| `packages` | 1,799 bytes | options, ast, lineinfos, idents, pathutils +1 more | 🔲 Pending |
| `renderer` | 72,612 bytes | lexer, options, idents, ast, msgs +3 more | 🔲 Pending |
| `suggestsymdb` | 7,101 bytes | ast, lineinfos, msgs | 🔲 Pending |

### Tier 8 — Depends on Tiers 0–7 (0/6 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `astalgo` | 19,737 bytes | ast, astyaml, options, lineinfos, idents +2 more | 🔲 Pending |
| `dfa` | 13,105 bytes | ast, lineinfos, renderer, aliasanalysis | 🔲 Pending |
| `filters` | 2,779 bytes | llstream, idents, ast, msgs, options +2 more | 🔲 Pending |
| `modulepaths` | 4,195 bytes | ast, renderer, msgs, options, idents +1 more | 🔲 Pending |
| `optimizer` | 8,219 bytes | ast, renderer, idents, trees | 🔲 Pending |
| `parser` | 86,112 bytes | llstream, lexer, idents, msgs, options +5 more | 🔲 Pending |

### Tier 9 — Depends on Tiers 0–8 (0/6 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `evaltempl` | 8,317 bytes | options, ast, astalgo, msgs, renderer +3 more | 🔲 Pending |
| `extccomp` | 47,774 bytes | ropes, platform, condsyms, options, msgs +3 more | 🔲 Pending |
| `filter_tmpl` | 6,791 bytes | llstream, ast, msgs, options, filters +2 more | 🔲 Pending |
| `layeredtable` | 3,220 bytes | ast, astalgo | 🔲 Pending |
| `modulegraphs` | 29,119 bytes | ast, astalgo, options, lineinfos, idents +8 more | 🔲 Pending |
| `renderverbatim` | 4,389 bytes | ast, options, msgs, renderer, astalgo | 🔲 Pending |

### Tier 10 — Depends on Tiers 0–9 (0/8 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `cgendata` | 11,199 bytes | ast, ropes, options, lineinfos, pathutils +2 more | 🔲 Pending |
| `commands` | 53,094 bytes | msgs, options, nversion, condsyms, extccomp +6 more | 🔲 Pending |
| `depends` | 3,135 bytes | options, ast, ropes, pathutils, msgs +2 more | 🔲 Pending |
| `mangleutils` | 1,570 bytes | ast, modulegraphs | 🔲 Pending |
| `pipelineutils` | 1,133 bytes | ast, options, lineinfos, pathutils, msgs +2 more | 🔲 Pending |
| `syntaxes` | 4,730 bytes | llstream, ast, idents, lexer, options +7 more | 🔲 Pending |
| `types` | 62,513 bytes | ast, astalgo, trees, msgs, platform +8 more | 🔲 Pending |
| `vmdef` | 11,634 bytes | ast, idents, options, modulegraphs, lineinfos | 🔲 Pending |

### Tier 11 — Depends on Tiers 0–10 (0/20 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `aliases` | 6,452 bytes | ast, astalgo, types, trees | 🔲 Pending |
| `ccgmerge_unused` | 8,140 bytes | ast, ropes, options, nimlexbase, cgendata +4 more | 🔲 Pending |
| `ccgutils` | 5,474 bytes | ast, types, msgs, wordrecg, platform +5 more | 🔲 Pending |
| `errorhandling` | 2,419 bytes | ast, renderer, options, types | 🔲 Pending |
| `evalffi` | 17,708 bytes | ast, types, options, msgs, lineinfos | 🔲 Pending |
| `expanddefaults` | 4,655 bytes | lineinfos, ast, types | 🔲 Pending |
| `isolation_check` | 7,161 bytes | ast, types, renderer | 🔲 Pending |
| `macrocacheimpl` | 1,375 bytes | lineinfos, ast, vmdef | 🔲 Pending |
| `magicsys` | 6,205 bytes | ast, msgs, platform, idents, modulegraphs +2 more | 🔲 Pending |
| `nifgen` | 49,570 bytes | ast, astalgo, modulegraphs, options, pathutils +4 more | 🔲 Pending |
| `nimsets` | 4,476 bytes | ast, astalgo, lineinfos, bitsets, types +1 more | 🔲 Pending |
| `parampatterns` | 12,813 bytes | ast, types, msgs, idents, renderer +2 more | 🔲 Pending |
| `reorder` | 13,966 bytes | ast, idents, renderer, msgs, modulegraphs +4 more | 🔲 Pending |
| `sighashes` | 15,004 bytes | ast, ropes, modulegraphs, options, msgs +2 more | 🔲 Pending |
| `treetab` | 3,672 bytes | ast, types | 🔲 Pending |
| `typesrenderer` | 5,110 bytes | renderer, ast, types | 🔲 Pending |
| `vmconv` | 1,723 bytes | ast, idents, lineinfos, astalgo, vmdef | 🔲 Pending |
| `vmdeps` | 13,802 bytes | ast, types, msgs, options, idents +2 more | 🔲 Pending |
| `vmmarshal` | 9,895 bytes | ast, astalgo, idents, types, msgs | 🔲 Pending |
| `vmprofiler` | 1,366 bytes | ast, options, vmdef, lineinfos, msgs | 🔲 Pending |

### Tier 12 — Depends on Tiers 0–11 (0/10 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `docgen` | 78,864 bytes | ast, options, msgs, idents, wordrecg +12 more | 🔲 Pending |
| `enumtostr` | 3,800 bytes | ast, idents, lineinfos, modulegraphs, magicsys | 🔲 Pending |
| `guards` | 37,907 bytes | ast, astalgo, msgs, magicsys, nimsets +4 more | 🔲 Pending |
| `lowerings` | 12,401 bytes | ast, astalgo, types, idents, magicsys +3 more | 🔲 Pending |
| `modules` | 2,488 bytes | ast, magicsys, msgs, options, idents +5 more | 🔲 Pending |
| `nilcheck` | 44,931 bytes | ast, renderer, msgs, options, lineinfos +2 more | 🔲 Pending |
| `semfold` | 31,536 bytes | options, ast, trees, nimsets, platform +9 more | 🔲 Pending |
| `semmacrosanity` | 6,152 bytes | ast, msgs, types, options, trees +1 more | 🔲 Pending |
| `spawn` | 19,073 bytes | ast, types, idents, magicsys, msgs +3 more | 🔲 Pending |
| `vmops` | 14,897 bytes | vmconv, vmmarshal | 🔲 Pending |

### Tier 13 — Depends on Tiers 0–12 (0/3 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `docgen2` | 2,211 bytes | options, ast, msgs, docgen, lineinfos +3 more | 🔲 Pending |
| `semdata` | 31,097 bytes | options, ast, msgs, idents, renderer +11 more | 🔲 Pending |
| `semparallel` | 17,154 bytes | ast, astalgo, idents, lowerings, magicsys +9 more | 🔲 Pending |

### Tier 14 — Depends on Tiers 0–13 (0/6 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `liftdestructors` | 57,474 bytes | modulegraphs, lineinfos, idents, ast, renderer +2 more | 🔲 Pending |
| `linter` | 6,704 bytes | options, ast, msgs, idents, lineinfos +5 more | 🔲 Pending |
| `lookups` | 33,183 bytes | ast, astalgo, idents, semdata, types +7 more | 🔲 Pending |
| `pluginsupport` | 943 bytes | ast, semdata, idents | 🔲 Pending |
| `semtypinst` | 34,068 bytes | ast, astalgo, msgs, types, magicsys +3 more | 🔲 Pending |
| `typeallowed` | 10,737 bytes | ast, renderer, options, semdata, types | 🔲 Pending |

### Tier 15 — Depends on Tiers 0–14 (0/4 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `concepts` | 22,764 bytes | ast, semdata, lookups, lineinfos, idents +4 more | 🔲 Pending |
| `procfind` | 3,474 bytes | ast, astalgo, msgs, semdata, types +2 more | 🔲 Pending |
| `semstrictfuncs` | 1,688 bytes | ast, typeallowed, renderer, aliasanalysis, trees | 🔲 Pending |
| `varpartitions` | 37,399 bytes | ast, types, lineinfos, options, msgs +5 more | 🔲 Pending |

### Tier 16 — Depends on Tiers 0–15 (0/2 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `injectdestructors` | 54,800 bytes | ast, astalgo, msgs, renderer, magicsys +15 more | 🔲 Pending |
| `sigmatch` | 122,192 bytes | ast, astalgo, semdata, types, msgs +16 more | 🔲 Pending |

### Tier 17 — Depends on Tiers 0–16 (0/3 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `importer` | 14,526 bytes | ast, msgs, options, idents, lookups +6 more | 🔲 Pending |
| `patterns` | 10,598 bytes | ast, types, semdata, sigmatch, idents +3 more | 🔲 Pending |
| `pragmas` | 52,923 bytes | condsyms, ast, astalgo, idents, semdata +15 more | 🔲 Pending |

### Tier 18 — Depends on Tiers 0–17 (0/2 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `liftlocals` | 2,355 bytes | options, ast, msgs, idents, renderer +5 more | 🔲 Pending |
| `pushpoppragmas` | 2,049 bytes | pragmas, options, ast, trees, lineinfos +3 more | 🔲 Pending |

### Tier 19 — Depends on Tiers 0–18 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `sempass2` | 71,677 bytes | ast, astalgo, msgs, renderer, magicsys +20 more | 🔲 Pending |

### Tier 20 — Depends on Tiers 0–19 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `cgmeth` | 11,076 bytes | options, ast, msgs, idents, renderer +6 more | 🔲 Pending |

### Tier 21 — Depends on Tiers 0–20 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `vtables` | 6,703 bytes | ast, modulegraphs, magicsys, lineinfos, options +2 more | 🔲 Pending |

### Tier 22 — Depends on Tiers 0–21 (0/10 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `cgen` | 102,559 bytes | ast, astalgo, trees, platform, magicsys +43 more | 🔲 Pending |
| `closureiters` | 51,781 bytes | ast, msgs, idents, renderer, magicsys +5 more | 🔲 Pending |
| `cmdlinehelper` | 3,134 bytes | options, idents, nimconf, extccomp, commands +5 more | 🔲 Pending |
| `jsgen` | 110,140 bytes | ast, trees, magicsys, options, nversion +19 more | 🔲 Pending |
| `lambdalifting` | 38,285 bytes | options, ast, astalgo, msgs, idents +9 more | 🔲 Pending |
| `nifbackend` | 5,570 bytes | ast, options, lineinfos, modulegraphs, cgendata +1 more | 🔲 Pending |
| `nimconf` | 11,746 bytes | llstream, commands, msgs, lexer, ast +6 more | 🔲 Pending |
| `passaux` | 942 bytes | ast, passes, msgs, options, lineinfos +1 more | 🔲 Pending |
| `passes` | 8,340 bytes | options, ast, llstream, msgs, idents +11 more | 🔲 Pending |
| `vmgen` | 86,949 bytes | ast, types, msgs, renderer, vmdef +10 more | 🔲 Pending |

### Tier 23 — Depends on Tiers 0–22 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `transf` | 49,864 bytes | options, ast, astalgo, trees, msgs +12 more | 🔲 Pending |

### Tier 24 — Depends on Tiers 0–23 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `vm` | 95,117 bytes | semmacrosanity, msgs, vmdef, vmgen, nimsets +23 more | 🔲 Pending |

### Tier 25 — Depends on Tiers 0–24 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `sem` | 35,019 bytes | ast, options, astalgo, trees, wordrecg +52 more | 🔲 Pending |

### Tier 26 — Depends on Tiers 0–25 (0/1 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `pipelines` | 15,252 bytes | sem, cgen, modulegraphs, ast, llstream +9 more | 🔲 Pending |

### Tier 27 — Depends on Tiers 0–26 (0/2 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `main` | 17,538 bytes | llstream, ast, lexer, syntaxes, options +18 more | 🔲 Pending |
| `scriptconfig` | 8,169 bytes | ast, modules, idents, condsyms, options +8 more | 🔲 Pending |

### Tier 28 — Depends on Tiers 0–27 (0/2 converted)

| Module | Size | Dependencies | Status |
|--------|------|--------------|--------|
| `nim` | 6,157 bytes | commands, options, msgs, extccomp, main +7 more | 🔲 Pending |
| `nimeval` | 6,447 bytes | ast, modules, condsyms, options, llstream +8 more | 🔲 Pending |
