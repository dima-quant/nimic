"""Nim std/times — DateTime, get_time(), and to_unix() for calendar time."""
import time as _time


class DateTime:
    """Nim DateTime — represents a point in calendar time."""

    __slots__ = ("_unix",)

    def __init__(self, unix_seconds: int):
        self._unix = unix_seconds

    def to_unix(self) -> int:
        """Return the Unix timestamp (seconds since 1970-01-01 UTC)."""
        return self._unix

    def __repr__(self) -> str:
        return f"DateTime(unix={self._unix})"


def get_time() -> DateTime:
    """Return the current calendar time (Nim: getTime())."""
    return DateTime(int(_time.time()))
