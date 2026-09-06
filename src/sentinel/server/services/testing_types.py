"""Canonical testing-target types and per-project on/off filtering.

Off means exclude from the required/progress set (not auto-pass). Controls still
render on generated technician pages; they are not work in pies or group select.
Popups still open and show "{type} are not included in testing".

Type ids are namespaced by family because the same extracted label can appear on
buttons and on events (System Macro, Macro Step).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class TestingType:
    id: str
    label: str
    family: str
    graphics: bool = False


_BUTTON_LABELS: tuple[str, ...] = (
    "Text",
    "System Macro",
    "Macro Step",
    "Variable - Text",
    "Variable - Reversed",
    "Variable - Inactive",
    "Variable - Visible",
    "Variable - Value",
    "Variable - State",
    "Variable - Command",
    "Variable - Image",
    "Variable - List",
    "Bitmap",
    "Icon",
    "Page Link",
)

_EVENT_LABELS: tuple[str, ...] = (
    "Event Trigger",
    "System Macro",
    "Macro Step",
)

_GRAPHICS_LABELS = frozenset({"Bitmap", "Icon", "Variable - Image"})


def _type_id(*, family: str, label: str) -> str:
    return f"{family}:{label}"


CATALOG: tuple[TestingType, ...] = tuple(
    [
        TestingType(
            id=_type_id(family="button", label=label),
            label=label,
            family="button",
            graphics=label in _GRAPHICS_LABELS,
        )
        for label in _BUTTON_LABELS
    ]
    + [
        TestingType(
            id=_type_id(family="event", label=label),
            label=label,
            family="event",
            graphics=False,
        )
        for label in _EVENT_LABELS
    ]
)

CATALOG_BY_ID: dict[str, TestingType] = {row.id: row for row in CATALOG}
KNOWN_TYPE_IDS: frozenset[str] = frozenset(CATALOG_BY_ID)
GRAPHICS_TYPE_IDS: tuple[str, ...] = (
    "button:Bitmap",
    "button:Icon",
    "button:Variable - Image",
)

_MACRO_ALIASES = frozenset({"macro", "macros", "system macro", "system macros"})
_MACRO_STEP_ALIASES = frozenset(
    {"macrostep", "macrosteps", "macro step", "macro steps", "macro-step"}
)
_TRIGGER_ALIASES = frozenset({"trigger", "triggers", "event trigger", "event triggers"})
_PAGE_LINK_ALIASES = frozenset({"pagelink", "page link", "pagelinks", "page links"})
_TEXT_ALIASES = frozenset({"text", "texts"})

# Settings labels, pluralized for the excluded-type dialogue. "Text Labels" is Jamie's wording.
_EXCLUDED_PLURAL_DISPLAY: dict[str, str] = {
    "Text": "Text Labels",
    "System Macro": "System Macros",
    "Macro Step": "Macro Steps",
    "Event Trigger": "Event Triggers",
    "Page Link": "Page Links",
    "Bitmap": "Bitmaps",
    "Icon": "Icons",
}


def canonicalize_label(label: str) -> str:
    """Map extracted aliases / key suffixes to catalog labels. Do not invent types."""
    s = str(label or "").strip()
    if not s:
        return ""
    lower = s.lower()
    if lower in _MACRO_ALIASES:
        return "System Macro"
    if lower in _MACRO_STEP_ALIASES:
        return "Macro Step"
    if lower in _TRIGGER_ALIASES:
        return "Event Trigger"
    if lower in _PAGE_LINK_ALIASES:
        return "Page Link"
    if lower in _TEXT_ALIASES:
        return "Text"
    if lower == "bitmap":
        return "Bitmap"
    if lower == "icon":
        return "Icon"
    if lower.startswith("variable - "):
        tail = s.split("-", 1)[1].strip() if "-" in s else ""
        return f"Variable - {tail[:1].upper()}{tail[1:]}" if tail else s
    if lower.startswith("var."):
        tail = s.split(".", 1)[1].strip() if "." in s else ""
        return f"Variable - {tail[:1].upper()}{tail[1:]}" if tail else s
    return s


def excluded_testing_display_name(label: str) -> str:
    """Plural settings-type label for the excluded-from-testing dialogue."""
    name = canonicalize_label(label) or str(label or "").strip()
    return _EXCLUDED_PLURAL_DISPLAY.get(name, name)


def excluded_from_testing_message(label: str) -> str:
    display = excluded_testing_display_name(label)
    if not display:
        return "are not included in testing"
    return f"{display} are not included in testing"


def family_for_target_key(target_key: str) -> str:
    raw = str(target_key or "").strip()
    return "event" if raw.startswith("event:") else "button"


def family_for_kind(kind: str) -> str:
    k = str(kind or "").strip().upper()
    return "event" if k == "EVENT" else "button"


def type_id_for_label(*, family: str, label: str) -> str:
    name = canonicalize_label(label)
    fam = "event" if str(family or "").strip().lower() == "event" else "button"
    if not name:
        return ""
    return _type_id(family=fam, label=name)


def type_id_for_target_key(target_key: str) -> str:
    raw = str(target_key or "").strip()
    if not raw:
        return ""
    suffix = raw.rsplit(":", 1)[-1]
    return type_id_for_label(family=family_for_target_key(raw), label=suffix)


def normalize_disabled_types(raw: Any) -> list[str]:
    if raw is None:
        return []
    values: Iterable[Any]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        if s.startswith("["):
            try:
                import json

                parsed = json.loads(s)
                values = parsed if isinstance(parsed, list) else [s]
            except Exception:
                values = [s]
        else:
            values = [s]
    elif isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        tid = str(item or "").strip()
        if tid not in KNOWN_TYPE_IDS or tid in seen:
            continue
        seen.add(tid)
        out.append(tid)
    return out


def disabled_types_from_repo(repo: Any, project_id: str) -> frozenset[str]:
    getter = getattr(repo, "get_testing_type_disabled", None)
    if not callable(getter):
        return frozenset()
    try:
        return frozenset(normalize_disabled_types(getter(projectId=str(project_id))))
    except Exception:
        return frozenset()


def is_type_enabled(type_id: str, disabled: Iterable[str] | None) -> bool:
    tid = str(type_id or "").strip()
    if not tid or tid not in KNOWN_TYPE_IDS:
        return True
    off = {str(x).strip() for x in (disabled or []) if str(x).strip()}
    return tid not in off


def is_target_key_enabled(target_key: str, disabled: Iterable[str] | None) -> bool:
    return is_type_enabled(type_id_for_target_key(target_key), disabled)


def filter_expected_keys(keys: Iterable[str], disabled: Iterable[str] | None) -> set[str]:
    off = frozenset(str(x).strip() for x in (disabled or []) if str(x).strip())
    if not off:
        return {str(k) for k in keys if str(k).strip()}
    return {str(k) for k in keys if str(k).strip() and is_target_key_enabled(str(k), off)}


def settings_payload(*, project_id: str, disabled_types: Iterable[str] | None) -> dict[str, Any]:
    disabled = normalize_disabled_types(list(disabled_types or []))
    disabled_set = set(disabled)
    types_out: list[dict[str, Any]] = []
    for row in CATALOG:
        types_out.append(
            {
                "id": row.id,
                "label": row.label,
                "family": row.family,
                "graphics": bool(row.graphics),
                "enabled": row.id not in disabled_set,
            }
        )
    return {
        "projectId": str(project_id or ""),
        "offBehavior": "exclude",
        "disabledTypes": disabled,
        "graphicsTypeIds": list(GRAPHICS_TYPE_IDS),
        "types": types_out,
    }
