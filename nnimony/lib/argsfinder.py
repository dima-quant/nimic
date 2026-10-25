# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/argsfinder.nim
# ///
#       Nif library
# (c) Copyright 2025 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Provides utility functions for the new "args configuration system".

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.strutils import *
from nimic.std.syncio import *
from nimic.std.parseopt import *


def _parseCmdArg(c: string, i: nint, a: mut @ string) -> nint:
    # eat all delimiting whitespace
    with var:
        i = nint(i)
    while i < c.len and c[i] in Tset[char](ch(' '), ch('\t'), ch('\n'), ch('\r')): i += 1
    if i >= c.len: return i
    match c[i]:
        case _ if c[i] == ch("'") or c[i] == ch('"'):
            with let:
                delim = c[i]
            i += 1  # skip ' or "
            while i < c.len and c[i] != delim:
                a.add(c[i])
                i += 1
            if i < c.len: i += 1
        case _:
            while i < c.len and c[i] > ch(' '):
                a.add(c[i])
                i += 1
    result = i
    return result


def _parseCmdLinePosix(c: string, result: mut @ seq[string]):
    ## Components are separated by whitespace unless the whitespace
    ## occurs within ``"`` or ``'`` quotes.
    with var:
        i = nint(0)
        a = string("")
    while i < c.len:
        i = _parseCmdArg(c, i, a)
        result.add(move(a))


def extractArgsKey(command: string) -> string:
    ## Extract the key from a command line option.
    ##
    ## Examples:
    ## - `/usr/bin/gcc` → `gcc`
    ## - `/usr/bin/arm-linux-gnueabihf-gcc` → `arm-linux-gnueabihf-gcc`
    ## - `/usr/bin/x86_64-w64-mingw32-gcc.exe -Wall` → `x86_64-w64-mingw32-gcc`
    ## - `/usr/local/bin/clang` → `clang`
    result = string("")
    _ = _parseCmdArg(command, 0, result)
    with var:
        i = nint(0)
        start = nint(0)
    while i < result.len:
        match result[i]:
            case _ if result[i] == ch('/') or result[i] == ch('\\'): start = i + 1
            case _ if result[i] == ch('.'): break
            case _: pass
        i += 1
    result = result.substr(start, i - 1)
    return result


def findArgs(baseDir: string, argsFileName: string) -> string:
    # Nim: `result = (try: expandFilename(baseDir) except: baseDir) / argsFileName`
    try:
        result = expandFilename(baseDir)
    except:
        result = baseDir
    result = result / argsFileName
    # This particular algorithm works both with Windows (C:\\) and Unix paths and does not
    # allocate memory in its loop (except for whatever allocations `fileExists` does).
    while True:
        #echo "looking for ", result
        if fileExists(result): return result
        # as long as there is a `/path_section/` in result, remove that section
        # and continue:
        with var:
            last = result.len - 1
        while last > 0 and result[last] not in Tset[char](ch('/'), ch('\\')):
            last -= 1
        with var:
            first = last - 1
        while first >= 0 and result[first] not in Tset[char](ch('/'), ch('\\')):
            first -= 1
        if first < 0: break
        first += 1  # don't delete the '/'
        # this way we don't allocate at all here:
        delete(result, inrange(first, last))
    return string("")  # not found


def processArgsFile(argsFile: string, args: mut @ seq[string]):
    if argsFile.len == 0: return
    for line in lines(argsFile):
        if line.len == 0 or line.startsWith(string("#")):
            _ = "ignore comment"
        else:
            _parseCmdLinePosix(line, args)


def processPathsFile(pathsFile: string, paths: mut @ seq[string]):
    if pathsFile.len == 0: return
    with let:
        dir = pathsFile.splitFile().dir
    with let:
        try:
            expanded = expandFilename(dir)
        except:
            expanded = dir
    for line in lines(pathsFile):
        if line.len == 0 or line.startsWith(string("#")):
            _ = "ignore comment"
        elif isAbsolute(line):
            paths.add(line)
        else:
            paths.add(expanded / line)


