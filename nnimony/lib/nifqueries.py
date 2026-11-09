# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lib/nifqueries.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this distribution, for details.

## Small, non-consuming queries over bounded ``nifcore`` cursors.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import assertions
from .nifcore import (
    childCursor, Cursor, cursorTagId, endRead, kind, NifKind, skip, strVal,
    tags)
from . import nifcore


@dispatch
def tagName(cursor: Cursor) -> string:
    """{.noSideEffect, inline.}"""
    ## Returns the textual tag at ``cursor``.
    assert kind(cursor) == NifKind.TagLit
    return tags(cursor).tagName(cursorTagId(cursor))


def tagIs(cursor: Cursor, name: string) -> bool:
    """{.noSideEffect, inline.}"""
    ## Tests a cursor's tag without exposing its per-buffer tag pool.
    return not cursor.cursorIsNil() and kind(cursor) == NifKind.TagLit and tagName(cursor) == name


def findChildTag(node: Cursor, name: string) -> Cursor:
    ## Finds the first direct child with tag ``name``.
    result = default(Cursor)
    if kind(node) != NifKind.TagLit:
        return result
    with var:
        children = childCursor(node)
    while children.hasMore():
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
    while children.hasMore():
        if tagIs(children, name):
            return children
        if kind(children) == NifKind.TagLit:
            with let:
                nested = findDescendantTag(children, name)
            if not nested.cursorIsNil():
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
    while children.hasMore():
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
    while children.hasMore():
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
        root = tree.beginRead()
    doAssert(tagIs(root, string("root")))
    with let:
        direct = findChildTag(root, string("direct"))
    doAssert(tagIs(direct, string("direct")))
    doAssert(strVal(findChildKind(direct, NifKind.StrLit)) == "first")
    doAssert(strVal(findLastChildKind(direct, NifKind.StrLit)) == "last")
    doAssert(tagIs(findDescendantTag(root, string("target")), string("target")))
    doAssert(findChildTag(root, string("missing")).cursorIsNil())
    endRead(root)

if comptime(__name__ == "__main__"):
    def show(title: string, c: Cursor):
        """The cursor a query returned: nil, or its kind and text."""
        if c.cursorIsNil():
            echo(title, ": nil")
        else:
            echo(title, ": ", kind(c), " ", toString(c, includeLineInfo=False))

    def addedTests():
        with var:
            t = parseFromBuffer(string(
                "(top a \"s1\" 12 (x (y \"deep\" (z 3)) \"s2\") (y 7) \"s3\" (x 'c') ident2 -4)"), string("q"))
        with var:
            top = t.beginRead()
        echo("tagName(top) = ", tagName(top))
        echo("tagIs top/top = ", tagIs(top, string("top")), ", top/x = ", tagIs(top, string("x")))
        show(string("findChildTag x"), findChildTag(top, string("x")))
        show(string("findChildTag y"), findChildTag(top, string("y")))
        show(string("findChildTag z (only nested)"), findChildTag(top, string("z")))
        show(string("findChildTag missing"), findChildTag(top, string("missing")))
        show(string("findDescendantTag y"), findDescendantTag(top, string("y")))
        show(string("findDescendantTag z"), findDescendantTag(top, string("z")))
        show(string("findDescendantTag missing"), findDescendantTag(top, string("missing")))
        show(string("findChildKind StrLit"), findChildKind(top, NifKind.StrLit))
        show(string("findChildKind IntLit"), findChildKind(top, NifKind.IntLit))
        show(string("findChildKind Ident"), findChildKind(top, NifKind.Ident))
        show(string("findChildKind TagLit"), findChildKind(top, NifKind.TagLit))
        show(string("findChildKind FloatLit"), findChildKind(top, NifKind.FloatLit))
        show(string("findLastChildKind StrLit"), findLastChildKind(top, NifKind.StrLit))
        show(string("findLastChildKind TagLit"), findLastChildKind(top, NifKind.TagLit))
        show(string("findLastChildKind IntLit"), findLastChildKind(top, NifKind.IntLit))
        show(string("findLastChildKind CharLit"), findLastChildKind(top, NifKind.CharLit))
        # queries on an atom find nothing; tagIs on an atom and on a nil cursor is false
        with let:
            atom = findChildKind(top, NifKind.StrLit)
        echo("tagIs atom = ", tagIs(atom, string("s1")))
        show(string("findChildTag on atom"), findChildTag(atom, string("x")))
        show(string("findDescendantTag on atom"), findDescendantTag(atom, string("x")))
        show(string("findChildKind on atom"), findChildKind(atom, NifKind.StrLit))
        show(string("findLastChildKind on atom"), findLastChildKind(atom, NifKind.StrLit))
        with let:
            nilCursor = default(Cursor)
        echo("tagIs nil = ", tagIs(nilCursor, string("top")))
        # the queries don't consume: `top` is still at the tree's head
        echo("top after the queries: ", tagName(top), " ", top.cursorIsNil())
        endRead(top)

    addedTests()
