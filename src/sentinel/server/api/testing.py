from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse

from sentinel.server.api.errors import http_error
from sentinel.server.services import sse
from sentinel.server.services.repositories import Repository


router = APIRouter(tags=["testing"])


def _repo(request: Request) -> Repository:
    return request.app.state.repo


def _broker(request: Request) -> sse.ProjectEventBroker:
    broker = getattr(request.app.state, "project_event_broker", None)
    if broker is None:
        broker = sse.ProjectEventBroker()
        request.app.state.project_event_broker = broker
    return broker


def _generated_root() -> Path:
    return Path(os.environ.get("SENTINEL_GENERATED_ROOT") or "generated").resolve()


def _project_dir(*, projectId: str) -> Path:
    return (_generated_root() / projectId).resolve()


def _find_project_home(project_dir: Path) -> Path | None:
    if not project_dir.exists() or not project_dir.is_dir():
        return None
    candidates = list(project_dir.glob("*__project-home.html"))
    if candidates:
        return max(candidates, key=lambda p: (p.stat().st_mtime, p.name))
    fallback = project_dir / "project-home.html"
    return fallback if fallback.exists() else None


def _inject_base_href(html: str, *, base_href: str) -> str:
    if "<base " in html or "<base>" in html:
        return html
    needle = "<head>"
    if needle in html:
        return html.replace(needle, needle + f'<base href="{base_href}">', 1)
    needle2 = "<head"
    idx = html.find(needle2)
    if idx >= 0:
        close = html.find(">", idx)
        if close >= 0:
            return html[: close + 1] + f'<base href="{base_href}">' + html[close + 1 :]
    return f'<base href="{base_href}">' + html


@router.get("/testing/{techToken}", response_class=HTMLResponse)
def testing_html(request: Request, techToken: str) -> HTMLResponse:
    try:
        tok = _repo(request).resolve_active_token(techToken=techToken)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")

    project_dir = _project_dir(projectId=tok.projectId)
    home = _find_project_home(project_dir)
    if home is None:
        html = "<!doctype html><html><head><meta charset='utf-8'><title>Sentinel Testing</title></head><body><h1>Sentinel Testing</h1><p>Testing UI has not been generated yet.</p></body></html>"
        with_base = _inject_base_href(html, base_href=f"/testing/{techToken}/files/")
        return HTMLResponse(content=with_base)

    raw = home.read_text(encoding="utf-8", errors="replace")
    with_base = _inject_base_href(raw, base_href=f"/testing/{techToken}/files/")
    return HTMLResponse(content=with_base)


@router.get("/testing/{techToken}/files/{path:path}")
def testing_file(request: Request, techToken: str, path: str) -> FileResponse:
    try:
        tok = _repo(request).resolve_active_token(techToken=techToken)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")

    rel = PurePosixPath("/" + path).relative_to("/")
    if any(part in ("..", "") for part in rel.parts):
        raise http_error(404, code="NOT_FOUND", message="File not found.")

    project_dir = _project_dir(projectId=tok.projectId)
    target = (project_dir / Path(*rel.parts)).resolve()
    if project_dir not in target.parents and target != project_dir:
        raise http_error(404, code="NOT_FOUND", message="File not found.")
    if not target.exists() or not target.is_file():
        raise http_error(404, code="NOT_FOUND", message="File not found.")

    return FileResponse(path=str(target))


@router.post("/api/v1/testing/{techToken}/results")
def post_result(request: Request, techToken: str, payload: dict) -> dict:
    target = payload.get("target") or {}
    outcome = str(payload.get("outcome") or "").strip().upper()
    fail_note = payload.get("failNote")

    if outcome not in ("PASS", "FAIL"):
        raise http_error(400, code="VALIDATION_ERROR", message="Outcome must be PASS or FAIL.")
    if outcome == "FAIL" and not str(fail_note or "").strip():
        raise http_error(400, code="FAIL_NOTE_REQUIRED", message="Fail note is required when outcome is FAIL.")

    try:
        rec = _repo(request).append_test_result(techToken=techToken, target=target, outcome=outcome, failNote=(str(fail_note).strip() if fail_note is not None else None))
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")

    target_key = str(rec.target.get("targetKey") or "")
    _broker(request).publish(
        projectId=rec.projectId,
        event={
            "type": "test_result",
            "projectId": rec.projectId,
            "recordedAtUtc": rec.recordedAtUtc,
            "targetKey": target_key,
            "outcome": rec.outcome,
            "targetName": rec.target.get("targetName"),
            "kind": rec.target.get("kind") or rec.target.get("targetKind"),
            "refs": rec.target.get("refs"),
        },
    )

    return {
        "testResultId": rec.testResultId,
        "projectId": rec.projectId,
        "generationRunId": None,
        "recordedAtUtc": rec.recordedAtUtc,
        "recordedBy": rec.recordedBy,
        "target": rec.target,
        "outcome": rec.outcome,
        "failNote": rec.failNote,
    }


@router.get("/api/v1/testing/{techToken}/target-status")
def target_status(request: Request, techToken: str, targetKey: str) -> dict:
    try:
        return _repo(request).get_target_status(techToken=techToken, targetKey=targetKey)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")
