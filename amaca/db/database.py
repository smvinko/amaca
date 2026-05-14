"""SQLAlchemy engine + session factory.

v1 targets SQLite (single file, WAL mode for safe concurrent reads).
The same code works against Postgres by swapping the URL — no schema
changes required because we don't lean on SQLite-only features.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def default_database_url() -> str:
    """Read ``AMACA_DATABASE_URL`` or fall back to a local SQLite file."""
    url = os.environ.get("AMACA_DATABASE_URL")
    if url:
        return url
    data_dir = Path(os.environ.get("AMACA_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir.resolve()}/amaca.db"


def make_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    url = url or default_database_url()
    is_sqlite = url.startswith("sqlite")
    kwargs: dict = {"future": True, "echo": echo}
    if is_sqlite:
        # Single connection should be safe across threads (FastAPI/asyncio).
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(SessionLocal: sessionmaker[Session]) -> Iterator[Session]:
    """Convenience: commit on success, rollback on error, always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
