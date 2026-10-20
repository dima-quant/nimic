# /// nimic
#
# ///
#
#
#           The Nim Compiler
#        (c) Copyright 2015 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# This lexer is handwritten for efficiency. I used an elegant buffering
# scheme which I have not seen anywhere else:
# We guarantee that a whole line is in the buffer. Thus only when scanning
# the \n or \r character we have to check whether we need to read in the next
# chunk. (\n or \r already need special handling for incrementing the line
# counter; choosing both \n and \r allows the lexer to properly read Unix,
# DOS or Macintosh text files, even when it is not the native format.

from __future__ import annotations
from nimic.ntypes import *

from .options import *
from .msgs import *
from .platform import *
from .idents import *
from .nimlexbase import *
from .llstream import *
from .wordrecg import *
from .lineinfos import *
from .pathutils import *
from . import msgs        # qualified: msgs.message
from . import nimlexbase  # qualified: nimlexbase.EndOfFile

from nimic.std.hashes import *
from nimic.std.parseutils import *
from nimic.std.strutils import *

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *
    from nimic.std.formatfloat import *

with const:
    numChars: Tset[char] = Tset[char](inrange(ch('0'), ch('9')), inrange(ch('a'), ch('z')), inrange(ch('A'), ch('Z')))
    SymChars: Tset[char] = Tset[char](inrange(ch('a'), ch('z')), inrange(ch('A'), ch('Z')), inrange(ch('0'), ch('9')),
                                      inrange(ch('\x80'), ch('\xFF')))
    SymStartChars: Tset[char] = Tset[char](inrange(ch('a'), ch('z')), inrange(ch('A'), ch('Z')), inrange(ch('\x80'), ch('\xFF')))
    OpChars: Tset[char] = Tset[char]({ch('+'), ch('-'), ch('*'), ch('/'), ch('\\'), ch('<'), ch('>'), ch('!'), ch('?'), ch('^'),
                                      ch('.'), ch('|'), ch('='), ch('%'), ch('&'), ch('$'), ch('@'), ch('~'), ch(':')})
    _UnaryMinusWhitelist = Tset[char]({ch(' '), ch('\t'), ch('\n'), ch('\r'), ch(','), ch(';'), ch('('), ch('['), ch('{')})

# don't forget to update the 'highlite' module if these charsets should change


class TokType(NStrEnum):
    tkInvalid = "tkInvalid"
    tkEof = "[EOF]"  # order is important here!
    tkSymbol = "tkSymbol"  # keywords:
    tkAddr = "addr"
    tkAnd = "and"
    tkAs = "as"
    tkAsm = "asm"
    tkBind = "bind"
    tkBlock = "block"
    tkBreak = "break"
    tkCase = "case"
    tkCast = "cast"
    tkConcept = "concept"
    tkConst = "const"
    tkContinue = "continue"
    tkConverter = "converter"
    tkDefer = "defer"
    tkDiscard = "discard"
    tkDistinct = "distinct"
    tkDiv = "div"
    tkDo = "do"
    tkElif = "elif"
    tkElse = "else"
    tkEnd = "end"
    tkEnum = "enum"
    tkExcept = "except"
    tkExport = "export"
    tkFinally = "finally"
    tkFor = "for"
    tkFrom = "from"
    tkFunc = "func"
    tkIf = "if"
    tkImport = "import"
    tkIn = "in"
    tkInclude = "include"
    tkInterface = "interface"
    tkIs = "is"
    tkIsnot = "isnot"
    tkIterator = "iterator"
    tkLet = "let"
    tkMacro = "macro"
    tkMethod = "method"
    tkMixin = "mixin"
    tkMod = "mod"
    tkNil = "nil"
    tkNot = "not"
    tkNotin = "notin"
    tkObject = "object"
    tkOf = "of"
    tkOr = "or"
    tkOut = "out"
    tkProc = "proc"
    tkPtr = "ptr"
    tkRaise = "raise"
    tkRef = "ref"
    tkReturn = "return"
    tkShl = "shl"
    tkShr = "shr"
    tkStatic = "static"
    tkTemplate = "template"
    tkTry = "try"
    tkTuple = "tuple"
    tkType = "type"
    tkUsing = "using"
    tkVar = "var"
    tkWhen = "when"
    tkWhile = "while"
    tkXor = "xor"
    tkYield = "yield"  # end of keywords

    tkIntLit = "tkIntLit"
    tkInt8Lit = "tkInt8Lit"
    tkInt16Lit = "tkInt16Lit"
    tkInt32Lit = "tkInt32Lit"
    tkInt64Lit = "tkInt64Lit"
    tkUIntLit = "tkUIntLit"
    tkUInt8Lit = "tkUInt8Lit"
    tkUInt16Lit = "tkUInt16Lit"
    tkUInt32Lit = "tkUInt32Lit"
    tkUInt64Lit = "tkUInt64Lit"
    tkFloatLit = "tkFloatLit"
    tkFloat32Lit = "tkFloat32Lit"
    tkFloat64Lit = "tkFloat64Lit"
    tkFloat128Lit = "tkFloat128Lit"
    tkStrLit = "tkStrLit"
    tkRStrLit = "tkRStrLit"
    tkTripleStrLit = "tkTripleStrLit"
    tkGStrLit = "tkGStrLit"
    tkGTripleStrLit = "tkGTripleStrLit"
    tkCharLit = "tkCharLit"
    tkCustomLit = "tkCustomLit"

    tkParLe = "("
    tkParRi = ")"
    tkBracketLe = "["
    tkBracketRi = "]"
    tkCurlyLe = "{"
    tkCurlyRi = "}"
    tkBracketDotLe = "[."
    tkBracketDotRi = ".]"
    tkCurlyDotLe = "{."
    tkCurlyDotRi = ".}"
    tkParDotLe = "(."
    tkParDotRi = ".)"
    tkComma = ","
    tkSemiColon = ";"
    tkColon = ":"
    tkColonColon = "::"
    tkEquals = "="
    tkDot = "."
    tkDotDot = ".."
    tkBracketLeColon = "[:"
    tkOpr = auto()
    tkComment = auto()
    tkAccent = "`"
    # these are fake tokens used by renderer.nim
    tkSpaces = auto()
    tkInfixOpr = auto()
    tkPrefixOpr = auto()
    tkPostfixOpr = auto()
    tkHideableStart = auto()
    tkHideableEnd = auto()


class TokTypes(Tset[TokType]): pass


with const:
    _weakTokens = Tset[TokType]({TokType.tkComma, TokType.tkSemiColon, TokType.tkColon,
                                 TokType.tkParRi, TokType.tkParDotRi, TokType.tkBracketRi, TokType.tkBracketDotRi,
                                 TokType.tkCurlyRi})  # \
    # tokens that should not be considered for previousToken
    tokKeywordLow = succ(TokType.tkSymbol)
    tokKeywordHigh = pred(TokType.tkIntLit)


class NumericalBase(NIntEnum):
    base10 = auto()             # base10 is listed as the first element,
                                # so that it is the correct default value
    base2 = auto()
    base8 = auto()
    base16 = auto()


class TokenSpacing(NIntEnum):
    tsLeading = auto()
    tsTrailing = auto()
    tsEof = auto()


class Token(Object):                # a Nim token
    tokType: TokType                # the type of the token
    base: NumericalBase             # the numerical base; only valid for int
                                    # or float literals
    spacing: Tset[TokenSpacing]     # spaces around token
    indent: nint                    # the indentation; != -1 if the token has been
                                    # preceded with indentation
    ident: PIdent                   # the parsed identifier
    iNumber: BiggestInt             # the parsed integer literal
    fNumber: BiggestFloat           # the parsed floating point literal
    literal: string                 # the parsed (string) literal; and
                                    # documentation comments are here too
    line: nint
    col: nint
    if comptime(defined("nimpretty")):
        offsetA: nint  # used for pretty printing so that literals
        offsetB: nint  # like 0b01 or  r"\L" are unaffected
        commentOffsetA: nint
        commentOffsetB: nint

    def __str__(tok: Token) -> string:
        match tok.tokType:
            case _ if tok.tokType in inrange(TokType.tkIntLit, TokType.tkInt64Lit): return str(tok.iNumber)
            case _ if tok.tokType in inrange(TokType.tkFloatLit, TokType.tkFloat64Lit): return str(tok.fNumber)
            case _ if tok.tokType == TokType.tkInvalid or tok.tokType in inrange(TokType.tkStrLit, TokType.tkCharLit) or \
                    tok.tokType == TokType.tkComment: return tok.literal
            case _ if tok.tokType in inrange(TokType.tkParLe, TokType.tkColon) or tok.tokType == TokType.tkEof or \
                    tok.tokType == TokType.tkAccent: return str(tok.tokType)
            case _:
                if tok.ident is not None:
                    return tok.ident.s
                else:
                    return string("")


@calltype
def ErrorHandler(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string) -> None:
    pass


