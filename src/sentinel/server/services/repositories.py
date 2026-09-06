from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import threading
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid4())


def new_token() -> str:
    return uuid4().hex


def project_has_generated_artifacts(*, projectId: str) -> bool:
    root = Path(os.environ.get("SENTINEL_GENERATED_ROOT") or "generated").resolve()
    project_dir = (root / str(projectId)).resolve()
    if not project_dir.is_dir():
        return False
    return any(project_dir.glob("*_project_data.json"))


def hydrate_project_ready_status(project: Project | None) -> Project | None:
    if project is None:
        return None
    status = str(project.status or "").strip().upper()
    if status != "READY" and project_has_generated_artifacts(projectId=project.projectId):
        project.status = "READY"
    return project


TEST_RESULT_SOURCE_SINGLE = "SINGLE"
TEST_RESULT_SOURCE_GROUP = "GROUP"


def result_source(rec: Any, *, default: str | None = None) -> str:
    raw = str(getattr(rec, "source", None) or "").strip().upper()
    if raw:
        return raw
    if getattr(rec, "batchId", None):
        return TEST_RESULT_SOURCE_GROUP
    return default or TEST_RESULT_SOURCE_SINGLE


def result_batch_id(rec: Any) -> str | None:
    raw = getattr(rec, "batchId", None)
    s = str(raw).strip() if raw is not None else ""
    return s or None


@dataclass(frozen=True)
class Client:
    clientId: str
    userId: str
    name: str
    createdAtUtc: str


@dataclass
class Project:
    projectId: str
    clientId: str
    name: str
    createdAtUtc: str
    status: str


@dataclass
class Technician:
    technicianId: str
    userId: str
    name: str
    createdAtUtc: str


@dataclass
class TechLink:
    techLinkId: str
    projectId: str
    label: str | None
    createdAtUtc: str
    technicianId: str | None = None
    issuedPath: str | None = None
    issuedAtUtc: str | None = None


@dataclass
class ActiveToken:
    techToken: str
    techLinkId: str
    projectId: str
    technicianId: str | None = None
    technicianName: str | None = None
    issuedAtUtc: str | None = None


def recorded_by_from_token(tok: ActiveToken) -> dict[str, Any]:
    name = str(tok.technicianName or "").strip()
    return {
        "role": "TECHNICIAN",
        "techLinkId": tok.techLinkId,
        "technicianId": tok.technicianId,
        "name": name,
    }


def tech_name_from_recorded_by(recorded_by: Any) -> str:
    if not isinstance(recorded_by, dict):
        return ""
    return str(recorded_by.get("name") or "").strip()


@dataclass
class UploadRecord:
    uploadId: str
    projectId: str
    originalFilename: str
    storagePath: str
    uploadedAtUtc: str


@dataclass
class TestResultRecord:
    testResultId: str
    projectId: str
    recordedAtUtc: str
    recordedBy: dict[str, Any]
    target: dict[str, Any]
    outcome: str
    failNote: str | None
    batchId: str | None = None
    source: str = TEST_RESULT_SOURCE_SINGLE


