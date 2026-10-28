from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
    path: str
    details: list[dict[str, Any]] | None = None