class Lexer(TBaseLexer):
    fileIdx: FileIndex
    indentAhead: nint           # if > 0 an indentation has already been read
                                # this is needed because scanning comments
                                # needs so much look-ahead
    currLineIndent: nint
    errorHandler: ErrorHandler
    cache: IdentCache
    if comptime(defined("nimsuggest")):
        _previousToken: TLineInfo
        tokenEnd: TLineInfo
        previousTokenEnd: TLineInfo
    config: ConfigRef

    def getLineInfo(L: Lexer, tok: Token) -> TLineInfo:
        """{.inline.}"""
        result = newLineInfo(L.fileIdx, tok.line, tok.col)
        if comptime(defined("nimpretty")):
            result.offsetA = tok.offsetA
            result.offsetB = tok.offsetB
            result.commentOffsetA = tok.commentOffsetA
            result.commentOffsetB = tok.commentOffsetB
        return result

    @dispatch
    def openLexer(lex: mut @ Lexer, fileIdx: FileIndex, inputstream: PLLStream,
                  cache: IdentCache, config: ConfigRef):
        lex.openBaseLexer(inputstream)
        lex.fileIdx = fileIdx
        lex.indentAhead = -1
        lex.currLineIndent = 0
        lex.lineNumber += inputstream.lineOffset
        lex.cache = cache
        if comptime(defined("nimsuggest")):
            lex._previousToken.fileIndex = fileIdx
        lex.config = config

    @dispatch
    def openLexer(lex: mut @ Lexer, filename: AbsoluteFile, inputstream: PLLStream,
                  cache: IdentCache, config: ConfigRef):
        lex.openLexer(fileInfoIdx(config, filename), inputstream, cache, config)

    def closeLexer(lex: mut @ Lexer):
        if lex.config is not None:
            lex.config.linesCompiled += lex.lineNumber
        lex.closeBaseLexer()

    def _getLineInfo(L: Lexer) -> TLineInfo:
        result = newLineInfo(L.fileIdx, L.lineNumber, L.getColNumber(L.bufpos))
        return result

    def _dispMessage(L: Lexer, info: TLineInfo, msg: TMsgKind, arg: string):
        if isNil(L.errorHandler):
            msgs.message(L.config, info, msg, arg)
        else:
            L.errorHandler(L.config, info, msg, arg)

    def lexMessage(L: Lexer, msg: TMsgKind, arg: string = string("")):
        L._dispMessage(L._getLineInfo(), msg, arg)

    def lexMessageTok(L: Lexer, msg: TMsgKind, tok: Token, arg: string = string("")):
        with var:
            info = newLineInfo(L.fileIdx, tok.line, tok.col)
        L._dispMessage(info, msg, arg)

    def _lexMessagePos(L: mut @ Lexer, msg: TMsgKind, pos: nint, arg: string = string("")):
        with var:
            info = newLineInfo(L.fileIdx, L.lineNumber, pos - L.lineStart)
        L._dispMessage(info, msg, arg)

    def _matchTwoChars(L: Lexer, first: char, second: Tset[char]) -> bool:
        result = (L.buf[L.bufpos] == first) and (L.buf[L.bufpos + 1] in second)
        return result

    @template
    @dispatch
    def _eatChar(L: mut @ Lexer, t: mut @ Token, replacementChar: char):
        t.literal.add(replacementChar)
        L.bufpos += 1

    @template
    @dispatch
    def _eatChar(L: mut @ Lexer, t: mut @ Token):
        t.literal.add(L.buf[L.bufpos])
        L.bufpos += 1

    def _handleHexChar(L: mut @ Lexer, xi: mut @ nint, position: Trange[0, 4]):
        @template
        def invalid():
            L.lexMessage(TMsgKind.errGenerated,
                         string("expected a hex digit, but found: ") + L.buf[L.bufpos] +
                         string("; maybe prepend with 0"))

        match L.buf[L.bufpos]:
            case _ if L.buf[L.bufpos] in inrange(ch('0'), ch('9')):
                xi <<= (xi << 4) | (ord(L.buf[L.bufpos]) - ord(ch('0')))
                L.bufpos += 1
            case _ if L.buf[L.bufpos] in inrange(ch('a'), ch('f')):
                xi <<= (xi << 4) | (ord(L.buf[L.bufpos]) - ord(ch('a')) + 10)
                L.bufpos += 1
            case _ if L.buf[L.bufpos] in inrange(ch('A'), ch('F')):
                xi <<= (xi << 4) | (ord(L.buf[L.bufpos]) - ord(ch('A')) + 10)
                L.bufpos += 1
            case _ if L.buf[L.bufpos] == ch('"') or L.buf[L.bufpos] == ch('\''):
                if position <= 1: invalid()
                # do not progress the bufpos here.
                if position == 0: L.bufpos += 1
            case _:
                invalid()
                # Need to progress for `nim check`
                L.bufpos += 1

    def _handleDecChars(L: mut @ Lexer, xi: mut @ nint):
        while L.buf[L.bufpos] in Tset[char](inrange(ch('0'), ch('9'))):
            xi <<= (xi * 10) + (ord(L.buf[L.bufpos]) - ord(ch('0')))
            L.bufpos += 1

    def _handleCRLF(L: mut @ Lexer, pos: nint) -> nint:
        @template
        def registerLine():
            with let:
                col = L.getColNumber(pos)

        match L.buf[pos]:
            case _ if L.buf[pos] == CR:
                registerLine()
                result = L.handleCR(pos)  # Nim: nimlexbase.handleCR(L, pos)
            case _ if L.buf[pos] == LF:
                registerLine()
                result = L.handleLF(pos)  # Nim: nimlexbase.handleLF(L, pos)
            case _: result = pos
        return result

    def _endOperator(L: mut @ Lexer, tok: mut @ Token, pos: nint,
                     hash: Hash):
        """{.inline.}"""
        with var:
            h = finish_hash(hash)
        tok.ident = L.cache.getIdent(cast[cstring](addr(L.buf[L.bufpos])), pos - L.bufpos, h)
        if (tok.ident.id < oprLow) or (tok.ident.id > oprHigh): tok.tokType = TokType.tkOpr
        else: tok.tokType = TokType(tok.ident.id - oprLow + ord(TokType.tkColon))
        L.bufpos = pos


def isKeyword(kind: TokType) -> bool:
    return (kind >= tokKeywordLow) and (kind <= tokKeywordHigh)


@template
def _ones(n) -> untyped:
    return ((1 << n) - 1)  # for utf-8 conversion


def isNimIdentifier(s: string) -> bool:
    with let:
        sLen = s.len
    if sLen > 0 and s[0] in SymStartChars:
        with var:
            i = 1
        while i < sLen:
            if s[i] == ch('_'): i += 1
            if i < sLen and s[i] not in SymChars: return False
            i += 1
        result = True
    else:
        result = False
    return result


def prettyTok(tok: Token) -> string:
    if isKeyword(tok.tokType): return string("keyword ") + tok.ident.s
    else: return str(tok)


def printTok(conf: ConfigRef, tok: Token):
    # xxx factor with toLocation
    msgWriteln(conf, str(tok.line) + string(":") + str(tok.col) + string("\t") + str(tok.tokType) + string(" ") + str(tok))


@template
def _tokenBegin(tok, pos):
    """{.dirty.}"""
    if comptime(defined("nimsuggest")):
        with var:
            colA = L.getColNumber(pos)
    if comptime(defined("nimpretty")):
        tok.offsetA = L.offsetBase + pos


@template
def _tokenEnd(tok, pos):
    """{.dirty.}"""
    if comptime(defined("nimsuggest")):
        with let:
            colB = L.getColNumber(pos) + 1
        if L.fileIdx == L.config.m.trackPos.fileIndex and L.config.m.trackPos.col in inrange(colA, colB) and \
                L.lineNumber == nint(L.config.m.trackPos.line) and L.config.ideCmd in Tset[IdeCmd]({IdeCmd.ideSug, IdeCmd.ideCon}):
            L.config.m.trackPos.col = int16(colA)
        colA = 0
    if comptime(defined("nimpretty")):
        tok.offsetB = L.offsetBase + pos


@template
def _tokenEndIgnore(tok, pos):
    if comptime(defined("nimsuggest")):
        with let:
            colB = L.getColNumber(pos)
        if L.fileIdx == L.config.m.trackPos.fileIndex and L.config.m.trackPos.col in inrange(colA, colB) and \
                L.lineNumber == nint(L.config.m.trackPos.line) and L.config.ideCmd in Tset[IdeCmd]({IdeCmd.ideSug, IdeCmd.ideCon}):
            L.config.m.trackPos.fileIndex = trackPosInvalidFileIdx
            L.config.m.trackPos.line = uint16(0)
        colA = 0
    if comptime(defined("nimpretty")):
        tok.offsetB = L.offsetBase + pos


@template
def _tokenEndPrevious(tok, pos):
    if comptime(defined("nimsuggest")):
        # when we detect the cursor in whitespace, we attach the track position
        # to the token that came before that, but only if we haven't detected
        # the cursor in a string literal or comment:
        with let:
            colB = L.getColNumber(pos)
        if L.fileIdx == L.config.m.trackPos.fileIndex and L.config.m.trackPos.col in inrange(colA, colB) and \
                L.lineNumber == nint(L.config.m.trackPos.line) and L.config.ideCmd in Tset[IdeCmd]({IdeCmd.ideSug, IdeCmd.ideCon}):
            L.config.m.trackPos = L._previousToken
            L.config.m.trackPosAttached = True
        colA = 0
    if comptime(defined("nimpretty")):
        tok.offsetB = L.offsetBase + pos


