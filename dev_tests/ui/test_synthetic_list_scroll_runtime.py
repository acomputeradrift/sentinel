"""
Playwright runtime tests: synthetic room/source list rows must stay inside the host list
scroll shell (overflow-y scroll), not only pass HTML string assertions.

AGENTS.md: HTML UI behavior requires browser-level verification.
"""

from __future__ import annotations

import socket
import sys
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import load_json, render_single_device_html


def _room_list_overflow_page() -> dict:
    """Host height 60px, fixed row 20px + 2px gap → 4 rows need 86px → scroll required."""
    list_btn = {
        "buttonIdentity": {"buttonTagName": "DISPLAY - Room List", "text": "", "buttonType": None},
        "buttonUI": {
            "fontSize": 12,
            "listItemHeightPx": 20,
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"left": 10, "top": 20, "width": 200, "height": 60}},
                "landscape": {"visible": True, "coordinates": {"left": 110, "top": 120, "width": 220, "height": 60}},
            },
            "stack": {"layerOrder": 0, "buttonOrder": 1, "frameNumber": 0},
        },
        "testTargets": {
            "text": False,
            "macros": False,
            "macroSteps": False,
            "variables": {k: (k == "List") for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List")},
            "graphics": {"bitmap": False, "icon": False},
            "pageLink": False,
        },
    }
    return {
        "pageName": "Controller",
        "pageId": 1,
        "rtiAddress": 99,
        "layers": [
            {
                "layerName": "Main",
                "layerOrder": 0,
                "sharedLayerId": 0,
                "buttonCategories": {
                    "screenLabels": [],
                    "screenButtons": [list_btn],
                    "hardButtons": [],
                    "uiItems": [],
                },
                "viewports": [],
            }
        ],
    }


def _device_ui_standard() -> dict:
    """Match other UI runtime tests so orientation + scale behave deterministically."""
    return {
        "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
        "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
    }


def _four_rooms_diag() -> dict:
    rooms = []
    for i in range(4):
        rid = i + 1
        rooms.append(
            {
                "roomId": rid,
                "roomName": f"Room {rid}",
                "controllerRoomOrder": i,
                "roomSelectTagsAll": [],
                "roomSelectRoomLabelTags": [
                    {"buttonTagId": 1080 + rid, "buttonTagName": f"Room: R{rid}", "macroId": 700 + rid}
                ],
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": []},
            }
        )
    return {
        "deviceId": 1,
        "pages": [
            {"pageId": 1, "buttons": [], "viewports": []},
            {"pageId": 2, "buttons": [], "viewports": []},
        ],
        "rooms": rooms,
        "sourceListRows": [],
    }


def _global_source_list_overflow_page() -> dict:
    """Host portrait height 50px; 6 rows at 10px + gap 2 → 6*10+5*2 = 70 > 50."""
    list_btn = {
        "buttonIdentity": {"buttonTagName": "DISPLAY - Source List", "text": "", "buttonType": None},
        "buttonUI": {
            "fontSize": 12,
            "listItemHeightPx": 10,
            "orientations": {
                "portrait": {"visible": True, "coordinates": {"left": 40, "top": 30, "width": 220, "height": 50}},
                "landscape": {"visible": True, "coordinates": {"left": 140, "top": 130, "width": 260, "height": 50}},
            },
            "stack": {"layerOrder": 0, "buttonOrder": 7, "frameNumber": 0},
        },
        "testTargets": {
            "text": False,
            "macros": False,
            "macroSteps": False,
            "variables": {k: (k == "List") for k in ("Text", "Reversed", "Inactive", "Visible", "Value", "State", "Command", "Image", "List")},
            "graphics": {"bitmap": False, "icon": False},
            "pageLink": False,
        },
    }
    return {
        "pageName": "Sources",
        "pageId": 3,
        "rtiAddress": 99,
        "layers": [
            {
                "layerName": "Main",
                "layerOrder": 0,
                "sharedLayerId": 0,
                "buttonCategories": {"screenLabels": [], "screenButtons": [list_btn], "hardButtons": [], "uiItems": []},
                "viewports": [],
            }
        ],
    }


