# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/nifler2/linkedtok.nim
# ///
#
#
#           Nifler2: Nim to NIF
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## The tree the parser builds, as links rather than as packed tokens.
##
## `nifcore.TokenBuf` is the right shape for a tree that is *read*: a flat
## array of `NifToken`, a subtree spanned by a jump field, `skip` an O(1)
## pointer bump. It is the wrong shape for a tree that is still being
## *rewritten*, which is what a parser for Nim's grammar does on almost every
## node -- `a + b` has to put the operator in front of an operand that is
## already written, a declaration with three names fans out into three nodes,
## a trailing `do` block moves inside the call in front of it. Against a flat
## array each of those is a memmove of the region since the mark, and reading
## the region back means a `Cursor`, which mints a `CursorOwner` header for
## the buffer and frees it again on the next append.
##
## Here a node is a cell: `down` is its first child, `next` its next sibling.
## Wrapping a run of siblings in a new tag, inserting an operator in front of
## one, moving the last child to the front -- all are pointer assignments that
## touch a constant number of cells, whatever the size of the subtree.
##
## What does NOT change is the atoms. A `payload` is a `nifcore.NifToken`
## built by nifcore's own constructors, so a tag is still a `TagId` and a name
## is still a `StrId` interned in the same `Pool`: only the wiring is local to
## nifler2. The one thing that does not fit in a token's 28-bit payload is a
## numeric literal, which nifcore spreads over up to three chained tokens; a
## cell keeps the value in `wide` instead and `flatten` hands it back to
## nifcore's chaining writer untouched.
##
## Cells come from a bump arena. Allocation is a pointer increment, and the
## whole tree is released by freeing the blocks -- there is nothing per-cell
## to run, which is what lets the rewrites drop subtrees on the floor instead
## of splicing them out.

# A cell links to cells that may not be there: `down` and `next` are nil at
# the edges of the tree, which is the whole point of the representation.

from __future__ import annotations
from nimic.ntypes import *

pragma("feature: \"lenientnils\"")

from nimic.std import assertions
from ..lib.nifpools import (
    addCharLit, addDotToken, addFloatLit, addIdent, addIntLit, addParLe, addParRi, addStrLit, addUIntLit,
    floatVal, intVal, kind, KindBits, NifKind, NifLineInfo, NifToken, Pool, StrId, strId, TagId, TagMask,
    TagShift, TokenBuf, uintVal)
from ..lib import nifpools
export(nifpools)


class LinkedToken(Object):
    payload: NifToken  ## kind plus the nifcore id: `TagId`, `StrId`,
                       ## a character, or a bare kind when the value
                       ## lives in `wide`
    info: NifLineInfo
    wide: uint64  ## `IntLit`/`UIntLit`/`FloatLit` only: the value,
                  ## which does not fit a token payload
    down: Node  ## first child; `nil` for an atom
    next: Node  ## next sibling

@ptr
class Node(LinkedToken):
    pass


with const:
    _BlockSize = 1024  ## cells per arena block


class Arena(Object):
    ## A bump allocator for cells. `blocks` only ever grows; `used` is the
    ## high-water mark inside the last block.
    _blocks: seq[ptr[UncheckedArray[LinkedToken]]]
    _used: nint

    def destroy(a: mut @ Arena):
        ## Frees every cell at once. Nothing is walked and no cell has a hook to
        ## run, so a tree of any shape costs one `dealloc` per block.
        for i in range(a._blocks.len):
            dealloc(a._blocks[i])
        a._blocks.setLen(0)
        a._used = _BlockSize

    def cellCount(a: Arena) -> nint:
        """{.inline.}"""
        ## Cells handed out so far: a size hint for whoever renders the tree.
        return 0 if a._blocks.len == 0 else (a._blocks.len - 1) * _BlockSize + a._used

    def alloc(a: mut @ Arena, payload: NifToken, info: NifLineInfo) -> Node:
        if a._used >= _BlockSize:
            a._blocks.add(cast[ptr[UncheckedArray[LinkedToken]]](alloc(sizeof(LinkedToken) * _BlockSize)))
            a._used = 0
        result = addr(a._blocks[a._blocks.len - 1][a._used])
        a._used += 1
        result.payload = payload
        result.info = info
        result.wide = u64(0)
        result.down = None
        result.next = None
        return result

    def allocWide(a: mut @ Arena, k: NifKind, v: uint64, info: NifLineInfo) -> Node:
        ## A numeric literal: the kind alone in the payload, the bits in `wide`.
        result = a.alloc(NifToken(uint32(k)), info)
        result.wide = v
        return result

    def copyTree(a: mut @ Arena, n: Node) -> Node:
        ## A fresh, unlinked copy of the subtree at `n`. Needed where one parsed
        ## tree ends up in more than one place -- the shared type and value of
        ## `var a, b: int` -- because a cell carries its own `next` and so can sit
        ## in exactly one sibling chain.
        if isNil(n): return None
        result = a.alloc(n.payload, n.info)
        result.wide = n.wide
        with var:
            src = n.down
            prev: Node = None
        while not isNil(src):
            with let:
                c = a.copyTree(src)
            if isNil(prev): result.down = c
            else: prev.next = c
            prev = c
            src = src.next
        return result


