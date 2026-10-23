"""Nim std/times — Time (a point in time: seconds and nanoseconds since the Unix epoch), DateTime (calendar
time), Duration, getTime, toUnix, fromUnix, nanosecond, utc / local, format, epochTime."""
from __future__ import annotations
import time as _time
from datetime import datetime as _pydatetime, timezone as _timezone
from nimic.ntypes import string, dispatch


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


class Time:
    """Nim Time — a point in time: seconds since the Unix epoch and the nanosecond within the second."""

    __slots__ = ("_seconds", "_nanosecond")

    def __init__(self, seconds: int = 0, nanosecond: int = 0):
        self._seconds = int(seconds)
        self._nanosecond = int(nanosecond)

    @property
    def nanosecond(self) -> int:
        """Nim: t.nanosecond — the nanoseconds within the second, 0 ..< 1_000_000_000."""
        return self._nanosecond

    def to_unix(self) -> int:
        """Nim: toUnix — whole seconds since the Unix epoch."""
        return self._seconds

    def _n_ns(self) -> int:
        return self._seconds * 1_000_000_000 + self._nanosecond

    def __sub__(self, other: "Time") -> Duration:
        return Duration(self._n_ns() - other._n_ns())

    def __eq__(self, other) -> bool:
        return isinstance(other, Time) and self._n_ns() == other._n_ns()

    def __lt__(self, other: "Time") -> bool:
        return self._n_ns() < other._n_ns()

    def __le__(self, other: "Time") -> bool:
        return self._n_ns() <= other._n_ns()

    def __hash__(self) -> int:
        return hash(self._n_ns())

    def __repr__(self) -> str:
        return f"Time({self._seconds}s, {self._nanosecond}ns)"


def _n_time_from_ns(ns: int) -> Time:
    return Time(ns // 1_000_000_000, ns % 1_000_000_000)


def get_time() -> Time:
    """Nim: getTime — the current time (nanosecond resolution)."""
    return _n_time_from_ns(_time.time_ns())

getTime = get_time


def toUnix(t: Time) -> int:
    """Nim: toUnix — whole seconds since the Unix epoch."""
    return t.to_unix()

to_unix = toUnix


def nanosecond(t: Time) -> int:
    """Nim: nanosecond(t) — the nanoseconds within the second."""
    return t.nanosecond


def from_unix(ts: int) -> Time:
    """Nim: fromUnix — the Time of a Unix timestamp in seconds."""
    return Time(int(ts))

fromUnix = from_unix


def utc(t: Time | DateTime | None = None) -> DateTime:
    """Nim: utc — the DateTime of a Time (now without one)."""
    if t is None:
        t = get_time()
    return DateTime(t.to_unix()) if isinstance(t, Time) else t


def local(t: Time | DateTime | None = None) -> DateTime:
    """Nim: local — the DateTime of a Time in local time (now without one)."""
    return utc(t)


@dispatch
def format(dt: DateTime, fmt: string) -> string:
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

@dispatch
def format(t: Time, fmt: string) -> string:
    """Nim: format(time, f) — the Time formatted as its DateTime (local)."""
    return format(local(t), fmt)


format_time = format


def epochTime() -> float:
    """Nim: epochTime — seconds since the Unix epoch as a float."""
    return _time.time()



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