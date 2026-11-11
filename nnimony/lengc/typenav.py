# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/typenav.nim
# ///
#
#
#        Lengc type navigator — nifcore port
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## A type navigator that recomputes the type of a Leng expression, over
## **nifcore** cursors. This is the nifcore port of `lengc/typenav.nim`: same
## algorithm, same shared `models/leng_tags` enums, but built on `nifcoreparse`
## / `nifcdecl` and the nifcore `MainModule` (`shoggoth/nifmodules`) so symbol
## resolution is fully cross-module — `MainModule.getDeclOrNil` lazily loads
## foreign declarations on demand.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import assertions, tables
from ..lib.nifcoreparse import (
    addSubtree, createTokenBuf, Cursor, intVal, kind, NifKind, parseFromBuffer, strId, strVal, sub, SymId,
    symId, TagId)  # re-exports nifcore + parseFromBuffer
from ..lib.nifcdecl import (
    asTypeDecl, exprKind, inc, into, isUnionBranch, LengExpr, LengOther, LengPragma, LengStmt, LengSym,
    LengType, loopInto, pragmaKind, skip, stmtKind, substructureKind, symKind, takeFieldDecl, takeParamDecl,
    takeUnionBranch, typeKind)  # stmtKind/exprKind/typeKind, tag enums
from ..models.tags import TagEnum  # *TagId ordinals for synthesis
from .nifmodules import getDeclOrNil, MainModule  # MainModule, getDeclOrNil
from ..lib.intrinsics import IntrinsicClass, IntrinsicOp, intrinsicOpByName  # the shared `{.instruction.}` row table
from ..lib import intrinsics
export(intrinsics)  # `intrinsicOfCallee` returns an `IntrinsicOp`, so every
                    # importer needs the enum and the row table with it


def _firstChild(c: Cursor) -> Cursor:
    """{.inline.}"""
    result = c.copy()
    result.inc()
    return result


def intrinsicOfCallee(m: mut @ MainModule, callee: Cursor, bits: mut @ nint) -> IntrinsicOp:
    ## The opcode a `(instr SYM …)` names, plus the width its row bound (taken
    ## from the declared first operand). Reads the `(instruction X)` /
    ## `(intrinsic X)` pragma off the callee's declaration — a table lookup on an
    ## ident, not a match against a C name. Shared by both Leng back ends: the
    ## C one keys its `__builtin_*` choice off it and the LLVM one reuses that
    ## same choice, so neither re-derives the row from the declaration itself.
    result = IntrinsicOp.NoIntrinsicOp
    bits <<= 0
    if kind(callee) != NifKind.Symbol: return result
    with let:
        d = getDeclOrNil(m, symId(callee))
    if isNil(d) or d.kind != LengSym.ProcY: return result
    with var:
        n = d.pos.copy()
    with into(n):
        n.inc()  # name
        if typeKind(n) == LengType.ParamsT:  # first param's type → the width
            with var:
                p = n.copy()
            for _ in loopInto(p):
                if substructureKind(p) == LengOther.ParamU and bits == 0:
                    with let:
                        pd = takeParamDecl(p)
                    if kind(pd.typ) == NifKind.TagLit and typeKind(pd.typ) in Tset[LengType](LengType.IT, LengType.UT, LengType.CT, LengType.FT):
                        with var:
                            b = pd.typ.copy()
                        b.inc()
                        if kind(b) == NifKind.IntLit: bits <<= nint(intVal(b))
                else:
                    skip(p)
        skip(n)  # params
        skip(n)  # return type
        if substructureKind(n) == LengOther.PragmasU:
            with var:
                p = n.copy()
            for _ in loopInto(p):
                with let:
                    pk = pragmaKind(p)
                if pk in Tset[LengPragma](LengPragma.InstructionP, LengPragma.IntrinsicP):
                    with var:
                        a = p
                    a = sub(a)
                    if kind(a) == NifKind.StrLit:
                        result = intrinsicOpByName(m.pool.strings[strId(a)], (IntrinsicClass.icPinned if pk == LengPragma.InstructionP else IntrinsicClass.icPortable))
                skip(p)
        while n.hasMore(): skip(n)
    return result


