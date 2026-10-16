# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

# Test scaffolding (nimic_translation_rules.md §2.1): the subset of cbuilderdecls.nim (not converted yet)
# that the ccg* include files use, copied line for line unless marked simplified. Included by the harnesses
# in ncompiler/tests between cbuilderexprs and cbuilderstmts, as in cgen.nim.

class VarKind(NIntEnum):
    Local = 0
    Global = auto()
    Threadvar = auto()
    Const = auto()
    AlwaysConst = auto()  # const even on C++


class DeclVisibility(NIntEnum):
    None_ = 0
    Extern = auto()
    ExternC = auto()
    ImportLib = auto()
    ExportLib = auto()
    ExportLibVar = auto()
    Private = auto()
    StaticProc = auto()


def addVarHeader(builder: mut@Builder, kind: VarKind) -> None:
    match kind:
        case VarKind.Local:
            discard
        case VarKind.Global:
            builder.add(string("static "))
        case VarKind.Const:
            builder.add(string("static NIM_CONST "))
        case VarKind.AlwaysConst:
            builder.add(string("static const "))
        case VarKind.Threadvar:
            doAssert(False, string("unimplemented"))


@dispatch
def addVar(builder: mut@Builder, kind: VarKind = VarKind.Local, name: string = string(""), typ: Snippet = string(""),
           initializer: Snippet = string("")) -> None:
    builder.addVarHeader(kind)
    builder.add(typ)
    builder.add(string(" "))
    builder.add(name)
    if initializer.len != 0:
        builder.add(string(" = "))
        builder.add(initializer)
    builder.addLineEnd(string(";"))


@template
def addVarWithInitializer(builder: mut@Builder, kind: VarKind = VarKind.Local, name: string = string(""),
                          typ: Snippet = string(""), initializerBody: typed = None):
    ## adds a variable declaration to the builder, with
    ## `initializerBody` building the initializer. initializer must be provided
    builder.addVarHeader(kind)
    builder.add(typ)
    builder.add(string(" "))
    builder.add(name)
    builder.add(string(" = "))
    initializerBody
    builder.addLineEnd(string(";"))


@template
def addVarWithTypeAndInitializer(builder: mut@Builder, kind: VarKind = VarKind.Local, name: string = string(""),
                                 typeBody: typed = None, initializerBody: typed = None):
    ## adds a variable declaration to the builder, with `typeBody` building the type, and
    ## `initializerBody` building the initializer. initializer must be provided
    builder.addVarHeader(kind)
    typeBody
    builder.add(string(" "))
    builder.add(name)
    builder.add(string(" = "))
    initializerBody
    builder.addLineEnd(string(";"))


class StructInitializerKind(NIntEnum):
    siOrderedStruct = 0  # struct constructor, but without named fields on C
    siNamedStruct = auto()  # struct constructor, with named fields i.e. C99 designated initializer
    siArray = auto()  # array constructor
    siWrapper = auto()  # wrapper for a single field, generates it verbatim


class StructInitializer(Object):
    ## context for building struct initializers, i.e. `{ field1, field2 }`
    kind: StructInitializerKind
    ## if true, fields will not be named, instead values are placed in order
    needsComma: bool


def initStructInitializer(builder: mut@Builder, kind: StructInitializerKind) -> StructInitializer:
    ## starts building a struct initializer, i.e. braced initializer list
    result = StructInitializer(kind=kind, needsComma=False)
    if kind != StructInitializerKind.siWrapper:
        builder.add(string("{"))
    return result


@template
def addField(builder: mut@Builder, constr: mut@StructInitializer, name: string, valueBody: typed):
    ## adds a field to a struct initializer, with the value built in `valueBody`
    if constr.needsComma:
        assert constr.kind != StructInitializerKind.siWrapper, "wrapper constructor cannot have multiple fields"
        builder.add(string(", "))
    else:
        constr.needsComma = True
    match constr.kind:
        case StructInitializerKind.siArray | StructInitializerKind.siWrapper:
            # no name, can just add value
            valueBody
        case StructInitializerKind.siOrderedStruct:
            # positional init - name not used in output (empty allowed for anonymous unions)
            valueBody
        case StructInitializerKind.siNamedStruct:
            # designated init - empty name for anonymous unions (skips .name = prefix)
            if name.len != 0:
                builder.add(string("."))
                builder.add(name)
                builder.add(string(" = "))
            valueBody


