"""
nimic nvariants module
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Object variants (Nim "case objects"): the declaration as a record tree and the
branch-activity layout computed from it.

    NRecord / NField / NCase / NBranch  — mirror Nim's nkRecList / nkRecCase / nkOfBranch / nkElse
    parse_record(class_def)             — class AST -> NRecord
    parse_class_source(src)             — class source -> NRecord
    NVariantLayout                      — all fields, discriminators, active_fields(), branch_key()

A nimic variant is declared with a `match` on the immediately preceding field:

    class NodeObj(Object):
        info: nint
        kind: NodeKind
        match kind:
            case NodeKind.nkInt:
                intVal: nint
            case NodeKind.nkAdd | NodeKind.nkSub:
                leftOp: Node
                rightOp: Node
            case _:
                pass
        tail: nint

Pure Python: no nimic types are imported. Pattern evaluation and ordinal
normalization are supplied by the caller (ntypesystem).
"""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, replace
from typing import Callable, Mapping


@dataclass(frozen=True)
class NField:
    name: str
    annotation: str  # annotation source text (ast.unparse)
    default: str | None = None  # the default value's source text (`k: nint = nint(5)`), None without one


@dataclass(frozen=True)
class NBranch:
    values: tuple[str, ...] | None  # pattern source texts; None == else (`case _`)
    items: tuple  # tuple[NField | NCase, ...]


@dataclass(frozen=True)
class NCase:
    discriminator: NField
    branches: tuple[NBranch, ...]


def _walk_fields(items, *, branches: bool = True):
    """Depth-first fields of `items` in declaration order (discriminators included)."""
    for it in items:
        if isinstance(it, NField):
            yield it
        else:
            yield it.discriminator
            if branches:
                for br in it.branches:
                    yield from _walk_fields(br.items)


def _walk_cases(items):
    for it in items:
        if isinstance(it, NCase):
            yield it
            for br in it.branches:
                yield from _walk_cases(br.items)


def _map_items(items, fn):
    out = []
    for it in items:
        if isinstance(it, NField):
            out.append(replace(it, annotation=fn(it.annotation)))
        else:
            out.append(NCase(replace(it.discriminator, annotation=fn(it.discriminator.annotation)),
                             tuple(NBranch(br.values, _map_items(br.items, fn)) for br in it.branches)))
    return tuple(out)


@dataclass(frozen=True)
class NRecord:
    items: tuple  # tuple[NField | NCase, ...]

    @property
    def is_variant(self) -> bool:
        return any(isinstance(it, NCase) for it in self.items)

    def all_fields(self) -> dict[str, NField]:
        """All fields of all branches plus discriminators, declaration order (depth-first)."""
        return {f.name: f for f in _walk_fields(self.items)}

    def discriminators(self) -> dict[str, NField]:
        return {c.discriminator.name: c.discriminator for c in _walk_cases(self.items)}

    def cases(self) -> tuple[NCase, ...]:
        return tuple(_walk_cases(self.items))

    def map_annotations(self, fn: Callable[[str], str]) -> NRecord:
        """Same record with every annotation passed through `fn` (generic specialization)."""
        return NRecord(_map_items(self.items, fn))


# --- parsing ---

def _pattern_values(pattern: ast.pattern, where: str) -> tuple[str, ...] | None:
    if isinstance(pattern, ast.MatchValue):
        return (ast.unparse(pattern.value),)
    if isinstance(pattern, ast.MatchSingleton):
        return (repr(pattern.value),)
    if isinstance(pattern, ast.MatchOr):
        values = []
        for p in pattern.patterns:
            sub = _pattern_values(p, where)
            if sub is None:
                raise TypeError(f"{where}: `_` cannot be part of an `|` pattern")
            values.extend(sub)
        return tuple(values)
    if isinstance(pattern, ast.MatchAs) and pattern.pattern is None and pattern.name is None:
        return None
    raise TypeError(f"{where}: unsupported case pattern `{ast.unparse(pattern)}` at line {pattern.lineno}")


def _is_ignorable(stmt: ast.stmt) -> bool:
    """`pass`, docstrings and `...` inside a branch."""
    return isinstance(stmt, ast.Pass) or (
        isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
        and (isinstance(stmt.value.value, str) or stmt.value.value is Ellipsis))


def _parse_items(body: list[ast.stmt], cls_name: str, *, top_level: bool) -> tuple:
    items: list = []
    for stmt in body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            no_default = stmt.value is None or isinstance(stmt.value, ast.Constant) and stmt.value.value is None
            items.append(NField(stmt.target.id, ast.unparse(stmt.annotation),  # (`= None`: a legacy dummy)
                                None if no_default else ast.unparse(stmt.value)))
        elif isinstance(stmt, ast.Match):
            subject = stmt.subject
            prev = items[-1] if items else None
            if not (isinstance(subject, ast.Name) and isinstance(prev, NField) and prev.name == subject.id):
                if top_level:
                    continue  # not a record case (e.g. a match inside class-level code)
                raise TypeError(f"{cls_name}: `match` at line {stmt.lineno} must follow the "
                                f"field it discriminates on")
            items.pop()
            where = f"{cls_name}.{prev.name}"
            branches = []
            for i, mc in enumerate(stmt.cases):
                if mc.guard is not None:
                    raise TypeError(f"{cls_name}: unsupported statement in variant branch at line "
                                    f"{mc.guard.lineno} (case guard)")
                values = _pattern_values(mc.pattern, where)
                if values is None and i != len(stmt.cases) - 1:
                    raise TypeError(f"{where}: `case _` must be the last branch (line {mc.pattern.lineno})")
                branches.append(NBranch(values, _parse_items(mc.body, cls_name, top_level=False)))
            items.append(NCase(prev, tuple(branches)))
        elif top_level or _is_ignorable(stmt):
            continue  # methods, decorators, `with` blocks, docstrings at class level
        else:
            raise TypeError(f"{cls_name}: unsupported statement in variant branch at line {stmt.lineno}")
    return tuple(items)


