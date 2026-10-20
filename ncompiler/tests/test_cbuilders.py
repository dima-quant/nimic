# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.intsets import *
from nimic.std.tables import *
from ..options import *
from ..lineinfos import *
from ..nodekinds import *
from ..ropes import *
from ..int128 import *
from ..cbuilderbase import *

# Test harness of the C builder include files of cgen.nim (cbuilderexprs, cbuilderstmts). Like cgen.nim
# it provides their context (cgen_context: stand-ins for modules not converted yet; the imports:
# converted), then includes them in cgen's order.

include("cgen_context")

# --- cgen.nim: include cbuilderexprs, cbuilderdecls, cbuilderstmts ---
include("../cbuilderexprs")
include("../cbuilderdecls")
include("../cbuilderstmts")


if comptime(__name__ == "__main__"):
    echo(string("Testing cbuilderexprs..."))

    # 1. Type helpers
    doAssert(_constType(string("int")) == string("NIM_CONST int"), string("constType"))
    doAssert(_constPtrType(string("int")) == string("int* NIM_CONST"), string("constPtrType"))
    doAssert(_ptrConstType(string("int")) == string("NIM_CONST int*"), string("ptrConstType"))
    doAssert(_ptrType(string("int")) == string("int*"), string("ptrType"))
    doAssert(_cppRefType(string("int")) == string("int&"), string("cppRefType"))

    # 2. Calling conventions, proc pointer types
    doAssert(_CallingConvToStr[TCallingConvention.ccNimCall] == string("N_NIMCALL"), string("ccNimCall"))
    doAssert(_CallingConvToStr[TCallingConvention.ccSysCall] == string("N_SYSCALL"), string("ccSysCall"))
    doAssert(_CallingConvToStr[TCallingConvention.ccMember] == string("N_NOCONV"), string("ccMember"))
    doAssert(_procPtrTypeUnnamed(string("void"), string("()")) == string("void(*)()"), string("procPtrTypeUnnamed 2"))
    doAssert(_procPtrTypeUnnamedNimCall(string("void"), string("()")) == string("void(N_RAW_NIMCALL*)()"),
             string("procPtrTypeUnnamedNimCall"))
    doAssert(_procPtrTypeUnnamed(TCallingConvention.ccNimCall, string("void"), string("()")) == string("N_NIMCALL_PTR(void, )()"),
             string("procPtrTypeUnnamed 3"))

    # 3. Cast, parens, addresses, fields
    doAssert(_cCast(string("int"), string("x")) == string("((int) x)"), string("cCast"))
    doAssert(_wrapPar(string("x + y")) == string("(x + y)"), string("wrapPar"))
    doAssert(_removeSinglePar(string("(x + y)")) == string("x + y"), string("removeSinglePar"))
    doAssert(_cAddr(string("x")) == string("(&x)"), string("cAddr"))
    doAssert(_cLabelAddr(string("L1")) == string("&&L1"), string("cLabelAddr"))
    doAssert(_cDeref(string("p")) == string("(*p)"), string("cDeref"))
    doAssert(_subscript(string("arr"), string("0")) == string("arr[0]"), string("subscript"))
    doAssert(_dotField(string("obj"), string("field")) == string("obj.field"), string("dotField"))
    doAssert(_derefField(string("ptr"), string("field")) == string("ptr->field"), string("derefField"))

    # 4. sizeof/alignof/offsetof, if expressions
    doAssert(_cSizeof(string("int")) == string("sizeof(int)"), string("cSizeof"))
    doAssert(_cAlignof(string("int")) == string("NIM_ALIGNOF(int)"), string("cAlignof"))
    doAssert(_cOffsetof(string("Type"), string("field")) == string("offsetof(Type, field)"), string("cOffsetof"))
    doAssert(_cIfExpr(string("cond"), string("a"), string("b")) == string("(cond ? a : b)"), string("cIfExpr"))
    doAssert(_cUnlikely(string("x")) == string("NIM_UNLIKELY(x)"), string("cUnlikely"))

    # 5. Calls (varargs); the callee is not modified
    with let:
        callee = string("foo")
    doAssert(_cCall(callee) == string("foo()"), string("cCall 0"))
    doAssert(_cCall(callee, string("a")) == string("foo(a)"), string("cCall 1"))
    doAssert(_cCall(callee, string("a"), string("b")) == string("foo(a, b)"), string("cCall 2"))
    doAssert(callee == string("foo"), string("cCall keeps the callee"))

    # 6. Builder procs (method call syntax as in cgen)
    with var:
        b = newBuilder(string(""))
    b._addSizeof(string("int"))
    b.add(string(" "))
    b._addAlignof(string("int"))
    b.add(string(" "))
    b._addOffsetof(string("Type"), string("field"))
    b.add(string(" "))
    b._addCall(string("bar"), string("x"), string("y"))
    doAssert(b.extract() == string("sizeof(int) NIM_ALIGNOF(int) offsetof(Type, field) bar(x, y)"),
             string("builder procs"))

    # 7. Operators
    with var:
        bo = newBuilder(string(""))
    bo._addOp(_TypedBinaryOp.Add, string("int"), string("a"), string("b"))
    bo._addOp(_TypedUnaryOp.Neg, string("int"), string("a"))
    bo._addOp(_UntypedBinaryOp.Equal, string("a"), string("b"))
    bo._addOp(_UntypedUnaryOp.Not, string("a"))
    doAssert(bo.extract() == string("(a + b)(-(a))(a == b)(!(a))"), string("addOp"))
    doAssert(_cOp(_TypedBinaryOp.Mul, string("int"), string("a"), string("b")) == string("(a * b)"), string("cOp typed binary"))
    doAssert(_cOp(_TypedUnaryOp.BitNot, string("int"), string("a")) == string("(~(a))"), string("cOp typed unary"))
    doAssert(_cOp(_UntypedBinaryOp.LessEqual, string("a"), string("b")) == string("(a <= b)"), string("cOp untyped binary"))
    doAssert(_cOp(_UntypedUnaryOp.Not, string("a")) == string("(!(a))"), string("cOp untyped unary"))

    # 8. Templates with code blocks (Nim `b.addCast(t): ...`)
    with var:
        bc = newBuilder(string(""))
    with bc._addCast(string("char*")):
        bc.add(string("p"))
    doAssert(bc.extract() == string("((char*) p)"), string("addCast"))

    with var:
        bcall = newBuilder(string(""))
        call = _CallBuilder()
    with bcall._addCall(call, string("func")):
        with bcall._addArgument(call):
            bcall.add(string("1"))
        with bcall._addArgument(call):
            bcall.add(string("2"))
    doAssert(bcall.extract() == string("func(1, 2)"), string("addCall + addArgument"))

    with var:
        bl = newBuilder(string(""))
    with bl._addCppLambda(_CppCaptureKind.ByReference, string("(int x)")):
        bl.addLineEnd(string("return x;"))
    doAssert(bl.extract() == string("[&] (int x) {\n\treturn x;\n}\n"), string("addCppLambda"))

    echo(string("All cbuilderexprs tests passed successfully!"))

    echo(string("Testing cbuilderstmts..."))

    # 1. Assignments (templates over templates; Snippet and integer overloads)
    with var:
        b1 = newBuilder(string(""))
    b1._addAssignment(string("x"), string("42"))
    b1._addFieldAssignment(string("o"), string("f"), string("v"))
    b1._addMutualFieldAssignment(string("dst"), string("src"), string("data"))
    b1._addAssignment(string("n"), nint(100))
    b1._addFieldAssignment(string("o"), string("count"), uint64(7))
    b1._addDerefFieldAssignment(string("p"), string("item"), string("v"))
    b1._addSubscriptAssignment(string("arr"), string("i"), string("e"))
    doAssert(b1.extract() == string("x = 42;\no.f = v;\ndst.data = src.data;\nn = 100;\no.count = 7;\np->item = v;\narr[i] = e;\n"),
             string("assignments"))

    # 2. Call statement (varargs passed on)
    with var:
        bc2 = newBuilder(string(""))
    bc2._addCallStmt(string("doSomething"), string("a"), string("b"))
    doAssert(bc2.extract() == string("doSomething(a, b);\n"), string("addCallStmt"))

    # 3. If statements: single, and with branches (out parameter stmt)
    with var:
        bif = newBuilder(string(""))
    with bif._addSingleIfStmt(string("x > 0")):
        bif._addAssignment(string("y"), string("1"))
    doAssert(bif.extract() == string("if (x > 0) {\n\ty = 1;\n}\n"), string("addSingleIfStmt"))
    with var:
        bif2 = newBuilder(string(""))
        stmt = IfBuilder()
    with bif2._addIfStmt(stmt):
        with bif2._addElifBranch(stmt, string("a < b")):
            bif2._addAssignment(string("m"), string("a"))
        with bif2._addElseBranch(stmt):
            bif2._addAssignment(string("m"), string("b"))
    doAssert(bif2.extract() == string("if (a < b) {\n\tm = a;\n} else {\n\tm = b;\n}\n"), string("addIfStmt"))

    # 4. Loops
    with var:
        bfor = newBuilder(string(""))
    with bfor._addForRangeExclusive(string("i"), string("0"), string("10")):
        bfor._addIncr(string("s"))
    with bfor._addWhileStmt(string("c")):
        bfor._addDecr(string("t"))
    doAssert(bfor.extract() == string("for (i = 0; i < 10; i++) {\n\ts++;\n}\nwhile (c) {\n\tt--;\n}\n"),
             string("loops"))

    # 5. Switch with the two-block template addSwitchCase (`: ... do: ...`)
    with var:
        bsw = newBuilder(string(""))
        caseBuilder = _SwitchCaseBuilder()
    with bsw._addSwitchStmt(string("v")):
        with bsw._addSwitchCase(caseBuilder):
            bsw._addCase(caseBuilder, string("1"))
            with do:
                doAssert(caseBuilder._state == _SwitchCaseState.Finished, string("state between the blocks"))
                bsw._addBreak()
        with bsw._addSwitchElse():
            bsw._addReturn(string("0"))
    doAssert(bsw.extract() == string("switch (v) {\ncase 1:\n\tbreak;\n\ndefault:\n\treturn 0;\n\n}\n"),
             string("switch"))

    # 6. Scope, labels, gotos, in-place operators, pragmas
    with var:
        bm = newBuilder(string(""))
    with bm._addScope():
        bm._addLabel(string("L"))
        bm._addGoto(string("L"))
    bm._addInPlaceOp(_TypedBinaryOp.Add, string("int"), string("x"), string("1"))
    bm._addInPlaceOp(_UntypedBinaryOp.And, string("f"), string("m"))
    bm._addCPragma(string("once"))
    bm._addDiscard(string("g()"))
    doAssert(bm.extract() == string("{\n\tL: ;\n\tgoto L;\n}\nx += 1;\nf &&= m;\n\n#pragma once\n(void)g();\n"),
             string("misc statements"))
    doAssert(_cInPlaceOp(_TypedBinaryOp.Mul, string("int"), string("a"), string("b")) == string("a *= b;\n"), string("cInPlaceOp"))

    echo(string("All cbuilderstmts tests passed successfully!"))
