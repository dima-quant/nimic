# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifstreams.nim
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
from .nifpools import *
from . import nifpools
# `except`: the frontend went all-NifLineInfo; the classic side keeps speaking
# PackedLineInfo, so nifpools' same-name/same-params variants must not leak
# through (`info(n: NifToken)` differs only in return type, `NoLineInfo` is a
# same-name const of a different type — either would be ambiguous or wrong for
# ast2nif). The classic replacements are defined below / come from lineinfos.
exportExcept(nifpools, "info", "NoLineInfo")
from .lineinfos import *
from . import lineinfos
with export:
    lineinfos

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
        li = rawLineInfo(c)
    if isValid(li.file): return pack(lineMan, li.file, li.line, li.col)
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
    addIntLit(dest, int64(id))
    if isValid(info):
        with let:
            u = unpack(lineMan, info)
        appendLineInfo(dest, u.file, u.line, u.col)

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


def floatToken(id: FloatId, info: PackedLineInfo) -> NifToken:
    """{.inline.}"""
    ## Transit-only token: carries the pool index so the receiver can decode it
    ## via `pool.floats[t.floatId]`. It must never be appended to a TokenBuf
    ## (nifcore stores floats inline as a multi-token encoding); the line info
    ## is dropped like in the other classic token constructors.
    return NifToken((uint32(id) << KindBits) | uint32(NifKind.FloatLit))


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
                result = identToken(pool.strings.getOrIncl(decodeStr(s.r, t)))
            case NifKind.StrLit:
                result = strLitToken(pool.strings.getOrIncl(decodeStr(s.r, t)))
            case NifKind.Symbol:
                result = symToken(pool.syms().getOrIncl(decodeStr(s.r, t)))
            case NifKind.SymbolDef:
                result = symdefToken(pool.syms().getOrIncl(decodeStr(s.r, t)))
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
                echo(string("  "), k, string(" "), pool.tags()[tagId(t)])
            elif k == NifKind.Ident or k == NifKind.StrLit:
                echo(string("  "), k, string(" "), pool.strings[litId(t)])
            elif k == NifKind.Symbol or k == NifKind.SymbolDef:
                echo(string("  "), k, string(" "), pool.syms()[symId(t)],
                     string(" key "), pool.syms().getKeyId(pool.syms()[symId(t)]) == symId(t))
            else:
                echo(string("  "), k, string(" (kind only) "), uoperand(t))
            echo(string("    info valid: "), isValid(info(t)), string(" "), info(t) == lineinfos.NoLineInfo)
            t = s.next()
        echo(string("  "), kind(t))
        s.close()
        removeFile(path)

    def _testFloats():
        with let:
            a = pool.floats().getOrIncl(1.5)
            b = pool.floats().getOrIncl(1.5)
            z = pool.floats().getOrIncl(0.0)
            nz = pool.floats().getOrIncl(-0.0)
            big = pool.floats().getOrIncl(1e100)
        echo(string("float ids: "), uint32(a), string(" "), uint32(b), string(" "), uint32(z), string(" "),
             uint32(nz), string(" "), uint32(big))
        echo(string("same value same id: "), a == b, string(" -0.0 vs 0.0 differ: "), not (z == nz))
        echo(string("decoded: "), pool.floats()[a], string(" "), pool.floats()[z], string(" "),
             pool.floats()[nz], string(" "), pool.floats()[big])
        echo(string("globalFloats shared: "), globalFloats[big])
        with let:
            ft = floatToken(big, lineinfos.NoLineInfo)
        echo(string("floatToken: "), kind(ft), string(" "), floatId(ft) == big, string(" "),
             pool.floats()[floatId(ft)])

    def _testIntegers():
        with let:
            i = pool.integers().getOrIncl(int64(-7))
            u = pool.uintegers().getOrIncl(high(uint64))
        echo(string("integers: "), pool.integers()[i], string(" "), pool.uintegers()[u])
        echo(string("IntId ==: "), i == IntId(-7), string(" "), i == IntId(7), string(" UIntId ==: "),
             u == UIntId(high(uint64)))
        with let:
            tok = int28Token(int32(-5), NoNifLineInfo)
        echo(string("intId(token): "), int64(intId(tok)))
        with var:
            b = parseFromBuffer(string("(nums -42 18446744073709551615u)"), string("m"))
        with var:
            c = b.beginRead()
        inc(c)
        echo(string("intId(cursor): "), int64(intId(c)))
        inc(c)
        echo(string("uintId(cursor): "), uint64(uintId(c)))
        c.endRead()

    def _testInfo():
        echo(string("info(token) valid: "), isValid(info(dotToken())))
        with var:
            b = parseFromBuffer(string("(stmts@3,7,a.nim x (call y))"), string("m"))
        with var:
            c = b.beginRead()
        with let:
            pi = info(c)
        with let:
            u = unpack(lineMan, pi)
        echo(string("info(cursor) valid: "), isValid(pi), string(" "), pool.files()[u.file],
             string(" line "), u.line, string(" col "), u.col)
        echo(string("man is lineMan: "), memSize(pool.man()) == memSize(lineMan))
        with var:
            ch2 = firstSon(c)
        echo(string("firstSon: "), toString(ch2, False), string(" litId "), pool.strings[litId(ch2)])
        inc(c)
        inc(c)
        echo(string("nifcore tags(c) still: "), tags(c).tags[cursorTagId(c)])
        c.endRead()
        with var:
            b0 = parseFromBuffer(string("(stmts 1 2)"), string("m"))
        with var:
            c0 = b0.beginRead()
        echo(string("info(cursor) without line info valid: "), isValid(info(c0)))
        c0.endRead()

    def _testAddIntLit():
        with let:
            fid = pool.filenames.getOrIncl(string("b.nim"))
        with let:
            good = pack(lineMan, fid, i32(10), i32(4))
        with var:
            b = createTokenBuf(8)
        with buildTree(b, ErrT, NoNifLineInfo):
            addIntLit(b, IntId(99), good)
            addIntLit(b, IntId(-1), lineinfos.NoLineInfo)
        echo(string("addIntLit: "), toString(b, False))

    def _testConstructors():
        with let:
            sid = pool.strings.getOrIncl(string("hello"))
            yid = pool.syms().getOrIncl(string("sym.1.m"))
        with let:
            st = strToken(sid, lineinfos.NoLineInfo)
            sy = symToken(yid, lineinfos.NoLineInfo)
            it = identToken(sid, lineinfos.NoLineInfo)
            dt = dotToken(lineinfos.NoLineInfo)
            ct = charToken(ch("q"), lineinfos.NoLineInfo)
        echo(string("strToken: "), kind(st), string(" "), pool.strings[litId(st)])
        echo(string("symToken: "), kind(sy), string(" "), pool.syms()[symId(sy)])
        echo(string("identToken: "), kind(it), string(" "), pool.strings[litId(it)])
        echo(string("dotToken: "), kind(dt), string(" "), dt == dotToken())
        echo(string("charToken: "), kind(ct), string(" "), uoperand(ct))
        with let:
            pt = PackedToken(st)
        echo(string("PackedToken: "), pt == st)

    _testStream()
    _testFloats()
    _testIntegers()
    _testInfo()
    _testAddIntLit()
    _testConstructors()