def _six_checked_sources_diag() -> dict:
    rows = []
    for i in range(6):
        rows.append(
            {
                "roomId": 1,
                "roomName": "Kitchen",
                "sourceDeviceId": 10 + i,
                "sourceName": f"Source {i}",
                "activityOrder": i,
                "checked": 1,
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": None},
            }
        )
    return {
        "deviceId": 1,
        "pages": [{"pageId": 3, "buttons": [], "viewports": []}],
        "rooms": [
            {
                "roomId": 1,
                "roomName": "Kitchen",
                "controllerRoomOrder": 0,
                "roomSelectTagsAll": [],
                "roomSelectRoomLabelTags": [{"buttonTagId": 1, "buttonTagName": "R", "macroId": 1}],
                "resolvedPageLink": {},
            }
        ],
        "sourceListRows": rows,
    }


def _two_room_checked_sources_diag() -> dict:
    rows = []
    for i in range(3):
        rows.append(
            {
                "roomId": 1,
                "roomName": "Kitchen",
                "sourceDeviceId": 110 + i,
                "sourceName": f"K-{i}",
                "activityOrder": i,
                "checked": 1,
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": None},
            }
        )
    for i in range(3):
        rows.append(
            {
                "roomId": 2,
                "roomName": "Office",
                "sourceDeviceId": 210 + i,
                "sourceName": f"O-{i}",
                "activityOrder": i,
                "checked": 1,
                "resolvedPageLink": {"targetPageId": None, "targetPageName": None, "resolutionPath": None},
            }
        )
    return {
        "deviceId": 1,
        "pages": [{"pageId": 3, "buttons": [], "viewports": []}],
        "rooms": [
            {
                "roomId": 1,
                "roomName": "Kitchen",
                "controllerRoomOrder": 0,
                "roomSelectTagsAll": [],
                "roomSelectRoomLabelTags": [{"buttonTagId": 1, "buttonTagName": "K", "macroId": 1}],
                "resolvedPageLink": {},
            },
            {
                "roomId": 2,
                "roomName": "Office",
                "controllerRoomOrder": 1,
                "roomSelectTagsAll": [],
                "roomSelectRoomLabelTags": [{"buttonTagId": 2, "buttonTagName": "O", "macroId": 2}],
                "resolvedPageLink": {},
            },
        ],
        "sourceListRows": rows,
    }


