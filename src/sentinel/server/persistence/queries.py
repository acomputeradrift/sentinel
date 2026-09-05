from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from sentinel.server.persistence import db


class DuplicateClientNameError(ValueError):
    pass


class DuplicateTechnicianNameError(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid4())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_client(database_url: str, *, user_id: str, name: str) -> str:
    client_id = _new_uuid()
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        try:
            cur.execute(
                "insert into clients (client_id, user_id, name, created_at_utc) values (%s, %s, %s, %s)",
                (client_id, user_id, name, _utc_now()),
            )
        except Exception as e:
            msg = str(e)
            if "clients_user_id_name_uq" in msg or "clients_name_uq" in msg:
                raise DuplicateClientNameError(name) from e
            raise
        con.commit()
        return client_id
    finally:
        con.close()


def list_clients_for_user(database_url: str, *, user_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select client_id as \"clientId\", user_id as \"userId\", name, created_at_utc as \"createdAtUtc\" "
            "from clients where user_id=%s order by created_at_utc desc",
            (user_id,),
        )
    finally:
        con.close()


def get_client(database_url: str, *, client_id: str) -> dict[str, Any] | None:
    con = db.connect(database_url)
    try:
        return db.fetch_one(
            con,
            "select client_id as \"clientId\", user_id as \"userId\", name, created_at_utc as \"createdAtUtc\" "
            "from clients where client_id=%s",
            (client_id,),
        )
    finally:
        con.close()


def list_technicians_for_user(database_url: str, *, user_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select technician_id as \"technicianId\", user_id as \"userId\", name, "
            "created_at_utc as \"createdAtUtc\" from technicians where user_id=%s "
            "order by created_at_utc asc, name asc",
            (user_id,),
        )
    finally:
        con.close()


def get_technician(database_url: str, *, technician_id: str) -> dict[str, Any] | None:
    con = db.connect(database_url)
    try:
        return db.fetch_one(
            con,
            "select technician_id as \"technicianId\", user_id as \"userId\", name, "
            "created_at_utc as \"createdAtUtc\" from technicians where technician_id=%s",
            (technician_id,),
        )
    finally:
        con.close()


def find_technician_by_name(database_url: str, *, user_id: str, name: str) -> dict[str, Any] | None:
    wanted = str(name or "").strip()
    if not wanted:
        return None
    con = db.connect(database_url)
    try:
        return db.fetch_one(
            con,
            "select technician_id as \"technicianId\", user_id as \"userId\", name, "
            "created_at_utc as \"createdAtUtc\" from technicians "
            "where user_id=%s and lower(name)=lower(%s)",
            (user_id, wanted),
        )
    finally:
        con.close()


def create_technician(database_url: str, *, user_id: str, name: str) -> dict[str, Any]:
    wanted = str(name or "").strip()
    if not wanted:
        raise KeyError("TECHNICIAN_NAME_REQUIRED")
    existing = find_technician_by_name(database_url, user_id=user_id, name=wanted)
    if existing is not None:
        return existing
    technician_id = _new_uuid()
    created_at = _utc_now()
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        try:
            cur.execute(
                "insert into technicians (technician_id, user_id, name, created_at_utc) values (%s, %s, %s, %s)",
                (technician_id, user_id, wanted, created_at),
            )
        except Exception as e:
            msg = str(e)
            if "technicians_user_id_name_ci_uq" in msg:
                con.rollback()
                found = find_technician_by_name(database_url, user_id=user_id, name=wanted)
                if found is not None:
                    return found
                raise DuplicateTechnicianNameError(wanted) from e
            raise
        con.commit()
        return {
            "technicianId": technician_id,
            "userId": user_id,
            "name": wanted,
            "createdAtUtc": created_at,
        }
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


def set_project_status(database_url: str, *, project_id: str, status: str) -> None:
    con = db.connect(database_url)
    try:
        exists = db.fetch_one(con, "select 1 from projects where project_id=%s", (project_id,))
        if exists is None:
            raise KeyError("PROJECT_NOT_FOUND")
        cur = con.cursor()
        cur.execute("update projects set status=%s where project_id=%s", (str(status or "").strip().upper(), project_id))
        con.commit()
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


