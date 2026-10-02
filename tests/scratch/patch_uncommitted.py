import sys

def replace_first(text, search, replacement):
    idx = text.find(search)
    if idx == -1:
        print(f"Warning: could not find snippet:\n{search[:100]}...")
        return text
    return text[:idx] + replacement + text[idx+len(search):]

with open('src/nimic/ntypesystem.py', 'r') as f:
    code = f.read()

# 1. get_or_eval_type
code = replace_first(code, 
"""    def get_or_eval_type(self, t_name: str, caller_globals: dict | None = None) -> type:
        if t_name in self.types:
            return self.types[t_name]
        # t_name is not in self.types, so needs to be resolved and registered.""",
"""    def get_or_eval_type(self, t_name: str, caller_globals: dict | None = None) -> type:
        if t_name in self.types:
            return self.types[t_name]
        if caller_globals and t_name in caller_globals:
            return caller_globals[t_name]
        # t_name is not in self.types, so needs to be resolved and registered.""")

# 2. Add Trange and Tset definitions before class Object
idx_object = code.find("class Object(metaclass=Ntype):")
if idx_object != -1:
    trange_tset = """
class Trange(int):
    @classmethod
    def __class_getitem__(cls, params):
        start, end = params
        class _Trange(cls):
            _n_start = start
            _n_end = end
            @classmethod
            def first(cls): return cls._n_start
            @classmethod
            def last(cls): return cls._n_end
            @classmethod
            def _n_register_type(cls): pass
        _Trange.__name__ = f"Trange[{start}, {end}]"
        DICT_OF_TYPES[_Trange.__name__] = _Trange
        return _Trange

class Tset(set):
    @classmethod
    def __class_getitem__(cls, item):
        class _Tset(cls):
            _n_type = item
            @classmethod
            def _n_register_type(cls): pass
            
            def __sub__(self, other): return self.__class__(super().__sub__(other))
            def __or__(self, other): return self.__class__(super().__or__(other))
            def __and__(self, other): return self.__class__(super().__and__(other))
            def __xor__(self, other): return self.__class__(super().__xor__(other))
        _Tset.__name__ = f"Tset[{item.__name__}]"
        DICT_OF_TYPES[_Tset.__name__] = _Tset
        return _Tset

"""
    code = code[:idx_object] + trange_tset + code[idx_object:]

# 3. array __class_getitem__
code = replace_first(code,
"""        # n can be ordinal
        if _ntype.__name__ not in DICT_OF_TYPES and hasattr(_ntype, '_n_register_type'):""",
"""        # n can be ordinal
        if isinstance(n, type) and issubclass(n, Enum):
            n_val = len(n)
        elif isinstance(n, type) and issubclass(n, Trange):
            n_val = int(n.last()) - int(n.first()) + 1
        else:
            n_val = int(n)

        if _ntype.__name__ not in DICT_OF_TYPES and hasattr(_ntype, '_n_register_type'):""")

code = replace_first(code,
"""arr_type = type(class_name, (array,), {"_n_type": _ntype, "_n_size": n})""",
"""arr_type = type(class_name, (array,), {"_n_type": _ntype, "_n_size": n_val})""")

# 4. array __init__ dict support
code = replace_first(code,
"""    def __init__(self, it: Sequence | None = None) -> None:
        self._n_cache = {}
        if hasattr(self, "_n_type") and hasattr(self, "_n_size"):
            class_name = f"array[{self._n_size}, {self._n_type.__name__}]"
            if class_name in DICT_OF_C_TYPES:
                self._n_backing = DICT_OF_C_TYPES[class_name]()
                self._n_owned_addr = BUFFER_REGISTRY.register(self._n_backing)
                self._n_view = DICT_OF_C_TYPES[class_name].from_address(
                    ctypes.addressof(self._n_backing)
                )
                if it is not None:
                    for index in range(self._n_size):
                        self._n_view[index] = it[index]
            else:
                # Scalar/simple types: use a plain Python list as backing store
                if it is not None:
                    self._n_cache = {j: self._n_type() for j in range(self._n_size)}
                    for index in range(self._n_size):
                        self._n_cache[index] = it[index]
                else:
                    self._n_cache = {j: self._n_type() for j in range(self._n_size)}""",
"""    def __init__(self, it: Sequence | dict | None = None) -> None:
        self._n_cache = {}
        if hasattr(self, "_n_type") and hasattr(self, "_n_size"):
            class_name = f"array[{self._n_size}, {self._n_type.__name__}]"
            if class_name in DICT_OF_C_TYPES:
                self._n_backing = DICT_OF_C_TYPES[class_name]()
                self._n_owned_addr = BUFFER_REGISTRY.register(self._n_backing)
                self._n_view = DICT_OF_C_TYPES[class_name].from_address(
                    ctypes.addressof(self._n_backing)
                )
                if it is not None:
                    if isinstance(it, dict):
                        for key, value in it.items():
                            self._n_view[int(key)] = value
                    else:
                        for index in range(self._n_size):
                            self._n_view[index] = it[index]
            else:
                # Scalar/simple types: use a plain Python list as backing store
                if it is not None:
                    if isinstance(it, dict):
                        self._n_cache = {j: self._n_type() for j in range(self._n_size)}
                        for key, value in it.items():
                            self._n_cache[int(key)] = value
                    else:
                        for index in range(self._n_size):
                            self._n_cache[index] = it[index]
                else:
                    self._n_cache = {j: self._n_type() for j in range(self._n_size)}""")

# 5. Enum import
if "from enum import IntEnum, Enum" not in code:
    code = replace_first(code, "from enum import IntEnum", "from enum import IntEnum, Enum")

# 6. NIntEnum first and last
code = replace_first(code,
"""class NIntEnum(IntEnum):
    @classmethod
    def _n_set_indices(cls) -> None:
        cls._n_indices = {val: ind for ind, val in enumerate(cls)}""",
"""class NIntEnum(IntEnum):
    @classmethod
    def _n_set_indices(cls) -> None:
        cls._n_members_tuple = tuple(cls)
        cls._n_indices = {val: ind for ind, val in enumerate(cls._n_members_tuple)}

    @classmethod
    def first(cls):
        if not hasattr(cls, '_n_members_tuple'):
            cls._n_set_indices()
        return cls._n_members_tuple[0]

    @classmethod
    def last(cls):
        if not hasattr(cls, '_n_members_tuple'):
            cls._n_set_indices()
        return cls._n_members_tuple[-1]""")


with open('src/nimic/ntypesystem.py', 'w') as f:
    f.write(code)

print("Applied patches successfully.")
