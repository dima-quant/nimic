
from __future__ import annotations
import ast
import builtins
import contextlib
import ctypes
import io
import math
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from nimic.ntypes import *
from nimic.nsystem import ord as nim_ord, _BuildProfile, _n_set_build_profile
from nimic.ntypesystem import (BUFFER_REGISTRY, BufferRegistry, DICT_OF_C_TYPES, _match_subtype,
                               _n_aliases, _n_distinct_types, _n_from_text, _n_registry, _n_to_text,
                               char as _char)
from nimic.std.endians import big_endian32
from nimic.std.math import classify, fcNegSubnormal, fcNormal, fcSubnormal
from nimic.std.options import Option, none, some
from nimic.std.os import fileExists, getCurrentDir, getEnv, walkDir
from nimic.std.parseutils import parse_hex, parse_ident
from nimic.std.strscans import scanf
from nimic.std.strutils import find, nimIdentNormalize, repeat, rfind, strip, toLowerAscii
from nimic.std.syncio import lines, read_file
from nimic.system.ansi_c import c_free, c_malloc, csize_t
from nimic.transpiler import unparse

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
        up = uintp.cast(p)
        ip = intp.cast(p)

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
        """high()/low() on signed integer types dispatches via NInteger.first()/last()."""
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

        self.assertEqual(ArrType.first(), 3)
        self.assertEqual(ArrType.last(), 7)

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
        self.assertEqual(cstring(b"\xc3\xa9")._value, b"\xc3\xa9")

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
        """classify reports subnormal floats like Nim's fcSubnormal / fcNegSubnormal."""
        tiny = sys.float_info.min / 2
        self.assertEqual(classify(tiny), fcSubnormal)
        self.assertEqual(classify(-tiny), fcNegSubnormal)
        self.assertEqual(classify(sys.float_info.min), fcNormal)

    def test_dispatched_callable_keeps_function_metadata(self):
        """A @dispatch wrapper exposes __type_params__/__globals__/__code__, so it can be re-dispatched."""
        def _t_ident[T](x: T) -> T:
            return x
        d = dispatch(_t_ident)
        self.assertEqual(d.__type_params__, _t_ident.__type_params__)
        self.assertIs(d.__globals__, _t_ident.__globals__)
        self.assertIs(d.__code__, _t_ident.__code__)
        d2 = dispatch(d)  # re-dispatching a wrapper (DispDict does this) must not fail ...
        self.assertIs(d2._fn, _t_ident)  # ... and registers the original function, not the wrapper
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
        q = _TPadded.cast(p)  # view-backed: fields are bound to the struct memory
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
        self.assertIn("name: string=string(\"\"), initializerBody: typed, other: untyped) =", unparse(ast.parse(src))[0])

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


if __name__ == '__main__':
    unittest.main()
