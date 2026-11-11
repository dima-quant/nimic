# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/genstmts.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

# included from codegen.nim

from __future__ import annotations
from nimic.ntypes import *


def _genEmitStmt(c: mut @ GeneratedCode, n: mut @ Cursor):
    for _ in loopInto(n):
        if kind(n) == NifKind.StrLit:
            with let:
                code = c._m.pool.strings[_litId(n)].copy()
            c.add(code)
            n.inc()
        else:
            _genx(c, n)
    c.add(_PredefinedToken.NewLine)


def _genIf(c: mut @ GeneratedCode, n: mut @ Cursor):
    with let:
        oldInToplevel = c._inToplevel
    c._inToplevel = False
    with var:
        hasElse = False
        hasElif = False
    with let:
        first = _firstSon(n)
    for _ in loopInto(n):
        match substructureKind(n):
            case LengOther.ElifU:
                if hasElse:
                    _error(c._m, string("no `elif` allowed after `else` but got: "), n)
                else:
                    if hasElif:
                        c.add(_PredefinedToken.ElseKeyword)
                    c.add(_PredefinedToken.IfKeyword)
                    with into(n):
                        _genCond(c, n)
                        c.add(_PredefinedToken.CurlyLe)
                        _genStmt(c, n)
                        c.add(_PredefinedToken.CurlyRi)
                        while n.hasMore(): skip(n)
                hasElif = True
            case LengOther.ElseU:
                hasElse = True
                if not hasElif:
                    _error(c._m, string("no `elif` before `else` but got: "), n)
                else:
                    c.add(_PredefinedToken.ElseKeyword)
                    c.add(_PredefinedToken.CurlyLe)
                    with into(n):
                        _genStmt(c, n)
                        while n.hasMore(): skip(n)
                    c.add(_PredefinedToken.CurlyRi)
            case _:
                _error(c._m, string("`if` expects `elif` or `else` but got: "), n)
                skip(n)  # avoid infinite loop on unexpected input
    if not hasElif and not hasElse:
        _error(c._m, string("`if` expects `elif` or `else` but got: "), first)
    c._inToplevel = oldInToplevel


def _getVirtualGuard(c: mut @ GeneratedCode, n: Cursor) -> tuple[SymId, bool]:
    result = (SymId(0), False)
    with var:
        n = n.copy()
    # Leng requirement: The last usage of a virtual flag
    # must be annotated with (lab).
    if exprKind(n) == LengExpr.NotC:
        n.inc()
        with var:
            isLast = False
        if stmtKind(n) == LengStmt.LabS:
            isLast = True
            n.inc()
        elif kind(n) == NifKind.Symbol:
            if c._currentProc._vflags.contains(symId(n)):
                result = (symId(n), isLast)
    return result


def _genIte(c: mut @ GeneratedCode, n: mut @ Cursor):
    with let:
        oldInToplevel = c._inToplevel
    c._inToplevel = False
    with into(n):
        with let:
            (vflag, isLast) = _getVirtualGuard(c, n)
        if vflag != SymId(0):
            #   vflag x = false
            #   ...
            #   jtrue x
            #   ...
            #   if not x:
            #     actions
            #
            #   -->
            #     actions
            skip(n)
            _genStmt(c, n)  # then-part is always taken
            # emit the label:
            if isLast:
                c.add(mangleToC(c._m.pool.symString(vflag)))
                c.add(_PredefinedToken.Colon)
                c.add(_PredefinedToken.Semicolon)
            skip(n)  # else-part is always ignored
        else:
            c.add(_PredefinedToken.IfKeyword)
            c.add(_PredefinedToken.Space)
            _genCond(c, n)
            c.add(_PredefinedToken.Space)
            c.add(_PredefinedToken.CurlyLe)
            _genStmt(c, n)
            c.add(_PredefinedToken.CurlyRi)
            if kind(n) != NifKind.DotToken:
                c.add(_PredefinedToken.ElseKeyword)
                c.add(_PredefinedToken.CurlyLe)
                _genStmt(c, n)
                c.add(_PredefinedToken.CurlyRi)
            else:
                n.inc()
        while n.hasMore(): skip(n)
    c._inToplevel = oldInToplevel
    c.add(_PredefinedToken.Semicolon)


