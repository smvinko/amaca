"""API: /api/users admin routes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from amaca.db import models

pytestmark = pytest.mark.api


async def test_admin_lists_users(
    admin_client: AsyncClient, user: models.User, admin: models.User
) -> None:
    r = await admin_client.get("/api/users")
    assert r.status_code == 200
    ids = {u["id"] for u in r.json()}
    assert {user.id, admin.id} <= ids


async def test_non_admin_forbidden(client: AsyncClient) -> None:
    r = await client.get("/api/users")
    assert r.status_code == 403


async def test_admin_can_promote(
    admin_client: AsyncClient, user: models.User
) -> None:
    r = await admin_client.patch(f"/api/users/{user.id}", json={"role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


async def test_admin_can_disable(
    admin_client: AsyncClient, user: models.User
) -> None:
    r = await admin_client.patch(f"/api/users/{user.id}", json={"disabled": True})
    assert r.status_code == 200
    assert r.json()["disabled"] is True


async def test_patch_invalid_role_rejected(
    admin_client: AsyncClient, user: models.User
) -> None:
    r = await admin_client.patch(f"/api/users/{user.id}", json={"role": "superuser"})
    assert r.status_code == 422


async def test_patch_missing_user_404(admin_client: AsyncClient) -> None:
    r = await admin_client.patch("/api/users/99999", json={"role": "admin"})
    assert r.status_code == 404
