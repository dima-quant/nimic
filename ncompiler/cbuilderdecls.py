# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# included from cgen.nim (include file: Builder, Snippet, BModule, PType, PSym, CC, ... come from the
# includer; tests: ncompiler/tests/test_ccg.py)


class _VarKind(NIntEnum):
    Local = 0
    Global = auto()
    Threadvar = auto()
    Const = auto()
    AlwaysConst = auto()  ## const even on C++


def _addVarHeader(builder: mut @ Builder, kind: _VarKind):
    ## adds modifiers for given var kind:
    ## Local has no modifier
    ## Global has `static` modifier
    ## Const has `static NIM_CONST` modifier
    ## AlwaysConst has `static const` modifier (NIM_CONST is no-op on C++)
    ## Threadvar is unimplemented
    match kind:
        case _VarKind.Local:
            discard
        case _VarKind.Global:
            builder.add(string("static "))
        case _VarKind.Const:
            builder.add(string("static NIM_CONST "))
        case _VarKind.AlwaysConst:
            builder.add(string("static const "))
        case _VarKind.Threadvar:
            doAssert(False, string("unimplemented"))


@dispatch
def _addVar(builder: mut @ Builder, kind: _VarKind = _VarKind.Local, name: string = string(""),
           typ: Snippet = string(""), initializer: Snippet = string("")):
    ## adds a variable declaration to the builder
    builder._addVarHeader(kind)
    builder.add(typ)
    builder.add(string(" "))
    builder.add(name)
    if initializer.len != 0:
        builder.add(string(" = "))
        builder.add(initializer)
    builder.addLineEnd(string(";"))


@template
def _addVarWithType(builder: mut @ Builder, kind: _VarKind = _VarKind.Local, name: string = string(""),
                   body: typed = None):
    ## adds a variable declaration to the builder, with the `body` building the type
    builder._addVarHeader(kind)
    body
    builder.add(string(" "))
    builder.add(name)
    builder.addLineEnd(string(";"))


@template
def _addVarWithInitializer(builder: mut @ Builder, kind: _VarKind = _VarKind.Local, name: string = string(""),
                          typ: Snippet = string(""), initializerBody: typed = None):
    ## adds a variable declaration to the builder, with
    ## `initializerBody` building the initializer. initializer must be provided
    builder._addVarHeader(kind)
    builder.add(typ)
    builder.add(string(" "))
    builder.add(name)
    builder.add(string(" = "))
    initializerBody
    builder.addLineEnd(string(";"))


@template
def _addVarWithTypeAndInitializer(builder: mut @ Builder, kind: _VarKind = _VarKind.Local, name: string = string(""),
                                 typeBody: typed = None, initializerBody: typed = None):
    ## adds a variable declaration to the builder, with `typeBody` building the type, and
    ## `initializerBody` building the initializer. initializer must be provided
    builder._addVarHeader(kind)
    typeBody
    builder.add(string(" "))
    builder.add(name)
    builder.add(string(" = "))
    initializerBody
    builder.addLineEnd(string(";"))


def _addArrayVar(builder: mut @ Builder, kind: _VarKind = _VarKind.Local, name: string = string(""),
                elementType: Snippet = string(""), len: nint = 0, initializer: Snippet = string("")):
    ## adds an array variable declaration to the builder
    builder._addVarHeader(kind)
    builder.add(elementType)
    builder.add(string(" "))
    builder.add(name)
    builder.add(string("["))
    builder.addIntValue(len)
    builder.add(string("]"))
    if initializer.len != 0:
        builder.add(string(" = "))
        builder.add(initializer)
    builder.addLineEnd(string(";"))


@template
def _addArrayVarWithInitializer(builder: mut @ Builder, kind: _VarKind = _VarKind.Local, name: string = string(""),
                               elementType: Snippet = string(""), len: nint = 0, body: typed = None):
    ## adds an array variable declaration to the builder with the initializer built according to `body`
    builder._addVarHeader(kind)
    builder.add(elementType)
    builder.add(string(" "))
    builder.add(name)
    builder.add(string("["))
    builder.addIntValue(len)
    builder.add(string("] = "))
    body
    builder.addLineEnd(string(";"))


