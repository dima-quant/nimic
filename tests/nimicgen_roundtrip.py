"""The round trip nimic -> Nim -> nimic over the converted nimony modules (nimicgen's phase 4).

For each module of `nnimony/` (`lib/bitabs`, ...):

1. transpile it, as `tests/verify_transpiled.py` does (its `TRANSPILE_MODULE`), into a copy of the nimony clone's
   `src/` (so its imports resolve);
2. run nimicgen (`nimony-nimic/bin/nimicgen`, the nimic backend for nimony) on the transpiled module;
3. compare nimicgen's nimic with the module:
   - **Python:** both parsed with `ast` and written back with `ast.unparse`, after the canonical steps of
     `Canon` (comments and docstring text dropped; the rules' free choices made equal: `x.copy()` / `copy(x)`,
     the order of a run of import statements and overload sets, rules §13.5);
   - **Nim** (`--nim`): nimicgen's output, put in place of the module in a copy of `nnimony/`, transpiled
     again and compared line by line with the transpiled module. Same Nim means every Python difference
     left is a free choice, a lossy rule, or a hand conversion that drifted from the rules; different Nim
     means a nimicgen bug (or a non-injective rule); no Nim means the output fails to import or fails the
     import checks.

4. on request, compare what they do (`--run`): each module's self-test (its `__main__` block, with its
   `# test-args:`) runs in a copy of `nnimony/` with nimicgen's module in place of the hand one, and its exit code
   and stdout are compared with the hand module's run (which `tests/verify_transpiled.py nimony` checks against
   compiled Nim, and for the 34 modules of the same Nim nimicgen's module transpiles to that same Nim: the question
   is whether nimicgen's Python runs like its Nim). A deviation is grouped by its reason: the exception a run ended
   with (an import check, `ValueCopyError`, `AttributeError`, ...), a different output, a timeout. The slow
   self-tests (`tests/slow_selftests.txt`) are skipped unless named or `--all` is given. `--integration` also runs
   `nnimony/checks/nif_roundtrip.py` (nifreader, nifbuilder, bif, nifcore together) with every module nimicgen
   writes in place at once, against the hand modules' run (Python only, a few minutes each).

The issues it found are in `nnimony/nimony_check_issues.md` (issues 18-31). Unlike the checks of
`tests/verify_transpiled.py` it is no pass/fail check: differences are expected (the free choices, the open
issues), and it needs nimicgen, built in a separate project.

Usage, from the Ndsl root:

    .venv/bin/python tests/nimicgen_roundtrip.py [--nim] [--run [--all] [--integration]] [lib/m ...]

Paths: `NIMONY_NIMIC_DIR` (default `../nimony-nimic`: `bin/nimicgen`, built there with
`bin/nimony c --nimcache:nimcache/nimicgen_build --out:bin/nimicgen src/nimicgen/nimicgen.nim`) and
`NIMONY_DIR` (default `../nimony`, the pinned clone, only read; as in `tests/verify_transpiled.py`). Work files go to
`.scratch/nimicgen_roundtrip/`: `src/` (the transpiled tree), `set.txt` (nimicgen's `--set:`, the conversion set
the methods rule is judged over: every converted module, also when only a few are compared), `pkg/` (the copy
of `nnimony/`, made afresh on each run), `run/` (`--run`: another copy of `nnimony/`, `tmp/` for the tests'
`{tmp}`), `out/` (per module: nimicgen's `.py`, the Python `.diff`, the Nim `.nimdiff`, the run's `.run`). Report only: the exit code is 0 unless a
step can't run.
"""
from __future__ import annotations

import ast
import difflib
import filecmp
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import verify_transpiled as vt
from verify_transpiled import NNIMONY, ROOT, TRANSPILE_MODULE

