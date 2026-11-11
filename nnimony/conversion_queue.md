# nimony → nnimony: Conversion Queue

> **Generated** by `python -m nnimony.tools.queue` from the nimony clone at `2c5b3dca1466` (pinned in `nnimony/tools/queue.py`). The plan: `ncompiler/conversion_plan.md`.

## Conversion Rules

1. **Convert the current component in tier order**, a module once the nimony modules it imports are converted.
2. **Mirror the path:** `src/lib/bitabs.nim` → `nnimony/lib/bitabs.py`; the module records its source commit in its header (`# source: nimony@<sha>:src/lib/bitabs.nim`).
3. **Missing std shims** (`src/nimic/std/`) are created as part of the conversion.
4. **`when defined(nimony)`** branches are converted like any `when` (`if comptime(...)`); Python runs the host-Nim build, where they are inactive.
5. **Review runs after every conversion**; verification: `tests/verify_transpiled.py`.

## Components

| Component | Role | Lines | State |
|---|---|---|---|
| `src/lib` | NIF libraries: the foundation of every nimony tool | 12,366 | current |
| `src/nifler2` | the parser (Nim -> NIF), a nimony program generated from a grammar (converted by nimicgen) | 7,026 | current |
| `src/lengc` | the C and LLVM backend (NIF -> C, LLVM IR), converted by nimicgen | 24,322 | current |
| `src/hexer` | lowering (shoggoth) | 25,002 | later |
| `src/nimony` | semantic checking (nimsem) and the driver | 52,935 | later |

## Ready to Convert (`src/lib`)

| Module | Size | Std imports (✗ = no nimic shim yet) | Agent |
|---|---|---|---|

## All modules of `src/lib` (36/36 converted, 3 legacy)

| Module | Tier | Size | Depends on | Std imports | Status |
|---|---|---|---|---|---|
| `lib/argsfinder` | 0 | 4,466 bytes |  | assertions, os, parseopt, strutils, syncio | ✅ Converted |
| `lib/bitabs` | 0 | 10,085 bytes |  | assertions, hashes | ✅ Converted |
| `lib/comesfrom` | 0 | 5,495 bytes |  |  | ✅ Converted |
| `lib/compat2` | 0 | 3,639 bytes |  | paths, tables | ✅ Converted |
| `lib/docpaths` | 0 | 3,130 bytes |  | os, strutils | ✅ Converted |
| `lib/intrinsics` | 0 | 83,257 bytes |  |  | ✅ Converted |
| `lib/lineinfos` | 0 | 5,345 bytes |  | assertions, hashes | ✅ Converted |
| `lib/nifroles` | 0 | 3,979 bytes |  |  | ✅ Converted |
| `lib/nimversion` | 0 | 2,742 bytes |  | syncio | ✅ Converted |
| `lib/platform` | 0 | 16,405 bytes |  | strutils, syncio | ✅ Converted |
| `lib/stringtrees` | 0 | 2,963 bytes |  | assertions | ✅ Converted |
| `lib/stringviews` | 0 | 2,238 bytes |  | hashes | ✅ Converted |
| `lib/symparser` | 0 | 9,123 bytes |  | assertions | ✅ Converted |
| `lib/tinyhashes` | 0 | 817 bytes |  |  | ✅ Converted |
| `lib/tooldirs` | 0 | 1,265 bytes |  | os, strutils | ✅ Converted |
| `lib/treemangler` | 0 | 5,308 bytes |  | assertions, formatfloat, hashes, strutils, syncio, tables | ✅ Converted |
| `lib/vfs` | 0 | 14,386 bytes |  | atomics, memfiles, os, syncio, times | ✅ Converted |
| `models/tags` | 0 | 14,086 bytes |  |  | ✅ Converted |
| `lib/filelinecache` | 1 | 2,128 bytes | lib/compat2 | hashes, strutils, syncio, tables | ✅ Converted |
| `lib/keymatcher` | 1 | 5,934 bytes | lib/stringtrees, lib/stringviews | assertions, macros (legacy: expand the calls) | ⛔ Legacy: macro machinery (`declareMatcher`), called only by its own tests; macros are legacy |
| `lib/legacy/nif26reader` | 1 | 13,861 bytes | lib/stringviews, lib/vfs | assertions, memfiles, parseutils | ⛔ Legacy: NIF26 reader, used only by the nif26 -> nif27 migration tool, which nimic doesn't need (also not for a newer nimony) |
| `lib/nifbuilder` | 1 | 16,576 bytes | lib/vfs | assertions, formatfloat, math, strutils, syncio | ✅ Converted |
| `lib/nifcore` | 1 | 112,398 bytes | lib/bitabs, lib/lineinfos, lib/nifroles | assertions, formatfloat, hashes | ✅ Converted |
| `models/callconv_tags` | 1 | 921 bytes | models/tags |  | ✅ Converted |
| `models/leng_tags` | 1 | 24,126 bytes | models/tags |  | ✅ Converted |
| `models/nifindex_tags` | 1 | 4,542 bytes | models/tags |  | ✅ Converted |
| `lib/bif` | 2 | 53,014 bytes | lib/compat2, lib/nifcore, lib/vfs | assertions, strutils, syncio, varints | ✅ Converted |
| `lib/htmlbuilder` | 2 | 4,222 bytes | lib/nifbuilder |  | ✅ Converted |
| `lib/lengiface` | 2 | 3,852 bytes | lib/nifbuilder, lib/nifcore, lib/vfs | assertions, formatfloat, sha1, syncio | ✅ Converted |
| `lib/nifcdecl` | 2 | 10,477 bytes | lib/nifcore, models/callconv_tags, models/leng_tags, models/tags | assertions | ✅ Converted |
| `lib/nifreader` | 2 | 46,670 bytes | lib/nifcore, lib/stringviews, lib/vfs | assertions, memfiles, parseutils | ✅ Converted |
| `lib/nifcoreparse` | 3 | 26,586 bytes | lib/comesfrom, lib/lineinfos, lib/nifbuilder, lib/nifcore, lib/nifreader, lib/stringviews | assertions, math, strutils, syncio | ✅ Converted |
| `lib/foreignmodules` | 4 | 7,572 bytes | lib/bif, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/stringviews | tables | ✅ Converted |
| `lib/nifpools` | 4 | 22,429 bytes | lib/comesfrom, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/nifroles, lib/vfs, models/tags | assertions | ✅ Converted |
| `lib/nifqueries` | 4 | 2,547 bytes | lib/nifcore, lib/nifcoreparse | assertions | ✅ Converted |
| `lib/nifchecksums` | 5 | 2,565 bytes | lib/bitabs, lib/nifpools, lib/nifreader | formatfloat, sha1 | ✅ Converted |
| `lib/nifprelude` | 5 | 372 bytes | lib/bitabs, lib/nifbuilder, lib/nifpools, lib/nifreader, lib/nifroles |  | ✅ Converted |
| `lib/nifstreams` | 5 | 8,456 bytes | lib/lineinfos, lib/nifpools, lib/nifreader | tables | ⛔ Legacy: the classic NIF streaming surface of the Nim 2 compiler's IC modules; no nimony tool imports it and nimony rejects it (unsynchronized global `lineMan`); taken out 2026-11-07 (user) |
| `lib/nifindexes` | 6 | 12,624 bytes | lib/bitabs, lib/compat2, lib/lineinfos, lib/nifchecksums, lib/nifcoreparse, lib/nifpools, lib/nifreader, lib/stringviews, lib/symparser, lib/vfs, models/nifindex_tags, models/tags | assertions, hashes, os, sha1, strutils, syncio, tables | ✅ Converted |

