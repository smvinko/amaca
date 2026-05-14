"""In-process async job runner.

Drives each ``Job`` row through its lifecycle:

  QUEUED → RUNNING → (SUCCEEDED | FAILED | CANCELLED)

The adapter's ``run(...)`` is synchronous, so we dispatch it on a
worker thread via ``asyncio.to_thread`` while the runner coroutine
stays on the event loop. Log lines and status changes are persisted to
the DB and broadcast to any WebSocket subscribers.

v1 is single-process. Swapping to a real queue (arq/Redis) later
replaces this module without touching the adapter contract.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from amaca.core import JobContext, JobStatus, get
from amaca.db import models

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobRunner:
    """Maintains the live tasks for an in-process worker."""

    def __init__(self, SessionLocal: sessionmaker[Session], data_dir: Path) -> None:
        self._SessionLocal = SessionLocal
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._cancel_flags: dict[int, bool] = {}
        self._subscribers: dict[int, list[asyncio.Queue[dict[str, Any]]]] = {}

    # ------------------------------------------------------------------ public

    async def submit(self, job_id: int) -> asyncio.Task[None]:
        """Schedule the job. The ``Job`` row must already exist with status=QUEUED."""
        existing = self._tasks.get(job_id)
        if existing is not None and not existing.done():
            return existing
        task = asyncio.create_task(self._run(job_id), name=f"job-{job_id}")
        self._tasks[job_id] = task
        return task

    def request_cancel(self, job_id: int) -> bool:
        """Set the cancellation flag. Returns True if the job is live."""
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return False
        self._cancel_flags[job_id] = True
        return True

    def subscribe(self, job_id: int) -> asyncio.Queue[dict[str, Any]]:
        """Return a queue that receives future log + status events for this job."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: int, q: asyncio.Queue[dict[str, Any]]) -> None:
        if q in self._subscribers.get(job_id, []):
            self._subscribers[job_id].remove(q)

    async def wait(self, job_id: int) -> None:
        """For tests / shutdown: await the task if any."""
        task = self._tasks.get(job_id)
        if task is not None:
            await task

    async def drain(self) -> None:
        """Await all live tasks (for graceful shutdown)."""
        live = [t for t in self._tasks.values() if not t.done()]
        if live:
            await asyncio.gather(*live, return_exceptions=True)

    # ------------------------------------------------------------------ internals

    @contextmanager
    def _session(self):
        db = self._SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _broadcast(self, job_id: int, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(job_id, ())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("subscriber queue full for job %d; dropping event", job_id)

    async def _run(self, job_id: int) -> None:
        # ---- load + transition to RUNNING ----
        try:
            with self._session() as db:
                job = db.get(models.Job, job_id)
                if job is None:
                    logger.error("job %d not found at dispatch", job_id)
                    return
                code_cls = get(job.code_name)
                inputs = code_cls.InputSchema.model_validate(job.inputs_json)
                owner_id = job.owner_id
                job.status = JobStatus.RUNNING.value
                job.started_at = _now()
                db.commit()
            self._broadcast(job_id, {"type": "status", "status": JobStatus.RUNNING.value})
        except Exception as exc:
            # validation/lookup failed before we even started — record as FAILED
            self._finalise(job_id, JobStatus.FAILED, error=f"{type(exc).__name__}: {exc}")
            return

        job_dir = self._data_dir / f"job-{job_id}"
        job_dir.mkdir(parents=True, exist_ok=True)

        instance = code_cls()
        log_lock = threading.Lock()

        def log(line: str) -> None:
            # Called from the adapter's worker thread. SQLite with
            # check_same_thread=False is fine; serialise with a lock to
            # avoid interleaving commits.
            with log_lock, self._session() as db:
                db.add(models.JobLog(job_id=job_id, line=line))
                db.commit()
            self._broadcast(job_id, {"type": "log", "line": line})

        def check_cancelled() -> bool:
            return self._cancel_flags.get(job_id, False)

        ctx = JobContext(
            job_id=job_id, user_id=owner_id, work_dir=job_dir,
            log=log, check_cancelled=check_cancelled,
        )

        # ---- dispatch the adapter ----
        try:
            outputs = await asyncio.to_thread(instance.run, inputs, ctx)
        except Exception as exc:
            if str(exc) == "cancelled" and check_cancelled():
                self._finalise(job_id, JobStatus.CANCELLED)
            else:
                self._finalise(job_id, JobStatus.FAILED, error=f"{type(exc).__name__}: {exc}")
            return
        finally:
            self._cancel_flags.pop(job_id, None)

        # ---- success ----
        outputs_json = outputs.model_dump(mode="json")
        self._finalise(job_id, JobStatus.SUCCEEDED, outputs_json=outputs_json)

    def _finalise(
        self,
        job_id: int,
        status: JobStatus,
        *,
        error: str | None = None,
        outputs_json: dict[str, Any] | None = None,
    ) -> None:
        with self._session() as db:
            job = db.get(models.Job, job_id)
            if job is None:
                return
            job.status = status.value
            job.finished_at = _now()
            if error is not None:
                job.error_text = error
            if outputs_json is not None:
                job.outputs_json = outputs_json
            db.commit()
        event: dict[str, Any] = {"type": "status", "status": status.value}
        if error is not None:
            event["error"] = error
        self._broadcast(job_id, event)
