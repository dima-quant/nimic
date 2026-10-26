# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifcdecl.nim
# ///
#
#           Leng tag decoding for `nifcore` cursors
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this distribution, for
#    details about the copyright.
#

## The `nifcore` counterpart of `lengc/leng_model`: tag decoders and declaration
## readers over **nifcore** cursors (no separate ParLe/ParRi; subtrees are
## bounded by jump fields). Originally `arkham/nifcdecl` in the `nativenif`
## repo; moved here so the shoggoth Leng optimizer and arkham's code generators
## share a single source (arkham already builds against nimony's `src/lib`).
##
## It reuses the canonical, NIF-API-independent enums from `models/leng_tags`
## (`LengStmt`, `LengExpr`, `LengType`, `LengPragma`, `LengOther`, `LengSym`, …)
## whose ordinals are the master tag ordinals. To make a parsed `nifcore`
## buffer's `cursorTagId` line up with those ordinals, seed the buffer's
## `TagPool` from the same master `TagData` (just like `nifstreams` seeds its
## global pool). Then `cast[LengStmt](tagId)` works exactly as in `leng_model`
## — but over `nifcore` cursors, keeping the enums clear of any NIF-API
## coupling.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.assertions import *
from .nifcore import *
from ..models.leng_tags import *
from ..models.callconv_tags import *
from ..models.tags import *
from ..models import leng_tags, callconv_tags
with export:
    leng_tags, callconv_tags


def createLengTagPool() -> TagPool:
    ## A `nifcore` tag pool seeded so each Leng tag's `TagId` equals its master
    ## `TagEnum` ordinal. Pass to `parseFromFile`/`parseFromBuffer` as
    ## `sharedTags` so `tagEnum`/`stmtKind`/… can decode by ordinal.
    result = newTagPool()
    for e in inrange(low(TagEnum), high(TagEnum)):
        if e == TagEnum.InvalidTagId:
            continue
        with let:
            id = result.registerTag(TagData[e][0])
        assert uint32(id) == uint32(TagData[e][1]), (
            string("nifc tag pool misalignment for ") + TagData[e][0])
    return result


@template
def tagEnumOf(c: Cursor) -> TagEnum:
    return (cast[TagEnum](uint32(c.cursorTagId()))
            if c.kind() == NifKind.TagLit else TagEnum.InvalidTagId)


@template
def tagEnum(c: Cursor) -> TagEnum:
    ## `leng_model`-compatible spelling of `tagEnumOf`.
    return tagEnumOf(c)

# ── tag-class decoders ──────────────────────────────────────────────────────


def stmtKind(c: Cursor) -> LengStmt:
    """{.inline.}"""
    with let:
        e = tagEnumOf(c)
    result = cast[LengStmt](e) if rawTagIsLengStmt(e) else LengStmt.NoStmt
    return result


def exprKind(c: Cursor) -> LengExpr:
    """{.inline.}"""
    with let:
        e = tagEnumOf(c)
    result = cast[LengExpr](e) if rawTagIsLengExpr(e) else LengExpr.NoExpr
    return result


def pragmaKind(c: Cursor) -> LengPragma:
    """{.inline.}"""
    with let:
        e = tagEnumOf(c)
    result = cast[LengPragma](e) if rawTagIsLengPragma(e) else LengPragma.NoPragma
    return result


def substructureKind(c: Cursor) -> LengOther:
    """{.inline.}"""
    with let:
        e = tagEnumOf(c)
    result = cast[LengOther](e) if rawTagIsLengOther(e) else LengOther.NoSub
    return result


def typeKind(c: Cursor) -> LengType:
    """{.inline.}"""
    if c.kind() == NifKind.DotToken:
        return LengType.VoidT       # an empty type slot reads as void
    with let:
        e = tagEnumOf(c)
    result = cast[LengType](e) if rawTagIsLengType(e) else LengType.NoType
    return result


