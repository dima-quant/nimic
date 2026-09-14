"""
ncompiler/parser.py — Parser state and helpers
Converted from compiler/parser.nim
"""
from __future__ import annotations
from ncompiler.lexer import (
    Lexer, Token, TokType, tokKeywordLow, tokKeywordHigh,
    openLexer, closeLexer, TTokenSpacing, prettyTok, lexMessageTok
)
from ncompiler.lexer_impl import rawGetTok, getPrecedence
from ncompiler.ast import (
    PNode, TNodeKind, newNode, newNodeI, newAtom, newTree, newTreeI,
    newIdentNode, newIntNode, newFloatNode, newStrNode, setBaseFlags,
    TNodeFlag, namePos, patternPos, genericParamsPos, paramsPos,
    pragmasPos, miscPos, bodyPos, newProcNode, isNewStyleConcept
)
from ncompiler.nodekinds import nkCallKinds
from ncompiler.idents import PIdent, IdentCache
from ncompiler.lineinfos import TLineInfo, FileIndex, TMsgKind
from ncompiler.options import ConfigRef
from ncompiler.msgs import localError, globalError, fileInfoIdx, newLineInfo, message
from ncompiler.llstream import PLLStream, llStreamOpen


# --- Enums ---
class SymbolMode:
    smNormal = 0
    smAllowNil = 1
    smAfterDot = 2

class PrimaryMode:
    pmNormal = 0
    pmTypeDesc = 1
    pmTypeDef = 2
    pmTrySimple = 3


# --- Constants ---
errInvalidIndentation = "invalid indentation"
errIdentifierExpected = "identifier expected, but got '$1'"
errExprExpected = "expression expected, but found '$1'"
errInternal = "internal error"

tkBuiltInMagics = {TokType.tkType, TokType.tkStatic, TokType.tkAddr}


# --- Parser ---
class Parser:
    """Parser state object."""
    __slots__ = ('lex', 'tok', 'inPragma', 'inSemiStmtList', 'emptyNode',
                 'currInd', 'firstTok', 'hasProgress',
                 'lineNumberPrevious', 'lineStartPrevious', 'bufposPrevious')
    def __init__(self):
        self.lex = Lexer()
        self.tok = Token()
        self.inPragma = 0
        self.inSemiStmtList = 0
        self.emptyNode: PNode = newNode(TNodeKind.nkEmpty)
        self.currInd = 0
        self.firstTok = True
        self.hasProgress = False
        self.lineNumberPrevious = 0
        self.lineStartPrevious = 0
        self.bufposPrevious = 0


# --- Helpers ---
def parLineInfo(p: Parser) -> TLineInfo:
    return newLineInfo(p.lex.fileIdx, p.tok.line, p.tok.col)

def getTok(p: Parser):
    p.lineNumberPrevious = p.lex.lineNumber
    p.lineStartPrevious = p.lex.lineStart
    p.bufposPrevious = p.lex.bufpos
    rawGetTok(p.lex, p.tok)
    p.hasProgress = True

def openParser(p: Parser, fileIdx: FileIndex, inputstream: PLLStream,
               cache: IdentCache, config: ConfigRef):
    openLexer(p.lex, fileIdx, inputstream, cache, config)
    getTok(p)
    p.firstTok = True

def closeParser(p: Parser):
    closeLexer(p.lex)

def parMessage(p: Parser, msg, arg: str = ""):
    """Emit a parser message. msg can be TMsgKind or a plain string."""
    if isinstance(msg, str):
        # String message — treat as errGenerated with the string as arg
        lexMessageTok(p.lex, TMsgKind.errGenerated, p.tok, msg)
    elif isinstance(msg, TMsgKind):
        lexMessageTok(p.lex, msg, p.tok, arg)
    else:
        lexMessageTok(p.lex, TMsgKind.errGenerated, p.tok, str(msg))

def parMessageTok(p: Parser, msg: str, tok: Token):
    """Produce a parser message about a specific token."""
    parMessage(p, msg.replace("$1", prettyTok(tok)))

def isKeyword(tt: TokType) -> bool:
    return tt.value >= tokKeywordLow.value and tt.value <= tokKeywordHigh.value

