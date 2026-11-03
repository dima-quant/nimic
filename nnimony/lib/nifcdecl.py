# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/nifcdecl.nim
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
from .nifcore import (
    addSymDef, addSymUse, createTokenBuf, Cursor, cursorTagId,
    endRead, into, kind, loopInto, newPool, newTagPool, NifKind, registerTag, skip, symName,
    TagId, TagPool)
from ..models.leng_tags import (
    LengExpr, LengOther, LengPragma, LengStmt, LengSym, LengType, LengTypeQualifier, rawTagIsLengExpr,
    rawTagIsLengOther, rawTagIsLengPragma, rawTagIsLengStmt, rawTagIsLengSym, rawTagIsLengType,
    rawTagIsLengTypeQualifier)
from ..models.callconv_tags import CallConv, rawTagIsCallConv
from ..models.tags import TagData, TagEnum
from ..models import leng_tags, callconv_tags
export(leng_tags, callconv_tags)


def createLengTagPool() -> TagPool:
    ## A `nifcore` tag pool seeded so each Leng tag's `TagId` equals its master
    ## `TagEnum` ordinal. Pass to `parseFromFile`/`parseFromBuffer` as
    ## `sharedTags` so `tagEnum`/`stmtKind`/… can decode by ordinal.
    result = newTagPool()
    for e in inrange(low(TagEnum), high(TagEnum)):
        if e == TagEnum.InvalidTagId:
            continue
        with let:
            id = registerTag(result, TagData[e][0])
        assert uint32(id) == uint32(TagData[e][1]), (
            string("nifc tag pool misalignment for ") + TagData[e][0])
    return result


@template
def tagEnumOf(c: Cursor) -> TagEnum:
    return (cast[TagEnum](uint32(cursorTagId(c)))
            if kind(c) == NifKind.TagLit else TagEnum.InvalidTagId)


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
    if kind(c) == NifKind.DotToken:
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
    result.inc()
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
    assert stmtKind(n) == LengStmt.TypeS
    with into(n):
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
    assert substructureKind(n) == LengOther.FldU
    with into(n):
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
    return substructureKind(n) in Tset[LengOther](LengOther.OfU, LengOther.ElseU)


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
        isOf = substructureKind(n) == LengOther.OfU
    result = default(UnionBranch)
    with into(n):
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
    assert substructureKind(n) == LengOther.ParamU
    with into(n):
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
    if typeKind(n) == LengType.ParamsT:
        # Already inside a (proc/proctype) scope; the caller entered. Read the
        # remaining sibling cursors without entering a new scope.
        assert typeKind(n) == LengType.ParamsT or kind(n) == NifKind.DotToken
        result = ProcType(params=n)
        skip(n)
        result.returnType = n
        skip(n)
        result.pragmas = n
        skip(n)
        if kind(n) == NifKind.DotToken:
            n.inc()
    else:
        assert stmtKind(n) == LengStmt.ProcS or typeKind(n) == LengType.ProctypeT
        with into(n):  # enter (proc ...) / (proctype ...)
            skip(n)  # name
            assert typeKind(n) == LengType.ParamsT or kind(n) == NifKind.DotToken
            result = ProcType(params=n)
            skip(n)
            result.returnType = n
            skip(n)
            result.pragmas = n
            skip(n)
            if n.hasMore() and kind(n) == NifKind.DotToken:
                n.inc()
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
    assert stmtKind(n) == LengStmt.ProcS
    with into(n):
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
    assert stmtKind(n) in Tset[LengStmt](
        LengStmt.GvarS, LengStmt.TvarS, LengStmt.VarS, LengStmt.ConstS)
    with into(n):
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
        return stmtKind(c) == expected
    elif comptime(isinstance(expected, LengExpr)):
        return exprKind(c) == expected
    elif comptime(isinstance(expected, LengType)):
        return typeKind(c) == expected
    elif comptime(isinstance(expected, LengOther)):
        return substructureKind(c) == expected
    elif comptime(isinstance(expected, LengPragma)):
        return pragmaKind(c) == expected
    elif comptime(isinstance(expected, LengSym)):
        return symKind(c) == expected
    else:
        return False


