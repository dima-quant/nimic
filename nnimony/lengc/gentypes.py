# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/gentypes.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

# included from codegen.nim

## Generates C types from Leng types.

from __future__ import annotations
from nimic.ntypes import *


class _TypeList(Object):
    _processed: IntSet
    _s: seq[tuple[Cursor, _PredefinedToken]]

    def _add(dest: mut @ _TypeList, elem: Cursor, decl: _PredefinedToken):
        if not containsOrIncl(dest._processed, elem.toUniqueId()):
            dest._s.add((elem, decl))


class _TypeOrder(Object):
    _forwardedDecls: _TypeList
    _ordered: _TypeList
    _lookedAt: IntSet
    _lookedAtBodies: HashSet[SymId]


def _traverseObjectBody(m: mut @ MainModule, o: mut @ _TypeOrder, t: Cursor):
    pass


def _traverseProctypeBody(m: mut @ MainModule, o: mut @ _TypeOrder, t: Cursor):
    pass


def _usesHeader(pragmas: Cursor) -> bool:
    if kind(pragmas) == NifKind.TagLit:
        with var:
            p = pragmas.copy()
        for _ in into(p):
            while p.hasMore():
                match pragmaKind(p):
                    case LengPragma.HeaderP | LengPragma.NodeclP:
                        return True
                    case _:
                        pass
                skip(p)
    return False


def _recordDependencyImpl(m: mut @ MainModule, o: mut @ _TypeOrder, parent: Cursor, child: Cursor, viaPointer: mut @ bool, typeDecl: Cursor = default(Cursor)):
    # `typeDecl` is the enclosing named `(type …)` declaration whose body `child`
    # is — threaded down from the caller (the Symbol branch / top level) to stand
    # in for the nifcursors-only `tracebackTypeC`, which walked the buffer
    # backwards (impossible with forward-only nifcore cursors).
    with var:
        ch = child
    while True:
        match typeKind(ch):
            case LengType.AptrT | LengType.PtrT:
                viaPointer <<= True
                ch = elementType(ch)
            case LengType.FlexarrayT:
                viaPointer <<= False
                ch = elementType(ch)
            case _:
                break

    match typeKind(ch):
        case LengType.ObjectT | LengType.UnionT:
            with let:
                decl = _PredefinedToken.TypedefStruct if typeKind(ch) == LengType.ObjectT else _PredefinedToken.TypedefUnion
                obj = ch
            if viaPointer:
                o._forwardedDecls._add(parent, decl)
            else:
                if not containsOrIncl(o._lookedAt, obj.toUniqueId()):
                    _traverseObjectBody(m, o, obj)
                o._ordered._add(typeDecl, decl)
        case LengType.ArrayT:
            if viaPointer:
                o._forwardedDecls._add(parent, _PredefinedToken.TypedefStruct)
            else:
                if not containsOrIncl(o._lookedAt, ch.toUniqueId()):
                    with var:
                        viaPointer = nbool(False)
                    _recordDependencyImpl(m, o, ch, _firstSon(ch), viaPointer, typeDecl)
                o._ordered._add(typeDecl, _PredefinedToken.TypedefStruct)
        case LengType.EnumT:
            # enums do not depend on anything so always safe to generate them
            o._ordered._add(typeDecl, _PredefinedToken.TypedefKeyword)
        case LengType.ProctypeT:
            # Function-pointer typedefs in C don't have a separate "forward
            # declaration" form: `typedef X X;` is just a self-typedef and the
            # real `typedef R (*X)(args)` is required for the type to be usable
            # at all. So emit the full definition regardless of `viaPointer`;
            # the existing `lookedAt` guard already prevents repeated traversal
            # of the same proc-type, and `traverseProctypeBody` deliberately
            # recurses into params with `viaPointer = true` so cycles stay
            # bounded. Surfaced 2026-05-01 by self-host work on `sdl3.nim`,
            # where dynlib procs taking other proc types as parameters produced
            # `typedef X60Qt_… X60Qt_…;` lines that gcc rightly rejected.
            if not containsOrIncl(o._lookedAt, ch.toUniqueId()):
                _traverseProctypeBody(m, o, ch)
            o._ordered._add(typeDecl, _PredefinedToken.TypedefKeyword)
        case _:
            if kind(ch) == NifKind.Symbol:
                # follow the symbol to its definition:
                with let:
                    id = symId(ch)
                    def_ = getDeclOrNil(m, id)
                if isNil(def_):
                    _error(m, string("undeclared symbol: "), ch)
                else:
                    with var:
                        n = def_.pos
                    with let:
                        decl = asTypeDecl(n)
                        alreadyFullyProcessed = symId(decl.name) in o._lookedAtBodies
                    if not alreadyFullyProcessed and _usesHeader(decl.pragmas):
                        # we need to fake a forward decl here so that
                        #   SysThread {.importc: "pthread_t",
                        #        header: "<sys/types.h>" .} = distinct culong
                        # Will trigger the header include!
                        o._forwardedDecls._add(def_.pos, _PredefinedToken.TypedefKeyword)

                    if viaPointer:
                        # For `viaPointer` we must traverse it (possibly again), in a shallow manner or
                        # else we might miss crucial forward declarations. This case is triggered
                        # by the `Continuation` type.
                        _recordDependencyImpl(m, o, n, decl.body, viaPointer, n)
                    elif not alreadyFullyProcessed:
                        # First time seeing this type for full processing (not via pointer).
                        # Mark it as fully processed before recursing to handle cycles.
                        o._lookedAtBodies.incl(symId(decl.name))
                        _recordDependencyImpl(m, o, n, decl.body, viaPointer, n)
            else:
                _ = "uninteresting type as we only focus on the required struct declarations"


