# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/platform.nim
# ///
#
#       Nif library
# (c) Copyright 2025 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

# This module contains data about the different processors
# and operating systems.
# Note: Unfortunately if an OS or CPU is listed here this does not mean that
# Nim has been tested on this platform or that the RTL has been ported.
# Feel free to test for your excentric platform!

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import *
from nimic.std.syncio import *


class TSystemOS(NIntEnum): # Also add OS in initialization section and alias
                           # conditionals to condsyms (end of module).
    osEmbedded = 0
    osDos = auto()
    osWindows = auto()
    osOs2 = auto()
    osLinux = auto()
    osMorphos = auto()
    osSkyos = auto()
    osSolaris = auto()
    osIllumos = auto()
    osIrix = auto()
    osNetbsd = auto()
    osFreebsd = auto()
    osOpenbsd = auto()
    osDragonfly = auto()
    osCrossos = auto()
    osAix = auto()
    osPalmos = auto()
    osQnx = auto()
    osAmiga = auto()
    osAtari = auto()
    osNetware = auto()
    osMacos = auto()
    osMacosx = auto()
    osIos = auto()
    osHaiku = auto()
    osAndroid = auto()
    osVxWorks = auto()
    osGenode = auto()
    osJS = auto()
    osNimVM = auto()
    osStandalone = auto()
    osNintendoSwitch = auto()
    osFreeRTOS = auto()
    osZephyr = auto()
    osNuttX = auto()
    osAny = auto()


class TInfoOSProp(NIntEnum):
    ospNeedsPIC = 0              # OS needs PIC for libraries
    ospCaseInsensitive = auto()  # OS filesystem is case insensitive
    ospPosix = auto()            # OS is posix-like
    ospLacksThreadVars = auto()  # OS lacks proper __threadvar support


class TInfoOSProps(Tset[TInfoOSProp]): pass


class TInfoOS(NTuple):
    name: string
    parDir: string
    dllFrmt: string
    altDirSep: string
    objExt: string
    newLine: string
    pathSep: string
    dirSep: string
    scriptExt: string
    curDir: string
    exeExt: string
    extSep: string
    props: TInfoOSProps


