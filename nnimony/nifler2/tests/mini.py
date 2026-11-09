# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/nifler2/tests/mini.nim
# ///
## A miniature indentation-based language, used to exercise the generator end
## to end before the full Nim grammar is wired up. It is deliberately the
## smallest grammar that uses every mechanism the design rests on:
##
## * an indentation block (`indented`, `IND{=}`) and a guard rule (`notInd`)
## * retroactive wrapping after automatic left factoring (`exprStmt`)
## * a declared fallback (`%else`)
## * a left-associative postfix chain via the `^tag[...]` anchor (`suffix`)
## * a semantic predicate (`&noSpaceBefore`: `f(x)` is a call, `f (x)` a command)
## * precedence climbing (`binary`) and a parameterized rule
## * separated repetition, both with a terminal and with a bare guard

from __future__ import annotations
from nimic.ntypes import *
from .minirt import IndClass, insertOpLeafAt, Mark, NiflerKind, Parser, TokKind, wrap, wrapAt
from . import minirt
export(minirt)


# plugexpand: `grammar:` (line 16), expanded
def canSuffix(p: Parser) -> bool:
    result = p.tok().kind in Tset[TokKind](TokKind.tkParLe) and p.noSpaceBefore() or p.tok().kind in Tset[TokKind](TokKind.tkBracketLe) and p.noSpaceBefore() or p.tok().kind in Tset[TokKind](TokKind.tkDot)
    return result


def pModule(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok().kind in Tset[TokKind](TokKind.tkIf, TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol, TokKind.tkWhile):
        with let:
            m1 = p.mark()
        pStmt(p)
        while p.tok().kind in Tset[TokKind](TokKind.tkIf, TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol, TokKind.tkWhile) and p.indClass() in Tset[IndClass](IndClass.icEq) or p.tok().kind in Tset[TokKind](TokKind.tkSemiColon):
            with let:
                m2 = p.mark()
            if p.tok().kind in Tset[TokKind](TokKind.tkSemiColon):
                p.expect(TokKind.tkSemiColon)
            else:
                p.checkInd(Tset[IndClass](IndClass.icEq))
            m2.discardUnused()
            pStmt(p)
        if p.tok().kind in Tset[TokKind](TokKind.tkIf, TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSemiColon, TokKind.tkSymbol, TokKind.tkWhile) and p.indClass() == IndClass.icGt:
            p.indentError()
        m1.discardUnused()
    wrap(p, m0, NiflerKind.StmtsL)
    m0.discardUnused()


def pNotInd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    p.checkInd(Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq))
    m1.discardUnused()
    m0.discardUnused()


def pStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok().kind in Tset[TokKind](TokKind.tkIf):
        p.expect(TokKind.tkIf)
        pExpr(p, -1)
        p.expect(TokKind.tkColon)
        pBody(p)
        wrap(p, m0, NiflerKind.IfL)
    elif p.tok().kind in Tset[TokKind](TokKind.tkWhile):
        p.expect(TokKind.tkWhile)
        pExpr(p, -1)
        p.expect(TokKind.tkColon)
        pBody(p)
        wrap(p, m0, NiflerKind.WhileL)
    else:
        pExprStmt(p)
    m0.discardUnused()


def pBody(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok().kind in Tset[TokKind](TokKind.tkIf, TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol, TokKind.tkWhile) and p.indClass() in Tset[IndClass](IndClass.icGt):
        p.pushInd()
        with let:
            m1 = p.mark()
        pStmt(p)
        while p.tok().kind in Tset[TokKind](TokKind.tkIf, TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol, TokKind.tkWhile) and p.indClass() in Tset[IndClass](IndClass.icEq) or p.tok().kind in Tset[TokKind](TokKind.tkSemiColon):
            with let:
                m2 = p.mark()
            if p.tok().kind in Tset[TokKind](TokKind.tkSemiColon):
                p.expect(TokKind.tkSemiColon)
            else:
                p.checkInd(Tset[IndClass](IndClass.icEq))
            m2.discardUnused()
            pStmt(p)
        if p.tok().kind in Tset[TokKind](TokKind.tkIf, TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSemiColon, TokKind.tkSymbol, TokKind.tkWhile) and p.indClass() == IndClass.icGt:
            p.indentError()
        m1.discardUnused()
        p.popInd()
    elif p.tok().kind in Tset[TokKind](TokKind.tkIf, TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol, TokKind.tkWhile) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq):
        pNotInd(p)
        pStmt(p)
    else:
        p.ruleError(string("body"), False)
    m0.discardUnused()


def pExprStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok().kind in Tset[TokKind](TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol):
        pExpr(p, -1)
        if p.tok().kind in Tset[TokKind](TokKind.tkEquals):
            p.expect(TokKind.tkEquals)
            pExpr(p, -1)
            wrap(p, m0, NiflerKind.AsgnL)
        elif p.tok().kind in Tset[TokKind](TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol):
            with let:
                m1 = p.mark()
            pExpr(p, -1)
            m1.discardUnused()
            while p.tok().kind in Tset[TokKind](TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol):
                with let:
                    m2 = p.mark()
                pExpr(p, -1)
                m2.discardUnused()
            wrap(p, m0, NiflerKind.CmdL)
        else:
            pass
    else:
        p.ruleError(string("exprStmt"), False)
    m0.discardUnused()


def pExpr(p: mut @ Parser, limit: nint):
    with let:
        m0 = p.mark()
    pPrimary(p)
    with var:
        prec = p.getPrecedence()
    while prec >= limit and p.indClass() == IndClass.icNoInd:
        with var:
            assoc = 1
        if p.isRightAssoc():
            assoc = 0
        with let:
            opInfo = p.info()
        insertOpLeafAt(p, m0)
        p.getTok()
        p.afterOperator()
        pExpr(p, prec + assoc)
        wrapAt(p, m0, NiflerKind.InfixL, opInfo)
        prec = p.getPrecedence()
    m0.discardUnused()


def pPrimary(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pAtom(p)
    while canSuffix(p):
        with let:
            m1 = p.mark()
        pSuffix(p, m0)
        m1.discardUnused()
    m0.discardUnused()


def pSuffix(p: mut @ Parser, anchor: Mark):
    with let:
        m0 = p.mark()
    if p.tok().kind in Tset[TokKind](TokKind.tkBracketLe, TokKind.tkParLe) and p.noSpaceBefore():
        if p.tok().kind in Tset[TokKind](TokKind.tkParLe):
            with var:
                at1 = p.info()
            p.expect(TokKind.tkParLe)
            if p.tok().kind in Tset[TokKind](TokKind.tkIntLit, TokKind.tkParLe, TokKind.tkSymbol):
                with let:
                    m2 = p.mark()
                pExpr(p, -1)
                while p.tok().kind in Tset[TokKind](TokKind.tkComma):
                    p.expect(TokKind.tkComma)
                    pExpr(p, -1)
                m2.discardUnused()
            p.expect(TokKind.tkParRi)
            wrapAt(p, anchor, NiflerKind.CallL, at1)
        elif p.tok().kind in Tset[TokKind](TokKind.tkBracketLe):
            with var:
                at3 = p.info()
            p.expect(TokKind.tkBracketLe)
            pExpr(p, -1)
            p.expect(TokKind.tkBracketRi)
            wrapAt(p, anchor, NiflerKind.AtL, at3)
        else:
            p.ruleError(string("suffix"), False)
    elif p.tok().kind in Tset[TokKind](TokKind.tkDot):
        with var:
            at4 = p.info()
        p.expect(TokKind.tkDot)
        p.emitLeaf()
        wrapAt(p, anchor, NiflerKind.DotL, at4)
    else:
        p.ruleError(string("suffix"), False)
    m0.discardUnused()


def pAtom(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok().kind in Tset[TokKind](TokKind.tkSymbol):
        p.emitLeaf()
    elif p.tok().kind in Tset[TokKind](TokKind.tkIntLit):
        p.emitLeaf()
    elif p.tok().kind in Tset[TokKind](TokKind.tkParLe):
        p.expect(TokKind.tkParLe)
        pExpr(p, -1)
        p.expect(TokKind.tkParRi)
    else:
        p.ruleError(string("atom"), False)
    m0.discardUnused()