def _recordDependency(m: mut @ MainModule, o: mut @ _TypeOrder, parent: Cursor, child: Cursor):
    with var:
        viaPointer = nbool(False)
    _recordDependencyImpl(m, o, parent, child, viaPointer)


def _traverseObjectBody(m: mut @ MainModule, o: mut @ _TypeOrder, t: Cursor):
    with let:
        kind = typeKind(t)
    with var:
        n = t.copy()
    with into(n):  # enter (object …) | (union …)
        if kind == LengType.ObjectT:
            if nifcoreparse.kind(n) == NifKind.Symbol:
                # inheritance
                _recordDependency(m, o, t, n)
                n.inc()
            elif nifcoreparse.kind(n) == NifKind.DotToken:
                n.inc()
            else:
                _error(m, string("expected `Symbol` or `.` for inheritance but got: "), n)
        while n.hasMore():
            match nifcoreparse.kind(n):
                case NifKind.TagLit:
                    if substructureKind(n) == LengOther.FldU:
                        with let:
                            decl = takeFieldDecl(n)
                        _recordDependency(m, o, t, decl.typ)
                    elif typeKind(n) in Tset[LengType](LengType.ObjectT, LengType.UnionT):  # anonymous object/union
                        _traverseObjectBody(m, o, n)  # recurse into the anonymous subtree
                        skip(n)  # advance past it
                    elif isUnionBranch(n):  # discriminated union branch
                        with let:
                            b = asUnionBranch(n)
                        if typeKind(b.body) == LengType.ObjectT:
                            _traverseObjectBody(m, o, b.body)
                        skip(n)
                    else:
                        _error(m, string("unexpected node inside object: "), n)
                        skip(n)
                case _:
                    _error(m, string("unexpected token inside object: "), n)
                    n.inc()


def _traverseProctypeBody(m: mut @ MainModule, o: mut @ _TypeOrder, t: Cursor):
    with var:
        n = t.copy()
    with let:
        procType = takeProcType(n)
    with var:
        param = procType.params.copy()
    # we only have weak deps to the param types:
    with var:
        viaPointer = nbool(True)
    if kind(param) == NifKind.TagLit:
        with into(param):
            while param.hasMore():
                with let:
                    paramDecl = takeParamDecl(param)
                _recordDependencyImpl(m, o, t, paramDecl.typ, viaPointer)
    _recordDependencyImpl(m, o, t, procType.returnType, viaPointer)


