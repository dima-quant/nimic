# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import *

#
#
#           The Nim Compiler
#        (c) Copyright 2017 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#
#

if comptime(__name__ == "__main__"):
    from nimic.std.strtabs import StringTableRef, newStringTable

    @ref
    class ConfigRef(Object):
        packageCache: StringTableRef

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
    result = ""
    with var:
        parents = 0
        _found = False
    for d in _myParentDirs(path):
        if conf.packageCache.hasKey(d):
            # echo "from cache ", d, " |", packageCache[d], "|", path.splitFile.name
            return conf.packageCache[d]
        parents += 1
        for file in walkFiles(d / "*.nimble"):
            result = file
            _found = True
            break
        if _found:
            break
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
        return "unknown"

if comptime(__name__ == "__main__"):
    with var:
        _conf = ConfigRef(packageCache=newStringTable())
    with let:
        _test_path = expandFilename(string("compiler/packagehandling.nim"))
        _nimble_file = getNimbleFile(_conf, _test_path)
    assert len(_nimble_file) > 0
    assert splitFile(_nimble_file).name == "compiler"
    assert splitFile(_nimble_file).ext == ".nimble"

    with let:
        _pkg = getPackageName(_conf, _test_path)
    assert _pkg == "compiler"

    # Cache verification
    assert _conf.packageCache.hasKey(parentDir(_test_path))
    with let:
        _cached_file = getNimbleFile(_conf, _test_path)
    assert _cached_file == _nimble_file

    # Unknown package and negative caching
    with let:
        _nonexistent = string("/tmp/nonexistent_dir_xyz_123/sub/file.nim")
        _unknown = getPackageName(_conf, _nonexistent)
    assert _unknown == "unknown"
    assert _conf.packageCache.hasKey(parentDir(_nonexistent))
    assert _conf.packageCache[parentDir(_nonexistent)] == ""
    with let:
        _cached_unknown = getNimbleFile(_conf, _nonexistent)
    assert _cached_unknown == ""

    # Direct iterator testing for _myParentDirs
    with var:
        _dirs = seq[string]()
    for d in _myParentDirs(string("/a/b/c")):
        _dirs.add(d)
    assert len(_dirs) == 3
    assert _dirs[0] == "/a/b"
    assert _dirs[1] == "/a"
    assert _dirs[2] == "/"

    with var:
        _root_count = 0
    for d in _myParentDirs(string("/")):
        _root_count += 1
    assert _root_count == 0

    echo("packagehandling tests passed successfully.")