@template
def _addTypedef(builder: mut @ Builder, name: string, typeBody: typed):
    ## adds a typedef declaration to the builder with name `name` and type as
    ## built in `typeBody`
    builder.add(string("typedef "))
    typeBody
    builder.add(string(" "))
    builder.add(name)
    builder.addLineEnd(string(";"))


def _addProcTypedef(builder: mut @ Builder, callConv: TCallingConvention, name: string, rettype: Snippet,
                   params: Snippet):
    builder.add(string("typedef "))
    builder.add(_CallingConvToStr[callConv])
    builder.add(string("_PTR("))
    builder.add(rettype)
    builder.add(string(", "))
    builder.add(name)
    builder.add(string(")"))
    builder.add(params)
    builder.addLineEnd(string(";"))


@template
def _addArrayTypedef(builder: mut @ Builder, name: string, len: BiggestInt, typeBody: typed):
    ## adds an array typedef declaration to the builder with name `name`,
    ## length `len`, and element type as built in `typeBody`
    builder.add(string("typedef "))
    typeBody
    builder.add(string(" "))
    builder.add(name)
    builder.add(string("["))
    builder.addIntValue(len)
    builder.addLineEnd(string("];"))


class _StructInitializerKind(NIntEnum):
    siOrderedStruct = 0  ## struct constructor, but without named fields on C
    siNamedStruct = auto()  ## struct constructor, with named fields i.e. C99 designated initializer
    siArray = auto()  ## array constructor
    siWrapper = auto()  ## wrapper for a single field, generates it verbatim


class _StructInitializer(Object):
    ## context for building struct initializers, i.e. `{ field1, field2 }`
    _kind: _StructInitializerKind
    ## if true, fields will not be named, instead values are placed in order
    _needsComma: bool


def _initStructInitializer(builder: mut @ Builder, kind: _StructInitializerKind) -> _StructInitializer:
    ## starts building a struct initializer, i.e. braced initializer list
    result = _StructInitializer(_kind=kind, _needsComma=False)
    if kind != _StructInitializerKind.siWrapper:
        builder.add(string("{"))
    return result


@template
def _addField(builder: mut @ Builder, constr: mut @ _StructInitializer, name: string, valueBody: typed):
    ## adds a field to a struct initializer, with the value built in `valueBody`
    if constr._needsComma:
        assert constr._kind != _StructInitializerKind.siWrapper, "wrapper constructor cannot have multiple fields"
        builder.add(string(", "))
    else:
        constr._needsComma = True
    match constr._kind:
        case _StructInitializerKind.siArray | _StructInitializerKind.siWrapper:
            # no name, can just add value
            valueBody
        case _StructInitializerKind.siOrderedStruct:
            # positional init - name not used in output (empty allowed for anonymous unions)
            valueBody
        case _StructInitializerKind.siNamedStruct:
            # designated init - empty name for anonymous unions (skips .name = prefix)
            if name.len != 0:
                builder.add(string("."))
                builder.add(name)
                builder.add(string(" = "))
            valueBody


def _finishStructInitializer(builder: mut @ Builder, constr: _StructInitializer):
    ## finishes building a struct initializer
    if constr._kind != _StructInitializerKind.siWrapper:
        builder.add(string("}"))


@template
def _addStructInitializer(builder: mut @ Builder, constr: out @ _StructInitializer, kind: _StructInitializerKind,
                         body: typed):
    ## builds a struct initializer, i.e. `{ field1, field2 }`
    ## a `var StructInitializer` must be declared and passed as a parameter so
    ## that it can be used with `addField`
    constr <<= builder._initStructInitializer(kind)
    body
    builder._finishStructInitializer(constr)


@dispatch
def _addField(obj: mut @ Builder, name: Snippet, typ: Snippet, isFlexArray: bool = False,
             initializer: Snippet = string("")):
    ## adds a field inside a struct/union type
    obj.add(ch('\t'))
    obj.add(typ)
    obj.add(string(" "))
    obj.add(name)
    if isFlexArray:
        obj.add(string("[SEQ_DECL_SIZE]"))
    if initializer.len != 0:
        obj.add(initializer)
    obj.add(string(";\n"))


def _addArrayField(obj: mut @ Builder, name: Snippet, elementType: Snippet, len: nint,
                  initializer: Snippet = string("")):
    ## adds an array field inside a struct/union type
    obj.add(ch('\t'))
    obj.add(elementType)
    obj.add(string(" "))
    obj.add(name)
    obj.add(string("["))
    obj.addIntValue(len)
    obj.add(string("]"))
    if initializer.len != 0:
        obj.add(initializer)
    obj.add(string(";\n"))


