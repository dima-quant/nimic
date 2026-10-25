# /// nimic
# source: nimony@3f56467ab15a46746c4f2b33a904809a2ffa0a12:src/lib/vfs.nim
# ///
#       Nif library
# (c) Copyright 2026 Andreas Rumpf
#
# See the file "license.txt", included in this
# distribution, for details about the copyright.

## Virtual filesystem abstraction for nimony, hexer, nifc, and nifmake.
##
## Built on the **relay** pattern from
## https://nim-lang.org/blog/relays.rst — every file operation is a
## module-level proc variable initialized to a default that calls
## straight through to the OS. Drivers reassign at startup; adapters
## capture the previous relay and wrap it (logging, sandboxing, in-memory
## cache, build cache, …).
##
## Day-zero behavior is identical to direct syncio/memfiles/os calls.
## The point is the swappable seam, not yet the swapping.

from __future__ import annotations
from nimic.ntypes import *

if comptime(defined("nimony")):
    pragma('feature: "lenientnils"')
    # The `*Relay` hooks are installed once at startup; the compiler is
    # single threaded.
    pragma('feature: "assumeSync"')

##
## Mmap'd reads return a `VfsBlob` rather than a raw `MemFile`. The blob
## carries an opaque cookie + cleanup proc supplied by the backend; its
## destructor calls cleanup so e.g. an LMDB-backed driver can close the
## read-transaction that owns its mmap'd pointer at exactly the right
## time. The default disk backend wraps a `MemFile`; an LMDB backend
## wraps a `MDB_txn`; a sandbox adapter would wrap whatever its source
## blob is and refuse to provide one for paths outside the allow-list.

from nimic.std.memfiles import *
from nimic.std import memfiles
from nimic.std.syncio import *
from nimic.std.times import *

# --- profiling --------------------------------------------------------
#
# Compile with `-d:vfsProfile` to record per-op counts and elapsed time.
# Each process emits a one-line summary at exit; the build driver
# invokes many short-lived processes, so `awk` over the lines aggregates
# totals across the whole build.

if comptime(defined("vfsProfile")):
    class VfsCounter(Object):
        count: nint
        ns: int64
        bytes: int64

    with var:
        statOpenMmap = VfsCounter()
        statRead = VfsCounter()
        statWrite = VfsCounter()
        statExists = VfsCounter()
        statMtime = VfsCounter()
        statRemove = VfsCounter()

    from nimic.std.strutils import *

    def dumpVfsProfile(label: string):
        @template
        def emit(name: string, c: VfsCounter):
            stderr.writeLine(string("[vfs] ") + label + string(" ") + name +
                             string(" count=") + str(c.count) +
                             string(" ms=") + formatFloat(float64(c.ns) / 1_000_000.0, ffDecimal, 3) +
                             string(" bytes=") + str(c.bytes))
        emit(string("openMmap"), statOpenMmap)
        emit(string("read"), statRead)
        emit(string("write"), statWrite)
        emit(string("exists"), statExists)
        emit(string("mtime"), statMtime)
        emit(string("remove"), statRemove)
else:
    @template
    def dumpVfsProfile(label: string):
        discard

with const:
    _nanosPerSec: int64 = i64(1_000_000_000)


class FileWriteMode(NIntEnum):
    AlwaysWrite = auto()
    OnlyIfChanged = auto()

# --- atomic replacement ---------------------------------------------------
#
# Never truncate a .nif or .bif that a reader may have mmap'd.

from nimic.std.atomics import *

if comptime(defined("windows")):
    @importc
    def _osProcessId() -> int32:
        """{.importc: "GetCurrentProcessId", stdcall,
                              dynlib: "kernel32".}"""
        pass
else:
    @importc
    def _osProcessId() -> int32:
        """{.importc: "getpid".}"""
        pass

if comptime(defined("nimony")):
    with var:
        _atomicWriteCounter: nint = 0

    def _nextTempSeq() -> nint:
        return atomicFetchAdd(_atomicWriteCounter, 1)
