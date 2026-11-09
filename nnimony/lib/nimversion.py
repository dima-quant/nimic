# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lib/nimversion.nim
# ///
#       Nimony
# (c) Copyright 2025 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Single source of truth for the toolchain version string. Every tool
## (nimony, nimsem, hexer, lengc, nifler, nifmake) imports `Version` from here
## instead of `slurp`ing `doc/version.md` on its own — so the relative path to
## the version file lives in exactly one place.
##
## `slurp` resolves the path relative to *this* file (`src/lib/`), which is the
## same depth as every tool's own main module (`src/<tool>/`), so the literal
## `../../doc/version.md` is unchanged from the copies it replaces.
##
## `doc/version.md` holds the version number, then whitespace, then the ISO
## date that number was set on — the same shape as `src/nativenif.commit`, and
## for the same reason: a diff bumping the version should say *when* without
## anyone running `git log`. The date is READABILITY ONLY. Nothing reads it
## back, only the first field is ever used, and the split doubles as the
## trailing-newline guard the old whole-file `slurp` never had (it worked only
## because the file happened to carry no final newline — one editor save away
## from putting a blank line into every `--version`).

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import syncio  # `slurp` is a `std/syncio` proc under nimony (a system
                                # magic under the host Nim bootstrap compiler).

with const:
    _VersionFile = slurp(string("../../doc/version.md"))
    ## The file verbatim: version, whitespace, date.


def _firstField(s: string) -> string:
    ## Everything up to the first whitespace, i.e. the version number alone.
    ## Hand-rolled rather than `strutils.split`/`strip` so this module keeps its
    ## single `std/syncio` import — it is the one module the whole toolchain
    ## depends on, and nifler and nifmake do not otherwise pull `strutils` in.
    result = string("")
    with var:
        i = 0
    while i < len(s) and s[i] > char(' '):
        result.add(s[i])
        i += 1
    return result


with const:
    Version = _firstField(_VersionFile)
    ## `firstField` carries no `semantics` pragma, so `expreval` cannot fold it
    ## natively the way it folds `slurp` itself and falls back to `executeExpr`'s
    ## nested sub-compile of this module. That sub-compile is content-addressed
    ## and its own inner build is incremental, so it costs ~0.1 s — it is not the
    ## thing to avoid. What used to make it expensive was a build-graph bug it
    ## walked into, since fixed: the sub-compile is a second nimony driving the
    ## same nimcache, and the configuration memo — then an input of EVERY sem node —
    ## carried the root module name, so the two builds overwrote each other's
    ## entry on every run and each re-semmed everything the other had just done.
    ## See `deps.nim`'s `addFrontendKey`.


if comptime(__name__ == "__main__"):
    from nimic.std import strutils

    echo(Version)
    # the first field of doc/version.md (the tests run from the nimony checkout, as nimony's own do)
    assert Version == readFile(string("doc/version.md")).split()[0]
    assert len(Version) > 0
