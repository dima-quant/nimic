# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# included from cgen.nim (include file: Snippet, Builder, TLabel, TCallingConvention come from the
# includer; tests: ncompiler/tests/test_cbuilders.py)


def _constType(t: Snippet) -> Snippet:
    # needs manipulation of `t` in nifc
    return string("NIM_CONST ") + t


def _constPtrType(t: Snippet) -> Snippet:
    return t + string("* NIM_CONST")


def _ptrConstType(t: Snippet) -> Snippet:
    return string("NIM_CONST ") + t + string("*")


def _ptrType(t: Snippet) -> Snippet:
    return t + string("*")


def _cppRefType(t: Snippet) -> Snippet:
    return t + string("&")


with const:
    _CallingConvToStr: array[TCallingConvention, string] = array[TCallingConvention, string]([
        string("N_NIMCALL"),
        string("N_STDCALL"), string("N_CDECL"), string("N_SAFECALL"),
        string("N_SYSCALL"),  # this is probably not correct for all platforms,
                              # but one can #define it to what one wants
        string("N_INLINE"), string("N_NOINLINE"), string("N_FASTCALL"), string("N_THISCALL"), string("N_CLOSURE"), string("N_NOCONV"),
        string("N_NOCONV"),  # ccMember is N_NOCONV
    ])


@dispatch
def _procPtrTypeUnnamed(rettype: Snippet, params: Snippet) -> Snippet:
    return rettype + string("(*)") + params


def _procPtrTypeUnnamedNimCall(rettype: Snippet, params: Snippet) -> Snippet:
    return rettype + string("(N_RAW_NIMCALL*)") + params


@dispatch
def _procPtrTypeUnnamed(callConv: TCallingConvention, rettype: Snippet, params: Snippet) -> Snippet:
    return _CallingConvToStr[callConv] + string("_PTR(") + rettype + string(", )") + params


class _CppCaptureKind(NIntEnum):
    None_ = 0
    ByReference = auto()
    ByCopy = auto()


@template
def _addCppLambda(builder: mut@Builder, captures: _CppCaptureKind, params: Snippet, body: typed):
    builder.add(string("["))
    match captures:
        case _CppCaptureKind.None_:
            discard
        case _CppCaptureKind.ByReference:
            builder.add(string("&"))
        case _CppCaptureKind.ByCopy:
            builder.add(string("="))
    builder.add(string("] "))
    builder.add(params)
    builder.addLineEndIndent(string(" {"))
    body
    builder.addLineEndDedent(string("}"))


def _cCast(typ: Snippet, value: Snippet) -> Snippet:
    return string("((") + typ + string(") ") + value + string(")")


def _wrapPar(value: Snippet) -> Snippet:
    # used for expression group, no-op on sexp
    return string("(") + value + string(")")


def _removeSinglePar(value: Snippet) -> Snippet:
    # removes a single paren layer expected to exist, to silence Wparentheses-equality
    assert value[0] == ch("(") and value[len(value) - 1] == ch(")")
    return value[1:len(value) - 1]


@template
def _addCast(builder: mut@Builder, typ: Snippet, valueBody: typed):
    """adds a cast to `typ` with value built by `valueBody`"""
    builder.add(string("(("))
    builder.add(typ)
    builder.add(string(") "))
    valueBody
    builder.add(string(")"))


def _cAddr(value: Snippet) -> Snippet:
    return string("(&") + value + string(")")


def _cLabelAddr(value: TLabel) -> Snippet:
    return string("&&") + value


def _cDeref(value: Snippet) -> Snippet:
    return string("(*") + value + string(")")


def _subscript(a: Snippet, b: Snippet) -> Snippet:
    return a + string("[") + b + string("]")


def _dotField(a: Snippet, b: Snippet) -> Snippet:
    return a + string(".") + b


def _derefField(a: Snippet, b: Snippet) -> Snippet:
    return a + string("->") + b


class _CallBuilder(Object):
    _needsComma: bool


def _initCallBuilder(builder: mut@Builder, callee: Snippet) -> _CallBuilder:
    result = _CallBuilder(_needsComma=False)
    builder.add(callee)
    builder.add(string("("))
    return result


with const:
    _cArgumentSeparator = string(", ")


def _addArgumentSeparator(builder: mut@Builder) -> None:
    # no-op on NIFC
    # used by "single argument" builders
    builder.add(_cArgumentSeparator)


@template
def _addArgument(builder: mut@Builder, call: mut@_CallBuilder, valueBody: typed):
    if call._needsComma:
        builder._addArgumentSeparator()
    else:
        call._needsComma = True
    valueBody


def _finishCallBuilder(builder: mut@Builder, call: _CallBuilder) -> None:
    builder.add(string(")"))


@template
def _addCall(builder: mut@Builder, call: out@_CallBuilder, callee: Snippet, body: typed):
    call <<= _initCallBuilder(builder, callee)
    body
    _finishCallBuilder(builder, call)


@dispatch
def _addCall(builder: mut@Builder, callee: Snippet, *args: Snippet) -> None:
    builder.add(callee)
    builder.add(string("("))
    if len(args) != 0:
        builder.add(args[0])
        for i in range(1, len(args)):
            builder.add(string(", "))
            builder.add(args[i])
    builder.add(string(")"))


@dispatch
def _cCall(callee: Snippet, *args: Snippet) -> Snippet:
    result = callee.copy()
    result.add(string("("))
    if len(args) != 0:
        result.add(args[0])
        for i in range(1, len(args)):
            result.add(string(", "))
            result.add(args[i])
    result.add(string(")"))
    return result