def _traverseTypes(m: mut @ MainModule, o: mut @ _TypeOrder):
    with var:
        i = nint(0)
    # m.types can actually grow while we are traversing it, so we need to use a while loop:
    while i < m.types.len:
        with let:
            n = m.types[i].copy()
            decl = asTypeDecl(n)
            t = decl.body
        match typeKind(t):
            case LengType.ObjectT:
                _traverseObjectBody(m, o, t)
                o._ordered._add(n, _PredefinedToken.TypedefStruct)
            case LengType.UnionT:
                _traverseObjectBody(m, o, t)
                o._ordered._add(n, _PredefinedToken.TypedefUnion)
            case LengType.ArrayT:
                _recordDependency(m, o, t, _firstSon(t))
                o._ordered._add(n, _PredefinedToken.TypedefStruct)
            case LengType.ProctypeT:
                _traverseProctypeBody(m, o, t)
                o._ordered._add(n, _PredefinedToken.TypedefKeyword)
            case LengType.EnumT:
                o._ordered._add(n, _PredefinedToken.TypedefKeyword)
            case _:
                # An imported scalar such as `Handle {.importc: "HANDLE", header:
                # "<windef.h>".} = distinct int` has no body to order, but its header
                # still has to be included — a proc signature or a local may be its
                # only use in this module.
                if _usesHeader(decl.pragmas):
                    o._forwardedDecls._add(n, _PredefinedToken.TypedefKeyword)
        i += 1


def _integralBits(t: Cursor) -> string:
    """{.inline.}"""
    with let:
        res = intVal(t)
    if res == -1:
        result = string("")
    else:  # 8, 16, 32, 64 etc.
        result = str(res)
    return result


def _genProcTypePragma(c: mut @ GeneratedCode, n: Cursor):
    # ProcTypePragma ::= CallingConvention | Attribute
    match pragmaKind(n):
        case LengPragma.AttrP:
            c.add(string(" __attribute__((") + _toString(_firstSon(n), False) + string("))"))
        case _:
            if callConvKind(n) != CallConv.NoCallConv:
                _ = "already handled"
            else:
                _error(c._m, string("invalid proc type pragma: "), n)


def _genProcTypePragmas(c: mut @ GeneratedCode, n: mut @ Cursor):
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            _genProcTypePragma(c, n)
            skip(n)
    else:
        _error(c._m, string("expected proc type pragmas but got: "), n)


def _genWasPragma(c: mut @ GeneratedCode, n: mut @ Cursor):
    with into(n):
        c.add(string("/* ") + _toString(n, False) + string(" */"))
        skip(n)
        while n.hasMore(): skip(n)


def _genFieldPragmas(c: mut @ GeneratedCode, n: mut @ Cursor, bits: mut @ BiggestInt):
    # CommonPragma ::= (align Number) | (was Identifier) | Attribute
    # FieldPragma ::= CommonPragma | (bits Number)
    if kind(n) == NifKind.DotToken:
        n.inc()
    elif substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            match pragmaKind(n):
                case LengPragma.AlignP:
                    with into(n):
                        c.add(string(" NIM_ALIGN(") + str(intVal(n)) + string(")"))
                        skip(n)
                        while n.hasMore(): skip(n)
                case LengPragma.WasP:
                    _genWasPragma(c, n)
                case LengPragma.AttrP:
                    with into(n):
                        c.add(string(" __attribute__((") + _toString(n, False) + string("))"))
                        skip(n)
                        while n.hasMore(): skip(n)
                case LengPragma.BitsP:
                    with into(n):
                        bits <<= intVal(n)
                        skip(n)
                        while n.hasMore(): skip(n)
                case LengPragma.ExportcP | LengPragma.ImportcP | LengPragma.ImportcppP | LengPragma.NodeclP:
                    skip(n)
                case _:
                    _error(c._m, string("invalid field pragma: "), n)
    else:
        _error(c._m, string("expected field pragmas but got: "), n)


