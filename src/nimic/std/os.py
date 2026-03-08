"""Nim system/io and os — file mode constants and OS utilities."""
from __future__ import annotations
import os as _os
from sys import stdout, stderr
import sys
from io import TextIOWrapper


    # "r", "rb":
fmRead = "r"
    # "w", "wb":
fmWrite = "w"
    # "a", "ab":
fmAppend = "a"
    # "r+", "rb+":
fmReadWriteExisting = "r+"
    # "w+", "wb+":
fmReadWrite = "w+"


def create_dir(dir: str) -> None:
    """Create directory and parents if needed (Nim: os.createDir)."""
    _os.makedirs(dir, exist_ok=True)