def _addSizeof(builder: mut@Builder, val: Snippet) -> None:
    builder.add(string("sizeof("))
    builder.add(val)
    builder.add(string(")"))


def _addAlignof(builder: mut@Builder, val: Snippet) -> None:
    builder.add(string("NIM_ALIGNOF("))
    builder.add(val)
    builder.add(string(")"))


def _addOffsetof(builder: mut@Builder, val: Snippet, member: Snippet) -> None:
    builder.add(string("offsetof("))
    builder.add(val)
    builder.add(string(", "))
    builder.add(member)
    builder.add(string(")"))


@template
def _cSizeof(val: Snippet) -> Snippet:
    return string("sizeof(") + val + string(")")


@template
def _cAlignof(val: Snippet) -> Snippet:
    return string("NIM_ALIGNOF(") + val + string(")")


@template
def _cOffsetof(val: Snippet, member: Snippet) -> Snippet:
    return string("offsetof(") + val + string(", ") + member + string(")")


class _TypedBinaryOp(NIntEnum):
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
    _typedBinaryOperators: array[_TypedBinaryOp, string] = array[_TypedBinaryOp, string]({
        _TypedBinaryOp.Add: string("+"),
        _TypedBinaryOp.Sub: string("-"),
        _TypedBinaryOp.Mul: string("*"),
        _TypedBinaryOp.Div: string("/"),
        _TypedBinaryOp.Mod: string("%"),
        _TypedBinaryOp.Shr: string(">>"),
        _TypedBinaryOp.Shl: string("<<"),
        _TypedBinaryOp.BitAnd: string("&"),
        _TypedBinaryOp.BitOr: string("|"),
        _TypedBinaryOp.BitXor: string("^"),
    })


class _TypedUnaryOp(NIntEnum):
    Neg = 0
    BitNot = auto()


with const:
    _typedUnaryOperators: array[_TypedUnaryOp, string] = array[_TypedUnaryOp, string]({
        _TypedUnaryOp.Neg: string("-"),
        _TypedUnaryOp.BitNot: string("~"),
    })


class _UntypedBinaryOp(NIntEnum):
    LessEqual = 0
    LessThan = auto()
    GreaterEqual = auto()
    GreaterThan = auto()
    Equal = auto()
    NotEqual = auto()
    And = auto()
    Or = auto()


with const:
    _untypedBinaryOperators: array[_UntypedBinaryOp, string] = array[_UntypedBinaryOp, string]({
        _UntypedBinaryOp.LessEqual: string("<="),
        _UntypedBinaryOp.LessThan: string("<"),
        _UntypedBinaryOp.GreaterEqual: string(">="),
        _UntypedBinaryOp.GreaterThan: string(">"),
        _UntypedBinaryOp.Equal: string("=="),
        _UntypedBinaryOp.NotEqual: string("!="),
        _UntypedBinaryOp.And: string("&&"),
        _UntypedBinaryOp.Or: string("||"),
    })


class _UntypedUnaryOp(NIntEnum):
    Not = 0


with const:
    _untypedUnaryOperators: array[_UntypedUnaryOp, string] = array[_UntypedUnaryOp, string]({
        _UntypedUnaryOp.Not: string("!"),
    })


@dispatch
def _addOp(builder: mut@Builder, binOp: _TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> None:
    builder.add(ch("("))
    builder.add(a)
    builder.add(ch(" "))
    builder.add(_typedBinaryOperators[binOp])
    builder.add(ch(" "))
    builder.add(b)
    builder.add(ch(")"))


@dispatch
def _addOp(builder: mut@Builder, unOp: _TypedUnaryOp, t: Snippet, a: Snippet) -> None:
    builder.add(ch("("))
    builder.add(_typedUnaryOperators[unOp])
    builder.add(ch("("))
    builder.add(a)
    builder.add(string("))"))


@dispatch
def _addOp(builder: mut@Builder, binOp: _UntypedBinaryOp, a: Snippet, b: Snippet) -> None:
    builder.add(ch("("))
    builder.add(a)
    builder.add(ch(" "))
    builder.add(_untypedBinaryOperators[binOp])
    builder.add(ch(" "))
    builder.add(b)
    builder.add(ch(")"))


@dispatch
def _addOp(builder: mut@Builder, unOp: _UntypedUnaryOp, a: Snippet) -> None:
    builder.add(ch("("))
    builder.add(_untypedUnaryOperators[unOp])
    builder.add(ch("("))
    builder.add(a)
    builder.add(string("))"))


@template
def _cOp(binOp: _TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> Snippet:
    return string("(") + a + string(" ") + _typedBinaryOperators[binOp] + string(" ") + b + string(")")


@template
def _cOp(binOp: _TypedUnaryOp, t: Snippet, a: Snippet) -> Snippet:
    return string("(") + _typedUnaryOperators[binOp] + string("(") + a + string("))")


@template
def _cOp(binOp: _UntypedBinaryOp, a: Snippet, b: Snippet) -> Snippet:
    return string("(") + a + string(" ") + _untypedBinaryOperators[binOp] + string(" ") + b + string(")")


@template
def _cOp(binOp: _UntypedUnaryOp, a: Snippet) -> Snippet:
    return string("(") + _untypedUnaryOperators[binOp] + string("(") + a + string("))")


@template
def _cIfExpr(cond: Snippet, a: Snippet, b: Snippet) -> Snippet:
    # XXX used for `min` and `max`, maybe add nifc primitives for these
    return string("(") + cond + string(" ? ") + a + string(" : ") + b + string(")")


@template
def _cUnlikely(val: Snippet) -> Snippet:
    return string("NIM_UNLIKELY(") + val + string(")")
