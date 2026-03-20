from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse


router = APIRouter(prefix="/api/v1/commissioning", tags=["events"])


def _sse_keepalive() -> Iterator[bytes]:
    yield b": ok\n\n"


@router.get("/projects/{projectId}/events")
def project_events(projectId: str) -> StreamingResponse:  # noqa: ARG001
    return StreamingResponse(_sse_keepalive(), media_type="text/event-stream")

