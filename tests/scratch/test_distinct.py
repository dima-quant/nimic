from nimic.ntypes import distinct, string
from nimic.ntypesystem import DICT_OF_TYPES

@distinct
class MyString(string):
    pass

print("MyString in DICT:", MyString.__name__ in DICT_OF_TYPES)
print("hasattr:", hasattr(MyString, "_n_register_type"))