## Ready to Convert (`src/nifler2`)

| Module | Size | Std imports (✗ = no nimic shim yet) | Agent |
|---|---|---|---|

## All modules of `src/nifler2` (23/23 converted, 2 covered otherwise)

| Module | Tier | Size | Depends on | Std imports | Status |
|---|---|---|---|---|---|
| `lib/bitabs` | 0 | 10,085 bytes |  | assertions, hashes | ✅ Converted |
| `lib/comesfrom` | 0 | 5,495 bytes |  |  | ✅ Converted |
| `lib/lineinfos` | 0 | 5,345 bytes |  | assertions, hashes | ✅ Converted |
| `lib/nifroles` | 0 | 3,979 bytes |  |  | ✅ Converted |
| `lib/stringviews` | 0 | 2,238 bytes |  | hashes | ✅ Converted |
| `lib/vfs` | 0 | 14,386 bytes |  | atomics, memfiles, os, syncio, times | ✅ Converted |
| `models/tags` | 0 | 14,086 bytes |  |  | ✅ Converted |
| `nifler2/deps/parsegen` | 0 | 74,222 bytes |  | plugins ✗, sets, strutils, tables | 🔌 Plugin: run at its call sites (plugexpand expands each `grammar:` call, nimicgen converts the expansion: nimgrammar, tests/mini) |
| `nifler2/nimlexer` | 0 | 39,620 bytes |  | rex ✗ | ✅ Converted |
| `lib/nifbuilder` | 1 | 16,576 bytes | lib/vfs | assertions, formatfloat, math, strutils, syncio | ✅ Converted |
| `lib/nifcore` | 1 | 112,398 bytes | lib/bitabs, lib/lineinfos, lib/nifroles | assertions, formatfloat, hashes | ✅ Converted |
| `models/nifler_tags` | 1 | 9,918 bytes | models/tags |  | ✅ Converted |
| `nifler2/tests/tnimlexer` | 1 | 4,738 bytes | nifler2/nimlexer | assertions, syncio | ☑️ Covered: its cases are nimlexer's self-test (it doesn't build at the pin: nimony rejects its unsynchronized global `failures`) |
| `lib/nifreader` | 2 | 46,670 bytes | lib/nifcore, lib/stringviews, lib/vfs | assertions, memfiles, parseutils | ✅ Converted |
| `nifler2/tests/minirt` | 2 | 7,413 bytes | models/nifler_tags | strutils, syncio | ✅ Converted |
| `lib/nifcoreparse` | 3 | 26,586 bytes | lib/comesfrom, lib/lineinfos, lib/nifbuilder, lib/nifcore, lib/nifreader, lib/stringviews | assertions, math, strutils, syncio | ✅ Converted |
| `nifler2/tests/mini` | 3 | 1,408 bytes | nifler2/tests/minirt |  | ✅ Converted |
| `lib/nifpools` | 4 | 22,429 bytes | lib/comesfrom, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/nifroles, lib/vfs, models/tags | assertions | ✅ Converted |
| `nifler2/tests/tmini` | 4 | 2,851 bytes | nifler2/tests/mini | strutils, syncio | ✅ Converted |
| `nifler2/linkedtok` | 5 | 7,585 bytes | lib/nifpools | assertions | ✅ Converted |
| `nifler2/parserrt` | 6 | 47,805 bytes | lib/nifcore, lib/nifpools, models/nifler_tags, nifler2/linkedtok, nifler2/nimlexer | parseutils, syncio | ✅ Converted |
| `nifler2/niflerout` | 7 | 12,804 bytes | lib/nifbuilder, lib/nifpools, nifler2/parserrt | assertions, syncio | ✅ Converted |
| `nifler2/nimgrammar` | 7 | 59,856 bytes | lib/nifcore, nifler2/parserrt | strutils | ✅ Converted |
| `nifler2/filters` | 8 | 14,786 bytes | nifler2/nimgrammar | strutils, syncio | ✅ Converted |
| `nifler2/nifler2` | 9 | 3,679 bytes | nifler2/filters, nifler2/niflerout, nifler2/nimgrammar | assertions, os, parseopt, syncio | ✅ Converted |

