# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.intsets import *
from ..options import *
from ..lineinfos import *
from ..nodekinds import *
from ..ropes import *

# Test harness of the C builder include files of cgen.nim (cbuilderexprs, cbuilderstmts). Like cgen.nim
# it provides their context (cgen_context: stand-ins for modules not converted yet; the imports:
# converted), then includes them in cgen's order.

include("cgen_context")

# --- cgen.nim: include cbuilderexprs, cbuilderdecls, cbuilderstmts ---
include("../cbuilderexprs")
include("cbuilderdecls_subset")
include("../cbuilderstmts")


if comptime(__name__ == "__main__"):
    echo(string("Testing cbuilderexprs..."))

    # 1. Type helpers
    doAssert(constType(string("int")) == string("NIM_CONST int"), string("constType"))
    doAssert(constPtrType(string("int")) == string("int* NIM_CONST"), string("constPtrType"))
    doAssert(ptrConstType(string("int")) == string("NIM_CONST int*"), string("ptrConstType"))
    doAssert(ptrType(string("int")) == string("int*"), string("ptrType"))
    doAssert(cppRefType(string("int")) == string("int&"), string("cppRefType"))

    # 2. Calling conventions, proc pointer types
    doAssert(CallingConvToStr[TCallingConvention.ccNimCall] == string("N_NIMCALL"), string("ccNimCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccSysCall] == string("N_SYSCALL"), string("ccSysCall"))
    doAssert(CallingConvToStr[TCallingConvention.ccMember] == string("N_NOCONV"), string("ccMember"))
    doAssert(procPtrTypeUnnamed(string("void"), string("()")) == string("void(*)()"), string("procPtrTypeUnnamed 2"))
    doAssert(procPtrTypeUnnamedNimCall(string("void"), string("()")) == string("void(N_RAW_NIMCALL*)()"),
             string("procPtrTypeUnnamedNimCall"))
    doAssert(procPtrTypeUnnamed(TCallingConvention.ccNimCall, string("void"), string("()")) == string("N_NIMCALL_PTR(void, )()"),
             string("procPtrTypeUnnamed 3"))

    # 3. Cast, parens, addresses, fields
    doAssert(cCast(string("int"), string("x")) == string("((int) x)"), string("cCast"))
    doAssert(wrapPar(string("x + y")) == string("(x + y)"), string("wrapPar"))
    doAssert(removeSinglePar(string("(x + y)")) == string("x + y"), string("removeSinglePar"))
    doAssert(cAddr(string("x")) == string("(&x)"), string("cAddr"))
    doAssert(cLabelAddr(string("L1")) == string("&&L1"), string("cLabelAddr"))
    doAssert(cDeref(string("p")) == string("(*p)"), string("cDeref"))
    doAssert(subscript(string("arr"), string("0")) == string("arr[0]"), string("subscript"))
    doAssert(dotField(string("obj"), string("field")) == string("obj.field"), string("dotField"))
    doAssert(derefField(string("ptr"), string("field")) == string("ptr->field"), string("derefField"))

    # 4. sizeof/alignof/offsetof, if expressions
    doAssert(cSizeof(string("int")) == string("sizeof(int)"), string("cSizeof"))
    doAssert(cAlignof(string("int")) == string("NIM_ALIGNOF(int)"), string("cAlignof"))
    doAssert(cOffsetof(string("Type"), string("field")) == string("offsetof(Type, field)"), string("cOffsetof"))
    doAssert(cIfExpr(string("cond"), string("a"), string("b")) == string("(cond ? a : b)"), string("cIfExpr"))
    doAssert(cUnlikely(string("x")) == string("NIM_UNLIKELY(x)"), string("cUnlikely"))

    # 5. Calls (varargs); the callee is not modified
    with let:
        callee = string("foo")
    doAssert(cCall(callee) == string("foo()"), string("cCall 0"))
    doAssert(cCall(callee, string("a")) == string("foo(a)"), string("cCall 1"))
    doAssert(cCall(callee, string("a"), string("b")) == string("foo(a, b)"), string("cCall 2"))
    doAssert(callee == string("foo"), string("cCall keeps the callee"))

    # 6. Builder procs (method call syntax as in cgen)
    with var:
        b = newBuilder(string(""))
    b.addSizeof(string("int"))
    b.add(string(" "))
    b.addAlignof(string("int"))
    b.add(string(" "))
    b.addOffsetof(string("Type"), string("field"))
    b.add(string(" "))
    b.addCall(string("bar"), string("x"), string("y"))
    doAssert(extract(b) == string("sizeof(int) NIM_ALIGNOF(int) offsetof(Type, field) bar(x, y)"),
             string("builder procs"))

    # 7. Operators
    with var:
        bo = newBuilder(string(""))
    bo.addOp(TypedBinaryOp.Add, string("int"), string("a"), string("b"))
    bo.addOp(TypedUnaryOp.Neg, string("int"), string("a"))
    bo.addOp(UntypedBinaryOp.Equal, string("a"), string("b"))
    bo.addOp(UntypedUnaryOp.Not, string("a"))
    doAssert(extract(bo) == string("(a + b)(-(a))(a == b)(!(a))"), string("addOp"))
    doAssert(cOp(TypedBinaryOp.Mul, string("int"), string("a"), string("b")) == string("(a * b)"), string("cOp typed binary"))
    doAssert(cOp(TypedUnaryOp.BitNot, string("int"), string("a")) == string("(~(a))"), string("cOp typed unary"))
    doAssert(cOp(UntypedBinaryOp.LessEqual, string("a"), string("b")) == string("(a <= b)"), string("cOp untyped binary"))
    doAssert(cOp(UntypedUnaryOp.Not, string("a")) == string("(!(a))"), string("cOp untyped unary"))

    # 8. Templates with code blocks (Nim `b.addCast(t): ...`)
    with var:
        bc = newBuilder(string(""))
    with bc.addCast(string("char*")):
        bc.add(string("p"))
    doAssert(extract(bc) == string("((char*) p)"), string("addCast"))

    with var:
        bcall = newBuilder(string(""))
        call = CallBuilder()
    with bcall.addCall(call, string("func")):
        with bcall.addArgument(call):
            bcall.add(string("1"))
        with bcall.addArgument(call):
            bcall.add(string("2"))
    doAssert(extract(bcall) == string("func(1, 2)"), string("addCall + addArgument"))

    with var:
        bl = newBuilder(string(""))
    with bl.addCppLambda(CppCaptureKind.ByReference, string("(int x)")):
        bl.addLineEnd(string("return x;"))
    doAssert(extract(bl) == string("[&] (int x) {\n\treturn x;\n}\n"), string("addCppLambda"))

    echo(string("All cbuilderexprs tests passed successfully!"))

    echo(string("Testing cbuilderstmts..."))

    # 1. Assignments (templates over templates; Snippet and integer overloads)
    with var:
        b1 = newBuilder(string(""))
    b1.addAssignment(string("x"), string("42"))
    b1.addFieldAssignment(string("o"), string("f"), string("v"))
    b1.addMutualFieldAssignment(string("dst"), string("src"), string("data"))
    b1.addAssignment(string("n"), nint(100))
    b1.addFieldAssignment(string("o"), string("count"), uint64(7))
    b1.addDerefFieldAssignment(string("p"), string("item"), string("v"))
    b1.addSubscriptAssignment(string("arr"), string("i"), string("e"))
    doAssert(extract(b1) == string("x = 42;\no.f = v;\ndst.data = src.data;\nn = 100;\no.count = 7;\np->item = v;\narr[i] = e;\n"),
             string("assignments"))

    # 2. Call statement (varargs passed on)
    with var:
        bc2 = newBuilder(string(""))
    bc2.addCallStmt(string("doSomething"), string("a"), string("b"))
    doAssert(extract(bc2) == string("doSomething(a, b);\n"), string("addCallStmt"))

    # 3. If statements: single, and with branches (out parameter stmt)
    with var:
        bif = newBuilder(string(""))
    with bif.addSingleIfStmt(string("x > 0")):
        bif.addAssignment(string("y"), string("1"))
    doAssert(extract(bif) == string("if (x > 0) {\n\ty = 1;\n}\n"), string("addSingleIfStmt"))
    with var:
        bif2 = newBuilder(string(""))
        stmt = IfBuilder()
    with bif2.addIfStmt(stmt):
        with bif2.addElifBranch(stmt, string("a < b")):
            bif2.addAssignment(string("m"), string("a"))
        with bif2.addElseBranch(stmt):
            bif2.addAssignment(string("m"), string("b"))
    doAssert(extract(bif2) == string("if (a < b) {\n\tm = a;\n} else {\n\tm = b;\n}\n"), string("addIfStmt"))

    # 4. Loops
    with var:
        bfor = newBuilder(string(""))
    with bfor.addForRangeExclusive(string("i"), string("0"), string("10")):
        bfor.addIncr(string("s"))
    with bfor.addWhileStmt(string("c")):
        bfor.addDecr(string("t"))
    doAssert(extract(bfor) == string("for (i = 0; i < 10; i++) {\n\ts++;\n}\nwhile (c) {\n\tt--;\n}\n"),
             string("loops"))

    # 5. Switch with the two-block template addSwitchCase (`: ... do: ...`)
    with var:
        bsw = newBuilder(string(""))
        caseBuilder = SwitchCaseBuilder()
    with bsw.addSwitchStmt(string("v")):
        with bsw.addSwitchCase(caseBuilder):
            bsw.addCase(caseBuilder, string("1"))
            with do:
                doAssert(caseBuilder.state == SwitchCaseState.Finished, string("state between the blocks"))
                bsw.addBreak()
        with bsw.addSwitchElse():
            bsw.addReturn(string("0"))
    doAssert(extract(bsw) == string("switch (v) {\ncase 1:\n\tbreak;\n\ndefault:\n\treturn 0;\n\n}\n"),
             string("switch"))

    # 6. Scope, labels, gotos, in-place operators, pragmas
    with var:
        bm = newBuilder(string(""))
    with bm.addScope():
        bm.addLabel(string("L"))
        bm.addGoto(string("L"))
    bm.addInPlaceOp(TypedBinaryOp.Add, string("int"), string("x"), string("1"))
    bm.addInPlaceOp(UntypedBinaryOp.And, string("f"), string("m"))
    bm.addCPragma(string("once"))
    bm.addDiscard(string("g()"))
    doAssert(extract(bm) == string("{\n\tL: ;\n\tgoto L;\n}\nx += 1;\nf &&= m;\n\n#pragma once\n(void)g();\n"),
             string("misc statements"))
    doAssert(cInPlaceOp(TypedBinaryOp.Mul, string("int"), string("a"), string("b")) == string("a *= b;\n"), string("cInPlaceOp"))

    echo(string("All cbuilderstmts tests passed successfully!"))
