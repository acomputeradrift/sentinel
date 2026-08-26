from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sentinel.server.services.test_result_source import (
    TEST_RESULT_BATCH_MAX,
    TEST_RESULT_SOURCES,
    normalize_source_detail,
    normalize_test_result_source,
)

__all__ = [
    "TEST_RESULT_BATCH_MAX",
    "TEST_RESULT_SOURCES",
    "normalize_source_detail",
    "normalize_test_result_source",
    "TestResultTargetIn",
    "PostTestResultBody",
    "PostTestResultBatchBody",
    "PostReadyBaselineBody",
]



class TestResultTargetIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    targetKey: str = Field(min_length=1)
    kind: str | None = None
    targetKind: str | None = None
    targetName: str | None = None
    refs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("targetKey")
    @classmethod
    def strip_target_key(cls, v: str) -> str:
        s = str(v or "").strip()
        if not s:
            raise ValueError("targetKey is required")
        return s


class PostTestResultBody(BaseModel):
    target: TestResultTargetIn
    outcome: str = Field(min_length=1)
    failNote: str | None = None
    source: str | None = None
    sourceDetail: dict[str, Any] | None = None

    @field_validator("outcome")
    @classmethod
    def normalize_outcome(cls, v: str) -> str:
        u = str(v or "").strip().upper()
        if u not in ("PASS", "FAIL", "UNTESTED"):
            raise ValueError("outcome must be PASS, FAIL, or UNTESTED")
        return u

    @field_validator("source")
    @classmethod
    def normalize_source_field(cls, v: str | None) -> str:
        return normalize_test_result_source(v)

    @field_validator("sourceDetail")
    @classmethod
    def normalize_detail_field(cls, v: dict[str, Any] | None) -> dict[str, Any]:
        return normalize_source_detail(v)

    def fail_note_normalized(self) -> str | None:
        if self.failNote is None:
            return None
        s = str(self.failNote).strip()
        return s or None

    def source_normalized(self) -> str:
        return normalize_test_result_source(self.source)

    def source_detail_normalized(self) -> dict[str, Any]:
        return normalize_source_detail(self.sourceDetail)


class PostTestResultBatchBody(BaseModel):
    results: list[PostTestResultBody] = Field(min_length=1, max_length=TEST_RESULT_BATCH_MAX)


class PostReadyBaselineBody(BaseModel):
    readySec: float = Field(ge=0)

    @field_validator("readySec", mode="before")
    @classmethod
    def coerce_ready(cls, v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError) as e:
            raise ValueError("readySec must be a number") from e
