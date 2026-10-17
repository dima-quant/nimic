# Nim Compiler → Nimic: Conversion Queue

> **Generated** by `python -m ncompiler.tools.dependencies` | **Total modules**: 163 | **Converted**: 29 | **Needs rework**: 2 | **Remaining**: 134

## Conversion Rules

1. **Convert in tier order** — only convert a module when all its dependencies are converted.
2. **Include files** (`include x` in an includer) depend on everything their includer imports or includes before the include point, so they are placed after those modules (column *Included from*).
3. **No stubs** unless strictly necessary and no reordering is possible; stand-ins for unconverted dependencies belong to tests only (`nimic_translation_rules.md` §2.1).
4. **Missing `nimic.std` modules** can be created proactively.
5. **Review runs automatically** after every conversion.

## Ready to Convert

Pending modules whose dependencies are all converted, smallest first:

| Module | Tier | Size | Included from |
|---|---|---|---|
| `debugutils` | 4 | 2,192 bytes |  |
| `nimlexbase` | 2 | 5,417 bytes |  |
| `condsyms` | 4 | 6,460 bytes |  |
| `int128` | 0 | 16,767 bytes |  |

## Needs Rework

See `ncompiler/review_core_2026_10_16.md` and `ncompiler/proposals/feature_line_for_line_fidelity.md`.

| Module | Tier | Status | Missing dependencies |
|---|---|---|---|
| `aliasanalysis` | 8 | ⚠️ Needs reconversion | ast |
| `msgs` | 4 | ⚠️ Needs re-review |  |

## Progress by Tier

| Tier | Modules | Converted | Remaining |
|---|---|---|---|
| 0 | 14 | 13 | 1 |
| 1 | 4 | 4 | 0 |
| 2 | 3 | 1 | 2 |
| 3 | 1 | 1 | 0 |
| 4 | 4 | 0 | 4 |
| 5 | 6 | 0 | 6 |
| 6 | 1 | 0 | 1 |
| 7 | 1 | 0 | 1 |
| 8 | 8 | 0 | 8 |
| 9 | 2 | 0 | 2 |
| 10 | 8 | 0 | 8 |
| 11 | 8 | 0 | 8 |
| 12 | 9 | 1 | 8 |
| 13 | 19 | 2 | 17 |
| 14 | 10 | 0 | 10 |
| 15 | 3 | 1 | 2 |
| 16 | 8 | 2 | 6 |
| 17 | 7 | 0 | 7 |
| 18 | 6 | 2 | 4 |
| 19 | 4 | 0 | 4 |
| 20 | 2 | 0 | 2 |
| 21 | 2 | 0 | 2 |
| 22 | 3 | 0 | 3 |
| 23 | 5 | 1 | 4 |
| 24 | 5 | 1 | 4 |
| 25 | 5 | 0 | 5 |
| 26 | 2 | 0 | 2 |
| 27 | 1 | 0 | 1 |
| 28 | 1 | 0 | 1 |
| 29 | 1 | 0 | 1 |
| 30 | 2 | 0 | 2 |
| 31 | 2 | 0 | 2 |
| 32 | 2 | 0 | 2 |
| 33 | 2 | 0 | 2 |
| 34 | 1 | 0 | 1 |
| 35 | 1 | 0 | 1 |

## Full Tier Breakdown

### Tier 0 (13/14 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `bitsets` | 2,754 bytes |  |  | ✅ Converted + Reviewed |
| `btrees` | 5,048 bytes |  |  | ✅ Converted + Reviewed |
| `int128` | 16,767 bytes |  |  | 🔲 Pending |
| `nimpaths` | 2,194 bytes |  |  | ✅ Converted + Reviewed |
| `nodejs` | 347 bytes |  |  | ✅ Converted + Reviewed |
| `nodekinds` | 9,756 bytes |  |  | ✅ Converted |
| `nversion` | 764 bytes |  |  | ✅ Converted + Reviewed |
| `pathutils` | 5,089 bytes |  |  | ✅ Converted + Reviewed |
| `platform` | 14,313 bytes |  |  | ✅ Converted + Reviewed |
| `prefixmatches` | 1,543 bytes |  |  | ✅ Converted + Reviewed |
| `rodutils` | 4,802 bytes |  |  | ✅ Converted + Reviewed |
| `saturate` | 2,189 bytes |  |  | ✅ Converted + Reviewed |
| `sourcemap` | 7,591 bytes |  |  | ✅ Converted + Reviewed |
| `wordrecg` | 8,361 bytes |  |  | ✅ Converted + Reviewed |

