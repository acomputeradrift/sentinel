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


@dataclass
class ActiveToken:
    techToken: str
    techLinkId: str
    projectId: str


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

    def resolve_active_token(self, *, techToken: str) -> ActiveToken: ...

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


class InMemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._clients: dict[str, Client] = {}
        self._projects: dict[str, Project] = {}
        self._tech_links: dict[str, TechLink] = {}
        self._active_tokens: dict[str, ActiveToken] = {}
        self._active_token_by_link: dict[str, str] = {}
        self._results_by_project_target: dict[tuple[str, str], list[TestResultRecord]] = {}

    def create_client(self, *, name: str) -> Client:
        with self._lock:
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
            link = TechLink(techLinkId=new_uuid(), projectId=projectId, label=label)
            self._tech_links[link.techLinkId] = link
            token = self._issue_token_locked(projectId=projectId, techLinkId=link.techLinkId)
            return link, token

    def rotate_tech_link_token(self, *, projectId: str, techLinkId: str) -> ActiveToken:
        with self._lock:
            # revoke old token for this link (remove mapping)
            old = self._active_token_by_link.get(techLinkId)
            if old is not None:
                self._active_tokens.pop(old, None)
            return self._issue_token_locked(projectId=projectId, techLinkId=techLinkId)

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
            if not items:
                return {"targetKey": targetKey, "currentOutcome": "UNTESTED", "lastTestedAtUtc": None, "lastFailNote": None}
            last = items[-1]
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
                out[target_key] = items[-1]
            return out


class PostgresRepository:
    def __init__(self, *, database_url: str) -> None:
        self._database_url = database_url
        from sentinel.server.persistence import db as persistence_db  # local import to avoid hard dependency in in-memory mode
        from sentinel.server.persistence import queries as persistence_queries

        self._db = persistence_db
        self._q = persistence_queries
        self._db.apply_migrations(database_url)

    def create_client(self, *, name: str) -> Client:
        client_id = self._q.create_client(self._database_url, name=name)
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
        token_row = self._q.rotate_tech_link_token(self._database_url, tech_link_id=link_row["techLinkId"])
        link = TechLink(techLinkId=link_row["techLinkId"], projectId=projectId, label=label)
        token = ActiveToken(techToken=token_row["techToken"], techLinkId=link.techLinkId, projectId=projectId)
        return link, token

    def rotate_tech_link_token(self, *, projectId: str, techLinkId: str) -> ActiveToken:  # noqa: ARG002
        token_row = self._q.rotate_tech_link_token(self._database_url, tech_link_id=techLinkId)
        # Validate token is tied to the expected project by resolving it.
        resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=token_row["techToken"])
        return ActiveToken(techToken=token_row["techToken"], techLinkId=resolved["techLinkId"], projectId=resolved["projectId"])

    def resolve_active_token(self, *, techToken: str) -> ActiveToken:
        resolved = self._q.resolve_active_tech_token(self._database_url, tech_token=techToken)
        return ActiveToken(techToken=techToken, techLinkId=resolved["techLinkId"], projectId=resolved["projectId"])

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

