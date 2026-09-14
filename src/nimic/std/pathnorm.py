
from __future__ import annotations
import os

from nimic.ntypes import string

def normalizePath(path: str, dirSep: str = '/') -> str:
    """Nim: pathnorm.normalizePath"""
    return string(os.path.normpath(str(path)).replace('\\', dirSep))

def addNormalizePath(x: str, result: string, state: object, dirSep: str = '/'):
    """Nim: pathnorm.addNormalizePath"""
    if not isinstance(result, string):
        return
        
    current_bytes = result.data.encode('utf-8')
    
    if len(current_bytes) > 0:
        # simple fallback since this is just a python shim
        new_path = os.path.normpath(current_bytes.decode('utf-8', 'ignore') + dirSep + str(x))
    else:
        new_path = os.path.normpath(str(x))
        
    new_path = new_path.replace('\\', dirSep)
    new_bytes = new_path.encode('utf-8')
    
    result._n_ensure_capacity(len(new_bytes) + 1)
    
    for i, b in enumerate(new_bytes):
        result._n_view[i] = b
            
    if len(new_bytes) < len(result._n_view):
        result._n_view[len(new_bytes)] = 0
