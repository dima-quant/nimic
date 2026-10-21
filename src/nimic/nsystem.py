from __future__ import annotations
import builtins as _builtins
import codecs
import ctypes
import ctypes.util as _ctypes_util
import functools as _functools
import io
import os
import importlib as _importlib
import re as _re
import math as _math
import resource as _resource
import traceback as _traceback
import shutil as _shutil
import sys
import types as _types
from enum import StrEnum, auto
from typing import Generator, TypeVar

from nimic.system.ansi_c import c_malloc, c_free
from nimic import ntypesystem as _ntypesystem
from nimic.ntypesystem import char, cstring, seq, string, NIntEnum, _n_dollar, ufcs, _n_default_value, RangeDefect

class _SomeCastClass:
    def __getitem__(self, other_cls: type) -> callable:
        # cast from value type to value type: convert object to bytes, construct from bytes
        # cast from pointer to pointer: ctypes pointer cast
        # cast from pointer to uintp: pointer that supports arithmetics
        # cast from uintp to pointer: ctypes cast from address to pointer
        # all pointer casts should keep the buffer reference to prevent GC
        if isinstance(other_cls, TypeVar):
            fun = lambda x: x
        else:
            fun = lambda x: other_cls._n_cast(x)
        return fun


cast = _SomeCastClass()


def sizeof(x: type) -> int:
    return x._n_sizeof()



def fields(x: object, y: object | None = None) -> object:
    if y is None:
        for name in x._n_fields:
            yield getattr(x, name)
    else:
        for name in x._n_fields:
            yield getattr(x, name), getattr(y, name)


def countdown(a: int, b: int) -> Generator:
    for i in range(a, b - 1, -1):
        yield i

# --- Nim system builtins ---

def alloc_shared0(size):
    """Nim: allocShared0 — allocate zero-initialized shared memory."""
    return c_malloc(size)

def dealloc_shared(p):
    """Nim: deallocShared — free shared memory."""
    c_free(p)

allocShared0 = alloc_shared0
deallocShared = dealloc_shared


def write_bytes(f, data, start: int, count: int) -> int:
    """Nim: writeBytes — write count bytes from data starting at offset start to file f.
    Returns number of bytes written."""
    if hasattr(data, '_n_view'):
        # seq or array with ctypes backing
        buf_addr = ctypes.addressof(data._n_view)
        raw = (ctypes.c_char * (start + count)).from_address(buf_addr)
        b = bytes(raw[start:start + count])
    elif isinstance(data, (bytes, bytearray)):
        b = data[start:start + count]
    else:
        b = bytes(int(data[i]) for i in range(start, start + count))
    return f.buffer.write(b) if hasattr(f, 'buffer') else f.write(b)

writeBytes = write_bytes


class _NewSeqHelper:
    """Nim: newSeq[T](n) — create a seq[T] of length n, or newSeq(s, n) — mutate s to length n."""
    def __getitem__(self, _ntype: type):
        def _make(n: int):
            s = seq[_ntype]()
            s.new_seq(n)
            return s
        return _make

    def __call__(self, s, n: int):
        s.new_seq(n)

newSeq = _NewSeqHelper()
new_seq = newSeq


def new_string_of_cap(cap: int):
    """Nim: newStringOfCap — create a string with a zero-filled buffer of
    *cap* bytes.  The resulting string is empty (len 0 in str terms) but its
    ``_n_view`` ctypes buffer has *cap* bytes available for in-place writes."""
    return string(cap)

newStringOfCap = new_string_of_cap


def newString(length: int) -> string:
    """Nim: newString(len) — a string of len NUL chars (written in place, e.g. through its cstring)."""
    return string("\0" * int(length))


def new_cstring_of_cap(cap: int):
    """Create a cstring with a zero-filled buffer of *cap* bytes."""
    return cstring(cap)

newCStringOfCap = new_cstring_of_cap


class Endianness(NIntEnum):
    littleEndian = 0
    bigEndian = auto()


def _detect_host_os():
    if sys.platform == "darwin":
        return string("macosx")
    elif sys.platform == "win32":
        return string("windows")
    elif sys.platform.startswith("linux"):
        return string("linux")
    elif sys.platform.startswith("freebsd"):
        return string("freebsd")
    elif sys.platform.startswith("openbsd"):
        return string("openbsd")
    elif sys.platform.startswith("netbsd"):
        return string("netbsd")
    elif sys.platform.startswith("solaris") or sys.platform.startswith("sunos"):
        return string("solaris")
    elif sys.platform.startswith("aix"):
        return string("aix")
    return string("any")


