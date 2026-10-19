# /// nimic
#
# ///
#
#
#           The Nim Compiler
#        (c) Copyright 2015 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# This module handles the conditional symbols.

from __future__ import annotations
from nimic.ntypes import *

from nimic.std.strtabs import *

importFrom(".options", "Feature")
importFrom(".lineinfos", "hintMin", "hintMax", "warnMin", "warnMax")


@ufcs(StringTableRef)
def defineSymbol(symbols: StringTableRef, symbol: string, value: string = string("true")):
    symbols[symbol] = value


@ufcs(StringTableRef)
def undefSymbol(symbols: StringTableRef, symbol: string):
    symbols.del_(symbol)

#proc lookupSymbol*(symbols: StringTableRef; symbol: string): string =
#  result = if isDefined(symbol): gSymbols[symbol] else: nil


@ufcs(StringTableRef)
def definedSymbolNames(symbols: StringTableRef) -> string:
    for key in symbols.keys():
        yield key


@ufcs(StringTableRef)
def countDefinedSymbols(symbols: StringTableRef) -> nint:
    return symbols.len


@ufcs(StringTableRef)
@template_expand
def initDefines(symbols: StringTableRef):
    # for bootstrapping purposes and old code:
    @template
    def defineSymbol(s):
        symbols.defineSymbol(s)
    defineSymbol(string("nimhygiene")) # deadcode
    defineSymbol(string("niminheritable")) # deadcode
    defineSymbol(string("nimmixin")) # deadcode
    defineSymbol(string("nimeffects")) # deadcode
    defineSymbol(string("nimbabel")) # deadcode
    defineSymbol(string("nimcomputedgoto")) # deadcode
    defineSymbol(string("nimunion")) # deadcode
    defineSymbol(string("nimnewshared")) # deadcode
    defineSymbol(string("nimNewTypedesc")) # deadcode
    defineSymbol(string("nimrequiresnimframe")) # deadcode
    defineSymbol(string("nimparsebiggestfloatmagic")) # deadcode
    defineSymbol(string("nimlocks")) # deadcode
    defineSymbol(string("nimnode")) # deadcode
    defineSymbol(string("nimvarargstyped")) # deadcode
    defineSymbol(string("nimtypedescfixed")) # deadcode
    defineSymbol(string("nimKnowsNimvm")) # deadcode
    defineSymbol(string("nimArrIdx")) # deadcode
    defineSymbol(string("nimHasalignOf")) # deadcode
    defineSymbol(string("nimDistros")) # deadcode
    defineSymbol(string("nimHasCppDefine")) # deadcode
    defineSymbol(string("nimGenericInOutFlags")) # deadcode
    if comptime(False): defineSymbol(string("nimHasOpt")) # deadcode
    defineSymbol(string("nimNoArrayToCstringConversion")) # deadcode
    defineSymbol(string("nimHasRunnableExamples")) # deadcode
    defineSymbol(string("nimNewDot")) # deadcode
    defineSymbol(string("nimHasNilChecks")) # deadcode
    defineSymbol(string("nimSymKind")) # deadcode
    defineSymbol(string("nimVmEqIdent")) # deadcode
    defineSymbol(string("nimNoNil")) # deadcode
    defineSymbol(string("nimNoZeroTerminator")) # deadcode
    defineSymbol(string("nimNotNil")) # deadcode
    defineSymbol(string("nimVmExportFixed")) # deadcode
    defineSymbol(string("nimHasSymOwnerInMacro")) # deadcode
    defineSymbol(string("nimNewRuntime")) # deadcode
    defineSymbol(string("nimIncrSeqV3")) # deadcode
    defineSymbol(string("nimAshr")) # deadcode
    defineSymbol(string("nimNoNilSeqs")) # deadcode
    defineSymbol(string("nimNoNilSeqs2")) # deadcode
    defineSymbol(string("nimHasUserErrors")) # deadcode
    defineSymbol(string("nimUncheckedArrayTyp")) # deadcode
    defineSymbol(string("nimHasTypeof")) # deadcode
    defineSymbol(string("nimErrorProcCanHaveBody")) # deadcode
    defineSymbol(string("nimHasInstantiationOfInMacro")) # deadcode
    defineSymbol(string("nimHasHotCodeReloading")) # deadcode
    defineSymbol(string("nimHasNilSeqs")) # deadcode
    defineSymbol(string("nimHasSignatureHashInMacro")) # deadcode
    defineSymbol(string("nimHasDefault")) # deadcode
    defineSymbol(string("nimMacrosSizealignof")) # deadcode
    defineSymbol(string("nimNoZeroExtendMagic")) # deadcode
    defineSymbol(string("nimMacrosGetNodeId")) # deadcode
    defineSymbol(string("nimFixedForwardGeneric")) # deadcode
    defineSymbol(string("nimToOpenArrayCString")) # deadcode
    defineSymbol(string("nimHasUsed")) # deadcode
    defineSymbol(string("nimnomagic64")) # deadcode
    defineSymbol(string("nimNewShiftOps")) # deadcode
    defineSymbol(string("nimHasCursor")) # deadcode
    defineSymbol(string("nimAlignPragma")) # deadcode
    defineSymbol(string("nimHasExceptionsQuery")) # deadcode
    defineSymbol(string("nimHasIsNamedTuple")) # deadcode
    defineSymbol(string("nimHashOrdinalFixed")) # deadcode
    defineSymbol(string("nimHasSinkInference")) # deadcode
    defineSymbol(string("nimNewIntegerOps")) # deadcode
    defineSymbol(string("nimHasInvariant")) # deadcode

    for f in Feature:
        defineSymbol(string("nimHas") + str(f))

    for s in inrange(warnMin, warnMax):
        defineSymbol(string("nimHasWarning") + str(s))
    for s in inrange(hintMin, hintMax):
        defineSymbol(string("nimHasHint") + str(s))

    defineSymbol(string("nimFixedOwned"))
    defineSymbol(string("nimHasStyleChecks"))

    if comptime(defined("nimHasLibFFI")):
        # Renaming as we can't conflate input vs output define flags; e.g. this
        # will report the right thing regardless of whether user adds
        # `-d:nimHasLibFFI` in his user config.
        defineSymbol(string("nimHasLibFFIEnabled")) # deadcode

    defineSymbol(string("nimHasStacktraceMsgs")) # deadcode
    defineSymbol(string("nimDoesntTrackDefects"))
    defineSymbol(string("nimHasLentIterators")) # deadcode
    defineSymbol(string("nimHasDeclaredMagic")) # deadcode
    defineSymbol(string("nimHasStacktracesModule")) # deadcode
    defineSymbol(string("nimHasEffectTraitsModule"))
    defineSymbol(string("nimHasCastPragmaBlocks"))
    defineSymbol(string("nimHasDeclaredLocs"))
    defineSymbol(string("nimHasJsBigIntBackend"))
    defineSymbol(string("nimHasWarningAsError"))
    defineSymbol(string("nimHasHintAsError"))
    defineSymbol(string("nimHasSpellSuggest"))
    defineSymbol(string("nimHasCustomLiterals"))
    defineSymbol(string("nimHasUnifiedTuple"))
    defineSymbol(string("nimHasIterable"))
    defineSymbol(string("nimHasTypeofVoid")) # deadcode
    defineSymbol(string("nimHasDragonBox")) # deadcode
    defineSymbol(string("nimHasHintAll"))
    defineSymbol(string("nimHasTrace"))
    defineSymbol(string("nimHasEffectsOf"))

    defineSymbol(string("nimHasEnforceNoRaises"))
    defineSymbol(string("nimHasTopDownInference"))
    defineSymbol(string("nimHasTemplateRedefinitionPragma"))
    defineSymbol(string("nimHasCstringCase"))
    defineSymbol(string("nimHasCallsitePragma"))

    defineSymbol(string("nimHasWarnCastSizes")) # deadcode
    defineSymbol(string("nimHasOutParams"))
    defineSymbol(string("nimHasSystemRaisesDefect"))
    defineSymbol(string("nimHasWarnUnnamedBreak"))
    defineSymbol(string("nimHasGenericDefine"))
    defineSymbol(string("nimHasDefineAliases"))
    defineSymbol(string("nimHasWarnBareExcept"))
    defineSymbol(string("nimHasDup"))
    defineSymbol(string("nimHasChecksums"))
    defineSymbol(string("nimHasSendable"))
    defineSymbol(string("nimAllowNonVarDestructor"))
    defineSymbol(string("nimHasQuirky"))
    defineSymbol(string("nimHasEnsureMove"))
    defineSymbol(string("nimHasNoReturnError"))

    defineSymbol(string("nimUseStrictDefs")) # deadcode
    defineSymbol(string("nimHasNolineTooLong"))

    defineSymbol(string("nimHasCastExtendedVm"))
    defineSymbol(string("nimHasWarnStdPrefix"))

    defineSymbol(string("nimHasVtables"))
    defineSymbol(string("nimHasGenericsOpenSym2"))
    defineSymbol(string("nimHasGenericsOpenSym3"))
    defineSymbol(string("nimHasJsNoLambdaLifting"))
    defineSymbol(string("nimHasDefaultFloatRoundtrip"))
    defineSymbol(string("nimHasXorSet"))

    defineSymbol(string("nimHasSetLengthSeqUninitMagic"))
    defineSymbol(string("nimHasPreviewDuplicateModuleError"))

    defineSymbol(string("nimHasImplicitRangeConversion"))


