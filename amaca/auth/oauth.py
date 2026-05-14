"""Thin GitHub OAuth web-app flow.

We use the standard *authorization code* grant. Calling
``authorize_url(state)`` returns a URL the browser should be sent to;
GitHub redirects back to our callback with ``?code=...&state=...``,
and we call ``exchange_code(code)`` and ``fetch_github_user(token)`` to
identify the user.

This module purposefully does **no** session management itself — the
caller wires the callback into the API and sets a session cookie.
That separation makes the helpers easy to unit-test and stub.
"""
from __future__ import annotations

import os
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


def random_state() -> str:
    """One-shot state string to mitigate CSRF on the callback."""
    return secrets.token_urlsafe(16)


def authorize_url(state: str, *, scope: str = "read:user user:email") -> str:
    client_id = os.environ["AMACA_GITHUB_CLIENT_ID"]
    redirect_uri = os.environ.get(
        "AMACA_OAUTH_REDIRECT_URI",
        "http://localhost:8000/api/auth/callback",
    )
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> str:
    client_id = os.environ["AMACA_GITHUB_CLIENT_ID"]
    client_secret = os.environ["AMACA_GITHUB_CLIENT_SECRET"]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        payload = r.json()
    if "access_token" not in payload:
        raise ValueError(f"GitHub OAuth code exchange failed: {payload}")
    return payload["access_token"]


async def fetch_github_user(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        r.raise_for_status()
        return r.json()
