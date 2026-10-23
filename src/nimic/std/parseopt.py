"""Nim std/parseopt — command line parser, ported line for line from Nim 2.2.4's lib/pure/parseopt.nim (the Nim
that tests/verify_transpiled.py compiles with), so a nimic program parses its arguments as the compiled one.

Supported syntax (as Nim's):
- short options: `-abcd` (a, b, c, d), `-e:5`, `-e=5`;
- long options: `--foo:bar`, `--foo=bar`, `--foo`;
- arguments: everything that doesn't start with `-`;
- with `shortNoVal` / `longNoVal` given, options not listed take a value: `-c foo`, `--foo bar`.
"""
from __future__ import annotations
import builtins as _builtins

from nimic.ntypes import NIntEnum, Object, Tset, auto, char, dispatch, nint, seq, string
from nimic.std.os import parseCmdLine, quoteShellCommand, param_count, param_str


class CmdLineKind(NIntEnum):
    """The detected command line token."""
    cmdEnd = auto()  # End of command line reached
    cmdArgument = auto()  # An argument such as a filename
    cmdLongOption = auto()  # A long option such as --option
    cmdShortOption = auto()  # A short option such as -c


cmdEnd = CmdLineKind.cmdEnd
cmdArgument = CmdLineKind.cmdArgument
cmdLongOption = CmdLineKind.cmdLongOption
cmdShortOption = CmdLineKind.cmdShortOption

_N_DELIMS = frozenset("\t ")


class OptParser(Object):
    """Implementation of the command line parser. To initialize it, use initOptParser."""
    _pos: nint
    _inShortState: bool
    _allowWhitespaceAfterColon: bool
    _shortNoVal: Tset[char]
    _longNoVal: seq[string]
    _cmds: seq[string]
    _idx: nint
    kind: CmdLineKind  # The detected command line token
    key: string  # Key and value pair; the key is the option or the argument,
    val: string  # and the value is not "" if the option was given a value


def _parseWord(s: str, i: int, w: list, delim: frozenset = _N_DELIMS) -> int:
    result = i
    if result < len(s) and s[result] == '"':
        result += 1
        while result < len(s):
            if s[result] == '"':
                result += 1
                break
            w.append(s[result])
            result += 1
    else:
        while result < len(s) and s[result] not in delim:
            w.append(s[result])
            result += 1
    return result


def _n_chars(shortNoVal) -> frozenset:
    return frozenset(str(c) for c in (shortNoVal or ()))


@dispatch
def initOptParser(cmdline: seq[string], shortNoVal: Tset[char] = Tset[char](), longNoVal: seq[string] = seq[string](),
                  allowWhitespaceAfterColon: bool = True) -> OptParser:
    """Initializes the command line parser. If cmdline is empty, the real command line as provided by the
    os module is retrieved instead. shortNoVal and longNoVal are used to specify which options do not take
    values. allowWhitespaceAfterColon: `--foo: bar` takes `bar` as the value of foo."""
    result = OptParser()
    result._pos = 0
    result._idx = 0
    result._inShortState = False
    result._shortNoVal = Tset[char](*(char(c) for c in _n_chars(shortNoVal)))
    result._longNoVal = seq[string]([string(str(x)) for x in (longNoVal or ())])
    result._allowWhitespaceAfterColon = bool(allowWhitespaceAfterColon)
    if len(cmdline) != 0:
        result._cmds = seq[string]([string(str(x)) for x in cmdline])
    else:
        result._cmds = seq[string]([param_str(i) for i in range(1, param_count() + 1)])
    result.kind = cmdEnd
    result.key = string("")
    result.val = string("")
    return result


@dispatch
def initOptParser(cmdline: string = string(""), shortNoVal: Tset[char] = Tset[char](), longNoVal: seq[string] = seq[string](),
                  allowWhitespaceAfterColon: bool = True) -> OptParser:
    """Initializes the command line parser from a command line string (split with parseCmdLine)."""
    return initOptParser(parseCmdLine(cmdline), shortNoVal, longNoVal, allowWhitespaceAfterColon)


