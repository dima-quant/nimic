# /// nimic
#
# ///
## std/memfiles in Python (the nimic shim, a port of Nim 2.2.4's POSIX memfiles) and in compiled Nim: reading
## through the mapping, memSlices / lines with `\r` trimmed, MemSlice `==` and `$`, writing through a mapping
## made with newFileSize, flush, allowRemap and resize (tests/verify_transpiled.py nimic compares the outputs).
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.syncio import *
from nimic.std.memfiles import *
from nimic.std import memfiles


if comptime(__name__ == "__main__"):
    def _main():
        with let:
            path = getTempDir() / string("nimic_std_memfiles_test.txt")
        writeFile(path, string("alpha\r\nbeta\ngamma"))
        with var:
            m = memfiles.open(path)
        echo(string("size "), m.size)
        with let:
            chars = cast[ptr[UncheckedArray[char]]](m.mem)
        echo(string("first "), chars[0], string(" last "), chars[m.size - 1])
        with var:
            n = 0
        for ms in memSlices(m):
            echo(string("slice ["), str(ms), string("] "), ms.size)
            n += 1
        echo(string("slices "), n)
        for line in lines(m):
            echo(string("line "), line)
        with var:
            buf = string("")
        for line in lines(m, buf):
            echo(string("buffered line "), line)
        with var:
            first = MemSlice(data=m.mem, size=5)
            again = MemSlice(data=m.mem, size=5)
            other = MemSlice(data=m.mem, size=4)
        echo(string("== "), first == again, string(" "), first == other)
        memfiles.close(m)
        echo(string("closed: mem nil "), isNil(m.mem), string(", size "), m.size)

        # a new file of 4 bytes, written through the mapping
        with var:
            w = memfiles.open(path, mode=fmReadWrite, newFileSize=4)
        with let:
            wchars = cast[ptr[UncheckedArray[char]]](w.mem)
        wchars[0] = char('W')
        wchars[1] = char('X')
        wchars[2] = char('Y')
        wchars[3] = char('Z')
        memfiles.flush(w)
        memfiles.close(w)
        echo(string("written "), readFile(path))

        # allowRemap keeps the descriptor for resize
        with var:
            r = memfiles.open(path, mode=fmReadWrite, allowRemap=True)
        echo(string("descriptor kept "), r.handle != -1)
        memfiles.resize(r, 6)
        with let:
            rchars = cast[ptr[UncheckedArray[char]]](r.mem)
        rchars[4] = char('!')
        rchars[5] = char('?')
        memfiles.close(r)
        echo(string("resized "), readFile(path), string(", descriptor after close "), r.handle)
        removeFile(path)

    _main()