def upsert_upload_record(
    database_url: str,
    *,
    project_id: str,
    upload_id: str,
    original_filename: str,
    storage_path: str,
) -> None:
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into uploads (upload_id, project_id, original_filename, storage_path, uploaded_at_utc) "
            "values (%s, %s, %s, %s, %s) "
            "on conflict (upload_id) do update set "
            "project_id=excluded.project_id, original_filename=excluded.original_filename, storage_path=excluded.storage_path",
            (upload_id, project_id, original_filename, storage_path, _utc_now()),
        )
        con.commit()
    finally:
        con.close()


def set_project_active_upload(database_url: str, *, project_id: str, upload_id: str) -> None:
    con = db.connect(database_url)
    try:
        owned = db.fetch_one(con, "select 1 from uploads where upload_id=%s and project_id=%s", (upload_id, project_id))
        if owned is None:
            raise KeyError("UPLOAD_NOT_FOUND")
        cur = con.cursor()
        cur.execute("update projects set active_upload_id=%s where project_id=%s", (upload_id, project_id))
        con.commit()
    finally:
        con.close()


def get_project_active_upload(database_url: str, *, project_id: str) -> dict[str, Any] | None:
    con = db.connect(database_url)
    try:
        return db.fetch_one(
            con,
            "select u.upload_id as \"uploadId\", u.project_id as \"projectId\", u.original_filename as \"originalFilename\", "
            "u.storage_path as \"storagePath\", u.uploaded_at_utc as \"uploadedAtUtc\" "
            "from projects p left join uploads u on u.upload_id=p.active_upload_id "
            "where p.project_id=%s",
            (project_id,),
        )
    finally:
        con.close()


def list_uploads_for_project(database_url: str, *, project_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select upload_id as \"uploadId\", project_id as \"projectId\", original_filename as \"originalFilename\", "
            "storage_path as \"storagePath\", uploaded_at_utc as \"uploadedAtUtc\" "
            "from uploads where project_id=%s order by uploaded_at_utc desc, upload_id desc",
            (project_id,),
        )
    finally:
        con.close()


def prune_project_uploads_keep_latest_two(database_url: str, *, project_id: str) -> list[str]:
    """
    Keep at most two upload rows per project: the two most recent by time, unless the active
    upload is older — then keep the newest row plus the active row.

    Returns storage_path values for deleted rows (for logging/diagnostics).
    """
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute("select active_upload_id from projects where project_id=%s", (project_id,))
        row = cur.fetchone()
        active_id = str(row[0]) if row and row[0] is not None else None
        cur.execute(
            "select upload_id, storage_path from uploads where project_id=%s "
            "order by uploaded_at_utc desc, upload_id desc",
            (project_id,),
        )
        rows = cur.fetchall()
        if not rows:
            con.commit()
            return []
        ordered_ids = [str(r[0]) for r in rows]
        id_to_path = {str(r[0]): str(r[1]) if r[1] is not None else "" for r in rows}
        keep: set[str] = set(ordered_ids[:2])
        if active_id and active_id not in keep:
            keep = {ordered_ids[0], active_id}
        deleted_paths: list[str] = []
        for uid in ordered_ids:
            if uid in keep:
                continue
            cur.execute("delete from uploads where upload_id=%s and project_id=%s", (uid, project_id))
            deleted_paths.append(id_to_path.get(uid, ""))
        con.commit()
        return deleted_paths
    finally:
        con.close()


def find_active_tech_link_for_technician(
    database_url: str, *, project_id: str, technician_id: str
) -> dict[str, Any] | None:
    wanted = str(technician_id or "").strip()
    if not wanted:
        return None
    con = db.connect(database_url)
    try:
        return db.fetch_one(
            con,
            "select tl.tech_link_id as \"techLinkId\", tl.label, tl.created_at_utc as \"createdAtUtc\", "
            "tl.technician_id as \"technicianId\", t.name as \"technicianName\", "
            "tlt.issued_path as \"issuedPath\", tlt.issued_at_utc as \"issuedAtUtc\" "
            "from tech_links tl join tech_link_tokens tlt on tlt.tech_link_id=tl.tech_link_id "
            "left join technicians t on t.technician_id=tl.technician_id "
            "where tl.project_id=%s and tl.technician_id=%s and tlt.revoked_at_utc is null "
            "order by tlt.issued_at_utc desc",
            (project_id, wanted),
        )
    finally:
        con.close()


