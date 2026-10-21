# nimony → nnimony: Conversion Queue

> **Generated** by `python -m nnimony.tools.queue` from the nimony clone at `3f56467ab15a` (pinned in `nnimony/tools/queue.py`). The plan: `ncompiler/conversion_plan.md`.

## Conversion Rules

1. **Convert the current component in tier order**, a module once the nimony modules it imports are converted.
2. **Mirror the path:** `src/lib/bitabs.nim` → `nnimony/lib/bitabs.py`; the module records its source commit in its header (`# source: nimony@<sha>:src/lib/bitabs.nim`).
3. **Missing std shims** (`src/nimic/std/`) are created as part of the conversion.
4. **`when defined(nimony)`** branches are converted like any `when` (`if comptime(...)`); Python runs the host-Nim build, where they are inactive.
5. **Review runs after every conversion**; verification: `tests/verify_transpiled.py`.

## Components

| Component | Role | Lines | State |
|---|---|---|---|
| `src/lib` | NIF libraries: the foundation of every nimony tool | 12,053 | current |
| `src/nifler2` | the parser (Nim -> NIF), a nimony program generated from a grammar | 6,927 | next |
| `src/lengc` | the C backend (NIF -> C) | 22,977 | later |
| `src/hexer` | lowering (shoggoth) | 24,466 | later |
| `src/nimony` | semantic checking (nimsem) and the driver | 50,268 | later |

## Ready to Convert (`src/lib`)

| Module | Size | Std imports (✗ = no nimic shim yet) | Agent |
|---|---|---|---|
| `models/callconv_tags` | 921 bytes |  | brief_lib_batch5.md |
| `models/nifindex_tags` | 4,112 bytes |  | brief_lib_batch5.md |
| `lib/argsfinder` | 4,466 bytes | assertions, os, parseopt ✗, strutils, syncio |  |
| `lib/keymatcher` | 5,934 bytes | assertions, macros ✗ |  |
| `lib/vfs` | 12,960 bytes | atomics ✗, memfiles ✗, os, posix/posix ✗, syncio, times |  |
| `models/leng_tags` | 24,091 bytes |  | brief_lib_batch5.md |
| `lib/intrinsics` | 80,220 bytes |  |  |
| `lib/nifcore` | 111,775 bytes | assertions, formatfloat, hashes |  |

## All modules of `src/lib` (16/39 converted)

| Module | Tier | Size | Depends on | Std imports | Status |
|---|---|---|---|---|---|
| `lib/argsfinder` | 0 | 4,466 bytes |  | assertions, os, parseopt ✗, strutils, syncio | 🔲 Pending |
| `lib/bitabs` | 0 | 10,085 bytes |  | assertions, hashes | ✅ Converted |
| `lib/comesfrom` | 0 | 5,495 bytes |  |  | ✅ Converted |
| `lib/compat2` | 0 | 3,478 bytes |  | paths, tables | ✅ Converted |
| `lib/docpaths` | 0 | 3,130 bytes |  | os, strutils | ✅ Converted |
| `lib/intrinsics` | 0 | 80,220 bytes |  |  | 🔲 Pending |
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
| `lib/vfs` | 0 | 12,960 bytes |  | atomics ✗, memfiles ✗, os, posix/posix ✗, syncio, times | 🔲 Pending |
| `models/tags` | 0 | 13,811 bytes |  |  | ✅ Converted |
| `lib/filelinecache` | 1 | 2,028 bytes | lib/compat2 | hashes, strutils, syncio, tables | ✅ Converted |
| `lib/keymatcher` | 1 | 5,934 bytes | lib/stringtrees, lib/stringviews | assertions, macros ✗ | 🔲 Pending |
| `lib/legacy/nif26reader` | 1 | 13,861 bytes | lib/stringviews, lib/vfs | assertions, memfiles ✗, parseutils | 🔲 Pending |
| `lib/nifbuilder` | 1 | 16,576 bytes | lib/vfs | assertions, formatfloat, math, strutils, syncio | 🔲 Pending |
| `lib/nifcore` | 1 | 111,775 bytes | lib/bitabs, lib/lineinfos, lib/nifroles | assertions, formatfloat, hashes | 🔲 Pending |
| `models/callconv_tags` | 1 | 921 bytes | models/tags |  | 🔲 Pending |
| `models/leng_tags` | 1 | 24,091 bytes | models/tags |  | 🔲 Pending |
| `models/nifindex_tags` | 1 | 4,112 bytes | models/tags |  | 🔲 Pending |
| `lib/bif` | 2 | 52,325 bytes | lib/compat2, lib/nifcore, lib/vfs | assertions, strutils, syncio, varints ✗ | 🔲 Pending |
| `lib/htmlbuilder` | 2 | 4,222 bytes | lib/nifbuilder |  | 🔲 Pending |
| `lib/lengiface` | 2 | 3,852 bytes | lib/nifbuilder, lib/nifcore, lib/vfs | assertions, formatfloat, sha1 ✗, syncio | 🔲 Pending |
| `lib/nifcdecl` | 2 | 10,477 bytes | lib/nifcore, models/callconv_tags, models/leng_tags, models/tags | assertions | 🔲 Pending |
| `lib/nifreader` | 2 | 38,779 bytes | lib/nifcore, lib/stringviews, lib/vfs | assertions, memfiles ✗, parseutils | 🔲 Pending |
| `lib/nifcoreparse` | 3 | 26,586 bytes | lib/comesfrom, lib/lineinfos, lib/nifbuilder, lib/nifcore, lib/nifreader, lib/stringviews | assertions, math, strutils, syncio | 🔲 Pending |
| `lib/foreignmodules` | 4 | 7,572 bytes | lib/bif, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/stringviews | tables | 🔲 Pending |
| `lib/nifpools` | 4 | 22,429 bytes | lib/comesfrom, lib/nifcore, lib/nifcoreparse, lib/nifreader, lib/nifroles, lib/vfs, models/tags | assertions | 🔲 Pending |
| `lib/nifqueries` | 4 | 2,547 bytes | lib/nifcore, lib/nifcoreparse | assertions | 🔲 Pending |
| `lib/nifchecksums` | 5 | 2,565 bytes | lib/bitabs, lib/nifpools, lib/nifreader | formatfloat, sha1 ✗ | 🔲 Pending |
| `lib/nifprelude` | 5 | 372 bytes | lib/bitabs, lib/nifbuilder, lib/nifpools, lib/nifreader, lib/nifroles |  | 🔲 Pending |
| `lib/nifstreams` | 5 | 8,456 bytes | lib/lineinfos, lib/nifpools, lib/nifreader | tables | 🔲 Pending |
| `lib/nifindexes` | 6 | 12,090 bytes | lib/bitabs, lib/compat2, lib/lineinfos, lib/nifchecksums, lib/nifcoreparse, lib/nifpools, lib/nifreader, lib/stringviews, lib/symparser, lib/vfs, models/nifindex_tags, models/tags | assertions, hashes, os, sha1 ✗, strutils, syncio, tables | 🔲 Pending |
