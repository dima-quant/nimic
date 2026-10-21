# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/docpaths.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Path-derivation rules shared by `deps.nim` (which decides where each
## module's `.html` lands) and `dagon` (which synthesises cross-module URLs
## from import suffixes). Both must agree byte-for-byte on what relpath a
## given source `.nim` maps to, otherwise hyperlinks miss their targets.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.strutils import *

with const:
    ExternalBucket = string("_external")


def toUnixPath(s: string) -> string:
    # On Windows, replace `\` with `/` so paths emitted into NIF / HTML are
    # byte-identical across operating systems (Windows, Linux, macOS produce
    # the same artifacts). No-op on POSIX. Apply at every boundary where a
    # path crosses into a NIF token, an HTML attribute, or a CLI arg whose
    # downstream consumer might also be cross-OS.
    if comptime(defined("windows")):
        return s.replace(ch('\\'), ch('/'))
    else:
        return s


with const:
    _UnreservedChar = Tset[char](
        inrange(ch('A'), ch('Z')),
        inrange(ch('a'), ch('z')),
        inrange(ch('0'), ch('9')),
        ch('-'), ch('.'), ch('_'), ch('~')
    )


def _sanitizePart(s: string) -> string:
    # Make a single path component URL/filesystem-safe. Replaces any byte
    # outside the unreserved set with `_`. Used for the `_external/…` bucket
    # where the source path is unconstrained.
    result = newStringOfCap(s.len)
    for c in s:
        if c in _UnreservedChar:
            result.add(c)
        else:
            result.add(ch('_'))
    return result


@ufcs(string)
def _startsWithPath(s: string, prefix: string) -> bool:
    """{.inline.}"""
    # True iff `s` starts with `prefix` followed by a path separator (or
    # equals `prefix`). Avoids the `lib/std/system` vs. `lib_other/` confusion
    # that a plain `startsWith` would have.
    if not s.startsWith(prefix):
        return False
    if s.len == prefix.len:
        return True
    with let:
        next = s[prefix.len]
    result = next == ch('/') or next == ch('\\')
    return result


def _externalBucketPath(srcPath: string) -> string:
    with let:
        bn = splitFile(srcPath).name
    result = ExternalBucket / _sanitizePart(bn) + string(".html")
    return result


def deriveRelpath(srcPath: string, projectRoot: string, stdlibRoot: string) -> string:
    # Compute the htmldocs-relative path for a source `.nim` file. Three
    # buckets, in priority order:
    #   1. Under `stdlibRoot`: keep the part after `stdlibRoot/` and swap
    #      `.nim` → `.html` (e.g. `lib/std/system.nim` → `std/system.html`).
    #   2. Under `projectRoot`: same, relative to the project (e.g.
    #      `myproj/src/foo.nim` → `src/foo.html`).
    #   3. Anywhere else: `_external/<sanitized-basename>.html`. Loses path
    #      info; collisions punted (rare in practice — stray imports of
    #      absolute paths from outside the project tree).
    #
    # `projectRoot` and `stdlibRoot` are expected to be absolute (callers in
    # `deps.nim` and `dagon` use `absoluteParentDir`/`stdlibDir`). If `srcPath`
    # is relative, fall through to bucket 3.
    if srcPath.isAbsolute():
        if stdlibRoot.len > 0 and srcPath._startsWithPath(stdlibRoot):
            return srcPath.substr(stdlibRoot.len + 1).changeFileExt(string("html"))
        if projectRoot.len > 0 and srcPath._startsWithPath(projectRoot):
            return srcPath.substr(projectRoot.len + 1).changeFileExt(string("html"))
    result = _externalBucketPath(srcPath)
    return result


if comptime(__name__ == "__main__"):
    assert ExternalBucket == string("_external")
    assert toUnixPath(string("a/b/c.nim")) == string("a/b/c.nim")
    echo(ExternalBucket, "|", toUnixPath(string("a/b/c.nim")))

    with let:
        cwd = getCurrentDir()
        stdlibRoot = cwd / string("lib")
        projectRoot = cwd / string("myproj")

    # Bucket 1: under stdlibRoot
    with let:
        r1 = deriveRelpath(stdlibRoot / string("std/system.nim"), projectRoot, stdlibRoot)
    assert r1 == string("std/system.html")
    echo(r1)

    # Bucket 2: under projectRoot
    with let:
        r2 = deriveRelpath(projectRoot / string("src/foo.nim"), projectRoot, stdlibRoot)
    assert r2 == string("src/foo.html")
    echo(r2)

    # Prefix boundary check: lib_other/ must not match lib
    with let:
        r3 = deriveRelpath(cwd / string("lib_other/bar.nim"), projectRoot, stdlibRoot)
    assert r3 == ExternalBucket / string("bar.html")
    echo(r3)

    # Bucket 3: external absolute path with special characters in basename
    with let:
        r4 = deriveRelpath(cwd / string("outside/my file@1.nim"), projectRoot, stdlibRoot)
    assert r4 == ExternalBucket / string("my_file_1.html")
    echo(r4)

    # Bucket 3: relative path falls through to external bucket
    with let:
        r5 = deriveRelpath(string("rel/baz.nim"), projectRoot, stdlibRoot)
    assert r5 == ExternalBucket / string("baz.html")
    echo(r5)
