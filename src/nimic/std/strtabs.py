"""Nim std/strtabs — StringTableRef: a string -> string table whose keys compare by its mode
(case sensitive, case insensitive, style insensitive). Iteration follows insertion order (Nim: hash
order)."""
from __future__ import annotations
from nimic.ntypes import string, NIntEnum, auto


class StringTableMode(NIntEnum):
    """Nim: StringTableMode — describes the table's operation mode."""
    modeCaseSensitive = 0  # the table is case sensitive
    modeCaseInsensitive = auto()  # the table is case insensitive
    modeStyleInsensitive = auto()  # the table is style insensitive


modeCaseSensitive = StringTableMode.modeCaseSensitive
modeCaseInsensitive = StringTableMode.modeCaseInsensitive
modeStyleInsensitive = StringTableMode.modeStyleInsensitive


def _n_norm(mode: StringTableMode, key) -> str:
    """The comparison key of `key` (Nim myhash/myCmp: cmp, cmpIgnoreCase, cmpIgnoreStyle)."""
    k = str(key)
    if mode == modeCaseInsensitive:
        return k.lower()
    if mode == modeStyleInsensitive:
        return k.replace("_", "").lower()
    return k


class StringTableRef:
    """Nim: StringTableRef."""

    def __init__(self, mode: StringTableMode = modeCaseSensitive):
        self._mode = mode
        self._data: dict[str, tuple[string, string]] = {}  # normalized key -> (key, value)

    @property
    def mode(self) -> StringTableMode:
        return self._mode

    def __len__(self) -> int:
        return len(self._data)

    @property
    def len(self) -> int:
        return len(self._data)

    def __getitem__(self, key) -> string:
        """Nim `t[key]`: KeyError if the key is missing."""
        return self._data[_n_norm(self._mode, key)][1]

    def __setitem__(self, key, value) -> None:
        k = _n_norm(self._mode, key)
        old = self._data.get(k)
        self._data[k] = (old[0] if old else string(str(key)),
                         value if isinstance(value, string) else string(str(value)))

    def getOrDefault(self, key, default=None) -> string:
        item = self._data.get(_n_norm(self._mode, key))
        if item is not None:
            return item[1]
        return default if default is not None else string("")

    get_or_default = getOrDefault

    def hasKey(self, key) -> bool:
        return _n_norm(self._mode, key) in self._data

    has_key = hasKey
    contains = hasKey
    __contains__ = hasKey

    def del_(self, key) -> None:
        """Nim: del (Python keyword: del_)."""
        self._data.pop(_n_norm(self._mode, key), None)

    def clear(self, mode: StringTableMode | None = None) -> None:
        if mode is not None:
            self._mode = mode
        self._data.clear()

    def pairs(self):
        for k, v in self._data.values():
            yield k, v

    def keys(self):
        for k, _ in self._data.values():
            yield k

    def values(self):
        for _, v in self._data.values():
            yield v

    __iter__ = keys

    def __str__(self) -> str:
        """Nim `$`: {key: value, ...}, {:} when empty."""
        if not self._data:
            return "{:}"
        return "{" + ", ".join(f"{k}: {v}" for k, v in self._data.values()) + "}"


def newStringTable(*args, mode: StringTableMode | None = None) -> StringTableRef:
    """Nim: newStringTable(mode) and newStringTable(key1, val1, key2, val2, ..., mode)."""
    items = list(args)
    if mode is None:
        mode = items.pop() if items and isinstance(items[-1], StringTableMode) else modeCaseSensitive
    result = StringTableRef(mode)
    for i in range(0, len(items) - 1, 2):
        result[items[i]] = items[i + 1]
    return result


new_string_table = newStringTable
