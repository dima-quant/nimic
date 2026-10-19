# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# included from cgen.nim (include file: Builder, Snippet, IfBuilder, Int128, TLabel come from the includer,
# TypedBinaryOp & co. from cbuilderexprs; tests: ncompiler/tests/test_cbuilders.py)


@template
def _addAssignmentWithValue(builder: mut@Builder, lhs: Snippet, valueBody: typed):
    builder.add(lhs)
    builder.add(string(" = "))
    valueBody
    builder.addLineEnd(string(";"))


@template
def _addFieldAssignmentWithValue(builder: mut@Builder, lhs: Snippet, name: string, valueBody: typed):
    builder.add(lhs)
    builder.add(string(".") + name + string(" = "))
    valueBody
    builder.addLineEnd(string(";"))


@template
def _addAssignment(builder: mut@Builder, lhs: Snippet, rhs: Snippet):
    with builder._addAssignmentWithValue(lhs):
        builder.add(rhs)


@template
def _addFieldAssignment(builder: mut@Builder, lhs: Snippet, name: string, rhs: Snippet):
    with builder._addFieldAssignmentWithValue(lhs, name):
        builder.add(rhs)


@template
def _addMutualFieldAssignment(builder: mut@Builder, lhs: Snippet, rhs: Snippet, name: string):
    with builder._addFieldAssignmentWithValue(lhs, name):
        builder.add(rhs)
        builder.add(string(".") + name)


@template
def _addAssignment(builder: mut@Builder, lhs: Snippet, rhs: nint | int64 | uint64 | Int128):
    with builder._addAssignmentWithValue(lhs):
        builder.addIntValue(rhs)


@template
def _addFieldAssignment(builder: mut@Builder, lhs: Snippet, name: string, rhs: nint | int64 | uint64 | Int128):
    with builder._addFieldAssignmentWithValue(lhs, name):
        builder.addIntValue(rhs)


@template
def _addDerefFieldAssignment(builder: mut@Builder, lhs: Snippet, name: string, rhs: Snippet):
    builder.add(lhs)
    builder.add(string("->") + name + string(" = "))
    builder.add(rhs)
    builder.addLineEnd(string(";"))


@template
def _addSubscriptAssignment(builder: mut@Builder, lhs: Snippet, index: Snippet, rhs: Snippet):
    builder.add(lhs)
    builder.add(string("[") + index + string("] = "))
    builder.add(rhs)
    builder.addLineEnd(string(";"))


@template
def _addStmt(builder: mut@Builder, stmtBody: typed):
    """makes an expression built by `stmtBody` into a statement"""
    stmtBody
    builder.addLineEnd(string(";"))


def _addCallStmt(builder: mut@Builder, callee: Snippet, *args: Snippet) -> None:
    with builder._addStmt():
        builder._addCall(callee, *args)


# XXX blocks need indent tracker in `Builder` object

@template
def _addSingleIfStmt(builder: mut@Builder, cond: Snippet, body: typed):
    builder.add(string("if ("))
    builder.add(cond)
    builder.addLineEndIndent(string(") {"))
    body
    builder.addLineEndDedent(string("}"))


@template
def _addSingleIfStmtWithCond(builder: mut@Builder, condBody: typed, body: typed):
    builder.add(string("if ("))
    condBody
    builder.addLineEndIndent(string(") {"))
    body
    builder.addLineEndDedent(string("}"))


def _initIfStmt(builder: mut@Builder) -> IfBuilder:
    return IfBuilder(state=IfBuilderState.WaitingIf)


def _finishIfStmt(builder: mut@Builder, stmt: IfBuilder) -> None:
    doAssert(stmt.state != IfBuilderState.InBlock)
    builder.addNewline()


@template
def _addIfStmt(builder: mut@Builder, stmt: out@IfBuilder, body: typed):
    stmt <<= _initIfStmt(builder)
    body
    _finishIfStmt(builder, stmt)


def _initElifBranch(builder: mut@Builder, stmt: mut@IfBuilder, cond: Snippet) -> None:
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


