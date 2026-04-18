from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Request, WebSocket
from fastapi import UploadFile

from sentinel.server.api.errors import http_error
from sentinel.server.api import commissioning_snapshots
from sentinel.server.api.commissioning_project_ws import run_commissioning_project_ws
from sentinel.server.services import commissioning_rollups
from sentinel.server.services import pipeline
from sentinel.server.services import progress
from sentinel.server.services import ws_broker
from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID
from sentinel.server.services.repositories import Repository


router = APIRouter(prefix="/api/v1/commissioning", tags=["commissioning"])
log = logging.getLogger("uvicorn.error")


def _repo(request: Request) -> Repository:
    return request.app.state.repo


def _commissioning_user_id(_request: Request) -> str:
    return COMMISSIONING_STUB_USER_ID


def _project_owned_by_user(repo: Repository, *, user_id: str, project_id: str) -> bool:
    proj = repo.get_project(projectId=project_id)
    if proj is None:
        return False
    client = repo.get_client(clientId=proj.clientId)
    return client is not None and str(client.userId) == str(user_id)


def _require_project_for_user(repo: Repository, *, user_id: str, project_id: str):
    if not _project_owned_by_user(repo, user_id=user_id, project_id=project_id):
        raise http_error(404, code="PROJECT_NOT_FOUND", message="Project not found.")
    return repo.get_project(projectId=project_id)


def _broker(request: Request) -> ws_broker.ProjectEventBroker:
    broker = getattr(request.app.state, "project_event_broker", None)
    if broker is None:
        broker = ws_broker.ProjectEventBroker()
        request.app.state.project_event_broker = broker
    return broker


def _publish_generation_phase(
    request: Request,
    *,
    projectId: str,
    status: str,
    percent: int | None = None,
    uploadId: str | None = None,
    originalFilename: str | None = None,
    activeUpload: dict | None = None,
) -> None:
    try:
        _broker(request).publish(
            projectId=projectId,
            event={
                "type": "generation_phase",
                "projectId": projectId,
                "status": str(status or "").strip().upper(),
                "percent": percent,
                "uploadId": uploadId,
                "originalFilename": originalFilename,
                "activeUpload": activeUpload,
            },
        )
    except Exception:
        log.exception("[commissioning-ws] publish:generation-phase-failed projectId=%s status=%s", projectId, status)


@router.get("/clients")
def list_clients(request: Request) -> list[dict]:
    uid = _commissioning_user_id(request)
    clients = _repo(request).list_clients(userId=uid)
    return [{"clientId": c.clientId, "name": c.name, "createdAtUtc": c.createdAtUtc} for c in clients]


@router.get("/clients/{clientId}/projects")
def list_projects_for_client(request: Request, clientId: str) -> list[dict]:
    uid = _commissioning_user_id(request)
    try:
        projects = _repo(request).list_projects_for_client(userId=uid, clientId=clientId)
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
    try:
        c = _repo(request).create_client(userId=_commissioning_user_id(request), name=name)
    except KeyError as e:
        if str(e) == "'CLIENT_EXISTS'" or str(e) == "CLIENT_EXISTS":
            raise http_error(409, code="CLIENT_EXISTS", message="Client name already exists.")
        raise
    return {"clientId": c.clientId, "name": c.name, "createdAtUtc": c.createdAtUtc}


