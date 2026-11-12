# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/llvmdebug.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## All LLVM DWARF debug-info generation: metadata infrastructure
## (DICompileUnit, DIFile, DISubprogram, DILocalVariable, DIGlobalVariable,
## #dbg_declare) and DWARF debug type metadata (DIBasicType, DIDerivedType,
## DICompositeType) generated from NIF type cursors.
##
## Included from llvmcodegen.nim after llvmgentypes — ``LLVMCode``,
## ``DebugInfo``, ``LLVMCurrentProc`` types, emit helpers, ``nifSymBaseName``
## and the type helpers (``typeSizeBits``, ``typeAlignBits``) are in scope.

# ---- DWARF encoding constants ----------------------------------------

from __future__ import annotations
from nimic.ntypes import *

with const:
    _DW_ATE_address = 1
    _DW_ATE_boolean = 2
    _DW_ATE_float = 4
    _DW_ATE_signed = 5
    _DW_ATE_signed_char = 6
    _DW_ATE_unsigned = 7
    _DW_ATE_unsigned_char = 8

# ---- Debug metadata infrastructure -----------------------------------


def _addMetadata(c: mut @ LLVMCode, node: string) -> nint:
    ## Add a metadata node, return its ID.
    result = copy(c.debug.nextMetadataId)
    c.debug.metadata.add(node)
    c.debug.nextMetadataId += 1
    return result


def _initDebugInfo(c: mut @ LLVMCode, filename: string):
    ## Debug metadata is initialized lazily: the first call to
    ## ``getOrCreateDIFile`` creates the DICompileUnit using the first
    ## real source file as its file reference.
    discard


def _bitsFromLLVMType(typ: LLType, defaultBits: nint) -> nint:
    if typ is not None and typ.kind == LLTypeKind.llInt: return copy(typ.intBits)
    else: return defaultBits


def _genDIBasicType(c: mut @ LLVMCode, name: string, sizeBits: nint, encoding: nint) -> nint:
    ## Get or create a DIBasicType metadata node. Cached by name+size+encoding.
    with let:
        key = name + string(":") + str(sizeBits) + string(":") + str(encoding)
    result = c.debug.diBasicTypeCache.getOrDefault(key)
    if result != 0: return result
    result = _addMetadata(c, string("!DIBasicType(name: \"") + name + string("\", size: ") + str(sizeBits) + string(", encoding: ") + str(encoding) + string(")"))
    c.debug.diBasicTypeCache[key] = result
    return result


def _getOrCreateDIFileByName(c: mut @ LLVMCode, path: string) -> nint:
    ## Get or create a DIFile metadata node for a plain source path. Keyed on the
    ## path itself, since the declaration sites carried in a forged filename have
    ## no `FileId` of their own.
    with let:
        cached = c.debug.fileIdsByName.getOrDefault(path, -1)
    if cached >= 0:
        return cached
    with let:
        (dir, name, ext) = splitFile(path)
        fullName = name + ext
        directory = _absoluteDirOrQuit(dir)
    result = _addMetadata(c, string("!DIFile(filename: \"") + fullName + string("\", directory: \"") + directory + string("\")"))
    c.debug.fileIdsByName[path] = result
    # First real source file → create the compile unit using this file
    if c.debug.cuId == 0:
        c.debug.cuId = _addMetadata(c, string("distinct !DICompileUnit(language: DW_LANG_C99, file: !") + str(result) + string(", producer: \"lengc\", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug)"))
    return result


def _getOrCreateDIFile(c: mut @ LLVMCode, fid: FileId) -> nint:
    ## Get or create a DIFile metadata node for the given FileId.
    with let:
        key = nint(fid)
    # `getOrDefault` rather than `[]`: the latter is `.raises` (KeyError) under
    # Nimony. Metadata ids are positive, so -1 is an unambiguous "not cached".
    with let:
        cached = c.debug.fileIds.getOrDefault(key, -1)
    if cached >= 0:
        return cached
    # A forged filename carries template-expansion provenance (`__crucial\0…`);
    # the DIFile must name the real source, and `dbgLocationId` reads the chain
    # separately to build the inlined frames.
    result = _getOrCreateDIFileByName(c, realFile(c._m.pool.filenames[fid]))
    c.debug.fileIds[key] = result
    return result


def _getOrCreateInlineSP(c: mut @ LLVMCode, origin: CrucialOrigin, fallbackFileId: nint, fallbackLine: nint) -> nint:
    pass


