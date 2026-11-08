# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/nifler2/tests/minirt.nim
# ///
## Runtime the generated parsers are written against: a token stream that
## carries indentation, and an output buffer that supports inserting an
## opening token at a saved position (`wrap`), which is what lets the
## generator left-factor freely and still build the tree the unfactored
## grammar describes.
##
## This is the miniature version used by `tmini`: a `seq` of open/close/leaf
## records instead of a NIF buffer, and its own three-screen lexer, so the
## generated parser can be tested without the Nim grammar's dependencies. The
## real one is `src/nifler2/parserrt.nim`.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import strutils, syncio
from ...models.nifler_tags import NiflerKind

from ...models import nifler_tags
export(nifler_tags)


class TokKind(NStrEnum):
    tkEof = "[EOF]"
    tkSymbol = "tkSymbol"
    tkIntLit = "tkIntLit"
    tkIf = "if"
    tkWhile = "while"
    tkColon = ":"
    tkEquals = "="
    tkSemiColon = ";"
    tkComma = ","
    tkDot = "."
    tkParLe = "("
    tkParRi = ")"
    tkBracketLe = "["
    tkBracketRi = "]"
    tkOpr = "tkOpr"


class IndClass(NIntEnum):
    icNoInd = auto()
    icLt = auto()
    icEq = auto()
    icGt = auto()


class Mark(Object):  # `src/nifler2/parserrt.nim` also carries the line info
    pos: nint
    info: nint  # this runtime has no positions; the field keeps
                # the generated `mark.info` references compiling

    def discardUnused(m: Mark):
        pass


class Token(Object):
    kind: TokKind
    s: string
    indent: int32  # column when first on its line, else -1
    spaceBefore: bool  # whitespace immediately before it
    line: int32
    col: int32


class _BufKind(NIntEnum):

    bOpen = auto()

    bClose = auto()

    bLeaf = auto()


class _BufTok(Object):
    _kind: _BufKind
    _text: string


class Parser(Object):
    toks: seq[Token]
    pos: nint
    currInd: int32
    indStack: seq[int32]
    buf: seq[_BufTok]
    errors: seq[string]

    def tok(p: Parser) -> Token:
        return p.toks[p.pos]

    def error(p: mut @ Parser, msg: string):
        with let:
            t = p.tok()
        p.errors.add(string("(") + str(t.line) + string(",") + str(t.col) + string(") ") + msg + string(", got '") + (t.s if t.s.len > 0 else str(t.kind)) + string("'"))

    def getTok(p: mut @ Parser):
        if p.pos < p.toks.high: p.pos += 1

    def ruleError(p: mut @ Parser, rule: string, misplaced: bool):
        p.error((string("invalid indentation in ") if misplaced else string("expected ")) + rule)

    def indentError(p: mut @ Parser):
        p.error(string("invalid indentation"))

    def indClass(p: Parser) -> IndClass:
        with let:
            ind = p.tok().indent
        if ind < 0: return IndClass.icNoInd
        elif ind < p.currInd: return IndClass.icLt
        elif ind == p.currInd: return IndClass.icEq
        else: return IndClass.icGt

    def afterOperator(p: mut @ Parser):
        if p.indClass() == IndClass.icLt: p.indentError()

    def checkInd(p: mut @ Parser, allowed: Tset[IndClass]):
        if p.indClass() not in allowed:
            with var:
                shown = string("")
            for c in inrange(low(IndClass), high(IndClass)):
                if c in allowed:
                    if shown.len > 0: shown.add(string(", "))
                    shown.add(str(c))
            p.error(string("invalid indentation (") + str(p.indClass()) + string(" not in {") + shown + string("})"))

    def pushInd(p: mut @ Parser):
        p.checkInd(Tset[IndClass](IndClass.icGt))
        p.indStack.add(p.currInd)
        p.currInd = p.tok().indent

    def popInd(p: mut @ Parser):
        p.currInd = p.indStack.pop()

    def expect(p: mut @ Parser, k: TokKind):
        if p.tok().kind == k: p.getTok()
        else: p.error(string("expected '") + str(k) + string("'"))

    def mark(p: Parser) -> Mark:
        return Mark(pos=p.buf.len)

    def noSpaceBefore(p: Parser) -> bool:
        ## `f(x)` is a call, `f (x)` a command -- the same rule Nim uses.
        return not p.tok().spaceBefore

    def getPrecedence(p: Parser) -> nint:
        ## Precedence from the operator's spelling, as Nim does it. Anything that is
        ## not an operator scores below every `limit`, which is what stops the loop.
        if p.tok().kind != TokKind.tkOpr: return -1000
        match p.tok().s[0]:
            case _ if p.tok().s[0] == char('$') or p.tok().s[0] == char('^'): return 10
            case _ if p.tok().s[0] == char('*') or p.tok().s[0] == char('/') or p.tok().s[0] == char('%'): return 9
            case _ if p.tok().s[0] == char('+') or p.tok().s[0] == char('-') or p.tok().s[0] == char('~') or p.tok().s[0] == char('|'): return 8
            case _ if p.tok().s[0] == char('&'): return 7
            case _ if p.tok().s[0] == char('.'): return 6
            case _ if p.tok().s[0] == char('=') or p.tok().s[0] == char('<') or p.tok().s[0] == char('>') or p.tok().s[0] == char('!'): return 5
            case _: return 4

    def isRightAssoc(p: Parser) -> bool:
        return p.tok().kind == TokKind.tkOpr and p.tok().s[0] == char('^')

    def insertLeafAt(p: mut @ Parser, m: Mark, text: string):
        _insertAt(p.buf, _BufTok(_kind=_BufKind.bLeaf, _text=text), m.pos)

    def insertOpLeafAt(p: mut @ Parser, m: Mark):
        with let:
            text = p.tok().s
        p.insertLeafAt(m, text)

    def emitLeaf(p: mut @ Parser):
        p.buf.add(_BufTok(_kind=_BufKind.bLeaf, _text=p.tok().s))
        p.getTok()

    def openTag(p: mut @ Parser, tag: string):
        p.buf.add(_BufTok(_kind=_BufKind.bOpen, _text=tag))

    def closeTag(p: mut @ Parser):
        p.buf.add(_BufTok(_kind=_BufKind.bClose, _text=string("")))

    def wrap(p: mut @ Parser, m: Mark, tag: NiflerKind):
        ## Insert the opening token at the mark and close at the end. The whole
        ## point of the design: the tag is decided after the fact.
        _insertAt(p.buf, _BufTok(_kind=_BufKind.bOpen, _text=str(tag)), m.pos)
        p.buf.add(_BufTok(_kind=_BufKind.bClose, _text=string("")))

    def wrapAt(p: mut @ Parser, m: Mark, tag: NiflerKind, info: nint):
        ## Positions are not modelled here, so this is `wrap`.
        p.wrap(m, tag)

    def info(p: Parser) -> nint:
        """{.inline.}"""
        return 0

    def render(p: Parser) -> string:
        result = string("")
        with var:
            needSpace = False
        for t in p.buf:
            match t._kind:
                case _BufKind.bOpen:
                    if needSpace: result.add(char(' '))
                    result.add(char('('))
                    result.add(t._text)
                    needSpace = True
                case _BufKind.bClose:
                    result.add(char(')'))
                    needSpace = True
                case _BufKind.bLeaf:
                    if needSpace: result.add(char(' '))
                    result.add(t._text)
                    needSpace = True
        return result

