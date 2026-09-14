"""
ncompiler/lexer.py — Nim lexer (Part 1: Token types, Token, Lexer structs)
Converted from compiler/lexer.nim
The actual tokenization procs are in lexer_impl.py
"""
from __future__ import annotations
from nimic.ntypes import *
from ncompiler.nimlexbase import TBaseLexer, EndOfFile, openBaseLexer, closeBaseLexer, getColNumber, handleCRLF
from ncompiler.wordrecg import TSpecialWord
from ncompiler.idents import PIdent, IdentCache, Hash
from ncompiler.lineinfos import TLineInfo, FileIndex, TMsgKind
from ncompiler.options import ConfigRef
from ncompiler.msgs import localError, lintReport, newLineInfo, message
from ncompiler.llstream import PLLStream


class TokType(NIntEnum):
    tkInvalid=auto(); tkEof=auto(); tkComment=auto(); tkCharLit=auto()
    tkStrLit=auto(); tkRStrLit=auto(); tkTripleStrLit=auto()
    tkGStrLit=auto(); tkGTripleStrLit=auto()
    tkIntLit=auto(); tkInt8Lit=auto(); tkInt16Lit=auto()
    tkInt32Lit=auto(); tkInt64Lit=auto()
    tkUIntLit=auto(); tkUInt8Lit=auto(); tkUInt16Lit=auto()
    tkUInt32Lit=auto(); tkUInt64Lit=auto()
    tkFloatLit=auto(); tkFloat32Lit=auto(); tkFloat64Lit=auto()
    tkFloat128Lit=auto()
    tkSymbol=auto(); tkAccent=auto()
    # keywords (must be in same order as TSpecialWord after wAddr)
    tkAddr=auto(); tkAnd=auto(); tkAs=auto(); tkAsm=auto()
    tkBind=auto(); tkBlock=auto(); tkBreak=auto(); tkCase=auto()
    tkCast=auto(); tkConcept=auto(); tkConst=auto(); tkContinue=auto()
    tkConverter=auto(); tkDefer=auto(); tkDiscard=auto(); tkDistinct=auto()
    tkDiv=auto(); tkDo=auto(); tkElif=auto(); tkElse=auto()
    tkEnd=auto(); tkEnum=auto(); tkExcept=auto(); tkExport=auto()
    tkFinally=auto(); tkFor=auto(); tkFrom=auto(); tkFunc=auto()
    tkIf=auto(); tkImport=auto(); tkIn=auto(); tkInclude=auto()
    tkInterface=auto(); tkIs=auto(); tkIsnot=auto(); tkIterator=auto()
    tkLet=auto(); tkMacro=auto(); tkMethod=auto(); tkMixin=auto()
    tkMod=auto(); tkNil=auto(); tkNot=auto(); tkNotin=auto()
    tkObject=auto(); tkOf=auto(); tkOr=auto(); tkOut=auto()
    tkProc=auto(); tkPtr=auto(); tkRaise=auto(); tkRef=auto()
    tkReturn=auto(); tkShl=auto(); tkShr=auto(); tkStatic=auto()
    tkTemplate=auto(); tkTry=auto(); tkTuple=auto(); tkType=auto()
    tkUsing=auto(); tkVar=auto(); tkWhen=auto(); tkWhile=auto()
    tkXor=auto(); tkYield=auto()
    # operators
    tkColon=auto(); tkColonColon=auto(); tkEquals=auto()
    tkDot=auto(); tkDotDot=auto()
    tkOpr=auto()
    tkParLe=auto(); tkParRi=auto(); tkBracketLe=auto(); tkBracketRi=auto()
    tkCurlyLe=auto(); tkCurlyRi=auto()
    tkBracketDotLe=auto(); tkBracketDotRi=auto()
    tkCurlyDotLe=auto(); tkCurlyDotRi=auto()
    tkParDotLe=auto(); tkParDotRi=auto()
    tkComma=auto(); tkSemiColon=auto()
    tkBracketLeColon=auto()

tokKeywordLow = TokType.tkAddr
tokKeywordHigh = TokType.tkYield

TokTypes = set

class TTokenSpacing(NIntEnum):
    tsNone=auto(); tsLeading=auto(); tsTrailing=auto(); tsEof=auto()


