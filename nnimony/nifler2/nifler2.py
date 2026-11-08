# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/nifler2/nifler2.nim
# program: the main block runs nifler2 (the original runs `main()` at its top level)
# test-args: t src/nifler2/linkedtok.nim
# ///
#
#
#           Nifler2: Nim to NIF
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## Nifler2 parses Nim code and writes NIF. Same job as `src/nifler`, without
## linking Nim 2's compiler: the lexer is `nimlexer` and the parser is
## generated from `nimgrammar.nim`.
##
##   bin/nimony c src/nifler2/nifler2.nim
##   nifler2 p file.nim [out.nif]

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import syncio, assertions
from nimic.std.os import absolutePath, addFileExt, changeFileExt, getCurrentDir, relativePath
from nimic.std.parseopt import CmdLineKind, getopt
from . import nimgrammar, niflerout, filters
from .nimgrammar import globalTags, openParser, parseModule, Parser, pool, toString
from .niflerout import writeDeps, writeNifler
from .filters import applyFilters

with const:
    _Usage = string("""nifler2 - Nim to NIF
Usage:
  nifler2 [options] p|parse file.nim [out.nif]   parse one file, write NIF
  nifler2 [options] deps file.nim [out.nif]      write only the deps file
  nifler2 t|tree file.nim                        parse one file, print the tree

Options:
  --portablePaths   accepted; paths are always written relative to the
                    current directory, as `nifler --portablePaths` does
  --deps            also write <out>.deps.nif, the module's dependencies
  --force, -f       accepted; the output is always rewritten
""")


def _parse(p: mut @ Parser, inp: string):
    """{.raises.}"""
    ## `Parser` owns a `TokenBuf`, which is not copyable, so it is filled in
    ## place rather than returned.
    ## A syntax error ends the process; the lexer's and the filters' errors are
    ## only collected.
    with let:
        filename = absolutePath(inp)
    with var:
        filterFailed = nbool(False)
    with let:
        src = applyFilters(readFile(inp), filename, filterFailed)
    p <<= openParser(src, filename, pool, globalTags)
    p.filterFailed = filterFailed
    parseModule(p)
    if p.failed: p.reportFailure()


def _report(p: Parser) -> bool:
    for e in p.lex.errors: echo(e)
    return p.lex.errors.len == 0 and not p.filterFailed


def _main():
    """{.raises.}"""
    with var:
        action = string("")
        args: seq[string] = seq[string]([])
        deps = False
    for kind, key, val in getopt():
        match kind:
            case CmdLineKind.cmdArgument:
                if action.len == 0: action = key
                else: args.add(key)
            case CmdLineKind.cmdLongOption | CmdLineKind.cmdShortOption:
                match key:
                    case "portablePaths" | "portablepaths" | "force" | "f": pass
                    case "deps": deps = True
                    case "help" | "h": quit(_Usage)
                    case _: quit(string("nifler2: unsupported option: ") + key)
            case CmdLineKind.cmdEnd: pass
    if args.len == 0: quit(_Usage)
    with let:
        inp = args[0]
    match action:
        case "p" | "parse" | "deps":
            with var:
                p = openParser(string(""), inp, pool, globalTags)
            _parse(p, inp)
            with let:
                ok = _report(p)
            if not ok: quit(1)
            # nifler's naming: `out.nif` as given (an extension added if missing), else
            # the input with `.nif`; the deps file replaces that extension
            with let:
                outp = addFileExt(args[1], string("nif")) if args.len >= 2 else changeFileExt(inp, string(".nif"))
            if action != "deps":
            # nimony runs nifler with `--portablePaths`: the file is written relative
            # to the current directory
                writeNifler(p.first, p.pool, p.tags, p.arena.cellCount() * 8, outp, relativePath(absolutePath(inp), getCurrentDir(), char('/')))
            if deps or action == "deps":
                writeDeps(p.first, p.pool, p.tags, changeFileExt(outp, string(".deps.nif")))
        case "t" | "tree":
            with var:
                p = openParser(string(""), inp, pool, globalTags)
            _parse(p, inp)
            with var:
                buf = p.finish()
            echo(toString(buf))
            if not _report(p): quit(1)
        case _:
            quit(_Usage)


# The program's entry: the original runs `main()` at the top level of the program module (rules §2.1, a
# program's entry module: its run goes under the `__main__` guard, as it is imported to be transpiled)
if comptime(__name__ == "__main__"):
    try:
        _main()
    except:
        quit(string("nifler2: cannot read the input file"))
