# /// nimic
#
#
#           The Nim Compiler
#        (c) Copyright 2012 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# This module contains data about the different processors
# and operating systems.
# Note: Unfortunately if an OS or CPU is listed here this does not mean that
# Nim has been tested on this platform or that the RTL has been ported.
# Feel free to test for your excentric platform!

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import cmpIgnoreStyle

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *

class TSystemOS(NIntEnum):
    osNone = 0
    osDos = auto()
    osWindows = auto()
    osOs2 = auto()
    osLinux = auto()
    osMorphos = auto()
    osSkyos = auto()
    osSolaris = auto()
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
    ospNeedsPIC = 0
    ospCaseInsensitive = auto()
    ospPosix = auto()
    ospLacksThreadVars = auto()

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
    OS = array[Trange[succ(low(TSystemOS)), high(TSystemOS)], TInfoOS]([
        TInfoOS(name=string("DOS"), parDir=string(".."), dllFrmt=string("$1.dll"), altDirSep=string("/"), objExt=string(".obj"), newLine=string("\x0D\x0A"), pathSep=string(";"), dirSep=string("\\"), scriptExt=string(".bat"), curDir=string("."), exeExt=string(".exe"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("Windows"), parDir=string(".."), dllFrmt=string("$1.dll"), altDirSep=string("/"), objExt=string(".obj"), newLine=string("\x0D\x0A"), pathSep=string(";"), dirSep=string("\\"), scriptExt=string(".bat"), curDir=string("."), exeExt=string(".exe"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("OS2"), parDir=string(".."), dllFrmt=string("$1.dll"), altDirSep=string("/"), objExt=string(".obj"), newLine=string("\x0D\x0A"), pathSep=string(";"), dirSep=string("\\"), scriptExt=string(".bat"), curDir=string("."), exeExt=string(".exe"), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospCaseInsensitive})),
        TInfoOS(name=string("Linux"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("MorphOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("SkyOS"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
        TInfoOS(name=string("Solaris"), parDir=string(".."), dllFrmt=string("lib$1.so"), altDirSep=string("/"), objExt=string(".o"), newLine=string("\x0A"), pathSep=string(":"), dirSep=string("/"), scriptExt=string(".sh"), curDir=string("."), exeExt=string(""), extSep=string("."), props=TInfoOSProps({TInfoOSProp.ospNeedsPIC, TInfoOSProp.ospPosix})),
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

class TSystemCPU(NIntEnum):
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
    cpuS390x = auto()
    cpuMips64 = auto()
    cpuMips64el = auto()
    cpuRiscV32 = auto()
    cpuRiscV64 = auto()
    cpuEsp = auto()
    cpuWasm32 = auto()
    cpuE2k = auto()
    cpuLoongArch64 = auto()

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
        TInfoCPU(name=string("amd64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("mips"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("mipsel"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("arm"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("arm64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("js"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("nimvm"), intSize=32, endian=Endianness.bigEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("avr"), intSize=16, endian=Endianness.littleEndian, floatSize=32, bit=16),
        TInfoCPU(name=string("msp430"), intSize=16, endian=Endianness.littleEndian, floatSize=32, bit=16),
        TInfoCPU(name=string("sparc64"), intSize=64, endian=Endianness.bigEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("s390x"), intSize=64, endian=Endianness.bigEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("mips64"), intSize=64, endian=Endianness.bigEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("mips64el"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("riscv32"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("riscv64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("esp"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("wasm32"), intSize=32, endian=Endianness.littleEndian, floatSize=64, bit=32),
        TInfoCPU(name=string("e2k"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
        TInfoCPU(name=string("loongarch64"), intSize=64, endian=Endianness.littleEndian, floatSize=64, bit=64),
    ])

class Target(Object):
    targetCPU: TSystemCPU
    hostCPU: TSystemCPU
    targetOS: TSystemOS
    hostOS: TSystemOS
    intSize: nint
    floatSize: nint
    ptrSize: nint
    tnl: string

def setTarget(t: mut@Target, o: TSystemOS, c: TSystemCPU):
    assert c != TSystemCPU.cpuNone
    assert o != TSystemOS.osNone
    t.targetCPU = c
    t.targetOS = o
    t.intSize = CPU[c].intSize // 8
    t.floatSize = CPU[c].floatSize // 8
    t.ptrSize = CPU[c].bit // 8
    t.tnl = OS[o].newLine

def nameToOS(name: string) -> TSystemOS:
    for i in inrange(succ(low(TSystemOS)), high(TSystemOS)):
        if cmpIgnoreStyle(name, OS[i].name) == 0:
            return i
    return TSystemOS.osNone

def listOSnames() -> seq[string]:
    result = seq[string]()
    for i in inrange(succ(low(TSystemOS)), high(TSystemOS)):
        result.add(OS[i].name)
    return result

def nameToCPU(name: string) -> TSystemCPU:
    for i in inrange(succ(low(TSystemCPU)), high(TSystemCPU)):
        if cmpIgnoreStyle(name, CPU[i].name) == 0:
            return i
    return TSystemCPU.cpuNone

def listCPUnames() -> seq[string]:
    result = seq[string]()
    for i in inrange(succ(low(TSystemCPU)), high(TSystemCPU)):
        result.add(CPU[i].name)
    return result

def setTargetFromSystem(t: mut@Target):
    t.hostOS = nameToOS(system.hostOS)
    t.hostCPU = nameToCPU(system.hostCPU)
    setTarget(t, t.hostOS, t.hostCPU)

if comptime(__name__ == '__main__'):
    # Basic nameToOS lookups
    assert nameToOS(string("MacOSX")) == TSystemOS.osMacosx
    assert nameToOS(string("linux")) == TSystemOS.osLinux
    assert nameToOS(string("WINDOWS")) == TSystemOS.osWindows
    assert nameToOS(string("NonExistentOS")) == TSystemOS.osNone

    # Basic nameToCPU lookups
    assert nameToCPU(string("amd64")) == TSystemCPU.cpuAmd64
    assert nameToCPU(string("i386")) == TSystemCPU.cpuI386
    assert nameToCPU(string("ARM64")) == TSystemCPU.cpuArm64
    assert nameToCPU(string("NonExistentCPU")) == TSystemCPU.cpuNone

    # Target configuration from system
    with var:
        t = Target()
    setTargetFromSystem(t)
    assert t.hostOS != TSystemOS.osNone
    assert t.hostCPU != TSystemCPU.cpuNone

    # Target configuration tests: 64-bit Linux Amd64
    with var:
        t_linux = Target()
    setTarget(t_linux, TSystemOS.osLinux, TSystemCPU.cpuAmd64)
    assert t_linux.targetOS == TSystemOS.osLinux
    assert t_linux.targetCPU == TSystemCPU.cpuAmd64
    assert t_linux.intSize == 8
    assert t_linux.floatSize == 8
    assert t_linux.ptrSize == 8
    assert t_linux.tnl == string("\x0A")

    # Target configuration tests: 32-bit Windows i386
    with var:
        t_win32 = Target()
    setTarget(t_win32, TSystemOS.osWindows, TSystemCPU.cpuI386)
    assert t_win32.targetOS == TSystemOS.osWindows
    assert t_win32.targetCPU == TSystemCPU.cpuI386
    assert t_win32.intSize == 4
    assert t_win32.floatSize == 8
    assert t_win32.ptrSize == 4
    assert t_win32.tnl == string("\x0D\x0A")

    # Target configuration tests: 16-bit embedded AVR
    with var:
        t_avr = Target()
    setTarget(t_avr, TSystemOS.osStandalone, TSystemCPU.cpuAVR)
    assert t_avr.targetOS == TSystemOS.osStandalone
    assert t_avr.targetCPU == TSystemCPU.cpuAVR
    assert t_avr.intSize == 2
    assert t_avr.floatSize == 4
    assert t_avr.ptrSize == 2

    # Array bounds and constants
    assert OS[TSystemOS.osLinux].name == string("Linux")
    assert OS[succ(low(TSystemOS))].name == string("DOS")
    assert OS[high(TSystemOS)].name == string("Any")

    assert CPU[TSystemCPU.cpuAmd64].intSize == 64
    assert CPU[succ(low(TSystemCPU))].name == string("i386")
    assert CPU[high(TSystemCPU)].name == string("loongarch64")

    # Endianness tests
    assert EndianToStr[Endianness.littleEndian] == string("littleEndian")
    assert EndianToStr[Endianness.bigEndian] == string("bigEndian")
    assert CPU[TSystemCPU.cpuM68k].endian == Endianness.bigEndian
    assert CPU[TSystemCPU.cpuSparc64].endian == Endianness.bigEndian
    assert CPU[TSystemCPU.cpuAmd64].endian == Endianness.littleEndian
    assert CPU[TSystemCPU.cpuArm64].endian == Endianness.littleEndian

    # OS Properties and set operations
    assert TInfoOSProp.ospNeedsPIC in OS[TSystemOS.osLinux].props
    assert TInfoOSProp.ospPosix in OS[TSystemOS.osLinux].props
    assert TInfoOSProp.ospCaseInsensitive in OS[TSystemOS.osWindows].props
    assert TInfoOSProp.ospNeedsPIC not in OS[TSystemOS.osWindows].props
    assert TInfoOSProp.ospLacksThreadVars in OS[TSystemOS.osMacosx].props

    # Name lists
    with var:
        os_names = listOSnames()
    assert len(os_names) == 34
    assert string("Linux") in os_names
    assert string("Windows") in os_names
    assert string("DOS") in os_names
    assert string("Any") in os_names

    with var:
        cpu_names = listCPUnames()
    assert len(cpu_names) == 29
    assert string("amd64") in cpu_names
    assert string("arm64") in cpu_names
    assert string("i386") in cpu_names
    assert string("loongarch64") in cpu_names

    echo("All platform tests passed.")
