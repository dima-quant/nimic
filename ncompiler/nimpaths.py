# /// nimic
##[
# Represents absolute paths, but using a symbolic variables (eg $nimr) which can be
# resolved at runtime; this avoids hardcoding at compile time absolute paths so
# that the project root can be relocated.
#
# xxx factor pending https://github.com/timotheecour/Nim/issues/616, see also
# $nim/testament/lib/stdtest/specialpaths.nim
# specialpaths is simpler because it doesn't need variables to be relocatable at
# runtime (eg for use in testament)
#
# interpolation variables:
# : $nimr: such that `$nimr/lib/system.nim` exists (avoids confusion with $nim binary)
#          in compiler, it's obtainable via getPrefixDir(); for other tools (eg koch),
#         this could be getCurrentDir() or getAppFilename().parentDir.parentDir,
#         depending on use case
#
# Unstable API
#]##

from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *
from nimic.std.strutils import *

if comptime(defined("nimPreviewSlimSystem")):
    from nimic.std.assertions import *

with const:
    docCss = string("$nimr/doc/nimdoc.css")
    docCls = string("$nimr/doc/nimdoc.cls")
    docHackNim = string("$nimr/tools/dochack/dochack.nim")
    docHackJs = changeFileExt(docHackNim, string("js"))
    docHackJsFname = lastPathPart(docHackJs)
    theindexFname = string("theindex.html")
    nimdocOutCss = string("nimdoc.out.css")
    nimdocOutCls = string("nimdoc.cls")
    # `out` to make it easier to use with gitignore in user's repos
    htmldocsDirname = string("htmldocs")
    dotdotMangle = string("_._")  ## refs #13223
    # if this changes, make sure it's consistent with `esc` and `escapeLink`
    # lots of other obvious options won't work, see #14454; `_` could work too

def interp(path: string, nimr: string) -> string:
    result = path % [string("nimr"), nimr]
    doAssert(ch("$") not in result, str((path, nimr, result)))  # avoids un-interpolated variables in output
    return result

def getDocHacksJs(nimr: string, nim: string = getCurrentCompilerExe(), forceRebuild: bool = False) -> string:
    """return absolute path to dochack.js, rebuilding if it doesn't exist or if `forceRebuild`."""
    with let:
        docHackJs2 = interp(docHackJs, nimr=nimr)
    if forceRebuild or not fileExists(docHackJs2):
        with let:
            cmd = string("$nim js -d:release $file") % [
                string("nim"), quoteShell(nim),
                string("file"), quoteShell(interp(docHackNim, nimr=nimr))
            ]
        echo(string("getDocHacksJs: cmd: ") + cmd)
        doAssert(execShellCmd(cmd) == 0, str(cmd))
    doAssert(fileExists(docHackJs2))
    result = docHackJs2
    return result

if comptime(__name__ == '__main__'):
    assert interp(string("$nimr/foo"), string("/usr/lib/nim")) == string("/usr/lib/nim/foo")
    assert interp(docCss, string("/opt/nim")) == string("/opt/nim/doc/nimdoc.css")
    assert interp(docCls, string("/opt/nim")) == string("/opt/nim/doc/nimdoc.cls")
    assert interp(docHackNim, string("/opt/nim")) == string("/opt/nim/tools/dochack/dochack.nim")
    assert interp(docHackJs, string("/opt/nim")) == string("/opt/nim/tools/dochack/dochack.js")
    assert docHackJsFname == string("dochack.js")
    assert theindexFname == string("theindex.html")
    assert nimdocOutCss == string("nimdoc.out.css")
    assert nimdocOutCls == string("nimdoc.cls")
    assert htmldocsDirname == string("htmldocs")
    assert dotdotMangle == string("_._")

    # Test interp failure on un-interpolated variable
    with var:
        _interp_failed = False
    try:
        _ = interp(string("$nimr/$unknown"), string("/usr/lib/nim"))
    except Exception:
        _interp_failed = True
    assert _interp_failed

    # Test getDocHacksJs when dochack.js already exists (no rebuild needed)
    with let:
        _mock_nimr = string(".scratch/mock_nimpaths_test")
        _mock_dir = _mock_nimr + string("/tools/dochack")
        _mock_file = _mock_dir + string("/dochack.js")
    createDir(_mock_dir)
    writeFile(_mock_file, string("// dummy dochack.js"))
    with let:
        _res = getDocHacksJs(_mock_nimr, forceRebuild=False)
    assert _res == _mock_file
    removeFile(_mock_file)
    removeDir(_mock_nimr)

    # Test getDocHacksJs failure when rebuild fails (non-existent path)
    with var:
        _rebuild_failed = False
    try:
        _ = getDocHacksJs(string("/nonexistent_path_xyz_123"), forceRebuild=True)
    except Exception:
        _rebuild_failed = True
    assert _rebuild_failed

    echo("All nimpaths tests passed.")