def parse_record(class_def: ast.ClassDef) -> NRecord:
    """Record tree of a class body. For variant records, raises TypeError on duplicate
    field names (Nim N1); always on unsupported statements inside variant branches."""
    record = NRecord(_parse_items(class_def.body, class_def.name, top_level=True))
    if not record.is_variant:
        return record  # plain objects keep Python's last-annotation-wins behaviour
    seen: set[str] = set()
    for f in _walk_fields(record.items):
        if f.name in seen:
            raise TypeError(f"{class_def.name}: duplicate field '{f.name}' (field names must be "
                            f"unique across all branches)")
        seen.add(f.name)
    return record


def parse_class_source(src: str) -> NRecord:
    """Record of the first class defined in `src` (dedented, e.g. inspect.getsource output)."""
    tree = ast.parse(textwrap.dedent(src))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return parse_record(node)
    raise TypeError("no class definition found in source")


# --- layout ---

class NVariantLayout:
    """Branch activity of a variant record.

    eval_value(src) evaluates a pattern source text (in the defining module);
    ordinal(value) normalizes discriminator and pattern values for comparison.
    Pattern values are evaluated once, lazily on first use (forward references)."""

    def __init__(self, record: NRecord, eval_value: Callable[[str], object],
                 ordinal: Callable[[object], int]):
        self.record = record
        self.fields: dict[str, NField] = record.all_fields()
        self.discriminators: dict[str, NField] = record.discriminators()
        self._eval_value = eval_value
        self._ordinal = ordinal
        self._branch_ords: dict[int, tuple[frozenset[int] | None, ...]] = {}
        self._owner: dict[str, NCase] = {}
        for case in record.cases():  # innermost owner: a branch owns its direct fields
            for br in case.branches:   # and the discriminators of cases nested in it
                for it in br.items:
                    self._owner[it.name if isinstance(it, NField) else it.discriminator.name] = case

    def _ords(self, case: NCase) -> tuple[frozenset[int] | None, ...]:
        ords = self._branch_ords.get(id(case))
        if ords is None:
            ords = tuple(None if br.values is None else
                         frozenset(self._ordinal(self._eval_value(v)) for v in br.values)
                         for br in case.branches)
            self._branch_ords[id(case)] = ords
        return ords

    def branch_values(self, case: NCase) -> tuple[frozenset[int] | None, ...]:
        """Normalized values per branch (None for `case _`)."""
        return self._ords(case)

    def _branch_index(self, case: NCase, disc_values: Mapping[str, object]) -> int | None:
        value = disc_values.get(case.discriminator.name)
        if value is None:
            return None
        o = self._ordinal(value)
        for i, vals in enumerate(self._ords(case)):
            if vals is None or o in vals:
                return i
        return None  # no branch matches and no `case _`: the case contributes no fields

    def _active(self, items, disc_values, out_fields: list, out_key: list) -> None:
        for it in items:
            if isinstance(it, NField):
                out_fields.append(it.name)
            else:
                out_fields.append(it.discriminator.name)
                i = self._branch_index(it, disc_values)
                out_key.append((it.discriminator.name, i))
                if i is not None:
                    self._active(it.branches[i].items, disc_values, out_fields, out_key)

    def active_fields(self, disc_values: Mapping[str, object]) -> tuple[str, ...]:
        """Common fields + fields of the active branches, declaration order."""
        fields: list = []
        self._active(self.record.items, disc_values, fields, [])
        return tuple(fields)

    def branch_key(self, disc_values: Mapping[str, object]) -> tuple:
        """Identity of the active branch set: ((discriminator, branch index), ...) for every
        reachable case. An unchanged key means a discriminator change keeps the branch (N5)."""
        key: list = []
        self._active(self.record.items, disc_values, [], key)
        return tuple(key)

    def owner_case(self, field: str) -> NCase | None:
        """The case whose branch declares `field` (None for common fields and top-level discriminators)."""
        return self._owner.get(field)

    def is_active(self, field: str, disc_values: Mapping[str, object]) -> bool:
        return field in self.active_fields(disc_values)

    def is_exhaustive(self, case: NCase, all_ordinals) -> bool:
        """True if `case` has `case _` or its branch values cover every ordinal in `all_ordinals`."""
        ords = self._ords(case)
        if any(v is None for v in ords):
            return True
        covered = frozenset().union(*ords)
        return set(all_ordinals) <= covered