def _detect_host_cpu():
    if hasattr(os, "uname"):
        arch = os.uname().machine.lower()
    else:
        arch = os.environ.get("PROCESSOR_ARCHITECTURE", "any").lower()
    if arch in ["x86_64", "amd64"]:
        return string("amd64")
    elif arch in ["i386", "i686", "x86"]:
        return string("i386")
    elif arch in ["arm64", "aarch64"]:
        return string("arm64")
    elif arch.startswith("arm"):
        return string("arm")
    elif arch.startswith("mips64"):
        return string("mips64")
    elif arch.startswith("mips"):
        return string("mips")
    elif arch.startswith("riscv32"):
        return string("riscv32")
    elif arch.startswith("riscv64"):
        return string("riscv64")
    elif arch.startswith("powerpc64") or arch.startswith("ppc64"):
        return string("powerpc64")
    elif arch.startswith("powerpc") or arch.startswith("ppc"):
        return string("powerpc")
    elif arch.startswith("sparc64"):
        return string("sparc64")
    elif arch.startswith("sparc"):
        return string("sparc")
    elif arch.startswith("s390x"):
        return string("s390x")
    return string("any")


hostOS = _detect_host_os()
hostCPU = _detect_host_cpu()


# --- Build profile: the conditional symbols of the emulated Nim build (Nim: defined(x)) ---
#
# Python mode emulates one Nim build: C backend, host OS/CPU, the default memory manager (ORC) and the
# defines of the Nim config files that the Nim compiler would read for the same main module. So
# `defined("c")` is true in Python too: `defined` is never a Python/Nim switch.

_N_DEFINES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nim_defines.txt")

# OS families and CPU properties as Nim's compiler (options.isDefined, platform) defines them
_N_POSIX_OS = {"linux", "macosx", "freebsd", "openbsd", "netbsd", "dragonfly", "crossos", "solaris",
               "aix", "haiku", "android", "ios", "irix", "qnx", "morphos", "skyos", "palmos", "atari",
               "vxworks", "nintendoswitch", "genode", "zephyr", "nuttx"}
_N_BSD_OS = {"freebsd", "openbsd", "netbsd", "dragonfly", "crossos"}
_N_CPU_ALIASES = {"i386": ("x86",), "amd64": ("x8664",), "ia64": ("itanium",)}
_N_CPU_32 = {"i386", "arm", "mips", "mipsel", "powerpc", "sparc", "riscv32", "wasm32", "avr", "msp430", "m68k"}
_N_CPU_BIG_ENDIAN = {"powerpc", "powerpc64", "sparc", "sparc64", "mips", "mips64", "s390x", "m68k"}
# Nim check options (normalized) that the Python runtime emulates or records
_N_CHECK_OPTIONS = ("overflowchecks", "boundchecks", "rangechecks", "objchecks", "fieldchecks",
                    "assertions", "nilchecks", "infchecks", "nanchecks")
# on/off switches that are not checks (not part of `checks:off`), on by default
_N_TRACE_OPTIONS = ("stacktrace", "linetrace", "excessivestacktrace")
# memory manager -> symbols it defines
_N_MM_SYMBOLS = {
    "orc": ("gcOrc", "gcDestructors", "nimV2", "nimSeqsV2"),
    "arc": ("gcArc", "gcDestructors", "nimV2", "nimSeqsV2"),
    "atomicarc": ("gcAtomicArc", "gcDestructors", "nimV2", "nimSeqsV2"),
    "yrc": ("gcYrc", "gcDestructors", "nimV2", "nimSeqsV2"),
    "refc": ("gcRefc",),
    "markandsweep": ("gcMarkAndSweep",),
    "boehm": ("gcBoehm",),
    "go": ("gcGo",),
    "none": ("gcNone",),
}


def _n_ident_normalize(name: str) -> str:
    """Nim identifier equality: the first character is case sensitive, the rest is case and
    underscore insensitive."""
    name = str(name)
    return name[:1] + name[1:].replace("_", "").lower()