def _getPtrQualifier(c: mut @ GeneratedCode, n: Cursor, isCppRef: mut @ bool) -> string:
    match typeQual(n):
        case LengTypeQualifier.RoQ:
            result = string("const ")
        case LengTypeQualifier.AtomicQ:
            if c._m.config.backend == Backend.backendC:
                result = string("_Atomic ")
            else:
                # TODO: cpp doesn't support _Atomic
                result = string("")
        case LengTypeQualifier.RestrictQ:
            result = string("restrict ")
        case LengTypeQualifier.CpprefQ:
            if c._m.config.backend == Backend.backendCpp:
                isCppRef <<= True
            result = string("")
        case LengTypeQualifier.NoQualifier:
            _error(c._m, string("expected pointer qualifier but got: "), n)
    return result


def _genType(c: mut @ GeneratedCode, n: mut @ Cursor, name=string(""), isConst=False):
    pass


@template
def _maybeAddName(c: mut @ GeneratedCode, name: string, isConst: bool):
    if isConst:
        c.add(_PredefinedToken.Space)
        c.add(string("const"))
    if name != "":
        c.add(_PredefinedToken.Space)
        c.add(name)


@template
def _atom(c: mut @ GeneratedCode, s: string, name: string, isConst: bool):
    c.add(s)
    _maybeAddName(c, name, isConst)


def _atomNumber(c: mut @ GeneratedCode, n: mut @ Cursor, typeName: string, name: string, isConst: bool):
    with var:
        s = string()
    with into(n):
        # Empty type tags like `(bool)` have no children — guard with hasMore
        # before peeking, otherwise we'd read the next sibling.
        if n.hasMore() and kind(n) == NifKind.IntLit:
            s = typeName + _integralBits(n)
            n.inc()
        else:
            s = typeName
        while n.hasMore():
            match typeQual(n):
                case LengTypeQualifier.RoQ:
                    c.add(string("const "))
                    skip(n)
                case LengTypeQualifier.AtomicQ:
                    if c._m.config.backend == Backend.backendC:
                        c.add(string("_Atomic "))
                    else:
                        # TODO: cpp doesn't support _Atomic
                        pass
                    skip(n)
                case LengTypeQualifier.RestrictQ | LengTypeQualifier.CpprefQ:
                    _error(c._m, string("expected number qualifier but got: "), n)
                case LengTypeQualifier.NoQualifier:
                    match pragmaKind(n):
                        case LengPragma.HeaderP:
                            with into(n):
                                if kind(n) == NifKind.StrLit:
                                    c._inclHeader(_litId(n))
                                    n.inc()
                                else:
                                    _error(c._m, string("header pragma requires a string literal but got: "), n)
                                while n.hasMore(): skip(n)
                        case LengPragma.ImportcP | LengPragma.ImportcppP:
                            with into(n):
                                if kind(n) == NifKind.StrLit:
                                    s = c._m.pool.strings[_litId(n)]
                                    n.inc()
                                else:
                                    _error(c._m, string("importc/importcpp type requires a string literal but got: "), n)
                                while n.hasMore(): skip(n)
                        case LengPragma.NodeclP:
                            skip(n)
                        case _:
                            _error(c._m, string("expected number qualifier but got: "), n)
    _atom(c, s, name, isConst)


