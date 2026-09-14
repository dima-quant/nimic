from __future__ import annotations
from nimic.ntypes import *
from nimic.std.strutils import cmpIgnoreStyle

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

class Endianness(NIntEnum):
    littleEndian = 0
    bigEndian = auto()

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
    intSize: int
    endian: Endianness
    floatSize: int
    bit: int

EndianToStr = array[Endianness, string]()
EndianToStr[Endianness.littleEndian] = string("littleEndian")
EndianToStr[Endianness.bigEndian] = string("bigEndian")

_OS_DATA = [
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
]

OS = array[Trange[succ(low(TSystemOS)), high(TSystemOS)], TInfoOS]()
for i, data in enumerate(_OS_DATA):
    OS[succ(succ(low(TSystemOS)), i)] = data

_CPU_DATA = [
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
]

CPU = array[Trange[succ(low(TSystemCPU)), high(TSystemCPU)], TInfoCPU]()
for i, data in enumerate(_CPU_DATA):
    CPU[succ(succ(low(TSystemCPU)), i)] = data

class Target(Object):
    targetCPU: TSystemCPU
    hostCPU: TSystemCPU
    targetOS: TSystemOS
    hostOS: TSystemOS
    intSize: int
    floatSize: int
    ptrSize: int
    tnl: string

def setTarget(t: mut[Target], o: TSystemOS, c: TSystemCPU):
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

# Mock implementation of Nim system.hostOS and system.hostCPU using Python's sys.platform and platform.machine()
import sys
import platform
def _get_host_os() -> string:
    if sys.platform == "darwin": return string("macosx")
    elif sys.platform == "win32": return string("windows")
    elif sys.platform.startswith("linux"): return string("linux")
    return string("any")

def _get_host_cpu() -> string:
    arch = platform.machine().lower()
    if arch in ["x86_64", "amd64"]: return string("amd64")
    elif arch in ["i386", "i686", "x86"]: return string("i386")
    elif arch in ["arm64", "aarch64"]: return string("arm64")
    elif arch.startswith("arm"): return string("arm")
    return string("any")

system_hostOS = _get_host_os()
system_hostCPU = _get_host_cpu()

def setTargetFromSystem(t: mut[Target]):
    t.hostOS = nameToOS(system_hostOS)
    t.hostCPU = nameToCPU(system_hostCPU)
    setTarget(t, t.hostOS, t.hostCPU)

if comptime(__name__ == '__main__'):
    import nimic.std.assertions
    # basic tests
    assert nameToOS(string("MacOSX")) == TSystemOS.osMacosx
    assert nameToCPU(string("amd64")) == TSystemCPU.cpuAmd64
    
    t = Target()
    setTargetFromSystem(t)
    assert t.hostOS != TSystemOS.osNone
    assert t.hostCPU != TSystemCPU.cpuNone
    
    # testing array bounds
    assert OS[TSystemOS.osLinux].name == string("Linux")
    assert CPU[TSystemCPU.cpuAmd64].intSize == 64

    print("All platform tests passed.")
