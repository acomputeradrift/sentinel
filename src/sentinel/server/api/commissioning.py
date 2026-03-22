from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi import UploadFile
from fastapi.responses import StreamingResponse

from sentinel.server.api.errors import http_error
from sentinel.server.services import pipeline
from sentinel.server.services import progress
from sentinel.server.services import sse
from sentinel.server.services.repositories import Repository


router = APIRouter(prefix="/api/v1/commissioning", tags=["commissioning"])


def _repo(request: Request) -> Repository:
    return request.app.state.repo


def _broker(request: Request) -> sse.ProjectEventBroker:
    broker = getattr(request.app.state, "project_event_broker", None)
    if broker is None:
        broker = sse.ProjectEventBroker()
        request.app.state.project_event_broker = broker
    return broker


@router.get("/clients")
def list_clients(request: Request) -> list[dict]:
    clients = _repo(request).list_clients()
    return [{"clientId": c.clientId, "name": c.name, "createdAtUtc": c.createdAtUtc} for c in clients]


@router.get("/clients/{clientId}/projects")
def list_projects_for_client(request: Request, clientId: str) -> list[dict]:
    try:
        projects = _repo(request).list_projects_for_client(clientId=clientId)
    except KeyError:
        raise http_error(404, code="CLIENT_NOT_FOUND", message="Client not found.")
    return [
        {
            "projectId": p.projectId,
            "clientId": p.clientId,
            "name": p.name,
            "status": p.status,
            "createdAtUtc": p.createdAtUtc,
        }
        for p in projects
    ]


