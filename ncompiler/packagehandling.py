# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2017 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#

# included from options.nim (ConfigRef and the os procs come from the includer; tests in options.py)


def _myParentDirs(p: string) -> string:
    # XXX os's parentDirs is stupid (multiple yields) and triggers an old bug...
    with var:
        current = p
    while True:
        current = parentDir(current)
        if len(current) == 0:
            break
        yield current


def getNimbleFile(conf: ConfigRef, path: string) -> string:
    """returns absolute path to nimble file, e.g.: /pathto/cligen.nimble"""
    result = string("")
    with var:
        parents = 0
    with block("packageSearch"):
        for d in _myParentDirs(path):
            if conf.packageCache.hasKey(d):
                # echo "from cache ", d, " |", packageCache[d], "|", path.splitFile.name
                return conf.packageCache[d]
            parents += 1
            for file in walkFiles(d / string("*.nimble")):
                result = file
                breakBlock("packageSearch")
    # we also store if we didn't find anything:
    for d in _myParentDirs(path):
        # echo "set cache ", d, " |", result, "|", parents
        conf.packageCache[d] = result
        parents -= 1
        if parents <= 0:
            break
    return result


def getPackageName(conf: ConfigRef, path: string) -> string:
    """returns nimble package name, e.g.: `cligen`"""
    with let:
        _path = getNimbleFile(conf, path)
    if len(_path) > 0:
        return splitFile(_path).name
    else:
        return string("unknown")
