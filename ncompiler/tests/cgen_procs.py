# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# Test scaffolding (nimic_translation_rules.md §2.1): the procs of cgen.nim and ccgtypes.nim that come after
# the C builders and before ccgtrav/ccgreset in cgen.nim's include order. Included by the harnesses in
# ncompiler/tests after cbuilderstmts. Each section is a subset of the named Nim module, line for line
# unless marked simplified.

# --- cgen.nim (subset) ---
# forward declarations (in cgen.nim before the C builders; here, so that harnesses without ccgthreadvars
# don't need them)
def _accessThreadLocalVar(p: BProc, s: PSym) -> None:
    pass


def _emulatedThreadVars(conf: ConfigRef) -> bool:
    """{.inline.}"""
    pass


def getModuleDllPath(m: BModule) -> Rope:
    # simplified: a fixed library path
    return makeCString(string("nimcache/libm.so"))


def rdLoc(a: TLoc) -> Rope:
    # 'read' location (deref if indirect)
    if TLocFlag.lfIndirect in a.flags:
        result = _cDeref(a.snippet)
    else:
        result = a.snippet
    return result


def lenField(p: BProc, val: Rope) -> Rope:
    """{.inline.}"""
    if p.module.compileToCpp:
        result = _derefField(val, string("len"))
    else:
        result = _dotField(_derefField(val, string("Sup")), string("len"))
    return result


def lenExpr(p: BProc, a: TLoc) -> Rope:
    if TGlobalOption.optSeqDestructors in p.config.globalOptions:
        if (p.config.usesSso() and a.lode is not None and a.t is not None and
                a.t.skipTypes(abstractInst).kind == TTypeKind.tyString):
            result = _cCall(cgsymValue(p.module, string("nimStrLen")), rdLoc(a))
        else:
            result = _dotField(rdLoc(a), string("len"))
    else:
        with let:
            ra = rdLoc(a)
        result = _cIfExpr(ra, lenField(p, ra), cIntValue(0))
    return result


def dataFieldAccessor(p: BProc, sym: Rope) -> Rope:
    if TGlobalOption.optSeqDestructors in p.config.globalOptions:
        result = _dotField(_wrapPar(sym), string("p"))
    else:
        result = sym
    return result


def dataField(p: BProc, val: Rope) -> Rope:
    """{.inline.}"""
    result = _derefField(dataFieldAccessor(p, val), string("data"))
    return result


# --- ccgtypes.nim (subset) ---
def mapSetType(conf: ConfigRef, typ: PType) -> TCTypeKind:
    match int(getSize(conf, typ)):
        case 1:
            result = TCTypeKind.ctInt8
        case 2:
            result = TCTypeKind.ctInt16
        case 4:
            result = TCTypeKind.ctInt32
        case 8:
            result = TCTypeKind.ctInt64
        case _:
            result = TCTypeKind.ctArray
    return result


def getTypeName(m: BModule, typ: PType, sig: SigHash) -> Rope:
    # simplified: the type's C name and the signature
    return typ.name + string(str(sig))


def fillObjectFields(m: BModule, typ: PType) -> None:
    # simplified: the field locations are preset
    discard


def genTypeInfoV1(m: BModule, t: PType, info: TLineInfo) -> Rope:
    # simplified: the name of the type info only
    return string("NTIv1_") + t.name