@dispatch
def _addField(obj: mut @ Builder, field: PSym, name: Snippet, typ: Snippet, isFlexArray: bool = False,
             initializer: Snippet = string("")):
    ## adds an field inside a struct/union type, based on an `skField` symbol
    obj.add(ch('\t'))
    if field.alignment > 0:
        obj.add(string("NIM_ALIGN("))
        obj.addIntValue(field.alignment)
        obj.add(string(") "))
    obj.add(typ)
    if TSymFlag.sfNoalias in field.flags:
        obj.add(string(" NIM_NOALIAS"))
    obj.add(string(" "))
    obj.add(name)
    if isFlexArray:
        obj.add(string("[SEQ_DECL_SIZE]"))
    if field.bitsize != 0:
        obj.add(string(":"))
        obj.addIntValue(field.bitsize)
    if initializer.len != 0:
        obj.add(initializer)
    obj.add(string(";\n"))


def _addProcField(obj: mut @ Builder, callConv: TCallingConvention, name: string, rettype: Snippet,
                 params: Snippet):
    obj.add(_CallingConvToStr[callConv])
    obj.add(string("_PTR("))
    obj.add(rettype)
    obj.add(string(", "))
    obj.add(name)
    obj.add(string(")"))
    obj.add(params)
    obj.add(string(";\n"))


class _BaseClassKind(NIntEnum):
    ## denotes how and whether or not the base class/RTTI should be stored
    bcNone = 0
    bcCppInherit = auto()
    bcSupField = auto()
    bcNoneRtti = auto()
    bcNoneTinyRtti = auto()


class _StructBuilderInfo(Object):
    ## context for building `struct` types
    _baseKind: _BaseClassKind
    _named: bool
    _preFieldsLen: nint


def _structOrUnion(t: PType) -> Snippet:
    with let:
        t = t.skipTypes(TTypeKinds({TTypeKind.tyAlias, TTypeKind.tySink}))
    if TTypeFlag.tfUnion in t.flags: return string("union")
    else: return string("struct")


def _startSimpleStruct(obj: mut @ Builder, m: BModule, name: string, baseType: Snippet) -> _StructBuilderInfo:
    result = _StructBuilderInfo(_baseKind=_BaseClassKind.bcNone, _named=name.len != 0)
    obj.add(string("struct"))
    if result._named:
        obj.add(string(" "))
        obj.add(name)
    if baseType.len != 0:
        if m.compileToCpp:
            result._baseKind = _BaseClassKind.bcCppInherit
        else:
            result._baseKind = _BaseClassKind.bcSupField
    if result._baseKind == _BaseClassKind.bcCppInherit:
        obj.add(string(" : public "))
        obj.add(baseType)
    obj.add(string(" "))
    obj.add(string("{\n"))
    result._preFieldsLen = obj.buf.len
    if result._baseKind == _BaseClassKind.bcSupField:
        obj._addField(name=string("Sup"), typ=baseType)
    return result


def _finishSimpleStruct(obj: mut @ Builder, m: BModule, info: _StructBuilderInfo):
    if info._baseKind == _BaseClassKind.bcNone and info._preFieldsLen == obj.buf.len:
        # no fields were added, add dummy field
        obj._addField(name=string("dummy"), typ=CChar)
    if info._named:
        obj.add(string("};\n"))
    else:
        obj.add(string("}"))


@template
def _addSimpleStruct(obj: mut @ Builder, m: BModule, name: string, baseType: Snippet, body: typed):
    ## builds a struct type not based on a Nim type with fields according to `body`,
    ## `name` can be empty to build as a type expression and not a statement
    with let:
        info = _startSimpleStruct(obj, m, name, baseType)
    body
    _finishSimpleStruct(obj, m, info)


