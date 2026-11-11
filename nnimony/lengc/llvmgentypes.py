# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/llvmgentypes.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

# included from llvmcodegen.nim
# Generates LLVM IR types from Leng types.

from __future__ import annotations
from nimic.ntypes import *


def _integralBitsLLVM(t: Cursor, c: LLVMCode) -> nint:
    """{.inline.}"""
    with let:
        res = intVal(t)
    return c._bits if res == -1 else nint(res)


# Forward decl: the genTypeLLVM <-> ensureTypeDef <-> genTypeDefBodyLLVM cycle.
def _ensureTypeDef(c: mut @ LLVMCode, symId: SymId) -> LLType:
    pass


def _genTypeLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> LLType:
    ## Returns the LLType for a NIF type node.
    match typeKind(n):
        case LengType.VoidT:
            result = c.prim.voidT
            skip(n)
        case LengType.IT:
            with into(n):
                if kind(n) == NifKind.IntLit:
                    result = c.llIntBits(_integralBitsLLVM(n, c))
                    n.inc()
                else:
                    result = c.llIntBits(c._bits)
                while n.hasMore():
                    skip(n)
        case LengType.UT:
            with into(n):
                if kind(n) == NifKind.IntLit:
                    result = c.llIntBits(_integralBitsLLVM(n, c))
                    n.inc()
                else:
                    result = c.llIntBits(c._bits)
                while n.hasMore():
                    skip(n)
        case LengType.FT:
            with into(n):
                with var:
                    bits = 64
                if kind(n) == NifKind.IntLit:
                    bits = _integralBitsLLVM(n, c)
                    n.inc()
                while n.hasMore():
                    skip(n)
                result = c.prim.f32_ if bits == 32 else newLLFloatType(128) if bits == 128 else c.prim.f64_
        case LengType.BoolT:
            with into(n):
                while n.hasMore():
                    skip(n)
            result = c.prim.i8_  # Use i8 for bool to match C ABI (i1 has different ABI)
        case LengType.CT:
            with into(n):
                if kind(n) == NifKind.IntLit:
                    result = c.llIntBits(_integralBitsLLVM(n, c))
                    n.inc()
                else:
                    result = c.prim.i8_
                while n.hasMore():
                    skip(n)
        case LengType.NoType:
            if kind(n) == NifKind.Symbol:
                with let:
                    d = getDeclOrNil(c._m, symId(n))
                if not isNil(d) and d.kind == LengSym.TypeY:
                    with let:
                        decl = asTypeDecl(d.pos)
                    if typeKind(decl.body) == LengType.ProctypeT:
                        result = c.prim.ptrT
                        n.inc()
                        return result
                result = _ensureTypeDef(c, symId(n))  # aggregate -> named ref; non-aggregate -> inline
                n.inc()
            else:
                _error(c._m, string("node is not a type: "), n)
        case LengType.PtrT | LengType.AptrT:
            result = c.prim.ptrT
            skip(n)
        case LengType.FlexarrayT:
            with into(n):
                with let:
                    elemType = _genTypeLLVM(c, n)
                result = newLLArrayType(0, elemType)
                while n.hasMore(): skip(n)
        case LengType.ProctypeT:
            result = c.prim.ptrT
            skip(n)
        case LengType.VarargsT:
            result = c.prim.ptrT  # placeholder; handled specially in signatures
            skip(n)
        case LengType.EnumT:
            with into(n):
                result = _genTypeLLVM(c, n)
                while n.hasMore():
                    skip(n)
        case LengType.ArrayT:
            with into(n):
                with let:
                    elemType = _genTypeLLVM(c, n)
                with var:
                    sz = 0
                if kind(n) == NifKind.IntLit:
                    sz = nint(intVal(n))
                    skip(n)
                elif kind(n) == NifKind.UIntLit:
                    sz = nint(uintVal(n))
                    skip(n)
                result = newLLArrayType(sz, elemType)
                while n.hasMore(): skip(n)
        case LengType.ObjectT | LengType.UnionT:
            with let:
                typeDecl = c._m.tracebackTypeC(n)
            if not typeDecl.cursorIsNil() and stmtKind(typeDecl) == LengStmt.TypeS:
                with let:
                    decl = asTypeDecl(typeDecl)
                if kind(decl.name) == NifKind.SymbolDef:
                    result = _ensureTypeDef(c, symId(decl.name))
                else:
                    result = c.prim.ptrT
            else:
                result = c.prim.ptrT
            skip(n)
        case LengType.ParamsT:
            _error(c._m, string("params type not allowed in expression context: "), n)
    return result


def _genTypeLLVMReadOnly(c: mut @ LLVMCode, n: Cursor) -> LLType:
    with var:
        nn = n.copy()
    result = _genTypeLLVM(c, nn)
    return result


def _fixedArrayLen(c: mut @ LLVMCode, n: Cursor) -> nint:
    result = -1
    with var:
        t = navigateToObjectBody(c._m, n)
    if typeKind(t) == LengType.ArrayT:
        t.inc()
        skip(t)
        if kind(t) == NifKind.IntLit:
            result = nint(intVal(t))
        elif kind(t) == NifKind.UIntLit:
            result = nint(uintVal(t))
    return result