class SyntheticListScrollRuntimeTest(unittest.TestCase):
    """Browser-level checks for .synthetic-list-scroll containment."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(
                f"playwright import failed ({type(exc).__name__}: {exc!s}); "
                "install with devtools/bootstrap_tmp_apex_env.py or set SENTINEL_VENV_PYTHON"
            ) from exc
        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()

    class _StaticServer:
        def __init__(self, directory: Path):
            self._directory = directory
            self._httpd: ThreadingHTTPServer | None = None
            self._thread: threading.Thread | None = None
            self.base_url: str | None = None

        def start(self) -> None:
            directory = self._directory

            class Handler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=str(directory), **kwargs)

                def log_message(self, fmt: str, *args) -> None:
                    return

            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            _host, port = sock.getsockname()
            sock.close()
            self._httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
            self._thread.start()
            self.base_url = f"http://127.0.0.1:{port}"

        def stop(self) -> None:
            if self._httpd:
                self._httpd.shutdown()
                self._httpd.server_close()
            if self._thread:
                self._thread.join(timeout=2)

    def _app_ui_browser_viewport(self) -> dict:
        return {
            "layout": {
                "appCanvas": {"mode": "browser-viewport"},
                "appUIControls": {"top": 52, "bottom": 32, "left": 240, "right": 240},
                "rtiCanvas": {"deriveFromAppCanvas": True},
                "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.25},
            },
            "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
            "appNavigation": {"enabled": True, "pageLinks": {"enabled": False}},
            "zoomControls": {"enabled": True},
            "viewportNavigation": {"enabled": True},
            "testingPopup": {"enabled": True},
            "buttonPresentation": {"fallbackFontSize": 10, "scaleRtiDerivedFontSizes": True},
            "state": {},
            "layerPanel": {"enabled": True},
        }

    def _write_device_html(self, project_data: dict) -> tuple[Path, Path]:
        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        merged = {**app_ui, **self._app_ui_browser_viewport()}
        html = render_single_device_html(project_data, merged, project_stem="synthetic_scroll_ui", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-synthetic-scroll-"))
        source_path = tmp_dir / "source_runtime.html"
        source_path.write_text(html, encoding="utf-8")
        shell_template = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "project_device_static_layout.html"
        shell_css = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "project_device_static_layout.css"
        shell_path = tmp_dir / "shell_runtime.html"
        css_copy = tmp_dir / "project_device_static_layout.css"
        css_copy.write_text(shell_css.read_text(encoding="utf-8"), encoding="utf-8")
        doc = shell_template.read_text(encoding="utf-8")
        doc = doc.replace(
            "</head>",
            '<meta name="sentinel-shell-source" content="/source_runtime.html"></head>',
            1,
        )
        shell_path.write_text(doc, encoding="utf-8")
        return shell_path, tmp_dir

    def _open_page(self, project_data: dict):
        shell_path, tmp_dir = self._write_device_html(project_data)
        server = self._StaticServer(tmp_dir)
        server.start()
        assert server.base_url
        page = self._browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{server.base_url}/{shell_path.name}", wait_until="domcontentloaded")
        page.wait_for_selector("#rtiDeviceContent .device-page.active .synthetic-list-scroll", timeout=15000)
        page.wait_for_timeout(400)
        return page, server, tmp_dir

    def test_room_list_scroll_shell_clips_overflow_and_scrolls(self):
        p2 = {"pageName": "B", "pageId": 2, "rtiAddress": 99, "layers": []}
        device = {
            "userFacing": {
                "displayName": "ScrollDevice",
                "deviceUI": _device_ui_standard(),
                "pages": [_room_list_overflow_page(), p2],
            },
            "diagnostics": _four_rooms_diag(),
        }
        project = {"devices": [device]}
        page, server, _tmp = self._open_page(project)
        try:
            result = page.evaluate(
                """
() => {
  const shell = document.querySelector('.synthetic-list-scroll[data-synthetic-list-kind="room"]');
  if (!shell) return { ok: false, reason: 'missing shell' };
  const rows = [...shell.querySelectorAll('.btn-wrap[data-synthetic-room-list]')];
  if (rows.length < 3) return { ok: false, reason: 'expected multiple rows', n: rows.length };
  const ch = shell.clientHeight;
  const cs = getComputedStyle(shell);
  const oy = cs.overflowY;
  if (oy !== 'auto' && oy !== 'scroll') return { ok: false, reason: 'bad overflow-y', oy };
  let maxBottom = 0;
  const heights = [];
  for (const r of rows) {
    const b = r.offsetTop + r.offsetHeight;
    maxBottom = Math.max(maxBottom, b);
    heights.push(r.offsetHeight);
  }
  // Absolute children may not inflate scrollHeight; compare stacked layout to viewport height.
  if (maxBottom <= ch + 1) {
    return { ok: false, reason: 'stack fits in shell without needing scroll (layout bug?)', maxBottom, ch, heights };
  }
  const canvas = document.getElementById('rtiDeviceCanvas');
  if (!canvas) return { ok: false, reason: 'no canvas' };
  const sr = shell.getBoundingClientRect();
  const cr = canvas.getBoundingClientRect();
  const inside =
    sr.top >= cr.top - 3 &&
    sr.left >= cr.left - 3 &&
    sr.bottom <= cr.bottom + 3 &&
    sr.right <= cr.right + 3;
  if (!inside) return { ok: false, reason: 'shell outside device canvas', sr, cr };
  shell.scrollTop = Math.max(0, shell.scrollHeight - shell.clientHeight);
  const last = rows[rows.length - 1];
  const lr = last.getBoundingClientRect();
  const sr2 = shell.getBoundingClientRect();
  const lastVisibleBottom = Math.min(lr.bottom, sr2.bottom);
  const lastVisibleTop = Math.max(lr.top, sr2.top);
  const lastSeen = lastVisibleBottom > lastVisibleTop + 2;
  if (!lastSeen) return { ok: false, reason: 'last row not visible after scroll', lr, sr2 };
  return { ok: true, maxBottom, ch, rowCount: rows.length, oy, heights };
}
"""
            )
            self.assertTrue(result.get("ok"), msg=str(result))
        finally:
            page.close()
            server.stop()

    def test_source_list_scroll_shell_clips_overflow(self):
        device = {
            "userFacing": {
                "displayName": "SourceScroll",
                "deviceUI": _device_ui_standard(),
                "pages": [_global_source_list_overflow_page()],
            },
            "diagnostics": _six_checked_sources_diag(),
        }
        project = {"devices": [device]}
        page, server, _tmp = self._open_page(project)
        try:
            result = page.evaluate(
                """