class _NimCfgReader:
    """Reads the define-related options of Nim config files (nim.cfg syntax): `define:x`, `d:x`,
    `--define:x`, `-d:x`, `undef:x`, `mm:x`/`gc:x`, `cc:x`, `backend:x`, inside `@if/@elif/@else/@end`
    blocks whose conditions (`and`, `or`, `not`, parentheses, symbols) are evaluated against the symbols
    defined so far, as the Nim compiler does. Other options are ignored."""

    def __init__(self, profile: "_BuildProfile"):
        self.profile = profile

    def read(self, path: str) -> None:
        try:
            with _builtins.open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            return
        # stack of (active, branch_taken) for @if blocks
        stack: list[list[bool]] = []
        for raw in lines:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("@"):
                word, _, rest = line[1:].partition(" ")
                word = word.rstrip(":").lower()
                cond = rest.strip().rstrip(":")
                if word == "if":
                    value = self._enclosing_active(stack + [[True, True]]) and self._eval(cond)
                    stack.append([value, value])
                elif word == "elif" and stack:
                    taken = stack[-1][1]
                    value = (not taken) and self._enclosing_active(stack) and self._eval(cond)
                    stack[-1] = [value, taken or value]
                elif word == "else" and stack:
                    taken = stack[-1][1]
                    stack[-1] = [(not taken) and self._enclosing_active(stack), True]
                elif word == "end" and stack:
                    stack.pop()
                continue
            if all(active for active, _ in stack):
                self._option(line)

    def _option(self, line: str) -> None:
        line = line.lstrip("-")
        for sep in (":", "="):
            if sep in line:
                key, _, value = line.partition(sep)
                break
        else:
            return
        key = _n_ident_normalize(key.strip())
        value = value.strip().strip('"')
        if key in ("define", "d"):
            self.profile.define(value.split(":", 1)[0].split("=", 1)[0])
        elif key in ("undef", "u"):
            self.profile.undefine(value)
        elif key in ("mm", "gc"):
            self.profile.set_mm(value)
        elif key == "cc":
            self.profile.set_cc(value)
        elif key == "backend":
            self.profile.set_backend(value)
        elif key.lower() in _N_CHECK_OPTIONS + _N_TRACE_OPTIONS or key == "checks" or key == "x":
            on = value.lower() in ("on", "true", "")
            names = _N_CHECK_OPTIONS if key in ("checks", "x") else (key.lower(),)
            for name in names:
                self.profile.checks[name] = on

    def _eval(self, cond: str) -> bool:
        tokens = cond.replace("(", " ( ").replace(")", " ) ").split()
        pos = 0

        def expr() -> bool:
            nonlocal pos
            value = term()
            while pos < len(tokens) and tokens[pos] == "or":
                pos += 1
                rhs = term()
                value = value or rhs
            return value

        def term() -> bool:
            nonlocal pos
            value = factor()
            while pos < len(tokens) and tokens[pos] == "and":
                pos += 1
                rhs = factor()
                value = value and rhs
            return value

        def factor() -> bool:
            nonlocal pos
            tok = tokens[pos] if pos < len(tokens) else ""
            pos += 1
            if tok == "not":
                return not factor()
            if tok == "(":
                value = expr()
                pos += 1  # ")"
                return value
            if tok in ("true", "false"):
                return tok == "true"
            return self.profile.is_defined(tok)

        return expr() if tokens else False

    @staticmethod
    def _enclosing_active(stack: list) -> bool:
        """True if all @if blocks enclosing the innermost one are active."""
        return all(active for active, _ in stack[:-1])


