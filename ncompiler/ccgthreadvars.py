# /// nimic
#
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

# included from cgen.nim

if comptime(__name__ == "__main__"):
    class TGlobalOption(NIntEnum):
        optThreads = 0
        optTlsEmulation = auto()
        optOther = auto()

    class TCProcFlag(NIntEnum):
        beforeRetNeeded = 0
        threadVarAccessed = auto()

    class CodegenFlag(NIntEnum):
        preventStackTrace = 0
        usesThreadVars = auto()

    class TCProcSection(NIntEnum):
        cpsLocals = 0
        cpsInit = 1
        cpsStmts = 2

    class TCFileSection(NIntEnum):
        cfsVars = 0
        cfsSeqTypes = 1
        cfsProcs = 2
        cfsCount = 3

    class TLocFlag(NIntEnum):
        lfExportLib = 0

    class VarKind(NIntEnum):
        Local = 0
        Threadvar = auto()

    class DeclVisibility(NIntEnum):
        None_ = 0
        Extern = auto()
        ExternC = auto()
        ExportLibVar = auto()
        Private = auto()

    class TBackend(NIntEnum):
        backendC = 0
        backendCpp = auto()

    class TSymFlag(NIntEnum):
        sfMainModule = 0
        sfCompileToCpp = auto()

    if not comptime(defined("c")):
        optThreads = TGlobalOption.optThreads
        optTlsEmulation = TGlobalOption.optTlsEmulation
        optOther = TGlobalOption.optOther
        threadVarAccessed = TCProcFlag.threadVarAccessed
        usesThreadVars = CodegenFlag.usesThreadVars
        cpsLocals = TCProcSection.cpsLocals
        cpsInit = TCProcSection.cpsInit
        cpsStmts = TCProcSection.cpsStmts
        cfsVars = TCFileSection.cfsVars
        cfsSeqTypes = TCFileSection.cfsSeqTypes
        cfsProcs = TCFileSection.cfsProcs
        cfsCount = TCFileSection.cfsCount
        lfExportLib = TLocFlag.lfExportLib
        Local = VarKind.Local
        Threadvar = VarKind.Threadvar
        None_ = DeclVisibility.None_
        Extern = DeclVisibility.Extern
        ExternC = DeclVisibility.ExternC
        ExportLibVar = DeclVisibility.ExportLibVar
        Private = DeclVisibility.Private
        backendC = TBackend.backendC
        backendCpp = TBackend.backendCpp
        sfMainModule = TSymFlag.sfMainModule
        sfCompileToCpp = TSymFlag.sfCompileToCpp

    with const:
        NimInt = string("NI")

    @ref
    class Buffer(Object):
        data: string

        @property
        def len(self) -> nint:
            return len(self.data)

    @ref
    class Builder(Object):
        buf: Buffer
        calls: seq[string]

    @ref
    class ConfigRef(Object):
        globalOptions: Tset[TGlobalOption]
        backend: TBackend

    @ref
    class TLoc(Object):
        snippet: string
        t: string
        flags: Tset[TLocFlag]

    @ref
    class PSym(Object):
        id: nint
        flags: Tset[TSymFlag]
        loc: TLoc

    class IdRange(Trange[0, 1000]):
        pass

    @ref
    class BModuleList(Object):
        config: ConfigRef
        nimtv: Builder
        nimtvDeps: seq[string]
        nimtvDeclared: Tset[IdRange]

    @ref
    class BModule(Object):
        g: BModuleList
        flags: Tset[CodegenFlag]
        module: PSym
        s: array[TCFileSection, Builder]

        @property
        def config(self) -> ConfigRef:
            return self.g.config

    @ref
    class BProc(Object):
        module: BModule
        flags: Tset[TCProcFlag]
        sections: array[TCProcSection, Builder]

        @property
        def config(self) -> ConfigRef:
            return self.module.g.config

        def procSec(self, sec: TCProcSection) -> Builder:
            return self.sections[sec]

    def addAssignment(self: Builder, lhs: string, rhs: string) -> None:
        self.calls.add(string("addAssignment"))

    def addField(self: Builder, name: string = string(""), typ: string = string("")) -> None:
        self.calls.add(string("addField"))

    def add(self: Builder, content: string) -> None:
        self.calls.add(string("add"))

    def addProcHeader(self: Builder, name: string = string(""), rettype: string = string(""), params: string = string("")) -> None:
        self.calls.add(string("addProcHeader"))

    def addReturn(self: Builder, val: string) -> None:
        self.calls.add(string("addReturn"))

    # Templates and overloaded procs for Nim
    if comptime(defined("c")):
        def addVar(self: Builder, kind: VarKind = VarKind.Local, name: string = string(""), typ: string = string("")) -> None:
            self.calls.add(string("addVar"))

        def addVar(self: Builder, m: BModule, s: PSym, name: string = string(""), typ: string = string(""), kind: VarKind = VarKind.Threadvar, visibility: DeclVisibility = DeclVisibility.Private) -> None:
            self.calls.add(string("addVar"))

        @template
        def containsOrIncl(s: untyped, val: untyped) -> untyped:
            if val in s:
                return True
            else:
                incl(s, val)
                return False

        @template
        def addTypedef(self: Builder, name: string, body: untyped) -> untyped:
            return body

        @template
        def addSimpleStruct(self: Builder, m: untyped, name: string, baseType: string, body: untyped) -> untyped:
            return body

        @template
        def addDeclWithVisibility(self: Builder, vis: untyped, body: untyped) -> untyped:
            return body

        @template
        def finishProcHeaderWithBody(self: Builder, body: untyped) -> untyped:
            return body

    if not comptime(defined("c")):
        def _py_addVar(self: Builder, a1: Any = None, a2: Any = None, name: string = string(""), typ: string = string(""), kind: VarKind = VarKind.Local, visibility: DeclVisibility = DeclVisibility.Private) -> None:
            self.calls.add(string("addVar"))

        def _py_addTypedef(self: Builder, name: string = string("")) -> Builder:
            self.calls.add(string("addTypedef"))
            return self

        def _py_addSimpleStruct(self: Builder, m: Any = None, name: string = string(""), baseType: string = string("")) -> Builder:
            self.calls.add(string("addSimpleStruct"))
            return self

        def _py_addDeclWithVisibility(self: Builder, vis: Any = None) -> Builder:
            self.calls.add(string("addDeclWithVisibility"))
            return self

        def _py_finishProcHeaderWithBody(self: Builder) -> Builder:
            self.calls.add(string("finishProcHeaderWithBody"))
            return self

        def containsOrIncl(s: set, val: Any) -> bool:
            if val in s:
                return True
            s.add(val)
            return False

        Builder.addVar = _py_addVar
        Builder.addAssignment = addAssignment
        Builder.addField = addField
        Builder.add = add
        Builder.addProcHeader = addProcHeader
        Builder.addReturn = addReturn
        Builder.addTypedef = _py_addTypedef
        Builder.addSimpleStruct = _py_addSimpleStruct
        Builder.addDeclWithVisibility = _py_addDeclWithVisibility
        Builder.finishProcHeaderWithBody = _py_finishProcHeaderWithBody

    def ptrType(t: string) -> string:
        return t + string("*")

    def cCast(typ: string, value: string) -> string:
        return string("((") + typ + string(")(") + value + string("))")

    def cCall(callee: string) -> string:
        return callee + string("()")

    def cgsymValue(module: BModule, name: string) -> string:
        return name

    def getTypeDesc(m: BModule, t: string) -> string:
        return string("TypeDesc(") + t + string(")")

    def finishTypeDescriptions(m: BModule) -> None:
        discard

    def extract(builder: Builder) -> string:
        return builder.buf.data

    def cProcParams() -> string:
        return string("void")

    def cSizeof(t: string) -> string:
        return string("sizeof(") + t + string(")")

    def newBuffer(data: string = string("")) -> Buffer:
        with var:
            b = Buffer()
        b.data = data
        return b

    def newBuilder() -> Builder:
        with var:
            b = Builder()
        b.buf = newBuffer()
        b.calls = new_seq[string](0)
        return b

    def newConfigRef(globalOptions: Tset[TGlobalOption] = Tset[TGlobalOption](), backend: TBackend = TBackend.backendC) -> ConfigRef:
        with var:
            c = ConfigRef()
        c.globalOptions = globalOptions
        c.backend = backend
        return c

    def newTLoc(snippet: string = string("varA"), t: string = string("intType"), flags: Tset[TLocFlag] = Tset[TLocFlag]()) -> TLoc:
        with var:
            loc = TLoc()
        loc.snippet = snippet
        loc.t = t
        loc.flags = flags
        return loc

    def newPSym(id: nint = 1, loc: TLoc = None) -> PSym:
        with var:
            s = PSym()
        s.id = id
        s.flags = Tset[TSymFlag]()
        s.loc = loc if loc is not None else newTLoc()
        return s

    def newBModuleList(config: ConfigRef = None) -> BModuleList:
        with var:
            g = BModuleList()
        g.config = config if config is not None else newConfigRef()
        g.nimtv = newBuilder()
        g.nimtvDeps = new_seq[string](0)
        g.nimtvDeclared = Tset[IdRange]()
        return g

    def newBModule(config: ConfigRef = None, is_main: bool = False, compile_to_cpp: bool = False) -> BModule:
        with var:
            m = BModule()
        m.g = newBModuleList(config)
        m.flags = Tset[CodegenFlag]()
        m.module = newPSym(0)
        if is_main:
            incl(m.module.flags, sfMainModule)
        if compile_to_cpp:
            incl(m.module.flags, sfCompileToCpp)
        with var:
            s_arr = array[TCFileSection, Builder]()
        s_arr[cfsVars] = newBuilder()
        s_arr[cfsSeqTypes] = newBuilder()
        s_arr[cfsProcs] = newBuilder()
        s_arr[cfsCount] = newBuilder()
        m.s = s_arr
        return m

    def newBProc(module: BModule) -> BProc:
        with var:
            p = BProc()
        p.module = module
        p.flags = Tset[TCProcFlag]()
        with var:
            sec_arr = array[TCProcSection, Builder]()
        sec_arr[cpsLocals] = newBuilder()
        sec_arr[cpsInit] = newBuilder()
        sec_arr[cpsStmts] = newBuilder()
        p.sections = sec_arr
        return p


