# /// nimic
#
# ///
## A module-level variable a routine touches (rule:global): `global runs` in each routine that reads or assigns it.
## Python needs it to assign the module's variable; the transpiler drops it and runs the routine's statements in
## the prelude's `assumeSync:` block (nimony's `{.cast(assumeSync).}`, which nimony requires for a mutable global,
## read or written). tests/verify_transpiled.py nimic compares the outputs of Python and compiled Nim.
from __future__ import annotations
from nimic.ntypes import *

with var:
    runs = nint(0)
    log = seq[string]()


def step(n: nint):
    global runs, log
    runs += n
    log.add(string("step ") + str(n))


def reset_runs():
    global runs
    runs = nint(0)


def peek() -> nint:
    global runs
    return runs


if comptime(__name__ == "__main__"):
    step(nint(2))
    step(nint(3))
    echo(peek(), string(" "), log.len)
    reset_runs()
    step(nint(1))
    echo(peek(), string(" "), log)
