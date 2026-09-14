import sys

with open('src/nimic/ntypesystem.py', 'r') as f:
    code = f.read()

# 1. pointer._n_on_array
target_pointer = """    @classmethod
    def _n_on_array(cls, parent_elems, index, value: int=None):
        \"\"\"Array-embedded pointer: reads address from parent's ctypes array slot.\"\"\"
        self = cls.__new__(cls)
        self._n_contents_cache = None
        base_addr = ctypes.addressof(parent_elems.contents) if hasattr(parent_elems, 'contents') else ctypes.addressof(parent_elems)
        self._n_slot_addr = base_addr + index * ctypes.sizeof(parent_elems._type_)
        c_ptr = ctypes.cast(ctypes.c_void_p(self._n_slot_addr), ctypes.POINTER(ctypes.c_void_p))
        self._n_view = c_ptr
        if value is not None:
            self._n_set_value(value._n_get_value() if hasattr(value, '_n_get_value') else int(value))
        else:
            raw = parent_elems[index]
            self._n_addr = int(raw) if raw else 0
        return self"""

replacement_pointer = """    @classmethod
    def _n_on_array(cls, parent_elems, index, value: int=None):
        \"\"\"Array-embedded pointer: reads address from parent's ctypes array slot.\"\"\"
        if value is not None:
            val = value._n_get_value() if hasattr(value, '_n_get_value') else int(value)
            parent_elems[index] = val
            if val == 0:
                return None
        else:
            raw = parent_elems[index]
            if not raw:
                return None
        self = cls.__new__(cls)
        self._n_contents_cache = None
        base_addr = ctypes.addressof(parent_elems.contents) if hasattr(parent_elems, 'contents') else ctypes.addressof(parent_elems)
        self._n_slot_addr = base_addr + index * ctypes.sizeof(parent_elems._type_)
        c_ptr = ctypes.cast(ctypes.c_void_p(self._n_slot_addr), ctypes.POINTER(ctypes.c_void_p))
        self._n_view = c_ptr
        self._n_addr = int(parent_elems[index])
        return self"""

# 2. array.__setitem__
target_array = """        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        elif hasattr(self._n_cache[index], '_n_set_value'):
            self._n_cache[index]._n_set_value(val)
        elif hasattr(self._n_cache[index], '__ilshift__'):
            self._n_cache[index] <<= value"""

replacement_array = """        if index not in self._n_cache or self._n_cache[index] is None:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index)
        elif hasattr(self._n_cache[index], '_n_set_value'):
            self._n_cache[index]._n_set_value(val)
        elif hasattr(self._n_cache[index], '__ilshift__'):
            self._n_cache[index] <<= value"""

# 3. seq.__setitem__
target_seq = """        if index not in self._n_cache:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index, value)
        else:
            self._n_cache[index]._n_set_value(value)"""

replacement_seq = """        if index not in self._n_cache or self._n_cache[index] is None:
            self._n_cache[index] = self._n_type._n_on_array(self._n_view, index, value)
        elif hasattr(self._n_cache[index], '_n_set_value'):
            self._n_cache[index]._n_set_value(value)
        elif hasattr(self._n_cache[index], '__ilshift__'):
            self._n_cache[index] <<= value"""

code = code.replace(target_pointer, replacement_pointer)
code = code.replace(target_array, replacement_array)
code = code.replace(target_seq, replacement_seq)

with open('src/nimic/ntypesystem.py', 'w') as f:
    f.write(code)

print("Applied pointer null patches.")
