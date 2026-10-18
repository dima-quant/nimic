# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2018 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# included from cgen.nim (tests: ncompiler/tests/test_ccg.py)

## This include file contains the logic to produce constant string
## and seq literals. The code here is responsible that
## ``const x = ["a", "b"]`` works without hidden runtime creation code.
## The price is that seqs and strings are not purely a library
## implementation.

@template
def detectVersion(field: untyped, corename: untyped):
    if m.g.config.selectedGC in {TGCMode.gcArc, TGCMode.gcOrc, TGCMode.gcYrc, TGCMode.gcAtomicArc, TGCMode.gcHooks}:
        result = 2
    else:
        result = 1


@template_expand
def detectStrVersion(m: BModule) -> nint:
    if m.g.config.usesSso() and (
        m.g.config.selectedGC in {TGCMode.gcArc, TGCMode.gcOrc, TGCMode.gcYrc, TGCMode.gcAtomicArc, TGCMode.gcHooks}
    ):
        result = 3
    else:
        detectVersion(strVersion, "nimStrVersion")
    return result


@template_expand
def detectSeqVersion(m: BModule) -> nint:
    detectVersion(seqVersion, "nimSeqVersion")
    return result


# ----- Version 1: GC'ed strings and seqs --------------------------------

def genStringLiteralDataOnlyV1(m: BModule, s: string, result: mut@Rope) -> None:
    cgsym(m, string("TGenericSeq"))
    with let:
        tmp = getTempName(m)
    result.add(tmp)
    with var:
        res = newBuilder(string(""))
    with res.addVarWithTypeAndInitializer(VarKind.AlwaysConst, name=tmp):
        with res.addSimpleStruct(m, name=string(""), baseType=string("")):
            res.addField(name=string("Sup"), typ=string("TGenericSeq"))
            res.addArrayField(name=string("data"), elementType=NimChar, len=s.len + 1)
        with do:
            with var:
                strInit = StructInitializer()
            with res.addStructInitializer(strInit, kind=StructInitializerKind.siOrderedStruct):
                with res.addField(strInit, name=string("Sup")):
                    with var:
                        seqInit = StructInitializer()
                    with res.addStructInitializer(seqInit, kind=StructInitializerKind.siOrderedStruct):
                        with res.addField(seqInit, name=string("len")):
                            res.addIntValue(s.len)
                        with res.addField(seqInit, name=string("reserved")):
                            res.add(cCast(NimInt, cOp(TypedBinaryOp.BitOr, NimUint, cCast(NimUint, cIntValue(s.len)), NimStrlitFlag)))
                with res.addField(strInit, name=string("data")):
                    res.add(makeCString(s))
    m.s[TCFileSection.cfsStrData].add(res.extract())


def genStringLiteralV1(m: BModule, n: PNode, result: mut@Builder) -> None:
    if s is None:
        result.add(cCast(ptrType(cgsymValue(m, string("NimStringDesc"))), NimNil))
    else:
        with let:
            id = nodeTableTestOrSet(m.dataCache, n, m.labels)
        with var:
            name: string = string("")
        if id == m.labels:
            # string literal not found in the cache:
            genStringLiteralDataOnlyV1(m, n.strVal, name)
        else:
            name = m.tmpBase + string(str(id))
        result.add(cCast(ptrType(cgsymValue(m, string("NimStringDesc"))), cAddr(name)))


# ------ Version 2: destructor based strings and seqs -----------------------

def genStringLiteralDataOnlyV2(m: BModule, s: string, result: Rope, isConst: bool) -> None:
    with var:
        res = newBuilder(string(""))
    with res.addVarWithTypeAndInitializer(
        VarKind.AlwaysConst if isConst else VarKind.Global,
        name=result
    ):
        with res.addSimpleStruct(m, name=string(""), baseType=string("")):
            res.addField(name=string("cap"), typ=NimInt)
            res.addArrayField(name=string("data"), elementType=NimChar, len=s.len + 1)
        with do:
            with var:
                structInit = StructInitializer()
            with res.addStructInitializer(structInit, kind=StructInitializerKind.siOrderedStruct):
                with res.addField(structInit, name=string("cap")):
                    res.add(cOp(TypedBinaryOp.BitOr, NimInt, cIntValue(s.len), NimStrlitFlag))
                with res.addField(structInit, name=string("data")):
                    res.add(makeCString(s))
    m.s[TCFileSection.cfsStrData].add(res.extract())


