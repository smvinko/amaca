"""DB model basic roundtrip + cascade tests."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from amaca.core import JobStatus
from amaca.db import models

pytestmark = pytest.mark.unit


def test_user_create_defaults(db: Session) -> None:
    u = models.User(github_id=42, github_username="alice", email="a@b.com")
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.id is not None
    assert u.role == "user"
    assert u.disabled is False
    assert u.is_admin is False
    assert u.created_at is not None
    assert u.last_login_at is None


def test_user_role_admin_flag(db: Session) -> None:
    u = models.User(github_id=1, github_username="root", role="admin")
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.is_admin is True


def test_apitoken_roundtrip(db: Session, user: models.User) -> None:
    t = models.ApiToken(
        user_id=user.id, name="laptop CLI", prefix="amk_abcd", hash="$2b$xxx"
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    assert t.is_active is True
    assert t.user.github_username == "alice"
    # Pulling tokens from the User side picks up the new row.
    db.refresh(user)
    assert len(user.tokens) == 1


def test_job_lifecycle_fields_default(db: Session, user: models.User) -> None:
    j = models.Job(
        owner_id=user.id, code_name="demo", code_version="0.1.0",
        inputs_json={"n_points": 5},
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    assert j.status == JobStatus.QUEUED.value
    assert j.status_enum is JobStatus.QUEUED
    assert j.started_at is None and j.finished_at is None
    assert j.error_text is None
    assert j.outputs_json is None


def test_job_cascade_delete_through_user(db: Session, user: models.User) -> None:
    j = models.Job(
        owner_id=user.id, code_name="demo", code_version="0.1.0",
        inputs_json={},
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    db.add(models.JobLog(job_id=j.id, line="hello"))
    db.add(models.Artifact(
        job_id=j.id, name="out.txt", path=f"job-{j.id}/out.txt",
        size_bytes=11, mime_type="text/plain",
    ))
    db.commit()

    db.delete(user)
    db.commit()
    assert db.query(models.Job).count() == 0
    assert db.query(models.JobLog).count() == 0
    assert db.query(models.Artifact).count() == 0
    assert db.query(models.ApiToken).count() == 0
