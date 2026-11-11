# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/genexprs.nim
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

from __future__ import annotations
from nimic.ntypes import *


def _genx(c: mut @ GeneratedCode, n: mut @ Cursor):
    pass


def _typedBinOp(c: mut @ GeneratedCode, n: mut @ Cursor, opr: string):
    with into(n):
        c.add(_PredefinedToken.ParLe)
        c.add(_PredefinedToken.ParLe)
        _genType(c, n)
        c.add(_PredefinedToken.ParRi)
        c.add(_PredefinedToken.ParLe)
        _genx(c, n)
        c.add(opr)
        _genx(c, n)
        c.add(_PredefinedToken.ParRi)
        c.add(_PredefinedToken.ParRi)
        while n.hasMore(): skip(n)


def _cmpOp(c: mut @ GeneratedCode, n: mut @ Cursor, opr: string):
    with into(n):
        c.add(_PredefinedToken.ParLe)
        _genx(c, n)
        c.add(opr)
        _genx(c, n)
        c.add(_PredefinedToken.ParRi)
        while n.hasMore(): skip(n)


def _unOp(c: mut @ GeneratedCode, n: mut @ Cursor, opr: string):
    with into(n):
        c.add(_PredefinedToken.ParLe)
        c.add(opr)
        _genx(c, n)
        c.add(_PredefinedToken.ParRi)
        while n.hasMore(): skip(n)


def _typedUnOp(c: mut @ GeneratedCode, n: mut @ Cursor, opr: string):
    with into(n):
        c.add(_PredefinedToken.ParLe)
        c.add(_PredefinedToken.ParLe)
        _genType(c, n)
        c.add(_PredefinedToken.ParRi)
        c.add(opr)
        # a negative literal operand -- `abs(-3.0)` once the inliner substitutes
        # the constant into `-y` -- must not glue onto `-` as C's `--`
        if opr == "-":
            c.add(string(" "))
        _genx(c, n)
        c.add(_PredefinedToken.ParRi)
        while n.hasMore(): skip(n)


def _genCall(c: mut @ GeneratedCode, n: mut @ Cursor):
    c._genCLineDir(_info(n))
    with into(n):
        with let:
            isCfn = isImportC(c._m, n)
        _genx(c, n)
        c.add(_PredefinedToken.ParLe)
        with var:
            i = nint(0)
        while n.hasMore():
            if i > 0: c.add(_PredefinedToken.Comma)
            if isCfn:
                c._flags.incl(GenFlag.gfInCallImportC)
            _genx(c, n)
            i += 1
        c.add(_PredefinedToken.ParRi)


def _intrinsicOfCallee(c: mut @ GeneratedCode, callee: Cursor, bits: mut @ nint) -> IntrinsicOp:
    """{.inline.}"""
    return intrinsicOfCallee(c._m, callee, bits)


