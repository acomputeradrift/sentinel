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


def page_filename(project_stem: str, page_name: str, page_index: int) -> str:
    return f"{project_stem}__page-{page_index}-{page_slug(page_name, page_index)}.html"


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


def _iter_viewport_boxes(page: dict[str, Any]) -> list[dict[str, int]]:
    out: list[dict[str, int]] = []
    for viewport in page.get("viewports", []):
        c = viewport.get("viewportUI", {}).get("coordinates", {})
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
        vp_c = viewport.get("viewportUI", {}).get("coordinates", {})
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
    user_pages = project_data["devices"][device_index]["userFacing"]["pages"]
    diag_pages = project_data["devices"][device_index].get("diagnostics", {}).get("pages", [])
    out: dict[int, str] = {}
    for index, diag_page in enumerate(diag_pages):
        if index >= len(user_pages):
            break
        page_id = diag_page.get("pageId")
        if page_id is None:
            continue
        page_name = user_pages[index].get("pageName", "")
        out[int(page_id)] = page_filename(project_stem, str(page_name), index)
    return out


def _render_button_control(btn: dict[str, Any], label: str, left: int, top: int, variable_label: str, app_ui: dict[str, Any], page_targets: dict[int, str], extra_classes: str = "", extra_style: str = "", extra_attrs: str = "") -> str:
    c = btn["buttonUI"]["coordinates"]
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
            link_html = (
                f"<a class='page-link-hit' href='{target_href}' aria-label='Open linked page' "
                f"data-hit-width='{nav_width}' data-hit-padding='{nav_pad}'>"
                f"<span class='page-link-icon' data-icon-size='{icon_size}'>{icon}</span></a>"
            )
    return (
        f"<div class='{classes}' data-left='{left}' data-top='{top}' data-width='{width}' data-height='{height}' data-font-size='{fs}' data-visible='{visibility_attr}' {extra_attrs}>"
        f"<button class='test-btn' data-meta='{meta_attr}'>{_btn_text(identity)}</button>"
        f"{link_html}</div>"
    )


