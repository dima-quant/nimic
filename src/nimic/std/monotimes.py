"""Nim std/monotimes — MonoTime and Duration for high-resolution timing."""
import time
from nimic.std.times import Duration

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'get_mono_time', 'MonoTime'
]

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

