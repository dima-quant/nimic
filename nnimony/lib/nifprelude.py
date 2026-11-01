# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/nifprelude.nim
# ///
## imports the set of NIF related modules that have won

from __future__ import annotations
from nimic.ntypes import *

with push("warning[UnusedImport]: off"):

    from .bitabs import getOrIncl
    from .nifpools import (
        buildTree, createTokenBuf, ErrT, globalTags, NifKind, NoLineInfo, pool, tags, toString, writeFile)
    from .nifbuilder import addHeader, addIdent, addIntLit, addStrLit, extract, open, withTree
    from . import nifroles
    export(nifroles)
    importFrom(".nifreader")   # text reader; qualified-only: its NifKind must
                               # not shadow nifcore's token kinds


if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir", "removeFile")
    from . import nifbuilder, nifpools
    # one name of two imports, called free: Nim overloads them (rule:overloads)
    addIdent = overloads(nifbuilder.addIdent, nifpools.addIdent)
    addIntLit = overloads(nifbuilder.addIntLit, nifpools.addIntLit)
    addStrLit = overloads(nifbuilder.addStrLit, nifpools.addStrLit)

    def _roleHelper(n: nint) -> nint:
        """{.nifBalanced.}"""
        return n + 1

    def _testPrelude():
        # nifcore's NifKind is not shadowed by nifreader's
        echo(string("kind: "), NifKind.TagLit, string(" "), NifKind.StrLit)

        # pool + globalTags + bitabs
        with let:
            sid = getOrIncl(pool.strings, string("hello"))
        echo(string("pool: "), pool.strings[sid], string(" tag: "), globalTags.tags[ErrT])

        # buildTree (from nifpools / nifcore)
        with var:
            tb = createTokenBuf(8)
        with buildTree(tb, ErrT, NoLineInfo):
            addIdent(tb, string("item"), NoLineInfo)
            addStrLit(tb, string("val"), NoLineInfo)
            addIntLit(tb, 42)
        echo(string("tree: "), toString(tb, False))

        # nifbuilder proc
        with var:
            bld = open(16, compact=True)
        addHeader(bld)
        with withTree(bld, string("stmts")):
            addIdent(bld, string("foo"))
            addIntLit(bld, 7)
        echo(string("builder: "), extract(bld))

        # nifreader.open on a small file under getTempDir()
        with let:
            tmpPath = getTempDir() + string("/nimic_test_nifprelude.nif")
        writeFile(tb, tmpPath)
        with var:
            r = nifreader.open(tmpPath)
        _ = nifreader.processDirectives(r)
        with var:
            tk = default(nifreader.ExpandedToken)
        nifreader.next(r, tk)
        echo(string("reader: "), tk.tk, string(" "), nifreader.decodeStr(r, tk))
        nifreader.close(r)
        removeFile(tmpPath)

        # nifroles pragma
        echo(string("role: "), _roleHelper(10))

    _testPrelude()
