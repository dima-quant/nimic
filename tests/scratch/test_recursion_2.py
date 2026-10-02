import sys
sys.path.append('src')
sys.path.append('ncompiler')
import nimic.ntypesystem as ns
from nimic.ntypesystem import _Object

old_init = _Object.__init__

def wrapped_init(self, **kwargs):
    print(f"wrapped_init called for {self.__class__.__name__}")
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
        import traceback
        traceback.print_exc()

dump_call()