def _startStruct(obj: mut @ Builder, m: BModule, t: PType, name: string, baseType: Snippet) -> _StructBuilderInfo:
    result = _StructBuilderInfo(_baseKind=_BaseClassKind.bcNone, _named=name.len != 0)
    if TTypeFlag.tfPacked in t.flags:
        if TInfoCCProp.hasAttribute in CC[m.config.cCompiler].props:
            obj.add(_structOrUnion(t))
            obj.add(string(" __attribute__((__packed__))"))
        else:
            obj.add(string("#pragma pack(push, 1)\n"))
            obj.add(_structOrUnion(t))
    else:
        obj.add(_structOrUnion(t))
    if result._named:
        obj.add(string(" "))
        obj.add(name)
    if t.kind == TTypeKind.tyObject:
        if t.baseClass is None:
            if lacksMTypeField(t):
                result._baseKind = _BaseClassKind.bcNone
            elif TGlobalOption.optTinyRtti in m.config.globalOptions:
                result._baseKind = _BaseClassKind.bcNoneTinyRtti
            else:
                result._baseKind = _BaseClassKind.bcNoneRtti
        elif m.compileToCpp:
            result._baseKind = _BaseClassKind.bcCppInherit
        else:
            result._baseKind = _BaseClassKind.bcSupField
    elif baseType.len != 0:
        if m.compileToCpp:
            result._baseKind = _BaseClassKind.bcCppInherit
        else:
            result._baseKind = _BaseClassKind.bcSupField
    if result._baseKind == _BaseClassKind.bcCppInherit:
        obj.add(string(" : public "))
        obj.add(baseType)
    obj.add(string(" "))
    obj.add(string("{\n"))
    result._preFieldsLen = obj.buf.len
    match result._baseKind:
        case _BaseClassKind.bcNone:
            # rest of the options add a field or don't need it due to inheritance,
            # we need to add the dummy field for uncheckedarray ahead of time
            # so that it remains trailing
            if (t.itemId not in m.g.graph.memberProcsPerType and
                    t.n is not None and t.n.len == 1 and t.n[0].kind == TNodeKind.nkSym and
                    t.n[0].sym.typ.skipTypes(abstractInst).kind == TTypeKind.tyUncheckedArray):
                # only consists of flexible array field, add *initial* dummy field
                obj._addField(name=string("dummy"), typ=CChar)
        case _BaseClassKind.bcCppInherit:
            discard
        case _BaseClassKind.bcNoneRtti:
            obj._addField(name=string("m_type"), typ=_ptrType(cgsymValue(m, string("TNimType"))))
        case _BaseClassKind.bcNoneTinyRtti:
            obj._addField(name=string("m_type"), typ=_ptrType(cgsymValue(m, string("TNimTypeV2"))))
        case _BaseClassKind.bcSupField:
            obj._addField(name=string("Sup"), typ=baseType)
    return result


def _finishStruct(obj: mut @ Builder, m: BModule, t: PType, info: _StructBuilderInfo):
    if (info._baseKind == _BaseClassKind.bcNone and info._preFieldsLen == obj.buf.len and
            t.itemId not in m.g.graph.memberProcsPerType):
        # no fields were added, add dummy field
        obj._addField(name=string("dummy"), typ=CChar)
    if info._named:
        obj.add(string("};\n"))
    else:
        obj.add(string("}"))
    if TTypeFlag.tfPacked in t.flags and TInfoCCProp.hasAttribute not in CC[m.config.cCompiler].props:
        obj.add(string("#pragma pack(pop)\n"))


@template
def _addStruct(obj: mut @ Builder, m: BModule, typ: PType, name: string, baseType: Snippet, body: typed):
    ## builds a struct type directly based on `typ` with fields according to `body`,
    ## `name` can be empty to build as a type expression and not a statement
    with let:
        info = _startStruct(obj, m, typ, name, baseType)
    body
    _finishStruct(obj, m, typ, info)


@template
def _addFieldWithStructType(obj: mut @ Builder, m: BModule, parentTyp: PType, fieldName: string, body: typed):
    ## adds a field with a `struct { ... }` type, building the fields according to `body`
    obj.add(ch('\t'))
    if TTypeFlag.tfPacked in parentTyp.flags:
        if TInfoCCProp.hasAttribute in CC[m.config.cCompiler].props:
            obj.add(string("struct __attribute__((__packed__)) {\n"))
        else:
            obj.add(string("#pragma pack(push, 1)\nstruct {"))
    else:
        obj.add(string("struct {\n"))
    body
    obj.add(string("} "))
    obj.add(fieldName)
    obj.add(string(";\n"))
    if TTypeFlag.tfPacked in parentTyp.flags and TInfoCCProp.hasAttribute not in CC[m.config.cCompiler].props:
        obj.add(string("#pragma pack(pop)\n"))


