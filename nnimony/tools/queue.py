"""
Conversion queue of nimony (Nim 3) sources, for the conversion into nnimony/.

    .venv/bin/python -m nnimony.tools.queue          # rewrite nnimony/conversion_queue.md

nimony is the sibling clone (NIMONY_DIR, default ../nimony) at the commit pinned in NIMONY_PIN; the plan is
ncompiler/conversion_plan.md. Modules are keyed by their path under nimony's src/ (`lib/bitabs`), since
names repeat across components. A module depends on the nimony modules it imports or includes; its `std`
imports are listed with whether nimic has a shim (src/nimic/std/<name>.py). `when` branches inactive in the
host-Nim build (e.g. `when defined(nimony)`) are not counted. Statuses: converted = nnimony/<path>.py exists.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from ncompiler.tools.dependencies import _statements, _strip_comments, tiers

ROOT = Path(__file__).resolve().parents[2]
NIMONY = Path(os.environ.get("NIMONY_DIR", ROOT.parent / "nimony"))
NIMONY_PIN = "3f56467ab15a46746c4f2b33a904809a2ffa0a12"  # nimony master, 2026-10-20
NNIMONY = ROOT / "nnimony"
QUEUE = NNIMONY / "conversion_queue.md"
STD_SHIMS = ROOT / "src" / "nimic" / "std"

# components in the order of the plan; the current one is scanned module by module
COMPONENTS = [
    ("lib", "NIF libraries: the foundation of every nimony tool", "current"),
    ("nifler2", "the parser (Nim -> NIF), a nimony program generated from a grammar", "next"),
    ("lengc", "the C backend (NIF -> C)", "later"),
    ("hexer", "lowering (shoggoth)", "later"),
    ("nimony", "semantic checking (nimsem) and the driver", "later"),
]
CURRENT = [c for c, _, state in COMPONENTS if state == "current"]
# first modules for an agent: small, standard library only (brief: nnimony/brief_lib_first.md)
AGENT_FIRST = {"lib/stringtrees", "lib/comesfrom", "lib/symparser"}


def _parts(body: str) -> list[str]:
    """The module paths of an import/include body: `a, b`, `x / [a, b]`, `".." / lib / [a]`, `std/x`."""
    body = re.sub(r"\bexcept\b.*$", "", body)
    out = []
    for part in re.split(r",(?![^\[]*\])", body):
        part = re.sub(r"\bas\s+\w+\s*$", "", part.strip()).replace('"', "").replace(" ", "")
        if not part:
            continue
        if "[" in part:
            prefix, inner = part.split("[", 1)
            out += [prefix + name for name in inner.rstrip("]").split(",") if name]
        else:
            out.append(part)
    return [p.removesuffix(".nim") for p in out]


def _scan_file(src: Path, key: str) -> tuple[set[str], set[str]]:
    """The nimony modules and std modules that module `key` imports or includes."""
    f = src / (key + ".nim")
    text = _strip_comments(f.read_text(errors="replace"))
    bodies = [b for _, b in _statements(text, "import")] + [b for _, b in _statements(text, "include")]
    bodies += [b.split(" import", 1)[0] for _, b in _statements(text, "from")]
    d, s = set(), set()
    for body in bodies:
        for part in _parts(body):
            if part.startswith("std/"):
                s.add(part.removeprefix("std/"))
                continue
            target = os.path.normpath(os.path.join(f.parent.relative_to(src).as_posix(), part))
            if (src / (target + ".nim")).exists():
                d.add(target)
            elif "/" not in part:
                s.add(part)  # a std module imported without the std/ prefix (system modules)
    return d - {key}, s


def scan(component: str) -> tuple[dict, dict, dict]:
    """deps[key] (nimony modules), std[key] (std modules), sizes[key] for the modules of `component` and
    the nimony modules of other components they need (transitively)."""
    src = NIMONY / "src"
    todo = [f.relative_to(src).with_suffix("").as_posix() for f in sorted((src / component).rglob("*.nim"))]
    deps, std, sizes = {}, {}, {}
    while todo:
        key = todo.pop()
        if key in deps:
            continue
        deps[key], std[key] = _scan_file(src, key)
        sizes[key] = (src / (key + ".nim")).stat().st_size
        todo += [k for k in deps[key] if k not in deps]
    return deps, std, sizes


def _converted(key: str) -> bool:
    return (NNIMONY / (key + ".py")).exists()


def _component_lines(component: str) -> int:
    return sum(f.read_text(errors="replace").count("\n") for f in (NIMONY / "src" / component).rglob("*.nim"))


def write_queue() -> None:
    head = subprocess.run(["git", "-C", str(NIMONY), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    lines = ["# nimony → nnimony: Conversion Queue", "",
             "> **Generated** by `python -m nnimony.tools.queue` from the nimony clone at "
             f"`{NIMONY_PIN[:12]}` (pinned in `nnimony/tools/queue.py`). The plan: `ncompiler/conversion_plan.md`."]
    if head != NIMONY_PIN:
        lines += ["", f"> ⚠️ The clone is at `{head[:12]}`, not at the pin."]
    lines += ["", "## Conversion Rules", "",
              "1. **Convert the current component in tier order**, a module once the nimony modules it imports are "
              "converted.",
              "2. **Mirror the path:** `src/lib/bitabs.nim` → `nnimony/lib/bitabs.py`; the module records its source "
              "commit in its header (`# source: nimony@<sha>:src/lib/bitabs.nim`).",
              "3. **Missing std shims** (`src/nimic/std/`) are created as part of the conversion.",
              "4. **`when defined(nimony)`** branches are converted like any `when` (`if comptime(...)`); Python runs "
              "the host-Nim build, where they are inactive.",
              "5. **Review runs after every conversion**; verification: `tests/verify_transpiled.py`.", "",
              "## Components", "", "| Component | Role | Lines | State |", "|---|---|---|---|"]
    for c, role, state in COMPONENTS:
        lines.append(f"| `src/{c}` | {role} | {_component_lines(c):,} | {state} |")
    for component in CURRENT:
        deps, std, sizes = scan(component)
        tier = tiers(deps)
        done = {k for k in deps if _converted(k)}
        ready = sorted((k for k in deps if k not in done and deps[k] <= done), key=lambda k: sizes[k])
        lines += ["", f"## Ready to Convert (`src/{component}`)", "",
                  "| Module | Size | Std imports (✗ = no nimic shim yet) | Agent |", "|---|---|---|---|"]
        for k in ready:
            lines.append(f"| `{k}` | {sizes[k]:,} bytes | {_std_list(std[k])} | {'yes' if k in AGENT_FIRST else ''} |")
        lines += ["", f"## All modules of `src/{component}` ({len(done)}/{len(deps)} converted)", "",
                  "| Module | Tier | Size | Depends on | Std imports | Status |", "|---|---|---|---|---|---|"]
        for k in sorted(deps, key=lambda k: (tier[k], k)):
            status = "✅ Converted" if k in done else "🔲 Pending"
            lines.append(f"| `{k}` | {tier[k]} | {sizes[k]:,} bytes | {', '.join(sorted(deps[k]))} | "
                         f"{_std_list(std[k])} | {status} |")
    QUEUE.write_text("\n".join(lines) + "\n")


def _std_list(names: set[str]) -> str:
    return ", ".join(n if (STD_SHIMS / f"{n}.py").exists() else f"{n} ✗" for n in sorted(names))


def main() -> None:
    write_queue()
    print(f"wrote {QUEUE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
