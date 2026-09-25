"""Nim std/times — DateTime, get_time(), and to_unix() for calendar time."""
from __future__ import annotations
import time as _time
from datetime import datetime as _pydatetime, timezone as _timezone
from nimic.ntypes import string


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

    def __init__(self, unix_seconds: int = 0):
        self._unix = unix_seconds

    def to_unix(self) -> int:
        """Return the Unix timestamp (seconds since 1970-01-01 UTC)."""
        return self._unix

    def __repr__(self) -> str:
        return f"DateTime(unix={self._unix})"


Time = DateTime


def get_time() -> DateTime:
    """Return the current calendar time (Nim: getTime())."""
    return DateTime(int(_time.time()))

getTime = get_time


def from_unix(ts: int) -> DateTime:
    """Return DateTime from unix timestamp in seconds (Nim: fromUnix)."""
    return DateTime(int(ts))

fromUnix = from_unix


def utc(dt: DateTime | None = None) -> DateTime:
    """Return DateTime in UTC (Nim: utc)."""
    if dt is None:
        return get_time()
    return dt


def local(dt: DateTime | None = None) -> DateTime:
    """Return DateTime in local time (Nim: local)."""
    if dt is None:
        return get_time()
    return dt


def format_time(dt: DateTime, fmt: str | string) -> string:
    """Format a DateTime using a format string (Nim: format)."""
    py_fmt = str(fmt)
    py_fmt = py_fmt.replace("yyyy", "%Y")
    py_fmt = py_fmt.replace("MM", "%m")
    py_fmt = py_fmt.replace("dd", "%d")
    py_fmt = py_fmt.replace("HH", "%H")
    py_fmt = py_fmt.replace("mm", "%M")
    py_fmt = py_fmt.replace("ss", "%S")
    t = _pydatetime.fromtimestamp(dt._unix, tz=_timezone.utc)
    return string(t.strftime(py_fmt))

format = format_time



def in_milliseconds(dur: Duration) -> int:
    """Convert a Duration to whole milliseconds (Nim: inMilliseconds)."""
    return dur._ns // 1_000_000

inMilliseconds = in_milliseconds


def in_microseconds(dur: Duration) -> int:
    """Convert a Duration to whole microseconds (Nim: inMicroseconds)."""
    return dur._ns // 1_000

inMicroseconds = in_microseconds


def in_seconds(dur: Duration) -> int:
    """Convert a Duration to whole seconds (Nim: inSeconds)."""
    return dur._ns // 1_000_000_000

inSeconds = in_seconds