@template_expand
def _getNumber(L: mut @ Lexer, result: mut @ Token):
    def matchUnderscoreChars(L: mut @ Lexer, tok: mut @ Token, chars: Tset[char]) -> Natural:
        with var:
            pos = L.bufpos.copy()              # use registers for pos, buf
        result = 0
        while True:
            if L.buf[pos] in chars:
                tok.literal.add(L.buf[pos])
                pos += 1
                result += 1
            else:
                break
            if L.buf[pos] == ch('_'):
                if L.buf[pos + 1] not in chars:
                    L.lexMessage(TMsgKind.errGenerated,
                                 string("only single underscores may occur in a token and token may not ") +
                                 string("end with an underscore: e.g. '1__1' and '1_' are invalid"))
                    break
                tok.literal.add(ch('_'))
                pos += 1
        L.bufpos = pos
        return result

    def matchChars(L: mut @ Lexer, tok: mut @ Token, chars: Tset[char]):
        with var:
            pos = L.bufpos.copy()              # use registers for pos, buf
        while L.buf[pos] in chars:
            tok.literal.add(L.buf[pos])
            pos += 1
        L.bufpos = pos

    def lexMessageLitNum(L: mut @ Lexer, msg: string, startpos: nint, msgKind: TMsgKind = TMsgKind.errGenerated):
        # Used to get slightly human friendlier err messages.
        with const:
            literalishChars = Tset[char](inrange(ch('A'), ch('Z')), inrange(ch('a'), ch('z')), inrange(ch('0'), ch('9')),
                                         ch('_'), ch('.'), ch('\''))
        with var:
            msgPos = L.bufpos.copy()
            t = Token(literal=string(""))
        L.bufpos = startpos  # Use L.bufpos as pos because of matchChars
        matchChars(L, t, literalishChars)
        # We must verify +/- specifically so that we're not past the literal
        if L.buf[L.bufpos] in Tset[char]({ch('+'), ch('-')}) and \
                L.buf[L.bufpos - 1] in Tset[char]({ch('e'), ch('E')}):
            t.literal.add(L.buf[L.bufpos])
            L.bufpos += 1
            matchChars(L, t, literalishChars)
        if L.buf[L.bufpos] in literalishChars:
            t.literal.add(L.buf[L.bufpos])
            L.bufpos += 1
            matchChars(L, t, Tset[char](inrange(ch('0'), ch('9'))))
        L.bufpos = msgPos
        L.lexMessage(msgKind, msg % t.literal)

    def checkBitWidth(L: mut @ Lexer, base: NumericalBase, tokType: TokType,
                      numDigits: nint, startpos: nint):
        # Check bit width for non-base-10 literals
        # Warn if the digit count exceeds what can fit in the target type
        with let:
            match base:
                case NumericalBase.base2: bitsPerDigit = 1
                case NumericalBase.base8: bitsPerDigit = 3
                case NumericalBase.base16: bitsPerDigit = 4
                case _: raiseAssert(string("unreachable"))
        with let:
            match tokType:
                case TokType.tkInt8Lit | TokType.tkUInt8Lit: bitWidth = 8
                case TokType.tkInt16Lit | TokType.tkUInt16Lit: bitWidth = 16
                case TokType.tkInt32Lit | TokType.tkUInt32Lit: bitWidth = 32
                case TokType.tkInt64Lit | TokType.tkUIntLit | TokType.tkIntLit | TokType.tkUInt64Lit: bitWidth = 64
                case _: raiseAssert(string("unreachable"))
        # Maximum digits = ceil(bitWidth / bitsPerDigit) = (bitWidth + bitsPerDigit - 1) div bitsPerDigit
        with let:
            maxDigits = (bitWidth + bitsPerDigit - 1) // bitsPerDigit
        if numDigits > maxDigits:
            lexMessageLitNum(L,
                             string("number has ") + str(numDigits) + string(" digits but type only supports ") +
                             str(maxDigits) + string(" digits: '$1'"), startpos, TMsgKind.warnLongLiterals)

    with var:
        xi: BiggestInt = BiggestInt()
        isBase10 = True
        numDigits = 0
    with const:
        # 'c', 'C' is deprecated
        baseCodeChars = Tset[char]({ch('X'), ch('x'), ch('o'), ch('b'), ch('B'), ch('c'), ch('C')})
        literalishChars = baseCodeChars + Tset[char](inrange(ch('A'), ch('F')), inrange(ch('a'), ch('f')),
                                                     inrange(ch('0'), ch('9')), ch('_'), ch('\''))
        floatTypes = Tset[TokType]({TokType.tkFloatLit, TokType.tkFloat32Lit, TokType.tkFloat64Lit, TokType.tkFloat128Lit})
    result.tokType = TokType.tkIntLit   # int literal until we know better
    result.literal = string("")
    result.base = NumericalBase.base10
    _tokenBegin(result, L.bufpos)

    with var:
        isPositive = True
    if L.buf[L.bufpos] == ch('-'):
        L._eatChar(result)
        isPositive = False

    with let:
        startpos = L.bufpos.copy()

    @template
    def setNumber(field, value):
        field = (value if isPositive else -value)

    # First stage: find out base, make verifications, build token literal string
    # {'c', 'C'} is added for deprecation reasons to provide a clear error message
    if L.buf[L.bufpos] == ch('0') and L.buf[L.bufpos + 1] in baseCodeChars + Tset[char]({ch('c'), ch('C'), ch('O')}):
        isBase10 = False
        L._eatChar(result, ch('0'))
        match L.buf[L.bufpos]:
            case _ if L.buf[L.bufpos] == ch('c') or L.buf[L.bufpos] == ch('C'):
                lexMessageLitNum(L,
                                 string("$1 will soon be invalid for oct literals; Use '0o' ") +
                                 string("for octals. 'c', 'C' prefix"),
                                 startpos,
                                 TMsgKind.warnDeprecated)
                L._eatChar(result, ch('c'))
                numDigits = matchUnderscoreChars(L, result, Tset[char](inrange(ch('0'), ch('7'))))
            case _ if L.buf[L.bufpos] == ch('O'):
                lexMessageLitNum(L, string("$1 is an invalid int literal; For octal literals ") +
                                 string("use the '0o' prefix."), startpos)
            case _ if L.buf[L.bufpos] == ch('x') or L.buf[L.bufpos] == ch('X'):
                L._eatChar(result, ch('x'))
                numDigits = matchUnderscoreChars(L, result, Tset[char](inrange(ch('0'), ch('9')), inrange(ch('a'), ch('f')),
                                                                     inrange(ch('A'), ch('F'))))
            case _ if L.buf[L.bufpos] == ch('o'):
                L._eatChar(result, ch('o'))
                numDigits = matchUnderscoreChars(L, result, Tset[char](inrange(ch('0'), ch('7'))))
            case _ if L.buf[L.bufpos] == ch('b') or L.buf[L.bufpos] == ch('B'):
                L._eatChar(result, ch('b'))
                numDigits = matchUnderscoreChars(L, result, Tset[char](inrange(ch('0'), ch('1'))))
            case _:
                internalError(L.config, L._getLineInfo(), string("getNumber"))
        if numDigits == 0:
            lexMessageLitNum(L, string("invalid number: '$1'"), startpos)
    else:
        _ = matchUnderscoreChars(L, result, Tset[char](inrange(ch('0'), ch('9'))))
        if (L.buf[L.bufpos] == ch('.')) and (L.buf[L.bufpos + 1] in Tset[char](inrange(ch('0'), ch('9')))):
            result.tokType = TokType.tkFloatLit
            L._eatChar(result, ch('.'))
            _ = matchUnderscoreChars(L, result, Tset[char](inrange(ch('0'), ch('9'))))
        if L.buf[L.bufpos] in Tset[char]({ch('e'), ch('E')}):
            result.tokType = TokType.tkFloatLit
            L._eatChar(result)
            if L.buf[L.bufpos] in Tset[char]({ch('+'), ch('-')}):
                L._eatChar(result)
            _ = matchUnderscoreChars(L, result, Tset[char](inrange(ch('0'), ch('9'))))
    with let:
        endpos = L.bufpos.copy()

    # Second stage, find out if there's a datatype suffix and handle it
    with var:
        postPos = endpos.copy()

    if L.buf[postPos] in Tset[char]({ch('\''), ch('f'), ch('F'), ch('d'), ch('D'), ch('i'), ch('I'), ch('u'), ch('U')}):
        with let:
            errPos = postPos.copy()
        with var:
            customLitPossible = False
        if L.buf[postPos] == ch('\''):
            postPos += 1
            customLitPossible = True

        if L.buf[postPos] in SymChars:
            with var:
                suffix = newStringOfCap(10)
            while True:
                suffix.add(L.buf[postPos])
                postPos += 1
                if L.buf[postPos] not in SymChars + Tset[char]({ch('_')}): break
            with let:
                suffixAsLower = toLowerAscii(suffix)
            match suffixAsLower:
                case "f" | "f32": result.tokType = TokType.tkFloat32Lit
                case "d" | "f64": result.tokType = TokType.tkFloat64Lit
                case "f128": result.tokType = TokType.tkFloat128Lit
                case "i8": result.tokType = TokType.tkInt8Lit
                case "i16": result.tokType = TokType.tkInt16Lit
                case "i32": result.tokType = TokType.tkInt32Lit
                case "i64": result.tokType = TokType.tkInt64Lit
                case "u": result.tokType = TokType.tkUIntLit
                case "u8": result.tokType = TokType.tkUInt8Lit
                case "u16": result.tokType = TokType.tkUInt16Lit
                case "u32": result.tokType = TokType.tkUInt32Lit
                case "u64": result.tokType = TokType.tkUInt64Lit
                case _ if customLitPossible:
                    # remember the position of the `'` so that the parser doesn't
                    # have to reparse the custom literal:
                    result.iNumber = result.literal.len
                    result.literal.add(ch('\''))
                    result.literal.add(suffix)
                    result.tokType = TokType.tkCustomLit
                case _:
                    lexMessageLitNum(L, string("invalid number suffix: '$1'"), errPos)
        else:
            lexMessageLitNum(L, string("invalid number suffix: '$1'"), errPos)

    # Is there still a literalish char awaiting? Then it's an error!
    if L.buf[postPos] in literalishChars or \
            (L.buf[postPos] == ch('.') and L.buf[postPos + 1] in Tset[char](inrange(ch('0'), ch('9')))):
        lexMessageLitNum(L, string("invalid number: '$1'"), startpos)

    if result.tokType != TokType.tkCustomLit:
        # Third stage, extract actual number
        L.bufpos = startpos            # restore position
        with var:
            pos = startpos.copy()
        try:
            if (L.buf[pos] == ch('0')) and (L.buf[pos + 1] in baseCodeChars):
                pos += 2
                xi <<= 0                  # it is a base prefix

                match L.buf[pos - 1]:
                    case _ if L.buf[pos - 1] == ch('b') or L.buf[pos - 1] == ch('B'):
                        result.base = NumericalBase.base2
                        while pos < endpos:
                            if L.buf[pos] != ch('_'):
                                xi = (xi << 1) | (ord(L.buf[pos]) - ord(ch('0')))
                            pos += 1
                    # 'c', 'C' is deprecated (a warning is issued elsewhere)
                    case _ if L.buf[pos - 1] == ch('o') or L.buf[pos - 1] == ch('c') or L.buf[pos - 1] == ch('C'):
                        result.base = NumericalBase.base8
                        while pos < endpos:
                            if L.buf[pos] != ch('_'):
                                xi = (xi << 3) | (ord(L.buf[pos]) - ord(ch('0')))
                            pos += 1
                    case _ if L.buf[pos - 1] == ch('x') or L.buf[pos - 1] == ch('X'):
                        result.base = NumericalBase.base16
                        while pos < endpos:
                            match L.buf[pos]:
                                case _ if L.buf[pos] == ch('_'):
                                    pos += 1
                                case _ if L.buf[pos] in inrange(ch('0'), ch('9')):
                                    xi = (xi << 4) | (ord(L.buf[pos]) - ord(ch('0')))
                                    pos += 1
                                case _ if L.buf[pos] in inrange(ch('a'), ch('f')):
                                    xi = (xi << 4) | (ord(L.buf[pos]) - ord(ch('a')) + 10)
                                    pos += 1
                                case _ if L.buf[pos] in inrange(ch('A'), ch('F')):
                                    xi = (xi << 4) | (ord(L.buf[pos]) - ord(ch('A')) + 10)
                                    pos += 1
                                case _:
                                    break
                    case _:
                        internalError(L.config, L._getLineInfo(), string("getNumber"))

                match result.tokType:
                    case TokType.tkIntLit | TokType.tkInt64Lit: setNumber(result.iNumber, xi)
                    case TokType.tkInt8Lit: setNumber(result.iNumber, ashr(xi << 56, 56))
                    case TokType.tkInt16Lit: setNumber(result.iNumber, ashr(xi << 48, 48))
                    case TokType.tkInt32Lit: setNumber(result.iNumber, ashr(xi << 32, 32))
                    case TokType.tkUIntLit | TokType.tkUInt64Lit: setNumber(result.iNumber, xi)
                    case TokType.tkUInt8Lit: setNumber(result.iNumber, xi & 0xff)
                    case TokType.tkUInt16Lit: setNumber(result.iNumber, xi & 0xffff)
                    case TokType.tkUInt32Lit: setNumber(result.iNumber, xi & 0xffffffff)
                    case TokType.tkFloat32Lit:
                        setNumber(result.fNumber, (cast[ptr[float32]](addr(xi))).contents)
                        # note: this code is endian neutral!
                        # XXX: Test this on big endian machine!
                    case TokType.tkFloat64Lit | TokType.tkFloatLit:
                        setNumber(result.fNumber, (cast[ptr[float64]](addr(xi))).contents)
                    case _: internalError(L.config, L._getLineInfo(), string("getNumber"))

                # Check bit width for non-base-10 literals
                # Warn if the digit count exceeds what can fit in the target type
                if result.base != NumericalBase.base10 and \
                        result.tokType in Tset[TokType](inrange(TokType.tkIntLit, TokType.tkUInt64Lit)) and numDigits > 0:
                    checkBitWidth(L, result.base, result.tokType, numDigits, startpos)

                # Bounds checks. Non decimal literals are allowed to overflow the range of
                # the datatype as long as their pattern don't overflow _bitwise_, hence
                # below checks of signed sizes against uint*.high is deliberate:
                # (0x80'u8 = 128, 0x80'i8 = -128, etc == OK)
                if result.tokType not in floatTypes:
                    with let:
                        match result.tokType:
                            case TokType.tkUInt8Lit | TokType.tkUInt16Lit | TokType.tkUInt32Lit: outOfRange = result.iNumber != xi
                            case TokType.tkInt8Lit: outOfRange = (xi > BiggestInt(high(uint8)))
                            case TokType.tkInt16Lit: outOfRange = (xi > BiggestInt(high(uint16)))
                            case TokType.tkInt32Lit: outOfRange = (xi > BiggestInt(high(uint32)))
                            case _: outOfRange = False

                    if outOfRange:
                        #echo "out of range num: ", result.iNumber, " vs ", xi
                        lexMessageLitNum(L, string("number out of range: '$1'"), startpos)

            else:
                match result.tokType:
                    case _ if result.tokType in floatTypes:
                        result.fNumber = parseFloat(result.literal)
                    case TokType.tkUInt64Lit | TokType.tkUIntLit:
                        with var:
                            iNumber: uint64 = uint64(0)
                            len: nint = 0
                        try:
                            len = parseBiggestUInt(result.literal, iNumber)
                        except ValueError:
                            raise newException(OverflowDefect, string("number out of range: ") + result.literal)
                        if len != result.literal.len:
                            raise newException(ValueError, string("invalid integer: ") + result.literal)
                        result.iNumber = cast[int64](iNumber)
                    case _:
                        with var:
                            iNumber: int64 = int64(0)
                            len: nint = 0
                        try:
                            len = parseBiggestInt(result.literal, iNumber)
                        except ValueError:
                            raise newException(OverflowDefect, string("number out of range: ") + result.literal)
                        if len != result.literal.len:
                            raise newException(ValueError, string("invalid integer: ") + result.literal)
                        result.iNumber = iNumber

                # Explicit bounds checks.
                with let:
                    match result.tokType:
                        case TokType.tkInt8Lit: outOfRange = result.iNumber > high(int8) or result.iNumber < low(int8)
                        case TokType.tkUInt8Lit: outOfRange = result.iNumber > BiggestInt(high(uint8)) or result.iNumber < 0
                        case TokType.tkInt16Lit: outOfRange = result.iNumber > high(int16) or result.iNumber < low(int16)
                        case TokType.tkUInt16Lit: outOfRange = result.iNumber > BiggestInt(high(uint16)) or result.iNumber < 0
                        case TokType.tkInt32Lit: outOfRange = result.iNumber > high(int32) or result.iNumber < low(int32)
                        case TokType.tkUInt32Lit: outOfRange = result.iNumber > BiggestInt(high(uint32)) or result.iNumber < 0
                        case _: outOfRange = False

                if outOfRange:
                    lexMessageLitNum(L, string("number out of range: '$1'"), startpos)

            # Promote int literal to int64? Not always necessary, but more consistent
            if result.tokType == TokType.tkIntLit:
                if result.iNumber > high(int32) or result.iNumber < low(int32):
                    result.tokType = TokType.tkInt64Lit

        except ValueError:
            lexMessageLitNum(L, string("invalid number: '$1'"), startpos)
        except (OverflowDefect, RangeDefect):
            lexMessageLitNum(L, string("number out of range: '$1'"), startpos)
    _tokenEnd(result, postPos - 1)
    L.bufpos = postPos


