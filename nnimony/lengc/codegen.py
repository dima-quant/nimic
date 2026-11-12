# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/codegen.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

# We produce C code as a list of tokens.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    # `moveToDataSection` & co. are `.dirty` templates whose bodies reach for the
    # caller's `c`; sem needs the feature to leave those idents untyped until the
    # expansion site (see doc/porting.md, "Dirty templates").
    pragma("feature: \"untyped\"")

from nimic.std import assertions, tables, formatfloat
from nimic.std.syncio import writeLine
from nimic.std.sets import HashSet
from nimic.std.intsets import IntSet
from nimic.std.packedsets import initPackedSet, PackedSet
importFrom("nimic.std.syncio", "readFile", "writeFile")
importFrom("nimic.std.os", "changeFileExt", "splitFile", "extractFilename", "fileExists")
from ..lib.vfs import vfsWrite
importFrom("nimic.std.sequtils", "insert")

from ..lib import nifcoreparse
from ..lib.nifcoreparse import (
    addSubtree, BiTable, charLit, childCursor, createTokenBuf, Cursor, FileId, floatVal, getOrIncl,
    initBiTable, intVal, isValid, kind, NifKind, NifLineInfo, pool, realFile, StrId, strId, SymId, symId,
    tags, toString, uintVal)  # re-exports nifcore
from ..lib.nifcdecl import (
    AddrKinds, asTypeDecl, asUnionBranch, CallConv, callConvKind, elementType, exprKind, into, isUnionBranch,
    LengExpr, LengOther, LengPragma, LengStmt, LengSym, LengType, LengTypeQualifier, loopInto, pragmaKind,
    skip, stmtKind, substructureKind, takeFieldDecl, takeParamDecl, takeProcDecl, takeProcType, takeTypeDecl,
    takeVarDecl, typeKind, typeQual)  # leng_model replacement (stmtKind/decls/tags)
from ..lib.intrinsics import IntrinsicNames, IntrinsicOp, IntrinsicRows  # the shared `{.instruction.}` / `{.intrinsic.}` table
from .mangler import makeCString, mangleToC, toCChar
from .cprelude import Prelude
from .noptions import Backend, Option, State
from ..lib import symparser
from . import typenav, nifmodules
from .typenav import (
    cBuiltinFor, createIntegralType, FieldSelector, getNominalType, getType, intrinsicOfCallee, isImportC,
    navigateToObjectBody, typeOfField)
from .nifmodules import externName, getDeclOrNil, MainModule
load = overloads(nifcoreparse.load, nifmodules.load)  # nifcore MainModule + getType (local)


@distinct
class _Token(uint32):
    def __eq__(a: _Token, b: _Token) -> bool:
        """{.borrow, private.}"""
        return super().__eq__(b)


class _PredefinedToken(NStrEnum):
    IgnoreMe = "<unused>"
    EmptyToken = ""
    CurlyLe = "{"
    CurlyRi = "}"
    ParLe = "("
    ParRi = ")"
    BracketLe = "["
    BracketRi = "]"
    NewLine = "\n"
    Semicolon = ";"
    Comma = ", "
    Space = " "
    Colon = ": "
    Dot = "."
    Arrow = "->"
    Star = "*"
    Amp = "&"
    DoubleQuote = "\""
    AsgnOpr = " = "
    ScopeOpr = "::"
    ConstKeyword = "const "
    StaticKeyword = "static "
    ExternKeyword = "extern "
    WhileKeyword = "while "
    GotoKeyword = "goto "
    IfKeyword = "if "
    ElseKeyword = "else "
    SwitchKeyword = "switch "
    CaseKeyword = "case "
    DefaultKeyword = "default:"
    BreakKeyword = "break"
    NullPtr = "NIM_NIL"
    ReturnKeyword = "return"
    TypedefStruct = "typedef struct "
    TypedefUnion = "typedef union "
    TypedefKeyword = "typedef "
    IncludeKeyword = "#include "
    LineDirKeyword = "#line "
    DiscardToken = "(void) "
    TryKeyword = "try "
    CatchKeyword = "catch ("
    ThrowKeyword = "throw"
    ErrToken = "LENGC_ERR_"
    OvfToken = "LENGC_OVF_"
    ThreadVarToken = "NIM_THREADVAR "
    AnonStruct = "struct "
    AnonUnion = "union "


# nifcore compatibility shims: the nifcursors world had a global `pool` and
# packed line info; here a StrLit carries its StrId in its own buffer's pool,
# and line info is a plain NifLineInfo on the cursor.
def _litId(c: Cursor) -> StrId:
    """{.inline.}"""
    return strId(c)


def _info(c: Cursor) -> NifLineInfo:
    """{.inline.}"""
    return c.rawLineInfo()


def _firstSon(c: Cursor) -> Cursor:
    """{.inline.}"""
    result = c.copy()
    result.inc()
    return result


def _toString(c: Cursor, spaces: bool) -> string:
    ## nifcore render shim for the nifcursors `toString(Cursor, bool)`.
    with var:
        buf = createTokenBuf(8, pool(c), tags(c))
    addSubtree(buf, c)
    result = nifcoreparse.toString(buf)
    return result


