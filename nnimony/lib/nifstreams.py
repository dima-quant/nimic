# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/nifstreams.nim
# ///
## nifstreams — the classic NIF streaming surface, kept ONLY for external
## consumers: the Nim compiler's IC modules (ast2nif / deps / modulegraphs /
## pipelines under `dist/nimony`) import this module and must keep compiling
## unchanged. Nimony's own code imports nifpools (via nifprelude) and must
## never import this file.
##
## Everything here is an honest adapter, not a fake:
## * Floats get a REAL interning pool: `pool.floats.getOrIncl` returns a
##   `FloatId` index, `floatToken` packs it into a genuine `FloatLit` NifToken
##   (transit-only: it must never enter a TokenBuf, whose float encoding is
##   inline multi-token), and `pool.floats[t.floatId]` decodes it — lossless.
## * `Stream`/`next` wrap the textual nifreader; the unified NifKind has real
##   `ParLe`/`ParRi`/`EofToken` members, so structural scanners (deps.nim)
##   see the exact classic kinds. Ident/StringLit/Symbol payloads are interned
##   into the global `pool`, so `pool.strings[t.litId]` works as before.
##   SYMBOLS are stored taken apart now (nimony#2457), but `pool.syms` still
##   answers the three questions this surface ever asked of it --
##   `getOrIncl(name)`, `[id]`, `getKeyId(name)` -- through `nifcore.SymPool`.
##   The spellings below are deliberately the classic ones: the Nim compiler
##   ships its own copy of this file, so what compiles here compiles there.
##   Number tokens keep their KIND only (a 4-byte token cannot always carry
##   the value); classic scanners never read those payloads.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.tables import *
from .nifpools import (
    addIntLit, buildTree, charToken, childCursor, createTokenBuf, Cursor, cursorTagId,
    dotToken, endRead, ErrT, getKeyId, getOrIncl, globalTags, identToken, info, int28Token, intVal, kind, KindBits,
    NifKind, NifToken, NoNifLineInfo, parseFromBuffer, Pool, pool, registerTag, soperand, StrId,
    strId, strLitToken, symdefToken, SymId, symId, syms, symToken, tagId, tagLitToken, tags, TokenBuf, toString,
    uintVal, uoperand, writeFile)
from . import nifpools
# `except`: the frontend went all-NifLineInfo; the classic side keeps speaking
# PackedLineInfo, so nifpools' same-name/same-params variants must not leak
# through (`info(n: NifToken)` differs only in return type, `NoLineInfo` is a
# same-name const of a different type — either would be ambiguous or wrong for
# ast2nif). The classic replacements are defined below / come from lineinfos.
exportExcept(nifpools, "info", "NoLineInfo")
from .lineinfos import isValid, LineInfoManager, PackedLineInfo, unpack
from . import lineinfos
export(lineinfos)

importFrom(".nifreader", "Reader", "ExpandedToken", "decodeStr")

# ── Classic names the Nim compiler side still uses ───────────────────────

PackedToken = NifToken  ## ast2nif still says PackedToken

# Raw payload decodes, sound ONLY on this surface. Every token here comes from
# `next` or the classic `symToken`/`strToken`/`identToken` constructors, which
# intern EVERY literal — including names of at most `StrInlineMaxLen` bytes,
# which the nifcore builders would instead store inside the token. On such an
# inline token the payload is packed bytes, not an id, so nifpools (nimony's own
# surface, where buffers come from the builders) deliberately has no equivalent:
# there it must go through a `Cursor`, which handles both encodings.


@dispatch
def litId(n: NifToken) -> StrId:
    """{.inline.}"""
    return StrId(uoperand(n) >> u32(1))


@dispatch
def symId(n: NifToken) -> SymId:
    """{.inline.}"""
    return SymId(uoperand(n) >> u32(1))


@dispatch
def litId(c: Cursor) -> StrId:
    """{.inline.}"""
    return strId(c)


def firstSon(n: Cursor) -> Cursor:
    """{.inline.}"""
    return childCursor(n)


with var:
    lineMan: LineInfoManager = LineInfoManager()
    ## The classic packed line-info side channel (`pool.man`). Frontend code no
    ## longer uses it — it lives here purely for ast2nif's writer, which packs
    ## `TLineInfo` into `PackedLineInfo` and unpacks on emit.


