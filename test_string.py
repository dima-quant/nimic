import collections
import ctypes

class string(collections.UserString):
    def __init__(self, bs=""):
        if isinstance(bs, string) and hasattr(bs, '_n_view_ref'):
            self._n_view_ref = bs._n_view_ref
            return
        if isinstance(bs, int):
            cap = bs
            self._n_view_ref = [(ctypes.c_char * cap)()]
            return
        if isinstance(bs, str):
            bs = bs.encode('utf-8', errors='replace')
        elif hasattr(bs, 'data'):
            bs = bs.data.encode('utf-8', errors='replace')
        self._n_view_ref = [(ctypes.c_char * len(bs)).from_buffer_copy(bs)]
    
    @property
    def data(self):
        if hasattr(self, '_n_view_ref') and self._n_view_ref[0] is not None:
            return bytes(self._n_view_ref[0]).split(b'\0', 1)[0].decode('utf-8', 'replace')
        return ""
        
    @data.setter
    def data(self, value):
        pass # ignored since we write to _n_view
        
    @property
    def _n_view(self):
        return self._n_view_ref[0] if hasattr(self, '_n_view_ref') else None

    @_n_view.setter
    def _n_view(self, val):
        if not hasattr(self, '_n_view_ref'):
            self._n_view_ref = [val]
        else:
            self._n_view_ref[0] = val

s = string('hello')
print(s.replace('o', 'a'))
print(s + string('!'))
print(type(s + string('!')))