def _typeSizeBits(c: mut @ LLVMCode, n: Cursor) -> nint:
    match typeKind(n):
        case LengType.IT | LengType.UT | LengType.CT:
            with var:
                nn = n.copy()
            nn.inc()
            if kind(nn) == NifKind.IntLit:
                with let:
                    bits = intVal(nn)
                result = c._bits if bits == -1 else nint(bits)
            else:
                result = copy(c._bits)
        case LengType.FT:
            with var:
                nn = n.copy()
            nn.inc()
            if kind(nn) == NifKind.IntLit:
                with let:
                    bits = intVal(nn)
                result = 64 if bits == -1 else nint(bits)
            else:
                result = 64
        case LengType.BoolT:
            result = 8
        case LengType.PtrT | LengType.AptrT | LengType.ProctypeT:
            result = copy(c._bits)
        case LengType.FlexarrayT:
            result = 0
        case LengType.EnumT:
            with var:
                nn = n.copy()
            nn.inc()
            result = _typeSizeBits(c, nn)
        case LengType.ArrayT:
            with var:
                nn = n.copy()
            nn.inc()
            with let:
                elemBits = _typeSizeBits(c, nn)
            skip(nn)
            with var:
                count = 0
            if kind(nn) == NifKind.IntLit:
                count = nint(intVal(nn))
            elif kind(nn) == NifKind.UIntLit:
                count = nint(uintVal(nn))
            result = elemBits * count
        case LengType.NoType:
            if kind(n) == NifKind.Symbol:
                with let:
                    d = getDeclOrNil(c._m, symId(n))
                if not isNil(d) and d.kind == LengSym.TypeY:
                    with let:
                        decl = asTypeDecl(d.pos)
                    result = _typeSizeBits(c, decl.body)
                else:
                    result = copy(c._bits)
            else:
                result = copy(c._bits)
        case LengType.ObjectT:
            with var:
                nn = n.copy()
            with into(nn):
                if kind(nn) == NifKind.Symbol:
                    result = _typeSizeBits(c, nn)
                    nn.inc()
                elif kind(nn) == NifKind.DotToken:
                    result = 0
                    nn.inc()
                else:
                    result = 0
                while nn.hasMore():
                    if substructureKind(nn) == LengOther.FldU:
                        with var:
                            fdecl = takeFieldDecl(nn)
                        result += _typeSizeBits(c, fdecl.typ)
                    elif typeKind(nn) == LengType.UnionT:
                        result += _typeSizeBits(c, nn)
                        skip(nn)
                    else:
                        skip(nn)
        case LengType.UnionT:
            with var:
                nn = n.copy()
            result = 0
            with into(nn):
                while nn.hasMore():
                    if substructureKind(nn) == LengOther.FldU:
                        with var:
                            fdecl = takeFieldDecl(nn)
                        with let:
                            sz = _typeSizeBits(c, fdecl.typ)
                        if sz > result: result = sz
                    elif typeKind(nn) in Tset[LengType](LengType.ObjectT, LengType.UnionT):
                        with let:
                            sz = _typeSizeBits(c, nn)
                        if sz > result: result = sz
                        skip(nn)
                    elif isUnionBranch(nn):
                        with let:
                            b = asUnionBranch(nn)
                        if typeKind(b.body) == LengType.ObjectT:
                            with let:
                                sz = _typeSizeBits(c, b.body)
                            if sz > result: result = sz
                        skip(nn)
                    else:
                        skip(nn)
        case LengType.VoidT | LengType.VarargsT | LengType.ParamsT:
            result = 0
    return result


def _typeAlignBits(c: mut @ LLVMCode, n: Cursor) -> nint:
    match typeKind(n):
        case LengType.IT | LengType.UT | LengType.CT | LengType.FT | LengType.BoolT:
            result = _typeSizeBits(c, n)
            if result > c._bits: result = copy(c._bits)
        case LengType.PtrT | LengType.AptrT | LengType.ProctypeT:
            result = copy(c._bits)
        case LengType.EnumT:
            with var:
                nn = n.copy()
            nn.inc()
            result = _typeAlignBits(c, nn)
        case LengType.ArrayT:
            result = _typeAlignBits(c, _firstSon(n))
        case LengType.NoType:
            if kind(n) == NifKind.Symbol:
                with let:
                    d = getDeclOrNil(c._m, symId(n))
                if not isNil(d) and d.kind == LengSym.TypeY:
                    with let:
                        decl = asTypeDecl(d.pos)
                    result = _typeAlignBits(c, decl.body)
                else:
                    result = copy(c._bits)
            else:
                result = copy(c._bits)
        case LengType.ObjectT | LengType.UnionT:
            with var:
                nn = n.copy()
            with into(nn):
                if typeKind(n) == LengType.ObjectT:
                    if kind(nn) == NifKind.Symbol:
                        result = _typeAlignBits(c, nn)
                        nn.inc()
                    elif kind(nn) == NifKind.DotToken:
                        result = 0
                        nn.inc()
                    else:
                        result = 0
                else:
                    result = 0
                while nn.hasMore():
                    if substructureKind(nn) == LengOther.FldU:
                        with var:
                            fdecl = takeFieldDecl(nn)
                        with let:
                            a = _typeAlignBits(c, fdecl.typ)
                        if a > result: result = a
                    elif typeKind(nn) in Tset[LengType](LengType.ObjectT, LengType.UnionT):
                        with let:
                            a = _typeAlignBits(c, nn)
                        if a > result: result = a
                        skip(nn)
                    elif isUnionBranch(nn):
                        with let:
                            b = asUnionBranch(nn)
                        if typeKind(b.body) == LengType.ObjectT:
                            with let:
                                a = _typeAlignBits(c, b.body)
                            if a > result: result = a
                        skip(nn)
                    else:
                        skip(nn)
        case _:
            result = 8
    return result