def _genInstr(c: mut @ GeneratedCode, n: mut @ Cursor):
    ## `(instr SYM X*)` — an intrinsic application. Selection-final: the opcode
    ## the source named is the one emitted, so this never falls back to a call.
    c._genCLineDir(_info(n))
    with let:
        start = n.copy()
    with into(n):
        with var:
            bits = nint(0)
        with let:
            op = _intrinsicOfCallee(c, n, bits)
        if op == IntrinsicOp.VolatileLoadOp or op == IntrinsicOp.VolatileStoreOp:
            # NB: no early `return` from inside `n.into:` — its epilogue drains the
            # scope, and skipping that left the statement generator closing a brace it
            # had not opened.
            # Not a builtin call: C spells a volatile access as a CAST, which is also
            # how Nim's own `std/volatile` emits it. `__typeof__` keeps this free of any
            # type rendering — the pointee's type is whatever the operand already has,
            # and naming it again is a chance to name it differently.
            #
            # An assignment is an expression in C, so the store needs no separate
            # statement form and both arms compose wherever `(instr …)` may appear.
            skip(n)  # the callee symbol
            c.add(_PredefinedToken.ParLe)
            c.add(string("*(volatile __typeof__(*("))
            with var:
                p0 = n.copy()
            _genx(c, p0)
            c.add(string(")) *)("))
            _genx(c, n)  # the pointer operand
            c.add(string(")"))
            c.add(_PredefinedToken.ParRi)
            if op == IntrinsicOp.VolatileStoreOp:
                c.add(string(" = "))
                c.add(_PredefinedToken.ParLe)
                _genx(c, n)  # the value
                c.add(_PredefinedToken.ParRi)
            while n.hasMore(): skip(n)
        else:
            with var:
                builtin = string("")
            if op == IntrinsicOp.NoIntrinsicOp:
                _error(c._m, string("callee of (instr ...) carries no instruction/intrinsic pragma: "), start)
            else:
                builtin = cBuiltinFor(op, bits)
                if builtin.len == 0:
                    with let:
                        row = IntrinsicRows[op]
                    if row.isFlagRead() or row.isFlagWrite() or row.isAssemblerOnly():
                        # No portable form exists or ever will: C has no notion of a condition
                        # code, and what makes a flag usable at all — that nothing runs between
                        # its definition and its read — is exactly what a C compiler will not
                        # promise. Say that, rather than suggesting `{.intrinsic.}`.
                        _errorAt(c._m, string("`") + IntrinsicNames[op] + string("` is a machine flag ") + string("instruction; C has no condition codes, so it is only available ") + string("inside an `{.assembler.}` proc compiled by arkham"), start)
                    elif row.inoutOperand() >= 0:
                        # A two-address row. C has no destructive-operand form, and suggesting
                        # `{.intrinsic.}` would be wrong advice: the portable spelling of
                        # `add(d, s)` is not another intrinsic, it is `d = d + s`.
                        _errorAt(c._m, string("`") + IntrinsicNames[op] + string("` is a two-address machine ") + string("instruction; C has no such form, so write `d = d ") + string("<op> s` for the portable path or guard the call with a `when`"), start)
                    else:
                        _error(c._m, string("the C backend has no lowering for the target-pinned instruction `") + IntrinsicNames[op] + string("`; use the portable `{.intrinsic: ....}` form ") + string("or guard the call with a `when`: "), start)
            c.add(builtin)
            skip(n)  # the callee symbol
            c.add(_PredefinedToken.ParLe)
            with var:
                i = nint(0)
            while n.hasMore():
                if i > 0: c.add(_PredefinedToken.Comma)
                _genx(c, n)
                i += 1
            c.add(_PredefinedToken.ParRi)


def _genCallCanRaise(c: mut @ GeneratedCode, n: mut @ Cursor):
    c._genCLineDir(_info(n))
    with into(n):
        skip(n)  # skip error action
        with let:
            isCfn = isImportC(c._m, n)
        _genx(c, n)
        c.add(_PredefinedToken.ParLe)
        with var:
            i = nint(0)
        while n.hasMore():
            if i > 0: c.add(_PredefinedToken.Comma)
            if isCfn:
                c._flags.incl(GenFlag.gfInCallImportC)
            _genx(c, n)
            i += 1
        c.add(_PredefinedToken.ParRi)


def _genDeref(c: mut @ GeneratedCode, n: mut @ Cursor):
    with into(n):
        c.add(_PredefinedToken.ParLe)
        with let:
            starAt = c._code.len
        c.add(string("*"))
        # `*NIM_NIL` is a dereference of `void*` and `(*NIM_NIL).f` does not even
        # compile. The dereference is dead code — the intra-module inliner
        # substitutes a literal argument at every use, including uses under a
        # guard it could not fold — but it still has to be *emitted*, so give the
        # null the pointer type the frontend attached to it. See nimony#2317.
        if exprKind(n) == LengExpr.NilC and childCursor(n).hasMore():
            with var:
                t = childCursor(n)
            c.add(_PredefinedToken.ParLe)
            c.add(_PredefinedToken.ParLe)
            _genType(c, t)
            c.add(_PredefinedToken.ParRi)
            c.add(_PredefinedToken.NullPtr)
            c.add(_PredefinedToken.ParRi)
            skip(n)
        else:
            _genx(c, n)
        c.add(_PredefinedToken.ParRi)
        if n.hasMore() and typeQual(n) == LengTypeQualifier.CpprefQ:
            if c._m.config.backend == Backend.backendCpp:
                c._code[starAt] = _Token(_PredefinedToken.EmptyToken)
            skip(n)
        while n.hasMore(): skip(n)


