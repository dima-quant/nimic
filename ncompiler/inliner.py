# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# included from cgen.nim (tests: ncompiler/tests/test_ccg.py)

def copySymdef(n: PNode, locals: mut @ Table[nint, PSym], idgen: IdGenerator, owner: PSym) -> PNode:
    match n.kind:
        case _ if n.kind in inrange(TNodeKind.nkEmpty, pred(TNodeKind.nkSym)) or n.kind in inrange(succ(TNodeKind.nkSym), TNodeKind.nkNilLit):
            result = n
        case TNodeKind.nkSym:
            with let:
                oldSym = n.sym
                newSym = copySym(oldSym, idgen)
            setOwner(newSym, owner)
            locals[oldSym.id] = newSym
            result = newSymNode(newSym, oldSym.info)
        case _:
            result = shallowCopy(n)
            for i in range(n.len):
                result[i] = copySymdef(n[i], locals, idgen, owner)
    return result

def copyInlineProcBody(n: PNode, locals: mut @ Table[nint, PSym], idgen: IdGenerator, owner: PSym) -> PNode:
    match n.kind:
        case _ if n.kind in inrange(TNodeKind.nkEmpty, pred(TNodeKind.nkSym)) or n.kind in inrange(succ(TNodeKind.nkSym), TNodeKind.nkNilLit):
            result = n
        case TNodeKind.nkSym:
            with let:
                sym = locals.getOrDefault(n.sym.id)
            if sym is not None:
                result = newSymNode(sym, n.info)
            else:
                result = n
        case TNodeKind.nkLetSection | TNodeKind.nkVarSection:
            result = shallowCopy(n)
            for i in range(n.len):
                with let:
                    it = n[i]
                if it.kind == TNodeKind.nkCommentStmt:
                    result[i] = it
                elif it.kind in {TNodeKind.nkIdentDefs, TNodeKind.nkConstDef}:
                    result[i] = shallowCopy(it)
                    for j in range(0, it.len - 2):
                        result[i][j] = copySymdef(it[j], locals, idgen, owner)
                    for j in range(it.len - 2, it.len):
                        result[i][j] = copyInlineProcBody(it[j], locals, idgen, owner)
                else:
                    assert it.kind == TNodeKind.nkVarTuple
                    result[i] = shallowCopy(it)
                    for j in range(0, it.len - 2):
                        assert it[j].kind == TNodeKind.nkSym
                        with let:
                            oldSym = it[j].sym
                            newSym = copySym(oldSym, idgen)
                        setOwner(newSym, owner)
                        locals[oldSym.id] = newSym
                        result[i][j] = newSymNode(newSym, oldSym.info)
                    for j in range(it.len - 2, it.len):
                        result[i][j] = copyInlineProcBody(it[j], locals, idgen, owner)
        case TNodeKind.nkForStmt | TNodeKind.nkParForStmt:
            result = shallowCopy(n)
            for i in range(0, n.len - 2):
                assert n[i].kind == TNodeKind.nkSym
                with let:
                    oldSym = n[i].sym
                    newSym = copySym(oldSym, idgen)
                setOwner(newSym, owner)
                locals[oldSym.id] = newSym
                result[i] = newSymNode(newSym, oldSym.info)
            result[n.len - 2] = copyInlineProcBody(n[n.len - 2], locals, idgen, owner)
            result[n.len - 1] = copyInlineProcBody(n[n.len - 1], locals, idgen, owner)
        case _ if (n.kind in routineDefs or n.kind == TNodeKind.nkTypeSection or n.kind == TNodeKind.nkTypeOfExpr or
                   n.kind == TNodeKind.nkMixinStmt or n.kind == TNodeKind.nkBindStmt or n.kind == TNodeKind.nkConstSection):
            result = n
        case _:
            result = shallowCopy(n)
            for i in range(n.len):
                result[i] = copyInlineProcBody(n[i], locals, idgen, owner)
    return result

def copyParams(n: PNode, locals: mut @ Table[nint, PSym], idgen: IdGenerator, owner: PSym) -> PNode:
    result = shallowCopy(n)
    result[0] = n[0]  # return type
    for i in range(1, n.len):
        with let:
            it = n[i]
        assert it.kind == TNodeKind.nkIdentDefs
        result[i] = shallowCopy(it)
        for j in range(0, it.len - 2):
            assert it[j].kind == TNodeKind.nkSym
            with let:
                oldSym = it[j].sym
                newSym = copySym(oldSym, idgen)
            setOwner(newSym, owner)
            locals[oldSym.id] = newSym
            result[i][j] = newSymNode(newSym, oldSym.info)
            addParam(owner.typ, newSym)
        for j in range(it.len - 2, it.len):
            result[i][j] = copyInlineProcBody(it[j], locals, idgen, owner)
    return result

def copyInlineProc(prc: PSym, idgen: IdGenerator) -> PSym:
    result = copySym(prc, idgen)
    with var:
        locals = initTable[nint, PSym]()
        a = shallowCopy(prc.ast)
    if resultPos < prc.ast.len and prc.ast[resultPos].kind == TNodeKind.nkSym:
        with let:
            oldRes = prc.ast[resultPos].sym
            newRes = copySym(oldRes, idgen)
        setOwner(newRes, result)
        locals[oldRes.id] = newRes
        a[resultPos] = newSymNode(newRes, oldRes.info)

    result.typ = copyType(prc.typ, idgen, result)
    result.typ.n = newNodeI(prc.typ.n.kind, prc.typ.n.info)
    if prc.typ.n.len > 0:
        result.typ.n.add(copyNode(prc.typ.n[0]))
        for i in range(1, prc.typ.n.len):
            with let:
                it = prc.typ.n[i]
            assert it.kind == TNodeKind.nkSym
            with let:
                oldSym = it.sym
                newSym = copySym(oldSym, idgen)
            setOwner(newSym, result)
            locals[oldSym.id] = newSym
            addParam(result.typ, newSym)

    for i in range(prc.ast.len):
        if i == paramsPos:
            a[i] = copyTree(prc.ast[i])
        elif i == resultPos and prc.ast[i].kind == TNodeKind.nkSym:
            _ = "handled above"
        else:
            a[i] = copyInlineProcBody(prc.ast[i], locals, idgen, result)
    result.ast = a
    return result