def _fillTokenTable(tab: mut @ BiTable[_Token, string]):
    for e in inrange(_PredefinedToken.EmptyToken, high(_PredefinedToken)):
        with let:
            id = getOrIncl(tab, str(e))
        assert id == _Token(e), str(uint32(id)) + string(" ") + str(ord(e))


class GenFlag(NIntEnum):
    gfMainModule = auto()  # isMainModule
    gfHasError = auto()  # already generated the error variable
    gfInCallImportC = auto()  # in importC call context
    gfInFlexArray = auto()  # initializing a flexible-array-member field (suppress NC8* cast)


class CurrentProc(Object):
    _needsOverflowFlag: bool
    _nextTemp: nint
    _vflags: HashSet[SymId]  # name and label token's position in the produced code


class GeneratedCode(Object):
    _m: MainModule
    _includes: seq[_Token]
    _includedHeaders: IntSet
    _protos: seq[_Token]
    _data: seq[_Token]
    _code: seq[_Token]
    _init: seq[_Token]
    _fileIds: PackedSet[FileId]
    _tokens: BiTable[_Token, string]
    _headerFile: seq[_Token]
    _generatedTypes: HashSet[SymId]
    _requestedSyms: HashSet[SymId]
    _flags: Tset[GenFlag]
    _inToplevel: bool
    _objConstrNeedsType: bool
    _bits: nint
    _currentProc: CurrentProc

    @dispatch
    def add(c: mut @ GeneratedCode, t: _PredefinedToken):
        """{.inline.}"""
        c._code.add(_Token(t))

    @dispatch
    def add(c: mut @ GeneratedCode, s: string):
        """{.inline.}"""
        c._code.add(getOrIncl(c._tokens, s))

    def _genIntLit(c: mut @ GeneratedCode, i: int64):
        if i > low(int32) and i <= high(int32) and c._bits != 64:
            c.add(str(i))
        elif i == low(int32) and c._bits != 64:
            # Nim has the same bug for the same reasons :-)
            c.add(string("(-2147483647 -1)"))
        elif i > low(int64):
            c.add(string("IL64("))
            c.add(str(i))
            c.add(string(")"))
        else:
            c.add(string("(IL64(-9223372036854775807) - IL64(1))"))

    def _genUIntLit(c: mut @ GeneratedCode, i: uint64):
        if i <= high(uint32) and c._bits != 64:
            c.add(str(i))
            c.add(string("u"))
        else:
            c.add(str(i))
            c.add(string("ull"))

    def _inclHeader(c: mut @ GeneratedCode, lit: StrId):
        with let:
            headerAsStr: pragma("cursor") = c._m.pool.strings[lit]
            header = getOrIncl(c._tokens, headerAsStr)
        if headerAsStr.len > 0 and not c._includedHeaders.containsOrIncl(nint(header)):
            if headerAsStr[0] == char('#'):
                # keeps the #include statements as they are
                c._includes.add(header)
            else:
                c._includes.add(_Token(_PredefinedToken.IncludeKeyword))
                if headerAsStr[0] == char('<'):
                    c._includes.add(header)
                else:
                    c._includes.add(_Token(_PredefinedToken.DoubleQuote))
                    c._includes.add(header)
                    c._includes.add(_Token(_PredefinedToken.DoubleQuote))

            c._includes.add(_Token(_PredefinedToken.NewLine))

    def _genCLineDir(c: mut @ GeneratedCode, info: NifLineInfo):
        if Option.optLineDir in c._m.config.options and info.isValid():
            with let:
                id = info.file
                line = info.line
                name = string("FX_") + str(nint(id))
            c.add(_PredefinedToken.LineDirKeyword)
            c.add(str(line))
            c.add(_PredefinedToken.Space)
            c.add(name)
            c.add(_PredefinedToken.NewLine)
            if isValid(id):
                c._fileIds.incl(id)

    def _overflowDeclTokens(c: mut @ GeneratedCode) -> seq[_Token]:
        ## The `NB8 ovf = NIM_FALSE;` prologue. Returned instead of inserted by the
        ## callee: the destination is always a field of `c` itself, and passing it as
        ## a separate `var seq` parameter next to `c` aliases the two.
        result = seq[_Token]([getOrIncl(c._tokens, string("NB8")), _Token(_PredefinedToken.Space), _Token(_PredefinedToken.OvfToken), _Token(_PredefinedToken.AsgnOpr), getOrIncl(c._tokens, string("NIM_FALSE")), _Token(_PredefinedToken.Semicolon)])
        return result


def initGeneratedCode(m: sink @ MainModule, flags: Tset[GenFlag], bits: nint) -> GeneratedCode:
    result = GeneratedCode(_m=m, _code=seq[_Token]([]), _tokens=initBiTable[_Token, string](), _fileIds=initPackedSet[FileId](), _flags=flags, _inToplevel=True, _objConstrNeedsType=True, _bits=bits)
    _fillTokenTable(result._tokens)
    return result


