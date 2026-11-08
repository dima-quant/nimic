# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/nifler2/nimlexer.nim
# ///
#
#
#           Nifler2: Nim to NIF
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## Nim's lexer for `nifler2`, built on `std/rex`'s `lex` construct.
##
## The token type, the token kinds and their spellings are the ones
## `compiler/lexer.nim` uses, because the two are meant to be differentially
## tested against each other: same input, same token sequence, or a bug.
## `src/nifler2/deps/parsegen.nim` already assumes these names -- the
## grammar's `'if'` is `tkIf` and its `'{.'` is `tkCurlyDotLe`.
##
## What the generated automata do and what is hand-written:
##
## * **`lex`**: keywords and identifiers, every numeric literal form --
##   decimal, hex, octal, binary, and floats with an exponent -- and the type
##   suffix behind a number. Numbers are where a DFA earns its keep:
##   `getNumber` in Nim's lexer is a hundred lines of hand-rolled state, most
##   of it spelling out where `_` may appear.
## * **hand-written**: the indentation and spacing bookkeeping, comments
##   (including nested `#[ ]#`), string and character literals, and the
##   punctuation whose meaning depends on the character *after* it (`(.` is
##   one token, `(..` is two).
##
## Keywords are case-sensitive, like every other identifier in Nimony: `proc`
## is the keyword, `pRoC` and `p_roc` are identifiers. This is where the lexer
## deliberately parts ways with Nim's, whose keywords are style-insensitive.

# plugexpand: `import std / rex` dropped

from __future__ import annotations
from nimic.ntypes import *


class TokKind(NStrEnum):
    ## Nim's `TokType`, minus the tokens only `renderer.nim` uses
    tkInvalid = "tkInvalid"
    tkEof = "[EOF]"
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
    tkOpr = "tkOpr"
    tkComment = "tkComment"
    tkAccent = "`"


class TokSpacing(NIntEnum):

    ## whitespace *around* a token, which the parser needs to
    ## tell `f(x)` from `f (x)` and `-x` from `a - x`
    tsLeading = auto()
    tsTrailing = auto()
    tsEof = auto()


class Token(Object):
    kind: TokKind
    s: string  ## identifier, operator, or the *decoded* literal
    indent: int32  ## column when first on its line, else -1
    spacing: Tset[TokSpacing]
    line: int32
    col: int32
    base: int32  ## 2, 8, 10 or 16 for the integer literals
    suffixPos: int32  ## `tkCustomLit`: index of the `'` inside `s`
    iNumber: int64  ## value of an integer literal
    ## Floats keep their text in `s` and are converted by whoever needs the
    ## value; integers cannot, because `tkIntLit` is promoted to
    ## `tkInt64Lit` exactly when the value leaves `int32`'s range.

    def isRightAssoc(tok: Token) -> bool:
        """{.inline.}"""
        ## Only `^`-like operators associate to the right, exactly as in
        ## `parser.nim`'s `isRightAssociative`.
        return tok.kind == TokKind.tkOpr and tok.s.len > 0 and tok.s[0] == char('^')

    def isUnary(tok: Token) -> bool:
        """{.inline.}"""
        ## Space in front and none behind: `-x` is a prefix operator, `a - x` is not.
        return tok.kind in Tset[TokKind](TokKind.tkOpr, TokKind.tkDotDot) and tok.spacing == Tset[TokSpacing](TokSpacing.tsLeading)

    def isDotLike(tok: Token) -> bool:
        """{.inline.}"""
        return tok.kind == TokKind.tkOpr and tok.s.len > 1 and tok.s[0] == char('.') and tok.s[1] != char('.')

    def isSigilLike(tok: Token) -> bool:
        """{.inline.}"""
        return tok.kind == TokKind.tkOpr and tok.s.len > 0 and tok.s[0] == char('@')

    def _normalizeBasePrefix(tok: mut @ Token):
        ## `getNumber` writes the base prefix into the literal in lower case
        ## whatever the source said, so `0X10` and `0x10` are one token and not two
        ## spellings of it.
        if tok.base == 10: return
        with let:
            i = 2 if tok.s.len > 0 and tok.s[0] == char('-') else 1
        if i < tok.s.len and tok.s[i] >= char('A') and tok.s[i] <= char('Z'):
            tok.s[i] = chr(ord(tok.s[i]) - ord(char('A')) + ord(char('a')))


