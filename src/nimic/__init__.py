import importlib
import inspect as ins
import os
import re
import shutil
import sys
import types

from typing import Iterator
from nimic import transpiler
from nimic.ntypesystem import _n_registry

def import_from_path(module_name, file_path):
    """Import a module given its name and file path. Credit: pythonmorsels"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

REGEX = r'(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$'

def stream(script: str) -> Iterator[tuple[str, str]]:
    for match in re.finditer(REGEX, script):
        yield match.group('type'), ''.join(
            line[2:] if line.startswith('# ') else line[1:]
            for line in match.group('content').splitlines(keepends=True)
        )

def nimp(obj: object, srcs: dict):
    src = ins.getsource(obj)
    aast = transpiler.parse(src)
    for meta, code in stream(src):
        if meta == "nimic":
            nim_src, modules_names = transpiler.unparse(aast, _n_registry)
            srcs[obj.__name__] = nim_src
            for module_name in modules_names:
                if module_name in sys.modules and module_name not in srcs:
                    nimp(sys.modules[module_name], srcs)
        else:
            pass # TODO:look for ncode folder with nim code and copy its content to ncache

def ntranspile(args: list[str | types.ModuleType]):
    if len(args)>2 and args[1] == "-m":
        module_fname = args[2]
        main_mod = importlib.import_module(module_fname)
        target_file = main_mod.__file__
        target_dir = os.path.dirname(target_file)
    elif len(args)==2:
        target_file  = args[1]
        module_name = os.path.basename(target_file).split(".")[0]
        target_dir = os.path.dirname(target_file)
        if target_dir not in sys.path:
            sys.path.append(target_dir)
        main_mod = import_from_path(module_name, target_file)
    elif len(args)==1 and isinstance(args[0], types.ModuleType):
        main_mod = args[0]
        target_file = main_mod.__file__
        target_dir = os.path.dirname(target_file)
    else:
        raise ValueError("No target specified")

    wdir = os.path.join(target_dir, "ncache")
    if not os.path.exists(wdir):
        os.makedirs(wdir)
    nimic_wd = os.path.dirname(os.path.realpath(__file__))
    code_dir = os.path.join(nimic_wd, "ncode")
    if not os.path.exists(os.path.join(wdir, "ncode")):
        shutil.copytree(code_dir, os.path.join(wdir, "ncode"))
    srcs = {}
    nimp(main_mod, srcs)
    for k, v in srcs.items():
        fname = os.path.join(wdir, k + ".nim")
        with open(fname, "w") as f:
            f.write(v)