def token_from_issued_path(issued_path: str | None) -> str | None:
    path = str(issued_path or "").strip()
    prefix = "/testing/"
    if not path.startswith(prefix):
        return None
    token = path[len(prefix) :].strip()
    return token or None


def create_tech_link(
    database_url: str, *, project_id: str, label: str | None, technician_id: str | None = None
) -> dict[str, Any]:
    tech_link_id = _new_uuid()
    created_at = _utc_now()
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into tech_links (tech_link_id, project_id, label, created_at_utc, technician_id) "
            "values (%s, %s, %s, %s, %s)",
            (tech_link_id, project_id, label, created_at, technician_id),
        )
        con.commit()
        return {
            "techLinkId": tech_link_id,
            "projectId": project_id,
            "label": label,
            "technicianId": technician_id,
            "createdAtUtc": created_at,
        }
    finally:
        con.close()


def list_active_tech_links(database_url: str, *, project_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select tl.tech_link_id as \"techLinkId\", tl.label, tl.created_at_utc as \"createdAtUtc\", "
            "tl.technician_id as \"technicianId\", t.name as \"technicianName\", "
            "tlt.issued_path as \"issuedPath\", tlt.issued_at_utc as \"issuedAtUtc\" "
            "from tech_links tl join tech_link_tokens tlt on tlt.tech_link_id=tl.tech_link_id "
            "left join technicians t on t.technician_id=tl.technician_id "
            "where tl.project_id=%s and tlt.revoked_at_utc is null "
            "order by tl.created_at_utc desc",
            (project_id,),
        )
    finally:
        con.close()


def revoke_tech_link_tokens(database_url: str, *, project_id: str, tech_link_id: str) -> None:
    revoked_at = _utc_now()
    con = db.connect(database_url)
    try:
        exists = db.fetch_one(
            con,
            "select 1 from tech_links where tech_link_id=%s and project_id=%s",
            (tech_link_id, project_id),
        )
        if exists is None:
            raise KeyError("TECH_LINK_NOT_FOUND")
        cur = con.cursor()
        cur.execute(
            "update tech_link_tokens set revoked_at_utc=%s "
            "where tech_link_id=%s and revoked_at_utc is null",
            (revoked_at, tech_link_id),
        )
        con.commit()
    finally:
        con.close()


def rotate_tech_link_token(database_url: str, *, tech_link_id: str, project_id: str | None = None) -> dict[str, Any]:
    tech_token = uuid4().hex
    token_hash = _hash_token(tech_token)
    token_id = _new_uuid()
    issued_at = _utc_now()

    con = db.connect(database_url)
    try:
        if project_id is not None:
            exists = db.fetch_one(
                con,
                "select 1 from tech_links where tech_link_id=%s and project_id=%s",
                (tech_link_id, project_id),
            )
            if exists is None:
                raise KeyError("TECH_LINK_NOT_FOUND")
        cur = con.cursor()
        issued_path = f"/testing/{tech_token}"
        cur.execute("update tech_link_tokens set revoked_at_utc=%s where tech_link_id=%s and revoked_at_utc is null", (issued_at, tech_link_id))
        cur.execute(
            "insert into tech_link_tokens (tech_link_token_id, tech_link_id, token_hash, issued_at_utc, revoked_at_utc, issued_path) "
            "values (%s,%s,%s,%s,null,%s)",
            (token_id, tech_link_id, token_hash, issued_at, issued_path),
        )
        con.commit()
        return {
            "techLinkId": tech_link_id,
            "techToken": tech_token,
            "issuedAtUtc": issued_at.isoformat(),
            "issuedPath": issued_path,
        }
    finally:
        con.close()


