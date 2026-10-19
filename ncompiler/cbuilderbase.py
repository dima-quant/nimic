# /// nimic
#
# ///
from __future__ import annotations
from nimic.ntypes import *
from .ropes import *
from .int128 import *


Snippet = string


class Builder(Object):
    buf: string
    indents: nint

    def extract(builder: Builder) -> Snippet:
        return builder.buf

    def add(builder: mut @ Builder, s: string):
        builder.buf.add(s)

    def add(builder: mut @ Builder, s: char):
        builder.buf.add(s)

    def addNewline(builder: mut @ Builder):
        builder.add(ch('\n'))
        for i in range(builder.indents):
            builder.add(ch('\t'))

    def addLineEnd(builder: mut @ Builder, s: string):
        builder.add(s)
        builder.addNewline()

    def addLineEndIndent(builder: mut @ Builder, s: string):
        builder.indents += 1
        builder.add(s)
        builder.addNewline()

    def addDedent(builder: mut @ Builder, s: string):
        # Nim: builder.buf[^1] (no nimic spelling for ^1 yet)
        if builder.buf.len > 0 and builder.buf[builder.buf.len - 1] == ch('\t'):
            builder.buf.setLen(builder.buf.len - 1)
        builder.add(s)
        builder.indents -= 1

    def addLineEndDedent(builder: mut @ Builder, s: string):
        builder.addDedent(s)
        builder.addNewline()

    def addLineComment(builder: mut @ Builder, comment: string):
        # probably no-op on nifc
        builder.add(string("// "))
        builder.add(comment)
        builder.addNewline()

    def addIntValue(builder: mut @ Builder, val: nint):
        builder.buf.addInt(val)

    def addIntValue(builder: mut @ Builder, val: int64):
        builder.buf.addInt(val)

    def addIntValue(builder: mut @ Builder, val: uint64):
        builder.buf.addInt(val)

    def addIntValue(builder: mut @ Builder, val: Int128):
        addInt128(builder.buf, val)

    def addInt64Literal(result: mut @ Builder, i: BiggestInt):
        if i > low(int64):
            result.add(FormatStr("IL64($1)") % [rope(i)])
        else:
            result.add(string("(IL64(-9223372036854775807) - IL64(1))"))

    def addUint64Literal(result: mut @ Builder, i: uint64):
        result.add(rope(string(str(i)) + "ULL"))

    def addIntLiteral(result: mut @ Builder, i: BiggestInt):
        if i > low(int32) and i <= high(int32):
            result.addIntValue(i)
        elif i == low(int32):
            # Nim has the same bug for the same reasons :-)
            result.add(string("(-2147483647 -1)"))
        elif i > low(int64):
            result.add(FormatStr("IL64($1)") % [rope(i)])
        else:
            result.add(string("(IL64(-9223372036854775807) - IL64(1))"))

    def addIntLiteral(result: mut @ Builder, i: Int128):
        result.addIntLiteral(toInt64(i))


@template
def newBuilder(s: string) -> Builder:
    return Builder(buf=s)


@template
def cIntValue(val: nint) -> Snippet:
    return string(str(val))


@template
def cIntValue(val: int64) -> Snippet:
    return string(str(val))


@template
def cIntValue(val: uint64) -> Snippet:
    return string(str(val))


@template
def cIntValue(val: Int128) -> Snippet:
    return string(str(val))


@template
def cUintValue(val: uint) -> Snippet:
    return string(str(val)) + "U"


from nimic.std.formatfloat import *


def addFloatValue(builder: mut @ Builder, val: float):
    builder.buf.addFloat(val)


@template
def cFloatValue(val: float) -> Snippet:
    return string(str(val))


def cInt64Literal(i: BiggestInt) -> Snippet:
    if i > low(int64):
        result = FormatStr("IL64($1)") % [rope(i)]
    else:
        result = string("(IL64(-9223372036854775807) - IL64(1))")
    return result


def cUint64Literal(i: uint64) -> Snippet:
    result = string(str(i)) + "ULL"
    return result


@dispatch
def cIntLiteral(i: BiggestInt) -> Snippet:
    if i > low(int32) and i <= high(int32):
        result = rope(i)
    elif i == low(int32):
        # Nim has the same bug for the same reasons :-)
        result = string("(-2147483647 -1)")
    elif i > low(int64):
        result = FormatStr("IL64($1)") % [rope(i)]
    else:
        result = string("(IL64(-9223372036854775807) - IL64(1))")
    return result


@dispatch
def cIntLiteral(i: Int128) -> Snippet:
    result = cIntLiteral(toInt64(i))
    return result


