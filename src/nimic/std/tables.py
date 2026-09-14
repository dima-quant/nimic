"""Nim std/tables — CountTable[T] with inc() for frequency counting."""
class CountTable():
    def __init__(self, *args):
        self._dict = {}
    def __class_getitem__(cls, tp):
        self = cls.__new__(cls)
        def wrap(*args):
            cls.__init__(self, *args)
            return self
        return wrap
    def __str__(self):
        return str(self._dict)
    def inc(self, _key):
        key = repr(_key)
        if key not in self._dict:
            self._dict[key] = 0
        self._dict[key] += 1

class _GenCountTable():
    def __getitem__(self, tp):
        return CountTable[tp]

initCountTable = _GenCountTable()

class Table:
    def __init__(self, *args, **kwargs):
        self._dict = dict(*args, **kwargs)
    def __class_getitem__(cls, tp):
        return cls
    def __getitem__(self, key):
        return self._dict[key]
    def __setitem__(self, key, value):
        self._dict[key] = value
    def __contains__(self, key):
        return key in self._dict
    def __str__(self):
        return str(self._dict)