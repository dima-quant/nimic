"""
ncompiler/platform.py — OS and CPU platform definitions
Converted from compiler/platform.nim (minimal for lexer/parser)
"""
from __future__ import annotations
from nimic.ntypes import *
import sys

class TSystemOS(NIntEnum):
    osNone = auto(); osDos = auto(); osWindows = auto(); osOs2 = auto()
    osLinux = auto(); osMorphos = auto(); osSkyos = auto(); osSolaris = auto()
    osIrix = auto(); osNetbsd = auto(); osFreebsd = auto(); osOpenbsd = auto()
    osDragonfly = auto(); osCrossos = auto(); osAix = auto(); osPalmos = auto()
    osQnx = auto(); osAmiga = auto(); osAtari = auto(); osNetware = auto()
    osMacos = auto(); osMacosx = auto(); osIos = auto(); osHaiku = auto()
    osAndroid = auto(); osVxWorks = auto(); osGenode = auto(); osJS = auto()
    osNimVM = auto(); osStandalone = auto(); osNintendoSwitch = auto()
    osFreeRTOS = auto(); osZephyr = auto(); osNuttX = auto(); osAny = auto()

class TSystemCPU(NIntEnum):
    cpuNone = auto(); cpuI386 = auto(); cpuM68k = auto(); cpuAlpha = auto()
    cpuPowerpc = auto(); cpuPowerpc64 = auto(); cpuPowerpc64el = auto()
    cpuSparc = auto(); cpuVm = auto(); cpuHppa = auto(); cpuIa64 = auto()
    cpuAmd64 = auto(); cpuMips = auto(); cpuMipsel = auto(); cpuArm = auto()
    cpuArm64 = auto(); cpuJS = auto(); cpuNimVM = auto(); cpuAVR = auto()
    cpuMSP430 = auto(); cpuSparc64 = auto(); cpuS390x = auto()
    cpuMips64 = auto(); cpuMips64el = auto(); cpuRiscV32 = auto()
    cpuRiscV64 = auto(); cpuEsp = auto(); cpuWasm32 = auto()
    cpuE2k = auto(); cpuLoongArch64 = auto()


# Simplified OS info — only the newline field is needed by the lexer
_OS_NEWLINES = {
    TSystemOS.osDos: "\r\n", TSystemOS.osWindows: "\r\n",
    TSystemOS.osOs2: "\r\n", TSystemOS.osNetware: "\r\n",
    TSystemOS.osMacos: "\r",
}

# Simplified CPU info
_CPU_BITS = {
    TSystemCPU.cpuI386: 32, TSystemCPU.cpuAmd64: 64,
    TSystemCPU.cpuArm: 32, TSystemCPU.cpuArm64: 64,
}

class Target:
    __slots__ = ('targetCPU', 'hostCPU', 'targetOS', 'hostOS',
                 'intSize', 'floatSize', 'ptrSize', 'tnl')
    def __init__(self):
        self.targetCPU = TSystemCPU.cpuNone
        self.hostCPU = TSystemCPU.cpuNone
        self.targetOS = TSystemOS.osNone
        self.hostOS = TSystemOS.osNone
        self.intSize = 8
        self.floatSize = 8
        self.ptrSize = 8
        self.tnl = "\n"

def setTarget(t: Target, o: TSystemOS, c: TSystemCPU):
    t.targetCPU = c
    t.targetOS = o
    t.tnl = _OS_NEWLINES.get(o, "\n")
    bits = _CPU_BITS.get(c, 64)
    t.intSize = bits // 8
    t.floatSize = 8
    t.ptrSize = bits // 8

def nameToOS(name: str) -> TSystemOS:
    nl = name.lower()
    for m in TSystemOS:
        if m.name[2:].lower() == nl:
            return m
    return TSystemOS.osNone

def nameToCPU(name: str) -> TSystemCPU:
    nl = name.lower()
    for m in TSystemCPU:
        if m.name[3:].lower() == nl:
            return m
    return TSystemCPU.cpuNone

def setTargetFromSystem(t: Target):
    plat = sys.platform
    if plat == "darwin":
        t.hostOS = TSystemOS.osMacosx
    elif plat.startswith("linux"):
        t.hostOS = TSystemOS.osLinux
    elif plat == "win32":
        t.hostOS = TSystemOS.osWindows
    else:
        t.hostOS = TSystemOS.osLinux
    import platform as _p
    machine = _p.machine().lower()
    if machine in ("x86_64", "amd64"):
        t.hostCPU = TSystemCPU.cpuAmd64
    elif machine in ("aarch64", "arm64"):
        t.hostCPU = TSystemCPU.cpuArm64
    elif machine in ("i386", "i686", "x86"):
        t.hostCPU = TSystemCPU.cpuI386
    else:
        t.hostCPU = TSystemCPU.cpuAmd64
    setTarget(t, t.hostOS, t.hostCPU)
