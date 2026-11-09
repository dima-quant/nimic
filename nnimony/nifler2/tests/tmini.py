# /// nimic
# source: nimony@2c5b3dca14667398bef077edea2d036dd0ff949e:src/nifler2/tests/tmini.nim
# program: the main block runs the tests (the original runs them at its top level)
# ///
## End-to-end test of the generated parser: source text in, tree out.

from __future__ import annotations
from nimic.ntypes import *
from nimic.std import syncio, strutils
from .mini import openParser, pModule, TokKind


def _parse(src: string) -> string:
    with var:
        p = openParser(src)
    pModule(p)
    if p.tok().kind != TokKind.tkEof:
        p.error(string("unexpected trailing input"))
    result = p.render()
    if p.errors.len > 0:
        result = string("ERR: ") + p.errors.join(string(" | "))
    return result


def _check(name: string, src: string, expected: string):
    with let:
        got = _parse(src)
    if got == expected:
        echo("ok   ", name)
    else:
        echo("FAIL ", name)
        echo("  want: ", expected)
        echo("  got:  ", got)



if comptime(__name__ == "__main__"):
    _check(string("assignment"), string("x = 1"), string("(stmts (asgn x 1))"))

    _check(string("command"), string("foo a b"), string("(stmts (cmd foo a b))"))

    _check(string("bare expr"), string("x"), string("(stmts x)"))

    _check(string("semicolons"), string("x = 1; y = 2"), string("(stmts (asgn x 1) (asgn y 2))"))

    _check(string("two lines"), string("x = 1\ny = 2"), string("(stmts (asgn x 1) (asgn y 2))"))

    _check(string("indented block"), string("if c:\n  y = 2\n  bar z"), string("(stmts (if c (asgn y 2) (cmd bar z)))"))

    _check(string("inline body"), string("if c: y = 2"), string("(stmts (if c (asgn y 2)))"))

    _check(string("nested blocks"), string("while d:\n  if e:\n    q = 3\n  r = 4"), string("(stmts (while d (if e (asgn q 3)) (asgn r 4)))"))

    _check(string("block then sibling"), string("if c:\n  y = 2\nz = 3"), string("(stmts (if c (asgn y 2)) (asgn z 3))"))

    _check(string("left assoc of command"), string("f a b c"), string("(stmts (cmd f a b c))"))

    # --- errors the indentation machinery must catch
    _check(string("bad dedent"), string("if c:\n  y = 2\n r = 3"), string("ERR: (3,1) invalid indentation, got 'r' | (3,1) unexpected trailing input, got 'r'"))

    # --- precedence climbing (`binary`)
    _check(string("precedence"), string("x = 1 + 2 * 3"), string("(stmts (asgn x (infix + 1 (infix * 2 3))))"))

    _check(string("precedence left"), string("x = 1 - 2 - 3"), string("(stmts (asgn x (infix - (infix - 1 2) 3)))"))

    _check(string("precedence right"), string("x = 1 ^ 2 ^ 3"), string("(stmts (asgn x (infix ^ 1 (infix ^ 2 3))))"))

    _check(string("parens beat precedence"), string("x = (1 + 2) * 3"), string("(stmts (asgn x (infix * (infix + 1 2) 3)))"))

    # `binary` requires the operator to be on the same line, so `+ 2` is not
    # folded into the previous expression. This grammar has no prefix-operator
    # rule, so what is left cannot start a statement either -- which is exactly
    # how the rejection shows up.
    _check(string("operator must not start a line"), string("x = 1\n+ 2"), string("ERR: (2,0) unexpected trailing input, got '+'"))

    # --- the `^tag[...]` anchor: left-associative postfix chains
    _check(string("dot chain"), string("a.b.c"), string("(stmts (dot (dot a b) c))"))

    _check(string("call"), string("f(1, 2)"), string("(stmts (call f 1 2))"))

    _check(string("index"), string("a[i]"), string("(stmts (at a i))"))

    _check(string("mixed chain"), string("a.b(c).d[e]"), string("(stmts (at (dot (call (dot a b) c) d) e))"))

    _check(string("call with no args"), string("f()"), string("(stmts (call f))"))

    # --- the semantic predicate: a space before '(' makes it a command
    _check(string("space makes a command"), string("f (1)"), string("(stmts (cmd f 1))"))

    _check(string("no space is a call"), string("f(1)"), string("(stmts (call f 1))"))

    _check(string("suffix inside a block"), string("if c:\n  a.b = 1"), string("(stmts (if c (asgn (dot a b) 1)))"))
