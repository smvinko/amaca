"""API: /api/codes routes."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.api


async def test_list_codes(client: AsyncClient) -> None:
    r = await client.get("/api/codes")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "demo" in names


async def test_get_code(client: AsyncClient) -> None:
    r = await client.get("/api/codes/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "demo"
    assert "properties" in body["input_schema"]
    assert "n_points" in body["input_schema"]["properties"]


async def test_get_code_404(client: AsyncClient) -> None:
    r = await client.get("/api/codes/nope")
    assert r.status_code == 404


async def test_codes_require_auth(raw_client: AsyncClient) -> None:
    r = await raw_client.get("/api/codes")
    assert r.status_code == 401