with const:
    OS = array[Trange[low(TSystemOS), high(TSystemOS)], TInfoOS]([
        # BARE METAL: no OS to ask for anything, which is a real target and not the
        # absence of one.
        #
        # Not `standalone`: that is Nim's name for a related but different
        # arrangement (a hosted-ish freestanding build with a `panicoverride`), and
        # nothing here offers that, so it would be the wrong word. Not `none`
        # either — the name becomes a `defined()` symbol, and `defined(none)` says
        # nothing about what is being built and reads like a mistake wherever it
        # appears. `defined(embedded)` says it.
        #
        # This slot used to be `osNone`, the not-found sentinel of `nameToOS`, which
        # is why it had no entry. `findOS` carries that answer in its result now.
        TInfoOS(name=string("embedded"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps()),
        TInfoOS(name=string("DOS"), parDir=string(".."), dllFrmt=string("$1.dll"), altDirSep=string("/"), objExt=string(".obj"), newLine=string("\x0D\x0A"), pathSep=string(";"), dirSep=string("\\"), scriptExt=string(".bat"), curDir=string("."), exeExt=string(".exe"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("Windows"), parDir=string(".."), dllFrmt=string("$1.dll"), altDirSep=string("/"), objExt=string(".obj"), newLine=string("\x0D\x0A"), pathSep=string(";"), dirSep=string("\\"), scriptExt=string(".bat"), curDir=string("."), exeExt=string(".exe"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("OS2"), parDir=string(".."), dllFrmt=string("$1.dll"), altDirSep=string("/"), objExt=string(".obj"), newLine=string("\x0D\x0A"), pathSep=string(";"), dirSep=string("\\"), scriptExt=string(".bat"), curDir=string("."), exeExt=string(".exe"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("Linux"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("MorphOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("SkyOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("Solaris"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("illumos"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("Irix"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("NetBSD"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("FreeBSD"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("OpenBSD"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("DragonFly"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("CROSSOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("AIX"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("PalmOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC})),
        TInfoOS(name=string("QNX"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("Amiga"), parDir=string(".."), dllFrmt=string("$1.library"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC})),
        TInfoOS(name=string("Atari"), parDir=string(".."), dllFrmt=string("$1.dll"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(""), curDir=string("."), exeExt=string(".tpp"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC})),
        TInfoOS(name=string("Netware"), parDir=string(".."), dllFrmt=string("$1.nlm"), altDirSep=string("/"), objExt=string(""), newLine=string("\x0D\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(".nlm"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("MacOS"), parDir=string("::"), dllFrmt=string("$1Lib"), altDirSep=string(":"), objExt=string(".o"), newLine=string("\x0D"), pathSep=string(","), dirSep=string(":"), scriptExt=string(""), curDir=string(":"), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("MacOSX"), parDir=string(".."), dllFrmt=string("lib$1.dylib"), altDirSep=string(":"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix, TInfoOSProp.ospLacksThreadVars})),
        TInfoOS(name=string("iOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("Haiku"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string(":"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix, TInfoOSProp.ospLacksThreadVars})),
        TInfoOS(name=string("Android"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("VxWorks"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(";"), dirSep=string("\\"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(".vxe"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix, TInfoOSProp.ospLacksThreadVars})),
        TInfoOS(name=string("Genode"), parDir=string(".."), dllFrmt=string("$1.lib.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(""), curDir=string("/"), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospLacksThreadVars})),
        TInfoOS(name=string("JS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps()),
        TInfoOS(name=string("NimVM"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps()),
        TInfoOS(name=string("Standalone"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps()),
        TInfoOS(name=string("NintendoSwitch"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(".elf"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("FreeRTOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospPosix})),
        TInfoOS(name=string("Zephyr"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospPosix})),
        TInfoOS(name=string("NuttX"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospPosix})),
        TInfoOS(name=string("Any"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps()),
    ])


class TSystemCPU(NIntEnum): # Also add CPU for in initialization section and
                            # alias conditionals to condsyms (end of module).
    cpuNone = 0
    cpuI386 = auto()
    cpuM68k = auto()
    cpuAlpha = auto()
    cpuPowerpc = auto()
    cpuPowerpc64 = auto()
    cpuPowerpc64el = auto()
    cpuSparc = auto()
    cpuVm = auto()
    cpuHppa = auto()
    cpuIa64 = auto()
    cpuAmd64 = auto()
    cpuMips = auto()
    cpuMipsel = auto()
    cpuArm = auto()
    cpuArm64 = auto()
    cpuJS = auto()
    cpuNimVM = auto()
    cpuAVR = auto()
    cpuMSP430 = auto()
    cpuSparc64 = auto()
    cpuMips64 = auto()
    cpuMips64el = auto()
    cpuRiscV32 = auto()
    cpuRiscV64 = auto()
    cpuEsp = auto()
    cpuWasm32 = auto()
    cpuE2k = auto()
    cpuLoongArch64 = auto()


class Endianness(NIntEnum):
    littleEndian = 0
    bigEndian = auto()


class TInfoCPU(NTuple):
    name: string
    intSize: nint
    endian: Endianness
    floatSize: nint
    bit: nint


with const:
    EndianToStr = array[Endianness, string]([string("littleEndian"), string("bigEndian")])
    CPU = array[Trange[succ(low(TSystemCPU)), high(TSystemCPU)], TInfoCPU]([
        TInfoCPU(name=string("i386"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("m68k"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("alpha"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("powerpc"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("powerpc64"), intSize=64, endian=Endianness.bigEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("powerpc64el"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("sparc"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("vm"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("hppa"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("ia64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("amd64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64), # a.k.a. x86_64, covers both amd and intel
        TInfoCPU(name=string("mips"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("mipsel"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        # `arm32`, not `arm`: alongside `arm64` the bare word never says which it is,
        # and this is the name the target triple is spelled with (`--cpu:arm32
        # --os:none` is the bare-metal Cortex-M target). `defined(arm)` still holds —
        # see `isDefined`'s alias table — and `--cpu:arm` is still accepted.
        TInfoCPU(name=string("arm32"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("arm64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("js"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("nimvm"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
          # xxx this seems buggy; on a 64bit machine, sizeof(int) is 64 in nimvm.
        TInfoCPU(name=string("avr"), intSize=16, endian=Endianness.littleEndian, floatSize=32, bit=16),
        TInfoCPU(name=string("msp430"), intSize=16, endian=Endianness.littleEndian, floatSize=32, bit=16),
        TInfoCPU(name=string("sparc64"), intSize=64, endian=Endianness.bigEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("mips64"), intSize=64, endian=Endianness.bigEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("mips64el"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("riscv32"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("riscv64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("esp"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("wasm32"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("e2k"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("loongarch64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
    ])


def findOS(name: string, res: mut @ TSystemOS) -> bool:
    # `true` and sets `res` when `name` is an OS this compiler knows.
    #
    # Separate from `nameToOS` because the first enum value is now a TARGET
    # (`osEmbedded`), so "returned the first one" no longer means "no match" — and
    # conflating the two would make every typo silently select bare metal.
    for i in inrange(low(TSystemOS), high(TSystemOS)):
        if cmpIgnoreStyle(name, OS[i].name) == 0:
            res <<= i
            return True
    result = False
    return result


def nameToOS(name: string) -> TSystemOS:
    # For the HOST's own name, which is always one this compiler knows. A miss here
    # is a bug in the `hostOS` derivation and not user input — `findOS` is what
    # validates a flag, and returning `osEmbedded` for a typo is exactly the
    # silence this split exists to prevent.
    #
    # The out-parameter goes to a LOCAL rather than straight to `result`: `result`
    # is not initialized on entry, and a `var` parameter must be, so handing it
    # over is a read of an uninitialized location whichever way `findOS` returns.
    with var:
        res = cell(TSystemOS.osEmbedded)
    if not findOS(name, res):
        quit(string("internal error: unknown host OS: ") + name)
    result = res
    return result


def findCPU(name: string, res: mut @ TSystemCPU) -> bool:
    # `true` and sets `res` when `name` is a CPU this compiler knows. `arm` is
    # accepted for `arm32`: the canonical name changed, the spelling people have
    # already written did not.
    for i in inrange(succ(TSystemCPU.cpuNone), high(TSystemCPU)):
        if cmpIgnoreStyle(name, CPU[i].name) == 0:
            res <<= i
            return True
    if cmpIgnoreStyle(name, string("arm")) == 0:
        res <<= TSystemCPU.cpuArm
        return True
    result = False
    return result


def nameToCPU(name: string) -> TSystemCPU:
    # The host's CPU; same contract as `nameToOS`.
    # `res` is a local for the same reason as in `nameToOS`.
    with var:
        res = cell(TSystemCPU.cpuNone)
    if not findCPU(name, res):
        quit(string("internal error: unknown host CPU: ") + name)
    result = res
    return result


if comptime(__name__ == "__main__"):
    # Array bounds and OS table entries
    assert OS[low(TSystemOS)].name == string("embedded")
    assert OS[TSystemOS.osEmbedded].name == string("embedded")
    assert OS[TSystemOS.osDos].name == string("DOS")
    assert OS[TSystemOS.osLinux].name == string("Linux")
    assert OS[TSystemOS.osIllumos].name == string("illumos")
    assert OS[TSystemOS.osWindows].exeExt == string(".exe")
    assert OS[TSystemOS.osMacosx].dllFrmt == string("lib$1.dylib")
    assert OS[high(TSystemOS)].name == string("Any")
    echo(OS[low(TSystemOS)].name, "|", OS[TSystemOS.osLinux].name, "|", OS[TSystemOS.osIllumos].name, "|", OS[high(TSystemOS)].name)

    # OS Properties and set operations
    assert TInfoOSProp.ospNeedsPIC not in OS[TSystemOS.osEmbedded].props
    assert TInfoOSProp.ospNeedsPIC in OS[TSystemOS.osLinux].props
    assert TInfoOSProp.ospPosix in OS[TSystemOS.osLinux].props
    assert TInfoOSProp.ospPosix in OS[TSystemOS.osIllumos].props
    assert TInfoOSProp.ospCaseInsensitive in OS[TSystemOS.osWindows].props
    assert TInfoOSProp.ospNeedsPIC not in OS[TSystemOS.osWindows].props
    assert TInfoOSProp.ospLacksThreadVars in OS[TSystemOS.osMacosx].props
    echo(TInfoOSProp.ospPosix in OS[TSystemOS.osLinux].props, "|", TInfoOSProp.ospCaseInsensitive in OS[TSystemOS.osWindows].props)

    # CPU table entries and Endianness
    assert EndianToStr[Endianness.littleEndian] == string("littleEndian")
    assert EndianToStr[Endianness.bigEndian] == string("bigEndian")
    echo(EndianToStr[Endianness.littleEndian], "|", EndianToStr[Endianness.bigEndian])

    assert CPU[succ(low(TSystemCPU))].name == string("i386")
    assert CPU[TSystemCPU.cpuAmd64].intSize == 64
    assert CPU[TSystemCPU.cpuArm].name == string("arm32")
    assert CPU[TSystemCPU.cpuArm].bit == 32
    assert CPU[TSystemCPU.cpuArm64].name == string("arm64")
    assert CPU[TSystemCPU.cpuArm64].bit == 64
    assert CPU[TSystemCPU.cpuAVR].intSize == 16
    assert CPU[TSystemCPU.cpuAVR].floatSize == 32
    assert CPU[TSystemCPU.cpuM68k].endian == Endianness.bigEndian
    assert CPU[TSystemCPU.cpuSparc64].endian == Endianness.bigEndian
    assert CPU[TSystemCPU.cpuAmd64].endian == Endianness.littleEndian
    assert CPU[high(TSystemCPU)].name == string("loongarch64")
    echo(CPU[succ(low(TSystemCPU))].name, "|", CPU[TSystemCPU.cpuArm].name, "|", CPU[TSystemCPU.cpuAmd64].intSize, "|", CPU[high(TSystemCPU)].name)

    # findOS and nameToOS tests (var TSystemOS parameter)
    with var:
        osRes = cell(TSystemOS.osEmbedded)
    echo(findOS(string("Linux"), osRes), "|", osRes)
    echo(findOS(string("illumos"), osRes), "|", osRes)
    echo(findOS(string("WINDOWS"), osRes), "|", osRes)
    echo(findOS(string("NonExistentOS"), osRes))
    echo(nameToOS(string("embedded")), "|", nameToOS(string("Linux")), "|", nameToOS(string("MacOSX")))

    # findCPU and nameToCPU tests (var TSystemCPU parameter)
    with var:
        cpuRes = cell(TSystemCPU.cpuNone)
    echo(findCPU(string("amd64"), cpuRes), "|", cpuRes)
    echo(findCPU(string("arm"), cpuRes), "|", cpuRes)
    echo(findCPU(string("arm32"), cpuRes), "|", cpuRes)
    echo(findCPU(string("NonExistentCPU"), cpuRes))
    echo(nameToCPU(string("amd64")), "|", nameToCPU(string("arm")), "|", nameToCPU(string("arm32")), "|", nameToCPU(string("loongarch64")))
