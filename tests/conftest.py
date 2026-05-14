"""Shared fixtures for amaca tests.

A fresh SQLite DB (temp file, not :memory: so worker threads see the
same rows) is provided per test, plus a default User, a SessionLocal,
and a JobRunner. The Demo adapter is imported here so all tests have
the registry populated.

For API tests we expose ``app``, ``client``, ``admin_client``, and
``raw_client`` (no auth override). The HTTP client is async because
route handlers spawn background runner tasks that need to live on the
test's event loop.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from amaca.api import create_app
from amaca.api.deps import current_user, get_db, get_runner
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


# --- API fixtures --- #

@pytest.fixture
def app(
    SessionLocal: sessionmaker[Session],
    runner: JobRunner,
    tmp_path: Path,
) -> FastAPI:
    """A FastAPI app wired to the test SessionLocal + runner.

    create_app builds its own engine/runner internally (which we ignore);
    we override the get_db / get_runner dependencies to point at the test
    fixtures, and set ``app.state.SessionLocal`` / ``app.state.runner``
    directly so WebSocket handlers (which bypass deps) also see the
    fixtures. We never enter the app's lifespan in tests.
    """
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'app.db'}",
        data_dir=tmp_path / "app_data",
        session_secret="test-secret-not-secure",
    )

    def _override_get_db() -> Iterator[Session]:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_runner] = lambda: runner
    app.state.SessionLocal = SessionLocal
    app.state.runner = runner
    return app


@pytest.fixture
async def client(app: FastAPI, user: models.User) -> AsyncIterator[AsyncClient]:
    """Authenticated client — current_user resolves to the ``user`` fixture."""
    app.dependency_overrides[current_user] = lambda: user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def admin_client(app: FastAPI, admin: models.User) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[current_user] = lambda: admin
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def raw_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """No auth override — exercises current_user's full logic (cookie/Bearer)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