NIMONY_NIMIC = Path(os.environ.get("NIMONY_NIMIC_DIR", ROOT.parent / "nimony-nimic")).resolve()
NIMONY = vt.NIMONY_SRC.parent.resolve()
NIMICGEN = NIMONY_NIMIC / "bin" / "nimicgen"
WORK = ROOT / ".scratch" / "nimicgen_roundtrip"
PY = sys.executable
# the modules whose originals nimony itself rejects (nimony_check_issues.md, issues 11, 13, 14)
UPSTREAM = {"lib/nifqueries"}


# ── the canonical form ──────────────────────────────────────────────────────

class Canon(ast.NodeTransformer):
    """What the comparison takes as equal. Comments are gone with the parse; a docstring keeps only its
    pragma part, comma-spaced. Of the rules' free choices (nimony_check_issues.md, issues 29, 46) only
    `x.copy()` / `copy(x)` are made equal, both valid spellings. The others have one canonical form (§13.5:
    `string("x")` or a bare "x" by position, `ch('x')`, `seq[T]`, `Tset[T]`, `echo(x)`, `float64`, a set in
    import order), which both sides must write: a difference is a deviation. The order of a run of import
    statements and sets is free (§13.5): `sort_imports` sorts it."""

    def _doc(self, node):
        self.generic_visit(node)
        b = node.body
        if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) and isinstance(b[0].value.value, str):
            m = re.match(r"\{\..*?\.\}", b[0].value.value.strip(), re.S)
            if m:
                b[0].value.value = re.sub(r"\s*,\s*", ", ", " ".join(m.group(0).split()))
                if len(b) == 2 and isinstance(b[1], ast.Pass):
                    del b[1]
            else:
                del b[0]
                if not b:
                    b.append(ast.Pass())
        return node

    visit_FunctionDef = visit_ClassDef = visit_Module = _doc

    def visit_Call(self, node):
        self.generic_visit(node)
        f = node.func
        # rule:copy: x.copy() and copy(x) are one copy (both `x` in Nim); nimicgen writes copy(x) for a scalar
        if isinstance(f, ast.Attribute) and f.attr == "copy" and not node.args and not node.keywords:
            node = ast.Call(func=ast.Name("copy", ast.Load()), args=[f.value], keywords=[])
            f = node.func
        return node


def _is_main_test(t) -> bool:
    return (isinstance(t, ast.Call) and isinstance(t.func, ast.Name) and t.func.id == "comptime" and len(t.args) == 1
            and ast.unparse(t.args[0]) in ("__name__ == '__main__'", '__name__ == "__main__"'))


def _stays_toplevel(stmt) -> bool:
    """The partition of rule:mainproc (the transpiler's `_stays_toplevel`)."""
    if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
        return True
    if (isinstance(stmt, ast.With) and len(stmt.items) == 1 and isinstance(stmt.items[0].context_expr, ast.Name)
            and stmt.items[0].context_expr.id == "const"):
        return True
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id in ("importFrom", "importExcept", "pragma"))


def _declares_any(stmt, names) -> bool:
    if not (isinstance(stmt, ast.With) and len(stmt.items) == 1 and isinstance(stmt.items[0].context_expr, ast.Name)
            and stmt.items[0].context_expr.id in ("var", "let")):
        return False
    return any(isinstance(t, ast.Name) and t.id in names for s in stmt.body if isinstance(s, (ast.Assign, ast.AnnAssign))
               for t in (s.targets if isinstance(s, ast.Assign) else [s.target]))


def main_order(tree):
    """rule:mainproc moves a main block's definitions (and the variables its procs use) before its other
    statements (issue 25): the source's main blocks in that order."""
    for node in tree.body:
        if isinstance(node, ast.If) and _is_main_test(node.test) and not node.orelse:
            used = {n.id for s in node.body if isinstance(s, (ast.FunctionDef, ast.ClassDef))
                    for n in ast.walk(s) if isinstance(n, ast.Name)}
            top = [s for s in node.body if _stays_toplevel(s) or _declares_any(s, used)]
            node.body = top + [s for s in node.body if not any(s is x for x in top)]
    return tree


