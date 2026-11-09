"""Nim std/winlean — the Windows API subset nimic code uses, with Nim 2.2.4's lib/windows/winlean.nim names and
types: Handle, DWORD, WINBOOL, WinSizeT, the file / mapping constants, createFileW, getFileSize,
createFileMappingW, mapViewOfFileEx, unmapViewOfFile, closeHandle, getLastError (vfs's Windows openMmapImpl).

The procs call kernel32 through ctypes (the error code stays for os.osLastError: use_last_error); elsewhere a call
raises OSError, as Nim's module doesn't exist there. The constants and types import on every OS, so code with a
`when defined(windows):` branch imports and transpiles anywhere (`import std/winlean`)."""
from __future__ import annotations
import ctypes as _ctypes
import sys as _sys

from nimic.ntypes import int32, nint, pointer, uint

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'closeHandle', 'CREATE_ALWAYS', 'CREATE_NEW', 'createFileMappingW', 'createFileW', 'DWORD',
    'FILE_ATTRIBUTE_NORMAL', 'FILE_ATTRIBUTE_READONLY', 'FILE_FLAG_RANDOM_ACCESS', 'FILE_MAP_READ',
    'FILE_MAP_WRITE', 'FILE_SHARE_DELETE', 'FILE_SHARE_READ', 'FILE_SHARE_WRITE', 'GENERIC_ALL', 'GENERIC_READ',
    'GENERIC_WRITE', 'getFileSize', 'getLastError', 'Handle', 'INVALID_HANDLE_VALUE', 'mapViewOfFileEx',
    'OPEN_ALWAYS', 'OPEN_EXISTING', 'PAGE_READONLY', 'PAGE_READWRITE', 'unmapViewOfFile', 'WINBOOL', 'WinSizeT'
]

Handle = nint
DWORD = int32
WINBOOL = int32
WinSizeT = uint

GENERIC_READ = int32(_ctypes.c_int32(0x80000000).value)
GENERIC_WRITE = int32(0x40000000)
GENERIC_ALL = int32(0x10000000)
FILE_SHARE_READ = int32(0x00000001)
FILE_SHARE_WRITE = int32(0x00000002)
FILE_SHARE_DELETE = int32(0x00000004)
CREATE_ALWAYS = int32(2)
CREATE_NEW = int32(1)
OPEN_EXISTING = int32(3)
OPEN_ALWAYS = int32(4)
FILE_ATTRIBUTE_READONLY = int32(0x00000001)
FILE_ATTRIBUTE_NORMAL = int32(0x00000080)
FILE_FLAG_RANDOM_ACCESS = int32(0x10000000)
PAGE_READONLY = int32(2)
PAGE_READWRITE = int32(4)
FILE_MAP_READ = int32(4)
FILE_MAP_WRITE = int32(2)
INVALID_HANDLE_VALUE = Handle(-1)

_n_kernel32 = None


def _n_k32():
    """kernel32, loaded on the first call (use_last_error: os.osLastError reads the call's error)."""
    global _n_kernel32
    if _sys.platform != "win32":
        raise OSError("nimic std/winlean: Windows only")
    if _n_kernel32 is None:
        k = _ctypes.WinDLL("kernel32", use_last_error=True)
        h, d, p = _ctypes.c_ssize_t, _ctypes.c_uint32, _ctypes.c_void_p
        k.CreateFileW.argtypes = (_ctypes.c_wchar_p, d, d, p, d, d, h)
        k.CreateFileW.restype = h
        k.GetFileSize.argtypes = (h, _ctypes.POINTER(d))
        k.GetFileSize.restype = d
        k.CreateFileMappingW.argtypes = (h, p, d, d, d, _ctypes.c_wchar_p)
        k.CreateFileMappingW.restype = h
        k.MapViewOfFileEx.argtypes = (h, d, d, d, _ctypes.c_size_t, p)
        k.MapViewOfFileEx.restype = p
        k.UnmapViewOfFile.argtypes = (p,)
        k.UnmapViewOfFile.restype = _ctypes.c_int32
        k.CloseHandle.argtypes = (h,)
        k.CloseHandle.restype = _ctypes.c_int32
        _n_kernel32 = k
    return _n_kernel32


def _n_dword(x) -> int:
    """A DWORD argument's bits (GENERIC_READ is a negative int32)."""
    return int(x) & 0xFFFFFFFF


def _n_address(p) -> int | None:
    """A pointer argument's address (nil: None)."""
    return None if p is None else (int(p._n_get_value()) or None)


def _n_wide(s):
    """A WideCString argument (widestrs.newWideCString's buffer), or nil."""
    return None if s is None else s.value


def createFileW(lpFileName, dwDesiredAccess: DWORD, dwShareMode: DWORD, lpSecurityAttributes: pointer,
                dwCreationDisposition: DWORD, dwFlagsAndAttributes: DWORD, hTemplateFile: Handle) -> Handle:
    return Handle(_n_k32().CreateFileW(_n_wide(lpFileName), _n_dword(dwDesiredAccess), _n_dword(dwShareMode),
                                       _n_address(lpSecurityAttributes), _n_dword(dwCreationDisposition),
                                       _n_dword(dwFlagsAndAttributes), int(hTemplateFile)))


def getFileSize(hFile: Handle, lpFileSizeHigh) -> DWORD:
    """The file's size: the low 32 bits returned, the high ones stored through lpFileSizeHigh (a ptr DWORD)."""
    high = _ctypes.c_uint32(0)
    low = _n_k32().GetFileSize(int(hFile), _ctypes.byref(high))
    if lpFileSizeHigh is not None:
        lpFileSizeHigh.contents = DWORD(_ctypes.c_int32(high.value).value)
    return DWORD(_ctypes.c_int32(low).value)


def createFileMappingW(hFile: Handle, lpFileMappingAttributes: pointer, flProtect: DWORD,
                       dwMaximumSizeHigh: DWORD, dwMaximumSizeLow: DWORD, lpName) -> Handle:
    return Handle(_n_k32().CreateFileMappingW(int(hFile), _n_address(lpFileMappingAttributes), _n_dword(flProtect),
                                              _n_dword(dwMaximumSizeHigh), _n_dword(dwMaximumSizeLow),
                                              _n_wide(lpName)))


def mapViewOfFileEx(hFileMappingObject: Handle, dwDesiredAccess: DWORD, dwFileOffsetHigh: DWORD,
                    dwFileOffsetLow: DWORD, dwNumberOfBytesToMap: WinSizeT, lpBaseAddress: pointer) -> pointer:
    """The mapping's address (nil when it failed)."""
    address = _n_k32().MapViewOfFileEx(int(hFileMappingObject), _n_dword(dwDesiredAccess),
                                       _n_dword(dwFileOffsetHigh), _n_dword(dwFileOffsetLow),
                                       int(dwNumberOfBytesToMap), _n_address(lpBaseAddress))
    return None if not address else pointer(address)


def unmapViewOfFile(lpBaseAddress: pointer) -> WINBOOL:
    return WINBOOL(_n_k32().UnmapViewOfFile(_n_address(lpBaseAddress)))


def closeHandle(hObject: Handle) -> WINBOOL:
    return WINBOOL(_n_k32().CloseHandle(int(hObject)))


def getLastError() -> int32:
    """The calling thread's last error code (of the last winlean call)."""
    _n_k32()
    return int32(_ctypes.get_last_error())