() => {
  const shell = document.querySelector('.synthetic-list-scroll[data-synthetic-list-kind="source"]');
  if (!shell) return { ok: false, reason: 'missing source shell' };
  const rows = [...shell.querySelectorAll('.btn-wrap[data-synthetic-source-list]')];
  if (rows.length < 4) return { ok: false, reason: 'expected multiple source rows', n: rows.length };
  const ch = shell.clientHeight;
  const oy = getComputedStyle(shell).overflowY;
  if (oy !== 'auto' && oy !== 'scroll') return { ok: false, reason: 'bad overflow-y on source shell', oy };
  const first = rows[0];
  if (!first) return { ok: false, reason: 'missing first source row' };
  if (first.offsetLeft < 8) return { ok: false, reason: 'source row missing left/right inset', offsetLeft: first.offsetLeft };
  let maxBottom = 0;
  for (const r of rows) {
    maxBottom = Math.max(maxBottom, r.offsetTop + r.offsetHeight);
  }
  if (maxBottom <= ch + 1) {
    return { ok: false, reason: 'source stack fits shell without scroll', maxBottom, ch };
  }
  return { ok: true, rows: rows.length, maxBottom, ch };
}
"""
            )
            self.assertTrue(result.get("ok"), msg=str(result))
        finally:
            page.close()
            server.stop()

    def test_source_list_selected_room_compacts_rows_to_top(self):
        device = {
            "userFacing": {
                "displayName": "SourceScroll",
                "deviceUI": _device_ui_standard(),
                "pages": [_global_source_list_overflow_page()],
            },
            "diagnostics": _two_room_checked_sources_diag(),
        }
        project = {"devices": [device]}
        page, server, _tmp = self._open_page(project)
        try:
            result = page.evaluate(
                """
() => {
  const shell = document.querySelector('.synthetic-list-scroll[data-synthetic-list-kind="source"]');
  if (!shell) return { ok: false, reason: 'missing source shell' };
  if (typeof setSelectedRoom !== 'function') return { ok: false, reason: 'setSelectedRoom unavailable' };
  setSelectedRoom(2, { persist: false });
  const rows = [...shell.querySelectorAll('.btn-wrap[data-synthetic-source-list]')];
  const visible = rows.filter(r => r.style.display !== 'none');
  if (visible.length !== 3) return { ok: false, reason: 'wrong visible count for selected room', visible: visible.length };
  const roomIds = [...new Set(visible.map(r => Number(r.dataset.syntheticSourceRoomId || 0)))];
  if (!(roomIds.length === 1 && roomIds[0] === 2)) return { ok: false, reason: 'visible rows include wrong rooms', roomIds };
  const tops = visible.map(r => r.offsetTop);
  const minTop = Math.min(...tops);
  if (minTop > 2) return { ok: false, reason: 'visible rows do not restart at shell top', tops };
  const pad = shell.querySelector('.synthetic-list-scroll-pad');
  if (!pad) return { ok: false, reason: 'missing scroll pad' };
  const activePad = Number(pad.dataset.activePadHeight || 0);
  if (activePad <= 0 || activePad > 200) return { ok: false, reason: 'active pad height not compacted', activePad };
  return { ok: true, visible: visible.length, roomIds, tops, activePad };
}
"""
            )
            self.assertTrue(result.get("ok"), msg=str(result))
        finally:
            page.close()
            server.stop()

    def test_source_list_first_load_starts_compacted_without_roundtrip(self):
        device = {
            "userFacing": {
                "displayName": "SourceScroll",
                "deviceUI": _device_ui_standard(),
                "pages": [_global_source_list_overflow_page()],
            },
            "diagnostics": _two_room_checked_sources_diag(),
        }
        project = {"devices": [device]}
        page, server, _tmp = self._open_page(project)
        try:
            page.wait_for_timeout(1200)
            result = page.evaluate(
                """
