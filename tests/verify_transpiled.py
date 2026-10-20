"""
Execution verification of converted nimic code: Python run vs transpiled + compiled Nim.

    .venv/bin/python tests/verify_transpiled.py [modules] [fidelity] [tests] [imports] [raytracer] [converters]

(no arguments = all checks; takes several minutes, the Python raytracer is the slow part)

  modules     every converted ncompiler/<m>.py is transpiled (as nimic.nimp does: import + unparse
              with the runtime type registry) and swapped into a copy of the Nim compiler sources
              (compiler/); then each is type-checked with `nim check` against the converted versions of
              its converted dependencies. The compiler's NEP-1 style check is
              switched off: nimic keeps snake_case names (accepted, see CLAUDE.md).
  raytracer   tests/nraytracer/trace_of_radiance_animation: Python run, transpile, `nim c -d:danger`,
              run; the rendered PPM frames of both runs must be byte-identical.
  converters  tests/nraytracer/test_converter_ppm_to_h264 and test_converter_h264_to_mp4 in Python
              and as compiled Nim; outputs must be byte-identical to reference.264 / reference.mp4 in
              tests/nraytracer/ncache/build/rendered_test (local, git-ignored inputs: skipped if absent).

  fidelity    nimic_translation_rules.md §2.1: every `if comptime(X)` of a converted module pairs with a
              `when X` of the original (only the test guard `__name__ == "__main__"` is unpaired), and no
              Python/Nim switches or monkey-patching (`defined("c")`, `setattr`, `globals()[...]`, `_py_*`,
              `Class.attr = proc`).
  tests       each module's tests run in Python and as compiled Nim (all modules transpiled into one
              directory with ncompiler/nim.cfg, so both use the same build profile); stdout must match.
  imports     each module that is not an include file compiles when imported (`import <m>`), the way its
              users load it.

Modules marked for rework or with open gaps in ncompiler/conversion_queue.md are reported as XFAIL
(expected failure).
Everything runs in .scratch/verify_transpiled (git-ignored). The tracked transpiled files in
tests/nraytracer/ncache are never touched (running tests/nraytracer/test_nast.py in place regenerates
them). Exit code 1 if any check fails.
"""
from __future__ import annotations

import ast
import filecmp
import os
import re
from collections import Counter
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]  # this script runs from tests/: nimic and ncompiler.tools
from ncompiler.tools.dependencies import dependencies  # noqa: E402
from nimic import transpiler  # noqa: E402
SCRATCH = ROOT / ".scratch" / "verify_transpiled"
PY = sys.executable
MODULES = sorted(p.stem for p in (ROOT / "ncompiler").glob("*.py") if p.stem != "__init__")
HARNESSES = sorted(p.stem for p in (ROOT / "ncompiler" / "tests").glob("test_*.py"))
# test scaffolding included by the harnesses (e.g. cgen_context)
TEST_SUPPORT = sorted(p.stem for p in (ROOT / "ncompiler" / "tests").glob("*.py") if not p.stem.startswith("test_"))


def _harnessed() -> set[str]:
    """Include files tested through their includer: a harness in ncompiler/tests (include("../x")) or a
    converted module that includes them (options includes packagehandling)."""
    found = set()
    sources = [ROOT / "ncompiler" / "tests" / f"{h}.py" for h in HARNESSES]
    sources += [ROOT / "ncompiler" / f"{m}.py" for m in MODULES]
    for path in sources:
        text = path.read_text()
        for names in re.findall(r"^include\(([^)]*)\)", text, flags=re.M):
            found |= {n.strip(" \"'").split("/")[-1] for n in names.split(",")}
    return found


HARNESSED = _harnessed()
QUEUE = ROOT / "ncompiler" / "conversion_queue.md"
CONVERTER_INPUTS = ROOT / "tests/nraytracer/ncache/build/rendered_test"

