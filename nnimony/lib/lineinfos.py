# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/lineinfos.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

# For the line information we use 32 bits. They are used as follows:
# Bit 0 (AsideBit): If we have inline line information or not.
# If inline line information is not used bit 1 is 0 and
# remaining 30 bits are used as an index into a seq[(FileId, int, int)].
# If bit 1 is 1 then the remaining 30 bits are can store an arbitrary payload.
# This "payload" mechanism is used to attach a token/node to its original index.
# It is used to combine a control flow graph with its original tree-like structure.
#
# We use 10 bits for the "file ID", this means a program can consist of as much
# as 1024 different files. (If it uses more files than that, the overflow bit
# would be set.)
# This means we have 21 bits left to encode the (line, col) pair. We use 7 bits for the column
# so 128 is the limit and 14 bits for the line number.
# The packed representation supports files with up to 16384 lines.
# Keep in mind that whenever any limit is reached the AsideBit is set and the real line
# information is kept in a side channel.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.assertions import *
from nimic.std.hashes import *

with const:
    _AsideBit = 1
    _FileBits = 10
    _LineBits = 14
    _ColBits = 7
    _FileMax = (1 << _FileBits) - 1
    _LineMax = (1 << _LineBits) - 1
    _ColMax = (1 << _ColBits) - 1

if comptime(not defined("nimony")):
    with static:
        assert _AsideBit + _FileBits + _LineBits + _ColBits == 32


@distinct
class PackedLineInfo(uint32):
    def __eq__(a: PackedLineInfo, b: PackedLineInfo) -> bool:
        """{.borrow, noSideEffect.}"""
        return super().__eq__(b)

    def hash(a: PackedLineInfo) -> Hash:
        """{.borrow, noSideEffect.}"""
        return hash(uint32(a))


@distinct
class FileId(uint32):
    def __eq__(a: FileId, b: FileId) -> bool:
        """{.borrow, noSideEffect.}"""
        return super().__eq__(b)

    def hash(a: FileId) -> Hash:
        """{.borrow, noSideEffect.}"""
        return hash(uint32(a))


class LineInfoUnpacked(Object):
    file: FileId
    line: int32
    col: int32
    comment: uint32  ## interned comment id (StrId.uint32); 0 means no comment.
                     ## Stored as raw uint32 to avoid a circular dep on nifstreams' StrId.


class LineInfoManager(Object):
    _aside: seq[LineInfoUnpacked]


with const:
    NoLineInfo = PackedLineInfo(u32(0))
    NoFile = FileId(u32(0))


@dispatch
def isValid(x: PackedLineInfo) -> bool:
    """{.inline.}"""
    return uint32(x) != uint32(NoLineInfo)


@dispatch
def isValid(x: FileId) -> bool:
    """{.inline.}"""
    return x != NoFile


def pack(m: mut @ LineInfoManager, file: FileId, line: int32, col: int32) -> PackedLineInfo:
    if uint32(file) <= uint32(_FileMax) and line <= _LineMax and col <= _ColMax:
        with let:
            col = u32(0) if col < i32(0) else uint32(col)
            line = u32(0) if line < i32(0) else uint32(line)
        # use inline representation:
        result = PackedLineInfo((uint32(file) << u32(1)) | (line << uint32(_AsideBit + _FileBits)) |
            (col << uint32(_AsideBit + _FileBits + _LineBits)))
    else:
        result = PackedLineInfo((m._aside.len << 2) | _AsideBit)
        m._aside.add(LineInfoUnpacked(file=file, line=line, col=col))
    return result


def packWithComment(m: mut @ LineInfoManager, file: FileId, line: int32, col: int32,
                    comment: uint32) -> PackedLineInfo:
    # Like `pack` but also attaches a `#comment#` to the position. Comment-bearing
    # infos always use the aside path (the inline encoding has no room for a
    # comment id). `comment == 0` means no comment — callers should use the plain
    # `pack` in that case.
    if comment == u32(0):
        result = pack(m, file, line, col)
    else:
        result = PackedLineInfo((m._aside.len << 2) | _AsideBit)
        m._aside.add(LineInfoUnpacked(file=file, line=line, col=col, comment=comment))
    return result


def isPayload(i: PackedLineInfo) -> bool:
    """{.inline.}"""
    result = (uint32(i) & u32(3)) == u32(3)
    return result


def unpack(m: LineInfoManager, info: PackedLineInfo) -> LineInfoUnpacked:
    with let:
        i = uint32(info)
    if (i & u32(1)) == u32(0):
        # inline representation:
        result = LineInfoUnpacked(
            file=FileId((i >> u32(1)) & uint32(_FileMax)),
            line=int32((i >> uint32(_AsideBit + _FileBits)) & uint32(_LineMax)),
            col=int32((i >> uint32(_AsideBit + _FileBits + _LineBits)) & uint32(_ColMax))
        )
    elif not isPayload(info):
        result = m._aside[nint(i >> u32(2))]
    else:
        result = LineInfoUnpacked(file=NoFile)
    return result


