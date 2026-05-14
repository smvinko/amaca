"""Allowlist + user-upsert unit tests."""
from __future__ import annotations

import pytest

from amaca.auth import is_admin_bootstrap, is_allowed, upsert_user_from_github

pytestmark = pytest.mark.unit


def test_is_allowed_false_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("AMACA_ALLOWED_GITHUB_USERS", raising=False)
    assert is_allowed("anyone") is False


def test_is_allowed_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("AMACA_ALLOWED_GITHUB_USERS", "Alice, BOB ,  charlie")
    assert is_allowed("alice")
    assert is_allowed("BOB")
    assert is_allowed("alICE")
    assert is_allowed("Charlie")
    assert not is_allowed("eve")


def test_is_admin_bootstrap_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("AMACA_ADMIN_GITHUB_USERS", "alice")
    assert is_admin_bootstrap("Alice")
    assert not is_admin_bootstrap("bob")


def test_upsert_creates_user_with_default_role(db, monkeypatch) -> None:
    monkeypatch.setenv("AMACA_ADMIN_GITHUB_USERS", "")
    u = upsert_user_from_github(
        db, github_id=99, github_username="newbie", email="n@b.com"
    )
    assert u.id is not None
    assert u.role == "user"
    assert u.last_login_at is not None
    assert u.email == "n@b.com"


def test_upsert_promotes_to_admin_via_env(db, monkeypatch) -> None:
    monkeypatch.setenv("AMACA_ADMIN_GITHUB_USERS", "rootuser")
    u = upsert_user_from_github(
        db, github_id=1, github_username="rootuser", email=None
    )
    assert u.role == "admin"


def test_upsert_updates_existing_user_username_and_email(db, monkeypatch) -> None:
    monkeypatch.setenv("AMACA_ADMIN_GITHUB_USERS", "")
    u0 = upsert_user_from_github(
        db, github_id=99, github_username="alice", email="a@b.com"
    )
    monkeypatch.setenv("AMACA_ADMIN_GITHUB_USERS", "alice-renamed")
    u1 = upsert_user_from_github(
        db, github_id=99, github_username="alice-renamed", email="new@b.com"
    )
    assert u0.id == u1.id
    assert u1.github_username == "alice-renamed"
    assert u1.email == "new@b.com"
    assert u1.role == "admin"  # promoted on re-login