# ---- Named-type definitions: lazily emitted by ensureTypeDef on first use. ----


class _UnionCandidate(Object):
    typ: LLType
    sizeBits: nint
    alignBits: nint


def _genObjectBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> LLType:
    pass


def _genUnionBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> LLType:
    pass


def _collectUnionCandidates(c: mut @ LLVMCode, n: Cursor, candidates: mut @ seq[_UnionCandidate]):
    with var:
        nn = n.copy()
    with into(nn):
        while nn.hasMore():
            if substructureKind(nn) == LengOther.FldU:
                with var:
                    decl = takeFieldDecl(nn)
                with let:
                    sz = _typeSizeBits(c, decl.typ)
                    al = _typeAlignBits(c, decl.typ)
                with var:
                    t = decl.typ.copy()
                candidates.add(_UnionCandidate(typ=_genTypeLLVM(c, t), sizeBits=sz, alignBits=al))
            elif typeKind(nn) == LengType.ObjectT:
                with var:
                    obj = nn.copy()
                candidates.add(_UnionCandidate(typ=_genObjectBodyLLVM(c, obj), sizeBits=_typeSizeBits(c, nn), alignBits=_typeAlignBits(c, nn)))
                skip(nn)
            elif typeKind(nn) == LengType.UnionT:
                with var:
                    u = nn.copy()
                candidates.add(_UnionCandidate(typ=_genUnionBodyLLVM(c, u), sizeBits=_typeSizeBits(c, nn), alignBits=_typeAlignBits(c, nn)))
                skip(nn)
            elif isUnionBranch(nn):
                # Discriminated-union branch: only the payload contributes to layout.
                # A field-less branch adds no candidate, exactly as an omitted branch
                # did before the branches were tagged.
                with let:
                    b = asUnionBranch(nn)
                if typeKind(b.body) == LengType.ObjectT:
                    with var:
                        obj = b.body.copy()
                    candidates.add(_UnionCandidate(typ=_genObjectBodyLLVM(c, obj), sizeBits=_typeSizeBits(c, b.body), alignBits=_typeAlignBits(c, b.body)))
                skip(nn)
            else:
                skip(nn)


def _genUnionBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> LLType:
    with var:
        candidates: seq[_UnionCandidate] = seq[_UnionCandidate]([])
    _collectUnionCandidates(c, n, candidates)
    skip(n)
    if candidates.len == 0:
        return newLLStructType(seq())
    with var:
        maxSize = candidates[0].sizeBits
        maxAlign = candidates[0].alignBits
        repIdx = 0
    for i in range(1, candidates.len):
        if candidates[i].sizeBits > maxSize: maxSize = candidates[i].sizeBits
        if candidates[i].alignBits > maxAlign: maxAlign = candidates[i].alignBits
        if candidates[i].alignBits > candidates[repIdx].alignBits or (candidates[i].alignBits == candidates[repIdx].alignBits and candidates[i].sizeBits > candidates[repIdx].sizeBits):
            repIdx = i
    with let:
        sizeBytes = (maxSize + 7) // 8
        alignBytes = maxAlign // 8
        repSizeBytes = (candidates[repIdx].sizeBits + 7) // 8
    with var:
        fields: seq[LLStructField] = seq[LLStructField]([])
    if alignBytes <= 1:
        fields.add(LLStructField(typ=newLLArrayType(sizeBytes, c.prim.i8_)))
    else:
        fields.add(LLStructField(typ=candidates[repIdx].typ))
        with let:
            paddingBytes = sizeBytes - repSizeBytes
        if paddingBytes > 0:
            fields.add(LLStructField(typ=newLLArrayType(paddingBytes, c.prim.i8_)))
    result = newLLStructType(fields)
    return result


def _flushBitfieldAccum(fields: mut @ seq[LLType], bitfieldAccum: mut @ int64):
    if bitfieldAccum > 0:
        with var:
            storeBits = 8
        while storeBits < bitfieldAccum: storeBits *= 2
        if storeBits > 64: storeBits = 64
        fields.add(newLLIntType(nint(storeBits)))
        bitfieldAccum <<= 0


def _accumulateBitfield(c: mut @ LLVMCode, fields: mut @ seq[LLType], bitfieldAccum: mut @ int64, bitfieldUnit: mut @ nint, bits: int64, typ: Cursor):
    with let:
        unitBits = _typeSizeBits(c, typ)
    if bitfieldUnit == 0:
        bitfieldUnit <<= unitBits
    if unitBits != bitfieldUnit or bitfieldAccum + bits > bitfieldUnit:
        _flushBitfieldAccum(fields, bitfieldAccum)
        bitfieldUnit <<= unitBits
    bitfieldAccum += bits