@template
def _addAnonUnion(obj: mut @ Builder, body: typed):
    ## adds an anonymous union i.e. `union { ... };` with fields according to `body`
    obj.add(string("union{\n"))
    body
    obj.add(string("};\n"))


@template
def _addUnionType(obj: mut @ Builder, body: typed):
    ## adds a union type i.e. `union { ... }` with fields according to `body`
    obj.add(string("union{\n"))
    body
    obj.add(string("}"))


class _DeclVisibility(NIntEnum):
    None_ = 0
    Extern = auto()
    ExternC = auto()
    ImportLib = auto()
    ExportLib = auto()
    ExportLibVar = auto()
    Private = auto()
    StaticProc = auto()


def _addVisibilityPrefix(builder: mut @ Builder, visibility: _DeclVisibility):
    # internal proc
    match visibility:
        case _DeclVisibility.None_:
            discard
        case _DeclVisibility.Extern:
            builder.add(string("extern "))
        case _DeclVisibility.ExternC:
            builder.add(string("NIM_EXTERNC "))
        case _DeclVisibility.ImportLib:
            builder.add(string("N_LIB_IMPORT "))
        case _DeclVisibility.ExportLib:
            builder.add(string("N_LIB_EXPORT "))
        case _DeclVisibility.ExportLibVar:
            builder.add(string("N_LIB_EXPORT_VAR "))
        case _DeclVisibility.Private:
            builder.add(string("N_LIB_PRIVATE "))
        case _DeclVisibility.StaticProc:
            builder.add(string("static "))


@template
def _addDeclWithVisibility(builder: mut @ Builder, visibility: _DeclVisibility, declBody: typed):
    ## adds a declaration as in `declBody` with the given visibility
    builder._addVisibilityPrefix(visibility)
    declBody


class _ProcParamBuilder(Object):
    _needsComma: bool


def _initProcParamBuilder(builder: mut @ Builder) -> _ProcParamBuilder:
    result = _ProcParamBuilder(_needsComma=False)
    builder.add(string("("))
    return result


def _finishProcParamBuilder(builder: mut @ Builder, params: _ProcParamBuilder):
    if params._needsComma:
        builder.add(string(")"))
    else:
        builder.add(string("void)"))


@template
def cgDeclFrmt(s: PSym) -> string:
    return s.constraint.strVal


@dispatch
def _addParam(builder: mut @ Builder, params: mut @ _ProcParamBuilder, name: string, typ: Snippet):
    if params._needsComma:
        builder.add(string(", "))
    else:
        params._needsComma = True
    builder.add(typ)
    builder.add(string(" "))
    builder.add(name)


@dispatch
def _addParam(builder: mut @ Builder, params: mut @ _ProcParamBuilder, param: PSym, typ: Snippet):
    if params._needsComma:
        builder.add(string(", "))
    else:
        params._needsComma = True
    with var:
        modifiedTyp = typ.copy()
    if TSymFlag.sfNoalias in param.flags:
        modifiedTyp.add(string(" NIM_NOALIAS"))
    if TSymFlag.sfCodegenDecl not in param.flags:
        builder.add(modifiedTyp)
        builder.add(string(" "))
        builder.add(param.loc.snippet)
    else:
        builder.add(runtimeFormat(cgDeclFrmt(param), [modifiedTyp, param.loc.snippet]))


def _addUnnamedParam(builder: mut @ Builder, params: mut @ _ProcParamBuilder, typ: Snippet):
    if params._needsComma:
        builder.add(string(", "))
    else:
        params._needsComma = True
    builder.add(typ)


def _addProcTypedParam(builder: mut @ Builder, paramBuilder: mut @ _ProcParamBuilder, callConv: TCallingConvention,
                      name: string, rettype: Snippet, params: Snippet):
    if paramBuilder._needsComma:
        builder.add(string(", "))
    else:
        paramBuilder._needsComma = True
    builder.add(_CallingConvToStr[callConv])
    builder.add(string("_PTR("))
    builder.add(rettype)
    builder.add(string(", "))
    builder.add(name)
    builder.add(string(")"))
    builder.add(params)