### Tier 1 (4/4 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `idents` | 3,574 bytes | wordrecg |  | ✅ Converted + Reviewed |
| `llstream` | 7,399 bytes | pathutils |  | ✅ Converted + Reviewed |
| `packagehandling` | 1,343 bytes | pathutils | options | ✅ Converted + Reviewed |
| `ropes` | 4,172 bytes | pathutils |  | ✅ Converted + Reviewed |

### Tier 2 (1/3 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `cbuilderbase` | 4,152 bytes | int128, ropes |  | 🔲 Pending |
| `lineinfos` | 16,909 bytes | pathutils, ropes |  | ✅ Converted + Reviewed |
| `nimlexbase` | 5,417 bytes | llstream |  | 🔲 Pending |

### Tier 3 (1/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `options` | 42,863 bytes | lineinfos, nimpaths, packagehandling, pathutils, platform +1 more |  | ✅ Converted |

### Tier 4 (0/4 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `astdef` | 48,591 bytes | idents, int128, lineinfos, nodekinds, options +1 more |  | 🔲 Pending |
| `condsyms` | 6,460 bytes | lineinfos, options |  | 🔲 Pending |
| `debugutils` | 2,192 bytes | options |  | 🔲 Pending |
| `msgs` | 28,370 bytes | lineinfos, options, pathutils, ropes |  | ⚠️ Needs re-review |

### Tier 5 (0/6 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `deps` | 18,153 bytes | lineinfos, msgs, options, pathutils |  | 🔲 Pending |
| `gorgeimpl` | 2,279 bytes | lineinfos, msgs, options, pathutils |  | 🔲 Pending |
| `lexer` | 48,749 bytes | idents, lineinfos, llstream, msgs, nimlexbase +4 more |  | 🔲 Pending |
| `nimblecmd` | 5,510 bytes | lineinfos, msgs, options, pathutils |  | 🔲 Pending |
| `tccgen` | 2,914 bytes | lineinfos, msgs, options |  | 🔲 Pending |
| `typekeys` | 8,978 bytes | astdef, idents, lineinfos, msgs, options |  | 🔲 Pending |

### Tier 6 (0/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ast2nif` | 60,319 bytes | astdef, idents, lineinfos, msgs, options +2 more |  | 🔲 Pending |

### Tier 7 (0/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ast` | 53,120 bytes | ast2nif, astdef, idents, int128, lineinfos +3 more |  | 🔲 Pending |

### Tier 8 (0/8 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `aliasanalysis` | 4,352 bytes | ast |  | ⚠️ Needs reconversion |
| `astmsgs` | 1,970 bytes | ast, msgs, options |  | 🔲 Pending |
| `astyaml` | 5,843 bytes | ast, lineinfos, msgs, options, rodutils |  | 🔲 Pending |
| `layouter` | 19,550 bytes | ast, idents, lexer, lineinfos, llstream +3 more |  | 🔲 Pending |
| `packages` | 1,799 bytes | ast, idents, lineinfos, msgs, options +1 more |  | 🔲 Pending |
| `parser` | 86,112 bytes | ast, idents, lexer, lineinfos, llstream +3 more |  | 🔲 Pending |
| `suggestsymdb` | 7,101 bytes | ast, lineinfos, msgs |  | 🔲 Pending |
| `trees` | 9,171 bytes | ast, idents, wordrecg |  | 🔲 Pending |

### Tier 9 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `astalgo` | 19,737 bytes | ast, astyaml, idents, lineinfos, msgs +2 more |  | 🔲 Pending |
| `renderer` | 72,612 bytes | ast, idents, lexer, lineinfos, msgs +3 more |  | 🔲 Pending |

