"""Nim std/tables — Table[K, V] and CountTable[T]."""
from nimic.ntypesystem import DICT_OF_TYPES, Object


class CountTable(Object):
    def __init__(self, *args):
        self._dict = {}

    def __class_getitem__(cls, tp):
        return type(f"CountTable[{tp}]", (CountTable,), {})

    def __str__(self):
        return str(self._dict)

    def inc(self, _key):
        key = repr(_key)
        if key not in self._dict:
            self._dict[key] = 0
        self._dict[key] += 1


class _GenCountTable:
    def __getitem__(self, tp):
        return CountTable[tp]


initCountTable = _GenCountTable()


class Table(Object):
    def __init__(self, *args, **kwargs):
        self._dict = dict(*args, **kwargs)

    def __class_getitem__(cls, tp):
        return type(f"Table[{tp}]", (Table,), {})

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, value):
        self._dict[key] = value

    def __contains__(self, key):
        return key in self._dict

    def __len__(self):
        return len(self._dict)

    def get(self, key, default=None):
        return self._dict.get(key, default)

    getOrDefault = get
    get_or_default = get

    def hasKey(self, key):
        return key in self._dict

    has_key = hasKey

    def __str__(self):
        return str(self._dict)


class _GenTable:
    def __getitem__(self, tp):
        return Table[tp]

    def __call__(self, *args, **kwargs):
        return Table(*args, **kwargs)


initTable = _GenTable()
init_table = initTable

DICT_OF_TYPES["Table"] = Table
DICT_OF_TYPES["CountTable"] = CountTable