def _addUnicodeCodePoint(s: mut @ string, i: nint):
    with let:
        _i = cast[uint](i)  # Nim: let i = cast[uint](i)
    # inlined toUTF-8 to avoid unicode and strutils dependencies.
    with let:
        pos = s.len
    if _i <= 127:
        s.setLen(pos + 1)
        s[pos + 0] = chr(_i)
    elif _i <= 0x07FF:
        s.setLen(pos + 2)
        s[pos + 0] = chr((_i >> 6) | 0b110_00000)
        s[pos + 1] = chr((_i & _ones(6)) | 0b10_0000_00)
    elif _i <= 0xFFFF:
        s.setLen(pos + 3)
        s[pos + 0] = chr(_i >> 12 | 0b1110_0000)
        s[pos + 1] = chr(_i >> 6 & _ones(6) | 0b10_0000_00)
        s[pos + 2] = chr(_i & _ones(6) | 0b10_0000_00)
    elif _i <= 0x001FFFFF:
        s.setLen(pos + 4)
        s[pos + 0] = chr(_i >> 18 | 0b1111_0000)
        s[pos + 1] = chr(_i >> 12 & _ones(6) | 0b10_0000_00)
        s[pos + 2] = chr(_i >> 6 & _ones(6) | 0b10_0000_00)
        s[pos + 3] = chr(_i & _ones(6) | 0b10_0000_00)
    elif _i <= 0x03FFFFFF:
        s.setLen(pos + 5)
        s[pos + 0] = chr(_i >> 24 | 0b111110_00)
        s[pos + 1] = chr(_i >> 18 & _ones(6) | 0b10_0000_00)
        s[pos + 2] = chr(_i >> 12 & _ones(6) | 0b10_0000_00)
        s[pos + 3] = chr(_i >> 6 & _ones(6) | 0b10_0000_00)
        s[pos + 4] = chr(_i & _ones(6) | 0b10_0000_00)
    elif _i <= 0x7FFFFFFF:
        s.setLen(pos + 6)
        s[pos + 0] = chr(_i >> 30 | 0b1111110_0)
        s[pos + 1] = chr(_i >> 24 & _ones(6) | 0b10_0000_00)
        s[pos + 2] = chr(_i >> 18 & _ones(6) | 0b10_0000_00)
        s[pos + 3] = chr(_i >> 12 & _ones(6) | 0b10_0000_00)
        s[pos + 4] = chr(_i >> 6 & _ones(6) | 0b10_0000_00)
        s[pos + 5] = chr(_i & _ones(6) | 0b10_0000_00)


