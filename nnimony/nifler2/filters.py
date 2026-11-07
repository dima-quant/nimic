# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/nifler2/filters.nim
# ///
#
#
#           Nifler2: Nim to NIF
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## Source code filters: a first line `#? stdtmpl | standard` turns the rest of
## the file into Nim code before it is parsed. Ported from Nim's
## `syntaxes.nim` (the `#?` pipe), `filters.nim` (`strip`, `replace`) and
## `filter_tmpl.nim` (`stdtmpl`), text in and text out, so that the parser
## and everything after it never know a filter was there.
##
## The pipe itself is Nim code and is parsed by nifler2's own parser; the
## filters read their arguments from that tree.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import cmpIgnoreStyle, repeat, spaces, startsWith
from nimic.std import syncio
from . import nimgrammar
from .nimgrammar import (
    add, ch, charLit, childCursor, Cursor, endRead, globalTags, inc, intVal, NifKind, openParser, pModule,
    pool, resolvedTagId, skip, strVal)
from nimic.std import strutils
replace = overloads(strutils.replace, nimgrammar.replace)


class _LineReader(Object):
    ## `llStreamReadLine`. The file stream and the string stream a filter
    ## writes do not agree on a trailing empty line: the file's `readLine`
    ## returns it, the string stream's loop does not.
    _s: string
    _rd: nint
    _fromFile: bool

    def _readLine(r: mut @ _LineReader, line: mut @ string) -> bool:
        line.setLen(0)
        if r._fromFile:
            if r._rd >= r._s.len: return False
            while r._rd < r._s.len and r._s[r._rd] != ch('\n'):
                line.add(r._s[r._rd])
                r._rd += 1
            if r._rd < r._s.len: r._rd += 1
            if line.len > 0 and line[line.len - 1] == ch('\r'): line.setLen(line.len - 1)
            result = True
        else:
            while r._rd < r._s.len:
                with let:
                    c = r._s[r._rd]
                if c == ch('\r'):
                    r._rd += 1
                    if r._rd < r._s.len and r._s[r._rd] == ch('\n'): r._rd += 1
                    break
                elif c == ch('\n'):
                    r._rd += 1
                    break
                else:
                    line.add(c)
                    r._rd += 1
            result = line.len > 0 or r._rd < r._s.len
        return result


class _FilterContext(Object):
    _filename: string
    failed: bool

    def _filterError(ctx: mut @ _FilterContext, line: nint, col: nint, msg: string):
        ## `localError`: reported, and the parse goes on -- nifler exits with an
        ## error at the end, but its first line is this one.
        echo(ctx._filename, "(", line, ", ", col + 1, ") Error: ", msg)
        ctx.failed = True

# ------------------------------------------------------------ the pipe tree


def _tag(c: Cursor) -> string:
    """{.inline.}"""
    return c.tags().tags[resolvedTagId(c)]


def _render(c: Cursor) -> string:
    ## Enough of `renderTree` for the arguments a filter can be given.
    match c.kind():
        case NifKind.Ident: result = strVal(c)
        case NifKind.IntLit: result = str(intVal(c))
        case NifKind.StrLit: result = string("\"") + strVal(c) + string("\"")
        case NifKind.CharLit:
            result = string("'")
            result.add(charLit(c))
            result.add(string("'"))
        case NifKind.TagLit:
            with var:
                k = childCursor(c)
            match _tag(c):
                case "vv":
                    result = _render(k)
                    skip(k)
                    result.add(string(" = ") + _render(k))
                case "suf":
                    result = _render(k)
                case "call" | "cmd":
                    result = _render(k)
                    skip(k)
                    result.add(string("("))
                    with var:
                        first = True
                    while k.hasMore():
                        if not first: result.add(string(", "))
                        first = False
                        result.add(_render(k))
                        skip(k)
                    result.add(string(")"))
                case "infix":
                    with let:
                        op = _render(k)
                    skip(k)
                    result = _render(k)
                    skip(k)
                    result.add(string(" ") + op + string(" ") + _render(k))
                case _:
                    result = _tag(c)
        case _:
            result = string("")
    return result


def _invalidPragma(ctx: mut @ _FilterContext, n: Cursor):
    with let:
        info = n.rawLineInfo()
    ctx._filterError(info.line, info.col, string("'") + _render(n) + string("' not allowed here"))


