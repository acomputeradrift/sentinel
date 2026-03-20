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