def _getEscapedChar(L: mut @ Lexer, tok: mut @ Token):
    L.bufpos += 1               # skip '\'
    match L.buf[L.bufpos]:
        case _ if L.buf[L.bufpos] == ch('n') or L.buf[L.bufpos] == ch('N'):
            tok.literal.add(ch('\n'))
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('p') or L.buf[L.bufpos] == ch('P'):
            if tok.tokType == TokType.tkCharLit:
                L.lexMessage(TMsgKind.errGenerated, string("\\p not allowed in character literal"))
            tok.literal.add(L.config.target.tnl)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('r') or L.buf[L.bufpos] == ch('R') or L.buf[L.bufpos] == ch('c') or \
                L.buf[L.bufpos] == ch('C'):
            tok.literal.add(CR)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('l') or L.buf[L.bufpos] == ch('L'):
            tok.literal.add(LF)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('f') or L.buf[L.bufpos] == ch('F'):
            tok.literal.add(FF)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('e') or L.buf[L.bufpos] == ch('E'):
            tok.literal.add(ESC)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('a') or L.buf[L.bufpos] == ch('A'):
            tok.literal.add(BEL)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('b') or L.buf[L.bufpos] == ch('B'):
            tok.literal.add(BACKSPACE)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('v') or L.buf[L.bufpos] == ch('V'):
            tok.literal.add(VT)
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('t') or L.buf[L.bufpos] == ch('T'):
            tok.literal.add(ch('\t'))
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('\'') or L.buf[L.bufpos] == ch('"'):
            tok.literal.add(L.buf[L.bufpos])
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('\\'):
            tok.literal.add(ch('\\'))
            L.bufpos += 1
        case _ if L.buf[L.bufpos] == ch('x') or L.buf[L.bufpos] == ch('X'):
            L.bufpos += 1
            with var:
                xi = nint(0)
            L._handleHexChar(xi, 1)
            L._handleHexChar(xi, 2)
            tok.literal.add(chr(xi))
        case _ if L.buf[L.bufpos] == ch('u') or L.buf[L.bufpos] == ch('U'):
            if tok.tokType == TokType.tkCharLit:
                L.lexMessage(TMsgKind.errGenerated, string("\\u not allowed in character literal"))
            L.bufpos += 1
            with var:
                xi = nint(0)
            if L.buf[L.bufpos] == ch('{'):
                L.bufpos += 1
                with var:
                    start = L.bufpos.copy()
                while L.buf[L.bufpos] != ch('}'):
                    L._handleHexChar(xi, 0)
                if start == L.bufpos:
                    L.lexMessage(TMsgKind.errGenerated,
                                 string("Unicode codepoint cannot be empty"))
                L.bufpos += 1
                if xi > 0x10FFFF:
                    with let:
                        hex = str(L.buf)[start:L.bufpos - 1]  # Nim: ($L.buf)[start..L.bufpos-2]
                    L.lexMessage(TMsgKind.errGenerated,
                                 string("Unicode codepoint must be lower than 0x10FFFF, but was: ") + hex)
            else:
                L._handleHexChar(xi, 1)
                L._handleHexChar(xi, 2)
                L._handleHexChar(xi, 3)
                L._handleHexChar(xi, 4)
            _addUnicodeCodePoint(tok.literal, xi)
        case _ if L.buf[L.bufpos] in inrange(ch('0'), ch('9')):
            if L._matchTwoChars(ch('0'), Tset[char](inrange(ch('0'), ch('9')))):
                L.lexMessage(TMsgKind.warnOctalEscape)
            with var:
                xi = nint(0)
            L._handleDecChars(xi)
            if (xi <= 255): tok.literal.add(chr(xi))
            else: L.lexMessage(TMsgKind.errGenerated, string("invalid character constant"))
        case _: L.lexMessage(TMsgKind.errGenerated, string("invalid character constant"))


class _StringMode(NIntEnum):
    normal = auto()
    raw = auto()
    generalized = auto()


def _getString(L: mut @ Lexer, tok: mut @ Token, mode: _StringMode):
    with var:
        pos = L.bufpos.copy()
        line = L.lineNumber.copy()         # save linenumber for better error message
    _tokenBegin(tok, pos - ord(mode == _StringMode.raw))
    pos += 1  # skip "
    if L.buf[pos] == ch('"') and L.buf[pos + 1] == ch('"'):
        tok.tokType = TokType.tkTripleStrLit  # long string literal:
        pos += 2               # skip ""
        # skip leading newline:
        if L.buf[pos] in Tset[char]({ch(' '), ch('\t')}):
            with var:
                newpos = pos + 1
            while L.buf[newpos] in Tset[char]({ch(' '), ch('\t')}): newpos += 1
            if L.buf[newpos] in Tset[char]({CR, LF}): pos = newpos
        pos = L._handleCRLF(pos)
        while True:
            match L.buf[pos]:
                case _ if L.buf[pos] == ch('"'):
                    if L.buf[pos + 1] == ch('"') and L.buf[pos + 2] == ch('"') and \
                            L.buf[pos + 3] != ch('"'):
                        _tokenEndIgnore(tok, pos + 2)
                        L.bufpos = pos + 3  # skip the three """
                        break
                    tok.literal.add(ch('"'))
                    pos += 1
                case _ if L.buf[pos] == CR or L.buf[pos] == LF:
                    _tokenEndIgnore(tok, pos)
                    pos = L._handleCRLF(pos)
                    tok.literal.add(string("\n"))
                case _ if L.buf[pos] == nimlexbase.EndOfFile:
                    _tokenEndIgnore(tok, pos)
                    with var:
                        line2 = L.lineNumber.copy()
                    L.lineNumber = line
                    L._lexMessagePos(TMsgKind.errGenerated, L.lineStart, string("closing \"\"\" expected, but end of file reached"))
                    L.lineNumber = line2
                    L.bufpos = pos
                    break
                case _:
                    tok.literal.add(L.buf[pos])
                    pos += 1
    else:
        # ordinary string literal
        if mode != _StringMode.normal: tok.tokType = TokType.tkRStrLit
        else: tok.tokType = TokType.tkStrLit
        while True:
            with let:
                c = L.buf[pos]
            if c == ch('"'):
                if mode != _StringMode.normal and L.buf[pos + 1] == ch('"'):
                    pos += 2
                    tok.literal.add(ch('"'))
                else:
                    _tokenEndIgnore(tok, pos)
                    pos += 1  # skip '"'
                    break
            elif c in Tset[char]({CR, LF, nimlexbase.EndOfFile}):
                _tokenEndIgnore(tok, pos)
                L.lexMessage(TMsgKind.errGenerated, string("closing \" expected"))
                break
            elif (c == ch('\\')) and mode == _StringMode.normal:
                L.bufpos = pos
                _getEscapedChar(L, tok)
                pos = L.bufpos.copy()
            else:
                tok.literal.add(c)
                pos += 1
        L.bufpos = pos


def _getCharacter(L: mut @ Lexer, tok: mut @ Token):
    _tokenBegin(tok, L.bufpos)
    with let:
        startPos = L.bufpos.copy()
    L.bufpos += 1               # skip '
    with let:
        c = L.buf[L.bufpos]
    match c:
        case _ if c in inrange(ch('\0'), pred(ch(' '))) or c == ch('\''):
            L.lexMessage(TMsgKind.errGenerated, string("invalid character literal"))
            tok.literal = string(str(c))
        case _ if c == ch('\\'): _getEscapedChar(L, tok)
        case _:
            tok.literal = string(str(c))
            L.bufpos += 1
    if L.buf[L.bufpos] == ch('\''):
        _tokenEndIgnore(tok, L.bufpos)
        L.bufpos += 1               # skip '
    else:
        if startPos > 0 and L.buf[startPos - 1] == ch('`'):
            tok.literal = string("'")
            L.bufpos = startPos + 1
        else:
            L.lexMessage(TMsgKind.errGenerated, string("missing closing ' for character literal"))
        _tokenEndIgnore(tok, L.bufpos)


with const:
    _UnicodeOperatorStartChars = Tset[char]({ch('\xe2'), ch('\xc2'), ch('\xc3')})
    # the allowed unicode characters ("∙ ∘ × ★ ⊗ ⊘ ⊙ ⊛ ⊠ ⊡ ∩ ∧ ⊓ ± ⊕ ⊖ ⊞ ⊟ ∪ ∨ ⊔")
    # all start with one of these.


class _UnicodeOprPred(NIntEnum):
    Mul = auto()
    Add = auto()


