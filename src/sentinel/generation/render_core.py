from __future__ import annotations

from html import escape
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


_SENTINEL_UI_DIR = Path(__file__).resolve().parent.parent / "ui"


def _sentinel_test_status_embed_js() -> str:
    return (_SENTINEL_UI_DIR / "testing" / "sentinel_test_status_embed.js").read_text(encoding="utf-8")


def _sentinel_device_theme_css() -> str:
    return (_SENTINEL_UI_DIR / "testing" / "sentinel_device_theme.css").read_text(encoding="utf-8")


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


def _button_identity_label(btn: dict[str, Any]) -> str:
    identity = btn.get("buttonIdentity", {}) if isinstance(btn, dict) else {}
    value = _btn_text(identity if isinstance(identity, dict) else {})
    if value:
        return value
    targets = btn.get("testTargets", {}) if isinstance(btn, dict) else {}
    graphics = targets.get("graphics", {}) if isinstance(targets, dict) else {}
    has_graphics = bool(graphics.get("bitmap")) or bool(graphics.get("icon"))
    return "Graphics" if has_graphics else ""


def _page_link_enabled(targets: dict[str, Any]) -> bool:
    page_link = targets.get("pageLink")
    if isinstance(page_link, dict):
        return bool(page_link.get("enabled"))
    return bool(page_link)


def _page_link_target_id(btn: dict[str, Any], *, rendering_page_id: int | None = None) -> int | None:
    resolved = btn.get("resolvedPageLink")
    if not isinstance(resolved, dict):
        return None
    if resolved.get("resolutionPath") == "nextInGroup":
        ids = resolved.get("groupPageIds")
        if not isinstance(ids, list) or len(ids) < 2:
            return None
        gids = [int(x) for x in ids]
        cur = int(rendering_page_id) if rendering_page_id is not None else int(resolved.get("anchorPageId") or 0)
        if cur not in gids:
            return None
        i = gids.index(cur)
        return int(gids[(i + 1) % len(gids)])
    raw = resolved.get("targetPageId")
    return int(raw) if raw is not None else None


def _page_link_resolved_room_id(btn: dict[str, Any]) -> int | None:
    resolved = btn.get("resolvedPageLink")
    if isinstance(resolved, dict):
        raw = resolved.get("resolvedRoomId")
        if raw is not None:
            try:
                rid = int(raw)
                if rid > 0:
                    return rid
            except (TypeError, ValueError):
                return None
    return None


def _page_link_markup(
    btn: dict[str, Any],
    app_ui: dict[str, Any],
    page_targets: dict[int, str],
    page_target_indexes: dict[int, int] | None,
    *,
    rendering_page_id: int | None = None,
) -> str:
    """Anchor + icon for resolved page links (shared by touchscreen and hard-key buttons)."""
    targets = btn.get("testTargets", {}) if isinstance(btn, dict) else {}
    link_cfg = app_ui.get("appNavigation", {}).get("pageLinks", {})
    if not link_cfg.get("enabled") or not _page_link_enabled(targets):
        return ""
    target_page_id = _page_link_target_id(btn, rendering_page_id=rendering_page_id)
    resolved_room_id = _page_link_resolved_room_id(btn)
    target_href = page_targets.get(target_page_id) if target_page_id is not None else None
    if not target_href:
        return ""
    nav_width = int(link_cfg.get("hoverActivationArea", {}).get("width") or 28)
    nav_pad = int(link_cfg.get("iconPaddingRight") or 8)
    icon_size = int(link_cfg.get("iconSize") or 16)
    icon = "<span class='material-symbols-outlined' aria-hidden='true'>link_2</span>"
    page_index_attr = ""
    if target_page_id is not None and page_target_indexes and target_page_id in page_target_indexes:
        page_index_attr = f" data-target-page-index='{page_target_indexes[target_page_id]}'"
    resolved_room_attr = f" data-resolved-room-id='{int(resolved_room_id)}'" if resolved_room_id is not None else ""
    return (
        f"<a class='page-link-hit' href='{target_href}' aria-label='Open linked page' "
        f"data-hit-width='{nav_width}' data-hit-padding='{nav_pad}'{page_index_attr}{resolved_room_attr}>"
        f"<span class='page-link-icon' data-icon-size='{icon_size}'>{icon}</span></a>"
    )


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
        out.append("System Macro")
    if t.get("macroSteps"):
        out.append("Macro Step")
    for name in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List"):
        if vars_t.get(name):
            out.append(variable_label_template.replace("{variableType}", name))
    if graphics_t.get("bitmap"):
        out.append("Bitmap")
    if graphics_t.get("icon"):
        out.append("Icon")
    if _page_link_enabled(t):
        out.append("Page Link")
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
        return [{"key": _layer_key(0), "name": "Page Layer", "layerOrder": 0, "sharedLayerId": None}]
    out: list[dict[str, Any]] = []
    for index, layer in enumerate(layers):
        name = str(layer.get("layerName") or "").strip() or f"Layer {index + 1}"
        shared_layer_id: int | None = None
        raw_shared_layer_id = layer.get("sharedLayerId")
        if raw_shared_layer_id is not None:
            try:
                parsed_shared_layer_id = int(raw_shared_layer_id)
            except Exception:
                parsed_shared_layer_id = 0
            if parsed_shared_layer_id > 0:
                shared_layer_id = parsed_shared_layer_id
        out.append(
            {
                "key": _layer_key(index),
                "name": name,
                "layerOrder": int(layer.get("layerOrder", 0) or 0),
                "sharedLayerId": shared_layer_id,
            }
        )
    return sorted(out, key=lambda layer: (-int(layer.get("layerOrder", 0) or 0), str(layer.get("name") or "")))


def _button_stack_sort_key(btn: dict[str, Any], category_rank: int) -> tuple[int, int, int]:
    stack = ((btn.get("buttonUI") or {}).get("stack") or {}) if isinstance(btn, dict) else {}
    button_order = int(stack.get("buttonOrder", 0) or 0)
    frame_number = int(stack.get("frameNumber", 0) or 0)
    return (button_order, frame_number, category_rank)


# Within-layer buttonOrder must stay below this band so a higher layerOrder always
# produces a higher composite z than any button on a lower layer (no "band overflow").
_Z_LAYER_BAND = 1_000_000
_Z_BASE_OFFSET = 1_000_000
_Z_SAFE_MAX = 2_000_000_000
# Buttons use _composite_z_index (capped at _Z_SAFE_MAX). Overlay must sit above all RTI buttons.
_Z_VP_OVERLAY = _Z_SAFE_MAX + 1
_Z_VP_FOCUS = _Z_SAFE_MAX + 2
# Viewport frame hit targets must paint above same-layer buttons (see btn_cap in _composite_z_index).
_VP_BOX_BUTTON_ORDER = _Z_LAYER_BAND - 250


def _composite_z_index(layer_order: int, button_order: int, frame_number: int = 0, tie_breaker: int = 0) -> int:
    # layerOrder is authoritative between layers; buttonOrder only competes inside a layer.
    layer = int(layer_order)
    button = int(button_order)
    frame = int(frame_number)
    btn_cap = _Z_LAYER_BAND - 200
    button = min(max(0, button), btn_cap)
    z = _Z_BASE_OFFSET + (layer * _Z_LAYER_BAND) + button + (frame * 2) + (1 if int(tie_breaker) > 0 else 0)
    return min(z, _Z_SAFE_MAX)


def _viewport_box_z_index(layer_order: int, vp_index: int) -> int:
    """Z for dashed viewport rectangles: top of layer band so clicks beat overlapping same-layer controls."""
    return _composite_z_index(layer_order, _VP_BOX_BUTTON_ORDER, vp_index)


def _button_composite_z_index(
    btn: dict[str, Any],
    *,
    fallback_layer_order: int = 0,
    fallback_frame_number: int = 0,
    tie_breaker: int = 0,
) -> int:
    stack = ((btn.get("buttonUI") or {}).get("stack") or {}) if isinstance(btn, dict) else {}
    # Canonical page z-layering comes from owning layer context, not stack.layerOrder.
    layer_order = int(fallback_layer_order)
    button_order = int(stack.get("buttonOrder", 0) or 0)
    frame_number = int(stack.get("frameNumber", fallback_frame_number) or fallback_frame_number)
    return _composite_z_index(layer_order, button_order, frame_number, tie_breaker=tie_breaker)


def _viewport_child_composite_z_index(
    *,
    owner_layer_order: int,
    vp_layer_order: int,
    button_order: int,
    frame_number: int,
) -> int:
    """Viewport child z that preserves layer bands and keeps vp-box on top.

    Viewport children must never leap outside their owning page layer band, and must
    remain below the viewport hit/surface cap so `.vp-box` keeps click capture/signifier
    behavior in normal mode.
    """
    layer = int(owner_layer_order)
    vp_layer = max(0, int(vp_layer_order))
    btn = max(0, int(button_order))
    frame = int(frame_number)

    # Pack viewport layer + button order into the within-layer lane, then clamp below
    # the viewport box cap to preserve `.vp-box` precedence.
    packed_within_layer = (vp_layer * 10_000) + min(btn, 9_999)
    packed_within_layer = min(packed_within_layer, max(0, _VP_BOX_BUTTON_ORDER - 2))
    return _composite_z_index(layer, packed_within_layer, frame, tie_breaker=1)


def _iter_page_buttons(page: dict[str, Any]) -> list[tuple[dict[str, Any], str, int, int, str, int]]:
    items: list[tuple[dict[str, Any], str, int, int, str, int]] = []
    category_defs: list[tuple[str, str]] = [
        ("screenLabels", "Screen Label"),
        ("screenButtons", "Screen Button"),
        ("hardButtons", "Hard Button"),
        ("emptyTag", "Empty Tag"),
        ("uiItems", "UI Item"),
    ]
    layers = _page_layers(page)
    if layers:
        for layer_index, layer in enumerate(layers):
            if layer.get("isKeypadLayer"):
                continue
            layer_key = _layer_key(layer_index)
            layer_order = int(layer.get("layerOrder", 0) or 0)
            cats = layer.get("buttonCategories", {})
            layer_items: list[tuple[dict[str, Any], str, int]] = []
            for rank, (cat, label) in enumerate(category_defs):
                for btn in cats.get(cat, []):
                    if cat not in ("uiItems", "emptyTag") and _is_ui_only_button(btn):
                        continue
                    layer_items.append((btn, label, rank))
            layer_items.sort(key=lambda item: _button_stack_sort_key(item[0], item[2]))
            for btn, label, _rank in layer_items:
                items.append((btn, label, 0, 0, layer_key, layer_order))
        return items
    root_items: list[tuple[dict[str, Any], str, int]] = []
    for rank, (cat, label) in enumerate(category_defs):
        for btn in page.get("buttonCategories", {}).get(cat, []):
            if cat not in ("uiItems", "emptyTag") and _is_ui_only_button(btn):
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
                    ("emptyTag", "Empty Tag"),
                    ("uiItems", "UI Item"),
                )
            ):
                for btn in cats.get(cat, []):
                    if cat not in ("uiItems", "emptyTag") and _is_ui_only_button(btn):
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


_HARD_KEY_TEMPLATE_CACHE: dict[str, tuple[str, str]] = {}


def clear_hard_key_template_cache() -> None:
    """Testing hook: templates are cached on disk reads; clear between fixture edits."""

    _HARD_KEY_TEMPLATE_CACHE.clear()


def _hard_key_strip_width_for_height(touch_h: int, hk_design_w: int, hk_design_h: int) -> int:
    if hk_design_h <= 0:
        return 1
    return max(1, int(round(hk_design_w * touch_h / hk_design_h)))


def _hard_key_layout_display_height(
    touch_w: int,
    touch_h: int,
    hk_design_w: int,
    hk_design_h: int,
) -> int:
    """Logical device height for contain scaling when the strip is width-matched to touch."""
    if touch_h <= 0:
        return 1
    if touch_w <= 0 or hk_design_w <= 0 or hk_design_h <= 0:
        return max(1, int(touch_h))
    strip_h_at_touch_w = max(1, int(round(touch_w * hk_design_h / hk_design_w)))
    return max(int(touch_h), strip_h_at_touch_w)


def _contain_scale(
    intrinsic_w: float,
    intrinsic_h: float,
    fit_w: float,
    fit_h: float,
) -> float:
    """Uniform scale so intrinsic rect fits inside fit_w x fit_h (aspect preserved)."""
    iw = float(intrinsic_w)
    ih = float(intrinsic_h)
    fw = float(fit_w)
    fh = float(fit_h)
    if iw <= 0 or ih <= 0 or fw <= 0 or fh <= 0:
        return 0.0
    return max(0.0, min(fw / iw, fh / ih))


def _layout_touchscreen_device(
    usable_w: int,
    usable_h: int,
    touch_w: int,
    touch_h: int,
    *,
    margin: int = 20,
) -> dict[str, float] | None:
    if usable_w <= 0 or usable_h <= 0 or touch_w <= 0 or touch_h <= 0:
        return None
    uw = float(usable_w)
    uh = float(usable_h)
    fit_w = max(1.0, uw - 2.0 * float(margin))
    fit_h = max(1.0, uh - 2.0 * float(margin))
    scale = _contain_scale(touch_w, touch_h, fit_w, fit_h)
    if scale <= 0:
        return None
    width = float(touch_w) * scale
    height = float(touch_h) * scale
    return {
        "scale": scale,
        "left": (uw - width) / 2.0,
        "top": (uh - height) / 2.0,
        "width": width,
        "height": height,
    }


def _layout_hard_key_touch_column(
    usable_w: int,
    usable_h: int,
    touch_w: int,
    touch_h: int,
    *,
    margin: int = 20,
) -> dict[str, float] | None:
    """HK touch column only: contain in half padded width x padded height; center at 25% of usable."""
    if usable_w <= 0 or usable_h <= 0 or touch_w <= 0 or touch_h <= 0:
        return None
    uw = float(usable_w)
    uh = float(usable_h)
    half_w = max(1.0, (uw - 2.0 * float(margin)) / 2.0)
    fit_h = max(1.0, uh - 2.0 * float(margin))
    scale = _contain_scale(float(touch_w), float(touch_h), half_w, fit_h)
    if scale <= 0:
        return None
    width = float(touch_w) * scale
    height = float(touch_h) * scale
    top = max(0.0, (uh - height) / 2.0)
    left = 0.25 * uw - width / 2.0
    return {
        "scale": scale,
        "left": left,
        "top": top,
        "width": width,
        "height": height,
        "centerX": 0.25 * uw,
        "centerY": top + height / 2.0,
    }


def _layout_hard_key_strip_column(
    usable_w: int,
    usable_h: int,
    touch_h: int,
    hk_design_w: int,
    hk_design_h: int,
    touch_column_width: float,
    *,
    margin: int = 20,
) -> dict[str, float] | None:
    """HK strip column: contain in half padded width and padded height; width capped by scaled touch column."""
    if usable_w <= 0 or usable_h <= 0 or touch_h <= 0:
        return None
    if hk_design_w <= 0 or hk_design_h <= 0:
        return None
    touch_col_w = float(touch_column_width)
    if touch_col_w <= 0:
        return None
    uw = float(usable_w)
    uh = float(usable_h)
    th = float(touch_h)
    dw = float(hk_design_w)
    dh = float(hk_design_h)
    half_w = max(1.0, (uw - 2.0 * float(margin)) / 2.0)
    fit_h = max(1.0, uh - 2.0 * float(margin))
    strip_w0 = th * dw / dh
    candidates = [_contain_scale(strip_w0, th, half_w, fit_h)]
    if strip_w0 > 0:
        candidates.append(touch_col_w / strip_w0)
    scale = min(c for c in candidates if c > 0)
    if scale <= 0:
        return None
    height = th * scale
    width = height * dw / dh
    top = max(0.0, (uh - height) / 2.0)
    left = 0.75 * uw - width / 2.0
    return {
        "scale": scale,
        "left": left,
        "top": top,
        "width": width,
        "height": height,
        "centerX": 0.75 * uw,
        "centerY": top + height / 2.0,
    }


def _hard_key_boxes_at_scales(
    usable_w: float,
    usable_h: float,
    touch_w: float,
    touch_h: float,
    hk_design_w: float,
    hk_design_h: float,
    touch_scale: float,
    strip_scale: float,
) -> dict[str, dict[str, float] | float]:
    th_touch = float(touch_h) * float(touch_scale)
    tw_s = float(touch_w) * float(touch_scale)
    strip_th = float(touch_h) * float(strip_scale)
    strip_w = strip_th * float(hk_design_w) / float(hk_design_h)
    touch_left = 0.25 * usable_w - tw_s / 2.0
    hk_left = 0.75 * usable_w - strip_w / 2.0
    touch_top = max(0.0, (float(usable_h) - th_touch) / 2.0)
    strip_top = max(0.0, (float(usable_h) - strip_th) / 2.0)
    touch = {
        "left": touch_left,
        "top": touch_top,
        "width": tw_s,
        "height": th_touch,
        "centerX": 0.25 * usable_w,
        "centerY": touch_top + th_touch / 2.0,
    }
    strip = {
        "left": hk_left,
        "top": strip_top,
        "width": strip_w,
        "height": strip_th,
        "centerX": 0.75 * usable_w,
        "centerY": strip_top + strip_th / 2.0,
    }
    asm_left = min(touch_left, hk_left)
    asm_top = min(touch_top, strip_top)
    asm_right = max(touch_left + tw_s, hk_left + strip_w)
    asm_bottom = max(touch_top + th_touch, strip_top + strip_th)
    assembly = {
        "left": asm_left,
        "top": asm_top,
        "width": asm_right - asm_left,
        "height": asm_bottom - asm_top,
        "centerX": 0.5 * usable_w,
        "centerY": asm_top + (asm_bottom - asm_top) / 2.0,
    }
    return {
        "touchScale": float(touch_scale),
        "stripScale": float(strip_scale),
        "scale": float(strip_scale),
        "touch": touch,
        "strip": strip,
        "assembly": assembly,
    }


def _hard_key_boxes_at_scale(
    usable_w: float,
    usable_h: float,
    touch_w: float,
    touch_h: float,
    hk_design_w: float,
    hk_design_h: float,
    scale: float,
) -> dict[str, dict[str, float] | float]:
    return _hard_key_boxes_at_scales(
        usable_w, usable_h, touch_w, touch_h, hk_design_w, hk_design_h, scale, scale
    )


def _layout_hard_key_split(
    usable_w: int,
    usable_h: int,
    touch_w: int,
    touch_h: int,
    hk_design_w: int,
    hk_design_h: int,
    *,
    margin: int = 20,
) -> dict[str, dict[str, float] | float] | None:
    """Anchor at 25% / 75% of usable width; each zone capped at half the padded usable width."""
    if usable_w <= 0 or usable_h <= 0 or touch_w <= 0 or touch_h <= 0:
        return None
    if hk_design_w <= 0 or hk_design_h <= 0:
        return None
    uw = float(usable_w)
    uh = float(usable_h)
    tw = float(touch_w)
    th = float(touch_h)
    dw = float(hk_design_w)
    dh = float(hk_design_h)
    touch_col = _layout_hard_key_touch_column(
        int(uw), int(uh), int(tw), int(th), margin=margin
    )
    if touch_col is None:
        return None
    touch_scale = float(touch_col["scale"])
    strip_col = _layout_hard_key_strip_column(
        int(uw),
        int(uh),
        int(th),
        int(dw),
        int(dh),
        float(touch_col["width"]),
        margin=margin,
    )
    if strip_col is None:
        return None
    strip_scale = float(strip_col["scale"])
    out = _hard_key_boxes_at_scales(uw, uh, tw, th, dw, dh, touch_scale, strip_scale)
    out["_usableW"] = uw
    out["_usableH"] = uh
    out["_touchW"] = tw
    out["_touchH"] = th
    out["_designW"] = dw
    out["_designH"] = dh
    return out


def _layout_hard_key_split_at_scale(
    layout: dict[str, dict[str, float] | float],
    touch_scale: float,
    strip_scale: float | None = None,
) -> dict[str, dict[str, float] | float]:
    """Recompute box geometry at new touch/strip scales (e.g. after zoom)."""
    uw = float(layout["_usableW"])
    uh = float(layout["_usableH"])
    tw = float(layout["_touchW"])
    th = float(layout["_touchH"])
    dw = float(layout["_designW"])
    dh = float(layout["_designH"])
    ss = float(strip_scale) if strip_scale is not None else float(touch_scale)
    out = _hard_key_boxes_at_scales(uw, uh, tw, th, dw, dh, float(touch_scale), ss)
    out["_usableW"] = uw
    out["_usableH"] = uh
    out["_touchW"] = tw
    out["_touchH"] = th
    out["_designW"] = dw
    out["_designH"] = dh
    return out


def _hard_key_usable_split_layout(
    usable_w: int,
    usable_h: int,
    touch_w: int,
    touch_h: int,
    hk_design_w: int,
    hk_design_h: int,
    *,
    margin: int = 20,
) -> dict[str, float] | None:
    """Backward-compatible flat dict for callers/tests migrating to _layout_hard_key_split."""
    lay = _layout_hard_key_split(
        usable_w, usable_h, touch_w, touch_h, hk_design_w, hk_design_h, margin=margin
    )
    if lay is None:
        return None
    touch = lay["touch"]
    strip = lay["strip"]
    assert isinstance(touch, dict) and isinstance(strip, dict)
    return {
        "scale": float(lay.get("stripScale", lay["scale"])),
        "touchScale": float(lay.get("touchScale", lay["scale"])),
        "stripScale": float(lay.get("stripScale", lay["scale"])),
        "touchLeft": float(touch["left"]),
        "touchTop": float(touch["top"]),
        "touchWidth": float(touch["width"]),
        "touchHeight": float(touch["height"]),
        "touchCenterX": float(touch["centerX"]),
        "hkLeft": float(strip["left"]),
        "hkTop": float(strip["top"]),
        "hkWidth": float(strip["width"]),
        "hkHeight": float(strip["height"]),
        "hkCenterX": float(strip["centerX"]),
        "_usableW": float(usable_w),
        "_usableH": float(usable_h),
        "_touchW": float(touch_w),
        "_touchH": float(touch_h),
        "_designW": float(hk_design_w),
        "_designH": float(hk_design_h),
    }


def _hard_key_quarter_band_layout(
    touch_w0: int,
    touch_h0: int,
    *,
    hk_design_w: int,
    hk_design_h: int,
    gap_design_px: int,
    pad_px: int,
) -> dict[str, int | float] | None:
    """Pad + inner usable width U; touch center at 25% of U, strip center at 75% (hard_keys.md)."""
    if touch_h0 <= 0 or touch_w0 <= 0:
        return None
    virtual_hk_w = _hard_key_strip_width_for_height(touch_h0, hk_design_w, hk_design_h)
    usable_u = max(
        2 * touch_w0,
        2 * virtual_hk_w,
        touch_w0 + virtual_hk_w + 2 * gap_design_px,
    )
    for _ in range(32):
        virtual_w = usable_u + 2 * pad_px
        touch_left = pad_px + int(round(0.25 * usable_u - touch_w0 / 2))
        hk_left = pad_px + int(round(0.75 * usable_u - virtual_hk_w / 2))
        touch_left = max(0, touch_left)
        hk_left = max(0, hk_left)
        max_right = max(touch_left + touch_w0, hk_left + virtual_hk_w)
        if max_right <= pad_px + usable_u:
            vw = max(1, int(virtual_w))
            return {
                "touch_w": touch_w0,
                "touch_h": touch_h0,
                "virtual_hk_w": virtual_hk_w,
                "virtual_w": vw,
                "usable_u": int(usable_u),
                "pad_px": int(pad_px),
                "gap_px": int(gap_design_px),
                "touch_left_px": int(touch_left),
                "hk_left_px": int(hk_left),
                "touch_left_pct": 100.0 * touch_left / vw,
                "touch_width_pct": 100.0 * touch_w0 / vw,
                "hk_left_pct": 100.0 * hk_left / vw,
                "hk_width_pct": 100.0 * virtual_hk_w / vw,
            }
        usable_u += max(8, max_right - (pad_px + usable_u))
    return None


def _hard_key_model_key(device: dict[str, Any]) -> str | None:
    uf = device.get("userFacing") if isinstance(device, dict) else None
    if not isinstance(uf, dict):
        return None
    raw = uf.get("productModel")
    if raw is None:
        return None
    key = str(raw).strip().lower()
    return key or None


