# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/lengc.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## Leng driver program.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.parseopt import CmdLineKind, getopt
from nimic.std.strutils import normalize
from nimic.std import os, osproc, assertions, syncio, paths
from nimic.std.tables import OrderedTable, Table
from nimic.std.dirs import createDir
from nimic.std.paths import Path
from . import codegen, llvmcodegen
from .codegen import generateCode, GenFlag
from .llvmcodegen import generateLLVMCode, LLVMGenFlag  # nifcore backends (local to shoggoth/)
from .noptions import (
    Action, AppType, Backend, ConfigRef, initActionTable, OptimizeLevel, Option, State, SystemCC)
from ..lib.symparser import splitModulePath
from ..lib.vfs import dumpVfsProfile
from ..lib.nimversion import Version
changeFileExt = overloads(os.changeFileExt, paths.changeFileExt)

include("../lib/compat2")


@template
def _makeDir(p: string):
    if comptime(defined("nimony")):
        _onRaiseQuit(createDir(path(p)))
    else:
        _onRaiseQuit(createDir(Path(p)))


with const:
    _Usage = string("Leng Compiler. Version ") + Version + string("""\

  (c) 2024 Andreas Rumpf
Usage:
  lengc [options] [command] [arguments]
Command:
  c|cpp|llvm file.nif [file2.nif]    convert NIF files to C|C++|LLVM IR

Options:
  -r, --run                 run the makefile and the compiled program
  --compileOnly             compile only, do not run the makefile and the compiled program
  --isMain                  mark the file as the main program
  --cc:SYMBOL               specify the C compiler
  --opt:none|speed|size     optimize not at all or for speed|size
  --lineDir:on|off          generation of #line directive on|off
  --bits:N                  `(i -1)` has N bits; possible values: 64, 32, 16
  --nimcache:PATH           set the path used for generated files
  --app:console|gui|lib|staticlib
                            set the application type (default: console)
  --version                 show the version
  --help                    show this help
""")


def _writeHelp():
    quit(_Usage, QuitSuccess)


def _writeVersion():
    quit(Version + string("\n"), QuitSuccess)


def _generateBackend(s: mut @ State, action: Action, files: seq[string], flags: Tset[GenFlag]):
    assert action in Tset[Action](Action.atC, Action.atCpp)
    if files.len == 0:
        quit(string("command takes a filename"))
    s.config.backend = Backend.backendC if action == Action.atC else Backend.backendCpp
    with let:
        destExt = string(".c") if action == Action.atC else string(".cpp")
    for i in range(files.len - 1):
        with let:
            inp = files[i]
            outp = s.config.nifcacheDir / splitModulePath(inp).name + destExt
        generateCode(s, inp, outp, Tset[GenFlag]())
    with let:
        inp = files[back(1)]
        outp = s.config.nifcacheDir / splitModulePath(inp).name + destExt
    generateCode(s, inp, outp, flags)


def _generateLLVMBackend(s: mut @ State, files: seq[string], flags: Tset[LLVMGenFlag]):
    if files.len == 0:
        quit(string("command takes a filename"))
    for i in range(files.len - 1):
        with let:
            inp = files[i]
            outp = s.config.nifcacheDir / splitModulePath(inp).name + string(".ll")
        generateLLVMCode(s, inp, outp, Tset[LLVMGenFlag]())
    with let:
        inp = files[back(1)]
        outp = s.config.nifcacheDir / splitModulePath(inp).name + string(".ll")
    generateLLVMCode(s, inp, outp, flags)


