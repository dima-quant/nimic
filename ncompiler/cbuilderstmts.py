# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# included from cgen.nim (include file: Builder, Snippet, IfBuilder, Int128, TLabel come from the includer,
# TypedBinaryOp & co. from cbuilderexprs; tests: ncompiler/tests/test_cbuilders.py)


@template
def addAssignmentWithValue(builder: mut@Builder, lhs: Snippet, valueBody: typed):
    builder.add(lhs)
    builder.add(string(" = "))
    valueBody
    builder.addLineEnd(string(";"))


@template
def addFieldAssignmentWithValue(builder: mut@Builder, lhs: Snippet, name: string, valueBody: typed):
    builder.add(lhs)
    builder.add(string(".") + name + string(" = "))
    valueBody
    builder.addLineEnd(string(";"))


@template
def addAssignment(builder: mut@Builder, lhs: Snippet, rhs: Snippet):
    with builder.addAssignmentWithValue(lhs):
        builder.add(rhs)


@template
def addFieldAssignment(builder: mut@Builder, lhs: Snippet, name: string, rhs: Snippet):
    with builder.addFieldAssignmentWithValue(lhs, name):
        builder.add(rhs)


@template
def addMutualFieldAssignment(builder: mut@Builder, lhs: Snippet, rhs: Snippet, name: string):
    with builder.addFieldAssignmentWithValue(lhs, name):
        builder.add(rhs)
        builder.add(string(".") + name)


@template
def addAssignment(builder: mut@Builder, lhs: Snippet, rhs: nint | int64 | uint64 | Int128):
    with builder.addAssignmentWithValue(lhs):
        builder.addIntValue(rhs)


@template
def addFieldAssignment(builder: mut@Builder, lhs: Snippet, name: string, rhs: nint | int64 | uint64 | Int128):
    with builder.addFieldAssignmentWithValue(lhs, name):
        builder.addIntValue(rhs)


@template
def addDerefFieldAssignment(builder: mut@Builder, lhs: Snippet, name: string, rhs: Snippet):
    builder.add(lhs)
    builder.add(string("->") + name + string(" = "))
    builder.add(rhs)
    builder.addLineEnd(string(";"))


@template
def addSubscriptAssignment(builder: mut@Builder, lhs: Snippet, index: Snippet, rhs: Snippet):
    builder.add(lhs)
    builder.add(string("[") + index + string("] = "))
    builder.add(rhs)
    builder.addLineEnd(string(";"))


@template
def addStmt(builder: mut@Builder, stmtBody: typed):
    """makes an expression built by `stmtBody` into a statement"""
    stmtBody
    builder.addLineEnd(string(";"))


def addCallStmt(builder: mut@Builder, callee: Snippet, *args: Snippet) -> None:
    with builder.addStmt():
        builder.addCall(callee, *args)


# XXX blocks need indent tracker in `Builder` object

@template
def addSingleIfStmt(builder: mut@Builder, cond: Snippet, body: typed):
    builder.add(string("if ("))
    builder.add(cond)
    builder.addLineEndIndent(string(") {"))
    body
    builder.addLineEndDedent(string("}"))


@template
def addSingleIfStmtWithCond(builder: mut@Builder, condBody: typed, body: typed):
    builder.add(string("if ("))
    condBody
    builder.addLineEndIndent(string(") {"))
    body
    builder.addLineEndDedent(string("}"))


def initIfStmt(builder: mut@Builder) -> IfBuilder:
    return IfBuilder(state=IfBuilderState.WaitingIf)


def finishIfStmt(builder: mut@Builder, stmt: IfBuilder) -> None:
    doAssert(stmt.state != IfBuilderState.InBlock)
    builder.addNewline()


@template
def addIfStmt(builder: mut@Builder, stmt: out@IfBuilder, body: typed):
    stmt <<= initIfStmt(builder)
    body
    finishIfStmt(builder, stmt)


def initElifBranch(builder: mut@Builder, stmt: mut@IfBuilder, cond: Snippet) -> None:
    match stmt.state:
        case IfBuilderState.WaitingIf:
            builder.add(string("if ("))
        case IfBuilderState.WaitingElseIf:
            builder.add(string(" else if ("))
        case _:
            doAssert(False, str(stmt.state))
    builder.add(cond)
    builder.addLineEndIndent(string(") {"))
    stmt.state = IfBuilderState.InBlock


