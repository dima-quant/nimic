"""
nimic nkeywords
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

nimic  a Python-embedded DSL that emulates Nim's
type semantics. Code written using these types runs natively in Python AND
transpiles to equivalent Nim code via the nimic transpiler.

Provides Python-side implementations of Nim keywords, builtins, and compiler
hints so that nimic code can run in Python. Consumed via
``from nimic.nkeywords import *`` inside ntypes.py.

Contents:

  Compiler hints      — const, let, var, block, export, alias
                        Implemented as contextlib.nullcontext() (no-ops in
                        Python, transpiled to Nim scope qualifiers).
  Reference types     — ref, ptr, mut  (SomeRefClass instances)
                        The @ operator returns identity; transpiled to
                        Nim ref/ptr/var annotations.
  Enum utilities      — NStrEnum with succ/pred/ord/nrange/subset/low/high.
  Cast & memory       — cast[T](x), sizeof(x), addr(x), unsafeAddr(x).
  Iteration helpers   — fields(obj), fields(obj1, obj2), countdown(a, b).
  Compile-time        — comptime(x), defined(varname), static.
  Nim stdlib shims    — file operations, path utilities, Table,
                        genEnumCaseStmt, and related helpers.
"""
from __future__ import annotations
import ast
import contextlib
from enum import StrEnum
from typing import TypeVar
import os
import shutil
import inspect as ins
import subprocess
from . import transpiler

def nimp(fn: callable) -> callable:
    # print(fn.__name__)
    # print(fn.__doc__)
    # print(fn.__type_params__)
    # print(fn.__annotations__)
    src = ins.getsource(fn)
    #print(src)
    aast = ast.parse(src)
    print(transpiler.unparse(aast))
    return fn

class NStrEnum(StrEnum):
    __members_tuple__ = None
    __indices__ = None

    @classmethod
    def _set_indices(cls) -> None:
        cls.__members_tuple__ = tuple(cls)
        cls.__indices__ = {val: ind for ind, val in enumerate(cls.__members_tuple__)}
    
    @classmethod
    def first(cls) -> StrEnum:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        return cls.__members_tuple__[0]

    @classmethod
    def last(cls) -> StrEnum:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        return cls.__members_tuple__[-1]

    @classmethod
    def nitems(cls) -> int:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        return len(cls.__members_tuple__)

    @classmethod
    def nrange(cls, first: StrEnum, last: StrEnum) -> StrEnum:
        if cls.__members_tuple__ is None:
            cls._set_indices()
        members = cls.__members_tuple__
        indices = cls.__indices__
        first_ind = indices[first]
        last_ind = indices[last]
        return members[first_ind:last_ind+1]
    
    def nrange(item, last: StrEnum) -> StrEnum:
        cls = item.__class__
        if cls.__members_tuple__ is None:
            cls._set_indices()
        members = cls.__members_tuple__
        indices = cls.__indices__
        first_ind = indices[item]
        last_ind = indices[last]
        return members[first_ind:last_ind+1]

    def succ(item, n: int=1) -> StrEnum:
        cls = item.__class__
        if cls.__members_tuple__ is None:
            cls._set_indices()
        members = cls.__members_tuple__
        indices = cls.__indices__
        if item in members:
            ind = indices[item] + n
            if ind >=0 and ind < len(members):
                res = members[ind]
            else:
                res = None
        else:
            res = None        
        return res

    def ord(item) -> int:
        cls = item.__class__
        if cls.__members_tuple__ is None:
            cls._set_indices()
        ind = cls.__indices__[item] 
        return ind


def succ(item: StrEnum, n: int=1) -> StrEnum:
    return item.succ(n)

def pred(item: StrEnum, n: int=1) -> StrEnum:
    return succ(item, -n)   

def nord(item: StrEnum) -> int:
    return item.ord()  

def nrange(first: StrEnum, last: StrEnum) -> list[StrEnum]:
    return first.nrange(last)

def subset(newname: str, first: NStrEnum, last: NStrEnum) -> type:
    cls = first.__class__
    return NStrEnum(newname, [(a.name,a.value) for a in nrange(first, last)])

def low[T: StrEnum](cls: T) -> T:
    return cls.first()

def high[T: StrEnum](cls: T) -> T:
    return cls.last()

