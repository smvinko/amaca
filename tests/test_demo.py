"""Demo-adapter specific tests (behaviour beyond the generic contract)."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from amaca.codes.demo import Demo, DemoInputs, DemoOutputs
from amaca.core import JobContext

pytestmark = pytest.mark.unit


def _ctx(tmp_path: Path, *, cancelled: bool = False, log: list[str] | None = None) -> JobContext:
    return JobContext(
        job_id=42, user_id=7, work_dir=tmp_path,
        log=(log.append if log is not None else (lambda line: None)),
        check_cancelled=lambda: cancelled,
    )


def test_demo_default_run_produces_sine_curve(tmp_path: Path) -> None:
    out = Demo().run(DemoInputs(), _ctx(tmp_path))
    assert isinstance(out, DemoOutputs)
    assert out.waveform == "sine"
    assert out.n_points == 20
    assert len(out.x) == 20 and len(out.y) == 20
    # First sample is sin(0) == 0, last is sin(2π) ≈ 0
    assert out.y[0] == pytest.approx(0.0, abs=1e-12)
    assert out.y[-1] == pytest.approx(0.0, abs=1e-12)
    # Quarter-period sample for n=20 is index 5 → x ≈ 1.6535 → sin ≈ 0.998
    assert max(out.y) == pytest.approx(1.0, abs=1e-2)


def test_demo_amplitude_scales_output(tmp_path: Path) -> None:
    out = Demo().run(DemoInputs(amplitude=2.5), _ctx(tmp_path))
    assert max(out.y) == pytest.approx(2.5, abs=2.5e-2)


def test_demo_waveform_square(tmp_path: Path) -> None:
    out = Demo().run(DemoInputs(waveform="square", n_points=8), _ctx(tmp_path))
    assert set(out.y) == {1.0, -1.0}


def test_demo_writes_log_lines(tmp_path: Path) -> None:
    log: list[str] = []
    Demo().run(DemoInputs(), _ctx(tmp_path, log=log))
    assert any("starting" in line for line in log)
    assert any("rms=" in line for line in log)


def test_demo_cancellation_raises(tmp_path: Path) -> None:
    # sleep>0 ensures the cancel-poll loop runs at least once
    with pytest.raises(RuntimeError, match="cancelled"):
        Demo().run(DemoInputs(sleep_s=0.5), _ctx(tmp_path, cancelled=True))


def test_demo_input_validation_rejects_negative_amplitude() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DemoInputs(amplitude=-1.0)


def test_demo_input_validation_rejects_too_many_points() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DemoInputs(n_points=10_001)


def test_demo_estimate_cost_present(tmp_path: Path) -> None:
    cost = Demo().estimate_cost(DemoInputs(sleep_s=1.5))
    assert cost is not None
    assert "time" in cost
    assert "1.5" in cost["time"]


def test_demo_rms_matches_pure_sine() -> None:
    """RMS of a unit sine over [0, 2π] is 1/√2; demo should approach this for big n."""
    out = Demo().run(DemoInputs(n_points=1000), _ctx(Path("/tmp")))
    assert out.rms == pytest.approx(1 / math.sqrt(2), abs=1e-2)