def _genField(c: mut @ GeneratedCode, fld: Cursor, objBody: Cursor, objTypeIsImported: bool):
    if kind(fld) == NifKind.Symbol:
        with let:
            s = symId(fld)
        with var:
            t = objBody.copy()
        with let:
            pragmas = typeOfField(c._m, t, s, FieldSelector.FieldPragmas)
        if not pragmas.cursorIsNil() and kind(pragmas) == NifKind.TagLit:
            with var:
                p = pragmas.copy()
            for _ in into(p):
                while p.hasMore():
                    match pragmaKind(p):
                        case LengPragma.ImportcP | LengPragma.ImportcppP | LengPragma.ExportcP:
                            with let:
                                litId = externName(s, p)
                                name = c._m.pool.strings[litId].copy()
                            c.add(name)
                            return
                        case _:
                            pass
                    skip(p)
        if objTypeIsImported:
            c.add(c._m.pool.symBasename(s))
        else:
            c.add(mangleToC(c._m.pool.symString(s)))
    else:
        _error(c._m, string("expected field name but got: "), fld)


def _isImportedArray(c: mut @ GeneratedCode, n: Cursor) -> bool:
    if exprKind(n) == LengExpr.DotC:
        with let:
            nn = _firstSon(n)
        with var:
            objType = getNominalType(c._m, nn)
        result = isImportC(c._m, objType)
    else:
        result = False
    return result


@template_expand
def _genLvalue(c: mut @ GeneratedCode, n: mut @ Cursor):
    match exprKind(n):
        case LengExpr.NoExpr:
            if kind(n) == NifKind.Symbol:
                c._requestedSyms.incl(symId(n))
                with let:
                    name = _mangleSym(c, symId(n))
                c.add(name)
                n.inc()
            else:
                _error(c._m, string("expected expression but got: "), n)
        case LengExpr.DerefC: _genDeref(c, n)
        case LengExpr.AtC:
            with into(n):
                with let:
                    needsAwrapper = not _isImportedArray(c, n)
                _genx(c, n)
                if needsAwrapper:
                    c.add(_PredefinedToken.Dot)
                    c.add(string("a"))
                c.add(_PredefinedToken.BracketLe)
                _genx(c, n)
                c.add(_PredefinedToken.BracketRi)
                while n.hasMore(): skip(n)
        case LengExpr.PatC:
            with into(n):
                _genx(c, n)
                c.add(_PredefinedToken.BracketLe)
                _genx(c, n)
                c.add(_PredefinedToken.BracketRi)
                while n.hasMore(): skip(n)
        case LengExpr.DotC:
            with into(n):
                with let:
                    objType = getNominalType(c._m, n)
                    objBody = navigateToObjectBody(c._m, objType)
                _genx(c, n)
                with var:
                    fld = n.copy()
                skip(n)
                if n.hasMore() and kind(n) == NifKind.IntLit:
                    with var:
                        inh = nint(intVal(n))
                    n.inc()
                    while inh > 0:
                        c.add(string(".Q"))
                        inh -= 1
                c.add(_PredefinedToken.Dot)
                _genField(c, fld, objBody, isImportC(c._m, objType))
                while n.hasMore(): skip(n)
        case LengExpr.ErrvC:
            if Tset[GenFlag](GenFlag.gfMainModule, GenFlag.gfHasError) * c._flags == Tset[GenFlag]():
                with _moveToDataSection():
                    c.add(_PredefinedToken.ExternKeyword)
                    c.add(_PredefinedToken.ThreadVarToken)
                    c.add(string("NB8 "))
                    c.add(_PredefinedToken.ErrToken)
                    c.add(_PredefinedToken.Semicolon)
                c._flags.incl(GenFlag.gfHasError)
            c.add(_PredefinedToken.ErrToken)
            skip(n)
        case LengExpr.OvfC:
            c.add(_PredefinedToken.OvfToken)
            c._currentProc._needsOverflowFlag = True
            skip(n)
        case _:
            _error(c._m, string("expected expression but got: "), n)


def _objConstrType(c: mut @ GeneratedCode, n: mut @ Cursor):
    # C99 is strange, it requires (T){} for struct construction but not for
    # consts.
    if c._objConstrNeedsType:
        c.add(_PredefinedToken.ParLe)
        _genType(c, n)
        c.add(_PredefinedToken.ParRi)
    else:
        skip(n)