### Tier 10 (0/8 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `dfa` | 13,105 bytes | aliasanalysis, ast, lineinfos, renderer |  | 🔲 Pending |
| `evaltempl` | 8,317 bytes | ast, astalgo, idents, lineinfos, msgs +3 more |  | 🔲 Pending |
| `filters` | 2,779 bytes | ast, idents, llstream, msgs, options +2 more |  | 🔲 Pending |
| `layeredtable` | 3,220 bytes | ast, astalgo |  | 🔲 Pending |
| `modulegraphs` | 29,119 bytes | ast, ast2nif, astalgo, btrees, idents +8 more |  | 🔲 Pending |
| `modulepaths` | 4,195 bytes | ast, idents, lineinfos, msgs, options +2 more |  | 🔲 Pending |
| `optimizer` | 8,219 bytes | ast, idents, renderer, trees |  | 🔲 Pending |
| `renderverbatim` | 4,389 bytes | ast, astalgo, msgs, options, renderer |  | 🔲 Pending |

### Tier 11 (0/8 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `cgendata` | 11,199 bytes | ast, cbuilderbase, lineinfos, modulegraphs, options +2 more |  | 🔲 Pending |
| `depends` | 3,135 bytes | ast, lineinfos, modulegraphs, msgs, options +2 more |  | 🔲 Pending |
| `extccomp` | 47,774 bytes | condsyms, lineinfos, modulepaths, msgs, options +3 more |  | 🔲 Pending |
| `filter_tmpl` | 6,791 bytes | ast, filters, lineinfos, llstream, msgs +2 more |  | 🔲 Pending |
| `mangleutils` | 1,570 bytes | ast, modulegraphs |  | 🔲 Pending |
| `pipelineutils` | 1,133 bytes | ast, lineinfos, modulegraphs, msgs, options +2 more |  | 🔲 Pending |
| `sizealignoffsetimpl` | 17,025 bytes | ast, int128, lineinfos, modulegraphs, msgs +3 more | types | 🔲 Pending |
| `vmdef` | 11,634 bytes | ast, idents, lineinfos, modulegraphs, options |  | 🔲 Pending |

### Tier 12 (1/9 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `cbuilderexprs` | 6,794 bytes | ast, cbuilderbase, cgendata | cgen | ✅ Converted |
| `ccgmerge_unused` | 8,140 bytes | ast, cgendata, llstream, modulegraphs, nimlexbase +4 more |  | 🔲 Pending |
| `commands` | 53,094 bytes | ast, condsyms, extccomp, lineinfos, msgs +6 more |  | 🔲 Pending |
| `macrocacheimpl` | 1,375 bytes | ast, lineinfos, vmdef |  | 🔲 Pending |
| `syntaxes` | 4,730 bytes | ast, filter_tmpl, filters, idents, lexer +7 more |  | 🔲 Pending |
| `types` | 62,513 bytes | ast, astalgo, astmsgs, int128, lineinfos +8 more |  | 🔲 Pending |
| `vmconv` | 1,723 bytes | ast, astalgo, idents, lineinfos, vmdef |  | 🔲 Pending |
| `vmhooks` | 2,334 bytes | ast, btrees, lineinfos, options, pathutils +2 more | vm | 🔲 Pending |
| `vmprofiler` | 1,366 bytes | ast, lineinfos, msgs, options, vmdef |  | 🔲 Pending |