def determineBaseDir(mainFileAt: nint = 1) -> string:
    # `mainFileAt` is the number of command line arguments to skip before
    # the base directory can be extracted from a file name. It defaults to 1
    # because the syntax is `nimony c myproject/main.nim`.
    with var:
        cmd = nint(mainFileAt)
    for kind, key, val in getopt():
        match kind:
            case CmdLineKind.cmdArgument:
                if cmd == 0:
                    return key.splitFile().dir
                cmd -= 1
            case _: pass
    return string("")


def extractCCKey(val: string) -> string:
    result = extractArgsKey(val)
    with var:
        dash = result.len - 1
    while dash >= 0 and result[dash] != ch('-'): dash -= 1
    if dash >= 0:
        result = result.substr(dash + 1)
    return result


if comptime(__name__ == "__main__"):
    from nimic.std.assertions import *
    assert extractArgsKey(string("gcc")) == string("gcc")
    assert extractArgsKey(string("/usr/bin/gcc")) == string("gcc")
    assert extractArgsKey(string("/usr/bin/arm-linux-gnueabihf-gcc")) == string("arm-linux-gnueabihf-gcc")
    assert extractArgsKey(string("/usr/bin/x86_64-w64-mingw32-gcc.exe -Wall")) == string("x86_64-w64-mingw32-gcc")
    assert extractArgsKey(string("/usr/local/bin/clang")) == string("clang")
    assert extractArgsKey(string("/usr/bin/x86_64-w64-mingw32-gcc.exe -Wall")) == string("x86_64-w64-mingw32-gcc")
    assert extractArgsKey(string("/usr/local/bin/clang")) == string("clang")

    assert extractArgsKey(string("'C:\\Program Files\\gcc\\bin\\gcc.exe' -Wall")) == string("gcc")

    echo(findArgs(string("."), string("gcc.args")))

    echo(findArgs(string("C:/some/path/here/"), string("gcc.args")))

    echo(findArgs(string("////some/path/here/"), string("gcc.args")))

if comptime(__name__ == "__main__"):
    # extractArgsKey / extractCCKey: quotes, a dash prefix, no extension
    echo(extractArgsKey(string("  \"/opt/my tools/clang++\" -O2")))
    echo(extractArgsKey(string("")))
    echo(extractCCKey(string("/usr/bin/arm-linux-gnueabihf-gcc")))
    echo(extractCCKey(string("/usr/bin/x86_64-w64-mingw32-gcc.exe -Wall")))
    echo(extractCCKey(string("clang")))

    # the parser over a given command line: an argument, a short and a long option
    for kind, key, val in getopt(seq[string]([string("main.nim"), string("-d"), string("--out:build/x")])):
        echo(kind, " ", key, " ", val)
    # the real command line has no arguments here (Python and the test binary alike)
    echo(determineBaseDir().len)

    # files under the temp dir: findArgs walks up from the base dir, the args and paths files
    with let:
        root = getTempDir() / string("argsfinder_test")
        deep = root / string("a") / string("b")
    removeDir(root)
    createDir(deep)
    writeFile(root / string("gcc.args"), string("# a comment\n\n-O2 'a b'  \"c d\"\n-Wall\n"))
    writeFile(root / string("p.paths"), string("# paths\nrel/dir\n/abs/dir\n"))
    with let:
        found = findArgs(deep, string("gcc.args"))
    echo(found.endsWith(string("/argsfinder_test/gcc.args")))
    echo(findArgs(deep, string("missing.args")).len)
    with var:
        args = seq[string]()
        paths = seq[string]()
    processArgsFile(found, args)
    processArgsFile(string(""), args)
    echo(args)
    processPathsFile(root / string("p.paths"), paths)
    processPathsFile(string(""), paths)
    echo(paths.len, " ", paths[0].endsWith(string("/argsfinder_test/rel/dir")), " ", paths[1])
    removeDir(root)