TRANSPILE_MODULE = """
import importlib, inspect, sys
from nimic import transpiler
from nimic.ntypesystem import _n_registry
mod = importlib.import_module(sys.argv[1])
# UTF-8 like nimic's own writer (stdout is byte-transparent: Latin-1 for chars below 0x100)
sys.stdout.buffer.write(transpiler.unparse(transpiler.parse(inspect.getsource(mod)), _n_registry)[0].encode("utf-8"))
"""
# transpile a source file (include files can't be imported on their own)
TRANSPILE_SOURCE = """
import importlib, pathlib, sys
from nimic import transpiler
from nimic.ntypesystem import _n_registry
importlib.import_module(sys.argv[2])  # registers the types, as nimic.nimp does (a harness for include files)
sys.stdout.buffer.write(transpiler.unparse(transpiler.parse(pathlib.Path(sys.argv[1]).read_text()), _n_registry)[0].encode("utf-8"))
"""
NTRANSPILE = "import importlib, sys; from nimic import ntranspile; ntranspile([importlib.import_module(sys.argv[1])])"

failures: list[str] = []
# the build the conversion targets; Python runs read it as the nim.cfg of ncompiler/
BUILD_CFG = ROOT / "ncompiler" / "nim.cfg"


def _rework_modules() -> set[str]:
    """Modules marked ⚠️ or with open gaps in the conversion queue: their failures are expected (XFAIL)."""
    if not QUEUE.exists():
        return set()
    return set(re.findall(r"^\| `(\w+)` \|[^\n]*(?:⚠️|open gaps)", QUEUE.read_text(), flags=re.M))


REWORK = _rework_modules()


def report(ok: bool, what: str, detail: str = "", module: str | None = None) -> None:
    expected = not ok and module in REWORK
    tag = "PASS" if ok else ("XFAIL" if expected else "FAIL")
    print(f"  {tag:5} {what}" + (f"  — {detail}" if detail else ""), flush=True)
    if not ok and not expected:
        failures.append(what)


# The raytracer and converters are built with `nim c -d:danger`; their Python runs emulate the same
# build (nimic's build profile: overflow checks off, `release` and `danger` defined).
NIM_BUILD_DEFINES = ("danger",)


def run(args, cwd, pythonpath=None, timeout=3600, defines=()):
    env = dict(os.environ)
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(str(p) for p in pythonpath)
    if defines:
        env["NIMIC_DEFINES"] = ",".join(defines)
    return subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=timeout)


def first_error(proc) -> str:
    out = (proc.stdout or "") + (proc.stderr or "")
    lines = [ln for ln in out.splitlines() if "Error" in ln] or out.strip().splitlines() or ["?"]
    return lines[0].replace(str(SCRATCH) + "/", "")[:200]


def copy_tree(src: Path, dst: Path) -> None:
    # skip generated/stale outputs: compare only what this run produces
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "ncache", "build"))


def nim_build(ncache: Path, module: str):
    return run(["nim", "c", *(f"-d:{d}" for d in NIM_BUILD_DEFINES), "--hints:off", "--warnings:off", "--outdir:build",
                f"{module}.nim"], ncache)


def check_modules() -> None:
    print("== converted compiler modules: transpile + nim check in compiler/", flush=True)
    work = SCRATCH / "compiler"
    shutil.copytree(ROOT / "compiler", work)
    shutil.copytree(ROOT / "src/nimic/ncode", work / "ncode")
    shutil.copy2(BUILD_CFG, work / "nim.cfg")  # the build profile of the Python runs (nimKochBootstrap)
    # every converted module replaces its original first, so a module is checked against the converted
    # versions of its converted dependencies (compiler/ may come from a newer Nim than the installed one:
    # the original llstream.nim needs system's readRawData, the converted one doesn't)
    transpiled = {}
    for m in MODULES:
        if m in HARNESSED:
            continue
        tr = run([PY, "-c", TRANSPILE_MODULE, f"ncompiler.{m}"], work, [ROOT / "src", ROOT])
        if tr.returncode != 0:
            transpiled[m] = None
            report(False, f"module {m}", "transpile: " + first_error(tr), m)
            continue
        transpiled[m] = tr.stdout
        (work / f"{m}.nim").write_text(tr.stdout)
    for m in MODULES:
        if m in HARNESSED:
            print(f"  SKIP  module {m}  — include file, checked through its harness (tests)", flush=True)
            continue
        if transpiled[m] is None:
            continue
        chk = run(["nim", "check", "--hints:off", "--warnings:off", "--styleCheck:off", f"{m}.nim"], work)
        report(chk.returncode == 0, f"module {m}", "" if chk.returncode == 0 else first_error(chk), m)


# --- fidelity: `if comptime` mirrors `when` (nimic_translation_rules.md §2.1) ---

