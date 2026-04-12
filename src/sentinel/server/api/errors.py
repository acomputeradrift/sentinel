from __future__ import annotations

from fastapi import HTTPException

from sentinel.server import request_context


def http_error(status_code: int, *, code: str, message: str, details: dict | None = None) -> HTTPException:
    tid = request_context.current_trace_id()
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}, "traceId": tid}},
    )