def _unicodeOprLen(buf: cstring, pos: nint) -> tuple[int8, _UnicodeOprPred]:
    @template
    def m(len) -> untyped:
        return (int8(len), _UnicodeOprPred.Mul)

    @template
    def a(len) -> untyped:
        return (int8(len), _UnicodeOprPred.Add)
    result = m(0)
    match buf[pos]:
        case _ if buf[pos] == ch('\xe2'):
            if buf[pos + 1] == ch('\x88'):
                if buf[pos + 2] == ch('\x98'): result = m(3)  # ∘
                elif buf[pos + 2] == ch('\x99'): result = m(3)  # ∙
                elif buf[pos + 2] == ch('\xa7'): result = m(3)  # ∧
                elif buf[pos + 2] == ch('\xa8'): result = a(3)  # ∨
                elif buf[pos + 2] == ch('\xa9'): result = m(3)  # ∩
                elif buf[pos + 2] == ch('\xaa'): result = a(3)  # ∪
            elif buf[pos + 1] == ch('\x8a'):
                if buf[pos + 2] == ch('\x93'): result = m(3)  # ⊓
                elif buf[pos + 2] == ch('\x94'): result = a(3)  # ⊔
                elif buf[pos + 2] == ch('\x95'): result = a(3)  # ⊕
                elif buf[pos + 2] == ch('\x96'): result = a(3)  # ⊖
                elif buf[pos + 2] == ch('\x97'): result = m(3)  # ⊗
                elif buf[pos + 2] == ch('\x98'): result = m(3)  # ⊘
                elif buf[pos + 2] == ch('\x99'): result = m(3)  # ⊙
                elif buf[pos + 2] == ch('\x9b'): result = m(3)  # ⊛
                elif buf[pos + 2] == ch('\x9e'): result = a(3)  # ⊞
                elif buf[pos + 2] == ch('\x9f'): result = a(3)  # ⊟
                elif buf[pos + 2] == ch('\xa0'): result = m(3)  # ⊠
                elif buf[pos + 2] == ch('\xa1'): result = m(3)  # ⊡
            elif buf[pos + 1] == ch('\x98') and buf[pos + 2] == ch('\x85'): result = m(3)  # ★
        case _ if buf[pos] == ch('\xc2'):
            if buf[pos + 1] == ch('\xb1'): result = a(2)  # ±
        case _ if buf[pos] == ch('\xc3'):
            if buf[pos + 1] == ch('\x97'): result = m(2)  # ×
        case _:
            pass
    return result


def _getSymbol(L: mut @ Lexer, tok: mut @ Token):
    with var:
        h: Hash = Hash(0)
        pos = L.bufpos.copy()
    _tokenBegin(tok, pos)
    with var:
        suspicious = False
    while True:
        with var:
            c = L.buf[pos]
        match c:
            case _ if c in inrange(ch('a'), ch('z')) or c in inrange(ch('0'), ch('9')):
                h = mix_hash(h, ord(c))
                pos += 1
            case _ if c in inrange(ch('A'), ch('Z')):
                c = chr(ord(c) + (ord(ch('a')) - ord(ch('A'))))  # toLower()
                h = mix_hash(h, ord(c))
                pos += 1
                suspicious = True
            case _ if c == ch('_'):
                if L.buf[pos + 1] not in SymChars:
                    L.lexMessage(TMsgKind.errGenerated, string("invalid token: trailing underscore"))
                    break
                pos += 1
                suspicious = True
            case _ if c in inrange(ch('\x80'), ch('\xFF')):
                if c in _UnicodeOperatorStartChars and _unicodeOprLen(L.buf, pos)[0] != 0:
                    break
                else:
                    h = mix_hash(h, ord(c))
                    pos += 1
            case _: break
    _tokenEnd(tok, pos - 1)
    h = finish_hash(h)
    tok.ident = L.cache.getIdent(cast[cstring](addr(L.buf[L.bufpos])), pos - L.bufpos, h)
    if (tok.ident.id < ord(tokKeywordLow) - ord(TokType.tkSymbol)) or \
            (tok.ident.id > ord(tokKeywordHigh) - ord(TokType.tkSymbol)):
        tok.tokType = TokType.tkSymbol
    else:
        tok.tokType = TokType(tok.ident.id + ord(TokType.tkSymbol))
        if suspicious and Tset[TGlobalOption]({TGlobalOption.optStyleHint, TGlobalOption.optStyleError,
                                               TGlobalOption.optStyleWarning}) * L.config.globalOptions != Tset[TGlobalOption]():
            lintReport(L.config, L._getLineInfo(), normalize(tok.ident.s), tok.ident.s)
    L.bufpos = pos


def _getOperator(L: mut @ Lexer, tok: mut @ Token):
    with var:
        pos = L.bufpos.copy()
    _tokenBegin(tok, pos)
    with var:
        h: Hash = Hash(0)
    while True:
        with let:
            c = L.buf[pos]
        if c in OpChars:
            h = mix_hash(h, ord(c))
            pos += 1
        elif c in _UnicodeOperatorStartChars:
            with let:
                oprLen = _unicodeOprLen(L.buf, pos)[0]
            if oprLen == 0: break
            for i in range(0, oprLen):
                h = mix_hash(h, ord(L.buf[pos]))
                pos += 1
        else:
            break
    L._endOperator(tok, pos, h)
    _tokenEnd(tok, pos - 1)
    # advance pos but don't store it in L.bufpos so the next token (which might
    # be an operator too) gets the preceding spaces:
    tok.spacing = tok.spacing - Tset[TokenSpacing]({TokenSpacing.tsTrailing, TokenSpacing.tsEof})
    with var:
        trailing = False
    while L.buf[pos] == ch(' '):
        pos += 1
        trailing = True
    if L.buf[pos] in Tset[char]({CR, LF, nimlexbase.EndOfFile}):
        tok.spacing.incl(TokenSpacing.tsEof)
    elif trailing:
        tok.spacing.incl(TokenSpacing.tsTrailing)


@dispatch
@template_expand
def getPrecedence(tok: Token) -> nint:
    """Calculates the precedence of the given token."""
    with const:
        MulPred = 9
        PlusPred = 8
    match tok.tokType:
        case TokType.tkOpr:
            with let:
                relevantChar = tok.ident.s[0]

            # arrow like?
            if tok.ident.s.len > 1 and tok.ident.s[back(1)] == ch('>') and \
                    tok.ident.s[back(2)] in Tset[char]({ch('-'), ch('~'), ch('=')}): return 0

            @template
            def considerAsgn(value: untyped):
                result = (1 if tok.ident.s[back(1)] == ch('=') else value)

            match relevantChar:
                case _ if relevantChar == ch('$') or relevantChar == ch('^'): considerAsgn(10)
                case _ if relevantChar == ch('*') or relevantChar == ch('%') or relevantChar == ch('/') or \
                        relevantChar == ch('\\'): considerAsgn(MulPred)
                case _ if relevantChar == ch('~'): result = 8
                case _ if relevantChar == ch('+') or relevantChar == ch('-') or relevantChar == ch('|'): considerAsgn(PlusPred)
                case _ if relevantChar == ch('&'): considerAsgn(7)
                case _ if relevantChar == ch('=') or relevantChar == ch('<') or relevantChar == ch('>') or \
                        relevantChar == ch('!'): result = 5
                case _ if relevantChar == ch('.'): considerAsgn(6)
                case _ if relevantChar == ch('?'): result = 2
                case _ if relevantChar in _UnicodeOperatorStartChars:
                    if tok.ident.s[back(1)] == ch('='):
                        result = 1
                    else:
                        with let:
                            (len, pred) = _unicodeOprLen(cstring(tok.ident.s), 0)
                        if len != 0:
                            result = (MulPred if pred == _UnicodeOprPred.Mul else PlusPred)
                        else:
                            result = 2
                case _: considerAsgn(2)
        case TokType.tkDiv | TokType.tkMod | TokType.tkShl | TokType.tkShr: result = 9
        case TokType.tkDotDot: result = 6
        case TokType.tkIn | TokType.tkNotin | TokType.tkIs | TokType.tkIsnot | TokType.tkOf | TokType.tkAs | \
                TokType.tkFrom: result = 5
        case TokType.tkAnd: result = 4
        case TokType.tkOr | TokType.tkXor | TokType.tkPtr | TokType.tkRef: result = 3
        case _: return -10
    return result


def _skipMultiLineComment(L: mut @ Lexer, tok: mut @ Token, start: nint,
                          isDoc: bool):
    with var:
        pos = start.copy()
        toStrip = 0
    _tokenBegin(tok, pos)
    # detect the amount of indentation:
    if isDoc:
        toStrip = L.getColNumber(pos)
        while L.buf[pos] == ch(' '):
            pos += 1
            toStrip += 1
        while L.buf[pos] in Tset[char]({CR, LF}):  # skip blank lines
            pos = L._handleCRLF(pos)
            toStrip = 0
            while L.buf[pos] == ch(' '):
                pos += 1
                toStrip += 1
    with var:
        nesting = 0
    while True:
        match L.buf[pos]:
            case _ if L.buf[pos] == ch('#'):
                if isDoc:
                    if L.buf[pos + 1] == ch('#') and L.buf[pos + 2] == ch('['):
                        nesting += 1
                    tok.literal.add(ch('#'))
                elif L.buf[pos + 1] == ch('['):
                    nesting += 1
                pos += 1
            case _ if L.buf[pos] == ch(']'):
                if isDoc:
                    if L.buf[pos + 1] == ch('#') and L.buf[pos + 2] == ch('#'):
                        if nesting == 0:
                            _tokenEndIgnore(tok, pos + 2)
                            pos += 3
                            break
                        nesting -= 1
                    tok.literal.add(ch(']'))
                elif L.buf[pos + 1] == ch('#'):
                    if nesting == 0:
                        _tokenEndIgnore(tok, pos + 1)
                        pos += 2
                        break
                    nesting -= 1
                pos += 1
            case _ if L.buf[pos] == CR or L.buf[pos] == LF:
                _tokenEndIgnore(tok, pos)
                pos = L._handleCRLF(pos)
                # strip leading whitespace:
                if comptime(defined("nimpretty")): tok.literal.add(string("\n"))
                if isDoc:
                    if comptime(not defined("nimpretty")): tok.literal.add(string("\n"))
                    with var:
                        c = toStrip
                    while L.buf[pos] == ch(' ') and c > 0:
                        pos += 1
                        c -= 1
            case _ if L.buf[pos] == nimlexbase.EndOfFile:
                _tokenEndIgnore(tok, pos)
                L._lexMessagePos(TMsgKind.errGenerated, pos, string("end of multiline comment expected"))
                break
            case _:
                if isDoc or defined("nimpretty"): tok.literal.add(L.buf[pos])
                pos += 1
    L.bufpos = pos
    if comptime(defined("nimpretty")):
        tok.commentOffsetB = L.offsetBase + pos - 1


