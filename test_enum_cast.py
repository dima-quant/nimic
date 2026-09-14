from nimic.ntypes import *
from ncompiler.wordrecg import TSpecialWord

print("ord:", nord(TSpecialWord.wAsm))
try:
    print("cast:", TSpecialWord(1))
except Exception as e:
    print("cast failed:", e)
