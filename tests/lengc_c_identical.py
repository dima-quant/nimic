"""Ad hoc check (not part of run_selftests.py / verify_transpiled.py: it takes 10–30 minutes): lengc converted by
nimicgen runs in Python and must write the same C (or LLVM IR, `--backend llvm`) as nimony's compiled lengc, byte
for byte, for every input.

    .venv/bin/python tests/lengc_c_identical.py                      # every *.c.nif of the run directory
    .venv/bin/python tests/lengc_c_identical.py cpuf8djhu sysvq0asl  # some inputs (module names)
    .venv/bin/python tests/lengc_c_identical.py --jobs 4 --timeout 900
    .venv/bin/python tests/lengc_c_identical.py --backend llvm       # `lengc llvm`: the .ll files

Inputs (local, not in git): `.scratch/lengc/run/*.c.nif` (with their `.idx.nif`), produced by nimony for its own
modules. The Python lengc: the project's `nnimony/lengc/` (`--pkg`: another directory holding an `nnimony/`, e.g. a
copy with a regenerated lengc). The compiled lengc: nimony's `bin/lengc` at the pinned commit (`--lengc`, default
`$NIMONY_NIMIC_DIR/bin/lengc`, else `.scratch/repin/nimony_master/bin/lengc`). Phase C milestones: all 61 inputs
byte-identical in C (2026-11-10)."""
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".scratch" / "lengc" / "run"
PKG = ROOT
EXT = {"c": "c", "llvm": "ll"}  # backend -> extension of its output
PY = ROOT / ".venv" / "bin" / "python"


def default_lengc() -> Path:
    base = os.environ.get("NIMONY_NIMIC_DIR")
    return Path(base) / "bin" / "lengc" if base else ROOT / ".scratch" / "repin" / "nimony_master" / "bin" / "lengc"


def check(name: str, run: Path, pkg: Path, lengc: Path, out: Path, timeout: int,
          backend: str = "c") -> tuple[str, float, str]:
    """One input through both lengcs; (name, Python seconds, result)."""
    nif = run / f"{name}.c.nif"
    nim_dir, py_dir = out / "nim" / name, out / "py" / name
    nim_dir.mkdir(parents=True), py_dir.mkdir(parents=True)
    nim = subprocess.run([str(lengc), backend, f"--nimcache:{nim_dir}", str(nif)], cwd=run, capture_output=True,
                         text=True)
    if nim.returncode != 0:
        return name, 0.0, f"compiled lengc failed: {(nim.stderr or nim.stdout).strip()[-200:]}"
    # both run in the input directory: a relative source path in the NIF is made absolute against it (DIFile)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(pkg.resolve()))))
    start = time.monotonic()
    try:
        py = subprocess.run([str(PY), "-m", "nnimony.lengc.lengc", backend, f"--nimcache:{py_dir}", str(nif)], cwd=run,
                            env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return name, time.monotonic() - start, f"TIMEOUT after {timeout}s"
    took = time.monotonic() - start
    produced, expected = py_dir / f"{name}.{EXT[backend]}", nim_dir / f"{name}.{EXT[backend]}"
    if py.returncode != 0 or not produced.exists():
        last = [line for line in (py.stderr or py.stdout).splitlines() if line.strip(" ~^")]
        return name, took, f"FAIL: {last[-1][:200] if last else f'exit {py.returncode}'}"
    if produced.read_bytes() == expected.read_bytes():
        return name, took, "IDENTICAL"
    diff = subprocess.run(["diff", str(produced), str(expected)], capture_output=True, text=True).stdout
    return name, took, f"DIFF: {sum(line[:1] in '<>' for line in diff.splitlines())} lines"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="*", help="inputs by module name (default: all of the run directory)")
    parser.add_argument("--run", type=Path, default=RUN, help="directory of the *.c.nif inputs")
    parser.add_argument("--pkg", type=Path, default=PKG, help="directory holding the Python lengc's nnimony/")
    parser.add_argument("--lengc", type=Path, default=default_lengc(), help="nimony's compiled lengc")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per input in Python")
    parser.add_argument("--backend", choices=sorted(EXT), default="c", help="lengc's command: c (default) or llvm")
    args = parser.parse_args()
    for needed in (args.run, args.pkg / "nnimony" / "lengc", args.lengc):
        if not needed.exists():
            print(f"missing: {needed}")
            return 2
    names = args.names or sorted((p.name[:-len(".c.nif")] for p in args.run.glob("*.c.nif")
                                  if not p.name.endswith(".idx.nif")), key=lambda n: (args.run / f"{n}.c.nif").stat().st_size)
    out = Path(tempfile.mkdtemp(prefix=f"lengc_{args.backend}_identical_"))
    try:
        with ThreadPoolExecutor(args.jobs) as pool:
            results = list(pool.map(lambda n: check(n, args.run, args.pkg, args.lengc, out, args.timeout, args.backend), names))
    finally:
        shutil.rmtree(out, ignore_errors=True)
    for name, took, result in results:
        print(f"{name:14} {took:7.1f}s  {result}")
    same = sum(result == "IDENTICAL" for _, _, result in results)
    print(f"{same}/{len(results)} byte-identical")
    return 0 if same == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