def cBuiltinFor(op: IntrinsicOp, bits: nint) -> string:
    ## The C name a *portable* opcode lowers to: a GCC/clang builtin, or — for the
    ## one row whose spelling is the C compiler's target to choose — a prelude
    ## macro. Target-pinned rows have no portable C spelling by construction and
    ## return "" — the C backend rejects them rather than guessing an equivalent.
    match op:
        case IntrinsicOp.CtzOp: return (string("__builtin_ctz") if bits <= 32 else string("__builtin_ctzll"))
        case IntrinsicOp.ClzOp: return (string("__builtin_clz") if bits <= 32 else string("__builtin_clzll"))
        case IntrinsicOp.PopcountOp: return (string("__builtin_popcount") if bits <= 32 else string("__builtin_popcountll"))
        case IntrinsicOp.BswapOp:
            if bits <= 16: return string("__builtin_bswap16")
            elif bits <= 32: return string("__builtin_bswap32")
            else: return string("__builtin_bswap64")
        # The atomics map back to the `__atomic_*` builtins their declarations used to
        # `importc` directly, so the generated C is unchanged by their becoming rows.
        # `bits` is not consulted: unlike the bit-counting builtins these are
        # type-generic in GCC — the width comes from the pointer argument — which is
        # also why `intrinsicOfCallee` leaves `bits` at 0 here (the first param is a
        # `ptr T`, not an integer).
        case IntrinsicOp.AtomicLoadOp: return string("__atomic_load_n")
        case IntrinsicOp.AtomicStoreOp: return string("__atomic_store_n")
        case IntrinsicOp.AtomicExchangeOp: return string("__atomic_exchange_n")
        case IntrinsicOp.AtomicCompareExchangeOp: return string("__atomic_compare_exchange_n")
        case IntrinsicOp.AtomicFetchAddOp: return string("__atomic_fetch_add")
        case IntrinsicOp.AtomicFetchSubOp: return string("__atomic_fetch_sub")
        case IntrinsicOp.AtomicFetchAndOp: return string("__atomic_fetch_and")
        case IntrinsicOp.AtomicFetchOrOp: return string("__atomic_fetch_or")
        case IntrinsicOp.AtomicFetchXorOp: return string("__atomic_fetch_xor")
        case IntrinsicOp.AtomicAddFetchOp: return string("__atomic_add_fetch")
        case IntrinsicOp.AtomicSubFetchOp: return string("__atomic_sub_fetch")
        case IntrinsicOp.AtomicTestAndSetOp: return string("__atomic_test_and_set")
        case IntrinsicOp.AtomicClearOp: return string("__atomic_clear")
        case IntrinsicOp.AtomicThreadFenceOp: return string("__atomic_thread_fence")
        case IntrinsicOp.AtomicSignalFenceOp: return string("__atomic_signal_fence")
        # Not a `__builtin_*` but a PRELUDE macro, and it has to be: which spelling a
        # spin hint has is a property of the C compiler's TARGET, and this side does
        # not know it. `__builtin_ia32_pause` does not exist off x86 and there is no
        # portable ARM equivalent to name instead, so the choice belongs in the `#if`
        # the C compiler itself evaluates (`cprelude.NIM_CPU_RELAX`). The call shape is
        # what matters here, and a function-like macro has exactly the one `genInstr`
        # emits.
        case IntrinsicOp.CpuRelaxOp: return string("NIM_CPU_RELAX")
        # The size operand is a Leng integer; C converts it to `size_t` implicitly.
        case IntrinsicOp.MemsetOp: return string("__builtin_memset")
        case IntrinsicOp.MemcpyOp: return string("__builtin_memcpy")
        case IntrinsicOp.MemcmpOp: return string("__builtin_memcmp")
        # gcc/clang expand these inline (`sqrtsd`), with an errno slow path for a
        # negative operand unless `-fno-math-errno`.
        case IntrinsicOp.SqrtOp: return (string("__builtin_sqrtf") if bits == 32 else string("__builtin_sqrt"))
        case _: return string("")