def _import_rank(stmt) -> int | None:
    """The place of an import statement or an overload set in its sorted run (None: not one). Core star imports
    first, then module imports, name imports, the sets last: the order in which Python's bindings stay those the
    import check accepts (a name import after the star import it would rebind, a set after its imports)."""
    if isinstance(stmt, ast.ImportFrom):
        if stmt.module == "__future__":
            return 0
        if stmt.names[0].name == "*":
            return 1
        return 2 if stmt.level and not stmt.module or stmt.module in ("nimic.std",) else 3
    if isinstance(stmt, ast.Import):
        return 2
    if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id in ("importFrom", "importExcept")):
        return 2 if len(stmt.value.args) == 1 else 3
    if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "overloads"):
        return 4
    return None


def sort_imports(tree):
    """Each run of import statements and overload sets in each statement list, sorted (`_import_rank`, then
    the text): their order is free (rules §13.5) where the bindings stay the same."""
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field, None)
            if not isinstance(stmts, list):
                continue
            i = 0
            while i < len(stmts):
                if _import_rank(stmts[i]) is None:
                    i += 1
                    continue
                j = i
                while j < len(stmts) and _import_rank(stmts[j]) is not None:
                    j += 1
                stmts[i:j] = sorted(stmts[i:j], key=lambda s: (_import_rank(s), ast.unparse(s)))
                i = j
    return tree


def canon(text: str) -> list[str]:
    return ast.unparse(Canon().visit(sort_imports(main_order(ast.parse(text))))).splitlines()


def nim_lines(text: str) -> list[str]:
    return [re.sub(r"\bfloat64\b", "float", l.rstrip()) for l in text.splitlines() if l.strip()]


def changed(d: list[str]) -> int:
    return sum(1 for l in d if l[:1] in "+-" and l[:3] not in ("+++", "---"))


# ── the steps ───────────────────────────────────────────────────────────────

def error_lines(stderr: str) -> list[str]:
    """The exception a failed run ended with and its message lines, not the tail of stderr: CPython's
    "Exception ignored in" reports at exit (a `__del__` during shutdown) come after it and hid it."""
    lines = stderr.strip().splitlines()
    cut = next((i for i, l in enumerate(lines) if l.startswith("Exception ignored")), len(lines))
    lines = lines[:cut] or lines
    heads = [i for i, l in enumerate(lines) if re.match(r"(?:[A-Za-z_][\w.]*)?(Error|Exception|Exit)\b", l)]
    if not heads:
        return lines[-3:] or ["?"]
    i = heads[-1]
    j = i + 1
    while j < len(lines) and lines[j].startswith(" "):
        j += 1
    return lines[i:j]


def transpile(module: str, pythonpath: list[Path], cwd: Path, env_extra: dict | None = None):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(p) for p in pythonpath), NIMONY_DIR=str(NIMONY))
    env.update(env_extra or {})
    return subprocess.run([PY, "-c", TRANSPILE_MODULE, module], cwd=cwd, capture_output=True, text=True, env=env)


def prepare(mods: list[str]) -> dict[str, str]:
    """Transpile `mods` into a fresh copy of nimony's src/; returns the modules that don't transpile."""
    src = WORK / "src"
    shutil.rmtree(src, ignore_errors=True)
    shutil.copytree(NIMONY / "src", src)
    errors = {}
    for m in mods:
        p = transpile("nnimony." + m.replace("/", "."), [ROOT / "src", ROOT], ROOT)
        if p.returncode != 0:
            errors[m] = " ".join(l.strip() for l in error_lines(p.stderr))
        else:
            (src / (m + ".nim")).write_text(p.stdout)
    return errors