def symKind(c: Cursor) -> LengSym:
    """{.inline.}"""
    with let:
        e = tagEnumOf(c)
    result = cast[LengSym](e) if rawTagIsLengSym(e) else LengSym.NoSym
    return result


def typeQual(c: Cursor) -> LengTypeQualifier:
    """{.inline.}"""
    with let:
        e = tagEnumOf(c)
    result = (cast[LengTypeQualifier](e)
              if rawTagIsLengTypeQualifier(e) else LengTypeQualifier.NoQualifier)
    return result


def callConvKind(c: Cursor) -> CallConv:
    """{.inline.}"""
    with let:
        e = tagEnumOf(c)
    result = cast[CallConv](e) if rawTagIsCallConv(e) else CallConv.NoCallConv
    return result

# Read helpers:


def elementType(n: Cursor) -> Cursor:
    """{.inline.}"""
    ## First child of a (single-element) type node, e.g. the `T` of `(ptr T)`.
    ## In `nifcore`, `inc` past a `TagLit` head lands on the first body token.
    result = n.copy()
    inc(result)
    return result


with const:
    AddrKinds = Tset[LengExpr](LengExpr.AddrC, LengExpr.HaddrC)
    ## `(addr x)` and `(haddr x)` both denote x's address and lower identically:
    ## every consumer that only needs "this is an address-of" should match on this
    ## set. They are separate tags because a consumer that cares about *why* the
    ## address was taken can then tell them apart without a second channel —
    ## `(haddr x)` is the compiler binding a location for a `var`/`out` parameter,
    ## `(addr x)` is the user turning a location into a value. Matching one tag
    ## alone is almost always a bug; matching this set says "either" out loud.

# NB: `leng_model.tracebackTypeC` is intentionally not ported — it walks
# *backwards* via `unsafeDec`, which `nifcore` has no primitive for, and no
# current consumer needs it. Add a backward primitive to `nifcore` first if a
# caller appears.

# ── declaration readers (mirror leng_model; already in into/skip/hasMore idiom)


class TypeDecl(Object):
    name: Cursor
    pragmas: Cursor
    body: Cursor


def _asTypeDeclImpl(n: mut @ Cursor) -> TypeDecl:
    ## Reads child positions; advances `n` past the (type) scope close.
    assert n.stmtKind() == LengStmt.TypeS
    with n.into():
        result = TypeDecl(name=n)
        skip(n)
        result.pragmas = n
        skip(n)
        result.body = n
        skip(n)  # consume body so the into-epilogue closes the scope cleanly
    return result


def asTypeDecl(n: Cursor) -> TypeDecl:
    with var:
        n = n.copy()
    result = _asTypeDeclImpl(n)  # local cursor is dropped on return
    return result


def takeTypeDecl(n: mut @ Cursor) -> TypeDecl:
    result = _asTypeDeclImpl(n)  # advances `n` past the close
    return result


class FieldDecl(Object):
    name: Cursor
    pragmas: Cursor
    typ: Cursor


def takeFieldDecl(n: mut @ Cursor) -> FieldDecl:
    assert n.substructureKind() == LengOther.FldU
    with n.into():
        result = FieldDecl(name=n)
        skip(n)
        result.pragmas = n
        skip(n)
        result.typ = n
        skip(n)
    return result


class UnionBranch(Object):
    ranges: Cursor  ## the `(ranges ...)` selecting this branch; `.` for `else`
    body: Cursor    ## the branch's anonymous `(object ...)`, or `.` if it
    ## declares no fields (`of x: nil`)


def isUnionBranch(n: Cursor) -> bool:
    """{.inline.}"""
    ## True if `n` is a discriminated-union branch, i.e. a case object lowered by
    ## hexer rather than the untagged `{.union.}` form. The two shapes never mix,
    ## so testing the child tag is enough - see `doc/leng-spec.md`, UnionBranch.
    return n.substructureKind() in Tset[LengOther](LengOther.OfU, LengOther.ElseU)


