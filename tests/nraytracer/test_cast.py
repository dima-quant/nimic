from __future__ import annotations
import ctypes
from random import randint
from nimic.ntypes import float64, Object, UncheckedArray, uint64, cast, \
ntype, unsafe_addr, seq, NIntEnum, auto, ptr

class value_view():
    def __init__(self, c_data, c_buff_type, id):
        if c_buff_type == "struct":
            get_value = lambda: getattr(c_data, id)  
            set_value = lambda value: setattr(c_data, id, value)
        else:
            self.value = 0
            get_value = lambda: getattr(self, "value")  
            set_value = lambda value: setattr(self, "value", value) 
        self.get_value = get_value
        self.set_value = set_value

@ntype
class Point3(Object):
    x: float64
    y: float64
    z: float64

@ntype
class Color(Object):
    x: float64
    y: float64
    z: float64


class Color2(Object):
    x: Color
    y: Color
    z: float64


class Color3(Object):
    x: uint64
    y: uint64
    z: uint64

class struct_view_():
    def __init__(self, elems):
        self.c_struct = elems
        self.fields = ["x", "y", "z"]

    def __setattr__(self, name, value):
        if name in ["c_struct", "fields"]:
            super().__setattr__(name, value)
        elif name not in self.fields:
            super().__setattr__(name, value)
        else:
            setattr(self.c_struct, name, value)
                       

    def __getattr__(self, name):
        if name in ["c_struct", "fields"]:
            return super().__getattribute__(name)
        elif name not in self.fields:
            return super().__getattribute__(name)
        else:
            return getattr(self.c_struct, name)           


# def cast(typed_array, data_ptr):
#     return typed_array.cast(data_ptr)

class canv():
    # pixels: ctypes.POINTER(s_struct["Color"])

    def __init__(self, num_of_structs):
        elems = (Color.c_type() * num_of_structs)()
        self.elems = elems
        self.pixels = cast[UncheckedArray[Color]](ctypes.addressof(elems))
        # elems1 = ctypes.addressof(self.pixels1[0])
        # self.pixels = cast[UncheckedArray[Color]](elems1)
        self.elements = num_of_structs

        for num in range(0, num_of_structs):
            self.pixels[num].x = 1*num
            self.pixels[num].y = 2*num
            self.pixels[num].z = 3*num

class canv1():
    # pixels: ctypes.POINTER(s_struct["Color"])

    def __init__(self, num_of_structs):
        elems = (float64.c_type() * num_of_structs)()
        self.elems = elems
        self.pixels = cast[UncheckedArray[float64]](ctypes.addressof(elems))
        self.elements = num_of_structs

        for num in range(0, num_of_structs):
            self.pixels[num] = 3*num


class Material(Object):
    kind: uint64 = None
    match kind:
        case 0:
            fMetal: Color
        case 1:
            fLambertian: Color2
        case 2:
            fDielectric: Color


class Sphere(Object):
    center: Point3
    radius: float64
    material: Material


class MovingSphere(Object):
  # From book 2
    center0: Point3
    center1: Point3
    radius: float64
    material: Material

class HittableVariantKind(NIntEnum):
      kSphere = auto()
      kMovingSphere = auto()

class HittableVariant(Object):
    kind: HittableVariantKind = None
    match kind:
        case HittableVariantKind.kSphere:
            fSphere: Sphere
        case HittableVariantKind.kMovingSphere:
            fMovingSphere: MovingSphere

# class HittableVariant(Object):
#     kind: uint64 = None
#     match kind:
#         case 0:
#             fSphere: Sphere
#         case 1:
#             fMovingSphere: MovingSphere


# cast[ptr[UncheckedArray[Color]]]
test0 = Color2()
test0.z = 10
print(test0.z)
elems2 = unsafe_addr(test0.z)
p2 = ctypes.cast(elems2, ctypes.POINTER(ctypes.c_double))
print(p2.contents)
print(test0.x.y)


def point3(x: float64, y: float64, z: float64) -> Point3:
    """{.inline.}"""
    result = Point3()
    result.x = x
    result.y = y
    result.z = z
    return Point3(result)

def sphere(center: Point3, radius: float64, material: Material) -> Sphere:
    """{.inline.}"""
    result = Sphere()
    result.center = center
    result.radius = radius
    result.material = material
    return result

def movingSphere(
       center0: Point3,
       center1: Point3,
       radius: float64, material: Material) -> MovingSphere:
    """{.inline.}"""
    result = MovingSphere()
    result.center0 = center0
    result.center1 = center1
    result.radius = radius
    result.material = material
    return result

centr0 = point3(2.2, 7.4, -1.5)
centr1 = point3(1.2, 3.4, 4.5)

met = Material(kind=0, fMetal=Color())
diel = Material(kind=2, fDielectric=Color())

sc = seq[HittableVariant]()
sc.append(HittableVariant(kind=HittableVariantKind.kSphere, fSphere=sphere(centr0, 5.0, met)))
print(sc[0].kind)
sc.append(HittableVariant(kind=HittableVariantKind.kMovingSphere, fMovingSphere=movingSphere(centr0, centr1, 17.0, diel)))
print(sc[1].fMovingSphere.material.kind)
sc.append(HittableVariant(kind=HittableVariantKind.kSphere, fSphere=sphere(centr1, 15.0, diel)))
sc.append(HittableVariant(kind=HittableVariantKind.kSphere, fSphere=sphere(centr1, 1.0, met)))
sc.append(HittableVariant(kind=HittableVariantKind.kSphere, fSphere=sphere(centr0, 3.0, met)))
sc.append(HittableVariant(kind=HittableVariantKind.kMovingSphere, fMovingSphere=movingSphere(centr1, centr0, 7.0, met)))
sc.append(HittableVariant(kind=HittableVariantKind.kSphere, fSphere=sphere(centr1, 11.0, diel)))
print(sc[1].fMovingSphere.material.kind)
# for j in range(len(sc)):
#     print(ctypes.addressof(sc.c_data[j]))
#     print(sc.c_data[j].kind)
objects = cast[ptr[UncheckedArray[HittableVariant]]](
        unsafe_addr(sc[0])
        )
# for j in range(len(sc)):
#     print(ctypes.addressof(objects.c_data[j]))
#     print(objects.c_data[j].kind)
print(objects[1].fMovingSphere.material.kind)
test = canv(10)
a = test.pixels[5].y
a += 9
print(test.pixels[5].y)
d = Color()
d.z = 5
print(d.z)
d.z +=3
print(d.z)
d.z +=3
print(d.z)
# print("%i done" % 10)

test1 = canv1(10)
print(test1.pixels[5])
b = test1.pixels[5]
b += 9
print(test1.pixels[5])

test5 = Color3()
test5.x = 1
test5.y = 2
test5.z = 3
c = test5.z
c += 3
print(test5.z)
pass