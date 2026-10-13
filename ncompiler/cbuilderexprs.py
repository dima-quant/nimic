# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2021 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# included from cgen.nim

if not comptime(defined("c")):
    Snippet = string
    TLabel = string
    varargs = seq

    class TCallingConvention(NIntEnum):
        ccNimCall = 0
        ccStdCall = auto()
        ccCDecl = auto()
        ccSafeCall = auto()
        ccSysCall = auto()
        ccInline = auto()
        ccNoInline = auto()
        ccFastCall = auto()
        ccThisCall = auto()
        ccClosure = auto()
        ccNoConvention = auto()
        ccMember = auto()

    class Builder(Object):
        buf: string = string("")
        indents: nint = 0

        def add(self: mut@Builder, s: string) -> None:
            self.buf.add(s)

        def add(self: mut@Builder, s: char) -> None:
            self.buf.add(s)

        def addNewline(self: mut@Builder) -> None:
            self.add(string("\n"))
            for i in range(self.indents):
                self.add(string("\t"))

        def addLineEnd(self: mut@Builder, s: string) -> None:
            self.add(s)
            self.addNewline()

        def addLineEndIndent(self: mut@Builder, s: string) -> None:
            self.indents += 1
            self.add(s)
            self.addNewline()

        def addDedent(self: mut@Builder, s: string) -> None:
            if len(self.buf) > 0 and self.buf[len(self.buf) - 1] == ch("\t"):
                self.buf = self.buf[0:len(self.buf) - 1]
            self.add(s)
            self.indents -= 1

        def addLineEndDedent(self: mut@Builder, s: string) -> None:
            self.addDedent(s)
            self.addNewline()

    def extract(builder: Builder) -> Snippet:
        return builder.buf

if comptime(defined("c")):
    if comptime(not declared(Snippet)):
        class Snippet(string):
            pass

    if comptime(not declared(TLabel)):
        class TLabel(string):
            pass

    if comptime(not declared(TCallingConvention)):
        class TCallingConvention(NIntEnum):
            ccNimCall = 0
            ccStdCall = auto()
            ccCDecl = auto()
            ccSafeCall = auto()
            ccSysCall = auto()
            ccInline = auto()
            ccNoInline = auto()
            ccFastCall = auto()
            ccThisCall = auto()
            ccClosure = auto()
            ccNoConvention = auto()
            ccMember = auto()

    if comptime(not declared(Builder)):
        class Builder(Object):
            buf: string = string("")
            indents: nint = 0

            def add(self: mut@Builder, s: string) -> None:
                self.buf.add(s)

            def add(self: mut@Builder, s: char) -> None:
                self.buf.add(s)

            def addNewline(self: mut@Builder) -> None:
                self.add(string("\n"))
                for i in range(self.indents):
                    self.add(string("\t"))

            def addLineEnd(self: mut@Builder, s: string) -> None:
                self.add(s)
                self.addNewline()

            def addLineEndIndent(self: mut@Builder, s: string) -> None:
                self.indents += 1
                self.add(s)
                self.addNewline()

            def addDedent(self: mut@Builder, s: string) -> None:
                if len(self.buf) > 0 and self.buf[len(self.buf) - 1] == ch("\t"):
                    self.buf = self.buf[0:len(self.buf) - 1]
                self.add(s)
                self.indents -= 1

            def addLineEndDedent(self: mut@Builder, s: string) -> None:
                self.addDedent(s)
                self.addNewline()

        def extract(builder: Builder) -> Snippet:
            return builder.buf


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
        string("N_STDCALL"),
        string("N_CDECL"),
        string("N_SAFECALL"),
        string("N_SYSCALL"),
        string("N_INLINE"),
        string("N_NOINLINE"),
        string("N_FASTCALL"),
        string("N_THISCALL"),
        string("N_CLOSURE"),
        string("N_NOCONV"),
        string("N_NOCONV"),
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
    doAssert(value[0] == ch("(") and value[len(value) - 1] == ch(")"))
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
def addCall(builder: mut@Builder, call: mut@CallBuilder, callee: Snippet, body: typed):
    call = initCallBuilder(builder, callee)
    body
    finishCallBuilder(builder, call)


@dispatch
def addCall(builder: mut@Builder, callee: Snippet, args: varargs[Snippet]) -> None:
    builder.add(callee)
    builder.add(string("("))
    if len(args) != 0:
        builder.add(args[0])
        for i in inrange(1, len(args) - 1):
            builder.add(string(", "))
            builder.add(args[i])
    builder.add(string(")"))