def _addVarargsParam(builder: mut @ Builder, params: mut @ _ProcParamBuilder):
    # does not exist in NIFC, needs to be proc pragma
    if params._needsComma:
        builder.add(string(", "))
    else:
        params._needsComma = True
    builder.add(string("..."))


@template
def _addProcParams(builder: mut @ Builder, params: out @ _ProcParamBuilder, body: typed):
    params <<= _initProcParamBuilder(builder)
    body
    _finishProcParamBuilder(builder, params)


class _SimpleProcParam(NTuple):
    name: string
    typ: string


def _cProcParams(*params: _SimpleProcParam) -> Snippet:
    if len(params) == 0: return string("(void)")
    result = string("(")
    for i in range(len(params)):
        if i != 0: result.add(string(", "))
        result.add(params[i].typ)
        if params[i].name.len != 0:
            result.add(string(" "))
            result.add(params[i].name)
    result.add(string(")"))
    return result


@template
def _addProcHeaderWithParams(builder: mut @ Builder, callConv: TCallingConvention,
                            name: string, rettype: Snippet, paramBuilder: typed):
    # on nifc should build something like (proc name params type pragmas
    # with no body given
    # or enforce this with secondary builder object
    builder.add(_CallingConvToStr[callConv])
    builder.add(string("("))
    builder.add(rettype)
    builder.add(string(", "))
    builder.add(name)
    builder.add(string(")"))
    paramBuilder


@dispatch
def _addProcHeader(builder: mut @ Builder, callConv: TCallingConvention,
                  name: string, rettype: Snippet, params: Snippet):
    # on nifc should build something like (proc name params type pragmas
    # with no body given
    # or enforce this with secondary builder object
    with _addProcHeaderWithParams(builder, callConv, name, rettype):
        builder.add(params)


@dispatch
def _addProcHeader(builder: mut @ Builder, name: string, rettype: Snippet, params: Snippet,
                  isConstructor: bool = False):
    # no callconv
    builder.add(rettype)
    builder.add(string(" "))
    if isConstructor:
        builder.add(string("__attribute__((constructor)) "))
    builder.add(name)
    builder.add(params)


@dispatch
def _addProcHeader(builder: mut @ Builder, m: BModule, prc: PSym, name: string, params: Snippet, rettype: Snippet,
                  addAttributes: bool):
    # on nifc should build something like (proc name params type pragmas
    # with no body given
    # or enforce this with secondary builder object
    with let:
        noreturn = isNoReturn(m, prc)
    # Nim: extccomp.CC (qualified) here and below
    if TSymFlag.sfPure in prc.flags and TInfoCCProp.hasDeclspec in CC[m.config.cCompiler].props:
        builder.add(string("__declspec(naked) "))
    if noreturn and TInfoCCProp.hasDeclspec in CC[m.config.cCompiler].props:
        builder.add(string("__declspec(noreturn) "))
    builder.add(_CallingConvToStr[prc.typ.callConv])
    builder.add(string("("))
    builder.add(rettype)
    builder.add(string(", "))
    builder.add(name)
    builder.add(string(")"))
    builder.add(params)
    if addAttributes:
        if TSymFlag.sfPure in prc.flags and TInfoCCProp.hasAttribute in CC[m.config.cCompiler].props:
            builder.add(string(" __attribute__((naked))"))
        if noreturn and TInfoCCProp.hasAttribute in CC[m.config.cCompiler].props:
            builder.add(string(" __attribute__((noreturn))"))


def _finishProcHeaderAsProto(builder: mut @ Builder):
    builder.addLineEnd(string(";"))


@template
def _finishProcHeaderWithBody(builder: mut @ Builder, body: typed):
    builder.addLineEndIndent(string(" {"))
    body
    builder.addLineEndDedent(string("}"))
    builder.addNewline()