def _initElseBranch(builder: mut@Builder, stmt: mut@IfBuilder) -> None:
    doAssert(stmt.state == IfBuilderState.WaitingElseIf, str(stmt.state))
    builder.addLineEndIndent(string(" else {"))
    stmt.state = IfBuilderState.InBlock


def _finishBranch(builder: mut@Builder, stmt: mut@IfBuilder) -> None:
    builder.addDedent(string("}"))
    stmt.state = IfBuilderState.WaitingElseIf


@template
def _addElifBranch(builder: mut@Builder, stmt: mut@IfBuilder, cond: Snippet, body: typed):
    _initElifBranch(builder, stmt, cond)
    body
    _finishBranch(builder, stmt)


@template
def _addElseBranch(builder: mut@Builder, stmt: mut@IfBuilder, body: typed):
    _initElseBranch(builder, stmt)
    body
    _finishBranch(builder, stmt)


def _initForRange(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, inclusive: bool = False) -> None:
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


def _initForStep(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, step: Snippet, inclusive: bool = False) -> None:
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


def _finishFor(builder: mut@Builder) -> None:
    """{.inline.}"""
    builder.addLineEndDedent(string("}"))


@template
def _addForRangeExclusive(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, body: typed):
    _initForRange(builder, i, start, bound, False)
    body
    _finishFor(builder)


@template
def _addForRangeInclusive(builder: mut@Builder, i: Snippet, start: Snippet, bound: Snippet, body: typed):
    _initForRange(builder, i, start, bound, True)
    body
    _finishFor(builder)


@template
def _addSwitchStmt(builder: mut@Builder, val: Snippet, body: typed):
    builder.add(string("switch ("))
    builder.add(val)
    builder.addLineEnd(string(") {")) # no indent
    body
    builder.addLineEnd(string("}"))


@template
def _addSingleSwitchCase(builder: mut@Builder, val: Snippet, body: typed):
    builder.add(string("case "))
    builder.add(val)
    builder.addLineEndIndent(string(":"))
    body
    builder.addLineEndDedent(string(""))


class _SwitchCaseState(NIntEnum):
    None_ = 0
    Of = auto()
    Else = auto()
    Finished = auto()


class _SwitchCaseBuilder(Object):
    _state: _SwitchCaseState


def _addCase(builder: mut@Builder, info: mut@_SwitchCaseBuilder, val: Snippet) -> None:
    if info._state != _SwitchCaseState.Of:
        doAssert(info._state == _SwitchCaseState.None_)
        info._state = _SwitchCaseState.Of
    builder.add(string("case "))
    builder.add(val)
    builder.addLineEndIndent(string(":"))


def _addCaseRange(builder: mut@Builder, info: mut@_SwitchCaseBuilder, first: Snippet, last: Snippet) -> None:
    if info._state != _SwitchCaseState.Of:
        doAssert(info._state == _SwitchCaseState.None_)
        info._state = _SwitchCaseState.Of
    builder.add(string("case "))
    builder.add(first)
    builder.add(string(" ... "))
    builder.add(last)
    builder.addLineEndIndent(string(":"))


def _addCaseElse(builder: mut@Builder, info: mut@_SwitchCaseBuilder) -> None:
    doAssert(info._state == _SwitchCaseState.None_)
    info._state = _SwitchCaseState.Else
    builder.addLineEndIndent(string("default:"))


@template
def _addSwitchCase(builder: mut@Builder, info: out@_SwitchCaseBuilder, caseBody: typed, body: typed):
    info <<= _SwitchCaseBuilder(_state=_SwitchCaseState.None_)
    caseBody
    info._state = _SwitchCaseState.Finished
    body
    builder.addLineEndDedent(string(""))


@template
def _addSwitchElse(builder: mut@Builder, body: typed):
    builder.addLineEndIndent(string("default:"))
    body
    builder.addLineEndDedent(string(""))


def _addBreak(builder: mut@Builder) -> None:
    builder.addLineEnd(string("break;"))


class _ScopeBuilder(Object):
    _inside: bool


def _initScope(builder: mut@Builder) -> _ScopeBuilder:
    builder.addLineEndIndent(string("{"))
    result = _ScopeBuilder(_inside=True)
    return result


