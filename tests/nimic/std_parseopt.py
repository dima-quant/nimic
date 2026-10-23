# /// nimic
#
# ///
## std/parseopt in Python (the nimic shim, a port of Nim 2.2.4's parseopt) and in compiled Nim: the same tokens
## for Nim's documented examples, shortNoVal / longNoVal, next, cmdLineRest, remainingArgs and
## allowWhitespaceAfterColon (tests/verify_transpiled.py nimic compares the outputs).
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.parseopt import *
from nimic.std.os import *


if comptime(__name__ == "__main__"):
    def _fmt(kind: CmdLineKind, key: string, val: string) -> string:
        if kind in (cmdShortOption, cmdLongOption):
            return string("Option: ") + key if val == string("") else string("Option and value: ") + key + string(", ") + val
        return string("Argument: ") + key

    for kind, key, val in getopt(parseCmdLine(string("-ab -e:5 --foo --bar=20 file.txt"))):
        echo(_fmt(kind, key, val))
    echo(string("--"))
    for kind, key, val in getopt(parseCmdLine(string("-n:9 --foo:bar")), shortNoVal=Tset[char](char('n')), longNoVal=seq[string]([string("foo")])):
        echo(kind, string(" "), key, string(" "), val)
    echo(string("--"))
    with var:
        p = initOptParser(string("-j4 --first bar"))
    for kind, key, val in getopt(p):
        echo(_fmt(kind, key, val))
    with var:
        q = initOptParser(string("-j4 --first bar"), shortNoVal=Tset[char](char('c')), longNoVal=seq[string]([string("second")]))
    for kind, key, val in getopt(q):
        echo(_fmt(kind, key, val))
    echo(string("--"))
    with var:
        r = initOptParser(string("--left -r:2 file.txt rest 'a b'"))
    next(r)
    echo(r.kind, string(" "), r.key)
    next(r)
    echo(r.kind, string(" "), r.key, string(" "), r.val)
    echo(cmdLineRest(r))
    echo(remainingArgs(r))
    next(r)
    echo(r.kind, string(" "), r.key)
    with var:
        s = initOptParser(seq[string]([string("--foo:"), string("bar"), string("-x"), string("--k = v")]), allowWhitespaceAfterColon=False)
    for kind, key, val in getopt(s):
        echo(kind, string(" ["), key, string("] ["), val, string("]"))
