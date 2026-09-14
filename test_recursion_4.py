import sys
sys.path.append('src')
sys.path.append('ncompiler')
import nimic.ntypesystem as ns
from nimic.ntypesystem import _Object

old_init = _Object.__init__

def wrapped_init(self, **kwargs):
    python_fields = getattr(self.__class__, '_n_python_fields', set())
    field_types = getattr(self.__class__, '_n_field_types', {})
    for name in python_fields:
        fc = field_types.get(name)
        if fc is not None and isinstance(fc, type) and name == "next":
            print(f"fc.__bases__={fc.__bases__}")
            print(f"fc is {fc}")
    old_init(self, **kwargs)

_Object.__init__ = wrapped_init

def dump_call():
    try:
        from idents import newIdentCache, getIdent
        import idents
        result = idents.IdentCache(wordCounter=0)
        from nimic.ntypesystem import string
        result.idAnon = getIdent(result, string(":anonymous"))
    except Exception as e:
        pass

dump_call()
