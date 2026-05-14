"""API: /api/auth/tokens + Bearer-token auth on /api/auth/me."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from amaca.auth import generate_token
from amaca.db import models

pytestmark = pytest.mark.api


async def test_create_token(client: AsyncClient) -> None:
    r = await client.post("/api/auth/tokens", json={"name": "laptop"})
    assert r.status_code == 201
    body = r.json()
    assert body["token"].startswith("amk_")
    assert body["info"]["name"] == "laptop"


async def test_list_tokens(client: AsyncClient) -> None:
    await client.post("/api/auth/tokens", json={"name": "a"})
    await client.post("/api/auth/tokens", json={"name": "b"})
    r = await client.get("/api/auth/tokens")
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert {"a", "b"} <= names


async def test_revoke_token(client: AsyncClient) -> None:
    r = await client.post("/api/auth/tokens", json={"name": "throwaway"})
    tid = r.json()["info"]["id"]
    r2 = await client.delete(f"/api/auth/tokens/{tid}")
    assert r2.status_code == 204
    r3 = await client.get("/api/auth/tokens")
    matching = [t for t in r3.json() if t["id"] == tid]
    assert len(matching) == 1
    assert matching[0]["revoked_at"] is not None


async def test_revoke_other_users_token_returns_404(
    client: AsyncClient, db, admin: models.User
) -> None:
    _, prefix, hashed = generate_token()
    row = models.ApiToken(user_id=admin.id, name="admin-tok", prefix=prefix, hash=hashed)
    db.add(row)
    db.commit()
    db.refresh(row)
    r = await client.delete(f"/api/auth/tokens/{row.id}")
    assert r.status_code == 404


async def test_bearer_token_authenticates(
    raw_client: AsyncClient, db, user: models.User
) -> None:
    plaintext, prefix, hashed = generate_token()
    db.add(models.ApiToken(user_id=user.id, name="cli", prefix=prefix, hash=hashed))
    db.commit()
    r = await raw_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {plaintext}"}
    )
    assert r.status_code == 200
    assert r.json()["github_username"] == user.github_username


async def test_revoked_bearer_token_rejected(
    raw_client: AsyncClient, db, user: models.User
) -> None:
    plaintext, prefix, hashed = generate_token()
    db.add(models.ApiToken(
        user_id=user.id, name="cli", prefix=prefix, hash=hashed,
        revoked_at=datetime.now(timezone.utc),
    ))
    db.commit()
    r = await raw_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {plaintext}"}
    )
    assert r.status_code == 401


async def test_unauth_endpoint_returns_401(raw_client: AsyncClient) -> None:
    r = await raw_client.get("/api/auth/me")
    assert r.status_code == 401


async def test_disabled_user_rejected(
    raw_client: AsyncClient, db, user: models.User
) -> None:
    plaintext, prefix, hashed = generate_token()
    db.add(models.ApiToken(user_id=user.id, name="cli", prefix=prefix, hash=hashed))
    user.disabled = True
    db.commit()
    r = await raw_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {plaintext}"}
    )
    assert r.status_code == 401