def _norm_cond(text: str) -> str:
    text = re.sub(r"\blocal_(?=\w)", "", text)  # a private name `_x` transpiles to local_x
    text = re.sub(r"""defined\(['"]?(\w+)['"]?\)""", r"defined(\1)", text)
    text = re.sub(r"""declared\(['"]?([\w.]+)['"]?\)""", r"declared(\1)", text)
    text = text.replace("isinstance(", "is(").replace("True", "true").replace("False", "false")
    return re.sub(r"[\s()]", "", text)


def _py_conditions(tree: ast.AST) -> list[str]:
    """The `when` conditions the module's `if comptime(...)` transpile to (so `nint`, `isinstance`,
    `issubclass`, ... compare in their Nim spelling)."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp)) and "comptime(" in ast.unparse(node.test):
            if "__name__" in ast.unparse(node.test):
                continue  # test guard (the exception of §2.1)
            if isinstance(node, ast.If):
                snippet = ast.If(test=node.test, body=[ast.Pass()], orelse=[])
            else:
                snippet = ast.Assign(targets=[ast.Name("x", ast.Store())], value=node)
            module = ast.fix_missing_locations(ast.Module(body=[snippet], type_ignores=[]))
            out.extend(_nim_conditions(transpiler.unparse(module)[0]))
    return out


def _nim_conditions(text: str) -> list[str]:
    out = []
    when_chain = {}  # indentation -> whether the statement chain at it is a `when` (its `elif`s count)
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        keyword = line.split(None, 1)[0].rstrip(":")
        when_chain = {i: w for i, w in when_chain.items() if i <= indent}
        if keyword == "when":
            when_chain[indent] = True
        elif keyword not in ("elif", "else"):
            when_chain[indent] = False
        # a `when` statement or one of its `elif`s, or a `when` expression (after `=`, or as a call argument
        # after `(` / `,`)
        m = (re.match(r"^\s*when\s+(.+?):\s*(\S.*)?$", line)
             or (re.match(r"^\s*elif\s+(.+?):\s*(\S.*)?$", line) if when_chain.get(indent) else None)
             or re.search(r"[=(,]\s*when\s+(.+?):", line))
        if m and "isMainModule" not in m.group(1):
            cond = m.group(1)
            # `x is T` is spelled isinstance(x, T) in nimic
            cond = re.sub(r"(\w+)\s+is\s+(\w+)", r"is(\1,\2)", cond)
            out.append(_norm_cond(cond))
    return out


_FORBIDDEN = [
    (re.compile(r"""defined\(\s*["'](c|js|cpp|objc)["']\s*\)"""), "backend switch defined(\"c\")"),
    (re.compile(r"\bsetattr\("), "setattr"),
    (re.compile(r"\bglobals\(\)\s*\["), "globals()[...]"),
    (re.compile(r"\b_py_\w+"), "_py_* copy"),
    (re.compile(r"__name__\s*==\s*[\"']__main__[\"']\s*\)\s*\)"), "not (__name__ == '__main__')"),
]


def _monkey_patches(tree: ast.AST) -> list[str]:
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    procs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in classes
                    and isinstance(node.value, (ast.Name, ast.Lambda)) and getattr(node.value, "id", "") in procs | {""}):
                out.append(f"{t.value.id}.{t.attr} = ... (line {node.lineno})")
    return out


def check_fidelity() -> None:
    print("== fidelity: `if comptime` mirrors `when`, no Python/Nim switches", flush=True)
    for m in MODULES:
        src = (ROOT / "ncompiler" / f"{m}.py").read_text()
        nim_path = ROOT / "compiler" / f"{m}.nim"
        tree = ast.parse(src)
        problems = []
        py, nim = Counter(_py_conditions(tree)), Counter(_nim_conditions(nim_path.read_text()) if nim_path.exists() else [])
        for cond, n in (py - nim).items():
            problems.append(f"comptime without matching when: {cond}" + (f" (x{n})" if n > 1 else ""))
        for cond, n in (nim - py).items():
            problems.append(f"when not converted: {cond}" + (f" (x{n})" if n > 1 else ""))
        for rx, what in _FORBIDDEN:
            hits = [i for i, line in enumerate(src.splitlines(), 1) if rx.search(line)]
            if hits:
                problems.append(f"{what} at line(s) {', '.join(map(str, hits[:5]))}")
        problems += _monkey_patches(tree)
        report(not problems, f"fidelity {m}", "; ".join(problems)[:300], m)


