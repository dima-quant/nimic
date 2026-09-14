"""
ncompiler/lexer_impl.py — Tokenization procedures
Converted from compiler/lexer.nim (rawGetTok and helpers)
"""
from __future__ import annotations
from ncompiler.lexer import *
from ncompiler.nimlexbase import EndOfFile, handleCRLF, getColNumber
from ncompiler.idents import Hash
from ncompiler.lineinfos import TMsgKind
from ncompiler.options import TGlobalOption

CR = '\r'
LF = '\n'
Digits = set('0123456789')
HexDigits = set('0123456789abcdefABCDEF')
OctDigits = set('01234567')
BinDigits = set('01')


def _matchUnderscoreChars(L: Lexer, tok: Token, chars: set) -> int:
    """Scan digits with optional underscores. Returns length scanned."""
    pos = L.bufpos
    start = pos
    while True:
        c = L.buf[pos]
        if c in chars:
            tok.literal += c
            pos += 1
        elif c == '_':
            if pos + 1 < len(L.buf) and L.buf[pos + 1] in chars:
                tok.literal += '_'
                pos += 1
            else:
                break
        else:
            break
    L.bufpos = pos
    return pos - start


def getNumber(L: Lexer, tok: Token):
    pos = L.bufpos
    startPos = pos
    isNeg = False
    if L.buf[pos] == '-':
        isNeg = True
        pos += 1
    tok.tokType = TokType.tkIntLit
    tok.literal = ""
    tok.base = 10
    # Collect the number into tok.literal
    numStart = pos
    if L.buf[pos] == '0':
        pos += 1
        nxt = L.buf[pos].lower() if pos < len(L.buf) else '\0'
        if nxt == 'x':
            tok.base = 16
            pos += 1
            L.bufpos = pos
            tok.literal = "0x"
            _matchUnderscoreChars(L, tok, HexDigits)
            pos = L.bufpos
        elif nxt == 'o':
            tok.base = 8
            pos += 1
            L.bufpos = pos
            tok.literal = "0o"
            _matchUnderscoreChars(L, tok, OctDigits)
            pos = L.bufpos
        elif nxt == 'b':
            tok.base = 2
            pos += 1
            L.bufpos = pos
            tok.literal = "0b"
            _matchUnderscoreChars(L, tok, BinDigits)
            pos = L.bufpos
        else:
            tok.literal = "0"
            L.bufpos = pos
            _matchUnderscoreChars(L, tok, Digits)
            pos = L.bufpos
    else:
        L.bufpos = pos
        _matchUnderscoreChars(L, tok, Digits)
        pos = L.bufpos

    # Fractional part
    if pos < len(L.buf) and L.buf[pos] == '.':
        nxt = L.buf[pos+1] if pos+1 < len(L.buf) else '\0'
        if nxt in Digits:
            tok.tokType = TokType.tkFloatLit
            tok.literal += '.'
            pos += 1
            L.bufpos = pos
            _matchUnderscoreChars(L, tok, Digits)
            pos = L.bufpos

    # Exponent
    if pos < len(L.buf) and L.buf[pos].lower() == 'e':
        tok.tokType = TokType.tkFloatLit
        tok.literal += L.buf[pos]
        pos += 1
        if pos < len(L.buf) and L.buf[pos] in ('+', '-'):
            tok.literal += L.buf[pos]
            pos += 1
        L.bufpos = pos
        _matchUnderscoreChars(L, tok, Digits)
        pos = L.bufpos

    # Type suffix
    if pos < len(L.buf) and L.buf[pos] == '\'':
        pos += 1
        suffix = ""
        while pos < len(L.buf) and L.buf[pos] in 'iIuUfFdD0123456789':
            suffix += L.buf[pos]
            pos += 1
        sl = suffix.lower()
        if sl == "i8": tok.tokType = TokType.tkInt8Lit
        elif sl == "i16": tok.tokType = TokType.tkInt16Lit
        elif sl == "i32": tok.tokType = TokType.tkInt32Lit
        elif sl == "i64": tok.tokType = TokType.tkInt64Lit
        elif sl == "u": tok.tokType = TokType.tkUIntLit
        elif sl == "u8": tok.tokType = TokType.tkUInt8Lit
        elif sl == "u16": tok.tokType = TokType.tkUInt16Lit
        elif sl == "u32": tok.tokType = TokType.tkUInt32Lit
        elif sl == "u64": tok.tokType = TokType.tkUInt64Lit
        elif sl == "f" or sl == "f32": tok.tokType = TokType.tkFloat32Lit
        elif sl == "d" or sl == "f64": tok.tokType = TokType.tkFloat64Lit
        elif sl == "f128": tok.tokType = TokType.tkFloat128Lit

    L.bufpos = pos
    if isNeg:
        tok.literal = "-" + tok.literal
    # Parse the numeric value
    lit = tok.literal.replace("_", "")
    try:
        if tok.tokType.value >= TokType.tkFloatLit.value:
            tok.fNumber = float(lit)
        else:
            tok.iNumber = int(lit, 0)
    except ValueError:
        lexMessage(L, TMsgKind.errGenerated, "invalid number: " + tok.literal)


