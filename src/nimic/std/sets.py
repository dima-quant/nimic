"""Nim std/sets — HashSet implementation."""
from __future__ import annotations

class HashSet(set):
    def __class_getitem__(cls, item):
        return cls

    def incl(self, elem):
        self.add(elem)

    def excl(self, elem):
        self.discard(elem)

    def contains_or_incl(self, elem):
        if elem in self:
            return True
        self.add(elem)
        return False

    containsOrIncl = contains_or_incl

    def contains(self, elem):
        return elem in self


class _InitHashSetHelper:
    def __getitem__(self, item):
        return self

    def __call__(self, *args, **kwargs) -> HashSet:
        return HashSet()


init_hash_set = _InitHashSetHelper()
initHashSet = init_hash_set
