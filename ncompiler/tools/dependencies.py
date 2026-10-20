"""
Dependencies of the Nim compiler modules in compiler/, for the conversion order.

    .venv/bin/python -m ncompiler.tools.dependencies          # rewrite dep.md, dep_tree.md, conversion_queue.md

A module depends on the compiler modules it imports or includes. An *include file* (`include x` in an
includer) has no imports of its own context: it sees everything its includer imported or included
before the include point, recursively for nested includes (ccgtrav <- ccgtypes <- cgen). Its
dependencies are the modules of that context that export an identifier the include file uses (procs,
types, constants, enum members), plus its own imports. The includer depends on its include files. Tiers are longest dependency paths (import cycles are
collapsed). Imports under a `when` whose condition is false in the default compiler build (the build
profile of ncompiler/nim.cfg, e.g. `when defined(nimDebugUtils)`) are not counted. Statuses of
conversion_queue.md are kept.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from nimic.nsystem import _BuildProfile

ROOT = Path(__file__).resolve().parents[2]
COMPILER = ROOT / "compiler"
NCOMPILER = ROOT / "ncompiler"
QUEUE = NCOMPILER / "conversion_queue.md"

# modules whose conversion must be redone or re-reviewed (ncompiler/review_core_2026_10_16.md)
NEEDS_RECONVERSION = {"aliasanalysis"}
NEEDS_REREVIEW: set[str] = set()
# converted modules with open core gaps; they count as converted for their dependents, which don't use
# the affected parts
OPEN_GAPS = {"msgs": "G13 `??`, G17 styled output"}

# --- the plan (ncompiler/conversion_plan.md): what to convert, phase by phase ---
PLAN = "ncompiler/conversion_plan.md"
# 2026-10-20: the work moved to nimony (nnimony/); the converted Nim 2 modules are frozen as test corpus
FROZEN = True
PHASE = 1  # the phase the Nim 2 conversion had reached
PHASE_NAMES = {1: "front end", 2: "NIF libraries and nifler (pinned nimony)", 3: "backends: nifc, LLVM",
               4: "semantic checking: nimony's sem"}
# Phase 1: these modules and everything they depend on (in the bootstrap build), plus small extras
PHASE1_TARGETS = ("parser", "renderer", "syntaxes", "astalgo")
PHASE1_EXTRA: set[str] = set()
# modules that can't be converted yet, and why
BLOCKED = {
    "tccgen": "needs tinyc (a binding of the Tiny C Compiler)",
    "gorgeimpl": "needs `checksums` (sha1) from dist/: Phase 2 import support",
    "nimblecmd": "needs `checksums` (sha1) from dist/: Phase 2 import support",
    "typekeys": "needs nimony's treemangler/modnames: Phase 2",
    "deps": "nimony libraries; not in the bootstrap build",
    "ast2nif": "Nim 3 NIF writer (nimony); not in the bootstrap build",
    "nifgen": "Nim 3 NIF generation (nimony); not in the bootstrap build",
    "nifbackend": "Nim 3 NIF backend (nimony); not in the bootstrap build",
}
# Nim 2 parts that Nim 3 replaces: not converted (converted ones stay as test corpus), by name pattern
DEFERRED = [
    (r"sem\w*|sigmatch|lookups|pragmas|procfind|concepts|typeallowed|types|typesrenderer|magicsys|importer|evaltempl|"
     r"patterns|parampatterns|suggest|suggestsymdb|errorhandling|expanddefaults|isolation_check|nilcheck|guards|"
     r"aliases|aliasanalysis|dfa|nimsets|optimizer|treetab|layeredtable|liftlocals|pushpoppragmas|enumtostr|"
     r"sizealignoffsetimpl|astmsgs|linter|reorder|sighashes|sinkparameter_inference|hlo",
     "Nim 2 semantic checking: replaced by nimony's sem (Phase 4)"),
    (r"transf|lambdalifting|closureiters|injectdestructors|liftdestructors|lowerings|varpartitions|spawn|vtables",
     "Nim 2 transforms: replaced by nimony's hexer (Phase 4)"),
    (r"vm\w*|nimeval|scriptconfig|evalffi|macrocacheimpl", "Nim 2 VM: replaced in Nim 3"),
    (r"cgen|ccg\w*|cbuilder\w*|cgendata|cgmeth|mangleutils|extccomp|debuginfo|inliner",
     "Nim 2 C backend: replaced by nifc (Phase 3)"),
    (r"jsgen|jstypes|sourcemap|nodejs", "Nim 2 JS backend: not targeted"),
    (r"main|nim|commands|cmdlinehelper|modules|modulegraphs|modulepaths|pipelines|pipelineutils|passes|passaux|"
     r"depends|docgen\w*|index|nimconf|packages|pluginsupport|layouter|renderverbatim|debugutils",
     "Nim 2 driver and tools: decide in Phase 2 (nimony's driver)"),
]
# planned conversions that are not part of compiler/
PLANNED = [
    (2, "nimony `src/lib`: bitabs, nifstreams, nifreader, nifbuilder, ... (at a pinned commit)"),
    (2, "nifler (Nim → NIF, on Nim 2's parser)"),
    (2, "`checksums` (md5, sha1) and nimony's treemangler/modnames, unblocking typekeys and modulegraphs"),
    (3, "nifc (NIF → C), at the pin"),
    (3, "an LLVM backend through the LLVM C API (`@importc`)"),
    (4, "nimony's sem and hexer, once stable"),
]


def _deferred_reason(name: str) -> str | None:
    return next((reason for pattern, reason in DEFERRED if re.fullmatch(pattern, name)), None)


def phase1_modules(deps: dict[str, set[str]]) -> set[str]:
    """Phase 1: the targets' dependency closure plus the extras."""
    seen, stack = set(), list(PHASE1_TARGETS)
    while stack:
        m = stack.pop()
        if m not in seen:
            seen.add(m)
            stack.extend(deps[m])
    return seen | PHASE1_EXTRA


