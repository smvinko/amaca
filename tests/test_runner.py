"""End-to-end JobRunner tests against the Demo adapter."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from amaca.codes.demo import DemoInputs
from amaca.core import JobStatus
from amaca.db import models
from amaca.workers import JobRunner

pytestmark = pytest.mark.unit


def _make_job(db: Session, user: models.User, inputs: dict | None = None) -> models.Job:
    job = models.Job(
        owner_id=user.id,
        code_name="demo",
        code_version="0.1.0",
        status=JobStatus.QUEUED.value,
        inputs_json=inputs if inputs is not None else DemoInputs().model_dump(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


async def test_runner_success_demo(
    runner: JobRunner, db: Session, user: models.User
) -> None:
    job = _make_job(db, user)
    await runner.submit(job.id)
    await runner.wait(job.id)

    db.refresh(job)
    assert job.status == JobStatus.SUCCEEDED.value
    assert job.error_text is None
    assert job.outputs_json is not None
    assert job.outputs_json["n_points"] == 20
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.finished_at >= job.started_at

    logs = db.scalars(
        select(models.JobLog).where(models.JobLog.job_id == job.id)
    ).all()
    assert len(logs) >= 2
    assert any("starting" in row.line for row in logs)
    assert any("rms=" in row.line for row in logs)


async def test_runner_cancellation(
    runner: JobRunner, db: Session, user: models.User
) -> None:
    job = _make_job(db, user, inputs=DemoInputs(sleep_s=1.5).model_dump())
    await runner.submit(job.id)
    await asyncio.sleep(0.1)
    cancelled = runner.request_cancel(job.id)
    assert cancelled
    await runner.wait(job.id)

    db.refresh(job)
    assert job.status == JobStatus.CANCELLED.value
    assert job.error_text is None


async def test_runner_validation_failure_marks_failed(
    runner: JobRunner, db: Session, user: models.User
) -> None:
    # n_points=0 violates the Field(ge=2) constraint — surfaces during
    # InputSchema.model_validate inside the runner.
    job = _make_job(db, user, inputs={"n_points": 0})
    await runner.submit(job.id)
    await runner.wait(job.id)

    db.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.error_text is not None
    assert "ValidationError" in job.error_text or "n_points" in job.error_text


async def test_runner_broadcasts_log_and_status_events(
    runner: JobRunner, db: Session, user: models.User
) -> None:
    job = _make_job(db, user)
    sub = runner.subscribe(job.id)
    await runner.submit(job.id)
    await runner.wait(job.id)

    events: list[dict] = []
    while not sub.empty():
        events.append(sub.get_nowait())
    types = [e["type"] for e in events]
    assert "log" in types
    statuses = [e["status"] for e in events if e["type"] == "status"]
    assert "running" in statuses
    assert "succeeded" in statuses


async def test_runner_broadcasts_progress_and_clears(
    runner: JobRunner, db: Session, user: models.User
) -> None:
    job = _make_job(db, user, inputs=DemoInputs(sleep_s=0.3).model_dump())
    sub = runner.subscribe(job.id)
    await runner.submit(job.id)
    await runner.wait(job.id)

    events: list[dict] = []
    while not sub.empty():
        events.append(sub.get_nowait())
    prog = [e for e in events if e["type"] == "progress"]
    assert prog, "no progress events broadcast"
    assert all(0.0 <= e["fraction"] <= 1.0 for e in prog)
    assert prog[-1]["fraction"] == pytest.approx(1.0)
    assert all(isinstance(e["message"], str) for e in prog)
    # Progress is dropped once the job finalises.
    assert runner.progress_of(job.id) is None


def test_jobcontext_progress_defaults_to_noop(tmp_path: Path) -> None:
    """The contract stays back-compatible: a context built without a
    progress sink still has a safe, callable .progress."""
    from amaca.core import JobContext
    ctx = JobContext(
        job_id=1, user_id=1, work_dir=tmp_path,
        log=lambda _l: None, check_cancelled=lambda: False,
    )
    ctx.progress(0.5, "halfway")  # must not raise


async def test_runner_double_submit_is_idempotent(
    runner: JobRunner, db: Session, user: models.User
) -> None:
    job = _make_job(db, user, inputs=DemoInputs(sleep_s=0.2).model_dump())
    t1 = await runner.submit(job.id)
    t2 = await runner.submit(job.id)
    assert t1 is t2
    await runner.wait(job.id)
    db.refresh(job)
    assert job.status == JobStatus.SUCCEEDED.value


async def test_runner_request_cancel_unknown_returns_false(runner: JobRunner) -> None:
    assert runner.request_cancel(9999) is False


# --------------------------------------------------- concurrency cap

async def test_runner_concurrency_cap_serialises(
    SessionLocal, db: Session, user: models.User, tmp_path: Path
) -> None:
    """With max_concurrent=1, a second job stays QUEUED until the first
    finishes (the cap serialises dispatch; resource policy is amaca's)."""
    r = JobRunner(SessionLocal, tmp_path / "d", max_concurrent=1)
    a = _make_job(db, user, DemoInputs(sleep_s=0.4).model_dump())
    b = _make_job(db, user, DemoInputs(sleep_s=0.05).model_dump())
    await r.submit(a.id)
    await r.submit(b.id)

    await asyncio.sleep(0.15)            # A running; B must still wait
    db.refresh(a)
    db.refresh(b)
    assert a.status == JobStatus.RUNNING.value
    assert b.status == JobStatus.QUEUED.value

    await r.wait(a.id)
    await r.wait(b.id)
    db.refresh(a)
    db.refresh(b)
    assert a.status == b.status == JobStatus.SUCCEEDED.value
    # B only started after A released its slot.
    assert b.started_at is not None and a.finished_at is not None
    assert b.started_at >= a.finished_at


async def test_runner_cancel_while_queued_never_dispatches(
    SessionLocal, db: Session, user: models.User, tmp_path: Path
) -> None:
    """A job cancelled while waiting for a slot finalises CANCELLED
    without the adapter ever running (no started_at, no logs)."""
    r = JobRunner(SessionLocal, tmp_path / "d", max_concurrent=1)
    a = _make_job(db, user, DemoInputs(sleep_s=0.4).model_dump())
    b = _make_job(db, user, DemoInputs(sleep_s=0.2).model_dump())
    await r.submit(a.id)
    await r.submit(b.id)

    await asyncio.sleep(0.1)             # A running; B queued
    assert r.request_cancel(b.id) is True

    await r.wait(a.id)
    await r.wait(b.id)
    db.refresh(a)
    db.refresh(b)
    assert a.status == JobStatus.SUCCEEDED.value
    assert b.status == JobStatus.CANCELLED.value
    assert b.started_at is None         # adapter never dispatched
    blogs = db.scalars(
        select(models.JobLog).where(models.JobLog.job_id == b.id)
    ).all()
    assert blogs == []
