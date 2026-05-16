"""run_monitored: subprocess + @amaca:progress sentinel bridging."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

from amaca.core import JobContext, run_monitored

pytestmark = pytest.mark.unit


def _ctx(tmp_path: Path, *, cancel: threading.Event | None = None) -> tuple[
    JobContext, list[str], list[dict]
]:
    logs: list[str] = []
    prog: list[dict] = []
    ctx = JobContext(
        job_id=1,
        user_id=1,
        work_dir=tmp_path,
        log=logs.append,
        check_cancelled=(lambda: cancel.is_set()) if cancel else (lambda: False),
        progress=lambda frac, msg="", **kw: prog.append(
            {"fraction": frac, "message": msg, **kw}
        ),
    )
    return ctx, logs, prog


def test_sentinel_lines_bridge_to_progress(tmp_path: Path) -> None:
    ctx, logs, prog = _ctx(tmp_path)
    script = (
        "import sys\n"
        "print('hello from child')\n"
        'print(\'@amaca:progress {"phase":"kinetics","step":1,"total":4}\')\n'
        'print(\'@amaca:progress {"phase":"kinetics","step":4,"total":4,'
        '"message":"done"}\')\n'
        "print('trailing log line')\n"
    )
    rc = run_monitored([sys.executable, "-c", script], ctx, poll_s=0.02)
    assert rc == 0
    # Non-sentinel lines are logged verbatim; sentinels are NOT logged.
    assert "hello from child" in logs
    assert "trailing log line" in logs
    assert not any("@amaca:progress" in line for line in logs)
    # Sentinels parsed → progress with step/total/phase.
    assert prog[0] == {"fraction": None, "message": "",
                       "step": 1, "total": 4, "phase": "kinetics"}
    assert prog[-1]["step"] == 4 and prog[-1]["message"] == "done"


def test_malformed_sentinel_is_logged_not_dropped(tmp_path: Path) -> None:
    ctx, logs, prog = _ctx(tmp_path)
    script = "print('@amaca:progress not-json')\n"
    run_monitored([sys.executable, "-c", script], ctx, poll_s=0.02)
    assert any("not-json" in line for line in logs)
    assert prog == []


def test_nonzero_exit_raises_with_tail(tmp_path: Path) -> None:
    ctx, logs, _ = _ctx(tmp_path)
    script = "print('boom about to happen'); raise SystemExit(3)"
    with pytest.raises(RuntimeError, match="exited with code 3"):
        run_monitored([sys.executable, "-c", script], ctx, poll_s=0.02)


def test_cancellation_terminates_child(tmp_path: Path) -> None:
    cancel = threading.Event()
    ctx, _, _ = _ctx(tmp_path, cancel=cancel)
    # Child sleeps 30s; fire cancel shortly after launch.
    threading.Timer(0.4, cancel.set).start()
    t0 = __import__("time").monotonic()
    with pytest.raises(RuntimeError, match="cancelled"):
        run_monitored(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            ctx, poll_s=0.05,
        )
    assert __import__("time").monotonic() - t0 < 10  # killed promptly
