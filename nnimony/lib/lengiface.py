# /// nimic
# source: nimony@8e0321d8917bc55953b17a354f6fd478890d479f:src/lib/lengiface.nim
# ///
#
#
#           Nif library
#        (c) Copyright 2026 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## The interface of a Leng module (`M.c.nif`, `M.oc.nif`): the part of it
## that the codegen nodes of OTHER modules read. `lengc` and `arkham` resolve
## a foreign symbol by loading its declaration out of the owning module's
## file: types, globals, constants and string literals, proc signatures, and
## the BODIES of `.inline` procs, which `lengc` emits into every translation
## unit that calls them. A non-inline proc body is never read from outside.
##
## The interface file `M.c.idx.nif` (`M.oc.idx.nif`) records a digest of
## exactly that part and is rewritten only when the digest changes, so a
## changed proc body re-runs the codegen of its own module and of nothing
## else. See doc/internals/ic.md.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.syncio import *
from nimic.std.assertions import *
from nimic.std.formatfloat import *
from .nifcore import (
    beginRead, charLit, Cursor, cursorTagId, endRead, floatVal, hasMore, inc, into, intVal, kind, NifKind, skip, strVal,
    symName, tagName, tags, TokenBuf, uintVal)
from .nifbuilder import addHeader, addStrLit, close, withTree
from . import nifbuilder
from nimic.std.sha1 import finalize, update
importFrom(".vfs", "OnlyIfChanged")
from nimic.std import syncio
from . import nifbuilder, nifcore
# one name of two imports, called free: Nim overloads them (rule:overloads)
close = overloads(syncio.close, nifbuilder.close)
addStrLit = overloads(nifbuilder.addStrLit, nifcore.addStrLit)

if comptime(defined("nimony")):
    from nimic.std.sha1 import *
else:
    with push("warning[Deprecated]: off"):
        from nimic.std.sha1 import *


def lengInterfaceFile(lengFile: string) -> string:
    ## `M.c.nif` -> `M.c.idx.nif`, `M.oc.nif` -> `M.oc.idx.nif`.
    with const:
        ext = string(".nif")
    assert lengFile.len > ext.len and \
        lengFile.substr(lengFile.len - ext.len) == ext, string("not a .nif file: ") + lengFile
    result = lengFile.substr(0, lengFile.len - ext.len - 1) + string(".idx.nif")
    return result


def _hashTree(s: mut @ Sha1State, n: mut @ Cursor, foundInline: mut @ bool):
    ## Hashes the tree at `n` and advances past it. Line information is not
    ## part of the digest, as for `.s.idx.nif`.
    match kind(n):
        case NifKind.TagLit:
            with let:
                tag = tagName(tags(n), cursorTagId(n))
            if tag == "inline": foundInline <<= True
            update(s, string("("))
            update(s, tag)
            with into(n):
                while hasMore(n):
                    _hashTree(s, n, foundInline)
            update(s, string(")"))
        case NifKind.Symbol:
            update(s, string(" "))
            update(s, symName(n))
            inc(n)
        case NifKind.SymbolDef:
            update(s, string(" :"))
            update(s, symName(n))
            inc(n)
        case NifKind.Ident:
            update(s, string(" "))
            update(s, strVal(n))
            inc(n)
        case NifKind.StrLit:
            update(s, string(" \""))
            update(s, strVal(n))
            inc(n)
        case NifKind.IntLit:
            update(s, string(" "))
            update(s, str(intVal(n)))
            inc(n)
        case NifKind.UIntLit:
            update(s, string(" "))
            update(s, str(uintVal(n)))
            inc(n)
        case NifKind.FloatLit:
            update(s, string(" "))
            update(s, str(floatVal(n)))
            inc(n)
        case NifKind.CharLit:
            update(s, string(" '"))
            update(s, str(ord(charLit(n))))
            inc(n)
        case NifKind.DotToken:
            update(s, string(" ."))
            inc(n)
        case _:
            inc(n)


