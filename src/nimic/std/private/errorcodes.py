"""nimony's ErrorCode (lib/std/errorcodes: errorcodes.nim, included in nimony's system; errorcodes_posix.nim's
posixToErrorCode, its generic branch, by errno name). Nim 2 has no such type. Imported by the nimony branches of
the std shims (dirs, files: `if comptime(defined("nimony")):`), until a nimony prelude binds it (rules §13.2)."""
from __future__ import annotations
import errno as _errno
from nimic.ntypes import NIntEnum, auto, int32

__all__ = [  # the module's own names: like a Nim module, it exports none it imports (N92)
    'ErrorCode', 'posixToErrorCode'
]


class ErrorCode(NIntEnum):
    """Nim: ErrorCode — all possible errors in one enum (members always qualified: `ErrorCode.Success`)."""
    Success = 0  # Operation completed successfully.
    OverflowError = auto()  # Integer overflow or underflow error.
    Failure = auto()  # General failure, unknown error, etc.
    BugError = auto()  # Programming bug detected.
    IndexError = auto()  # Array index out of bounds.
    RangeError = auto()  # Range check error.
    OverlapError = auto()  # Source and destination memory overlaps.
    SyntaxError = auto()  # A general parsing error.
    OutOfMemError = auto()  # Not enough memory left.
    DiskFullError = auto()  # No space left on device.
    StackOverflow = auto()  # No stack space left.
    IOError = auto()  # I/O error.
    ValueError = auto()  # Invalid argument. Or: Bad/missing message.
    KeyError = auto()  # Invalid key.
    EndOfStreamError = auto()  # End of stream/file reached.
    SkipError = auto()  # Skip to next item.
    FullError = auto()  # No space left in the buffer. Or: Argument list too long.
    EmptyError = auto()  # No message is available.
    BusyError = auto()  # Device is busy. Too many requests.
    DeadResource = auto()  # Dead thread/owner/child.
    ResourceExhaustedError = auto()  # Thread/process/etc creation failed.
    DescriptorExhaustedError = auto()  # Too many files open in system.
    PermissionDenied = auto()  # Permission denied.
    RetryError = auto()  # Resource unavailable, try again.
    TimeoutError = auto()  # Connection timed out.
    InterruptedError = auto()  # Interrupted function.
    DeadlockError = auto()  # Resource deadlock would occur.
    LockedError = auto()  # Resource is locked.
    FormatMismatch = auto()  # Source and destination have incompatible formats.
    AlreadyConnected = auto()  # Address in use. Socket is connected.
    AddressNotAvailable = auto()  # Address not available.
    AddressFamilyUnsupported = auto()  # Address family not supported.
    BadOperation = auto()  # Operation not supported. Bad Request.
    AbortedOperation = auto()  # Operation canceled. Connection aborted.
    UnimplementedOperation = auto()  # Operation is not implemented.
    AlreadyInProgress = auto()  # Operation already in progress.
    NameTooLong = auto()  # Path/Filename/URL too long.
    NameExists = auto()  # Name file/directory already exists.
    NameNotFound = auto()  # No such file or directory or device.
    ContentTooLong = auto()  # File/content too large.
    BadDescriptor = auto()  # Bad file descriptor/pipe/process/etc.
    BadExecutable = auto()  # Executable file format error.
    BadLink = auto()  # Too many levels of symbolic links. Too many links. Cross-device link. HTTP: Misdirected request.
    BadProtocol = auto()  # Protocol wrong type for socket. Protocol not available. HTTP version not supported.
    ProtocolError = auto()  # Protocol error.
    ReadonlyProtection = auto()  # Cannot write to readonly data.
    SegFault = auto()  # Bad address. Segmentation fault. Nil pointer derefence.
    DiskCorruption = auto()  # Corrupted disk/file/table.
    Disconnected = auto()  # Network is down. Network unreachable. Connection reset. The socket is not connected.
    RefusedConnection = auto()  # Connection refused.
    UnreachableHost = auto()  # Host is unreachable. Bad Gateway.
    UnrecoverableState = auto()  # State not recoverable.
    AuthenticationRequired = auto()  # Network authentication required.
    RedirectError = auto()  # Redirect to other URL/path.
    Reserved1 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved2 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved3 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved4 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved5 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved6 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved7 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved8 = auto()  # Reserved for future extensions. This field will then be renamed!
    Reserved9 = auto()  # Reserved for future extensions. This field will then be renamed!