class Token:
    __slots__ = ('tokType','indent','ident','iNumber','fNumber',
                 'base','literal','line','col','spacing')
    def __init__(self):
        self.tokType = TokType.tkInvalid
        self.indent = -1
        self.ident: PIdent|None = None
        self.iNumber: int = 0
        self.fNumber: float = 0.0
        self.base = 10
        self.literal = ""
        self.line = 0
        self.col = 0
        self.spacing: set = set()

def reset(tok: Token):
    tok.tokType = TokType.tkInvalid
    tok.indent = -1
    tok.ident = None
    tok.iNumber = 0
    tok.fNumber = 0.0
    tok.base = 10
    tok.literal = ""
    tok.line = 0
    tok.col = 0
    tok.spacing = set()


class Lexer(TBaseLexer):
    __slots__ = ('fileIdx','indentAhead','currLineIndent','cache','config')
    def __init__(self):
        super().__init__()
        self.fileIdx = FileIndex(0)
        self.indentAhead = -1
        self.currLineIndent = 0
        self.cache: IdentCache|None = None
        self.config: ConfigRef|None = None


def getLineInfo(L: Lexer) -> TLineInfo:
    return newLineInfo(L.fileIdx, L.lineNumber, getColNumber(L, L.bufpos))

def lexMessage(L: Lexer, msg: TMsgKind, arg: str = ""):
    if msg.value >= TMsgKind.errUnknown.value and msg.value <= TMsgKind.errUser.value:
        localError(L.config, getLineInfo(L), msg, arg)
    else:
        message(L.config, getLineInfo(L), msg, arg)

def lexMessagePos(L: Lexer, msg: TMsgKind, pos: int, arg: str = ""):
    info = newLineInfo(L.fileIdx, L.lineNumber, getColNumber(L, pos))
    if msg.value >= TMsgKind.errUnknown.value and msg.value <= TMsgKind.errUser.value:
        localError(L.config, info, msg, arg)
    else:
        message(L.config, info, msg, arg)

# Character sets
SymChars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff')
SymStartChars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff')
OpChars = set('+-*/<>=@$~&%|!?^.:\\')
UnaryMinusWhitelist = set(' \t\n\r,;([:{\0')

def openLexer(L: Lexer, fileIdx: FileIndex, inputstream: PLLStream,
              cache: IdentCache, config: ConfigRef):
    openBaseLexer(L, inputstream)
    L.fileIdx = fileIdx
    L.indentAhead = -1
    L.currLineIndent = 0
    L.cache = cache
    L.config = config

def closeLexer(L: Lexer):
    closeBaseLexer(L)


def prettyTok(tok: Token) -> str:
    """Return a human-readable representation of a token for error messages."""
    if tok.tokType == TokType.tkSymbol:
        return tok.ident.s if tok.ident else "???"
    if tok.tokType == TokType.tkOpr:
        return tok.ident.s if tok.ident else "operator"
    if tok.tokType in (TokType.tkIntLit, TokType.tkInt8Lit, TokType.tkInt16Lit,
                       TokType.tkInt32Lit, TokType.tkInt64Lit,
                       TokType.tkUIntLit, TokType.tkUInt8Lit, TokType.tkUInt16Lit,
                       TokType.tkUInt32Lit, TokType.tkUInt64Lit):
        return tok.literal or str(tok.iNumber)
    if tok.tokType in (TokType.tkFloatLit, TokType.tkFloat32Lit,
                       TokType.tkFloat64Lit, TokType.tkFloat128Lit):
        return tok.literal or str(tok.fNumber)
    if tok.tokType in (TokType.tkStrLit, TokType.tkRStrLit, TokType.tkTripleStrLit):
        return '"' + tok.literal + '"'
    if tok.tokType == TokType.tkCharLit:
        return "'" + tok.literal + "'"
    # For keywords, return the keyword name
    if tok.ident:
        return tok.ident.s
    return tok.tokType.name


def lexMessageTok(L: Lexer, msg: TMsgKind, tok: Token, arg: str = ""):
    """Emit a message using the token's position info."""
    from ncompiler.msgs import newLineInfo, localError, message
    info = newLineInfo(L.fileIdx, tok.line, tok.col)
    if msg.value >= TMsgKind.errUnknown.value and msg.value <= TMsgKind.errUser.value:
        localError(L.config, info, msg, arg)
    else:
        message(L.config, info, msg, arg)
