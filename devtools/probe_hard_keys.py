"""
Hard-keys discovery probe.

Reads an .apex SQLite project and prints findings needed to lock the five
"Open Clarifications Required Before Implementation" in `hard_keys.md`:

1. Device identity rule (DisplayName / Name / ProductId mapping)
2. Canonical hard-key layer selection (SharedLayers + IsKeypadLayer + ProductId)
3. Slot ranges actually present in RTIDeviceButtonData per model
4. Frame and order details for hard-key rows
5. Cross-check against expected ranges from hard_keys.md.

Usage::

    python devtools/probe_hard_keys.py "Assets/test with t4x isr-2 isr-4.apex"
    python devtools/probe_hard_keys.py "Assets/test with t4x isr-2 isr-4.apex" --json devtools/probe_hard_keys.out.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

EXPECTED_RANGES = {
    "T4x": (128, 147),
    "ISR-4": (128, 149),
    "ISR-2": (128, 161),
}


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f"pragma table_info({table})")
    return [str(r[1]) for r in cur.fetchall()]


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (table,),
    )
    return cur.fetchone() is not None


def probe(apex_path: Path) -> dict[str, Any]:
    con = sqlite3.connect(str(apex_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    out: dict[str, Any] = {"apex": str(apex_path)}

    out["schema"] = {
        "Devices": _table_columns(cur, "Devices") if _table_exists(cur, "Devices") else None,
        "RTIDeviceData": _table_columns(cur, "RTIDeviceData") if _table_exists(cur, "RTIDeviceData") else None,
        "SharedLayers": _table_columns(cur, "SharedLayers") if _table_exists(cur, "SharedLayers") else None,
        "RTIDeviceButtonData": _table_columns(cur, "RTIDeviceButtonData") if _table_exists(cur, "RTIDeviceButtonData") else None,
        "ButtonTagNames": _table_columns(cur, "ButtonTagNames") if _table_exists(cur, "ButtonTagNames") else None,
    }

    devices_cols = out["schema"]["Devices"] or []
    rti_cols = out["schema"]["RTIDeviceData"] or []
    has_rti_pid = "ProductId" in rti_cols
    has_disp = "DisplayName" in devices_cols

    select_rti = (
        "select rd.RTIAddress, rd.DeviceId, "
        + ("rd.ProductId, " if has_rti_pid else "")
        + "rd.CloneRTIAddress, "
        + ("d.DisplayName, " if has_disp else "")
        + "d.Name "
        + "from RTIDeviceData rd join Devices d on d.DeviceId = rd.DeviceId "
        + "order by rd.RTIAddress"
    )
    cur.execute(select_rti)
    devices = [_row_dict(r) for r in cur.fetchall()]
    out["devices"] = devices

    sl_cols = out["schema"]["SharedLayers"] or []
    has_keypad = "IsKeypadLayer" in sl_cols
    has_sl_pid = "ProductId" in sl_cols
    cur.execute("select * from SharedLayers")
    shared_layers = [_row_dict(r) for r in cur.fetchall()]
    out["sharedLayersAll"] = shared_layers
    out["sharedLayersHasIsKeypadLayer"] = has_keypad
    out["sharedLayersHasProductId"] = has_sl_pid

    hk_layers: list[dict[str, Any]] = []
    for sl in shared_layers:
        name = str(sl.get("Name") or "")
        is_keypad = int(sl.get("IsKeypadLayer") or 0) if has_keypad else 0
        if is_keypad == 1 or name.lower().startswith("hard keys"):
            hk_layers.append(sl)
    out["hardKeyLayers"] = hk_layers

    btn_cols = out["schema"]["RTIDeviceButtonData"] or []
    btn_select = "select * from RTIDeviceButtonData where SharedLayerId = ? and ButtonWidth = 0 and ButtonHeight = 0 order by FrameNumber, ButtonTop, ButtonLeft, ButtonOrder"
    sl_id_to_buttons: dict[int, list[dict[str, Any]]] = {}
    for sl in hk_layers:
        slid = int(sl["SharedLayerId"])
        cur.execute(btn_select, (slid,))
        rows = [_row_dict(r) for r in cur.fetchall()]
        sl_id_to_buttons[slid] = rows
    out["hardKeyButtonsByLayer"] = sl_id_to_buttons

    if _table_exists(cur, "ButtonTagNames"):
        cur.execute("select ButtonTagId, ButtonTagName from ButtonTagNames")
        tag_by_id = {int(r["ButtonTagId"]): str(r["ButtonTagName"] or "") for r in cur.fetchall()}
    else:
        tag_by_id = {}
    out["tagByIdSize"] = len(tag_by_id)

    summary: list[dict[str, Any]] = []
    for sl in hk_layers:
        slid = int(sl["SharedLayerId"])
        rows = sl_id_to_buttons.get(slid, [])
        lefts = sorted({int(r.get("ButtonLeft") or 0) for r in rows})
        frames = sorted({int(r.get("FrameNumber") or 0) for r in rows})
        tops = sorted({int(r.get("ButtonTop") or 0) for r in rows})
        product_id = int(sl.get("ProductId") or 0) if has_sl_pid else None
        summary.append(
            {
                "sharedLayerId": slid,
                "name": sl.get("Name"),
                "productId": product_id,
                "isKeypadLayer": int(sl.get("IsKeypadLayer") or 0) if has_keypad else None,
                "rowCount": len(rows),
                "leftRange": (lefts[0], lefts[-1]) if lefts else None,
                "leftSlots": lefts,
                "frames": frames,
                "topRange": (tops[0], tops[-1]) if tops else None,
                "sample": [
                    {
                        "ButtonId": int(r.get("ButtonId") or 0),
                        "ButtonTagId": int(r.get("ButtonTagId") or 0),
                        "ButtonTagName": tag_by_id.get(int(r.get("ButtonTagId") or 0), ""),
                        "ButtonLeft": int(r.get("ButtonLeft") or 0),
                        "ButtonTop": int(r.get("ButtonTop") or 0),
                        "FrameNumber": int(r.get("FrameNumber") or 0),
                        "ButtonOrder": int(r.get("ButtonOrder") or 0),
                    }
                    for r in rows[:6]
                ],
            }
        )
    out["summaryPerHardKeyLayer"] = summary

    devices_with_pid_to_layers: list[dict[str, Any]] = []
    if has_rti_pid and has_sl_pid:
        for dev in devices:
            pid = int(dev.get("ProductId") or 0)
            matched = [sl for sl in hk_layers if int(sl.get("ProductId") or 0) == pid]
            devices_with_pid_to_layers.append(
                {
                    "RTIAddress": dev.get("RTIAddress"),
                    "DeviceId": dev.get("DeviceId"),
                    "DisplayName": dev.get("DisplayName"),
                    "Name": dev.get("Name"),
                    "ProductId": pid,
                    "matchedHardKeyLayers": [
                        {
                            "SharedLayerId": int(sl["SharedLayerId"]),
                            "Name": sl.get("Name"),
                            "ProductId": int(sl.get("ProductId") or 0),
                        }
                        for sl in matched
                    ],
                }
            )
    out["deviceToHardKeyLayers"] = devices_with_pid_to_layers

    if _table_exists(cur, "Products"):
        cur.execute("pragma table_info(Products)")
        product_cols = [str(r[1]) for r in cur.fetchall()]
        out["productsCols"] = product_cols
        try:
            cur.execute("select * from Products")
            out["products"] = [_row_dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError as exc:
            out["productsError"] = str(exc)
    else:
        out["productsCols"] = None

    return out


def render(out: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"apex: {out['apex']}")
    lines.append("")
    lines.append("== Schema columns of interest ==")
    for table, cols in out["schema"].items():
        lines.append(f"  {table}: {cols}")
    lines.append("")
    lines.append(f"SharedLayers has IsKeypadLayer column: {out['sharedLayersHasIsKeypadLayer']}")
    lines.append(f"SharedLayers has ProductId column:    {out['sharedLayersHasProductId']}")
    lines.append("")
    lines.append("== Devices (RTIDeviceData join Devices) ==")
    for d in out["devices"]:
        clone = d.get("CloneRTIAddress")
        clone_str = f" clone={clone}" if clone else ""
        pid = d.get("ProductId")
        pid_str = f" ProductId={pid}" if pid is not None else ""
        lines.append(
            f"  RTI={d.get('RTIAddress')} DevId={d.get('DeviceId')}{pid_str}{clone_str} DisplayName={d.get('DisplayName')!r} Name={d.get('Name')!r}"
        )
    lines.append("")
    lines.append("== Products table ==")
    if out.get("productsCols") is not None:
        lines.append(f"  cols: {out['productsCols']}")
        for p in out.get("products") or []:
            lines.append(f"    {p}")
    else:
        lines.append("  (no Products table in schema)")
    lines.append("")
    lines.append("== All SharedLayers ==")
    for sl in out["sharedLayersAll"]:
        nm = sl.get("Name")
        slid = sl.get("SharedLayerId")
        ikl = sl.get("IsKeypadLayer")
        pid = sl.get("ProductId")
        lines.append(f"  SharedLayerId={slid} ProductId={pid} IsKeypadLayer={ikl} Name={nm!r}")
    lines.append("")
    lines.append("== Candidate hard-key SharedLayers ==")
    for s in out["summaryPerHardKeyLayer"]:
        lines.append(
            f"  slid={s['sharedLayerId']} pid={s['productId']} name={s['name']!r} rows={s['rowCount']} leftRange={s['leftRange']} frames={s['frames']}"
        )
        lines.append(f"    leftSlots: {s['leftSlots']}")
        for sample in s["sample"]:
            lines.append(f"    sample: {sample}")
    lines.append("")
    lines.append("== Device -> matched hard-key layers (by ProductId) ==")
    for d in out["deviceToHardKeyLayers"]:
        lines.append(
            f"  RTI={d['RTIAddress']} DevId={d['DeviceId']} pid={d['ProductId']} disp={d['DisplayName']!r} name={d['Name']!r}"
        )
        for m in d["matchedHardKeyLayers"]:
            lines.append(f"    -> SharedLayerId={m['SharedLayerId']} pid={m['ProductId']} name={m['Name']!r}")
    lines.append("")
    lines.append("== Cross-check vs hard_keys.md expected ranges ==")
    for label, (lo, hi) in EXPECTED_RANGES.items():
        lines.append(f"  Expected {label}: {lo}..{hi}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe an .apex file for hard-key data.")
    ap.add_argument("apex", type=Path)
    ap.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    args = ap.parse_args()

    if not args.apex.exists():
        print(f"apex file not found: {args.apex}", file=sys.stderr)
        return 2

    out = probe(args.apex)
    print(render(out))

    if args.json:
        args.json.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
        print(f"\nJSON written: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
