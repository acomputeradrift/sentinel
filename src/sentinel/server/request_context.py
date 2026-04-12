from __future__ import annotations

import contextvars
import uuid

request_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_trace_id", default=None)


def new_trace_id() -> str:
    return str(uuid.uuid4())


def current_trace_id() -> str | None:
    return request_trace_id.get()
