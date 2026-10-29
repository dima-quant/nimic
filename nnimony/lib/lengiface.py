# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/lengiface.nim
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
from .nifcore import *
from .nifbuilder import *
from . import nifbuilder
importFrom(".vfs", "OnlyIfChanged")

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
    match n.kind():
        case NifKind.TagLit:
            with let:
                tag = n.tags().tagName(n.cursorTagId())
            if tag == "inline": foundInline <<= True
            s.update("(")
            s.update(tag)
            with n.into():
                while n.hasMore():
                    _hashTree(s, n, foundInline)
            s.update(")")
        case NifKind.Symbol:
            s.update(" ")
            s.update(n.symName())
            inc(n)
        case NifKind.SymbolDef:
            s.update(" :")
            s.update(n.symName())
            inc(n)
        case NifKind.Ident:
            s.update(" ")
            s.update(n.strVal())
            inc(n)
        case NifKind.StrLit:
            s.update(" \"")
            s.update(n.strVal())
            inc(n)
        case NifKind.IntLit:
            s.update(" ")
            s.update(str(n.intVal()))
            inc(n)
        case NifKind.UIntLit:
            s.update(" ")
            s.update(str(n.uintVal()))
            inc(n)
        case NifKind.FloatLit:
            s.update(" ")
            s.update(str(n.floatVal()))
            inc(n)
        case NifKind.CharLit:
            s.update(" '")
            s.update(str(ord(n.charLit())))
            inc(n)
        case NifKind.DotToken:
            s.update(" .")
            inc(n)
        case _:
            inc(n)


def lengInterfaceDigest(buf: mut @ TokenBuf) -> string:
    ## Digest of everything in the module except the bodies of non-inline procs.
    with var:
        s = newSha1State()
    with var:
        n = beginRead(buf)
    if n.kind() == NifKind.TagLit:
        s.update("(")
        s.update(n.tags().tagName(n.cursorTagId()))
        with n.into():
            while n.hasMore():
                if n.kind() == NifKind.TagLit and n.tags().tagName(n.cursorTagId()) == "proc":
                    # (proc SymbolDef Params Type ProcPragmas Body)
                    s.update("(proc")
                    with var:
                        isInline = nbool(False)
                    with n.into():
                        with var:
                            i = nint(0)
                        while i < 4 and n.hasMore():
                            _hashTree(s, n, isInline)
                            i += 1
                        while n.hasMore():
                            if isInline:
                                with var:
                                    ignored = nbool(False)
                                _hashTree(s, n, ignored)
                            else:
                                skip(n)
                    s.update(")")
                else:
                    with var:
                        ignored = nbool(False)
                    _hashTree(s, n, ignored)
        s.update(")")
    endRead(n)
    result = string(str(SecureHash(s.finalize())))
    return result


def writeLengInterface(buf: mut @ TokenBuf, lengFile: string):
    ## Writes `lengFile`'s interface file next to it, unless it already records
    ## the same digest: then its modification time stays, and so do the codegen
    ## nodes of the other modules.
    with var:
        b = nifbuilder.open(lengInterfaceFile(lengFile), writeMode=OnlyIfChanged)
    b.addHeader()
    with b.withTree(string("interface")):
        b.addStrLit(lengInterfaceDigest(buf))
    b.close()


if comptime(__name__ == "__main__"):
    from .nifcoreparse import *
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
        try:
            echo(lengInterfaceFile(string("M.c")))
        except AssertionDefect:
            echo(string("AssertionDefect: not a .nif file"))

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