def _dbgLocationId(c: mut @ LLVMCode, info: NifLineInfo) -> nint:
    ## Build a DILocation metadata node for the given source location and return
    ## its id, or 0 if the location is invalid.
    ##
    ## When the walk is inside a template expansion - `currentProc.frameStack` is
    ## non-empty, pushed by `pushExpansionFrames` on entering a node whose head
    ## carries a forged filename (see `comesfrom`) - the stack is turned into
    ## DWARF inlined frames: one synthetic DISubprogram per expanded routine,
    ## the location scoped to the innermost and chained outwards through
    ## `inlinedAt` until it reaches the enclosing proc. That is what makes a
    ## debugger show a template as an inlined frame instead of jumping into its
    ## definition file (#1987).
    if not info.isValid(): return 0
    with let:
        rawInfo = info
    if not isValid(rawInfo.file): return 0
    with let:
        fileId = _getOrCreateDIFile(c, rawInfo.file)

    # The call site: the location this expansion was written at, in the enclosing
    # proc. Everything the chain builds hangs off it.
    def scopeInProc(c: mut @ LLVMCode, fileId: nint) -> nint:
        if fileId == c._currentProc.subprogramFileId:
            return copy(c._currentProc.subprogramId)
        else:
            return _addMetadata(c, string("!DILexicalBlockFile(scope: !") + str(c._currentProc.subprogramId) + string(", file: !") + str(fileId) + string(", discriminator: 0)"))

    if c._currentProc.frameStack.len == 0:
        result = _addMetadata(c, string("!DILocation(line: ") + str(rawInfo.line) + string(", column: ") + str(rawInfo.col + 1) + string(", scope: !") + str(scopeInProc(c, fileId)) + string(")"))
        return result

    # Outermost first, so each iteration nests one level deeper. The call-site
    # location is the same for every level: expansions carry no separate location
    # for where each nested template was invoked, so the whole chain attributes
    # back to the statement the outermost expansion replaced.
    with var:
        inlinedAt = _addMetadata(c, string("!DILocation(line: ") + str(rawInfo.line) + string(", column: ") + str(rawInfo.col + 1) + string(", scope: !") + str(scopeInProc(c, fileId)) + string(")"))
        scopeId = 0
    # `getOrCreateInlineSP` takes `c` as `var`, so the stack is moved out for the
    # loop rather than borrowed; nothing it calls reads the stack.
    with var:
        frames = move(c._currentProc.frameStack)
    for origin in frames:
        with let:
            spId = _getOrCreateInlineSP(c, origin, fileId, rawInfo.line)
        if spId == 0: continue
        if scopeId != 0:
            # The previous level's location becomes this one's call site.
            inlinedAt = _addMetadata(c, string("!DILocation(line: ") + str(rawInfo.line) + string(", column: ") + str(rawInfo.col + 1) + string(", scope: !") + str(scopeId) + string(", inlinedAt: !") + str(inlinedAt) + string(")"))
        scopeId = spId
    c._currentProc.frameStack = move(frames)
    if scopeId == 0:
        result = inlinedAt
    else:
        result = _addMetadata(c, string("!DILocation(line: ") + str(rawInfo.line) + string(", column: ") + str(rawInfo.col + 1) + string(", scope: !") + str(scopeId) + string(", inlinedAt: !") + str(inlinedAt) + string(")"))
    return result


def _dbgLocation(c: mut @ LLVMCode, info: NifLineInfo) -> string:
    ## Return a `, !dbg !N` suffix for the given source location, or "" if invalid.
    with let:
        locId = _dbgLocationId(c, info)
    result = string("") if locId == 0 else string(", !dbg !") + str(locId)
    return result


def _getOrCreateInlineSP(c: mut @ LLVMCode, origin: CrucialOrigin, fallbackFileId: nint, fallbackLine: nint) -> nint:
    ## Get or create the synthetic DISubprogram for an expanded routine, shared by
    ## every call site of it. Returns 0 when none can be built.
    ##
    ## The frame is placed at the routine's *declaration* site, which the forged
    ## filename carries for exactly this reason: a template declaration does not
    ## survive into Leng, and the expanded code's own line info points at whatever
    ## file the body came from. The fallbacks cover a chain written before the
    ## declaration site was encoded.
    with let:
        cached = c.debug.inlineSpCache.getOrDefault(origin.sym, -1)
    if cached >= 0: return cached
    with var:
        fileId = fallbackFileId
        line = fallbackLine
    if origin.declFile.len > 0:
        fileId = _getOrCreateDIFileByName(c, origin.declFile)
        line = nint(origin.declLine)
    if fileId == 0: return 0
    # A subprogram definition needs a type and a unit; the signature is opaque
    # (`!{null}`: unknown return, no formals) because a template has neither a
    # calling convention nor materialized parameters.
    if c.debug.nullSigId == 0:
        c.debug.nullSigId = _addMetadata(c, string("!DISubroutineType(types: !{null})"))
    with var:
        isGlobal = nbool(False)
        shortName = extractBasename(origin.sym, isGlobal)
    if shortName.len == 0: shortName = origin.sym
    result = _addMetadata(c, string("distinct !DISubprogram(name: \"") + shortName + string("\", scope: !") + str(fileId) + string(", file: !") + str(fileId) + string(", line: ") + str(line) + string(", type: !") + str(c.debug.nullSigId) + string(", scopeLine: ") + str(line) + string(", spFlags: DISPFlagDefinition, unit: !") + str(c.debug.cuId) + string(")"))
    c.debug.inlineSpCache[origin.sym] = result
    return result


