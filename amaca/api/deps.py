"""FastAPI dependencies: DB session, runner, current user."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from amaca.auth import lookup_token
from amaca.db import models
from amaca.workers import JobRunner


def get_db(request: Request) -> Iterator[Session]:
    SessionLocal = request.app.state.SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_runner(request: Request) -> JobRunner:
    return request.app.state.runner


DB = Annotated[Session, Depends(get_db)]
Runner = Annotated[JobRunner, Depends(get_runner)]


def current_user(
    request: Request,
    db: DB,
    authorization: Annotated[str | None, Header()] = None,
) -> models.User:
    """Resolve the caller via Bearer token first, then session cookie."""
    user_id: int | None = None

    if authorization and authorization.lower().startswith("bearer "):
        plaintext = authorization.split(None, 1)[1].strip()
        token = lookup_token(db, plaintext)
        if token is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
        token.last_used_at = datetime.now(timezone.utc)
        db.commit()
        user_id = token.user_id
    else:
        session_user = request.session.get("user_id") if hasattr(request, "session") else None
        if session_user is not None:
            user_id = int(session_user)

    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")

    user = db.get(models.User, user_id)
    if user is None or user.disabled:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or disabled")
    return user


CurrentUser = Annotated[models.User, Depends(current_user)]


def require_admin(user: CurrentUser) -> models.User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin required")
    return user


AdminUser = Annotated[models.User, Depends(require_admin)]