def _atomPointer(c: mut @ GeneratedCode, n: mut @ Cursor, name: string, isConst: bool):
    with var:
        elem = Cursor()
        isCppRef = nbool(False)
    with into(n):
        elem = n.copy()
        skip(n)  # element type
        while n.hasMore():
            c.add(_getPtrQualifier(c, n, isCppRef))
            skip(n)
    if typeKind(elem) == LengType.FlexarrayT:
        # `ptr (flexarray T)` must use the parenthesised declarator form
        # `T (*name)[]`. The naive `genType elem; *; name` would produce
        # `T[] *name`, which C parses as "array of pointers" — a type error
        # at the decl site, or worse, silently wrong.
        with var:
            inner = elem.copy()
        with into(inner):
            _genType(c, inner)
            while inner.hasMore(): skip(inner)
        c.add(_PredefinedToken.Space)
        c.add(_PredefinedToken.ParLe)
        if isCppRef: c.add(string("&"))
        else: c.add(_PredefinedToken.Star)
        _maybeAddName(c, name, isConst)
        c.add(_PredefinedToken.ParRi)
        c.add(_PredefinedToken.BracketLe)
        c.add(_PredefinedToken.BracketRi)
    else:
        _genType(c, elem)
        if isCppRef:
            c.add(string("&"))
        else:
            c.add(_PredefinedToken.Star)
        _maybeAddName(c, name, isConst)


def _genProcType(c: mut @ GeneratedCode, n: mut @ Cursor, name=string(""), isConst=False):
    with let:
        decl = takeProcType(n)
    with var:
        lastCallConv = CallConv.NoCallConv
    if kind(decl.pragmas) == NifKind.TagLit:
        with var:
            p = decl.pragmas.copy()
        with into(p):
            while p.hasMore():
                with let:
                    cc = callConvKind(p)
                if cc != CallConv.NoCallConv:
                    lastCallConv = cc
                skip(p)
    if lastCallConv != CallConv.NoCallConv:
        c.add(_callingConvToStr(lastCallConv))
        c.add(string("_PTR"))
        c.add(_PredefinedToken.ParLe)
        if kind(decl.returnType) == NifKind.DotToken:
            c.add(string("void"))
        else:
            with var:
                ret = decl.returnType.copy()
            _genType(c, ret)
        c.add(_PredefinedToken.Comma)
        with var:
            pragmas = decl.pragmas.copy()
        _genProcTypePragmas(c, pragmas)
        _maybeAddName(c, name, isConst)
        c.add(_PredefinedToken.ParRi)
    else:
        if kind(decl.returnType) == NifKind.DotToken:
            c.add(string("void"))
        else:
            with var:
                ret = decl.returnType.copy()
            _genType(c, ret)
        c.add(_PredefinedToken.Space)
        c.add(_PredefinedToken.ParLe)
        with var:
            pragmas = decl.pragmas.copy()
        _genProcTypePragmas(c, pragmas)
        c.add(_PredefinedToken.Star)  # "(*fn)"
        _maybeAddName(c, name, isConst)
        c.add(_PredefinedToken.ParRi)
    c.add(_PredefinedToken.ParLe)
    with var:
        i = nint(0)
    if kind(decl.params) == NifKind.TagLit:
        with var:
            p = decl.params.copy()
        with into(p):
            while p.hasMore():
                with var:
                    param = takeParamDecl(p)
                if i > 0: c.add(_PredefinedToken.Comma)
                _genType(c, param.typ)
                i += 1

    if i == 0:
        c.add(string("void"))
    c.add(_PredefinedToken.ParRi)


def _mangleSym(c: mut @ GeneratedCode, s: SymId) -> string:
    with let:
        x = getDeclOrNil(c._m, s)
    if not isNil(x) and x.extern != StrId(0):
        if x.kind == LengSym.ProcY and x.bareImport:
            # A bare-importc proc keeps its MANGLED C identifier; its prototype
            # carries an `__asm__` label binding it to the real symbol (see
            # `genProcDecl`). Using the libc identifier here would collide with a
            # header prototype whenever a splice moves the reference into a module
            # that includes that header.
            result = mangleToC(c._m.pool.symString(s))
        else:
            result = c._m.pool.strings[x.extern].copy()
    else:
        result = mangleToC(c._m.pool.symString(s))
    return result