def _createSubprogram(c: mut @ LLVMCode, name: string, info: NifLineInfo) -> nint:
    ## Create a DISubprogram metadata node for a function.
    with var:
        fileId = 0
        line = 0
    if info.isValid():
        with let:
            rawInfo = info
        if isValid(rawInfo.file):
            fileId = _getOrCreateDIFile(c, rawInfo.file)
            line = rawInfo.line
    c._currentProc.spName = name
    c._currentProc.spLine = line
    c._currentProc.spScopeLine = line
    c._currentProc.subprogramFileId = fileId
    # placeholder (content replaced later by finalizeSubprogram)
    result = _addMetadata(c, string(""))
    return result


def _finalizeSubprogram(c: mut @ LLVMCode, spId: nint, paramDITypes: seq[nint], retainedNodes: seq[nint]):
    if spId == 0: return
    with let:
        fid = copy(c._currentProc.subprogramFileId)
    with var:
        typesStr = string("")
    for i, pt in pairs(paramDITypes):
        if i > 0: typesStr.add(string(", "))
        typesStr.add(string("!") + str(pt))
    with let:
        stId = _addMetadata(c, string("!DISubroutineType(types: !{") + typesStr + string("})"))
    with var:
        rnList = string("")
    for i, rn in pairs(retainedNodes):
        if i > 0: rnList.add(string(", "))
        rnList.add(string("!") + str(rn))
    with let:
        rnId = _addMetadata(c, string("!{") + rnList + string("}"))
        finalSp = string("distinct !DISubprogram(name: \"") + c._currentProc.spName + string("\", scope: !") + str(fid) + string(", file: !") + str(fid) + string(", line: ") + str(c._currentProc.spLine) + string(", type: !") + str(stId) + string(", scopeLine: ") + str(c._currentProc.spScopeLine) + string(", spFlags: DISPFlagDefinition, unit: !") + str(c.debug.cuId) + string(", retainedNodes: !") + str(rnId) + string(")")
    c.debug.metadata[spId] = finalSp


def _emitDbgDeclare(c: mut @ LLVMCode, localName: string, symId: SymId, wasName: string, info: NifLineInfo, diType: nint = 0, argNo: nint = 0, llvmTyp: LLType = None):
    ## Emit a #dbg_declare for a local variable (as a raw intrinsic line).
    if not info.isValid(): return
    with let:
        rawInfo = info
    if not isValid(rawInfo.file): return
    with var:
        useType = diType
    if useType == 0:
        with let:
            bits = _bitsFromLLVMType(llvmTyp, c._bits)
        useType = _genDIBasicType(c, string("int ") + str(bits), bits, _DW_ATE_signed)
    with let:
        debugName = wasName if wasName.len > 0 else c.nifSymBaseName(symId)
        fileId = _getOrCreateDIFile(c, rawInfo.file)
    # A variable declared inside a template expansion belongs to that template's
    # synthetic subprogram, and its declare location must carry the matching
    # `inlinedAt` chain: LLVM's verifier rejects a #dbg_declare whose variable
    # scope and location scope disagree. `template t = (var x = ...)` is ordinary
    # code, so this is required, not polish.
    #
    # Both come from the same place - the active frame stack - so they cannot
    # drift: the innermost origin names the SP that `dbgLocationId` will scope to.
    with let:
        inFrame = c._currentProc.frameStack.len > 0
    with var:
        varScopeId = copy(c._currentProc.subprogramId)
        frames = move(c._currentProc.frameStack)  # as in `dbgLocationId`
    for origin in frames:
        with let:
            spId = _getOrCreateInlineSP(c, origin, fileId, rawInfo.line)
        if spId != 0: varScopeId = spId
    c._currentProc.frameStack = move(frames)
    with var:
        varMetadata = string("!DILocalVariable(name: \"") + debugName + string("\"")
    if argNo > 0:
        varMetadata.add(string(", arg: ") + str(argNo))
    varMetadata.add(string(", scope: !") + str(varScopeId) + string(", file: !") + str(fileId) + string(", line: ") + str(rawInfo.line) + string(", type: !") + str(useType) + string(")"))
    with let:
        varId = _addMetadata(c, varMetadata)
    if not inFrame:
        # `retainedNodes` lists the variables scoped to *this* subprogram; one
        # scoped to a template's synthetic SP does not belong in the proc's list.
        c._currentProc.retainedNodes.add(varId)
    with let:
        locId = _dbgLocationId(c, info)
    if locId == 0: return
    c.emitRaw(string("#dbg_declare(ptr ") + localName + string(", !") + str(varId) + string(", !DIExpression(), !") + str(locId) + string(")"))


