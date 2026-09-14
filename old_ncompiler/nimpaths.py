# ##[
# Represents absolute paths, but using a symbolic variables (eg $nimr) which can be
# resolved at runtime; this avoids hardcoding at compile time absolute paths so
# that the project root can be relocated.

# xxx factor pending https://github.com/timotheecour/Nim/issues/616, see also
# $nim/testament/lib/stdtest/specialpaths.nim
# specialpaths is simpler because it doesn't need variables to be relocatable at
# runtime (eg for use in testament)

# interpolation variables:
# : $nimr: such that `$nimr/lib/system.nim` exists (avoids confusion with $nim binary)
#          in compiler, it's obtainable via getPrefixDir(); for other tools (eg koch),
#         this could be getCurrentDir() or getAppFilename().parentDir.parentDir,
#         depending on use case

# Unstable API
# ]##

# import std/[os, strutils]

# when defined(nimPreviewSlimSystem):
#   import std/assertions
#from __future__ import annotations
from nkeywords import *
from pathutils import *

# const
#   docCss* = "$nimr/doc/nimdoc.css"
#   docCls* = "$nimr/doc/nimdoc.cls"
#   docHackNim* = "$nimr/tools/dochack/dochack.nim"
#   docHackJs* = docHackNim.changeFileExt("js")
#   docHackJsFname* = docHackJs.lastPathPart
#   theindexFname* = "theindex.html"
#   nimdocOutCss* = "nimdoc.out.css"
#   nimdocOutCls* = "nimdoc.cls"
#     # `out` to make it easier to use with gitignore in user's repos
#   htmldocsDirname* = "htmldocs"
#   dotdotMangle* = "_._"  ## refs #13223
#     # if this changes, make sure it's consistent with `esc` and `escapeLink`
#     # lots of other obvious options won't work, see #14454; `_` could work too

with const:
  docCss = "$nimr/doc/nimdoc.css"
  docCls = "$nimr/doc/nimdoc.cls"
  docHackNim = "$nimr/tools/dochack/dochack.nim"
  docHackJs = changeFileExt(docHackNim, "js")
  docHackJsFname = lastPathPart(docHackJs)
  theindexFname = "theindex.html"
  nimdocOutCss = "nimdoc.out.css"
  nimdocOutCls = "nimdoc.cls"
    # `out` to make it easier to use with gitignore in user's repos
  htmldocsDirname = "htmldocs"
  dotdotMangle = "_._"  ## refs #13223
    # if this changes, make sure it's consistent with `esc` and `escapeLink`
    # lots of other obvious options won't work, see #14454; `_` could work too

# proc interp*(path: string, nimr: string): string =
#   result = path % ["nimr", nimr]
#   doAssert '$' notin result, $(path, nimr, result) # avoids un-interpolated variables in output

def interp(path: string, nimr: string) -> string:
  result = to_string(to_string(path) % ["nimr", nimr])
  assert '$' not in result, f"{path}, {nimr}, {result}" # avoids un-interpolated variables in output
  return result

# proc getDocHacksJs*(nimr: string, nim = getCurrentCompilerExe(), forceRebuild = false): string =
#   ## return absolute path to dochack.js, rebuilding if it doesn't exist or if
#   ## `forceRebuild`.
#   let docHackJs2 = docHackJs.interp(nimr = nimr)
#   if forceRebuild or not docHackJs2.fileExists:
#     let cmd =  "$nim js -d:release $file" % ["nim", nim.quoteShell, "file", docHackNim.interp(nimr = nimr).quoteShell]
#     echo "getDocHacksJs: cmd: " & cmd
#     doAssert execShellCmd(cmd) == 0, $(cmd)
#   doAssert docHackJs2.fileExists
#   result = docHackJs2

def getDocHacksJs(nimr: string, nim = getCurrentCompilerExe(), forceRebuild = False) -> string:
  ## return absolute path to dochack.js, rebuilding if it doesn't exist or if
  ## `forceRebuild`.
  docHackJs2 = interp(docHackJs, nimr = nimr)
  if forceRebuild or not docHackJs2.fileExists:
    cmd =  to_string("$nim js -d:release $file") % ["nim", quoteShell(nim), "file", quoteShell(interp(docHackNim, nimr = nimr))]
    print("getDocHacksJs: cmd: " + cmd)
    assert execShellCmd(cmd) == 0, f"{cmd}"
  assert fileExists(docHackJs2)
  result = docHackJs2
  return result