def _handleShortOption(p: OptParser, cmd: str):
    i = int(p._pos)
    p.kind = cmdShortOption
    key = list(str(p.key))
    if i < len(cmd):
        key.append(cmd[i])
        i += 1
    p.key = string("".join(key))
    p._inShortState = True
    while i < len(cmd) and cmd[i] in _N_DELIMS:
        i += 1
        p._inShortState = False
    short_no_val = _n_chars(p._shortNoVal)
    if i < len(cmd) and (cmd[i] in ":=" or len(short_no_val) > 0 and str(p.key)[0] not in short_no_val):
        if i < len(cmd) and cmd[i] in ":=":
            i += 1
        p._inShortState = False
        while i < len(cmd) and cmd[i] in _N_DELIMS:
            i += 1
        p.val = string(cmd[i:])
        p._pos = 0
        p._idx += 1
    else:
        p._pos = i
    if i >= len(cmd):
        p._inShortState = False
        p._pos = 0
        p._idx += 1


def next(p: OptParser, *default) -> None:  # noqa: A001
    """Parses the next token. p.kind describes what kind of token has been parsed. p.key and p.val are set
    accordingly. (Nim's name: a module that star-imports parseopt still gets Python's next() for anything
    that is no OptParser.)"""
    if not isinstance(p, OptParser):
        return _builtins.next(p, *default)
    cmds = p._cmds
    if p._idx >= len(cmds):
        p.kind = cmdEnd
        return
    cmd = str(cmds[p._idx])
    i = int(p._pos)
    while i < len(cmd) and cmd[i] in _N_DELIMS:
        i += 1
    p._pos = i
    p.key = string("")
    p.val = string("")
    if p._inShortState:
        p._inShortState = False
        if i >= len(cmd):
            p._idx += 1
            p._pos = 0
            if p._idx >= len(cmds):
                p.kind = cmdEnd
                return
        else:
            _handleShortOption(p, cmd)
            return
    if i < len(cmd) and cmd[i] == "-":
        i += 1
        if i < len(cmd) and cmd[i] == "-":
            p.kind = cmdLongOption
            i += 1
            key = []
            i = _parseWord(cmd, i, key, frozenset(" \t:="))
            p.key = string("".join(key))
            while i < len(cmd) and cmd[i] in _N_DELIMS:
                i += 1
            if i < len(cmd) and cmd[i] in ":=":
                i += 1
                while i < len(cmd) and cmd[i] in _N_DELIMS:
                    i += 1
                # if we're at the end, use the next command line option:
                if i >= len(cmd) and p._idx < len(cmds) and p._allowWhitespaceAfterColon:
                    p._idx += 1
                    i = 0
                if p._idx < len(cmds):
                    p.val = string(str(cmds[p._idx])[i:])
            elif len(p._longNoVal) > 0 and p.key not in p._longNoVal and p._idx + 1 < len(cmds):
                p.val = string(str(cmds[p._idx + 1]))
                p._idx += 1
            else:
                p.val = string("")
            p._idx += 1
            p._pos = 0
        else:
            p._pos = i
            _handleShortOption(p, cmd)
    else:
        p.kind = cmdArgument
        p.key = string(cmd)
        p._idx += 1
        p._pos = 0


def cmdLineRest(p: OptParser) -> string:
    """Retrieves the rest of the command line that has not been parsed yet (quoted with quoteShellCommand)."""
    return quoteShellCommand(list(p._cmds)[int(p._idx):])


def remainingArgs(p: OptParser) -> seq[string]:
    """Retrieves a sequence of the arguments that have not been parsed yet."""
    return seq[string]([string(str(x)) for x in list(p._cmds)[int(p._idx):]])


def _n_token(p: OptParser) -> tuple:
    # a Nim tuple copies the strings: the parser resets p.key / p.val for the next token
    return (p.kind, string(str(p.key)), string(str(p.val)))


@dispatch
def getopt(p: OptParser):
    """Convenience iterator for iterating over the given OptParser: (kind, key, val) per token. Resets the
    parser to the start of its command line."""
    p._pos = 0
    p._idx = 0
    while True:
        next(p)
        if p.kind == cmdEnd:
            break
        yield _n_token(p)


@dispatch
def getopt(cmdline: seq[string] = seq[string](), shortNoVal: Tset[char] = Tset[char](), longNoVal: seq[string] = seq[string]()):
    """Convenience iterator for iterating over command line arguments: (kind, key, val) per token. If cmdline
    is empty, the real command line of the program is used."""
    p = initOptParser(seq[string]([string(str(x)) for x in (cmdline or ())]), shortNoVal=shortNoVal,
                      longNoVal=longNoVal)
    while True:
        next(p)
        if p.kind == cmdEnd:
            break
        yield _n_token(p)