# _member_map_
# _value2member_map_
# cls.__members__.values()
    # @classmethod
    # def _iter_member_by_value_(cls, value):
    #     """
    #     Extract all members from the value in definition (i.e. increasing value) order.
    #     """
    #     for val in _iter_bits_lsb(value & cls._flag_mask_):
    #         yield cls._value2member_map_.get(val)

    # _iter_member_ = _iter_member_by_value_

    # def __iter__(self):
    #     """
    #     Returns flags in definition order.
    #     """
    #     yield from self._iter_member_(self._value_)

    # def __iter__(cls):
    #     """
    #     Return members in definition order.
    #     """
    #     return (cls._member_map_[name] for name in cls._member_names_)
# it = iter(a) # calls a.__iter__
    # @bltns.property
    # def __members__(cls):
    #     """
    #     Returns a mapping of member name->value.

    #     This mapping lists all enum members, including aliases. Note that this
    #     is a read-only view of the internal mapping.
    #     """
    #     return MappingProxyType(cls._member_map_)
  

# class ref:
#     pass

# def ref(cls):
#     return cls

# def ptr(cls):
#     return cls

class SomeRefClass:
    def __matmul__(self, other: object) -> object:
        return other
    def __call__(self, other: object) -> object:
        return other
    def __getitem__(self, other: object) -> object:
        return other
    
    # def set_value(self, value):
    #     self = value

ref = SomeRefClass()
ptr = SomeRefClass()
# reserve keyword for modifiable variables
mut = SomeRefClass()


def local(cls: type) -> type:
    return cls



class concept:
    @classmethod
    def is_concept_of(cls, other: type) -> bool:
        # TO DO implement actulal check for concepts
        return True

# class Hittable(concept):
#     self: object = None
    # All hittables implement
    # func hit(self: Hittable, r: Ray, t_min: float64, t_max: float64): Option[HitRecord]
    # We use Option instead of passing a mutable reference like in the tutorial.
    # self.hit(Ray, float64, float64, mut @ HitRecord) is bool

#static: doAssert Sphere is Hittable
#assert Hittable.is_concept_of(Sphere)

# def T(x):
#     # trivial type-cast
#     return x

# compiler hints
const = contextlib.nullcontext()
let = contextlib.nullcontext()
var = contextlib.nullcontext()
block = contextlib.nullcontext()
Type = contextlib.nullcontext()
context_template = contextlib.contextmanager
export = contextlib.nullcontext()
alias = contextlib.nullcontext()

# type array_dict = dict
# within const array[int,:] -> dict, {} -> set
# within const Table[string,:] -> dict
### replaced inc(i) -> i += 1
### high -> len
### on strings "a" & s -> "a" + s

static = set #Generic

# type cstring = str
type array = list

    
# class SomeCastClass:
#     def __init__(self):
#         # self.size = None
#         self.type = None
#     # def _set(self, x):
#     #     # self.size = x #x.size
#     #     # return this type instance )
#     #     if isinstance(x, bytearray):
#     #         return self.type.from_bytes(x)
#     #     else:
#     #         return self.type.from_bytes(x.to_bytes())
    
#     def _cast(self, x):
#         return self.type.cast(x)

#     def __getitem__(self, cls):
#         self.type = cls
#         if isinstance(cls, TypeVar):
#             fun = lambda x: x
#         else:    
#             fun = self._cast
#         return fun 

# cast = SomeCastClass()

class SomeCastClass:
    def __getitem__(self, other_cls: type) -> callable:
        if isinstance(other_cls, TypeVar):
            fun = lambda x: x
        else:    
            fun = lambda x: other_cls.cast(x)
        return fun 

cast = SomeCastClass()

# class csize_t(int):
#     pass


def sizeof(x: type) -> int:
    return x._n_sizeof()

def make_pointer(x: object) -> object:
    x._n_ptr_alike = True
    return x

def addr(x: object) -> object:
    return make_pointer(x)

def unsafe_addr(x: object) -> object:
    return make_pointer(x)

def ntype(cls: type) -> type:
    cls.register_type()
    return cls

def new(x: object, cls: type) -> None:
    # cls = x.__class__
    x = cls()