def _genType(c: mut @ GeneratedCode, n: mut @ Cursor, name=string(""), isConst=False):
    match typeKind(n):
        case LengType.VoidT:
            _atom(c, string("void"), name, isConst)
            skip(n)
        case LengType.IT:
            _atomNumber(c, n, string("NI"), name, isConst)
        case LengType.UT:
            _atomNumber(c, n, string("NU"), name, isConst)
        case LengType.FT:
            _atomNumber(c, n, string("NF"), name, isConst)
        case LengType.BoolT:
            _atomNumber(c, n, string("NB8"), name, isConst)
        case LengType.CT:
            _atomNumber(c, n, string("NC"), name, isConst)
        case LengType.NoType:
            if kind(n) == NifKind.Symbol:
                _atom(c, _mangleSym(c, symId(n)), name, isConst)
                n.inc()
            else:
                _error(c._m, string("node is not a type: "), n)
        case LengType.PtrT | LengType.AptrT:
            _atomPointer(c, n, name, isConst)
        case LengType.FlexarrayT:
            with into(n):
                _genType(c, n)
                _maybeAddName(c, name, isConst)
                c.add(_PredefinedToken.BracketLe)
                c.add(_PredefinedToken.BracketRi)
                while n.hasMore(): skip(n)
        case LengType.ProctypeT:
            _genProcType(c, n, name, isConst)
        case LengType.VarargsT:
            c.add(string("..."))
        case LengType.ParamsT | LengType.UnionT | LengType.ObjectT | LengType.EnumT | LengType.ArrayT:
            _error(c._m, string("nominal type not allowed here: "), n)


def _mangleField(c: mut @ GeneratedCode, s: SymId, pragmas: Cursor, skipDecl: mut @ bool) -> string:
    if kind(pragmas) == NifKind.TagLit:
        with var:
            p = pragmas.copy()
        result = string("")
        with into(p):
            while p.hasMore():
                match pragmaKind(p):
                    case LengPragma.ImportcP | LengPragma.ImportcppP:
                        with let:
                            litId = externName(s, p)
                        result = c._m.pool.strings[litId].copy()  # but keep looping to detect HeaderP
                    case LengPragma.ExportcP:
                        with let:
                            litId = externName(s, p)
                        result = c._m.pool.strings[litId].copy()
                    case LengPragma.HeaderP | LengPragma.NodeclP:
                        skipDecl <<= True
                    case _:
                        pass
                skip(p)
        if result.len > 0: return result
    result = mangleToC(c._m.pool.symString(s))
    return result


def _mangleDecl(c: mut @ GeneratedCode, n: Cursor, pragmas: Cursor, skipDecl: mut @ bool) -> string:
    if kind(n) == NifKind.SymbolDef:
        result = _mangleField(c, symId(n), pragmas, skipDecl)
    else:
        result = string("InvalidFieldName")
        _error(c._m, string("declaration must have a SymbolDef, but got: "), n)
    return result