def finishStructInitializer(builder: mut@Builder, constr: StructInitializer) -> None:
    ## finishes building a struct initializer
    if constr.kind != StructInitializerKind.siWrapper:
        builder.add(string("}"))


@template
def addStructInitializer(builder: mut@Builder, constr: out@StructInitializer, kind: StructInitializerKind,
                         body: typed):
    ## builds a struct initializer, i.e. `{ field1, field2 }`
    ## a `var StructInitializer` must be declared and passed as a parameter so
    ## that it can be used with `addField`
    constr <<= builder.initStructInitializer(kind)
    body
    builder.finishStructInitializer(constr)


@dispatch
def addVar(builder: mut@Builder, m: BModule, s: PSym, name: string, typ: Snippet, kind: VarKind = VarKind.Local,
           visibility: DeclVisibility = DeclVisibility.None_, initializer: Snippet = string("")) -> None:
    # simplified: visibility as a prefix
    if visibility == DeclVisibility.Extern:
        builder.add(string("extern "))
    elif visibility == DeclVisibility.Private:
        builder.add(string("static "))
    if kind == VarKind.Threadvar:
        builder.add(string("NIM_THREADVAR "))
    builder.add(typ)
    builder.add(string(" "))
    builder.add(name)
    builder.addLineEnd(string(";"))


@template
def addTypedef(builder: mut@Builder, name: string, typeBody: typed):
    builder.add(string("typedef "))
    typeBody
    builder.add(string(" "))
    builder.add(name)
    builder.addLineEnd(string(";"))


@dispatch
def addField(obj: mut@Builder, name: Snippet, typ: Snippet, isFlexArray: bool = False,
             initializer: Snippet = string("")) -> None:
    ## adds a field inside a struct/union type
    obj.add(ch("\t"))
    obj.add(typ)
    obj.add(string(" "))
    obj.add(name)
    if isFlexArray:
        obj.add(string("[SEQ_DECL_SIZE]"))
    if initializer.len != 0:
        obj.add(initializer)
    obj.add(string(";\n"))


def addArrayField(obj: mut@Builder, name: Snippet, elementType: Snippet, len: nint,
                  initializer: Snippet = string("")) -> None:
    ## adds an array field inside a struct/union type
    obj.add(ch("\t"))
    obj.add(elementType)
    obj.add(string(" "))
    obj.add(name)
    obj.add(string("["))
    obj.addIntValue(len)
    obj.add(string("]"))
    if initializer.len != 0:
        obj.add(initializer)
    obj.add(string(";\n"))


class BaseClassKind(NIntEnum):
    ## denotes how and whether or not the base class/RTTI should be stored
    bcNone = 0
    bcCppInherit = auto()
    bcSupField = auto()
    bcNoneRtti = auto()
    bcNoneTinyRtti = auto()


class StructBuilderInfo(Object):
    ## context for building `struct` types
    baseKind: BaseClassKind
    named: bool
    preFieldsLen: nint


def startSimpleStruct(obj: mut@Builder, m: BModule, name: string, baseType: Snippet) -> StructBuilderInfo:
    result = StructBuilderInfo(baseKind=BaseClassKind.bcNone, named=name.len != 0)
    obj.add(string("struct"))
    if result.named:
        obj.add(string(" "))
        obj.add(name)
    if baseType.len != 0:
        if m.compileToCpp:
            result.baseKind = BaseClassKind.bcCppInherit
        else:
            result.baseKind = BaseClassKind.bcSupField
    if result.baseKind == BaseClassKind.bcCppInherit:
        obj.add(string(" : public "))
        obj.add(baseType)
    obj.add(string(" "))
    obj.add(string("{\n"))
    result.preFieldsLen = obj.buf.len
    if result.baseKind == BaseClassKind.bcSupField:
        obj.addField(name=string("Sup"), typ=baseType)
    return result


def finishSimpleStruct(obj: mut@Builder, m: BModule, info: StructBuilderInfo) -> None:
    if info.baseKind == BaseClassKind.bcNone and info.preFieldsLen == obj.buf.len:
        # no fields were added, add dummy field
        obj.addField(name=string("dummy"), typ=CChar)
    if info.named:
        obj.add(string("};\n"))
    else:
        obj.add(string("}"))


