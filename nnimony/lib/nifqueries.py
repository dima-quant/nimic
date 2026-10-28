# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/nifqueries.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this distribution, for details.

## Small, non-consuming queries over bounded ``nifcore`` cursors.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.assertions import *
from .nifcore import *


@dispatch
def tagName(cursor: Cursor) -> string:
    """{.noSideEffect, inline.}"""
    ## Returns the textual tag at ``cursor``.
    assert kind(cursor) == NifKind.TagLit
    return tags(cursor).tagName(cursorTagId(cursor))


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
        children = node.childCursor()
    while hasMore(children):
        if children.tagIs(name):
            return children
        skip(children)
    return result


def findDescendantTag(node: Cursor, name: string) -> Cursor:
    ## Finds the first descendant with tag ``name`` in depth-first order.
    result = default(Cursor)
    if kind(node) != NifKind.TagLit:
        return result
    with var:
        children = node.childCursor()
    while hasMore(children):
        if children.tagIs(name):
            return children
        if kind(children) == NifKind.TagLit:
            with let:
                nested = children.findDescendantTag(name)
            if not cursorIsNil(nested):
                return nested
        skip(children)
    return result


def findChildKind(node: Cursor, kind: NifKind) -> Cursor:
    ## Finds the first direct child with token ``kind``.
    result = default(Cursor)
    if node.kind() != NifKind.TagLit:
        return result
    with var:
        children = node.childCursor()
    while hasMore(children):
        if children.kind() == kind:
            return children
        skip(children)
    return result


def findLastChildKind(node: Cursor, kind: NifKind) -> Cursor:
    ## Finds the last direct child with token ``kind``.
    result = default(Cursor)
    if node.kind() != NifKind.TagLit:
        return result
    with var:
        children = node.childCursor()
    while hasMore(children):
        if children.kind() == kind:
            result = children.copy()
        skip(children)
    return result


if comptime(__name__ == "__main__"):
    from .nifcoreparse import *

    with var:
        tree = parseFromBuffer(
            string("(root (direct \"first\" \"last\") (nested (target value)))"), string("test"))
    with var:
        root = tree.beginRead()
    doAssert(root.tagIs(string("root")))
    with let:
        direct = root.findChildTag(string("direct"))
    doAssert(direct.tagIs(string("direct")))
    doAssert(strVal(direct.findChildKind(NifKind.StrLit)) == string("first"))
    doAssert(strVal(direct.findLastChildKind(NifKind.StrLit)) == string("last"))
    doAssert(root.findDescendantTag(string("target")).tagIs(string("target")))
    doAssert(cursorIsNil(root.findChildTag(string("missing"))))
    root.endRead()

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
            top = t.beginRead()
        echo(string("tagName(top) = "), tagName(top))
        echo(string("tagIs top/top = "), top.tagIs(string("top")), string(", top/x = "), top.tagIs(string("x")))
        _show(string("findChildTag x"), top.findChildTag(string("x")))
        _show(string("findChildTag y"), top.findChildTag(string("y")))
        _show(string("findChildTag z (only nested)"), top.findChildTag(string("z")))
        _show(string("findChildTag missing"), top.findChildTag(string("missing")))
        _show(string("findDescendantTag y"), top.findDescendantTag(string("y")))
        _show(string("findDescendantTag z"), top.findDescendantTag(string("z")))
        _show(string("findDescendantTag missing"), top.findDescendantTag(string("missing")))
        _show(string("findChildKind StrLit"), top.findChildKind(NifKind.StrLit))
        _show(string("findChildKind IntLit"), top.findChildKind(NifKind.IntLit))
        _show(string("findChildKind Ident"), top.findChildKind(NifKind.Ident))
        _show(string("findChildKind TagLit"), top.findChildKind(NifKind.TagLit))
        _show(string("findChildKind FloatLit"), top.findChildKind(NifKind.FloatLit))
        _show(string("findLastChildKind StrLit"), top.findLastChildKind(NifKind.StrLit))
        _show(string("findLastChildKind TagLit"), top.findLastChildKind(NifKind.TagLit))
        _show(string("findLastChildKind IntLit"), top.findLastChildKind(NifKind.IntLit))
        _show(string("findLastChildKind CharLit"), top.findLastChildKind(NifKind.CharLit))
        # queries on an atom find nothing; tagIs on an atom and on a nil cursor is false
        with let:
            atom = top.findChildKind(NifKind.StrLit)
        echo(string("tagIs atom = "), atom.tagIs(string("s1")))
        _show(string("findChildTag on atom"), atom.findChildTag(string("x")))
        _show(string("findDescendantTag on atom"), atom.findDescendantTag(string("x")))
        _show(string("findChildKind on atom"), atom.findChildKind(NifKind.StrLit))
        _show(string("findLastChildKind on atom"), atom.findLastChildKind(NifKind.StrLit))
        with let:
            nilCursor = default(Cursor)
        echo(string("tagIs nil = "), nilCursor.tagIs(string("top")))
        # the queries don't consume: `top` is still at the tree's head
        echo(string("top after the queries: "), tagName(top), string(" "), cursorIsNil(top))
        top.endRead()

    _addedTests()