def _genObjectOrUnionBody(c: mut @ GeneratedCode, n: mut @ Cursor):
    with let:
        kind = typeKind(n)
    with into(n):
        if kind == LengType.ObjectT:
            if nifcoreparse.kind(n) == NifKind.DotToken:
                n.inc()
            elif nifcoreparse.kind(n) == NifKind.Symbol:
                _genType(c, n, string("Q"))
                c.add(_PredefinedToken.Semicolon)
            else:
                _error(c._m, string("expected `Symbol` or `.` for inheritance but got: "), n)

        while n.hasMore():
            match nifcoreparse.kind(n):
                case NifKind.TagLit:
                    if substructureKind(n) == LengOther.FldU:
                        with var:
                            decl = takeFieldDecl(n)
                            skipDecl = nbool(False)
                        with let:
                            f = _mangleDecl(c, decl.name, decl.pragmas, skipDecl)
                        if not skipDecl:
                            with var:
                                bits = i64(0)
                            _genFieldPragmas(c, decl.pragmas, bits)
                            _genType(c, decl.typ, f)
                            if bits > 0:
                                c.add(string(" : "))
                                c.add(str(bits))
                            c.add(_PredefinedToken.Semicolon)
                    elif typeKind(n) == LengType.ObjectT:
                        c.add(_PredefinedToken.AnonStruct)
                        c.add(_PredefinedToken.CurlyLe)
                        _genObjectOrUnionBody(c, n)  # recurse; consumes the anon scope
                        c.add(_PredefinedToken.CurlyRi)
                        c.add(_PredefinedToken.Semicolon)
                    elif typeKind(n) == LengType.UnionT:
                        c.add(_PredefinedToken.AnonUnion)
                        c.add(_PredefinedToken.CurlyLe)
                        _genObjectOrUnionBody(c, n)
                        c.add(_PredefinedToken.CurlyRi)
                        c.add(_PredefinedToken.Semicolon)
                    elif isUnionBranch(n):
                        # A discriminated-union branch. C has no variant concept, so the
                        # `(ranges ...)` are ignored and only the payload is emitted - the
                        # same anonymous struct this branch produced before the branches
                        # were tagged. A field-less branch emits nothing, as before.
                        with let:
                            b = asUnionBranch(n)
                        if typeKind(b.body) == LengType.ObjectT:
                            with var:
                                body = b.body.copy()
                            c.add(_PredefinedToken.AnonStruct)
                            c.add(_PredefinedToken.CurlyLe)
                            _genObjectOrUnionBody(c, body)
                            c.add(_PredefinedToken.CurlyRi)
                            c.add(_PredefinedToken.Semicolon)
                        skip(n)
                    else:
                        _error(c._m, string("expected `fld` but got: "), n)
                        skip(n)
                case _:
                    _error(c._m, string("expected `fld` but got: "), n)
                    n.inc()


def _genEnumDecl(c: mut @ GeneratedCode, n: mut @ Cursor, name: string):
    # (efld SymbolDef Expr)
    # EnumDecl ::= (enum Type EnumFieldDecl+)
    with into(n):
        c.add(_PredefinedToken.TypedefKeyword)
        with let:
            baseType = n.copy()
        _genType(c, n)
        c.add(_PredefinedToken.Space)
        c.add(name)
        c.add(_PredefinedToken.Semicolon)
        c.add(_PredefinedToken.NewLine)

        while n.hasMore():
            if substructureKind(n) == LengOther.EfldU:
                with into(n):
                    if kind(n) == NifKind.SymbolDef:
                        with let:
                            enumFieldName = mangleToC(c._m.pool.symString(symId(n)))
                        n.inc()
                        c.add(string("#define "))
                        c.add(enumFieldName)
                        c.add(_PredefinedToken.Space)
                        c.add(_PredefinedToken.ParLe)
                        c.add(_PredefinedToken.ParLe)
                        with var:
                            base = baseType.copy()
                        _genType(c, base)
                        c.add(_PredefinedToken.ParRi)
                        match kind(n):
                            case NifKind.IntLit:
                                c._genIntLit(intVal(n))
                                n.inc()
                            case NifKind.UIntLit:
                                c._genUIntLit(uintVal(n))
                                n.inc()
                            case _:
                                _error(c._m, string("expected `Number` but got: "), n)
                        c.add(_PredefinedToken.ParRi)
                        c.add(_PredefinedToken.NewLine)
                    else:
                        _error(c._m, string("expected `SymbolDef` but got: "), n)
                    while n.hasMore(): skip(n)
            else:
                _error(c._m, string("expected `efld` but got: "), n)
                skip(n)  # avoid infinite loop on unexpected input


