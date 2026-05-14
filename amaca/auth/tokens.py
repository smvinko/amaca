"""API token generation, verification, and DB lookup.

A token looks like ``amk_<43 url-safe base64 chars>`` (≈ 256 bits of
entropy from 32 random bytes). We store **only** the bcrypt hash plus
a short indexed prefix; the plaintext is shown to the user exactly
once at creation time and never recorded again.

Lookup goes: prefix match (indexed) → bcrypt verify against each match.
With 8 random base64 chars after ``amk_`` the prefix space is ~2.8e14
so collisions inside a single deployment are negligible; the bcrypt
check is the security boundary regardless.
"""
from __future__ import annotations

import secrets

import bcrypt
from sqlalchemy.orm import Session

from amaca.db import models

TOKEN_PREFIX = "amk_"
PREFIX_LEN = 12               # "amk_" + 8 random chars
SECRET_BYTES = 32             # raw entropy before url-safe encoding


def generate_token() -> tuple[str, str, str]:
    """Return ``(plaintext, prefix, bcrypt_hash)``. The plaintext is the
    only form the user will ever see — store the hash, return the prefix
    for indexed lookup."""
    body = secrets.token_urlsafe(SECRET_BYTES)
    token = TOKEN_PREFIX + body
    prefix = token[:PREFIX_LEN]
    hashed = bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()
    return token, prefix, hashed


def verify_token(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except (TypeError, ValueError):
        return False


def lookup_token(db: Session, plaintext: str) -> models.ApiToken | None:
    """Find and verify an unrevoked token row matching ``plaintext``."""
    if not plaintext.startswith(TOKEN_PREFIX) or len(plaintext) < PREFIX_LEN + 4:
        return None
    prefix = plaintext[:PREFIX_LEN]
    candidates = (
        db.query(models.ApiToken)
        .filter(
            models.ApiToken.prefix == prefix,
            models.ApiToken.revoked_at.is_(None),
        )
        .all()
    )
    for row in candidates:
        if verify_token(plaintext, row.hash):
            return row
    return None
