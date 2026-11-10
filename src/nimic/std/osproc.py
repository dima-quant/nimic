"""Nim std/osproc (nimony's lib/std/osproc) — running commands: execCmdEx."""
from __future__ import annotations
import subprocess as _subprocess
from nimic.ntypes import nint, string
from nimic.ntypesystem import _n_os_arg

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'execCmdEx'
]


def execCmdEx(command: string, workingDir: string = string(""), input: string = string("")) -> tuple:
    """Nim: execCmdEx(command, workingDir = "", input = "") — runs `command` through the shell (stderr into
    stdout); its output and exit code."""
    p = _subprocess.run(_n_os_arg(command), shell=True, cwd=_n_os_arg(workingDir) or None,
                        input=str(input).encode("latin-1"), stdout=_subprocess.PIPE, stderr=_subprocess.STDOUT)
    return string(p.stdout.decode("latin-1")), nint(p.returncode)
