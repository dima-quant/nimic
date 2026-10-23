# /// nimic
#
# ///
## The std/os and std/times procs vfs uses, in Python (the nimic shims) and in compiled Nim: getTime, toUnix,
## nanosecond, fromUnix, Time comparisons and differences, getLastModificationTime, moveFile, existsOrCreateDir,
## sleep. Only deterministic facts are printed (tests/verify_transpiled.py nimic compares the outputs).
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.syncio import *
from nimic.std.times import *


if comptime(__name__ == "__main__"):
    def _main():
        with let:
            t = getTime()
        echo(string("after 2020 "), toUnix(t) > 1_577_836_800, string(", nanosecond in range "),
             t.nanosecond >= 0 and t.nanosecond < 1_000_000_000)
        echo(string("fromUnix "), toUnix(fromUnix(5)), string(" "), fromUnix(5).nanosecond)
        echo(string("order "), fromUnix(1) < fromUnix(2), string(" "), fromUnix(2) == fromUnix(2))
        echo(string("difference "), inSeconds(fromUnix(10) - fromUnix(4)))
        with let:
            dir = getTempDir() / string("nimic_std_os_times")
            src = dir / string("a.txt")
            dst = dir / string("b.txt")
        removeDir(dir)
        echo(string("created: existed "), existsOrCreateDir(dir))
        echo(string("again: existed "), existsOrCreateDir(dir))
        writeFile(src, string("payload"))
        with let:
            m = getLastModificationTime(src)
        echo(string("mtime after 2020 "), toUnix(m) > 1_577_836_800, string(", not in the future "), m <= getTime())
        moveFile(src, dst)
        echo(string("moved: source "), fileExists(src), string(", dest "), fileExists(dst), string(" "), readFile(dst))
        writeFile(src, string("other"))
        moveFile(src, dst)
        echo(string("replaced: "), readFile(dst))
        sleep(1)
        removeDir(dir)
        echo(string("removed "), dirExists(dir))

    _main()