@dispatch
def cCall(callee: Snippet, args: varargs[Snippet]) -> Snippet:
    result = callee
    result.add(string("("))
    if len(args) != 0:
        result.add(args[0])
        for i in inrange(1, len(args) - 1):
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
    typedBinaryOperators: array[TypedBinaryOp, string] = array[TypedBinaryOp, string]([
        string("+"),
        string("-"),
        string("*"),
        string("/"),
        string("%"),
        string(">>"),
        string("<<"),
        string("&"),
        string("|"),
        string("^"),
    ])


class TypedUnaryOp(NIntEnum):
    Neg = 0
    BitNot = auto()


with const:
    typedUnaryOperators: array[TypedUnaryOp, string] = array[TypedUnaryOp, string]([
        string("-"),
        string("~"),
    ])


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
    untypedBinaryOperators: array[UntypedBinaryOp, string] = array[UntypedBinaryOp, string]([
        string("<="),
        string("<"),
        string(">="),
        string(">"),
        string("=="),
        string("!="),
        string("&&"),
        string("||"),
    ])


class UntypedUnaryOp(NIntEnum):
    Not = 0


with const:
    untypedUnaryOperators: array[UntypedUnaryOp, string] = array[UntypedUnaryOp, string]([
        string("!"),
    ])


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