def getEscapedChar(L: Lexer, tok: Token):
    pos = L.bufpos
    assert L.buf[pos] == '\\'
    pos += 1
    c = L.buf[pos]
    if c == 'n':
        tok.literal += '\n'; pos += 1
    elif c == 'r':
        tok.literal += '\r'; pos += 1
    elif c == 'c':
        tok.literal += '\r'; pos += 1
    elif c == 'l':
        tok.literal += '\n'; pos += 1
    elif c == 'f':
        tok.literal += '\f'; pos += 1
    elif c == 'e':
        tok.literal += '\x1b'; pos += 1
    elif c == 'a':
        tok.literal += '\a'; pos += 1
    elif c == 'b':
        tok.literal += '\b'; pos += 1
    elif c == 'v':
        tok.literal += '\v'; pos += 1
    elif c == 't':
        tok.literal += '\t'; pos += 1
    elif c == '\\':
        tok.literal += '\\'; pos += 1
    elif c == '"':
        tok.literal += '"'; pos += 1
    elif c == '\'':
        tok.literal += '\''; pos += 1
    elif c == 'x':
        pos += 1
        h = ""
        for _ in range(2):
            if pos < len(L.buf) and L.buf[pos] in HexDigits:
                h += L.buf[pos]; pos += 1
        if h:
            tok.literal += chr(int(h, 16))
    elif c in Digits:
        h = ""
        for _ in range(3):
            if pos < len(L.buf) and L.buf[pos] in Digits:
                h += L.buf[pos]; pos += 1
        if h:
            tok.literal += chr(int(h))
    elif c == 'u':
        pos += 1
        if pos < len(L.buf) and L.buf[pos] == '{':
            pos += 1
            h = ""
            while pos < len(L.buf) and L.buf[pos] in HexDigits:
                h += L.buf[pos]; pos += 1
            if pos < len(L.buf) and L.buf[pos] == '}':
                pos += 1
            if h:
                tok.literal += chr(int(h, 16))
        else:
            h = ""
            for _ in range(4):
                if pos < len(L.buf) and L.buf[pos] in HexDigits:
                    h += L.buf[pos]; pos += 1
            if h:
                tok.literal += chr(int(h, 16))
    else:
        lexMessage(L, TMsgKind.errGenerated, "invalid character escape: \\" + c)
    L.bufpos = pos


