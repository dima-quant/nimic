"""Nim std/terminal — terminal handling utilities."""
from __future__ import annotations
import sys


def is_atty(f=sys.stderr) -> bool:
    """Nim: isatty — returns true if f refers to a terminal."""
    try:
        if hasattr(f, "isatty"):
            return f.isatty()
        return False
    except Exception:
        return False


isatty = is_atty
