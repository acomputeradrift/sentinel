from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi import UploadFile

from sentinel.server.api.errors import http_error
from sentinel.server.services import pipeline
from sentinel.server.services import progress
from sentinel.server.services.repositories import Repository


router = APIRouter(prefix="/api/v1/commissioning", tags=["commissioning"])


def _repo(request: Request) -> Repository:
    return request.app.state.repo


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
    fails = [rec for rec in latest.values() if rec.outcome == "FAIL"]
    fails.sort(key=lambda r: r.recordedAtUtc, reverse=True)
    return [
        {
            "targetKey": str(rec.target.get("targetKey") or ""),
            "currentOutcome": "FAIL",
            "lastTestedAtUtc": rec.recordedAtUtc,
            "lastFailNote": rec.failNote,
            "recordedBy": rec.recordedBy,
        }
        for rec in fails
        if str(rec.target.get("targetKey") or "")
    ]


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
