from __future__ import annotations

import os
import logging
from pathlib import Path, PurePosixPath

import asyncio
import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse

from sentinel.server.api.errors import http_error
from sentinel.server.services import progress
from sentinel.server.services import ws_broker
from sentinel.server.services.repositories import Repository


router = APIRouter(tags=["testing"])
log = logging.getLogger("uvicorn.error")


def _repo(request: Request) -> Repository:
    return request.app.state.repo


def _broker(request: Request) -> ws_broker.ProjectEventBroker:
    broker = getattr(request.app.state, "project_event_broker", None)
    if broker is None:
        broker = ws_broker.ProjectEventBroker()
        request.app.state.project_event_broker = broker
    return broker


def _ws_repo(websocket: WebSocket) -> Repository:
    return websocket.app.state.repo


def _ws_broker(websocket: WebSocket) -> ws_broker.ProjectEventBroker:
    broker = getattr(websocket.app.state, "project_event_broker", None)
    if broker is None:
        broker = ws_broker.ProjectEventBroker()
        websocket.app.state.project_event_broker = broker
    return broker


def _compute_progress_and_rollups(*, repo: Repository, projectId: str) -> tuple[dict | None, dict | None]:
    try:
        latest = repo.get_latest_results_for_project(projectId=projectId)
        prog = progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        log.info("[testing-ws] rollups:project-model-missing projectId=%s", projectId)
        return None, None
    except Exception:
        log.exception("[testing-ws] rollups:compute-failed projectId=%s", projectId)
        return None, None

    tags = repo.get_fail_tags_for_project(projectId=projectId)
    by_target: dict[str, int] = {}
    by_tag = {"NOT_STARTED": 0, "IN_PROGRESS": 0, "DONE": 0}
    total = 0
    for rec in latest.values():
        if rec.outcome != "FAIL":
            continue
        target = rec.target if isinstance(rec.target, dict) else {}
        target_key = str(target.get("targetKey") or "").strip()
        if not target_key:
            continue
        total += 1
        name = str(target.get("targetName") or "").strip() or "(unknown)"
        by_target[name] = by_target.get(name, 0) + 1
        tag = str(tags.get(target_key, "NOT_STARTED") or "NOT_STARTED").strip().upper()
        if tag not in by_tag:
            tag = "NOT_STARTED"
        by_tag[tag] += 1

    rollups = {
        "projectId": projectId,
        "progress": prog,
        "firstTimeFailTargets": repo.count_first_time_fail_targets(projectId=projectId),
        "currentFailures": {"total": total, "byTargetName": by_target, "byTag": by_tag},
    }
    return prog, rollups


def _build_test_result_event(*, repo: Repository, rec) -> dict:
    target_key = str(rec.target.get("targetKey") or "")
    progress_payload, rollups_payload = _compute_progress_and_rollups(repo=repo, projectId=rec.projectId)
    return {
        "type": "test_result",
        "projectId": rec.projectId,
        "recordedAtUtc": rec.recordedAtUtc,
        "targetKey": target_key,
        "outcome": rec.outcome,
        "targetName": rec.target.get("targetName"),
        "kind": rec.target.get("kind") or rec.target.get("targetKind"),
        "refs": rec.target.get("refs"),
        "failNote": rec.failNote,
        "progress": progress_payload,
        "rollups": rollups_payload,
    }


def _build_testing_snapshot(*, repo: Repository, projectId: str) -> dict:
    latest = repo.get_latest_results_for_project(projectId=projectId)
    rows = list(latest.values())
    rows.sort(key=lambda r: r.recordedAtUtc, reverse=True)
    results: list[dict] = []
    for rec in rows:
        target = rec.target if isinstance(rec.target, dict) else {}
        results.append(
            {
                "targetKey": str(target.get("targetKey") or ""),
                "outcome": str(rec.outcome or "").upper(),
                "recordedAtUtc": rec.recordedAtUtc,
                "targetName": target.get("targetName"),
                "kind": target.get("kind") or target.get("targetKind"),
                "refs": target.get("refs"),
                "failNote": rec.failNote,
            }
        )
    return {"type": "testing_snapshot", "projectId": projectId, "results": results}


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
    _broker(request).publish(projectId=rec.projectId, event=_build_test_result_event(repo=_repo(request), rec=rec))

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