def initElseBranch(builder: mut@Builder, stmt: mut@IfBuilder) -> None:
    doAssert(stmt.state == IfBuilderState.WaitingElseIf, str(stmt.state))
    builder.addLineEndIndent(string(" else {"))
    stmt.state = IfBuilderState.InBlock


def finishBranch(builder: mut@Builder, stmt: mut@IfBuilder) -> None:
    builder.addDedent(string("}"))
    stmt.state = IfBuilderState.WaitingElseIf


@template
def addElifBranch(builder: mut@Builder, stmt: mut@IfBuilder, cond: Snippet, body: typed):
    initElifBranch(builder, stmt, cond)
    body
    finishBranch(builder, stmt)


@template
def addElseBranch(builder: mut@Builder, stmt: mut@IfBuilder, body: typed):
    initElseBranch(builder, stmt)
    body
    finishBranch(builder, stmt)


def initForRange(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, inclusive: bool = False) -> None:
    builder.add(string("for ("))
    builder.add(i)
    builder.add(string(" = "))
    builder.add(start)
    builder.add(string("; "))
    builder.add(i)
    if inclusive:
        builder.add(string(" <= "))
    else:
        builder.add(string(" < "))
    builder.add(bound)
    builder.add(string("; "))
    builder.add(i)
    builder.addLineEndIndent(string("++) {"))


def initForStep(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, step: Snippet, inclusive: bool = False) -> None:
    builder.add(string("for ("))
    builder.add(i)
    builder.add(string(" = "))
    builder.add(start)
    builder.add(string("; "))
    builder.add(i)
    if inclusive:
        builder.add(string(" <= "))
    else:
        builder.add(string(" < "))
    builder.add(bound)
    builder.add(string("; "))
    builder.add(i)
    builder.add(string(" += "))
    builder.add(step)
    builder.addLineEndIndent(string(") {"))


def finishFor(builder: mut@Builder) -> None:
    """{.inline.}"""
    builder.addLineEndDedent(string("}"))


@template
def addForRangeExclusive(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, body: typed):
    initForRange(builder, i, start, bound, False)
    body
    finishFor(builder)


@template
def addForRangeInclusive(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, body: typed):
    initForRange(builder, i, start, bound, True)
    body
    finishFor(builder)


@template
def addSwitchStmt(builder: mut@Builder, val: Snippet, body: typed):
    builder.add(string("switch ("))
    builder.add(val)
    builder.addLineEnd(string(") {")) # no indent
    body
    builder.addLineEnd(string("}"))


@template
def addSingleSwitchCase(builder: mut@Builder, val: Snippet, body: typed):
    builder.add(string("case "))
    builder.add(val)
    builder.addLineEndIndent(string(":"))
    body
    builder.addLineEndDedent(string(""))


class SwitchCaseState(NIntEnum):
    None_ = 0
    Of = auto()
    Else = auto()
    Finished = auto()


class SwitchCaseBuilder(Object):
    state: SwitchCaseState


def addCase(builder: mut@Builder, info: mut@SwitchCaseBuilder, val: Snippet) -> None:
    if info.state != SwitchCaseState.Of:
        doAssert(info.state == SwitchCaseState.None_)
        info.state = SwitchCaseState.Of
    builder.add(string("case "))
    builder.add(val)
    builder.addLineEndIndent(string(":"))


def addCaseRange(builder: mut@Builder, info: mut@SwitchCaseBuilder, first: Snippet, last: Snippet) -> None:
    if info.state != SwitchCaseState.Of:
        doAssert(info.state == SwitchCaseState.None_)
        info.state = SwitchCaseState.Of
    builder.add(string("case "))
    builder.add(first)
    builder.add(string(" ... "))
    builder.add(last)
    builder.addLineEndIndent(string(":"))


def addCaseElse(builder: mut@Builder, info: mut@SwitchCaseBuilder) -> None:
    doAssert(info.state == SwitchCaseState.None_)
    info.state = SwitchCaseState.Else
    builder.addLineEndIndent(string("default:"))


@template
def addSwitchCase(builder: mut@Builder, info: out@SwitchCaseBuilder, caseBody: typed, body: typed):
    info <<= SwitchCaseBuilder(state=SwitchCaseState.None_)
    caseBody
    info.state = SwitchCaseState.Finished
    body
    builder.addLineEndDedent(string(""))


