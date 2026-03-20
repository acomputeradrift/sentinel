from __future__ import annotations

from fastapi import FastAPI
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from sentinel.server.api.commissioning import router as commissioning_router
from sentinel.server.api.events import router as events_router
from sentinel.server.api.testing import router as testing_router
from sentinel.server.services.repositories import InMemoryRepository


def create_app() -> FastAPI:
    app = FastAPI(title="Sentinel", version="0.1.0")
    app.state.repo = InMemoryRepository()

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):  # type: ignore[override]
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}, "traceId": None}})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(commissioning_router)
    app.include_router(events_router)
    app.include_router(testing_router)

    return app


app = create_app()