def _scope_hard_key_selector(selector: str, scope_selector: str) -> str:
    trimmed = selector.strip()
    if not trimmed:
        return scope_selector
    if scope_selector in trimmed:
        return trimmed
    lowered = trimmed.lower()
    for root_sel in (":root", "html", "body"):
        if lowered == root_sel:
            return scope_selector
        if lowered.startswith(root_sel + " "):
            return f"{scope_selector}{trimmed[len(root_sel):]}"
        if lowered.startswith(root_sel + ">"):
            return f"{scope_selector}{trimmed[len(root_sel):]}"
        if lowered.startswith(root_sel + ":"):
            return f"{scope_selector}{trimmed[len(root_sel):]}"
    return f"{scope_selector} {trimmed}"


def _scope_hard_key_template_css(css: str, scope_selector: str) -> str:
    """Prefix template selectors so hard-key template CSS cannot leak globally."""

    def _walk(block: str, *, allow_keyframe_steps: bool) -> str:
        out: list[str] = []
        idx = 0
        n = len(block)
        while idx < n:
            start = idx
            while idx < n and block[idx] not in "{;":
                idx += 1
            if idx >= n:
                out.append(block[start:])
                break
            token = block[start:idx]
            delim = block[idx]
            if delim == ";":
                out.append(token + ";")
                idx += 1
                continue
            depth = 1
            inner_start = idx + 1
            idx += 1
            while idx < n and depth > 0:
                if block[idx] == "{":
                    depth += 1
                elif block[idx] == "}":
                    depth -= 1
                idx += 1
            inner = block[inner_start : idx - 1] if depth == 0 else block[inner_start:]
            header = token.strip()
            if not header:
                out.append("{" + inner + "}")
                continue
            if header.startswith("@"):
                at_lower = header.lower()
                keyframes = at_lower.startswith(("@keyframes", "@-webkit-keyframes"))
                out.append(header + "{" + _walk(inner, allow_keyframe_steps=keyframes) + "}")
                continue
            if allow_keyframe_steps:
                out.append(header + "{" + inner + "}")
                continue
            scoped_selector = ", ".join(
                _scope_hard_key_selector(part, scope_selector) for part in header.split(",")
            )
            out.append(scoped_selector + "{" + inner + "}")
        return "".join(out)

    return _walk(css or "", allow_keyframe_steps=False)


def _hard_key_template_class_count(html_text: str, class_token: str) -> int:
    if not html_text or not class_token:
        return 0
    pattern = rf'class="[^"]*\b{re.escape(class_token)}\b[^"]*"'
    return len(re.findall(pattern, html_text, flags=re.IGNORECASE))


def _load_hard_key_template(model_key: str) -> tuple[str, str]:
    """Return `(scoped_style_css, body_inner_html)` for a hard-key template, cached.

    Template CSS is fully scoped so generic template selectors (for example `.row` and
    `.box`) are confined to this model's right hard-key zone.
    """
    cached = _HARD_KEY_TEMPLATE_CACHE.get(model_key)
    if cached is not None:
        return cached
    from sentinel.generation.hard_keys import registry as _hk_registry

    model = _hk_registry.MODELS.get(model_key)
    if model is None:
        return ("", "")
    text = model.template_html_path.read_text(encoding="utf-8")
    style_match = re.search(r"<style[^>]*>(.*?)</style>", text, re.DOTALL | re.IGNORECASE)
    body_match = re.search(r"<body[^>]*>(.*?)</body>", text, re.DOTALL | re.IGNORECASE)
    style = style_match.group(1) if style_match else ""
    body = body_match.group(1) if body_match else ""
    scope_selector = f".hk-split-right[data-hk-model=\"{model_key}\"]"
    style = _scope_hard_key_template_css(style, scope_selector)
    _HARD_KEY_TEMPLATE_CACHE[model_key] = (style, body)
    return (style, body)


def _hard_key_button_meta(btn: dict[str, Any], variable_label: str, app_ui: dict[str, Any], category_label: str) -> str:
    identity = btn.get("buttonIdentity", {}) if isinstance(btn, dict) else {}
    identity_label = _button_identity_label(btn) if isinstance(btn, dict) else ""
    category_key = _category_key_from_label(category_label)
    meta: dict[str, Any] = {
        "category": category_label,
        "categoryKey": category_key,
        "identity": identity_label,
        "buttonType": identity.get("buttonType") or "",
        "targets": _targets(btn, variable_label) if isinstance(btn, dict) else {},
    }
    if isinstance(btn, dict) and isinstance(btn.get("apexScopeSource"), dict):
        meta["apexScopeSource"] = btn.get("apexScopeSource")
    return json.dumps(meta).replace("'", "&apos;")


def _render_hard_key_button(
    btn: dict[str, Any],
    *,
    slot: int,
    category_label: str,
    variable_label: str,
    app_ui: dict[str, Any],
    page_targets: dict[int, str],
    page_target_indexes: dict[int, int] | None,
    rendering_page_id: int | None = None,
) -> str:
    """Render a hard-key `.btn-wrap` that fills its template slot and reuses target wiring."""
    if not isinstance(btn, dict):
        return ""
    identity_label = _button_identity_label(btn)
    tag_name = _button_tag_name(btn)
    category_key = _category_key_from_label(category_label)
    meta_attr = _hard_key_button_meta(btn, variable_label, app_ui, category_label)
    link_html = _page_link_markup(btn, app_ui, page_targets, page_target_indexes, rendering_page_id=rendering_page_id)
    return (
        f"<div class='btn-wrap hk-btn-wrap' "
        f"style='position:absolute;inset:0;width:auto;height:auto;display:flex;'"
        f" data-hard-key-slot='{int(slot)}'"
        f" data-button-category='{escape(category_key, quote=True)}'"
        f" data-button-tag='{escape(tag_name, quote=True)}'>"
        f"<button class='test-btn' type='button' data-meta='{meta_attr}'>{escape(identity_label)}</button>"
        f"{link_html}"
        f"<div class='btn-pass-total' aria-hidden='true'></div>"
        f"</div>"
    )


def _augment_template_with_slots(
    body_html: str,
    *,
    model_key: str,
    slot_buttons_by_left: dict[int, tuple[dict[str, Any], str]],
    variable_label: str,
    app_ui: dict[str, Any],
    page_targets: dict[int, str],
    page_target_indexes: dict[int, int] | None,
    rendering_page_id: int | None = None,
) -> str:
    from sentinel.generation.hard_keys import registry as _hk_registry

    model = _hk_registry.MODELS.get(model_key)
    if model is None:
        return body_html

    box_re = re.compile(
        r'<div\s+class="([^"]*\bbox\b[^"]*)"([^>]*?)>\s*</div>',
        re.DOTALL,
    )
    template_box_count = len(box_re.findall(body_html))
    lo, hi = model.slot_range
    expected_slot_keys = set(range(lo, hi + 1))

    label_map = model.slot_by_data_label
    dpad_count_before = _hard_key_template_class_count(body_html, "dpad")
    injected_slots: list[int] = []
    data_label_re = re.compile(r'data-label\s*=\s*"([^"]*)"', re.IGNORECASE)

    if label_map is not None:
        if len(label_map) != template_box_count:
            raise ValueError(
                f"Hard-key template slot count mismatch for model '{model_key}': "
                f"template empty boxes={template_box_count}, registry label map={len(label_map)}"
            )
        if sorted(label_map.values()) != list(range(lo, hi + 1)):
            raise ValueError(
                f"Hard-key label map must list each ButtonLeft in [{lo},{hi}] exactly once "
                f"for model '{model_key}'"
            )
        expected_slot_count = template_box_count

        def _replace(match: re.Match[str]) -> str:
            full = match.group(0)
            inner = re.match(r"^(<div\b[^>]+>)\s*(</div>)\s*$", full, flags=re.DOTALL | re.IGNORECASE)
            if not inner:
                return full
            open_tag, close_tag = inner.group(1), inner.group(2)
            dm = data_label_re.search(open_tag)
            if not dm:
                raise ValueError(
                    f"Hard-key template box missing data-label for model '{model_key}': {open_tag[:160]!r}"
                )
            dl = dm.group(1).strip()
            slot = label_map.get(dl)
            if slot is None:
                raise ValueError(f"Unknown data-label {dl!r} for model '{model_key}'")
            injected_slots.append(int(slot))
            button_entry = slot_buttons_by_left.get(int(slot))
            if button_entry is None:
                return full
            button, category_label = button_entry
            btn_html = _render_hard_key_button(
                button,
                slot=int(slot),
                category_label=category_label,
                variable_label=variable_label,
                app_ui=app_ui,
                page_targets=page_targets,
                page_target_indexes=page_target_indexes,
                rendering_page_id=rendering_page_id,
            )
            return f"{open_tag}{btn_html}{close_tag}"

    else:
        template_slots = list(model.slot_dom_order)
        expected_slot_count = len(template_slots)
        if template_box_count != expected_slot_count:
            raise ValueError(
                f"Hard-key template slot count mismatch for model '{model_key}': "
                f"template empty boxes={template_box_count}, registry slot_dom_order={expected_slot_count}"
            )
        iter_slots = iter(model.slot_dom_order)

        def _replace(match: re.Match[str]) -> str:
            try:
                slot = next(iter_slots)
            except StopIteration:
                return match.group(0)
            injected_slots.append(int(slot))
            button_entry = slot_buttons_by_left.get(int(slot))
            full = match.group(0)
            # Keep the template's opening tag byte-for-byte; only inject children before </div>.
            inner = re.match(r"^(<div\b[^>]+>)\s*(</div>)\s*$", full, flags=re.DOTALL | re.IGNORECASE)
            if not inner:
                return full
            open_tag, close_tag = inner.group(1), inner.group(2)
            if button_entry is None:
                return full
            button, category_label = button_entry
            btn_html = _render_hard_key_button(
                button,
                slot=int(slot),
                category_label=category_label,
                variable_label=variable_label,
                app_ui=app_ui,
                page_targets=page_targets,
                page_target_indexes=page_target_indexes,
                rendering_page_id=rendering_page_id,
            )
            return f"{open_tag}{btn_html}{close_tag}"

    augmented = box_re.sub(_replace, body_html)
    if len(injected_slots) != expected_slot_count:
        raise ValueError(
            f"Hard-key slot walk mismatch for model '{model_key}': "
            f"walked={len(injected_slots)} expected={expected_slot_count}"
        )
    unknown_slots = sorted(k for k in slot_buttons_by_left.keys() if int(k) not in expected_slot_keys)
    if unknown_slots:
        raise ValueError(
            f"Hard-key slot mapping contains unknown slots for model '{model_key}': {unknown_slots}"
        )
    dpad_count_after = _hard_key_template_class_count(augmented, "dpad")
    if dpad_count_before != dpad_count_after:
        raise ValueError(
            f"Hard-key template d-pad structure changed for model '{model_key}': "
            f"before={dpad_count_before} after={dpad_count_after}"
        )
    return augmented


def _render_hard_key_strip(
    *,
    model_key: str,
    hard_key_layer: dict[str, Any],
    layer_hard_buttons: list[tuple[dict[str, Any], str]],
    variable_label: str,
    app_ui: dict[str, Any],
    page_targets: dict[int, str],
    page_target_indexes: dict[int, int] | None,
    rendering_page_id: int | None = None,
) -> str:
    """Build the right-zone HTML for one page using the registry template + layer rows."""
    _, body = _load_hard_key_template(model_key)
    if not body:
        return ""
    button_by_id: dict[int, tuple[dict[str, Any], str]] = {}
    for ub, category_label in layer_hard_buttons or []:
        if not isinstance(ub, dict):
            continue
        scope = ub.get("apexScopeSource") if isinstance(ub.get("apexScopeSource"), dict) else {}
        bid_obj = scope.get("button") if isinstance(scope.get("button"), dict) else {}
        bid = bid_obj.get("buttonId")
        if bid is None:
            continue
        button_by_id[int(bid)] = (ub, category_label)

    slot_buttons_by_left: dict[int, tuple[dict[str, Any], str]] = {}
    for slot in (hard_key_layer or {}).get("slots", []) or []:
        if not isinstance(slot, dict):
            continue
        bid = slot.get("buttonId")
        if bid is None:
            continue
        button_entry = button_by_id.get(int(bid))
        if button_entry is None:
            continue
        slot_key = int(slot.get("slotKey") or slot.get("buttonLeft") or 0)
        slot_buttons_by_left[slot_key] = button_entry

    augmented = _augment_template_with_slots(
        body,
        model_key=model_key,
        slot_buttons_by_left=slot_buttons_by_left,
        variable_label=variable_label,
        app_ui=app_ui,
        page_targets=page_targets,
        page_target_indexes=page_target_indexes,
        rendering_page_id=rendering_page_id,
    )
    return augmented


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
    rendering_page_id: int | None = None,
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
    identity_label = _button_identity_label(btn)
    category_key = _category_key_from_label(label)
    meta = {
        "category": label,
        "categoryKey": category_key,
        "identity": identity_label,
        "buttonType": identity.get("buttonType") or "",
        "targets": _targets(btn, variable_label),
    }
    if isinstance(btn.get("apexScopeSource"), dict):
        meta["apexScopeSource"] = btn.get("apexScopeSource")
    meta_attr = json.dumps(meta).replace("'", "&apos;")
    visibility_attr = "1" if bool(oriented_ui.get("visible", True)) and "display:none" not in extra_style else "0"
    classes = f"btn-wrap {extra_classes}".strip()
    tag_name = _button_tag_name(btn)
    link_html = _page_link_markup(btn, app_ui, page_targets, page_target_indexes, rendering_page_id=rendering_page_id)
    standard_attrs = f"data-button-tag='{escape(tag_name, quote=True)}'"
    return (
        f"<div class='{classes}' style='{extra_style}' data-left='{left}' data-top='{top}' data-width='{width}' data-height='{height}' data-font-size='{fs}' data-visible='{visibility_attr}' data-button-category='{escape(category_key, quote=True)}' {orientation_attrs} {standard_attrs} {extra_attrs}>"
        f"<button class='test-btn' data-meta='{meta_attr}'>{escape(identity_label)}</button>"
        f"{link_html}</div>"
    )


_ROOM_LIST_SYNTHETIC_GAP_PX = 2
_ROOM_LIST_SYNTHETIC_Z_BOOST = 0
_SYNTHETIC_LIST_SIDE_INSET_PX = 10
# Extra horizontal shrink per side (device px) so row hit targets do not span the full inner width and
# the true list host can receive clicks in the left/right gutters (see synthetic-list pointer-events).
_SYNTHETIC_LIST_ROW_HIT_SHRINK_PX = 8