() => {
  const shell = document.querySelector('.device-page.active .synthetic-list-scroll[data-synthetic-list-kind="source"]');
  if (!shell) return { ok: false, reason: 'missing active source shell' };
  const rows = [...shell.querySelectorAll('.btn-wrap[data-synthetic-source-list]')];
  const visible = rows.filter(r => r.style.display !== 'none');
  if (!visible.length) return { ok: false, reason: 'no visible rows' };
  const tops = visible.map(r => r.offsetTop);
  const minTop = Math.min(...tops);
  const roomIds = [...new Set(visible.map(r => Number(r.dataset.syntheticSourceRoomId || 0)))];
  const head = visible.slice(0, 6).map(r => ({
    roomId: Number(r.dataset.syntheticSourceRoomId || 0),
    top: Number(r.dataset.top || 0),
    activeTop: Number(r.dataset.activeTop || 0),
    offsetTop: r.offsetTop,
    label: (r.querySelector('.test-btn')?.textContent || '').trim(),
  }));
  if (minTop > 4) return { ok: false, reason: 'first-load rows not compacted at top', minTop, roomIds, head };
  return { ok: true, minTop, roomIds, head };
}
"""
            )
            self.assertTrue(result.get("ok"), msg=str(result))
        finally:
            page.close()
            server.stop()

    def test_source_list_compaction_survives_layout_visibility_order(self):
        device = {
            "userFacing": {
                "displayName": "SourceScroll",
                "deviceUI": _device_ui_standard(),
                "pages": [_global_source_list_overflow_page()],
            },
            "diagnostics": _two_room_checked_sources_diag(),
        }
        project = {"devices": [device]}
        page, server, _tmp = self._open_page(project)
        try:
            result = page.evaluate(
                """
() => {
  if (typeof applyRtiLayout !== 'function' || typeof applyLayerVisibility !== 'function') {
    return { ok: false, reason: 'layout or visibility hooks unavailable' };
  }
  // Reproduce the problematic ordering observed on first load:
  // layout pass first, then selected-room visibility compaction.
  applyRtiLayout();
  applyLayerVisibility();
  const shell = document.querySelector('.device-page.active .synthetic-list-scroll[data-synthetic-list-kind="source"]');
  if (!shell) return { ok: false, reason: 'missing active source shell' };
  const rows = [...shell.querySelectorAll('.btn-wrap[data-synthetic-source-list]')];
  const visible = rows.filter(r => r.style.display !== 'none');
  if (!visible.length) return { ok: false, reason: 'no visible rows' };
  const minTop = Math.min(...visible.map(r => r.offsetTop));
  const head = visible.slice(0, 6).map(r => ({
    roomId: Number(r.dataset.syntheticSourceRoomId || 0),
    top: Number(r.dataset.top || 0),
    activeTop: Number(r.dataset.activeTop || 0),
    offsetTop: r.offsetTop,
    label: (r.querySelector('.test-btn')?.textContent || '').trim(),
  }));
  if (minTop > 4) return { ok: false, reason: 'rows stale after visibility pass', minTop, head };
  return { ok: true, minTop, head };
}
"""
            )
            self.assertTrue(result.get("ok"), msg=str(result))
        finally:
            page.close()
            server.stop()

    def test_source_list_compaction_survives_orientation_toggle(self):
        device = {
            "userFacing": {
                "displayName": "SourceScroll",
                "deviceUI": _device_ui_standard(),
                "pages": [_global_source_list_overflow_page()],
            },
            "diagnostics": _two_room_checked_sources_diag(),
        }
        project = {"devices": [device]}
        page, server, _tmp = self._open_page(project)
        try:
            result = page.evaluate(
                """
