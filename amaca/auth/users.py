"""Allowlist + GitHub→User upsert.

Two env vars gate access:

- ``AMACA_ALLOWED_GITHUB_USERS``  — comma-separated usernames who can log in.
- ``AMACA_ADMIN_GITHUB_USERS``    — subset who get the ``admin`` role on first login.

Empty allowlist means **no one can log in** (fail-closed).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from amaca.db import models


def _csv(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [tok.strip().lower() for tok in raw.split(",") if tok.strip()]


def allowed_users() -> list[str]:
    return _csv("AMACA_ALLOWED_GITHUB_USERS")


def admin_users() -> list[str]:
    return _csv("AMACA_ADMIN_GITHUB_USERS")


def is_allowed(github_username: str) -> bool:
    allowed = allowed_users()
    if not allowed:
        return False
    return github_username.lower() in allowed


def is_admin_bootstrap(github_username: str) -> bool:
    return github_username.lower() in admin_users()


def upsert_user_from_github(
    db: Session,
    *,
    github_id: int,
    github_username: str,
    email: str | None,
) -> models.User:
    """Create or refresh the User row for a verified GitHub identity.

    Caller must have already checked ``is_allowed(github_username)``.

    Updates the username (it can change on GitHub) and email on every
    login, bumps ``last_login_at``, and promotes the user to admin if
    they appear in ``AMACA_ADMIN_GITHUB_USERS``.
    """
    now = datetime.now(timezone.utc)
    user = (
        db.query(models.User).filter_by(github_id=github_id).one_or_none()
    )
    if user is None:
        user = models.User(
            github_id=github_id,
            github_username=github_username,
            email=email,
            role="admin" if is_admin_bootstrap(github_username) else "user",
            last_login_at=now,
        )
        db.add(user)
    else:
        user.github_username = github_username
        user.email = email
        user.last_login_at = now
        if is_admin_bootstrap(github_username) and user.role != "admin":
            user.role = "admin"
    db.commit()
    db.refresh(user)
    return user