# --- tests: Python vs compiled Nim, imports ---

def _transpile_all(work: Path) -> dict[str, str]:
    """Transpile every converted module into `work` (with ncode/ and ncompiler/nim.cfg); returns errors."""
    (work / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILD_CFG, work / "nim.cfg")  # same build profile as the Python runs
    errors = {}
    harness_of = {}
    includers = [(ROOT / "ncompiler" / "tests" / f"{h}.py", f"ncompiler.tests.{h}") for h in HARNESSES]
    includers += [(ROOT / "ncompiler" / f"{m}.py", f"ncompiler.{m}") for m in MODULES]
    for path, module in includers:
        for names in re.findall(r"^include\(([^)]*)\)", path.read_text(), flags=re.M):
            for n in names.split(","):
                harness_of.setdefault(n.strip(" \"'").split("/")[-1], module)
    for m in MODULES + [f"tests.{h}" for h in HARNESSES + TEST_SUPPORT]:
        importer = harness_of.get(m.split(".")[-1], f"ncompiler.{m}")
        tr = run([PY, "-c", TRANSPILE_SOURCE, str(ROOT / "ncompiler" / (m.replace(".", "/") + ".py")), importer],
                 ROOT, [ROOT / "src", ROOT])
        if tr.returncode != 0:
            errors[m] = first_error(tr)
        else:
            (work / (m.replace(".", "/") + ".nim")).write_text(tr.stdout)
    return errors


def _nim_c(work: Path, main: str, out: str):
    """Compile work/<main>.nim (main may be tests/<harness>) from its own directory."""
    path = work / f"{main}.nim"
    return run(["nim", "c", "--hints:off", "--warnings:off", "--styleCheck:off", f"--path:{work}",
                f"--path:{ROOT / 'src/nimic'}", f"--path:{ROOT / 'compiler'}", f"--nimcache:{work / ('cache_' + out)}",
                f"-o:{work / out}", path.name], path.parent)


def check_tests() -> None:
    print("== module tests: Python vs compiled Nim (same build profile)", flush=True)
    work = SCRATCH / "tests"
    errors = _transpile_all(work)
    for m in [m for m in MODULES if m not in HARNESSED] + [f"tests.{h}" for h in HARNESSES]:
        if m in errors:
            report(False, f"tests {m}", "transpile: " + errors[m], m)
            continue
        py = run([PY, "-m", f"ncompiler.{m}"], ROOT, [ROOT / "src", ROOT])
        if py.returncode != 0:
            report(False, f"tests {m}", "Python: " + first_error(py), m)
            continue
        build = _nim_c(work, m.replace(".", "/"), f"bin_{m}")
        if build.returncode != 0:
            report(False, f"tests {m}", "nim c: " + first_error(build), m)
            continue
        nim = run([work / f"bin_{m}"], ROOT)
        if nim.returncode != 0:
            report(False, f"tests {m}", f"Nim run: exit {nim.returncode} " + first_error(nim), m)
            continue
        same = py.stdout == nim.stdout
        detail = "" if same else "stdout differs: " + next(
            (f"py {a!r} / nim {b!r}" for a, b in zip(py.stdout.splitlines(), nim.stdout.splitlines()) if a != b),
            "different number of lines")
        report(same, f"tests {m}", detail[:200], m)


def check_imports() -> None:
    print("== imports: modules compile when imported (include files excluded)", flush=True)
    _, includer, _ = dependencies()
    work = SCRATCH / "imports"
    errors = _transpile_all(work)
    for m in MODULES:
        if m in includer:
            continue
        if m in errors:
            report(False, f"import {m}", "transpile: " + errors[m], m)
            continue
        (work / f"use_{m}.nim").write_text(f"import {m}\n")
        chk = run(["nim", "check", "--hints:off", "--warnings:off", "--styleCheck:off", f"--path:{work}",
                   f"--path:{ROOT / 'src/nimic'}", f"--path:{ROOT / 'compiler'}", f"use_{m}.nim"], work)
        report(chk.returncode == 0, f"import {m}", "" if chk.returncode == 0 else first_error(chk), m)


