# Nimic Translation Rules — nimony / Nim 3 (`../nimony/src/` → `nnimony/`)

**The rules for the current work, all in one file:**
- §0–§12: the nimic language;
- §13: the conventions of nimony modules (layout, imports, build, tests, verification);
- §14: the Nim 3 constructs and nimic's support for them.

Rows marked **(Nim 2: ...)** describe Nim 2 behaviour that Nim 3 changes. Converted nimony code runs the
host-Nim (Nim 2) build for now, so those rows still apply, and §14 gives the Nim 3 version.

The plan and its reasons are in `ncompiler/conversion_plan.md`. The Nim 2 compiler conversion (frozen)
has its own file, `nimic_translation_rules_nim2.md`. Language changes are made here first.

This document serves as a comprehensive collection of translation rules and syntax mappings when transpiling from Nim syntax to Python syntax for the `nimic` transpiler. These rules correspond directly to the internal `rule:` definitions located in `nimic/transpiler.py`. The major requirement is that nimic code is valid Python that transpiles to valid Nim code with the same behavior (§0, unity principle). Expressions not explicitly mentioned as a rule are assumed to be translated directly to Python syntax. Nimic code should be marked by the meta-comment and typically makes havy use of annotations and nimic.ntypes:

```python
# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
```


| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `isNil`, `copyMem` | `is_nil`, `copy_mem` | Nimic follows the Python convention, replacing `camelCase` with `snake_case` for functions and attributes **(Nim 2: the Nim 3 version is in §14)** |
| `let x = 5` | `with let: x = 5` | Immutable assignments |

## 0. Unity principle — one source, one behavior

Every line of converted code — statements, declarations, imports and tests — is nimic: it runs in Python and
transpiles to Nim that behaves the same. Same behavior means the same output, results and raised errors under
the same build profile; `tests/verify_transpiled.py` checks it (Python run vs compiled Nim).

*Nimic* means the constructs of these rules and the API of `nimic.ntypes` and `nimic.std`. Other Python is not
nimic, even if it happens to run or to transpile: Python builtins, the standard library and idioms with no Nim
equivalent.

There is no code for only one side:
- no branches on the backend (`defined("c")`, `not defined("c")`);
- no `_py_*` copies or alternative implementations;
- no rebinding or monkey-patching (`Class.attr = proc`, `setattr`, `globals()[...]`);
- no Python builtins or idioms that have no Nim equivalent.

`if comptime(X)` is allowed only where it mirrors a `when X` of the original (§2.1). That isn't a split: Python
emulates one Nim build, the build profile aligned with `nim.cfg`.

Python implementations belong in the nimic core (`src/nimic/`) and in `nimic.std`, never in converted modules.

When nimic can't express a construct faithfully, don't work around it:
1. write the closest faithful code and mark it `# TODO: requires nimic feature <name>`;
2. report the gap (a proposal in `ncompiler/proposals/`, or the conversion report);
3. continue with the rest.

A gap closed in the core benefits every module; a workaround in a module splits it into a Python and a Nim
version.

## 1. Variable Declarations (`rule:varini`, `rule:dropwith`)
Nim variable declarations are mapped to Python context managers to encapsulate scoping and mutability semantics. The transpiler strips the `with` block and generates standard Nim variable sections.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `var x: SomeType` | `with var: x = SomeType()` | Declaration and initializatoin |
| `var a: array[2, uint8]` | `with var: a = array[2, uint8]()` | Declaration and initializatoin |
| `var x = RefType()` | `with var: x = RefType()` | For a `ref` type (`@ref` class) the constructor call is kept, since `var x: RefType` would be `nil` (`rule:varini`) |
| `let x = 5` | `with let: x = 5` | Immutable assignments |
| `const x = 5` | `with const: x = 5` | Compile-time constants |
| `var x, y: int` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x = nint(0)`<br>&nbsp;&nbsp;&nbsp;&nbsp;`y = nint(0)` | Groups declarations |
| `var tY: uint16` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_tY = uint16()` | A module-level variable without `*` (also one in a module-level `when`) is written `_tY`: it transpiles to `tY`, not exported (`rule:localname`); without the `_` it would become the exported global `tY*`. Variables of a proc, loop or `block` (also `with block("name"):` at module level) are local and keep their names (`rule:dropwith`) |

### 1.1 Assignment copies values: `.copy()`, checked (`rule:valuecheck`)
Nim's assignment copies a value: after `var y = x`, changing `y` leaves `x` alone. Python binds the same object.
The converted code writes the copy where the difference shows, `y = x.copy()` (the transpiler drops it,
`rule:copy`), and runs as written: directly, under a debugger, in the REPL. Nimic checks that the copies are there
(`src/nimic/valuecheck.py`): a missing one whose value is then changed while both locations hold it, so that Python
and Nim certainly differ, is a `ValueCopyError` naming the binding and the write, with the copy to write.

| Nim | Python (Nimic) | Needs `.copy()` when |
| --- | --- | --- |
| `var y = x`, `var y = o.f`, `var y = s[i]`, `y = x` | `with var: y = x.copy()` | a value-type value (object, `seq`, `string`, array, set, scalar, a tuple holding one) and later one of the two names is changed (a store into it, `+=`, a method or a `mut @` argument, a core proc that may change it) while the other is read. Not for refs, procs, types, Python's immutable values, `with const:` values (frozen: changing one raises `TypeError`), a swap `(a, b) = (b, a)`, or a local's last use (Nim moves it). **Scalars too:** a nimic integer is a cell, `+=` changes it in place (`b = a; b += 1` changes `a`). **Decided from the source, before the binding's last read:** the binding is changed (assigned into, `+=`, a `mut @` argument or method), or its source is: the l-value it was read from (`start`, `t._keys[h]`) or a prefix of that path (`t`) assigned or passed as `mut @`. A parameter as the source is read after the proc (its cell is the caller's): `i = first; i += 1` copies. No copy of a fresh value (a literal, an arithmetic result, a call's result: the callee copies, next row), nor when only something off the path changes (`e0 = m.index[0]` before `m.buf.cursorAt(...)`; `path = pool.strings[k]` while `strId(n)` interns through `n`'s owner) |
| `proc f(p: P): T = p.f` | `def f(p: P) -> T: return p.f.copy()` | the proc returns a value it shares (a parameter, a global, a part of one, or a local bound to one): Nim's `-> T` result is a copy. Scalars too (`return r._indexAt.copy()`), also in a `@property` getter (`TokenBuf.len`: `return b._len.copy()`), so callers never copy a call's result. A proc that returns the location declares `-> lent @ T` / `-> mut @ T` (Nim `lent T` / `var T`); a local's own value is moved out (`return result`) |
| `var p = t.data.p` (a pointer) ... `decodeEscape(p)` (`p: var pchar`) | `with var: p = t.data.p.copy()` | A pointer is a value too: the copy is needed when the binding is then assigned in place (`p <<= q`, a `mut @` argument), which would move the field as well. Rebinding (`p = cast[pchar](...)`, what `inc p` expands to) needs none. Stores (field, `seq.add`) share pointers. Checked like the other values A value that may be nil is copied with the free form `copy(x)` (rule:copy): nil is Python's None, which has no method, and copies to nil (nifreader's `var p {.inject.} = r.p` is `p = copy(r._p)`: an empty buffer's `r.p` is nil); transpiled to `x` like `.copy()` |
| `var y = f(x)` | `with var: y = f(x)` | the result is one of its inputs or a part of one and is changed: a `lent @` / `mut @` result, a template's l-value, a core or std proc's result (`min(a, b)`, `t.getOrDefault(k)`), or a nimic proc returning a parameter's part without `.copy()` (better fixed in the proc, row above) |
| `o.f = x`, `s[i] = x`, `s.add(x)`, `T(f: x)` | the same | never: stores copy by themselves (`_n_value_copy`) |
| `f(x)` with `proc f(buf: sink string)` that moves `buf` (`ensureMove(buf)`, `move`, `wasMoved`) | `f(x.copy())` | `x` is not at its last use: a local read again later, a borrowed (non-`sink`) parameter, a global. Nim moves only a last use and copies otherwise; Python passes the object, and the callee's move empties the caller's. Passing a local at its last use or a `sink` parameter on needs none. Checked when the move runs: a caller up the chain still holding the value in a location it reads again is a `ValueCopyError` naming the call where Nim copies |

- **How it checks.** When a nimic module loads (an import hook only watches it; the main program and the modules
  that import nimic are watched from their running frames), the syntax marks the bindings that may need a copy and
  the statements that may change their values; nothing else is checked. A function is analyzed when it first runs.
  At run time (sys.monitoring, a tool of its own: debuggers and coverage run beside it), a marked binding whose
  value is a value type that another location still holds (the l-value it was read from, or a part of a call's
  inputs) is armed in its frame; each marked statement after it compares a fingerprint of the value before and
  after it. A change while both locations still hold the value is the error: in Nim only one of them changed. A
  binding that only *may* share (a getter's result only read, a value rebound before the write, a `break` before
  the write) is not an error. Each site is checked on its first 64 executions (and as many writes), then costs
  nothing. A site that never runs is not checked: `NIMIC_VALUECHECK_REPORT=<file>` appends the sites that ran,
  failed and never ran.