if comptime(__name__ == "__main__"):
    if not comptime(defined("c")):
        class AddCppLambdaCtx(Object):
            builder: Builder
            captures: CppCaptureKind
            params: Snippet

            def enter(self) -> AddCppLambdaCtx:
                self.builder.add(string("["))
                if self.captures == CppCaptureKind.ByReference:
                    self.builder.add(string("&"))
                elif self.captures == CppCaptureKind.ByCopy:
                    self.builder.add(string("="))
                self.builder.add(string("] "))
                self.builder.add(self.params)
                self.builder.addLineEndIndent(string(" {"))
                return self

            def exit(self) -> None:
                self.builder.addLineEndDedent(string("}"))

        class AddCastCtx(Object):
            builder: Builder
            typ: Snippet

            def enter(self) -> AddCastCtx:
                self.builder.add(string("(("))
                self.builder.add(self.typ)
                self.builder.add(string(") "))
                return self

            def exit(self) -> None:
                self.builder.add(string(")"))

        class AddArgumentCtx(Object):
            builder: Builder
            call: object

            def enter(self) -> AddArgumentCtx:
                if self.call.needsComma:
                    addArgumentSeparator(self.builder)
                else:
                    self.call.needsComma = True
                return self

            def exit(self) -> None:
                pass

        class AddCallBlockCtx(Object):
            builder: Builder
            call: object
            callee: Snippet

            def enter(self) -> AddCallBlockCtx:
                self.call.needsComma = False
                self.builder.add(self.callee)
                self.builder.add(string("("))
                return self

            def exit(self) -> None:
                self.builder.add(string(")"))

        setattr(AddCppLambdaCtx, "__enter__", lambda self: self.enter())
        setattr(AddCppLambdaCtx, "__exit__", lambda self, *args: self.exit())
        setattr(AddCastCtx, "__enter__", lambda self: self.enter())
        setattr(AddCastCtx, "__exit__", lambda self, *args: self.exit())
        setattr(AddArgumentCtx, "__enter__", lambda self: self.enter())
        setattr(AddArgumentCtx, "__exit__", lambda self, *args: self.exit())
        setattr(AddCallBlockCtx, "__enter__", lambda self: self.enter())
        setattr(AddCallBlockCtx, "__exit__", lambda self, *args: self.exit())

        def _py_addCppLambda(builder: Builder, captures: CppCaptureKind, params: Snippet) -> AddCppLambdaCtx:
            with var:
                ctx = AddCppLambdaCtx()
            ctx.builder = builder
            ctx.captures = captures
            ctx.params = params
            return ctx

        def _py_addCast(builder: Builder, typ: Snippet) -> AddCastCtx:
            with var:
                ctx = AddCastCtx()
            ctx.builder = builder
            ctx.typ = typ
            return ctx

        def _py_addArgument(builder: Builder, call: CallBuilder) -> AddArgumentCtx:
            with var:
                ctx = AddArgumentCtx()
            ctx.builder = builder
            ctx.call = call
            return ctx

        _orig_cCall = cCall
        def _py_cCall(callee: Snippet, a1: Snippet = None, a2: Snippet = None) -> Snippet:
            if a1 is None:
                return _orig_cCall(callee, seq[Snippet]())
            elif a2 is None:
                if isinstance(a1, seq):
                    return _orig_cCall(callee, a1)
                else:
                    return _orig_cCall(callee, seq[Snippet]([a1]))
            else:
                return _orig_cCall(callee, seq[Snippet]([a1, a2]))

        _orig_addCall = addCall
        def _py_addCall_block(builder: Builder, call: CallBuilder, callee: Snippet) -> AddCallBlockCtx:
            with var:
                ctx = AddCallBlockCtx()
            ctx.builder = builder
            ctx.call = call
            ctx.callee = callee
            return ctx

        def _py_addCall_proc(builder: Builder, callee: Snippet, a1: Snippet = None, a2: Snippet = None) -> None:
            if a1 is None:
                _orig_addCall(builder, callee, seq[Snippet]())
            elif a2 is None:
                if isinstance(a1, seq):
                    _orig_addCall(builder, callee, a1)
                else:
                    _orig_addCall(builder, callee, seq[Snippet]([a1]))
            else:
                _orig_addCall(builder, callee, seq[Snippet]([a1, a2]))

        def _py_addCall_dispatch(builder: Builder, a1: object = None, a2: object = None, a3: object = None) -> object:
            if isinstance(a1, CallBuilder):
                return _py_addCall_block(builder, a1, a2)
            return _py_addCall_proc(builder, a1, a2, a3)

        addCppLambda = _py_addCppLambda
        addCast = _py_addCast
        addArgument = _py_addArgument
        addCall = _py_addCall_dispatch
        cCall = _py_cCall

    # Unit tests
    echo(string("Testing cbuilderexprs..."))

    # 1. Type helpers
    doAssert(constType(string("int")) == string("NIM_CONST int"), string("constType"))
    doAssert(constPtrType(string("int")) == string("int* NIM_CONST"), string("constPtrType"))
    doAssert(ptrConstType(string("int")) == string("NIM_CONST int*"), string("ptrConstType"))
    doAssert(ptrType(string("int")) == string("int*"), string("ptrType"))
    doAssert(cppRefType(string("int")) == string("int&"), string("cppRefType"))

    # 2. Calling convention to string and proc ptrs
    doAssert(CallingConvToStr[TCallingConvention.ccNimCall] == string("N_NIMCALL"), string("ccNimCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccStdCall] == string("N_STDCALL"), string("ccStdCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccCDecl] == string("N_CDECL"), string("ccCDecl"))
    doAssert(CallingConvToStr[TCallingConvention.ccSafeCall] == string("N_SAFECALL"), string("ccSafeCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccSysCall] == string("N_SYSCALL"), string("ccSysCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccInline] == string("N_INLINE"), string("ccInline"))
    doAssert(CallingConvToStr[TCallingConvention.ccNoInline] == string("N_NOINLINE"), string("ccNoInline"))
    doAssert(CallingConvToStr[TCallingConvention.ccFastCall] == string("N_FASTCALL"), string("ccFastCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccThisCall] == string("N_THISCALL"), string("ccThisCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccClosure] == string("N_CLOSURE"), string("ccClosure"))
    doAssert(CallingConvToStr[TCallingConvention.ccNoConvention] == string("N_NOCONV"), string("ccNoConvention"))
    doAssert(CallingConvToStr[TCallingConvention.ccMember] == string("N_NOCONV"), string("ccMember"))

    doAssert(procPtrTypeUnnamed(string("void"), string("()")) == string("void(*)()"), string("procPtrTypeUnnamed 2"))
    doAssert(procPtrTypeUnnamedNimCall(string("void"), string("()")) == string("void(N_RAW_NIMCALL*)()"), string("procPtrTypeUnnamedNimCall"))
    doAssert(procPtrTypeUnnamed(TCallingConvention.ccNimCall, string("void"), string("()")) == string("N_NIMCALL_PTR(void, )()"), string("procPtrTypeUnnamed 3"))

    # 3. Cast, Paren, Addr, Deref, Dot, Subscript
    doAssert(cCast(string("int"), string("x")) == string("((int) x)"), string("cCast"))
    doAssert(wrapPar(string("x + y")) == string("(x + y)"), string("wrapPar"))
    doAssert(removeSinglePar(string("(x + y)")) == string("x + y"), string("removeSinglePar"))
    doAssert(cAddr(string("x")) == string("(&x)"), string("cAddr"))
    doAssert(cLabelAddr(string("L1")) == string("&&L1"), string("cLabelAddr"))
    doAssert(cDeref(string("p")) == string("(*p)"), string("cDeref"))
    doAssert(subscript(string("arr"), string("0")) == string("arr[0]"), string("subscript"))
    doAssert(dotField(string("obj"), string("field")) == string("obj.field"), string("dotField"))
    doAssert(derefField(string("ptr"), string("field")) == string("ptr->field"), string("derefField"))

    # 4. Sizes and align
    doAssert(cSizeof(string("int")) == string("sizeof(int)"), string("cSizeof"))
    doAssert(cAlignof(string("int")) == string("NIM_ALIGNOF(int)"), string("cAlignof"))
    doAssert(cOffsetof(string("Type"), string("field")) == string("offsetof(Type, field)"), string("cOffsetof"))
    doAssert(cIfExpr(string("cond"), string("a"), string("b")) == string("(cond ? a : b)"), string("cIfExpr"))
    doAssert(cUnlikely(string("x")) == string("NIM_UNLIKELY(x)"), string("cUnlikely"))

    # 5. Calls
    doAssert(cCall(string("foo")) == string("foo()"), string("cCall 0"))
    doAssert(cCall(string("foo"), string("a")) == string("foo(a)"), string("cCall 1"))
    doAssert(cCall(string("foo"), string("a"), string("b")) == string("foo(a, b)"), string("cCall 2"))

    # 6. Builder operations
    with var:
        b = Builder()
    addSizeof(b, string("int"))
    doAssert(extract(b) == string("sizeof(int)"), string("addSizeof"))

    with var:
        b2 = Builder()
    addAlignof(b2, string("int"))
    doAssert(extract(b2) == string("NIM_ALIGNOF(int)"), string("addAlignof"))

    with var:
        b3 = Builder()
    addOffsetof(b3, string("Type"), string("field"))
    doAssert(extract(b3) == string("offsetof(Type, field)"), string("addOffsetof"))

    with var:
        b4 = Builder()
    addCall(b4, string("bar"), string("x"), string("y"))
    doAssert(extract(b4) == string("bar(x, y)"), string("addCall args"))

    # 7. Operator helpers
    with var:
        b5 = Builder()
    addOp(b5, TypedBinaryOp.Add, string("int"), string("a"), string("b"))
    doAssert(extract(b5) == string("(a + b)"), string("addOp TypedBinaryOp"))

    with var:
        b6 = Builder()
    addOp(b6, TypedUnaryOp.Neg, string("int"), string("a"))
    doAssert(extract(b6) == string("(-(a))"), string("addOp TypedUnaryOp"))

    with var:
        b7 = Builder()
    addOp(b7, UntypedBinaryOp.Equal, string("a"), string("b"))
    doAssert(extract(b7) == string("(a == b)"), string("addOp UntypedBinaryOp"))

    with var:
        b8 = Builder()
    addOp(b8, UntypedUnaryOp.Not, string("a"))
    doAssert(extract(b8) == string("(!(a))"), string("addOp UntypedUnaryOp"))

    doAssert(cOp(TypedBinaryOp.Mul, string("int"), string("a"), string("b")) == string("(a * b)"), string("cOp TypedBinaryOp"))
    doAssert(cOp(TypedUnaryOp.BitNot, string("int"), string("a")) == string("(~(a))"), string("cOp TypedUnaryOp"))
    doAssert(cOp(UntypedBinaryOp.LessEqual, string("a"), string("b")) == string("(a <= b)"), string("cOp UntypedBinaryOp"))
    doAssert(cOp(UntypedUnaryOp.Not, string("a")) == string("(!(a))"), string("cOp UntypedUnaryOp"))

    # 8. Template block builders (with statements)
    with var:
        b_cast = Builder()
    with addCast(b_cast, string("char*")):
        b_cast.add(string("p"))
    doAssert(extract(b_cast) == string("((char*) p)"), string("with addCast"))

    with var:
        b_cb = Builder()
        cb = CallBuilder()
    with addCall(b_cb, cb, string("func")):
        with addArgument(b_cb, cb):
            b_cb.add(string("1"))
        with addArgument(b_cb, cb):
            b_cb.add(string("2"))
    doAssert(extract(b_cb) == string("func(1, 2)"), string("with addCall and addArgument"))

    with var:
        b_lambda = Builder()
    with addCppLambda(b_lambda, CppCaptureKind.ByReference, string("int x")):
        b_lambda.addLineEnd(string("return x;"))
    doAssert(extract(b_lambda) == string("[&] int x {\n\treturn x;\n}\n"), string("with addCppLambda"))

    echo(string("All cbuilderexprs tests passed successfully!"))