def takeUnionBranch(n: mut @ Cursor) -> UnionBranch:
    ## Read a `(of RANGES BODY)` / `(else BODY)` branch and advance past it.
    ## Callers that only need the fields use `result.body`; debug info also reads
    ## `result.ranges` to name the branch after its discriminant values.
    ##
    ## Start from the nil-cursor default: an `else` branch has no ranges, so
    ## without this `result.ranges` is whatever the stack held — and
    ## `cursorIsNil(branch.ranges)` is exactly how `contracts_fir` and
    ## `llvmdebug` tell the two shapes apart. `strictdefs` rejects the field
    ## write into an uninitialized `result` for that reason.
    with let:
        isOf = n.substructureKind() == LengOther.OfU
    result = default(UnionBranch)
    with n.into():
        if isOf:
            result.ranges = n
            skip(n)
        result.body = n
        skip(n)
    return result


def asUnionBranch(n: Cursor) -> UnionBranch:
    with var:
        n = n.copy()
    result = takeUnionBranch(n)  # local cursor is dropped on return
    return result


class ParamDecl(Object):
    name: Cursor
    pragmas: Cursor
    typ: Cursor


def takeParamDecl(n: mut @ Cursor) -> ParamDecl:
    assert n.substructureKind() == LengOther.ParamU
    with n.into():
        result = ParamDecl(name=n)
        skip(n)
        result.pragmas = n
        skip(n)
        result.typ = n
        skip(n)
    return result


class ProcType(Object):
    params: Cursor
    returnType: Cursor
    pragmas: Cursor


def takeProcType(n: mut @ Cursor) -> ProcType:
    if n.typeKind() == LengType.ParamsT:
        # Already inside a (proc/proctype) scope; the caller entered. Read the
        # remaining sibling cursors without entering a new scope.
        assert n.typeKind() == LengType.ParamsT or n.kind() == NifKind.DotToken
        result = ProcType(params=n)
        skip(n)
        result.returnType = n
        skip(n)
        result.pragmas = n
        skip(n)
        if n.kind() == NifKind.DotToken:
            inc(n)
    else:
        assert n.stmtKind() == LengStmt.ProcS or n.typeKind() == LengType.ProctypeT
        with n.into():  # enter (proc ...) / (proctype ...)
            skip(n)  # name
            assert n.typeKind() == LengType.ParamsT or n.kind() == NifKind.DotToken
            result = ProcType(params=n)
            skip(n)
            result.returnType = n
            skip(n)
            result.pragmas = n
            skip(n)
            if n.hasMore() and n.kind() == NifKind.DotToken:
                inc(n)
            while n.hasMore():
                skip(n)
    return result


class ProcDecl(Object):
    name: Cursor
    params: Cursor
    returnType: Cursor
    pragmas: Cursor
    body: Cursor


def takeProcDecl(n: mut @ Cursor) -> ProcDecl:
    assert n.stmtKind() == LengStmt.ProcS
    with n.into():
        result = ProcDecl(name=n)
        skip(n)
        result.params = n
        skip(n)
        result.returnType = n
        skip(n)
        result.pragmas = n
        skip(n)
        result.body = n
        skip(n)
    return result


class VarDecl(Object):
    name: Cursor
    pragmas: Cursor
    typ: Cursor
    value: Cursor


def takeVarDecl(n: mut @ Cursor) -> VarDecl:
    assert n.stmtKind() in Tset[LengStmt](
        LengStmt.GvarS, LengStmt.TvarS, LengStmt.VarS, LengStmt.ConstS)
    with n.into():
        result = VarDecl(name=n)
        skip(n)
        result.pragmas = n
        skip(n)
        result.typ = n
        skip(n)
        result.value = n
        skip(n)
    return result

# ── Tag-typed intent overloads (mirrors leng_model / nimony_model) ───────────

type LengTagKind = (
    LengStmt | LengExpr | LengType | LengOther | LengPragma | LengSym
)

