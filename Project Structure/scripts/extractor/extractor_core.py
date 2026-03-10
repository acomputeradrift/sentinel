from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_STYLE_TO_TYPE = {9: "Slider", 7: "Toggle", 11: "LevelIndicatorBar"}
_TOKEN_ONLY_RE = re.compile(r"^\s*\$%TAG!.*?%\$\s*$", re.IGNORECASE | re.DOTALL)


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


def _resolve_button(cur: sqlite3.Cursor, button_row: sqlite3.Row, tag_name_by_id: dict[int, str], variables_by_tag: dict[int, list[sqlite3.Row]], button_text_tag_ids: set[int], macros_by_tag: dict[int, list[sqlite3.Row]], page_links_by_tag: set[int]) -> tuple[dict[str, Any], dict[str, Any], bool]:
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

    page_link_enabled = tag_id in page_links_by_tag if tag_id > 0 else False

    is_hard = int(button_row["ButtonHeight"] or 0) == 0 and int(button_row["ButtonWidth"] or 0) == 0

    user_button = {
        "buttonIdentity": {
            "buttonTagName": tag_name,
            "text": text,
            "buttonType": button_type,
        },
        "buttonUI": {
            "fontSize": int(button_row["TextSize"] or 0),
            "coordinates": {
                "top": int(button_row["ButtonTop"] or 0),
                "left": int(button_row["ButtonLeft"] or 0),
                "height": int(button_row["ButtonHeight"] or 0),
                "width": int(button_row["ButtonWidth"] or 0),
            },
        },
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
            "pageLink": page_link_enabled,
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
            "pageLink": {"pageLinkId": 1 if page_link_enabled else None, "targetPageId": None, "targetPageName": None},
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

    cur.execute("select ButtonTagId from PageLinks")
    page_links_by_tag = {int(r[0]) for r in cur.fetchall() if r[0] is not None}
    cur.execute("select distinct ViewPortButtonId from Layers where ViewPortButtonId is not null")
    viewport_button_ids = {int(r[0]) for r in cur.fetchall() if r[0] is not None}

    cur.execute("select * from Events where Enabled = 1")
    event_rows = cur.fetchall()

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
        trigger = ev["Description"] or ev["DriverExtraString"] or ""
        macro_id = int(ev["MacroId"] or 0)
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
        if int(ev["DriverId"] or 0) > 0 or event_type == 5:
            out["events"]["driver"].append({"userFacing": {"eventType": "Driver", "resolvedTrigger": trigger}, "diagnostics": {**diag, "driverId": int(ev["DriverId"] or 0), "driverName": "", "driverExtraString": ev["DriverExtraString"] or ""}})
        else:
            out["events"]["system"].append({"userFacing": {"eventType": _event_type_name(event_type), "resolvedTrigger": trigger}, "diagnostics": diag})

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
                                "viewportUI": {"coordinates": user_button["buttonUI"]["coordinates"]},
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
                        if user_button["buttonUI"]["coordinates"]["height"] == 0 and user_button["buttonUI"]["coordinates"]["width"] == 0:
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

            if is_special and user_button["buttonUI"]["coordinates"]["height"] == 0 and user_button["buttonUI"]["coordinates"]["width"] == 0:
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
    return bool(not t["pageLink"] and not t["macro"] and has_display and button["buttonIdentity"].get("buttonType") is None)


def json_load(path: Path) -> Any:
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
