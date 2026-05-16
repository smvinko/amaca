"""Cross-cutting types for amaca's core."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


def _noop_progress(fraction: float, message: str = "") -> None:
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
    - ``progress(fraction, message="")`` — report run progress;
      ``fraction`` is 0..1 (clamped), ``message`` an optional short
      status. Streamed live to the job page and surfaced as a progress
      bar. Optional: adapters that don't call it just don't get a bar.
    """
    job_id: int
    user_id: int
    work_dir: Path
    log: Callable[[str], None]
    check_cancelled: Callable[[], bool]
    progress: Callable[[float, str], None] = field(default=_noop_progress)
