from __future__ import annotations

from html import escape
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _resolution_or_default(resolution: dict[str, Any] | None, default_width: int, default_height: int) -> dict[str, int]:
    raw = resolution or {}
    width = int(raw.get("width") or 0)
    height = int(raw.get("height") or 0)
    if width > 0 and height > 0:
        return {"width": width, "height": height}
    return {"width": default_width, "height": default_height}


def page_index_by_name(project_data: dict[str, Any], page_name: str, device_index: int = 0) -> int:
    pages = project_data["devices"][device_index]["userFacing"]["pages"]
    for i, page in enumerate(pages):
        if str(page.get("pageName") or "") == page_name:
            return i
    raise ValueError(f"Page not found: {page_name}")


def page_slug(page_name: str, page_index: int) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", (page_name or "").strip()).strip("-").lower()
    return slug or f"page-{page_index}"


def device_filename(project_stem: str, device_name: str, device_index: int) -> str:
    return f"{project_stem}__device-{device_index}-{page_slug(device_name, device_index)}.html"


def project_home_filename(project_stem: str) -> str:
    return f"{project_stem}__project-home.html"


def project_manifest_filename(project_stem: str) -> str:
    return f"{project_stem}__project-manifest.json"


def device_payload_filename(project_stem: str, device_name: str, device_index: int) -> str:
    return f"{project_stem}__device-{device_index}-{page_slug(device_name, device_index)}__payload.json"


def _btn_text(identity: dict[str, Any]) -> str:
    text = str(identity.get("text") or "").strip()
    tag = str(identity.get("buttonTagName") or "").strip()
    return text if text else tag


def _page_link_enabled(targets: dict[str, Any]) -> bool:
    page_link = targets.get("pageLink")
    if isinstance(page_link, dict):
        return bool(page_link.get("enabled"))
    return bool(page_link)


def _page_link_target_id(btn: dict[str, Any]) -> int | None:
    resolved = btn.get("resolvedPageLink")
    if isinstance(resolved, dict):
        raw = resolved.get("targetPageId")
        return int(raw) if raw is not None else None
    return None


def _button_tag_name(btn: dict[str, Any]) -> str:
    return str(btn.get("buttonIdentity", {}).get("buttonTagName") or "").strip()


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _diag_match_button_id(diag_buttons: list[dict[str, Any]], user_btn: dict[str, Any]) -> int | None:
    user_identity = user_btn.get("buttonIdentity", {}) if isinstance(user_btn, dict) else {}
    user_tag = _norm_text(user_identity.get("buttonTagName"))
    user_text = _norm_text(user_identity.get("text"))
    if not user_tag and not user_text:
        return None

    matches: list[int] = []
    for diag in diag_buttons:
        if not isinstance(diag, dict):
            continue
        diag_tag = _norm_text(diag.get("buttonTagName"))
        diag_text = _norm_text((diag.get("identifiers") or {}).get("text"))
        if diag_tag == user_tag and diag_text == user_text:
            button_id = diag.get("buttonId")
            if button_id is not None:
                matches.append(int(button_id))

    if len(matches) == 1:
        return matches[0]
    return None


def _diag_match_viewport_button_ids(
    diag_viewports: list[dict[str, Any]],
    *,
    vp_index: int,
    frame_id: int,
    user_btn: dict[str, Any],
) -> tuple[int | None, int | None]:
    if vp_index < 0 or vp_index >= len(diag_viewports):
        return None, None
    diag_vp = diag_viewports[vp_index]
    if not isinstance(diag_vp, dict):
        return None, None
    viewport_button_id = diag_vp.get("viewportButtonId")
    frames = diag_vp.get("frames", [])
    if not isinstance(frames, list):
        frames = []
    diag_frame = next((f for f in frames if isinstance(f, dict) and int(f.get("frameId", -1)) == int(frame_id)), None)
    diag_buttons = (diag_frame.get("buttons") if isinstance(diag_frame, dict) else None) or []
    if not isinstance(diag_buttons, list):
        diag_buttons = []
    return (int(viewport_button_id) if viewport_button_id is not None else None), _diag_match_button_id(diag_buttons, user_btn)


def _room_name_from_button_tag(tag_name: str) -> str | None:
    tag = str(tag_name or "").strip()
    if not tag.lower().startswith("room:"):
        return None
    name = tag.split(":", 1)[1].strip()
    return name or None


def _targets(btn: dict[str, Any], variable_label_template: str) -> list[str]:
    t = btn.get("testTargets", {})
    vars_t = t.get("variables", {})
    graphics_t = t.get("graphics", {})
    out: list[str] = []
    if t.get("text"):
        out.append("Text")
    if t.get("macros"):
        out.append("Macro")
    if t.get("macroSteps"):
        out.append("MacroStep")
    for name in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List"):
        if vars_t.get(name):
            out.append(variable_label_template.replace("{variableType}", name))
    if graphics_t.get("bitmap"):
        out.append("Bitmap")
    if graphics_t.get("icon"):
        out.append("Icon")
    if _page_link_enabled(t):
        out.append("PageLink")
    return out


def _category_key_from_label(label: str) -> str:
    value = str(label or "").strip().lower()
    if value == "screen label":
        return "screenLabels"
    if value == "screen button":
        return "screenButtons"
    if value == "hard button":
        return "hardButtons"
    if value == "ui item":
        return "uiItems"
    if value == "empty tag":
        return "emptyTag"
    return "screenButtons"


