# /// nimic
#
# ///
## std/parseutils in Python (the nimic shim) and in compiled Nim: parseBiggestFloat (fast path, slop path,
## strtod slow path, NaN/Inf, extreme exponents, invalid/partial inputs), parseBiggestInt, parseBiggestUInt,
## parseHex, parseIdent, skipWhitespace and skipUntil on strings and on toOpenArray views of a
## ptr UncheckedArray[char] (tests/verify_transpiled.py nimic compares the outputs).
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.parseutils import *
from nimic.std import parseutils
from nimic.std.math import *


if comptime(__name__ == "__main__"):
    def _main():
        with var:
            f = BiggestFloat(0.0)
        for sample in [
            string("0"),
            string("-0.0"),
            string("32"),
            string("32.57"),
            string("-123.456"),
            string(".5"),
            string("5."),
            string("1_000.25_5"),
            string("0.1"),
            string("1e22"),
            string("1e-22"),
            string("123456789012345e7"),
            string("123456789012345e8"),
            string("8999999999999999"),
            string("9000000000000001"),
            string("1.2345678901234567890123456789"),
            string("1.234567890123456789e-50"),
            string("1e300"),
            string("-1e300"),
            string("5e-324"),
            string("-5e-324"),
            string("2.2250738585072014e-308"),
            string("1.7976931348623157e+308"),
            string("1e1000"),
            string("-1e1000"),
            string("1e-1000"),
            string("-1e-1000"),
            string("0e1000"),
            string("inf"),
            string("+Inf"),
            string("-INF"),
            string("nan"),
            string("NaN"),
            string("12.34px"),
            string("1.5e"),
        ]:
            f = BiggestFloat(-99.0)
            with let:
                n = parseBiggestFloat(sample, f)
            echo(sample, string(" -> n="), n, string(" val="), f, string(" class="), classify(f),
                 string(" bits="), cast[uint64](f))

        for bad in [string(""), string("+"), string("-"), string("abc"), string("infinit"), string("nanny"), string("1.5e+x")]:
            f = BiggestFloat(-77.5)
            with let:
                n = parseBiggestFloat(bad, f)
            echo(bad, string(" -> n="), n, string(" untouched="), f)

        echo(string("offset: "), parseBiggestFloat(string("xx32.57yy"), f, 2), string(" "), f)

        with var:
            buf = string("0.1 -1e300 5e-324 9223372036854775807 -9223372036854775808 18446744073709551615")
            p = cast[ptr[UncheckedArray[char]]](addr(buf[0]))
            iv = BiggestInt(0)
            uv = BiggestUInt(0)
        echo(string("ptr float1: "), parseutils.parseBiggestFloat(toOpenArray(p, 0, 2), f), string(" "), f,
             string(" "), cast[uint64](f))
        echo(string("ptr float2: "), parseutils.parseBiggestFloat(toOpenArray(p, 4, 9), f), string(" "), f)
        echo(string("ptr float3: "), parseutils.parseBiggestFloat(toOpenArray(p, 11, 16), f), string(" "), f,
             string(" "), cast[uint64](f))
        echo(string("ptr int1: "), parseutils.parseBiggestInt(toOpenArray(p, 18, 36), iv), string(" "), iv)
        echo(string("ptr int2: "), parseutils.parseBiggestInt(toOpenArray(p, 38, 57), iv), string(" "), iv)
        echo(string("ptr uint: "), parseutils.parseBiggestUInt(toOpenArray(p, 59, 78), uv), string(" "), uv)

        for over_i in [string("9223372036854775808"), string("-9223372036854775809")]:
            iv = BiggestInt(42)
            try:
                _ = parseutils.parseBiggestInt(over_i, iv)
                echo(string("unexpected ok"))
            except ValueError:
                echo(string("int overflow caught, untouched="), iv)

        for over_u in [string("18446744073709551616"), string("-1")]:
            uv = BiggestUInt(42)
            try:
                _ = parseutils.parseBiggestUInt(over_u, uv)
                echo(string("unexpected ok"))
            except ValueError:
                echo(string("uint overflow caught, untouched="), uv)

        with var:
            hx = nint(0)
            ident = string("")
            src = string("  foo_12 0xCAFE_01:tail")
            sp = cast[ptr[UncheckedArray[char]]](addr(src[0]))
        echo(string("ws: "), skipWhitespace(toOpenArray(sp, 0, src.len - 1)))
        echo(string("ident: "), parseIdent(toOpenArray(sp, 2, src.len - 1), ident), string(" "), ident)
        echo(string("hex: "), parseHex(toOpenArray(sp, 9, src.len - 1), hx), string(" "), hx)
        echo(string("until: "), skipUntil(toOpenArray(sp, 9, src.len - 1), Tset[char](char(':'))))

    _main()
