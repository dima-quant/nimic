import typing

def gen_enum_case_stmt(T, s, default, low, high, normalize):
    """
    Python implementation of Nim's genEnumCaseStmt macro.
    In Python, we simply normalize the string and search the enum values.
    """
    normalized_s = normalize(s)

    # In PEP 695 generics, T might be a TypeVar at runtime.
    # Fallback to getting the enum class from the default value.
    if isinstance(T, typing.TypeVar):
        T = type(default)

    for e in T:
        # e.ord() is used in NStrEnum for its integer value
        if low <= e.ord() <= high:
            if normalize(e.value) == normalized_s:
                return e
    return default

genEnumCaseStmt = gen_enum_case_stmt