def _is_ui_only_button(btn: dict[str, Any]) -> bool:
    identity = btn.get("buttonIdentity", {})
    t = btn.get("testTargets", {})
    vars_t = t.get("variables", {})
    graphics_t = t.get("graphics", {})
    has_any_var = any(bool(vars_t.get(k)) for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List"))
    has_any_graphics = bool(graphics_t.get("bitmap")) or bool(graphics_t.get("icon"))
    return (
        not str(identity.get("buttonTagName") or "").strip()
        and not str(identity.get("text") or "").strip()
        and not bool(t.get("text"))
        and not bool(t.get("macros"))
        and not bool(t.get("macroSteps"))
        and not _page_link_enabled(t)
        and not has_any_var
        and not has_any_graphics
    )


def _layer_key(layer_index: int) -> str:
    return f"layer-{layer_index}"


def _page_layers(page: dict[str, Any]) -> list[dict[str, Any]]:
    layers = page.get("layers", [])
    if not isinstance(layers, list):
        return []
    return sorted(layers, key=lambda layer: (int(layer.get("layerOrder", 0) or 0), str(layer.get("layerName") or "")))


def _page_layer_state(page: dict[str, Any]) -> list[dict[str, Any]]:
    layers = _page_layers(page)
    if not layers:
        return [{"key": _layer_key(0), "name": "Page Layer", "layerOrder": 0}]
    out: list[dict[str, Any]] = []
    for index, layer in enumerate(layers):
        name = str(layer.get("layerName") or "").strip() or f"Layer {index + 1}"
        out.append({"key": _layer_key(index), "name": name, "layerOrder": int(layer.get("layerOrder", 0) or 0)})
    return sorted(out, key=lambda layer: (-int(layer.get("layerOrder", 0) or 0), str(layer.get("name") or "")))


def _button_stack_sort_key(btn: dict[str, Any], category_rank: int) -> tuple[int, int, int]:
    stack = ((btn.get("buttonUI") or {}).get("stack") or {}) if isinstance(btn, dict) else {}
    button_order = int(stack.get("buttonOrder", 0) or 0)
    frame_number = int(stack.get("frameNumber", 0) or 0)
    return (button_order, frame_number, category_rank)


def _iter_page_buttons(page: dict[str, Any]) -> list[tuple[dict[str, Any], str, int, int, str, int]]:
    items: list[tuple[dict[str, Any], str, int, int, str, int]] = []
    category_defs: list[tuple[str, str]] = [
        ("screenLabels", "Screen Label"),
        ("screenButtons", "Screen Button"),
        ("hardButtons", "Hard Button"),
        ("uiItems", "UI Item"),
    ]
    layers = _page_layers(page)
    if layers:
        for layer_index, layer in enumerate(layers):
            layer_key = _layer_key(layer_index)
            layer_order = int(layer.get("layerOrder", 0) or 0)
            cats = layer.get("buttonCategories", {})
            layer_items: list[tuple[dict[str, Any], str, int]] = []
            for rank, (cat, label) in enumerate(category_defs):
                for btn in cats.get(cat, []):
                    if cat != "uiItems" and _is_ui_only_button(btn):
                        continue
                    layer_items.append((btn, label, rank))
            layer_items.sort(key=lambda item: _button_stack_sort_key(item[0], item[2]))
            for btn, label, _rank in layer_items:
                items.append((btn, label, 0, 0, layer_key, layer_order))
        return items
    root_items: list[tuple[dict[str, Any], str, int]] = []
    for rank, (cat, label) in enumerate(category_defs):
        for btn in page.get("buttonCategories", {}).get(cat, []):
            if cat != "uiItems" and _is_ui_only_button(btn):
                continue
            root_items.append((btn, label, rank))
    root_items.sort(key=lambda item: _button_stack_sort_key(item[0], item[2]))
    for btn, label, _rank in root_items:
        items.append((btn, label, 0, 0, _layer_key(0), 0))
    return items


def _orientation_ui(ui: dict[str, Any], orientation: str) -> dict[str, Any]:
    orientations = ui.get("orientations", {})
    oriented = orientations.get(orientation, {})
    if oriented:
        return oriented
    fallback = orientations.get("portrait") or orientations.get("landscape")
    if fallback:
        return fallback
    return ui


def _visible_in_any_orientation(ui: dict[str, Any]) -> bool:
    orientations = ui.get("orientations", {})
    if isinstance(orientations, dict) and orientations:
        portrait = orientations.get("portrait")
        landscape = orientations.get("landscape")
        portrait_visible = bool(portrait.get("visible", True)) if isinstance(portrait, dict) else False
        landscape_visible = bool(landscape.get("visible", True)) if isinstance(landscape, dict) else False
        return portrait_visible or landscape_visible
    return bool(ui.get("visible", True))


def _ui_coordinates(ui: dict[str, Any], orientation: str) -> dict[str, int]:
    if "coordinates" in ui:
        return ui.get("coordinates", {})
    oriented = _orientation_ui(ui, orientation)
    if oriented.get("coordinates"):
        return oriented.get("coordinates", {})
    return {}


def _orientation_data_attrs(
    ui: dict[str, Any],
    *,
    portrait_offset_left: int = 0,
    portrait_offset_top: int = 0,
    landscape_offset_left: int = 0,
    landscape_offset_top: int = 0,
) -> str:
    orientations = ui.get("orientations", {})
    attrs: list[str] = []
    for key, short in (("portrait", "p"), ("landscape", "l")):
        oriented = orientations.get(key, {})
        coords = oriented.get("coordinates", {})
        offset_left = portrait_offset_left if key == "portrait" else landscape_offset_left
        offset_top = portrait_offset_top if key == "portrait" else landscape_offset_top
        attrs.append(f"data-{short}-visible='{'1' if bool(oriented.get('visible', True)) else '0'}'")
        attrs.append(f"data-{short}-left='{int(coords.get('left') or 0) + offset_left}'")
        attrs.append(f"data-{short}-top='{int(coords.get('top') or 0) + offset_top}'")
        attrs.append(f"data-{short}-width='{int(coords.get('width') or 0)}'")
        attrs.append(f"data-{short}-height='{int(coords.get('height') or 0)}'")
    return " ".join(attrs)


def _iter_viewport_boxes(page: dict[str, Any], orientation: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page_viewports: list[dict[str, Any]] = []
    layers = _page_layers(page)
    if layers:
        for layer_index, layer in enumerate(layers):
            layer_key = _layer_key(layer_index)
            layer_order = int(layer.get("layerOrder", 0) or 0)
            for viewport in layer.get("viewports", []):
                page_viewports.append({"viewport": viewport, "layer_key": layer_key, "layer_order": layer_order})
    else:
        page_viewports = [{"viewport": viewport, "layer_key": _layer_key(0), "layer_order": 0} for viewport in page.get("viewports", [])]
    for vp_index, entry in enumerate(page_viewports):
        viewport = entry["viewport"]
        viewport_ui = viewport.get("viewportUI", {})
        if not _visible_in_any_orientation(viewport_ui):
            continue
        c = _ui_coordinates(viewport_ui, orientation)
        out.append(
            {
                "left": int(c.get("left") or 0),
                "top": int(c.get("top") or 0),
                "width": int(c.get("width") or 0),
                "height": int(c.get("height") or 0),
                "viewport_ui": viewport_ui,
                "layer_key": entry["layer_key"],
                "layer_order": entry["layer_order"],
                "vp_index": vp_index,
            }
        )
    return out


def _iter_viewport_buttons(page: dict[str, Any], orientation: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page_viewports: list[dict[str, Any]] = []
    layers = _page_layers(page)
    if layers:
        for layer_index, layer in enumerate(layers):
            layer_key = _layer_key(layer_index)
            layer_order = int(layer.get("layerOrder", 0) or 0)
            for viewport in layer.get("viewports", []):
                page_viewports.append({"viewport": viewport, "layer_key": layer_key, "layer_order": layer_order})
    else:
        page_viewports = [{"viewport": viewport, "layer_key": _layer_key(0), "layer_order": 0} for viewport in page.get("viewports", [])]
    for vp_index, entry in enumerate(page_viewports):
        viewport = entry["viewport"]
        viewport_ui = viewport.get("viewportUI", {})
        if not _visible_in_any_orientation(viewport_ui):
            continue
        # Viewport-child buttons must inherit the container viewport's orientation visibility.
        vp_orientations = viewport_ui.get("orientations", {})
        vp_portrait_visible = bool((vp_orientations.get("portrait") or {}).get("visible", True))
        vp_landscape_visible = bool((vp_orientations.get("landscape") or {}).get("visible", True))
        vp_c = _ui_coordinates(viewport_ui, orientation)
        portrait_vp_c = _ui_coordinates(viewport_ui, "portrait")
        landscape_vp_c = _ui_coordinates(viewport_ui, "landscape")
        off_top = int(vp_c.get("top") or 0)
        off_left = int(vp_c.get("left") or 0)
        frame_entries: list[dict[str, Any]] = []
        if viewport.get("layers"):
            for layer_index, layer in enumerate(viewport.get("layers", [])):
                vp_layer_key = f"vp-layer-{layer_index}"
                vp_layer_name = str(layer.get("layerName") or "").strip()
                vp_layer_order = int(layer.get("layerOrder", 0) or 0)
                for frame in layer.get("frames", []):
                    frame_entries.append(
                        {
                            "frame": frame,
                            "vp_layer_key": vp_layer_key,
                            "vp_layer_name": vp_layer_name,
                            "vp_layer_order": vp_layer_order,
                        }
                    )
        else:
            for frame in list(viewport.get("frames", [])):
                frame_entries.append({"frame": frame, "vp_layer_key": "vp-layer-0", "vp_layer_name": "", "vp_layer_order": 0})

        frame_entries = sorted(frame_entries, key=lambda e: int((e.get("frame") or {}).get("frameId", 0)))
        frames = [e["frame"] for e in frame_entries]
        if not frame_entries:
            continue
        default_frame_id = int(frames[0].get("frameId", 0))
        for entry_frame in frame_entries:
            frame = entry_frame["frame"]
            frame_id = int(frame.get("frameId", 0))
            cats = frame.get("buttonCategories", {})
            frame_items: list[tuple[dict[str, Any], str, int]] = []
            for rank, (cat, label) in enumerate(
                (
                    ("screenLabels", "Screen Label"),
                    ("screenButtons", "Screen Button"),
                    ("hardButtons", "Hard Button"),
                    ("uiItems", "UI Item"),
                )
            ):
                for btn in cats.get(cat, []):
                    if cat != "uiItems" and _is_ui_only_button(btn):
                        continue
                    frame_items.append((btn, label, rank))
            frame_items.sort(key=lambda item: _button_stack_sort_key(item[0], item[2]))
            for btn, label, _rank in frame_items:
                    out.append(
                        {
                            "btn": btn,
                            "label": label,
                            "off_top": off_top,
                            "off_left": off_left,
                            "portrait_off_top": int(portrait_vp_c.get("top") or 0),
                            "portrait_off_left": int(portrait_vp_c.get("left") or 0),
                            "landscape_off_top": int(landscape_vp_c.get("top") or 0),
                            "landscape_off_left": int(landscape_vp_c.get("left") or 0),
                            "vp_portrait_visible": vp_portrait_visible,
                            "vp_landscape_visible": vp_landscape_visible,
                            "vp_index": vp_index,
                            "frame_id": frame_id,
                            "vp_layer_key": str(entry_frame.get("vp_layer_key") or ""),
                            "vp_layer_name": str(entry_frame.get("vp_layer_name") or ""),
                            "vp_layer_order": int(entry_frame.get("vp_layer_order") or 0),
                            "visible": frame_id == default_frame_id and bool(_orientation_ui(btn["buttonUI"], orientation).get("visible", True)),
                            "owner_layer_key": entry["layer_key"],
                            "owner_layer_order": entry["layer_order"],
                        }
                    )
    return out


def _page_all_buttons(page: dict[str, Any], orientation: str) -> list[dict[str, Any]]:
    buttons = [btn for btn, *_rest in _iter_page_buttons(page)]
    buttons.extend(vb["btn"] for vb in _iter_viewport_buttons(page, orientation))
    return buttons


def _page_target_map(
    project_data: dict[str, Any],
    project_stem: str,
    device_index: int,
    resolved_targets: dict[str, Any] | None = None,
) -> dict[int, str]:
    device = project_data["devices"][device_index]
    user_pages = device["userFacing"]["pages"]
    diag_pages = project_data["devices"][device_index].get("diagnostics", {}).get("pages", [])
    device_name = str(device["userFacing"].get("displayName", f"device-{device_index}"))
    target_href = device_filename(project_stem, device_name, device_index)
    out: dict[int, str] = {}
    if isinstance(resolved_targets, dict):
        rows = resolved_targets.get("devices", [])
        if isinstance(rows, list):
            diag_device_id = int((project_data["devices"][device_index].get("diagnostics", {}) or {}).get("deviceId") or 0)
            match = next((r for r in rows if isinstance(r, dict) and int(r.get("deviceId") or 0) == diag_device_id), None)
            if isinstance(match, dict):
                page_ids = match.get("pageIds", [])
                if isinstance(page_ids, list):
                    for idx, page_id in enumerate(page_ids):
                        if idx >= len(user_pages):
                            break
                        out[int(page_id)] = target_href
                    if out:
                        return out
    for index, diag_page in enumerate(diag_pages):
        if index >= len(user_pages):
            break
        page_id = diag_page.get("pageId")
        if page_id is None:
            continue
        out[int(page_id)] = target_href
    return out


def _page_target_indexes(
    project_data: dict[str, Any],
    device_index: int,
    resolved_targets: dict[str, Any] | None = None,
) -> dict[int, int]:
    diag_pages = project_data["devices"][device_index].get("diagnostics", {}).get("pages", [])
    out: dict[int, int] = {}
    if isinstance(resolved_targets, dict):
        rows = resolved_targets.get("devices", [])
        if isinstance(rows, list):
            diag_device_id = int((project_data["devices"][device_index].get("diagnostics", {}) or {}).get("deviceId") or 0)
            match = next((r for r in rows if isinstance(r, dict) and int(r.get("deviceId") or 0) == diag_device_id), None)
            if isinstance(match, dict):
                page_ids = match.get("pageIds", [])
                if isinstance(page_ids, list):
                    for index, page_id in enumerate(page_ids):
                        out[int(page_id)] = index
                    if out:
                        return out
    for index, diag_page in enumerate(diag_pages):
        page_id = diag_page.get("pageId")
        if page_id is not None:
            out[int(page_id)] = index
    return out


def _render_button_control(
    btn: dict[str, Any],
    label: str,
    left: int,
    top: int,
    variable_label: str,
    app_ui: dict[str, Any],
    page_targets: dict[int, str],
    page_target_indexes: dict[int, int] | None = None,
    extra_classes: str = "",
    extra_style: str = "",
    extra_attrs: str = "",
    orientation: str = "portrait",
    portrait_offset_left: int = 0,
    portrait_offset_top: int = 0,
    landscape_offset_left: int = 0,
    landscape_offset_top: int = 0,
) -> str:
    oriented_ui = _orientation_ui(btn["buttonUI"], orientation)
    c = _ui_coordinates(btn["buttonUI"], orientation)
    orientation_attrs = _orientation_data_attrs(
        btn["buttonUI"],
        portrait_offset_left=portrait_offset_left,
        portrait_offset_top=portrait_offset_top,
        landscape_offset_left=landscape_offset_left,
        landscape_offset_top=landscape_offset_top,
    )
    width = int(c.get("width") or 0)
    height = int(c.get("height") or 0)
    fs = int(btn["buttonUI"].get("fontSize") or app_ui.get("buttonPresentation", {}).get("fallbackFontSize", 10))
    identity = btn.get("buttonIdentity", {})
    targets = btn.get("testTargets", {})
    category_key = _category_key_from_label(label)
    meta = {
        "category": label,
        "categoryKey": category_key,
        "identity": _btn_text(identity),
        "buttonType": identity.get("buttonType") or "",
        "targets": _targets(btn, variable_label),
    }
    if isinstance(btn.get("apexScopeSource"), dict):
        meta["apexScopeSource"] = btn.get("apexScopeSource")
    meta_attr = json.dumps(meta).replace("'", "&apos;")
    visibility_attr = "1" if bool(oriented_ui.get("visible", True)) and "display:none" not in extra_style else "0"
    classes = f"btn-wrap {extra_classes}".strip()
    link_cfg = app_ui.get("appNavigation", {}).get("pageLinks", {})
    link_html = ""
    tag_name = _button_tag_name(btn)
    if link_cfg.get("enabled") and _page_link_enabled(targets):
        target_page_id = _page_link_target_id(btn)
        target_href = page_targets.get(target_page_id) if target_page_id is not None else None
        if target_href:
            nav_width = int(link_cfg.get("hoverActivationArea", {}).get("width") or 28)
            nav_pad = int(link_cfg.get("iconPaddingRight") or 8)
            icon_size = int(link_cfg.get("iconSize") or 16)
            icon = "<span class='material-symbols-outlined' aria-hidden='true'>link_2</span>"
            page_index_attr = ""
            if target_page_id is not None and page_target_indexes and target_page_id in page_target_indexes:
                page_index_attr = f" data-target-page-index='{page_target_indexes[target_page_id]}'"
            link_html = (
                f"<a class='page-link-hit' href='{target_href}' aria-label='Open linked page' "
                f"data-hit-width='{nav_width}' data-hit-padding='{nav_pad}'{page_index_attr}>"
                f"<span class='page-link-icon' data-icon-size='{icon_size}'>{icon}</span></a>"
            )
    standard_attrs = f"data-button-tag='{escape(tag_name, quote=True)}'"
    return (
        f"<div class='{classes}' style='{extra_style}' data-left='{left}' data-top='{top}' data-width='{width}' data-height='{height}' data-font-size='{fs}' data-visible='{visibility_attr}' data-button-category='{escape(category_key, quote=True)}' {orientation_attrs} {standard_attrs} {extra_attrs}>"
        f"<button class='test-btn' data-meta='{meta_attr}'>{escape(_btn_text(identity))}</button>"
        f"<div class='btn-pass-total' aria-hidden='true'></div>"
        f"{link_html}</div>"
    )


def _page_payload(
    project_data: dict[str, Any],
    app_ui: dict[str, Any],
    project_stem: str,
    device_index: int,
    page_index: int,
    orientation: str,
    resolved_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    device = project_data["devices"][device_index]
    diag = device.get("diagnostics", {}) if isinstance(device, dict) else {}
    diag_device_id = diag.get("deviceId") if isinstance(diag, dict) else None
    diag_pages = (diag.get("pages") if isinstance(diag, dict) else None) or []
    diag_page = diag_pages[page_index] if isinstance(diag_pages, list) and page_index < len(diag_pages) else {}
    diag_page_id = diag_page.get("pageId") if isinstance(diag_page, dict) else None
    diag_buttons = (diag_page.get("buttons") if isinstance(diag_page, dict) else None) or []
    diag_viewports = (diag_page.get("viewports") if isinstance(diag_page, dict) else None) or []
    if not isinstance(diag_buttons, list):
        diag_buttons = []
    if not isinstance(diag_viewports, list):
        diag_viewports = []

    uf = device["userFacing"]
    page = uf["pages"][page_index]
    variable_label = app_ui.get("testingPopup", {}).get("variableLabelTemplate", "Variable - {variableType}")
    page_targets = _page_target_map(project_data, project_stem, device_index, resolved_targets)
    page_target_indexes = _page_target_indexes(project_data, device_index, resolved_targets)
    layer_name_by_key = {
        str(layer.get("key") or ""): str(layer.get("name") or "")
        for layer in _page_layer_state(page)
        if isinstance(layer, dict)
    }
    diag_button_by_id: dict[int, dict[str, Any]] = {}
    for row in diag_buttons:
        if not isinstance(row, dict):
            continue
        bid = row.get("buttonId")
        if bid is None:
            continue
        diag_button_by_id[int(bid)] = row
    diag_vp_child_button_by_id: dict[int, dict[str, Any]] = {}
    for vp in diag_viewports:
        if not isinstance(vp, dict):
            continue
        frames = vp.get("frames", [])
        if not isinstance(frames, list):
            continue
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            buttons = frame.get("buttons", [])
            if not isinstance(buttons, list):
                continue
            for row in buttons:
                if not isinstance(row, dict):
                    continue
                bid = row.get("buttonId")
                if bid is None:
                    continue
                diag_vp_child_button_by_id[int(bid)] = row

    page_button_rows: list[str] = []
    for btn, label, off_top, off_left, layer_key, layer_order in _iter_page_buttons(page):
        oriented_ui = _orientation_ui(btn["buttonUI"], orientation)
        if not bool(oriented_ui.get("visible", True)):
            continue
        c = _ui_coordinates(btn["buttonUI"], orientation)
        diag_button_id = _diag_match_button_id(diag_buttons, btn)
        diag_attrs = ""
        if diag_device_id is not None:
            diag_attrs += f" data-diag-device-id='{int(diag_device_id)}'"
        if diag_page_id is not None:
            diag_attrs += f" data-diag-page-id='{int(diag_page_id)}'"
        if diag_button_id is not None:
            diag_attrs += f" data-diag-button-id='{int(diag_button_id)}'"
            resolved_context = diag_button_by_id.get(int(diag_button_id), {}).get("resolvedContext")
            if isinstance(resolved_context, dict):
                room_name = str(resolved_context.get("effectiveRoomName") or "").strip()
                source_name = str(resolved_context.get("effectiveSourceName") or "").strip()
                scope_names = f"{room_name} -> {source_name}" if room_name and source_name else room_name
                if room_name:
                    diag_attrs += f" data-effective-room-name='{escape(room_name, quote=True)}'"
                if source_name:
                    diag_attrs += f" data-effective-source-name='{escape(source_name, quote=True)}'"
                if scope_names:
                    diag_attrs += f" data-effective-scope-names='{escape(scope_names, quote=True)}'"
        page_button_rows.append(
            _render_button_control(
                btn,
                label,
                int(c.get("left") or 0) + off_left,
                int(c.get("top") or 0) + off_top,
                variable_label,
                app_ui,
                page_targets,
                page_target_indexes,
                extra_style=f"z-index:{100 + layer_order};",
                extra_attrs=(
                    f"data-owner-layer-key='{layer_key}' data-owner-layer-order='{layer_order}' "
                    f"data-owner-layer-name='{escape(str(layer_name_by_key.get(str(layer_key), '') or ''))}'{diag_attrs}"
                ),
                orientation=orientation,
            )
        )

    viewport_button_rows: list[str] = []
    for vb in _iter_viewport_buttons(page, orientation):
        btn = vb["btn"]
        c = _ui_coordinates(btn["buttonUI"], orientation)
        extra = f"z-index:{100 + int(vb['owner_layer_order'])};"
        if not vb["visible"]:
            extra = "display:none;" + extra
        vp_button_id, vp_child_button_id = _diag_match_viewport_button_ids(
            diag_viewports,
            vp_index=int(vb["vp_index"]),
            frame_id=int(vb["frame_id"]),
            user_btn=btn,
        )
        diag_attrs = ""
        if diag_device_id is not None:
            diag_attrs += f" data-diag-device-id='{int(diag_device_id)}'"
        if diag_page_id is not None:
            diag_attrs += f" data-diag-page-id='{int(diag_page_id)}'"
        if vp_button_id is not None:
            diag_attrs += f" data-diag-viewport-button-id='{int(vp_button_id)}'"
        if vp_child_button_id is not None:
            diag_attrs += f" data-diag-button-id='{int(vp_child_button_id)}'"
            resolved_context = diag_vp_child_button_by_id.get(int(vp_child_button_id), {}).get("resolvedContext")
            if isinstance(resolved_context, dict):
                room_name = str(resolved_context.get("effectiveRoomName") or "").strip()
                source_name = str(resolved_context.get("effectiveSourceName") or "").strip()
                scope_names = f"{room_name} -> {source_name}" if room_name and source_name else room_name
                if room_name:
                    diag_attrs += f" data-effective-room-name='{escape(room_name, quote=True)}'"
                if source_name:
                    diag_attrs += f" data-effective-source-name='{escape(source_name, quote=True)}'"
                if scope_names:
                    diag_attrs += f" data-effective-scope-names='{escape(scope_names, quote=True)}'"
        viewport_button_rows.append(
            _render_button_control(
                btn,
                vb["label"],
                int(c.get("left") or 0) + int(vb["off_left"]),
                int(c.get("top") or 0) + int(vb["off_top"]),
                variable_label,
                app_ui,
                page_targets,
                page_target_indexes,
                extra_classes="vp-btn",
                extra_style=extra,
                extra_attrs=(
                    f"data-vp='{vb['vp_index']}' data-frame='{vb['frame_id']}' "
                    f"data-vp-layer-key='{escape(str(vb.get('vp_layer_key') or ''))}' "
                    f"data-vp-layer-name='{escape(str(vb.get('vp_layer_name') or ''))}' "
                    f"data-vp-layer-order='{int(vb.get('vp_layer_order') or 0)}' "
                    f"data-vp-pv='{'1' if bool(vb.get('vp_portrait_visible', True)) else '0'}' "
                    f"data-vp-lv='{'1' if bool(vb.get('vp_landscape_visible', True)) else '0'}' "
                    f"data-owner-layer-key='{vb['owner_layer_key']}' data-owner-layer-order='{vb['owner_layer_order']}' "
                    f"data-owner-layer-name='{escape(str(layer_name_by_key.get(str(vb.get('owner_layer_key')), '') or ''))}'{diag_attrs}"
                ),
                orientation=orientation,
                portrait_offset_left=int(vb["portrait_off_left"]),
                portrait_offset_top=int(vb["portrait_off_top"]),
                landscape_offset_left=int(vb["landscape_off_left"]),
                landscape_offset_top=int(vb["landscape_off_top"]),
            )
        )

    page_viewports: list[dict[str, Any]] = []
    layers = _page_layers(page)
    if layers:
        for layer in layers:
            page_viewports.extend(layer.get("viewports", []))
    else:
        page_viewports = list(page.get("viewports", []))
    vp_frames: list[list[int]] = []
    for vp in page_viewports:
        if vp.get("layers"):
            frames = []
            for layer in vp.get("layers", []):
                frames.extend(layer.get("frames", []))
        else:
            frames = list(vp.get("frames", []))
        vp_frames.append(sorted({int(f.get("frameId", 0)) for f in frames}))
    viewport_boxes = "".join(
        [
            "<div class='vp-box' style='z-index:{z};' data-vp='{vp_index}' data-nav-mode='{nav_mode}' data-left='{left}' data-top='{top}' data-width='{width}' data-height='{height}' {orientation_attrs} data-owner-layer-key='{layer_key}' data-owner-layer-order='{layer_order}'></div>".format(
                z=9200 + int(c["layer_order"]),
                nav_mode=escape(str((c.get("viewport_ui") or {}).get("navigationMode") or "page")),
                orientation_attrs=_orientation_data_attrs(c["viewport_ui"]),
                **c,
            )
            for c in _iter_viewport_boxes(page, orientation)
        ]
    )
    return {
        "page_name": str(page.get("pageName", "")),
        "page_index": page_index,
        "layers": _page_layer_state(page),
        "vp_frames": vp_frames,
        "viewport_boxes": viewport_boxes,
        "page_button_rows": "".join(page_button_rows),
        "viewport_button_rows": "".join(viewport_button_rows),
    }



def _render_document(
    app_ui: dict[str, Any],
    header: str,
    w: int,
    h: int,
    body_markup: str,
    page_html_by_index_json: str,
    page_state_json: str,
    project_session_key: str,
    orientation_state_json: str,
    show_orientation_toggle: bool,
    home_href: str | None = None,
) -> str:
    link_cfg = app_ui.get("appNavigation", {}).get("pageLinks", {})
    link_hover_enabled = bool(link_cfg.get("enabled") and link_cfg.get("showLinkAffordanceOnHover"))
    layout_cfg = app_ui.get("layout", {})
    control_cfg = layout_cfg.get("appUIControls", {})
    rti_device_cfg = layout_cfg.get("rtiDeviceCanvas", {})
    layer_panel_cfg = app_ui.get("layerPanel", {})
    layer_panel_panel_cfg = layer_panel_cfg.get("panel", {})
    layer_panel_button_cfg = layer_panel_cfg.get("buttons", {})
    layer_button_active_cfg = layer_panel_button_cfg.get("active", {})
    layer_button_inactive_cfg = layer_panel_button_cfg.get("inactive", {})
    app_json = json.dumps(app_ui)
    control_json = json.dumps(control_cfg)
    rti_device_json = json.dumps(rti_device_cfg)
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{header}</title>
<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&icon_names=link_2\">
<style>
html,body{{margin:0;width:100%;height:100%;}}
body{{font-family:Segoe UI,Tahoma,sans-serif;background:#eef3f7;color:#183247;overflow:hidden;}}
.app-canvas{{position:relative;width:100vw;height:100vh;overflow:hidden;}}
.app-ui-controls{{position:absolute;box-sizing:border-box;z-index:20;}}
.top-controls{{left:0;right:0;top:0;display:flex;align-items:center;justify-content:center;}}
.bottom-controls{{left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:center;}}
.left-controls{{left:0;display:flex;align-items:center;justify-content:center;}}
.right-controls{{right:0;display:flex;align-items:center;justify-content:center;}}
.layer-controls{{right:0;display:flex;align-items:center;justify-content:center;z-index:22;}}
.orientation-controls{{left:0;display:flex;align-items:flex-start;justify-content:center;z-index:23;}}
.top-controls{{padding:0 16px;box-sizing:border-box;gap:12px;justify-content:space-between;}}
.header{{font-weight:700;font-size:20px;text-align:center;display:flex;align-items:center;justify-content:center;flex:1;height:100%;min-width:0;}}
.project-home-link{{display:inline-flex;align-items:center;justify-content:center;min-width:132px;height:40px;padding:0 16px;border-radius:14px;border:1px solid #a9bccd;background:#f7fbff;color:#14324b;text-decoration:none;font-size:14px;line-height:1;box-sizing:border-box;white-space:nowrap;}}
.project-home-link:hover{{filter:brightness(0.98);}}
.rti-canvas{{position:absolute;box-sizing:border-box;z-index:1;overflow:auto;scrollbar-width:none;scrollbar-gutter:stable overlay;}}
.rti-canvas.scroll-hover:hover{{scrollbar-width:thin;}}
.rti-canvas::-webkit-scrollbar{{width:10px;height:10px;}}
.rti-canvas:not(.scroll-hover)::-webkit-scrollbar-thumb{{background:transparent;}}
.rti-canvas:not(.scroll-hover)::-webkit-scrollbar-track{{background:transparent;}}
.rti-canvas.scroll-hover:hover::-webkit-scrollbar{{width:10px;height:10px;}}
.rti-canvas.scroll-hover:hover::-webkit-scrollbar-thumb{{background:#a9bccd;border-radius:999px;}}
.rti-content{{position:relative;min-width:100%;min-height:100%;}}
.rti-device-canvas{{position:absolute;border:1px solid #c6d2dd;border-radius:10px;background:#f8fbfe;overflow:hidden;box-sizing:border-box;z-index:2;}}
.device-page{{position:absolute;inset:0;display:none;}}
.device-page.active{{display:block;}}
 .vp-box{{position:absolute;border:2px dashed #88a6bd;border-radius:0;background:rgba(255,255,255,0.50);pointer-events:auto;cursor:pointer;z-index:9101;box-sizing:border-box;}}
 .vp-overlay{{position:absolute;inset:0;background:rgba(255,255,255,0.05);z-index:9000;pointer-events:none;display:none;}}
 .viewport-mode .vp-overlay{{display:block;}}
 .viewport-mode .vp-focus{{z-index:9500 !important;pointer-events:auto;}}
 .viewport-mode .vp-box:not(.vp-focus){{pointer-events:none;}}
.btn-wrap{{position:absolute;z-index:2;}}
 .device-page .btn-wrap.vp-btn{{pointer-events:none;}}
 .vp-popup-stage .btn-wrap.vp-btn{{pointer-events:auto;}}
 .viewport-mode #rtiCanvas{{pointer-events:none;overflow:hidden;}}
 .vp-popup{{position:fixed;left:0;top:0;width:0;height:0;display:none;align-items:center;justify-content:center;background:rgba(255,255,255,0.05);z-index:9800;}}
 .viewport-mode .vp-popup{{display:flex;}}
 .vp-popup[hidden]{{display:none;}}
 .vp-popup-panel{{position:relative;width:min(920px,calc(100% - 56px));height:min(720px,calc(100% - 56px));background:rgba(247,251,255,.96);border:1px solid #b9cad8;border-radius:18px;box-shadow:0 18px 50px rgba(20,50,75,.20);overflow:hidden;box-sizing:border-box;isolation:isolate;}}
 .vp-popup-scroller{{position:absolute;inset:0;overflow:hidden;scrollbar-width:thin;scrollbar-color:transparent transparent;scrollbar-gutter:stable overlay;z-index:1;}}
 .vp-popup-scroller.scroll-hover:hover{{scrollbar-color:#a9bccd transparent;}}
 .vp-popup-scroller::-webkit-scrollbar{{width:10px;height:10px;}}
 .vp-popup-scroller::-webkit-scrollbar-thumb{{background:transparent;}}
 .vp-popup-scroller::-webkit-scrollbar-track{{background:transparent;}}
 .vp-popup-scroller.scroll-hover:hover::-webkit-scrollbar-thumb{{background:#a9bccd;border-radius:999px;}}
 .vp-popup-stage{{position:relative;transform-origin:0 0;z-index:1;}}
 .vp-popup-scrollpad{{min-width:100%;min-height:100%;display:flex;align-items:center;justify-content:center;box-sizing:border-box;}}
 .vp-popup-close{{position:absolute;top:12px;right:18px;z-index:220;width:44px;height:44px;border-radius:14px;border:2px solid #f0a126;background:#f7fbff;color:#29445a;font-size:26px;line-height:1;cursor:pointer;display:flex;align-items:center;justify-content:center;box-sizing:border-box;}}
 .vp-popup-nav{{position:absolute;z-index:210;width:44px;height:44px;border-radius:14px;border:2px solid #f0a126;background:rgba(247,251,255,.94);color:#29445a;font-size:22px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-sizing:border-box;}}
 .vp-popup-prev{{left:14px;top:50%;transform:translateY(-50%);}}
 .vp-popup-next{{right:14px;top:50%;transform:translateY(-50%);}}
 .vp-popup-up{{left:50%;top:14px;transform:translateX(-50%);}}
 .vp-popup-down{{left:50%;bottom:14px;transform:translateX(-50%);}}
 .vp-popup-indicator{{position:absolute;left:0;top:0;transform:translateY(-50%);z-index:205;pointer-events:none;width:fit-content;}}
 .vp-popup-indicator.is-vertical{{flex-direction:column;}}
 .vp-popup-viewport{{position:relative;left:auto;top:auto;border:2px dashed #88a6bd;border-radius:0;background:transparent;box-shadow:none;box-sizing:border-box;overflow:hidden;}}
 .vp-popup-vcontent{{position:relative;left:0;top:0;}}
.btn-wrap{{--btn-fill-color:#2c6fb7;--btn-state-trim-color:transparent;--btn-state-trim-width:0px;}}
.test-btn{{position:absolute;inset:0;box-sizing:border-box;border:0;border-radius:10px;background:var(--btn-fill-color);box-shadow:inset 0 0 0 1px #154665,inset 0 0 0 var(--btn-state-trim-width) var(--btn-state-trim-color);color:#fff;line-height:1.1;white-space:pre-line;cursor:pointer;overflow:hidden;padding:0;}}
.btn-pass-total{{position:absolute;left:6px;top:50%;transform:translateY(-50%);display:none;visibility:hidden;padding:1px 4px;border-radius:6px;background:rgba(0,0,0,.22);color:#fff;font-size:11px;line-height:1.1;font-weight:700;white-space:nowrap;pointer-events:none;}}
.page-link-hit{{position:absolute;top:0;right:0;height:100%;display:flex;align-items:center;justify-content:flex-end;text-decoration:none;color:#fff;opacity:1;pointer-events:auto;transition:opacity .15s ease;}}
.page-link-icon{{display:inline-flex;align-items:center;justify-content:center;background:transparent;border-radius:0;}}
.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;font-size:115%;line-height:1;}}
.vp-nav{{width:44px;height:44px;border-radius:14px;border:2px solid #f0a126;background:transparent;color:#29445a;font-size:22px;cursor:pointer;position:relative;z-index:21;}}
.orientation-toggle{{display:flex;flex-direction:column;gap:8px;align-items:stretch;justify-content:center;max-width:120px;}}
.orientation-btn{{min-width:96px;height:40px;border-radius:12px;border:2px solid #f0a126;background:transparent;color:#29445a;font-size:12px;font-weight:700;cursor:pointer;display:flex;align-items:center;justify-content:center;box-sizing:border-box;padding:0 10px;}}
.orientation-btn.active{{background:#29445a;color:#fff;}}
 .zoom-controls{{position:absolute;display:flex;gap:8px;z-index:30;}}
.zoom-btn{{width:44px;height:44px;border-radius:14px;border:2px solid #f0a126;background:transparent;color:#29445a;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-sizing:border-box;}}
.zoom-btn.zoom-reset{{min-width:72px;width:auto;padding:0 12px;font-size:14px;}}
.layer-panel{{width:min(100%,{int(layer_panel_panel_cfg.get("maxWidth", 240))}px);max-height:100%;display:flex;flex-direction:column;gap:{int(layer_panel_panel_cfg.get("gap", 12))}px;padding:{int(layer_panel_panel_cfg.get("padding", 14))}px;border:1px solid #b9cad8;border-radius:{int(layer_panel_panel_cfg.get("borderRadius", 18))}px;background:rgba(247,251,255,.94);box-shadow:0 10px 30px rgba(20,50,75,.10);box-sizing:border-box;}}
.layer-panel[hidden]{{display:none;}}
.layer-panel-title{{font-size:15px;font-weight:700;line-height:1;color:#14324b;text-align:center;}}
.layer-list{{display:flex;flex-direction:column;gap:10px;overflow:auto;padding-right:2px;}}
.layer-toggle{{width:100%;min-height:{int(layer_panel_button_cfg.get("minHeight", 44))}px;border-radius:{int(layer_panel_button_cfg.get("borderRadius", 12))}px;border:0;box-shadow:inset 0 0 0 1px {str(layer_button_active_cfg.get("border", "#154665"))};background:{str(layer_button_active_cfg.get("background", "#1e5f86"))};color:{str(layer_button_active_cfg.get("text", "#ffffff"))};font-size:{int(layer_panel_button_cfg.get("fontSize", 13))}px;line-height:1.15;padding:10px 12px;cursor:pointer;text-align:center;}}
.layer-toggle.is-inactive{{background:{str(layer_button_inactive_cfg.get("background", "#f7fbff"))};color:{str(layer_button_inactive_cfg.get("text", "#14324b"))};box-shadow:inset 0 0 0 1px {str(layer_button_inactive_cfg.get("border", "#a9bccd"))};}}
.layer-toggle:hover{{filter:brightness(0.98);}}
.vp-indicator{{display:flex;gap:8px;min-height:14px;align-items:center;justify-content:center;}}
.dot{{width:10px;height:10px;border-radius:50%;border:1px solid #9fb4c6;background:#e2ebf2;}}
.dot.active{{background:#2d5f81;border-color:#2d5f81;}}
.ov{{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:flex-start;justify-content:center;padding:8px 12px;z-index:10000;}}
.ov.open{{display:flex;}}
.pop{{width:min(560px,calc(100vw - 24px));max-width:100%;max-height:calc(100vh - 16px);display:flex;flex-direction:column;box-sizing:border-box;background:#fff;border:1px solid #cbd7e2;border-radius:18px;padding:20px 24px;margin-top:0;}}
.pop-head{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;}}
.pop h3{{margin:0;font-size:16px;line-height:1.1;font-weight:700;}}
#passAll{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;}}
#passAll:disabled{{opacity:.55;cursor:not-allowed;}}
.rows-scroll{{overflow:auto;min-height:0;padding-right:2px;scrollbar-width:thin;scrollbar-color:transparent transparent;scrollbar-gutter:stable overlay;}}
.rows-scroll.scroll-hover:hover{{scrollbar-color:#a9bccd transparent;}}
.rows-scroll::-webkit-scrollbar{{width:10px;height:10px;}}
.rows-scroll::-webkit-scrollbar-thumb{{background:transparent;}}
.rows-scroll::-webkit-scrollbar-track{{background:transparent;}}
.rows-scroll.scroll-hover:hover::-webkit-scrollbar-thumb{{background:#a9bccd;border-radius:999px;}}
.row{{box-sizing:border-box;width:100%;border:1px solid #d4dee8;border-radius:14px;padding:12px 14px;margin-bottom:10px;overflow:hidden;}}
.row:last-child{{margin-bottom:0;}}
.row-head{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px;}}
.n{{font-weight:600;margin:0;font-size:14px;line-height:1.1;}}
 .row-meta{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:8px;}}
 .actions{{display:flex;gap:10px;margin:0;}}
 .actions button{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;}}
 .actions button:disabled{{opacity:.55;cursor:not-allowed;}}
 .actions button.is-pass-active{{color:#1f5d2d;background:#eaf7ef;border-color:#39b54a;font-weight:700;}}
 .actions button.is-fail-active{{color:#7f1d1d;background:#fdeeee;border-color:#ef4444;font-weight:700;}}
 .row-last-test{{font-size:13px;line-height:1.2;color:#274258;}}
 textarea{{display:block;box-sizing:border-box;width:100%;max-width:100%;border:1px solid #ccd8e2;border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.2;resize:vertical;}}
 .post-status{{margin:10px 0 10px;font-size:13px;line-height:1.25;border-radius:12px;padding:10px 12px;border:1px solid #ccd8e2;background:#f8fbfe;color:#274258;}}
 .post-status.is-saving{{background:#fff7e8;border-color:#f0a126;color:#6f4b12;}}
 .post-status.is-success{{background:#eaf7ef;border-color:#3a9c5d;color:#1e6b3c;}}
 .post-status.is-error{{background:#fdeeee;border-color:#d05555;color:#8f1f1f;}}
 #close{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;display:block;margin-top:12px;margin-left:auto;margin-right:2px;}}
 #close:disabled{{opacity:.55;cursor:not-allowed;}}
</style></head>
<body><div class='app-canvas' id='appCanvas'>
<div class='app-ui-controls top-controls' id='topControls'>{f"<a class='project-home-link' href='{home_href}'>Project Home</a>" if home_href else "<div></div>"}<div class='header'>{header}</div><div></div></div>
{f"<div class='app-ui-controls orientation-controls' id='orientationControls'><div class='orientation-toggle' id='orientationToggle'><button class='orientation-btn' type='button' data-orientation='portrait'>Portrait</button><button class='orientation-btn' type='button' data-orientation='landscape'>Landscape</button></div></div>" if show_orientation_toggle else ""}
<div class='app-ui-controls layer-controls' id='layerControls'><div class='layer-panel' id='layerPanel' hidden><div class='layer-panel-title'>{escape(str(layer_panel_cfg.get("title", "Layers")))}</div><div class='layer-list' id='layerList'></div></div></div>
<div class='app-ui-controls bottom-controls' id='bottomControls'></div>
<div class='zoom-controls' id='zoomControls'><button class='zoom-btn zoom-dec' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("decrease", "-")}</button><button class='zoom-btn zoom-reset' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("reset", "100%")}</button><button class='zoom-btn zoom-inc' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("increase", "+")}</button></div>
 <div class='rti-canvas' id='rtiCanvas'><div class='vp-overlay' id='vpOverlay' hidden></div><div class='rti-content' id='rtiContent'><div class='rti-device-canvas' id='rtiDeviceCanvas'>{body_markup}</div></div></div></div>
 <div class='vp-popup' id='vpPopup' hidden><div class='vp-popup-panel' id='vpPopupPanel' role='dialog' aria-modal='true' aria-label='Viewport viewer'><button class='vp-popup-close' id='vpPopupClose' type='button' aria-label='Close viewport viewer'>&times;</button><button class='vp-popup-nav vp-popup-prev' id='vpPopupPrev' type='button' aria-label='Previous frame'>&lsaquo;</button><button class='vp-popup-nav vp-popup-next' id='vpPopupNext' type='button' aria-label='Next frame'>&rsaquo;</button><button class='vp-popup-nav vp-popup-up' id='vpPopupUp' type='button' aria-label='Scroll up'>&uarr;</button><button class='vp-popup-nav vp-popup-down' id='vpPopupDown' type='button' aria-label='Scroll down'>&darr;</button><div class='vp-popup-indicator vp-indicator' id='vpPopupIndicator'></div><div class='vp-popup-scroller' id='vpPopupScroller'><div class='vp-popup-scrollpad' id='vpPopupScrollpad'><div class='vp-popup-stage' id='vpPopupStage'></div></div></div></div></div>
 <div class='ov' id='ov'><div class='pop'><div class='pop-head'><h3 id='pt'></h3><button id='passAll' type='button'>Pass All</button></div><div id='rows' class='rows-scroll scroll-hover'></div><div class='post-status' id='postStatus' role='status' aria-live='polite' hidden></div><button id='close'>Close</button></div></div>
<script>
const APP_UI={app_json};
const APP_UI_CONTROLS={control_json};
const RTI_DEVICE_LAYOUT={rti_device_json};
const VIEWPORT_NAV={json.dumps(app_ui.get("viewportNavigation", {}))};
const ZOOM_CONTROLS={json.dumps(app_ui.get("zoomControls", {}))};
const LAYER_PANEL={json.dumps(layer_panel_cfg)};
const ZOOM_DEFAULT={int(app_ui.get("zoomControls", {}).get("zoom", {}).get("defaultPercent", 100))};
const ZOOM_MAX={max(300, int(app_ui.get("zoomControls", {}).get("zoom", {}).get("maxPercent", 300)))};
const ZOOM_STEP={int(app_ui.get("zoomControls", {}).get("zoom", {}).get("stepPercent", 10))};
const SOURCE_DEVICE_SIZE={{width:{w},height:{h}}};
const PROJECT_SESSION_KEY={json.dumps(project_session_key)};
const PAGE_HTML_BY_INDEX={page_html_by_index_json};
const PAGE_STATE={page_state_json};
const ORIENTATION_STATE={orientation_state_json};
const VP_FRAMES=(PAGE_STATE[0]?.vpFrames||[]);
let currentZoomPercent=ZOOM_DEFAULT;
let currentTotalScale=1;
let currentDeviceLeft=0;
let currentDeviceTop=0;
 let activePageIndex=0;
 let currentViewportIndexes=VP_FRAMES.map(()=>0);
 let currentOrientation=ORIENTATION_STATE.current;
 const viewportMode={{active:false,vpIndex:0,preZoom:null,popupZoomPercent:ZOOM_DEFAULT,popupFitScale:1,popupBaseFitScale:null,popupBaseKey:'',popupNavMode:'page',popupScrollY:0}};
 const ov=document.getElementById('ov'),pt=document.getElementById('pt'),rows=document.getElementById('rows'),postStatus=document.getElementById('postStatus'),passAllBtn=document.getElementById('passAll');
 let isPosting=false;
 let techWs=null;
 let techWsToken=null;
 let techWsReconnectTimer=null;
 let techWsReconnectDelayMs=500;
 let pendingTargetKey=null;
 let techLastAppliedSeq=0;
 let passAllQueue=[];
 let passAllContext=null;
 const rowStatusByTargetKey=new Map();
 const statusByTargetKey=new Map();
 const CATEGORY_FILL={{screenLabels:"#58585a",screenButtons:"#2c6fb7",hardButtons:"#2c6fb7",uiItems:"#a7a9ac",emptyTag:"#ef4444"}};
 const STATE_TRIM={{pass:"#39b54a",partial:"#fcb040",fail:"#ef4444",untested:"transparent"}};
 function _buttonCategoryKeyFromMeta(meta, wrap) {{
  const m=(meta&&typeof meta==="object")?meta:{{}};
  const key=String(m.categoryKey||wrap?.dataset?.buttonCategory||"").trim();
  if (key && CATEGORY_FILL[key]) return key;
  const label=String(m.category||"").trim().toLowerCase();
  if (label==="screen label") return "screenLabels";
  if (label==="screen button") return "screenButtons";
  if (label==="hard button") return "hardButtons";
  if (label==="ui item") return "uiItems";
  if (label==="empty tag") return "emptyTag";
  return "screenButtons";
 }}
 function _buttonTargetPrefix(wrap) {{
  if (!wrap || !wrap.dataset) return "";
  const deviceId=wrap.dataset.diagDeviceId;
  const pageIndexRaw = (wrap.dataset.pageIndex != null) ? wrap.dataset.pageIndex : (wrap.closest ? (wrap.closest(".device-page") || {{}}).dataset?.pageIndex : null);
  const pageIndex=pageIndexRaw == null ? null : Number(pageIndexRaw);
  const pageState=(pageIndex != null && Array.isArray(PAGE_STATE)) ? PAGE_STATE[pageIndex] : null;
  const pageId=pageState && pageState.pageId != null ? pageState.pageId : null;
  const vpButtonId=wrap.dataset.diagViewportButtonId;
  const buttonId=wrap.dataset.diagButtonId;
  if (vpButtonId && deviceId != null && pageId != null && buttonId != null) return `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{buttonId}}`;
  if (vpButtonId && deviceId != null && pageId != null) return `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}`;
  if (deviceId != null && pageId != null && buttonId != null) return `btn:${{deviceId}}:${{pageId}}:${{buttonId}}`;
  return "";
 }}
 function _buttonTargets(meta) {{
  const m=(meta&&typeof meta==="object")?meta:{{}};
  const targets=Array.isArray(m.targets)?m.targets:[];
  return targets.map((t)=>String(t||"").trim()).filter(Boolean);
 }}
 function _stateFromCounts(categoryKey, passCount, totalCount, testedCount) {{
  if (categoryKey==="emptyTag") return "fail";
  if (!Number(totalCount)||Number(totalCount)<=0) return "untested";
  if (!Number(testedCount)||Number(testedCount)<=0) return "untested";
  if (Number(passCount)>=Number(totalCount)) return "pass";
  if (Number(passCount)<=0) return "fail";
  return "partial";
 }}
 function refreshButtonVisualStates() {{
  document.querySelectorAll(".device-page .btn-wrap, .vp-popup-vcontent .btn-wrap.vp-btn").forEach((wrap)=>{{
   const btn=wrap.querySelector(".test-btn");
   if (!btn) return;
   let meta={{}};
   try {{ meta=JSON.parse(btn.dataset.meta||"{{}}"); }} catch (_e) {{ meta={{}}; }}
   const categoryKey=_buttonCategoryKeyFromMeta(meta, wrap);
   wrap.style.setProperty("--btn-fill-color", CATEGORY_FILL[categoryKey] || CATEGORY_FILL.screenButtons);
   const targets=_buttonTargets(meta);
   let passCount=0;
   let testedCount=0;
   for (const label of targets) {{
    const target = buildTargetPayload(btn, meta, label);
    const key = String(target?.targetKey || "").trim();
    if (!key) continue;
    const rec=statusByTargetKey.get(key);
    if (!rec) continue;
    const outcome=String(rec.outcome||"").toUpperCase();
    if (outcome!=="PASS" && outcome!=="FAIL") continue;
    testedCount += 1;
    if (outcome==="PASS") passCount += 1;
   }}
   const stateKey=_stateFromCounts(categoryKey, passCount, targets.length, testedCount);
   const trimColor=STATE_TRIM[stateKey] || "transparent";
   const trimWidth=(stateKey==="untested") ? "0px" : "4px";
   wrap.style.setProperty("--btn-state-trim-color", trimColor);
   wrap.style.setProperty("--btn-state-trim-width", trimWidth);
   const countEl=wrap.querySelector(".btn-pass-total");
   if (countEl) {{
    const countText = targets.length > 0 ? `${{passCount}}/${{targets.length}}` : "";
    countEl.textContent = countText;
    if (!countText) {{
     countEl.style.display = "none";
     countEl.style.visibility = "hidden";
    }} else {{
     countEl.style.display = "block";
     countEl.style.visibility = "hidden";
     const wrapRect=wrap.getBoundingClientRect();
     const countRect=countEl.getBoundingClientRect();
     const fits = countRect.width <= wrapRect.width && countRect.height <= wrapRect.height;
     countEl.style.visibility = fits ? "visible" : "hidden";
     if (!fits) countEl.style.display = "none";
    }}
   }}
  }});
 }}
 const _perfNow=()=>((typeof performance!=="undefined"&&performance.now)?performance.now():Date.now());
 const techPerf={{layoutCalls:0,layoutTotalMs:0,wsCalls:0,wsTotalMs:0,lastConsoleAt:0}};
 function _emitTechPerf(reason, lastMs) {{
  const now=_perfNow();
  if (now-techPerf.lastConsoleAt<5000 && reason!=="boot") return;
  techPerf.lastConsoleAt=now;
  const layoutAvgMs=techPerf.layoutCalls ? Number((techPerf.layoutTotalMs/techPerf.layoutCalls).toFixed(2)) : 0;
  const wsAvgMs=techPerf.wsCalls ? Number((techPerf.wsTotalMs/techPerf.wsCalls).toFixed(2)) : 0;
  try {{
   if (typeof console!=="undefined" && console.log) {{
    console.log("[tech-perf]", {{
     reason,
     lastMs:Number((Number(lastMs)||0).toFixed(2)),
     layoutCalls:techPerf.layoutCalls,
     layoutTotalMs:Number(techPerf.layoutTotalMs.toFixed(2)),
     layoutAvgMs,
     wsCalls:techPerf.wsCalls,
     wsTotalMs:Number(techPerf.wsTotalMs.toFixed(2)),
     wsAvgMs
    }});
   }}
  }} catch (_e) {{}}
 }}
 function _recordLayoutPerf(ms) {{
  const n=Number(ms)||0;
  techPerf.layoutCalls+=1;
  techPerf.layoutTotalMs+=n;
  if (n>=50 || techPerf.layoutCalls%20===0) _emitTechPerf("layout", n);
 }}
 function _recordWsPerf(ms, kind) {{
  const n=Number(ms)||0;
  techPerf.wsCalls+=1;
  techPerf.wsTotalMs+=n;
  if (n>=30 || techPerf.wsCalls%25===0) _emitTechPerf(`ws:${{String(kind||"unknown")}}`, n);
 }}
 function _logTechWs(action, data) {{
  try {{
   if (typeof console !== "undefined" && console.log) {{
    const msg = data == null ? "" : data;
    console.log("[tech-ws]", action, msg);
   }}
  }} catch (_e) {{
   _logTechWs("recv:parse-failed");
  }}
 }}
 function techTokenFromLocation() {{
  const parts=String(window.location.pathname||'').split('/').filter(Boolean);
  const i=parts.indexOf('testing');
  return (i>=0 && parts[i+1]) ? parts[i+1] : null;
 }}
 function techWsUrl(path) {{
  const proto = window.location && window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location && window.location.host ? window.location.host : "localhost";
  return `${{proto}}://${{host}}${{path}}`;
 }}
 function _scheduleTechWsReconnect() {{
  if (techWsReconnectTimer) return;
  techWsReconnectTimer = setTimeout(() => {{
   techWsReconnectTimer = null;
   _connectTechWs();
  }}, Math.min(5000, Math.max(250, techWsReconnectDelayMs)));
  techWsReconnectDelayMs = Math.min(5000, techWsReconnectDelayMs * 2);
 }}
 function _sendTechSyncRequest() {{
  if (!techWs || techWs.readyState !== 1) return;
  try {{
   techWs.send(JSON.stringify({{ type:"sync.request", lastAppliedSeq:Number(techLastAppliedSeq||0) }}));
   _logTechWs("sync.request", Number(techLastAppliedSeq||0));
  }} catch (_e) {{}}
 }}
 function _applyTechPayload(payload) {{
   const _wsT0=_perfNow();
   const t = String(payload?.type || "").trim();
   try {{
    _logTechWs("recv", t || "(unknown)");
    if (t === "error") {{
     const code = payload?.code;
     const message = payload?.message;
     const msg = String(code ? `${{code}}${{message ? ": " + message : ""}}` : (message || "Error"));
     setPosting(false);
     setPostStatus(`Error: ${{msg}}`, "error");
     drainPassAllQueue();
     return;
    }}
    if (t === "replay.batch") {{
     const events = Array.isArray(payload?.events) ? payload.events : [];
     for (const ev of events) _applyTechPayload(ev);
     return;
    }}
    const seq = Number(payload?.seq || 0);
    const isSnapshot = t === "testing_snapshot";
    if (seq > 0) {{
     if (seq <= techLastAppliedSeq) return;
     if (!isSnapshot && seq > techLastAppliedSeq + 1) {{
      _sendTechSyncRequest();
      return;
     }}
     techLastAppliedSeq = seq;
    }}
    if (t === "testing_snapshot") {{
     const results = Array.isArray(payload?.results) ? payload.results : [];
     let applied = 0;
     for (const rec of results) {{
      const targetKey = String(rec?.targetKey || "");
      if (!targetKey) continue;
      const outcome = String(rec?.outcome || "").toUpperCase();
      const at = String(rec?.recordedAtUtc || rec?.lastTestedAtUtc || rec?.tsUtc || "");
      statusByTargetKey.set(targetKey, {{ outcome, recordedAtUtc: at }});
      const rowUi = rowStatusByTargetKey.get(targetKey);
      if (rowUi) {{
       setRowStatus(rowUi, outcome, at);
       applied += 1;
      }}
     }}
     _logTechWs("snapshot:applied", {{ total: results.length, applied }});
     refreshButtonVisualStates();
     return;
    }}
    if (t !== "test_result.recorded" && t !== "test_result") return;
    const targetKey = String(payload?.targetKey || payload?.target?.targetKey || "");
    if (!targetKey) return;
    const outcome = String(payload?.outcome || payload?.currentOutcome || "").toUpperCase();
    const at = String(payload?.recordedAtUtc || payload?.lastTestedAtUtc || payload?.tsUtc || "");
    statusByTargetKey.set(targetKey, {{ outcome, recordedAtUtc: at }});
    const rowUi = rowStatusByTargetKey.get(targetKey);
    if (!rowUi) {{
     _logTechWs("row-miss", targetKey);
    }} else {{
      setRowStatus(rowUi, outcome, at);
    }}
    refreshButtonVisualStates();
    if (pendingTargetKey && pendingTargetKey === targetKey) {{
     _logTechWs("ack-match", targetKey);
     pendingTargetKey = null;
     setPosting(false);
      setPostStatus("", "");
     drainPassAllQueue();
    }} else if (pendingTargetKey) {{
     _logTechWs("ack-miss", {{ pending: pendingTargetKey, received: targetKey }});
    }}
   }} finally {{
    _recordWsPerf(_perfNow()-_wsT0, t || "(unknown)");
   }}
 }}
 function _handleTechWsMessage(evt) {{
  try {{
   const payload = JSON.parse(String(evt.data || "{{}}"));
   _applyTechPayload(payload);
  }} catch (_e) {{
   _logTechWs("recv:parse-failed");
  }}
 }}
 function _connectTechWs() {{
  const techToken = techTokenFromLocation();
  if (!techToken) return;
  if (techWs && techWsToken === techToken) return;
  if (techWs) {{
   try {{ techWs.close(); }} catch (_e) {{}}
  }}
  techWsToken = techToken;
  techLastAppliedSeq = 0;
  _logTechWs("connect", techToken);
  const ws = new WebSocket(techWsUrl(`/api/v1/testing/${{encodeURIComponent(techToken)}}/ws`));
  techWs = ws;
  ws.onopen = () => {{ techWsReconnectDelayMs = 500; _logTechWs("open"); _sendTechSyncRequest(); }};
  ws.onclose = () => {{
   techWs = null;
   _logTechWs("close");
   _scheduleTechWsReconnect();
  }};
  ws.onerror = () => {{
   _logTechWs("error");
   try {{ if (techWs) techWs.close(); }} catch (_e) {{}}
  }};
  ws.onmessage = _handleTechWsMessage;
 }}
  function _sendTechWs(payload) {{
   if (!techWs || techWs.readyState !== 1) {{
    _connectTechWs();
   }}
   if (!techWs || techWs.readyState !== 1) {{
    _logTechWs("send-abort:not-open", techWs ? techWs.readyState : "null");
    setPosting(false);
    if (pendingTargetKey) setRowInlineError(pendingTargetKey, "websocket not connected");
    setPostStatus("", "");
    return;
   }}
   _logTechWs("send", payload?.type || "");
  techWs.send(JSON.stringify(payload));
 }}
 function formatLastTestUtc(ts) {{
  const raw = String(ts || "").trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  const pad2 = (n) => String(n).padStart(2, "0");
  const yyyy = d.getUTCFullYear();
  const mm = pad2(d.getUTCMonth() + 1);
  const dd = pad2(d.getUTCDate());
  const hh = pad2(d.getUTCHours());
  const mi = pad2(d.getUTCMinutes());
  const ss = pad2(d.getUTCSeconds());
  return `${{yyyy}}-${{mm}}-${{dd}} ${{hh}}:${{mi}}:${{ss}}Z`;
 }}
 function setRowStatus(rowUi, outcome, recordedAtUtc) {{
  if (!rowUi) return;
  const o = String(outcome || "").trim().toUpperCase();
  const at = formatLastTestUtc(recordedAtUtc);
  if (rowUi.passBtn) rowUi.passBtn.classList.toggle("is-pass-active", o === "PASS");
  if (rowUi.failBtn) rowUi.failBtn.classList.toggle("is-fail-active", o === "FAIL");
  if (rowUi.lastTestEl) rowUi.lastTestEl.textContent = at ? `Last Test: ${{at}}` : "";
 }}
 function applyCachedStatus(rowUi, targetKey) {{
  if (!rowUi) return;
  const key = String(targetKey || "").trim();
  if (!key) return;
  const rec = statusByTargetKey.get(key);
  if (!rec) return;
  const outcome = String(rec.outcome || "").toUpperCase();
  const at = String(rec.recordedAtUtc || "");
  setRowStatus(rowUi, outcome, at);
 }}
function buildTargetPayload(ctxBtn, meta, targetLabel) {{
  const m = (meta && typeof meta === "object") ? meta : {{}};
  const label = String(targetLabel || "").trim();
  const kind = String(m.kind || "").trim().toUpperCase();
  const refs = (m.refs && typeof m.refs === "object") ? {{...m.refs}} : {{}};
  if (kind === "EVENT") {{
   const eventId = refs.eventId;
   if (eventId == null) return null;
   const targetKey = `event:${{eventId}}:${{label || "Trigger"}}`;
   return {{
    targetKey,
    kind: "EVENT",
    targetName: label || String(m.identity || "").trim(),
    refs
   }};
  }}
  const btn = ctxBtn || null;
  const wrap = btn && btn.closest ? btn.closest(".btn-wrap") : null;
  const deviceId = wrap && wrap.dataset ? wrap.dataset.diagDeviceId : null;
  const pageIndexRaw = (wrap && wrap.dataset && wrap.dataset.pageIndex != null) ? wrap.dataset.pageIndex : null;
  const pageIndexRawResolved = pageIndexRaw != null ? pageIndexRaw : (wrap && wrap.closest ? (wrap.closest(".device-page") || {{}}).dataset?.pageIndex : null);
  const pageIndex = pageIndexRawResolved == null ? null : Number(pageIndexRawResolved);
  const pageState = (pageIndex != null && Array.isArray(PAGE_STATE)) ? PAGE_STATE[pageIndex] : null;
  const pageId = pageState && pageState.pageId != null ? pageState.pageId : null;
  const vpButtonId = wrap && wrap.dataset ? wrap.dataset.diagViewportButtonId : null;
  const buttonId = wrap && wrap.dataset ? wrap.dataset.diagButtonId : null;
  const buttonTag = wrap && wrap.dataset ? wrap.dataset.buttonTag : "";
  const categoryName = String(m.category || "").trim();
  const buttonName = String(m.identity || "").trim();
  const targetName = String(label || "").trim() || buttonName || categoryName;
  const keyToken = String(label || "").trim() || categoryName || buttonName || "Button";
  const scope = vpButtonId ? "VIEWPORT_BUTTON" : "BUTTON";
  if (deviceId != null) refs.deviceId = Number(deviceId);
  if (pageId != null) refs.pageId = pageId;
  if (buttonId != null) refs.buttonId = Number(buttonId);
  if (vpButtonId != null) refs.viewportButtonId = Number(vpButtonId);
  if (buttonTag) refs.buttonTag = buttonTag;
  if (pageState && pageState.deviceName) refs.deviceName = String(pageState.deviceName || "");
  if (pageState && pageState.pageName) refs.pageName = String(pageState.pageName || "");
  if (buttonName) refs.buttonName = buttonName;
  const ownerLayerName = wrap && wrap.dataset ? String(wrap.dataset.ownerLayerName || "").trim() : "";
  const vpLayerName = wrap && wrap.dataset ? String(wrap.dataset.vpLayerName || "").trim() : "";
  const frameRaw = wrap && wrap.dataset ? wrap.dataset.frame : null;
  const frameIndexRti = frameRaw == null ? null : Number(frameRaw);
  if (vpLayerName) refs.layerName = vpLayerName;
  else if (ownerLayerName) refs.layerName = ownerLayerName;
  const effectiveRoomName = wrap && wrap.dataset ? String(wrap.dataset.effectiveRoomName || "").trim() : "";
  const effectiveSourceName = wrap && wrap.dataset ? String(wrap.dataset.effectiveSourceName || "").trim() : "";
  const effectiveScopeNames = wrap && wrap.dataset ? String(wrap.dataset.effectiveScopeNames || "").trim() : "";
  if (effectiveRoomName) refs.effectiveRoomName = effectiveRoomName;
  if (effectiveSourceName) refs.effectiveSourceName = effectiveSourceName;
  if (effectiveScopeNames) refs.effectiveScopeNames = effectiveScopeNames;
  if (vpButtonId != null && frameIndexRti != null && Number.isFinite(frameIndexRti)) {{
   refs.frameIndexRti = Number(frameIndexRti);
   refs.viewport = `Frame ${{Number(frameIndexRti) + 1}}`;
  }} else {{
   refs.viewport = "No";
  }}
  refs.scope = scope;
  const apexScopeSource = (m.apexScopeSource && typeof m.apexScopeSource === "object") ? m.apexScopeSource : null;
  if (apexScopeSource) {{
   refs.apexScopeSource = apexScopeSource;
   const pageScope = (apexScopeSource.page && typeof apexScopeSource.page === "object") ? apexScopeSource.page : {{}};
   const viewportLayerScope = (apexScopeSource.viewportLayer && typeof apexScopeSource.viewportLayer === "object")
    ? apexScopeSource.viewportLayer
    : ((apexScopeSource.layer && typeof apexScopeSource.layer === "object") ? apexScopeSource.layer : {{}});
   const pageLayerScope = (apexScopeSource.pageLayer && typeof apexScopeSource.pageLayer === "object") ? apexScopeSource.pageLayer : {{}};
   const buttonScope = (apexScopeSource.button && typeof apexScopeSource.button === "object") ? apexScopeSource.button : {{}};
   const bindings = (apexScopeSource.bindings && typeof apexScopeSource.bindings === "object") ? apexScopeSource.bindings : {{}};
   const rtiAddress = pageScope.rtiAddress;
   const pageRoomId = pageScope.roomId;
   const pageSourceDeviceId = pageScope.sourceDeviceId;
   const viewportLayerRoomId = viewportLayerScope.roomId;
   const viewportLayerSourceId = viewportLayerScope.sourceId;
   const pageLayerRoomId = pageLayerScope.roomId;
   const pageLayerSourceId = pageLayerScope.sourceId;
   const effectiveRoomId = viewportLayerRoomId != null
    ? Number(viewportLayerRoomId)
    : (pageLayerRoomId != null ? Number(pageLayerRoomId) : (pageRoomId != null ? Number(pageRoomId) : null));
   const effectiveSourceId = viewportLayerSourceId != null
    ? Number(viewportLayerSourceId)
    : (pageLayerSourceId != null ? Number(pageLayerSourceId) : (pageSourceDeviceId != null ? Number(pageSourceDeviceId) : null));
   const buttonTagId = buttonScope.buttonTagId;
   const scopedButtonId = buttonScope.buttonId;
   const macroIds = Array.isArray(bindings.macroIds) ? bindings.macroIds : [];
   const variableIds = Array.isArray(bindings.variableIds) ? bindings.variableIds : [];
   const macroStepIds = Array.isArray(bindings.macroStepIds) ? bindings.macroStepIds : [];
   const lowerLabel = String(keyToken || "").trim().toLowerCase();
   if (buttonTagId != null) {{
    let programRef = "none";
    const firstMacroId = macroIds.length ? Number(macroIds[0]) : null;
    const firstVarId = variableIds.length ? Number(variableIds[0]) : null;
    const firstMacroStepId = macroStepIds.length ? Number(macroStepIds[0]) : null;
    if (lowerLabel === "macro" || lowerLabel === "macros") {{
     if (firstMacroId != null && Number.isFinite(firstMacroId)) programRef = `macro:${{firstMacroId}}`;
    }} else if (lowerLabel === "macrostep" || lowerLabel === "macrosteps") {{
     if (firstMacroId != null && Number.isFinite(firstMacroId)) {{
      if (firstMacroStepId != null && Number.isFinite(firstMacroStepId)) {{
       programRef = `mstep:${{firstMacroId}}:${{firstMacroStepId}}`;
      }} else {{
       programRef = `mstepmacro:${{firstMacroId}}`;
      }}
     }}
    }} else if (lowerLabel.startsWith("variable - ") || lowerLabel.startsWith("var.")) {{
     if (firstVarId != null && Number.isFinite(firstVarId)) programRef = `var:${{firstVarId}}`;
    }}
    const scopeType = Number(effectiveRoomId || 0) === 0 ? "GLOBAL" : "ROOM";
    refs.scopeType = scopeType;
    refs.effectiveRoomId = effectiveRoomId;
    refs.effectiveSourceId = effectiveSourceId;
    refs.programRef = programRef;
    if (rtiAddress != null && effectiveRoomId != null && effectiveSourceId != null) {{
     const targetKey = `tt2:${{Number(rtiAddress)}}:${{scopeType}}:${{Number(effectiveRoomId)}}:${{Number(effectiveSourceId)}}:${{Number(buttonTagId)}}:${{programRef}}:${{keyToken}}`;
     return {{
      targetKey,
      kind: scope,
      targetName,
      refs
     }};
    }}
   }} else {{
    const sharedLayerId = viewportLayerScope.sharedLayerId;
    const layerId = viewportLayerScope.layerId;
    const sharedFlag = sharedLayerId != null ? "SHARED" : "LOCAL";
    const scopeLayerId = sharedLayerId != null ? Number(sharedLayerId) : (layerId != null ? Number(layerId) : null);
    refs.sharedFlag = sharedFlag;
    refs.scopeLayerId = scopeLayerId;
    if (rtiAddress != null && scopeLayerId != null && scopedButtonId != null) {{
     const targetKey = `tt_ui:${{Number(rtiAddress)}}:${{sharedFlag}}:${{scopeLayerId}}:${{Number(scopedButtonId)}}:${{keyToken}}`;
     return {{
      targetKey,
      kind: scope,
      targetName,
      refs
     }};
    }}
   }}
  }}
  let targetKey = "";
  if (vpButtonId && deviceId != null && pageId != null && buttonId != null) {{
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{buttonId}}:${{keyToken}}`;
  }} else if (vpButtonId && deviceId != null && pageId != null) {{
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{keyToken}}`;
  }} else if (deviceId != null && pageId != null && buttonId != null) {{
   targetKey = `btn:${{deviceId}}:${{pageId}}:${{buttonId}}:${{keyToken}}`;
  }} else {{
   targetKey = `btn:${{keyToken}}`;
  }}
  return {{
   targetKey,
   kind: scope,
   targetName,
   refs
  }};
 }}
 function esc(s){{return String(s == null ? '' : s).replace(/[&<>\"]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[m]));}}
  function setPostStatus(text, kind) {{
   if (!postStatus) return;
   const t=String(text||'').trim();
   postStatus.textContent=t;
   postStatus.className='post-status' + (kind ? (' is-' + kind) : '');
   if (t) postStatus.removeAttribute('hidden'); else postStatus.setAttribute('hidden','hidden');
  }}
  function setRowInlineError(targetKey, message) {{
   const key = String(targetKey || "").trim();
   const rowUi = rowStatusByTargetKey.get(key);
   if (!rowUi || !rowUi.lastTestEl) return;
   rowUi.lastTestEl.textContent = `Error: ${{String(message || "").trim()}}`;
  }}
 function clearPassAllQueue() {{
  passAllQueue = [];
  passAllContext = null;
 }}
 function drainPassAllQueue() {{
  if (isPosting) return;
  if (!passAllQueue.length) {{
   passAllContext = null;
   return;
  }}
  const next = passAllQueue.shift();
  if (!next || !next.label) {{
   drainPassAllQueue();
   return;
  }}
  const ctx = passAllContext || {{ ctxBtn: null, meta: {{}} }};
  postResultWs(ctx.ctxBtn || null, ctx.meta || {{}}, next.label, "PASS", null, next.rowUi || null);
  if (!passAllQueue.length) passAllContext = null;
 }}
 function queuePassAll(ctxBtn, meta) {{
  clearPassAllQueue();
  rows.querySelectorAll('.row').forEach(row=>{{
   const label = String(row.querySelector('.n')?.textContent || '').trim();
   const buttons = row.querySelectorAll('.actions button');
   const rowUi = {{
    passBtn: buttons.length >= 1 ? buttons[0] : null,
    failBtn: buttons.length >= 2 ? buttons[1] : null,
    lastTestEl: row.querySelector('.row-last-test'),
   }};
   if (!label) return;
   passAllQueue.push({{ label, rowUi }});
  }});
  if (!passAllQueue.length) return;
  passAllContext = {{ ctxBtn: ctxBtn || null, meta: (meta && typeof meta === "object") ? meta : {{}} }};
  drainPassAllQueue();
 }}

 function setPosting(on) {{
  isPosting=!!on;
  rows.querySelectorAll('.row').forEach(row=>{{
   const buttons = row.querySelectorAll('.actions button');
   if (buttons.length < 2) return;
   const passBtn = buttons[0];
   const failBtn = buttons[1];
   const noteEl = row.querySelector('textarea');
   passBtn.disabled = isPosting;
   const note = noteEl ? String(noteEl.value || '').trim() : '';
   failBtn.disabled = isPosting || !note;
  }});
  if (passAllBtn) passAllBtn.disabled=isPosting;
  const closeBtn=document.getElementById('close');
  if (closeBtn) closeBtn.disabled=isPosting;
 }}

 async function postResultWs(ctxBtn, meta, targetLabel, outcome, failNote, rowUi) {{
  const techToken=techTokenFromLocation();
  if (!techToken) {{
   _logTechWs("blocked:no-token");
   return;
  }}
  const target=buildTargetPayload(ctxBtn, meta, targetLabel);
  if (!target) {{
   _logTechWs("blocked:no-target", targetLabel);
   return;
  }}
  const isFail=String(outcome||'').toUpperCase()==='FAIL';
  const note=isFail ? String(failNote||'').trim() : null;
  if (isFail && !note) {{
   _logTechWs("blocked:missing-fail-note", target.targetKey);
   return;
  }}
  if (isPosting) {{
   _logTechWs("blocked:isPosting", {{ pending: pendingTargetKey, targetKey: target.targetKey }});
   return;
  }}

  const payload={{
    type:"test_result.submit",
    target:{{targetKey:target.targetKey,kind:target.kind,refs:target.refs,targetName:target.targetName}},
    outcome:String(outcome||'').toUpperCase(),
    failNote:note
  }};
  _logTechWs("expect", target.targetKey);
  setPosting(true);
  setPostStatus('','');
  pendingTargetKey = target.targetKey;
  if (rowUi) rowStatusByTargetKey.set(target.targetKey, rowUi);
  if (rowUi) setRowStatus(rowUi, payload.outcome, "");
  _sendTechWs(payload);
 }}












 function bindResultRows(ctxBtn, meta) {{
  rowStatusByTargetKey.clear();
  rows.querySelectorAll('.row').forEach(row=>{{
   const label=row.querySelector('.n')?.textContent||'';
   const buttons=row.querySelectorAll('.actions button');
   if (buttons.length<2) return;
   const passBtn=buttons[0];
   const failBtn=buttons[1];
   const noteEl=row.querySelector('textarea');
   const rowUi={{ passBtn, failBtn, lastTestEl: row.querySelector('.row-last-test') }};
   const syncFailEnabled=()=>{{
    const note=noteEl ? String(noteEl.value||'').trim() : '';
    if (!isPosting) failBtn.disabled = !note;
    }};
   if (noteEl) noteEl.addEventListener('input', syncFailEnabled);
   syncFailEnabled();
   const target = buildTargetPayload(ctxBtn, meta, label);
   if (target?.targetKey) {{
    rowStatusByTargetKey.set(target.targetKey, rowUi);
    applyCachedStatus(rowUi, target.targetKey);
   }}
   passBtn.addEventListener('click', e=>{{e.stopPropagation(); postResultWs(ctxBtn, meta, label, 'PASS', null, rowUi);}});
   failBtn.addEventListener('click', e=>{{e.stopPropagation(); postResultWs(ctxBtn, meta, label, 'FAIL', noteEl ? noteEl.value : '', rowUi);}});
  }});
 }}
 function bindTestButtonClicks(root) {{
  const scope=root||document;
  scope.querySelectorAll('.test-btn').forEach(b=>{{
   if (b.dataset.boundTestBtn) return;
   b.dataset.boundTestBtn='1';
   b.addEventListener('click',()=>{{
     const m=JSON.parse(b.dataset.meta||'{{}}');
     const suffix=(APP_UI.testingPopup?.includeButtonTypeInTitle&&m.buttonType)?` (${{m.buttonType}})`:''; 
     pt.textContent=(APP_UI.testingPopup?.titleTemplate||'{{category}} Test - {{identity}}').replace('{{category}}',m.category).replace('{{identity}}',m.identity)+suffix;
     rows.innerHTML=(m.targets||[]).map(t=>`<div class='row'><div class='row-head'><div class='n'>${{esc(t)}}</div></div><div class='row-meta'><div class='actions'><button>Pass</button><button disabled title='Enter a fail note to enable'>Fail</button></div><div class='row-last-test' aria-live='polite'></div></div><textarea placeholder='Fail note (required for Fail)' style='min-height:70px;'></textarea></div>`).join('')||"<div class='row'><div class='n'>No true test targets.</div></div>";
     clearPassAllQueue();
     setPostStatus('','');
     if (passAllBtn) {{
      passAllBtn.disabled = !(Array.isArray(m.targets) && m.targets.length);
      passAllBtn.onclick = () => queuePassAll(b, m);
     }}
     ov.classList.add('open');
     bindResultRows(b, m);
   }});
  }});
 }}
 function bindViewportBoxClicks(root) {{
  const scope=root||document;
  scope.querySelectorAll('.vp-box').forEach(el=>{{
   if (el.dataset.boundVpClick) return;
   el.dataset.boundVpClick='1';
   el.addEventListener('click', ()=>{{
    if (viewportMode.active) return;
    enterViewportMode(el.dataset.vp);
   }});
  }});
 }}
bindTestButtonClicks(document);
bindViewportBoxClicks(document);
 _connectTechWs();
document.getElementById('close').addEventListener('click',()=>{{ clearPassAllQueue(); ov.classList.remove('open'); }});
ov.addEventListener('click',e=>{{if(e.target===ov){{ clearPassAllQueue(); ov.classList.remove('open'); }}}});
 function activePageEl() {{
  return document.querySelector(`.device-page[data-page-index="${{activePageIndex}}"]`);
 }}
 function activePageState() {{
  return PAGE_STATE[activePageIndex] || {{pageName:'',vpFrames:[],layers:[]}};
 }}
 function activeViewportIndex() {{
  if (viewportMode.active) return Number(viewportMode.vpIndex||0);
  const pageEl=activePageEl();
  const frames=(activePageState().vpFrames||[]);
  if (!pageEl || !frames.length) return 0;
  for (let i=0;i<frames.length;i++) {{
   const box=pageEl.querySelector(`.vp-box[data-vp="${{i}}"]`);
   if (box && String(box.dataset.visible||'1')==='1') return i;
  }}
  return 0;
 }}
 function focusedViewportBox() {{
  const pageEl=activePageEl();
  if (!pageEl) return null;
  const vpIndex=Number(viewportMode.vpIndex||0);
  return pageEl.querySelector(`.vp-box[data-vp="${{vpIndex}}"]`);
 }}
 function viewportSupportsOrientation(vpBox, orientation) {{
  if (!vpBox) return true;
  const short = (orientation==='landscape') ? 'l' : 'p';
  const key = short+'Visible';
  return String(vpBox.dataset[key]||'1')==='1';
 }}
 function focusViewportElements() {{
  const pageEl=activePageEl();
  if (!pageEl) return;
  const vpIndex=Number(viewportMode.vpIndex||0);
  pageEl.querySelectorAll('.vp-box, .vp-btn').forEach(el=>{{
   const match=Number(el.dataset.vp||-1)===vpIndex;
   el.classList.toggle('vp-focus', viewportMode.active && match);
  }});
 }}
 function zoomToFocusedViewport() {{
  const rtiCanvas=document.getElementById('rtiCanvas');
  const vpBox=focusedViewportBox();
  if (!rtiCanvas || !vpBox) return;
  const vw=Number(vpBox.dataset.width||0);
  const vh=Number(vpBox.dataset.height||0);
  if (vw<=0 || vh<=0) return;
  const targetW=(rtiCanvas.clientWidth||1)*0.88;
  const targetH=(rtiCanvas.clientHeight||1)*0.88;
  const curW=vw*(currentTotalScale||1);
  const curH=vh*(currentTotalScale||1);
  if (curW<=0 || curH<=0) return;
  const mul=Math.min(targetW/curW, targetH/curH);
  if (!Number.isFinite(mul) || mul<=0) return;
  const nextZoom=clamp(currentZoomPercent*mul, ZOOM_DEFAULT, ZOOM_MAX);
  currentZoomPercent=nextZoom;
 }}
 function centerFocusedViewport() {{
  const rtiCanvas=document.getElementById('rtiCanvas');
  const vpBox=focusedViewportBox();
  if (!rtiCanvas || !vpBox) return;
  const left=Number(vpBox.dataset.left||0)*(currentTotalScale||1);
  const top=Number(vpBox.dataset.top||0)*(currentTotalScale||1);
  const width=Number(vpBox.dataset.width||0)*(currentTotalScale||1);
  const height=Number(vpBox.dataset.height||0)*(currentTotalScale||1);
  const cx=(currentDeviceLeft||0)+left+(width/2);
  const cy=(currentDeviceTop||0)+top+(height/2);
  const maxScrollLeft=Math.max(rtiCanvas.scrollWidth-rtiCanvas.clientWidth,0);
  const maxScrollTop=Math.max(rtiCanvas.scrollHeight-rtiCanvas.clientHeight,0);
  rtiCanvas.scrollLeft=clamp(cx-(rtiCanvas.clientWidth/2),0,maxScrollLeft);
  rtiCanvas.scrollTop=clamp(cy-(rtiCanvas.clientHeight/2),0,maxScrollTop);
 }}
  function popupElements() {{
   return {{
    popup: document.getElementById('vpPopup'),
    panel: document.getElementById('vpPopupPanel'),
    scroller: document.getElementById('vpPopupScroller'),
    scrollpad: document.getElementById('vpPopupScrollpad'),
    stage: document.getElementById('vpPopupStage'),
    close: document.getElementById('vpPopupClose'),
    prev: document.getElementById('vpPopupPrev'),
    next: document.getElementById('vpPopupNext'),
    up: document.getElementById('vpPopupUp'),
    down: document.getElementById('vpPopupDown'),
    indicator: document.getElementById('vpPopupIndicator')
   }};
  }}
  function syncViewportPopupBounds() {{
   const rtiCanvas=document.getElementById('rtiCanvas');
   const popup=document.getElementById('vpPopup');
   if (!rtiCanvas || !popup) return;
   const rr=rtiCanvas.getBoundingClientRect();
   popup.style.left=`${{rr.left}}px`;
   popup.style.top=`${{rr.top}}px`;
   popup.style.width=`${{rr.width}}px`;
   popup.style.height=`${{rr.height}}px`;
  }}
 function activeViewportFrameId(vpIndex) {{
  const frames=activePageState().vpFrames||[];
  const pageFrames=frames[vpIndex]||[];
  if (!pageFrames.length) return null;
  const idx=Math.max(0, Math.min(currentViewportIndexes[vpIndex] ?? 0, pageFrames.length-1));
  currentViewportIndexes[vpIndex]=idx;
  return pageFrames[idx];
 }}
  function popupNavMode() {{
   const vpBox=focusedViewportBox();
   const nav=(vpBox && vpBox.dataset.navMode) ? String(vpBox.dataset.navMode||'page') : 'page';
   return nav;
  }}
   function syncPopupControls() {{
    const els=popupElements();
    if (!els.popup) return;
    const nav=viewportMode.popupNavMode||'page';
    const isPage=(nav==='page');
    const vpIndex=Number(viewportMode.vpIndex||0);
    const frames=(activePageState().vpFrames||[]);
    const pageFrames=frames[vpIndex]||[];
    const hasFrameNav=pageFrames.length>1;
    if (els.prev) els.prev.style.display=(hasFrameNav && isPage)?'':'none';
    if (els.next) els.next.style.display=(hasFrameNav && isPage)?'':'none';
    if (els.indicator) els.indicator.style.display=hasFrameNav?'':'none';
    if (els.up) els.up.style.display=(hasFrameNav && !isPage)?'':'none';
    if (els.down) els.down.style.display=(hasFrameNav && !isPage)?'':'none';
    if (els.indicator) els.indicator.classList.toggle('is-vertical', hasFrameNav && !isPage);
   }}
   function applyViewportPopupLayerVisibility() {{
    if (!viewportMode.active) return;
    const stage=document.getElementById('vpPopupStage');
    if (!stage) return;
    const vpIndex=Number(viewportMode.vpIndex||0);
    const activeFrame=activeViewportFrameId(vpIndex);
    const short=currentOrientation==='landscape' ? 'l' : 'p';
    const vis=activeLayerVisibility();
    stage.querySelectorAll('.vp-popup-vcontent .btn-wrap.vp-btn').forEach(clone=>{{
     let show=true;
     if (activeFrame!=null) show = show && (Number(clone.dataset.frame)===Number(activeFrame));
     const vpVisible=(short==='l' ? (clone.dataset.vpLv||'1') : (clone.dataset.vpPv||'1'))==='1';
     if (!vpVisible) show=false;
     const vpLayerKey=String(clone.dataset.vpLayerKey||'');
     if (vpLayerKey && vis[vpLayerKey]===false) show=false;
     clone.style.display=show?'':'none';
    }});
   }}
  function renderPopupIndicator() {{
   const els=popupElements();
   if (!els.indicator) return;
   const vpIndex=Number(viewportMode.vpIndex||0);
   const frames=(activePageState().vpFrames||[]);
   const pageFrames=frames[vpIndex]||[];
   if (pageFrames.length<=1) {{
    els.indicator.innerHTML='';
    return;
   }}
   const idx=Math.max(0, Math.min(currentViewportIndexes[vpIndex] ?? 0, pageFrames.length-1));
   els.indicator.innerHTML=pageFrames.map((_,i)=>`<span class="dot${{i===idx?' active':''}}" data-dot="${{i}}"></span>`).join('');
  }}
  function positionPopupIndicator() {{
   const els=popupElements();
   const indicator=els.indicator;
   const panel=els.panel;
   const stage=els.stage;
   if (!indicator || !panel || !stage) return;
   if (indicator.style.display==='none') return;
   const viewportWindow=stage.querySelector('.vp-popup-viewport');
   if (!viewportWindow) return;
   const pr=panel.getBoundingClientRect();
   const vr=viewportWindow.getBoundingClientRect();
   const nav=viewportMode.popupNavMode||'page';
   const isPage=(nav==='page');
   const gap=14;
   if (isPage) {{
    const cx=(vr.left - pr.left) + (vr.width/2);
    const top=(vr.bottom - pr.top) + gap;
    indicator.style.left=`${{cx}}px`;
    indicator.style.top=`${{top}}px`;
    indicator.style.transform='translateX(-50%)';
   }} else {{
    const left=(vr.right - pr.left) + gap;
    const cy=(vr.top - pr.top) + (vr.height/2);
    indicator.style.left=`${{left}}px`;
    indicator.style.top=`${{cy}}px`;
    indicator.style.transform='translateY(-50%)';
   }}
  }}
	  function applyViewportPopupLayout() {{
	    if (!viewportMode.active) return;
	    syncViewportPopupBounds();
	    const els=popupElements();
	    const stage=els.stage;
	    const scroller=els.scroller;
	    const scrollpad=els.scrollpad;
	    const vpBox=focusedViewportBox();
	    if (!stage || !scroller || !vpBox) return;
	   const nav=viewportMode.popupNavMode||'page';
	   const vw=Number(vpBox.dataset.width||0);
	   const vh=Number(vpBox.dataset.height||0);
	   if (vw<=0 || vh<=0) return;
	   const isPage=(nav==='page');
		   // Reserve is sizing-only: used to compute the 100% baseline fit scale, but not applied
		   // as real scroller insets (so zoom steps remain smooth from 100% upward).
		   const CONTROL_GAP=10;
	   let topReserve=0;
	   let bottomReserve=0;
	   let leftReserve=0;
	   let rightReserve=0;
		   let lr=null;
		   let rr=null;
		   let ur=null;
		   let dr=null;
	   const pr=els.panel ? els.panel.getBoundingClientRect() : null;
	   if (!pr) return;
	   if (!isPage) {{
	    ur=(els.up && els.up.style.display!=='none') ? els.up.getBoundingClientRect() : null;
	    dr=(els.down && els.down.style.display!=='none') ? els.down.getBoundingClientRect() : null;
	    if (ur) topReserve=Math.max(0, (ur.bottom - pr.top)) + CONTROL_GAP;
	    if (dr) bottomReserve=Math.max(0, (pr.bottom - dr.top)) + CONTROL_GAP;
	   }} else {{
	    lr=(els.prev && els.prev.style.display!=='none') ? els.prev.getBoundingClientRect() : null;
	    rr=(els.next && els.next.style.display!=='none') ? els.next.getBoundingClientRect() : null;
	    if (lr) leftReserve=Math.max(0, (lr.right - pr.left)) + CONTROL_GAP;
	    if (rr) rightReserve=Math.max(0, (pr.right - rr.left)) + CONTROL_GAP;
	   }}
	    // Keep center stable while zooming by preserving the scroll center ratio.
	    const prevScrollW=Math.max(scroller.scrollWidth||0, 1);
	    const prevScrollH=Math.max(scroller.scrollHeight||0, 1);
	    const prevCx=(scroller.scrollLeft + (scroller.clientWidth/2)) / prevScrollW;
	    const prevCy=(scroller.scrollTop + (scroller.clientHeight/2)) / prevScrollH;
	
		    scroller.style.display='block';
		    scroller.style.boxSizing='border-box';
		    scroller.style.left='0px';
		    scroller.style.right='0px';
		    scroller.style.top='0px';
		    scroller.style.bottom='0px';
		    scroller.style.padding='0px';
		   const availW=Math.max(scroller.clientWidth||1,1);
		   const availH=Math.max(scroller.clientHeight||1,1);
		   const zoom=clamp(Number(viewportMode.popupZoomPercent||ZOOM_DEFAULT), ZOOM_DEFAULT, ZOOM_MAX);
		   viewportMode.popupZoomPercent=zoom;

		   // Cache a baseline fit scale computed from the reserved available area (as-if the
		   // scroller were inset), but keep the scroller full-panel for all zoom levels.
		   const usableW=Math.max(1, (pr.width||availW) - leftReserve - rightReserve);
		   const usableH=Math.max(1, (pr.height||availH) - topReserve - bottomReserve);
		   const baseKey=`${{nav}}:${{Math.round(pr.width||availW)}}x${{Math.round(pr.height||availH)}}:${{vw}}x${{vh}}:${{Math.round(leftReserve)}}:${{Math.round(rightReserve)}}:${{Math.round(topReserve)}}:${{Math.round(bottomReserve)}}`;
		   if (viewportMode.popupBaseFitScale==null || viewportMode.popupBaseKey!==baseKey) {{
		    const fitReserved=Math.min(usableW/vw, usableH/vh);
		    viewportMode.popupBaseFitScale=(Number.isFinite(fitReserved) && fitReserved>0) ? fitReserved : 1;
		    viewportMode.popupBaseKey=baseKey;
		   }}
		   viewportMode.popupFitScale=Number(viewportMode.popupBaseFitScale||1);
	    const allowPan = zoom > ZOOM_DEFAULT;
    scroller.style.overflow = allowPan ? 'auto' : 'hidden';
    scroller.classList.toggle('scroll-hover', allowPan);
   const scale=viewportMode.popupFitScale*(zoom/100);
  stage.dataset.popupScale=String(scale);
  stage.style.width=`${{vw*scale}}px`;
  stage.style.height=`${{vh*scale}}px`;

  const viewportWindow=stage.querySelector('.vp-popup-viewport');
  if (viewportWindow) {{
   viewportWindow.style.width=`${{vw*scale}}px`;
   viewportWindow.style.height=`${{vh*scale}}px`;
  }}

  const content=stage.querySelector('.vp-popup-vcontent');
  const contentW=Number(stage.dataset.contentW||vw);
  const contentH=Number(stage.dataset.contentH||vh);
  if (content) {{
   content.style.width=`${{contentW*scale}}px`;
   content.style.height=`${{contentH*scale}}px`;
  }}

  // When zoomed, ensure the scroll container's scrollWidth/scrollHeight actually reflect the
  // zoomed stage size. Otherwise the left/top edge can appear "locked" on early zoom steps
  // (the stage grows beyond the usable area, but scrollWidth doesn't grow, so scrollLeft stays 0).
  //
  // Also keep the viewport centered on any axis that doesn't overflow: if we force flex-start
  // on both axes, the viewport pins to top-left and breaks the centering contract.
	  if (scrollpad) {{
	   const stageW=vw*scale;
	   const stageH=vh*scale;
	   if (!allowPan) {{
	    scrollpad.style.width='100%';
	    scrollpad.style.height='100%';
	    scrollpad.style.boxSizing='border-box';
	    scrollpad.style.paddingLeft='0px';
	    scrollpad.style.paddingTop='0px';
	    scrollpad.style.paddingRight='0px';
	    scrollpad.style.paddingBottom='0px';
	    scrollpad.style.justifyContent='center';
	    scrollpad.style.alignItems='center';
	   }} else {{
	    // If the platform uses classic scrollbars (non-overlay), the gutter appears on the
	    // right/bottom and shifts the visible center. To keep the viewport visually centered
	    // relative to the popup controls, add symmetric padding on the opposite edges.
	    const sbW=Math.max(0, (scroller.offsetWidth||0) - (scroller.clientWidth||0));
	    const sbH=Math.max(0, (scroller.offsetHeight||0) - (scroller.clientHeight||0));
	    const padLeft=sbW;
	    const padTop=sbH;

	    scrollpad.style.boxSizing='border-box';
	    scrollpad.style.paddingLeft=`${{padLeft}}px`;
	    scrollpad.style.paddingTop=`${{padTop}}px`;
	    scrollpad.style.paddingRight='0px';
	    scrollpad.style.paddingBottom='0px';

	    // Grow the scrollpad to at least the stage size to make scrollWidth/scrollHeight expand with zoom.
	    scrollpad.style.width=`${{Math.max(availW, stageW + padLeft)}}px`;
	    scrollpad.style.height=`${{Math.max(availH, stageH + padTop)}}px`;
	    const needsHScroll=stageW > (availW + 0.5);
	    const needsVScroll=stageH > (availH + 0.5);
	    scrollpad.style.justifyContent=needsHScroll ? 'flex-start' : 'center';
	    scrollpad.style.alignItems=needsVScroll ? 'flex-start' : 'center';
	   }}
	  }}

  stage.querySelectorAll('.btn-wrap.vp-btn[data-src-left]').forEach(el=>{{
   const left=Number(el.dataset.srcLeft||0)*scale;
   const top=Number(el.dataset.srcTop||0)*scale;
   const width=Number(el.dataset.srcWidth||0)*scale;
   const height=Number(el.dataset.srcHeight||0)*scale;
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
   const btn=el.querySelector('.test-btn');
   if (btn) {{
    const sourceFont=Number(el.dataset.fontSize||APP_UI.buttonPresentation?.fallbackFontSize||10);
    if (APP_UI.buttonPresentation?.scaleRtiDerivedFontSizes) btn.style.fontSize=`${{Math.max(1, sourceFont*scale)}}px`;
    else btn.style.fontSize=`${{sourceFont}}px`;
    btn.style.borderRadius=`${{Math.max(2, 10*scale)}}px`;
   }}
  }});

   // Virtual scrolling for vertical scroll viewports (no native scrollbars).
   if (!isPage && content) {{
   const maxScroll=Math.max(0, contentH - vh);
   const next=clamp(Number(viewportMode.popupScrollY||0), 0, maxScroll);
   viewportMode.popupScrollY=next;
   content.style.transform=`translateY(-${{next*scale}}px)`;
    }} else if (content) {{
     viewportMode.popupScrollY=0;
     content.style.transform='';
    }}

    // After layout changes, restore scroll position (or reset at fit).
    if (!allowPan) {{
     scroller.scrollLeft=0;
     scroller.scrollTop=0;
    }} else {{
     const newScrollW=Math.max(scroller.scrollWidth||0, 1);
     const newScrollH=Math.max(scroller.scrollHeight||0, 1);
     const maxL=Math.max(0, newScrollW - scroller.clientWidth);
     const maxT=Math.max(0, newScrollH - scroller.clientHeight);
     scroller.scrollLeft=clamp((prevCx*newScrollW)-(scroller.clientWidth/2), 0, maxL);
     scroller.scrollTop=clamp((prevCy*newScrollH)-(scroller.clientHeight/2), 0, maxT);

	     // Snap-center: when zooming, keep the viewport window visually centered relative to the
	     // nav arrows (user's reference), not relative to the scrollbar client area. This keeps the
	     // viewport stable even when classic scrollbar gutters appear.
	     // This avoids small accumulated drift from scrollWidth/clientWidth rounding and flex layout.
	     const viewportWindow=stage.querySelector('.vp-popup-viewport');
	     if (viewportWindow) {{
	      const sr=scroller.getBoundingClientRect();
	      const wr=viewportWindow.getBoundingClientRect();
	      let desiredCx=(pr.left + pr.right)/2;
	      let desiredCy=(pr.top + pr.bottom)/2;
	      if (lr && rr) {{
	       const lcx=(lr.left+lr.right)/2;
	       const lcy=(lr.top+lr.bottom)/2;
	       const rcx=(rr.left+rr.right)/2;
	       const rcy=(rr.top+rr.bottom)/2;
	       desiredCx=(lcx+rcx)/2;
	       desiredCy=(lcy+rcy)/2;
	      }} else if (ur && dr) {{
	       const ucx=(ur.left+ur.right)/2;
	       const ucy=(ur.top+ur.bottom)/2;
	       const dcx=(dr.left+dr.right)/2;
	       const dcy=(dr.top+dr.bottom)/2;
	       desiredCx=(ucx+dcx)/2;
	       desiredCy=(ucy+dcy)/2;
	      }}
	      const cx=(wr.left+wr.right)/2;
	      const cy=(wr.top+wr.bottom)/2;
	      const dx=cx-desiredCx;
	      const dy=cy-desiredCy;
	      if (Math.abs(dx) > 0.25) scroller.scrollLeft=clamp(scroller.scrollLeft + dx, 0, maxL);
	      if (Math.abs(dy) > 0.25) scroller.scrollTop=clamp(scroller.scrollTop + dy, 0, maxT);
	     }}
	    }}
    positionPopupIndicator();
   }}
	  function renderViewportPopup() {{
	   if (!viewportMode.active) return;
	   const els=popupElements();
	   const stage=els.stage;
	   const scroller=els.scroller;
	   const pageEl=activePageEl();
	   const vpBox=focusedViewportBox();
	   if (!stage || !scroller || !pageEl || !vpBox) return;
   const vpIndex=Number(viewportMode.vpIndex||0);
   viewportMode.popupNavMode=popupNavMode();
   syncPopupControls();
   stage.innerHTML='';
   const nav=viewportMode.popupNavMode||'page';
   const vw=Number(vpBox.dataset.width||0);
   const vh=Number(vpBox.dataset.height||0);
   const vpLeft=Number(vpBox.dataset.left||0);
   const vpTop=Number(vpBox.dataset.top||0);
   const short=currentOrientation==='landscape' ? 'l' : 'p';
   const activeFrame=activeViewportFrameId(vpIndex);
   let contentBottom=vh;
   let contentRight=vw;
   const btnNodes=[...pageEl.querySelectorAll(`.btn-wrap.vp-btn[data-vp="${{vpIndex}}"]`)];
   const frameFiltered=btnNodes.filter(node=>activeFrame==null || Number(node.dataset.frame)===Number(activeFrame));
   frameFiltered.forEach(node=>{{
    // Popup uses viewport-relative coordinates; source nodes store device-absolute coords.
    const relTop=Number(node.dataset.top||0) - vpTop;
    const relLeft=Number(node.dataset.left||0) - vpLeft;
    const b=relTop + Number(node.dataset.height||0);
    const r=relLeft + Number(node.dataset.width||0);
    if (b>contentBottom) contentBottom=b;
    if (r>contentRight) contentRight=r;
   }});
   stage.dataset.contentW=String(Math.max(vw, contentRight));
   stage.dataset.contentH=String(nav==='page' ? vh : Math.max(vh, contentBottom));

  const viewportWindow=document.createElement('div');
  viewportWindow.className='vp-popup-viewport';
  const viewportContent=document.createElement('div');
  viewportContent.className='vp-popup-vcontent';
  viewportWindow.appendChild(viewportContent);
  stage.appendChild(viewportWindow);

   viewportMode.popupScrollY=0;
	   frameFiltered.forEach(node=>{{
	     const clone=node.cloneNode(true);
	     clone.style.display='';
	     // Ensure popup controls remain topmost regardless of source z-index.
	     clone.style.zIndex='1';
	     // Cloned buttons inherit data-bound markers from the main canvas; clear so the popup can bind clicks.
	     clone.querySelectorAll('.test-btn').forEach(tb=>{{
	      tb.removeAttribute('data-bound-test-btn');
	      try {{ delete tb.dataset.boundTestBtn; }} catch (_) {{}}
	     }});
	    // Convert from device-absolute (source) to viewport-relative (popup).
	    clone.dataset.srcLeft=String(Number(node.dataset.left||0) - vpLeft);
	    clone.dataset.srcTop=String(Number(node.dataset.top||0) - vpTop);
	    clone.dataset.srcWidth=String(Number(node.dataset.width||0));
	    clone.dataset.srcHeight=String(Number(node.dataset.height||0));
     clone.dataset.pageIndex=String(activePageIndex);
    let show=true;
    if (activeFrame!=null) show = show && (Number(clone.dataset.frame)===Number(activeFrame));
    const vpVisible=(short==='l' ? (clone.dataset.vpLv||'1') : (clone.dataset.vpPv||'1'))==='1';
   if (!vpVisible) show=false;
    const vpLayerKey=String(clone.dataset.vpLayerKey||'');
    if (vpLayerKey && activeLayerVisibility()[vpLayerKey]===false) show=false;
    clone.style.display=show?'':'none';
    viewportContent.appendChild(clone);
   }});
   bindTestButtonClicks(viewportContent);
   renderPopupIndicator();
	   applyViewportPopupLayerVisibility();
	   viewportMode.popupZoomPercent=ZOOM_DEFAULT;
	   viewportMode.popupBaseFitScale=null;
	   viewportMode.popupBaseKey='';
	   syncZoomResetText();
	   applyViewportPopupLayout();
	  }}
  function enterViewportMode(vpIndex) {{
  const overlay=document.getElementById('vpOverlay');
  const closeBtn=document.getElementById('vpPopupClose');
  const appCanvas=document.getElementById('appCanvas');
  const viewportRoot=document.body || appCanvas;
  const popup=document.getElementById('vpPopup');
  if (!overlay || !closeBtn || !viewportRoot || !popup) return;
  viewportMode.active=true;
  viewportMode.vpIndex=Number(vpIndex||0);
  viewportMode.preZoom=currentZoomPercent;
   syncViewportPopupBounds();
   overlay.removeAttribute('hidden');
   popup.removeAttribute('hidden');
  viewportRoot.classList.add('viewport-mode');
  focusViewportElements();
  renderViewportPopup();
  renderLayerPanel();
  applyLayerVisibility();
 }}
  function exitViewportMode() {{
  const overlay=document.getElementById('vpOverlay');
  const closeBtn=document.getElementById('vpPopupClose');
  const appCanvas=document.getElementById('appCanvas');
  const viewportRoot=document.body || appCanvas;
  const popup=document.getElementById('vpPopup');
  const stage=document.getElementById('vpPopupStage');
  if (!overlay || !closeBtn || !viewportRoot || !popup) return;
  viewportMode.active=false;
  viewportRoot.classList.remove('viewport-mode');
   overlay.setAttribute('hidden','hidden');
   popup.setAttribute('hidden','hidden');
   popup.style.left='';
   popup.style.top='';
   popup.style.width='';
   popup.style.height='';
   if (stage) stage.innerHTML='';
  if (viewportMode.preZoom!=null) currentZoomPercent=viewportMode.preZoom;
  viewportMode.preZoom=null;
  focusViewportElements();
  applyRtiLayout();
  renderLayerPanel();
  syncViewportControls();
  applyLayerVisibility();
 }}
function layerScopeKey(state) {{
 return [PROJECT_SESSION_KEY, state?.deviceName||'', state?.pageName||''].join('::');
}}
function loadLayerVisibility(scopeKey) {{
 try {{
   const raw=sessionStorage.getItem(scopeKey);
   return raw ? JSON.parse(raw) : null;
 }} catch (_err) {{
   return null;
 }}
}}
function saveLayerVisibility(scopeKey, visibility) {{
 try {{
   sessionStorage.setItem(scopeKey, JSON.stringify(visibility));
 }} catch (_err) {{}}
}}
function ensureLayerVisibility(state) {{
 const scopeKey=layerScopeKey(state);
 const stored=loadLayerVisibility(scopeKey);
 const visibility=(stored && typeof stored==='object') ? stored : Object.fromEntries((state?.layers||[]).map(layer=>[layer.key,true]));
 (state?.layers||[]).forEach(layer=>{{
   if (!(layer.key in visibility)) visibility[layer.key]=true;
 }});
 saveLayerVisibility(scopeKey, visibility);
 return visibility;
}}
function activeViewportLayers() {{
 const pageEl=activePageEl();
 if (!pageEl) return [];
 const vpIndex=Number(viewportMode.vpIndex||0);
 const map=new Map();
 pageEl.querySelectorAll(`.vp-btn[data-vp="${{vpIndex}}"]`).forEach(el=>{{
   const key=String(el.dataset.vpLayerKey||'').trim();
   if (!key) return;
   const name=(String(el.dataset.vpLayerName||'').trim() || key);
   const order=Number(el.dataset.vpLayerOrder||0);
   if (!map.has(key)) map.set(key, {{key, name, layerOrder: order}});
 }});
 return [...map.values()].sort((a,b)=>Number(b.layerOrder||0)-Number(a.layerOrder||0));
}}
function activeLayerList() {{
 const state=activePageState();
 return viewportMode.active ? activeViewportLayers() : (state.layers||[]);
}}
function activeLayerScopeKey() {{
 const base=layerScopeKey(activePageState());
 return viewportMode.active ? (base+`::viewport:${{Number(viewportMode.vpIndex||0)}}`) : base;
}}
function ensureActiveLayerVisibility() {{
 const layers=activeLayerList();
 const scopeKey=activeLayerScopeKey();
 const stored=loadLayerVisibility(scopeKey);
 const visibility=(stored && typeof stored==='object') ? stored : Object.fromEntries((layers||[]).map(layer=>[layer.key,true]));
 (layers||[]).forEach(layer=>{{ if (!(layer.key in visibility)) visibility[layer.key]=true; }});
 saveLayerVisibility(scopeKey, visibility);
 return visibility;
}}
function activeLayerVisibility() {{
 return ensureActiveLayerVisibility();
}}
function currentOrientationSize() {{
 const size=(ORIENTATION_STATE.sizes && ORIENTATION_STATE.sizes[currentOrientation]) || SOURCE_DEVICE_SIZE;
 return {{
  width:Number(size?.width||SOURCE_DEVICE_SIZE.width||480),
  height:Number(size?.height||SOURCE_DEVICE_SIZE.height||854)
 }};
}}
function applyOrientationState() {{
 const short=currentOrientation==='landscape' ? 'l' : 'p';
 document.querySelectorAll('.orientation-btn').forEach(button=>button.classList.toggle('active', button.dataset.orientation===currentOrientation));
 document.querySelectorAll('.device-page .vp-box, .device-page .btn-wrap').forEach(el=>{{
  const visKey=`${{short}}Visible`;
  el.dataset.left=String(Number(el.dataset[`${{short}}Left`]||0));
  el.dataset.top=String(Number(el.dataset[`${{short}}Top`]||0));
  el.dataset.width=String(Number(el.dataset[`${{short}}Width`]||0));
  el.dataset.height=String(Number(el.dataset[`${{short}}Height`]||0));
  if (visKey in el.dataset) {{
   // vp-box elements previously only had data-p-visible/data-l-visible; normalize to data-visible too.
   el.dataset.visible=String(el.dataset[visKey]||'1');
  }}
 }});
}}
function renderOrientationToggle() {{
 const toggle=document.getElementById('orientationToggle');
 if (!toggle) return;
 const options=Array.isArray(ORIENTATION_STATE.options) ? ORIENTATION_STATE.options : [];
 toggle.querySelectorAll('.orientation-btn').forEach(button=>{{
  const enabled=options.includes(button.dataset.orientation||'');
  button.style.display=enabled ? '' : 'none';
  button.classList.toggle('active', button.dataset.orientation===currentOrientation);
  if (!button.dataset.bound) {{
   button.dataset.bound='1';
    button.addEventListener('click', ()=>{{
     const next=button.dataset.orientation||'portrait';
     if (next===currentOrientation || !options.includes(next)) return;
     if (viewportMode.active) {{
      const vpBox=focusedViewportBox();
      if (vpBox && !viewportSupportsOrientation(vpBox, next)) return;
     }}
     currentOrientation=next;
     applyOrientationState();
     focusViewportElements();
     applyRtiLayout();
     applyLayerVisibility();
     if (viewportMode.active) renderViewportPopup();
    }});
   }}
  }});
}}
function isLayerVisible(layerKey) {{
 return activeLayerVisibility()[layerKey] !== false;
}}
function renderLayerPanel() {{
 const panel=document.getElementById('layerPanel');
 const list=document.getElementById('layerList');
 if (!panel || !list) return;
  const layers=activeLayerList();
  if (!layers.length) {{
    list.innerHTML='';
    panel.setAttribute('hidden','hidden');
    return;
  }}
 list.innerHTML=layers.map(layer=>`<button class="layer-toggle${{isLayerVisible(layer.key)?'':' is-inactive'}}" type="button" data-layer-key="${{esc(layer.key)}}" aria-pressed="${{isLayerVisible(layer.key)?'true':'false'}}">${{esc(layer.name)}}</button>`).join('');
 panel.removeAttribute('hidden');
  list.querySelectorAll('.layer-toggle').forEach(button=>button.addEventListener('click',()=>{{
    const key=button.dataset.layerKey||'';
    const scopeKey=activeLayerScopeKey();
    const visibility=ensureActiveLayerVisibility();
    visibility[key]=!(visibility[key] !== false);
    saveLayerVisibility(scopeKey, visibility);
    renderLayerPanel();
    applyLayerVisibility();
  }}));
}}
 function applyLayerVisibility() {{
  const pageEl=activePageEl();
  if (!pageEl) return;
 pageEl.querySelectorAll('.vp-box').forEach(el=>{{
   const baseVisible=String(el.dataset.visible||'1')==='1';
   if (viewportMode.active) {{
    const match=Number(el.dataset.vp||-1)===Number(viewportMode.vpIndex||0);
    el.style.display=(match && baseVisible)?'':'none';
   }} else {{
    const layerKey=String(el.dataset.ownerLayerKey||'');
    el.style.display=(isLayerVisible(layerKey) && baseVisible)?'':'none';
   }}
 }});
  pageEl.querySelectorAll('.btn-wrap').forEach(el=>{{
   const layerKey=String(el.dataset.ownerLayerKey||'');
   const baseVisible=String(el.dataset.visible||'1')==='1';
   const layerVisible=isLayerVisible(layerKey);
   let shouldShow=layerVisible && baseVisible;
   if (el.classList.contains('vp-btn')) {{
     if (viewportMode.active && Number(el.dataset.vp||-1)!==Number(viewportMode.vpIndex||0)) {{
      shouldShow=false;
     }}
     const short=currentOrientation==='landscape' ? 'l' : 'p';
     const vpVisible=(short==='l' ? (el.dataset.vpLv||'1') : (el.dataset.vpPv||'1'))==='1';
     if (!vpVisible) shouldShow=false;
     if (viewportMode.active) {{
      const vpLayerKey=String(el.dataset.vpLayerKey||'');
      if (vpLayerKey && activeLayerVisibility()[vpLayerKey]===false) shouldShow=false;
     }}
     const vpIndex=Number(el.dataset.vp||0);
     const frames=activePageState().vpFrames||[];
     const pageFrames=frames[vpIndex]||[];
     if (!pageFrames.length) {{
       shouldShow=false;
     }} else {{
       const currentIndex=Math.max(0, Math.min(currentViewportIndexes[vpIndex] ?? 0, pageFrames.length-1));
       const activeFrame=pageFrames[currentIndex];
       shouldShow=shouldShow && Number(el.dataset.frame)===activeFrame;
     }}
   }}
    el.style.display=shouldShow?'':'none';
  }});
  // In viewport mode the viewer uses cloned nodes; keep them in sync when viewport-layer toggles change.
  if (viewportMode.active) {{
   applyViewportPopupLayerVisibility();
  }}
 }}
function syncHeader() {{
 const headerEl=document.querySelector('#topControls .header');
 if (!headerEl) return;
 const titleTemplate=APP_UI.header?.titleTemplate||'{{deviceName}} - {{pageName}}';
 headerEl.textContent=titleTemplate.replace('{{deviceName}}', PAGE_STATE[0]?.deviceName || '').replace('{{pageName}}', activePageState().pageName || '');
}}
 function syncViewportControls() {{}}
  function applyViewportState() {{
   const pageEl=activePageEl();
   const state=activePageState();
   const frames=state.vpFrames||[];
   if (!pageEl) return;
  frames.forEach((pageFrames, vpIndex)=>{{
    if (!pageFrames.length) return;
    const currentIndex=Math.max(0, Math.min(currentViewportIndexes[vpIndex] ?? 0, pageFrames.length-1));
    currentViewportIndexes[vpIndex]=currentIndex;
  }});
   applyLayerVisibility();
  }}
  function activeZoomPercent() {{
   return Number(viewportMode.active ? (viewportMode.popupZoomPercent||ZOOM_DEFAULT) : (currentZoomPercent||ZOOM_DEFAULT));
  }}
  function syncZoomResetText() {{
   const zoomControls=document.getElementById('zoomControls');
   if (!zoomControls) return;
   const zoomReset=zoomControls.querySelector('.zoom-reset');
   if (!zoomReset) return;
   zoomReset.textContent = `${{activeZoomPercent()}}%`;
  }}
function applyRtiLayout() {{
 const _layoutT0=_perfNow();
 try {{
 const appCanvas=document.getElementById('appCanvas');
 const topControls=document.getElementById('topControls');
 const bottomControls=document.getElementById('bottomControls');
 const orientationControls=document.getElementById('orientationControls');
 const layerControls=document.getElementById('layerControls');
 const layerPanel=document.getElementById('layerPanel');
 const zoomControls=document.getElementById('zoomControls');
 const rtiCanvas=document.getElementById('rtiCanvas');
 const rtiContent=document.getElementById('rtiContent');
 const rtiDeviceCanvas=document.getElementById('rtiDeviceCanvas');
 if (!appCanvas || !topControls || !bottomControls || !layerControls || !zoomControls || !rtiCanvas || !rtiContent || !rtiDeviceCanvas) return;

 const controls={{
   top:Number(APP_UI_CONTROLS.top||0),
   bottom:Number(APP_UI_CONTROLS.bottom||0),
   left:Number(APP_UI_CONTROLS.left||0),
   right:Number(APP_UI_CONTROLS.right||0)
 }};
 const appWidth=window.innerWidth;
 const appHeight=window.innerHeight;
 topControls.style.height=`${{controls.top}}px`;
 bottomControls.style.height=`${{controls.bottom}}px`;
 if (orientationControls) {{
  orientationControls.style.top='auto';
  orientationControls.style.bottom=`${{Math.max(controls.bottom + 16, 16)}}px`;
  orientationControls.style.width=`${{controls.left}}px`;
 }}
 layerControls.style.top=`${{controls.top}}px`;
 layerControls.style.bottom=`${{controls.bottom}}px`;
 layerControls.style.width=`${{controls.right}}px`;
 layerControls.style.left='auto';
 layerControls.style.right='0';

 const rtiCanvasWidth=Math.max(appWidth-controls.left-controls.right,1);
 const rtiCanvasHeight=Math.max(appHeight-controls.top-controls.bottom,1);
 rtiCanvas.style.left=`${{controls.left}}px`;
 rtiCanvas.style.top=`${{controls.top}}px`;
 rtiCanvas.style.width=`${{rtiCanvasWidth}}px`;
 rtiCanvas.style.height=`${{rtiCanvasHeight}}px`;

 const sourceSize=currentOrientationSize();
 const widthScale=rtiCanvasWidth/sourceSize.width;
 const heightScale=rtiCanvasHeight/sourceSize.height;
 let scale=Math.min(widthScale,heightScale);
 const maxScale=Number(RTI_DEVICE_LAYOUT.maxScale ?? 10);
 const minScale=Number(RTI_DEVICE_LAYOUT.minScale ?? 0.25);
 if (!Boolean(RTI_DEVICE_LAYOUT.allowScaleAboveOne)) {{
   scale=Math.min(scale,1);
 }}
 scale=Math.min(maxScale, Math.max(minScale, scale));
 const totalScale=scale*(currentZoomPercent/100);
 const fittedWidth=sourceSize.width*totalScale;
 const fittedHeight=sourceSize.height*totalScale;
 const contentWidth=Math.max(rtiCanvasWidth,fittedWidth);
 const contentHeight=Math.max(rtiCanvasHeight,fittedHeight);
 const offsetLeft=(contentWidth-fittedWidth)/2;
 const offsetTop=(contentHeight-fittedHeight)/2;
 rtiContent.style.width=`${{contentWidth}}px`;
 rtiContent.style.height=`${{contentHeight}}px`;
 rtiDeviceCanvas.style.left=`${{offsetLeft}}px`;
 rtiDeviceCanvas.style.top=`${{offsetTop}}px`;
 rtiDeviceCanvas.style.width=`${{fittedWidth}}px`;
 rtiDeviceCanvas.style.height=`${{fittedHeight}}px`;
 currentTotalScale=totalScale;
 currentDeviceLeft=offsetLeft;
 currentDeviceTop=offsetTop;
 if (_pendingZoomCenter) {{
  const maxScrollLeft=Math.max(rtiCanvas.scrollWidth-rtiCanvas.clientWidth,0);
  const maxScrollTop=Math.max(rtiCanvas.scrollHeight-rtiCanvas.clientHeight,0);
  const cx=Number(_pendingZoomCenter.centerX||0);
  const cy=Number(_pendingZoomCenter.centerY||0);
  rtiCanvas.scrollLeft=clamp((currentDeviceLeft+(cx*currentTotalScale))-(rtiCanvas.clientWidth/2),0,maxScrollLeft);
  rtiCanvas.scrollTop=clamp((currentDeviceTop+(cy*currentTotalScale))-(rtiCanvas.clientHeight/2),0,maxScrollTop);
  _pendingZoomCenter=null;
 }}
 rtiCanvas.classList.toggle('scroll-hover', Boolean(ZOOM_CONTROLS.scrollbars?.showOnHover) && currentZoomPercent > 100);

 if (orientationControls) {{
   orientationControls.style.left='0';
   orientationControls.style.right='auto';
   orientationControls.style.height='auto';
   orientationControls.style.top='auto';
   orientationControls.style.bottom=`${{Math.max(controls.bottom + 16, 16)}}px`;
  }}

 layerControls.style.height=`${{Math.max(appHeight-controls.top-controls.bottom,1)}}px`;
 layerControls.style.justifyContent=(LAYER_PANEL.placement?.centerVertically===false)?'flex-start':'center';
 layerControls.style.alignItems='center';
 if (layerPanel) {{
   const layerPanelWidth=Math.max(Math.min(controls.right-Number(LAYER_PANEL.panel?.sidePadding||32), Number(LAYER_PANEL.panel?.maxWidth||240)), Number(LAYER_PANEL.panel?.minWidth||160));
   layerPanel.style.width=`${{layerPanelWidth}}px`;
   layerPanel.style.maxHeight=`${{Math.max(appHeight-controls.top-controls.bottom-Number(LAYER_PANEL.panel?.verticalPadding||24), 120)}}px`;
 }}

  if (ZOOM_CONTROLS.enabled) {{
    const zoomWidth = zoomControls.offsetWidth || 176;
    const zoomLeft = Math.max((controls.left - zoomWidth) / 2, 0);
    zoomControls.style.left = `${{zoomLeft}}px`;
    zoomControls.style.top = `${{controls.top}}px`;
    syncZoomResetText();
  }}

 document.querySelectorAll('.device-page').forEach(page=>page.classList.toggle('active', Number(page.dataset.pageIndex)===activePageIndex));
 const activePage=activePageEl();
 if (activePage) activePage.querySelectorAll('.vp-box').forEach(el=>{{
   const left=Number(el.dataset.left||0)*totalScale;
   const top=Number(el.dataset.top||0)*totalScale;
   const width=Number(el.dataset.width||0)*totalScale;
   const height=Number(el.dataset.height||0)*totalScale;
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
 }});

 if (activePage) activePage.querySelectorAll('.btn-wrap').forEach(el=>{{
   const left=Number(el.dataset.left||0)*totalScale;
   const top=Number(el.dataset.top||0)*totalScale;
   const width=Number(el.dataset.width||0)*totalScale;
   const height=Number(el.dataset.height||0)*totalScale;
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
   const button=el.querySelector('.test-btn');
   if (button) {{
     const sourceFont=Number(el.dataset.fontSize||APP_UI.buttonPresentation?.fallbackFontSize||10);
     if (APP_UI.buttonPresentation?.scaleRtiDerivedFontSizes) {{
       button.style.fontSize=`${{Math.max(1, sourceFont*totalScale)}}px`;
     }} else {{
       button.style.fontSize=`${{sourceFont}}px`;
     }}
     button.style.borderRadius=`${{Math.max(2, 10*totalScale)}}px`;
   }}
   const linkHit=el.querySelector('.page-link-hit');
   if (linkHit) {{
     const hitWidth=Number(linkHit.dataset.hitWidth||28)*totalScale;
     const hitPadding=Number(linkHit.dataset.hitPadding||8)*totalScale;
     linkHit.style.width=`${{hitWidth}}px`;
     linkHit.style.paddingRight=`${{hitPadding}}px`;
     linkHit.style.right='0';
     const icon=linkHit.querySelector('.page-link-icon');
     if (icon) {{
       const iconSize=Number(icon.dataset.iconSize||16)*totalScale;
       icon.style.width=`${{iconSize}}px`;
       icon.style.height=`${{iconSize}}px`;
       icon.style.fontSize=`${{iconSize}}px`;
   }}
  }}
 }});
 refreshButtonVisualStates();
 syncHeader();
 if (LAYER_PANEL.enabled===false) {{
   const panel=document.getElementById('layerPanel');
   if (panel) panel.setAttribute('hidden','hidden');
  }} else {{
    renderLayerPanel();
  }}
  syncViewportControls();
  applyViewportState();
  if (viewportMode.active) applyViewportPopupLayout();
  maybeReportReadyBaseline();
 }} finally {{
  _recordLayoutPerf(_perfNow()-_layoutT0);
 }}
}}
let _rtiLayoutScheduled=false;
let _pendingZoomCenter=null;
function scheduleRtiLayout(reason) {{
 if (_rtiLayoutScheduled) return;
 _rtiLayoutScheduled=true;
 requestAnimationFrame(() => {{
  _rtiLayoutScheduled=false;
 applyRtiLayout();
 }});
}}
function clamp(value,min,max){{return Math.min(max,Math.max(min,value));}}
let _readyBaselineSent=false;
function maybeReportReadyBaseline() {{
 if (_readyBaselineSent) return;
 const canvas=document.getElementById('rtiCanvas');
 if (!canvas) return;
 const rows=document.querySelectorAll('.device-page.active .btn-wrap');
 if (!rows || !rows.length) return;
 const rect=canvas.getBoundingClientRect();
 if (!rect || rect.width<=0 || rect.height<=0) return;
 const readySec=Number((performance.now()/1000).toFixed(3));
 window.__sentinelReadySec=readySec;
 _readyBaselineSent=true;
 const techToken=techTokenFromLocation();
 if (!techToken) return;
 const url=`/api/v1/testing/${{encodeURIComponent(techToken)}}/ready`;
 const payload={{readySec, recordedAtUtc:new Date().toISOString()}};
 const body=JSON.stringify(payload);
 try {{
  if (navigator.sendBeacon) {{
   const blob=new Blob([body], {{type:'application/json'}});
   navigator.sendBeacon(url, blob);
  }} else {{
   fetch(url, {{method:'POST', headers:{{'content-type':'application/json'}}, body, keepalive:true}}).catch(()=>{{}});
  }}
 }} catch (_e) {{}}
}}
function updateZoom(nextPercent){{
 if (viewportMode.active) {{
  viewportMode.popupZoomPercent=clamp(nextPercent, ZOOM_DEFAULT, ZOOM_MAX);
  syncZoomResetText();
  applyViewportPopupLayout();
  return;
 }}
 const rtiCanvas=document.getElementById('rtiCanvas');
 if (!rtiCanvas) return;
 const oldScale=currentTotalScale||1;
 const oldLeft=currentDeviceLeft||0;
 const oldTop=currentDeviceTop||0;
 const centerX=(rtiCanvas.scrollLeft+(rtiCanvas.clientWidth/2)-oldLeft)/oldScale;
 const centerY=(rtiCanvas.scrollTop+(rtiCanvas.clientHeight/2)-oldTop)/oldScale;
 currentZoomPercent=clamp(nextPercent, ZOOM_DEFAULT, ZOOM_MAX);
 _pendingZoomCenter={{centerX, centerY}};
 syncZoomResetText();
 scheduleRtiLayout("zoom");
}}
function ensurePageMaterialized(pageIndex) {{
 const normalized=Number(pageIndex);
 if (!Number.isFinite(normalized) || !PAGE_STATE[normalized]) return null;
 let pageEl=document.querySelector(`.device-page[data-page-index="${{normalized}}"]`);
 if (pageEl) return pageEl;
 const rtiDeviceCanvas=document.getElementById('rtiDeviceCanvas');
 if (!rtiDeviceCanvas) return null;
 const inner=PAGE_HTML_BY_INDEX[String(normalized)];
 if (typeof inner !== 'string') return null;
 pageEl=document.createElement('div');
 pageEl.className='device-page';
 pageEl.dataset.pageIndex=String(normalized);
 pageEl.innerHTML=inner;
 rtiDeviceCanvas.appendChild(pageEl);
 bindTestButtonClicks(pageEl);
 bindViewportBoxClicks(pageEl);
 applyOrientationState();
 return pageEl;
}}
function setActivePage(nextPageIndex) {{
 const target=Number(nextPageIndex);
 if (!Number.isFinite(target) || !PAGE_STATE[target]) return;
 ensurePageMaterialized(target);
 activePageIndex=target;
 currentZoomPercent=ZOOM_DEFAULT;
 viewportMode.popupZoomPercent=ZOOM_DEFAULT;
 syncZoomResetText();
 currentViewportIndexes=(PAGE_STATE[target].vpFrames||[]).map(()=>0);
 const rtiCanvas=document.getElementById('rtiCanvas');
 if (rtiCanvas) {{
   rtiCanvas.scrollLeft=0;
   rtiCanvas.scrollTop=0;
 }}
 applyRtiLayout();
}}
window.addEventListener('resize', applyRtiLayout);
renderOrientationToggle();
applyOrientationState();
applyRtiLayout();
const rtiCanvasEl=document.getElementById('rtiCanvas');
if (rtiCanvasEl) rtiCanvasEl.addEventListener('scroll', applyRtiLayout, {{passive:true}});
	document.addEventListener('click', e=>{{
	 const link=e.target.closest('.page-link-hit');
	 if (!link) return;
	 const targetPageIndex=link.dataset.targetPageIndex;
	 if (targetPageIndex==null || targetPageIndex==='') return;
	 e.preventDefault();
	 if (viewportMode.active) exitViewportMode();
	 setActivePage(targetPageIndex);
	}});
const zoomDec=document.querySelector('.zoom-dec');
const zoomInc=document.querySelector('.zoom-inc');
const zoomReset=document.querySelector('.zoom-reset');
if (zoomDec) zoomDec.addEventListener('click',()=>updateZoom(activeZoomPercent()-ZOOM_STEP));
if (zoomInc) zoomInc.addEventListener('click',()=>updateZoom(activeZoomPercent()+ZOOM_STEP));
if (zoomReset) zoomReset.addEventListener('click',()=>updateZoom(ZOOM_DEFAULT));
const vpPopupClose=document.getElementById('vpPopupClose');
if (vpPopupClose) vpPopupClose.addEventListener('click',()=>exitViewportMode());
// Only the X closes the popup. Backdrop click and Escape are ignored on purpose.
const popupUp=document.getElementById('vpPopupUp');
const popupDown=document.getElementById('vpPopupDown');
if (popupUp) popupUp.addEventListener('click',()=>{{
 if (!viewportMode.active) return;
 if ((viewportMode.popupNavMode||'page')==='page') return;
 const vpIndex=Number(viewportMode.vpIndex||0);
 const frames=activePageState().vpFrames||[];
 const pageFrames=frames[vpIndex]||[];
 if (pageFrames.length<=1) return;
 const idx=Math.max(0, Math.min(currentViewportIndexes[vpIndex] ?? 0, pageFrames.length-1));
 if (idx<=0) return;
 currentViewportIndexes[vpIndex]=idx-1;
 renderViewportPopup();
}});
if (popupDown) popupDown.addEventListener('click',()=>{{
 if (!viewportMode.active) return;
 if ((viewportMode.popupNavMode||'page')==='page') return;
 const vpIndex=Number(viewportMode.vpIndex||0);
 const frames=activePageState().vpFrames||[];
 const pageFrames=frames[vpIndex]||[];
 if (pageFrames.length<=1) return;
 const idx=Math.max(0, Math.min(currentViewportIndexes[vpIndex] ?? 0, pageFrames.length-1));
 if (idx>=pageFrames.length-1) return;
 currentViewportIndexes[vpIndex]=idx+1;
 renderViewportPopup();
}});
const popupPrev=document.getElementById('vpPopupPrev');
const popupNext=document.getElementById('vpPopupNext');
if (popupPrev) popupPrev.addEventListener('click',()=>{{
 if (!viewportMode.active) return;
 if ((viewportMode.popupNavMode||'page')!=='page') return;
 const vpIndex=Number(viewportMode.vpIndex||0);
 const frames=activePageState().vpFrames||[];
 const pageFrames=frames[vpIndex]||[];
 if (pageFrames.length<=1) return;
 if (pageFrames.length && (currentViewportIndexes[vpIndex] ?? 0)>0) {{
  currentViewportIndexes[vpIndex]--;
  renderViewportPopup();
 }}
}});
if (popupNext) popupNext.addEventListener('click',()=>{{
 if (!viewportMode.active) return;
 if ((viewportMode.popupNavMode||'page')!=='page') return;
 const vpIndex=Number(viewportMode.vpIndex||0);
 const frames=activePageState().vpFrames||[];
 const pageFrames=frames[vpIndex]||[];
 if (pageFrames.length<=1) return;
 if (pageFrames.length && (currentViewportIndexes[vpIndex] ?? 0)<pageFrames.length-1) {{
  currentViewportIndexes[vpIndex]++;
  renderViewportPopup();
 }}
}});
</script></body></html>"""


def _event_section_items(project_data: dict[str, Any], event_key: str) -> list[dict[str, Any]]:
    events = project_data.get("events", {})
    if not isinstance(events, dict):
        return []
    items = events.get(event_key, [])
    return items if isinstance(items, list) else []


def _dedupe_names(values: Any) -> list[str]:
    if isinstance(values, list):
        names: list[str] = []
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in names:
                names.append(cleaned)
        if names:
            return names
    return []


def _event_action_names(user: dict[str, Any], key: str) -> list[str]:
    values = user.get(key)
    names = _dedupe_names(values)
    if names:
        return names
    fallback_key = "macroName" if key == "macroNames" else "commandName"
    fallback = str(user.get(fallback_key) or "").strip()
    return [fallback] if fallback else []


def _driver_macro_steps(user: dict[str, Any]) -> list[dict[str, str]]:
    resolved = user.get("resolvedActions", {})
    if isinstance(resolved, dict):
        raw_steps = resolved.get("macroSteps")
        if isinstance(raw_steps, list):
            out: list[dict[str, str]] = []
            for raw_step in raw_steps:
                if not isinstance(raw_step, dict):
                    continue
                step_type = str(raw_step.get("type") or "").strip()
                if step_type not in {"command", "undefined"}:
                    continue
                out.append({"name": str(raw_step.get("name") or "").strip(), "type": step_type})
            if out:
                return out
        command_names = _dedupe_names(resolved.get("commands"))
        if command_names:
            return [{"name": name, "type": "command"} for name in command_names]
    return []


def _driver_resolved_actions(user: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    resolved = user.get("resolvedActions", {})
    if isinstance(resolved, dict):
        macro_names = _dedupe_names(resolved.get("macros"))
        macro_steps = _driver_macro_steps(user)
        if macro_names or macro_steps:
            return macro_names, macro_steps
    return _event_action_names(user, "macroNames"), _driver_macro_steps(user)


def _event_action_phrase(macro_names: list[str], command_names: list[str]) -> str:
    if macro_names and not command_names:
        noun = "macro" if len(macro_names) == 1 else "macros"
        return f"run {noun}: {'; '.join(macro_names)}"
    if command_names and not macro_names:
        noun = "command" if len(command_names) == 1 else "commands"
        return f"run {noun}: {'; '.join(command_names)}"
    if macro_names and command_names:
        parts = [
            f"{'macro' if len(macro_names) == 1 else 'macros'} {'; '.join(macro_names)}",
            f"{'command' if len(command_names) == 1 else 'commands'} {'; '.join(command_names)}",
        ]
        return f"run actions: {'; '.join(parts)}"
    return "run action: Unknown"


def _event_button_text(item: dict[str, Any], event_kind: str) -> str:
    user = item.get("userFacing", {}) if isinstance(item, dict) else {}
    trigger = str(user.get("resolvedTrigger") or "No trigger").strip()
    if event_kind == "driver":
        driver_category = str(user.get("driverCategory") or "").strip()
        trigger_text = f"{driver_category} / {trigger}" if driver_category else trigger
        macro_names, macro_steps = _driver_resolved_actions(user)
        total_actions = len(macro_names) + len(macro_steps)
        first_action_name = str(user.get("firstActionName") or "").strip()
        if not first_action_name:
            if macro_names:
                first_action_name = macro_names[0]
            else:
                first_action_name = next((str(step.get("name") or "").strip() for step in macro_steps if str(step.get("name") or "").strip()), "")
        if macro_names and not macro_steps:
            noun = "macro" if len(macro_names) == 1 else "macros"
            remainder = f" ...+{total_actions - 1} more" if total_actions > 1 else ""
            return f"When {trigger_text} happens, run {noun}: {first_action_name or 'Unknown'}{remainder}"
        if macro_steps and not macro_names:
            undefined_count = int(user.get("macroStepCount") or len(macro_steps) or 0)
            if macro_steps and all(str(step.get("type") or "") == "undefined" for step in macro_steps):
                noun = "macro step" if undefined_count == 1 else "macro steps"
                return f"When {trigger_text} happens, run {undefined_count} undefined {noun}"
            if len(macro_steps) == 1 and str(macro_steps[0].get("type") or "") == "command":
                return f"When {trigger_text} happens, run macro step (Command): {first_action_name or 'Unknown'}"
            remainder = f" ...+{total_actions - 1} more" if total_actions > 1 else ""
            noun = "macro step" if total_actions == 1 else "macro steps"
            return f"When {trigger_text} happens, run {noun}: {first_action_name or 'Unknown'}{remainder}"
        if macro_names and macro_steps:
            remainder = f" ...+{total_actions - 1} more" if total_actions > 1 else ""
            return f"When {trigger_text} happens, run actions: {first_action_name or 'Unknown'}{remainder}"
        else:
            return f"When {trigger_text} happens, run action: Unknown"
    macro_names = _event_action_names(user, "macroNames")
    command_names = _event_action_names(user, "commandNames")
    action_phrase = _event_action_phrase(macro_names, command_names)
    description = str(user.get("description") or "").strip()
    if description:
        return f'"{escape(description)}" | {trigger}, {action_phrase}'
    return f"{trigger}, {action_phrase}"


def _event_meta(item: dict[str, Any], event_kind: str) -> dict[str, Any]:
    user = item.get("userFacing", {}) if isinstance(item, dict) else {}
    diag = item.get("diagnostics", {}) if isinstance(item, dict) else {}
    event_id = diag.get("eventId") if isinstance(diag, dict) else None
    if event_kind == "driver":
        identity = str(user.get("driverName") or "Driver Event").strip()
    else:
        identity = str(user.get("description") or user.get("eventType") or "System Event").strip()
    targets: list[str] = []
    test_targets = user.get("testTargets", {})
    if isinstance(test_targets, dict):
        for label in ("Trigger", "Macro", "Macros", "MacroStep", "MacroSteps", "Command", "Commands"):
            if test_targets.get(label):
                targets.append(label)

    refs: dict[str, Any] = {"eventId": int(event_id) if event_id is not None else None}
    if isinstance(diag, dict):
        if diag.get("scope") is not None:
            refs["scope"] = diag.get("scope")
        if diag.get("resolvedData") is not None:
            refs["resolvedData"] = diag.get("resolvedData")
    return {
        "category": "Driver Event" if event_kind == "driver" else "System Event",
        "identity": identity,
        "buttonType": "",
        "targets": targets,
        "kind": "EVENT",
        "refs": refs,
    }


def _count_label(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def render_project_home_html(project_data: dict[str, Any], app_ui: dict[str, Any], project_stem: str) -> str:
    source = project_data.get("source", {})
    source_file = str(source.get("file") or project_stem)
    project_title = Path(source_file).stem if source_file else project_stem
    system_events = _event_section_items(project_data, "system")
    driver_events = _event_section_items(project_data, "driver")
    devices = project_data.get("devices", [])
    system_title = f"System Events | {_count_label(len(system_events), 'event')}"
    driver_title = f"Driver Events | {_count_label(len(driver_events), 'event')}"

    system_rows = []
    for item in system_events:
        meta_attr = json.dumps(_event_meta(item, "system")).replace("'", "&apos;")
        system_rows.append(
            f"<button class='home-row event-row test-btn' type='button' data-meta='{meta_attr}'>{_event_button_text(item, 'system')}</button>"
        )

    driver_rows = []
    grouped_drivers: dict[str, list[dict[str, Any]]] = {}
    for item in driver_events:
        user = item.get("userFacing", {}) if isinstance(item, dict) else {}
        driver_name = str(user.get("driverName") or "Unassigned Driver").strip()
        grouped_drivers.setdefault(driver_name, []).append(item)
    for driver_name, items in grouped_drivers.items():
        driver_rows.append(f"<div class='home-subtitle'>{driver_name}</div>")
        for item in items:
            meta_attr = json.dumps(_event_meta(item, "driver")).replace("'", "&apos;")
            driver_rows.append(
                f"<button class='home-row event-row test-btn' type='button' data-meta='{meta_attr}'>{_event_button_text(item, 'driver')}</button>"
            )

    device_rows = []
    for device_index, device in enumerate(devices):
        user = device.get("userFacing", {})
        device_name = str(user.get("displayName") or f"Device {device_index}").strip()
        pages = user.get("pages", [])
        if not isinstance(pages, list) or not pages:
            continue
        page_count = len(pages)
        href = device_filename(project_stem, device_name, device_index)
        label = f"{device_name} | {page_count} page{'s' if page_count != 1 else ''}"
        device_rows.append(f"<a class='home-row device-row' href='{href}'>{label}</a>")

    system_content = "".join(system_rows) if system_rows else "<div class='home-empty'>No system events in project.</div>"
    driver_content = "".join(driver_rows) if driver_rows else "<div class='home-empty'>No driver events in project.</div>"
    device_content = "".join(device_rows) if device_rows else "<div class='home-empty'>No testable devices in project.</div>"

    app_json = json.dumps(app_ui)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{project_title}</title>
<style>
html,body{{margin:0;min-height:100%;}}
body{{font-family:Segoe UI,Tahoma,sans-serif;background:linear-gradient(180deg,#eef3f7 0%,#dce7ef 100%);color:#183247;}}
.home-shell{{max-width:980px;margin:0 auto;padding:28px 20px 40px;box-sizing:border-box;}}
.home-header{{margin-bottom:24px;padding:24px 28px;border:1px solid #c6d2dd;border-radius:20px;background:#f8fbfe;box-shadow:0 14px 34px rgba(24,50,71,.08);}}
.home-kicker{{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#5a7387;margin-bottom:10px;}}
.home-title{{margin:0;font-size:32px;line-height:1.05;}}
.home-source{{margin-top:10px;font-size:14px;color:#4d6678;word-break:break-word;}}
.home-section{{margin-top:28px;padding:22px 24px;border:1px solid #c6d2dd;border-radius:20px;background:#f8fbfe;box-shadow:0 14px 34px rgba(24,50,71,.08);}}
.section-toggle{{display:inline-flex;align-items:center;gap:10px;margin:0;padding:0;border:0;background:transparent;color:#183247;cursor:pointer;text-align:left;}}
.section-toggle-label{{font-size:22px;line-height:1.1;font-weight:700;}}
.section-chevron{{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;color:#5a7387;}}
.section-chevron svg{{display:block;width:14px;height:14px;stroke:currentColor;stroke-width:2.2;fill:none;stroke-linecap:round;stroke-linejoin:round;}}
.home-subtitle{{margin:18px 0 10px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#5a7387;}}
.home-list{{display:flex;flex-direction:column;gap:12px;margin-top:16px;}}
.home-list[hidden]{{display:none !important;}}
.home-row{{width:100%;display:block;box-sizing:border-box;padding:16px 18px;border-radius:16px;border:1px solid #a9bccd;background:#1e5f86;color:#fff;text-decoration:none;font-size:15px;line-height:1.35;text-align:left;box-shadow:inset 0 0 0 1px #154665;}}
.home-row:hover{{filter:brightness(1.05);}}
.event-row{{cursor:pointer;}}
.device-row{{background:#29445a;box-shadow:inset 0 0 0 1px #1c3244;}}
.home-empty{{padding:16px 18px;border:1px dashed #a9bccd;border-radius:16px;background:#edf4f8;color:#557082;font-size:14px;}}
.ov{{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:flex-start;justify-content:center;padding:8px 12px;z-index:10000;}}
.ov.open{{display:flex;}}
.pop{{width:min(560px,calc(100vw - 24px));max-width:100%;max-height:calc(100vh - 16px);display:flex;flex-direction:column;box-sizing:border-box;background:#fff;border:1px solid #cbd7e2;border-radius:18px;padding:20px 24px;margin-top:0;}}
.pop-head{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px;}}
.pop h3{{margin:0;font-size:16px;line-height:1.1;font-weight:700;}}
#passAll{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;}}
#passAll:disabled{{opacity:.55;cursor:not-allowed;}}
.rows-scroll{{overflow:auto;min-height:0;padding-right:2px;scrollbar-width:thin;scrollbar-color:transparent transparent;scrollbar-gutter:stable overlay;}}
.rows-scroll.scroll-hover:hover{{scrollbar-color:#a9bccd transparent;}}
.rows-scroll::-webkit-scrollbar{{width:10px;height:10px;}}
.rows-scroll::-webkit-scrollbar-thumb{{background:transparent;}}
.rows-scroll::-webkit-scrollbar-track{{background:transparent;}}
.rows-scroll.scroll-hover:hover::-webkit-scrollbar-thumb{{background:#a9bccd;border-radius:999px;}}
.row{{box-sizing:border-box;width:100%;border:1px solid #d4dee8;border-radius:14px;padding:12px 14px;margin-bottom:10px;overflow:hidden;}}
.row:last-child{{margin-bottom:0;}}
.row-head{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px;}}
.n{{font-weight:600;margin:0;font-size:14px;line-height:1.1;}}
 .row-meta{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:8px;}}
 .actions{{display:flex;gap:10px;margin:0;}}
 .actions button{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;}}
 .actions button:disabled{{opacity:.55;cursor:not-allowed;}}
 .actions button.is-pass-active{{color:#1f5d2d;background:#eaf7ef;border-color:#39b54a;font-weight:700;}}
 .actions button.is-fail-active{{color:#7f1d1d;background:#fdeeee;border-color:#ef4444;font-weight:700;}}
 .row-last-test{{font-size:13px;line-height:1.2;color:#274258;}}
 textarea{{display:block;box-sizing:border-box;width:100%;max-width:100%;border:1px solid #ccd8e2;border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.2;resize:vertical;}}
 .post-status{{margin:10px 0 10px;font-size:13px;line-height:1.25;border-radius:12px;padding:10px 12px;border:1px solid #ccd8e2;background:#f8fbfe;color:#274258;}}
 .post-status.is-saving{{background:#fff7e8;border-color:#f0a126;color:#6f4b12;}}
 .post-status.is-success{{background:#eaf7ef;border-color:#3a9c5d;color:#1e6b3c;}}
 .post-status.is-error{{background:#fdeeee;border-color:#d05555;color:#8f1f1f;}}
 #close{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;display:block;margin-top:12px;margin-left:auto;margin-right:2px;}}
 #close:disabled{{opacity:.55;cursor:not-allowed;}}
</style></head>
<body>
<main class='home-shell'>
<section class='home-header'>
<div class='home-kicker'>Project Home</div>
<h1 class='home-title'>{project_title}</h1>
<div class='home-source'>{source_file}</div>
</section>
<section class='home-section'>
<button class='section-toggle' type='button' data-target='system-events' aria-expanded='false' onclick='toggleSection(this)'><span class='section-toggle-label'>{system_title}</span><span class='section-chevron' aria-hidden='true'><svg viewBox='0 0 16 16'><path d='M3.5 6.25 8 10.75 12.5 6.25'/></svg></span></button>
<div class='home-list' id='system-events' hidden>{system_content}</div>
</section>
<section class='home-section'>
<button class='section-toggle' type='button' data-target='driver-events' aria-expanded='false' onclick='toggleSection(this)'><span class='section-toggle-label'>{driver_title}</span><span class='section-chevron' aria-hidden='true'><svg viewBox='0 0 16 16'><path d='M3.5 6.25 8 10.75 12.5 6.25'/></svg></span></button>
<div class='home-list' id='driver-events' hidden>{driver_content}</div>
</section>
<section class='home-section'>
<h2>Devices</h2>
<div class='home-list'>{device_content}</div>
</section>
</main>
<div class='ov' id='ov'><div class='pop'><div class='pop-head'><h3 id='pt'></h3><button id='passAll' type='button'>Pass All</button></div><div id='rows' class='rows-scroll scroll-hover'></div><div class='post-status' id='postStatus' role='status' aria-live='polite' hidden></div><button id='close'>Close</button></div></div>
<script>
const APP_UI={app_json};
 const ov=document.getElementById('ov'),pt=document.getElementById('pt'),rows=document.getElementById('rows'),postStatus=document.getElementById('postStatus'),passAllBtn=document.getElementById('passAll');
 let isPosting=false;
 let techWs=null;
 let techWsToken=null;
 let techWsReconnectTimer=null;
 let techWsReconnectDelayMs=500;
 let pendingTargetKey=null;
 let passAllQueue=[];
 let passAllContext=null;
 const rowStatusByTargetKey=new Map();
 const statusByTargetKey=new Map();
 function _logTechWs(action, data) {{
  try {{
   if (typeof console !== "undefined" && console.log) {{
    const msg = data == null ? "" : data;
    console.log("[tech-ws]", action, msg);
   }}
  }} catch (_e) {{}}
 }}
 function techTokenFromLocation() {{
  const parts=String(window.location.pathname||'').split('/').filter(Boolean);
  const i=parts.indexOf('testing');
  return (i>=0 && parts[i+1]) ? parts[i+1] : null;
 }}
 function techWsUrl(path) {{
  const proto = window.location && window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location && window.location.host ? window.location.host : "localhost";
  return `${{proto}}://${{host}}${{path}}`;
 }}
 function _scheduleTechWsReconnect() {{
  if (techWsReconnectTimer) return;
  techWsReconnectTimer = setTimeout(() => {{
   techWsReconnectTimer = null;
   _connectTechWs();
  }}, Math.min(5000, Math.max(250, techWsReconnectDelayMs)));
  techWsReconnectDelayMs = Math.min(5000, techWsReconnectDelayMs * 2);
 }}
 function _sendTechSyncRequest() {{
  if (!techWs || techWs.readyState !== 1) return;
  try {{
   techWs.send(JSON.stringify({{ type:"sync.request", lastAppliedSeq:Number(techLastAppliedSeq||0) }}));
   _logTechWs("sync.request", Number(techLastAppliedSeq||0));
  }} catch (_e) {{}}
 }}
 function _applyTechPayload(payload) {{
   const t = String(payload?.type || "").trim();
   _logTechWs("recv", t || "(unknown)");
   if (t === "error") {{
     const code = payload?.code;
     const message = payload?.message;
      const msg = String(code ? `${{code}}${{message ? ": " + message : ""}}` : (message || "Error"));
      setPosting(false);
      if (pendingTargetKey) setRowInlineError(pendingTargetKey, msg);
      setPostStatus("", "");
      drainPassAllQueue();
      return;
     }}
   if (t === "replay.batch") {{
    const events = Array.isArray(payload?.events) ? payload.events : [];
    for (const ev of events) _applyTechPayload(ev);
    return;
   }}
   const seq = Number(payload?.seq || 0);
   const isSnapshot = t === "testing_snapshot";
   if (seq > 0) {{
    if (seq <= techLastAppliedSeq) return;
    if (!isSnapshot && seq > techLastAppliedSeq + 1) {{
      _sendTechSyncRequest();
      return;
    }}
    techLastAppliedSeq = seq;
   }}
   if (t === "testing_snapshot") {{
    const results = Array.isArray(payload?.results) ? payload.results : [];
    let applied = 0;
    for (const rec of results) {{
     const targetKey = String(rec?.targetKey || "");
     if (!targetKey) continue;
     const outcome = String(rec?.outcome || "").toUpperCase();
     const at = String(rec?.recordedAtUtc || rec?.lastTestedAtUtc || rec?.tsUtc || "");
     statusByTargetKey.set(targetKey, {{ outcome, recordedAtUtc: at }});
     const rowUi = rowStatusByTargetKey.get(targetKey);
     if (rowUi) {{
      setRowStatus(rowUi, outcome, at);
      applied += 1;
     }}
    }}
    _logTechWs("snapshot:applied", {{ total: results.length, applied }});
    return;
   }}
   if (t !== "test_result.recorded" && t !== "test_result") return;
   const targetKey = String(payload?.targetKey || payload?.target?.targetKey || "");
   if (!targetKey) return;
   const outcome = String(payload?.outcome || payload?.currentOutcome || "").toUpperCase();
   const at = String(payload?.recordedAtUtc || payload?.lastTestedAtUtc || payload?.tsUtc || "");
   statusByTargetKey.set(targetKey, {{ outcome, recordedAtUtc: at }});
   const rowUi = rowStatusByTargetKey.get(targetKey);
   if (rowUi) {{
    setRowStatus(rowUi, outcome, at);
   }}
    if (pendingTargetKey && pendingTargetKey === targetKey) {{
     _logTechWs("ack-match", targetKey);
     pendingTargetKey = null;
     setPosting(false);
      setPostStatus("", "");
     drainPassAllQueue();
    }} else if (pendingTargetKey) {{
     _logTechWs("ack-miss", {{ pending: pendingTargetKey, received: targetKey }});
    }}
 }}
 function _handleTechWsMessage(evt) {{
  try {{
   const payload = JSON.parse(String(evt.data || "{{}}"));
   _applyTechPayload(payload);
  }} catch (_e) {{}}
 }}
 function _connectTechWs() {{
  const techToken = techTokenFromLocation();
  if (!techToken) return;
  if (techWs && techWsToken === techToken) return;
  if (techWs) {{
   try {{ techWs.close(); }} catch (_e) {{}}
  }}
  techWsToken = techToken;
  techLastAppliedSeq = 0;
  _logTechWs("connect", techToken);
  const ws = new WebSocket(techWsUrl(`/api/v1/testing/${{encodeURIComponent(techToken)}}/ws`));
  techWs = ws;
  ws.onopen = () => {{ techWsReconnectDelayMs = 500; _logTechWs("open"); _sendTechSyncRequest(); }};
  ws.onclose = () => {{
   techWs = null;
   _logTechWs("close");
   _scheduleTechWsReconnect();
  }};
  ws.onerror = () => {{
   _logTechWs("error");
   try {{ if (techWs) techWs.close(); }} catch (_e) {{}}
  }};
  ws.onmessage = _handleTechWsMessage;
 }}
 function _sendTechWs(payload) {{
  if (!techWs || techWs.readyState !== 1) {{
   _connectTechWs();
  }}
    if (!techWs || techWs.readyState !== 1) {{
     _logTechWs("send-abort:not-open", techWs ? techWs.readyState : "null");
     setPosting(false);
     if (pendingTargetKey) setRowInlineError(pendingTargetKey, "websocket not connected");
     setPostStatus("", "");
     return;
    }}
  _logTechWs("send", payload?.type || "");
  techWs.send(JSON.stringify(payload));
 }}
 function formatLastTestUtc(ts) {{
  const raw = String(ts || "").trim();
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  const pad2 = (n) => String(n).padStart(2, "0");
  const yyyy = d.getUTCFullYear();
  const mm = pad2(d.getUTCMonth() + 1);
  const dd = pad2(d.getUTCDate());
  const hh = pad2(d.getUTCHours());
  const mi = pad2(d.getUTCMinutes());
  const ss = pad2(d.getUTCSeconds());
  return `${{yyyy}}-${{mm}}-${{dd}} ${{hh}}:${{mi}}:${{ss}}Z`;
 }}
 function setRowStatus(rowUi, outcome, recordedAtUtc) {{
  if (!rowUi) return;
  const o = String(outcome || "").trim().toUpperCase();
  const at = formatLastTestUtc(recordedAtUtc);
  if (rowUi.passBtn) rowUi.passBtn.classList.toggle("is-pass-active", o === "PASS");
  if (rowUi.failBtn) rowUi.failBtn.classList.toggle("is-fail-active", o === "FAIL");
  if (rowUi.lastTestEl) rowUi.lastTestEl.textContent = at ? `Last Test: ${{at}}` : "";
 }}
 function applyCachedStatus(rowUi, targetKey) {{
  if (!rowUi) return;
  const key = String(targetKey || "").trim();
  if (!key) return;
  const rec = statusByTargetKey.get(key);
  if (!rec) return;
  const outcome = String(rec.outcome || "").toUpperCase();
  const at = String(rec.recordedAtUtc || "");
  setRowStatus(rowUi, outcome, at);
 }}
function buildTargetPayload(ctxBtn, meta, targetLabel) {{
  const m = (meta && typeof meta === "object") ? meta : {{}};
  const label = String(targetLabel || "").trim();
  const kind = String(m.kind || "").trim().toUpperCase();
  const refs = (m.refs && typeof m.refs === "object") ? {{...m.refs}} : {{}};
  if (kind === "EVENT") {{
   const eventId = refs.eventId;
   if (eventId == null) return null;
   const targetKey = `event:${{eventId}}:${{label || "Trigger"}}`;
   return {{
    targetKey,
    kind: "EVENT",
    targetName: label || String(m.identity || "").trim(),
    refs
   }};
  }}
  const btn = ctxBtn || null;
  const wrap = btn && btn.closest ? btn.closest(".btn-wrap") : null;
  const deviceId = wrap && wrap.dataset ? wrap.dataset.diagDeviceId : null;
  const pageIndexRaw = (wrap && wrap.dataset && wrap.dataset.pageIndex != null) ? wrap.dataset.pageIndex : null;
  const pageIndexRawResolved = pageIndexRaw != null ? pageIndexRaw : (wrap && wrap.closest ? (wrap.closest(".device-page") || {{}}).dataset?.pageIndex : null);
  const pageIndex = pageIndexRawResolved == null ? null : Number(pageIndexRawResolved);
  const pageState = (pageIndex != null && Array.isArray(PAGE_STATE)) ? PAGE_STATE[pageIndex] : null;
  const pageId = pageState && pageState.pageId != null ? pageState.pageId : null;
  const vpButtonId = wrap && wrap.dataset ? wrap.dataset.diagViewportButtonId : null;
  const buttonId = wrap && wrap.dataset ? wrap.dataset.diagButtonId : null;
  const buttonTag = wrap && wrap.dataset ? wrap.dataset.buttonTag : "";
  const categoryName = String(m.category || "").trim();
  const buttonName = String(m.identity || "").trim();
  const targetName = String(label || "").trim() || buttonName || categoryName;
  const keyToken = String(label || "").trim() || categoryName || buttonName || "Button";
  const scope = vpButtonId ? "VIEWPORT_BUTTON" : "BUTTON";
  if (deviceId != null) refs.deviceId = Number(deviceId);
  if (pageId != null) refs.pageId = pageId;
  if (buttonId != null) refs.buttonId = Number(buttonId);
  if (vpButtonId != null) refs.viewportButtonId = Number(vpButtonId);
  if (buttonTag) refs.buttonTag = buttonTag;
  if (pageState && pageState.deviceName) refs.deviceName = String(pageState.deviceName || "");
  if (pageState && pageState.pageName) refs.pageName = String(pageState.pageName || "");
  if (buttonName) refs.buttonName = buttonName;
  const ownerLayerName = wrap && wrap.dataset ? String(wrap.dataset.ownerLayerName || "").trim() : "";
  const vpLayerName = wrap && wrap.dataset ? String(wrap.dataset.vpLayerName || "").trim() : "";
  const frameRaw = wrap && wrap.dataset ? wrap.dataset.frame : null;
  const frameIndexRti = frameRaw == null ? null : Number(frameRaw);
  if (vpLayerName) refs.layerName = vpLayerName;
  else if (ownerLayerName) refs.layerName = ownerLayerName;
  const effectiveRoomName = wrap && wrap.dataset ? String(wrap.dataset.effectiveRoomName || "").trim() : "";
  const effectiveSourceName = wrap && wrap.dataset ? String(wrap.dataset.effectiveSourceName || "").trim() : "";
  const effectiveScopeNames = wrap && wrap.dataset ? String(wrap.dataset.effectiveScopeNames || "").trim() : "";
  if (effectiveRoomName) refs.effectiveRoomName = effectiveRoomName;
  if (effectiveSourceName) refs.effectiveSourceName = effectiveSourceName;
  if (effectiveScopeNames) refs.effectiveScopeNames = effectiveScopeNames;
  if (vpButtonId != null && frameIndexRti != null && Number.isFinite(frameIndexRti)) {{
   refs.frameIndexRti = Number(frameIndexRti);
   refs.viewport = `Frame ${{Number(frameIndexRti) + 1}}`;
  }} else {{
   refs.viewport = "No";
  }}
  refs.scope = scope;
  const apexScopeSource = (m.apexScopeSource && typeof m.apexScopeSource === "object") ? m.apexScopeSource : null;
  if (apexScopeSource) {{
   refs.apexScopeSource = apexScopeSource;
   const pageScope = (apexScopeSource.page && typeof apexScopeSource.page === "object") ? apexScopeSource.page : {{}};
   const viewportLayerScope = (apexScopeSource.viewportLayer && typeof apexScopeSource.viewportLayer === "object")
    ? apexScopeSource.viewportLayer
    : ((apexScopeSource.layer && typeof apexScopeSource.layer === "object") ? apexScopeSource.layer : {{}});
   const pageLayerScope = (apexScopeSource.pageLayer && typeof apexScopeSource.pageLayer === "object") ? apexScopeSource.pageLayer : {{}};
   const buttonScope = (apexScopeSource.button && typeof apexScopeSource.button === "object") ? apexScopeSource.button : {{}};
   const bindings = (apexScopeSource.bindings && typeof apexScopeSource.bindings === "object") ? apexScopeSource.bindings : {{}};
   const rtiAddress = pageScope.rtiAddress;
   const pageRoomId = pageScope.roomId;
   const pageSourceDeviceId = pageScope.sourceDeviceId;
   const viewportLayerRoomId = viewportLayerScope.roomId;
   const viewportLayerSourceId = viewportLayerScope.sourceId;
   const pageLayerRoomId = pageLayerScope.roomId;
   const pageLayerSourceId = pageLayerScope.sourceId;
   const effectiveRoomId = viewportLayerRoomId != null
    ? Number(viewportLayerRoomId)
    : (pageLayerRoomId != null ? Number(pageLayerRoomId) : (pageRoomId != null ? Number(pageRoomId) : null));
   const effectiveSourceId = viewportLayerSourceId != null
    ? Number(viewportLayerSourceId)
    : (pageLayerSourceId != null ? Number(pageLayerSourceId) : (pageSourceDeviceId != null ? Number(pageSourceDeviceId) : null));
   const buttonTagId = buttonScope.buttonTagId;
   const scopedButtonId = buttonScope.buttonId;
   const macroIds = Array.isArray(bindings.macroIds) ? bindings.macroIds : [];
   const variableIds = Array.isArray(bindings.variableIds) ? bindings.variableIds : [];
   const macroStepIds = Array.isArray(bindings.macroStepIds) ? bindings.macroStepIds : [];
   const lowerLabel = String(keyToken || "").trim().toLowerCase();
   if (buttonTagId != null) {{
    let programRef = "none";
    const firstMacroId = macroIds.length ? Number(macroIds[0]) : null;
    const firstVarId = variableIds.length ? Number(variableIds[0]) : null;
    const firstMacroStepId = macroStepIds.length ? Number(macroStepIds[0]) : null;
    if (lowerLabel === "macro" || lowerLabel === "macros") {{
     if (firstMacroId != null && Number.isFinite(firstMacroId)) programRef = `macro:${{firstMacroId}}`;
    }} else if (lowerLabel === "macrostep" || lowerLabel === "macrosteps") {{
     if (firstMacroId != null && Number.isFinite(firstMacroId)) {{
      if (firstMacroStepId != null && Number.isFinite(firstMacroStepId)) {{
       programRef = `mstep:${{firstMacroId}}:${{firstMacroStepId}}`;
      }} else {{
       programRef = `mstepmacro:${{firstMacroId}}`;
      }}
     }}
    }} else if (lowerLabel.startsWith("variable - ") || lowerLabel.startsWith("var.")) {{
     if (firstVarId != null && Number.isFinite(firstVarId)) programRef = `var:${{firstVarId}}`;
    }}
    const scopeType = Number(effectiveRoomId || 0) === 0 ? "GLOBAL" : "ROOM";
    refs.scopeType = scopeType;
    refs.effectiveRoomId = effectiveRoomId;
    refs.effectiveSourceId = effectiveSourceId;
    refs.programRef = programRef;
    if (rtiAddress != null && effectiveRoomId != null && effectiveSourceId != null) {{
     const targetKey = `tt2:${{Number(rtiAddress)}}:${{scopeType}}:${{Number(effectiveRoomId)}}:${{Number(effectiveSourceId)}}:${{Number(buttonTagId)}}:${{programRef}}:${{keyToken}}`;
     return {{
      targetKey,
      kind: scope,
      targetName,
      refs
     }};
    }}
   }} else {{
    const sharedLayerId = viewportLayerScope.sharedLayerId;
    const layerId = viewportLayerScope.layerId;
    const sharedFlag = sharedLayerId != null ? "SHARED" : "LOCAL";
    const scopeLayerId = sharedLayerId != null ? Number(sharedLayerId) : (layerId != null ? Number(layerId) : null);
    refs.sharedFlag = sharedFlag;
    refs.scopeLayerId = scopeLayerId;
    if (rtiAddress != null && scopeLayerId != null && scopedButtonId != null) {{
     const targetKey = `tt_ui:${{Number(rtiAddress)}}:${{sharedFlag}}:${{scopeLayerId}}:${{Number(scopedButtonId)}}:${{keyToken}}`;
     return {{
      targetKey,
      kind: scope,
      targetName,
      refs
     }};
    }}
   }}
  }}
  let targetKey = "";
  if (vpButtonId && deviceId != null && pageId != null && buttonId != null) {{
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{buttonId}}:${{keyToken}}`;
  }} else if (vpButtonId && deviceId != null && pageId != null) {{
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{keyToken}}`;
  }} else if (deviceId != null && pageId != null && buttonId != null) {{
   targetKey = `btn:${{deviceId}}:${{pageId}}:${{buttonId}}:${{keyToken}}`;
  }} else {{
   targetKey = `btn:${{keyToken}}`;
  }}
  return {{
   targetKey,
   kind: scope,
   targetName,
   refs
  }};
 }}
 function esc(s){{return String(s == null ? '' : s).replace(/[&<>\"]/g,function(m){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[m];}});}}
 function setPostStatus(text, kind) {{
  if (!postStatus) return;
  const t=String(text||'').trim();
  postStatus.textContent=t;
  postStatus.className='post-status' + (kind ? (' is-' + kind) : '');
  if (t) postStatus.removeAttribute('hidden'); else postStatus.setAttribute('hidden','hidden');
 }}
 function setRowInlineError(targetKey, message) {{
  const key = String(targetKey || "").trim();
  const rowUi = rowStatusByTargetKey.get(key);
  if (!rowUi || !rowUi.lastTestEl) return;
  rowUi.lastTestEl.textContent = `Error: ${{String(message || "").trim()}}`;
 }}
 function clearPassAllQueue() {{
  passAllQueue = [];
  passAllContext = null;
 }}
 function drainPassAllQueue() {{
  if (isPosting) return;
  if (!passAllQueue.length) {{
   passAllContext = null;
   return;
  }}
  const next = passAllQueue.shift();
  if (!next || !next.label) {{
   drainPassAllQueue();
   return;
  }}
  const ctx = passAllContext || {{ ctxBtn: null, meta: {{}} }};
  postResultWs(ctx.ctxBtn || null, ctx.meta || {{}}, next.label, "PASS", null, next.rowUi || null);
  if (!passAllQueue.length) passAllContext = null;
 }}
 function queuePassAll(ctxBtn, meta) {{
  clearPassAllQueue();
  rows.querySelectorAll('.row').forEach(function(row){{
   const label = String((row.querySelector('.n')||{{}}).textContent || '').trim();
   const buttons = row.querySelectorAll('.actions button');
   const rowUi = {{
    passBtn: buttons.length >= 1 ? buttons[0] : null,
    failBtn: buttons.length >= 2 ? buttons[1] : null,
    lastTestEl: row.querySelector('.row-last-test'),
   }};
   if (!label) return;
   passAllQueue.push({{ label, rowUi }});
  }});
  if (!passAllQueue.length) return;
  passAllContext = {{ ctxBtn: ctxBtn || null, meta: (meta && typeof meta === "object") ? meta : {{}} }};
  drainPassAllQueue();
 }}
 function setPosting(on) {{
  isPosting=!!on;
  rows.querySelectorAll('.row').forEach(function(row){{
   const buttons = row.querySelectorAll('.actions button');
   if (buttons.length < 2) return;
   const passBtn = buttons[0];
   const failBtn = buttons[1];
   const noteEl = row.querySelector('textarea');
   passBtn.disabled = isPosting;
   const note = noteEl ? String(noteEl.value || '').trim() : '';
   failBtn.disabled = isPosting || !note;
  }});
  if (passAllBtn) passAllBtn.disabled=isPosting;
  const closeBtn=document.getElementById('close');
  if (closeBtn) closeBtn.disabled=isPosting;
 }}
 function toggleSection(btn) {{
  const targetId = btn ? btn.getAttribute("data-target") : "";
  const section = targetId ? document.getElementById(targetId) : null;
  if (!section) return;
  const isHidden = section.hasAttribute("hidden");
  if (isHidden) section.removeAttribute("hidden");
  else section.setAttribute("hidden", "hidden");
  btn.setAttribute("aria-expanded", isHidden ? "true" : "false");
 }}
 async function postResultWs(ctxBtn, meta, targetLabel, outcome, failNote, rowUi) {{
  const techToken=techTokenFromLocation();
  if (!techToken) {{
   _logTechWs("blocked:no-token");
   return;
  }}
  const target=buildTargetPayload(ctxBtn, meta, targetLabel);
  if (!target) {{
   _logTechWs("blocked:no-target", targetLabel);
   return;
  }}
  const isFail=String(outcome||'').toUpperCase()==='FAIL';
  const note=isFail ? String(failNote||'').trim() : null;
  if (isFail && !note) {{
   _logTechWs("blocked:missing-fail-note", target.targetKey);
   return;
  }}
  if (isPosting) {{
   _logTechWs("blocked:isPosting", {{ pending: pendingTargetKey, targetKey: target.targetKey }});
   return;
  }}

  const payload={{
    type:"test_result.submit",
    target:{{targetKey:target.targetKey,kind:target.kind,refs:target.refs,targetName:target.targetName}},
    outcome:String(outcome||'').toUpperCase(),
    failNote:note
  }};
  _logTechWs("expect", target.targetKey);
  setPosting(true);
  setPostStatus('','');
  pendingTargetKey = target.targetKey;
 if (rowUi) rowStatusByTargetKey.set(target.targetKey, rowUi);
 if (rowUi) setRowStatus(rowUi, payload.outcome, "");
 _sendTechWs(payload);
 }}
 function bindResultRows(meta) {{
  rowStatusByTargetKey.clear();
  rows.querySelectorAll('.row').forEach(function(row){{
   const label=(row.querySelector('.n')||{{}}).textContent||'';
   const buttons=row.querySelectorAll('.actions button');
   if (buttons.length<2) return;
   const passBtn=buttons[0];
   const failBtn=buttons[1];
   const noteEl=row.querySelector('textarea');
   const rowUi={{ passBtn: passBtn, failBtn: failBtn, lastTestEl: row.querySelector('.row-last-test') }};
   function syncFailEnabled() {{
    const note=noteEl ? String(noteEl.value||'').trim() : '';
    if (!isPosting) failBtn.disabled = !note;
    }}
   if (noteEl) noteEl.addEventListener('input', syncFailEnabled);
   syncFailEnabled();
   const target = buildTargetPayload(null, meta, label);
   if (target?.targetKey) {{
    rowStatusByTargetKey.set(target.targetKey, rowUi);
    applyCachedStatus(rowUi, target.targetKey);
   }}
   passBtn.addEventListener('click', function(e){{e.stopPropagation(); postResultWs(null, meta, label, 'PASS', null, rowUi);}});
   failBtn.addEventListener('click', function(e){{e.stopPropagation(); postResultWs(null, meta, label, 'FAIL', noteEl ? noteEl.value : '', rowUi);}});
  }});
 }}
 Array.prototype.forEach.call(document.querySelectorAll('.test-btn'), function(b){{
  b.addEventListener('click', function(){{
   const m=JSON.parse(b.getAttribute('data-meta')||'{{}}');
   const popupCfg=(APP_UI && APP_UI.testingPopup) ? APP_UI.testingPopup : {{}};
   const suffix=(popupCfg.includeButtonTypeInTitle && m.buttonType)?(' (' + m.buttonType + ')'):'';
   const titleTemplate=popupCfg.titleTemplate || '{{category}} Test - {{identity}}';
   pt.textContent=titleTemplate.replace('{{category}}',m.category).replace('{{identity}}',m.identity)+suffix;
   const targets=Array.isArray(m.targets) ? m.targets : [];
    rows.innerHTML=targets.map(function(t){{return "<div class='row'><div class='row-head'><div class='n'>" + esc(t) + "</div></div><div class='row-meta'><div class='actions'><button>Pass</button><button disabled title='Enter a fail note to enable'>Fail</button></div><div class='row-last-test' aria-live='polite'></div></div><textarea placeholder='Fail note (required for Fail)' style='min-height:70px;'></textarea></div>";}}).join('') || "<div class='row'><div class='n'>No true test targets.</div></div>";
    clearPassAllQueue();
    setPostStatus('','');
    if (passAllBtn) {{
     passAllBtn.disabled = !targets.length;
     passAllBtn.onclick = function(){{ queuePassAll(null, m); }};
    }}
    ov.classList.add('open');
   bindResultRows(m);
  }});
 }});
_connectTechWs();
document.getElementById('close').addEventListener('click', function(){{ clearPassAllQueue(); ov.classList.remove('open'); }});
ov.addEventListener('click', function(e){{if(e.target===ov){{ clearPassAllQueue(); ov.classList.remove('open'); }}}});
</script></body></html>"""
def build_device_render_bundle(
    project_data: dict[str, Any],
    app_ui: dict[str, Any],
    project_stem: str,
    device_index: int = 0,
    resolved_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    device = project_data["devices"][device_index]
    uf = device["userFacing"]
    device_ui = uf.get("deviceUI", {})
    portrait = device_ui.get("portrait", {})
    landscape = device_ui.get("landscape", {})
    portrait_resolution = _resolution_or_default(portrait.get("resolution"), 480, 854)
    landscape_resolution = _resolution_or_default(landscape.get("resolution"), 854, 480)
    if bool(portrait.get("supported")):
        res = portrait_resolution
        active_orientation = "portrait"
    elif bool(landscape.get("supported")):
        res = landscape_resolution
        active_orientation = "landscape"
    else:
        res = portrait_resolution if any(int(portrait_resolution.get(k) or 0) > 0 for k in ("width", "height")) else landscape_resolution
        active_orientation = "portrait"
    w = int(res.get("width") or 480)
    h = int(res.get("height") or 854)
    orientation_options = [name for name, cfg in (("portrait", portrait), ("landscape", landscape)) if bool(cfg.get("supported"))]
    show_orientation_toggle = len(orientation_options) > 1
    orientation_state = {
        "current": active_orientation,
        "options": orientation_options,
        "sizes": {
            "portrait": portrait_resolution,
            "landscape": landscape_resolution,
        },
    }
    pages = uf.get("pages", [])
    title = app_ui.get("header", {}).get("titleTemplate", "{deviceName} - {pageName}")
    first_page_name = str(pages[0].get("pageName", "")) if pages else ""
    header = title.replace("{deviceName}", uf.get("displayName", "")).replace("{pageName}", first_page_name)
    diag_pages = device.get("diagnostics", {}).get("pages", [])

    page_html_by_index: dict[str, str] = {}
    page_state: list[dict[str, Any]] = []
    page_payloads: list[dict[str, Any]] = []
    for page_index, _page in enumerate(pages):
        payload = _page_payload(project_data, app_ui, project_stem, device_index, page_index, active_orientation, resolved_targets)
        page_payloads.append(payload)
        diag_page_id = diag_pages[page_index].get("pageId") if page_index < len(diag_pages) else None
        page_html_by_index[str(page_index)] = f"{payload['viewport_boxes']}{payload['page_button_rows']}{payload['viewport_button_rows']}"
        page_state.append(
            {
                "deviceName": uf.get("displayName", ""),
                "pageName": payload["page_name"],
                "pageId": diag_page_id,
                "layers": payload.get("layers", []),
                "vpFrames": payload["vp_frames"],
            }
        )
    first_page_inner = page_html_by_index.get("0", "")
    initial_page_markup = f"<div class='device-page active' data-page-index='0'>{first_page_inner}</div>" if pages else ""
    html = _render_document(
        app_ui,
        header,
        w,
        h,
        initial_page_markup,
        json.dumps(page_html_by_index),
        json.dumps(page_state),
        project_stem,
        json.dumps(orientation_state),
        show_orientation_toggle,
        home_href=project_home_filename(project_stem),
    )
    payload_doc_pages: list[dict[str, Any]] = []
    for page_index, payload in enumerate(page_payloads):
        diag_page = diag_pages[page_index] if isinstance(diag_pages, list) and page_index < len(diag_pages) else {}
        payload_doc_pages.append(
            {
                "pageName": payload.get("page_name", ""),
                "pageIndex": int(payload.get("page_index", page_index)),
                "pageId": diag_page.get("pageId") if isinstance(diag_page, dict) else None,
                "layers": payload.get("layers", []),
                "vpFrames": payload.get("vp_frames", []),
            }
        )
    payload_doc = {
        "format": "sentinel-testing-payload-v1",
        "projectStem": project_stem,
        "deviceIndex": int(device_index),
        "deviceName": str(uf.get("displayName", f"device-{device_index}")),
        "deviceUI": device_ui,
        "orientationState": {
            "current": active_orientation,
            "options": orientation_options,
            "sizes": {"portrait": portrait_resolution, "landscape": landscape_resolution},
        },
        "pages": payload_doc_pages,
    }
    return {"html": html, "payload": payload_doc}


def render_single_device_html(
    project_data: dict[str, Any],
    app_ui: dict[str, Any],
    project_stem: str,
    device_index: int = 0,
    resolved_targets: dict[str, Any] | None = None,
) -> str:
    bundle = build_device_render_bundle(
        project_data,
        app_ui,
        project_stem,
        device_index=device_index,
        resolved_targets=resolved_targets,
    )
    return str(bundle.get("html") or "")


def build_device_payload(
    project_data: dict[str, Any],
    app_ui: dict[str, Any],
    project_stem: str,
    device_index: int = 0,
    resolved_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = build_device_render_bundle(
        project_data,
        app_ui,
        project_stem,
        device_index=device_index,
        resolved_targets=resolved_targets,
    )
    payload = bundle.get("payload")
    return payload if isinstance(payload, dict) else {}


def build_project_manifest(project_data: dict[str, Any], project_stem: str) -> dict[str, Any]:
    source = project_data.get("source", {})
    devices = project_data.get("devices", [])
    manifest_devices: list[dict[str, Any]] = []
    for device_index, device in enumerate(devices):
        user = device.get("userFacing", {})
        pages = user.get("pages", [])
        if not isinstance(pages, list) or not pages:
            continue
        device_name = str(user.get("displayName", f"device-{device_index}"))
        manifest_devices.append(
            {
                "deviceIndex": int(device_index),
                "deviceName": device_name,
                "pageCount": len(pages),
                "htmlFile": device_filename(project_stem, device_name, device_index),
                "payloadFile": device_payload_filename(project_stem, device_name, device_index),
            }
        )
    return {
        "format": "sentinel-testing-payload-v1",
        "projectStem": project_stem,
        "projectHomeHtml": project_home_filename(project_stem),
        "source": source,
        "devices": manifest_devices,
    }
