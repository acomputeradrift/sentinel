from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from typing import Any, Protocol
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid4())


def new_token() -> str:
    return uuid4().hex


@dataclass(frozen=True)
class Client:
    clientId: str
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
class TechLink:
    techLinkId: str
    projectId: str
    label: str | None
    createdAtUtc: str


@dataclass
class ActiveToken:
    techToken: str
    techLinkId: str
    projectId: str


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


class Repository(Protocol):
    def create_client(self, *, name: str) -> Client: ...

    def create_project(self, *, clientId: str, name: str) -> Project: ...

    def list_clients(self) -> list[Client]: ...

    def list_projects_for_client(self, *, clientId: str) -> list[Project]: ...

    def get_project(self, *, projectId: str) -> Project | None: ...

    def create_tech_link(self, *, projectId: str, label: str | None) -> tuple[TechLink, ActiveToken]: ...

    def rotate_tech_link_token(self, *, projectId: str, techLinkId: str) -> ActiveToken: ...

    def list_active_tech_links(self, *, projectId: str) -> list[TechLink]: ...

    def revoke_tech_link(self, *, projectId: str, techLinkId: str) -> None: ...

    def resolve_active_token(self, *, techToken: str) -> ActiveToken: ...

    def record_upload(self, *, projectId: str, uploadId: str, originalFilename: str, storagePath: str) -> UploadRecord: ...

    def set_project_active_upload(self, *, projectId: str, uploadId: str) -> None: ...

    def get_project_active_upload(self, *, projectId: str) -> UploadRecord | None: ...

    def append_test_result(
        self,
        *,
        techToken: str,
        target: dict[str, Any],
        outcome: str,
        failNote: str | None,
    ) -> TestResultRecord: ...

    def get_target_status(self, *, techToken: str, targetKey: str) -> dict[str, Any]: ...

    def get_latest_results_for_project(self, *, projectId: str) -> dict[str, TestResultRecord]: ...

    def set_fail_tag(self, *, projectId: str, targetKey: str, tag: str) -> None: ...

    def get_fail_tags_for_project(self, *, projectId: str) -> dict[str, str]: ...

    def count_first_time_fail_targets(self, *, projectId: str) -> int: ...


class InMemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, Client] = {}
        self._projects: dict[str, Project] = {}
        self._tech_links: dict[str, TechLink] = {}
        self._active_tokens: dict[str, ActiveToken] = {}
        self._active_token_by_link: dict[str, str] = {}
        self._uploads: dict[str, UploadRecord] = {}
        self._active_upload_by_project: dict[str, str] = {}
        self._results_by_project_target: dict[tuple[str, str], list[TestResultRecord]] = {}
        self._fail_tags_by_project_target: dict[tuple[str, str], str] = {}

    @staticmethod
    def _latest_record(items: list[TestResultRecord]) -> TestResultRecord | None:
        if not items:
            return None
        # Deterministic "latest" selection:
        # - primary: recordedAtUtc
        # - tie-break: testResultId (lexicographic)
        return max(items, key=lambda r: (r.recordedAtUtc, r.testResultId))

    @staticmethod
    def _earliest_record(items: list[TestResultRecord]) -> TestResultRecord | None:
        if not items:
            return None
        return min(items, key=lambda r: (r.recordedAtUtc, r.testResultId))

    def create_client(self, *, name: str) -> Client:
        with self._lock:
            wanted = str(name).strip().casefold()
            for existing in self._clients.values():
                if str(existing.name).strip().casefold() == wanted:
                    raise KeyError("CLIENT_EXISTS")
            client = Client(clientId=new_uuid(), name=name, createdAtUtc=utc_now())
            self._clients[client.clientId] = client
            return client

    def create_project(self, *, clientId: str, name: str) -> Project:
        with self._lock:
            project = Project(projectId=new_uuid(), clientId=clientId, name=name, createdAtUtc=utc_now(), status="EMPTY")
            self._projects[project.projectId] = project
            return project

    def list_clients(self) -> list[Client]:
        with self._lock:
            return list(self._clients.values())

    def list_projects_for_client(self, *, clientId: str) -> list[Project]:
        with self._lock:
            if clientId not in self._clients:
                raise KeyError("CLIENT_NOT_FOUND")
            return [p for p in self._projects.values() if p.clientId == clientId]

    def get_project(self, *, projectId: str) -> Project | None:
        with self._lock:
            return self._projects.get(projectId)

    def create_tech_link(self, *, projectId: str, label: str | None) -> tuple[TechLink, ActiveToken]:
        with self._lock:
            if projectId not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            link = TechLink(techLinkId=new_uuid(), projectId=projectId, label=label, createdAtUtc=utc_now())
            self._tech_links[link.techLinkId] = link
            token = self._issue_token_locked(projectId=projectId, techLinkId=link.techLinkId)
            return link, token

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
                if link.techLinkId not in self._active_token_by_link:
                    continue
                out.append(link)
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

    def _issue_token_locked(self, *, projectId: str, techLinkId: str) -> ActiveToken:
        techToken = new_token()
        token = ActiveToken(techToken=techToken, techLinkId=techLinkId, projectId=projectId)
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

    def append_test_result(
        self,
        *,
        techToken: str,
        target: dict[str, Any],
        outcome: str,
        failNote: str | None,
    ) -> TestResultRecord:
        tok = self.resolve_active_token(techToken=techToken)
        rec = TestResultRecord(
            testResultId=new_uuid(),
            projectId=tok.projectId,
            recordedAtUtc=utc_now(),
            recordedBy={"role": "TECHNICIAN", "techLinkId": tok.techLinkId},
            target=target,
            outcome=outcome,
            failNote=failNote,
        )
        with self._lock:
            key = (tok.projectId, str(target.get("targetKey") or ""))
            self._results_by_project_target.setdefault(key, []).append(rec)
        return rec

    def get_target_status(self, *, techToken: str, targetKey: str) -> dict[str, Any]:
        tok = self.resolve_active_token(techToken=techToken)
        with self._lock:
            key = (tok.projectId, targetKey)
            items = self._results_by_project_target.get(key, [])
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
                last = self._latest_record(items)
                if last is not None:
                    out[target_key] = last
            return out

    def set_fail_tag(self, *, projectId: str, targetKey: str, tag: str) -> None:
        with self._lock:
            if projectId not in self._projects:
                raise KeyError("PROJECT_NOT_FOUND")
            self._fail_tags_by_project_target[(projectId, targetKey)] = tag

    def get_fail_tags_for_project(self, *, projectId: str) -> dict[str, str]:
        with self._lock:
            out: dict[str, str] = {}
            for (pid, target_key), tag in self._fail_tags_by_project_target.items():
                if pid == projectId:
                    out[target_key] = tag
            return out

    def count_first_time_fail_targets(self, *, projectId: str) -> int:
        with self._lock:
            count = 0
            for (pid, _target_key), items in self._results_by_project_target.items():
                if pid != projectId or not items:
                    continue
                first = self._earliest_record(items)
                if first is not None and first.outcome == "FAIL":
                    count += 1
            return count


