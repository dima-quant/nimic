"""
Upstream changes of nimony for the converted modules: the re-pin tool (ncompiler/conversion_plan.md, "Re-pinning
nimony").

    .venv/bin/python -m nnimony.tools.upstream [TARGET] [--diff] [--out FILE]   # report what changed upstream
    .venv/bin/python -m nnimony.tools.upstream TARGET --mark lib/bif ...         # a module's diff is converted

Every converted module nnimony/<path>.py records the original it was converted from in its header:
`# source: nimony@<sha>:src/<path>.nim`. For each one the report gives the changes of that original between <sha>
and TARGET (default: origin/master of the clone): the commits touching it, a diffstat and, with --diff, the
unified diff. It also lists the files of the converted components (src/lib, src/models) that TARGET adds,
deletes or renames. A diff is applied to the Python by hand, as a conversion: the converted module isn't a
textual copy of the original. Then `--mark` moves the module's header to TARGET (resolved to its full sha).

nimony is the sibling clone (NIMONY_DIR, default ../nimony); `git fetch` it first. The tool only reads the
clone. A re-pin moves the clone and the pins (nnimony/tools/queue.py NIMONY_PIN, tests/verify_transpiled.py
DIST_PINS) once every module is marked.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
NIMONY = Path(os.environ.get("NIMONY_DIR", ROOT.parent / "nimony"))
NNIMONY = ROOT / "nnimony"
HEADER = re.compile(r"^# source: nimony@([0-9a-f]{7,40}):(\S+)$", re.M)
SKIPPED_DIRS = {"tools", "checks"}  # nnimony's own Python, no converted modules


class Module(NamedTuple):
    key: str        # the path under nnimony/ and nimony's src/, without extension: `lib/bif`
    path: Path      # nnimony/lib/bif.py
    source: str     # the original's path in the clone: `src/lib/bif.nim`
    sha: str        # the commit the module was converted from


class Drift(NamedTuple):
    module: Module
    commits: list   # `<short sha> <subject>`, oldest first
    stat: str       # `+12 -3`, "" when unchanged
    diff: str       # the unified diff of the original, "" when unchanged
    status: str     # "unchanged", "changed", "deleted", "renamed to <path>"


def _git(nimony: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(nimony), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def converted_modules(nnimony: Path = NNIMONY) -> list[Module]:
    """The converted modules and the commit each one records (a module without a header is an error)."""
    found = []
    for path in sorted(nnimony.rglob("*.py")):
        rel = path.relative_to(nnimony)
        if SKIPPED_DIRS & set(rel.parts) or path.stem == "__init__":
            continue
        match = HEADER.search(path.read_text(encoding="utf-8")[:2000])
        if match is None:
            raise SystemExit(f"{path}: no `# source: nimony@<sha>:<path>` header")
        found.append(Module(rel.with_suffix("").as_posix(), path, match.group(2), match.group(1)))
    return found


def drift(modules: list[Module], target: str, nimony: Path = NIMONY) -> list[Drift]:
    """What changed in each module's original between its commit and `target`."""
    result = []
    for m in modules:
        log = _git(nimony, "log", "--reverse", "--format=%h %s", f"{m.sha}..{target}", "--", m.source)
        commits = log.splitlines()
        exists = _git(nimony, "ls-tree", "--name-only", target, "--", m.source).strip()
        if not exists:
            moved = [line.split("\t") for line in _git(nimony, "diff", "--name-status", "-M", m.sha, target).splitlines()
                     if line.startswith("R") and line.split("\t")[1] == m.source]
            status = f"renamed to {moved[0][2]}" if moved else "deleted"
            result.append(Drift(m, commits, "", "", status))
            continue
        numstat = _git(nimony, "diff", "--numstat", m.sha, target, "--", m.source).split()
        diff = _git(nimony, "diff", m.sha, target, "--", m.source) if numstat else ""
        stat = f"+{numstat[0]} -{numstat[1]}" if numstat else ""
        result.append(Drift(m, commits, stat, diff, "changed" if numstat else "unchanged"))
    return result