def scope_of(name: str, phase1: set[str], converted: set[str]) -> str:
    """The module's place in the plan: P1, blocked, deferred, or done (corpus: a converted Nim 2 part that
    Nim 3 replaces)."""
    if name in phase1:
        return "P1"
    if name in BLOCKED:
        return "blocked"
    if _deferred_reason(name):
        return "corpus" if name in converted else "deferred"
    return "done" if name in converted else "unplanned"


def _strip_comments(text: str) -> str:
    text = re.sub(r"#\[.*?\]#", "", text, flags=re.S)
    return "\n".join(line.split("#", 1)[0] if not line.lstrip().startswith('"') else line
                     for line in text.splitlines())


_PROFILE = _BuildProfile(str(NCOMPILER / "nim.nim"), "")  # ncompiler/nim.cfg: the build the conversion targets


def _when_active(cond: str) -> bool:
    """A `when` condition evaluated in the default compiler build; conditions other than
    defined()/and/or/not/true/false (e.g. declared(...), constants) count as active."""
    expr = re.sub(r"defined\((\w+)\)", lambda m: str(_PROFILE.is_defined(m.group(1))), cond)
    expr = expr.replace("true", "True").replace("false", "False")
    if re.fullmatch(r"[\s()]*((not|and|or|True|False)[\s()]*)+", expr):
        return bool(eval(expr))
    return True


def _inside_inactive_when(lines: list[str], i: int) -> bool:
    """True if line i lies in a `when` branch that is inactive in the default build."""
    indent = len(lines[i]) - len(lines[i].lstrip())
    inline = re.match(r"^\s*when\s+(.+?):\s*\S", lines[i])
    if inline and not _when_active(inline.group(1)):
        return True
    for j in range(i - 1, -1, -1):
        line = lines[j]
        if not line.strip():
            continue
        ind = len(line) - len(line.lstrip())
        if ind < indent:
            m = re.match(r"^\s*(when|elif|else)\b\s*(.*?):\s*$", line)
            if m and m.group(1) == "when" and not _when_active(m.group(2)):
                return True
            if not m:
                return False
            indent = ind
            if ind == 0:
                return False
    return False