class PostgresRepository:
    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url
        from sentinel.server.persistence import db as persistence_db  # local import to avoid hard dependency in in-memory mode
        from sentinel.server.persistence import queries as persistence_queries

        self._db = persistence_db
        self._q = persistence_queries
        self._db.apply_migrations(database_url)

    def create_client(self, *, name: str) -> Client:
        try:
            client_id = self._q.create_client(self._database_url, name=name)
        except self._q.DuplicateClientNameError as e:
            raise KeyError("CLIENT_EXISTS") from e
        return Client(clientId=client_id, name=name, createdAtUtc=utc_now())

    def create_project(self, *, clientId: str, name: str) -> Project:
        project_id = self._q.create_project(self._database_url, client_id=clientId, name=name)
        return Project(projectId=project_id, clientId=clientId, name=name, createdAtUtc=utc_now(), status="EMPTY")

    def list_clients(self) -> list[Client]:
        rows = self._q.list_clients(self._database_url)
        out: list[Client] = []
        for r in rows:
            created = r.get("createdAtUtc")
            created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
            out.append(Client(clientId=str(r["clientId"]), name=str(r["name"]), createdAtUtc=created_str))
        return out

    def list_projects_for_client(self, *, clientId: str) -> list[Project]:
        con = self._db.connect(self._database_url)
        try:
            exists = self._db.fetch_one(con, "select client_id as \"clientId\" from clients where client_id=%s", (clientId,))
            if exists is None:
                raise KeyError("CLIENT_NOT_FOUND")
        finally:
            con.close()
        rows = self._q.list_projects_for_client(self._database_url, client_id=clientId)
        out: list[Project] = []
        for r in rows:
            created = r.get("createdAtUtc")
            created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
            out.append(Project(projectId=str(r["projectId"]), clientId=str(r["clientId"]), name=str(r["name"]), status=str(r["status"]), createdAtUtc=created_str))
        return out

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
            return Project(projectId=str(row["projectId"]), clientId=str(row["clientId"]), name=str(row["name"]), status=str(row["status"]), createdAtUtc=created_str)
        finally:
            con.close()

    def create_tech_link(self, *, projectId: str, label: str | None) -> tuple[TechLink, ActiveToken]:
        link_row = self._q.create_tech_link(self._database_url, project_id=projectId, label=label)
        token_row = self._q.rotate_tech_link_token(self._database_url, tech_link_id=link_row["techLinkId"], project_id=projectId)
        created = link_row.get("createdAtUtc")
        created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
        link = TechLink(techLinkId=link_row["techLinkId"], projectId=projectId, label=label, createdAtUtc=created_str)
        token = ActiveToken(techToken=token_row["techToken"], techLinkId=link.techLinkId, projectId=projectId)
        return link, token

    def rotate_tech_link_token(self, *, projectId: str, techLinkId: str) -> ActiveToken:
        token_row = self._q.rotate_tech_link_token(self._database_url, tech_link_id=techLinkId, project_id=projectId)
        # Validate token is tied to the expected project by resolving it.
        resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=token_row["techToken"])
        if str(resolved["projectId"]) != str(projectId):
            raise KeyError("TECH_LINK_NOT_FOUND")
        return ActiveToken(techToken=token_row["techToken"], techLinkId=resolved["techLinkId"], projectId=resolved["projectId"])

    def list_active_tech_links(self, *, projectId: str) -> list[TechLink]:
        rows = self._q.list_active_tech_links(self._database_url, project_id=projectId)
        out: list[TechLink] = []
        for r in rows:
            created = r.get("createdAtUtc")
            created_str = created.isoformat() if hasattr(created, "isoformat") else str(created)
            out.append(TechLink(techLinkId=str(r["techLinkId"]), projectId=projectId, label=r.get("label"), createdAtUtc=created_str))
        return out

    def revoke_tech_link(self, *, projectId: str, techLinkId: str) -> None:
        self._q.revoke_tech_link_tokens(self._database_url, project_id=projectId, tech_link_id=techLinkId)

    def resolve_active_token(self, *, techToken: str) -> ActiveToken:
        resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=techToken)
        return ActiveToken(techToken=techToken, techLinkId=resolved["techLinkId"], projectId=resolved["projectId"])

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

        self._q.append_test_result(
            self._database_url,
            project_id=tok.projectId,
            generation_run_id=generation_run_id,
            recorded_by_tech_link_id=tok.techLinkId,
            target_key=str(target.get("targetKey") or ""),
            target_kind=str(target.get("kind") or target.get("targetKind") or ""),
            target_name=str(target.get("targetName") or ""),
            refs=dict(target.get("refs") or {}),
            outcome=outcome,
            fail_note=failNote,
        )

        return TestResultRecord(
            testResultId=new_uuid(),
            projectId=tok.projectId,
            recordedAtUtc=utc_now(),
            recordedBy={"role": "TECHNICIAN", "techLinkId": tok.techLinkId},
            target=target,
            outcome=outcome,
            failNote=failNote,
        )

    def get_target_status(self, *, techToken: str, targetKey: str) -> dict[str, Any]:
        tok = self.resolve_active_token(techToken=techToken)
        return self._q.get_target_status(self._database_url, project_id=tok.projectId, target_key=targetKey)

    def get_latest_results_for_project(self, *, projectId: str) -> dict[str, TestResultRecord]:
        con = self._db.connect(self._database_url)
        try:
            rows = self._db.fetch_all(
                con,
                "select distinct on (target_key) "
                "target_key as \"targetKey\", target_kind as \"targetKind\", target_name as \"targetName\", refs as \"refs\", "
                "outcome, fail_note as \"failNote\", recorded_at_utc as \"recordedAtUtc\", recorded_by_role as \"recordedByRole\", recorded_by_tech_link_id as \"recordedByTechLinkId\" "
                "from test_results where project_id=%s order by target_key, recorded_at_utc desc, test_result_id desc",
                (projectId,),
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
                recorded_by = {"role": str(r.get("recordedByRole") or ""), "techLinkId": r.get("recordedByTechLinkId")}
                out[target_key] = TestResultRecord(
                    testResultId=new_uuid(),
                    projectId=projectId,
                    recordedAtUtc=created_str,
                    recordedBy=recorded_by,
                    target=target,
                    outcome=str(r.get("outcome") or ""),
                    failNote=r.get("failNote"),
                )
            return out
        finally:
            con.close()

    def set_fail_tag(self, *, projectId: str, targetKey: str, tag: str) -> None:
        self._q.upsert_fail_tag(self._database_url, project_id=projectId, target_key=targetKey, tag=tag)

    def get_fail_tags_for_project(self, *, projectId: str) -> dict[str, str]:
        rows = self._q.list_fail_tags_for_project(self._database_url, project_id=projectId)
        out: dict[str, str] = {}
        for r in rows:
            out[str(r.get("targetKey") or "")] = str(r.get("tag") or "")
        return out

    def count_first_time_fail_targets(self, *, projectId: str) -> int:
        return int(self._q.count_first_time_fail_targets(self._database_url, project_id=projectId))

