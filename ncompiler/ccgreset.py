# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2020 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# included from cgen.nim (tests: ncompiler/tests/test_ccg.py)

## Code specialization instead of the old, incredibly slow 'genericReset'
## implementation.

def _specializeResetT(p: BProc, accessor: Rope, typ: PType) -> None:
    pass


def _specializeResetN(p: BProc, accessor: Rope, n: PNode, typ: PType) -> None:
    if n is None:
        return
    match n.kind:
        case TNodeKind.nkRecList:
            for i in range(n.len):
                _specializeResetN(p, accessor, n[i], typ)
        case TNodeKind.nkRecCase:
            if n[0].kind != TNodeKind.nkSym:
                internalError(p.config, n.info, string("specializeResetN"))
            with let:
                disc = n[0].sym
            if disc.loc.snippet == string(""):
                fillObjectFields(p.module, typ)
            if disc.loc.t is None:
                internalError(p.config, n.info, string("specializeResetN()"))
            with let:
                discField = _dotField(accessor, disc.loc.snippet)
            with p.s(TCProcSection.cpsStmts)._addSwitchStmt(discField):
                for i in range(1, n.len):
                    with let:
                        branch = n[i]
                    assert branch.kind in {TNodeKind.nkOfBranch, TNodeKind.nkElse}
                    with var:
                        caseBuilder = _SwitchCaseBuilder()
                    with p.s(TCProcSection.cpsStmts)._addSwitchCase(caseBuilder):
                        if branch.kind == TNodeKind.nkOfBranch:
                            _genCaseRange(p, branch, caseBuilder)
                        else:
                            p.s(TCProcSection.cpsStmts)._addCaseElse(caseBuilder)
                        with do:
                            _specializeResetN(p, accessor, lastSon(branch), typ)
                            p.s(TCProcSection.cpsStmts)._addBreak()
            _specializeResetT(p, discField, disc.loc.t)
        case TNodeKind.nkSym:
            with let:
                field = n.sym
            if field.typ.kind == TTypeKind.tyVoid:
                return
            if field.loc.snippet == string(""):
                fillObjectFields(p.module, typ)
            if field.loc.t is None:
                internalError(p.config, n.info, string("specializeResetN()"))
            _specializeResetT(p, _dotField(accessor, field.loc.snippet), field.loc.t)
        case _:
            internalError(p.config, n.info, string("specializeResetN()"))


