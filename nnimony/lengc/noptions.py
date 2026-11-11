# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/noptions.nim
# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.tables import initOrderedTable, OrderedTable
from nimic.std import syncio  # syncio: `quit` is not in Nimony's `system`


class Backend(NStrEnum):
    backendInvalid = ""  # for parseEnum
    backendC = "c"
    backendCpp = "cpp"


class Option(NIntEnum):
    optLineDir = auto()


class OptimizeLevel(NIntEnum):
    None_ = auto()
    Speed = auto()
    Size = auto()


class SystemCC(NIntEnum):
    ccNone = auto()
    ccGcc = auto()
    ccCLang = auto()


class Action(NIntEnum):
    atNone = auto()
    atC = auto()
    atCpp = auto()
    atNative = auto()
    atLLVM = auto()


class AppType(NStrEnum):
    appConsole = "console"  # executable with console
    appGui = "gui"  # executable with GUI (no console on Windows)
    appLib = "lib"  # dynamic library (dll/so/dylib)
    appStaticLib = "staticlib"  # static library (.a/.lib)


@ref
class ConfigRef(Object):  ## every global configuration
    """{.acyclic.}"""
    cCompiler: SystemCC
    backend: Backend
    options: Tset[Option]
    optimizeLevel: OptimizeLevel
    nifcacheDir: string
    outputFile: string
    appType: AppType

    @template
    def getoptimizeLevelFlag(config: ConfigRef) -> string:
        match config.optimizeLevel:
            case OptimizeLevel.Speed:
                return string("-O3")
            case OptimizeLevel.Size:
                return string("-Os")
            case OptimizeLevel.None_:
                return string("")

    @template
    def getCompilerConfig(config: ConfigRef) -> tuple[string, string]:
        match config.cCompiler:
            case SystemCC.ccGcc:
                return (string("gcc"), string("g++"))
            case SystemCC.ccCLang:
                return (string("clang"), string("clang++"))
            case _:
                quit(string("unreachable"))


class State(Object):
    config: ConfigRef
    bits: nint


ActionTable = OrderedTable[Action, seq[string]]


def initActionTable() -> ActionTable:
    """{.inline.}"""
    result = initOrderedTable[Action, seq[string]]()
    return result


with const:
    ExtAction = array[Action, string]([string(""), string(".c"), string(".cpp"), string(".S"), string(".ll")])
