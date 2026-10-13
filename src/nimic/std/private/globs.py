"""
nimic std/private/globs module
"""
import sys

from ...ntypes import string

def native_to_unix_path(path: string | str) -> string:
    p = str(path)
    if sys.platform == "win32":
        return string(p.replace("\\", "/"))
    return string(p)

nativeToUnixPath = native_to_unix_path