def _specializeResetT(p: BProc, accessor: Rope, typ: PType) -> None:
    if typ is None:
        return

    match typ.kind:
        case (TTypeKind.tyGenericInst | TTypeKind.tyGenericBody | TTypeKind.tyTypeDesc | TTypeKind.tyAlias |
              TTypeKind.tyDistinct | TTypeKind.tyInferred | TTypeKind.tySink | TTypeKind.tyOwned):
            _specializeResetT(p, accessor, skipModifier(typ))
        case TTypeKind.tyArray:
            with let:
                arraySize = lengthOrd(p.config, typ.indexType)
            with var:
                i: TLoc = _getTemp(p, getSysType(p.module.g.graph, unknownLineInfo, TTypeKind.tyInt))
            with p.s(TCProcSection.cpsStmts)._addForRangeExclusive(i.snippet, cIntValue(0), cIntValue(arraySize)):
                _specializeResetT(p, _subscript(accessor, i.snippet), typ.elementType)
        case TTypeKind.tyObject:
            with var:
                x = typ.baseClass
            if x is not None:
                x = x.skipTypes(skipPtrs)
            _specializeResetT(p, accessor._parentObj(p.module), x)
            if typ.n is not None:
                if typ.sym is not None and TSymFlag.sfImportc in typ.sym.flags:
                    # imported C struct, nimZeroMem
                    p.s(TCProcSection.cpsStmts)._addCallStmt(cgsymValue(p.module, string("nimZeroMem")),
                        _cCast(_ptrType(CPointer), _cAddr(accessor)),
                        _cSizeof(getTypeDesc(p.module, typ)))
                else:
                    _specializeResetN(p, accessor, typ.n, typ)
        case TTypeKind.tyTuple:
            with let:
                typ = getUniqueType(typ)
            for i, a in typ.ikids():
                _specializeResetT(p, _dotField(accessor, string("Field") + string(str(i))), a)

        case TTypeKind.tyString | TTypeKind.tyRef | TTypeKind.tySequence:
            p.s(TCProcSection.cpsStmts)._addCallStmt(cgsymValue(p.module, string("unsureAsgnRef")),
                _cCast(_ptrType(CPointer), _cAddr(accessor)),
                NimNil)

        case TTypeKind.tyProc:
            if typ.callConv == TCallingConvention.ccClosure:
                p.s(TCProcSection.cpsStmts)._addCallStmt(cgsymValue(p.module, string("unsureAsgnRef")),
                    _cCast(_ptrType(CPointer), _cAddr(_dotField(accessor, string("ClE_0")))),
                    NimNil)
                p.s(TCProcSection.cpsStmts)._addFieldAssignment(accessor, string("ClP_0"), NimNil)
            else:
                p.s(TCProcSection.cpsStmts)._addAssignment(accessor, NimNil)
        case (TTypeKind.tyChar | TTypeKind.tyBool | TTypeKind.tyEnum | TTypeKind.tyRange | TTypeKind.tyInt |
              TTypeKind.tyInt8 | TTypeKind.tyInt16 | TTypeKind.tyInt32 | TTypeKind.tyInt64 | TTypeKind.tyFloat |
              TTypeKind.tyFloat32 | TTypeKind.tyFloat64 | TTypeKind.tyFloat128 | TTypeKind.tyUInt |
              TTypeKind.tyUInt8 | TTypeKind.tyUInt16 | TTypeKind.tyUInt32 | TTypeKind.tyUInt64):
            p.s(TCProcSection.cpsStmts)._addAssignment(accessor, cIntValue(0))
        case TTypeKind.tyCstring | TTypeKind.tyPointer | TTypeKind.tyPtr | TTypeKind.tyVar | TTypeKind.tyLent:
            p.s(TCProcSection.cpsStmts)._addAssignment(accessor, NimNil)
        case TTypeKind.tySet:
            match mapSetType(p.config, typ):
                case TCTypeKind.ctArray:
                    with let:
                        t = getTypeDesc(p.module, typ)
                    p.s(TCProcSection.cpsStmts)._addCallStmt(cgsymValue(p.module, string("nimZeroMem")),
                        accessor,
                        _cSizeof(t))
                case TCTypeKind.ctInt8 | TCTypeKind.ctInt16 | TCTypeKind.ctInt32 | TCTypeKind.ctInt64:
                    p.s(TCProcSection.cpsStmts)._addAssignment(accessor, cIntValue(0))
                case _:
                    raiseAssert(string("unexpected set type kind"))
        case (TTypeKind.tyNone | TTypeKind.tyEmpty | TTypeKind.tyNil | TTypeKind.tyUntyped | TTypeKind.tyTyped |
              TTypeKind.tyGenericInvocation | TTypeKind.tyGenericParam | TTypeKind.tyOrdinal |
              TTypeKind.tyOpenArray | TTypeKind.tyForward | TTypeKind.tyVarargs | TTypeKind.tyUncheckedArray |
              TTypeKind.tyError | TTypeKind.tyBuiltInTypeClass | TTypeKind.tyUserTypeClass |
              TTypeKind.tyUserTypeClassInst | TTypeKind.tyCompositeTypeClass | TTypeKind.tyAnd |
              TTypeKind.tyOr | TTypeKind.tyNot | TTypeKind.tyAnything | TTypeKind.tyStatic |
              TTypeKind.tyFromExpr | TTypeKind.tyConcept | TTypeKind.tyVoid | TTypeKind.tyIterable):
            discard


def _specializeReset(p: BProc, a: TLoc) -> None:
    _specializeResetT(p, rdLoc(a), a.t)
