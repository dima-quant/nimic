from __future__ import annotations
from nimic.ntypes import *
from nraytracer.nimic.transpiler import *
import importlib
from native import ntypes
importlib.reload(ntypes)

class ConfigRef:
    def __init__(self):
        self.unitSep: str = None
        self.evalTemplateCounter: int
        self.evalMacroCounter: int

ts =  ConfigRef()
#ts.unitSep2 = " 1 "
print(ts.__dict__)
print(type(ts.unitSep))

nimpretty = False
if 'nimpretty' in globals():
    print("hi")

class TIdent:
    pass

# class ref:
#     pass

type PIdent = list[str] #ref[TIdent]

class Object:
    def __init__(self, *args, **kwargs):
        attributes = list(self.__annotations__)
        if len(args)>0:
            for i, x in enumerate(args):
                setattr(self, attributes[i], x)
        for x in kwargs:
            if x in attributes:
                setattr(self, x, kwargs[x])
            else:
                raise AttributeError(x)  
class testt(Object):
    fy: int
    jh: str
    f: int = 0

g = testt(2, jh="3")
print(dir(g))
print(g.fy)
print(g.jh)
k = testt()
# x = PIdent()

from string import Template
# class string(str):
#     def _substitute(self, **kwargs):
#         return Template(self).substitute(**kwargs)
    
#     def __mod__(self, itr):
#         set_key = True
#         kwargs = {}
#         for item in itr:
#             if set_key:
#                 key = item
#                 set_key = False
#             else:
#                 kwargs[key] = item
#                 set_key = True
#         return self._substitute(**kwargs)        

st = string('hanning$num.pdf') % ['num', 22]
print(st)

# import inspect as ins
# import ast

# def nimp(fn: callable) -> callable:
#     # print(fn.__name__)
#     # print(fn.__doc__)
#     # print(fn.__type_params__)
#     # print(fn.__annotations__)
#     src = ins.getsource(fn)
#     # print(src)
#     # aast = ast.parse(src)
#     # print(ast.dump(aast))
#     return fn


@nimp
def main_nimp(s: string) -> string:
    """{.align.}"""

    class  IdentCache(Object, ref):
        wordCounter: int

    def ins(inp: IdentCache) -> int:
        return inp.wordCounter
      
    s = s + "23"
    return s

# su = main_nimp("fdk")
# print(su)


class CallArgumentNameFinder(ast.NodeVisitor):
    # from https://stackoverflow.com/questions/52184796
    def __init__(self, functionname):
        self.name = functionname
        self.params = []
        self.kwargs = {}

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            return  # not a name(...) call
        if node.func.id != self.name:
            return  # different name being called
        self.params = [n.id for n in node.args if isinstance(n, ast.Name) or isinstance(n, ast.Expr)]
        self.kwargs = {
            kw.arg: kw.value.id for kw in node.keywords
            if isinstance(kw.value, ast.Name)
        }

def check_func(func):
    caller = ins.stack()[2]  # caller of our caller
    try:
        tree = ast.parse(caller.code_context[0])
    except SyntaxError:
        # not a complete Python statement
        return None
    visitor = CallArgumentNameFinder(func.__name__)
    visitor.visit(tree)
    return ins.signature(func).bind_partial(
        *visitor.params, **visitor.kwargs)

def get_args(caller):
    try:
        tree = ast.parse(caller.code_context[0])
    except SyntaxError:
        # not a complete Python statement
        return None
    func_call = tree.body[0].value
    args = [ast.unparse(arg) for arg in func_call.args]
    return args

def template(functionlike=True):
    if functionlike:
        if callable(functionlike):
            return functionlike
        else:
            return lambda fn: fn
    else:
        def wrapper(fn):
            all_sigs = tuple(fn.__annotations__.keys())
            return_value = all_sigs[-1] == 'return'
            if return_value:
                sigs = all_sigs[:-1]
            else:
                sigs = all_sigs
            if not sigs:
                return fn
            src = ins.getsource(fn).split("\n")[-2].lstrip()
            def temp_fn(*args):
                args_expr = get_args(ins.stack()[1])
                expr = src
                for sig, arg in zip(sigs, args_expr):
                    expr = expr.replace(sig, arg)
                if return_value:
                    return eval(expr)
                else:
                    exec(expr)
            return temp_fn
        return wrapper    

@template(functionlike=False)
def my_join_aa(s1: string, s2: string):
    global aa; aa = s1 + s2

@template(functionlike=True)
def my_join(s1: string, s2: string) -> string:
    return s1 + s2


@template
def my_join2(s1: string, s2: string) -> string:
    return s1 + s2

# st1 = "fdk1000"
# st2 = "f3k"
# my_join_aa(st1, "".join(["sd","sr"]))
# print(aa)
# st3 = my_join(st1, "".join(["sd","sr"]))
# print(st3)
# st3 = my_join2(st1, "".join(["sd","sr"]))
# print(st3)
# print(st)