@template
def files(p: Pool) -> untyped:
    return p.filenames


@template
def tags(p: Pool) -> untyped:
    return globalTags.tags


@template
def man(p: Pool) -> untyped:
    return lineMan


@dispatch
def info(n: NifToken) -> PackedLineInfo:
    """{.inline.}"""
    return lineinfos.NoLineInfo
    ## Classic tokens carried their line info inline; a bare 4-byte nifcore
    ## token cannot, so reading it back yields `NoLineInfo` (ast2nif's
    ## `emitInfo(t.info)` then emits nothing — matching the writer, which
    ## attaches real positions at the builder level instead).


@dispatch
def info(c: Cursor) -> PackedLineInfo:
    """{.inline.}"""
    ## Classic packed view of a cursor's line info (ast2nif shadows this with
    ## its own NifLineInfo template; kept for any other classic reader).
    with let:
        li = c.rawLineInfo()
    if isValid(li.file): return lineMan.pack(li.file, li.line, li.col)
    else: return lineinfos.NoLineInfo


@distinct
class IntId(int64):  ## value carriers (nifcore stores inline)
    def __eq__(a: IntId, b: IntId) -> bool:
        """{.borrow.}"""
        return super().__eq__(b)


@distinct
class UIntId(uint64):
    def __eq__(a: UIntId, b: UIntId) -> bool:
        """{.borrow.}"""
        return super().__eq__(b)


## Identity proxies: the id already carries the value, `[]` returns it.
class IntegersProxy(Object):
    @template
    def __getitem__(x: IntegersProxy, id: IntId) -> int64:
        return int64(id)

    # nifcore stores integers inline: the "id" is the value itself.
    @template
    def getOrIncl(x: IntegersProxy, v: int64) -> IntId:
        return IntId(v)


class UIntegersProxy(Object):
    @template
    def __getitem__(x: UIntegersProxy, id: UIntId) -> uint64:
        return uint64(id)

    @template
    def getOrIncl(x: UIntegersProxy, v: uint64) -> UIntId:
        return UIntId(v)


@template
def integers(p: Pool) -> IntegersProxy:
    return IntegersProxy()


@template
def uintegers(p: Pool) -> UIntegersProxy:
    return UIntegersProxy()


@dispatch
def intId(n: NifToken) -> IntId:
    """{.inline.}"""
    return IntId(soperand(n))


@dispatch
def uintId(n: NifToken) -> UIntId:
    """{.inline.}"""
    return UIntId(uoperand(n))


@dispatch
def intId(c: Cursor) -> IntId:
    """{.inline.}"""
    return IntId(intVal(c))


@dispatch
def uintId(c: Cursor) -> UIntId:
    """{.inline.}"""
    return UIntId(uintVal(c))


@dispatch
def addIntLit(dest: mut @ TokenBuf, id: IntId, info: PackedLineInfo):
    dest.addIntLit(int64(id))
    if isValid(info):
        with let:
            u = unpack(lineMan, info)
        dest.appendLineInfo(u.file, u.line, u.col)

# Classic single-token constructors with a (dropped) line-info argument.


def strToken(s: StrId, info: PackedLineInfo) -> NifToken:
    """{.inline.}"""
    return strLitToken(s)


@dispatch
def symToken(id: SymId, info: PackedLineInfo) -> NifToken:
    """{.inline.}"""
    return symToken(id)


@dispatch
def identToken(id: StrId, info: PackedLineInfo) -> NifToken:
    """{.inline.}"""
    return identToken(id)


@dispatch
def dotToken(info: PackedLineInfo) -> NifToken:
    """{.inline.}"""
    return dotToken()


@dispatch
def charToken(ch: char, info: PackedLineInfo) -> NifToken:
    """{.inline.}"""
    return charToken(ch)

# ── Classic interned float literals (ast2nif) ────────────────────────────


@distinct
class FloatId(uint32):  ## 1-based index into the global float pool
    def __eq__(a: FloatId, b: FloatId) -> bool:
        """{.borrow.}"""
        return super().__eq__(b)

    def floatToken(id: FloatId, info: PackedLineInfo) -> NifToken:
        """{.inline.}"""
        ## Transit-only token: carries the pool index so the receiver can decode it
        ## via `pool.floats[t.floatId]`. It must never be appended to a TokenBuf
        ## (nifcore stores floats inline as a multi-token encoding); the line info
        ## is dropped like in the other classic token constructors.
        return NifToken((uint32(id) << KindBits) | uint32(NifKind.FloatLit))


