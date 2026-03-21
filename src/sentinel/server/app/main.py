from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sentinel.server.api.commissioning import router as commissioning_router
from sentinel.server.api.events import router as events_router
from sentinel.server.api.testing import router as testing_router
from sentinel.server.services.repositories import InMemoryRepository, PostgresRepository, Repository


def create_app(repo: Repository | None = None) -> FastAPI:
    app = FastAPI(title="Sentinel", version="0.1.0")

    if repo is not None:
        app.state.repo = repo
    else:
        database_url = os.environ.get("DATABASE_URL")
        app.state.repo = PostgresRepository(database_url=database_url) if database_url else InMemoryRepository()

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException):  # type: ignore[override]
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail), "details": {}, "traceId": None}})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    ui_root = os.path.join(os.path.dirname(__file__), "..", "..", "ui")
    commissioning_dir = os.path.join(ui_root, "commissioning")
    if os.path.isdir(commissioning_dir):
        app.mount("/commissioning", StaticFiles(directory=commissioning_dir, html=True), name="commissioning-ui")

    app.include_router(commissioning_router)
    app.include_router(events_router)
    app.include_router(testing_router)

    return app


app = create_app()