def new_upstream_files(modules: list[Module], target: str, nimony: Path = NIMONY) -> tuple[list[str], list[str]]:
    """The `.nim` files `target` has in the converted components' directories that no module was converted from:
    (added since the modules' commits, there before but not converted), as `src/lib/x.nim`."""
    converted = {m.source for m in modules}
    dirs = sorted({str(Path(m.source).parent) for m in modules})

    def nim_files(commit: str) -> set:
        return {f for f in _git(nimony, "ls-tree", "-r", "--name-only", commit, "--", *dirs).splitlines()
                if f.endswith(".nim")}
    before = set().union(*(nim_files(sha) for sha in {m.sha for m in modules}))
    rest = sorted(nim_files(target) - converted)
    return [f for f in rest if f not in before], [f for f in rest if f in before]


def report(drifts: list[Drift], new_files: tuple, target: str, target_sha: str, with_diff: bool) -> str:
    changed = [d for d in drifts if d.status != "unchanged"]
    lines = [f"# nimony upstream changes for the converted modules",
             "",
             f"Target: `{target}` = `{target_sha[:12]}`. {len(changed)} of {len(drifts)} converted modules changed.",
             ""]
    pins = sorted({d.module.sha for d in drifts})
    if len(pins) > 1:
        lines += [f"Modules record {len(pins)} different commits: " + ", ".join(f"`{p[:12]}`" for p in pins), ""]
    lines += ["| Module | Status | Lines | Commits |", "|---|---|---|---|"]
    for d in drifts:
        if d.status != "unchanged":
            lines.append(f"| `{d.module.key}` | {d.status} | {d.stat} | {len(d.commits)} |")
    unchanged = [d.module.key for d in drifts if d.status == "unchanged"]
    lines += ["", f"Unchanged ({len(unchanged)}): " + ", ".join(f"`{k}`" for k in unchanged), ""]
    added, unconverted = new_files
    if added:
        lines += ["New upstream files in these directories (to queue: `python -m nnimony.tools.queue` at the new "
                  "pin):", ""] + [f"- `{f}`" for f in added] + [""]
    if unconverted:
        lines += ["Not converted, as before (legacy or not needed yet; nnimony/conversion_queue.md): "
                  + ", ".join(f"`{f}`" for f in unconverted), ""]
    for d in changed:
        lines += [f"## `{d.module.key}` ({d.status}{', ' + d.stat if d.stat else ''})", ""]
        lines += [f"- {c}" for c in d.commits] + [""]
        if with_diff and d.diff:
            lines += ["```diff", d.diff.rstrip("\n"), "```", ""]
    return "\n".join(lines)


def mark(modules: list[Module], keys: list[str], target_sha: str) -> list[str]:
    """Move the headers of the modules `keys` to `target_sha`; returns what changed."""
    by_key = {m.key: m for m in modules}
    unknown = [k for k in keys if k not in by_key]
    if unknown:
        raise SystemExit(f"not a converted module: {', '.join(unknown)}")
    done = []
    for key in keys:
        m = by_key[key]
        text = m.path.read_text(encoding="utf-8")
        old = f"# source: nimony@{m.sha}:{m.source}"
        m.path.write_text(text.replace(old, f"# source: nimony@{target_sha}:{m.source}", 1), encoding="utf-8")
        done.append(f"{key}: {m.sha[:12]} -> {target_sha[:12]}")
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("target", nargs="?", default="origin/master", help="a commit of the clone")
    parser.add_argument("--diff", action="store_true", help="include the unified diffs")
    parser.add_argument("--out", help="write the report to this file")
    parser.add_argument("--mark", nargs="+", metavar="MODULE", help="move these modules' headers to TARGET")
    args = parser.parse_args(argv)
    target_sha = _git(NIMONY, "rev-parse", "--verify", f"{args.target}^{{commit}}").strip()
    modules = converted_modules()
    if args.mark:
        print("\n".join(mark(modules, args.mark, target_sha)))
        return 0
    text = report(drift(modules, target_sha), new_upstream_files(modules, target_sha), args.target, target_sha,
                  args.diff)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
