"""Nim std/atomics — atomic values, the API of Nim 2.2.4's lib/pure/concurrency/atomics.nim: MemoryOrder,
Atomic[T], AtomicFlag, load / store / exchange / compareExchange(Weak), fetchAdd / fetchSub / fetchAnd /
fetchOr / fetchXor, atomicInc / atomicDec, `+=` / `-=`, testAndSet / clear, fence / signalFence.

Each Atomic holds a Python lock, so its operations are atomic for Python threads too. The memory orders are
accepted and change nothing (Python has no weaker orders). Integer operations wrap like C11 atomics
(Atomic[uint8] 255 + 1 is 0), whatever the overflow checks say."""
from __future__ import annotations
import threading as _threading

from nimic.ntypes import NIntEnum, Object, auto, int8
from nimic.ntypesystem import _n_value_copy


class MemoryOrder(NIntEnum):
    """Specifies how non-atomic operations can be reordered around atomic operations."""
    moRelaxed = auto()
    moConsume = auto()
    moAcquire = auto()
    moRelease = auto()
    moAcquireRelease = auto()
    moSequentiallyConsistent = auto()


moRelaxed = MemoryOrder.moRelaxed
moConsume = MemoryOrder.moConsume
moAcquire = MemoryOrder.moAcquire
moRelease = MemoryOrder.moRelease
moAcquireRelease = MemoryOrder.moAcquireRelease
moSequentiallyConsistent = MemoryOrder.moSequentiallyConsistent


class Atomic[T](Object):
    """An atomic object with underlying type T (its default value: default(T))."""
    _raw: T

    @property
    def _n_guard(self) -> _threading.Lock:
        """The lock of this atomic (made on first use: an Atomic can be a view of a field)."""
        lock = self.__dict__.get("_n_lock")
        if lock is None:
            lock = self.__dict__.setdefault("_n_lock", _threading.Lock())
        return lock


class AtomicFlag(Object):
    """An atomic boolean state (testAndSet / clear)."""
    _flag: int8


def _n_value(location: Atomic):
    """The atomic's value, a copy: the field reads as a view of its slot, which the next store changes."""
    return _n_value_copy(location._raw)


def _n_set(location: Atomic, value) -> None:
    location._raw = value


def _n_typed(location: Atomic, value):
    """value as the atomic's T (a Python literal takes the type of the stored value)."""
    current = location._raw
    return type(current)(value) if hasattr(current, "plus_percent") and not isinstance(value, type(current)) else value


def load(location: Atomic, order: MemoryOrder = moSequentiallyConsistent):
    """Atomically obtains the value of the atomic object."""
    with location._n_guard:
        return _n_value(location)


def store(location: Atomic, desired, order: MemoryOrder = moSequentiallyConsistent) -> None:
    """Atomically replaces the value of the atomic object with the desired value."""
    with location._n_guard:
        _n_set(location, _n_typed(location, desired))


def exchange(location: Atomic, desired, order: MemoryOrder = moSequentiallyConsistent):
    """Atomically replaces the value with desired and returns the value it held."""
    with location._n_guard:
        result = _n_value(location)
        _n_set(location, _n_typed(location, desired))
        return result


def compareExchange(location: Atomic, expected, desired, *orders: MemoryOrder) -> bool:
    """If the value equals expected, replaces it with desired (true); else loads it into expected (false).
    `expected` is a `var T`: a cell (nint, ...) that is assigned with `<<=`. The orders: none, one, or the
    success and failure orders (Nim's two overloads)."""
    with location._n_guard:
        current = _n_value(location)
        if current != expected:
            expected <<= current
            return False
        _n_set(location, _n_typed(location, desired))
        return True


def compareExchangeWeak(location: Atomic, expected, desired, *orders: MemoryOrder) -> bool:
    """compareExchange that may fail spuriously in C; in Python it doesn't."""
    return compareExchange(location, expected, desired, *orders)


def _n_fetch(location: Atomic, value, op):
    with location._n_guard:
        result = _n_value(location)
        _n_set(location, op(result, _n_typed(location, value)))
        return result


def fetchAdd(location: Atomic, value, order: MemoryOrder = moSequentiallyConsistent):
    """Atomically adds value (wrapping) and returns the value before."""
    return _n_fetch(location, value, lambda a, b: a.plus_percent(b))


def fetchSub(location: Atomic, value, order: MemoryOrder = moSequentiallyConsistent):
    """Atomically subtracts value (wrapping) and returns the value before."""
    return _n_fetch(location, value, lambda a, b: a.minus_percent(b))


def fetchAnd(location: Atomic, value, order: MemoryOrder = moSequentiallyConsistent):
    """Atomically replaces the value with `value and it` and returns the value before."""
    return _n_fetch(location, value, lambda a, b: a & b)


def fetchOr(location: Atomic, value, order: MemoryOrder = moSequentiallyConsistent):
    """Atomically replaces the value with `value or it` and returns the value before."""
    return _n_fetch(location, value, lambda a, b: a | b)


def fetchXor(location: Atomic, value, order: MemoryOrder = moSequentiallyConsistent):
    """Atomically replaces the value with `value xor it` and returns the value before."""
    return _n_fetch(location, value, lambda a, b: a ^ b)


def atomicInc(location: Atomic, value=1) -> None:
    """Atomically increments the atomic integer by some value."""
    fetchAdd(location, value)


def atomicDec(location: Atomic, value=1) -> None:
    """Atomically decrements the atomic integer by some value."""
    fetchSub(location, value)


def _atomic_iadd(location: Atomic, value) -> Atomic:
    """Nim: `+=` of an atomic (fetchAdd)."""
    fetchAdd(location, value)
    return location


def _atomic_isub(location: Atomic, value) -> Atomic:
    """Nim: `-=` of an atomic (fetchSub)."""
    fetchSub(location, value)
    return location


Atomic.__iadd__ = _atomic_iadd
Atomic.__isub__ = _atomic_isub


def testAndSet(location: AtomicFlag, order: MemoryOrder = moSequentiallyConsistent) -> bool:
    """Atomically sets the flag and returns whether it was set before."""
    with _n_flag_lock:
        was = int(location._flag) != 0
        location._flag = 1
        return was


def clear(location: AtomicFlag, order: MemoryOrder = moSequentiallyConsistent) -> None:
    """Atomically clears the flag."""
    with _n_flag_lock:
        location._flag = 0


_n_flag_lock = _threading.Lock()


def fence(order: MemoryOrder) -> None:
    """Ensures memory ordering without using atomic operations (nothing to do in Python)."""


def signalFence(order: MemoryOrder) -> None:
    """Prevents reordering of accesses by the compiler as would fence, but inserts no CPU instructions."""