def resolve_active_tech_token(database_url: str, *, tech_token: str) -> dict[str, Any]:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select tl.tech_link_id as \"techLinkId\", tl.project_id as \"projectId\", "
            "tl.technician_id as \"technicianId\", coalesce(t.name, tl.label) as \"technicianName\" "
            "from tech_link_tokens tlt join tech_links tl on tl.tech_link_id=tlt.tech_link_id "
            "left join technicians t on t.technician_id=tl.technician_id "
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
    recorded_by_technician_id: str | None = None,
    recorded_by_technician_name: str | None = None,
    target_key: str,
    target_kind: str,
    target_name: str,
    refs: dict[str, Any],
    outcome: str,
    fail_note: str | None,
    batch_id: str | None = None,
    source: str = "SINGLE",
) -> str:
    test_result_id = _new_uuid()
    recorded_at = _utc_now()
    source_s = str(source or "SINGLE").strip().upper() or "SINGLE"
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into test_results "
            "(test_result_id, project_id, generation_run_id, recorded_at_utc, recorded_by_role, recorded_by_tech_link_id, "
            "recorded_by_technician_id, recorded_by_technician_name, "
            "target_key, target_kind, target_name, refs, outcome, fail_note, batch_id, source) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
            (
                test_result_id,
                project_id,
                generation_run_id,
                recorded_at,
                "TECHNICIAN",
                recorded_by_tech_link_id,
                recorded_by_technician_id,
                recorded_by_technician_name,
                target_key,
                target_kind,
                target_name,
                json.dumps(refs),
                outcome,
                fail_note,
                batch_id,
                source_s,
            ),
        )
        cur.execute(
            "insert into target_first_test_outcomes "
            "(project_id, target_key, first_outcome, first_test_result_id, first_recorded_at_utc) "
            "values (%s,%s,%s,%s,%s) "
            "on conflict (project_id, target_key) do nothing",
            (project_id, target_key, outcome, test_result_id, recorded_at),
        )
        con.commit()
        return test_result_id
    finally:
        con.close()


def append_test_results_batch(
    database_url: str,
    *,
    project_id: str,
    generation_run_id: str | None,
    recorded_by_tech_link_id: str | None,
    outcome: str,
    items: list[dict[str, Any]],
    batch_id: str | None = None,
    source: str = "GROUP",
    recorded_by_technician_id: str | None = None,
    recorded_by_technician_name: str | None = None,
) -> list[dict[str, Any]]:
    """Insert many test_results in one connection/transaction. Shared recorded_at, batch_id, and source."""
    recorded_at = _utc_now()
    batch_id = str(batch_id or "").strip() or _new_uuid()
    source_s = str(source or "GROUP").strip().upper() or "GROUP"
    out: list[dict[str, Any]] = []
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        for item in items:
            test_result_id = _new_uuid()
            target_key = str(item.get("target_key") or "")
            cur.execute(
                "insert into test_results "
                "(test_result_id, project_id, generation_run_id, recorded_at_utc, recorded_by_role, recorded_by_tech_link_id, "
                "recorded_by_technician_id, recorded_by_technician_name, "
                "target_key, target_kind, target_name, refs, outcome, fail_note, batch_id, source) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)",
                (
                    test_result_id,
                    project_id,
                    generation_run_id,
                    recorded_at,
                    "TECHNICIAN",
                    recorded_by_tech_link_id,
                    recorded_by_technician_id,
                    recorded_by_technician_name,
                    target_key,
                    str(item.get("target_kind") or ""),
                    str(item.get("target_name") or ""),
                    json.dumps(item.get("refs") or {}),
                    outcome,
                    item.get("fail_note"),
                    batch_id,
                    source_s,
                ),
            )
            cur.execute(
                "insert into target_first_test_outcomes "
                "(project_id, target_key, first_outcome, first_test_result_id, first_recorded_at_utc) "
                "values (%s,%s,%s,%s,%s) "
                "on conflict (project_id, target_key) do nothing",
                (project_id, target_key, outcome, test_result_id, recorded_at),
            )
            out.append(
                {
                    "testResultId": test_result_id,
                    "targetKey": target_key,
                    "recordedAtUtc": recorded_at,
                    "batchId": batch_id,
                    "source": source_s,
                }
            )
        con.commit()
        return out
    finally:
        con.close()