@template
def addSimpleStruct(obj: mut@Builder, m: BModule, name: string, baseType: Snippet, body: typed):
    ## builds a struct type not based on a Nim type with fields according to `body`,
    ## `name` can be empty to build as a type expression and not a statement
    with let:
        info = startSimpleStruct(obj, m, name, baseType)
    body
    finishSimpleStruct(obj, m, info)


def addVisibilityPrefix(builder: mut@Builder, visibility: DeclVisibility) -> None:
    # internal proc
    match visibility:
        case DeclVisibility.None_:
            discard
        case DeclVisibility.Extern:
            builder.add(string("extern "))
        case DeclVisibility.ExternC:
            builder.add(string("NIM_EXTERNC "))
        case DeclVisibility.ImportLib:
            builder.add(string("N_LIB_IMPORT "))
        case DeclVisibility.ExportLib:
            builder.add(string("N_LIB_EXPORT "))
        case DeclVisibility.ExportLibVar:
            builder.add(string("N_LIB_EXPORT_VAR "))
        case DeclVisibility.Private:
            builder.add(string("N_LIB_PRIVATE "))
        case DeclVisibility.StaticProc:
            builder.add(string("static "))


@template
def addDeclWithVisibility(builder: mut@Builder, visibility: DeclVisibility, declBody: typed):
    ## adds a declaration as in `declBody` with the given visibility
    builder.addVisibilityPrefix(visibility)
    declBody


@dispatch
def addProcHeader(builder: mut@Builder, name: string, rettype: Snippet, params: Snippet,
                  isConstructor: bool = False) -> None:
    builder.add(rettype)
    builder.add(string(" "))
    builder.add(name)
    builder.add(params)


@template
def finishProcHeaderWithBody(builder: mut@Builder, body: typed):
    builder.addLineEndIndent(string(" {"))
    body
    builder.addLineEndDedent(string("}"))
    builder.addNewline()


def cProcParams() -> Snippet:
    return string("(void)")


class ProcParamBuilder(Object):
    needsComma: bool


def initProcParamBuilder(builder: mut@Builder) -> ProcParamBuilder:
    result = ProcParamBuilder(needsComma=False)
    builder.add(string("("))
    return result


def finishProcParamBuilder(builder: mut@Builder, params: ProcParamBuilder) -> None:
    if params.needsComma:
        builder.add(string(")"))
    else:
        builder.add(string("void)"))


def addParam(builder: mut@Builder, params: mut@ProcParamBuilder, name: string, typ: Snippet) -> None:
    if params.needsComma:
        builder.add(string(", "))
    else:
        params.needsComma = True
    builder.add(typ)
    builder.add(string(" "))
    builder.add(name)


def addUnnamedParam(builder: mut@Builder, params: mut@ProcParamBuilder, typ: Snippet) -> None:
    if params.needsComma:
        builder.add(string(", "))
    else:
        params.needsComma = True
    builder.add(typ)


@template
def addProcParams(builder: mut@Builder, params: out@ProcParamBuilder, body: typed):
    params <<= initProcParamBuilder(builder)
    body
    finishProcParamBuilder(builder, params)


@template
def addProcHeaderWithParams(builder: mut@Builder, callConv: TCallingConvention, name: string, rettype: Snippet,
                            paramBuilder: typed):
    # on nifc should build something like (proc name params type pragmas
    # with no body given
    # or enforce this with secondary builder object
    builder.add(CallingConvToStr[callConv])
    builder.add(string("("))
    builder.add(rettype)
    builder.add(string(", "))
    builder.add(name)
    builder.add(string(")"))
    paramBuilder


def finishProcHeaderAsProto(builder: mut@Builder) -> None:
    builder.addLineEnd(string(";"))


def addProcVar(builder: mut@Builder, callConv: TCallingConvention, name: string, params: Snippet, rettype: Snippet,
               isStatic: bool = False, isVolatile: bool = False) -> None:
    # on nifc, builds full variable
    if isStatic:
        builder.add(string("static "))
    builder.add(CallingConvToStr[callConv])
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
