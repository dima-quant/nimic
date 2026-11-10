"""Nim std/packedsets — PackedSet[A], a sparse bit set over an ordinal type (nimony's lib/std/packedsets).

An element's ordinal value, cast to uint, is its bit position. Positions are grouped into trunks of
`_BITS_PER_TRUNK` bits; as in nimony, `items` yields the trunks in the order they were first touched (nimony's
Table is insertion-ordered) and ascending within a trunk, and a trunk emptied by `excl` keeps its place. So the
iteration order, which the converted lengc writes into its C output, is nimony's."""
from __future__ import annotations
from typing import Iterator
from nimic.ntypesystem import Object, nint

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'card', 'clear', 'containsOrIncl', 'difference', 'disjoint', 'excl', 'incl', 'initPackedSet', 'intersection',
    'missingOrExcl', 'PackedSet', 'symmetricDifference', 'toPackedSet', 'union'
]

_UINT_BITS = 64
_BITS_PER_TRUNK = 8 * _UINT_BITS  # TrunkSize words of one uint each
_UINT_MASK = (1 << _UINT_BITS) - 1


def _split(key) -> tuple[int, int]:
    """The key's trunk and its bit within the trunk (nimony: `split(bitPos(key))`, the cast to uint included)."""
    pos = int(key) & _UINT_MASK
    return pos // _BITS_PER_TRUNK, pos % _BITS_PER_TRUNK


class PackedSet[A](Object):
    """Nim: PackedSet[A: Ordinal]. `_n_trunks` maps a trunk key to its bits (a Python int of
    `_BITS_PER_TRUNK` bits), in the order the trunks were added."""

    def __init__(self, *args):
        self._n_trunks: dict[int, int] = {}

    def __class_getitem__(cls, params):
        specialized = super().__class_getitem__(params)
        if "_n_elem_type" not in specialized.__dict__:
            specialized._n_elem_type = params  # the class, for `A(i)` in items
        return specialized

    def _n_element(self, pos: int):
        """The element at bit position `pos` (nimony: `A(cast[int](pos))`)."""
        value = pos - (1 << _UINT_BITS) if pos >> (_UINT_BITS - 1) else pos
        elem_type = getattr(type(self), "_n_elem_type", None)
        return nint(value) if elem_type is None or isinstance(elem_type, str) else elem_type(value)

    def contains(self, key) -> bool:
        trunk, bit = _split(key)
        return bool(self._n_trunks.get(trunk, 0) >> bit & 1)

    def __contains__(self, key) -> bool:
        return self.contains(key)

    def containsOrIncl(self, key) -> bool:
        """Includes `key`; true if it was in the set already."""
        trunk, bit = _split(key)
        bits = self._n_trunks.get(trunk, 0)
        self._n_trunks[trunk] = bits | 1 << bit
        return bool(bits >> bit & 1)

    def missingOrExcl(self, key) -> bool:
        """Excludes `key`; true if it wasn't in the set. Excluding never adds a trunk."""
        trunk, bit = _split(key)
        if trunk not in self._n_trunks:
            return True
        bits = self._n_trunks[trunk]
        self._n_trunks[trunk] = bits & ~(1 << bit)
        return not bits >> bit & 1

    def incl(self, key) -> None:
        """Nim: incl(s, key), and incl(s, other) for every element of another PackedSet."""
        if isinstance(key, PackedSet):
            for item in key:
                self.containsOrIncl(item)
        else:
            self.containsOrIncl(key)

    def excl(self, key) -> None:
        """Nim: excl(s, key), and excl(s, other) for every element of another PackedSet."""
        if isinstance(key, PackedSet):
            for item in key:
                self.missingOrExcl(item)
        else:
            self.missingOrExcl(key)

    def __iter__(self) -> Iterator:
        for trunk, bits in self._n_trunks.items():
            base = trunk * _BITS_PER_TRUNK
            while bits:
                low = bits & -bits
                yield self._n_element(base + low.bit_length() - 1)
                bits ^= low

    def items(self) -> Iterator:
        return iter(self)

    def __len__(self) -> int:
        return sum(bits.bit_count() for bits in self._n_trunks.values())

    def card(self) -> nint:
        return nint(len(self))

    def clear(self) -> None:
        self._n_trunks.clear()

    def copy(self, deep: bool = True) -> PackedSet:
        """Nim's copy of a PackedSet value (`var t = s`): its own trunks."""
        result = type(self)()
        result._n_trunks = dict(self._n_trunks)
        return result

    def __ilshift__(self, other):
        """Nim `s = other` into an existing set."""
        if other is not self:
            self._n_trunks = dict(other._n_trunks)
        return self

    def _n_contents(self):
        """What the set holds, for a fingerprint (nimic.ntypesystem._n_fingerprint): its trunks."""
        return self._n_trunks

    def __le__(self, other: PackedSet) -> bool:
        return all(other.contains(item) for item in self)

    def __lt__(self, other: PackedSet) -> bool:
        return self <= other and not other <= self

    def __eq__(self, other) -> bool:
        return isinstance(other, PackedSet) and self <= other and other <= self

    __hash__ = None

    def __add__(self, other: PackedSet) -> PackedSet:
        return union(self, other)

    def __mul__(self, other: PackedSet) -> PackedSet:
        return intersection(self, other)

    def __sub__(self, other: PackedSet) -> PackedSet:
        return difference(self, other)

    def __str__(self) -> str:
        return "{" + ", ".join(str(item) for item in self) + "}"


class _GenInitPackedSet:
    """`initPackedSet[A]()`: an empty PackedSet[A]."""

    def __getitem__(self, tp):
        return PackedSet[tp]

    def __call__(self) -> PackedSet:
        return PackedSet()


initPackedSet = _GenInitPackedSet()


def toPackedSet(x) -> PackedSet:
    """A PackedSet of the elements of `x`, of their type (that of the first one; nint for an empty `x`)."""
    items = list(x)
    result = PackedSet[type(items[0])]() if items else PackedSet()
    for item in items:
        result.incl(item)
    return result


def incl(s: PackedSet, key) -> None:
    s.incl(key)


def excl(s: PackedSet, key) -> None:
    s.excl(key)


def containsOrIncl(s: PackedSet, key) -> bool:
    return s.containsOrIncl(key)


def missingOrExcl(s: PackedSet, key) -> bool:
    return s.missingOrExcl(key)


def card(s: PackedSet) -> nint:
    return s.card()


def clear(s: PackedSet) -> None:
    s.clear()


def union(s1: PackedSet, s2: PackedSet) -> PackedSet:
    result = s1.copy()
    result.incl(s2)
    return result


def intersection(s1: PackedSet, s2: PackedSet) -> PackedSet:
    result = type(s1)()
    for item in s1:
        if s2.contains(item):
            result.incl(item)
    return result


def difference(s1: PackedSet, s2: PackedSet) -> PackedSet:
    result = type(s1)()
    for item in s1:
        if not s2.contains(item):
            result.incl(item)
    return result


def symmetricDifference(s1: PackedSet, s2: PackedSet) -> PackedSet:
    result = s1.copy()
    for item in s2:
        if result.containsOrIncl(item):
            result.excl(item)
    return result


def disjoint(s1: PackedSet, s2: PackedSet) -> bool:
    return not any(s2.contains(item) for item in s1)