@router.post("/clients/{clientId}/projects")
def create_project(request: Request, clientId: str, payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise http_error(400, code="VALIDATION_ERROR", message="Project name is required.")
    p = _repo(request).create_project(userId=_commissioning_user_id(request), clientId=clientId, name=name)
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
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    label = payload.get("label")
    link, token = repo.create_tech_link(projectId=projectId, label=str(label) if label is not None else None)
    return {"techLinkId": link.techLinkId, "techUrl": f"/testing/{token.techToken}"}


@router.post("/projects/{projectId}/tech-links/{techLinkId}/rotate")
def rotate_tech_link(request: Request, projectId: str, techLinkId: str) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    try:
        token = repo.rotate_tech_link_token(projectId=projectId, techLinkId=techLinkId)
    except KeyError:
        raise http_error(404, code="TECH_LINK_NOT_FOUND", message="Tech link not found.")
    return {"techLinkId": techLinkId, "techUrl": f"/testing/{token.techToken}"}


@router.get("/projects/{projectId}/tech-links")
def list_active_tech_links(request: Request, projectId: str) -> list[dict]:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    links = repo.list_active_tech_links(projectId=projectId)
    # Read-only list endpoint: do not rotate/revoke tokens as a side effect.
    return [{"techLinkId": l.techLinkId, "label": l.label, "createdAtUtc": l.createdAtUtc, "techUrl": ""} for l in links]


@router.post("/projects/{projectId}/tech-links/{techLinkId}/revoke")
def revoke_tech_link(request: Request, projectId: str, techLinkId: str) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    try:
        repo.revoke_tech_link(projectId=projectId, techLinkId=techLinkId)
    except KeyError:
        raise http_error(404, code="TECH_LINK_NOT_FOUND", message="Tech link not found.")
    return {"projectId": projectId, "techLinkId": techLinkId, "revoked": True}


@router.post("/projects/{projectId}/uploads")
async def upload_apex(request: Request, projectId: str, apex: UploadFile) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    if not apex.filename:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex filename is required.")
    content = await apex.read()
    if not content:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex file is empty.")
    upload_id = str(uuid4())
    path = pipeline.save_upload(projectId=projectId, uploadId=upload_id, filename=apex.filename, content=content)
    repo.record_upload(projectId=projectId, uploadId=upload_id, originalFilename=apex.filename, storagePath=str(path))
    return {"uploadId": upload_id, "projectId": projectId, "originalFilename": apex.filename, "storagePath": str(path)}


@router.post("/projects/{projectId}/upload-and-regenerate")
async def upload_and_regenerate(request: Request, projectId: str, apex: UploadFile) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    if not apex.filename:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex filename is required.")
    content = await apex.read()
    if not content:
        raise http_error(400, code="VALIDATION_ERROR", message="Apex file is empty.")

    upload_id = str(uuid4())
    path = pipeline.save_upload(projectId=projectId, uploadId=upload_id, filename=apex.filename, content=content)
    repo.record_upload(projectId=projectId, uploadId=upload_id, originalFilename=apex.filename, storagePath=str(path))

    try:
        generation = await asyncio.to_thread(
            pipeline.regenerate_project,
            projectId=projectId,
            apex_path=path,
            phase_hook=lambda phase, percent=0: _publish_generation_phase(
                request,
                projectId=projectId,
                status=str(phase or ""),
                percent=percent,
                uploadId=upload_id,
                originalFilename=apex.filename,
            ),
        )
    except Exception as e:
        raise http_error(500, code="REGENERATE_FAILED", message=str(e))
    commissioning_snapshots.log_regen_baseline(
        projectId=projectId,
        uploadId=upload_id,
        originalFilename=apex.filename,
        generation=generation if isinstance(generation, dict) else {},
    )
    repo.set_project_active_upload(projectId=projectId, uploadId=upload_id)
    repo.prune_project_upload_retention(
        projectId=projectId,
        activeUploadId=str(upload_id),
        activeStoragePath=str(path),
    )
    active_upload = commissioning_snapshots.active_upload_payload(repo=repo, projectId=projectId)
    _publish_generation_phase(
        request,
        projectId=projectId,
        status="READY",
        percent=100,
        uploadId=upload_id,
        originalFilename=apex.filename,
        activeUpload=active_upload,
    )

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
async def regenerate(request: Request, projectId: str, payload: dict) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    upload_id = payload.get("uploadId")
    if upload_id is None:
        raise http_error(400, code="VALIDATION_ERROR", message="uploadId is required for MVP regenerate.")
    upload_dir = pipeline._project_upload_dir(projectId=projectId)
    candidates = list(upload_dir.glob(f"{upload_id}__*.apex"))
    if not candidates:
        raise http_error(404, code="UPLOAD_NOT_FOUND", message="Upload not found.")
    apex_path = candidates[0]
    generation: dict | None = None
    try:
        generation = await asyncio.to_thread(
            pipeline.regenerate_project,
            projectId=projectId,
            apex_path=apex_path,
            phase_hook=lambda phase, percent=0: _publish_generation_phase(
                request,
                projectId=projectId,
                status=str(phase or ""),
                percent=percent,
                uploadId=str(upload_id),
                originalFilename=apex_path.name.split("__", 1)[1] if "__" in apex_path.name else Path(apex_path.name).name,
            ),
        )
    except Exception as e:
        raise http_error(500, code="REGENERATE_FAILED", message=str(e))

    original_filename = apex_path.name.split("__", 1)[1] if "__" in apex_path.name else Path(apex_path.name).name
    commissioning_snapshots.log_regen_baseline(
        projectId=projectId,
        uploadId=str(upload_id),
        originalFilename=original_filename,
        generation=generation if isinstance(generation, dict) else {},
    )
    repo.record_upload(projectId=projectId, uploadId=str(upload_id), originalFilename=original_filename, storagePath=str(apex_path))
    repo.set_project_active_upload(projectId=projectId, uploadId=str(upload_id))
    repo.prune_project_upload_retention(
        projectId=projectId,
        activeUploadId=str(upload_id),
        activeStoragePath=str(apex_path),
    )
    active_upload = commissioning_snapshots.active_upload_payload(repo=repo, projectId=projectId)
    _publish_generation_phase(
        request,
        projectId=projectId,
        status="READY",
        percent=100,
        uploadId=str(upload_id),
        originalFilename=original_filename,
        activeUpload=active_upload,
    )
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
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    latest = repo.get_latest_results_for_project(projectId=projectId)
    return commissioning_snapshots.fails_from_latest(repo=repo, projectId=projectId, latest_results=latest)


@router.put("/projects/{projectId}/fail-tags")
def put_fail_tag(request: Request, projectId: str, payload: dict) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)

    target_key = str(payload.get("targetKey") or "").strip()
    tag = str(payload.get("tag") or "").strip().upper()
    if not target_key:
        raise http_error(400, code="VALIDATION_ERROR", message="targetKey is required.")
    if tag not in ("NOT_STARTED", "IN_PROGRESS", "DONE"):
        raise http_error(400, code="VALIDATION_ERROR", message="tag must be NOT_STARTED, IN_PROGRESS, or DONE.")

    try:
        repo.set_fail_tag(projectId=projectId, targetKey=target_key, tag=tag)
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
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    latest = repo.get_latest_results_for_project(projectId=projectId)
    try:
        return progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        raise http_error(503, code="GENERATION_NOT_READY", message="Project model is not ready yet.")


