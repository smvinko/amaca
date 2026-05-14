"""Auth routes: GitHub OAuth flow + session + API tokens."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from amaca.auth import (
    authorize_url,
    exchange_code,
    fetch_github_user,
    generate_token,
    is_allowed,
    random_state,
    upsert_user_from_github,
)
from amaca.db import models

from .deps import DB, CurrentUser
from .schemas import TokenCreate, TokenCreated, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    state = random_state()
    request.session["oauth_state"] = state
    return RedirectResponse(authorize_url(state))


@router.get("/callback")
async def callback(
    code: str, state: str, request: Request, db: DB,
) -> RedirectResponse:
    expected = request.session.pop("oauth_state", None)
    if not expected or expected != state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "oauth state mismatch")
    access_token = await exchange_code(code)
    gh = await fetch_github_user(access_token)
    username = gh.get("login")
    if not username or not is_allowed(username):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not authorised")
    user = upsert_user_from_github(
        db,
        github_id=int(gh["id"]),
        github_username=username,
        email=gh.get("email"),
    )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> models.User:
    return user


@router.post(
    "/tokens",
    response_model=TokenCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_token(payload: TokenCreate, user: CurrentUser, db: DB) -> TokenCreated:
    plaintext, prefix, hashed = generate_token()
    row = models.ApiToken(
        user_id=user.id, name=payload.name, prefix=prefix, hash=hashed,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return TokenCreated(
        token=plaintext,
        info=TokenOut.model_validate(row),
    )


@router.get("/tokens", response_model=list[TokenOut])
async def list_tokens(user: CurrentUser, db: DB) -> list[models.ApiToken]:
    return (
        db.query(models.ApiToken)
        .filter_by(user_id=user.id)
        .order_by(models.ApiToken.id.desc())
        .all()
    )


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(token_id: int, user: CurrentUser, db: DB) -> Response:
    row = db.get(models.ApiToken, token_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "token not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