# See `nimony_model.nim`'s `tagDispatch` for the rationale: tag-class
# templates dispatch via `when expected is X` and use `==`/`$` operators that
# don't exist on the union itself, so we mark them `.untyped` under nimony so
# the body isn't typechecked at definition time.
if comptime(defined("nimony")):
    pragma("pragma: tagDispatch, untyped")
else:
    pragma("pragma: tagDispatch")


@template
def _kindMatches(c: Cursor, expected: LengTagKind) -> bool:
    """{.tagDispatch.}"""
    if comptime(isinstance(expected, LengStmt)):
        return c.stmtKind() == expected
    elif comptime(isinstance(expected, LengExpr)):
        return c.exprKind() == expected
    elif comptime(isinstance(expected, LengType)):
        return c.typeKind() == expected
    elif comptime(isinstance(expected, LengOther)):
        return c.substructureKind() == expected
    elif comptime(isinstance(expected, LengPragma)):
        return c.pragmaKind() == expected
    elif comptime(isinstance(expected, LengSym)):
        return c.symKind() == expected
    else:
        return False


@template
def skip(c: mut @ Cursor, expected: LengTagKind):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("skip ") + str(expected) + string(": cursor at kind=") + str(c.kind()))
    skip(c)


@template
def inc(c: mut @ Cursor, expected: LengTagKind):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("inc ") + str(expected) + string(": cursor at kind=") + str(c.kind()))
    inc(c)


@template
def into(c: mut @ Cursor, expected: LengTagKind, body: untyped):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("into ") + str(expected) + string(": cursor at kind=") + str(c.kind()))
    with into(c):
        body


@template
def loopInto(c: mut @ Cursor, expected: LengTagKind, body: untyped):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("loopInto ") + str(expected) + string(": cursor at kind=") + str(c.kind()))
    for _ in loopInto(c):
        body


