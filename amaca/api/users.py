"""Admin-only user management."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from amaca.db import models

from .deps import DB, AdminUser
from .schemas import UserOut, UserPatch

router = APIRouter(prefix="/api/users", tags=["admin"])


@router.get("", response_model=list[UserOut])
async def list_users(_: AdminUser, db: DB) -> list[models.User]:
    return db.query(models.User).order_by(models.User.id).all()


@router.patch("/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: int, payload: UserPatch, _: AdminUser, db: DB,
) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if payload.role is not None:
        user.role = payload.role
    if payload.disabled is not None:
        user.disabled = payload.disabled
    db.commit()
    db.refresh(user)
    return user
