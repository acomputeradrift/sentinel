from __future__ import annotations

import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_STYLE_TO_TYPE = {9: "Slider", 7: "Toggle", 11: "LevelIndicatorBar"}
_TOKEN_ONLY_RE = re.compile(r"^\s*\$%TAG!.*?%\$\s*$", re.IGNORECASE | re.DOTALL)
_DRIVER_TOKEN_RE = re.compile(r"%%([^%]+)%%")


@dataclass
class ExtractContext:
    apex_path: Path
    project_structure_path: Path


def _is_token_only_text(text: str | None) -> bool:
    return bool(text and _TOKEN_ONLY_RE.match(text))


def _empty(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _fetch_map(cur: sqlite3.Cursor, query: str, key_idx: int = 0, val_idx: int = 1) -> dict[Any, Any]:
    cur.execute(query)
    out: dict[Any, Any] = {}
    for row in cur.fetchall():
        out[row[key_idx]] = row[val_idx]
    return out


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


def _resolve_driver_trigger(system_events_xml: str | None, driver_extra_string: str | None, driver_config: dict[str, str]) -> str:
    tag = str(driver_extra_string or "").strip()
    if not tag:
        return ""
    xml_text = str(system_events_xml or "").strip()
    if not xml_text:
        return tag
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return tag
    matched_name = ""
    for event_node in root.findall(".//event"):
        if str(event_node.attrib.get("tag") or "").strip() == tag:
            matched_name = str(event_node.attrib.get("name") or "").strip()
            break
    if not matched_name:
        return tag

    resolved = _expand_driver_tokens(matched_name, driver_config)
    return resolved or tag


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

        function_name = str(function_node.attrib.get("name") or export_name).strip()
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


def _resolve_driver_action(
    cur: sqlite3.Cursor,
    macro_id: int,
    driver_id: int,
    macros_by_id: dict[int, sqlite3.Row],
    macros_by_system_id: dict[int, list[sqlite3.Row]],
    tag_name_by_id: dict[int, str],
    driver_data_by_device_id: dict[int, sqlite3.Row],
    driver_config_by_driver_device_id: dict[int, dict[str, str]],
) -> tuple[list[str], list[str]]:
    wrapper_rows = [
        row
        for row in macros_by_system_id.get(macro_id, [])
        if int(row["MacroId"] or -1) != macro_id and int(row["DeviceId"] or -1) == driver_id
    ]
    root_row = macros_by_id.get(macro_id)
    candidate_rows = wrapper_rows or ([root_row] if root_row is not None else [])

    macro_names: list[str] = []
    for row in candidate_rows:
        wrapper_name = _usable_name(tag_name_by_id.get(int(row["ButtonTagId"] or -1)))
        if wrapper_name:
            macro_names.append(wrapper_name)
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
        return macro_names, []

    command_names: list[str] = []
    comment_names: list[str] = []
    for row in candidate_rows:
        command_summaries = _resolve_direct_command_summaries(
            cur,
            int(row["MacroId"]),
            driver_data_by_device_id,
            driver_config_by_driver_device_id,
        )
        command_names.extend(command_summaries)

        cur.execute(
            "select CommentText from MacroStepsView where MacroId = ? and Type = 17 order by StepIndex, MacroStepId",
            (int(row["MacroId"]),),
        )
        for step in cur.fetchall():
            comment = str(step[0] or "").strip()
            if comment:
                comment_names.append(comment)

    comment_names = _dedupe_non_empty(comment_names)
    if comment_names:
        return comment_names, []
    return [], _dedupe_non_empty(command_names)


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


def _event_test_targets(macro_names: list[str], command_names: list[str]) -> dict[str, bool]:
    targets = {"Trigger": True}
    if macro_names:
        targets["Macro" if len(macro_names) == 1 else "Macros"] = True
    if command_names:
        targets["Command" if len(command_names) == 1 else "Commands"] = True
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


def _sense_action_text(cur: sqlite3.Cursor, sense_action: int, sense_expander_id: int) -> str:
    cur.execute("select Mask from SenseModeMap where RTIAddress = 0 and ExpanderId = ?", (sense_expander_id,))
    row = cur.fetchone()
    mask = int(row["Mask"] or 0) if row else 0
    is_closure = bool(mask & 1)
    if is_closure:
        return "closes" if sense_action == 0 else "opens"
    return "goes high" if sense_action == 0 else "goes low"


def _decode_scheduled_trigger(ev: sqlite3.Row) -> str:
    if int(_row_value(ev, "DailyAstronomical", 0) or 0) == 1:
        raw = bytes(_row_value(ev, "DailyStartTime", b"") or b"")
        raw_hex = raw.hex().upper()
        if raw_hex.endswith("0000"):
            return "On sunrise"
        if raw_hex.endswith("0001"):
            return "On sunset"
        return "On scheduled astronomical event"

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
        action = _sense_action_text(cur, sense_action, sense_expander_id)
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


def _orientation_visibility(mask: int) -> dict[str, bool]:
    if mask == 3:
        return {"portrait": True, "landscape": True}
    if mask == 2:
        return {"portrait": True, "landscape": False}
    # Strong working inference used to preserve app behavior until mask=1 is explicitly locked.
    if mask == 1:
        return {"portrait": False, "landscape": True}
    return {"portrait": False, "landscape": False}


def _button_ui(button_row: sqlite3.Row) -> dict[str, Any]:
    vis = _orientation_visibility(int(button_row["VisibleOrientations"] or 0))
    return {
        "fontSize": int(button_row["TextSize"] or 0),
        "orientations": {
            "portrait": {
                "visible": vis["portrait"],
                "coordinates": _coords(
                    button_row["ButtonTop"],
                    button_row["ButtonLeft"],
                    button_row["ButtonHeight"],
                    button_row["ButtonWidth"],
                ),
            },
            "landscape": {
                "visible": vis["landscape"],
                "coordinates": _coords(
                    button_row["ButtonTopAlt"],
                    button_row["ButtonLeftAlt"],
                    button_row["ButtonHeightAlt"],
                    button_row["ButtonWidthAlt"],
                ),
            },
        },
    }


def _is_hard_button(button_ui: dict[str, Any]) -> bool:
    portrait = button_ui["orientations"]["portrait"]["coordinates"]
    return int(portrait["height"] or 0) == 0 and int(portrait["width"] or 0) == 0


def _resolve_button(cur: sqlite3.Cursor, button_row: sqlite3.Row, tag_name_by_id: dict[int, str], variables_by_tag: dict[int, list[sqlite3.Row]], button_text_tag_ids: set[int], macros_by_tag: dict[int, list[sqlite3.Row]], page_links_by_tag: dict[int, sqlite3.Row]) -> tuple[dict[str, Any], dict[str, Any], bool]:
    button_id = int(button_row["ButtonId"])
    tag_id = int(button_row["ButtonTagId"] or -1)
    text = button_row["Text"] or ""
    style = int(button_row["ButtonStyle"] or 0)
    button_type = _STYLE_TO_TYPE.get(style)
    tag_name = tag_name_by_id.get(tag_id)

    variables_rows = variables_by_tag.get(tag_id, []) if tag_id > 0 else []
    object_tokens = [str(v["ObjectData"] or "") for v in variables_rows]
    button_text_tokens = [str(v["ButtonText"] or "") for v in variables_rows]

    has_var_text = any(not _empty(v["ButtonText"]) for v in variables_rows) or button_id in button_text_tag_ids or _is_token_only_text(text)
    has_literal_text = not _empty(text) and not _is_token_only_text(text)

    value_enabled = any("@DDL" in tok for tok in object_tokens)
    state_enabled = any("@DDS" in tok for tok in object_tokens)
    command_enabled = bool(style == 9 and value_enabled)

    reversed_enabled = any(not _empty(v["ReversedData"]) for v in variables_rows)
    inactive_enabled = any(not _empty(v["InactiveData"]) for v in variables_rows)
    visible_enabled = any(not _empty(v["VisibleData"]) for v in variables_rows)

    tag_macro_rows = macros_by_tag.get(tag_id, []) if tag_id > 0 else []
    macro_non_empty = any(_has_non_empty_macro(cur, int(m["MacroId"])) for m in tag_macro_rows)
    has_macro_target = bool(tag_name) and macro_non_empty

    page_link_row = page_links_by_tag.get(tag_id) if tag_id > 0 else None
    page_link_enabled = page_link_row is not None
    target_page_id = int(page_link_row["PageId"]) if page_link_row and page_link_row["PageId"] is not None else None
    page_link_id = int(page_link_row["PageLinkId"]) if page_link_row and page_link_row["PageLinkId"] is not None else None

    button_ui = _button_ui(button_row)
    is_hard = _is_hard_button(button_ui)

    user_button = {
        "buttonIdentity": {
            "buttonTagName": tag_name,
            "text": text,
            "buttonType": button_type,
        },
        "buttonUI": button_ui,
        "testTargets": {
            "text": has_literal_text,
            "macro": has_macro_target,
            "variables": {
                "Text": has_var_text,
                "Reversed": reversed_enabled,
                "Inactive": inactive_enabled,
                "Visible": visible_enabled,
                "Value": value_enabled,
                "State": state_enabled,
                "Command": command_enabled,
            },
            "pageLink": {
                "enabled": page_link_enabled,
                "targetPageId": target_page_id,
            },
        },
    }

    diag_button = {
        "buttonId": button_id,
        "buttonTagName": tag_name,
        "identifiers": {"buttonTagId": tag_id if tag_id > 0 else None, "text": text},
        "testTargets": {
            "macro": {
                "scope": "Global",
                "scopeType": "Global | Room | Source | Controller",
                "globalMacroId": tag_macro_rows[0]["MacroId"] if tag_macro_rows else None,
                "deviceMacroId": None,
                "resolvedCommand": None,
                "isEmpty": not macro_non_empty if tag_macro_rows else False,
            },
            "variableDetails": {
                "Text": {"enabled": has_var_text, "rawButtonText": next((t for t in button_text_tokens if t), None), "resolvedName": None},
                "Reversed": {"enabled": reversed_enabled, "source": "ReversedData" if reversed_enabled else None},
                "Inactive": {"enabled": inactive_enabled, "source": "InactiveData" if inactive_enabled else None},
                "Visible": {"enabled": visible_enabled, "source": "VisibleData" if visible_enabled else None},
                "Value": {"enabled": value_enabled, "source": "ObjectData" if value_enabled else None, "objectRef": next((t for t in object_tokens if "@DDL" in t), None)},
                "State": {"enabled": state_enabled, "source": "ObjectData" if state_enabled else None, "objectRef": next((t for t in object_tokens if "@DDS" in t), None)},
                "Command": {"enabled": command_enabled, "source": "driverFunction+controlType" if command_enabled else None, "controlType": button_type, "driverFunction": None, "pairedMacroFunction": None},
            },
            "pageLink": {"pageLinkId": page_link_id, "targetPageId": target_page_id, "targetPageName": None},
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
    )
    is_ui_item = bool(tag_id <= 0 and _empty(text) and not has_macro_target and not has_any_variable_target)
    return user_button, diag_button, is_hard or is_ui_item


def extract_project_data(ctx: ExtractContext) -> dict[str, Any]:
    _ = json_load(ctx.project_structure_path)
    con = sqlite3.connect(ctx.apex_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    tag_name_by_id = _fetch_map(cur, "select ButtonTagId, ButtonTagName from ButtonTagNames")
    page_name_by_id = _fetch_map(cur, "select PageNameId, PageName from PageNames")
    room_name_by_id = _fetch_map(cur, "select RoomId, Name from Rooms")
    device_columns = _table_columns(cur, "Devices")
    driver_data_columns = _table_columns(cur, "DriverData") if "DriverData" in {row[0] for row in cur.execute("select name from sqlite_master where type='table'").fetchall()} else set()
    driver_config_columns = _table_columns(cur, "DriverConfig") if "DriverConfig" in {row[0] for row in cur.execute("select name from sqlite_master where type='table'").fetchall()} else set()

    cur.execute("select DeviceId, DisplayName, Name from Devices")
    driver_name_by_device_id: dict[int, str] = {}
    for row in cur.fetchall():
        driver_name_by_device_id[int(row["DeviceId"])] = _driver_name(row["DisplayName"] if "DisplayName" in device_columns else None, row["Name"] if "Name" in device_columns else None)

    cur.execute("select * from Variables")
    variables_by_tag: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in cur.fetchall():
        variables_by_tag[int(row["ButtonTagId"] or -1)].append(row)

    cur.execute("select ButtonId from ButtonTextTags")
    button_text_tag_ids = {int(r[0]) for r in cur.fetchall()}

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

    cur.execute("select PageLinkId, ButtonTagId, PageId from PageLinks where ButtonTagId is not null")
    page_links_by_tag: dict[int, sqlite3.Row] = {}
    for row in cur.fetchall():
        page_links_by_tag[int(row["ButtonTagId"])] = row
    cur.execute("select distinct ViewPortButtonId from Layers where ViewPortButtonId is not null")
    viewport_button_ids = {int(r[0]) for r in cur.fetchall() if r[0] is not None}

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
            trigger = _resolve_driver_trigger(
                driver_data_row["SystemEvents"] if driver_data_row is not None and "SystemEvents" in driver_data_columns else None,
                ev["DriverExtraString"],
                driver_config,
            )
            macro_names, command_names = _resolve_driver_action(
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
            command_name = "; ".join(command_names)
            first_action_name = (macro_names + command_names)[0] if (macro_names or command_names) else ""
        else:
            trigger = _resolve_system_trigger(cur, ev, event_type)
            macro_name = _resolve_system_macro_name(macro_id, macros_by_id, macros_by_system_id, tag_name_by_id)
            macro_names = [macro_name] if macro_name else []
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
                        "resolvedTrigger": trigger,
                        "firstActionName": first_action_name,
                        "resolvedActions": {
                            "macros": macro_names,
                            "commands": command_names,
                        },
                        "testTargets": _event_test_targets(macro_names, command_names),
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
                        "testTargets": _event_test_targets(macro_names, command_names),
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
               rd.ScreenLandscapeWidth, rd.ScreenLandscapeHeight, d.DisplayName, d.Name
        from RTIDeviceData rd join Devices d on d.DeviceId = rd.DeviceId
        where coalesce(rd.CloneRTIAddress, 0) <= 0
        order by d.DisplayOrder, rd.RTIAddress
        """
    )
    device_rows = cur.fetchall()

    for drow in device_rows:
        device_id = int(drow["DeviceId"])
        rti_address = int(drow["RTIAddress"])
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

            cur.execute("select * from Layers where PageId = ? order by LayerOrder, LayerId", (page_id,))
            page_layers = cur.fetchall()
            user_cats = {"screenLabels": [], "screenButtons": [], "hardButtons": []}
            diag_ui_items: list[dict[str, Any]] = []
            diag_buttons: list[dict[str, Any]] = []
            user_viewports: list[dict[str, Any]] = []
            diag_viewports: list[dict[str, Any]] = []

            # page-level buttons
            for layer in [l for l in page_layers if l["ViewPortButtonId"] is None]:
                cur.execute("select * from RTIDeviceButtonData where SharedLayerId = ? order by ButtonOrder, ButtonId", (int(layer["SharedLayerId"]),))
                for b in cur.fetchall():
                    button_id = int(b["ButtonId"])
                    user_button, diag_button, is_special = _resolve_button(cur, b, tag_name_by_id, variables_by_tag, button_text_tag_ids, macros_by_tag, page_links_by_tag)
                    diag_buttons.append(diag_button)

                    if button_id in viewport_button_ids:
                        frames = _resolve_viewport_frames(cur, button_id, tag_name_by_id, variables_by_tag, button_text_tag_ids, macros_by_tag, page_links_by_tag)
                        user_viewports.append(
                            {
                                "viewportIdentity": {"viewportButtonId": button_id},
                                "viewportUI": {
                                    "navigationMode": "verticalScroll" if int(b["ViewPortVerticalScroll"] or 0) != 0 else "page",
                                    "orientations": user_button["buttonUI"]["orientations"],
                                },
                                "frames": frames["user_frames"],
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
                        continue

                    if is_special:
                        if _empty(user_button["buttonIdentity"]["buttonTagName"]) and _empty(user_button["buttonIdentity"]["text"]):
                            diag_ui_items.append({"buttonId": button_id})
                            continue
                        if _is_hard_button(user_button["buttonUI"]):
                            user_cats["hardButtons"].append(user_button)
                            continue

                    if _is_screen_label(user_button):
                        user_cats["screenLabels"].append(user_button)
                    else:
                        user_cats["screenButtons"].append(user_button)

            user_pages.append({"pageName": page_name, "buttonCategories": user_cats, "viewports": user_viewports})
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
                            "supported": int(drow["ScreenPortraitWidth"] or 0) > 0 and int(drow["ScreenPortraitHeight"] or 0) > 0,
                            "resolution": {"width": int(drow["ScreenPortraitWidth"] or 0), "height": int(drow["ScreenPortraitHeight"] or 0)},
                        },
                        "landscape": {
                            "supported": int(drow["ScreenLandscapeWidth"] or 0) > 0 and int(drow["ScreenLandscapeHeight"] or 0) > 0,
                            "resolution": {"width": int(drow["ScreenLandscapeWidth"] or 0), "height": int(drow["ScreenLandscapeHeight"] or 0)},
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
                    "pages": diag_pages,
                },
            }
        )

    con.close()
    return out


def _resolve_viewport_frames(cur: sqlite3.Cursor, viewport_button_id: int, tag_name_by_id: dict[int, str], variables_by_tag: dict[int, list[sqlite3.Row]], button_text_tag_ids: set[int], macros_by_tag: dict[int, list[sqlite3.Row]], page_links_by_tag: set[int]) -> dict[str, Any]:
    cur.execute("select * from Layers where ViewPortButtonId = ? order by LayerOrder, LayerId", (viewport_button_id,))
    child_layers = cur.fetchall()

    frame_user: dict[int, dict[str, Any]] = {}
    frame_diag: dict[int, dict[str, Any]] = {}
    layer_links: list[dict[str, Any]] = []

    for layer in child_layers:
        layer_links.append(
            {
                "layerId": int(layer["LayerId"]),
                "sharedLayerId": int(layer["SharedLayerId"]),
                "layerOrder": int(layer["LayerOrder"] or 0),
                "sourceId": int(layer["SourceId"] or 0),
                "roomId": int(layer["RoomId"] or 0),
            }
        )
        cur.execute("select * from RTIDeviceButtonData where SharedLayerId = ? order by ButtonOrder, ButtonId", (int(layer["SharedLayerId"]),))
        for b in cur.fetchall():
            frame_id = int(b["FrameNumber"] or 0)
            frame_user.setdefault(frame_id, {"frameId": frame_id, "buttonCategories": {"screenLabels": [], "screenButtons": [], "hardButtons": []}})
            frame_diag.setdefault(frame_id, {"frameId": frame_id, "buttons": []})

            user_button, diag_button, is_special = _resolve_button(cur, b, tag_name_by_id, variables_by_tag, button_text_tag_ids, macros_by_tag, page_links_by_tag)
            frame_diag[frame_id]["buttons"].append(diag_button)

            if is_special and _is_hard_button(user_button["buttonUI"]):
                frame_user[frame_id]["buttonCategories"]["hardButtons"].append(user_button)
            elif _is_screen_label(user_button):
                frame_user[frame_id]["buttonCategories"]["screenLabels"].append(user_button)
            else:
                frame_user[frame_id]["buttonCategories"]["screenButtons"].append(user_button)

    return {
        "user_frames": [frame_user[k] for k in sorted(frame_user)],
        "diag_frames": [frame_diag[k] for k in sorted(frame_diag)],
        "layer_links": layer_links,
    }


def _is_screen_label(button: dict[str, Any]) -> bool:
    t = button["testTargets"]
    has_display = bool(t["text"] or t["variables"]["Text"])
    page_link = t.get("pageLink", {})
    page_link_enabled = bool(page_link.get("enabled")) if isinstance(page_link, dict) else bool(page_link)
    return bool(not page_link_enabled and not t["macro"] and has_display and button["buttonIdentity"].get("buttonType") is None)


def json_load(path: Path) -> Any:
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
