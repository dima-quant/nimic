"""
Self-tests of the converted modules: each module's `__main__` tests run in Python (`python -m <module>`), the way
tests/verify_transpiled.py's `tests` and `nimony` checks run them (without the Nim side).

    .venv/bin/python tests/run_selftests.py [--all] [<module> ...]

  ncompiler   every ncompiler/<m>.py that is no include file, and the harnesses ncompiler/tests/test_*.py
  nnimony     every nnimony/lib and nnimony/models module, run from the nimony clone with its `# test-args:`

The modules listed in tests/slow_selftests.txt take most of the run time: they are skipped unless --all is given
(before a commit). Named modules (`nnimony.lib.nifcoreparse`) run alone, slow or not: a change that concerns
them. Prints a FAIL line per failing module, the slowest modules (to keep the list current) and a summary;
exit code 1 if any fails.
"""
from __future__ import annotations

import sys
import time

import verify_transpiled as vt


def _selftests() -> list[tuple[str, list, object]]:
    """(module, extra arguments, working directory) of every self-test."""
    found = [(f"ncompiler.{m}", [], vt.ROOT) for m in vt.MODULES if m not in vt.HARNESSED]
    found += [(f"ncompiler.tests.{h}", [], vt.ROOT) for h in vt.HARNESSES]
    for key in vt._nnimony_modules():
        tmp = vt.SCRATCH / "selftests_tmp" / key.replace("/", "_")
        found.append(("nnimony." + key.replace("/", "."), vt._test_args(vt.NNIMONY / f"{key}.py", tmp),
                      vt.NIMONY_SRC.parent))
    return found


def main() -> int:
    args = sys.argv[1:]
    named = [a for a in args if a != "--all"]
    tests = _selftests()
    unknown = sorted(set(named) - {m for m, _, _ in tests})
    if unknown:
        print(f"unknown module(s): {unknown}")
        return 2
    if named:
        tests = [t for t in tests if t[0] in named]
    elif "--all" not in args:
        skipped = [t[0] for t in tests if t[0] in vt.SLOW]
        tests = [t for t in tests if t[0] not in vt.SLOW]
        print(f"skipped {len(skipped)} slow self-tests (tests/slow_selftests.txt; --all runs them)", flush=True)
    failed, seconds = [], {}
    for module, extra, cwd in tests:
        start = time.monotonic()
        proc = vt.run([vt.PY, "-m", module, *extra], cwd, [vt.ROOT / "src", vt.ROOT])
        seconds[module] = time.monotonic() - start
        if proc.returncode != 0:
            failed.append(module)
            print(f"FAIL: {module}  — {vt.first_error(proc)}", flush=True)
    total = sum(seconds.values())
    slowest = sorted(seconds, key=seconds.get, reverse=True)[:8]
    print("slowest: " + ", ".join(f"{m} {seconds[m]:.0f}s" for m in slowest))
    print(f"{len(tests) - len(failed)}/{len(tests)} passed in {total:.0f}s"
          + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
