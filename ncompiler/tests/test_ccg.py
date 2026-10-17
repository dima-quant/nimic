# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.intsets import *
from nimic.std.strutils import startsWith
from ..options import *
from ..lineinfos import *
from ..msgs import *
from ..nodekinds import *
from ..ropes import *
from ..platform import *
from nimic.std.tables import *

# Test harness of the ccg* include files of cgen.nim. Like cgen.nim it provides their context
# (cgen_context, cbuilderdecls_subset, cgen_procs, cgen_stmts: stand-ins for modules not converted yet;
# the imports: converted) and includes them in cgen's order (ccgtrav is included by ccgtypes).
include("cgen_context")
include("../cbuilderexprs", "cbuilderdecls_subset", "../cbuilderstmts")
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
    specializeReset(p, TLoc(snippet=string("x"), t=t))
    return extract(p.sections[TCProcSection.cpsStmts])


def literalModule(gc: TGCMode, strings: StringsMode) -> BModule:
    ## a module of a 64-bit little endian target with the given GC and string implementation
    result = newModuleForTest(newConfigRef())
    result.config.selectedGC = gc
    result.config.selectedStrings = strings
    setTarget(result.config.target, TSystemOS.osLinux, TSystemCPU.cpuAmd64)
    return result


def strLit(m: BModule, s: string) -> string:
    ## genStringLiteral of a string literal node; returns the expression
    with var:
        b = newBuilder(string(""))
    genStringLiteral(m, PNode(kind=TNodeKind.nkStrLit, strVal=s), b)
    return extract(b)


def traverseCode(c: TTraversalClosure, t: PType) -> string:
    ## genTraverseProc of a location `x` of type t; returns the generated statements
    c.p.sections[TCProcSection.cpsStmts] = newBuilder(string(""))
    genTraverseProc(c, string("x"), t)
    return extract(c.p.sections[TCProcSection.cpsStmts])


def fieldNode(name: string, t: PType) -> PNode:
    return PNode(kind=TNodeKind.nkSym, sym=PSym(typ=t, loc=TLoc(snippet=name, t=t)))


