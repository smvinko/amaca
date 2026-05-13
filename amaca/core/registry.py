"""Process-wide registry of installed code adapters.

Adapters declare themselves with ``@register`` at class-definition time.
The runtime consumes the registry to list available codes, look up a
code by name, and instantiate it for a job.
"""
from __future__ import annotations

from typing import TypeVar

from .code import Code

_REGISTRY: dict[str, type[Code]] = {}

T = TypeVar("T", bound=type[Code])


def register(cls: T) -> T:
    """Class decorator: register a concrete Code subclass under its ``name``."""
    if cls.name in _REGISTRY:
        existing = _REGISTRY[cls.name]
        if existing is cls:
            return cls
        raise ValueError(
            f"Code name {cls.name!r} is already registered to {existing.__name__}"
        )
    _REGISTRY[cls.name] = cls
    return cls


def get(name: str) -> type[Code]:
    if name not in _REGISTRY:
        raise KeyError(f"No code registered as {name!r}")
    return _REGISTRY[name]


def all_codes() -> list[type[Code]]:
    return list(_REGISTRY.values())


def reset() -> None:
    """Clear the registry. Test-only helper — production code never calls this."""
    _REGISTRY.clear()