if comptime(__name__ == "__main__"):
    def _tid(e: TagEnum) -> TagId:
        return TagId(uint32(ord(e)))

    def _runTests():
        with var:
            tags = createLengTagPool()
            pool = newPool()
            b = createTokenBuf(cap=128, sharedPool=pool, sharedTags=tags)

        # Verify tag pool seeding
        echo(tagName(tags, TagId(uint32(ord(TagEnum.StmtsTagId)))))
        echo(tagName(tags, TagId(uint32(ord(TagEnum.ProcTagId)))))

        # Root (stmts ...)
        b.openTag(_tid(TagEnum.StmtsTagId))

        # 1. (type :MyType.0.m (pragmas (packed)) (object . (fld :x.0.m . (i +32))))
        b.openTag(_tid(TagEnum.TypeTagId))
        b.addSymDef(string("MyType.0.m"))
        b.openTag(_tid(TagEnum.PragmasTagId))
        b.openTag(_tid(TagEnum.PackedTagId))
        b.closeTag()
        b.closeTag()
        b.openTag(_tid(TagEnum.ObjectTagId))
        b.addDotToken()
        b.openTag(_tid(TagEnum.FldTagId))
        b.addSymDef(string("x.0.m"))
        b.addDotToken()
        b.openTag(_tid(TagEnum.ITagId))
        b.addIntLit(i64(32))
        b.closeTag()
        b.closeTag()
        b.closeTag()
        b.closeTag()

        # 2. Union branches: (of (ranges +1) (object .)) and (else .)
        b.openTag(_tid(TagEnum.OfTagId))
        b.openTag(_tid(TagEnum.RangesTagId))
        b.addIntLit(i64(1))
        b.closeTag()
        b.openTag(_tid(TagEnum.ObjectTagId))
        b.addDotToken()
        b.closeTag()
        b.closeTag()

        b.openTag(_tid(TagEnum.ElseTagId))
        b.addDotToken()
        b.closeTag()

        # 3. (proc :fn.0.m (params (param :a.0.m . (ptr (i +32)))) . (pragmas (inline) (cdecl)) (stmts (ret .)))
        b.openTag(_tid(TagEnum.ProcTagId))
        b.addSymDef(string("fn.0.m"))
        b.openTag(_tid(TagEnum.ParamsTagId))
        b.openTag(_tid(TagEnum.ParamTagId))
        b.addSymDef(string("a.0.m"))
        b.addDotToken()
        b.openTag(_tid(TagEnum.PtrTagId))
        b.openTag(_tid(TagEnum.ITagId))
        b.addIntLit(i64(32))
        b.closeTag()
        b.closeTag()
        b.closeTag()
        b.closeTag()
        b.addDotToken()
        b.openTag(_tid(TagEnum.PragmasTagId))
        b.openTag(_tid(TagEnum.InlineTagId))
        b.closeTag()
        b.openTag(_tid(TagEnum.CdeclTagId))
        b.closeTag()
        b.closeTag()
        b.openTag(_tid(TagEnum.StmtsTagId))
        b.openTag(_tid(TagEnum.RetTagId))
        b.addDotToken()
        b.closeTag()
        b.closeTag()
        b.closeTag()

        # 4. (proctype . (params) (u +64) (pragmas (fastcall)) .)
        b.openTag(_tid(TagEnum.ProctypeTagId))
        b.addDotToken()
        b.openTag(_tid(TagEnum.ParamsTagId))
        b.closeTag()
        b.openTag(_tid(TagEnum.UTagId))
        b.addIntLit(i64(64))
        b.closeTag()
        b.openTag(_tid(TagEnum.PragmasTagId))
        b.openTag(_tid(TagEnum.FastcallTagId))
        b.closeTag()
        b.closeTag()
        b.addDotToken()
        b.closeTag()

        # 5. (gvar :gv.0.m . (ro (i +32)) (addr g)) and (var :lv.0.m . (atomic (i +32)) (haddr g))
        b.openTag(_tid(TagEnum.GvarTagId))
        b.addSymDef(string("gv.0.m"))
        b.addDotToken()
        b.openTag(_tid(TagEnum.RoTagId))
        b.openTag(_tid(TagEnum.ITagId))
        b.addIntLit(i64(32))
        b.closeTag()
        b.closeTag()
        b.openTag(_tid(TagEnum.AddrTagId))
        b.addSymUse(string("g.0.m"))
        b.closeTag()
        b.closeTag()

        b.openTag(_tid(TagEnum.VarTagId))
        b.addSymDef(string("lv.0.m"))
        b.addDotToken()
        b.openTag(_tid(TagEnum.AtomicTagId))
        b.openTag(_tid(TagEnum.ITagId))
        b.addIntLit(i64(32))
        b.closeTag()
        b.closeTag()
        b.openTag(_tid(TagEnum.HaddrTagId))
        b.addSymUse(string("g.0.m"))
        b.closeTag()
        b.closeTag()

        b.closeTag()  # end root (stmts ...)

        with var:
            c = b.beginRead()

        # Root tag decoders
        echo(c.tagEnumOf(), " ", c.tagEnum(), " ", c.stmtKind(), " ", c.exprKind(),
             " ", c.typeKind(), " ", c.substructureKind(), " ", c.pragmaKind(),
             " ", c.symKind(), " ", c.typeQual(), " ", c.callConvKind())

        with c.into(LengStmt.StmtsS):
            # 1. TypeDecl via asTypeDecl (non-advancing) and takeTypeDecl (advancing)
            echo("type symKind=", c.symKind())
            with let:
                tdPeek = asTypeDecl(c)
                td = takeTypeDecl(c)
            echo("td=", symName(tdPeek.name), " ", symName(td.name),
                 " ", td.pragmas.substructureKind(), " ", td.body.typeKind())
            with var:
                pcur = td.pragmas.copy()
            for _ in pcur.loopInto(LengOther.PragmasU):
                echo("type pragma=", pcur.pragmaKind())
                pcur.skip(LengPragma.PackedP)
            with var:
                ocur = td.body.copy()
            with ocur.into(LengType.ObjectT):
                echo("obj base typeKind=", ocur.typeKind())
                skip(ocur)  # dot
                echo("isUnionBranch on fld=", isUnionBranch(ocur))
                with let:
                    fd = takeFieldDecl(ocur)
                echo("fld=", symName(fd.name), " ", fd.pragmas.kind(), " ", fd.typ.typeKind())

            # 2. Union branches (OfU and ElseU)
            echo("isUnionBranch of=", isUnionBranch(c))
            with let:
                ubPeek = asUnionBranch(c)
                ubOf = takeUnionBranch(c)
            echo("ubOf=", cursorIsNil(ubPeek.ranges), " ", ubOf.ranges.substructureKind(),
                 " ", ubOf.body.typeKind())
            echo("isUnionBranch else=", isUnionBranch(c))
            with let:
                ubElse = takeUnionBranch(c)
            echo("ubElse=", cursorIsNil(ubElse.ranges), " ", ubElse.body.kind(),
                 " ", ubElse.body.typeKind())

            # 3. ProcS: test takeProcType (both from ProcS and from ParamsT) and takeProcDecl
            with var:
                procCopy1 = c.copy()
                procCopy2 = c.copy()
            with let:
                ptFromProc = takeProcType(procCopy1)
            echo("ptFromProc=", ptFromProc.params.typeKind(), " ",
                 ptFromProc.returnType.typeKind(), " ", ptFromProc.pragmas.substructureKind())

            with procCopy2.into(LengStmt.ProcS):
                skip(procCopy2)  # name
                with let:
                    ptFromParams = takeProcType(procCopy2)
                echo("ptFromParams=", ptFromParams.params.typeKind(), " ",
                     ptFromParams.returnType.typeKind(), " ", ptFromParams.pragmas.substructureKind())
                while procCopy2.hasMore():
                    skip(procCopy2)

            with let:
                pd = takeProcDecl(c)
            echo("pd=", symName(pd.name), " ", pd.params.typeKind(), " ",
                 pd.returnType.typeKind(), " ", pd.pragmas.substructureKind(), " ",
                 pd.body.stmtKind())
            with var:
                paramsCur = pd.params.copy()
            for _ in paramsCur.loopInto(LengType.ParamsT):
                with let:
                    param = takeParamDecl(paramsCur)
                    elem = elementType(param.typ)
                echo("param=", symName(param.name), " ", param.pragmas.kind(),
                     " ", param.typ.typeKind(), " elem=", elem.typeKind())
            with var:
                procPragmas = pd.pragmas.copy()
            with procPragmas.into(LengOther.PragmasU):
                echo("proc pragma1=", procPragmas.pragmaKind())
                procPragmas.skip(LengPragma.InlineP)
                echo("proc callconv=", procPragmas.callConvKind())
                skip(procPragmas)

            # 4. ProctypeT via takeProcType
            with let:
                pt2 = takeProcType(c)
            echo("pt2=", pt2.params.typeKind(), " ", pt2.returnType.typeKind(),
                 " ", pt2.pragmas.substructureKind())

            # 5. VarDecl (GvarS and VarS), typeQual, AddrKinds, 2-arg inc
            with let:
                vd1 = takeVarDecl(c)
            with var:
                vt1 = vd1.typ.copy()
                vv1 = vd1.value.copy()
            echo("vd1=", symName(vd1.name), " qual=", vt1.typeQual(),
                 " elem=", elementType(vt1).typeKind(),
                 " valKind=", vv1.exprKind(), " inAddr=", vv1.exprKind() in AddrKinds)
            vv1.inc(LengExpr.AddrC)
            echo("vd1 target=", symName(vv1), " tagEnumOnSym=", vv1.tagEnumOf())

            with let:
                vd2 = takeVarDecl(c)
            with var:
                vt2 = vd2.typ.copy()
                vv2 = vd2.value.copy()
            echo("vd2=", symName(vd2.name), " qual=", vt2.typeQual(),
                 " valKind=", vv2.exprKind(), " inAddr=", vv2.exprKind() in AddrKinds)

        endRead(c)

    _runTests()
