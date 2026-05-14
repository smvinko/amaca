"""Plugin discovery via the ``amaca.codes`` entry-point group.

We don't actually install a sibling package in tests; instead we patch
``importlib.metadata.entry_points`` to return synthetic entry points
whose ``load()`` registers a fake Code via the public ``@register``.
"""
from __future__ import annotations

import importlib.metadata

import pytest
from pydantic import BaseModel

from amaca.core import Code, JobContext, all_codes, load_entry_points, register

pytestmark = pytest.mark.unit


class _FakeIn(BaseModel):
    x: int = 1


class _FakeOut(BaseModel):
    x: int


def _make_ep(ep_name: str, *, raises: bool = False):
    """Synthetic entry point whose load() registers a small valid Code subclass."""
    class _EP:
        pass

    ep = _EP()
    ep.name = ep_name

    def _load() -> None:
        if raises:
            raise RuntimeError(f"boom in {ep_name}")

        # Define a fully-valid Code subclass so __init_subclass__ is happy.
        attrs = {
            "name": f"plugin-{ep_name}",
            "title": f"Fake {ep_name}",
            "version": "0.0.1",
            "InputSchema": _FakeIn,
            "OutputSchema": _FakeOut,
            "run": lambda self, inputs, ctx: _FakeOut(x=inputs.x),
        }
        plugin_cls = type(f"_FakePlugin_{ep_name}", (Code,), attrs)
        register(plugin_cls)

    ep.load = _load  # type: ignore[assignment]
    return ep


def test_load_entry_points_registers_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_eps = [_make_ep("a"), _make_ep("b")]
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda group=None: fake_eps if group == "amaca.codes" else [],
    )
    loaded = load_entry_points()
    assert sorted(loaded) == ["a", "b"]
    names = {c.name for c in all_codes()}
    assert {"plugin-a", "plugin-b"} <= names


def test_load_entry_points_returns_empty_when_no_plugins(monkeypatch) -> None:
    monkeypatch.setattr(importlib.metadata, "entry_points", lambda group=None: [])
    assert load_entry_points() == []


def test_load_entry_points_swallows_broken_plugin(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda group=None: [_make_ep("broken", raises=True)] if group == "amaca.codes" else [],
    )
    loaded = load_entry_points()
    assert loaded == []  # broken plugin did not register
    # Demo and any earlier plugins are unaffected.
    assert "demo" in {c.name for c in all_codes()}