# --------------------------------------------------------------- lexing


with const:
    _OpChars = Tset[char](char('+'), char('-'), char('*'), char('/'), char('<'), char('>'), char('='), char('^'), char('&'), char('%'), char('!'), char('~'), char('|'))


def lex(src: string) -> seq[Token]:
    result = seq[Token]([])
    with var:
        i = nint(0)
        line = i32(1)
        lineStart = 0
        atLineStart = True
        sawSpace = False
    while i < src.len:
        with let:
            c = src[i]
        if c == char('\n'):
            line += 1
            i += 1
            lineStart = copy(i)
            atLineStart = True
            sawSpace = True
            continue
        if c in Tset[char](char(' '), char('\t'), char('\r')):
            i += 1
            sawSpace = True
            continue
        if c == char('#'):
            while i < src.len and src[i] != char('\n'): i += 1
            continue
        with let:
            col = int32(i - lineStart)
        with var:
            t = Token(indent=(col if atLineStart else i32(-1)), spaceBefore=sawSpace, line=line, col=col)
        atLineStart = False
        sawSpace = False
        if c in Tset[char](inrange(char('a'), char('z')), inrange(char('A'), char('Z')), char('_')):
            with let:
                start = copy(i)
            while i < src.len and src[i] in Tset[char](inrange(char('a'), char('z')), inrange(char('A'), char('Z')), inrange(char('0'), char('9')), char('_')): i += 1
            t.s = src.substr(start, i - 1)
            match t.s:
                case "if": t.kind = TokKind.tkIf
                case "while": t.kind = TokKind.tkWhile
                case _: t.kind = TokKind.tkSymbol
        elif c in Tset[char](inrange(char('0'), char('9'))):
            with let:
                start = copy(i)
            while i < src.len and src[i] in Tset[char](inrange(char('0'), char('9'))): i += 1
            t.s = src.substr(start, i - 1)
            t.kind = TokKind.tkIntLit
        elif c in _OpChars:
            with let:
                start = copy(i)
            while i < src.len and src[i] in _OpChars: i += 1
            t.s = src.substr(start, i - 1)
            t.kind = TokKind.tkEquals if t.s == "=" else TokKind.tkOpr
        else:
            t.s = str(c)
            i += 1
            match c:
                case _ if c == char(':'): t.kind = TokKind.tkColon
                case _ if c == char(';'): t.kind = TokKind.tkSemiColon
                case _ if c == char(','): t.kind = TokKind.tkComma
                case _ if c == char('.'): t.kind = TokKind.tkDot
                case _ if c == char('('): t.kind = TokKind.tkParLe
                case _ if c == char(')'): t.kind = TokKind.tkParRi
                case _ if c == char('['): t.kind = TokKind.tkBracketLe
                case _ if c == char(']'): t.kind = TokKind.tkBracketRi
                case _: t.kind = TokKind.tkEof
        result.add(t)
    result.add(Token(kind=TokKind.tkEof, s=string(""), indent=0, line=line, col=0))
    return result


def openParser(src: string) -> Parser:
    return Parser(toks=lex(src), pos=0, currInd=0, indStack=seq[int32]([]), buf=seq[_BufTok]([]), errors=seq[string]([]))

# --------------------------------------------------------------- primitives

# ---- what the generated code needs for `binary(...)` and `&predicates`


def _insertAt(buf: mut @ seq[_BufTok], t: _BufTok, pos: nint):
    buf.add(t)
    with var:
        i = nint(buf.len - 1)
    while i > pos:
        swap(buf[i], buf[i - 1])
        i -= 1