class _CppFile(Object):
    _buf: string  # write to buffer, then to the file at the end

    @dispatch
    def _write(f: mut @ _CppFile, s: string):
        f._buf.add(s)

    @dispatch
    def _write(f: mut @ _CppFile, c: char):
        f._buf.add(c)

    def _writeTokenSeq(f: mut @ _CppFile, s: seq[_Token], c: GeneratedCode):
        with var:
            indent = nint(0)
        for i in range(s.len):
            with let:
                x = s[i]
            match x:
                case _ if x == _Token(_PredefinedToken.CurlyLe):
                    indent += 1
                    f._write(c._tokens[x])
                    f._write(string("\n"))
                    for i in inrange(1, indent * 2): f._write(char(' '))
                case _ if x == _Token(_PredefinedToken.CurlyRi):
                    indent -= 1
                    f._write(c._tokens[x])
                    if i + 1 < s.len and s[i + 1] == _Token(_PredefinedToken.CurlyRi):
                        pass
                    else:
                        f._write(string("\n"))
                        for i in inrange(1, indent * 2): f._write(char(' '))
                case _ if x == _Token(_PredefinedToken.Semicolon):
                    f._write(c._tokens[x])
                    if i + 1 < s.len and s[i + 1] == _Token(_PredefinedToken.CurlyRi):
                        _ = "no newline before }"
                    else:
                        f._write(string("\n"))
                        for i in inrange(1, indent * 2): f._write(char(' '))
                case _ if x == _Token(_PredefinedToken.NewLine):
                    f._write(c._tokens[x])
                    for i in inrange(1, indent * 2): f._write(char(' '))
                case _:
                    f._write(c._tokens[x])

    def _writeLineDir(f: mut @ _CppFile, c: mut @ GeneratedCode):
        for id in items(c._fileIds):
            with let:
                name = string("FX_") + str(nint(id))
                def_ = string("#define ") + name + string(" \"") + c._m.pool.filenames[id] + string("\"")
            f._write(def_)
            f._write(string("\n"))


def _render(m: MainModule, n: Cursor) -> string:
    with var:
        buf = createTokenBuf(8, m.pool, m.tags)
    addSubtree(buf, n)
    result = toString(buf)
    return result


def _errorAt(m: MainModule, msg: string, n: Cursor):
    """{.noreturn.}"""
    ## `error` without the trailing render of `n`. For a message that already names
    ## what is wrong in prose: rendering the node would append its raw NIF spelling
    ## (mangled symbol plus embedded line info), which says nothing a reader wants.
    with let:
        info = n.rawLineInfo()
    if info.isValid():
        write(stdout, realFile(m.pool.filenames[info.file]))
        write(stdout, string("(") + str(info.line) + string(", ") + str(info.col + 1) + string(") "))
    # `Error: `, not the `[Error] ` of the rendering `error` above: this is a
    # user-facing diagnostic, and that is the spelling every other user-facing
    # nimony error uses (the test harness keys the expected exit code off it).
    write(stdout, string("Error: "))
    writeLine(stdout, msg)
    if comptime(defined("debug")):
        echo(getStackTrace())
    quit(1)


def _error(m: MainModule, msg: string, n: Cursor):
    """{.noreturn.}"""
    with let:
        info = n.rawLineInfo()
    if info.isValid():
        write(stdout, realFile(m.pool.filenames[info.file]))
        write(stdout, string("(") + str(info.line) + string(", ") + str(info.col + 1) + string(") "))
    write(stdout, string("[Error] "))
    write(stdout, msg)
    writeLine(stdout, _render(m, n))
    if comptime(defined("debug")):
        echo(getStackTrace())
    quit(1)

# Atoms

# Type graph


def _callingConvToStr(cc: CallConv) -> string:
    match cc:
        case CallConv.NoCallConv: return string("")
        case CallConv.Cdecl: return string("N_CDECL")
        case CallConv.Stdcall: return string("N_STDCALL")
        case CallConv.Safecall: return string("N_SAFECALL")
        case CallConv.Syscall: return string("N_SYSCALL")
        case CallConv.Fastcall: return string("N_FASTCALL")
        case CallConv.Thiscall: return string("N_THISCALL")
        case CallConv.Noconv: return string("N_NOCONV")
        case CallConv.Member: return string("N_NOCONV")
        case CallConv.Nimcall: return string("N_NIMCALL")


include("gentypes")

# Procs


class _PragmaInfo(Object):
    _flags: Tset[LengPragma]
    _extern: StrId
    _attr: StrId
    _callConv: CallConv

    def _isBareImportProc(prag: _PragmaInfo) -> bool:
        """{.inline.}"""
        ## `importc` proc with neither `header` nor `nodecl`: declared by US, under
        ## its mangled name + `__asm__` label (collision-proof against header
        ## prototypes for the same libc identifier — see `mangleSym`).
        return LengPragma.ImportcP in prag._flags and Tset[LengPragma](LengPragma.HeaderP, LengPragma.NodeclP) * prag._flags == Tset[LengPragma]()


