from __future__ import annotations
from typing import Iterator
from nimic.ntypes import nint

class IntSet:
    def __init__(self, elements=None):
        self._data = set(int(x) for x in elements) if elements else set()

    def incl(self, elem: nint) -> None:
        self._data.add(int(elem))

    def excl(self, elem: nint) -> None:
        self._data.discard(int(elem))

    def contains(self, elem: nint) -> bool:
        return int(elem) in self._data

    def containsOrIncl(self, elem: nint) -> bool:
        v = int(elem)
        if v in self._data:
            return True
        self._data.add(v)
        return False

    def __contains__(self, elem: nint) -> bool:
        return int(elem) in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[nint]:
        return iter(self._data)

    def __repr__(self) -> str:
        return f"IntSet({self._data})"


def init_int_set() -> IntSet:
    return IntSet()


initIntSet = init_int_set


def contains_or_incl(s: IntSet, key: nint) -> bool:
    return s.containsOrIncl(key)


containsOrIncl = contains_or_incl


def incl(s: IntSet, key: nint) -> None:
    s.incl(key)


def excl(s: IntSet, key: nint) -> None:
    s.excl(key)


def contains(s: IntSet, key: nint) -> bool:
    return s.contains(key)
