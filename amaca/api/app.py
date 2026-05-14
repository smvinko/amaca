"""FastAPI app factory.

Bound up here so tests can instantiate fresh apps with overridden
dependencies. Production entry point is ``uvicorn amaca.api.app:app``,
where ``app`` is the module-level instance below.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from amaca.db import Base, make_engine, make_sessionmaker
from amaca.workers import JobRunner

# Register bundled adapters (side-effectful import).
import amaca.codes.demo  # noqa: F401

from . import auth, codes, jobs, users


def create_app(
    *,
    database_url: str | None = None,
    data_dir: str | Path | None = None,
    session_secret: str | None = None,
) -> FastAPI:
    database_url = database_url or os.environ.get("AMACA_DATABASE_URL")
    data_dir = Path(data_dir or os.environ.get("AMACA_DATA_DIR", "./data"))
    session_secret = session_secret or os.environ.get(
        "AMACA_SESSION_SECRET",
        "dev-only-insecure-secret-please-set-AMACA_SESSION_SECRET",
    )

    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = make_sessionmaker(engine)
    runner = JobRunner(SessionLocal, data_dir / "jobs")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine
        app.state.SessionLocal = SessionLocal
        app.state.runner = runner
        yield
        await runner.drain()
        engine.dispose()

    app = FastAPI(
        title="amaca",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="amaca_session",
        max_age=30 * 24 * 3600,
        same_site="lax",
        https_only=False,
    )
    app.include_router(auth.router)
    app.include_router(codes.router)
    app.include_router(jobs.router)
    app.include_router(users.router)
    return app


# Module-level instance for `uvicorn amaca.api.app:app` in production.
app = create_app()
