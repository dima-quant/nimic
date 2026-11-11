# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/lengc/mangler.nim
# ///
#
#
#           Leng Compiler
#        (c) Copyright 2024 Andreas Rumpf
#
#    See the file "license.txt", included in this
#    distribution, for details about the copyright.
#

## Name mangling. See leng-spec.md for details.

from __future__ import annotations
from nimic.ntypes import *


def _addOctal(result: mut @ string, c: char):
    """{.inline.}"""
    ## The 3-digit octal escape `\NNN` used inside C string literals. Spelled out
    ## here because Nimony's `strutils` has no `toOctal` -- and this variant does
    ## not allocate.
    with let:
        n = nint(c)
    result.add(char(ord(char('0')) + ((n >> 6) & 7)))
    result.add(char(ord(char('0')) + ((n >> 3) & 7)))
    result.add(char(ord(char('0')) + (n & 7)))


def _escape(result: mut @ string, c: char):
    """{.inline.}"""
    with const:
        HexChars = string("0123456789ABCDEF")
    with var:
        n = nint(c)
    result.add(char('X'))
    result.add(HexChars[n >> 4 & 0xF])
    result.add(HexChars[n & 0xF])
    result.add(char('Q'))


def mangleToC(s: string) -> string:
    with var:
        i = nint(0)
    result = newStringOfCap(s.len)
    while i < s.len:
        match s[i]:
            case _ if s[i] in inrange(char('A'), pred(char('Q'))) or s[i] in inrange(succ(char('Q')), char('Z')) or s[i] in inrange(char('a'), char('z')) or s[i] in inrange(char('0'), char('9')):
                result.add(s[i])
            case _ if s[i] == char('Q'): result.add(string("QQ"))
            case _ if s[i] == char('_'): result.add(string("Q_"))
            case _ if s[i] == char('.'): result.add(char('_'))
            case _ if s[i] == char('['):
                if i < s.len - 1 and s[i + 1] == char(']'):
                    if i < s.len - 2 and s[i + 2] == char('='):
                        result.add(string("putQ"))
                        i += 2
                    else:
                        result.add(string("getQ"))
                        i += 1
                else:
                    _escape(result, char('['))
            case _ if s[i] == char('='):
                if i < s.len - 1 and s[i + 1] == char('='):
                    result.add(string("eqQ"))
                    i += 1
                else:
                    result.add(string("eQ"))
            case _ if s[i] == char('<'):
                if i < s.len - 1 and s[i + 1] == char('='):
                    result.add(string("leQ"))
                    i += 1
                else:
                    result.add(string("ltQ"))
            case _ if s[i] == char('>'):
                if i < s.len - 1 and s[i + 1] == char('='):
                    result.add(string("geQ"))
                    i += 1
                else:
                    result.add(string("gtQ"))
            case _ if s[i] == char('$'): result.add(string("dollarQ"))
            case _ if s[i] == char('%'): result.add(string("percentQ"))
            case _ if s[i] == char('&'): result.add(string("ampQ"))
            case _ if s[i] == char('^'): result.add(string("roofQ"))
            case _ if s[i] == char('!'): result.add(string("emarkQ"))
            case _ if s[i] == char('?'): result.add(string("qmarkQ"))
            case _ if s[i] == char('*'): result.add(string("starQ"))
            case _ if s[i] == char('+'): result.add(string("plusQ"))
            case _ if s[i] == char('-'): result.add(string("minusQ"))
            case _ if s[i] == char('/'): result.add(string("slashQ"))
            case _ if s[i] == char('\\'): result.add(string("bslashQ"))
            case _ if s[i] == char('~'): result.add(string("tildeQ"))
            case _ if s[i] == char(':'): result.add(string("colonQ"))
            case _ if s[i] == char('@'): result.add(string("atQ"))
            case _ if s[i] == char('|'): result.add(string("barQ"))
            case _:
                _escape(result, s[i])
        i += 1
    return result


def toCChar(c: char, result: mut @ string):
    """{.inline.}"""
    match c:
        case _ if c in inrange(char('\x00'), char('\x1f')) or c in inrange(char('\x7f'), char('\xff')):
            result.add(char('\\'))
            _addOctal(result, c)
        case _ if c == char('\'') or c == char('"') or c == char('\\') or c == char('?'):
            result.add(char('\\'))
            result.add(c)
        case _:
            result.add(c)


def makeCString(s: string) -> string:
    result = newStringOfCap(s.len + 10)
    result.add(char('"'))
    for c in s: toCChar(c, result)
    result.add(char('"'))
    return result


if comptime(__name__ == "__main__"):
    from nimic.std import assertions

    assert mangleToC(string(r"foo.3.baz")) == "foo_3_baz"
    assert mangleToC(string(r"Query?")) == "QQueryqmarkQ"
    assert mangleToC(string(r"abc_def_[]=")) == "abcQ_defQ_putQ"
    assert mangleToC(string(r"[]")) == "getQ"