if comptime(__name__ == "__main__"):
    with var:
        _syms = newStringTable(modeStyleInsensitive)
    doAssert(countDefinedSymbols(_syms) == 0)

    defineSymbol(_syms, string("fooBar"))
    doAssert(_syms.hasKey(string("foo_bar")))
    doAssert(_syms[string("foobar")] == string("true"))
    defineSymbol(_syms, string("customVal"), string("42"))
    doAssert(_syms[string("custom_val")] == string("42"))
    doAssert(countDefinedSymbols(_syms) == 2)

    undefSymbol(_syms, string("FOO_BAR"))
    doAssert(not _syms.hasKey(string("fooBar")))
    doAssert(countDefinedSymbols(_syms) == 1)

    initDefines(_syms)
    doAssert(_syms.hasKey(string("nimhygiene")))
    doAssert(_syms[string("nimhygiene")] == string("true"))
    doAssert(_syms.hasKey(string("nimHasWarning") + str(warnMin)))
    doAssert(_syms.hasKey(string("nimHasWarningCannotOpenFile")))
    doAssert(_syms.hasKey(string("nimHasHintSuccess")))
    doAssert(_syms.hasKey(string("nimHasdotOperators")))
    doAssert(not _syms.hasKey(string("nimHasOpt")))

    with var:
        _names = seq[string]()
    for _k in definedSymbolNames(_syms):
        _names.add(_k)
    doAssert(_names.len == countDefinedSymbols(_syms))
    doAssert(string("nimhygiene") in _names)
    doAssert(string("customVal") in _names)
    echo(string("condsyms: all tests passed!"))
