from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


_log = logging.getLogger("uvicorn.error")

LINE_CAP = 100


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _heading(previous_filename: str, current_filename: str) -> str:
    prev = str(previous_filename or "").strip()
    curr = str(current_filename or "").strip()
    if prev and curr:
        return f"Change Log ({prev} -> {curr})"
    if curr:
        return f"Change Log ({curr})"
    return "Change Log"


def _empty_doc(
    *,
    status: str,
    previous_filename: str,
    current_filename: str,
    empty_message: str,
) -> dict[str, Any]:
    return {
        "status": status,
        "previousFilename": str(previous_filename or ""),
        "currentFilename": str(current_filename or ""),
        "heading": _heading(previous_filename, current_filename),
        "emptyMessage": empty_message,
        "testable": [],
        "layoutOnly": [],
        "testableOmitted": 0,
        "layoutOnlyOmitted": 0,
    }


def _button_id(button: dict[str, Any]) -> int | None:
    scope = _as_dict(button.get("apexScopeSource"))
    raw = _as_dict(scope.get("button")).get("buttonId")
    if raw is None:
        raw = _as_dict(button.get("buttonIdentity")).get("buttonId")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _page_id(button: dict[str, Any]) -> int:
    scope = _as_dict(button.get("apexScopeSource"))
    try:
        return int(_as_dict(scope.get("page")).get("pageId") or 0)
    except (TypeError, ValueError):
        return 0


def _device_id(button: dict[str, Any], fallback: Any) -> int:
    scope = _as_dict(button.get("apexScopeSource"))
    raw = _as_dict(scope.get("page")).get("deviceId")
    if raw is None:
        raw = fallback
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _button_label(button: dict[str, Any]) -> str:
    ident = _as_dict(button.get("buttonIdentity"))
    tag = str(ident.get("buttonTagName") or "").strip()
    text = str(ident.get("text") or "").strip()
    if tag:
        return tag
    if text:
        return text
    bid = _button_id(button)
    return f"button {bid}" if bid is not None else "button"


def _located_line(device_name: str, page_name: str, label: str, what: str) -> str:
    parts = [p for p in (device_name.strip(), page_name.strip(), label.strip()) if p]
    where = " / ".join(parts) if parts else "Item"
    return f"{where}: {what}"