def _addObjectFieldsLLVM(c: mut @ LLVMCode, n: mut @ Cursor, fields: mut @ seq[LLType], bitfieldAccum: mut @ int64, bitfieldUnit: mut @ nint):
    with let:
        kind = typeKind(n)
    with into(n):
        if kind == LengType.ObjectT:
            if nifcoreparse.kind(n) == NifKind.DotToken:
                n.inc()
            elif nifcoreparse.kind(n) == NifKind.Symbol:
                with let:
                    baseName = c._mangleSym(symId(n))
                fields.add(LLType(kind=LLTypeKind.llStruct, name=baseName))
                n.inc()
            else:
                _error(c._m, string("expected `Symbol` or `.` for inheritance but got: "), n)
        while n.hasMore():
            if substructureKind(n) == LengOther.FldU:
                with var:
                    decl = takeFieldDecl(n)
                with let:
                    bits = _extractBitfieldBits(decl.pragmas)
                if bits > 0:
                    _accumulateBitfield(c, fields, bitfieldAccum, bitfieldUnit, bits, decl.typ)
                else:
                    _flushBitfieldAccum(fields, bitfieldAccum)
                    bitfieldUnit <<= 0
                    with var:
                        t = decl.typ.copy()
                    fields.add(_genTypeLLVM(c, t))
            elif typeKind(n) == LengType.UnionT:
                _flushBitfieldAccum(fields, bitfieldAccum)
                bitfieldUnit <<= 0
                fields.add(_genUnionBodyLLVM(c, n))
            elif typeKind(n) == LengType.ObjectT:
                _flushBitfieldAccum(fields, bitfieldAccum)
                bitfieldUnit <<= 0
                _addObjectFieldsLLVM(c, n, fields, bitfieldAccum, bitfieldUnit)
            else:
                _error(c._m, string("expected `fld` but got: "), n)


def _genObjectBodyLLVM(c: mut @ LLVMCode, n: mut @ Cursor) -> LLType:
    with let:
        kind = typeKind(n)
    if kind == LengType.UnionT:
        return _genUnionBodyLLVM(c, n)
    with var:
        fields: seq[LLType] = seq[LLType]([])
        bitfieldAccum = i64(0)
        bitfieldUnit = nint(0)
    _addObjectFieldsLLVM(c, n, fields, bitfieldAccum, bitfieldUnit)
    _flushBitfieldAccum(fields, bitfieldAccum)
    with var:
        sfields: seq[LLStructField] = seq[LLStructField]([])
    for ft in fields:
        sfields.add(LLStructField(typ=ft))
    result = newLLStructType(sfields)
    return result


class FieldAccess(Object):
    isBranch: bool
    index: nint
    branchType: LLType
    branchIndex: nint


def _searchFieldIdx(c: mut @ LLVMCode, body: mut @ Cursor, fldSym: SymId, access: mut @ FieldAccess, bitfieldAccum: mut @ int64, bitfieldUnit: mut @ nint) -> bool:
    with let:
        kind = typeKind(body)
    result = False
    for _ in into(body):
        if kind == LengType.ObjectT:
            if nifcoreparse.kind(body) == NifKind.Symbol:
                body.inc()
                access.index = 1
            elif nifcoreparse.kind(body) == NifKind.DotToken:
                body.inc()
        while body.hasMore() and not result:
            if substructureKind(body) == LengOther.FldU:
                with let:
                    decl = takeFieldDecl(body)
                    bits = _extractBitfieldBits(decl.pragmas)
                if bits > 0:
                    with let:
                        unitBits = _typeSizeBits(c, decl.typ)
                    if bitfieldUnit == 0:
                        bitfieldUnit <<= unitBits
                    if unitBits != bitfieldUnit or bitfieldAccum + bits > bitfieldUnit:
                        if bitfieldAccum > 0: access.index += 1
                        bitfieldAccum <<= 0
                        bitfieldUnit <<= unitBits
                    if nifcoreparse.kind(decl.name) == NifKind.SymbolDef and symId(decl.name) == fldSym:
                        return True
                    bitfieldAccum += bits
                else:
                    if bitfieldAccum > 0:
                        access.index += 1
                        bitfieldAccum <<= 0
                        bitfieldUnit <<= 0
                    if nifcoreparse.kind(decl.name) == NifKind.SymbolDef and symId(decl.name) == fldSym:
                        return True
                    access.index += 1
            elif typeKind(body) == LengType.UnionT:
                if bitfieldAccum > 0:
                    access.index += 1
                    bitfieldAccum <<= 0
                    bitfieldUnit <<= 0
                with let:
                    unionIdx = copy(access.index)
                with var:
                    unionBody = body.copy()
                skip(unionBody)
                with var:
                    search = body.copy()
                search.inc()
                while search.hasMore():
                    if substructureKind(search) == LengOther.FldU:
                        with let:
                            fdecl = takeFieldDecl(search)
                        if nifcoreparse.kind(fdecl.name) == NifKind.SymbolDef and symId(fdecl.name) == fldSym:
                            with var:
                                ft = fdecl.typ.copy()
                            access <<= FieldAccess(isBranch=True, index=unionIdx, branchType=_genUnionBodyLLVM(c, ft), branchIndex=0)
                            return True
                    elif typeKind(search) == LengType.ObjectT:
                        with var:
                            branchCur = search.copy()
                        with let:
                            brType = _genObjectBodyLLVM(c, branchCur)
                        with var:
                            innerAccess = default(FieldAccess)
                            brBfAccum = i64(0)
                            brBfUnit = nint(0)
                        if _searchFieldIdx(c, search, fldSym, innerAccess, brBfAccum, brBfUnit):
                            access <<= FieldAccess(isBranch=True, index=unionIdx, branchType=brType, branchIndex=innerAccess.index)
                            return True
                    elif isUnionBranch(search):
                        # Discriminated-union branch: the payload object is what carries
                        # the fields, so this resolves exactly like the untagged branch
                        # above. Missing this arm would fall through to `skip search`,
                        # leaving `access.index` at the union rather than the field - a
                        # silently wrong GEP index, not a compile error.
                        with let:
                            b = asUnionBranch(search)
                        if typeKind(b.body) == LengType.ObjectT:
                            with var:
                                brCur = b.body.copy()
                            with let:
                                brType = _genObjectBodyLLVM(c, brCur)
                            with var:
                                innerAccess = default(FieldAccess)
                                brBfAccum = i64(0)
                                brBfUnit = nint(0)
                                inner = b.body.copy()
                            if _searchFieldIdx(c, inner, fldSym, innerAccess, brBfAccum, brBfUnit):
                                access <<= FieldAccess(isBranch=True, index=unionIdx, branchType=brType, branchIndex=innerAccess.index)
                                return True
                        skip(search)
                    else:
                        skip(search)
                body <<= unionBody
                access.index += 1
            elif typeKind(body) == LengType.ObjectT:
                if bitfieldAccum > 0:
                    access.index += 1
                    bitfieldAccum <<= 0
                    bitfieldUnit <<= 0
                if _searchFieldIdx(c, body, fldSym, access, bitfieldAccum, bitfieldUnit):
                    return True
            else:
                skip(body)
    return False