def getString(L: Lexer, tok: Token, mode: str = "normal"):
    """Lex a string literal. mode: 'normal', 'raw', 'generalized'"""
    pos = L.bufpos
    tok.tokType = TokType.tkStrLit
    tok.literal = ""
    assert L.buf[pos] == '"'
    pos += 1
    # Triple-quoted?
    if pos + 1 < len(L.buf) and L.buf[pos] == '"' and L.buf[pos+1] == '"':
        tok.tokType = TokType.tkTripleStrLit
        pos += 2
        while True:
            c = L.buf[pos]
            if c == EndOfFile:
                lexMessage(L, TMsgKind.errGenerated, "closing \"\"\" expected")
                break
            if c == '"' and pos+2 < len(L.buf) and L.buf[pos+1] == '"' and L.buf[pos+2] == '"':
                pos += 3
                # skip extra "
                while pos < len(L.buf) and L.buf[pos] == '"':
                    tok.literal += '"'; pos += 1
                break
            tok.literal += c
            pos += 1
    else:
        if mode == "raw":
            tok.tokType = TokType.tkRStrLit
        while True:
            c = L.buf[pos]
            if c == '"':
                if mode != "normal" and pos+1 < len(L.buf) and L.buf[pos+1] == '"':
                    tok.literal += '"'; pos += 2
                else:
                    pos += 1; break
            elif c in (CR, LF, EndOfFile):
                lexMessage(L, TMsgKind.errGenerated, 'closing " expected')
                break
            elif c == '\\' and mode == "normal":
                L.bufpos = pos
                getEscapedChar(L, tok)
                pos = L.bufpos
            else:
                tok.literal += c; pos += 1
    L.bufpos = pos


def getCharacter(L: Lexer, tok: Token):
    pos = L.bufpos
    assert L.buf[pos] == '\''
    pos += 1
    tok.literal = ""
    c = L.buf[pos]
    if c == '\\':
        L.bufpos = pos
        getEscapedChar(L, tok)
        pos = L.bufpos
    elif c in ('\0', '\r', '\n'):
        lexMessage(L, TMsgKind.errGenerated, "invalid character literal")
        tok.literal = str(c)
    else:
        tok.literal = c; pos += 1
    if pos < len(L.buf) and L.buf[pos] == '\'':
        pos += 1
    else:
        lexMessage(L, TMsgKind.errGenerated, "missing closing ' for character literal")
    L.bufpos = pos


def _wordToTokType(w: TSpecialWord) -> TokType:
    """Map a TSpecialWord to the corresponding TokType."""
    # Keywords: wAddr..wYield map to tkAddr..tkYield
    if w.value >= TSpecialWord.wAddr.value and w.value <= TSpecialWord.wYield.value:
        return TokType(w.value - TSpecialWord.wAddr.value + TokType.tkAddr.value)
    # Operators: wColon..wDotDot map to tkColon..tkDotDot
    if w.value >= TSpecialWord.wColon.value and w.value <= TSpecialWord.wDotDot.value:
        return TokType(w.value - TSpecialWord.wColon.value + TokType.tkColon.value)
    return TokType.tkSymbol


def getSymbol(L: Lexer, tok: Token):
    pos = L.bufpos
    while True:
        c = L.buf[pos]
        if 'a' <= c <= 'z' or '0' <= c <= '9':
            pos += 1
        elif 'A' <= c <= 'Z':
            pos += 1
        elif c == '_':
            if pos + 1 < len(L.buf) and L.buf[pos+1] in SymChars:
                pos += 1
            else:
                break
        elif ord(c) >= 0x80:
            pos += 1
        else:
            break
    s = L.buf[L.bufpos:pos]
    tok.ident = L.cache.getIdent(s)
    from ncompiler.wordrecg import findStr
    w = findStr(tok.ident.s)
    if w == TSpecialWord.wInvalid:
        tok.tokType = TokType.tkSymbol
    else:
        tok.tokType = _wordToTokType(w)
    L.bufpos = pos