class Lexer(Object):
    buf: string
    pos: nint
    filename: string
    lineNumber: int32
    lineStart: nint  ## buffer offset of the current line's first char
    currLineIndent: int32
    indentAhead: int32  ## set by a doc comment for the token behind it
    errors: seq[string]

    def _errorAt(L: mut @ Lexer, line: nint, col: nint, msg: string):
        L.errors.add(L.filename + string("(") + str(line) + string(", ") + str(col + 1) + string(") Error: ") + msg)

    def _error(L: mut @ Lexer, pos: nint, msg: string):
        L._errorAt(L.lineNumber, pos - L.lineStart, msg)

    def _litNumText(L: Lexer, start: nint) -> string:
        ## The number as `lexMessageLitNum` quotes it: everything literal-ish from
        ## `start`, which is behind a leading `-`.
        with const:
            LiteralishChars = Tset[char](inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('0'), char('9')), char('_'), char('.'), char('\''))
        result = string("")
        with var:
            pos = copy(start)
        while L.ch(pos) in LiteralishChars:
            result.add(L.ch(pos))
            pos += 1
        if L.ch(pos) in Tset[char](char('+'), char('-')) and L.ch(pos - 1) in Tset[char](char('e'), char('E')):
            result.add(L.ch(pos))
            pos += 1
            while L.ch(pos) in LiteralishChars:
                result.add(L.ch(pos))
                pos += 1
        if L.ch(pos) in LiteralishChars:
            result.add(L.ch(pos))
            pos += 1
            while L.ch(pos) in Tset[char](inrange(char('0'), char('9'))):
                result.add(L.ch(pos))
                pos += 1
        return result

    def _handleCRLF(L: mut @ Lexer, pos: nint) -> nint:
        result = copy(pos)
        if L.ch(result) == char('\r'):
            result += 1
            if L.ch(result) == char('\n'): result += 1
        elif L.ch(result) == char('\n'):
            result += 1
        L.lineNumber += 1
        L.lineStart = result
        return result

    def _numberSuffix(L: mut @ Lexer, tok: mut @ Token, start: nint, isFloat: bool):
        ## Second stage, as in `getNumber`: the first automaton matched the number,
        ## this one reads the `'i8` / `u32` / `'myLit` behind it. They are two
        ## automata and not one because the number must be the *longest* number:
        ## `0x1f32` is a hex literal, not `0x1` with the suffix `f32`, and a single
        ## automaton's maximal munch cannot tell those apart.
        tok.kind = TokKind.tkFloatLit if isFloat else TokKind.tkIntLit
        with let:
            numEnd = copy(L.pos)
        tok.s = L.buf.substr(start, numEnd - 1)
        with var:
            pos = copy(numEnd)
            kind = tok.kind
        # The built-in suffixes come first so that they win against the custom
        # literal and the bad suffix on a tie; a longer spelling (`'i8x`) does not
        # tie and is not built in.
        # plugexpand: `lex L.buf, pos:` (line 316), expanded
        with var:
            tmp1 = 1
            tmp3 = 0
            tmp4 = copy(pos)
        while True:
            with var:
                tmp2 = char('\x00')
            if pos < len(L.buf):
                tmp2 = L.buf[pos]
            match tmp1:
                case 1:
                    if tmp2 in Tset[char](char('F'), char('f')):
                        pos += 1
                        tmp1 = 2
                    elif tmp2 in Tset[char](char('D'), char('d')):
                        pos += 1
                        tmp1 = 3
                    elif tmp2 in Tset[char](char('U'), char('u')):
                        pos += 1
                        tmp1 = 9
                    elif tmp2 in Tset[char](char('I'), char('i')):
                        pos += 1
                        tmp1 = 31
                    elif tmp2 == char('\''):
                        pos += 1
                        tmp1 = 32
                    else:
                        break
                case 2:
                    tmp3 = 1
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('2'), char('4'), char('5'), inrange(char('7'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('1'):
                        pos += 1
                        tmp1 = 15
                    elif tmp2 == char('3'):
                        pos += 1
                        tmp1 = 28
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 52
                    else:
                        break
                case 3:
                    tmp3 = 2
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 4:
                    tmp3 = 3
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 5:
                    tmp3 = 4
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 6:
                    tmp3 = 5
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 7:
                    tmp3 = 6
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 8:
                    tmp3 = 7
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 9:
                    tmp3 = 8
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('2'), char('4'), char('5'), char('7'), char('9'), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('8'):
                        pos += 1
                        tmp1 = 10
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 29
                    elif tmp2 == char('1'):
                        pos += 1
                        tmp1 = 30
                    elif tmp2 == char('3'):
                        pos += 1
                        tmp1 = 35
                    else:
                        break
                case 10:
                    tmp3 = 9
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 11:
                    tmp3 = 10
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 12:
                    tmp3 = 11
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 13:
                    tmp3 = 12
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 14:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 27
                    else:
                        break
                case 15:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 36
                    else:
                        break
                case 16:
                    tmp3 = 12
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 17:
                    tmp3 = 11
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 18:
                    tmp3 = 10
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 19:
                    tmp3 = 9
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 20:
                    tmp3 = 8
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('2'), char('4'), char('5'), char('7'), char('9'), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('8'):
                        pos += 1
                        tmp1 = 19
                    elif tmp2 == char('1'):
                        pos += 1
                        tmp1 = 46
                    elif tmp2 == char('3'):
                        pos += 1
                        tmp1 = 47
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 48
                    else:
                        break
                case 21:
                    tmp3 = 7
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 22:
                    tmp3 = 6
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 23:
                    tmp3 = 5
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 24:
                    tmp3 = 4
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 25:
                    tmp3 = 3
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 26:
                    tmp3 = 2
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 27:
                    tmp3 = 1
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 28:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 34
                    else:
                        break
                case 29:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('3')), inrange(char('5'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('4'):
                        pos += 1
                        tmp1 = 13
                    else:
                        break
                case 30:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('5')), inrange(char('7'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 11
                    else:
                        break
                case 31:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('2'), char('4'), char('5'), char('7'), char('9'), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('8'):
                        pos += 1
                        tmp1 = 5
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 49
                    elif tmp2 == char('3'):
                        pos += 1
                        tmp1 = 50
                    elif tmp2 == char('1'):
                        pos += 1
                        tmp1 = 51
                    else:
                        break
                case 32:
                    if tmp2 in Tset[char](char('U'), char('u')):
                        pos += 1
                        tmp1 = 20
                    elif tmp2 in Tset[char](char('D'), char('d')):
                        pos += 1
                        tmp1 = 26
                    elif tmp2 in Tset[char](char('F'), char('f')):
                        pos += 1
                        tmp1 = 39
                    elif tmp2 in Tset[char](char('I'), char('i')):
                        pos += 1
                        tmp1 = 42
                    elif tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('C')), char('E'), char('G'), char('H'), inrange(char('J'), char('T')), inrange(char('V'), char('Z')), inrange(char('a'), char('c')), char('e'), char('g'), char('h'), inrange(char('j'), char('t')), inrange(char('v'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 33:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 34:
                    tmp3 = 1
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    else:
                        break
                case 35:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 12
                    else:
                        break
                case 36:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('7')), char('9'), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('8'):
                        pos += 1
                        tmp1 = 4
                    else:
                        break
                case 37:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 44
                    else:
                        break
                case 38:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 22
                    else:
                        break
                case 39:
                    tmp3 = 1
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('2'), char('4'), char('5'), inrange(char('7'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('3'):
                        pos += 1
                        tmp1 = 14
                    elif tmp2 == char('1'):
                        pos += 1
                        tmp1 = 37
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 40
                    else:
                        break
                case 40:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('3')), inrange(char('5'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('4'):
                        pos += 1
                        tmp1 = 26
                    else:
                        break
                case 41:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('5')), inrange(char('7'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 23
                    else:
                        break
                case 42:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('2'), char('4'), char('5'), char('7'), char('9'), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('8'):
                        pos += 1
                        tmp1 = 24
                    elif tmp2 == char('3'):
                        pos += 1
                        tmp1 = 38
                    elif tmp2 == char('1'):
                        pos += 1
                        tmp1 = 41
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 45
                    else:
                        break
                case 43:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    else:
                        break
                case 44:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('7')), char('9'), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('8'):
                        pos += 1
                        tmp1 = 25
                    else:
                        break
                case 45:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('3')), inrange(char('5'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('4'):
                        pos += 1
                        tmp1 = 21
                    else:
                        break
                case 46:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('5')), inrange(char('7'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 18
                    else:
                        break
                case 47:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 17
                    else:
                        break
                case 48:
                    tmp3 = 13
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('3')), inrange(char('5'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 43
                    elif tmp2 == char('4'):
                        pos += 1
                        tmp1 = 16
                    else:
                        break
                case 49:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('3')), inrange(char('5'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('4'):
                        pos += 1
                        tmp1 = 8
                    else:
                        break
                case 50:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](char('0'), char('1'), inrange(char('3'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('2'):
                        pos += 1
                        tmp1 = 7
                    else:
                        break
                case 51:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('5')), inrange(char('7'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('6'):
                        pos += 1
                        tmp1 = 6
                    else:
                        break
                case 52:
                    tmp3 = 14
                    tmp4 = copy(pos)
                    if tmp2 in Tset[char](inrange(char('0'), char('3')), inrange(char('5'), char('9')), inrange(char('A'), char('Z')), char('_'), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                        pos += 1
                        tmp1 = 33
                    elif tmp2 == char('4'):
                        pos += 1
                        tmp1 = 3
                    else:
                        break
                case _:
                    break
        pos = tmp4
        match tmp3:
            case 1:
                kind = TokKind.tkFloat32Lit
            case 2:
                kind = TokKind.tkFloat64Lit
            case 3:
                kind = TokKind.tkFloat128Lit
            case 4:
                kind = TokKind.tkInt8Lit
            case 5:
                kind = TokKind.tkInt16Lit
            case 6:
                kind = TokKind.tkInt32Lit
            case 7:
                kind = TokKind.tkInt64Lit
            case 8:
                kind = TokKind.tkUIntLit
            case 9:
                kind = TokKind.tkUInt8Lit
            case 10:
                kind = TokKind.tkUInt16Lit
            case 11:
                kind = TokKind.tkUInt32Lit
            case 12:
                kind = TokKind.tkUInt64Lit
            case 13:
                kind = TokKind.tkCustomLit
            case 14:
                L._error(numEnd, string("invalid number suffix: \'") + L.buf.substr(numEnd, pos - 1) + string("\'"))
            case _:
                if L.ch(pos) == char('\''):
                    L._error(pos + 1, string("invalid number suffix"))
        L.pos = pos
        if kind == TokKind.tkCustomLit:
            tok.suffixPos = int32(numEnd - start)
            tok.s = L.buf.substr(start, pos - 1)
        tok.kind = kind

    def _skipMultiLineComment(L: mut @ Lexer, tok: mut @ Token, start: nint, isDoc: bool):
        with var:
            pos = copy(start)
            toStrip = nint(0)
        if isDoc:
            toStrip = pos - L.lineStart
            while L.ch(pos) == char(' '):
                pos += 1
                toStrip += 1
            while L.ch(pos) == char('\r') or L.ch(pos) == char('\n'):
                pos = L._handleCRLF(pos)
                toStrip = 0
                while L.ch(pos) == char(' '):
                    pos += 1
                    toStrip += 1
        with var:
            nesting = nint(0)
        while True:
            with let:
                c = L.ch(pos)
            if c == char('#'):
                if isDoc:
                    if L.ch(pos + 1) == char('#') and L.ch(pos + 2) == char('['): nesting += 1
                    tok.s.add(char('#'))
                elif L.ch(pos + 1) == char('['):
                    nesting += 1
                pos += 1
            elif c == char(']'):
                if isDoc:
                    if L.ch(pos + 1) == char('#') and L.ch(pos + 2) == char('#'):
                        if nesting == 0:
                            pos += 3
                            break
                        nesting -= 1
                    tok.s.add(char(']'))
                elif L.ch(pos + 1) == char('#'):
                    if nesting == 0:
                        pos += 2
                        break
                    nesting -= 1
                pos += 1
            elif c == char('\r') or c == char('\n'):
                pos = L._handleCRLF(pos)
                if isDoc:
                    tok.s.add(char('\n'))
                    with var:
                        n = copy(toStrip)
                    while L.ch(pos) == char(' ') and n > 0:
                        pos += 1
                        n -= 1
            elif c == char('\x00'):
                L._error(pos, string("end of multiline comment expected"))
                break
            else:
                if isDoc: tok.s.add(c)
                pos += 1
        L.pos = pos

    def _scanComment(L: mut @ Lexer, tok: mut @ Token):
        ## Only doc comments get here: `skip` eats the ordinary ones. Consecutive
        ## `##` lines become **one** token, and the indentation of the line after
        ## the block is remembered in `indentAhead` for the token that follows.
        with var:
            pos = copy(L.pos)
        tok.kind = TokKind.tkComment
        if L.ch(pos + 2) == char('['):
            L._skipMultiLineComment(tok, pos + 3, True)
            return
        pos += 2
        with var:
            toStrip = nint(0)
            stripInit = False
        while True:
            if not stripInit:
                while L.ch(pos) == char(' '):
                    pos += 1
                    toStrip += 1
                if L.ch(pos) == char('\r') or L.ch(pos) == char('\n'): toStrip = 0
                else: stripInit = True
            while L.ch(pos) != char('\r') and L.ch(pos) != char('\n') and L.ch(pos) != char('\x00'):
                tok.s.add(L.buf[pos])
                pos += 1
            if L.ch(pos) == char('\x00'): break
            pos = L._handleCRLF(pos)
            with var:
                indent = nint(0)
            while L.ch(pos) == char(' '):
                pos += 1
                indent += 1
            if L.ch(pos) == char('#') and L.ch(pos + 1) == char('#'):
                tok.s.add(char('\n'))
                pos += 2
                if stripInit:
                    with var:
                        n = copy(toStrip)
                    while L.ch(pos) == char(' ') and n > 0:
                        pos += 1
                        n -= 1
            else:
                if L.ch(pos) > char(' '): L.indentAhead = int32(indent)
                break
        L.pos = pos

    def _handleHexChar(L: mut @ Lexer, xi: mut @ nint, position: Trange[0, 4]):
        with let:
            c = L.ch(L.pos)
        if c >= char('0') and c <= char('9'): xi <<= (xi << 4) | (ord(c) - ord(char('0')))
        elif c >= char('a') and c <= char('f'): xi <<= (xi << 4) | (ord(c) - ord(char('a')) + 10)
        elif c >= char('A') and c <= char('F'): xi <<= (xi << 4) | (ord(c) - ord(char('A')) + 10)
        else:
            if position <= 1: L._error(L.pos, string("expected a hex digit"))
            return
        L.pos += 1

    def _endOperator(L: mut @ Lexer, tok: mut @ Token, start: nint, stop: nint):
        ## The five operator spellings that are punctuation rather than operators.
        tok.s = L.buf.substr(start, stop)
        if tok.s == ":": tok.kind = TokKind.tkColon
        elif tok.s == "::": tok.kind = TokKind.tkColonColon
        elif tok.s == "=": tok.kind = TokKind.tkEquals
        elif tok.s == ".": tok.kind = TokKind.tkDot
        elif tok.s == "..": tok.kind = TokKind.tkDotDot
        else: tok.kind = TokKind.tkOpr
        L.pos = stop + 1

    def _skip(L: mut @ Lexer, tok: mut @ Token):
        ## Everything that is not a token. `tok.indent` comes out of here: it is the
        ## column of the first token on a line and -1 for every other token, which
        ## is the single input the generated parser's `IndClass` is computed from.
        with var:
            pos = copy(L.pos)
        tok.spacing.excl(TokSpacing.tsLeading)
        while True:
            with let:
                c = L.ch(pos)
            if c == char(' '):
                pos += 1
                tok.spacing.incl(TokSpacing.tsLeading)
            elif c == char('\t'):
                L._error(pos, string("tabs are not allowed, use spaces instead"))
                pos += 1
            elif c == char('\r') or c == char('\n'):
                pos = L._handleCRLF(pos)
                with var:
                    indent = nint(0)
                while True:
                    if L.ch(pos) == char(' '):
                        pos += 1
                        indent += 1
                    elif L.ch(pos) == char('#') and L.ch(pos + 1) == char('['):
                        L.pos = pos
                        L._skipMultiLineComment(tok, pos + 2, False)
                        pos = L.pos.copy()
                    else:
                        break
                tok.spacing.excl(TokSpacing.tsLeading)
                if L.ch(pos) > char(' ') and (L.ch(pos) != char('#') or L.ch(pos + 1) == char('#')):
                    tok.indent = int32(indent)
                    L.currLineIndent = int32(indent)
                    break
            elif c == char('#'):
                if L.ch(pos + 1) == char('#'): break  # a doc comment is a token
                if L.ch(pos + 1) == char('['):
                    L.pos = pos
                    L._skipMultiLineComment(tok, pos + 2, False)
                    pos = L.pos.copy()
                else:
                    while L.ch(pos) != char('\r') and L.ch(pos) != char('\n') and L.ch(pos) != char('\x00'):
                        pos += 1
            else:
                break  # end of file leaves the loop too
        L.pos = pos


with const:
    KeywordLow = TokKind.tkAddr
    KeywordHigh = TokKind.tkYield

    OpChars = Tset[char](char('+'), char('-'), char('*'), char('/'), char('\\'), char('<'), char('>'), char('!'), char('?'), char('^'), char('.'), char('|'), char('='), char('%'), char('&'), char('$'), char('@'), char('~'), char(':'))
    SymChars = Tset[char](inrange(char('a'), char('z')), inrange(char('A'), char('Z')), inrange(char('0'), char('9')), inrange(char('\x80'), char('\xff')))
    SymStartChars = Tset[char](inrange(char('a'), char('z')), inrange(char('A'), char('Z')), inrange(char('\x80'), char('\xff')))
    UnicodeOperatorStartChars = Tset[char](char('\xc2'), char('\xc3'), char('\xe2'))
    ## `∙ ∘ × ★ ☆ ⊗ ⊘ ⊙ ⊛ ⊠ ⊡ ∩ ∧ ⊓ ⟑ ⟇ ⩓ ⩔ ■ □ ± ⊕ ⊖ ⊞ ⊟ ∪ ∨ ⊔` all start
    ## with one of these three bytes.
    _UnaryMinusWhitelist = Tset[char](char(' '), char('\t'), char('\n'), char('\r'), char(','), char(';'), char('('), char('['), char('{'))

    _MulPred = 9
    _PlusPred = 8

# ---------------------------------------------------------------------------
# Buffer access
#
# Nim's lexer reads from a sentinel-terminated buffer, so it may peek one or
# two characters past the token without a bounds check. `ch` gives us the same
# freedom over a plain string: everything past the end reads as '\0', which is
# also what the real lexer's end-of-file sentinel is.
# ---------------------------------------------------------------------------


def _str(c: char) -> string:
    """{.inline.}"""
    result = string("")
    result.add(c)
    return result


def _charAt(buf: string, i: nint) -> char:
    """{.inline.}"""
    return buf[i] if i >= 0 and i < buf.len else char('\x00')


@ufcs(Lexer)
@dispatch
def ch(L: Lexer, i: nint) -> char:
    """{.inline.}"""
    return _charAt(L.buf, i)

# ---------------------------------------------------------------------------
# Identifiers and keywords
# ---------------------------------------------------------------------------


def nimIdentNormalize(s: string) -> string:
    ## Nim's identifier equality made explicit: the first character counts as
    ## written, the rest is lowercased and underscores drop out. The lexer does
    ## not use it; the differential tools compare identifiers with it, because
    ## Nim's identifier cache cannot report the spelling it saw.
    result = string("")
    if s.len > 0: result.add(s[0])
    with var:
        i = nint(1)
    while i < s.len:
        with let:
            c = s[i]
        if c == char('_'): pass
        elif c >= char('A') and c <= char('Z'): result.add(chr(ord(c) - ord(char('A')) + ord(char('a'))))
        else: result.add(c)
        i += 1
    return result

# ---------------------------------------------------------------------------
# Unicode operators
# ---------------------------------------------------------------------------


class _UnicodeOprPred(NIntEnum):
    uopNone = auto()
    uopMul = auto()
    uopAdd = auto()


def unicodeOprLen(buf: string, pos: nint) -> tuple[nint, _UnicodeOprPred]:
    ## Length and precedence class of the unicode operator at `pos`, or
    ## `(0, uopNone)`. A byte in `UnicodeOperatorStartChars` that does not begin
    ## one of these is an ordinary identifier character, which is the whole
    ## reason this has to be consulted while scanning a symbol.
    result = (0, _UnicodeOprPred.uopNone)
    match _charAt(buf, pos):
        case _ if _charAt(buf, pos) == char('\xe2'):
            with let:
                b1 = _charAt(buf, pos + 1)
                b2 = _charAt(buf, pos + 2)
            if b1 == char('\x88'):
                if b2 == char('\x98') or b2 == char('\x99') or b2 == char('\xa7') or b2 == char('\xa9'):
                    result = (3, _UnicodeOprPred.uopMul)  # ∘ ∙ ∧ ∩
                elif b2 == char('\xa8') or b2 == char('\xaa'):
                    result = (3, _UnicodeOprPred.uopAdd)  # ∨ ∪
            elif b1 == char('\x8a'):
                if b2 == char('\x93') or b2 == char('\x97') or b2 == char('\x98') or b2 == char('\x99') or b2 == char('\x9b') or b2 == char('\xa0') or b2 == char('\xa1'):
                    result = (3, _UnicodeOprPred.uopMul)  # ⊓ ⊗ ⊘ ⊙ ⊛ ⊠ ⊡
                elif b2 == char('\x94') or b2 == char('\x95') or b2 == char('\x96') or b2 == char('\x9e') or b2 == char('\x9f'):
                    result = (3, _UnicodeOprPred.uopAdd)  # ⊔ ⊕ ⊖ ⊞ ⊟
            elif b1 == char('\x96'):
                if b2 == char('\xa0') or b2 == char('\xa1'): result = (3, _UnicodeOprPred.uopMul)  # ■ □
            elif b1 == char('\x98'):
                if b2 == char('\x85') or b2 == char('\x86'): result = (3, _UnicodeOprPred.uopMul)  # ★ ☆
            elif b1 == char('\x9f'):
                if b2 == char('\x87') or b2 == char('\x91'): result = (3, _UnicodeOprPred.uopMul)  # ⟇ ⟑
            elif b1 == char('\xa9'):
                if b2 == char('\x93') or b2 == char('\x94'): result = (3, _UnicodeOprPred.uopMul)  # ⩓ ⩔
        case _ if _charAt(buf, pos) == char('\xc2'):
            if _charAt(buf, pos + 1) == char('\xb1'): result = (2, _UnicodeOprPred.uopAdd)  # ±
        case _ if _charAt(buf, pos) == char('\xc3'):
            if _charAt(buf, pos + 1) == char('\x97'): result = (2, _UnicodeOprPred.uopMul)  # ×
        case _: pass
    return result

# ---------------------------------------------------------------------------
# Operator classification -- lexer-level in Nim, and the parser runtime needs
# all of it.
# ---------------------------------------------------------------------------


def getPrecedence(tok: Token) -> nint:
    ## Nim computes an operator's precedence from its spelling, which is why the
    ## grammar's `binary(...)` takes this as a parameter rather than baking a
    ## precedence table into the generated parser.
    match tok.kind:
        case TokKind.tkOpr:
            with let:
                s = tok.s
            if s.len == 0: return -10
            with let:
                last = s[s.len - 1]
            if s.len > 1 and last == char('>') and (s[s.len - 2] == char('-') or s[s.len - 2] == char('~') or s[s.len - 2] == char('=')):
                return 0  # arrow-like
            with let:
                asgn = last == char('=')
            match s[0]:
                case _ if s[0] == char('$') or s[0] == char('^'): result = (1 if asgn else 10)
                case _ if s[0] == char('*') or s[0] == char('%') or s[0] == char('/') or s[0] == char('\\'): result = (1 if asgn else _MulPred)
                case _ if s[0] == char('~'): result = 8
                case _ if s[0] == char('+') or s[0] == char('-') or s[0] == char('|'): result = (1 if asgn else _PlusPred)
                case _ if s[0] == char('&'): result = (1 if asgn else 7)
                case _ if s[0] == char('=') or s[0] == char('<') or s[0] == char('>') or s[0] == char('!'): result = 5
                case _ if s[0] == char('.'): result = (1 if asgn else 6)
                case _ if s[0] == char('?'): result = 2
                case _ if s[0] == char('\xc2') or s[0] == char('\xc3') or s[0] == char('\xe2'):
                    if asgn:
                        result = 1
                    else:
                        with let:
                            (n, pred) = unicodeOprLen(s, 0)
                        if n != 0: result = (_MulPred if pred == _UnicodeOprPred.uopMul else _PlusPred)
                        else: result = 2
                case _: result = (1 if asgn else 2)
        case TokKind.tkDiv | TokKind.tkMod | TokKind.tkShl | TokKind.tkShr: result = 9
        case TokKind.tkDotDot: result = 6
        case TokKind.tkIn | TokKind.tkNotin | TokKind.tkIs | TokKind.tkIsnot | TokKind.tkOf | TokKind.tkAs | TokKind.tkFrom: result = 5
        case TokKind.tkAnd: result = 4
        case TokKind.tkOr | TokKind.tkXor | TokKind.tkPtr | TokKind.tkRef: result = 3
        case _: result = -10
    return result

# ---------------------------------------------------------------------------
# The generated automata
# ---------------------------------------------------------------------------


def _hexVal(c: char) -> nint:
    """{.inline.}"""
    if c >= char('0') and c <= char('9'): return ord(c) - ord(char('0'))
    elif c >= char('a') and c <= char('f'): return ord(c) - ord(char('a')) + 10
    elif c >= char('A') and c <= char('F'): return ord(c) - ord(char('A')) + 10
    else: return 0


def _signExtend(x: uint64, bits: nint) -> int64:
    ## `x`'s low `bits` bits, read as a two's complement number. `0x80'i8` is
    ## -128 and not an error, which is the rule for every non-decimal literal.
    with let:
        m = u64(1) << (bits - 1)
        masked = x & ((m << 1) - u64(1))
    result = cast[int64](masked ^ m) - cast[int64](m)
    return result


def _numberValue(L: mut @ Lexer, tok: mut @ Token, start: nint):
    ## The value matters here and not only in the parser: `0xffffffff` is a
    ## `tkInt64Lit` and `0xffff` is a `tkIntLit`, so the token *kind* depends on
    ## it. Floats are left as text.
    if tok.kind == TokKind.tkCustomLit or (tok.kind >= TokKind.tkFloatLit and tok.kind <= TokKind.tkFloat128Lit):
        return
    with var:
        i = nint(0)
        negative = False
    if i < tok.s.len and tok.s[i] == char('-'):
        negative = True
        i += 1
    with var:
        xi = u64(0)
    if tok.base != 10:
        with let:
            shiftBy = 4 if tok.base == 16 else 3 if tok.base == 8 else 1
        i += 2  # past `0x` / `0o` / `0c` / `0b`
        while i < tok.s.len:
            if tok.s[i] != char('_'): xi = (xi << shiftBy) | uint64(_hexVal(tok.s[i]))
            i += 1
        match tok.kind:
            case TokKind.tkInt8Lit: tok.iNumber = _signExtend(xi, 8)
            case TokKind.tkInt16Lit: tok.iNumber = _signExtend(xi, 16)
            case TokKind.tkInt32Lit: tok.iNumber = _signExtend(xi, 32)
            case TokKind.tkUInt8Lit: tok.iNumber = cast[int64](xi & u64(0xff))
            case TokKind.tkUInt16Lit: tok.iNumber = cast[int64](xi & u64(0xffff))
            case TokKind.tkUInt32Lit: tok.iNumber = cast[int64](xi & u64(0xffffffff))
            case _: tok.iNumber = cast[int64](xi)
    else:
        with var:
            overflow = False
        while i < tok.s.len:
            with let:
                c = tok.s[i]
            if c != char('_'):
                with let:
                    d = uint64(ord(c) - ord(char('0')))
                if xi > (u64(0xffffffffffffffff) - d) // u64(10): overflow = True
                xi = xi * u64(10) + d
            i += 1
        # A decimal literal is parsed, not reinterpreted, so it really can be out
        # of range -- and when it is, Nim abandons the whole third stage, which
        # means the token keeps the kind it already had. `9223372036854775808`
        # stays a `tkIntLit`; it does not become a `tkInt64Lit`.
        with let:
            limit = u64(0xffffffffffffffff) if tok.kind == TokKind.tkUIntLit or tok.kind == TokKind.tkUInt64Lit else u64(0x8000000000000000) if negative else u64(0x7fffffffffffffff)
        if overflow or xi > limit:
        # Nim's third stage has rewound to the start of the digits
            L._error(start, string("number out of range: '") + L._litNumText(start) + string("'"))
            return
        tok.iNumber = cast[int64](xi)
        if negative: tok.iNumber = -tok.iNumber
        with let:
            match tok.kind:
                case TokKind.tkInt8Lit: tooWide = tok.iNumber > i64(127) or tok.iNumber < i64(-128)
                case TokKind.tkInt16Lit: tooWide = tok.iNumber > i64(32767) or tok.iNumber < i64(-32768)
                case TokKind.tkInt32Lit:
                    tooWide = tok.iNumber > i64(2147483647) or tok.iNumber < i64(-2147483648)
                case TokKind.tkUInt8Lit: tooWide = tok.iNumber > i64(255) or tok.iNumber < i64(0)
                case TokKind.tkUInt16Lit: tooWide = tok.iNumber > i64(65535) or tok.iNumber < i64(0)
                case TokKind.tkUInt32Lit: tooWide = tok.iNumber > i64(4294967295) or tok.iNumber < i64(0)
                case _: tooWide = False
        if tooWide: L._error(start, string("number out of range: '") + L._litNumText(start) + string("'"))
    if tok.base != 10 and negative: tok.iNumber = -tok.iNumber
    # "Promote int literal to int64? Not always necessary, but more consistent"
    if tok.kind == TokKind.tkIntLit and (tok.iNumber > i64(2147483647) or tok.iNumber < i64(-2147483648)):
        tok.kind = TokKind.tkInt64Lit


def _scanNumber(L: mut @ Lexer, tok: mut @ Token):
    ## One automaton for every numeric literal Nim has. The patterns spell out
    ## `_`'s rule -- between digits, never doubled, never trailing -- rather
    ## than checking for it afterwards, which is the whole hundred lines of
    ## `matchUnderscoreChars` and its callers gone.
    with let:
        start = copy(L.pos)
    with var:
        pos = copy(L.pos)
        base = i32(10)
        isFloat = False
    with block:
        with let:
            d = start + 1 if L.ch(start) == char('-') else start
        if L.ch(d) == char('0') and L.ch(d + 1) == char('O'):
            L._error(d + 1, L._litNumText(d) + string(" is an invalid int literal; For octal literals use the '0o' prefix."))
    # plugexpand: `lex L.buf, pos:` (line 446), expanded
    with var:
        tmp6 = 1
        tmp8 = 0
        tmp9 = copy(pos)
    while True:
        with var:
            tmp7 = char('\x00')
        if pos < len(L.buf):
            tmp7 = L.buf[pos]
        match tmp6:
            case 1:
                if tmp7 in Tset[char](inrange(char('1'), char('9'))):
                    pos += 1
                    tmp6 = 13
                elif tmp7 == char('0'):
                    pos += 1
                    tmp6 = 7
                elif tmp7 == char('-'):
                    pos += 1
                    tmp6 = 19
                else:
                    break
            case 2:
                tmp8 = 1
                tmp9 = copy(pos)
                if tmp7 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('F')), inrange(char('a'), char('f'))):
                    pos += 1
                    tmp6 = 2
                elif tmp7 == char('_'):
                    pos += 1
                    tmp6 = 18
                else:
                    break
            case 3:
                tmp8 = 2
                tmp9 = copy(pos)
                if tmp7 in Tset[char](inrange(char('0'), char('7'))):
                    pos += 1
                    tmp6 = 3
                elif tmp7 == char('_'):
                    pos += 1
                    tmp6 = 17
                else:
                    break
            case 4:
                tmp8 = 3
                tmp9 = copy(pos)
                if tmp7 in Tset[char](char('0'), char('1')):
                    pos += 1
                    tmp6 = 4
                elif tmp7 == char('_'):
                    pos += 1
                    tmp6 = 16
                else:
                    break
            case 5:
                tmp8 = 4
                tmp9 = copy(pos)
                if tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 5
                elif tmp7 == char('_'):
                    pos += 1
                    tmp6 = 15
                else:
                    break
            case 6:
                tmp8 = 5
                tmp9 = copy(pos)
                if tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 6
                elif tmp7 in Tset[char](char('E'), char('e')):
                    pos += 1
                    tmp6 = 8
                elif tmp7 == char('_'):
                    pos += 1
                    tmp6 = 9
                else:
                    break
            case 7:
                tmp8 = 6
                tmp9 = copy(pos)
                if tmp7 in Tset[char](char('E'), char('e')):
                    pos += 1
                    tmp6 = 8
                elif tmp7 in Tset[char](char('B'), char('b')):
                    pos += 1
                    tmp6 = 10
                elif tmp7 in Tset[char](char('C'), char('c'), char('o')):
                    pos += 1
                    tmp6 = 11
                elif tmp7 in Tset[char](char('X'), char('x')):
                    pos += 1
                    tmp6 = 12
                elif tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 13
                elif tmp7 == char('.'):
                    pos += 1
                    tmp6 = 9
                elif tmp7 == char('_'):
                    pos += 1
                    tmp6 = 14
                else:
                    break
            case 8:
                if tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 5
                elif tmp7 in Tset[char](char('+'), char('-')):
                    pos += 1
                    tmp6 = 15
                else:
                    break
            case 9:
                if tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 6
                else:
                    break
            case 10:
                tmp8 = 3
                tmp9 = copy(pos)
                if tmp7 in Tset[char](char('0'), char('1')):
                    pos += 1
                    tmp6 = 4
                else:
                    break
            case 11:
                tmp8 = 2
                tmp9 = copy(pos)
                if tmp7 in Tset[char](inrange(char('0'), char('7'))):
                    pos += 1
                    tmp6 = 3
                else:
                    break
            case 12:
                tmp8 = 1
                tmp9 = copy(pos)
                if tmp7 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('F')), inrange(char('a'), char('f'))):
                    pos += 1
                    tmp6 = 2
                else:
                    break
            case 13:
                tmp8 = 6
                tmp9 = copy(pos)
                if tmp7 in Tset[char](char('E'), char('e')):
                    pos += 1
                    tmp6 = 8
                elif tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 13
                elif tmp7 == char('.'):
                    pos += 1
                    tmp6 = 9
                elif tmp7 == char('_'):
                    pos += 1
                    tmp6 = 14
                else:
                    break
            case 14:
                if tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 13
                else:
                    break
            case 15:
                if tmp7 in Tset[char](inrange(char('0'), char('9'))):
                    pos += 1
                    tmp6 = 5
                else:
                    break
            case 16:
                if tmp7 in Tset[char](char('0'), char('1')):
                    pos += 1
                    tmp6 = 4
                else:
                    break
            case 17:
                if tmp7 in Tset[char](inrange(char('0'), char('7'))):
                    pos += 1
                    tmp6 = 3
                else:
                    break
            case 18:
                if tmp7 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('F')), inrange(char('a'), char('f'))):
                    pos += 1
                    tmp6 = 2
                else:
                    break
            case 19:
                if tmp7 in Tset[char](inrange(char('1'), char('9'))):
                    pos += 1
                    tmp6 = 13
                elif tmp7 == char('0'):
                    pos += 1
                    tmp6 = 7
                else:
                    break
            case _:
                break
    pos = tmp9
    match tmp8:
        case 1:
            base = i32(16)
        case 2:
            base = i32(8)
        case 3:
            base = i32(2)
        case 4 | 5:
            isFloat = True
        case 6:
            pass
        case _:
            tok.kind = TokKind.tkInvalid
            tok.s = _str(L.ch(pos))
            L._error(pos, string("invalid number"))
            pos += 1
            L.pos = pos
            return
    L.pos = pos
    tok.base = base
    with let:
        digits = start + 1 if L.buf[start] == char('-') else start
    if base != 10 and pos - digits <= 2:
        L._error(pos, string("invalid number: '") + L._litNumText(digits) + string("'"))
    L._numberSuffix(tok, start, isFloat)
    tok._normalizeBasePrefix()
    _numberValue(L, tok, digits)
    if L.ch(L.pos) in SymChars + Tset[char](char('_')) and unicodeOprLen(L.buf, L.pos)[0] == 0:
        L._error(L.pos, string("invalid token: no whitespace between number and identifier"))


def _symbolKind(s: string, pos: mut @ nint) -> TokKind:
    ## The keyword or identifier starting at `pos`, which is moved behind it;
    ## `tkInvalid`, with `pos` unmoved, when there is none. A keyword ties with
    ## the identifier pattern and wins because it comes first; `iffy` is longer
    ## than `if` and so is an identifier.
    result = TokKind.tkInvalid
    # plugexpand: `lex s, pos:` (line 481), expanded
    with var:
        tmp11 = 69
        tmp13 = 0
        tmp14 = copy(pos)
    while True:
        with var:
            tmp12 = char('\x00')
        if pos < len(s):
            tmp12 = s[pos]
        match tmp11:
            case 1:
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                else:
                    break
            case 2:
                tmp13 = 1
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 3:
                tmp13 = 2
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 4:
                tmp13 = 3
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('l')), inrange(char('n'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('m'):
                    pos += 1
                    tmp11 = 5
                else:
                    break
            case 5:
                tmp13 = 4
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 6:
                tmp13 = 5
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 7:
                tmp13 = 6
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 8:
                tmp13 = 7
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 9:
                tmp13 = 8
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 10:
                tmp13 = 9
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 11:
                tmp13 = 10
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 12:
                tmp13 = 11
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 13:
                tmp13 = 12
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 14:
                tmp13 = 13
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 15:
                tmp13 = 14
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 16:
                tmp13 = 15
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 17:
                tmp13 = 16
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 18:
                tmp13 = 17
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 19:
                tmp13 = 18
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 20:
                tmp13 = 19
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 21:
                tmp13 = 20
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 22:
                tmp13 = 21
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 23:
                tmp13 = 22
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 24:
                tmp13 = 23
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 25:
                tmp13 = 24
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 26:
                tmp13 = 25
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 27:
                tmp13 = 26
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 28:
                tmp13 = 27
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 29:
                tmp13 = 28
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 30:
                tmp13 = 29
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 31:
                tmp13 = 30
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 32:
                tmp13 = 31
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 176
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 180
                else:
                    break
            case 33:
                tmp13 = 32
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 34:
                tmp13 = 33
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 35:
                tmp13 = 34
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 152
                else:
                    break
            case 36:
                tmp13 = 35
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 37:
                tmp13 = 36
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 38:
                tmp13 = 37
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 39:
                tmp13 = 38
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 40:
                tmp13 = 39
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 41:
                tmp13 = 40
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 42:
                tmp13 = 41
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 43:
                tmp13 = 42
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 44:
                tmp13 = 43
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 199
                else:
                    break
            case 45:
                tmp13 = 44
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 46:
                tmp13 = 45
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 47:
                tmp13 = 46
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 48:
                tmp13 = 47
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 49:
                tmp13 = 48
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 50:
                tmp13 = 49
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 51:
                tmp13 = 50
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 52:
                tmp13 = 51
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 53:
                tmp13 = 52
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 54:
                tmp13 = 53
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 55:
                tmp13 = 54
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 56:
                tmp13 = 55
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 57:
                tmp13 = 56
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 58:
                tmp13 = 57
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 59:
                tmp13 = 58
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 60:
                tmp13 = 59
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 61:
                tmp13 = 60
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 62:
                tmp13 = 61
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 63:
                tmp13 = 62
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 64:
                tmp13 = 63
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 65:
                tmp13 = 64
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 66:
                tmp13 = 65
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 67:
                tmp13 = 66
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 68:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 196
                else:
                    break
            case 69:
                if tmp12 in Tset[char](inrange(char('A'), char('Z')), char('g'), char('h'), char('j'), char('k'), char('q'), char('z'), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 78
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 80
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 82
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 84
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 89
                elif tmp12 == char('f'):
                    pos += 1
                    tmp11 = 93
                elif tmp12 == char('m'):
                    pos += 1
                    tmp11 = 97
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 99
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 100
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 105
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 108
                elif tmp12 == char('v'):
                    pos += 1
                    tmp11 = 117
                elif tmp12 == char('x'):
                    pos += 1
                    tmp11 = 120
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 121
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 130
                elif tmp12 == char('w'):
                    pos += 1
                    tmp11 = 138
                elif tmp12 == char('b'):
                    pos += 1
                    tmp11 = 148
                elif tmp12 == char('y'):
                    pos += 1
                    tmp11 = 150
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 158
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 159
                else:
                    break
            case 70:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 57
                else:
                    break
            case 71:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('t')), inrange(char('v'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 22
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 218
                else:
                    break
            case 72:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 65
                else:
                    break
            case 73:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('e')), inrange(char('g'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('f'):
                    pos += 1
                    tmp11 = 53
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 134
                else:
                    break
            case 74:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('f')), inrange(char('h'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('g'):
                    pos += 1
                    tmp11 = 62
                else:
                    break
            case 75:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('j')), inrange(char('l'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('k'):
                    pos += 1
                    tmp11 = 8
                else:
                    break
            case 76:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 43
                else:
                    break
            case 77:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('l')), inrange(char('n'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('m'):
                    pos += 1
                    tmp11 = 28
                else:
                    break
            case 78:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('e')), inrange(char('g'), char('l')), inrange(char('o'), char('r')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('f'):
                    pos += 1
                    tmp11 = 30
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 32
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 35
                elif tmp12 == char('m'):
                    pos += 1
                    tmp11 = 111
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 125
                else:
                    break
            case 79:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 64
                else:
                    break
            case 80:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('h')), inrange(char('j'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 19
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 87
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 126
                else:
                    break
            case 81:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 55
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 56
                else:
                    break
            case 82:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), inrange(char('c'), char('e')), inrange(char('g'), char('q')), char('s'), char('t'), inrange(char('v'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('f'):
                    pos += 1
                    tmp11 = 47
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 48
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 86
                elif tmp12 == char('b'):
                    pos += 1
                    tmp11 = 115
                else:
                    break
            case 83:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 66
                else:
                    break
            case 84:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('m')), inrange(char('o'), char('r')), inrange(char('t'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 4
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 118
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 232
                else:
                    break
            case 85:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 9
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 10
                else:
                    break
            case 86:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 49
                else:
                    break
            case 87:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('r')), char('t'), char('u'), inrange(char('w'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('v'):
                    pos += 1
                    tmp11 = 18
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 114
                else:
                    break
            case 88:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('x')), char('z'), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('y'):
                    pos += 1
                    tmp11 = 59
                else:
                    break
            case 89:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('q')), char('s'), char('t'), inrange(char('v'), char('x')), char('z'), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 88
                elif tmp12 == char('y'):
                    pos += 1
                    tmp11 = 163
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 172
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 174
                else:
                    break
            case 90:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 68
                else:
                    break
            case 91:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 90
                else:
                    break
            case 92:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 91
                else:
                    break
            case 93:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('n')), char('p'), char('q'), char('s'), char('t'), inrange(char('v'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 92
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 139
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 182
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 211
                else:
                    break
            case 94:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 95
                else:
                    break
            case 95:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 39
                else:
                    break
            case 96:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 94
                else:
                    break
            case 97:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('d')), inrange(char('f'), char('h')), inrange(char('j'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 96
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 137
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 147
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 187
                else:
                    break
            case 98:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 203
                else:
                    break
            case 99:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 207
                else:
                    break
            case 100:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 76
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 204
                else:
                    break
            case 101:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('o')), inrange(char('q'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 220
                else:
                    break
            case 102:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 212
                else:
                    break
            case 103:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('r')), char('u'), inrange(char('w'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('v'):
                    pos += 1
                    tmp11 = 129
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 168
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 223
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 225
                else:
                    break
            case 104:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 103
                else:
                    break
            case 105:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 104
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 116
                else:
                    break
            case 106:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 102
                else:
                    break
            case 107:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('o')), inrange(char('q'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 109
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 217
                else:
                    break
            case 108:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), char('m'), inrange(char('o'), char('w')), char('y'), char('z'), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 71
                elif tmp12 == char('x'):
                    pos += 1
                    tmp11 = 107
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 135
                else:
                    break
            case 109:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 101
                else:
                    break
            case 110:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 98
                else:
                    break
            case 111:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('o')), inrange(char('q'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 106
                else:
                    break
            case 112:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 205
                else:
                    break
            case 113:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 112
                else:
                    break
            case 114:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 113
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 145
                else:
                    break
            case 115:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('i')), inrange(char('k'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('j'):
                    pos += 1
                    tmp11 = 110
                else:
                    break
            case 116:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('r')), inrange(char('t'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 85
                else:
                    break
            case 117:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 188
                else:
                    break
            case 118:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 229
                else:
                    break
            case 119:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 219
                else:
                    break
            case 120:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 83
                else:
                    break
            case 121:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), char('s'), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 183
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 193
                else:
                    break
            case 122:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 189
                else:
                    break
            case 123:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 122
                else:
                    break
            case 124:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 123
                else:
                    break
            case 125:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 124
                else:
                    break
            case 126:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('e')), inrange(char('g'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('f'):
                    pos += 1
                    tmp11 = 119
                else:
                    break
            case 127:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 228
                else:
                    break
            case 128:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 127
                else:
                    break
            case 129:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 128
                else:
                    break
            case 130:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('g')), inrange(char('i'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('h'):
                    pos += 1
                    tmp11 = 81
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 185
                else:
                    break
            case 131:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 79
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 162
                else:
                    break
            case 132:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 206
                else:
                    break
            case 133:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 192
                else:
                    break
            case 134:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('t')), inrange(char('v'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 133
                else:
                    break
            case 135:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('r')), inrange(char('t'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 136
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 214
                else:
                    break
            case 136:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('e')), inrange(char('g'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('f'):
                    pos += 1
                    tmp11 = 20
                else:
                    break
            case 137:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('w')), char('y'), char('z'), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('x'):
                    pos += 1
                    tmp11 = 132
                else:
                    break
            case 138:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('g')), inrange(char('i'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('h'):
                    pos += 1
                    tmp11 = 131
                else:
                    break
            case 139:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 77
                else:
                    break
            case 140:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 141
                else:
                    break
            case 141:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 67
                else:
                    break
            case 142:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 226
                else:
                    break
            case 143:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 208
                else:
                    break
            case 144:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 209
                else:
                    break
            case 145:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 144
                else:
                    break
            case 146:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('g')), inrange(char('i'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('h'):
                    pos += 1
                    tmp11 = 143
                else:
                    break
            case 147:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 146
                else:
                    break
            case 148:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), char('j'), char('k'), inrange(char('m'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 142
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 154
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 155
                else:
                    break
            case 149:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 140
                else:
                    break
            case 150:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 149
                else:
                    break
            case 151:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 75
                else:
                    break
            case 152:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 210
                else:
                    break
            case 153:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 231
                else:
                    break
            case 154:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 153
                else:
                    break
            case 155:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 151
                else:
                    break
            case 156:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 74
                else:
                    break
            case 157:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 156
                else:
                    break
            case 158:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('r')), inrange(char('t'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 157
                else:
                    break
            case 159:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 73
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 173
                else:
                    break
            case 160:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 200
                else:
                    break
            case 161:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 213
                else:
                    break
            case 162:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 72
                else:
                    break
            case 163:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('o')), inrange(char('q'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 190
                else:
                    break
            case 164:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('r')), inrange(char('t'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('s'):
                    pos += 1
                    tmp11 = 197
                else:
                    break
            case 165:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 195
                else:
                    break
            case 166:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('t')), inrange(char('v'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 224
                else:
                    break
            case 167:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 166
                else:
                    break
            case 168:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 167
                else:
                    break
            case 169:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 165
                else:
                    break
            case 170:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 169
                else:
                    break
            case 171:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('o')), inrange(char('q'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 170
                else:
                    break
            case 172:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('l')), inrange(char('n'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('m'):
                    pos += 1
                    tmp11 = 171
                else:
                    break
            case 173:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 164
                else:
                    break
            case 174:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('o')), inrange(char('q'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 191
                else:
                    break
            case 175:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('t')), inrange(char('v'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('u'):
                    pos += 1
                    tmp11 = 161
                else:
                    break
            case 176:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 175
                else:
                    break
            case 177:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 160
                else:
                    break
            case 178:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('e')), inrange(char('g'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('f'):
                    pos += 1
                    tmp11 = 177
                else:
                    break
            case 179:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 178
                else:
                    break
            case 180:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 179
                else:
                    break
            case 181:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('h')), inrange(char('j'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('i'):
                    pos += 1
                    tmp11 = 70
                else:
                    break
            case 182:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 202
                else:
                    break
            case 183:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 198
                else:
                    break
            case 184:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 181
                else:
                    break
            case 185:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('b'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('a'):
                    pos += 1
                    tmp11 = 184
                else:
                    break
            case 186:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                else:
                    break
            case 187:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 42
                else:
                    break
            case 188:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 63
                else:
                    break
            case 189:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 201
                else:
                    break
            case 190:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 61
                else:
                    break
            case 191:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('k')), inrange(char('m'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('l'):
                    pos += 1
                    tmp11 = 194
                else:
                    break
            case 192:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 54
                else:
                    break
            case 193:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 51
                else:
                    break
            case 194:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 60
                else:
                    break
            case 195:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 58
                else:
                    break
            case 196:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('x')), char('z'), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('y'):
                    pos += 1
                    tmp11 = 26
                else:
                    break
            case 197:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 52
                else:
                    break
            case 198:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 50
                else:
                    break
            case 199:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 45
                else:
                    break
            case 200:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 34
                else:
                    break
            case 201:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 37
                else:
                    break
            case 202:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 29
                else:
                    break
            case 203:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 46
                else:
                    break
            case 204:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 44
                else:
                    break
            case 205:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), char('a'), char('b'), inrange(char('d'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('c'):
                    pos += 1
                    tmp11 = 221
                else:
                    break
            case 206:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('m')), inrange(char('o'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('n'):
                    pos += 1
                    tmp11 = 41
                else:
                    break
            case 207:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 38
                else:
                    break
            case 208:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 40
                else:
                    break
            case 209:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 16
                else:
                    break
            case 210:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 36
                else:
                    break
            case 211:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 27
                else:
                    break
            case 212:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 31
                else:
                    break
            case 213:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 33
                else:
                    break
            case 214:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 21
                else:
                    break
            case 215:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 25
                else:
                    break
            case 216:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 215
                else:
                    break
            case 217:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('n')), inrange(char('p'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('o'):
                    pos += 1
                    tmp11 = 216
                else:
                    break
            case 218:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('l')), inrange(char('n'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('m'):
                    pos += 1
                    tmp11 = 23
                else:
                    break
            case 219:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 15
                else:
                    break
            case 220:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 24
                else:
                    break
            case 221:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 17
                else:
                    break
            case 222:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('o')), inrange(char('q'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('p'):
                    pos += 1
                    tmp11 = 230
                else:
                    break
            case 223:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 222
                else:
                    break
            case 224:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 13
                else:
                    break
            case 225:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 12
                else:
                    break
            case 226:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 6
                else:
                    break
            case 227:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 14
                else:
                    break
            case 228:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('d')), inrange(char('f'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('e'):
                    pos += 1
                    tmp11 = 227
                else:
                    break
            case 229:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('q')), inrange(char('s'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('r'):
                    pos += 1
                    tmp11 = 2
                else:
                    break
            case 230:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('s')), inrange(char('u'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('t'):
                    pos += 1
                    tmp11 = 11
                else:
                    break
            case 231:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('j')), inrange(char('l'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('k'):
                    pos += 1
                    tmp11 = 7
                else:
                    break
            case 232:
                tmp13 = 67
                tmp14 = copy(pos)
                if tmp12 in Tset[char](inrange(char('0'), char('9')), inrange(char('A'), char('Z')), inrange(char('a'), char('c')), inrange(char('e'), char('z')), inrange(char('\x80'), char('\xff'))):
                    pos += 1
                    tmp11 = 186
                elif tmp12 == char('_'):
                    pos += 1
                    tmp11 = 1
                elif tmp12 == char('d'):
                    pos += 1
                    tmp11 = 3
                else:
                    break
            case _:
                break
    pos <<= tmp14
    match tmp13:
        case 1:
            result = TokKind.tkAddr
        case 2:
            result = TokKind.tkAnd
        case 3:
            result = TokKind.tkAs
        case 4:
            result = TokKind.tkAsm
        case 5:
            result = TokKind.tkBind
        case 6:
            result = TokKind.tkBlock
        case 7:
            result = TokKind.tkBreak
        case 8:
            result = TokKind.tkCase
        case 9:
            result = TokKind.tkCast
        case 10:
            result = TokKind.tkConcept
        case 11:
            result = TokKind.tkConst
        case 12:
            result = TokKind.tkContinue
        case 13:
            result = TokKind.tkConverter
        case 14:
            result = TokKind.tkDefer
        case 15:
            result = TokKind.tkDiscard
        case 16:
            result = TokKind.tkDistinct
        case 17:
            result = TokKind.tkDiv
        case 18:
            result = TokKind.tkDo
        case 19:
            result = TokKind.tkElif
        case 20:
            result = TokKind.tkElse
        case 21:
            result = TokKind.tkEnd
        case 22:
            result = TokKind.tkEnum
        case 23:
            result = TokKind.tkExcept
        case 24:
            result = TokKind.tkExport
        case 25:
            result = TokKind.tkFinally
        case 26:
            result = TokKind.tkFor
        case 27:
            result = TokKind.tkFrom
        case 28:
            result = TokKind.tkFunc
        case 29:
            result = TokKind.tkIf
        case 30:
            result = TokKind.tkImport
        case 31:
            result = TokKind.tkIn
        case 32:
            result = TokKind.tkInclude
        case 33:
            result = TokKind.tkInterface
        case 34:
            result = TokKind.tkIs
        case 35:
            result = TokKind.tkIsnot
        case 36:
            result = TokKind.tkIterator
        case 37:
            result = TokKind.tkLet
        case 38:
            result = TokKind.tkMacro
        case 39:
            result = TokKind.tkMethod
        case 40:
            result = TokKind.tkMixin
        case 41:
            result = TokKind.tkMod
        case 42:
            result = TokKind.tkNil
        case 43:
            result = TokKind.tkNot
        case 44:
            result = TokKind.tkNotin
        case 45:
            result = TokKind.tkObject
        case 46:
            result = TokKind.tkOf
        case 47:
            result = TokKind.tkOr
        case 48:
            result = TokKind.tkOut
        case 49:
            result = TokKind.tkProc
        case 50:
            result = TokKind.tkPtr
        case 51:
            result = TokKind.tkRaise
        case 52:
            result = TokKind.tkRef
        case 53:
            result = TokKind.tkReturn
        case 54:
            result = TokKind.tkShl
        case 55:
            result = TokKind.tkShr
        case 56:
            result = TokKind.tkStatic
        case 57:
            result = TokKind.tkTemplate
        case 58:
            result = TokKind.tkTry
        case 59:
            result = TokKind.tkTuple
        case 60:
            result = TokKind.tkType
        case 61:
            result = TokKind.tkUsing
        case 62:
            result = TokKind.tkVar
        case 63:
            result = TokKind.tkWhen
        case 64:
            result = TokKind.tkWhile
        case 65:
            result = TokKind.tkXor
        case 66:
            result = TokKind.tkYield
        case 67:
            result = TokKind.tkSymbol
        case _:
            pass
    return result


def _scanSymbol(L: mut @ Lexer, tok: mut @ Token):
    with let:
        start = copy(L.pos)
    with var:
        pos = copy(L.pos)
        kind = _symbolKind(L.buf, pos)
    if kind == TokKind.tkInvalid:
        tok.kind = TokKind.tkInvalid
        tok.s = _str(L.ch(pos))
        pos += 1
        L.pos = pos
        return
    # A byte in `UnicodeOperatorStartChars` that begins a unicode operator ends
    # the identifier; the automaton has no way to know that, so cut here -- and
    # ask again what the shorter text is, since `and∙` starts with a keyword.
    with var:
        i = copy(start)
    while i < pos:
        if L.buf[i] in UnicodeOperatorStartChars and unicodeOprLen(L.buf, i)[0] != 0:
            pos = i
            with let:
                cut = L.buf.substr(start, pos - 1)
            with var:
                p = nint(0)
            kind = _symbolKind(cut, p)
            if p != cut.len: kind = TokKind.tkSymbol
            break
        i += 1
    if pos == start:
        tok.kind = TokKind.tkInvalid
        tok.s = _str(L.ch(pos))
        pos += 1
        L.pos = pos
        return
    if L.ch(pos) == char('_'):
        L._error(start, string("invalid token: trailing underscore"))
    L.pos = pos
    tok.s = L.buf.substr(start, pos - 1)
    tok.kind = kind

# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# String and character literals
# ---------------------------------------------------------------------------


def _addUnicodeCodePoint(s: mut @ string, i: nint):
    ## UTF-8 encode; the only place `nimlexer` produces multi-byte output of its
    ## own rather than copying input.
    if i <= 127:
        s.add(chr(i))
    elif i <= 0x07FF:
        s.add(chr((i >> 6) | 0b1100_0000))
        s.add(chr((i & 0b0011_1111) | 0b1000_0000))
    elif i <= 0xFFFF:
        s.add(chr((i >> 12) | 0b1110_0000))
        s.add(chr(((i >> 6) & 0b0011_1111) | 0b1000_0000))
        s.add(chr((i & 0b0011_1111) | 0b1000_0000))
    else:
        s.add(chr((i >> 18) | 0b1111_0000))
        s.add(chr(((i >> 12) & 0b0011_1111) | 0b1000_0000))
        s.add(chr(((i >> 6) & 0b0011_1111) | 0b1000_0000))
        s.add(chr((i & 0b0011_1111) | 0b1000_0000))


def _getEscapedChar(L: mut @ Lexer, tok: mut @ Token):
    L.pos += 1  # skip '\'
    with let:
        c = L.ch(L.pos)
    match c:
        case _ if c == char('n') or c == char('N'):
            tok.s.add(char('\n'))
            L.pos += 1
        case _ if c == char('p') or c == char('P'):
            if tok.kind == TokKind.tkCharLit:
                L._error(L.pos, string("\\p not allowed in character literal"))
            tok.s.add(char('\n'))
            L.pos += 1
        case _ if c == char('r') or c == char('R') or c == char('c') or c == char('C'):
            tok.s.add(char('\r'))
            L.pos += 1
        case _ if c == char('l') or c == char('L'):
            tok.s.add(char('\n'))
            L.pos += 1
        case _ if c == char('f') or c == char('F'):
            tok.s.add(char('\x0c'))
            L.pos += 1
        case _ if c == char('e') or c == char('E'):
            tok.s.add(char('\x1b'))
            L.pos += 1
        case _ if c == char('a') or c == char('A'):
            tok.s.add(char('\x07'))
            L.pos += 1
        case _ if c == char('b') or c == char('B'):
            tok.s.add(char('\x08'))
            L.pos += 1
        case _ if c == char('v') or c == char('V'):
            tok.s.add(char('\x0b'))
            L.pos += 1
        case _ if c == char('t') or c == char('T'):
            tok.s.add(char('\t'))
            L.pos += 1
        case _ if c == char('\'') or c == char('"'):
            tok.s.add(c)
            L.pos += 1
        case _ if c == char('\\'):
            tok.s.add(char('\\'))
            L.pos += 1
        case _ if c == char('x') or c == char('X'):
            L.pos += 1
            with var:
                xi = nint(0)
            L._handleHexChar(xi, 1)
            L._handleHexChar(xi, 2)
            tok.s.add(chr(xi))
        case _ if c == char('u') or c == char('U'):
            if tok.kind == TokKind.tkCharLit:
                L._error(L.pos, string("\\u not allowed in character literal"))
            L.pos += 1
            with var:
                xi = nint(0)
            if L.ch(L.pos) == char('{'):
                L.pos += 1
                with let:
                    start = copy(L.pos)
                while L.ch(L.pos) != char('}') and L.ch(L.pos) != char('\x00'):
                    L._handleHexChar(xi, 0)
                if start == L.pos: L._error(L.pos, string("Unicode codepoint cannot be empty"))
                if L.ch(L.pos) == char('}'): L.pos += 1
                if xi > 0x10FFFF:
                    L._error(L.pos, string("Unicode codepoint must be lower than 0x10FFFF"))
            else:
                L._handleHexChar(xi, 1)
                L._handleHexChar(xi, 2)
                L._handleHexChar(xi, 3)
                L._handleHexChar(xi, 4)
            _addUnicodeCodePoint(tok.s, xi)
        case _ if c in inrange(char('0'), char('9')):
            with var:
                xi = 0
            while L.ch(L.pos) >= char('0') and L.ch(L.pos) <= char('9'):
                xi = xi * 10 + (ord(L.ch(L.pos)) - ord(char('0')))
                L.pos += 1
            if xi <= 255: tok.s.add(chr(xi))
            else: L._error(L.pos, string("invalid character constant"))
        case _:
            L._error(L.pos, string("invalid character constant"))
            L.pos += 1


class _StringMode(NIntEnum):
    smNormal = auto()
    smRaw = auto()
    smGeneralized = auto()


def _getString(L: mut @ Lexer, tok: mut @ Token, mode: _StringMode):
    with var:
        pos = copy(L.pos)
    with let:
        line = copy(L.lineNumber)
    pos += 1  # skip the opening quote
    if L.ch(pos) == char('"') and L.ch(pos + 1) == char('"'):
        tok.kind = TokKind.tkTripleStrLit
        pos += 2
        # a newline directly after `"""` is not part of the string
        if L.ch(pos) == char(' ') or L.ch(pos) == char('\t'):
            with var:
                newpos = nint(pos + 1)
            while L.ch(newpos) == char(' ') or L.ch(newpos) == char('\t'): newpos += 1
            if L.ch(newpos) == char('\r') or L.ch(newpos) == char('\n'): pos = newpos
        if L.ch(pos) == char('\r') or L.ch(pos) == char('\n'):
            pos = L._handleCRLF(pos)
        while True:
            with let:
                c = L.ch(pos)
            if c == char('"'):
                if L.ch(pos + 1) == char('"') and L.ch(pos + 2) == char('"') and L.ch(pos + 3) != char('"'):
                    pos = pos + 3
                    break
                tok.s.add(char('"'))
                pos += 1
            elif c == char('\r') or c == char('\n'):
                pos = L._handleCRLF(pos)
                tok.s.add(char('\n'))
            elif c == char('\x00'):
                L._errorAt(line, 0, string("closing \"\"\" expected, but end of file reached"))
                break
            else:
                tok.s.add(c)
                pos += 1
        L.pos = pos
    else:
        tok.kind = TokKind.tkStrLit if mode == _StringMode.smNormal else TokKind.tkRStrLit
        while True:
            with let:
                c = L.ch(pos)
            if c == char('"'):
                if mode != _StringMode.smNormal and L.ch(pos + 1) == char('"'):
                    pos += 2
                    tok.s.add(char('"'))
                else:
                    pos += 1
                    break
            elif c == char('\r') or c == char('\n') or c == char('\x00'):
            # at `L.pos`: the opening quote, or behind the last escape sequence
                L._error(L.pos, string("closing \" expected"))
                break
            elif c == char('\\') and mode == _StringMode.smNormal:
                L.pos = pos
                _getEscapedChar(L, tok)
                pos = L.pos.copy()
            else:
                tok.s.add(c)
                pos += 1
        L.pos = pos


def _getCharacter(L: mut @ Lexer, tok: mut @ Token):
    with let:
        startPos = copy(L.pos)
    tok.kind = TokKind.tkCharLit
    L.pos += 1  # skip '
    with let:
        c = L.ch(L.pos)
    if c < char(' ') or c == char('\''):
        L._error(L.pos, string("invalid character literal"))
        tok.s = _str(c)
    elif c == char('\\'):
        _getEscapedChar(L, tok)
    else:
        tok.s = _str(c)
        L.pos += 1
    if L.ch(L.pos) == char('\''):
        L.pos += 1
    elif startPos > 0 and L.ch(startPos - 1) == char('`'):
    # `'` as an operator name inside backticks
        tok.s = string("'")
        L.pos = startPos + 1
    else:
        L._error(L.pos, string("missing closing ' for character literal"))

# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


def _getOperator(L: mut @ Lexer, tok: mut @ Token):
    with let:
        start = copy(L.pos)
    with var:
        pos = copy(L.pos)
    while True:
        with let:
            c = L.ch(pos)
        if c in OpChars:
            pos += 1
        elif c in UnicodeOperatorStartChars:
            with let:
                n = unicodeOprLen(L.buf, pos)[0]
            if n == 0: break
            pos += n
        else:
            break
    L._endOperator(tok, start, pos - 1)
    # An operator's trailing spacing decides whether it is unary, so it is read
    # here without moving `L.pos`: the next token still gets its leading space.
    tok.spacing = tok.spacing - Tset[TokSpacing](TokSpacing.tsTrailing, TokSpacing.tsEof)
    with var:
        trailing = False
    while L.ch(pos) == char(' '):
        pos += 1
        trailing = True
    with let:
        c = L.ch(pos)
    if c == char('\r') or c == char('\n') or c == char('\x00'): tok.spacing.incl(TokSpacing.tsEof)
    elif trailing: tok.spacing.incl(TokSpacing.tsTrailing)

# ---------------------------------------------------------------------------
# Whitespace, and the indentation it produces
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# The main dispatch
# ---------------------------------------------------------------------------


def openLexer(src: string, filename=string("")) -> Lexer:
    result = Lexer(buf=src, pos=0, filename=filename, lineNumber=1, lineStart=0, currLineIndent=0, indentAhead=-1, errors=seq[string]([]))
    # `nimlexbase` skips a UTF-8 BOM before the lexer ever sees the file; here
    # the whole source is one string, so it is skipped on the way in.
    if src.len >= 3 and src[0] == char('\xef') and src[1] == char('\xbb') and src[2] == char('\xbf'):
        result.pos = 3
        result.lineStart = 3
    return result


def next(L: mut @ Lexer, tok: mut @ Token):
    ## One token. Mirrors `rawGetTok` in `compiler/lexer.nim` branch for branch,
    ## because that is what the differential test compares against.
    with let:
        carry = tok.spacing * Tset[TokSpacing](TokSpacing.tsLeading)
    tok <<= Token(kind=TokKind.tkInvalid, s=string(""), indent=-1, spacing=carry, line=0, col=0, base=10, suffixPos=-1)
    if L.indentAhead >= 0:
        tok.indent = L.indentAhead
        L.currLineIndent = L.indentAhead
        L.indentAhead = -1
    L._skip(tok)
    with let:
        c = L.ch(L.pos)
    tok.line = L.lineNumber
    tok.col = int32(L.pos - L.lineStart)

    if c in SymStartChars - Tset[char](char('r'), char('R')) - UnicodeOperatorStartChars:
        _scanSymbol(L, tok)
    elif c in UnicodeOperatorStartChars:
        if unicodeOprLen(L.buf, L.pos)[0] != 0: _getOperator(L, tok)
        else: _scanSymbol(L, tok)
    elif c == char('#'):
        L._scanComment(tok)
    elif c == char('*'):
    # `*:` is two tokens in `var v*: int`, and one operator in `a *: b`
        if L.ch(L.pos + 1) == char(':') and L.ch(L.pos + 2) not in OpChars:
            L._endOperator(tok, L.pos, L.pos)
        else:
            _getOperator(L, tok)
    elif c == char(','):
        tok.kind = TokKind.tkComma
        L.pos += 1
    elif c == char('r') or c == char('R'):
        if L.ch(L.pos + 1) == char('"'):
            L.pos += 1
            _getString(L, tok, _StringMode.smRaw)
        else:
            _scanSymbol(L, tok)
    elif c == char('('):
        L.pos += 1
        if L.ch(L.pos) == char('.') and L.ch(L.pos + 1) != char('.'):
            tok.kind = TokKind.tkParDotLe
            L.pos += 1
        else:
            tok.kind = TokKind.tkParLe
    elif c == char(')'):
        tok.kind = TokKind.tkParRi
        L.pos += 1
    elif c == char('['):
        L.pos += 1
        if L.ch(L.pos) == char('.') and L.ch(L.pos + 1) != char('.'):
            tok.kind = TokKind.tkBracketDotLe
            L.pos += 1
        elif L.ch(L.pos) == char(':'):
            tok.kind = TokKind.tkBracketLeColon
            L.pos += 1
        else:
            tok.kind = TokKind.tkBracketLe
    elif c == char(']'):
        tok.kind = TokKind.tkBracketRi
        L.pos += 1
    elif c == char('.'):
        if L.ch(L.pos + 1) == char(']'):
            tok.kind = TokKind.tkBracketDotRi
            L.pos += 2
        elif L.ch(L.pos + 1) == char('}'):
            tok.kind = TokKind.tkCurlyDotRi
            L.pos += 2
        elif L.ch(L.pos + 1) == char(')'):
            tok.kind = TokKind.tkParDotRi
            L.pos += 2
        else:
            _getOperator(L, tok)
    elif c == char('{'):
        L.pos += 1
        if L.ch(L.pos) == char('.') and L.ch(L.pos + 1) != char('.'):
            tok.kind = TokKind.tkCurlyDotLe
            L.pos += 1
        else:
            tok.kind = TokKind.tkCurlyLe
    elif c == char('}'):
        tok.kind = TokKind.tkCurlyRi
        L.pos += 1
    elif c == char(';'):
        tok.kind = TokKind.tkSemiColon
        L.pos += 1
    elif c == char('`'):
        tok.kind = TokKind.tkAccent
        L.pos += 1
    elif c == char('_'):
        L.pos += 1
        if L.ch(L.pos) not in SymChars + Tset[char](char('_')):
            tok.kind = TokKind.tkSymbol
            tok.s = string("_")
        else:
            tok.kind = TokKind.tkInvalid
            tok.s = string("_")
            L._error(L.pos, string("invalid token: _"))
    elif c == char('"'):
    # `foo"bar"` is a generalized string literal, `foo "bar"` is a command
        with let:
            mode = _StringMode.smGeneralized if L.pos > 0 and L.ch(L.pos - 1) in SymChars else _StringMode.smNormal
        _getString(L, tok, mode)
        if mode == _StringMode.smGeneralized:
            if tok.kind == TokKind.tkRStrLit: tok.kind = TokKind.tkGStrLit
            elif tok.kind == TokKind.tkTripleStrLit: tok.kind = TokKind.tkGTripleStrLit
    elif c == char('\''):
        _getCharacter(L, tok)
    elif c >= char('0') and c <= char('9'):
        _scanNumber(L, tok)
    elif c == char('-'):
        if L.ch(L.pos + 1) >= char('0') and L.ch(L.pos + 1) <= char('9') and (L.pos == 0 or L.ch(L.pos - 1) in _UnaryMinusWhitelist):
            _scanNumber(L, tok)
        else:
            _getOperator(L, tok)
    elif c in OpChars:
        _getOperator(L, tok)
    elif c == char('\x00'):
        tok.kind = TokKind.tkEof
        tok.indent = 0
    else:
        tok.kind = TokKind.tkInvalid
        tok.s = _str(c)
        L._error(L.pos, string("invalid token: ") + _str(c) + string(" (\\") + str(ord(c)) + string(")"))
        L.pos += 1


def tokens(src: string, filename=string("")) -> Token:
    """{.sideEffect.}"""
    ## Every token of `src`, `tkEof` last.
    with var:
        L = openLexer(src, filename)
        tok = Token(kind=TokKind.tkInvalid, s=string(""), indent=-1, spacing=Tset[TokSpacing](), line=0, col=0, base=10, suffixPos=-1)
    while True:
        next(L, tok)
        yield tok
        if tok.kind == TokKind.tkEof: break


if comptime(__name__ == "__main__"):
    # Token-level tests, the cases of nimony's `src/nifler2/tests/tnimlexer.nim` (its expectations come from Nim 2's
    # own lexer, `bin/refdump`, except `caseSensitiveKeywords`). That test doesn't build at the pin (nimony's sem:
    # "unsynchronized access to global variable 'failures'"), so its cases run here, `failures` a local.
    def esc(s: string) -> string:
        result = string("")
        with var:
            i = 0
        while i < s.len:
            with let:
                c = s[i]
            if c == char('\n'): result.add(string("\\n"))
            elif c == char('\r'): result.add(string("\\r"))
            elif c == char('\t'): result.add(string("\\t"))
            elif c == char('\\'): result.add(string("\\\\"))
            else: result.add(c)
            i += 1
        return result

    def text(tok: Token) -> string:
        if tok.kind == TokKind.tkSymbol: return nimIdentNormalize(tok.s)
        elif tok.kind >= KeywordLow and tok.kind <= KeywordHigh: return string("")
        elif tok.kind in Tset[TokKind](TokKind.tkOpr, TokKind.tkColon, TokKind.tkColonColon, TokKind.tkEquals,
                                        TokKind.tkDot, TokKind.tkDotDot):
            return tok.s.copy()
        elif tok.kind >= TokKind.tkIntLit and tok.kind <= TokKind.tkCustomLit: return tok.s.copy()
        elif tok.kind == TokKind.tkComment: return tok.s.copy()
        else: return string("")

    def render(src: string) -> string:
        result = string("")
        for tok in tokens(src, string("t.nim")):
            if tok.kind == TokKind.tkEof: break
            if result.len > 0: result.add(string(" "))
            result.add(str(tok.kind))
            with let:
                t = text(tok)
            if t.len > 0:
                result.add(string("("))
                result.add(esc(t))
                result.add(string(")"))
            if tok.indent >= 0:
                result.add(string("@"))
                result.add(str(tok.indent))
            with var:
                sp = string("")
            if TokSpacing.tsLeading in tok.spacing: sp.add(string("L"))
            if TokSpacing.tsTrailing in tok.spacing: sp.add(string("T"))
            if TokSpacing.tsEof in tok.spacing: sp.add(string("E"))
            if sp.len > 0:
                result.add(string("/"))
                result.add(sp)
        return result

    def check(name: string, src: string, expected: string) -> bool:
        with let:
            got = render(src)
        if got == expected:
            echo("ok ", name)
            return True
        echo("FAIL ", name)
        echo("  got:      ", got)
        echo("  expected: ", expected)
        return False

    with var:
        failures = 0
    if not check(string("keywords"), string("if x: y\n"), string("if tkSymbol(x)/L :(:)/T tkSymbol(y)/L")): failures += 1
    # Nimony's keywords are case-sensitive; Nim would make the first two `proc`
    if not check(string("caseSensitiveKeywords"), string("p_roc pRoC Proc proc\n"), string("tkSymbol(proc) tkSymbol(proc)/L tkSymbol(Proc)/L proc/L")): failures += 1
    if not check(string("keywordBeforeUnicodeOpr"), utf8("and∙b\n"), utf8("and tkOpr(∙) tkSymbol(b)")): failures += 1
    if not check(string("suffixes"), string("1'I8 2'big 0x1f32 3'f32x 4U16 0xFF'f\n"), string("tkInt8Lit(1) tkCustomLit(2'big)/L tkIntLit(0x1f32)/L tkCustomLit(3'f32x)/L tkUInt16Lit(4)/L tkFloat32Lit(0xFF)/L")): failures += 1
    if not check(string("ints"), string("0 12 1_000 0xFF 0b1010 0o17\n"), string("tkIntLit(0) tkIntLit(12)/L tkIntLit(1_000)/L tkIntLit(0xFF)/L tkIntLit(0b1010)/L tkIntLit(0o17)/L")): failures += 1
    if not check(string("bigInt"), string("0xffffffff 2147483648 2147483647\n"), string("tkInt64Lit(0xffffffff) tkInt64Lit(2147483648)/L tkIntLit(2147483647)/L")): failures += 1
    if not check(string("floats"), string("1.5 1e5 2.5e-3 1'f32 3.0'f64\n"), string("tkFloatLit(1.5) tkFloatLit(1e5)/L tkFloatLit(2.5e-3)/L tkFloat32Lit(1)/L tkFloat64Lit(3.0)/L")): failures += 1
    if not check(string("intSuffix"), string("1'i8 12u8 5i64\n"), string("tkInt8Lit(1) tkUInt8Lit(12)/L tkInt64Lit(5)/L")): failures += 1
    if not check(string("basePrefixCase"), string("0X10 0B10 0O7 0C7\n"), string("tkIntLit(0x10) tkIntLit(0b10)/L tkIntLit(0)/L tkSymbol(O7) tkIntLit(0c7)/L")): failures += 1
    if not check(string("emptyBase"), string("0x 0b\n"), string("tkIntLit(0x) tkIntLit(0b)/L")): failures += 1
    if not check(string("customLit"), string("12'big\n"), string("tkCustomLit(12'big)")): failures += 1
    if not check(string("dotdot"), string("1..2\n"), string("tkIntLit(1) ..(..) tkIntLit(2)")): failures += 1
    if not check(string("digraphs"), string("{. .} [. .] (. .) [: ::\n"), string("{. .}/L [./L .]/L (./L .)/L [:/L ::(::)/LE")): failures += 1
    if not check(string("parDotVsDotDot"), string("(..2)\n"), string("( ..(..) tkIntLit(2) )")): failures += 1
    if not check(string("starColon"), string("var v*: int\n"), string("var tkSymbol(v)/L tkOpr(*) :(:)/T tkSymbol(int)/L")): failures += 1
    if not check(string("strings"), string("\"a\\nb\" r\"a\\nb\"\n"), string("tkStrLit(a\\nb) tkRStrLit(a\\\\nb)/L")): failures += 1
    if not check(string("tripleStr"), string("\"\"\"a\nb\"\"\"\n"), string("tkTripleStrLit(a\\nb)")): failures += 1
    if not check(string("gstr"), string("re\"x\"\n"), string("tkSymbol(re) tkGStrLit(x)")): failures += 1
    if not check(string("chars"), string("'a' '\\n' '\\x41'\n"), string("tkCharLit(a) tkCharLit(\\n)/L tkCharLit(A)/L")): failures += 1
    if not check(string("comment"), string("a # nope\nb\n"), string("tkSymbol(a) tkSymbol(b)@0")): failures += 1
    if not check(string("docComment"), string("## hi\n## there\nb\n"), string("tkComment(hi\\nthere) tkSymbol(b)@0")): failures += 1
    if not check(string("nestedComment"), string("a #[ x #[ y ]# z ]# b\n"), string("tkSymbol(a) tkSymbol(b)/L")): failures += 1
    if not check(string("indent"), string("a\n  b\n c\n"), string("tkSymbol(a) tkSymbol(b)@2 tkSymbol(c)@1")): failures += 1
    if not check(string("unaryMinus"), string("a - 1 (-1) f(-1)\n"), string("tkSymbol(a) tkOpr(-)/LT tkIntLit(1)/L (/L tkIntLit(-1) ) tkSymbol(f)/L ( tkIntLit(-1) )")): failures += 1
    if not check(string("operators"), string("a += b; c ->> d\n"), string("tkSymbol(a) tkOpr(+=)/LT tkSymbol(b)/L ; tkSymbol(c)/L tkOpr(->>)/LT tkSymbol(d)/L")): failures += 1
    if not check(string("accent"), string("`+`\n"), string("` tkOpr(+) `")): failures += 1
    if not check(string("unicodeOpr"), utf8("a ∙ b\n"), utf8("tkSymbol(a) tkOpr(∙)/LT tkSymbol(b)/L")): failures += 1
    if not check(string("underscore"), string("_ = 3\n"), string("tkSymbol(_) =(=)/LT tkIntLit(3)/L")): failures += 1
    if failures == 0: echo("all lexer cases ok")
    else: quit(string("failures: ") + str(failures))
