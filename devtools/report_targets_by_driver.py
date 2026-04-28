"""
Count UI *test targets* (same rules as commissioning ``_derive_device_targets``) per **driver
bucket**, where the bucket is the **effective source device** display name when known, else the
controller display name. Categories match ``_button_target_labels`` / user-facing toggles:
``text``, ``macros``, ``macroSteps``, ``variables``, ``graphics``, ``pageLink``.

Also prints **driver event** rows (``events.driver``) with per-driver counts of event test labels
(Trigger, Macro, MacroStep, Command, …).

Either pass generated ``*_project_data.json``, or pass ``--apex`` (e.g. ``Assets/Sung Residence
v207.2.apex``) to run extraction first (large files may take minutes).

Run from repo root with ``sentinel`` importable (``pip install -e .`` or equivalent).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sentinel.server.services import progress as prog  # noqa: E402

UI_CATS = ("text", "macros", "macroSteps", "variables", "graphics", "pageLink")


def _label_to_ui_category(label: str) -> str | None:
    if label == "Text":
        return "text"
    if label == "Macro":
        return "macros"
    if label == "MacroStep":
        return "macroSteps"
    if str(label).startswith("Variable - "):
        return "variables"
    if label in ("Bitmap", "Icon"):
        return "graphics"
    if label == "PageLink":
        return "pageLink"
    return None


def _device_display_map(project_data: dict[str, Any]) -> dict[int, str]:
    out: dict[int, str] = {}
    devices = project_data.get("devices", [])
    if not isinstance(devices, list):
        return out
    for device in devices:
        if not isinstance(device, dict):
            continue
        diag = device.get("diagnostics", {})
        if not isinstance(diag, dict):
            continue
        did = diag.get("deviceId")
        if did is None:
            continue
        user = device.get("userFacing", {})
        disp = ""
        if isinstance(user, dict):
            disp = str(user.get("displayName") or "").strip()
        if not disp:
            disp = str(diag.get("displayName") or diag.get("deviceName") or f"Device {did}").strip()
        out[int(did)] = disp or f"Device {int(did)}"
    return out


def _effective_scope_from_diag_button(diag_button: dict[str, Any]) -> tuple[int | None, int | None, str, str]:
    rc = diag_button.get("resolvedContext")
    if not isinstance(rc, dict):
        return None, None, "", ""
    rid = rc.get("effectiveRoomId")
    sid = rc.get("effectiveSourceId")
    try:
        room_id = int(rid) if rid is not None else None
    except Exception:
        room_id = None
    try:
        src_id = int(sid) if sid is not None else None
    except Exception:
        src_id = None
    rn = str(rc.get("effectiveRoomName") or "").strip()
    sn = str(rc.get("effectiveSourceName") or "").strip()
    return room_id, src_id, rn, sn


def _source_id_from_scoped_key(scoped: str | None) -> int | None:
    if not scoped or not str(scoped).startswith("tt2:"):
        return None
    parts = str(scoped).split(":")
    if len(parts) < 6:
        return None
    try:
        return int(parts[4])
    except Exception:
        return None


def _driver_bucket(
    *,
    device_names: dict[int, str],
    controller_display: str,
    effective_source_id: int | None,
    scoped_key: str | None,
    effective_source_name: str = "",
) -> str:
    sid = effective_source_id
    if sid is None or sid <= 0:
        sid = _source_id_from_scoped_key(scoped_key)
    if sid is not None and sid > 0:
        mapped = device_names.get(sid)
        if mapped:
            return mapped
        name = str(effective_source_name or "").strip()
        if name:
            return f"{name} (#{sid})"
        return f"device#{sid}"
    return controller_display


def collect_ui_targets_by_driver(project_data: dict[str, Any]) -> tuple[dict[str, dict[str, int]], dict[str, set[str]]]:
    """Returns (counts per driver bucket -> category -> n, scope lines per bucket)."""
    device_names = _device_display_map(project_data)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    scopes: dict[str, set[str]] = defaultdict(set)

    devices = project_data.get("devices", [])
    if not isinstance(devices, list):
        return counts, scopes

    def walk_buttons(
        *,
        controller_display: str,
        uf_page: dict[str, Any],
        diag_buttons: list[dict[str, Any]],
    ) -> None:
        for uf_btn in prog._iter_page_buttons(uf_page):
            labels = prog._button_target_labels(uf_btn)
            if not labels:
                continue
            button_id = prog._match_diag_button_id([b for b in diag_buttons if isinstance(b, dict)], uf_btn)
            if button_id is None:
                scoped_id = prog._scope_button_id(uf_btn)
                if scoped_id is not None and any(
                    isinstance(b, dict) and int(b.get("buttonId") or -1) == scoped_id for b in diag_buttons
                ):
                    button_id = scoped_id
            if button_id is None:
                continue
            diag_btn = next((b for b in diag_buttons if isinstance(b, dict) and int(b.get("buttonId") or -1) == button_id), None)
            if not isinstance(diag_btn, dict):
                continue
            room_id, eff_src, room_name, src_name = _effective_scope_from_diag_button(diag_btn)
            scope_line = (
                f"room={room_id if room_id is not None else '?'} {room_name!r} | "
                f"src={eff_src if eff_src is not None else '?'} {src_name!r}"
            )
            for label in labels:
                cat = _label_to_ui_category(label)
                if cat is None:
                    continue
                scoped_key = prog._scoped_target_key_from_button(button=uf_btn, label=label)
                bucket = _driver_bucket(
                    device_names=device_names,
                    controller_display=controller_display,
                    effective_source_id=eff_src,
                    scoped_key=scoped_key,
                    effective_source_name=src_name,
                )
                scopes[bucket].add(scope_line)
                counts[bucket][cat] += 1

    for device in devices:
        if not isinstance(device, dict):
            continue
        diag = device.get("diagnostics", {})
        if not isinstance(diag, dict):
            continue
        device_id = diag.get("deviceId")
        if device_id is None:
            continue
        device_id = int(device_id)
        user = device.get("userFacing", {})
        if not isinstance(user, dict):
            user = {}
        controller_display = str(
            user.get("displayName") or diag.get("displayName") or diag.get("deviceName") or f"Device {device_id}"
        ).strip() or f"Device {device_id}"

        diag_pages = diag.get("pages", [])
        uf_pages = user.get("pages", [])
        if not isinstance(diag_pages, list):
            diag_pages = []
        if not isinstance(uf_pages, list):
            uf_pages = []

        for page_index, uf_page in enumerate(uf_pages):
            if not isinstance(uf_page, dict):
                continue
            diag_page = diag_pages[page_index] if page_index < len(diag_pages) and isinstance(diag_pages[page_index], dict) else None
            if not diag_page:
                continue
            diag_buttons = diag_page.get("buttons", [])
            if not isinstance(diag_buttons, list):
                diag_buttons = []

            walk_buttons(
                controller_display=controller_display,
                uf_page=uf_page,
                diag_buttons=[b for b in diag_buttons if isinstance(b, dict)],
            )

            diag_viewports = diag_page.get("viewports", [])
            if not isinstance(diag_viewports, list):
                diag_viewports = []
            diag_viewports_dicts = [vp for vp in diag_viewports if isinstance(vp, dict)]

            for uf_vp in prog._iter_page_viewports(uf_page):
                vp_ident = uf_vp.get("viewportIdentity", {})
                if not isinstance(vp_ident, dict):
                    continue
                viewport_button_id = vp_ident.get("viewportButtonId")
                if viewport_button_id is None:
                    continue
                diag_vp = next(
                    (vp for vp in diag_viewports_dicts if vp.get("viewportButtonId") == viewport_button_id),
                    None,
                )
                if not isinstance(diag_vp, dict):
                    continue
                vp_layers = uf_vp.get("layers", [])
                if not isinstance(vp_layers, list):
                    continue
                for vp_layer in vp_layers:
                    if not isinstance(vp_layer, dict):
                        continue
                    frames = vp_layer.get("frames", [])
                    if not isinstance(frames, list):
                        continue
                    for uf_frame in frames:
                        if not isinstance(uf_frame, dict):
                            continue
                        frame_id = uf_frame.get("frameId")
                        if frame_id is None:
                            continue
                        diag_frames = diag_vp.get("frames", [])
                        if not isinstance(diag_frames, list):
                            continue
                        diag_frame = next((f for f in diag_frames if isinstance(f, dict) and f.get("frameId") == frame_id), None)
                        if not isinstance(diag_frame, dict):
                            continue
                        diag_frame_buttons = diag_frame.get("buttons", [])
                        if not isinstance(diag_frame_buttons, list):
                            diag_frame_buttons = []
                        diag_frame_buttons_dicts = [b for b in diag_frame_buttons if isinstance(b, dict)]
                        cats = uf_frame.get("buttonCategories", {})
                        if not isinstance(cats, dict):
                            continue
                        for cat in ("screenLabels", "screenButtons", "hardButtons", "uiItems"):
                            uf_buttons = cats.get(cat, [])
                            if not isinstance(uf_buttons, list):
                                continue
                            for uf_btn in uf_buttons:
                                if not isinstance(uf_btn, dict):
                                    continue
                                labels = prog._button_target_labels(uf_btn)
                                if not labels:
                                    continue
                                child_button_id = prog._match_diag_viewport_button_id(diag_frame_buttons_dicts, uf_btn)
                                if child_button_id is None:
                                    continue
                                diag_btn = next(
                                    (
                                        b
                                        for b in diag_frame_buttons_dicts
                                        if isinstance(b, dict) and int(b.get("buttonId") or -1) == child_button_id
                                    ),
                                    None,
                                )
                                if not isinstance(diag_btn, dict):
                                    continue
                                room_id, eff_src, room_name, src_name = _effective_scope_from_diag_button(diag_btn)
                                scope_line = (
                                    f"room={room_id if room_id is not None else '?'} {room_name!r} | "
                                    f"src={eff_src if eff_src is not None else '?'} {src_name!r}"
                                )
                                for label in labels:
                                    ucat = _label_to_ui_category(label)
                                    if ucat is None:
                                        continue
                                    scoped_key = prog._scoped_target_key_from_button(button=uf_btn, label=label)
                                    bucket = _driver_bucket(
                                        device_names=device_names,
                                        controller_display=controller_display,
                                        effective_source_id=eff_src,
                                        scoped_key=scoped_key,
                                        effective_source_name=src_name,
                                    )
                                    scopes[bucket].add(scope_line)
                                    counts[bucket][ucat] += 1

    return counts, scopes


def collect_driver_event_targets(project_data: dict[str, Any]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    events = project_data.get("events", {})
    if not isinstance(events, dict):
        return out
    items = events.get("driver", [])
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        diag = item.get("diagnostics", {})
        user = item.get("userFacing", {})
        name = ""
        if isinstance(diag, dict):
            name = str(diag.get("driverName") or "").strip()
        if not name and isinstance(user, dict):
            name = str(user.get("driverName") or "").strip()
        if not name:
            name = "(unnamed driver event)"
        for label in prog._event_target_labels(item):
            out[name][label] += 1
    return out


def _print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def print_driver_summary_tables(
    ui_counts: dict[str, dict[str, int]],
    ev: dict[str, dict[str, int]],
) -> None:
    """Name, total targets, %% of all targets, category breakdown (UI + driver events)."""
    ui_rows: list[tuple[str, int, dict[str, int]]] = []
    for name, row in ui_counts.items():
        cats = {c: int(row.get(c, 0)) for c in UI_CATS}
        ui_rows.append((name, sum(cats.values()), cats))
    ui_grand = sum(t for _n, t, _c in ui_rows)

    ev_rows: list[tuple[str, int, dict[str, int]]] = []
    ev_label_order: list[str] = []
    seen_lab: set[str] = set()
    for name, d in ev.items():
        dd = {str(k): int(v) for k, v in d.items()}
        ev_rows.append((name, sum(dd.values()), dd))
        for k in dd:
            if k not in seen_lab:
                seen_lab.add(k)
                ev_label_order.append(k)
    ev_label_order.sort(key=lambda s: s.lower())
    ev_grand = sum(t for _n, t, _c in ev_rows)

    grand = ui_grand + ev_grand

    def pct(n: int) -> str:
        return f"{(100.0 * n / grand):.2f}%" if grand else "0.00%"

    _print_section("Effective source (UI): total, % of all targets, breakdown by category")
    col_w = 11
    name_w = 52
    hdr = f"{'Name':<{name_w}} {'Total':>8} {'Pct':>9}"
    for c in UI_CATS:
        hdr += f" {c:>{col_w}}"
    print(hdr)
    print("-" * len(hdr))
    for name, total, cats in sorted(ui_rows, key=lambda x: x[0].lower()):
        line = f"{name[: name_w - 1]:<{name_w}} {total:>8} {pct(total):>9}"
        for c in UI_CATS:
            line += f" {cats[c]:>{col_w}}"
        print(line)
    print("-" * len(hdr))
    print(f"{'Subtotal UI':<{name_w}} {ui_grand:>8} {pct(ui_grand):>9}")

    if ev_rows:
        _print_section("Driver events (events.driver): total, % of all, label breakdown")
        hdr2 = f"{'Name':<{name_w}} {'Total':>8} {'Pct':>9}"
        for lab in ev_label_order:
            hdr2 += f" {lab[:col_w]:>{col_w}}"
        print(hdr2)
        print("-" * len(hdr2))
        for name, total, dd in sorted(ev_rows, key=lambda x: x[0].lower()):
            line = f"{name[: name_w - 1]:<{name_w}} {total:>8} {pct(total):>9}"
            for lab in ev_label_order:
                line += f" {int(dd.get(lab, 0)):>{col_w}}"
            print(line)
        print("-" * len(hdr2))
        print(f"{'Subtotal driver events':<{name_w}} {ev_grand:>8} {pct(ev_grand):>9}")

    _print_section("Grand total (UI + driver event targets)")
    print(f"{'All targets':<{52}} {grand:>8} {'100.00%' if grand else '0.00%':>9}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Test targets per driver bucket + category breakdown.")
    src_grp = ap.add_mutually_exclusive_group(required=True)
    src_grp.add_argument(
        "--project-json",
        type=Path,
        default=None,
        help="Path to *_project_data.json (generated extraction output).",
    )
    src_grp.add_argument(
        "--apex",
        type=Path,
        default=None,
        help="Path to .apex: run full extract_project_data first (slow on large projects).",
    )
    ap.add_argument(
        "--max-scopes",
        type=int,
        default=6,
        help="With --detail: max scope lines per bucket (default 6).",
    )
    ap.add_argument(
        "--detail",
        action="store_true",
        help="Print per-bucket scope lines and legacy long format after the summary tables.",
    )
    args = ap.parse_args()
    project_data: dict[str, Any]
    if args.apex is not None:
        apex_path = args.apex.resolve()
        if not apex_path.is_file():
            print(f"File not found: {apex_path}", file=sys.stderr)
            return 2
        contract = (ROOT / "src" / "sentinel" / "contracts" / "apex_project_structure_v4.json").resolve()
        if not contract.is_file():
            print(f"Contract not found: {contract}", file=sys.stderr)
            return 2
        from sentinel.extraction.extractor_core import ExtractContext, extract_project_data  # noqa: E402

        print(f"Extracting: {apex_path}", flush=True)
        project_data = extract_project_data(
            ExtractContext(apex_path=apex_path, project_structure_path=contract),
            progress_hook=None,
        )
    else:
        path = args.project_json.resolve()
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            return 2
        project_data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    src = project_data.get("source", {})
    if isinstance(src, dict) and src.get("file"):
        print(f"Source: {src.get('file')}")

    ui_counts, scopes = collect_ui_targets_by_driver(project_data)
    ev = collect_driver_event_targets(project_data)
    print_driver_summary_tables(ui_counts, ev)

    if args.detail:
        _print_section("UI test targets by driver bucket (effective source device when available)")
        for bucket in sorted(ui_counts.keys(), key=lambda s: s.lower()):
            row = ui_counts[bucket]
            parts = [f"{c}={int(row.get(c, 0))}" for c in UI_CATS]
            print(f"{bucket} ({', '.join(parts)})")
            scope_lines = sorted(scopes.get(bucket, ()))
            if scope_lines:
                shown = scope_lines[: max(0, int(args.max_scopes))]
                for line in shown:
                    print(f"    scope: {line}")
                if len(scope_lines) > len(shown):
                    print(f"    ... +{len(scope_lines) - len(shown)} more distinct scope lines")

        _print_section("Driver *event* test labels (events.driver: Trigger / Macro / Command / ...)")
        if not ev:
            print("(no driver events in this file)")
        else:
            for name in sorted(ev.keys(), key=lambda s: s.lower()):
                bits = [f"{k}={int(v)}" for k, v in sorted(ev[name].items())]
                print(f"{name} ({', '.join(bits)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
