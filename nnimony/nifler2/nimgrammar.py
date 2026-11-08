# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/nifler2/nimgrammar.nim
# ///
#       Nifler2
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## The grammar of Nim.
##
## Transcribed from Nim's `doc/grammar.txt`, which is itself generated from the
## `#|` comments in `compiler/parser.nim`. See
## `doc/internals/parser_generator.md` for the notation.
##
## Transcription rules followed here:
##
## * `doc/grammar.txt` is the source, and where it disagrees with what
##   `parser.nim` actually does, the transcription follows **parser.nim** and
##   says so in a `# GRAMMAR.TXT:` note. Collecting those is one of the points
##   of the exercise.
## * Ordered choice (`/`) does not exist in the notation. Every `/` in the
##   original is resolved into either disjoint alternatives (usually by an
##   indentation class), a left-factored set of entries, or a declared
##   predicate — and the ones that needed a predicate are marked `# PRED`.
## * `OP0`..`OP10` and the eleven precedence-level rules are gone; `binary(...)`
##   owns precedence, exactly as `parser.nim` does.
## * `DED` is implicit in `indented(...)`.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import strutils
from .parserrt import (
    accentEnd, add, addSubtree, afterOperator, attachBlocks, blockNameEnd, callOrObjConstr, checkInd, childCursor,
    curlyOrTable, doLayout, dotLayout, emitLeaf, emptyDiscriminator, endRead, enumListEnd, expect, expectLeaf,
    exprExpected, fanOut, fanOutKv, identExpected, inc, IndClass, indentError, inheritLayout, inSemiStmtList,
    insertTokAt, listEnd, Mark, NiflerKind, noIndHere, openParser, Parser, Pool, pragmaBlock, PrimaryMode,
    procLayout, pushInd, requireFields, routineLayout, ruleError, skip, stmtListEnd, stmtListExprLayout,
    strictListEnd, strictListStart, TagPool, TokenBuf, TokKind, tupleEnd, wrap, wrapAt, wrapLikeFirst,
    wrapNoInfo, wrapSection)
importFrom("..lib.nifcore", "createTokenBuf")
from . import parserrt
export(parserrt)


# plugexpand: `grammar:` (line 32), expanded
def canIdentOrLiteral(p: Parser, mode: PrimaryMode) -> bool:
    result = p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkRStrLit, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit) or p.tok.kind in Tset[TokKind](TokKind.tkParLe) and p.parIsTuple(mode) or p.tok.kind in Tset[TokKind](TokKind.tkParLe)
    return result


def canPrimarySuffix(p: Parser, mode: PrimaryMode) -> bool:
    result = p.tok.kind in Tset[TokKind](TokKind.tkParLe) and p.noSpaceBefore() or p.tok.kind in Tset[TokKind](TokKind.tkDot) or p.tok.kind == TokKind.tkOpr and p.tok.isDotLike() and p.dotLikeOps() or p.tok.kind in Tset[TokKind](TokKind.tkGStrLit, TokKind.tkGTripleStrLit) or p.tok.kind in Tset[TokKind](TokKind.tkBracketLe) and p.noSpaceBefore() or p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe) and p.noSpaceBefore()
    return result


def canCommandSuffix(p: Parser, mode: PrimaryMode) -> bool:
    result = p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.commandStart() and p.commandAllowed(mode)
    return result


def canTypeKAuxOperand(p: Parser, mode: PrimaryMode) -> bool:
    result = p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkConcept, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt) and p.isTypedefOperand(mode) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt) and p.typeOperandFollows()
    return result


def canCommandParam(p: Parser, mode: PrimaryMode) -> bool:
    result = p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor) and p.inTypeDesc(mode) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor)
    return result


def canPrimary(p: Parser, mode: PrimaryMode) -> bool:
    result = p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkParLe, TokKind.tkRStrLit, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit) or p.tok.kind in Tset[TokKind](TokKind.tkAnd, TokKind.tkAs, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkFrom, TokKind.tkIn, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkMod, TokKind.tkNot, TokKind.tkNotin, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkShl, TokKind.tkShr, TokKind.tkXor) and p.isSigilLike() or p.tok.kind in Tset[TokKind](TokKind.tkAnd, TokKind.tkAs, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkFrom, TokKind.tkIn, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkMod, TokKind.tkNot, TokKind.tkNotin, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkShl, TokKind.tkShr, TokKind.tkXor) and p.isUnary() or p.tok.kind in Tset[TokKind](TokKind.tkFunc, TokKind.tkIterator, TokKind.tkProc) or p.tok.kind in Tset[TokKind](TokKind.tkBind) or p.tok.kind in Tset[TokKind](TokKind.tkDistinct, TokKind.tkEnum, TokKind.tkObject, TokKind.tkOut, TokKind.tkPtr, TokKind.tkRef, TokKind.tkTuple, TokKind.tkVar) or p.tok.kind in Tset[TokKind](TokKind.tkAnd, TokKind.tkAs, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkFrom, TokKind.tkIn, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkMod, TokKind.tkNot, TokKind.tkNotin, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkShl, TokKind.tkShr, TokKind.tkXor)
    return result


def canGenericParamName(p: Parser) -> bool:
    result = p.tok.kind in Tset[TokKind](inrange(TokKind.tkAddr, TokKind.tkYield)) and p.inOrOut() or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol)
    return result


def canStmt(p: Parser) -> bool:
    result = p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icGt) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExport, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq) and inSemiStmtList(p) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExport, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd)
    return result


def pModule(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
        with let:
            m1 = p.mark()
        pComplexOrSimpleStmt(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
            with let:
                m2 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                expect(p, TokKind.tkSemiColon)
            else:
                checkInd(p, Tset[IndClass](IndClass.icEq))
            m2.discardUnused()
            pComplexOrSimpleStmt(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkSemiColon, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() == IndClass.icGt:
            indentError(p)
        m1.discardUnused()
    wrap(p, m0, NiflerKind.StmtsL)
    m0.discardUnused()


def pComma(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkComma)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    m0.discardUnused()


def pSemicolon(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkSemiColon)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    m0.discardUnused()


def pColon(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkColon)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    m0.discardUnused()


def pColcom(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkColon)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    m0.discardUnused()


def pTrailComment(p: mut @ Parser):
    with let:
        m0 = p.mark()
    checkInd(p, Tset[IndClass](IndClass.icNoInd))
    emitLeaf(p)
    m0.discardUnused()


def pFlexComment(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pValidInd(p)
    emitLeaf(p)
    m0.discardUnused()


def pValidInd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    checkInd(p, Tset[IndClass](IndClass.icNoInd, IndClass.icGt))
    m1.discardUnused()
    m0.discardUnused()


def pOptSameInd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    checkInd(p, Tset[IndClass](IndClass.icNoInd, IndClass.icEq))
    m1.discardUnused()
    m0.discardUnused()


def pNotInd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    checkInd(p, Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq))
    m1.discardUnused()
    m0.discardUnused()


def pOptInd(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    pValidInd(p)
    m0.discardUnused()


def pOptPar(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    checkInd(p, Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt))
    m1.discardUnused()
    m0.discardUnused()


def pOperator(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkOpr):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOr):
        expectLeaf(p, TokKind.tkOr)
    elif p.tok.kind in Tset[TokKind](TokKind.tkXor):
        expectLeaf(p, TokKind.tkXor)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAnd):
        expectLeaf(p, TokKind.tkAnd)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIs):
        expectLeaf(p, TokKind.tkIs)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIsnot):
        expectLeaf(p, TokKind.tkIsnot)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIn):
        expectLeaf(p, TokKind.tkIn)
    elif p.tok.kind in Tset[TokKind](TokKind.tkNotin):
        expectLeaf(p, TokKind.tkNotin)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOf):
        expectLeaf(p, TokKind.tkOf)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAs):
        expectLeaf(p, TokKind.tkAs)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFrom):
        expectLeaf(p, TokKind.tkFrom)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDiv):
        expectLeaf(p, TokKind.tkDiv)
    elif p.tok.kind in Tset[TokKind](TokKind.tkMod):
        expectLeaf(p, TokKind.tkMod)
    elif p.tok.kind in Tset[TokKind](TokKind.tkShl):
        expectLeaf(p, TokKind.tkShl)
    elif p.tok.kind in Tset[TokKind](TokKind.tkShr):
        expectLeaf(p, TokKind.tkShr)
    elif p.tok.kind in Tset[TokKind](TokKind.tkNot):
        expectLeaf(p, TokKind.tkNot)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDotDot):
        expectLeaf(p, TokKind.tkDotDot)
    else:
        ruleError(p, string("operator"), False)
    m1.discardUnused()
    m0.discardUnused()


def pPrefixOperator(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pOperator(p)
    m0.discardUnused()


def pOperatorB(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pOperator(p)
    m0.discardUnused()


def pPlainSymbol(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent):
        expect(p, TokKind.tkAccent)
        with let:
            m1 = p.mark()
            m2 = p.mark()
        if p.tok.kind in Tset[TokKind](inrange(TokKind.tkAddr, TokKind.tkYield)):
            emitLeaf(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkSymbol):
            emitLeaf(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCharLit, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkRStrLit, TokKind.tkStrLit, TokKind.tkTripleStrLit, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
            pQuotedLiteral(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBracketDotLe, TokKind.tkBracketDotRi, TokKind.tkBracketLe, TokKind.tkBracketRi, TokKind.tkCurlyDotLe, TokKind.tkCurlyDotRi, TokKind.tkCurlyLe, TokKind.tkCurlyRi, TokKind.tkDot, TokKind.tkDotDot, TokKind.tkEquals, TokKind.tkOpr, TokKind.tkParDotLe, TokKind.tkParDotRi, TokKind.tkParLe, TokKind.tkParRi):
            pQuotedPunct(p)
        else:
            ruleError(p, string("plainSymbol"), False)
        m2.discardUnused()
        m1.discardUnused()
        while p.tok.kind in Tset[TokKind](inrange(TokKind.tkAddr, TokKind.tkYield), TokKind.tkBracketDotLe, TokKind.tkBracketDotRi, TokKind.tkBracketLe, TokKind.tkBracketRi, TokKind.tkCharLit, TokKind.tkCurlyDotLe, TokKind.tkCurlyDotRi, TokKind.tkCurlyLe, TokKind.tkCurlyRi, TokKind.tkCustomLit, TokKind.tkDot, TokKind.tkDotDot, TokKind.tkEquals, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkOpr, TokKind.tkParDotLe, TokKind.tkParDotRi, TokKind.tkParLe, TokKind.tkParRi, TokKind.tkRStrLit, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
            with let:
                m3 = p.mark()
                m4 = p.mark()
            if p.tok.kind in Tset[TokKind](inrange(TokKind.tkAddr, TokKind.tkYield)):
                emitLeaf(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkSymbol):
                emitLeaf(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkCharLit, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkRStrLit, TokKind.tkStrLit, TokKind.tkTripleStrLit, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
                pQuotedLiteral(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkBracketDotLe, TokKind.tkBracketDotRi, TokKind.tkBracketLe, TokKind.tkBracketRi, TokKind.tkCurlyDotLe, TokKind.tkCurlyDotRi, TokKind.tkCurlyLe, TokKind.tkCurlyRi, TokKind.tkDot, TokKind.tkDotDot, TokKind.tkEquals, TokKind.tkOpr, TokKind.tkParDotLe, TokKind.tkParDotRi, TokKind.tkParLe, TokKind.tkParRi):
                pQuotedPunct(p)
            else:
                ruleError(p, string("plainSymbol"), False)
            m4.discardUnused()
            m3.discardUnused()
        pAccentEnd(p)
        expect(p, TokKind.tkAccent)
        wrap(p, m0, NiflerKind.QuotedL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkSymbol):
        emitLeaf(p)
    else:
        ruleError(p, string("plainSymbol"), False)
    m0.discardUnused()


def pAccentEnd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    accentEnd(p)
    m0.discardUnused()


def pQuotedLiteral(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pLiteral(p)
    with let:
        m = m0
    p.literalAsIdent(m)
    m0.discardUnused()


def pQuotedPunct(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
        m2 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkOpr):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDot):
        expectLeaf(p, TokKind.tkDot)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDotDot):
        expectLeaf(p, TokKind.tkDotDot)
    elif p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        expectLeaf(p, TokKind.tkEquals)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        expectLeaf(p, TokKind.tkParLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParRi):
        expectLeaf(p, TokKind.tkParRi)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
        expectLeaf(p, TokKind.tkBracketLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBracketRi):
        expectLeaf(p, TokKind.tkBracketRi)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
        expectLeaf(p, TokKind.tkCurlyLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyRi):
        expectLeaf(p, TokKind.tkCurlyRi)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBracketDotLe):
        expectLeaf(p, TokKind.tkBracketDotLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBracketDotRi):
        expectLeaf(p, TokKind.tkBracketDotRi)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        expectLeaf(p, TokKind.tkCurlyDotLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotRi):
        expectLeaf(p, TokKind.tkCurlyDotRi)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParDotLe):
        expectLeaf(p, TokKind.tkParDotLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParDotRi):
        expectLeaf(p, TokKind.tkParDotRi)
    else:
        ruleError(p, string("quotedPunct"), False)
    m2.discardUnused()
    m1.discardUnused()
    while p.tok.kind in Tset[TokKind](TokKind.tkBracketDotLe, TokKind.tkBracketDotRi, TokKind.tkBracketLe, TokKind.tkBracketRi, TokKind.tkCurlyDotLe, TokKind.tkCurlyDotRi, TokKind.tkCurlyLe, TokKind.tkCurlyRi, TokKind.tkDot, TokKind.tkDotDot, TokKind.tkEquals, TokKind.tkOpr, TokKind.tkParDotLe, TokKind.tkParDotRi, TokKind.tkParLe, TokKind.tkParRi):
        with let:
            m3 = p.mark()
            m4 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkOpr):
            emitLeaf(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDot):
            expectLeaf(p, TokKind.tkDot)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDotDot):
            expectLeaf(p, TokKind.tkDotDot)
        elif p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            expectLeaf(p, TokKind.tkEquals)
        elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
            expectLeaf(p, TokKind.tkParLe)
        elif p.tok.kind in Tset[TokKind](TokKind.tkParRi):
            expectLeaf(p, TokKind.tkParRi)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
            expectLeaf(p, TokKind.tkBracketLe)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBracketRi):
            expectLeaf(p, TokKind.tkBracketRi)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
            expectLeaf(p, TokKind.tkCurlyLe)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyRi):
            expectLeaf(p, TokKind.tkCurlyRi)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBracketDotLe):
            expectLeaf(p, TokKind.tkBracketDotLe)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBracketDotRi):
            expectLeaf(p, TokKind.tkBracketDotRi)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
            expectLeaf(p, TokKind.tkCurlyDotLe)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotRi):
            expectLeaf(p, TokKind.tkCurlyDotRi)
        elif p.tok.kind in Tset[TokKind](TokKind.tkParDotLe):
            expectLeaf(p, TokKind.tkParDotLe)
        elif p.tok.kind in Tset[TokKind](TokKind.tkParDotRi):
            expectLeaf(p, TokKind.tkParDotRi)
        else:
            ruleError(p, string("quotedPunct"), False)
        m4.discardUnused()
        m3.discardUnused()
    with let:
        m = m0
    p.joinIdents(m)
    m0.discardUnused()


