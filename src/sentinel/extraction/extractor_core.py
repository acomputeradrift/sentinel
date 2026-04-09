from __future__ import annotations

import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_STYLE_TO_TYPE = {5: "Slider", 6: "Image", 9: "Slider", 7: "Toggle", 10: "Toggle", 11: "LevelIndicatorBar", 14: "Image"}
_TOKEN_ONLY_RE = re.compile(r"^\s*(?:\$%(?:TAG|VARIABLE)!.*?%\$\s*)+$", re.IGNORECASE | re.DOTALL)
_TEXT_TOKEN_RE = re.compile(r"\$%(TAG|VARIABLE)!(.*?)%\$", re.IGNORECASE | re.DOTALL)
_DRIVER_TOKEN_RE = re.compile(r"%%([^%]+)%%")


@dataclass
class ExtractContext:
    apex_path: Path
    project_structure_path: Path


def validate_contract_shape(*, contract: Any, payload: Any) -> None:
    errors: list[str] = []

    def _walk(template: Any, value: Any, path: str) -> None:
        if isinstance(template, dict):
            if value is None:
                return
            if not isinstance(value, dict):
                errors.append(f"{path}: expected object, got {type(value).__name__}")
                return
            for key, child_template in template.items():
                child_path = f"{path}.{key}" if path else str(key)
                if key not in value:
                    errors.append(f"{child_path}: missing required key")
                    continue
                _walk(child_template, value.get(key), child_path)
            for key in value.keys():
                if key not in template:
                    child_path = f"{path}.{key}" if path else str(key)
                    errors.append(f"{child_path}: unexpected key")
            return

        if isinstance(template, list):
            if value is None:
                return
            if not isinstance(value, list):
                errors.append(f"{path}: expected array, got {type(value).__name__}")
                return
            if not template:
                return
            item_template = template[0]
            for idx, item in enumerate(value):
                _walk(item_template, item, f"{path}[{idx}]")
            return

    _walk(contract, payload, "")
    if errors:
        joined = "\n".join(f"- {msg}" for msg in errors)
        raise ValueError(f"Project data does not match contract shape:\n{joined}")


def _map_staged_progress(stage: str, percent: float) -> float:
    s = str(stage or "").strip().lower()
    try:
        p = float(percent or 0.0)
    except Exception:
        p = 0.0
    if p < 0:
        p = 0.0
    if p > 100:
        p = 100.0
    if s == "setup":
        return (15.0 * p) / 100.0
    if s == "work":
        return 15.0 + ((77.0 * p) / 100.0)
    if s == "finalize":
        return 92.0 + ((8.0 * p) / 100.0)
    return p


def _has_dimensions(width: Any, height: Any) -> bool:
    return int(width or 0) > 0 and int(height or 0) > 0


def _device_orientation_support(
    supported_orientations: Any,
    portrait_width: Any,
    portrait_height: Any,
    landscape_width: Any,
    landscape_height: Any,
    fallback_width: Any,
    fallback_height: Any,
) -> tuple[bool, bool]:
    value = int(supported_orientations or 0)
    portrait_dimensions = _has_dimensions(portrait_width, portrait_height)
    landscape_dimensions = _has_dimensions(landscape_width, landscape_height)
    fallback_dimensions = _has_dimensions(fallback_width, fallback_height)
    if value == 1:
        return portrait_dimensions or fallback_dimensions, False
    if value == 2:
        return False, landscape_dimensions or fallback_dimensions
    if value == 3:
        if portrait_dimensions or landscape_dimensions:
            return portrait_dimensions, landscape_dimensions
        if fallback_dimensions:
            fallback_w = int(fallback_width or 0)
            fallback_h = int(fallback_height or 0)
            if fallback_h >= fallback_w:
                return True, False
            return False, True
        return portrait_dimensions, landscape_dimensions
    return False, False


def _device_resolution(
    supported: bool,
    width: Any,
    height: Any,
    fallback_width: Any,
    fallback_height: Any,
) -> dict[str, int]:
    resolved_width = int(width or 0)
    resolved_height = int(height or 0)
    if supported and (resolved_width <= 0 or resolved_height <= 0):
        resolved_width = int(fallback_width or 0)
        resolved_height = int(fallback_height or 0)
    return {"width": resolved_width, "height": resolved_height}


def _is_token_only_text(text: str | None) -> bool:
    return bool(text and _TOKEN_ONLY_RE.match(text))


def _display_button_text(text: str | None) -> str:
    raw = str(text or "")
    if not raw:
        return raw

    def replace_token(match: re.Match[str]) -> str:
        token_type = str(match.group(1) or "").strip().upper()
        token_value = str(match.group(2) or "")
        if token_type == "TAG":
            return f"<Text Tag: {token_value}>"
        if token_type == "VARIABLE":
            return f"<Text Variable: {token_value}>"
        return match.group(0)

    return _TEXT_TOKEN_RE.sub(replace_token, raw)


