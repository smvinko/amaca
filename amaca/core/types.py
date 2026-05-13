"""Cross-cutting types for amaca's core."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


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
    """
    job_id: int
    user_id: int
    work_dir: Path
    log: Callable[[str], None]
    check_cancelled: Callable[[], bool]
