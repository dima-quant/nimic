"""Nim std/strtabs — StringTableRef implementation."""
from __future__ import annotations
from collections import UserDict
from nimic.ntypes import string

class StringTableRef(UserDict):
    def hasKey(self, key) -> bool:
        return str(key) in self.data or key in self.data

    has_key = hasKey

    def __getitem__(self, key):
        k = str(key)
        if k in self.data:
            return self.data[k]
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[str(key)] = string(value) if not isinstance(value, string) else value

    def get_or_default(self, key, default=string("")):
        k = str(key)
        if k in self.data:
            return self.data[k]
        if key in self.data:
            return self.data[key]
        return default

    getOrDefault = get_or_default


def newStringTable(*args, **kwargs) -> StringTableRef:
    return StringTableRef()

new_string_table = newStringTable
