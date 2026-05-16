"""Cross-cutting types for amaca's core."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


def _noop_progress(
    fraction: float,
    message: str = "",
    *,
    step: int | None = None,
    total: int | None = None,
    phase: str | None = None,
) -> None:
    """Default ``JobContext.progress`` — does nothing.

    Lets adapters (and tests) construct a context without a progress
    sink, and means calling ``ctx.progress(...)`` is always safe even
    when nothing is listening.
    """


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED)


@dataclass
class JobContext:
    """Passed to ``Code.run()`` — the adapter's view of the runtime.

    Carries identifiers, a per-job scratch directory, and two callables
    the adapter is expected to use:

    - ``log(line)`` — append a line to the job's streamed log channel.
    - ``check_cancelled()`` — return True if the user has asked to cancel;
      the adapter is expected to poll this in any loop longer than a few
      seconds and raise/return cleanly when True.
    - ``progress(fraction, message="", *, step=None, total=None,
      phase=None)`` — report run progress. ``fraction`` is 0..1
      (clamped; if omitted-as-None and step/total are given the worker
      derives it). ``step``/``total`` give a real step counter and
      ``phase`` names the current stage (e.g. "kinetics"). Streamed
      live to the job page as a bar + "phase — step/total". Optional:
      adapters that don't call it just don't get a bar. Long-running
      out-of-process codes should instead emit the ``@amaca:progress``
      stdout sentinel and be launched via ``amaca.core.run_monitored``
      (see SPEC) — that bridges the sentinel to this callable.
    """
    job_id: int
    user_id: int
    work_dir: Path
    log: Callable[[str], None]
    check_cancelled: Callable[[], bool]
    progress: Callable[..., None] = field(default=_noop_progress)
