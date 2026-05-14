"""Shared fixtures for amaca tests.

A fresh SQLite DB (temp file, not :memory: so worker threads see the
same rows) is provided per test, plus a default User, a SessionLocal,
and a JobRunner. The Demo adapter is imported here so all tests have
the registry populated.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from amaca.db import Base, make_engine, make_sessionmaker
from amaca.db import models
from amaca.workers import JobRunner

import amaca.codes.demo  # noqa: F401  -- registers the Demo adapter


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    db_path = tmp_path / "test.db"
    engine = make_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def SessionLocal(engine: Engine) -> sessionmaker[Session]:
    return make_sessionmaker(engine)


@pytest.fixture
def db(SessionLocal: sessionmaker[Session]) -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def user(db: Session) -> models.User:
    u = models.User(github_id=42, github_username="alice", email="a@b.com")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def admin(db: Session) -> models.User:
    u = models.User(github_id=1, github_username="root", role="admin")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def runner(SessionLocal: sessionmaker[Session], tmp_path: Path) -> JobRunner:
    return JobRunner(SessionLocal, tmp_path / "data")