def _emitGlobalDbgVar(c: mut @ LLVMCode, name: string, varInfo: NifLineInfo, symId: SymId, diType: nint) -> string:
    if c.debug.cuId == 0: return string("")
    with var:
        fileId = 0
        line = 0
    if varInfo.isValid() and isValid(varInfo.file):
        fileId = _getOrCreateDIFile(c, varInfo.file)
        line = nint(varInfo.line)
    if fileId == 0:
        fileId = copy(c._currentProc.subprogramFileId)
    if fileId == 0: return string("")
    if diType == 0: return string("")
    with let:
        displayName = c.nifSymBaseName(symId)
        gvId = _addMetadata(c, string("distinct !DIGlobalVariable(name: \"") + displayName + string("\", scope: !") + str(c.debug.cuId) + string(", file: !") + str(fileId) + string(", line: ") + str(line) + string(", type: !") + str(diType) + string(", isLocal: false, isDefinition: true)"))
        gveId = _addMetadata(c, string("!DIGlobalVariableExpression(var: !") + str(gvId) + string(", expr: !DIExpression())"))
    c.debug.globalExprs.add(gveId)
    result = string(", !dbg !") + str(gveId)
    return result

# ---- DWARF debug type generation -------------------------------------

# ---- Forward decls ---------------------------------------------------


def genDIType(c: mut @ LLVMCode, n: Cursor) -> nint:
    pass


def _genDITypeForSymbol(c: mut @ LLVMCode, symId: SymId) -> nint:
    pass


def _genDICompositeType(c: mut @ LLVMCode, n: mut @ Cursor) -> nint:
    pass

# ---- Helper: read-only cursor ---------------------------------------


def _genDITypeReadOnly(c: mut @ LLVMCode, n: Cursor) -> nint:
    ## Like genDIType but does not advance the cursor.
    with var:
        nn = n
    result = genDIType(c, nn)
    return result

# ---- Main dispatcher ------------------------------------------------


def _genDITypeImpl(c: mut @ LLVMCode, n: mut @ Cursor) -> nint:
    match typeKind(n):
        case LengType.VoidT:
            result = 0
            skip(n)
        case LengType.IT:
            with into(n):
                with var:
                    bits = copy(c._bits)
                if kind(n) == NifKind.IntLit:
                    with let:
                        b = intVal(n)
                    if b != -1: bits = nint(b)
                    n.inc()
                result = _genDIBasicType(c, string("int ") + str(bits), bits, _DW_ATE_signed)
                while n.hasMore(): skip(n)
        case LengType.UT:
            with into(n):
                with var:
                    bits = copy(c._bits)
                if kind(n) == NifKind.IntLit:
                    with let:
                        b = intVal(n)
                    if b != -1: bits = nint(b)
                    n.inc()
                result = _genDIBasicType(c, string("uint ") + str(bits), bits, _DW_ATE_unsigned)
                while n.hasMore(): skip(n)
        case LengType.CT:
            with into(n):
                with var:
                    bits = 8
                if kind(n) == NifKind.IntLit:
                    with let:
                        b = intVal(n)
                    if b != -1: bits = nint(b)
                    n.inc()
                result = _genDIBasicType(c, string("char"), bits, _DW_ATE_signed_char)
                while n.hasMore(): skip(n)
        case LengType.FT:
            with into(n):
                with var:
                    bits = 64
                if kind(n) == NifKind.IntLit:
                    with let:
                        b = intVal(n)
                    if b != -1: bits = nint(b)
                    n.inc()
                with let:
                    name = string("float") if bits == 32 else string("fp128") if bits == 128 else string("double")
                result = _genDIBasicType(c, name, bits, _DW_ATE_float)
                while n.hasMore(): skip(n)
        case LengType.BoolT:
            with into(n):
                while n.hasMore(): skip(n)
            result = _genDIBasicType(c, string("bool"), 8, _DW_ATE_boolean)
        case LengType.PtrT | LengType.AptrT:
            with let:
                pointee = _firstSon(n)
                pt = _genDITypeReadOnly(c, pointee)
                baseRef = string("!") + str(pt) if pt > 1 else string("null")
            result = _addMetadata(c, string("!DIDerivedType(tag: DW_TAG_pointer_type") + string(", baseType: ") + baseRef + string(", size: ") + str(c._bits) + string(", align: ") + str(c._bits) + string(", dwarfAddressSpace: 0)"))
            skip(n)
        case LengType.ProctypeT:
            # Opaque pointer — DWARF just needs the pointer type, not the signature
            result = _addMetadata(c, string("!DIDerivedType(tag: DW_TAG_pointer_type") + string(", baseType: null") + string(", size: ") + str(c._bits) + string(", align: ") + str(c._bits) + string(", dwarfAddressSpace: 0)"))
            skip(n)
        case LengType.FlexarrayT:
            # [0 x T] — treat as array with unknown bound
            with into(n):
                with let:
                    et = genDIType(c, n)
                    subrange = _addMetadata(c, string("!DISubrange(count: -1)"))
                    totalSize = 0  # flexarray has unknown size for DWARF
                result = _addMetadata(c, string("!DICompositeType(tag: DW_TAG_array_type") + string(", elements: !{!") + str(subrange) + string("}") + string(", baseType: !") + str(et) + string(", size: ") + str(totalSize) + string(")"))
                while n.hasMore(): skip(n)
        case LengType.ArrayT:
            with let:
                totalSize = _typeSizeBits(c, n)  # capture before entering
            with into(n):
                with let:
                    et = genDIType(c, n)
                with var:
                    sz = 0
                if kind(n) == NifKind.IntLit:
                    sz = nint(intVal(n))
                    skip(n)
                elif kind(n) == NifKind.UIntLit:
                    sz = nint(uintVal(n))
                    skip(n)
                with let:
                    subrange = _addMetadata(c, string("!DISubrange(count: ") + str(sz) + string(")"))
                result = _addMetadata(c, string("!DICompositeType(tag: DW_TAG_array_type") + string(", elements: !{!") + str(subrange) + string("}") + string(", baseType: !") + str(et) + string(", size: ") + str(totalSize) + string(")"))
                while n.hasMore(): skip(n)
        case LengType.EnumT:
            with let:
                enumSize = _typeSizeBits(c, n)  # capture BEFORE n.into
            with into(n):
                with let:
                    base = genDIType(c, n)  # underlying integer type
                with var:
                    enumerators: seq[nint] = seq[nint]([])
                while n.hasMore():
                    if substructureKind(n) == LengOther.EfldU:
                        with into(n):
                            with let:
                                enumName = c.nifSymBaseName(symId(n))
                            n.inc()
                            with var:
                                val = 0
                            if kind(n) == NifKind.IntLit:
                                val = nint(intVal(n))
                                n.inc()
                            elif kind(n) == NifKind.UIntLit:
                                val = nint(uintVal(n))
                                n.inc()
                            with let:
                                en = _addMetadata(c, string("!DIEnumerator(name: \"") + enumName + string("\", value: ") + str(val) + string(")"))
                            enumerators.add(en)
                            while n.hasMore(): skip(n)
                    else:
                        skip(n)
                with var:
                    enumElems = string("")
                for i, e in pairs(enumerators):
                    if i > 0: enumElems.add(string(", "))
                    enumElems.add(string("!") + str(e))
                result = _addMetadata(c, string("!DICompositeType(tag: DW_TAG_enumeration_type") + string(", baseType: !") + str(base) + string(", elements: !{") + enumElems + string("}") + string(", size: ") + str(enumSize) + string(")"))
                while n.hasMore(): skip(n)
        case LengType.ObjectT | LengType.UnionT:
            result = _genDICompositeType(c, n)
            # genDICompositeType always consumes n (skip n at end, or skip n on cache hit)
        case LengType.NoType:
            if kind(n) == NifKind.Symbol:
                result = _genDITypeForSymbol(c, symId(n))
                n.inc()
            elif kind(n) == NifKind.DotToken:
                result = 0
                n.inc()
            else:
                result = 0
                skip(n)
        case LengType.VarargsT:
            result = 0
            skip(n)
        case LengType.ParamsT:
            result = 0
            skip(n)
        case _:
            result = 0
            skip(n)
    return result