def endOperator(L: Lexer, tok: Token, pos: int, h: Hash):
    s = L.buf[L.bufpos:pos]
    tok.ident = L.cache.getIdent(s)
    from ncompiler.wordrecg import findStr
    w = findStr(tok.ident.s)
    if w.value >= TSpecialWord.wColon.value and w.value <= TSpecialWord.wDotDot.value:
        tok.tokType = TokType(w.value - TSpecialWord.wColon.value + TokType.tkColon.value)
    else:
        tok.tokType = TokType.tkOpr
    L.bufpos = pos


def getOperator(L: Lexer, tok: Token):
    pos = L.bufpos
    h: Hash = 0
    while True:
        c = L.buf[pos]
        if c in OpChars:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
            pos += 1
        else:
            break
    endOperator(L, tok, pos, h)
    # Check trailing spacing
    tok.spacing -= {TTokenSpacing.tsTrailing, TTokenSpacing.tsEof}
    trailing = False
    while pos < len(L.buf) and L.buf[pos] == ' ':
        pos += 1; trailing = True
    if pos >= len(L.buf) or L.buf[pos] in (CR, LF, EndOfFile):
        tok.spacing.add(TTokenSpacing.tsEof)
    elif trailing:
        tok.spacing.add(TTokenSpacing.tsTrailing)


def skipMultiLineComment(L: Lexer, tok: Token, pos: int, isDoc: bool) -> int:
    nesting = 0
    while True:
        c = L.buf[pos]
        if c == '#':
            if isDoc:
                if pos+2 < len(L.buf) and L.buf[pos+1] == '#' and L.buf[pos+2] == '[':
                    nesting += 1
                tok.literal += '#'
            elif pos+1 < len(L.buf) and L.buf[pos+1] == '[':
                nesting += 1
            pos += 1
        elif c == ']':
            if isDoc:
                if pos+2 < len(L.buf) and L.buf[pos+1] == '#' and L.buf[pos+2] == '#':
                    if nesting == 0:
                        pos += 3; break
                    nesting -= 1
                tok.literal += ']'
            elif pos+1 < len(L.buf) and L.buf[pos+1] == '#':
                if nesting == 0:
                    pos += 2; break
                nesting -= 1
            pos += 1
        elif c in (CR, LF):
            pos = handleCRLF(L, pos)
            if isDoc: tok.literal += '\n'
        elif c == EndOfFile:
            lexMessagePos(L, TMsgKind.errGenerated, pos, "end of multiline comment expected")
            break
        else:
            if isDoc: tok.literal += c
            pos += 1
    L.bufpos = pos
    return pos


def scanComment(L: Lexer, tok: Token):
    pos = L.bufpos
    tok.tokType = TokType.tkComment
    assert L.buf[pos+1] == '#'
    if pos+2 < len(L.buf) and L.buf[pos+2] == '[':
        skipMultiLineComment(L, tok, pos+3, True)
        return
    pos += 2
    tok.literal = ""
    while True:
        while pos < len(L.buf) and L.buf[pos] not in (CR, LF, EndOfFile):
            tok.literal += L.buf[pos]; pos += 1
        pos = handleCRLF(L, pos)
        indent = 0
        while pos < len(L.buf) and L.buf[pos] == ' ':
            pos += 1; indent += 1
        if pos+1 < len(L.buf) and L.buf[pos] == '#' and L.buf[pos+1] == '#':
            tok.literal += '\n'
            pos += 2
        else:
            if pos < len(L.buf) and L.buf[pos] > ' ':
                L.indentAhead = indent
            break
    L.bufpos = pos


