# /// nimic
#
# ///
## The Phase A milestone (ncompiler/conversion_plan.md): NIF files round-trip through the converted nimony
## modules. Each `.nif` given on the command line is read with nifreader into a TokenBuf
## (`nifcoreparse.parseFromFile`) and written back as text with nifbuilder (`nifcoreparse.toString`); the text must
## parse back to the same text. The buffer is then stored as bif and loaded back (`bif.store`, `bif.load`): the
## loaded buffer must give the same text. The texts and the `.bif` go to the output directory (the last argument).
##
## tests/verify_transpiled.py (`roundtrip`) runs this in Python and as compiled Nim over nimony's `.nif` files and
## compares stdout and every output file byte for byte.
from __future__ import annotations
from nimic.ntypes import *
from nimic.std.os import extractFilename, paramCount, paramStr
from nimic.std import syncio
from ..lib import bif, nifcoreparse
from ..lib.nifreader import extractModuleSuffix


def _verdict(same: bool) -> string:
    if same:
        return string("same")
    return string("DIFFERS")


def roundTrip(path: string, outDir: string) -> bool:
    """Round-trips one file; whether its texts all agree."""
    with let:
        name = extractFilename(path)
    with var:
        buf = nifcoreparse.parseFromFile(path)
    with let:
        text = nifcoreparse.toString(buf)
    with var:
        again = nifcoreparse.parseFromBuffer(text, extractModuleSuffix(path))
    with let:
        reparsed = nifcoreparse.toString(again)
        bifFile = outDir / (name + string(".bif"))
    writeFile(outDir / (name + string(".txt")), text)
    bif.store(buf, bifFile)
    with var:
        loaded = bif.load(bifFile)
    with let:
        fromBif = nifcoreparse.toString(loaded.buf)
    writeFile(outDir / (name + string(".bif.txt")), fromBif)
    echo(name, string(": tokens "), buf.len, string(", text "), text.len, string(" bytes, reparse "),
         _verdict(reparsed == text), string(", bif "), _verdict(fromBif == text))
    return reparsed == text and fromBif == text


if comptime(__name__ == "__main__"):
    with var:
        failed = 0
    with let:
        outDir = paramStr(paramCount())
    for i in range(1, paramCount()):
        if not roundTrip(paramStr(i), outDir):
            failed += 1
    if failed > 0:
        quit(string("round trip: ") + str(failed) + string(" file(s) differ"))
