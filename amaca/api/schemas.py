"""Pydantic request/response shapes for the API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    github_username: str
    email: str | None = None
    role: str
    disabled: bool
    created_at: datetime
    last_login_at: datetime | None = None


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class TokenCreated(BaseModel):
    """Returned exactly once at creation; the plaintext is never recoverable."""
    token: str
    info: TokenOut


class CodeOut(BaseModel):
    name: str
    title: str
    version: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class JobSubmit(BaseModel):
    code: str
    inputs: dict[str, Any]


class JobOut(BaseModel):
    id: int
    owner_id: int
    code_name: str
    code_version: str
    status: str
    inputs: dict[str, Any]
    outputs: dict[str, Any] | None = None
    error_text: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobLogLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ts: datetime
    line: str


class JobListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code_name: str
    status: str
    created_at: datetime
    finished_at: datetime | None = None


class UserPatch(BaseModel):
    role: str | None = Field(default=None, pattern="^(user|admin)$")
    disabled: bool | None = None