() => {
  const shell = document.querySelector('.device-page.active .synthetic-list-scroll[data-synthetic-list-kind="source"]');
  if (!shell) return { ok: false, reason: 'missing active source shell' };
  if (typeof setSelectedRoom !== 'function') return { ok: false, reason: 'setSelectedRoom unavailable' };
  setSelectedRoom(2, { persist: false });
  const minVisibleTop = () => {
    const rows = [...shell.querySelectorAll('.btn-wrap[data-synthetic-source-list]')];
    const visible = rows.filter(r => r.style.display !== 'none');
    if (!visible.length) return { minTop: 9999, roomIds: [] };
    return {
      minTop: Math.min(...visible.map(r => r.offsetTop)),
      roomIds: [...new Set(visible.map(r => Number(r.dataset.syntheticSourceRoomId || 0)))],
    };
  };
  const before = minVisibleTop();
  const land = document.querySelector('.orientation-btn[data-orientation="landscape"]');
  const port = document.querySelector('.orientation-btn[data-orientation="portrait"]');
  if (!land || !port) return { ok: false, reason: 'missing orientation controls', before };
  land.click();
  port.click();
  const after = minVisibleTop();
  if (before.minTop > 4) return { ok: false, reason: 'precondition failed before orientation', before, after };
  if (after.minTop > 4) return { ok: false, reason: 'compaction lost after orientation toggle', before, after };
  if (!(after.roomIds.length === 1 && after.roomIds[0] === 2)) {
    return { ok: false, reason: 'wrong visible room after orientation toggle', before, after };
  }
  return { ok: true, before, after };
}
"""
            )
            self.assertTrue(result.get("ok"), msg=str(result))
        finally:
            page.close()
            server.stop()

    def test_source_list_first_paint_has_no_compaction_flash(self):
        device = {
            "userFacing": {
                "displayName": "SourceScroll",
                "deviceUI": _device_ui_standard(),
                "pages": [_global_source_list_overflow_page()],
            },
            "diagnostics": _two_room_checked_sources_diag(),
        }
        project = {"devices": [device]}
        page, server, _tmp = self._open_page(project)
        try:
            result = page.evaluate(
                """
async () => {
  const shell = document.querySelector('.device-page.active .synthetic-list-scroll[data-synthetic-list-kind="source"]');
  if (!shell) return { ok: false, reason: 'missing active source shell' };
  const samples = [];
  for (let i = 0; i < 36; i += 1) {
    const rows = [...shell.querySelectorAll('.btn-wrap[data-synthetic-source-list]')];
    const visible = rows.filter(r => r.style.display !== 'none');
    if (visible.length) {
      const minTop = Math.min(...visible.map(r => r.offsetTop));
      samples.push(minTop);
    }
    await new Promise(resolve => requestAnimationFrame(() => resolve()));
  }
  if (!samples.length) return { ok: false, reason: 'no visible samples captured' };
  const maxMinTop = Math.max(...samples);
  if (maxMinTop > 4) return { ok: false, reason: 'first-paint compaction flash detected', maxMinTop, samples };
  return { ok: true, maxMinTop, samples };
}
"""
            )
            self.assertTrue(result.get("ok"), msg=str(result))
        finally:
            page.close()
            server.stop()


if __name__ == "__main__":
    unittest.main()