def _synthetic_list_host_rect_pair(
    host_btn: dict[str, Any],
    portrait_off_left: int,
    portrait_off_top: int,
    landscape_off_left: int,
    landscape_off_top: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    p_c = _ui_coordinates(host_btn["buttonUI"], "portrait")
    l_c = _ui_coordinates(host_btn["buttonUI"], "landscape")
    portrait = (
        int(p_c.get("left") or 0) + portrait_off_left,
        int(p_c.get("top") or 0) + portrait_off_top,
        int(p_c.get("width") or 0),
        int(p_c.get("height") or 0),
    )
    landscape = (
        int(l_c.get("left") or 0) + landscape_off_left,
        int(l_c.get("top") or 0) + landscape_off_top,
        int(l_c.get("width") or 0),
        int(l_c.get("height") or 0),
    )
    return portrait, landscape


def _synthetic_list_scroll_pad_height_px(
    n: int,
    gap: int,
    row_h: int | None,
    host_h_portrait: int,
    host_h_landscape: int,
) -> int:
    """Min document height (device px) so overflow:auto can scroll when rows are position:absolute."""

    def stack_for_host(host_h: int) -> int:
        if n <= 0 or host_h <= 0:
            return 0
        if row_h is not None and row_h > 0:
            return n * row_h + max(0, n - 1) * gap
        return host_h

    return max(stack_for_host(host_h_portrait), stack_for_host(host_h_landscape))


def _synthetic_list_scroll_pad_html(pad_h: int) -> str:
    if pad_h <= 0:
        return ""
    return (
        f'<div class="synthetic-list-scroll-pad" aria-hidden="true" data-pad-height="{pad_h}" '
        f'style="width:100%;height:0;visibility:hidden;pointer-events:none;margin:0;padding:0;border:0;"></div>'
    )


def _synthetic_list_scroll_shell_open(
    *,
    host_btn: dict[str, Any],
    portrait_off_left: int,
    portrait_off_top: int,
    landscape_off_left: int,
    landscape_off_top: int,
    z_index: int,
    list_kind: str,
    layer_key: str,
    layer_order: int,
    layer_display: str,
    orientation: str,
    extra_classes: str = "",
    extra_attrs: str = "",
) -> str:
    (pl, pt, pw, ph), (ll, lt, lw, lh) = _synthetic_list_host_rect_pair(
        host_btn,
        portrait_off_left,
        portrait_off_top,
        landscape_off_left,
        landscape_off_top,
    )
    shell_ui: dict[str, Any] = {
        "fontSize": 10,
        "orientations": {
            "portrait": {"visible": True, "coordinates": {"left": pl, "top": pt, "width": pw, "height": ph}},
            "landscape": {"visible": True, "coordinates": {"left": ll, "top": lt, "width": lw, "height": lh}},
        },
    }
    oriented = _orientation_ui(shell_ui, orientation)
    visibility_attr = "1" if bool(oriented.get("visible", True)) else "0"
    oc = _ui_coordinates(shell_ui, orientation)
    left = int(oc.get("left") or 0)
    top = int(oc.get("top") or 0)
    w = int(oc.get("width") or 0)
    h = int(oc.get("height") or 0)
    classes = f"synthetic-list-scroll scroll-hover {extra_classes}".strip()
    # Inline overflow so clipping cannot be lost to stylesheet ordering/specificity in embedded UIs.
    return (
        f"<div class='{classes}' style='z-index:{z_index}; overflow-x:hidden; overflow-y:auto; min-height:0;' "
        f"data-left='{left}' data-top='{top}' data-width='{w}' data-height='{h}' "
        f"data-visible='{visibility_attr}' data-font-size='10' "
        f"{_orientation_data_attrs(shell_ui)} "
        f"data-synthetic-list-scroll='1' data-synthetic-list-kind='{list_kind}' "
        f"data-owner-layer-key='{layer_key}' data-owner-layer-order='{layer_order}' "
        f"data-owner-layer-name='{escape(layer_display, quote=True)}'{extra_attrs}>"
    )


def _is_room_list_host_button(btn: dict[str, Any]) -> bool:
    if not isinstance(btn, dict):
        return False
    t = btn.get("testTargets", {})
    if not isinstance(t, dict):
        return False
    vars_t = t.get("variables", {})
    if not isinstance(vars_t, dict) or not bool(vars_t.get("List")):
        return False
    tag = _norm_text(_button_tag_name(btn)).lower()
    text = _norm_text((btn.get("buttonIdentity") or {}).get("text") or "").lower()
    blob = f"{tag} {text}"
    return "room" in blob and "list" in blob


def _sorted_diag_room_rows(diag: dict[str, Any]) -> list[dict[str, Any]]:
    rooms = diag.get("rooms")
    if not isinstance(rooms, list):
        return []

    def sort_key(row: dict[str, Any]) -> tuple[int, int]:
        raw = row.get("controllerRoomOrder")
        if raw is None:
            return (1, 10**9)
        try:
            return (0, int(raw))
        except (TypeError, ValueError):
            return (1, 10**9)

    rows = [r for r in rooms if isinstance(r, dict)]
    return sorted(rows, key=sort_key)


def _room_list_primary_tag_info(room_row: dict[str, Any]) -> tuple[str, int | None]:
    for key in ("roomSelectRoomLabelTags", "roomSelectTagsAll"):
        val = room_row.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    name = _norm_text(item.get("buttonTagName"))
                    tid_raw = item.get("buttonTagId")
                    if name:
                        try:
                            tid = int(tid_raw) if tid_raw is not None else None
                        except (TypeError, ValueError):
                            tid = None
                        return name, tid
                else:
                    s = _norm_text(item)
                    if s:
                        return s, None
    return "Room", None


def _list_row_height_px_from_host(btn: dict[str, Any]) -> int | None:
    """Apex list row height merged into `buttonUI.listItemHeightPx` during extraction."""
    ui = btn.get("buttonUI") if isinstance(btn, dict) else None
    if not isinstance(ui, dict):
        return None
    raw = ui.get("listItemHeightPx")
    try:
        h = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return None
    if h <= 0:
        return None
    return int(h)


def _synthetic_list_row_slot_rects(
    list_left: int,
    list_top: int,
    list_w: int,
    list_h: int,
    n: int,
    gap: int,
    row_height_px: int | None = None,
) -> list[tuple[int, int, int, int]]:
    if n <= 0 or list_w <= 0 or list_h <= 0:
        return []
    # When Apex gives a row height (after display multiplier), use it for every row even if the stack
    # extends past the host rect — divide-by-n was producing unusably thin strips.
    if row_height_px is not None and row_height_px > 0:
        out_fixed: list[tuple[int, int, int, int]] = []
        y = list_top
        for _ in range(n):
            out_fixed.append((list_left, y, list_w, row_height_px))
            y += row_height_px + gap
        return out_fixed
    total_gap = gap * (n - 1)
    slot_h = (list_h - total_gap) // n
    if slot_h <= 0:
        return []
    out: list[tuple[int, int, int, int]] = []
    y = list_top
    for _ in range(n):
        out.append((list_left, y, list_w, slot_h))
        y += slot_h + gap
    return out


def _synthetic_list_inset_rect_args(list_w: int) -> tuple[int, int]:
    inset = max(0, int(_SYNTHETIC_LIST_SIDE_INSET_PX))
    inner_w = max(1, int(list_w) - (2 * inset))
    return inset, inner_w


def _synthetic_list_row_track_rect_args(list_w: int) -> tuple[int, int]:
    """Row slot left + width inside the host (inner list area after side inset, then hit shrink)."""
    base_inset, inner_w = _synthetic_list_inset_rect_args(list_w)
    shrink = max(0, int(_SYNTHETIC_LIST_ROW_HIT_SHRINK_PX))
    row_left = base_inset + shrink
    row_w = max(1, inner_w - (2 * shrink))
    return row_left, row_w


def _room_list_row_slot_rects(
    list_left: int,
    list_top: int,
    list_w: int,
    list_h: int,
    n: int,
    gap: int,
    row_height_px: int | None = None,
) -> list[tuple[int, int, int, int]]:
    """Backward-compatible alias; use `_synthetic_list_row_slot_rects` for new code."""
    return _synthetic_list_row_slot_rects(list_left, list_top, list_w, list_h, n, gap, row_height_px=row_height_px)


def _max_button_order_for_page_layer(page: dict[str, Any], layer_key: str) -> int:
    category_defs = ("screenLabels", "screenButtons", "hardButtons", "emptyTag", "uiItems")
    max_order = 0
    layers = _page_layers(page)
    if layers and layer_key.startswith("layer-"):
        try:
            idx = int(layer_key.split("-", 1)[1])
        except (TypeError, ValueError):
            idx = -1
        if 0 <= idx < len(layers):
            cats = layers[idx].get("buttonCategories", {})
            for cat in category_defs:
                for btn in (cats.get(cat, []) if isinstance(cats, dict) else []):
                    stack = ((btn.get("buttonUI") or {}).get("stack") or {}) if isinstance(btn, dict) else {}
                    max_order = max(max_order, int(stack.get("buttonOrder", 0) or 0))
            return max_order
    cats = page.get("buttonCategories", {})
    for cat in category_defs:
        for btn in (cats.get(cat, []) if isinstance(cats, dict) else []):
            stack = ((btn.get("buttonUI") or {}).get("stack") or {}) if isinstance(btn, dict) else {}
            max_order = max(max_order, int(stack.get("buttonOrder", 0) or 0))
    return max_order


def _find_room_list_host(page: dict[str, Any], orientation: str) -> tuple[str, dict[str, Any]] | None:
    for btn, label, off_top, off_left, layer_key, layer_order in _iter_page_buttons(page):
        if not _is_room_list_host_button(btn):
            continue
        oriented_ui = _orientation_ui(btn["buttonUI"], orientation)
        if not bool(oriented_ui.get("visible", True)):
            continue
        c = _ui_coordinates(btn["buttonUI"], orientation)
        if int(c.get("width") or 0) <= 0 or int(c.get("height") or 0) <= 0:
            continue
        return (
            "page",
            {
                "btn": btn,
                "label": label,
                "off_top": off_top,
                "off_left": off_left,
                "layer_key": layer_key,
                "layer_order": layer_order,
            },
        )
    for vb in _iter_viewport_buttons(page, orientation):
        if not vb.get("visible"):
            continue
        btn = vb.get("btn")
        if not isinstance(btn, dict) or not _is_room_list_host_button(btn):
            continue
        c = _ui_coordinates(btn["buttonUI"], orientation)
        if int(c.get("width") or 0) <= 0 or int(c.get("height") or 0) <= 0:
            continue
        return ("viewport", vb)
    return None


def _synthetic_room_list_row_button(
    *,
    room_row: dict[str, Any],
    row_rect_portrait: tuple[int, int, int, int],
    row_rect_landscape: tuple[int, int, int, int],
    layer_order: int,
    row_index: int,
    page_id: Any,
    rti_address: Any,
    source_device_id: Any,
    primary_tag: str,
    primary_tag_id: int | None,
    layer_max_button_order: int,
    room_display: str,
) -> dict[str, Any]:
    row_left_p, row_top_p, row_w_p, row_h_p = row_rect_portrait
    row_left_l, row_top_l, row_w_l, row_h_l = row_rect_landscape
    slot_fs = 10
    resolved = room_row.get("resolvedPageLink")
    page_link_on = isinstance(resolved, dict) and (
        resolved.get("targetPageId") is not None
        or (
            resolved.get("resolutionPath") == "nextInGroup"
            and isinstance(resolved.get("groupPageIds"), list)
            and len(resolved["groupPageIds"]) >= 2
        )
    )
    room_id = int(room_row.get("roomId") or 0)
    return {
        "buttonIdentity": {
            "buttonTagName": primary_tag,
            "text": room_display,
            "buttonType": None,
        },
        "buttonUI": {
            "fontSize": slot_fs,
            "orientations": {
                "portrait": {
                    "visible": True,
                    "coordinates": {"left": row_left_p, "top": row_top_p, "width": row_w_p, "height": row_h_p},
                },
                "landscape": {
                    "visible": True,
                    "coordinates": {"left": row_left_l, "top": row_top_l, "width": row_w_l, "height": row_h_l},
                },
            },
            "stack": {
                "layerOrder": layer_order,
                "buttonOrder": int(layer_max_button_order) + 1,
                "frameNumber": 0,
            },
        },
        "testTargets": {
            "text": True,
            "macros": False,
            "macroSteps": False,
            "variables": {
                "Text": False,
                "Reversed": False,
                "Inactive": False,
                "Visible": False,
                "Value": False,
                "State": False,
                "Command": False,
                "Image": False,
                "List": False,
            },
            "graphics": {"bitmap": False, "icon": False},
            "pageLink": {"enabled": page_link_on},
        },
        "resolvedPageLink": resolved if page_link_on else None,
        "apexScopeSource": {
            "page": {"pageId": page_id, "roomId": room_id, "sourceDeviceId": source_device_id, "rtiAddress": rti_address},
            "viewportLayer": {"layerId": 0, "sharedLayerId": 0, "roomId": None, "sourceId": None},
            "pageLayer": {"roomId": None, "sourceId": None},
            "button": {"buttonId": 1_000_000 + row_index, "buttonTagId": primary_tag_id},
            "bindings": {"macroIds": [], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
        },
    }


def _synthetic_room_list_row_id_attr(room_row: dict[str, Any], fallback_index: int) -> str:
    rid = room_row.get("roomId")
    if rid is None:
        return str(fallback_index)
    try:
        return str(int(rid))
    except (TypeError, ValueError):
        return str(rid)


def _synthetic_controller_room_list_rows_html(
    page: dict[str, Any],
    orientation: str,
    diag: dict[str, Any],
    diag_page_id: Any,
    diag_device_id: Any,
    variable_label: str,
    app_ui: dict[str, Any],
    page_targets: dict[int, str],
    page_target_indexes: dict[int, int] | None,
    layer_name_by_key: dict[str, str],
    page_id: Any,
    rti_address: Any,
) -> str:
    room_rows = _sorted_diag_room_rows(diag)
    if not room_rows:
        return ""
    host_hit = _find_room_list_host(page, orientation)
    if not host_hit:
        return ""
    kind, payload = host_hit
    parts: list[str] = []

    if kind == "page":
        btn = payload["btn"]
        label = str(payload["label"] or "Screen Button")
        off_top = int(payload["off_top"])
        off_left = int(payload["off_left"])
        layer_key = str(payload["layer_key"])
        layer_order = int(payload["layer_order"])
        p_c = _ui_coordinates(btn["buttonUI"], "portrait")
        l_c = _ui_coordinates(btn["buttonUI"], "landscape")
        row_h = _list_row_height_px_from_host(btn)
        p_row_left, p_row_w = _synthetic_list_row_track_rect_args(int(p_c.get("width") or 0))
        l_row_left, l_row_w = _synthetic_list_row_track_rect_args(int(l_c.get("width") or 0))
        rects_p = _synthetic_list_row_slot_rects(
            p_row_left,
            0,
            p_row_w,
            int(p_c.get("height") or 0),
            len(room_rows),
            _ROOM_LIST_SYNTHETIC_GAP_PX,
            row_h,
        )
        rects_l = _synthetic_list_row_slot_rects(
            l_row_left,
            0,
            l_row_w,
            int(l_c.get("height") or 0),
            len(room_rows),
            _ROOM_LIST_SYNTHETIC_GAP_PX,
            row_h,
        )
        if len(rects_p) != len(room_rows) or len(rects_l) != len(room_rows):
            return ""
        layer_max_button_order = _max_button_order_for_page_layer(page, layer_key)
        layer_display = str(layer_name_by_key.get(layer_key, "") or "")
        rid0 = _synthetic_room_list_row_id_attr(room_rows[0], 0)
        room_display0 = _norm_text(room_rows[0].get("roomName")) or f"Room {rid0}"
        tag0, tag_id0 = _room_list_primary_tag_info(room_rows[0])
        syn0 = _synthetic_room_list_row_button(
            room_row=room_rows[0],
            row_rect_portrait=rects_p[0],
            row_rect_landscape=rects_l[0],
            layer_order=layer_order,
            row_index=0,
            page_id=page_id,
            rti_address=rti_address,
            source_device_id=diag_device_id,
            primary_tag=tag0,
            primary_tag_id=tag_id0,
            layer_max_button_order=layer_max_button_order,
            room_display=room_display0,
        )
        list_z = _button_composite_z_index(syn0, fallback_layer_order=layer_order, tie_breaker=1)
        parts.append(
            _synthetic_list_scroll_shell_open(
                host_btn=btn,
                portrait_off_left=off_left,
                portrait_off_top=off_top,
                landscape_off_left=off_left,
                landscape_off_top=off_top,
                z_index=list_z,
                list_kind="room",
                layer_key=layer_key,
                layer_order=layer_order,
                layer_display=layer_display,
                orientation=orientation,
            )
        )
        pad_h = _synthetic_list_scroll_pad_height_px(
            len(room_rows),
            _ROOM_LIST_SYNTHETIC_GAP_PX,
            row_h,
            int(p_c.get("height") or 0),
            int(l_c.get("height") or 0),
        )
        parts.append(_synthetic_list_scroll_pad_html(pad_h))
        for i, room_row in enumerate(room_rows):
            rid_attr = _synthetic_room_list_row_id_attr(room_row, i)
            room_display = _norm_text(room_row.get("roomName")) or f"Room {rid_attr}"
            tag_name, tag_id = _room_list_primary_tag_info(room_row)
            syn = _synthetic_room_list_row_button(
                room_row=room_row,
                row_rect_portrait=rects_p[i],
                row_rect_landscape=rects_l[i],
                layer_order=layer_order,
                row_index=i,
                page_id=page_id,
                rti_address=rti_address,
                source_device_id=diag_device_id,
                primary_tag=tag_name,
                primary_tag_id=tag_id,
                layer_max_button_order=layer_max_button_order,
                room_display=room_display,
            )
            active_rect = rects_p[i] if orientation == "portrait" else rects_l[i]
            extra = (
                f"data-synthetic-room-list='1' data-synthetic-room-id='{escape(rid_attr, quote=True)}' "
                f"data-synthetic-room-tag-id='{int(tag_id) if tag_id is not None else ''}' "
                f"data-owner-layer-key='{layer_key}' data-owner-layer-order='{layer_order}' "
                f"data-owner-layer-name='{escape(layer_display, quote=True)}'"
            )
            if diag_device_id is not None:
                extra += f" data-diag-device-id='{int(diag_device_id)}'"
            if diag_page_id is not None:
                extra += f" data-diag-page-id='{int(diag_page_id)}'"
            parts.append(
                _render_button_control(
                    syn,
                    label,
                    active_rect[0],
                    active_rect[1],
                    variable_label,
                    app_ui,
                    page_targets,
                    page_target_indexes,
                    extra_style=f"z-index:{list_z};",
                    extra_attrs=extra,
                    orientation=orientation,
                    rendering_page_id=int(diag_page_id) if diag_page_id is not None else None,
                )
            )
        parts.append("</div>")
        return "".join(parts)

    vb = payload
    btn = vb["btn"]
    label = str(vb.get("label") or "Screen Button")
    p_c = _ui_coordinates(btn["buttonUI"], "portrait")
    l_c = _ui_coordinates(btn["buttonUI"], "landscape")
    row_h = _list_row_height_px_from_host(btn)
    p_row_left, p_row_w = _synthetic_list_row_track_rect_args(int(p_c.get("width") or 0))
    l_row_left, l_row_w = _synthetic_list_row_track_rect_args(int(l_c.get("width") or 0))
    rects_p = _synthetic_list_row_slot_rects(
        p_row_left,
        0,
        p_row_w,
        int(p_c.get("height") or 0),
        len(room_rows),
        _ROOM_LIST_SYNTHETIC_GAP_PX,
        row_h,
    )
    rects_l = _synthetic_list_row_slot_rects(
        l_row_left,
        0,
        l_row_w,
        int(l_c.get("height") or 0),
        len(room_rows),
        _ROOM_LIST_SYNTHETIC_GAP_PX,
        row_h,
    )
    if len(rects_p) != len(room_rows) or len(rects_l) != len(room_rows):
        return ""
    owner_lo = int(vb.get("owner_layer_order") or 0)
    owner_key = str(vb.get("owner_layer_key") or "")
    layer_max_button_order = _max_button_order_for_page_layer(page, owner_key)
    layer_display = str(layer_name_by_key.get(owner_key, "") or "")
    rid0 = _synthetic_room_list_row_id_attr(room_rows[0], 0)
    room_display0 = _norm_text(room_rows[0].get("roomName")) or f"Room {rid0}"
    tag0, tag_id0 = _room_list_primary_tag_info(room_rows[0])
    syn0 = _synthetic_room_list_row_button(
        room_row=room_rows[0],
        row_rect_portrait=rects_p[0],
        row_rect_landscape=rects_l[0],
        layer_order=owner_lo,
        row_index=0,
        page_id=page_id,
        rti_address=rti_address,
        source_device_id=diag_device_id,
        primary_tag=tag0,
        primary_tag_id=tag_id0,
        layer_max_button_order=layer_max_button_order,
        room_display=room_display0,
    )
    list_z = _button_composite_z_index(syn0, fallback_layer_order=owner_lo, fallback_frame_number=int(vb.get("frame_id") or 0), tie_breaker=1)
    vp_shell_extra = (
        f" data-vp='{vb['vp_index']}' data-frame='{vb['frame_id']}' "
        f"data-vp-layer-key='{escape(str(vb.get('vp_layer_key') or ''), quote=True)}' "
        f"data-vp-layer-name='{escape(str(vb.get('vp_layer_name') or ''), quote=True)}' "
        f"data-vp-layer-order='{int(vb.get('vp_layer_order') or 0)}' "
        f"data-vp-pv='{'1' if bool(vb.get('vp_portrait_visible', True)) else '0'}' "
        f"data-vp-lv='{'1' if bool(vb.get('vp_landscape_visible', True)) else '0'}'"
    )
    parts.append(
        _synthetic_list_scroll_shell_open(
            host_btn=btn,
            portrait_off_left=int(vb["portrait_off_left"]),
            portrait_off_top=int(vb["portrait_off_top"]),
            landscape_off_left=int(vb["landscape_off_left"]),
            landscape_off_top=int(vb["landscape_off_top"]),
            z_index=list_z,
            list_kind="room",
            layer_key=owner_key,
            layer_order=owner_lo,
            layer_display=layer_display,
            orientation=orientation,
            extra_classes="vp-btn",
            extra_attrs=vp_shell_extra,
        )
    )
    pad_h = _synthetic_list_scroll_pad_height_px(
        len(room_rows),
        _ROOM_LIST_SYNTHETIC_GAP_PX,
        row_h,
        int(p_c.get("height") or 0),
        int(l_c.get("height") or 0),
    )
    parts.append(_synthetic_list_scroll_pad_html(pad_h))
    for i, room_row in enumerate(room_rows):
        rid_attr = _synthetic_room_list_row_id_attr(room_row, i)
        room_display = _norm_text(room_row.get("roomName")) or f"Room {rid_attr}"
        tag_name, tag_id = _room_list_primary_tag_info(room_row)
        syn = _synthetic_room_list_row_button(
            room_row=room_row,
            row_rect_portrait=rects_p[i],
            row_rect_landscape=rects_l[i],
            layer_order=owner_lo,
            row_index=i,
            page_id=page_id,
            rti_address=rti_address,
            source_device_id=diag_device_id,
            primary_tag=tag_name,
            primary_tag_id=tag_id,
            layer_max_button_order=layer_max_button_order,
            room_display=room_display,
        )
        active_rect = rects_p[i] if orientation == "portrait" else rects_l[i]
        extra = (
            f"data-synthetic-room-list='1' data-synthetic-room-id='{escape(rid_attr, quote=True)}' "
            f"data-synthetic-room-tag-id='{int(tag_id) if tag_id is not None else ''}' "
            f"data-vp='{vb['vp_index']}' data-frame='{vb['frame_id']}' "
            f"data-vp-layer-key='{escape(str(vb.get('vp_layer_key') or ''), quote=True)}' "
            f"data-vp-layer-name='{escape(str(vb.get('vp_layer_name') or ''), quote=True)}' "
            f"data-vp-layer-order='{int(vb.get('vp_layer_order') or 0)}' "
            f"data-vp-pv='{'1' if bool(vb.get('vp_portrait_visible', True)) else '0'}' "
            f"data-vp-lv='{'1' if bool(vb.get('vp_landscape_visible', True)) else '0'}' "
            f"data-owner-layer-key='{owner_key}' data-owner-layer-order='{owner_lo}' "
            f"data-owner-layer-name='{escape(layer_display, quote=True)}'"
        )
        if diag_device_id is not None:
            extra += f" data-diag-device-id='{int(diag_device_id)}'"
        if diag_page_id is not None:
            extra += f" data-diag-page-id='{int(diag_page_id)}'"
        parts.append(
            _render_button_control(
                syn,
                label,
                active_rect[0],
                active_rect[1],
                variable_label,
                app_ui,
                page_targets,
                page_target_indexes,
                extra_classes="vp-btn",
                extra_style=f"z-index:{list_z};",
                extra_attrs=extra,
                orientation=orientation,
                rendering_page_id=int(diag_page_id) if diag_page_id is not None else None,
            )
        )
    parts.append("</div>")
    return "".join(parts)


def _is_source_list_host_button(btn: dict[str, Any]) -> bool:
    if not isinstance(btn, dict):
        return False
    t = btn.get("testTargets", {})
    if not isinstance(t, dict):
        return False
    vars_t = t.get("variables", {})
    if not isinstance(vars_t, dict) or not bool(vars_t.get("List")):
        return False
    tag = _norm_text(_button_tag_name(btn)).lower()
    text = _norm_text((btn.get("buttonIdentity") or {}).get("text") or "").lower()
    blob = f"{tag} {text}"
    return "source" in blob and "list" in blob


def _scope_room_source_from_button(btn: dict[str, Any]) -> tuple[int | None, int | None]:
    scope = btn.get("apexScopeSource")
    if not isinstance(scope, dict):
        return None, None
    page = scope.get("page") if isinstance(scope.get("page"), dict) else {}
    viewport_layer = scope.get("viewportLayer")
    if not isinstance(viewport_layer, dict):
        viewport_layer = scope.get("layer") if isinstance(scope.get("layer"), dict) else {}
    page_layer = scope.get("pageLayer") if isinstance(scope.get("pageLayer"), dict) else {}

    room_raw = viewport_layer.get("roomId")
    if room_raw is None:
        room_raw = page_layer.get("roomId")
    if room_raw is None:
        room_raw = page.get("roomId")

    source_raw = viewport_layer.get("sourceId")
    if source_raw is None:
        source_raw = page_layer.get("sourceId")
    if source_raw is None:
        source_raw = page.get("sourceDeviceId")

    room_id = int(room_raw) if room_raw is not None else None
    source_id = int(source_raw) if source_raw is not None else None
    return room_id, source_id


def _sorted_diag_source_rows(diag: dict[str, Any], room_id: int | None) -> list[dict[str, Any]]:
    rows = diag.get("sourceListRows")
    if not isinstance(rows, list):
        return []
    out = [r for r in rows if isinstance(r, dict)]
    # Apex Activities.Checked: non-zero = source appears on the room list (checkbox on).
    out = [r for r in out if int(r.get("checked") or 0) != 0]
    # Room id 0 / unset = not a real room scope (e.g. global overview). Emit all rooms' rows so
    # the client can show only the last selected room (session) via applySelectedRoomToSourceRows.
    if room_id is not None and int(room_id) > 0:
        out = [r for r in out if int(r.get("roomId") or -1) == int(room_id)]
    return sorted(
        out,
        key=lambda r: (
            int(r.get("roomId") or 0),
            int(r.get("activityOrder") or 0),
            _norm_text(r.get("sourceName")).lower(),
        ),
    )


def _find_source_list_host(page: dict[str, Any], orientation: str) -> tuple[str, dict[str, Any]] | None:
    for btn, label, off_top, off_left, layer_key, layer_order in _iter_page_buttons(page):
        if not _is_source_list_host_button(btn):
            continue
        oriented_ui = _orientation_ui(btn["buttonUI"], orientation)
        if not bool(oriented_ui.get("visible", True)):
            continue
        c = _ui_coordinates(btn["buttonUI"], orientation)
        if int(c.get("width") or 0) <= 0 or int(c.get("height") or 0) <= 0:
            continue
        return (
            "page",
            {
                "btn": btn,
                "label": label,
                "off_top": off_top,
                "off_left": off_left,
                "layer_key": layer_key,
                "layer_order": layer_order,
            },
        )
    for vb in _iter_viewport_buttons(page, orientation):
        if not vb.get("visible"):
            continue
        btn = vb.get("btn")
        if not isinstance(btn, dict) or not _is_source_list_host_button(btn):
            continue
        c = _ui_coordinates(btn["buttonUI"], orientation)
        if int(c.get("width") or 0) <= 0 or int(c.get("height") or 0) <= 0:
            continue
        return ("viewport", vb)
    return None


def _synthetic_source_list_row_button(
    *,
    source_row: dict[str, Any],
    row_rect_portrait: tuple[int, int, int, int],
    row_rect_landscape: tuple[int, int, int, int],
    layer_order: int,
    row_index: int,
    page_id: Any,
    rti_address: Any,
    layer_max_button_order: int,
) -> dict[str, Any]:
    row_left_p, row_top_p, row_w_p, row_h_p = row_rect_portrait
    row_left_l, row_top_l, row_w_l, row_h_l = row_rect_landscape
    source_name = _norm_text(source_row.get("sourceName")) or f"Source {row_index + 1}"
    source_device_id = int(source_row.get("sourceDeviceId") or 0)
    room_id = int(source_row.get("roomId") or 0)
    resolved = source_row.get("resolvedPageLink")
    page_link_on = isinstance(resolved, dict) and (
        resolved.get("targetPageId") is not None
        or (
            resolved.get("resolutionPath") == "nextInGroup"
            and isinstance(resolved.get("groupPageIds"), list)
            and len(resolved["groupPageIds"]) >= 2
        )
    )
    return {
        "buttonIdentity": {"buttonTagName": f"Source:{source_name}", "text": source_name, "buttonType": None},
        "buttonUI": {
            "fontSize": 10,
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"left": row_left_p, "top": row_top_p, "width": row_w_p, "height": row_h_p}},
                "landscape": {"visible": True, "coordinates": {"left": row_left_l, "top": row_top_l, "width": row_w_l, "height": row_h_l}},
            },
            "stack": {
                "layerOrder": layer_order,
                "buttonOrder": int(layer_max_button_order) + 1,
                "frameNumber": 0,
            },
        },
        "testTargets": {
            "text": True,
            "macros": False,
            "macroSteps": False,
            "variables": {
                "Text": False,
                "Reversed": False,
                "Inactive": False,
                "Visible": False,
                "Value": False,
                "State": False,
                "Command": False,
                "Image": False,
                "List": False,
            },
            "graphics": {"bitmap": False, "icon": False},
            "pageLink": {"enabled": page_link_on},
        },
        "resolvedPageLink": resolved if page_link_on else None,
        "apexScopeSource": {
            "page": {"pageId": page_id, "roomId": room_id, "sourceDeviceId": source_device_id, "rtiAddress": rti_address},
            "viewportLayer": {"layerId": 0, "sharedLayerId": 0, "roomId": room_id, "sourceId": source_device_id},
            "pageLayer": {"roomId": room_id, "sourceId": source_device_id},
            "button": {"buttonId": 2_000_000 + row_index, "buttonTagId": None},
            "bindings": {"macroIds": [], "variableIds": [], "macroStepIds": [], "pageLinkId": None},
        },
    }


