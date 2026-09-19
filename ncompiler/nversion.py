# /// nimic

# ///
from __future__ import annotations
from nimic.ntypes import *

#
#
#           The Nim Compiler
#        (c) Copyright 2015 Andreas Rumpf
#
#    See the file "copying.txt", included in this
#    distribution, for details about the copyright.
#
#

# This module contains Nim's version. It is the only place where it needs
# to be changed.

with const:
    MaxSetElements = 1 << 16  # (2^16) to support unicode character sets?
    DefaultSetElements = 1 << 8
    # assumed set element count when using int literals
    VersionAsString = system.NimVersion
    RodFileVersion = "1223"  # modify this if the rod-format changes!

    NimCompilerApiVersion = 3  # Check for the existence of this before accessing it
    # as older versions of the compiler API do not
    # declare this.

if comptime(__name__ == "__main__"):
    with let:
        _v = VersionAsString
    assert MaxSetElements == 65536
    assert DefaultSetElements == 256
    assert MaxSetElements > DefaultSetElements
    assert MaxSetElements - 1 == 65535
    assert DefaultSetElements - 1 == 255
    assert len(_v) > 0
    assert _v == system.NimVersion
    assert RodFileVersion == "1223"
    assert NimCompilerApiVersion == 3
    echo("nversion test passed: VersionAsString = ", _v)