def render_html(project_data: dict[str, Any], app_ui: dict[str, Any], project_stem: str, device_index: int = 0, page_index: int = 0) -> str:
    device = project_data["devices"][device_index]
    uf = device["userFacing"]
    page = uf["pages"][page_index]

    res = uf.get("deviceUI", {}).get("portrait", {}).get("resolution", {"width": 480, "height": 854})
    w = int(res.get("width") or 480)
    h = int(res.get("height") or 854)

    title = app_ui.get("header", {}).get("titleTemplate", "{deviceName} - {pageName}")
    header = title.replace("{deviceName}", uf.get("displayName", "")).replace("{pageName}", page.get("pageName", ""))
    variable_label = app_ui.get("testingPopup", {}).get("variableLabelTemplate", "Variable - {variableType}")
    page_targets = _page_target_map(project_data, project_stem, device_index)
    link_cfg = app_ui.get("appNavigation", {}).get("pageLinks", {})
    link_hover_enabled = bool(link_cfg.get("enabled") and link_cfg.get("showLinkAffordanceOnHover"))
    layout_cfg = app_ui.get("layout", {})
    control_cfg = layout_cfg.get("appUIControls", {})
    rti_device_cfg = layout_cfg.get("rtiDeviceCanvas", {})

    page_button_rows: list[str] = []
    for btn, label, off_top, off_left in _iter_page_buttons(page):
        c = btn["buttonUI"]["coordinates"]
        page_button_rows.append(
            _render_button_control(
                btn,
                label,
                int(c.get("left") or 0) + off_left,
                int(c.get("top") or 0) + off_top,
                variable_label,
                app_ui,
                page_targets,
            )
        )

    viewport_button_rows: list[str] = []
    for vb in _iter_viewport_buttons(page):
        btn = vb["btn"]
        c = btn["buttonUI"]["coordinates"]
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
                extra_classes="vp-btn",
                extra_style=extra,
                extra_attrs=f"data-vp='{vb['vp_index']}' data-frame='{vb['frame_id']}'",
            )
        )

    vp_frames = [sorted([int(f.get("frameId", 0)) for f in vp.get("frames", [])]) for vp in page.get("viewports", [])]
    vp_nav_enabled = bool(app_ui.get("viewportNavigation", {}).get("enabled", False) and vp_frames and vp_frames[0])
    vp_dot_rows = ""
    if vp_nav_enabled:
        dots = "".join([f"<span class='dot{' active' if i == 0 else ''}' data-dot='{i}'></span>" for i, _ in enumerate(vp_frames[0])])
        vp_dot_rows = f"<div class='vp-indicator' id='vpIndicator'>{dots}</div>"
    nav_prev = "<button class='vp-nav vp-prev' id='vpPrev' aria-label='Previous frame'>&lsaquo;</button>" if vp_nav_enabled else ""
    nav_next = "<button class='vp-nav vp-next' id='vpNext' aria-label='Next frame'>&rsaquo;</button>" if vp_nav_enabled else ""

    app_json = json.dumps(app_ui)
    control_json = json.dumps(control_cfg)
    rti_device_json = json.dumps(rti_device_cfg)
    vp_frames_json = json.dumps(vp_frames)
    viewport_boxes = "".join(
        [
            "<div class='vp-box' data-left='{left}' data-top='{top}' data-width='{width}' data-height='{height}'></div>".format(**c)
            for c in _iter_viewport_boxes(page)
        ]
    )

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
.header{{font-weight:700;font-size:20px;text-align:center;display:flex;align-items:center;justify-content:center;width:100%;height:100%;}}
.rti-canvas{{position:absolute;box-sizing:border-box;z-index:1;}}
.rti-device-canvas{{position:absolute;border:1px solid #c6d2dd;border-radius:10px;background:#f8fbfe;overflow:hidden;box-sizing:border-box;z-index:2;}}
.vp-box{{position:absolute;border:2px dashed #88a6bd;border-radius:0;background:transparent;pointer-events:none;z-index:1;box-sizing:border-box;}}
.btn-wrap{{position:absolute;z-index:2;}}
.test-btn{{position:absolute;inset:0;box-sizing:border-box;border:0;border-radius:10px;background:#1e5f86;box-shadow:inset 0 0 0 1px #154665;color:#fff;line-height:1.1;white-space:pre-line;cursor:pointer;overflow:hidden;padding:0;}}
.page-link-hit{{position:absolute;top:0;right:0;height:100%;display:flex;align-items:center;justify-content:flex-end;text-decoration:none;color:#fff;opacity:{'0' if link_hover_enabled else '1'};pointer-events:{'none' if link_hover_enabled else 'auto'};transition:opacity .15s ease;}}
.btn-wrap:hover .page-link-hit{{opacity:1;pointer-events:auto;}}
.page-link-icon{{display:inline-flex;align-items:center;justify-content:center;background:transparent;border-radius:0;}}
.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24;font-size:115%;line-height:1;}}
.vp-nav{{width:44px;height:44px;border-radius:14px;border:2px solid #f0a126;background:transparent;color:#29445a;font-size:22px;cursor:pointer;position:relative;z-index:21;}}
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
<div class='app-ui-controls top-controls' id='topControls'><div class='header'>{header}</div></div>
<div class='app-ui-controls left-controls' id='leftControls'>{nav_prev}</div>
<div class='app-ui-controls right-controls' id='rightControls'>{nav_next}</div>
<div class='app-ui-controls bottom-controls' id='bottomControls'>{vp_dot_rows}</div>
<div class='rti-canvas' id='rtiCanvas'><div class='rti-device-canvas' id='rtiDeviceCanvas'>{viewport_boxes}{''.join(page_button_rows)}{''.join(viewport_button_rows)}</div></div></div>
<div class='ov' id='ov'><div class='pop'><h3 id='pt'></h3><div id='rows'></div><button id='close'>Close</button></div></div>
<script>
const APP_UI={app_json};
const APP_UI_CONTROLS={control_json};
const RTI_DEVICE_LAYOUT={rti_device_json};
const VIEWPORT_NAV={json.dumps(app_ui.get("viewportNavigation", {}))};
const SOURCE_DEVICE_SIZE={{width:{w},height:{h}}};
const VP_FRAMES={vp_frames_json};
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
function applyRtiLayout() {{
 const appCanvas=document.getElementById('appCanvas');
 const topControls=document.getElementById('topControls');
 const bottomControls=document.getElementById('bottomControls');
 const leftControls=document.getElementById('leftControls');
 const rightControls=document.getElementById('rightControls');
 const rtiCanvas=document.getElementById('rtiCanvas');
 const rtiDeviceCanvas=document.getElementById('rtiDeviceCanvas');
 if (!appCanvas || !topControls || !bottomControls || !leftControls || !rightControls || !rtiCanvas || !rtiDeviceCanvas) return;

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
 const fittedWidth=SOURCE_DEVICE_SIZE.width*scale;
 const fittedHeight=SOURCE_DEVICE_SIZE.height*scale;
 const offsetLeft=(rtiCanvasWidth-fittedWidth)/2;
 const offsetTop=(rtiCanvasHeight-fittedHeight)/2;
 const navEdgeOffset=Number(VIEWPORT_NAV.placement?.edgeOffset||36);
 rtiDeviceCanvas.style.left=`${{offsetLeft}}px`;
 rtiDeviceCanvas.style.top=`${{offsetTop}}px`;
 rtiDeviceCanvas.style.width=`${{fittedWidth}}px`;
 rtiDeviceCanvas.style.height=`${{fittedHeight}}px`;

 const leftArrowLeft=Math.max((controls.left+offsetLeft)-navEdgeOffset-44,0);
 const rightArrowLeft=Math.max((controls.left+offsetLeft+fittedWidth)+navEdgeOffset,0);
 const arrowTop=Math.max((controls.top+offsetTop)+((fittedHeight-44)/2),0);
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

 document.querySelectorAll('.vp-box').forEach(el=>{{
   const left=Number(el.dataset.left||0)*scale;
   const top=Number(el.dataset.top||0)*scale;
   const width=Number(el.dataset.width||0)*scale;
   const height=Number(el.dataset.height||0)*scale;
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
 }});

 document.querySelectorAll('.btn-wrap').forEach(el=>{{
   const left=Number(el.dataset.left||0)*scale;
   const top=Number(el.dataset.top||0)*scale;
   const width=Number(el.dataset.width||0)*scale;
   const height=Number(el.dataset.height||0)*scale;
   const visible=String(el.dataset.visible||'1')==='1';
   el.style.left=`${{left}}px`;
   el.style.top=`${{top}}px`;
   el.style.width=`${{width}}px`;
   el.style.height=`${{height}}px`;
   el.style.display=visible?'':'none';
   const button=el.querySelector('.test-btn');
   if (button) {{
     const sourceFont=Number(el.dataset.fontSize||APP_UI.buttonPresentation?.fallbackFontSize||10);
     if (APP_UI.buttonPresentation?.scaleRtiDerivedFontSizes) {{
       button.style.fontSize=`${{Math.max(1, sourceFont*scale)}}px`;
     }} else {{
       button.style.fontSize=`${{sourceFont}}px`;
     }}
     button.style.borderRadius=`${{Math.max(2, 10*scale)}}px`;
   }}
   const linkHit=el.querySelector('.page-link-hit');
   if (linkHit) {{
     const hitWidth=Number(linkHit.dataset.hitWidth||28)*scale;
     const hitPadding=Number(linkHit.dataset.hitPadding||8)*scale;
     linkHit.style.width=`${{hitWidth}}px`;
     linkHit.style.paddingRight=`${{hitPadding}}px`;
     const icon=linkHit.querySelector('.page-link-icon');
     if (icon) {{
       const iconSize=Number(icon.dataset.iconSize||16)*scale;
       icon.style.width=`${{iconSize}}px`;
       icon.style.height=`${{iconSize}}px`;
       icon.style.fontSize=`${{iconSize}}px`;
     }}
   }}
 }});
}}
window.addEventListener('resize', applyRtiLayout);
applyRtiLayout();
if (VP_FRAMES.length && VP_FRAMES[0].length) {{
 let vp0 = 0;
 const prev=document.getElementById('vpPrev');
 const next=document.getElementById('vpNext');
 const dots=[...document.querySelectorAll('#vpIndicator .dot')];
 const apply=()=>{{
   const frame=VP_FRAMES[0][vp0];
   document.querySelectorAll('.vp-btn[data-vp=\"0\"]').forEach(el=>{{el.style.display=(Number(el.dataset.frame)===frame)?'':'none';}});
   dots.forEach((d,i)=>d.classList.toggle('active',i===vp0));
 }};
 if (prev && next) {{
   prev.addEventListener('click',()=>{{ if(vp0>0){{vp0--;apply();}} }});
   next.addEventListener('click',()=>{{ if(vp0<VP_FRAMES[0].length-1){{vp0++;apply();}} }});
 }}
 apply();
}}
</script></body></html>"""
