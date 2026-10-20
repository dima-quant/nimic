# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/symparser.nim
# ///
#       Nif library
# (c) Copyright 2024 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

from __future__ import annotations
from nimic.ntypes import *

## Parses NIF symbols into their components.


@dispatch
def extractBasename(s: string, isGlobal: mut @ bool) -> string:
    # From "abc.12.Mod132a3bc" extract "abc".
    # From "abc.12" extract "abc".
    # From "a.b.c.23" extract "a.b.c".
    with var:
        i = s.len - 2
    while i > 0:
        if s[i] == ch('.'):
            if s[i + 1] in Tset[char](inrange(ch('0'), ch('9'))):
                return substr(s, 0, i - 1)
            isGlobal <<= True  # we skipped one dot so it's a global name
        i -= 1
    return string("")


@dispatch
def extractBasename(s: mut @ string):
    with var:
        i = s.len - 2
    while i > 0:
        if s[i] == ch('.'):
            if s[i + 1] in Tset[char](inrange(ch('0'), ch('9'))):
                s.setLen(i)
                return
        i -= 1


def genericTypeName(key: string, modname: string) -> string:
    result = string("`t.0.I") + key + string(".") + modname
    return result


def extractModule(s: string) -> string:
    # From "abc.12.Mod132a3bc" extract "Mod132a3bc".
    # From "abc.12" extract "".
    with var:
        i = s.len - 2
    while i > 0:
        if s[i] == ch('.'):
            if s[i + 1] in Tset[char](inrange(ch('0'), ch('9'))):
                return string("")
            else:
                return substr(s, i + 1)
        i -= 1
    return string("")


class SplittedSymName(Object):
    name: string
    module: string

    def __str__(s: SplittedSymName) -> string:
        if s.module.len > 0:
            result = s.name + string(".") + s.module
        else:
            result = s.name
        return result


def splitSymName(s: string) -> SplittedSymName:
    with var:
        i = s.len - 2
    while i > 0:
        if s[i] == ch('.'):
            if s[i + 1] in Tset[char](inrange(ch('0'), ch('9'))):
                return SplittedSymName(name=s, module=string(""))
            else:
                return SplittedSymName(name=substr(s, 0, i - 1), module=substr(s, i + 1))
        i -= 1
    return SplittedSymName(name=s, module=string(""))


def extractVersionedBasename(s: string) -> string:
    # From "abc.12.Mod132a3bc" extract "abc.12".
    with var:
        i = s.len - 2
    while i > 0:
        if s[i] == ch('.'):
            if s[i + 1] in Tset[char](inrange(ch('0'), ch('9'))):
                with var:
                    j = i + 1
                while j < s.len and s[j] in Tset[char](inrange(ch('0'), ch('9'))): j += 1
                return substr(s, 0, j - 1)
        i -= 1
    return string("")


def derivedName(stem: string, tag: string) -> string:
    ## The `identifier.<number>` half of a symbol the compiler mints ALONGSIDE
    ## another one — a closure's environment type, a class's vtable, a coroutine's
    ## frame. `stem` is the originating symbol minus its module suffix, and the
    ## caller appends the module it wants the result to live in:
    ##
    ##   derivedName("outer.0", "env")        == "outer`env.0"
    ##   derivedName("gen.12.Iaaaa", "coro")  == "gen.12.Iaaaa`coro.0"
    ##
    ## The tag goes INTO the identifier rather than becoming a dotted segment of
    ## its own, because the two shapes say different things. nif-spec.md gives a
    ## global symbol as `<ident>.<disamb>.<moduleSuffix>` OR
    ## `<ident>.<disamb>.<key>.<moduleSuffix>`, "where `key` usually is the result
    ## from a generic instantiation". The `key` slot answers WHICH instantiation of
    ## `<ident>.<disamb>` this is — and because every module needing that
    ## instantiation derives the same key independently, `<ident>.<disamb>.<key>` is
    ## meaningful across module boundaries. That is exactly what lets a backend
    ## collapse the copies each importing module emits: DCE's
    ## `resolveSymbolConflicts`, `lengcgen`'s content-hashed
    ## `strlit.0.I<hash>.<mod>`, and nifasm's COMDAT merge all key on it.
    ##
    ## `env`, `coro`, `vt` are not keys — they name a ROLE, and the entity they name
    ## is private to one module. Put in the key slot they promise a cross-module
    ## identity they do not have, and two modules that each close over a variable in
    ## a proc named `outer` both claim `outer.0.env`. That is not a hypothetical:
    ## one module's closure read its captures out of the other's layout — see
    ## tests/nimony/closures/tenv_name_clash.nim.
    ##
    ## The backtick keeps the result out of the Nim-spellable namespace, matching
    ## the `` `f `` of a lifted local. It is inserted before the trailing version so
    ## the disambiguation number keeps its place; a stem that does not end in one
    ## (a keyed stem ends in its key) gets a fresh `.0` instead, which keeps both
    ## distinguishing parts — stem and tag — inside the identifier where they
    ## belong.
    ##
    ## Only a version at the very END counts, and that restriction is the whole
    ## point rather than an implementation detail: the result must be an UNKEYED
    ## global symbol. Scanning back past a later segment to find a number would
    ## leave that segment sitting in the key slot — `("gen.12.Iaaaa", "coro")` would
    ## come back as `gen`coro.12.Iaaaa`, a keyed name again, and one that has
    ## silently adopted the ORIGINAL symbol's key as its own cross-module identity.
    with var:
        i = stem.len - 1
    while i > 0 and stem[i] in Tset[char](inrange(ch('0'), ch('9'))): i -= 1
    if i > 0 and i < stem.len - 1 and stem[i] == ch('.'):
        result = substr(stem, 0, i - 1) + string("`") + tag + substr(stem, i)
    else:
        result = stem + string("`") + tag + string(".0")
    return result