def _synthetic_source_list_rows_html(
    page: dict[str, Any],
    orientation: str,
    diag: dict[str, Any],
    diag_page_id: Any,
    diag_device_id: Any,
    variable_label: str,
    app_ui: dict[str, Any],
    page_targets: dict[int, str],
    page_target_indexes: dict[int, int] | None,
    layer_name_by_key: dict[str, str],
    page_id: Any,
    rti_address: Any,
) -> str:
    host_hit = _find_source_list_host(page, orientation)
    if not host_hit:
        return ""
    kind, payload = host_hit
    host_btn = payload["btn"] if kind == "page" else payload["btn"]
    scoped_room_id, _scoped_source_id = _scope_room_source_from_button(host_btn)
    source_rows = _sorted_diag_source_rows(diag, scoped_room_id)
    if not source_rows:
        return ""
    parts: list[str] = []

    if kind == "page":
        label = str(payload["label"] or "Screen Button")
        off_top = int(payload["off_top"])
        off_left = int(payload["off_left"])
        layer_key = str(payload["layer_key"])
        layer_order = int(payload["layer_order"])
        p_c = _ui_coordinates(host_btn["buttonUI"], "portrait")
        l_c = _ui_coordinates(host_btn["buttonUI"], "landscape")
        src_row_h = _list_row_height_px_from_host(host_btn)
        p_row_left, p_row_w = _synthetic_list_row_track_rect_args(int(p_c.get("width") or 0))
        l_row_left, l_row_w = _synthetic_list_row_track_rect_args(int(l_c.get("width") or 0))
        rects_p = _synthetic_list_row_slot_rects(
            p_row_left,
            0,
            p_row_w,
            int(p_c.get("height") or 0),
            len(source_rows),
            _ROOM_LIST_SYNTHETIC_GAP_PX,
            src_row_h,
        )
        rects_l = _synthetic_list_row_slot_rects(
            l_row_left,
            0,
            l_row_w,
            int(l_c.get("height") or 0),
            len(source_rows),
            _ROOM_LIST_SYNTHETIC_GAP_PX,
            src_row_h,
        )
        if len(rects_p) != len(source_rows) or len(rects_l) != len(source_rows):
            return ""
        layer_max_button_order = _max_button_order_for_page_layer(page, layer_key)
        layer_display = str(layer_name_by_key.get(layer_key, "") or "")
        syn0 = _synthetic_source_list_row_button(
            source_row=source_rows[0],
            row_rect_portrait=rects_p[0],
            row_rect_landscape=rects_l[0],
            layer_order=layer_order,
            row_index=0,
            page_id=page_id,
            rti_address=rti_address,
            layer_max_button_order=layer_max_button_order,
        )
        list_z = _button_composite_z_index(syn0, fallback_layer_order=layer_order, tie_breaker=1)
        parts.append(
            _synthetic_list_scroll_shell_open(
                host_btn=host_btn,
                portrait_off_left=off_left,
                portrait_off_top=off_top,
                landscape_off_left=off_left,
                landscape_off_top=off_top,
                z_index=list_z,
                list_kind="source",
                layer_key=layer_key,
                layer_order=layer_order,
                layer_display=layer_display,
                orientation=orientation,
            )
        )
        pad_h = _synthetic_list_scroll_pad_height_px(
            len(source_rows),
            _ROOM_LIST_SYNTHETIC_GAP_PX,
            src_row_h,
            int(p_c.get("height") or 0),
            int(l_c.get("height") or 0),
        )
        parts.append(_synthetic_list_scroll_pad_html(pad_h))
        for i, source_row in enumerate(source_rows):
            syn = _synthetic_source_list_row_button(
                source_row=source_row,
                row_rect_portrait=rects_p[i],
                row_rect_landscape=rects_l[i],
                layer_order=layer_order,
                row_index=i,
                page_id=page_id,
                rti_address=rti_address,
                layer_max_button_order=layer_max_button_order,
            )
            active_rect = rects_p[i] if orientation == "portrait" else rects_l[i]
            extra = (
                f"data-synthetic-source-list='1' data-synthetic-source-room-id='{int(source_row.get('roomId') or 0)}' "
                f"data-synthetic-source-device-id='{int(source_row.get('sourceDeviceId') or 0)}' "
                f"data-owner-layer-key='{layer_key}' data-owner-layer-order='{layer_order}' "
                f"data-owner-layer-name='{escape(layer_display, quote=True)}'"
            )
            if diag_device_id is not None:
                extra += f" data-diag-device-id='{int(diag_device_id)}'"
            if diag_page_id is not None:
                extra += f" data-diag-page-id='{int(diag_page_id)}'"
            parts.append(
                _render_button_control(
                    syn,
                    label,
                    active_rect[0],
                    active_rect[1],
                    variable_label,
                    app_ui,
                    page_targets,
                    page_target_indexes,
                    extra_style=f"z-index:{list_z};",
                    extra_attrs=extra,
                    orientation=orientation,
                    rendering_page_id=int(diag_page_id) if diag_page_id is not None else None,
                )
            )
        parts.append("</div>")
        return "".join(parts)

    vb = payload
    label = str(vb.get("label") or "Screen Button")
    p_c = _ui_coordinates(host_btn["buttonUI"], "portrait")
    l_c = _ui_coordinates(host_btn["buttonUI"], "landscape")
    src_row_h = _list_row_height_px_from_host(host_btn)
    p_row_left, p_row_w = _synthetic_list_row_track_rect_args(int(p_c.get("width") or 0))
    l_row_left, l_row_w = _synthetic_list_row_track_rect_args(int(l_c.get("width") or 0))
    rects_p = _synthetic_list_row_slot_rects(
        p_row_left,
        0,
        p_row_w,
        int(p_c.get("height") or 0),
        len(source_rows),
        _ROOM_LIST_SYNTHETIC_GAP_PX,
        src_row_h,
    )
    rects_l = _synthetic_list_row_slot_rects(
        l_row_left,
        0,
        l_row_w,
        int(l_c.get("height") or 0),
        len(source_rows),
        _ROOM_LIST_SYNTHETIC_GAP_PX,
        src_row_h,
    )
    if len(rects_p) != len(source_rows) or len(rects_l) != len(source_rows):
        return ""
    owner_lo = int(vb.get("owner_layer_order") or 0)
    owner_key = str(vb.get("owner_layer_key") or "")
    layer_max_button_order = _max_button_order_for_page_layer(page, owner_key)
    layer_display = str(layer_name_by_key.get(owner_key, "") or "")
    syn0 = _synthetic_source_list_row_button(
        source_row=source_rows[0],
        row_rect_portrait=rects_p[0],
        row_rect_landscape=rects_l[0],
        layer_order=owner_lo,
        row_index=0,
        page_id=page_id,
        rti_address=rti_address,
        layer_max_button_order=layer_max_button_order,
    )
    list_z = _button_composite_z_index(syn0, fallback_layer_order=owner_lo, fallback_frame_number=int(vb.get("frame_id") or 0), tie_breaker=1)
    vp_shell_extra = (
        f" data-vp='{vb['vp_index']}' data-frame='{vb['frame_id']}' "
        f"data-vp-layer-key='{escape(str(vb.get('vp_layer_key') or ''), quote=True)}' "
        f"data-vp-layer-name='{escape(str(vb.get('vp_layer_name') or ''), quote=True)}' "
        f"data-vp-layer-order='{int(vb.get('vp_layer_order') or 0)}' "
        f"data-vp-pv='{'1' if bool(vb.get('vp_portrait_visible', True)) else '0'}' "
        f"data-vp-lv='{'1' if bool(vb.get('vp_landscape_visible', True)) else '0'}'"
    )
    parts.append(
        _synthetic_list_scroll_shell_open(
            host_btn=host_btn,
            portrait_off_left=int(vb["portrait_off_left"]),
            portrait_off_top=int(vb["portrait_off_top"]),
            landscape_off_left=int(vb["landscape_off_left"]),
            landscape_off_top=int(vb["landscape_off_top"]),
            z_index=list_z,
            list_kind="source",
            layer_key=owner_key,
            layer_order=owner_lo,
            layer_display=layer_display,
            orientation=orientation,
            extra_classes="vp-btn",
            extra_attrs=vp_shell_extra,
        )
    )
    pad_h = _synthetic_list_scroll_pad_height_px(
        len(source_rows),
        _ROOM_LIST_SYNTHETIC_GAP_PX,
        src_row_h,
        int(p_c.get("height") or 0),
        int(l_c.get("height") or 0),
    )
    parts.append(_synthetic_list_scroll_pad_html(pad_h))
    for i, source_row in enumerate(source_rows):
        syn = _synthetic_source_list_row_button(
            source_row=source_row,
            row_rect_portrait=rects_p[i],
            row_rect_landscape=rects_l[i],
            layer_order=owner_lo,
            row_index=i,
            page_id=page_id,
            rti_address=rti_address,
            layer_max_button_order=layer_max_button_order,
        )
        active_rect = rects_p[i] if orientation == "portrait" else rects_l[i]
        extra = (
            f"data-synthetic-source-list='1' data-synthetic-source-room-id='{int(source_row.get('roomId') or 0)}' "
            f"data-synthetic-source-device-id='{int(source_row.get('sourceDeviceId') or 0)}' "
            f"data-vp='{vb['vp_index']}' data-frame='{vb['frame_id']}' "
            f"data-vp-layer-key='{escape(str(vb.get('vp_layer_key') or ''), quote=True)}' "
            f"data-vp-layer-name='{escape(str(vb.get('vp_layer_name') or ''), quote=True)}' "
            f"data-vp-layer-order='{int(vb.get('vp_layer_order') or 0)}' "
            f"data-vp-pv='{'1' if bool(vb.get('vp_portrait_visible', True)) else '0'}' "
            f"data-vp-lv='{'1' if bool(vb.get('vp_landscape_visible', True)) else '0'}' "
            f"data-owner-layer-key='{owner_key}' data-owner-layer-order='{owner_lo}' "
            f"data-owner-layer-name='{escape(layer_display, quote=True)}'"
        )
        if diag_device_id is not None:
            extra += f" data-diag-device-id='{int(diag_device_id)}'"
        if diag_page_id is not None:
            extra += f" data-diag-page-id='{int(diag_page_id)}'"
        parts.append(
            _render_button_control(
                syn,
                label,
                active_rect[0],
                active_rect[1],
                variable_label,
                app_ui,
                page_targets,
                page_target_indexes,
                extra_classes="vp-btn",
                extra_style=f"z-index:{list_z};",
                extra_attrs=extra,
                orientation=orientation,
                rendering_page_id=int(diag_page_id) if diag_page_id is not None else None,
            )
        )
    parts.append("</div>")
    return "".join(parts)


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
    rendering_page_id = int(diag_page_id) if diag_page_id is not None else None
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
                extra_style=f"z-index:{_button_composite_z_index(btn, fallback_layer_order=layer_order)};",
                extra_attrs=(
                    f"data-owner-layer-key='{layer_key}' data-owner-layer-order='{layer_order}' "
                    f"data-owner-layer-name='{escape(str(layer_name_by_key.get(str(layer_key), '') or ''))}'{diag_attrs}"
                ),
                orientation=orientation,
                rendering_page_id=rendering_page_id,
            )
        )

    page_button_rows.append(
        _synthetic_controller_room_list_rows_html(
            page,
            orientation,
            diag,
            diag_page_id,
            diag_device_id,
            variable_label,
            app_ui,
            page_targets,
            page_target_indexes,
            layer_name_by_key,
            page.get("pageId"),
            page.get("rtiAddress"),
        )
    )
    page_button_rows.append(
        _synthetic_source_list_rows_html(
            page,
            orientation,
            diag,
            diag_page_id,
            diag_device_id,
            variable_label,
            app_ui,
            page_targets,
            page_target_indexes,
            layer_name_by_key,
            page.get("pageId"),
            page.get("rtiAddress"),
        )
    )

    viewport_button_rows: list[str] = []
    for vb in _iter_viewport_buttons(page, orientation):
        btn = vb["btn"]
        c = _ui_coordinates(btn["buttonUI"], orientation)
        stack = ((btn.get("buttonUI") or {}).get("stack") or {}) if isinstance(btn, dict) else {}
        z = _viewport_child_composite_z_index(
            owner_layer_order=int(vb["owner_layer_order"]),
            vp_layer_order=int(vb.get("vp_layer_order") or 0),
            button_order=int(stack.get("buttonOrder", 0) or 0),
            frame_number=int(stack.get("frameNumber", vb.get("frame_id") or 0) or 0),
        )
        extra = (
            f"z-index:{z};"
        )
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
                rendering_page_id=rendering_page_id,
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
                z=_viewport_box_z_index(int(c["layer_order"]), int(c["vp_index"])),
                nav_mode=escape(str((c.get("viewport_ui") or {}).get("navigationMode") or "page")),
                orientation_attrs=_orientation_data_attrs(c["viewport_ui"]),
                **c,
            )
            for c in _iter_viewport_boxes(page, orientation)
        ]
    )
    hard_key_strip_html = ""
    hard_key_owner_layer_key = ""
    model_key = _hard_key_model_key(device)
    if model_key is not None:
        page_layers_list = _page_layers(page) or []
        for layer_index, layer in enumerate(page_layers_list):
            if not isinstance(layer, dict):
                continue
            if not layer.get("isKeypadLayer"):
                continue
            hk_layer = layer.get("hardKeyLayer") if isinstance(layer.get("hardKeyLayer"), dict) else {}
            if not (hk_layer.get("slots") or hk_layer.get("gestures") or hk_layer.get("unmappedSlots")):
                continue
            hard_buttons: list[tuple[dict[str, Any], str]] = []
            categories = layer.get("buttonCategories") if isinstance(layer.get("buttonCategories"), dict) else {}
            if isinstance(categories.get("hardButtons"), list):
                hard_buttons.extend((btn, "Hard Button") for btn in categories.get("hardButtons") if isinstance(btn, dict))
            if isinstance(categories.get("emptyTag"), list):
                hard_buttons.extend((btn, "Empty Tag") for btn in categories.get("emptyTag") if isinstance(btn, dict))
            hard_key_strip_html = _render_hard_key_strip(
                model_key=model_key,
                hard_key_layer=hk_layer,
                layer_hard_buttons=hard_buttons,
                variable_label=variable_label,
                app_ui=app_ui,
                page_targets=page_targets,
                page_target_indexes=page_target_indexes,
                rendering_page_id=rendering_page_id,
            )
            if hard_key_strip_html:
                hard_key_owner_layer_key = _layer_key(layer_index)
                break

    return {
        "page_name": str(page.get("pageName", "")),
        "page_index": page_index,
        "layers": _page_layer_state(page),
        "vp_frames": vp_frames,
        "viewport_boxes": viewport_boxes,
        "page_button_rows": "".join(page_button_rows),
        "viewport_button_rows": "".join(viewport_button_rows),
        "hard_key_strip_html": hard_key_strip_html,
        "hard_key_owner_layer_key": hard_key_owner_layer_key,
        "product_model": model_key,
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
    room_list_resolution_json: str = "[]",
    source_list_resolution_json: str = "[]",
    hard_key_model_key: str | None = None,
    hard_key_style_css: str = "",
    hard_key_design_w: int = 0,
    hard_key_design_h: int = 0,
    device_profile_class: str = "",
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
    _ts_embed = _sentinel_test_status_embed_js()
    _hk_css_stripped = (hard_key_style_css or "").strip()
    _hard_key_template_style_tag = (
        '<style data-sentinel-hard-key-template="1">\n' + _hk_css_stripped + "\n</style>" if _hk_css_stripped else ""
    )
    device_theme_css = _sentinel_device_theme_css()
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{header}</title>
<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&icon_names=link_2,lock,lock_open_right\">
<style>
{device_theme_css}
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
.selected-room-indicator{{position:absolute;right:16px;top:50%;transform:translateY(-50%);font-size:12px;line-height:1;color:#2a455b;background:rgba(248,251,254,.92);border:1px solid #c6d2dd;border-radius:10px;padding:4px 10px;white-space:nowrap;pointer-events:none;z-index:24;}}
.selected-room-indicator .value{{font-weight:700;}}
.project-home-link{{display:inline-flex;align-items:center;justify-content:center;min-width:132px;height:40px;padding:0 16px;border-radius:14px;border:1px solid #a9bccd;background:#f7fbff;color:#14324b;text-decoration:none;font-size:14px;line-height:1;box-sizing:border-box;white-space:nowrap;}}
.project-home-link:hover{{filter:brightness(0.98);}}
.rti-canvas{{position:absolute;box-sizing:border-box;z-index:1;overflow:auto;scrollbar-width:none;scrollbar-gutter:stable overlay;}}
.rti-canvas.scroll-hover:hover{{scrollbar-width:thin;}}
.rti-canvas::-webkit-scrollbar{{width:10px;height:10px;}}
.rti-canvas:not(.scroll-hover)::-webkit-scrollbar-thumb{{background:transparent;}}
.rti-canvas:not(.scroll-hover)::-webkit-scrollbar-track{{background:transparent;}}
.rti-canvas.scroll-hover:hover::-webkit-scrollbar{{width:10px;height:10px;}}
.rti-canvas.scroll-hover:hover::-webkit-scrollbar-thumb{{background:#a9bccd;border-radius:999px;}}
.app-canvas:has(.rti-device-canvas-hk){{overflow:visible !important;}}
.app-canvas:has(.rti-device-canvas-hk) .rti-canvas{{overflow:visible !important;}}
.rti-content{{position:relative;min-width:100%;min-height:100%;}}
.rti-device-canvas:not(.rti-device-canvas-hk){{position:absolute;border:0;overflow:hidden;box-sizing:border-box;z-index:2;}}
.rti-device-canvas.rti-device-canvas-hk{{position:absolute;border:0;overflow:visible;box-sizing:border-box;z-index:2;}}
.device-page{{position:absolute;inset:0;display:none;}}
.device-page.active{{display:block;}}
 .vp-box{{position:absolute;border:2px dashed #88a6bd;border-radius:0;background:rgba(255,255,255,0.50);pointer-events:auto;cursor:pointer;z-index:9101;box-sizing:border-box;}}
 .vp-overlay{{position:absolute;inset:0;background:rgba(255,255,255,0.05);z-index:{_Z_VP_OVERLAY};pointer-events:none;display:none;}}
 .viewport-mode .vp-overlay{{display:block;}}
 .viewport-mode .vp-focus{{z-index:{_Z_VP_FOCUS} !important;pointer-events:auto;}}
 .viewport-mode .vp-box:not(.vp-focus){{pointer-events:none;}}
.btn-wrap{{position:absolute;z-index:2;}}
.synthetic-list-scroll{{position:absolute;z-index:2;overflow-x:hidden;overflow-y:auto;box-sizing:border-box;scrollbar-width:thin;scrollbar-color:transparent transparent;scrollbar-gutter:stable overlay;}}
.synthetic-list-scroll.scroll-hover:hover{{scrollbar-color:#a9bccd transparent;}}
.synthetic-list-scroll::-webkit-scrollbar{{width:10px;height:10px;}}
.synthetic-list-scroll::-webkit-scrollbar-thumb{{background:transparent;}}
.synthetic-list-scroll::-webkit-scrollbar-track{{background:transparent;}}
.synthetic-list-scroll.scroll-hover:hover::-webkit-scrollbar-thumb{{background:#a9bccd;border-radius:999px;}}
.synthetic-list-scroll .btn-wrap{{z-index:1;}}
/* Let clicks reach the real list host .btn-wrap underneath; rows stay interactive. */
.synthetic-list-scroll{{pointer-events:none;}}
.synthetic-list-scroll > .btn-wrap{{pointer-events:auto;}}
.synthetic-list-scroll > .synthetic-list-scroll-pad{{pointer-events:none;}}
 .device-page .btn-wrap.vp-btn{{pointer-events:none;}}
 .device-page .synthetic-list-scroll.vp-btn{{pointer-events:none;}}
 .vp-popup-stage .btn-wrap.vp-btn{{pointer-events:auto;}}
 .vp-popup-stage .synthetic-list-scroll.vp-btn{{pointer-events:auto;}}
 .viewport-mode #rtiCanvas{{pointer-events:none;overflow:hidden;}}
 .vp-popup{{position:fixed;left:0;top:0;width:0;height:0;display:none;align-items:center;justify-content:center;background:rgba(255,255,255,0.05);z-index:9800;}}
 .viewport-mode .vp-popup{{display:flex;}}
 .vp-popup[hidden]{{display:none;}}
.vp-popup-panel{{position:relative;width:100%;height:100%;max-width:none;max-height:none;background:rgba(247,251,255,.96);border:1px solid #b9cad8;border-radius:18px;box-shadow:0 18px 50px rgba(20,50,75,.20);overflow:hidden;box-sizing:border-box;isolation:isolate;}}
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
.page-link-hit{{position:absolute;top:0;right:0;height:100%;display:flex;align-items:center;justify-content:flex-end;text-decoration:none;color:#fff;opacity:1;pointer-events:auto;transition:opacity .15s ease;font-size:inherit;}}
.page-link-icon{{display:inline-flex;align-items:center;justify-content:center;width:1em;height:1em;font-size:1em;line-height:1;background:transparent;border-radius:0;}}
.page-link-icon .material-symbols-outlined{{font-size:1em;line-height:1;}}
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
.layer-toggle{{width:100%;min-height:{int(layer_panel_button_cfg.get("minHeight", 44))}px;border-radius:{int(layer_panel_button_cfg.get("borderRadius", 12))}px;border:0;box-shadow:inset 0 0 0 1px {str(layer_button_active_cfg.get("border", "#154665"))};background:{str(layer_button_active_cfg.get("background", "#1e5f86"))};color:{str(layer_button_active_cfg.get("text", "#ffffff"))};font-size:{int(layer_panel_button_cfg.get("fontSize", 13))}px;line-height:1.15;padding:10px 12px;cursor:pointer;text-align:left;display:inline-flex;align-items:center;gap:8px;}}
.layer-toggle.is-inactive{{background:{str(layer_button_inactive_cfg.get("background", "#f7fbff"))};color:{str(layer_button_inactive_cfg.get("text", "#14324b"))};box-shadow:inset 0 0 0 1px {str(layer_button_inactive_cfg.get("border", "#a9bccd"))};}}
.layer-lock-toggle{{display:inline-flex;align-items:center;justify-content:center;width:1em;min-width:1em;height:1em;font-size:1em;line-height:1;background:transparent;border-radius:0;}}
.layer-lock-icon.material-symbols-outlined{{font-size:1em;line-height:1;}}
.layer-toggle-label{{flex:1;text-align:left;}}
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
 .rti-device-canvas-hk .device-page{{display:none;position:relative;}}
 .rti-device-canvas-hk .device-page.active{{display:block;padding:0;height:100%;min-height:0;max-height:100%;overflow:visible;box-sizing:border-box;}}
 .rti-device-canvas-hk .device-page .hk-split-left{{position:absolute;top:0;bottom:0;height:auto;display:flex;align-items:center;justify-content:center;overflow:visible;z-index:1;}}
 .rti-device-canvas-hk .device-page .hk-split-right{{position:absolute;top:0;bottom:0;left:auto;height:auto;display:flex;flex-direction:column;align-items:center;justify-content:center;box-sizing:border-box;z-index:2;min-height:0;}}
 .rti-device-canvas-hk .hk-touch-stack{{position:relative;box-sizing:border-box;}}
 .hk-split-right .frame{{margin:0 auto;max-height:100%;}}
 .hk-split-right .box{{position:relative;}}
 .hk-btn-wrap{{position:absolute;left:0;top:0;width:100%;height:100%;display:flex;align-items:stretch;justify-content:stretch;}}
</style>{_hard_key_template_style_tag}</head>
<body><div class='app-canvas' id='appCanvas'>
<div class='app-ui-controls top-controls' id='topControls'>{f"<a class='project-home-link' href='{home_href}'>Project Home</a>" if home_href else "<div></div>"}<div class='header'>{header}</div><div></div><div class='selected-room-indicator' id='selectedRoomIndicator'>Selected Room: <span class='value' id='selectedRoomValue'>All Rooms</span></div></div>
{f"<div class='app-ui-controls orientation-controls' id='orientationControls'><div class='orientation-toggle' id='orientationToggle'><button class='orientation-btn' type='button' data-orientation='portrait'>Portrait</button><button class='orientation-btn' type='button' data-orientation='landscape'>Landscape</button></div></div>" if show_orientation_toggle else ""}
<div class='app-ui-controls layer-controls' id='layerControls'><div class='layer-panel' id='layerPanel' hidden><div class='layer-panel-title'>{escape(str(layer_panel_cfg.get("title", "Layers")))}</div><div class='layer-list' id='layerList'></div></div></div>
<div class='app-ui-controls bottom-controls' id='bottomControls'></div>
<div class='zoom-controls' id='zoomControls'><button class='zoom-btn zoom-dec' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("decrease", "-")}</button><button class='zoom-btn zoom-reset' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("reset", "100%")}</button><button class='zoom-btn zoom-inc' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("increase", "+")}</button></div>
 <div class='rti-canvas' id='rtiCanvas'><div class='vp-overlay' id='vpOverlay' hidden></div><div class='rti-content' id='rtiContent'><div class='rti-device-canvas{(" rti-device-canvas-hk" if hard_key_model_key else "")}' id='rtiDeviceCanvas'{(f" data-hk-model='{hard_key_model_key}' data-hk-design-w='{int(hard_key_design_w)}' data-hk-design-h='{int(hard_key_design_h)}'" if hard_key_model_key else "")}>{body_markup}</div></div></div></div>
 <div class='vp-popup' id='vpPopup' hidden><div class='vp-popup-panel' id='vpPopupPanel' role='dialog' aria-modal='true' aria-label='Viewport viewer'><button class='vp-popup-close' id='vpPopupClose' type='button' aria-label='Close viewport viewer'>&times;</button><button class='vp-popup-nav vp-popup-prev' id='vpPopupPrev' type='button' aria-label='Previous frame'>&lsaquo;</button><button class='vp-popup-nav vp-popup-next' id='vpPopupNext' type='button' aria-label='Next frame'>&rsaquo;</button><button class='vp-popup-nav vp-popup-up' id='vpPopupUp' type='button' aria-label='Scroll up'>&uarr;</button><button class='vp-popup-nav vp-popup-down' id='vpPopupDown' type='button' aria-label='Scroll down'>&darr;</button><div class='vp-popup-indicator vp-indicator' id='vpPopupIndicator'></div><div class='vp-popup-scroller' id='vpPopupScroller'><div class='vp-popup-scrollpad' id='vpPopupScrollpad'><div class='vp-popup-stage' id='vpPopupStage'></div></div></div></div></div>
 <div class='ov' id='ov'><div class='pop'><div class='pop-head'><h3 id='pt'></h3><button id='passAll' type='button'>Pass All</button></div><div id='rows' class='rows-scroll scroll-hover'></div><div class='post-status' id='postStatus' role='status' aria-live='polite' hidden></div><button id='close'>Close</button></div></div>
<script>
{_ts_embed}
const APP_UI={app_json};
const APP_UI_CONTROLS={control_json};
const RTI_DEVICE_LAYOUT={rti_device_json};
const VIEWPORT_NAV={json.dumps(app_ui.get("viewportNavigation", {}))};
const ZOOM_CONTROLS={json.dumps(app_ui.get("zoomControls", {}))};
const LAYER_PANEL={json.dumps(layer_panel_cfg)};
const ZOOM_DEFAULT={int(app_ui.get("zoomControls", {}).get("zoom", {}).get("defaultPercent", 100))};
const ZOOM_MAX={max(300, int(app_ui.get("zoomControls", {}).get("zoom", {}).get("maxPercent", 300)))};
const ZOOM_STEP={int(app_ui.get("zoomControls", {}).get("zoom", {}).get("stepPercent", 10))};
const TEXT_ZOOM_DEFAULT=100;
const TEXT_ZOOM_MIN=100;
const TEXT_ZOOM_MAX=300;
const TEXT_ZOOM_STEP=10;
const SOURCE_DEVICE_SIZE={{width:{w},height:{h}}};
const PROJECT_SESSION_KEY={json.dumps(project_session_key)};
const PAGE_HTML_BY_INDEX={page_html_by_index_json};
const PAGE_STATE={page_state_json};
const ROOM_LIST_RESOLUTION={room_list_resolution_json};
const SOURCE_LIST_RESOLUTION={source_list_resolution_json};
const ORIENTATION_STATE={orientation_state_json};
const VP_FRAMES=(PAGE_STATE[0]?.vpFrames||[]);
let currentZoomPercent=ZOOM_DEFAULT;
let currentTextZoomPercent=TEXT_ZOOM_DEFAULT;
let currentTotalScale=1;
let currentDeviceLeft=0;
let currentDeviceTop=0;
 let activePageIndex=0;
 let currentViewportIndexes=VP_FRAMES.map(()=>0);
 let currentOrientation=ORIENTATION_STATE.current;
const SELECTED_ROOM_SESSION_KEY=`${{PROJECT_SESSION_KEY}}:selected-room-id`;
let selectedRoomId=null;
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
const persistedLayerLocksByScope=new Map();
const sessionUnlockedLayerLocks=new Set();
const pendingLayerLockWsByKey=new Map();
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
function normalizeRoomId(raw) {{
 const n=Number(raw);
 if (!Number.isFinite(n) || n<=0) return null;
 return Number(n);
}}
function allResolvedRooms() {{
 return Array.isArray(ROOM_LIST_RESOLUTION) ? ROOM_LIST_RESOLUTION : [];
}}
function roomNameById(roomId) {{
 const target=normalizeRoomId(roomId);
 if (target==null) return "";
 for (const row of allResolvedRooms()) {{
  const rid=normalizeRoomId(row?.roomId);
  if (rid==null || rid!==target) continue;
  const name=String(row?.roomName||"").trim();
  if (name) return name;
 }}
 return "";
}}
function roomIdByName(roomName) {{
 const target=String(roomName||"").trim().toLowerCase();
 if (!target || target==="all rooms" || target==="whole house") return null;
 for (const row of allResolvedRooms()) {{
  const name=String(row?.roomName||"").trim();
  if (!name) continue;
  if (name.toLowerCase()!==target) continue;
  const rid=normalizeRoomId(row?.roomId);
  if (rid!=null) return rid;
 }}
 return null;
}}
function defaultSelectedRoomId() {{
 for (const row of allResolvedRooms()) {{
  const rid=normalizeRoomId(row?.roomId);
  if (rid!=null) return rid;
 }}
 return null;
}}
function loadSelectedRoomId() {{
 try {{
  const raw=sessionStorage.getItem(SELECTED_ROOM_SESSION_KEY);
  return normalizeRoomId(raw);
 }} catch (_e) {{
  return null;
 }}
}}
function persistSelectedRoomId(roomId) {{
 try {{
  if (roomId==null) sessionStorage.removeItem(SELECTED_ROOM_SESSION_KEY);
  else sessionStorage.setItem(SELECTED_ROOM_SESSION_KEY, String(roomId));
 }} catch (_e) {{}}
}}
function selectedRoomLabel() {{
 if (selectedRoomId==null) return "All Rooms";
 const name=roomNameById(selectedRoomId);
 return name ? name : `Room ${{selectedRoomId}}`;
}}
function syncSelectedRoomIndicator() {{
 const valueEl=document.getElementById('selectedRoomValue');
 if (!valueEl) return;
 valueEl.textContent=selectedRoomLabel();
}}
function applySelectedRoomToSourceRows(pageEl) {{
 if (!pageEl) return;
 const indicatorName=(document.getElementById('selectedRoomValue')?.textContent||'').trim();
 const fallbackRoomId=selectedRoomId==null ? roomIdByName(indicatorName) : null;
 const effectiveRoomId=(selectedRoomId!=null) ? selectedRoomId : fallbackRoomId;
 const byShell=new Map();
 pageEl.querySelectorAll(".btn-wrap[data-synthetic-source-list='1']").forEach(el=>{{
  const shell=el.closest(".synthetic-list-scroll[data-synthetic-list-kind='source']");
  if (!shell) return;
  const rowRoomId=normalizeRoomId(el.dataset.syntheticSourceRoomId);
  const matches=effectiveRoomId==null || (rowRoomId!=null && Number(rowRoomId)===Number(effectiveRoomId));
  el.dataset.selectedRoomMatch=matches ? "1" : "0";
  if (el.dataset.baseTop==null) el.dataset.baseTop=String(Number(el.dataset.top||0));
  const bucket=byShell.get(shell) || [];
  bucket.push(el);
  byShell.set(shell, bucket);
 }});
 byShell.forEach((rows, shell)=>{{
  const sorted=[...rows].sort((a,b)=>Number(a.dataset.baseTop||0)-Number(b.dataset.baseTop||0));
  const heights=sorted.map(r=>Number(r.dataset.height||0)).filter(v=>v>0);
  const rowH=heights.length ? heights[0] : 0;
  let step=0;
  for (let i=1; i<sorted.length; i+=1) {{
   const d=Number(sorted[i].dataset.baseTop||0)-Number(sorted[i-1].dataset.baseTop||0);
   if (d>0 && (step===0 || d<step)) step=d;
  }}
  const gap=Math.max(0, step>0 ? step-rowH : 2);
  let visibleIndex=0;
  sorted.forEach(row=>{{
   if (String(row.dataset.selectedRoomMatch||"0")==="1") {{
    row.dataset.activeTop=String(visibleIndex * (rowH + gap));
    visibleIndex += 1;
   }} else {{
    row.dataset.activeTop=String(Number(row.dataset.baseTop||0));
   }}
   // Keep canonical top in sync so every layout path uses compacted rows.
   row.dataset.top=String(Number(row.dataset.activeTop||row.dataset.baseTop||0));
  }});
  const pad=shell.querySelector(".synthetic-list-scroll-pad");
  if (pad) {{
   if (pad.dataset.basePadHeight==null) pad.dataset.basePadHeight=String(Number(pad.dataset.padHeight||0));
   const activePad=visibleIndex>0 ? (visibleIndex*rowH)+((visibleIndex-1)*gap) : 0;
   pad.dataset.activePadHeight=String(activePad);
  }}
  shell.scrollTop=0;
 }});
}}
function inferScopedRoomIdFromPage(pageEl) {{
 if (!pageEl) return null;
 const ids = new Set();
 pageEl.querySelectorAll(".btn-wrap[data-synthetic-source-list='1']").forEach(el=>{{
  const rid = normalizeRoomId(el.dataset.syntheticSourceRoomId);
  if (rid != null && Number(rid) > 0) ids.add(Number(rid));
 }});
 if (ids.size === 1) return Number(Array.from(ids)[0]);
 return null;
}}
function scopedRoomIdFromApexScope(apexScopeSource) {{
 const src=(apexScopeSource && typeof apexScopeSource==="object") ? apexScopeSource : null;
 if (!src) return null;
 const page=(src.page && typeof src.page==="object") ? src.page : {{}};
 const viewportLayer=(src.viewportLayer && typeof src.viewportLayer==="object")
  ? src.viewportLayer
  : ((src.layer && typeof src.layer==="object") ? src.layer : {{}});
 const pageLayer=(src.pageLayer && typeof src.pageLayer==="object") ? src.pageLayer : {{}};
 const roomRaw=(viewportLayer.roomId!=null)
  ? viewportLayer.roomId
  : ((pageLayer.roomId!=null) ? pageLayer.roomId : page.roomId);
 return normalizeRoomId(roomRaw);
}}
function scopedRoomIdFromWrap(wrap) {{
 if (!wrap) return null;
 const btn=wrap.querySelector(".test-btn");
 if (!btn || !btn.dataset) return null;
 let meta={{}};
 try {{
  meta=JSON.parse(btn.dataset.meta||"{{}}");
 }} catch (_e) {{
  meta={{}};
 }}
 return scopedRoomIdFromApexScope(meta && typeof meta==="object" ? meta.apexScopeSource : null);
}}
function setSelectedRoom(nextRoomId, options) {{
 const opts=(options && typeof options==="object") ? options : {{}};
 const persist=opts.persist!==false;
 selectedRoomId=normalizeRoomId(nextRoomId);
 if (persist) persistSelectedRoomId(selectedRoomId);
 syncSelectedRoomIndicator();
 applyLayerVisibility();
 if (!viewportMode.active) applyRtiLayout();
 refreshButtonVisualStates();
}}
 function refreshButtonVisualStates() {{
  const api=globalThis.__sentinelTestStatus;
  if (!api||typeof api.refreshButtonWraps!=="function") return;
  api.refreshButtonWraps({{
   root: document,
   wrapSelector: ".device-page .btn-wrap, .vp-popup-vcontent .btn-wrap.vp-btn",
   statusByTargetKey: statusByTargetKey,
   buildTargetPayload: buildTargetPayload,
  }});
}}
function deviceButtonRadiusBase() {{
 try {{
  const rootStyle=getComputedStyle(document.documentElement);
  const rawBase=String(rootStyle.getPropertyValue('--sentinel-device-button-radius-base')||'').trim();
  const nBase=Number.parseFloat(rawBase);
  if (Number.isFinite(nBase) && nBase>0) return nBase;
  const rawRadius=String(rootStyle.getPropertyValue('--sentinel-device-button-radius')||'').trim();
  const nRadius=Number.parseFloat(rawRadius);
  return Number.isFinite(nRadius) && nRadius>0 ? nRadius : 10;
 }} catch (_e) {{
  return 10;
 }}
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
     if (pendingTargetKey || isPosting) {{
      setPosting(false);
      setPostStatus(`Error: ${{msg}}`, "error");
      drainPassAllQueue();
     }} else {{
      _logTechWs("error-msg", msg);
     }}
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
     const layerLocks = Array.isArray(payload?.layerLocks) ? payload.layerLocks : [];
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
     _syncPersistedLayerLocksFromRows(layerLocks, true);
     renderLayerPanel();
     applyLayerVisibility();
     applyRtiLayout();
     _logTechWs("snapshot:applied", {{ total: results.length, applied, layerLocks: layerLocks.length }});
     refreshButtonVisualStates();
     return;
    }}
    if (t === "layer_lock_state") {{
     _syncPersistedLayerLocksFromRows([payload], false);
     renderLayerPanel();
     applyLayerVisibility();
     applyRtiLayout();
     return;
    }}
    if (t === "commissioning_rollups") return;
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
 ws.onopen = () => {{ techWsReconnectDelayMs = 500; _logTechWs("open"); _sendTechSyncRequest(); _flushLayerLockWsQueue(); }};
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
 function _renderRowStatusTimes(rowUi) {{
  if (!rowUi || !rowUi.lastTestEl) return;
  const times = rowUi.statusTimes || {{}};
  const outcome = String(rowUi.currentOutcome || "").trim().toUpperCase();
  if (outcome === "PASS" && times.PASS) {{
    rowUi.lastTestEl.textContent = `Passed: ${{times.PASS}}`;
    return;
  }}
  if (outcome === "FAIL" && times.FAIL) {{
    rowUi.lastTestEl.textContent = `Failed: ${{times.FAIL}}`;
    return;
  }}
  if (outcome === "UNTESTED" && times.UNTESTED) {{
    rowUi.lastTestEl.textContent = `Reverted: ${{times.UNTESTED}}`;
    return;
  }}
  rowUi.lastTestEl.textContent = "";
 }}
 function setRowStatus(rowUi, outcome, recordedAtUtc) {{
  if (!rowUi) return;
  const o = String(outcome || "").trim().toUpperCase();
  const at = formatLastTestUtc(recordedAtUtc);
  if (!rowUi.statusTimes) rowUi.statusTimes = {{}};
  if (rowUi.passBtn) rowUi.passBtn.classList.toggle("is-pass-active", o === "PASS");
  if (rowUi.failBtn) rowUi.failBtn.classList.toggle("is-fail-active", o === "FAIL");
  rowUi.currentOutcome = o;
  if (at && (o === "PASS" || o === "FAIL" || o === "UNTESTED")) rowUi.statusTimes[o] = at;
  _renderRowStatusTimes(rowUi);
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
  const targetKey = `event:${{eventId}}:${{label || "Event Trigger"}}`;
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
  const syntheticRoomList = wrap && wrap.dataset ? String(wrap.dataset.syntheticRoomList || "") === "1" : false;
  const syntheticRoomIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticRoomId : null;
  const syntheticRoomTagIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticRoomTagId : null;
  const syntheticRoomId = syntheticRoomIdRaw == null ? null : Number(syntheticRoomIdRaw);
  const syntheticRoomTagId = syntheticRoomTagIdRaw == null ? null : Number(syntheticRoomTagIdRaw);
  const syntheticSourceList = wrap && wrap.dataset ? String(wrap.dataset.syntheticSourceList || "") === "1" : false;
  const syntheticSourceRoomIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticSourceRoomId : null;
  const syntheticSourceDeviceIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticSourceDeviceId : null;
  const syntheticSourceRoomId = syntheticSourceRoomIdRaw == null ? null : Number(syntheticSourceRoomIdRaw);
  const syntheticSourceDeviceId = syntheticSourceDeviceIdRaw == null ? null : Number(syntheticSourceDeviceIdRaw);
  const categoryName = String(m.category || "").trim();
  const buttonName = String(m.identity || "").trim();
  const targetName = String(label || "").trim() || buttonName || categoryName;
  const keyToken = String(label || "").trim() || categoryName || buttonName || "Button";
  const keyTokenResolved = syntheticRoomList && syntheticRoomId != null && Number.isFinite(syntheticRoomId)
   ? `${{keyToken}}:room:${{Number(syntheticRoomId)}}`
   : (syntheticSourceList && syntheticSourceDeviceId != null && Number.isFinite(syntheticSourceDeviceId)
      ? `${{keyToken}}:src:${{Number(syntheticSourceDeviceId)}}:${{(syntheticSourceRoomId != null && Number.isFinite(syntheticSourceRoomId)) ? `room:${{Number(syntheticSourceRoomId)}}` : "room:na"}}`
      : keyToken);
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
  const effectiveRoomIdBase = viewportLayerRoomId != null
    ? Number(viewportLayerRoomId)
    : (pageLayerRoomId != null ? Number(pageLayerRoomId) : (pageRoomId != null ? Number(pageRoomId) : null));
  const effectiveSourceId = viewportLayerSourceId != null
    ? Number(viewportLayerSourceId)
    : (pageLayerSourceId != null ? Number(pageLayerSourceId) : (pageSourceDeviceId != null ? Number(pageSourceDeviceId) : null));
  const effectiveRoomId = syntheticRoomList && syntheticRoomId != null && Number.isFinite(syntheticRoomId)
   ? Number(syntheticRoomId)
   : (syntheticSourceList
      ? ((selectedRoomId != null && Number.isFinite(selectedRoomId))
         ? Number(selectedRoomId)
         : (syntheticSourceRoomId != null && Number.isFinite(syntheticSourceRoomId) ? Number(syntheticSourceRoomId) : effectiveRoomIdBase))
      : effectiveRoomIdBase);
  const buttonTagIdBase = buttonScope.buttonTagId;
  const buttonTagId = syntheticRoomList && syntheticRoomTagId != null && Number.isFinite(syntheticRoomTagId)
   ? Number(syntheticRoomTagId)
   : buttonTagIdBase;
  const effectiveSourceIdResolved = syntheticSourceList && syntheticSourceDeviceId != null && Number.isFinite(syntheticSourceDeviceId)
   ? Number(syntheticSourceDeviceId)
   : effectiveSourceId;
   const scopedButtonId = buttonScope.buttonId;
   const macroIds = Array.isArray(bindings.macroIds) ? bindings.macroIds : [];
   const variableIds = Array.isArray(bindings.variableIds) ? bindings.variableIds : [];
   const macroStepIds = Array.isArray(bindings.macroStepIds) ? bindings.macroStepIds : [];
  const lowerLabel = String(keyTokenResolved || "").trim().toLowerCase();
   if (buttonTagId != null) {{
    let programRef = "none";
    const firstMacroId = macroIds.length ? Number(macroIds[0]) : null;
    const firstVarId = variableIds.length ? Number(variableIds[0]) : null;
    const firstMacroStepId = macroStepIds.length ? Number(macroStepIds[0]) : null;
    if (lowerLabel === "macro" || lowerLabel === "macros" || lowerLabel === "system macro" || lowerLabel === "system macros") {{
     if (firstMacroId != null && Number.isFinite(firstMacroId)) programRef = `macro:${{firstMacroId}}`;
    }} else if (lowerLabel === "macrostep" || lowerLabel === "macrosteps" || lowerLabel === "macro step" || lowerLabel === "macro steps") {{
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
    refs.effectiveSourceId = effectiveSourceIdResolved;
  if (syntheticRoomList) {{
   if (syntheticRoomId != null && Number.isFinite(syntheticRoomId)) refs.syntheticRoomId = Number(syntheticRoomId);
   if (syntheticRoomTagId != null && Number.isFinite(syntheticRoomTagId)) refs.syntheticRoomTagId = Number(syntheticRoomTagId);
  }}
  if (syntheticSourceList) {{
   if (syntheticSourceRoomId != null && Number.isFinite(syntheticSourceRoomId)) refs.syntheticSourceRoomId = Number(syntheticSourceRoomId);
   if (syntheticSourceDeviceId != null && Number.isFinite(syntheticSourceDeviceId)) refs.syntheticSourceDeviceId = Number(syntheticSourceDeviceId);
  }}
    refs.programRef = programRef;
    if (apexScopeSource.audioScope && typeof apexScopeSource.audioScope === "object" && apexScopeSource.audioScope.wrapperDeviceId != null && rtiAddress != null && effectiveRoomId != null) {{
     const wrapperDeviceId = Number(apexScopeSource.audioScope.wrapperDeviceId);
     const targetKey = `tt2_audio:${{Number(rtiAddress)}}:${{scopeType}}:${{Number(effectiveRoomId)}}:${{wrapperDeviceId}}:${{Number(buttonTagId)}}:${{keyTokenResolved}}`;
     return {{
      targetKey,
      kind: scope,
      targetName,
      refs
     }};
    }}
    if (rtiAddress != null && effectiveRoomId != null && effectiveSourceIdResolved != null) {{
     const targetKey = `tt2:${{Number(rtiAddress)}}:${{scopeType}}:${{Number(effectiveRoomId)}}:${{Number(effectiveSourceIdResolved)}}:${{Number(buttonTagId)}}:${{programRef}}:${{keyTokenResolved}}`;
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
     const targetKey = `tt_ui:${{Number(rtiAddress)}}:${{sharedFlag}}:${{scopeLayerId}}:${{Number(scopedButtonId)}}:${{keyTokenResolved}}`;
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
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{buttonId}}:${{keyTokenResolved}}`;
  }} else if (vpButtonId && deviceId != null && pageId != null) {{
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{keyTokenResolved}}`;
  }} else if (deviceId != null && pageId != null && buttonId != null) {{
   targetKey = `btn:${{deviceId}}:${{pageId}}:${{buttonId}}:${{keyTokenResolved}}`;
  }} else {{
   targetKey = `btn:${{keyTokenResolved}}`;
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
  const m = (meta && typeof meta === "object") ? meta : {{}};
  rows.querySelectorAll('.row').forEach(row=>{{
   const label = String(row.querySelector('.n')?.textContent || '').trim();
   if (!label) return;
   const target = buildTargetPayload(ctxBtn, m, label);
   if (!target?.targetKey) return;
   const rowUi = rowStatusByTargetKey.get(target.targetKey);
   if (!rowUi) return;
   passAllQueue.push({{ label, rowUi }});
  }});
  if (!passAllQueue.length) return;
  passAllContext = {{ ctxBtn: ctxBtn || null, meta: m }};
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

 async function postResultWs(ctxBtn, meta, targetLabel, outcome, failNote, rowUi, isRevert) {{
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
    target:{{targetKey:target.targetKey,kind:target.kind,refs:{{...(target.refs||{{}}), ...(isRevert ? {{ revertedFrom: "PASS" }} : {{}})}},targetName:target.targetName}},
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
   passBtn.addEventListener('click', e=>{{e.stopPropagation(); const nextOutcome = rowUi.currentOutcome === 'PASS' ? 'UNTESTED' : 'PASS'; postResultWs(ctxBtn, meta, label, nextOutcome, null, rowUi, nextOutcome === 'UNTESTED');}});
   failBtn.addEventListener('click', e=>{{e.stopPropagation(); postResultWs(ctxBtn, meta, label, 'FAIL', noteEl ? noteEl.value : '', rowUi);}});
  }});
 }}
 function bindTestButtonClicks(root) {{
  const scope=root||document;
  scope.querySelectorAll('.test-btn').forEach(b=>{{
   if (b.dataset.boundTestBtn) return;
   b.dataset.boundTestBtn='1';
   b.addEventListener('click',()=>{{
    const wrap=b.closest('.btn-wrap');
    if (wrap && String(wrap.dataset.syntheticRoomList || '') === '1') {{
      setSelectedRoom(wrap.dataset.syntheticRoomId);
    }}
     const m=JSON.parse(b.dataset.meta||'{{}}');
     const suffix=(APP_UI.testingPopup?.includeButtonTypeInTitle&&m.buttonType)?` (${{m.buttonType}})`:''; 
     pt.textContent=(APP_UI.testingPopup?.titleTemplate||'{{category}} Test - {{identity}}').replace('{{category}}',m.category).replace('{{identity}}',m.identity)+suffix;
     rows.innerHTML=(m.targets||[]).map(t=>`<div class='row'><div class='row-head'><div class='n'>${{esc(t)}}</div></div><div class='row-meta'><div class='actions'><button>Pass</button><button disabled title='Enter a fail note to enable'>Fail</button></div><div class='row-last-test' aria-live='polite'></div></div><textarea placeholder='Fail note (required for Fail)' style='min-height:70px;'></textarea></div>`).join('')||"<div class='row'><div class='n'>No true test targets.</div></div>";
     clearPassAllQueue();
     setPostStatus('','');
     if (passAllBtn) {{
      const targets = Array.isArray(m.targets) ? m.targets : [];
      const showPassAll = targets.length > 1;
      passAllBtn.hidden = !showPassAll;
      passAllBtn.disabled = !showPassAll;
      passAllBtn.onclick = showPassAll ? (() => queuePassAll(b, m)) : null;
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
  pageEl.querySelectorAll('.vp-box, .vp-btn, .synthetic-list-scroll.vp-btn').forEach(el=>{{
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
  function computeViewportPopupBounds() {{
   const usable=document.getElementById('rtiUsableCanvas') || document.getElementById('rtiCanvas');
   if (!usable) return null;
   const ur=usable.getBoundingClientRect();
   const controls={{
    top:Number(APP_UI_CONTROLS.top||0),
    bottom:Number(APP_UI_CONTROLS.bottom||0),
    left:Number(APP_UI_CONTROLS.left||0),
    right:Number(APP_UI_CONTROLS.right||0),
   }};
   let expandedContractWidth=NaN;
   try {{
    const rootStyle=getComputedStyle(document.documentElement);
    expandedContractWidth=Number.parseFloat(String(rootStyle.getPropertyValue('--controls-expanded-w')||'').replace('px','').trim());
   }} catch (_e) {{}}
   const effectiveLeft=Number.isFinite(expandedContractWidth) ? Math.max(0, expandedContractWidth) : controls.left;
   const effectiveRight=Number.isFinite(expandedContractWidth) ? Math.max(0, expandedContractWidth) : controls.right;
   let left=effectiveLeft;
   let top=controls.top;
   let width=Math.max(1, window.innerWidth - effectiveLeft - effectiveRight);
   let height=Math.max(1, window.innerHeight - controls.top - controls.bottom);
   if (!Number.isFinite(left) || !Number.isFinite(top) || !Number.isFinite(width) || !Number.isFinite(height) || width <= 1 || height <= 1) {{
    left=ur.left;
    top=ur.top;
    width=Math.max(1, ur.width);
    height=Math.max(1, ur.height);
   }}
   return {{
    left,
    top,
    width,
    height,
   }};
  }}
  function syncViewportPopupBounds() {{
   const popup=document.getElementById('vpPopup');
   if (!popup) return;
   const bounds=computeViewportPopupBounds();
   if (!bounds) return;
   popup.style.left=`${{bounds.left}}px`;
   popup.style.top=`${{bounds.top}}px`;
   popup.style.width=`${{bounds.width}}px`;
   popup.style.height=`${{bounds.height}}px`;
  }}
  function waitForStableViewportBounds(onStable) {{
   let prev=null;
   let stableFrames=0;
   let ticks=0;
   const MAX_TICKS=10;
   const EPS=0.75;
   const step=() => {{
    if (!viewportMode.active) return;
    const cur=computeViewportPopupBounds();
    if (cur && prev) {{
     const stable=
      Math.abs(cur.left - prev.left) <= EPS &&
      Math.abs(cur.top - prev.top) <= EPS &&
      Math.abs(cur.width - prev.width) <= EPS &&
      Math.abs(cur.height - prev.height) <= EPS;
     stableFrames = stable ? (stableFrames + 1) : 0;
    }}
    prev=cur;
    ticks += 1;
    if (stableFrames >= 1 || ticks >= MAX_TICKS) {{
     onStable();
     return;
    }}
    requestAnimationFrame(step);
   }};
   requestAnimationFrame(step);
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
	    const els=popupElements();
	    if (!els.popup) return;
	    syncViewportPopupBounds();
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

  stage.querySelectorAll('.vp-popup-vcontent .synthetic-list-scroll').forEach(shell=>{{
   const sl=Number(shell.dataset.srcLeft||0)*scale;
   const st=Number(shell.dataset.srcTop||0)*scale;
   const sw=Number(shell.dataset.srcWidth||0)*scale;
   const sh=Number(shell.dataset.srcHeight||0)*scale;
   shell.style.left=`${{sl}}px`;
   shell.style.top=`${{st}}px`;
   shell.style.width=`${{sw}}px`;
   shell.style.height=`${{sh}}px`;
   shell.querySelectorAll('.btn-wrap.vp-btn').forEach(inner=>{{
    const il=Number(inner.dataset.srcLeft||0)*scale;
    const it=Number(inner.dataset.srcTop||0)*scale;
    const iw=Number(inner.dataset.srcWidth||0)*scale;
    const ih=Number(inner.dataset.srcHeight||0)*scale;
    inner.style.left=`${{il}}px`;
    inner.style.top=`${{it}}px`;
    inner.style.width=`${{iw}}px`;
    inner.style.height=`${{ih}}px`;
   const btn=inner.querySelector('.test-btn');
    if (btn) {{
     const buttonFontPx=resolveButtonFontPx(inner, scale);
     btn.style.fontSize=`${{buttonFontPx}}px`;
     btn.style.borderRadius=`${{Math.max(2, deviceButtonRadiusBase()*scale)}}px`;
     const linkHit=inner.querySelector('.page-link-hit');
     if (linkHit) applyLinkSizing(linkHit, buttonFontPx, scale);
    }}
   }});
  }});
  stage.querySelectorAll('.btn-wrap.vp-btn[data-src-left]').forEach(el=>{{
   if (el.closest('.synthetic-list-scroll')) return;
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
    const buttonFontPx=resolveButtonFontPx(el, scale);
    btn.style.fontSize=`${{buttonFontPx}}px`;
    btn.style.borderRadius=`${{Math.max(2, deviceButtonRadiusBase()*scale)}}px`;
    const linkHit=el.querySelector('.page-link-hit');
    if (linkHit) applyLinkSizing(linkHit, buttonFontPx, scale);
   }}
  }});
  stage.querySelectorAll('.vp-popup-vcontent .test-btn').forEach(btn=>{{
   const wrap=btn.closest('.btn-wrap');
   if (wrap && wrap.dataset && wrap.dataset.srcLeft!=null) return;
   if (!btn.dataset.baseFontPx) {{
    const base=Number.parseFloat(getComputedStyle(btn).fontSize||'0');
    btn.dataset.baseFontPx=String(Number.isFinite(base)&&base>0?base:10);
   }}
   const basePx=Number(btn.dataset.baseFontPx||10);
   btn.style.fontSize=`${{Math.max(1, basePx*textZoomFactor())}}px`;
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
   const shellNodes=[...pageEl.querySelectorAll(`.synthetic-list-scroll.vp-btn[data-vp="${{vpIndex}}"]`)].filter(shell=>{{
    if (activeFrame!=null && Number(shell.dataset.frame)!==Number(activeFrame)) return false;
    return true;
   }});
   const skipBtns=new Set();
   shellNodes.forEach(shell=>{{
    shell.querySelectorAll('.btn-wrap.vp-btn').forEach(b=>skipBtns.add(b));
   }});
   const btnNodes=[...pageEl.querySelectorAll(`.btn-wrap.vp-btn[data-vp="${{vpIndex}}"]`)];
   const frameFiltered=btnNodes.filter(node=>{{
    if (skipBtns.has(node)) return false;
    return activeFrame==null || Number(node.dataset.frame)===Number(activeFrame);
   }});
   [...shellNodes, ...frameFiltered].forEach(node=>{{
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
	   const roots=[];
	   shellNodes.forEach(shell=>roots.push({{kind:'shell', node:shell}}));
	   frameFiltered.forEach(node=>roots.push({{kind:'btn', node}}));
	   roots.forEach(({{kind, node}})=>{{
	     const clone=node.cloneNode(true);
	     clone.style.display='';
	     clone.style.zIndex='1';
	     clone.querySelectorAll('.test-btn').forEach(tb=>{{
	      tb.removeAttribute('data-bound-test-btn');
	      try {{ delete tb.dataset.boundTestBtn; }} catch (_) {{}}
	     }});
	    if (kind==='shell') {{
	     clone.dataset.srcLeft=String(Number(node.dataset.left||0) - vpLeft);
	     clone.dataset.srcTop=String(Number(node.dataset.top||0) - vpTop);
	     clone.dataset.srcWidth=String(Number(node.dataset.width||0));
	     clone.dataset.srcHeight=String(Number(node.dataset.height||0));
	     clone.querySelectorAll('.btn-wrap.vp-btn').forEach(innerClone=>{{
	      innerClone.dataset.srcLeft=String(Number(innerClone.dataset.left||0));
	      innerClone.dataset.srcTop=String(Number(innerClone.dataset.top||0));
	      innerClone.dataset.srcWidth=String(Number(innerClone.dataset.width||0));
	      innerClone.dataset.srcHeight=String(Number(innerClone.dataset.height||0));
	     }});
	    }} else {{
	     clone.dataset.srcLeft=String(Number(node.dataset.left||0) - vpLeft);
	     clone.dataset.srcTop=String(Number(node.dataset.top||0) - vpTop);
	     clone.dataset.srcWidth=String(Number(node.dataset.width||0));
	     clone.dataset.srcHeight=String(Number(node.dataset.height||0));
	    }}
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
  overlay.removeAttribute('hidden');
  viewportRoot.classList.add('viewport-mode');
  focusViewportElements();
  // Wait until shell/side-panel geometry stops moving, then size the popup once and render.
  // Doing layout before this (or re-layout in a second pass) makes the viewer jump when bounds settle.
  const openViewportWhenStable=() => {{
   if (!viewportMode.active) return;
   syncViewportPopupBounds();
   popup.removeAttribute('hidden');
   renderViewportPopup();
   positionPopupIndicator();
  }};
  waitForStableViewportBounds(openViewportWhenStable);
  syncLayerLocksForActiveLayers(false).finally(()=>{{ renderLayerPanel(); applyLayerVisibility(); }});
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
  syncLayerLocksForActiveLayers(false).finally(()=>{{ renderLayerPanel(); applyLayerVisibility(); }});
  renderLayerPanel();
  syncViewportControls();
  applyLayerVisibility();
}}
function _syncPersistedLayerLocksFromRows(rows, replaceAll) {{
 const list = Array.isArray(rows) ? rows : [];
 if (replaceAll) persistedLayerLocksByScope.clear();
 list.forEach((row) => {{
  const rowScope=String(row?.scopeKey||'').trim();
  const layerKey=String(row?.layerKey||'').trim();
  if (!rowScope || !layerKey) return;
  const lockKey=layerLockCompositeKey(rowScope, layerKey);
  if (Boolean(row?.locked)) {{
   persistedLayerLocksByScope.set(lockKey, {{visible:Boolean(row?.visible), locked:true}});
  }} else {{
   persistedLayerLocksByScope.delete(lockKey);
  }}
 }});
}}
function _flushLayerLockWsQueue() {{
 if (!techWs || techWs.readyState !== 1) return;
 const items=Array.from(pendingLayerLockWsByKey.entries());
 items.forEach(([key, payload]) => {{
  try {{
   techWs.send(JSON.stringify(payload));
   pendingLayerLockWsByKey.delete(key);
   _logTechWs("send", payload?.type || "");
  }} catch (_e) {{}}
 }});
}}
function _queueLayerLockStateForWs(scopeKey, layerKey, visible, locked) {{
 const scope=String(scopeKey||'').trim();
 const layer=String(layerKey||'').trim();
 if (!scope || !layer) return;
 const payload={{
  type:"layer_lock.set",
  scopeKey:scope,
  layerKey:layer,
  visible:Boolean(visible),
  locked:Boolean(locked),
 }};
 const key=layerLockCompositeKey(scope, layer);
 pendingLayerLockWsByKey.set(key, payload);
 _flushLayerLockWsQueue();
 if (pendingLayerLockWsByKey.has(key)) _connectTechWs();
}}
function layerScopeKey(state) {{
 return [PROJECT_SESSION_KEY, state?.deviceName||'', state?.pageName||''].join('::');
}}
function layerLockCompositeKey(scopeKey, layerKey) {{
 return `${{String(scopeKey||'')}}::${{String(layerKey||'')}}`;
}}
function normalizeSharedLayerId(layer) {{
 const raw=layer && typeof layer==='object' ? layer.sharedLayerId : null;
 if (raw == null) return null;
 const value=Number(raw);
 if (!Number.isFinite(value)) return null;
 const normalized=Math.trunc(value);
 return normalized > 0 ? normalized : null;
}}
function layerPersistenceScopeKey(layer, defaultScopeKey) {{
 const fallbackScope=String(defaultScopeKey||'').trim();
 if (viewportMode.active) return fallbackScope;
 const sharedLayerId=normalizeSharedLayerId(layer);
 if (sharedLayerId == null) return fallbackScope;
 const state=activePageState();
 return [PROJECT_SESSION_KEY, state?.deviceName||'', `shared-layer:${{sharedLayerId}}`].join('::');
}}
function layerPersistenceLayerKey(layer) {{
 const sharedLayerId=normalizeSharedLayerId(layer);
 if (sharedLayerId == null) return String(layer?.key||'');
 return `shared-layer-${{sharedLayerId}}`;
}}
function layerPersistenceLockKey(layer, defaultScopeKey) {{
 const scopeKey=layerPersistenceScopeKey(layer, defaultScopeKey);
 const layerKey=layerPersistenceLayerKey(layer);
 return layerLockCompositeKey(scopeKey, layerKey);
}}
function syncLayerLocksForActiveLayers(_force) {{
 return Promise.resolve();
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
function isLayerLocked(scopeKey, layer) {{
 const lockKey=layerPersistenceLockKey(layer, scopeKey);
 return persistedLayerLocksByScope.has(lockKey) && !sessionUnlockedLayerLocks.has(lockKey);
}}
function persistedLayerVisibility(scopeKey, layer) {{
 const lockKey=layerPersistenceLockKey(layer, scopeKey);
 const row=persistedLayerLocksByScope.get(lockKey);
 return row ? Boolean(row.visible) : true;
}}
function ensureActiveLayerVisibility() {{
 const layers=activeLayerList();
 const scopeKey=activeLayerScopeKey();
 const stored=loadLayerVisibility(scopeKey);
 const visibility=(stored && typeof stored==='object') ? stored : Object.fromEntries((layers||[]).map(layer=>[layer.key,true]));
 (layers||[]).forEach(layer=>{{ if (!(layer.key in visibility)) visibility[layer.key]=true; }});
 (layers||[]).forEach(layer=>{{
  if (isLayerLocked(scopeKey, layer)) {{
   visibility[layer.key]=persistedLayerVisibility(scopeKey, layer);
  }}
 }});
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
function hkTouchSourceSize() {{
 const sz=ORIENTATION_STATE.sizes && ORIENTATION_STATE.sizes[currentOrientation];
 const hk=sz && sz.hardKeyLayout;
 if (hk && Number(hk.touchSourceWidth)>0 && Number(hk.touchSourceHeight)>0) {{
  return {{width:Number(hk.touchSourceWidth), height:Number(hk.touchSourceHeight)}};
 }}
 const s=currentOrientationSize();
 return {{width:Number(s.width||0), height:Number(s.height||0)}};
}}
function containScale(intrinsicW, intrinsicH, fitW, fitH) {{
 const iw=Number(intrinsicW)||0;
 const ih=Number(intrinsicH)||0;
 const fw=Number(fitW)||0;
 const fh=Number(fitH)||0;
 if (iw<=0 || ih<=0 || fw<=0 || fh<=0) return 0;
 return Math.max(0, Math.min(fw/iw, fh/ih));
}}
function layoutTouchscreenDevice(usableW, usableH, touchW, touchH, margin) {{
 const uw=Number(usableW)||0;
 const uh=Number(usableH)||0;
 const tw=Number(touchW)||0;
 const th=Number(touchH)||0;
 const m=margin==null ? 20 : Number(margin);
 if (uw<=0 || uh<=0 || tw<=0 || th<=0) return null;
 const fitW=Math.max(1, uw-2*m);
 const fitH=Math.max(1, uh-2*m);
 const scale=containScale(tw, th, fitW, fitH);
 if (!Number.isFinite(scale) || scale<=0) return null;
 const width=tw*scale;
 const height=th*scale;
 return {{scale, left:(uw-width)/2, top:(uh-height)/2, width, height}};
}}
function layoutHardKeyTouchColumn(usableW, usableH, touchW, touchH, margin) {{
 const uw=Number(usableW)||0;
 const uh=Number(usableH)||0;
 const tw=Number(touchW)||0;
 const th=Number(touchH)||0;
 const m=margin==null ? 20 : Number(margin);
 if (uw<=0 || uh<=0 || tw<=0 || th<=0) return null;
 const halfW=Math.max(1, (uw-2*m)/2);
 const fitH=Math.max(1, uh-2*m);
 const scale=containScale(tw, th, halfW, fitH);
 if (!Number.isFinite(scale) || scale<=0) return null;
 const width=tw*scale;
 const height=th*scale;
 const top=Math.max(0, (uh-height)/2);
 const left=0.25*uw-width/2;
 return {{scale, left, top, width, height, centerX:0.25*uw, centerY:top+height/2}};
}}
function layoutHardKeyStripColumn(usableW, usableH, touchH, designW, designH, touchColumnWidth, margin) {{
 const uw=Number(usableW)||0;
 const uh=Number(usableH)||0;
 const th=Number(touchH)||0;
 const dw=Number(designW)||0;
 const dh=Number(designH)||0;
 const touchColW=Number(touchColumnWidth)||0;
 const m=margin==null ? 20 : Number(margin);
 if (uw<=0 || uh<=0 || th<=0 || dw<=0 || dh<=0 || touchColW<=0) return null;
 const halfW=Math.max(1, (uw-2*m)/2);
 const fitH=Math.max(1, uh-2*m);
 const stripW0=th*dw/dh;
 const candidates=[containScale(stripW0, th, halfW, fitH)];
 if (stripW0>0) candidates.push(touchColW/stripW0);
 const scale=Math.min.apply(null, candidates.filter(v=>Number.isFinite(v)&&v>0));
 if (!Number.isFinite(scale) || scale<=0) return null;
 const height=th*scale;
 const width=height*dw/dh;
 const top=Math.max(0, (uh-height)/2);
 const left=0.75*uw-width/2;
 return {{scale, left, top, width, height, centerX:0.75*uw, centerY:top+height/2}};
}}
function hardKeyBoxesAtScales(usableW, usableH, touchW, touchH, designW, designH, touchScale, stripScale) {{
 const uw=Number(usableW)||0;
 const uh=Number(usableH)||0;
 const ts=Number(touchScale)||0;
 const ss=Number(stripScale)||0;
 const tw=Number(touchW)*ts;
 const thTouch=Number(touchH)*ts;
 const stripTh=Number(touchH)*ss;
 const stripW=stripTh*Number(designW)/Number(designH);
 const touchLeft=0.25*uw-tw/2;
 const hkLeft=0.75*uw-stripW/2;
 const touchTop=Math.max(0, (uh-thTouch)/2);
 const stripTop=Math.max(0, (uh-stripTh)/2);
 const touch={{
  left:touchLeft,
  top:touchTop,
  width:tw,
  height:thTouch,
  centerX:0.25*uw,
  centerY:touchTop+thTouch/2,
 }};
 const strip={{
  left:hkLeft,
  top:stripTop,
  width:stripW,
  height:stripTh,
  centerX:0.75*uw,
  centerY:stripTop+stripTh/2,
 }};
 const asmLeft=Math.min(touchLeft, hkLeft);
 const asmTop=Math.min(touchTop, stripTop);
 const asmRight=Math.max(touchLeft+tw, hkLeft+stripW);
 const asmBottom=Math.max(touchTop+thTouch, stripTop+stripTh);
 const assembly={{
  left:asmLeft,
  top:asmTop,
  width:asmRight-asmLeft,
  height:asmBottom-asmTop,
  centerX:0.5*uw,
  centerY:asmTop+(asmBottom-asmTop)/2,
 }};
 return {{touchScale:ts, stripScale:ss, scale:ss, touch, strip, assembly}};
}}
function layoutHardKeySplit(usableW, usableH, touchW, touchH, designW, designH, margin) {{
 const uw=Number(usableW)||0;
 const uh=Number(usableH)||0;
 const tw=Number(touchW)||0;
 const th=Number(touchH)||0;
 const dw=Number(designW)||0;
 const dh=Number(designH)||0;
 const m=margin==null ? 20 : Number(margin);
 if (uw<=0 || uh<=0 || tw<=0 || th<=0 || dw<=0 || dh<=0) return null;
 const touchCol=layoutHardKeyTouchColumn(uw, uh, tw, th, m);
 if (!touchCol) return null;
 const stripCol=layoutHardKeyStripColumn(uw, uh, th, dw, dh, touchCol.width, m);
 if (!stripCol) return null;
 const touchScale=Number(touchCol.scale)||0;
 const stripScale=Number(stripCol.scale)||0;
 if (!Number.isFinite(touchScale) || touchScale<=0 || !Number.isFinite(stripScale) || stripScale<=0) return null;
 const out=hardKeyBoxesAtScales(uw, uh, tw, th, dw, dh, touchScale, stripScale);
 out._usableW=uw;
 out._usableH=uh;
 out._touchW=tw;
 out._touchH=th;
 out._designW=dw;
 out._designH=dh;
 return out;
}}
function layoutHardKeySplitAtScale(layout, touchScale, stripScale) {{
 if (!layout) return null;
 const ss=(stripScale==null) ? Number(touchScale) : Number(stripScale);
 const out=hardKeyBoxesAtScales(
  layout._usableW, layout._usableH, layout._touchW, layout._touchH, layout._designW, layout._designH, touchScale, ss
 );
 out._usableW=layout._usableW;
 out._usableH=layout._usableH;
 out._touchW=layout._touchW;
 out._touchH=layout._touchH;
 out._designW=layout._designW;
 out._designH=layout._designH;
 return out;
}}
function applyHardKeySplitLayout(activePage, pos) {{
 if (!activePage||!pos||!pos.assembly) return;
 const asm=pos.assembly;
 const rel=(box)=>({{
  left:Number(box.left)-asm.left,
  top:Number(box.top)-asm.top,
  width:Number(box.width),
  height:Number(box.height),
 }});
 const touch=rel(pos.touch);
 const strip=rel(pos.strip);
 const leftCol=activePage.querySelector('.hk-split-left');
 const rightCol=activePage.querySelector('.hk-split-right');
 const touchStack=activePage.querySelector('.hk-touch-stack');
 const place=(el, left, top, width, height)=>{{
  if (!el) return;
  el.style.position='absolute';
  el.style.left=`${{left}}px`;
  el.style.top=`${{top}}px`;
  el.style.width=`${{width}}px`;
  el.style.height=`${{height}}px`;
  el.style.right='auto';
  el.style.bottom='auto';
 }};
 place(leftCol, touch.left, touch.top, touch.width, touch.height);
 place(rightCol, strip.left, strip.top, strip.width, strip.height);
 if (touchStack) {{
  touchStack.style.width=`${{touch.width}}px`;
  touchStack.style.height=`${{touch.height}}px`;
 }}
 const frameW=Math.max(1, Math.floor(strip.width));
 const frameH=Math.max(1, Math.floor(strip.height));
 if (rightCol) {{
  rightCol.style.setProperty('--frame-w', `${{frameW}}px`);
  rightCol.style.setProperty('--frame-h', `${{frameH}}px`);
  const frame=rightCol.querySelector('.frame');
  if (frame) {{
   frame.style.setProperty('--frame-w', `${{frameW}}px`);
   frame.style.setProperty('--frame-h', `${{frameH}}px`);
   frame.style.removeProperty('transform');
   frame.style.removeProperty('transform-origin');
  }}
 }}
}}
function centerRtiCanvasOnHkAssembly(pos) {{
 const rtiCanvas=document.getElementById('rtiCanvas');
 if (!rtiCanvas||!pos||!pos.assembly) return;
 const cx=Number(pos.assembly.centerX)||0;
 const cy=Number(pos.assembly.centerY)||0;
 const maxL=Math.max(rtiCanvas.scrollWidth-rtiCanvas.clientWidth, 0);
 const maxT=Math.max(rtiCanvas.scrollHeight-rtiCanvas.clientHeight, 0);
 rtiCanvas.scrollLeft=clamp(cx-(rtiCanvas.clientWidth/2), 0, maxL);
 rtiCanvas.scrollTop=clamp(cy-(rtiCanvas.clientHeight/2), 0, maxT);
}}
function applyOrientationState() {{
 const short=currentOrientation==='landscape' ? 'l' : 'p';
 document.querySelectorAll('.orientation-btn').forEach(button=>button.classList.toggle('active', button.dataset.orientation===currentOrientation));
 document.querySelectorAll('.device-page .vp-box, .device-page .btn-wrap, .device-page .synthetic-list-scroll').forEach(el=>{{
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
     applyLayerVisibility();
     applyRtiLayout();
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
 const scopeKey=activeLayerScopeKey();
  const layers=activeLayerList();
  if (!layers.length) {{
    list.innerHTML='';
    panel.setAttribute('hidden','hidden');
    return;
  }}
  const layerByKey=new Map((layers||[]).map(layer=>[String(layer?.key||''), layer]));
 list.innerHTML=layers.map(layer=>{{
  const locked=isLayerLocked(scopeKey, layer);
  const icon=locked ? 'lock' : 'lock_open_right';
  return `<button class="layer-toggle${{isLayerVisible(layer.key)?'':' is-inactive'}}${{locked?' is-locked':''}}" type="button" data-layer-key="${{esc(layer.key)}}" aria-pressed="${{isLayerVisible(layer.key)?'true':'false'}}"><span class="layer-lock-toggle" role="button" aria-label="${{locked?'Unlock layer':'Lock layer'}}"><span class="layer-lock-icon material-symbols-outlined" aria-hidden="true">${{icon}}</span></span><span class="layer-toggle-label">${{esc(layer.name)}}</span></button>`;
 }}).join('');
 panel.removeAttribute('hidden');
  list.querySelectorAll('.layer-toggle').forEach(button=>button.addEventListener('click',(event)=>{{
    const key=button.dataset.layerKey||'';
    const currentScopeKey=activeLayerScopeKey();
    const layer=layerByKey.get(String(key)) || {{key}};
    const lockScopeKey=layerPersistenceScopeKey(layer, currentScopeKey);
    const lockLayerKey=layerPersistenceLayerKey(layer);
    const lockKey=layerLockCompositeKey(lockScopeKey, lockLayerKey);
    const lockBtn=event.target && event.target.closest ? event.target.closest('.layer-lock-toggle') : null;
    if (lockBtn) {{
      event.preventDefault();
      event.stopPropagation();
      const visibility=ensureActiveLayerVisibility();
      if (isLayerLocked(currentScopeKey, layer)) {{
        sessionUnlockedLayerLocks.add(lockKey);
        renderLayerPanel();
        applyLayerVisibility();
        return;
      }}
      sessionUnlockedLayerLocks.delete(lockKey);
      const lockedVisible=visibility[key] !== false;
      persistedLayerLocksByScope.set(lockKey, {{visible:Boolean(lockedVisible), locked:true}});
      _queueLayerLockStateForWs(lockScopeKey, lockLayerKey, Boolean(lockedVisible), true);
      renderLayerPanel();
      applyLayerVisibility();
      return;
    }}
    if (isLayerLocked(currentScopeKey, layer)) return;
    const visibility=ensureActiveLayerVisibility();
    visibility[key]=!(visibility[key] !== false);
    saveLayerVisibility(currentScopeKey, visibility);
    renderLayerPanel();
    applyLayerVisibility();
  }}));
}}
 function applyLayerVisibility() {{
  const pageEl=activePageEl();
  if (!pageEl) return;
 applySelectedRoomToSourceRows(pageEl);
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
  pageEl.querySelectorAll('.hk-split-right[data-owner-layer-key]').forEach(el=>{{
   const layerKey=String(el.dataset.ownerLayerKey||'');
   el.style.display=isLayerVisible(layerKey)?'':'none';
 }});
  pageEl.querySelectorAll('.synthetic-list-scroll').forEach(el=>{{
   const layerKey=String(el.dataset.ownerLayerKey||'');
   let baseVisible=String(el.dataset.visible||'1')==='1';
   const layerVisible=isLayerVisible(layerKey);
   let shouldShow=layerVisible && baseVisible;
   if (el.classList.contains('vp-btn')) {{
     // Viewport children should be gated by viewport orientation/frame/layer state, not stale data-visible.
     baseVisible=true;
     shouldShow=layerVisible && baseVisible;
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
  pageEl.querySelectorAll('.btn-wrap').forEach(el=>{{
   const layerKey=String(el.dataset.ownerLayerKey||'');
   let baseVisible=String(el.dataset.visible||'1')==='1';
   const layerVisible=isLayerVisible(layerKey);
   let shouldShow=layerVisible && baseVisible;
  if (String(el.dataset.syntheticSourceList || '') === '1' && String(el.dataset.selectedRoomMatch || '1') !== '1') {{
    shouldShow=false;
  }}
   if (el.classList.contains('vp-btn')) {{
     // Viewport children should be gated by viewport orientation/frame/layer state, not stale data-visible.
     baseVisible=true;
     shouldShow=layerVisible && baseVisible;
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
 syncSelectedRoomIndicator();
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
  function activeTextZoomPercent() {{
   return Number(currentTextZoomPercent||TEXT_ZOOM_DEFAULT);
  }}
  function textZoomFactor() {{
   return clamp(activeTextZoomPercent(), TEXT_ZOOM_MIN, TEXT_ZOOM_MAX)/100;
  }}
  function syncZoomResetText() {{
   const zoomControls=document.getElementById('zoomControls');
   if (!zoomControls) return;
   const zoomReset=zoomControls.querySelector('.zoom-reset');
   if (!zoomReset) return;
   zoomReset.textContent = `${{activeZoomPercent()}}%`;
  }}
  function syncTextZoomResetText() {{
   const value=`${{activeTextZoomPercent()}}%`;
   document.querySelectorAll('[data-control="text-zoom-reset"]').forEach(button=>{{
    const vertical=button.querySelector('.zoomPctVertical');
    if (vertical) vertical.textContent=value;
    else button.textContent=value;
   }});
  }}
  function resolveButtonFontPx(el, derivedScale) {{
   const sourceFont=Number(el?.dataset?.fontSize||APP_UI.buttonPresentation?.fallbackFontSize||10);
   const basePx=APP_UI.buttonPresentation?.scaleRtiDerivedFontSizes ? (sourceFont*derivedScale) : sourceFont;
   return Math.max(1, basePx*textZoomFactor());
  }}
  function applyLinkSizing(linkHit, buttonFontPx, derivedScale) {{
   if (!linkHit) return;
   const hitWidth=Number(linkHit.dataset.hitWidth||28)*derivedScale;
   const hitPadding=Number(linkHit.dataset.hitPadding||8)*derivedScale;
   linkHit.style.width=`${{hitWidth}}px`;
   linkHit.style.paddingRight=`${{hitPadding}}px`;
   linkHit.style.right='0';
   linkHit.style.fontSize=`${{buttonFontPx}}px`;
  }}
  function firstVisibleNode(nodes) {{
   if (!Array.isArray(nodes)) return null;
   for (const node of nodes) {{
    if (!node) continue;
    if (node.offsetParent!==null) return node;
   }}
   return nodes[0] || null;
  }}
  function zoomTelemetrySizes() {{
   const context=viewportMode.active ? document.getElementById('vpPopupStage') : activePageEl();
   const root=context || document;
   const button=firstVisibleNode(Array.from(root.querySelectorAll('.btn-wrap .test-btn')));
   const icon=firstVisibleNode(Array.from(root.querySelectorAll('.btn-wrap .page-link-icon')));
   const buttonTextPx=button ? Number.parseFloat(getComputedStyle(button).fontSize||'0') : 0;
   const linkIconPx=icon ? Number.parseFloat(getComputedStyle(icon).fontSize||'0') : 0;
   return {{
    buttonTextPx:Number.isFinite(buttonTextPx)?buttonTextPx:0,
    linkIconPx:Number.isFinite(linkIconPx)?linkIconPx:0
   }};
  }}
  function emitZoomTelemetry(reason) {{
   const sizes=zoomTelemetrySizes();
   try {{
    if (typeof console!=="undefined" && console.log) {{
     console.log('SENTINEL_ZOOM', {{
      reason:String(reason||''),
      viewportMode:Boolean(viewportMode.active),
      deviceZoomPercent:Number(currentZoomPercent||ZOOM_DEFAULT),
      textZoomPercent:activeTextZoomPercent(),
      activeZoomPercent:activeZoomPercent(),
      buttonTextPx:Number(sizes.buttonTextPx.toFixed(4)),
      linkIconPx:Number(sizes.linkIconPx.toFixed(4))
     }});
    }}
   }} catch (_e) {{}}
  }}
  function updateTextZoom(nextPercent) {{
   currentTextZoomPercent=clamp(nextPercent, TEXT_ZOOM_MIN, TEXT_ZOOM_MAX);
   syncTextZoomResetText();
   document.querySelectorAll('#vpPopup .vp-popup-vcontent .test-btn').forEach(btn=>{{
    const wrap=btn.closest('.btn-wrap');
    if (wrap && wrap.dataset && wrap.dataset.srcLeft!=null) return;
    if (!btn.dataset.baseFontPx) {{
     const base=Number.parseFloat(getComputedStyle(btn).fontSize||'0');
     btn.dataset.baseFontPx=String(Number.isFinite(base)&&base>0?base:10);
    }}
    const basePx=Number(btn.dataset.baseFontPx||10);
    btn.style.fontSize=`${{Math.max(1, basePx*textZoomFactor())}}px`;
   }});
   if (viewportMode.active) {{
    applyViewportPopupLayout();
    emitZoomTelemetry('text-zoom');
    return;
   }}
   scheduleRtiLayout('text-zoom');
  }}
  function textZoomAction(action) {{
   const normalized=String(action||'').toLowerCase();
   if (normalized==='inc') {{ updateTextZoom(activeTextZoomPercent()+TEXT_ZOOM_STEP); return; }}
   if (normalized==='dec') {{ updateTextZoom(activeTextZoomPercent()-TEXT_ZOOM_STEP); return; }}
   if (normalized==='reset') {{ updateTextZoom(TEXT_ZOOM_DEFAULT); return; }}
  }}
  window.__sentinelTextZoomAction=textZoomAction;
  window.__sentinelSyncTextZoomControls=syncTextZoomResetText;
  function applyHkTightClusterLayout(activePage) {{
   const canvas=document.getElementById('rtiDeviceCanvas');
   if (!canvas||!canvas.classList.contains('rti-device-canvas-hk')) return;
   canvas.querySelectorAll('.hk-split-right').forEach((zone)=>{{ zone.classList.remove('hk-tight-cluster'); }});
   canvas.querySelectorAll('.hk-cluster-rim').forEach((el)=>{{ el.remove(); }});
   if (!activePage) return;
   const HK_TIGHT_PAD=4;
   const ringStrokeRaw=getComputedStyle(document.documentElement).getPropertyValue('--sentinel-device-frame-ring-width').trim();
   const ringStroke=Math.max(0,parseFloat(ringStrokeRaw)||0)||3;
   activePage.querySelectorAll('.hk-split-right').forEach((zone)=>{{
    const frame=zone.querySelector('.frame');
    if (!frame) return;
    let boxes=[...frame.querySelectorAll('.box')].filter((b)=>b.querySelector('.hk-btn-wrap'));
    if (!boxes.length) boxes=[...frame.querySelectorAll('.box')];
    if (!boxes.length) return;
    let minL=Infinity,minT=Infinity,maxR=-Infinity,maxB=-Infinity;
    for (const el of boxes) {{
     const r=el.getBoundingClientRect();
     minL=Math.min(minL,r.left);
     minT=Math.min(minT,r.top);
     maxR=Math.max(maxR,r.right);
     maxB=Math.max(maxB,r.bottom);
    }}
    const uw=maxR-minL;
    const uh=maxB-minT;
    if (!Number.isFinite(uw)||!Number.isFinite(uh)||uw<=0||uh<=0) {{
     return;
    }}
    zone.classList.add('hk-tight-cluster');
    const zr=zone.getBoundingClientRect();
    const innerW=uw+2*HK_TIGHT_PAD;
    const innerH=uh+2*HK_TIGHT_PAD;
    const rim=document.createElement('div');
    rim.className='hk-cluster-rim';
    rim.setAttribute('aria-hidden','true');
    rim.style.cssText=
     'position:absolute;box-sizing:content-box;pointer-events:none;z-index:2147483647;'+
     `left:${{minL-HK_TIGHT_PAD-ringStroke-zr.left}}px;top:${{minT-HK_TIGHT_PAD-ringStroke-zr.top}}px;`+
     `width:${{innerW}}px;height:${{innerH}}px;`;
    zone.appendChild(rim);
   }});
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

const isHkDevice=rtiDeviceCanvas.classList.contains('rti-device-canvas-hk');
const DEVICE_CANVAS_MARGIN=20;
const zoomMul=clamp(Number(currentZoomPercent||ZOOM_DEFAULT), ZOOM_DEFAULT, ZOOM_MAX)/100;
const maxScale=Number(RTI_DEVICE_LAYOUT.maxScale ?? 10);
const minScale=Number(RTI_DEVICE_LAYOUT.minScale ?? 0.25);
let totalScale=1;
let hkTouchScale=1;
let hkStripScale=1;
let fittedWidth=0;
let fittedHeight=0;
let offsetLeft=0;
let offsetTop=0;
let hkSplitPos=null;
if (isHkDevice) {{
 const usableW=rtiCanvasWidth;
 const usableH=rtiCanvasHeight;
 const ts=hkTouchSourceSize();
 const touchW=Number(ts.width||0);
 const touchH=Number(ts.height||0);
 const designW=Number(rtiDeviceCanvas.dataset.hkDesignW||0);
 const designH=Number(rtiDeviceCanvas.dataset.hkDesignH||0);
 const baseLay=layoutHardKeySplit(usableW, usableH, touchW, touchH, designW, designH, DEVICE_CANVAS_MARGIN);
 let baseTouchScale=(baseLay && Number(baseLay.touchScale)>0) ? Number(baseLay.touchScale) : 1;
 let baseStripScale=(baseLay && Number(baseLay.stripScale)>0) ? Number(baseLay.stripScale) : baseTouchScale;
 if (!Boolean(RTI_DEVICE_LAYOUT.allowScaleAboveOne)) {{
  baseTouchScale=Math.min(baseTouchScale, 1);
  baseStripScale=Math.min(baseStripScale, 1);
 }}
 baseTouchScale=Math.min(maxScale, Math.max(minScale, baseTouchScale));
 baseStripScale=Math.min(maxScale, Math.max(minScale, baseStripScale));
 hkTouchScale=baseTouchScale*zoomMul;
 hkStripScale=baseStripScale*zoomMul;
 totalScale=hkStripScale;
 hkSplitPos=layoutHardKeySplitAtScale(baseLay, hkTouchScale, hkStripScale);
 const asm=(hkSplitPos && hkSplitPos.assembly) ? hkSplitPos.assembly : null;
 fittedWidth=asm ? asm.width : usableW;
 fittedHeight=asm ? asm.height : usableH;
 offsetLeft=asm ? asm.left : 0;
 offsetTop=asm ? asm.top : 0;
 const contentWidth=Math.max(rtiCanvasWidth, asm ? (asm.left+asm.width) : rtiCanvasWidth);
 const contentHeight=Math.max(rtiCanvasHeight, asm ? (asm.top+asm.height) : rtiCanvasHeight);
 rtiContent.style.width=`${{contentWidth}}px`;
 rtiContent.style.height=`${{contentHeight}}px`;
 rtiDeviceCanvas.style.left=`${{offsetLeft}}px`;
 rtiDeviceCanvas.style.top=`${{offsetTop}}px`;
 rtiDeviceCanvas.style.width=`${{fittedWidth}}px`;
 rtiDeviceCanvas.style.height=`${{fittedHeight}}px`;
 rtiDeviceCanvas.style.setProperty('--sentinel-device-scale', String(hkStripScale));
 rtiDeviceCanvas.style.setProperty('--sentinel-hk-touch-scale', String(hkTouchScale));
}} else {{
 const sourceSize=currentOrientationSize();
 const touchLay=layoutTouchscreenDevice(rtiCanvasWidth, rtiCanvasHeight, sourceSize.width, sourceSize.height, DEVICE_CANVAS_MARGIN);
 let baseScale=(touchLay && Number(touchLay.scale)>0) ? Number(touchLay.scale) : 1;
 if (!Boolean(RTI_DEVICE_LAYOUT.allowScaleAboveOne)) baseScale=Math.min(baseScale, 1);
 baseScale=Math.min(maxScale, Math.max(minScale, baseScale));
 totalScale=baseScale*zoomMul;
 fittedWidth=sourceSize.width*totalScale;
 fittedHeight=sourceSize.height*totalScale;
 const contentWidth=Math.max(rtiCanvasWidth,fittedWidth);
 const contentHeight=Math.max(rtiCanvasHeight,fittedHeight);
 offsetLeft=(contentWidth-fittedWidth)/2;
 offsetTop=(contentHeight-fittedHeight)/2;
 rtiContent.style.width=`${{contentWidth}}px`;
 rtiContent.style.height=`${{contentHeight}}px`;
 rtiDeviceCanvas.style.left=`${{offsetLeft}}px`;
 rtiDeviceCanvas.style.top=`${{offsetTop}}px`;
 rtiDeviceCanvas.style.width=`${{fittedWidth}}px`;
 rtiDeviceCanvas.style.height=`${{fittedHeight}}px`;
 rtiDeviceCanvas.style.removeProperty('--sentinel-device-scale');
}}
 currentTotalScale=totalScale;
 currentDeviceLeft=offsetLeft;
 currentDeviceTop=offsetTop;
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
 const hkElementScale=(el)=>{{
  if (!isHkDevice || !el) return totalScale;
  if (el.classList.contains('hk-btn-wrap')) return hkStripScale;
  if (el.closest('.hk-split-left')) return hkTouchScale;
  return totalScale;
 }};
 if (activePage) activePage.querySelectorAll('.vp-box').forEach(el=>{{
   const elScale=hkElementScale(el);
   const left=Number(el.dataset.left||0)*elScale;
   const top=Number(el.dataset.top||0)*elScale;
   const width=Number(el.dataset.width||0)*elScale;
   const height=Number(el.dataset.height||0)*elScale;
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
 }});

 if (activePage) activePage.querySelectorAll('.synthetic-list-scroll').forEach(el=>{{
   const elScale=hkElementScale(el);
   const left=Number(el.dataset.left||0)*elScale;
   const top=Number(el.dataset.top||0)*elScale;
   const width=Number(el.dataset.width||0)*elScale;
   const height=Number(el.dataset.height||0)*elScale;
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
  }});
 if (activePage) activePage.querySelectorAll('.synthetic-list-scroll .synthetic-list-scroll-pad').forEach(el=>{{
   const elScale=hkElementScale(el);
   const ph=Number(el.dataset.activePadHeight!=null ? el.dataset.activePadHeight : (el.dataset.padHeight||0))*elScale;
   el.style.height=`${{ph}}px`;
 }});
 if (activePage) activePage.querySelectorAll('.btn-wrap').forEach(el=>{{
   const isHk=el.classList.contains('hk-btn-wrap');
   if (!isHk) {{
   const elScale=hkElementScale(el);
   const left=Number(el.dataset.left||0)*elScale;
   const top=Number(el.dataset.top||0)*elScale;
   const width=Number(el.dataset.width||0)*elScale;
   const height=Number(el.dataset.height||0)*elScale;
   const inSyntheticList=String(el.dataset.syntheticSourceList||'')==='1' || String(el.dataset.syntheticRoomList||'')==='1';
   const shell=inSyntheticList ? el.closest('.synthetic-list-scroll') : null;
   const reserveRight=(shell && inSyntheticList) ? Math.max(4, (shell.offsetWidth-shell.clientWidth)+4) : 0;
   const adjustedWidth=Math.max(1, width-reserveRight);
   const adjustedLeft=left + (reserveRight/2);
   el.style.left=`${{adjustedLeft}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{adjustedWidth}}px`;
   el.style.height=`${{height}}px`;
   }}
   const button=el.querySelector('.test-btn');
    if (button) {{
      const elScale=hkElementScale(el);
      if (isHk) {{
       button.style.removeProperty('font-size');
      }} else {{
       const buttonFontPx=resolveButtonFontPx(el, elScale);
       button.style.fontSize=`${{buttonFontPx}}px`;
      }}
      button.style.borderRadius=`${{Math.max(2, deviceButtonRadiusBase()*elScale)}}px`;
      const linkHit=el.querySelector('.page-link-hit');
      if (linkHit) {{
       const buttonFontPx=isHk
        ? Number.parseFloat(getComputedStyle(button).fontSize||'0')
        : resolveButtonFontPx(el, elScale);
       if (buttonFontPx>0) applyLinkSizing(linkHit, buttonFontPx, elScale);
      }}
    }}
  }});
 if (isHkDevice && activePage && hkSplitPos) {{
  applyHardKeySplitLayout(activePage, hkSplitPos);
  applyHkTightClusterLayout(activePage);
 }}
 if (_pendingZoomCenter) {{
  if (isHkDevice && hkSplitPos) {{
   centerRtiCanvasOnHkAssembly(hkSplitPos);
  }} else {{
   const maxScrollLeft=Math.max(rtiCanvas.scrollWidth-rtiCanvas.clientWidth,0);
   const maxScrollTop=Math.max(rtiCanvas.scrollHeight-rtiCanvas.clientHeight,0);
   const cx=Number(_pendingZoomCenter.centerX||0);
   const cy=Number(_pendingZoomCenter.centerY||0);
   rtiCanvas.scrollLeft=clamp((currentDeviceLeft+(cx*currentTotalScale))-(rtiCanvas.clientWidth/2),0,maxScrollLeft);
   rtiCanvas.scrollTop=clamp((currentDeviceTop+(cy*currentTotalScale))-(rtiCanvas.clientHeight/2),0,maxScrollTop);
  }}
  _pendingZoomCenter=null;
 }}
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
  if (_pendingZoomTelemetryReason) {{
   emitZoomTelemetry(_pendingZoomTelemetryReason);
   _pendingZoomTelemetryReason='';
  }}
  maybeReportReadyBaseline();
 }} finally {{
  _recordLayoutPerf(_perfNow()-_layoutT0);
 }}
}}
let _rtiLayoutScheduled=false;
let _pendingZoomCenter=null;
let _pendingZoomTelemetryReason='';
function scheduleRtiLayout(reason) {{
 if (reason) _pendingZoomTelemetryReason=String(reason);
 if (_rtiLayoutScheduled) return;
 _rtiLayoutScheduled=true;
 requestAnimationFrame(() => {{
  _rtiLayoutScheduled=false;
 applyRtiLayout();
 }});
}}
function clamp(value,min,max){{return Math.min(max,Math.max(min,value));}}
let _readyBaselineSent=false;
window.__sentinelRuntimeReady=false;
let _runtimeReadySignaled=false;
const _shellBootDelayMs=Math.max(0, Number(window.__sentinelShellBootDelayMs||0));
function markRuntimeReady() {{
 if (_runtimeReadySignaled) return;
 _runtimeReadySignaled=true;
 window.__sentinelRuntimeReady=true;
 try {{
  if (document.body) document.body.setAttribute('data-sentinel-runtime-ready','1');
  document.dispatchEvent(new CustomEvent('sentinel:runtime-ready', {{ detail: {{ ready:true }} }}));
 }} catch (_e) {{}}
}}
function waitForStableRtiGeometry(onStable) {{
 let prev=null;
 let stableFrames=0;
 let ticks=0;
 const MAX_TICKS=24;
 const EPS=0.75;
 const step=() => {{
  const canvas=document.getElementById('rtiCanvas');
  if (!canvas) {{
   onStable();
   return;
  }}
  const r=canvas.getBoundingClientRect();
  const cur={{left:r.left, top:r.top, width:r.width, height:r.height}};
  if (prev) {{
   const stable=
    Math.abs(cur.left-prev.left)<=EPS &&
    Math.abs(cur.top-prev.top)<=EPS &&
    Math.abs(cur.width-prev.width)<=EPS &&
    Math.abs(cur.height-prev.height)<=EPS;
   stableFrames=stable ? (stableFrames+1) : 0;
  }}
  prev=cur;
  ticks += 1;
  if (stableFrames>=2 || ticks>=MAX_TICKS) {{
   onStable();
   return;
  }}
  requestAnimationFrame(step);
 }};
 requestAnimationFrame(step);
}}
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
  emitZoomTelemetry('device-zoom');
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
 scheduleRtiLayout("device-zoom");
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
 pageEl.className='device-page {device_profile_class}';
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
 currentTextZoomPercent=TEXT_ZOOM_DEFAULT;
 viewportMode.popupZoomPercent=ZOOM_DEFAULT;
 syncZoomResetText();
 syncTextZoomResetText();
 currentViewportIndexes=(PAGE_STATE[target].vpFrames||[]).map(()=>0);
 const rtiCanvas=document.getElementById('rtiCanvas');
 if (rtiCanvas) {{
   rtiCanvas.scrollLeft=0;
   rtiCanvas.scrollTop=0;
 }}
 const scopedRoomId = inferScopedRoomIdFromPage(activePageEl());
 if (scopedRoomId != null) {{
  setSelectedRoom(scopedRoomId, {{persist:true}});
 }}
 syncLayerLocksForActiveLayers(false).finally(()=>{{ renderLayerPanel(); applyLayerVisibility(); scheduleRtiLayout('page-change'); }});
}}
selectedRoomId=loadSelectedRoomId();
if (selectedRoomId == null) {{
 selectedRoomId=defaultSelectedRoomId();
 persistSelectedRoomId(selectedRoomId);
}}
syncSelectedRoomIndicator();
window.addEventListener('resize', applyRtiLayout);
renderOrientationToggle();
applyOrientationState();
// Ensure synthetic source rows are compacted before first layout paint.
applyLayerVisibility();
syncTextZoomResetText();
const rtiCanvasEl=document.getElementById('rtiCanvas');
if (rtiCanvasEl) rtiCanvasEl.addEventListener('scroll', applyRtiLayout, {{passive:true}});
const _finalizeRuntimeBoot=() => {{
 waitForStableRtiGeometry(() => {{
  if (_shellBootDelayMs > 0) {{
   setTimeout(markRuntimeReady, _shellBootDelayMs);
  }} else {{
   markRuntimeReady();
  }}
 }});
}};
applyRtiLayout();
syncLayerLocksForActiveLayers(false).finally(()=>{{ renderLayerPanel(); applyLayerVisibility(); applyRtiLayout(); _finalizeRuntimeBoot(); }});
	document.addEventListener('click', e=>{{
	 const link=e.target.closest('.page-link-hit');
	 if (!link) return;
	 const targetPageIndex=link.dataset.targetPageIndex;
	 if (targetPageIndex==null || targetPageIndex==='') return;
	 e.preventDefault();
   const resolvedRoomId=normalizeRoomId(link?.dataset?.resolvedRoomId);
   const wrap=link.closest('.btn-wrap');
   if (wrap && String(wrap.dataset.syntheticRoomList || '')==='1') {{
    setSelectedRoom(wrap.dataset.syntheticRoomId);
   }} else if (wrap && String(wrap.dataset.syntheticSourceList || '')==='1') {{
    /* source-list rows intentionally do not set selected room */
   }} else if (resolvedRoomId != null) {{
    setSelectedRoom(resolvedRoomId);
   }} else {{
    const scopedRoomId=scopedRoomIdFromWrap(wrap);
    if (scopedRoomId != null) setSelectedRoom(scopedRoomId);
   }}
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
        noun = "System Macro" if len(macro_names) == 1 else "System Macros"
        return f"run {noun}: {'; '.join(macro_names)}"
    if command_names and not macro_names:
        noun = "command" if len(command_names) == 1 else "commands"
        return f"run {noun}: {'; '.join(command_names)}"
    if macro_names and command_names:
        parts = [
            f"{'System Macro' if len(macro_names) == 1 else 'System Macros'} {'; '.join(macro_names)}",
            f"{'command' if len(command_names) == 1 else 'commands'} {'; '.join(command_names)}",
        ]
        return f"run actions: {'; '.join(parts)}"
    return "run action: Unknown"


def _event_button_text(item: dict[str, Any], event_kind: str) -> str:
    user = item.get("userFacing", {}) if isinstance(item, dict) else {}
    trigger = str(user.get("resolvedTrigger") or "No Event Trigger").strip()
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
            noun = "System Macro" if len(macro_names) == 1 else "System Macros"
            remainder = f" ...+{total_actions - 1} more" if total_actions > 1 else ""
            return f"When {trigger_text} happens, run {noun}: {first_action_name or 'Unknown'}{remainder}"
        if macro_steps and not macro_names:
            undefined_count = int(user.get("macroStepCount") or len(macro_steps) or 0)
            if macro_steps and all(str(step.get("type") or "") == "undefined" for step in macro_steps):
                noun = "Macro Step" if undefined_count == 1 else "Macro Steps"
                return f"When {trigger_text} happens, run {undefined_count} undefined {noun}"
            if len(macro_steps) == 1 and str(macro_steps[0].get("type") or "") == "command":
                return f"When {trigger_text} happens, run Macro Step (Command): {first_action_name or 'Unknown'}"
            remainder = f" ...+{total_actions - 1} more" if total_actions > 1 else ""
            noun = "Macro Step" if total_actions == 1 else "Macro Steps"
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
        canonical_map = (
            ("Event Trigger", ("Event Trigger", "Trigger")),
            ("System Macro", ("System Macro", "System Macros", "Macro", "Macros")),
            ("Macro Step", ("Macro Step", "Macro Steps", "MacroStep", "MacroSteps")),
            ("Command", ("Command", "Commands")),
        )
        for canonical, aliases in canonical_map:
            if any(test_targets.get(alias) for alias in aliases):
                targets.append(canonical)

    refs: dict[str, Any] = {"eventId": int(event_id) if event_id is not None else None}
    refs["eventKind"] = "DRIVER" if event_kind == "driver" else "SYSTEM"
    if isinstance(diag, dict):
        if diag.get("scope") is not None:
            refs["scope"] = diag.get("scope")
        if diag.get("resolvedData") is not None:
            refs["resolvedData"] = diag.get("resolvedData")
    return {
        "category": "Driver Event" if event_kind == "driver" else "System Event",
        "categoryKey": "driverEvents" if event_kind == "driver" else "systemEvents",
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
            f"<div class='btn-wrap btn-wrap--home-event'>"
            f"<button class='test-btn' type='button' data-meta='{meta_attr}'>{_event_button_text(item, 'system')}</button>"
            f"</div>"
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
                f"<div class='btn-wrap btn-wrap--home-event'>"
                f"<button class='test-btn' type='button' data-meta='{meta_attr}'>{_event_button_text(item, 'driver')}</button>"
                f"</div>"
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
    device_title = f"Devices | {_count_label(len(device_rows), 'device')}"

    app_json = json.dumps(app_ui)
    _ts_embed = _sentinel_test_status_embed_js()
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
.section-toggle{{display:flex;align-items:center;justify-content:space-between;gap:14px;width:100%;box-sizing:border-box;margin:0;padding:0;border:0;background:transparent;color:#183247;cursor:pointer;text-align:left;}}
.section-toggle-main{{display:inline-flex;align-items:center;gap:10px;min-width:0;}}
.section-toggle-label{{font-size:22px;line-height:1.1;font-weight:700;}}
.section-pct{{flex-shrink:0;font-size:18px;line-height:1.1;font-weight:700;color:#5a7387;}}
.section-chevron{{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;color:#5a7387;}}
.section-chevron svg{{display:block;width:14px;height:14px;stroke:currentColor;stroke-width:2.2;fill:none;stroke-linecap:round;stroke-linejoin:round;}}
.home-subtitle{{margin:18px 0 10px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#5a7387;}}
.home-list{{display:flex;flex-direction:column;gap:12px;margin-top:16px;}}
.home-list[hidden]{{display:none !important;}}
.home-row{{width:100%;display:block;box-sizing:border-box;padding:16px 18px;border-radius:16px;border:1px solid #a9bccd;background:#1e5f86;color:#fff;text-decoration:none;font-size:15px;line-height:1.35;text-align:left;box-shadow:inset 0 0 0 1px #154665;}}
.home-row:hover{{filter:brightness(1.05);}}
.btn-wrap.btn-wrap--home-event{{width:100%;position:relative;border-radius:16px;--btn-fill-color:#1e5f86;--btn-state-trim-color:transparent;--btn-state-trim-width:0px;}}
.btn-wrap--home-event .test-btn{{width:100%;margin:0;font:inherit;display:block;box-sizing:border-box;padding:16px 18px;border-radius:16px;border:0;background:var(--btn-fill-color);color:#fff;box-shadow:inset 0 0 0 1px #154665,inset 0 0 0 var(--btn-state-trim-width) var(--btn-state-trim-color);font-size:15px;line-height:1.35;text-align:left;cursor:pointer;white-space:normal;}}
.btn-wrap--home-event:hover .test-btn{{filter:brightness(1.05);}}
.btn-wrap--home-event .btn-pass-total{{display:none !important;visibility:hidden !important;}}
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
<button class='section-toggle' type='button' data-target='system-events' aria-expanded='false' onclick='toggleSection(this)'><span class='section-toggle-main'><span class='section-toggle-label'>{system_title}</span><span class='section-chevron' aria-hidden='true'><svg viewBox='0 0 16 16'><path d='M3.5 6.25 8 10.75 12.5 6.25'/></svg></span></span><span class='section-pct' id='home-pct-system'>0%</span></button>
<div class='home-list' id='system-events' hidden>{system_content}</div>
</section>
<section class='home-section'>
<button class='section-toggle' type='button' data-target='driver-events' aria-expanded='false' onclick='toggleSection(this)'><span class='section-toggle-main'><span class='section-toggle-label'>{driver_title}</span><span class='section-chevron' aria-hidden='true'><svg viewBox='0 0 16 16'><path d='M3.5 6.25 8 10.75 12.5 6.25'/></svg></span></span><span class='section-pct' id='home-pct-driver'>0%</span></button>
<div class='home-list' id='driver-events' hidden>{driver_content}</div>
</section>
<section class='home-section'>
<button class='section-toggle' type='button' data-target='devices' aria-expanded='false' onclick='toggleSection(this)'><span class='section-toggle-main'><span class='section-toggle-label'>{device_title}</span><span class='section-chevron' aria-hidden='true'><svg viewBox='0 0 16 16'><path d='M3.5 6.25 8 10.75 12.5 6.25'/></svg></span></span><span class='section-pct' id='home-pct-devices'>0%</span></button>
<div class='home-list' id='devices' hidden>{device_content}</div>
</section>
</main>
<div class='ov' id='ov'><div class='pop'><div class='pop-head'><h3 id='pt'></h3><button id='passAll' type='button'>Pass All</button></div><div id='rows' class='rows-scroll scroll-hover'></div><div class='post-status' id='postStatus' role='status' aria-live='polite' hidden></div><button id='close'>Close</button></div></div>
<script>
{_ts_embed}
const APP_UI={app_json};
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
 function homePctDisplay(pass, total) {{
  const p = Number(pass || 0);
  const t = Number(total || 0);
  if (t <= 0) return "0%";
  return `${{Math.round((p / t) * 100)}}%`;
 }}
 function updateHomeSectionPercents(progress) {{
  if (!progress || typeof progress !== "object") return;
  const sys = progress.eventSections && progress.eventSections.system ? progress.eventSections.system.counts : null;
  const drv = progress.eventSections && progress.eventSections.driver ? progress.eventSections.driver.counts : null;
  const elS = document.getElementById("home-pct-system");
  const elD = document.getElementById("home-pct-driver");
  const elV = document.getElementById("home-pct-devices");
  if (elS && sys) elS.textContent = homePctDisplay(sys.pass, sys.totalTargets);
  if (elD && drv) elD.textContent = homePctDisplay(drv.pass, drv.totalTargets);
  if (elV && Array.isArray(progress.devices)) {{
   let pass = 0, total = 0;
   for (let i = 0; i < progress.devices.length; i++) {{
    const d = progress.devices[i];
    const c = d && d.counts ? d.counts : null;
    if (!c) continue;
    const t = Number(c.totalTargets || 0);
    if (t <= 0) continue;
    total += t;
    pass += Number(c.pass || 0);
   }}
   elV.textContent = homePctDisplay(pass, total);
  }}
 }}
 function refreshHomeEventVisualStates() {{
  const api=globalThis.__sentinelTestStatus;
  if (!api||typeof api.refreshButtonWraps!=="function") return;
  api.refreshButtonWraps({{
   root: document,
   wrapSelector: ".btn-wrap--home-event",
   statusByTargetKey: statusByTargetKey,
   buildTargetPayload: buildTargetPayload,
  }});
 }}
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
    refreshHomeEventVisualStates();
    return;
   }}
   if (t === "commissioning_rollups") {{
    updateHomeSectionPercents(payload?.progress);
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
   refreshHomeEventVisualStates();
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
 function _renderRowStatusTimes(rowUi) {{
  if (!rowUi || !rowUi.lastTestEl) return;
  const times = rowUi.statusTimes || {{}};
  const outcome = String(rowUi.currentOutcome || "").trim().toUpperCase();
  if (outcome === "PASS" && times.PASS) {{
    rowUi.lastTestEl.textContent = `Passed: ${{times.PASS}}`;
    return;
  }}
  if (outcome === "FAIL" && times.FAIL) {{
    rowUi.lastTestEl.textContent = `Failed: ${{times.FAIL}}`;
    return;
  }}
  if (outcome === "UNTESTED" && times.UNTESTED) {{
    rowUi.lastTestEl.textContent = `Reverted: ${{times.UNTESTED}}`;
    return;
  }}
  rowUi.lastTestEl.textContent = "";
 }}
 function setRowStatus(rowUi, outcome, recordedAtUtc) {{
  if (!rowUi) return;
  const o = String(outcome || "").trim().toUpperCase();
  const at = formatLastTestUtc(recordedAtUtc);
  if (!rowUi.statusTimes) rowUi.statusTimes = {{}};
  if (rowUi.passBtn) rowUi.passBtn.classList.toggle("is-pass-active", o === "PASS");
  if (rowUi.failBtn) rowUi.failBtn.classList.toggle("is-fail-active", o === "FAIL");
  rowUi.currentOutcome = o;
  if (at && (o === "PASS" || o === "FAIL" || o === "UNTESTED")) rowUi.statusTimes[o] = at;
  _renderRowStatusTimes(rowUi);
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
  const targetKey = `event:${{eventId}}:${{label || "Event Trigger"}}`;
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
  const syntheticRoomList = wrap && wrap.dataset ? String(wrap.dataset.syntheticRoomList || "") === "1" : false;
  const syntheticRoomIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticRoomId : null;
  const syntheticRoomTagIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticRoomTagId : null;
  const syntheticRoomId = syntheticRoomIdRaw == null ? null : Number(syntheticRoomIdRaw);
  const syntheticRoomTagId = syntheticRoomTagIdRaw == null ? null : Number(syntheticRoomTagIdRaw);
  const syntheticSourceList = wrap && wrap.dataset ? String(wrap.dataset.syntheticSourceList || "") === "1" : false;
  const syntheticSourceRoomIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticSourceRoomId : null;
  const syntheticSourceDeviceIdRaw = wrap && wrap.dataset ? wrap.dataset.syntheticSourceDeviceId : null;
  const syntheticSourceRoomId = syntheticSourceRoomIdRaw == null ? null : Number(syntheticSourceRoomIdRaw);
  const syntheticSourceDeviceId = syntheticSourceDeviceIdRaw == null ? null : Number(syntheticSourceDeviceIdRaw);
  const categoryName = String(m.category || "").trim();
  const buttonName = String(m.identity || "").trim();
  const targetName = String(label || "").trim() || buttonName || categoryName;
  const keyToken = String(label || "").trim() || categoryName || buttonName || "Button";
  const keyTokenResolved = syntheticRoomList && syntheticRoomId != null && Number.isFinite(syntheticRoomId)
   ? `${{keyToken}}:room:${{Number(syntheticRoomId)}}`
   : (syntheticSourceList && syntheticSourceDeviceId != null && Number.isFinite(syntheticSourceDeviceId)
      ? `${{keyToken}}:src:${{Number(syntheticSourceDeviceId)}}:${{(syntheticSourceRoomId != null && Number.isFinite(syntheticSourceRoomId)) ? `room:${{Number(syntheticSourceRoomId)}}` : "room:na"}}`
      : keyToken);
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
  const effectiveRoomIdBase = viewportLayerRoomId != null
    ? Number(viewportLayerRoomId)
    : (pageLayerRoomId != null ? Number(pageLayerRoomId) : (pageRoomId != null ? Number(pageRoomId) : null));
   const effectiveSourceId = viewportLayerSourceId != null
    ? Number(viewportLayerSourceId)
    : (pageLayerSourceId != null ? Number(pageLayerSourceId) : (pageSourceDeviceId != null ? Number(pageSourceDeviceId) : null));
  const effectiveRoomId = syntheticRoomList && syntheticRoomId != null && Number.isFinite(syntheticRoomId)
   ? Number(syntheticRoomId)
   : (syntheticSourceList
      ? ((selectedRoomId != null && Number.isFinite(selectedRoomId))
         ? Number(selectedRoomId)
         : (syntheticSourceRoomId != null && Number.isFinite(syntheticSourceRoomId) ? Number(syntheticSourceRoomId) : effectiveRoomIdBase))
      : effectiveRoomIdBase);
  const buttonTagIdBase = buttonScope.buttonTagId;
  const buttonTagId = syntheticRoomList && syntheticRoomTagId != null && Number.isFinite(syntheticRoomTagId)
   ? Number(syntheticRoomTagId)
   : buttonTagIdBase;
  const effectiveSourceIdResolved = syntheticSourceList && syntheticSourceDeviceId != null && Number.isFinite(syntheticSourceDeviceId)
   ? Number(syntheticSourceDeviceId)
   : effectiveSourceId;
   const scopedButtonId = buttonScope.buttonId;
   const macroIds = Array.isArray(bindings.macroIds) ? bindings.macroIds : [];
   const variableIds = Array.isArray(bindings.variableIds) ? bindings.variableIds : [];
   const macroStepIds = Array.isArray(bindings.macroStepIds) ? bindings.macroStepIds : [];
  const lowerLabel = String(keyTokenResolved || "").trim().toLowerCase();
   if (buttonTagId != null) {{
    let programRef = "none";
    const firstMacroId = macroIds.length ? Number(macroIds[0]) : null;
    const firstVarId = variableIds.length ? Number(variableIds[0]) : null;
    const firstMacroStepId = macroStepIds.length ? Number(macroStepIds[0]) : null;
    if (lowerLabel === "macro" || lowerLabel === "macros" || lowerLabel === "system macro" || lowerLabel === "system macros") {{
     if (firstMacroId != null && Number.isFinite(firstMacroId)) programRef = `macro:${{firstMacroId}}`;
    }} else if (lowerLabel === "macrostep" || lowerLabel === "macrosteps" || lowerLabel === "macro step" || lowerLabel === "macro steps") {{
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
    refs.effectiveSourceId = effectiveSourceIdResolved;
  if (syntheticRoomList) {{
   if (syntheticRoomId != null && Number.isFinite(syntheticRoomId)) refs.syntheticRoomId = Number(syntheticRoomId);
   if (syntheticRoomTagId != null && Number.isFinite(syntheticRoomTagId)) refs.syntheticRoomTagId = Number(syntheticRoomTagId);
  }}
  if (syntheticSourceList) {{
   if (syntheticSourceRoomId != null && Number.isFinite(syntheticSourceRoomId)) refs.syntheticSourceRoomId = Number(syntheticSourceRoomId);
   if (syntheticSourceDeviceId != null && Number.isFinite(syntheticSourceDeviceId)) refs.syntheticSourceDeviceId = Number(syntheticSourceDeviceId);
  }}
    refs.programRef = programRef;
    if (apexScopeSource.audioScope && typeof apexScopeSource.audioScope === "object" && apexScopeSource.audioScope.wrapperDeviceId != null && rtiAddress != null && effectiveRoomId != null) {{
     const wrapperDeviceId = Number(apexScopeSource.audioScope.wrapperDeviceId);
     const targetKey = `tt2_audio:${{Number(rtiAddress)}}:${{scopeType}}:${{Number(effectiveRoomId)}}:${{wrapperDeviceId}}:${{Number(buttonTagId)}}:${{keyTokenResolved}}`;
     return {{
      targetKey,
      kind: scope,
      targetName,
      refs
     }};
    }}
    if (rtiAddress != null && effectiveRoomId != null && effectiveSourceIdResolved != null) {{
     const targetKey = `tt2:${{Number(rtiAddress)}}:${{scopeType}}:${{Number(effectiveRoomId)}}:${{Number(effectiveSourceIdResolved)}}:${{Number(buttonTagId)}}:${{programRef}}:${{keyTokenResolved}}`;
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
     const targetKey = `tt_ui:${{Number(rtiAddress)}}:${{sharedFlag}}:${{scopeLayerId}}:${{Number(scopedButtonId)}}:${{keyTokenResolved}}`;
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
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{buttonId}}:${{keyTokenResolved}}`;
  }} else if (vpButtonId && deviceId != null && pageId != null) {{
   targetKey = `vpbtn:${{deviceId}}:${{pageId}}:${{vpButtonId}}:${{keyTokenResolved}}`;
  }} else if (deviceId != null && pageId != null && buttonId != null) {{
   targetKey = `btn:${{deviceId}}:${{pageId}}:${{buttonId}}:${{keyTokenResolved}}`;
  }} else {{
   targetKey = `btn:${{keyTokenResolved}}`;
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
  const m = (meta && typeof meta === "object") ? meta : {{}};
  rows.querySelectorAll('.row').forEach(function(row){{
   var label = String((row.querySelector('.n')||{{}}).textContent || '').trim();
   if (!label) return;
   var target = buildTargetPayload(ctxBtn || null, m, label);
   if (!target || !target.targetKey) return;
   var rowUi = rowStatusByTargetKey.get(target.targetKey);
   if (!rowUi) return;
   passAllQueue.push({{ label: label, rowUi: rowUi }});
  }});
  if (!passAllQueue.length) return;
  passAllContext = {{ ctxBtn: ctxBtn || null, meta: m }};
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
 async function postResultWs(ctxBtn, meta, targetLabel, outcome, failNote, rowUi, isRevert) {{
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
    target:{{targetKey:target.targetKey,kind:target.kind,refs:{{...(target.refs||{{}}), ...(isRevert ? {{ revertedFrom: "PASS" }} : {{}})}},targetName:target.targetName}},
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
  passBtn.addEventListener('click', function(e){{e.stopPropagation(); const nextOutcome = rowUi.currentOutcome === 'PASS' ? 'UNTESTED' : 'PASS'; postResultWs(null, meta, label, nextOutcome, null, rowUi, nextOutcome === 'UNTESTED');}});
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
     const showPassAll = targets.length > 1;
     passAllBtn.hidden = !showPassAll;
     passAllBtn.disabled = !showPassAll;
     passAllBtn.onclick = showPassAll ? function(){{ queuePassAll(null, m); }} : null;
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
    device_display_name = str(uf.get("displayName", "") or "")
    profile_name = device_display_name.lower()
    device_profile_class = (
        "sentinel-device-profile-iphone-ipad"
        if ("iphone" in profile_name or "ipad" in profile_name)
        else "sentinel-device-profile-other"
    )
    title = app_ui.get("header", {}).get("titleTemplate", "{deviceName} - {pageName}")
    first_page_name = str(pages[0].get("pageName", "")) if pages else ""
    header = title.replace("{deviceName}", uf.get("displayName", "")).replace("{pageName}", first_page_name)
    diag_pages = device.get("diagnostics", {}).get("pages", [])

    product_model_key = _hard_key_model_key(device)
    hk_remote = False
    if product_model_key is not None:
        from sentinel.generation.hard_keys import registry as _hk_registry

        _hk_model = _hk_registry.MODELS.get(product_model_key)
        if _hk_model is not None:
            hk_remote = True
            hk_design_w, hk_design_h = _hk_model.design_size
            for orient_key in ("portrait", "landscape"):
                size = orientation_state["sizes"].get(orient_key)
                if not isinstance(size, dict):
                    continue
                touch_w0 = int(size.get("width") or 0)
                touch_h0 = int(size.get("height") or 0)
                size["hardKeyLayout"] = {
                    "touchSourceWidth": touch_w0,
                    "touchSourceHeight": touch_h0,
                    "stripDesignWidth": int(hk_design_w),
                    "stripDesignHeight": int(hk_design_h),
                }
                size["height"] = _hard_key_layout_display_height(
                    touch_w0,
                    touch_h0,
                    hk_design_w,
                    hk_design_h,
                )
            if active_orientation == "portrait":
                res = orientation_state["sizes"]["portrait"]
            else:
                res = orientation_state["sizes"]["landscape"]
            w = int(res.get("width") or w)
            h = int(res.get("height") or h)
    page_html_by_index: dict[str, str] = {}
    page_state: list[dict[str, Any]] = []
    page_payloads: list[dict[str, Any]] = []
    for page_index, _page in enumerate(pages):
        payload = _page_payload(project_data, app_ui, project_stem, device_index, page_index, active_orientation, resolved_targets)
        page_payloads.append(payload)
        diag_page_id = diag_pages[page_index].get("pageId") if page_index < len(diag_pages) else None
        # Keep viewport box click-targets above same-layer button rows while preserving layer z-order.
        page_inner_main = f"{payload['page_button_rows']}{payload['viewport_button_rows']}{payload['viewport_boxes']}"
        if hk_remote:
            strip_html = payload.get("hard_key_strip_html") or ""
            hk_owner = str(payload.get("hard_key_owner_layer_key") or "").strip()
            hk_owner_attr = (
                f" data-owner-layer-key='{escape(hk_owner, quote=True)}'" if hk_owner else ""
            )
            page_html_by_index[str(page_index)] = (
                f"<div class='hk-split-left'>"
                f"<div class='hk-touch-stack'>{page_inner_main}</div></div>"
                f"<div class='hk-split-right'{hk_owner_attr} data-hk-model=\"{product_model_key}\">"
                f"{strip_html}</div>"
            )
        else:
            page_html_by_index[str(page_index)] = page_inner_main
        page_state.append(
            {
                "deviceName": uf.get("displayName", ""),
                "pageName": payload["page_name"],
                "pageId": diag_page_id,
                "layers": payload.get("layers", []),
                "vpFrames": payload["vp_frames"],
            }
        )
    diag_for_rooms = device.get("diagnostics", {}) if isinstance(device, dict) else {}
    room_list = diag_for_rooms.get("rooms") if isinstance(diag_for_rooms, dict) else None
    if not isinstance(room_list, list):
        room_list = []
    source_list = diag_for_rooms.get("sourceListRows") if isinstance(diag_for_rooms, dict) else None
    if not isinstance(source_list, list):
        source_list = []
    first_page_inner = page_html_by_index.get("0", "")
    hard_key_style_css = ""
    hard_key_design_w = 0
    hard_key_design_h = 0
    if product_model_key is not None:
        from sentinel.generation.hard_keys import registry as _hk_registry

        scoped_style, _ = _load_hard_key_template(product_model_key)
        hard_key_style_css = scoped_style or ""
        model = _hk_registry.MODELS.get(product_model_key)
        if model is not None:
            hard_key_design_w, hard_key_design_h = model.design_size
    initial_page_markup = (
        f"<div class='device-page active {device_profile_class}' data-page-index='0'>{first_page_inner}</div>"
        if pages
        else ""
    )
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
        room_list_resolution_json=json.dumps(room_list),
        source_list_resolution_json=json.dumps(source_list),
        hard_key_model_key=product_model_key,
        hard_key_style_css=hard_key_style_css,
        hard_key_design_w=hard_key_design_w,
        hard_key_design_h=hard_key_design_h,
        device_profile_class=device_profile_class,
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
            "sizes": orientation_state["sizes"],
        },
        "pages": payload_doc_pages,
        "roomListResolution": room_list,
        "sourceListResolution": source_list,
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