def _parseProcPragmas(c: mut @ GeneratedCode, n: mut @ Cursor) -> _PragmaInfo:
    result = _PragmaInfo()
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            with let:
                pk = pragmaKind(n)
            match pk:
                case LengPragma.NoPragma | LengPragma.AlignP | LengPragma.BitsP | LengPragma.VectorP | LengPragma.StaticP | LengPragma.PackedP:
                    if callConvKind(n) != CallConv.NoCallConv:
                        result._callConv = callConvKind(n)
                        skip(n)
                    else:
                        _error(c._m, string("invalid proc pragma: "), n)
                case LengPragma.NodeclP:
                    result._flags.incl(LengPragma.NodeclP)
                    skip(n)
                case LengPragma.DynlibP:
                    # Static-import library annotation for the NATIVE backend (arkham);
                    # meaningless for C output — the linker resolves the symbol.
                    skip(n)
                case LengPragma.ConstrefP:
                    # A PARAMETER pragma; never legal on a proc.
                    _error(c._m, string("invalid proc pragma: "), n)
                case LengPragma.ImportjsP:
                    # The JS back end's extern: the argument is a JS splice template only
                    # jorogumo can answer. Ignoring it would emit a call to a C symbol that is
                    # never declared, so refuse while the name is still in hand.
                    _errorAt(c._m, string("importjs is a JS-backend pragma and has no C lowering"), n)
                case LengPragma.ImportcppP | LengPragma.ImportcP | LengPragma.ExportcP:
                    with into(n):
                        if n.hasMore() and kind(n) == NifKind.StrLit:
                            result._extern = _litId(n)
                            n.inc()
                        result._flags.incl(pk)
                        while n.hasMore(): skip(n)
                case LengPragma.HeaderP:
                    with into(n):
                        if kind(n) != NifKind.StrLit:
                            _error(c._m, string("expected string literal in header pragma but got: "), n)
                        else:
                            c._inclHeader(_litId(n))
                            result._flags.incl(pk)
                            n.inc()
                        while n.hasMore(): skip(n)
                case LengPragma.SelectanyP:
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.InstructionP | LengPragma.IntrinsicP:
                    # An intrinsic declares a machine instruction, not a callable: there is
                    # no definition anywhere, and every call to it is an `(instr …)` the
                    # expression generator lowers directly. Recording the flag is enough —
                    # `genProcDecl` then emits nothing for the declaration itself.
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.AssemblerP | LengPragma.NakedP:
                    # `{.assembler.}`/`{.naked.}` bodies are transliterated by arkham, not
                    # compiled to C.
                    # Routing them into a C build means assembling them separately and
                    # linking the object — see `nativenif/doc/asm-c-interop.md`, which is not
                    # built yet. Reject loudly rather than emit a prototype that will fail to
                    # link with no explanation.
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.InterruptP:
                    # An interrupt-table entry, and a C build has no such table to install it
                    # in. Emitting the function anyway would compile and link and simply
                    # never be reached — a device that does not respond to the interrupt,
                    # with nothing at the failure site to say why. `{.exportc: "…".}` is
                    # what binds a handler by name against a vendor startup file.
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.RegisterP | LengPragma.StackP:
                    # Location pins. They are assertions inside an `{.assembler.}` proc
                    # (rejected above) and allocator hints outside one; C has no way to
                    # honour either (its own `register` keyword is advisory), so drop them.
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.WasP:
                    _genWasPragma(c, n)
                case LengPragma.ErrsP | LengPragma.RaisesP | LengPragma.SmryP:
                    skip(n)
                case LengPragma.InlineP:
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.AlwaysInlineP | LengPragma.NoinlineP:
                    result._flags.incl(pk)
                    skip(n)
                case LengPragma.AttrP:
                    with into(n):
                        if kind(n) != NifKind.StrLit:
                            _error(c._m, string("expected string literal in attr pragma but got: "), n)
                        else:
                            result._attr = _litId(n)
                        n.inc()
                        while n.hasMore(): skip(n)
    else:
        _error(c._m, string("expected proc pragmas but got: "), n)
    return result


def _genSymDef(c: mut @ GeneratedCode, n: Cursor, prag: _PragmaInfo, isProc=False) -> string:
    if kind(n) == NifKind.SymbolDef:
        with let:
            lit = symId(n)
        if Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP, LengPragma.ExportcP) * prag._flags != Tset[LengPragma]():
            if isProc and prag._isBareImportProc():
                result = mangleToC(c._m.pool.symString(lit))
            elif prag._extern != StrId(0):
                result = c._m.pool.strings[prag._extern].copy()
            else:
                result = c._m.pool.symBasename(lit)
        else:
            result = mangleToC(c._m.pool.symString(lit))
        c.add(result)
    else:
        result = string("")
        _error(c._m, string("expected SymbolDef but got: "), n)
    return result


def _genParamPragmas(c: mut @ GeneratedCode, n: mut @ Cursor):
    # ProcPragma ::= (was Identifier) | Attribute
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            match pragmaKind(n):
                case LengPragma.AttrP:
                    with into(n):
                        c.add(string(" __attribute__((") + c._m.pool.strings[_litId(n)] + string("))"))
                        n.inc()
                        while n.hasMore(): skip(n)
                case LengPragma.WasP:
                    _genWasPragma(c, n)
                case LengPragma.ConstrefP:
                    # Provenance only (see `doc/tags.md`): the pointer stands for a
                    # by-value source parameter. Nothing to emit — it exists for
                    # `funcsummary`/the optimizer.
                    skip(n)
                case _:
                    _error(c._m, string("invalid pragma: "), n)
    else:
        _error(c._m, string("expected pragmas but got: "), n)