def default(x: type) -> object:
    if "__value__" in dir(x):
        val = x.__value__
    else:    
        val = x
    if str(val)[0:4] == 'dict':
        res = dict()
    return res

#  presense of resolve_aot in "if" expression forces aot evaluation
#  resolve_aot itself is resolved to True 
# resolve_aot = True

#  presense of comptime in "if" expression forces aot evaluation
def comptime(x: object) -> object:
    return x

def defined(varname: str) -> bool:
    """
    Check if a variable with the given name is defined in the global scope.

    Args:
        varname (str): The name of the variable to check.

    Returns:
        bool: True if the variable is defined in the global scope, False otherwise.
    """
    return varname in globals()


def get_args(caller: object) -> list[str] | None:
    try:
        tree = ast.parse(caller.code_context[0])
    except SyntaxError:
        # not a complete Python statement
        return None
    func_call = tree.body[0].value
    args = [ast.unparse(arg) for arg in func_call.args]
    return args
 

def fields(x: object, y: object | None = None) -> object:
    if y is None:
        for name in x._n_fields:
            yield getattr(x, name) 
    else:
        for name in x._n_fields:
            yield getattr(x, name), getattr(y, name) 


def countdown(a: int, b: int) -> range:
    for i in range(a, b-1, -1):
        yield i

# def items(x):
#     for name in x._n_fields:
#         yield name, getattr(x, name) 

# def ffields(x):
#     for name in x._n_fields:
#         yield name



# def isMainModule(name):
#     return name == "__main__"

# def export(*args, **kwargs):
#     pass

############ std #################




def exec_shell_cmd(cmd: str) -> int:
    return subprocess.run(cmd, shell=True).returncode


class Hash:
    pass

Table = dict

def hash_ignore_style(s: cstring) -> Hash:
    pass

def nhash() -> int:
    pass

# gen_enum_case_stmt(T, s, default = nil, ord(low(T)), ord(high(T)), normalize)
# T, s, default, nord(a), nord(b), normalize
def gen_enum_case_stmt[T](T: type, s: T, default: T,
                      userMin: static[int], userMax: static[int],
                      normalizer: callable) -> object:
    enum_members = list(T)
    for member in enum_members[userMin:userMax+1]:
        if normalizer(member.value) == normalizer(s):
            return member
    return default

def normalize(s: string) -> string:
    return s

def init_table() -> dict:
    pass


def get_current_dir() -> string:
    return Path(os.getcwd())


def write_file(x: str, content: str) -> None:
    pass

def quote_shell(x: str) -> str:
    pass


def remove_file(x: str) -> None:
    """
    Remove a file.

    Args:
        x (str): The file path to remove.

    Returns:
        None
    """
    os.remove(x)

def extract_filename(x: str) -> str:
    pass

#implement in Python functionality according to the function's name for this declaratyion: 


def file_exists(x: str) -> bool:
    """
    Check if a file exists.

    Args:
        x (str): The file path to check.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    return os.path.exists(x)

def add_file_ext(x: str, ext: str) -> str:
    pass


def dir_exists(x: str) -> bool:
    """
    Check if a directory exists.

    Args:
        x (str): The directory path to check.

    Returns:
        bool: True if the directory exists, False otherwise.
    """
    return os.path.isdir(x)

def cmp_paths(x: str, y: str) -> int:
    pass


def create_dir(x: str) -> None:
    """
    Create a directory.

    Args:
        x (str): The directory path to create.

    Returns:
        None
    """
    os.makedirs(x, exist_ok=True)

def change_file_ext(x: str, ext: str) -> str:
    pass


def os_copyFile(x: str, y: str) -> None:
    """
    Copy a file from one location to another.

    Args:
        x (str): The source file path.
        y (str): The destination file path.

    Returns:
        None
    """
    shutil.copy(x, y)

def split_file(x: string) -> tuple[string, string, string]:
    """
    Split a file path into directory, base name, and extension.

    Args:
        x (str): The file path to split.

    Returns:
        Tuple[str, str, str]: A tuple containing directory, base name, and extension.
    """
    dirname, basename = os.path.split(x)
    base, ext = os.path.splitext(basename)
    return dirname, base, ext


def is_absolute(path: string) -> bool:
    return os.path.isabs(path)