# ---- Public dispatcher ----------------------------------------------


def genDIType(c: mut @ LLVMCode, n: Cursor) -> nint:
    with var:
        nn = n.copy()
    result = _genDITypeImpl(c, nn)
    return result

# ---- Pointer type ----------------------------------------------------


def _genDIPointerType(c: mut @ LLVMCode, pointeeType: Cursor) -> nint:
    with let:
        pt = _genDITypeReadOnly(c, pointeeType)
        ptStr = string("!$") + str(pt) if pt != 0 else string("null")
    result = _addMetadata(c, string("!DIDerivedType(tag: DW_TAG_pointer_type") + string(", baseType: ") + ptStr + string(", size: ") + str(c._bits) + string(", align: ") + str(c._bits) + string(", dwarfAddressSpace: 0)"))
    return result

# ---- Type for a named symbol -----------------------------------------


def _genDITypeForSymbol(c: mut @ LLVMCode, symId: SymId) -> nint:
    result = c.debug.diTypeCache.getOrDefault(symId)
    if result == -1:
        # Cycle: emit placeholder and cache it
        with let:
            d = getDeclOrNil(c._m, symId)
            typeName = c.nifSymBaseName(nifcoreparse.symId(asTypeDecl(d.pos).name)) if not isNil(d) and d.kind == LengSym.TypeY else c.nifSymBaseName(symId)
        result = _addMetadata(c, string("!DICompositeType(tag: DW_TAG_structure_type") + string(", name: \"") + typeName + string("\", elements: !{}, size: 0)"))
        c.debug.diTypeCache[symId] = result
        return result
    if result != 0: return result

    with let:
        d = getDeclOrNil(c._m, symId)
    if not isNil(d) and d.kind == LengSym.TypeY:
        with let:
            decl = asTypeDecl(d.pos)
            typeName = c.nifSymBaseName(nifcoreparse.symId(decl.name))
        # Set sentinel before recursing to break cycles
        c.debug.diTypeCache[symId] = -1
        with let:
            underlying = _genDITypeReadOnly(c, decl.body)
        if underlying > 1:
            if typeKind(decl.body) in Tset[LengType](LengType.ObjectT, LengType.UnionT):
                # DICompositeType already carries the name; no typedef wrapper needed.
                # genDICompositeType may have returned a placeholder — it will update
                # the metadata in-place when it builds the full type.
                result = underlying
            else:
                result = _addMetadata(c, string("!DIDerivedType(tag: DW_TAG_typedef") + string(", name: \"") + typeName + string("\"") + string(", baseType: !") + str(underlying) + string(")"))
        else:
            result = 0
        c.debug.diTypeCache[symId] = result
    elif not isNil(d):
        result = 0
    else:
        result = 0
    return result