def write_set(mods: list[str], errors: dict[str, str]) -> Path:
    """The conversion set for nimicgen's `--set:` (rules §4, methods rule: judged over the converted
    modules): the transpiled `.nim` of every module that transpiles."""
    path = WORK / "set.txt"
    path.write_text("".join(f"{WORK / 'src' / (m + '.nim')}\n" for m in mods if m not in errors))
    return path


def nimicgen(m: str, dst: Path) -> list[str]:
    """Run nimicgen on the transpiled `m`, with the conversion set; its notes (stderr)."""
    py = (NNIMONY / (m + ".py")).read_text()
    header = re.search(r"^# source: (\S+)", py, re.M)
    args = [str(NIMICGEN), f"--path:{ROOT / 'src' / 'nimic'}", f"--set:{WORK / 'set.txt'}"]
    if header:
        args.append(f"--source:{header.group(1)}")
    p = subprocess.run(args + [str(WORK / "src" / (m + ".nim")), str(dst)], cwd=WORK, capture_output=True, text=True)
    return [l for l in p.stderr.splitlines() if l.strip()]


def nim_check(m: str, generated: Path) -> tuple[int, list[str]]:
    """Transpile nimicgen's output again in place of `m` (in a copy of nnimony/): the Nim lines that differ
    from the transpiled module, -1 when it doesn't transpile."""
    pkg = WORK / "pkg"
    if not pkg.exists():
        shutil.copytree(NNIMONY, pkg / "nnimony", ignore=shutil.ignore_patterns("__pycache__", "*.md"))
    target = pkg / "nnimony" / (m + ".py")
    original = target.read_text()
    target.write_text(generated.read_text())
    try:
        p = transpile("nnimony." + m.replace("/", "."), [pkg, ROOT / "src"], pkg)
    finally:
        target.write_text(original)
    if p.returncode != 0:
        return -1, error_lines(p.stderr)
    want = nim_lines((WORK / "src" / (m + ".nim")).read_text())
    d = list(difflib.unified_diff(want, nim_lines(p.stdout), "transpiled module", "transpiled nimicgen", n=1,
                                  lineterm=""))
    return changed(d), d


# ── what they do (--run, --integration) ─────────────────────────────────────

RUN_TIMEOUT = 900  # seconds per self-test run


def _env(pkg: Path) -> dict:
    """The environment of a run in the copy `pkg` of nnimony/: no bytecode written (a module swapped in place
    within the same second would reuse the other's)."""
    return dict(os.environ, PYTHONPATH=os.pathsep.join([str(pkg), str(ROOT / "src")]), NIMONY_DIR=str(NIMONY),
                PYTHONDONTWRITEBYTECODE="1")


def fresh_copy(pkg: Path) -> Path:
    shutil.rmtree(pkg, ignore_errors=True)
    shutil.copytree(NNIMONY, pkg / "nnimony", ignore=shutil.ignore_patterns("__pycache__"))
    return pkg


def has_tests(m: str) -> bool:
    return any(isinstance(n, ast.If) and _is_main_test(n.test) for n in ast.parse((NNIMONY / (m + ".py")).read_text()).body)