# import future

# proc `+` (a, b: string): string =
#   result = a & b

s = ntypes.string
s1 = string
print(s("dfs")&s("dfs232"))

def nimp(obj: object) -> object:
    print(obj.__name__)
    print(obj.__doc__)
    print(obj.__type_params__)
    print(obj.__annotations__)
    src = ins.getsource(obj)
    #print(src)
    aast = ast.parse(src)
    print(transpiler.unparse(aast))
    return obj

# __dispatch__ = {}

# def dispatch(fn: callable) -> callable:
#     print(fn.__name__)
#     print(fn.__doc__)
#     print(fn.__annotations__)
#     sigs =(v for k, v in fn.__annotations__.items() if k != 'return')
#     fn_sig = (fn.__name__, *sigs)
#     __dispatch__[fn_sig] = fn
#     def fn_dispatch(*args):
#         sigs = (type(arg).__name__ for arg in args)
#         fn_sig = (fn.__name__, *sigs)
#         return __dispatch__[fn_sig](*args)
#     return fn_dispatch

def private[T](x: T) -> T: 
    return x


@nimp
def hsh(x: int, y: float) -> int: 
    """{.inline.}"""
    class TIdent(Object):
        """{.acyclic.}"""
        id: int
    @ref
    class PIdent(TIdent):
        pass

    @distinct
    class Ppass(string):
        pass

    @ref
    class Ipass(Ppass):
        _wordCounter: int

    @ref
    class IdentCache(Object):
        _wordCounter: int
        idAnon: PIdent
    # def _hsha(x: int) -> None:
    #     """{.inline.}"""
    #     x = 1
    # def _hshb(x: int) -> None:
    #     x = 1    
    
    class nt(Object):
        color: IdentCache = None
        match color:
            case 2: sd: string

    with var:
        rt: ptr @ IdentCache
        rt2: nt

    with let:
        d4: ptr[IdentCache] = 4      

    with const:
        s3 = "jgjhg" 
    
    return x + 1

    # Node = ref object
    #     case kind: NodeKind  # the `kind` field is the discriminator
    #     of nkInt: intVal: int  


    # Node = ref object
    #     case kind: NodeKind  # the `kind` field is the discriminator
    #     of nkInt: intVal: int   
# proc hash*(x: PIdent): Hash {.inline.} = x.h
# type
#   PIdent* = ref TIdent
#   TIdent*{.acyclic.} = object
#     id*: int # unique id; use this for comparisons and not the pointers
#     s*: string
#     next*: PIdent             # for hash-table chaining
#     h*: Hash                 # hash value of s

#   IdentCache* = ref object
#     buckets: array[0..4096 * 2 - 1, PIdent]
#     wordCounter: int
#     idAnon*, idDelegator*, emptyIdent*: PIdent
            # # private via pragma or decorator? now pragma
            # # parse the pragma
            # pragma_list = pragma[2:-2].split(",")
            # if "private" in pragma_list:    
            #     pub_str = ""
            #     pragma = "{." + ",".join([prg for prg in pragma_list if prg != "private"]) + ".}"
            # else:
            #     pub_str = "*"
#f = hsh(12)
#print(f)

class Dfs():
    def __init__(self, x):
        self.x = x
    def __ilshift__(self, o):
        self.__dict__ = o.__dict__     
def sdfs(z: Dfs):
    z <<= Dfs(14)

class df(int):
    def __iadd__(self, o):
        self = self.__class__(self + o)
        return self

class Canvas():
    ## 2D Buffer
    ## Images are stored in row-major order
    # Size 24 bytes
    pixels: ptr[UncheckedArray[int]]
    pixels2: ptr @ UncheckedArray[int] # type: ignore
    def __init__(self):
        self.pixels = cast[ptr @ UncheckedArray[int]](5)


@dispatch
def fun[T: SomeInteger](x: float64, y: T) -> T:
    return x + y

#@dispatch
def fun1(x: int32, z, y: float64) -> int:
    print("float")
    return x

@dispatch
def fun(x: int32, _: type[float64]) -> int:
    print("type")
    return 0

@dispatch
def fun[T](x: T, y: T) -> T:
    return x * y

# @dispatch
# def fun(x: int, y: int) -> int:
#     print("int")
#     return y

# @dispatch
# def fun(x: SomeInteger, y: SomeInteger):
#     return x + y



# h = hsh(2,8.0)
#print(fun(3, float64))
print(fun(11, 2.0))
print(fun(1.0, 20))
print(fun(3, 20))
print(fun(11.0, 2.0))
# pt = UncheckedArray(h)
# print(pt[...])
# print(pt[:])
d = 3.4
#print(math.sqrt(d))
e=3
# d =  Canvas()  
# sdf = cast[ptr @ int](5)
# print(sdf)
# cd = Dfs(12)
# print(cd.x)
# sdfs(cd)
# print(cd.x)