def stripComment(m: mut @ LineInfoManager, info: PackedLineInfo) -> PackedLineInfo:
    # Return the same file/line/col but with no comment attached. Useful when
    # propagating a parent's info to children for relative-position math:
    # comments are *decorations on a single token*, not inherited by descendants.
    with let:
        raw = unpack(m, info)
    if raw.comment == u32(0):
        result = info
    else:
        result = pack(m, raw.file, raw.line, raw.col)
    return result


def getPayload(i: PackedLineInfo) -> uint32:
    """{.inline.}"""
    assert isPayload(i)
    result = uint32(i) >> u32(2)
    return result


def toPayload(val: uint32) -> PackedLineInfo:
    """{.inline.}"""
    result = PackedLineInfo((val << u32(2)) | u32(3))
    return result


def getFileId(m: LineInfoManager, i: PackedLineInfo) -> FileId:
    result = unpack(m, i).file
    return result


def memSize(m: LineInfoManager) -> nint:
    return m._aside.len


if comptime(__name__ == "__main__" and not defined("nimony")):
    with var:
        m = LineInfoManager(_aside=seq[LineInfoUnpacked]([]))
    for i in range(i32(0), i32(16388)):
        for col in range(i32(0), i32(100)):
            with let:
                packed = pack(m, FileId(1023), i, col)
            assert not isPayload(packed)
            with let:
                u = unpack(m, packed)
            assert u.file == FileId(1023)
            assert u.line == i
            assert u.col == col
    echo(m._aside.len)

    with let:
        i = toPayload(u32(8000))
    assert isPayload(i)
    assert getPayload(i) == u32(8000)


if comptime(__name__ == "__main__"):
    with var:
        mgr = LineInfoManager(_aside=seq[LineInfoUnpacked]([]))
    echo(isValid(NoLineInfo), "|", isValid(NoFile))
    echo(isValid(FileId(u32(1))), "|", isValid(FileId(u32(1023))))

    # Inline bit-field edges: FileId(1023), line 16383, col 127
    with let:
        pInline = pack(mgr, FileId(u32(1023)), i32(16383), i32(127))
        uInline = unpack(mgr, pInline)
    echo(isValid(pInline), "|", isPayload(pInline), "|", uint32(uInline.file), "|", uInline.line, "|", uInline.col, "|", memSize(mgr))

    # Negative line/col clamped to 0 in inline path
    with let:
        pNeg = pack(mgr, FileId(u32(5)), i32(-3), i32(-1))
        uNeg = unpack(mgr, pNeg)
    echo(uint32(uNeg.file), "|", uNeg.line, "|", uNeg.col, "|", memSize(mgr))

    # Overflow edges trigger aside storage (file > 1023, line > 16383, col > 127)
    with let:
        pFileOv = pack(mgr, FileId(u32(1024)), i32(10), i32(20))
        pLineOv = pack(mgr, FileId(u32(1)), i32(16384), i32(20))
        pColOv = pack(mgr, FileId(u32(1)), i32(10), i32(128))
        uFileOv = unpack(mgr, pFileOv)
        uLineOv = unpack(mgr, pLineOv)
        uColOv = unpack(mgr, pColOv)
    echo(uint32(uFileOv.file), "|", uFileOv.line, "|", uFileOv.col, "|", memSize(mgr))
    echo(uint32(uLineOv.file), "|", uLineOv.line, "|", uLineOv.col)
    echo(uint32(uColOv.file), "|", uColOv.line, "|", uColOv.col)

    # packWithComment and stripComment
    with let:
        pNoCmt = packWithComment(mgr, FileId(u32(7)), i32(42), i32(3), u32(0))
        pWithCmt = packWithComment(mgr, FileId(u32(7)), i32(42), i32(3), u32(99))
        uWithCmt = unpack(mgr, pWithCmt)
        pStripped = stripComment(mgr, pWithCmt)
        uStripped = unpack(mgr, pStripped)
    echo(pNoCmt == pStripped, "|", stripComment(mgr, pNoCmt) == pNoCmt)
    echo(uint32(uWithCmt.file), "|", uWithCmt.line, "|", uWithCmt.col, "|", uWithCmt.comment)
    echo(uint32(uStripped.file), "|", uStripped.line, "|", uStripped.col, "|", uStripped.comment)
    echo(uint32(getFileId(mgr, pWithCmt)), "|", memSize(mgr))

    # Payload helpers and unpack of payload
    with let:
        pay0 = toPayload(u32(0))
        payMax = toPayload(u32(123456))
        uPay = unpack(mgr, payMax)
    echo(isPayload(pay0), "|", getPayload(pay0), "|", isPayload(payMax), "|", getPayload(payMax), "|", uint32(uPay.file))

    # Borrowed == and hash
    echo(FileId(u32(42)) == FileId(u32(42)), "|", hash(FileId(u32(42))) == hash(FileId(u32(42))))
    echo(pInline == pInline, "|", hash(pInline) == hash(pInline))