def _genLoop(c: mut @ GeneratedCode, n: mut @ Cursor):
    ## `(loop body)`: infinite, left only by a `break`/`jmp` inside the body.
    with let:
        oldInToplevel = c._inToplevel
    c._inToplevel = False
    with into(n):
        c.add(_PredefinedToken.WhileKeyword)
        c.add(_PredefinedToken.Space)
        c.add(_PredefinedToken.ParLe)
        c.add(string("NIM_TRUE"))
        c.add(_PredefinedToken.ParRi)
        c.add(_PredefinedToken.Space)
        c.add(_PredefinedToken.CurlyLe)
        _genStmt(c, n)  # loop body
        c.add(_PredefinedToken.CurlyRi)
        while n.hasMore(): skip(n)
    c._inToplevel = oldInToplevel


def _genWhile(c: mut @ GeneratedCode, n: mut @ Cursor):
    with let:
        oldInToplevel = c._inToplevel
    c._inToplevel = False
    with into(n):
        c.add(_PredefinedToken.WhileKeyword)
        _genCond(c, n)
        c.add(_PredefinedToken.CurlyLe)
        _genStmt(c, n)
        c.add(_PredefinedToken.CurlyRi)
        while n.hasMore(): skip(n)
    c._inToplevel = oldInToplevel


def _genTryCpp(c: mut @ GeneratedCode, n: mut @ Cursor):
    # The generated code is equivalent to:
    #  bool needsFinalRethrow = false;
    #  try {
    #      // original code
    #  } catch (...) {
    #      needsFinalRethrow = true;
    #      // catch block code
    #  }
    #
    #  // finally section
    #  if (needsFinalRethrow) { throw; }
    #
    #  Possible cases:
    #  1. No exception in original code:
    #     - needsFinalRethrow stays false
    #     - finally runs normally
    #     - needsFinalRethrow check fails, no rethrow
    #
    #  2. Exception in original code, no exception in finally:
    #     - needsFinalRethrow set to true
    #     - finally runs normally
    #     - needsFinalRethrow succeeds, original exception rethrown
    #
    #  3. No exception in original code, exception in finally:
    #     - needsFinalRethrow stays false
    #     - finally throws directly
    #     - never reaches rethrow check
    #
    #  4. Exception in original code, exception in finally:
    #     - needsFinalRethrow set to true
    #     - finally throws directly
    #     - never reaches rethrow check
    with into(n):

        # Add needsFinalRethrow flag
        with let:
            varName = string("needsFinalRethrow") + str(c._currentProc._nextTemp)
        c._currentProc._nextTemp += 1
        c.add(string("bool ") + varName + string(" = false;"))
        c.add(_PredefinedToken.NewLine)

        # Try block
        c.add(_PredefinedToken.TryKeyword)
        c.add(_PredefinedToken.CurlyLe)
        _genStmt(c, n)
        c.add(_PredefinedToken.CurlyRi)

        # Catch block for original exception
        c.add(_PredefinedToken.CatchKeyword)
        c.add(string("..."))
        c.add(_PredefinedToken.ParRi)
        c.add(_PredefinedToken.Space)
        c.add(_PredefinedToken.CurlyLe)
        with let:
            beforeAsgn = c._code.len
        with var:
            sections = nint(0)
        c.add(varName + string(" = true;"))
        c.add(_PredefinedToken.NewLine)
        if kind(n) != NifKind.DotToken:
            _genStmt(c, n)
            sections += 1
        else:
            n.inc()
        c.add(_PredefinedToken.CurlyRi)

        # Finally section
        if kind(n) != NifKind.DotToken:
            _genStmt(c, n)
            sections += 1
        else:
            n.inc()
        if sections == 0:
            c._code.shrink(beforeAsgn)
            c.add(_PredefinedToken.CurlyRi)

        # Rethrow original exception if needed
        c.add(string("if (") + varName + string(") { throw; }"))
        c.add(_PredefinedToken.NewLine)

        while n.hasMore(): skip(n)


