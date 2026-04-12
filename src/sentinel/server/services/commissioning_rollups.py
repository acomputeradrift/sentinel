from __future__ import annotations

import logging
from typing import Any

from sentinel.server.services import progress
from sentinel.server.services.repositories import Repository, TestResultRecord

_log = logging.getLogger("uvicorn.error")


def failure_breakdown_for_latest(
    *,
    repo: Repository,
    projectId: str,
    latest_results: dict[str, TestResultRecord],
) -> tuple[int, dict[str, int], dict[str, int]]:
    """Returns (total_fail_rows, by_target_name, by_tag) for current FAIL outcomes."""
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
    return total, by_target, by_tag


def rollups_payload(
    *,
    repo: Repository,
    projectId: str,
    progress_payload: dict[str, Any],
    latest_results: dict[str, TestResultRecord],
) -> dict[str, Any]:
    """Commissioning HTTP / snapshot rollups shape (includes nested counts)."""
    first_time_fail_targets = repo.count_first_time_fail_targets(projectId=projectId)
    total, by_target, by_tag = failure_breakdown_for_latest(
        repo=repo, projectId=projectId, latest_results=latest_results
    )
    return {
        "projectId": projectId,
        "progress": progress_payload,
        "counts": {
            "totalTargets": int((progress_payload or {}).get("counts", {}).get("totalTargets") or 0),
            "firstTimeFailTargets": first_time_fail_targets,
        },
        "firstTimeFailTargets": first_time_fail_targets,
        "currentFailures": {"total": total, "byTargetName": by_target, "byTag": by_tag},
    }


def compute_progress_and_testing_rollups(
    *, repo: Repository, projectId: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Progress dict plus testing-style rollups (no nested counts block), or (None, None) if model missing.
    """
    try:
        latest = repo.get_latest_results_for_project(projectId=projectId)
        prog = progress.commissioning_progress(projectId=projectId, latest_results=latest)
    except FileNotFoundError:
        _log.info("[rollups] project-model-missing projectId=%s", projectId)
        return None, None
    except Exception:
        _log.exception("[rollups] compute-failed projectId=%s", projectId)
        return None, None

    total, by_target, by_tag = failure_breakdown_for_latest(
        repo=repo, projectId=projectId, latest_results=latest
    )
    rollups = {
        "projectId": projectId,
        "progress": prog,
        "firstTimeFailTargets": repo.count_first_time_fail_targets(projectId=projectId),
        "currentFailures": {"total": total, "byTargetName": by_target, "byTag": by_tag},
    }
    return prog, rollups
