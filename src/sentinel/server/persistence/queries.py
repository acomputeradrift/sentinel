from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sentinel.server.persistence import db


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid4())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_client(database_url: str, *, name: str) -> str:
    client_id = _new_uuid()
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into clients (client_id, name, created_at_utc) values (%s, %s, %s)",
            (client_id, name, _utc_now()),
        )
        con.commit()
        return client_id
    finally:
        con.close()


def list_clients(database_url: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select client_id as \"clientId\", name, created_at_utc as \"createdAtUtc\" from clients order by created_at_utc desc",
            (),
        )
    finally:
        con.close()


def create_project(database_url: str, *, client_id: str, name: str) -> str:
    project_id = _new_uuid()
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into projects (project_id, client_id, name, status, created_at_utc) values (%s, %s, %s, %s, %s)",
            (project_id, client_id, name, "EMPTY", _utc_now()),
        )
        con.commit()
        return project_id
    finally:
        con.close()


def list_projects_for_client(database_url: str, *, client_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select project_id as \"projectId\", client_id as \"clientId\", name, status, created_at_utc as \"createdAtUtc\" "
            "from projects where client_id=%s order by created_at_utc desc",
            (client_id,),
        )
    finally:
        con.close()


def create_tech_link(database_url: str, *, project_id: str, label: str | None) -> dict[str, Any]:
    tech_link_id = _new_uuid()
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into tech_links (tech_link_id, project_id, label, created_at_utc) values (%s, %s, %s, %s)",
            (tech_link_id, project_id, label, _utc_now()),
        )
        con.commit()
        return {"techLinkId": tech_link_id, "projectId": project_id, "label": label}
    finally:
        con.close()


def rotate_tech_link_token(database_url: str, *, tech_link_id: str) -> dict[str, Any]:
    tech_token = uuid4().hex
    token_hash = _hash_token(tech_token)
    token_id = _new_uuid()
    issued_at = _utc_now()

    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute("update tech_link_tokens set revoked_at_utc=%s where tech_link_id=%s and revoked_at_utc is null", (issued_at, tech_link_id))
        cur.execute(
            "insert into tech_link_tokens (tech_link_token_id, tech_link_id, token_hash, issued_at_utc, revoked_at_utc) values (%s,%s,%s,%s,null)",
            (token_id, tech_link_id, token_hash, issued_at),
        )
        con.commit()
        return {"techLinkId": tech_link_id, "techToken": tech_token, "issuedAtUtc": issued_at.isoformat()}
    finally:
        con.close()


def resolve_active_tech_token(database_url: str, *, tech_token: str) -> dict[str, Any]:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select tl.tech_link_id as \"techLinkId\", tl.project_id as \"projectId\" "
            "from tech_link_tokens tlt join tech_links tl on tl.tech_link_id=tlt.tech_link_id "
            "where tlt.token_hash=%s and tlt.revoked_at_utc is null",
            (_hash_token(tech_token),),
        )
        if row is None:
            raise KeyError("TECH_LINK_REVOKED")
        return row
    finally:
        con.close()


def ensure_generation_run(database_url: str, *, project_id: str) -> str:
    con = db.connect(database_url)
    try:
        existing = db.fetch_one(
            con,
            "select generation_run_id as \"generationRunId\" from generation_runs where project_id=%s order by started_at_utc desc limit 1",
            (project_id,),
        )
        if existing is not None:
            return str(existing["generationRunId"])
        generation_run_id = _new_uuid()
        cur = con.cursor()
        cur.execute(
            "insert into generation_runs (generation_run_id, project_id, started_at_utc) values (%s,%s,%s)",
            (generation_run_id, project_id, _utc_now()),
        )
        con.commit()
        return generation_run_id
    finally:
        con.close()