def skip(L: Lexer, tok: Token):
    pos = L.bufpos
    tok.spacing -= {TTokenSpacing.tsLeading}
    while True:
        c = L.buf[pos]
        if c == ' ':
            pos += 1
            tok.spacing.add(TTokenSpacing.tsLeading)
        elif c == '\t':
            lexMessagePos(L, TMsgKind.errGenerated, pos, "tabs are not allowed, use spaces instead")
            pos += 1
        elif c in (CR, LF):
            pos = handleCRLF(L, pos)
            indent = 0
            while True:
                if pos < len(L.buf) and L.buf[pos] == ' ':
                    pos += 1; indent += 1
                elif pos+1 < len(L.buf) and L.buf[pos] == '#' and L.buf[pos+1] == '[':
                    skipMultiLineComment(L, tok, pos+2, False)
                    pos = L.bufpos
                else:
                    break
            tok.spacing -= {TTokenSpacing.tsLeading}
            if pos < len(L.buf) and L.buf[pos] > ' ' and (L.buf[pos] != '#' or (pos+1 < len(L.buf) and L.buf[pos+1] == '#')):
                tok.indent = indent
                L.currLineIndent = indent
                break
        elif c == '#':
            if pos+1 < len(L.buf) and L.buf[pos+1] == '#':
                break  # doc comment
            if pos+1 < len(L.buf) and L.buf[pos+1] == '[':
                skipMultiLineComment(L, tok, pos+2, False)
                pos = L.bufpos
            else:
                while pos < len(L.buf) and L.buf[pos] not in (CR, LF, EndOfFile):
                    pos += 1
        else:
            break
    L.bufpos = pos


def rawGetTok(L: Lexer, tok: Token):
    reset(tok)
    if L.indentAhead >= 0:
        tok.indent = L.indentAhead
        L.currLineIndent = L.indentAhead
        L.indentAhead = -1
    else:
        tok.indent = -1
    skip(L, tok)
    c = L.buf[L.bufpos]
    tok.line = L.lineNumber
    tok.col = getColNumber(L, L.bufpos)

    if c in SymStartChars and c not in ('r', 'R'):
        getSymbol(L, tok)
    elif c == '#':
        scanComment(L, tok)
    elif c == '*':
        if L.bufpos+1 < len(L.buf) and L.buf[L.bufpos+1] == ':' and (L.bufpos+2 >= len(L.buf) or L.buf[L.bufpos+2] not in OpChars):
            h = (0 * 31 + ord('*')) & 0xFFFFFFFF
            endOperator(L, tok, L.bufpos+1, h)
        else:
            getOperator(L, tok)
    elif c == ',':
        tok.tokType = TokType.tkComma; L.bufpos += 1
    elif c in ('r', 'R'):
        if L.bufpos+1 < len(L.buf) and L.buf[L.bufpos+1] == '"':
            L.bufpos += 1
            getString(L, tok, "raw")
        else:
            getSymbol(L, tok)
    elif c == '(':
        L.bufpos += 1
        if L.bufpos < len(L.buf) and L.buf[L.bufpos] == '.' and (L.bufpos+1 >= len(L.buf) or L.buf[L.bufpos+1] != '.'):
            tok.tokType = TokType.tkParDotLe; L.bufpos += 1
        else:
            tok.tokType = TokType.tkParLe
    elif c == ')':
        tok.tokType = TokType.tkParRi; L.bufpos += 1
    elif c == '[':
        L.bufpos += 1
        if L.bufpos < len(L.buf) and L.buf[L.bufpos] == '.' and (L.bufpos+1 >= len(L.buf) or L.buf[L.bufpos+1] != '.'):
            tok.tokType = TokType.tkBracketDotLe; L.bufpos += 1
        elif L.bufpos < len(L.buf) and L.buf[L.bufpos] == ':':
            tok.tokType = TokType.tkBracketLeColon; L.bufpos += 1
        else:
            tok.tokType = TokType.tkBracketLe
    elif c == ']':
        tok.tokType = TokType.tkBracketRi; L.bufpos += 1
    elif c == '.':
        if L.bufpos+1 < len(L.buf) and L.buf[L.bufpos+1] == ']':
            tok.tokType = TokType.tkBracketDotRi; L.bufpos += 2
        elif L.bufpos+1 < len(L.buf) and L.buf[L.bufpos+1] == '}':
            tok.tokType = TokType.tkCurlyDotRi; L.bufpos += 2
        elif L.bufpos+1 < len(L.buf) and L.buf[L.bufpos+1] == ')':
            tok.tokType = TokType.tkParDotRi; L.bufpos += 2
        else:
            getOperator(L, tok)
    elif c == '{':
        L.bufpos += 1
        if L.bufpos < len(L.buf) and L.buf[L.bufpos] == '.' and (L.bufpos+1 >= len(L.buf) or L.buf[L.bufpos+1] != '.'):
            tok.tokType = TokType.tkCurlyDotLe; L.bufpos += 1
        else:
            tok.tokType = TokType.tkCurlyLe
    elif c == '}':
        tok.tokType = TokType.tkCurlyRi; L.bufpos += 1
    elif c == ';':
        tok.tokType = TokType.tkSemiColon; L.bufpos += 1
    elif c == '`':
        tok.tokType = TokType.tkAccent; L.bufpos += 1
    elif c == '_':
        L.bufpos += 1
        if L.bufpos < len(L.buf) and L.buf[L.bufpos] not in SymChars and L.buf[L.bufpos] != '_':
            tok.tokType = TokType.tkSymbol
            tok.ident = L.cache.getIdent("_")
        else:
            tok.literal = c
            tok.tokType = TokType.tkInvalid
            lexMessage(L, TMsgKind.errGenerated, "invalid token: " + c)
    elif c == '"':
        mode = "generalized" if L.bufpos > 0 and L.buf[L.bufpos-1] in SymChars else "normal"
        getString(L, tok, mode)
        if mode == "generalized":
            tok.tokType = TokType(tok.tokType.value + 2)
    elif c == '\'':
        tok.tokType = TokType.tkCharLit
        getCharacter(L, tok)
        tok.tokType = TokType.tkCharLit
    elif '0' <= c <= '9':
        getNumber(L, tok)
    elif c == '-':
        if L.bufpos+1 < len(L.buf) and '0' <= L.buf[L.bufpos+1] <= '9' and (L.bufpos == 0 or L.buf[L.bufpos-1] in UnaryMinusWhitelist):
            getNumber(L, tok)
        else:
            getOperator(L, tok)
    elif c in OpChars:
        getOperator(L, tok)
    elif c == EndOfFile:
        tok.tokType = TokType.tkEof
        tok.indent = 0
    else:
        tok.literal = c
        tok.tokType = TokType.tkInvalid
        lexMessage(L, TMsgKind.errGenerated, "invalid token: " + c)
        L.bufpos += 1