def _genScope(c: mut @ GeneratedCode, n: mut @ Cursor):
    c.add(_PredefinedToken.CurlyLe)
    c._m.openScope()
    for _ in loopInto(n):
        _genStmt(c, n)
    c.add(_PredefinedToken.CurlyRi)
    c._m.closeScope()


def _isBranchValue(n: Cursor) -> bool:
    with var:
        n = n.copy()
    if kind(n) in Tset[NifKind](NifKind.IntLit, NifKind.UIntLit, NifKind.CharLit, NifKind.Symbol) or exprKind(n) in Tset[LengExpr](LengExpr.TrueC, LengExpr.FalseC):
        result = True
    elif exprKind(n) == LengExpr.SufC:
        n.inc()  # peek; n is a local copy
        result = kind(n) in Tset[NifKind](NifKind.IntLit, NifKind.UIntLit, NifKind.CharLit)
    elif exprKind(n) in Tset[LengExpr](LengExpr.ConvC, LengExpr.CastC):
        # `(conv T <lit>)` → `((T)<lit>)` is a constant expression in C and is
        # valid inside a `case` label.
        n.inc()  # peek; n is a local copy
        skip(n)  # type
        result = _isBranchValue(n)
    else:
        result = False
    return result


def _genBranchValue(c: mut @ GeneratedCode, n: mut @ Cursor):
    if _isBranchValue(n):
        _genx(c, n)
    else:
        _error(c._m, string("expected valid `of` value but got: "), n)


def _genCaseCond(c: mut @ GeneratedCode, n: mut @ Cursor):
    # BranchValue ::= Number | CharLiteral | Symbol | (true) | (false)
    # BranchRange ::= BranchValue | (range BranchValue BranchValue)
    # BranchRanges ::= (ranges BranchRange+)
    if substructureKind(n) == LengOther.RangesU:
        for _ in loopInto(n):
            c.add(_PredefinedToken.CaseKeyword)
            if substructureKind(n) == LengOther.RangeU:
                with into(n):
                    _genBranchValue(c, n)
                    c.add(string(" ... "))
                    _genBranchValue(c, n)
                    while n.hasMore(): skip(n)
            else:
                _genBranchValue(c, n)
            c.add(string(":"))
            c.add(_PredefinedToken.NewLine)
    else:
        _error(c._m, string("`ranges` expected but got: "), n)


def _genLabel(c: mut @ GeneratedCode, n: mut @ Cursor):
    with into(n):
        if kind(n) == NifKind.SymbolDef:
            with let:
                name = mangleToC(c._m.pool.symString(symId(n)))
            c.add(name)
            c.add(_PredefinedToken.Colon)
            c.add(_PredefinedToken.Semicolon)
            n.inc()
        else:
            _error(c._m, string("expected SymbolDef but got: "), n)
        while n.hasMore(): skip(n)


def _genGoto(c: mut @ GeneratedCode, n: mut @ Cursor):
    with into(n):
        if kind(n) == NifKind.Symbol:
            with let:
                name = mangleToC(c._m.pool.symString(symId(n)))
            c.add(_PredefinedToken.GotoKeyword)
            c.add(name)
            c.add(_PredefinedToken.Semicolon)
            n.inc()
        else:
            _error(c._m, string("expected Symbol but got: "), n)
        while n.hasMore(): skip(n)


