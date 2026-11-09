# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lib/nifprelude.nim
# ///
## imports the set of NIF related modules that have won

from __future__ import annotations
from nimic.ntypes import *

with push("warning[UnusedImport]: off"):

    from .bitabs import getOrIncl
    from .nifpools import buildTree, createTokenBuf, ErrT, globalTags, NifKind, NoLineInfo, pool, toString, writeFile
    from . import nifbuilder
    from .nifbuilder import addHeader, extract, open, withTree
    from . import nifroles
    export(nifroles)
    importFrom(".nifreader")   # text reader; qualified-only: its NifKind must
                               # not shadow nifcore's token kinds
    from . import nifpools
    # one name of two imports, called free: Nim overloads them (rule:overloads)
    addIdent = overloads(nifpools.addIdent, nifbuilder.addIdent)
    addIntLit = overloads(nifpools.addIntLit, nifbuilder.addIntLit)
    addStrLit = overloads(nifpools.addStrLit, nifbuilder.addStrLit)


if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir", "removeFile")

    def roleHelper(n: nint) -> nint:
        """{.nifBalanced.}"""
        return n + 1

    def testPrelude():
        # nifcore's NifKind is not shadowed by nifreader's
        echo("kind: ", NifKind.TagLit, " ", NifKind.StrLit)

        # pool + globalTags + bitabs
        with let:
            sid = getOrIncl(pool.strings, string("hello"))
        echo("pool: ", pool.strings[sid], " tag: ", globalTags.tags[ErrT])

        # buildTree (from nifpools / nifcore)
        with var:
            tb = createTokenBuf(8)
        with buildTree(tb, ErrT, NoLineInfo):
            addIdent(tb, string("item"), NoLineInfo)
            addStrLit(tb, string("val"), NoLineInfo)
            tb.addIntLit(42)
        echo("tree: ", toString(tb, False))

        # nifbuilder proc
        with var:
            bld = open(16, compact=True)
        addHeader(bld)
        with withTree(bld, string("stmts")):
            addIdent(bld, string("foo"))
            addIntLit(bld, 7)
        echo("builder: ", extract(bld))

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
        echo("reader: ", tk.tk, " ", nifreader.decodeStr(r, tk))
        nifreader.close(r)
        removeFile(tmpPath)

        # nifroles pragma
        echo("role: ", roleHelper(10))

    testPrelude()
