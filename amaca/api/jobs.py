"""Job routes: submit, list, get, cancel, logs, WebSocket stream."""
from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import ValidationError
from sqlalchemy import select

from amaca.core import JobStatus, get
from amaca.db import models

from .deps import DB, CurrentUser, Runner
from .schemas import JobListItem, JobLogLine, JobOut, JobSubmit

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _to_out(job: models.Job) -> JobOut:
    return JobOut(
        id=job.id,
        owner_id=job.owner_id,
        code_name=job.code_name,
        code_version=job.code_version,
        status=job.status,
        inputs=job.inputs_json,
        outputs=job.outputs_json,
        error_text=job.error_text,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _ensure_visible(job: models.Job | None, user: models.User) -> models.Job:
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    if job.owner_id != user.id and not user.is_admin:
        # Hide existence from non-admins.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return job


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def submit_job(
    payload: JobSubmit, user: CurrentUser, db: DB, runner: Runner,
) -> JobOut:
    try:
        code_cls = get(payload.code)
    except KeyError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"code {payload.code!r} not found"
        )
    try:
        inputs_validated = code_cls.InputSchema.model_validate(payload.inputs)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.errors())

    job = models.Job(
        owner_id=user.id,
        code_name=code_cls.name,
        code_version=code_cls.version,
        status=JobStatus.QUEUED.value,
        inputs_json=inputs_validated.model_dump(mode="json"),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    await runner.submit(job.id)
    return _to_out(job)


@router.get("", response_model=list[JobListItem])
async def list_jobs(
    user: CurrentUser, db: DB,
    code: str | None = None,
    status_: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[models.Job]:
    q = db.query(models.Job)
    if not user.is_admin:
        q = q.filter(models.Job.owner_id == user.id)
    if code is not None:
        q = q.filter(models.Job.code_name == code)
    if status_ is not None:
        q = q.filter(models.Job.status == status_)
    return q.order_by(models.Job.created_at.desc()).limit(limit).all()


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, user: CurrentUser, db: DB) -> JobOut:
    return _to_out(_ensure_visible(db.get(models.Job, job_id), user))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: int, user: CurrentUser, db: DB, runner: Runner,
) -> None:
    job = _ensure_visible(db.get(models.Job, job_id), user)
    if job.status_enum.is_terminal:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"job already {job.status}",
        )
    runner.request_cancel(job.id)


@router.get("/{job_id}/logs", response_model=list[JobLogLine])
async def get_job_logs(
    job_id: int, user: CurrentUser, db: DB,
) -> list[models.JobLog]:
    _ensure_visible(db.get(models.Job, job_id), user)
    return db.scalars(
        select(models.JobLog)
        .where(models.JobLog.job_id == job_id)
        .order_by(models.JobLog.id)
    ).all()


@router.websocket("/{job_id}/stream")
async def stream_job(websocket: WebSocket, job_id: int) -> None:
    """Push log + status events for the job in real time.

    Auth: session cookie only (browsers can't set custom headers on the
    WebSocket handshake). Bearer-token CLIs should poll ``/logs``
    and ``/`` instead.
    """
    session = websocket.scope.get("session") or {}
    user_id = session.get("user_id")
    if user_id is None:
        await websocket.close(code=4401)
        return

    SessionLocal = websocket.app.state.SessionLocal
    runner = websocket.app.state.runner

    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        if user is None or user.disabled:
            await websocket.close(code=4401)
            return
        job = db.get(models.Job, job_id)
        if job is None or (job.owner_id != user.id and not user.is_admin):
            await websocket.close(code=4404)
            return
        # Capture terminal status now so a job that finished before the
        # subscriber arrived still gets a final frame.
        if job.status_enum.is_terminal:
            await websocket.accept()
            await websocket.send_json({"type": "status", "status": job.status})
            await websocket.close()
            return

    queue = runner.subscribe(job_id)
    await websocket.accept()
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event.get("type") == "status" and event["status"] in (
                JobStatus.SUCCEEDED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
            ):
                break
    except WebSocketDisconnect:
        pass
    finally:
        runner.unsubscribe(job_id, queue)
        try:
            await websocket.close()
        except RuntimeError:
            pass
