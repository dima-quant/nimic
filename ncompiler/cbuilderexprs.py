# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# included from cgen.nim (include file: Snippet, Builder, TLabel, TCallingConvention come from the
# includer; tests: ncompiler/tests/test_cbuilders.py)


def constType(t: Snippet) -> Snippet:
    # needs manipulation of `t` in nifc
    return string("NIM_CONST ") + t


def constPtrType(t: Snippet) -> Snippet:
    return t + string("* NIM_CONST")


def ptrConstType(t: Snippet) -> Snippet:
    return string("NIM_CONST ") + t + string("*")


def ptrType(t: Snippet) -> Snippet:
    return t + string("*")


def cppRefType(t: Snippet) -> Snippet:
    return t + string("&")


with const:
    CallingConvToStr: array[TCallingConvention, string] = array[TCallingConvention, string]([
        string("N_NIMCALL"),
        string("N_STDCALL"), string("N_CDECL"), string("N_SAFECALL"),
        string("N_SYSCALL"),  # this is probably not correct for all platforms,
                              # but one can #define it to what one wants
        string("N_INLINE"), string("N_NOINLINE"), string("N_FASTCALL"), string("N_THISCALL"), string("N_CLOSURE"), string("N_NOCONV"),
        string("N_NOCONV"),  # ccMember is N_NOCONV
    ])


@dispatch
def procPtrTypeUnnamed(rettype: Snippet, params: Snippet) -> Snippet:
    return rettype + string("(*)") + params


def procPtrTypeUnnamedNimCall(rettype: Snippet, params: Snippet) -> Snippet:
    return rettype + string("(N_RAW_NIMCALL*)") + params


@dispatch
def procPtrTypeUnnamed(callConv: TCallingConvention, rettype: Snippet, params: Snippet) -> Snippet:
    return CallingConvToStr[callConv] + string("_PTR(") + rettype + string(", )") + params


class CppCaptureKind(NIntEnum):
    None_ = 0
    ByReference = auto()
    ByCopy = auto()


@template
def addCppLambda(builder: mut@Builder, captures: CppCaptureKind, params: Snippet, body: typed):
    builder.add(string("["))
    match captures:
        case CppCaptureKind.None_:
            discard
        case CppCaptureKind.ByReference:
            builder.add(string("&"))
        case CppCaptureKind.ByCopy:
            builder.add(string("="))
    builder.add(string("] "))
    builder.add(params)
    builder.addLineEndIndent(string(" {"))
    body
    builder.addLineEndDedent(string("}"))


def cCast(typ: Snippet, value: Snippet) -> Snippet:
    return string("((") + typ + string(") ") + value + string(")")


def wrapPar(value: Snippet) -> Snippet:
    # used for expression group, no-op on sexp
    return string("(") + value + string(")")


def removeSinglePar(value: Snippet) -> Snippet:
    # removes a single paren layer expected to exist, to silence Wparentheses-equality
    assert value[0] == ch("(") and value[len(value) - 1] == ch(")")
    return value[1:len(value) - 1]


@template
def addCast(builder: mut@Builder, typ: Snippet, valueBody: typed):
    """adds a cast to `typ` with value built by `valueBody`"""
    builder.add(string("(("))
    builder.add(typ)
    builder.add(string(") "))
    valueBody
    builder.add(string(")"))


def cAddr(value: Snippet) -> Snippet:
    return string("(&") + value + string(")")


def cLabelAddr(value: TLabel) -> Snippet:
    return string("&&") + value


def cDeref(value: Snippet) -> Snippet:
    return string("(*") + value + string(")")


def subscript(a: Snippet, b: Snippet) -> Snippet:
    return a + string("[") + b + string("]")


def dotField(a: Snippet, b: Snippet) -> Snippet:
    return a + string(".") + b


def derefField(a: Snippet, b: Snippet) -> Snippet:
    return a + string("->") + b


class CallBuilder(Object):
    needsComma: bool


def initCallBuilder(builder: mut@Builder, callee: Snippet) -> CallBuilder:
    result = CallBuilder(needsComma=False)
    builder.add(callee)
    builder.add(string("("))
    return result


with const:
    cArgumentSeparator = string(", ")


def addArgumentSeparator(builder: mut@Builder) -> None:
    # no-op on NIFC
    # used by "single argument" builders
    builder.add(cArgumentSeparator)


@template
def addArgument(builder: mut@Builder, call: mut@CallBuilder, valueBody: typed):
    if call.needsComma:
        builder.addArgumentSeparator()
    else:
        call.needsComma = True
    valueBody


def finishCallBuilder(builder: mut@Builder, call: CallBuilder) -> None:
    builder.add(string(")"))


@template
def addCall(builder: mut@Builder, call: out@CallBuilder, callee: Snippet, body: typed):
    call <<= initCallBuilder(builder, callee)
    body
    finishCallBuilder(builder, call)


@dispatch
def addCall(builder: mut@Builder, callee: Snippet, *args: Snippet) -> None:
    builder.add(callee)
    builder.add(string("("))
    if len(args) != 0:
        builder.add(args[0])
        for i in range(1, len(args)):
            builder.add(string(", "))
            builder.add(args[i])
    builder.add(string(")"))


@dispatch
def cCall(callee: Snippet, *args: Snippet) -> Snippet:
    result = callee.copy()
    result.add(string("("))
    if len(args) != 0:
        result.add(args[0])
        for i in range(1, len(args)):
            result.add(string(", "))
            result.add(args[i])
    result.add(string(")"))
    return result


def addSizeof(builder: mut@Builder, val: Snippet) -> None:
    builder.add(string("sizeof("))
    builder.add(val)
    builder.add(string(")"))