def self_test(m: str, pkg: Path) -> subprocess.CompletedProcess | None:
    """The module's self-test as `tests/verify_transpiled.py nimony` runs it (from the nimony clone, with its
    `# test-args:`, `{tmp}` a fresh directory, the same for both runs); None on a timeout."""
    tmp = WORK / "run" / "tmp" / m.replace("/", "_")
    args = vt._test_args(NNIMONY / (m + ".py"), tmp)
    try:
        return subprocess.run([PY, "-m", "nnimony." + m.replace("/", "."), *args], cwd=NIMONY, env=_env(pkg),
                              capture_output=True, text=True, timeout=RUN_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None


def reason(p: subprocess.CompletedProcess | None) -> str:
    """A failed run's reason, the exception it ended with, made general enough to group runs by: paths, numbers
    and quoted names replaced."""
    if p is None:
        return f"timeout ({RUN_TIMEOUT}s)"
    lines = error_lines(p.stderr)
    head = lines[0].strip()
    if head.endswith(":") and len(lines) > 1:  # the import checks: the first problem's kind (`importorder: ...`)
        head += " " + re.sub(r"^\S+:\d+: ", "", lines[1].strip()).split(":")[0]
    head = re.sub(r"(?:/[\w.+-]+)+(?::\d+)?", "<path>", head)
    head = re.sub(r"(['`\"])[^'`\"]*\1", r"\1…\1", head)
    head = re.sub(r"\b\d+\b", "N", head)
    return head[:110] if head else f"exit code {p.returncode}"


def compare_runs(ref, got) -> tuple[str | None, list[str]]:
    """(None: the same; else the reason, and the lines of the `.run` report)."""
    if got is not None and got.returncode == ref.returncode and got.stdout == ref.stdout:
        return None, []
    detail = [f"hand: exit {ref.returncode}", f"nimicgen: " + ("timeout" if got is None else f"exit {got.returncode}")]
    if got is not None and got.returncode != 0 and ref.returncode == 0:
        return reason(got), detail + error_lines(got.stderr)
    if got is None:
        return reason(None), detail
    d = list(difflib.unified_diff(ref.stdout.splitlines(), got.stdout.splitlines(), "hand", "nimicgen", n=1,
                                  lineterm=""))
    first = next((l for l in d if l[:1] == "+" and not l.startswith("+++")), "")
    return "different output", detail + d[:60] + ([f"... ({len(d)} diff lines)"] if len(d) > 60 else []) + (
        [f"first: {first}"] if first else [])


def run_module(m: str, generated: Path, pkg: Path) -> tuple[str | None, list[str]]:
    """The self-test of `m` with the hand module, then with nimicgen's in its place."""
    target = pkg / "nnimony" / (m + ".py")
    hand = target.read_text()
    ref = self_test(m, pkg)
    if ref is None or ref.returncode != 0:
        return "the hand module's self-test fails", [reason(ref)]
    target.write_text(generated.read_text())
    try:
        got = self_test(m, pkg)
    finally:
        target.write_text(hand)
    return compare_runs(ref, got)


def integration(generated: dict[str, Path]) -> None:
    """nnimony/checks/nif_roundtrip.py over the nimony clone's .nif files, with the hand modules and with every
    module nimicgen wrote in place at once: the stdout and the files written must be the same."""
    pkg = fresh_copy(WORK / "integration")
    corpus = vt._nif_corpus()
    runs = {}
    for side in ("hand", "nimicgen"):
        if side == "nimicgen":
            for m, path in generated.items():
                (pkg / "nnimony" / (m + ".py")).write_text(path.read_text())
        out = WORK / "integration_out" / side
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        try:
            runs[side] = subprocess.run([PY, "-m", vt.ROUNDTRIP, *map(str, corpus), str(out)], cwd=ROOT, env=_env(pkg),
                                        capture_output=True, text=True, timeout=3600)
        except subprocess.TimeoutExpired:
            runs[side] = None
    ref, got = runs["hand"], runs["nimicgen"]
    if ref is None or ref.returncode != 0:
        print(f"integration: the hand modules' run fails: {reason(ref)}")
        return
    why, detail = compare_runs(ref, got)
    hand_out, gen_out = WORK / "integration_out" / "hand", WORK / "integration_out" / "nimicgen"
    files = sorted(f.name for f in hand_out.iterdir())
    differ = [n for n in files if not (gen_out / n).exists() or not filecmp.cmp(hand_out / n, gen_out / n, shallow=False)]
    (WORK / "out" / "integration.run").write_text("\n".join(detail + [f"files differ: {n}" for n in differ]) + "\n")
    print(f"integration (nif_roundtrip, {len(corpus)} files, {len(generated)} modules of nimicgen): "
          + ("same" if why is None and not differ else f"{why or 'same output'}; {len(differ)} of {len(files)} files differ"))


def main() -> int:
    nim = "--nim" in sys.argv
    run = "--run" in sys.argv
    named = [a for a in sys.argv[1:] if not a.startswith("--")]
    every = vt._nnimony_modules()
    mods = named or every
    if not NIMICGEN.exists():
        print(f"no nimicgen at {NIMICGEN} (set NIMONY_NIMIC_DIR)")
        return 2
    if not (NIMONY / "src").is_dir():
        print(f"no nimony clone at {NIMONY} (set NIMONY_DIR)")
        return 2
    WORK.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(WORK / "pkg", ignore_errors=True)
    out = WORK / "out"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    errors = prepare(every)  # all of them, also for a few: the conversion set is every converted module
    write_set(every, errors)
    py_equal = nim_equal = total = 0
    generated: dict[str, Path] = {}
    runs: dict[str, str | None] = {}  # module -> None (the same) or the reason it deviates
    skipped: list[str] = []
    pkg = fresh_copy(WORK / "run" / "pkg") if run else None
    for m in mods:
        name = m.replace("/", "_")
        up = "  (upstream)" if m in UPSTREAM else ""
        if m in errors:
            print(f"FAIL {m}: doesn't transpile: {errors[m]}{up}")
            continue
        dst = out / (name + ".py")
        notes = nimicgen(m, dst)
        if not dst.exists():
            print(f"FAIL {m}: nimicgen: {' '.join(notes)[:200]}{up}")
            continue
        generated[m] = dst
        try:
            d = list(difflib.unified_diff(canon((NNIMONY / (m + ".py")).read_text()), canon(dst.read_text()),
                                          "source", "nimicgen", n=1, lineterm=""))
        except SyntaxError as e:
            print(f"FAIL {m}: nimicgen's output: {e}{up}")
            continue
        (out / (name + ".diff")).write_text("\n".join(d + notes) + "\n")
        n = changed(d)
        total += n
        py_equal += n == 0
        extra = ""
        if nim:
            nn, nd = nim_check(m, dst)
            (out / (name + ".nimdiff")).write_text("\n".join(nd) + "\n")
            nim_equal += nn == 0
            why = (nd[1] if len(nd) > 1 else nd[0] if nd else "?").strip().replace(str(WORK / "pkg") + "/", "")
            extra = "  nim: " + (f"doesn't transpile ({why[:160]})" if nn < 0 else "same" if nn == 0
                                 else f"{nn} lines differ")
        if run:
            slow = "nnimony." + m.replace("/", ".") in vt.SLOW and m not in named and "--all" not in sys.argv
            if slow or not has_tests(m):
                skipped.append(m)
                extra += "  run: skipped (" + ("slow" if slow else "no self-test") + ")"
            else:
                why, detail = run_module(m, dst, pkg)
                runs[m] = why
                (out / (name + ".run")).write_text("\n".join(detail) + "\n")
                extra += "  run: " + ("same" if why is None else why[:100])
        print(f"{'PASS' if n == 0 else 'DIFF'} {m}: {n} lines differ, {len(notes)} notes{extra}{up}", flush=True)
    print(f"{py_equal} of {len(mods)} equal in Python" + (f", {nim_equal} in Nim" if nim else "")
          + f"; {total} differing lines")
    if run:
        same = sum(why is None for why in runs.values())
        print(f"run: {same} of {len(runs)} self-tests behave the same as the hand module's"
              + (f" ({len(skipped)} skipped: {', '.join(skipped)})" if skipped else ""))
        groups: dict[str, list[str]] = {}
        for m, why in runs.items():
            if why is not None:
                groups.setdefault(why, []).append(m)
        for why, ms in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(ms):3}  {why}  ({', '.join(ms)})")
    if "--integration" in sys.argv:
        integration(generated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