def _scanComment(L: mut @ Lexer, tok: mut @ Token):
    with var:
        pos = L.bufpos.copy()
    tok.tokType = TokType.tkComment
    assert L.buf[pos + 1] == ch('#')
    if comptime(defined("nimpretty")):
        tok.commentOffsetA = L.offsetBase + pos

    if L.buf[pos + 2] == ch('['):
        _skipMultiLineComment(L, tok, pos + 3, True)
        return
    _tokenBegin(tok, pos)
    pos += 2

    with var:
        toStrip = 0
        stripInit = False

    while True:
        if not stripInit:  # find baseline indentation inside comment
            while L.buf[pos] == ch(' '):
                pos += 1
                toStrip += 1
            if L.buf[pos] in Tset[char]({CR, LF}):  # don't set toStrip in blank comment lines
                toStrip = 0
            else:  # found first non-whitespace character
                stripInit = True
        while L.buf[pos] not in Tset[char]({CR, LF, nimlexbase.EndOfFile}):
            tok.literal.add(L.buf[pos])
            pos += 1
        _tokenEndIgnore(tok, pos)
        pos = L._handleCRLF(pos)
        with var:
            indent = 0
        while L.buf[pos] == ch(' '):
            pos += 1
            indent += 1

        if L.buf[pos] == ch('#') and L.buf[pos + 1] == ch('#'):
            tok.literal.add(string("\n"))
            pos += 2
            if stripInit:
                with var:
                    c = toStrip
                while L.buf[pos] == ch(' ') and c > 0:
                    pos += 1
                    c -= 1
        else:
            if L.buf[pos] > ch(' '):
                L.indentAhead = indent
            _tokenEndIgnore(tok, pos)
            break
    L.bufpos = pos
    if comptime(defined("nimpretty")):
        tok.commentOffsetB = L.offsetBase + pos - 1


def _skip(L: mut @ Lexer, tok: mut @ Token):
    with var:
        pos = L.bufpos.copy()
    _tokenBegin(tok, pos)
    tok.spacing.excl(TokenSpacing.tsLeading)
    if comptime(defined("nimpretty")):
        with var:
            hasComment = False
            commentIndent = L.currLineIndent.copy()
        tok.commentOffsetA = L.offsetBase + pos
        tok.commentOffsetB = tok.commentOffsetA
        tok.line = -1
    while True:
        match L.buf[pos]:
            case _ if L.buf[pos] == ch(' '):
                pos += 1
                tok.spacing.incl(TokenSpacing.tsLeading)
            case _ if L.buf[pos] == ch('\t'):
                L._lexMessagePos(TMsgKind.errGenerated, pos, string("tabs are not allowed, use spaces instead"))
                pos += 1
            case _ if L.buf[pos] == CR or L.buf[pos] == LF:
                _tokenEndPrevious(tok, pos)
                pos = L._handleCRLF(pos)
                with var:
                    indent = 0
                while True:
                    if L.buf[pos] == ch(' '):
                        pos += 1
                        indent += 1
                    elif L.buf[pos] == ch('#') and L.buf[pos + 1] == ch('['):
                        if comptime(defined("nimpretty")):
                            hasComment = True
                            if tok.line < 0:
                                tok.line = L.lineNumber
                                commentIndent = indent
                        _skipMultiLineComment(L, tok, pos + 2, False)
                        pos = L.bufpos.copy()
                    else:
                        break
                tok.spacing.excl(TokenSpacing.tsLeading)
                if comptime(defined("nimpretty")):
                    if L.buf[pos] == ch('#') and tok.line < 0: commentIndent = indent
                if L.buf[pos] > ch(' ') and (L.buf[pos] != ch('#') or L.buf[pos + 1] == ch('#')):
                    tok.indent = indent
                    L.currLineIndent = indent
                    break
            case _ if L.buf[pos] == ch('#'):
                # do not skip documentation comment:
                if L.buf[pos + 1] == ch('#'): break
                if comptime(defined("nimpretty")):
                    hasComment = True
                    if tok.line < 0:
                        tok.line = L.lineNumber

                if L.buf[pos + 1] == ch('['):
                    _skipMultiLineComment(L, tok, pos + 2, False)
                    pos = L.bufpos.copy()
                else:
                    _tokenBegin(tok, pos)
                    while L.buf[pos] not in Tset[char]({CR, LF, nimlexbase.EndOfFile}):
                        if comptime(defined("nimpretty")): tok.literal.add(L.buf[pos])
                        pos += 1
                    _tokenEndIgnore(tok, pos + 1)
                    if comptime(defined("nimpretty")):
                        tok.commentOffsetB = L.offsetBase + pos + 1
            case _:
                break                   # EndOfFile also leaves the loop
    _tokenEndPrevious(tok, pos - 1)
    L.bufpos = pos
    if comptime(defined("nimpretty")):
        if hasComment:
            tok.commentOffsetB = L.offsetBase + pos - 1
            tok.tokType = TokType.tkComment
            tok.indent = commentIndent


