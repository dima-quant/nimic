# /// nimic
#
# ///
## std/varints and std/sha1 in Python (the nimic shims) and in compiled Nim: varint lengths and bytes at every
## encoding boundary, round trips, too short buffers, zigzag; SHA-1 digests of strings in one and in several
## updates, `$`, parseSecureHash, `==`, isValidSha1Hash (tests/verify_transpiled.py nimic compares the outputs).
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.varints import *
from nimic.std.sha1 import *


if comptime(__name__ == "__main__"):
    def _main():
        with var:
            buf = array[maxVarIntLen, uint8]()
            back = uint64(0)
        for x in [uint64(0), uint64(240), uint64(241), uint64(2287), uint64(2288), uint64(67823), uint64(67824),
                  uint64(16777215), uint64(16777216), uint64(4294967295), uint64(4294967296),
                  uint64(1099511627776), uint64(72057594037927936), uint64(18446744073709551615)]:
            with let:
                n = writeVu64(buf, x)
                m = readVu64(buf, back)
            echo(x, string(": "), n, string(" bytes, first "), buf[0], string(", read "), m, string(" "), back,
                 string(" "), back == x)
        with var:
            short = array[1, uint8]()
        short[0] = uint8(249)
        echo(string("too short: "), readVu64(short, back))
        echo(string("zigzag "), encodeZigzag(int64(0)), string(" "), encodeZigzag(int64(-1)), string(" "),
             encodeZigzag(int64(1)), string(" "), encodeZigzag(int64(-2)))
        echo(string("unzigzag "), decodeZigzag(uint64(0)), string(" "), decodeZigzag(uint64(1)), string(" "),
             decodeZigzag(uint64(2)), string(" "), decodeZigzag(uint64(3)))

        with let:
            h = secureHash(string("Hello World"))
        echo(string("sha1 "), h)
        with var:
            state = newSha1State()
        state.update(string("Hello "))
        state.update(string("World"))
        with let:
            parts = SecureHash(state.finalize())
        echo(string("in parts "), parts, string(" same "), parts == h)
        echo(string("empty "), secureHash(string("")))
        echo(string("parsed "), parseSecureHash(string("0A4D55A8D778E5022FAB701977C5D840BBC486D0")) == h)
        echo(string("valid "), isValidSha1Hash(string("0A4D55A8D778E5022FAB701977C5D840BBC486D0")), string(" "),
             isValidSha1Hash(string("xyz")))

    _main()
