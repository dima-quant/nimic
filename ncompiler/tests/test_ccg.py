# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.intsets import *
from nimic.std.tables import *
from nimic.std.strutils import startsWith
from ..options import *
from ..lineinfos import *
from ..msgs import *
from ..nodekinds import *
from ..ropes import *
from ..int128 import *
from ..cbuilderbase import *
from ..platform import *
from nimic.std.tables import *

# Test harness of the ccg* include files of cgen.nim. Like cgen.nim it provides their context
# (cgen_context, cgen_procs, cgen_stmts: stand-ins for modules not converted yet;
# the imports: converted) and includes them in cgen's order (ccgtrav is included by ccgtypes).
include("cgen_context")
include("../cbuilderexprs", "../cbuilderdecls", "../cbuilderstmts")
include("cgen_procs")
include("../ccgliterals")
include("../ccgtrav")
include("../ccgreset")
include("../ccgthreadvars")
include("cgen_stmts")
include("../inliner")


def inlSym(id: nint, kind: TSymKind, name: string) -> PSym:
    return PSym(id=id, kind=kind, name=name, info=unknownLineInfo)


def inlTree(kind: TNodeKind, sons: seq[PNode]) -> PNode:
    return PNode(kind=kind, info=unknownLineInfo, sons=sons)


def inlProcType() -> PType:
    ## a proc type (ast.newProcType): son 0 is the return type; n[0] the effects, then the parameters
    with var:
        noReturn = seq[PType]()
        n = newNode(TNodeKind.nkFormalParams)
    noReturn.add(None)
    n.add(newNode(nkEffectList))
    return PType(kind=TTypeKind.tyProc, n=n, sonsImpl=noReturn)


def resetCode(p: BProc, t: PType) -> string:
    ## specializeReset of a location `x` of type t; returns the generated statements
    p.sections[TCProcSection.cpsStmts] = newBuilder(string(""))
    _specializeReset(p, TLoc(snippet=string("x"), t=t))
    return p.sections[TCProcSection.cpsStmts].extract()


def literalModule(gc: TGCMode, strings: StringsMode) -> BModule:
    ## a module of a 64-bit little endian target with the given GC and string implementation
    result = newModuleForTest(newConfigRef())
    result.config.selectedGC = gc
    result.config.selectedStrings = strings
    result.config.target.setTarget(TSystemOS.osLinux, TSystemCPU.cpuAmd64)
    return result


def strLit(m: BModule, s: string) -> string:
    ## genStringLiteral of a string literal node; returns the expression
    with var:
        b = newBuilder(string(""))
    _genStringLiteral(m, PNode(kind=TNodeKind.nkStrLit, strVal=s), b)
    return b.extract()


def traverseCode(c: _TTraversalClosure, t: PType) -> string:
    ## genTraverseProc of a location `x` of type t; returns the generated statements
    c._p.sections[TCProcSection.cpsStmts] = newBuilder(string(""))
    _genTraverseProc(c, string("x"), t)
    return c._p.sections[TCProcSection.cpsStmts].extract()


def fieldNode(name: string, t: PType) -> PNode:
    return PNode(kind=TNodeKind.nkSym, sym=PSym(typ=t, loc=TLoc(snippet=name, t=t)))