def lengInterfaceDigest(buf: mut @ TokenBuf) -> string:
    ## Digest of everything in the module except the bodies of non-inline procs.
    with var:
        s = newSha1State()
    with var:
        n = beginRead(buf)
    if kind(n) == NifKind.TagLit:
        update(s, string("("))
        update(s, tagName(tags(n), cursorTagId(n)))
        with into(n):
            while hasMore(n):
                if kind(n) == NifKind.TagLit and tagName(tags(n), cursorTagId(n)) == "proc":
                    # (proc SymbolDef Params Type ProcPragmas Body)
                    update(s, string("(proc"))
                    with var:
                        isInline = nbool(False)
                    with into(n):
                        with var:
                            i = nint(0)
                        while i < 4 and hasMore(n):
                            _hashTree(s, n, isInline)
                            i += 1
                        while hasMore(n):
                            if isInline:
                                with var:
                                    ignored = nbool(False)
                                _hashTree(s, n, ignored)
                            else:
                                skip(n)
                    update(s, string(")"))
                else:
                    with var:
                        ignored = nbool(False)
                    _hashTree(s, n, ignored)
        update(s, string(")"))
    endRead(n)
    result = string(str(SecureHash(finalize(s))))
    return result


def writeLengInterface(buf: mut @ TokenBuf, lengFile: string):
    ## Writes `lengFile`'s interface file next to it, unless it already records
    ## the same digest: then its modification time stays, and so do the codegen
    ## nodes of the other modules.
    with var:
        b = nifbuilder.open(lengInterfaceFile(lengFile), writeMode=OnlyIfChanged)
    addHeader(b)
    with withTree(b, string("interface")):
        addStrLit(b, lengInterfaceDigest(buf))
    close(b)