def _fieldIndex(c: mut @ LLVMCode, objBody: Cursor, fldSym: SymId) -> nint:
    result = 0
    if typeKind(objBody) == LengType.UnionT:
        return 0
    with var:
        body = objBody.copy()
        bitfieldAccum = i64(0)
        bitfieldUnit = nint(0)
        access = default(FieldAccess)
    _ = _searchFieldIdx(c, body, fldSym, access, bitfieldAccum, bitfieldUnit)
    result = access.index
    return result


def _fieldAccessLLVM(c: mut @ LLVMCode, objBody: Cursor, fldSym: SymId) -> FieldAccess:
    if typeKind(objBody) == LengType.UnionT:
        result = FieldAccess(index=0)
        return result
    with var:
        body = objBody.copy()
        bitfieldAccum = i64(0)
        bitfieldUnit = nint(0)
    result = FieldAccess()
    _ = _searchFieldIdx(c, body, fldSym, result, bitfieldAccum, bitfieldUnit)
    return result


def _genTypeDefBodyLLVM(c: mut @ LLVMCode, body: mut @ Cursor) -> LLType:
    ## Build the body `LLType` for a named type. Returns nil for kinds we can't
    ## render (ensureTypeDef then emits `= type opaque`); empty objects become `{}`.
    match typeKind(body):
        case LengType.ObjectT | LengType.UnionT:
            # Empty object -> `{}` (sized 0), never nil: nil would serialize as opaque
            # (unsized) and break `alloca %Empty`.
            result = _genObjectBodyLLVM(c, body)
        case LengType.ArrayT:
            with into(body):
                with let:
                    elemType = _genTypeLLVM(c, body)
                with var:
                    sz = 0
                if kind(body) == NifKind.IntLit:
                    sz = nint(intVal(body))
                    skip(body)
                elif kind(body) == NifKind.UIntLit:
                    sz = nint(uintVal(body))
                    skip(body)
                result = newLLArrayType(sz, elemType)
                while body.hasMore(): skip(body)
        case LengType.EnumT:
            with into(body):
                result = _genTypeLLVM(c, body)
                while body.hasMore():
                    skip(body)
        case LengType.ProctypeT:
            with let:
                procType = takeProcType(body)
            with var:
                retType = LLType()
            if kind(procType.returnType) == NifKind.DotToken:
                retType = c.prim.voidT
            else:
                with var:
                    rt = procType.returnType.copy()
                retType = _genTypeLLVM(c, rt)
            with var:
                paramTypes: seq[LLType] = seq[LLType]([])
            if kind(procType.params) == NifKind.TagLit:
                with var:
                    p = procType.params.copy()
                for _ in loopInto(p):
                    with let:
                        paramDecl = takeParamDecl(p)
                    with var:
                        t = paramDecl.typ.copy()
                    paramTypes.add(_genTypeLLVM(c, t))
            result = newLLFuncType(retType, paramTypes, False)
        case _:
            result = None
    return result


def _typeDefByName(c: mut @ LLVMCode, name: string) -> nint:
    ## Index of `name` in c.module.typeDefs, or -1. Linear scan: type count is small.
    for i, nt in pairs(c.module.typeDefs):
        if nt.name == name: return i
    return -1


def _ensureTypeDef(c: mut @ LLVMCode, symId: SymId) -> LLType:
    ## Aggregates (object/union) get a `%Name = type <body>` def; non-aggregates
    ## (enum→scalar, array) resolve inline — LLVM forbids forward refs to non-struct
    ## named types. The placeholder is inserted before the body so recursion returns
    ## a ref instead of looping.
    with let:
        name = mangleToC(c._m.pool.symString(symId))
    if _typeDefByName(c, name) >= 0:
        return LLType(kind=LLTypeKind.llStruct, name=name)  # already registered aggregate (incl. placeholder)
    with let:
        d = getDeclOrNil(c._m, symId)
    if isNil(d) or d.kind != LengSym.TypeY:
        return c.prim.ptrT  # unresolved symbol -> opaque pointer
    with let:
        decl = asTypeDecl(d.pos)
    with var:
        body = decl.body.copy()
    if typeKind(body) not in Tset[LengType](LengType.ObjectT, LengType.UnionT):
        # Non-aggregate: inline the underlying LLType, no %Name def.
        result = _genTypeDefBodyLLVM(c, body)
        if result is None: result = c.prim.ptrT
        return result
    # Aggregate: placeholder before the body for recursion safety (above).
    with var:
        packed = False
    if substructureKind(decl.pragmas) == LengOther.PragmasU:
        with var:
            p = decl.pragmas.copy()
        for _ in loopInto(p):
            if pragmaKind(p) == LengPragma.PackedP: packed = True
            skip(p)
    with let:
        idx = c.module.typeDefs.len
    c.module.typeDefs.add(LLNamedType(name=name, body=None, packed=False))  # placeholder
    with let:
        bodyType = _genTypeDefBodyLLVM(c, body)
    if bodyType is not None:
        c.module.typeDefs[idx] = LLNamedType(name=name, body=bodyType, packed=packed)
        # else: placeholder stays nil => serializes as `= type opaque`
    result = LLType(kind=LLTypeKind.llStruct, name=name)
    return result