def _genParam(c: mut @ GeneratedCode, n: mut @ Cursor):
    with var:
        d = takeParamDecl(n)
    if kind(d.name) == NifKind.SymbolDef:
        with let:
            s = symId(d.name)
        c._m.registerLocal(s, d.typ)
        with var:
            skipDecl = nbool(False)
        with let:
            name = _mangleDecl(c, d.name, d.pragmas, skipDecl)
        _genType(c, d.typ, name)
        _genParamPragmas(c, d.pragmas)
    else:
        _error(c._m, string("expected SymbolDef but got: "), d.name)


def _genVarPragmas(c: mut @ GeneratedCode, n: mut @ Cursor) -> Tset[LengPragma]:
    result = Tset[LengPragma]()
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            with let:
                pk = pragmaKind(n)
            match pk:
                case LengPragma.AlignP:
                    with into(n):
                        c.add(string(" NIM_ALIGN(") + str(intVal(n)) + string(")"))
                        n.inc()
                        while n.hasMore(): skip(n)
                case LengPragma.AttrP:
                    with into(n):
                        c.add(string(" __attribute__((") + c._m.pool.strings[_litId(n)] + string("))"))
                        skip(n)
                        while n.hasMore(): skip(n)
                case LengPragma.WasP:
                    _genWasPragma(c, n)
                case LengPragma.HeaderP:
                    with into(n):
                        if kind(n) != NifKind.StrLit:
                            _error(c._m, string("expected string literal in header pragma but got: "), n)
                        else:
                            c._inclHeader(_litId(n))
                            result.incl(pk)
                            skip(n)
                        while n.hasMore(): skip(n)
                case LengPragma.StaticP | LengPragma.ImportcP | LengPragma.ImportcppP | LengPragma.ExportcP | LengPragma.NodeclP:
                    result.incl(pk)
                    skip(n)
                case _:
                    _error(c._m, string("invalid pragma: "), n)
    else:
        _error(c._m, string("expected pragmas but got: "), n)
    return result


@template
def _moveToDataSection(body: untyped):
    """{.dirty.}"""
    with let:
        oldLen = c._code.len
    body
    for i in range(oldLen, c._code.len):
        c._data.add(c._code[i])
    setLen(c._code, oldLen)


@template
def _moveToInitSection(body: untyped):
    """{.dirty.}"""
    with let:
        oldLen = c._code.len
    body
    for i in range(oldLen, c._code.len):
        c._init.add(c._code[i])
    setLen(c._code, oldLen)


include("genexprs")


class _VarKind(NIntEnum):
    IsLocal = auto()
    IsGlobal = auto()
    IsThreadlocal = auto()
    IsConst = auto()
    IsMflag = auto()


def _isLiteral(n: mut @ Cursor) -> bool:
    match kind(n):
        case NifKind.IntLit | NifKind.UIntLit | NifKind.FloatLit | NifKind.CharLit | NifKind.StrLit | NifKind.DotToken:
            result = True
            n.inc()
        case _:
            match exprKind(n):
                case LengExpr.FalseC | LengExpr.TrueC | LengExpr.InfC | LengExpr.NeginfC | LengExpr.NanC | LengExpr.SufC | LengExpr.NilC:
                    result = True
                    skip(n)
                case LengExpr.AconstrC | LengExpr.OconstrC | LengExpr.CastC | LengExpr.ConvC:
                    result = True
                    for _ in into(n):
                        skip(n)  # type
                        while n.hasMore():
                            if substructureKind(n) == LengOther.KvU:
                                for _ in into(n):
                                    skip(n)  # key (field name Symbol - not a value to check)
                                    if not _isLiteral(n): return False  # check the value
                                    if n.hasMore():
                                        skip(n)  # optional inheritance
                                    while n.hasMore(): skip(n)
                            else:
                                if not _isLiteral(n): return False
                case _:
                    result = False
    return result


def _genStmt(c: mut @ GeneratedCode, n: mut @ Cursor):
    pass


def _genOnError(c: mut @ GeneratedCode, n: mut @ Cursor):
    c.add(_PredefinedToken.IfKeyword)
    c.add(_PredefinedToken.ParLe)
    c.add(_PredefinedToken.ErrToken)
    c.add(_PredefinedToken.ParRi)
    c.add(_PredefinedToken.Space)
    c.add(_PredefinedToken.CurlyLe)
    _genStmt(c, n)
    c.add(_PredefinedToken.CurlyRi)


