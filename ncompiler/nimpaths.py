from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import changeFileExt, extractFilename, fileExists, execShellCmd, getCurrentCompilerExe


docCss = string("$nimr/doc/nimdoc.css")
docCls = string("$nimr/doc/nimdoc.cls")
docHackNim = string("$nimr/tools/dochack/dochack.nim")
docHackJs = changeFileExt(docHackNim, string("js"))
docHackJsFname = extractFilename(docHackJs)
theindexFname = string("theindex.html")
nimdocOutCss = string("nimdoc.out.css")
nimdocOutCls = string("nimdoc.cls")
htmldocsDirname = string("htmldocs")
dotdotMangle = string("_._")

def interp(path: string, nimr: string) -> string:
    result = string(str(path).replace("$nimr", str(nimr)))
    assert '$' not in str(result)
    return result


def getDocHacksJs(nimr: string, nim: string = getCurrentCompilerExe(), forceRebuild: bool = False) -> string:
    docHackJs2 = interp(docHackJs, nimr)
    if forceRebuild or not fileExists(docHackJs2):
        from shlex import quote
        cmd = string(f"{str(nim)} js -d:release {quote(str(interp(docHackNim, nimr)))}")
        print("getDocHacksJs: cmd: " + str(cmd))
        assert execShellCmd(cmd) == 0
    assert fileExists(docHackJs2)
    return docHackJs2

if comptime(__name__ == '__main__'):
    assert interp(string("$nimr/foo"), string("/usr/lib/nim")) == string("/usr/lib/nim/foo")
    print("All nimpaths tests passed.")
