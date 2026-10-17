"""Nim std/terminal — terminal handling utilities."""
from __future__ import annotations
import sys
from nimic.ntypes import NIntEnum, auto, Tset
from nimic.std.syncio import write as _write


def is_atty(f=sys.stderr) -> bool:
    """Nim: isatty — returns true if f refers to a terminal."""
    try:
        return hasattr(f, "isatty") and f.isatty()
    except (ValueError, OSError):  # closed or detached stream
        return False


isatty = is_atty


# --- styles and colors (POSIX ANSI escape codes, as Nim's terminal on non-Windows) ---

ansiResetCode = "\x1b[0m"
_stylePrefix = "\x1b["


class Style(NIntEnum):
    """Nim: Style — different styles for text output."""
    styleBright = 1
    styleDim = auto()
    styleItalic = auto()
    styleUnderscore = auto()
    styleBlink = auto()
    styleBlinkRapid = auto()
    styleReverse = auto()
    styleHidden = auto()
    styleStrikethrough = auto()


class ForegroundColor(NIntEnum):
    """Nim: ForegroundColor — terminal's foreground colors."""
    fgBlack = 30
    fgRed = auto()
    fgGreen = auto()
    fgYellow = auto()
    fgBlue = auto()
    fgMagenta = auto()
    fgCyan = auto()
    fgWhite = auto()
    fg8Bit = auto()
    fgDefault = auto()


class BackgroundColor(NIntEnum):
    """Nim: BackgroundColor — terminal's background colors."""
    bgBlack = 40
    bgRed = auto()
    bgGreen = auto()
    bgYellow = auto()
    bgBlue = auto()
    bgMagenta = auto()
    bgCyan = auto()
    bgWhite = auto()
    bg8Bit = auto()
    bgDefault = auto()


class TerminalCmd(NIntEnum):
    """Nim: TerminalCmd — commands that can be expressed as arguments."""
    resetStyle = 0
    fgColor = auto()
    bgColor = auto()


# Nim's enums are not pure: the members are also visible unqualified
for _enum in (Style, ForegroundColor, BackgroundColor, TerminalCmd):
    for _member in _enum:
        globals()[_member.name] = _member


def ansiStyleCode(style) -> str:
    """Nim: ansiStyleCode."""
    return f"{_stylePrefix}{int(style)}m"


def resetAttributes(f) -> None:
    """Nim: resetAttributes — resets all attributes."""
    _write(f, ansiResetCode)


def setStyle(f, style) -> None:
    """Nim: setStyle — writes the codes of a set of styles."""
    for s in sorted(style, key=int):
        _write(f, ansiStyleCode(s))


def setForegroundColor(f, fg: ForegroundColor, bright: bool = False) -> None:
    """Nim: setForegroundColor."""
    _write(f, ansiStyleCode(int(fg) + (60 if bright else 0)))


def setBackgroundColor(f, bg: BackgroundColor, bright: bool = False) -> None:
    """Nim: setBackgroundColor."""
    _write(f, ansiStyleCode(int(bg) + (60 if bright else 0)))


def styledWrite(f, *args) -> None:
    """Nim: styledWrite — `write` that treats style, color and TerminalCmd arguments specially, and
    resets the attributes after styled output. (The Nim macro skips the final reset only when all
    arguments are string literals; at run time a string argument counts as a literal.)"""
    reset = False
    for a in args:
        if isinstance(a, Style):
            setStyle(f, {a})
            reset = True
        elif isinstance(a, (set, frozenset, Tset)):
            setStyle(f, a)
            reset = True
        elif isinstance(a, ForegroundColor):
            setForegroundColor(f, a)
            reset = True
        elif isinstance(a, BackgroundColor):
            setBackgroundColor(f, a)
            reset = True
        elif isinstance(a, TerminalCmd):
            if a == TerminalCmd.resetStyle:
                resetAttributes(f)
            reset = True
        else:
            _write(f, a)
    if reset:
        resetAttributes(f)


def styledWriteLine(f, *args) -> None:
    """Nim: styledWriteLine — styledWrite and a newline."""
    styledWrite(f, *args)
    _write(f, "\n")