def _genVarInitValue(c: mut @ GeneratedCode, n: mut @ Cursor):
    if kind(n) == NifKind.DotToken:
        n.inc()
        c.add(_PredefinedToken.Semicolon)
    elif stmtKind(n) == LengStmt.OnerrS:
        with var:
            onErrAction = n.copy()
        onErrAction.inc()
        c.add(_PredefinedToken.AsgnOpr)
        _genCallCanRaise(c, n)
        c.add(_PredefinedToken.Semicolon)
        if kind(onErrAction) != NifKind.DotToken:
            _genOnError(c, onErrAction)
    else:
        c.add(_PredefinedToken.AsgnOpr)
        _genx(c, n)
        c.add(_PredefinedToken.Semicolon)


def _genVarDecl(c: mut @ GeneratedCode, n: mut @ Cursor, vk: _VarKind, toExtern=False, useStatic=False):
    c._genCLineDir(_info(n))
    with var:
        d = takeVarDecl(n)
    if kind(d.name) == NifKind.SymbolDef:
        with let:
            lit = symId(d.name)
        # Infer the variable's type from its initializer when the explicit type
        # slot is empty. Leng has no general var-type inference; the tree
        # optimizers (cse / induction_variables) synthesize `(var :t . . (addr
        # expr))` without spelling out the pointer type, and without this the
        # empty slot degrades to `void`, so the `(deref t)` uses produce invalid C.
        with var:
            typ = d.typ.copy()
        if kind(typ) == NifKind.DotToken and kind(d.value) != NifKind.DotToken:
            typ = getNominalType(c._m, d.value)
        c._m.registerLocal(lit, typ)
        with var:
            skipDecl = nbool(False)
        with let:
            name = _mangleDecl(c, d.name, d.pragmas, skipDecl)
            beforeDecl = c._code.len

        if toExtern or isImportC(c._m, d.name):
            c.add(_PredefinedToken.ExternKeyword)

        if vk == _VarKind.IsThreadlocal:
            c.add(string("__thread "))
        _genType(c, typ, name, isConst=vk == _VarKind.IsConst)
        with let:
            flags = _genVarPragmas(c, d.pragmas)
        if not toExtern and (LengPragma.StaticP in flags or useStatic):
            c._code.insert([_Token(_PredefinedToken.StaticKeyword)], beforeDecl)
        with let:
            beforeInit = c._code.len

        with var:
            value = d.value.copy()
        with let:
            mustMoveToInit = (vk == _VarKind.IsGlobal and not _isLiteral(value))
        if toExtern:
            c.add(_PredefinedToken.Semicolon)
        else:
            if vk != _VarKind.IsLocal and not mustMoveToInit: c._objConstrNeedsType = False
            _genVarInitValue(c, d.value)
            if vk != _VarKind.IsLocal and not mustMoveToInit: c._objConstrNeedsType = True

        if skipDecl:
            setLen(c._code, beforeDecl)
        elif vk == _VarKind.IsLocal and c._inToplevel:
            for i in range(beforeDecl, c._code.len):
                c._init.add(c._code[i])
            setLen(c._code, beforeDecl)
            c.add(_PredefinedToken.Semicolon)
        elif mustMoveToInit and not toExtern:
            c._init.add(getOrIncl(c._tokens, name))
            for i in range(beforeInit, c._code.len):
                c._init.add(c._code[i])
            setLen(c._code, beforeInit)
            c.add(_PredefinedToken.Semicolon)
    else:
        _error(c._m, string("expected SymbolDef but got: "), d.name)


include("genstmts")