## Ready to Convert (`src/lengc`)

| Module | Size | Std imports (✗ = no nimic shim yet) | Agent |
|---|---|---|---|
| `nimony/langmodes` | 786 bytes |  |  |
| `nimony/nif_annotations` | 2,201 bytes |  |  |
| `models/finalir_tags` | 2,373 bytes |  |  |
| `gear2/modnames` | 3,747 bytes | os |  |
| `hexer/passes` | 4,294 bytes | monotimes, os, strutils, syncio, times |  |
| `nimony/features` | 5,168 bytes |  |  |
| `nimony/reporters` | 5,320 bytes | assertions, os, sets, strutils, syncio, terminal |  |
| `hexer/stringcases` | 6,058 bytes |  |  |
| `nimony/xints` | 8,212 bytes |  |  |
| `nimony/nifconfig` | 17,889 bytes | os, sets, strutils |  |
| `models/nimony_tags` | 54,962 bytes |  |  |

## All modules of `src/lengc` (49/107 converted, 24 covered otherwise)

| Module | Tier | Size | Depends on | Std imports | Status |
|---|---|---|---|---|---|
| `hexer/stringcases` | 0 | 6,058 bytes |  |  | 🔲 Pending |
| `lengc/cprelude` | 0 | 13,985 bytes |  |  | ✅ Converted |
| `lengc/genexprs` | 0 | 17,042 bytes |  |  | ✅ Converted |
| `lengc/genstmts` | 0 | 15,729 bytes |  |  | ✅ Converted |
| `lengc/gentypes` | 0 | 22,667 bytes |  |  | ✅ Converted |
| `lengc/llvmdebug` | 0 | 31,974 bytes |  |  | ✅ Converted |
| `lengc/llvmgenexprs` | 0 | 49,473 bytes |  |  | ✅ Converted |
| `lengc/llvmgenstmts` | 0 | 20,930 bytes |  |  | ✅ Converted |
| `lengc/llvmgentypes` | 0 | 33,199 bytes |  |  | ✅ Converted |
| `lengc/llvmirmodel` | 0 | 11,632 bytes |  |  | ✅ Converted |
| `lengc/mangler` | 0 | 2,852 bytes |  | assertions | ✅ Converted |
| `lengc/noptions` | 0 | 1,511 bytes |  | syncio, tables | ✅ Converted |
| `lib/argsfinder` | 0 | 4,466 bytes |  | assertions, os, parseopt, strutils, syncio | ✅ Converted |
| `lib/bitabs` | 0 | 10,085 bytes |  | assertions, hashes | ✅ Converted |
| `lib/comesfrom` | 0 | 5,495 bytes |  |  | ✅ Converted |
| `lib/compat2` | 0 | 3,639 bytes |  | paths, tables | ✅ Converted |
| `lib/intrinsics` | 0 | 83,257 bytes |  |  | ✅ Converted |
| `lib/lineinfos` | 0 | 5,345 bytes |  | assertions, hashes | ✅ Converted |
| `lib/nifroles` | 0 | 3,979 bytes |  |  | ✅ Converted |
| `lib/nimversion` | 0 | 2,742 bytes |  | syncio | ✅ Converted |
| `lib/platform` | 0 | 16,405 bytes |  | strutils, syncio | ✅ Converted |
| `lib/stringtrees` | 0 | 2,963 bytes |  | assertions | ✅ Converted |
| `lib/stringviews` | 0 | 2,238 bytes |  | hashes | ✅ Converted |
| `lib/symparser` | 0 | 9,123 bytes |  | assertions | ✅ Converted |
| `lib/tinyhashes` | 0 | 817 bytes |  |  | ✅ Converted |
| `lib/treemangler` | 0 | 5,308 bytes |  | assertions, formatfloat, hashes, strutils, syncio, tables | ✅ Converted |
| `lib/vfs` | 0 | 14,386 bytes |  | atomics, memfiles, os, syncio, times | ✅ Converted |
| `models/tags` | 0 | 14,086 bytes |  |  | ✅ Converted |
| `nimony/features` | 0 | 5,168 bytes |  |  | 🔲 Pending |
| `nimony/langmodes` | 0 | 786 bytes |  |  | 🔲 Pending |
| `nimony/nif_annotations` | 0 | 2,201 bytes |  |  | 🔲 Pending |
| `nimony/xints` | 0 | 8,212 bytes |  |  | 🔲 Pending |
| `gear2/modnames` | 1 | 3,747 bytes | lib/compat2, lib/tinyhashes | os | 🔲 Pending |
| `lengc/llvmserializer` | 1 | 14,619 bytes | lengc/llvmirmodel |  | ✅ Converted |
| `lengc/shoggoth/trackers` | 1 | 38,798 bytes | lib/compat2 | assertions, hashes, sets, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lib/filelinecache` | 1 | 2,128 bytes | lib/compat2 | hashes, strutils, syncio, tables | ✅ Converted |
| `lib/nifbuilder` | 1 | 16,576 bytes | lib/vfs | assertions, formatfloat, math, strutils, syncio | ✅ Converted |
| `lib/nifcore` | 1 | 112,398 bytes | lib/bitabs, lib/lineinfos, lib/nifroles | assertions, formatfloat, hashes | ✅ Converted |
| `models/callconv_tags` | 1 | 921 bytes | models/tags |  | ✅ Converted |
| `models/finalir_tags` | 1 | 2,373 bytes | models/tags |  | 🔲 Pending |
| `models/leng_tags` | 1 | 24,126 bytes | models/tags |  | ✅ Converted |
| `models/nifindex_tags` | 1 | 4,542 bytes | models/tags |  | ✅ Converted |
| `models/nimony_tags` | 1 | 54,962 bytes | models/tags |  | 🔲 Pending |
| `lib/bif` | 2 | 53,014 bytes | lib/compat2, lib/nifcore, lib/vfs | assertions, strutils, syncio, varints | ✅ Converted |
| `lib/lengiface` | 2 | 3,852 bytes | lib/nifbuilder, lib/nifcore, lib/vfs | assertions, formatfloat, sha1, syncio | ✅ Converted |
| `lib/nifcdecl` | 2 | 10,477 bytes | lib/nifcore, models/callconv_tags, models/leng_tags, models/tags | assertions | ✅ Converted |
| `lib/nifreader` | 2 | 46,670 bytes | lib/nifcore, lib/stringviews, lib/vfs | assertions, memfiles, parseutils | ✅ Converted |
| `lib/nifcoreparse` | 3 | 26,586 bytes | lib/comesfrom, lib/lineinfos, lib/nifbuilder, lib/nifcore, lib/nifreader, lib/stringviews | assertions, math, strutils, syncio | ✅ Converted |
| `lengc/shoggoth/accesspaths` | 4 | 9,141 bytes | lib/nifcdecl, lib/nifcoreparse |  | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/patchsets` | 4 | 4,861 bytes | lib/nifcoreparse | assertions, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/patextract` | 4 | 7,692 bytes | gear2/modnames, lib/argsfinder, lib/compat2, lib/nifcoreparse | assertions, dirs, os, osproc, parseopt, paths, strutils, syncio | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/vmrewriter` | 4 | 40,679 bytes | lib/compat2, lib/nifcoreparse | algorithm, assertions, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lib/foreignmodules` | 4 | 7,572 bytes | lib/bif, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/stringviews | tables | ✅ Converted |
| `lib/nifpools` | 4 | 22,429 bytes | lib/comesfrom, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/nifroles, lib/vfs, models/tags | assertions | ✅ Converted |
| `hexer/passes` | 5 | 4,294 bytes | lib/nifpools | monotimes, os, strutils, syncio, times | 🔲 Pending |
| `lengc/nifmodules` | 5 | 16,264 bytes | lengc/noptions, lib/bif, lib/foreignmodules, lib/nifcdecl, lib/nifcoreparse, lib/nifreader, lib/symparser | assertions, os, syncio, tables | ✅ Converted |
| `lengc/shoggoth/tailcalls` | 5 | 17,257 bytes | lengc/shoggoth/patchsets, lib/nifcdecl, lib/nifcoreparse | tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/unswitch` | 5 | 34,946 bytes | lengc/shoggoth/patchsets, lib/nifcdecl, lib/nifcoreparse, models/tags | assertions, sets, strutils, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/vectorizer` | 5 | 64,898 bytes | lengc/shoggoth/patchsets, lib/compat2, lib/nifcdecl, lib/nifcoreparse, models/tags | assertions, sets, strutils, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lib/nifchecksums` | 5 | 2,565 bytes | lib/bitabs, lib/nifpools, lib/nifreader | formatfloat, sha1 | ✅ Converted |
| `lib/nifprelude` | 5 | 372 bytes | lib/bitabs, lib/nifbuilder, lib/nifpools, lib/nifreader, lib/nifroles |  | ✅ Converted |
| `nimony/identstyle` | 5 | 5,060 bytes | lib/bitabs, lib/nifpools, models/nimony_tags, models/tags | tables | 🔲 Pending |
| `nimony/reporters` | 5 | 5,320 bytes | lib/bitabs, lib/compat2, lib/nifpools | assertions, os, sets, strutils, syncio, terminal | 🔲 Pending |
| `finalir/finalir_model` | 6 | 1,011 bytes | lib/compat2, lib/nifprelude, models/finalir_tags, models/tags | assertions | 🔲 Pending |
| `lengc/leng_model` | 6 | 8,101 bytes | lib/nifprelude, models/callconv_tags, models/leng_tags, models/tags | assertions, syncio | ⏭️ Later: used by hexer and the optimizer, not by lengc's backends (they read NIF through lib/nifcdecl) |
| `lengc/shoggoth/nifrender` | 6 | 1,922 bytes | lib/nifprelude | assertions, nifbuilder ✗, nifpools ✗ | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/typenav` | 6 | 14,618 bytes | lengc/nifmodules, lib/intrinsics, lib/nifcdecl, lib/nifcoreparse, models/tags | assertions, tables | ✅ Converted |
| `lib/nifindexes` | 6 | 12,624 bytes | lib/bitabs, lib/compat2, lib/lineinfos, lib/nifchecksums, lib/nifcoreparse, lib/nifpools, lib/nifreader, lib/stringviews, lib/symparser, lib/vfs, models/nifindex_tags, models/tags | assertions, hashes, os, sha1, strutils, syncio, tables | ✅ Converted |
| `nimony/nifconfig` | 6 | 17,889 bytes | lib/nifcoreparse, lib/nifprelude, lib/platform | os, sets, strutils | 🔲 Pending |
| `nimony/nimony_model` | 6 | 23,236 bytes | lib/nifprelude, lib/stringviews, lib/symparser, models/callconv_tags, models/nimony_tags, models/tags | assertions | 🔲 Pending |
| `hexer/dce1` | 7 | 7,970 bytes | lengc/leng_model, lib/compat2, lib/nifcoreparse, lib/nifprelude, lib/symparser | algorithm, assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/funcsummary` | 7 | 35,343 bytes | lengc/leng_model, lib/compat2, lib/nifprelude | assertions, tables | 🔲 Pending |
| `hexer/intramodinliner` | 7 | 98,779 bytes | lengc/leng_model, lib/compat2, lib/foreignmodules, lib/nifprelude, lib/symparser | assertions, hashes, os, sets, syncio, tables | 🔲 Pending |
| `lengc/codegen` | 7 | 29,029 bytes | lengc/cprelude, lengc/genexprs, lengc/genstmts, lengc/gentypes, lengc/mangler, lengc/nifmodules, lengc/noptions, lengc/typenav, lib/intrinsics, lib/nifcdecl, lib/nifcoreparse, lib/symparser, lib/vfs | assertions, formatfloat, intsets, os, packedsets, sequtils, sets, syncio, tables | ✅ Converted |
| `lengc/llvmcodegen` | 7 | 34,384 bytes | lengc/llvmdebug, lengc/llvmgenexprs, lengc/llvmgenstmts, lengc/llvmgentypes, lengc/llvmirmodel, lengc/llvmserializer, lengc/mangler, lengc/nifmodules, lengc/noptions, lengc/typenav, lib/nifcdecl, lib/nifcoreparse, lib/symparser, lib/vfs | assertions, formatfloat, os, sequtils, sets, strutils, syncio, tables | ✅ Converted |
| `lengc/shoggoth/aliasing` | 7 | 12,601 bytes | lengc/nifmodules, lengc/typenav, lib/nifcdecl, lib/nifcoreparse | tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/constant_folding` | 7 | 10,390 bytes | lengc/leng_model, lengc/shoggoth/nifrender, lib/nifprelude, models/tags | assertions, hashes, nifpools ✗, patchsets_legacy ✗, sets, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/intrinsiceffects` | 7 | 2,768 bytes | lengc/nifmodules, lengc/typenav, lib/intrinsics, lib/nifcdecl, lib/nifcoreparse |  | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/memidioms` | 7 | 43,651 bytes | lengc/nifmodules, lengc/shoggoth/patchsets, lengc/shoggoth/vmrewriter, lengc/typenav, lib/intrinsics, lib/nifcdecl, lib/nifcoreparse | assertions, sets, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/scalarizer` | 7 | 30,718 bytes | lengc/nifmodules, lengc/shoggoth/patchsets, lengc/typenav, lib/compat2, lib/nifcdecl, lib/nifcoreparse, lib/symparser, models/tags | algorithm, assertions, hashes, sets, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `nimony/asthelpers` | 7 | 1,346 bytes | lib/nifprelude, lib/symparser, nimony/nimony_model | assertions, formatfloat, sets, syncio, tables | 🔲 Pending |
| `nimony/builtintypes` | 7 | 9,778 bytes | lib/nifprelude, nimony/nimony_model |  | 🔲 Pending |
| `nimony/decls` | 7 | 10,529 bytes | lib/compat2, lib/nifprelude, nimony/nimony_model, nimony/reporters | assertions, syncio | 🔲 Pending |
| `nimony/magics` | 7 | 4,564 bytes | lib/nifpools, models/tags, nimony/nimony_model |  | 🔲 Pending |
| `nimony/symtabs` | 7 | 3,345 bytes | lib/compat2, lib/nifprelude, nimony/identstyle, nimony/nimony_model | tables | 🔲 Pending |
| `hexer/dce2` | 8 | 14,971 bytes | hexer/dce1, lengc/leng_model, lib/compat2, lib/lengiface, lib/nifprelude, lib/symparser | algorithm, assertions, hashes, os, sets, syncio, tables | 🔲 Pending |
| `lengc/lengc` | 8 | 7,226 bytes | lengc/codegen, lengc/llvmcodegen, lengc/noptions, lib/compat2, lib/nimversion, lib/symparser, lib/vfs | assertions, dirs, os, osproc, parseopt, paths, strutils, syncio, tables | ✅ Converted |
| `lengc/shoggoth/cse` | 8 | 118,356 bytes | lengc/nifmodules, lengc/shoggoth/accesspaths, lengc/shoggoth/aliasing, lengc/shoggoth/intrinsiceffects, lengc/shoggoth/patchsets, lengc/shoggoth/trackers, lengc/typenav, lib/compat2, lib/nifcdecl, lib/nifcoreparse, models/tags | algorithm, assertions, formatfloat, hashes, sets, strutils, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/induction_variables` | 8 | 20,322 bytes | lengc/nifmodules, lengc/shoggoth/intrinsiceffects, lengc/shoggoth/patchsets, lengc/typenav, lib/compat2, lib/nifcdecl, lib/nifcoreparse, models/tags | assertions, sets, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/intermodinliner` | 8 | 6,694 bytes | hexer/intramodinliner, lengc/leng_model, lib/nifprelude, lib/symparser | assertions, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `nimony/programs` | 8 | 22,777 bytes | gear2/modnames, lib/compat2, lib/nifcoreparse, lib/nifindexes, lib/nifprelude, lib/nifreader, lib/symparser, models/nifindex_tags, nimony/builtintypes, nimony/decls, nimony/identstyle, nimony/nimony_model, nimony/reporters, nimony/symtabs | hashes, os, sequtils, sets, syncio, tables, times | 🔲 Pending |
| `finalir/condextractor` | 9 | 8,285 bytes | finalir/finalir_model, lib/compat2, lib/nifprelude, nimony/decls, nimony/nimony_model, nimony/programs | assertions, tables | 🔲 Pending |
| `hexer/arcopt` | 9 | 13,524 bytes | hexer/passes, lengc/leng_model, lib/compat2, lib/nifprelude, lib/symparser, models/leng_tags, nimony/nimony_model, nimony/programs | assertions, intsets | 🔲 Pending |
| `hexer/mover` | 9 | 30,411 bytes | finalir/finalir_model, lib/compat2, lib/nifprelude, nimony/decls, nimony/nimony_model, nimony/programs | assertions, intsets | 🔲 Pending |
| `lengc/shoggoth/copyprop` | 9 | 71,625 bytes | lengc/nifmodules, lengc/shoggoth/cse, lengc/shoggoth/patchsets, lengc/shoggoth/trackers, lib/nifcdecl, lib/nifcoreparse | assertions, hashes, sets, tables | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/imi_bridge` | 9 | 1,380 bytes | lengc/shoggoth/intermodinliner, lib/nifprelude | assertions | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/optfuzz` | 9 | 5,354 bytes | lengc/leng_model, lengc/shoggoth/constant_folding, lengc/shoggoth/cse, lengc/shoggoth/nifrender, lib/nifprelude, models/tags | assertions, copy_propagation ✗, induction_variables_legacy ✗, nifpools ✗, os, rewriter ✗, strutils, times | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `nimony/renderer` | 9 | 53,623 bytes | finalir/finalir_model, lib/bitabs, lib/filelinecache, lib/nifpools, lib/symparser, nimony/decls, nimony/nimony_model, nimony/programs | assertions, formatfloat, strutils | 🔲 Pending |
| `nimony/semdata` | 9 | 20,883 bytes | gear2/modnames, lib/compat2, lib/intrinsics, lib/nifindexes, lib/nifprelude, lib/symparser, nimony/builtintypes, nimony/decls, nimony/features, nimony/langmodes, nimony/magics, nimony/nifconfig, nimony/nimony_model, nimony/programs, nimony/reporters, nimony/symtabs, nimony/xints | assertions, formatfloat, hashes, os, sets, syncio, tables | 🔲 Pending |
| `nimony/staticmatches` | 9 | 6,830 bytes | lib/nifprelude, lib/symparser, models/tags, nimony/builtintypes, nimony/decls, nimony/nimony_model, nimony/programs | assertions | 🔲 Pending |
| `lengc/shoggoth/optdriver` | 10 | 16,959 bytes | lengc/nifmodules, lengc/shoggoth/copyprop, lengc/shoggoth/cse, lengc/shoggoth/imi_bridge, lengc/shoggoth/induction_variables, lengc/shoggoth/memidioms, lengc/shoggoth/scalarizer, lengc/shoggoth/tailcalls, lengc/shoggoth/unswitch, lengc/shoggoth/vectorizer, lengc/shoggoth/vmrewriter, lengc/typenav, lib/compat2, lib/intrinsics, lib/lengiface, lib/nifcdecl, lib/nifcoreparse | assertions, envvars ✗, os, sets, strutils, syncio | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `lengc/shoggoth/tracer_tmp` | 10 | 4,409 bytes | lengc/nifmodules, lengc/shoggoth/copyprop, lengc/shoggoth/cse, lengc/shoggoth/imi_bridge, lengc/shoggoth/induction_variables, lengc/shoggoth/scalarizer, lengc/shoggoth/vmrewriter, lengc/typenav, lib/nifcdecl, lib/nifcoreparse | assertions, os, strutils, syncio | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
| `nimony/typeprops` | 10 | 25,469 bytes | lib/nifprelude, models/tags, nimony/builtintypes, nimony/decls, nimony/nifconfig, nimony/nimony_model, nimony/programs, nimony/semdata, nimony/xints | assertions, sets, strutils | 🔲 Pending |
| `nimony/conceptcache` | 11 | 11,843 bytes | lib/compat2, lib/nifprelude, lib/symparser, nimony/decls, nimony/nimony_model, nimony/programs, nimony/semdata, nimony/symtabs, nimony/typeprops | hashes, sets, tables | 🔲 Pending |
| `nimony/expreval` | 11 | 67,175 bytes | lib/nifprelude, lib/symparser, nimony/builtintypes, nimony/decls, nimony/langmodes, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/semdata, nimony/typeprops, nimony/xints | assertions, os, syncio | 🔲 Pending |
| `nimony/typenav` | 11 | 27,157 bytes | finalir/finalir_model, lib/compat2, lib/nifprelude, nimony/builtintypes, nimony/decls, nimony/nimony_model, nimony/programs, nimony/typeprops | assertions, strutils, tables | 🔲 Pending |
| `hexer/closuretypes` | 12 | 8,477 bytes | lib/compat2, lib/nifprelude, nimony/builtintypes, nimony/nif_annotations, nimony/nimony_model, nimony/typenav | assertions | 🔲 Pending |
| `hexer/defaultvalues` | 12 | 12,077 bytes | lib/compat2, lib/nifprelude, nimony/decls, nimony/expreval, nimony/nimony_model, nimony/programs, nimony/reporters, nimony/typeprops, nimony/xints | assertions | 🔲 Pending |
| `hexer/xelim` | 12 | 64,194 bytes | finalir/finalir_model, hexer/passes, lib/compat2, lib/nifprelude, nimony/builtintypes, nimony/decls, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/typenav, nimony/typeprops | assertions, syncio | 🔲 Pending |
| `nimony/sigconcepts` | 12 | 14,761 bytes | lib/compat2, lib/nifprelude, lib/symparser, nimony/conceptcache, nimony/decls, nimony/features, nimony/nimony_model, nimony/programs, nimony/semdata, nimony/symtabs, nimony/typeprops | assertions, sets, tables | 🔲 Pending |
| `nimony/sizeof` | 12 | 16,050 bytes | lib/compat2, lib/nifprelude, nimony/decls, nimony/expreval, nimony/nimony_model, nimony/programs, nimony/semdata, nimony/xints | assertions, tables | 🔲 Pending |
| `finalir/finalir` | 13 | 35,754 bytes | finalir/condextractor, finalir/finalir_model, hexer/mover, hexer/passes, hexer/xelim, lib/compat2, lib/nifprelude, lib/symparser, nimony/builtintypes, nimony/decls, nimony/nimony_model, nimony/programs, nimony/typenav, nimony/typeprops | assertions, os, syncio, tables | 🔲 Pending |
| `hexer/eraiser` | 13 | 42,105 bytes | finalir/finalir_model, hexer/passes, lib/compat2, lib/nifprelude, models/tags, nimony/builtintypes, nimony/decls, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/reporters, nimony/sizeof, nimony/typenav, nimony/typeprops | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `nimony/sigmatch` | 13 | 126,532 bytes | lib/compat2, lib/nifprelude, lib/symparser, models/tags, nimony/asthelpers, nimony/builtintypes, nimony/conceptcache, nimony/decls, nimony/expreval, nimony/features, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/semdata, nimony/sigconcepts, nimony/staticmatches, nimony/symtabs, nimony/typeprops, nimony/xints | assertions, sets, tables | 🔲 Pending |
| `nimony/typekeys` | 14 | 5,616 bytes | lib/nifprelude, lib/symparser, lib/treemangler, nimony/decls, nimony/nimony_model, nimony/sigmatch | assertions | 🔲 Pending |
| `hexer/lifter` | 15 | 61,760 bytes | hexer/closuretypes, lib/compat2, lib/nifindexes, lib/nifprelude, lib/symparser, lib/treemangler, nimony/builtintypes, nimony/decls, nimony/expreval, nimony/nimony_model, nimony/programs, nimony/typekeys, nimony/typenav, nimony/typeprops, nimony/xints | assertions, hashes, os, strutils, syncio, tables | 🔲 Pending |
| `nimony/vtables_frontend` | 15 | 5,095 bytes | lib/compat2, lib/nifindexes, lib/nifprelude, lib/symparser, lib/treemangler, nimony/builtintypes, nimony/decls, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/semdata, nimony/sigmatch, nimony/typekeys, nimony/typenav, nimony/typeprops | assertions | 🔲 Pending |
| `hexer/destroyer` | 16 | 22,379 bytes | finalir/finalir_model, hexer/lifter, hexer/passes, lengc/shoggoth/trackers, lib/compat2, lib/nifindexes, lib/nifprelude, lib/symparser, lib/treemangler, nimony/decls, nimony/nimony_model, nimony/programs, nimony/typenav | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/hexer_context` | 16 | 4,589 bytes | hexer/lifter, lib/compat2, lib/nifprelude, nimony/langmodes, nimony/nimony_model, nimony/sizeof, nimony/typenav | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/desugar` | 17 | 59,419 bytes | finalir/finalir_model, hexer/closuretypes, hexer/hexer_context, hexer/lifter, hexer/passes, lib/compat2, lib/nifprelude, nimony/builtintypes, nimony/decls, nimony/expreval, nimony/langmodes, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/reporters, nimony/sizeof, nimony/typenav, nimony/typeprops, nimony/xints | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/duplifier` | 17 | 78,756 bytes | finalir/finalir_model, hexer/closuretypes, hexer/defaultvalues, hexer/hexer_context, hexer/lifter, hexer/mover, hexer/passes, lib/compat2, lib/nifindexes, lib/nifprelude, lib/symparser, lib/treemangler, nimony/builtintypes, nimony/decls, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/reporters, nimony/typekeys, nimony/typenav | assertions, hashes, sets, strutils, syncio, tables | 🔲 Pending |
| `hexer/constparams` | 18 | 12,190 bytes | hexer/duplifier, hexer/passes, lib/compat2, lib/nifprelude, models/tags, nimony/builtintypes, nimony/decls, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/sizeof, nimony/typenav, nimony/typeprops | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/iterinliner` | 18 | 28,936 bytes | finalir/finalir_model, hexer/duplifier, hexer/hexer_context, hexer/passes, lib/compat2, lib/nifprelude, nimony/decls, nimony/nimony_model, nimony/programs, nimony/typenav | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/coro_transform` | 19 | 119,599 bytes | finalir/finalir_model, hexer/closuretypes, hexer/constparams, hexer/defaultvalues, hexer/duplifier, hexer/passes, lib/compat2, lib/nifprelude, lib/symparser, nimony/builtintypes, nimony/decls, nimony/expreval, nimony/langmodes, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/reporters, nimony/sizeof, nimony/typenav, nimony/typeprops, nimony/xints | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/cps` | 20 | 19,026 bytes | hexer/coro_transform, hexer/passes, lib/compat2, lib/nifprelude, nimony/builtintypes, nimony/decls, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/typenav, nimony/typeprops | assertions, sets, tables | 🔲 Pending |
| `hexer/lambdalifting` | 20 | 100,070 bytes | finalir/finalir_model, hexer/coro_transform, hexer/eraiser, hexer/hexer_context, hexer/passes, lib/compat2, lib/nifprelude, lib/symparser, nimony/builtintypes, nimony/decls, nimony/expreval, nimony/langmodes, nimony/nif_annotations, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/reporters, nimony/sizeof, nimony/typenav, nimony/typeprops, nimony/xints | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/vtables_backend` | 20 | 35,647 bytes | finalir/finalir_model, hexer/coro_transform, hexer/duplifier, hexer/passes, lib/compat2, lib/nifindexes, lib/nifprelude, lib/symparser, lib/tinyhashes, lib/treemangler, nimony/builtintypes, nimony/decls, nimony/nimony_model, nimony/programs, nimony/renderer, nimony/typekeys, nimony/typenav, nimony/typeprops, nimony/vtables_frontend | assertions, hashes, sets, strutils, syncio, tables | 🔲 Pending |
| `hexer/pipeline` | 21 | 6,702 bytes | finalir/finalir, hexer/arcopt, hexer/constparams, hexer/cps, hexer/destroyer, hexer/desugar, hexer/duplifier, hexer/eraiser, hexer/funcsummary, hexer/hexer_context, hexer/intramodinliner, hexer/iterinliner, hexer/lambdalifting, hexer/lifter, hexer/passes, hexer/vtables_backend, hexer/xelim, lib/compat2, lib/nifprelude, nimony/decls, nimony/nimony_model, nimony/programs | assertions, hashes, sets, syncio, tables | 🔲 Pending |
| `hexer/lengcgen` | 22 | 104,855 bytes | finalir/finalir_model, hexer/dce1, hexer/hexer_context, hexer/lifter, hexer/pipeline, hexer/stringcases, lib/compat2, lib/intrinsics, lib/nifprelude, lib/stringtrees, lib/symparser, models/tags, nimony/builtintypes, nimony/decls, nimony/expreval, nimony/langmodes, nimony/nifconfig, nimony/nimony_model, nimony/programs, nimony/sizeof, nimony/typekeys, nimony/typenav, nimony/typeprops, nimony/xints | assertions, hashes, os, sets, syncio, tables | 🔲 Pending |
| `hexer/hexer` | 23 | 1,314 bytes | hexer/dce2, hexer/lengcgen |  | 🔲 Pending |
| `lengc/shoggoth/shoggoth` | 24 | 9,372 bytes | hexer/hexer, lengc/shoggoth/optdriver, lengc/shoggoth/patextract, lib/compat2, lib/nimversion, lib/vfs, nimony/langmodes, nimony/nifconfig, nimony/programs | assertions, dirs, os, parseopt, paths, strutils, syncio | ⏭️ Later: the optimizer (`--opt:speed|size`, the shoggoth binary), after hexer (Phase D) |