def append_test_result(
    database_url: str,
    *,
    project_id: str,
    generation_run_id: str | None,
    recorded_by_tech_link_id: str | None,
    target_key: str,
    target_kind: str,
    target_name: str,
    refs: dict[str, Any],
    outcome: str,
    fail_note: str | None,
) -> str:
    test_result_id = _new_uuid()
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into test_results "
            "(test_result_id, project_id, generation_run_id, recorded_at_utc, recorded_by_role, recorded_by_tech_link_id, "
            "target_key, target_kind, target_name, refs, outcome, fail_note) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
            (
                test_result_id,
                project_id,
                generation_run_id,
                _utc_now(),
                "TECHNICIAN",
                recorded_by_tech_link_id,
                target_key,
                target_kind,
                target_name,
                json.dumps(refs),
                outcome,
                fail_note,
            ),
        )
        con.commit()
        return test_result_id
    finally:
        con.close()


def get_target_status(database_url: str, *, project_id: str, target_key: str) -> dict[str, Any]:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select outcome as \"currentOutcome\", recorded_at_utc as \"lastTestedAtUtc\", fail_note as \"lastFailNote\" "
            "from test_results where project_id=%s and target_key=%s order by recorded_at_utc desc, test_result_id desc limit 1",
            (project_id, target_key),
        )
        if row is None:
            return {"targetKey": target_key, "currentOutcome": "UNTESTED", "lastTestedAtUtc": None, "lastFailNote": None}
        return {"targetKey": target_key, **row}
    finally:
        con.close()


def list_latest_target_statuses(database_url: str, *, project_id: str) -> list[dict[str, Any]]:
    """
    Returns one row per targetKey representing the latest recorded state for that target in the project.

    Latest is determined by:
    - recorded_at_utc DESC
    - test_result_id DESC (deterministic tie-breaker)
    """
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select distinct on (tr.target_key) "
            "  tr.target_key as \"targetKey\", "
            "  tr.outcome as \"currentOutcome\", "
            "  tr.recorded_at_utc as \"lastTestedAtUtc\", "
            "  tr.fail_note as \"lastFailNote\", "
            "  tr.target_kind as \"targetKind\", "
            "  tr.target_name as \"targetName\", "
            "  tr.refs as \"refs\", "
            "  tr.recorded_by_tech_link_id as \"recordedByTechLinkId\", "
            "  tl.label as \"recordedByTechLabel\" "
            "from test_results tr "
            "left join tech_links tl on tl.tech_link_id=tr.recorded_by_tech_link_id "
            "where tr.project_id=%s "
            "order by tr.target_key, tr.recorded_at_utc desc, tr.test_result_id desc",
            (project_id,),
        )
    finally:
        con.close()


def list_latest_failed_targets(database_url: str, *, project_id: str) -> list[dict[str, Any]]:
    """
    Returns one row per targetKey where the latest recorded outcome is FAIL.

    Ordering is by lastTestedAtUtc DESC then targetKey ASC for stable UI presentation.
    """
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select * from ("
            "  select distinct on (tr.target_key) "
            "    tr.target_key as \"targetKey\", "
            "    tr.outcome as \"currentOutcome\", "
            "    tr.recorded_at_utc as \"lastTestedAtUtc\", "
            "    tr.fail_note as \"lastFailNote\", "
            "    tr.target_kind as \"targetKind\", "
            "    tr.target_name as \"targetName\", "
            "    tr.refs as \"refs\", "
            "    tr.recorded_by_tech_link_id as \"recordedByTechLinkId\", "
            "    tl.label as \"recordedByTechLabel\" "
            "  from test_results tr "
            "  left join tech_links tl on tl.tech_link_id=tr.recorded_by_tech_link_id "
            "  where tr.project_id=%s "
            "  order by tr.target_key, tr.recorded_at_utc desc, tr.test_result_id desc"
            ") latest where latest.\"currentOutcome\"='FAIL' "
            "order by latest.\"lastTestedAtUtc\" desc, latest.\"targetKey\" asc",
            (project_id,),
        )
    finally:
        con.close()