@template_expand
def _collectStructFieldTypes(c: mut @ LLVMCode, body: mut @ Cursor, types: mut @ seq[LLType], bitfieldAccum: mut @ int64, bitfieldUnit: mut @ nint):
    @template
    def flushBf():
        if bitfieldAccum > 0:
            with var:
                storeBits = 8
            while storeBits < bitfieldAccum: storeBits *= 2
            if storeBits > 64: storeBits = 64
            types.add(newLLIntType(storeBits))
            bitfieldAccum <<= 0
            bitfieldUnit <<= 0
    while body.hasMore():
        if substructureKind(body) == LengOther.FldU:
            with var:
                fdecl = takeFieldDecl(body)
            with let:
                bits = _extractBitfieldBits(fdecl.pragmas)
            if bits > 0:
                with let:
                    unitBits = _typeSizeBits(c, fdecl.typ)
                if bitfieldUnit == 0:
                    bitfieldUnit <<= unitBits
                if unitBits != bitfieldUnit or bitfieldAccum + bits > bitfieldUnit:
                    flushBf()
                    bitfieldUnit <<= unitBits
                bitfieldAccum += bits
            else:
                flushBf()
                with var:
                    t = fdecl.typ.copy()
                types.add(_genTypeLLVM(c, t))
        elif typeKind(body) == LengType.UnionT:
            flushBf()
            types.add(_genUnionBodyLLVM(c, body))
        elif typeKind(body) == LengType.ObjectT:
            flushBf()
            with into(body):
                _collectStructFieldTypes(c, body, types, bitfieldAccum, bitfieldUnit)
        else:
            body.inc()
    flushBf()


def _getStructFieldTypes(c: mut @ LLVMCode, typeSym: Cursor) -> seq[LLType]:
    result = seq[LLType]([])
    if kind(typeSym) == NifKind.Symbol:
        with let:
            d = getDeclOrNil(c._m, symId(typeSym))
        if not isNil(d) and d.kind == LengSym.TypeY:
            with let:
                decl = asTypeDecl(d.pos)
            with var:
                body = decl.body.copy()
            if typeKind(body) == LengType.UnionT:
                result.add(_genTypeLLVMReadOnly(c, body))
            elif typeKind(body) == LengType.ObjectT:
                with var:
                    bitfieldAccum = i64(0)
                    bitfieldUnit = nint(0)
                with into(body):
                    if kind(body) == NifKind.Symbol:
                        with let:
                            baseName = mangleToC(c._m.pool.symString(symId(body)))
                        result.add(LLType(kind=LLTypeKind.llStruct, name=baseName))
                        body.inc()
                    elif kind(body) == NifKind.DotToken:
                        body.inc()
                    _collectStructFieldTypes(c, body, result, bitfieldAccum, bitfieldUnit)
    return result


def _isPackedType(c: mut @ LLVMCode, typeSym: Cursor) -> bool:
    result = False
    if kind(typeSym) == NifKind.Symbol:
        with let:
            d = getDeclOrNil(c._m, symId(typeSym))
        if not isNil(d) and d.kind == LengSym.TypeY:
            with let:
                tdecl = asTypeDecl(d.pos)
            if substructureKind(tdecl.pragmas) == LengOther.PragmasU:
                with var:
                    p = tdecl.pragmas.copy()
                for _ in loopInto(p):
                    if pragmaKind(p) == LengPragma.PackedP:
                        result = True
                    skip(p)
    return result


def _operandStr(v: LLValue) -> string:
    """{.inline.}"""
    ## Typed operand text "<type> <value>" for one constant-initializer element
    result = string("")
    operand(v, result)
    return result