def compare_trees(a: Path, b: Path, pattern: str) -> tuple[int, list[str]]:
    files = sorted(p.relative_to(a) for p in a.rglob(pattern))
    return len(files), [str(f) for f in files if not (b / f).exists() or not filecmp.cmp(a / f, b / f, shallow=False)]


def check_raytracer() -> None:
    print("== raytracer animation: Python vs compiled Nim", flush=True)
    work = SCRATCH / "nraytracer"
    copy_tree(ROOT / "tests/nraytracer", work)
    py = run([PY, "-c", "import runpy; runpy.run_path('trace_of_radiance_animation.py', run_name='__main__')"],
             work, [ROOT / "src", work], defines=NIM_BUILD_DEFINES)
    report(py.returncode == 0, "raytracer Python run", "" if py.returncode == 0 else first_error(py))
    tr = run([PY, "-c", NTRANSPILE, "trace_of_radiance_animation"], work, [ROOT / "src", work])
    if tr.returncode != 0:
        report(False, "raytracer transpile", first_error(tr))
        return
    ncache = work / "ncache"
    build = nim_build(ncache, "trace_of_radiance_animation")
    report(build.returncode == 0, "raytracer nim c", "" if build.returncode == 0 else first_error(build))
    if build.returncode != 0:
        return
    nim = run([ncache / "build/trace_of_radiance_animation"], ncache)
    report(nim.returncode == 0, "raytracer Nim run", "" if nim.returncode == 0 else first_error(nim))
    if py.returncode == 0 and nim.returncode == 0:
        n, diff = compare_trees(work / "build", ncache / "build", "*.ppm")
        report(n > 0 and not diff, "raytracer frames Python == Nim", f"{n} frames" + (f", differ: {diff}" if diff else ""))


def check_converters() -> None:
    print("== ppm -> h264 -> mp4 converters: Python and compiled Nim vs reference files", flush=True)
    inputs = ["animation_00000.ppm", "animation_00001.ppm", "reference.264", "reference.mp4"]
    if not all((CONVERTER_INPUTS / f).exists() for f in inputs):
        print(f"  SKIP  converter inputs not found in {CONVERTER_INPUTS.relative_to(ROOT)}", flush=True)
        return
    base = SCRATCH / "conv"  # the converters use paths relative to the repo root
    work = base / "tests/nraytracer"
    copy_tree(ROOT / "tests/nraytracer", work)
    data = work / "ncache/build/rendered_test"
    data.mkdir(parents=True)
    for f in inputs:
        shutil.copy2(CONVERTER_INPUTS / f, data / f)
    steps = (("test_converter_ppm_to_h264", "reference_py.264", "reference.264"),
             ("test_converter_h264_to_mp4", "reference_py.mp4", "reference.mp4"))
    for module, out, ref in steps:
        py = run([PY, f"tests/nraytracer/{module}.py"], base, [ROOT / "src", work], defines=NIM_BUILD_DEFINES)
        ok = py.returncode == 0 and (data / out).exists() and filecmp.cmp(data / out, data / ref, shallow=False)
        report(ok, f"{module} Python == {ref}", "" if py.returncode == 0 else first_error(py))
        (data / out).unlink(missing_ok=True)
    for module, out, ref in steps:
        tr = run([PY, "-c", NTRANSPILE, module], work, [ROOT / "src", work])
        if tr.returncode != 0:
            report(False, f"{module} transpile", first_error(tr))
            continue
        build = nim_build(work / "ncache", module)
        if build.returncode != 0:
            report(False, f"{module} nim c", first_error(build))
            continue
        nim = run([work / "ncache/build" / module], base)
        ok = nim.returncode == 0 and (data / out).exists() and filecmp.cmp(data / out, data / ref, shallow=False)
        report(ok, f"{module} Nim == {ref}", "" if nim.returncode == 0 else first_error(nim))


def main() -> int:
    checks = {"modules": check_modules, "fidelity": check_fidelity, "tests": check_tests, "imports": check_imports,
              "raytracer": check_raytracer, "converters": check_converters}
    selected = sys.argv[1:] or list(checks)
    unknown = [s for s in selected if s not in checks]
    if unknown:
        print(f"unknown check(s): {unknown}; choose from {list(checks)}")
        return 2
    shutil.rmtree(SCRATCH, ignore_errors=True)
    SCRATCH.mkdir(parents=True)
    for name in selected:
        checks[name]()
    print(f"\n{'ALL PASSED' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