def _genSwitch(c: mut @ GeneratedCode, n: mut @ Cursor):
    # (case Expr (of BranchRanges StmtList)* (else StmtList)?) |
    with let:
        oldInToplevel = c._inToplevel
    c._inToplevel = False
    c.add(_PredefinedToken.SwitchKeyword)
    with let:
        first = _firstSon(n)
    with into(n):
        _genCond(c, n)
        c.add(_PredefinedToken.CurlyLe)

        with var:
            hasElse = False
            hasElif = False
        while n.hasMore():
            match substructureKind(n):
                case LengOther.OfU:
                    if hasElse:
                        _error(c._m, string("no `of` allowed after `else` but got: "), n)
                    else:
                        with into(n):
                            _genCaseCond(c, n)
                            c.add(_PredefinedToken.CurlyLe)
                            _genStmt(c, n)
                            c.add(_PredefinedToken.CurlyRi)
                            c.add(_PredefinedToken.BreakKeyword)
                            c.add(_PredefinedToken.Semicolon)
                            while n.hasMore(): skip(n)
                    hasElif = True
                case LengOther.ElseU:
                    hasElse = True
                    if not hasElif:
                        _error(c._m, string("no `of` before `else` but got: "), n)
                    else:
                        c.add(_PredefinedToken.DefaultKeyword)
                        c.add(_PredefinedToken.NewLine)
                        c.add(_PredefinedToken.CurlyLe)
                        with into(n):
                            _genStmt(c, n)
                            while n.hasMore(): skip(n)
                        c.add(_PredefinedToken.CurlyRi)
                        c.add(_PredefinedToken.BreakKeyword)
                        c.add(_PredefinedToken.Semicolon)
                case _:
                    _error(c._m, string("`case` expects `of` or `else` but got: "), n)
                    skip(n)  # avoid infinite loop on unexpected input
        if not hasElif and not hasElse:
            _error(c._m, string("`case` expects `of` or `else` but got: "), first)
        c.add(_PredefinedToken.CurlyRi)
    c._inToplevel = oldInToplevel


def _genMflagDecl(c: mut @ GeneratedCode, n: mut @ Cursor):
    c._genCLineDir(_info(n))
    with into(n):
        if kind(n) == NifKind.SymbolDef:
            with let:
                s = symId(n)
            c._m.registerLocal(s, createIntegralType(c._m, string("(bool)")))
            c.add(string("NB8"))
            c.add(_PredefinedToken.Space)
            c.add(mangleToC(c._m.pool.symString(s)))
            c.add(_PredefinedToken.Semicolon)
            n.inc()
        else:
            _error(c._m, string("expected SymbolDef but got: "), n)
        while n.hasMore(): skip(n)


def _genVflagDecl(c: mut @ GeneratedCode, n: mut @ Cursor):
    c._genCLineDir(_info(n))
    with into(n):
        if kind(n) == NifKind.SymbolDef:
            with let:
                s = symId(n)
            c._m.registerLocal(s, createIntegralType(c._m, string("(bool)")))
            c._currentProc._vflags.incl(s)
            n.inc()
        else:
            _error(c._m, string("expected SymbolDef but got: "), n)
        while n.hasMore(): skip(n)


def _genJtrue(c: mut @ GeneratedCode, n: mut @ Cursor):
    with into(n):
        while n.hasMore():
            if kind(n) == NifKind.Symbol:
                with let:
                    s = symId(n)
                if not c._currentProc._vflags.contains(s):
                    _error(c._m, string("virtual flag not declared: "), n)
                n.inc()
                if not n.hasMore():
                    # last symbol becomes a target goto:
                    c.add(_PredefinedToken.GotoKeyword)
                    c.add(mangleToC(c._m.pool.symString(s)))
                    c.add(_PredefinedToken.Semicolon)
            else:
                _error(c._m, string("expected Symbol but got: "), n)
                n.inc()  # avoid infinite loop


@template_expand
def _genVar(c: mut @ GeneratedCode, n: mut @ Cursor, vk: _VarKind, toExtern=False, useStatic=False):
    match vk:
        case _VarKind.IsLocal:
            _genVarDecl(c, n, _VarKind.IsLocal, toExtern)
        case _VarKind.IsMflag:
            _genMflagDecl(c, n)
        case _VarKind.IsGlobal:
            with _moveToDataSection():
                _genVarDecl(c, n, _VarKind.IsGlobal, toExtern)
        case _VarKind.IsThreadlocal:
            with _moveToDataSection():
                _genVarDecl(c, n, _VarKind.IsThreadlocal, toExtern)
        case _VarKind.IsConst:
            with _moveToDataSection():
                _genVarDecl(c, n, _VarKind.IsConst, toExtern, useStatic)