@router.post("/clients")
def create_client(request: Request, payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise http_error(400, code="VALIDATION_ERROR", message="Client name is required.")
    c = _repo(request).create_client(name=name)
    return {"clientId": c.clientId, "name": c.name, "createdAtUtc": c.createdAtUtc}


@router.post("/clients/{clientId}/projects")
def create_project(request: Request, clientId: str, payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise http_error(400, code="VALIDATION_ERROR", message="Project name is required.")
    p = _repo(request).create_project(clientId=clientId, name=name)
    return {
        "projectId": p.projectId,
        "clientId": p.clientId,
        "name": p.name,
        "status": p.status,
        "createdAtUtc": p.createdAtUtc,
        "activeTechLinkIds": [],
    }


@router.post("/projects/{projectId}/tech-links")
def create_tech_link(request: Request, projectId: str, payload: dict) -> dict:
    label = payload.get("label")
    link, token = _repo(request).create_tech_link(projectId=projectId, label=str(label) if label is not None else None)
    return {"techLinkId": link.techLinkId, "techUrl": f"/testing/{token.techToken}"}


@router.post("/projects/{projectId}/tech-links/{techLinkId}/rotate")
def rotate_tech_link(request: Request, projectId: str, techLinkId: str) -> dict:
    token = _repo(request).rotate_tech_link_token(projectId=projectId, techLinkId=techLinkId)
    return {"techLinkId": techLinkId, "techUrl": f"/testing/{token.techToken}"}


@router.get("/projects/{projectId}/tech-links")
def list_active_tech_links(request: Request, projectId: str) -> list[dict]:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    links = _repo(request).list_active_tech_links(projectId=projectId)
    return [{"techLinkId": l.techLinkId, "label": l.label, "createdAtUtc": l.createdAtUtc} for l in links]


@router.post("/projects/{projectId}/tech-links/{techLinkId}/revoke")
def revoke_tech_link(request: Request, projectId: str, techLinkId: str) -> dict:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    try:
        _repo(request).revoke_tech_link(projectId=projectId, techLinkId=techLinkId)
    except KeyError:
        raise http_error(404, code="TECH_LINK_NOT_FOUND", message="Tech link not found.")
    return {"projectId": projectId, "techLinkId": techLinkId, "revoked": True}


@router.post("/projects/{projectId}/uploads")
async def upload_apex(projectId: str, apex: UploadFile) -> dict:
    if not apex.filename:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex filename is required.")
    content = await apex.read()
    if not content:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex file is empty.")
    upload_id = str(uuid4())
    path = pipeline.save_upload(projectId=projectId, uploadId=upload_id, filename=apex.filename, content=content)
    return {"uploadId": upload_id, "projectId": projectId, "originalFilename": apex.filename, "storagePath": str(path)}


@router.post("/projects/{projectId}/upload-and-regenerate")
async def upload_and_regenerate(request: Request, projectId: str, apex: UploadFile) -> dict:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    if not apex.filename:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex filename is required.")
    content = await apex.read()
    if not content:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex file is empty.")

    upload_id = str(uuid4())
    path = pipeline.save_upload(projectId=projectId, uploadId=upload_id, filename=apex.filename, content=content)

    try:
        generation = pipeline.regenerate_project(projectId=projectId, apex_path=path)
    except Exception as e:
        raise http_error(500, code="REGENERATE_FAILED", message=str(e))

    try:
        _broker(request).publish(
            projectId=projectId,
            event={
                "type": "generation",
                "status": "READY",
                "uploadId": upload_id,
                "originalFilename": apex.filename,
            },
        )
    except Exception:
        pass

    return {
        "projectId": projectId,
        "uploadId": upload_id,
        "originalFilename": apex.filename,
        "storagePath": str(path),
        "generation": {"status": "READY", **(generation or {})},
    }


@router.post("/projects/{projectId}/regenerate")
def regenerate(projectId: str, payload: dict) -> dict:
    upload_id = payload.get("uploadId")
    if upload_id is None:
        raise http_error(400, code="VALIDATION_ERROR", message="uploadId is required for MVP regenerate.")
    upload_dir = pipeline._project_upload_dir(projectId=projectId)
    candidates = list(upload_dir.glob(f"{upload_id}__*.apex"))
    if not candidates:
        raise http_error(404, code="UPLOAD_NOT_FOUND", message="Upload not found.")
    apex_path = candidates[0]
    pipeline.regenerate_project(projectId=projectId, apex_path=apex_path)
    return {"projectId": projectId, "status": "READY"}


@router.get("/projects/{projectId}/fails")
def project_fails(request: Request, projectId: str) -> list[dict]:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    latest = _repo(request).get_latest_results_for_project(projectId=projectId)
    tags = _repo(request).get_fail_tags_for_project(projectId=projectId)
    fails = [rec for rec in latest.values() if rec.outcome == "FAIL"]
    fails.sort(key=lambda r: r.recordedAtUtc, reverse=True)
    return [
        {
            "targetKey": str(rec.target.get("targetKey") or ""),
            "currentOutcome": "FAIL",
            "lastTestedAtUtc": rec.recordedAtUtc,
            "lastFailNote": rec.failNote,
            "recordedBy": rec.recordedBy,
            "tag": tags.get(str(rec.target.get("targetKey") or ""), "NOT_STARTED"),
            "deviceName": (rec.target.get("refs") or {}).get("deviceName") if isinstance(rec.target.get("refs"), dict) else None,
            "pageName": (rec.target.get("refs") or {}).get("pageName") if isinstance(rec.target.get("refs"), dict) else None,
            "buttonName": (rec.target.get("refs") or {}).get("buttonName") if isinstance(rec.target.get("refs"), dict) else None,
            "scope": (rec.target.get("refs") or {}).get("scope") if isinstance(rec.target.get("refs"), dict) else None,
            "targetName": rec.target.get("targetName"),
            "resolvedData": (rec.target.get("refs") or {}).get("resolvedData") if isinstance(rec.target.get("refs"), dict) else None,
        }
        for rec in fails
        if str(rec.target.get("targetKey") or "")
    ]


@router.put("/projects/{projectId}/fail-tags")
def put_fail_tag(request: Request, projectId: str, payload: dict) -> dict:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")

    target_key = str(payload.get("targetKey") or "").strip()
    tag = str(payload.get("tag") or "").strip().upper()
    if not target_key:
        raise http_error(400, code="VALIDATION_ERROR", message="targetKey is required.")
    if tag not in ("NOT_STARTED", "IN_PROGRESS", "DONE"):
        raise http_error(400, code="VALIDATION_ERROR", message="tag must be NOT_STARTED, IN_PROGRESS, or DONE.")

    try:
        _repo(request).set_fail_tag(projectId=projectId, targetKey=target_key, tag=tag)
    except KeyError:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")

    try:
        _broker(request).publish(
            projectId=projectId,
            event={
                "type": "fail_tag_updated",
                "projectId": projectId,
                "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
                "targetKey": target_key,
                "tag": tag,
            },
        )
    except Exception:
        pass

    return {"projectId": projectId, "targetKey": target_key, "tag": tag}


@router.get("/projects/{projectId}/progress")
def project_progress(request: Request, projectId: str) -> dict:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    latest = _repo(request).get_latest_results_for_project(projectId=projectId)
    try:
        return progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        raise http_error(503, code="GENERATION_NOT_READY", message="Project model is not ready yet.")


@router.get("/projects/{projectId}/rollups")
def project_rollups(request: Request, projectId: str) -> dict:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")

    latest = _repo(request).get_latest_results_for_project(projectId=projectId)
    try:
        prog = progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        raise http_error(503, code="GENERATION_NOT_READY", message="Project model is not ready yet.")

    tags = _repo(request).get_fail_tags_for_project(projectId=projectId)
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

    return {
        "projectId": projectId,
        "progress": prog,
        "firstTimeFailTargets": _repo(request).count_first_time_fail_targets(projectId=projectId),
        "currentFailures": {"total": total, "byTargetName": by_target, "byTag": by_tag},
    }


@router.get("/projects/{projectId}/events")
async def project_events(request: Request, projectId: str, once: bool = False):
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")

    broker = _broker(request)
    q = broker.subscribe(projectId=projectId)

    async def gen():
        try:
            yield b": connected\nretry: 3000\n\n"
            while True:
                msg = await sse.wait_for_next(q, timeout_s=15.0)
                if msg is None:
                    yield b": keepalive\n\n"
                    continue
                event_name = "message"
                try:
                    parsed = json.loads(msg)
                    if isinstance(parsed, dict):
                        t = str(parsed.get("type") or "").strip()
                        if t:
                            event_name = t
                except Exception:
                    pass
                yield f"event: {event_name}\ndata: {msg}\n\n".encode("utf-8")
                if once:
                    return
        finally:
            broker.unsubscribe(projectId=projectId, q=q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            "x-accel-buffering": "no",
        },
    )


@router.websocket("/projects/{projectId}/ws")
async def project_ws(websocket: WebSocket, projectId: str):
    await websocket.accept()

    repo = getattr(websocket.app.state, "repo", None)
    if repo is None or repo.get_project(projectId=projectId) is None:
        try:
            await websocket.send_text(json.dumps({"type": "error", "code": "PROJECT_NOT_FOUND", "projectId": projectId}))
        finally:
            await websocket.close(code=1008)
        return

    broker = getattr(websocket.app.state, "project_event_broker", None)
    if broker is None:
        broker = sse.ProjectEventBroker()
        websocket.app.state.project_event_broker = broker

    q = broker.subscribe(projectId=projectId)
    try:
        while True:
            msg = await sse.wait_for_next(q, timeout_s=15.0)
            if msg is None:
                await websocket.send_text(json.dumps({"type": "keepalive"}))
                continue
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        return
    except Exception:
        return
    finally:
        try:
            broker.unsubscribe(projectId=projectId, q=q)
        except Exception:
            pass


@router.websocket("/projects/{projectId}/ws")
async def project_ws(websocket: WebSocket, projectId: str) -> None:
    await websocket.accept()

    repo: Repository = websocket.app.state.repo
    proj = repo.get_project(projectId=projectId)
    if proj is None:
        await websocket.send_text('{"error":{"code":"PROJECT_NOT_FOUND","message":"Project not found.","details":{},"traceId":null}}')
        await websocket.close(code=1008)
        return

    broker = getattr(websocket.app.state, "project_event_broker", None)
    if broker is None:
        broker = sse.ProjectEventBroker()
        websocket.app.state.project_event_broker = broker

    q = broker.subscribe(projectId=projectId)
    try:
        while True:
            msg = await sse.wait_for_next(q, timeout_s=15.0)
            if msg is None:
                await websocket.send_text('{"type":"keepalive"}')
                continue
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        return
    finally:
        try:
            broker.unsubscribe(projectId=projectId, q=q)
        except Exception:
            pass
