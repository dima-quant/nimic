import sys

with open('src/nimic/ntypesystem.py', 'r') as f:
    code = f.read()

target = """    def __init__(self, x=None):
        if x is None:
            self._n_addr = 0
            self._n_contents_cache = None"""

replacement = """    def __init__(self, x=None, **kwargs):
        if x is None and not kwargs:
            self._n_addr = 0
            self._n_contents_cache = None
        elif kwargs and x is None:
            obj = self._n_contents_type(**kwargs)
            self._n_addr = ctypes.addressof(obj._n_view) if hasattr(obj, '_n_view') else 0
            self._n_contents_cache = obj"""

if target in code:
    code = code.replace(target, replacement)
    with open('src/nimic/ntypesystem.py', 'w') as f:
        f.write(code)
    print("Applied pointer kwargs patch.")
else:
    print("Target not found.")
