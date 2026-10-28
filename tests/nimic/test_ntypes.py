
from __future__ import annotations
import ast
import builtins
import contextlib
import ctypes
import inspect
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest

from nimic.ntypes import *
from nimic.nsystem import ord as nim_ord, _BuildProfile, _n_set_build_profile
from nimic.ntypesystem import (BUFFER_REGISTRY, _n_routine_pragmas, nord, BufferRegistry, DICT_OF_C_TYPES, _match_subtype,
                               _n_aliases, _n_distinct_types, _n_from_text, _n_registry, _n_to_text,
                               NilPtr, char as _char, _n_assign_copies, _n_fingerprint, _n_param_mutable,
                               _n_result_may_alias, _n_templates)
from nimic.std.bitops import fastLog2
from nimic.std.endians import big_endian32
from nimic.std.formatfloat import addFloat
from nimic.std.hashes import Hash, hashIgnoreStyle, mix_hash, finish_hash, hash as nhash
from nimic.std.strutils import parseFloat
from nimic.std.math import FloatClass, classify, fcNormal, fcSubnormal, trunc
from nimic.std.options import Option, none, some
from nimic.std.os import ExeExt, absolutePath, addFileExt, changeFileExt, searchExtPos, fileExists, getCurrentDir, getEnv, walkDir
from nimic.std.parseutils import parse_hex, parse_ident, parseBiggestInt, parseBiggestUInt
from nimic.std.strscans import scanf
from nimic.std.strutils import isUpperAscii, find, nimIdentNormalize, repeat, rfind, split, strip, toLowerAscii
from nimic.std.syncio import lines, read_file
from nimic.std.tables import OrderedTable, Table, initOrderedTable, initTable
from nimic.system.ansi_c import c_free, c_malloc, csize_t
from nimic.transpiler import (unparse, private_name_collisions, check_private_names, free_call_overlaps,
                              check_imported_module)
from nimic import valuecheck

def _n_fwd_proc(a, b):
    """A forward declaration in this module (overloads below)."""
    pass


@dispatch
def _n_fwd_proc(a: nint, b: nint) -> nint:
    return a + b


class _NMethodHost(Object):
    """Procs of a type defined in the class (translation rules: methods) are also callable as free procs."""
    n: nint

    def grow(h: mut @ _NMethodHost, k: nint):
        h.n += k

    def grow(h: mut @ _NMethodHost, s: string):
        h.n += len(s)

    def total(h: _NMethodHost) -> nint:
        return h.n

    def __str__(h: _NMethodHost) -> string:
        return string("host ") + str(h.n)


class _NEnumWithDollar(NIntEnum):
    first = 0
    second = auto()

    def __str__(e: _NEnumWithDollar) -> string:
        return string("1st") if e == _NEnumWithDollar.first else string("2nd")


# An alias of an anonymous tuple type (Nim `Key = (string, string)`), used as a seq element before a
# field of another anonymous tuple type is resolved: the alias's name ("tuple") must not shadow `tuple`
_TTupKey = tuple[string, string]
_TTupKeys = seq[_TTupKey]


class _TTupHolder(Object):
    best: tuple[char, nint]
    keys: seq[_TTupKey]
    nested: tuple[seq[nint], tuple[nint, string]]


# Nim `{.pragma: name, p1, p2.}`: an alias of this module, used by the templates below
pragma("pragma: _tMaybeDirty, dirty")
pragma("pragma: _tTwice, _tMaybeDirty, inline")
pragma("pragma: _tNothing")


@template
def _tDirtyByAlias():
    """{._tMaybeDirty.}"""
    pass


@template
def _tCustomPragma(kind: string):
    """{.pragma.}"""


# Nim `BiTableFloat[Id] = distinct BiTable[Id, uint64]` (bitabs): a generic distinct object whose procs
# convert it to its base; module-level, as the specializations of generic procs run in the module's scope
class _TGTab[Id, T](Object):
    _vals: seq[T]


@distinct
class _TGTabF[Id](_TGTab[Id, uint64]):
    pass


@dispatch
def _tGAdd[Id, T](t: mut @ _TGTab[Id, T], v: T) -> Id:
    t._vals.add(v)
    return Id(t._vals.len)


@dispatch
def _tGAdd[Id](t: mut @ _TGTabF[Id], v: float64) -> Id:
    return _TGTab[Id, uint64](t)._tGAdd(cast[uint64](v))


# nifpools' `template buildTree*[T: enum](dest: var TokenBuf; tag: T; info; body: untyped)`: a generic block
# template next to a concrete one of the same name; module-level, as the specializations run in the module's scope
class _TBlkTag(NIntEnum):
    a = auto()
    b = auto()


@template
def _tBlkTree(out: mut @ seq[string], tag: nint, body: untyped):
    out.add(string("(int ") + str(tag))
    body
    out.add(string(")"))


@template
def _tBlkTree[T: enum](out: mut @ seq[string], tag: T, body: untyped):
    out.add(string("(high ") + str(ord(high(T))) + string(" ") + str(ord(tag)))
    body
    out.add(string(")"))


class TestNTypes(unittest.TestCase):

    def test_integers_initialization(self):
        # Test basic initialization
        _i32 = int32(10)
        self.assertEqual(int(_i32), 10)
        self.assertEqual(str(_i32), "10")

        _u64 = uint64(100)
        self.assertEqual(int(_u64), 100)

        # Test default initialization (should be 0)
        self.assertEqual(int(int32()), 0)
        self.assertEqual(int(uint64()), 0)

    def test_int32_range(self):
        # This specifically tests the fix for "int32 object cannot be interpreted as an integer"
        i = int32(5)
        r = range(i)
        self.assertEqual(list(r), [0, 1, 2, 3, 4])

        start = int32(2)
        end = int32(5)
        r2 = range(start, end)
        self.assertEqual(list(r2), [2, 3, 4])

    def test_integer_overflow_underflow(self):
        """Nim: signed overflow raises OverflowDefect (overflow checks on, the default build);
        unsigned arithmetic wraps; +% and -% always wrap."""
        val = int8(127)
        with self.assertRaises(OverflowDefect):
            val += 1
        with self.assertRaises(OverflowDefect):
            _ = int8(-128) - 1
        with self.assertRaises(OverflowDefect):
            _ = -int8(-128)
        with self.assertRaises(OverflowDefect):
            _ = high(nint) * 190
        with self.assertRaises(OverflowDefect):
            _ = low(int64) // int64(-1)
        self.assertEqual(int(int8(127).plus_percent(1)), -128)
        self.assertEqual(int(int8(1) << 7), -128)  # shifts don't check

        # uint8: 0 to 255
        uval = uint8(255)
        uval += 1
        self.assertEqual(int(uval), 0)

        uval = uint8(0)
        uval -= 1
        self.assertEqual(int(uval), 255)

    def test_integer_arithmetic(self):
        a = int32(10)
        b = int32(3)

        self.assertEqual(int(a + b), 13)
        self.assertEqual(int(a - b), 7)
        self.assertEqual(int(a * b), 30)
        self.assertEqual(int(a // b), 3)  # Floor division
        self.assertEqual(int(a % b), 1)

        # Test mixing with python int
        self.assertEqual(int(a + 5), 15)
        self.assertEqual(int(5 + a), 15)

    def test_integer_bitwise(self):
        a = uint8(0b1100) # 12
        b = uint8(0b1010) # 10

        self.assertEqual(int(a & b), 0b1000) # 8
        self.assertEqual(int(a | b), 0b1110) # 14
        self.assertEqual(int(a ^ b), 0b0110) # 6
        self.assertEqual(int(~a), 0b11110011) # ~12 in 8-bit unsigned is 243 (255-12)

        # Shift
        x = uint8(1)
        self.assertEqual(int(x << 1), 2)
        self.assertEqual(int(x << 7), 128)
        # Overflow shift
        self.assertEqual(int(x << 8), 0)

    def test_float_operations(self):
        f = float64(1.5)
        self.assertAlmostEqual(float(f), 1.5)

        f2 = float64(2.0)
        res = f + f2
        self.assertIsInstance(res, float64)
        self.assertAlmostEqual(float(res), 3.5)

        # Test mixing types
        res2 = f + int32(2) # Should promote to float64
        self.assertIsInstance(res2, float64)
        self.assertAlmostEqual(float(res2), 3.5)

        # Test mixing types
        res3 = int32(1) * f # Should promote to float64
        self.assertIsInstance(res3, float64)
        self.assertAlmostEqual(float(res3), 1.5)

        # Test mixing with literals
        res4 = int32(2) * 0.75 # Should promote to float64
        self.assertIsInstance(res4, float64)
        self.assertAlmostEqual(float(res4), 1.5)

        # Test truediv on ints
        res5 = int32(3) / int32(2) # Should promote to float64
        self.assertIsInstance(res5, float64)
        self.assertAlmostEqual(float(res5), 1.5)

    def test_object_subclassing_and_init(self):
        class MyVec(Object):
            x: float64
            y: float64
            z: float64

        v = MyVec(x=1.0, y=2.0, z=0.0) # z needs explicit init with current Object implementation
        self.assertAlmostEqual(float(v.x), 1.0)
        self.assertAlmostEqual(float(v.y), 2.0)
        self.assertAlmostEqual(float(v.z), 0.0)

        # Update attribute
        v.z = 3.0
        self.assertAlmostEqual(float(v.z), 3.0)

        # Type enforcement/conversion
        v.x = 5 # Assign int, should convert to float64
        self.assertIsInstance(v.x, float64)
        self.assertAlmostEqual(float(v.x), 5.0)

    def test_object_with_nested_object(self):
        class Point(Object):
            x: int32
            y: int32

        class Rect(Object):
            top_left: Point
            bottom_right: Point

        r = Rect()
        # Default initialization check
        self.assertEqual(int(r.top_left.x), 0)

        r.top_left.x = 10
        r.top_left.y = 20
        self.assertEqual(int(r.top_left.x), 10)

        # Assignment with object
        p = Point(x=100, y=200)
        r.bottom_right = p
        self.assertEqual(int(r.bottom_right.x), 100)

    def test_sequences(self):
        s = seq[int32]()
        self.assertEqual(len(s), 0)

        s.add(int32(10))
        s.add(20) # Should convert to int32

        self.assertEqual(len(s), 2)
        self.assertEqual(int(s[0]), 10)
        self.assertEqual(int(s[1]), 20)

        s[0] = 5
        self.assertEqual(int(s[0]), 5)

        # Test automatic resizing (implied by adding many Items if we wanted stress test,
        # but here just checking basic functionality)

    def test_seq_in_object(self):
        class Polygon(Object):
            points: seq[int32]

        poly = Polygon()
        self.assertEqual(len(poly.points), 0)

        poly.points.add(1)
        poly.points.add(2)
        self.assertEqual(len(poly.points), 2)
        self.assertEqual(int(poly.points[1]), 2)

    def test_in_place_ops(self):
        i = int32(10)
        i += 5
        self.assertEqual(int(i), 15)

        i *= 2
        self.assertEqual(int(i), 30)

        # Test overflow in place
        b = uint8(250)
        b += 10 # 260 -> 4
        self.assertEqual(int(b), 4)

    def test_unchecked_array_cast(self):
        # Simulate memory allocation

        count = 10
        size_bytes = count * 4 # 4 bytes for int32
        mem = c_malloc(csize_t(size_bytes))

        # Cast to UncheckedArray
        arr_ptr = cast[ptr[UncheckedArray[int32]]](mem)

        # Access elements
        for i in range(count):
            arr_ptr[i] = int32(i * 10)

        # Verify
        for i in range(count):
            self.assertEqual(int(arr_ptr[i]), i * 10)


        c_free(mem)

    def test_classes_without_future_annotations(self):
        """A module without `from __future__ import annotations` (Python 3.14, PEP 649: the class body keeps only
        __annotate_func__) defines the same fields: plain, ptr (nil by default), and a variant object whose body
        reads its discriminator (`match kind:`)."""
        source = textwrap.dedent("""\
            from nimic.ntypes import *

            class Kind(NIntEnum):
                kA = auto()
                kB = auto()

            class O(Object):
                rc: nint

            class T(Object):
                owner: ptr[O]
                n: nint

            class V(Object):
                kind: Kind
                match kind:
                    case Kind.kA:
                        a: nint
                    case Kind.kB:
                        b: string

            t = T(n=nint(3))
            print(int(t.n), isNil(t.owner), sorted(T._n_fields))
            v = V(kind=Kind.kB, b=string("x"))
            print(str(v.b), sorted(V._n_fields))
            """)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "no_future.py")
            with open(path, "w") as f:
                f.write(source)
            run = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr[-800:])
        # the same as with the future import (a variant class lists the fields of all its branches)
        self.assertEqual(run.stdout.splitlines(), ["3 True ['n', 'owner']", "x ['a', 'b', 'kind']"])

    def test_unchecked_char_cursor_into_string(self):
        """A `ptr UncheckedArray[char]` into a string's payload (nifbuilder's write cursor): writes land in
        the string, a slot written twice reads the second value, `addr(raw[i])` is the address of byte i
        (copyMem through it), and the string sees all of it after a setLen."""
        s = string("")
        s.setLen(8)
        raw = cast[ptr[UncheckedArray[char]]](addr(s[0]))
        raw[0] = char('a')
        self.assertEqual(raw[0], char('a'))
        raw[0] = char('b')
        self.assertEqual((raw[0], s[0]), (char('b'), char('b')))
        src = string("xyz")
        copyMem(cast[pointer](addr(raw[1])), cast[pointer](addr(src[0])), 3)
        self.assertEqual((raw[1], raw[2], raw[3]), (char('x'), char('y'), char('z')))
        raw[2] = char('Y')
        s.setLen(4)
        self.assertEqual(s, string("bxYz"))

    def test_dispatch_dollar_argument_is_string(self):
        """Nim's `$x` is a string: `str(x)` passed to a `string` parameter of a dispatched proc arrives as a
        nimic string (nifbuilder's `b.put $i`), as a literal arrives as the parameter's scalar type."""
        @dispatch
        def _tPutStr(s: string) -> nint:
            self.assertIsInstance(s, string)
            return s.len

        @dispatch
        def _tPutStr(s: string, n: nint) -> nint:
            return s.len + n

        self.assertEqual(_tPutStr(str(int64(-12345))), 6)
        self.assertEqual(_tPutStr(str(uint64(999)), 1), 4)
        self.assertEqual(_tPutStr(string("ab")), 2)

    def test_cast_to_enum(self):
        """`cast[E](x)` of an integer or of another enum's member is the member of E with that ordinal, for
        int and string-valued enums with holes (nifcdecl's `cast[LengStmt](tagEnum)`)."""
        class _TTag(NIntEnum):
            InvalidTag = 0
            StmtsTag = 1
            CallTag = 5

        class _TStmt(NStrEnum):
            NoStmt = (0, "nostmt")
            StmtsS = (1, "stmts")
            CallS = (5, "call")

        self.assertIs(cast[_TTag](uint32(5)), _TTag.CallTag)
        self.assertIs(cast[_TStmt](_TTag.CallTag), _TStmt.CallS)
        self.assertIs(cast[_TStmt](uint32(1)), _TStmt.StmtsS)
        self.assertIs(cast[_TTag](_TStmt.CallS), _TTag.CallTag)
        with self.assertRaises(ValueError):
            cast[_TStmt](uint32(3))

    def test_union_type_alias_is_type_class(self):
        """A module-level `Kind = A | B` (rule:typealias; also `type Kind = A | B`) is a type class: a
        parameter `expected: Kind` takes a member of A or B (nifcdecl's `LengTagKind`), not of a third
        enum, and transpiles to `type Kind* = A or B`."""
        src = ("from nimic.ntypes import *\n"
               "class _A(NIntEnum):\n"
               "    a1 = auto()\n"
               "class _B(NIntEnum):\n"
               "    b1 = auto()\n"
               "class _C(NIntEnum):\n"
               "    c1 = auto()\n"
               "Kind = _A | _B\n"
               "type Kind2 = _A | _B\n"
               "@dispatch\n"
               "def f(x: nint, expected: Kind) -> string:\n"
               "    return string('A') if isinstance(expected, _A) else string('B')\n"
               "@dispatch\n"
               "def g(expected: Kind2) -> bool:\n"
               "    return isinstance(expected, Kind2.__value__)\n")
        ns = {"__name__": "_t_union_alias"}
        exec(src, ns)
        self.assertEqual((ns["f"](nint(1), ns["_A"].a1), ns["f"](nint(1), ns["_B"].b1)), (string("A"), string("B")))
        self.assertTrue(ns["g"](ns["_B"].b1))
        with self.assertRaises(NotImplementedError):
            ns["f"](nint(1), ns["_C"].c1)
        out = unparse(ast.parse(src))[0]
        self.assertIn("Kind* = A or B", out)

    def test_field_store_copies_value(self):
        """Nim's `o.f = x` copies a value (rules §1.1: stores copy by themselves): a string, seq or object
        stored into a field is independent of `x` afterwards, also for a field the constructor didn't name
        (nifcdecl's `result = TypeDecl(name: n); skip n; result.pragmas = n`), and such a field is one of the
        object's fields. A ref is shared, and an in-place `o.f <<= x` keeps the field's value."""
        @ref
        class _TRefBox(Object):
            n: nint

        class _TFields(Object):
            name: string
            pragmas: string
            q: seq[nint]
            r: _TRefBox

        n = string("name")
        o = _TFields(name=n)
        n.add(char('!'))
        o.pragmas = n
        n.add(char('?'))
        self.assertEqual((o.name, o.pragmas), (string("name"), string("name!")))
        self.assertEqual(list(o._n_fields), ["name", "pragmas", "q", "r"])
        q = seq[nint]([1])
        o.q = q
        q.add(nint(2))
        self.assertEqual(len(o.q), 1)
        r = _TRefBox()
        o.r = r
        self.assertIs(o.r, r)
        field = o.name
        o.name <<= string("other")
        self.assertIs(o.name, field)
        self.assertEqual(o.name, string("other"))

    def test_nim_allocator(self):
        """Nim's alloc / alloc0 / realloc / dealloc / create / resize (nsystem): blocks of raw memory, seen
        through casts; realloc keeps the content; dealloc of anything but a block's start is a ValueError
        (Nim: undefined behavior) and leaves the pointer dangling, not nil."""
        p = alloc0(4 * 4)
        a = cast[ptr[UncheckedArray[int32]]](p)
        for i in range(4):
            self.assertEqual(int(a[i]), 0)
            a[i] = int32(i + 1)
        q = realloc(p, 8 * 4)
        b = cast[ptr[UncheckedArray[int32]]](q)
        self.assertEqual([int(b[i]) for i in range(8)], [1, 2, 3, 4, 0, 0, 0, 0])
        with self.assertRaises(ValueError):
            dealloc(p)  # p was freed by realloc
        self.assertNotEqual(p._n_addr, 0)  # dangling, not nil
        r = realloc(q, 2 * 4)
        c = cast[ptr[UncheckedArray[int32]]](r)
        self.assertEqual([int(c[i]) for i in range(2)], [1, 2])
        dealloc(r)
        with self.assertRaises(ValueError):
            dealloc(r)
        inner = alloc(16)
        with self.assertRaises(ValueError):
            dealloc(addr(cast[ptr[UncheckedArray[int32]]](inner)[1]))  # not a block's start
        dealloc(inner)
        n = realloc(None, 3)  # realloc(nil, n) is alloc(n)
        self.assertTrue(isNil(realloc(n, 0)))  # realloc(p, 0) frees p
        dealloc(alloc(0))  # alloc(0) is a block of its own
        z = realloc0(alloc(2), 2, 6)
        self.assertEqual([int(cast[ptr[UncheckedArray[uint8]]](z)[i]) for i in range(6)], [0] * 6)
        dealloc(z)

        class _TPair(Object):
            a: int32
            b: int32

        pairs = create(_TPair, 2)
        pairs.contents.a = int32(7)
        self.assertEqual(int(cast[ptr[_TPair]](pairs).contents.a), 7)
        pairs = resize(pairs, 4)
        self.assertEqual(int(pairs.contents.a), 7)
        dealloc(pairs)

    def test_pointer_equality_and_nil(self):
        """Pointers compare by where they point (Nim), not as Python objects: two casts of one address are equal
        (nifcore's `=copy` tests `dest.p != src.p`), nil is address 0, and an unset ptr field (a pointer holding
        address 0) is nil for isNil and `== None`."""
        class _TPtrTarget(Object):
            rc: nint

        class _TPtrHolder(Object):
            owner: ptr[_TPtrTarget]

        mem = alloc0(sizeof(_TPtrTarget) * 2)
        p = cast[ptr[_TPtrTarget]](mem)
        q = cast[ptr[_TPtrTarget]](cast[pointer](p))
        self.assertTrue(p == q)
        self.assertFalse(p != q)
        self.assertEqual(hash(p), hash(q))
        other = cast[ptr[_TPtrTarget]](addr(cast[ptr[UncheckedArray[_TPtrTarget]]](mem)[1]))
        self.assertTrue(p != other)
        holder = _TPtrHolder()
        self.assertTrue(isNil(holder.owner))
        self.assertTrue(holder.owner == None)  # noqa: E711 (Nim `== nil`)
        self.assertTrue(NilPtr("ptr[_TPtrTarget]") == holder.owner)
        self.assertFalse(isNil(p))
        holder.owner = p
        self.assertTrue(holder.owner == p)
        dealloc(mem)

    def test_pointer_arithmetic_nifcore_patterns(self):
        """nifcore's address arithmetic: `cast[ptr T](cast[uint](p) + n * sizeof(T).uint)`, the difference of two
        addresses divided by the element size, an alignment test with `and`, and an address from an integer."""
        @distinct
        class _TToken(uint32):
            pass

        data = cast[ptr[UncheckedArray[_TToken]]](alloc(sizeof(_TToken) * 4))
        for i in range(3):
            data[i] = _TToken(7 + 2 * i)
        p = addr(data[0])
        q = cast[ptr[_TToken]](cast[uintp](p) + uint(2) * uint(sizeof(_TToken)))
        self.assertEqual(int(uint32(q.contents)), 11)
        self.assertEqual(int((cast[uintp](q) - cast[uintp](p)) // uint(sizeof(_TToken))), 2)
        self.assertEqual(cast[uintp](data) & (uint(sizeof(_TToken)) - uint(1)), 0)  # aligned
        self.assertEqual(cast[uintp](q) | 0, int(cast[uintp](q)))
        self.assertEqual(int(uintp(4096)), 4096)
        self.assertTrue(uintp(0).is_nil)
        out = unparse(ast.parse("from nimic.ntypes import *\n"
                                "def f(p: ptr[uint32], data: pointer) -> bool:\n"
                                "    q = cast[ptr[uint32]](cast[uintp](p) + uint(2) * uint(sizeof(uint32)))\n"
                                "    return (cast[uintp](data) & (uint(sizeof(uint32)) - uint(1))) == 0\n"))[0]
        # uintp is ncode/pydefs' `uintp* = uint`; Nim's `and` binds looser than `-`, no parentheses needed
        self.assertIn("cast[ptr uint32](cast[uintp](p) + uint(2) * uint(sizeof(uint32)))", out)
        self.assertIn("(cast[uintp](data) and uint(sizeof(uint32)) - uint(1)) == 0", out)
        dealloc(data)

    def test_builtin_type_class_constraints(self):
        """Nim's built-in type classes bound a type parameter under @dispatch: `[E: enum]` (nifcore's createTags),
        `[T: object]`, `[T: ref]`; another type doesn't fit. Overloads that differ only in their bounds are
        distinct."""
        class _TClassColor(NIntEnum):
            red = auto()
            green = auto()

        class _TClassBox(Object):
            v: nint

        @ref
        class _TClassNode(Object):
            v: nint

        @dispatch
        def _tCount[E: enum](x: E) -> nint:
            return nint(len(E))

        @dispatch
        def _tKind[T: object](x: T) -> string:
            return string("object")

        @dispatch
        def _tKind[T: ref](x: T) -> string:
            return string("ref")

        self.assertEqual(_tCount(_TClassColor.green), 2)
        with self.assertRaises(NotImplementedError):
            _tCount(nint(1))
        self.assertEqual(_tKind(_TClassBox()), "object")
        self.assertEqual(_tKind(_TClassNode()), "ref")

        # overloads that differ only in their bounds are distinct (the second replaced the first)
        @dispatch
        def _tNum[T: SomeInteger](x: T) -> string:
            return string("int")

        @dispatch
        def _tNum[T: SomeFloat](x: T) -> string:
            return string("float")

        self.assertEqual(_tNum(nint(1)), "int")
        self.assertEqual(_tNum(float64(1.5)), "float")
        self.assertEqual(_tNum(uint8(3)), "int")

    def test_compile_option(self):
        """compileOption (nifcore: `const assertionsEnabled = compileOption("assertions")`) answers from the
        emulated Nim build: on/off checks and traces, and value options (mm, backend, cc); another option is a
        ValueError. It transpiles as it is written."""
        _n_set_build_profile(_BuildProfile())  # Nim's defaults, whatever NIMIC_DEFINES says
        try:
            self.assertTrue(compileOption("assertions"))
            self.assertTrue(compileOption("boundChecks"))
            self.assertTrue(compileOption("mm", "orc"))
            self.assertFalse(compileOption("mm", "arc"))
            self.assertTrue(compileOption("backend", "c"))
            with self.assertRaises(ValueError):
                compileOption("noSuchOption")
            with self.assertRaises(ValueError):
                compileOption("noSuchOption", "x")
        finally:
            _n_set_build_profile(None)  # back to the lazily created profile
        out = unparse(ast.parse("from nimic.ntypes import *\nwith const:\n    _a = compileOption('assertions')\n"))[0]
        self.assertIn('a = compileOption("assertions")', out)

    def test_gc_ref_unref(self):
        """GC_ref(x) keeps x alive while only raw memory refers to it; GC_unref undoes one GC_ref (more
        GC_unrefs than GC_refs is a ValueError: Nim would free a live object)."""
        import gc
        import weakref

        @ref
        class _TPool(Object):
            n: nint

        pool = _TPool(n=nint(1))
        alive = weakref.ref(pool)
        GC_ref(pool)
        GC_ref(pool)
        del pool
        gc.collect()
        self.assertIsNotNone(alive())
        GC_unref(alive())
        self.assertIsNotNone(alive())
        GC_unref(alive())
        gc.collect()
        self.assertIsNone(alive())
        with self.assertRaises(ValueError):
            GC_unref(_TPool())
        GC_ref(None)  # nil: nothing to keep
        GC_unref(None)

    def test_refs_in_c_storage(self):
        """A ref field of a ctypes-backed object is nil by default (Nim), and holds a handle in its slot: every
        view of the memory (casts, derefs) reads the same ref. Written through a view of raw memory (alloc),
        the slot keeps the ref alive until it is overwritten or the block is freed; realloc moves it along.
        A slot whose ref died is a ReferenceError (Nim: a dangling ref)."""
        import gc
        import weakref

        @ref
        class _TRefPool(Object):
            n: nint

        class _TOwnerObj(Object):
            rc: nint
            pool: _TRefPool

        self.assertIsNone(_TOwnerObj().pool)
        self.assertIsNone(default(_TOwnerObj).pool)
        mem = alloc0(sizeof(_TOwnerObj))
        cast[ptr[_TOwnerObj]](mem).contents.pool = _TRefPool(n=nint(7))  # only the raw memory refers to it
        gc.collect()
        again = cast[ptr[_TOwnerObj]](mem).contents.pool
        self.assertEqual(int(again.n), 7)
        self.assertIs(cast[ptr[_TOwnerObj]](mem).contents.pool, again)
        alive = weakref.ref(again)
        del again
        mem = realloc(mem, sizeof(_TOwnerObj) * 2)  # the pin moves with the content
        gc.collect()
        self.assertIsNotNone(alive())
        self.assertIs(cast[ptr[_TOwnerObj]](mem).contents.pool, alive())
        cast[ptr[_TOwnerObj]](mem).contents.pool = None  # overwriting the slot releases it
        gc.collect()
        self.assertIsNone(alive())
        self.assertIsNone(cast[ptr[_TOwnerObj]](mem).contents.pool)
        second = _TRefPool(n=nint(8))
        cast[ptr[_TOwnerObj]](mem).contents.pool = second
        alive = weakref.ref(second)
        del second
        dealloc(mem)  # freeing the block releases its refs
        gc.collect()
        self.assertIsNone(alive())
        # an owning object keeps its refs itself; a view of its memory reads them by handle
        owner = _TOwnerObj(pool=_TRefPool(n=nint(9)))
        self.assertEqual(int(cast[ptr[_TOwnerObj]](addr(owner)).contents.pool.n), 9)
        # a ref that died behind a slot: dangling
        mem = alloc0(sizeof(_TOwnerObj))
        holder = _TOwnerObj(pool=_TRefPool(n=nint(1)))
        copyMem(mem, addr(holder), sizeof(_TOwnerObj))  # raw copy: the handle, no pin (as Nim: no count)
        del holder
        gc.collect()
        with self.assertRaises(ReferenceError):
            cast[ptr[_TOwnerObj]](mem).contents.pool
        dealloc(mem)

    def test_object_array_cast(self):
        # Simulate memory allocation for Objects

        class Point(Object):
            x: int32
            y: int32

        count = 5
        # We need to know sizeof(Point). In ntypes it uses struct padding etc.
        # For simple int32 x, y it should be 8 bytes.
        size_bytes = count * 8
        mem = c_malloc(csize_t(size_bytes))

        # Cast to UncheckedArray[Point]
        arr_ptr = cast[ptr[UncheckedArray[Point]]](mem)

        # Initialize and verify
        for i in range(count):
            # Write via object interface if supported, or field by field
            # UncheckedArray[Object] returns an Object instance mapped to that memory
            # accessing fields should write to memory
            p = arr_ptr[i]
            p.x = i
            p.y = i * 2

        for i in range(count):
            p = arr_ptr[i]
            self.assertEqual(p.x, i)
            self.assertEqual(p.y, i * 2)

        c_free(mem)

    def test_seq_cast_to_unchecked_array(self):
        # Test casting from seq buffer to UncheckedArray like in hittables_lists.py

        class Point(Object):
            x: int32
            y: int32

        s = seq[Point]()
        for i in range(5):
            p = Point(x=i, y=i*2)
            s.add(p)

        first_elem = s[0]
        ptr_to_first = unsafe_addr(first_elem)

        # In Python simulation, cast[] needs the type
        # The syntax in python is cast[Type](value)
        arr_ptr = cast[ptr[UncheckedArray[Point]]](ptr_to_first)

        # Verify view
        for i in range(5):
            p = arr_ptr[i]
            self.assertEqual(p.x, i)
            self.assertEqual(p.y, i * 2)

        # Verify shared memory (modifying view modifies seq)
        arr_ptr[0].x = 100
        self.assertEqual(s[0].x, 100)

    def test_method_dispatch(self):
        # Test method overloading by argument type

        class Dispatcher(Object):
            id: int32

            def process(self, x: int32) -> int32:
                return x + 1

            def process(self, x: float64) -> float64:
                return x + 10.0

        d = Dispatcher()

        # Test int32 dispatch
        res_i = d.process(int32(5))
        self.assertIsInstance(res_i, int32)
        self.assertEqual(res_i, 6)

        # Test float64 dispatch
        res_f = d.process(float64(5.0))
        self.assertIsInstance(res_f, float64)
        self.assertAlmostEqual(res_f, 15.0)

    def test_subtype_dispatch(self):
        # Test that dispatch matches subtypes (e.g. Color dispatches to Vec3 handler)

        class TVec(Object):
            x: float64
            y: float64

        @distinct
        class TColor(TVec):
            """{.borrow: `.`.}"""
            @converter
            def toCVec(uv: TColor) -> TVec:
                return TVec(uv)

        @dispatch
        def length_sq(v: TVec) -> float64:
            return v.x * v.x + v.y * v.y

        # Direct match on TVec
        v = TVec(x=3.0, y=4.0)
        self.assertAlmostEqual(float(length_sq(v)), 25.0)

        # Subtype match: TColor is a subclass of TVec
        c = TColor(TVec(x=1.0, y=2.0))
        result = length_sq(c)
        self.assertAlmostEqual(float(result), 5.0)

    def test_distinct_blocks_methods(self):
        # Base type with methods
        class TBase(Object):
            x: float64
            y: float64

            def length_sq(self: TBase) -> float64:
                return self.x * self.x + self.y * self.y

            def __add__(self: TBase, other: TBase) -> TBase:
                result = TBase()
                result.x = self.x + other.x
                result.y = self.y + other.y
                return result

            def scale(self: TBase, s: float64) -> TBase:
                result = TBase()
                result.x = self.x * s
                result.y = self.y * s
                return result

        # Distinct type — only borrows __add__, blocks length_sq and scale
        @distinct
        class TDist(TBase):
            """{.borrow: `.`.}"""

            def __add__(self: TDist, other: TDist) -> TDist:
                """{.borrow.}"""
                return super().__add__(other)

        d1 = TDist(TBase(x=1.0, y=2.0))
        d2 = TDist(TBase(x=3.0, y=4.0))

        # Field access works (borrow: `.`)
        self.assertAlmostEqual(float(d1.x), 1.0)
        self.assertAlmostEqual(float(d1.y), 2.0)

        # Borrowed method works
        d3 = d1 + d2
        self.assertAlmostEqual(float(d3.x), 4.0)
        self.assertAlmostEqual(float(d3.y), 6.0)

        # Non-borrowed methods are blocked
        with self.assertRaises(AttributeError):
            d1.length_sq()

        with self.assertRaises(AttributeError):
            d1.scale(float64(2.0))

    def test_converter_preserves_methods(self):
        # Base type with a method
        class CVec(Object):
            x: float64
            y: float64

            def length_sq(self: CVec) -> float64:
                return self.x * self.x + self.y * self.y

        # Distinct type WITH converter → keeps inherited methods
        @distinct
        class CUnit(CVec):
            """{.borrow: `.`.}"""

            @converter
            def toCVec(uv: CUnit) -> CVec:
                return CVec(uv)

        u = CUnit(CVec(x=3.0, y=4.0))
        # Inherited method is available thanks to converter
        self.assertAlmostEqual(float(u.length_sq()), 25.0)

    def test_converter_dispatch(self):
        # dispatch resolves via converter: function for CVec matches CUnit args
        class DVec(Object):
            x: float64
            y: float64

        @distinct
        class DUnit(DVec):
            """{.borrow: `.`.}"""
            @converter
            def toDVec(uv: DUnit) -> DVec:
                return DVec(uv)

        @dispatch
        def dot_product(a: DVec, b: DVec) -> float64:
            return a.x * b.x + a.y * b.y

        v = DVec(x=3.0, y=4.0)
        u = DUnit(DVec(x=1.0, y=2.0))

        # DVec × DVec — exact match
        self.assertAlmostEqual(float(dot_product(v, v)), 25.0)

        # DUnit × DVec — converter match on first arg
        self.assertAlmostEqual(float(dot_product(u, v)), 11.0)

        # DUnit × DUnit — converter match on both args
        self.assertAlmostEqual(float(dot_product(u, u)), 5.0)

    def test_example(self):
        # Struct definition (Nim object)
        class Vec3(Object):
            x: float64
            y: float64
            z: float64

            def __add__(self: Vec3, v: Vec3) -> Vec3:
                """{.inline.}"""
                result = Vec3()
                result.x = self.x + v.x
                result.y = self.y + v.y
                result.z = self.z + v.z
                return result

        # Distinct type
        @distinct
        class Point3(Vec3):
            """{.borrow: `.`.}"""

        # Multi-dispatch
        @dispatch
        def point3(x: float64, y: float64, z: float64) -> Point3:
            result = Point3(Vec3())
            result.x = x; result.y = y; result.z = z
            return result

        # Usage
        with let:
            a = point3(1.0, 2.0, 3.0)
            b = point3(4.0, 5.0, 6.0)
            c = Vec3(a) + Vec3(b)

    def test_option(self):

        # some() wraps a value
        opt_s = some(int32(42))
        self.assertTrue(opt_s.is_some())
        self.assertFalse(opt_s.is_none())
        self.assertEqual(int(opt_s.get()), 42)

        # none() is empty
        opt_n = none(int32)
        self.assertFalse(opt_n.is_some())
        self.assertTrue(opt_n.is_none())

        # get() on none raises ValueError
        with self.assertRaises(ValueError):
            opt_n.get()

        # unsafe_get returns value without check
        self.assertEqual(int(opt_s.unsafe_get()), 42)

        # equality
        self.assertEqual(some(int32(10)), some(int32(10)))
        self.assertNotEqual(some(int32(10)), some(int32(20)))
        self.assertEqual(none(), none())
        self.assertNotEqual(some(int32(10)), none())

        # truthiness
        self.assertTrue(bool(some(int32(1))))
        self.assertFalse(bool(none()))

        # Option[T] generic syntax
        OptI32 = Option[int32]
        opt_typed = OptI32(int32(7), _has_value=True)
        self.assertTrue(opt_typed.is_some())
        self.assertEqual(int(opt_typed.get()), 7)

        # repr
        self.assertIn("some(", repr(some(int32(5))))
        self.assertEqual(repr(none()), "none")

    def test_generic_dispatch(self):
        """Test that generic [T] functions are specialized on first call."""

        @dispatch
        def foo[T](x: T) -> seq[T]:
            result = seq[T]()
            result.add(x)
            print(T)
            return result

        # Call with int32 — should specialize T=int32
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            s = foo(int32(42))
        # The print(T) should print the resolved type class
        printed = buf.getvalue().strip()
        self.assertIn("int32", printed)
        # Result should be seq[int32] with one element
        self.assertEqual(len(s), 1)
        self.assertEqual(int(s[0]), 42)

        # Call again with int32 — should use cached specialization
        s2 = foo(int32(7))
        self.assertEqual(len(s2), 1)
        self.assertEqual(int(s2[0]), 7)

        # Call with float64 — should specialize T=float64
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            s3 = foo(float64(3.14))
        printed2 = buf2.getvalue().strip()
        self.assertIn("float64", printed2)
        self.assertEqual(len(s3), 1)
        self.assertAlmostEqual(float(s3[0]), 3.14)

    def test_pointer_arithmetic(self):
        """Test arithmetic on byte addresses via intp/uintp."""

        # Test basic pointer logic
        class SimpleObj(Object):
            val: int32

        obj = SimpleObj(val=10)
        p = addr(obj)

        # Test casting to byte address (uintp/intp)
        up = cast[uintp](p)
        ip = cast[intp](p)

        # Validate that properties matched the wrapper address
        self.assertFalse(up.is_nil)
        self.assertFalse(ip.is_nil)

        # Verify that __add__ increments address correctly
        # p represents address of obj. If we do ip + 4 (sizeof int32), it advances 4 bytes.
        ip_plus_4 = ip + 4

        # ptr - ptr = offset
        self.assertEqual(ip_plus_4 - ip, 4)

        # uintp syntax test: cast[uintp](p) + bytes
        up_plus_8 = cast[uintp](p) + 8
        self.assertEqual(up_plus_8 - cast[uintp](p), 8)

        # Ensure that subtraction handles generic addresses
        diff = up_plus_8 - up
        self.assertEqual(diff, 8)

        # Test allocation and indexing with intp
        mem = c_malloc(csize_t(16))
        mem_ip = cast[intp](mem)
        mem_ip_offset = mem_ip + 8
        self.assertEqual(mem_ip_offset - mem_ip, 8)
        c_free(mem)

    def test_pointer_arithmetic_cast(self):
        """Test casting from advanced intp back to a structured pointer."""

        class MultiFields(Object):
            a: int32
            b: int32
            c: int32

        # Allocate array of 3 MultiFields (3 * 12 = 36 bytes)
        mem = c_malloc(csize_t(36))

        # Access as array to setup data
        arr_ptr = cast[ptr[UncheckedArray[MultiFields]]](mem)
        for i in range(3):
            arr_ptr[i].a = i * 10
            arr_ptr[i].b = i * 10 + 1
            arr_ptr[i].c = i * 10 + 2

        # Get base address
        base_ip = cast[intp](mem)

        # Advance by exactly one MultiFields struct (12 bytes)
        ip_plus_1 = base_ip + 12

        # Cast back to ptr[MultiFields]
        ptr_to_second = cast[ptr[MultiFields]](ip_plus_1)

        # Verify it points to the second element
        self.assertEqual(int(ptr_to_second.a), 10)
        self.assertEqual(int(ptr_to_second.b), 11)
        self.assertEqual(int(ptr_to_second.c), 12)

        c_free(mem)


    def test_addr(self):

        class BitBuffer(Object):
            shift: nint
            cache: uint32
            buf: ptr[UncheckedArray[byte]]
            cursor: nint
        
        sps = newSeq[byte](32)
        with var:
            bb = BitBuffer(
                shift=0,
                cache=0,
                buf=cast[ptr[UncheckedArray[uint8]]](addr(sps[0])),
                cursor=0
            )
        
        sps[0:4] = array[4, byte]([0x00, 0x00, 0x00, 0x01])
        bb.shift = 5
        bb.cursor = 4

        bb.cache = uint32(0)
        with let:
            val = uint32(7)
            n = 5
        bb.shift -= n
        bb.cache = bb.cache | (val >> -bb.shift)
        big_endian32(addr(bb.buf[bb.cursor]), addr(bb.cache))
        bb.cursor += 4
        bb.shift += 32
        bb.cache = uint32(0)
        assert bb.buf[7] == uint8(7)


    def test_variant(self):
        class HittableVariantKind(NIntEnum):
            kSphere = auto()
            kMovingSphere = auto()

        class Vec3(Object):
            x: float64
            y: float64
            z: float64

        class Sphere(Object):
            center: Vec3
            radius: float64

        class MovingSphere(Object):
            center0: Vec3
            center1: Vec3
            time0: float64
            time1: float64
            radius: float64

        class HittableVariant(Object):
            kind: HittableVariantKind
            match kind:
                case HittableVariantKind.kSphere:
                    fSphere: Sphere
                case HittableVariantKind.kMovingSphere:
                    fMovingSphere: MovingSphere

        class HittableList(Object):
            len: nint
            objects: ptr[UncheckedArray[HittableVariant]]

        class Scene(Object):
            objects: seq[HittableVariant]

            def add(self: mut @ Scene, h: HittableVariant):
                self.objects.add(h)  

            def list(scene: Scene) -> HittableList:
                assert len(scene.objects) > 0
                result = HittableList()
                result.len = len(scene.objects)
                result.objects = cast[ptr[UncheckedArray[HittableVariant]]](
                    unsafe_addr(scene.objects[0])
                )
                return result

        class _ReturnScenes(NTuple):
            point: Vec3
            scene: Scene

        # Nim has no implicit payload -> variant conversion: construct the variant explicitly
        result = Scene()
        result.add(HittableVariant(kind=HittableVariantKind.kSphere,
                                   fSphere=Sphere(center=Vec3(x=0, y=-1000, z=0), radius=1000.0)))
        result.add(HittableVariant(kind=HittableVariantKind.kMovingSphere,
                                   fMovingSphere=MovingSphere(center0=Vec3(x=0, y=0, z=0), center1=Vec3(x=0, y=0, z=0),
                                                              time0=0.0, time1=1.0, radius=1.0)))
        world_list = result.list()
        self.assertEqual(world_list.len, 2)
        self.assertEqual(world_list.objects[0].kind, HittableVariantKind.kSphere)
        self.assertEqual(world_list.objects[1].kind, HittableVariantKind.kMovingSphere)

        result = _ReturnScenes()
        result.scene.add(HittableVariant(kind=HittableVariantKind.kSphere,
                                         fSphere=Sphere(center=Vec3(x=0, y=-1000, z=0), radius=1000.0)))
        self.assertEqual(float(result.scene.objects[0].fSphere.radius), 1000.0)
        self.assertEqual(result.scene.objects[0].kind, HittableVariantKind.kSphere)

    def test_keyword_dispatch(self):
        class DispatcherKw(Object):
            id: int32

            def compute(self, a: int32, b: int32) -> int32:
                return a - b

            def compute(self, y: float64, x: float64) -> float64:
                return x / y

        d = DispatcherKw()

        # 1. basic out-of-order named args
        res_i = d.compute(b=int32(3), a=int32(10))
        self.assertIsInstance(res_i, int32)
        self.assertEqual(int(res_i), 7)

        # 2. Positional and named arguments
        res_i2 = d.compute(int32(10), b=int32(3))
        self.assertEqual(int(res_i2), 7)

        # 3. Floating point with different arg names
        res_f = d.compute(x=float64(10.0), y=float64(2.0))
        self.assertIsInstance(res_f, float64)
        self.assertAlmostEqual(float(res_f), 5.0)

        # 4. Bad kwarg names
        with self.assertRaises((TypeError, NotImplementedError)):
            d.compute(badkw=int32(1))

    def test_buffer_registry_register_find(self):
        """Register a buffer and find it by interior address."""
        reg = BufferRegistry()
        buf = (ctypes.c_char * 256)()
        addr = reg.register(buf)
        self.assertIn(addr, reg)
        self.assertEqual(len(reg), 1)
        # Interior address lookup
        self.assertIs(reg.find_buffer_for_address(addr), buf)
        self.assertIs(reg.find_buffer_for_address(addr + 128), buf)
        self.assertIs(reg.find_buffer_for_address(addr + 255), buf)
        # Out of bounds
        self.assertIsNone(reg.find_buffer_for_address(addr + 256))
        self.assertIsNone(reg.find_buffer_for_address(addr - 1))

    def test_buffer_registry_update(self):
        """Resize a buffer and verify the registry re-keys correctly."""
        reg = BufferRegistry()
        buf = (ctypes.c_char * 64)()
        old_addr = reg.register(buf)
        # Simulate resize (same object, bigger size)
        ctypes.resize(buf, 128)
        new_addr = reg.update(old_addr, buf)
        self.assertEqual(len(reg), 1)
        self.assertIs(reg.find_buffer_for_address(new_addr), buf)
        # Interior of new size should be reachable
        self.assertIs(reg.find_buffer_for_address(new_addr + 100), buf)

    def test_buffer_registry_free(self):
        """Free a buffer and verify it's no longer found."""
        reg = BufferRegistry()
        buf = (ctypes.c_char * 64)()
        addr = reg.register(buf)
        self.assertTrue(reg.free(buf))
        self.assertEqual(len(reg), 0)
        self.assertIsNone(reg.find_buffer_for_address(addr))
        # Double-free is safe
        self.assertFalse(reg.free(buf))

    def test_buffer_registry_object_init(self):
        """After Phase 2: creating an Object should register its buffer."""
        initial = len(BUFFER_REGISTRY)
        class Point(Object):
            x: int32
            y: int32
        p = Point()
        # The buffer should be in the global registry
        self.assertGreaterEqual(len(BUFFER_REGISTRY), initial + 1)

    def test_buffer_registry_seq_resize(self):
        """After Phase 2: seq resize should update the registry."""
        s = seq[int32]()
        initial = len(BUFFER_REGISTRY)
        for i in range(10):
            s.add(int32(i))
        # Registry should still track the buffer (possibly updated)
        self.assertGreaterEqual(len(BUFFER_REGISTRY), initial)

    def test_ptr_decorator(self):
        @ptr
        class Nested(Object):
            y: int32
            nested: ptr[Nested]

        # with var:
        #     p = Nested(y=int32(1), nested=Nested(y=int32(2), nested=Nested(y=int32(3), nested=Nested(y=int32(4), nested=Nested()))))
        #     ptr_ptr = cast[ptr[Nested]](cast[ptr[ptr[Nested]]](addr(p)))

        @ptr
        class Frame(Object):
            Y: ptr[UncheckedArray[uint8]]
            Cb: ptr[UncheckedArray[uint8]]
            Cr: ptr[UncheckedArray[uint8]]
            lumaWidth: int32
            lumaHeight: int32
            size: int32
            buffer: UncheckedArray[uint8]

        class H264Encoder(Object):
            sps: seq[byte]
            needCropping: bool
            frame: Frame

        # # Verify Frame is treated as a pointer type
        # from nimic.ntypesystem import pointer, DICT_OF_C_TYPES
        # import ctypes
        # self.assertTrue(issubclass(Frame, pointer))
        # self.assertTrue(getattr(Frame, '_n_is_ptr', False))
        # self.assertIs(DICT_OF_C_TYPES["Frame"], ctypes.c_void_p)
        # self.assertEqual(Frame._n_contents_type.__name__, "_n_bare_Frame")
        
        # # Verify _n_bare_Frame has proper ctypes structure backing
        # bare_frame_c_type = DICT_OF_C_TYPES["_n_bare_Frame"]
        # self.assertTrue(issubclass(bare_frame_c_type, ctypes.Structure))
        # self.assertEqual(bare_frame_c_type.__name__, "c__n_bare_Frame")
        # # Ensure it has the correct fields (e.g. lumaWidth is int32/c_int)
        # field_names = [name for name, _ in bare_frame_c_type._fields_]
        # self.assertIn("lumaWidth", field_names)
        # self.assertIn("buffer", field_names)

        with var:
            width = 1920
            height = 1080
            size = width * height
            frame = cast[Frame](
                alloc_shared0(
                    3 * sizeof(pointer) +
                    3 * sizeof(int32) +
                    size
                )
            )
            #zero_mem(frame, 3 * sizeof(pointer) + 3 * sizeof(int32) + size)

        frame.size = int32(size)
        frame.lumaWidth = int32(width)
        frame.lumaHeight = int32(height)
        frame.Y = cast[ptr[UncheckedArray[uint8]]](addr(frame.buffer))
        frame.Cb = frame.Y
        frame.Cr = frame.Y
        frame.Y[0] = uint8(1)
        assert frame.Y[0] == uint8(1)
        assert frame.Cb[0] == uint8(1)
        assert frame.Cr[0] == uint8(1)

        with var:
            encoder = H264Encoder()
            encoder.frame = frame
            assert encoder.needCropping == False
            assert encoder.frame.Y[0] == uint8(1)

    def test_ptr_ptr(self):
        

        def _fourCC(a: char, b: char, c: char, d: char) -> uint32:
            """{.inline.}"""
            return (uint32(ord(a)) << 24) | (uint32(ord(b)) << 16) | (uint32(ord(c)) << 8) | uint32(ord(d))

        with var:
            _stackBase = array[20, ptr[uint8]]()
            _stack = cast[ptr[ptr[uint8]]](addr(_stackBase[0]))
        with let:
            _indexBytes = 1024
            _base = cast[ptr[uint8]](c_malloc(csize_t(_indexBytes)))
        with var:
            p = _base.copy()  # copy pointer as mutable
        with let:
            _BOX_trak = _fourCC(ch('t'),ch('r'),ch('a'),ch('k'))
            x = _BOX_trak
        cast[ptr[ptr[uint8]]](_stack).contents = p  # save pointer p to _stackBase
        _stack <<= cast[ptr[ptr[uint8]]](cast[intp](_stack) + sizeof(pointer))  # update _stack pointer
        p <<= cast[ptr[uint8]](cast[intp](p) + 4)
        p.contents = uint8((x >> 24) & 0xFF)
        p <<= cast[ptr[uint8]](cast[intp](p) + 1)
        p.contents = uint8((x >> 16) & 0xFF)
        p <<= cast[ptr[uint8]](cast[intp](p) + 1)
        p.contents = uint8((x >> 8) & 0xFF)
        p <<= cast[ptr[uint8]](cast[intp](p) + 1)
        p.contents = uint8(x & 0xFF)
        p <<= cast[ptr[uint8]](cast[intp](p) + 1)
        _stack <<= cast[ptr[ptr[uint8]]](cast[intp](_stack) - sizeof(pointer))  # restore _stack pointer
        
        with let:
            _atomStart = cast[ptr[ptr[uint8]]](_stack).contents

        with let:
            _xu = uint32(cast[intp](p) - cast[intp](_atomStart))
            _arr = cast[ptr[UncheckedArray[uint8]]](p)
            _arr[0] = uint8((_xu >> 24) & 0xFF)
            _arr[1] = uint8((_xu >> 16) & 0xFF)
            _arr[2] = uint8((_xu >> 8) & 0xFF)
            _arr[3] = uint8(_xu & 0xFF)
        assert _arr[3] == uint8(8)  # pointer offset
        with let:
            _arr = cast[ptr[UncheckedArray[uint8]]](_atomStart)
        assert _arr[4] == uint8(ord(ch('t')))  

        c_free(_base)


    def test_array_dict_initialization(self):
        class TMsgKind(NIntEnum):
            errUnknown = 0
            errFatal = 1
            errInternal = 2

        arr = array[TMsgKind, string]({
            TMsgKind.errUnknown: string("unknown error"),
            TMsgKind.errFatal: string("fatal error: $1")
        })

        self.assertEqual(str(arr[TMsgKind.errUnknown]), "unknown error")
        self.assertEqual(str(arr[TMsgKind.errFatal]), "fatal error: $1")
        self.assertEqual(str(arr[TMsgKind.errInternal]), "")



    def test_trange_and_tset(self):
        class TMsgKind(NIntEnum):
            errUnknown = 0
            errFatal = 1
            errInternal = 2

        class TNoteKind(Trange[TMsgKind.errUnknown, TMsgKind.errFatal]): pass
        class TNoteKinds(Tset[TNoteKind]): pass

        # Test Trange low and high
        self.assertEqual(low(TNoteKind), TMsgKind.errUnknown)
        self.assertEqual(high(TNoteKind), TMsgKind.errFatal)

        # Test Tset
        s1 = TNoteKinds({TMsgKind.errUnknown, TMsgKind.errFatal})
        s2 = TNoteKinds({TMsgKind.errFatal, TMsgKind.errInternal})
        s3 = s1 - s2
        
        self.assertIsInstance(s3, TNoteKinds)
        self.assertEqual(s3, {TMsgKind.errUnknown})

    def test_string_distinct_view(self):
        """string(x) on a distinct/alias string subclass shares the _n_view buffer."""

        @distinct
        class AbsFile(string): pass

        # Create a distinct string instance
        af = AbsFile("hello")
        self.assertEqual(str(af), "hello")

        # string(af) should share the same _n_view buffer
        sv = string(af)
        self.assertEqual(str(sv), "hello")
        self.assertIs(sv._n_view, af._n_view)

        # Mutating the shared buffer through sv should be visible via af
        sv._n_view[0] = b'H'
        self.assertEqual(af._n_view[0], b'H')
        self.assertEqual(sv._n_view[0], b'H')
        self.assertEqual(ctypes.addressof(sv._n_view), ctypes.addressof(af._n_view))

        # string(plain_bytes) should create an independent copy
        s1 = string("world")
        s2 = string(s1)
        self.assertIs(s2._n_view, s1._n_view)  # same string instance → same view
        s2._n_view[0] = b'W'
        self.assertEqual(s1._n_view[0], b'W')  # shared

        # string(b"bytes") should create a fresh buffer (no sharing)
        s3 = string(b"bytes")
        s4 = string(b"bytes")
        self.assertIsNot(s3._n_view, s4._n_view)  # independent buffers


    # ------------------------------------------------------------------ #
    #  Tests added by nimic-core-review 2026-10-01                       #
    # ------------------------------------------------------------------ #

    # --- high() / low() on integer types ---

    def test_high_low_signed_integers(self):
        """high()/low() on signed integer types dispatches via NInteger._n_low_bound()/_n_high_bound()."""
        self.assertEqual(int(low(int8)), -128)
        self.assertEqual(int(high(int8)), 127)
        self.assertEqual(int(low(int16)), -32768)
        self.assertEqual(int(high(int16)), 32767)
        self.assertEqual(int(low(int32)), -2147483648)
        self.assertEqual(int(high(int32)), 2147483647)
        self.assertEqual(int(low(int64)), -9223372036854775808)
        self.assertEqual(int(high(int64)), 9223372036854775807)

    def test_high_low_unsigned_integers(self):
        """high()/low() on unsigned integer types."""
        self.assertEqual(int(low(uint8)), 0)
        self.assertEqual(int(high(uint8)), 255)
        self.assertEqual(int(low(uint16)), 0)
        self.assertEqual(int(high(uint16)), 65535)
        self.assertEqual(int(low(uint32)), 0)
        self.assertEqual(int(high(uint32)), 4294967295)
        self.assertEqual(int(low(uint64)), 0)
        self.assertEqual(int(high(uint64)), 18446744073709551615)

    def test_high_low_enum(self):
        """high()/low() on NIntEnum returns first/last member."""
        class Color(NIntEnum):
            red = 0
            green = auto()
            blue = auto()

        self.assertEqual(low(Color), Color.red)
        self.assertEqual(high(Color), Color.blue)

    def test_high_low_on_seq(self):
        """high()/low() on a seq instance returns 0 and len-1."""
        s = seq[int32]()
        s.add(10)
        s.add(20)
        s.add(30)
        self.assertEqual(low(s), 0)
        self.assertEqual(high(s), 2)

    def test_high_low_on_array(self):
        """high()/low() on an array type returns first/last index."""
        ArrType = array[5, int32]
        self.assertEqual(low(ArrType), 0)
        self.assertEqual(high(ArrType), 4)

    # --- NStrEnum comparison operators ---

    def test_nstrenum_comparisons(self):
        """NStrEnum supports ordinal-based <, <=, >, >= comparisons."""
        class Severity(NStrEnum):
            low = "low"
            medium = "medium"
            high = "high"

        self.assertTrue(Severity.low < Severity.medium)
        self.assertTrue(Severity.medium < Severity.high)
        self.assertFalse(Severity.high < Severity.low)
        self.assertTrue(Severity.low <= Severity.low)
        self.assertTrue(Severity.low <= Severity.medium)
        self.assertTrue(Severity.high > Severity.medium)
        self.assertTrue(Severity.high >= Severity.high)
        self.assertFalse(Severity.low > Severity.medium)

    def test_nstrenum_int_index(self):
        """NStrEnum supports __int__ and __index__ via ord()."""
        class Direction(NStrEnum):
            north = "north"
            south = "south"
            east = "east"
            west = "west"

        self.assertEqual(int(Direction.north), 0)
        self.assertEqual(int(Direction.south), 1)
        self.assertEqual(int(Direction.east), 2)
        self.assertEqual(int(Direction.west), 3)
        # __index__ allows use as list index
        data = ['N', 'S', 'E', 'W']
        self.assertEqual(data[Direction.east], 'E')

    # --- Non-zero-based arrays (array with Trange index) ---

    def test_array_nonzero_based(self):
        """array indexed by Trange has non-zero first index."""
        R = Trange[3, 7]
        ArrType = array[R, int32]

        self.assertEqual(low(ArrType), 3)
        self.assertEqual(high(ArrType), 7)

        a = ArrType()
        # Set/get with non-zero indices
        a[3] = 100
        a[5] = 200
        a[7] = 300
        self.assertEqual(int(a[3]), 100)
        self.assertEqual(int(a[5]), 200)
        self.assertEqual(int(a[7]), 300)

    def test_array_nonzero_based_high_low(self):
        """high()/low() on Trange-indexed array returns correct bounds."""
        R = Trange[1, 5]
        ArrType = array[R, int32]
        self.assertEqual(low(ArrType), 1)
        self.assertEqual(high(ArrType), 5)

    # --- string mutability: setLen, __iadd__, __ilshift__ ---

    def test_string_setlen(self):
        """string.setLen() truncates correctly and extends the backing buffer."""
        s = string("hello")
        s.setLen(3)
        self.assertEqual(str(s), "hel")
        # Extending pads with null bytes in the backing buffer
        s.setLen(5)
        raw = bytes(s._n_view_ref[0])
        self.assertEqual(len(raw), 5)
        self.assertEqual(raw[:3], b'hel')

    def test_string_iadd(self):
        """string += appends in place."""
        s = string("hello")
        s += string(" world")
        self.assertEqual(str(s), "hello world")

    def test_string_ilshift(self):
        """string <<= replaces content (Nim shallow assignment)."""
        s = string("hello")
        s <<= string("goodbye")
        self.assertEqual(str(s), "goodbye")

    def test_string_data_setter(self):
        """string.data setter actually updates the backing buffer."""
        s = string("original")
        s.data = "replaced"
        self.assertEqual(str(s), "replaced")

    def test_string_getitem_returns_char(self):
        """Indexing a string always returns a char."""
        s = string("abc")
        c = s[0]
        self.assertIsInstance(c, _char)
        self.assertEqual(str(c), "a")

    def test_string_endswith_startswith(self):
        """string.endswith / startswith accept string and tuple."""
        s = string("hello.nim")
        self.assertTrue(s.endswith(string(".nim")))
        self.assertTrue(s.endswith(".nim"))
        self.assertTrue(s.endswith((".nim", ".py")))
        self.assertFalse(s.endswith(".py"))
        self.assertTrue(s.startswith(string("hello")))
        self.assertTrue(s.startswith("hello"))
        self.assertTrue(s.startswith(("hello", "world")))

    # --- Tset reverse operators ---

    def test_tset_reverse_operators(self):
        """Tset supports reverse operators (+, *, -) and preserves type."""
        class TKind(NIntEnum):
            a = 0
            b = auto()
            c = auto()

        S = Tset[TKind]
        s1 = S({TKind.a, TKind.b})
        s2 = S({TKind.b, TKind.c})

        # Union via +
        s3 = s1 + s2
        self.assertIsInstance(s3, S)
        self.assertEqual(s3, {TKind.a, TKind.b, TKind.c})

        # Intersection via *
        s4 = s1 * s2
        self.assertIsInstance(s4, S)
        self.assertEqual(s4, {TKind.b})

        # Difference
        s5 = s1 - s2
        self.assertIsInstance(s5, S)
        self.assertEqual(s5, {TKind.a})

        # XOR (symmetric difference)
        s6 = s1 ^ s2
        self.assertIsInstance(s6, S)
        self.assertEqual(s6, {TKind.a, TKind.c})

    def test_tset_contains_and_copy(self):
        """Tset.contains() and copy() work correctly."""
        class TKind2(NIntEnum):
            x = 0
            y = auto()

        S = Tset[TKind2]
        s = S({TKind2.x})
        self.assertTrue(s.contains(TKind2.x))
        self.assertFalse(s.contains(TKind2.y))

        s2 = s.copy()
        self.assertEqual(s, s2)
        self.assertIsNot(s, s2)
        self.assertIsInstance(s2, S)

    # --- Object with callable fields ---

    def test_object_callable_field(self):
        """Object with a function-typed field initializes to None."""

        @calltype
        def my_callback(x: int32) -> int32: ...

        class Handler(Object):
            on_event: my_callback
            name: string

        h = Handler()
        self.assertIsNone(h.on_event)
        self.assertEqual(str(h.name), "")

    # --- Dispatch subtype matching ---

    def test_dispatch_subtype_int_variants(self):
        """@dispatch with alias resolution: nint resolves to int64."""
        @dispatch
        def process_nint(x: int64) -> string:
            return string("int64")

        # int64 exact match
        self.assertEqual(str(process_nint(int64(5))), "int64")

        # nint is aliased to int64 — should match via alias resolution
        result = process_nint(nint(5))
        self.assertEqual(str(result), "int64")

    def test_dispatch_no_ambiguity_with_exact_match(self):
        """When an exact match exists, it takes priority over subtype match."""
        @dispatch
        def classify(x: int32) -> string:
            return string("i32")

        @dispatch
        def classify(x: int64) -> string:
            return string("i64")

        self.assertEqual(str(classify(int32(1))), "i32")
        self.assertEqual(str(classify(int64(1))), "i64")

    def test_forward_declared_field_types(self):
        """A field whose type is declared later in the same type section (Nim: one `type` block)
        resolves to that type once it is defined: a ref field defaults to nil, a value field to
        its zero value, and the field accepts instances of the real type."""
        @ref
        class FwdNode(Object):
            sym: FwdSym
            info: FwdInfo
            n: nint

        @ref
        class FwdSym(Object):
            node: FwdNode

        class FwdInfo(Object):
            line: nint

        x = FwdNode(n=1)
        self.assertIsNone(x.sym)
        self.assertIsInstance(x.info, FwdInfo)
        self.assertEqual(x.info.line, 0)
        x.sym = FwdSym(node=x)
        self.assertIs(x.sym.node, x)
        self.assertIs(FwdNode._n_field_types["sym"], FwdSym)

    def test_dispatch_none_matches_nilable_types(self):
        """None (Nim nil) dispatches only to nilable parameter types: ref, ptr, pointer, proc."""
        @ref
        class _TNilRef(Object):
            x: nint

        class _TNilValue(Object):
            x: nint

        @calltype
        def _t_nil_cb(x: int32) -> int32: ...

        for nilable in (_TNilRef, ptr[int32], pointer, _t_nil_cb):
            self.assertTrue(_match_subtype("NoneType", nilable.__name__), nilable.__name__)
        for value in (_TNilValue, int32, nint, float64, bool, char, string, Tset[uint8], array[3, int8]):
            self.assertFalse(_match_subtype("NoneType", value.__name__), value.__name__)

        @dispatch
        def _t_nil_take(a: _TNilRef, b: nint) -> string:
            return string("ref")

        self.assertEqual(str(_t_nil_take(None, nint(1))), "ref")

    # --- char from bytes ---

    def test_char_from_bytes(self):
        """char() accepts bytes and bytearray."""
        c1 = _char(b'A')
        self.assertEqual(str(c1), 'A')
        self.assertEqual(int(c1), 65)

        c2 = _char(bytearray(b'Z'))
        self.assertEqual(str(c2), 'Z')
        self.assertEqual(int(c2), 90)

    def test_char_sizeof(self):
        """char._n_sizeof() returns 1."""
        self.assertEqual(_char._n_sizeof(), 1)

    # --- Trange inherits from Trange ---

    def test_trange_issubclass(self):
        """Dynamic Trange subclasses are actual subclasses of Trange."""
        R = Trange[0, 10]
        self.assertTrue(issubclass(R, Trange))

    # --- nsystem: Endianness, hostOS, hostCPU, substr, ord, quit ---

    def test_endianness_enum(self):
        """Endianness enum has expected members."""
        self.assertEqual(int(Endianness.littleEndian), 0)
        self.assertEqual(int(Endianness.bigEndian), 1)

    def test_host_os_cpu(self):
        """hostOS and hostCPU return non-empty strings."""
        self.assertIsInstance(hostOS, string)
        self.assertIsInstance(hostCPU, string)
        self.assertGreater(len(str(hostOS)), 0)
        self.assertGreater(len(str(hostCPU)), 0)

    def test_substr(self):
        """substr() implements Nim's inclusive slicing."""
        s = string("hello world")
        self.assertEqual(str(substr(s, 0, 4)), "hello")
        self.assertEqual(str(substr(s, 6)), "world")
        self.assertEqual(str(substr(s, 0, 0)), "h")

    def test_ord_function(self):
        """ord() works on enum, char, int, bool."""

        # char
        self.assertEqual(nim_ord(_char('A')), 65)
        # int passthrough
        self.assertEqual(nim_ord(42), 42)
        # bool
        self.assertEqual(nim_ord(True), 1)
        self.assertEqual(nim_ord(False), 0)
        # NIntEnum
        class TestEnum(NIntEnum):
            a = 0
            b = auto()
        self.assertEqual(nim_ord(TestEnum.a), 0)
        self.assertEqual(nim_ord(TestEnum.b), 1)

    # --- ntypes: writeFile / readFile ---

    def test_write_read_file(self):
        """writeFile / readFile round-trip."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            path = f.name
        try:
            writeFile(path, "nimic test content")
            content = readFile(path)
            self.assertEqual(str(content), "nimic test content")
        finally:
            os.unlink(path)

    # --- ntypes: setLen ---

    def test_setLen_string(self):
        """setLen on string truncates or pads."""
        s = string("hello")
        setLen(s, 3)
        self.assertEqual(str(s), "hel")

    def test_setLen_list(self):
        """setLen on a plain list extends or truncates."""
        lst = [1, 2, 3]
        setLen(lst, 5)
        self.assertEqual(len(lst), 5)
        setLen(lst, 2)
        self.assertEqual(lst, [1, 2])

    # --- File context manager ---

    def test_file_context_manager(self):
        """File supports with-statement (context manager)."""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.bin', delete=False) as f:
            path = f.name

        try:
            handle = open(path, 'rb')
            f = File(handle)
            with f:
                pass  # just verify no exception
        finally:
            os.unlink(path)

    # --- string.string property ---

    def test_string_string_property(self):
        """string.string returns self (Nim compat)."""
        s = string("test")
        self.assertIs(s.string, s)

    # --- raiseAssert ---

    def test_raise_assert(self):
        """raiseAssert raises AssertionError."""
        with self.assertRaises(AssertionError):
            raiseAssert("test message")


    def test_untyped_parameter_takes_distinct_argument(self):
        """An `untyped` template parameter takes every argument, a @distinct one too (bitabs' `isFilled`
        called with a `TagId`); a typed parameter still rejects it."""
        @distinct
        class _DId(uint32):
            pass

        @template
        def is_filled(x: untyped) -> bool:
            return uint32(x) != u32(0)

        @dispatch
        def typed_only(x: uint32) -> bool:
            return True

        self.assertTrue(is_filled(_DId(u32(3))))
        self.assertFalse(is_filled(_DId(u32(0))))
        self.assertTrue(is_filled(u32(1)))
        self.assertTrue(_match_subtype("_DId", "untyped"))
        with self.assertRaises(NotImplementedError):
            typed_only(_DId(u32(3)))

    def test_suffix_call_takes_literal_only(self):
        """u32(5) / u32(-1) are the literals 5'u32 / -1'u32; u32(x) of a non-literal is rejected (a conversion
        is written uint32(x)), instead of transpiling to the invalid x'u32."""
        out = unparse(ast.parse("from nimic.ntypes import *\n"
                                "def f(i: nint) -> uint32:\n"
                                "    return u32(5) + u32(-1) + uint32(i) + f32(2.5).u32\n"))[0]
        self.assertIn("5'u32 + -1'u32 + uint32(i)", out)
        self.assertIn("2.5'f32", out)
        for expr in ("u32(i)", "u32(p >> u64(1))", "f64(x.y)"):
            with self.assertRaises(SyntaxError) as cm:
                unparse(ast.parse(f"from nimic.ntypes import *\ndef f(i, p, x):\n    return {expr}\n"))
            self.assertIn("conversion", str(cm.exception))
        self.assertIn("float64(...)", str(cm.exception))  # the last one, f64(x.y)

    def test_export_of_operator(self):
        """`with export:` names another module's operator by its dunder: lineinfos.__eq__ is
        lineinfos.`==` (Nim's `export lineinfos.`==``); other attributes keep their names."""
        out = unparse(ast.parse("from nimic.ntypes import *\nfrom . import lineinfos\n"
                                "with export:\n    lineinfos.FileId, lineinfos.__eq__, lineinfos.__str__, lineinfos.hash\n"
                                "def f(a, b) -> bool:\n    return a.__eq__(b)\n"))[0]
        self.assertIn("lineinfos.FileId, lineinfos.`==`, lineinfos.`$`, lineinfos.hash", out)
        self.assertNotIn("a.`==`", out)  # outside `with export:` an attribute keeps its name

    def test_operator_decorator(self):
        """@operator("+!") gives a letter-named proc its Nim operator: Python calls it by name, the transpiler
        writes the definition as `+!` and its calls as the operator, with Nim's precedence (first character)
        and parentheses where needed; a one-argument call is the prefix form; a private proc stays unexported;
        procs of other modules are found through the registry."""
        @operator("+!")
        def plus_bang_t(a: nint, b: nint) -> nint:
            return a + b

        self.assertEqual(plus_bang_t(nint(1), nint(2)), 3)
        self.assertEqual(_n_registry.operators["plus_bang_t"], "+!")
        with self.assertRaises(ValueError):
            operator("plus")
        src = ("from nimic.ntypes import *\n"
               "@operator('+!')\ndef plus_bang(c: nint, diff: nint) -> nint:\n    return c + diff\n"
               "@operator('!&')\ndef _mix(h: nint, v: nint) -> nint:\n    return h\n"
               "@operator('$$')\ndef dd(h: nint) -> nint:\n    return h\n"
               "def g(a: nint) -> nint:\n"
               "    x = plus_bang(a, 1) * 2\n"
               "    y = a.plus_bang(plus_bang(1, 2))\n"
               "    z = _mix(a, 1) == 3\n"
               "    w = dd(a + 1)\n"
               "    f = plus_bang\n"
               "    return plus_bang(x + 1, y)\n")
        out = unparse(ast.parse(src))[0]
        self.assertIn("proc `+!`*(c: int, diff: int): int =", out)
        self.assertIn("proc `!&`(h: int, v: int): int =", out)
        self.assertIn("x = (a +! 1) * 2", out)
        self.assertIn("y = a +! (1 +! 2)", out)
        self.assertIn("z = (a !& 1) == 3", out)
        self.assertIn("w = $$(a + 1)", out)
        self.assertIn("f = `+!`", out)
        self.assertIn("return x + 1 +! y", out)
        # a call of another module's operator proc: found through the registry passed to unparse
        out = unparse(ast.parse("from nimic.ntypes import *\ndef h(a: nint) -> nint:\n    return plus_bang_t(a, 2)\n"),
                      _n_registry)[0]
        self.assertIn("return a +! 2", out)

    def test_ast_to_str(self):
        """astToStr(x) is the source text of x; of a template parameter, the text of the call's argument
        (positional, keyword or method-call form), also in an inline-expanded template. Python spells the
        expression in Python (a diagnostic, as in nimony); the transpiler keeps Nim's astToStr."""
        n = nint(5)
        self.assertEqual(astToStr(n + 2), "n + 2")
        self.assertIsInstance(astToStr(n), string)
        self.assertEqual(_tAstText(n * 3, n - 1), "n * 3 / n - 1")
        self.assertEqual(_tAstText(expected=len("ab"), x=n), "n / len('ab')")
        self.assertEqual(_tUsesAstText(nint(1)), "n * (2 + 1)")
        self.assertEqual(_tUsesSetAstText(nint(1)), "n + 1")
        self.assertIn("result = string('n + 1')", _tUsesSetAstText._n_source)
        out = unparse(ast.parse("from nimic.ntypes import *\n@template\ndef t(a: untyped) -> string:\n"
                                "    return astToStr(a)\n"))[0]
        self.assertIn("astToStr(a)", out)

    def test_dollar_of_distinct_scalar(self):
        """A `$` (__str__ returning a nimic string) defined on a scalar subclass works with str() and
        echo, as on Object and enums."""
        @distinct
        class _DTag(uint32):
            def __str__(self) -> string:
                return string("tag") + string(str(uint32(self)))

        self.assertEqual(str(_DTag(u32(3))), "tag3")
        self.assertEqual(f"{_DTag(u32(4))}", "tag4")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            echo(_DTag(u32(5)))
        self.assertEqual(buf.getvalue(), "tag5\n")
        self.assertEqual(str(u32(7)), "7")  # builtin scalars keep their `$`

    def test_seq_pop(self):
        """Nim's pop removes the last element and returns it; IndexDefect on an empty seq."""
        s = seq[nint]([1, 2, 3])
        x = s.pop()
        self.assertEqual(x, 3)
        self.assertEqual(len(s), 2)
        s.add(9)  # the popped value is not a view into the reused slot
        self.assertEqual(x, 3)
        self.assertEqual(s.pop(), 9)
        names = seq[string]([string("a"), string("b")])
        self.assertEqual(names.pop(), "b")
        self.assertEqual(len(names), 1)
        empty = seq[nint]([])
        with self.assertRaises(IndexDefect):
            empty.pop()
        out = unparse(ast.parse("from nimic.ntypes import *\n"
                                "def f(s: mut @ seq[nint]) -> nint:\n"
                                "    return s.pop()\n"))[0]
        self.assertIn("s.pop()", out)

    # ------------------------------------------------------------------ #
    #  Tests for unified type relationships (alias / distinct / inherit)  #
    # ------------------------------------------------------------------ #

    def test_distinct_not_matched_by_subtype(self):
        """@distinct type is NOT matched via subtype dispatch."""
        class TDollar(Object):
            value: int32

        @distinct
        class TEuro(TDollar):
            """{.borrow: `.`}"""

        @dispatch
        def pay_dollars(d: TDollar) -> string:
            return string("paid")

        # TDollar exact match works
        self.assertEqual(str(pay_dollars(TDollar(value=10))), "paid")

        # TEuro should NOT match TDollar via subtype
        with self.assertRaises(NotImplementedError):
            pay_dollars(TEuro(TDollar(value=10)))

    def test_distinct_matched_by_converter(self):
        """@distinct type IS matched when @converter exists."""
        class TVec2(Object):
            x: float64
            y: float64

        @distinct
        class TPoint2(TVec2):
            """{.borrow: `.`}"""
            @converter
            def toTVec2(p: TPoint2) -> TVec2:
                return TVec2(p)

        @dispatch
        def tvec_length(v: TVec2) -> float64:
            return v.x * v.x + v.y * v.y

        # Should work via converter
        p = TPoint2(TVec2(x=3.0, y=4.0))
        self.assertAlmostEqual(float(tvec_length(p)), 25.0)

    def test_inheritance_matched_by_subtype(self):
        """Inherited type IS matched via subtype dispatch (Liskov)."""
        class TShape(Object):
            area: float64

        class TCircle(TShape):
            radius: float64

        @dispatch
        def describe_tshape(s: TShape) -> string:
            return string("shape")

        c = TCircle(radius=5.0, area=78.5)
        # Should match via inheritance
        self.assertEqual(str(describe_tshape(c)), "shape")

    def test_alias_matched_both_directions(self):
        """Type alias resolves through _n_aliases for dispatch."""
        @dispatch
        def process_i32(x: int32) -> int32:
            return x + 1

        # nint is aliased to int64 which is-a NInteger, same as int32
        # Calling with plain Python int (aliased to int32) should match exactly
        result = process_i32(int32(5))
        self.assertEqual(int(result), 6)

    def test_openarray_protocol(self):
        """openArray matches seq, array, and list via protocol."""
        self.assertTrue(_match_subtype("seq", "openArray"))
        self.assertTrue(_match_subtype("array", "openArray"))
        self.assertTrue(_match_subtype("list", "openArray"))
        self.assertFalse(_match_subtype("string", "openArray"))

    def test_distinct_in_registry(self):
        """@distinct adds the type name to _n_distinct_types."""

        @distinct
        class TDistReg(Object):
            """{.borrow: `.`}"""
            val: int32

        self.assertIn("TDistReg", _n_distinct_types)

    def test_distinct_match_subtype_returns_false(self):
        """_match_subtype returns False when arg is a distinct type."""

        @distinct
        class TDistSub(Object):
            """{.borrow: `.`}"""
            val: int32

        self.assertIn("TDistSub", _n_distinct_types)
        # Even though TDistSub is a Python subclass of Object,
        # _match_subtype should return False for distinct types
        self.assertFalse(_match_subtype("TDistSub", "_Object"))

    def test_inheritance_not_confused_with_distinct(self):
        """Non-distinct subclass still matches via _match_subtype."""

        class TAnimal(Object):
            name: string

        class TDog(TAnimal):
            breed: string

        # TDog is a genuine subclass, not distinct — should match
        self.assertTrue(_match_subtype("TDog", "TAnimal"))

    def test_rootobj_multilevel_inheritance_fields(self):
        """Object subclass inherits all fields from base classes in MRO order."""
        class TOrganism(RootObj):
            alive: bool

        class TMammal(TOrganism):
            name: string

        class TCanine(TMammal):
            breed: string

        # Field ordering: base first, derived last
        self.assertEqual(TCanine._n_fields, ["alive", "name", "breed"])

        # Construct instance and verify all fields are set
        c = TCanine(alive=True, name=string("Rover"), breed=string("Labrador"))
        self.assertTrue(c.alive)
        self.assertEqual(str(c.name), "Rover")
        self.assertEqual(str(c.breed), "Labrador")

        # Verify C struct backing preserves field order
        c_type = DICT_OF_C_TYPES.get("TCanine")
        self.assertIsNotNone(c_type)
        c_field_names = [f[0] for f in c_type._fields_]
        self.assertEqual(c_field_names, ["alive", "name", "breed"])

    def test_rootobj_dispatch_polymorphism(self):
        """Dispatch against RootObj and intermediate classes respects subtype hierarchy."""
        class TBaseEntity(RootObj):
            id: int32

        class TPerson(TBaseEntity):
            name: string

        class TEmployee(TPerson):
            salary: int32

        @dispatch
        def get_entity_id(e: RootObj) -> int32:
            return e.id

        @dispatch
        def get_person_name(p: TPerson) -> string:
            return p.name

        emp = TEmployee(id=int32(101), name=string("Alice"), salary=int32(50000))
        person = TPerson(id=int32(102), name=string("Bob"))
        entity = TBaseEntity(id=int32(103))

        # RootObj accepts TEmployee, TPerson, and TBaseEntity
        self.assertEqual(int(get_entity_id(emp)), 101)
        self.assertEqual(int(get_entity_id(person)), 102)
        self.assertEqual(int(get_entity_id(entity)), 103)

        # TPerson accepts TEmployee (derived), but NOT TBaseEntity (parent)
        self.assertEqual(str(get_person_name(emp)), "Alice")
        self.assertEqual(str(get_person_name(person)), "Bob")
        with self.assertRaises(NotImplementedError):
            get_person_name(entity)

    def test_rootobj_empty_subclass(self):
        """Empty subclass of Object is a subtype, not an alias."""
        class TVehicle(RootObj):
            wheels: int32

        class TBicycle(TVehicle):
            pass

        # TBicycle inherits fields
        b = TBicycle(wheels=int32(2))
        self.assertEqual(int(b.wheels), 2)

        # TBicycle is a subtype of TVehicle
        self.assertTrue(_match_subtype("TBicycle", "TVehicle"))
        # TVehicle is NOT a subtype of TBicycle
        self.assertFalse(_match_subtype("TVehicle", "TBicycle"))

        # Dispatch expecting TBicycle rejects TVehicle
        @dispatch
        def ring_bell(b: TBicycle) -> string:
            return string("ring")

        self.assertEqual(str(ring_bell(b)), "ring")
        with self.assertRaises(NotImplementedError):
            ring_bell(TVehicle(wheels=int32(4)))

    def test_ufcs_borrowed_method_dispatch(self):
        """Free-function dispatch calls borrowed method on distinct type via UFCS."""
        @distinct
        class TFilePath(string):
            def baseName(self) -> string:
                """{.borrow.}"""
                return string(os.path.basename(str(self)))

        @dispatch
        def baseName(p: string) -> string:
            return string(os.path.basename(str(p)))

        fp = TFilePath("/path/to/file.txt")
        # Free-function syntax baseName(fp) resolves to fp.baseName() via UFCS
        result = baseName(fp)
        self.assertEqual(str(result), "file.txt")

    # ------------------------------------------------------------------ #
    #  Tests for dispatch defaults, bare ptr, and binary readFile         #
    # ------------------------------------------------------------------ #

    def test_dispatch_unannotated_param_with_default(self):
        """@dispatch infers types for parameters that have default values without type annotations."""
        @dispatch
        def clamp_val(val: float64, min_val: float64, max_val = 100.0) -> float64:
            if val < min_val: return min_val
            if val > max_val: return max_val
            return val

        self.assertEqual(float(clamp_val(float64(50.0), float64(0.0))), 50.0)
        self.assertEqual(float(clamp_val(float64(150.0), float64(0.0))), 100.0)
        self.assertEqual(float(clamp_val(float64(150.0), float64(0.0), 200.0)), 150.0)

    def test_dispatch_ptr_protocol_matching(self):
        """@dispatch matches bare 'ptr' parameter against specialized ptr[T] argument."""
        @dispatch
        def get_ptr_addr(p: ptr, delta: int32) -> intp:
            return cast[intp](p) + delta

        buf = array[4, uint8]()
        p = addr(buf[0])
        res = get_ptr_addr(p, int32(2))
        self.assertEqual(int(res), int(cast[intp](p)) + 2)

    def test_read_file_binary_content(self):
        """read_file reads binary files (e.g. H.264 streams) without UnicodeDecodeError."""

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00\x00\x00\x01\xf8\xca\xfe\xba\xbe')
            tmp_path = f.name

        try:
            content = read_file(tmp_path)
            self.assertIsInstance(content, string)
            self.assertEqual(len(content), 9)
            self.assertEqual(ord(content[4]), 0xf8)
        finally:
            os.unlink(tmp_path)

    def test_generic_class_tuple_pattern_matching(self):
        """@dispatch matches generic function with tuple parameter containing generic type classes."""
        class MockChannel[T](Object):
            data: list
            @dispatch
            def __getitem__[T](channel: MockChannel[T], indices: tuple[SomeInteger, SomeInteger]) -> T:
                r, c = indices
                return channel.data[r + c]

        chan = MockChannel[int32]()
        chan.data = [int32(10), int32(20), int32(30)]
        val = chan[1, 1]
        self.assertEqual(int(val), 30)

    def test_ufcs_dunder_guard(self):
        """UFCS fallback does NOT trigger on dunder methods to avoid infinite recursion."""
        class MockSubscriptObj(Object):
            @dispatch
            def __getitem__(self: MockSubscriptObj, idx: int32) -> int32:
                return idx

        inst = MockSubscriptObj()
        self.assertEqual(int(inst[int32(42)]), 42)
        with self.assertRaises(NotImplementedError):
            inst[3.14]

    def test_specialize_generic_strips_decorators(self):
        """_specialize_generic strips decorators and executes cleanly through generic dispatch."""
        @dispatch
        def generic_add[T](a: T, b: T) -> T:
            return a + b

        res = generic_add(int32(10), int32(20))
        self.assertEqual(int(res), 30)

    def test_string_add_and_fspath(self):
        """string.add updates _n_len and content, and string implements os.PathLike."""
        s = newStringOfCap(80)
        s.add("hello")
        s.add(" ")
        s.add(string("world"))
        self.assertEqual(str(s), "hello world")
        self.assertEqual(len(s), 11)

        # PathLike interface
        joined = os.path.join(s, "subpath")
        self.assertEqual(joined, "hello world/subpath")

    def test_cstring_and_string_non_ascii_roundtrip(self):
        """string and cstring are Latin-1 byte views: one char per byte, lossless round-trip."""
        for text in ("é", "naïve", "\xff\x80"):
            self.assertEqual(str(string(text)), text)
            self.assertEqual(str(cstring(text)), text)
            self.assertEqual(len(string(text)), len(text))
            self.assertEqual(len(cstring(text)), len(text))
        # no UTF-8 guessing on decode: the bytes C3 83 C2 A9 stay four bytes
        self.assertEqual(string("Ã©").data, "Ã©")
        self.assertEqual(string(b"\xc3\xa9").data, "\xc3\xa9")
        self.assertEqual(cstring(b"\xc3\xa9")._n_value, b"\xc3\xa9")

    def test_cstring_of_string_is_a_view(self):
        """Nim `s.cstring` / `cstring(s)` points into the string's buffer: writes through the cstring
        change the string and the other way round; reads stop at the first NUL (strlen)."""
        s = string("abcd")
        c = cstring(s)
        c[0] = ch("x")
        self.assertEqual(s, "xbcd")
        s[1] = ch("y")
        self.assertEqual(c[1], "y")
        self.assertEqual(str(s.cstring), "xycd")
        self.assertEqual(c[4], "\0")  # past the end: the terminator
        c2 = c  # a cstring copy is the same pointer
        c2[3] = ch("\0")
        self.assertEqual(len(c), 3)
        self.assertEqual(str(c), "xyc")
        self.assertEqual(len(s), 4)  # the string keeps its length
        self.assertEqual(cstring(c)[0], "x")
        self.assertIsInstance(c[0], _char)

    def test_new_string_and_mem_through_cstring(self):
        """newString(n) is n NUL chars; copyMem/moveMem through addr(c[i]) write into the string
        (nimlexbase fills its buffer this way)."""
        s = newString(8)
        self.assertEqual(len(s), 8)
        self.assertEqual(s, "\0" * 8)
        c = s.cstring
        self.assertEqual(len(c), 0)
        src = string("hello")
        copyMem(addr(c[2]), addr(src[0]), 5)
        self.assertEqual(s, "\0\0hello\0")
        moveMem(addr(c[0]), addr(c[2]), 5)  # overlapping regions
        self.assertEqual(s, "hellolo\0")
        self.assertEqual(str(c), "hellolo")
        with self.assertRaises(IndexError):
            c[8] = ch("!")  # no slot past the buffer

        class _Lexer(Object):
            buf: cstring
            bufStorage: string

        lx = _Lexer()
        lx.bufStorage = newString(4)
        lx.buf = lx.bufStorage.cstring  # a cstring field aliases the string field too
        lx.buf[1] = ch("x")
        lx.bufStorage[0] = ch("a")
        self.assertEqual(lx.bufStorage, "ax\0\0")
        self.assertEqual(str(lx.buf), "ax")

    def test_string_rejects_chars_above_latin1(self):
        """A char > 0xFF cannot be a Nim byte; string/cstring/char raise NimicEncodingError."""
        with self.assertRaises(NimicEncodingError) as cm:
            string("€")
        self.assertIn("U+20AC", str(cm.exception))
        self.assertIn("utf8(", str(cm.exception))
        self.assertIsInstance(cm.exception, ValueError)
        with self.assertRaises(NimicEncodingError):
            cstring("€uro")
        with self.assertRaises(NimicEncodingError):
            char("€")

    def test_utf8_builds_nim_literal_bytes(self):
        """utf8("é") mirrors the Nim literal "é": the UTF-8 bytes C3 A9."""
        s = utf8("é")
        self.assertIsInstance(s, string)
        self.assertEqual(len(s), 2)
        self.assertEqual(s.data, "\xc3\xa9")
        self.assertEqual(utf8("abc"), "abc")

    def _run_nimic_snippet(self, code, **env_overrides):
        """Run `code` in a fresh interpreter after `from nimic.ntypes import *`; return raw stdout bytes."""
        env = {k: v for k, v in os.environ.items() if k != "NIMIC_NO_STDIO_RECONFIGURE"}
        env.update(env_overrides)
        proc = subprocess.run([sys.executable, "-c", "from nimic.ntypes import *\n" + code],
                              capture_output=True, env=env, check=True)
        return proc.stdout

    def test_stdio_is_byte_transparent(self):
        """print/echo of a byte view emits its raw bytes, like Nim's echo."""
        self.assertEqual(self._run_nimic_snippet("print(string(b'\\xc3\\xa9'))"), b"\xc3\xa9\n")
        self.assertEqual(self._run_nimic_snippet("echo(string('\\xe9'))"), b"\xe9\n")
        # Unicode text above 0xFF (Python-side) still reaches the terminal as UTF-8
        self.assertEqual(self._run_nimic_snippet("print('\\u20ac')"), b"\xe2\x82\xac\n")

    def test_stdio_reconfigure_opt_out(self):
        """NIMIC_NO_STDIO_RECONFIGURE=1 leaves stdout as a UTF-8 text stream."""
        out = self._run_nimic_snippet("print(string(b'\\xc3\\xa9'))",
                                      NIMIC_NO_STDIO_RECONFIGURE="1", PYTHONIOENCODING="utf-8")
        self.assertEqual(out, b"\xc3\x83\xc2\xa9\n")

    def test_files_and_paths_are_byte_transparent(self):
        """writeFile/readFile/lines/walkDir/getEnv move raw bytes; non-ASCII paths hit the same on-disk name."""
        with tempfile.TemporaryDirectory() as d:
            name = utf8(os.path.join(d, "café.txt"))
            writeFile(name, utf8("é\n"))
            on_disk = os.path.join(d, "café.txt")
            self.assertTrue(os.path.exists(on_disk))
            with builtins.open(on_disk, "rb") as f:
                self.assertEqual(f.read(), b"\xc3\xa9\n")
            self.assertEqual(readFile(name).data, "\xc3\xa9\n")
            self.assertTrue(fileExists(name))
            names = [e.path for e in walkDir(utf8(d), relative=True)]
            self.assertEqual(names, [utf8("café.txt")])
            # lines() keeps invalid UTF-8 byte-exact
            raw_path = os.path.join(d, "raw.bin")
            with builtins.open(raw_path, "wb") as f:
                f.write(b"\xff\x80\nab\r\n")
            self.assertEqual([l.data for l in lines(raw_path)], ["\xff\x80", "ab"])
        os.environ["NIMIC_TEST_ENV"] = "café"
        try:
            self.assertEqual(getEnv(string("NIMIC_TEST_ENV")), utf8("café"))
        finally:
            del os.environ["NIMIC_TEST_ENV"]
        self.assertEqual(getCurrentDir(), utf8(os.getcwd()))

    def test_text_boundary_helpers_roundtrip(self):
        """_n_from_text/_n_to_text convert Unicode text <-> byte view; arbitrary bytes survive."""
        self.assertEqual(_n_to_text(utf8("€uro")), "€uro")
        self.assertEqual(_n_from_text("€"), "\xe2\x82\xac")
        all_bytes = bytes(range(256)).decode("latin-1")
        self.assertEqual(_n_from_text(_n_to_text(all_bytes)), all_bytes)
        self.assertEqual(_n_from_text(_n_to_text(string(all_bytes))), all_bytes)

    def test_wrapping_percent_ops(self):
        """plus_percent and minus_percent on plain ints wrap in Nim `int` (64-bit) width."""
        max_i64 = 0x7FFFFFFFFFFFFFFF
        min_i64 = -0x8000000000000000
        self.assertEqual(plus_percent(max_i64, 1), min_i64)
        self.assertEqual(minus_percent(min_i64, 1), max_i64)
        self.assertEqual(plus_percent(10, 20), 30)
        self.assertEqual(minus_percent(30, 20), 10)
        self.assertIs(type(plus_percent(10, 20)), nint)

    def test_wrapping_percent_methods_on_ninteger(self):
        """NInteger.plus_percent / minus_percent wrap in the operand type's own width."""
        r = int8(127).plus_percent(1)
        self.assertIs(type(r), int8)
        self.assertEqual(int(r), -128)
        r = int8(-128).minus_percent(1)
        self.assertEqual(int(r), 127)
        r = uint8(0).minus_percent(1)
        self.assertIs(type(r), uint8)
        self.assertEqual(int(r), 255)
        r = uint32(0xFFFFFFFF).plus_percent(uint32(1))
        self.assertIs(type(r), uint32)
        self.assertEqual(int(r), 0)
        r = int16(0x7FFF).plus_percent(int16(1))
        self.assertEqual(int(r), -0x8000)
        r = uint64(0).minus_percent(1)
        self.assertEqual(int(r), 0xFFFFFFFFFFFFFFFF)

    def test_wrapping_percent_free_functions_delegate(self):
        """Free plus_percent/minus_percent delegate to NInteger; a plain int adopts the NInteger peer's type."""
        r = plus_percent(int32(0x7FFFFFFF), 1)
        self.assertIs(type(r), int32)
        self.assertEqual(int(r), -0x80000000)
        # plain int on the left adopts the type of the NInteger on the right
        r = plus_percent(1, uint32(0xFFFFFFFF))
        self.assertIs(type(r), uint32)
        self.assertEqual(int(r), 0)
        r = minus_percent(0, uint8(1))
        self.assertIs(type(r), uint8)
        self.assertEqual(int(r), 255)
        # operands are not mutated
        a = int8(127)
        plus_percent(a, 1)
        self.assertEqual(int(a), 127)

    def test_unsigned_compare_percent_ops(self):
        """Nim <%, <=%, >%, >=% compare as unsigned in the operand type's width: -1 >=% 3 for int."""
        self.assertTrue(ge_percent(nint(-1), nint(3)))
        self.assertFalse(lt_percent(nint(-1), nint(3)))
        self.assertTrue(le_percent(nint(3), 3))
        self.assertTrue(gt_percent(int8(-1), int8(127)))
        self.assertTrue(nint(5).lt_percent(nint(-5)))
        def nim(src):
            return unparse(ast.parse(src))[0].strip()
        self.assertEqual(nim("x = ge_percent(i, n)"), "x = i >=% n")
        self.assertEqual(nim("x = a.lt_percent(b + 1)"), "x = a <% b + 1")
        self.assertEqual(nim("x = not le_percent(a, b)"), "x = not (a <=% b)")
        self.assertEqual(nim("x = gt_percent(a, b)"), "x = a >% b")

    def test_transpile_percent_ops(self):
        """rule:percentops emits Nim +% / -% with additive precedence, for call and method forms."""

        def nim(src):
            return unparse(ast.parse(src))[0].strip()

        self.assertEqual(nim("x = plus_percent(a, b)"), "x = a +% b")
        self.assertEqual(nim("x = minus_percent(a, b)"), "x = a -% b")
        self.assertEqual(nim("x = a.plus_percent(b)"), "x = a +% b")
        self.assertEqual(nim("x = a.minus_percent(b)"), "x = a -% b")
        # the infix result must be parenthesized inside tighter-binding contexts
        self.assertEqual(nim("x = plus_percent(a, b) * 2"), "x = (a +% b) * 2")
        self.assertEqual(nim("x = -minus_percent(a, b)"), "x = -(a -% b)")
        # left-associative, same level as + / -
        self.assertEqual(nim("x = plus_percent(a + b, c)"), "x = a + b +% c")
        self.assertEqual(nim("x = minus_percent(a, b - c)"), "x = a -% (b - c)")
        self.assertEqual(nim("x = plus_percent(a, b) + c"), "x = a +% b + c")

    def test_dispatch_resolves_module_level_type_aliases(self):
        """`Label = string` in the function's module makes `x: Label` dispatch as `string`,
        also inside generic subscripts (`vararg[Label]` with `vararg = seq`), without core edits."""
        ns = {}
        exec(textwrap.dedent('''
            from __future__ import annotations
            from nimic.ntypes import *
            AliasLabel = string
            aliasvararg = seq

            @dispatch
            def _t_alias_describe(x: AliasLabel) -> string:
                return string("label")

            @dispatch
            def _t_alias_describe(x: nint) -> string:
                return string("int")

            @dispatch
            def _t_alias_count(xs: aliasvararg[AliasLabel]) -> nint:
                return nint(len(xs))
        '''), ns)
        self.assertEqual(ns["_t_alias_describe"](string("a")), "label")
        self.assertEqual(ns["_t_alias_describe"](nint(1)), "int")
        xs = seq[string]()
        xs.add(string("a"))
        xs.add(string("b"))
        self.assertEqual(int(ns["_t_alias_count"](xs)), 2)
        # aliases are resolved per module: nothing leaks into the core alias table
        self.assertNotIn("AliasLabel", _n_aliases)

    def test_dispatch_keeps_type_classes_and_static(self):
        """Names the type system already knows (SomeInteger, static[bool]) are not resolved to the
        Python builtins they alias (int, set): generic matching and static params keep working."""
        @dispatch
        def _t_tc_width[T](buf: T, width: SomeInteger, subsampled: static[bool]) -> nint:
            return nint(int(width) * (2 if subsampled else 1))
        self.assertEqual(int(_t_tc_width(string("x"), int32(4), True)), 8)
        self.assertEqual(int(_t_tc_width(string("x"), int64(4), False)), 4)
        self.assertEqual(int(_t_tc_width(string("x"), 4, subsampled=False)), 4)

    def test_ufcs_installs_free_proc_as_method(self):
        """@ufcs(T) gives Nim method-call syntax: x.f(a) == f(x, a); aliases too; never shadows."""
        class _UBox:
            def __init__(self, v):
                self.v = v
            def existing(self):
                return "own"

        @ufcs(_UBox, aliases=("plusOne",))
        def plus_one(b, k=1):
            return b.v + k

        self.assertEqual(plus_one(_UBox(1)), 2)  # still a free function
        self.assertEqual(_UBox(1).plus_one(), 2)
        self.assertEqual(_UBox(1).plusOne(5), 6)

        @ufcs(_UBox)
        @dispatch
        def _t_ufcs_scale(b: _UBox, k: nint) -> nint:
            return nint(b.v * int(k))

        self.assertEqual(int(_UBox(3)._t_ufcs_scale(nint(2))), 6)
        # re-registering the same name (e.g. a further @dispatch overload) is allowed
        ufcs(_UBox)(_t_ufcs_scale)
        # an attribute the class already defines is never shadowed
        with self.assertRaises(TypeError):
            @ufcs(_UBox)
            def existing(b):
                return "free"
        with self.assertRaises(TypeError):
            @ufcs(string)
            def find(s, sub):
                return -1
        # python_api=True replaces only a method inherited from a Python standard-library base (UserString)
        with self.assertRaises(TypeError):
            @ufcs(_UBox, python_api=True)
            def existing(b):
                return "free"

    def test_std_string_procs_use_ufcs(self):
        """std procs used with method syntax in converted code are available on string."""
        s = string("  ab_cd")
        self.assertTrue(string("abc").startsWith(string("ab")))
        self.assertTrue(string("abc").endsWith(string("bc")))
        self.assertEqual([x.data for x in string("a\nb").splitLines()], ["a", "b"])
        self.assertEqual(int(s.skipWhitespace(0)), 2)

    def test_strutils_nim_semantics(self):
        """strutils procs follow Nim: ASCII-only whitespace/case, char args, last = -1 means 'to the end'."""
        self.assertEqual(rfind(string("abca"), ch('a')), 3)
        self.assertEqual(rfind(string("abca"), ch('a'), 0, 2), 0)
        self.assertEqual(find(string("abca"), ch('a'), 1), 3)
        self.assertEqual(find(string("abca"), ch('b'), 0, 0), -1)
        self.assertEqual(repeat(ch('a'), 3), "aaa")
        # NBSP (\xa0) is not Nim whitespace
        self.assertEqual(strip(string("\xa0 x \t\n")), "\xa0 x")
        self.assertEqual(strip(string("  x  "), leading=False), "  x")
        self.assertEqual(strip(string("xxayx"), chars={ch('x')}), "ay")
        self.assertEqual(toLowerAscii(string("\xc0B_")), "\xc0b_")
        lc = toLowerAscii(ch('A'))
        self.assertIsInstance(lc, char)
        self.assertEqual(lc, 'a')
        self.assertEqual(nimIdentNormalize(string("Foo_Bar")), "Foobar")

    def test_parseutils_nim_semantics(self):
        """parseIdent stops at non-ASCII bytes; parseHex accepts 0x/# prefixes and underscores."""
        ident = string("")
        self.assertEqual(int(parse_ident(string("ab\xe9c"), ident)), 2)
        self.assertEqual(ident, "ab")
        n = nint(0)
        self.assertEqual(int(parse_hex(string("0x1F_a!"), n)), 6)
        self.assertEqual(int(n), 0x1FA)
        self.assertEqual(int(parse_hex(string("#ff"), n)), 3)
        self.assertEqual(int(n), 255)
        self.assertEqual(int(parse_hex(string("abcd"), n, 0, 2)), 2)
        self.assertEqual(int(n), 0xAB)
        n2 = nint(7)
        self.assertEqual(int(parse_hex(string("zz"), n2)), 0)
        self.assertEqual(int(n2), 7)  # untouched when nothing was parsed

    def test_scanf_nim_semantics(self):
        """$s skips whitespace (no capture), $w is an identifier, $. anchors the end, matching is a prefix match."""
        n, m = nint(0), nint(0)
        self.assertTrue(scanf(string("x=   5"), string("x=$s$i"), n))
        self.assertEqual(int(n), 5)
        self.assertTrue(scanf(string("12 rest"), string("$i"), n))
        self.assertFalse(scanf(string("12 rest"), string("$i$."), n))
        a, b = string(""), string("")
        self.assertTrue(scanf(string("foo_1 bar"), string("$w $w"), a, b))
        self.assertEqual((a.data, b.data), ("foo_1", "bar"))
        p = string("")
        self.assertTrue(scanf(string('/* line 3:4 "a.nim" */'), string('/* line $i:$i "$+" */'), n, m, p))
        self.assertEqual((int(n), int(m), p.data), (3, 4, "a.nim"))
        self.assertTrue(scanf(string("key: tail end"), string("key: $+"), p))
        self.assertEqual(p.data, "tail end")
        with self.assertRaises(ValueError):
            scanf(string("x"), string("$q"))

    def test_math_classify_subnormals(self):
        """classify is Nim's: FloatClass has Nim's 7 members in Nim's order, and a negative normal or
        subnormal float is fcNormal / fcSubnormal (only zero and inf have a negative class)."""
        tiny = sys.float_info.min / 2
        self.assertEqual(classify(tiny), fcSubnormal)
        self.assertEqual(classify(-tiny), fcSubnormal)
        self.assertEqual(classify(sys.float_info.min), fcNormal)
        self.assertEqual(classify(-1.5), fcNormal)
        self.assertEqual([str(c) for c in FloatClass],
                         ["fcNormal", "fcSubnormal", "fcZero", "fcNegZero", "fcNan", "fcInf", "fcNegInf"])
        self.assertEqual(ord(FloatClass.fcNegInf), 6)

    def test_dispatched_callable_keeps_function_metadata(self):
        """A @dispatch wrapper exposes __type_params__/__globals__/__code__, so it can be re-dispatched."""
        def _t_ident[T](x: T) -> T:
            return x
        d = dispatch(_t_ident)
        self.assertEqual(d.__type_params__, _t_ident.__type_params__)
        self.assertIs(d.__globals__, _t_ident.__globals__)
        self.assertIs(d.__code__, _t_ident.__code__)
        d2 = dispatch(d)  # re-dispatching a wrapper (DispDict does this) must not fail ...
        self.assertIs(d2._n_fn, _t_ident)  # ... and registers the original function, not the wrapper
        self.assertEqual(int(d2(nint(3))), 3)  # no self-dispatch recursion

    def test_dispatch_overload_of_explicitly_dispatched_method(self):
        """A class with an explicit @dispatch method plus an overload (DispDict re-dispatches) calls through."""
        class _TReDisp(Object):
            v: nint

            @dispatch
            def scale(self, k: nint) -> nint:
                return nint(int(self.v) * int(k))

            @dispatch
            def scale(self, k: float64) -> float64:
                return float64(float(self.v) * float(k))
        o = _TReDisp(v=nint(2))
        self.assertEqual(int(o.scale(nint(3))), 6)
        self.assertEqual(float(o.scale(float64(1.5))), 3.0)

    def test_default_is_nim_zero_value(self):
        """default(T) is Nim's zero value: scalars 0, ref types nil, arrays default-filled,
        enums low(T), type aliases / generic aliases via their target type, type variables nil."""
        from typing import TypeVar

        @ref
        class _TDefRef(Object):
            x: nint

        class _TDefKind(NIntEnum):
            a = 1
            b = 2
        type _TDefDict = dict[str, int]
        self.assertEqual(int(default(int32)), 0)
        self.assertIsNone(default(_TDefRef))
        self.assertEqual(len(default(array[3, int8])), 3)
        self.assertEqual(default(_TDefKind), _TDefKind.a)
        self.assertEqual(default(_TDefDict), {})
        self.assertEqual(default(dict[str, int]), {})
        self.assertEqual(default(string), "")
        self.assertIsNone(default(TypeVar("Val")))

    def test_field_defect_hierarchy(self):
        """Nim: FieldDefect is a Defect."""
        self.assertTrue(issubclass(FieldDefect, Defect))
        self.assertTrue(issubclass(Defect, Exception))

    def test_unchecked_assign_is_reentrant(self):
        """Nested `with uncheckedAssign:` keeps the flag active until the outer block exits."""
        from nimic.ntypesystem import _n_unchecked_assign_active
        self.assertFalse(_n_unchecked_assign_active())
        with uncheckedAssign:
            self.assertTrue(_n_unchecked_assign_active())
            with uncheckedAssign:
                self.assertTrue(_n_unchecked_assign_active())
            self.assertTrue(_n_unchecked_assign_active())
        self.assertFalse(_n_unchecked_assign_active())
        with self.assertRaises(ZeroDivisionError):
            with uncheckedAssign:
                1 / 0
        self.assertFalse(_n_unchecked_assign_active())

    def test_variant_discriminator_needs_no_dummy_default(self):
        """`kind: bool` + `match kind:` without a default defines the class (no NameError)."""
        class _TNoDefault(Object):
            n: nint
            isLeaf: bool
            match isLeaf:
                case True:
                    leafVal: nint
                case False:
                    pass
        self.assertTrue(getattr(_TNoDefault, "_n_body_has_case", False))

    def test_class_body_unknown_name_still_raises(self):
        """Only annotated names are filled by the unset sentinel; other free names still fail."""
        with self.assertRaises(NameError):
            class _TBadName(Object):
                x: nint
                y = _t_undefined_free_name_  # noqa: F821

    def test_class_body_method_named_like_annotation(self):
        """A method whose name is also annotated is still a normal method."""
        class _TMethodName(Object):
            size: nint

            def area(self) -> nint:
                return self.size * self.size
        self.assertEqual(int(_TMethodName(size=nint(3)).area()), 9)
        self.assertFalse(getattr(_TMethodName, "_n_body_has_case", False))

    # --- object variants (proposals/feature_object_variants.md, V5–V8) ---

    def _variant_types(self):
        """NodeObj from the proposal (python-side ref variant) and a ctypes-backed scalar variant."""
        class TNodeKind(NIntEnum):
            nkInt = 0
            nkAdd = 1
            nkSub = 2
            nkIf = 3

        @ref
        class TNodeObj(Object):
            info: nint
            kind: TNodeKind
            match kind:
                case TNodeKind.nkInt:
                    intVal: nint
                case TNodeKind.nkAdd | TNodeKind.nkSub:
                    leftOp: string
                    rightOp: string
                case TNodeKind.nkIf:
                    cond: string
                    hasElse: bool
                    match hasElse:
                        case True:
                            elsePart: string
                        case False:
                            pass
            tail: nint

        class TShapeKind(NIntEnum):
            skCircle = 1
            skRect = 2

        class TShape(Object):
            kind: TShapeKind
            match kind:
                case TShapeKind.skCircle:
                    radius: float64
                case TShapeKind.skRect:
                    w: int32
                    h: int32
            tag: int8
        return TNodeKind, TNodeObj, TShapeKind, TShape

    def test_variant_layout_registered_from_declaration(self):
        """Every field of every branch is part of the type, also for generic specializations."""
        @ref
        class TVNode[K, V](Object):
            entries: nint
            keys: array[4, K]
            isInternal: bool
            match isInternal:
                case False:
                    vals: array[4, V]
                case True:
                    links: array[4, TVNode[K, V]]

        spec = TVNode[str, int]
        self.assertEqual(list(spec._n_variant_layout.fields),
                         ["entries", "keys", "isInternal", "vals", "links"])
        self.assertEqual(spec._n_variant_layout.fields["vals"].annotation, "array[4, int]")
        self.assertEqual(spec._n_variant_layout.fields["links"].annotation, "array[4, TVNode[str, int]]")
        self.assertIs(spec._n_field_types["links"]._n_type, spec)  # self-reference resolves to itself

    def test_variant_non_exhaustive_case_raises(self):
        """Nim N8: a bool/enum case must cover all values or have `case _`."""
        with self.assertRaises(TypeError):
            class _TBadCase(Object):
                flag: bool
                match flag:
                    case True:
                        x: nint

        class _TElseCase(Object):
            flag: bool
            match flag:
                case True:
                    x: nint
                case _:
                    pass
        self.assertIsNotNone(_TElseCase._n_variant_layout)

    def test_variant_without_source_raises(self):
        """A variant defined via exec() has no source to read its declaration from."""
        src = textwrap.dedent('''
            class _TExecVariant(Object):
                flag: bool
                match flag:
                    case True:
                        x: nint
                    case False:
                        pass
        ''')
        with self.assertRaises(TypeError) as cm:
            exec(src, {"Object": Object, "nint": nint})
        self.assertIn("needs its source", str(cm.exception))

    def test_struct_field_offsets_include_padding(self):
        """NScalar fields use the real field offset (int8 then float64: b at offset 8)."""
        class _TPadded(Object):
            a: int8
            b: int64
        p = _TPadded(a=int8(1), b=int64(7))
        self.assertEqual(ctypes.sizeof(p._n_view), 16)
        q = cast[_TPadded](p)  # view-backed: fields are bound to the struct memory
        self.assertEqual(ctypes.addressof(q.b._n_view) - ctypes.addressof(q._n_view), 8)
        self.assertEqual(int(q.b), 7)
        q.b = int64(9)
        raw = bytes(p._n_view)
        self.assertEqual(raw[0], 1)
        self.assertEqual(raw[8:16], bytes(ctypes.c_int64(9)))

    def test_variant_ctypes_union_layout(self):
        """Branches share memory: sizeof = discriminator + largest branch + trailing fields."""
        _, _, TShapeKind, TShape = self._variant_types()
        c_type = DICT_OF_C_TYPES["TShape"]
        # kind: uint64 @0 | union{ {radius: double}, {w, h: int32} } @8 | tag: int8 @16
        self.assertEqual(ctypes.sizeof(c_type), 24)
        self.assertEqual([c_type.radius.offset, c_type.w.offset, c_type.h.offset, c_type.tag.offset], [8, 8, 12, 16])
        c = TShape(kind=TShapeKind.skCircle, radius=float64(1.5), tag=int8(7))
        self.assertEqual(float(c.radius), 1.5)
        self.assertEqual(int(c.tag), 7)
        r = TShape(kind=TShapeKind.skRect, w=int32(3), h=int32(4))
        self.assertEqual((int(r.w), int(r.h)), (3, 4))
        self.assertEqual(r._n_view.kind, int(TShapeKind.skRect))
        shapes = seq[TShape]()
        shapes.add(c)
        shapes.add(r)
        # all elements share the max-size stride, whatever their branch
        self.assertEqual(ctypes.addressof(shapes[1]._n_view) - ctypes.addressof(shapes[0]._n_view),
                         ctypes.sizeof(c_type))
        self.assertEqual(float(shapes[0].radius), 1.5)
        self.assertEqual(int(shapes[1].h), 4)
        with self.assertRaises(FieldDefect):
            shapes[1].radius

    def test_variant_construction_initializes_active_fields(self):
        """Nim N3: discriminator first, omitted one = zero value, only active fields exist."""
        TNodeKind, TNodeObj, TShapeKind, TShape = self._variant_types()
        n = TNodeObj(kind=TNodeKind.nkAdd, leftOp=string("a"))
        self.assertEqual(n._n_fields, ["info", "kind", "leftOp", "rightOp", "tail"])
        self.assertEqual(n.leftOp, "a")
        self.assertEqual(n.rightOp, "")
        d = TNodeObj()
        self.assertEqual(d.kind, TNodeKind.nkInt)
        self.assertEqual(int(d.intVal), 0)
        s = TShape()
        self.assertEqual(s.kind, TShapeKind.skCircle)  # low(TShapeKind), not 0
        self.assertEqual(float(s.radius), 0.0)

    def test_variant_inactive_field_access_raises(self):
        """Nim N4: reading/writing/constructing an inactive branch field raises FieldDefect."""
        TNodeKind, TNodeObj, _, TShape = self._variant_types()
        n = TNodeObj(kind=TNodeKind.nkInt, intVal=nint(3))
        with self.assertRaises(FieldDefect) as cm:
            n.leftOp
        self.assertEqual(str(cm.exception),
                         "field 'leftOp' is not accessible for type 'TNodeObj' using 'kind = nkInt'")
        with self.assertRaises(FieldDefect):
            n.leftOp = string("x")
        with self.assertRaises(FieldDefect):
            n["leftOp"]
        with self.assertRaises(FieldDefect):
            TNodeObj(kind=TNodeKind.nkInt, leftOp=string("x"))
        with self.assertRaises(AttributeError):
            n.notAField
        self.assertFalse(hasattr(n, "notAField"))

    def test_variant_discriminator_assignment(self):
        """Nim N5/N7: same branch is fine, a branch change needs uncheckedAssign."""
        TNodeKind, TNodeObj, TShapeKind, TShape = self._variant_types()
        n = TNodeObj(kind=TNodeKind.nkAdd, leftOp=string("l"))
        n.kind = TNodeKind.nkSub  # nkAdd and nkSub share a branch
        self.assertEqual(n.kind, TNodeKind.nkSub)
        self.assertEqual(n.leftOp, "l")
        with self.assertRaises(FieldDefect) as cm:
            n.kind = TNodeKind.nkInt
        self.assertEqual(str(cm.exception), "assignment to discriminant changes object branch")
        with uncheckedAssign:
            n.kind = TNodeKind.nkInt
        self.assertEqual(n.kind, TNodeKind.nkInt)
        self.assertEqual(int(n.intVal), 0)  # newly active python-side field is defaulted
        with self.assertRaises(FieldDefect):
            n.leftOp
        # ctypes-backed: the union memory is reused, not reset
        s = TShape(kind=TShapeKind.skRect, w=int32(5))
        with uncheckedAssign:
            s.kind = TShapeKind.skCircle
        self.assertEqual(s._n_view.kind, int(TShapeKind.skCircle))
        self.assertEqual(ctypes.c_int32.from_address(ctypes.addressof(s._n_view) + 8).value, 5)

    def test_variant_nested_case_activation(self):
        """A nested case's fields follow its own discriminator inside the active outer branch."""
        TNodeKind, TNodeObj, _, _ = self._variant_types()
        n = TNodeObj(kind=TNodeKind.nkIf, cond=string("c"), hasElse=True, elsePart=string("e"))
        self.assertEqual(n.elsePart, "e")
        with self.assertRaises(FieldDefect):
            n.hasElse = False
        with uncheckedAssign:
            n.hasElse = False
        with self.assertRaises(FieldDefect):
            n.elsePart
        m = TNodeObj(kind=TNodeKind.nkInt)
        with self.assertRaises(FieldDefect):
            m.hasElse  # nested discriminator of an inactive branch

    def test_variant_field_of_zeroed_struct_gets_default_discriminator(self):
        """A variant embedded in a default-constructed object: zeroed memory is not a valid
        enum value when the enum starts at 1, so the discriminator takes default(K) = low(K)."""
        _, _, TShapeKind, TShape = self._variant_types()

        class _THolder(Object):
            id: nint
            shape: TShape
        h = _THolder()
        self.assertEqual(h.shape.kind, TShapeKind.skCircle)
        self.assertEqual(h.shape._n_view.kind, int(TShapeKind.skCircle))
        self.assertEqual(float(h.shape.radius), 0.0)

    def test_variant_whole_object_assignment_and_copy(self):
        """Nim N6: replacing the whole object (`x[] = T(kind: ...)`) may change the branch."""
        TNodeKind, TNodeObj, TShapeKind, TShape = self._variant_types()
        n = TNodeObj(kind=TNodeKind.nkInt, intVal=nint(1))
        n <<= TNodeObj(kind=TNodeKind.nkAdd, leftOp=string("a"), rightOp=string("b"))
        self.assertEqual(n.kind, TNodeKind.nkAdd)
        self.assertEqual((n.leftOp, n.rightOp), ("a", "b"))
        with self.assertRaises(FieldDefect):
            n.intVal
        s = TShape(kind=TShapeKind.skCircle, radius=float64(2.0))
        s <<= TShape(kind=TShapeKind.skRect, w=int32(1), h=int32(2))
        self.assertEqual((s.kind, int(s.w), int(s.h)), (TShapeKind.skRect, 1, 2))
        for orig in (TShape(kind=TShapeKind.skCircle, radius=float64(3.0)),
                     TShape(kind=TShapeKind.skRect, w=int32(4), h=int32(5))):
            c = orig.copy()
            self.assertEqual(c.kind, orig.kind)
            self.assertEqual(c._n_fields, orig._n_fields)
            self.assertEqual(bytes(c._n_view), bytes(orig._n_view))
            self.assertIsNot(c._n_view, orig._n_view)

    def test_transpile_string_literal_bytes(self):
        """rule:latin1literal / rule:utf8literal keep Python and Nim literals byte-identical."""

        def nim(src):
            return unparse(ast.parse(src))[0].strip()

        # a bare "é" is the byte E9 in nimic -> Nim escape
        self.assertEqual(nim('x = "é"'), 'x = "\\xE9"')
        self.assertEqual(nim('x = "a\\xffb"'), 'x = "a\\xFFb"')
        self.assertEqual(nim('x = "plain"'), 'x = "plain"')
        # utf8("é") is the UTF-8 text -> raw Nim literal (Nim source is UTF-8)
        self.assertEqual(nim('x = utf8("é")'), 'x = "é"')
        self.assertEqual(nim('x = utf8("€uro")'), 'x = "€uro"')
        self.assertEqual(nim('x = utf8(s)'), 'x = utf8(s)')
        # chars above 0xFF cannot be bytes
        with self.assertRaises(SyntaxError) as cm:
            nim('x = "€"')
        self.assertIn("utf8(", str(cm.exception))
        # f-string literal parts get the same escape; expressions are untouched
        self.assertEqual(nim('x = f"é{n}"'), 'x = &"\\xE9{n}"')
        with self.assertRaises(SyntaxError):
            nim('x = f"€{n}"')

    def test_transpile_object_variant_record(self):
        """rule:matchcase: nested record cases, `case _` -> else, discriminator defaults dropped."""
        src = textwrap.dedent('''
            class NodeObj(Object):
                info: nint
                kind: NodeKind
                match kind:
                    case NodeKind.nkInt:
                        intVal: nint
                    case NodeKind.nkAdd | NodeKind.nkSub:
                        leftOp: Node
                        rightOp: Node
                    case NodeKind.nkIf:
                        cond: Node
                        hasElse: bool = False
                        match hasElse:
                            case True:
                                elsePart: Node
                            case False:
                                pass
                    case _:
                        pass
                tail: nint
        ''')
        expected = textwrap.dedent('''\
            type
              NodeObj* = object
                info*: int
                case kind*: NodeKind
                  of NodeKind.nkInt:
                    intVal*: int
                  of NodeKind.nkAdd, NodeKind.nkSub:
                    leftOp*: Node
                    rightOp*: Node
                  of NodeKind.nkIf:
                    cond*: Node
                    case hasElse*: bool
                      of true:
                        elsePart*: Node
                      of false:
                        discard
                  else:
                    discard
                tail*: int''')
        self.assertEqual(unparse(ast.parse(src))[0].strip(), expected)

    def test_value_assignment_containers(self):
        """`x <<= y` (Nim `x = y` through a var parameter) works for seq, array and Tset, in place."""
        def assign_seq(dst: seq[int32], src: seq[int32]) -> None:
            dst <<= src
        a = seq[int32]()
        a.add(int32(1))
        b = seq[int32]()
        for v in (4, 5, 6):
            b.add(int32(v))
        assign_seq(a, b)
        self.assertEqual([int(x) for x in a], [4, 5, 6])
        b[0] = int32(9)
        self.assertEqual(int(a[0]), 4)  # a copy, not an alias
        names = seq[string]()
        other = seq[string]()
        other.add(string("x"))
        names <<= other
        other[0].add(string("y"))
        self.assertEqual(str(names[0]), "x")  # value elements are copied
        arr = array[3, int32]([1, 2, 3])
        arr <<= array[3, int32]([7, 8, 9])
        self.assertEqual([int(x) for x in arr], [7, 8, 9])
        st = Tset[uint8]({uint8(1)})
        st <<= Tset[uint8]({uint8(2), uint8(3)})
        self.assertEqual(st, Tset[uint8]({uint8(2), uint8(3)}))

    def test_overflow_checks_follow_profile_and_push(self):
        """Overflow checks are off under -d:danger (overflow_checks:off from the global config) and for
        procs defined inside `with push("overflowChecks: off"):` (Nim {.push overflowChecks: off.})."""
        from nimic.nsystem import _n_build_profile
        profile = _BuildProfile(None, "")
        profile.checks["overflowchecks"] = False
        _n_set_build_profile(profile)
        try:
            self.assertEqual(int(int8(127) + 1), -128)
        finally:
            _n_set_build_profile(None)
        with push("overflowChecks: off"):
            def wrap_mul(x: int8) -> int8:
                return x * 2
        def checked_mul(x: int8) -> int8:
            return x * 2
        self.assertEqual(int(wrap_mul(int8(100))), -56)
        with self.assertRaises(OverflowDefect):
            checked_mul(int8(100))
        with push("checks: off"):
            self.assertEqual(int(int8(127) + 1), -128)  # module-level code inside the region

    def test_string_index_at_len_reads_terminator(self):
        """A Nim string is '\\0'-terminated: s[s.len] raises IndexDefect with bound checks on and reads
        '\\0' with them off (-d:danger, push boundChecks: off)."""
        s = string("ab")
        with self.assertRaises(IndexDefect):
            _ = s[2]
        with push("boundChecks: off"):
            self.assertEqual(str(s[2]), "\0")
        self.assertEqual(str(s[-1]), "b")  # Python negative indexes are left alone

    def test_string_setitem_and_mitems(self):
        """Nim `s[i] = c` writes the char in place (IndexDefect past the end); `for c in mitems(s):
        c = x` is `c <<= x` in nimic (transpiled `c = x`) and writes back into the string."""
        s = string("aBc")
        alias = s
        s[0] = ch("X")
        self.assertEqual(str(s), "XBc")
        self.assertEqual(str(alias), "XBc")
        with self.assertRaises(IndexDefect):
            s[3] = ch("z")
        for c in mitems(s):
            if isUpperAscii(c):
                c <<= char(uint8(ord(c)) ^ uint8(0b0010_0000))
        self.assertEqual(str(s), "xbc")
        self.assertEqual([str(c) for c in items(s)], ["x", "b", "c"])
        src = textwrap.dedent('''\
            for c in mitems(a):
                c <<= ch("x")
            ''')
        self.assertIn("for c in mitems(a):\n  c = 'x'", unparse(ast.parse(src))[0])

    def test_instantiation_info_and_typeof(self):
        """instantiationInfo(index, fullPaths) gives (filename, line, column) of a caller; `T =
        typeof(expr)` at module level is a type alias (rule:typealias)."""
        def here():
            return instantiationInfo(-1, fullPaths=True)
        line = sys._getframe().f_lineno + 1
        info = here()
        self.assertEqual(int(info.line), line)
        self.assertEqual(str(info.filename), os.path.abspath(__file__))
        self.assertIsInstance(info, typeof(instantiationInfo()))
        def short():
            return instantiationInfo()
        self.assertEqual(str(short().filename), os.path.basename(__file__))
        out = unparse(ast.parse("InstantiationInfo = typeof(instantiationInfo())\n"))[0]
        self.assertIn("type\n  InstantiationInfo* = typeof(instantiationInfo())", out)

    def test_strutils_percent_and_format(self):
        """strutils `%`/format/addf follow Nim: $1..$n, $# (sequential), ${n}, $name/${name} (key/value
        pairs, style-insensitive), $$; ValueError for an invalid format string."""
        from nimic.std import strutils as su
        self.assertEqual(str(string("$1-$#-${2}-$x$$") % [string("a"), string("b"), string("x"), string("y")]),
                         "a-a-b-y$")
        self.assertEqual(str(string("$1 $10") % [string(str(i)) for i in range(1, 11)]), "1 10")
        self.assertEqual(str(string("$-1") % [string("a"), string("b")]), "b")
        self.assertEqual(str(string(" [$1]") % string("User")), " [User]")  # `%` with a single string
        self.assertEqual(str(string("$build/${Loc}") % [string("build"), string("B"), string("loc"), string("L")]), "B/L")
        self.assertEqual(str(su.format(string("$1 and $2"), nint(1), string("b"))), "1 and b")
        s = string("x")
        su.addf(s, string("[$1]"), string("y"))
        self.assertEqual(str(s), "x[y]")
        with self.assertRaises(ValueError):
            _ = string("$3") % [string("a")]

    def test_strutils_format_float_and_size(self):
        """formatBiggestFloat/formatFloat (C printf semantics), trimZeros and formatSize, as Nim's
        runnableExamples."""
        from nimic.std import strutils as su
        self.assertEqual(str(su.formatFloat(123.456)), "123.4560000000000")
        self.assertEqual(str(su.formatFloat(123.456, su.ffDecimal, 4)), "123.4560")
        self.assertEqual(str(su.formatFloat(123.456, su.ffScientific, 2)), "1.23e+02")
        self.assertEqual(str(su.formatFloat(1.23456, su.ffDecimal, 3)), "1.235")
        x = string("123.456000000")
        su.trimZeros(x)
        self.assertEqual(str(x), "123.456")
        self.assertEqual(str(su.formatSize((1 << 31) + (300 << 20))), "2.293GiB")
        self.assertEqual(str(su.formatSize(int(2.234 * 1024 * 1024))), "2.234MiB")
        self.assertEqual(str(su.formatSize(4096, includeSpace=True)), "4 KiB")
        self.assertEqual(str(su.formatSize(4096, prefix=su.bpColloquial, includeSpace=True)), "4 kB")
        self.assertEqual(str(su.formatSize(4096)), "4KiB")
        self.assertEqual(str(su.formatSize(5_378_934, prefix=su.bpColloquial, decimalSep=ch(","))), "5,13MB")
        self.assertEqual(str(su.formatSize(0)), "0B")

    def test_format_overloads_merge(self):
        """strutils.format and times.format are overloads of one proc: either binding resolves both
        (Python star imports re-export, Nim imports don't)."""
        from nimic.std import strutils as su, times as tm
        for fmt in (su.format, tm.format):
            self.assertEqual(str(fmt(string("$1!"), string("a"))), "a!")
            self.assertEqual(str(fmt(tm.fromUnix(0), string("yyyy"))), "1970")
        self.assertAlmostEqual(tm.epochTime(), __import__("time").time(), delta=5)

    def test_system_stacktrace_and_memory(self):
        """stackTraceAvailable follows the build (stacktrace:off under -d:danger/release);
        getMaxMem/getTotalMem/getOccupiedMem give the process memory (Nim: its allocator's)."""
        self.assertTrue(stackTraceAvailable())
        profile = _BuildProfile(None, "")
        profile.checks["stacktrace"] = False
        _n_set_build_profile(profile)
        try:
            self.assertFalse(stackTraceAvailable())
        finally:
            _n_set_build_profile(None)
        self.assertGreater(int(getMaxMem()), 0)
        self.assertGreater(int(getTotalMem()), 0)
        self.assertGreater(int(getOccupiedMem()), 0)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            writeStackTrace()
        self.assertIn("Traceback (most recent call last)", err.getvalue())
        from nimic.std.os import getTempDir, getHomeDir
        from nimic.std.os import expandFilename
        self.assertEqual(str(expandFilename(string("."))), os.path.realpath("."))
        with self.assertRaises(OSError):  # POSIX realpath: the file must exist
            expandFilename(string("/no/such/dir/file.nim"))
        self.assertTrue(str(getTempDir()).endswith("/"))
        self.assertEqual(str(getHomeDir()), os.environ.get("HOME", "") + "/")

    def test_terminal_styled_write_line(self):
        """styledWriteLine writes ANSI codes for styles and colors (POSIX), resets after styled
        output and ends the line."""
        from nimic.std import terminal as tl
        out = io.StringIO()
        tl.styledWriteLine(out, tl.styleBright, string("loc "), tl.resetStyle, tl.fgRed, string("Error: "),
                           tl.resetStyle, string("msg"))
        self.assertEqual(out.getvalue(), "\x1b[1mloc \x1b[0m\x1b[31mError: \x1b[0mmsg\x1b[0m\n")
        plain = io.StringIO()
        tl.styledWriteLine(plain, string("a"), string("b"))
        self.assertEqual(plain.getvalue(), "ab\n")
        self.assertEqual(int(tl.fgCyan), 36)

    def test_misc_dollars_to_location(self):
        """std/private/miscdollars toLocation: file(line, col), the column only when > 0."""
        from nimic.std.private.miscdollars import toLocation
        r = string("")
        toLocation(r, string("a.nim"), nint(3), nint(5))
        self.assertEqual(str(r), "a.nim(3, 5)")
        r2 = string("")
        toLocation(r2, string("a.nim"), nint(3), nint(0))
        self.assertEqual(str(r2), "a.nim(3)")
        r3 = string("")
        toLocation(r3, string("a.nim"), nint(0), nint(4))
        self.assertEqual(str(r3), "a.nim")

    def test_import_except(self):
        """importExcept("m", "a", "%") is Nim `import m except a, `%``: the module's public names
        without the excluded ones (rule:importexcept)."""
        ns = {"importExcept": importExcept, "__name__": "probe", "__package__": ""}
        exec("importExcept('nimic.std.terminal', 'styledWriteLine', '%')", ns)
        self.assertIn("styledWrite", ns)
        self.assertNotIn("styledWriteLine", ns)
        self.assertNotIn("_write", ns)
        out = unparse(ast.parse("importExcept('..ropes', '%', 'rope')\nimportExcept('.ropes', '%')\n"
                                "importExcept('nimic.std.strutils', 'format')\n"))[0]
        self.assertIn("import ../ropes except `%`, rope", out)
        self.assertIn("import ropes except `%`", out)
        self.assertIn("import std/strutils except format", out)

    def test_pragma_block(self):
        """`with pragma("gcsafe"):` is a Nim pragma block `{.gcsafe.}:` (rule:pragmablock); the body runs
        as is in Python."""
        ran = []
        with pragma("gcsafe"):
            ran.append(1)
        self.assertEqual(ran, [1])
        out = unparse(ast.parse("with pragma('cast(gcsafe)'):\n    f()\n"))[0]
        self.assertIn("{.cast(gcsafe).}:\n  f()", out)

    def test_class_methods(self):
        """Procs of a type are methods of its class (methods rule) and are called as methods; overloads
        of a name in the class are dispatched. A `$` (`__str__`) defined in the class may return a nimic
        string, also in enums."""
        h = _NMethodHost(n=1)
        h.grow(2)
        h.grow(string("abc"))
        self.assertEqual(h.total(), 6)
        self.assertEqual(str(h), "host 6")
        self.assertNotIn("grow", globals())  # no free proc: a method is called as a method
        self.assertEqual(str(_NEnumWithDollar.first), "1st")
        self.assertEqual(f"{_NEnumWithDollar.second}", "2nd")

    def test_ufcs_overload_extends_class_method(self):
        """An operator defined in the class (it uses nothing defined later) and later `@ufcs @dispatch`
        overloads of it (they do) form one overload set."""
        class _Cents(Object):
            v: nint

            def __add__(a: _Cents, b: _Cents) -> _Cents:
                return _Cents(v=a.v + b.v)

        @ufcs(_Cents)
        @dispatch
        def __add__(a: _Cents, b: nint) -> _Cents:
            return _Cents(v=a.v + b)

        self.assertEqual((_Cents(v=1) + _Cents(v=2)).v, 3)
        self.assertEqual((_Cents(v=1) + nint(5)).v, 6)
        class _Euros(Object):
            v: nint

            def __add__(a: _Euros, b: _Euros) -> _Euros:
                return _Euros(v=a.v + b.v)

        with self.assertRaises(TypeError):
            @ufcs(_Euros)
            def __add__(a: _Euros, b: string) -> _Euros:  # not an overload set: never shadows the method
                return a

    def test_add_int_and_add_float(self):
        """system addInt (decimal of any integer) and addFloat (shortest round trip, as Nim's $)."""
        s = string("x")
        s.addInt(int64(-9223372036854775807) - 1)
        addInt(s, u64(18446744073709551615))
        s.addInt(nint(7))
        self.assertEqual(s, "x-922337203685477580818446744073709551615" + "7")
        f = string("")
        f.addFloat(45.67)
        f.add(ch(" "))
        addFloat(f, float32(0.5))
        f.add(ch(" "))
        f.addFloat(1e20)
        self.assertEqual(f, "45.67 0.5 1e+20")

    def test_method_call_syntax_private_proc(self):
        """`arg.sdata(3)` with a private proc/template (`_sdata`, Nim without `*`) is method-call syntax too."""
        class _Pair(Object):
            a: nint
            b: nint

        def _second(p: _Pair, add: nint) -> nint:
            return p.b + add

        self.assertEqual(_Pair(a=1, b=2)._second(10), 12)
        with self.assertRaises(AttributeError):
            _Pair()._n_missing_internal  # nimic internals are never procs

    def test_set_literal_with_ranges(self):
        """Nim `{'-', '0'..'9'}`: Tset[T] takes elements and inrange(...) ranges, as arguments or in a
        Python set literal; a single iterable (another set, a range) gives its members."""
        digits = inrange(ch('0'), ch('9'))
        for s in (Tset[char](ch('-'), digits), Tset[char]({ch('-'), digits})):
            self.assertIn(ch('5'), s)
            self.assertIn(ch('-'), s)
            self.assertNotIn(ch('a'), s)
            self.assertEqual(len(s), 11)
        self.assertEqual(len(Tset[char](digits)), 10)
        self.assertEqual(Tset[char](ch('x')), Tset[char]({ch('x')}))
        self.assertEqual(Tset[uint8](1, inrange(3, 5)), {1, 3, 4, 5})
        self.assertEqual(Tset[uint8](Tset[uint8](2, 4)), {2, 4})
        self.assertEqual(unparse(ast.parse("x = Tset[char](ch('-'), inrange(ch('0'), ch('9')))"))[0].strip(),
                         "x = {'-', '0' .. '9'}")

    def test_dispatch_overload_extends_imported_proc(self):
        """A @dispatch proc named like an imported (system, std) or Python builtin proc is a new overload
        of it, as in Nim: arguments no overload matches go to the imported proc."""
        class _Thing(Object):
            v: nint

        @dispatch
        def cmp(a: _Thing, b: _Thing) -> nint:
            return a.v - b.v

        @dispatch
        def abs(a: _Thing) -> _Thing:
            return _Thing(v=-a.v if a.v < 0 else a.v)

        self.assertEqual(cmp(_Thing(v=5), _Thing(v=3)), 2)
        self.assertEqual(cmp(int32(1), int32(2)), -1)  # system cmp
        self.assertEqual(abs(_Thing(v=-4)).v, 4)
        self.assertEqual(abs(int64(-7)), 7)  # Python builtin abs
        self.assertEqual(_n_fwd_proc(nint(1), nint(2)), 3)
        with self.assertRaises(NotImplementedError):
            _n_fwd_proc(string("x"), nint(2))  # the forward declaration is no imported proc

    def test_dispatch_set_survives_a_later_import_of_the_extended_proc(self):
        """`import nifpools, std/syncio`: nifpools' `writeFile(b: TokenBuf; path)` overloads syncio's plain
        `writeFile(path, content)`, and Nim reaches it whatever the import order. A later star import of the plain
        proc's module (or of a module re-exporting it) still reaches the set: the free and the method call. The
        proc's own module and a qualified call from the extending module (nifpools' `nifcore.addIdent(dest, s)` in
        its `addIdent(dest, s, info = NoLineInfo)`) reach the plain proc. An overload defined in a function doesn't
        rebind the module's names; a Python library proc is never rebound."""
        modules = {}
        python_basename = os.path.basename

        class _PxLocal(Object):
            n: nint
        sources = {
            "_n_px_std": """
                def wf(path: string, content: string) -> string:
                    return string("std ") + path
                def join(a: string, b: string) -> string:
                    return a + b
                def tag(s: string) -> string:
                    return string("std ") + s
                def tagTwice(s: string) -> string:
                    return tag(s) + tag(s)
                """,
            "_n_px_reexport": """
                from _n_px_std import *
                """,
            "_n_px_pools": """
                from _n_px_std import *
                from os.path import basename
                class Buf(Object):
                    n: nint
                @dispatch
                def wf(b: Buf, path: string) -> string:
                    return string("pools ") + path
                @dispatch
                def basename(b: Buf) -> string:
                    return string("buf")
                import _n_px_std
                @dispatch
                def tag(s: string, info: nint = 0) -> string:
                    return _n_px_std.tag(s) + string(" info")
                """,
            "_n_px_user": """
                from _n_px_pools import *
                from _n_px_std import *
                from _n_px_reexport import *
                def run(b: Buf) -> list:
                    return [wf(b, string("p")), b.wf(string("q")), wf(string("r"), string("text"))]
                """,
        }
        try:
            for module_name, body in sources.items():
                module = types.ModuleType(module_name)
                sys.modules[module_name] = module
                exec("from __future__ import annotations\nfrom nimic.ntypes import *\n" + textwrap.dedent(body),
                     module.__dict__)
                modules[module_name] = module
            std, pools, user = modules["_n_px_std"], modules["_n_px_pools"], modules["_n_px_user"]
            self.assertEqual(user.run(pools.Buf()), ["pools p", "pools q", "std r"])
            self.assertIs(std.wf, modules["_n_px_reexport"].wf)
            self.assertIs(std.wf, user.wf)
            self.assertEqual(std.wf(string("s"), string("t")), "std s")
            self.assertEqual(pools.tag(string("a")), "std a info")
            self.assertEqual(std.tagTwice(string("b")), "std bstd b")
            self.assertIs(os.path.basename, python_basename)
            self.assertEqual(pools.basename(pools.Buf()), "buf")

            @dispatch
            def join(b: _PxLocal, c: _PxLocal) -> string:  # a local overload: Nim's local scope
                return string("local")
            self.assertIsNot(std.join, join)
            self.assertEqual(std.join(string("a"), string("b")), "ab")
        finally:
            for name in sources:
                sys.modules.pop(name, None)

    def test_method_call_reaches_the_extending_set_past_another_modules_proc(self):
        """`import nifpools, nifbuilder` then `tb.addIdent(s, info)`: nifbuilder's plain `addIdent(b: var Builder)`,
        star-imported last, doesn't take a TokenBuf, so the method call reaches the binding of TokenBuf's module
        (nifcore), the extended proc. Nim sees nifpools' overloads there: the call reaches the set, not nifcore's
        plain proc. A free call of the class's module's proc, and its own qualified call, still reach the plain proc."""
        modules = {}
        sources = {
            "_n_xs_core": """
                class Buf(Object):
                    n: nint
                def mark(b: Buf, s: string) -> string:
                    return string("core ") + s
                def markCore(b: Buf) -> string:
                    return b.mark(string("own"))
                """,
            "_n_xs_pools": """
                from _n_xs_core import *
                import _n_xs_core
                @dispatch
                def mark(b: Buf, s: string, info: nint) -> string:
                    return _n_xs_core.mark(b, string("pools ")) + s
                @dispatch
                def mark(b: Buf, s: nint, info: nint) -> string:
                    return string("pools int")
                """,
            "_n_xs_builder": """
                class Bld(Object):
                    n: nint
                def mark(b: Bld, s: string) -> string:
                    return string("builder ") + s
                """,
            "_n_xs_prelude": """
                from _n_xs_pools import *
                from _n_xs_builder import *
                import _n_xs_core
                def run(b: Buf, d: Bld) -> list:
                    return [b.mark(string("a"), 1), b.mark(string("b")), d.mark(string("c")),
                            _n_xs_core.mark(b, string("d"))]
                """,
        }
        try:
            for module_name, body in sources.items():
                module = types.ModuleType(module_name)
                sys.modules[module_name] = module
                exec("from __future__ import annotations\nfrom nimic.ntypes import *\n" + textwrap.dedent(body),
                     module.__dict__)
                modules[module_name] = module
            core, prelude = modules["_n_xs_core"], modules["_n_xs_prelude"]
            self.assertEqual(prelude.run(core.Buf(), modules["_n_xs_builder"].Bld()),
                             ["core pools a", "core b", "builder c", "core d"])
            self.assertEqual(core.markCore(core.Buf()), "core own")
        finally:
            for name in sources:
                sys.modules.pop(name, None)

    def test_syncio_close_takes_only_a_file(self):
        """syncio's `close(f: File)` doesn't take an Object: a later star import that rebinds `close` to it (a
        module re-exporting nimic.ntypes) leaves `bld.close()` to the proc of the receiver's module, as in Nim."""
        module = types.ModuleType("_n_cl_builder")
        sys.modules["_n_cl_builder"] = module
        try:
            exec(textwrap.dedent("""
                from __future__ import annotations
                from nimic.ntypes import *
                class Bld(Object):
                    n: nint
                def close(b: mut @ Bld):
                    b.n = 7
                """), module.__dict__)
            scope = {}
            exec(textwrap.dedent("""
                from __future__ import annotations
                from _n_cl_builder import *
                from nimic.ntypes import *
                bld = Bld()
                bld.close()
                """), scope)
            self.assertEqual(scope["bld"].n, 7)
        finally:
            sys.modules.pop("_n_cl_builder", None)

    def test_method_call_reaches_the_receiver_types_module(self):
        """Two imported modules' plain procs of one name are overloads in Nim (nifcore's `addIdent(b: var
        TokenBuf)`, nifbuilder's `addIdent(b: var Builder)`); the later star import rebinds the name in Python.
        A method call whose receiver the caller's proc doesn't take reaches the proc of the receiver type's module
        (also through a base class); a proc that takes the receiver, or isn't annotated, is called as before."""
        modules = {}
        for module_name, cls_name in (("_n_mc_core", "Buf"), ("_n_mc_builder", "Bld")):
            module = types.ModuleType(module_name)
            exec(textwrap.dedent(f"""
                from __future__ import annotations
                from nimic.ntypes import *
                class {cls_name}(Object):
                    n: nint
                def tag(b: mut @ {cls_name}, v: nint) -> string:
                    return string("{module_name}:") + str(v)
                """), module.__dict__)
            modules[module_name] = module
        sys.modules.update(modules)
        try:
            core, builder = modules["_n_mc_core"], modules["_n_mc_builder"]
            tag = builder.tag  # `from core import *` then `from builder import *`

            class _Sub(core.Buf):
                pass

            self.assertEqual(core.Buf().tag(1), "_n_mc_core:1")
            self.assertEqual(builder.Bld().tag(2), "_n_mc_builder:2")
            self.assertEqual(_Sub().tag(3), "_n_mc_core:3")
            tag = core.tag  # the other import order
            self.assertEqual(builder.Bld().tag(4), "_n_mc_builder:4")

            # a @dispatch set of the caller's scope without an overload for the receiver (nifbuilder's addUIntLit)
            exec(textwrap.dedent("""
                @dispatch
                def mcLitProbe(b: mut @ Bld, v: nint) -> string:
                    return string("builder")
                @dispatch
                def mcLitProbe(b: mut @ Bld, v: nint, suffix: string) -> string:
                    return string("builder suffix")
                """), builder.__dict__)
            exec("def mcLitProbe(b: mut @ Buf, v: nint) -> string:\n    return string('core')", core.__dict__)
            mcLitProbe = builder.mcLitProbe
            self.assertEqual(core.Buf().mcLitProbe(1), "core")
            self.assertEqual(builder.Bld().mcLitProbe(1), "builder")

            def tag(b, v):  # not annotated: takes anything
                return string("local")
            self.assertEqual(builder.Bld().tag(5), "local")
        finally:
            for name in modules:
                sys.modules.pop(name)

    def test_method_call_skips_a_local_that_is_no_routine(self):
        """nifqueries' `findChildKind(node: Cursor; kind: NifKind)` compares `children.kind == kind`: Nim's call
        resolution skips the parameter `kind` (no routine) and reaches the proc `kind(Cursor)`. A local routine
        still shadows the module's proc."""
        module = types.ModuleType("_n_mc_shadow")
        exec(textwrap.dedent("""
            from __future__ import annotations
            from nimic.ntypes import *
            class C(Object):
                v: nint
            def kind(c: C) -> nint:
                return c.v
            def same(c: C, kind: nint) -> bool:
                return c.kind() == kind
            def local_proc(c: C) -> nint:
                def kind(c: C) -> nint:
                    return c.v + 1
                return c.kind()
            """), module.__dict__)
        sys.modules[module.__name__] = module
        try:
            self.assertTrue(module.same(module.C(v=3), 3))
            self.assertEqual(module.local_proc(module.C(v=3)), 4)
        finally:
            sys.modules.pop(module.__name__)

    def test_transpile_rejects_free_calls_of_overlapping_star_imports(self):
        """rule:methodcall: two star imports binding one name to different procs, one of them plain (nifcore's and
        nifbuilder's addIdent): a free call `addIdent(b, s)` reaches only the last import's proc in Python, so
        check_imported_module() rejects it and names the method call; `b.addIdent(s)` passes. Not reported: a
        name the module defines itself, a local shadowing the proc, a @dispatch set extending the other proc, a
        qualified call."""
        modules = {}
        for module_name, cls_name in (("_n_fc_core", "Buf"), ("_n_fc_builder", "Bld")):
            module = types.ModuleType(module_name)
            exec(textwrap.dedent(f"""
                from __future__ import annotations
                from nimic.ntypes import *
                class {cls_name}(Object):
                    n: nint
                def addThing(b: mut @ {cls_name}, v: nint):
                    pass
                def ownThing(b: mut @ {cls_name}):
                    pass
                """), module.__dict__)
            modules[module_name] = module
        exec(textwrap.dedent("""
            def lowProbe(x: nint) -> nint:
                return x
            """), modules["_n_fc_core"].__dict__)
        modules["_n_fc_builder"].__dict__["lowProbe"] = modules["_n_fc_core"].lowProbe  # re-exported: one proc
        exec("def extProbe(x: nint) -> nint:\n    return x", modules["_n_fc_core"].__dict__)
        # int128's `low`: a @dispatch set extending the plain proc it imported (calls no overload takes go to it)
        modules["_n_fc_builder"].__dict__["extProbe"] = modules["_n_fc_core"].extProbe
        exec("@dispatch\ndef extProbe(x: Bld) -> nint:\n    return nint(0)", modules["_n_fc_builder"].__dict__)
        source = textwrap.dedent("""
            from nimic.ntypes import *
            from _n_fc_core import *
            from _n_fc_builder import *
            import _n_fc_core
            def ownThing(b):
                pass
            def f(b: Buf, d: Bld):
                addThing(b, 1)
                d.addThing(2)
                ownThing(b)
                _n_fc_core.addThing(b, 3)
                lowProbe(4)
                extProbe(d)
            def g(b: Buf, addThing):
                addThing(b, 5)
            """)
        sys.modules.update(modules)
        try:
            module = types.ModuleType("_n_fc_user")
            exec(source, module.__dict__)
            tree = ast.parse(source)
            overlaps = free_call_overlaps(tree, module)
            self.assertEqual([line for line, _ in overlaps], [9])
            self.assertIn("_n_fc_builder, _n_fc_core", overlaps[0][1])
            self.assertIn("write b.addThing(...)", overlaps[0][1])
            with self.assertRaisesRegex(ValueError, "line 9: addThing"):
                check_imported_module(tree, module)
            self.assertIn("addThing(b, 1)", unparse(tree)[0])  # unparse() itself doesn't need the module
        finally:
            for name in modules:
                sys.modules.pop(name)

    def test_object_field_defaults(self):
        """Nim 2 object field defaults (`k: int = 5`): each new value gets its own copy (they used to stay on the
        class: a struct field read 0, and every instance shared one default object). Given fields, copies and
        conversions don't take them; nested struct objects, inherited and generic fields, `default(T)`, `reset` and
        a variant's branches (the class body runs only one `match` branch) do; a legacy `= None` stays nil."""
        class FdK(NIntEnum):
            a = auto()
            b = auto()

        class FdT(Object):
            k: nint = nint(5)
            s: string = string("ab")
            q: seq[nint]

        class FdH(Object):
            t: FdT
            z: nint = nint(3)

        class FdD(FdT):
            m: nint = nint(8)

        class FdG[X](Object):
            v: X
            w: nint = nint(7)

        class FdV(Object):
            name: string = string("v")
            kind: FdK = FdK.b
            match kind:
                case FdK.a:
                    x: nint = nint(11)
                case FdK.b:
                    y: nint = nint(22)

        t1, t2 = FdT(), FdT(k=nint(1))
        self.assertEqual((t1.k, t1.s, len(t1.q), t2.k, t2.s), (5, "ab", 0, 1, "ab"))
        self.assertIsNot(t1.s, t2.s)
        self.assertNotIn("k", FdT.__dict__)
        t1.k += 1
        t1.s.add("c")
        self.assertEqual((t1.k, t1.s, FdT().k, FdT().s), (6, "abc", 5, "ab"))
        self.assertEqual((t1.copy().k, FdT(t1).k), (6, 6))
        h = FdH()
        self.assertEqual((h.t.k, h.t.s, h.z, default(FdH).t.k), (5, "ab", 3, 5))
        self.assertEqual(FdH(t=FdT(k=nint(9))).t.k, 9)
        self.assertEqual((FdD().k, FdD().m), (5, 8))
        self.assertEqual(FdG[nint]().w, 7)
        reset(t1)
        self.assertEqual((t1.k, t1.s), (5, "ab"))
        v, w = FdV(), FdV(kind=FdK.a)
        self.assertEqual((v.kind, v.name, v.y, w.kind, w.x, w.name), (FdK.b, "v", 22, FdK.a, 11, "v"))
        self.assertEqual(FdV(kind=FdK.a, x=nint(1)).x, 1)

    def test_source_checks_run_at_import(self):
        """The transpiler's source checks run when a nimic module runs, as the main program or imported, in every
        NIMIC_VALUECHECK mode: Python finds what transpiling would reject. rule:localname before the module runs;
        rule:methodcall once its imports have run (before the next line, so before its main block), also for a
        module with no line after its imports. The messages give the file and line."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        header = "# /// nimic\n#\n# ///\nfrom nimic.ntypes import *\n"
        files = {
            "sc_core.py": header + "class Buf(Object):\n    n: nint\ndef addThing(b: mut @ Buf, v: nint):\n    b.n += v\n",
            "sc_builder.py": header + "class Bld(Object):\n    n: nint\ndef addThing(b: mut @ Bld, v: nint):\n    b.n -= v\n",
            "sc_free.py": header + "from sc_core import *\nfrom sc_builder import *\n"
                                   "if comptime(__name__ == '__main__'):\n    echo('ran')\n    addThing(Buf(), nint(1))\n",
            "sc_method.py": header + "from sc_core import *\nfrom sc_builder import *\n"
                                     "if comptime(__name__ == '__main__'):\n    b = Buf()\n    b.addThing(nint(1))\n"
                                     "    echo(b.n)\n",
            # nothing after its imports
            "sc_lib.py": header + "def use(b):\n    addThing(b, nint(1))\nfrom sc_core import *\nfrom sc_builder import *\n",
            "sc_private.py": header + "_x = nint(1)\nx = nint(2)\necho('ran')\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in files.items():
                with open(os.path.join(tmp, name), "w") as f:
                    f.write(text)
            env = dict(os.environ, PYTHONPATH=os.pathsep.join((os.path.join(root, "src"), root, tmp)))

            def run(args, mode="error"):
                return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=tmp,
                                      env=dict(env, NIMIC_VALUECHECK=mode))

            for mode in ("error", "off"):
                free = run([os.path.join(tmp, "sc_free.py")], mode)
                self.assertEqual((free.stdout, free.returncode != 0), ("", True), free.stderr)
                self.assertIn(f"{os.path.join(tmp, 'sc_free.py')}:9: addThing(...) is a proc of sc_builder, "
                              f"sc_core", free.stderr)
                private = run([os.path.join(tmp, "sc_private.py")], mode)
                self.assertEqual(private.stdout, "", private.stderr)
                self.assertIn(f"{os.path.join(tmp, 'sc_private.py')}:5 [module]: _x and x are both defined",
                              private.stderr)
            method = run([os.path.join(tmp, "sc_method.py")])
            self.assertEqual((method.returncode, method.stdout), (0, "1\n"), method.stderr)
            imported = run(["-c", "import nimic, sc_free"])
            self.assertIn("sc_free.py:9: addThing(...)", imported.stderr)
            lib = run(["-c", "import nimic, sc_lib; print('imported')"])  # checked once it ran
            self.assertEqual(lib.stdout, "", lib.stderr)
            self.assertIn("sc_lib.py:6: addThing(...)", lib.stderr)

    def test_dispatch_unannotated_int_default_is_nint(self):
        """An unannotated default `cap = 16` has the literal's Nim type, `int` (nifpools' `createTokenBuf(cap =
        16)`, called with `subtreeWidth(src) + 2`): an `nint` argument matches it, as a literal does."""
        @dispatch
        def _n_t_cap_default(cap=16) -> string:
            return string("int ") + str(cap)

        @dispatch
        def _n_t_cap_default(cap: string) -> string:
            return string("string")

        self.assertEqual(_n_t_cap_default(), "int 16")
        self.assertEqual(_n_t_cap_default(3), "int 3")
        self.assertEqual(_n_t_cap_default(nint(4)), "int 4")
        self.assertEqual(_n_t_cap_default(string("x")), "string")

    def test_dispatch_bound_call_keeps_body_errors(self):
        """A call bound to an overload through its defaults runs that overload; a NotImplementedError of its body
        (a nested call no overload takes) propagates. It used to be taken for "no overload" and the next binding
        ran on arguments the body had changed (nifcoreparse.parseFromBuffer: its `thisModule` already moved)."""
        calls = []

        @dispatch
        def _n_inner(x: nint) -> nint:
            return x

        @dispatch
        def _n_bound(s: string, m: string, size: nint = 100) -> nint:
            calls.append("first")
            m.setLen(0)
            return _n_inner(string("no overload"))

        @dispatch
        def _n_bound(s: string, m: string, unused: string, size: nint = 100) -> nint:
            calls.append("second")
            return nint(len(m))

        with self.assertRaisesRegex(NotImplementedError, "_n_inner"):
            _n_bound(string("a"), string("t"))
        self.assertEqual(calls, ["first"])
        with self.assertRaisesRegex(NotImplementedError, "_n_inner"):
            _n_bound(string("a"), string("t"), size=nint(4))
        self.assertEqual(calls, ["first", "first"])
        self.assertEqual(_n_bound(string("a"), string("tt"), string("u")), 2)
        with self.assertRaisesRegex(NotImplementedError, "_n_bound"):
            _n_bound(nint(1), nint(2))

    def test_seq_of_string_stores_nimic_strings(self):
        """`vals.add $v` written `vals.add(str(v))` (bitabs.getOrInclFromView) stores a nimic string in a
        seq[string], as an element assignment does; other seqs store a str as given."""
        s = seq[string]()
        s.add(str(42))
        s.add(string("x"))
        s.setLen(3)
        s[2] = "y"
        self.assertEqual([type(x) for x in s], [string, string, string])
        self.assertEqual(s[0].len, 2)

    def test_dispatch_keywords_bind_per_overload_without_shifting(self):
        """A keyword call binds to each overload by its parameter names; a binding whose types fit no
        overload is dropped, not re-filled with another overload's defaults (cbuilderdecls.addProcVar)."""
        @dispatch
        def _n_pv(cc: uint8, name: string, isStatic: bool = False, isVolatile: bool = False) -> string:
            return string("cc static=") + str(isStatic) + " volatile=" + str(isVolatile)

        @dispatch
        def _n_pv(name: string, isStatic: bool = False, isVolatile: bool = False) -> string:
            return string("plain static=") + str(isStatic) + " volatile=" + str(isVolatile)

        self.assertEqual(_n_pv(u8(1), string("x"), isVolatile=True), "cc static=False volatile=True")
        self.assertEqual(_n_pv(string("x"), isVolatile=True), "plain static=False volatile=True")
        self.assertEqual(_n_pv(u8(1), string("x"), isStatic=True), "cc static=True volatile=False")

    def test_dispatch_registered_alias_parameter(self):
        """A parameter typed with a registered alias (`BiggestInt` = int64, `byte` = uint8) matches the
        aliased type, and an integer literal converts to it (Nim `5` for a BiggestInt)."""
        @dispatch
        def _n_big(x: BiggestInt) -> string:
            return string("big")

        @dispatch
        def _n_big(x: string) -> string:
            return string("str")

        self.assertEqual(_n_big(int64(1)), "big")
        self.assertEqual(_n_big(5), "big")
        self.assertEqual(_n_big(string("x")), "str")

        @dispatch
        def _n_big2(x: BiggestInt, y: string) -> nint:
            return 2

        @dispatch
        def _n_big2(x: string, y: string) -> nint:
            return 3

        self.assertEqual(_n_big2(5, string("y")), 2)
        self.assertEqual(_n_big2(int32(5), string("y")), 2)

    def test_dispatch_literal_takes_parameter_type(self):
        """A Python number literal passed to a typed parameter has that type in the body (Nim types the
        literal by the parameter): `f(5)` with `x: BiggestInt` sees an int64, a generic `T` its binding."""
        @dispatch
        def _n_lit(x: BiggestInt, y: string) -> string:
            return string(type(x).__name__)

        @dispatch
        def _n_lit(x: string, y: string) -> string:
            return y

        self.assertEqual(_n_lit(5, string("y")), "int64")

        @dispatch
        def _n_glit[T: SomeInteger](x: T) -> nint:
            return sizeof(x)

        self.assertEqual(_n_glit(5), 4)  # the literal binds T to int32 (nimic's integer literal type)
        self.assertEqual(_n_glit(u64(5)), 8)

        @dispatch
        def _n_byte(x: byte) -> nint:
            return 1

        self.assertEqual(_n_byte(uint8(3)), 1)

    def test_when_type_parameter_is(self):
        """Nim `when T is bool` / `when T is SomeUnsignedInt` is `if comptime(issubclass(T, X))` (rule:isinstance):
        true in the specialization for T, transpiled as `T is X`."""
        @dispatch
        def _n_kind_of[T: SomeInteger | bool](arg: T) -> string:
            if comptime(issubclass(T, bool)):
                return string("bool")
            elif comptime(issubclass(T, SomeUnsignedInt)):
                return string("unsigned")
            else:
                return string("signed")

        self.assertEqual(_n_kind_of(True), "bool")
        self.assertEqual(_n_kind_of(u16(1)), "unsigned")
        self.assertEqual(_n_kind_of(int8(1)), "signed")
        out = unparse(ast.parse("if comptime(issubclass(T, SomeUnsignedInt)):\n    pass\n"))[0]
        self.assertIn("when T is SomeUnsignedInt:", out)

    def test_type_classes_and_uint(self):
        """Nim type classes work in `when x is SomeUnsignedInt` (`isinstance`) and in dispatch; `uint` is
        Nim's unsigned word (64 bits)."""
        self.assertTrue(isinstance(u64(1), SomeUnsignedInt))
        self.assertTrue(isinstance(uint(1), SomeUnsignedInt))
        self.assertFalse(isinstance(int8(1), SomeUnsignedInt))
        self.assertTrue(isinstance(int8(1), SomeSignedInt))
        self.assertTrue(isinstance(nint(1), SomeInteger))
        self.assertTrue(isinstance(5, SomeInteger))  # an integer literal
        self.assertFalse(isinstance(True, SomeInteger))
        self.assertTrue(isinstance(float32(1), SomeFloat))
        self.assertTrue(isinstance(1.5, SomeNumber) and isinstance(uint16(1), SomeNumber))
        self.assertFalse(isinstance(string("1"), SomeNumber))
        self.assertEqual(uint(high(uint64)), high(uint64))
        self.assertEqual(sizeof(uint(0)), 8)
        self.assertEqual(uint(5) - uint(2), 3)

        @dispatch
        def _n_kind(x: SomeUnsignedInt) -> string:
            return string("unsigned")

        @dispatch
        def _n_kind(x: SomeSignedInt) -> string:
            return string("signed")

        self.assertEqual(_n_kind(uint(1)), "unsigned")
        self.assertEqual(_n_kind(u8(1)), "unsigned")
        self.assertEqual(_n_kind(int32(1)), "signed")

    def test_generic_union_constraint(self):
        """`proc f[T: SomeInteger | bool](arg: T)`: a union constraint of a type parameter is a type class."""
        @dispatch
        def _n_width[T: SomeInteger | bool](arg: T) -> nint:
            return -1 if comptime(isinstance(arg, bool)) else sizeof(T)  # names as in the module (bool)

        self.assertEqual(_n_width(u64(1)), 8)
        self.assertEqual(_n_width(int16(1)), 2)
        self.assertEqual(_n_width(True), -1)
        with self.assertRaises(NotImplementedError):
            _n_width(1.5)

    def test_dispatch_typedesc(self):
        """`typedesc[T]` parameters match the type T itself (Nim `low(Int128)`); system low/high still
        serve the other types."""
        class _Wide(Object):
            v: nint

        @template
        def low(t: typedesc[_Wide]) -> nint:
            return -99

        @dispatch
        def describe(t: typedesc[_Wide]) -> string:
            return string("wide")

        @dispatch
        def describe(x: _Wide) -> string:
            return string("value")

        self.assertEqual(low(_Wide), -99)
        self.assertEqual(low(int8), -128)
        self.assertEqual(describe(_Wide), "wide")
        self.assertEqual(describe(_Wide(v=1)), "value")

    def test_mixed_operators_follow_nim_overloads(self):
        """`proc <(a: BiggestInt, b: T)` and `proc +(a: BiggestInt, b: T)` are written with the Nim
        parameter order; Python's reflected calls (`int64(3) < t`, `int64(3) + t`) reach them, and
        `t > x` is `x < t` as Nim's `>` template."""
        class _Big(Object):
            v: nint

        @ufcs(_Big)
        @dispatch
        def __lt__(a: _Big, b: _Big) -> bool:
            return a.v < b.v

        @ufcs(_Big)
        @dispatch
        def __lt__(a: BiggestInt, b: _Big) -> bool:
            return a < b.v

        @ufcs(_Big)
        @dispatch
        def __le__(a: BiggestInt, b: _Big) -> bool:
            return a <= b.v

        @ufcs(_Big)
        @dispatch
        def __add__(a: BiggestInt, b: _Big) -> _Big:
            return _Big(v=a + b.v)

        @ufcs(_Big)
        @dispatch
        def __sub__(a: BiggestInt, b: _Big) -> _Big:
            return _Big(v=a - b.v)

        @ufcs(_Big)
        def __str__(a: _Big) -> string:
            return string("big ") + str(a.v)

        t = _Big(v=10)
        self.assertEqual(str(t), "big 10")  # a `$` returning a nimic string serves Python's str()
        self.assertEqual(f"{t}", "big 10")
        self.assertTrue(int64(3) < t)
        self.assertFalse(int64(30) < t)
        self.assertTrue(t > int64(3))  # Nim: `>`(t, 3) is 3 < t
        self.assertTrue(t >= int64(10))
        self.assertTrue(_Big(v=20) > t)
        self.assertEqual((int64(3) + t).v, 13)
        self.assertEqual((int64(3) - t).v, -7)
        with self.assertRaises(TypeError):
            _ = int64(3) * t  # no `*` overload: Python's TypeError, not a wrong value
        self.assertEqual(int64(3) + 4, 7)  # plain scalars unchanged
        self.assertTrue(int64(3) < 4.5)

    def test_importc_proc(self):
        """`@importc` binds a body-less proc to the C function named by its `{.importc.}` pragma, through
        ctypes, with the annotated nimic types; the transpiler drops the decorator."""
        @importc
        def _c_abs(x: cint) -> cint:
            """{.importc: "abs", header: "<stdlib.h>".}"""
            pass

        @importc
        def ldexp(x: float64, exp: cint) -> float64:
            """{.importc, header: "<math.h>".}"""
            pass

        self.assertEqual(_c_abs(cint(-5)), 5)
        self.assertIsInstance(_c_abs(cint(-5)), cint)
        self.assertEqual(ldexp(1.5, -1), 0.75)
        self.assertIsInstance(ldexp(1.0, 3), float64)
        out = unparse(ast.parse('@importc\ndef _c_abs(x: cint) -> cint:\n'
                                '    """{.importc: "abs", header: "<stdlib.h>".}"""\n    pass\n'))[0]
        self.assertNotIn("importc\n", out.split("proc")[0])
        self.assertIn('proc c_abs(x: cint): cint {.importc: "abs", header: "<stdlib.h>".}', out)

    def test_bitops_math_and_branch_hints(self):
        """std/bitops fastLog2, std/math trunc (a float, as in Nim), likely/unlikely."""
        self.assertEqual(fastLog2(u32(1)), 0)
        self.assertEqual(fastLog2(u32(0x80000000)), 31)
        self.assertEqual(fastLog2(u64(1) << 40), 40)
        self.assertIsInstance(fastLog2(u32(8)), nint)
        self.assertEqual(trunc(-2.7), -2.0)
        self.assertIsInstance(trunc(2.7), float)
        self.assertTrue(unlikely(True))
        self.assertFalse(likely(False))

    def test_quit_overloads(self):
        """Nim quit(errorcode: int) exits with the code (any nimic integer), quit(errormsg: string)
        writes the message to stderr and exits with QuitFailure (1)."""
        for arg, code in ((int8(3), 3), (nint(0), 0), (2, 2)):
            with self.assertRaises(SystemExit) as cm:
                quit(arg)
            self.assertEqual(cm.exception.code, code)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            quit(string("bye"))
        self.assertEqual((cm.exception.code, err.getvalue()), (1, "bye\n"))

    def test_instantiation_info_skips_runtime_frames(self):
        """instantiationInfo counts the user's frames: @dispatch / @template wrappers don't shift it."""
        @dispatch
        def where() -> object:
            return instantiationInfo(-1)
        line = sys._getframe().f_lineno + 1
        info = where()
        self.assertEqual(int(info.line), line)

    def test_seq_growth_keeps_string_fields(self):
        """Growing a ctypes-backed seq of objects keeps the string fields of the elements already in it
        (their buffers stay owned while the seq refers to them)."""
        class _TGrowObj(Object):
            n: nint
            name: string

        t = seq[_TGrowObj]()
        for i in range(9):
            t.add(_TGrowObj(n=nint(i), name=string(f"s{i}")))
        self.assertEqual([str(t[i].name) for i in range(9)], [f"s{i}" for i in range(9)])
        t[0] = _TGrowObj(n=nint(0), name=string("z"))
        t.add(_TGrowObj(n=nint(9), name=string("s9")))
        self.assertEqual((str(t[0].name), str(t[9].name)), ("z", "s9"))
        a = array[2, _TGrowObj]()
        a[0] = _TGrowObj(n=nint(1), name=string("a0"))
        b = array[2, _TGrowObj]()
        b <<= a
        self.assertEqual(str(b[0].name), "a0")
        u = seq[_TGrowObj]()
        for i in range(3):
            u.add(_TGrowObj(n=nint(i), name=string("u")))
        u[0:2] = a
        self.assertEqual((str(u[0].name), int(u[0].n)), ("a0", 1))

    def test_anonymous_tuple_types(self):
        """Nim's anonymous tuple types `(char, int)` are `tuple[char, nint]`: as Object fields (each
        element defaults to its zero value), seq elements, aliases and nested; assigning or adding a
        tuple copies its value elements, as Nim does."""
        h = _TTupHolder()
        self.assertEqual(h.best, (_char(0), 0))
        self.assertEqual(h.nested[1], (0, string("")))
        self.assertEqual(len(h.nested[0]), 0)
        self.assertEqual(type(_TTupKeys()).__name__, "seq[tuple[string, string]]")
        key = (string("a"), string("kA"))
        h.keys.add(key)
        key[0].add(string("x"))
        self.assertEqual(str(h.keys[0][0]), "a")
        h2 = _TTupHolder(best=(_char("b"), nint(3)), keys=h.keys)
        self.assertEqual((str(h2.best[0]), int(h2.best[1])), ("b", 3))
        h.keys[0][1].add(string("y"))
        self.assertEqual(str(h2.keys[0][1]), "kA")
        self.assertIs(_n_registry.get_or_eval_type("tuple[seq[nint], nint]").__origin__, tuple)

    def test_transpile_anonymous_tuple_types(self):
        """rule:tupletype: `tuple[A, B]` is Nim's `(A, B)` in aliases, fields and seq elements."""
        src = textwrap.dedent('''\
            Key = tuple[string, string]
            class R(Object):
                best: tuple[char, nint]
                keys: seq[Key]
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("Key* = (string, string)", out)
        self.assertIn("best*: (char, int)", out)
        self.assertIn("keys*: seq[Key]", out)

    def test_substr_method_call(self):
        """Nim `s.substr(first, last)` (method-call syntax of system's substr), as `substr(s, ...)`."""
        s = string("__crucial\0real.nim")
        self.assertEqual(s.substr(10), string("real.nim"))
        self.assertEqual(s.substr(2, 8), substr(s, 2, 8))
        self.assertEqual(s.substr(30), string(""))

    def test_transpile_char_constructor_literal(self):
        """rule:char: `char("0")` of a one-char string constant is the char literal `'0'`, like `ch("0")`
        (for a proc with a local named `ch`); `char(x)` of anything else stays a conversion."""
        src = textwrap.dedent('''\
            def f(entry: string, n: nint) -> bool:
                with let:
                    ch = entry[0]
                return ch < char("0") or ch > char("\\0") or ch == char(n)
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("ch < '0' or ch > '\\0' or ch == char(n)", out)

    def test_os_exe_ext(self):
        """Nim os.ExeExt: "exe" on Windows, "" elsewhere; `addFileExt` adds nothing for "" (POSIX)."""
        self.assertEqual(ExeExt, string("exe") if os.name == "nt" else string(""))
        if os.name != "nt":
            self.assertEqual(addFileExt(string("nifler2"), ExeExt), string("nifler2"))

    def test_os_file_ext_procs(self):
        """Nim's searchExtPos / addFileExt / changeFileExt: the extension is the last component's, an
        empty extension adds nothing and removes one, a leading dot starts none."""
        self.assertEqual(searchExtPos(string("a/b.c.nim")), 5)
        self.assertEqual(searchExtPos(string("a.d/b")), -1)
        self.assertEqual(searchExtPos(string("a/.bashrc")), -1)
        self.assertEqual(addFileExt(string("a/b"), string("nim")), string("a/b.nim"))
        self.assertEqual(addFileExt(string("a/b"), string(".nim")), string("a/b.nim"))
        self.assertEqual(addFileExt(string("a/b.c"), string("nim")), string("a/b.c"))
        self.assertEqual(changeFileExt(string("a/b.c"), string("html")), string("a/b.html"))
        self.assertEqual(changeFileExt(string("a/b.c"), string("")), string("a/b"))
        self.assertEqual(changeFileExt(string("a.d/b"), string("x")), string("a.d/b.x"))

    def test_pragma_aliases(self):
        """`{.pragma: name, p1, p2.}` (`pragma("pragma: name, p1, p2")`) defines a pragma alias of its
        module: a routine's pragmas are its docstring's, with the module's aliases expanded (nested,
        with arguments, and to nothing); a template marked dirty through an alias is dirty."""
        def f():
            """{._tTwice, raises: [IOError, OSError], _tNothing, nifEmits: "D, Y".}"""
        self.assertEqual(_n_routine_pragmas(f), ["dirty", "inline", "raises", "nifEmits"])
        self.assertEqual(_n_routine_pragmas(_tDirtyByAlias), ["dirty"])
        self.assertEqual(_n_routine_pragmas(lambda: 0), [])
        with pragma("gcsafe"):  # a pragma block still only runs its body
            x = 1
        self.assertEqual(x, 1)

    def test_transpile_pragma_statements(self):
        """rule:pragmastmt: `pragma("p")` as a statement is the standalone pragma `{.p.}`; a routine
        whose body is only its pragma docstring has no body (`template x() {.pragma.}`, a custom pragma)."""
        src = textwrap.dedent('''\
            if comptime(defined("nimony")):
                pragma('feature: "untyped"')
            else:
                pragma("pragma: untyped")
            pragma("pragma: maybeDirty, dirty")

            @template
            def nifEmits(kind: string):
                """{.pragma.}"""

            @template
            def getOrInclImpl():
                """{.maybeDirty.}"""
                ensureIndexed(t)

            def f(x: nint) -> nint:
                """{.nifAdvance, nifEmits: "D".}"""
                return x
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn('when defined(nimony):\n  {.feature: "untyped".}\nelse:\n  {.pragma: untyped.}\n', out)
        self.assertIn("{.pragma: maybeDirty, dirty.}", out)
        self.assertIn("template nifEmits*(kind: string) {.pragma.}\n", out)
        self.assertNotIn("template nifEmits*(kind: string) {.pragma.} =", out)
        self.assertIn("template getOrInclImpl*() {.maybeDirty.} =", out)
        self.assertIn('proc f*(x: int): int {.nifAdvance, nifEmits: "D".} =', out)

    def test_static_block(self):
        """Nim `static:` is `with static:`: Python runs the body when the module runs (compile time in
        Nim), so a failing assert stops the import; `static[T]` stays a parameter type."""
        with static:
            ran = True
        self.assertTrue(ran)
        with self.assertRaises(AssertionError):
            with static:
                assert 1 + 1 == 3
        self.assertIsNotNone(static[nint])
        out = unparse(ast.parse("with static:\n    assert A + B == 32\n"))[0]
        self.assertEqual(out.strip(), "static:\n  assert A + B == 32")

    def test_var_enum_parameter(self):
        """Nim `var E` of an enum: an enum member is immutable in Python, so the caller's variable is
        `cell(member)`, which `<<=` changes; it dispatches, compares, indexes, prints and matches as its
        member, and storing it stores the member. `<<=` on a bare member raises instead of shifting."""
        class _TOs(NIntEnum):
            osNone = 0
            osLinux = auto()
            osMac = auto()

        class _TTxt(NStrEnum):
            first = "First"
            second = "Second"

        @dispatch
        def _tFind(name: string, res: mut @ _TOs) -> bool:
            for i in inrange(low(_TOs), high(_TOs)):
                if str(i) == str(name):
                    res <<= i
                    return True
            return False

        names = array[_TOs, string]([string("none"), string("linux"), string("mac")])
        with var:
            r = cell(_TOs.osNone)
            t = cell(_TTxt.first)
        self.assertTrue(_tFind(string("osMac"), r))
        self.assertEqual(r, _TOs.osMac)
        self.assertEqual(str(r), "osMac")
        self.assertEqual(str(names[r]), "mac")
        self.assertEqual(ord(r), 2)
        self.assertTrue(r > _TOs.osLinux)
        match r:
            case _TOs.osMac:
                matched = True
            case _:
                matched = False
        self.assertTrue(matched)
        s = seq[_TOs]()
        s.add(r)
        r <<= _TOs.osLinux
        self.assertIs(s[0], _TOs.osMac)
        self.assertEqual(str(names[r]), "linux")
        t <<= _TTxt.second
        self.assertEqual(str(t), "Second")
        self.assertEqual(array[_TTxt, nint]([1, 2])[t], 2)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            echo(r, "|", t)
        self.assertEqual(out.getvalue(), "osLinux|Second\n")
        with self.assertRaises(TypeError):
            v = _TOs.osNone
            v <<= _TOs.osMac
        with self.assertRaises(TypeError):
            cell(nint(3))
        out = unparse(ast.parse("with var:\n    r = cell(TSystemOS.osEmbedded)\n"))[0]
        self.assertNotIn("cell", out)
        self.assertIn("r* = TSystemOS.osEmbedded", out)

    def test_os_path_procs_method_calls(self):
        """std/os path procs are also method calls on a string, as nimony writes them
        (`name.addFileExt(ExeExt)`, `p.isAbsolute`, `p.changeFileExt("html")`); absolutePath."""
        p = string("a/b.c")
        self.assertEqual(p.addFileExt(string("x")), addFileExt(p, string("x")))
        self.assertEqual(p.changeFileExt(string("html")), string("a/b.html"))
        self.assertFalse(p.isAbsolute())
        self.assertEqual((p.splitFile().name, p.splitPath().tail, p.parentDir()), (string("b"), string("b.c"), string("a")))
        self.assertEqual(string("x").absolutePath(string("/r")), string("/r/x"))
        self.assertEqual(absolutePath(string("/y")), string("/y"))

    def test_str_enum_explicit_ordinals(self):
        """Nim `Cdecl = (ord(CdeclTagId), "cdecl")`: a member with an explicit ordinal and text, as the
        tag models write them. The ordinal may leave holes; a member without one continues from the
        previous ordinal. ord, E(ordinal), comparisons, low/high, iteration and `$` follow Nim; an enum
        with holes is no array index type, as in Nim; an Object field stores the member."""
        class _TTag(NIntEnum):
            NoTag = 0
            CdeclTag = auto()
            StdcallTag = auto()

        class _TCallConv(NStrEnum):
            NoCallConv = auto()
            Cdecl = (ord(_TTag.CdeclTag) + 4, "cdecl")
            Stdcall = (6, "stdcall")
            Later = "later"

        self.assertEqual([ord(m) for m in _TCallConv], [0, 5, 6, 7])
        self.assertEqual([str(m) for m in _TCallConv], ["NoCallConv", "cdecl", "stdcall", "later"])
        self.assertIs(_TCallConv(6), _TCallConv.Stdcall)
        with self.assertRaises(ValueError):
            _TCallConv(3)
        self.assertTrue(_TCallConv.Cdecl < _TCallConv.Later)
        self.assertEqual((low(_TCallConv), high(_TCallConv)), (_TCallConv.NoCallConv, _TCallConv.Later))
        self.assertEqual(list(inrange(_TCallConv.Cdecl, _TCallConv.Later)),
                         [_TCallConv.Cdecl, _TCallConv.Stdcall, _TCallConv.Later])
        self.assertNotEqual(_TCallConv.Cdecl, _TCallConv.Stdcall)
        with self.assertRaises(TypeError):  # Nim: ordinal type expected
            array[_TCallConv, nint]

        class _TUsesConv(Object):
            conv: _TCallConv
            n: nint

        u = _TUsesConv(conv=_TCallConv.Stdcall, n=1)
        self.assertIs(u.conv, _TCallConv.Stdcall)
        u.conv = _TCallConv.Later
        self.assertIs(u.conv, _TCallConv.Later)
        with self.assertRaises(ValueError):
            class _TBadConv(NStrEnum):
                A = (3, "a")
                B = (2, "b")
        src = textwrap.dedent('''\
            class CallConv(NStrEnum):
                NoCallConv = auto()
                Cdecl = (ord(TagEnum.CdeclTagId), "cdecl")
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn('Cdecl = (ord(TagEnum.CdeclTagId), "cdecl")', out)

    def test_int_enum_explicit_values(self):
        """An NIntEnum with explicit values: ord and nord are the values; an array indexed by an enum
        that starts above 0 spans ord(low)..ord(high), as in Nim; one with holes is no index type."""
        class _THoley(NIntEnum):
            a = 2
            b = 5
            c = auto()

        class _TFrom2(NIntEnum):
            a = 2
            b = auto()
            c = auto()

        self.assertEqual([nord(m) for m in _THoley], [2, 5, 6])
        self.assertEqual(ord(_THoley.b), 5)
        with self.assertRaises(TypeError):
            array[_THoley, nint]
        arr = array[_TFrom2, nint]()
        self.assertEqual(len(arr), 3)
        arr[_TFrom2.c] = 9
        arr[_TFrom2.a] = 1
        self.assertEqual((arr[_TFrom2.a], arr[_TFrom2.b], arr[_TFrom2.c]), (1, 0, 9))

    def test_hash_nim_values(self):
        """std/hashes `hash` gives Nim's values (the host Nim 2 std/hashes): hashWangYi1 of the ordinal
        for every integer type, char, bool and enum, of the bits for floats (-0.0 as 0.0), hashFarm for
        strings and openArray[char], and the mixed element hashes for tuples and other openArrays. The
        expected values are printed by compiled Nim (Python's own str hash is randomized per process)."""
        class _THashE(NIntEnum):
            e0 = auto()
            e1 = auto()
            e2 = auto()

        s100 = string("".join(chr(ord("a") + i % 26) for i in range(100)))
        self.assertEqual([nhash(0), nhash(nint(1)), nhash(nint(-1)), nhash(uint32(5)), nhash(high(uint64))],
                         [-5940405725068231575, 8641844181895329213, 8231874320669540605,
                          6628840058955693702, 8231874320669540605])
        self.assertEqual([nhash(char("a")), nhash(True), nhash(_THashE.e2), nhash(1.5)],
                         [661948602591176288, 8641844181895329213, 6130242188011939732, 7707678244570155511])
        self.assertEqual(nhash(-0.0), nhash(0.0))
        self.assertEqual([nhash(string("")), nhash(string("hello")), nhash(string("abcdefghijklmnopqrst")),
                          nhash(s100[0:40]), nhash(s100)],
                         [-7286425919675154353, -5436999610281751320, 7349542659848948094,
                          4224718273921451922, -3110835528467311390])
        self.assertEqual(nhash((nint(1), string("a"))), 4503073964935643945)
        self.assertEqual(nhash(toOpenArray(s100, 2, 11)), nhash(s100[2:12]))
        self.assertEqual(nhash(toOpenArray(array[3, nint]([1, 2, 3]), 0, 2)), -8042410921291333870)

        @distinct
        class _THashId(uint32):
            def hash(a: _THashId) -> Hash:
                """{.borrow.}"""
                return nhash(uint32(a))

        self.assertEqual(_THashId(5).hash(), 6628840058955693702)

    def test_to_open_array(self):
        """Nim system.toOpenArray(x, first, last): positions first..last of a seq, array, string, openArray
        or ptr UncheckedArray as an openArray view; reads and writes go to x. A range outside x is an
        IndexDefect; last = first - 1 is the empty view."""
        s = seq[nint]([10, 20, 30, 40])
        v = toOpenArray(s, 1, 2)
        self.assertEqual((len(v), v[0], v[1], list(v)), (2, 20, 30, [20, 30]))
        v[1] = 33
        self.assertEqual(s[2], 33)
        self.assertEqual(len(toOpenArray(s, 2, 1)), 0)
        with self.assertRaises(IndexDefect):
            toOpenArray(s, 2, 4)
        with self.assertRaises(IndexDefect):
            v[2]
        st = string("hello")
        self.assertEqual("".join(str(c) for c in toOpenArray(st, 1, 3)), "ell")
        self.assertEqual(type(toOpenArray(st, 0, 1)).__name__, "openArray[char]")
        p = cast[ptr[UncheckedArray[char]]](addr(st[0]))
        pv = toOpenArray(p, 0, 4)
        self.assertEqual((len(pv), str(pv[4])), (5, "o"))
        out = unparse(ast.parse("def f(s: string) -> nint:\n    return hash(toOpenArray(s, 0, s.len - 1))\n"))[0]
        self.assertIn("hash(toOpenArray(s, 0, s.len - 1))", out)

    def test_swap(self):
        """Nim system.swap(a, b: var T): both variables change in place (seqs, strings, objects, the
        scalar cells, fields). A Python literal or enum member can't be a variable: TypeError."""
        a, b = seq[nint]([1, 2]), seq[nint]([3])
        swap(a, b)
        self.assertEqual((list(a), list(b)), ([3], [1, 2]))
        x, y = string("x"), string("yy")
        swap(x, y)
        self.assertEqual((str(x), str(y)), ("yy", "x"))
        i, j = nint(1), nint(2)
        swap(i, j)
        self.assertEqual((i, j), (2, 1))

        class _TSwapHolder(Object):
            keys: seq[nint]

        h = _TSwapHolder(keys=seq[nint]([7]))
        n = seq[nint]([0, 0])
        swap(h.keys, n)
        self.assertEqual((list(h.keys), list(n)), ([0, 0], [7]))
        with self.assertRaises(TypeError):
            swap(1, 2)
        out = unparse(ast.parse("swap(t._keys, n)\n"))[0]
        self.assertIn("swap(t.keys, n)", out)

    def test_sink_lent_annotations(self):
        """Nim `v: sink T` and a `lent T` return: `sink @ T` / `lent @ T`, as `mut @ T` is `var T`.
        In Python the value is passed and returned as it is; dispatch matches T."""
        @dispatch
        def _tSinkAdd(s: mut @ seq[nint], v: sink @ nint) -> nint:
            s.add(v)
            return s.len

        @dispatch
        def _tLentAt(s: seq[nint], i: nint) -> lent @ nint:
            return s[i]

        s = seq[nint]([])
        self.assertEqual(_tSinkAdd(s, nint(4)), 1)
        self.assertEqual(_tLentAt(s, 0), 4)
        out = unparse(ast.parse(textwrap.dedent('''\
            def addOrdered(t: mut @ BiTable[Id, T], v: sink @ T) -> Id:
                return Id(0)
            def at(t: BiTable[Id, T], i: Id) -> lent @ T:
                return t.vals[i]
            ''')))[0]
        self.assertIn("(t: var BiTable[Id, T], v: sink T): Id", out)
        self.assertIn("(t: BiTable[Id, T], i: Id): lent T", out)

    def test_block_scope_not_exported(self):
        """Variables declared in a `block` (labeled or not) are local to it in Nim, also at module
        level: no export marker (`'export' is only allowed at top level`)."""
        out = unparse(ast.parse(textwrap.dedent('''\
            with block("orderedFill"):
                with var:
                    a = 1
            with block:
                with var:
                    b = 2
            with var:
                c = 3
            ''')))[0]
        self.assertIn("block orderedFill:\n  var\n    a = 1", out)
        self.assertIn("block:\n  var\n    b = 2", out)
        self.assertIn("var\n  c* = 3", out)

    def test_generic_object_proc_binding(self):
        """Generic objects with several parameters are named as in Nim (`G[uint32, string]`); a generic
        proc called with explicit types (`initG[uint32, string]()`, `@generic`) binds them in its body,
        and a @dispatch generic proc binds its type variables from such an argument, also when a type
        variable's name occurs in the class name (`T` in `BiTable`)."""
        class _TBiTable[Id, T](Object):
            _vals: seq[T]
            _keys: seq[Id]

        @generic
        def _tInitBiTable[Id, T]() -> _TBiTable[Id, T]:
            return _TBiTable[Id, T](_vals=seq[T]([]), _keys=seq[Id]([]))

        @dispatch
        def _tAdd[Id, T](t: mut @ _TBiTable[Id, T], v: T) -> Id:
            t._vals.add(v)
            return Id(t._vals.len)

        @dispatch
        def _tIsStr[Id, T](t: _TBiTable[Id, T]) -> bool:
            return issubclass(T, string)

        t = _tInitBiTable[uint32, string]()
        self.assertEqual(type(t).__name__, "_TBiTable[uint32, string]")
        self.assertIs(type(t), _TBiTable[uint32, string])
        self.assertEqual(type(t._keys).__name__, "seq[uint32]")
        r = _tAdd(t, string("a"))
        self.assertEqual((r, type(r).__name__), (1, "uint32"))
        self.assertTrue(_tIsStr(t))
        self.assertFalse(_tIsStr(_tInitBiTable[uint32, float64]()))
        with self.assertRaises(NotImplementedError):
            _tAdd(t, 1.5)

    def test_generic_dispatch_literals(self):
        """A literal argument of a generic proc takes the type its parameter has or its type variable is
        bound to, as in Nim: `hasNext(b, 0)` for `index: int`, `add(b, k, 10)` for `val: Val` with Val
        bound to int by `b`."""
        class _TLitTab[K, V](Object):
            _vals: seq[V]

        @dispatch
        def _tLitAdd[K, V](t: mut @ _TLitTab[K, V], v: V, n: nint) -> nint:
            t._vals.add(v)
            return t._vals.len + n

        t = _TLitTab[string, nint](_vals=seq[nint]([]))
        self.assertEqual(_tLitAdd(t, 10, 0), 1)
        self.assertEqual(_tLitAdd(t, nint(20), 5), 7)
        self.assertEqual(list(t._vals), [10, 20])

    def test_container_stores_values(self):
        """Nim assignment copies values: an array slot (also one without C storage: the element type an
        unbound type variable) stores a copy of a string or of a mutable scalar (an nint read from another
        array is a view of that slot), and a Python value stored in a typed array takes its element type."""
        class _TRefKeys[K](Object):
            keys: array[3, K]

        r = _TRefKeys[_TRefKeys.__type_params__[0]]()  # K unbound, as in a generic proc without @dispatch
        self.assertIsNone(r.keys._n_view)
        s = string("a")
        r.keys[0] = s
        s <<= string("b")
        self.assertEqual(str(r.keys[0]), "a")
        src = array[2, nint]()
        src[0] = nint(5)
        r.keys[1] = src[0]
        src[0] = nint(7)
        self.assertEqual(int(r.keys[1]), 5)
        a = array[2, string]()
        a[0] = "py"
        self.assertEqual((str(a[0]), type(a[0]).__name__), ("py", "string"))

    def test_distinct_generic_object(self):
        """Nim `BiTableFloat[Id] = distinct BiTable[Id, uint64]`: a generic distinct object. Its
        specializations are distinct (procs of the base don't take them), and a conversion between a
        distinct object and its base (`BiTable[Id, uint64](t)`, `D(b)`) is a view of the same value,
        as Nim's l-value conversion: changes through it change the converted variable."""
        f = _TGTabF[uint32](_TGTab[uint32, uint64](_vals=seq[uint64]([])))
        self.assertEqual(type(f).__name__, "_TGTabF[uint32]")
        self.assertEqual(type(f._vals).__name__, "seq[uint64]")
        self.assertIn("_TGTabF[uint32]", _n_distinct_types)
        self.assertEqual(_tGAdd(f, 1.5), 1)
        self.assertEqual(_tGAdd(f, -0.0), 2)
        self.assertEqual(list(f._vals), [0x3FF8000000000000, 0x8000000000000000])

        class _TBox(Object):
            v: seq[nint]

        @distinct
        class _TDBox(_TBox):
            pass

        d = _TDBox(_TBox(v=seq[nint]([1])))
        _TBox(d).v.add(2)
        self.assertEqual(list(d.v), [1, 2])

    def test_var_bool_parameter(self):
        """Nim `var bool` (G19): a Python bool can't be changed through a parameter, so the caller's
        variable is a `nbool` cell (like `nint` for `var int`) and the callee assigns it with `<<=`.
        Object fields of type bool are such cells already."""
        @dispatch
        def _tSetFlag(flag: mut @ bool, v: bool) -> None:
            flag <<= v

        class _TFlags(Object):
            known: bool

        with var:
            f = nbool(False)
        _tSetFlag(f, True)
        self.assertTrue(f)
        self.assertEqual(f, True)
        self.assertEqual(str(f), "true")
        _tSetFlag(f, False)
        self.assertFalse(f)
        o = _TFlags()
        _tSetFlag(o.known, True)
        self.assertTrue(o.known)
        g = f.copy()
        _tSetFlag(g, True)
        self.assertFalse(f)
        self.assertTrue(g)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            echo(g, " ", not g)
        self.assertEqual(out.getvalue(), "true false\n")
        self.assertIn("f* = bool(false)", unparse(ast.parse("with var:\n    f = nbool(False)\n"))[0])

    def test_seq_of_named_tuples_accepts_tuple_literals(self):
        """`s.add((a, b))` / `s[i] = (a, b)` for a seq of a named tuple type converts the literal
        positionally, as Nim does for tuple constructors."""
        class _TPair(NTuple):
            n: nint
            name: string

        s = seq[_TPair]()
        s.add((nint(1), string("a")))
        s.add((nint(2), string("b")))
        self.assertEqual((int(s[0].n), str(s[0].name)), (1, "a"))
        s[1] = (nint(3), string("c"))
        self.assertEqual((int(s[1].n), str(s[1].name)), (3, "c"))

    def test_is_nil(self):
        """Nim isNil for refs, procs and pointers: None (and a nil pointer) is nil."""
        @ref
        class _TNilRef(Object):
            n: nint
        self.assertTrue(isNil(None))
        self.assertFalse(isNil(_TNilRef()))
        self.assertFalse(isNil(lambda: 0))

    def test_str_enum_distinct_members_and_auto_names(self):
        """NStrEnum (Nim enum with string values): members with equal texts stay distinct (Nim
        `warnUser = "User", hintUser = "User"`), `$` of an auto() member is its name."""
        class _TKind(NStrEnum):
            errA = auto()
            warnUser = "User"
            hintUser = "User"
            hintB = auto()

        self.assertEqual(len(list(_TKind)), 4)
        self.assertIsNot(_TKind.hintUser, _TKind.warnUser)
        self.assertNotEqual(_TKind.hintUser, _TKind.warnUser)
        self.assertEqual((str(_TKind.hintUser), str(_TKind.errA)), ("User", "errA"))
        self.assertEqual((int(_TKind.warnUser), int(_TKind.hintUser)), (1, 2))
        self.assertIn(_TKind.hintUser, inrange(_TKind.hintUser, _TKind.hintB))
        self.assertNotIn(_TKind.hintUser, inrange(_TKind.errA, _TKind.warnUser))
        self.assertIs(_TKind("User"), _TKind.warnUser)
        self.assertIs(_TKind(nint(2)), _TKind.hintUser)  # by ordinal, any integer type
        self.assertEqual(len({_TKind.warnUser, _TKind.hintUser}), 2)
        self.assertTrue(_TKind.hintB > _TKind.hintUser)

    def test_constructor_copies_value_fields(self):
        """Object(field=v) copies a value-type v (Nim object constructors copy values); refs are shared."""
        class _TPoint(Object):
            x: nint

        @ref
        class _TNode(Object):
            x: nint

        class _THolder(Object):
            p: _TPoint
            r: _TNode
            name: string

        origin = _TPoint(x=nint(0))
        node = _TNode(x=nint(1))
        nm = string("a")
        h = _THolder(p=origin, r=node, name=nm)
        h.p = _TPoint(x=nint(5))
        h.p.x = nint(7)
        self.assertEqual(int(origin.x), 0)
        self.assertIs(h.r, node)
        h.name.add("b")
        self.assertEqual(str(nm), "a")

    def test_negative_default_and_named_argument(self):
        """rule:argdefault: `bits = -1` and `f(a = -1)` keep the spaces; `=-` would be one Nim operator."""
        src = ("from nimic.ntypes import *\n"
               "def f(sizeHint: nint, bits: nint = -1) -> nint:\n    return bits\n"
               "def g():\n    f(1, bits=-1)\n")
        out = unparse(ast.parse(src))[0]
        self.assertIn("proc f*(sizeHint: int, bits: int = -1): int =", out)
        self.assertIn("f(1, bits = -1)", out)

    def test_set_alias_constructor_is_set_literal(self):
        """A module-level alias `Flags = Tset[F]` constructs sets like Tset: `Flags()` is `{}`,
        `Flags({F.a})` is `{F.a}` (rule:typealias, rule:setlit)."""
        out = unparse(ast.parse("MsgFlags = Tset[MsgFlag]\n"
                                "def f(flags: MsgFlags = MsgFlags()) -> None:\n"
                                "    y = MsgFlags({MsgFlag.a})\n"))[0]
        self.assertIn("proc f*(flags: MsgFlags = {}) =", out)
        self.assertIn("y = {MsgFlag.a}", out)

    def test_object_equality_is_field_wise(self):
        """Nim `==` for objects and tuples compares the fields; for refs, the references. A
        user-defined `==` replaces it."""
        class _TEqPoint(Object):
            x: nint
            name: string

        @ref
        class _TEqRef(Object):
            x: nint

        self.assertEqual(_TEqPoint(x=nint(1), name=string("a")), _TEqPoint(x=nint(1), name=string("a")))
        self.assertNotEqual(_TEqPoint(x=nint(1), name=string("a")), _TEqPoint(x=nint(2), name=string("a")))
        self.assertNotEqual(_TEqRef(x=nint(1)), _TEqRef(x=nint(1)))
        r = _TEqRef(x=nint(1))
        self.assertEqual(r, r)
        self.assertEqual(len({_TEqPoint(x=nint(1)), _TEqPoint(x=nint(1))}), 2)  # identity hash

    def test_table_ref(self):
        """std/tables TableRef / newTable[K, V](): a table with reference semantics."""
        from nimic.std.tables import TableRef, newTable

        class _THolderT(Object):
            t: TableRef[string, nint]

        t = newTable[string, nint]()
        t[string("a")] = nint(1)
        h = _THolderT(t=t)
        h.t[string("b")] = nint(2)
        self.assertEqual(len(t), 2)  # shared, not copied
        self.assertTrue(t.hasKey(string("b")))
        self.assertIsInstance(newTable[string, nint](), TableRef)

    def test_table_generic_specializations(self):
        """std/tables: Table[K, V] is a nimic generic object: one registered specialization named as in Nim,
        so a generic proc over Table[A, B] binds A and B; getOrDefault(k) is default(V); OrderedTable is a
        Table that keeps insertion order (as every dict)."""
        self.assertIs(Table[string, nint], Table[string, nint])
        self.assertEqual(Table[string, nint].__name__, "Table[string, nint]")
        t = initTable[string, nint]()
        self.assertIs(type(t), Table[string, nint])
        t[string("a")] = nint(3)

        @dispatch
        def _tGetOrQuit[A, B](t: Table[A, B], k: A) -> B:
            return t[k]

        @dispatch
        def _tValueIsSeq[A, B](t: Table[A, B]) -> bool:
            return issubclass(B, seq)

        self.assertEqual(_tGetOrQuit(t, string("a")), 3)
        self.assertFalse(_tValueIsSeq(t))
        self.assertTrue(_tValueIsSeq(initTable[string, seq[nint]]()))
        # getOrDefault: the zero value of V for a missing key, or the given default
        self.assertEqual(t.getOrDefault(string("x")), 0)
        self.assertIsInstance(t.getOrDefault(string("x")), nint)
        self.assertEqual(t.getOrDefault(string("x"), nint(7)), 7)
        self.assertEqual(t.getOrDefault(string("a")), 3)
        self.assertEqual(initTable[nint, string]().getOrDefault(1), "")
        self.assertEqual(len(initTable[string, seq[nint]]().getOrDefault(string("x"))), 0)
        # OrderedTable: its own specializations, insertion order; not a Table (as in Nim)
        o = initOrderedTable[string, nint]()
        self.assertIs(type(o), OrderedTable[string, nint])
        self.assertNotIsInstance(o, Table)
        with self.assertRaises(NotImplementedError):
            _tGetOrQuit(o, string("a"))
        for k in ("z", "a", "m"):
            o[string(k)] = nint(1)
        self.assertEqual([str(k) for k in o._n_dict], ["z", "a", "m"])
        self.assertEqual(o.getOrDefault(string("q")), 0)

    def test_strutils_split(self):
        """strutils.split has Nim's results (a seq[string] of strings, runs of separators not merged), also as
        s.split(...): it replaces Python's UserString.split on string (@ufcs python_api)."""
        parts = string("foo.3.mymod").split(char("."))
        self.assertIsInstance(parts, seq)
        self.assertEqual([str(p) for p in parts], ["foo", "3", "mymod"])
        self.assertTrue(all(isinstance(p, string) for p in parts))
        self.assertTrue(all(isinstance(c, char) for c in parts[0]))
        self.assertEqual([str(p) for p in split(string(""), char(" "))], [""])
        self.assertEqual([str(p) for p in string("a,,b").split(char(","))], ["a", "", "b"])
        self.assertEqual([str(p) for p in string("a  b").split()], ["a", "", "b"])  # Python's gives ["a", "b"]
        self.assertEqual([str(p) for p in string("a,b;c").split(Tset[char](char(","), char(";")))], ["a", "b", "c"])
        self.assertEqual([str(p) for p in string("a man a plan").split(string("a "))], ["", "man ", "plan"])
        self.assertEqual([str(p) for p in string("a  largely    spaced").split(string(" "), maxsplit=1)],
                         ["a", " largely    spaced"])
        self.assertEqual([str(p) for p in string("unsplit").split(string(""))], ["unsplit"])
        self.assertEqual([str(p) for p in string("unsplit").split(Tset[char]())], ["unsplit"])

    def test_string_iteration_stops_at_len(self):
        """for c in s yields s[0 ..< s.len]: not the terminating '\\0' nor the buffer's spare capacity, also
        after add() gave the string a C buffer and with bound checks off."""
        s = string("")
        s.add(string("50.4"))
        self.assertEqual([str(c) for c in s], ["5", "0", ".", "4"])
        with push("boundChecks: off"):
            def _tChars(x: string) -> list:
                return [str(c) for c in x]
        self.assertEqual(_tChars(s), ["5", "0", ".", "4"])
        c = newStringOfCap(16)
        c.add(char("a"))
        self.assertEqual([str(ch_) for ch_ in c], ["a"])

    def test_slurp_resolves_against_the_original_source(self):
        """slurp / staticRead read a file relative to the calling module's original source file: the one its
        `# /// nimic` header records (`# source: <repo>@<sha>:<path>`), in the clone `$<REPO>_DIR` or a
        directory `<repo>` next to the module or one of its parents; without a header, the module's own
        directory. The path doesn't depend on the current directory."""
        with tempfile.TemporaryDirectory() as root:
            clone_doc = os.path.join(root, "fakerepo", "doc")
            os.makedirs(clone_doc)
            os.makedirs(os.path.join(root, "proj", "pkg", "lib"))
            with open(os.path.join(clone_doc, "version.md"), "wb") as f:
                f.write(b"1.2.3 2026-10-21\n")
            converted = os.path.join(root, "proj", "pkg", "lib", "m.py")
            with open(converted, "w") as f:
                f.write("# /// nimic\n# source: fakerepo@0123abcd:src/lib/m.nim\n# ///\n")
            plain = os.path.join(root, "proj", "pkg", "plain.py")
            with open(plain, "w") as f:
                f.write("# a module without a source header\n")
            with open(os.path.join(root, "proj", "pkg", "data.txt"), "wb") as f:
                f.write(b"local")

            def run(module_file, code):
                ns = {"__file__": module_file, "slurp": slurp, "staticRead": staticRead}
                exec(code, ns)
                return ns["x"]

            old_cwd = os.getcwd()
            os.chdir(tempfile.gettempdir())
            try:
                self.assertEqual(run(converted, "x = slurp('../../doc/version.md')"), "1.2.3 2026-10-21\n")
                self.assertIsInstance(run(converted, "x = slurp('../../doc/version.md')"), string)
                self.assertEqual(run(plain, "x = staticRead('data.txt')"), "local")
                with self.assertRaises(OSError):
                    run(plain, "x = slurp('missing.txt')")
                other = os.path.join(root, "elsewhere")
                os.makedirs(os.path.join(other, "doc"))
                with open(os.path.join(other, "doc", "version.md"), "wb") as f:
                    f.write(b"9.9.9")
                os.environ["FAKEREPO_DIR"] = other
                try:
                    self.assertEqual(run(converted, "x = slurp('../../doc/version.md')"), "9.9.9")
                finally:
                    del os.environ["FAKEREPO_DIR"]
            finally:
                os.chdir(old_cwd)
        out = unparse(ast.parse("from nimic.ntypes import *\nwith const:\n    _V = slurp('../../doc/version.md')\n"))[0]
        self.assertIn('V = slurp("../../doc/version.md")', out)

    def test_variable_pragma(self):
        """rule:varpragma: a variable annotated `pragma("cursor")` is `entry {.cursor.} = v`; with a type,
        `pragma("noinit") @ T` is `x {.noinit.}: T = v`, and rule:varini makes `x: pragma("noinit") @ T = T()`
        the declaration `x {.noinit.}: T`, for a subscripted type too. In Python the annotation has no effect
        (a local's annotation is never evaluated)."""
        src = ("from nimic.ntypes import *\n"
               "def f(t: seq[nint]) -> nint:\n"
               "    with let:\n"
               "        entry: pragma('cursor') = t\n"
               "        typed: pragma('cursor') @ seq[nint] = t\n"
               "    with var:\n"
               "        x: pragma('noinit') @ nint = nint(0)\n"
               "        y: nint = nint()\n"
               "        buf: pragma('noinit') @ array[12, char] = array[12, char]()\n"
               "        z: pragma('noinit') @ nint = nint()\n"
               "    buf[0] = ch('a')\n"
               "    return len(entry) + len(typed) + x\n"
               "with var:\n"
               "    _g: pragma('threadvar') @ nint = 0\n")
        out = unparse(ast.parse(src))[0]
        self.assertIn("entry {.cursor.} = t", out)
        self.assertIn("typed {.cursor.}: seq[int] = t", out)
        self.assertIn("x {.noinit.}: int = int(0)", out)
        self.assertIn("    y: int\n", out)  # rule:varini still applies to a plain annotation
        self.assertIn("    buf {.noinit.}: array[12, char]\n", out)
        self.assertIn("    z {.noinit.}: int\n", out)
        self.assertIn("g {.threadvar.}: int = 0", out)
        ns = {}
        exec("from __future__ import annotations\n" + src, ns)
        self.assertEqual(ns["f"](seq[nint]([1, 2])), 4)

    def test_lifetime_hook(self):
        """rule:hook: @hook("copy") on a def is the lifetime hook `=copy` (exported unless the name starts
        with _); an unknown hook is a ValueError. In Python the proc stays an ordinary function: Python copies
        where Nim moves, so the hook (an {.error.} one in particular) is Nim's."""
        src = ("from nimic.ntypes import *\n"
               "class _THooked(Object):\n    _buf: string\n"
               "@hook('copy')\n"
               "def _copyHooked(dest: mut @ _THooked, src: _THooked):\n    \"\"\"{.error.}\"\"\"\n    pass\n"
               "@hook('destroy')\n"
               "def destroyHooked(x: _THooked):\n    discard\n")
        out = unparse(ast.parse(src))[0]
        self.assertIn("proc `=copy`(dest: var THooked, src: THooked) {.error.}", out)
        self.assertIn("proc `=destroy`*(x: THooked) =", out)

        class _THookedBox(Object):
            v: nint

        @hook("wasMoved")
        def _tWasMoved(x: mut @ _THookedBox):
            x.v = nint(-1)
            return "called"
        self.assertEqual(_tWasMoved(_THookedBox()), "called")  # the hook stays an ordinary proc
        self.assertEqual(_tWasMoved._n_hook, "wasMoved")
        self.assertIs(_THookedBox._n_hooks["wasMoved"], _tWasMoved)
        with self.assertRaises(ValueError):
            hook("copyy")
        with self.assertRaises(TypeError):  # hooks belong to object types
            @hook("destroy")
            def _tNoType(x: nint):
                pass

    def test_loop_template(self):
        """A template that runs its code block in a loop (nifcore's loopInto) is called with `for _ in t():`,
        one iteration per run of the block. `break` leaves the template's loop and the template finishes
        (Nim's `break` in the expanded body); `return` and exceptions leave the template where it is. `with`
        still rejects it (a block run twice). The transpiler writes the block call `t(3):`."""
        log = []

        @template
        def loopTo(n: nint, body: untyped):
            with var:
                i = 0
            while i < n:
                body
                i += 1
            log.append(f"end {i}")

        def plain():
            for _ in loopTo(3):
                log.append("b")

        def stops():
            for _ in loopTo(5):
                log.append("b")
                if len(log) == 2:
                    break
            log.append("after")

        def returns():
            for _ in loopTo(5):
                return "r"

        plain()
        self.assertEqual(log, ["b", "b", "b", "end 3"])
        log.clear()
        stops()
        self.assertEqual(log, ["b", "b", "end 1", "after"])
        log.clear()
        self.assertEqual(returns(), "r")
        with self.assertRaises(ValueError):
            for _ in loopTo(5):
                raise ValueError
        self.assertEqual(log, [])  # neither returns nor exceptions finish the template
        with self.assertRaises(TemplateBlockError):
            with loopTo(2):
                pass
        out = unparse(ast.parse("from nimic.ntypes import *\n@template\ndef loopTo(n: nint, body: untyped):\n"
                                "    while n > 0:\n        body\n"
                                "def f(c: nint):\n    for _ in loopTo(3):\n        echo(1)\n"
                                "    for _ in c.loopTo():\n        break\n    for _ in range(3):\n        pass\n"))[0]
        self.assertIn("  loopTo(3):\n    echo(1)", out)
        self.assertIn("  c.loopTo():\n    break", out)
        self.assertIn("for _ in range(3):", out)  # other loops are not template calls

    def test_pointer_to_object_is_the_object(self):
        """Dereferencing a pointer to an object whose address was taken gives that object, also after casts
        and pointer arithmetic (nifcore's `cast[ptr TokenBuf](unsafeAddr b)[]`): its Python-held fields (a
        ref, a seq) are the object's, so a store through the pointer is seen by the object."""
        @ref
        class _TPRef(Object):
            n: nint

        class _TPBox(Object):
            count: nint
            owner: _TPRef
            items: seq[nint]

        box = _TPBox(count=nint(1), owner=None, items=seq[nint]([]))
        through = cast[ptr[_TPBox]](cast[uintp](unsafe_addr(box)))
        self.assertIs(through.contents, box)
        through.contents.owner = _TPRef(n=nint(7))
        through.contents.items.add(nint(3))
        through.contents.count += 1
        self.assertEqual((box.owner.n, len(box.items), box.count), (7, 1, 2))
        self.assertIs(cast[ptr[_TPBox]](addr(box)).contents, box)

    def test_table_copy(self):
        """A table's `.copy()` and `<<=` copy its entries (value entries copied, refs shared), as Nim's
        table assignment; the entries are not object fields, so Object's field copy missed them."""
        t = initTable[string, seq[nint]]()
        t[string("a")] = seq[nint]([nint(1)])
        c = t.copy()
        self.assertTrue(c.hasKey(string("a")))
        c[string("a")].add(nint(2))
        self.assertEqual((len(t[string("a")]), len(c[string("a")])), (1, 2))
        o = initOrderedTable[string, nint]()
        o[string("x")] = nint(5)
        o2 = initOrderedTable[string, nint]()
        o2 <<= o
        self.assertEqual(o2[string("x")], 5)
        o[string("y")] = nint(6)
        self.assertFalse(o2.hasKey(string("y")))

    def test_value_check_analysis(self):
        """rule:valuecheck: a binding of an l-value or a call's result without `.copy()` is a site (checked at run
        time) when one of the two names may change the value while the other is read later: a store, `+=`, a
        method call, an argument, a closure, a global. A local's last use (Nim moves it), `.copy()`, new values,
        names never changed, `with let:` names and a swap's targets that are only read are not."""
        source = textwrap.dedent("""\
            def f(p: P, q: P) -> P:
                with var:
                    a = p
                    b = p.f
                    c = g(p)
                    d = p.copy()
                    k = 1
                    m = a + b
                    n = q
                    r = q
                a.x += 1
                b.add(1)
                use(c)
                d.x = 2
                k += 1
                m.x = 3
                echo(n)
                return r

            def moves(p: P) -> P:
                with var:
                    x = h(p)
                    y = x
                y.x = 1
                for i in s:
                    w = y
                    w.x = 2
                with let:
                    z = p
                return y

            def captured(p: P):
                with var:
                    v = p
                def inner():
                    v.x = 1
                inner()
            """)
        source += textwrap.dedent("""\

            def alias(p: mut @ P) -> mut @ T:
                return p.f

            @template
            def t(p: P) -> T:
                return p.f

            def __iadd__(p: P, q: P) -> P:
                return p
            """)
        analysis = valuecheck.analyze(ast.parse(source), "<test>")
        found = {(site.target, site.sources[0].text) for site in analysis.sites if site.target is not None}
        # `echo(n)` may change n as far as syntax tells: the run time asks the callee (echo's varargs don't)
        self.assertEqual(found, {("a", "p"), ("b", "p.f"), ("c", "g(p)"), ("n", "q"), ("w", "y"), ("v", "p")})
        # a `-> T` proc's return of a value it may share is checked in the proc (its callers bind their own value);
        # alias results, templates and Python protocol methods are not
        returns = {(site.line, site.text, tuple(s.text for s in site.sources))
                   for site in analysis.sites if site.target is None}
        self.assertEqual(returns, {(18, "r", ("q",)), (30, "y", ("h(p)",))})
        # what each function returns that may be shared: `r = q` returns the parameter; `moves` returns its own value
        self.assertEqual([s.text for s in analysis.returns[(1, "f")]], ["q"])
        self.assertEqual([s.text for s in analysis.returns[(20, "moves")]], ["h(p)"])
        self.assertTrue(valuecheck.alias_annotation("mut @ T") and valuecheck.alias_annotation("lent@T")
                        and valuecheck.alias_annotation("untyped") and not valuecheck.alias_annotation("Point"))
        self.assertTrue(valuecheck.mutable_annotation("mut @ T") and not valuecheck.mutable_annotation("lent @ T"))

    def test_value_check_policy(self):
        """The type system's answers to the value checks: Nim's assignment copies value types (objects, seqs,
        strings, scalars, a tuple holding one), not refs, types or Python's immutable values; a call's result may
        be shared unless its callee is a type, a new-value builtin (`len`) or a nimic proc returning a new value;
        an argument may be changed through a `mut @` / `untyped` parameter or an unannotated core proc's, not
        through a type, a builtin or `*args`. A value's fingerprint (`_n_fingerprint`) tells whether a write
        changed it: equal values have equal fingerprints, refs compare by identity."""
        class _TVc(Object):
            x: nint

        @ref
        class _TVcRef(Object):
            x: nint

        for value in (_TVc(x=nint(1)), nint(3), string("ab"), seq[nint]([nint(1)]), (1, string("a"))):
            self.assertTrue(_n_assign_copies(value), value)
        for value in (_TVcRef(x=nint(1)), 3, "ab", None, _TVc, (1, 2)):
            self.assertFalse(_n_assign_copies(value), value)
        self.assertFalse(_n_result_may_alias(_TVc))
        self.assertFalse(_n_result_may_alias(len))
        self.assertTrue(_n_result_may_alias(min))
        @template
        def _tVcField(o: _TVc) -> nint:  # its body is substituted: the l-value itself
            return o.x

        @template
        def _tVcNew(o: _TVc) -> _TVc:
            return _TVc(x=o.x)

        self.assertTrue(_n_result_may_alias(_tVcField))
        self.assertFalse(_n_result_may_alias(_tVcNew))
        self.assertFalse(_n_result_may_alias(cast[int64]))  # a new value of the type

        def plainPython(p: _TVc) -> _TVc:  # not nimic code: may return its argument
            return p

        def setX(p: mut @ _TVc, x: nint) -> None:
            p.x = x

        self.assertTrue(_n_result_may_alias(plainPython))
        self.assertTrue(_n_param_mutable(setX, 0, None))
        self.assertFalse(_n_param_mutable(setX, 1, None))
        self.assertFalse(_n_param_mutable(setX, None, "x"))
        self.assertTrue(_n_param_mutable(setLen, 0, None))  # a core proc, unannotated
        self.assertFalse(_n_param_mutable(echo, 0, None))  # varargs
        self.assertFalse(_n_param_mutable(_TVc, 0, None))
        self.assertFalse(_n_param_mutable(len, 0, None))
        self.assertTrue(_n_param_mutable(seq[nint]([nint(1)]).add, -1, None))  # a core method's receiver

        class _TVcHolder(Object):
            v: _TVc
            items: seq[nint]
            r: _TVcRef
            name: string

        holder = _TVcHolder(v=_TVc(x=nint(1)), items=seq[nint]([nint(1)]), r=_TVcRef(x=nint(1)), name=string("a"))
        before = _n_fingerprint(holder)
        self.assertEqual(_n_fingerprint(holder.copy()), before)  # an equal value
        holder.r.x = nint(2)  # a ref's target is not the value's (Nim shares it)
        self.assertEqual(_n_fingerprint(holder), before)
        for change in (lambda: setattr(holder.v, "x", nint(5)), lambda: holder.items.add(nint(2)),
                       lambda: holder.name.add(string("b")), lambda: setattr(holder, "r", _TVcRef(x=nint(2)))):
            change()
            self.assertNotEqual(_n_fingerprint(holder), before)
            before = _n_fingerprint(holder)
        table = initTable[string, seq[nint]]()
        table[string("k")] = seq[nint]([nint(1)])
        before = _n_fingerprint(table)
        table[string("k")].add(nint(2))
        self.assertNotEqual(_n_fingerprint(table), before)
        scalar = nint(1)
        before = _n_fingerprint(scalar)
        scalar += 1
        self.assertNotEqual(_n_fingerprint(scalar), before)

    def test_value_check_program(self):
        """A nimic program (the `# /// nimic` header) runs as written; its bindings are checked when they run:
        tests/nimic/value_bindings.py writes each copy Nim's assignment makes and prints what compiled Nim prints
        (tests/verify_transpiled.py nimic). A missing copy whose value a write then changes while both locations
        hold it (a certain difference from Nim) is a ValueCopyError naming the binding and the write (main program
        and imported module), or a warning (NIMIC_VALUECHECK=warn); a binding that only may differ (rebound before
        the write, a getter's result only read) is not, and NIMIC_VALUECHECK=lint lists it.
        NIMIC_VALUECHECK_REPORT lists the sites."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((os.path.join(root, "src"), root)))
        env.pop("NIMIC_VALUECHECK", None)
        run = subprocess.run([sys.executable, os.path.join(root, "tests", "nimic", "value_bindings.py")],
                             capture_output=True, text=True, env=env, cwd=root)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.splitlines(), [
            "declared: a.x=1 b.x=2 n=6 same=11 result=101 a.tags=1 tags=2",
            "core procs: a.x=1 lo=1001 shown=a.x",
            "std procs: stored=1 entry=2",
            "re-assigned: a.x=1 c.x=50",
            "swapped: u.x=1004 w.x=3",
            "aliases: h.p.x=7 h.name=h s=h! mine=70 seen=80 got=90",
            "tracked: t.n=1 kept.n=2 copies=1",
            "moved: last.n=12 copies=1"])
        with tempfile.TemporaryDirectory() as tmp:  # each of its copies is needed: without them, 13 errors
            path = os.path.join(tmp, "value_bindings_nocopy.py")
            with builtins.open(os.path.join(root, "tests", "nimic", "value_bindings.py"), encoding="utf-8") as f:
                source = f.read()
            with builtins.open(path, "w", encoding="utf-8") as f:
                f.write(source.replace(".copy()", ""))
            nocopy = subprocess.run([sys.executable, path], capture_output=True, text=True,
                                    env=dict(env, NIMIC_VALUECHECK="warn"))
            self.assertEqual(nocopy.returncode, 0, nocopy.stderr)
            self.assertEqual(sum(line.startswith("nimic valuecheck: ") for line in nocopy.stderr.splitlines()), 13,
                             nocopy.stderr)
        program = textwrap.dedent("""\
            # /// nimic
            #
            # ///
            from nimic.ntypes import *

            class P(Object):
                x: nint

            class H(Object):
                p: P

            def get(h: H) -> P:
                return h.p

            def maybe(p: P, fresh: bool):
                with var:
                    q = p
                if fresh:
                    q = P(x=nint(9))
                q.x += 1
                echo(p.x)

            def bump(p: P):
                with var:
                    q = p
                q.x += 1
                echo(p.x)

            def viaGetter(h: H):
                with var:
                    g = get(h)
                g.x += 1
                echo(h.p.x)

            if comptime(__name__ == "__main__"):
                with var:
                    h = H(p=P(x=nint(1)))
                echo(get(h).x)
                maybe(P(x=nint(1)), True)
                bump(P(x=nint(1)))
                viaGetter(h)
            """)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vc_missing.py")
            with open(path, "w") as f:
                f.write(program)
            failed = subprocess.run([sys.executable, path], capture_output=True, text=True, env=env)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(failed.stdout, "1\n1\n")  # the possible-only bindings run on
            self.assertIn("ValueCopyError", failed.stderr)
            self.assertIn("vc_missing.py:25: `q = p` binds the P that p holds", failed.stderr)
            self.assertIn("line 26 (`q.x += 1`) changed it while both held it", failed.stderr)
            self.assertIn("write `q = p.copy()`", failed.stderr)
            report = os.path.join(tmp, "report.jsonl")
            warned = subprocess.run([sys.executable, path], capture_output=True, text=True,
                                    env=dict(env, NIMIC_VALUECHECK="warn", NIMIC_VALUECHECK_REPORT=report))
            self.assertEqual((warned.returncode, warned.stdout), (0, "1\n1\n2\n2\n"), warned.stderr)
            self.assertIn("vc_missing.py:31: `g = get(h)` binds the P that an input of get(h) (h) holds",
                          warned.stderr)
            self.assertNotIn("(lint)", warned.stderr)
            with open(report) as f:
                entry = json.loads(f.read())
            self.assertEqual([e.rsplit(":", 1)[1] for e in entry["errors"]], ["25", "31"])
            self.assertEqual((entry["possible"], entry["unchecked"]), ([], []))
            linted = subprocess.run([sys.executable, path], capture_output=True, text=True,
                                    env=dict(env, NIMIC_VALUECHECK="lint"))
            self.assertEqual((linted.returncode, linted.stdout), (0, "1\n1\n2\n2\n"), linted.stderr)
            for line in ("13: `return h.p`", "17: `q = p`", "25: `q = p`", "31: `g = get(h)`"):
                self.assertIn(f"nimic valuecheck (lint): {path}:{line}", linted.stderr)
            # an imported nimic module is checked too (the import hook only watches it), and runs as written
            imported = subprocess.run([sys.executable, "-c", "import nimic, vc_missing; vc_missing.bump(vc_missing.P())"],
                                      capture_output=True, text=True, env=dict(env, PYTHONPATH=env["PYTHONPATH"] + os.pathsep + tmp))
            self.assertIn("ValueCopyError", imported.stderr)
            off = subprocess.run([sys.executable, path], capture_output=True, text=True,
                                 env=dict(env, NIMIC_VALUECHECK="off"))
            self.assertEqual((off.returncode, off.stdout), (0, "1\n1\n2\n2\n"), off.stderr)

    def test_value_check_sink_moved_out(self):
        """A proc that moves its `sink @` parameter (`ensureMove(buf)`) empties the caller's object in Python. Nim
        moves the argument only at its last use, and copies it otherwise: a ValueCopyError when a caller up the chain
        still holds the value in a location it reads again (a local read later, a global), naming the call where Nim
        copies (where the first borrowed parameter or live location passes it) and the copy to write. Passing a copy,
        a local at its last use or a `sink` parameter on is no error (nifcoreparse's `openFromBuffer(input.copy())`)."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((os.path.join(root, "src"), root)))
        program = textwrap.dedent("""\
            # /// nimic
            #
            # ///
            from nimic.ntypes import *

            class Reader(Object):
                buf: string

            def openFromBuffer(buf: sink @ string) -> Reader:
                return Reader(buf=ensureMove(buf))

            def parse(input: string) -> nint:
                with var:
                    r = openFromBuffer(input)
                return len(r.buf)

            def parseCopy(input: string) -> nint:
                with var:
                    r = openFromBuffer(input.copy())
                return len(r.buf)

            def passOn(s: sink @ string) -> nint:
                r = openFromBuffer(s)
                return len(r.buf)

            def lastUse() -> nint:
                with var:
                    s = string("local")
                return passOn(s)

            def liveLocal() -> nint:
                with var:
                    s = string("abc")
                r = openFromBuffer(s)
                echo(s)
                return len(r.buf)

            def main(case: string):
                with var:
                    text = string("hello")
                if case == "copy":
                    echo(parseCopy(text), text, lastUse(), passOn(string("tmp")))
                elif case == "live":
                    echo(liveLocal())
                else:
                    echo(parse(text), text)

            if comptime(__name__ == "__main__"):
                import sys
                main(string(sys.argv[1]))
            """)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vc_sink.py")
            with open(path, "w") as f:
                f.write(program)

            def run(case, mode="error"):
                return subprocess.run([sys.executable, path, case], capture_output=True, text=True,
                                      env=dict(env, NIMIC_VALUECHECK=mode))

            fine = run("copy")
            self.assertEqual((fine.returncode, fine.stdout), (0, "5hello53\n"), fine.stderr)
            borrowed = run("parse")
            self.assertIn("ValueCopyError", borrowed.stderr)
            self.assertIn(f"{path}:10: `return Reader(buf=ensureMove(buf))` empties the string that `text` still "
                          f"holds at {path}:46", borrowed.stderr)
            self.assertIn(f"Nim copies its argument at {path}:14 (`r = openFromBuffer(input)`), where `input` is a "
                          f"borrowed parameter there", borrowed.stderr)
            self.assertIn("pass `input.copy()` in that call", borrowed.stderr)
            live = run("live")
            self.assertIn("where `s` is read again at line 35", live.stderr)
            warned = run("parse", "warn")
            self.assertEqual((warned.returncode, warned.stdout), (0, "5\n"), warned.stderr)  # Python emptied it
            self.assertIn("nimic valuecheck: ", warned.stderr)
            off = run("parse", "off")
            self.assertEqual((off.returncode, off.stderr), (0, ""))

    def test_value_check_type_holds_no_value(self):
        """`default(T)` at module level (a test block): its input is the type, Nim's typedesc, which holds no value.
        valuecheck doesn't search a type's attributes for the bound value (they reach the module's globals, where
        the variable itself is): changing it through a `mut @` parameter is no ValueCopyError."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((os.path.join(root, "src"), root)))
        env.pop("NIMIC_VALUECHECK", None)
        program = textwrap.dedent("""\
            # /// nimic
            #
            # ///
            from nimic.ntypes import *

            class T(Object):
                a: nint

            def fill(t: mut @ T):
                t.a = 3

            if comptime(__name__ == "__main__"):
                with var:
                    tok = default(T)
                fill(tok)
                echo(tok.a)
            """)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vc_typedesc.py")
            with builtins.open(path, "w") as f:
                f.write(program)
            run = subprocess.run([sys.executable, path], capture_output=True, text=True, env=env)
            self.assertEqual((run.returncode, run.stdout), (0, "3\n"), run.stderr)

    def test_value_check_pointer_bindings(self):
        """A pointer is a value in Nim: `var p = t.p` copies the address. Python binds the field's own pointer
        (a view of its slot), so an in-place write through the copy (`p <<= q`, or `p` passed to a `var pchar`
        parameter that assigns it) also moves `t.p`. valuecheck watches pointer bindings like scalar ones: the
        missing `.copy()` is a ValueCopyError naming the binding and the write. Stores still share pointers;
        rebinding the name (`p = cast[pchar](...)`, what `inc p` expands to) is no write; with `.copy()` the
        field keeps its address, and `pointer.copy()` reads the slot's current address."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((os.path.join(root, "src"), root)))
        env.pop("NIMIC_VALUECHECK", None)
        program = textwrap.dedent("""\
            # /// nimic
            #
            # ///
            from nimic.ntypes import *

            pchar = ptr[UncheckedArray[char]]

            class View(Object):
                p: pchar
                len: nint

            def advance(p: mut @ pchar):
                p <<= cast[pchar](cast[intp](p) + 1)

            def rebound(v: View) -> char:
                with var:
                    p = v.p
                p = cast[pchar](cast[intp](p) + 2)
                advance(p)
                return p[0]

            def copied(v: View) -> char:
                with var:
                    p = v.p.copy()
                advance(p)
                return p[0]

            def shared(v: View) -> char:
                with var:
                    p = v.p
                advance(p)
                return p[0]

            if comptime(__name__ == "__main__"):
                with var:
                    s = string("abcdef")
                    v = View(p=cast[pchar](addr(s[0])), len=nint(6))
                echo(rebound(v), v.p[0])
                echo(copied(v), v.p[0])
                v.p <<= cast[pchar](cast[intp](v.p) + 4)
                echo(v.p.copy()[0])
                echo(shared(v), v.p[0])
            """)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vc_pointer.py")
            with builtins.open(path, "w") as f:
                f.write(program)
            run = subprocess.run([sys.executable, path], capture_output=True, text=True, env=env)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(run.stdout, "da\nba\ne\n")  # the rebound and copied bindings run on
            self.assertIn("ValueCopyError", run.stderr)
            self.assertIn("vc_pointer.py:30: `p = v.p` binds the ptr[UncheckedArray[char]] that v.p holds", run.stderr)
            self.assertIn("line 31 (`advance(p)`) changed it while both held it", run.stderr)
            self.assertIn("write `p = v.p.copy()`", run.stderr)
            fixed = subprocess.run([sys.executable, path], capture_output=True, text=True,
                                   env=dict(env, NIMIC_VALUECHECK="warn"))
            self.assertEqual((fixed.returncode, fixed.stdout), (0, "da\nba\ne\nff\n"), fixed.stderr)  # warn runs on: `shared` moved v.p too (Nim prints "fe")

    def test_block_ends_lifetimes(self):
        """`with block:` / `with block("name"):` end the lifetimes of the variables they declare, as Nim's
        scopes: an owning value with a `=destroy` hook is destroyed at the block's end, the last declared
        first, once (not again when CPython frees it). A value that escapes the block (returned, bound to an
        outer variable) is not destroyed there, as Nim moves it out."""
        log = []

        class _TScoped(Object):
            tag: nint

        @hook("destroy")
        def _tScopedDestroy(x: mut @ _TScoped):
            log.append(int(x.tag))

        def scoped():
            with block:
                with var:
                    a = _TScoped(tag=1)
                    b = _TScoped(tag=2)
                log.append(0)
            log.append(-1)  # after the block: both destroyed, b first
            with block("named"):
                with var:
                    c = _TScoped(tag=3)
                breakBlock("named")
            log.append(-2)
            with var:
                kept = None
            with block:
                with var:
                    d = _TScoped(tag=4)
                kept = d  # escapes into an outer variable: not destroyed by the block
            log.append(-3)
            with block:
                with var:
                    e = _TScoped(tag=5)
                return e  # returned: not destroyed by the block

        e = scoped()
        self.assertEqual(log[:6], [0, 2, 1, -1, 3, -2])
        self.assertNotIn(5, log)
        self.assertEqual(e.tag, 5)
        del e
        self.assertEqual(log.count(5), 1)  # destroyed once, when CPython frees it
        self.assertEqual(log.count(1) + log.count(2) + log.count(3), 3)  # not again at the proc's end

    def test_const_values_are_frozen(self):
        """Values bound in `with const:` are frozen: a variable aliasing a constant and changed in place
        (`x += 1`, `x <<= y`, a field store, an in-place change of a field) raises TypeError naming the
        constant and `.copy()`, instead of changing the constant. Copies, rebinding and reads work."""
        class _TCPoint(Object):
            x: nint
            y: int32

        with const:
            _CBits = u32(28)
            _COrigin = _TCPoint(x=nint(0), y=i32(0))
        with var:
            shift = _CBits
        with self.assertRaises(TypeError) as cm:
            shift += _CBits
        self.assertIn("_CBits.copy()", str(cm.exception))
        self.assertEqual(_CBits, 28)
        with var:
            last = _COrigin
        for change in (lambda: last.__ilshift__(_TCPoint(x=nint(7), y=i32(1))),
                       lambda: setattr(last, "x", nint(7)),
                       lambda: last.y.__iadd__(1)):
            with self.assertRaises(TypeError):
                change()
        self.assertEqual((_COrigin.x, _COrigin.y), (0, 0))
        with var:
            own = _CBits.copy()
            mine = _COrigin.copy()
        own += _CBits
        mine <<= _TCPoint(x=nint(7), y=i32(1))
        mine.y += 1
        self.assertEqual((own, mine.x, mine.y, _CBits, _COrigin.x), (56, 7, 2, 28, 0))
        shift = shift + 1  # rebinding the variable is no change of the constant
        self.assertEqual((shift, _CBits), (29, 28))

    def test_lifetime_hooks_count_references(self):
        """Lifetime hooks at run time (ncompiler/proposals/feature_lifetime_hooks_runtime.md): one owning
        object is one Nim value. A handle counts its owner's references as nifcore's Cursor does: `=dup` /
        `=copy` add one, `=destroy` (when CPython frees an owning handle) takes one away, move() keeps
        the count and =wasMoved's the source. Views (casts) and aliases don't count."""
        @ref
        class _TOwner(Object):
            rc: nint

        class _THandle(Object):
            owner: _TOwner
            pos: nint

        @hook("destroy")
        def _tDestroy(x: mut @ _THandle):
            if x.owner is not None:
                x.owner.rc -= 1

        @hook("wasMoved")
        def _tWasMoved(x: mut @ _THandle):
            x.owner = None

        @hook("copy")
        def _tCopy(dest: mut @ _THandle, src: _THandle):
            if dest.owner is not src.owner:
                _tDestroy(dest)
                if src.owner is not None:
                    src.owner.rc += 1
                dest.owner = src.owner
            dest.pos = src.pos

        @hook("dup")
        def _tDup(src: _THandle) -> _THandle:
            if src.owner is not None:
                src.owner.rc += 1
            return _THandle(owner=src.owner, pos=src.pos)

        class _THolder(Object):
            h: _THandle

        def begin_read(o: _TOwner) -> _THandle:  # nifcore's beginRead: the new handle holds one count
            o.rc += 1
            return _THandle(owner=o)

        o = _TOwner()
        h = begin_read(o)
        self.assertEqual(o.rc, 1)

        def use_copy():
            c = h.copy()  # =dup
            self.assertEqual(o.rc, 2)
            self.assertIsNot(c, h)
        use_copy()
        self.assertEqual(o.rc, 1)  # the copy died at the end of the function
        alias = h  # an alias is the same value: no count
        self.assertEqual(o.rc, 1)
        del alias
        # stores copy (=dup); the stored handle dies with its container
        holder = _THolder(h=h)
        self.assertEqual(o.rc, 2)
        handles = seq[_THandle]()
        handles.add(h)
        self.assertEqual(o.rc, 3)
        handles.add(begin_read(o))  # a temporary: Nim moves it; Python copies it, and the temporary dies
        self.assertEqual(o.rc, 4)
        del handles
        self.assertEqual(o.rc, 2)
        holder.h = begin_read(o)  # the old field value dies
        self.assertEqual(o.rc, 2)
        del holder
        self.assertEqual(o.rc, 1)
        # `a = b` into an existing value: =copy
        other = _TOwner()
        g = begin_read(other)
        g <<= h
        self.assertEqual((o.rc, other.rc), (2, 0))
        del g
        self.assertEqual(o.rc, 1)
        # move keeps the count and =wasMoved's the source
        m = move(h)
        self.assertEqual(o.rc, 1)
        self.assertIsNone(h.owner)
        self.assertIs(m.owner, o)
        del h
        self.assertEqual(o.rc, 1)  # a moved-from handle destroys nothing
        # a view doesn't own: a cast of the handle's memory leaves the count alone
        view = _THandle._n_cast(m)
        del view
        self.assertEqual(o.rc, 1)
        del m
        self.assertEqual(o.rc, 0)

    def test_lifetime_hook_failure_fails_the_program(self):
        """A `=destroy` hook that raises (Python only prints exceptions in __del__) makes the program exit with
        status 1 and a report on stderr, after its normal output."""
        source = textwrap.dedent("""\
            from __future__ import annotations
            from nimic.ntypes import *

            class Res(Object):
                n: nint

            @hook("destroy")
            def _destroyRes(r: mut @ Res):
                if r.n == 2:
                    raise ValueError("cannot release 2")

            def f():
                with var:
                    a = Res(n=nint(1))
                    b = Res(n=nint(2))
                print("in f")

            f()
            print("after f")
            """)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "failing_destroy.py")
            with open(path, "w") as f:
                f.write(source)
            run = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 1, run.stderr[-500:])
        self.assertEqual(run.stdout.splitlines(), ["in f", "after f"])
        self.assertIn("1 `=destroy` hook(s) failed", run.stderr)
        self.assertIn("cannot release 2", run.stderr)

    def test_lifetime_hooks_in_arrays(self):
        """An array of values with hooks holds their owning objects (no C storage): a store copies (=dup),
        an overwritten element and the array's elements die with it (=destroy), `a <<= b` copies each."""
        @ref
        class _TArrOwner(Object):
            rc: nint

        class _TArrHandle(Object):
            owner: _TArrOwner

        @hook("destroy")
        def _tArrDestroy(x: mut @ _TArrHandle):
            if x.owner is not None:
                x.owner.rc -= 1

        @hook("dup")
        def _tArrDup(src: _TArrHandle) -> _TArrHandle:
            if src.owner is not None:
                src.owner.rc += 1
            return _TArrHandle(owner=src.owner)

        o = _TArrOwner()
        o.rc += 1
        h = _TArrHandle(owner=o)
        handles = array[3, _TArrHandle]()
        self.assertIsNone(handles._n_view)  # Python-held elements
        handles[0] = h
        handles[1] = h
        self.assertEqual(o.rc, 3)
        handles[1] = _TArrHandle()  # the overwritten element dies
        self.assertEqual(o.rc, 2)
        other = array[3, _TArrHandle]()
        other <<= handles
        self.assertEqual(o.rc, 3)
        del handles, other
        self.assertEqual(o.rc, 1)
        del h
        self.assertEqual(o.rc, 0)

    def test_array_assign_python_held_elements(self):
        """`a <<= b` of arrays without C storage (here of seqs) copies the elements; it called
        ctypes.addressof(None)."""
        a = array[2, seq[nint]]([seq[nint]([1]), seq[nint]([2, 3])])
        b = array[2, seq[nint]]()
        b <<= a
        self.assertEqual(str(b), "[@[1], @[2, 3]]")
        a[0].add(nint(9))
        self.assertEqual(str(b), "[@[1], @[2, 3]]")  # a copy

    def test_lifetime_hooks_move_only(self):
        """A `=copy` with {.error.} (nifcore's TokenBuf, treemangler's Mangler) makes the type move-only:
        Nim proves no copy happens, so a store moves (shares) the value and `.copy()` is a TypeError;
        `a <<= b` moves b in (a's old value destroyed, b no longer owns)."""
        destroyed = []

        class _TBuf(Object):
            n: nint

        @hook("copy")
        def _tNoCopy(dest: mut @ _TBuf, src: _TBuf):
            """{.error.}"""
            pass

        @hook("destroy")
        def _tFree(x: mut @ _TBuf):
            destroyed.append(int(x.n))

        class _TBufHolder(Object):
            b: _TBuf

        self.assertTrue(_TBuf._n_move_only)
        b = _TBuf(n=nint(1))
        holder = _TBufHolder(b=b)
        self.assertIs(holder.b, b)  # moved in, not copied
        with self.assertRaises(TypeError):
            b.copy()
        del b
        self.assertEqual(destroyed, [])  # the holder still has it
        del holder
        self.assertEqual(destroyed, [1])
        a, c = _TBuf(n=nint(2)), _TBuf(n=nint(3))
        a <<= c
        self.assertEqual(destroyed, [1, 2])  # a's old value
        del c
        self.assertEqual(destroyed, [1, 2])  # c was moved out: it no longer owns
        del a
        self.assertEqual(destroyed, [1, 2, 3])
        # an owner's own ctypes buffer is released too, as for every Object (_Object.__del__)
        d = _TBuf(n=nint(4))
        addr = d.__dict__.get("_n_owned_addr")
        self.assertIsNotNone(addr)
        self.assertIn(addr, BUFFER_REGISTRY)
        del d
        self.assertNotIn(addr, BUFFER_REGISTRY)
        self.assertEqual(destroyed, [1, 2, 3, 4])

    def test_concepts(self):
        """rule:concept: `class C(Concept): pass` is Nim 2's universal `C = concept x`; signatures in the body are
        the concept's procs over `Self` (`{.noSideEffect.}`: func); a concept base is nimony's `concept of B`.
        A concept is a @dispatch bound `[T: C]`; Python doesn't check its signatures yet, so every type fits
        (Nim checks them). A concept has no instances."""
        src = ("from nimic.ntypes import *\n"
               "class _Equatable(Concept):\n    pass\n"
               "class Hashable(Concept):\n    def hash(x: Self) -> Hash: ...\n"
               "class Comparable(Concept):\n"
               "    def __eq__(x: Self, y: Self) -> bool:\n        \"\"\"{.noSideEffect.}\"\"\"\n"
               "    def __lt__(x: Self, y: Self) -> bool:\n        \"\"\"{.noSideEffect.}\"\"\"\n"
               "class Keyable(Hashable):\n    def __eq__(a: Self, b: Self) -> bool: ...\n"
               "class HasDefault(Concept):\n    def default(_: typedesc[Self]) -> Self: ...\n"
               "def cmp2[T: Comparable](x: T, y: T) -> nint:\n    return 0\n")
        out = unparse(ast.parse(src))[0]
        self.assertIn("  Equatable = concept x\n", out)
        self.assertIn("  Hashable* = concept\n    proc hash(x: Self): Hash\n", out)
        self.assertIn("  Comparable* = concept\n    func `==`(x: Self, y: Self): bool\n    func `<`(x: Self, y: Self): bool\n", out)
        self.assertIn("  Keyable* = concept of Hashable\n    proc `==`(a: Self, b: Self): bool\n", out)
        self.assertIn("  HasDefault* = concept\n    proc default(_: typedesc[Self]): Self\n", out)
        self.assertIn("proc cmp2*[T: Comparable](x: T, y: T): int =", out)
        self.assertNotIn("import typing", out)

        class _TComparable(Concept):
            def __lt__(x: Self, y: Self) -> bool: ...

        @dispatch
        def _tMin[T: _TComparable](x: T, y: T) -> T:
            return x if x < y else y

        @dispatch
        def _tFirst[K: _TComparable, V](t: Table[K, V], k: K) -> V:
            return t[k]

        self.assertEqual(_tMin(nint(3), nint(2)), 2)
        self.assertEqual(_tMin(string("b"), string("a")), "a")
        t = initTable[string, nint]()
        t[string("k")] = nint(5)
        self.assertEqual(_tFirst(t, string("k")), 5)
        with self.assertRaises(TypeError):
            _TComparable()

    def test_import_module_of_nimic_package(self):
        """`from nimic.std import memfiles` (a std module used qualified, memfiles.open) is `import std/memfiles`,
        once even next to `from nimic.std.memfiles import *`; `as` keeps its name; `from . import m` (a sibling)
        emits nothing, as before."""
        out = unparse(ast.parse("from nimic.ntypes import *\n"
                                "from nimic.std.memfiles import *\n"
                                "from nimic.std import memfiles\n"
                                "from nimic.std import os as nos\n"
                                "from . import msgs\n"))[0]
        self.assertEqual(out.count("import std/memfiles"), 1)
        self.assertIn("import std/os as nos", out)
        self.assertNotIn("msgs", out)
        self.assertNotIn("import std\n", out)

    def test_import_module_of_relative_package(self):
        """`from ..models import leng_tags, tags` binds module names of a sibling directory (nifcdecl's
        `export leng_tags`): `import ../models/tags`, nothing for a module a star import already imports,
        never `import ../models` (a directory)."""
        out = unparse(ast.parse("from nimic.ntypes import *\n"
                                "from ..models.leng_tags import *\n"
                                "from ..models import leng_tags, tags\n"
                                "from ..options import *\n"
                                "with export:\n"
                                "    leng_tags\n"))[0]
        self.assertEqual(out.count("import ../models/leng_tags"), 1)
        self.assertIn("import ../models/tags\n", out)
        self.assertNotIn("import ../models\n", out)
        self.assertIn("import ../options", out)
        self.assertIn("export\n  leng_tags", out)

    def test_import_module_alias(self):
        """`from . import nifreader as rd` (nifcoreparse's `import nifreader as rd`, used qualified: rd.next) is
        `import nifreader as rd`; `from ..lib import vfs as v` keeps its directory."""
        out = unparse(ast.parse("from nimic.ntypes import *\n"
                                "from . import nifreader as rd\n"
                                "from ..lib import vfs as v\n"
                                "x = rd.EofToken\n"))[0]
        self.assertIn("import nifreader as rd\n", out)
        self.assertIn("import ../lib/vfs as v\n", out)

    def test_uint64_literal_above_int64(self):
        """rule:literaltypes: uint64(c) / uint(c) with a constant above high(int64) is c'u64 / c'u (Nim reads a bare
        c as an int: out of range); smaller constants keep the conversion."""
        out = unparse(ast.parse("from nimic.ntypes import *\n"
                                "a = uint64(18446744073709551615)\n"
                                "b = uint(9223372036854775808)\n"
                                "c = uint64(5)\n"))[0]
        self.assertIn("18446744073709551615'u64", out)
        self.assertIn("9223372036854775808'u", out)
        self.assertIn("uint64(5)", out)

    def test_selective_import(self):
        """A Python `from m import a` (a class comes with its methods) is a full `import m`; Nim's selective
        `from m import a, b` is importFrom("m", "a", "b") (rule:importfrom), which binds only those names."""
        out = unparse(ast.parse("from nimic.std.times import utc, fromUnix\n"
                                "importFrom('nimic.std.times', 'utc', 'fromUnix')\n"
                                "importFrom('..options', 'TGCMode', '%')\n"
                                "from .lineinfos import *\n"))[0]
        self.assertIn("import std/times\n", out)
        self.assertIn("from std/times import utc, fromUnix", out)
        self.assertIn("from ../options import TGCMode, `%`", out)
        self.assertIn("import lineinfos", out)
        ns = {"importFrom": importFrom, "__name__": "probe", "__package__": ""}
        exec("importFrom('nimic.std.terminal', 'styledWrite')", ns)
        self.assertIn("styledWrite", ns)
        self.assertNotIn("styledWriteLine", ns)
        # Nim's `from m import nil` (nifpools' nifcoreparse): only the module's name, for qualified calls
        self.assertIn("from ../options import nil", unparse(ast.parse("importFrom('..options')\n"))[0])
        exec("importFrom('nimic.std.terminal')", ns)
        self.assertIs(ns["terminal"], sys.modules["nimic.std.terminal"])
        self.assertNotIn("nil", ns)

    def test_selective_import_of_enum_members(self):
        """nifpools' `from vfs import FileWriteMode, AlwaysWrite, OnlyIfChanged`: a non-pure enum's members are
        symbols of its module in Nim, so importFrom binds a member by its name (in Python it lives in its class).
        A name of no enum, or of members of two enums (Nim picks by the expected type), is an ImportError."""
        module = types.ModuleType("_n_imp_enums")
        exec(textwrap.dedent("""
            from nimic.ntypes import *
            class Mode(NIntEnum):
                AlwaysWrite = auto()
                OnlyIfChanged = auto()
            ModeAlias = Mode
            class Vis(NIntEnum):
                Local = auto()
                Shared = auto()
            class Capture(NIntEnum):
                Local = auto()
            """), module.__dict__)
        sys.modules[module.__name__] = module
        try:
            ns = {"importFrom": importFrom, "__name__": "probe", "__package__": ""}
            exec("importFrom('_n_imp_enums', 'Mode', 'AlwaysWrite', 'OnlyIfChanged', 'Shared')", ns)
            self.assertIs(ns["AlwaysWrite"], module.Mode.AlwaysWrite)
            self.assertIs(ns["OnlyIfChanged"], module.Mode.OnlyIfChanged)
            self.assertIs(ns["Shared"], module.Vis.Shared)
            with self.assertRaisesRegex(ImportError, "a member of the enums Capture, Vis, write it qualified"):
                exec("importFrom('_n_imp_enums', 'Local')", ns)
            with self.assertRaisesRegex(ImportError, "cannot import name 'Missing' from '_n_imp_enums'$"):
                exec("importFrom('_n_imp_enums', 'Missing')", ns)
        finally:
            sys.modules.pop(module.__name__)
        out = unparse(ast.parse("importFrom('.vfs', 'FileWriteMode', 'AlwaysWrite')\n"))[0]
        self.assertIn("from vfs import FileWriteMode, AlwaysWrite", out)

    def test_export_except(self):
        """Nim's `export nifcore except createTokenBuf, pool` is exportExcept(nifcore, "createTokenBuf", "pool")
        (rule:exportexcept; operators by their Nim names). In Python it only checks its argument is a module."""
        out = unparse(ast.parse("from . import nifcore\nexportExcept(nifcore, 'createTokenBuf', 'pool', '%')\n"))[0]
        self.assertIn("export nifcore except createTokenBuf, pool, `%`", out)
        exportExcept(textwrap, "dedent")
        with self.assertRaisesRegex(TypeError, "is no module"):
            exportExcept("textwrap", "dedent")

    def test_strtabs_modes(self):
        """std/strtabs: keys compare by the table's mode (case / style insensitive)."""
        from nimic.std.strtabs import newStringTable, StringTableMode, modeStyleInsensitive
        t = newStringTable(modeStyleInsensitive)
        t[string("foo_Bar")] = string("1")
        self.assertTrue(t.hasKey(string("FooBar")))
        self.assertEqual(str(t[string("foobar")]), "1")
        t[string("FOOBAR")] = string("2")
        self.assertEqual(len(t), 1)
        self.assertEqual(str(t.getOrDefault(string("foo_bar"))), "2")
        self.assertEqual(str(t.getOrDefault(string("x"), string("d"))), "d")
        cs = newStringTable(StringTableMode.modeCaseSensitive)
        cs[string("A")] = string("a")
        self.assertFalse(cs.hasKey(string("a")))
        ci = newStringTable(string("k1"), string("v1"), string("K2"), string("v2"), StringTableMode.modeCaseInsensitive)
        self.assertEqual(str(ci[string("k2")]), "v2")
        self.assertEqual([(str(k), str(v)) for k, v in ci.pairs()], [("k1", "v1"), ("K2", "v2")])
        self.assertEqual(str(ci.mode), "modeCaseInsensitive")
        ci.del_(string("K1"))
        self.assertEqual(len(ci), 1)
        self.assertEqual(str(newStringTable(modeStyleInsensitive)), "{:}")
        with self.assertRaises(KeyError):
            _ = ci[string("missing")]

    def test_int_enum_dollar_is_name(self):
        """Nim `$` of an enum member is its name: str(), echo and f-strings of an NIntEnum."""
        class _TColor(NIntEnum):
            red = 0
            green = auto()

        self.assertEqual(str(_TColor.green), "green")
        self.assertEqual(f"{_TColor.green}", "green")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            echo(_TColor.red, string(" "), nint(int(_TColor.green)))
        self.assertEqual(out.getvalue(), "red 1\n")

    def test_tuple_literal_result_is_named_tuple(self):
        """A proc declared to return a named tuple type gives that type for a returned tuple literal;
        os.splitPath gives (head, tail)."""
        class _TSplit(NTuple):
            head: string
            n: nint

        @dispatch
        def split2(s: string) -> _TSplit:
            return (s, nint(1))

        r = split2(string("a"))
        self.assertIsInstance(r, _TSplit)
        self.assertEqual((str(r.head), int(r.n)), ("a", 1))
        from nimic.std.os import splitPath
        sp = splitPath(string("/usr/local/bin"))
        from nimic.std.os import getAppDir, getAppFilename
        self.assertEqual(str(getAppDir()), os.path.dirname(os.path.abspath(sys.argv[0])))
        self.assertEqual((str(sp.head), str(sp.tail)), ("/usr/local", "bin"))

    def test_pairs(self):
        """Nim pairs: (index, item) of a seq, array or string; a table's own pairs."""
        sq = seq[nint]([nint(5), nint(6)])
        self.assertEqual([(int(i), int(x)) for i, x in pairs(sq)], [(0, 5), (1, 6)])
        self.assertIsInstance(next(iter(pairs(sq)))[0], nint)
        self.assertEqual([(int(i), str(c)) for i, c in pairs(string("ab"))], [(0, "a"), (1, "b")])
        from nimic.std.strtabs import newStringTable, modeCaseSensitive
        t = newStringTable(string("k"), string("v"), modeCaseSensitive)
        self.assertEqual([(str(k), str(v)) for k, v in pairs(t)], [("k", "v")])

    def test_ref_object_int_fields_hold_declared_type(self):
        """A plain int assigned to an integer field of a ref object becomes the declared type, so the
        field can be passed as a `var int` (and keeps its width)."""
        @ref
        class _TCounter(Object):
            n: nint
            small: int8

        def bump(x: mut@nint) -> None:
            x <<= x + 1

        c = _TCounter()
        c.n = 41
        self.assertIsInstance(c.n, nint)
        bump(c.n)
        self.assertEqual(int(c.n), 42)
        c.small = 5
        self.assertIsInstance(c.small, int8)
        self.assertIsInstance(_TCounter(n=3).n, nint)

    def test_transpile_push_pop(self):
        """rule:push: `with push("p"):` emits {.push p.}, the body at the same level, then {.pop.}."""
        src = textwrap.dedent('''\
            with push("overflowChecks: off"):
                def f(x: nint) -> nint:
                    return x * 2
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertRegex(out, r"\{\.push overflowChecks: off\.\}\n+proc f\*\(x: int\): int =\n  return x \* 2\n\{\.pop\.\}")

    def test_string_type_alias_dispatch(self):
        """rule:typealias: `class Snippet(string): pass` aliases string for dispatch (as numeric aliases do);
        a string subclass with members of its own (std/paths.Path) is no alias."""
        class TAliasSnippet(string):
            pass

        @dispatch
        def _t_alias_join(a: TAliasSnippet, b: TAliasSnippet) -> TAliasSnippet:
            return a + b

        self.assertEqual(str(_t_alias_join(string("a"), string("b"))), "ab")
        self.assertEqual(_n_aliases["TAliasSnippet"], "string")
        from nimic.std.paths import Path
        self.assertNotIn("Path", _n_aliases)

    def test_transpile_type_alias_assignment(self):
        """rule:typealias, assignment form: a module-level `Name = <type>` is a type alias."""
        src = textwrap.dedent('''\
            Snippet = string
            Rows = seq[Snippet]
            limit = 5
            def f(a: Snippet) -> Snippet:
                b = a
                return b
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("type\n  Snippet* = string\n  Rows* = seq[Snippet]", out)
        self.assertIn("limit = 5", out)
        self.assertIn("  b = a", out)

    def test_varargs_dispatch(self):
        """rule:varargs: `*args: T` takes any number of T (Nim varargs[T]); a varargs[T, conv] parameter
        converts each argument (str is Nim's `$`); overloads without varargs are preferred."""
        @dispatch
        def _t_va_call(callee: string, *args: string) -> string:
            result = callee + string("(")
            for i in range(len(args)):
                if i > 0:
                    result.add(string(", "))
                result.add(args[i])
            result.add(string(")"))
            return result

        @dispatch
        def _t_va_call(callee: string, n: nint) -> string:
            return string("fixed")

        self.assertEqual(str(_t_va_call(string("f"))), "f()")
        self.assertEqual(str(_t_va_call(string("f"), string("a"), string("b"))), "f(a, b)")
        self.assertEqual(str(_t_va_call(string("f"), nint(1))), "fixed")
        with self.assertRaises(NotImplementedError):
            _t_va_call(string("f"), nint(1), nint(2))

        @dispatch
        def _t_va_join(*args: varargs[string, str]) -> string:
            result = string("")
            for a in args:
                result.add(a)
            return result

        self.assertEqual(str(_t_va_join(string("n="), nint(3), True)), "n=3true")

    def test_transpile_varargs(self):
        """rule:varargs: `*args: T` -> `args: varargs[T]`; starred call arguments pass varargs on."""
        src = textwrap.dedent('''\
            def addCallStmt(builder: mut@Builder, callee: Snippet, *args: Snippet) -> None:
                addCall(builder, callee, *args)
            def log(*args: varargs[string, str]) -> None:
                echo(*args)
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("proc addCallStmt*(builder: var Builder, callee: Snippet, args: varargs[Snippet]) =", out)
        self.assertIn("  addCall(builder, callee, args)", out)
        self.assertIn("proc log*(args: varargs[string, `$`]) =", out)

    def test_dispatch_keywords_and_defaults_per_overload(self):
        """Keyword calls may omit defaulted parameters; a defaulted overload stays reachable when another
        overload has the call's arity (Nim overload resolution)."""
        class _TOvlKind(NIntEnum):
            kA = 0
            kB = auto()

        @dispatch
        def _t_ovl_var(b: string, kind: _TOvlKind = _TOvlKind.kA, name: string = string(""),
                       typ: string = string(""), init: string = string("")) -> string:
            return typ + string(" ") + name

        @dispatch
        def _t_ovl_var(b: string, m: nint, name: string = string(""), kind: _TOvlKind = _TOvlKind.kB) -> string:
            return string("module ") + name

        self.assertEqual(str(_t_ovl_var(string("b"), kind=_TOvlKind.kA, name=string("x"), typ=string("int"))), "int x")
        self.assertEqual(str(_t_ovl_var(string("b"), nint(1), name=string("y"))), "module y")
        with self.assertRaises(TypeError):
            _t_ovl_var(string("b"), noSuchParam=1)

        @dispatch
        def _t_ovl_err(info: nint, msg: _TOvlKind, arg: string = string("")) -> string:
            return string("kind")

        @dispatch
        def _t_ovl_err(info: nint, arg: string) -> string:
            return string("text")

        self.assertEqual(str(_t_ovl_err(nint(1), string("t"))), "text")
        self.assertEqual(str(_t_ovl_err(nint(1), _TOvlKind.kB)), "kind")
        self.assertEqual(str(_t_ovl_err(nint(1), _TOvlKind.kB, string("a"))), "kind")

    def test_dispatch_union_type_class(self):
        """A union annotation `A | B` (Nim `A or B`) is a type class for dispatch."""
        @dispatch
        def _t_union(lhs: string, rhs: string) -> string:
            return string("snippet")

        @dispatch
        def _t_union(lhs: string, rhs: int64 | uint64) -> string:
            return string("int")

        self.assertEqual(str(_t_union(string("x"), string("y"))), "snippet")
        self.assertEqual(str(_t_union(string("x"), uint64(5))), "int")
        with self.assertRaises(NotImplementedError):
            _t_union(string("x"), float64(1.0))

    def test_eq_overload_keeps_hash(self):
        """An overloaded `==` (__eq__) on an Object keeps it hashable, as Nim's `==` and `hash` are
        independent (idents.PIdent defines `==`)."""
        @ref
        class _TEqIdent(Object):
            id: nint

            def __eq__(a: _TEqIdent, b: _TEqIdent) -> bool:
                if a is None or b is None:
                    return a is b
                return a.id == b.id

        x, y = _TEqIdent(id=1), _TEqIdent(id=1)
        self.assertTrue(x == y)
        self.assertEqual(len({x, y}), 2)  # hashing is by identity, as for Nim refs

    def test_assign_and_when_expression(self):
        """assign(target, value) (rule:assigncall) assigns in place through a var-T result;
        `a if comptime(c) else b` is a when expression (rule:comptimeexpr)."""
        class _TAsgBuilder(Object):
            buf: string

        class _TAsgProc(Object):
            sections: array[2, _TAsgBuilder]

            def s(self, sec: nint) -> mut @ _TAsgBuilder:
                return self.sections[sec]

        p = _TAsgProc()
        old = p.s(1).copy()
        p.s(1).buf.add(string("loop"))
        assign(p.s(1), old)
        self.assertEqual(len(p.s(1).buf), 0)
        src = textwrap.dedent('''\
            x = a if comptime(isinstance(f, float32)) else b
            assign(p.s(cpsStmts), oldCode)
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("x = when f is float32: a else: b", out)
        self.assertIn("p.s(cpsStmts) = oldCode", out)

    def test_value_semantics_of_object_fields_and_elements(self):
        """Nim assignment copies values: copy(), `<<=`, a[i] = obj, s.add(str) don't alias strings, seqs
        or value objects; refs stay shared."""
        class _TValB(Object):
            buf: string
            n: int32

        class _TValP(Object):
            sections: array[2, _TValB]

        p = _TValP()
        old = p.sections[1].copy()
        p.sections[1].buf.add(string("loop"))
        self.assertEqual(str(old.buf), "")  # copy() didn't alias the string field
        p.sections[1] <<= old
        self.assertEqual(str(p.sections[1].buf), "")
        src = _TValB()
        src.buf = string("zz")
        p.sections[0] = src
        src.buf.add(string("!"))
        self.assertEqual(str(p.sections[0].buf), "zz")
        names = seq[string]()
        item = string("a")
        names.add(item)
        item.add(string("b"))
        self.assertEqual(str(names[0]), "a")

        @ref
        class _TValRef(Object):
            n: nint

        refs = seq[_TValRef]()
        r = _TValRef(n=1)
        refs.add(r)
        r.n = 2
        self.assertEqual(int(refs[0].n), 2)  # refs are shared

    def test_include_runs_in_includer_namespace(self):
        """include("x") (Nim `include x`): the file runs in the includer's namespace, sees the includer's
        and earlier includes' symbols, and may define templates and dispatched procs; transpiles to
        `include x`."""
        with tempfile.TemporaryDirectory() as d:
            files = {
                "host.py": '''# /// nimic
# ///
from __future__ import annotations
from nimic.ntypes import *

class Builder(Object):
    buf: string

include("first", "second")

if comptime(__name__ == "__main__"):
    with var:
        b = Builder()
    with addParens(b):
        addWord(b, string("x"))
    echo(b.buf, " ", kindName(Kind.kB))
''',
                "first.py": '''# /// nimic
# ///
from __future__ import annotations
from nimic.ntypes import *

class Kind(NIntEnum):
    kA = 0
    kB = auto()

@template
def addParens(b: mut@Builder, body: typed):
    b.buf.add(string("("))
    body
    b.buf.add(string(")"))
''',
                "second.py": '''# /// nimic
# ///
from __future__ import annotations
from nimic.ntypes import *

@dispatch
def kindName(k: Kind) -> string:
    return string("kind ") + string(str(ord(k)))

def addWord(b: mut@Builder, w: string) -> None:
    b.buf.add(w)
'''}
            for name, text in files.items():
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)
            env = dict(os.environ, PYTHONPATH=os.path.join(os.path.dirname(__file__), "..", "..", "src"))
            out = subprocess.run([sys.executable, os.path.join(d, "host.py")], capture_output=True, text=True, env=env)
            self.assertEqual(out.stdout, "(x) kind 1\n", out.stderr)
        src = textwrap.dedent('''\
            include("cbuilderexprs", "cbuilderstmts")
            ''')
        self.assertIn("include cbuilderexprs, cbuilderstmts", unparse(ast.parse(src))[0])

    def test_block_template_param_after_defaults(self):
        """A block template whose Nim signature has defaulted parameters before the block parameters
        (`kind: VarKind = Local, name: string, initializerBody: typed`) needs Python placeholder defaults;
        `= None` on a typed/untyped parameter is not written to Nim (rule:blockparam), and the block still
        binds by position in Python."""
        @template
        def _tAddVarInit(b: mut@string, kind: nint = nint(0), name: string = string(""),
                         initializerBody: typed = None):
            b.add(name)
            b.add(string(" = "))
            initializerBody
            b.add(string(";"))

        buf = string("")
        with _tAddVarInit(buf, name=string("x")):
            buf.add(string("1"))
        self.assertEqual(str(buf), "x = 1;")
        src = textwrap.dedent('''\
            @template
            def addVarWithInitializer(builder: mut@Builder, kind: VarKind = VarKind.Local, name: string = string(""),
                                      initializerBody: typed = None, other: untyped = None):
                initializerBody
            ''')
        self.assertIn("name: string = string(\"\"), initializerBody: typed, other: untyped) =", unparse(ast.parse(src))[0])

    def test_method_call_syntax_ufcs(self):
        """Nim method-call syntax: `obj.f(args)` calls a proc `f(obj, args)` visible in the caller's scope
        (module or local), including block templates (`with b.t(x):`); real attributes win."""
        class _TUfcsB(Object):
            buf: string

        def addWord(b: _TUfcsB, w: string) -> None:
            b.buf.add(w)

        @template
        def addParens(b: mut@_TUfcsB, body: typed):
            b.buf.add(string("("))
            body
            b.buf.add(string(")"))

        b = _TUfcsB()
        with b.addParens():
            b.addWord(string("x"))
        self.assertEqual(str(b.buf), "(x)")
        with self.assertRaises(AttributeError):
            b.noSuchProc()

    def test_to_float_to_int(self):
        """Nim toFloat(int): float and toInt(float): int (rounds half away from zero)."""
        self.assertEqual(toFloat(nint(3)), 3.0)
        self.assertIsInstance(toFloat(nint(3)), float)
        self.assertIsInstance(toInt(2.5), nint)
        self.assertEqual([int(toInt(x)) for x in (2.5, -2.5, 2.4, -0.6)], [3, -3, 2, -1])

    def test_echo_has_no_separator(self):
        """Nim echo writes $a & $b & ... (no separator), bools as true/false, nil as nil."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            echo(string("x = "), 5, True, ch("c"), None)
        self.assertEqual(buf.getvalue(), "x = 5truecnil\n")

    def test_shallow_copy_assigns_in_place(self):
        """shallowCopy(dest, src) assigns into dest (Nim); immutable destinations are rejected."""
        dest = seq[int32]()
        dest.add(int32(1))
        src = seq[int32]()
        src.add(int32(7))
        src.add(int32(8))
        shallowCopy(dest, src)
        self.assertEqual([int(x) for x in dest], [7, 8])
        text = string("old")
        shallowCopy(text, string("new"))
        self.assertEqual(str(text), "new")
        with self.assertRaises(TypeError):
            shallowCopy(5, 6)

    def test_os_build_dependent_constants(self):
        """FileSystemCaseSensitive follows the emulated OS like Nim's osseps; getCurrentCompilerExe is the
        nim compiler, not the Python interpreter."""
        from nimic.std.os import FileSystemCaseSensitive, getCurrentCompilerExe
        self.assertEqual(FileSystemCaseSensitive, not (defined("macosx") or defined("windows")))
        self.assertNotEqual(str(getCurrentCompilerExe()), sys.executable)

    # --- build profile: defined / declared (Nim conditional symbols) ---

    def test_defined_emulates_nim_build(self):
        """defined() reflects the emulated Nim build (C backend, host OS/CPU, ORC), never Python vs Nim."""
        profile = _BuildProfile(None, "")
        _n_set_build_profile(profile)
        try:
            self.assertTrue(defined("c"))
            self.assertFalse(defined("js"))
            self.assertTrue(defined(str(hostOS)))
            self.assertTrue(defined(str(hostCPU)))
            for sym in ("gcOrc", "gcDestructors", "nimV2"):
                self.assertTrue(defined(sym), sym)
            self.assertFalse(defined("gcArc"))
            self.assertFalse(defined("release"))
            self.assertFalse(defined("contextlib"))  # a Python global is not a Nim symbol
            self.assertTrue(defined("nimHasDefault"))  # compiler feature symbol (nim_defines.txt)
            self.assertTrue(defined("nim_has_default"))  # Nim identifier equality
            self.assertFalse(defined("NimHasDefault"))  # first character is case sensitive
        finally:
            _n_set_build_profile(None)

    def test_defined_extra_symbols_and_mm(self):
        """NIMIC_DEFINES-style extras define and undefine symbols; `danger` implies `release` through the
        global Nim config, exactly as `nim c -d:danger`."""
        profile = _BuildProfile(None, "danger, myFlag -gcOrc")
        self.assertTrue(profile.is_defined("danger"))
        self.assertTrue(profile.is_defined("myflag"))
        self.assertFalse(profile.is_defined("gcOrc"))
        if profile._config_files(None):  # the global config is found only when `nim` is installed
            self.assertTrue(profile.is_defined("release"))
        profile.set_mm("refc")
        self.assertTrue(profile.is_defined("gcRefc"))
        self.assertFalse(profile.is_defined("gcDestructors"))

    def test_defined_reads_project_nim_cfg(self):
        """nim.cfg files from the root down to the main module's directory are read with @if/@elif/@else."""
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "proj")
            os.mkdir(sub)
            with open(os.path.join(d, "nim.cfg"), "w") as f:
                f.write("define:outerFlag\n")
            with open(os.path.join(sub, "nim.cfg"), "w") as f:
                f.write(textwrap.dedent("""\
                    # comment
                    --define:fromProject
                    @if outerFlag and not windows:
                      d:nestedOk
                      @if js:
                        define:neverJs
                      @elif c:
                        define:cBranch
                      @else:
                        define:neverElse
                      @end
                    @end
                    @if undefinedSym:
                      define:neverDefined
                    @else:
                      define:elseTaken
                    @end
                    mm:arc
                    """))
            with open(os.path.join(sub, "main.nim.cfg"), "w") as f:
                f.write("undef:fromProject\n")
            profile = _BuildProfile(os.path.join(sub, "main.py"), "")
            for sym in ("outerFlag", "cBranch", "elseTaken", "gcArc"):
                self.assertTrue(profile.is_defined(sym), sym)
            self.assertEqual(profile.is_defined("nestedOk"), str(hostOS) != "windows")
            for sym in ("neverJs", "neverElse", "neverDefined", "fromProject", "gcOrc"):
                self.assertFalse(profile.is_defined(sym), sym)

    def test_declared_looks_up_caller_scope(self):
        """declared("x") checks the caller's locals, globals (incl. star-imports) and builtins."""
        local_name = 1
        self.assertTrue(declared("local_name"))
        self.assertTrue(declared("unittest"))           # module global of the caller
        self.assertTrue(declared("seq"))                # star-imported nimic name
        self.assertTrue(declared("os.path.join"))       # dotted
        self.assertFalse(declared("os.path.noSuchProc"))
        self.assertFalse(declared("noSuchName"))
        self.assertTrue(declared("system.getMaxMem"))   # Nim's system module: nimic's system procs
        self.assertFalse(declared("system.noSuchProc"))

    def test_hashes_nim_algorithm(self):
        """std/hashes `!&` (mix_hash), `!$` (finish_hash) and hashIgnoreStyle compute Nim's values (64-bit
        wrapping, unsigned shifts), so a hash built char by char (the lexer) matches hashIgnoreStyle (idents).
        Expected values from Nim 2.2."""
        self.assertEqual(hashIgnoreStyle(string("abracadabra")), -5600162842546114722)
        self.assertEqual(hashIgnoreStyle(string("aBr_aCa_dAB_ra")), -5600162842546114722)
        self.assertEqual(hashIgnoreStyle(string("")), 0)
        self.assertEqual(hashIgnoreStyle(string("Lexer")), 4924223376909363949)
        h = mix_hash(Hash(0), ord(ch("x")))
        self.assertEqual(h, 124921)
        self.assertIsInstance(h, Hash)
        self.assertEqual(finish_hash(h), 36826228197)
        self.assertEqual(mix_hash(Hash(0), -1), -288230376151710704)
        with var:
            h2: Hash = Hash(0)
        for c in "lexer":
            h2 = mix_hash(h2, ord(ch(c)))
        self.assertEqual(finish_hash(h2), hashIgnoreStyle(string("Lexer")))

    def test_hash_is_an_int_alias(self):
        """std/hashes `Hash` is Nim's `type Hash* = int`: an alias of nint, so hashes are nint values,
        `cast[Hash](x)` reinterprets 64 bits, `Hash(0) + 1` is int arithmetic and a proc taking `Hash` takes
        an nint (and the reverse)."""
        self.assertIs(Hash, nint)
        self.assertIsInstance(nhash(string("abc")), nint)
        self.assertEqual(cast[Hash](u64(0x9E3779B97F4A7C15)), -7046029254386353131)
        self.assertEqual(Hash(5) + 1, 6)

        @dispatch
        def takes_hash(h: Hash) -> nint:
            return h + 1

        self.assertEqual(takes_hash(nint(41)), 42)
        self.assertEqual(takes_hash(nhash(string("x"))), nhash(string("x")) + 1)

    def test_transpile_hash_operators(self):
        """rule:percentops -> std/hashes' operators spelled as calls: mix_hash(h, v) is `h !& v`,
        finish_hash(h) is `!$h`."""
        out = unparse(ast.parse("h = mix_hash(h, ord(c))\nh = finish_hash(h)\nx = finish_hash(mix_hash(0, 1))\n"))[0]
        self.assertIn("h = h !& ord(c)", out)
        self.assertIn("h = !$h", out)
        self.assertIn("x = !$(0 !& 1)", out)

    def test_ashr(self):
        """Nim: ashr(x, y) — arithmetic shift right of a signed integer, in x's type (values from Nim 2.2)."""
        self.assertEqual(ashr(int64(-256), 4), -16)
        self.assertIsInstance(ashr(int64(-256), 4), int64)
        self.assertEqual(ashr(int8(-128), 1), -64)
        self.assertIsInstance(ashr(int8(-128), 1), int8)
        self.assertEqual(ashr(int16(100), 2), 25)
        self.assertEqual(ashr(int64(0xF0) << 56, 56), -16)
        self.assertEqual(ashr(int64(0x7F) << 56, 56), 127)
        self.assertIn("ashr(x shl 56, 56)", unparse(ast.parse("y = ashr(x << 56, 56)\n"))[0])

    def test_reset(self):
        """Nim: reset(x) — x becomes default(typeof(x)), in place (objects, strings, integers, enums)."""
        class _TRs(Object):
            n: int64
            s: string
        with var:
            o = _TRs(n=int64(5), s=string("ab"))
            alias = o
            i = int64(7)
            st = string("xyz")
        reset(o)
        self.assertEqual(o.n, 0)
        self.assertEqual(o.s, string(""))
        self.assertIs(alias, o)
        reset(i)
        self.assertEqual(i, 0)
        reset(st)
        self.assertEqual(st, string(""))
        self.assertIn("reset(o)", unparse(ast.parse("reset(o)\n"))[0])

    def test_backwards_index(self):
        """Nim: s[^n] — the n-th element from the end; nimic spells ^n as back(n) (rule:namedops). A plain
        negative index stays an IndexDefect, as in Nim."""
        with var:
            s = string("abc")
            q = seq[int32]([int32(1), int32(2), int32(3)])
            a = array[3, int32]([int32(4), int32(5), int32(6)])
        self.assertEqual(s[back(1)], ch("c"))
        self.assertEqual(s[back(3)], ch("a"))
        self.assertEqual(q[back(1)], 3)
        self.assertEqual(a[back(2)], 5)
        s[back(1)] = ch("z")
        q[back(1)] = int32(9)
        a[back(1)] = int32(7)
        self.assertEqual(s, string("abz"))
        self.assertEqual(q[2], 9)
        self.assertEqual(a[2], 7)
        self.assertEqual(len(openArray(q)), 3)  # not the seq's capacity
        self.assertEqual(openArray(q)[back(2)], 2)
        self.assertIsInstance(back(1), BackwardsIndex)
        with self.assertRaises(IndexDefect):
            q[back(4)]
        with self.assertRaises(IndexDefect):
            a[-1]
        out = unparse(ast.parse("c = s[back(1)]\nd = s[back(n + 1)]\n"))[0]
        self.assertIn("c = s[^1]", out)
        self.assertIn("d = s[^(n + 1)]", out)

    def test_parse_biggest_int_uint_float(self):
        """std/parseutils parseBiggestInt / parseBiggestUInt and std/strutils parseFloat (values from Nim 2.2):
        the number of chars parsed, 0 (number untouched) without digits, ValueError out of range."""
        with var:
            r = BiggestInt(7)
            u = uint64(3)
        self.assertEqual(parseBiggestInt(string("9223372036854775807"), r), 19)
        self.assertEqual(r, 9223372036854775807)
        self.assertEqual(parseBiggestInt(string("-2024_05_09"), r), 11)
        self.assertEqual(r, -20240509)
        r <<= BiggestInt(7)
        self.assertEqual(parseBiggestInt(string("abc"), r), 0)
        self.assertEqual(r, 7)
        self.assertEqual(parseBiggestInt(string("x12"), r, 1), 2)
        self.assertEqual(r, 12)
        self.assertEqual(parseBiggestInt(string("-9223372036854775808"), r), 20)
        self.assertEqual(r, -9223372036854775808)
        with self.assertRaises(ValueError):
            parseBiggestInt(string("9223372036854775808"), r)
        self.assertEqual(parseBiggestUInt(string("18446744073709551615"), u), 20)
        self.assertEqual(u, 18446744073709551615)
        with self.assertRaises(ValueError):
            parseBiggestUInt(string("18446744073709551616"), u)
        with self.assertRaises(ValueError):
            parseBiggestUInt(string("-1"), u)
        self.assertEqual(parseFloat(string("1_000.5e3")), 1000500.0)
        self.assertIsInstance(parseFloat(string("0.1")), float64)
        with self.assertRaises(ValueError):
            parseFloat(string("x"))

    def test_chr_rangedefect_natural(self):
        """Nim: chr(i) is a char (RangeDefect above 255); RangeDefect is a Defect, not a ValueError (the lexer
        catches ValueError before RangeDefect); Natural / Positive and Trange[a, b] annotate range types."""
        self.assertIsInstance(chr(65), char)
        self.assertEqual(chr(nint(97)), ch("a"))
        with self.assertRaises(RangeDefect):
            chr(256)
        self.assertTrue(issubclass(RangeDefect, Defect))
        self.assertFalse(issubclass(RangeDefect, ValueError))
        out = unparse(ast.parse("def m(chars: Tset[char], p: Trange[0, 4]) -> Natural:\n    pass\n"))[0]
        self.assertIn("proc m*(chars: set[char], p: range[0 .. 4]): Natural", out)

    def test_transpile_except_several(self):
        """`except (A, B):` is Nim's `except A, B:`."""
        out = unparse(ast.parse("try:\n    f()\nexcept (OverflowDefect, RangeDefect):\n    g()\n"))[0]
        self.assertIn("except OverflowDefect, RangeDefect:", out)

    def test_nintenum_auto_starts_at_zero(self):
        """A Nim enum's first member is 0: NIntEnum's auto() counts from 0 (and from the previous value),
        so default(E) and a zeroed object field are the first member."""
        class _E(NIntEnum):
            a = auto()
            b = auto()
            c = 10
            d = auto()
        self.assertEqual([int(_E.a), int(_E.b), int(_E.c), int(_E.d)], [0, 1, 10, 11])
        self.assertIs(default(_E), _E.a)

        class _O(Object):
            k: _E
        self.assertIs(_O().k, _E.a)

    def test_cast_pointer_to_cstring(self):
        """cast[cstring](addr(buf[i])) is a cstring into the middle of a buffer (Nim's char*): it reads and
        writes the same memory from offset i (the lexer hands identifiers to getIdent this way)."""
        with var:
            s = string("hello world")
            c = cstring(s)
        tail = cast[cstring](addr(c[6]))
        self.assertEqual(str(tail), "world")
        self.assertEqual(tail[0], ch("w"))
        tail[0] = ch("W")
        self.assertEqual(s, string("hello World"))
        self.assertIn("cast[cstring](addr(c[6]))", unparse(ast.parse("t = cast[cstring](addr(c[6]))\n"))[0])

    def test_succ_pred_char(self):
        """Nim: succ/pred of a char (`'\\0'..pred(' ')` in the lexer); RangeDefect past '\\xFF' or below '\\0'."""
        self.assertEqual(pred(ch(" ")), ch("\x1f"))
        self.assertEqual(succ(ch("a"), 2), ch("c"))
        self.assertIsInstance(succ(ch("a")), char)
        self.assertTrue(ch("\x05") in inrange(ch("\0"), pred(ch(" "))))
        with self.assertRaises(RangeDefect):
            pred(ch("\0"))

    def test_dollar_of_containers(self):
        """Nim `$` of a set, seq and array (collectionToString): elements in order (a set by ordinal), strings
        and chars quoted with Nim's escapes (addQuoted). Expected texts from Nim 2.2."""
        class _E(NIntEnum):
            ea = auto()
            eb = auto()
            ec = auto()
        self.assertEqual(str(Tset[_E]({_E.ec, _E.ea})), "{ea, ec}")
        self.assertEqual(str(Tset[char]({ch("b"), ch("a"), ch("\n"), ch("'")})), "{'\\n', '\\'', 'a', 'b'}")
        self.assertEqual(str(Tset[_E]()), "{}")
        self.assertEqual(str(seq[nint]([nint(1), nint(2), nint(3)])), "@[1, 2, 3]")
        self.assertEqual(str(seq[string]([string('a"b'), string("c")])), '@["a\\"b", "c"]')
        self.assertEqual(str(array[2, int8]([int8(1), int8(2)])), "[1, 2]")
        self.assertEqual(str(seq[char]([ch("x"), ch("\t"), ch("\xF0")])), "@['x', '\\t', '\\xF0']")
        self.assertEqual(str(seq[float64]([float64(1.5), float64(2.0)])), "@[1.5, 2.0]")
        self.assertEqual(str(seq[nint]()), "@[]")

    def test_addr_of_local_scalar(self):
        """addr(x) of a local integer/float (Nim: every variable has an address): the scalar gets storage of its
        own, so a pointer reads and writes it, also reinterpreted (`cast[ptr float32](addr(xi))[]`)."""
        with var:
            xi = BiggestInt(0x3F800000)
        self.assertEqual(cast[ptr[float32]](addr(xi)).contents, 1.0)
        with var:
            p = addr(xi)
        xi += 1
        self.assertEqual(p.contents, 0x3F800001)
        p.contents = BiggestInt(7)
        self.assertEqual(xi, 7)
        self.assertIsInstance(xi, BiggestInt)
        with var:
            f = float64(2.5)
        self.assertEqual(addr(f).contents, 2.5)

    def test_transpile_strformat_typed_names(self):
        """rule:strformat -> `%` is Nim's format operator when the left operand is a string: a literal, a
        string(...) call, or a name declared as string / FormatStr in the scope (parameter, annotated or
        string(...)-assigned variable); otherwise it is `mod`."""
        src = textwrap.dedent('''\
            def f(msg: string, n: nint, m: mut @ string) -> string:
                with var:
                    t: string = string("x")
                    u = string("$1")
                    k = n % 3
                a = msg % t
                b = m % t
                c = u % t
                return a
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("a = msg % t", out)
        self.assertIn("b = m % t", out)
        self.assertIn("c = u % t", out)
        self.assertIn("k = n mod 3", out)

    def test_transpile_dollar_as_base(self):
        """rule:dollarparens -> `$` is a prefix operator: str(x)[a:b] / str(x).len are ($(x))[a..<b] /
        ($(x)).len, not $(x[...])."""
        out = unparse(ast.parse("h = str(L.buf)[s:e]\nn = str(x).len\nm = str(x) + y\n"))[0]
        self.assertIn("h = ($(L.buf))[s..<e]", out)
        self.assertIn("n = ($(x)).len", out)
        self.assertIn("m = $(x) + y", out)

    def test_cast_python_number(self):
        """cast[T](x) of a plain Python number treats it as a Nim literal (int / float64)."""
        self.assertEqual(cast[uint8](200), 200)
        self.assertIsInstance(cast[uint8](200), uint8)
        self.assertEqual(cast[uint8](300), 44)  # the low byte, as Nim on a little-endian machine
        self.assertEqual(cast[int64](1.0), 0x3FF0000000000000)

    def test_internal_names_dont_collide(self):
        """nimic's internal hooks are `_n_` names: user enum members and fields may be called first, last,
        cast, ..., and low/high/cast/inrange still work."""
        class _E(NStrEnum):
            first = "a"
            last = "b"
            nitems = "c"
        self.assertIs(low(_E), _E.first)
        self.assertIs(high(_E), _E.nitems)
        self.assertEqual(list(inrange(_E.first, _E.last)), [_E.first, _E.last])

        class _O(Object):
            cast: int32
            first: int32
        with var:
            o = _O(cast=int32(1), first=int32(2))
        self.assertEqual(o.cast, 1)
        self.assertEqual(cast[ptr[_O]](addr(o)).contents.first, 2)

    def test_transpile_case_expression(self):
        """rule:caseassign -> a match inside `with let:`/`with var:` whose every branch ends by assigning the
        same name (or raises) is that name's Nim case expression: `let x = case s of ...: v`."""
        src = textwrap.dedent('''\
            def f(base: Base) -> nint:
                with let:
                    match base:
                        case Base.base2:
                            bitsPerDigit = 1
                        case Base.base8:
                            bitsPerDigit = 3
                        case _:
                            raiseAssert(string("unreachable"))
                return bitsPerDigit
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("  let\n    bitsPerDigit = case base\n      of Base.base2:\n        1\n"
                      "      of Base.base8:\n        3\n      else:\n        raiseAssert(string(\"unreachable\"))", out)
        # not every branch assigns the same name: an ordinary case statement
        src2 = textwrap.dedent('''\
            with var:
                match k:
                    case 1:
                        a = 1
                    case _:
                        b = 2
            ''')
        self.assertIn("case k", unparse(ast.parse(src2))[0])
        self.assertNotIn("= case", unparse(ast.parse(src2))[0])

    def test_transpile_private_names(self):
        """rule:localname: a private _x keeps its Nim name x, unexported (procs, overloads of public procs,
        templates, fields, types, module variables); __x and _1 keep the local_ prefix. rule:privatepragma
        keeps an operator unexported."""
        src = textwrap.dedent('''\
            class _T(Object):
                _a: int32
                b: int32
            def _abs(a: int32) -> nint:
                return nint(a)
            def abs(a: _T) -> _T:
                return a
            @ufcs(_T)
            @dispatch
            def __mul__(a: _T, b: uint32) -> _T:
                """{.private, inline.}"""
                return a
            with var:
                _x = 1
                __y = 2
                t = _T(_a=int32(1), b=int32(2))
            type _P = int32
            type Q = int32 | int64
            class _E(byte): pass
            class S(seq[_E]): pass
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("T(a: int32(1), b: int32(2))", out)
        self.assertIn("type P = int32", out)
        self.assertIn("type Q* = int32 or int64", out)
        self.assertIn("S* = seq[E]", out)
        self.assertIn("T = object", out)
        self.assertNotIn("T* =", out)
        self.assertIn("a: int32", out)
        self.assertIn("b*: int32", out)
        self.assertIn("proc abs(a: int32): int", out)
        self.assertIn("proc abs*(a: T): T", out)
        self.assertIn("proc `*`(a: T, b: uint32): T {.inline.}", out)
        self.assertIn("x = 1", out)
        self.assertIn("local__y = 2", out)

    def test_private_name_collisions(self):
        """rule:localname: modules where dropping the _ of a private name changes meaning are rejected."""
        def collisions(src):
            return [msg for _, _, msg in private_name_collisions(ast.parse(textwrap.dedent(src)))]
        # overloads and Nim's `let base = f(base)` shadowing a parameter are fine
        self.assertEqual(collisions('''\
            def _f(a: int32): pass
            def f(a: int64): pass
            def g(base: int32):
                with let:
                    _base = f(base)
                return _base
            '''), [])
        # a variable defined twice
        self.assertEqual(collisions('''\
            with var:
                x = 1
                _x = 2
            '''), ["_x and x are both defined"])
        # a field and a method of the same name
        self.assertEqual(collisions('''\
            class T(Object):
                _a: int32
                def a(self): pass
            '''), ["_a and a are both defined"])
        # a parameter _a doesn't hide the proc a in a call (Nim's `var a = a(1)`), but does as a value
        self.assertEqual(collisions('''\
            def g(_a: int32):
                return a(_a)
            '''), [])
        self.assertEqual(collisions('''\
            def g(_a: int32):
                return h(a)
            '''), ["a is used after _a, which transpiles to a"])
        # a parameter used after a private local shadows it
        self.assertEqual(collisions('''\
            def g(base: int32):
                with let:
                    _base = base + 1
                return base
            '''), ["base is used after _base, which transpiles to base"])
        tree = ast.parse("with var:\n    x = 1\n    _x = 2\n")
        with self.assertRaises(ValueError):
            check_private_names(tree)
        unparse(tree)  # unparse() itself only unparses

    def test_transpile_defined_declared(self):
        """rule:defined / rule:declared strip the quotes."""
        src = textwrap.dedent('''\
            if comptime(not declared("signbit") and defined("gcOrc")):
                pass
            ''')
        self.assertIn("when not declared(signbit) and defined(gcOrc):", unparse(ast.parse(src))[0])

    def test_transpile_mut_return_type(self):
        """rule:funcdefmut: `mut @ T` is `var T` for parameters, return types and calltype signatures."""
        src = textwrap.dedent('''\
            def s(self: BProc, sec: nint) -> mut @ Builder:
                return self.sections[sec]
            ''')
        self.assertIn("proc s*(self: BProc, sec: int): var Builder =", unparse(ast.parse(src))[0])
        cb = textwrap.dedent('''\
            @calltype
            def Cb(b: mut @ Builder) -> mut @ Builder: ...
            ''')
        self.assertIn("Cb* = proc(b: var Builder): var Builder", unparse(ast.parse(cb))[0])

    def test_transpile_var_init_ref_vs_value(self):
        """rule:varini: `with var: x = T()` declares `var x: T` for registered value types, but a
        ref type (registered or @ref in the module) must allocate: `var x = T()`."""
        @ref
        class TVarRef(Object):
            x: nint

        class TVarValue(Object):
            x: nint

        src = textwrap.dedent('''\
            @ref
            class LocalRef(Object):
                x: nint

            with var:
                a = TVarRef()
                b = TVarValue()
                c = LocalRef()
            ''')
        out = unparse(ast.parse(src), _n_registry)[0]
        self.assertIn("a* = TVarRef()", out)
        self.assertIn("b*: TVarValue", out)
        self.assertIn("c* = LocalRef()", out)

    def test_transpile_for_loop_targets(self):
        """rule:fortupleunpack: Python item unpacking is Nim `for (a, b) in xs` (bare would mean
        index + item); Nim's magic fields(a, b) / fieldPairs(x) yield separate values: bare names."""
        def nim(src):
            return unparse(ast.parse(src))[0].strip()
        self.assertEqual(nim("for name, val in [(a, 1), (b, 2)]:\n    pass"),
                         "for (name, val) in [(a, 1), (b, 2)]:\n  discard")
        self.assertEqual(nim("for dst, src in fields(u, v):\n    pass"), "for dst, src in fields(u, v):\n  discard")
        self.assertEqual(nim("for name, val in fieldPairs(u):\n    pass"), "for name, val in fieldPairs(u):\n  discard")
        self.assertEqual(nim("for x in s:\n    pass"), "for x in s:\n  discard")

    def test_transpile_inplace_operator(self):
        """rule:funcdefinplace: __iadd__ etc. become `+=` procs without a return type or `return self`;
        other __i...__ dunders (e.g. __invert__/__iter__) are not in-place operators."""
        src = textwrap.dedent('''
            class V(Object):
                x: float64

                def __iadd__(u: mut @ V, v: V):
                    u.x += v.x
                    return u
        ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("proc `+=`*(u: var V, v: V) =", out)
        self.assertNotIn("return u", out)
        self.assertNotIn("result = u", out)

    def test_transpile_template_return(self):
        """rule:templatereturn: nested `return x` is the value of a typed template, but a real
        `return` (leaving the caller) in an untyped statement template, as in Nim."""
        typed = textwrap.dedent('''
            @template
            def pick(c: bool, a: int, b: int) -> int:
                if c:
                    return a
                else:
                    return b
        ''')
        out = unparse(ast.parse(typed))[0]
        self.assertIn("    a\n", out)
        self.assertNotIn("return a", out)
        stmt = textwrap.dedent('''
            @template
            def checkSol(root: untyped) -> untyped:
                """{.dirty.}"""
                if root > 0:
                    return True
        ''')
        self.assertIn("return true", unparse(ast.parse(stmt))[0])
        # an untyped template whose if/else returns on every path is an expression template
        expr = textwrap.dedent('''
            @template
            def containsOrIncl(s: untyped, val: untyped) -> untyped:
                if val in s:
                    return True
                else:
                    incl(s, val)
                    return False
        ''')
        out = unparse(ast.parse(expr))[0]
        self.assertNotIn("return", out)
        self.assertIn("    true\n", out)

    def test_transpile_array_literals(self):
        """rule:array types the first element of an array[N, T](...) call; the declaration form
        `x: array[N, T] = [...]` is only used for a variable being declared."""
        def nim(src):
            return unparse(ast.parse(src))[0].strip()
        self.assertEqual(nim("x.s[0:4] = array[4, byte]([0, 0, 0, 1])"),
                         "x.s[0..<4] = array[4, byte]([byte(0), 0, 0, 1])")
        self.assertEqual(nim("with var:\n    a = array[4, byte]([0, 0, 0, 1])"),
                         "var\n  a*: array[4, byte] = [0, 0, 0, 1]")
        self.assertEqual(nim("f(array[2, float64]([1.0, 2.0]))"), "f(array[2, float64]([float64(1.0), 2.0]))")
        # where the field or the annotation gives the type, the array is the bare literal, as Nim writes it
        self.assertEqual(nim("R(p=array[3, K]([K.a, K.b, K.c]), n=1)"), "R(p: [K.a, K.b, K.c], n: 1)")
        self.assertEqual(nim("R(q=array[2, byte]([1, 2]))"), "R(q: [1, 2])")
        self.assertEqual(nim('with const:\n    X: array[K, string] = array[K, string]([string("a"), "b"])'),
                         'const\n  X*: array[K, string] = [string("a"), "b"]')
        # elsewhere the conversion carries the index type; a numeric first element takes the element type
        self.assertEqual(nim("f(array[2, int8]([-1, 2]))"), "f(array[2, int8]([int8(-1), 2]))")
        self.assertEqual(nim("g(x=array[2, byte]([1, 2]))"), "g(x = array[2, byte]([byte(1), 2]))")
        self.assertEqual(nim("f(array[2, ptr[nint]]([p, q]))"), "f(array[2, ptr int]([p, q]))")
        self.assertEqual(nim("f(array[2, bool]([True, False]))"), "f(array[2, bool]([true, false]))")

    def test_enum_array_field(self):
        """An array[N, E] field of a C-backed object (E an NIntEnum): its slots hold the ordinals and a
        read is the member (enums implement the slot protocol _n_on_array / _n_on_struct)."""
        class Ek(NIntEnum):
            ekA = auto()
            ekB = auto()
            ekC = auto()

        class Er(Object):
            p: array[3, Ek]
            n: nint

        self.assertEqual(Er().p[0], Ek.ekA)  # the default
        a = array[3, Ek]([Ek.ekB, Ek.ekC, Ek.ekA])
        r = Er(p=a)  # a constructor copies the array into the field
        self.assertIs(r.p[1], Ek.ekC)
        self.assertEqual(str(r.p), "[ekB, ekC, ekA]")
        self.assertEqual(r.p, a)
        r.p[0] = Ek.ekC  # a slot store changes the field, not the array it was built from
        r.p[0] = Ek.ekA
        self.assertEqual(str(r.p), "[ekA, ekC, ekA]")
        self.assertEqual(str(a), "[ekB, ekC, ekA]")
        self.assertEqual(str(r.copy().p), "[ekA, ekC, ekA]")
        self.assertEqual(str(a.copy()), "[ekB, ekC, ekA]")  # a standalone array copies its slots too
        self.assertEqual(seq[Ek]([Ek.ekB]), seq[Ek]([Ek.ekB]))

    def test_array_and_seq_equality(self):
        """Nim `==` of arrays and seqs compares the elements (system.`==`); hash stays independent."""
        self.assertEqual(array[3, nint]([1, 2, 3]), array[3, nint]([1, 2, 3]))
        self.assertNotEqual(array[3, nint]([1, 2, 3]), array[3, nint]([1, 2, 4]))
        self.assertEqual(array[2, string]([string("a"), string("b")]), array[2, string]([string("a"), string("b")]))
        self.assertEqual(seq[nint]([1, 2]), seq[nint]([1, 2]))
        self.assertNotEqual(seq[nint]([1, 2]), seq[nint]([1, 2, 3]))
        self.assertNotEqual(seq[nint]([1, 2]), seq[nint]([2, 1]))
        self.assertEqual(seq[string]([]), seq[string]([]))
        self.assertTrue(seq[nint]([1]) != seq[nint]([2]))
        s = seq[nint]([1])
        self.assertEqual(len({id(s): s}), 1)  # still hashable (identity), as objects

    def test_move_resets_source(self):
        """Nim's move(x) leaves x as default(T) (string, seq, array, object, scalars); the result holds the
        value. A ref is returned as it is: Python can't nil the variable, and the object is shared."""
        a = string("abc")
        s = seq[string]()
        s.add(move(a))
        self.assertEqual((a, s), (string(""), seq[string]([string("abc")])))
        q = seq[nint]([1, 2])
        q2 = move(q)
        self.assertEqual((len(q), q2), (0, seq[nint]([1, 2])))

        class Mo(Object):
            s: string
            n: nint
        o = Mo(s=string("x"), n=nint(5))
        o2 = move(o)
        self.assertEqual((o.s, o.n, o2.s, o2.n), (string(""), 0, string("x"), 5))
        i = nint(3)
        j = move(i)
        self.assertEqual((i, j), (0, 3))

        @ref
        class Mr(Object):
            n: nint
        r = Mr(n=nint(4))
        self.assertIs(move(r), r)
        self.assertEqual(r.n, 4)

    def test_catchable_error(self):
        """Nim's CatchableError: `except CatchableError:` catches the errors nimic raises for Nim's IOError /
        OSError, ValueError, KeyError, EOFError and its own subclasses, not Defects (nor Python bugs)."""
        def caught(exc) -> bool:
            try:
                raise exc
            except CatchableError:
                return True
            except BaseException:
                return False
        for exc in (OSError("x"), IOError("x"), ValueError("x"), KeyError("x"), EOFError("x"),
                    newException(CatchableError, "x")):
            self.assertTrue(caught(exc), exc)
        for exc in (IndexDefect("x"), RangeDefect("x"), AssertionError("x"), AttributeError("x"), TypeError("x")):
            self.assertFalse(caught(exc), exc)

        class MyError(CatchableError):
            pass
        e = newException(MyError, "mine")
        self.assertTrue(caught(e))
        self.assertEqual(e.msg, "mine")
        self.assertTrue(isinstance(e, CatchableError) and isinstance(OSError(), CatchableError))
        self.assertFalse(isinstance(IndexDefect(), CatchableError))
        out = unparse(ast.parse("class MyError(CatchableError):\n    pass\ntry:\n    f()\nexcept CatchableError:\n    pass\n"))[0]
        self.assertIn("MyError* = object of CatchableError", out)
        self.assertIn("except CatchableError:", out)

    def test_delete(self):
        """Nim's delete: strutils delete(s, a..b) of a string, system delete(s, i) and sequtils
        delete(s, a..b) of a seq; the order is kept, an out-of-range slice raises IndexDefect."""
        a = string("abcde")
        with self.assertRaises(IndexDefect):
            a.delete(inrange(4, 5))
        self.assertEqual(a, string("abcde"))
        delete(a, inrange(4, 4))
        self.assertEqual(a, string("abcd"))
        a.delete(inrange(1, 2))
        self.assertEqual(a, string("ad"))
        a.delete(range(1, 1))  # an empty slice (1 ..< 1)
        self.assertEqual(a, string("ad"))
        for s in (seq[nint]([1, 2, 3, 4, 5]), seq[string]([string(c) for c in "12345"])):
            T = s._n_type
            s.delete(2)
            self.assertEqual(s, seq[T]([T(x) for x in (1, 2, 4, 5)] if T is nint else [string(x) for x in "1245"]))
            delete(s, inrange(0, 1))
            self.assertEqual(len(s), 2)
            self.assertEqual(str(s[0]), "4")
            with self.assertRaises(IndexDefect):
                s.delete(2)
            with self.assertRaises(IndexDefect):
                s.delete(inrange(1, 2))

        class Dp(Object):
            x: nint
            y: float64
        ps = seq[Dp]([Dp(x=1), Dp(x=2), Dp(x=3)])
        first = ps[0]
        ps.delete(1)
        self.assertEqual([p.x for p in ps], [1, 3])
        self.assertIs(ps[0], first)

    def test_enum_field_store_keeps_members_shared(self):
        """Storing an enum field doesn't attach accessors to the member (a shared singleton): a store into
        one object never writes the C storage of another holding the same member."""
        class Fk(NIntEnum):
            fkA = auto()
            fkB = auto()
            fkC = auto()

        class Fr(Object):
            k: Fk
            n: nint

        r1, r2 = Fr(k=Fk.fkB), Fr(k=Fk.fkB)
        r1.k = Fk.fkC
        self.assertIs(r2.k, Fk.fkB)
        self.assertEqual(r2._n_view.k, Fk.fkB.ord())
        self.assertNotIn("_n_set_value", Fk.fkB.__dict__)
        arr = array[2, Fr]([r1, r2])  # the copy reads the C storage
        self.assertEqual((arr[0].k, arr[1].k), (Fk.fkC, Fk.fkB))

    def test_transpile_try_expressions(self):
        """rule:tryassign: a try in `with let:` / `with var:` whose branches all assign one name is that name's
        try expression; rule:tryreturn: a body ending with a try whose branches all return is one."""
        def nim(src):
            return unparse(ast.parse(textwrap.dedent(src)))[0]
        out = nim('''
            def f(dir: string) -> string:
                with let:
                    try:
                        expanded = expandFilename(dir)
                    except:
                        expanded = dir
                return expanded
        ''')
        self.assertIn("  let\n    expanded = try:\n        expandFilename(dir)\n      except:\n        dir\n", out)
        out = unparse(ast.parse(textwrap.dedent('''
            def o(filename: string) -> VfsBlob:
                with let:
                    try:
                        f = vfsOpenMmap(filename)
                    except:
                        if comptime(defined("debug")):
                            writeStackTrace()
                        quit(string("[Error] cannot open: ") + filename)
                return f
        ''')), _n_registry)[0]  # a handler may end with a call of a {.noreturn.} proc: system's quit (the registry)
        self.assertIn("  let\n    f = try:\n        vfsOpenMmap(filename)\n      except:\n"
                      "        when defined(debug):\n          writeStackTrace()\n        quit(", out)
        out = nim('''
            def fail():
                \"\"\"{.noinline, noreturn.}\"\"\"
                quit(string("bad"))

            def p(s: string) -> nint:
                with let:
                    try:
                        n = parseInt(s)
                    except ValueError:
                        fail()
                return n
        ''')  # or of the module's own (no registry here: system's quit is unknown)
        self.assertIn("    n = try:\n        parseInt(s)\n      except ValueError:\n        fail()", out)
        out = nim('''
            def g(p: string) -> int64:
                try:
                    with let:
                        t = getTime()
                    return toUnix(t)
                except OSError:
                    return i64(0)
        ''')
        self.assertIn("  try:\n    let\n      t = getTime()\n    toUnix(t)\n  except OSError:\n    0'i64", out)
        self.assertNotIn("return", out)
        out = nim('''
            def h(p: string) -> MemFile:
                try: return memfiles.open(p)
                except: quit(string("vfs: open failed: ") + p)
        ''')
        self.assertIn("  try:\n    return memfiles.open(p)\n  except:\n    quit(", out)  # a call ends no branch
        # not a try expression: a branch that doesn't assign / return, or a finally
        out = nim('''
            def k(p: string) -> bool:
                try:
                    return f(p)
                finally:
                    g()
        ''')
        self.assertIn("return f(p)", out)
        out = nim('''
            with var:
                try:
                    x = f()
                except:
                    log()
        ''')
        self.assertNotIn("= try", out)

    def test_proc_variable(self):
        """rule:procvar: a def in `with var:` / `with let:` is a variable of the def's proc type, initialized with
        the def as an anonymous proc; the docstring pragma belongs to the type. Python binds the name to the
        function, so swapping the proc is an assignment in both languages."""
        def nim(src):
            return unparse(ast.parse(textwrap.dedent(src)))[0]
        out = nim('''
            with var:
                def openRelay(path: string, n: nint) -> string:
                    """{.nimcall.}"""
                    return path
            with let:
                def _now() -> int64:
                    with var:
                        x = i64(1)
                    return x
        ''')
        self.assertIn("var\n  openRelay*: proc (path: string, n: int): string {.nimcall.} =\n"
                      "    proc (path: string, n: int): string =\n      return path\n", out)
        self.assertIn("let\n  now: proc (): int64 =\n    proc (): int64 =\n      var\n        x = 1'i64\n"
                      "      return x", out)
        # inside a proc: a local variable
        out = nim('''
            def f():
                with var:
                    def cb(x: nint):
                        echo(x)
                cb(1)
        ''')
        self.assertIn("  var\n    cb: proc (x: int) =\n      proc (x: int) =\n        echo(x)\n  cb(1)", out)
        # a second def of the name would silently rebind it in Python, but redefines the variable in Nim
        with self.assertRaises(SyntaxError):
            nim('''
                with var:
                    def r(x: nint): pass
                with var:
                    def r(x: nint): pass
            ''')
        with self.assertRaises(SyntaxError):
            nim('''
                with const:
                    def r(x: nint): pass
            ''')
        # a def in a value block (rule:block) the section's expression expands to is the block's proc
        out = nim('''
            def _block():
                def _count(x: nint) -> nint:
                    return x
                return _count(2)
            with const:
                two = _block()
        ''')
        self.assertIn("proc count(x: int): int =", out)  # `_`: a block's proc is not exported
        self.assertNotIn(": proc (", out)
        # Python: the variable holds the function and an assignment swaps it
        ns = {}
        exec(textwrap.dedent('''
            from nimic.ntypes import *
            with var:
                def relay(x: nint) -> nint:
                    return x + 1
            def use(x: nint) -> nint:
                return relay(x)
            before = use(1)
            relay = lambda x: x * 10
            after = use(1)
        '''), ns)
        self.assertEqual((ns["before"], ns["after"]), (2, 10))

    def test_inline_calltype(self):
        """rule:calltypeinline: @calltype(inline=True) on a private proc type declares no Nim type; its uses
        (fields, parameters, casts) are the anonymous proc type. In Python it is a calltype as any other."""
        def nim(src):
            return unparse(ast.parse(textwrap.dedent(src)))[0]
        out = nim('''
            @calltype(inline=True)
            def _Cleanup(b: mut @ Blob):
                """{.nimcall.}"""
                pass

            class Blob(Object):
                size: nint
                _cleanup: _Cleanup

            def initBlob(size: nint, cleanup: _Cleanup = None) -> Blob:
                return Blob(size=size, _cleanup=cleanup)
        ''')
        self.assertNotIn("Cleanup", out)
        self.assertIn("    cleanup: proc (b: var Blob) {.nimcall.}\n", out)
        self.assertIn("proc initBlob*(size: int, cleanup: proc (b: var Blob) {.nimcall.} = nil): Blob", out)
        self.assertTrue(out.lstrip().startswith("type\n  Blob* = object"))
        with self.assertRaises(SyntaxError):  # an importer would have no type to name
            nim('''
                @calltype(inline=True)
                def Cleanup(b: nint): pass
            ''')
        # Python: a calltype, used as a nilable field type
        ns = {}
        exec(textwrap.dedent('''
            from nimic.ntypes import *
            @calltype(inline=True)
            def _Hook(x: nint) -> nint: pass
            class Holder(Object):
                hook: _Hook
            h = Holder()
            empty = h.hook is None
            h.hook = lambda x: x + 1
            got = h.hook(1)
        '''), ns)
        self.assertEqual((ns["empty"], ns["got"]), (True, 2))

    def test_transpile_unchecked_assign(self):
        """rule:uncheckedassign: `with uncheckedAssign:` is a {.cast(uncheckedAssign).}: block."""
        src = "def f(x: Node):\n    with uncheckedAssign:\n        x.kind = NodeKind.nkInt\n"
        self.assertIn("  {.cast(uncheckedAssign).}:\n    x.kind = NodeKind.nkInt",
                      unparse(ast.parse(src))[0])

    def test_move_and_shallow_copy(self):
        """move is an identity operation in the Python runtime (shallowCopy: see
        test_shallow_copy_assigns_in_place)."""
        obj = [1, 2, 3]
        self.assertIs(move(obj), obj)
        self.assertIs(ensureMove(obj), obj)  # Nim's compile-time "can move" check has no Python effect

    def test_cmp_three_way(self):
        """cmp provides standard three-way comparison (-1, 0, 1)."""
        self.assertEqual(cmp(1, 2), -1)
        self.assertEqual(cmp(2, 2), 0)
        self.assertEqual(cmp(3, 2), 1)
        self.assertEqual(cmp("abc", "def"), -1)
        self.assertEqual(cmp("abc", "abc"), 0)
        self.assertEqual(cmp("xyz", "abc"), 1)

    def test_generic_decorator(self):
        """@generic allows parameterless generic functions to be subscripted with types in Python."""
        @generic
        def make_btree[T, U]():
            return "ok"

        res = make_btree[int, str]()
        self.assertEqual(res, "ok")

    def test_strutils_find_returns_int(self):
        """strutils find/rfind return Nim `int` (nint), so the index can be passed on as a `var int`."""
        def back(i: mut@nint) -> None:
            i -= 2

        idx = rfind(string("a b c"), ch(" "))
        self.assertIsInstance(idx, nint)
        back(idx)
        self.assertEqual(int(idx), 1)
        self.assertIsInstance(find(string("abc"), string("c")), nint)
        self.assertIsInstance(find(string("abc"), Tset[char]({ch("x")})), nint)
        self.assertEqual(int(find(string("abc"), Tset[char]({ch("x")}))), -1)

    def test_template_uses_caller_variables(self):
        """A statement template whose body uses names that are neither its parameters nor its own
        locals nor globals (Nim: open symbols, bound at the call site) is expanded in callers decorated
        with @template_expand, without {.dirty.} or nonlocal: it reads and assigns the caller's variables
        (`m`, `result`, an enclosing proc's `idx`) and `return` returns from the caller."""
        self.assertEqual(int(_tStrVersion(_TCfg(gc=2))), 2)
        self.assertEqual(int(_tStrVersion(_TCfg(gc=0))), 1)
        self.assertTrue(_tEndsWithWords(string("a b"), ch(" ")))
        self.assertTrue(_tEndsWithWords(string("a  b"), ch(" ")))
        self.assertIs(_tEndsWithWords(string("x b"), ch(" ")), False)  # bare `return` returns result
        self.assertIs(_tEndsWithWords(string("a c"), ch(" ")), False)  # bare `return` returns result
        out = unparse(ast.parse(textwrap.dedent(inspect.getsource(_tDetectVersion))))[0]
        self.assertIn("template tDetectVersion(field: untyped) =", out)
        self.assertNotIn("dirty", out)

    def test_template_routine_params_and_expanded_procs(self):
        """Template parameters used as routines are substituted in call and method-call position
        (`n.a.op(note)` with `fun(incl)` is `n.a.incl(note)`; `self(v, result)` with the proc itself).
        An expanded proc sees module globals defined after it, and `push` applies to it."""
        n = _TNotes()
        _tSetNote(n, uint8(3), True)
        self.assertIn(uint8(3), n.a)
        self.assertIn(uint8(3), n.b)
        _tSetNote(n, uint8(3), False)
        self.assertNotIn(uint8(3), n.a)
        out = string("")
        _tCountDown(nint(2), out)
        self.assertEqual(str(out), "012")
        self.assertEqual(int(_tWrappingAdd(int64(2**63 - 1), int64(1))), -2**63)

    def test_pointer_ordering(self):
        """Nim's `<` / `<=` of pointers (system) compare the addresses, `>` / `>=` are its templates `y < x` /
        `y <= x`: a scan `while p < eof`, `cast[pointer](p) >= data` (nifreader); nil is address 0."""
        with var:
            s = string("hello")
            p = cast[ptr[UncheckedArray[char]]](addr(s[0]))
            q = cast[ptr[UncheckedArray[char]]](cast[intp](p) + 2)
        self.assertTrue(p < q and p <= q and q > p and q >= p and p <= p and p >= p)
        self.assertFalse(q < p or q <= p or p > q or p >= q or p < p)
        data = cast[pointer](p)
        self.assertTrue(cast[pointer](q) >= data and not (data > cast[pointer](q)))
        self.assertTrue(p > nil and not (p < nil))
        with self.assertRaises(TypeError):
            p < 3

    def test_template_assigns_its_parameter(self):
        """A statement template assigning its parameter (`template inc(p: pchar; diff = 1) = p = ...`) assigns
        the call's argument: it is expanded in @template_expand callers, also with a default or keyword argument,
        for a local, a field (`inc r.p`) and a `mut @` parameter of the caller (assigned in place, `<<=`)."""
        with var:
            s = string("abcdef")
        self.assertEqual(str(_tScanLocal(s)), "a c f")
        r = _TCur(p=cast[ptr[UncheckedArray[char]]](addr(s[0])))
        _tAdvanceField(r)
        self.assertEqual(r.p[0], ch("d"))
        self.assertEqual(_tViaVarParam(s), ch("c"))
        self.assertIn("_tIncP", _n_templates)

    def test_block_template_uses_caller_scope(self):
        """A block template using its caller's variables (nifreader's `useCpuRegisters`: `var p {.inject.} =
        r.p`, the block, `r.p = p`) is expanded at `with t():` in @template_expand callers: its {.inject.} locals
        are the block's, and it reads and writes the caller's `r`. A statement template whose body has such a
        `with` (nifreader's `scanWord`) expands both. Its `break` leaves its loop, as Nim's expanded body."""
        with var:
            s = string("ab  cd")
        r = _TCur(p=cast[ptr[UncheckedArray[char]]](addr(s[0])))
        r.eof = cast[ptr[UncheckedArray[char]]](cast[intp](r.p) + len(s))
        self.assertEqual(int(_tSkipWord(r)), 2)
        self.assertEqual(r.p[0], ch(" "))
        self.assertEqual(int(_tSkipBlanksThenWord(r)), 2)
        self.assertEqual(r.p, r.eof)
        out = unparse(ast.parse(textwrap.dedent(inspect.getsource(_tSkipWord))))[0]
        self.assertIn("  tUseRegs():\n    while q < eof:", out)  # the transpiled source keeps the call

    def test_new_seq_default_length(self):
        """Nim's `newSeq[T](len = 0)`: an empty seq without the length."""
        self.assertEqual(len(newSeq[string]()), 0)
        self.assertEqual(newSeq[string](), seq[string]())

    def test_inrange_chars(self):
        """inrange of chars (Nim 'a'..'z') yields chars: membership and iteration."""
        self.assertIn(ch("b"), inrange(ch("a"), ch("z")))
        self.assertNotIn(ch("B"), inrange(ch("a"), ch("z")))
        self.assertEqual([str(c) for c in inrange(ch("a"), ch("c"))], ["a", "b", "c"])
        self.assertIn(ch("\x90"), inrange(ch("\x80"), ch("\xff")))

    def test_case_ranges_and_elif_branches(self):
        """`case _ if <subject> in inrange(a, b):` is `of a..b:`; ranges and `== v` joined with `or` are one
        `of` list; any other guard is an `elif` branch of the case (rule:matchcase)."""
        def kind(c: char, n: nint) -> nint:
            match c:
                case _ if c in inrange(ch("0"), ch("9")):
                    return nint(1)
                case _ if c in inrange(ch("a"), ch("z")) or c in inrange(ch("A"), ch("Z")) or c == ch("_"):
                    return nint(2)
                case "-":
                    return nint(3)
                case _ if n > 0:
                    return nint(4)
                case _:
                    return nint(0)

        self.assertEqual([int(kind(ch(x), nint(0))) for x in "5qZ_-+"], [1, 2, 2, 2, 3, 0])
        self.assertEqual(int(kind(ch("+"), nint(1))), 4)
        src = textwrap.dedent('''\
            match s[i]:
                case _ if s[i] in inrange(ch("0"), ch("9")):
                    a = 1
                case _ if s[i] in inrange(ch("a"), ch("z")) or s[i] in inrange(ch("A"), ch("Z")) or s[i] == ch("_"):
                    a = 2
                case _ if s[i] in inrange(TMsgKind.warnMin, TMsgKind.warnMax):
                    a = 3
                case _ if n > 0:
                    a = 4
                case _:
                    a = 0
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("case s[i]:\n  of '0' .. '9':", out)
        self.assertIn("of 'a' .. 'z', 'A' .. 'Z', '_':", out)
        self.assertIn("of TMsgKind.warnMin .. TMsgKind.warnMax:", out)
        self.assertIn("elif n > 0:", out)
        self.assertIn("else:", out)

    def test_case_expression_as_proc_result(self):
        """A proc whose body ends with a match in which every branch is `return <value>` is a Nim case
        expression as the proc's result (rule:casereturn); other returns keep `return`."""
        src = textwrap.dedent('''\
            def parseCmd(s: string) -> Cmd:
                match s:
                    case "sug":
                        return Cmd.ideSug
                    case "con" | "c":
                        return Cmd.ideCon
                    case _:
                        return Cmd.ideNone

            def f(s: string) -> nint:
                match s:
                    case "a":
                        x = 1
                        return x
                    case _:
                        return 0
            ''')
        out = unparse(ast.parse(src))[0]
        self.assertIn("proc parseCmd*(s: string): Cmd =\n  case s:\n    of \"sug\":\n      Cmd.ideSug\n", out)
        self.assertIn("of \"con\", \"c\":\n      Cmd.ideCon\n    else:\n      Cmd.ideNone", out)
        self.assertIn("return x", out)
        self.assertIn("return 0", out)

    def test_block_template_runs_around_block(self):
        """A template with a code-block parameter (Nim `t(args): block`) runs as `with t(args):`: the code
        before the block, the with body, then the code after it."""
        class _TBlkBuilder(Object):
            buf: string

        @template
        def _t_add_cast(b: mut@_TBlkBuilder, typ: string, valueBody: typed):
            b.buf.add(string("(("))
            b.buf.add(typ)
            b.buf.add(string(") "))
            valueBody
            b.buf.add(string(")"))

        b = _TBlkBuilder()
        with _t_add_cast(b, string("char*")):
            b.buf.add(string("p"))
        self.assertEqual(str(b.buf), "((char*) p)")

    def test_generic_block_template(self):
        """A block template with type parameters (nifpools' `buildTree[T: enum]`): `with t(args):` binds `T` from
        the argument, in the template's body too, as a generic proc's call does; the concrete overload of the
        name keeps its arguments."""
        out = seq[string]()
        with _tBlkTree(out, _TBlkTag.b):
            with _tBlkTree(out, nint(7)):
                out.add(string("x"))
        self.assertEqual([str(s) for s in out], ["(high 1 1", "(int 7", "x", ")", ")"])

    def test_block_template_two_blocks_out_param_and_overload(self):
        """Two blocks (`t(args): b1 do: b2` as `with t(args):` ... `with do:`), an out parameter assigned
        with `<<=`, and a template/proc overload set sharing one name."""
        class _TBlkInfo(Object):
            state: nint

        class _TBlkB(Object):
            buf: string

        @template
        def _t_switch_case(b: mut@_TBlkB, info: mut@_TBlkInfo, caseBody: typed, body: typed):
            info <<= _TBlkInfo(state=1)
            caseBody
            info.state = 2
            body
            b.buf.add(string(";"))

        b, info, seen = _TBlkB(), _TBlkInfo(), []
        with _t_switch_case(b, info):
            seen.append(int(info.state))
            with do:
                seen.append(int(info.state))
                b.buf.add(string("x"))
        self.assertEqual(seen, [1, 2])
        self.assertEqual(str(b.buf), "x;")
        with self.assertRaises(TemplateBlockError):
            with _t_switch_case(b, info):
                pass  # the second block is missing
        with self.assertRaises(TemplateBlockError):
            with do:
                pass  # no block template call

        @template
        def _t_blk_call(b: mut@_TBlkB, n: nint, body: typed):
            b.buf.add(string("("))
            body
            b.buf.add(string(")"))

        @dispatch
        def _t_blk_call(b: mut@_TBlkB, callee: string, *args: string) -> None:
            b.buf.add(callee)

        b2 = _TBlkB()
        with _t_blk_call(b2, nint(1)):
            b2.buf.add(string("in"))
        _t_blk_call(b2, string("f"), string("a"))
        self.assertEqual(str(b2.buf), "(in)f")

    def test_block_template_exception_and_skip(self):
        """An exception in the block propagates through the template (its try/finally runs); a template
        that would skip its block is reported instead of silently running the with body."""
        log = []

        @template
        def _t_guarded(body: typed):
            try:
                log.append("enter")
                body
            finally:
                log.append("exit")

        with self.assertRaises(ValueError):
            with _t_guarded():
                raise ValueError("boom")
        self.assertEqual(log, ["enter", "exit"])

        @template
        def _t_maybe(cond: bool, body: typed):
            if cond:
                body

        with self.assertRaises(TemplateBlockError):
            with _t_maybe(False):
                pass

    def test_variant_record_generic_attributes(self):
        """Variant record branches with array fields instantiate and access attributes cleanly."""
        @ref
        class MockVariantNode[K, V](Object):
            entries: nint
            keys: array[16, K]
            isInternal: bool
            match isInternal:
                case False:
                    vals: array[16, V]
                case True:
                    links: array[16, MockVariantNode[K, V]]

        leaf = MockVariantNode[str, int](entries=1, isInternal=False)
        self.assertEqual(len(leaf.keys), 16)
        self.assertEqual(len(leaf.vals), 16)

        internal = MockVariantNode[str, int](entries=2, isInternal=True)
        self.assertEqual(len(internal.keys), 16)
        # links accessed on internal node initializes array of size 16 without error
        self.assertEqual(len(internal.links), 16)
        internal.links[0] = leaf
        # each node only has the fields of its own branch
        with self.assertRaises(FieldDefect):
            leaf.links
        with self.assertRaises(FieldDefect):
            internal.vals
    def test_ninteger_trunc_div_and_mod(self):
        """NInteger __floordiv__ and __mod__ implement Nim-style truncation towards zero."""
        a = nint(-7)
        b = nint(3)
        self.assertEqual(int(a // b), -2)
        self.assertEqual(int(a % b), -1)

        c = nint(7)
        d = nint(-3)
        self.assertEqual(int(c // d), -2)
        self.assertEqual(int(c % d), 1)

        e = nint(-7)
        f = nint(-3)
        self.assertEqual(int(e // f), 2)
        self.assertEqual(int(e % f), -1)

        # Reflected
        self.assertEqual(int(-7 // b), -2)
        self.assertEqual(int(-7 % b), -1)


# --- templates that use the caller's variables (Nim: open symbols bind at the call site) ---
class _TCfg(Object):
    gc: nint


@template
def _tDetectVersion(field: untyped):
    if m.gc > 1:
        result = 2
    else:
        result = 1


@template_expand
def _tStrVersion(m: _TCfg) -> nint:
    _tDetectVersion(strVersion)
    return result


@template_expand
def _tEndsWithWords(x: string, sep: char) -> bool:
    with var:
        idx = len(x) - 1
        result = False

    @template
    def eatWord(word: untyped):
        while x[idx] == sep:
            idx -= 1
        result = x[idx] == word
        if not result:
            return
        idx -= 1

    eatWord(ch("b"))
    eatWord(ch("a"))
    result = True
    return result


class _TNotes(Object):
    a: Tset[uint8]
    b: Tset[uint8]


@template_expand
def _tSetNote(n: _TNotes, note: uint8, enabled: bool) -> None:
    @template
    def fun(op: untyped):
        n.a.op(note)
        n.b.op(note)
    if enabled:
        fun(incl)
    else:
        fun(excl)


@template
def _tWrapImpl(self: untyped):
    if x > 0:
        self(x - 1, result)
    result.add(_tLater(x))


@template_expand
def _tCountDown(x: nint, result: mut@string) -> None:
    _tWrapImpl(_tCountDown)


def _tLater(x: nint) -> string:
    return string(str(x))


with push("overflowChecks: off"):
    @template
    def _tAddImpl():
        result = a + b

    @template_expand
    def _tWrappingAdd(a: int64, b: int64) -> int64:
        _tAddImpl()
        return result



@template
def _tAstText(x: untyped, expected: untyped) -> string:
    """A typed template: called as a proc in Python."""
    return astToStr(x) + string(" / ") + astToStr(expected)


@template
def _tAstTextDirty(x: untyped) -> untyped:
    """{.dirty.}"""
    return astToStr(x)


@template_expand
def _tUsesAstText(n: nint) -> string:
    return _tAstTextDirty(n * (2 + 1))


@template
def _tSetAstText(x: untyped):
    """{.dirty.}"""
    result = astToStr(x)


@template_expand
def _tUsesSetAstText(n: nint) -> string:
    result = string("")
    _tSetAstText(n + 1)  # expanded inline: astToStr(x) becomes the argument's text at expansion
    return result


class _TCur(Object):
    p: ptr[UncheckedArray[char]]
    eof: ptr[UncheckedArray[char]]


@template
def _tIncP(p: ptr[UncheckedArray[char]], diff=1):
    p = cast[ptr[UncheckedArray[char]]](cast[intp](p) + diff)


@template_expand
def _tScanLocal(s: string) -> string:
    with var:
        p = cast[ptr[UncheckedArray[char]]](addr(s[0]))
        result = string("")
    result.add(p[0])
    _tIncP(p, 2)
    result.add(string(" "))
    result.add(p[0])
    _tIncP(p)
    _tIncP(diff=2, p=p)
    result.add(string(" "))
    result.add(p[0])
    return result


@template_expand
def _tAdvanceField(r: mut @ _TCur):
    _tIncP(r.p)
    _tIncP(r.p, 2)


@template_expand
def _tBumpVar(p: mut @ ptr[UncheckedArray[char]]):
    _tIncP(p)


def _tViaVarParam(s: string) -> char:
    with var:
        p = cast[ptr[UncheckedArray[char]]](addr(s[0]))
    _tBumpVar(p)
    _tBumpVar(p)
    return p[0]


@template
def _tUseRegs(body: untyped):
    with var:
        q: pragma("inject") = r.p
    with let:
        eof: pragma("inject") = r.eof
    body
    r.p = q


@template_expand
def _tSkipWord(r: mut @ _TCur) -> nint:
    with var:
        n = nint(0)
    with _tUseRegs():
        while q < eof:
            if q[0] == ch(" "):
                break
            n += 1
            _tIncP(q)
    return n


@template_expand
def _tSkipBlanksThenWord(r: mut @ _TCur) -> nint:
    with var:
        n = nint(0)

    @template
    def skipWhile(c: char):
        with _tUseRegs():
            while q < eof and q[0] == c:
                _tIncP(q)

    skipWhile(ch(" "))
    with _tUseRegs():
        while q < eof:
            n += 1
            _tIncP(q)
    return n

if __name__ == '__main__':
    unittest.main()