def pSymbol(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pPlainSymbol(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAddr):
        expectLeaf(p, TokKind.tkAddr)
    elif p.tok.kind in Tset[TokKind](TokKind.tkType):
        expectLeaf(p, TokKind.tkType)
    elif p.tok.kind in Tset[TokKind](TokKind.tkStatic):
        expectLeaf(p, TokKind.tkStatic)
    else:
        ruleError(p, string("symbol"), False)
    m0.discardUnused()


def pSymbolOrKeyword(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
        pSymbol(p)
    elif p.tok.kind in Tset[TokKind](inrange(TokKind.tkAddr, TokKind.tkYield)):
        emitLeaf(p)
    else:
        ruleError(p, string("symbolOrKeyword"), False)
    m0.discardUnused()


def pLiteral(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkIntLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkInt8Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkInt16Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkInt32Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkInt64Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkUIntLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkUInt8Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkUInt16Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkUInt32Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkUInt64Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFloatLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFloat32Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFloat64Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFloat128Lit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkStrLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkRStrLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkTripleStrLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCharLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCustomLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkNil):
        expect(p, TokKind.tkNil)
        wrap(p, m1, NiflerKind.NilL)
    else:
        ruleError(p, string("literal"), False)
    m1.discardUnused()
    m0.discardUnused()


def pGeneralizedLit(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkGStrLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkGTripleStrLit):
        emitLeaf(p)
    else:
        ruleError(p, string("generalizedLit"), False)
    m1.discardUnused()
    m0.discardUnused()


def pExprColonEqExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
        pExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkEquals):
            with var:
                at1 = p.info()
            if p.tok.kind in Tset[TokKind](TokKind.tkColon):
                expect(p, TokKind.tkColon)
                pExpr(p)
                wrapAt(p, m0, NiflerKind.KvL, at1)
            elif p.tok.kind in Tset[TokKind](TokKind.tkEquals):
                expect(p, TokKind.tkEquals)
                pExpr(p)
                wrapAt(p, m0, NiflerKind.VvL, at1)
            else:
                ruleError(p, string("exprColonEqExpr"), False)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            if p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m2 = p.mark()
                checkInd(p, Tset[IndClass](IndClass.icNoInd))
                pDoBlock(p, True)
                while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                    with let:
                        m3 = p.mark()
                    pExtraPostExprBlock(p)
                    m3.discardUnused()
                m2.discardUnused()
            with let:
                m = m0
            attachBlocks(p, m)
        else:
            if p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m4 = p.mark()
                checkInd(p, Tset[IndClass](IndClass.icNoInd))
                pDoBlock(p, True)
                while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                    with let:
                        m5 = p.mark()
                    pExtraPostExprBlock(p)
                    m5.discardUnused()
                m4.discardUnused()
            with let:
                m = m0
            attachBlocks(p, m)
    else:
        ruleError(p, string("exprColonEqExpr"), False)
    m0.discardUnused()


def pExprEqExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
        pExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with var:
                at1 = m0.info
            at1 = p.info()
            expect(p, TokKind.tkEquals)
            pExpr(p)
            wrapAt(p, m0, NiflerKind.VvL, at1)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            if p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m2 = p.mark()
                checkInd(p, Tset[IndClass](IndClass.icNoInd))
                pDoBlock(p, True)
                while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                    with let:
                        m3 = p.mark()
                    pExtraPostExprBlock(p)
                    m3.discardUnused()
                m2.discardUnused()
            with let:
                m = m0
            attachBlocks(p, m)
        else:
            if p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m4 = p.mark()
                checkInd(p, Tset[IndClass](IndClass.icNoInd))
                pDoBlock(p, True)
                while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                    with let:
                        m5 = p.mark()
                    pExtraPostExprBlock(p)
                    m5.discardUnused()
                m4.discardUnused()
            with let:
                m = m0
            attachBlocks(p, m)
    else:
        ruleError(p, string("exprEqExpr"), False)
    m0.discardUnused()


def pExprList(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    pExpr(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        pComma(p)
        pExpr(p)
    m1.discardUnused()
    m0.discardUnused()


def pExprColonEqExprList(p: mut @ Parser, close: TokKind):
    with let:
        m0 = p.mark()
    pExprColonEqExpr(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        with let:
            m2 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
            pExprColonEqExpr(p)
        else:
            pListEnd(p, close)
        m2.discardUnused()
        m1.discardUnused()
    m0.discardUnused()


def pListEnd(p: mut @ Parser, close: TokKind):
    with let:
        m0 = p.mark()
        m = m0
    listEnd(p, close)
    m0.discardUnused()


def pQualifiedIdent(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
        pSymbol(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkDot):
            with var:
                at1 = m0.info
            at1 = p.info()
            expect(p, TokKind.tkDot)
            pOptInd(p)
            pSymbolOrKeyword(p)
            wrapAt(p, m0, NiflerKind.DotL, at1)
        else:
            pass
    else:
        ruleError(p, string("qualifiedIdent"), False)
    m0.discardUnused()


def pSetOrTableConstr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
        expect(p, TokKind.tkCurlyLe)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCurlyRi, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            pOptInd(p)
            with let:
                m1 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                pExprColonEqExprList(p, TokKind.tkCurlyRi)
            else:
                pListEnd(p, TokKind.tkCurlyRi)
            m1.discardUnused()
            pOptPar(p)
            expect(p, TokKind.tkCurlyRi)
            wrap(p, m0, NiflerKind.CurlyL)
            with let:
                m = m0
            curlyOrTable(p, m)
        elif p.tok.kind in Tset[TokKind](TokKind.tkColon):
            expect(p, TokKind.tkColon)
            pOptPar(p)
            expect(p, TokKind.tkCurlyRi)
            wrap(p, m0, NiflerKind.TabconstrL)
        else:
            ruleError(p, string("setOrTableConstr"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCurlyRi, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq, IndClass.icGt))
    else:
        ruleError(p, string("setOrTableConstr"), False)
    m0.discardUnused()


def pCastExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkCast):
        expect(p, TokKind.tkCast)
        if p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
            expect(p, TokKind.tkBracketLe)
            pOptInd(p)
            pTypeDesc(p)
            pOptPar(p)
            expect(p, TokKind.tkBracketRi)
            expect(p, TokKind.tkParLe)
            pOptInd(p)
            pExpr(p)
            pOptPar(p)
            expect(p, TokKind.tkParRi)
            wrap(p, m0, NiflerKind.CastL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
            expect(p, TokKind.tkParLe)
            p.emitEmpty()
            pOptInd(p)
            pExprColonEqExpr(p)
            pOptPar(p)
            expect(p, TokKind.tkParRi)
            wrap(p, m0, NiflerKind.CastL)
        else:
            ruleError(p, string("castExpr"), False)
    else:
        ruleError(p, string("castExpr"), False)
    m0.discardUnused()


def pParKeyw(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkDiscard):
        expect(p, TokKind.tkDiscard)
    elif p.tok.kind in Tset[TokKind](TokKind.tkInclude):
        expect(p, TokKind.tkInclude)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIf):
        expect(p, TokKind.tkIf)
    elif p.tok.kind in Tset[TokKind](TokKind.tkWhile):
        expect(p, TokKind.tkWhile)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCase):
        expect(p, TokKind.tkCase)
    elif p.tok.kind in Tset[TokKind](TokKind.tkTry):
        expect(p, TokKind.tkTry)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFinally):
        expect(p, TokKind.tkFinally)
    elif p.tok.kind in Tset[TokKind](TokKind.tkExcept):
        expect(p, TokKind.tkExcept)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFor):
        expect(p, TokKind.tkFor)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBlock):
        expect(p, TokKind.tkBlock)
    elif p.tok.kind in Tset[TokKind](TokKind.tkConst):
        expect(p, TokKind.tkConst)
    elif p.tok.kind in Tset[TokKind](TokKind.tkLet):
        expect(p, TokKind.tkLet)
    elif p.tok.kind in Tset[TokKind](TokKind.tkWhen):
        expect(p, TokKind.tkWhen)
    elif p.tok.kind in Tset[TokKind](TokKind.tkVar):
        expect(p, TokKind.tkVar)
    elif p.tok.kind in Tset[TokKind](TokKind.tkMixin):
        expect(p, TokKind.tkMixin)
    else:
        ruleError(p, string("parKeyw"), False)
    m1.discardUnused()
    m0.discardUnused()


def pSemiStmtItem(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkIf):
        pIfExpr(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkWhen):
        pWhenExpr(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
        pComplexOrSimpleStmt(p)
    else:
        ruleError(p, string("semiStmtItem"), False)
    m1.discardUnused()
    m0.discardUnused()


def pSemiStmtList(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.inSemiStmtList += 1
    pSemiStmtItem(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkSemiColon, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
        with let:
            m1 = p.mark()
            m2 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
            expect(p, TokKind.tkSemiColon)
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
                with let:
                    m3 = p.mark()
                pSemiStmtItem(p)
                m3.discardUnused()
        elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
            pSemiStmtItem(p)
        else:
            ruleError(p, string("semiStmtList"), False)
        m2.discardUnused()
        m1.discardUnused()
    p.inSemiStmtList -= 1
    m0.discardUnused()


def pPar(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        expect(p, TokKind.tkParLe)
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkSemiColon, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            pOptInd(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkBlock, TokKind.tkCase, TokKind.tkConst, TokKind.tkDiscard, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkFor, TokKind.tkIf, TokKind.tkInclude, TokKind.tkLet, TokKind.tkMixin, TokKind.tkTry, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile):
                p.pushIndAny()
                pSemiStmtList(p)
                p.popInd()
                pOptPar(p)
                expect(p, TokKind.tkParRi)
                with let:
                    m = m0
                stmtListExprLayout(p, m)
            elif p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                expect(p, TokKind.tkSemiColon)
                if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
                    with let:
                        m1 = p.mark()
                    p.pushIndAny()
                    pSemiStmtList(p)
                    p.popInd()
                    m1.discardUnused()
                pOptPar(p)
                expect(p, TokKind.tkParRi)
                with let:
                    m = m0
                stmtListExprLayout(p, m)
            elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
                pPragmaStmt(p)
                pOptPar(p)
                expect(p, TokKind.tkParRi)
                wrap(p, m0, NiflerKind.ParL)
            elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor):
                pSimpleExpr(p, -1, PrimaryMode.pmNormal)
                if p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                    checkInd(p, Tset[IndClass](IndClass.icNoInd))
                    pDoBlock(p, True)
                    while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                        with let:
                            m2 = p.mark()
                        pExtraPostExprBlock(p)
                        m2.discardUnused()
                    pOptPar(p)
                    expect(p, TokKind.tkParRi)
                    with let:
                        m = m0
                    attachBlocks(p, m)
                elif p.tok.kind in Tset[TokKind](TokKind.tkEquals):
                    with var:
                        at3 = m0.info
                    at3 = p.info()
                    expect(p, TokKind.tkEquals)
                    pExpr(p)
                    wrapAt(p, m0, NiflerKind.AsgnL, at3)
                    if p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                        pOptPar(p)
                        expect(p, TokKind.tkParRi)
                        wrap(p, m0, NiflerKind.ParL)
                    elif p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                        expect(p, TokKind.tkSemiColon)
                        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
                            with let:
                                m4 = p.mark()
                            p.pushIndAny()
                            pSemiStmtList(p)
                            p.popInd()
                            m4.discardUnused()
                        pOptPar(p)
                        expect(p, TokKind.tkParRi)
                        with let:
                            m = m0
                        stmtListExprLayout(p, m)
                    else:
                        ruleError(p, string("par"), p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icLt))
                elif p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                    expect(p, TokKind.tkSemiColon)
                    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield):
                        with let:
                            m5 = p.mark()
                        p.pushIndAny()
                        pSemiStmtList(p)
                        p.popInd()
                        m5.discardUnused()
                    pOptPar(p)
                    expect(p, TokKind.tkParRi)
                    with let:
                        m = m0
                    stmtListExprLayout(p, m)
                elif p.tok.kind in Tset[TokKind](TokKind.tkColon):
                    with let:
                        m6 = p.mark()
                    with var:
                        at7 = p.info()
                    expect(p, TokKind.tkColon)
                    pExpr(p)
                    wrapAt(p, m0, NiflerKind.KvL, at7)
                    m6.discardUnused()
                    while p.tok.kind in Tset[TokKind](TokKind.tkColon):
                        with let:
                            m8 = p.mark()
                        with var:
                            at9 = p.info()
                        expect(p, TokKind.tkColon)
                        pExpr(p)
                        wrapAt(p, m0, NiflerKind.KvL, at9)
                        m8.discardUnused()
                    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        with let:
                            m10 = p.mark()
                        pComma(p)
                        with let:
                            m11 = p.mark()
                        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                            pExprColonEqExpr(p)
                        else:
                            pListEnd(p, TokKind.tkParRi)
                        m11.discardUnused()
                        m10.discardUnused()
                    pOptPar(p)
                    expect(p, TokKind.tkParRi)
                    wrap(p, m0, NiflerKind.TupL)
                elif p.tok.kind in Tset[TokKind](TokKind.tkComma):
                    pComma(p)
                    while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                        with let:
                            m12 = p.mark()
                        pExprColonEqExpr(p)
                        if p.tok.kind in Tset[TokKind](TokKind.tkComma):
                            with let:
                                m13 = p.mark()
                            pComma(p)
                            m13.discardUnused()
                        m12.discardUnused()
                    pTupleEnd(p)
                    pOptPar(p)
                    expect(p, TokKind.tkParRi)
                    wrap(p, m0, NiflerKind.TupL)
                elif p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                    pOptPar(p)
                    expect(p, TokKind.tkParRi)
                    wrap(p, m0, NiflerKind.ParL)
                else:
                    ruleError(p, string("par"), p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icLt) or p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq, IndClass.icGt))
            else:
                ruleError(p, string("par"), False)
        elif p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
            pOptPar(p)
            expect(p, TokKind.tkParRi)
            wrap(p, m0, NiflerKind.TupL)
        else:
            ruleError(p, string("par"), p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icLt) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkSemiColon, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.indClass() not in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt))
    else:
        ruleError(p, string("par"), False)
    m0.discardUnused()


def pTupleConstr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        expect(p, TokKind.tkParLe)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkParRi, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
                with let:
                    m1 = p.mark()
                pFlexComment(p)
                m1.discardUnused()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkParRi, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                pOptPar(p)
                if p.tok.kind in Tset[TokKind](TokKind.tkParRi):
                    expect(p, TokKind.tkParRi)
                    wrap(p, m0, NiflerKind.ParL)
                elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                    pExprColonEqExpr(p)
                    if p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                        pOptPar(p)
                        expect(p, TokKind.tkParRi)
                        wrap(p, m0, NiflerKind.ParL)
                    elif p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        pComma(p)
                        while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                            with let:
                                m2 = p.mark()
                            pExprColonEqExpr(p)
                            if p.tok.kind in Tset[TokKind](TokKind.tkComma):
                                with let:
                                    m3 = p.mark()
                                pComma(p)
                                m3.discardUnused()
                            m2.discardUnused()
                        pTupleEnd(p)
                        pOptPar(p)
                        expect(p, TokKind.tkParRi)
                        wrap(p, m0, NiflerKind.TupL)
                    else:
                        ruleError(p, string("tupleConstr"), p.tok.kind in Tset[TokKind](TokKind.tkParRi) and p.indClass() in Tset[IndClass](IndClass.icLt))
                else:
                    ruleError(p, string("tupleConstr"), False)
            else:
                ruleError(p, string("tupleConstr"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkParRi, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icLt) or p.indClass() not in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt))
        else:
            ruleError(p, string("tupleConstr"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkParRi, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icLt) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.indClass() not in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt))
    else:
        ruleError(p, string("tupleConstr"), False)
    m0.discardUnused()


def pTupleEnd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    tupleEnd(p)
    m0.discardUnused()


def pArrayConstr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkBracketLe)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pFlexComment(p)
        m1.discardUnused()
    pOptPar(p)
    with let:
        m2 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
        pExprColonEqExprList(p, TokKind.tkBracketRi)
    else:
        pListEnd(p, TokKind.tkBracketRi)
    m2.discardUnused()
    pOptPar(p)
    expect(p, TokKind.tkBracketRi)
    wrap(p, m0, NiflerKind.BracketL)
    m0.discardUnused()