def current_test_pass_started_at(database_url: str, *, project_id: str) -> str | None:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select started_at_utc as \"startedAtUtc\" from project_test_passes "
            "where project_id=%s order by started_at_utc desc limit 1",
            (project_id,),
        )
        if not row or not row.get("startedAtUtc"):
            return None
        started = row.get("startedAtUtc")
        return started.isoformat() if hasattr(started, "isoformat") else str(started)
    finally:
        con.close()


def start_project_test_pass(
    database_url: str,
    *,
    project_id: str,
    recorded_by_role: str,
    recorded_by_user_id: str | None,
    reason: str | None,
    confirm_name: str | None,
) -> dict[str, Any]:
    pass_id = _new_uuid()
    started_at = _utc_now()
    con = db.connect(database_url)
    try:
        exists = db.fetch_one(con, "select 1 from projects where project_id=%s", (project_id,))
        if exists is None:
            raise KeyError("PROJECT_NOT_FOUND")
        cur = con.cursor()
        cur.execute(
            "insert into project_test_passes "
            "(test_pass_id, project_id, started_at_utc, recorded_by_role, recorded_by_user_id, reason, confirm_name) "
            "values (%s,%s,%s,%s,%s,%s,%s)",
            (pass_id, project_id, started_at, recorded_by_role, recorded_by_user_id, reason, confirm_name),
        )
        tags = db.fetch_all(
            con,
            "select target_key as \"targetKey\", tag, updated_at_utc as \"updatedAtUtc\" from fail_tags where project_id=%s",
            (project_id,),
        )
        for row in tags:
            cur.execute(
                "insert into fail_tag_history "
                "(fail_tag_history_id, project_id, target_key, tag, updated_at_utc, archived_at_utc, test_pass_id) "
                "values (%s,%s,%s,%s,%s,%s,%s)",
                (
                    _new_uuid(),
                    project_id,
                    row.get("targetKey"),
                    row.get("tag"),
                    row.get("updatedAtUtc") or started_at,
                    started_at,
                    pass_id,
                ),
            )
        cur.execute("delete from fail_tags where project_id=%s", (project_id,))
        con.commit()
        return {
            "testPassId": pass_id,
            "projectId": project_id,
            "startedAtUtc": started_at.isoformat() if hasattr(started_at, "isoformat") else str(started_at),
            "recordedBy": {"role": recorded_by_role, "userId": recorded_by_user_id},
            "reason": reason,
            "confirmName": confirm_name,
        }
    finally:
        con.close()


def list_fail_tag_history_for_project(database_url: str, *, project_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select target_key as \"targetKey\", tag, updated_at_utc as \"updatedAtUtc\", "
            "archived_at_utc as \"archivedAtUtc\", test_pass_id as \"testPassId\", project_id as \"projectId\" "
            "from fail_tag_history where project_id=%s order by archived_at_utc asc",
            (project_id,),
        )
    finally:
        con.close()


def list_test_results_for_project(database_url: str, *, project_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select test_result_id as \"testResultId\", "
            "target_key as \"targetKey\", target_kind as \"targetKind\", target_name as \"targetName\", refs as \"refs\", "
            "outcome, fail_note as \"failNote\", recorded_at_utc as \"recordedAtUtc\", recorded_by_role as \"recordedByRole\", "
            "recorded_by_tech_link_id as \"recordedByTechLinkId\", "
            "recorded_by_technician_id as \"recordedByTechnicianId\", "
            "recorded_by_technician_name as \"recordedByTechnicianName\", "
            "batch_id as \"batchId\", source as \"source\" "
            "from test_results where project_id=%s order by recorded_at_utc asc, test_result_id asc",
            (project_id,),
        )
    finally:
        con.close()