- **Modes** (`NIMIC_VALUECHECK`): `error` (the default), `warn` (printed once per site, the program continues),
  `lint` (also prints the possible differences: the bindings and `-> T` returns that may need a copy, judged from
  the syntax and the callees' annotations; most are not real), `off`.
- **Not checked:** code typed in the REPL or a debugger console, and Python files without the header.
- **The transpiler's source checks run too** (in every mode, `off` included): a module whose private names collide
  with their Nim names (`rule:localname`) is rejected before it runs, and imports that bind other procs than Nim's
  (`rule:import`, §8: a star import of a nimic module, a hidden overload, ...) once its imports have run (before its
  next line, so before a main block; the imports of a main block, a module's tests, don't count; a main program with
  no line after its imports is not checked). The error gives the file and line, as `nimp` does when transpiling.
## 2. Compile-Time and Metaprogramming (`rule:comptime`, `rule:templateinline`)
Compile-time metaprogramming relies on function calls or specific decorators.

**Macros are a legacy feature.** nimony replaces them with compiler plugins, and nimic has no macros:
- a `macro` definition is not converted;
- each call of a macro is written out as the code it expands to: plain procs, types and constants, with
  templates where they keep it readable (a repeated shape, a block template for a `body` parameter);
- the conversion keeps the macro as a comment where it was defined (its name and what it generates), and the
  report lists every expanded call;
- `import std/macros` is dropped when nothing else uses it.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `when x < 5:` | `if comptime(x < 5):` | |
| `template foo()` | `@template`<br>`def foo()` | Template definition. Note: `@template_expand` is **only** needed on the *calling function* if you need to actually expand *untyped* templates inside it. Typed templates should have a `return` statement. |
| `template eatWord(word) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`while x[idx] == sep: idx.dec`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = ...`<br>&nbsp;&nbsp;&nbsp;&nbsp;`if not result: return` | `@template`<br>`def eatWord(word: untyped):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`while x[idx] == sep: idx -= 1`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = ...`<br>&nbsp;&nbsp;&nbsp;&nbsp;`if not result: return` | A statement template using the caller's variables (names that are not its parameters, its own `with var/let` locals or globals of its module) is expanded in callers decorated with `@template_expand`: no `{.dirty.}` (unless the original has it) and no `nonlocal`. Its bare `return` returns `result` from the caller. A call expands where the caller binds the name to the template (its module's import or definition, a local template); a caller whose name is another proc calls the proc |
| `template inc(p: pchar; diff = 1) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`p = cast[pchar](cast[int](p) + diff)`<br>`inc p`, `inc r.p, 2` | `@template`<br>`def _inc(p: pchar, diff=1):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`p = cast[pchar](cast[intp](p) + diff)`<br>`_inc(p)`, `_inc(r._p, 2)` | A statement template that assigns one of its parameters assigns the call's argument (Nim substitutes it): it is expanded in callers decorated with `@template_expand`, as one using the caller's variables. Missing arguments take the template's defaults; keywords work. When the argument is a `mut @` parameter of the caller (`proc decodeEscape(p: var pchar)`), the assignment is `p <<= ...` (Nim assigns through the `var` parameter). Called from a proc without `@template_expand`, the assignment only rebinds the template's own name. A template passing its parameter to such a template (nifreader's `unsignedSuffix(p, ...)` calling `inc(p)`) is expanded the same way, so the assignment reaches the caller's argument through both (Nim substitutes into both bodies); the inner template is declared first, as Nim requires. A call of a proc with a `var` parameter (nifpools' `inc` templates calling nifcore's `inc(c: var Cursor)`) is no assignment of the template's parameter: the proc changes the argument in place, so no `@template_expand` is needed for it; only system's `inc`/`dec` (a rebinding of a scalar or pointer) or a template of the module itself that assigns count |
| `template useCpuRegisters(body: untyped) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`var p {.inject.} = r.p`<br>&nbsp;&nbsp;&nbsp;&nbsp;`body`<br>&nbsp;&nbsp;&nbsp;&nbsp;`r.p = p`<br>`useCpuRegisters:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`while p < eof: inc p` | `@template`<br>`def _useCpuRegisters(body: untyped):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`p: pragma("inject") = r._p`<br>&nbsp;&nbsp;&nbsp;&nbsp;`body`<br>&nbsp;&nbsp;&nbsp;&nbsp;`r._p = p`<br>`with _useCpuRegisters():`<br>&nbsp;&nbsp;&nbsp;&nbsp;`while p < eof: _inc(p)` | A block template using its caller's variables (`r`) or `{.dirty.}` is expanded at `with t(args):` in `@template_expand` callers: its body with the `with` body (and the `with do:` blocks) in place of the block parameters, so its `{.inject.}` locals are the block's and its `break` leaves its own loop, as in Nim. Templates in the expanded code (`inc p`, a local statement template whose body has such a `with`) are expanded too. Without `@template_expand` it runs as any block template (and the caller's names are missing) |
| `template fun(op) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`conf.notes.op note`<br>`fun(incl)` | `@template`<br>`def fun(op: untyped):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`conf.notes.op(note)`<br>`fun(incl)` | A template parameter used as a routine, in call (`self(v, result)`) or method-call position, is substituted on expansion: `incl(conf.notes, note)` |
| `template impl() = result = 0; ...` shared by procs returning `int` and `BiggestInt` | `result <<= 0` in the template; each proc starts with `result = nint(0)` / `result = BiggestInt(0)` | `<<=` assigns in place and keeps the caller's result type (Nim `result = 0`) |
| `template _sph(): untyped {.dirty.} =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`moving_spheres[i]`  (used inline by attributes) | `with template_inline:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.dirty.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_sph = moving_spheres[i]` |  For substituting an expression accessed by attributes. |
| `when defined(windows):` | `if comptime(defined("windows")):` | `defined()` takes a string in Nimic (`rule:defined`); transpiler strips quotes for Nim. In Python it tests the *build profile* of the emulated Nim build: `c`, host OS/CPU (`macosx`, `posix`, `arm64`, ...), `gcOrc`, the compiler's feature symbols, the `define:` lines of the Nim configs Nim would read for the same main module (global config, `nim.cfg` files from the root down to the main module's directory, `<main>.nim.cfg`; `ncompiler/nim.cfg` links `compiler/nim.cfg`), and `NIMIC_DEFINES` (e.g. `NIMIC_DEFINES=danger`). So `defined("c")` is true in Python too |
| `when declared(signbit):` | `if comptime(declared("signbit")):` | `rule:declared`: the name (dotted allowed: `declared("system.getMaxMem")`) is looked up in the calling module's scope |
| `const x = when c: a else: b` | `with const:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x = a if comptime(c) else b` | `when` expression (`rule:comptimeexpr`) |
| `{.push overflowChecks: off.}`<br>`...`<br>`{.pop.}` | `with push("overflowChecks: off"):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...` | `rule:push`: emits the pragma, the body unindented, then `{.pop.}`. Python emulates the runtime checks `overflowChecks`, `boundChecks` and `checks` for procs defined inside the block; other pragmas only affect the Nim output |
| `when not compileOption("threads"):` | `if comptime(not compileOption("threads")):` | `not comptime(...)` is also handled correctly |
| `template addCast(b: var Builder, t: Snippet, body: typed) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...; body; ...`<br>`b.addCast(t): b.add(x)` | `@template`<br>`def addCast(b: mut@Builder, t: Snippet, body: typed):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...; body; ...`<br>`with b.addCast(t):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`b.add(x)` | Block template: trailing `typed`/`untyped` parameters used as bare statements are the code blocks of the call. `return x` is a value, not a block: `template onRaiseQuit(call: untyped): untyped = call` is `return call`, called `onRaiseQuit(f.readBuffer(p, n))` (a bare `call` would make it a block template) A second block (`... : first do: second`) follows `with do:` *inside* the `with` body. Skipped, extra or missing blocks raise `TemplateBlockError`. A proc overload of the same name needs `@dispatch`. A generic block template (`template buildTree*[T: enum](dest: var TokenBuf; tag: T; body: untyped)`) is `def buildTree[T: enum](...)`: the call binds `T` from its arguments, in the body too |
| `template loopInto*(c: var Cursor; body: untyped) =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`into c:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`while c.hasMore: body`<br>`n.loopInto:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`skip n` | `for _ in n.loopInto():`<br>&nbsp;&nbsp;&nbsp;&nbsp;`skip(n)` | `rule:looptemplate`: a block template that runs its block in a loop is called with `for _ in ...:` (a `with` body runs once: `with` raises `TemplateBlockError`), one iteration per run of the block. `break` leaves the template's loop and the template finishes, as Nim's `break` in the expanded body; `return` and exceptions leave the template where it is. `continue` resumes the template after the block (Nim skips the rest of the template's loop body: the same when nothing follows the block there). Limit: a `break` inside `try`/`finally` that ends the function counts as a `return` |
| `template t(b: var Builder, kind = Local, name: string, body: typed)` | `def t(b: mut@Builder, kind: VarKind = VarKind.Local, name: string = string(""), body: typed = None)` | Python needs defaults after a defaulted parameter; the `= None` of a block parameter is not written to Nim (`rule:blockparam`) |
| `include cbuilderexprs, cbuilderstmts` | `include("cbuilderexprs", "cbuilderstmts")` | `rule:include`: the file runs in the includer's namespace. An include file has no imports of its own (only the nimic boilerplate) and no tests: it is tested through a harness in `ncompiler/tests/` that, like its real includer, imports the converted modules, includes stand-ins for the unconverted ones (`cgen_context`, ...) and the include files in the includer's order |
| `{.gcsafe.}:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`body` | `with pragma("gcsafe"):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`body` | Pragma block (`rule:pragmablock`), also `pragma("cast(gcsafe)")`; no effect in Python |
| `let entry {.cursor.} = files[name]`, `var x {.noinit.}: int` (a variable's pragma) | `with let:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`entry: pragma("cursor") = files[name]`<br>`with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x: pragma("noinit") @ nint = nint()` | `rule:varpragma`: the annotation `pragma("p")` (Nim infers the type) or `pragma("p") @ T`. No effect in Python; Python needs a value even where Nim has none (`noinit`) |
| `const VersionFile = slurp("../../doc/version.md")` (also `staticRead`) | `with const:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_VersionFile = slurp("../../doc/version.md")` | Read when the module runs (Nim's compile time), relative to the **original** source file: the one the module's `# source: <repo>@<sha>:<path>` header names, in the clone `$<REPO>_DIR` or a directory `<repo>` next to the module or one of its parents (`../nimony`). A module without a header reads relative to itself. Not relative to the current directory |
| `{.emit: """C code""".}` | `emit("""C code""")` | `rule:emit`; raises in Python, so it belongs in a `when` branch that is inactive in the emulated build |

### 2.1 Rule: `if comptime` must mirror a `when` of the original Nim

This rule applies the unity principle (§0) to compile-time branches.

Every `if comptime(X)` in a converted module, with its `elif comptime(...)` and `else` branches, must correspond one to one to a `when X` (`elif`, `else`) of the original Nim source: same position, same condition in nimic spelling, every branch converted. The only exception is test code that the original source does not contain.

- **Keep every branch.** Convert all branches of the original `when`, including branches that are inactive on your machine or in the default build (`when defined(windows)`, GC- or backend-specific branches) and `when false:` / `when true:` (`if comptime(False):` / `if comptime(True):`). Do not resolve a `when` at conversion time by keeping one branch, and do not turn it into a runtime `if`: `when f is float32` is `if comptime(isinstance(f, float32))`, not `if isinstance(f, float32)`.
- **Same condition.** Translate the condition as written: `defined(x)` → `defined("x")`, a constant stays a constant (`when FileSystemCaseSensitive:` → `if comptime(FileSystemCaseSensitive):`, not `defined("FileSystemCaseSensitive")`), `isMainModule` → `__name__ == "__main__"`, `declared(x)` → `declared("x")`.
- **Exception: added tests.** Tests that the original does not contain, and the scaffolding they need (stand-in types and procs for dependencies that are not converted yet), go under `if comptime(__name__ == "__main__"):`, and only under that condition. They must run identically in Python and in the transpiled Nim, must not redefine, rebind or monkey-patch converted code (no `_py_*` copies, no `Class.method = ...`, no `setattr`/`globals()`), and must not shadow names that the module's imports provide. A `when isMainModule:` block of the original is converted like any other code; added tests come after it. If the block reads the command line (`paramStr(1)`), the module's header gives the arguments the tests run with, `# test-args: {tmp}/x.s.nif`. The verification passes them to the Python run and to the compiled Nim, with `{tmp}` an empty directory of each run's own. Include files are the exception: they have no test section, their tests live in a harness (see `include` above).
- **A program's entry module** whose top level runs the program (nifler2's `try: main() except: quit "…"`, no `when isMainModule`) puts that code under `if comptime(__name__ == "__main__"):` (transpiled `when isMainModule:`, the same for the program): the transpiler and the import checks import the module, which must not run the program. Its header says so, `# program: <why>`; the verification then runs the original program as it is (no tests appended), with the header's `# test-args:`. Decided 2026-11-07 (N54): it is Python's own entry point and fits a build from a `main.py` (nimiclang). nimicgen can't tell an entry module from the source alone: it is told which modules are programs (the programs hastur builds, or an option). **Where the guard starts** (canonical, decided 2026-11-08): at the first top-level statement that runs code (no declaration, import, comment, pragma or `when`), together with the `var` / `let` sections right above it that no routine reads; everything after it goes under the guard. The transpiler makes the guarded block a proc (`rule:mainproc`), where those sections are locals: the run's own variables, as the original's top-level run uses them. (Left above, they would be module globals; since `rule:global` the main proc's `assumeSync:` block lets it touch them under nimony, so the boundary is a canonical choice, not a necessity.) A section a routine reads stays above (`var verbose = false` read by `proc log`). A program module with its own `when isMainModule` is an error. The default header is `# program: the main block runs the program (the original runs it at its top level)`.
- **Never tell Python and Nim apart.** A condition whose purpose is to run different code in Python and in Nim is forbidden: `defined("c")` / `not defined("c")` (Python mode emulates the C-backend Nim build; `defined` is not a Python/Nim switch), `declared(X)` to supply missing types, `not (__name__ == "__main__")`, or any branch that exists for only one language. Needing such a switch means nimic lacks a feature: mark the spot `# TODO: requires nimic feature <name>`, write a proposal (`nimic-propose-feature` skill) and keep the original Nim structure.
- **Review check.** List every `comptime(...)` of the converted module and every `when` of the original; apart from the `__name__ == "__main__"` test guard they must pair up one to one. Run the module's tests in Python and as compiled Nim: the outputs must be identical.

Background and the list of nimic features still missing for this rule: `ncompiler/review_core_2026_10_16.md`.

**Template return** (`rule:templatereturn`): Inside a typed template, `return expr` is transpiled as just `expr` (no `return` keyword), matching Nim's template result semantics. In Nimic, write `return result` normally — the transpiler handles the transformation.

## 3. Structural Definitions (`rule:classdef`, `rule:typealias`, `rule:typedistinct`)
Classes and objects use standard Python `class` definitions but employ specific parent classes to signal type semantics to Nimic.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `type SomeType = object` | `class SomeType(Object):` | Base object type definition (`RootObj = Object`). |
| `type SomeType = object of BaseType` | `class SomeType(BaseType):` | Object inheritance via RootObj. Automatically inherits all fields from `BaseType` in MRO order. Supports subtype polymorphism in `@dispatch`. |
| `type SomeType = ptr object` | `@ptr class SomeType(Object):` | class definition should be decorated by `@ptr` for pointer types |
| `SomeType(x: 1, y: 2)` | `SomeType(x=1, y=2)` | Object instantiation |
| `type T = object`<br>&nbsp;&nbsp;&nbsp;&nbsp;`k: int = 5` | `class T(Object):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`k: nint = nint(5)` | Field defaults (Nim 2), also in a variant's branches: each new value gets its own copy of a default it isn't given (`T()`, `T(s=...)`, `default(T)`, `reset`, a nested object field); a copy or conversion takes the source's fields, and zeroed memory (`cast`, `alloc0`) has none. `= None` is no default (a nil ref, a legacy dummy discriminator default) |
| `type Time* = float64` | `Time = float64` | Type Alias (`rule:typealias`). Bidirectionally interchangeable with the target type in `@dispatch`. `class Time(float64): pass` transpiles the same and still works (the Nim 2 conversions use it), but the assignment is the canonical form (§13.5): it is the same Python type, as Nim's alias is |
| `type range[warnMin .. hintMax]` | `class MyRange(Trange[warnMin, hintMax]): pass` | Range subtyping definition (`rule:trange`) |
| `type MySet = set[TNoteKind]` | `MySet = Tset[TNoteKind]` | A set type alias (also `class MySet(Tset[TNoteKind]): pass`, see `type Time*`) |
| `type MySeq = seq[string]` | `MySeq = seq[string]` | A sequence type alias (also `class MySeq(seq[string]): pass`, see `type Time*`) |
| `(x: 1, y: 2)` | `SomeTuple(x=1, y=2)` | NTuple constructor transpiles to Nim tuple literal (`rule:tuplelit`) |
| `{}` | `Tset[T]()` | Empty set literal (`rule:setlit`). `Tset()` transpiles the same, but its elements have no type (canonical: `Tset[T]`, §13.5) |
| `{a, b, c}` | `Tset[T](a, b, c)` | Set literal with elements (`rule:setlit`); a single element too (`Tset[char](char('x'))`, `{'x'}`). `Tset(a, b, c)` transpiles the same |
| `{'-', '0'..'9'}` | `Tset[char](char('-'), inrange(char('0'), char('9')))` or `Tset[char]({char('-'), inrange(...)})` | Ranges in a set literal |
| `@[a, b, c]` | `seq[T]([a, b, c])` | Sequence literal (`rule:seqlit`). The element type is needed in Python: `seq([a, b])` transpiles, but doesn't run ("Seq type not specified") |
| `@[]` | `seq[T]([])` | Empty sequence literal (`rule:seqlit`), in every position; `seq()` doesn't run either. `seq[T]()` is a bare `var x: seq[T]` (`rule:varini`: `with var: x = seq[T]()`), not `@[]` |
| `tag(n) in ["call", "cmd"]` (an array literal as the operand of `in` / `notin`) | `_tag(n) in [string("call"), string("cmd")]` | Stays a Python list: the transpiler writes `[...]`, Nim's array literal, so the Nim is the original's. Nobody can change a literal that is only searched (N44, decided 2026-11-07) |
| `[byte 1, 5]` | `array[2, byte]([1, 5])` | Arrays (`rule:array`). Where the field or the annotation gives the type, the transpiler writes Nim's bare literal: `R(params=array[6, PatKind]([...]))` → `R(params: [...])`, `X = array[E, string]([...])` (a constant or variable: the conversion gives the type, so no annotation is written) → `X: array[E, string] = [...]`. Elsewhere (a call argument, an element, a `return`) it writes the conversion `array[N, T]([...])`, which keeps the index type, with a numeric first element typed (`[int8(-1), 2]`) |
| `type T = object` with `case kind: K` | `class T(Object):` with `kind: K` + `match kind:` | Object variants, see §11 (`rule:matchcase`) **(Nim 2: the Nim 3 version is in §14)** |
| `ar: array[1, string] = [0: "some"]` | `ar = array[1, string]({0: string("some")})` | Arrays initialized with a dictionary |
| `SomeTuple = tuple[x: int, y: float]` | `class SomeTuple(NTuple):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x: nint`<br>&nbsp;&nbsp;&nbsp;&nbsp;`y: float64` | Tuples should be defined as Named Tuple with an alias |

**distinct type** `type SomeType = distinct int` ➔ Must be decorated by `@distinct` on a class that inherits from the base type (`nint` for Nim `int`).
A distinct type is excluded from subtype matching in `@dispatch` (functions expecting the base type will reject it unless an explicit `@converter` is defined). Borrowed procs are declared as methods with `"""{.borrow.}"""` and can be called directly or via free-function UFCS dispatch:
```nim
  type otherint = distinct int
  proc `*`*(self: otherint, scalar: float64): otherint {.borrow.}
```
translates to
```python
  # Python Nimic
  @distinct
  class otherint(nint):
    def __mul__(self: otherint, scalar: float64) -> otherint:
      """{.borrow.}"""
      return super().__mul__(scalar)
```
A borrowed operator's body calls the base type's operator: `return super().__eq__(b)` for `` `==` ``, `return super().__str__()`
for `` `$` `` (Python's `str()` takes the base's text). A borrowed named proc calls it on the base value:
`func hash*(x: TagId): Hash {.borrow.}` is `return hash(uint32(x))` (§7, `hash`). Only the pragma reaches Nim
(`rule:funcdefbody`), so the body is Python's alone and has this one form.
**Enums (`rule:enum`) `type SomeEnum = enum`** ➔ `class SomeEnum(NIntEnum):`, e.g., for enumerations
```python
  # Python Nimic
  class SomeEnum(NIntEnum):
    sort1 = auto()
    sort2 = auto()
    sort3 = auto()
```
`auto()` in a `NIntEnum` counts from 0 like Nim (the first member is 0, each next one more than the previous), so writing the first member `= 0` is not needed; `default(E)` and a zeroed field are the first member.
An enum with string values (`warnUser = "User"`) is a `NStrEnum`: `$` of an `auto()` member is its name, and members with equal texts (`warnUser = "User", hintUser = "User"`) are distinct members, ordered by declaration.
A member with an explicit ordinal and text (`Cdecl = (ord(CdeclTagId), "cdecl")`, the tag models) is written the same way in a `NStrEnum`: `Cdecl = (ord(TagEnum.CdeclTagId), "cdecl")`. Ordinals increase strictly and may leave holes. A member without one is the previous ordinal plus one (`"text"`, `auto()`). `ord`, `E(ordinal)`, comparisons and stored fields use the ordinal, and `succ`/iteration follow the declared members. An `NIntEnum` takes explicit values the same way (`a = 2`). As in Nim, an enum with holes is no ordinal type, so it can't index an array (`TypeError`). An array indexed by an enum spans `ord(low)..ord(high)`.

**Generic distinct objects** `BiTableFloat*[Id] = distinct BiTable[Id, uint64]` ➔ `@distinct class BiTableFloat[Id](BiTable[Id, uint64]): pass`. `BiTableFloat[uint32]` is distinct (procs of `BiTable` don't take it) and derives from `BiTable[uint32, uint64]`. A conversion between a distinct object and its base, or between an object and its base type (`BiTable[Id, uint64](t)`, `BiTableFloat[uint32](b)`), is a view of the same value, as Nim's l-value conversion: `BiTable[Id, uint64](t).getOrIncl(x)` changes `t`. To keep a separate value, `.copy()` it.

**Types of one type section.** Consecutive classes are one Nim `type` section (methods are written after it), so a field may name a type declared later in the section (`PType.sym: PSym` before `class PSym`): the field resolves when the later type is defined, with that type's zero value (`nil` for a `@ref`). An alias naming a type declared later in its section (`Node* = ptr LinkedToken` before `LinkedToken* = object`, nifler2's linkedtok) is a `type` statement in the original's place, `type Node = ptr[LinkedToken]` before `class LinkedToken`: Python evaluates it lazily, so it may name the later class (the assignment form `Node = ptr[...]` would be a `NameError`). A field typed with it is the type's value in the class's memory layout (a pointer field: an arena of cells keeps its links), and once its value is a type the module binds the name to it (`seq[Node]`, `@dispatch` annotations). The transpiler writes `type` statements into the section of the classes next to them (`rule:classdefseq`). Writing the alias after the class instead is wrong: the fields would be typed before the alias exists

## 4. Functions and Arguments
Functions use standard Python `def` definitions but might employ specific decorators to mimic Nim semantics.

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| **Implicit `result` Variable** | `def foo() -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`result = nint(5)`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return result` | Nim's `result` variable is implicitly declared and returned. In Nimic, you must explicitly assign `result = ...` and write `return result` at the end. Note: There is no need to declare a default instantiation `result = Type()` if the value is defined or overwritten immediately on the next line! A declared `result` (`with var: result = v`) is written as the assignment `result = v` in a proc with a return type (`rule:resultvar`): a `var result` would shadow Nim's (nimony rejects it) |
| `discard foo()` | `_ = foo()` | Discarding a function call result |
| `proc foo(x: var SomeType)` | `def foo(x: mut@SomeType):` | Assigning new value requires `<<=`, e.g., `x <<= y` (not needed for attributes and array elements). |
| `proc s(p: BProc): var Builder` | `def s(p: BProc) -> mut@Builder:` | Mutable (`var`) return type, also in `@calltype` signatures (`rule:funcdefmut`). |
| `proc init(x: out T)` | `def init(x: out@T):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`x <<= T(...)` | `out` parameter (`rule:funcdefout`) |
| `proc addOrdered(t: var B; v: sink T)`, ``proc `[]`(t: B; i: Id): lent T`` | `def addOrdered(t: mut @ B, v: sink @ T)`, `def __getitem__(t: B, i: Id) -> lent @ T` | `sink` parameter and `lent` return type (`rule:funcdefsink`); in Python the value itself |
| `type InstantiationInfo* = typeof(instantiationInfo())` | `InstantiationInfo = typeof(instantiationInfo())` | `typeof(x)` as a type alias (`rule:typealias`); `instantiationInfo(-2, fullPaths = true)` gives the call site in Python too |
| `proc canonicalCase(path: var string)` (not exported) | `def _canonicalCase(path: mut@string)` | A private proc or template has a leading `_`. It transpiles to the original Nim name without `*` (`proc canonicalCase(...)`), and Python star imports don't re-export it. A private overload of a public name is written the same way: `def _abs(a: int32)` next to a public `abs` is Nim's private `proc abs(a: int32)`, `_addToHex(uint32)` next to `addToHex(Int128)` |
| `udata: array[4, uint32]` (a private field) | `_udata: array[4, uint32]` | A private field has a leading `_`, also in constructors and accesses: `Int128(_udata=[...])`, `a._udata[0]` transpile to `Int128(udata: [...])`, `a.udata[0]` |
| `proc `*`(a: Int128, b: uint32): Int128` (private operator) | `def __mul__(a: Int128, b: uint32) -> Int128:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.private.}"""` | An operator can't take a `_`: the `{.private.}` docstring pragma (`rule:privatepragma`) keeps it unexported in Nim and is not emitted. In Python the overload stays visible to other modules (Nim would reject such a call) |
| `proc `=copy`(dest: var Mangler; src: Mangler) {.error.}` (a lifetime hook: `=copy`, `=sink`, `=destroy`, `=wasMoved`, `=dup`, `=trace`) | `@hook("copy")`<br>`def _copyMangler(dest: mut @ Mangler, src: Mangler):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.error.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pass` | `rule:hook`: the Nim name is the hook's; the Python name only decides export. It is `<hook><Type>`, with `_` exactly when the original hook isn't exported (`_copyMangler`, `_copyTokenBuf`, `destroyCursor`): unique when a module has hooks of several types, and never `copy` / `destroy`, which would hide nimic's `copy()`. A call of the hook by that name (`destroyCursor(dest)`) is the hook's Nim call (`` `=destroy`(dest) ``). A module-level `def` right after its type, where Nim needs it (before the type's first use). When a hook calls a routine written after the class, the hooks come after that routine, and so do the routines that use them implicitly (methods rule, row `type T = object`). In Python one owning object is one Nim value: `=destroy` runs when CPython frees it or at the end of the `with block:` that declared it (not for views and casts); `.copy()` and stores (constructor, field, `seq.add`) run `=dup` / `=copy`; `a <<= b` runs `=copy`; `move(x)` runs `=wasMoved(x)`. A `=copy` with `{.error.}` makes the type move-only: stores move (share) it, `.copy()` is a `TypeError`. Python copies where Nim moves, so a count read in between can be higher (`ncompiler/proposals/feature_lifetime_hooks_runtime.md` §4) |
| `` `=destroy`(dest.openTags) `` (a direct call of a type's `=destroy`, e.g. a custom `=destroy` releasing its fields) | `hook.destroy(dest.openTags)` | `rule:hookcall`. A custom `=destroy` replaces the field-wise one, so it destroys its owned fields itself (nifcore's `TokenBuf`). Python: a value with a `=destroy` hook runs it now if it owns its value, and not again when CPython frees it; one without is destroyed field by field / element by element (an object's active fields, a seq's or array's elements), as Nim's built-in `=destroy`; a ref, nil or a scalar has nothing to run (CPython drops the reference with its holder: a shared object lives on, as Nim's count keeps it). A call of the module's own hook proc is still its Python name (`destroyCursor(dest)`, row above). Decided 2026-11-09 (N88): `hook.destroy` reserves no new name (`destroy` is a common user identifier) |
| `proc f(x: int): int` (forward declaration) | `def f(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pass` | A body of only `pass` (after an optional pragma docstring) is a forward declaration; the later definition replaces it in Python. Overloaded procs: both with `@dispatch` |
| `proc f(x: int) = discard`, `template t*(label: string) = discard` (an empty body) | `def f(x: nint):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`discard` | A body that does nothing is `discard` (nimic's no-op name, emitted as `discard`), never `pass`, which would make it a forward declaration (row above: Nim then wants an implementation). vfs's `dumpVfsProfile` without `vfsProfile` |
| `obj.f(a)` (method call syntax), `f(obj, a)` | `f(obj, a)` for a module-level proc, `obj.f(a)` for a method of the class | **The call syntax follows the Python definition.** A method of the class (the methods rule, row `type T = object` below; a `@property`; `@ufcs(T)`, which installs a method) is called as a method everywhere; a module-level proc or template is called free everywhere, also a block template (`with addCast(b, t):`), whatever the original's spelling: Nim's two spellings are one call, so the transpiled code means the same. Method syntax of a module-level proc is an `AttributeError`, whose message names the free call when the caller binds a routine of that name; without parentheses too (`b.count` is no bound proc). A free call of a proc whose name a parameter or a module-level value holds is the qualified call (`nifcore.kind(node)` next to a parameter `kind: NifKind`; §8.1 `shadowed`). A module calling a method of another module's class imports that module for Nim (§8: `from . import nifcore`), even when Python finds the method through the class. **User code calls its module-level routines free** (N72, decided 2026-11-07, applied to `nnimony/` 2026-11-08), also where the original writes method syntax: `srcPath.startsWithPath(stdlibRoot)` (`docpaths.nim:66`) is `_startsWithPath(srcPath, stdlibRoot)`, `w.b.addHeader(...)` is `addHeader(w.b, ...)`, `r.next(tok)` is `next(r, tok)`; chains nest (`a.f().g()` is `g(f(a))`), and the name is in the caller's import list (§8). A Python reader finds a method in its class, a free routine at its module. **Exempt: nimic's core and `nimic.std.*`**, decided by where the routine is defined: their routines on core types are the Nim system / std API (`s.add(x)`, `s.startsWith(p)`, `s.skipWhitespace(i)` under the shim's `@ufcs(string, aliases=…)`) and keep method syntax. **`@ufcs(T)` in user code** only on a module-level operator or `$` (`__eq__`, `__str__`: Python finds dunders only through the class), never driven by calls; and on a host shim standing in for a nimony system routine under `when not defined(nimony)` (`readRawData` in stringviews and nifreader, N80), which keeps the system API's method syntax (`s.readRawData()`). Which shims those are follows the original's calls (N87): a shim the module calls with method syntax (`s.readRawData()`, `r.thisModule.readRawData()`) is `@ufcs(T)`, first and alone (no `@dispatch`), its name not imported; one it calls free (`beginStore(result, n)`, `endStore`, `readRawDataStable`) is a plain `def`, called free like any user routine. Nim's two spellings are one call, so the transpiled code means the same; the round trip compares calls, not their spelling. `@ufcs` is the first decorator (`@ufcs(StringView)`, `@dispatch`) |
| `proc len*(b: TokenBuf): int {.inline.} = b.len` (a getter of a private field `len`) | `class TokenBuf(Object):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`_len: nint`<br>&nbsp;&nbsp;&nbsp;&nbsp;`@property`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def len(b: TokenBuf) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`"""{.inline.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`return b._len` | A `@property` that only returns the field of its name with a `_` is Nim's getter: the field `_len` and the property `len` don't collide (`rule:localname`), although both are `len` in Nim (in the module `b.len` is the field, elsewhere the proc: the same value). A property is one spelling, as any Python property: callers write `b.len` / `c.kind` everywhere, never `kind(c)` or `c.kind()` (there is no module-level `kind`), even where the original has the free call `kind(c)` (Nim's two spellings are one call, so the transpiled code means the same). The one exception is `len`, whose `len(b)` is Python's own protocol (below). A `len` the class declares (a `@property` or a method) also answers Python's `len(b)`, Nim's other spelling of the same call; an object of length 0 stays truthy. Every sized nimic value has `.len` (`seq`, `array`, `string`, `cstring`, `openArray`, `Tset`, the std/tables tables) |
| `foo(nil)` for `x: SomeRef` | `foo(None)` | `None` dispatches only to nilable parameter types: `@ref` classes, `ptr[T]`, `pointer`, `@calltype` procs. **(Nim 2: the Nim 3 version is in §14)** |
| `iterator myIter(x: int): int`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | |
| `proc foo(x:int)`<br>`proc foo(x:float)` | `@dispatch`<br>`def foo(...)` | "Static" dispatch. |
| `foo(x = 1)` | `foo(x = 1)` | Call and dispatch with keyword arguments. |
| `proc foo(x: int, y = 5)` | `@dispatch`<br>`def foo(x: nint, y = 5):` | Default parameter values are supported in `@dispatch`/`@template`; types are inferred (an integer literal is Nim's `int`, `nint`) and missing trailing arguments populated automatically. Arguments are bound per overload, so keyword calls may omit defaulted parameters (`addVar(b, kind=Local, name=n, typ=t)`), and an overload with defaults stays reachable when another overload has the call's arity. |
| `proc f(a: T, args: varargs[T])` | `def f(a: T, *args: T)` | `rule:varargs`; pass varargs or a seq on with `f(a, *args)` (Nim `f(a, args)`). A conversion, `varargs[string, $]`, is written `*args: varargs[string, str]` and needs `@dispatch` (it applies `$` to each argument) |
| `proc f(x: int \| int64 \| uint64)` | `def f(x: nint \| int64 \| uint64)` | A union is a type class for `@dispatch` (Nim `int or int64 or uint64`) |
| `type LengTagKind* = LengStmt \| LengExpr \| LengType` (a named type class) | `type LengTagKind = (LengStmt \| LengExpr \| LengType)` | `visit_TypeAlias`: Python's `type` statement is a `type` section. A parameter `expected: LengTagKind` takes a member of any of the types (`@dispatch`, templates), and `isinstance(expected, LengStmt)` (`when expected is LengStmt`) tells them apart. The assignment form `K = A \| B` (`rule:typealias`) works only when A and B are classes of the module or registered types (imported enums aren't), so use the `type` statement |
| `p.s(cpsStmts) = oldCode` (a proc returning `var T`) | `assign(p.s(cpsStmts), oldCode)` | `rule:assigncall`: Python can't assign to a call; `assign` assigns in place like `<<=` **(Nim 2: the Nim 3 version is in §14)** |
| `proc cmp*(a, b: Int128): int`, `proc abs*(a: Int128)` (a new overload of a system/imported proc) | `@dispatch`<br>`def cmp(a: Int128, b: Int128) -> nint:` | An overload set belongs to the scope defining it: the module, or the proc for a local `@dispatch` (Nim's local scope); a class's methods belong to its module, with its procs of the name. Created by the first `@dispatch` of the name, it overloads what the scope then binds to the name: an imported set (its overloads join), or a proc of another module (system, std, a plain nimic proc) or the builtins `abs`/`len`/`min`/`max`, which take the calls no overload matches, as in Nim. So a module sees the overloads its imports bring, not every overload of the name: nifstreams' `info(n: NifToken): PackedLineInfo` and nifpools' `info(n: NifToken): NifLineInfo` are two sets, and a module that imports the name from nifpools reaches nifpools' set (which includes the plain proc it extends); the proc's own module and its importers call the proc. A signature the scope defines itself wins over the same signature of an imported set, a local proc's over the module's (Nim's `cmpScopes`, nimony's `scopeBump`): nifstreams imports `info` from nifpools and its own `info(n: NifToken)` takes its calls; two imported sets with one signature are an ambiguous call. The core's modules (`nimic.ntypes`, `nimic.std.*`) share one scope: star imports bind their names, the last one would hide another core module's overloads. A generic proc's call of an overloaded name (bitabs' `getOrInclFromView[T]` calling `hash(v)`) reaches the name's overloads where it is instantiated too (Nim's open symbol): its specialization calls every module's overloads of the name, its own module's preferred |
| `template low*(t: typedesc[Int128]): Int128 = Min` | `@template`<br>`def low(t: typedesc[Int128]) -> Int128:` | A `typedesc[T]` parameter matches the type T itself (`low(Int128)`); other types still reach system `low` |
| `proc `<`*(a: BiggestInt, b: Int128): bool`, `proc `+`*(a: BiggestInt, b: Int128)` | `@ufcs(Int128)`<br>`@dispatch`<br>`def __lt__(a: BiggestInt, b: Int128) -> bool:` | Operators keep Nim's parameter order. `int64(3) < x` reaches the overload through Python's reflected call, and `x > y` / `x >= y` are `y < x` / `y <= x` (Nim's system templates). Operators that the methods rule keeps at module level are `@ufcs(T)`; a `$` (`__str__`) may return a nimic `string` |
| `when T is bool`, `when T is SomeUnsignedInt` (T a type parameter) | `if comptime(issubclass(T, bool)):` | `rule:isinstance` writes `T is X`; type classes `SomeInteger`, `SomeSignedInt`, `SomeUnsignedInt`, `SomeFloat`, `SomeNumber` work in `isinstance`/`issubclass` and dispatch. A union constraint `[T: SomeInteger \| bool]` is a type class |
| `proc ldexp(x: float64, exp: cint): float64 {.importc: "ldexp", header: "<math.h>".}` | `@importc`<br>`def _ldexp(x: float64, exp: cint) -> float64:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.importc: "ldexp", header: "<math.h>".}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pass` | In Python `@importc` calls that C function of the process (libc, libm) through ctypes, with the annotated scalar types; the transpiler drops the decorator |
| `f(5)` with `x: BiggestInt` | `f(5)` | A number literal takes the type of the parameter it is passed to (int64 here; for a generic `T` its binding) |
| `arg.sdata(3)` (a private proc or template) | `arg._sdata(3)` | Method-call syntax also finds private (`_`) procs of the caller's scope |
| `proc foo(...)` | `def foo(...)` | Methods of classes inheriting from `Object` are dispatched automatically. |
| `0 ..< a`, `a ..< b` | `range(a)`, `range(a, b)` | Range syntax. A half-open range is `range`, also in a `for` loop (`for i in 1..<s.len:` is `for i in range(1, s.len):`), never `inrange(a, b - 1)`: `range(a, b)` transpiles to `a ..< b`, and `b - 1` underflows for an unsigned `b` of 0. The transpiler writes Nim's operator itself (`rule:range`; nimony's `range` is system's type constructor): `range(n)` is `0 ..< n`. A step must be an int literal: `range(a, b, 2)` is `countup(a, b - 1, 2)`, `range(n - 1, -1, -1)` is `countdown(n - 1, 0)` (a literal bound is folded) |
| `a .. b` | `inrange(a, b)` | Inclusive range syntax, frequently used for sets (e.g. `Tset[TNoteKind](inrange(low, high))`). |
| `[a ..< b]`,  `[a ..^1]`, `[a ..< ^n]`, `[a .. b]`, `[a .. ^n]` | `[a:b]`, `[a:]`, `[a:back(n)]`, `[inrange(a, b)]`, `[inrange(a, back(n))]` | Slicing (`rule:slice`, N82): a Python slice is Nim's half-open `a ..< b`, `inrange` the inclusive `a .. b`; a bound counted from the end is `back(n)` (`^n`, len - n), in either form. A slice of a string is a string, of a seq, array or openArray a new seq of the elements' copies (Nim's `[]` of an HSlice). An empty slice (b < a) is fine; a non-empty one past the bounds is an `IndexDefect`, as in Nim 2 (nimony clips it: in its dialect nimic clips too). A negative int is no Python index from the end: it is out of bounds; no step. `[a:b + 1]` for `[a .. b]` is the older spelling. Under nimony the prelude adds the slices its system lacks (of an openArray or array) and makes `a ..< ^n` Nim 2's `a .. ^(n + 1)` (nimony's `..<`, `a .. pred(b)`, gives `^(n - 1)`) |
| `proc `+`(a: SomeType, b:int):` | `class SomeType(Object):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def __add__(self: static[SomeType], b: nint):` | Operator overloading via dunder methods. To avoid monkey-patching in Python, function definitions acting as operators or methods for a specific type should be included as methods within the class definition. The transpiler natively unpacks them to freestanding `proc`s. |
| `type T = object` ... `proc f*(x: T, k: int)`, `proc `==`*(a, b: T)` (procs of a type of the same module) | `class T(Object):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`...`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def f(x: T, k: nint):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def __eq__(a: T, b: T) -> bool:` | **Methods rule.** A proc, iterator, template or operator whose first parameter has a type defined in the same module (`var`, `sink`, `lent` and generic arguments aside) is written as a method of that type's class, if its whole Python definition (decorators, parameter and return annotations, default values, docstring pragmas and body) refers only to names already defined at the class's position in the Python module: what stands above the class (imports, constants, classes, module-level defs, and the methods of the classes above), the class itself and its fields, and the methods written before it in the class. Python's reading order is the definition order the module must respect; the transpiler emits the methods as procs right after the type section, where Nim needs the same. So a reference to anything below the class keeps the routine a module-level `def` at its original place: a later constant (`NoLineInfo`), a later proc or template, an import placed after the class, a class written after this one (also one of the same type section). An implicit use counts as a reference too: a routine that constructs a value of the class's type, copies one (`.copy()`, a `-> T` result copied from a shared value) or takes one as `sink @` refers to the type's lifetime hooks (`rule:hook`), and when they are written below the class it stays a module-level `def` after them. Nim binds an implicit hook at the first such use and then rejects the explicit one ("cannot bind another '=destroy' to: Cursor; previous declaration was constructed here implicitly"). Examples: nifcore's `+!` (`plus_bang`, builds a `Cursor`) and `peekPastEnd` (copies one), whose hooks call `_decRcAndFree`, defined after `Cursor`; treemangler's `extract(b: sink @ Mangler)`. Methods that only read the value or change it in place (`inc(c: mut @ Cursor)`) don't use the hooks. Keep the original order among the methods. An iterator of the class is a method like a proc (bif's `iterator declarations*(module: var BifModule)` is `def declarations(module: mut @ BifModule) -> _DeclarationsT:` in `class BifModule`, looped as `for d in m.declarations():`). A method is called as a method everywhere in nimic, `x.f(1)` (Nim's `f(x, 1)` and `x.f(1)` are the same call, so the transpiled code doesn't change); several methods of the same name in one class are an overload set (`@dispatch`); methods of the same name in different classes are not. An operator kept at module level, or `$`, is `@ufcs(T)` (`@ufcs(T)` `@dispatch` adds overloads to an operator the class defines). Enum classes, and `@distinct` scalars (`TagId = distinct uint32`), take their `$` (`__str__`, which may return a nimic `string`) as a method too. Exceptions, which stay module-level: procs of a type alias (`Rope = string`, `TBitSet = seq[ElemType]`: methods would make the alias a new type); a routine named like a field of its class (parserrt's `proc inSemiStmtList*(p: Parser): bool` next to the field `inSemiStmtList*: int`: Nim tells `p.inSemiStmtList` from `inSemiStmtList(p)`, a Python class holds one of them); an overload set of which one overload must stay module-level (an overload set isn't split: the module's own overloads of the name; a system, std or builtin proc of the name doesn't count, so `inc(c: var Cursor)`, `add(b: var TokenBuf, ...)`, `len(t: BiTable)`, `hash(x: StringView)` are methods, called `c.inc()`, `b.add(...)`; a `len` method may still be called `len(t)`, which nimic's `len` reaches, as the original spells it); a dirty template or one using its caller's variables (in nimony: written `{.dirty.}` or `{.untyped.}`, or assigning a parameter; it is expanded at free call sites); a lifetime hook (`rule:hook`); a proc used as a value (`s.isNil` with `s` the proc); a proc that an importer calls module-qualified (`rd.close(r)` after `import nifreader as rd`, `nifreader.close(r)` after `from nifreader import nil`), judged, like the whole rule, over the converted modules (the module and its converted importers: what nimicgen is given, so it decides the same): in Python a method is no attribute of its module, so `rd.close(r)` would be an `AttributeError`, and under `from m import nil` Nim rejects the method spelling `r.close()`. The qualified call keeps the original's spelling; the other calls of the proc are free (`close(r)`), or method calls under `@ufcs(T)` where the original spells them so (row `obj.f(a)`). Only the procs called qualified (and their overload sets) stay; the other procs of the class follow the rule. **An exception decided on a wider scope is marked.** A call in a module not converted yet (`rd.fileSize(r)` in nimony's `lengc/nifmodules.nim`) keeps a routine module-level only with `{.nimicModuleLevel.}` among its docstring pragmas (`"""{.inline, nimicModuleLevel.}"""`) and a comment above it naming the call. The pragma is a no-op of the prelude (`pydefs.nim`), so it reaches the transpiled Nim, which nimicgen reads, and nimicgen keeps such a routine module-level. The marker stays when that module is converted: it records the decision where it was made; a proc whose first parameter only selects the operation (`cOp(op: TypedBinaryOp, ...)`). Test scaffolding follows the Nim module each stand-in comes from (`types.skipTypes` on `astdef.PType` is not a method). Example: in `lineinfos`, `pack(m: var LineInfoManager; ...)` uses `LineInfoUnpacked`, a class written above `LineInfoManager`, and constants above both: it is a method; `isValid(x: PackedLineInfo)` uses `NoLineInfo`, a constant below the class: it stays module-level |
| `func foo(x:uint):` | `def foo(x:uint):` `"""{.noSideEffect.}"""` | function is proc without side effect **(Nim 2: the Nim 3 version is in §14)** |
| `proc `+`=(a: uint, b:uint):` | `def __iadd__(a: uint, b:uint):` | In-place operators in Python should return the modified object. |
| `proc `+`=(a: uint, b:uint):` | `def __radd__(a: uint, b:uint):` | Right-hand side binary operators swap arguments. |
| `converter toFloat(x: int): float` | `@converter`<br>`def toFloat(x: nint) -> float:` | Converter functions. |
| `iterator myIter(x: int): int = yield x` | `def myIter(x: nint) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`yield x` | Iterators are translated to generator functions. |
| `for (a, b) in pairs:` | `for (a, b) in pairs:` | Tuple unpacking in for-loops; parentheses preserved for Nim (`rule:fortupleunpack`) |
| `proc foo[T, U](): ...` | `@generic`<br>`def foo[T, U](): ...` | `@generic`: a generic proc called with explicit types, `foo[T, U]()`; the types bind `T` and `U` in its body (`BiTable[Id, T](...)` creates a `BiTable[uint32, string]`). Transpiler strips `@generic`. |
| `proc getOrQuit*[A, B](t: Table[A, B]; k: A): lent B`, `t.getOrDefault(k)` | `@dispatch`<br>`def getOrQuit[A, B](t: Table[A, B], k: A) -> lent @ B:`, `t.getOrDefault(k)` | std/tables: `Table[K, V]`, `OrderedTable[K, V]`, `TableRef[K, V]` are generic objects, so a generic proc binds `A`, `B` from them. They are three unrelated types, as in Nim (a proc over `Table[A, B]` doesn't take an `OrderedTable`). `getOrDefault(k)` is `default(V)` for a missing key |
| `s.split('.')`, `s.split({',', ';'})`, `s.split(" ")`, `s.split()` | `s.split(char('.'))`, `s.split(Tset[char](char(','), char(';')))`, `s.split(string(" "))`, `s.split()` | strutils `split`: a `seq[string]`; runs of separators are not merged (`"a  b".split()` is `@["a", "", "b"]`, unlike Python's `str.split()`) |
| `proc getKeyId[Id, T](t: BiTable[Id, T]; v: T): Id = ... Id(0)` | `@dispatch`<br>`def getKeyId[Id, T](t: BiTable[Id, T], v: T) -> Id:` | Nim instantiates every generic proc. In nimic `@dispatch` binds the type parameters from the arguments (structurally: `BiTable[Id, T]` matches `BiTable[uint32, string]`; a literal argument takes the bound type), so a body using them as values (`Id(0)`, `seq[Id]()`, `issubclass(T, string)`, `sizeof(T)`) needs `@dispatch`. An undecorated generic `def` runs with its type parameters unbound. **`@dispatch` exactly when:** the routine is one of an overload set of its scope (the module's own routines of the name, a class's methods of the name), a new overload of a routine the module binds by name from an import or the core (`plaindef`; not one reached only qualified, `from nifcoreparse import nil`), or a generic whose body uses a type parameter as a value. Not otherwise (bitabs' `hasId`, `ensureIndexed`, `BiTable.hash`). Never on a `@template`: templates of one name dispatch by themselves (`@template def _lowBits(x: uint32)` and `(x: uint64)`; bif's two `doAssert` arities); importers that see one name from two modules take an `overloads(...)` set (`rule:overloads`) |
| `(T1, T2)` (tuple type) | `tuple[T1, T2]` | Tuple type annotations in function return or variable types, aliases (`Key = tuple[string, string]`), object fields and seq elements transpile as Nim parenthesized tuple types `(T1, T2)` (`rule:tupletype`). A field defaults to the tuple of its elements' zero values; assigning or adding a tuple copies its value elements |

**Get/Set Operators (`rule:funcdefrenamedunder`)** Nim get/set operators map to Python dunder (magic) methods.
  - `[]=` ➔ `__setitem__`
  - `[]` ➔ `__getitem__`, for multi-argument operators, the arguments are packed into a tuple
  ```nim
  proc `[]`*(canvas: Canvas, row: SomeInteger, col: SomeInteger): Color {.inline.} =
    return canvas.pixels[row * canvas.ncols + col]
  ```
  ```python
    def __getitem__(canvas: Canvas, packed_tuple: tuple[SomeInteger, SomeInteger]) -> Color:
      """{.inline.}"""
      row, col = packed_tuple
      return canvas.pixels[row * canvas.ncols + col]
  ```

## 5. Memory and Pointers (`rule:dropbrackets`)
Memory primitives are strongly enforced to mirror Nim.
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `ptr SomeType` | `ptr[SomeType]` | |
| `p: ptr` | `p: ptr` | Bare `ptr` protocol in `@dispatch` matches any `ptr[T]`. |
| `ptr UncheckedArray[T]` | `ptr[UncheckedArray[T]]` | Bare `ptr[T]` cannot be indexed. |
| `pointer` | `pointer` | Untyped void pointer |
| `c_malloc(csize_t(size))` | `c_malloc(csize_t(size))` | allocators |
| `allocShared0(size)` | `alloc_shared0(size)` | shared memory allocator |
| `deallocShared(p)` | `dealloc_shared(p)` | shared memory deallocator |
| `alloc(n)`, `alloc0(n)`, `realloc(p, n)`, `realloc0(p, old, n)`, `dealloc(p)`, `create(T, n)`, `createU(T, n)`, `resize(p, n)` | the same names | Nim's allocator: blocks of raw memory seen through casts (`cast[ptr[UncheckedArray[T]]](alloc0(n))`). Python zero-fills `alloc` (Nim doesn't: don't read before writing). `dealloc` of anything but a block's start is a `ValueError` (Nim: undefined behavior); the pointer stays dangling, not nil. `realloc(nil, n)` is `alloc(n)`, `realloc(p, 0)` frees `p` and is nil |
| `GC_ref(x)`, `GC_unref(x)` | the same names | Keep a ref alive that only raw memory refers to. More `GC_unref`s than `GC_ref`s is a `ValueError` |
| a `ref` field of an object in raw memory (`owner.pool = b.pool` through `ptr CursorOwnerObj`) | the same | A ref field is nil by default. Every view of the memory (casts, derefs) reads the same ref. Written through a view of `alloc`'d memory, the slot keeps the ref alive until it is overwritten or the block is freed (`realloc` moves it along). `copyMem` copies a ref without keeping it alive, as in Nim; a ref that died behind a slot is a `ReferenceError` |
| `writeBytes(f, data, 0, len)` | `write_bytes(f, data, 0, len)` | writing bytes to file |
| `cast[int](p) + 4` | `cast[intp](p) + 4` | `intp` supports pointer arithmetic in nimic. |
| `cast[uint](p) + 4` | `cast[uintp](p) + 4` | `uintp` supports pointer arithmetic in nimic. |
| `while p < eof:`, `cast[pointer](r.p) >= r.f.data` (`p`, `eof`: pointers) | `while p < eof:`, `cast[pointer](r._p) >= r._f.data` | Pointers compare by address (system's `<` / `<=` of pointers; `>` / `>=` are its templates); nil is address 0 |
| `cast[LengStmt](tagEnum)`, `cast[TagEnum](uint32(id))` | the same | A cast to an enum is the member whose ordinal is the value's bits (an integer, or another enum's member); a hole in the enum's ordinals is a `ValueError` |
| `p[]`, `p[] = x` | `p.contents`, `p.contents = x` | Pointer dereferencing. A `ptr char` (or `ptr` of an enum) reads the slot on every access, as a container element does: `cast[ptr char](base + uint(i))[]` is `cast[ptr[char]](base + uint(i)).contents`, and a write through another path is seen |
| `p == q`, `p != nil`, `p.isNil` | `p == q`, `not isNil(p)` | Pointers compare by where they point: two casts of one address are equal. nil is address 0; an unset `ptr` field is nil. nimony's system has `isNil` for `cstring` only: the prelude adds it for `ptr`, `ref` and `pointer` |
| `array[3, float64]([1, 2, 3])`| `array[3, float64]([1.0, 2.0, 3.0])` | Nimic arrays use iterables as initialization payloads. |
| `addr x` | `addr(x)` | Maps natively using Nimic's variable aliasing mechanics. A standalone local integer or float gets storage of its own on `addr`, so pointers read and write it (`cast[ptr float32](addr(xi))[]` is `cast[ptr[float32]](addr(xi)).contents`). Dereferencing a pointer to an object whose address was taken gives the object itself, also after casts and pointer arithmetic (`cast[ptr[TokenBuf]](unsafe_addr(b)).contents is b`), so its Python-held fields (refs, pointers, seqs, the fields of a type with hooks) are shared, as the memory is in Nim |
| `cast[cstring](addr(L.buf[i]))` | `cast[cstring](addr(L.buf[i]))` | A `char*` into the middle of a buffer: a cstring sharing the memory of the string or buffer that contains the address, from there to its end **(Nim 2: the Nim 3 version is in §14)** |
| `unsafeAddr x` | `unsafe_addr(x)` | Equivalent to `addr x` in Nimic logic. |

## 6. Primitives & Typing
Because the transpiler is sensitive to Python's internal logic versus Nim's system macros, specific mappings apply:
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `bool` | `bool` | |
| `int` | `nint` | Nimic must NOT shadow Python's built-in `int` type. Use `nint` for Nim `int` type annotations, field types, parameter types, return types, and conversions (e.g. `nint(x)`). Integer literals (e.g. `0`, `1`, `42`) are standard Python literals and are allowed. Transpiles to Nim `int` (`rule:nint`). |
| `string` | `string` | `string` should be used instead of Python's `str` |
| `str1 / str2` (Paths) | `string(str1) / str2` | |
| `str1 & str2` | `str1 + str2` | String concatenation |
| `&"var: {x}"`, `fmt"var: {x}"` | `f"var: {x}"` | String interpolation (`rule:stringjoin`: `f` is written `&`); format specs (`{x:>5}`, `{f:.3f}`) mean the same in Python and Nim's strformat. Needs `from nimic.std import strformat` (Nim `import std/strformat`). `fmt"..."` is a raw literal in Nim, so a backslash in it is written `\\` in the f-string. A `bool` prints `True` in Python but `true` in Nim (G23) |
| `true`, `false`, `nil`, `Inf` |` True`, `False`, `None`, `inf` | Python's standard `inf` is `Inf` in Nim, bools transpile via `rule:lowercasebool`|
| `0x9e37...15'u64` | `u64(0x9e37...15)` | Numeric literal types. Only for literals: `u32(i)` is a transpile error, a conversion is `uint32(i)` |
| `'#'` | `char("#")` | Char literal: `char` of a one-char string constant (`rule:char`), as `string("x")` is a string literal; `char(x)` of anything else is a conversion. nimic has no `ch`: a module's own `ch` (nimlexer's `proc ch(L: Lexer; i: int): char`) is a name like any other |
| `None` (Nim keyword) | `None_` | Trailing `_` stripped by transpiler for Python keyword clashes (`rule:keywordescape`) |
| `hook`, `emit`, `back` (a Nim identifier nimic reserves) | `hook_`, `emit_`, `back_` | **Name collisions with the core** (`rule:reservedescape`): nimic reserves the names `from nimic.ntypes import *` binds that Nim doesn't have, its own vocabulary (`src/nimic/reserved.py`: `u8`…`f64`, `utf8`, `cell`, `inrange`, `nint`, `Tset`, `Object`, `dispatch`, `overloads`, `alias`, `hook`, `emit`, `pragma`, `importFrom`, `assign`, `back`, `subset`, the snake_case aliases `new_seq`, `copy_mem` …), and the Python builtins nimic's spelling uses with their Python meaning (`isinstance`, `issubclass`, `print`, `property`, `str`: std/parsejson's `proc str(my: JsonParser)` is `def str_(my)`, since `str(x)` is Nim's `$x`). A user identifier spelled like one is written with a trailing `_`, everywhere it occurs and whatever it names: a routine, type, field, parameter, local, enum member, an import's `as` name (`def emit_(info)`, `hook_: SymId`, `e.hook_`, `Entry(hook_=h)`). The transpiler drops the `_`; the mapping is deterministic and reversible, since a Nim identifier never ends with `_`. Unescaped, the name would shadow the core's binding in Python (for the module or the routine) and the transpiler would read some of them as nimic syntax (`u8(x)`, `cell(x)`). A nimic module that binds a reserved name unescaped is rejected at import and before transpiling (`check_reserved_names`); the core's own modules aren't checked. `$` of an escaped enum member is its Nim name, without the `_` (`Mode.alias_` and `Mode.None_` print `alias` and `None`; an `NStrEnum`'s `auto()` text too), as in Nim. Nim's own names (`len`, `add`, `echo`, `copy`, `push`) aren't reserved: a module's routine of such a name overloads system's (§4, `@dispatch`) |
| `"format: $1" % [arg]` | `string("format: $1") % [arg]` | String `%` operator transpiles as Nim `%` (formatting), not `mod` (`rule:strformat`): the left operand is a string literal, `string(...)`/`FormatStr(...)`, a name declared `string`/`FormatStr` (parameter, annotated or `string(...)`-assigned variable, also in an enclosing scope), or a call of a proc declared `-> string`; or the right operand is a list/tuple or a name declared as a seq/openArray/array/varargs of `string` |
| `chr(i)` | `chr(i)` | nimic's `chr` gives a `char` (Python's builtin gives a `str`); `RangeDefect` outside 0..255 |
| `succ(c)`, `pred(' ')` (a char) | `succ(c)`, `pred(char(' '))` | Also for chars; `RangeDefect` past `'\xFF'` or below `'\0'` |
| `$s` of a set, seq or array | `str(s)` | Nim's text: `{a, b}` (set, in ordinal order), `@[1, 2]` (seq), `[1, 2]` (array); strings and chars quoted with Nim's escapes (`@["a\"b"]`, `{'\n'}`) |
| `($x)[a..b]`, `($x).len` | `str(x)[a:b + 1]`, `str(x).len` | `rule:dollarparens`: a `str(...)` used as the base of an index or attribute is parenthesized in Nim |
| `b.put $i` (`$` passed to a `string` parameter) | `b._put(str(i))` | A Python `str` passed to a `string` parameter of a `@dispatch` proc arrives as a nimic `string`, as a number literal arrives as the parameter's scalar type. Elsewhere `str(x)` is a Python `str`: write `string(str(x))` where a nimic string is needed (`str(x).len`, a plain proc's parameter). A `str` stored in a `seq[string]` (`vals.add(str(v))`, `s[i] = str(v)`) becomes a nimic `string` |
| `except ValueError, OverflowDefect:` | `except (ValueError, OverflowDefect):` | Several exception types (`rule:exceptseveral`) |
| `Natural`, `Positive`, `range[0..4]` (parameter/return types) | `Natural`, `Positive`, `Trange[0, 4]` | Range types as annotations; values are not range-checked in Python yet (only `chr` and enum `succ`/`pred` raise `RangeDefect`) **(Nim 2: the Nim 3 version is in §14)** |
| `except CatchableError:`, `object of CatchableError` | the same | Nim's base of the catchable errors. It matches the classes nimic raises for them (Python's `OSError` for `IOError` / `OSError`, `ValueError`, `KeyError`, `EOFError`) and its own subclasses, not Defects or Python errors such as `AttributeError`. `newException(CatchableError, msg)` works |
| `delete(s, a..b)` (strutils, sequtils), `delete(s, i)` (system) | `delete(s, inrange(a, b))`, `s.delete(i)` | Removes the slice or the element, keeping the order. A slice outside `0 .. high(s)` raises `IndexDefect` |
| `RangeDefect` | `RangeDefect` | A `Defect`, not a `ValueError`: `except ValueError` doesn't catch it, as in Nim **(Nim 2: the Nim 3 version is in §14)** |
| `readFile(f)` | `read_file(f)` / `readFile(f)` | Reads binary-safe byte buffer into Nimic `string`. |
| `Path(str)` | `Path(str)` | `from nimic.std.paths import Path`. Supports `/` (`__truediv__`) and `os.PathLike` (`__fspath__`). |
| `dir / name`, `absolutePath(p)` | `dir / name`, `absolutePath(p)` | os' `/` (joinPath) of two `string`s or `Path`s, also inside `absolutePath`, normalizes as Nim's does: `.` dropped, `..` resolved against the head (`"a/b" / "../c"` is `a/c`, `"/" / ".."` stays `/..`), repeated `/` folded, the tail's trailing `/` kept |
| `s.skipWhitespace(i)` (UFCS on a std proc) | `s.skipWhitespace(i)` | Works when the Python std shim declares the proc with `@ufcs(string, aliases=("skipWhitespace",))`; std shims must not `setattr` methods onto core types. Python's own `str` methods (`find`, `rfind`, `strip`, …) are never shadowed — call the strutils proc as a function (`rfind(s, c)`) when Nim semantics differ |
| `type Snippet = string` | `Snippet = string` | `rule:typealias` (assignment form): a module-level `Name = <type>` is emitted in a `type` section (`type Snippet* = string`); `@dispatch` resolves it through the defining module's globals. `class Snippet(string): pass` is an alias too (a `string` subclass without members) |
| `== nil` / `!= nil` | `is None` / `is not None` | Python identity checks transpile as Nim nil comparisons (`rule:nilident`) |

### 6.1 Strings are bytes (`rule:latin1literal`, `rule:utf8literal`)
A Nim `string` is a sequence of bytes. A nimic `string`/`cstring`/`char` holds those bytes as a Python `str` *byte view*: one char per byte (code points 0–0xFF, i.e. Latin-1).

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `string` = bytes, `len` = byte count, `s[i]` = byte i | `s.data` is the Latin-1 byte view | `len(s)` and `s[i]` are byte-exact |
| `"\xE9"` (one byte) | `"é"` or `"\xe9"` | A bare non-ASCII char ≤ 0xFF *is* that byte; transpiles as `"\xE9"` (`rule:latin1literal`) |
| `"abc"` (a string literal) | `"abc"`, `string("abc")` | `string("abc")` transpiles as the bare literal (`rule:stringliteral`): nimony doesn't evaluate the conversion at compile time, e.g. in a `const` |
| `"é"` (UTF-8 bytes `C3 A9`) | `utf8("é")` | `utf8(text)` gives the UTF-8 bytes of Unicode text; a constant argument transpiles as the raw literal `"é"` (`rule:utf8literal`) |
| — | `"€"` (char > 0xFF) | Not a byte: `string("€")` raises `NimicEncodingError` (a `ValueError`); the transpiler raises `SyntaxError`. Use `utf8("€")` |
| `echo`, `readLine`, `write` (byte-transparent) | `print`/`echo`, stdio | Importing `nimic.ntypes` reconfigures stdin/stdout/stderr to Latin-1, so byte views are written as their exact bytes. Python-side text > 0xFF is still written as UTF-8. Opt out with env `NIMIC_NO_STDIO_RECONFIGURE=1` |
| `readFile`, `writeFile`, `lines`, `File` | same names | Binary I/O, no decoding |
| OS paths, env vars, `paramStr`, `getCurrentDir`, `walkDir` | `nimic.std.os` (the path procs are also method calls: `name.addFileExt(ExeExt)`, `p.isAbsolute()`, `p.changeFileExt("html")`); imported as `ncode/std/os` (`rule:stdbridge`), which under nimony adds the `string` forms of `removeFile`, `removeDir`, `createDir` (nimony's are on `Path`) | Paths are bytes on disk: `utf8("café.txt")` names the same file Nim's `"café.txt"` does |
| `std/unicode` (runes) | — | Not yet available: Unicode handling is explicit on UTF-8 byte views |
| `newString(n)` | `newString(n)` | `n` NUL chars, to be written in place |
| `L.buf = s.cstring`, `cstring(s)` | the same | Points into `s`'s buffer: `c[i] = x`, `copyMem`/`moveMem(addr c[i], ...)` change `s`, and changes to `s` are seen through `c`. After `s.setLen` the buffer may move: take the cstring again, as in Nim. A cstring of anything else is a copy. Reads stop at the first NUL; past the buffer `c[i]` is `'\0'` **(Nim 2: the Nim 3 version is in §14)** |
| `moveMem(dst, src, n)` | `moveMem(dst, src, n)` | Overlapping regions allowed |

Runtime boundary helpers (in `ntypesystem.py`, for std shims only): `_n_from_text` (Unicode text → byte view), `_n_to_text` (byte view → text), `_n_os_arg`, `_n_os_result`.

## 7. Operators and Logic (`rule:bitwiserename`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `and`, `or`, etc (binary) | `&`, `\|`, etc | Nim binary operators map to Python bitwise |
| `(if c: a else: b)` (an `if` expression) | `a if c else b`, as a result `return a if c else b` | An `if` expression is Python's conditional expression, also as a template's or proc's result (nifcdecl's `tagEnumOf`); `if c: a elif d: b else: e` nests, `a if c else (b if d else e)` (transpiled `if c: a else: (if d: b else: e)`). An original's `if` statement whose branches `return` stays an `if` statement. The transpiler writes the two differently (the expression on one line), so each spelling of the original is kept |
| `s[i] = c` | `s[i] = c` | Writes the char in place (`IndexDefect` past the end) |
| `for c in mitems(s): c = x` | `for c in mitems(s):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`c <<= x` | `mitems` of a string yields chars bound to their slots; `<<=` writes back (transpiled `c = x`) |
| `"$1 [$#] ${name}" % [a, b]`, `format(f, a, b)`, `s.addf(f, a)` | the same | strutils `%`, `format`, `addf` with Nim semantics (`$1`, `$#`, `$-1`, `${n}`, `$name` key/value pairs, `$$`; `ValueError` if invalid) |
| `a <% b`, `a <=% b`, `a >% b`, `a >=% b` | `lt_percent(a, b)`, `le_percent`, `gt_percent`, `ge_percent` | Unsigned comparisons (`rule:percentops`) |
| `x.isNil`, `quit(1)`, `quit("msg")` | `isNil(x)`, `quit(1)`, `quit(string("msg"))` | system procs. `quit` ends the process as Nim's does (the exit procs run, the output is flushed): it is no exception, so an `except:` or `finally` around it doesn't run (nifler2's `try: main() except: quit "…"` with a `quit` inside `main`) |
| `except: quit "cannot open: " & f & " (" & getCurrentExceptionMsg() & ")"` | `except:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`quit(string("cannot open: ") + f + string(" (") + getCurrentExceptionMsg() + string(")"))` | system proc: the message of the exception being handled, "" outside a handler (also in a routine the handler calls). Nim's `msg` (`newException`'s), else a Python exception's own message (an `OSError`'s text names the OS's reason, as Nim's does, in Python's wording). nimony has none (Nim 3's exceptions, §14): the original keeps it in a `when not defined(nimony)` branch (nifreader's `open`) |
| `newSeqOfCap[Node](16)` | `newSeqOfCap[Node](16)` | an empty `seq[Node]`; the capacity is a hint (nimic's seqs grow on `add`) |
| `s.addInt(x)`, `s.addFloat(f)`, `likely(c)`, `unlikely(c)`, `uint`, `cint`, `cuint` | the same | system (`addFloat` from `std/formatfloat`, shortest round trip as `$`); `fastLog2` from `std/bitops`; `trunc` from `std/math` returns a float as in Nim |
| `$x`, `s.addFloat(x)` (`x: float`, `float32`) | `str(x)`, `s.addFloat(x)` | Nim's float text (dragonbox; schubfach for `float32`): the shortest digits that round-trip in the type, written fixed while the decimal point lies within -6..17 places (`float32`: -4..9), an integer value with `.0` (`10000000000000000.0`, `0.0000001`, `123.0`), else `d.igitse±X` with an unpadded exponent (`1e+17`, `1e-8`, float32 `1e+9`); `nan`, `inf`, `-inf`. Python's `repr` differs (`1e+16`, `1e-05`): nimic's `float64` / `float32` write Nim's |
| `for i, x in s:` (implicit pairs), `for i, x in pairs(s):` | `for i, x in pairs(s):` or `for i, x in enumerate(s):` | `(index, item)` of a seq, array, string or openArray; `(key, value)` of a table (`pairs(t)`; also `t.keys()`, `t.values()`), in insertion order for an `OrderedTable`. `enumerate(s)` is an allowed deviation from the original, Python's own spelling of the index loop: it transpiles as written and Nim's `std/enumerate` (re-exported by `ncode/pydefs`) runs it, with the same `(int, item)` pairs. Its index is a Python `int` (`pairs` gives a `nint`). Not for a table (Python's `enumerate(t)` would number the keys) |
| `proc p(): tuple[dir: AbsoluteDir, name: string]` ... `result = (a, b)` | `class _SplitT(NTuple)` ..., `def p() -> _SplitT:` ... `return (a, b)` | A tuple literal returned from a proc declared to return a named tuple type becomes that type (`@dispatch`) |
| `$e`, `echo e` (enum member) | `str(e)`, `echo(e)` | The member's name (string-valued enums: the text) |
| `del t, key` | `t.del_(key)` | Python keyword: trailing `_` (`rule:keywordescape`) |
| `s.add((info, detail))` (seq of a named tuple) | `s.add((info, detail))` | A tuple literal becomes the seq's element tuple type |
| `MsgFlags* = set[MsgFlag]`, `flags: MsgFlags = {}` | `MsgFlags = Tset[MsgFlag]`, `flags: MsgFlags = Tset[MsgFlag]()` | A set literal names its element type, also where the location is typed by a set alias (§13.5). A call of the alias (`MsgFlags()`) is a set literal as well (`rule:setlit`), but not the canonical form: the original's `{}` doesn't name the alias |
| `s[s.len]` | `s[s.len]` | A string is `'\0'`-terminated: with bound checks off (`-d:danger`, `push boundChecks: off`) it reads `'\0'`, otherwise `IndexDefect`. Don't add Python-only bounds guards **(Nim 2: the Nim 3 version is in §14)** |
| `toFloat(i)`, `toInt(f)` | `toFloat(i)`, `toInt(f)` | system procs |
| `a == b` (objects, tuples) | `a == b` | Field-wise, as Nim's default `==`; refs compare as references. Object constructors copy value arguments |
| `x = y` (value type) | `x = y.copy()` | Where one of them is changed later while the other is read, and for a proc's `-> T` result that it shares: §1.1, checked (`rule:valuecheck`). `string`, `seq`, `array`, `Tset`, `Object` and the integer types (`nint`, `int64`, `uint8`, ...) have `.copy()`; reading an object field or array slot gives a view of it, so `oldBufLen = L.bufLen.copy()` before `L.bufLen = L.bufLen * 2`. Assigning an object, `a[i] = obj` and `s.add(v)` copy value fields/elements (strings, seqs, non-ref objects) and share refs, as Nim does. Values bound in `with const:` are frozen: changing one in place through an alias (`x = C` then `x += 1`, `x <<= y`, a field store) raises `TypeError` naming `C.copy()` |
| `x = y` through a `var` parameter | `x <<= y` | Works for objects, `string`, `seq`, `array`, `Tset` and the scalar cells (in place) |
| `var found = false` ... `p(found)` (`proc p(b: var bool)`), `var x = 0.0` passed as `var float` | `with var: found = nbool(False)` ... `p(found)`, `with var: x = float64(0.0)` | A Python `bool`/`float` can't be changed through a parameter: a variable passed as `var` is a cell, `nbool` (transpiles to `bool`, `rule:nint`) or `float64`, as `nint` is for `var int`. Object fields of type `bool` are cells already. Elsewhere Nim `bool` stays Python `bool` |
| `var res = osEmbedded` ... `findOS(name, res)` (`proc findOS(name: string; res: var TSystemOS)`) | `with var: res = cell(TSystemOS.osEmbedded)` ... `findOS(name, res)`; the callee assigns `res <<= i` | An enum member is immutable in Python: a variable passed as `var` of an enum type is a `cell` (`rule:cell`: transpiles to the member). It dispatches, compares, indexes arrays, prints and matches as its member, and storing it in a field, seq or array stores the member. `<<=` on a bare member raises `TypeError` instead of shifting. Ints, bools and floats have their own cells (`nint`, `nbool`, `float64`) |
| `echo a, b` | `echo(a, b)` | Nim semantics: `$` of each argument, no separator (`echo("n=", 3, true)` prints `n=3true`). An argument that isn't a string or a literal is written `$x` (`rule:echodollar`): nimony's echo doesn't apply `$` (a set, a seq) |
| signed integer overflow | `a + b`, `a * b`, ... | Raises `OverflowDefect` like Nim with overflow checks on (the default build); off with `-d:danger` (`NIMIC_DEFINES=danger`) or inside `with push("overflowChecks: off"):`. Unsigned types, `+%`/`-%`, shifts and bitwise operations wrap. Array indexes out of bounds raise `IndexDefect`. **Dialect:** code of a module or package that declares `__nimic_dialect__ = "nimony"` (`nnimony/__init__.py`) wraps instead, as nimony does: it has no overflow checks (`{.keepOverflowFlag.}` / `overflowFlag()` ask explicitly). nifler2's lexer relies on it (`-tok.iNumber` of `low(int64)` for `-9223372036854775808`, N63). The nearest declaration wins (the module, then its packages; `"nim2"` restores the checks); without one the checks are Nim 2's (`ncompiler/`, `tests/`). §13.3 |
| `isnot`, `notin` | `is not`, `not in` | |
| `(width + 15) shr 4 - 1` | `((width + 15) >> 4) - 1` | In Python bitwise operators have lower precedance than arithmetic operators | 
| `for item in arr.mitems:` | `for item in arr.mitems:` | In-place mutation loops translate directly, do not replace with `enumerate`. |
| `data[i] == ' '` (chars) | `ord(data[i]) == 32` | Python string chars don't map smoothly to Nim `char`. Use `ord()` for comparisons. |
| `not x` (bitwise) | `~x` | Nim bitwise `not` maps to Python bitwise inversion `~` (`rule:bitwiserename`) |
| `a +% b` | `plus_percent(a, b)` or `a.plus_percent(b)` | Nim wrapping addition in the operand type's width (`NInteger.plus_percent`; a plain `int` adopts its `NInteger` peer's type, else Nim `int`) (`rule:percentops`) |
| `a -% b` | `minus_percent(a, b)` or `a.minus_percent(b)` | Nim wrapping subtraction in the operand type's width (`NInteger.minus_percent`) (`rule:percentops`) |
| `h !& v`, `!$h` (std/hashes) | `mix_hash(h, v)`, `finish_hash(h)` | Nim std operators Python can't spell are named procs that transpile back to the operator (`rule:namedops`); `hashIgnoreStyle` uses the same Nim algorithm, so a hash built with `mix_hash` matches it |
| `hash(x)` (std/hashes) | `hash(x)` | Nim's values (the host Nim 2 std/hashes): every integer type, char, bool and enum (hashWangYi1 of the ordinal), floats, strings and `openArray[char]` (hashFarm), tuples and other openArrays (the elements mixed). A distinct type borrows it: `return hash(uint32(a))`. Objects, seqs and sets still hash by Python identity (to do) |
| `proc `+!`*(c: Cursor; diff: int): Cursor` (a custom operator of a converted module) | `@operator("+!")`<br>`def plus_bang(c: Cursor, diff: nint) -> Cursor:` | `rule:operator`: the proc gets a name in letters and `@operator` its Nim spelling. Python calls the name (`plus_bang(c, 1)`, `c.plus_bang(1)`); the transpiler writes the definition as `` `+!` `` and every call as the operator (`c +! 1`, with Nim's precedence; a one-argument call is the prefix form), also calls from other modules (through the registry). So the transpiled module has the original's names, and tests run against the original module. Older conversions name the operator only (`qq` for `` `??` ``, saturate's `sat_plus` for `` `|+|` ``, tinyhashes' `_mix_hash`): the transpiled module then defines and calls the letter name |
| `s[^1]`, `s[^n]` | `s[back(1)]`, `s[back(n)]` | Index counted from the end (`BackwardsIndex`, `rule:namedops`) for string, seq, array and openArray; a negative index is an `IndexDefect`, as in Nim |
| `astToStr(a)` (system) | `astToStr(a)` | The text of the expression; of a template parameter, the text of the call's argument. Python gives the Python spelling of the expression (`ast.unparse`, e.g. `cursorTagId(c)` where Nim renders `c.cursorTagId`): a diagnostic, which is all nimony uses it for (test messages, `onRaiseQuit`). The transpiler keeps `astToStr` |
| `ashr(x, y)` | `ashr(x, y)` | Arithmetic shift right of a signed integer, in `x`'s type (`NInteger.ashr`) |
| `a div b` | `a // b` | Nim integer division truncated toward zero (native on `NInteger`) |
| `a mod b` | `a % b` | Nim integer modulo truncated toward zero (native on `NInteger`) |
| `x is T` | `isinstance(x, T)` | Nim type query translates as `x is T` (`rule:isinstance`) |
| `cmp(a, b)` | `cmp(a, b)` | Standard three-way comparison `(a > b) - (a < b)` |
| `FormatStr(s)` | `FormatStr(s)` | Wraps format string for `%` operator; unwraps to string literal in Nim (`rule:formatstr`) |
| `move x`, `ensureMove x`, `wasMoved(x)` | `move(x)`, `ensureMove(x)`, `wasMoved(x)` | Nim ownership transfer. The source is left as `default(T)`, as in Nim: `s.add(move a)` empties `a`. A type with lifetime hooks is `=wasMoved`; strings, seqs, arrays, objects and scalars are copied and reset. A ref and an immutable Python value (an enum member) are returned as they are: Python can't nil the variable |
| `swap(t.keys, n)` | `swap(t._keys, n)` | system `swap`: both variables change in place (string, seq, array, set, object, field, the scalar cells); a Python literal or enum member is no variable (`TypeError`) |
| `toOpenArray(s, a, b)`, `toOpenArray(p, 0, n - 1)` (`p: ptr UncheckedArray[char]`) | the same | An `openArray[T]` view of positions `a..b` of a seq, array, string, openArray or ptr UncheckedArray; writes go to the source. Out of range: `IndexDefect` |
| `reset(x)` | `reset(x)` | `x` becomes `default(typeof(x))` in place (Object, string, seq, array, set, integer) |
| `inc(tok.tokType, 2)` (an enum) | `tok.tokType = succ(tok.tokType, 2)` | Nim's `inc` of an enum is `succ`; an integer's `inc(x, n)` is `x += n` |
| `shallowCopy(d, s)` | `shallowCopy(d, s)` | Assigns `s` to `d` in place (`d` must be a mutable nimic value) |

## 8. Exporting and Scope (`rule:writeexport`, `rule:localname`, `rule:modulepath`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `export nifcore, comesfrom` | `from . import nifcore, comesfrom`<br>`export(nifcore, comesfrom)` | `rule:writeexport`: the calling module's importers can import the modules' names from it (`from .nifcoreparse import TokenBuf`, nifcoreparse's `export nifcore`) and reach them qualified (`nifcoreparse.TokenBuf`), through the module's `__getattr__` (a name the module binds itself is its own). A module only: a symbol is `exportFrom` |
| `export nifcore except createTokenBuf, pool, addIdent` | `from . import nifcore`<br>`exportExcept(nifcore, "createTokenBuf", "pool", "addIdent")` | `rule:exportexcept`: operators by their Nim names, as `importExcept`. The module's importers get nifcore's names from it except those; a name the module defines itself is its own (nifpools defines all three) |
| ``export lineinfos.FileId, lineinfos.`==` `` (symbols of another module, an operator) | `exportFrom(lineinfos, "FileId", "==")` | `rule:writeexport`: the names of the module, operators by their Nim names (in Python a class's operators are its methods and come with the class) |
| Private names | `_` prefix (operators: `{.private.}`) | Identifiers defined **without** `*` in Nim (procs, templates, types, fields, module variables) are written `_name`; they transpile to `name` without `*` (`rule:localname`). Names starting with `__` or `_<digit>` keep a `local_` prefix. The transpiler rejects a module where dropping the `_` changes meaning (`private_name_collisions`): `_x` and `x` both defined in one scope (except overloaded procs, and `_base = f(base)` for a parameter `base` not used afterwards, i.e. Nim's `let base = f(base)`), or `x` used as a value after a private value `_x` (calls `x(...)` still find the proc in Nim). Rename then, e.g. `_pkgConf` |
| `import std/tables` | `from nimic.std.tables import Table, initTable` (the names read free), or `from nimic.std import tables` when none is | Module paths are translated: `nimic.x.y` → `x/y`, with module renaming (`rule:modulepath`) |
| `import ../options`, `import nifcore` (another nimic module) | `from ..options import ConfigRef, TOption`, `from .nifcore import Cursor, TokenBuf, beginRead` | `rule:import`: a nimic module is imported **by name**, its names listed (`nnimony/tools/explicit_imports.py` writes the list); nimic's std modules too (`from nimic.std.strutils import split`; `from nimic.std import strutils` when no name of it is read free, as Nim's import still needs it). Only the prelude `nimic.ntypes` (Nim's implicitly imported `system`) is star-imported. Python's star import would also bind what the module imported itself (no `nimic.std` module has `__all__`: `syncio`'s star bound Python's `os`, `sys`, `ctypes`), and a later star import would rebind a name (proposal `feature_module_scoped_dispatch.md`). Decided 2026-11-05 for `nnimony/`; `ncompiler/` and `tests/` still star-import std modules until they are migrated, which the import checks accept. A Python `from m import ...` is a full Nim `import m`; relative imports keep their level (one `../` per extra dot). A name the module only imports itself (not exported) is imported from the module defining it. The import checks (§8.1, at import and before transpiling) reject a star import of a nimic module (`starimport`), a name imported from two modules (`doubleimport`), a name imported from a module that only imports it (`notexported`), a plain `def` of an imported name (`plaindef`: write `@dispatch`), a core star import after a name import it rebinds (`importorder`), and a name the module calls free (imported by name, or bound by a core star import) while another imported module makes a different routine of it visible (`hiddenoverload`: Nim overloads them, write `f = overloads(a.f, b.f)`) |
| `msgs.message(...)`, `nimlexbase.EndOfFile` (qualified by module) | `from . import msgs`, then `msgs.message(...)` | `from . import m` binds the module name in Python and is `import m` (once at module level). A method of another module's type is called as a method (`nimlexbase.handleCR(L, pos)` is `L.handleCR(pos)`) |
| `import nifreader as rd`, then `rd.next(r, tok)`, `rd.ExpandedToken` | `from . import nifreader as rd`, then `rd.next(r, tok)` | `rule:import`: `from . import m as x` (also `from ..pkg import m as x`) is `import m as x`. A routine of a module imported only this way is called qualified, also where the original writes method syntax (N79, decided 2026-11-08): nifcoreparse's `r.firstUnusedName()` is `rd.firstUnusedName(r)`. Python binds only `rd`, so a free `firstUnusedName(r)` is unbound, and an extra `from .nifreader import firstUnusedName` would come back as a second Nim import |
| `import ".." / models / [leng_tags, tags]` then `export leng_tags` (modules of another directory used by name) | `from ..models import leng_tags, tags`, `export(leng_tags)` | A relative `from ..pkg import m` binds module names: `import ../pkg/m` (`rule:import`; unparse()'s `package` tells it from a name import `from .nifcore import TokenBuf`) |
| `import std/times` | `from nimic.std.times import DateTime, now` (the names read free) | A Python `from m import ...` is a full Nim `import m`: a class comes with its methods, which are procs in Nim |
| `memfiles.open(p)`, `memfiles.close(mf)` (a std module used qualified, e.g. where `open` would be ambiguous with syncio's) | `from nimic.std import memfiles`, then `memfiles.open(p)` | `from nimic.std import m` is `import std/m` (once; `as x` is kept) |
| `from std/times import utc, fromUnix` | `importFrom("nimic.std.times", "utc", "fromUnix")` | `rule:importfrom`: Nim's selective import; binds those names and the module's name (Nim's `from m import a` makes `m.b` valid too: nifindexes' `nifcoreparse.parse(...)`) |
| `from vfs import FileWriteMode, AlwaysWrite, OnlyIfChanged` (members of a non-pure enum) | `importFrom(".vfs", "FileWriteMode", "AlwaysWrite", "OnlyIfChanged")` | `rule:importfrom`: a name the module doesn't bind is looked up among the members of its enums, and the member is bound (then `mode: FileWriteMode = AlwaysWrite` works as written). A member of two enums is an `ImportError`: Nim picks it by the expected type, so write it qualified |
| `from nifcoreparse import nil` | `importFrom(".nifcoreparse")` | `rule:importfrom` without names: binds only the module's name, for qualified calls (`nifcoreparse.toString(c)`) |
| `import nifcore, nifbuilder` then `addIdent(b, s)` with `b` of either type (one name from two modules, called free) | `from . import nifcore, nifbuilder`<br>`addIdent = overloads(nifcore.addIdent, nifbuilder.addIdent)` | `rule:overloads`: a set over both procs, resolved by the argument types; the assignment emits nothing (Nim overloads the procs of its imports). The procs share their name; a plain proc needs all its parameters annotated. Without it the import check reports `hiddenoverload` (§8.1); a qualified call (`nifcore.addIdent(b, s)`) needs no set. A signature both sets define is an ambiguous call (`TypeError`, as Nim's). When one module's set already includes the other's (nifpools' `writeFile` extends syncio's; nifbuilder's and nifreader's `@dispatch` `close` extend syncio's), import the name from that module instead: `from .nifbuilder import close`, no `close = overloads(syncio.close, nifbuilder.close)`. A set is still needed where a later import rebinds the name (foreignmodules' main block star-imports syncio after importing `close` from nifreader); the import check (`hiddenoverload`) tells. A name a set binds is not also imported by name (`from .nifbuilder import addHeader`, not `addHeader, addStrLit`, with `addStrLit = overloads(...)`). A set lists each proc once, by the module that defines it: a module re-exporting it (`nifcoreparse`'s `export nifcore`) adds no member. It is written at the top level where its modules are imported; a main block's import that brings no new proc of the name neither moves nor extends it (lengiface: `addStrLit = overloads(nifcore.addStrLit, nifbuilder.addStrLit)` at the top level, its main block's `nifcoreparse` adds nothing) |
| `import ropes except `%`` | `importExcept(".ropes", "%")` | `rule:importexcept`: the module's public names except the given ones (operators have no Python name) |


### 8.1 Name resolution (`rule:import`)

Nim resolves a name among the symbols visible in the module; Python binds one object per name. nimic code must make
the two agree. The rules below are what `nimic/imports.py` implements and what the import checks
(`transpiler.import_problems`, at import and before transpiling) enforce. `nnimony/tools/explicit_imports.py` uses
the same definitions.

**Definitions**, for a name `n` that module `M` reads (a free call, a value, an annotation):

| Term | Definition |
| --- | --- |
| **own(M, n)** | `M` defines `n` at its top level, also in `when` branches and in the files it includes: a plain `def`, an overload set (`@dispatch`, `@template`), a class, a variable or constant. `n = overloads(...)` defines nothing: it binds imported procs |
| **imports of M** | Every Python import of a nimic module is a full Nim import of it: `from .nifcore import TokenBuf`, `from . import nifcore`, `import nifcore` (and the core's star imports). `importFrom(".m", "a")` limits it to `a`, `importExcept(".m", "a")` hides `a`. The imports of `M`'s main block count only when `M` is the main program |
| **exports(I, n)** | What Nim's import of module `I` brings as `n`: `I`'s own non-private `n` (a `_name` is never exported), and, recursively, what `I` re-exports with `export(m)`, `exportFrom(m, "n")`, `exportExcept(m, ...)` minus the hidden names. A module that isn't nimic (the core, Python's) exports what it binds |
| **V(M, n)**, Nim's view | own(M, n) plus exports(I, n) for every import `I` of `M`, one entry per distinct object |
| **B(M, n)**, Python's binding | `M`'s global `n` once its imports have run: the last name import or core star import that binds it. An own `@dispatch`/`@template` set then extends B; an own plain `def` replaces it |
| **B reaches X** | `B is X`, or `B` is an overload set that includes `X` (its overloads, the sets it includes, the proc it extends) |

**The rule:** for every name `M` reads, B(M, n) must reach every routine in V(M, n), and a type or value in V(M, n)
must be B(M, n) itself. Each way to break it has its own report:

| Report | When | Fix |
| --- | --- | --- |
| `hiddenoverload` | B (a name import, a core star import) doesn't reach another visible routine of `n` | `n = overloads(a.n, b.n)` (Nim overloads them; the line emits nothing) |
| `ownset` | an own `@dispatch`/`@template` `n` extends a B that misses a visible routine | bind `n = overloads(...)` before the set |
| `plaindef` | an own plain `def n`, called by `M`, while an import makes a routine `n` visible, a core proc too (nifreader's `open` next to syncio's): Python replaces, Nim overloads. Not a def under `if comptime(not declared("n")):` (Nim `when not declared(n)`) | `@dispatch` |
| `notexported` | B is an object no import of `M` exports (`from .m import x` where `m` only imports `x`) | import it from the module defining it |
| `unbound` | `M` reads `n`, Nim's imports bring it, Python binds nothing | import it |
| `ambiguous` | a type or value `n` of several imports (Nim reports an ambiguity) | import one of them qualified |
| `qualified` | `m.f` reaches one routine while Nim's `m.f` overloads those `m` exports | `f = overloads(...)` in `m` |
| `shadowed` | a free call `f(x)` of a name that a proc's parameter (of a type that is no proc) or a module-level value holds, while Nim sees a routine `f`: Nim's call resolution passes over a symbol that is no routine (nifqueries' parameter `kind: NifKind` next to the proc `kind`), Python calls the value | the qualified call `nifcore.kind(x)` (the same call in Nim) |

Import hygiene, checked too: `starimport` (a star import of a nimic module that isn't the core: it also binds what
that module imported), `doubleimport` (one name imported from two modules), `importorder` (a core star import
rebinding a name imported before it; only `ncompiler/` and `tests/` still star-import std modules, it goes
once they are migrated).

**Not checked:** a name imported but not read (no call can reach the wrong proc); duplicates within the core itself (std/os's `fmRead` next to syncio's);
dynamic access (`getattr(m, "f")`, `globals()`), which Nim has no equivalent of. The checks can't see argument types:
they report a visible overload even when every call takes the bound one's types.

## 9. Callable type (`rule:calltype`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `type`<br>`Name* = proc(x: int): int` | `@calltype`<br>`def Name(x: nint) -> nint: pass` | |
| `cleanup: proc (b: var VfsBlob) {.nimcall.}` (a proc type without a name: a field of `VfsBlob`, a parameter, a result, a variable or a `cast` type) | `@calltype(inline=True)`<br>`def _VfsBlobCleanup(b: mut @ VfsBlob):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.nimcall.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;`pass`<br>`cleanup: _VfsBlobCleanup` | `rule:calltypeinline`: declares no Nim type; every use of `_VfsBlobCleanup` is written as `proc (b: var VfsBlob) {.nimcall.}`. The name must be private (`_`): an importer would have no type to name. Python treats it as any calltype. **The name** (canonical, N73, decided 2026-11-08) comes from the type's first use in the module, each part with its first letter upper-cased: `_<Object><Field>` for a field (`_VfsBlobCleanup`), `_<Routine><Param>` for a parameter (`_InitBlobCleanup`), `_<Routine>Result` for a result type, `_<Owner><Var>` for a variable (the routine or type it is declared in; `_<Var>` at the module's top level); `Proc` is appended when the name is taken (by another inline calltype or a name of the module). The same type spelled again (the same parameters, result and pragmas) reuses the first name (vfs's `initBlob(…, cleanup: proc (b: var VfsBlob) {.nimcall.})` takes `_VfsBlobCleanup`). The def stands right before the top-level statement of its first use (a method's: before its class) |
| `var r*: proc (p: string): int {.nimcall.} =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`proc (p: string): int = len(p)` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`def r(p: string) -> nint:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`"""{.nimcall.}"""`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`return len(p)` | A proc variable initialized with an anonymous proc (`rule:procvar`, also `with let:`): the def's signature is the variable's type, the docstring pragma the type's, the body the anonymous proc's. Swap the proc by assigning it (`r = other`), never by a second `def r` (Python would rebind it silently, Nim reports a redefinition; the transpiler rejects it). `with const:` doesn't take a def. **Gap:** a write to another module's variable (a driver setting `vfs.openMmapRelay`) has no form yet: after `from vfs import *`, `openMmapRelay = mine` rebinds only the importer's name |

## 10. Block Statements (`rule:block`, `rule:dropwith`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `block:` (statement) | `with block:` | A scope. At its end (also of `with block("name"):`) the variables it declared end their lifetimes, as in Nim: owning values with a `=destroy` hook are destroyed, the last declared first. A value that escapes (returned, bound to an outer variable) is left to CPython, as Nim moves it out |
| `block:` (value return) | `def _block():`<br>&nbsp;&nbsp;&nbsp;&nbsp;`return val`<br>`result = _block()` | Emulate value-returning blocks with immediately invoked localized functions. |
| `do:` | `with do:` | Nim `do:` block statement (`rule:doblock`) |
| `block search:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`... break search` | `with block("search"):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`... breakBlock("search")` | Labeled block (`rule:labeledblock`) |


## 11. Variant type and `case` statements (`rule:matchcase`, `rule:uncheckedassign`)
- **`case` statements** ➔ `match` statements

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `case c`<br>`of 'a'..'z', 'A'..'Z', '_':` | `match c:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`case _ if c in inrange(char('a'), char('z')) or c in inrange(char('A'), char('Z')) or c == char('_'):` | Ranges, values and set constants (`c in routineDefs`) of one `of` branch: a guard on the subject joined with `or`. A char value needs a guard (`c == char('_')`) since `case "_"` is a string |
| `of nkEmpty..pred(nkSym), succ(nkSym)..nkNilLit:` | `case _ if n.kind in inrange(TNodeKind.nkEmpty, pred(TNodeKind.nkSym)) or n.kind in inrange(succ(TNodeKind.nkSym), TNodeKind.nkNilLit):` | Enum ranges likewise |
| `elif cond:` (branch of a `case`) | `case _ if cond:` | Any other guard is an `elif` branch |
| `proc p(s: string): Cmd =`<br>&nbsp;&nbsp;`case s`<br>&nbsp;&nbsp;`of "sug": ideSug`<br>&nbsp;&nbsp;`else: ideNone` | `def p(s: string) -> Cmd:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`match s:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case "sug": return Cmd.ideSug`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case _: return Cmd.ideNone` | `case` expression as the proc's result (`rule:casereturn`): a body ending with a `match` whose every branch is `return <value>` |
| `let bitsPerDigit = case base`<br>&nbsp;&nbsp;`of base2: 1`<br>&nbsp;&nbsp;`else: raiseAssert "unreachable"` | `with let:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`match base:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case NumericalBase.base2: bitsPerDigit = 1`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case _: raiseAssert(string("unreachable"))` | `case` expression assigned to a variable (`rule:caseassign`): a `match` directly inside `with let:`/`with var:`/`with const:` whose every branch ends by assigning the same name, or with a raise or a call that doesn't return. Also for `var` |
| `emitStr p, (case k of tkInt8Lit: "i8" else: "i64"), info` (a `case` expression as an argument or operand; `proc emitStr(p: var Parser; s: string; info: NifLineInfo)`) | `with let:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`match k:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case TokKind.tkInt8Lit: s = string("i8")`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`case _: s = string("i64")`<br>`emitStr(p, s, info)` | A `case` expression anywhere but a binding's or a `return`'s value is bound first (`rule:caseassign`) right before its statement, and the statement reads the name: Nim keeps the `case` (its exhaustiveness check), which a conditional expression would lose. Arguments before it that have side effects are bound first too, in order, so the evaluation order stays. The round trip gives back this form, not the original's nested one (N42, decided 2026-11-07). **The bound name** (canonical, decided 2026-11-08): the callee's parameter at that position, when the module defines the callee with one signature (`s` above; for `p.emitStr(…)` the parameters after the receiver), else `value`; when the routine already uses the name (any identifier of the routine, in any branch), the first free of `name2`, `name3`, … (parserrt's `emitLeaf`, which has a local `s`: `s2`, `s3`, `s4`). A name that is a Python keyword or a reserved name gets its `_` (`rule:keywordescape`, `rule:reservedescape`). Mechanical, so nimicgen writes it and the round trip compares equal |
| `let expanded = try: expandFilename(dir) except: dir` | `with let:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`try:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`expanded = expandFilename(dir)`<br>&nbsp;&nbsp;&nbsp;&nbsp;`except:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`expanded = dir` | `try` expression assigned to a variable (`rule:tryassign`): a `try` without `else` / `finally` directly inside `with let:`/`with var:`/`with const:` whose body and handlers all end by assigning the same name; a handler may end with a `raise` or a call of a `{.noreturn.}` proc instead: system's `quit` / `raiseAssert`, or a proc of the module whose docstring has `{.noreturn.}` (another call doesn't count: it may return), or an `if` / `when` whose every branch, an `else` included, ends so (nifreader's `open`: `when defined(nimony): quit … else: quit …`). `let f = try: vfsOpenMmap(filename) except: quit "..."` is `with let:` / `try: f = vfsOpenMmap(filename)` / `except: quit(...)`. A `try` inside a larger expression, `result = (try: a except: b) / c`, is a `try` statement assigning the target, then `result = result / c` |
| `proc readBytes(p: string): string =`<br>&nbsp;&nbsp;`try: readFile(p) except: ""` | `def readBytes(p: string) -> string:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`try: return readFile(p)`<br>&nbsp;&nbsp;&nbsp;&nbsp;`except: return string("")` | `try` expression as the proc's result (`rule:tryreturn`): a body ending with such a `try` whose branches end with `return <value>` (or a `raise`) |
- **variant types (case objects)** ➔ `Object` with a `match` on the field declared immediately before it
```nim
  NodeObj* = object
    info*: int
    case kind*: NodeKind
      of nkInt: intVal*: int
      of nkAdd, nkSub:
        leftOp*, rightOp*: Node
      of nkIf:
        cond*: Node
        case hasElse*: bool
        of true: elsePart*: Node
        of false: discard
      else: discard
    tail*: int
```
translates in nimic Python as
```python
class NodeObj(Object):
    info: nint
    kind: NodeKind              # no dummy default needed
    match kind:
        case NodeKind.nkInt:
            intVal: nint
        case NodeKind.nkAdd | NodeKind.nkSub:
            leftOp: Node
            rightOp: Node
        case NodeKind.nkIf:
            cond: Node
            hasElse: bool
            match hasElse:
                case True:
                    elsePart: Node
                case False:
                    pass
        case _:
            pass
    tail: nint
```

| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| `case kind*: K` | `kind: K` then `match kind:` | The discriminator needs no default (a legacy `= None` is accepted and dropped by the transpiler) |
| `of A, B:` | `case K.A \| K.B:` | |
| `else:` | `case _:` | Must be the last branch |
| `discard` (empty branch) | `pass` | |
| nested `case` inside a branch | nested `match` inside a `case` | |
| — | — | Every field of every branch is part of the type; names must be unique across branches. Methods and guards are not allowed inside branches. The class must live in a `.py` file (its source is read once at definition) |
| `T(kind: nkAdd, leftOp: x)` | `T(kind=K.nkAdd, leftOp=x)` | Discriminators are set first; an omitted one takes its zero value (`low(K)`, `False`); only the selected branch's fields exist and are zero-initialized |
| `FieldDefect` | `FieldDefect` | Reading/writing a field of an inactive branch, or passing it to the constructor: `field 'x' is not accessible for type 'T' using 'kind = nkInt'` |
| `x.kind = nkSub` (same branch) | `x.kind = K.nkSub` | Allowed when the active branch does not change; otherwise `FieldDefect("assignment to discriminant changes object branch")` |
| `x[] = T(kind: nkInt, ...)` | `x <<= T(kind=K.nkInt, ...)` | Replacing the whole object may change the branch (also `copy()`) |
| `{.cast(uncheckedAssign).}:` | `with uncheckedAssign:` | Branch-changing discriminator assignment; union memory is reused, newly active python-side fields are defaulted (`rule:uncheckedassign`) |
| C layout | — | Common fields, the discriminator, then a union of one struct per branch: `sizeof` = common + largest branch; `seq[T]` elements share that stride |
| `of 'a'..'z':` (range branch) | — | Not supported yet |

## 12. Closures, Nonlocal and Global Scope (`rule:nonlocal`, `rule:global`)
| Nim | Python (Nimic) | Notes |
| --- | --- | --- |
| (implicit capture) | `nonlocal x` | Nim closures capture outer scope variables by reference automatically. In Python, mutating captured outer variables requires `nonlocal x`, which the transpiler suppresses (`rule:nonlocal`). |
| `var runs = 0` (module level)<br>`proc step() =`<br>&nbsp;&nbsp;&nbsp;&nbsp;`{.cast(assumeSync).}:`<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`inc runs` | `with var:`<br>&nbsp;&nbsp;&nbsp;&nbsp;`runs = nint(0)`<br>`def step():`<br>&nbsp;&nbsp;&nbsp;&nbsp;`global runs`<br>&nbsp;&nbsp;&nbsp;&nbsp;`runs += 1` | **A routine touching a module's mutable global** (`rule:global`, decided 2026-11-08) declares it `global`, whether it assigns it or only reads it: Python needs `global` to assign a module-level name (an assignment anywhere in a function, `=`, `+=`, `<<=`, makes the name local: `UnboundLocalError`), and nimony rejects any access to a mutable global outside `{.cast(assumeSync).}` ("unsynchronized access to global variable"). The transpiler drops `global` and runs the routine's statements after it in an `assumeSync:` block, the prelude's template: `{.cast(assumeSync).}:` under nimony, the plain statements in Nim 2 (which has neither the check nor the cast). So `global x` and nimony's cast stand for each other: the original's `{.cast(assumeSync).}:` around a routine's statements is `global` with the names it touches (a narrower cast block comes back covering the routine's statements after the `global`). A module with `pragma('feature: "assumeSync"')` (nimony's `{.feature: "assumeSync".}`, e.g. `programs.nim`) gets no block: the feature covers every routine; `global` is still written where Python assigns. A main block's proc (`rule:mainproc`) runs in an `assumeSync:` block too: in nimic it is top-level code, which may touch globals |

## 13. nimony modules

### 13.1 Source and target

| | |
|---|---|
| Source | the nimony clone next to the project (`../nimony`, or `NIMONY_DIR`), at `2c5b3dca14667398bef077edea2d036dd0ff949e` (master, 2026-11-09); the pin is `NIMONY_PIN` in `nnimony/tools/queue.py` |
| Target | `nnimony/` mirrors `src/`: `src/lib/bitabs.nim` → `nnimony/lib/bitabs.py`, `src/models/tags.nim` → `nnimony/models/tags.py` |
| Queue | `nnimony/conversion_queue.md`, generated by `python -m nnimony.tools.queue` |
| Agent briefs | `nnimony/brief_<name>.md` |

### 13.2 Module layout

| Nim (nimony) | Python (nimic) | Notes |
| --- | --- | --- |
| a module `src/lib/bitabs.nim` | `nnimony/lib/bitabs.py`, starting with `# /// nimic`, `# source: nimony@<sha>:src/lib/bitabs.nim`, `# ///`, then the original header comments | Every module records the commit it was converted from. A re-pin is applied as upstream diffs since that commit |
| `import std/assertions`, `import std / [hashes, tables]` | `from nimic.std import assertions`, `from nimic.std.hashes import hash` ... | nimony's `src/config.nims` makes a missing `std/` prefix an error (`StdPrefix`); nimic's std imports transpile with the prefix |
| `import bitabs` (a sibling) | `from .bitabs import *` | |
| `import ".." / models / [tags]`, `import ".." / lib / [vfs, nimversion]` | `from ..models.tags import *`, `from ..lib.vfs import *` | One `from` per module; paths keep nimony's directories |
| `when defined(nimony):` / `when not defined(nimony):` | `if comptime(defined("nimony")):` / `if comptime(not defined("nimony")):` | Converted with every branch, like any `when` (§2.1). Python runs the host-Nim (Nim 2) build, where `nimony` is not defined |
| `proc `!&`(h: UHash; val: uint32): UHash` (a custom operator) | `@operator("!&")`<br>`def _mix_hash(h: UHash, val: uint32) -> UHash:` | Custom operators get letter names and `@operator` (`rule:operator`, see §6); a private one has a `_` and transpiles to `` proc `!&` `` without `*` (`nnimony/lib/nifcore.py`'s `plus_bang`; `nnimony/lib/tinyhashes.py` predates `@operator`) |

### 13.3 Build profile

- **`nnimony/nim.cfg`** mirrors nimony's `src/config.nims`: `define:nimPreviewSlimSystem` and
  `experimental:strictDefs`. Python runs read it as the `nim.cfg` of `nnimony/`.
- **The Nim checks** build in a copy of nimony's `src/`, which carries the original `config.nims`.
- **The dialect** (`nnimony/__init__.py`: `__nimic_dialect__ = "nimony"`): nimony's semantics where they differ from Nim 2's and Python can follow them without nimony's library: signed arithmetic wraps (no `OverflowDefect`, §7). Python still runs the Nim 2 branches of `when defined(nimony)` (§13.2): their nimony branches need nimony's std in nimic (`std/posix`, nimony-only procs), a later step toward a nimony build profile. Decided 2026-11-07 (N63).

### 13.4 Tests and verification

- **Tests:** a module's tests go at the end, under `if comptime(__name__ == "__main__"):`, and print their
  results with `echo`. A `when isMainModule` block of the original is converted like any code; added
  tests come after it.
- **Use only names the original module has.** The verification appends the transpiled test block to the
  original module.
- **Under `nimony c`** the test block meets nimony's library:
  - its statements run in `proc nimicMainN()` (`rule:mainproc`), `.raises` under nimony and called in
    `try: ... except: quit(1)`, so it may call `readFile`, `getCurrentDir`, `removeFile`; its imports and
    definitions (also a `when` of only definitions, `f = overloads(...)`) and the variable sections its procs
    read stay at the top level, before the statements; its procs are `.raises` under nimony too;
  - nothing of a main block is exported (no `*`), so its variables and definitions are plain names (`for s in
    ...`, `def show()`, not `_s`, `_show`): `_x` and `x` are the same Nim code there. A main block's name must
    not rebind a module-level name, also one a star import binds (Python shares the module's namespace);
  - order: the transpiled block has its definitions first. Tests the conversion adds are written in that
    order; a converted `when isMainModule` keeps the original's order (bif, nifreader interleave procs and
    tests), which the round trip can't give back;
  - `doAssert` comes from the prelude; `except AssertionDefect` has no meaning (nimony's `assert` quits);
  - a local passed as `var` (or added to) must be initialized: `x: seq[T] = seq[T]([])` (`@[]`) or
    `x = default(T)`; `x = T()` is Nim's bare `var x: T` (`rule:varini`).
- **`tests/verify_transpiled.py nimony`** checks three things per converted module:
  1. **module:** `nim check` of the transpiled module in a copy of nimony's `src/`;
  2. **tests:** the output of Python and of the compiled transpiled module are equal;
  3. **original:** the output of Python and of the original nimony module, compiled with the transpiled
     test block appended, are equal. This is the check of fidelity to the source.

### 13.5 Canonical forms

Nim can't tell some nimic spellings apart: they transpile to the same Nim, so a Nim → nimic round trip
(nimicgen, `../nimony-nimic`) gives back one of them. The conversions write that one:

| Choice | Canonical form | Not |
| --- | --- | --- |
| a string literal (§6) | `string("x")` where the literal is a value: bound (assignment, `with` section, default), stored, returned, passed as an argument (`update(s, string("("))`, `quit(string("msg"))`, `slurp(string("../x.md"))`); an operand of an operator, on either side (`s + string("!")`, `string("a") / name`, `string("$1.nim") % [m]`): Python takes the operator from the left operand, and `str` has its own `%` (Python formatting: `"$1-x" % [s]` is silently `'$1-x'`), none for `/` (`TypeError`), and `"x" + str(n)` gives a Python `str`; a bare `"x"` where Python takes its `str` as it is: an `echo` argument, an `assert` message, an operand of a comparison (`x == "abc"`, `"a" < s`, `"i" in s`), an enum member's text, `_ = "..."`, a directive's argument (`pragma`, `push`, `importFrom`, `exportExcept`, `defined`) | the other spelling in that place |
| a char literal (`rule:char`) | `char(' ')` (nimic has no `ch` since 2026-11-08) | — |
| a seq or set literal (`rule:seqlit`, `rule:setlit`) | `seq[T]([a, b])`, `seq[T]([])` (`@[]`, also in a typed declaration), `Tset[T](a, b)`, `Tset[T]()` | `seq(...)` (doesn't run), `seq[T]()` for `@[]` (it is a bare `var x: seq[T]`, `rule:varini`), `Tset(...)` |
| an `echo` argument (`rule:echodollar`) | `echo(x)`: echo applies Nim's `$` itself | `echo(str(x))` (`str(True)` is `True`, `$true` is `true`) |
| Nim's `float` | `float64` (`float64(hits)`, `f: float64`): Python's `float` is no nimic type | `float` |
| a type alias (§3) | `X = T` (`TInfoOSProps = Tset[TInfoOSProp]`) | `class X(T): pass` |
| a borrowed operator (§3, distinct) | `return super().__eq__(b)`, `return super().__str__()` | `return string(str(uint32(x)))` |
| `overloads(...)` (`rule:overloads`) | the modules in the order the module imports them | another order |
| a call of a `len` or `hash` method (§4, methods rule) | as the original spells it: `t.len` → `t.len()`, `len(t)` → `len(t)`, `hash(v)` → `hash(v)`. The free call reaches the method (an Object's `len` answers `len(b)`, its `hash` Python's `hash(b)`), and generic code needs it (bitabs' `hash(t.vals[i])` for any `T`) | the other spelling |
| an array constant or variable (`rule:array`) | `X = array[E, T]([...])`: the conversion gives the type | `X: array[E, T] = array[E, T]([...])` |
| an empty array literal (Nim `[]` for an `openArray` or `array[0, T]`) | `array[0, T]()` (as `array[2, uint8]()`, §3); transpiled to `default(array[0, T])` | `default(array[0, T])` |
| a set literal in a place typed by a set alias (`props: TInfoOSProps`, `TInfoOSProps = set[TInfoOSProp]`) | `Tset[TInfoOSProp](...)`, `Tset[TInfoOSProp]()`: the original's `{...}` names no alias | `TInfoOSProps(...)`, `TInfoOSProps({...})` (a Python set) |
| a main block's names (§13.4) | plain names, its variables and its definitions (`def show()`, `class Color`) | `_x`, `_show` |
| a main block's order (§13.4) | definitions first (added tests) | definitions after statements |
| a number literal | bare when the original has no type suffix, wherever it stands (`b0 <= 240`, `col: int32 = 0`, `r.line += 1`, an argument); with a suffix the typed form (`240'u8` → `u8(240)`, `0'u32` → `u32(0)`). No conversion the original doesn't write (no `uint64(u32(0))` for a `uint64` parameter). An operand, a comparison, `+=` and a store take the other side's type in Python; a default or an argument stays a Python `int` inside the callee (no overflow wrap there) | `u8(240)`, `int32(0)` where the original writes `0`; `uint64(u32(0))` |
| a value-producing last statement of a routine with a result type, also the last statement of a `try`, `if` or `case` branch (`template onRaiseQuit(call): untyped = try: call except: quit ...`) | `return call` (rules §2: a typed template returns): a bare `call` is `None` in Python, and in a template makes it a block template. `rule:templatereturn` writes a `return` in tail position as the value, also in the body and handlers of a `try` without `else` / `finally` (Nim's try expression) | `call` |
| a copy of a scalar (rules §1.1, `rule:copy`) | `copy(x)`: nimicgen writes it, as it works for a nimic integer (a cell) and a plain Python `int` alike (a `len`, a literal bound to a local), which has no `.copy()`. `x.copy()` is the same copy, and a developer may write it (as pandas' `df.copy()`) where `x` is a nimic value: a field, an element, a typed variable; the round trip takes the two as equal. A non-scalar value is copied `x.copy()`, `copy(x)` when it may be nil | `x.copy()` of a plain Python `int` (`AttributeError`) |
| which names a nimic module's import lists (§8) | the names the module reads free (a call, a value, an annotation). Not one it uses only through method syntax (`tb.inc()`: a method of the class, or a core / std routine under its `@ufcs`, reached through its type; a user module-level routine is called free since N72, so it is listed: `addIntLit(b, ...)`) or qualified (`bif.load(p)`); when no name of the module is left, the module is imported `from . import m` (Nim's method call needs the import). Not a name a set binds (`rule:overloads`). A module re-exporting a name (`export(nifcore)`) keeps it listed: Python's `export` re-exports its bindings | a listed name the module never reads free |
| where a re-exported name is imported from (§8) | the module that defines it, when the module imports that module as well (`nifcoreparse`: `FileId`, `isValid` from `lineinfos`, which `nifcore` re-exports) | the re-exporting module |
| nimic's std modules (§8) | imported by name where the original imports them, nothing more: a module the original imports only in a `when` (`std/sha1` in `nifchecksums`, `lengiface`, `nifindexes`) is imported in each branch, no top-level line beside it | a star import; an import line the original doesn't have |
| the order of import statements and sets (§8) | free, where Python's bindings don't change (a set comes after the imports of its name; with std modules imported by name only `ntypes`' star import is left, first); a set stands at the top level where its modules are imported. The round trip compares a run of import statements and sets sorted | — |
| a half-open range from 0 (`rule:range`) | `range(n)` (`for i in range(s.len):`, Nim `0 ..< s.len`) | `range(0, n)` |
| a custom operator's letter name (`rule:operator`) | each character named, joined by `_`, with `_` when the original isn't exported: `+` plus, `-` minus, `*` star, `/` slash, `\` backslash, `<` lt, `>` gt, `!` bang, `?` question, `^` caret, `.` dot, `\|` bar, `=` eq, `%` percent, `&` amp, `$` dollar, `@` at, `~` tilde, `:` colon (`+!` `plus_bang`, nifreader's private `^` `_caret`). std/hashes' named operators keep their names (`!&` `mix_hash`, §7) | a name for the meaning (`_deref`) |
| the hooks' Python names (`rule:hook`) | `<hook><Type>`, `_` when the original isn't exported (`_copyMangler`, `destroyCursor`) | `_copy`, `copy`, `destroy` |

Forms the transpiler keeps apart, so each original spelling has its own nimic form: `from . import a, b`
(one `import a, b` line) vs one `from . import` per module (Nim's `import bitabs, lineinfos, nifroles` is
`from . import bitabs, lineinfos, nifroles`; an import already written is left out), and likewise
`from nimic.std import memfiles, syncio` (one `import std/memfiles, std/syncio` line) vs one line per module; `a if c else b` (§7) vs an `if` statement whose
branches return; `x.f()` vs `f(x)` (§4: the call syntax follows the definition, `@ufcs`).

## 14. Nim 3 constructs

nimony's sources are written to compile with Nim 2 as well. In the host-Nim build, Nim 3-only code sits in
`when defined(nimony)` branches, or behind `compat2.nim`. nimic gains the Nim 3 constructs as conversions
need them. Until then a converted module writes them faithfully inside their inactive branch, or marks them
`# TODO: requires nimic feature <name>`.

| Nim 3 (nimony) | Replaces (Nim 2 rows of §0–§12) | nimic support |
| --- | --- | --- |
| `{.feature: "lenientnils".}`, `{.feature: "untyped".}`, `{.feature: "assumeSync".}` (module features), any standalone pragma `{.p.}` | — | `pragma('feature: "lenientnils"')` as a statement (`rule:pragmastmt`), usually in its `when defined(nimony)` branch. No effect in Python |
| `{.pragma: maybeDirty, dirty.}`, `{.pragma: untyped.}` (a pragma alias) | — | `pragma("pragma: maybeDirty, dirty")` (`rule:pragmastmt`). Defines the alias for the module's routines: `"""{.maybeDirty.}"""` on a template makes it dirty in Python too. An alias to nothing (`{.pragma: untyped.}`) is an empty pragma |
| `template nifEmits*(kind: string) {.pragma.}` (a custom pragma), `proc p() {.nifEmits: "D".}` | — | `@template`<br>`def nifEmits(kind: string):`<br>&nbsp;&nbsp;&nbsp;&nbsp;`"""{.pragma.}"""` (the docstring is the whole body: no Nim body, `rule:funcdefbody`); used like any pragma, `"""{.nifEmits: "D".}"""`. Its `##` doc comment lines follow the docstring as comments. No effect in Python |
| `static:` blocks | — | `with static:` (`rule:dropwith`). Python runs the body when the module runs (Nim's compile time): a failing `assert` stops the import |
| Case-sensitive identifiers | style-insensitive names (`is_nil` row) | `{.feature: "ignoreStyle".}` per module: the transpiler writes it after the prelude import (`rule:ignorestyle`), so `unsafe_addr` is `unsafeAddr` as in Nim 2 |
| `nil ref T` / `nil ptr T` (refs are not nil by default) | `None` for nilable refs | planned: a nilable marker |
| `raise IOError`, `except IOError:` (no `as e`), `{.raises.}` opt-in; `ErrorCode` values | exceptions as classes with messages | planned |
| `case` inside `object`: the new syntax | the `match kind:` variant row | planned: transpiler output |
| explicit generic parameters (`proc f[T: SomeInteger](x: T)`) | implicit generics (`x: SomeInteger`) | planned: always emit `[T: ...]` |
| concepts: `Equatable = concept x` (Nim 2, universal), `Comparable* = concept` + `func `<`(x, y: Self): bool`, `Keyable* = concept of Hashable`; used as bounds `[T: Comparable]` | — | `class _Equatable(Concept): pass`; `class Comparable(Concept):` with signatures as the body (`def __lt__(x: Self, y: Self) -> bool:` + `"""{.noSideEffect.}"""` for a `func`, or `...`); a concept base `class Keyable(Hashable):` is `concept of Hashable` (nimony syntax, Nim 2 rejects it: only in `when defined(nimony)`). `Self` comes from `nimic.ntypes` (`rule:concept`). A bound needs `@dispatch`. Python doesn't check the signatures yet: every type fits a concept, Nim checks them |
| strings without a terminating `'\0'`; `cstring` of a string copies | cstring rows, `s[s.len]` row | planned: a per-target string model |
| polymorphic accessors (`func [](x: C): var E`) | `var T` overloads | planned |
| `func` is `noSideEffect`, `proc` side-effecting, no inference; `{.cast(noSideEffect).}:` | `func` row | planned |
| unlabeled `break` leaves only a loop | — | already so: blocks are left with `breakBlock("name")` |
| compiler plugins | macros (G17) | macros are legacy: every macro call is written out as the code it expands to (§2), no macro support in nimic. Plugins: later |
| `range` checked at compile time, no runtime checks | `Natural`/`RangeDefect` rows | to decide (Python can't prove) |