def _suffixToType(c: mut @ GeneratedCode, suffix: Cursor):
    match c._m.pool.strings[_litId(suffix)]:
        case "i64":
            c.add(string("NI64"))
        case "i32":
            c.add(string("NI32"))
        case "i16":
            c.add(string("NI16"))
        case "i8":
            c.add(string("NI8"))
        case "u64":
            c.add(string("NU64"))
        case "u32":
            c.add(string("NU32"))
        case "u16":
            c.add(string("NU16"))
        case "u8":
            c.add(string("NU8"))
        case "f64":
            c.add(string("NF64"))
        case "f32":
            c.add(string("NF32"))
        case _:
            # TODO: f128?
            quit(string("unsupported suffix"))


def _suffixConv(c: mut @ GeneratedCode, value: Cursor, suffix: Cursor):
    c.add(_PredefinedToken.ParLe)
    c.add(_PredefinedToken.ParLe)
    _suffixToType(c, suffix)
    c.add(_PredefinedToken.ParRi)
    with var:
        value = value.copy()
    _genx(c, value)
    c.add(_PredefinedToken.ParRi)


def _genAddr(c: mut @ GeneratedCode, n: mut @ Cursor):
    # If we take the address of an array expression, add the `.a` field access.
    with let:
        inCallImportC = GenFlag.gfInCallImportC in c._flags
    with into(n):
        with let:
            needsAwrapper = not _isImportedArray(c, n)
            arrType = getType(c._m, n)
        c.add(_PredefinedToken.ParLe)
        with let:
            ampAt = c._code.len
        c.add(string("&"))
        _genx(c, n)
        if typeKind(arrType) == LengType.ArrayT and needsAwrapper and inCallImportC:
            c.add(string(".a[0]"))
        c.add(_PredefinedToken.ParRi)
        if n.hasMore() and typeQual(n) == LengTypeQualifier.CpprefQ:
            if c._m.config.backend == Backend.backendCpp:
                c._code[ampAt] = _Token(_PredefinedToken.EmptyToken)
            skip(n)
        while n.hasMore(): skip(n)


def _genCond(c: mut @ GeneratedCode, n: mut @ Cursor):
    # Special cased so that we do not end up with `if ((a == b))` which
    # produced warnings.
    match exprKind(n):
        case LengExpr.EqC: _cmpOp(c, n, string(" == "))
        case LengExpr.NeqC: _cmpOp(c, n, string(" != "))
        case LengExpr.LeC: _cmpOp(c, n, string(" <= "))
        case LengExpr.LtC: _cmpOp(c, n, string(" < "))
        case _:
            c.add(_PredefinedToken.ParLe)
            _genx(c, n)
            c.add(_PredefinedToken.ParRi)