def _genKeepOverflow(c: mut @ GeneratedCode, n: mut @ Cursor):
    with into(n):  # (keepovf <op> <dest>)
        with let:
            op = exprKind(n)
        with var:
            gcc = string("")
            prefix = string("__builtin_")
            checkable = True
        match op:
            case LengExpr.AddC:
                gcc.add(string("add"))
            case LengExpr.SubC:
                gcc.add(string("sub"))
            case LengExpr.MulC:
                gcc.add(string("mul"))
            case LengExpr.DivC:
                gcc.add(string("div_"))
                prefix = string("_Qlengc_")
            case LengExpr.ModC:
                gcc.add(string("mod_"))
                prefix = string("_Qlengc_")
            case _:
                # The operation is gone: an optimizer rewrite replaced it with something
                # that cannot overflow. `(mul T x 1)` and `(add T x 0)` collapse to `x`,
                # `(mul T x 0)` and `(sub T x x)` to `0`, and constant folding turns
                # literal operands into a literal. Every rewrite that can leave a
                # non-arithmetic node here yields a value that provably cannot overflow,
                # so there is no check to emit: store the value and clear the flag, this
                # `keepovf` did not overflow. Erroring out instead made `newSeq[T](1)`
                # fail to compile at `-d:release`, where `(mul T 1 (sizeof T))` folds to
                # `(sizeof T)`.
                checkable = False
        if not checkable:
            with var:
                value = n.copy()
            skip(n)  # the value
            _genLvalue(c, n)  # the destination
            c.add(_PredefinedToken.AsgnOpr)
            _genx(c, value)
            c.add(_PredefinedToken.Semicolon)
            c._currentProc._needsOverflowFlag = True
            c.add(_PredefinedToken.OvfToken)
            c.add(_PredefinedToken.AsgnOpr)
            c.add(string("NIM_FALSE"))
            c.add(_PredefinedToken.Semicolon)
        else:
            with var:
                isLongLong = False
            with let:
                opName = gcc.copy()
            with into(n):  # (add | sub | mul | … <type> lhs rhs)
                if typeKind(n) == LengType.IT:
                    gcc = prefix + string("s") + gcc
                elif typeKind(n) == LengType.UT:
                    gcc = prefix + string("u") + gcc
                else:
                    _error(c._m, string("expected integer type but got: "), n)
                with into(n):  # (i bits) | (u bits)
                    if kind(n) == NifKind.IntLit:
                        with let:
                            bits = intVal(n)
                        if bits == 64 or (bits == -1 and c._bits == 64):
                            gcc.add(string("ll"))
                            isLongLong = True
                        elif (bits == 8 or bits == 16) and prefix == "__builtin_":
                            # `__builtin_[su]add_overflow` stores an `int` through its
                            # pointer; the type-generic builtin stores the narrow type and
                            # reports an overflow of that type
                            gcc = prefix + opName
                        n.inc()
                    else:
                        _error(c._m, string("expected integer literal but got: "), n)
                    while n.hasMore(): skip(n)
                c._currentProc._needsOverflowFlag = True
                # Not sticky: the flag is this operation's verdict alone.
                c.add(_PredefinedToken.OvfToken)
                c.add(_PredefinedToken.AsgnOpr)
                gcc.add(string("_overflow"))
                c.add(gcc)
                c.add(_PredefinedToken.ParLe)
                _genx(c, n)
                c.add(_PredefinedToken.Comma)
                _genx(c, n)
                while n.hasMore(): skip(n)
            c.add(_PredefinedToken.Comma)
            if isLongLong:
                c.add(string("(long long int*)"))
                c.add(_PredefinedToken.ParLe)
            c.add(_PredefinedToken.Amp)
            _genLvalue(c, n)
            if isLongLong:
                c.add(_PredefinedToken.ParRi)
            c.add(_PredefinedToken.ParRi)
            c.add(_PredefinedToken.Semicolon)
        while n.hasMore(): skip(n)


