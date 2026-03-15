"""Nim std/times — DateTime, get_time(), and to_unix() for calendar time."""
import time as _time

class Duration:
    """Nim Duration — a time span stored in nanoseconds."""

    __slots__ = ("_ns",)

    def __init__(self, nanoseconds: int = 0):
        self._ns = nanoseconds

    def __sub__(self, other: "Duration") -> "Duration":
        return Duration(self._ns - other._ns)

    def __add__(self, other: "Duration") -> "Duration":
        return Duration(self._ns + other._ns)

    def __repr__(self) -> str:
        return f"Duration({self._ns}ns)"

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

def in_milliseconds(dur: Duration) -> int:
    """Convert a Duration to whole milliseconds (Nim: inMilliseconds)."""
    return dur._ns // 1_000_000


def in_microseconds(dur: Duration) -> int:
    """Convert a Duration to whole microseconds (Nim: inMicroseconds)."""
    return dur._ns // 1_000


def in_seconds(dur: Duration) -> int:
    """Convert a Duration to whole seconds (Nim: inSeconds)."""
    return dur._ns // 1_000_000_000