def getPrecedence(tok: Token) -> int:
    MulPred, PlusPred = 9, 8
    tt = tok.tokType
    if tt == TokType.tkOpr:
        s = tok.ident.s
        if len(s) > 1 and s[-1] == '>' and s[-2] in ('-', '~', '='):
            return 0
        isAsgn = s[-1] == '='
        r = s[0]
        if r in ('$', '^'): return 1 if isAsgn else 10
        if r in ('*', '%', '/', '\\'): return 1 if isAsgn else MulPred
        if r == '~': return 8
        if r in ('+', '-', '|'): return 1 if isAsgn else PlusPred
        if r == '&': return 1 if isAsgn else 7
        if r in ('=', '<', '>', '!'): return 5
        if r == '.': return 1 if isAsgn else 6
        if r == '?': return 2
        return 1 if isAsgn else 2
    if tt in (TokType.tkDiv, TokType.tkMod, TokType.tkShl, TokType.tkShr):
        return 9
    if tt == TokType.tkDotDot: return 6
    if tt in (TokType.tkIn, TokType.tkNotin, TokType.tkIs, TokType.tkIsnot, TokType.tkOf, TokType.tkAs, TokType.tkFrom):
        return 5
    if tt == TokType.tkAnd: return 4
    if tt in (TokType.tkOr, TokType.tkXor, TokType.tkPtr, TokType.tkRef):
        return 3
    return -10