def eat(p: Parser, tokType: TokType):
    if p.tok.tokType == tokType:
        getTok(p)
    else:
        from ncompiler.lexer import lexMessage
        lexMessageTok(p.lex, TMsgKind.errGenerated, p.tok,
                      f"expected: '{tokType.name}', but got: '{prettyTok(p.tok)}'")

def opt(p: Parser, tokType: TokType) -> bool:
    if p.tok.tokType == tokType:
        getTok(p)
        return True
    return False

def validInd(p: Parser) -> bool:
    return p.tok.indent < 0 or p.tok.indent > p.currInd

def rawSkipComment(p: Parser, node: PNode):
    if p.tok.tokType == TokType.tkComment:
        if node is not None:
            node.comment = node.comment + p.tok.literal
        else:
            parMessage(p, TMsgKind.errInternal, "skipComment")
        getTok(p)

def skipComment(p: Parser, n: PNode):
    if p.tok.indent < 0:
        rawSkipComment(p, n)

def flexComment(p: Parser, n: PNode):
    if p.tok.indent < 0 or realInd(p):
        rawSkipComment(p, n)

def indAndComment(p: Parser, n: PNode, maybeMissEquals: bool = False):
    """Handle optional indentation + doc comment after a construct."""
    if p.tok.indent > p.currInd:
        if p.tok.tokType == TokType.tkComment:
            rawSkipComment(p, n)
        elif maybeMissEquals:
            col = p.bufposPrevious - p.lineStartPrevious
            info = newLineInfo(p.lex.fileIdx, p.lineNumberPrevious, col)
            from ncompiler.msgs import toFileLineCol
            parMessage(p, f"invalid indentation, maybe you forgot a '=' at {toFileLineCol(p.lex.config, info)} ?")
        else:
            parMessage(p, errInvalidIndentation)
    else:
        skipComment(p, n)

def sameOrNoInd(p: Parser) -> bool:
    return p.tok.indent < 0 or p.tok.indent >= p.currInd

def sameInd(p: Parser) -> bool:
    return p.tok.indent == p.currInd

def realInd(p: Parser) -> bool:
    return p.tok.indent > p.currInd

def skipInd(p: Parser):
    if p.tok.indent >= 0:
        if not realInd(p):
            parMessage(p, errInvalidIndentation)

def optPar(p: Parser):
    if p.tok.indent >= 0:
        if p.tok.indent < p.currInd:
            parMessage(p, errInvalidIndentation)

def optInd(p: Parser, n: PNode):
    skipComment(p, n)
    skipInd(p)

def getTokNoInd(p: Parser):
    getTok(p)
    if p.tok.indent >= 0:
        parMessage(p, errInvalidIndentation)

def expectIdentOrKeyw(p: Parser):
    if p.tok.tokType != TokType.tkSymbol and not isKeyword(p.tok.tokType):
        from ncompiler.lexer import lexMessage
        lexMessageTok(p.lex, TMsgKind.errGenerated, p.tok,
                      errIdentifierExpected.replace("$1", prettyTok(p.tok)))

def expectIdent(p: Parser):
    if p.tok.tokType != TokType.tkSymbol:
        from ncompiler.lexer import lexMessage
        lexMessageTok(p.lex, TMsgKind.errGenerated, p.tok,
                      errIdentifierExpected.replace("$1", prettyTok(p.tok)))

def colcom(p: Parser, n: PNode):
    eat(p, TokType.tkColon)
    skipComment(p, n)

def isUnary(p_or_tok) -> bool:
    """Check if the current operator is unary (leading whitespace only)."""
    if isinstance(p_or_tok, Parser):
        tok = p_or_tok.tok
    else:
        tok = p_or_tok
    return (tok.tokType in (TokType.tkOpr, TokType.tkDotDot) and
            tok.spacing == {TTokenSpacing.tsLeading})

def isOperator(tok: Token) -> bool:
    return tok.tokType in {TokType.tkOpr, TokType.tkDiv, TokType.tkMod,
                           TokType.tkShl, TokType.tkShr, TokType.tkIn,
                           TokType.tkNotin, TokType.tkIs, TokType.tkIsnot,
                           TokType.tkNot, TokType.tkOf, TokType.tkAs,
                           TokType.tkFrom, TokType.tkDotDot, TokType.tkAnd,
                           TokType.tkOr, TokType.tkXor}

