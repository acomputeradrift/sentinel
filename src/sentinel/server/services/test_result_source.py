from __future__ import annotations

from typing import Any

TEST_RESULT_SOURCES = ("INDIVIDUAL", "BUTTON_PASS_ALL", "SELECTION_PASS_ALL")
TEST_RESULT_BATCH_MAX = 4000


def normalize_test_result_source(raw: Any) -> str:
    s = str(raw or "").strip().upper()
    if not s:
        return "INDIVIDUAL"
    if s not in TEST_RESULT_SOURCES:
        raise ValueError("source must be INDIVIDUAL, BUTTON_PASS_ALL, or SELECTION_PASS_ALL")
    return s


def normalize_source_detail(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    return {}