with const:
    NimInt = string("NI")
    NimInt8 = string("NI8")
    NimInt16 = string("NI16")
    NimInt32 = string("NI32")
    NimInt64 = string("NI64")
    CInt = string("int")
    NimUint = string("NU")
    NimUint8 = string("NU8")
    NimUint16 = string("NU16")
    NimUint32 = string("NU32")
    NimUint64 = string("NU64")
    NimFloat = string("NF")
    NimFloat32 = string("NF32")
    NimFloat64 = string("NF64")
    NimFloat128 = string("NF128")  # not actually defined
    NimNan = string("NAN")
    NimInf = string("INF")
    NimBool = string("NIM_BOOL")
    NimTrue = string("NIM_TRUE")
    NimFalse = string("NIM_FALSE")
    NimChar = string("NIM_CHAR")
    CChar = string("char")
    NimCstring = string("NCSTRING")
    NimNil = string("NIM_NIL")
    CNil = string("NULL")
    NimStrlitFlag = string("NIM_STRLIT_FLAG")
    CVoid = string("void")
    CPointer = string("void*")
    CConstPointer = string("NIM_CONST void*")


def cIntType(bits: BiggestInt) -> Snippet:
    return string("NI") + str(bits)


def cUintType(bits: BiggestInt) -> Snippet:
    return string("NU") + str(bits)


class IfBuilderState(NIntEnum):
    WaitingIf = 0
    WaitingElseIf = auto()
    InBlock = auto()


class IfBuilder(Object):
    state: IfBuilderState


if comptime(__name__ == "__main__"):
    def test_cbuilderbase():
        with var:
            b = newBuilder(string(""))
        b.add(string("int x;"))
        b.addNewline()
        b.addLineEndIndent(string("{"))
        b.addLineComment(string("body"))
        b.addLineEndDedent(string("}"))
        b.add(ch('x'))
        doAssert(b.extract() == "int x;\n{\n\t// body\n}\nx", string("indent/dedent: ") + b.extract())

        with var:
            c = newBuilder(string(""))
        c.addIntValue(nint(-5))
        c.add(ch(' '))
        c.addIntValue(u64(18446744073709551615))
        c.add(ch(' '))
        c.addIntValue(parseDecimalInt128(string("-170141183460469231731687303715884105727")))
        c.add(ch(' '))
        c.addFloatValue(0.5)
        doAssert(c.extract() == "-5 18446744073709551615 -170141183460469231731687303715884105727 0.5",
                 string("values: ") + c.extract())

        with var:
            lit = newBuilder(string(""))
        lit.addIntLiteral(BiggestInt(42))
        lit.add(ch(' '))
        lit.addIntLiteral(BiggestInt(-2147483648))
        lit.add(ch(' '))
        lit.addIntLiteral(BiggestInt(4294967296))
        lit.add(ch(' '))
        lit.addIntLiteral(low(int64))
        lit.add(ch(' '))
        lit.addIntLiteral(toInt128(int64(-7)))
        lit.add(ch(' '))
        lit.addInt64Literal(BiggestInt(3))
        lit.add(ch(' '))
        lit.addUint64Literal(u64(9))
        doAssert(lit.extract() == "42 (-2147483647 -1) IL64(4294967296) (IL64(-9223372036854775807) - IL64(1)) -7 IL64(3) 9ULL",
                 string("literals: ") + lit.extract())

        doAssert(cIntLiteral(BiggestInt(7)) == "7", string("cIntLiteral"))
        doAssert(cIntLiteral(BiggestInt(-4294967296)) == "IL64(-4294967296)", string("cIntLiteral 64"))
        doAssert(cIntLiteral(toInt128(int64(12))) == "12", string("cIntLiteral Int128"))
        doAssert(cInt64Literal(low(int64)) == "(IL64(-9223372036854775807) - IL64(1))", string("cInt64Literal"))
        doAssert(cUint64Literal(u64(1)) == "1ULL", string("cUint64Literal"))
        doAssert(cIntValue(toInt128(int64(-3))) == "-3", string("cIntValue Int128"))
        doAssert(cIntValue(int64(3)) == "3", string("cIntValue int64"))
        doAssert(cUintValue(uint(4)) == "4U", string("cUintValue"))
        doAssert(cFloatValue(2.5) == "2.5", string("cFloatValue"))
        doAssert(cIntType(BiggestInt(32)) == "NI32" and cUintType(BiggestInt(8)) == "NU8", string("int types"))
        with var:
            e = newBuilder(string(""))
        e.addLineEnd(string("a;"))
        e.addDedent(string("}"))  # no trailing tab to remove
        e.add(ch(' '))
        e.addIntValue(int64(-7))
        e.add(ch(' '))
        e.addIntLiteral(BiggestInt(2147483647))
        e.add(ch(' '))
        e.addIntLiteral(BiggestInt(-2147483647))
        e.add(ch(' '))
        e.addIntLiteral(BiggestInt(2147483648))
        e.add(ch(' '))
        e.addInt64Literal(low(int64))
        doAssert(e.extract() == "a;\n} -7 2147483647 -2147483647 IL64(2147483648) (IL64(-9223372036854775807) - IL64(1))",
                 string("boundaries: ") + e.extract())
        doAssert(e.indents == -1, string("dedent below zero, as in Nim"))
        doAssert(cIntValue(nint(-1)) == "-1" and cIntValue(u64(18446744073709551615)) == "18446744073709551615",
                 string("cIntValue nint/uint64"))
        echo(string("cbuilderbase tests passed"))

    test_cbuilderbase()
