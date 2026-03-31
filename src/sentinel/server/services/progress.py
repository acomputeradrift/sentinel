from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from sentinel.server.services.repositories import TestResultRecord


def _generated_root() -> Path:
    return Path(os.environ.get("SENTINEL_GENERATED_ROOT") or "generated").resolve()


def _project_dir(*, projectId: str) -> Path:
    return (_generated_root() / projectId).resolve()


def _latest_project_data_path(*, projectId: str) -> Path | None:
    project_dir = _project_dir(projectId=projectId)
    if not project_dir.exists() or not project_dir.is_dir():
        return None
    candidates = sorted(project_dir.glob("*_project_data.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _max_ts(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    return a if _parse_ts(a) >= _parse_ts(b) else b


def _counts_from_expected(expected: set[str], latest: dict[str, TestResultRecord]) -> tuple[dict[str, Any], str | None]:
    total = len(expected)
    tested = 0
    passed = 0
    failed = 0
    last_ts: str | None = None
    for key in expected:
        rec = latest.get(key)
        if rec is None:
            continue
        tested += 1
        last_ts = _max_ts(last_ts, rec.recordedAtUtc)
        if rec.outcome == "PASS":
            passed += 1
        elif rec.outcome == "FAIL":
            failed += 1
    untested = total - tested
    pct = (tested / total) if total else 0.0
    return (
        {
            "totalTargets": total,
            "testedTargets": tested,
            "pass": passed,
            "fail": failed,
            "untested": untested,
            "percentComplete": pct,
        },
        last_ts,
    )


def _normalize_target_name(label: str) -> str:
    s = str(label or "").strip()
    if s.lower().startswith("variable - "):
        tail = s[len("variable - ") :].strip()
        return ("Var." + tail) if tail else s
    return s


def _scope_program_ref(*, label: str, bindings: dict[str, Any]) -> str:
    lower = str(label or "").strip().lower()
    macro_ids = bindings.get("macroIds")
    variable_ids = bindings.get("variableIds")
    macro_step_ids = bindings.get("macroStepIds")
    macro_id = int(macro_ids[0]) if isinstance(macro_ids, list) and macro_ids else None
    variable_id = int(variable_ids[0]) if isinstance(variable_ids, list) and variable_ids else None
    macro_step_id = int(macro_step_ids[0]) if isinstance(macro_step_ids, list) and macro_step_ids else None
    if lower in {"macro", "macros"} and macro_id is not None:
        return f"macro:{macro_id}"
    if lower in {"macrostep", "macrosteps"} and macro_id is not None and macro_step_id is not None:
        return f"mstep:{macro_id}:{macro_step_id}"
    if lower.startswith("variable - ") or lower.startswith("var."):
        if variable_id is not None:
            return f"var:{variable_id}"
    return "none"


def _scoped_target_key_from_button(*, button: dict[str, Any], label: str) -> str | None:
    scope_source = button.get("apexScopeSource")
    if not isinstance(scope_source, dict):
        return None
    page = scope_source.get("page")
    layer = scope_source.get("layer")
    btn = scope_source.get("button")
    bindings = scope_source.get("bindings")
    if not isinstance(page, dict) or not isinstance(layer, dict) or not isinstance(btn, dict):
        return None
    if not isinstance(bindings, dict):
        bindings = {}

    rti_address = page.get("rtiAddress")
    page_room_id = page.get("roomId")
    page_source_id = page.get("sourceDeviceId")
    layer_room_id = layer.get("roomId")
    layer_source_id = layer.get("sourceId")
    effective_room_id = layer_room_id if layer_room_id is not None else page_room_id
    effective_source_id = layer_source_id if layer_source_id is not None else page_source_id
    button_tag_id = btn.get("buttonTagId")
    button_id = btn.get("buttonId")
    target_name = str(label or "").strip()

    if button_tag_id is not None:
        if rti_address is None or effective_room_id is None or effective_source_id is None:
            return None
        scope_type = "GLOBAL" if int(effective_room_id) == 0 else "ROOM"
        program_ref = _scope_program_ref(label=target_name, bindings=bindings)
        return (
            f"tt2:{int(rti_address)}:{scope_type}:{int(effective_room_id)}:{int(effective_source_id)}:"
            f"{int(button_tag_id)}:{program_ref}:{target_name}"
        )

    shared_layer_id = layer.get("sharedLayerId")
    layer_id = layer.get("layerId")
    scope_layer_id = shared_layer_id if shared_layer_id is not None else layer_id
    if rti_address is None or scope_layer_id is None or button_id is None:
        return None
    shared_flag = "SHARED" if shared_layer_id is not None else "LOCAL"
    return f"tt_ui:{int(rti_address)}:{shared_flag}:{int(scope_layer_id)}:{int(button_id)}:{target_name}"


def _event_target_labels(item: dict[str, Any]) -> list[str]:
    user = item.get("userFacing") if isinstance(item, dict) else {}
    test_targets = user.get("testTargets") if isinstance(user, dict) else {}
    if not isinstance(test_targets, dict):
        return []
    out: list[str] = []
    for label in ("Trigger", "Macro", "Macros", "MacroStep", "MacroSteps", "Command", "Commands"):
        if test_targets.get(label):
            out.append(label)
    return out


def _derive_event_section_targets(project_data: dict[str, Any]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {"system": set(), "driver": set()}
    events = project_data.get("events", {})
    if not isinstance(events, dict):
        return out

    for section in ("system", "driver"):
        items = events.get(section, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            diag = item.get("diagnostics", {})
            if not isinstance(diag, dict):
                continue
            event_id = diag.get("eventId")
            if event_id is None:
                continue
            for label in _event_target_labels(item):
                out[section].add(f"event:{int(event_id)}:{label}")
    return out


def _button_target_labels(btn: dict[str, Any]) -> list[str]:
    t = btn.get("testTargets", {})
    if not isinstance(t, dict):
        return []
    vars_t = t.get("variables", {})
    if not isinstance(vars_t, dict):
        vars_t = {}
    out: list[str] = []
    if t.get("text"):
        out.append("Text")
    if t.get("macros"):
        out.append("Macro")
    if t.get("macroSteps"):
        out.append("MacroStep")
    for name in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List"):
        if vars_t.get(name):
            out.append(f"Variable - {name}")
    if t.get("pageLink"):
        out.append("PageLink")
    return out


def _iter_page_buttons(page: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    layers = page.get("layers", [])
    if isinstance(layers, list) and layers:
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            cats = layer.get("buttonCategories", {})
            if not isinstance(cats, dict):
                continue
            for cat in ("screenLabels", "screenButtons", "hardButtons", "uiItems"):
                items = cats.get(cat, [])
                if not isinstance(items, list):
                    continue
                out.extend([b for b in items if isinstance(b, dict)])
        return out
    cats = page.get("buttonCategories", {})
    if not isinstance(cats, dict):
        return out
    for cat in ("screenLabels", "screenButtons", "hardButtons", "uiItems"):
        items = cats.get(cat, [])
        if not isinstance(items, list):
            continue
        out.extend([b for b in items if isinstance(b, dict)])
    return out


def _iter_page_viewports(page: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    layers = page.get("layers", [])
    if isinstance(layers, list) and layers:
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            vps = layer.get("viewports", [])
            if not isinstance(vps, list):
                continue
            out.extend([vp for vp in vps if isinstance(vp, dict)])
        return out
    vps = page.get("viewports", [])
    if isinstance(vps, list):
        out.extend([vp for vp in vps if isinstance(vp, dict)])
    return out


def _button_identity(btn: dict[str, Any]) -> tuple[str | None, str | None]:
    ident = btn.get("buttonIdentity", {})
    if not isinstance(ident, dict):
        return None, None
    tag = str(ident.get("buttonTagName") or "").strip() or None
    text = str(ident.get("text") or "").strip() or None
    return tag, text


def _diag_button_identity(btn: dict[str, Any]) -> tuple[str | None, str | None]:
    tag = str(btn.get("buttonTagName") or "").strip() or None
    ident = btn.get("identifiers", {})
    text = None
    if isinstance(ident, dict):
        text = str(ident.get("text") or "").strip() or None
    return tag, text


def _match_diag_button_id(diag_buttons: list[dict[str, Any]], user_button: dict[str, Any]) -> int | None:
    u_tag, u_text = _button_identity(user_button)
    if u_tag:
        for b in diag_buttons:
            d_tag, _d_text = _diag_button_identity(b)
            if d_tag == u_tag and b.get("buttonId") is not None:
                return int(b["buttonId"])
    if u_text:
        for b in diag_buttons:
            _d_tag, d_text = _diag_button_identity(b)
            if d_text == u_text and b.get("buttonId") is not None:
                return int(b["buttonId"])
    return None


def _match_diag_viewport_button_id(diag_frame_buttons: list[dict[str, Any]], user_button: dict[str, Any]) -> int | None:
    # Same matching strategy as normal buttons.
    return _match_diag_button_id(diag_frame_buttons, user_button)


def _derive_device_targets(project_data: dict[str, Any]) -> list[dict[str, Any]]:
    devices = project_data.get("devices", [])
    if not isinstance(devices, list):
        return []

    out: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        diag = device.get("diagnostics", {})
        if not isinstance(diag, dict):
            continue
        device_id = diag.get("deviceId")
        if device_id is None:
            continue
        user = device.get("userFacing", {})
        if not isinstance(user, dict):
            user = {}
        display = user.get("displayName") or diag.get("displayName") or diag.get("deviceName") or f"Device {device_id}"

        diag_pages = diag.get("pages", [])
        uf_pages = user.get("pages", [])
        if not isinstance(diag_pages, list):
            diag_pages = []
        if not isinstance(uf_pages, list):
            uf_pages = []

        expected: set[str] = set()
        for page_index, uf_page in enumerate(uf_pages):
            if not isinstance(uf_page, dict):
                continue
            diag_page = diag_pages[page_index] if page_index < len(diag_pages) and isinstance(diag_pages[page_index], dict) else None
            if not diag_page:
                continue
            page_id = diag_page.get("pageId")
            if page_id is None:
                continue
            diag_buttons = diag_page.get("buttons", [])
            if not isinstance(diag_buttons, list):
                diag_buttons = []

            # Normal page buttons.
            for uf_btn in _iter_page_buttons(uf_page):
                labels = _button_target_labels(uf_btn)
                if not labels:
                    continue
                button_id = _match_diag_button_id([b for b in diag_buttons if isinstance(b, dict)], uf_btn)
                if button_id is None:
                    continue
                for label in labels:
                    scoped_key = _scoped_target_key_from_button(button=uf_btn, label=label)
                    if scoped_key:
                        expected.add(scoped_key)
                        continue
                    name = _normalize_target_name(label)
                    expected.add(f"btn:{int(device_id)}:{int(page_id)}:{int(button_id)}:{name}")

            # Viewports (viewportButtonId comes from userFacing.viewportIdentity; child buttonId from diagnostics viewport frames).
            diag_viewports = diag_page.get("viewports", [])
            if not isinstance(diag_viewports, list):
                diag_viewports = []
            diag_viewports_dicts = [vp for vp in diag_viewports if isinstance(vp, dict)]

            for uf_vp in _iter_page_viewports(uf_page):
                vp_ident = uf_vp.get("viewportIdentity", {})
                if not isinstance(vp_ident, dict):
                    continue
                viewport_button_id = vp_ident.get("viewportButtonId")
                if viewport_button_id is None:
                    continue
                diag_vp = next((vp for vp in diag_viewports_dicts if vp.get("viewportButtonId") == viewport_button_id), None)
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
                                labels = _button_target_labels(uf_btn)
                                if not labels:
                                    continue
                                child_button_id = _match_diag_viewport_button_id(diag_frame_buttons_dicts, uf_btn)
                                if child_button_id is None:
                                    continue
                                for label in labels:
                                    scoped_key = _scoped_target_key_from_button(button=uf_btn, label=label)
                                    if scoped_key:
                                        expected.add(scoped_key)
                                        continue
                                    name = _normalize_target_name(label)
                                    expected.add(
                                        f"vpbtn:{int(device_id)}:{int(page_id)}:{int(viewport_button_id)}:{int(frame_id)}:{int(child_button_id)}:{name}"
                                    )

        out.append({"deviceId": int(device_id), "displayName": str(display), "expected": expected})
    return out


def commissioning_progress(*, projectId: str, latest_results: dict[str, TestResultRecord]) -> dict[str, Any]:
    path = _latest_project_data_path(projectId=projectId)
    if path is None:
        raise FileNotFoundError("project_data_missing")
    project_data = _load_json(path)

    event_targets = _derive_event_section_targets(project_data)
    device_targets = _derive_device_targets(project_data)

    all_expected: set[str] = set()
    for section_keys in event_targets.values():
        all_expected |= section_keys
    for d in device_targets:
        all_expected |= set(d["expected"])

    counts, last_ts = _counts_from_expected(all_expected, latest_results)
    system_counts, system_last = _counts_from_expected(event_targets["system"], latest_results)
    driver_counts, driver_last = _counts_from_expected(event_targets["driver"], latest_results)

    devices_out: list[dict[str, Any]] = []
    for d in device_targets:
        d_counts, d_last = _counts_from_expected(set(d["expected"]), latest_results)
        devices_out.append(
            {
                "deviceId": d["deviceId"],
                "displayName": d["displayName"],
                "counts": d_counts,
                "lastTestedAtUtc": d_last,
            }
        )

    return {
        "projectId": projectId,
        "asOfGenerationRunId": None,
        "counts": counts,
        "lastTestedAtUtc": last_ts,
        "eventSections": {
            "system": {"counts": system_counts, "lastTestedAtUtc": system_last},
            "driver": {"counts": driver_counts, "lastTestedAtUtc": driver_last},
        },
        "devices": devices_out,
    }

