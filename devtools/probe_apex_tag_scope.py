"""
Per-tag scope probe: compact JSON only.

For each ``ButtonId`` under a tag, list every ``MacroId`` and ``VariableId`` on that tag with the
same ``runtimeScope``: ``{ resolvedRoomName, resolvedSourceName }``.

Effective room/source follows **layer precedence** in ``rti_scope_doc.md`` rules 3–4 (viewport →
page layer → workspace), implemented from ``Layers`` + ``PagesView`` + ``RTIDevicePageData`` only.

``rti_scope_doc.md`` rule 9 (Global workspace: room from ``Selected Room`` at runtime) cannot be
read statically from apex; when workspace + computed runtime room are both 0, ``resolvedRoomName``
is a fixed placeholder noting rule 9.

Usage::

  python devtools/probe_apex_tag_scope.py
  python devtools/probe_apex_tag_scope.py --tag-name "Circuit 6 - Toggle" --out devtools/tag_scope_probe_report.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _load_device_display_names(cur: sqlite3.Cursor) -> dict[int, str]:
    cur.execute("pragma table_info(Devices)")
    cols = {str(r[1]) for r in cur.fetchall()}
    has_disp = "DisplayName" in cols
    has_name = "Name" in cols
    cur.execute("select DeviceId, DisplayName, Name from Devices")
    out: dict[int, str] = {}
    for row in cur.fetchall():
        did = int(row["DeviceId"] or 0)
        if did <= 0:
            continue
        dn = str(row["DisplayName"] or "").strip() if has_disp else ""
        nm = str(row["Name"] or "").strip() if has_name else ""
        out[did] = dn or nm or f"Device {did}"
    return out


def _load_room_names(cur: sqlite3.Cursor) -> dict[int, str]:
    cur.execute("select RoomId, Name from Rooms")
    out: dict[int, str] = {}
    for row in cur.fetchall():
        rid = int(row["RoomId"] or 0)
        if rid < 0:
            continue
        nm = str(row["Name"] or "").strip()
        if rid > 0 and nm:
            out[rid] = nm
    return out


def _resolve_tag_id(cur: sqlite3.Cursor, tag_name: str) -> tuple[int, str]:
    cur.execute(
        "select ButtonTagId, ButtonTagName from ButtonTagNames where ButtonTagName = ?",
        (tag_name,),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "select ButtonTagId, ButtonTagName from ButtonTagNames where ButtonTagName like ? limit 5",
            (f"%{tag_name}%",),
        )
        near = [dict(r) for r in cur.fetchall()]
        raise SystemExit(
            f"No exact match for tag name {tag_name!r}. "
            f"Try --tag-id or fix spelling. Similar (up to 5): {near}"
        )
    return int(row["ButtonTagId"]), str(row["ButtonTagName"])


def _page_name(cur: sqlite3.Cursor, page_name_id: int | None) -> str | None:
    if page_name_id is None or int(page_name_id) < 0:
        return None
    cur.execute("select PageName from PageNames where PageNameId = ?", (int(page_name_id),))
    pn = cur.fetchone()
    if not pn:
        return None
    s = str(pn[0] or "").strip()
    return s or None


def _pages_view_row(cur: sqlite3.Cursor, page_id: int) -> sqlite3.Row | None:
    cur.execute("select * from PagesView where PageId = ?", (page_id,))
    return cur.fetchone()


def _rti_page_rows(cur: sqlite3.Cursor, page_id: int) -> list[sqlite3.Row]:
    cur.execute(
        """
        select RTIAddress, SourceDeviceId, PageNameId, PageOrder
        from RTIDevicePageData
        where PageId = ?
        order by RTIAddress, PageOrder
        """,
        (page_id,),
    )
    return list(cur.fetchall())


def _parent_page_layer_for_viewport_child(cur: sqlite3.Cursor, child_layer_id: int) -> sqlite3.Row | None:
    cur.execute(
        """
        select parent.*
        from Layers child
        join RTIDeviceButtonData vb on vb.ButtonId = child.ViewPortButtonId
        join Layers parent
          on parent.SharedLayerId = vb.SharedLayerId
         and parent.PageId = child.PageId
         and parent.ViewPortButtonId is null
        where child.LayerId = ?
        limit 1
        """,
        (child_layer_id,),
    )
    return cur.fetchone()


def _effective_room_source(
    *,
    page_room_id: int,
    page_source_id: int | None,
    layer_room_id: int | None,
    layer_source_id: int | None,
    page_layer_room_id: int | None,
    page_layer_source_id: int | None,
) -> tuple[int, int | None]:
    eff_r = (
        int(layer_room_id)
        if layer_room_id is not None
        else (
            int(page_layer_room_id)
            if page_layer_room_id is not None
            else int(page_room_id)
        )
    )
    eff_s = (
        int(layer_source_id)
        if layer_source_id is not None
        else (
            int(page_layer_source_id)
            if page_layer_source_id is not None
            else (int(page_source_id) if page_source_id is not None else None)
        )
    )
    return eff_r, eff_s


def _parent_host_layer_for_viewport_button(cur: sqlite3.Cursor, viewport_button_id: int) -> sqlite3.Row | None:
    cur.execute(
        """
        select parent.*
        from RTIDeviceButtonData vb
        join Layers parent
          on parent.SharedLayerId = vb.SharedLayerId
         and parent.ViewPortButtonId is null
         and parent.PageId is not null
        where vb.ButtonId = ?
        order by parent.LayerOrder, parent.LayerId
        limit 1
        """,
        (int(viewport_button_id),),
    )
    return cur.fetchone()


def _resolve_page_id_and_parent_for_orphan_layer(
    cur: sqlite3.Cursor, lr: sqlite3.Row
) -> tuple[int | None, sqlite3.Row | None, str | None]:
    vpb = lr["ViewPortButtonId"]
    if vpb is None:
        return None, None, "Layers.PageId is null and ViewPortButtonId is null"
    cur.execute("select * from RTIDeviceButtonData where ButtonId = ?", (int(vpb),))
    vb = cur.fetchone()
    if vb is None:
        return None, None, f"ViewPortButtonId {vpb} not found in RTIDeviceButtonData"
    parent = _parent_host_layer_for_viewport_button(cur, int(vpb))
    if parent is None:
        return None, None, f"no parent host Layers row for viewport ButtonId {vpb}"
    return int(parent["PageId"]), parent, None


def _viewport_parent_layer(cur: sqlite3.Cursor, lr: sqlite3.Row) -> sqlite3.Row | None:
    vpb = lr["ViewPortButtonId"]
    if vpb is None:
        return None
    if lr["PageId"] is not None:
        return _parent_page_layer_for_viewport_child(cur, int(lr["LayerId"]))
    return _parent_host_layer_for_viewport_button(cur, int(vpb))


def _emit_one_placement(
    cur: sqlite3.Cursor,
    *,
    button_id: int,
    b: sqlite3.Row,
    lr: sqlite3.Row,
    page_id: int,
    pv: sqlite3.Row,
    rti_row: sqlite3.Row | None,
    placement_kind: str,
    parent_host_layer: sqlite3.Row | None,
) -> dict[str, Any]:
    page_room_id = int(pv["RoomId"] or 0)
    page_src = int(rti_row["SourceDeviceId"]) if rti_row is not None and rti_row["SourceDeviceId"] is not None else None
    page_name_id = int(rti_row["PageNameId"]) if rti_row is not None and rti_row["PageNameId"] is not None else None
    if page_name_id is None and "PageNameId" in pv.keys() and pv["PageNameId"] is not None:
        page_name_id = int(pv["PageNameId"])
    rti_address = int(rti_row["RTIAddress"]) if rti_row is not None and rti_row["RTIAddress"] is not None else None

    lr_room = int(lr["RoomId"]) if lr["RoomId"] is not None else None
    lr_src = int(lr["SourceId"]) if lr["SourceId"] is not None else None
    vpb = lr["ViewPortButtonId"]

    page_layer_room: int | None = None
    page_layer_src: int | None = None
    if placement_kind == "viewportInnerLayer" and parent_host_layer is not None:
        page_layer_room = int(parent_host_layer["RoomId"]) if parent_host_layer["RoomId"] is not None else None
        page_layer_src = int(parent_host_layer["SourceId"]) if parent_host_layer["SourceId"] is not None else None

    eff_r, eff_s = _effective_room_source(
        page_room_id=page_room_id,
        page_source_id=page_src,
        layer_room_id=lr_room,
        layer_source_id=lr_src,
        page_layer_room_id=page_layer_room,
        page_layer_source_id=page_layer_src,
    )

    return {
        "buttonId": button_id,
        "placementKind": placement_kind,
        "page": {
            "pageId": int(page_id),
            "pageName": _page_name(cur, page_name_id),
            "roomId": page_room_id,
            "sourceDeviceId": page_src,
            "rtiAddress": rti_address,
        },
        "workspaceScope": {"roomId": page_room_id, "sourceId": page_src},
        "pageLayerScope": {"roomId": page_layer_room, "sourceId": page_layer_src},
        "viewportLayerScope": {"roomId": lr_room, "sourceId": lr_src},
        "runtimeScope": {"roomId": eff_r, "sourceId": eff_s},
    }


def _collect_button_placements(cur: sqlite3.Cursor, tag_id: int) -> list[dict[str, Any]]:
    cur.execute(
        """
        select b.ButtonId, b.SharedLayerId, b.ButtonTagId, b.FrameNumber, b.ButtonStyle, b.Text
        from RTIDeviceButtonData b
        where b.ButtonTagId = ?
        order by b.ButtonId
        """,
        (tag_id,),
    )
    buttons = cur.fetchall()
    out: list[dict[str, Any]] = []
    for b in buttons:
        bid = int(b["ButtonId"])
        cur.execute(
            "select * from Layers where SharedLayerId = ? order by LayerOrder, LayerId",
            (int(b["SharedLayerId"]),),
        )
        layer_rows = list(cur.fetchall())
        if not layer_rows:
            out.append({"buttonId": bid, "error": "no Layers row for SharedLayerId", "buttonRow": _row_dict(b)})
            continue

        seen_emit: set[tuple[int, int, int, int | None]] = set()

        for lr in layer_rows:
            page_id_val = lr["PageId"]
            placement_kind = "pageLayer"
            parent_host: sqlite3.Row | None = None

            if page_id_val is not None:
                page_id = int(page_id_val)
                pv = _pages_view_row(cur, page_id)
                if pv is None:
                    out.append({"buttonId": bid, "error": f"no PagesView row for PageId {page_id}"})
                    continue
                if lr["ViewPortButtonId"] is not None:
                    placement_kind = "viewportInnerLayer"
                    parent_host = _viewport_parent_layer(cur, lr)
                rti_rows = _rti_page_rows(cur, page_id)
                if not rti_rows:
                    rti_rows = [None]
                for rti_row in rti_rows:
                    rti_key = int(rti_row["RTIAddress"]) if rti_row is not None and rti_row["RTIAddress"] is not None else None
                    dedupe = (bid, int(lr["LayerId"]), page_id, rti_key)
                    if dedupe in seen_emit:
                        continue
                    seen_emit.add(dedupe)
                    out.append(
                        _emit_one_placement(
                            cur,
                            button_id=bid,
                            b=b,
                            lr=lr,
                            page_id=page_id,
                            pv=pv,
                            rti_row=rti_row,
                            placement_kind=placement_kind,
                            parent_host_layer=parent_host,
                        )
                    )
            else:
                page_id_res, parent_host, err = _resolve_page_id_and_parent_for_orphan_layer(cur, lr)
                if err or page_id_res is None:
                    out.append({"buttonId": bid, "error": err or "unresolved PageId", "layerRow": _row_dict(lr)})
                    continue
                page_id = int(page_id_res)
                placement_kind = "viewportInnerLayer"
                pv = _pages_view_row(cur, page_id)
                if pv is None:
                    out.append({"buttonId": bid, "error": f"no PagesView row for resolved PageId {page_id}"})
                    continue
                rti_rows = _rti_page_rows(cur, page_id)
                if not rti_rows:
                    rti_rows = [None]
                for rti_row in rti_rows:
                    rti_key = int(rti_row["RTIAddress"]) if rti_row is not None and rti_row["RTIAddress"] is not None else None
                    dedupe = (bid, int(lr["LayerId"]), page_id, rti_key)
                    if dedupe in seen_emit:
                        continue
                    seen_emit.add(dedupe)
                    out.append(
                        _emit_one_placement(
                            cur,
                            button_id=bid,
                            b=b,
                            lr=lr,
                            page_id=page_id,
                            pv=pv,
                            rti_row=rti_row,
                            placement_kind=placement_kind,
                            parent_host_layer=parent_host,
                        )
                    )
    return out


def _room_label(
    room_id: int | None,
    *,
    room_names: dict[int, str],
    selected_room_rule: bool = False,
    default_label: bool = False,
) -> str:
    if default_label and room_id is None:
        return "Default Room"
    rid = int(room_id or 0)
    if selected_room_rule and rid == 0:
        return "Selected Room"
    if rid <= 0:
        return "Global"
    return room_names.get(rid) or f"RoomId {rid}"


def _source_label(
    source_id: int | None,
    *,
    device_names: dict[int, str],
    default_label: bool = False,
) -> str:
    if default_label and source_id is None:
        return "Default Source"
    if source_id is None:
        return "Global"
    sid = int(source_id)
    if sid <= 0:
        return "Global"
    return device_names.get(sid) or f"DeviceId {sid}"


def _all_scope_labels(
    *,
    room_names: dict[int, str],
    device_names: dict[int, str],
    ctx: dict[str, Any],
) -> dict[str, dict[str, str]]:
    workspace = ctx.get("workspaceScope") or {}
    page_layer = ctx.get("pageLayerScope") or {}
    viewport_layer = ctx.get("viewportLayerScope") or {}
    runtime = ctx.get("runtimeScope") or {}

    workspace_room = workspace.get("roomId")
    workspace_source = workspace.get("sourceId")

    workspace_scope = {
        "resolvedRoomName": _room_label(
            int(workspace_room) if workspace_room is not None else None,
            room_names=room_names,
            selected_room_rule=True,
        ),
        "resolvedSourceName": _source_label(
            int(workspace_source) if workspace_source is not None else None,
            device_names=device_names,
        ),
    }
    page_layer_scope = {
        "resolvedRoomName": _room_label(
            int(page_layer["roomId"]) if page_layer.get("roomId") is not None else None,
            room_names=room_names,
            default_label=True,
        ),
        "resolvedSourceName": _source_label(
            int(page_layer["sourceId"]) if page_layer.get("sourceId") is not None else None,
            device_names=device_names,
            default_label=True,
        ),
    }
    viewport_layer_scope = {
        "resolvedRoomName": _room_label(
            int(viewport_layer["roomId"]) if viewport_layer.get("roomId") is not None else None,
            room_names=room_names,
            default_label=True,
        ),
        "resolvedSourceName": _source_label(
            int(viewport_layer["sourceId"]) if viewport_layer.get("sourceId") is not None else None,
            device_names=device_names,
            default_label=True,
        ),
    }
    runtime_scope = {
        "resolvedRoomName": _room_label(
            int(runtime["roomId"]) if runtime.get("roomId") is not None else None,
            room_names=room_names,
            selected_room_rule=(int(workspace_room or 0) == 0),
        ),
        "resolvedSourceName": _source_label(
            int(runtime["sourceId"]) if runtime.get("sourceId") is not None else None,
            device_names=device_names,
        ),
    }
    return {
        "workspaceScope": workspace_scope,
        "pageLayerScope": page_layer_scope,
        "viewportLayerScope": viewport_layer_scope,
        "runtimeScope": runtime_scope,
    }


def run(apex: Path, tag_name: str | None, tag_id: int | None) -> dict[str, Any]:
    if not apex.is_file():
        raise FileNotFoundError(str(apex))
    con = sqlite3.connect(str(apex))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    if tag_id is not None:
        tid = int(tag_id)
        cur.execute("select ButtonTagName from ButtonTagNames where ButtonTagId = ?", (tid,))
        trow = cur.fetchone()
        if not trow:
            raise SystemExit(f"ButtonTagId {tid} not in ButtonTagNames")
        resolved_name = str(trow["ButtonTagName"] or "")
    else:
        assert tag_name is not None
        tid, resolved_name = _resolve_tag_id(cur, tag_name)

    placements = _collect_button_placements(cur, tid)
    room_names = _load_room_names(cur)
    device_names = _load_device_display_names(cur)

    by_button: dict[int, dict[str, Any]] = {}
    for ctx in placements:
        if "error" in ctx:
            continue
        bid = int(ctx["buttonId"])
        labels = _all_scope_labels(room_names=room_names, device_names=device_names, ctx=ctx)
        if bid not in by_button:
            by_button[bid] = {"labels": labels, "ctx": ctx}
        elif by_button[bid]["labels"] != labels:
            # Keep first; caller can diff raw placements if needed
            pass

    cur.execute("select MacroId from Macros where ButtonTagId = ? order by MacroId", (tid,))
    macro_ids = [int(r[0]) for r in cur.fetchall() if r[0] is not None]
    cur.execute("select VariableId from Variables where ButtonTagId = ? order by VariableId", (tid,))
    variable_ids = [int(r[0]) for r in cur.fetchall() if r[0] is not None]

    buttons_out: list[dict[str, Any]] = []
    for bid in sorted(by_button.keys()):
        scopes = dict(by_button[bid]["labels"])
        buttons_out.append(
            {
                "buttonId": bid,
                "macros": [
                    {
                        "macroId": mid,
                        "resolvedPageName": by_button[bid]["ctx"]["page"].get("pageName"),
                        "workspaceScope": dict(scopes["workspaceScope"]),
                        "pageLayerScope": dict(scopes["pageLayerScope"]),
                        "viewportLayerScope": dict(scopes["viewportLayerScope"]),
                        "runtimeScope": dict(scopes["runtimeScope"]),
                    }
                    for mid in macro_ids
                ],
                "variables": [
                    {
                        "variableId": vid,
                        "resolvedPageName": by_button[bid]["ctx"]["page"].get("pageName"),
                        "workspaceScope": dict(scopes["workspaceScope"]),
                        "pageLayerScope": dict(scopes["pageLayerScope"]),
                        "viewportLayerScope": dict(scopes["viewportLayerScope"]),
                        "runtimeScope": dict(scopes["runtimeScope"]),
                    }
                    for vid in variable_ids
                ],
            }
        )

    unresolved = sorted({int(x["buttonId"]) for x in placements if "error" in x})

    con.close()
    return {
        "apex": str(apex.resolve()),
        "tag": {"buttonTagId": tid, "buttonTagName": resolved_name},
        "rtiScopeDoc": "rti_scope_doc.md",
        "limitationNotes": [
            "Room/source chain follows rti_scope_doc.md rules 3–4 (viewport → page layer → workspace) using Layers + PagesView + RTIDevicePageData.",
            "Rule 9 placeholder is used only when PagesView workspace room and computed effective room id are both 0; other cases use Rooms.Name for the computed effective room id.",
        ],
        "unresolvedButtonIds": unresolved,
        "buttons": buttons_out,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Compact per-button macro/variable effective scope for one tag.")
    p.add_argument(
        "--apex",
        default=str(ROOT / "Assets" / "Sung Residence v207.2.apex"),
        help="Path to .apex (SQLite)",
    )
    p.add_argument(
        "--tag-name",
        default="Circuit 6 - Toggle",
        help="Exact ButtonTagNames.ButtonTagName",
    )
    p.add_argument("--tag-id", type=int, default=None, help="Override name lookup with ButtonTagId")
    p.add_argument(
        "--out",
        default=str(ROOT / "devtools" / "tag_scope_probe_report.json"),
        help="JSON report output path",
    )
    args = p.parse_args()
    apex = Path(args.apex).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = run(apex, args.tag_name, args.tag_id)
    except Exception as exc:
        err = {"error": str(exc), "apex": str(apex)}
        out.write_text(json.dumps(err, indent=2, ensure_ascii=True), encoding="utf-8")
        print(str(exc), file=sys.stderr)
        print(str(out))
        return 1
    out.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
