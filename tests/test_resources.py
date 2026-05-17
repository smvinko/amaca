"""amaca.core.resources — host detection + per-job compute budget."""
from __future__ import annotations

import pytest

from amaca.core import resources

pytestmark = pytest.mark.unit


def test_host_cores_is_positive() -> None:
    assert resources.host_cores() >= 1


def test_cores_per_job_defaults_to_eight_capped_at_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AMACA_CORES_PER_JOB", raising=False)
    # Small host → default 8 is clamped down to the host count.
    monkeypatch.setattr(resources, "host_cores", lambda: 4)
    assert resources.cores_per_job() == 4
    # Big host → the soft default (8) wins.
    monkeypatch.setattr(resources, "host_cores", lambda: 32)
    assert resources.cores_per_job() == 8


def test_cores_per_job_env_override_still_capped_at_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resources, "host_cores", lambda: 16)
    monkeypatch.setenv("AMACA_CORES_PER_JOB", "12")
    assert resources.cores_per_job() == 12          # honoured
    monkeypatch.setenv("AMACA_CORES_PER_JOB", "999")
    assert resources.cores_per_job() == 16          # never exceeds host
    monkeypatch.setenv("AMACA_CORES_PER_JOB", "nonsense")
    assert resources.cores_per_job() == 8           # junk → default


def test_max_concurrent_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resources, "host_cores", lambda: 20)
    monkeypatch.delenv("AMACA_CORES_PER_JOB", raising=False)
    monkeypatch.delenv("AMACA_MAX_CONCURRENT_JOBS", raising=False)
    # default = host // cores_per_job  → 20 // 8 == 2
    assert resources.max_concurrent_jobs() == 2
    monkeypatch.setenv("AMACA_MAX_CONCURRENT_JOBS", "5")
    assert resources.max_concurrent_jobs() == 5
    monkeypatch.setenv("AMACA_MAX_CONCURRENT_JOBS", "0")  # invalid → default
    assert resources.max_concurrent_jobs() == 2


def test_thread_env_pins_all_pools_and_preserves_base() -> None:
    base = {"PATH": "/usr/bin", "OMP_NUM_THREADS": "64"}
    env = resources.thread_env(3, base=base)
    assert env["PATH"] == "/usr/bin"                 # base preserved
    for var in resources.THREAD_ENV_VARS:
        assert env[var] == "3"                       # all pools pinned
    # Never emits < 1.
    assert resources.thread_env(0)["OMP_NUM_THREADS"] == "1"