def isInstantiation(s: string) -> bool:
    # abc.12.Iabcdefghi.mod2
    with var:
        i = s.len - 2
        dots = 3
    while i > 0:
        if s[i] == ch('.'):
            dots -= 1
            if s[i + 1] in Tset[char](inrange(ch('0'), ch('9'))):
                return dots == 0
            elif dots == 1 and s[i + 1] != ch('I'):
                return False
        i -= 1
    result = False
    return result


def isLocalName(s: string) -> bool:
    with var:
        dots = 0
    for c in s:
        if c == ch('.'): dots += 1
    result = dots <= 1
    return result


def splitLocalSymName(s: string, basename: mut @ string,
                      disamb: mut @ nint) -> bool:
    ## Splits a local symbol such as `tmp.14` into `tmp` and `14`.
    basename <<= string("")
    disamb <<= 0
    with var:
        dot = s.len - 1
    while dot >= 0 and s[dot] in Tset[char](inrange(ch('0'), ch('9'))):
        dot -= 1
    if dot <= 0 or dot == s.len - 1 or s[dot] != ch('.'):
        return False
    for i in range(0, dot):
        if s[i] == ch('.'):
            return False
    with var:
        value = 0
    for i in range(dot + 1, s.len):
        with let:
            digit = ord(s[i]) - ord(ch('0'))
        if value > (high(nint) - digit) // 10:
            return False
        value = value * 10 + digit
    basename <<= substr(s, 0, dot - 1)
    disamb <<= value
    result = True
    return result


def removeModule(s: string) -> string:
    # From "abc.12.Mod132a3bc" extract "abc.12".
    # From "abc.12" extract "abc.12".
    with var:
        i = s.len - 2
    while i > 0:
        if s[i] == ch('.'):
            if s[i + 1] in Tset[char](inrange(ch('0'), ch('9'))):
                return s
            else:
                return substr(s, 0, i - 1)
        i -= 1
    return s


class SplittedModulePath(Object):
    dir: string
    name: string
    ext: string

    def __str__(s: SplittedModulePath) -> string:
        result = s.dir.copy()
        if result.len > 0: result.add(string("/"))
        result.add(s.name)
        result.add(s.ext)
        return result


def splitModulePath(s: string) -> SplittedModulePath:
    # We diverge from `splitFile` here in that we consider the `.2.nif` part the extension, not just the `.nif` part.
    with var:
        i = s.len - 2
    while i >= 0 and s[i] not in Tset[char](ch('/'), ch('\\')):
        i -= 1
    with var:
        d = i + 1  # find first dot (i can be -1 here!)
    while d < s.len and s[d] != ch('.'):
        d += 1
    result = SplittedModulePath(dir=substr(s, 0, i - 1), name=substr(s, i + 1, d - 1), ext=substr(s, d))
    return result


def changeModuleExt(s: string, ext: string) -> string:
    with let:
        mp = splitModulePath(s)
    result = mp.dir.copy()
    if result.len > 0: result.add(string("/"))
    result.add(mp.name)
    if ext.len > 0 and ext[0] != ch('.'):
        result.add(string(".") + ext)
    else:
        result.add(ext)
    return result


def cmpNames(a: string, b: string) -> nint:
    ## `sort` needs an explicit comparator under Nimony, whose stdlib has no `cmp`.
    return -1 if a < b else (1 if a > b else 0)


