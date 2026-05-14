"""Unit tests for the API token helpers."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from amaca.auth import generate_token, lookup_token, verify_token
from amaca.db import models

pytestmark = pytest.mark.unit


def test_generate_returns_distinct_tokens() -> None:
    a = generate_token()
    b = generate_token()
    assert a[0] != b[0]      # plaintext differs
    assert a[1] != b[1]      # prefix differs (random suffix)
    assert a[2] != b[2]      # bcrypt hash differs (different salt)


def test_token_format() -> None:
    plaintext, prefix, hashed = generate_token()
    assert plaintext.startswith("amk_")
    assert prefix == plaintext[:12]
    assert hashed.startswith("$2b$")


def test_verify_token_roundtrip() -> None:
    plaintext, _, hashed = generate_token()
    assert verify_token(plaintext, hashed) is True
    assert verify_token(plaintext + "x", hashed) is False
    assert verify_token("", hashed) is False


def test_lookup_token_finds_match(db, user) -> None:
    plaintext, prefix, hashed = generate_token()
    db.add(models.ApiToken(user_id=user.id, name="x", prefix=prefix, hash=hashed))
    db.commit()
    found = lookup_token(db, plaintext)
    assert found is not None
    assert found.user_id == user.id


def test_lookup_token_rejects_revoked(db, user) -> None:
    plaintext, prefix, hashed = generate_token()
    db.add(models.ApiToken(
        user_id=user.id, name="x", prefix=prefix, hash=hashed,
        revoked_at=datetime.now(timezone.utc),
    ))
    db.commit()
    assert lookup_token(db, plaintext) is None


def test_lookup_token_rejects_malformed(db) -> None:
    assert lookup_token(db, "not-a-token") is None
    assert lookup_token(db, "amk_short") is None
    assert lookup_token(db, "") is None