### Tier 13 (2/19 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `aliases` | 6,452 bytes | ast, astalgo, trees, types |  | 🔲 Pending |
| `cbuilderdecls` | 22,463 bytes | ast, astalgo, cbuilderbase, cbuilderexprs, cgendata +7 more | cgen | 🔲 Pending |
| `cbuilderstmts` | 9,403 bytes | ast, astalgo, cbuilderbase, cbuilderexprs, cgendata +1 more | cgen | ✅ Converted |
| `ccgutils` | 5,474 bytes | ast, cgendata, mangleutils, msgs, options +5 more |  | 🔲 Pending |
| `errorhandling` | 2,419 bytes | ast, options, renderer, types |  | 🔲 Pending |
| `evalffi` | 17,708 bytes | ast, lineinfos, msgs, options, types |  | 🔲 Pending |
| `expanddefaults` | 4,655 bytes | ast, lineinfos, types |  | 🔲 Pending |
| `isolation_check` | 7,161 bytes | ast, renderer, types |  | 🔲 Pending |
| `jstypes` | 6,158 bytes | ast, idents, lineinfos, modulegraphs, msgs +4 more | jsgen | ✅ Converted + Reviewed |
| `magicsys` | 6,205 bytes | ast, idents, lineinfos, modulegraphs, msgs +2 more |  | 🔲 Pending |
| `nifgen` | 49,570 bytes | ast, astalgo, idents, lineinfos, modulegraphs +4 more |  | 🔲 Pending |
| `nimsets` | 4,476 bytes | ast, astalgo, bitsets, lineinfos, options +1 more |  | 🔲 Pending |
| `parampatterns` | 12,813 bytes | ast, idents, msgs, options, renderer +3 more |  | 🔲 Pending |
| `reorder` | 13,966 bytes | ast, idents, lineinfos, modulegraphs, modulepaths +4 more |  | 🔲 Pending |
| `sighashes` | 15,004 bytes | ast, modulegraphs, msgs, options, pathutils +2 more |  | 🔲 Pending |
| `treetab` | 3,672 bytes | ast, types |  | 🔲 Pending |
| `typesrenderer` | 5,110 bytes | ast, renderer, types |  | 🔲 Pending |
| `vmdeps` | 13,802 bytes | ast, idents, lineinfos, msgs, options +2 more |  | 🔲 Pending |
| `vmmarshal` | 9,895 bytes | ast, astalgo, idents, lineinfos, msgs +2 more |  | 🔲 Pending |

### Tier 14 (0/10 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `debuginfo` | 2,052 bytes | sighashes |  | 🔲 Pending |
| `docgen` | 78,864 bytes | ast, idents, lexer, lineinfos, msgs +12 more |  | 🔲 Pending |
| `enumtostr` | 3,800 bytes | ast, idents, lineinfos, magicsys, modulegraphs |  | 🔲 Pending |
| `guards` | 37,907 bytes | ast, astalgo, idents, int128, lineinfos +9 more |  | 🔲 Pending |
| `lowerings` | 12,401 bytes | ast, astalgo, idents, lineinfos, magicsys +4 more |  | 🔲 Pending |
| `modules` | 2,488 bytes | ast, idents, lexer, lineinfos, magicsys +5 more |  | 🔲 Pending |
| `nilcheck` | 44,931 bytes | ast, idents, lineinfos, msgs, options +2 more |  | 🔲 Pending |
| `semfold` | 31,536 bytes | ast, commands, idents, lineinfos, magicsys +9 more |  | 🔲 Pending |
| `semmacrosanity` | 6,152 bytes | ast, msgs, nimsets, options, trees +1 more |  | 🔲 Pending |
| `vmops` | 14,897 bytes | ast, btrees, gorgeimpl, idents, int128 +9 more | vm | 🔲 Pending |

### Tier 15 (1/3 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ccgliterals` | 13,946 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +12 more | cgen | ✅ Converted |
| `docgen2` | 2,211 bytes | ast, docgen, lineinfos, modulegraphs, msgs +3 more |  | 🔲 Pending |
| `semdata` | 31,097 bytes | ast, astalgo, idents, layeredtable, lineinfos +11 more |  | 🔲 Pending |

### Tier 16 (2/8 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ccgtrav` | 8,380 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +14 more | ccgtypes | ✅ Converted |
| `liftdestructors` | 57,474 bytes | ast, ccgutils, idents, lineinfos, lowerings +9 more |  | 🔲 Pending |
| `linter` | 6,704 bytes | ast, astmsgs, idents, lineinfos, modulegraphs +5 more |  | 🔲 Pending |
| `lookups` | 33,183 bytes | ast, astalgo, astmsgs, idents, lineinfos +7 more |  | 🔲 Pending |
| `pluginsupport` | 943 bytes | ast, idents, semdata |  | 🔲 Pending |
| `semtypinst` | 34,068 bytes | ast, astalgo, layeredtable, lineinfos, magicsys +6 more |  | 🔲 Pending |
| `sinkparameter_inference` | 2,393 bytes | ast, astalgo, guards, idents, lineinfos +7 more | sempass2 | ✅ Converted + Reviewed |
| `typeallowed` | 10,737 bytes | ast, options, renderer, semdata, types |  | 🔲 Pending |

