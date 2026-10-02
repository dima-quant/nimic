from nimic.ntypes import *

class TSpecialWord(NIntEnum):
    wInvalid = 0
    wIf = 1
    wElse = 2

val = TSpecialWord(1)
print(type(val), val == TSpecialWord.wIf)