def _genx(c: mut @ GeneratedCode, n: mut @ Cursor):
    if exprKind(n) not in AddrKinds and kind(n) != NifKind.StrLit:
        c._flags.excl(GenFlag.gfInCallImportC)
    match exprKind(n):
        case LengExpr.NoExpr:
            match kind(n):
                case NifKind.IntLit:
                    c._genIntLit(intVal(n))
                    n.inc()
                case NifKind.UIntLit:
                    c._genUIntLit(uintVal(n))
                    n.inc()
                case NifKind.FloatLit:
                    c.add(str(floatVal(n)))
                    n.inc()
                case NifKind.CharLit:
                    with let:
                        ch = charLit(n)
                    c.add(string("(NC8)"))
                    with var:
                        s = string("'")
                    toCChar(ch, s)
                    s.add(string("'"))
                    c.add(s)
                    n.inc()
                case NifKind.StrLit:
                    # The cast and the literal must be emitted as ONE parenthesized unit.
                    # C's postfix operators bind tighter than a cast, so an unwrapped
                    # `(NC8*)"lit"` that a caller then subscripts yields
                    # `(NC8*)"lit"[i]` = `(NC8*)("lit"[i])` — a char cast to a pointer,
                    # not the i-th char of the string. The subscript emitters (AtC/PatC)
                    # and DotC append directly to whatever `genx` produced, so making the
                    # literal self-parenthesizing here fixes every one of those call
                    # sites at once. Same shape `suffixConv` above already uses for its
                    # own cast. Reached in practice by inlining a string-literal argument
                    # into a `cstring` parameter that is indexed (only at --opt:speed,
                    # since without inlining the parameter stays a variable).
                    if GenFlag.gfInCallImportC not in c._flags and GenFlag.gfInFlexArray not in c._flags:
                        c.add(_PredefinedToken.ParLe)
                        c.add(string("(NC8*)"))
                        c.add(makeCString(c._m.pool.strings[_litId(n)]))
                        c.add(_PredefinedToken.ParRi)
                    else:
                        # No cast emitted in these contexts, so there is nothing for a
                        # postfix operator to bind past — and a bare literal is what an
                        # importC call / flexible-array initializer expects.
                        c.add(makeCString(c._m.pool.strings[_litId(n)]))
                    n.inc()
                case _:
                    _genLvalue(c, n)
        case LengExpr.FalseC:
            c.add(string("NIM_FALSE"))
            skip(n)
        case LengExpr.TrueC:
            c.add(string("NIM_TRUE"))
            skip(n)
        case LengExpr.NilC:
            # A bare `NIM_NIL`, NOT a cast to the `(nil T)` type the frontend attaches.
            # `NIM_NIL` is assignment-compatible with every pointer type, and casting
            # would make an `{.importc.}` signature whose C spelling differs from
            # Nimony's (`cstring` is `unsigned char*`, `strtod` wants `char**`) a hard
            # `-Wincompatible-pointer-types` error. `genDeref` casts where C insists on
            # knowing the pointee.
            c.add(_PredefinedToken.NullPtr)
            skip(n)
        case LengExpr.InfC:
            c.add(string("INF"))
            skip(n)
        case LengExpr.NeginfC:
            c.add(string("-INF"))
            skip(n)
        case LengExpr.NanC:
            c.add(string("NAN"))
            skip(n)
        case LengExpr.AconstrC:
            with into(n):
                with let:
                    isUncheckedArray = typeKind(n) in Tset[LengType](LengType.PtrT, LengType.AptrT, LengType.FlexarrayT)
                _objConstrType(c, n)
                c.add(_PredefinedToken.CurlyLe)
                if not isUncheckedArray:
                    c.add(string(".a = "))
                    c.add(_PredefinedToken.CurlyLe)
                with var:
                    i = nint(0)
                while n.hasMore():
                    if i > 0: c.add(_PredefinedToken.Comma)
                    _genx(c, n)
                    i += 1
                if not isUncheckedArray:
                    c.add(_PredefinedToken.CurlyRi)
                c.add(_PredefinedToken.CurlyRi)
        case LengExpr.OconstrC:
            with into(n):
                with let:
                    objType = n.copy()
                    objBody = navigateToObjectBody(c._m, n)
                _objConstrType(c, n)
                c.add(_PredefinedToken.CurlyLe)
                with var:
                    i = nint(0)
                while n.hasMore():
                    if i > 0: c.add(_PredefinedToken.Comma)
                    if substructureKind(n) == LengOther.KvU:
                        with into(n):
                            c.add(_PredefinedToken.Dot)
                            with var:
                                depth = n.copy()
                            skip(depth)
                            skip(depth)
                            if depth.hasMore() and depth.hasMore():
                                # inheritance depth
                                assert kind(depth) == NifKind.IntLit
                                with let:
                                    d = intVal(depth)
                                for _ in range(d):
                                    c.add(string("Q"))
                                    c.add(_PredefinedToken.Dot)
                            with let:
                                fldSym = symId(n) if kind(n) == NifKind.Symbol else SymId(0)
                            _genField(c, n, objBody, isImportC(c._m, objType))
                            n.inc()
                            c.add(_PredefinedToken.AsgnOpr)
                            # For flexible array member fields, suppress the (NC8*) cast on string literals
                            with var:
                                fldBody = objBody.copy()
                            with let:
                                fldType = typeOfField(c._m, fldBody, fldSym) if fldSym != SymId(0) else default(Cursor)
                                isFlexArr = not fldType.cursorIsNil() and typeKind(fldType) == LengType.FlexarrayT
                            if isFlexArr: c._flags.incl(GenFlag.gfInFlexArray)
                            _genx(c, n)
                            if isFlexArr: c._flags.excl(GenFlag.gfInFlexArray)
                            while n.hasMore(): skip(n)
                    elif exprKind(n) == LengExpr.OconstrC:
                        # inheritance
                        c.add(_PredefinedToken.Dot)
                        c.add(string("Q"))
                        c.add(_PredefinedToken.AsgnOpr)
                        _genx(c, n)
                    else:
                        _genx(c, n)
                    i += 1
                c.add(_PredefinedToken.CurlyRi)
        case LengExpr.BaseobjC:
            with into(n):
                skip(n)  # type not interesting for us
                with var:
                    counter = nint(intVal(n))
                skip(n)
                _genx(c, n)
                while counter > 0:
                    c.add(string(".Q"))
                    counter -= 1
                while n.hasMore(): skip(n)
        case LengExpr.ParC:
            c.add(_PredefinedToken.ParLe)
            with into(n):
                _genx(c, n)
                c.add(_PredefinedToken.ParRi)
                while n.hasMore(): skip(n)
        case LengExpr.AddrC | LengExpr.HaddrC:
            # C has one `&`: a hidden address is the same `&x`, only the REASON differs
            # (see `nifcdecl.AddrKinds`), and C has nowhere to put the reason.
            _genAddr(c, n)
            c._flags.excl(GenFlag.gfInCallImportC)
        case LengExpr.SizeofC:
            c.add(string("sizeof"))
            c.add(_PredefinedToken.ParLe)
            with into(n):
                _genType(c, n)
                c.add(_PredefinedToken.ParRi)
                while n.hasMore(): skip(n)
        case LengExpr.AlignofC:
            c.add(string("NIM_ALIGNOF"))
            c.add(_PredefinedToken.ParLe)
            with into(n):
                _genType(c, n)
                c.add(_PredefinedToken.ParRi)
                while n.hasMore(): skip(n)
        case LengExpr.OffsetofC:
            with into(n):
                c.add(string("offsetof"))
                c.add(_PredefinedToken.ParLe)
                _genType(c, n)
                c.add(_PredefinedToken.Comma)
                with let:
                    name = _mangleSym(c, symId(n))
                n.inc()
                c.add(name)
                c.add(_PredefinedToken.ParRi)
                while n.hasMore(): skip(n)
        case LengExpr.CallC: _genCall(c, n)
        case LengExpr.InstrC: _genInstr(c, n)
        case LengExpr.AddC: _typedBinOp(c, n, string(" + "))
        case LengExpr.SubC: _typedBinOp(c, n, string(" - "))
        case LengExpr.MulC: _typedBinOp(c, n, string(" * "))
        case LengExpr.DivC: _typedBinOp(c, n, string(" / "))
        case LengExpr.ModC: _typedBinOp(c, n, string(" % "))
        case LengExpr.ShlC: _typedBinOp(c, n, string(" << "))
        case LengExpr.ShrC: _typedBinOp(c, n, string(" >> "))
        case LengExpr.BitandC: _typedBinOp(c, n, string(" & "))
        case LengExpr.BitorC: _typedBinOp(c, n, string(" | "))
        case LengExpr.BitxorC: _typedBinOp(c, n, string(" ^ "))
        case LengExpr.BitnotC: _typedUnOp(c, n, string(" ~ "))
        case LengExpr.AndC: _cmpOp(c, n, string(" && "))
        case LengExpr.OrC: _cmpOp(c, n, string(" || "))
        case LengExpr.NotC: _unOp(c, n, string("!"))
        case LengExpr.NegC: _typedUnOp(c, n, string("-"))
        case LengExpr.EqC: _cmpOp(c, n, string(" == "))
        case LengExpr.NeqC: _cmpOp(c, n, string(" != "))
        case LengExpr.LeC: _cmpOp(c, n, string(" <= "))
        case LengExpr.LtC: _cmpOp(c, n, string(" < "))
        case LengExpr.CastC: _typedUnOp(c, n, string(""))
        case LengExpr.ConvC: _typedUnOp(c, n, string(""))
        case LengExpr.SufC:
            with var:
                value = Cursor()
                suffix = Cursor()
            with into(n):
                value = n.copy()
                skip(n)
                suffix = n.copy()
                skip(n)
                while n.hasMore(): skip(n)
            if kind(value) == NifKind.StrLit:
                _genx(c, value)
            else:
                _suffixConv(c, value, suffix)
        case LengExpr.ErrvC | LengExpr.AtC | LengExpr.DerefC | LengExpr.DotC | LengExpr.PatC | LengExpr.OvfC:
            _genLvalue(c, n)