### Tier 17 (0/7 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ccgtypes` | 84,300 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +19 more | cgen | 🔲 Pending |
| `concepts` | 22,764 bytes | ast, idents, layeredtable, lineinfos, lookups +4 more |  | 🔲 Pending |
| `procfind` | 3,474 bytes | ast, astalgo, lookups, msgs, semdata +2 more |  | 🔲 Pending |
| `semstrictfuncs` | 1,688 bytes | aliasanalysis, ast, renderer, trees, typeallowed |  | 🔲 Pending |
| `spawn` | 19,073 bytes | ast, idents, liftdestructors, lowerings, magicsys +6 more |  | 🔲 Pending |
| `suggest` | 36,588 bytes | ast, astalgo, idents, lexer, lineinfos +10 more | sigmatch | 🔲 Pending |
| `varpartitions` | 37,399 bytes | ast, isolation_check, lineinfos, modulegraphs, msgs +5 more |  | 🔲 Pending |

### Tier 18 (2/6 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ccgcalls` | 33,985 bytes | aliasanalysis, aliases, ast, astalgo, cbuilderbase +15 more | cgen | 🔲 Pending |
| `ccgreset` | 4,536 bytes | ast, cbuilderbase, cbuilderexprs, cbuilderstmts, ccgliterals +12 more | cgen | ✅ Converted |
| `ccgthreadvars` | 2,429 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +9 more | cgen | ✅ Converted |
| `injectdestructors` | 54,800 bytes | aliasanalysis, ast, astalgo, dfa, idents +15 more |  | 🔲 Pending |
| `semparallel` | 17,154 bytes | ast, astalgo, guards, idents, lineinfos +9 more |  | 🔲 Pending |
| `sigmatch` | 122,192 bytes | ast, astalgo, concepts, idents, layeredtable +16 more |  | 🔲 Pending |

### Tier 19 (0/4 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `importer` | 14,526 bytes | ast, idents, lineinfos, lookups, modulegraphs +6 more |  | 🔲 Pending |
| `patterns` | 10,598 bytes | aliases, ast, idents, parampatterns, semdata +3 more |  | 🔲 Pending |
| `pragmas` | 52,923 bytes | ast, astalgo, condsyms, extccomp, idents +15 more |  | 🔲 Pending |
| `semcall` | 44,523 bytes | ast, astalgo, astmsgs, idents, int128 +14 more | sem | 🔲 Pending |

### Tier 20 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `liftlocals` | 2,355 bytes | ast, idents, lineinfos, lowerings, msgs +5 more |  | 🔲 Pending |
| `pushpoppragmas` | 2,049 bytes | ast, idents, lineinfos, options, pragmas +3 more |  | 🔲 Pending |

### Tier 21 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ccgstmts` | 71,794 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderexprs +20 more | cgen | 🔲 Pending |
| `sempass2` | 71,677 bytes | ast, astalgo, errorhandling, guards, idents +19 more |  | 🔲 Pending |

### Tier 22 (0/3 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `ccgexprs` | 163,248 bytes | aliases, ast, astalgo, astmsgs, bitsets +26 more | cgen | 🔲 Pending |
| `cgmeth` | 11,076 bytes | ast, astalgo, idents, lineinfos, magicsys +6 more |  | 🔲 Pending |
| `seminst` | 18,919 bytes | ast, astalgo, extccomp, idents, int128 +16 more | sem | 🔲 Pending |

### Tier 23 (1/5 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `closureiters` | 51,781 bytes | ast, idents, lambdalifting, lineinfos, lowerings +5 more |  | 🔲 Pending |
| `inliner` | 4,217 bytes | ast, astalgo, cbuilderbase, cbuilderdecls, cbuilderstmts +8 more | cgen | ✅ Converted + Reviewed |
| `lambdalifting` | 38,285 bytes | ast, astalgo, idents, liftdestructors, lineinfos +9 more |  | 🔲 Pending |
| `transf` | 49,864 bytes | ast, astalgo, cgmeth, closureiters, idents +12 more |  | 🔲 Pending |
| `vtables` | 6,703 bytes | ast, cgmeth, lineinfos, magicsys, modulegraphs +2 more |  | 🔲 Pending |