def pIdentOrLiteral(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkRStrLit, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
        with let:
            m1 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkGStrLit, TokKind.tkGTripleStrLit):
            pGeneralizedLit(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
            pSymbol(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCharLit, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkRStrLit, TokKind.tkStrLit, TokKind.tkTripleStrLit, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
            pLiteral(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
            pArrayConstr(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
            pSetOrTableConstr(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCast):
            pCastExpr(p)
        else:
            ruleError(p, string("identOrLiteral"), False)
        m1.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkParLe) and p.parIsTuple(mode):
        pTupleConstr(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        pPar(p)
    else:
        ruleError(p, string("identOrLiteral"), False)
    m0.discardUnused()


def pPrimarySuffix(p: mut @ Parser, anchor: Mark, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkBracketLe, TokKind.tkCurlyLe, TokKind.tkParLe) and p.noSpaceBefore():
        if p.tok.kind in Tset[TokKind](TokKind.tkParLe):
            with var:
                at1 = p.info()
            expect(p, TokKind.tkParLe)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
                with let:
                    m2 = p.mark()
                pFlexComment(p)
                m2.discardUnused()
            pOptPar(p)
            with let:
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                pExprColonEqExprList(p, TokKind.tkParRi)
            else:
                pListEnd(p, TokKind.tkParRi)
            m3.discardUnused()
            pOptPar(p)
            expect(p, TokKind.tkParRi)
            wrapAt(p, anchor, NiflerKind.CallL, at1)
            with let:
                m = anchor
            callOrObjConstr(p, m)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
            with var:
                at4 = p.info()
            expect(p, TokKind.tkBracketLe)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
                with let:
                    m5 = p.mark()
                pFlexComment(p)
                m5.discardUnused()
            pOptPar(p)
            with let:
                m6 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                pExprColonEqExprList(p, TokKind.tkBracketRi)
            else:
                pListEnd(p, TokKind.tkBracketRi)
            m6.discardUnused()
            pOptPar(p)
            expect(p, TokKind.tkBracketRi)
            wrapAt(p, anchor, NiflerKind.AtL, at4)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
            with var:
                at7 = p.info()
            expect(p, TokKind.tkCurlyLe)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
                with let:
                    m8 = p.mark()
                pFlexComment(p)
                m8.discardUnused()
            pOptPar(p)
            with let:
                m9 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                pExprColonEqExprList(p, TokKind.tkCurlyRi)
            else:
                pListEnd(p, TokKind.tkCurlyRi)
            m9.discardUnused()
            pOptPar(p)
            expect(p, TokKind.tkCurlyRi)
            wrapAt(p, anchor, NiflerKind.CurlyatL, at7)
        else:
            ruleError(p, string("primarySuffix"), False)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDot):
        with var:
            at10 = p.info()
        expect(p, TokKind.tkDot)
        pOptInd(p)
        pSymbolOrKeyword(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkBracketLeColon) and p.noSpaceBefore():
            with let:
                m11 = p.mark()
            expect(p, TokKind.tkBracketLeColon)
            pExprList(p)
            expect(p, TokKind.tkBracketRi)
            wrap(p, m11, NiflerKind.AtL)
            pPosMarker(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkParLe) and p.noSpaceBefore():
                with let:
                    m12 = p.mark()
                expect(p, TokKind.tkParLe)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
                    with let:
                        m13 = p.mark()
                    pFlexComment(p)
                    m13.discardUnused()
                pOptPar(p)
                with let:
                    m14 = p.mark()
                if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                    pExprColonEqExprList(p, TokKind.tkParRi)
                else:
                    pListEnd(p, TokKind.tkParRi)
                m14.discardUnused()
                pOptPar(p)
                expect(p, TokKind.tkParRi)
                m12.discardUnused()
            m11.discardUnused()
        wrapAt(p, anchor, NiflerKind.DotL, at10)
        with let:
            m = anchor
        dotLayout(p, m)
    elif p.tok.kind == TokKind.tkOpr and p.tok.isDotLike() and p.dotLikeOps():
        with var:
            at15 = p.info()
        emitLeaf(p)
        pOptInd(p)
        pSymbolOrKeyword(p)
        wrapAt(p, anchor, NiflerKind.DotL, at15)
    elif p.tok.kind in Tset[TokKind](TokKind.tkGStrLit, TokKind.tkGTripleStrLit):
        with var:
            at16 = p.info()
        pGeneralizedLit(p)
        wrapAt(p, anchor, NiflerKind.CallstrlitL, at16)
    else:
        ruleError(p, string("primarySuffix"), False)
    m0.discardUnused()


def pCommandSuffix(p: mut @ Parser, anchor: Mark, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    with var:
        at1 = p.info()
    pCommandParam(p, mode)
    wrapAt(p, anchor, NiflerKind.CmdL, at1)
    m0.discardUnused()


def pPragma(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.inPragma += 1
    expect(p, TokKind.tkCurlyDotLe)
    pOptInd(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
        with let:
            m1 = p.mark()
        pExprColonEqExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkComma):
            with let:
                m2 = p.mark()
            pComma(p)
            m2.discardUnused()
        m1.discardUnused()
    pListEnd(p, TokKind.tkCurlyDotRi)
    pOptPar(p)
    with let:
        m3 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotRi):
        expect(p, TokKind.tkCurlyDotRi)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyRi):
        expect(p, TokKind.tkCurlyRi)
    else:
        ruleError(p, string("pragma"), False)
    m3.discardUnused()
    p.inPragma -= 1
    wrap(p, m0, NiflerKind.PragmasL)
    m0.discardUnused()


def pExportMarker(p: mut @ Parser):
    with let:
        m0 = p.mark()
    emitLeaf(p)
    with let:
        m = m0
    p.setExportMarker(m)
    m0.discardUnused()


def pIdentVis(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pPlainSymbol(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkOpr):
        with let:
            m1 = p.mark()
        pExportMarker(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    m0.discardUnused()


def pIdentVisDot(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pPlainSymbol(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkOpr):
            pExportMarker(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDot):
            with var:
                at1 = m0.info
            at1 = p.info()
            expect(p, TokKind.tkDot)
            pOptInd(p)
            pSymbolOrKeyword(p)
            wrapAt(p, m0, NiflerKind.DotL, at1)
            p.emitEmpty()
        elif False:
            p.emitEmpty()
        else:
            p.emitEmpty()
    else:
        ruleError(p, string("identVisDot"), False)
    m0.discardUnused()


def pIdentWithPragma(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentVis(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        with let:
            m1 = p.mark()
        pPragma(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    m0.discardUnused()


def pIdentWithPragmaDot(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentVisDot(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        with let:
            m1 = p.mark()
        pPragma(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    m0.discardUnused()


def pParamColonEquals(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentWithPragma(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        pIdentWithPragma(p)
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m2 = p.mark()
        pComma(p)
        m2.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        with let:
            m3 = p.mark()
        expect(p, TokKind.tkColon)
        pOptInd(p)
        pTypeDescExpr(p)
        m3.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        with let:
            m4 = p.mark()
        expect(p, TokKind.tkEquals)
        pOptInd(p)
        pExpr(p)
        m4.discardUnused()
    else:
        p.emitEmpty()
    with let:
        m = m0
    fanOut(p, m)
    m0.discardUnused()


def pDeclColonEquals(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentWithPragma(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        pIdentWithPragma(p)
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m2 = p.mark()
        pComma(p)
        m2.discardUnused()
    with let:
        m3 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        expect(p, TokKind.tkColon)
        pOptInd(p)
        pTypeDescExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with let:
                m4 = p.mark()
            expect(p, TokKind.tkEquals)
            pOptInd(p)
            pExpr(p)
            m4.discardUnused()
        else:
            p.emitEmpty()
    elif p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        p.emitEmpty()
        expect(p, TokKind.tkEquals)
        pOptInd(p)
        pExpr(p)
    else:
        ruleError(p, string("declColonEquals"), False)
    m3.discardUnused()
    with let:
        m = m0
    fanOut(p, m)
    m0.discardUnused()


def pIdentColonEquals(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pPlainSymbol(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        pPlainSymbol(p)
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m2 = p.mark()
        pComma(p)
        m2.discardUnused()
    with let:
        m3 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        expect(p, TokKind.tkColon)
        pOptInd(p)
        pTypeDescExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with let:
                m4 = p.mark()
            expect(p, TokKind.tkEquals)
            pOptInd(p)
            pExpr(p)
            m4.discardUnused()
        else:
            p.emitEmpty()
    elif p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        p.emitEmpty()
        expect(p, TokKind.tkEquals)
        pOptInd(p)
        pExpr(p)
    else:
        ruleError(p, string("identColonEquals"), False)
    m3.discardUnused()
    with let:
        m = m0
    fanOutKv(p, m)
    m0.discardUnused()


def pDeclColonEqualsDot(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentWithPragmaDot(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        pIdentWithPragmaDot(p)
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m2 = p.mark()
        pComma(p)
        m2.discardUnused()
    with let:
        m3 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        expect(p, TokKind.tkColon)
        pOptInd(p)
        pTypeDescExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with let:
                m4 = p.mark()
            expect(p, TokKind.tkEquals)
            pOptInd(p)
            pExprBlocks(p)
            m4.discardUnused()
        else:
            p.emitEmpty()
    elif p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        p.emitEmpty()
        expect(p, TokKind.tkEquals)
        pOptInd(p)
        pExprBlocks(p)
    else:
        ruleError(p, string("declColonEqualsDot"), False)
    m3.discardUnused()
    with let:
        m = m0
    fanOut(p, m)
    m0.discardUnused()


def pTupleTypeBracket(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkBracketLe)
    pOptInd(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        with let:
            m1 = p.mark()
        pIdentColonEquals(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkComma, TokKind.tkSemiColon):
            with let:
                m2 = p.mark()
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkComma):
                pComma(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                pSemicolon(p)
            else:
                ruleError(p, string("tupleTypeBracket"), False)
            m3.discardUnused()
            m2.discardUnused()
        m1.discardUnused()
    pOptPar(p)
    expect(p, TokKind.tkBracketRi)
    m0.discardUnused()


def pTupleType(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkTuple):
        expect(p, TokKind.tkTuple)
        if p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
            pTupleTypeBracket(p)
            wrap(p, m0, NiflerKind.TupleL)
        elif False:
            with var:
                at1 = m0.info
            at1 = p.info()
            wrapAt(p, m0, NiflerKind.TupleL, at1)
        else:
            with var:
                at2 = m0.info
            at2 = p.info()
            wrapAt(p, m0, NiflerKind.TupleL, at2)
    else:
        ruleError(p, string("tupleType"), False)
    m0.discardUnused()


def pTupleDecl(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkTuple):
        expect(p, TokKind.tkTuple)
        if p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
            pTupleTypeBracket(p)
            wrap(p, m0, NiflerKind.TupleL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icGt) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m1 = p.mark()
                pTrailComment(p)
                m1.discardUnused()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icGt):
                with let:
                    m2 = p.mark()
                pushInd(p)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
                    with let:
                        m3 = p.mark()
                    pOptSameInd(p)
                    emitLeaf(p)
                    m3.discardUnused()
                with let:
                    m4 = p.mark()
                pIdentColonEquals(p)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                    with let:
                        m5 = p.mark()
                    pOptPar(p)
                    emitLeaf(p)
                    m5.discardUnused()
                while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icEq):
                    checkInd(p, Tset[IndClass](IndClass.icEq))
                    pIdentColonEquals(p)
                    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                        with let:
                            m6 = p.mark()
                        pOptPar(p)
                        emitLeaf(p)
                        m6.discardUnused()
                if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol) and p.indClass() == IndClass.icGt:
                    indentError(p)
                m4.discardUnused()
                p.popInd()
                m2.discardUnused()
            wrap(p, m0, NiflerKind.TupleL)
        else:
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m7 = p.mark()
                pTrailComment(p)
                m7.discardUnused()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icGt):
                with let:
                    m8 = p.mark()
                pushInd(p)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
                    with let:
                        m9 = p.mark()
                    pOptSameInd(p)
                    emitLeaf(p)
                    m9.discardUnused()
                with let:
                    m10 = p.mark()
                pIdentColonEquals(p)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                    with let:
                        m11 = p.mark()
                    pOptPar(p)
                    emitLeaf(p)
                    m11.discardUnused()
                while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icEq):
                    checkInd(p, Tset[IndClass](IndClass.icEq))
                    pIdentColonEquals(p)
                    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                        with let:
                            m12 = p.mark()
                        pOptPar(p)
                        emitLeaf(p)
                        m12.discardUnused()
                if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol) and p.indClass() == IndClass.icGt:
                    indentError(p)
                m10.discardUnused()
                p.popInd()
                m8.discardUnused()
            wrap(p, m0, NiflerKind.TupleL)
    else:
        ruleError(p, string("tupleDecl"), False)
    m0.discardUnused()


def pParamList(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.pushSection(NiflerKind.ParamL)
    expect(p, TokKind.tkParLe)
    pOptInd(p)
    pParamStart(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        with let:
            m1 = p.mark()
        pParamColonEquals(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkComma, TokKind.tkSemiColon):
            with let:
                m2 = p.mark()
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkComma):
                pComma(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                pSemicolon(p)
            else:
                ruleError(p, string("paramList"), False)
            m3.discardUnused()
            pParamStart(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
                with let:
                    m4 = p.mark()
                pParamColonEquals(p)
                m4.discardUnused()
            m2.discardUnused()
        m1.discardUnused()
    pOptPar(p)
    expect(p, TokKind.tkParRi)
    p.popSection()
    wrap(p, m0, NiflerKind.ParamsL)
    m0.discardUnused()


def pDoBlock(p: mut @ Parser, atBody: bool):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkDo)
    pPosMarker(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkParLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        pParamList(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind == TokKind.tkOpr and p.tok.s == "->" and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m2 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        expect(p, TokKind.tkOpr, string("->"))
        pOptInd(p)
        pTypeDesc(p)
        m2.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        with let:
            m3 = p.mark()
        pPragma(p)
        m3.discardUnused()
    else:
        p.emitEmpty()
    pColcom(p)
    pStmt(p)
    pPosMarker(p)
    with let:
        m = m0
    doLayout(p, m, atBody)
    m0.discardUnused()


def pRoutineSig(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkParLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        pParamList(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m2 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        expect(p, TokKind.tkColon)
        pOptInd(p)
        pTypeDesc(p)
        m2.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m3 = p.mark()
        pValidInd(p)
        pPragma(p)
        m3.discardUnused()
    else:
        p.emitEmpty()
    m0.discardUnused()


def pRoutineExpr(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkProc):
        with var:
            at1 = m0.info
        expect(p, TokKind.tkProc)
        at1 = p.info()
        pRoutineSig(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals) and p.routineBodyAllowed(mode):
            with let:
                m2 = p.mark()
            expect(p, TokKind.tkEquals)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m3 = p.mark()
                pTrailComment(p)
                m3.discardUnused()
            pStmt(p)
            m2.discardUnused()
        else:
            p.emitEmpty()
        with let:
            m = Mark(prev=m0.prev, info=at1, sigs=m0.sigs)
        procLayout(p, m, NiflerKind.ProcL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFunc):
        with var:
            at4 = m0.info
        expect(p, TokKind.tkFunc)
        at4 = p.info()
        pRoutineSig(p)
        with let:
            m5 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals) and p.routineBodyAllowed(mode):
            expect(p, TokKind.tkEquals)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m6 = p.mark()
                pTrailComment(p)
                m6.discardUnused()
            pStmt(p)
        elif False:
            p.emitEmpty()
            pFuncType(p)
        else:
            p.emitEmpty()
            pFuncType(p)
        m5.discardUnused()
        with let:
            m = Mark(prev=m0.prev, info=at4, sigs=m0.sigs)
        procLayout(p, m, NiflerKind.FuncL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIterator):
        with var:
            at7 = m0.info
        expect(p, TokKind.tkIterator)
        at7 = p.info()
        pRoutineSig(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals) and p.routineBodyAllowed(mode):
            with let:
                m8 = p.mark()
            expect(p, TokKind.tkEquals)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m9 = p.mark()
                pTrailComment(p)
                m9.discardUnused()
            pStmt(p)
            m8.discardUnused()
        else:
            p.emitEmpty()
        with let:
            m = Mark(prev=m0.prev, info=at7, sigs=m0.sigs)
        procLayout(p, m, NiflerKind.IteratorL)
    else:
        ruleError(p, string("routineExpr"), False)
    m0.discardUnused()


def pFuncType(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    p.funcType()
    m0.discardUnused()


def pRoutineType(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkProc):
        with var:
            at1 = m0.info
        expect(p, TokKind.tkProc)
        at1 = p.info()
        pRoutineSig(p)
        p.emitEmpty()
        with let:
            m = Mark(prev=m0.prev, info=at1, sigs=m0.sigs)
        procLayout(p, m, NiflerKind.ProcL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIterator):
        with var:
            at2 = m0.info
        expect(p, TokKind.tkIterator)
        at2 = p.info()
        pRoutineSig(p)
        p.emitEmpty()
        with let:
            m = Mark(prev=m0.prev, info=at2, sigs=m0.sigs)
        procLayout(p, m, NiflerKind.IteratorL)
    else:
        ruleError(p, string("routineType"), False)
    m0.discardUnused()


def pRawTypeDesc(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkIterator, TokKind.tkProc):
        pRoutineType(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkNot) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m1 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icNoInd))
            with var:
                at2 = p.info()
            insertTokAt(p, m0, TokKind.tkNot)
            pPrimary(p, PrimaryMode.pmTypeDesc)
            at2 = p.info()
            wrapAt(p, m0, NiflerKind.InfixL, at2)
            m1.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkDistinct, TokKind.tkEnum, TokKind.tkObject, TokKind.tkOut, TokKind.tkPtr, TokKind.tkRef, TokKind.tkTuple, TokKind.tkVar):
        pTypeDescKeyw(p, PrimaryMode.pmTypeDesc)
    else:
        ruleError(p, string("rawTypeDesc"), False)
    m0.discardUnused()


def pTypeDescKeyw(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkTuple):
        pTupleType(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkEnum):
        expectLeaf(p, TokKind.tkEnum)
    elif p.tok.kind in Tset[TokKind](TokKind.tkObject):
        expect(p, TokKind.tkObject)
        wrap(p, m1, NiflerKind.ObjectL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkVar):
        expect(p, TokKind.tkVar)
        if canTypeKAuxOperand(p, mode):
            with let:
                m2 = p.mark()
            pTypeKAuxOperand(p, mode)
            m2.discardUnused()
        wrap(p, m1, NiflerKind.MutL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOut):
        expect(p, TokKind.tkOut)
        if canTypeKAuxOperand(p, mode):
            with let:
                m3 = p.mark()
            pTypeKAuxOperand(p, mode)
            m3.discardUnused()
        wrap(p, m1, NiflerKind.OutL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkRef):
        expect(p, TokKind.tkRef)
        if canTypeKAuxOperand(p, mode):
            with let:
                m4 = p.mark()
            pTypeKAuxOperand(p, mode)
            m4.discardUnused()
        wrap(p, m1, NiflerKind.RefL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkPtr):
        expect(p, TokKind.tkPtr)
        if canTypeKAuxOperand(p, mode):
            with let:
                m5 = p.mark()
            pTypeKAuxOperand(p, mode)
            m5.discardUnused()
        wrap(p, m1, NiflerKind.PtrL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDistinct):
        expect(p, TokKind.tkDistinct)
        if canTypeKAuxOperand(p, mode):
            with let:
                m6 = p.mark()
            pTypeKAuxOperand(p, mode)
            m6.discardUnused()
        wrap(p, m1, NiflerKind.DistinctL)
    else:
        ruleError(p, string("typeDescKeyw"), False)
    m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkNot) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m7 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        with var:
            at8 = p.info()
        insertTokAt(p, m0, TokKind.tkNot)
        pPrimary(p, PrimaryMode.pmTypeDesc)
        at8 = p.info()
        wrapAt(p, m0, NiflerKind.InfixL, at8)
        m7.discardUnused()
    m0.discardUnused()


def pTypeKAuxOperand(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkConcept, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt) and p.isTypedefOperand(mode):
        pValidInd(p)
        pTypeDefValue(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt) and p.typeOperandFollows():
        pValidInd(p)
        pPrimary(p, mode)
    else:
        ruleError(p, string("typeKAuxOperand"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkConcept, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.indClass() not in Tset[IndClass](IndClass.icNoInd, IndClass.icGt))
    m0.discardUnused()


def pTypeDescExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pSimpleExpr(p, -1, PrimaryMode.pmTypeDesc)
    if p.tok.kind in Tset[TokKind](TokKind.tkNot) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        with var:
            at2 = p.info()
        insertTokAt(p, m0, TokKind.tkNot)
        pPrimary(p, PrimaryMode.pmTypeDesc)
        at2 = p.info()
        wrapAt(p, m0, NiflerKind.InfixL, at2)
        m1.discardUnused()
    m0.discardUnused()


def pTypeDesc(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkDistinct, TokKind.tkEnum, TokKind.tkIterator, TokKind.tkObject, TokKind.tkOut, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRef, TokKind.tkTuple, TokKind.tkVar):
        pRawTypeDesc(p)
    else:
        pTypeDescExpr(p)
    m0.discardUnused()


def pForVar(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentWithPragma(p)
    p.emitEmpty()
    p.emitEmpty()
    with let:
        m = m0
    wrapNoInfo(p, m, NiflerKind.LetL)
    m0.discardUnused()


def pForTupleVar(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pPlainSymbol(p)
    p.emitEmpty()
    p.emitEmpty()
    p.emitEmpty()
    p.emitEmpty()
    with let:
        m = m0
    wrapNoInfo(p, m, NiflerKind.LetL)
    m0.discardUnused()


def pForTuple(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkParLe)
    pOptInd(p)
    pForTupleVar(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
            with let:
                m2 = p.mark()
            pForTupleVar(p)
            m2.discardUnused()
        m1.discardUnused()
    pOptPar(p)
    expect(p, TokKind.tkParRi)
    wrap(p, m0, NiflerKind.UnpacktupL)
    m0.discardUnused()


def pForHead(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        pForTuple(p)
        expect(p, TokKind.tkIn)
        pExpr(p)
        with let:
            m = m0
        p.moveLastToMark(m)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pForVar(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkComma):
            with let:
                m1 = p.mark()
            pComma(p)
            with let:
                m2 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
                pForVar(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
                pForTuple(p)
            else:
                ruleError(p, string("forHead"), False)
            m2.discardUnused()
            m1.discardUnused()
        wrap(p, m0, NiflerKind.UnpackflatL)
        expect(p, TokKind.tkIn)
        pExpr(p)
        with let:
            m = m0
        p.moveLastToMark(m)
    else:
        ruleError(p, string("forHead"), False)
    m0.discardUnused()


def pForStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    with var:
        at1 = m0.info
    expect(p, TokKind.tkFor)
    at1 = p.info()
    pForHead(p)
    pColcom(p)
    pStmt(p)
    wrapAt(p, m0, NiflerKind.ForL, at1)
    m0.discardUnused()


def pForExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pForStmt(p)
    m0.discardUnused()


def pExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkBlock, TokKind.tkCase, TokKind.tkFor, TokKind.tkIf, TokKind.tkTry, TokKind.tkWhen):
        with let:
            m1 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkBlock):
            pBlockExpr(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkIf):
            pIfExpr(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkWhen):
            pWhenExpr(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCase):
            pCaseStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkFor):
            pForExpr(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkTry):
            pTryExpr(p)
        else:
            ruleError(p, string("expr"), False)
        m1.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor):
        pSimpleExpr(p, -1, PrimaryMode.pmNormal)
    else:
        ruleError(p, string("expr"), False)
    m0.discardUnused()


def pSimplePrimary(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    pIdentOrLiteral(p, mode)
    while canPrimarySuffix(p, mode) and p.suffixStart():
        with let:
            m1 = p.mark()
        pPrimarySuffix(p, m0, mode)
        m1.discardUnused()
    if canCommandSuffix(p, mode) and p.suffixStart():
        with let:
            m2 = p.mark()
        pCommandSuffix(p, m0, mode)
        m2.discardUnused()
    m0.discardUnused()


def pCommandParam(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor) and p.inTypeDesc(mode):
        pSimpleExpr(p, -1, mode)
    else:
        pExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m1 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icNoInd))
            pDoBlock(p, True)
            while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                with let:
                    m2 = p.mark()
                pExtraPostExprBlock(p)
                m2.discardUnused()
            m1.discardUnused()
        with let:
            m = m0
        attachBlocks(p, m)
    m0.discardUnused()


def pPrimary(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkParLe, TokKind.tkRStrLit, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
        pSimplePrimary(p, mode)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAnd, TokKind.tkAs, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkFrom, TokKind.tkIn, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkMod, TokKind.tkNot, TokKind.tkNotin, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkShl, TokKind.tkShr, TokKind.tkXor) and p.isSigilLike():
        pPrefixOperator(p)
        with let:
            m1 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkParLe, TokKind.tkRStrLit, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
            pIdentOrLiteral(p, mode)
        else:
            pPrimary(p, PrimaryMode.pmNormal)
        m1.discardUnused()
        wrap(p, m0, NiflerKind.PrefixL)
        while canPrimarySuffix(p, mode) and p.suffixStart():
            with let:
                m2 = p.mark()
            pPrimarySuffix(p, m0, mode)
            m2.discardUnused()
        if canCommandSuffix(p, mode) and p.suffixStart():
            with let:
                m3 = p.mark()
            pCommandSuffix(p, m0, mode)
            m3.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAnd, TokKind.tkAs, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkFrom, TokKind.tkIn, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkMod, TokKind.tkNot, TokKind.tkNotin, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkShl, TokKind.tkShr, TokKind.tkXor) and p.isUnary():
        pOperatorB(p)
        pPrimary(p, mode)
        wrap(p, m0, NiflerKind.PrefixL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFunc, TokKind.tkIterator, TokKind.tkProc):
        pRoutineExpr(p, mode)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBind):
        expect(p, TokKind.tkBind)
        pOptInd(p)
        pPrimary(p, PrimaryMode.pmNormal)
        wrap(p, m0, NiflerKind.BindL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDistinct, TokKind.tkEnum, TokKind.tkObject, TokKind.tkOut, TokKind.tkPtr, TokKind.tkRef, TokKind.tkTuple, TokKind.tkVar):
        pTypeDescKeyw(p, mode)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAnd, TokKind.tkAs, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkFrom, TokKind.tkIn, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkMod, TokKind.tkNot, TokKind.tkNotin, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkShl, TokKind.tkShr, TokKind.tkXor):
        pPrefixOperator(p)
        pPrimary(p, mode)
        wrap(p, m0, NiflerKind.PrefixL)
    else:
        ruleError(p, string("primary"), False)
    m0.discardUnused()


def pSimpleExpr(p: mut @ Parser, limit: nint, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    pPrimaryPragma(p, mode)
    with var:
        prec = p.getPrecedence()
    while prec >= limit and p.indClass() == IndClass.icNoInd:
        with var:
            assoc = 1
        if p.isRightAssoc():
            assoc = 0
        with let:
            opInfo = p.info()
        p.insertOpLeafAt(m0)
        p.getTok()
        afterOperator(p)
        pSimpleExpr(p, prec + assoc, mode.rhsMode())
        wrapAt(p, m0, NiflerKind.InfixL, opInfo)
        prec = p.getPrecedence()
    m0.discardUnused()


def pPrimaryPragma(p: mut @ Parser, mode: PrimaryMode):
    with let:
        m0 = p.mark()
    pPrimary(p, mode)
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt) and p.pragmaOnPrimary(mode):
        with let:
            m1 = p.mark()
        pValidInd(p)
        with var:
            at2 = p.info()
        pPragma(p)
        wrapAt(p, m0, NiflerKind.PragmaxL, at2)
        m1.discardUnused()
    m0.discardUnused()


def pExtraPostExprBlock(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
        checkInd(p, Tset[IndClass](IndClass.icEq))
        if p.tok.kind in Tset[TokKind](TokKind.tkDo):
            pDoBlock(p, False)
        elif p.tok.kind in Tset[TokKind](TokKind.tkOf):
            expect(p, TokKind.tkOf)
            pExprList(p)
            wrap(p, m0, NiflerKind.RangesL)
            expect(p, TokKind.tkColon)
            pStmt(p)
            wrap(p, m0, NiflerKind.OfL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkElif):
            expect(p, TokKind.tkElif)
            pExpr(p)
            expect(p, TokKind.tkColon)
            pStmt(p)
            wrap(p, m0, NiflerKind.ElifL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkExcept):
            expect(p, TokKind.tkExcept)
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                with let:
                    m1 = p.mark()
                    m2 = p.mark()
                pExpr(p)
                while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                    pComma(p)
                    pExpr(p)
                m2.discardUnused()
                m1.discardUnused()
            else:
                p.emitEmpty()
            expect(p, TokKind.tkColon)
            pStmt(p)
            wrap(p, m0, NiflerKind.ExceptL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkFinally):
            expect(p, TokKind.tkFinally)
            expect(p, TokKind.tkColon)
            pStmt(p)
            wrap(p, m0, NiflerKind.FinL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkElse):
            expect(p, TokKind.tkElse)
            expect(p, TokKind.tkColon)
            pStmt(p)
            wrap(p, m0, NiflerKind.ElseL)
        else:
            ruleError(p, string("extraPostExprBlock"), False)
    else:
        ruleError(p, string("extraPostExprBlock"), p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icGt) or p.indClass() not in Tset[IndClass](IndClass.icEq))
    m0.discardUnused()


def pPostExprBlocks(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        if p.tok.kind in Tset[TokKind](TokKind.tkDo):
            pDoBlock(p, True)
            while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                with let:
                    m1 = p.mark()
                pExtraPostExprBlock(p)
                m1.discardUnused()
        elif p.tok.kind in Tset[TokKind](TokKind.tkColon):
            expect(p, TokKind.tkColon)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m2 = p.mark()
                pTrailComment(p)
                m2.discardUnused()
            with let:
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                pExtraPostExprBlock(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkAsm, TokKind.tkBlock, TokKind.tkCase, TokKind.tkConst, TokKind.tkConverter, TokKind.tkDefer, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkFor, TokKind.tkIf, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkTemplate, TokKind.tkTry, TokKind.tkUsing, TokKind.tkWhen, TokKind.tkWhile) and p.indClass() in Tset[IndClass](IndClass.icGt) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExport, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor, TokKind.tkYield):
                pStmt(p)
            else:
                ruleError(p, string("postExprBlocks"), p.tok.kind in Tset[TokKind](TokKind.tkExcept, TokKind.tkFinally) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt) or p.tok.kind in Tset[TokKind](TokKind.tkAsm, TokKind.tkBlock, TokKind.tkCase, TokKind.tkConst, TokKind.tkConverter, TokKind.tkDefer, TokKind.tkFor, TokKind.tkIf, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkTemplate, TokKind.tkTry, TokKind.tkUsing, TokKind.tkWhen, TokKind.tkWhile) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icGt))
            m3.discardUnused()
            while p.tok.kind in Tset[TokKind](TokKind.tkDo, TokKind.tkElif, TokKind.tkElse, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
                with let:
                    m4 = p.mark()
                pExtraPostExprBlock(p)
                m4.discardUnused()
        else:
            ruleError(p, string("postExprBlocks"), False)
    else:
        ruleError(p, string("postExprBlocks"), p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq, IndClass.icGt) or p.indClass() not in Tset[IndClass](IndClass.icNoInd))
    m0.discardUnused()


def pExprBlocks(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pExpr(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pPostExprBlocks(p)
        m1.discardUnused()
    with let:
        m = m0
    attachBlocks(p, m)
    m0.discardUnused()


def pExprStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor):
        pSimpleExpr(p, -1, PrimaryMode.pmTrySimple)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with var:
                at1 = m0.info
            at1 = p.info()
            expect(p, TokKind.tkEquals)
            pOptInd(p)
            pExprBlocks(p)
            wrapAt(p, m0, NiflerKind.AsgnL, at1)
        elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            checkInd(p, Tset[IndClass](IndClass.icNoInd))
            with let:
                m2 = p.mark()
            pExprEqExpr(p)
            while p.tok.kind in Tset[TokKind](TokKind.tkComma) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                pOptPar(p)
                pComma(p)
                pOptInd(p)
                pExprEqExpr(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkComma) and p.indClass() == IndClass.icGt:
                indentError(p)
            m2.discardUnused()
            if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m3 = p.mark()
                pPostExprBlocks(p)
                m3.discardUnused()
            with let:
                m = m0
            wrapLikeFirst(p, m, NiflerKind.CmdL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m4 = p.mark()
                pPostExprBlocks(p)
                m4.discardUnused()
            with let:
                m = m0
            attachBlocks(p, m)
        else:
            if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m5 = p.mark()
                pPostExprBlocks(p)
                m5.discardUnused()
            with let:
                m = m0
            attachBlocks(p, m)
    else:
        ruleError(p, string("exprStmt"), False)
    m0.discardUnused()


def pImportStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkImport):
        expect(p, TokKind.tkImport)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            pOptInd(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                pExpr(p)
                if p.tok.kind in Tset[TokKind](TokKind.tkComma):
                    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        with let:
                            m1 = p.mark()
                        pComma(p)
                        pExpr(p)
                        m1.discardUnused()
                    wrap(p, m0, NiflerKind.ImportL)
                elif p.tok.kind in Tset[TokKind](TokKind.tkExcept):
                    expect(p, TokKind.tkExcept)
                    pOptInd(p)
                    with let:
                        m2 = p.mark()
                    pExpr(p)
                    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        pComma(p)
                        pExpr(p)
                    m2.discardUnused()
                    wrap(p, m0, NiflerKind.ImportexceptL)
                else:
                    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        with let:
                            m3 = p.mark()
                        pComma(p)
                        pExpr(p)
                        m3.discardUnused()
                    wrap(p, m0, NiflerKind.ImportL)
            else:
                ruleError(p, string("importStmt"), False)
        else:
            ruleError(p, string("importStmt"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq, IndClass.icGt) or p.indClass() not in Tset[IndClass](IndClass.icNoInd, IndClass.icGt))
    else:
        ruleError(p, string("importStmt"), False)
    m0.discardUnused()


def pExportStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkExport):
        expect(p, TokKind.tkExport)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            pOptInd(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                pExpr(p)
                if p.tok.kind in Tset[TokKind](TokKind.tkComma):
                    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        with let:
                            m1 = p.mark()
                        pComma(p)
                        pExpr(p)
                        m1.discardUnused()
                    wrap(p, m0, NiflerKind.ExportL)
                elif p.tok.kind in Tset[TokKind](TokKind.tkExcept):
                    expect(p, TokKind.tkExcept)
                    pOptInd(p)
                    with let:
                        m2 = p.mark()
                    pExpr(p)
                    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        pComma(p)
                        pExpr(p)
                    m2.discardUnused()
                    wrap(p, m0, NiflerKind.ExportexceptL)
                else:
                    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                        with let:
                            m3 = p.mark()
                        pComma(p)
                        pExpr(p)
                        m3.discardUnused()
                    wrap(p, m0, NiflerKind.ExportL)
            else:
                ruleError(p, string("exportStmt"), False)
        else:
            ruleError(p, string("exportStmt"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq, IndClass.icGt) or p.indClass() not in Tset[IndClass](IndClass.icNoInd, IndClass.icGt))
    else:
        ruleError(p, string("exportStmt"), False)
    m0.discardUnused()


def pIncludeStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkInclude)
    pOptInd(p)
    with let:
        m1 = p.mark()
    pExpr(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        pComma(p)
        pExpr(p)
    m1.discardUnused()
    wrap(p, m0, NiflerKind.IncludeL)
    m0.discardUnused()


def pFromStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkFrom)
    pExpr(p)
    expect(p, TokKind.tkImport)
    pOptInd(p)
    pExpr(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        pExpr(p)
        m1.discardUnused()
    wrap(p, m0, NiflerKind.FromimportL)
    m0.discardUnused()


def pOptExprBody(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        emitLeaf(p)
        p.emitEmpty()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        pValidInd(p)
        pExprBlocks(p)
    else:
        ruleError(p, string("optExprBody"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq, IndClass.icGt) or p.indClass() not in Tset[IndClass](IndClass.icNoInd, IndClass.icGt))
    m0.discardUnused()


def pReturnStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkReturn)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pOptExprBody(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    wrap(p, m0, NiflerKind.RetL)
    m0.discardUnused()


def pRaiseStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkRaise)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pOptExprBody(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    wrap(p, m0, NiflerKind.RaiseL)
    m0.discardUnused()


def pYieldStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkYield)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pOptExprBody(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    wrap(p, m0, NiflerKind.YldL)
    m0.discardUnused()


def pDiscardStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkDiscard)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pOptExprBody(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    wrap(p, m0, NiflerKind.DiscardL)
    m0.discardUnused()


def pBreakStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkBreak)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pOptExprBody(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    wrap(p, m0, NiflerKind.BreakL)
    m0.discardUnused()


def pContinueStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkContinue)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pOptExprBody(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    wrap(p, m0, NiflerKind.ContinueL)
    m0.discardUnused()


def pCondStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pExpr(p)
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.ElifL)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    while p.tok.kind in Tset[TokKind](TokKind.tkElif) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
        with let:
            m2 = p.mark()
        with var:
            at3 = m2.info
        pOptSameInd(p)
        expect(p, TokKind.tkElif)
        at3 = p.info()
        pExpr(p)
        pColcom(p)
        pStmt(p)
        wrapAt(p, m2, NiflerKind.ElifL, at3)
        m2.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkElse) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
        with let:
            m4 = p.mark()
        pOptSameInd(p)
        expect(p, TokKind.tkElse)
        pColcom(p)
        pStmt(p)
        wrap(p, m4, NiflerKind.ElseL)
        m4.discardUnused()
    m0.discardUnused()


def pIfStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkIf)
    pCondStmt(p)
    wrap(p, m0, NiflerKind.IfL)
    m0.discardUnused()


def pWhenStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkWhen)
    pCondStmt(p)
    wrap(p, m0, NiflerKind.WhenL)
    m0.discardUnused()


def pCondExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pOptInd(p)
    pExpr(p)
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.ElifL)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    while p.tok.kind in Tset[TokKind](TokKind.tkElif):
        with let:
            m2 = p.mark()
        with var:
            at3 = m2.info
        expect(p, TokKind.tkElif)
        at3 = p.info()
        pOptInd(p)
        pExpr(p)
        pColcom(p)
        pStmt(p)
        wrapAt(p, m2, NiflerKind.ElifL, at3)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m4 = p.mark()
            pTrailComment(p)
            m4.discardUnused()
        m2.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkElse):
        with let:
            m5 = p.mark()
        expect(p, TokKind.tkElse)
        pColcom(p)
        pStmt(p)
        wrap(p, m5, NiflerKind.ElseL)
        m5.discardUnused()
    m0.discardUnused()


def pIfExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkIf)
    pCondExpr(p)
    wrap(p, m0, NiflerKind.IfL)
    m0.discardUnused()


def pWhenExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkWhen)
    pCondExpr(p)
    wrap(p, m0, NiflerKind.WhenL)
    m0.discardUnused()


def pWhileStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkWhile)
    pExpr(p)
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.WhileL)
    m0.discardUnused()


def pOfBranch(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkOf)
    pExprList(p)
    wrap(p, m0, NiflerKind.RangesL)
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.OfL)
    m0.discardUnused()


def pOfBranches(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkOf):
        pOfBranch(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
            with let:
                m1 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icEq))
            pOfBranch(p)
            m1.discardUnused()
        while p.tok.kind in Tset[TokKind](TokKind.tkElif) and p.indClass() in Tset[IndClass](IndClass.icEq):
            with let:
                m2 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icEq))
            expect(p, TokKind.tkElif)
            pExpr(p)
            pColcom(p)
            pStmt(p)
            wrap(p, m2, NiflerKind.ElifL)
            m2.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkElse) and p.indClass() in Tset[IndClass](IndClass.icEq):
            with let:
                m3 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icEq))
            expect(p, TokKind.tkElse)
            pColcom(p)
            pStmt(p)
            wrap(p, m3, NiflerKind.ElseL)
            m3.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkElif):
        with let:
            m4 = p.mark()
        expect(p, TokKind.tkElif)
        pExpr(p)
        pColcom(p)
        pStmt(p)
        wrap(p, m4, NiflerKind.ElifL)
        m4.discardUnused()
        while p.tok.kind in Tset[TokKind](TokKind.tkElif):
            with let:
                m5 = p.mark()
            expect(p, TokKind.tkElif)
            pExpr(p)
            pColcom(p)
            pStmt(p)
            wrap(p, m5, NiflerKind.ElifL)
            m5.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkElse) and p.indClass() in Tset[IndClass](IndClass.icEq):
            with let:
                m6 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icEq))
            expect(p, TokKind.tkElse)
            pColcom(p)
            pStmt(p)
            wrap(p, m6, NiflerKind.ElseL)
            m6.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkElse):
        expect(p, TokKind.tkElse)
        pColcom(p)
        pStmt(p)
        wrap(p, m0, NiflerKind.ElseL)
    else:
        ruleError(p, string("ofBranches"), False)
    m0.discardUnused()


def pCaseStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkCase)
    pExpr(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        with let:
            m1 = p.mark()
        expect(p, TokKind.tkColon)
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m2 = p.mark()
        pTrailComment(p)
        m2.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkElif, TokKind.tkElse, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq, IndClass.icGt):
        with let:
            m3 = p.mark()
            m4 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkElif, TokKind.tkElse, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icGt):
            pushInd(p)
            pOfBranches(p)
            p.popInd()
        elif p.tok.kind in Tset[TokKind](TokKind.tkElif, TokKind.tkElse, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
            checkInd(p, Tset[IndClass](IndClass.icEq))
            pOfBranches(p)
        else:
            ruleError(p, string("caseStmt"), p.tok.kind in Tset[TokKind](TokKind.tkElif, TokKind.tkElse, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt))
        m4.discardUnused()
        m3.discardUnused()
    wrap(p, m0, NiflerKind.CaseL)
    m0.discardUnused()


def pTryStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkTry)
    pColcom(p)
    pStmt(p)
    pTryBranches(p)
    wrap(p, m0, NiflerKind.TryL)
    m0.discardUnused()


def pTryBranches(p: mut @ Parser):
    with let:
        m0 = p.mark()
    while p.tok.kind in Tset[TokKind](TokKind.tkExcept, TokKind.tkFinally) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
        with let:
            m1 = p.mark()
        pOptSameInd(p)
        with let:
            m2 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkExcept):
            expect(p, TokKind.tkExcept)
            with let:
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                with let:
                    m4 = p.mark()
                pExpr(p)
                while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                    pComma(p)
                    pExpr(p)
                m4.discardUnused()
            elif False:
                p.emitEmpty()
                pListEnd(p, TokKind.tkColon)
            else:
                p.emitEmpty()
                pListEnd(p, TokKind.tkColon)
            m3.discardUnused()
            pColcom(p)
            pStmt(p)
            wrap(p, m2, NiflerKind.ExceptL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkFinally):
            expect(p, TokKind.tkFinally)
            pColcom(p)
            pStmt(p)
            wrap(p, m2, NiflerKind.FinL)
        else:
            ruleError(p, string("tryBranches"), False)
        m2.discardUnused()
        m1.discardUnused()
    with let:
        m = m0
    p.requireExcept(m)
    m0.discardUnused()


def pTryExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkTry)
    pColcom(p)
    pStmt(p)
    pTryExprBranches(p)
    wrap(p, m0, NiflerKind.TryL)
    m0.discardUnused()


def pTryExprBranches(p: mut @ Parser):
    with let:
        m0 = p.mark()
    while p.tok.kind in Tset[TokKind](TokKind.tkExcept, TokKind.tkFinally) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
        with let:
            m1 = p.mark()
        pOptPar(p)
        with let:
            m2 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkExcept):
            expect(p, TokKind.tkExcept)
            with let:
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkIn, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkWhen, TokKind.tkXor):
                with let:
                    m4 = p.mark()
                pExpr(p)
                while p.tok.kind in Tset[TokKind](TokKind.tkComma):
                    pComma(p)
                    pExpr(p)
                m4.discardUnused()
            elif False:
                p.emitEmpty()
                pListEnd(p, TokKind.tkColon)
            else:
                p.emitEmpty()
                pListEnd(p, TokKind.tkColon)
            m3.discardUnused()
            pColcom(p)
            pStmt(p)
            wrap(p, m2, NiflerKind.ExceptL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkFinally):
            expect(p, TokKind.tkFinally)
            pColcom(p)
            pStmt(p)
            wrap(p, m2, NiflerKind.FinL)
        else:
            ruleError(p, string("tryExprBranches"), False)
        m2.discardUnused()
        m1.discardUnused()
    with let:
        m = m0
    p.requireExcept(m)
    m0.discardUnused()


def pBlockStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkBlock)
    pNoIndHere(p)
    with let:
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
        pSymbol(p)
    elif False:
        p.emitEmpty()
        pBlockNameEnd(p)
    else:
        p.emitEmpty()
        pBlockNameEnd(p)
    m1.discardUnused()
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.BlockL)
    m0.discardUnused()


def pBlockExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkBlock)
    pNoIndHere(p)
    with let:
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
        pSymbol(p)
    elif False:
        p.emitEmpty()
        pBlockNameEnd(p)
    else:
        p.emitEmpty()
        pBlockNameEnd(p)
    m1.discardUnused()
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.BlockL)
    m0.discardUnused()


def pNoIndHere(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    noIndHere(p)
    m0.discardUnused()


def pBlockNameEnd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    blockNameEnd(p)
    m0.discardUnused()


def pStaticStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkStatic)
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.StaticstmtL)
    m0.discardUnused()


def pDeferStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkDefer)
    pColcom(p)
    pStmt(p)
    wrap(p, m0, NiflerKind.DeferL)
    m0.discardUnused()


def pAsmStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkAsm)
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        with let:
            m1 = p.mark()
        pPragma(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    with let:
        m2 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkStrLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkRStrLit):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkTripleStrLit):
        emitLeaf(p)
    else:
        ruleError(p, string("asmStmt"), False)
    m2.discardUnused()
    wrap(p, m0, NiflerKind.AsmL)
    m0.discardUnused()


def pGenericParamName(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](inrange(TokKind.tkAddr, TokKind.tkYield)) and p.inOrOut():
        emitLeaf(p)
        pPlainSymbol(p)
        wrap(p, m0, NiflerKind.PrefixL)
        p.emitEmpty()
        p.emitEmpty()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pPlainSymbol(p)
        p.emitEmpty()
        p.emitEmpty()
    else:
        ruleError(p, string("genericParamName"), False)
    m0.discardUnused()