class _BuildProfile:
    """The set of conditional symbols of the emulated Nim build, assembled like the Nim compiler does:
    its built-in feature symbols (nim_defines.txt), backend/OS/CPU/memory-manager symbols, the global
    config ($nim/config/nim.cfg), the user config, every nim.cfg from the filesystem root down to the
    main module's directory, `<main>.nim.cfg`, and finally NIMIC_DEFINES (comma or space separated,
    `-name` undefines). NimScript configs (config.nims) are not evaluated."""

    def __init__(self, main_file: str | None = None, extra: str | None = None):
        self.symbols: set[str] = set()
        # runtime checks switched by config options (`overflow_checks:off`, `checks:off`, ...), as
        # `-d:danger` does through the global config
        self.checks: dict[str, bool] = {name: True for name in _N_CHECK_OPTIONS}
        self.mm = "orc"
        self.backend = "c"
        self.cc = None
        try:
            with _builtins.open(_N_DEFINES_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.define(line)
        except OSError:
            pass
        self.define(self.backend)
        self._define_platform()
        self.set_mm(self.mm)
        if extra is None:
            extra = os.environ.get("NIMIC_DEFINES", "")
        extra_items = [s for s in extra.replace(",", " ").split() if s]
        for item in extra_items:  # before the configs: `@if danger:` blocks must see -d:danger
            if not item.startswith("-"):
                self.define(item)
        reader = _NimCfgReader(self)
        for path in self._config_files(main_file):
            reader.read(path)
        for item in extra_items:
            if item.startswith("-"):
                self.undefine(item[1:])

    # -- symbol set --
    def define(self, name: str) -> None:
        if name:
            self.symbols.add(_n_ident_normalize(name))

    def undefine(self, name: str) -> None:
        self.symbols.discard(_n_ident_normalize(name))

    def is_defined(self, name: str) -> bool:
        return _n_ident_normalize(name) in self.symbols

    def check_enabled(self, name: str) -> bool:
        """Whether the runtime check `name` (e.g. "overflowChecks") is on in this build."""
        return self.checks.get(_n_ident_normalize(name).lower(), True)

    def set_mm(self, mm: str) -> None:
        for syms in _N_MM_SYMBOLS.values():
            for s in syms:
                self.undefine(s)
        self.mm = _n_ident_normalize(mm).lower()
        for s in _N_MM_SYMBOLS.get(self.mm, ()):
            self.define(s)

    def set_cc(self, cc: str) -> None:
        if self.cc:
            self.undefine(self.cc)
        self.cc = cc
        self.define(cc)

    def set_backend(self, backend: str) -> None:
        self.undefine(self.backend)
        self.backend = backend
        self.define(backend)

    def _define_platform(self) -> None:
        os_name, cpu = str(hostOS), str(hostCPU)
        self.define(os_name)
        if os_name in _N_POSIX_OS:
            self.define("posix")
            self.define("unix")
        if os_name in _N_BSD_OS:
            self.define("bsd")
        if os_name == "macosx":
            self.define("osx")
        self.define(cpu)
        for alias in _N_CPU_ALIASES.get(cpu, ()):
            self.define(alias)
        self.define("cpu32" if cpu in _N_CPU_32 else "cpu64")
        self.define("bigEndian" if cpu in _N_CPU_BIG_ENDIAN else "littleEndian")

    @staticmethod
    def _config_files(main_file: str | None) -> list[str]:
        files = []
        nim_exe = os.environ.get("NIMIC_NIM") or _shutil.which("nim")
        if nim_exe:
            nim_root = os.path.dirname(os.path.dirname(os.path.realpath(nim_exe)))
            files.append(os.path.join(nim_root, "config", "nim.cfg"))
        files.append(os.path.join(os.path.expanduser("~"), ".config", "nim", "nim.cfg"))
        if main_file:
            project_dir = os.path.dirname(os.path.abspath(main_file))
            parts = []
            d = project_dir
            while True:
                parts.append(d)
                parent = os.path.dirname(d)
                if parent == d:
                    break
                d = parent
            files.extend(os.path.join(p, "nim.cfg") for p in reversed(parts))
            stem = os.path.splitext(os.path.basename(main_file))[0]
            files.append(os.path.join(project_dir, stem + ".nim.cfg"))
        return [f for f in files if os.path.isfile(f)]


_n_profile: _BuildProfile | None = None


def _n_build_profile() -> _BuildProfile:
    """The build profile of this run, created on first use from the main module (the Nim project)."""
    global _n_profile
    if _n_profile is None:
        main = sys.modules.get("__main__")
        main_file = getattr(main, "__file__", None)
        _n_profile = _BuildProfile(main_file)
    return _n_profile


# runtime checks (overflowChecks, boundChecks, ...) follow the build profile
_ntypesystem._n_check_provider = lambda name: _n_build_profile().check_enabled(name)


def _n_set_build_profile(profile: _BuildProfile | None) -> None:
    """Replace (or with None: reset to lazy creation) the build profile; for tests and tools."""
    global _n_profile
    _n_profile = profile


def defined(name: str) -> bool:
    """Nim: defined(x) — true if the conditional symbol `x` is defined in the emulated Nim build
    (see _BuildProfile). nimic spelling takes a string: defined("windows") (rule:defined)."""
    return _n_build_profile().is_defined(name)


def declared(name: str) -> bool:
    """Nim: declared(x) — true if the identifier `x` is declared at this point of the calling module
    (its locals, its globals including star-imports, or builtins). Dotted names resolve attributes:
    declared("system.getMaxMem"). nimic spelling takes a string (rule:declared)."""
    frame = sys._getframe(1)
    head, *rest = str(name).split(".")
    if head in frame.f_locals:
        obj = frame.f_locals[head]
    elif head in frame.f_globals:
        obj = frame.f_globals[head]
    elif hasattr(_builtins, head):
        obj = getattr(_builtins, head)
    else:
        return False
    for part in rest:
        if not hasattr(obj, part):
            return False
        obj = getattr(obj, part)
    return True


class pragma:
    """Nim pragma block `{.p.}: body` (e.g. `with pragma("gcsafe"):`, rule:pragmablock): the body runs
    as is; the pragma only affects the Nim output. As a statement, `pragma("p")` is the standalone
    pragma `{.p.}` (rule:pragmastmt): `pragma('feature: "lenientnils"')` only affects the Nim output,
    `pragma("pragma: name, p1, p2")` defines a pragma alias of the calling module (see
    ntypesystem._n_routine_pragmas)."""

    def __init__(self, p: str):
        self._n_pragma = p
        _ntypesystem._n_register_pragma(sys._getframe(1).f_globals.get("__name__"), p)

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def importExcept(module: str, *names: str) -> None:
    """Nim: import m except a, b — binds the public names of `module` (relative to the calling
    module's package for a leading dot) in the caller's namespace, except `names`; operator names
    such as "%" have no Python binding. Transpiles to `import m except a, b` (rule:importexcept)."""
    frame = sys._getframe(1)
    namespace = frame.f_globals
    mod = _importlib.import_module(module, namespace.get("__package__") or None)
    public = getattr(mod, "__all__", None) or [n for n in vars(mod) if not n.startswith("_")]
    excluded = set(names)
    for n in public:
        if n not in excluded:
            namespace[n] = getattr(mod, n)


def importFrom(module: str, *names: str) -> None:
    """Nim: from m import a, b — binds only `names` of `module` (relative to the calling module's package
    for a leading dot) in the caller's namespace; operator names have no Python binding. Transpiles to
    `from m import a, b` (rule:importfrom)."""
    namespace = sys._getframe(1).f_globals
    mod = _importlib.import_module(module, namespace.get("__package__") or None)
    for n in names:
        if n.isidentifier():
            namespace[n] = getattr(mod, n)


@ufcs(string)
def substr(s, first: int = 0, last: int | None = None):
    """Nim: substr — slice string from `first` to `last` (inclusive); also `s.substr(first, last)`."""
    s_val = str(s)
    f = max(int(first), 0)
    if last is None:
        l = len(s_val) - 1
    else:
        l = min(int(last), len(s_val) - 1)
    if f <= l:
        return string(s_val[f:l + 1])
    return string("")


def chr(x) -> char:
    """Nim: chr(i) — the char with ordinal i; RangeDefect outside 0..255 (range checks on)."""
    i = int(x)
    if not 0 <= i <= 255:
        raise RangeDefect(f"value out of range: {i} notin 0 .. 255")
    return char(_builtins.chr(i))


def ord(x) -> int:
    """Nim: ord(x) — returns ordinal integer of an enum, char, int, bool, or StrEnum."""
    if hasattr(x, 'ord'):
        return x.ord()
    if hasattr(x, 'value') and isinstance(x.value, int):
        return x.value
    if isinstance(x, (int, bool)):
        return int(x)
    return _builtins.ord(x)


# --- Byte-transparent stdio (Nim echo/readLine move raw bytes) ---

def _n_utf8_fallback(e: UnicodeEncodeError):
    """Codec error handler "nimic.utf8": chars > 0xFF (Python-side Unicode text)
    are written as their UTF-8 bytes instead of failing the Latin-1 encode."""
    return e.object[e.start:e.end].encode("utf-8"), e.end


_n_stdio_configured = False


def _n_setup_stdio() -> None:
    """Make stdin/stdout/stderr Latin-1 streams so a string byte view is
    read/written as its exact bytes. Idempotent; skipped when the env var
    NIMIC_NO_STDIO_RECONFIGURE is set or a stream is not a TextIOWrapper."""
    global _n_stdio_configured
    if _n_stdio_configured or os.environ.get("NIMIC_NO_STDIO_RECONFIGURE"):
        return
    _n_stdio_configured = True
    codecs.register_error("nimic.utf8", _n_utf8_fallback)
    for stream, errors in ((sys.stdout, "nimic.utf8"), (sys.stderr, "nimic.utf8"),
                           (sys.stdin, "strict")):  # Latin-1 decoding never fails
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="latin-1", errors=errors)
            except io.UnsupportedOperation:
                pass  # stream already read from (e.g. interactive stdin): keep its encoding