def isImportC(m: mut @ MainModule, n: Cursor) -> bool:
    if kind(n) in Tset[NifKind](NifKind.Symbol, NifKind.SymbolDef):
        with let:
            d = getDeclOrNil(m, symId(n))
        result = not isNil(d) and d.isImport
    else:
        result = False
    return result


def registerParams(c: mut @ MainModule, params: Cursor):
    ## Register a routine's parameters in the current scope (their types feed
    ## `getType`). `params` is the `(params (param :name pragmas type) …)` node, or
    ## `.` for a parameterless routine.
    if kind(params) != NifKind.TagLit: return
    with var:
        p = params.copy()
    for _ in loopInto(p):
        if substructureKind(p) == LengOther.ParamU:
            with let:
                d = takeParamDecl(p)
            if kind(d.name) == NifKind.SymbolDef:
                c.registerLocal(symId(d.name), d.typ)
        else:
            skip(p)

# ---- synthesized types ----------------------------------------------------


def createIntegralType(c: mut @ MainModule, name: string) -> Cursor:
    result = c.builtinTypes.getOrDefault(name, default(Cursor))
    if result.cursorIsNil():
        with var:
            buf = parseFromBuffer(name, string("<builtin>"), 8, c.pool, c.tags)
        result = buf.cursorAt(0)
        c.builtinTypes[name] = result
    return result


def _ptrTypeOf(c: mut @ MainModule, elem: Cursor) -> Cursor:
    with var:
        buf = createTokenBuf(4, c.pool, c.tags)
    buf.openTag(TagId(ord(TagEnum.PtrTagId)))
    addSubtree(buf, elem)
    buf.closeTag()
    result = buf.cursorAt(0)
    return result

# ---- field lookup ---------------------------------------------------------


class FieldSelector(NIntEnum):
    FieldType = auto()
    FieldPragmas = auto()


def typeOfField(c: mut @ MainModule, n: mut @ Cursor, fld: SymId, sel=FieldSelector.FieldType) -> Cursor:
    if substructureKind(n) == LengOther.FldU:
        with let:
            decl = takeFieldDecl(n)
        if kind(decl.name) == NifKind.SymbolDef and symId(decl.name) == fld:
            result = decl.typ if sel == FieldSelector.FieldType else decl.pragmas
        else:
            result = default(Cursor)
    elif isUnionBranch(n):
        # Discriminated-union branch: the fields live in its payload object.
        result = default(Cursor)
        with let:
            b = takeUnionBranch(n)  # advances `n` past the whole branch
        if typeKind(b.body) == LengType.ObjectT:
            with var:
                body = b.body.copy()
            result = typeOfField(c, body, fld, sel)
    else:
        result = default(Cursor)
        with let:
            tk = typeKind(n)
        if tk in Tset[LengType](LengType.ObjectT, LengType.UnionT):
            with into(n):
                with var:
                    hasBase = False
                    baseSym = default(SymId)
                if tk == LengType.ObjectT:
                    if kind(n) == NifKind.Symbol:
                        hasBase = True
                        baseSym = symId(n)
                    skip(n)  # inheritance reference
                with var:
                    done = False
                while n.hasMore() and not done:
                    result = typeOfField(c, n, fld, sel)
                    if not result.cursorIsNil(): done = True
                while n.hasMore(): skip(n)  # mop up if we broke early
                if result.cursorIsNil() and hasBase:
                    with let:
                        d = getDeclOrNil(c, baseSym)
                    if not isNil(d) and stmtKind(d.pos) == LengStmt.TypeS:
                        with var:
                            baseBody = asTypeDecl(d.pos).body
                        result = typeOfField(c, baseBody, fld, sel)
        else:
            # Unknown node. Every other path advances `n`, and the caller above
            # loops `while n.hasMore and not done` - so failing to advance here is
            # an infinite loop, not a missed field. Keep the walk progressing.
            skip(n)
    return result