class Repository(Protocol):
    def create_client(self, *, userId: str, name: str) -> Client: ...

    def get_client(self, *, clientId: str) -> Client | None: ...

    def create_project(self, *, userId: str, clientId: str, name: str) -> Project: ...

    def list_clients(self, *, userId: str) -> list[Client]: ...

    def list_projects_for_client(self, *, userId: str, clientId: str) -> list[Project]: ...

    def get_project(self, *, projectId: str) -> Project | None: ...

    def set_project_status(self, *, projectId: str, status: str) -> None: ...

    def list_technicians(self, *, userId: str) -> list[Technician]: ...

    def create_technician(self, *, userId: str, name: str) -> Technician: ...

    def get_technician(self, *, technicianId: str) -> Technician | None: ...

    def create_tech_link(
        self, *, projectId: str, label: str | None, technicianId: str | None = None
    ) -> tuple[TechLink, ActiveToken]: ...

    def rotate_tech_link_token(self, *, projectId: str, techLinkId: str) -> ActiveToken: ...

    def list_active_tech_links(self, *, projectId: str) -> list[TechLink]: ...

    def revoke_tech_link(self, *, projectId: str, techLinkId: str) -> None: ...

    def resolve_active_token(self, *, techToken: str) -> ActiveToken: ...

    def record_upload(self, *, projectId: str, uploadId: str, originalFilename: str, storagePath: str) -> UploadRecord: ...

    def set_project_active_upload(self, *, projectId: str, uploadId: str) -> None: ...

    def get_project_active_upload(self, *, projectId: str) -> UploadRecord | None: ...

    def list_uploads_for_project(self, *, projectId: str) -> list[UploadRecord]: ...

    def prune_project_upload_retention(self, *, projectId: str, activeUploadId: str, activeStoragePath: str) -> None: ...

    def append_test_result(
        self,
        *,
        techToken: str,
        target: dict[str, Any],
        outcome: str,
        failNote: str | None,
    ) -> TestResultRecord: ...

    def append_test_results_batch(
        self,
        *,
        techToken: str,
        items: list[dict[str, Any]],
        outcome: str,
    ) -> list[TestResultRecord]: ...

    def get_target_status(self, *, techToken: str, targetKey: str) -> dict[str, Any]: ...

    def get_latest_results_for_project(self, *, projectId: str) -> dict[str, TestResultRecord]: ...

    def list_test_results_for_project(self, *, projectId: str) -> list[TestResultRecord]: ...

    def start_project_test_pass(
        self,
        *,
        projectId: str,
        recordedBy: dict[str, Any],
        reason: str | None = None,
        confirmName: str | None = None,
    ) -> dict[str, Any]: ...

    def get_current_test_pass_started_at(self, *, projectId: str) -> str | None: ...

    def list_fail_tag_history_for_project(self, *, projectId: str) -> list[dict[str, Any]]: ...

    def set_fail_tag(self, *, projectId: str, targetKey: str, tag: str) -> None: ...

    def get_fail_tags_for_project(self, *, projectId: str) -> dict[str, str]: ...

    def get_fail_tag_updated_at_for_project(self, *, projectId: str) -> dict[str, str]: ...

    def set_layer_lock_state(self, *, projectId: str, scopeKey: str, layerKey: str, visible: bool, locked: bool) -> None: ...

    def list_layer_lock_states_for_project(self, *, projectId: str, scopeKey: str | None = None) -> list[dict[str, Any]]: ...

    def count_first_time_fail_targets(self, *, projectId: str) -> int: ...

    def get_tech_link_label(self, *, techLinkId: str) -> str | None: ...

    def clear_project_testing_data(self, *, projectId: str) -> None: ...

    def get_idempotency_response(self, *, scope: str, key: str) -> dict[str, Any] | None: ...

    def put_idempotency_response(self, *, scope: str, key: str, response: dict[str, Any]) -> None: ...

    def get_testing_type_disabled(self, *, projectId: str) -> list[str]: ...

    def set_testing_type_disabled(self, *, projectId: str, disabledTypes: list[str]) -> list[str]: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, Client] = {}
        self._projects: dict[str, Project] = {}
        self._technicians: dict[str, Technician] = {}
        self._tech_links: dict[str, TechLink] = {}
        self._active_tokens: dict[str, ActiveToken] = {}
        self._active_token_by_link: dict[str, str] = {}
        self._uploads: dict[str, UploadRecord] = {}
        self._active_upload_by_project: dict[str, str] = {}
        self._results_by_project_target: dict[tuple[str, str], list[TestResultRecord]] = {}
        self._fail_tags_by_project_target: dict[tuple[str, str], str] = {}
        self._fail_tag_times_by_project_target: dict[tuple[str, str], str] = {}
        self._layer_locks_by_project_scope_layer: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._idempotency: dict[tuple[str, str], dict[str, Any]] = {}
        # First recorded outcome per (projectId, targetKey); mirrors Postgres target_first_test_outcomes.
        self._first_outcome_by_project_target: dict[tuple[str, str], str] = {}
        # Monotonic ids for in-memory test results (matches Postgres test_result_id ordering).
        self._next_test_result_id = 0
        self._testing_type_disabled_by_project: dict[str, list[str]] = {}
        self._test_passes_by_project: dict[str, list[dict[str, Any]]] = {}
        self._fail_tag_history: list[dict[str, Any]] = []

    @staticmethod
    def _latest_record(items: list[TestResultRecord]) -> TestResultRecord | None:
        if not items:
            return None
        # Deterministic "latest" selection (aligns with Postgres: recorded_at desc, test_result_id desc):
        # - primary: recordedAtUtc (ISO string sorts chronologically for same offset)
        # - tie-break: numeric testResultId when possible, else lexicographic
        def _key(r: TestResultRecord) -> tuple:
            tid = r.testResultId
            try:
                tid_sort: int | str = int(tid)
            except ValueError:
                tid_sort = tid
            return (r.recordedAtUtc, tid_sort)

        return max(items, key=_key)

    def create_client(self, *, userId: str, name: str) -> Client:
        with self._lock:
            wanted = str(name).strip().casefold()
            for existing in self._clients.values():
                if str(existing.userId) == str(userId) and str(existing.name).strip().casefold() == wanted:
                    raise KeyError("CLIENT_EXISTS")
            client = Client(clientId=new_uuid(), userId=str(userId), name=name, createdAtUtc=utc_now())
            self._clients[client.clientId] = client
            return client

    def get_client(self, *, clientId: str) -> Client | None:
        with self._lock:
            return self._clients.get(clientId)

    def create_project(self, *, userId: str, clientId: str, name: str) -> Project:
        with self._lock:
            client = self._clients.get(clientId)
            if client is None or str(client.userId) != str(userId):
                raise KeyError("CLIENT_NOT_FOUND")
            project = Project(projectId=new_uuid(), clientId=clientId, name=name, createdAtUtc=utc_now(), status="EMPTY")
            self._projects[project.projectId] = project
            return project

    def list_clients(self, *, userId: str) -> list[Client]:
        with self._lock:
            return [c for c in self._clients.values() if str(c.userId) == str(userId)]

    def list_projects_for_client(self, *, userId: str, clientId: str) -> list[Project]:
        with self._lock:
            client = self._clients.get(clientId)
            if client is None or str(client.userId) != str(userId):
                raise KeyError("CLIENT_NOT_FOUND")
            return [hydrate_project_ready_status(p) or p for p in self._projects.values() if p.clientId == clientId]

    def get_project(self, *, projectId: str) -> Project | None:
        with self._lock:
            project = self._projects.get(projectId)
        return hydrate_project_ready_status(project)

    def set_project_status(self, *, projectId: str, status: str) -> None:
        wanted = str(status or "").strip().upper()
        with self._lock:
            project = self._projects.get(projectId)
            if project is None:
                raise KeyError("PROJECT_NOT_FOUND")
            project.status = wanted

    def list_technicians(self, *, userId: str) -> list[Technician]:
        with self._lock:
            out = [t for t in self._technicians.values() if str(t.userId) == str(userId)]
            out.sort(key=lambda t: (t.createdAtUtc, t.name))
            return out

    def create_technician(self, *, userId: str, name: str) -> Technician:
        with self._lock:
            return self._find_or_create_technician_locked(userId=str(userId), name=name)

    def get_technician(self, *, technicianId: str) -> Technician | None:
        with self._lock:
            return self._technicians.get(str(technicianId))

    def _find_or_create_technician_locked(self, *, userId: str, name: str) -> Technician:
        wanted = str(name or "").strip()
        if not wanted:
            raise KeyError("TECHNICIAN_NAME_REQUIRED")
        folded = wanted.casefold()
        for existing in self._technicians.values():
            if str(existing.userId) == str(userId) and str(existing.name).strip().casefold() == folded:
                return existing
        tech = Technician(
            technicianId=new_uuid(),
            userId=str(userId),
            name=wanted,
            createdAtUtc=utc_now(),
        )
        self._technicians[tech.technicianId] = tech
        return tech

    def _company_user_id_for_project_locked(self, *, projectId: str) -> str:
        project = self._projects.get(projectId)
        if project is None:
            raise KeyError("PROJECT_NOT_FOUND")
        client = self._clients.get(project.clientId)
        if client is None:
            raise KeyError("CLIENT_NOT_FOUND")
        return str(client.userId)

    def _resolve_technician_for_link_locked(
        self, *, projectId: str, label: str | None, technicianId: str | None
    ) -> Technician:
        user_id = self._company_user_id_for_project_locked(projectId=projectId)
        tid = str(technicianId or "").strip()
        if tid:
            tech = self._technicians.get(tid)
            if tech is None or str(tech.userId) != str(user_id):
                raise KeyError("TECHNICIAN_NOT_FOUND")
            return tech
        return self._find_or_create_technician_locked(userId=user_id, name=str(label or ""))

    def create_tech_link(
        self, *, projectId: str, label: str | None, technicianId: str | None = None
    ) -> tuple[TechLink, ActiveToken]:
        with self._lock:
            tech = self._resolve_technician_for_link_locked(
                projectId=projectId, label=label, technicianId=technicianId
            )
            existing = self._active_link_for_technician_locked(
                projectId=projectId, technicianId=tech.technicianId
            )
            if existing is None:
                existing = self._active_link_for_name_locked(projectId=projectId, name=tech.name)
            if existing is not None:
                token = self._active_tokens.get(self._active_token_by_link[existing.techLinkId])
                if token is not None:
                    return existing, token
            link = TechLink(
                techLinkId=new_uuid(),
                projectId=projectId,
                label=tech.name,
                createdAtUtc=utc_now(),
                technicianId=tech.technicianId,
            )
            self._tech_links[link.techLinkId] = link
            token = self._issue_token_locked(projectId=projectId, techLinkId=link.techLinkId)
            return link, token

    def _active_link_for_technician_locked(self, *, projectId: str, technicianId: str) -> TechLink | None:
        wanted = str(technicianId or "").strip()
        if not wanted:
            return None
        for link in self._tech_links.values():
            if link.projectId != projectId:
                continue
            if str(link.technicianId or "").strip() != wanted:
                continue
            if link.techLinkId not in self._active_token_by_link:
                continue
            return link
        return None

    def _link_display_name_locked(self, link: TechLink) -> str:
        tid = str(link.technicianId or "").strip()
        if tid:
            tech = self._technicians.get(tid)
            if tech is not None:
                name = str(tech.name or "").strip()
                if name:
                    return name
        return str(link.label or "").strip()

    def _active_link_for_name_locked(self, *, projectId: str, name: str) -> TechLink | None:
        wanted = str(name or "").strip().casefold()
        if not wanted:
            return None
        for link in self._tech_links.values():
            if link.projectId != projectId:
                continue
            if link.techLinkId not in self._active_token_by_link:
                continue
            if self._link_display_name_locked(link).casefold() == wanted:
                return link
        return None

    def rotate_tech_link_token(self, *, projectId: str, techLinkId: str) -> ActiveToken:
        with self._lock:
            link = self._tech_links.get(techLinkId)
            if link is None or link.projectId != projectId:
                raise KeyError("TECH_LINK_NOT_FOUND")
            # revoke old token for this link (remove mapping)
            old = self._active_token_by_link.get(techLinkId)
            if old is not None:
                self._active_tokens.pop(old, None)
            return self._issue_token_locked(projectId=projectId, techLinkId=techLinkId)

    def list_active_tech_links(self, *, projectId: str) -> list[TechLink]:
        with self._lock:
            out: list[TechLink] = []
            for link in self._tech_links.values():
                if link.projectId != projectId:
                    continue
                token = self._active_token_by_link.get(link.techLinkId)
                if not token:
                    continue
                active = self._active_tokens.get(token)
                issued_at = active.issuedAtUtc if active is not None else None
                out.append(
                    TechLink(
                        techLinkId=link.techLinkId,
                        projectId=link.projectId,
                        label=link.label,
                        createdAtUtc=link.createdAtUtc,
                        technicianId=link.technicianId,
                        issuedPath=f"/testing/{token}",
                        issuedAtUtc=issued_at,
                    )
                )
            out.sort(key=lambda l: l.createdAtUtc, reverse=True)
            return out

    def revoke_tech_link(self, *, projectId: str, techLinkId: str) -> None:
        with self._lock:
            link = self._tech_links.get(techLinkId)
            if link is None or link.projectId != projectId:
                raise KeyError("TECH_LINK_NOT_FOUND")
            old = self._active_token_by_link.pop(techLinkId, None)
            if old is not None:
                self._active_tokens.pop(old, None)

    def _who_for_link_locked(self, *, techLinkId: str) -> tuple[str | None, str | None]:
        link = self._tech_links.get(techLinkId)
        if link is None:
            return None, None
        tid = str(link.technicianId or "").strip() or None
        name = None
        if tid:
            tech = self._technicians.get(tid)
            if tech is not None:
                name = str(tech.name or "").strip() or None
        if not name:
            name = str(link.label or "").strip() or None
        return tid, name

    def _issue_token_locked(self, *, projectId: str, techLinkId: str) -> ActiveToken:
        techToken = new_token()
        technician_id, technician_name = self._who_for_link_locked(techLinkId=techLinkId)
        token = ActiveToken(
            techToken=techToken,
            techLinkId=techLinkId,
            projectId=projectId,
            technicianId=technician_id,
            technicianName=technician_name,
            issuedAtUtc=utc_now(),
        )
        self._active_tokens[techToken] = token
        self._active_token_by_link[techLinkId] = techToken
        return token

    def resolve_active_token(self, *, techToken: str) -> ActiveToken:
        with self._lock:
            tok = self._active_tokens.get(techToken)
            if tok is None:
                raise KeyError("TECH_LINK_REVOKED")
            return tok

    def record_upload(self, *, projectId: str, uploadId: str, originalFilename: str, storagePath: str) -> UploadRecord:
        with self._lock:
            if projectId not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            uploaded = UploadRecord(
                uploadId=uploadId,
                projectId=projectId,
                originalFilename=originalFilename,
                storagePath=storagePath,
                uploadedAtUtc=utc_now(),
            )
            self._uploads[uploadId] = uploaded
            return uploaded

    def set_project_active_upload(self, *, projectId: str, uploadId: str) -> None:
        with self._lock:
            upload = self._uploads.get(uploadId)
            if upload is None or upload.projectId != projectId:
                raise KeyError("UPLOAD_NOT_FOUND")
            self._active_upload_by_project[projectId] = uploadId

    def get_project_active_upload(self, *, projectId: str) -> UploadRecord | None:
        with self._lock:
            upload_id = self._active_upload_by_project.get(projectId)
            if not upload_id:
                return None
            return self._uploads.get(upload_id)

    def list_uploads_for_project(self, *, projectId: str) -> list[UploadRecord]:
        with self._lock:
            items = [u for u in self._uploads.values() if u.projectId == projectId]
            items.sort(key=lambda u: (u.uploadedAtUtc, u.uploadId), reverse=True)
            return list(items)

    def prune_project_upload_retention(self, *, projectId: str, activeUploadId: str, activeStoragePath: str) -> None:
        from sentinel.server.services import pipeline

        with self._lock:
            items = [u for u in self._uploads.values() if u.projectId == projectId]
            items.sort(key=lambda u: (u.uploadedAtUtc, u.uploadId), reverse=True)
            ordered_ids = [u.uploadId for u in items]
            keep: set[str] = set(ordered_ids[:2])
            if str(activeUploadId) not in keep and ordered_ids:
                keep = {ordered_ids[0], str(activeUploadId)}
            elif str(activeUploadId) not in keep:
                keep = {str(activeUploadId)}
            for uid in ordered_ids:
                if uid in keep:
                    continue
                self._uploads.pop(uid, None)
        keep_path = Path(activeStoragePath).resolve()
        pipeline.prune_project_upload_dir_to_single_file(projectId=projectId, keep_path=keep_path)

    def append_test_result(
        self,
        *,
        techToken: str,
        target: dict[str, Any],
        outcome: str,
        failNote: str | None,
    ) -> TestResultRecord:
        tok = self.resolve_active_token(techToken=techToken)
        with self._lock:
            self._next_test_result_id += 1
            tr_id = str(self._next_test_result_id)
            ts = utc_now()
            rec = TestResultRecord(
                testResultId=tr_id,
                projectId=tok.projectId,
                recordedAtUtc=ts,
                recordedBy=recorded_by_from_token(tok),
                target=target,
                outcome=outcome,
                failNote=failNote,
                batchId=None,
                source=TEST_RESULT_SOURCE_SINGLE,
            )
            key = (tok.projectId, str(target.get("targetKey") or ""))
            self._results_by_project_target.setdefault(key, []).append(rec)
            if key not in self._first_outcome_by_project_target:
                self._first_outcome_by_project_target[key] = str(outcome or "").strip().upper()
        return rec

    def append_test_results_batch(
        self,
        *,
        techToken: str,
        items: list[dict[str, Any]],
        outcome: str,
    ) -> list[TestResultRecord]:
        tok = self.resolve_active_token(techToken=techToken)
        ts = utc_now()
        batch_id = new_uuid()
        recs: list[TestResultRecord] = []
        with self._lock:
            for item in items:
                target = dict(item.get("target") or {})
                note = item.get("failNote")
                note_s = str(note).strip() if note is not None else None
                self._next_test_result_id += 1
                tr_id = str(self._next_test_result_id)
                rec = TestResultRecord(
                    testResultId=tr_id,
                    projectId=tok.projectId,
                    recordedAtUtc=ts,
                    recordedBy=recorded_by_from_token(tok),
                    target=target,
                    outcome=outcome,
                    failNote=note_s or None,
                    batchId=batch_id,
                    source=TEST_RESULT_SOURCE_GROUP,
                )
                key = (tok.projectId, str(target.get("targetKey") or ""))
                self._results_by_project_target.setdefault(key, []).append(rec)
                if key not in self._first_outcome_by_project_target:
                    self._first_outcome_by_project_target[key] = str(outcome or "").strip().upper()
                recs.append(rec)
        return recs

    def _current_pass_started_at_locked(self, *, projectId: str) -> str | None:
        passes = self._test_passes_by_project.get(str(projectId)) or []
        if not passes:
            return None
        return str(passes[-1].get("startedAtUtc") or "") or None

    def _results_in_current_pass_locked(self, items: list[TestResultRecord], *, projectId: str) -> list[TestResultRecord]:
        cutoff = self._current_pass_started_at_locked(projectId=projectId)
        if not cutoff:
            return list(items)
        return [r for r in items if str(r.recordedAtUtc or "") >= cutoff]

    def get_target_status(self, *, techToken: str, targetKey: str) -> dict[str, Any]:
        tok = self.resolve_active_token(techToken=techToken)
        with self._lock:
            key = (tok.projectId, targetKey)
            items = self._results_in_current_pass_locked(
                self._results_by_project_target.get(key, []), projectId=tok.projectId
            )
            last = self._latest_record(items)
            if last is None:
                return {"targetKey": targetKey, "currentOutcome": "UNTESTED", "lastTestedAtUtc": None, "lastFailNote": None}
            return {
                "targetKey": targetKey,
                "currentOutcome": last.outcome,
                "lastTestedAtUtc": last.recordedAtUtc,
                "lastFailNote": last.failNote,
            }

    def get_latest_results_for_project(self, *, projectId: str) -> dict[str, TestResultRecord]:
        with self._lock:
            out: dict[str, TestResultRecord] = {}
            for (pid, target_key), items in self._results_by_project_target.items():
                if pid != projectId or not items:
                    continue
                window = self._results_in_current_pass_locked(items, projectId=projectId)
                last = self._latest_record(window)
                if last is not None:
                    out[target_key] = last
            return out

    def list_test_results_for_project(self, *, projectId: str) -> list[TestResultRecord]:
        with self._lock:
            out: list[TestResultRecord] = []
            for (pid, _target_key), items in self._results_by_project_target.items():
                if pid != projectId:
                    continue
                out.extend(items)
            out.sort(key=lambda r: (r.recordedAtUtc, r.testResultId))
            return out

    def get_current_test_pass_started_at(self, *, projectId: str) -> str | None:
        with self._lock:
            return self._current_pass_started_at_locked(projectId=projectId)

    def start_project_test_pass(
        self,
        *,
        projectId: str,
        recordedBy: dict[str, Any],
        reason: str | None = None,
        confirmName: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if projectId not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            started = utc_now()
            pass_id = new_uuid()
            rec = {
                "testPassId": pass_id,
                "projectId": projectId,
                "startedAtUtc": started,
                "recordedBy": dict(recordedBy or {}),
                "reason": str(reason).strip() if reason else None,
                "confirmName": str(confirmName).strip() if confirmName else None,
            }
            self._test_passes_by_project.setdefault(projectId, []).append(rec)
            drop_tag_keys = [key for key in self._fail_tags_by_project_target.keys() if key[0] == projectId]
            for key in drop_tag_keys:
                self._fail_tag_history.append(
                    {
                        "targetKey": key[1],
                        "tag": self._fail_tags_by_project_target.get(key),
                        "updatedAtUtc": self._fail_tag_times_by_project_target.get(key),
                        "archivedAtUtc": started,
                        "testPassId": pass_id,
                        "projectId": projectId,
                    }
                )
                self._fail_tags_by_project_target.pop(key, None)
                self._fail_tag_times_by_project_target.pop(key, None)
            return rec

    def list_fail_tag_history_for_project(self, *, projectId: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._fail_tag_history if row.get("projectId") == projectId]

    def set_fail_tag(self, *, projectId: str, targetKey: str, tag: str) -> None:
        with self._lock:
            if projectId not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            self._fail_tags_by_project_target[(projectId, targetKey)] = tag
            self._fail_tag_times_by_project_target[(projectId, targetKey)] = utc_now()

    def get_fail_tags_for_project(self, *, projectId: str) -> dict[str, str]:
        with self._lock:
            out: dict[str, str] = {}
            for (pid, target_key), tag in self._fail_tags_by_project_target.items():
                if pid == projectId:
                    out[target_key] = tag
            return out

    def get_fail_tag_updated_at_for_project(self, *, projectId: str) -> dict[str, str]:
        with self._lock:
            out: dict[str, str] = {}
            for (pid, target_key), at in self._fail_tag_times_by_project_target.items():
                if pid == projectId:
                    out[target_key] = at
            return out

    def set_layer_lock_state(self, *, projectId: str, scopeKey: str, layerKey: str, visible: bool, locked: bool) -> None:
        with self._lock:
            if projectId not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            self._layer_locks_by_project_scope_layer[(projectId, str(scopeKey), str(layerKey))] = {
                "scopeKey": str(scopeKey),
                "layerKey": str(layerKey),
                "visible": bool(visible),
                "locked": bool(locked),
                "updatedAtUtc": utc_now(),
            }

    def list_layer_lock_states_for_project(self, *, projectId: str, scopeKey: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows: list[dict[str, Any]] = []
            for (pid, scope_key, _layer_key), value in self._layer_locks_by_project_scope_layer.items():
                if pid != projectId:
                    continue
                if scopeKey is not None and str(scope_key) != str(scopeKey):
                    continue
                rows.append(dict(value))
            rows.sort(key=lambda r: str(r.get("updatedAtUtc") or ""), reverse=True)
            return rows

    def count_first_time_fail_targets(self, *, projectId: str) -> int:
        with self._lock:
            count = 0
            seen: set[str] = set()
            for (pid, target_key), items in self._results_by_project_target.items():
                if pid != projectId or target_key in seen:
                    continue
                window = self._results_in_current_pass_locked(items, projectId=projectId)
                if not window:
                    continue
                first = min(window, key=lambda r: (r.recordedAtUtc, r.testResultId))
                seen.add(target_key)
                if str(first.outcome or "").strip().upper() == "FAIL":
                    count += 1
            return count

    def get_tech_link_label(self, *, techLinkId: str) -> str | None:
        with self._lock:
            link = self._tech_links.get(techLinkId)
            if link is None:
                return None
            label = str(link.label or "").strip()
            return label or None

    def clear_project_testing_data(self, *, projectId: str) -> None:
        self.start_project_test_pass(
            projectId=projectId,
            recordedBy={"role": "PROGRAMMER", "userId": None},
            reason="clear-tests-alias",
        )

    def get_idempotency_response(self, *, scope: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._idempotency.get((str(scope), str(key)))

    def put_idempotency_response(self, *, scope: str, key: str, response: dict[str, Any]) -> None:
        with self._lock:
            self._idempotency[(str(scope), str(key))] = dict(response)

    def get_testing_type_disabled(self, *, projectId: str) -> list[str]:
        with self._lock:
            if str(projectId) not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            return list(self._testing_type_disabled_by_project.get(str(projectId)) or [])

    def set_testing_type_disabled(self, *, projectId: str, disabledTypes: list[str]) -> list[str]:
        from sentinel.server.services import testing_types

        cleaned = testing_types.normalize_disabled_types(disabledTypes)
        with self._lock:
            if str(projectId) not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            self._testing_type_disabled_by_project[str(projectId)] = list(cleaned)
            return list(cleaned)


class PostgresRepository:
    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url
        from sentinel.server.persistence import db as persistence_db  # local import to avoid hard dependency in in-memory mode
        from sentinel.server.persistence import queries as persistence_queries

        self._db = persistence_db
        self._q = persistence_queries
        self._db.apply_migrations(database_url)

    def create_client(self, *, userId: str, name: str) -> Client:
        try:
            client_id = self._q.create_client(self._database_url, user_id=userId, name=name)
        except self._q.DuplicateClientNameError as e:
            raise KeyError("CLIENT_EXISTS") from e
        return Client(clientId=client_id, userId=str(userId), name=name, createdAtUtc=utc_now())

    def get_client(self, *, clientId: str) -> Client | None:
        row = self._q.get_client(self._database_url, client_id=clientId)
        if row is None:
            return None
        created = row.get("createdAtUtc")
        created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
        return Client(
            clientId=str(row["clientId"]),
            userId=str(row["userId"]),
            name=str(row["name"]),
            createdAtUtc=created_str,
        )

    def create_project(self, *, userId: str, clientId: str, name: str) -> Project:
        owner = self.get_client(clientId=clientId)
        if owner is None or str(owner.userId) != str(userId):
            raise KeyError("CLIENT_NOT_FOUND")
        project_id = self._q.create_project(self._database_url, client_id=clientId, name=name)
        return Project(projectId=project_id, clientId=clientId, name=name, createdAtUtc=utc_now(), status="EMPTY")

    def list_clients(self, *, userId: str) -> list[Client]:
        rows = self._q.list_clients_for_user(self._database_url, user_id=userId)
        out: list[Client] = []
        for r in rows:
            created = r.get("createdAtUtc")
            created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
            out.append(
                Client(
                    clientId=str(r["clientId"]),
                    userId=str(r["userId"]),
                    name=str(r["name"]),
                    createdAtUtc=created_str,
                )
            )
        return out

    def list_projects_for_client(self, *, userId: str, clientId: str) -> list[Project]:
        owner = self.get_client(clientId=clientId)
        if owner is None or str(owner.userId) != str(userId):
            raise KeyError("CLIENT_NOT_FOUND")
        rows = self._q.list_projects_for_client(self._database_url, client_id=clientId)
        out: list[Project] = []
        for r in rows:
            created = r.get("createdAtUtc")
            created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
            project = hydrate_project_ready_status(
                Project(
                    projectId=str(r["projectId"]),
                    clientId=str(r["clientId"]),
                    name=str(r["name"]),
                    status=str(r["status"]),
                    createdAtUtc=created_str,
                )
            )
            if project is not None:
                out.append(project)
        return out

    def set_project_status(self, *, projectId: str, status: str) -> None:
        self._q.set_project_status(self._database_url, project_id=projectId, status=status)

    def get_project(self, *, projectId: str) -> Project | None:
        con = self._db.connect(self._database_url)
        try:
            row = self._db.fetch_one(
                con,
                "select project_id as \"projectId\", client_id as \"clientId\", name, status, created_at_utc as \"createdAtUtc\" from projects where project_id=%s",
                (projectId,),
            )
            if row is None:
                return None
            created = row.get("createdAtUtc")
            created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
            project = Project(
                projectId=str(row["projectId"]),
                clientId=str(row["clientId"]),
                name=str(row["name"]),
                status=str(row["status"]),
                createdAtUtc=created_str,
            )
            before = str(project.status or "")
            hydrated = hydrate_project_ready_status(project)
            if hydrated is not None and str(hydrated.status or "") != before:
                try:
                    self.set_project_status(projectId=projectId, status=str(hydrated.status))
                except Exception:
                    pass
            return hydrated
        finally:
            con.close()

    def _technician_from_row(self, row: dict[str, Any] | None) -> Technician | None:
        if not row:
            return None
        created = row.get("createdAtUtc")
        created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
        return Technician(
            technicianId=str(row["technicianId"]),
            userId=str(row["userId"]),
            name=str(row.get("name") or ""),
            createdAtUtc=created_str,
        )

    def _active_token_from_resolved(self, *, techToken: str, resolved: dict[str, Any]) -> ActiveToken:
        name = str(resolved.get("technicianName") or "").strip() or None
        tid_raw = resolved.get("technicianId")
        tid = str(tid_raw).strip() if tid_raw else None
        return ActiveToken(
            techToken=techToken,
            techLinkId=str(resolved["techLinkId"]),
            projectId=str(resolved["projectId"]),
            technicianId=tid or None,
            technicianName=name,
        )

    def _company_user_id_for_project(self, *, projectId: str) -> str:
        project = self.get_project(projectId=projectId)
        if project is None:
            raise KeyError("PROJECT_NOT_FOUND")
        client = self.get_client(clientId=project.clientId)
        if client is None:
            raise KeyError("CLIENT_NOT_FOUND")
        return str(client.userId)

    def list_technicians(self, *, userId: str) -> list[Technician]:
        rows = self._q.list_technicians_for_user(self._database_url, user_id=userId)
        out: list[Technician] = []
        for row in rows:
            tech = self._technician_from_row(row)
            if tech is not None:
                out.append(tech)
        return out

    def create_technician(self, *, userId: str, name: str) -> Technician:
        row = self._q.create_technician(self._database_url, user_id=userId, name=name)
        tech = self._technician_from_row(row)
        if tech is None:
            raise KeyError("TECHNICIAN_NOT_FOUND")
        return tech

    def get_technician(self, *, technicianId: str) -> Technician | None:
        row = self._q.get_technician(self._database_url, technician_id=technicianId)
        return self._technician_from_row(row)

    def create_tech_link(
        self, *, projectId: str, label: str | None, technicianId: str | None = None
    ) -> tuple[TechLink, ActiveToken]:
        user_id = self._company_user_id_for_project(projectId=projectId)
        tid = str(technicianId or "").strip()
        if tid:
            row = self._q.get_technician(self._database_url, technician_id=tid)
            tech = self._technician_from_row(row)
            if tech is None or str(tech.userId) != str(user_id):
                raise KeyError("TECHNICIAN_NOT_FOUND")
        else:
            tech = self.create_technician(userId=user_id, name=str(label or ""))
        existing = self._q.find_active_tech_link_for_technician(
            self._database_url, project_id=projectId, technician_id=tech.technicianId
        )
        if existing is None:
            existing = self._q.find_active_tech_link_for_name(
                self._database_url, project_id=projectId, name=tech.name
            )
        if existing is not None:
            token_plain = self._q.token_from_issued_path(existing.get("issuedPath"))
            if token_plain:
                created = existing.get("createdAtUtc")
                created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
                issued = existing.get("issuedAtUtc")
                issued_str = issued.isoformat() if hasattr(issued, "isoformat") else (str(issued) if issued else None)
                name = str(existing.get("technicianName") or existing.get("label") or tech.name or "").strip()
                link = TechLink(
                    techLinkId=str(existing["techLinkId"]),
                    projectId=projectId,
                    label=name or tech.name,
                    createdAtUtc=created_str,
                    technicianId=tech.technicianId,
                    issuedPath=str(existing.get("issuedPath") or "").strip() or None,
                    issuedAtUtc=issued_str,
                )
                resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=token_plain)
                token = self._active_token_from_resolved(techToken=token_plain, resolved=resolved)
                token.issuedAtUtc = issued_str
                return link, token
        link_row = self._q.create_tech_link(
            self._database_url,
            project_id=projectId,
            label=tech.name,
            technician_id=tech.technicianId,
        )
        token_row = self._q.rotate_tech_link_token(self._database_url, tech_link_id=link_row["techLinkId"], project_id=projectId)
        created = link_row.get("createdAtUtc")
        created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
        link = TechLink(
            techLinkId=link_row["techLinkId"],
            projectId=projectId,
            label=tech.name,
            createdAtUtc=created_str,
            technicianId=tech.technicianId,
        )
        resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=token_row["techToken"])
        token = self._active_token_from_resolved(techToken=token_row["techToken"], resolved=resolved)
        return link, token

    def rotate_tech_link_token(self, *, projectId: str, techLinkId: str) -> ActiveToken:
        token_row = self._q.rotate_tech_link_token(self._database_url, tech_link_id=techLinkId, project_id=projectId)
        resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=token_row["techToken"])
        if str(resolved["projectId"]) != str(projectId):
            raise KeyError("TECH_LINK_NOT_FOUND")
        return self._active_token_from_resolved(techToken=token_row["techToken"], resolved=resolved)

    def list_active_tech_links(self, *, projectId: str) -> list[TechLink]:
        rows = self._q.list_active_tech_links(self._database_url, project_id=projectId)
        out: list[TechLink] = []
        for r in rows:
            created = r.get("createdAtUtc")
            created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
            name = str(r.get("technicianName") or r.get("label") or "").strip() or None
            tid_raw = r.get("technicianId")
            tid = str(tid_raw).strip() if tid_raw else None
            issued = r.get("issuedAtUtc")
            issued_str = issued.isoformat() if hasattr(issued, "isoformat") else (str(issued) if issued else None)
            issued_path = str(r.get("issuedPath") or "").strip() or None
            out.append(
                TechLink(
                    techLinkId=str(r["techLinkId"]),
                    projectId=projectId,
                    label=name or r.get("label"),
                    createdAtUtc=created_str,
                    technicianId=tid or None,
                    issuedPath=issued_path,
                    issuedAtUtc=issued_str,
                )
            )
        return out

    def revoke_tech_link(self, *, projectId: str, techLinkId: str) -> None:
        self._q.revoke_tech_link_tokens(self._database_url, project_id=projectId, tech_link_id=techLinkId)

    def resolve_active_token(self, *, techToken: str) -> ActiveToken:
        resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=techToken)
        return self._active_token_from_resolved(techToken=techToken, resolved=resolved)

    def record_upload(self, *, projectId: str, uploadId: str, originalFilename: str, storagePath: str) -> UploadRecord:
        self._q.upsert_upload_record(
            self._database_url,
            project_id=projectId,
            upload_id=uploadId,
            original_filename=originalFilename,
            storage_path=storagePath,
        )
        row = self._q.get_project_active_upload(self._database_url, project_id=projectId)
        if row and str(row.get("uploadId") or "") == str(uploadId):
            uploaded_at = row.get("uploadedAtUtc")
            uploaded_at_str = uploaded_at.isoformat() if hasattr(uploaded_at, "isoformat") else str(uploaded_at)
            return UploadRecord(
                uploadId=str(row["uploadId"]),
                projectId=str(row["projectId"]),
                originalFilename=str(row["originalFilename"]),
                storagePath=str(row["storagePath"]),
                uploadedAtUtc=uploaded_at_str,
            )
        return UploadRecord(
            uploadId=uploadId,
            projectId=projectId,
            originalFilename=originalFilename,
            storagePath=storagePath,
            uploadedAtUtc=utc_now(),
        )

    def set_project_active_upload(self, *, projectId: str, uploadId: str) -> None:
        self._q.set_project_active_upload(self._database_url, project_id=projectId, upload_id=uploadId)

    def get_project_active_upload(self, *, projectId: str) -> UploadRecord | None:
        row = self._q.get_project_active_upload(self._database_url, project_id=projectId)
        if not row or not row.get("uploadId"):
            return None
        uploaded_at = row.get("uploadedAtUtc")
        uploaded_at_str = uploaded_at.isoformat() if hasattr(uploaded_at, "isoformat") else str(uploaded_at)
        return UploadRecord(
            uploadId=str(row["uploadId"]),
            projectId=str(row["projectId"]),
            originalFilename=str(row["originalFilename"]),
            storagePath=str(row["storagePath"]),
            uploadedAtUtc=uploaded_at_str,
        )

    def list_uploads_for_project(self, *, projectId: str) -> list[UploadRecord]:
        rows = self._q.list_uploads_for_project(self._database_url, project_id=projectId)
        out: list[UploadRecord] = []
        for row in rows:
            uploaded_at = row.get("uploadedAtUtc")
            uploaded_at_str = uploaded_at.isoformat() if hasattr(uploaded_at, "isoformat") else str(uploaded_at)
            out.append(
                UploadRecord(
                    uploadId=str(row["uploadId"]),
                    projectId=str(row["projectId"]),
                    originalFilename=str(row["originalFilename"]),
                    storagePath=str(row["storagePath"]),
                    uploadedAtUtc=uploaded_at_str,
                )
            )
        return out

    def prune_project_upload_retention(self, *, projectId: str, activeUploadId: str, activeStoragePath: str) -> None:
        from sentinel.server.services import pipeline

        self._q.prune_project_uploads_keep_latest_two(self._database_url, project_id=projectId)
        keep_path = Path(activeStoragePath).resolve()
        pipeline.prune_project_upload_dir_to_single_file(projectId=projectId, keep_path=keep_path)

    def append_test_result(
        self,
        *,
        techToken: str,
        target: dict[str, Any],
        outcome: str,
        failNote: str | None,
    ) -> TestResultRecord:
        tok = self.resolve_active_token(techToken=techToken)
        generation_run_id = self._q.ensure_generation_run(self._database_url, project_id=tok.projectId)

        test_result_id = self._q.append_test_result(
            self._database_url,
            project_id=tok.projectId,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tok.techLinkId,
            recorded_by_technician_id=tok.technicianId,
            recorded_by_technician_name=str(tok.technicianName or "").strip() or None,
            target_key=str(target.get("targetKey") or ""),
            target_kind=str(target.get("kind") or target.get("targetKind") or ""),
            target_name=str(target.get("targetName") or ""),
            refs=dict(target.get("refs") or {}),
            outcome=outcome,
            fail_note=failNote,
            batch_id=None,
            source=TEST_RESULT_SOURCE_SINGLE,
        )

        return TestResultRecord(
            testResultId=str(test_result_id),
            projectId=tok.projectId,
            recordedAtUtc=utc_now(),
            recordedBy=recorded_by_from_token(tok),
            target=target,
            outcome=outcome,
            failNote=failNote,
            batchId=None,
            source=TEST_RESULT_SOURCE_SINGLE,
        )

    def append_test_results_batch(
        self,
        *,
        techToken: str,
        items: list[dict[str, Any]],
        outcome: str,
    ) -> list[TestResultRecord]:
        tok = self.resolve_active_token(techToken=techToken)
        generation_run_id = self._q.ensure_generation_run(self._database_url, project_id=tok.projectId)
        batch_id = new_uuid()
        rows = self._q.append_test_results_batch(
            self._database_url,
            project_id=tok.projectId,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tok.techLinkId,
            recorded_by_technician_id=tok.technicianId,
            recorded_by_technician_name=str(tok.technicianName or "").strip() or None,
            outcome=outcome,
            batch_id=batch_id,
            source=TEST_RESULT_SOURCE_GROUP,
            items=[
                {
                    "target_key": str((item.get("target") or {}).get("targetKey") or ""),
                    "target_kind": str(
                        (item.get("target") or {}).get("kind") or (item.get("target") or {}).get("targetKind") or ""
                    ),
                    "target_name": str((item.get("target") or {}).get("targetName") or ""),
                    "refs": dict((item.get("target") or {}).get("refs") or {}),
                    "fail_note": item.get("failNote"),
                }
                for item in items
            ],
        )
        ts = utc_now()
        recs: list[TestResultRecord] = []
        for row, item in zip(rows, items):
            recorded = row.get("recordedAtUtc")
            if hasattr(recorded, "isoformat"):
                recorded_str = recorded.isoformat()
            elif recorded:
                recorded_str = str(recorded)
            else:
                recorded_str = ts
            row_batch = row.get("batchId")
            recs.append(
                TestResultRecord(
                    testResultId=str(row.get("testResultId") or ""),
                    projectId=tok.projectId,
                    recordedAtUtc=recorded_str,
                    recordedBy=recorded_by_from_token(tok),
                    target=dict(item.get("target") or {}),
                    outcome=outcome,
                    failNote=item.get("failNote"),
                    batchId=str(row_batch).strip() if row_batch else batch_id,
                    source=str(row.get("source") or TEST_RESULT_SOURCE_GROUP),
                )
            )
        return recs

    def get_target_status(self, *, techToken: str, targetKey: str) -> dict[str, Any]:
        tok = self.resolve_active_token(techToken=techToken)
        return self._q.get_target_status(self._database_url, project_id=tok.projectId, target_key=targetKey)

    def get_latest_results_for_project(self, *, projectId: str) -> dict[str, TestResultRecord]:
        con = self._db.connect(self._database_url)
        try:
            rows = self._db.fetch_all(
                con,
                "select distinct on (target_key) "
                "test_result_id as \"testResultId\", "
                "target_key as \"targetKey\", target_kind as \"targetKind\", target_name as \"targetName\", refs as \"refs\", "
                "outcome, fail_note as \"failNote\", recorded_at_utc as \"recordedAtUtc\", recorded_by_role as \"recordedByRole\", "
                "recorded_by_tech_link_id as \"recordedByTechLinkId\", "
                "recorded_by_technician_id as \"recordedByTechnicianId\", "
                "recorded_by_technician_name as \"recordedByTechnicianName\", "
                "batch_id as \"batchId\", source as \"source\" "
                "from test_results where project_id=%s "
                "and recorded_at_utc >= coalesce("
                "(select max(started_at_utc) from project_test_passes where project_id=%s), "
                "'-infinity'::timestamptz) "
                "order by target_key, recorded_at_utc desc, test_result_id desc",
                (projectId, projectId),
            )
            out: dict[str, TestResultRecord] = {}
            for r in rows:
                target_key = str(r["targetKey"])
                created = r.get("recordedAtUtc")
                created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
                refs_val = r.get("refs") or {}
                if isinstance(refs_val, str):
                    try:
                        import json as _json

                        refs_val = _json.loads(refs_val)
                    except Exception:
                        refs_val = {}
                target = {"targetKey": target_key, "kind": str(r.get("targetKind") or ""), "refs": refs_val, "targetName": str(r.get("targetName") or "")}
                recorded_by = {
                    "role": str(r.get("recordedByRole") or ""),
                    "techLinkId": r.get("recordedByTechLinkId"),
                    "technicianId": r.get("recordedByTechnicianId"),
                    "name": str(r.get("recordedByTechnicianName") or "").strip(),
                }
                batch_raw = r.get("batchId")
                batch_id = str(batch_raw).strip() if batch_raw else None
                source_raw = str(r.get("source") or "").strip().upper()
                out[target_key] = TestResultRecord(
                    testResultId=str(r.get("testResultId") or new_uuid()),
                    projectId=projectId,
                    recordedAtUtc=created_str,
                    recordedBy=recorded_by,
                    target=target,
                    outcome=str(r.get("outcome") or ""),
                    failNote=r.get("failNote"),
                    batchId=batch_id or None,
                    source=source_raw or (TEST_RESULT_SOURCE_GROUP if batch_id else TEST_RESULT_SOURCE_SINGLE),
                )
            return out
        finally:
            con.close()

    def _result_from_row(self, *, projectId: str, row: dict[str, Any]) -> TestResultRecord:
        created = row.get("recordedAtUtc")
        created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
        refs_val = row.get("refs") or {}
        if isinstance(refs_val, str):
            try:
                import json as _json

                refs_val = _json.loads(refs_val)
            except Exception:
                refs_val = {}
        batch_raw = row.get("batchId")
        batch_id = str(batch_raw).strip() if batch_raw else None
        source_raw = str(row.get("source") or "").strip().upper()
        return TestResultRecord(
            testResultId=str(row.get("testResultId") or new_uuid()),
            projectId=projectId,
            recordedAtUtc=created_str,
            recordedBy={
                "role": str(row.get("recordedByRole") or ""),
                "techLinkId": row.get("recordedByTechLinkId"),
                "technicianId": row.get("recordedByTechnicianId"),
                "name": str(row.get("recordedByTechnicianName") or "").strip(),
            },
            target={
                "targetKey": str(row.get("targetKey") or ""),
                "kind": str(row.get("targetKind") or ""),
                "refs": refs_val,
                "targetName": str(row.get("targetName") or ""),
            },
            outcome=str(row.get("outcome") or ""),
            failNote=row.get("failNote"),
            batchId=batch_id or None,
            source=source_raw or (TEST_RESULT_SOURCE_GROUP if batch_id else TEST_RESULT_SOURCE_SINGLE),
        )

    def list_test_results_for_project(self, *, projectId: str) -> list[TestResultRecord]:
        rows = self._q.list_test_results_for_project(self._database_url, project_id=projectId)
        return [self._result_from_row(projectId=projectId, row=r) for r in rows]

    def get_current_test_pass_started_at(self, *, projectId: str) -> str | None:
        return self._q.current_test_pass_started_at(self._database_url, project_id=projectId)

    def start_project_test_pass(
        self,
        *,
        projectId: str,
        recordedBy: dict[str, Any],
        reason: str | None = None,
        confirmName: str | None = None,
    ) -> dict[str, Any]:
        if self.get_project(projectId=projectId) is None:
            raise KeyError("PROJECT_NOT_FOUND")
        return self._q.start_project_test_pass(
            self._database_url,
            project_id=projectId,
            recorded_by_role=str((recordedBy or {}).get("role") or "PROGRAMMER"),
            recorded_by_user_id=str((recordedBy or {}).get("userId") or "") or None,
            reason=str(reason).strip() if reason else None,
            confirm_name=str(confirmName).strip() if confirmName else None,
        )

    def list_fail_tag_history_for_project(self, *, projectId: str) -> list[dict[str, Any]]:
        return self._q.list_fail_tag_history_for_project(self._database_url, project_id=projectId)

    def set_fail_tag(self, *, projectId: str, targetKey: str, tag: str) -> None:
        self._q.upsert_fail_tag(self._database_url, project_id=projectId, target_key=targetKey, tag=tag)

    def get_fail_tags_for_project(self, *, projectId: str) -> dict[str, str]:
        rows = self._q.list_fail_tags_for_project(self._database_url, project_id=projectId)
        out: dict[str, str] = {}
        for r in rows:
            out[str(r.get("targetKey") or "")] = str(r.get("tag") or "")
        return out

    def get_fail_tag_updated_at_for_project(self, *, projectId: str) -> dict[str, str]:
        rows = self._q.list_fail_tags_for_project(self._database_url, project_id=projectId)
        out: dict[str, str] = {}
        for r in rows:
            key = str(r.get("targetKey") or "")
            at = str(r.get("updatedAtUtc") or "").strip()
            if key and at:
                out[key] = at
        return out

    def set_layer_lock_state(self, *, projectId: str, scopeKey: str, layerKey: str, visible: bool, locked: bool) -> None:
        self._q.upsert_layer_lock_state(
            self._database_url,
            project_id=projectId,
            scope_key=str(scopeKey),
            layer_key=str(layerKey),
            visible=bool(visible),
            locked=bool(locked),
        )

    def list_layer_lock_states_for_project(self, *, projectId: str, scopeKey: str | None = None) -> list[dict[str, Any]]:
        rows = self._q.list_layer_lock_states_for_project(self._database_url, project_id=projectId, scope_key=scopeKey)
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "scopeKey": str(r.get("scopeKey") or ""),
                    "layerKey": str(r.get("layerKey") or ""),
                    "visible": bool(r.get("visible")),
                    "locked": bool(r.get("locked")),
                    "updatedAtUtc": str(r.get("updatedAtUtc") or ""),
                }
            )
        return out

    def count_first_time_fail_targets(self, *, projectId: str) -> int:
        return int(self._q.count_first_time_fail_targets(self._database_url, project_id=projectId))

    def get_tech_link_label(self, *, techLinkId: str) -> str | None:
        label = self._q.get_tech_link_label(self._database_url, tech_link_id=techLinkId)
        s = str(label or "").strip()
        return s or None

    def clear_project_testing_data(self, *, projectId: str) -> None:
        self._q.clear_project_testing_data(self._database_url, project_id=projectId)

    def get_idempotency_response(self, *, scope: str, key: str) -> dict[str, Any] | None:
        return self._q.get_idempotency_response(self._database_url, scope=str(scope), idempotency_key=str(key))

    def put_idempotency_response(self, *, scope: str, key: str, response: dict[str, Any]) -> None:
        self._q.put_idempotency_response(self._database_url, scope=str(scope), idempotency_key=str(key), response=response)

    def get_testing_type_disabled(self, *, projectId: str) -> list[str]:
        if self.get_project(projectId=projectId) is None:
            raise KeyError("PROJECT_NOT_FOUND")
        return self._q.get_testing_type_disabled(self._database_url, project_id=projectId)

    def set_testing_type_disabled(self, *, projectId: str, disabledTypes: list[str]) -> list[str]:
        if self.get_project(projectId=projectId) is None:
            raise KeyError("PROJECT_NOT_FOUND")
        return self._q.set_testing_type_disabled(
            self._database_url, project_id=projectId, disabled_types=disabledTypes
        )

