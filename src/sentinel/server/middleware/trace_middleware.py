from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from sentinel.server import request_context


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Attach a per-request trace id for logs and JSON error bodies."""

    async def dispatch(self, request: Request, call_next) -> Response:
        tid = request_context.new_trace_id()
        request.state.trace_id = tid
        token = request_context.request_trace_id.set(tid)
        try:
            response = await call_next(request)
        finally:
            request_context.request_trace_id.reset(token)
        response.headers["X-Request-Id"] = tid
        return response