def _parseTypePragmas(c: mut @ GeneratedCode, n: Cursor) -> Tset[LengPragma]:
    result = Tset[LengPragma]()
    with var:
        n = n.copy()
    if substructureKind(n) == LengOther.PragmasU:
        for _ in loopInto(n):
            with let:
                pk = pragmaKind(n)
            match pk:
                case LengPragma.PackedP | LengPragma.ImportcP | LengPragma.ImportcppP | LengPragma.NodeclP:
                    result.incl(pk)
                    skip(n)
                case LengPragma.HeaderP:
                    with into(n):
                        if kind(n) != NifKind.StrLit:
                            _error(c._m, string("expected string literal in header pragma but got: "), n)
                        else:
                            c._inclHeader(_litId(n))
                            n.inc()
                        while n.hasMore(): skip(n)
                case LengPragma.ExportcP:
                    skip(n)
                case _:
                    _error(c._m, string("got unexpected type pragma: "), n)
    elif kind(n) != NifKind.DotToken:
        _error(c._m, string("expected type pragmas but got: "), n)
    return result


def _generateTypes(c: mut @ GeneratedCode, o: _TypeOrder):
    for (d, declKeyword) in o._forwardedDecls._s:
        with var:
            n = d.copy()
        with let:
            decl = takeTypeDecl(n)
        with var:
            skipDecl = nbool(False)
        with let:
            s = _mangleDecl(c, decl.name, decl.pragmas, skipDecl)
        if not skipDecl:
            c.add(declKeyword)
            c.add(s)
            c.add(_PredefinedToken.Space)
            c.add(s)
            c.add(_PredefinedToken.Semicolon)
        else:
            # do not miss a `.header` pragma:
            _ = _parseTypePragmas(c, decl.pragmas)

    for (d, declKeyword) in o._ordered._s:
        with var:
            n = d.copy()
            decl = takeTypeDecl(n)
        if not c._generatedTypes.containsOrIncl(symId(decl.name)):
            with var:
                skipDecl = nbool(False)
            with let:
                s = _mangleDecl(c, decl.name, decl.pragmas, skipDecl)
            if skipDecl:
                # do not miss a `.header` pragma:
                _ = _parseTypePragmas(c, decl.pragmas)
                continue
            match typeKind(decl.body):
                case LengType.ArrayT:
                    c.add(declKeyword)
                    c.add(s)
                    c.add(_PredefinedToken.CurlyLe)
                    with var:
                        n = _firstSon(decl.body)
                    _genType(c, n, string("a"))
                    c.add(_PredefinedToken.BracketLe)
                    match kind(n):
                        case NifKind.IntLit: c._genIntLit(intVal(n))
                        case NifKind.UIntLit: c._genUIntLit(uintVal(n))
                        case _: _error(c._m, string("array size must be an int literal, but got: "), n)
                    c.add(_PredefinedToken.BracketRi)
                    c.add(_PredefinedToken.Semicolon)
                    c.add(_PredefinedToken.CurlyRi)
                    c.add(s)
                    c.add(_PredefinedToken.Semicolon)
                case LengType.EnumT:
                    _genEnumDecl(c, decl.body, s)
                case LengType.ProctypeT:
                    c.add(_PredefinedToken.TypedefKeyword)
                    _genType(c, decl.body, s)
                    c.add(_PredefinedToken.Semicolon)
                case _:
                    with let:
                        prag = _parseTypePragmas(c, decl.pragmas)
                    c.add(declKeyword)
                    if LengPragma.PackedP in prag:
                        # `alignas` is in C23 standard but `alignas(1)` doesn't reduce minimum alignment and
                        # work like `packed` attribute.
                        # `[[gnu::packed]]` is not supported by MSVC and old GCC/Clang.
                        # `#pragma pack(push, 1)` is supported by GCC, Clang and MSVC, but a not in C standard
                        # and `aligned (x)` attribute in struct fields are ignored.
                        # `__attribute__ ((__packed__))` is not supported by MSVC.
                        c.add(string("__attribute__ ((__packed__)) "))
                    c.add(s)
                    c.add(_PredefinedToken.CurlyLe)
                    # XXX generate attributes and pragmas here
                    _genObjectOrUnionBody(c, decl.body)
                    c.add(_PredefinedToken.CurlyRi)
                    c.add(s)
                    c.add(_PredefinedToken.Semicolon)
