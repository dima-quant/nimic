import sys
sys.path.append('src')
sys.path.append('ncompiler')
import nimic.ntypesystem as ns

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

ns._DEBUG = True
dump_call()
