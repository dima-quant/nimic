from nimic.ntypesystem import seq
import ncompiler.pathutils as p
try:
    print(seq[p.AbsoluteDir])
except Exception as e:
    import traceback
    traceback.print_exc()
