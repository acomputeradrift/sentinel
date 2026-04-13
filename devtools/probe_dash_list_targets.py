"""
Probe Dash (or any) .apex SQLite for:
  - Controller room list (ControllerRoomList + Rooms), per RTI address
  - Room -> navigation targets from RoomEvents + macro step page links (same pipeline as
    extractor_core.extract_project_data, ~L1425–1538 / roomSelectEvent resolution ~L1059–1070)
  - List/browser buttons (ButtonStyle=8 + Variables.ObjectData) with full resolution via
    extract_project_data (resolvedPageLink matches production)

Writes JSON to --out (default: devtools/dash_list_probe_report.json).

Run from repo root (requires repo on PYTHONPATH, e.g. pip install -e .):
  python devtools/probe_dash_list_targets.py
  python devtools/probe_dash_list_targets.py --apex "Assets/Dash OS v55.2 iPhone.apex"
  python devtools/probe_dash_list_targets.py --no-extract   # SQL-only, no full extract
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sentinel.extraction.extractor_core import (  # noqa: E402
    ExtractContext,
    _activity_target_page_ids,
    _csv_page_targets,
    _pick_target_for_rti,
    extract_project_data,
)


def _table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f"pragma table_info({table})")
    return [str(r[1]) for r in cur.fetchall()]


def _build_room_event_targets_by_room(
    cur: sqlite3.Cursor,
) -> tuple[dict[int, str], dict[int, list[tuple[int, int]]], dict[tuple[int, int], list[tuple[int, int]]]]:
    """
    Mirror extractor_core.extract_project_data RoomEvents + Activities aggregation (~L1425–1538).
    Keep in sync when that block changes.

    Returns:
      page_name_by_page_id
      room_event_targets_by_room
      activity_target_pages_by_room_and_device  (source/activity navigation base for activityEvent)
    """
    cur.execute("select PageId, PageName from PagesView")
    page_name_by_page_id: dict[int, str] = {}
    for row in cur.fetchall():
        page_name_by_page_id[int(row["PageId"])] = str(row["PageName"] or "").strip()

    cur.execute(
        """
        select msv.MacroId, msv.Type, mpl.TargetPageId, msv.TargetRTIAddress, msr.SelectRoomId,
               mss.SelectSourceId, mss.SelectSourceRoomId, mro.RoomOffId
        from MacroStepsView msv
        left join MacroPageLinkView mpl on mpl.MacroStepId = msv.MacroStepId and msv.Type = 8
        left join MacroSelectRoom msr on msr.MacroStepId = msv.MacroStepId and msv.Type = 24
        left join MacroSelectSource mss on mss.MacroStepId = msv.MacroStepId and msv.Type = 26
        left join MacroRoomOff mro on mro.MacroStepId = msv.MacroStepId and msv.Type = 27
        order by msv.MacroId, msv.StepIndex, msv.MacroStepId
        """
    )
    macro_step_targets_by_macro: dict[int, list[tuple[int, int]]] = defaultdict(list)
    select_sources_by_macro: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for row in cur.fetchall():
        macro_id = int(row["MacroId"] or 0)
        step_type = int(row["Type"] or 0)
        if step_type == 8:
            for target in _csv_page_targets(row["TargetPageId"], row["TargetRTIAddress"]):
                if target not in macro_step_targets_by_macro[macro_id]:
                    macro_step_targets_by_macro[macro_id].append(target)
        elif step_type == 26:
            select_source_id = int(row["SelectSourceId"] or 0)
            select_source_room_id = int(row["SelectSourceRoomId"] or 0)
            pair = (select_source_id, select_source_room_id)
            if select_source_id > 0 and pair not in select_sources_by_macro[macro_id]:
                select_sources_by_macro[macro_id].append(pair)

    cur.execute(
        """
        select a.RoomId, a.DeviceId, a.PagelinkMacroId, a.Checked, a.ActivityOrder
        from Activities a
        join Devices d on d.DeviceId = a.DeviceId
        order by a.RoomId, a.Checked desc, a.ActivityOrder, a.ActivitiesId
        """
    )
    activity_target_pages_by_room_and_device: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for row in cur.fetchall():
        room_id = int(row["RoomId"] or 0)
        device_id = int(row["DeviceId"] or 0)
        key = (room_id, device_id)
        pagelink_macro_id = int(row["PagelinkMacroId"] or 0)
        if key not in activity_target_pages_by_room_and_device:
            activity_target_pages_by_room_and_device[key] = macro_step_targets_by_macro.get(pagelink_macro_id, [])

    cur.execute(
        "select RoomId, SelectedMacroId from RoomEvents where SelectedMacroId is not null order by RoomId, EventType"
    )
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

    return page_name_by_page_id, dict(room_event_targets_by_room), activity_target_pages_by_room_and_device


def _macro_select_room_tags_by_room_id(cur: sqlite3.Cursor) -> dict[int, list[dict[str, Any]]]:
    """
    For each MacroSelectRoom.SelectRoomId, collect Macros.ButtonTagId from Type=24 steps.

    RTI convention: actual room-pick tags often look like ``Room: Kitchen``; the same join also
    picks up ``NAVIGATION - *`` macros that include a SelectRoom step — see
    ``roomSelectRoomLabelTags`` vs ``roomSelectTagsAll`` in the report.
    """
    cur.execute("select name from sqlite_master where type='table' and name='MacroSelectRoom'")
    if not cur.fetchone():
        return {}
    cur.execute(
        """
        select distinct msr.SelectRoomId, m.ButtonTagId, tn.ButtonTagName, ms.MacroId
        from MacroSelectRoom msr
        join MacroSteps ms on ms.MacroStepId = msr.MacroStepId and ms.Type = 24
        join Macros m on m.MacroId = ms.MacroId
        left join ButtonTagNames tn on tn.ButtonTagId = m.ButtonTagId
        where coalesce(m.ButtonTagId, 0) > 0
        order by msr.SelectRoomId, tn.ButtonTagName, m.ButtonTagId
        """
    )
    by_room: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[int, int, int]] = set()
    for row in cur.fetchall():
        rid = int(row["SelectRoomId"] or 0)
        tid = int(row["ButtonTagId"] or 0)
        mid = int(row["MacroId"] or 0)
        key = (rid, tid, mid)
        if key in seen:
            continue
        seen.add(key)
        by_room[rid].append(
            {
                "buttonTagId": tid,
                "buttonTagName": str(row["ButtonTagName"] or "").strip() or None,
                "macroId": mid,
            }
        )
    return dict(by_room)


def _room_label_tags(tags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep tags whose name looks like documented room-select labels (``Room: …``)."""
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for t in tags:
        name = str(t.get("buttonTagName") or "").strip()
        if not name.lower().startswith("room:"):
            continue
        tid = int(t.get("buttonTagId") or 0)
        if tid in seen:
            continue
        seen.add(tid)
        out.append(dict(t))
    return out