def _statements(text: str, keyword: str) -> list[tuple[int, str]]:
    """(line number, module list text) of `import ...`/`include ...` statements, joining continuation
    lines (a trailing comma, or an indented list after a bare `import`)."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = re.match(rf"^(\s*)(?:when\s+[^:]+:\s*)?{keyword}\b(.*)$", lines[i])
        if m:
            indent, body = len(m.group(1)), m.group(2).strip()
            start = i
            while (body == "" or body.rstrip().endswith((",", "[", "/"))) and i + 1 < len(lines):
                nxt = lines[i + 1]
                if nxt.strip() == "":
                    i += 1
                    continue
                if body != "" or len(nxt) - len(nxt.lstrip()) > indent:
                    body += " " + nxt.strip()
                    i += 1
                else:
                    break
            if not _inside_inactive_when(lines, start):
                out.append((start + 1, body))
        i += 1
    return out


def _module_names(body: str, known: set[str]) -> list[str]:
    body = re.sub(r"\bexcept\b.*$", "", body)
    names = []
    for part in re.split(r",(?![^\[]*\])", body):
        part = part.strip().strip('"')
        if not part:
            continue
        part = re.sub(r"\bas\s+\w+$", "", part).strip()
        if "[" in part:  # std/[a, b] or ic / [a, b]
            prefix, inner = part.split("[", 1)
            if prefix.replace(" ", "").rstrip("/") in ("std", "pkg", ""):
                continue
            candidates = [p.strip() for p in inner.rstrip("]").split(",")]
        else:
            candidates = [part.replace(" ", "")]
        for c in candidates:
            c = c.removesuffix(".nim")
            if c.startswith("../") or "/" in c:
                continue  # stdlib paths, subdirectories (ic/, plugins/)
            if c in known:
                names.append(c)
    return names


_ROUTINE = re.compile(r"^\s*(?:proc|func|template|macro|iterator|method|converter)\s+(`[^`]+`|\w+)\*")
_DECL = re.compile(r"^\s*(?:type\s+|const\s+|let\s+|var\s+)?(\w+)\*\s*(?:\{\..*?\.\})?\s*(?:=|:)")
# include files share their includer's scope: their unexported top-level names count as well
_ROUTINE_ANY = re.compile(r"^(?:proc|func|template|macro|iterator|method|converter)\s+(`[^`]+`|\w+)")
_DECL_ANY = re.compile(r"^(?:type\s+|const\s+|let\s+|var\s+|  )(\w+)\*?\s*(?:\{\..*?\.\})?\s*(?:=|:)")
_ENUM = re.compile(r"^(\s*)(?:type\s+)?(\w+)\*?\s*(?:\{\..*?\.\})?\s*=\s*enum\b(.*)$")
_IDENT = re.compile(r"\b[A-Za-z]\w*\b")


def exported_names(text: str, include_private: bool = False) -> set[str]:
    """Identifiers a module exports: `*`-marked routines and declarations, and the members of its enums.
    With include_private, also the unexported top-level ones (for include files)."""
    names = set()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for rx in ((_ROUTINE, _DECL, _ROUTINE_ANY, _DECL_ANY) if include_private else (_ROUTINE, _DECL)):
            m = rx.match(line)
            if m:
                names.add(m.group(1).strip("`"))
        m = _ENUM.match(line)
        if m and (include_private or "*" in line.split("=", 1)[0]):
            indent = len(m.group(1))
            body = [m.group(3)]
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                body.append(nxt)
            for part in body:
                part = re.sub(r'"[^"]*"', "", part)
                names.update(re.findall(r"(\w+)\s*(?:=|,|$)", part))
    return names


def used_names(text: str) -> set[str]:
    text = re.sub(r'"(?:[^"\\]|\\.)*"', "", text)
    return set(_IDENT.findall(text))


def scan() -> tuple[dict, dict, dict, dict]:
    """imports[m] / includes[m]: (line, module) pairs in source order; sizes[m] in bytes; texts[m]."""
    files = {p.stem: p for p in sorted(COMPILER.glob("*.nim"))}
    known = set(files)
    imports, includes, sizes, texts = {}, {}, {}, {}
    for name, path in files.items():
        text = _strip_comments(path.read_text(errors="replace"))
        texts[name] = text
        sizes[name] = path.stat().st_size
        imports[name] = [(ln, m) for ln, body in _statements(text, "import") for m in _module_names(body, known)]
        imports[name] += [(ln, m) for ln, body in _statements(text, "from")
                          for m in _module_names(body.split(" import", 1)[0], known)]
        includes[name] = [(ln, m) for ln, body in _statements(text, "include") for m in _module_names(body, known)]
    return imports, includes, sizes, texts


def dependencies() -> tuple[dict[str, set[str]], dict[str, str], dict[str, int]]:
    """Effective dependencies of every module, the includer of each include file, and sizes."""
    imports, includes, sizes, texts = scan()
    includer = {inc: name for name, incs in includes.items() for _, inc in incs}
    exports = {m: exported_names(t, include_private=m in includer) for m, t in texts.items()}
    context_cache: dict[tuple[str, int], set[str]] = {}

    def context(name: str, line: int) -> set[str]:
        """Modules visible in `name` at `line`: its imports and includes before that line, and (for an
        include file) the context of its includer at its include point."""
        key = (name, line)
        if key in context_cache:
            return context_cache[key]
        result = {m for ln, m in imports[name] if ln < line}
        result |= {m for ln, m in includes[name] if ln < line}
        if name in includer:
            parent = includer[name]
            at = next(ln for ln, m in includes[parent] if m == name)
            result |= context(parent, at)
        context_cache[key] = result
        return result

    deps = {}
    for name in imports:
        own = {m for _, m in imports[name]} | {m for _, m in includes[name]}
        if name in includer:
            chain = {includer[name]}
            p = includer[name]
            while p in includer:
                p = includer[p]
                chain.add(p)
            used = used_names(texts[name]) - exported_names(texts[name], include_private=True)
            visible = context(name, 10 ** 9) - {name} - chain
            own |= {m for m in visible if used & exports[m]}
        deps[name] = own - {name}
    return deps, includer, sizes


def tiers(deps: dict[str, set[str]]) -> dict[str, int]:
    """Longest path to a leaf, with import cycles (strongly connected components) collapsed."""
    index, low, on_stack, stack, comp, counter = {}, {}, set(), [], {}, [0]
    sys.setrecursionlimit(10000)

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in deps[v]:
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            members = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                members.append(w)
                if w == v:
                    break
            for w in members:
                comp[w] = v

    for v in deps:
        if v not in index:
            strong(v)
    members: dict[str, list[str]] = {}
    for v, c in comp.items():
        members.setdefault(c, []).append(v)
    cdeps = {c: {comp[w] for v in vs for w in deps[v]} - {c} for c, vs in members.items()}
    memo: dict[str, int] = {}

    def depth(c):
        if c not in memo:
            memo[c] = 1 + max((depth(d) for d in cdeps[c]), default=-1)
        return memo[c]

    return {v: depth(comp[v]) for v in deps}


def _converted() -> set[str]:
    return {p.stem for p in NCOMPILER.glob("*.py") if p.stem != "__init__"}


def _old_statuses() -> dict[str, str]:
    statuses = {}
    if QUEUE.exists():
        for line in QUEUE.read_text().splitlines():
            m = re.match(r"^\| `(\w+)` \|.*\| ([^|]+) \|$", line)
            if m and ("Converted" in m.group(2) or "Pending" in m.group(2) or "Needs" in m.group(2)):
                statuses.setdefault(m.group(1), m.group(2).strip())
    return statuses


def status_of(name: str, converted: set[str], old: dict[str, str]) -> str:
    if name in NEEDS_RECONVERSION:
        return "⚠️ Needs reconversion"
    if name in NEEDS_REREVIEW:
        return "⚠️ Needs re-review"
    if name in converted:
        if name in OPEN_GAPS:
            return f"✅ Converted (open gaps: {OPEN_GAPS[name]})"
        prev = old.get(name, "")
        return prev if prev.startswith("✅") else "✅ Converted"
    return "🔲 Pending"


def _short(names: set[str], limit: int = 5) -> str:
    items = sorted(names)
    return ", ".join(items[:limit]) + (f" +{len(items) - limit} more" if len(items) > limit else "")


def write_dep_files(deps: dict[str, set[str]], includer: dict[str, str]) -> None:
    users: dict[str, set[str]] = {m: set() for m in deps}
    for m, ds in deps.items():
        for d in ds:
            users[d].add(m)
    for m, inc in includer.items():
        users[m].add(inc)
    header = ("<!-- generated by `python -m ncompiler.tools.dependencies`: effective dependencies; an include\n"
              "     file (marked `included from X`) depends on what X imports/includes before the include point -->\n")
    (COMPILER / "dep.md").write_text(header + "".join(
        f"{m} [{', '.join(sorted(deps[m]))}]" + (f" (included from {includer[m]})" if m in includer else "") + "\n"
        for m in sorted(deps)))
    (COMPILER / "dep_tree.md").write_text(header + "".join(
        f"{m} [{', '.join(sorted(users[m]))}]\n" for m in sorted(deps)))


def write_queue(deps, includer, sizes, tier) -> None:
    converted = _converted()
    old = _old_statuses()
    statuses = {m: status_of(m, converted, old) for m in deps}
    done = {m for m, s in statuses.items() if s.startswith("✅")}
    phase1 = phase1_modules(deps)
    scope = {m: scope_of(m, phase1, converted) for m in deps}
    by_tier: dict[int, list[str]] = {}
    for m, t in tier.items():
        by_tier.setdefault(t, []).append(m)
    n_tiers = max(by_tier) + 1
    lines = ["# Nim Compiler → Nimic: Conversion Queue", "",
             f"> **Generated** by `python -m ncompiler.tools.dependencies` | **Total modules**: {len(deps)} | "
             f"**Converted**: {len(done)} | **Needs rework**: {sum(s.startswith('⚠️') for s in statuses.values())} | "
             f"**Remaining**: {len(deps) - len(done)}", "",
             (f"> **Frozen as test corpus** (2026-10-20): the work moved to nimony, see `nnimony/conversion_queue.md` "
              f"and `{PLAN}`. The converted modules stay green in verification but are not extended; the phases "
              "below are where the Nim 2 conversion stood." if FROZEN else
              f"> **Current phase: {PHASE} — {PHASE_NAMES[PHASE]}.** The plan and its reasons: `{PLAN}`. Phases and "
              "scopes are set in `ncompiler/tools/dependencies.py` (`PHASE`, `PHASE1_TARGETS`, `BLOCKED`, `DEFERRED`)."), "",
             "## Conversion Rules", "",
             "1. **Convert in phase order, then tier order** — only modules of the current phase, and only when all "
             "their dependencies are converted. Blocked and deferred modules are not converted (see below).",
             "2. **Include files** (`include x` in an includer) depend on everything their includer imports or "
             "includes before the include point, so they are placed after those modules (column *Included from*).",
             "3. **No stubs** unless strictly necessary and no reordering is possible; stand-ins for unconverted "
             "dependencies belong to tests only (`nimic_translation_rules_nim2.md` §2.1).",
             "4. **Missing `nimic.std` modules** can be created proactively.",
             "5. **Review runs automatically** after every conversion.", "",
             f"## Ready to Convert (Phase {PHASE})", "",
             "Pending modules of the current phase whose dependencies are all converted, smallest first:", "",
             "| Module | Tier | Size | Included from |", "|---|---|---|---|"]
    ready = [] if FROZEN else sorted(
        (m for m in deps if statuses[m] == "🔲 Pending" and scope[m] == f"P{PHASE}" and deps[m] <= done),
        key=lambda m: sizes[m])
    if FROZEN:
        lines.append("| — | | | none: frozen |")
    for m in ready:
        lines.append(f"| `{m}` | {tier[m]} | {sizes[m]:,} bytes | {includer.get(m, '')} |")
    p1 = sorted(phase1, key=lambda m: (tier[m], m))
    lines += ["", f"## Phase 1 — {PHASE_NAMES[1]}", "",
              f"Targets {', '.join(f'`{t}`' for t in PHASE1_TARGETS)} and their dependencies"
              + (f", plus {', '.join(f'`{t}`' for t in sorted(PHASE1_EXTRA))}" if PHASE1_EXTRA else "") + ": "
              f"{sum(m in done for m in p1)}/{len(p1)} converted.", "",
              "| Module | Tier | Size | Missing dependencies | Status |", "|---|---|---|---|---|"]
    for m in p1:
        lines.append(f"| `{m}` | {tier[m]} | {sizes[m]:,} bytes | {_short(deps[m] - done)} | {statuses[m]} |")
    lines += ["", "## Blocked", "", "Not convertible yet:", "", "| Module | Size | Reason |", "|---|---|---|"]
    for m in sorted(n for n in deps if scope[n] == "blocked"):
        lines.append(f"| `{m}` | {sizes[m]:,} bytes | {BLOCKED[m]} |")
    lines += ["", "## Deferred", "",
              "Nim 2 parts that Nim 3 replaces: not converted. Already converted ones (marked *corpus*) stay as "
              "test corpus and are not extended.", ""]
    for _, reason in DEFERRED:
        ms = sorted(n for n in deps if scope[n] in ("deferred", "corpus") and _deferred_reason(n) == reason)
        if ms:
            size = sum(sizes[n] for n in ms)
            lines.append(f"- **{reason}** ({len(ms)} modules, {size:,} bytes): " +
                         ", ".join(f"`{n}`" + (" *(corpus)*" if scope[n] == "corpus" else "") for n in ms))
    unplanned = sorted(n for n in deps if scope[n] == "unplanned")
    if unplanned:
        lines += ["", "Not yet placed in the plan: " + ", ".join(f"`{n}`" for n in unplanned)]
    lines += ["", "## Planned (outside compiler/)", ""]
    lines += [f"- **Phase {ph}:** {what}" for ph, what in PLANNED]
    rework = sorted(m for m, s in statuses.items() if s.startswith("⚠️"))
    lines += ["", "## Needs Rework", "",
              "See `ncompiler/review_core_2026_10_16.md` and `ncompiler/proposals/feature_line_for_line_fidelity.md`.",
              "", "| Module | Tier | Status | Missing dependencies |", "|---|---|---|---|"]
    for m in rework:
        lines.append(f"| `{m}` | {tier[m]} | {statuses[m]} | {_short(deps[m] - done)} |")
    lines += ["", "## Progress by Tier", "", "| Tier | Modules | Converted | Remaining |", "|---|---|---|---|"]
    for t in range(n_tiers):
        ms = by_tier.get(t, [])
        c = sum(m in done for m in ms)
        lines.append(f"| {t} | {len(ms)} | {c} | {len(ms) - c} |")
    lines += ["", "## Full Tier Breakdown", "",
              "Scope: `P1` current phase, `done` converted, `corpus` converted Nim 2 part that Nim 3 replaces, "
              "`blocked`, `deferred` (see above)."]
    for t in range(n_tiers):
        ms = sorted(by_tier.get(t, []))
        c = sum(m in done for m in ms)
        lines += ["", f"### Tier {t} ({c}/{len(ms)} converted)", "",
                  "| Module | Size | Dependencies | Included from | Scope | Status |", "|---|---|---|---|---|---|"]
        for m in ms:
            lines.append(f"| `{m}` | {sizes[m]:,} bytes | {_short(deps[m])} | {includer.get(m, '')} | {scope[m]} | "
                         f"{statuses[m]} |")
    QUEUE.write_text("\n".join(lines) + "\n")


def main() -> None:
    deps, includer, sizes = dependencies()
    tier = tiers(deps)
    write_dep_files(deps, includer)
    write_queue(deps, includer, sizes, tier)
    print(f"{len(deps)} modules, {len(includer)} include files, {max(tier.values()) + 1} tiers")


if __name__ == "__main__":
    main()
