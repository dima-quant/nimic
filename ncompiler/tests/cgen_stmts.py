# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# Test scaffolding (nimic_translation_rules_nim2.md §2.1): procs of cgen.nim and ccgstmts.nim that ccgtrav
# forward-declares, at their place in cgen.nim's include order (after ccgthreadvars). Included by the
# harnesses in ncompiler/tests. Each section is a subset of the named Nim module; simplified procs say so.

# --- cgen.nim (subset) ---
def _getTemp(p: BProc, t: PType, needsInit: bool = False) -> TLoc:
    # simplified: no C++ temporaries, no initialization
    p.labels += 1
    result = TLoc(snippet=string("T") + rope(p.labels) + string("_"), t=t)
    p.s(TCProcSection.cpsLocals)._addVar(kind=_VarKind.Local, name=result.snippet, typ=getTypeDesc(p.module, t))
    return result


# --- ccgstmts.nim (subset) ---
def _genCaseRange(p: BProc, branch: PNode, info: mut@_SwitchCaseBuilder) -> None:
    # simplified: integer literals, no ranges
    for j in range(branch.len - 1):
        p.s(TCProcSection.cpsStmts)._addCase(info, cIntValue(branch[j].intVal))