def genStringLiteralV2(m: BModule, n: PNode, isConst: bool, result: mut@Builder) -> None:
    with let:
        id = nodeTableTestOrSet(m.dataCache, n, m.labels)
    with var:
        litName = string()
    if id == m.labels:
        cgsym(m, string("NimStrPayload"))
        cgsym(m, string("NimStringV2"))
        # string literal not found in the cache:
        litName = getTempName(m)
        genStringLiteralDataOnlyV2(m, n.strVal, litName, isConst)
    else:
        litName = m.tmpBase + string(str(id))
    with let:
        tmp = getTempName(m)
    result.add(tmp)
    with var:
        res = newBuilder(string(""))
    with res.addVarWithInitializer(
        VarKind.AlwaysConst if isConst else VarKind.Global,
        name=tmp,
        typ=string("NimStringV2")
    ):
        with var:
            strInit = StructInitializer()
        with res.addStructInitializer(strInit, kind=StructInitializerKind.siOrderedStruct):
            with res.addField(strInit, name=string("len")):
                res.addIntValue(n.strVal.len)
            with res.addField(strInit, name=string("p")):
                res.add(cCast(ptrType(string("NimStrPayload")), cAddr(litName)))
    m.s[TCFileSection.cfsStrData].add(res.extract())


def genStringLiteralV2Const(m: BModule, n: PNode, isConst: bool, result: mut@Builder) -> None:
    with let:
        id = nodeTableTestOrSet(m.dataCache, n, m.labels)
    with var:
        pureLit = Rope()
    if id == m.labels:
        pureLit = getTempName(m)
        cgsym(m, string("NimStrPayload"))
        cgsym(m, string("NimStringV2"))
        # string literal not found in the cache:
        genStringLiteralDataOnlyV2(m, n.strVal, pureLit, isConst)
    else:
        pureLit = m.tmpBase + rope(id)
    with var:
        strInit = StructInitializer()
    with result.addStructInitializer(strInit, kind=StructInitializerKind.siOrderedStruct):
        with result.addField(strInit, name=string("len")):
            result.addIntValue(n.strVal.len)
        with result.addField(strInit, name=string("p")):
            result.add(cCast(ptrType(string("NimStrPayload")), cAddr(pureLit)))


def ssoCharLit(ch: char) -> string:
    ## Return a C char literal for ch, with proper escaping.
    with const:
        hexDigits = string("0123456789abcdef")
    result = string("'")
    with let:
        c = ord(ch)
    if c == 39:  # '\''
        result.add(string(r"\'"))
    elif c == 92:  # '\\'
        result.add(string(r"\\"))
    elif c == 0:
        result.add(string(r"\0"))
    elif c == 10:  # '\n'
        result.add(string(r"\n"))
    elif c == 13:  # '\r'
        result.add(string(r"\r"))
    elif c == 9:  # '\t'
        result.add(string(r"\t"))
    elif c < 32 or c == 127:
        result.add(string(r"\x"))
        result.add(hexDigits[c >> 4])
        result.add(hexDigits[c & 0xF])
    else:
        result.add(ch)
    result.add(string("'"))
    return result


def ssoBytesLit(m: BModule, s: string, slen: nint) -> string:
    ## Compute the `bytes` field value for the new SmallString layout.
    ## byte 0 = slen, bytes 1-7 = inline chars 0-6 (zero-padded).
    ## On LE: slen in bits 0-7, char[i] in bits (i+1)*8..(i+1)*8+7.
    ## On BE: slen in bits 56-63, char[i] in bits (6-i)*8..(6-i)*8+7.
    with const:
        AlwaysAvail = 7
    with var:
        val: uint64 = uint64(0)
    if CPU[m.g.config.target.targetCPU].endian == Endianness.littleEndian:
        val = uint64(slen)
        for i in range(min(s.len, AlwaysAvail)):
            val = val | (uint64(ord(s[i])) << uint64((i + 1) * 8))
    else:
        val = uint64(slen) << uint64(56)
        for i in range(min(s.len, AlwaysAvail)):
            val = val | (uint64(ord(s[i])) << uint64((AlwaysAvail - 1 - i) * 8))
    # Cast to NU (C name for Nim's uint, = NU64 on 64-bit). NU64 = uint64_t.
    result = cCast(string("NU"), str(val) + string("ULL"))
    return result


