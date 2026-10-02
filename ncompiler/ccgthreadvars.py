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
    # Mock structures and enums for standalone unit testing

    class TGlobalOption(NIntEnum):
        optThreads = auto()
        optTlsEmulation = auto()
        optOther = auto()

    optThreads = TGlobalOption.optThreads
    optTlsEmulation = TGlobalOption.optTlsEmulation
    optOther = TGlobalOption.optOther

    class TCProcFlag(NIntEnum):
        beforeRetNeeded = auto()
        threadVarAccessed = auto()

    threadVarAccessed = TCProcFlag.threadVarAccessed

    class CodegenFlag(NIntEnum):
        preventStackTrace = auto()
        usesThreadVars = auto()

    usesThreadVars = CodegenFlag.usesThreadVars

    class TCProcSection(NIntEnum):
        cpsLocals = 0
        cpsInit = 1
        cpsStmts = 2

    cpsLocals = TCProcSection.cpsLocals
    cpsInit = TCProcSection.cpsInit
    cpsStmts = TCProcSection.cpsStmts

    class TCFileSection(NIntEnum):
        cfsVars = 0
        cfsSeqTypes = 1
        cfsProcs = 2
        cfsCount = 3

    cfsVars = TCFileSection.cfsVars
    cfsSeqTypes = TCFileSection.cfsSeqTypes
    cfsProcs = TCFileSection.cfsProcs

    class TLocFlag(NIntEnum):
        lfExportLib = auto()

    lfExportLib = TLocFlag.lfExportLib

    class VarKind(NIntEnum):
        Local = auto()
        Threadvar = auto()

    Local = VarKind.Local
    Threadvar = VarKind.Threadvar

    class DeclVisibility(NIntEnum):
        None_ = auto()
        Extern = auto()
        ExternC = auto()
        ExportLibVar = auto()
        Private = auto()

    None_ = DeclVisibility.None_
    Extern = DeclVisibility.Extern
    ExternC = DeclVisibility.ExternC
    ExportLibVar = DeclVisibility.ExportLibVar
    Private = DeclVisibility.Private

    class TBackend(NIntEnum):
        backendC = auto()
        backendCpp = auto()

    backendC = TBackend.backendC
    backendCpp = TBackend.backendCpp

    class TSymFlag(NIntEnum):
        sfMainModule = auto()
        sfCompileToCpp = auto()

    sfMainModule = TSymFlag.sfMainModule
    sfCompileToCpp = TSymFlag.sfCompileToCpp

    NimInt = "NI"

    # Helper mock procedures
    def ptrType(t: str) -> str:
        return f"{t}*"

    def cCast(typ: str, value: str) -> str:
        return f"(({typ})({value}))"

    def cCall(callee: str) -> str:
        return f"{callee}()"

    def cgsymValue(module: BModule, name: str) -> str:
        return name

    def getTypeDesc(m: BModule, t: Any) -> str:
        return f"TypeDesc({t})"

    _finished_type_descriptions = []

    def finishTypeDescriptions(m: BModule) -> None:
        _finished_type_descriptions.append(m)

    def extract(builder: Builder) -> str:
        return builder.buf.data

    def cProcParams() -> str:
        return "void"

    def cSizeof(t: str) -> str:
        return f"sizeof({t})"

    class Buffer(Object):
        def __init__(self, data: str = ""):
            self.data = data

        @property
        def len(self) -> nint:
            return len(self.data)

    class Builder(Object):
        def __init__(self):
            self.buf = Buffer()
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def addVar(self, *args, **kwargs):
            self.calls.append(("addVar", args, kwargs))

        def addAssignment(self, lhs, rhs):
            self.calls.append(("addAssignment", (lhs, rhs)))

        def addField(self, name="", typ=""):
            self.calls.append(("addField", (name, typ)))

        def add(self, content):
            self.calls.append(("add", (content,)))

        def addTypedef(self, name=""):
            self.calls.append(("addTypedef", (name,)))
            return self

        def addSimpleStruct(self, m=None, name="", baseType=""):
            self.calls.append(("addSimpleStruct", (name, baseType)))
            return self

        def addDeclWithVisibility(self, visibility=None):
            self.calls.append(("addDeclWithVisibility", (visibility,)))
            return self

        def addProcHeader(self, name="", rettype="", params=""):
            self.calls.append(("addProcHeader", (name, rettype, params)))

        def finishProcHeaderWithBody(self):
            self.calls.append(("finishProcHeaderWithBody", ()))
            return self

        def addReturn(self, val):
            self.calls.append(("addReturn", (val,)))

    class ConfigRef(Object):
        def __init__(self, globalOptions=None, backend=backendC):
            self.globalOptions = globalOptions if globalOptions is not None else set()
            self.backend = backend

    class Seq(list):
        def add(self, x):
            self.append(x)

    class BModuleList(Object):
        def __init__(self, config=None):
            self.config = config if config is not None else ConfigRef()
            self.nimtv = Builder()
            self.nimtvDeps = Seq()
            self.nimtvDeclared = set()

    class BModule(Object):
        def __init__(self, config=None, is_main=False, compile_to_cpp=False):
            self.g = BModuleList(config)
            self.flags = set()
            self.module = PSym(id=0)
            if is_main:
                self.module.flags.add(sfMainModule)
            if compile_to_cpp:
                self.module.flags.add(sfCompileToCpp)
            self.s = [Builder() for _ in range(nint(TCFileSection.cfsCount))]

        @property
        def config(self) -> ConfigRef:
            return self.g.config

    class BProc(Object):
        def __init__(self, module: BModule):
            self.module = module
            self.flags = set()
            self.sections = [Builder() for _ in range(3)]

        @property
        def config(self) -> ConfigRef:
            return self.module.g.config

        def procSec(self, sec: TCProcSection) -> Builder:
            return self.sections[nint(sec)]

    class TLoc(Object):
        def __init__(self, snippet="varA", t="intType", flags=None):
            self.snippet = snippet
            self.t = t
            self.flags = flags if flags is not None else set()

    class PSym(Object):
        def __init__(self, id=1, loc=None):
            self.id = id
            self.flags = set()
            self.loc = loc if loc is not None else TLoc()

    # --- Test Suite ---
    print("Running ccgthreadvars tests...")

    # 1. Test emulatedThreadVars
    conf_none = ConfigRef()
    assert emulatedThreadVars(conf_none) == False, "empty options should be False"

    conf_threads_only = ConfigRef({optThreads})
    assert emulatedThreadVars(conf_threads_only) == False, "only optThreads should be False"

    conf_tls_only = ConfigRef({optTlsEmulation})
    assert emulatedThreadVars(conf_tls_only) == False, "only optTlsEmulation should be False"

    conf_emulated = ConfigRef({optThreads, optTlsEmulation})
    assert emulatedThreadVars(conf_emulated) == True, "both should be True"

    conf_emulated_plus = ConfigRef({optThreads, optTlsEmulation, optOther})
    assert emulatedThreadVars(conf_emulated_plus) == True, "both plus others should be True"
    print("  [1] emulatedThreadVars: PASS")

    # 2. Test accessThreadLocalVar
    # Case 2a: Not emulated
    mod_native = BModule(ConfigRef())
    proc_native = BProc(mod_native)
    sym1 = PSym(1)
    accessThreadLocalVar(proc_native, sym1)
    assert threadVarAccessed not in proc_native.flags
    assert usesThreadVars not in mod_native.flags
    assert len(proc_native.procSec(cpsLocals).calls) == 0

    # Case 2b: Emulated, first access
    mod_emu = BModule(ConfigRef({optThreads, optTlsEmulation}))
    proc_emu = BProc(mod_emu)
    accessThreadLocalVar(proc_emu, sym1)
    assert threadVarAccessed in proc_emu.flags, "threadVarAccessed should be added"
    assert usesThreadVars in mod_emu.flags, "usesThreadVars should be added to module"
    locals_calls = proc_emu.procSec(cpsLocals).calls
    assert len(locals_calls) == 1
    assert locals_calls[0][0] == "addVar"
    assert locals_calls[0][2] == {"kind": Local, "name": "NimTV_", "typ": "NimThreadVars*"}
    init_calls = proc_emu.procSec(cpsInit).calls
    assert len(init_calls) == 1
    assert init_calls[0][0] == "addAssignment"
    assert init_calls[0][1][0] == "NimTV_"

    # Case 2c: Emulated, second access in same proc (should be a no-op)
    accessThreadLocalVar(proc_emu, sym1)
    assert len(proc_emu.procSec(cpsLocals).calls) == 1, "should not add variable twice"
    assert len(proc_emu.procSec(cpsInit).calls) == 1, "should not add assignment twice"

    # Case 2d: Emulated, but threadVarAccessed already in p.flags initially
    mod_emu_pre = BModule(ConfigRef({optThreads, optTlsEmulation}))
    proc_emu_pre = BProc(mod_emu_pre)
    proc_emu_pre.flags.add(threadVarAccessed)
    accessThreadLocalVar(proc_emu_pre, sym1)
    assert usesThreadVars not in mod_emu_pre.flags, "should not flag module if proc already accessed"
    assert len(proc_emu_pre.procSec(cpsLocals).calls) == 0, "should not add locals if proc already accessed"
    print("  [2] accessThreadLocalVar: PASS")

    # 3. Test declareThreadVar
    # Case 3a: Emulated mode
    mod_emu2 = BModule(ConfigRef({optThreads, optTlsEmulation}))
    sym_a = PSym(id=10, loc=TLoc(snippet="myVarA", t="int32"))
    declareThreadVar(mod_emu2, sym_a, isExtern=False)
    assert 10 in mod_emu2.g.nimtvDeclared, "sym id should be registered"
    assert mod_emu2.g.nimtvDeps == ["int32"], "type should be in nimtvDeps"
    assert mod_emu2.g.nimtv.calls == [("addField", ("myVarA", "TypeDesc(int32)"))]

    # Duplicate declaration for same sym id in emulated mode (idempotent)
    declareThreadVar(mod_emu2, sym_a, isExtern=False)
    assert len(mod_emu2.g.nimtvDeps) == 1, "should not duplicate in nimtvDeps"
    assert len(mod_emu2.g.nimtv.calls) == 1, "should not call addField again"

    # Case 3b: Native mode, isExtern=True -> Extern
    mod_nat2 = BModule(ConfigRef())
    sym_ext = PSym(id=20, loc=TLoc(snippet="extVar", t="float64"))
    declareThreadVar(mod_nat2, sym_ext, isExtern=True)
    vars_calls = mod_nat2.s[cfsVars].calls
    assert len(vars_calls) == 1
    assert vars_calls[0][2]["visibility"] == Extern
    assert vars_calls[0][2]["kind"] == Threadvar

    # Case 3c: Native mode, lfExportLib -> ExportLibVar
    sym_exp = PSym(id=21, loc=TLoc(snippet="expVar", t="float64", flags={lfExportLib}))
    declareThreadVar(mod_nat2, sym_exp, isExtern=False)
    assert len(vars_calls) == 2
    assert vars_calls[1][2]["visibility"] == ExportLibVar

    # Case 3d: Native mode, Private
    sym_priv = PSym(id=22, loc=TLoc(snippet="privVar", t="float64"))
    declareThreadVar(mod_nat2, sym_priv, isExtern=False)
    assert len(vars_calls) == 3
    assert vars_calls[2][2]["visibility"] == Private

    # Case 3e: Emulated mode, multiple distinct symbols
    sym_b = PSym(id=11, loc=TLoc(snippet="myVarB", t="string"))
    declareThreadVar(mod_emu2, sym_b, isExtern=False)
    assert 11 in mod_emu2.g.nimtvDeclared, "second sym id should be registered"
    assert mod_emu2.g.nimtvDeps == ["int32", "string"], "both types should be in nimtvDeps"
    assert len(mod_emu2.g.nimtv.calls) == 2, "second field should be added"
    print("  [3] declareThreadVar: PASS")

    # 4. Test generateThreadLocalStorage
    # Case 4a: Buffer is empty -> no generation
    mod_gen = BModule(ConfigRef({optThreads, optTlsEmulation}))
    generateThreadLocalStorage(mod_gen)
    assert len(mod_gen.s[cfsSeqTypes].calls) == 0

    # Case 4b: Buffer has content, but neither usesThreadVars nor sfMainModule -> no generation
    mod_gen.g.nimtv.buf.data = "int threadvar1;\n"
    generateThreadLocalStorage(mod_gen)
    assert len(mod_gen.s[cfsSeqTypes].calls) == 0

    # Case 4c: Buffer has content and usesThreadVars in module flags
    mod_gen.flags.add(usesThreadVars)
    mod_gen.g.nimtvDeps = ["type1", "type2"]
    generateThreadLocalStorage(mod_gen)
    assert mod_gen in _finished_type_descriptions
    seq_calls = mod_gen.s[cfsSeqTypes].calls
    assert ("addTypedef", ("NimThreadVars",)) in seq_calls
    assert ("addSimpleStruct", ("", "")) in seq_calls
    assert ("add", ("int threadvar1;\n",)) in seq_calls

    # Case 4d: sfMainModule flag triggers generation even without usesThreadVars
    mod_main = BModule(ConfigRef({optThreads, optTlsEmulation}), is_main=True)
    mod_main.g.nimtv.buf.data = "int main_tv;\n"
    generateThreadLocalStorage(mod_main)
    main_seq_calls = mod_main.s[cfsSeqTypes].calls
    assert ("addTypedef", ("NimThreadVars",)) in main_seq_calls

    # Case 4e: Both usesThreadVars and sfMainModule present
    mod_both = BModule(ConfigRef({optThreads, optTlsEmulation}), is_main=True)
    mod_both.flags.add(usesThreadVars)
    mod_both.g.nimtv.buf.data = "int both_tv;\n"
    generateThreadLocalStorage(mod_both)
    assert ("addTypedef", ("NimThreadVars",)) in mod_both.s[cfsSeqTypes].calls
    print("  [4] generateThreadLocalStorage: PASS")

    # 5. Test generateThreadVarsSize
    # Case 5a: Buffer empty -> no-op
    mod_size = BModule(ConfigRef())
    generateThreadVarsSize(mod_size)
    assert len(mod_size.s[cfsProcs].calls) == 0

    # Case 5b: C backend, not compile to cpp -> visibility is None_
    mod_size.g.nimtv.buf.data = "tv data"
    generateThreadVarsSize(mod_size)
    p_calls = mod_size.s[cfsProcs].calls
    assert ("addDeclWithVisibility", (None_,)) in p_calls
    assert ("addProcHeader", ("NimThreadVarsSize", "NI", "void")) in p_calls
    assert ("finishProcHeaderWithBody", ()) in p_calls
    assert ("addReturn", ("((NI)(sizeof(NimThreadVars)))",)) in p_calls

    # Case 5c: backendCpp -> visibility is ExternC
    mod_size_cpp = BModule(ConfigRef(backend=backendCpp))
    mod_size_cpp.g.nimtv.buf.data = "tv data"
    generateThreadVarsSize(mod_size_cpp)
    assert ("addDeclWithVisibility", (ExternC,)) in mod_size_cpp.s[cfsProcs].calls

    # Case 5d: sfCompileToCpp in module flags -> visibility is ExternC
    mod_size_sfcpp = BModule(ConfigRef(backend=backendC), compile_to_cpp=True)
    mod_size_sfcpp.g.nimtv.buf.data = "tv data"
    generateThreadVarsSize(mod_size_sfcpp)
    assert ("addDeclWithVisibility", (ExternC,)) in mod_size_sfcpp.s[cfsProcs].calls

    # Case 5e: Both backendCpp and sfCompileToCpp -> visibility is ExternC
    mod_size_both = BModule(ConfigRef(backend=backendCpp), compile_to_cpp=True)
    mod_size_both.g.nimtv.buf.data = "tv data"
    generateThreadVarsSize(mod_size_both)
    assert ("addDeclWithVisibility", (ExternC,)) in mod_size_both.s[cfsProcs].calls
    print("  [5] generateThreadVarsSize: PASS")

    print("\nAll ccgthreadvars tests passed successfully!")
