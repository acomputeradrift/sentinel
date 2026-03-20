from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from sentinel.server.api.errors import http_error
from sentinel.server.services.repositories import Repository


router = APIRouter(tags=["testing"])


def _repo(request: Request) -> Repository:
    return request.app.state.repo


@router.get("/testing/{techToken}", response_class=HTMLResponse)
def testing_html(request: Request, techToken: str) -> HTMLResponse:
    try:
        _repo(request).resolve_active_token(techToken=techToken)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")
    html = "<!doctype html><html><head><meta charset='utf-8'><title>Sentinel Testing</title></head><body><h1>Sentinel Testing</h1><p>MVP server is running.</p></body></html>"
    return HTMLResponse(content=html)


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

