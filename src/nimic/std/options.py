"""
nimic std/options module
Copyright (c) 2026 Dmytro Makogon, see LICENSE (MIT).

Python-side implementation of Nim's std/options module.
Provides Option[T] — a type-safe container that either holds a value (some)
or is empty (none).

Usage in nimic code:
    from nimic.std.options import Option, some, none

    x: Option[int32] = some(int32(42))
    y: Option[int32] = none(int32)

    if x.is_some():
        print(x.get())

Transpiles to Nim:
    import std/options
    var x: Option[int32] = some(42'i32)
    var y: Option[int32] = none(int32)
"""


class Option:
    """Nim Option[T] — either some(value) or none.

    Instances should be created via some() and none() helper functions,
    not by direct construction.
    """

    def __init__(self, value=None, _has_value=False):
        self._value = value
        self._has_value = _has_value

    def __class_getitem__(cls, T):
        """Support Option[T] syntax for type annotations."""
        # Return a new subclass specialized for type T
        type_name = T.__name__ if hasattr(T, '__name__') else str(T)
        specialized = type(f"Option[{type_name}]", (Option,), {"_n_inner_type": T})
        return specialized

    def is_some(self) -> bool:
        """Returns true if the Option contains a value."""
        return self._has_value

    def is_none(self) -> bool:
        """Returns true if the Option is empty."""
        return not self._has_value

    def get(self):
        """Returns the contained value.

        Raises UnpackDefect (ValueError) if the Option is empty.
        """
        if not self._has_value:
            raise ValueError("Option is none — cannot get value (UnpackDefect)")
        return self._value

    def unsafe_get(self):
        """Returns the contained value without checking.

        Behavior is undefined if the Option is empty.
        """
        return self._value

    def __eq__(self, other):
        if isinstance(other, Option):
            if self._has_value and other._has_value:
                return self._value == other._value
            return self._has_value == other._has_value
        return NotImplemented

    def __repr__(self):
        if self._has_value:
            return f"some({self._value!r})"
        return "none"

    def __str__(self):
        if self._has_value:
            return f"some({self._value})"
        return "none()"

    def __bool__(self):
        """Allow truthiness check: `if opt: ...` is equivalent to `if opt.is_some(): ...`."""
        return self._has_value


def some(value) -> Option:
    """Create an Option containing a value."""
    return Option(value, _has_value=True)


def none(T=None) -> Option:
    """Create an empty Option.

    T is the type parameter (used for type annotations, ignored at runtime).
    In nimic: none(int32) transpiles to none(int32).
    """
    return Option(_has_value=False)
