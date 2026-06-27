"""Shared markdown-it-py token utilities for platform renderers.

markdown-it-py ``Token.attrs`` is typed as ``dict[str, str | int | float] | None``
in the type stubs, but at runtime some versions return a ``list[tuple[str, ...]]``.
These helpers handle both representations without triggering Pyright ``Never``
narrowing issues.
"""

from __future__ import annotations

from typing import Any


def _get_str_impl(attrs: Any, key: str, default: str = "") -> str:
    """Get a string attr from a dict or list-of-tuples."""
    if isinstance(attrs, dict):
        val = attrs.get(key)
        if val is not None:
            return str(val) if not isinstance(val, str) else val
        return default
    if isinstance(attrs, (list, tuple)):
        for item in attrs:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                k, v = item
                if isinstance(k, str) and k == key:
                    return str(v) if not isinstance(v, str) else v
        return default
    return default


def _get_int_impl(attrs: Any, key: str, default: int = 1) -> int:
    """Get an int attr from a dict or list-of-tuples."""
    if isinstance(attrs, dict):
        val = attrs.get(key)
        if val is not None:
            try:
                return int(val)
            except TypeError, ValueError:
                return default
        return default
    if isinstance(attrs, (list, tuple)):
        for item in attrs:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                k, v = item
                if isinstance(k, str) and k == key:
                    try:
                        return int(v)
                    except TypeError, ValueError:
                        return default
        return default
    return default


def get_attr(attrs: object, key: str, default: str = "") -> str:
    """Get a string attribute value from token attrs.

    Accepts both ``dict`` and ``list[tuple]`` attribute representations
    to stay compatible across markdown-it-py versions.
    """
    return _get_str_impl(attrs, key, default)


def get_int_attr(attrs: object, key: str, default: int = 1) -> int:
    """Get an integer attribute value from token attrs.

    Accepts both ``dict`` and ``list[tuple]`` attribute representations.
    Returns *default* when the attribute is missing or not convertible.
    """
    return _get_int_impl(attrs, key, default)
