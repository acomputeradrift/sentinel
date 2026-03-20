from __future__ import annotations

from fastapi import APIRouter, Request

from sentinel.server.api.errors import http_error
from sentinel.server.services.repositories import Repository


router = APIRouter(prefix="/api/v1/commissioning", tags=["commissioning"])


def _repo(request: Request) -> Repository:
    return request.app.state.repo


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

