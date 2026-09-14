
from __future__ import annotations
import unittest
import math
from nimic.ntypes import *

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
        # int8: -128 to 127
        val = int8(127)
        val += 1
        self.assertEqual(int(val), -128)  # Overflow wraps around

        val = int8(-128)
        val -= 1
        self.assertEqual(int(val), 127)   # Underflow wraps around

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
        from nimic.system.ansi_c import c_malloc, c_free, csize_t

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
        from nimic.system.ansi_c import c_malloc, c_free, csize_t

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
        from nimic.std.options import Option, some, none

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
        import io, contextlib

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
        from nimic.system.ansi_c import c_malloc, c_free, csize_t
        import ctypes

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
        from nimic.system.ansi_c import c_malloc, c_free, csize_t

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
        from nimic.std.endians import big_endian32

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
            kind: HittableVariantKind = None
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

        result = Scene()
        result.add(Sphere(center=Vec3(x=0, y=-1000, z=0), radius=1000.0))
        result.add(MovingSphere(center0=Vec3(x=0, y=0, z=0), center1=Vec3(x=0, y=0, z=0), time0=0.0, time1=1.0, radius=1.0))
        world_list = result.list()
        self.assertEqual(world_list.len, 2)
        self.assertEqual(world_list.objects[0].kind, HittableVariantKind.kSphere)
        self.assertEqual(world_list.objects[1].kind, HittableVariantKind.kMovingSphere)

        result = _ReturnScenes()
        result.scene.add(Sphere(center=Vec3(x=0, y=-1000, z=0), radius=1000.0))
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
        import ctypes
        from nimic.ntypesystem import BufferRegistry
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
        import ctypes
        from nimic.ntypesystem import BufferRegistry
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
        import ctypes
        from nimic.ntypesystem import BufferRegistry
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
        from nimic.ntypesystem import BUFFER_REGISTRY
        initial = len(BUFFER_REGISTRY)
        class Point(Object):
            x: int32
            y: int32
        p = Point()
        # The buffer should be in the global registry
        self.assertGreaterEqual(len(BUFFER_REGISTRY), initial + 1)

    def test_buffer_registry_seq_resize(self):
        """After Phase 2: seq resize should update the registry."""
        from nimic.ntypesystem import BUFFER_REGISTRY
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
        
        from nimic.system.ansi_c import c_malloc, c_free, csize_t

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
        import ctypes

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


if __name__ == '__main__':
    unittest.main()