if comptime(__name__ == "__main__"):
    from .nifcoreparse import len, parseFromBuffer
    importFrom("nimic.std.os", "getTempDir", "removeFile", "fileExists", "getLastModificationTime")

    def _digestOf(text: string) -> string:
        with var:
            buf = parseFromBuffer(text, string("lt"))
        result = lengInterfaceDigest(buf)
        return result

    def _addedTests():
        # the interface file's name
        echo(lengInterfaceFile(string("M.c.nif")))
        echo(lengInterfaceFile(string("M.oc.nif")))
        echo(lengInterfaceFile(string("dir/sub.M.c.nif")))

        # the digest of small modules
        with let:
            base = _digestOf(string(
                "(stmts (type :T.0 . . (object)) (const :c.0 . . (i +32) 5)" +
                " (proc :f.0 (params (param :a.0 . . (i +32))) (i +32) . (stmts (ret a.0)))" +
                " (proc :g.0 (params) . (pragmas (inline)) (stmts (call f.0 1)))" +
                " (var :v.0 . . (f +64) 1.5) (let :ch.0 . . (c +8) 'x') (let :u.0 . . (u +64) 7u)" +
                " (let :s.0 . . (string) \"str\") (let :n.0 . . (i +32) -3))"))
        echo(string("base: "), base)
        # only a non-inline body changes: the same digest
        with let:
            body = _digestOf(string(
                "(stmts (type :T.0 . . (object)) (const :c.0 . . (i +32) 5)" +
                " (proc :f.0 (params (param :a.0 . . (i +32))) (i +32) . (stmts (ret 42) (call g.0)))" +
                " (proc :g.0 (params) . (pragmas (inline)) (stmts (call f.0 1)))" +
                " (var :v.0 . . (f +64) 1.5) (let :ch.0 . . (c +8) 'x') (let :u.0 . . (u +64) 7u)" +
                " (let :s.0 . . (string) \"str\") (let :n.0 . . (i +32) -3))"))
        echo(string("non-inline body changed: "), body, string(" same: "), body == base)
        # an inline body changes: a different digest
        with let:
            inl = _digestOf(string(
                "(stmts (type :T.0 . . (object)) (const :c.0 . . (i +32) 5)" +
                " (proc :f.0 (params (param :a.0 . . (i +32))) (i +32) . (stmts (ret a.0)))" +
                " (proc :g.0 (params) . (pragmas (inline)) (stmts (call f.0 2)))" +
                " (var :v.0 . . (f +64) 1.5) (let :ch.0 . . (c +8) 'x') (let :u.0 . . (u +64) 7u)" +
                " (let :s.0 . . (string) \"str\") (let :n.0 . . (i +32) -3))"))
        echo(string("inline body changed: "), inl, string(" same: "), inl == base)
        # a signature changes: a different digest
        with let:
            sig = _digestOf(string(
                "(stmts (type :T.0 . . (object)) (const :c.0 . . (i +32) 5)" +
                " (proc :f.0 (params (param :a.0 . . (i +64))) (i +32) . (stmts (ret a.0)))" +
                " (proc :g.0 (params) . (pragmas (inline)) (stmts (call f.0 1)))" +
                " (var :v.0 . . (f +64) 1.5) (let :ch.0 . . (c +8) 'x') (let :u.0 . . (u +64) 7u)" +
                " (let :s.0 . . (string) \"str\") (let :n.0 . . (i +32) -3))"))
        echo(string("signature changed: "), sig, string(" same: "), sig == base)
        # a global's value changes: a different digest
        with let:
            val = _digestOf(string(
                "(stmts (type :T.0 . . (object)) (const :c.0 . . (i +32) 6)" +
                " (proc :f.0 (params (param :a.0 . . (i +32))) (i +32) . (stmts (ret a.0)))" +
                " (proc :g.0 (params) . (pragmas (inline)) (stmts (call f.0 1)))" +
                " (var :v.0 . . (f +64) 1.5) (let :ch.0 . . (c +8) 'x') (let :u.0 . . (u +64) 7u)" +
                " (let :s.0 . . (string) \"str\") (let :n.0 . . (i +32) -3))"))
        echo(string("const value changed: "), val == base)
        # line info is not part of the digest
        echo(string("line info ignored: "), _digestOf(string("(stmts@1,2,a.nim (let@3,4 :x.0 . . . 1))")) ==
             _digestOf(string("(stmts (let :x.0 . . . 1))")))
        # a module that is no tree, and an empty one
        echo(string("atom: "), _digestOf(string("x")))
        echo(string("empty stmts: "), _digestOf(string("(stmts)")))
        # a proc with fewer than 4 sons
        echo(string("short proc: "), _digestOf(string("(stmts (proc :p.0 (params)))")))

        # writeLengInterface under getTempDir()
        with let:
            lengFile = getTempDir() + string("nimic_lengiface_test.c.nif")
        with let:
            idxFile = lengInterfaceFile(lengFile)
        if fileExists(idxFile): removeFile(idxFile)
        with var:
            buf = parseFromBuffer(string("(stmts (proc :f.0 (params) . . (stmts (ret 1))))"), string("lt"))
        writeLengInterface(buf, lengFile)
        echo(string("written: "), fileExists(idxFile))
        echo(readFile(idxFile))
        # the same digest: the file is kept, so its modification time stays
        with let:
            mtime1 = getLastModificationTime(idxFile)
        with var:
            buf2 = parseFromBuffer(string("(stmts (proc :f.0 (params) . . (stmts (ret 2))))"), string("lt"))
        writeLengInterface(buf2, lengFile)
        echo(string("same mtime: "), getLastModificationTime(idxFile) == mtime1)
        # replaced by hand: the content differs from the digest, so it is written again
        writeFile(idxFile, string("replaced by hand\n"))
        writeLengInterface(buf2, lengFile)
        echo(string("rewritten: "), readFile(idxFile))
        # a changed signature rewrites it
        with var:
            buf3 = parseFromBuffer(string("(stmts (proc :f.0 (params (param :a.0 . . (i +8))) . . (stmts)))"),
                                   string("lt"))
        writeLengInterface(buf3, lengFile)
        echo(readFile(idxFile))
        removeFile(idxFile)

    _addedTests()