def addAlignof(builder: mut@Builder, val: Snippet) -> None:
    builder.add(string("NIM_ALIGNOF("))
    builder.add(val)
    builder.add(string(")"))


def addOffsetof(builder: mut@Builder, val: Snippet, member: Snippet) -> None:
    builder.add(string("offsetof("))
    builder.add(val)
    builder.add(string(", "))
    builder.add(member)
    builder.add(string(")"))


@template
def cSizeof(val: Snippet) -> Snippet:
    return string("sizeof(") + val + string(")")


@template
def cAlignof(val: Snippet) -> Snippet:
    return string("NIM_ALIGNOF(") + val + string(")")


@template
def cOffsetof(val: Snippet, member: Snippet) -> Snippet:
    return string("offsetof(") + val + string(", ") + member + string(")")


class TypedBinaryOp(NIntEnum):
    Add = 0
    Sub = auto()
    Mul = auto()
    Div = auto()
    Mod = auto()
    Shr = auto()
    Shl = auto()
    BitAnd = auto()
    BitOr = auto()
    BitXor = auto()


with const:
    typedBinaryOperators: array[TypedBinaryOp, string] = array[TypedBinaryOp, string]({
        TypedBinaryOp.Add: string("+"),
        TypedBinaryOp.Sub: string("-"),
        TypedBinaryOp.Mul: string("*"),
        TypedBinaryOp.Div: string("/"),
        TypedBinaryOp.Mod: string("%"),
        TypedBinaryOp.Shr: string(">>"),
        TypedBinaryOp.Shl: string("<<"),
        TypedBinaryOp.BitAnd: string("&"),
        TypedBinaryOp.BitOr: string("|"),
        TypedBinaryOp.BitXor: string("^"),
    })


class TypedUnaryOp(NIntEnum):
    Neg = 0
    BitNot = auto()


with const:
    typedUnaryOperators: array[TypedUnaryOp, string] = array[TypedUnaryOp, string]({
        TypedUnaryOp.Neg: string("-"),
        TypedUnaryOp.BitNot: string("~"),
    })


class UntypedBinaryOp(NIntEnum):
    LessEqual = 0
    LessThan = auto()
    GreaterEqual = auto()
    GreaterThan = auto()
    Equal = auto()
    NotEqual = auto()
    And = auto()
    Or = auto()


with const:
    untypedBinaryOperators: array[UntypedBinaryOp, string] = array[UntypedBinaryOp, string]({
        UntypedBinaryOp.LessEqual: string("<="),
        UntypedBinaryOp.LessThan: string("<"),
        UntypedBinaryOp.GreaterEqual: string(">="),
        UntypedBinaryOp.GreaterThan: string(">"),
        UntypedBinaryOp.Equal: string("=="),
        UntypedBinaryOp.NotEqual: string("!="),
        UntypedBinaryOp.And: string("&&"),
        UntypedBinaryOp.Or: string("||"),
    })


class UntypedUnaryOp(NIntEnum):
    Not = 0


with const:
    untypedUnaryOperators: array[UntypedUnaryOp, string] = array[UntypedUnaryOp, string]({
        UntypedUnaryOp.Not: string("!"),
    })


@dispatch
def addOp(builder: mut@Builder, binOp: TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> None:
    builder.add(ch("("))
    builder.add(a)
    builder.add(ch(" "))
    builder.add(typedBinaryOperators[binOp])
    builder.add(ch(" "))
    builder.add(b)
    builder.add(ch(")"))


@dispatch
def addOp(builder: mut@Builder, unOp: TypedUnaryOp, t: Snippet, a: Snippet) -> None:
    builder.add(ch("("))
    builder.add(typedUnaryOperators[unOp])
    builder.add(ch("("))
    builder.add(a)
    builder.add(string("))"))


@dispatch
def addOp(builder: mut@Builder, binOp: UntypedBinaryOp, a: Snippet, b: Snippet) -> None:
    builder.add(ch("("))
    builder.add(a)
    builder.add(ch(" "))
    builder.add(untypedBinaryOperators[binOp])
    builder.add(ch(" "))
    builder.add(b)
    builder.add(ch(")"))


@dispatch
def addOp(builder: mut@Builder, unOp: UntypedUnaryOp, a: Snippet) -> None:
    builder.add(ch("("))
    builder.add(untypedUnaryOperators[unOp])
    builder.add(ch("("))
    builder.add(a)
    builder.add(string("))"))


@template
def cOp(binOp: TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> Snippet:
    return string("(") + a + string(" ") + typedBinaryOperators[binOp] + string(" ") + b + string(")")


@template
def cOp(binOp: TypedUnaryOp, t: Snippet, a: Snippet) -> Snippet:
    return string("(") + typedUnaryOperators[binOp] + string("(") + a + string("))")


@template
def cOp(binOp: UntypedBinaryOp, a: Snippet, b: Snippet) -> Snippet:
    return string("(") + a + string(" ") + untypedBinaryOperators[binOp] + string(" ") + b + string(")")


@template
def cOp(binOp: UntypedUnaryOp, a: Snippet) -> Snippet:
    return string("(") + untypedUnaryOperators[binOp] + string("(") + a + string("))")


@template
def cIfExpr(cond: Snippet, a: Snippet, b: Snippet) -> Snippet:
    # XXX used for `min` and `max`, maybe add nifc primitives for these
    return string("(") + cond + string(" ? ") + a + string(" : ") + b + string(")")


@template
def cUnlikely(val: Snippet) -> Snippet:
    return string("NIM_UNLIKELY(") + val + string(")")