def _getArg(n: Cursor, name: string, pos: nint, found: mut @ Cursor) -> bool:
    ## The argument called `name`, or else the `pos`-th one (the callee is 0).
    if n.kind() != NifKind.TagLit: return False
    with var:
        k = childCursor(n)
    skip(k)
    with var:
        i = nint(1)
    while k.hasMore():
        if k.kind() == NifKind.TagLit and _tag(k) == "vv":
            with let:
                key = childCursor(k)
            if key.kind() == NifKind.Ident and cmpIgnoreStyle(strVal(key), name) == 0:
                found <<= key
                skip(found)
                return True
        elif i == pos:
            found <<= k
            return True
        skip(k)
        i += 1
    return False


def _charArg(ctx: mut @ _FilterContext, n: Cursor, name: string, pos: nint, default: char) -> char:
    with var:
        x = n.copy()
    if not _getArg(n, name, pos, x): result = default.copy()
    elif x.kind() == NifKind.CharLit: result = charLit(x)
    else:
        result = ch('\x00')
        _invalidPragma(ctx, n)
    return result


def _strArg(ctx: mut @ _FilterContext, n: Cursor, name: string, pos: nint, default: string) -> string:
    with var:
        x = n.copy()
    if not _getArg(n, name, pos, x): return default.copy()
    if x.kind() == NifKind.TagLit and _tag(x) == "suf":
        x = childCursor(x)  # a raw or triple-quoted string
    if x.kind() == NifKind.StrLit: result = strVal(x)
    else:
        result = string("")
        _invalidPragma(ctx, n)
    return result


def _boolArg(ctx: mut @ _FilterContext, n: Cursor, name: string, pos: nint, default: bool) -> bool:
    with var:
        x = n.copy()
    if not _getArg(n, name, pos, x): result = default
    elif x.kind() == NifKind.Ident and cmpIgnoreStyle(strVal(x), string("true")) == 0: result = True
    elif x.kind() == NifKind.Ident and cmpIgnoreStyle(strVal(x), string("false")) == 0: result = False
    else:
        result = False
        _invalidPragma(ctx, n)
    return result

# ------------------------------------------------------------ strip, replace


with const:
    _Whitespace = Tset[char](ch(' '), ch('\t'), ch('\x0b'), ch('\r'), ch('\n'), ch('\x0c'))


def _strip(s: string, leading: bool, trailing: bool) -> string:
    with var:
        a = nint(0)
        b = nint(s.len - 1)
    if leading:
        while a <= b and s[a] in _Whitespace: a += 1
    if trailing:
        while b >= a and s[b] in _Whitespace: b -= 1
    result = s.substr(a, b)
    return result


def _filterStrip(ctx: mut @ _FilterContext, input: mut @ _LineReader, call: Cursor) -> string:
    with let:
        pattern = _strArg(ctx, call, string("startswith"), 1, string(""))
        leading = _boolArg(ctx, call, string("leading"), 2, True)
        trailing = _boolArg(ctx, call, string("trailing"), 3, True)
    result = string("")
    with var:
        line = string("")
    while input._readLine(line):
        with let:
            stripped = _strip(line, leading, trailing)
        if pattern.len == 0 or startsWith(stripped, pattern):
            result.add(stripped)
        else:
            result.add(line)
        result.add(ch('\n'))
    return result


def _filterReplace(ctx: mut @ _FilterContext, input: mut @ _LineReader, call: Cursor) -> string:
    with let:
        sub = _strArg(ctx, call, string("sub"), 1, string(""))
    if sub.len == 0: _invalidPragma(ctx, call)
    with let:
        by = _strArg(ctx, call, string("by"), 2, string(""))
    result = string("")
    with var:
        line = string("")
    while input._readLine(line):
        result.add((line if sub.len == 0 else replace(line, sub, by)))
        result.add(ch('\n'))
    return result

# ------------------------------------------------------------ stdtmpl


class _TmplState(NIntEnum):
    psDirective = auto()
    psTempl = auto()