def _genProcDecl(c: mut @ GeneratedCode, n: mut @ Cursor, isExtern: bool):
    c._m.openScope()
    c._inToplevel = False
    with let:
        oldProc = c._currentProc.copy()
    c._currentProc = CurrentProc(_needsOverflowFlag=False)
    with let:
        signatureBegin = c._code.len
    with var:
        prc = takeProcDecl(n)

    with let:
        prag = _parseProcPragmas(c, prc.pragmas)
    if prag._flags * Tset[LengPragma](LengPragma.AssemblerP, LengPragma.NakedP) != Tset[LengPragma]():
        _errorAt(c._m, string("the C backend cannot compile an `{.assembler.}` proc; it must ") + string("be assembled by arkham and linked as an object (see doc/asm-c-interop.md)"), prc.name)
    if LengPragma.InterruptP in prag._flags:
        _errorAt(c._m, string("the C backend has no interrupt table to install an `{.interrupt.}` ") + string("handler in; use `{.exportc: \"...\".}` to bind one by name against a ") + string("startup file, or compile it with arkham"), prc.name)
    if Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP) * prag._flags != Tset[LengPragma]() and LengPragma.InlineP not in prag._flags and kind(prc.body) != NifKind.DotToken:
        # The back end emits only a declaration for an imported proc; a body here
        # is a hexer bug, not something to drop silently.
        _errorAt(c._m, string("BUG: imported proc reached Leng with a body"), prc.name)
    if prag._flags * Tset[LengPragma](LengPragma.InstructionP, LengPragma.IntrinsicP) != Tset[LengPragma]():
        # No C declaration: an intrinsic has no definition to link against, and
        # every application of it is an `(instr …)` lowered at the use site.
        # Undo EVERY piece of entry state, `inToplevel` included: the normal exit
        # restores it, and leaving it false here would make the rest of the module
        # think it is inside a proc — so a later module-scope `(var …)` would stop
        # being routed into `c.init` and land at file scope with its initializer.
        c._code.setLen(signatureBegin)
        c._m.closeScope()
        c._inToplevel = True
        c._currentProc = oldProc
        return
    if LengPragma.InlineP in prag._flags:
        c.add(_PredefinedToken.StaticKeyword)
        c.add(string("inline "))
    else:
        if isExtern:
            c.add(_PredefinedToken.ExternKeyword)
        if LengPragma.NoinlineP in prag._flags:
            c.add(string("N_NOINLINE "))

    with let:
        name = string()
    if prag._callConv != CallConv.NoCallConv:
        c.add(_callingConvToStr(prag._callConv))
        c.add(_PredefinedToken.ParLe)
        if kind(prc.returnType) == NifKind.DotToken:
            c.add(string("void"))
        else:
            _genType(c, prc.returnType)
        c.add(_PredefinedToken.Comma)
        if prag._attr != StrId(0):
            c.add(string("__attribute__((") + c._m.pool.strings[prag._attr] + string(")) "))
        name = _genSymDef(c, prc.name, prag, isProc=True)
        c.add(_PredefinedToken.ParRi)
    else:
        if kind(prc.returnType) == NifKind.DotToken:
            c.add(string("void"))
        else:
            _genType(c, prc.returnType)
        c.add(_PredefinedToken.Space)
        if prag._attr != StrId(0):
            c.add(string("__attribute__((") + c._m.pool.strings[prag._attr] + string(")) "))
        name = _genSymDef(c, prc.name, prag, isProc=True)

    c.add(_PredefinedToken.ParLe)

    with var:
        params = nint(0)
    if kind(prc.params) != NifKind.DotToken:
        with var:
            p = prc.params.copy()
        for _ in loopInto(p):
            if params > 0: c.add(_PredefinedToken.Comma)
            _genParam(c, p)
            params += 1

    if params == 0:
        c.add(string("void"))
    c.add(_PredefinedToken.ParRi)

    if Tset[LengPragma](LengPragma.NodeclP, LengPragma.HeaderP) * prag._flags != Tset[LengPragma]():
        c._code.setLen(signatureBegin)
    elif LengPragma.InlineP not in prag._flags and (isExtern or Tset[LengPragma](LengPragma.ImportcP, LengPragma.ImportcppP) * prag._flags != Tset[LengPragma]()):
        # External/imported function without body - just prototype
        if prag._isBareImportProc():
            # Bind the mangled identifier to the real symbol. The identifier never
            # collides with a header's prototype for the same libc function, which
            # matters since inliner splices carry bare-importc references into
            # arbitrary modules (measured: `write` vs <unistd.h> in threads/cps).
            with var:
                asmName = string("")
            if prag._extern != StrId(0):
                asmName = c._m.pool.strings[prag._extern].copy()
            else:
                asmName = c._m.pool.symBasename(symId(prc.name))
            c.add(string(" __asm__(NIM_ASM_PREFIX "))
            c.add(makeCString(asmName))
            c.add(string(")"))
        for i in range(signatureBegin, c._code.len):
            c._protos.add(c._code[i])
        c._protos.add(_Token(_PredefinedToken.Semicolon))
        c._code.setLen(signatureBegin)  # Remove signature from code since it's now in protos
    else:
        # Local function with body - generate prototype if requested by other modules
        if c._requestedSyms.contains(symId(prc.name)):
            for i in range(signatureBegin, c._code.len):
                c._protos.add(c._code[i])
            c._protos.add(_Token(_PredefinedToken.Semicolon))

        c.add(_PredefinedToken.CurlyLe)
        with let:
            beforeBody = c._code.len
        _genStmt(c, prc.body)
        if c._currentProc._needsOverflowFlag:
            with let:
                ovfDecl = c._overflowDeclTokens()
            c._code.insert(ovfDecl, beforeBody)
        c.add(_PredefinedToken.CurlyRi)
    c._m.closeScope()
    c._inToplevel = True
    c._currentProc = oldProc


@template
def _genForeignDataDecl(body: untyped):
    """{.dirty.}"""
    # Foreign var/const/gvar/tvar `extern` declarations are emitted by `genVar`
    # into `c.data` via `moveToDataSection`. But `genImportedSyms` runs *after*
    # `genToplevel` has already filled `c.data` with this module's own consts —
    # so the `extern` would land after a sibling const that takes its address
    # (e.g. `more = &strlit…` for a deduped long-string literal). C rejects the
    # forward reference. Relocate the just-emitted declaration to `c.protos`,
    # which is written before `c.data`, so the `extern` always precedes its use.
    with let:
        before = c._data.len
    body
    for i in range(before, c._data.len):
        c._protos.add(c._data[i])
    setLen(c._data, before)


