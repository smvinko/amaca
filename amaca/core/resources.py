"""Host CPU detection + per-job compute budget — code-agnostic.

amaca is the platform that hosts codes; resource policy lives **here**,
not in any adapter. Every out-of-process code goes through
``run_monitored``, which enforces the per-job CPU budget defined here,
so a single adapter can never decide to oversubscribe the machine
amaca runs on.

Two env knobs (read at call time, so they track the running host /
deployment, never an install-time snapshot):

- ``AMACA_CORES_PER_JOB``     soft per-job core budget (default 8),
                              always capped at the host core count.
- ``AMACA_MAX_CONCURRENT_JOBS`` simple cap on simultaneously *running*
                              jobs (default ``host // cores_per_job``,
                              so total in-flight threads ≈ the host).
"""
from __future__ import annotations

import os
from collections.abc import Mapping

# Thread-pool env vars every job's subprocess gets pinned to its
# budget: OpenMP plus the common BLAS backends (OpenBLAS, MKL, Apple
# Accelerate/vecLib, NumExpr) so the core count is actually respected
# and BLAS doesn't spin up its own host-wide pool underneath.
THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)

_DEFAULT_CORES_PER_JOB = 8


def host_cores() -> int:
    """Logical CPUs actually available to this process (always ≥ 1).

    Prefers ``os.sched_getaffinity`` (Linux: respects CPU affinity /
    cgroup pinning, so it's correct inside a container) and falls back
    to ``os.cpu_count`` (macOS and others have no affinity API).
    """
    try:
        return max(1, len(os.sched_getaffinity(0)))  # type: ignore[attr-defined]
    except AttributeError:
        return max(1, os.cpu_count() or 1)


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def cores_per_job() -> int:
    """Per-job CPU budget = ``min(AMACA_CORES_PER_JOB or 8, host)``.

    The host-core ceiling is always enforced, so a job can never ask
    for more cores than the machine amaca runs on — which is exactly
    the "default is never more than available cores" guarantee, with
    no install-time query (this is evaluated on the run host).
    """
    want = _env_int("AMACA_CORES_PER_JOB")
    if want is None or want < 1:
        want = _DEFAULT_CORES_PER_JOB
    return max(1, min(want, host_cores()))


def max_concurrent_jobs() -> int:
    """Cap on simultaneously *running* jobs (≥ 1).

    Override via ``AMACA_MAX_CONCURRENT_JOBS``; default keeps the total
    in-flight thread count near the host size: ``host // cores_per_job``.
    """
    override = _env_int("AMACA_MAX_CONCURRENT_JOBS")
    if override is not None and override >= 1:
        return override
    return max(1, host_cores() // cores_per_job())


def thread_env(
    n: int, base: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Copy of ``base`` (or ``os.environ``) with the thread-pool caps
    pinned to ``n``. Everything else (PATH, venv, …) is preserved."""
    env = dict(base if base is not None else os.environ)
    for var in THREAD_ENV_VARS:
        env[var] = str(max(1, int(n)))
    return env