class _TmplParser(Object):
    _state: _TmplState
    _line: nint
    _col: nint
    _indent: nint
    _emitPar: nint
    _x: string  ## the current input line
    _outp: string
    _subsChar: char
    _nimDirective: char
    _emit: string
    _conc: string
    _toStr: string
    _curly: nint
    _bracket: nint
    _par: nint
    _pendingExprLine: bool

    def _at(p: _TmplParser, i: nint) -> char:
        """{.inline.}"""
        ## Nim's `p.x[j]` one past the end reads the string's terminator.
        return p._x[i] if i < p._x.len else ch('\x00')

    def _scanPar(p: mut @ _TmplParser, d: nint):
        with var:
            i = copy(d)
        while i < p._x.len:
            match p._x[i]:
                case _ if p._x[i] == ch('('): p._par += 1
                case _ if p._x[i] == ch(')'): p._par -= 1
                case _ if p._x[i] == ch('['): p._bracket += 1
                case _ if p._x[i] == ch(']'): p._bracket -= 1
                case _ if p._x[i] == ch('{'): p._curly += 1
                case _ if p._x[i] == ch('}'): p._curly -= 1
                case _: pass
            i += 1

    def _withInExpr(p: _TmplParser) -> bool:
        """{.inline.}"""
        return p._par > 0 or p._bracket > 0 or p._curly > 0


with const:
    _PatternChars = Tset[char](inrange(ch('a'), ch('z')), inrange(ch('A'), ch('Z')), inrange(ch('0'), ch('9')), inrange(ch('\x80'), ch('\xff')), ch('.'), ch('_'))
    _LineContinuationOprs = Tset[char](ch('+'), ch('-'), ch('*'), ch('/'), ch('\\'), ch('<'), ch('>'), ch('^'), ch('|'), ch('%'), ch('&'), ch('$'), ch('@'), ch('~'), ch(','))


def _spacesN(n: nint) -> string:
    """{.inline.}"""
    return spaces(max(n, 0))


def _newLine(p: mut @ _TmplParser):
    p._outp.add(repeat(ch(')'), p._emitPar))
    p._emitPar = 0
    if p._line > 1: p._outp.add(string("\n"))
    if p._pendingExprLine:
        p._outp.add(_spacesN(2))
        p._pendingExprLine = False


def _hexByte(c: char) -> string:
    with const:
        HexChars = string("0123456789ABCDEF")
    result = string("")
    result.add(HexChars[ord(c) >> 4])
    result.add(HexChars[ord(c) & 15])
    return result


