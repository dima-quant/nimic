"""Nim std/tables — Table[K, V], OrderedTable[K, V], TableRef[K, V] and CountTable[T].

The tables are generic objects (`class Table[K, V](Object)`): `Table[string, nint]` is one cached,
registered specialization, so a generic proc over `Table[A, B]` binds A and B from its argument."""
from nimic.ntypesystem import DICT_OF_TYPES, Object, _n_default_value, _n_value_copy


class CountTable[T](Object):
    def __init__(self, *args):
        self._n_dict = {}

    def __str__(self):
        return str(self._n_dict)

    def _n_contents(self):
        """What the table holds, for a fingerprint (nimic.ntypesystem._n_fingerprint): its entries."""
        return self._n_dict

    def inc(self, _key):
        key = repr(_key)
        if key not in self._n_dict:
            self._n_dict[key] = 0
        self._n_dict[key] += 1


class _GenCountTable:
    def __getitem__(self, tp):
        return CountTable[tp]


initCountTable = _GenCountTable()


class _NTable(Object):
    """The implementation of Table, OrderedTable and TableRef: a Python dict holds the entries (it keeps
    insertion order, as OrderedTable does). In Nim they are three unrelated types, so neither derives from
    another: a proc over Table[A, B] doesn't take an OrderedTable."""

    def __init__(self, *args, **kwargs):
        self._n_dict = dict(*args, **kwargs)

    def __class_getitem__(cls, params):
        specialized = super().__class_getitem__(params)
        if isinstance(params, tuple) and len(params) == 2 and "_n_value_type" not in specialized.__dict__:
            specialized._n_key_type, specialized._n_value_type = params  # the classes, for default(V)
        return specialized

    def __getitem__(self, key):
        return self._n_dict[key]

    def __setitem__(self, key, value):
        self._n_dict[key] = value

    def __contains__(self, key):
        return key in self._n_dict

    def __len__(self):
        return len(self._n_dict)

    def getOrDefault(self, key, *default):
        """Nim: t.getOrDefault(k) is default(V) for a missing key; t.getOrDefault(k, d) is d."""
        if key in self._n_dict:
            return self._n_dict[key]
        if default:
            return default[0]
        return _n_default_value(getattr(type(self), "_n_value_type", None))

    get_or_default = getOrDefault

    def get(self, key, default=None):
        return self._n_dict.get(key, default)

    def hasKey(self, key):
        return key in self._n_dict

    has_key = hasKey

    def __str__(self):
        return str(self._n_dict)

    def _n_contents(self):
        """What the table holds, for a fingerprint (nimic.ntypesystem._n_fingerprint): its entries."""
        return self._n_dict

    def copy(self, deep: bool = True):
        """Nim's copy of a table value: its entries, value entries copied and refs shared (`var t2 = t`)."""
        result = type(self)()
        result._n_dict = {k: _n_value_copy(v) for k, v in self._n_dict.items()}
        return result

    def __ilshift__(self, other):
        """Nim `t = other` into an existing table: replaces its entries by copies of other's."""
        if other is not self:
            self._n_dict = {k: _n_value_copy(v) for k, v in other._n_dict.items()}
        return self


class Table[K, V](_NTable):
    """Nim: Table[K, V]."""


class _GenTable:
    def __getitem__(self, tp):
        return Table[tp]

    def __call__(self, *args, **kwargs):
        return Table(*args, **kwargs)


initTable = _GenTable()
init_table = initTable


class OrderedTable[K, V](_NTable):
    """Nim: OrderedTable[K, V], a table that iterates in insertion order (as every Python dict)."""


class _GenOrderedTable:
    def __getitem__(self, tp):
        return OrderedTable[tp]

    def __call__(self, *args, **kwargs):
        return OrderedTable(*args, **kwargs)


initOrderedTable = _GenOrderedTable()


class TableRef[K, V](_NTable):
    """Nim: TableRef[K, V] — a table with reference semantics (assignment shares it)."""
    _n_is_ref = True


class _GenNewTable:
    def __getitem__(self, tp):
        return TableRef[tp]

    def __call__(self, *args, **kwargs):
        return TableRef(*args, **kwargs)


newTable = _GenNewTable()

DICT_OF_TYPES["Table"] = Table
DICT_OF_TYPES["OrderedTable"] = OrderedTable
DICT_OF_TYPES["TableRef"] = TableRef
DICT_OF_TYPES["CountTable"] = CountTable
