import re

with open('src/nimic/ntypesystem.py', 'r') as f:
    content = f.read()

if 'import collections' not in content:
    content = content.replace('import ctypes\n', 'import ctypes\nimport collections\n')

string_cls = """class string(collections.UserString):
    \"\"\"Nim-compatible string with C-buffer backing to support addr().\"\"\"
    
    @property
    def _n_view(self):
        return self._n_view_ref[0] if hasattr(self, '_n_view_ref') else None

    @_n_view.setter
    def _n_view(self, val):
        if not hasattr(self, '_n_view_ref'):
            self._n_view_ref = [val]
        else:
            self._n_view_ref[0] = val

    def __init__(self, bs=""):
        if isinstance(bs, string) and hasattr(bs, '_n_view_ref'):
            self._n_view_ref = bs._n_view_ref
            return
        if isinstance(bs, int):
            cap = bs
            self._n_view_ref = [(ctypes.c_char * cap)()]
            if cap > 0:
                BUFFER_REGISTRY.register(self._n_view_ref[0])
            return
            
        if isinstance(bs, str):
            bs_bytes = bs.encode('utf-8', errors='replace')
        elif hasattr(bs, 'data'):
            bs_bytes = bs.data.encode('utf-8', errors='replace')
        else:
            bs_bytes = str(bs).encode('utf-8', errors='replace')
            
        self._n_view_ref = [(ctypes.c_char * len(bs_bytes)).from_buffer_copy(bs_bytes)]
        if len(bs_bytes) > 0:
            BUFFER_REGISTRY.register(self._n_view_ref[0])

    @property
    def data(self):
        if hasattr(self, '_n_view_ref') and self._n_view_ref[0] is not None:
            return bytes(self._n_view_ref[0]).split(b'\\0', 1)[0].decode('utf-8', 'replace')
        return ""
        
    @data.setter
    def data(self, value):
        pass

    def _n_ensure_capacity(self, new_cap):
        if self._n_view is None:
            self._n_view = (ctypes.c_char * new_cap)()
            BUFFER_REGISTRY.register(self._n_view)
        elif len(self._n_view) < new_cap:
            BUFFER_REGISTRY.unregister(self._n_view)
            new_size = max(len(self._n_view) * 2, new_cap)
            new_arr = (ctypes.c_char * new_size)()
            ctypes.memmove(new_arr, self._n_view, len(self._n_view))
            self._n_view = new_arr
            BUFFER_REGISTRY.register(self._n_view)

    def add(self, other):
        if isinstance(other, str):
            other_bytes = other.encode('utf-8')
        elif hasattr(other, 'data'):
            other_bytes = other.data.encode('utf-8')
        else:
            other_bytes = str(other).encode('utf-8')
            
        cur_bytes = self.data.encode('utf-8')
        new_len = len(cur_bytes) + len(other_bytes) + 1
        self._n_ensure_capacity(new_len)
        
        for i, b in enumerate(other_bytes):
            self._n_view[len(cur_bytes) + i] = b
        self._n_view[len(cur_bytes) + len(other_bytes)] = 0

    def _n_get_value(self):
        return self.data.encode('utf-8')

    def __str__(self):
        return self.data

    def __len__(self):
        return len(self.data)

    def __eq__(self, other):
        if isinstance(other, string):
            return self.data == other.data
        if isinstance(other, str):
            return self.data == other
        return NotImplemented
        
    def __hash__(self):
        return hash(self.data)

    def __and__(self, other):
        return string(self.data + str(other))

    def _substitute(self, **kwargs):
        from string import Template
        return string(Template(self.data).substitute(**kwargs))

    def __mod__(self, itr):
        if hasattr(itr, '__iter__') and not isinstance(itr, (str, bytes)):
            return string(self.data % tuple(itr))
        return string(self.data % itr)

    def is_empty(self) -> bool:
        return len(self.data) == 0

    def __truediv__(self, tail) -> 'string':
        tail_str = tail.data if hasattr(tail, 'data') else str(tail)
        return string(f"{self.data}/{tail_str}")

    def splitlines(self):
        return [string(x) for x in self.data.splitlines()]

    def split_whitespace(self):
        return [string(x) for x in self.data.split()]
        
    def endswith(self, suffix: str) -> bool:
        return self.data.endswith(suffix)
        
    def startswith(self, prefix: str) -> bool:
        return self.data.startswith(prefix)
        
    def __getitem__(self, index):
        if isinstance(index, slice):
            return string(self.data[index])
        if hasattr(self, '_n_view') and self._n_view is not None:
            return char(self.data[index], ctypes.addressof(self._n_view) + index)
        return self.data[index]
"""

pattern = re.compile(r'class string\(str\):.*?def startswith\(self, prefix: str\) -> bool:\n        """Nim: startsWith — check if string starts with prefix."""\n        return super\(\)\.startswith\(prefix\)', re.DOTALL)

content = pattern.sub(string_cls, content)

with open('src/nimic/ntypesystem.py', 'w') as f:
    f.write(content)