def get_target_status(database_url: str, *, project_id: str, target_key: str) -> dict[str, Any]:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select outcome as \"currentOutcome\", recorded_at_utc as \"lastTestedAtUtc\", fail_note as \"lastFailNote\" "
            "from test_results where project_id=%s and target_key=%s "
            "and recorded_at_utc >= coalesce("
            "(select max(started_at_utc) from project_test_passes where project_id=%s), "
            "'-infinity'::timestamptz) "
            "order by recorded_at_utc desc, test_result_id desc limit 1",
            (project_id, target_key, project_id),
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
            "and tr.recorded_at_utc >= coalesce("
            "(select max(started_at_utc) from project_test_passes where project_id=%s), "
            "'-infinity'::timestamptz) "
            "order by tr.target_key, tr.recorded_at_utc desc, tr.test_result_id desc",
            (project_id, project_id),
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
            "  and tr.recorded_at_utc >= coalesce("
            "(select max(started_at_utc) from project_test_passes where project_id=%s), "
            "'-infinity'::timestamptz) "
            "  order by tr.target_key, tr.recorded_at_utc desc, tr.test_result_id desc"
            ") latest where latest.\"currentOutcome\"='FAIL' "
            "order by latest.\"lastTestedAtUtc\" desc, latest.\"targetKey\" asc",
            (project_id, project_id),
        )
    finally:
        con.close()


def upsert_fail_tag(database_url: str, *, project_id: str, target_key: str, tag: str) -> None:
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into fail_tags (project_id, target_key, tag, updated_at_utc) values (%s,%s,%s,%s) "
            "on conflict (project_id, target_key) do update set tag=excluded.tag, updated_at_utc=excluded.updated_at_utc",
            (project_id, target_key, tag, _utc_now()),
        )
        con.commit()
    finally:
        con.close()


def list_fail_tags_for_project(database_url: str, *, project_id: str) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        return db.fetch_all(
            con,
            "select target_key as \"targetKey\", tag, updated_at_utc as \"updatedAtUtc\" from fail_tags where project_id=%s",
            (project_id,),
        )
    finally:
        con.close()


def upsert_layer_lock_state(
    database_url: str,
    *,
    project_id: str,
    scope_key: str,
    layer_key: str,
    visible: bool,
    locked: bool,
) -> None:
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into layer_lock_states (project_id, scope_key, layer_key, visible, locked, updated_at_utc) "
            "values (%s,%s,%s,%s,%s,%s) "
            "on conflict (project_id, scope_key, layer_key) do update set "
            "visible=excluded.visible, locked=excluded.locked, updated_at_utc=excluded.updated_at_utc",
            (project_id, scope_key, layer_key, bool(visible), bool(locked), _utc_now()),
        )
        con.commit()
    finally:
        con.close()


def list_layer_lock_states_for_project(
    database_url: str, *, project_id: str, scope_key: str | None = None
) -> list[dict[str, Any]]:
    con = db.connect(database_url)
    try:
        if scope_key is not None:
            return db.fetch_all(
                con,
                "select scope_key as \"scopeKey\", layer_key as \"layerKey\", visible, locked, updated_at_utc as \"updatedAtUtc\" "
                "from layer_lock_states where project_id=%s and scope_key=%s order by updated_at_utc desc",
                (project_id, scope_key),
            )
        return db.fetch_all(
            con,
            "select scope_key as \"scopeKey\", layer_key as \"layerKey\", visible, locked, updated_at_utc as \"updatedAtUtc\" "
            "from layer_lock_states where project_id=%s order by updated_at_utc desc",
            (project_id,),
        )
    finally:
        con.close()


@lru_cache(maxsize=32)
def _ensure_target_first_outcomes_backfilled(database_url: str) -> None:
    """One-time (per process, per DB URL) fill for rows created before materialized table existed."""
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into target_first_test_outcomes "
            "(project_id, target_key, first_outcome, first_test_result_id, first_recorded_at_utc) "
            "select s.project_id, s.target_key, s.outcome, s.test_result_id, s.recorded_at_utc from ( "
            "  select distinct on (tr.project_id, tr.target_key) tr.project_id, tr.target_key, tr.outcome, "
            "    tr.test_result_id, tr.recorded_at_utc "
            "  from test_results tr "
            "  where not exists ( "
            "    select 1 from target_first_test_outcomes t "
            "    where t.project_id = tr.project_id and t.target_key = tr.target_key "
            "  ) "
            "  order by tr.project_id, tr.target_key, tr.recorded_at_utc asc, tr.ctid asc "
            ") s "
            "on conflict (project_id, target_key) do nothing"
        )
        con.commit()
    finally:
        con.close()