def quit(error: int | str = 0) -> None:
    """Nim: quit(errorcode: int = QuitSuccess) exits with the code; quit(errormsg: string) writes the
    message and a newline to stderr and exits with QuitFailure."""
    if isinstance(error, (str, _ntypesystem.string)):
        sys.stderr.write(str(error) + "\n")
        sys.stderr.flush()
        sys.exit(1)
    sys.exit(int(error))



class _InstantiationInfo(_ntypesystem.NTuple):
    filename: _ntypesystem.string
    line: _ntypesystem.nint
    column: _ntypesystem.nint


def instantiationInfo(index: int = -1, fullPaths: bool = False) -> _InstantiationInfo:
    """Nim: instantiationInfo — (filename, line, column) of a call site: index -1 is the caller of the
    proc (template in Nim) that calls instantiationInfo, -2 its caller, and so on."""
    frame = sys._getframe(1)
    for _ in range(-int(index)):  # up `-index` user frames; nimic's runtime frames (wrappers) don't count
        frame = frame.f_back
        while frame is not None and frame.f_code.co_filename.startswith(_ntypesystem._N_RUNTIME_DIR):
            frame = frame.f_back
    filename = os.path.abspath(frame.f_code.co_filename) if fullPaths else os.path.basename(frame.f_code.co_filename)
    positions = list(frame.f_code.co_positions())
    column = positions[frame.f_lasti // 2][2] if frame.f_lasti // 2 < len(positions) else 0
    return _InstantiationInfo(filename=_ntypesystem.string(filename), line=_ntypesystem.nint(frame.f_lineno),
                              column=_ntypesystem.nint(column or 0))


def typeof(x: object) -> type:
    """Nim: typeof(x) — the type of an expression; `T = typeof(expr)` is a type alias."""
    return type(x)


@ufcs(string)
def addInt(result: string, x) -> None:
    """Nim: addInt — appends the decimal representation of the integer x (int, int64, uint64, ...)."""
    result.add(str(int(x)))


def likely(val: bool) -> bool:
    """Nim: likely — a branch prediction hint; the value itself."""
    return val


def unlikely(val: bool) -> bool:
    """Nim: unlikely — a branch prediction hint; the value itself."""
    return val


_N_IMPORTC_PRAGMA = _re.compile(r'\bimportc\b(?:\s*:\s*"([^"]+)")?')
_N_C_INT_TYPES = {(8, True): ctypes.c_int8, (16, True): ctypes.c_int16, (32, True): ctypes.c_int32,
                  (64, True): ctypes.c_int64, (8, False): ctypes.c_uint8, (16, False): ctypes.c_uint16,
                  (32, False): ctypes.c_uint32, (64, False): ctypes.c_uint64}
_N_C_FLOAT_TYPES = {"f": ctypes.c_float, "d": ctypes.c_double}


@_functools.cache
def _n_c_libraries() -> tuple:
    """The C libraries importc procs are looked up in: the process itself, then libc and libm."""
    libs = [ctypes.CDLL(None)]
    for name in ("c", "m"):
        path = _ctypes_util.find_library(name)
        if path:
            libs.append(ctypes.CDLL(path))
    return tuple(libs)


def _n_c_type(cls: type) -> type:
    """The ctypes type of a nimic scalar type (for an importc call)."""
    c_type = _ntypesystem.DICT_OF_C_TYPES.get(cls.__name__)
    if c_type is not None:
        return c_type
    if issubclass(cls, _ntypesystem.NInteger):
        return _N_C_INT_TYPES[(cls._n_bits, cls._n_signed)]
    if issubclass(cls, _ntypesystem.NFloat):
        return _N_C_FLOAT_TYPES[cls._n_format]
    raise TypeError(f"importc: no C type for {cls.__name__} (scalar types only)")


def importc(fn):
    """Nim: a proc with `{.importc.}` / `{.importc: "cname".}` in its pragma docstring and no body
    (rule:importc). In Python it calls that C function of the running process (libc, libm) through
    ctypes; arguments and the result are converted to the annotated nimic scalar types."""
    match = _N_IMPORTC_PRAGMA.search(fn.__doc__ or "")
    if match is None:
        raise TypeError(f"@importc {fn.__name__}: no {{.importc.}} pragma in its docstring")
    c_name = match.group(1) or fn.__name__
    c_fn = next((getattr(lib, c_name) for lib in _n_c_libraries() if hasattr(lib, c_name)), None)
    if c_fn is None:
        raise NameError(f"@importc {fn.__name__}: C function {c_name} not found")

    def resolve(annotation):
        if isinstance(annotation, str):
            return fn.__globals__.get(annotation) or _ntypesystem.DICT_OF_TYPES[annotation]
        return annotation

    names = fn.__code__.co_varnames[:fn.__code__.co_argcount]
    arg_types = [resolve(fn.__annotations__[name]) for name in names]
    ret = fn.__annotations__.get("return")
    ret_type = None if ret in (None, "None") else resolve(ret)
    c_fn.argtypes = [_n_c_type(t) for t in arg_types]
    c_fn.restype = None if ret_type is None else _n_c_type(ret_type)

    @_functools.wraps(fn)
    def call(*args):
        c_args = [float(a) if issubclass(t, _ntypesystem.NFloat) else int(a) for a, t in zip(args, arg_types)]
        res = c_fn(*c_args)
        return None if ret_type is None else ret_type(res)
    return call


def isNil(x: object) -> bool:
    """Nim: isNil — whether a ref, ptr, pointer, proc or cstring is nil (None or a nil pointer)."""
    return x is None or isinstance(x, _ntypesystem.NilPtr)


def stackTraceAvailable() -> bool:
    """Nim: stackTraceAvailable — whether the build has stack traces (`stacktrace:off` under
    -d:release / -d:danger)."""
    return _n_build_profile().check_enabled("stacktrace")


def writeStackTrace() -> None:
    """Nim: writeStackTrace — writes the current stack trace to stderr (Python frames here)."""
    frames = _traceback.extract_stack()[:-1]
    sys.stderr.write("Traceback (most recent call last)\n")
    for fr in frames:
        sys.stderr.write(f"{fr.filename}({fr.lineno}) {fr.name}\n")
    sys.stderr.flush()


def _n_process_memory() -> int:
    """Peak resident memory of the process in bytes (ru_maxrss: bytes on macOS, KiB on Linux)."""
    rss = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss
    return rss if sys.platform == "darwin" else rss * 1024


def getMaxMem() -> int:
    """Nim: getMaxMem — the peak memory; Python: the process's peak memory (Nim: its allocator's)."""
    return _ntypesystem.nint(_n_process_memory())


def getTotalMem() -> int:
    """Nim: getTotalMem — the memory owned by the process (approximated by the peak)."""
    return _ntypesystem.nint(_n_process_memory())


def getOccupiedMem() -> int:
    """Nim: getOccupiedMem — the memory in use (approximated by the peak)."""
    return _ntypesystem.nint(_n_process_memory())


def toFloat(i: int) -> float:
    """Nim: toFloat — the int as a float."""
    return float(int(i))


def toInt(f: float) -> int:
    """Nim: toInt — the float rounded to the nearest int, halves away from zero."""
    r = _math.floor(abs(f) + 0.5)
    return _ntypesystem.nint(r if f >= 0 else -r)


def echo(*args) -> None:
    """Nim: echo(a, b, ...) — writes `$a & $b & ...` and a newline to stdout and flushes; unlike
    Python's print there is no separator between the arguments."""
    sys.stdout.write("".join(_n_dollar(a) for a in args) + "\n")
    sys.stdout.flush()


def shallowCopy(dest, src) -> None:
    """Nim: shallowCopy(dest, src) — assigns src to dest (under ORC/ARC the same as `dest = src`).
    `dest` must be a mutable nimic value (string, seq, array, Object, ...), assigned in place like
    `dest <<= src`; Python cannot rebind a caller's immutable variable."""
    if not hasattr(dest, "__ilshift__"):
        raise TypeError(f"shallowCopy: destination of type {type(dest).__name__} cannot be assigned in place")
    dest <<= src


def swap(a, b) -> None:
    """Nim: swap(a, b: var T) — exchanges the values of two variables, both changed in place like
    `a <<= b`. They must be mutable nimic values (string, seq, array, set, Object, a field, the scalar
    cells nint / nbool / float64 / cell(...)); Python cannot rebind a caller's immutable variable."""
    for x in (a, b):
        if not hasattr(x, "__ilshift__"):
            raise TypeError(f"swap: a value of type {type(x).__name__} cannot be changed in place; "
                            "use a variable (nint(...), nbool(...), cell(...), a string, seq or object)")
    tmp = a.copy()
    a <<= b
    b <<= tmp


def toOpenArray(x, first, last):
    """Nim: toOpenArray(x, first, last) — positions first..last of x (seq, array, string, openArray,
    ptr UncheckedArray) as an openArray view; reads and writes go to x (openArray._n_slice)."""
    return _ntypesystem.openArray._n_slice(x, first, last)


class push:
    """Nim: {.push pragma.} ... {.pop.} — `with push("overflowChecks: off"):` around a group of procs
    (rule:push emits {.push overflowChecks: off.}, the body unindented, then {.pop.}).

    Python emulates the runtime-check pragmas (overflowChecks, boundChecks, rangeChecks, checks): procs
    defined inside the block run with the check off (their code objects are registered), and so does
    module-level code executing inside the block. Other pragmas only affect the Nim output."""

    def __init__(self, pragma: str):
        self._n_pragma = pragma
        self._n_checks: dict[str, bool] = {}
        for part in pragma.split(","):
            key, _, value = part.partition(":")
            key = _n_ident_normalize(key.strip()).lower()
            on = value.strip().lower() in ("on", "true", "")
            names = _N_CHECK_OPTIONS if key in ("checks", "x") else (key,) if key in _N_CHECK_OPTIONS else ()
            for name in names:
                self._n_checks[name] = on

    def _n_off(self) -> list[str]:
        return [name for name, on in self._n_checks.items() if not on]

    def __enter__(self):
        self._n_frame = sys._getframe(1)  # module or proc scope: names defined in the block land in f_locals
        self._n_before = dict(self._n_frame.f_locals)
        for name in self._n_off():
            _ntypesystem._n_push_depth[name] = _ntypesystem._n_push_depth.get(name, 0) + 1
        return self

    def __exit__(self, *exc):
        off = self._n_off()
        for name in off:
            _ntypesystem._n_push_depth[name] -= 1
        codes = set()
        for key, value in dict(self._n_frame.f_locals).items():
            if self._n_before.get(key) is not value:
                _n_collect_codes(value, codes)
        self._n_frame = None
        for name in off:
            _ntypesystem._n_unchecked_codes.setdefault(name, set()).update(codes)
        return False


def _n_collect_codes(obj, codes: set) -> None:
    """Code objects of a proc (also behind @dispatch/@template wrappers), a class's methods, and the
    procs nested in them."""
    if isinstance(obj, type):
        for member in vars(obj).values():
            _n_collect_codes(member, codes)
        return
    fn = getattr(obj, "_n_fn", obj)
    stack = []
    while fn is not None:  # the function and each function it wraps (@template_expand runs its own code)
        code = getattr(fn, "__code__", None)
        if code is not None:
            stack.append(code)
        fn = getattr(fn, "__wrapped__", None)
    while stack:
        c = stack.pop()
        if c in codes:
            continue
        codes.add(c)
        stack.extend(k for k in c.co_consts if hasattr(k, "co_code"))


def assign(dest, src) -> None:
    """Nim `dest = src` where Python can't assign, e.g. through a proc returning `var T`:
    assign(p.s(cpsStmts), oldCode) (rule:assigncall). `dest` must be a mutable nimic value (Object,
    string, seq, array, set), assigned in place like `dest <<= src`."""
    if not hasattr(dest, "__ilshift__"):
        raise TypeError(f"assign: destination of type {type(dest).__name__} cannot be assigned in place")
    dest <<= src


def reset(x) -> None:
    """Nim: reset(x) — x becomes default(typeof(x)), in place like assign. `x` must be a mutable nimic
    value (Object, string, seq, array, set, integer); an enum is immutable in Python, reset its owner."""
    assign(x, _n_default_value(type(x)))


def include(*names: str) -> None:
    """Nim: include x, y — textual inclusion: each `<name>.py` next to the including file runs in the
    including module's namespace (like Nim, the included code sees and defines the includer's symbols).
    The included file keeps its own path for tracebacks and inspect.getsource; it is registered in
    sys.modules as `<includer package>.<name>` (not executed again) so tools can find its source.
    Transpiles to `include x, y` (rule:include)."""
    frame = sys._getframe(1)
    namespace = frame.f_globals
    base_dir = os.path.dirname(os.path.abspath(frame.f_code.co_filename))
    package = namespace.get("__package__") or ""
    for name in names:
        path = os.path.join(base_dir, *str(name).split("/")) + ".py"
        with _builtins.open(path, encoding="utf-8") as f:
            # the nimic boilerplate import of the included file must not rebind the includer's names
            # (e.g. containsOrIncl from std/intsets): an include file sees the includer's scope
            source = "".join("\n" if line.strip() == "from nimic.ntypes import *" else line for line in f)
        qualified = f"{package}.{os.path.basename(name)}" if package else os.path.basename(name)
        if qualified not in sys.modules:
            stub = _types.ModuleType(qualified)
            stub.__file__ = path
            stub._n_included_by = namespace.get("__name__")
            sys.modules[qualified] = stub
        exec(compile(source, path, "exec", dont_inherit=True), namespace)


def emit(code: str) -> None:
    """Nim: {.emit: \"\"\"code\"\"\".} — C code for the C backend (rule:emit). Python can't run it, so it
    raises if executed: write it only in a `when` branch that is inactive in the emulated build
    (e.g. `if comptime(defined("windows") and defined("bcc")):`)."""
    raise NotImplementedError("emit: C code can't run in Python mode; it belongs in an inactive `when` branch")


class _BlockBreak(Exception):
    """Raised by breakBlock(label); caught by the `with block(label):` of that label."""

    def __init__(self, label: str):
        super().__init__(label)
        self._n_label = label


class _LabeledBlock:
    def __init__(self, label: str):
        self._n_label = label

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return isinstance(exc, _BlockBreak) and exc._n_label == self._n_label


class _Block:
    """Nim `block:` (`with block:`, a scope) and `block name:` (`with block("name"):`, rule:dropwith /
    rule:labeledblock); `breakBlock("name")` leaves the named block (Nim `break name`)."""

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False

    def __call__(self, label: str) -> _LabeledBlock:
        return _LabeledBlock(label)


block = _Block()


class _Static:
    """Nim `static:` (`with static:`, rule:dropwith): the body runs when the module runs, which is
    Nim's compile time, so a failing `assert` in it stops the import as it stops the compilation.
    `static[T]` is the type of a compile-time parameter."""

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False

    def __getitem__(self, t):
        return set[t]


static = _Static()


def breakBlock(label: str) -> None:
    """Nim `break label`: leave the enclosing `with block(label):` (rule:labeledblock)."""
    raise _BlockBreak(label)
