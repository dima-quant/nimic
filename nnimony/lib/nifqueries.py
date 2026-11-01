# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/nifqueries.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this distribution, for details.

## Small, non-consuming queries over bounded ``nifcore`` cursors.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.assertions import *
from .nifcore import (
    beginRead, childCursor, Cursor, cursorIsNil, cursorTagId, endRead, hasMore, kind, NifKind, skip, strVal, tagName,
    tags)
from . import nifcore


@dispatch
def tagName(cursor: Cursor) -> string:
    """{.noSideEffect, inline.}"""
    ## Returns the textual tag at ``cursor``.
    assert kind(cursor) == NifKind.TagLit
    return tagName(tags(cursor), cursorTagId(cursor))


def tagIs(cursor: Cursor, name: string) -> bool:
    """{.noSideEffect, inline.}"""
    ## Tests a cursor's tag without exposing its per-buffer tag pool.
    return not cursorIsNil(cursor) and kind(cursor) == NifKind.TagLit and tagName(cursor) == name


def findChildTag(node: Cursor, name: string) -> Cursor:
    ## Finds the first direct child with tag ``name``.
    result = default(Cursor)
    if kind(node) != NifKind.TagLit:
        return result
    with var:
        children = childCursor(node)
    while hasMore(children):
        if tagIs(children, name):
            return children
        skip(children)
    return result


def findDescendantTag(node: Cursor, name: string) -> Cursor:
    ## Finds the first descendant with tag ``name`` in depth-first order.
    result = default(Cursor)
    if kind(node) != NifKind.TagLit:
        return result
    with var:
        children = childCursor(node)
    while hasMore(children):
        if tagIs(children, name):
            return children
        if kind(children) == NifKind.TagLit:
            with let:
                nested = findDescendantTag(children, name)
            if not cursorIsNil(nested):
                return nested
        skip(children)
    return result


def findChildKind(node: Cursor, kind: NifKind) -> Cursor:
    ## Finds the first direct child with token ``kind``.
    result = default(Cursor)
    if nifcore.kind(node) != NifKind.TagLit:
        return result
    with var:
        children = childCursor(node)
    while hasMore(children):
        if nifcore.kind(children) == kind:
            return children
        skip(children)
    return result


def findLastChildKind(node: Cursor, kind: NifKind) -> Cursor:
    ## Finds the last direct child with token ``kind``.
    result = default(Cursor)
    if nifcore.kind(node) != NifKind.TagLit:
        return result
    with var:
        children = childCursor(node)
    while hasMore(children):
        if nifcore.kind(children) == kind:
            result = children.copy()
        skip(children)
    return result


if comptime(__name__ == "__main__"):
    from .nifcoreparse import parseFromBuffer, toString

    with var:
        tree = parseFromBuffer(
            string("(root (direct \"first\" \"last\") (nested (target value)))"), string("test"))
    with var:
        root = beginRead(tree)
    doAssert(tagIs(root, string("root")))
    with let:
        direct = findChildTag(root, string("direct"))
    doAssert(tagIs(direct, string("direct")))
    doAssert(strVal(findChildKind(direct, NifKind.StrLit)) == string("first"))
    doAssert(strVal(findLastChildKind(direct, NifKind.StrLit)) == string("last"))
    doAssert(tagIs(findDescendantTag(root, string("target")), string("target")))
    doAssert(cursorIsNil(findChildTag(root, string("missing"))))
    endRead(root)

if comptime(__name__ == "__main__"):
    def _show(title: string, c: Cursor):
        """The cursor a query returned: nil, or its kind and text."""
        if cursorIsNil(c):
            echo(title, string(": nil"))
        else:
            echo(title, string(": "), kind(c), string(" "), toString(c, includeLineInfo=False))

    def _addedTests():
        with var:
            t = parseFromBuffer(string(
                "(top a \"s1\" 12 (x (y \"deep\" (z 3)) \"s2\") (y 7) \"s3\" (x 'c') ident2 -4)"), string("q"))
        with var:
            top = beginRead(t)
        echo(string("tagName(top) = "), tagName(top))
        echo(string("tagIs top/top = "), tagIs(top, string("top")), string(", top/x = "), tagIs(top, string("x")))
        _show(string("findChildTag x"), findChildTag(top, string("x")))
        _show(string("findChildTag y"), findChildTag(top, string("y")))
        _show(string("findChildTag z (only nested)"), findChildTag(top, string("z")))
        _show(string("findChildTag missing"), findChildTag(top, string("missing")))
        _show(string("findDescendantTag y"), findDescendantTag(top, string("y")))
        _show(string("findDescendantTag z"), findDescendantTag(top, string("z")))
        _show(string("findDescendantTag missing"), findDescendantTag(top, string("missing")))
        _show(string("findChildKind StrLit"), findChildKind(top, NifKind.StrLit))
        _show(string("findChildKind IntLit"), findChildKind(top, NifKind.IntLit))
        _show(string("findChildKind Ident"), findChildKind(top, NifKind.Ident))
        _show(string("findChildKind TagLit"), findChildKind(top, NifKind.TagLit))
        _show(string("findChildKind FloatLit"), findChildKind(top, NifKind.FloatLit))
        _show(string("findLastChildKind StrLit"), findLastChildKind(top, NifKind.StrLit))
        _show(string("findLastChildKind TagLit"), findLastChildKind(top, NifKind.TagLit))
        _show(string("findLastChildKind IntLit"), findLastChildKind(top, NifKind.IntLit))
        _show(string("findLastChildKind CharLit"), findLastChildKind(top, NifKind.CharLit))
        # queries on an atom find nothing; tagIs on an atom and on a nil cursor is false
        with let:
            atom = findChildKind(top, NifKind.StrLit)
        echo(string("tagIs atom = "), tagIs(atom, string("s1")))
        _show(string("findChildTag on atom"), findChildTag(atom, string("x")))
        _show(string("findDescendantTag on atom"), findDescendantTag(atom, string("x")))
        _show(string("findChildKind on atom"), findChildKind(atom, NifKind.StrLit))
        _show(string("findLastChildKind on atom"), findLastChildKind(atom, NifKind.StrLit))
        with let:
            nilCursor = default(Cursor)
        echo(string("tagIs nil = "), tagIs(nilCursor, string("top")))
        # the queries don't consume: `top` is still at the tree's head
        echo(string("top after the queries: "), tagName(top), string(" "), cursorIsNil(top))
        endRead(top)

    _addedTests()