def _handleCmdLine():
    with var:
        toRun = False
        compileOnly = False
        isMain = False
        currentAction = Action.atNone

    with var:
        actionTable = initActionTable()

    with var:
        s = State(config=ConfigRef(), bits=sizeof(nint) * 8)
    if comptime(defined("macosx")):  # TODO: switches to default config for platforms
        s.config.cCompiler = SystemCC.ccCLang
    else:
        s.config.cCompiler = SystemCC.ccGcc
    s.config.nifcacheDir = string("nimcache")
    s.config.appType = AppType.appConsole  # console is the default

    for kind, key, val in getopt():
        match kind:
            case CmdLineKind.cmdArgument:
                match key.normalize():
                    case "c":
                        currentAction = Action.atC
                        if not actionTable.hasKey(Action.atC):
                            actionTable[Action.atC] = seq[string]([])
                    case "cpp":
                        currentAction = Action.atCpp
                        if not actionTable.hasKey(Action.atCpp):
                            actionTable[Action.atCpp] = seq[string]([])
                    case "n":
                        currentAction = Action.atNative
                        if not actionTable.hasKey(Action.atNative):
                            actionTable[Action.atNative] = seq[string]([])
                    case "llvm":
                        currentAction = Action.atLLVM
                        if not actionTable.hasKey(Action.atLLVM):
                            actionTable[Action.atLLVM] = seq[string]([])
                    case _:
                        match currentAction:
                            case Action.atC:
                                getOrQuit(actionTable, Action.atC).add(key)
                            case Action.atCpp:
                                getOrQuit(actionTable, Action.atCpp).add(key)
                            case Action.atNative:
                                getOrQuit(actionTable, Action.atNative).add(key)
                            case Action.atLLVM:
                                getOrQuit(actionTable, Action.atLLVM).add(key)
                            case Action.atNone:
                                quit(string("invalid command: ") + key)
            case CmdLineKind.cmdLongOption | CmdLineKind.cmdShortOption:
                match normalize(key):
                    case "bits":
                        match val:
                            case "64": s.bits = 64
                            case "32": s.bits = 32
                            case "16": s.bits = 16
                            case _: quit(string("invalid value for --bits"))
                    case "help" | "h": _writeHelp()
                    case "version" | "v": _writeVersion()
                    case "run" | "r": toRun = True
                    case "compileonly": compileOnly = True
                    case "ismain": isMain = True
                    case "cc":
                        match val.normalize():
                            case "gcc":
                                s.config.cCompiler = SystemCC.ccGcc
                            case "clang":
                                s.config.cCompiler = SystemCC.ccCLang
                            case _:
                                quit(string("unknown C compiler: '") + val + string("'. Available options are: gcc, clang"))
                    case "opt":
                        match val.normalize():
                            case "speed":
                                s.config.optimizeLevel = OptimizeLevel.Speed
                            case "size":
                                s.config.optimizeLevel = OptimizeLevel.Size
                            case "none":
                                s.config.optimizeLevel = OptimizeLevel.None_
                            case _:
                                quit(string("'none', 'speed' or 'size' expected, but '") + val + string("' found"))
                    case "linedir":
                        match val.normalize():
                            case "" | "on":
                                s.config.options.incl(Option.optLineDir)
                            case "off":
                                s.config.options.excl(Option.optLineDir)
                            case _:
                                quit(string("'on', 'off' expected, but '") + val + string("' found"))
                    case "nimcache":
                        s.config.nifcacheDir = val
                    case "out" | "o":
                        s.config.outputFile = val
                    case "app":
                        match normalize(val):
                            case "console":
                                s.config.appType = AppType.appConsole
                            case "gui":
                                s.config.appType = AppType.appGui
                            case "lib":
                                s.config.appType = AppType.appLib
                            case "staticlib":
                                s.config.appType = AppType.appStaticLib
                            case _:
                                quit(string("invalid value for --app; expected console, gui, lib, or staticlib"))
                    case _: _writeHelp()
            case CmdLineKind.cmdEnd: assert False, "cannot happen"

    _makeDir(s.config.nifcacheDir)
    if actionTable.len != 0:
        for action in actionTable.keys():
            match action:
                case Action.atC | Action.atCpp:
                    with let:
                        isLast = (isMain if compileOnly else currentAction == action)
                        flags = Tset[GenFlag](GenFlag.gfMainModule) if isLast else Tset[GenFlag]()
                    _generateBackend(s, action, getOrQuit(actionTable, action), flags)
                case Action.atNative:
                    with let:
                        args = getOrQuit(actionTable, action)
                    if args.len == 0:
                        quit(string("command takes a filename"))
                    else:
                        if comptime(defined("enableAsm")):
                            for inp in items(args):
                                with let:
                                    outp = changeFileExt(inp, string(".S"))
                                generateAsm(inp, s.config.nifcacheDir / outp)
                        else:
                            quit(string("wasn't built with native target support"))
                case Action.atLLVM:
                    with let:
                        isLast = (isMain if compileOnly else currentAction == action)
                        llvmFlags = Tset[LLVMGenFlag](LLVMGenFlag.gfMainModule) if isLast else Tset[LLVMGenFlag]()
                    _generateLLVMBackend(s, getOrQuit(actionTable, action), llvmFlags)
                case Action.atNone:
                    quit(string("targets are not specified"))

        with let:
            appName = splitModulePath(getOrQuit(actionTable, currentAction)[back(1)]).name
        if s.config.outputFile == "":
            s.config.outputFile = appName
    else:
        _writeHelp()


if comptime(__name__ == "__main__"):
    _handleCmdLine()
    dumpVfsProfile(string("lengc"))