if comptime(__name__ == "__main__"):
    echo(string("Testing ccgliterals..."))
    with var:
        m1 = literalModule(TGCMode.gcRefc, StringsMode.stringDefault)
        m2 = literalModule(TGCMode.gcOrc, StringsMode.stringDefault)
        m3 = literalModule(TGCMode.gcOrc, StringsMode.stringSso)
    doAssert(_detectStrVersion(m1) == 1 and _detectSeqVersion(m1) == 1, string("version 1"))
    doAssert(_detectStrVersion(m2) == 2 and _detectSeqVersion(m2) == 2, string("version 2"))
    doAssert(_detectStrVersion(m3) == 3 and _detectSeqVersion(m3) == 2, string("version 3"))
    # 1. version 1 (GC'ed strings): a TGenericSeq struct, cached per module
    doAssert(strLit(m1, string("ab")) == string("((NimStringDesc*) (&TM__1_0))"), string("v1 literal"))
    doAssert(strLit(m1, string("ab")) == string("((NimStringDesc*) (&TM__1_0))"), string("v1 cached"))
    doAssert(m1.s[TCFileSection.cfsStrData].extract() ==
             string("static const struct {\n\tTGenericSeq Sup;\n\tNIM_CHAR data[3];\n} TM__1_0 = " +
                    "{{2, ((NI) (((NU) 2) | NIM_STRLIT_FLAG))}, \"ab\"};\n"), string("v1 data"))

    # 2. version 2 (destructor based): the payload is cached, each literal gets a NimStringV2
    doAssert(strLit(m2, string("ab")) == string("TM__1_1"), string("v2 literal"))
    doAssert(strLit(m2, string("ab")) == string("TM__1_2"), string("v2 second literal"))
    doAssert(m2.s[TCFileSection.cfsStrData].extract() ==
             string("static const struct {\n\tNI cap;\n\tNIM_CHAR data[3];\n} TM__1_0 = {(2 | NIM_STRLIT_FLAG), \"ab\"};\n" +
                    "static const NimStringV2 TM__1_1 = {2, ((NimStrPayload*) (&TM__1_0))};\n" +
                    "static const NimStringV2 TM__1_2 = {2, ((NimStrPayload*) (&TM__1_0))};\n"), string("v2 data"))
    with var:
        bc = newBuilder(string(""))
    _genStringLiteralV2Const(m2, PNode(kind=TNodeKind.nkStrLit, strVal=string("ab")), True, bc)
    doAssert(bc.extract() == string("{2, ((NimStrPayload*) (&TM__1_0))}"), string("v2 const"))
    with var:
        rd = Rope()
    _genStringLiteralDataOnly(m2, string("xy"), unknownLineInfo, True, rd)
    doAssert(rd == string("TM__1_3"), string("v2 data only"))

    # 3. version 3 (SmallString): short and medium strings inline, long ones in a cached LongString
    doAssert(strLit(m3, string("ab")) == string("TM__1_0"), string("v3 short"))
    doAssert(strLit(m3, string("abcdefghij")) == string("TM__1_1"), string("v3 medium"))
    doAssert(strLit(m3, string("abcdefghijklmnopq")) == string("TM__1_2"), string("v3 long"))
    doAssert(strLit(m3, string("abcdefghijklmnopq")) == string("TM__1_4"), string("v3 long again"))
    doAssert(m3.s[TCFileSection.cfsStrData].extract() ==
             string("static const SmallString TM__1_0 = {((NU) 6447362ULL), NIM_NIL};\n" +
                    "static const SmallString TM__1_1 = {((NU) 7450754115369591050ULL), " +
                    "((LongString*) (uintptr_t)6973800)};\n" +
                    "static const struct {\n\tNI rc;\n\tNI fullLen;\n\tNI capImpl;\n\tNIM_CHAR data[18];\n} " +
                    "TM__1_3 = {17, 1, 0, \"abcdefghijklmnopq\"};\n" +
                    "static const SmallString TM__1_2 = {((NU) 7450754115369591294ULL), ((LongString*) (&TM__1_3))};\n" +
                    "static const SmallString TM__1_4 = {((NU) 7450754115369591294ULL), ((LongString*) (&TM__1_3))};\n"),
             string("v3 data"))
    with var:
        bv3 = newBuilder(string(""))
    _genStringLiteralV3Const(m3, PNode(kind=TNodeKind.nkStrLit, strVal=string("abcdefghijklmnopq")), True, bv3)
    doAssert(bv3.extract() == string("{((NU) 7450754115369591294ULL), ((LongString*) (&TM__1_5))}"), string("v3 const"))

    # 4. C char literals
    doAssert(_ssoCharLit(ch("a")) + _ssoCharLit(ch("'")) + _ssoCharLit(ch("\n")) + _ssoCharLit(ch("\x01")) ==
             string("'a''\\'''\\n''\\x01'"), string("ssoCharLit"))
    echo(string("All ccgliterals tests passed successfully!"))

    echo(string("Testing ccgreset..."))
    with var:
        rm = newModuleForTest(newConfigRef())
        rp = newProcForTest(rm)
        tNI = PType(kind=TTypeKind.tyInt, name=string("NI"))
        tStr = PType(kind=TTypeKind.tyString, name=string("NimStringV2"))

    # 1. scalars -> 0, pointers -> NIM_NIL, strings/refs/seqs -> unsureAsgnRef
    for k in [TTypeKind.tyInt, TTypeKind.tyBool, TTypeKind.tyChar, TTypeKind.tyEnum, TTypeKind.tyFloat64,
              TTypeKind.tyUInt32]:
        doAssert(resetCode(rp, PType(kind=k)) == string("x = 0;\n"), string("scalar"))
    for k in [TTypeKind.tyPtr, TTypeKind.tyPointer, TTypeKind.tyCstring, TTypeKind.tyVar, TTypeKind.tyLent]:
        doAssert(resetCode(rp, PType(kind=k)) == string("x = NIM_NIL;\n"), string("pointer"))
    doAssert(resetCode(rp, tStr) == string("unsureAsgnRef(((void**) (&x)), NIM_NIL);\n"), string("string"))

    # 2. procs: closures reset environment and proc pointer
    doAssert(resetCode(rp, PType(kind=TTypeKind.tyProc, callConvImpl=TCallingConvention.ccClosure)) ==
             string("unsureAsgnRef(((void**) (&x.ClE_0)), NIM_NIL);\nx.ClP_0 = NIM_NIL;\n"), string("closure"))
    doAssert(resetCode(rp, PType(kind=TTypeKind.tyProc)) == string("x = NIM_NIL;\n"), string("nimcall proc"))

    # 3. modifiers are skipped; void and type classes generate nothing
    doAssert(resetCode(rp, PType(kind=TTypeKind.tyDistinct, sonsImpl=seq[PType]([tNI]))) == string("x = 0;\n"),
             string("distinct"))
    doAssert(resetCode(rp, PType(kind=TTypeKind.tyVoid)) == string(""), string("void"))

    # 4. tuples: one reset per field
    doAssert(resetCode(rp, PType(kind=TTypeKind.tyTuple, sonsImpl=seq[PType]([tNI, tStr]))) ==
             string("x.Field0 = 0;\nunsureAsgnRef(((void**) (&x.Field1)), NIM_NIL);\n"), string("tuple"))

    # 5. arrays: a loop over a temporary declared in the locals section
    with var:
        idx = PType(kind=TTypeKind.tyRange, n=PNode(sons=seq[PNode]([PNode(intVal=int64(0)), PNode(intVal=int64(4))])))
    doAssert(resetCode(rp, PType(kind=TTypeKind.tyArray, sonsImpl=seq[PType]([idx, tNI]))) ==
             string("for (T1_ = 0; T1_ < 5; T1_++) {\n\tx[T1_] = 0;\n}\n"), string("array"))
    doAssert(rp.sections[TCProcSection.cpsLocals].extract() == string("NI T1_;\n"), string("array temp"))

    # 6. sets: by size, an integer or a zeroed array
    doAssert(resetCode(rp, PType(kind=TTypeKind.tySet, sizeImpl=int64(4))) == string("x = 0;\n"), string("int set"))
    doAssert(resetCode(rp, PType(kind=TTypeKind.tySet, name=string("tySet_x"), sizeImpl=int64(32))) ==
             string("nimZeroMem(x, sizeof(tySet_x));\n"), string("array set"))

    # 7. objects (son 0: the base class or nil): base class through Sup, fields, imported structs with nimZeroMem
    with var:
        noBase = seq[PType]()
    noBase.add(None)
    with var:
        base = PType(kind=TTypeKind.tyObject, sonsImpl=noBase, n=PNode(kind=TNodeKind.nkRecList,
                     sons=seq[PNode]([fieldNode(string("b"), tNI)])))
        derived = PType(kind=TTypeKind.tyObject, sonsImpl=seq[PType]([base]),
                        n=PNode(kind=TNodeKind.nkRecList, sons=seq[PNode]([fieldNode(string("s"), tStr)])))
    doAssert(resetCode(rp, derived) == string("x.Sup.b = 0;\nunsureAsgnRef(((void**) (&x.s)), NIM_NIL);\n"),
             string("object"))
    with var:
        imported = PType(kind=TTypeKind.tyObject, name=string("struct stat"), sonsImpl=noBase, sym=PSym(flags=Tset[TSymFlag]({TSymFlag.sfImportc})),
                         n=PNode(kind=TNodeKind.nkRecList))
    doAssert(resetCode(rp, imported) == string("nimZeroMem(((void**) (&x)), sizeof(struct stat));\n"),
             string("importc object"))

    # 8. case objects: a switch over the discriminator, then the discriminator
    with var:
        recCase = PNode(kind=TNodeKind.nkRecCase, sons=seq[PNode]([
            fieldNode(string("kind"), PType(kind=TTypeKind.tyEnum)),
            PNode(kind=TNodeKind.nkOfBranch, sons=seq[PNode]([PNode(kind=TNodeKind.nkIntLit, intVal=int64(1)),
                                                             fieldNode(string("s"), tStr)])),
            PNode(kind=TNodeKind.nkElse, sons=seq[PNode]([fieldNode(string("i"), tNI)]))]))
    doAssert(resetCode(rp, PType(kind=TTypeKind.tyObject, sonsImpl=noBase, n=recCase)) ==
             string("switch (x.kind) {\ncase 1:\n\tunsureAsgnRef(((void**) (&x.s)), NIM_NIL);\n\tbreak;\n\n" +
                    "default:\n\tx.i = 0;\n\tbreak;\n\n}\nx.kind = 0;\n"), string("case object"))
    echo(string("All ccgreset tests passed successfully!"))

    echo(string("Testing ccgtrav..."))
    with var:
        tm = newModuleForTest(newConfigRef())
        tp = newProcForTest(tm)
        tc = _TTraversalClosure(_p=tp, _visitorFrmt=string("op"))
        tRef = PType(kind=TTypeKind.tyRef, name=string("tyRef_x"))
        tSeq = PType(kind=TTypeKind.tySequence, name=string("tySequence_x"), sonsImpl=seq[PType]([tRef]))

    # 1. GC'ed locations are visited; value types, `=` strings and nimcall procs are not
    doAssert(traverseCode(tc, tRef) == string("nimGCvisit(((void*) x), op);\n"), string("ref"))
    doAssert(traverseCode(tc, tSeq) == string("nimGCvisit(((void*) x), op);\n"), string("seq"))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyString)) == string("nimGCvisit(((void*) x), op);\n"),
             string("string"))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyString, flags=Tset[TTypeFlag]({TTypeFlag.tfHasAsgn}))) ==
             string(""), string("string with ="))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyInt)) == string(""), string("int"))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyProc, callConvImpl=TCallingConvention.ccClosure)) ==
             string("nimGCvisit(((void*) x.ClE_0), op);\n"), string("closure"))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyProc)) == string(""), string("nimcall proc"))

    # 2. seqs with destructors: only their GC'ed data is visited
    tm.config.globalOptions.incl(TGlobalOption.optSeqDestructors)
    doAssert(traverseCode(tc, tSeq) == string("nimGCvisitSeq(((void*) x), op);\n"), string("seq data"))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tySequence, sonsImpl=seq[PType]([PType(kind=TTypeKind.tyInt)]))) ==
             string(""), string("seq of int"))
    tm.config.globalOptions.excl(TGlobalOption.optSeqDestructors)

    # 3. arrays: the loop is kept only when its body visits something
    with var:
        idx4 = PType(kind=TTypeKind.tyRange, n=PNode(sons=seq[PNode]([PNode(intVal=int64(0)), PNode(intVal=int64(3))])))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyArray, sonsImpl=seq[PType]([idx4, PType(kind=TTypeKind.tyInt)]))) ==
             string(""), string("array of int"))
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyArray, sonsImpl=seq[PType]([idx4, tRef]))) ==
             string("for (T2_ = 0; T2_ < 4; T2_++) {\n\tnimGCvisit(((void*) x[T2_]), op);\n}\n"), string("array of ref"))

    # 4. tuples, objects (base class through Sup), case objects
    doAssert(traverseCode(tc, PType(kind=TTypeKind.tyTuple, sonsImpl=seq[PType]([PType(kind=TTypeKind.tyInt), tRef]))) ==
             string("nimGCvisit(((void*) x.Field1), op);\n"), string("tuple"))
    with var:
        noBaseT = seq[PType]()
    noBaseT.add(None)
    with var:
        baseT = PType(kind=TTypeKind.tyObject, sonsImpl=noBaseT, n=PNode(kind=TNodeKind.nkRecList,
                      sons=seq[PNode]([fieldNode(string("r"), tRef)])))
        objT = PType(kind=TTypeKind.tyObject, sonsImpl=seq[PType]([baseT]), n=PNode(kind=TNodeKind.nkRecCase,
                     sons=seq[PNode]([fieldNode(string("k"), PType(kind=TTypeKind.tyEnum)),
                                      PNode(kind=TNodeKind.nkOfBranch, sons=seq[PNode]([
                                          PNode(kind=TNodeKind.nkIntLit, intVal=int64(0)), fieldNode(string("s"), tSeq)])),
                                      PNode(kind=TNodeKind.nkElse, sons=seq[PNode]([
                                          fieldNode(string("i"), PType(kind=TTypeKind.tyInt))]))])))
    doAssert(traverseCode(tc, objT) == string("nimGCvisit(((void*) x.Sup.r), op);\nswitch (x.k) {\ncase 0:\n" +
                                              "\tnimGCvisit(((void*) x.s), op);\n\tbreak;\n\ndefault:\n\tbreak;\n\n}\n"),
             string("object"))

    # 5. marker procs of a ref type (one param `p`, deref'ed) and of a seq type (a loop over the data)
    with var:
        tmm = newModuleForTest(newConfigRef())
        refObj = PType(kind=TTypeKind.tyRef, name=string("tyRef_o"), sonsImpl=seq[PType]([baseT]))
    doAssert(_genTraverseProc(tmm, refObj, SigHash(digest=string("H1"))) == string("Marker_tyRef_oH1"), string("marker name"))
    doAssert(tmm.s[TCFileSection.cfsProcHeaders].extract() ==
             string("static N_NIMCALL(void, Marker_tyRef_oH1)(void* p, NI op);\n"), string("marker proto"))
    doAssert(tmm.s[TCFileSection.cfsProcs].extract() ==
             string("static N_NIMCALL(void, Marker_tyRef_oH1)(void* p, NI op) {\n\ttyRef_o a;\n" +
                    "a = ((tyRef_o) p);\nnimGCvisit(((void*) (*a).r), op);\n}\n\n"), string("marker proc"))
    with var:
        tms = newModuleForTest(newConfigRef())
    _ = _genTraverseProc(tms, tSeq, SigHash(digest=string("H2")))
    doAssert(tms.s[TCFileSection.cfsProcs].extract() ==
             string("static N_NIMCALL(void, Marker_tySequence_xH2)(void* p, NI op) {\n\ttySequence_x a;\nNI T1_;\n" +
                    "a = ((tySequence_x) p);\nfor (T1_ = 0; T1_ < (a ? a->Sup.len : 0); T1_++) {\n" +
                    "\tnimGCvisit(((void*) a->data[T1_]), op);\n}\n}\n\n"), string("seq marker proc"))

    # 6. traversal proc of a global
    with var:
        tmg = newModuleForTest(newConfigRef())
        g = PSym(loc=TLoc(snippet=string("gx"), t=tRef))
    doAssert(_genTraverseProcForGlobal(tmg, g, unknownLineInfo) == string("TM__1_0"), string("global proc name"))
    doAssert(tmg.s[TCFileSection.cfsProcs].extract() ==
             string("static N_NIMCALL(void, TM__1_0)(void) {\n\tnimGCvisit(((void*) gx), 0);\n}\n\n"),
             string("global proc"))
    echo(string("All ccgtrav tests passed successfully!"))

    echo(string("Testing inliner..."))
    with var:
        inlIdgen = IdGenerator(symId=int32(100))
        caller = inlSym(1, TSymKind.skProc, string("caller"))

    # 1. copySymdef: atoms unchanged; a symbol is cloned, owned by the new owner and recorded
    with var:
        locals1 = initTable[nint, PSym]()
        identNode = newNode(TNodeKind.nkIdent)
        intLitNode = newNode(TNodeKind.nkIntLit)
    doAssert(_copySymdef(identNode, locals1, inlIdgen, caller) == identNode)
    doAssert(_copySymdef(intLitNode, locals1, inlIdgen, caller) == intLitNode)
    with var:
        varSym = inlSym(10, TSymKind.skVar, string("myLocal"))
        symNode = newSymNode(varSym)
    with let:
        cloned = _copySymdef(symNode, locals1, inlIdgen, caller)
    doAssert(cloned.kind == TNodeKind.nkSym and cloned.sym.id == 101 and cloned.sym.name == string("myLocal"))
    doAssert(cloned.sym.owner == caller and locals1[nint(10)] == cloned.sym)
    with var:
        callNode = inlTree(TNodeKind.nkCall, seq[PNode]([newSymNode(inlSym(110, TSymKind.skVar, string("c1"))),
                                                          intLitNode]))
    with let:
        copiedCall = _copySymdef(callNode, locals1, inlIdgen, caller)
    doAssert(copiedCall.len == 2 and copiedCall[0].sym.id != 110 and copiedCall[1] == intLitNode)

    # 2. copyInlineProcBody: symbols of locals are replaced, others kept
    with var:
        locals2 = initTable[nint, PSym]()
        clonedVar = inlSym(201, TSymKind.skVar, string("clonedVar"))
    locals2[nint(10)] = clonedVar
    doAssert(_copyInlineProcBody(symNode, locals2, inlIdgen, caller).sym == clonedVar)
    with var:
        globalNode = newSymNode(inlSym(99, TSymKind.skVar, string("globalVar")))
    doAssert(_copyInlineProcBody(globalNode, locals2, inlIdgen, caller) == globalNode)

    # 3. var/let sections: identDefs, constDef, varTuple clone their symbols; comments are kept
    with var:
        locals3 = initTable[nint, PSym]()
        identDefs = inlTree(TNodeKind.nkIdentDefs, seq[PNode]([newSymNode(inlSym(20, TSymKind.skVar, string("x"))),
                            newNode(TNodeKind.nkEmpty), newNode(TNodeKind.nkIntLit)]))
        commentNode = newNode(TNodeKind.nkCommentStmt)
        varTuple = inlTree(TNodeKind.nkVarTuple, seq[PNode]([newSymNode(inlSym(82, TSymKind.skLet, string("t1"))),
                           newSymNode(inlSym(83, TSymKind.skLet, string("t2"))), newNode(TNodeKind.nkEmpty),
                           newNode(TNodeKind.nkCall)]))
    with let:
        varSection = _copyInlineProcBody(inlTree(TNodeKind.nkVarSection, seq[PNode]([identDefs])), locals3, inlIdgen, caller)
        letSection = _copyInlineProcBody(inlTree(TNodeKind.nkLetSection, seq[PNode]([commentNode, varTuple])),
                                        locals3, inlIdgen, caller)
    doAssert(varSection[0].kind == TNodeKind.nkIdentDefs and varSection[0][0].sym.id != 20)
    doAssert(locals3[nint(20)] == varSection[0][0].sym)
    doAssert(letSection[0] == commentNode and letSection[1][0].sym.owner == caller)
    doAssert(locals3.hasKey(nint(82)) and locals3.hasKey(nint(83)))

    # 4. for loops clone their variables; routines and type sections are not copied
    with var:
        locals4 = initTable[nint, PSym]()
        forStmt = inlTree(TNodeKind.nkForStmt, seq[PNode]([newSymNode(inlSym(30, TSymKind.skForVar, string("i"))),
                          newNode(TNodeKind.nkCall), newNode(TNodeKind.nkStmtList)]))
    with let:
        copiedFor = _copyInlineProcBody(forStmt, locals4, inlIdgen, caller)
    doAssert(copiedFor[0].sym.id != 30 and locals4[nint(30)] == copiedFor[0].sym)
    for k in [TNodeKind.nkProcDef, TNodeKind.nkTemplateDef, TNodeKind.nkTypeSection, TNodeKind.nkConstSection,
              TNodeKind.nkMixinStmt]:
        with let:
            n = newNode(k)
        doAssert(_copyInlineProcBody(n, locals4, inlIdgen, caller) == n)

    # 5. copyParams: parameters are cloned and added to the owner's proc type
    with var:
        locals5 = initTable[nint, PSym]()
        owner5 = inlSym(120, TSymKind.skProc, string("multiParamProc"))
    owner5.typ = inlProcType()
    with var:
        multiDefs = inlTree(TNodeKind.nkIdentDefs, seq[PNode]([newSymNode(inlSym(121, TSymKind.skParam, string("p1"))),
                            newSymNode(inlSym(122, TSymKind.skParam, string("p2"))), newNode(TNodeKind.nkIdent),
                            newNode(TNodeKind.nkEmpty)]))
        retNode = newNode(TNodeKind.nkEmpty)
    with let:
        params = _copyParams(inlTree(TNodeKind.nkFormalParams, seq[PNode]([retNode, multiDefs])), locals5, inlIdgen, owner5)
    doAssert(params[0] == retNode and params[1][0].sym.id != 121 and params[1][1].sym.id != 122)
    doAssert(locals5[nint(121)].owner == owner5 and locals5[nint(122)].owner == owner5)
    doAssert(owner5.typ.n.len == 3 and owner5.typ.len == 1)  # proc types keep parameters in n
    doAssert(params[1][1].sym.position == 1)

    # 6. copyInlineProc: a new proc whose result and parameters are its own
    with var:
        origProc = inlSym(70, TSymKind.skProc, string("inlineCandidate"))
        origParam = inlSym(71, TSymKind.skParam, string("x"))
        resultSym = inlSym(72, TSymKind.skResult, string("result"))
        astSons = seq[PNode]()
    origProc.typ = inlProcType()
    origProc.typ.n.add(newSymNode(origParam))
    for k in range(8):
        astSons.add(newNode(TNodeKind.nkEmpty))
    astSons[paramsPos] = newNode(TNodeKind.nkFormalParams)
    astSons[resultPos] = newSymNode(resultSym)
    astSons[bodyPos] = inlTree(TNodeKind.nkStmtList, seq[PNode]([inlTree(TNodeKind.nkAsgn, seq[PNode]([
        newSymNode(resultSym), newSymNode(origParam)]))]))
    origProc.ast = inlTree(TNodeKind.nkProcDef, astSons)
    with let:
        clonedProc = _copyInlineProc(origProc, inlIdgen)
        asgn = clonedProc.ast[bodyPos][0]
    doAssert(clonedProc.id != origProc.id and clonedProc.ast.len == 8)
    doAssert(clonedProc.ast[resultPos].sym.id != 72 and clonedProc.ast[resultPos].sym.owner == clonedProc)
    doAssert(asgn[0].sym == clonedProc.ast[resultPos].sym)
    doAssert(asgn[1].sym.id != 71 and asgn[1].sym.owner == clonedProc)
    doAssert(clonedProc.typ.n.len == 2 and clonedProc.typ.n[1].sym == asgn[1].sym)
    echo(string("All inliner tests passed successfully!"))

    echo(string("Testing ccgthreadvars..."))
    with var:
        emulated = newConfigRef()
        native = newConfigRef()
    emulated.globalOptions.incl(TGlobalOption.optThreads)
    emulated.globalOptions.incl(TGlobalOption.optTlsEmulation)
    native.globalOptions.incl(TGlobalOption.optThreads)  # threads:on, Nim 2's default
    native.globalOptions.excl(TGlobalOption.optTlsEmulation)

    # 1. emulatedThreadVars
    doAssert(_emulatedThreadVars(emulated), string("emulated"))
    doAssert(not _emulatedThreadVars(native), string("native"))

    # 2. accessThreadLocalVar: first access declares NimTV_, later accesses don't
    with var:
        m = newModuleForTest(emulated)
        p = newProcForTest(m)
        sym = PSym(id=1)
    _accessThreadLocalVar(p, sym)
    doAssert(TCProcFlag.threadVarAccessed in p.flags, string("proc flag"))
    doAssert(CodegenFlag.usesThreadVars in m.flags, string("module flag"))
    doAssert(p.procSec(TCProcSection.cpsLocals).extract() == string("NimThreadVars* NimTV_;\n"), string("NimTV_ decl"))
    doAssert(p.procSec(TCProcSection.cpsInit).extract() == string("NimTV_ = ((NimThreadVars*) GetThreadLocalVars());\n"),
             string("NimTV_ init"))
    _accessThreadLocalVar(p, sym)
    doAssert(p.procSec(TCProcSection.cpsLocals).extract() == string("NimThreadVars* NimTV_;\n"), string("idempotent"))

    # 3. declareThreadVar: emulated -> field of NimThreadVars (once per symbol); native -> threadvar
    with var:
        tInt = PType(id=1, name=string("NI"))
        v1 = PSym(id=10, loc=TLoc(snippet=string("tv1"), t=tInt))
    _declareThreadVar(m, v1, False)
    _declareThreadVar(m, v1, False)
    doAssert(m.g.nimtv.extract() == string("\tNI tv1;\n"), string("emulated field"))
    doAssert(len(m.g.nimtvDeps) == 1, string("deps"))
    with var:
        mn = newModuleForTest(native)
        v2 = PSym(id=11, typ=tInt, loc=TLoc(snippet=string("tv2"), t=tInt))
    _declareThreadVar(mn, v2, True)
    doAssert(mn.s[TCFileSection.cfsVars].extract() == string("extern NIM_THREADVAR NI tv2;\n"), string("native extern"))

    # 4. generateThreadLocalStorage: typedef struct of the gathered fields
    _generateThreadLocalStorage(m)
    doAssert(m.s[TCFileSection.cfsSeqTypes].extract() == string("typedef struct {\n\tNI tv1;\n} NimThreadVars;\n"),
             string("NimThreadVars typedef"))

    # 5. generateThreadVarsSize: NimThreadVarsSize proc, extern "C" for C++
    _generateThreadVarsSize(m)
    doAssert(m.s[TCFileSection.cfsProcs].extract() ==
             string("NI NimThreadVarsSize(void) {\n\treturn ((NI) sizeof(NimThreadVars));\n}\n\n"), string("size proc"))
    m.g.config.backend = TBackend.backendCpp
    m.s[TCFileSection.cfsProcs] = newBuilder(string(""))
    _generateThreadVarsSize(m)
    doAssert(m.s[TCFileSection.cfsProcs].extract().startsWith(string("NIM_EXTERNC NI")), string("extern C"))
    echo(string("All ccgthreadvars tests passed successfully!"))

    echo(string("Testing cbuilderdecls..."))
    # 1. variables, arrays, typedefs
    with var:
        dcD = newBuilder(string(""))
    dcD._addVar(kind=_VarKind.Global, name=string("g"), typ=string("NI"), initializer=string("1"))
    dcD._addArrayVar(kind=_VarKind.Const, name=string("arr"), elementType=string("NU8"), len=3)
    with dcD._addArrayVarWithInitializer(kind=_VarKind.AlwaysConst, name=string("t"), elementType=string("NI"), len=2):
        dcD.add(string("{1, 2}"))
    with dcD._addVarWithType(kind=_VarKind.Local, name=string("v")):
        dcD.add(string("NF"))
    with dcD._addTypedef(name=string("T")):
        dcD.add(string("NI32"))
    with dcD._addArrayTypedef(name=string("A"), len=BiggestInt(4)):
        dcD.add(string("NI"))
    dcD._addProcTypedef(TCallingConvention.ccCDecl, string("P"), string("void"), string("(void)"))
    dcD._addInclude(string("<stdio.h>"))
    doAssert(dcD.extract() == string("static NI g = 1;\nstatic NIM_CONST NU8 arr[3];\nstatic const NI t[2] = {1, 2};\n"
                                  "NF v;\ntypedef NI32 T;\ntypedef NI A[4];\ntypedef N_CDECL_PTR(void, P)(void);\n"
                                  "#include <stdio.h>\n"), string("decls: ") + dcD.extract())

    # 2. struct initializers and fields
    with var:
        dcSi = newBuilder(string(""))
        dcConstr = _StructInitializer()
    with dcSi._addStructInitializer(dcConstr, kind=_StructInitializerKind.siNamedStruct):
        with dcSi._addField(dcConstr, name=string("a")):
            dcSi.add(string("1"))
        with dcSi._addField(dcConstr, name=string("")):
            dcSi.add(string("2"))
    doAssert(dcSi.extract() == string("{.a = 1, 2}"), string("named initializer: ") + dcSi.extract())
    with var:
        dcFb = newBuilder(string(""))
        dcFsym = PSym(id=20, alignment=16, bitsize=3, flags=Tset[TSymFlag]({TSymFlag.sfNoalias}))
    dcFb._addField(dcFsym, name=string("f"), typ=string("NI"))
    dcFb._addArrayField(name=string("buf"), elementType=string("char"), len=8)
    dcFb._addProcField(TCallingConvention.ccNimCall, string("cb"), string("void"), string("(void)"))
    doAssert(dcFb.extract() == string("\tNIM_ALIGN(16) NI NIM_NOALIAS f:3;\n\tchar buf[8];\nN_NIMCALL_PTR(void, cb)(void);\n"),
             string("fields: ") + dcFb.extract())

    # 3. structs from Nim types: RTTI field, packed, base class, empty
    with var:
        dcSm = newModuleForTest(newConfigRef())
        dcSb = newBuilder(string(""))
        dcObjT = PType(id=30, kind=TTypeKind.tyObject, sonsImpl=seq[PType]([None]))
    dcSm.config.cCompiler = TSystemCC.ccGcc
    dcSm.config.globalOptions.incl(TGlobalOption.optTinyRtti)
    with dcSb._addStruct(dcSm, dcObjT, string("Obj"), string("")):
        dcSb._addField(name=string("x"), typ=string("NI"))
    dcObjT.flags.incl(TTypeFlag.tfPacked)
    dcObjT.flags.incl(TTypeFlag.tfFinal)
    with dcSb._addStruct(dcSm, dcObjT, string("Packed"), string("")):
        discard
    with var:
        dcSub = PType(id=31, kind=TTypeKind.tyObject, sonsImpl=seq[PType]([dcObjT]))
    with dcSb._addStruct(dcSm, dcSub, string("Sub"), string("Obj")):
        discard
    doAssert(dcSb.extract() == string("struct Obj {\n\tTNimTypeV2* m_type;\n\tNI x;\n};\n"
                                   "struct __attribute__((__packed__)) Packed {\n\tchar dummy;\n};\n"
                                   "struct Sub {\n\tObj Sup;\n};\n"), string("structs: ") + dcSb.extract())
    dcSm.config.cCompiler = TSystemCC.ccVcc
    with var:
        dcVb = newBuilder(string(""))
    with dcVb._addStruct(dcSm, dcObjT, string("P2"), string("")):
        with dcVb._addFieldWithStructType(dcSm, dcObjT, string("inner")):
            dcVb._addField(name=string("y"), typ=string("NI"))
        with dcVb._addAnonUnion():
            dcVb._addField(name=string("u"), typ=string("NI"))
    with dcVb._addSimpleStruct(dcSm, string(""), string("")):
        discard
    doAssert(dcVb.extract() == string("#pragma pack(push, 1)\nstruct P2 {\n\t#pragma pack(push, 1)\nstruct {\tNI y;\n} inner;\n"
                                   "#pragma pack(pop)\nunion{\n\tNI u;\n};\n};\n#pragma pack(pop)\n"
                                   "struct {\n\tchar dummy;\n}"), string("packed vcc: ") + dcVb.extract())

    # 4. proc dcParams and headers
    with var:
        dcPb = newBuilder(string(""))
        dcParams = _ProcParamBuilder()
        dcNoaliasParam = PSym(id=40, flags=Tset[TSymFlag]({TSymFlag.sfNoalias}), loc=TLoc(snippet=string("p")))
    with dcPb._addProcParams(dcParams):
        dcPb._addParam(dcParams, name=string("a"), typ=string("NI"))
        dcPb._addParam(dcParams, dcNoaliasParam, typ=string("NI*"))
        dcPb._addUnnamedParam(dcParams, string("NF"))
        dcPb._addProcTypedParam(dcParams, TCallingConvention.ccNimCall, string("f"), string("void"), string("(void)"))
        dcPb._addVarargsParam(dcParams)
    doAssert(dcPb.extract() == string("(NI a, NI* NIM_NOALIAS p, NF, N_NIMCALL_PTR(void, f)(void), ...)"),
             string("dcParams: ") + dcPb.extract())
    doAssert(_cProcParams() == string("(void)"), string("cProcParams()"))
    doAssert(_cProcParams(_SimpleProcParam(name=string("x"), typ=string("NI")), _SimpleProcParam(name=string(""), typ=string("NF")))
             == string("(NI x, NF)"), string("cProcParams"))
    with var:
        dcHb = newBuilder(string(""))
        dcPrcType = PType(id=50, kind=TTypeKind.tyProc, callConvImpl=TCallingConvention.ccNoInline)
        dcPrc = PSym(id=51, typ=dcPrcType, flags=Tset[TSymFlag]({TSymFlag.sfPure, TSymFlag.sfNoReturn}))
    dcSm.config.exc = ExceptionSystem.excSetjmp
    dcHb._addProcHeader(TCallingConvention.ccCDecl, string("f"), string("void"), string("(void)"))
    dcHb._finishProcHeaderAsProto()
    dcHb._addProcHeader(string("init"), string("void"), string("(void)"), isConstructor=True)
    dcHb._finishProcHeaderAsProto()
    dcHb._addProcHeader(dcSm, dcPrc, string("g"), string("(void)"), string("void"), True)
    dcHb._finishProcHeaderAsProto()
    dcSm.config.cCompiler = TSystemCC.ccGcc
    dcHb._addProcHeader(dcSm, dcPrc, string("h"), string("(void)"), string("void"), True)
    with dcHb._finishProcHeaderWithBody():
        dcHb.addLineEnd(string("return;"))
    doAssert(dcHb.extract() == string("N_CDECL(void, f)(void);\nvoid __attribute__((constructor)) init(void);\n"
                                   "__declspec(naked) __declspec(noreturn) N_NOINLINE(void, g)(void);\n"
                                   "N_NOINLINE(void, h)(void) __attribute__((naked)) __attribute__((noreturn)) {\n"
                                   "\treturn;\n}\n\n"), string("headers: ") + dcHb.extract())
    with var:
        dcPv = newBuilder(string(""))
    dcPv._addProcVar(dcSm, dcPrc, string("pv1"), string("(void)"), string("void"), isStatic=True)
    dcPv._addProcVar(TCallingConvention.ccNimCall, string("pv2"), string("(NI)"), string("NI"), isVolatile=True)
    dcPv._addProcVar(string("pv3"), string("(void)"), string("void"), isStatic=True)
    doAssert(dcPv.extract() == string("static N_NOINLINE_PTR(void, pv1)(void) __attribute__((naked)) __attribute__((noreturn));\n"
                                   "N_NIMCALL_PTR(NI, volatile pv2)(NI);\nstatic void (*pv3)(void);\n"),
             string("proc vars: ") + dcPv.extract())

    # 5. variables from symbols: alignment, visibility, codegenDecl, register/volatile
    with var:
        dcVv = newBuilder(string(""))
        dcAlignedVar = PSym(id=60, kind=TSymKind.skVar, alignment=8,
                          flags=Tset[TSymFlag]({TSymFlag.sfRegister, TSymFlag.sfVolatile}))
        dcDeclVar = PSym(id=61, kind=TSymKind.skVar, flags=Tset[TSymFlag]({TSymFlag.sfCodegenDecl}),
                       constraint=PNode(kind=TNodeKind.nkStrLit, strVal=string("$1 __thread $2")))
    dcVv._addVar(dcSm, dcAlignedVar, name=string("a"), typ=string("NI"), kind=_VarKind.Global,
              visibility=_DeclVisibility.Private, initializer=string("0"))
    dcVv._addVar(dcSm, dcDeclVar, name=string("b"), typ=string("NI"), initializer=string("{}"),
              initializerKind=_VarInitializerKind.CppConstructor)
    with dcVv._addDeclWithVisibility(_DeclVisibility.ExternC):
        dcVv.addLineEnd(string("int c;"))
    doAssert(dcVv.extract() == string("NIM_ALIGN(8) N_LIB_PRIVATE static NI register volatile a = 0;\n"
                                   "NI __thread b{};\nNIM_EXTERNC int c;\n"), string("symbol vars: ") + dcVv.extract())

    # 6. initializer templates, union types, all struct initializer kinds
    with var:
        dc2B = newBuilder(string(""))
        dc2Init = _StructInitializer()
    with dc2B._addVarWithInitializer(kind=_VarKind.Local, name=string("v"), typ=string("NI")):
        dc2B.add(string("1"))
    with dc2B._addVarWithTypeAndInitializer(kind=_VarKind.Global, name=string("w")):
        dc2B.add(string("NF"))
        with do:
            dc2B.add(string("2.0"))
    with dc2B._addUnionType():
        dc2B._addField(name=string("u"), typ=string("NI"))
    dc2B.add(ch('\n'))
    for kind in [_StructInitializerKind.siArray, _StructInitializerKind.siOrderedStruct]:
        with dc2B._addStructInitializer(dc2Init, kind=kind):
            with dc2B._addField(dc2Init, name=string("a")):
                dc2B.add(string("1"))
            with dc2B._addField(dc2Init, name=string("b")):
                dc2B.add(string("2"))
        dc2B.add(ch(' '))
    with dc2B._addStructInitializer(dc2Init, kind=_StructInitializerKind.siWrapper):
        with dc2B._addField(dc2Init, name=string("x")):
            dc2B.add(string("x"))
    doAssert(dc2B.extract() == string("NI v = 1;\nstatic NF w = 2.0;\nunion{\n\tNI u;\n}\n{1, 2} {1, 2} x"),
             string("initializers: ") + dc2B.extract())

    # 7. simple struct with a base type (C: Sup field, C++: inheritance); RTTI field; flexible array dummy
    with var:
        dc2M = newModuleForTest(newConfigRef())
        dc2S = newBuilder(string(""))
        dc2Rtti = PType(id=70, kind=TTypeKind.tyObject, sonsImpl=seq[PType]([None]))
        dc2Flex = PType(id=71, kind=TTypeKind.tyObject, sonsImpl=seq[PType]([None]),
                        flags=Tset[TTypeFlag]({TTypeFlag.tfFinal}),
                        n=PNode(kind=TNodeKind.nkRecList, sons=seq[PNode]([
                            PNode(kind=TNodeKind.nkSym, sym=PSym(id=72, typ=PType(id=73, kind=TTypeKind.tyUncheckedArray)))])))
    dc2M.config.globalOptions.excl(TGlobalOption.optTinyRtti)
    with dc2S._addSimpleStruct(dc2M, string("S"), string("Base")):
        discard
    with dc2S._addStruct(dc2M, dc2Rtti, string("R"), string("")):
        discard
    with dc2S._addStruct(dc2M, dc2Flex, string("F"), string("")):
        dc2S._addField(name=string("data"), typ=string("NI"), isFlexArray=True)
    dc2M.config.backend = TBackend.backendCpp
    with dc2S._addSimpleStruct(dc2M, string("C"), string("Base")):
        discard
    doAssert(dc2S.extract() == string("struct S {\n\tBase Sup;\n};\nstruct R {\n\tTNimType* m_type;\n};\n"
                                      "struct F {\n\tchar dummy;\n\tNI data[SEQ_DECL_SIZE];\n};\n"
                                      "struct C : public Base {\n};\n"), string("structs 2: ") + dc2S.extract())

    # 8. a C++ non-POD thread variable
    with var:
        dc2V = newBuilder(string(""))
        dc2Pod = PType(id=74, name=string("NI"), sym=PSym(id=75, flags=Tset[TSymFlag]({TSymFlag.sfCppNonPod})))
        dc2Tl = PSym(id=76, kind=TSymKind.skVar, typ=dc2Pod)
    dc2M.config.globalOptions.incl(TGlobalOption.optThreads)
    dc2V._addVar(dc2M, dc2Tl, name=string("tl"), typ=string("NI"), kind=_VarKind.Threadvar)
    doAssert(dc2V.extract() == string("NIM_THREAD_LOCAL NI tl;\n"), string("thread local: ") + dc2V.extract())
    echo(string("All cbuilderdecls tests passed successfully!"))