def count_first_time_fail_targets(database_url: str, *, project_id: str) -> int:
    """
    Counts targets where the first ever recorded outcome for that target is FAIL.

    Uses ``target_first_test_outcomes`` (maintained on append, backfilled once per process).
    """
    _ensure_target_first_outcomes_backfilled(database_url)
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select count(*)::bigint as \"count\" from ("
            "  select distinct on (tr.target_key) tr.outcome as outcome "
            "  from test_results tr "
            "  where tr.project_id=%s "
            "  and tr.recorded_at_utc >= coalesce("
            "    (select max(started_at_utc) from project_test_passes where project_id=%s),"
            "    '-infinity'::timestamptz) "
            "  order by tr.target_key, tr.recorded_at_utc asc, tr.test_result_id asc"
            ") firsts where firsts.outcome='FAIL'",
            (project_id, project_id),
        )
        return int(row["count"]) if row else 0
    finally:
        con.close()


def get_tech_link_label(database_url: str, *, tech_link_id: str) -> str | None:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select label from tech_links where tech_link_id=%s",
            (tech_link_id,),
        )
        if row is None:
            return None
        return row.get("label")
    finally:
        con.close()


def clear_project_testing_data(database_url: str, *, project_id: str) -> None:
    start_project_test_pass(
        database_url,
        project_id=project_id,
        recorded_by_role="PROGRAMMER",
        recorded_by_user_id=None,
        reason="clear-tests-alias",
        confirm_name=None,
    )


def get_idempotency_response(database_url: str, *, scope: str, idempotency_key: str) -> dict[str, Any] | None:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select response_json as \"responseJson\" from idempotency_keys where scope=%s and idempotency_key=%s",
            (scope, idempotency_key),
        )
        if not row:
            return None
        rj = row.get("responseJson")
        if isinstance(rj, str):
            return json.loads(rj)
        if isinstance(rj, dict):
            return dict(rj)
        return None
    finally:
        con.close()


def put_idempotency_response(database_url: str, *, scope: str, idempotency_key: str, response: dict[str, Any]) -> None:
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into idempotency_keys (scope, idempotency_key, response_json) values (%s,%s,%s::jsonb)",
            (scope, idempotency_key, json.dumps(response)),
        )
        con.commit()
    finally:
        con.close()


def _parse_disabled_types(raw: Any) -> list[str]:
    from sentinel.server.services import testing_types

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = [raw]
    return testing_types.normalize_disabled_types(raw)


def get_testing_type_disabled(database_url: str, *, project_id: str) -> list[str]:
    con = db.connect(database_url)
    try:
        row = db.fetch_one(
            con,
            "select disabled_types as \"disabledTypes\" from project_testing_type_settings where project_id=%s",
            (project_id,),
        )
        if not row:
            return []
        return _parse_disabled_types(row.get("disabledTypes"))
    finally:
        con.close()


def set_testing_type_disabled(database_url: str, *, project_id: str, disabled_types: list[str]) -> list[str]:
    from sentinel.server.services import testing_types

    cleaned = testing_types.normalize_disabled_types(disabled_types)
    con = db.connect(database_url)
    try:
        cur = con.cursor()
        cur.execute(
            "insert into project_testing_type_settings (project_id, disabled_types, updated_at_utc) "
            "values (%s, %s::jsonb, %s) "
            "on conflict (project_id) do update set disabled_types = excluded.disabled_types, "
            "updated_at_utc = excluded.updated_at_utc",
            (project_id, json.dumps(cleaned), _utc_now()),
        )
        con.commit()
        return list(cleaned)
    finally:
        con.close()
