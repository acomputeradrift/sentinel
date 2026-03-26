from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi import UploadFile

from sentinel.server.api.errors import http_error
from sentinel.server.services import pipeline
from sentinel.server.services import progress
from sentinel.server.services import ws_broker
from sentinel.server.services.repositories import Repository


router = APIRouter(prefix="/api/v1/commissioning", tags=["commissioning"])
log = logging.getLogger("uvicorn.error")


def _repo(request: Request) -> Repository:
    return request.app.state.repo


def _broker(request: Request) -> ws_broker.ProjectEventBroker:
    broker = getattr(request.app.state, "project_event_broker", None)
    if broker is None:
        broker = ws_broker.ProjectEventBroker()
        request.app.state.project_event_broker = broker
    return broker


def _safe_progress(*, repo: Repository, projectId: str) -> dict:
    try:
        latest = repo.get_latest_results_for_project(projectId=projectId)
        return progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except Exception:
        log.exception("[commissioning-ws] progress:compute-failed projectId=%s", projectId)
        return {
            "projectId": projectId,
            "counts": {"totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0},
            "lastTestedAtUtc": None,
            "eventSections": {"system": {"counts": {"totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0}, "lastTestedAtUtc": None}, "driver": {"counts": {"totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0}, "lastTestedAtUtc": None}},
            "devices": [],
        }


def _rollups_from_repo(*, repo: Repository, projectId: str, latest_results: dict, progress_payload: dict) -> dict:
    tags = repo.get_fail_tags_for_project(projectId=projectId)
    by_target: dict[str, int] = {}
    by_tag = {"NOT_STARTED": 0, "IN_PROGRESS": 0, "DONE": 0}
    total = 0
    for rec in latest_results.values():
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
        "progress": progress_payload,
        "counts": {
            "totalTargets": int((progress_payload or {}).get("counts", {}).get("totalTargets") or 0),
            "firstTimeFailTargets": repo.count_first_time_fail_targets(projectId=projectId),
        },
        "firstTimeFailTargets": repo.count_first_time_fail_targets(projectId=projectId),
        "currentFailures": {"total": total, "byTargetName": by_target, "byTag": by_tag},
    }


def _fails_from_latest(*, repo: Repository, projectId: str, latest_results: dict) -> list[dict]:
    tags = repo.get_fail_tags_for_project(projectId=projectId)
    fails = [rec for rec in latest_results.values() if rec.outcome == "FAIL"]
    fails.sort(key=lambda r: r.recordedAtUtc, reverse=True)
    out: list[dict] = []
    for rec in fails:
        target_key = str(rec.target.get("targetKey") or "")
        if not target_key:
            continue
        refs = rec.target.get("refs") if isinstance(rec.target.get("refs"), dict) else {}
        out.append(
            {
                "targetKey": target_key,
                "currentOutcome": "FAIL",
                "lastTestedAtUtc": rec.recordedAtUtc,
                "lastFailNote": rec.failNote,
                "recordedBy": rec.recordedBy,
                "tag": tags.get(target_key, "NOT_STARTED"),
                "deviceName": refs.get("deviceName") if isinstance(refs, dict) else None,
                "pageName": refs.get("pageName") if isinstance(refs, dict) else None,
                "buttonName": refs.get("buttonName") if isinstance(refs, dict) else None,
                "scope": refs.get("scope") if isinstance(refs, dict) else None,
                "targetName": rec.target.get("targetName"),
                "resolvedData": refs.get("resolvedData") if isinstance(refs, dict) else None,
            }
        )
    return out


def _activities_from_latest(*, latest_results: dict) -> list[dict]:
    rows = list(latest_results.values())
    rows.sort(key=lambda r: r.recordedAtUtc, reverse=True)
    out: list[dict] = []
    for rec in rows[:50]:
        refs = rec.target.get("refs") if isinstance(rec.target.get("refs"), dict) else {}
        out.append(
            {
                "type": "test_result",
                "projectId": rec.projectId,
                "recordedAtUtc": rec.recordedAtUtc,
                "targetKey": str(rec.target.get("targetKey") or ""),
                "outcome": rec.outcome,
                "targetName": rec.target.get("targetName"),
                "kind": rec.target.get("kind") or rec.target.get("targetKind"),
                "refs": refs if isinstance(refs, dict) else {},
                "failNote": rec.failNote,
            }
        )
    return out