@router.get("/projects/{projectId}/rollups")
def project_rollups(request: Request, projectId: str) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    latest = repo.get_latest_results_for_project(projectId=projectId)
    try:
        prog = progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        raise http_error(503, code="GENERATION_NOT_READY", message="Project model is not ready yet.")
    return commissioning_rollups.rollups_payload(
        repo=repo, projectId=projectId, latest_results=latest, progress_payload=prog
    )


@router.get("/projects/{projectId}/events")
async def project_events(request: Request, projectId: str, once: bool = False):
    raise http_error(410, code="SSE_REMOVED", message="SSE endpoints have been removed; use WebSocket.")


@router.post("/projects/{projectId}/clear-tests")
def clear_project_tests(request: Request, projectId: str) -> dict:
    repo = _repo(request)
    _require_project_for_user(repo, user_id=_commissioning_user_id(request), project_id=projectId)
    repo.clear_project_testing_data(projectId=projectId)
    snapshot = commissioning_snapshots.commissioning_snapshot(repo=repo, projectId=projectId)
    try:
        _broker(request).publish(projectId=projectId, event=snapshot)
    except Exception:
        log.exception("[commissioning-ws] publish:clear-tests-failed projectId=%s", projectId)
    return snapshot


@router.websocket("/projects/{projectId}/ws")
async def project_ws(websocket: WebSocket, projectId: str):
    await websocket.accept()

    repo = getattr(websocket.app.state, "repo", None)
    if repo is None or not _project_owned_by_user(repo, user_id=COMMISSIONING_STUB_USER_ID, project_id=projectId):
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

    await run_commissioning_project_ws(websocket=websocket, projectId=projectId, repo=repo, broker=broker)
