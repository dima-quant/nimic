"""
nimic std/private/globs module
"""
from ...ntypes import string

def native_to_unix_path(path: string | str) -> string:
    import sys
    p = str(path)
    if sys.platform == "win32":
        return string(p.replace("\\", "/"))
    return string(p)

nativeToUnixPath = native_to_unix_path
