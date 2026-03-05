"""Nim system/io — file mode constants (fmRead, fmWrite, etc.) mapped to Python open() modes."""
from __future__ import annotations
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