def _controller_room_lists(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    cur.execute("select name from sqlite_master where type='table' and name='ControllerRoomList'")
    if not cur.fetchone():
        return []
    cur.execute(
        """
        select cr.RTIAddress, cr.ControllerRoomOrder, cr.RoomId, rm.Name as RoomName,
               rd.DeviceId, d.DisplayName
        from ControllerRoomList cr
        join Rooms rm on rm.RoomId = cr.RoomId
        join RTIDeviceData rd on rd.RTIAddress = cr.RTIAddress
        join Devices d on d.DeviceId = rd.DeviceId
        where coalesce(rd.CloneRTIAddress, 0) <= 0
        order by cr.RTIAddress, cr.ControllerRoomOrder, cr.RoomId
        """
    )
    return [dict(r) for r in cur.fetchall()]


def _resolve_targets_for_rti(
    targets: list[tuple[int, int]],
    rti_address: int,
    page_name_by_page_id: dict[int, str],
    *,
    resolution_path: str = "roomSelectEvent",
) -> dict[str, Any]:
    """Apply _pick_target_for_rti and attach names (same idea as resolvedPageLink)."""
    picked = _pick_target_for_rti(targets, rti_address)
    out: dict[str, Any] = {
        "rawTargets": [{"pageId": p, "rtiAddress": r} for p, r in targets],
        "pickedTargetPageId": picked,
        "pickedTargetPageName": (str(page_name_by_page_id.get(int(picked)) or "").strip() or None) if picked else None,
        "resolutionPath": resolution_path,
    }
    return out


def _device_rti_by_device_id(cur: sqlite3.Cursor) -> dict[int, int]:
    cur.execute(
        """
        select DeviceId, RTIAddress from RTIDeviceData
        where coalesce(CloneRTIAddress, 0) <= 0
        """
    )
    return {int(r["DeviceId"] or 0): int(r["RTIAddress"] or 0) for r in cur.fetchall() if int(r["DeviceId"] or 0) > 0}


def _iter_user_buttons(project_data: dict[str, Any]):
    """Walk userFacing buttons on pages and inside viewport frames."""
    for dev in project_data.get("devices", []):
        display_name = (dev.get("userFacing") or {}).get("displayName", "")
        diag = dev.get("diagnostics") or {}
        device_id = diag.get("deviceId")
        rti = diag.get("rtiAddress")
        for page in (dev.get("userFacing") or {}).get("pages", []):
            page_name = page.get("pageName", "")
            for layer in page.get("layers", []):
                layer_name = layer.get("layerName", "")
                bcat = layer.get("buttonCategories") or {}
                for cat in ("screenLabels", "screenButtons", "hardButtons", "emptyTag", "uiItems"):
                    for btn in bcat.get(cat, []) or []:
                        yield {
                            "deviceDisplayName": display_name,
                            "deviceId": device_id,
                            "rtiAddress": rti,
                            "pageName": page_name,
                            "layerName": layer_name,
                            "viewportButtonId": None,
                            "button": btn,
                        }
                for vp in layer.get("viewports", []) or []:
                    vpb = (vp.get("viewportIdentity") or {}).get("viewportButtonId")
                    for vlayer in vp.get("layers", []) or []:
                        for frame in vlayer.get("frames", []) or []:
                            fcat = frame.get("buttonCategories") or {}
                            for cat in ("screenLabels", "screenButtons", "hardButtons", "emptyTag", "uiItems"):
                                for btn in fcat.get(cat, []) or []:
                                    yield {
                                        "deviceDisplayName": display_name,
                                        "deviceId": device_id,
                                        "rtiAddress": rti,
                                        "pageName": page_name,
                                        "layerName": vlayer.get("layerName", ""),
                                        "viewportButtonId": vpb,
                                        "frameId": frame.get("frameId"),
                                        "button": btn,
                                    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--apex",
        default=str(ROOT / "Assets" / "Dash OS v55.2 iPhone.apex"),
        help="Path to .apex (SQLite)",
    )
    p.add_argument(
        "--project-structure",
        default=str(ROOT / "src" / "sentinel" / "contracts" / "apex_project_structure_v4.json"),
        help="Contract JSON (required by extract_project_data)",
    )
    p.add_argument(
        "--out",
        default=str(ROOT / "devtools" / "dash_list_probe_report.json"),
        help="JSON report output path",
    )
    p.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip full extract_project_data (faster); omit list-button resolvedPageLink section",
    )
    args = p.parse_args()
    apex = Path(args.apex).resolve()
    contract = Path(args.project_structure).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not apex.exists():
        err = {"error": f"apex not found: {apex}"}
        out.write_text(json.dumps(err, indent=2, ensure_ascii=True), encoding="utf-8")
        print(err["error"], file=sys.stderr)
        return 1
    if not contract.exists():
        err = {"error": f"contract not found: {contract}"}
        out.write_text(json.dumps(err, indent=2, ensure_ascii=True), encoding="utf-8")
        print(err["error"], file=sys.stderr)
        return 1

    try:
        _run_probe(apex, contract, args.no_extract, out)
        print(str(out))
        return 0
    except Exception as exc:  # pragma: no cover
        err = {"error": str(exc), "traceback": traceback.format_exc(), "apex": str(apex)}
        out.write_text(json.dumps(err, indent=2, ensure_ascii=True), encoding="utf-8")
        print(str(exc), file=sys.stderr)
        return 1


