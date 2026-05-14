"""Codes routes: list + detail (read-only)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from amaca.core import Code, all_codes, get

from .deps import CurrentUser
from .schemas import CodeOut

router = APIRouter(prefix="/api/codes", tags=["codes"])


def _to_out(cls: type[Code]) -> CodeOut:
    return CodeOut(
        name=cls.name,
        title=cls.title,
        version=cls.version,
        input_schema=cls.InputSchema.model_json_schema(),
        output_schema=cls.OutputSchema.model_json_schema(),
    )


@router.get("", response_model=list[CodeOut])
async def list_codes(_: CurrentUser) -> list[CodeOut]:
    return [_to_out(cls) for cls in all_codes()]


@router.get("/{name}", response_model=CodeOut)
async def get_code(name: str, _: CurrentUser) -> CodeOut:
    try:
        cls = get(name)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return _to_out(cls)