@template
def addSwitchElse(builder: mut@Builder, body: typed):
    builder.addLineEndIndent(string("default:"))
    body
    builder.addLineEndDedent(string(""))


def addBreak(builder: mut@Builder) -> None:
    builder.addLineEnd(string("break;"))


class ScopeBuilder(Object):
    inside: bool


def initScope(builder: mut@Builder) -> ScopeBuilder:
    builder.addLineEndIndent(string("{"))
    result = ScopeBuilder(inside=True)
    return result


def finishScope(builder: mut@Builder, scope: mut@ScopeBuilder) -> None:
    doAssert(scope.inside, string("scope not inited"))
    builder.addLineEndDedent(string("}"))
    scope.inside = False


@template
def addScope(builder: mut@Builder, body: typed):
    builder.addLineEndIndent(string("{"))
    body
    builder.addLineEndDedent(string("}"))


class WhileBuilder(Object):
    inside: bool


def initWhileStmt(builder: mut@Builder, cond: Snippet) -> WhileBuilder:
    builder.add(string("while ("))
    builder.add(cond)
    builder.addLineEndIndent(string(") {"))
    result = WhileBuilder(inside=True)
    return result


def finishWhileStmt(builder: mut@Builder, stmt: mut@WhileBuilder) -> None:
    doAssert(stmt.inside, string("while stmt not inited"))
    builder.addLineEndDedent(string("}"))
    stmt.inside = False


@template
def addWhileStmt(builder: mut@Builder, cond: Snippet, body: typed):
    builder.add(string("while ("))
    builder.add(cond)
    builder.addLineEndIndent(string(") {"))
    body
    builder.addLineEndDedent(string("}"))


def addLabel(builder: mut@Builder, name: TLabel) -> None:
    builder.add(name)
    builder.addLineEnd(string(": ;"))


@dispatch
def addReturn(builder: mut@Builder) -> None:
    builder.addLineEnd(string("return;"))


@dispatch
def addReturn(builder: mut@Builder, value: Snippet) -> None:
    builder.add(string("return "))
    builder.add(value)
    builder.addLineEnd(string(";"))


def addGoto(builder: mut@Builder, label: TLabel) -> None:
    builder.add(string("goto "))
    builder.add(label)
    builder.addLineEnd(string(";"))


def addComputedGoto(builder: mut@Builder, value: Snippet) -> None:
    builder.add(string("goto *"))
    builder.add(value)
    builder.addLineEnd(string(";"))


def addIncr(builder: mut@Builder, val: Snippet) -> None:
    builder.add(val)
    builder.addLineEnd(string("++;"))


def addDecr(builder: mut@Builder, val: Snippet) -> None:
    builder.add(val)
    builder.addLineEnd(string("--;"))


@dispatch
def addInPlaceOp(builder: mut@Builder, binOp: TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> None:
    builder.add(a)
    builder.add(ch(" "))
    builder.add(typedBinaryOperators[binOp])
    builder.add(string("= "))
    builder.add(b)
    builder.addLineEnd(string(";"))


@dispatch
def addInPlaceOp(builder: mut@Builder, binOp: UntypedBinaryOp, a: Snippet, b: Snippet) -> None:
    builder.add(a)
    builder.add(ch(" "))
    builder.add(untypedBinaryOperators[binOp])
    builder.add(string("= "))
    builder.add(b)
    builder.addLineEnd(string(";"))


@dispatch
def cInPlaceOp(binOp: TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> Snippet:
    result = string("")
    result.add(a)
    result.add(ch(" "))
    result.add(typedBinaryOperators[binOp])
    result.add(string("= "))
    result.add(b)
    result.add(string(";\n"))
    return result


@dispatch
def cInPlaceOp(binOp: UntypedBinaryOp, a: Snippet, b: Snippet) -> Snippet:
    result = string("")
    result.add(a)
    result.add(ch(" "))
    result.add(untypedBinaryOperators[binOp])
    result.add(string("= "))
    result.add(b)
    result.add(string(";\n"))
    return result


@template
def addCPragma(builder: mut@Builder, val: Snippet):
    builder.addNewline()
    builder.add(string("#pragma "))
    builder.add(val)
    builder.addNewline()


def addDiscard(builder: mut@Builder, val: Snippet) -> None:
    builder.add(string("(void)"))
    builder.add(val)
    builder.addLineEnd(string(";"))