def pGenericParam(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pGenericParamName(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        if canGenericParamName(p):
            with let:
                m2 = p.mark()
            pGenericParamName(p)
            m2.discardUnused()
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        with let:
            m3 = p.mark()
        pColon(p)
        pExpr(p)
        m3.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        with let:
            m4 = p.mark()
        expect(p, TokKind.tkEquals)
        pOptInd(p)
        pExpr(p)
        m4.discardUnused()
    else:
        p.emitEmpty()
    with let:
        m = m0
    fanOut(p, m)
    m0.discardUnused()


def pGenericParamList(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.pushSection(NiflerKind.TypevarL)
    expect(p, TokKind.tkBracketLe)
    pOptInd(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, inrange(TokKind.tkAddr, TokKind.tkYield), TokKind.tkSymbol):
        with let:
            m1 = p.mark()
        pGenericParam(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkComma, TokKind.tkSemiColon):
            with let:
                m2 = p.mark()
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkComma):
                pComma(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                pSemicolon(p)
            else:
                ruleError(p, string("genericParamList"), False)
            m3.discardUnused()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, inrange(TokKind.tkAddr, TokKind.tkYield), TokKind.tkSymbol):
                with let:
                    m4 = p.mark()
                pGenericParam(p)
                m4.discardUnused()
            m2.discardUnused()
        m1.discardUnused()
    pOptPar(p)
    expect(p, TokKind.tkBracketRi)
    p.popSection()
    wrap(p, m0, NiflerKind.TypevarsL)
    m0.discardUnused()


def pPattern(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkCurlyLe)
    pStmt(p)
    expect(p, TokKind.tkCurlyRi)
    m0.discardUnused()


def pIndAndComment(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            with let:
                m2 = p.mark()
            pFlexComment(p)
            m2.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m3 = p.mark()
            pTrailComment(p)
            m3.discardUnused()
    m1.discardUnused()
    m0.discardUnused()


def pRoutineName(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
        pSymbol(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkOpr):
            with let:
                m1 = p.mark()
            pExportMarker(p)
            m1.discardUnused()
        else:
            p.emitEmpty()
    elif p.tok.kind in Tset[TokKind](inrange(TokKind.tkAddr, TokKind.tkYield)):
        identExpected(p)
        emitLeaf(p)
    else:
        ruleError(p, string("routineName"), False)
    m0.discardUnused()


def pRoutine(p: mut @ Parser, kw: NiflerKind):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkComment, TokKind.tkParLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, inrange(TokKind.tkAddr, TokKind.tkYield), TokKind.tkCurlyDotLe, TokKind.tkEquals, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        pOptInd(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, inrange(TokKind.tkAddr, TokKind.tkYield), TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
            pRoutineName(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
                with let:
                    m1 = p.mark()
                pPattern(p)
                m1.discardUnused()
            else:
                p.emitEmpty()
            if p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
                with let:
                    m2 = p.mark()
                pGenericParamList(p)
                m2.discardUnused()
            else:
                p.emitEmpty()
            with let:
                m3 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkParLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                checkInd(p, Tset[IndClass](IndClass.icNoInd))
                pParamList(p)
            elif False:
                with var:
                    at4 = m3.info
                at4 = p.info()
                wrapAt(p, m3, NiflerKind.ParamsL, at4)
            else:
                with var:
                    at5 = m3.info
                at5 = p.info()
                wrapAt(p, m3, NiflerKind.ParamsL, at5)
            m3.discardUnused()
            if p.tok.kind in Tset[TokKind](TokKind.tkColon) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m6 = p.mark()
                checkInd(p, Tset[IndClass](IndClass.icNoInd))
                expect(p, TokKind.tkColon)
                pOptInd(p)
                pTypeDesc(p)
                m6.discardUnused()
            else:
                p.emitEmpty()
            if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
                with let:
                    m7 = p.mark()
                pValidInd(p)
                pPragma(p)
                m7.discardUnused()
            else:
                p.emitEmpty()
            with let:
                m8 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkEquals) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
                pValidInd(p)
                expect(p, TokKind.tkEquals)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                    with let:
                        m9 = p.mark()
                    pTrailComment(p)
                    m9.discardUnused()
                pStmt(p)
            elif False:
                p.emitEmpty()
                pMissingEquals(p)
            else:
                p.emitEmpty()
                pMissingEquals(p)
            m8.discardUnused()
            pIndAndComment(p)
            with let:
                m = m0
            routineLayout(p, m, kw)
        elif p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkParLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd) or p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt) or p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with var:
                at10 = m0.info
            at10 = p.info()
            pRoutineSig(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
                with let:
                    m11 = p.mark()
                expect(p, TokKind.tkEquals)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                    with let:
                        m12 = p.mark()
                    pTrailComment(p)
                    m12.discardUnused()
                pStmt(p)
                m11.discardUnused()
            else:
                p.emitEmpty()
            with let:
                m = Mark(prev=m0.prev, info=at10, sigs=m0.sigs)
            procLayout(p, m, kw)
        else:
            with var:
                at13 = m0.info
            at13 = p.info()
            pRoutineSig(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
                with let:
                    m14 = p.mark()
                expect(p, TokKind.tkEquals)
                if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                    with let:
                        m15 = p.mark()
                    pTrailComment(p)
                    m15.discardUnused()
                pStmt(p)
                m14.discardUnused()
            else:
                p.emitEmpty()
            with let:
                m = Mark(prev=m0.prev, info=at13, sigs=m0.sigs)
            procLayout(p, m, kw)
    else:
        with var:
            at16 = m0.info
        pOptInd(p)
        at16 = p.info()
        pRoutineSig(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with let:
                m17 = p.mark()
            expect(p, TokKind.tkEquals)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
                with let:
                    m18 = p.mark()
                pTrailComment(p)
                m18.discardUnused()
            pStmt(p)
            m17.discardUnused()
        else:
            p.emitEmpty()
        with let:
            m = Mark(prev=m0.prev, info=at16, sigs=m0.sigs)
        procLayout(p, m, kw)
    m0.discardUnused()


def pMissingEquals(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    p.missingEquals()
    m0.discardUnused()


def pCommentStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    emitLeaf(p)
    wrap(p, m0, NiflerKind.CommentL)
    m0.discardUnused()


def pEnumDecl(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkEnum)
    pOptInd(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m1 = p.mark()
        pFlexComment(p)
        m1.discardUnused()
    p.emitEmpty()
    with let:
        m2 = p.mark()
    with var:
        at3 = m2.info
    pValidInd(p)
    pSymbol(p)
    p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        with let:
            m4 = p.mark()
        pPragma(p)
        at3 = p.info()
        m4.discardUnused()
    else:
        p.emitEmpty()
    p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        with let:
            m5 = p.mark()
        expect(p, TokKind.tkEquals)
        pOptInd(p)
        at3 = p.info()
        pExpr(p)
        m5.discardUnused()
    else:
        p.emitEmpty()
    wrapAt(p, m2, NiflerKind.EfldL, at3)
    if p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m6 = p.mark()
        pComma(p)
        m6.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m7 = p.mark()
        pFlexComment(p)
        m7.discardUnused()
    m2.discardUnused()
    while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m8 = p.mark()
        with var:
            at9 = m8.info
        pValidInd(p)
        pSymbol(p)
        p.emitEmpty()
        if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
            with let:
                m10 = p.mark()
            pPragma(p)
            at9 = p.info()
            m10.discardUnused()
        else:
            p.emitEmpty()
        p.emitEmpty()
        if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
            with let:
                m11 = p.mark()
            expect(p, TokKind.tkEquals)
            pOptInd(p)
            at9 = p.info()
            pExpr(p)
            m11.discardUnused()
        else:
            p.emitEmpty()
        wrapAt(p, m8, NiflerKind.EfldL, at9)
        if p.tok.kind in Tset[TokKind](TokKind.tkComma):
            with let:
                m12 = p.mark()
            pComma(p)
            m12.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            with let:
                m13 = p.mark()
            pFlexComment(p)
            m13.discardUnused()
        m8.discardUnused()
    pEnumListEnd(p)
    wrap(p, m0, NiflerKind.EnumL)
    m0.discardUnused()


def pObjectWhen(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.pushFieldWrap(False)
    expect(p, TokKind.tkWhen)
    with var:
        at1 = m0.info
    at1 = p.info()
    pExpr(p)
    pColcom(p)
    pObjectPart(p)
    wrapAt(p, m0, NiflerKind.ElifL, at1)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m2 = p.mark()
        pFlexComment(p)
        m2.discardUnused()
    while p.tok.kind in Tset[TokKind](TokKind.tkElif) and p.indClass() in Tset[IndClass](IndClass.icEq):
        with let:
            m3 = p.mark()
        with var:
            at4 = m3.info
        checkInd(p, Tset[IndClass](IndClass.icEq))
        expect(p, TokKind.tkElif)
        at4 = p.info()
        pExpr(p)
        pColcom(p)
        pObjectPart(p)
        wrapAt(p, m3, NiflerKind.ElifL, at4)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            with let:
                m5 = p.mark()
            pFlexComment(p)
            m5.discardUnused()
        m3.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkElse) and p.indClass() in Tset[IndClass](IndClass.icEq):
        with let:
            m6 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icEq))
        pObjectElse(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            with let:
                m7 = p.mark()
            pFlexComment(p)
            m7.discardUnused()
        m6.discardUnused()
    p.popFieldWrap()
    wrap(p, m0, NiflerKind.WhenL)
    m0.discardUnused()


def pObjectElse(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.pushFieldWrap(True)
    expect(p, TokKind.tkElse)
    pColcom(p)
    pBranchPart(p)
    p.popFieldWrap()
    wrap(p, m0, NiflerKind.ElseL)
    m0.discardUnused()


def pObjectBranch(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.pushFieldWrap(True)
    expect(p, TokKind.tkOf)
    pExprList(p)
    wrap(p, m0, NiflerKind.RangesL)
    pColcom(p)
    pBranchPart(p)
    p.popFieldWrap()
    wrap(p, m0, NiflerKind.OfL)
    m0.discardUnused()


def pBranchPart(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pObjectPart(p)
    with let:
        m = m0
    requireFields(p, m)
    m0.discardUnused()


def pObjectBranches(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkOf):
        pObjectBranch(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
            with let:
                m1 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icEq))
            pObjectBranch(p)
            m1.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkElse) and p.indClass() in Tset[IndClass](IndClass.icEq):
            with let:
                m2 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icEq))
            pObjectElse(p)
            m2.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkElse):
        pObjectElse(p)
    else:
        ruleError(p, string("objectBranches"), False)
    m0.discardUnused()


def pObjectCase(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkCase)
    with let:
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pDeclColonEquals(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        p.emitEmpty()
        p.emitEmpty()
        pPragma(p)
        p.emitEmpty()
        p.emitEmpty()
        wrap(p, m1, NiflerKind.FldL)
    else:
        pEmptyDiscriminator(p)
    m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        with let:
            m2 = p.mark()
        expect(p, TokKind.tkColon)
        m2.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m3 = p.mark()
        pFlexComment(p)
        m3.discardUnused()
    with let:
        m4 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkElse, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icGt):
        pushInd(p)
        pObjectBranches(p)
        p.popInd()
    elif p.tok.kind in Tset[TokKind](TokKind.tkElse, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icEq):
        checkInd(p, Tset[IndClass](IndClass.icEq))
        pObjectBranches(p)
    else:
        ruleError(p, string("objectCase"), p.tok.kind in Tset[TokKind](TokKind.tkElse, TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt))
    m4.discardUnused()
    wrap(p, m0, NiflerKind.CaseL)
    m0.discardUnused()


def pObjectPart(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkCase, TokKind.tkComment, TokKind.tkDiscard, TokKind.tkNil, TokKind.tkSymbol, TokKind.tkWhen) and p.indClass() in Tset[IndClass](IndClass.icGt):
        p.pushFieldWrap(False)
        pushInd(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
            with let:
                m1 = p.mark()
            pOptSameInd(p)
            emitLeaf(p)
            m1.discardUnused()
        with let:
            m2 = p.mark()
        pObjectPart(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkCase, TokKind.tkDiscard, TokKind.tkNil, TokKind.tkSymbol, TokKind.tkWhen) and p.indClass() in Tset[IndClass](IndClass.icEq):
            checkInd(p, Tset[IndClass](IndClass.icEq))
            pObjectPart(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkCase, TokKind.tkDiscard, TokKind.tkNil, TokKind.tkSymbol, TokKind.tkWhen) and p.indClass() == IndClass.icGt:
            indentError(p)
        m2.discardUnused()
        pStrictListEnd(p)
        p.popInd()
        p.popFieldWrap()
        wrap(p, m0, NiflerKind.StmtsL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkCase, TokKind.tkDiscard, TokKind.tkNil, TokKind.tkSymbol, TokKind.tkWhen) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
        pOptSameInd(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkWhen):
            pObjectWhen(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCase):
            pObjectCase(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkNil):
            expect(p, TokKind.tkNil)
            wrap(p, m0, NiflerKind.NilL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDiscard):
            expect(p, TokKind.tkDiscard)
            wrap(p, m0, NiflerKind.NilL)
        elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
            pDeclColonEquals(p)
            if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq, IndClass.icGt):
                with let:
                    m3 = p.mark()
                pOptPar(p)
                emitLeaf(p)
                m3.discardUnused()
        else:
            ruleError(p, string("objectPart"), False)
    else:
        with let:
            m = m0
        strictListStart(p)
    m0.discardUnused()


def pObjectDecl(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.pushSection(NiflerKind.FldL)
    expect(p, TokKind.tkObject)
    if p.tok.kind in Tset[TokKind](TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        expect(p, TokKind.tkOf)
        pTypeDesc(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m2 = p.mark()
        pTrailComment(p)
        m2.discardUnused()
    with let:
        m3 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkCase, TokKind.tkComment, TokKind.tkDiscard, TokKind.tkNil, TokKind.tkSymbol, TokKind.tkWhen) and p.indClass() in Tset[IndClass](IndClass.icGt):
        checkInd(p, Tset[IndClass](IndClass.icGt))
        pObjectBody(p)
    else:
        pStrictListStart(p)
    m3.discardUnused()
    p.popSection()
    wrap(p, m0, NiflerKind.ObjectL)
    m0.discardUnused()


def pObjectBody(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.pushFieldWrap(False)
    pushInd(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
        with let:
            m1 = p.mark()
        pOptSameInd(p)
        emitLeaf(p)
        m1.discardUnused()
    with let:
        m2 = p.mark()
    pObjectPart(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkCase, TokKind.tkDiscard, TokKind.tkNil, TokKind.tkSymbol, TokKind.tkWhen) and p.indClass() in Tset[IndClass](IndClass.icEq):
        checkInd(p, Tset[IndClass](IndClass.icEq))
        pObjectPart(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkCase, TokKind.tkDiscard, TokKind.tkNil, TokKind.tkSymbol, TokKind.tkWhen) and p.indClass() == IndClass.icGt:
        indentError(p)
    m2.discardUnused()
    pStrictListEnd(p)
    p.popInd()
    p.popFieldWrap()
    m0.discardUnused()


def pEmptyDiscriminator(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    emptyDiscriminator(p)
    m0.discardUnused()


def pPosMarker(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    p.posMarker()
    m0.discardUnused()


def pStrictListEnd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    strictListEnd(p)
    m0.discardUnused()


def pStrictListStart(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    strictListStart(p)
    m0.discardUnused()


def pEnumListEnd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    enumListEnd(p)
    m0.discardUnused()


def pParamStart(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    p.paramStart()
    m0.discardUnused()


def pOfInherit(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkOf)
    pTypeDesc(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        expect(p, TokKind.tkComma)
        pTypeDesc(p)
        m1.discardUnused()
    with let:
        m = m0
    inheritLayout(p, m)
    m0.discardUnused()


def pConceptParam(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkVar):
        expect(p, TokKind.tkVar)
        pSymbol(p)
        wrap(p, m1, NiflerKind.MutL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOut):
        expect(p, TokKind.tkOut)
        pSymbol(p)
        wrap(p, m1, NiflerKind.OutL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkPtr):
        expect(p, TokKind.tkPtr)
        pSymbol(p)
        wrap(p, m1, NiflerKind.PtrL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkRef):
        expect(p, TokKind.tkRef)
        pSymbol(p)
        wrap(p, m1, NiflerKind.RefL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkStatic):
        expect(p, TokKind.tkStatic)
        pSymbol(p)
        wrap(p, m1, NiflerKind.StaticL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkType):
        expect(p, TokKind.tkType)
        pSymbol(p)
        wrap(p, m1, NiflerKind.TypeofL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType):
        pSymbol(p)
    else:
        ruleError(p, string("conceptParam"), False)
    m1.discardUnused()
    m0.discardUnused()


def pConceptDecl(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkConcept)
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkOut, TokKind.tkPtr, TokKind.tkRef, TokKind.tkStatic, TokKind.tkSymbol, TokKind.tkType, TokKind.tkVar) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m2 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        with let:
            m3 = p.mark()
        pConceptParam(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkComma):
            expect(p, TokKind.tkComma)
            pConceptParam(p)
        m3.discardUnused()
        wrap(p, m2, NiflerKind.StmtsL)
        m2.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m4 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        pPragma(p)
        m4.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkOf) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m5 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        pOfInherit(p)
        m5.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m6 = p.mark()
        pTrailComment(p)
        m6.discardUnused()
    if canStmt(p) and p.indClass() in Tset[IndClass](IndClass.icGt):
        with let:
            m7 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icGt))
        pStmt(p)
        m7.discardUnused()
    else:
        p.emitEmpty()
    wrap(p, m0, NiflerKind.ConceptL)
    m0.discardUnused()


def pTypeDef(p: mut @ Parser):
    with let:
        m0 = p.mark()
    with var:
        at1 = m0.info
    pIdentVisDot(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
        with let:
            m2 = p.mark()
        pGenericParamList(p)
        m2.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        with let:
            m3 = p.mark()
        pPragma(p)
        m3.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkEquals):
        with let:
            m4 = p.mark()
        at1 = p.info()
        expect(p, TokKind.tkEquals)
        pOptInd(p)
        pTypeDefValue(p)
        m4.discardUnused()
    else:
        p.emitEmpty()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
        with let:
            m5 = p.mark()
        pIndAndComment(p)
        m5.discardUnused()
    wrapAt(p, m0, NiflerKind.TypeL, at1)
    m0.discardUnused()


def pTypeDefValue(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkConcept, TokKind.tkEnum, TokKind.tkObject, TokKind.tkTuple):
        with let:
            m1 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkTuple):
            pTupleDecl(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkEnum):
            pEnumDecl(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkObject):
            pObjectDecl(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkConcept):
            pConceptDecl(p)
        else:
            ruleError(p, string("typeDefValue"), False)
        m1.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkNot) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m2 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icNoInd))
            with var:
                at3 = p.info()
            insertTokAt(p, m0, TokKind.tkNot)
            pPrimary(p, PrimaryMode.pmTypeDesc)
            at3 = p.info()
            wrapAt(p, m0, NiflerKind.InfixL, at3)
            m2.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkWhen):
        pWhenExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkNot) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m4 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icNoInd))
            with var:
                at5 = p.info()
            insertTokAt(p, m0, TokKind.tkNot)
            pPrimary(p, PrimaryMode.pmTypeDesc)
            at5 = p.info()
            wrapAt(p, m0, NiflerKind.InfixL, at5)
            m4.discardUnused()
    else:
        pTypeDefExpr(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkNot) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m6 = p.mark()
            checkInd(p, Tset[IndClass](IndClass.icNoInd))
            with var:
                at7 = p.info()
            insertTokAt(p, m0, TokKind.tkNot)
            pPrimary(p, PrimaryMode.pmTypeDesc)
            at7 = p.info()
            wrapAt(p, m0, NiflerKind.InfixL, at7)
            m6.discardUnused()
    m0.discardUnused()


def pTypeDefExpr(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pSimpleExpr(p, -1, PrimaryMode.pmTypeDef)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m1 = p.mark()
        pComma(p)
        pExprEqExpr(p)
        m1.discardUnused()
    if p.tok.kind in Tset[TokKind](TokKind.tkColon, TokKind.tkDo) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m2 = p.mark()
        pPostExprBlocks(p)
        m2.discardUnused()
    with let:
        m = m0
    attachBlocks(p, m)
    m0.discardUnused()


def pTupleVar(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentWithPragmaDot(p)
    p.emitEmpty()
    p.emitEmpty()
    with let:
        m = m0
    wrapSection(p, m)
    m0.discardUnused()


def pVarTupleLhs(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkParLe)
    pOptInd(p)
    with let:
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pTupleVar(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        pNestedTuple(p)
    else:
        ruleError(p, string("varTupleLhs"), False)
    m1.discardUnused()
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        with let:
            m2 = p.mark()
        pComma(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol):
            with let:
                m3 = p.mark()
                m4 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
                pTupleVar(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
                pNestedTuple(p)
            else:
                ruleError(p, string("varTupleLhs"), False)
            m4.discardUnused()
            m3.discardUnused()
        m2.discardUnused()
    pOptPar(p)
    expect(p, TokKind.tkParRi)
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        with let:
            m5 = p.mark()
        expect(p, TokKind.tkColon)
        pOptInd(p)
        pTypeDescExpr(p)
        m5.discardUnused()
    wrap(p, m0, NiflerKind.UnpacktupL)
    m0.discardUnused()


def pNestedTuple(p: mut @ Parser):
    with let:
        m0 = p.mark()
    p.emitEmpty()
    pVarTupleLhs(p)
    wrap(p, m0, NiflerKind.UnpackdeclL)
    m0.discardUnused()


def pVarTupleBody(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pVarTupleLhs(p)
    expect(p, TokKind.tkEquals)
    pOptInd(p)
    pExprBlocks(p)
    with let:
        m = m0
    p.moveLastToMark(m)
    m0.discardUnused()


def pVarTuple(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pVarTupleBody(p)
    wrap(p, m0, NiflerKind.UnpackdeclL)
    m0.discardUnused()


def pVariable(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        pVarTuple(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pDeclColonEqualsDot(p)
    else:
        ruleError(p, string("variable"), False)
    m1.discardUnused()
    pIndAndComment(p)
    m0.discardUnused()


def pConstDef(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pIdentWithPragma(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkColon):
        with let:
            m1 = p.mark()
        pColon(p)
        pTypeDesc(p)
        m1.discardUnused()
    else:
        p.emitEmpty()
    expect(p, TokKind.tkEquals)
    pOptInd(p)
    pExprBlocks(p)
    with let:
        m = m0
    fanOut(p, m)
    m0.discardUnused()


def pConstant(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        pVarTuple(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
        pConstDef(p)
    else:
        ruleError(p, string("constant"), False)
    m1.discardUnused()
    pIndAndComment(p)
    m0.discardUnused()


def pBindStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkBind)
    pOptInd(p)
    with let:
        m1 = p.mark()
    pQualifiedIdent(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        pComma(p)
        pQualifiedIdent(p)
    m1.discardUnused()
    wrap(p, m0, NiflerKind.BindL)
    m0.discardUnused()


def pMixinStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    expect(p, TokKind.tkMixin)
    pOptInd(p)
    with let:
        m1 = p.mark()
    pQualifiedIdent(p)
    while p.tok.kind in Tset[TokKind](TokKind.tkComma):
        pComma(p)
        pQualifiedIdent(p)
    m1.discardUnused()
    wrap(p, m0, NiflerKind.MixinL)
    m0.discardUnused()


def pPragmaStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    pPragma(p)
    if p.tok.kind in Tset[TokKind](TokKind.tkColon) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        expect(p, TokKind.tkColon)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m2 = p.mark()
            pTrailComment(p)
            m2.discardUnused()
        pStmt(p)
        m1.discardUnused()
    with let:
        m = m0
    pragmaBlock(p, m)
    m0.discardUnused()


def pSimpleStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkBreak, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkDiscard, TokKind.tkExport, TokKind.tkFrom, TokKind.tkImport, TokKind.tkInclude, TokKind.tkRaise, TokKind.tkReturn, TokKind.tkYield):
        with let:
            m1 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkReturn):
            pReturnStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkRaise):
            pRaiseStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkYield):
            pYieldStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDiscard):
            pDiscardStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBreak):
            pBreakStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkContinue):
            pContinueStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
            pPragmaStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkImport):
            pImportStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkExport):
            pExportStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkFrom):
            pFromStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkInclude):
            pIncludeStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
            pCommentStmt(p)
        else:
            ruleError(p, string("simpleStmt"), False)
        m1.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m2 = p.mark()
            pTrailComment(p)
            m2.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkEnum, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIterator, TokKind.tkNil, TokKind.tkNot, TokKind.tkObject, TokKind.tkOpr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRef, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar):
        pExprStmt(p)
        if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            with let:
                m3 = p.mark()
            pTrailComment(p)
            m3.discardUnused()
    else:
        ruleError(p, string("simpleStmt"), False)
    m0.discardUnused()


def pExprStart(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkSymbol):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent):
        expect(p, TokKind.tkAccent)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOpr):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkNot):
        expect(p, TokKind.tkNot)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCast):
        expect(p, TokKind.tkCast)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIf):
        expect(p, TokKind.tkIf)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFor):
        expect(p, TokKind.tkFor)
    elif p.tok.kind in Tset[TokKind](TokKind.tkProc):
        expect(p, TokKind.tkProc)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFunc):
        expect(p, TokKind.tkFunc)
    elif p.tok.kind in Tset[TokKind](TokKind.tkIterator):
        expect(p, TokKind.tkIterator)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBind):
        expect(p, TokKind.tkBind)
    elif p.tok.kind in Tset[TokKind](TokKind.tkType):
        expect(p, TokKind.tkType)
    elif p.tok.kind in Tset[TokKind](TokKind.tkStatic):
        expect(p, TokKind.tkStatic)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAddr):
        expect(p, TokKind.tkAddr)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        expect(p, TokKind.tkParLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
        expect(p, TokKind.tkBracketLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
        expect(p, TokKind.tkCurlyLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCharLit, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkRStrLit, TokKind.tkStrLit, TokKind.tkTripleStrLit, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
        pLiteral(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkGStrLit, TokKind.tkGTripleStrLit):
        pGeneralizedLit(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkVar):
        expect(p, TokKind.tkVar)
    elif p.tok.kind in Tset[TokKind](TokKind.tkRef):
        expect(p, TokKind.tkRef)
    elif p.tok.kind in Tset[TokKind](TokKind.tkPtr):
        expect(p, TokKind.tkPtr)
    elif p.tok.kind in Tset[TokKind](TokKind.tkEnum):
        expect(p, TokKind.tkEnum)
    elif p.tok.kind in Tset[TokKind](TokKind.tkTuple):
        expect(p, TokKind.tkTuple)
    elif p.tok.kind in Tset[TokKind](TokKind.tkObject):
        expect(p, TokKind.tkObject)
    elif p.tok.kind in Tset[TokKind](TokKind.tkWhen):
        expect(p, TokKind.tkWhen)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCase):
        expect(p, TokKind.tkCase)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOut):
        expect(p, TokKind.tkOut)
    elif p.tok.kind in Tset[TokKind](TokKind.tkTry):
        expect(p, TokKind.tkTry)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBlock):
        expect(p, TokKind.tkBlock)
    else:
        ruleError(p, string("exprStart"), False)
    m1.discardUnused()
    m0.discardUnused()


def pComplexOrSimpleStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkCase, TokKind.tkDefer, TokKind.tkFor, TokKind.tkIf, TokKind.tkMixin, TokKind.tkStatic, TokKind.tkTry, TokKind.tkWhen, TokKind.tkWhile):
        with let:
            m1 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkIf):
            pIfStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkWhen):
            pWhenStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkWhile):
            pWhileStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkTry):
            pTryStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkFor):
            pForStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBlock):
            pBlockStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkStatic):
            pStaticStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkDefer):
            pDeferStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkAsm):
            pAsmStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkBind):
            pBindStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkMixin):
            pMixinStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkCase):
            pCaseStmt(p)
        else:
            ruleError(p, string("complexOrSimpleStmt"), False)
        m1.discardUnused()
    elif p.tok.kind in Tset[TokKind](TokKind.tkExcept):
        expect(p, TokKind.tkExcept)
        p.emitEmpty()
        pColcom(p)
        pStmt(p)
        wrap(p, m0, NiflerKind.ExceptL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFinally):
        expect(p, TokKind.tkFinally)
        pColcom(p)
        pStmt(p)
        wrap(p, m0, NiflerKind.FinL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkProc):
        p.pushInfo()
        expect(p, TokKind.tkProc)
        pRoutine(p, NiflerKind.ProcL)
        p.popInfo()
    elif p.tok.kind in Tset[TokKind](TokKind.tkMethod):
        p.pushInfo()
        expect(p, TokKind.tkMethod)
        pRoutine(p, NiflerKind.MethodL)
        p.popInfo()
    elif p.tok.kind in Tset[TokKind](TokKind.tkFunc):
        p.pushInfo()
        expect(p, TokKind.tkFunc)
        pRoutine(p, NiflerKind.FuncL)
        p.popInfo()
    elif p.tok.kind in Tset[TokKind](TokKind.tkIterator):
        p.pushInfo()
        expect(p, TokKind.tkIterator)
        pRoutine(p, NiflerKind.IteratorL)
        p.popInfo()
    elif p.tok.kind in Tset[TokKind](TokKind.tkMacro):
        p.pushInfo()
        expect(p, TokKind.tkMacro)
        pRoutine(p, NiflerKind.MacroL)
        p.popInfo()
    elif p.tok.kind in Tset[TokKind](TokKind.tkTemplate):
        p.pushInfo()
        expect(p, TokKind.tkTemplate)
        pRoutine(p, NiflerKind.TemplateL)
        p.popInfo()
    elif p.tok.kind in Tset[TokKind](TokKind.tkConverter):
        p.pushInfo()
        expect(p, TokKind.tkConverter)
        pRoutine(p, NiflerKind.ConverterL)
        p.popInfo()
    elif p.tok.kind in Tset[TokKind](TokKind.tkType):
        expect(p, TokKind.tkType)
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icGt):
            pSection_typeDef(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
            with var:
                at2 = m0.info
            expect(p, TokKind.tkParLe)
            at2 = p.info()
            pPrimary(p, PrimaryMode.pmTypeDesc)
            expect(p, TokKind.tkParRi)
            wrapAt(p, m0, NiflerKind.TypeofL, at2)
            with var:
                prec3 = p.getPrecedence()
            while prec3 >= -1 and p.indClass() == IndClass.icNoInd:
                with var:
                    assoc3 = 1
                if p.isRightAssoc():
                    assoc3 = 0
                with let:
                    opassoc3 = p.info()
                p.insertOpLeafAt(m0)
                p.getTok()
                afterOperator(p)
                pSimpleExpr(p, prec3 + assoc3, PrimaryMode.pmNormal)
                wrapAt(p, m0, NiflerKind.InfixL, opassoc3)
                prec3 = p.getPrecedence()
        else:
            ruleError(p, string("complexOrSimpleStmt"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq))
    elif p.tok.kind in Tset[TokKind](TokKind.tkConst):
        p.pushSection(NiflerKind.ConstL)
        expect(p, TokKind.tkConst)
        pSection_constant(p)
        p.popSection()
    elif p.tok.kind in Tset[TokKind](TokKind.tkLet):
        p.pushSection(NiflerKind.LetL)
        expect(p, TokKind.tkLet)
        pSection_variable(p)
        p.popSection()
    elif p.tok.kind in Tset[TokKind](TokKind.tkVar):
        p.pushSection(NiflerKind.VarL)
        expect(p, TokKind.tkVar)
        pSection_variable(p)
        p.popSection()
    elif p.tok.kind in Tset[TokKind](TokKind.tkUsing):
        p.pushLastSection()
        expect(p, TokKind.tkUsing)
        pSection_variable(p)
        p.popSection()
        wrap(p, m0, NiflerKind.UsingL)
    else:
        pSimpleStmt(p)
    m0.discardUnused()


def pStmt(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icGt):
        pushInd(p)
        pComplexOrSimpleStmt(p)
        while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
            with let:
                m1 = p.mark()
                m2 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icEq):
                checkInd(p, Tset[IndClass](IndClass.icEq))
                pComplexOrSimpleStmt(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                expect(p, TokKind.tkSemiColon)
                if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icEq):
                    with let:
                        m3 = p.mark()
                    pOptSameInd(p)
                    pComplexOrSimpleStmt(p)
                    m3.discardUnused()
            else:
                ruleError(p, string("stmt"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBind, TokKind.tkBlock, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCase, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkConst, TokKind.tkContinue, TokKind.tkConverter, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDefer, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExcept, TokKind.tkExport, TokKind.tkFinally, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFor, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkIf, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTemplate, TokKind.tkTripleStrLit, TokKind.tkTry, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icGt))
            m2.discardUnused()
            m1.discardUnused()
        pStmtListEnd(p)
        p.popInd()
        wrap(p, m0, NiflerKind.StmtsL)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDiscard, TokKind.tkEnum, TokKind.tkExport, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkImport, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkNot, TokKind.tkObject, TokKind.tkOpr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq):
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExport, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq) and inSemiStmtList(p):
            pNotInd(p)
            pSimpleStmt(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExport, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
            checkInd(p, Tset[IndClass](IndClass.icNoInd))
            with let:
                m4 = p.mark()
            pSimpleStmt(p)
            while p.tok.kind in Tset[TokKind](TokKind.tkSemiColon):
                expect(p, TokKind.tkSemiColon)
                pSimpleStmt(p)
            m4.discardUnused()
            wrap(p, m0, NiflerKind.StmtsL)
        else:
            ruleError(p, string("stmt"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkAddr, TokKind.tkAnd, TokKind.tkAs, TokKind.tkBind, TokKind.tkBracketLe, TokKind.tkBreak, TokKind.tkCast, TokKind.tkCharLit, TokKind.tkComment, TokKind.tkContinue, TokKind.tkCurlyDotLe, TokKind.tkCurlyLe, TokKind.tkCustomLit, TokKind.tkDiscard, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkEnum, TokKind.tkExport, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkFrom, TokKind.tkFunc, TokKind.tkGStrLit, TokKind.tkGTripleStrLit, TokKind.tkImport, TokKind.tkIn, TokKind.tkInclude, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkMod, TokKind.tkNil, TokKind.tkNot, TokKind.tkNotin, TokKind.tkObject, TokKind.tkOf, TokKind.tkOpr, TokKind.tkOr, TokKind.tkOut, TokKind.tkParLe, TokKind.tkProc, TokKind.tkPtr, TokKind.tkRStrLit, TokKind.tkRaise, TokKind.tkRef, TokKind.tkReturn, TokKind.tkShl, TokKind.tkShr, TokKind.tkStatic, TokKind.tkStrLit, TokKind.tkSymbol, TokKind.tkTripleStrLit, TokKind.tkTuple, TokKind.tkType, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit, TokKind.tkVar, TokKind.tkXor, TokKind.tkYield) and p.indClass() in Tset[IndClass](IndClass.icGt))
    else:
        ruleError(p, string("stmt"), p.tok.kind in Tset[TokKind](TokKind.tkAnd, TokKind.tkAs, TokKind.tkAsm, TokKind.tkBlock, TokKind.tkCase, TokKind.tkConst, TokKind.tkConverter, TokKind.tkDefer, TokKind.tkDistinct, TokKind.tkDiv, TokKind.tkDotDot, TokKind.tkExcept, TokKind.tkFinally, TokKind.tkFor, TokKind.tkFunc, TokKind.tkIf, TokKind.tkIn, TokKind.tkIs, TokKind.tkIsnot, TokKind.tkIterator, TokKind.tkLet, TokKind.tkMacro, TokKind.tkMethod, TokKind.tkMixin, TokKind.tkMod, TokKind.tkNotin, TokKind.tkOf, TokKind.tkOr, TokKind.tkProc, TokKind.tkShl, TokKind.tkShr, TokKind.tkTemplate, TokKind.tkTry, TokKind.tkType, TokKind.tkUsing, TokKind.tkVar, TokKind.tkWhen, TokKind.tkWhile, TokKind.tkXor) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq))
    m0.discardUnused()