def _parseLine(ctx: mut @ _FilterContext, p: mut @ _TmplParser):
    with var:
        j = nint(0)
    with let:
        len = p._x.len

    while j < len and p._x[j] == ch(' '): j += 1

    if len >= 2 and p._x[0] == p._nimDirective and p._x[1] == ch('?'):
        _newLine(p)
    elif j < len and p._x[j] == p._nimDirective:
        _newLine(p)
        j += 1
        while j < len and p._x[j] == ch(' '): j += 1
        with let:
            d = copy(j)
        with var:
            keyw = string("")
        while j < len and p._x[j] in _PatternChars:
            keyw.add(p._x[j])
            j += 1

        p._scanPar(j)
        p._pendingExprLine = p._withInExpr() or (len > 0 and p._x[len - 1] in _LineContinuationOprs)
        match keyw:
            case "end":
                if p._indent >= 2:
                    p._indent -= 2
                else:
                    ctx._filterError(p._line, j, string("'end' does not close a control flow construct"))
                p._outp.add(_spacesN(p._indent))
                p._outp.add(string("#end"))
            case "if" | "when" | "try" | "while" | "for" | "block" | "case" | "proc" | "iterator" | "converter" | "macro" | "template" | "method" | "func":
                p._outp.add(_spacesN(p._indent))
                p._outp.add(substr(p._x, d))
                p._indent += 2
            case "elif" | "of" | "else" | "except" | "finally":
                p._outp.add(_spacesN(p._indent - 2))
                p._outp.add(substr(p._x, d))
            case "let" | "var" | "const" | "type":
                p._outp.add(_spacesN(p._indent))
                p._outp.add(substr(p._x, d))
                if not (p._x.contains(ch(':')) or p._x.contains(ch('='))):
                # no inline element --> treat as block:
                    p._indent += 2
            case _:
                p._outp.add(_spacesN(p._indent))
                p._outp.add(substr(p._x, d))
        p._state = _TmplState.psDirective
    else:
    # data line
        p._par = 0
        p._curly = 0
        p._bracket = 0
        j = 0
        match p._state:
            case _TmplState.psTempl:
            # next line of string literal:
                p._outp.add(p._conc)
                p._outp.add(string("\n"))
                p._outp.add(_spacesN(p._indent + 2))
                p._outp.add(string("\""))
            case _TmplState.psDirective:
                _newLine(p)
                p._outp.add(_spacesN(p._indent))
                p._outp.add(p._emit)
                p._outp.add(string("(\""))
                p._emitPar += 1
        p._state = _TmplState.psTempl
        while j < len:
            with let:
                c = p._x[j]
            if c in Tset[char](inrange(ch('\x01'), ch('\x1f')), inrange(ch('\x80'), ch('\xff'))):
                p._outp.add(string("\\x"))
                p._outp.add(_hexByte(c))
                j += 1
            elif c == ch('\\'):
                p._outp.add(string("\\\\"))
                j += 1
            elif c == ch('\''):
                p._outp.add(string("\\\'"))
                j += 1
            elif c == ch('"'):
                p._outp.add(string("\\\""))
                j += 1
            elif c == p._subsChar:
            # parse Nim expression:
                j += 1
                with let:
                    e = p._at(j)
                if e == ch('{'):
                    p._col = j
                    p._outp.add(ch('"'))
                    p._outp.add(p._conc)
                    p._outp.add(p._toStr)
                    p._outp.add(ch('('))
                    j += 1
                    with var:
                        curly = nint(0)
                    while j < len:
                        match p._x[j]:
                            case _ if p._x[j] == ch('{'):
                                j += 1
                                curly += 1
                                p._outp.add(ch('{'))
                            case _ if p._x[j] == ch('}'):
                                j += 1
                                if curly == 0: break
                                if curly > 0: curly -= 1
                                p._outp.add(ch('}'))
                            case _:
                                p._outp.add(p._x[j])
                                j += 1
                    if curly > 0:
                        ctx._filterError(p._line, p._col, string("expected closing '}'"))
                        break
                    p._outp.add(ch(')'))
                    p._outp.add(p._conc)
                    p._outp.add(ch('"'))
                elif e in Tset[char](inrange(ch('a'), ch('z')), inrange(ch('A'), ch('Z')), inrange(ch('\x80'), ch('\xff'))):
                    p._outp.add(ch('"'))
                    p._outp.add(p._conc)
                    p._outp.add(p._toStr)
                    p._outp.add(ch('('))
                    while j < len and p._x[j] in _PatternChars:
                        p._outp.add(p._x[j])
                        j += 1
                    p._outp.add(ch(')'))
                    p._outp.add(p._conc)
                    p._outp.add(ch('"'))
                elif e == p._subsChar:
                    p._outp.add(p._subsChar)
                    j += 1
                else:
                    ctx._filterError(p._line, j, string("invalid expression"))
            else:
                p._outp.add(c)
                j += 1
        p._outp.add(string("\\n\""))


def _filterTmpl(ctx: mut @ _FilterContext, input: mut @ _LineReader, call: Cursor) -> string:
    with var:
        p = _TmplParser(_subsChar=_charArg(ctx, call, string("subschar"), 1, ch('$')), _nimDirective=_charArg(ctx, call, string("metachar"), 2, ch('#')), _emit=_strArg(ctx, call, string("emit"), 3, string("result.add")), _conc=_strArg(ctx, call, string("conc"), 4, string(" & ")), _toStr=_strArg(ctx, call, string("tostring"), 5, string("$")), _outp=string(""), _x=string(""))
    # do not process the first line which contains the directive:
    if input._readLine(p._x):
        p._line += 1
    while input._readLine(p._x):
        p._line += 1
        _parseLine(ctx, p)
    _newLine(p)
    result = move(p._outp)
    return result

# ------------------------------------------------------------ the dispatcher


class _FilterKind(NStrEnum):
    filtNone = "none"
    filtTemplate = "stdtmpl"
    filtReplace = "replace"
    filtStrip = "strip"


def _getFilter(name: string) -> _FilterKind:
    result = _FilterKind.filtNone
    for i in inrange(low(_FilterKind), high(_FilterKind)):
        if cmpIgnoreStyle(name, str(i)) == 0:
            return i
    return result


