"""
Execution verification of converted nimic code: Python run vs transpiled + compiled Nim.

    .venv/bin/python tests/verify_transpiled.py [modules] [raytracer] [converters]

(no arguments = all three checks; takes several minutes, the Python raytracer is the slow part)

  modules     each converted ncompiler/<m>.py is transpiled (as nimic.nimp does: import + unparse
              with the runtime type registry), swapped into a copy of the Nim compiler sources
              (compiler/) and type-checked with `nim check`. The compiler's NEP-1 style check is
              switched off: nimic keeps snake_case names (accepted, see CLAUDE.md).
  raytracer   tests/nraytracer/trace_of_radiance_animation: Python run, transpile, `nim c -d:danger`,
              run; the rendered PPM frames of both runs must be byte-identical.
  converters  tests/nraytracer/test_converter_ppm_to_h264 and test_converter_h264_to_mp4 in Python
              and as compiled Nim; outputs must be byte-identical to reference.264 / reference.mp4 in
              tests/nraytracer/ncache/build/rendered_test (local, git-ignored inputs: skipped if absent).

Everything runs in .scratch/verify_transpiled (git-ignored). The tracked transpiled files in
tests/nraytracer/ncache are never touched (running tests/nraytracer/test_nast.py in place regenerates
them). Exit code 1 if any check fails.
"""
from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRATCH = ROOT / ".scratch" / "verify_transpiled"
PY = sys.executable
MODULES = ("prefixmatches wordrecg idents platform pathutils nimpaths ropes llstream lineinfos options msgs "
           "bitsets hlo inliner aliasanalysis ccgreset rodutils btrees jstypes saturate nodekinds nversion "
           "packagehandling ccgthreadvars sinkparameter_inference sourcemap cbuilderexprs").split()
CONVERTER_INPUTS = ROOT / "tests/nraytracer/ncache/build/rendered_test"

TRANSPILE_MODULE = """
import importlib, inspect, sys
from nimic import transpiler
from nimic.ntypesystem import _n_registry
mod = importlib.import_module(sys.argv[1])
print(transpiler.unparse(transpiler.parse(inspect.getsource(mod)), _n_registry)[0])
"""
NTRANSPILE = "import importlib, sys; from nimic import ntranspile; ntranspile([importlib.import_module(sys.argv[1])])"

failures: list[str] = []


def report(ok: bool, what: str, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {what}" + (f"  — {detail}" if detail else ""), flush=True)
    if not ok:
        failures.append(what)


def run(args, cwd, pythonpath=None, timeout=3600):
    env = dict(os.environ)
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(str(p) for p in pythonpath)
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
    return run(["nim", "c", "-d:danger", "--hints:off", "--warnings:off", "--outdir:build", f"{module}.nim"], ncache)


def check_modules() -> None:
    print("== converted compiler modules: transpile + nim check in compiler/", flush=True)
    work = SCRATCH / "compiler"
    shutil.copytree(ROOT / "compiler", work)
    shutil.copytree(ROOT / "src/nimic/ncode", work / "ncode")
    for m in MODULES:
        original = (work / f"{m}.nim").read_text()
        tr = run([PY, "-c", TRANSPILE_MODULE, f"ncompiler.{m}"], work, [ROOT / "src", ROOT])
        if tr.returncode != 0:
            report(False, f"module {m}", "transpile: " + first_error(tr))
            continue
        (work / f"{m}.nim").write_text(tr.stdout)
        chk = run(["nim", "check", "--hints:off", "--warnings:off", "--styleCheck:off", f"{m}.nim"], work)
        report(chk.returncode == 0, f"module {m}", "" if chk.returncode == 0 else first_error(chk))
        (work / f"{m}.nim").write_text(original)


def compare_trees(a: Path, b: Path, pattern: str) -> tuple[int, list[str]]:
    files = sorted(p.relative_to(a) for p in a.rglob(pattern))
    return len(files), [str(f) for f in files if not (b / f).exists() or not filecmp.cmp(a / f, b / f, shallow=False)]


def check_raytracer() -> None:
    print("== raytracer animation: Python vs compiled Nim", flush=True)
    work = SCRATCH / "nraytracer"
    copy_tree(ROOT / "tests/nraytracer", work)
    py = run([PY, "-c", "import runpy; runpy.run_path('trace_of_radiance_animation.py', run_name='__main__')"],
             work, [ROOT / "src", work])
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
        py = run([PY, f"tests/nraytracer/{module}.py"], base, [ROOT / "src", work])
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
    checks = {"modules": check_modules, "raytracer": check_raytracer, "converters": check_converters}
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
