from __future__ import annotations

import logging
from datetime import datetime, timezone

from sentinel.server.services import commissioning_rollups
from sentinel.server.services import progress
from sentinel.server.services.repositories import Repository

log = logging.getLogger("uvicorn.error")


def safe_progress(*, repo: Repository, projectId: str) -> dict:
    try:
        latest = repo.get_latest_results_for_project(projectId=projectId)
        return progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except Exception:
        log.exception("[commissioning-ws] progress:compute-failed projectId=%s", projectId)
        return {
            "projectId": projectId,
            "counts": {"totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0},
            "lastTestedAtUtc": None,
            "eventSections": {
                "system": {
                    "counts": {"totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0},
                    "lastTestedAtUtc": None,
                },
                "driver": {
                    "counts": {"totalTargets": 0, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 0, "percentComplete": 0.0},
                    "lastTestedAtUtc": None,
                },
            },
            "devices": [],
        }


def fails_from_latest(*, repo: Repository, projectId: str, latest_results: dict) -> list[dict]:
    tags = repo.get_fail_tags_for_project(projectId=projectId)
    fails = [rec for rec in latest_results.values() if rec.outcome == "FAIL"]
    fails.sort(key=lambda r: r.recordedAtUtc, reverse=True)
    out: list[dict] = []
    for rec in fails:
        target_key = str(rec.target.get("targetKey") or "")
        if not target_key:
            continue
        refs = rec.target.get("refs") if isinstance(rec.target.get("refs"), dict) else {}
        recorded_by = rec.recordedBy if isinstance(rec.recordedBy, dict) else {}
        tech_name = ""
        if isinstance(refs, dict):
            tech_name = str(refs.get("techName") or "").strip()
        if not tech_name:
            tech_name = str(
                repo.get_tech_link_label(techLinkId=str(recorded_by.get("techLinkId") or "").strip()) or ""
            ).strip()
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
                "layerName": refs.get("layerName") if isinstance(refs, dict) else None,
                "viewport": refs.get("viewport") if isinstance(refs, dict) else None,
                "buttonName": refs.get("buttonName") if isinstance(refs, dict) else None,
                "scope": refs.get("scope") if isinstance(refs, dict) else None,
                "targetName": rec.target.get("targetName"),
                "resolvedData": refs.get("resolvedData") if isinstance(refs, dict) else None,
                "scopeType": refs.get("scopeType") if isinstance(refs, dict) else None,
                "effectiveRoomId": refs.get("effectiveRoomId") if isinstance(refs, dict) else None,
                "effectiveSourceId": refs.get("effectiveSourceId") if isinstance(refs, dict) else None,
                "effectiveRoomName": refs.get("effectiveRoomName") if isinstance(refs, dict) else None,
                "effectiveSourceName": refs.get("effectiveSourceName") if isinstance(refs, dict) else None,
                "effectiveScopeNames": refs.get("effectiveScopeNames") if isinstance(refs, dict) else None,
                "techName": tech_name,
            }
        )
    return out


def activities_from_latest(*, latest_results: dict) -> list[dict]:
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


def active_upload_payload(*, repo: Repository, projectId: str) -> dict | None:
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


def log_regen_baseline(
    *,
    projectId: str,
    uploadId: str | None,
    originalFilename: str | None,
    generation: dict | None,
) -> None:
    timings = (generation or {}).get("timings") if isinstance(generation, dict) else {}
    if not isinstance(timings, dict):
        timings = {}
    extract_s = timings.get("extractSec")
    generate_s = timings.get("generateSec")
    preload_s = generate_s
    total_s = timings.get("totalSec")
    log.info(
        "REGEN_BASELINE projectId=%s uploadId=%s file=%s extractSec=%s preloadSec=%s generateSec=%s totalSec=%s",
        str(projectId or ""),
        str(uploadId or ""),
        str(originalFilename or ""),
        extract_s if extract_s is not None else "",
        preload_s if preload_s is not None else "",
        generate_s if generate_s is not None else "",
        total_s if total_s is not None else "",
    )


def commissioning_snapshot(*, repo: Repository, projectId: str, seq: int = 0) -> dict:
    latest = repo.get_latest_results_for_project(projectId=projectId)
    progress_payload = safe_progress(repo=repo, projectId=projectId)
    rollups = commissioning_rollups.rollups_payload(
        repo=repo, projectId=projectId, latest_results=latest, progress_payload=progress_payload
    )
    return {
        "type": "commissioning_snapshot",
        "seq": int(seq or 0),
        "projectId": projectId,
        "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
        "progress": progress_payload,
        "rollups": rollups,
        "activities": activities_from_latest(latest_results=latest),
        "fails": fails_from_latest(repo=repo, projectId=projectId, latest_results=latest),
        "activeUpload": active_upload_payload(repo=repo, projectId=projectId),
    }