@dispatch
def _addProcVar(builder: mut @ Builder, m: BModule, prc: PSym, name: string, params: Snippet, rettype: Snippet,
               isStatic: bool = False, ignoreAttributes: bool = False):
    # on nifc, builds full variable
    if isStatic:
        builder.add(string("static "))
    with let:
        noreturn = isNoReturn(m, prc)
    if not ignoreAttributes:
        if TSymFlag.sfPure in prc.flags and TInfoCCProp.hasDeclspec in CC[m.config.cCompiler].props:
            builder.add(string("__declspec(naked) "))
        if noreturn and TInfoCCProp.hasDeclspec in CC[m.config.cCompiler].props:
            builder.add(string("__declspec(noreturn) "))
    builder.add(_CallingConvToStr[prc.typ.callConv])
    builder.add(string("_PTR("))
    builder.add(rettype)
    builder.add(string(", "))
    builder.add(name)
    builder.add(string(")"))
    builder.add(params)
    if not ignoreAttributes:
        if TSymFlag.sfPure in prc.flags and TInfoCCProp.hasAttribute in CC[m.config.cCompiler].props:
            builder.add(string(" __attribute__((naked))"))
        if noreturn and TInfoCCProp.hasAttribute in CC[m.config.cCompiler].props:
            builder.add(string(" __attribute__((noreturn))"))
    # ensure we are just adding a variable:
    builder.addLineEnd(string(";"))


@dispatch
def _addProcVar(builder: mut @ Builder, callConv: TCallingConvention,
               name: string, params: Snippet, rettype: Snippet,
               isStatic: bool = False, isVolatile: bool = False):
    # on nifc, builds full variable
    if isStatic:
        builder.add(string("static "))
    builder.add(_CallingConvToStr[callConv])
    builder.add(string("_PTR("))
    builder.add(rettype)
    builder.add(string(", "))
    if isVolatile:
        builder.add(string("volatile "))
    builder.add(name)
    builder.add(string(")"))
    builder.add(params)
    # ensure we are just adding a variable:
    builder.addLineEnd(string(";"))


@dispatch
def _addProcVar(builder: mut @ Builder,
               name: string, params: Snippet, rettype: Snippet,
               isStatic: bool = False, isVolatile: bool = False):
    # no callconv
    if isStatic:
        builder.add(string("static "))
    builder.add(rettype)
    builder.add(string(" (*"))
    if isVolatile:
        builder.add(string("volatile "))
    builder.add(name)
    builder.add(string(")"))
    builder.add(params)
    # ensure we are just adding a variable:
    builder.addLineEnd(string(";"))


class _VarInitializerKind(NIntEnum):
    Assignment = 0
    CppConstructor = auto()


@dispatch
def _addVar(builder: mut @ Builder, m: BModule, s: PSym, name: string, typ: Snippet, kind: _VarKind = _VarKind.Local,
           visibility: _DeclVisibility = _DeclVisibility.None_, initializer: Snippet = string(""),
           initializerKind: _VarInitializerKind = _VarInitializerKind.Assignment):
    if TSymFlag.sfCodegenDecl in s.flags:
        builder.add(runtimeFormat(cgDeclFrmt(s), [typ, name]))
        if initializer.len != 0:
            if initializerKind == _VarInitializerKind.Assignment:
                builder.add(string(" = "))
            builder.add(initializer)
        builder.addLineEnd(string(";"))
        return
    if s.kind in Tset[TSymKind]({TSymKind.skLet, TSymKind.skVar, TSymKind.skField, TSymKind.skForVar}) and s.alignment > 0:
        builder.add(string("NIM_ALIGN(") + str(s.alignment) + ") ")
    builder._addVisibilityPrefix(visibility)
    if kind == _VarKind.Threadvar:
        if TGlobalOption.optThreads in m.config.globalOptions:
            with let:
                sym = s.typ.sym
            if sym is not None and TSymFlag.sfCppNonPod in sym.flags:
                builder.add(string("NIM_THREAD_LOCAL "))
            else: builder.add(string("NIM_THREADVAR "))
    else:
        builder._addVarHeader(kind)
    builder.add(typ)
    if TSymFlag.sfRegister in s.flags: builder.add(string(" register"))
    if TSymFlag.sfVolatile in s.flags: builder.add(string(" volatile"))
    if TSymFlag.sfNoalias in s.flags: builder.add(string(" NIM_NOALIAS"))
    builder.add(string(" "))
    builder.add(name)
    if initializer.len != 0:
        if initializerKind == _VarInitializerKind.Assignment:
            builder.add(string(" = "))
        builder.add(initializer)
    builder.addLineEnd(string(";"))


def _addInclude(builder: mut @ Builder, value: Snippet):
    builder.addLineEnd(string("#include ") + value)