def pStmtListEnd(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m = m0
    stmtListEnd(p)
    m0.discardUnused()


def pOneLinerStart(p: mut @ Parser):
    with let:
        m0 = p.mark()
        m1 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkReturn):
        expect(p, TokKind.tkReturn)
    elif p.tok.kind in Tset[TokKind](TokKind.tkRaise):
        expect(p, TokKind.tkRaise)
    elif p.tok.kind in Tset[TokKind](TokKind.tkYield):
        expect(p, TokKind.tkYield)
    elif p.tok.kind in Tset[TokKind](TokKind.tkDiscard):
        expect(p, TokKind.tkDiscard)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBreak):
        expect(p, TokKind.tkBreak)
    elif p.tok.kind in Tset[TokKind](TokKind.tkContinue):
        expect(p, TokKind.tkContinue)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyDotLe):
        expect(p, TokKind.tkCurlyDotLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkImport):
        expect(p, TokKind.tkImport)
    elif p.tok.kind in Tset[TokKind](TokKind.tkExport):
        expect(p, TokKind.tkExport)
    elif p.tok.kind in Tset[TokKind](TokKind.tkFrom):
        expect(p, TokKind.tkFrom)
    elif p.tok.kind in Tset[TokKind](TokKind.tkInclude):
        expect(p, TokKind.tkInclude)
    elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkSymbol):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent):
        expect(p, TokKind.tkAccent)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOpr):
        emitLeaf(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkNot):
        expect(p, TokKind.tkNot)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCast):
        expect(p, TokKind.tkCast)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBind):
        expect(p, TokKind.tkBind)
    elif p.tok.kind in Tset[TokKind](TokKind.tkStatic):
        expect(p, TokKind.tkStatic)
    elif p.tok.kind in Tset[TokKind](TokKind.tkAddr):
        expect(p, TokKind.tkAddr)
    elif p.tok.kind in Tset[TokKind](TokKind.tkParLe):
        expect(p, TokKind.tkParLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkBracketLe):
        expect(p, TokKind.tkBracketLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCurlyLe):
        expect(p, TokKind.tkCurlyLe)
    elif p.tok.kind in Tset[TokKind](TokKind.tkCharLit, TokKind.tkCustomLit, TokKind.tkFloat128Lit, TokKind.tkFloat32Lit, TokKind.tkFloat64Lit, TokKind.tkFloatLit, TokKind.tkInt16Lit, TokKind.tkInt32Lit, TokKind.tkInt64Lit, TokKind.tkInt8Lit, TokKind.tkIntLit, TokKind.tkNil, TokKind.tkRStrLit, TokKind.tkStrLit, TokKind.tkTripleStrLit, TokKind.tkUInt16Lit, TokKind.tkUInt32Lit, TokKind.tkUInt64Lit, TokKind.tkUInt8Lit, TokKind.tkUIntLit):
        pLiteral(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkGStrLit, TokKind.tkGTripleStrLit):
        pGeneralizedLit(p)
    elif p.tok.kind in Tset[TokKind](TokKind.tkRef):
        expect(p, TokKind.tkRef)
    elif p.tok.kind in Tset[TokKind](TokKind.tkPtr):
        expect(p, TokKind.tkPtr)
    elif p.tok.kind in Tset[TokKind](TokKind.tkEnum):
        expect(p, TokKind.tkEnum)
    elif p.tok.kind in Tset[TokKind](TokKind.tkTuple):
        expect(p, TokKind.tkTuple)
    elif p.tok.kind in Tset[TokKind](TokKind.tkObject):
        expect(p, TokKind.tkObject)
    elif p.tok.kind in Tset[TokKind](TokKind.tkOut):
        expect(p, TokKind.tkOut)
    else:
        ruleError(p, string("oneLinerStart"), False)
    m1.discardUnused()
    m0.discardUnused()


def pSection_typeDef(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    with let:
        m2 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icGt):
        pushInd(p)
        with let:
            m3 = p.mark()
            m4 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
            pTypeDef(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
            pCommentStmt(p)
        else:
            ruleError(p, string("section_typeDef"), False)
        m4.discardUnused()
        while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icEq):
            checkInd(p, Tset[IndClass](IndClass.icEq))
            with let:
                m5 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol):
                pTypeDef(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
                pCommentStmt(p)
            else:
                ruleError(p, string("section_typeDef"), False)
            m5.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkSymbol) and p.indClass() == IndClass.icGt:
            indentError(p)
        m3.discardUnused()
        pStrictListEnd(p)
        p.popInd()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        pTypeDef(p)
    else:
        ruleError(p, string("section_typeDef"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq))
    m2.discardUnused()
    m0.discardUnused()


def pSection_constant(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    with let:
        m2 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icGt):
        pushInd(p)
        with let:
            m3 = p.mark()
            m4 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol):
            pConstant(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
            pCommentStmt(p)
        else:
            ruleError(p, string("section_constant"), False)
        m4.discardUnused()
        while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icEq):
            checkInd(p, Tset[IndClass](IndClass.icEq))
            with let:
                m5 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol):
                pConstant(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
                pCommentStmt(p)
            else:
                ruleError(p, string("section_constant"), False)
            m5.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() == IndClass.icGt:
            indentError(p)
        m3.discardUnused()
        pStrictListEnd(p)
        p.popInd()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        pConstant(p)
    else:
        ruleError(p, string("section_constant"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq))
    m2.discardUnused()
    m0.discardUnused()


def pSection_variable(p: mut @ Parser):
    with let:
        m0 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        with let:
            m1 = p.mark()
        pTrailComment(p)
        m1.discardUnused()
    with let:
        m2 = p.mark()
    if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icGt):
        pushInd(p)
        with let:
            m3 = p.mark()
            m4 = p.mark()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol):
            pVariable(p)
        elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
            pCommentStmt(p)
        else:
            ruleError(p, string("section_variable"), False)
        m4.discardUnused()
        while p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icEq):
            checkInd(p, Tset[IndClass](IndClass.icEq))
            with let:
                m5 = p.mark()
            if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol):
                pVariable(p)
            elif p.tok.kind in Tset[TokKind](TokKind.tkComment):
                pCommentStmt(p)
            else:
                ruleError(p, string("section_variable"), False)
            m5.discardUnused()
        if p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkComment, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() == IndClass.icGt:
            indentError(p)
        m3.discardUnused()
        pStrictListEnd(p)
        p.popInd()
    elif p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icNoInd):
        checkInd(p, Tset[IndClass](IndClass.icNoInd))
        pVariable(p)
    else:
        ruleError(p, string("section_variable"), p.tok.kind in Tset[TokKind](TokKind.tkAccent, TokKind.tkParLe, TokKind.tkSymbol) and p.indClass() in Tset[IndClass](IndClass.icLt, IndClass.icEq) or p.tok.kind in Tset[TokKind](TokKind.tkComment) and p.indClass() in Tset[IndClass](IndClass.icNoInd, IndClass.icLt, IndClass.icEq))
    m2.discardUnused()
    m0.discardUnused()

# --------------------------------------------------------------- entry points


def parseModule(p: mut @ Parser):
    ## A whole module, with `parser.nim`'s `parseTopLevelStmt` checks around
    ## `module`. An error is recorded in `p`, not reported.
    if p.tok.indent > 0:
        indentError(p)  # `parseTopLevelStmt`: the first statement starts a line
    pModule(p)
    if not p.failed and p.tok.kind != TokKind.tkEof:
    # `module` stops at a token that does not start a statement, or not its
    # own line: parser.nim's `parseTopLevelStmt`
        if p.tok.indent == 0 or (p.tok.indent < 0 and p.prevKind in Tset[TokKind](TokKind.tkInvalid, TokKind.tkSemiColon)):
            exprExpected(p)
        elif p.tok.kind == TokKind.tkOpr and p.tok.s == "*":
            p.error(string("invalid indentation; an export marker '*' follows the declared identifier"))
        else:
            indentError(p)


def parseSnippet(code: string, asExpr: bool, pool: Pool, tags: TagPool, err: mut @ string) -> TokenBuf:
    ## Nim's `parseStmt` (`asExpr = false`) and `parseExpr`: `(stmts ...)`, or
    ## the one expression, into `pool` and `tags`. `err` is the first error --
    ## the lexer's messages come first, as nifler prints them -- and the result
    ## is empty when there is one. `parseExpr` is `parseStmt` that insists on
    ## exactly one statement, as it is in Nim's VM.
    with var:
        p = openParser(code, string(""), pool, tags)
    parseModule(p)
    err <<= string("")
    if p.lex.errors.len > 0:
    # the lexer's message is formatted, `(line, col) Error: msg` for a parser
    # without a file name
        with let:
            e = p.lex.errors[0]
            sep = e.find(string(") Error: "))
        err <<= e.substr(sep + len(string(") Error: "))) + string(" (at ") + e.substr(1, sep - 1) + string(" of the parsed code)")
    elif p.failed:
        err <<= p.errMsg + string(" (at ") + str(p.errLine) + string(", ") + str(p.errCol + 1) + string(" of the parsed code)")
    result = nifcore.createTokenBuf(16, pool, tags)
    if err.len == 0:
        with var:
            buf = p.finish()
            c = buf.beginRead()
        if not asExpr:
            addSubtree(result, c)
        else:
            with var:
                kids = childCursor(c)
                n = nint(0)
                first = kids.copy()
            while kids.hasMore():
                n += 1
                skip(kids)
            if n == 1: addSubtree(result, first)
            else: err <<= string("expected expression, but got multiple statements")
        endRead(c)
    p.close()
    return result


if comptime(__name__ == "__main__"):
    # parseSnippet, Nim's parseStmt / parseExpr: the tree it builds in nifpools' pool and tags, or its first
    # error (the lexer's or the parser's)
    from ..lib.nifpools import globalTags, pool, toString

    def show(code: string, asExpr: bool):
        with var:
            err = string("")
            buf = parseSnippet(code, asExpr, pool, globalTags, err)
        if err.len == 0: echo(toString(buf, False))
        else: echo("error: ", err)

    show(string("let x = 1 + 2\necho x"), False)
    show(string("proc f(a: int; b = 2): int =\n  result = a * b\n"), False)
    show(string("for i in 0 ..< n:\n  if i mod 2 == 0: s.add i\n  else: discard"), False)
    show(string("a.b(c, d)[0]"), True)
    show(string("Obj(x: 1, y: @[2, 3])"), True)
    show(string("x = 1; y = 2"), True)
    show(string("proc (x: int) ="), False)
    show(string("let s = \"unterminated"), False)
