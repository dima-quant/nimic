# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifprelude.nim
# ///
## imports the set of NIF related modules that have won

from __future__ import annotations
from nimic.ntypes import *

with push("warning[UnusedImport]: off"):

    from .bitabs import *
    from .nifpools import *
    from .nifbuilder import *
    from .nifroles import *           # role pragmas the validator reads off declarations
    from . import nifroles
    with export:
        nifroles
    importFrom(".nifreader")   # text reader; qualified-only: its NifKind must
                               # not shadow nifcore's token kinds


if comptime(__name__ == "__main__"):
    importFrom("nimic.std.os", "getTempDir", "removeFile")

    def _roleHelper(n: nint) -> nint:
        """{.nifBalanced.}"""
        return n + 1

    def _testPrelude():
        # nifcore's NifKind is not shadowed by nifreader's
        echo(string("kind: "), NifKind.TagLit, string(" "), NifKind.StrLit)

        # pool + globalTags + bitabs
        with let:
            sid = pool.strings.getOrIncl(string("hello"))
        echo(string("pool: "), pool.strings[sid], string(" tag: "), globalTags.tags[ErrT])

        # buildTree (from nifpools / nifcore)
        with var:
            tb = createTokenBuf(8)
        with buildTree(tb, ErrT, NoLineInfo):
            tb.addIdent(string("item"), NoLineInfo)
            tb.addStrLit(string("val"), NoLineInfo)
            tb.addIntLit(42)
        echo(string("tree: "), toString(tb, False))

        # nifbuilder proc
        with var:
            bld = open(16, compact=True)
        bld.addHeader()
        with bld.withTree(string("stmts")):
            bld.addIdent(string("foo"))
            bld.addIntLit(7)
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
