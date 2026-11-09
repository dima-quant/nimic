"""
nimic std/private/globs module
"""
import sys

from ...ntypes import string

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'native_to_unix_path', 'nativeToUnixPath'
]

def native_to_unix_path(path: string | str) -> string:
    p = str(path)
    if sys.platform == "win32":
        return string(p.replace("\\", "/"))
    return string(p)

nativeToUnixPath = native_to_unix_path
