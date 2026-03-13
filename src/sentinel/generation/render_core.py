from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def _btn_text(identity: dict[str, Any]) -> str:
    text = str(identity.get("text") or "").strip()
    tag = str(identity.get("buttonTagName") or "").strip()
    return text if text else tag


def _page_link_enabled(targets: dict[str, Any]) -> bool:
    page_link = targets.get("pageLink")
    if isinstance(page_link, dict):
        return bool(page_link.get("enabled"))
    return bool(page_link)


def _page_link_target_id(targets: dict[str, Any]) -> int | None:
    page_link = targets.get("pageLink")
    if isinstance(page_link, dict):
        raw = page_link.get("targetPageId")
        return int(raw) if raw is not None else None
    return None


def _targets(btn: dict[str, Any], variable_label_template: str) -> list[str]:
    t = btn.get("testTargets", {})
    vars_t = t.get("variables", {})
    out: list[str] = []
    if t.get("text"):
        out.append("Text")
    if t.get("macro"):
        out.append("Macro")
    for name in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command"):
        if vars_t.get(name):
            out.append(variable_label_template.replace("{variableType}", name))
    if _page_link_enabled(t):
        out.append("PageLink")
    return out


def _is_ui_only_button(btn: dict[str, Any]) -> bool:
    identity = btn.get("buttonIdentity", {})
    t = btn.get("testTargets", {})
    vars_t = t.get("variables", {})
    has_any_var = any(bool(vars_t.get(k)) for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command"))
    return (
        not str(identity.get("buttonTagName") or "").strip()
        and not str(identity.get("text") or "").strip()
        and not bool(t.get("text"))
        and not bool(t.get("macro"))
        and not _page_link_enabled(t)
        and not has_any_var
    )


def _iter_page_buttons(page: dict[str, Any]) -> list[tuple[dict[str, Any], str, int, int]]:
    items: list[tuple[dict[str, Any], str, int, int]] = []
    for cat, label in (("screenLabels", "Screen Label"), ("screenButtons", "Screen Button"), ("hardButtons", "Hard Button")):
        for btn in page.get("buttonCategories", {}).get(cat, []):
            if _is_ui_only_button(btn):
                continue
            items.append((btn, label, 0, 0))
    return items


def _ui_coordinates(ui: dict[str, Any]) -> dict[str, int]:
    if "coordinates" in ui:
        return ui.get("coordinates", {})
    orientations = ui.get("orientations", {})
    portrait = orientations.get("portrait", {})
    if portrait.get("coordinates"):
        return portrait.get("coordinates", {})
    landscape = orientations.get("landscape", {})
    if landscape.get("coordinates"):
        return landscape.get("coordinates", {})
    return {}


def _iter_viewport_boxes(page: dict[str, Any]) -> list[dict[str, int]]:
    out: list[dict[str, int]] = []
    for viewport in page.get("viewports", []):
        c = _ui_coordinates(viewport.get("viewportUI", {}))
        out.append(
            {
                "left": int(c.get("left") or 0),
                "top": int(c.get("top") or 0),
                "width": int(c.get("width") or 0),
                "height": int(c.get("height") or 0),
            }
        )
    return out


def _iter_viewport_buttons(page: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for vp_index, viewport in enumerate(page.get("viewports", [])):
        vp_c = _ui_coordinates(viewport.get("viewportUI", {}))
        off_top = int(vp_c.get("top") or 0)
        off_left = int(vp_c.get("left") or 0)
        frames = sorted(viewport.get("frames", []), key=lambda f: int(f.get("frameId", 0)))
        if not frames:
            continue
        default_frame_id = int(frames[0].get("frameId", 0))
        for frame in frames:
            frame_id = int(frame.get("frameId", 0))
            cats = frame.get("buttonCategories", {})
            for cat, label in (("screenLabels", "Screen Label"), ("screenButtons", "Screen Button"), ("hardButtons", "Hard Button")):
                for btn in cats.get(cat, []):
                    if _is_ui_only_button(btn):
                        continue
                    out.append(
                        {
                            "btn": btn,
                            "label": label,
                            "off_top": off_top,
                            "off_left": off_left,
                            "vp_index": vp_index,
                            "frame_id": frame_id,
                            "visible": frame_id == default_frame_id,
                        }
                    )
    return out


def _page_target_map(project_data: dict[str, Any], project_stem: str, device_index: int) -> dict[int, str]:
    device = project_data["devices"][device_index]
    user_pages = device["userFacing"]["pages"]
    diag_pages = project_data["devices"][device_index].get("diagnostics", {}).get("pages", [])
    device_name = str(device["userFacing"].get("displayName", f"device-{device_index}"))
    target_href = device_filename(project_stem, device_name, device_index)
    out: dict[int, str] = {}
    for index, diag_page in enumerate(diag_pages):
        if index >= len(user_pages):
            break
        page_id = diag_page.get("pageId")
        if page_id is None:
            continue
        out[int(page_id)] = target_href
    return out


def _page_target_indexes(project_data: dict[str, Any], device_index: int) -> dict[int, int]:
    diag_pages = project_data["devices"][device_index].get("diagnostics", {}).get("pages", [])
    out: dict[int, int] = {}
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
) -> str:
    c = _ui_coordinates(btn["buttonUI"])
    width = int(c.get("width") or 0)
    height = int(c.get("height") or 0)
    fs = int(btn["buttonUI"].get("fontSize") or app_ui.get("buttonPresentation", {}).get("fallbackFontSize", 10))
    identity = btn.get("buttonIdentity", {})
    targets = btn.get("testTargets", {})
    meta = {
        "category": label,
        "identity": _btn_text(identity),
        "buttonType": identity.get("buttonType") or "",
        "targets": _targets(btn, variable_label),
    }
    meta_attr = json.dumps(meta).replace("'", "&apos;")
    visibility_attr = "1" if "display:none" not in extra_style else "0"
    classes = f"btn-wrap {extra_classes}".strip()
    link_cfg = app_ui.get("appNavigation", {}).get("pageLinks", {})
    link_html = ""
    if link_cfg.get("enabled") and _page_link_enabled(targets):
        target_page_id = _page_link_target_id(targets)
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
    return (
        f"<div class='{classes}' data-left='{left}' data-top='{top}' data-width='{width}' data-height='{height}' data-font-size='{fs}' data-visible='{visibility_attr}' {extra_attrs}>"
        f"<button class='test-btn' data-meta='{meta_attr}'>{_btn_text(identity)}</button>"
        f"{link_html}</div>"
    )


def _page_payload(project_data: dict[str, Any], app_ui: dict[str, Any], project_stem: str, device_index: int, page_index: int) -> dict[str, Any]:
    device = project_data["devices"][device_index]
    uf = device["userFacing"]
    page = uf["pages"][page_index]
    variable_label = app_ui.get("testingPopup", {}).get("variableLabelTemplate", "Variable - {variableType}")
    page_targets = _page_target_map(project_data, project_stem, device_index)
    page_target_indexes = _page_target_indexes(project_data, device_index)

    page_button_rows: list[str] = []
    for btn, label, off_top, off_left in _iter_page_buttons(page):
        c = _ui_coordinates(btn["buttonUI"])
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
            )
        )

    viewport_button_rows: list[str] = []
    for vb in _iter_viewport_buttons(page):
        btn = vb["btn"]
        c = _ui_coordinates(btn["buttonUI"])
        extra = "" if vb["visible"] else "display:none;"
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
                extra_attrs=f"data-vp='{vb['vp_index']}' data-frame='{vb['frame_id']}'",
            )
        )

    vp_frames = [sorted([int(f.get("frameId", 0)) for f in vp.get("frames", [])]) for vp in page.get("viewports", [])]
    viewport_boxes = "".join(
        [
            "<div class='vp-box' data-left='{left}' data-top='{top}' data-width='{width}' data-height='{height}'></div>".format(**c)
            for c in _iter_viewport_boxes(page)
        ]
    )
    return {
        "page_name": str(page.get("pageName", "")),
        "page_index": page_index,
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
    page_state_json: str,
    home_href: str | None = None,
) -> str:
    link_cfg = app_ui.get("appNavigation", {}).get("pageLinks", {})
    link_hover_enabled = bool(link_cfg.get("enabled") and link_cfg.get("showLinkAffordanceOnHover"))
    layout_cfg = app_ui.get("layout", {})
    control_cfg = layout_cfg.get("appUIControls", {})
    rti_device_cfg = layout_cfg.get("rtiDeviceCanvas", {})
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
.vp-box{{position:absolute;border:2px dashed #88a6bd;border-radius:0;background:transparent;pointer-events:none;z-index:1;box-sizing:border-box;}}
.btn-wrap{{position:absolute;z-index:2;}}
.test-btn{{position:absolute;inset:0;box-sizing:border-box;border:0;border-radius:10px;background:#1e5f86;box-shadow:inset 0 0 0 1px #154665;color:#fff;line-height:1.1;white-space:pre-line;cursor:pointer;overflow:hidden;padding:0;}}
.page-link-hit{{position:absolute;top:0;right:0;height:100%;display:flex;align-items:center;justify-content:flex-end;text-decoration:none;color:#fff;opacity:{'0' if link_hover_enabled else '1'};pointer-events:{'none' if link_hover_enabled else 'auto'};transition:opacity .15s ease;}}
.btn-wrap:hover .page-link-hit{{opacity:1;pointer-events:auto;}}
.page-link-icon{{display:inline-flex;align-items:center;justify-content:center;background:transparent;border-radius:0;}}
.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;font-size:115%;line-height:1;}}
.vp-nav{{width:44px;height:44px;border-radius:14px;border:2px solid #f0a126;background:transparent;color:#29445a;font-size:22px;cursor:pointer;position:relative;z-index:21;}}
.zoom-controls{{position:absolute;display:flex;gap:8px;z-index:21;}}
.zoom-btn{{width:44px;height:44px;border-radius:14px;border:2px solid #f0a126;background:transparent;color:#29445a;font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;box-sizing:border-box;}}
.zoom-btn.zoom-reset{{min-width:72px;width:auto;padding:0 12px;font-size:14px;}}
.vp-indicator{{display:flex;gap:8px;min-height:14px;align-items:center;justify-content:center;position:relative;z-index:21;}}
.dot{{width:10px;height:10px;border-radius:50%;border:1px solid #9fb4c6;background:#e2ebf2;}}
.dot.active{{background:#2d5f81;border-color:#2d5f81;}}
.ov{{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:flex-start;justify-content:center;padding:8px 12px 12px;z-index:10000;}}
.ov.open{{display:flex;}}
.pop{{width:min(980px,100%);background:#fff;border:1px solid #cbd7e2;border-radius:18px;padding:20px 24px;margin-top:0;}}
.pop h3{{margin:0 0 16px;font-size:16px;line-height:1.1;font-weight:700;}}
.row{{border:1px solid #d4dee8;border-radius:14px;padding:12px 14px;margin-bottom:12px;}}
.n{{font-weight:600;margin-bottom:10px;font-size:14px;line-height:1.1;}}
.actions{{display:flex;gap:10px;margin-bottom:10px;}}
.actions button{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;}}
textarea{{border:1px solid #ccd8e2;border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.2;}}
#close{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;display:block;margin-left:auto;}}
</style></head>
<body><div class='app-canvas' id='appCanvas'>
<div class='app-ui-controls top-controls' id='topControls'>{f"<a class='project-home-link' href='{home_href}'>Project Home</a>" if home_href else "<div></div>"}<div class='header'>{header}</div><div></div></div>
<div class='app-ui-controls left-controls' id='leftControls'><button class='vp-nav vp-prev' id='vpPrev' aria-label='Previous frame'>&lsaquo;</button></div>
<div class='app-ui-controls right-controls' id='rightControls'><button class='vp-nav vp-next' id='vpNext' aria-label='Next frame'>&rsaquo;</button></div>
<div class='app-ui-controls bottom-controls' id='bottomControls'><div class='vp-indicator' id='vpIndicator'></div></div>
<div class='zoom-controls' id='zoomControls'><button class='zoom-btn zoom-dec' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("decrease", "-")}</button><button class='zoom-btn zoom-reset' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("reset", "100%")}</button><button class='zoom-btn zoom-inc' type='button'>{app_ui.get("zoomControls", {}).get("buttons", {}).get("increase", "+")}</button></div>
<div class='rti-canvas' id='rtiCanvas'><div class='rti-content' id='rtiContent'><div class='rti-device-canvas' id='rtiDeviceCanvas'>{body_markup}</div></div></div></div>
<div class='ov' id='ov'><div class='pop'><h3 id='pt'></h3><div id='rows'></div><button id='close'>Close</button></div></div>
<script>
const APP_UI={app_json};
const APP_UI_CONTROLS={control_json};
const RTI_DEVICE_LAYOUT={rti_device_json};
const VIEWPORT_NAV={json.dumps(app_ui.get("viewportNavigation", {}))};
const ZOOM_CONTROLS={json.dumps(app_ui.get("zoomControls", {}))};
const ZOOM_DEFAULT={int(app_ui.get("zoomControls", {}).get("zoom", {}).get("defaultPercent", 100))};
const ZOOM_MAX={int(app_ui.get("zoomControls", {}).get("zoom", {}).get("maxPercent", 200))};
const ZOOM_STEP={int(app_ui.get("zoomControls", {}).get("zoom", {}).get("stepPercent", 10))};
const SOURCE_DEVICE_SIZE={{width:{w},height:{h}}};
const PAGE_STATE={page_state_json};
const VP_FRAMES=(PAGE_STATE[0]?.vpFrames||[]);
let currentZoomPercent=ZOOM_DEFAULT;
let currentTotalScale=1;
let currentDeviceLeft=0;
let currentDeviceTop=0;
let activePageIndex=0;
let currentViewportIndexes=VP_FRAMES.map(()=>0);
const ov=document.getElementById('ov'),pt=document.getElementById('pt'),rows=document.getElementById('rows');
function esc(s){{return String(s??'').replace(/[&<>\"]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[m]));}}
document.querySelectorAll('.test-btn').forEach(b=>b.addEventListener('click',()=>{{
 const m=JSON.parse(b.dataset.meta||'{{}}');
 const suffix=(APP_UI.testingPopup?.includeButtonTypeInTitle&&m.buttonType)?` (${{m.buttonType}})`:''; 
 pt.textContent=(APP_UI.testingPopup?.titleTemplate||'{{category}} Test - {{identity}}').replace('{{category}}',m.category).replace('{{identity}}',m.identity)+suffix;
 rows.innerHTML=(m.targets||[]).map(t=>`<div class='row'><div class='n'>${{esc(t)}}</div><div class='actions'><button>Pass</button><button>Fail</button></div><textarea placeholder='Fail note' style='width:100%;min-height:70px;'></textarea></div>`).join('')||"<div class='row'><div class='n'>No true test targets.</div></div>";
ov.classList.add('open');
}}));
document.getElementById('close').addEventListener('click',()=>ov.classList.remove('open'));
ov.addEventListener('click',e=>{{if(e.target===ov)ov.classList.remove('open')}});
function activePageEl() {{
 return document.querySelector(`.device-page[data-page-index="${{activePageIndex}}"]`);
}}
function activePageState() {{
 return PAGE_STATE[activePageIndex] || {{pageName:'',vpFrames:[]}};
}}
function syncHeader() {{
 const headerEl=document.querySelector('#topControls .header');
 if (!headerEl) return;
 const titleTemplate=APP_UI.header?.titleTemplate||'{{deviceName}} - {{pageName}}';
 headerEl.textContent=titleTemplate.replace('{{deviceName}}', PAGE_STATE[0]?.deviceName || '').replace('{{pageName}}', activePageState().pageName || '');
}}
function syncViewportControls() {{
 const state=activePageState();
 const frames=state.vpFrames||[];
 const hasViewportNav=Boolean(VIEWPORT_NAV.enabled && frames.length && frames[0]?.length);
 const prev=document.getElementById('vpPrev');
 const next=document.getElementById('vpNext');
 const indicator=document.getElementById('vpIndicator');
 if (prev) prev.style.display=hasViewportNav?'':'none';
 if (next) next.style.display=hasViewportNav?'':'none';
 if (!indicator) return;
 if (!hasViewportNav) {{
   indicator.innerHTML='';
   return;
 }}
 indicator.innerHTML=frames[0].map((_,i)=>`<span class="dot${{i===0?' active':''}}" data-dot="${{i}}"></span>`).join('');
}}
function applyViewportState() {{
 const pageEl=activePageEl();
 const state=activePageState();
 const frames=state.vpFrames||[];
 if (!pageEl) return;
 if (!(frames.length && frames[0].length)) return;
 const dots=[...document.querySelectorAll('#vpIndicator .dot')];
 frames.forEach((pageFrames, vpIndex)=>{{
   if (!pageFrames.length) return;
   const currentIndex=Math.max(0, Math.min(currentViewportIndexes[vpIndex] ?? 0, pageFrames.length-1));
   currentViewportIndexes[vpIndex]=currentIndex;
   const frame=pageFrames[currentIndex];
   pageEl.querySelectorAll(`.vp-btn[data-vp="${{vpIndex}}"]`).forEach(el=>{{
     el.style.display=(Number(el.dataset.frame)===frame)?'':'none';
   }});
   if (vpIndex===0) dots.forEach((d,i)=>d.classList.toggle('active',i===currentIndex));
 }});
}}
function applyRtiLayout() {{
 const appCanvas=document.getElementById('appCanvas');
 const topControls=document.getElementById('topControls');
 const bottomControls=document.getElementById('bottomControls');
 const leftControls=document.getElementById('leftControls');
 const rightControls=document.getElementById('rightControls');
 const zoomControls=document.getElementById('zoomControls');
 const rtiCanvas=document.getElementById('rtiCanvas');
 const rtiContent=document.getElementById('rtiContent');
 const rtiDeviceCanvas=document.getElementById('rtiDeviceCanvas');
 if (!appCanvas || !topControls || !bottomControls || !leftControls || !rightControls || !zoomControls || !rtiCanvas || !rtiContent || !rtiDeviceCanvas) return;

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
 leftControls.style.top=`${{controls.top}}px`;
 leftControls.style.bottom=`${{controls.bottom}}px`;
 leftControls.style.width=`${{controls.left}}px`;
 rightControls.style.top=`${{controls.top}}px`;
 rightControls.style.bottom=`${{controls.bottom}}px`;
 rightControls.style.width=`${{controls.right}}px`;

 const rtiCanvasWidth=Math.max(appWidth-controls.left-controls.right,1);
 const rtiCanvasHeight=Math.max(appHeight-controls.top-controls.bottom,1);
 rtiCanvas.style.left=`${{controls.left}}px`;
 rtiCanvas.style.top=`${{controls.top}}px`;
 rtiCanvas.style.width=`${{rtiCanvasWidth}}px`;
 rtiCanvas.style.height=`${{rtiCanvasHeight}}px`;

 const widthScale=rtiCanvasWidth/SOURCE_DEVICE_SIZE.width;
 const heightScale=rtiCanvasHeight/SOURCE_DEVICE_SIZE.height;
 let scale=Math.min(widthScale,heightScale);
 const maxScale=Number(RTI_DEVICE_LAYOUT.maxScale ?? 10);
 const minScale=Number(RTI_DEVICE_LAYOUT.minScale ?? 0.25);
 if (!Boolean(RTI_DEVICE_LAYOUT.allowScaleAboveOne)) {{
   scale=Math.min(scale,1);
 }}
 scale=Math.min(maxScale, Math.max(minScale, scale));
 const totalScale=scale*(currentZoomPercent/100);
 const fittedWidth=SOURCE_DEVICE_SIZE.width*totalScale;
 const fittedHeight=SOURCE_DEVICE_SIZE.height*totalScale;
 const contentWidth=Math.max(rtiCanvasWidth,fittedWidth);
 const contentHeight=Math.max(rtiCanvasHeight,fittedHeight);
 const offsetLeft=(contentWidth-fittedWidth)/2;
 const offsetTop=(contentHeight-fittedHeight)/2;
 const navEdgeOffset=Number(VIEWPORT_NAV.placement?.edgeOffset||36);
 rtiContent.style.width=`${{contentWidth}}px`;
 rtiContent.style.height=`${{contentHeight}}px`;
 rtiDeviceCanvas.style.left=`${{offsetLeft}}px`;
 rtiDeviceCanvas.style.top=`${{offsetTop}}px`;
 rtiDeviceCanvas.style.width=`${{fittedWidth}}px`;
 rtiDeviceCanvas.style.height=`${{fittedHeight}}px`;
 currentTotalScale=totalScale;
 currentDeviceLeft=offsetLeft;
 currentDeviceTop=offsetTop;
 rtiCanvas.classList.toggle('scroll-hover', Boolean(ZOOM_CONTROLS.scrollbars?.showOnHover) && currentZoomPercent > 100);

  const pageEl=activePageEl();
  let viewportLeft=controls.left+currentDeviceLeft-rtiCanvas.scrollLeft;
  let viewportRight=viewportLeft+fittedWidth;
  let viewportTop=controls.top+currentDeviceTop-rtiCanvas.scrollTop;
  let viewportBottom=viewportTop+fittedHeight;
  const firstViewport=pageEl ? pageEl.querySelector('.vp-box') : null;
  if (firstViewport) {{
    viewportLeft=controls.left+currentDeviceLeft+rtiCanvas.clientLeft+((Number(firstViewport.dataset.left||0)*totalScale)-rtiCanvas.scrollLeft);
    viewportTop=controls.top+currentDeviceTop+rtiCanvas.clientTop+((Number(firstViewport.dataset.top||0)*totalScale)-rtiCanvas.scrollTop);
    viewportRight=viewportLeft+(Number(firstViewport.dataset.width||0)*totalScale);
    viewportBottom=viewportTop+(Number(firstViewport.dataset.height||0)*totalScale);
  }}
  const leftArrowLeft=Math.max(viewportLeft-navEdgeOffset-44,0);
  const rightArrowLeft=Math.max(viewportRight+navEdgeOffset,0);
  const arrowTop=Math.max(viewportTop+(((viewportBottom-viewportTop)-44)/2),0);
 leftControls.style.left=`${{leftArrowLeft}}px`;
 leftControls.style.width='44px';
 leftControls.style.height='44px';
 leftControls.style.top=`${{arrowTop}}px`;
 leftControls.style.bottom='auto';
 leftControls.style.right='auto';

 rightControls.style.left=`${{rightArrowLeft}}px`;
 rightControls.style.width='44px';
 rightControls.style.height='44px';
 rightControls.style.top=`${{arrowTop}}px`;
 rightControls.style.bottom='auto';
 rightControls.style.right='auto';

 if (ZOOM_CONTROLS.enabled) {{
   const zoomWidth = zoomControls.offsetWidth || 176;
   const zoomLeft = Math.max((controls.left - zoomWidth) / 2, 0);
   zoomControls.style.left = `${{zoomLeft}}px`;
   zoomControls.style.top = `${{controls.top}}px`;
   const zoomReset = zoomControls.querySelector('.zoom-reset');
   if (zoomReset) zoomReset.textContent = `${{currentZoomPercent}}%`;
 }}

 document.querySelectorAll('.device-page').forEach(page=>page.classList.toggle('active', Number(page.dataset.pageIndex)===activePageIndex));
 document.querySelectorAll('.device-page .vp-box').forEach(el=>{{
   const left=Number(el.dataset.left||0)*totalScale;
   const top=Number(el.dataset.top||0)*totalScale;
   const width=Number(el.dataset.width||0)*totalScale;
   const height=Number(el.dataset.height||0)*totalScale;
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
 }});

 document.querySelectorAll('.device-page .btn-wrap').forEach(el=>{{
   const left=Number(el.dataset.left||0)*totalScale;
   const top=Number(el.dataset.top||0)*totalScale;
   const width=Number(el.dataset.width||0)*totalScale;
   const height=Number(el.dataset.height||0)*totalScale;
   const visible=String(el.dataset.visible||'1')==='1';
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
   if (!el.classList.contains('vp-btn')) {{
     el.style.display=visible?'':'none';
   }}
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
 syncHeader();
 syncViewportControls();
 applyViewportState();
}}
function clamp(value,min,max){{return Math.min(max,Math.max(min,value));}}
function updateZoom(nextPercent){{
 const rtiCanvas=document.getElementById('rtiCanvas');
 if (!rtiCanvas) return;
 const oldScale=currentTotalScale||1;
 const oldLeft=currentDeviceLeft||0;
 const oldTop=currentDeviceTop||0;
 const centerX=(rtiCanvas.scrollLeft+(rtiCanvas.clientWidth/2)-oldLeft)/oldScale;
 const centerY=(rtiCanvas.scrollTop+(rtiCanvas.clientHeight/2)-oldTop)/oldScale;
 currentZoomPercent=clamp(nextPercent, ZOOM_DEFAULT, ZOOM_MAX);
 applyRtiLayout();
 const maxScrollLeft=Math.max(rtiCanvas.scrollWidth-rtiCanvas.clientWidth,0);
 const maxScrollTop=Math.max(rtiCanvas.scrollHeight-rtiCanvas.clientHeight,0);
 rtiCanvas.scrollLeft=clamp((currentDeviceLeft+(centerX*currentTotalScale))-(rtiCanvas.clientWidth/2),0,maxScrollLeft);
 rtiCanvas.scrollTop=clamp((currentDeviceTop+(centerY*currentTotalScale))-(rtiCanvas.clientHeight/2),0,maxScrollTop);
}}
function setActivePage(nextPageIndex) {{
 const target=Number(nextPageIndex);
 if (!Number.isFinite(target) || !PAGE_STATE[target]) return;
 activePageIndex=target;
 currentViewportIndexes=(PAGE_STATE[target].vpFrames||[]).map(()=>0);
 const rtiCanvas=document.getElementById('rtiCanvas');
 if (rtiCanvas) {{
   rtiCanvas.scrollLeft=0;
   rtiCanvas.scrollTop=0;
 }}
 applyRtiLayout();
}}
window.addEventListener('resize', applyRtiLayout);
applyRtiLayout();
const rtiCanvasEl=document.getElementById('rtiCanvas');
if (rtiCanvasEl) rtiCanvasEl.addEventListener('scroll', applyRtiLayout, {{passive:true}});
document.querySelectorAll('.page-link-hit[data-target-page-index]').forEach(link=>link.addEventListener('click',e=>{{
 e.preventDefault();
 setActivePage(link.dataset.targetPageIndex);
}}));
const zoomDec=document.querySelector('.zoom-dec');
const zoomInc=document.querySelector('.zoom-inc');
const zoomReset=document.querySelector('.zoom-reset');
if (zoomDec) zoomDec.addEventListener('click',()=>updateZoom(currentZoomPercent-ZOOM_STEP));
if (zoomInc) zoomInc.addEventListener('click',()=>updateZoom(currentZoomPercent+ZOOM_STEP));
if (zoomReset) zoomReset.addEventListener('click',()=>updateZoom(ZOOM_DEFAULT));
const prev=document.getElementById('vpPrev');
const next=document.getElementById('vpNext');
if (prev && next) {{
  prev.addEventListener('click',()=>{{
    const frames=activePageState().vpFrames||[];
    if (frames.length && currentViewportIndexes[0]>0) {{
      currentViewportIndexes[0]--;
      applyViewportState();
    }}
  }});
  next.addEventListener('click',()=>{{
    const frames=activePageState().vpFrames||[];
    if (frames.length && currentViewportIndexes[0]<frames[0].length-1) {{
      currentViewportIndexes[0]++;
      applyViewportState();
    }}
  }});
}}
</script></body></html>"""


def _event_section_items(project_data: dict[str, Any], event_key: str) -> list[dict[str, Any]]:
    events = project_data.get("events", {})
    if not isinstance(events, dict):
        return []
    items = events.get(event_key, [])
    return items if isinstance(items, list) else []


def _event_button_text(item: dict[str, Any], event_kind: str) -> str:
    user = item.get("userFacing", {}) if isinstance(item, dict) else {}
    trigger = str(user.get("resolvedTrigger") or "No trigger").strip()
    macro = str(user.get("macroName") or "No macro").strip()
    if event_kind == "driver":
        return f"When {trigger} happens, run macro {macro}"
    description = str(user.get("description") or user.get("eventType") or "System Event").strip()
    return f"{description} | {trigger}, run macro {macro}"


def _event_meta(item: dict[str, Any], event_kind: str) -> dict[str, Any]:
    user = item.get("userFacing", {}) if isinstance(item, dict) else {}
    if event_kind == "driver":
        identity = str(user.get("driverName") or "Driver Event").strip()
    else:
        identity = str(user.get("description") or user.get("eventType") or "System Event").strip()
    targets: list[str] = []
    test_targets = user.get("testTargets", {})
    if isinstance(test_targets, dict):
        if test_targets.get("Trigger"):
            targets.append("Trigger")
        if test_targets.get("Macro"):
            targets.append("Macro")
    return {
        "category": "Driver Event" if event_kind == "driver" else "System Event",
        "identity": identity,
        "buttonType": "",
        "targets": targets,
    }


def render_project_home_html(project_data: dict[str, Any], app_ui: dict[str, Any], project_stem: str) -> str:
    source = project_data.get("source", {})
    source_file = str(source.get("file") or project_stem)
    project_title = Path(source_file).stem if source_file else project_stem
    system_events = _event_section_items(project_data, "system")
    driver_events = _event_section_items(project_data, "driver")
    devices = project_data.get("devices", [])

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
.home-section h2{{margin:0 0 16px;font-size:22px;line-height:1.1;}}
.home-subtitle{{margin:18px 0 10px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#5a7387;}}
.home-list{{display:flex;flex-direction:column;gap:12px;}}
.home-row{{width:100%;display:block;box-sizing:border-box;padding:16px 18px;border-radius:16px;border:1px solid #a9bccd;background:#1e5f86;color:#fff;text-decoration:none;font-size:15px;line-height:1.35;text-align:left;box-shadow:inset 0 0 0 1px #154665;}}
.home-row:hover{{filter:brightness(1.05);}}
.event-row{{cursor:pointer;}}
.device-row{{background:#29445a;box-shadow:inset 0 0 0 1px #1c3244;}}
.home-empty{{padding:16px 18px;border:1px dashed #a9bccd;border-radius:16px;background:#edf4f8;color:#557082;font-size:14px;}}
.ov{{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:flex-start;justify-content:center;padding:8px 12px 12px;z-index:10000;}}
.ov.open{{display:flex;}}
.pop{{width:min(980px,100%);background:#fff;border:1px solid #cbd7e2;border-radius:18px;padding:20px 24px;margin-top:0;}}
.pop h3{{margin:0 0 16px;font-size:16px;line-height:1.1;font-weight:700;}}
.row{{border:1px solid #d4dee8;border-radius:14px;padding:12px 14px;margin-bottom:12px;}}
.n{{font-weight:600;margin-bottom:10px;font-size:14px;line-height:1.1;}}
.actions{{display:flex;gap:10px;margin-bottom:10px;}}
.actions button{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;}}
textarea{{border:1px solid #ccd8e2;border-radius:10px;padding:10px 12px;font-size:13px;line-height:1.2;}}
#close{{border:1px solid #a9bccd;background:#f7fbff;border-radius:10px;padding:6px 16px;font-size:13px;line-height:1;cursor:pointer;color:#14324b;display:block;margin-left:auto;}}
</style></head>
<body>
<main class='home-shell'>
<section class='home-header'>
<div class='home-kicker'>Project Home</div>
<h1 class='home-title'>{project_title}</h1>
<div class='home-source'>{source_file}</div>
</section>
<section class='home-section'>
<h2>System Events</h2>
<div class='home-list'>{system_content}</div>
</section>
<section class='home-section'>
<h2>Driver Events</h2>
<div class='home-list'>{driver_content}</div>
</section>
<section class='home-section'>
<h2>Devices</h2>
<div class='home-list'>{device_content}</div>
</section>
</main>
<div class='ov' id='ov'><div class='pop'><h3 id='pt'></h3><div id='rows'></div><button id='close'>Close</button></div></div>
<script>
const APP_UI={app_json};
const ov=document.getElementById('ov'),pt=document.getElementById('pt'),rows=document.getElementById('rows');
function esc(s){{return String(s??'').replace(/[&<>\"]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[m]));}}
document.querySelectorAll('.test-btn').forEach(b=>b.addEventListener('click',()=>{{
 const m=JSON.parse(b.dataset.meta||'{{}}');
 const suffix=(APP_UI.testingPopup?.includeButtonTypeInTitle&&m.buttonType)?` (${{m.buttonType}})`:'';
 pt.textContent=(APP_UI.testingPopup?.titleTemplate||'{{category}} Test - {{identity}}').replace('{{category}}',m.category).replace('{{identity}}',m.identity)+suffix;
 rows.innerHTML=(m.targets||[]).map(t=>`<div class='row'><div class='n'>${{esc(t)}}</div><div class='actions'><button>Pass</button><button>Fail</button></div><textarea placeholder='Fail note' style='width:100%;min-height:70px;'></textarea></div>`).join('')||"<div class='row'><div class='n'>No true test targets.</div></div>";
 ov.classList.add('open');
}}));
document.getElementById('close').addEventListener('click',()=>ov.classList.remove('open'));
ov.addEventListener('click',e=>{{if(e.target===ov)ov.classList.remove('open')}});
</script></body></html>"""
def render_single_device_html(project_data: dict[str, Any], app_ui: dict[str, Any], project_stem: str, device_index: int = 0) -> str:
    device = project_data["devices"][device_index]
    uf = device["userFacing"]
    res = uf.get("deviceUI", {}).get("portrait", {}).get("resolution", {"width": 480, "height": 854})
    w = int(res.get("width") or 480)
    h = int(res.get("height") or 854)
    pages = uf.get("pages", [])
    title = app_ui.get("header", {}).get("titleTemplate", "{deviceName} - {pageName}")
    first_page_name = str(pages[0].get("pageName", "")) if pages else ""
    header = title.replace("{deviceName}", uf.get("displayName", "")).replace("{pageName}", first_page_name)

    page_markup: list[str] = []
    page_state: list[dict[str, Any]] = []
    for page_index, _page in enumerate(pages):
        payload = _page_payload(project_data, app_ui, project_stem, device_index, page_index)
        page_markup.append(
            f"<div class='device-page{' active' if page_index == 0 else ''}' data-page-index='{page_index}'>"
            f"{payload['viewport_boxes']}{payload['page_button_rows']}{payload['viewport_button_rows']}</div>"
        )
        page_state.append(
            {
                "deviceName": uf.get("displayName", ""),
                "pageName": payload["page_name"],
                "vpFrames": payload["vp_frames"],
            }
        )
    return _render_document(app_ui, header, w, h, "".join(page_markup), json.dumps(page_state), home_href=project_home_filename(project_stem))