def _iter_buttons(project_data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for device in _as_list(project_data.get("devices")):
        if not isinstance(device, dict):
            continue
        uf = _as_dict(device.get("userFacing"))
        diag = _as_dict(device.get("diagnostics"))
        device_name = str(uf.get("displayName") or diag.get("displayName") or "").strip()
        device_id = diag.get("deviceId")
        for page in _as_list(uf.get("pages")):
            if not isinstance(page, dict):
                continue
            page_name = str(page.get("pageName") or "").strip()
            for layer in _as_list(page.get("layers")):
                if not isinstance(layer, dict):
                    continue
                cats = _as_dict(layer.get("buttonCategories"))
                for items in cats.values():
                    for btn in _as_list(items):
                        if isinstance(btn, dict):
                            out.append(
                                {
                                    "deviceName": device_name,
                                    "deviceId": device_id,
                                    "pageName": page_name,
                                    "button": btn,
                                }
                            )
                for vp in _as_list(layer.get("viewports")):
                    if not isinstance(vp, dict):
                        continue
                    for vpl in _as_list(vp.get("layers")):
                        if not isinstance(vpl, dict):
                            continue
                        for frame in _as_list(vpl.get("frames")):
                            if not isinstance(frame, dict):
                                continue
                            for items in _as_dict(frame.get("buttonCategories")).values():
                                for btn in _as_list(items):
                                    if isinstance(btn, dict):
                                        out.append(
                                            {
                                                "deviceName": device_name,
                                                "deviceId": device_id,
                                                "pageName": page_name,
                                                "button": btn,
                                            }
                                        )
    return out


def _buttons_by_key(project_data: dict[str, Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    keyed: dict[tuple[int, int, int], dict[str, Any]] = {}
    for rec in _iter_buttons(project_data):
        btn = rec["button"]
        bid = _button_id(btn)
        if bid is None:
            continue
        key = (_device_id(btn, rec.get("deviceId")), _page_id(btn), bid)
        keyed[key] = rec
    return keyed


def _iter_viewports(project_data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for device in _as_list(project_data.get("devices")):
        if not isinstance(device, dict):
            continue
        uf = _as_dict(device.get("userFacing"))
        diag = _as_dict(device.get("diagnostics"))
        device_name = str(uf.get("displayName") or diag.get("displayName") or "").strip()
        try:
            device_id = int(diag.get("deviceId") or 0)
        except (TypeError, ValueError):
            device_id = 0
        for page in _as_list(uf.get("pages")):
            if not isinstance(page, dict):
                continue
            page_name = str(page.get("pageName") or "").strip()
            page_id = 0
            for layer in _as_list(page.get("layers")):
                if not isinstance(layer, dict):
                    continue
                host_labels: dict[int, str] = {}
                for items in _as_dict(layer.get("buttonCategories")).values():
                    for btn in _as_list(items):
                        if not isinstance(btn, dict):
                            continue
                        bid = _button_id(btn)
                        if bid is None:
                            continue
                        host_labels[bid] = _button_label(btn)
                        if page_id == 0:
                            page_id = _page_id(btn)
                for vp in _as_list(layer.get("viewports")):
                    if not isinstance(vp, dict):
                        continue
                    try:
                        vpid = int((_as_dict(vp.get("viewportIdentity")).get("viewportButtonId")) or 0)
                    except (TypeError, ValueError):
                        vpid = 0
                    layers = []
                    for vpl in _as_list(vp.get("layers")):
                        if not isinstance(vpl, dict):
                            continue
                        try:
                            order = int(vpl.get("layerOrder") or 0)
                        except (TypeError, ValueError):
                            order = 0
                        layers.append((order, str(vpl.get("layerName") or "").strip()))
                    out.append(
                        {
                            "key": (device_id, page_id, vpid),
                            "deviceName": device_name,
                            "pageName": page_name,
                            "label": host_labels.get(vpid) or f"VIEWPORT {vpid}",
                            "layers": layers,
                        }
                    )
    return out


def _expected_key_rows(resolved: dict[str, Any] | None) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    payload = _as_dict(resolved)
    events = _as_dict(payload.get("events"))
    for section in ("system", "driver"):
        title = "System events" if section == "system" else "Driver events"
        for key in _as_list(events.get(section)):
            rows.append((str(key), title))
    for device in _as_list(payload.get("devices")):
        if not isinstance(device, dict):
            continue
        name = str(device.get("displayName") or "").strip() or "Device"
        for key in _as_list(device.get("expected")):
            rows.append((str(key), name))
    return rows


def _key_tail(target_key: str) -> str:
    text = str(target_key or "").strip()
    if ":" in text:
        return text.rsplit(":", 1)[-1] or text
    return text or "target"


def _cap_lines(lines: list[str]) -> tuple[list[str], int]:
    if len(lines) <= LINE_CAP:
        return lines, 0
    return lines[:LINE_CAP], len(lines) - LINE_CAP


def _json_norm(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _bindings_snapshot(button: dict[str, Any]) -> dict[str, Any]:
    scope = _as_dict(button.get("apexScopeSource"))
    bindings = _as_dict(scope.get("bindings"))
    page_link = _as_dict(button.get("resolvedPageLink"))
    return {
        "macroIds": list(bindings.get("macroIds") or []),
        "variableIds": list(bindings.get("variableIds") or []),
        "pageLinkId": bindings.get("pageLinkId"),
        "targetPageId": page_link.get("targetPageId"),
    }


def _describe_testable_button(old_btn: dict[str, Any], new_btn: dict[str, Any]) -> str | None:
    bits: list[str] = []
    if _json_norm(old_btn.get("testTargets")) != _json_norm(new_btn.get("testTargets")):
        bits.append("test targets changed")
    old_bind = _bindings_snapshot(old_btn)
    new_bind = _bindings_snapshot(new_btn)
    if _json_norm(old_bind) != _json_norm(new_bind):
        if old_bind.get("macroIds") != new_bind.get("macroIds"):
            bits.append(f"macro ids {old_bind['macroIds']} → {new_bind['macroIds']}")
        elif old_bind.get("targetPageId") != new_bind.get("targetPageId"):
            bits.append(f"page-link destination {old_bind.get('targetPageId')} → {new_bind.get('targetPageId')}")
        else:
            bits.append("bindings changed")
    if not bits:
        return None
    return "; ".join(bits)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _describe_layout_button(old_btn: dict[str, Any], new_btn: dict[str, Any]) -> str | None:
    old_ui = _as_dict(old_btn.get("buttonUI"))
    new_ui = _as_dict(new_btn.get("buttonUI"))
    parts: list[str] = []
    moved_px = 0
    for orient in ("portrait", "landscape"):
        old_c = _as_dict(_as_dict(_as_dict(old_ui.get("orientations")).get(orient)).get("coordinates"))
        new_c = _as_dict(_as_dict(_as_dict(new_ui.get("orientations")).get(orient)).get("coordinates"))
        for field in ("top", "left", "height", "width"):
            ov, nv = _int(old_c.get(field)), _int(new_c.get(field))
            if ov != nv:
                parts.append(f"{orient} {field} {ov} → {nv}")
                if field in ("top", "left"):
                    moved_px += abs(nv - ov)
        old_vis = bool(_as_dict(_as_dict(old_ui.get("orientations")).get(orient)).get("visible", True))
        new_vis = bool(_as_dict(_as_dict(new_ui.get("orientations")).get(orient)).get("visible", True))
        if old_vis != new_vis:
            parts.append(f"{orient} visibility {old_vis} → {new_vis}")
    old_stack = _as_dict(old_ui.get("stack"))
    new_stack = _as_dict(new_ui.get("stack"))
    for field, label in (("layerOrder", "layer order"), ("buttonOrder", "button order")):
        ov, nv = _int(old_stack.get(field)), _int(new_stack.get(field))
        if ov != nv:
            parts.append(f"{label} {ov} → {nv}")
    if not parts:
        return None
    coord_parts = [p for p in parts if p.startswith("portrait ") or p.startswith("landscape ")]
    other_parts = [p for p in parts if p not in coord_parts]
    chunks: list[str] = []
    if coord_parts:
        if moved_px <= 1:
            prefix = "moved 1 px"
        elif moved_px <= 12:
            prefix = "moved a few px"
        else:
            prefix = f"moved {moved_px} px"
        chunks.append(f"{prefix} ({'; '.join(coord_parts)})")
    chunks.extend(other_parts)
    return "; ".join(chunks)


def _describe_viewport_layers(old_layers: list[tuple[int, str]], new_layers: list[tuple[int, str]]) -> str | None:
    if old_layers == new_layers:
        return None
    old_orders = [o for o, _ in old_layers]
    new_orders = [o for o, _ in new_layers]
    old_names = [n for _, n in old_layers if n]
    new_names = [n for _, n in new_layers if n]
    name_bit = ""
    if old_names and old_names == new_names:
        name_bit = f" ({', '.join(old_names)})"
    relative = " Relative stack unchanged." if old_names == new_names and old_orders != new_orders else ""
    old_txt = ", ".join(str(o) for o in old_orders) if old_orders else "(none)"
    new_txt = ", ".join(str(o) for o in new_orders) if new_orders else "(none)"
    return f"layer order {old_txt} → {new_txt}{name_bit}.{relative}".rstrip()


def build_changelog(
    *,
    old_project_data: dict[str, Any] | None,
    new_project_data: dict[str, Any] | None,
    old_resolved: dict[str, Any] | None,
    new_resolved: dict[str, Any] | None,
    previous_filename: str,
    current_filename: str,
) -> dict[str, Any]:
    if not isinstance(old_project_data, dict):
        return _empty_doc(
            status="first_file",
            previous_filename=previous_filename,
            current_filename=current_filename,
            empty_message="No previous file. Changelog starts on the next load.",
        )
    new_data = _as_dict(new_project_data)
    testable: list[str] = []
    layout_only: list[str] = []

    old_keys = {key: where for key, where in _expected_key_rows(old_resolved)}
    new_keys = {key: where for key, where in _expected_key_rows(new_resolved)}
    for key in sorted(set(new_keys) - set(old_keys)):
        where = new_keys.get(key) or "Device"
        testable.append(f"{where}: added test target {_key_tail(key)}")
    for key in sorted(set(old_keys) - set(new_keys)):
        where = old_keys.get(key) or "Device"
        testable.append(f"{where}: removed test target {_key_tail(key)}")

    old_buttons = _buttons_by_key(old_project_data)
    new_buttons = _buttons_by_key(new_data)
    for key in sorted(set(old_buttons) | set(new_buttons)):
        old_rec = old_buttons.get(key)
        new_rec = new_buttons.get(key)
        if old_rec is None or new_rec is None:
            continue
        old_btn = old_rec["button"]
        new_btn = new_rec["button"]
        device_name = str(new_rec.get("deviceName") or old_rec.get("deviceName") or "")
        page_name = str(new_rec.get("pageName") or old_rec.get("pageName") or "")
        label = _button_label(new_btn)
        testable_what = _describe_testable_button(old_btn, new_btn)
        if testable_what:
            testable.append(_located_line(device_name, page_name, label, testable_what))
            continue
        layout_what = _describe_layout_button(old_btn, new_btn)
        if layout_what:
            layout_only.append(_located_line(device_name, page_name, label, layout_what))

    old_vps = {rec["key"]: rec for rec in _iter_viewports(old_project_data)}
    new_vps = {rec["key"]: rec for rec in _iter_viewports(new_data)}
    for key in sorted(set(old_vps) | set(new_vps)):
        old_vp = old_vps.get(key)
        new_vp = new_vps.get(key)
        if old_vp is None or new_vp is None:
            continue
        what = _describe_viewport_layers(old_vp["layers"], new_vp["layers"])
        if not what:
            continue
        layout_only.append(
            _located_line(
                str(new_vp.get("deviceName") or ""),
                str(new_vp.get("pageName") or ""),
                str(new_vp.get("label") or "VIEWPORT"),
                what,
            )
        )

    if not testable and not layout_only:
        return _empty_doc(
            status="no_changes",
            previous_filename=previous_filename,
            current_filename=current_filename,
            empty_message="No changes since last file.",
        )

    testable_kept, testable_omitted = _cap_lines(testable)
    layout_kept, layout_omitted = _cap_lines(layout_only)
    return {
        "status": "ok",
        "previousFilename": str(previous_filename or ""),
        "currentFilename": str(current_filename or ""),
        "heading": _heading(previous_filename, current_filename),
        "emptyMessage": None,
        "testable": testable_kept,
        "layoutOnly": layout_kept,
        "testableOmitted": testable_omitted,
        "layoutOnlyOmitted": layout_omitted,
    }


def safe_build_changelog(**kwargs: Any) -> dict[str, Any]:
    previous_filename = str(kwargs.get("previous_filename") or "")
    current_filename = str(kwargs.get("current_filename") or "")
    try:
        return build_changelog(**kwargs)
    except Exception as exc:
        _log.warning("upload changelog build failed: %s", exc)
        return _empty_doc(
            status="error",
            previous_filename=previous_filename,
            current_filename=current_filename,
            empty_message="Changelog could not be computed.",
        )


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _first_named(directory: Path, suffix: str) -> Path | None:
    if not directory.is_dir():
        return None
    matches = sorted(p for p in directory.glob(f"*{suffix}") if p.is_file())
    return matches[0] if matches else None


def write_stage_changelog(
    *,
    old_dir: Path,
    stage_dir: Path,
    previous_filename: str,
    current_filename: str,
) -> dict[str, Any]:
    old_project = _first_named(old_dir, "_project_data.json")
    new_project = _first_named(stage_dir, "_project_data.json")
    old_resolved = None
    new_resolved = None
    if old_project is not None:
        old_resolved = old_dir / old_project.name.replace("_project_data.json", "_resolved_targets.json")
    if new_project is not None:
        new_resolved = stage_dir / new_project.name.replace("_project_data.json", "_resolved_targets.json")
    doc = safe_build_changelog(
        old_project_data=_load_json(old_project),
        new_project_data=_load_json(new_project),
        old_resolved=_load_json(old_resolved),
        new_resolved=_load_json(new_resolved),
        previous_filename=previous_filename,
        current_filename=current_filename,
    )
    try:
        (stage_dir / "upload_changelog.json").write_text(
            json.dumps(doc, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        _log.exception("upload changelog stage write failed")
    return doc