def _active_upload_payload(*, repo: Repository, projectId: str) -> dict | None:
    active = repo.get_project_active_upload(projectId=projectId)
    if active is None:
        return None
    return {
        "uploadId": active.uploadId,
        "projectId": active.projectId,
        "originalFilename": active.originalFilename,
        "storagePath": active.storagePath,
        "uploadedAtUtc": active.uploadedAtUtc,
    }


def _commissioning_snapshot(*, repo: Repository, projectId: str) -> dict:
    latest = repo.get_latest_results_for_project(projectId=projectId)
    progress_payload = _safe_progress(repo=repo, projectId=projectId)
    rollups = _rollups_from_repo(repo=repo, projectId=projectId, latest_results=latest, progress_payload=progress_payload)
    return {
        "type": "commissioning_snapshot",
        "projectId": projectId,
        "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
        "progress": progress_payload,
        "rollups": rollups,
        "activities": _activities_from_latest(latest_results=latest),
        "fails": _fails_from_latest(repo=repo, projectId=projectId, latest_results=latest),
        "activeUpload": _active_upload_payload(repo=repo, projectId=projectId),
    }


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
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    label = payload.get("label")
    link, token = _repo(request).create_tech_link(projectId=projectId, label=str(label) if label is not None else None)
    return {"techLinkId": link.techLinkId, "techUrl": f"/testing/{token.techToken}"}


@router.post("/projects/{projectId}/tech-links/{techLinkId}/rotate")
def rotate_tech_link(request: Request, projectId: str, techLinkId: str) -> dict:
    try:
        token = _repo(request).rotate_tech_link_token(projectId=projectId, techLinkId=techLinkId)
    except KeyError:
        raise http_error(404, code="TECH_LINK_NOT_FOUND", message="Tech link not found.")
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
async def upload_apex(request: Request, projectId: str, apex: UploadFile) -> dict:
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
    _repo(request).record_upload(projectId=projectId, uploadId=upload_id, originalFilename=apex.filename, storagePath=str(path))
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
    _repo(request).record_upload(projectId=projectId, uploadId=upload_id, originalFilename=apex.filename, storagePath=str(path))

    try:
        generation = pipeline.regenerate_project(projectId=projectId, apex_path=path)
    except Exception as e:
        raise http_error(500, code="REGENERATE_FAILED", message=str(e))
    _repo(request).set_project_active_upload(projectId=projectId, uploadId=upload_id)
    active_upload = _active_upload_payload(repo=_repo(request), projectId=projectId)

    try:
        _broker(request).publish(
            projectId=projectId,
            event={
                "type": "generation",
                "status": "READY",
                "uploadId": upload_id,
                "originalFilename": apex.filename,
                "activeUpload": active_upload,
            },
        )
    except Exception:
        log.exception("[commissioning-ws] publish:generation-failed projectId=%s", projectId)

    return {
        "projectId": projectId,
        "uploadId": upload_id,
        "originalFilename": apex.filename,
        "storagePath": str(path),
        "activeUpload": active_upload,
        "generation": {"status": "READY", **(generation or {})},
    }


