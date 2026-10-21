# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/compat2.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Compat shims that let a module compile under both Nim and Nimony.
## Must be `include`d, not `import`ed, because Nim does not export
## custom pragmas across module boundaries.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    pragma("pragma: canRaise, raises")
else:
    pragma("pragma: canRaise")

if comptime(defined("nimony")):
    @template
    def onRaiseQuit(call: untyped) -> untyped:
        """{.private.}"""
        ## Calls a `{.raises.}` proc from a non-raising context: wraps in
        ## try/except and aborts with a useful diagnostic on failure. Lets us
        ## keep `raises` from spreading virally through every layer in `sem.nim`
        ## et al. without silently swallowing the raise.
        ## Unexported on purpose — `compat2.nim` is `include`d, not `import`ed,
        ## so each user file gets its own private copy and there is no
        ## cross-module ambiguity.
        try:
            call
        except:
            quit(string("FAILURE: ") + astToStr(call))
else:
    @template
    def onRaiseQuit(call: untyped) -> untyped:
        """{.private.}"""
        call

if comptime(not defined("nimony")):
    importFrom("nimic.std.paths", "Path")

    def path(s: string) -> Path:
        """{.inline.}"""
        ## Compat shim: Nimony exposes `path(string) -> Path` (its dirs/paths API
        ## takes a `Path`-typed wrapper); on host Nim the equivalent is `Path(s)`.
        ## Having both spellings lets call sites write `createDir(path(s))`
        ## unconditionally, dropping the `when defined(nimony)`/`else` ladder.
        ## `from … import` keeps `paths.getCurrentDir` etc. out of scope so it
        ## doesn't collide with `os.getCurrentDir` in modules that include this.
        return Path(s)

if comptime(not defined("nimony")):
    from nimic.std.tables import *

    @dispatch
    def getOrQuit[A, B](t: mut @ Table[A, B], k: A) -> mut @ B:
        ## Host-Nim shim for the Nimony `tables.getOrQuit` that returns `var B`
        ## and aborts if the key is absent. Callers guard with `hasKey` before
        ## this call, so the missing-key branch is unreachable in practice.
        if not t.hasKey(k):
            quit(string("getOrQuit: missing key"))
        result = t[k]
        return result

    @dispatch
    def getOrQuit[A, B](t: mut @ OrderedTable[A, B], k: A) -> mut @ B:
        if not t.hasKey(k):
            quit(string("getOrQuit: missing key"))
        result = t[k]
        return result

    @dispatch
    def getOrQuit[A, B](t: Table[A, B], k: A) -> lent @ B:
        ## Read-only variant for `let`-bound tables: nimony's `getOrQuit` takes
        ## the table by value and returns `var B`, but host Nim distinguishes
        ## mutable from immutable receivers.
        if not t.hasKey(k):
            quit(string("getOrQuit: missing key"))
        result = t[k]
        return result

    @dispatch
    def getOrQuit[A, B](t: OrderedTable[A, B], k: A) -> lent @ B:
        if not t.hasKey(k):
            quit(string("getOrQuit: missing key"))
        result = t[k]
        return result

if comptime(not defined("nimony")):
    # Nimony's `system` defines these as enforcing concepts (`Equatable` requires
    # `==`, `Comparable` requires `==`/`<`, etc.); host Nim has no such concepts.
    # Dual-compiled compiler source can still carry the constraints (so it stays
    # checked-generics-clean under Nimony) because here they are universal-match
    # typeclasses — `concept x` with an empty body matches every type. Not
    # exported: a constraint is only needed locally where it is written, and
    # re-exporting a type from an `include`d shim would create cross-module
    # ambiguity.
    class _Equatable(Concept):
        pass

    class _Comparable(Concept):
        pass

    class _ComparableAndNegatable(Concept):
        pass

    class _Arithmetic(Concept):
        pass

    class _Orderable(Concept):
        pass

    class _Keyable(Concept):
        pass

    class _Hashable(Concept):
        pass

    class _HasDefault(Concept):
        pass

    class _HasWriteErr(Concept):
        pass