def ssoMoreLit(m: BModule, s: string) -> string:
    ## For medium string literals (AlwaysAvail < len <= PayloadSize), encode
    ## chars[AlwaysAvail..ptrSize-1] in the 'more' pointer field bit-pattern.
    ## The last pointer byte is always '\0' (null terminator), guaranteed by
    ## PayloadSize = AlwaysAvail + ptrSize - 1.  slen <= PayloadSize guards
    ## prevent any code from dereferencing this as an actual pointer.
    with const:
        AlwaysAvail = 7
    with let:
        ptrSize = m.g.config.target.ptrSize
    with var:
        val: uint64 = uint64(0)
    for i in range(ptrSize):
        with let:
            ch_val: uint64 = uint64(ord(s[AlwaysAvail + i])) if AlwaysAvail + i < s.len else uint64(0)
        if CPU[m.g.config.target.targetCPU].endian == Endianness.littleEndian:
            val = val | (ch_val << uint64(i * 8))
        else:
            val = val | (ch_val << uint64((ptrSize - 1 - i) * 8))
    result = cCast(ptrType(string("LongString")), string("(uintptr_t)") + str(val))
    return result


def genStringLiteralV3Const(m: BModule, n: PNode, isConst: bool, result: mut@Builder) -> None:
    # Inline SmallString struct initializer for use inside const aggregate types.
    # Layout: {bytes: NimUint, more: ptr LongString}
    # bytes = slen (low byte) | char[0]<<8 | char[1]<<16 | ... | char[6]<<56
    with const:
        AlwaysAvail = 7
    with let:
        s = n.strVal

    cgsym(m, string("SmallString"))
    cgsym(m, string("LongString"))

    with let:
        payloadSize = AlwaysAvail + m.g.config.target.ptrSize - 1
    with var:
        si = StructInitializer()
    with result.addStructInitializer(si, kind=StructInitializerKind.siOrderedStruct):
        if s.len <= AlwaysAvail:
            with result.addField(si, name=string("bytes")):
                result.add(ssoBytesLit(m, s, s.len))
            with result.addField(si, name=string("more")):
                result.add(NimNil)
        elif s.len <= payloadSize:
            # Medium string: bytes holds slen + chars 0-6; more holds chars 7..PayloadSize-1.
            with result.addField(si, name=string("bytes")):
                result.add(ssoBytesLit(m, s, s.len))
            with result.addField(si, name=string("more")):
                result.add(ssoMoreLit(m, s))
        else:
            # Emit the LongString block into cfsStrData and reference it inline.
            with let:
                dataName = getTempName(m)
            with var:
                res = newBuilder(string(""))
            with res.addVarWithTypeAndInitializer(
                VarKind.AlwaysConst if isConst else VarKind.Global,
                name=dataName
            ):
                with res.addSimpleStruct(m, name=string(""), baseType=string("")):
                    res.addField(name=string("rc"), typ=NimInt)
                    res.addField(name=string("fullLen"), typ=NimInt)
                    res.addField(name=string("capImpl"), typ=NimInt)
                    res.addArrayField(name=string("data"), elementType=NimChar, len=s.len + 1)
                with do:
                    with var:
                        di = StructInitializer()
                    with res.addStructInitializer(di, kind=StructInitializerKind.siOrderedStruct):
                        with res.addField(di, name=string("fullLen")):
                            res.addIntValue(s.len)
                        with res.addField(di, name=string("rc")):
                            res.addIntValue(1)
                        with res.addField(di, name=string("capImpl")):
                            res.addIntValue(0)  # static, never freed
                        with res.addField(di, name=string("data")):
                            res.add(makeCString(s))
            m.s[TCFileSection.cfsStrData].add(res.extract())
            # slen = StaticSlen (254): marks this as a static (never-freed) long string.
            with result.addField(si, name=string("bytes")):
                result.add(ssoBytesLit(m, s, 254))
            with result.addField(si, name=string("more")):
                result.add(cCast(ptrType(string("LongString")), cAddr(dataName)))


# ------ Version 3: SmallString (SSO) strings --------------------------------