@router.websocket("/api/v1/testing/{techToken}/ws")
async def testing_ws(websocket: WebSocket, techToken: str):
    await websocket.accept()
    log.info("[testing-ws] connect techToken=%s", techToken)

    repo = getattr(websocket.app.state, "repo", None)
    if repo is None:
        log.error("[testing-ws] repo_missing techToken=%s", techToken)
        await websocket.close(code=1011)
        return

    try:
        tok = repo.resolve_active_token(techToken=techToken)
    except KeyError:
        try:
            log.info("[testing-ws] revoked techToken=%s", techToken)
            await websocket.send_text(json.dumps({"type": "error", "code": "TECH_LINK_REVOKED"}))
        finally:
            await websocket.close(code=1008)
        return

    project_id = tok.projectId
    broker = _ws_broker(websocket)
    log.info("[testing-ws] broker_id=%s projectId=%s", id(broker), project_id)
    q = broker.subscribe(projectId=project_id)
    try:
        snapshot = _build_testing_snapshot(repo=repo, projectId=project_id)
        log.info("[testing-ws] snapshot-send projectId=%s count=%s", project_id, len(snapshot.get("results") or []))
        await websocket.send_text(json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False))
    except Exception:
        log.exception("[testing-ws] snapshot-send-failed projectId=%s techToken=%s", project_id, techToken)

    async def send_loop():
        while True:
            msg = await ws_broker.wait_for_next(q, timeout_s=15.0)
            if msg is None:
                await websocket.send_text(json.dumps({"type": "keepalive"}))
                continue
            await websocket.send_text(msg)

    async def recv_loop():
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except Exception:
                log.warning("[testing-ws] recv:json-parse-failed techToken=%s raw=%s", techToken, str(raw)[:200])
                continue
            msg_type = str(payload.get("type") or "").strip()
            log.info("[testing-ws] recv type=%s techToken=%s", msg_type, techToken)
            if msg_type not in ("test_result.submit", "test_result"):
                await websocket.send_text(json.dumps({"type": "error", "code": "UNKNOWN_MESSAGE"}))
                continue
            target = payload.get("target") or {}
            outcome = str(payload.get("outcome") or "").strip().upper()
            fail_note = payload.get("failNote")
            if outcome not in ("PASS", "FAIL"):
                await websocket.send_text(json.dumps({"type": "error", "code": "VALIDATION_ERROR", "message": "Outcome must be PASS or FAIL."}))
                continue
            if outcome == "FAIL" and not str(fail_note or "").strip():
                await websocket.send_text(json.dumps({"type": "error", "code": "FAIL_NOTE_REQUIRED", "message": "Fail note is required when outcome is FAIL."}))
                continue
            try:
                rec = repo.append_test_result(
                    techToken=techToken,
                    target=target,
                    outcome=outcome,
                    failNote=(str(fail_note).strip() if fail_note is not None else None),
                )
            except KeyError:
                await websocket.send_text(json.dumps({"type": "error", "code": "TECH_LINK_REVOKED"}))
                await websocket.close(code=1008)
                return
            event = _build_test_result_event(repo=repo, rec=rec)
            log.info(
                "[testing-ws] publish projectId=%s targetKey=%s outcome=%s broker_id=%s",
                rec.projectId,
                str(event.get("targetKey") or ""),
                str(event.get("outcome") or ""),
                id(broker),
            )
            try:
                await websocket.send_text(json.dumps(event, separators=(",", ":"), ensure_ascii=False))
            except Exception:
                log.exception("[testing-ws] direct_send_failed techToken=%s", techToken)
            broker.publish(projectId=rec.projectId, event=event)

    send_task = asyncio.create_task(send_loop())
    try:
        await recv_loop()
    except WebSocketDisconnect:
        log.info("[testing-ws] disconnect techToken=%s", techToken)
    finally:
        send_task.cancel()
        await asyncio.gather(send_task, return_exceptions=True)
        try:
            broker.unsubscribe(projectId=project_id, q=q)
        except Exception:
            log.exception("[testing-ws] unsubscribe-failed techToken=%s projectId=%s", techToken, project_id)


@router.get("/api/v1/testing/{techToken}/target-status")
def target_status(request: Request, techToken: str, targetKey: str) -> dict:
    try:
        return _repo(request).get_target_status(techToken=techToken, targetKey=targetKey)
    except KeyError:
        raise http_error(410, code="TECH_LINK_REVOKED", message="This technician link has been revoked.")