def _finishScope(builder: mut@Builder, scope: mut@_ScopeBuilder) -> None:
    doAssert(scope._inside, string("scope not inited"))
    builder.addLineEndDedent(string("}"))
    scope._inside = False


@template
def _addScope(builder: mut@Builder, body: typed):
    builder.addLineEndIndent(string("{"))
    body
    builder.addLineEndDedent(string("}"))


class _WhileBuilder(Object):
    _inside: bool


def _initWhileStmt(builder: mut@Builder, cond: Snippet) -> _WhileBuilder:
    builder.add(string("while ("))
    builder.add(cond)
    builder.addLineEndIndent(string(") {"))
    result = _WhileBuilder(_inside=True)
    return result


def _finishWhileStmt(builder: mut@Builder, stmt: mut@_WhileBuilder) -> None:
    doAssert(stmt._inside, string("while stmt not inited"))
    builder.addLineEndDedent(string("}"))
    stmt._inside = False


@template
def _addWhileStmt(builder: mut@Builder, cond: Snippet, body: typed):
    builder.add(string("while ("))
    builder.add(cond)
    builder.addLineEndIndent(string(") {"))
    body
    builder.addLineEndDedent(string("}"))


def _addLabel(builder: mut@Builder, name: TLabel) -> None:
    builder.add(name)
    builder.addLineEnd(string(": ;"))


@dispatch
def _addReturn(builder: mut@Builder) -> None:
    builder.addLineEnd(string("return;"))


@dispatch
def _addReturn(builder: mut@Builder, value: Snippet) -> None:
    builder.add(string("return "))
    builder.add(value)
    builder.addLineEnd(string(";"))


def _addGoto(builder: mut@Builder, label: TLabel) -> None:
    builder.add(string("goto "))
    builder.add(label)
    builder.addLineEnd(string(";"))


def _addComputedGoto(builder: mut@Builder, value: Snippet) -> None:
    builder.add(string("goto *"))
    builder.add(value)
    builder.addLineEnd(string(";"))


def _addIncr(builder: mut@Builder, val: Snippet) -> None:
    builder.add(val)
    builder.addLineEnd(string("++;"))


def _addDecr(builder: mut@Builder, val: Snippet) -> None:
    builder.add(val)
    builder.addLineEnd(string("--;"))


@dispatch
def _addInPlaceOp(builder: mut@Builder, binOp: _TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> None:
    builder.add(a)
    builder.add(ch(" "))
    builder.add(_typedBinaryOperators[binOp])
    builder.add(string("= "))
    builder.add(b)
    builder.addLineEnd(string(";"))


@dispatch
def _addInPlaceOp(builder: mut@Builder, binOp: _UntypedBinaryOp, a: Snippet, b: Snippet) -> None:
    builder.add(a)
    builder.add(ch(" "))
    builder.add(_untypedBinaryOperators[binOp])
    builder.add(string("= "))
    builder.add(b)
    builder.addLineEnd(string(";"))


@dispatch
def _cInPlaceOp(binOp: _TypedBinaryOp, t: Snippet, a: Snippet, b: Snippet) -> Snippet:
    result = string("")
    result.add(a)
    result.add(ch(" "))
    result.add(_typedBinaryOperators[binOp])
    result.add(string("= "))
    result.add(b)
    result.add(string(";\n"))
    return result


@dispatch
def _cInPlaceOp(binOp: _UntypedBinaryOp, a: Snippet, b: Snippet) -> Snippet:
    result = string("")
    result.add(a)
    result.add(ch(" "))
    result.add(_untypedBinaryOperators[binOp])
    result.add(string("= "))
    result.add(b)
    result.add(string(";\n"))
    return result


@template
def _addCPragma(builder: mut@Builder, val: Snippet):
    builder.addNewline()
    builder.add(string("#pragma "))
    builder.add(val)
    builder.addNewline()


def _addDiscard(builder: mut@Builder, val: Snippet) -> None:
    builder.add(string("(void)"))
    builder.add(val)
    builder.addLineEnd(string(";"))