# ---- Composite type (struct / union) ----------------------------------


def _genDIUnionType(c: mut @ LLVMCode, n: mut @ Cursor, selectorType: Cursor = default(Cursor)) -> nint:
    pass


def _genDIAnonObject(c: mut @ LLVMCode, n: mut @ Cursor, name=string("")) -> nint:
    pass


def _enumFieldName(c: mut @ LLVMCode, enumType: Cursor, value: int64) -> string:
    ## Map a discriminant value back to its enum field name. `lengcgen` folds enum
    ## symbols to plain integers when it copies a branch's `(ranges ...)`, so the
    ## name has to be recovered from the selector's own `(enum ...)` declaration,
    ## which sits in the same module.
    result = string("")
    if enumType.cursorIsNil(): return result
    with var:
        t = enumType.copy()
    if kind(t) == NifKind.Symbol:
        with let:
            d = getDeclOrNil(c._m, symId(t))
        if isNil(d) or d.kind != LengSym.TypeY: return result
        t = asTypeDecl(d.pos).body
    if typeKind(t) != LengType.EnumT: return result
    with into(t):
        skip(t)  # underlying integer type
        while t.hasMore():
            if substructureKind(t) == LengOther.EfldU and result.len == 0:
                with var:
                    f = t.copy()
                with into(f):
                    if kind(f) == NifKind.SymbolDef:
                        with let:
                            nameSym = symId(f)
                        f.inc()
                        with var:
                            v = int64(0)
                        if kind(f) == NifKind.IntLit: v = intVal(f)
                        elif kind(f) == NifKind.UIntLit: v = int64(uintVal(f))
                        if v == value:
                            result = c.nifSymBaseName(nameSym)
                    while f.hasMore(): skip(f)
            skip(t)
    return result


def _branchName(c: mut @ LLVMCode, b: UnionBranch, selectorType: Cursor) -> string:
    ## Name a union branch after the first discriminant value that selects it.
    ## An `else` branch has no `ranges` to name it after, but leaving it unnamed
    ## reproduces the very problem this is fixing, so it gets the literal name.
    result = string("")
    if b.ranges.cursorIsNil() or substructureKind(b.ranges) != LengOther.RangesU:
        return string("else")
    with var:
        r = b.ranges.copy()
    with into(r):
        if r.hasMore():
            with var:
                v = r
            if substructureKind(v) == LengOther.RangeU:  # `(range lo hi)`: name after `lo`
                v = childCursor(v)
            if kind(v) == NifKind.IntLit:
                result = _enumFieldName(c, selectorType, intVal(v))
            elif kind(v) == NifKind.UIntLit:
                result = _enumFieldName(c, selectorType, int64(uintVal(v)))
        while r.hasMore(): skip(r)
    return result


def _diElemsList(members: seq[nint]) -> string:
    result = string("")
    for i, m in pairs(members):
        if i > 0: result.add(string(", "))
        result.add(string("!") + str(m))
    return result


