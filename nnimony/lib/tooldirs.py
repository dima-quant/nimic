# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/tooldirs.nim
# ///
## This module provides functions to find tools in the Nimony bin directory.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.strutils import *


def binDir() -> string:
    # The directory tools live in. `bin*` is matched (not just `bin`) so the
    # boot bootstrap can stage parallel toolchains under sibling directories
    # like `bin0`, `bin1`, `bin2` without each stage's nimony falling back to
    # looking in `bin*/bin`.
    with let:
        appDir = getAppDir()
        (_, tail) = splitPath(appDir)
    if tail.startsWith(string("bin")):
        result = appDir
    else:
        result = appDir / string("bin")
    return result


def toolDir(f: string) -> string:
    result = binDir() / f
    return result


def findTool(name: string) -> string:
    result = name.addFileExt(ExeExt)
    if fileExists(result):
        _ = string("ok")
    elif not name.isAbsolute():
        with let:
            t = toolDir(result)
        if fileExists(t):
            result = t
    return result


def parserTool() -> string:
    # The Nim-to-NIF parser: `nifler2` once it is built, `nifler` before. The
    # fallback is the bootstrap -- nifler2 is itself compiled by nimony, which
    # must parse it with something. Both write byte-identical `.p.nif` and deps
    # files; nifler stays the tool for `config` and `--docs`, which nifler2
    # does not implement.
    result = findTool(string("nifler2"))
    if not fileExists(result):
        result = findTool(string("nifler"))
    return result


if comptime(__name__ == "__main__"):
    with let:
        b = binDir()
    assert b.len > 0
    assert toolDir(string("mytool")) == b / string("mytool")
    echo(b.len > 0, "|", toolDir(string("x")) == b / string("x"), "|", toolDir(string("x")).endsWith(string("/x")))

    # Nonexistent relative tool returns name with ExeExt
    with let:
        missing = string("nonexistent_tool_xyz_98765")
    assert findTool(missing) == addFileExt(missing, ExeExt)
    echo(findTool(missing) == addFileExt(missing, ExeExt))

    # Nonexistent absolute tool returns name with ExeExt without prepending binDir
    with let:
        absMissing = b / string("nonexistent_tool_xyz_98765")
    assert findTool(absMissing) == addFileExt(absMissing, ExeExt)
    echo(findTool(absMissing) == addFileExt(absMissing, ExeExt))

    # parserTool returns a non-empty string
    with let:
        pt = parserTool()
    assert pt.len > 0
    echo(pt.len > 0)
