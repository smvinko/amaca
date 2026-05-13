"""Contract tests every registered Code must satisfy.

This module forces import of the bundled adapter package so its
``@register`` side-effects fire, then runs the same contract checks
against each code in the registry. A code that ships with amaca and
fails any of these checks is broken and must be fixed before merge.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel

from amaca.core import Code, JobContext, all_codes
import amaca.codes.demo  # noqa: F401  -- triggers @register

pytestmark = pytest.mark.contract


def _ctx(tmp_path: Path) -> JobContext:
    return JobContext(
        job_id=1,
        user_id=1,
        work_dir=tmp_path,
        log=lambda line: None,
        check_cancelled=lambda: False,
    )


@pytest.fixture(params=all_codes(), ids=lambda c: c.name)
def code_cls(request: pytest.FixtureRequest) -> type[Code]:
    return request.param


def test_required_class_attrs_present(code_cls: type[Code]) -> None:
    assert isinstance(code_cls.name, str) and code_cls.name
    assert isinstance(code_cls.title, str) and code_cls.title
    assert isinstance(code_cls.version, str) and code_cls.version
    assert issubclass(code_cls.InputSchema, BaseModel)
    assert issubclass(code_cls.OutputSchema, BaseModel)


def test_name_is_safe_identifier(code_cls: type[Code]) -> None:
    """The ``name`` is used in URLs and DB keys — keep it kebab/snake-case."""
    assert code_cls.name.replace("-", "_").replace("_", "").isalnum()
    assert code_cls.name.islower()


def test_default_inputs_parse(code_cls: type[Code]) -> None:
    """``InputSchema()`` must succeed (i.e. every required field has a
    default). This is what the UI uses to show a sensible initial form
    state. Codes with genuinely required-without-default fields will
    need a separate ``example_inputs()`` hook in v2."""
    code_cls.InputSchema()


def test_run_with_defaults_returns_outputs(
    code_cls: type[Code], tmp_path: Path
) -> None:
    inputs = code_cls.InputSchema()
    instance = code_cls()
    outputs = instance.run(inputs, _ctx(tmp_path))
    assert isinstance(outputs, code_cls.OutputSchema)


def test_run_propagates_cancellation(code_cls: type[Code], tmp_path: Path) -> None:
    """When ``check_cancelled`` is True the adapter must not return
    normally — either raise ``RuntimeError('cancelled')`` or some other
    exception. (Adapters whose work is genuinely uninterruptible can
    override this contract by skipping the test via a marker.)"""
    inputs = code_cls.InputSchema()
    ctx = JobContext(
        job_id=1, user_id=1, work_dir=tmp_path,
        log=lambda line: None,
        check_cancelled=lambda: True,
    )
    instance = code_cls()
    with pytest.raises(Exception):
        instance.run(inputs, ctx)