def _addFieldMember(c: mut @ LLVMCode, fd: FieldDecl, members: mut @ seq[nint], fieldOffset: mut @ nint):
    with let:
        fieldName = c.nifSymBaseName(symId(fd.name))
        fieldType = _genDITypeReadOnly(c, fd.typ)
    if fieldType == 0: return
    with let:
        fieldSize = _typeSizeBits(c, fd.typ)
        fieldAlign = copy(c._bits) if typeKind(fd.typ) in Tset[LengType](LengType.PtrT, LengType.AptrT, LengType.ProctypeT) else min(fieldSize, c._bits)
    if fieldAlign > 0:
        fieldOffset <<= ((fieldOffset + fieldAlign - 1) // fieldAlign) * fieldAlign
    with let:
        fInfo = _info(fd.name)
    with var:
        fFileId = 0
        fLine = 0
    if fInfo.isValid() and isValid(fInfo.file):
        fFileId = _getOrCreateDIFile(c, fInfo.file)
        fLine = nint(fInfo.line)
    with var:
        mStr = string("!DIDerivedType(tag: DW_TAG_member") + string(", name: \"") + fieldName + string("\"")
    if fFileId != 0:
        mStr.add(string(", file: !") + str(fFileId) + string(", line: ") + str(fLine))
    mStr.add(string(", baseType: !") + str(fieldType) + string(", size: ") + str(fieldSize) + string(", align: ") + str(fieldAlign))
    if fieldOffset > 0:
        mStr.add(string(", offset: ") + str(fieldOffset))
    mStr.add(string(")"))
    members.add(_addMetadata(c, mStr))
    fieldOffset += fieldSize


def _addUnionMember(c: mut @ LLVMCode, n: mut @ Cursor, members: mut @ seq[nint], fieldOffset: mut @ nint, selectorType: Cursor):
    ## Add the embedded union ``n`` (UnionT) as a single member whose baseType
    ## is an anonymous DICompositeType union. Consumes ``n``.
    ## ``selectorType`` is the discriminator field's type for a case object, used
    ## to name each branch after the enum value that selects it.
    with let:
        uSize = _typeSizeBits(c, n)
        uAlign = _typeAlignBits(c, n)
        udi = _genDIUnionType(c, n, selectorType)
    if uAlign > 0:
        fieldOffset <<= ((fieldOffset + uAlign - 1) // uAlign) * uAlign
    if udi != 0:
        with var:
            mStr = string("!DIDerivedType(tag: DW_TAG_member") + string(", baseType: !") + str(udi) + string(", size: ") + str(uSize) + string(", align: ") + str(uAlign)
        if fieldOffset > 0:
            mStr.add(string(", offset: ") + str(fieldOffset))
        mStr.add(string(")"))
        members.add(_addMetadata(c, mStr))
    fieldOffset += uSize


def _genDIAnonObject(c: mut @ LLVMCode, n: mut @ Cursor, name=string("")) -> nint:
    ## Generate a DICompositeType struct for an inline object body. ``name`` is
    ## set for a case object's branch payload so a debugger can print which
    ## branch it is looking at; otherwise the struct stays anonymous.
    with var:
        members: seq[nint] = seq[nint]([])
        fieldOffset = nint(0)
    with let:
        oSize = _typeSizeBits(c, n)
        oAlign = _typeAlignBits(c, n)
        kind = typeKind(n)
    with var:
        selectorType = default(Cursor)
    with into(n):
        if kind == LengType.ObjectT:
            if nifcoreparse.kind(n) == NifKind.DotToken: n.inc()
            elif nifcoreparse.kind(n) == NifKind.Symbol: n.inc()
        while n.hasMore():
            if substructureKind(n) == LengOther.FldU:
                with var:
                    fd = takeFieldDecl(n)
                selectorType = fd.typ  # a union sees the field just before it
                _addFieldMember(c, fd, members, fieldOffset)
            elif typeKind(n) == LengType.UnionT:
                _addUnionMember(c, n, members, fieldOffset, selectorType)
            else:
                skip(n)
    with var:
        s = string("!DICompositeType(tag: DW_TAG_structure_type")
    if name.len > 0:
        s.add(string(", name: \"") + name + string("\""))
    s.add(string(", elements: !{") + _diElemsList(members) + string("}") + string(", size: ") + str(oSize) + string(", align: ") + str(oAlign) + string(")"))
    result = _addMetadata(c, s)
    return result


def _genDIUnionType(c: mut @ LLVMCode, n: mut @ Cursor, selectorType: Cursor = default(Cursor)) -> nint:
    ## Generate an anonymous DICompositeType union for an inline union body.
    ## Each branch (nested object / field) becomes an overlapping member.
    ##
    ## For a case object the branches arrive tagged (`(of RANGES BODY)`), and each
    ## member is named after the enum value that selects it. Without those names
    ## a debugger prints the branches as unnamed members, which is what
    ## nim-lang/nimony#2068 reports.
    with var:
        members: seq[nint] = seq[nint]([])
    with let:
        uSize = _typeSizeBits(c, n)
        uAlign = _typeAlignBits(c, n)
    with into(n):
        while n.hasMore():
            if substructureKind(n) == LengOther.FldU:
                with var:
                    fd = takeFieldDecl(n)
                    off = nint(0)
                _addFieldMember(c, fd, members, off)
            elif typeKind(n) == LengType.ObjectT:
                with let:
                    bdi = _genDIAnonObject(c, n)
                if bdi != 0:
                    members.add(_addMetadata(c, string("!DIDerivedType(tag: DW_TAG_member") + string(", baseType: !") + str(bdi) + string(")")))
            elif typeKind(n) == LengType.UnionT:
                with let:
                    ndi = _genDIUnionType(c, n)
                if ndi != 0:
                    members.add(_addMetadata(c, string("!DIDerivedType(tag: DW_TAG_member") + string(", baseType: !") + str(ndi) + string(")")))
            elif isUnionBranch(n):
                with let:
                    b = asUnionBranch(n)
                if typeKind(b.body) == LengType.ObjectT:
                    with let:
                        bname = _branchName(c, b, selectorType)
                    with var:
                        body = b.body.copy()
                    with let:
                        bdi = _genDIAnonObject(c, body, bname)
                    if bdi != 0:
                        with var:
                            mStr = string("!DIDerivedType(tag: DW_TAG_member")
                        if bname.len > 0:
                            mStr.add(string(", name: \"") + bname + string("\""))
                        mStr.add(string(", baseType: !") + str(bdi) + string(", size: ") + str(_typeSizeBits(c, b.body)) + string(", align: ") + str(_typeAlignBits(c, b.body)) + string(")"))
                        members.add(_addMetadata(c, mStr))
                skip(n)
            else:
                skip(n)
    result = _addMetadata(c, string("!DICompositeType(tag: DW_TAG_union_type") + string(", elements: !{") + _diElemsList(members) + string("}") + string(", size: ") + str(uSize) + string(", align: ") + str(uAlign) + string(")"))
    return result


def _genDICompositeType(c: mut @ LLVMCode, n: mut @ Cursor) -> nint:
    ## Generate DICompositeType for ObjectT or UnionT.
    ## Walks ``decl.body`` (not the inline cursor) — matches
    ## ``addObjectFieldsLLVM`` / ``genObjectBodyLLVM`` pattern exactly.
    result = 0
    with let:
        td = c._m.tracebackTypeC(n)
        decl = asTypeDecl(td)
        symId = nifcoreparse.symId(decl.name)

    # Already fully built? Return immediately.
    if symId in c.debug.compositeTypeDone:
        result = c.debug.diTypeCache.getOrDefault(symId)
        skip(n)
        return result

    # Save the old cache value (could be 0, -1 sentinel, or a placeholder
    # metadata ID from a previous genDITypeForSymbol / genDICompositeType call).
    with let:
        oldCached = c.debug.diTypeCache.getOrDefault(symId)

    # Set sentinel to break cycles during field processing.
    # Even if oldCached == -1 (genDITypeForSymbol is processing this type),
    # we still build the full type here. The -1 sentinel already handles
    # self-references: genDITypeForSymbol will create a placeholder when it
    # sees -1, and we update that placeholder in-place at the end.
    c.debug.diTypeCache[symId] = -1

    with let:
        tag = string("DW_TAG_union_type") if typeKind(decl.body) == LengType.UnionT else string("DW_TAG_structure_type")
        typeName = c.nifSymBaseName(symId)
        totalSize = _typeSizeBits(c, decl.body)
        totalAlign = _typeAlignBits(c, decl.body)

    # Source location for the type declaration
    with let:
        declInfo = _info(decl.name)
    with var:
        declFileId = 0
        declLine = 0
    if declInfo.isValid() and isValid(declInfo.file):
        declFileId = _getOrCreateDIFile(c, declInfo.file)
        declLine = nint(declInfo.line)

    # Walk the canonical body from the declaration (pattern from addObjectFieldsLLVM)
    with var:
        members: seq[nint] = seq[nint]([])
        fieldOffset = nint(0)
        body = decl.body.copy()
    with let:
        k = typeKind(body)
    with into(body):
        if k == LengType.ObjectT:
            if kind(body) == NifKind.DotToken:
                body.inc()
            elif kind(body) == NifKind.Symbol:
                with let:
                    baseDi = _genDITypeForSymbol(c, nifcoreparse.symId(body))
                if baseDi != 0:
                    members.add(_addMetadata(c, string("!DIDerivedType(tag: DW_TAG_inheritance") + string(", baseType: !") + str(baseDi) + string(", size: ") + str(_typeSizeBits(c, body)) + string(", offset: 0, flags: 0)")))
                body.inc()

        with var:
            selectorType = default(Cursor)
        while body.hasMore():
            if substructureKind(body) == LengOther.FldU:
                with var:
                    fd = takeFieldDecl(body)
                # A case object's discriminator is the field directly before the union
                # (an invariant of `lengcgen.trObjFields`), so remembering the last
                # field is enough to name the branches.
                selectorType = fd.typ
                _addFieldMember(c, fd, members, fieldOffset)
            elif typeKind(body) == LengType.UnionT:
                _addUnionMember(c, body, members, fieldOffset, selectorType)
            elif typeKind(body) == LengType.ObjectT:
                skip(body)
            else:
                skip(body)

    with var:
        membersStr = string("")
    for i, m in pairs(members):
        if i > 0: membersStr.add(string(", "))
        membersStr.add(string("!") + str(m))

    with var:
        realTypeStr = string("!DICompositeType(tag: ") + tag + string(", name: \"") + typeName + string("\"")
    if declFileId != 0:
        realTypeStr.add(string(", file: !") + str(declFileId) + string(", line: ") + str(declLine))
    realTypeStr.add(string(", size: ") + str(totalSize) + string(", align: ") + str(totalAlign) + string(", elements: !{") + membersStr + string("})"))

    # Check if a placeholder was created during field processing (self-referential
    # type, e.g. ``type Node = object; next: ptr Node``).
    with let:
        postFieldCached = c.debug.diTypeCache.getOrDefault(symId)

    # Update pre-existing placeholder (from genDITypeForSymbol or recursive call)
    if oldCached > 1:
        c.debug.metadata[oldCached] = realTypeStr
        result = oldCached
    # Also update any placeholder created during field processing
    if postFieldCached > 1 and postFieldCached != oldCached:
        c.debug.metadata[postFieldCached] = realTypeStr
        if result == 0:
            result = postFieldCached
    # No placeholder exists yet — create fresh metadata
    if result == 0:
        result = _addMetadata(c, realTypeStr)

    c.debug.diTypeCache[symId] = result
    c.debug.compositeTypeDone.incl(symId)

    # Consume the caller's inline cursor
    skip(n)
    return result