def rawGetTok(L: mut @ Lexer, tok: mut @ Token):
    @template
    def atTokenEnd():
        """{.dirty.}"""
        if comptime(defined("nimsuggest")):
            L.previousTokenEnd.line = L.tokenEnd.line
            L.previousTokenEnd.col = L.tokenEnd.col
            L.tokenEnd.line = uint16(tok.line)
            L.tokenEnd.col = int16(L.getColNumber(L.bufpos))
            # we attach the cursor to the last *strong* token
            if tok.tokType not in _weakTokens:
                L._previousToken.line = uint16(tok.line)
                L._previousToken.col = int16(tok.col)

    reset(tok)
    if L.indentAhead >= 0:
        tok.indent = L.indentAhead
        L.currLineIndent = L.indentAhead
        L.indentAhead = -1
    else:
        tok.indent = -1
    _skip(L, tok)
    if comptime(defined("nimpretty")):
        if tok.tokType == TokType.tkComment:
            L.indentAhead = L.currLineIndent
            return
    with let:
        c = L.buf[L.bufpos]
    tok.line = L.lineNumber
    tok.col = L.getColNumber(L.bufpos)
    if c in SymStartChars - Tset[char]({ch('r'), ch('R')}) - _UnicodeOperatorStartChars:
        _getSymbol(L, tok)
    else:
        match c:
            case _ if c in _UnicodeOperatorStartChars:
                if _unicodeOprLen(L.buf, L.bufpos)[0] != 0:
                    _getOperator(L, tok)
                else:
                    _getSymbol(L, tok)
            case _ if c == ch('#'):
                _scanComment(L, tok)
            case _ if c == ch('*'):
                # '*:' is unfortunately a special case, because it is two tokens in
                # 'var v*: int'.
                if L.buf[L.bufpos + 1] == ch(':') and L.buf[L.bufpos + 2] not in OpChars:
                    with var:
                        h = mix_hash(0, ord(ch('*')))
                    L._endOperator(tok, L.bufpos + 1, h)
                else:
                    _getOperator(L, tok)
            case _ if c == ch(','):
                tok.tokType = TokType.tkComma
                L.bufpos += 1
            case _ if c == ch('r') or c == ch('R'):
                if L.buf[L.bufpos + 1] == ch('"'):
                    L.bufpos += 1
                    _getString(L, tok, _StringMode.raw)
                else:
                    _getSymbol(L, tok)
            case _ if c == ch('('):
                L.bufpos += 1
                if L.buf[L.bufpos] == ch('.') and L.buf[L.bufpos + 1] != ch('.'):
                    tok.tokType = TokType.tkParDotLe
                    L.bufpos += 1
                else:
                    tok.tokType = TokType.tkParLe
                    if comptime(defined("nimsuggest")):
                        if L.fileIdx == L.config.m.trackPos.fileIndex and tok.col < L.config.m.trackPos.col and \
                                tok.line == nint(L.config.m.trackPos.line) and L.config.ideCmd == IdeCmd.ideCon:
                            L.config.m.trackPos.col = int16(tok.col)
            case _ if c == ch(')'):
                tok.tokType = TokType.tkParRi
                L.bufpos += 1
            case _ if c == ch('['):
                L.bufpos += 1
                if L.buf[L.bufpos] == ch('.') and L.buf[L.bufpos + 1] != ch('.'):
                    tok.tokType = TokType.tkBracketDotLe
                    L.bufpos += 1
                elif L.buf[L.bufpos] == ch(':'):
                    tok.tokType = TokType.tkBracketLeColon
                    L.bufpos += 1
                else:
                    tok.tokType = TokType.tkBracketLe
            case _ if c == ch(']'):
                tok.tokType = TokType.tkBracketRi
                L.bufpos += 1
            case _ if c == ch('.'):
                if comptime(defined("nimsuggest")):
                    if L.fileIdx == L.config.m.trackPos.fileIndex and tok.col + 1 == L.config.m.trackPos.col and \
                            tok.line == nint(L.config.m.trackPos.line) and L.config.ideCmd == IdeCmd.ideSug:
                        tok.tokType = TokType.tkDot
                        L.config.m.trackPos.col = int16(tok.col)
                        L.bufpos += 1
                        atTokenEnd()
                        return
                if L.buf[L.bufpos + 1] == ch(']'):
                    tok.tokType = TokType.tkBracketDotRi
                    L.bufpos += 2
                elif L.buf[L.bufpos + 1] == ch('}'):
                    tok.tokType = TokType.tkCurlyDotRi
                    L.bufpos += 2
                elif L.buf[L.bufpos + 1] == ch(')'):
                    tok.tokType = TokType.tkParDotRi
                    L.bufpos += 2
                else:
                    _getOperator(L, tok)
            case _ if c == ch('{'):
                L.bufpos += 1
                if L.buf[L.bufpos] == ch('.') and L.buf[L.bufpos + 1] != ch('.'):
                    tok.tokType = TokType.tkCurlyDotLe
                    L.bufpos += 1
                else:
                    tok.tokType = TokType.tkCurlyLe
            case _ if c == ch('}'):
                tok.tokType = TokType.tkCurlyRi
                L.bufpos += 1
            case _ if c == ch(';'):
                tok.tokType = TokType.tkSemiColon
                L.bufpos += 1
            case _ if c == ch('`'):
                tok.tokType = TokType.tkAccent
                L.bufpos += 1
            case _ if c == ch('_'):
                L.bufpos += 1
                if L.buf[L.bufpos] not in SymChars + Tset[char]({ch('_')}):
                    tok.tokType = TokType.tkSymbol
                    tok.ident = L.cache.getIdent(string("_"))
                else:
                    tok.literal = string(str(c))
                    tok.tokType = TokType.tkInvalid
                    L.lexMessage(TMsgKind.errGenerated, string("invalid token: ") + c + string(" (\\") + str(ord(c)) + ch(')'))
            case _ if c == ch('"'):
                # check for generalized raw string literal:
                with let:
                    mode = (_StringMode.generalized if L.bufpos > 0 and L.buf[L.bufpos - 1] in SymChars else _StringMode.normal)
                _getString(L, tok, mode)
                if mode == _StringMode.generalized:
                    # tkRStrLit -> tkGStrLit
                    # tkTripleStrLit -> tkGTripleStrLit
                    tok.tokType = succ(tok.tokType, 2)  # Nim: inc(tok.tokType, 2)
            case _ if c == ch('\''):
                tok.tokType = TokType.tkCharLit
                _getCharacter(L, tok)
                tok.tokType = TokType.tkCharLit
            case _ if c in inrange(ch('0'), ch('9')):
                _getNumber(L, tok)
                with let:
                    c = L.buf[L.bufpos]
                if c in SymChars + Tset[char]({ch('_')}):
                    if c in _UnicodeOperatorStartChars and \
                            _unicodeOprLen(L.buf, L.bufpos)[0] != 0:
                        pass
                    else:
                        L.lexMessage(TMsgKind.errGenerated, string("invalid token: no whitespace between number and identifier"))
            case _ if c == ch('-'):
                if L.buf[L.bufpos + 1] in Tset[char](inrange(ch('0'), ch('9'))) and \
                        (L.bufpos - 1 == 0 or L.buf[L.bufpos - 1] in _UnaryMinusWhitelist):
                    # x)-23 # binary minus
                    # ,-23  # unary minus
                    # \n-78 # unary minus? Yes.
                    # =-3   # parsed as `=-` anyway
                    _getNumber(L, tok)
                    with let:
                        c = L.buf[L.bufpos]
                    if c in SymChars + Tset[char]({ch('_')}):
                        if c in _UnicodeOperatorStartChars and \
                                _unicodeOprLen(L.buf, L.bufpos)[0] != 0:
                            pass
                        else:
                            L.lexMessage(TMsgKind.errGenerated, string("invalid token: no whitespace between number and identifier"))
                else:
                    _getOperator(L, tok)
            case _:
                if c in OpChars:
                    _getOperator(L, tok)
                elif c == nimlexbase.EndOfFile:
                    tok.tokType = TokType.tkEof
                    tok.indent = 0
                else:
                    tok.literal = string(str(c))
                    tok.tokType = TokType.tkInvalid
                    L.lexMessage(TMsgKind.errGenerated, string("invalid token: ") + c + string(" (\\") + str(ord(c)) + ch(')'))
                    L.bufpos += 1
    atTokenEnd()


def getIndentWidth(fileIdx: FileIndex, inputstream: PLLStream,
                   cache: IdentCache, config: ConfigRef) -> nint:
    result = 0
    with var:
        lex: Lexer = default(Lexer)
        tok: Token = default(Token)
    lex.openLexer(fileIdx, inputstream, cache, config)
    with var:
        prevToken = TokType.tkEof
    while tok.tokType != TokType.tkEof:
        rawGetTok(lex, tok)
        if tok.indent > 0 and prevToken in Tset[TokType]({TokType.tkColon, TokType.tkEquals, TokType.tkType, TokType.tkConst,
                                                           TokType.tkLet, TokType.tkVar, TokType.tkUsing}):
            result = tok.indent
            if result > 0: break
        prevToken = tok.tokType
    lex.closeLexer()
    return result


@dispatch
def getPrecedence(ident: PIdent) -> nint:
    """assumes ident is binary operator already"""
    with let:
        tokType = (TokType(ident.id + ord(TokType.tkSymbol))
                   if ident.id in inrange(ord(tokKeywordLow) - ord(TokType.tkSymbol), ord(tokKeywordHigh) - ord(TokType.tkSymbol))
                   else TokType.tkOpr)
        tok = Token(ident=ident, tokType=tokType)

    return getPrecedence(tok)


if comptime(__name__ == "__main__"):
    with var:
        _errors = seq[string]()

    def _collect(conf: ConfigRef, info: TLineInfo, msg: TMsgKind, arg: string) -> None:
        _errors.add(str(info.line) + string(":") + str(info.col) + string(" ") + str(msg) + string(" ") + arg)

    def _lexAll(src: string) -> seq[string]:
        """the tokens of src: kind, text, line:col, indent, spacing"""
        result = seq[string]()
        with var:
            lex: Lexer = default(Lexer)
            tok: Token = default(Token)
        lex.openLexer(AbsoluteFile(string("test.nim")), llStreamOpen(src), newIdentCache(), newConfigRef())
        lex.errorHandler = _collect
        while True:
            rawGetTok(lex, tok)
            result.add(str(tok.tokType) + string(" |") + prettyTok(tok) + string("| ") + str(tok.line) + string(":") +
                       str(tok.col) + string(" i") + str(tok.indent) + string(" ") + str(tok.spacing))
            if tok.tokType == TokType.tkEof: break
        lex.closeLexer()
        return result

    with let:
        _src = utf8("proc fooBar*(x: int; y = 3): string =\n"
                      "  ## doc comment\n"
                      "  ## second line\n"
                      "  let z = x +% 0x1F'u8 + 0b1010 + 0o17 + 123'i16 + 1_000 - 0xFF'i8\n"
                      "  var f = 3.5e2 + 1.5'f32 + 0x3F800000'f32 + 2.0'd + 12'myLit\n"
                      "  result = $(-5) & \"a\\tb\\x41\\u{1F600}\\\\\" & r\"raw\\n\" & foo\"gen\" & \"\"\"\n"
                      "triple \"q\" \"\"\"\n"
                      "  discard 'a' & '\\n' & '\\x42' & '\\''\n"
                      "  a ±= b ∘ c; d..<e; v*: int; x.y[.1.] {.p.} (.q.) `+`  # comment\n"
                      "  #[ multi\n"
                      "     line ]# z = _ == foo_Bar\n"
                      "  ##[ doc\n"
                      "    block ]##\n"
                      "  echo 9223372036854775807, 18446744073709551615'u64, 4294967296\n")
    for _line in _lexAll(_src):
        echo(_line)

    # errors are reported through the errorHandler
    for _line in _lexAll(string("x = 1__2 + 0b12 + 300'u8 + 1_ + 'ab' + \"open\n\tz 3a\n")):
        echo(_line)
    for _e in _errors:
        echo(_e)

    # precedence, keywords, identifiers, indentation
    with var:
        _cache2 = newIdentCache()
    doAssert(getPrecedence(_cache2.getIdent(string("+"))) == 8)
    doAssert(getPrecedence(_cache2.getIdent(string("*="))) == 1)
    doAssert(getPrecedence(_cache2.getIdent(string("->"))) == 0)
    doAssert(getPrecedence(_cache2.getIdent(string("div"))) == 9)
    doAssert(getPrecedence(_cache2.getIdent(string("and"))) == 4)
    doAssert(getPrecedence(_cache2.getIdent(utf8("±"))) == 8)
    doAssert(getPrecedence(_cache2.getIdent(string("foo"))) == 2)
    doAssert(isKeyword(TokType.tkProc) and not isKeyword(TokType.tkSymbol) and not isKeyword(TokType.tkIntLit))
    doAssert(isNimIdentifier(string("foo_bar")) and not isNimIdentifier(string("_x")) and not isNimIdentifier(string("a__")))
    doAssert(getIndentWidth(FileIndex(0), llStreamOpen(string("type\n    A = int\n")), newIdentCache(), newConfigRef()) == 4)
    echo(string("lexer: all tests passed!"))
