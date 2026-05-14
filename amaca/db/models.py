"""SQLAlchemy ORM models.

Five tables:
  - ``users``      — GitHub-identity-backed accounts
  - ``api_tokens`` — long-lived bearer tokens (CLI / scripts)
  - ``jobs``       — one row per code invocation
  - ``job_logs``   — append-only log lines per job (for stream replay)
  - ``artifacts``  — files emitted by a job (paths only; bytes on disk)

Schema design notes:
- All FKs use ``ondelete='CASCADE'`` so deleting a user cleanly drops
  their jobs/tokens.
- ``Job.inputs_json`` and ``Job.outputs_json`` store the validated
  Pydantic models as JSON. The runner serialises with ``model_dump()``;
  consumers re-hydrate with ``Code.InputSchema.model_validate(...)``.
- ``Job.status`` is a string column (not a SQL ENUM) so adding/removing
  states later doesn't require a migration on Postgres.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from amaca.core import JobStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    github_username: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="user")  # "user" | "admin"
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tokens: Mapped[list["ApiToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="tokens")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_name: Mapped[str] = mapped_column(String(64), index=True)
    code_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED.value, index=True)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    outputs_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="jobs")
    logs: Mapped[list["JobLog"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobLog.id"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def status_enum(self) -> JobStatus:
        return JobStatus(self.status)


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    line: Mapped[str] = mapped_column(Text)

    job: Mapped["Job"] = relationship(back_populates="logs")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    path: Mapped[str] = mapped_column(String(512))  # relative to data dir
    size_bytes: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped["Job"] = relationship(back_populates="artifacts")


# Useful composite indices for the common list-my-recent-jobs query.
Index("ix_jobs_owner_created", Job.owner_id, Job.created_at.desc())
Index("ix_jobs_status_created", Job.status, Job.created_at.desc())