def genStringLiteralV3(m: BModule, n: PNode, isConst: bool, result: mut@Builder) -> None:
    # SmallString literal. Always generate a fresh SmallString variable (like v2
    # always generates a fresh outer NimStringV2). For long strings, cache the
    # LongString payload to avoid duplicates within a module.
    with const:
        AlwaysAvail = 7  # must match strs_v3.nim
    with let:
        s = n.strVal
        tmp = getTempName(m)
    result.add(tmp)

    cgsym(m, string("SmallString"))
    cgsym(m, string("LongString"))

    with let:
        payloadSize = AlwaysAvail + m.g.config.target.ptrSize - 1
    with var:
        res = newBuilder(string(""))
    if s.len <= AlwaysAvail:
        # Short: bytes holds slen + all chars (zero-padded), more = NULL.
        with res.addVarWithInitializer(
            VarKind.AlwaysConst if isConst else VarKind.Global,
            name=tmp, typ=string("SmallString")
        ):
            with var:
                si = StructInitializer()
            with res.addStructInitializer(si, kind=StructInitializerKind.siOrderedStruct):
                with res.addField(si, name=string("bytes")):
                    res.add(ssoBytesLit(m, s, s.len))
                with res.addField(si, name=string("more")):
                    res.add(NimNil)
    elif s.len <= payloadSize:
        # Medium: bytes holds slen + chars 0-6; more holds chars 7..PayloadSize-1 as raw bits.
        with res.addVarWithInitializer(
            VarKind.AlwaysConst if isConst else VarKind.Global,
            name=tmp, typ=string("SmallString")
        ):
            with var:
                si = StructInitializer()
            with res.addStructInitializer(si, kind=StructInitializerKind.siOrderedStruct):
                with res.addField(si, name=string("bytes")):
                    res.add(ssoBytesLit(m, s, s.len))
                with res.addField(si, name=string("more")):
                    res.add(ssoMoreLit(m, s))
    else:
        # Long: cache the LongString block to emit it only once per module per string.
        # Always generate a fresh SmallString pointing at the (possibly cached) block.
        with let:
            id = nodeTableTestOrSet(m.dataCache, n, m.labels)
        with var:
            dataName = string()
        if id == m.labels:
            dataName = getTempName(m)
            with res.addVarWithTypeAndInitializer(
                VarKind.AlwaysConst if isConst else VarKind.Global,
                name=dataName
            ):
                with res.addSimpleStruct(m, name=string(""), baseType=string("")):
                    res.addField(name=string("rc"), typ=NimInt)
                    res.addField(name=string("fullLen"), typ=NimInt)
                    res.addField(name=string("capImpl"), typ=NimInt)
                    res.addArrayField(name=string("data"), elementType=NimChar, len=s.len + 1)
                with do:
                    with var:
                        di = StructInitializer()
                    with res.addStructInitializer(di, kind=StructInitializerKind.siOrderedStruct):
                        with res.addField(di, name=string("fullLen")):
                            res.addIntValue(s.len)
                        with res.addField(di, name=string("rc")):
                            res.addIntValue(1)
                        with res.addField(di, name=string("capImpl")):
                            res.addIntValue(0)  # bit 0 = 0: static, never freed
                        with res.addField(di, name=string("data")):
                            res.add(makeCString(s))
        else:
            dataName = m.tmpBase + string(str(id))
        # slen = StaticSlen (254): marks this as a static (never-freed) long string.
        with res.addVarWithInitializer(
            VarKind.AlwaysConst if isConst else VarKind.Global,
            name=tmp, typ=string("SmallString")
        ):
            with var:
                si = StructInitializer()
            with res.addStructInitializer(si, kind=StructInitializerKind.siOrderedStruct):
                with res.addField(si, name=string("bytes")):
                    res.add(ssoBytesLit(m, s, 254))
                with res.addField(si, name=string("more")):
                    res.add(cCast(ptrType(string("LongString")), cAddr(dataName)))
    m.s[TCFileSection.cfsStrData].add(res.extract())


# ------ Version selector ---------------------------------------------------

def genStringLiteralDataOnly(m: BModule, s: string, info: TLineInfo,
                             isConst: bool, result: mut@Rope) -> None:
    match detectStrVersion(m):
        case 0 | 1:
            genStringLiteralDataOnlyV1(m, s, result)
        case 2:
            with let:
                tmp = getTempName(m)
            genStringLiteralDataOnlyV2(m, s, tmp, isConst)
            result.add(tmp)
        case 3:
            localError(m.config, info, string("genStringLiteralDataOnly not supported for SmallString (nimsso)"))
        case _:
            localError(m.config, info, string("cannot determine how to produce code for string literal"))


def genNilStringLiteral(m: BModule, info: TLineInfo, result: mut@Builder) -> None:
    result.add(cCast(ptrType(cgsymValue(m, string("NimStringDesc"))), NimNil))


def genStringLiteral(m: BModule, n: PNode, result: mut@Builder) -> None:
    match detectStrVersion(m):
        case 0 | 1:
            genStringLiteralV1(m, n, result)
        case 2:
            genStringLiteralV2(m, n, isConst=True, result=result)
        case 3:
            genStringLiteralV3(m, n, isConst=True, result=result)
        case _:
            localError(m.config, n.info, string("cannot determine how to produce code for string literal"))