_n_posix_codes = (  # errorcodes_posix.nim's generic branch: errno names -> member; a name the OS lacks is left out
    (('EOVERFLOW',), ErrorCode.OverflowError),
    (('ERANGE', 'EDOM',), ErrorCode.RangeError),
    (('ENOMEM',), ErrorCode.OutOfMemError),
    (('ENOSPC',), ErrorCode.DiskFullError),
    (('EIO',), ErrorCode.IOError),
    (('EINVAL', 'EBADMSG', 'EILSEQ', 'ENOMSG', 'EDESTADDRREQ',), ErrorCode.ValueError),
    (('E2BIG', 'ENOBUFS',), ErrorCode.FullError),
    (('ENODATA',), ErrorCode.EmptyError),
    (('EBUSY', 'ETXTBSY',), ErrorCode.BusyError),
    (('ECHILD', 'EOWNERDEAD',), ErrorCode.DeadResource),
    (('ENOLCK',), ErrorCode.ResourceExhaustedError),
    (('ENFILE',), ErrorCode.DescriptorExhaustedError),
    (('EACCES', 'EPERM',), ErrorCode.PermissionDenied),
    (('EAGAIN', 'EWOULDBLOCK',), ErrorCode.RetryError),
    (('ETIMEDOUT', 'ETIME',), ErrorCode.TimeoutError),
    (('EINTR',), ErrorCode.InterruptedError),
    (('EDEADLK',), ErrorCode.DeadlockError),
    (('EADDRINUSE', 'EISCONN',), ErrorCode.AlreadyConnected),
    (('EADDRNOTAVAIL',), ErrorCode.AddressNotAvailable),
    (('EAFNOSUPPORT',), ErrorCode.AddressFamilyUnsupported),
    (('EOPNOTSUPP', 'ENOTSUP', 'ENOSYS', 'EPROTONOSUPPORT', 'ENOTTY', 'ESPIPE', 'EISDIR', 'ENOTEMPTY',), ErrorCode.BadOperation),
    (('ECANCELED', 'ECONNABORTED', 'ENETRESET',), ErrorCode.AbortedOperation),
    (('EALREADY', 'EINPROGRESS',), ErrorCode.AlreadyInProgress),
    (('ENAMETOOLONG',), ErrorCode.NameTooLong),
    (('EEXIST',), ErrorCode.NameExists),
    (('ENOENT', 'EIDRM', 'ENODEV', 'ENOTDIR',), ErrorCode.NameNotFound),
    (('EFBIG', 'EMSGSIZE',), ErrorCode.ContentTooLong),
    (('EPIPE', 'EBADF', 'EMFILE', 'ENOSTR', 'ENOTSOCK', 'ENOSR', 'ENXIO', 'ESRCH',), ErrorCode.BadDescriptor),
    (('ENOEXEC',), ErrorCode.BadExecutable),
    (('ELOOP', 'EMLINK', 'EXDEV',), ErrorCode.BadLink),
    (('EPROTOTYPE', 'ENOPROTOOPT',), ErrorCode.BadProtocol),
    (('EPROTO',), ErrorCode.ProtocolError),
    (('EROFS',), ErrorCode.ReadonlyProtection),
    (('EFAULT',), ErrorCode.SegFault),
    (('ENETDOWN', 'ENETUNREACH', 'ECONNRESET', 'ENOTCONN',), ErrorCode.Disconnected),
    (('ECONNREFUSED',), ErrorCode.RefusedConnection),
    (('EHOSTUNREACH',), ErrorCode.UnreachableHost),
    (('ENOTRECOVERABLE',), ErrorCode.UnrecoverableState),
)
_n_by_errno: dict[int, ErrorCode] = {}
for _names, _member in _n_posix_codes:
    for _name in _names:
        if hasattr(_errno, _name):
            _n_by_errno.setdefault(getattr(_errno, _name), _member)  # the first test that matches, as the `elif` chain


def posixToErrorCode(err: int32) -> ErrorCode:
    """Nim: posixToErrorCode(err) — the ErrorCode of a POSIX errno; 0 is Success, an unknown one Failure."""
    if int(err) == 0:
        return ErrorCode.Success
    return _n_by_errno.get(int(err), ErrorCode.Failure)