def isSigilLike(tok: Token) -> bool:
    return tok.tokType == TokType.tkOpr and tok.ident and tok.ident.s[0] == '@'

def isRightAssociative(tok: Token) -> bool:
    return tok.tokType == TokType.tkOpr and tok.ident and tok.ident.s[0] == '^'

def isDotLike(tok: Token) -> bool:
    return (tok.tokType == TokType.tkOpr and tok.ident and
            len(tok.ident.s) > 1 and tok.ident.s[0] == '.' and tok.ident.s[1] != '.')

def checkBinary(p: Parser):
    if p.tok.tokType == TokType.tkOpr:
        if p.tok.spacing == {TTokenSpacing.tsTrailing}:
            parMessage(p, TMsgKind.warnInconsistentSpacing if hasattr(TMsgKind, 'warnInconsistentSpacing') else TMsgKind.warnUser, prettyTok(p.tok))

def isExprStart(p: Parser) -> bool:
    return p.tok.tokType in {
        TokType.tkSymbol, TokType.tkAccent, TokType.tkOpr, TokType.tkNot,
        TokType.tkNil, TokType.tkCast, TokType.tkIf, TokType.tkFor,
        TokType.tkProc, TokType.tkFunc, TokType.tkIterator, TokType.tkBind,
        TokType.tkParLe, TokType.tkBracketLe, TokType.tkCurlyLe,
        TokType.tkIntLit, TokType.tkInt8Lit, TokType.tkInt16Lit,
        TokType.tkInt32Lit, TokType.tkInt64Lit, TokType.tkUIntLit,
        TokType.tkUInt8Lit, TokType.tkUInt16Lit, TokType.tkUInt32Lit,
        TokType.tkUInt64Lit, TokType.tkFloatLit, TokType.tkFloat32Lit,
        TokType.tkFloat64Lit, TokType.tkFloat128Lit,
        TokType.tkStrLit, TokType.tkRStrLit, TokType.tkTripleStrLit,
        TokType.tkCharLit, TokType.tkGStrLit, TokType.tkGTripleStrLit,
        TokType.tkVar, TokType.tkRef, TokType.tkPtr,
        TokType.tkEnum, TokType.tkTuple, TokType.tkObject,
        TokType.tkWhen, TokType.tkCase, TokType.tkOut, TokType.tkTry,
        TokType.tkBlock,
        TokType.tkType, TokType.tkStatic, TokType.tkAddr,
    }


# --- Node constructors using parser line info ---
def newNodeP(kind: TNodeKind, p: Parser) -> PNode:
    return newNode(kind, parLineInfo(p))

def newIntNodeP(kind: TNodeKind, intVal: int, p: Parser) -> PNode:
    return newAtom(kind, intVal, parLineInfo(p))

def newFloatNodeP(kind: TNodeKind, floatVal: float, p: Parser) -> PNode:
    return newAtom(kind, floatVal, parLineInfo(p))

def newStrNodeP(kind: TNodeKind, strVal: str, p: Parser) -> PNode:
    return newAtom(kind, strVal, parLineInfo(p))

def newIdentNodeP(ident: PIdent, p: Parser) -> PNode:
    return newAtom(ident, parLineInfo(p))


# --- withInd context manager ---
class _withInd:
    """Context manager to save/restore p.currInd while executing parser body."""
    __slots__ = ('p', 'oldInd')
    def __init__(self, p: Parser):
        self.p = p
        self.oldInd = p.currInd
    def __enter__(self):
        self.p.currInd = self.p.tok.indent
        return self
    def __exit__(self, *args):
        self.p.currInd = self.oldInd

def withInd(p: Parser):
    return _withInd(p)


def makeCall(n: PNode) -> PNode:
    """Creates a call if the given node isn't already a call."""
    if n.kind in nkCallKinds:
        return n
    result = newNode(TNodeKind.nkCall, n.info)
    result.add(n)
    return result