def _applyFilter(ctx: mut @ _FilterContext, n: Cursor, input: mut @ _LineReader):
    with var:
        callee = string("")
    if n.kind() == NifKind.Ident:
        callee = strVal(n)
    elif n.kind() == NifKind.TagLit and _tag(n) in [string("call"), string("cmd"), string("callstrlit"), string("infix"), string("prefix"), string("postfix")] and childCursor(n).kind() == NifKind.Ident:
        callee = strVal(childCursor(n))
    else:
        with let:
            info = n.rawLineInfo()
        ctx._filterError(info.line, info.col, string("invalid filter: ") + _render(n))
    with var:
        output = string("")
    match _getFilter(callee):
        case _FilterKind.filtNone: return
        case _FilterKind.filtTemplate: output = _filterTmpl(ctx, input, n)
        case _FilterKind.filtStrip: output = _filterStrip(ctx, input, n)
        case _FilterKind.filtReplace: output = _filterReplace(ctx, input, n)
    input <<= _LineReader(_s=output, _rd=0, _fromFile=False)


def _evalPipe(ctx: mut @ _FilterContext, n: Cursor, input: mut @ _LineReader):
    if n.kind() == NifKind.TagLit and _tag(n) == "infix" and childCursor(n).kind() == NifKind.Ident and strVal(childCursor(n)) == "|":
        with var:
            k = childCursor(n)
        skip(k)
        for i in inrange(1, 2):
            if k.kind() == NifKind.TagLit and _tag(k) == "infix":
                _evalPipe(ctx, k, input)
            else:
                _applyFilter(ctx, k, input)
            skip(k)
    elif n.kind() == NifKind.TagLit and _tag(n) == "stmts":
        with let:
            k = childCursor(n)
        if k.hasMore(): _evalPipe(ctx, k, input)
    else:
        _applyFilter(ctx, n, input)


def _containsShebang(s: string, i: nint) -> bool:
    if i + 1 < s.len and s[i] == ch('#') and s[i + 1] == ch('!'):
        with var:
            j = nint(i + 2)
        while j < s.len and s[j] in _Whitespace: j += 1
        result = j < s.len and s[j] == ch('/')
    else:
        result = False
    return result


def applyFilters(src: string, filename: string, failed: mut @ bool) -> string:
    ## `syntaxes.openParser`: the source the parser gets, which is `src` itself
    ## unless the first line (after a BOM and a shebang line) is a `#?` pipe.
    with var:
        r = _LineReader(_s=src, _rd=0, _fromFile=True)
        line = string("")
    _ = r._readLine(line)
    with var:
        i = nint(3 if line.len >= 3 and line[0] == ch('\xef') and line[1] == ch('\xbb') and line[2] == ch('\xbf') else 0)
    if _containsShebang(line, i):
        _ = r._readLine(line)
        i = 0
    if not (i + 1 < line.len and line[i] == ch('#') and line[i + 1] == ch('?')):
        return src.copy()
    i += 2
    while i < line.len and line[i] in _Whitespace: i += 1
    with var:
        pipe = openParser(substr(line, i), filename, pool, globalTags)
    pModule(pipe)
    if pipe.failed: pipe.reportFailure()
    with var:
        ctx = _FilterContext(_filename=filename)
        input = _LineReader(_s=src, _rd=0, _fromFile=True)
        pipeBuf = pipe.finish()
        c = pipeBuf.beginRead()
    _evalPipe(ctx, c, input)
    endRead(c)
    pipe.close()
    failed <<= ctx.failed
    result = src if input._fromFile else move(input._s)
    return result


if comptime(__name__ == "__main__"):
    # the source filters (a `#?` pipe on the first line): the code the parser gets and whether a filter failed
    def show(src: string):
        with var:
            failed = nbool(False)
        with let:
            code = applyFilters(src, string("t.nim"), failed)
        echo(code)
        echo("failed: ", failed)

    show(string("echo 1\n"))
    show(string("#? stdtmpl | standard\n#proc f(x: int): string =\n#  result = \"\"\nvalue $x and ${x + 1}\n#end proc\n"))
    show(string("#? stdtmpl(subsChar = '$', metaChar = '%')\n%for i in 0..2:\n  line $i\n%end for\n"))
    show(string("#? strip(leading = true, trailing = true)\n   echo 1   \n  echo 2  \n"))
    show(string("#? replace(sub = \"X\", by = \"echo\")\nX 1\nX 2\n"))
    show(string("#? stdtmpl\n#if x:\n#end while\n"))
    show(string("#? nosuchfilter\necho 1\n"))
