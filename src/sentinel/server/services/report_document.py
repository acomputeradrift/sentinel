"""Report option contract and structured report document (no PDF).

Presets and checkboxes match docs/management_surface_and_reports_plan.md §4.
History is loaded from append-only test_results, never the 50-row activity cap.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sentinel.server.api import commissioning_snapshots
from sentinel.server.services import testing_types
from sentinel.server.services.repositories import (
    Repository,
    result_batch_id,
    result_source,
    tech_name_from_recorded_by,
)

PRESET_CLOSEOUT = "closeout"
PRESET_DEALER_PUNCH_LIST = "dealer_punch_list"
PRESET_FULL_AUDIT = "full_audit"

_KNOWN_PRESETS = frozenset({PRESET_CLOSEOUT, PRESET_DEALER_PUNCH_LIST, PRESET_FULL_AUDIT})
_OUTCOMES = ("PASS", "FAIL", "UNTESTED")

_INCLUDE_KEYS = (
    "cover",
    "progressSummary",
    "eventSectionCounts",
    "deviceCounts",
    "currentTargets",
    "failDetail",
    "programmerFields",
    "fullHistory",
    "includePriorPasses",
    "testingTypeLegend",
    "operatorAppendix",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _preset_include(preset: str) -> dict[str, Any]:
    if preset == PRESET_DEALER_PUNCH_LIST:
        return {
            "cover": True,
            "progressSummary": False,
            "eventSectionCounts": False,
            "deviceCounts": False,
            "currentTargets": False,
            "currentTargetOutcomes": ["FAIL"],
            "failDetail": True,
            "programmerFields": True,
            "fullHistory": False,
            "includePriorPasses": False,
            "testingTypeLegend": False,
            "operatorAppendix": False,
        }
    if preset == PRESET_FULL_AUDIT:
        return {
            "cover": True,
            "progressSummary": True,
            "eventSectionCounts": True,
            "deviceCounts": True,
            "currentTargets": True,
            "currentTargetOutcomes": ["PASS", "FAIL", "UNTESTED"],
            "failDetail": True,
            "programmerFields": True,
            "fullHistory": True,
            "includePriorPasses": True,
            "testingTypeLegend": True,
            "operatorAppendix": False,
        }
    return {
        "cover": True,
        "progressSummary": True,
        "eventSectionCounts": False,
        "deviceCounts": True,
        "currentTargets": False,
        "currentTargetOutcomes": ["FAIL"],
        "failDetail": True,
        "programmerFields": False,
        "fullHistory": False,
        "includePriorPasses": False,
        "testingTypeLegend": False,
        "operatorAppendix": False,
    }


def resolve_report_options(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    preset = str(raw.get("preset") or PRESET_CLOSEOUT).strip() or PRESET_CLOSEOUT
    if preset not in _KNOWN_PRESETS:
        raise ValueError("UNKNOWN_REPORT_PRESET")
    include = dict(_preset_include(preset))
    overrides = raw.get("include") if isinstance(raw.get("include"), dict) else {}
    for key in _INCLUDE_KEYS:
        if key in overrides:
            include[key] = bool(overrides[key])
    if "currentTargetOutcomes" in overrides:
        raw_out = overrides.get("currentTargetOutcomes")
        if isinstance(raw_out, list):
            include["currentTargetOutcomes"] = [str(x).strip().upper() for x in raw_out if str(x).strip().upper() in _OUTCOMES]
        elif raw_out is None:
            include["currentTargetOutcomes"] = list(_OUTCOMES)
    scope_in = raw.get("scope") if isinstance(raw.get("scope"), dict) else {}
    device_ids = scope_in.get("deviceIds")
    cleaned_ids: list[str] | None
    if isinstance(device_ids, list):
        cleaned_ids = [str(x).strip() for x in device_ids if str(x).strip()]
    else:
        cleaned_ids = None
    scope = {
        "includeSystemEvents": True if "includeSystemEvents" not in scope_in else bool(scope_in.get("includeSystemEvents")),
        "includeDriverEvents": True if "includeDriverEvents" not in scope_in else bool(scope_in.get("includeDriverEvents")),
        "includeDevices": True if "includeDevices" not in scope_in else bool(scope_in.get("includeDevices")),
        "deviceIds": cleaned_ids,
        "includeDisabledTypes": bool(scope_in.get("includeDisabledTypes") or False),
    }
    return {"preset": preset, "scope": scope, "include": include}


def _row_device_id(row: dict[str, Any]) -> str | None:
    raw = row.get("deviceId")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    key = str(row.get("targetKey") or "")
    if key.startswith("btn:") or key.startswith("vpbtn:"):
        parts = key.split(":")
        if len(parts) >= 2 and parts[1]:
            return parts[1]
    return None


def _row_event_section(row: dict[str, Any]) -> str | None:
    section = str(row.get("eventSection") or "").strip().lower()
    if section in {"system", "driver"}:
        return section
    key = str(row.get("targetKey") or "")
    kind = str(row.get("kind") or "").strip().upper()
    if key.startswith("event:") or kind == "EVENT":
        return None
    return None


def _in_scope(row: dict[str, Any], *, scope: dict[str, Any]) -> bool:
    section = _row_event_section(row)
    device_id = _row_device_id(row)
    if section == "system":
        return bool(scope.get("includeSystemEvents"))
    if section == "driver":
        return bool(scope.get("includeDriverEvents"))
    if device_id is not None:
        if not scope.get("includeDevices"):
            return False
        wanted = scope.get("deviceIds")
        if isinstance(wanted, list) and wanted:
            return device_id in {str(x) for x in wanted}
        return True
    key = str(row.get("targetKey") or "")
    if key.startswith("event:"):
        return bool(scope.get("includeSystemEvents") or scope.get("includeDriverEvents"))
    return True


def _fail_row(row: dict[str, Any], *, programmer_fields: bool) -> dict[str, Any]:
    out = {
        "targetKey": row.get("targetKey"),
        "currentOutcome": row.get("currentOutcome") or "FAIL",
        "lastFailNote": row.get("lastFailNote") or row.get("failNote"),
        "deviceName": row.get("deviceName"),
        "pageName": row.get("pageName"),
        "buttonName": row.get("buttonName"),
        "layerName": row.get("layerName"),
        "viewport": row.get("viewport"),
        "effectiveRoomName": row.get("effectiveRoomName"),
        "effectiveSourceName": row.get("effectiveSourceName"),
        "effectiveScopeNames": row.get("effectiveScopeNames"),
        "techName": row.get("techName"),
        "targetName": row.get("targetName"),
    }
    if programmer_fields:
        out["tag"] = row.get("tag")
        if row.get("failTag") is not None:
            out["failTag"] = row.get("failTag")
    return out


def _history_in_pass(rows: list[dict[str, Any]], *, include_prior: bool, cutoff: str | None) -> list[dict[str, Any]]:
    if include_prior:
        return list(rows)
    if cutoff:
        return [r for r in rows if str(r.get("recordedAtUtc") or "") >= cutoff]
    return [r for r in rows if str(r.get("passBoundary") or "") != "prior"]


def assemble_report_document(*, options: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    include = options.get("include") if isinstance(options.get("include"), dict) else {}
    scope = options.get("scope") if isinstance(options.get("scope"), dict) else {}
    generated_at = str(source.get("generatedAtUtc") or _utc_now())
    doc: dict[str, Any] = {
        "preset": options.get("preset"),
        "options": options,
        "generatedAtUtc": generated_at,
    }
    if include.get("cover"):
        cover = dict(source.get("cover") or {})
        cover["generatedAtUtc"] = generated_at
        doc["cover"] = cover
    progress = source.get("progress") if isinstance(source.get("progress"), dict) else {}
    if include.get("progressSummary"):
        doc["progressSummary"] = {
            "counts": progress.get("counts") or {},
            "lastTestedAtUtc": progress.get("lastTestedAtUtc"),
        }
    if include.get("eventSectionCounts"):
        sections = progress.get("eventSections") if isinstance(progress.get("eventSections"), dict) else {}
        out_sections: dict[str, Any] = {}
        if scope.get("includeSystemEvents") and "system" in sections:
            out_sections["system"] = sections.get("system")
        if scope.get("includeDriverEvents") and "driver" in sections:
            out_sections["driver"] = sections.get("driver")
        doc["eventSectionCounts"] = out_sections
    if include.get("deviceCounts"):
        devices = progress.get("devices") if isinstance(progress.get("devices"), list) else []
        filtered = [d for d in devices if isinstance(d, dict) and _in_scope(d, scope=scope)]
        doc["deviceCounts"] = filtered
    if include.get("currentTargets"):
        wanted = {str(x).strip().upper() for x in (include.get("currentTargetOutcomes") or list(_OUTCOMES))}
        rows = source.get("currentTargets") if isinstance(source.get("currentTargets"), list) else []
        doc["currentTargets"] = [
            r
            for r in rows
            if isinstance(r, dict)
            and str(r.get("currentOutcome") or "").strip().upper() in wanted
            and _in_scope(r, scope=scope)
        ]
    if include.get("failDetail"):
        fails = source.get("fails") if isinstance(source.get("fails"), list) else []
        doc["failDetail"] = [
            _fail_row(r, programmer_fields=bool(include.get("programmerFields")))
            for r in fails
            if isinstance(r, dict) and _in_scope(r, scope=scope)
        ]
    if include.get("fullHistory"):
        history = source.get("history") if isinstance(source.get("history"), list) else []
        history = _history_in_pass(
            [r for r in history if isinstance(r, dict)],
            include_prior=bool(include.get("includePriorPasses")),
            cutoff=str(source.get("currentPassStartedAtUtc") or "") or None,
        )
        doc["history"] = [r for r in history if _in_scope(r, scope=scope)]
    if include.get("testingTypeLegend"):
        legend = source.get("testingTypes") if isinstance(source.get("testingTypes"), dict) else {}
        doc["testingTypeLegend"] = legend
    if include.get("operatorAppendix"):
        names = source.get("technicianNames") if isinstance(source.get("technicianNames"), list) else []
        cleaned = []
        seen: set[str] = set()
        for name in names:
            s = str(name or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            cleaned.append(s)
        doc["operatorAppendix"] = {"technicianNames": cleaned}
    return doc


def _history_row_from_record(rec: Any) -> dict[str, Any]:
    target = rec.target if isinstance(getattr(rec, "target", None), dict) else {}
    recorded_by = rec.recordedBy if isinstance(getattr(rec, "recordedBy", None), dict) else {}
    return {
        "testResultId": rec.testResultId,
        "recordedAtUtc": rec.recordedAtUtc,
        "outcome": rec.outcome,
        "failNote": rec.failNote,
        "source": result_source(rec),
        "batchId": result_batch_id(rec),
        "targetKey": target.get("targetKey"),
        "targetName": target.get("targetName"),
        "kind": target.get("kind") or target.get("targetKind"),
        "techName": tech_name_from_recorded_by(recorded_by),
        "recordedBy": {
            "role": recorded_by.get("role"),
            "technicianId": recorded_by.get("technicianId"),
            "name": tech_name_from_recorded_by(recorded_by),
        },
    }


def _current_target_from_record(rec: Any) -> dict[str, Any]:
    target = rec.target if isinstance(getattr(rec, "target", None), dict) else {}
    recorded_by = rec.recordedBy if isinstance(getattr(rec, "recordedBy", None), dict) else {}
    refs = target.get("refs") if isinstance(target.get("refs"), dict) else {}
    kind = str(target.get("kind") or target.get("targetKind") or "").strip().upper()
    return {
        "targetKey": target.get("targetKey"),
        "kind": kind or None,
        "targetName": target.get("targetName"),
        "currentOutcome": rec.outcome,
        "lastTestedAtUtc": rec.recordedAtUtc,
        "lastFailNote": rec.failNote,
        "techName": tech_name_from_recorded_by(recorded_by),
        "deviceId": refs.get("deviceId") or _row_device_id({"targetKey": target.get("targetKey")}),
        "eventSection": "system" if kind == "EVENT" and "system" in str(refs.get("eventSection") or "").lower() else refs.get("eventSection"),
    }


def _technician_names(*, repo: Repository, projectId: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for link in repo.list_active_tech_links(projectId=projectId):
        name = str(getattr(link, "label", None) or "").strip()
        tech_id = str(getattr(link, "technicianId", None) or "").strip()
        if tech_id:
            tech = repo.get_technician(technicianId=tech_id)
            if tech is not None and str(tech.name or "").strip():
                name = str(tech.name).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _current_pass_started_at(*, repo: Repository, projectId: str) -> str | None:
    fn = getattr(repo, "get_current_test_pass_started_at", None)
    if callable(fn):
        return fn(projectId=projectId)
    locked = getattr(repo, "_current_pass_started_at_locked", None)
    if callable(locked):
        lock = getattr(repo, "_lock", None)
        if lock is not None:
            with lock:
                return locked(projectId=projectId)
        return locked(projectId=projectId)
    queries = getattr(repo, "_q", None)
    url = getattr(repo, "_database_url", None)
    if queries is not None and url:
        return queries.current_test_pass_started_at(url, project_id=projectId)
    return None


def load_report_source(*, repo: Repository, projectId: str) -> dict[str, Any]:
    project = repo.get_project(projectId=projectId)
    if project is None:
        raise KeyError("PROJECT_NOT_FOUND")
    client = repo.get_client(clientId=project.clientId)
    latest = repo.get_latest_results_for_project(projectId=projectId)
    progress = commissioning_snapshots.safe_progress(repo=repo, projectId=projectId)
    fails = commissioning_snapshots.fails_from_latest(repo=repo, projectId=projectId, latest_results=latest)
    history_recs = repo.list_test_results_for_project(projectId=projectId)
    upload = repo.get_project_active_upload(projectId=projectId)
    settings = testing_types.settings_payload(
        project_id=projectId, disabled_types=testing_types.disabled_types_from_repo(repo, projectId)
    )
    return {
        "cover": {
            "clientName": str(client.name if client is not None else ""),
            "projectName": str(project.name or ""),
            "projectId": project.projectId,
            "originalFilename": upload.originalFilename if upload is not None else None,
            "uploadedAtUtc": upload.uploadedAtUtc if upload is not None else None,
            "status": str(project.status or ""),
        },
        "progress": progress,
        "fails": fails,
        "currentTargets": [_current_target_from_record(rec) for rec in latest.values()],
        "history": [_history_row_from_record(rec) for rec in history_recs],
        "testingTypes": settings,
        "technicianNames": _technician_names(repo=repo, projectId=projectId),
        "currentPassStartedAtUtc": _current_pass_started_at(repo=repo, projectId=projectId),
    }


def build_report_document(*, repo: Repository, projectId: str, options: dict[str, Any]) -> dict[str, Any]:
    return assemble_report_document(options=options, source=load_report_source(repo=repo, projectId=projectId))