class FloatPool(Object):
    values: seq[float64]
    lookup: Table[uint64, uint32]  # bit pattern -> 1-based id

    def getOrIncl(fp: mut @ FloatPool, v: float64) -> FloatId:
        with let:
            bits = cast[uint64](v)
        with let:
            existing = fp.lookup.getOrDefault(bits, u32(0))
        if existing != u32(0):
            result = FloatId(existing)
        else:
            fp.values.add(v)
            with let:
                id = uint32(fp.values.len)
            fp.lookup[bits] = id
            result = FloatId(id)
        return result

    def __getitem__(fp: FloatPool, id: FloatId) -> float64:
        """{.inline.}"""
        return fp.values[nint(uint32(id)) - 1]


with var:
    globalFloats: FloatPool = FloatPool()


@template
def floats(p: Pool) -> mut @ FloatPool:
    return globalFloats


def floatId(n: NifToken) -> FloatId:
    """{.inline.}"""
    return FloatId(uoperand(n))

# ── Classic streaming text reader (deps.nim) ─────────────────────────────


class Stream(Object):
    r: Reader

    def close(s: mut @ Stream):
        nifreader.close(s.r)

    def next(s: mut @ Stream) -> NifToken:
        ## One classic packed token per call. Pool-referencing kinds are interned
        ## into the global `pool`/`globalTags`, so `.litId`/`.tagId` accessors and
        ## `pool.strings[...]`/`pool.tags[...]` lookups behave exactly as classic
        ## nifstreams did. Kinds without a pool payload come back kind-only.
        with var:
            t = default(ExpandedToken)
        nifreader.next(s.r, t)
        match t.tk:
            case NifKind.ParLe:
                result = tagLitToken(registerTag(globalTags, decodeStr(s.r, t)))
            case NifKind.Ident:
                result = identToken(getOrIncl(pool.strings, decodeStr(s.r, t)))
            case NifKind.StrLit:
                result = strLitToken(getOrIncl(pool.strings, decodeStr(s.r, t)))
            case NifKind.Symbol:
                result = symToken(syms(pool).getOrIncl(decodeStr(s.r, t)))
            case NifKind.SymbolDef:
                result = symdefToken(syms(pool).getOrIncl(decodeStr(s.r, t)))
            case _:
                # ParRi/EofToken/DotToken/CharLit/numbers: correct kind, no payload.
                result = NifToken(uint32(t.tk))
        return result


@dispatch
def open(filename: string) -> Stream:
    return Stream(r=nifreader.open(filename))