def _empty(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _fetch_map(cur: sqlite3.Cursor, query: str, key_idx: int = 0, val_idx: int = 1) -> dict[Any, Any]:
    cur.execute(query)
    out: dict[Any, Any] = {}
    for row in cur.fetchall():
        out[row[key_idx]] = row[val_idx]
    return out


def _shared_layer_buttons(
    cur: sqlite3.Cursor,
    shared_layer_id: int,
    cache: dict[int, list[sqlite3.Row]],
) -> list[sqlite3.Row]:
    layer_id = int(shared_layer_id or 0)
    if layer_id in cache:
        return cache[layer_id]
    cur.execute(
        "select * from RTIDeviceButtonData where SharedLayerId = ? order by ButtonOrder, ButtonId",
        (layer_id,),
    )
    rows = list(cur.fetchall())
    cache[layer_id] = rows
    return rows


def _row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def _table_columns(cur: sqlite3.Cursor, table_name: str) -> set[str]:
    cur.execute(f"pragma table_info({table_name})")
    return {str(row[1]) for row in cur.fetchall()}


def _event_type_name(event_type: int) -> str:
    return {1: "Sense", 3: "Scheduled", 4: "Startup", 5: "Driver"}.get(event_type, f"Type{event_type}")


def _scope(room_id: int | None, device_id: int | None) -> str:
    r = room_id or 0
    d = -1 if device_id is None else device_id
    if r == 0 and d == -1:
        return "Global"
    if r > 0 and d == -1:
        return "Room"
    if r == 0 and d >= 0:
        return "Source"
    return "Controller"


def _has_non_empty_macro(cur: sqlite3.Cursor, macro_id: int) -> bool:
    cur.execute("select Type from MacroSteps where MacroId = ?", (macro_id,))
    rows = [r[0] for r in cur.fetchall()]
    if not rows:
        return False
    return any(step_type not in (3, 15) for step_type in rows)


def _usable_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.isdigit():
        return ""
    return text


def _driver_name(display_name: str | None, raw_name: str | None) -> str:
    return str(display_name or raw_name or "").strip()


def _expand_driver_tokens(text: str | None, driver_config: dict[str, str]) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(1)
        return driver_config.get(token, match.group(0))

    return _DRIVER_TOKEN_RE.sub(replace_token, raw).strip()


def _resolve_driver_trigger(system_events_xml: str | None, driver_extra_string: str | None, driver_config: dict[str, str]) -> tuple[str, str]:
    tag = str(driver_extra_string or "").strip()
    if not tag:
        return "", ""
    xml_text = str(system_events_xml or "").strip()
    if not xml_text:
        return "", tag
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "", tag
    matched_name = ""
    matched_category = ""
    for category_node in root.findall(".//category"):
        category_name = _expand_driver_tokens(category_node.attrib.get("name"), driver_config)
        for event_node in category_node.findall("./event"):
            if str(event_node.attrib.get("tag") or "").strip() == tag:
                matched_name = str(event_node.attrib.get("name") or "").strip()
                matched_category = str(category_name or "").strip()
                break
        if matched_name:
            break
    if not matched_name:
        return "", tag

    resolved = _expand_driver_tokens(matched_name, driver_config)
    return matched_category, resolved or tag


def _macro_family_rows(root_macro_id: int, macros_by_id: dict[int, sqlite3.Row], macros_by_system_id: dict[int, list[sqlite3.Row]]) -> list[sqlite3.Row]:
    seen: set[int] = set()
    out: list[sqlite3.Row] = []

    def visit(macro_id: int) -> None:
        if macro_id in seen:
            return
        seen.add(macro_id)
        row = macros_by_id.get(macro_id)
        if row is not None:
            out.append(row)
        for child in macros_by_system_id.get(macro_id, []):
            child_id = int(child["MacroId"])
            if child_id not in seen:
                out.append(child)
                visit(child_id)

    visit(root_macro_id)
    deduped: list[sqlite3.Row] = []
    seen_ids: set[int] = set()
    for row in out:
        macro_id = int(row["MacroId"])
        if macro_id in seen_ids:
            continue
        seen_ids.add(macro_id)
        deduped.append(row)
    return deduped


def _dedupe_non_empty(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def _resolve_direct_command_summaries(
    cur: sqlite3.Cursor,
    macro_id: int,
    driver_data_by_device_id: dict[int, sqlite3.Row],
    driver_config_by_driver_device_id: dict[int, dict[str, str]],
) -> list[str]:
    cur.execute(
        """
        select MacroStepId, Type, Name, Function, Parameter1, Parameter2, Parameter3, Parameter4, DeviceId
        from MacroStepsView
        where MacroId = ? and Type = 1
        order by StepIndex, MacroStepId
        """,
        (macro_id,),
    )
    summaries: list[str] = []
    for step in cur.fetchall():
        direct_name = _usable_name(step["Name"])
        if direct_name:
            summaries.append(direct_name)
            continue

        target_device_id = int(step["DeviceId"] or -1)
        driver_row = driver_data_by_device_id.get(target_device_id)
        driver_config: dict[str, str] = {}
        functions_xml = ""
        if driver_row is not None:
            driver_device_id = int(driver_row["DriverDeviceId"] or -1)
            driver_config = driver_config_by_driver_device_id.get(driver_device_id, {})
            functions_xml = str(driver_row["SystemFunctions"] or "")

        export_name = str(step["Function"] or "").strip()
        if not export_name:
            continue
        if not functions_xml:
            summaries.append(export_name)
            continue

        try:
            root = ET.fromstring(functions_xml)
        except ET.ParseError:
            summaries.append(export_name)
            continue

        function_node = None
        for candidate in root.findall(".//function"):
            if str(candidate.attrib.get("export") or "").strip() == export_name:
                function_node = candidate
                break
        if function_node is None:
            summaries.append(export_name)
            continue

        param_nodes = [node for node in list(function_node) if node.tag == "parameter"]
        raw_values = [str(step[f"Parameter{i}"] or "").strip() for i in range(1, 5)]
        resolved_by_name: dict[str, str] = {}
        ordered_values: list[str] = []
        for idx, param_node in enumerate(param_nodes[:4]):
            if str(param_node.attrib.get("hidden") or "").lower() == "true":
                continue
            raw_value = raw_values[idx]
            if not raw_value:
                continue
            resolved_value = raw_value
            for choice in list(param_node):
                if choice.tag != "choice":
                    continue
                if str(choice.attrib.get("value") or "").strip() != raw_value:
                    continue
                choice_name = _expand_driver_tokens(choice.attrib.get("name"), driver_config)
                if choice_name:
                    resolved_value = re.sub(r"\s+\(ID\s+\d+\)$", "", choice_name).strip()
                break
            param_name = str(param_node.attrib.get("name") or "").strip()
            if param_name:
                resolved_by_name[param_name] = resolved_value
            ordered_values.append(resolved_value)

        function_name = _expand_driver_tokens(function_node.attrib.get("name"), driver_config) or str(export_name).strip()
        if export_name == "SetDimmerLevel:QSDimmer":
            target = resolved_by_name.get("Integration ID")
            level = resolved_by_name.get("Level")
            if target and level:
                summaries.append(f"{target} to {level}%")
                continue
        if export_name == "SwitchCmd:Switch":
            target = resolved_by_name.get("Integration ID")
            action = resolved_by_name.get("Switch Command")
            if target and action:
                summaries.append(f"{target} {action}")
                continue

        if ordered_values:
            summaries.append(f"{function_name}: {', '.join(ordered_values)}")
        else:
            summaries.append(function_name)

    return _dedupe_non_empty(summaries)


def _resolve_macro_flag_summaries(cur: sqlite3.Cursor, macro_id: int) -> list[str]:
    cur.execute(
        """
        select FlagIndex, FlagType
        from MacroStepsView
        where MacroId = ?
          and Type = 15
        order by StepIndex, MacroStepId
        """,
        (macro_id,),
    )
    summaries: list[str] = []
    for row in cur.fetchall():
        flag_index = row["FlagIndex"]
        flag_type = row["FlagType"]
        parts = []
        if flag_index is not None:
            parts.append(f"FlagIndex={int(flag_index)}")
        if flag_type is not None:
            parts.append(f"FlagType={int(flag_type)}")
        if parts:
            summaries.append(", ".join(parts))
    return _dedupe_non_empty(summaries)


def _build_macro_flag_summary_cache(rows: list[tuple[int, Any, Any]]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for macro_id, flag_index, flag_type in rows:
        mid = int(macro_id or 0)
        if mid <= 0:
            continue
        parts: list[str] = []
        if flag_index is not None:
            parts.append(f"FlagIndex={int(flag_index)}")
        if flag_type is not None:
            parts.append(f"FlagType={int(flag_type)}")
        if not parts:
            continue
        summary = ", ".join(parts)
        bucket = out.setdefault(mid, [])
        if summary not in bucket:
            bucket.append(summary)
    return out


def _resolve_driver_action(
    cur: sqlite3.Cursor,
    macro_id: int,
    driver_id: int,
    macros_by_id: dict[int, sqlite3.Row],
    macros_by_system_id: dict[int, list[sqlite3.Row]],
    tag_name_by_id: dict[int, str],
    driver_data_by_device_id: dict[int, sqlite3.Row],
    driver_config_by_driver_device_id: dict[int, dict[str, str]],
) -> tuple[list[str], list[dict[str, str]], int]:
    wrapper_rows = [
        row
        for row in macros_by_system_id.get(macro_id, [])
        if int(row["MacroId"] or -1) != macro_id and int(row["DeviceId"] or -1) == driver_id
    ]
    root_row = macros_by_id.get(macro_id)
    candidate_rows = wrapper_rows or ([root_row] if root_row is not None else [])

    macro_step_count = 0
    for row in candidate_rows:
        cur.execute("select count(*) from MacroStepsView where MacroId = ?", (int(row["MacroId"]),))
        count_row = cur.fetchone()
        macro_step_count += int(count_row[0] or 0) if count_row else 0

    macro_names: list[str] = []
    for row in candidate_rows:
        cur.execute(
            "select CommandTagId from MacroStepsView where MacroId = ? and Type = 14 order by StepIndex, MacroStepId",
            (int(row["MacroId"]),),
        )
        for step in cur.fetchall():
            if step[0] is None:
                continue
            command_tag_id = int(step[0])
            command_name = _usable_name(tag_name_by_id.get(command_tag_id))
            if command_name:
                macro_names.append(command_name)

    macro_names = _dedupe_non_empty(macro_names)
    if macro_names:
        return macro_names, [], 0

    for row in candidate_rows:
        wrapper_name = _usable_name(tag_name_by_id.get(int(row["ButtonTagId"] or -1)))
        if wrapper_name:
            return [wrapper_name], [], 0

    macro_steps: list[dict[str, str]] = []
    for row in candidate_rows:
        command_summaries = _resolve_direct_command_summaries(
            cur,
            int(row["MacroId"]),
            driver_data_by_device_id,
            driver_config_by_driver_device_id,
        )
        for summary in command_summaries:
            macro_steps.append({"name": summary, "type": "command"})
        flag_summaries = _resolve_macro_flag_summaries(cur, int(row["MacroId"]))
        for summary in flag_summaries:
            macro_steps.append({"name": summary, "type": "flag"})

    seen_step_names: set[tuple[str, str]] = set()
    deduped_steps: list[dict[str, str]] = []
    for step in macro_steps:
        key = (str(step.get("name") or "").strip(), str(step.get("type") or "").strip())
        if not key[0] or key in seen_step_names:
            continue
        seen_step_names.add(key)
        deduped_steps.append({"name": key[0], "type": key[1] or "command"})
    if deduped_steps:
        return [], deduped_steps, macro_step_count

    if macro_step_count > 0:
        return [], [{"name": "", "type": "undefined"} for _ in range(macro_step_count)], macro_step_count
    return [], [], 0


def _resolve_system_macro_name(
    macro_id: int,
    macros_by_id: dict[int, sqlite3.Row],
    macros_by_system_id: dict[int, list[sqlite3.Row]],
    tag_name_by_id: dict[int, str],
) -> str:
    for row in macros_by_system_id.get(macro_id, []):
        if int(row["MacroId"] or -1) == macro_id:
            continue
        related_name = _usable_name(tag_name_by_id.get(int(row["ButtonTagId"] or -1)))
        if related_name:
            return related_name
    direct_row = macros_by_id.get(macro_id)
    if direct_row:
        direct_name = _usable_name(tag_name_by_id.get(int(direct_row["ButtonTagId"] or -1)))
        if direct_name:
            return direct_name
    return ""


def _event_test_targets(macro_names: list[str], macro_steps: list[dict[str, str]]) -> dict[str, bool]:
    targets = {
        "Trigger": True,
        "Macro": False,
        "Macros": False,
        "MacroStep": False,
        "MacroSteps": False,
    }
    if macro_names:
        targets["Macro" if len(macro_names) == 1 else "Macros"] = True
    if macro_steps:
        targets["MacroStep" if len(macro_steps) == 1 else "MacroSteps"] = True
    return targets


def _sense_port_label(cur: sqlite3.Cursor, sense_port: int) -> str:
    generic_label = ""
    cur.execute("select LabelKey, LabelName from PortLabels where RTIAddress = 0")
    for row in cur.fetchall():
        label_key = int(row["LabelKey"] or 0)
        port_number = (label_key & 65535) - 512 + 1
        if (port_number - 1) == sense_port:
            label = str(row["LabelName"] or "").strip()
            if label:
                if -65024 <= label_key <= -65017:
                    return label
                if not generic_label:
                    generic_label = label
    return generic_label or f"Sense {sense_port + 1}"


def _sense_action_text(cur: sqlite3.Cursor, sense_port: int, sense_action: int, sense_expander_id: int) -> str:
    cur.execute("select Mask from SenseModeMap where RTIAddress = 0 and ExpanderId = ?", (sense_expander_id,))
    row = cur.fetchone()
    mask = int(row["Mask"] or 0) if row else 0
    is_closure = bool(mask & (1 << sense_port))
    if is_closure:
        return "closes" if sense_action == 0 else "opens"
    return "goes Low" if sense_action == 0 else "goes High"


def _decode_scheduled_trigger(ev: sqlite3.Row) -> str:
    if int(_row_value(ev, "DailyAstronomical", 0) or 0) == 1:
        raw = bytes(_row_value(ev, "DailyStartTime", b"") or b"")
        raw_hex = raw.hex().upper()
        if raw_hex.endswith("0000"):
            return "At Sunrise"
        if raw_hex.endswith("0001") or raw_hex.endswith("0100"):
            return "At Sunset"
        return "At astronomical event"

    day_mask = int(_row_value(ev, "DailyDayMask", 0) or 0)
    day_group = {62: "Weekdays", 65: "Weekends", 127: "Every day"}.get(day_mask, "Scheduled")
    raw = bytes(_row_value(ev, "DailyStartTime", b"") or b"")
    if len(raw) >= 16:
        parts = list(int.from_bytes(raw[i : i + 2], "little") for i in range(0, 16, 2))
        hour24 = parts[4]
        minute = parts[6]
        if 0 <= hour24 <= 23 and 0 <= minute <= 59:
            am_pm = "AM" if hour24 < 12 else "PM"
            hour12 = hour24 % 12 or 12
            prefix = "Every day" if day_group == "Every day" else f"On {day_group.lower()}"
            return f"{prefix} at {hour12}:{minute:02d} {am_pm}"
    return "Every day" if day_group == "Every day" else f"On {day_group.lower()}"


def _resolve_system_trigger(cur: sqlite3.Cursor, ev: sqlite3.Row, event_type: int) -> str:
    if event_type == 1:
        if not all(k in ev.keys() for k in ("SensePort", "SenseAction", "SenseExpanderId")):
            description = str(_row_value(ev, "Description", "") or "").strip()
            return description or "When sense event occurs"
        sense_port = int(_row_value(ev, "SensePort", 0) or 0)
        sense_action = int(_row_value(ev, "SenseAction", 0) or 0)
        sense_expander_id = int(_row_value(ev, "SenseExpanderId", -1) or -1)
        label = _sense_port_label(cur, sense_port)
        action = _sense_action_text(cur, sense_port, sense_action, sense_expander_id)
        return f"When {label} {action}"
    if event_type == 3:
        return _decode_scheduled_trigger(ev)
    if event_type == 4:
        return "On system startup"
    return str(ev["Description"] or "").strip()


def _coords(top: Any, left: Any, height: Any, width: Any) -> dict[str, int]:
    return {
        "top": int(top or 0),
        "left": int(left or 0),
        "height": int(height or 0),
        "width": int(width or 0),
    }


def _coords_fit_resolution(coords: dict[str, int], resolution: dict[str, int]) -> bool:
    left = int(coords.get("left") or 0)
    top = int(coords.get("top") or 0)
    width = int(coords.get("width") or 0)
    height = int(coords.get("height") or 0)
    res_w = int(resolution.get("width") or 0)
    res_h = int(resolution.get("height") or 0)
    if width <= 0 or height <= 0 or res_w <= 0 or res_h <= 0:
        return False
    if left < 0 or top < 0:
        return False
    return (left + width) <= res_w and (top + height) <= res_h


def _select_orientation_coordinates(
    *,
    orientation: str,
    primary: dict[str, int],
    alt: dict[str, int],
    portrait_supported: bool,
    landscape_supported: bool,
    portrait_resolution: dict[str, int],
    landscape_resolution: dict[str, int],
) -> dict[str, int]:
    is_landscape = str(orientation or "").strip().lower() == "landscape"
    resolution = landscape_resolution if is_landscape else portrait_resolution
    both_supported = bool(portrait_supported) and bool(landscape_supported)
    landscape_only = bool(landscape_supported) and not bool(portrait_supported)
    if is_landscape:
        # Preserve explicit portrait/landscape split when both are supported.
        default_candidate = alt if both_supported else primary if landscape_only else alt
        fallback_candidate = primary if default_candidate is alt else alt
    else:
        default_candidate = primary
        fallback_candidate = alt
    if _coords_fit_resolution(default_candidate, resolution):
        return default_candidate
    if _coords_fit_resolution(fallback_candidate, resolution):
        return fallback_candidate
    return default_candidate


def _orientation_visibility(mask: int) -> dict[str, bool]:
    if mask == 3:
        return {"portrait": True, "landscape": True}
    if mask == 1:
        return {"portrait": True, "landscape": False}
    if mask == 2:
        return {"portrait": False, "landscape": True}
    return {"portrait": False, "landscape": False}


def _button_ui(
    button_row: sqlite3.Row,
    *,
    portrait_supported: bool = True,
    landscape_supported: bool = True,
    portrait_resolution: dict[str, int] | None = None,
    landscape_resolution: dict[str, int] | None = None,
    layer_order: int = 0,
    button_order: int = 0,
    frame_number: int = 0,
) -> dict[str, Any]:
    vis = _orientation_visibility(int(button_row["VisibleOrientations"] or 0))
    primary = _coords(
        button_row["ButtonTop"],
        button_row["ButtonLeft"],
        button_row["ButtonHeight"],
        button_row["ButtonWidth"],
    )
    alt = _coords(
        button_row["ButtonTopAlt"],
        button_row["ButtonLeftAlt"],
        button_row["ButtonHeightAlt"],
        button_row["ButtonWidthAlt"],
    )
    portrait_res = portrait_resolution or {"width": 0, "height": 0}
    landscape_res = landscape_resolution or {"width": 0, "height": 0}
    return {
        "fontSize": int(button_row["TextSize"] or 0),
        "orientations": {
            "portrait": {
                "visible": vis["portrait"],
                "coordinates": _select_orientation_coordinates(
                    orientation="portrait",
                    primary=primary,
                    alt=alt,
                    portrait_supported=portrait_supported,
                    landscape_supported=landscape_supported,
                    portrait_resolution=portrait_res,
                    landscape_resolution=landscape_res,
                ),
            },
            "landscape": {
                "visible": vis["landscape"],
                "coordinates": _select_orientation_coordinates(
                    orientation="landscape",
                    primary=primary,
                    alt=alt,
                    portrait_supported=portrait_supported,
                    landscape_supported=landscape_supported,
                    portrait_resolution=portrait_res,
                    landscape_resolution=landscape_res,
                ),
            },
        },
        "stack": {
            "layerOrder": int(layer_order or 0),
            "buttonOrder": int(button_order or 0),
            "frameNumber": int(frame_number or 0),
        },
    }


def _is_hard_button(button_ui: dict[str, Any]) -> bool:
    portrait = button_ui["orientations"]["portrait"]["coordinates"]
    return int(portrait["height"] or 0) == 0 and int(portrait["width"] or 0) == 0


def _csv_ints(value: Any, *, dedupe: bool = True) -> list[int]:
    out: list[int] = []
    for piece in str(value or "").split(","):
        cleaned = piece.strip()
        if not cleaned:
            continue
        try:
            num = int(cleaned)
        except ValueError:
            continue
        if not dedupe or num not in out:
            out.append(num)
    return out


def _append_resolved_page_link(
    resolved: list[dict[str, Any]],
    seen: set[tuple[int, str]],
    target_page_id: int | None,
    target_page_name: str | None,
    resolution_path: str,
) -> None:
    if target_page_id is None:
        return
    key = (int(target_page_id), str(resolution_path))
    if key in seen:
        return
    seen.add(key)
    resolved.append(
        {
            "targetPageId": int(target_page_id),
            "targetPageName": str(target_page_name or "").strip() or None,
            "resolutionPath": resolution_path,
        }
    )


def _csv_page_targets(page_ids_value: Any, rti_addresses_value: Any) -> list[tuple[int, int]]:
    page_ids = _csv_ints(page_ids_value, dedupe=False)
    rti_addresses = _csv_ints(rti_addresses_value, dedupe=False)
    out: list[tuple[int, int]] = []
    for idx, page_id in enumerate(page_ids):
        rti_address = rti_addresses[idx] if idx < len(rti_addresses) else 0
        out.append((page_id, rti_address))
    return out


def _pick_target_for_rti(targets: list[tuple[int, int]], current_rti_address: int) -> int | None:
    for page_id, rti_address in targets:
        if int(rti_address or 0) == int(current_rti_address or 0):
            return int(page_id)
    return int(targets[0][0]) if targets else None


def _activity_target_page_ids(
    select_source_id: int,
    select_source_room_id: int,
    fallback_room_id: int,
    activity_target_pages_by_room_and_device: dict[tuple[int, int], list[tuple[int, int]]],
    global_room_fallback_id: int | None = None,
) -> list[tuple[int, int]]:
    room_id = select_source_room_id if select_source_room_id > 0 else fallback_room_id
    if room_id == 0 and global_room_fallback_id is not None:
        room_id = int(global_room_fallback_id)
    return activity_target_pages_by_room_and_device.get((room_id, select_source_id), [])


def _pick_select_source_macro_target(
    macro_id: int,
    current_rti_address: int,
    page_room_id: int,
    select_sources_by_macro: dict[int, list[tuple[int, int]]],
    activity_target_pages_by_room_and_device: dict[tuple[int, int], list[tuple[int, int]]],
    macro_step_targets_by_macro: dict[int, list[tuple[int, int]]],
    global_room_fallback_id: int | None = None,
) -> int | None:
    select_sources = select_sources_by_macro.get(macro_id, [])
    macro_targets = macro_step_targets_by_macro.get(macro_id, [])
    if not select_sources or not macro_targets:
        return None

    current_device_targets = [int(page_id) for page_id, rti_address in macro_targets if int(rti_address or 0) == int(current_rti_address or 0)]
    if len(current_device_targets) <= 1:
        return None

    allowed_targets = set(current_device_targets)
    for select_source_id, select_source_room_id in select_sources:
        for page_id, rti_address in _activity_target_page_ids(
            select_source_id,
            select_source_room_id,
            page_room_id,
            activity_target_pages_by_room_and_device,
            global_room_fallback_id=global_room_fallback_id,
        ):
            if int(rti_address or 0) != int(current_rti_address or 0):
                continue
            candidate_page_id = int(page_id)
            if candidate_page_id in allowed_targets:
                return candidate_page_id
    return None


def _room_off_target_page_ids(
    room_off_id: int,
    current_room_id: int,
    room_home_target_pages_by_room: dict[int, list[tuple[int, int]]],
) -> list[tuple[int, int]]:
    if room_off_id == -1 and current_room_id > 0:
        return room_home_target_pages_by_room.get(current_room_id, [])
    return []


def _resolve_button(
    cur: sqlite3.Cursor,
    button_row: sqlite3.Row,
    current_device_id: int,
    tag_name_by_id: dict[int, str],
    variables_by_tag: dict[int, list[sqlite3.Row]],
    button_text_tag_ids: set[int],
    macros_by_tag: dict[int, list[sqlite3.Row]],
    macro_non_empty_by_id: dict[int, bool],
    page_links_by_device_and_tag: dict[tuple[int, int], sqlite3.Row],
    page_links_by_tag: dict[int, sqlite3.Row],
    first_page_target_by_device_id: dict[int, tuple[int, str | None]],
    page_name_by_page_id: dict[int, str],
    room_name_by_id: dict[int, str],
    source_name_by_device_id: dict[int, str],
    macro_step_exact_page_by_macro: dict[int, int],
    macro_step_targets_by_macro: dict[int, list[tuple[int, int]]],
    room_event_targets_by_room: dict[int, list[tuple[int, int]]],
    select_rooms_by_macro: dict[int, list[int]],
    room_offs_by_macro: dict[int, list[int]],
    select_sources_by_macro: dict[int, list[tuple[int, int]]],
    activity_target_pages_by_room_and_device: dict[tuple[int, int], list[tuple[int, int]]],
    room_home_target_pages_by_room: dict[int, list[tuple[int, int]]],
    variable_command_rows_by_variable_id: dict[int, list[sqlite3.Row]],
    macro_flag_summaries_by_macro_id: dict[int, list[str]],
    button_graphics_targets_by_button_id: dict[int, tuple[bool, bool]],
    use_explicit_button_bitmaps: bool,
    page_id: int,
    page_source_device_id: int | None,
    page_room_id: int,
    current_rti_address: int,
    global_room_fallback_id: int | None,
    layer_id: int,
    shared_layer_id: int,
    layer_name_resolved: str,
    layer_room_id: int | None,
    layer_source_id: int | None,
    page_layer_room_id: int | None,
    page_layer_source_id: int | None,
    layer_order: int,
    button_order: int,
    frame_number: int,
    host_viewport_button_id: int | None,
    portrait_supported: bool = True,
    landscape_supported: bool = True,
    portrait_resolution: dict[str, int] | None = None,
    landscape_resolution: dict[str, int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    button_id = int(button_row["ButtonId"])
    tag_id = int(button_row["ButtonTagId"] or -1)
    text = button_row["Text"] or ""
    display_text = _display_button_text(text)
    style = int(button_row["ButtonStyle"] or 0)
    button_type = _STYLE_TO_TYPE.get(style)
    tag_name = tag_name_by_id.get(tag_id)

    up_bitmap_id = int(button_row["UpBitmapId"]) if "UpBitmapId" in button_row.keys() and button_row["UpBitmapId"] is not None else -1
    down_bitmap_id = int(button_row["DownBitmapId"]) if "DownBitmapId" in button_row.keys() and button_row["DownBitmapId"] is not None else -1
    icon_bitmap_id = int(button_row["IconBitmapId"]) if "IconBitmapId" in button_row.keys() and button_row["IconBitmapId"] is not None else -1
    raw_bitmap_enabled = bool(up_bitmap_id != -1 or down_bitmap_id != -1)
    raw_icon_enabled = bool(icon_bitmap_id != -1)
    # Temporary gating rule: slider/toggle/level-indicator controls do not emit graphics test targets.
    # For all other controls, rely on raw RTIDeviceButtonData bitmap/icon ids.
    if button_type in {"Slider", "Toggle", "LevelIndicatorBar"}:
        bitmap_enabled = False
        icon_enabled = False
    else:
        bitmap_enabled = raw_bitmap_enabled
        icon_enabled = raw_icon_enabled

    variables_rows = variables_by_tag.get(tag_id, []) if tag_id > 0 else []
    object_tokens = [str(v["ObjectData"] or "") for v in variables_rows]
    button_text_tokens = [str(v["ButtonText"] or "") for v in variables_rows]
    variable_ids = [int(v["VariableId"]) for v in variables_rows if v["VariableId"] is not None]

    has_var_text = any(not _empty(v["ButtonText"]) for v in variables_rows) or button_id in button_text_tag_ids or _is_token_only_text(text)
    has_literal_text = not _empty(text) and not _is_token_only_text(text)

    object_data_tokens = [tok for tok in object_tokens if tok]
    has_object_data = bool(object_data_tokens)
    is_slider = button_type == "Slider"
    is_toggle = button_type == "Toggle"
    is_level_indicator = button_type == "LevelIndicatorBar"
    is_image = button_type == "Image"
    is_style8_object = style == 8 and has_object_data
    value_enabled = bool(has_object_data and (is_slider or is_level_indicator))
    state_object_tokens = object_data_tokens if is_toggle else []
    state_enabled = bool(state_object_tokens)
    image_object_tokens = object_data_tokens if is_image else []
    image_enabled = bool(image_object_tokens)
    list_object_tokens = object_data_tokens if is_style8_object else []
    list_enabled = bool(list_object_tokens)
    variable_command_rows: list[sqlite3.Row] = []
    for variable_id in variable_ids:
        variable_command_rows.extend(variable_command_rows_by_variable_id.get(variable_id, []))
    command_enabled = bool(is_slider and variable_command_rows)

    reversed_enabled = any(not _empty(v["ReversedData"]) for v in variables_rows)
    inactive_enabled = any(not _empty(v["InactiveData"]) for v in variables_rows)
    visible_enabled = any(not _empty(v["VisibleData"]) for v in variables_rows)

    explicit_macro_ids: list[int] = []
    for field in ("GlobalMacroId", "DeviceMacroId"):
        if field in button_row.keys() and button_row[field] is not None:
            macro_id = int(button_row[field])
            if macro_id > 0 and macro_id not in explicit_macro_ids:
                explicit_macro_ids.append(macro_id)

    all_tag_macro_rows = macros_by_tag.get(tag_id, []) if tag_id > 0 else []
    scoped_tag_macro_rows = [m for m in all_tag_macro_rows if int(m["RoomId"] or 0) in {0, page_room_id}]
    tag_macro_rows = scoped_tag_macro_rows or all_tag_macro_rows
    has_macros_target = bool(explicit_macro_ids)
    has_macro_steps_target = any(macro_non_empty_by_id.get(int(m["MacroId"]), False) for m in tag_macro_rows)
    resolved_macro_summaries: list[str] = []
    for macro_row in tag_macro_rows:
        macro_id = int(macro_row["MacroId"] or 0)
        if macro_id <= 0:
            continue
        for summary in macro_flag_summaries_by_macro_id.get(macro_id, []):
            if summary not in resolved_macro_summaries:
                resolved_macro_summaries.append(summary)

    direct_page_link_id = int(button_row["PageLinkId"]) if "PageLinkId" in button_row.keys() and button_row["PageLinkId"] is not None else None
    direct_target_page_id = int(button_row["LinkPageId"]) if "LinkPageId" in button_row.keys() and button_row["LinkPageId"] is not None else None
    page_link_row = None
    page_link_row_link_type = None
    if tag_id > 0:
        page_link_row = page_links_by_device_and_tag.get((current_device_id, tag_id))
        if page_link_row is None:
            page_link_row = page_links_by_tag.get(tag_id)
    if page_link_row is not None and "LinkType" in page_link_row.keys():
        page_link_row_link_type = int(page_link_row["LinkType"] or 0)
    if direct_page_link_id is not None or direct_target_page_id is not None:
        page_link_enabled = True
        target_page_id = direct_target_page_id
        page_link_id = direct_page_link_id
    else:
        page_link_enabled = page_link_row is not None
        target_page_id = None
        if page_link_row and page_link_row["PageId"] is not None:
            if page_link_row_link_type == 1:
                first_page_target = first_page_target_by_device_id.get(current_device_id)
                target_page_id = first_page_target[0] if first_page_target is not None else None
            else:
                target_page_id = int(page_link_row["PageId"])
        page_link_id = int(page_link_row["PageLinkId"]) if page_link_row and page_link_row["PageLinkId"] is not None else None

    resolved_page_link: dict[str, Any] | None = None
    if target_page_id is not None:
        resolved_page_link = {
            "targetPageId": int(target_page_id),
            "targetPageName": str(page_name_by_page_id.get(target_page_id) or "").strip() or None,
            "resolutionPath": "directPageLink",
        }

    candidate_macro_ids: list[int] = explicit_macro_ids[:]
    for macro_row in tag_macro_rows:
        macro_id = int(macro_row["MacroId"] or 0)
        if macro_id > 0 and macro_id not in candidate_macro_ids:
            candidate_macro_ids.append(macro_id)

    if resolved_page_link is None:
        for macro_id in candidate_macro_ids:
            macro_target_page_id = macro_step_exact_page_by_macro.get(macro_id)
            if macro_target_page_id is None:
                macro_target_page_id = _pick_select_source_macro_target(
                    macro_id,
                    current_rti_address,
                    page_room_id,
                    select_sources_by_macro,
                    activity_target_pages_by_room_and_device,
                    macro_step_targets_by_macro,
                    global_room_fallback_id=global_room_fallback_id,
                )
            if macro_target_page_id is None:
                macro_target_page_id = _pick_target_for_rti(macro_step_targets_by_macro.get(macro_id, []), current_rti_address)
            if macro_target_page_id is not None:
                resolved_page_link = {
                    "targetPageId": macro_target_page_id,
                    "targetPageName": str(page_name_by_page_id.get(macro_target_page_id) or "").strip() or None,
                    "resolutionPath": "macroStep",
                }
                break

    if resolved_page_link is None:
        for macro_id in candidate_macro_ids:
            for select_room_id in select_rooms_by_macro.get(macro_id, []):
                room_target_page_id = _pick_target_for_rti(room_event_targets_by_room.get(select_room_id, []), current_rti_address)
                if room_target_page_id is not None:
                    resolved_page_link = {
                        "targetPageId": room_target_page_id,
                        "targetPageName": str(page_name_by_page_id.get(room_target_page_id) or "").strip() or None,
                        "resolutionPath": "roomSelectEvent",
                    }
                    break
            if resolved_page_link is not None:
                break

    if resolved_page_link is None:
        for macro_id in candidate_macro_ids:
            for select_source_id, select_source_room_id in select_sources_by_macro.get(macro_id, []):
                activity_target_page_id = _pick_target_for_rti(
                    _activity_target_page_ids(
                        select_source_id,
                        select_source_room_id,
                        page_room_id,
                        activity_target_pages_by_room_and_device,
                        global_room_fallback_id=global_room_fallback_id,
                    ),
                    current_rti_address,
                )
                if activity_target_page_id is not None:
                    resolved_page_link = {
                        "targetPageId": activity_target_page_id,
                        "targetPageName": str(page_name_by_page_id.get(activity_target_page_id) or "").strip() or None,
                        "resolutionPath": "activityEvent",
                    }
                    break
            if resolved_page_link is not None:
                break

    if resolved_page_link is None:
        for macro_id in candidate_macro_ids:
            for room_off_id in room_offs_by_macro.get(macro_id, []):
                room_off_target_page_id = _pick_target_for_rti(
                    _room_off_target_page_ids(room_off_id, page_room_id, room_home_target_pages_by_room),
                    current_rti_address,
                )
                if room_off_target_page_id is not None:
                    resolved_page_link = {
                        "targetPageId": room_off_target_page_id,
                        "targetPageName": str(page_name_by_page_id.get(room_off_target_page_id) or "").strip() or None,
                        "resolutionPath": "roomOffEvent",
                    }
                    break
            if resolved_page_link is not None:
                break

    macro_step_ids: list[int] = []

    button_ui = _button_ui(
        button_row,
        portrait_supported=portrait_supported,
        landscape_supported=landscape_supported,
        portrait_resolution=portrait_resolution or {"width": 0, "height": 0},
        landscape_resolution=landscape_resolution or {"width": 0, "height": 0},
        layer_order=layer_order,
        button_order=button_order,
        frame_number=frame_number,
    )
    page_name_resolved = str(page_name_by_page_id.get(int(page_id)) or "").strip()
    effective_room_id = (
        int(layer_room_id) if layer_room_id is not None else (int(page_layer_room_id) if page_layer_room_id is not None else int(page_room_id))
    )
    effective_source_id = (
        int(layer_source_id)
        if layer_source_id is not None
        else (int(page_layer_source_id) if page_layer_source_id is not None else (int(page_source_device_id) if page_source_device_id is not None else None))
    )
    effective_room_name = str(room_name_by_id.get(effective_room_id) or ("Global" if int(effective_room_id) == 0 else f"Room {effective_room_id}"))
    effective_source_name = ""
    if effective_source_id is not None:
        effective_source_name = str(source_name_by_device_id.get(int(effective_source_id)) or str(int(effective_source_id)))

    user_button = {
        "buttonIdentity": {
            "buttonTagName": tag_name,
            "text": display_text,
            "buttonType": button_type,
        },
        "buttonUI": button_ui,
        "testTargets": {
            "text": has_literal_text,
            "macros": has_macros_target,
            "macroSteps": has_macro_steps_target,
            "variables": {
                "Text": has_var_text,
                "Reversed": reversed_enabled,
                "Inactive": inactive_enabled,
                "Visible": visible_enabled,
                "Value": value_enabled,
                "State": state_enabled,
                "Command": command_enabled,
                "Image": image_enabled,
                "List": list_enabled,
            },
            "graphics": {
                "bitmap": bitmap_enabled,
                "icon": icon_enabled,
            },
            "pageLink": resolved_page_link is not None,
        },
        "resolvedPageLink": resolved_page_link,
        "apexScopeSource": {
            "page": {
                "pageId": int(page_id),
                "roomId": int(page_room_id),
                "sourceDeviceId": (int(page_source_device_id) if page_source_device_id is not None else None),
                "rtiAddress": int(current_rti_address),
            },
            "viewportLayer": {
                "layerId": int(layer_id),
                "sharedLayerId": int(shared_layer_id),
                "roomId": (int(layer_room_id) if layer_room_id is not None else None),
                "sourceId": (int(layer_source_id) if layer_source_id is not None else None),
            },
            "pageLayer": {
                "roomId": (int(page_layer_room_id) if page_layer_room_id is not None else None),
                "sourceId": (int(page_layer_source_id) if page_layer_source_id is not None else None),
            },
            "button": {
                "buttonId": int(button_id),
                "buttonTagId": (int(tag_id) if tag_id > 0 else None),
            },
            "bindings": {
                "macroIds": [int(mid) for mid in candidate_macro_ids],
                "variableIds": [int(vid) for vid in variable_ids],
                "macroStepIds": [int(sid) for sid in macro_step_ids],
                "pageLinkId": page_link_id,
            },
        },
    }

    diag_button = {
        "buttonId": button_id,
        "buttonTagName": tag_name,
        "source": {
            "layerId": int(layer_id),
            "sharedLayerId": int(shared_layer_id),
            "layerOrder": int(layer_order or 0),
            "buttonOrder": int(button_order or 0),
            "frameNumber": int(frame_number or 0),
        },
        "identifiers": {"buttonTagId": tag_id if tag_id > 0 else None, "text": text},
        "testTargets": {
            "macro": {
                "scope": "Global",
                "scopeType": "Global | Room | Source | Controller",
                "globalMacroId": tag_macro_rows[0]["MacroId"] if tag_macro_rows else None,
                "deviceMacroId": None,
                "resolvedCommand": " | ".join(resolved_macro_summaries) if resolved_macro_summaries else None,
                "isEmpty": not has_macro_steps_target if tag_macro_rows else False,
            },
            "variableDetails": {
                "Text": {"enabled": has_var_text, "rawButtonText": next((t for t in button_text_tokens if t), None), "resolvedName": None},
                "Reversed": {"enabled": reversed_enabled, "source": "ReversedData" if reversed_enabled else None},
                "Inactive": {"enabled": inactive_enabled, "source": "InactiveData" if inactive_enabled else None},
                "Visible": {"enabled": visible_enabled, "source": "VisibleData" if visible_enabled else None},
                "Value": {"enabled": value_enabled, "source": "ObjectData" if value_enabled else None, "objectRef": next(iter(object_data_tokens), None)},
                "State": {"enabled": state_enabled, "source": "ObjectData" if state_enabled else None, "objectRef": next(iter(state_object_tokens), None)},
                "Command": {
                    "enabled": command_enabled,
                    "source": "MacroDeviceCommand.VariableId" if is_slider and variable_command_rows else None,
                    "controlType": button_type,
                    "driverFunction": next((str(r["Function"] or "").strip() or None for r in variable_command_rows), None),
                    "pairedMacroFunction": None,
                },
                "Image": {"enabled": image_enabled, "source": "ObjectData" if image_enabled else None, "objectRef": next(iter(image_object_tokens), None)},
                "List": {"enabled": list_enabled, "source": "ObjectData" if list_enabled else None, "objectRef": next(iter(list_object_tokens), None)},
            },
            "pageLink": {"pageLinkId": page_link_id, "targetPageId": target_page_id, "targetPageName": None},
        },
        "viewportContext": {
            "hostViewportButtonId": (int(host_viewport_button_id) if host_viewport_button_id is not None else None),
            "frameIndexRti": (int(frame_number) if host_viewport_button_id is not None else None),
        },
        "resolvedContext": {
            "pageNameResolved": page_name_resolved,
            "layerNameResolved": str(layer_name_resolved or ""),
            "effectiveRoomId": int(effective_room_id),
            "effectiveSourceId": (int(effective_source_id) if effective_source_id is not None else None),
            "effectiveRoomName": effective_room_name,
            "effectiveSourceName": effective_source_name,
        },
    }

    has_any_variable_target = bool(
        has_var_text
        or reversed_enabled
        or inactive_enabled
        or visible_enabled
        or value_enabled
        or state_enabled
        or command_enabled
        or list_enabled
    )
    return user_button, diag_button


def _has_any_variable_target(button: dict[str, Any]) -> bool:
    variables = button.get("testTargets", {}).get("variables", {})
    if not isinstance(variables, dict):
        return False
    return any(bool(v) for v in variables.values())


def _classify_user_button_category(
    *,
    button: dict[str, Any],
    has_tag_field: bool,
    raw_text: str,
    has_macros_target: bool,
    has_any_variable_target: bool,
) -> str:
    if _is_hard_button(button["buttonUI"]):
        return "hardButtons"
    if (not has_tag_field) and _empty(raw_text) and (not has_macros_target) and (not has_any_variable_target):
        return "uiItems"
    if _is_screen_label(button):
        return "screenLabels"
    if has_tag_field and _empty(button.get("buttonIdentity", {}).get("buttonTagName")):
        return "emptyTag"
    return "screenButtons"


def _merge_diag_ui_items(existing: list[dict[str, Any]], viewport_button_ids: list[int]) -> list[dict[str, Any]]:
    out = list(existing or [])
    seen_ids = {int(row.get("buttonId")) for row in out if isinstance(row, dict) and row.get("buttonId") is not None}
    for button_id in viewport_button_ids:
        bid = int(button_id or 0)
        if bid <= 0 or bid in seen_ids:
            continue
        seen_ids.add(bid)
        out.append({"buttonId": bid})
    return out


def extract_project_data(ctx: ExtractContext, progress_hook: Any = None) -> dict[str, Any]:
    _ = json_load(ctx.project_structure_path)
    con = sqlite3.connect(ctx.apex_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    progress_enabled = callable(progress_hook)
    last_percent_reported = -1.0
    total_work_units = 0
    completed_work_units = 0
    setup_steps_total = 8
    setup_steps_done = 0

    def _emit_stage(stage: str, stage_percent: float, force: bool = False) -> None:
        nonlocal last_percent_reported
        if not progress_enabled:
            return
        mapped = round(float(_map_staged_progress(stage, stage_percent)), 4)
        if force or mapped != last_percent_reported:
            last_percent_reported = mapped
            try:
                progress_hook(mapped)
            except Exception:
                pass

    def _mark_setup() -> None:
        nonlocal setup_steps_done
        if not progress_enabled:
            return
        setup_steps_done += 1
        pct = (float(setup_steps_done) * 100.0) / max(float(setup_steps_total), 1.0)
        if pct > 100:
            pct = 100.0
        _emit_stage("setup", pct)

    def _emit_work(force: bool = False) -> None:
        if total_work_units <= 0:
            pct = 100.0
        else:
            pct = (float(completed_work_units) * 100.0) / float(total_work_units)
        if pct < 0:
            pct = 0.0
        if pct > 100:
            pct = 100.0
        _emit_stage("work", pct, force=force)

    def _mark_viewport_frame_button_processed() -> None:
        nonlocal completed_work_units
        completed_work_units += 1
        _emit_work()

    _emit_stage("setup", 0, force=True)

    tag_name_by_id = _fetch_map(cur, "select ButtonTagId, ButtonTagName from ButtonTagNames")
    page_name_by_id = _fetch_map(cur, "select PageNameId, PageName from PageNames")
    room_name_by_id = _fetch_map(cur, "select RoomId, Name from Rooms")
    device_columns = _table_columns(cur, "Devices")
    driver_data_columns = _table_columns(cur, "DriverData") if "DriverData" in {row[0] for row in cur.execute("select name from sqlite_master where type='table'").fetchall()} else set()
    driver_config_columns = _table_columns(cur, "DriverConfig") if "DriverConfig" in {row[0] for row in cur.execute("select name from sqlite_master where type='table'").fetchall()} else set()
    _mark_setup()

    cur.execute("select DeviceId, DisplayName, Name from Devices")
    driver_name_by_device_id: dict[int, str] = {}
    for row in cur.fetchall():
        driver_name_by_device_id[int(row["DeviceId"])] = _driver_name(row["DisplayName"] if "DisplayName" in device_columns else None, row["Name"] if "Name" in device_columns else None)

    cur.execute("select * from Variables")
    variables_by_tag: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in cur.fetchall():
        variables_by_tag[int(row["ButtonTagId"] or -1)].append(row)
    _mark_setup()

    cur.execute("select ButtonId from ButtonTextTags")
    button_text_tag_ids = {int(r[0]) for r in cur.fetchall()}

    # Graphics targets should come from explicit ButtonBitmaps mapping when present.
    cur.execute("select name from sqlite_master where type='table' and name='ButtonBitmaps'")
    use_explicit_button_bitmaps = cur.fetchone() is not None
    button_graphics_targets_by_button_id: dict[int, tuple[bool, bool]] = {}
    if use_explicit_button_bitmaps:
        cur.execute("select ButtonId, UpBitmapId, DownBitmapId, IconBitmapId from ButtonBitmaps")
        for row in cur.fetchall():
            button_id = int(row["ButtonId"] or 0)
            if button_id <= 0:
                continue
            existing = button_graphics_targets_by_button_id.get(button_id, (False, False))
            bitmap_enabled = existing[0] or int(row["UpBitmapId"] or -1) != -1 or int(row["DownBitmapId"] or -1) != -1
            icon_enabled = existing[1] or int(row["IconBitmapId"] or -1) != -1
            button_graphics_targets_by_button_id[button_id] = (bitmap_enabled, icon_enabled)

    cur.execute("select * from Macros where ButtonTagId is not null")
    macros_by_tag: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in cur.fetchall():
        macros_by_tag[int(row["ButtonTagId"] or -1)].append(row)
    cur.execute("select * from Macros")
    macros_by_id: dict[int, sqlite3.Row] = {}
    macros_by_system_id: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in cur.fetchall():
        macros_by_id[int(row["MacroId"])] = row
        macros_by_system_id[int(row["SystemMacroId"] or -1)].append(row)

    cur.execute("select MacroId, Type from MacroSteps")
    macro_types_by_macro: dict[int, set[int]] = defaultdict(set)
    for row in cur.fetchall():
        macro_types_by_macro[int(row["MacroId"] or 0)].add(int(row["Type"] or 0))
    macro_non_empty_by_id = {
        macro_id: bool(step_types)
        for macro_id, step_types in macro_types_by_macro.items()
    }
    cur.execute(
        """
        select MacroId, FlagIndex, FlagType
        from MacroStepsView
        where Type = 15
        order by MacroId, StepIndex, MacroStepId
        """
    )
    macro_flag_summary_rows: list[tuple[int, Any, Any]] = []
    for row in cur.fetchall():
        macro_flag_summary_rows.append((int(row["MacroId"] or 0), row["FlagIndex"], row["FlagType"]))
    macro_flag_summaries_by_macro_id = _build_macro_flag_summary_cache(macro_flag_summary_rows)
    _mark_setup()

    cur.execute("select PageId, PageName, RoomId from PagesView")
    page_name_by_page_id: dict[int, str] = {}
    page_room_id_by_page_id: dict[int, int] = {}
    for row in cur.fetchall():
        page_name_by_page_id[int(row["PageId"])] = str(row["PageName"] or "").strip()
        page_room_id_by_page_id[int(row["PageId"])] = int(row["RoomId"] or 0)
    cur.execute("select MacroStepId, MacroId from MacroSteps where Type = 8")
    macro_id_by_step_id: dict[int, int] = {}
    for row in cur.fetchall():
        macro_id_by_step_id[int(row["MacroStepId"] or 0)] = int(row["MacroId"] or 0)

    macro_step_exact_page_by_macro: dict[int, int] = {}
    table_names = {row[0] for row in cur.execute("select name from sqlite_master where type='table'").fetchall()}
    if "MacroPageLink" in table_names:
        cur.execute("select MacroStepId, Page from MacroPageLink")
        for row in cur.fetchall():
            page_id = int(row["Page"] or 0)
            if page_id <= 0 or page_id not in page_name_by_page_id:
                continue
            macro_id = macro_id_by_step_id.get(int(row["MacroStepId"] or 0), 0)
            if macro_id > 0:
                macro_step_exact_page_by_macro[macro_id] = page_id

    cur.execute(
        """
        select msv.MacroId, msv.Type, mpl.TargetPageId, msv.TargetRTIAddress, msr.SelectRoomId, mss.SelectSourceId, mss.SelectSourceRoomId, mro.RoomOffId
        from MacroStepsView msv
        left join MacroPageLinkView mpl on mpl.MacroStepId = msv.MacroStepId and msv.Type = 8
        left join MacroSelectRoom msr on msr.MacroStepId = msv.MacroStepId and msv.Type = 24
        left join MacroSelectSource mss on mss.MacroStepId = msv.MacroStepId and msv.Type = 26
        left join MacroRoomOff mro on mro.MacroStepId = msv.MacroStepId and msv.Type = 27
        order by msv.MacroId, msv.StepIndex, msv.MacroStepId
        """
    )
    macro_step_targets_by_macro: dict[int, list[tuple[int, int]]] = defaultdict(list)
    select_rooms_by_macro: dict[int, list[int]] = defaultdict(list)
    room_offs_by_macro: dict[int, list[int]] = defaultdict(list)
    select_sources_by_macro: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for row in cur.fetchall():
        macro_id = int(row["MacroId"] or 0)
        step_type = int(row["Type"] or 0)
        if step_type == 8:
            for target in _csv_page_targets(row["TargetPageId"], row["TargetRTIAddress"]):
                if target not in macro_step_targets_by_macro[macro_id]:
                    macro_step_targets_by_macro[macro_id].append(target)
        elif step_type == 24:
            select_room_id = int(row["SelectRoomId"] or 0)
            if select_room_id > 0 and select_room_id not in select_rooms_by_macro[macro_id]:
                select_rooms_by_macro[macro_id].append(select_room_id)
        elif step_type == 27:
            room_off_id = int(row["RoomOffId"] or 0)
            if room_off_id != 0 and room_off_id not in room_offs_by_macro[macro_id]:
                room_offs_by_macro[macro_id].append(room_off_id)
        elif step_type == 26:
            select_source_id = int(row["SelectSourceId"] or 0)
            select_source_room_id = int(row["SelectSourceRoomId"] or 0)
            pair = (select_source_id, select_source_room_id)
            if select_source_id > 0 and pair not in select_sources_by_macro[macro_id]:
                select_sources_by_macro[macro_id].append(pair)
    _mark_setup()

    cur.execute(
        """
        select a.*, d.DisplayName, d.Name
        from Activities a
        join Devices d on d.DeviceId = a.DeviceId
        order by a.RoomId, a.Checked desc, a.ActivityOrder, a.ActivitiesId
        """
    )
    activity_target_pages_by_room_and_device: dict[tuple[int, int], list[tuple[int, int]]] = {}
    room_home_target_pages_by_room: dict[int, list[tuple[int, int]]] = {}
    for row in cur.fetchall():
        room_id = int(row["RoomId"] or 0)
        device_id = int(row["DeviceId"] or 0)
        key = (room_id, device_id)
        pagelink_macro_id = int(row["PagelinkMacroId"] or 0)
        if key not in activity_target_pages_by_room_and_device:
            activity_target_pages_by_room_and_device[key] = macro_step_targets_by_macro.get(pagelink_macro_id, [])
        if room_id > 0 and int(row["Checked"] or 0) == 1 and int(row["ActivityOrder"] or 0) == 0 and room_id not in room_home_target_pages_by_room:
            room_home_target_pages_by_room[room_id] = macro_step_targets_by_macro.get(pagelink_macro_id, [])

    variable_command_rows_by_variable_id: dict[int, list[sqlite3.Row]] = defaultdict(list)
    cur.execute(
        """
        select *
        from MacroDeviceCommand
        where VariableId is not null
          and MacroStepId is null
        order by VariableId
        """
    )
    for row in cur.fetchall():
        variable_id = int(row["VariableId"] or 0)
        if variable_id > 0:
            variable_command_rows_by_variable_id[variable_id].append(row)

    cur.execute("select RoomId, SelectedMacroId from RoomEvents where SelectedMacroId is not null order by RoomId, EventType")
    room_event_targets_by_room: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for row in cur.fetchall():
        room_id = int(row["RoomId"] or 0)
        selected_macro_id = int(row["SelectedMacroId"] or 0)
        for target in macro_step_targets_by_macro.get(selected_macro_id, []):
            if target not in room_event_targets_by_room[room_id]:
                room_event_targets_by_room[room_id].append(target)
        for select_source_id, select_source_room_id in select_sources_by_macro.get(selected_macro_id, []):
            for target in _activity_target_page_ids(
                select_source_id,
                select_source_room_id,
                room_id,
                activity_target_pages_by_room_and_device,
            ):
                if target not in room_event_targets_by_room[room_id]:
                    room_event_targets_by_room[room_id].append(target)
    _mark_setup()

    cur.execute("select PageLinkId, DeviceId, ButtonTagId, LinkType, PageId from PageLinks where ButtonTagId is not null")
    page_links_by_device_and_tag: dict[tuple[int, int], sqlite3.Row] = {}
    page_links_by_tag: dict[int, sqlite3.Row] = {}
    for row in cur.fetchall():
        device_id = int(row["DeviceId"] or 0)
        button_tag_id = int(row["ButtonTagId"] or 0)
        if device_id > 0 and button_tag_id > 0:
            page_links_by_device_and_tag[(device_id, button_tag_id)] = row
        page_links_by_tag[button_tag_id] = row
    cur.execute("select distinct ViewPortButtonId from Layers where ViewPortButtonId is not null")
    viewport_button_ids = {int(r[0]) for r in cur.fetchall() if r[0] is not None}
    cur.execute("select SharedLayerId, Name from SharedLayers")
    shared_layer_name_by_id = {int(row["SharedLayerId"]): str(row["Name"] or "") for row in cur.fetchall()}
    shared_layer_buttons_cache: dict[int, list[sqlite3.Row]] = {}
    cur.execute(
        """
        select d.DeviceId, p.PageId, n.PageName
        from RTIDevicePageData p
        join RTIDeviceData d on d.RTIAddress = p.RTIAddress
        left join PageNames n on n.PageNameId = p.PageNameId
        order by d.DeviceId, p.PageOrder, p.PageId
        """
    )
    first_page_target_by_device_id: dict[int, tuple[int, str | None]] = {}
    for row in cur.fetchall():
        device_id = int(row["DeviceId"] or 0)
        if device_id <= 0 or device_id in first_page_target_by_device_id:
            continue
        first_page_target_by_device_id[device_id] = (int(row["PageId"] or 0), str(row["PageName"] or "").strip() or None)
    _mark_setup()

    cur.execute("select * from Events where Enabled = 1")
    event_rows = cur.fetchall()

    driver_data_by_device_id: dict[int, sqlite3.Row] = {}
    driver_data_by_driver_device_id: dict[int, sqlite3.Row] = {}
    if driver_data_columns:
        cur.execute("select * from DriverData")
        for row in cur.fetchall():
            driver_data_by_device_id[int(row["DeviceId"] or -1)] = row
            driver_data_by_driver_device_id[int(row["DriverDeviceId"] or -1)] = row

    driver_config_by_driver_device_id: dict[int, dict[str, str]] = defaultdict(dict)
    if driver_config_columns:
        cur.execute("select DriverDeviceId, Name, Value from DriverConfig")
        for row in cur.fetchall():
            driver_config_by_driver_device_id[int(row["DriverDeviceId"] or -1)][str(row["Name"] or "")] = str(row["Value"] or "")
    _mark_setup()

    out: dict[str, Any] = {
        "source": {
            "file": str(ctx.apex_path),
            "extractedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "events": {"system": [], "driver": []},
        "devices": [],
    }

    for ev in event_rows:
        event_type = int(ev["EventType"] or 0)
        description = str(ev["Description"] or "")
        macro_id = int(ev["MacroId"] or 0)
        driver_id = int(ev["DriverId"] or 0)
        driver_data_row = driver_data_by_device_id.get(driver_id) or driver_data_by_driver_device_id.get(driver_id)
        driver_device_id = int(driver_data_row["DriverDeviceId"] or -1) if driver_data_row is not None and "DriverDeviceId" in driver_data_columns else -1
        driver_config = driver_config_by_driver_device_id.get(driver_device_id, {})
        driver_name = ""
        if driver_id > 0:
            driver_name = driver_name_by_device_id.get(driver_id, "")
            if not driver_name and driver_data_row is not None and "DeviceId" in driver_data_columns:
                driver_name = driver_name_by_device_id.get(int(driver_data_row["DeviceId"] or -1), "")
            if not driver_name and driver_data_row is not None and "DriverId" in driver_data_columns:
                driver_name = str(driver_data_row["DriverId"] or "").strip()
        if event_type == 5 or driver_id > 0:
            driver_category, trigger = _resolve_driver_trigger(
                driver_data_row["SystemEvents"] if driver_data_row is not None and "SystemEvents" in driver_data_columns else None,
                ev["DriverExtraString"],
                driver_config,
            )
            macro_names, macro_steps, macro_step_count = _resolve_driver_action(
                cur,
                macro_id,
                driver_id,
                macros_by_id,
                macros_by_system_id,
                tag_name_by_id,
                driver_data_by_device_id,
                driver_config_by_driver_device_id,
            )
            macro_name = "; ".join(macro_names)
            command_names = [str(step.get("name") or "").strip() for step in macro_steps if str(step.get("type") or "") == "command" and str(step.get("name") or "").strip()]
            command_name = "; ".join(command_names)
            first_action_name = macro_names[0] if macro_names else next((str(step.get("name") or "").strip() for step in macro_steps if str(step.get("name") or "").strip()), "")
        else:
            trigger = _resolve_system_trigger(cur, ev, event_type)
            macro_name = _resolve_system_macro_name(macro_id, macros_by_id, macros_by_system_id, tag_name_by_id)
            macro_names = [macro_name] if macro_name else []
            macro_steps = []
            macro_step_count = 0
            command_names = []
            command_name = ""
        diag = {
            "eventId": int(ev["EventId"]),
            "enabled": True,
            "macro": {
                "systemMacroId": macro_id,
                "macroId": macro_id,
                "scope": {"roomId": 0, "roomName": room_name_by_id.get(0, "Global"), "deviceId": -1, "deviceName": None},
                "buttonTagName": None,
            },
        }
        if driver_id > 0 or event_type == 5:
            out["events"]["driver"].append(
                {
                    "userFacing": {
                        "eventType": "Driver",
                        "driverName": driver_name,
                        "driverCategory": driver_category,
                        "resolvedTrigger": trigger,
                        "firstActionName": first_action_name,
                        "resolvedActions": {
                            "macros": macro_names,
                            "macroSteps": macro_steps,
                        },
                        "macroStepCount": macro_step_count,
                        "testTargets": _event_test_targets(macro_names, macro_steps),
                    },
                    "diagnostics": {
                        **diag,
                        "driverId": driver_id,
                        "driverName": driver_name,
                        "driverExtraString": ev["DriverExtraString"] or "",
                        "macroNames": macro_names,
                        "commandName": command_name,
                        "commandNames": command_names,
                    },
                }
            )
        else:
            out["events"]["system"].append(
                {
                    "userFacing": {
                        "eventType": _event_type_name(event_type),
                        "description": description,
                        "resolvedTrigger": trigger,
                        "macroName": macro_name,
                        "macroNames": macro_names,
                        "commandName": command_name,
                        "commandNames": command_names,
                        "testTargets": _event_test_targets(macro_names, []),
                    },
                    "diagnostics": {
                        **diag,
                        "description": description,
                        "resolvedTrigger": trigger,
                        "macroName": macro_name,
                        "macroNames": macro_names,
                        "commandName": command_name,
                        "commandNames": command_names,
                    },
                }
            )

    cur.execute(
        """
        select rd.RTIAddress, rd.DeviceId, rd.CloneRTIAddress, rd.ScreenPortraitWidth, rd.ScreenPortraitHeight,
               rd.ScreenLandscapeWidth, rd.ScreenLandscapeHeight, rd.SupportedOrientations,
               rd.ScreenWidth, rd.ScreenHeight, d.DisplayName, d.Name
        from RTIDeviceData rd join Devices d on d.DeviceId = rd.DeviceId
        where coalesce(rd.CloneRTIAddress, 0) <= 0
        order by d.DisplayOrder, rd.RTIAddress
        """
    )
    device_rows = cur.fetchall()

    if progress_enabled:
        rti_addresses = [int(row["RTIAddress"] or 0) for row in device_rows]
        valid_rti_addresses = [addr for addr in rti_addresses if addr > 0]
        if valid_rti_addresses:
            placeholders = ",".join("?" for _ in valid_rti_addresses)
            cur.execute(
                f"""
                select count(*)
                from RTIDeviceButtonData b
                join Layers l on l.SharedLayerId = b.SharedLayerId
                join RTIDevicePageData p on p.PageId = l.PageId
                where l.ViewPortButtonId is null
                  and p.RTIAddress in ({placeholders})
                """,
                tuple(valid_rti_addresses),
            )
            row = cur.fetchone()
            total_work_units += int((row[0] if row else 0) or 0)

            cur.execute(
                f"""
                select distinct l.ViewPortButtonId
                from Layers l
                join RTIDevicePageData p on p.PageId = l.PageId
                where l.ViewPortButtonId is not null
                  and p.RTIAddress in ({placeholders})
                """,
                tuple(valid_rti_addresses),
            )
            selected_viewport_ids = [int(r[0]) for r in cur.fetchall() if r[0] is not None]
            if selected_viewport_ids:
                vp_placeholders = ",".join("?" for _ in selected_viewport_ids)
                cur.execute(
                    f"""
                    select count(*)
                    from RTIDeviceButtonData b
                    join Layers l on l.SharedLayerId = b.SharedLayerId
                    where l.ViewPortButtonId in ({vp_placeholders})
                    """,
                    tuple(selected_viewport_ids),
                )
                row = cur.fetchone()
                total_work_units += int((row[0] if row else 0) or 0)
        _mark_setup()
        _emit_stage("setup", 100, force=True)
        _emit_work(force=True)

    for drow in device_rows:
        device_id = int(drow["DeviceId"])
        rti_address = int(drow["RTIAddress"])
        portrait_supported, landscape_supported = _device_orientation_support(
            drow["SupportedOrientations"] if "SupportedOrientations" in drow.keys() else 0,
            drow["ScreenPortraitWidth"] if "ScreenPortraitWidth" in drow.keys() else 0,
            drow["ScreenPortraitHeight"] if "ScreenPortraitHeight" in drow.keys() else 0,
            drow["ScreenLandscapeWidth"] if "ScreenLandscapeWidth" in drow.keys() else 0,
            drow["ScreenLandscapeHeight"] if "ScreenLandscapeHeight" in drow.keys() else 0,
            drow["ScreenWidth"] if "ScreenWidth" in drow.keys() else 0,
            drow["ScreenHeight"] if "ScreenHeight" in drow.keys() else 0,
        )
        portrait_resolution = _device_resolution(
            portrait_supported,
            drow["ScreenPortraitWidth"] if "ScreenPortraitWidth" in drow.keys() else 0,
            drow["ScreenPortraitHeight"] if "ScreenPortraitHeight" in drow.keys() else 0,
            drow["ScreenWidth"] if "ScreenWidth" in drow.keys() else 0,
            drow["ScreenHeight"] if "ScreenHeight" in drow.keys() else 0,
        )
        landscape_resolution = _device_resolution(
            landscape_supported,
            drow["ScreenLandscapeWidth"] if "ScreenLandscapeWidth" in drow.keys() else 0,
            drow["ScreenLandscapeHeight"] if "ScreenLandscapeHeight" in drow.keys() else 0,
            drow["ScreenWidth"] if "ScreenWidth" in drow.keys() else 0,
            drow["ScreenHeight"] if "ScreenHeight" in drow.keys() else 0,
        )
        cur.execute(
            """
            select cr.RoomId, rm.Name
            from ControllerRoomList cr
            join Rooms rm on rm.RoomId = cr.RoomId
            where cr.RTIAddress = ?
            order by cr.ControllerRoomOrder, cr.RoomId
            """,
            (rti_address,),
        )
        diag_rooms = [{"roomId": int(row["RoomId"]), "roomName": str(row["Name"] or "")} for row in cur.fetchall()]
        lowest_nonzero_device_room_id = min((int(room["roomId"]) for room in diag_rooms if int(room["roomId"]) > 0), default=None)
        cur.execute(
            """
            select * from RTIDevicePageData where RTIAddress = ? order by PageOrder, PageId
            """,
            (rti_address,),
        )
        page_rows = cur.fetchall()

        user_pages: list[dict[str, Any]] = []
        diag_pages: list[dict[str, Any]] = []

        for prow in page_rows:
            page_id = int(prow["PageId"])
            page_name = page_name_by_id.get(int(prow["PageNameId"] or -1), "")
            page_room_id = page_room_id_by_page_id.get(page_id, 0)
            page_rti_address = int(prow["RTIAddress"] or 0)

            cur.execute("select * from Layers where PageId = ? order by LayerOrder, LayerId", (page_id,))
            page_layers = cur.fetchall()
            user_layers: list[dict[str, Any]] = []
            diag_ui_items: list[dict[str, Any]] = []
            diag_buttons: list[dict[str, Any]] = []
            diag_viewports: list[dict[str, Any]] = []

            for layer in [l for l in page_layers if l["ViewPortButtonId"] is None]:
                layer_user = {
                    "layerName": shared_layer_name_by_id.get(int(layer["SharedLayerId"]), ""),
                    "layerOrder": int(layer["LayerOrder"] or 0),
                    "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": [], "emptyTag": [], "uiItems": []},
                    "viewports": [],
                }
                for b in _shared_layer_buttons(cur, int(layer["SharedLayerId"]), shared_layer_buttons_cache):
                    button_id = int(b["ButtonId"])
                    user_button, diag_button = _resolve_button(
                        cur,
                        b,
                        device_id,
                    tag_name_by_id,
                    variables_by_tag,
                    button_text_tag_ids,
                    macros_by_tag,
                    macro_non_empty_by_id,
                    page_links_by_device_and_tag,
                    page_links_by_tag,
                    first_page_target_by_device_id,
                    page_name_by_page_id,
                    room_name_by_id,
                    driver_name_by_device_id,
                    macro_step_exact_page_by_macro,
                        macro_step_targets_by_macro,
                        room_event_targets_by_room,
                        select_rooms_by_macro,
                        room_offs_by_macro,
                        select_sources_by_macro,
                        activity_target_pages_by_room_and_device,
                        room_home_target_pages_by_room,
                        variable_command_rows_by_variable_id,
                        macro_flag_summaries_by_macro_id,
                        button_graphics_targets_by_button_id,
                        use_explicit_button_bitmaps,
                        page_id,
                        (int(prow["SourceDeviceId"]) if prow["SourceDeviceId"] is not None else None),
                        page_room_id,
                        page_rti_address,
                        lowest_nonzero_device_room_id,
                        layer_id=int(layer["LayerId"]),
                        shared_layer_id=int(layer["SharedLayerId"]),
                        layer_name_resolved=shared_layer_name_by_id.get(int(layer["SharedLayerId"]), ""),
                        layer_room_id=(int(layer["RoomId"]) if layer["RoomId"] is not None else None),
                        layer_source_id=(int(layer["SourceId"]) if layer["SourceId"] is not None else None),
                        page_layer_room_id=None,
                        page_layer_source_id=None,
                        layer_order=int(layer["LayerOrder"] or 0),
                        button_order=int(b["ButtonOrder"] or 0),
                        frame_number=int(b["FrameNumber"] or 0),
                        host_viewport_button_id=None,
                        portrait_supported=portrait_supported,
                        landscape_supported=landscape_supported,
                        portrait_resolution=portrait_resolution,
                        landscape_resolution=landscape_resolution,
                    )
                    diag_buttons.append(diag_button)
                    completed_work_units += 1
                    _emit_work()

                    if button_id in viewport_button_ids:
                        frames = _resolve_viewport_frames(
                            cur,
                            button_id,
                            device_id,
                            tag_name_by_id,
                            variables_by_tag,
                            button_text_tag_ids,
                            macros_by_tag,
                            macro_non_empty_by_id,
                            page_links_by_device_and_tag,
                            page_links_by_tag,
                            first_page_target_by_device_id,
                            page_name_by_page_id,
                            room_name_by_id,
                            driver_name_by_device_id,
                            macro_step_exact_page_by_macro,
                            macro_step_targets_by_macro,
                            room_event_targets_by_room,
                            select_rooms_by_macro,
                            room_offs_by_macro,
                            select_sources_by_macro,
                            activity_target_pages_by_room_and_device,
                            room_home_target_pages_by_room,
                            variable_command_rows_by_variable_id,
                            macro_flag_summaries_by_macro_id,
                            button_graphics_targets_by_button_id,
                            use_explicit_button_bitmaps,
                            page_id,
                            (int(prow["SourceDeviceId"]) if prow["SourceDeviceId"] is not None else None),
                            page_room_id,
                            page_rti_address,
                            lowest_nonzero_device_room_id,
                            (int(layer["RoomId"]) if layer["RoomId"] is not None else None),
                            (int(layer["SourceId"]) if layer["SourceId"] is not None else None),
                            portrait_supported,
                            landscape_supported,
                            portrait_resolution,
                            landscape_resolution,
                            shared_layer_buttons_cache,
                            _mark_viewport_frame_button_processed,
                        )
                        layer_user["viewports"].append(
                            {
                                "viewportIdentity": {"viewportButtonId": button_id},
                                "viewportUI": {
                                    "navigationMode": "verticalScroll" if int(b["ViewPortVerticalScroll"] or 0) != 0 else "page",
                                    "orientations": user_button["buttonUI"]["orientations"],
                                },
                                "layers": frames["viewport_layers"],
                            }
                        )
                        diag_viewports.append(
                            {
                                "viewportButtonId": button_id,
                                "source": {
                                    "viewPortVerticalScroll": int(b["ViewPortVerticalScroll"] or 0),
                                    "visibleOrientations": int(b["VisibleOrientations"] or 0),
                                },
                                "layerLinks": frames["layer_links"],
                                "frames": frames["diag_frames"],
                            }
                        )
                        diag_ui_items = _merge_diag_ui_items(diag_ui_items, frames["ui_item_button_ids"])
                        continue

                    category = _classify_user_button_category(
                        button=user_button,
                        has_tag_field=diag_button["identifiers"].get("buttonTagId") is not None,
                        raw_text=str(diag_button["identifiers"].get("text") or ""),
                        has_macros_target=bool(user_button["testTargets"].get("macros")),
                        has_any_variable_target=_has_any_variable_target(user_button),
                    )
                    layer_user["buttonCategories"][category].append(user_button)
                    if category == "uiItems":
                        diag_ui_items.append({"buttonId": button_id})

                user_layers.append(layer_user)

            user_pages.append({"pageName": page_name, "layers": user_layers})
            diag_pages.append(
                {
                    "pageId": page_id,
                    "pageName": page_name,
                    "pageOrder": int(prow["PageOrder"] or 0),
                    "pageNumber": len(diag_pages) + 1,
                    "uiItems": diag_ui_items,
                    "buttons": diag_buttons,
                    "viewports": diag_viewports,
                }
            )

        out["devices"].append(
            {
                "userFacing": {
                    "displayName": drow["DisplayName"] or drow["Name"] or f"Device {device_id}",
                    "deviceUI": {
                        "portrait": {
                            "supported": portrait_supported,
                            "resolution": portrait_resolution,
                        },
                        "landscape": {
                            "supported": landscape_supported,
                            "resolution": landscape_resolution,
                        },
                    },
                    "pages": user_pages,
                },
                "diagnostics": {
                    "deviceId": device_id,
                    "deviceName": drow["Name"] or drow["DisplayName"],
                    "displayName": drow["DisplayName"] or drow["Name"],
                    "rtiAddress": rti_address,
                    "isClonedController": False,
                    "rooms": diag_rooms,
                    "pages": diag_pages,
                },
            }
        )

    _emit_work(force=True)
    _emit_stage("finalize", 35, force=True)

    con.close()
    # Reserve final completion for script-level validate/write heartbeat and handoff.
    _emit_stage("finalize", 90, force=True)
    return out


def _resolve_viewport_frames(
    cur: sqlite3.Cursor,
    viewport_button_id: int,
    current_device_id: int,
    tag_name_by_id: dict[int, str],
    variables_by_tag: dict[int, list[sqlite3.Row]],
    button_text_tag_ids: set[int],
    macros_by_tag: dict[int, list[sqlite3.Row]],
    macro_non_empty_by_id: dict[int, bool],
    page_links_by_device_and_tag: dict[tuple[int, int], sqlite3.Row],
    page_links_by_tag: dict[int, sqlite3.Row],
    first_page_target_by_device_id: dict[int, tuple[int, str | None]],
    page_name_by_page_id: dict[int, str],
    room_name_by_id: dict[int, str],
    source_name_by_device_id: dict[int, str],
    macro_step_exact_page_by_macro: dict[int, int],
    macro_step_targets_by_macro: dict[int, list[tuple[int, int]]],
    room_event_targets_by_room: dict[int, list[tuple[int, int]]],
    select_rooms_by_macro: dict[int, list[int]],
    room_offs_by_macro: dict[int, list[int]],
    select_sources_by_macro: dict[int, list[tuple[int, int]]],
    activity_target_pages_by_room_and_device: dict[tuple[int, int], list[tuple[int, int]]],
    room_home_target_pages_by_room: dict[int, list[tuple[int, int]]],
    variable_command_rows_by_variable_id: dict[int, list[sqlite3.Row]],
    macro_flag_summaries_by_macro_id: dict[int, list[str]],
    button_graphics_targets_by_button_id: dict[int, tuple[bool, bool]],
    use_explicit_button_bitmaps: bool,
    page_id: int,
    page_source_device_id: int | None,
    page_room_id: int,
    current_rti_address: int,
    global_room_fallback_id: int | None,
    parent_layer_room_id: int | None,
    parent_layer_source_id: int | None,
    portrait_supported: bool = True,
    landscape_supported: bool = True,
    portrait_resolution: dict[str, int] | None = None,
    landscape_resolution: dict[str, int] | None = None,
    shared_layer_buttons_cache: dict[int, list[sqlite3.Row]] | None = None,
    button_processed_hook: Any = None,
) -> dict[str, Any]:
    cur.execute("select * from Layers where ViewPortButtonId = ? order by LayerOrder, LayerId", (viewport_button_id,))
    child_layers = cur.fetchall()
    layer_buttons_cache = shared_layer_buttons_cache if isinstance(shared_layer_buttons_cache, dict) else {}

    frame_user: dict[int, dict[str, Any]] = {}
    frame_diag: dict[int, dict[str, Any]] = {}
    layer_links: list[dict[str, Any]] = []
    viewport_layers: list[dict[str, Any]] = []
    viewport_ui_item_button_ids: list[int] = []
    frame_button_count = 0

    cur.execute("select SharedLayerId, Name from SharedLayers")
    shared_layer_name_by_id = {int(row["SharedLayerId"]): str(row["Name"] or "") for row in cur.fetchall()}

    for layer in child_layers:
        layer_frames: dict[int, dict[str, Any]] = {}
        layer_links.append(
            {
                "layerId": int(layer["LayerId"]),
                "sharedLayerId": int(layer["SharedLayerId"]),
                "layerOrder": int(layer["LayerOrder"] or 0),
                "sourceId": int(layer["SourceId"] or 0),
                "roomId": int(layer["RoomId"] or 0),
            }
        )
        for b in _shared_layer_buttons(cur, int(layer["SharedLayerId"]), layer_buttons_cache):
            frame_button_count += 1
            if callable(button_processed_hook):
                try:
                    button_processed_hook()
                except Exception:
                    pass
            frame_id = int(b["FrameNumber"] or 0)
            frame_user.setdefault(
                frame_id,
                {"frameId": frame_id, "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": [], "emptyTag": [], "uiItems": []}},
            )
            frame_diag.setdefault(frame_id, {"frameId": frame_id, "buttons": []})
            layer_frames.setdefault(
                frame_id,
                {"frameId": frame_id, "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": [], "emptyTag": [], "uiItems": []}},
            )

            user_button, diag_button = _resolve_button(
                cur,
                b,
                current_device_id,
                    tag_name_by_id,
                    variables_by_tag,
                    button_text_tag_ids,
                    macros_by_tag,
                    macro_non_empty_by_id,
                    page_links_by_device_and_tag,
                    page_links_by_tag,
                    first_page_target_by_device_id,
                    page_name_by_page_id,
                    room_name_by_id,
                    source_name_by_device_id,
                    macro_step_exact_page_by_macro,
                macro_step_targets_by_macro,
                room_event_targets_by_room,
                select_rooms_by_macro,
                room_offs_by_macro,
                select_sources_by_macro,
                activity_target_pages_by_room_and_device,
                room_home_target_pages_by_room,
                variable_command_rows_by_variable_id,
                macro_flag_summaries_by_macro_id,
                button_graphics_targets_by_button_id,
                use_explicit_button_bitmaps,
                page_id,
                page_source_device_id,
                page_room_id,
                current_rti_address,
                global_room_fallback_id,
                layer_id=int(layer["LayerId"]),
                shared_layer_id=int(layer["SharedLayerId"]),
                layer_name_resolved=shared_layer_name_by_id.get(int(layer["SharedLayerId"]), ""),
                layer_room_id=(int(layer["RoomId"]) if layer["RoomId"] is not None else None),
                layer_source_id=(int(layer["SourceId"]) if layer["SourceId"] is not None else None),
                page_layer_room_id=parent_layer_room_id,
                page_layer_source_id=parent_layer_source_id,
                layer_order=int(layer["LayerOrder"] or 0),
                button_order=int(b["ButtonOrder"] or 0),
                frame_number=int(b["FrameNumber"] or 0),
                host_viewport_button_id=int(viewport_button_id),
                portrait_supported=portrait_supported,
                landscape_supported=landscape_supported,
                portrait_resolution=portrait_resolution or {"width": 0, "height": 0},
                landscape_resolution=landscape_resolution or {"width": 0, "height": 0},
            )
            frame_diag[frame_id]["buttons"].append(diag_button)
            category = _classify_user_button_category(
                button=user_button,
                has_tag_field=diag_button["identifiers"].get("buttonTagId") is not None,
                raw_text=str(diag_button["identifiers"].get("text") or ""),
                has_macros_target=bool(user_button["testTargets"].get("macros")),
                has_any_variable_target=_has_any_variable_target(user_button),
            )
            frame_user[frame_id]["buttonCategories"][category].append(user_button)
            layer_frames[frame_id]["buttonCategories"][category].append(user_button)
            if category == "uiItems":
                viewport_ui_item_button_ids.append(int(diag_button["buttonId"]))

        viewport_layers.append(
            {
                "layerName": shared_layer_name_by_id.get(int(layer["SharedLayerId"]), ""),
                "layerOrder": int(layer["LayerOrder"] or 0),
                "frames": [layer_frames[k] for k in sorted(layer_frames)],
            }
        )

    return {
        "user_frames": [frame_user[k] for k in sorted(frame_user)],
        "diag_frames": [frame_diag[k] for k in sorted(frame_diag)],
        "layer_links": layer_links,
        "viewport_layers": viewport_layers,
        "ui_item_button_ids": viewport_ui_item_button_ids,
        "frame_button_count": frame_button_count,
    }


def _is_screen_label(button: dict[str, Any]) -> bool:
    t = button["testTargets"]
    has_display = bool(t["text"] or t["variables"]["Text"])
    page_link_enabled = bool(t.get("pageLink"))
    return bool(not page_link_enabled and not t["macros"] and not t["macroSteps"] and has_display and button["buttonIdentity"].get("buttonType") is None)


def json_load(path: Path) -> Any:
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