if comptime(__name__ == "__main__"):
    echo(string("Testing ccgliterals..."))
    with var:
        m1 = literalModule(TGCMode.gcRefc, StringsMode.stringDefault)
        m2 = literalModule(TGCMode.gcOrc, StringsMode.stringDefault)
        m3 = literalModule(TGCMode.gcOrc, StringsMode.stringSso)
    doAssert(detectStrVersion(m1) == 1 and detectSeqVersion(m1) == 1, string("version 1"))
    doAssert(detectStrVersion(m2) == 2 and detectSeqVersion(m2) == 2, string("version 2"))
    doAssert(detectStrVersion(m3) == 3 and detectSeqVersion(m3) == 2, string("version 3"))
    # 1. version 1 (GC'ed strings): a TGenericSeq struct, cached per module
    doAssert(strLit(m1, string("ab")) == string("((NimStringDesc*) (&TM__1_0))"), string("v1 literal"))
    doAssert(strLit(m1, string("ab")) == string("((NimStringDesc*) (&TM__1_0))"), string("v1 cached"))
    doAssert(extract(m1.s[TCFileSection.cfsStrData]) ==
             string("static const struct {\n\tTGenericSeq Sup;\n\tNIM_CHAR data[3];\n} TM__1_0 = " +
                    "{{2, ((NI) (((NU) 2) | NIM_STRLIT_FLAG))}, \"ab\"};\n"), string("v1 data"))

    # 2. version 2 (destructor based): the payload is cached, each literal gets a NimStringV2
    doAssert(strLit(m2, string("ab")) == string("TM__1_1"), string("v2 literal"))
    doAssert(strLit(m2, string("ab")) == string("TM__1_2"), string("v2 second literal"))
    doAssert(extract(m2.s[TCFileSection.cfsStrData]) ==
             string("static const struct {\n\tNI cap;\n\tNIM_CHAR data[3];\n} TM__1_0 = {(2 | NIM_STRLIT_FLAG), \"ab\"};\n" +
                    "static const NimStringV2 TM__1_1 = {2, ((NimStrPayload*) (&TM__1_0))};\n" +
                    "static const NimStringV2 TM__1_2 = {2, ((NimStrPayload*) (&TM__1_0))};\n"), string("v2 data"))
    with var:
        bc = newBuilder(string(""))
    genStringLiteralV2Const(m2, PNode(kind=TNodeKind.nkStrLit, strVal=string("ab")), True, bc)
    doAssert(extract(bc) == string("{2, ((NimStrPayload*) (&TM__1_0))}"), string("v2 const"))
    with var:
        rd = Rope()
    genStringLiteralDataOnly(m2, string("xy"), unknownLineInfo, True, rd)
    doAssert(rd == string("TM__1_3"), string("v2 data only"))

    # 3. version 3 (SmallString): short and medium strings inline, long ones in a cached LongString
    doAssert(strLit(m3, string("ab")) == string("TM__1_0"), string("v3 short"))
    doAssert(strLit(m3, string("abcdefghij")) == string("TM__1_1"), string("v3 medium"))
    doAssert(strLit(m3, string("abcdefghijklmnopq")) == string("TM__1_2"), string("v3 long"))
    doAssert(strLit(m3, string("abcdefghijklmnopq")) == string("TM__1_4"), string("v3 long again"))
    doAssert(extract(m3.s[TCFileSection.cfsStrData]) ==
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
    genStringLiteralV3Const(m3, PNode(kind=TNodeKind.nkStrLit, strVal=string("abcdefghijklmnopq")), True, bv3)
    doAssert(extract(bv3) == string("{((NU) 7450754115369591294ULL), ((LongString*) (&TM__1_5))}"), string("v3 const"))

    # 4. C char literals
    doAssert(ssoCharLit(ch("a")) + ssoCharLit(ch("'")) + ssoCharLit(ch("\n")) + ssoCharLit(ch("\x01")) ==
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
    doAssert(extract(rp.sections[TCProcSection.cpsLocals]) == string("NI T1_;\n"), string("array temp"))

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
        tc = TTraversalClosure(p=tp, visitorFrmt=string("op"))
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
    doAssert(genTraverseProc(tmm, refObj, SigHash(digest=string("H1"))) == string("Marker_tyRef_oH1"), string("marker name"))
    doAssert(extract(tmm.s[TCFileSection.cfsProcHeaders]) ==
             string("static N_NIMCALL(void, Marker_tyRef_oH1)(void* p, NI op);\n"), string("marker proto"))
    doAssert(extract(tmm.s[TCFileSection.cfsProcs]) ==
             string("static N_NIMCALL(void, Marker_tyRef_oH1)(void* p, NI op) {\n\ttyRef_o a;\n" +
                    "a = ((tyRef_o) p);\nnimGCvisit(((void*) (*a).r), op);\n}\n\n"), string("marker proc"))
    with var:
        tms = newModuleForTest(newConfigRef())
    _ = genTraverseProc(tms, tSeq, SigHash(digest=string("H2")))
    doAssert(extract(tms.s[TCFileSection.cfsProcs]) ==
             string("static N_NIMCALL(void, Marker_tySequence_xH2)(void* p, NI op) {\n\ttySequence_x a;\nNI T1_;\n" +
                    "a = ((tySequence_x) p);\nfor (T1_ = 0; T1_ < (a ? a->Sup.len : 0); T1_++) {\n" +
                    "\tnimGCvisit(((void*) a->data[T1_]), op);\n}\n}\n\n"), string("seq marker proc"))

    # 6. traversal proc of a global
    with var:
        tmg = newModuleForTest(newConfigRef())
        g = PSym(loc=TLoc(snippet=string("gx"), t=tRef))
    doAssert(genTraverseProcForGlobal(tmg, g, unknownLineInfo) == string("TM__1_0"), string("global proc name"))
    doAssert(extract(tmg.s[TCFileSection.cfsProcs]) ==
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
    doAssert(copySymdef(identNode, locals1, inlIdgen, caller) == identNode)
    doAssert(copySymdef(intLitNode, locals1, inlIdgen, caller) == intLitNode)
    with var:
        varSym = inlSym(10, TSymKind.skVar, string("myLocal"))
        symNode = newSymNode(varSym)
    with let:
        cloned = copySymdef(symNode, locals1, inlIdgen, caller)
    doAssert(cloned.kind == TNodeKind.nkSym and cloned.sym.id == 101 and cloned.sym.name == string("myLocal"))
    doAssert(cloned.sym.owner == caller and locals1[nint(10)] == cloned.sym)
    with var:
        callNode = inlTree(TNodeKind.nkCall, seq[PNode]([newSymNode(inlSym(110, TSymKind.skVar, string("c1"))),
                                                          intLitNode]))
    with let:
        copiedCall = copySymdef(callNode, locals1, inlIdgen, caller)
    doAssert(copiedCall.len == 2 and copiedCall[0].sym.id != 110 and copiedCall[1] == intLitNode)

    # 2. copyInlineProcBody: symbols of locals are replaced, others kept
    with var:
        locals2 = initTable[nint, PSym]()
        clonedVar = inlSym(201, TSymKind.skVar, string("clonedVar"))
    locals2[nint(10)] = clonedVar
    doAssert(copyInlineProcBody(symNode, locals2, inlIdgen, caller).sym == clonedVar)
    with var:
        globalNode = newSymNode(inlSym(99, TSymKind.skVar, string("globalVar")))
    doAssert(copyInlineProcBody(globalNode, locals2, inlIdgen, caller) == globalNode)

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
        varSection = copyInlineProcBody(inlTree(TNodeKind.nkVarSection, seq[PNode]([identDefs])), locals3, inlIdgen, caller)
        letSection = copyInlineProcBody(inlTree(TNodeKind.nkLetSection, seq[PNode]([commentNode, varTuple])),
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
        copiedFor = copyInlineProcBody(forStmt, locals4, inlIdgen, caller)
    doAssert(copiedFor[0].sym.id != 30 and locals4[nint(30)] == copiedFor[0].sym)
    for k in [TNodeKind.nkProcDef, TNodeKind.nkTemplateDef, TNodeKind.nkTypeSection, TNodeKind.nkConstSection,
              TNodeKind.nkMixinStmt]:
        with let:
            n = newNode(k)
        doAssert(copyInlineProcBody(n, locals4, inlIdgen, caller) == n)

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
        params = copyParams(inlTree(TNodeKind.nkFormalParams, seq[PNode]([retNode, multiDefs])), locals5, inlIdgen, owner5)
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
        clonedProc = copyInlineProc(origProc, inlIdgen)
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
    native.globalOptions.excl(TGlobalOption.optTlsEmulation)

    # 1. emulatedThreadVars
    doAssert(emulatedThreadVars(emulated), string("emulated"))
    doAssert(not emulatedThreadVars(native), string("native"))

    # 2. accessThreadLocalVar: first access declares NimTV_, later accesses don't
    with var:
        m = newModuleForTest(emulated)
        p = newProcForTest(m)
        sym = PSym(id=1)
    accessThreadLocalVar(p, sym)
    doAssert(TCProcFlag.threadVarAccessed in p.flags, string("proc flag"))
    doAssert(CodegenFlag.usesThreadVars in m.flags, string("module flag"))
    doAssert(extract(p.procSec(TCProcSection.cpsLocals)) == string("NimThreadVars* NimTV_;\n"), string("NimTV_ decl"))
    doAssert(extract(p.procSec(TCProcSection.cpsInit)) == string("NimTV_ = ((NimThreadVars*) GetThreadLocalVars());\n"),
             string("NimTV_ init"))
    accessThreadLocalVar(p, sym)
    doAssert(extract(p.procSec(TCProcSection.cpsLocals)) == string("NimThreadVars* NimTV_;\n"), string("idempotent"))

    # 3. declareThreadVar: emulated -> field of NimThreadVars (once per symbol); native -> threadvar
    with var:
        tInt = PType(id=1, name=string("NI"))
        v1 = PSym(id=10, loc=TLoc(snippet=string("tv1"), t=tInt))
    declareThreadVar(m, v1, False)
    declareThreadVar(m, v1, False)
    doAssert(extract(m.g.nimtv) == string("\tNI tv1;\n"), string("emulated field"))
    doAssert(len(m.g.nimtvDeps) == 1, string("deps"))
    with var:
        mn = newModuleForTest(native)
        v2 = PSym(id=11, loc=TLoc(snippet=string("tv2"), t=tInt))
    declareThreadVar(mn, v2, True)
    doAssert(extract(mn.s[TCFileSection.cfsVars]) == string("extern NIM_THREADVAR NI tv2;\n"), string("native extern"))

    # 4. generateThreadLocalStorage: typedef struct of the gathered fields
    generateThreadLocalStorage(m)
    doAssert(extract(m.s[TCFileSection.cfsSeqTypes]) == string("typedef struct {\n\tNI tv1;\n} NimThreadVars;\n"),
             string("NimThreadVars typedef"))

    # 5. generateThreadVarsSize: NimThreadVarsSize proc, extern "C" for C++
    generateThreadVarsSize(m)
    doAssert(extract(m.s[TCFileSection.cfsProcs]) ==
             string("NI NimThreadVarsSize(void) {\n\treturn ((NI) sizeof(NimThreadVars));\n}\n\n"), string("size proc"))
    m.g.config.backend = TBackend.backendCpp
    m.s[TCFileSection.cfsProcs] = newBuilder(string(""))
    generateThreadVarsSize(m)
    doAssert(extract(m.s[TCFileSection.cfsProcs]).startsWith(string("NIM_EXTERNC NI")), string("extern C"))
    echo(string("All ccgthreadvars tests passed successfully!"))
