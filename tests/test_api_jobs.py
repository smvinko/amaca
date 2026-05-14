"""API: /api/jobs routes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from amaca.codes.demo import DemoInputs
from amaca.core import JobStatus
from amaca.db import models
from amaca.workers import JobRunner

pytestmark = pytest.mark.api


async def test_submit_demo_job(
    client: AsyncClient, user: models.User, runner: JobRunner
) -> None:
    payload = {"code": "demo", "inputs": DemoInputs().model_dump()}
    r = await client.post("/api/jobs", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["code_name"] == "demo"
    assert body["owner_id"] == user.id
    # Status may be queued, running, or succeeded depending on scheduling.
    await runner.wait(body["id"])


async def test_submit_validation_error(client: AsyncClient) -> None:
    r = await client.post(
        "/api/jobs", json={"code": "demo", "inputs": {"n_points": 0}}
    )
    assert r.status_code == 422


async def test_submit_unknown_code(client: AsyncClient) -> None:
    r = await client.post("/api/jobs", json={"code": "missing", "inputs": {}})
    assert r.status_code == 404


async def test_list_jobs_filters_by_owner(
    client: AsyncClient, db, user: models.User, admin: models.User
) -> None:
    j1 = models.Job(owner_id=user.id, code_name="demo", code_version="0.1.0",
                    status=JobStatus.QUEUED.value, inputs_json={})
    j2 = models.Job(owner_id=admin.id, code_name="demo", code_version="0.1.0",
                    status=JobStatus.QUEUED.value, inputs_json={})
    db.add_all([j1, j2])
    db.commit()
    db.refresh(j1)
    db.refresh(j2)
    r = await client.get("/api/jobs")
    assert r.status_code == 200
    ids = {j["id"] for j in r.json()}
    assert j1.id in ids
    assert j2.id not in ids


async def test_admin_sees_all_jobs(
    admin_client: AsyncClient, db, user: models.User, admin: models.User
) -> None:
    j1 = models.Job(owner_id=user.id, code_name="demo", code_version="0.1.0",
                    status=JobStatus.QUEUED.value, inputs_json={})
    j2 = models.Job(owner_id=admin.id, code_name="demo", code_version="0.1.0",
                    status=JobStatus.QUEUED.value, inputs_json={})
    db.add_all([j1, j2])
    db.commit()
    db.refresh(j1)
    db.refresh(j2)
    r = await admin_client.get("/api/jobs")
    assert r.status_code == 200
    ids = {j["id"] for j in r.json()}
    assert {j1.id, j2.id} <= ids


async def test_other_users_job_hidden_as_404(
    client: AsyncClient, db, admin: models.User
) -> None:
    j = models.Job(owner_id=admin.id, code_name="demo", code_version="0.1.0",
                   status=JobStatus.QUEUED.value, inputs_json={})
    db.add(j)
    db.commit()
    db.refresh(j)
    r = await client.get(f"/api/jobs/{j.id}")
    assert r.status_code == 404


async def test_cancel_running_job_round_trip(
    client: AsyncClient, runner: JobRunner
) -> None:
    payload = {"code": "demo", "inputs": DemoInputs(sleep_s=1.5).model_dump()}
    r = await client.post("/api/jobs", json=payload)
    jid = r.json()["id"]
    r2 = await client.delete(f"/api/jobs/{jid}")
    assert r2.status_code == 204
    await runner.wait(jid)
    r3 = await client.get(f"/api/jobs/{jid}")
    assert r3.json()["status"] == JobStatus.CANCELLED.value


async def test_cancel_already_finished_returns_409(
    client: AsyncClient, runner: JobRunner
) -> None:
    payload = {"code": "demo", "inputs": DemoInputs().model_dump()}
    r = await client.post("/api/jobs", json=payload)
    jid = r.json()["id"]
    await runner.wait(jid)
    r2 = await client.delete(f"/api/jobs/{jid}")
    assert r2.status_code == 409


async def test_get_job_logs(client: AsyncClient, runner: JobRunner) -> None:
    payload = {"code": "demo", "inputs": DemoInputs().model_dump()}
    r = await client.post("/api/jobs", json=payload)
    jid = r.json()["id"]
    await runner.wait(jid)
    r2 = await client.get(f"/api/jobs/{jid}/logs")
    assert r2.status_code == 200
    lines = [row["line"] for row in r2.json()]
    assert any("starting" in line for line in lines)
