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

def _emulatedThreadVars(conf: ConfigRef) -> bool:
    result = Tset[TGlobalOption]({TGlobalOption.optThreads, TGlobalOption.optTlsEmulation}) <= conf.globalOptions
    return result


def _accessThreadLocalVar(p: BProc, s: PSym) -> None:
    if _emulatedThreadVars(p.config) and TCProcFlag.threadVarAccessed not in p.flags:
        incl(p.flags, TCProcFlag.threadVarAccessed)
        incl(p.module.flags, CodegenFlag.usesThreadVars)
        p.procSec(TCProcSection.cpsLocals)._addVar(
            kind=_VarKind.Local,
            name=string("NimTV_"),
            typ=_ptrType(string("NimThreadVars")),
        )
        p.procSec(TCProcSection.cpsInit)._addAssignment(
            string("NimTV_"),
            _cCast(
                _ptrType(string("NimThreadVars")),
                _cCall(cgsymValue(p.module, string("GetThreadLocalVars"))),
            ),
        )


def _declareThreadVar(m: BModule, s: PSym, isExtern: bool) -> None:
    if _emulatedThreadVars(m.config):
        # we gather all thread locals var into a struct; we need to allocate
        # storage for that somehow, can't use the thread local storage
        # allocator for it :-(
        if not containsOrIncl(m.g.nimtvDeclared, s.id):
            m.g.nimtvDeps.add(s.loc.t)
            m.g.nimtv._addField(name=s.loc.snippet, typ=getTypeDesc(m, s.loc.t))
    else:
        with let:
            vis = (
                _DeclVisibility.Extern
                if isExtern
                else (_DeclVisibility.ExportLibVar if TLocFlag.lfExportLib in s.loc.flags else _DeclVisibility.Private)
            )
        m.s[TCFileSection.cfsVars]._addVar(
            m,
            s,
            name=s.loc.snippet,
            typ=getTypeDesc(m, s.loc.t),
            kind=_VarKind.Threadvar,
            visibility=vis,
        )


def _generateThreadLocalStorage(m: BModule) -> None:
    if m.g.nimtv.buf.len != 0 and (
        CodegenFlag.usesThreadVars in m.flags or TSymFlag.sfMainModule in m.module.flags
    ):
        for t in items(m.g.nimtvDeps):
            _ = getTypeDesc(m, t)
        finishTypeDescriptions(m)
        with m.s[TCFileSection.cfsSeqTypes]._addTypedef(name=string("NimThreadVars")):
            with m.s[TCFileSection.cfsSeqTypes]._addSimpleStruct(m, name=string(""), baseType=string("")):
                m.s[TCFileSection.cfsSeqTypes].add(m.g.nimtv.extract())


def _generateThreadVarsSize(m: BModule) -> None:
    if m.g.nimtv.buf.len != 0:
        with let:
            externc = (
                _DeclVisibility.ExternC
                if (m.config.backend == TBackend.backendCpp)
                or (TSymFlag.sfCompileToCpp in m.module.flags)
                else _DeclVisibility.None_
            )
        with m.s[TCFileSection.cfsProcs]._addDeclWithVisibility(externc):
            m.s[TCFileSection.cfsProcs]._addProcHeader(string("NimThreadVarsSize"), NimInt, _cProcParams())
            with m.s[TCFileSection.cfsProcs]._finishProcHeaderWithBody():
                m.s[TCFileSection.cfsProcs]._addReturn(_cCast(NimInt, _cSizeof(string("NimThreadVars"))))