def _genStmt(c: mut @ GeneratedCode, n: mut @ Cursor):
    match stmtKind(n):
        case LengStmt.NoStmt:
            if kind(n) == NifKind.DotToken:
                n.inc()
            else:
                _error(c._m, string("expected statement but got: "), n)
        case LengStmt.StmtsS | LengStmt.AlwaysS:
            for _ in loopInto(n):
                _genStmt(c, n)
        case LengStmt.ScopeS:
            with let:
                oldInToplevel = c._inToplevel
            c._inToplevel = False
            _genScope(c, n)
            c._inToplevel = oldInToplevel
        case LengStmt.CallS:
            _genCall(c, n)
            c.add(_PredefinedToken.Semicolon)
        case LengStmt.InstrS:
            _genInstr(c, n)
            c.add(_PredefinedToken.Semicolon)
        case LengStmt.VarS:
            _genVar(c, n, _VarKind.IsLocal)
        case LengStmt.GvarS:
            _genVar(c, n, _VarKind.IsGlobal)
        case LengStmt.TvarS:
            _genVar(c, n, _VarKind.IsThreadlocal)
        case LengStmt.MflagS:
            _genMflagDecl(c, n)
        case LengStmt.VflagS:
            _genVflagDecl(c, n)
        case LengStmt.ConstS:
            _genVar(c, n, _VarKind.IsConst, useStatic=True)
        case LengStmt.EmitS:
            _genEmitStmt(c, n)
        case LengStmt.AsgnS:
            c._genCLineDir(_info(n))
            with into(n):
                _genLvalue(c, n)
                c.add(_PredefinedToken.AsgnOpr)
                _genx(c, n)
                c.add(_PredefinedToken.Semicolon)
                while n.hasMore(): skip(n)
        case LengStmt.IfS: _genIf(c, n)
        case LengStmt.IteS | LengStmt.ItecS: _genIte(c, n)
        case LengStmt.WhileS: _genWhile(c, n)
        case LengStmt.LoopS: _genLoop(c, n)
        case LengStmt.BreakS:
            with into(n):
                c.add(_PredefinedToken.BreakKeyword)
                c.add(_PredefinedToken.Semicolon)
                while n.hasMore(): skip(n)
        case LengStmt.JtrueS: _genJtrue(c, n)
        case LengStmt.CaseS: _genSwitch(c, n)
        case LengStmt.LabS: _genLabel(c, n)
        case LengStmt.JmpS: _genGoto(c, n)
        case LengStmt.RetS:
            c.add(_PredefinedToken.ReturnKeyword)
            with into(n):
                if kind(n) != NifKind.DotToken:
                    c.add(_PredefinedToken.Space)
                    _genx(c, n)
                else:
                    n.inc()
                c.add(_PredefinedToken.Semicolon)
                while n.hasMore(): skip(n)
        case LengStmt.DiscardS:
            with into(n):
                c.add(_PredefinedToken.DiscardToken)
                _genx(c, n)
                c.add(_PredefinedToken.Semicolon)
                while n.hasMore(): skip(n)
        case LengStmt.TryS:
            _genTryCpp(c, n)
        case LengStmt.RaiseS:
            c.add(_PredefinedToken.ThrowKeyword)
            with into(n):
                if kind(n) != NifKind.DotToken:
                    c.add(_PredefinedToken.Space)
                    _genx(c, n)
                else:
                    n.inc()
                c.add(_PredefinedToken.Semicolon)
                while n.hasMore(): skip(n)
        case LengStmt.OnerrS:
            with var:
                onErrAction = n.copy()
            onErrAction.inc()
            _genCallCanRaise(c, n)
            c.add(_PredefinedToken.Semicolon)
            if kind(onErrAction) != NifKind.DotToken:
                c._genOnError(onErrAction)
        case LengStmt.ProcS | LengStmt.TypeS:
            _error(c._m, string("expected statement but got: "), n)
        case LengStmt.KeepovfS:
            _genKeepOverflow(c, n)