if comptime(__name__ == "__main__"):
    from nimic.std.formatfloat import *
    importFrom("nimic.std.os", "getTempDir", "removeFile")

    def _testStream():
        # a small .nif file under getTempDir(), read back token by token
        with var:
            src = parseFromBuffer(string("(stmts :x.0.m foo \"str lit\" 'c' . 12 -3 4u 1.5 x.0.m (inner))"),
                                  string("m"))
        with let:
            path = getTempDir() + string("nifstreams_test.nif")
        writeFile(src, path)
        with var:
            s = open(path)
        with var:
            t = s.next()
        while kind(t) != NifKind.EofToken:
            with let:
                k = kind(t)
            if k == NifKind.TagLit:
                echo("  ", k, " ", tags(pool)[tagId(t)])
            elif k == NifKind.Ident or k == NifKind.StrLit:
                echo("  ", k, " ", pool.strings[litId(t)])
            elif k == NifKind.Symbol or k == NifKind.SymbolDef:
                echo("  ", k, " ", syms(pool)[symId(t)],
                     " key ", syms(pool).getKeyId(syms(pool)[symId(t)]) == symId(t))
            else:
                echo("  ", k, " (kind only) ", uoperand(t))
            echo("    info valid: ", isValid(info(t)), " ", info(t) == lineinfos.NoLineInfo)
            t = s.next()
        echo("  ", kind(t))
        s.close()
        removeFile(path)

    def _testFloats():
        with let:
            a = floats(pool).getOrIncl(1.5)
            b = floats(pool).getOrIncl(1.5)
            z = floats(pool).getOrIncl(0.0)
            nz = floats(pool).getOrIncl(-0.0)
            big = floats(pool).getOrIncl(1e100)
        echo("float ids: ", uint32(a), " ", uint32(b), " ", uint32(z), " ",
             uint32(nz), " ", uint32(big))
        echo("same value same id: ", a == b, " -0.0 vs 0.0 differ: ", not (z == nz))
        echo("decoded: ", floats(pool)[a], " ", floats(pool)[z], " ",
             floats(pool)[nz], " ", floats(pool)[big])
        echo("globalFloats shared: ", globalFloats[big])
        with let:
            ft = big.floatToken(lineinfos.NoLineInfo)
        echo("floatToken: ", kind(ft), " ", floatId(ft) == big, " ",
             floats(pool)[floatId(ft)])

    def _testIntegers():
        with let:
            i = integers(pool).getOrIncl(int64(-7))
            u = uintegers(pool).getOrIncl(high(uint64))
        echo("integers: ", integers(pool)[i], " ", uintegers(pool)[u])
        echo("IntId ==: ", i == IntId(-7), " ", i == IntId(7), " UIntId ==: ",
             u == UIntId(high(uint64)))
        with let:
            tok = int28Token(int32(-5), NoNifLineInfo)
        echo("intId(token): ", int64(intId(tok)))
        with var:
            b = parseFromBuffer(string("(nums -42 18446744073709551615u)"), string("m"))
        with var:
            c = b.beginRead()
        c.inc()
        echo("intId(cursor): ", int64(intId(c)))
        c.inc()
        echo("uintId(cursor): ", uint64(uintId(c)))
        endRead(c)

    def _testInfo():
        echo("info(token) valid: ", isValid(info(dotToken())))
        with var:
            b = parseFromBuffer(string("(stmts@3,7,a.nim x (call y))"), string("m"))
        with var:
            c = b.beginRead()
        with let:
            pi = info(c)
        with let:
            u = unpack(lineMan, pi)
        echo("info(cursor) valid: ", isValid(pi), " ", files(pool)[u.file],
             " line ", u.line, " col ", u.col)
        echo("man is lineMan: ", man(pool).memSize() == lineMan.memSize())
        with var:
            ch2 = firstSon(c)
        echo("firstSon: ", toString(ch2, False), " litId ", pool.strings[litId(ch2)])
        c.inc()
        c.inc()
        echo("nifcore tags(c) still: ", tags(c).tags[cursorTagId(c)])
        endRead(c)
        with var:
            b0 = parseFromBuffer(string("(stmts 1 2)"), string("m"))
        with var:
            c0 = b0.beginRead()
        echo("info(cursor) without line info valid: ", isValid(info(c0)))
        endRead(c0)

    def _testAddIntLit():
        with let:
            fid = getOrIncl(pool.filenames, string("b.nim"))
        with let:
            good = lineMan.pack(fid, i32(10), i32(4))
        with var:
            b = createTokenBuf(8)
        with buildTree(b, ErrT, NoNifLineInfo):
            addIntLit(b, IntId(99), good)
            addIntLit(b, IntId(-1), lineinfos.NoLineInfo)
        echo("addIntLit: ", toString(b, False))

    def _testConstructors():
        with let:
            sid = getOrIncl(pool.strings, string("hello"))
            yid = syms(pool).getOrIncl(string("sym.1.m"))
        with let:
            st = strToken(sid, lineinfos.NoLineInfo)
            sy = symToken(yid, lineinfos.NoLineInfo)
            it = identToken(sid, lineinfos.NoLineInfo)
            dt = dotToken(lineinfos.NoLineInfo)
            ct = charToken(ch("q"), lineinfos.NoLineInfo)
        echo("strToken: ", kind(st), " ", pool.strings[litId(st)])
        echo("symToken: ", kind(sy), " ", syms(pool)[symId(sy)])
        echo("identToken: ", kind(it), " ", pool.strings[litId(it)])
        echo("dotToken: ", kind(dt), " ", dt == dotToken())
        echo("charToken: ", kind(ct), " ", uoperand(ct))
        with let:
            pt = PackedToken(st)
        echo("PackedToken: ", pt == st)

    _testStream()
    _testFloats()
    _testIntegers()
    _testInfo()
    _testAddIntLit()
    _testConstructors()
