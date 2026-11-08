"""nimic's reserved names (rules §1, `rule:reservedescape`): the names `from nimic.ntypes import *` binds that are
no Nim identifier of system (or of Nim's syncio / assertions), nimic's own vocabulary: the literal helpers (`u8`,
`f64`, `utf8`, `cell`), nimic's types (`nint`, `Tset`, `Object`), its decorators and directives (`dispatch`,
`overloads`, `importFrom`, `pragma`), the snake_case aliases of system procs (`new_seq`, `copy_mem`), and what
Python's own imports leave in the module (`annotations`, `contextlib`, `Self`). Also reserved: the Python builtins
nimic's spelling uses with their Python meaning, which the transpiler maps (`isinstance(x, T)` is `x is T`,
`str(x)` is `$x`, `print` is `echo`, `@property` a getter): a user's own `isinstance` or `str` (std/parsejson's
`proc str(my: JsonParser)`) would shadow the builtin and its calls would be read as the builtin's.

A user identifier spelled like one of them (a routine, type, field, parameter, local or enum member of a converted
module) is written with a trailing `_` in nimic, everywhere it occurs (`back_`, `x.hook_`, `f(emit_=1)`); the
transpiler drops the `_` again. The mapping is deterministic and reversible: a Nim identifier never ends with `_`.
Python keywords get the same `_` (`rule:keywordescape`).

Kept apart from `nimic.ntypes` (which imports the transpiler through nsystem) so that the transpiler, the name
checks and nimicgen's core-name list read it without importing the core. `tests/nimic/test_ntypes.py` checks that
each public name of `nimic.ntypes` is either reserved here or one of Nim's: a new core name is classified when it is
added (adding a reserved name renames the user identifiers spelled like it, which the name check then reports)."""

CORE_NAMES = frozenset({
    # literal helpers and value forms the transpiler reads as syntax
    "u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64", "f16", "f32", "f64", "utf8", "cell", "inrange",
    # nimic's types and type constructors
    "nint", "nbool", "nord", "intp", "uintp", "float16", "Tset", "Trange", "NTuple", "NCell", "NInteger",
    "NIntEnum", "NStrEnum", "Object", "Concept", "Type", "Self", "DICT_OF_TYPES",
    # decorators, directives and block forms
    "dispatch", "ufcs", "overloads", "alias", "calltype", "comptime", "generic", "hook", "mut", "operator",
    "pragma", "emit", "importc", "template_expand", "template_inline", "breakBlock", "importFrom", "importExcept",
    "exportFrom", "exportExcept", "assign", "back", "subset",
    # nimic's exceptions
    "NimicEncodingError", "TemplateBlockError",
    # snake_case aliases and nimic spellings of system procs and operators
    "plus_percent", "minus_percent", "lt_percent", "le_percent", "gt_percent", "ge_percent", "contains_or_incl",
    "copy_mem", "move_mem", "alloc_shared0", "dealloc_shared", "unsafe_addr", "new_seq", "new_seq_of_cap",
    "new_string_of_cap", "new_cstring_of_cap", "newCStringOfCap", "new_exception", "write_buffer", "write_bytes",
    # left in the module by Python's imports
    "annotations", "contextlib",
})

PYTHON_NAMES = frozenset({"isinstance", "issubclass", "print", "property", "str"})

RESERVED_NAMES = CORE_NAMES | PYTHON_NAMES


def escaped(name: str) -> str | None:
    """The Nim name of `name` when it is an escaped reserved name (`hook_` -> `hook`), else None."""
    if len(name) > 1 and name.endswith("_") and name[:-1] in RESERVED_NAMES:
        return name[:-1]
    return None