if comptime(__name__ == "__main__"):
    from nimic.std.assertions import *
    assert extractVersionedBasename(string("abc.12.Mod132a3bc")) == string("abc.12")
    assert extractVersionedBasename(string("abc.Mod132a3bc")) == string("")

    with let:
        _sn = splitSymName(string("abc.12.Mod132a3bc"))
    assert _sn.name == string("abc.12")
    assert _sn.module == string("Mod132a3bc")

    assert derivedName(string("outer.0"), string("env")) == string("outer`env.0")
    assert derivedName(string("abc.12"), string("vt")) == string("abc`vt.12")
    # An instantiation stem ends in its key, not in a version: the tag and a fresh
    # number are appended so the key stays inside the identifier.
    assert derivedName(string("gen.12.Iaaaa"), string("coro")) == string("gen.12.Iaaaa`coro.0")
    # Whatever a caller appends its module to, the result must NOT read back as an
    # instantiation — that is the whole point of the exercise.
    assert not isInstantiation(derivedName(string("outer.0"), string("env")) + string(".mymod"))
    assert not isInstantiation(derivedName(string("gen.12.Iaaaa"), string("coro")) + string(".mymod"))
    assert isInstantiation(string("gen.12.Iaaaa.mymod"))
    # ...and the module suffix must still be recoverable.
    assert extractModule(derivedName(string("gen.12.Iaaaa"), string("coro")) + string(".mymod")) == string("mymod")
    assert extractModule(derivedName(string("outer.0"), string("env")) + string(".mymod")) == string("mymod")

    with let:
        _mp = splitModulePath(string("abc/def.2.nif"))
    assert _mp.dir == string("abc")
    assert _mp.name == string("def")
    assert _mp.ext == string(".2.nif")

    with let:
        _mp2 = splitModulePath(string("def.2.nif"))
    assert _mp2.dir == string(""), _mp2.dir
    assert _mp2.name == string("def"), _mp2.name
    assert _mp2.ext == string(".2.nif")

    with let:
        _mp3 = splitModulePath(string("def"))
    assert _mp3.dir == string(""), _mp3.dir
    assert _mp3.name == string("def"), _mp3.name
    assert _mp3.ext == string("")

    with var:
        _basename = string("")
        _disamb = nint(0)
    assert splitLocalSymName(string("tmp.14"), _basename, _disamb)
    assert _basename == string("tmp")
    assert _disamb == 14
    assert not splitLocalSymName(string("tmp.14.mod"), _basename, _disamb)
    assert not splitLocalSymName(string("tmp.part.14"), _basename, _disamb)

    # Added tests for remaining procs and edge cases
    with var:
        _isGlob = nbool(False)
        _inPlace = string("abc.12.Mod132a3bc")
        _inPlaceNoVer = string("abc.Mod132a3bc")
    echo(extractBasename(string("abc.12.Mod132a3bc"), _isGlob), "|", extractBasename(string("abc.12"), _isGlob), "|", extractBasename(string("a.b.c.23"), _isGlob), "|", extractBasename(string("nodigits"), _isGlob), "|", extractBasename(string(""), _isGlob))
    echo(_isGlob)
    _isGlob = nbool(False)
    echo(extractBasename(string("abc.12"), _isGlob), "|", _isGlob)
    echo(extractBasename(string("abc.12.Mod132a3bc"), _isGlob), "|", _isGlob)
    extractBasename(_inPlace)
    extractBasename(_inPlaceNoVer)
    echo(_inPlace, "|", _inPlaceNoVer)
    echo(genericTypeName(string("key1"), string("mod1")))
    echo(extractModule(string("abc.12")), "|", extractModule(string("")), "|", extractModule(string("a")))
    echo(str(_sn), "|", str(splitSymName(string("abc.12"))), "|", str(splitSymName(string(""))))
    echo(extractVersionedBasename(string("")), "|", extractVersionedBasename(string("abc.12")))
    echo(derivedName(string(""), string("env")), "|", derivedName(string(".0"), string("env")))
    echo(isInstantiation(string("")), "|", isInstantiation(string("gen.12.Xaaaa.mymod")))
    echo(isLocalName(string("")), "|", isLocalName(string("tmp")), "|", isLocalName(string("tmp.14")), "|", isLocalName(string("abc.12.Mod132a3bc")))
    echo(splitLocalSymName(string(""), _basename, _disamb), "|", splitLocalSymName(string(".14"), _basename, _disamb), "|", splitLocalSymName(string("tmp."), _basename, _disamb), "|", splitLocalSymName(string("tmp.99999999999999999999"), _basename, _disamb))
    echo(removeModule(string("abc.12.Mod132a3bc")), "|", removeModule(string("abc.12")), "|", removeModule(string("")))
    echo(str(_mp), "|", str(_mp2), "|", str(_mp3), "|", str(splitModulePath(string("a"))), "|", str(splitModulePath(string("a\\b.2.nif"))))
    echo(changeModuleExt(string("abc/def.2.nif"), string("c.nif")), "|", changeModuleExt(string("def.2.nif"), string(".s.nif")), "|", changeModuleExt(string("abc/def.2.nif"), string("")))
    echo(cmpNames(string("abc"), string("def")), "|", cmpNames(string("def"), string("abc")), "|", cmpNames(string("abc"), string("abc")))
