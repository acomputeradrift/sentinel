from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("outcome")
    @classmethod
    def normalize_outcome(cls, v: str) -> str:
        u = str(v or "").strip().upper()
        if u not in ("PASS", "FAIL"):
            raise ValueError("outcome must be PASS or FAIL")
        return u

    def fail_note_normalized(self) -> str | None:
        if self.failNote is None:
            return None
        s = str(self.failNote).strip()
        return s or None


class PostReadyBaselineBody(BaseModel):
    readySec: float = Field(ge=0)

    @field_validator("readySec", mode="before")
    @classmethod
    def coerce_ready(cls, v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError) as e:
            raise ValueError("readySec must be a number") from e