def emulatedThreadVars(conf: ConfigRef) -> bool:
    result = {optThreads, optTlsEmulation} <= conf.globalOptions
    return result


def accessThreadLocalVar(p: BProc, s: PSym) -> None:
    if emulatedThreadVars(p.config) and threadVarAccessed not in p.flags:
        incl(p.flags, threadVarAccessed)
        incl(p.module.flags, usesThreadVars)
        p.procSec(cpsLocals).addVar(
            kind=Local,
            name="NimTV_",
            typ=ptrType("NimThreadVars"),
        )
        p.procSec(cpsInit).addAssignment(
            "NimTV_",
            cCast(
                ptrType("NimThreadVars"),
                cCall(cgsymValue(p.module, "GetThreadLocalVars")),
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
                Extern
                if isExtern
                else (ExportLibVar if lfExportLib in s.loc.flags else Private)
            )
        m.s[cfsVars].addVar(
            m,
            s,
            name=s.loc.snippet,
            typ=getTypeDesc(m, s.loc.t),
            kind=Threadvar,
            visibility=vis,
        )


def generateThreadLocalStorage(m: BModule) -> None:
    if m.g.nimtv.buf.len != 0 and (
        usesThreadVars in m.flags or sfMainModule in m.module.flags
    ):
        for t in items(m.g.nimtvDeps):
            _ = getTypeDesc(m, t)
        finishTypeDescriptions(m)
        with m.s[cfsSeqTypes].addTypedef(name="NimThreadVars"):
            with m.s[cfsSeqTypes].addSimpleStruct(m, name="", baseType=""):
                m.s[cfsSeqTypes].add(extract(m.g.nimtv))


def generateThreadVarsSize(m: BModule) -> None:
    if m.g.nimtv.buf.len != 0:
        with let:
            externc = (
                ExternC
                if (m.config.backend == backendCpp)
                or (sfCompileToCpp in m.module.flags)
                else None_
            )
        with m.s[cfsProcs].addDeclWithVisibility(externc):
            m.s[cfsProcs].addProcHeader("NimThreadVarsSize", NimInt, cProcParams())
            with m.s[cfsProcs].finishProcHeaderWithBody():
                m.s[cfsProcs].addReturn(cCast(NimInt, cSizeof("NimThreadVars")))


if comptime(__name__ == "__main__"):
    # --- Test Suite ---
    echo("Running ccgthreadvars tests...")

    # 1. Test emulatedThreadVars
    with var:
        conf_none = newConfigRef()
    assert emulatedThreadVars(conf_none) == False

    with var:
        conf_threads_only = newConfigRef(Tset[TGlobalOption]({optThreads}))
    assert emulatedThreadVars(conf_threads_only) == False

    with var:
        conf_tls_only = newConfigRef(Tset[TGlobalOption]({optTlsEmulation}))
    assert emulatedThreadVars(conf_tls_only) == False

    with var:
        conf_emulated = newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation}))
    assert emulatedThreadVars(conf_emulated) == True

    with var:
        conf_emulated_plus = newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation, optOther}))
    assert emulatedThreadVars(conf_emulated_plus) == True
    echo("  [1] emulatedThreadVars: PASS")

    # 2. Test accessThreadLocalVar
    # Case 2a: Not emulated
    with var:
        mod_native = newBModule(newConfigRef())
        proc_native = newBProc(mod_native)
        sym1 = newPSym(1)
    accessThreadLocalVar(proc_native, sym1)
    assert threadVarAccessed not in proc_native.flags
    assert usesThreadVars not in mod_native.flags
    assert len(proc_native.procSec(cpsLocals).calls) == 0

    # Case 2b: Emulated, first access
    with var:
        mod_emu = newBModule(newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation})))
        proc_emu = newBProc(mod_emu)
    accessThreadLocalVar(proc_emu, sym1)
    assert threadVarAccessed in proc_emu.flags
    assert usesThreadVars in mod_emu.flags
    assert len(proc_emu.procSec(cpsLocals).calls) == 1
    assert len(proc_emu.procSec(cpsInit).calls) == 1

    # Case 2c: Emulated, second access (idempotent, flags already set)
    with var:
        calls_before = len(proc_emu.procSec(cpsLocals).calls)
    accessThreadLocalVar(proc_emu, sym1)
    assert len(proc_emu.procSec(cpsLocals).calls) == calls_before

    # Case 2d: Proc already has threadVarAccessed prior to call
    with var:
        proc_pre_flagged = newBProc(mod_emu)
    incl(proc_pre_flagged.flags, threadVarAccessed)
    accessThreadLocalVar(proc_pre_flagged, sym1)
    assert len(proc_pre_flagged.procSec(cpsLocals).calls) == 0
    echo("  [2] accessThreadLocalVar: PASS")

    # 3. Test declareThreadVar
    # Case 3a: Emulated mode
    with var:
        sym_emu1 = newPSym(10, newTLoc(string("myThreadVar"), string("intType")))
    declareThreadVar(mod_emu, sym_emu1, False)
    assert 10 in mod_emu.g.nimtvDeclared
    assert len(mod_emu.g.nimtvDeps) == 1
    assert mod_emu.g.nimtvDeps[0] == "intType"
    assert len(mod_emu.g.nimtv.calls) == 1

    # Duplicate declaration in emulated mode (idempotent)
    declareThreadVar(mod_emu, sym_emu1, False)
    assert len(mod_emu.g.nimtvDeps) == 1
    assert len(mod_emu.g.nimtv.calls) == 1

    # Case 3b: Native mode, isExtern=True
    with var:
        sym_nat1 = newPSym(20, newTLoc(string("extVar"), string("floatType")))
    declareThreadVar(mod_native, sym_nat1, True)
    assert len(mod_native.s[cfsVars].calls) == 1

    # Case 3c: Native mode, isExtern=False, lfExportLib in flags
    with var:
        sym_nat2 = newPSym(21, newTLoc(string("libVar"), string("floatType"), Tset[TLocFlag]({lfExportLib})))
    declareThreadVar(mod_native, sym_nat2, False)
    assert len(mod_native.s[cfsVars].calls) == 2

    # Case 3d: Native mode, isExtern=False, Private
    with var:
        sym_nat3 = newPSym(22, newTLoc(string("privVar"), string("intType")))
    declareThreadVar(mod_native, sym_nat3, False)
    assert len(mod_native.s[cfsVars].calls) == 3

    # Case 3e: Emulated mode with multiple distinct symbols
    with var:
        sym_emu2 = newPSym(30, newTLoc(string("varB"), string("stringType")))
    declareThreadVar(mod_emu, sym_emu2, False)
    assert 30 in mod_emu.g.nimtvDeclared
    assert len(mod_emu.g.nimtvDeps) == 2
    assert mod_emu.g.nimtvDeps[1] == "stringType"
    assert len(mod_emu.g.nimtv.calls) == 2
    echo("  [3] declareThreadVar: PASS")

    # 4. Test generateThreadLocalStorage
    # Case 4a: Buffer is empty -> no-op
    with var:
        mod_ls_empty = newBModule(newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation})))
    incl(mod_ls_empty.flags, usesThreadVars)
    generateThreadLocalStorage(mod_ls_empty)
    assert len(mod_ls_empty.s[cfsSeqTypes].calls) == 0

    # Case 4b: Buffer has content, but lacks usesThreadVars and sfMainModule -> no-op
    with var:
        mod_ls_noflag = newBModule(newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation})))
    mod_ls_noflag.g.nimtv.buf = newBuffer(string("field: int;"))
    generateThreadLocalStorage(mod_ls_noflag)
    assert len(mod_ls_noflag.s[cfsSeqTypes].calls) == 0

    # Case 4c: Buffer has content and usesThreadVars in m.flags
    with var:
        mod_ls_gen = newBModule(newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation})))
    mod_ls_gen.g.nimtv.buf = newBuffer(string("field: int;"))
    mod_ls_gen.g.nimtvDeps.add(string("depTypeA"))
    incl(mod_ls_gen.flags, usesThreadVars)
    generateThreadLocalStorage(mod_ls_gen)
    assert len(mod_ls_gen.s[cfsSeqTypes].calls) >= 1

    # Case 4d: Buffer has content, sfMainModule in m.module.flags
    with var:
        mod_ls_main = newBModule(newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation})), is_main=True)
    mod_ls_main.g.nimtv.buf = newBuffer(string("field: int;"))
    generateThreadLocalStorage(mod_ls_main)
    assert len(mod_ls_main.s[cfsSeqTypes].calls) >= 1

    # Case 4e: Both usesThreadVars and sfMainModule present
    with var:
        mod_ls_both = newBModule(newConfigRef(Tset[TGlobalOption]({optThreads, optTlsEmulation})), is_main=True)
    mod_ls_both.g.nimtv.buf = newBuffer(string("field: int;"))
    incl(mod_ls_both.flags, usesThreadVars)
    generateThreadLocalStorage(mod_ls_both)
    assert len(mod_ls_both.s[cfsSeqTypes].calls) >= 1
    echo("  [4] generateThreadLocalStorage: PASS")

    # 5. Test generateThreadVarsSize
    # Case 5a: Buffer empty -> no-op
    with var:
        mod_sz_empty = newBModule(newConfigRef())
    generateThreadVarsSize(mod_sz_empty)
    assert len(mod_sz_empty.s[cfsProcs].calls) == 0

    # Case 5b: C backend, not compile to C++
    with var:
        mod_sz_c = newBModule(newConfigRef(backend=TBackend.backendC))
    mod_sz_c.g.nimtv.buf = newBuffer(string("field: int;"))
    generateThreadVarsSize(mod_sz_c)
    assert len(mod_sz_c.s[cfsProcs].calls) >= 1

    # Case 5c: backendCpp
    with var:
        mod_sz_cpp = newBModule(newConfigRef(backend=TBackend.backendCpp))
    mod_sz_cpp.g.nimtv.buf = newBuffer(string("field: int;"))
    generateThreadVarsSize(mod_sz_cpp)
    assert len(mod_sz_cpp.s[cfsProcs].calls) >= 1

    # Case 5d: sfCompileToCpp in m.module.flags
    with var:
        mod_sz_flag_cpp = newBModule(newConfigRef(backend=TBackend.backendC), compile_to_cpp=True)
    mod_sz_flag_cpp.g.nimtv.buf = newBuffer(string("field: int;"))
    generateThreadVarsSize(mod_sz_flag_cpp)
    assert len(mod_sz_flag_cpp.s[cfsProcs].calls) >= 1

    # Case 5e: Both backendCpp and sfCompileToCpp set
    with var:
        mod_sz_both_cpp = newBModule(newConfigRef(backend=TBackend.backendCpp), compile_to_cpp=True)
    mod_sz_both_cpp.g.nimtv.buf = newBuffer(string("field: int;"))
    generateThreadVarsSize(mod_sz_both_cpp)
    assert len(mod_sz_both_cpp.s[cfsProcs].calls) >= 1
    echo("  [5] generateThreadVarsSize: PASS")

    echo("All ccgthreadvars tests passed successfully!")