def navigateToObjectBody(c: mut @ MainModule, n: Cursor) -> Cursor:
    with var:
        counter = nint(20)
    result = n.copy()
    while counter > 0 and kind(result) == NifKind.Symbol:
        counter -= 1
        with let:
            d = getDeclOrNil(c, symId(result))
        if not isNil(d) and stmtKind(d.pos) == LengStmt.TypeS:
            result = asTypeDecl(d.pos).body
        else:
            break
    return result

# ---- the navigator --------------------------------------------------------


def _getTypeImpl(c: mut @ MainModule, n: Cursor) -> Cursor:
    match kind(n):
        case NifKind.DotToken | NifKind.Ident | NifKind.SymbolDef:
            result = createIntegralType(c, string("(err)"))
        case NifKind.Symbol:
            with var:
                it: pragma("cursor") = c.current
            while it is not None:
                with let:
                    res = it.locals.getOrDefault(symId(n), default(Cursor))
                if not res.cursorIsNil():
                    return res
                it = it.parent
            with let:
                d = getDeclOrNil(c, symId(n))
            if not isNil(d):
                result = _getTypeImpl(c, d.pos)
            else:
                # importC types are not defined
                result = createIntegralType(c, string("(err)"))
        case NifKind.IntLit:
            result = createIntegralType(c, string("(i -1)"))
        case NifKind.UIntLit:
            result = createIntegralType(c, string("(u -1)"))
        case NifKind.FloatLit:
            result = createIntegralType(c, string("(f +64)"))
        case NifKind.StrLit:
            result = createIntegralType(c, string("(aptr (c +8))"))
        case NifKind.CharLit:
            result = createIntegralType(c, string("(c +8)"))
        case NifKind.ExtendedSuffix | NifKind.LineInfoLit | NifKind.UnknownToken | NifKind.EofToken | NifKind.ParLe | NifKind.ParRi:
            result = createIntegralType(c, string("(err)"))
        case NifKind.TagLit:
            match exprKind(n):
                case LengExpr.SizeofC | LengExpr.AlignofC | LengExpr.OffsetofC:
                    result = createIntegralType(c, string("(i +8)"))
                case LengExpr.InfC | LengExpr.NeginfC | LengExpr.NanC:
                    result = createIntegralType(c, string("(f +64)"))
                case LengExpr.TrueC | LengExpr.FalseC | LengExpr.AndC | LengExpr.OrC | LengExpr.NotC | LengExpr.EqC | LengExpr.NeqC | LengExpr.LeC | LengExpr.LtC | LengExpr.ErrvC | LengExpr.OvfC:
                    result = createIntegralType(c, string("(bool)"))
                case LengExpr.CallC | LengExpr.InstrC:
                    # `(instr SYM …)` is typed EXACTLY like `(call SYM …)` — the callee's
                    # signature drives everything. Only the *cost* differs, which is what the
                    # separate tag exists to make visible.
                    with var:
                        procType = navigateToObjectBody(c, _getTypeImpl(c, _firstChild(n)))
                    if typeKind(procType) == LengType.ProctypeT or symKind(procType) == LengSym.ProcY:
                        procType.inc()
                        skip(procType)  # name
                    if typeKind(procType) == LengType.ParamsT:
                        result = procType
                        skip(result)  # skip the parameters, return type follows
                    else:
                        result = createIntegralType(c, string("(err)"))
                case LengExpr.AtC | LengExpr.PatC:
                    with var:
                        arrayType = navigateToObjectBody(c, _getTypeImpl(c, _firstChild(n)))
                    # Descend to the element type only when the base really is an indexable
                    # type. Otherwise the base did not resolve (an unresolved `Symbol` or the
                    # `(err)` sentinel), and a blind `inc` would run the cursor off the end of
                    # its buffer — a later `kind`/`typeKind` on that exhausted cursor crashes.
                    if typeKind(arrayType) in Tset[LengType](LengType.ArrayT, LengType.FlexarrayT, LengType.PtrT, LengType.AptrT):
                        result = arrayType
                        result.inc()  # into the element type (first child of (arr …)/(ptr …))
                    else:
                        result = createIntegralType(c, string("(err)"))
                case LengExpr.DotC:
                    with var:
                        a = _firstChild(n)
                        objType = navigateToObjectBody(c, _getTypeImpl(c, a))
                    skip(a)  # skip the object
                    with let:
                        fld = symId(a)
                    if typeKind(objType) in Tset[LengType](LengType.ObjectT, LengType.UnionT):
                        result = typeOfField(c, objType, fld)
                        if result.cursorIsNil():
                            result = createIntegralType(c, string("(err)"))
                    else:
                        result = createIntegralType(c, string("(err)"))
                case LengExpr.DerefC:
                    with let:
                        x = _getTypeImpl(c, _firstChild(n))
                    if typeKind(x) == LengType.PtrT:
                        result = _firstChild(x)
                    else:
                        result = createIntegralType(c, string("(err)"))
                case LengExpr.AddrC | LengExpr.HaddrC:  # both are `&lvalue`
                    with let:
                        x = _getTypeImpl(c, _firstChild(n))
                    result = _ptrTypeOf(c, x)
                case LengExpr.ConvC | LengExpr.CastC | LengExpr.AconstrC | LengExpr.OconstrC | LengExpr.BaseobjC:
                    result = _firstChild(n)
                case LengExpr.NegC | LengExpr.AddC | LengExpr.SubC | LengExpr.MulC | LengExpr.DivC | LengExpr.ModC | LengExpr.ShrC | LengExpr.ShlC | LengExpr.BitandC | LengExpr.BitorC | LengExpr.BitxorC | LengExpr.BitnotC:
                    result = _firstChild(n)
                case LengExpr.ParC:
                    result = _getTypeImpl(c, _firstChild(n))
                case LengExpr.NilC:
                    # `(nil T)` — the frontend types every `nil` it emits, so use that type.
                    # Only a `nil` some backend pass synthesized is still untyped, and for
                    # those `void*` remains the honest answer.
                    with let:
                        t = _firstChild(n)
                    if t.hasMore():
                        result = t
                    else:
                        result = createIntegralType(c, string("(ptr (void))"))
                case LengExpr.SufC:
                    result = createIntegralType(c, string("(err)"))
                    with var:
                        a = _firstChild(n)
                    skip(a)
                    if kind(a) in Tset[NifKind](NifKind.StrLit, NifKind.Ident):
                        with let:
                            s = strVal(a, c.pool)
                        if s.len > 0:
                            if s[0] == char('i'):
                                result = createIntegralType(c, string("(i ") + s.substr(1) + string(")"))
                            elif s[0] == char('u'):
                                result = createIntegralType(c, string("(u ") + s.substr(1) + string(")"))
                            elif s[0] == char('f'):
                                result = createIntegralType(c, string("(f ") + s.substr(1) + string(")"))
                case LengExpr.NoExpr:
                    match stmtKind(n):
                        case LengStmt.ProcS:
                            result = n.copy()
                            result.inc()  # ProcS token
                            skip(result)  # skip the name
                        case LengStmt.GvarS | LengStmt.TvarS | LengStmt.ConstS | LengStmt.VarS:
                            result = n.copy()
                            result.inc()  # token
                            skip(result)  # skip the name
                            skip(result)  # skip the pragmas
                        case _:
                            if substructureKind(n) in Tset[LengOther](LengOther.ParamU, LengOther.FldU):
                                result = n.copy()
                                result.inc()  # token
                                skip(result)  # skip the name
                                skip(result)  # skip the pragmas
                            else:
                                result = createIntegralType(c, string("(err)"))
    return result


def getType(c: mut @ MainModule, n: Cursor, skipAliases=True) -> Cursor:
    result = _getTypeImpl(c, n)
    if skipAliases:
        result = navigateToObjectBody(c, result)
    return result


def getNominalType(c: mut @ MainModule, n: Cursor) -> Cursor:
    ## Arrays are nominal types in NIFC too, so this does not skip aliases.
    result = _getTypeImpl(c, n)
    return result


def lookupField(c: mut @ MainModule, typ: Cursor, fld: SymId) -> Cursor:
    with var:
        body = navigateToObjectBody(c, typ)
    result = typeOfField(c, body, fld)
    return result