@router.post("/projects/{projectId}/regenerate")
def regenerate(request: Request, projectId: str, payload: dict) -> dict:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    upload_id = payload.get("uploadId")
    if upload_id is None:
        raise http_error(400, code="VALIDATION_ERROR", message="uploadId is required for MVP regenerate.")
    upload_dir = pipeline._project_upload_dir(projectId=projectId)
    candidates = list(upload_dir.glob(f"{upload_id}__*.apex"))
    if not candidates:
        raise http_error(404, code="UPLOAD_NOT_FOUND", message="Upload not found.")
    apex_path = candidates[0]
    try:
        pipeline.regenerate_project(projectId=projectId, apex_path=apex_path)
    except Exception as e:
        raise http_error(500, code="REGENERATE_FAILED", message=str(e))

    original_filename = apex_path.name.split("__", 1)[1] if "__" in apex_path.name else Path(apex_path.name).name
    _repo(request).record_upload(projectId=projectId, uploadId=str(upload_id), originalFilename=original_filename, storagePath=str(apex_path))
    _repo(request).set_project_active_upload(projectId=projectId, uploadId=str(upload_id))
    active_upload = _active_upload_payload(repo=_repo(request), projectId=projectId)
    try:
        _broker(request).publish(
            projectId=projectId,
            event={
                "type": "generation",
                "status": "READY",
                "uploadId": str(upload_id),
                "originalFilename": original_filename,
                "activeUpload": active_upload,
            },
        )
    except Exception:
        log.exception("[commissioning-ws] publish:generation-failed projectId=%s", projectId)
    return {"projectId": projectId, "status": "READY", "activeUpload": active_upload}


@router.get("/projects/{projectId}/fails")
def project_fails(request: Request, projectId: str) -> list[dict]:
    proj = _repo(request).get_project(projectId=projectId)
    if proj is None:
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    latest = _repo(request).get_latest_results_for_project(projectId=projectId)
    return _fails_from_latest(repo=_repo(request), projectId=projectId, latest_results=latest)


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
        log.exception("[commissioning-ws] publish:fail-tag-update-failed projectId=%s", projectId)

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

    repo = _repo(request)
    latest = repo.get_latest_results_for_project(projectId=projectId)
    try:
        prog = progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        raise http_error(503, code="GENERATION_NOT_READY", message="Project model is not ready yet.")
    return _rollups_from_repo(repo=repo, projectId=projectId, latest_results=latest, progress_payload=prog)


@router.get("/projects/{projectId}/events")
async def project_events(request: Request, projectId: str, once: bool = False):
    raise http_error(410, code="SSE_REMOVED", message="SSE endpoints have been removed; use WebSocket.")


@router.websocket("/projects/{projectId}/ws")
async def project_ws(websocket: WebSocket, projectId: str):
    await websocket.accept()
    log.info("[commissioning-ws] connect projectId=%s", projectId)

    repo = getattr(websocket.app.state, "repo", None)
    if repo is None or repo.get_project(projectId=projectId) is None:
        try:
            log.info("[commissioning-ws] project_not_found projectId=%s", projectId)
            await websocket.send_text(json.dumps({"type": "error", "code": "PROJECT_NOT_FOUND", "projectId": projectId}))
        finally:
            await websocket.close(code=1008)
        return

    broker = getattr(websocket.app.state, "project_event_broker", None)
    if broker is None:
        broker = ws_broker.ProjectEventBroker()
        websocket.app.state.project_event_broker = broker
    log.info("[commissioning-ws] broker_id=%s projectId=%s", id(broker), projectId)

    q = broker.subscribe(projectId=projectId)
    try:
        snapshot = _commissioning_snapshot(repo=repo, projectId=projectId)
        await websocket.send_text(json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False))
        while True:
            msg = await ws_broker.wait_for_next(q, timeout_s=15.0)
            if msg is None:
                await websocket.send_text(json.dumps({"type": "keepalive"}))
                continue
            try:
                parsed = json.loads(msg)
                if isinstance(parsed, dict):
                    t = str(parsed.get("type") or "").strip()
                    if t:
                        log.info("[commissioning-ws] send type=%s projectId=%s", t, projectId)
            except Exception:
                log.warning("[commissioning-ws] send:parse-failed projectId=%s", projectId)
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        log.info("[commissioning-ws] disconnect projectId=%s", projectId)
        return
    except Exception:
        log.exception("[commissioning-ws] stream-failed projectId=%s", projectId)
        return
    finally:
        try:
            broker.unsubscribe(projectId=projectId, q=q)
        except Exception:
            log.exception("[commissioning-ws] unsubscribe-failed projectId=%s", projectId)
