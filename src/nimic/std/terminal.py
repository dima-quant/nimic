"""Nim std/terminal — terminal handling utilities."""
from __future__ import annotations
import sys


def is_atty(f=sys.stderr) -> bool:
    """Nim: isatty — returns true if f refers to a terminal."""
    try:
        return hasattr(f, "isatty") and f.isatty()
    except (ValueError, OSError):  # closed or detached stream
        return False


isatty = is_atty