@template_expand
def _genImportedSyms(c: mut @ GeneratedCode):
    # needs a good old fixpoint iteration as we expand the graph of imported symbols.
    while True:
        with let:
            fsyms = move(c._m.requestedForeignSyms)
        if fsyms.len == 0: break
        for fsym in fsyms:
            with var:
                n = fsym.copy()
            match stmtKind(fsym):
                case LengStmt.ProcS:
                    _genProcDecl(c, n, True)
                case LengStmt.VarS:
                    _ = "we need to ignore local variables of the form x.0.suffix here which are still produced sometimes by Nimony..."
                case LengStmt.GvarS:
                    with _genForeignDataDecl(): _genVar(c, n, _VarKind.IsGlobal, True)
                case LengStmt.TvarS:
                    with _genForeignDataDecl(): _genVar(c, n, _VarKind.IsThreadlocal, True)
                case LengStmt.ConstS:
                    with _genForeignDataDecl(): _genVar(c, n, _VarKind.IsConst, True)
                case _:
                    _ = "uninteresting symbol"


def _genNodecl(c: mut @ GeneratedCode, n: mut @ Cursor):
    with let:
        signatureBegin = c._code.len
    with into(n):
        match stmtKind(n):
            case LengStmt.ProcS: _genProcDecl(c, n, False)
            case LengStmt.VarS: _genStmt(c, n)
            case LengStmt.ConstS: _genStmt(c, n)
            case _:
                _error(c._m, string("expected declaration for `nodecl` but got: "), n)
        while n.hasMore(): skip(n)
    c._code.setLen(signatureBegin)


@template_expand
def _genToplevel(c: mut @ GeneratedCode, n: mut @ Cursor):
    # ExternDecl ::= (imp ProcDecl | VarDecl | ConstDecl)
    # Include ::= (incl StringLiteral)
    # TopLevelConstruct ::= ExternDecl | ProcDecl | VarDecl | ConstDecl |
    #                       TypeDecl | Include | EmitStmt
    match stmtKind(n):
        case LengStmt.ProcS: _genProcDecl(c, n, False)
        case LengStmt.VarS | LengStmt.GvarS | LengStmt.TvarS: _genStmt(c, n)
        case LengStmt.ConstS: _genVar(c, n, _VarKind.IsConst)
        case LengStmt.DiscardS | LengStmt.AsgnS | LengStmt.KeepovfS | LengStmt.ScopeS | LengStmt.IfS | LengStmt.WhileS | LengStmt.CaseS | LengStmt.LabS | LengStmt.JmpS | LengStmt.TryS | LengStmt.RaiseS | LengStmt.CallS | LengStmt.OnerrS:
            with _moveToInitSection():
                _genStmt(c, n)
        case LengStmt.TypeS:
            _ = "handled in a different pass"
            skip(n)
        case LengStmt.EmitS: _genEmitStmt(c, n)
        case LengStmt.StmtsS:
            for _ in loopInto(n): _genToplevel(c, n)
        case _:
            _error(c._m, string("expected top level construct but got: "), n)


def _traverseCode(c: mut @ GeneratedCode, n: mut @ Cursor):
    if stmtKind(n) == LengStmt.StmtsS:
        for _ in loopInto(n): _genToplevel(c, n)
        _genImportedSyms(c)
    else:
        _error(c._m, string("expected `stmts` but got: "), n)


def generateCode(s: mut @ State, inp: string, outp: string, flags: Tset[GenFlag]):
    with var:
        m = load(inp)
    m.config = s.config
    with var:
        c = initGeneratedCode(m, flags, s.bits)
    c._m.openScope()

    with var:
        n = c._m.src.beginRead()
    _traverseCode(c, n)

    with let:
        realCode = move(c._code)
    # now that we have seen the full code, we also know all the involved types:
    with var:
        co = default(_TypeOrder)
    _traverseTypes(c._m, co)

    _generateTypes(c, co)
    with let:
        typeDecls = move(c._code)

    with var:
        f = default(_CppFile)
    f._write(string("#define NIM_INTBITS ") + str(s.bits) + string("\n"))
    f._write(Prelude)
    if GenFlag.gfMainModule in c._flags:
        f._write(str(_PredefinedToken.ThreadVarToken) + string("NB8 ") + str(_PredefinedToken.ErrToken) + str(_PredefinedToken.Semicolon) + string("\n"))

    f._writeTokenSeq(c._includes, c)
    if Option.optLineDir in c._m.config.options:
        f._writeLineDir(c)
    f._writeTokenSeq(typeDecls, c)
    # so that v-tables can be generated protos must be written before data:
    f._writeTokenSeq(c._protos, c)
    f._writeTokenSeq(c._data, c)
    f._writeTokenSeq(realCode, c)

    if c._init.len > 0:
        f._write(string("static void __attribute__((constructor)) init(void) {"))
        if c._currentProc._needsOverflowFlag:
            with let:
                ovfDecl = c._overflowDeclTokens()
            c._init.insert(ovfDecl, 0)
        f._writeTokenSeq(c._init, c)
        f._write(string("}\n\n"))

    # Always written: the `.c` file is no interface file, its one consumer is
    # this module's C compiler (doc/internals/ic.md).
    vfsWrite(outp, f._buf)

    if c._headerFile.len > 0:
        with let:
            selectHeader = outp.changeFileExt(string(".h"))
        with var:
            hbuf = string("")
        for x in items(c._headerFile):
            hbuf.add(c._tokens[x])
        vfsWrite(selectHeader, hbuf)

    c._m.closeScope()
