"""Nim std/monotimes — MonoTime and Duration for high-resolution timing."""
import time


class Duration:
    """Nim Duration — a time span stored in nanoseconds."""

    __slots__ = ("_ns",)

    def __init__(self, nanoseconds: int):
        self._ns = nanoseconds

    def __sub__(self, other: "Duration") -> "Duration":
        return Duration(self._ns - other._ns)

    def __add__(self, other: "Duration") -> "Duration":
        return Duration(self._ns + other._ns)

    def __repr__(self) -> str:
        return f"Duration({self._ns}ns)"


class MonoTime:
    """Nim MonoTime — a monotonic time point."""

    __slots__ = ("_ns",)

    def __init__(self, nanoseconds: int):
        self._ns = nanoseconds

    def __sub__(self, other: "MonoTime") -> Duration:
        return Duration(self._ns - other._ns)

    def __repr__(self) -> str:
        return f"MonoTime({self._ns}ns)"


def get_mono_time() -> MonoTime:
    """Return the current monotonic time (Nim: getMonoTime())."""
    return MonoTime(time.monotonic_ns())


def in_milliseconds(dur: Duration) -> int:
    """Convert a Duration to whole milliseconds (Nim: inMilliseconds)."""
    return dur._ns // 1_000_000


def in_microseconds(dur: Duration) -> int:
    """Convert a Duration to whole microseconds (Nim: inMicroseconds)."""
    return dur._ns // 1_000


def in_seconds(dur: Duration) -> int:
    """Convert a Duration to whole seconds (Nim: inSeconds)."""
    return dur._ns // 1_000_000_000
