from __future__ import annotations

from fastapi import HTTPException


def http_error(status_code: int, *, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}, "traceId": None}},
    )