def initArena() -> Arena:
    return Arena(_blocks=seq[ptr[UncheckedArray[LinkedToken]]]([]), _used=_BlockSize)  ## forces the first `alloc` to grow

# --------------------------------------------------------------- inspection


@dispatch
def kind(n: Node) -> NifKind:
    """{.inline.}"""
    return kind(n.payload)


def tag(n: Node) -> TagId:
    """{.inline.}"""
    ## Only for a `TagLit`. The jump field of the payload is not maintained
    ## here -- `down` is the structure -- so it is masked out.
    return TagId((uint32(n.payload) >> TagShift) & TagMask)


@dispatch
def strId(n: Node) -> StrId:
    """{.inline.}"""
    ## Only for an `Ident` or a `StrLit`: cells always intern, never inline.
    ## `identToken`/`strLitToken` put the id in bit 1 upward; bit 0 is the
    ## inline/pool-ref flag, and a cell always interns.
    return StrId((uint32(n.payload) >> KindBits) >> 1)


def charVal(n: Node) -> char:
    """{.inline.}"""
    return char(uint32(n.payload) >> KindBits)


@dispatch
def intVal(n: Node) -> int64:
    """{.inline.}"""
    return cast[int64](n.wide)


@dispatch
def uintVal(n: Node) -> uint64:
    """{.inline.}"""
    return n.wide.copy()


@dispatch
def floatVal(n: Node) -> float64:
    """{.inline.}"""
    return cast[float64](n.wide)


def isEmpty(n: Node) -> bool:
    """{.inline.}"""
    ## The `.` that stands for an absent child.
    return not isNil(n) and kind(n.payload) == NifKind.DotToken


def childCount(n: Node) -> nint:
    result = 0
    with var:
        k = n.down
    while not isNil(k):
        result += 1
        k = k.next
    return result

# --------------------------------------------------------------- copying

# --------------------------------------------------------------- flattening


def _flattenOne(dest: mut @ TokenBuf, n: Node, pool: Pool):
    ## A name goes back through the *string* builder, not through the `StrId`
    ## one: the latter reads nifpools' global pool, and a plugin parses into its
    ## own. The builder then re-applies nifcore's inline rule, so the bytes are
    ## the ones a `TokenBuf` written directly would have had.
    match kind(n.payload):
        case NifKind.TagLit:
            addParLe(dest, tag(n), n.info)
            with var:
                k = n.down
            while not isNil(k):
                _flattenOne(dest, k, pool)
                k = k.next
            addParRi(dest)
        case NifKind.DotToken:
            addDotToken(dest, n.info)
        case NifKind.Ident:
            addIdent(dest, pool.strings[strId(n)], n.info)
        case NifKind.StrLit:
            addStrLit(dest, pool.strings[strId(n)], n.info)
        case NifKind.CharLit:
            addCharLit(dest, charVal(n), n.info)
        case NifKind.IntLit:
            addIntLit(dest, intVal(n), n.info)
        case NifKind.UIntLit:
            addUIntLit(dest, uintVal(n), n.info)
        case NifKind.FloatLit:
            addFloatLit(dest, floatVal(n), n.info)
        case _:
            raiseAssert(string("linkedtok: cannot flatten ") + str(kind(n.payload)))


def flatten(dest: mut @ TokenBuf, first: Node, pool: Pool):
    ## Writes the sibling chain starting at `first` into `dest` as ordinary
    ## packed tokens, jumps and all -- nifcore's own `closeTag` computes those.
    ## This is the bridge back for everything that reads a `TokenBuf`: the
    ## plugin entry point, and `nifler2 tree`.
    with var:
        n = first
    while not isNil(n):
        _flattenOne(dest, n, pool)
        n = n.next
