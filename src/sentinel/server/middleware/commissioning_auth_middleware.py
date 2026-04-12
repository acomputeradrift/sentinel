from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

def _expected_commissioning_key() -> str:
    return str(os.environ.get("SENTINEL_COMMISSIONING_API_KEY") or "").strip()


def _provided_commissioning_key(request: Request) -> str:
    q = (
        request.query_params.get("commissioningKey")
        or request.query_params.get("commissioning_key")
        or ""
    )
    if str(q).strip():
        return str(q).strip()
    return (
        request.headers.get("x-sentinel-commissioning-key")
        or request.headers.get("X-Sentinel-Commissioning-Key")
        or str(request.headers.get("authorization") or "").replace("Bearer ", "").strip()
    )


class CommissioningAuthMiddleware(BaseHTTPMiddleware):
    """
    When SENTINEL_COMMISSIONING_API_KEY is set, require it for all /api/v1/commissioning traffic
    (including WebSocket upgrade requests).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not path.startswith("/api/v1/commissioning"):
            return await call_next(request)
        expected = _expected_commissioning_key()
        if not expected:
            return await call_next(request)
        if _provided_commissioning_key(request) != expected:
            tid = getattr(request.state, "trace_id", None)
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "COMMISSIONING_AUTH_REQUIRED",
                        "message": "Invalid or missing commissioning API key.",
                        "details": {},
                        "traceId": tid,
                    }
                },
            )
        return await call_next(request)
