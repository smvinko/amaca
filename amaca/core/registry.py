"""Process-wide registry of installed code adapters.

Two ways adapters land in the registry:

  1. ``@register`` at class-definition time (used by the built-in Demo
     adapter and by adapter packages that want to register imperatively).
  2. **Entry points** in the ``amaca.codes`` group. An external package
     declares itself with::

         [project.entry-points."amaca.codes"]
         ccfly = "amaca_ccfly.adapter:CcflyCode"

     and amaca picks it up at process startup via
     :func:`load_entry_points`. This is the canonical extension surface
     — amaca core never imports any specific scientific code, and each
     adapter package pins its own version of the underlying code.

The runtime consumes the registry to list available codes, look up a
code by name, and instantiate it for a job.
"""
from __future__ import annotations

import importlib.metadata
import logging
from typing import TypeVar

from .code import Code

logger = logging.getLogger(__name__)

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


def load_entry_points(group: str = "amaca.codes") -> list[str]:
    """Import every plugin declared under ``group``.

    Each entry point should target a :class:`Code` subclass — importing
    the module triggers its ``@register`` side effect. Returns the names
    of plugins successfully loaded.

    A broken plugin is logged but does not raise; one misbehaving adapter
    must not take down the whole app.
    """
    loaded: list[str] = []
    try:
        eps = importlib.metadata.entry_points(group=group)
    except TypeError:
        # Python <3.10 compatibility (kwargs form was added then).
        eps = importlib.metadata.entry_points().get(group, [])  # type: ignore[assignment]

    for ep in eps:
        try:
            ep.load()
            loaded.append(ep.name)
            logger.info("amaca: loaded plugin %r from entry point", ep.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("amaca: failed to load plugin %r: %s", ep.name, exc)
    return loaded


def get(name: str) -> type[Code]:
    if name not in _REGISTRY:
        raise KeyError(f"No code registered as {name!r}")
    return _REGISTRY[name]


def all_codes() -> list[type[Code]]:
    return list(_REGISTRY.values())


def reset() -> None:
    """Clear the registry. Test-only helper — production code never calls this."""
    _REGISTRY.clear()