else:
    with var:
        _atomicWriteCounter = Atomic[nint]()

    def _nextTempSeq() -> nint:
        return _atomicWriteCounter.fetchAdd(1)


def atomicTempPath(target: string) -> string:
    ## A sibling temp path for an atomic replacement of `target`
    result = target + string(".tmp.") + str(nint(_osProcessId())) + string(".") + str(_nextTempSeq())
    return result


if comptime(defined("windows")):
    @importc
    def vfsSleepMs(ms: uint32):
        """{.importc: "Sleep", stdcall, dynlib: "kernel32".}"""
        pass
elif comptime(defined("nimony")):
    # `nanosleep`, not libc's `usleep`: the native backend links no libc and
    # knows `nanosleep` as the syscall it is.
    importFrom("nimic.std.posix.posix", "Timespec", "nanosleep")

    def vfsSleepMs(ms: uint32):
        with var:
            req = Timespec()
        req.tv_sec = typeof(req.tv_sec)(clong(ms // u32(1000)))
        req.tv_nsec = clong(ms % u32(1000)) * 1_000_000
        with var:
            rem = Timespec()
        _ = nanosleep(req, rem)
else:
    importFrom("nimic.std.os", "sleep")

    def vfsSleepMs(ms: uint32):
        sleep(nint(ms))

if comptime(defined("nimony")):
    from nimic.std.os import *
    from nimic.std.dirs import *
    from nimic.std.paths import *
    from nimic.std.private.oscommons import *
    # Nimony's stdlib procs are `.raises`. Wrap them so vfs.nim stays
    # non-raising (the rest of the compiler is wired that way).

    def _unixModTime(p: string) -> int64:
        try: return getLastModificationTime(p)
        except: return i64(0)

    def _unixNow() -> int64:
        try:
            with let:
                t = getTime()
            return toUnix(t) * _nanosPerSec + int64(t.nanosecond)
        except: return i64(0)

    def _rmPath(p: string):
        try: removeFile(path(p))
        except: pass

    def _moveIntoImpl(src: string, dst: string) -> bool:
        try: return tryMoveFSObject(src, dst, False)
        except: return False

    def _removeTreeImpl(d: string):
        try:
            for it in walkDir(path(d)):
                if it.kind == pcDir: _removeTreeImpl(str(it.path))
                else: _ = tryRemoveFile(it.path)
            _ = tryRemoveFinalDir(path(d))
        except: pass

    def _readBytes(p: string) -> string:
        try: return readFile(p)
        except: return string("")

    def _createDirImpl(d: string) -> bool:
        try: return tryCreateFinalDir(path(d)) == Success
        except: return False

    def _removeDirImpl(d: string):
        try: _ = tryRemoveFinalDir(path(d))
        except: pass

    def _writeBytes(p: string, c: string):
        with let:
            tmp = atomicTempPath(p)
        with var:
            ok = False
        try:
            writeFile(tmp, c)
            ok = _moveIntoImpl(tmp, p)
        except:
            ok = False
        if not ok:
            try: removeFile(path(tmp))
            except: pass   # no `.tmp.NNN` litter
            quit(string("vfs: write failed: ") + p)

    def _fileMaybeExists(p: string) -> bool:
        try: return fileExists(p)
        except: return False

    def _openMmapImpl(p: string) -> MemFile:
        try: return memfiles.open(p)
        except: quit(string("vfs: open failed: ") + p)
else:
    from nimic.std.os import *

    def _unixModTime(path: string) -> int64:
        with let:
            t = getLastModificationTime(path)
        return toUnix(t) * _nanosPerSec + int64(t.nanosecond)

    def _unixNow() -> int64:
        with let:
            t = getTime()
        return toUnix(t) * _nanosPerSec + int64(t.nanosecond)

    def _rmPath(path: string): removeFile(path)

    def _moveIntoImpl(src: string, dst: string) -> bool:
        try:
            moveFile(src, dst)
            return True
        except CatchableError: return False

    def _removeTreeImpl(d: string):
        try: removeDir(d)
        except CatchableError: pass

    def _readBytes(p: string) -> string: return readFile(p)

    def _createDirImpl(d: string) -> bool:
        try: return not existsOrCreateDir(d)
        except CatchableError: return False

    def _removeDirImpl(d: string):
        try: removeDir(d)
        except CatchableError: pass

    def _writeBytes(p: string, c: string):
        with let:
            tmp = atomicTempPath(p)
        try:
            writeFile(tmp, c)
            if not _moveIntoImpl(tmp, p): raise newException(IOError, string("move failed: ") + p)
        except CatchableError:
            try: removeFile(tmp)
            except CatchableError: pass   # no `.tmp.NNN` litter
            raise

    def _fileMaybeExists(p: string) -> bool: return fileExists(p)

    def _openMmapImpl(p: string) -> MemFile: return memfiles.open(p)


def vfsMoveInto(src: string, dst: string) -> bool:
    ## Move `src` onto `dst` as a single filesystem operation, replacing whatever
    ## was there. The point is that `dst` is never opened for writing: a reader
    ## that mmap'd it, or a process currently EXECUTING it, keeps the old inode
    ## and is undisturbed, while everyone who opens the path afterwards sees the
    ## complete new file. There is no window in which `dst` is half-written.
    ##
    ## This is what makes a build artefact safe to publish from several processes
    ## at once. Writing one in place is not: a concurrent `execve` of a partially
    ## written executable fails with ETXTBSY ("Text file busy"), and so does
    ## writing one that somebody else is executing.
    return _moveIntoImpl(src, dst)


def vfsTryLock(lock: string) -> bool:
    ## Take the cross-process lock `lock` (a path): true when this call took it,
    ## false when another process holds it. The lock is a directory because
    ## creating one either succeeds or finds it there, atomically, on every OS.
    return _createDirImpl(lock)


def vfsUnlock(lock: string):
    _removeDirImpl(lock)


def vfsRemoveTree(dir: string):
    ## Remove `dir` and everything below it. Best effort: it exists to clean up
    ## a scratch directory this process created for itself, and failing to do
    ## so must never fail a build.
    _removeTreeImpl(dir)

# --- relays ---------------------------------------------------------------
#
# Mtimes are exposed as `int64` nanoseconds since the Unix epoch. Whole-second
# resolution caused spurious rebuilds when an output landed in the same wall
# second as one of its inputs (input mtime tied with output mtime → `>=`
# triggered rebuild). nifmake's `<` / `>=` comparisons keep their meaning.

# --- VfsBlob: backend-owned, mmap-friendly read handle -------------------


# Nim's field type `proc (b: var VfsBlob) {.nimcall.}` has no name: an inline calltype is written at its uses
@calltype(inline=True)
def _VfsBlobCleanup(b: mut @ VfsBlob):
    """{.nimcall.}"""
    pass


class VfsBlob(Object):
    ## Opaque mmap'd read handle. `data` points at `size` bytes of
    ## contiguous read-only content. The disk-backed default fills `mf`
    ## inline and uses `closeMemFileBlob` as cleanup; alternative
    ## backends (LMDB, in-memory cache, …) leave `mf` zero-initialised
    ## and use `cookie` for whatever they need to release. The caller
    ## drops the blob via `closeBlob`, which calls cleanup. Explicit
    ## close — same lifecycle shape as the `MemFile` it replaces.
    data: pointer
    size: nint
    _mf: MemFile
    cookie: pointer
    _cleanup: _VfsBlobCleanup

    def closeBlob(b: mut @ VfsBlob):
        ## Release the backend resource (mmap unmap, LMDB read txn close, …).
        ## Safe to call multiple times — the second call is a no-op.
        if b._cleanup is not None:
            b._cleanup(b)
        b.data = None
        b.size = 0
        b._mf = default(MemFile)
        b.cookie = None
        b._cleanup = None


def initBlob(data: pointer, size: nint,
             cookie: pointer = None,
             cleanup: _VfsBlobCleanup = None) -> VfsBlob:
    ## Constructor for non-MemFile backends.
    return VfsBlob(data=data, size=size, cookie=cookie, _cleanup=cleanup)

# Default disk backend: wrap a MemFile in a VfsBlob whose cleanup runs
# `memfiles.close`. MemFile is plain data (no destructor) so we just
# copy its fields into the blob — no heap alloc per open.


def _closeMemFileBlob(b: mut @ VfsBlob):
    """{.nimcall.}"""
    try: memfiles.close(b._mf)
    except: pass


def fromMemFile(mf: sink @ MemFile) -> VfsBlob:
    ## Wrap an already-opened MemFile in a blob whose cleanup closes it.
    result = VfsBlob(data=mf.mem, size=mf.size, _mf=mf,
                     cookie=None, _cleanup=_closeMemFileBlob)
    return result


with var:
    def openMmapRelay(path: string) -> VfsBlob:
        """{.nimcall.}"""
        return fromMemFile(_openMmapImpl(path))

with var:
    def readBytesRelay(path: string) -> string:
        """{.nimcall.}"""
        return _readBytes(path)

with var:
    def writeBytesRelay(path: string, content: string):
        """{.nimcall.}"""
        _writeBytes(path, content)

with var:
    def existsRelay(path: string) -> bool:
        """{.nimcall.}"""
        return _fileMaybeExists(path)

with var:
    def mtimeRelay(path: string) -> int64:
        """{.nimcall.}"""
        return _unixModTime(path)

with var:
    def nowRelay() -> int64:
        """{.nimcall.}"""
        return _unixNow()

with var:
    def removeRelay(path: string):
        """{.nimcall.}"""
        _rmPath(path)

# --- portable wrappers ----------------------------------------------------

if comptime(defined("vfsProfile")):
    def vfsOpenMmap(path: string) -> VfsBlob:
        with let:
            t0 = getMonoTime()
        result = openMmapRelay(path)
        statOpenMmap.count += 1
        statOpenMmap.bytes += result.size
        statOpenMmap.ns += inNanoseconds(getMonoTime() - t0)
        return result

    def vfsRead(path: string) -> string:
        with let:
            t0 = getMonoTime()
        result = readBytesRelay(path)
        statRead.count += 1
        statRead.bytes += result.len
        statRead.ns += inNanoseconds(getMonoTime() - t0)
        return result

    def vfsWrite(path: string, content: string):
        with let:
            t0 = getMonoTime()
        writeBytesRelay(path, content)
        statWrite.count += 1
        statWrite.bytes += content.len
        statWrite.ns += inNanoseconds(getMonoTime() - t0)

    def vfsExists(path: string) -> bool:
        with let:
            t0 = getMonoTime()
        result = existsRelay(path)
        statExists.count += 1
        statExists.ns += inNanoseconds(getMonoTime() - t0)
        return result

    def vfsMtime(path: string) -> int64:
        with let:
            t0 = getMonoTime()
        result = mtimeRelay(path)
        statMtime.count += 1
        statMtime.ns += inNanoseconds(getMonoTime() - t0)
        return result

    def vfsNow() -> int64:
        """{.inline.}"""
        return nowRelay()

    def vfsRemove(path: string):
        with let:
            t0 = getMonoTime()
        removeRelay(path)
        statRemove.count += 1
        statRemove.ns += inNanoseconds(getMonoTime() - t0)
else:
    def vfsOpenMmap(path: string) -> VfsBlob:
        """{.inline.}"""
        return openMmapRelay(path)

    def vfsRead(path: string) -> string:
        """{.inline.}"""
        return readBytesRelay(path)

    def vfsWrite(path: string, content: string):
        """{.inline.}"""
        writeBytesRelay(path, content)

    def vfsExists(path: string) -> bool:
        """{.inline.}"""
        return existsRelay(path)

    def vfsMtime(path: string) -> int64:
        """{.inline.}"""
        return mtimeRelay(path)

    def vfsNow() -> int64:
        """{.inline.}"""
        return nowRelay()

    def vfsRemove(path: string):
        """{.inline.}"""
        removeRelay(path)


if comptime(__name__ == "__main__"):
    from nimic.std.strutils import *

    def _countEntries(dir: string) -> nint:
        result = nint(0)
        for kind, path in walkDir(dir):
            result += 1
        return result

    def _taggedRead(path: string) -> string:
        return string("relayed: ") + _readBytes(path)

    echo(FileWriteMode.AlwaysWrite, " ", ord(FileWriteMode.OnlyIfChanged))
    dumpVfsProfile(string("test"))

    # a scratch directory of this process (Python and Nim run with different pids)
    with let:
        dir = atomicTempPath(getTempDir() / string("vfstest"))
        f = dir / string("a.txt")
    createDir(dir)

    # vfsWrite replaces atomically: the file is there, no `.tmp.` file is left behind
    echo(vfsExists(f))
    vfsWrite(f, string("hello vfs"))
    echo(vfsExists(f), " ", _countEntries(dir))
    vfsWrite(f, string("hello again"))
    echo(vfsRead(f), " ", _countEntries(dir))

    # the mmap'd blob: its data and size; closeBlob twice is a no-op
    with var:
        blob = vfsOpenMmap(f)
        text = newString(blob.size)
    copyMem(addr(text[0]), blob.data, blob.size)
    echo(blob.size, " ", text, " ", blob.data is not None)
    blob.closeBlob()
    echo(blob.size, " ", blob.data is None)
    blob.closeBlob()
    echo(blob.size)
    with var:
        other = initBlob(None, 0)
    other.closeBlob()
    echo(other.size, " ", other.cookie is None)

    # mtimes in nanoseconds, not in the future
    with let:
        mtime = vfsMtime(f)
    echo(mtime > 0, " ", mtime <= vfsNow())

    # the temp path: target, `.tmp.`, the pid, a counter that increases
    with let:
        p1 = atomicTempPath(f)
        p2 = atomicTempPath(f)
        prefix = f + string(".tmp.")
        parts1 = p1.substr(prefix.len).split(char('.'))
        parts2 = p2.substr(prefix.len).split(char('.'))
    echo(p1.startsWith(prefix), " ", parts1.len, " ", parts1[0] == parts2[0], " ",
         parseInt(parts1[0]) > 0, " ", parseInt(parts2[1]) == parseInt(parts1[1]) + 1)

    # vfsMoveInto replaces the target; a missing source is false
    with let:
        g = dir / string("b.txt")
    vfsWrite(g, string("second"))
    echo(vfsMoveInto(g, f), " ", vfsExists(g), " ", vfsRead(f))

    # a relay swapped by a driver, then restored
    with let:
        savedRead = readBytesRelay
    readBytesRelay = _taggedRead
    echo(vfsRead(f))
    readBytesRelay = savedRead
    echo(vfsRead(f))

    # the lock: taken once, then held, then free again
    with let:
        lock = dir / string("lock")
    echo(vfsTryLock(lock), " ", vfsTryLock(lock))
    vfsUnlock(lock)
    echo(vfsTryLock(lock))
    vfsUnlock(lock)

    vfsRemove(f)
    echo(vfsExists(f))
    vfsSleepMs(1)

    # vfsRemoveTree: a tree with a subdirectory and files; then the directory is gone
    createDir(dir / string("sub"))
    vfsWrite(dir / string("sub") / string("c.txt"), string("x"))
    vfsRemoveTree(dir)
    echo(dirExists(dir))

    # a failed move (missing source) is false, not an exception
    echo(vfsMoveInto(dir / string("missing"), f))
