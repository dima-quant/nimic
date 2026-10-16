# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

## Thread var support for architectures that lack native support for
## thread local storage.

# included from cgen.nim (tests: ncompiler/tests/test_ccg.py)

def emulatedThreadVars(conf: ConfigRef) -> bool:
    result = Tset[TGlobalOption]({TGlobalOption.optThreads, TGlobalOption.optTlsEmulation}) <= conf.globalOptions
    return result


def accessThreadLocalVar(p: BProc, s: PSym) -> None:
    if emulatedThreadVars(p.config) and TCProcFlag.threadVarAccessed not in p.flags:
        incl(p.flags, TCProcFlag.threadVarAccessed)
        incl(p.module.flags, CodegenFlag.usesThreadVars)
        p.procSec(TCProcSection.cpsLocals).addVar(
            kind=VarKind.Local,
            name=string("NimTV_"),
            typ=ptrType(string("NimThreadVars")),
        )
        p.procSec(TCProcSection.cpsInit).addAssignment(
            string("NimTV_"),
            cCast(
                ptrType(string("NimThreadVars")),
                cCall(cgsymValue(p.module, string("GetThreadLocalVars"))),
            ),
        )


def declareThreadVar(m: BModule, s: PSym, isExtern: bool) -> None:
    if emulatedThreadVars(m.config):
        # we gather all thread locals var into a struct; we need to allocate
        # storage for that somehow, can't use the thread local storage
        # allocator for it :-(
        if not containsOrIncl(m.g.nimtvDeclared, s.id):
            m.g.nimtvDeps.add(s.loc.t)
            m.g.nimtv.addField(name=s.loc.snippet, typ=getTypeDesc(m, s.loc.t))
    else:
        with let:
            vis = (
                DeclVisibility.Extern
                if isExtern
                else (DeclVisibility.ExportLibVar if TLocFlag.lfExportLib in s.loc.flags else DeclVisibility.Private)
            )
        m.s[TCFileSection.cfsVars].addVar(
            m,
            s,
            name=s.loc.snippet,
            typ=getTypeDesc(m, s.loc.t),
            kind=VarKind.Threadvar,
            visibility=vis,
        )


def generateThreadLocalStorage(m: BModule) -> None:
    if m.g.nimtv.buf.len != 0 and (
        CodegenFlag.usesThreadVars in m.flags or TSymFlag.sfMainModule in m.module.flags
    ):
        for t in items(m.g.nimtvDeps):
            _ = getTypeDesc(m, t)
        finishTypeDescriptions(m)
        with m.s[TCFileSection.cfsSeqTypes].addTypedef(name=string("NimThreadVars")):
            with m.s[TCFileSection.cfsSeqTypes].addSimpleStruct(m, name=string(""), baseType=string("")):
                m.s[TCFileSection.cfsSeqTypes].add(extract(m.g.nimtv))


def generateThreadVarsSize(m: BModule) -> None:
    if m.g.nimtv.buf.len != 0:
        with let:
            externc = (
                DeclVisibility.ExternC
                if (m.config.backend == TBackend.backendCpp)
                or (TSymFlag.sfCompileToCpp in m.module.flags)
                else DeclVisibility.None_
            )
        with m.s[TCFileSection.cfsProcs].addDeclWithVisibility(externc):
            m.s[TCFileSection.cfsProcs].addProcHeader(string("NimThreadVarsSize"), NimInt, cProcParams())
            with m.s[TCFileSection.cfsProcs].finishProcHeaderWithBody():
                m.s[TCFileSection.cfsProcs].addReturn(cCast(NimInt, cSizeof(string("NimThreadVars"))))