### Tier 24 (1/5 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `cgen` | 102,559 bytes | aliases, ast, astalgo, astmsgs, bitsets +44 more |  | 🔲 Pending |
| `hlo` | 3,811 bytes | ast, astalgo, evaltempl, idents, int128 +12 more | sem | ✅ Converted + Reviewed |
| `jsgen` | 110,140 bytes | ast, astmsgs, cgmeth, idents, injectdestructors +19 more |  | 🔲 Pending |
| `semtypes` | 106,643 bytes | ast, astalgo, concepts, enumtostr, idents +29 more | sem | 🔲 Pending |
| `vmgen` | 86,949 bytes | ast, astmsgs, evalffi, lineinfos, lowerings +10 more |  | 🔲 Pending |

### Tier 25 (0/5 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `nifbackend` | 5,570 bytes | ast, ast2nif, cgen, cgendata, extccomp +8 more |  | 🔲 Pending |
| `semfields` | 6,625 bytes | ast, astalgo, idents, int128, layeredtable +15 more | semstmts | 🔲 Pending |
| `semgnrc` | 24,878 bytes | ast, astalgo, idents, int128, lineinfos +14 more | sem | 🔲 Pending |
| `semtempl` | 31,451 bytes | ast, astalgo, idents, int128, lineinfos +18 more | sem | 🔲 Pending |
| `vm` | 95,117 bytes | ast, btrees, evalffi, evaltempl, gorgeimpl +23 more |  | 🔲 Pending |

### Tier 26 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `semmagic` | 27,519 bytes | aliases, ast, astalgo, idents, int128 +22 more | semexprs | 🔲 Pending |
| `semstmts` | 117,249 bytes | ast, astalgo, cgmeth, hlo, idents +27 more | sem | 🔲 Pending |

### Tier 27 (0/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `semobjconstr` | 23,372 bytes | ast, astalgo, astmsgs, idents, int128 +18 more | semexprs | 🔲 Pending |

### Tier 28 (0/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `semexprs` | 142,092 bytes | ast, astalgo, astmsgs, evaltempl, idents +35 more | sem | 🔲 Pending |

### Tier 29 (0/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `sem` | 35,019 bytes | aliases, ast, astalgo, astmsgs, cgmeth +51 more |  | 🔲 Pending |

### Tier 30 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `passes` | 8,340 bytes | ast, idents, lineinfos, llstream, modulegraphs +10 more |  | 🔲 Pending |
| `pipelines` | 15,252 bytes | ast, ast2nif, cgen, cgendata, depends +25 more |  | 🔲 Pending |

### Tier 31 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `passaux` | 942 bytes | ast, lineinfos, modulegraphs, msgs, options +1 more |  | 🔲 Pending |
| `scriptconfig` | 8,169 bytes | ast, commands, condsyms, idents, llstream +8 more |  | 🔲 Pending |

### Tier 32 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `nimconf` | 11,746 bytes | ast, commands, idents, lexer, lineinfos +6 more |  | 🔲 Pending |
| `nimeval` | 6,447 bytes | ast, condsyms, idents, lineinfos, llstream +8 more |  | 🔲 Pending |

### Tier 33 (0/2 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `cmdlinehelper` | 3,134 bytes | commands, condsyms, extccomp, idents, lineinfos +5 more |  | 🔲 Pending |
| `main` | 17,538 bytes | ast, cgen, condsyms, depends, deps +18 more |  | 🔲 Pending |

### Tier 34 (0/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `nim` | 6,157 bytes | cmdlinehelper, commands, extccomp, idents, lineinfos +7 more |  | 🔲 Pending |

### Tier 35 (0/1 converted)

| Module | Size | Dependencies | Included from | Status |
|---|---|---|---|---|
| `index` | 478 bytes | nim |  | 🔲 Pending |
