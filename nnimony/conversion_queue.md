# nimony → nnimony: Conversion Queue

> **Generated** by `python -m nnimony.tools.queue` from the nimony clone at `8e0321d8917b` (pinned in `nnimony/tools/queue.py`). The plan: `ncompiler/conversion_plan.md`.

## Conversion Rules

1. **Convert the current component in tier order**, a module once the nimony modules it imports are converted.
2. **Mirror the path:** `src/lib/bitabs.nim` → `nnimony/lib/bitabs.py`; the module records its source commit in its header (`# source: nimony@<sha>:src/lib/bitabs.nim`).
3. **Missing std shims** (`src/nimic/std/`) are created as part of the conversion.
4. **`when defined(nimony)`** branches are converted like any `when` (`if comptime(...)`); Python runs the host-Nim build, where they are inactive.
5. **Review runs after every conversion**; verification: `tests/verify_transpiled.py`.

## Components

| Component | Role | Lines | State |
|---|---|---|---|
| `src/lib` | NIF libraries: the foundation of every nimony tool | 12,295 | current |
| `src/nifler2` | the parser (Nim -> NIF), a nimony program generated from a grammar | 7,010 | next |
| `src/lengc` | the C backend (NIF -> C) | 24,256 | later |
| `src/hexer` | lowering (shoggoth) | 24,622 | later |
| `src/nimony` | semantic checking (nimsem) and the driver | 51,264 | later |

## Ready to Convert (`src/lib`)

| Module | Size | Std imports (✗ = no nimic shim yet) | Agent |
|---|---|---|---|

## All modules of `src/lib` (37/37 converted, 2 legacy)

| Module | Tier | Size | Depends on | Std imports | Status |
|---|---|---|---|---|---|
| `lib/argsfinder` | 0 | 4,466 bytes |  | assertions, os, parseopt, strutils, syncio | ✅ Converted |
| `lib/bitabs` | 0 | 10,085 bytes |  | assertions, hashes | ✅ Converted |
| `lib/comesfrom` | 0 | 5,495 bytes |  |  | ✅ Converted |
| `lib/compat2` | 0 | 3,639 bytes |  | paths, tables | ✅ Converted |
| `lib/docpaths` | 0 | 3,130 bytes |  | os, strutils | ✅ Converted |
| `lib/intrinsics` | 0 | 82,410 bytes |  |  | ✅ Converted |
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
| `lib/vfs` | 0 | 12,960 bytes |  | atomics, memfiles, os, syncio, times | ✅ Converted |
| `models/tags` | 0 | 13,866 bytes |  |  | ✅ Converted |
| `lib/filelinecache` | 1 | 2,028 bytes | lib/compat2 | hashes, strutils, syncio, tables | ✅ Converted |
| `lib/keymatcher` | 1 | 5,934 bytes | lib/stringtrees, lib/stringviews | assertions, macros (legacy: expand the calls) | ⛔ Legacy: macro machinery (`declareMatcher`), called only by its own tests; macros are legacy |
| `lib/legacy/nif26reader` | 1 | 13,861 bytes | lib/stringviews, lib/vfs | assertions, memfiles, parseutils | ⛔ Legacy: NIF26 reader, used only by the nif26 -> nif27 migration tool, which nimic doesn't need (also not for a newer nimony) |
| `lib/nifbuilder` | 1 | 16,576 bytes | lib/vfs | assertions, formatfloat, math, strutils, syncio | ✅ Converted |
| `lib/nifcore` | 1 | 111,788 bytes | lib/bitabs, lib/lineinfos, lib/nifroles | assertions, formatfloat, hashes | ✅ Converted |
| `models/callconv_tags` | 1 | 921 bytes | models/tags |  | ✅ Converted |
| `models/leng_tags` | 1 | 24,126 bytes | models/tags |  | ✅ Converted |
| `models/nifindex_tags` | 1 | 4,112 bytes | models/tags |  | ✅ Converted |
| `lib/bif` | 2 | 53,014 bytes | lib/compat2, lib/nifcore, lib/vfs | assertions, strutils, syncio, varints | ✅ Converted |
| `lib/htmlbuilder` | 2 | 4,222 bytes | lib/nifbuilder |  | ✅ Converted |
| `lib/lengiface` | 2 | 3,852 bytes | lib/nifbuilder, lib/nifcore, lib/vfs | assertions, formatfloat, sha1, syncio | ✅ Converted |
| `lib/nifcdecl` | 2 | 10,477 bytes | lib/nifcore, models/callconv_tags, models/leng_tags, models/tags | assertions | ✅ Converted |
| `lib/nifreader` | 2 | 46,432 bytes | lib/nifcore, lib/stringviews, lib/vfs | assertions, memfiles, parseutils | ✅ Converted |
| `lib/nifcoreparse` | 3 | 26,586 bytes | lib/comesfrom, lib/lineinfos, lib/nifbuilder, lib/nifcore, lib/nifreader, lib/stringviews | assertions, math, strutils, syncio | ✅ Converted |
| `lib/foreignmodules` | 4 | 7,572 bytes | lib/bif, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/stringviews | tables | ✅ Converted |
| `lib/nifpools` | 4 | 22,429 bytes | lib/comesfrom, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/nifroles, lib/vfs, models/tags | assertions | ✅ Converted |
| `lib/nifqueries` | 4 | 2,547 bytes | lib/nifcore, lib/nifcoreparse | assertions | ✅ Converted |
| `lib/nifchecksums` | 5 | 2,565 bytes | lib/bitabs, lib/nifpools, lib/nifreader | formatfloat, sha1 | ✅ Converted |
| `lib/nifprelude` | 5 | 372 bytes | lib/bitabs, lib/nifbuilder, lib/nifpools, lib/nifreader, lib/nifroles |  | ✅ Converted |
| `lib/nifstreams` | 5 | 8,456 bytes | lib/lineinfos, lib/nifpools, lib/nifreader | tables | ✅ Converted |
| `lib/nifindexes` | 6 | 12,090 bytes | lib/bitabs, lib/compat2, lib/lineinfos, lib/nifchecksums, lib/nifcoreparse, lib/nifpools, lib/nifreader, lib/stringviews, lib/symparser, lib/vfs, models/nifindex_tags, models/tags | assertions, hashes, os, sha1, strutils, syncio, tables | ✅ Converted |