@template
def skip(c: mut @ Cursor, expected: LengTagKind):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("skip ") + str(expected) + string(": cursor at kind=") + str(kind(c)))
    skip(c)


@template
def inc(c: mut @ Cursor, expected: LengTagKind):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("inc ") + str(expected) + string(": cursor at kind=") + str(kind(c)))
    c.inc()


@template
def into(c: mut @ Cursor, expected: LengTagKind, body: untyped):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("into ") + str(expected) + string(": cursor at kind=") + str(kind(c)))
    with into(c):
        body


@template
def loopInto(c: mut @ Cursor, expected: LengTagKind, body: untyped):
    """{.tagDispatch.}"""
    assert _kindMatches(c, expected), (
        string("loopInto ") + str(expected) + string(": cursor at kind=") + str(kind(c)))
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
        echo(tags.tagName(TagId(uint32(ord(TagEnum.StmtsTagId)))))
        echo(tags.tagName(TagId(uint32(ord(TagEnum.ProcTagId)))))

        # Root (stmts ...)
        b.openTag(_tid(TagEnum.StmtsTagId))

        # 1. (type :MyType.0.m (pragmas (packed)) (object . (fld :x.0.m . (i +32))))
        b.openTag(_tid(TagEnum.TypeTagId))
        addSymDef(b, string("MyType.0.m"))
        b.openTag(_tid(TagEnum.PragmasTagId))
        b.openTag(_tid(TagEnum.PackedTagId))
        b.closeTag()
        b.closeTag()
        b.openTag(_tid(TagEnum.ObjectTagId))
        b.addDotToken()
        b.openTag(_tid(TagEnum.FldTagId))
        addSymDef(b, string("x.0.m"))
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
        addSymDef(b, string("fn.0.m"))
        b.openTag(_tid(TagEnum.ParamsTagId))
        b.openTag(_tid(TagEnum.ParamTagId))
        addSymDef(b, string("a.0.m"))
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
        addSymDef(b, string("gv.0.m"))
        b.addDotToken()
        b.openTag(_tid(TagEnum.RoTagId))
        b.openTag(_tid(TagEnum.ITagId))
        b.addIntLit(i64(32))
        b.closeTag()
        b.closeTag()
        b.openTag(_tid(TagEnum.AddrTagId))
        addSymUse(b, string("g.0.m"))
        b.closeTag()
        b.closeTag()

        b.openTag(_tid(TagEnum.VarTagId))
        addSymDef(b, string("lv.0.m"))
        b.addDotToken()
        b.openTag(_tid(TagEnum.AtomicTagId))
        b.openTag(_tid(TagEnum.ITagId))
        b.addIntLit(i64(32))
        b.closeTag()
        b.closeTag()
        b.openTag(_tid(TagEnum.HaddrTagId))
        addSymUse(b, string("g.0.m"))
        b.closeTag()
        b.closeTag()

        b.closeTag()  # end root (stmts ...)

        with var:
            c = b.beginRead()

        # Root tag decoders
        echo(tagEnumOf(c), " ", tagEnum(c), " ", stmtKind(c), " ", exprKind(c),
             " ", typeKind(c), " ", substructureKind(c), " ", pragmaKind(c),
             " ", symKind(c), " ", typeQual(c), " ", callConvKind(c))

        with into(c, LengStmt.StmtsS):
            # 1. TypeDecl via asTypeDecl (non-advancing) and takeTypeDecl (advancing)
            echo("type symKind=", symKind(c))
            with let:
                tdPeek = asTypeDecl(c)
                td = takeTypeDecl(c)
            echo("td=", symName(tdPeek.name), " ", symName(td.name),
                 " ", substructureKind(td.pragmas), " ", typeKind(td.body))
            with var:
                pcur = td.pragmas.copy()
            for _ in loopInto(pcur, LengOther.PragmasU):
                echo("type pragma=", pragmaKind(pcur))
                skip(pcur, LengPragma.PackedP)
            with var:
                ocur = td.body.copy()
            with into(ocur, LengType.ObjectT):
                echo("obj base typeKind=", typeKind(ocur))
                skip(ocur)  # dot
                echo("isUnionBranch on fld=", isUnionBranch(ocur))
                with let:
                    fd = takeFieldDecl(ocur)
                echo("fld=", symName(fd.name), " ", kind(fd.pragmas), " ", typeKind(fd.typ))

            # 2. Union branches (OfU and ElseU)
            echo("isUnionBranch of=", isUnionBranch(c))
            with let:
                ubPeek = asUnionBranch(c)
                ubOf = takeUnionBranch(c)
            echo("ubOf=", ubPeek.ranges.cursorIsNil(), " ", substructureKind(ubOf.ranges),
                 " ", typeKind(ubOf.body))
            echo("isUnionBranch else=", isUnionBranch(c))
            with let:
                ubElse = takeUnionBranch(c)
            echo("ubElse=", ubElse.ranges.cursorIsNil(), " ", kind(ubElse.body),
                 " ", typeKind(ubElse.body))

            # 3. ProcS: test takeProcType (both from ProcS and from ParamsT) and takeProcDecl
            with var:
                procCopy1 = c.copy()
                procCopy2 = c.copy()
            with let:
                ptFromProc = takeProcType(procCopy1)
            echo("ptFromProc=", typeKind(ptFromProc.params), " ",
                 typeKind(ptFromProc.returnType), " ", substructureKind(ptFromProc.pragmas))

            with into(procCopy2, LengStmt.ProcS):
                skip(procCopy2)  # name
                with let:
                    ptFromParams = takeProcType(procCopy2)
                echo("ptFromParams=", typeKind(ptFromParams.params), " ",
                     typeKind(ptFromParams.returnType), " ", substructureKind(ptFromParams.pragmas))
                while procCopy2.hasMore():
                    skip(procCopy2)

            with let:
                pd = takeProcDecl(c)
            echo("pd=", symName(pd.name), " ", typeKind(pd.params), " ",
                 typeKind(pd.returnType), " ", substructureKind(pd.pragmas), " ",
                 stmtKind(pd.body))
            with var:
                paramsCur = pd.params.copy()
            for _ in loopInto(paramsCur, LengType.ParamsT):
                with let:
                    param = takeParamDecl(paramsCur)
                    elem = elementType(param.typ)
                echo("param=", symName(param.name), " ", kind(param.pragmas),
                     " ", typeKind(param.typ), " elem=", typeKind(elem))
            with var:
                procPragmas = pd.pragmas.copy()
            with into(procPragmas, LengOther.PragmasU):
                echo("proc pragma1=", pragmaKind(procPragmas))
                skip(procPragmas, LengPragma.InlineP)
                echo("proc callconv=", callConvKind(procPragmas))
                skip(procPragmas)

            # 4. ProctypeT via takeProcType
            with let:
                pt2 = takeProcType(c)
            echo("pt2=", typeKind(pt2.params), " ", typeKind(pt2.returnType),
                 " ", substructureKind(pt2.pragmas))

            # 5. VarDecl (GvarS and VarS), typeQual, AddrKinds, 2-arg inc
            with let:
                vd1 = takeVarDecl(c)
            with var:
                vt1 = vd1.typ.copy()
                vv1 = vd1.value.copy()
            echo("vd1=", symName(vd1.name), " qual=", typeQual(vt1),
                 " elem=", typeKind(elementType(vt1)),
                 " valKind=", exprKind(vv1), " inAddr=", exprKind(vv1) in AddrKinds)
            inc(vv1, LengExpr.AddrC)
            echo("vd1 target=", symName(vv1), " tagEnumOnSym=", tagEnumOf(vv1))

            with let:
                vd2 = takeVarDecl(c)
            with var:
                vt2 = vd2.typ.copy()
                vv2 = vd2.value.copy()
            echo("vd2=", symName(vd2.name), " qual=", typeQual(vt2),
                 " valKind=", exprKind(vv2), " inAddr=", exprKind(vv2) in AddrKinds)

        endRead(c)

    _runTests()