def _genGlobalConstr(c: mut @ LLVMCode, n: mut @ Cursor, declaredType: Cursor) -> LLValue:
    ## Generate a constant value as an LLValue. Scalar leaves use the proper
    ## value kinds (llvInt/llvGlobal/llvZero/…); only composed aggregates and
    ## escaped string literals fall back to llvRawText (pre-formatted text).
    @template
    def rawConst(t: LLType, v: string) -> LLValue:
        return LLValue(kind=LLValueKind.llvRawText, rawText=v, typ=t)
    match kind(n):
        case NifKind.IntLit:
            with let:
                typ = _genTypeLLVMReadOnly(c, declaredType)
            result = llIntText(str(intVal(n)), typ)
            n.inc()
        case NifKind.UIntLit:
            with let:
                typ = _genTypeLLVMReadOnly(c, declaredType)
            result = llIntText(str(uintVal(n)), typ)
            n.inc()
        case NifKind.FloatLit:
            with let:
                typ = _genTypeLLVMReadOnly(c, declaredType)
            result = llFloatText(_llFloatHexText(floatVal(n)), typ)
            n.inc()
        case NifKind.CharLit:
            with let:
                typ = _genTypeLLVMReadOnly(c, declaredType)
            result = llIntText(str(ord(charLit(n))), typ)
            n.inc()
        case NifKind.StrLit:
            with let:
                s = c._m.pool.strings[_litId(n)]
            n.inc()
            if s.len == 0:
                result = llZeroInit(newLLArrayType(0, c.prim.i8_))
            else:
                with var:
                    escaped = string("c\"")
                for ch in s:
                    with let:
                        o = ord(ch)
                    if o < 32 or o > 126 or ch == char('"') or ch == char('\\'):
                        escaped.add(char('\\'))
                        escaped.add(string("0123456789ABCDEF")[o >> 4])
                        escaped.add(string("0123456789ABCDEF")[o & 0xF])
                    else:
                        escaped.add(ch)
                escaped.add(char('"'))
                result = rawConst(newLLArrayType(s.len, c.prim.i8_), escaped)
        case NifKind.Symbol:
            with let:
                name = c._mangleSym(symId(n))
            c.requestedSyms.incl(symId(n))
            with let:
                typ = _genTypeLLVMReadOnly(c, declaredType)
            result = llGlobalRef(name, typ)
            n.inc()
        case NifKind.DotToken:
            with let:
                typ = _genTypeLLVMReadOnly(c, declaredType)
            result = llZeroInit(typ)
            n.inc()
        case _:
            match exprKind(n):
                case LengExpr.FalseC:
                    result = llIntText(string("0"), c.prim.i8_)
                    skip(n)
                case LengExpr.TrueC:
                    result = llIntText(string("1"), c.prim.i8_)
                    skip(n)
                case LengExpr.NilC:
                    result = llNull(c.prim.ptrT)
                    skip(n)
                case LengExpr.OconstrC:
                    with var:
                        resultTyp: LLType = None
                        resultVal: string = string("")
                    with into(n):
                        with let:
                            typeSym = n
                            fieldTypes = _getStructFieldTypes(c, n)
                            packed = _isPackedType(c, n)
                        with var:
                            fieldNifTypes: seq[Cursor] = seq[Cursor]([])
                        if kind(n) == NifKind.Symbol:
                            with let:
                                d = getDeclOrNil(c._m, symId(n))
                            if not isNil(d) and d.kind == LengSym.TypeY:
                                with let:
                                    decl = asTypeDecl(d.pos)
                                with var:
                                    body = decl.body.copy()
                                if typeKind(body) in Tset[LengType](LengType.ObjectT, LengType.UnionT):
                                    with into(body):
                                        if typeKind(decl.body) == LengType.ObjectT:
                                            if kind(body) == NifKind.Symbol:
                                                fieldNifTypes.add(body)
                                                body.inc()
                                            elif kind(body) == NifKind.DotToken:
                                                body.inc()
                                        while body.hasMore():
                                            if substructureKind(body) == LengOther.FldU:
                                                with var:
                                                    fdecl = takeFieldDecl(body)
                                                fieldNifTypes.add(fdecl.typ)
                                            elif typeKind(body) == LengType.UnionT:
                                                # Traverse into union to collect branch field types
                                                # so that branch-specific KvU pairs find the correct NIF type.
                                                with into(body):
                                                    while body.hasMore():
                                                        if substructureKind(body) == LengOther.FldU:
                                                            with var:
                                                                fdecl = takeFieldDecl(body)
                                                            fieldNifTypes.add(fdecl.typ)
                                                        elif typeKind(body) in Tset[LengType](LengType.ObjectT, LengType.UnionT):
                                                            # Nested object/union inside a union branch.
                                                            with into(body):
                                                                while body.hasMore():
                                                                    if substructureKind(body) == LengOther.FldU:
                                                                        with var:
                                                                            fdecl = takeFieldDecl(body)
                                                                        fieldNifTypes.add(fdecl.typ)
                                                                    else:
                                                                        skip(body)
                                                        elif isUnionBranch(body):
                                                            # Discriminated-union branch: collect its payload's
                                                            # fields, same as the untagged branch above.
                                                            with let:
                                                                b = asUnionBranch(body)
                                                            if typeKind(b.body) == LengType.ObjectT:
                                                                with var:
                                                                    inner = b.body.copy()
                                                                with into(inner):
                                                                    if kind(inner) == NifKind.DotToken: inner.inc()
                                                                    while inner.hasMore():
                                                                        if substructureKind(inner) == LengOther.FldU:
                                                                            with var:
                                                                                fdecl = takeFieldDecl(inner)
                                                                            fieldNifTypes.add(fdecl.typ)
                                                                        else:
                                                                            skip(inner)
                                                            skip(body)
                                                        else:
                                                            skip(body)
                                            else:
                                                skip(body)
                        skip(n)  # type
                        with var:
                            typeParts: seq[LLType] = seq[LLType]([])
                            valParts: seq[string] = seq[string]([])
                            usedNifTypes: seq[Cursor] = seq[Cursor]([])
                            fieldIdx = nint(0)
                        while n.hasMore():
                            if substructureKind(n) == LengOther.KvU:
                                with into(n):
                                    skip(n)
                                    with let:
                                        nifType = fieldNifTypes[fieldIdx] if fieldIdx < fieldNifTypes.len else declaredType
                                    usedNifTypes.add(nifType)
                                    with let:
                                        tc = _genGlobalConstr(c, n, nifType)
                                    typeParts.add(tc.typ)
                                    valParts.add(_operandStr(tc))
                                    while n.hasMore(): skip(n)
                                fieldIdx += 1
                            elif exprKind(n) == LengExpr.OconstrC:
                                with let:
                                    nifType = fieldNifTypes[fieldIdx] if fieldIdx < fieldNifTypes.len else declaredType
                                usedNifTypes.add(nifType)
                                with let:
                                    tc = _genGlobalConstr(c, n, nifType)
                                typeParts.add(tc.typ)
                                valParts.add(_operandStr(tc))
                                fieldIdx += 1
                            else:
                                with let:
                                    nifType = fieldNifTypes[fieldIdx] if fieldIdx < fieldNifTypes.len else declaredType
                                usedNifTypes.add(nifType)
                                with let:
                                    tc = _genGlobalConstr(c, n, nifType)
                                typeParts.add(tc.typ)
                                valParts.add(_operandStr(tc))
                                fieldIdx += 1
                    with var:
                        needsAnon = False
                    for i in range(min(typeParts.len, fieldTypes.len)):
                        if not typeEq(typeParts[i], fieldTypes[i]):
                            needsAnon = True
                            break
                    if typeParts.len != fieldTypes.len:
                        needsAnon = True
                    # For union object types, the branch-specific fields may not fill the
                    # full declared type. Add padding to match the declared size.
                    if needsAnon:
                        with let:
                            declaredSizeBits = _typeSizeBits(c, declaredType)
                        with var:
                            actualSizeBits = 0
                        for nt in usedNifTypes:
                            actualSizeBits += _typeSizeBits(c, nt)
                        with let:
                            paddingBits = declaredSizeBits - actualSizeBits
                        if paddingBits > 0:
                            with let:
                                paddingBytes = paddingBits // 8
                                padType = newLLArrayType(paddingBytes, c.prim.i8_)
                            typeParts.add(padType)
                            valParts.add(string("[") + str(paddingBytes) + string(" x i8] zeroinitializer"))
                    with let:
                        valStr = valParts.join(string(", "))
                    if needsAnon:
                        with var:
                            sfields: seq[LLStructField] = seq[LLStructField]([])
                        for ft in typeParts: sfields.add(LLStructField(typ=ft))
                        with let:
                            anonTyp = newLLStructType(sfields)
                        if packed:
                            resultTyp = anonTyp
                            resultVal = string("<{ ") + valStr + string(" }>")
                        else:
                            resultTyp = anonTyp
                            resultVal = string("{ ") + valStr + string(" }")
                    else:
                        with var:
                            dt = declaredType.copy()
                        resultTyp = _genTypeLLVM(c, dt)
                        if packed:
                            resultVal = string("<{ ") + valStr + string(" }>")
                        else:
                            resultVal = string("{ ") + valStr + string(" }")
                    result = rawConst(resultTyp, resultVal)
                case LengExpr.AconstrC:
                    with into(n):
                        with var:
                            elemTypeCursor = declaredType
                            elemType: LLType = c.prim.i8_
                        if typeKind(declaredType) == LengType.FlexarrayT:
                            with var:
                                et = declaredType.copy()
                            et.inc()
                            elemType = _genTypeLLVMReadOnly(c, et)
                            elemTypeCursor = et
                        elif typeKind(declaredType) == LengType.ArrayT:
                            with var:
                                at = declaredType.copy()
                            at.inc()
                            elemType = _genTypeLLVMReadOnly(c, at)
                            elemTypeCursor = at
                        else:
                            if typeKind(n) == LengType.FlexarrayT:
                                with var:
                                    et = n.copy()
                                et.inc()
                                elemType = _genTypeLLVMReadOnly(c, et)
                                elemTypeCursor = et
                            elif typeKind(n) == LengType.ArrayT:
                                with var:
                                    at = n.copy()
                                at.inc()
                                elemType = _genTypeLLVMReadOnly(c, at)
                                elemTypeCursor = at
                            elif kind(n) == NifKind.Symbol:
                                with let:
                                    d = getDeclOrNil(c._m, symId(n))
                                if not isNil(d) and d.kind == LengSym.TypeY:
                                    with let:
                                        tdecl = asTypeDecl(d.pos)
                                    if typeKind(tdecl.body) == LengType.ArrayT:
                                        with var:
                                            at = tdecl.body.copy()
                                        at.inc()
                                        elemType = _genTypeLLVMReadOnly(c, at)
                                        elemTypeCursor = at
                        skip(n)  # type
                        with var:
                            elems: seq[string] = seq[string]([])
                        while n.hasMore():
                            with let:
                                tc = _genGlobalConstr(c, n, elemTypeCursor)
                            elems.add(_operandStr(tc))
                        with let:
                            arrTyp = newLLArrayType(elems.len, elemType)
                        result = rawConst(arrTyp, string("[ ") + elems.join(string(", ")) + string(" ]"))
                case LengExpr.CastC | LengExpr.ConvC:
                    with into(n):
                        skip(n)
                        result = _genGlobalConstr(c, n, declaredType)
                        while n.hasMore(): skip(n)
                case LengExpr.SufC:
                    with into(n):
                        result = _genGlobalConstr(c, n, declaredType)
                        skip(n)
                        while n.hasMore(): skip(n)
                case LengExpr.AddrC | LengExpr.HaddrC:
                    with into(n):
                        if kind(n) == NifKind.Symbol:
                            with let:
                                name = c._mangleSym(symId(n))
                            c.requestedSyms.incl(symId(n))
                            result = llGlobalRef(name, c.prim.ptrT)
                            n.inc()
                        else:
                            _error(c._m, string("unsupported address constant; only plain symbols are currently handled: "), n)
                        while n.hasMore(): skip(n)
                case _:
                    _error(c._m, string("unhandled expression in global constant: "), n)
    return result