def _run_probe(apex: Path, contract: Path, no_extract: bool, out: Path) -> None:
    con = sqlite3.connect(str(apex))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    report: dict[str, Any] = {
        "apex": str(apex),
        "docsRef": "extractor_core._resolve_button roomSelectEvent + RoomEvents join (~L1059–1070, ~L1521–1538); "
        "apex_project_structure_resolution_v2.md (page link / room select)",
    }

    page_name_by_page_id, room_event_targets_by_room, activity_targets_by_room_device = _build_room_event_targets_by_room(cur)
    device_rti = _device_rti_by_device_id(cur)

    # --- Full controller room list rows (actual order on controller) + MacroSelectRoom -> ButtonTag ---
    tags_by_room = _macro_select_room_tags_by_room_id(cur)
    cr_rows = _controller_room_lists(cur)
    for row in cr_rows:
        rid = int(row.get("RoomId") or 0)
        all_tags = tags_by_room.get(rid, [])
        row["roomSelectTagsAll"] = all_tags
        row["roomSelectRoomLabelTags"] = _room_label_tags(all_tags)
    report["controllerRoomLists"] = cr_rows
    report["roomIdToRoomSelectTags"] = {
        str(k): {"all": v, "roomLabel": _room_label_tags(v)} for k, v in sorted(tags_by_room.items())
    }

    # --- Per RTI: map each controller room row -> room-event page targets (room select navigation) ---
    by_rti: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in report["controllerRoomLists"]:
        rti = int(row["RTIAddress"] or 0)
        rid = int(row["RoomId"] or 0)
        targets = room_event_targets_by_room.get(rid, [])
        by_rti[rti].append(
            {
                "controllerRoomOrder": int(row.get("ControllerRoomOrder") or 0),
                "roomId": rid,
                "roomName": row.get("RoomName"),
                "deviceId": int(row.get("DeviceId") or 0),
                "displayName": row.get("DisplayName"),
                "roomEventNavigation": _resolve_targets_for_rti(targets, rti, page_name_by_page_id),
            }
        )
    report["controllerRoomListWithRoomEventPageLinks"] = {str(k): v for k, v in sorted(by_rti.items())}

    # --- Source / activity list: Activities -> PagelinkMacroId -> macro Type-8 page targets (activityEvent base) ---
    activity_rows: list[dict[str, Any]] = []
    for (room_id, device_id), targets in sorted(activity_targets_by_room_device.items()):
        rti = device_rti.get(int(device_id), 0)
        activity_rows.append(
            {
                "roomId": int(room_id),
                "deviceId": int(device_id),
                "rtiAddress": rti,
                "activityPagelinkNavigation": _resolve_targets_for_rti(
                    targets,
                    rti,
                    page_name_by_page_id,
                    resolution_path="activityPagelinkMacro",
                ),
            }
        )
    report["sourceListActivityNavigation"] = {
        "note": "First-seen Activities row per (roomId, deviceId) maps to PagelinkMacroId step targets; "
        "extractor merges these into room_event_targets and activityEvent path (extractor_core ~L1073–1094).",
        "rows": activity_rows,
    }

    # --- Style-8 + ObjectData (extractor list target gate); SQL preview ---
    cols = _table_columns(cur, "RTIDeviceButtonData")
    style_col = "ButtonStyle" if "ButtonStyle" in cols else None
    if style_col:
        cur.execute(
            f"""
            select b.ButtonId, b.ButtonTagId, b.Text, b.{style_col} as ButtonStyle,
                   b.ViewPortVerticalScroll, tn.ButtonTagName as ButtonTagName
            from RTIDeviceButtonData b
            left join ButtonTagNames tn on tn.ButtonTagId = b.ButtonTagId
            where b.{style_col} = 8
            order by b.ButtonId
            """
        )
        style8 = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            select v.ButtonTagId, v.VariableId, v.ObjectData
            from Variables v
            where v.ObjectData is not null and trim(cast(v.ObjectData as text)) != ''
            """
        )
        obj_by_tag: dict[int, list[dict]] = defaultdict(list)
        for r in cur.fetchall():
            tid = int(r["ButtonTagId"] or 0)
            if tid > 0:
                obj_by_tag[tid].append(
                    {"variableId": int(r["VariableId"] or 0), "objectData": str(r["ObjectData"] or "")}
                )
        list_rows = []
        for row in style8:
            tid = int(row.get("ButtonTagId") or 0)
            objs = obj_by_tag.get(tid, [])
            list_rows.append({**row, "objectDataBindings": objs, "listTarget": bool(objs)})
        report["listBrowserButtonsSql"] = {
            "countStyle8": len(style8),
            "withNonEmptyObjectData": sum(1 for r in list_rows if r["listTarget"]),
            "rows": list_rows,
        }

    con.close()

    # --- Full extraction: production-resolved pageLink for every button (including list rows) ---
    if not no_extract:
        data = extract_project_data(ExtractContext(apex_path=apex, project_structure_path=contract), progress_hook=None)
        list_buttons: list[dict[str, Any]] = []
        for ctx in _iter_user_buttons(data):
            btn = ctx["button"]
            tt = (btn.get("testTargets") or {}).get("variables") or {}
            if not tt.get("List"):
                continue
            list_buttons.append(
                {
                    **{k: v for k, v in ctx.items() if k != "button"},
                    "buttonIdentity": btn.get("buttonIdentity"),
                    "testTargets": btn.get("testTargets"),
                    "resolvedPageLink": btn.get("resolvedPageLink"),
                    "apexScopeSource": btn.get("apexScopeSource"),
                }
            )
        report["listButtonsFromExtract"] = {
            "count": len(list_buttons),
            "note": "resolvedPageLink uses full _resolve_button pipeline (directPageLink, macroStep, roomSelectEvent, activityEvent, roomOffEvent).",
            "rows": list_buttons,
        }
        # Optional: surface device diagnostics.rooms alongside extract (same as JSON devices)
        report["deviceDiagnosticsRoomsFromExtract"] = [
            {
                "displayName": d.get("userFacing", {}).get("displayName"),
                **(d.get("diagnostics") or {}),
            }
            for d in data.get("devices", [])
        ]

    out.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
