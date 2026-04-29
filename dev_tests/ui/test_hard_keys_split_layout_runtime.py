"""Playwright runtime UI test: T4x hard-key split layout renders both zones side-by-side."""
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

from sentinel.generation.render_core import clear_hard_key_template_cache, render_single_device_html


def _make_hard_key_button(button_id: int, tag: str) -> dict:
    return {
        "buttonIdentity": {"buttonTagName": tag, "text": tag, "buttonType": None},
        "apexScopeSource": {"button": {"buttonId": button_id}},
        "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
    }


def _t4x_project_data() -> dict:
    """Minimal synthetic project_data that triggers T4x split-layout rendering."""
    hk_buttons = [
        _make_hard_key_button(1, "Power"),
        _make_hard_key_button(2, "Mute"),
        _make_hard_key_button(3, "Menu"),
    ]
    hk_slots = [
        {"buttonId": 1, "slotKey": 128},
        {"buttonId": 2, "slotKey": 129},
        {"buttonId": 3, "slotKey": 130},
    ]
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "T4x Test Device",
                    "productModel": "t4x",
                    "deviceUI": {
                        "portrait": {
                            "supported": True,
                            "resolution": {"width": 480, "height": 854},
                        },
                        "landscape": {
                            "supported": False,
                            "resolution": {"width": 854, "height": 480},
                        },
                    },
                    "pages": [
                        {
                            "pageName": "Page 1",
                            "layers": [
                                {
                                    "layerName": "Screen Layer",
                                    "layerOrder": 0,
                                    "isKeypadLayer": False,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "hardButtons": [],
                                        "screenButtons": [],
                                    },
                                    "viewports": [],
                                },
                                {
                                    "layerName": "Hard Key Layer",
                                    "layerOrder": 1,
                                    "isKeypadLayer": True,
                                    "hardKeyLayer": {"slots": hk_slots},
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "hardButtons": hk_buttons,
                                        "screenButtons": [],
                                    },
                                    "viewports": [],
                                },
                            ],
                            "buttonCategories": {
                                "screenLabels": [],
                                "hardButtons": [],
                                "screenButtons": [],
                            },
                            "viewports": [],
                        }
                    ],
                },
                "diagnostics": {
                    "deviceId": 1,
                    "pages": [{"pageId": 1, "pageName": "Page 1"}],
                },
            }
        ]
    }


class HardKeysSplitLayoutRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        clear_hard_key_template_cache()
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
                self._thread.join(timeout=1)

    def _render_and_serve(self):
        app_ui = {
            "layout": {
                "appCanvas": {"mode": "browser-viewport"},
                "appUIControls": {"top": 52, "bottom": 32, "left": 0, "right": 0},
                "rtiCanvas": {"deriveFromAppCanvas": True},
                "rtiDeviceCanvas": {
                    "fitMode": "contain",
                    "allowScaleAboveOne": True,
                    "maxScale": 10,
                    "minScale": 0.1,
                },
            },
            "header": {"enabled": False, "titleTemplate": "{deviceName}"},
            "appNavigation": {"enabled": False, "pageLinks": {"enabled": False}},
            "zoomControls": {"enabled": False},
            "viewportNavigation": {"enabled": False},
            "testingPopup": {"enabled": False},
            "buttonPresentation": {"fallbackFontSize": 12, "scaleRtiDerivedFontSizes": True},
            "state": {},
            "layerPanel": {"enabled": False},
        }
        project_data = _t4x_project_data()
        html = render_single_device_html(
            project_data,
            app_ui,
            project_stem="hk_split_layout_test",
            device_index=0,
        )
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-hk-split-"))
        html_path = tmp_dir / "t4x_test.html"
        html_path.write_text(html, encoding="utf-8")

        server = self._StaticServer(tmp_dir)
        server.start()
        page = self._browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(f"{server.base_url}/{html_path.name}", wait_until="domcontentloaded")
        page.wait_for_selector("#rtiDeviceCanvas", state="attached", timeout=5000)
        page.wait_for_selector(".device-page.active", state="attached", timeout=5000)
        page.wait_for_timeout(600)
        return page, server

    def test_hk_split_zones_exist_and_are_visible(self):
        page, server = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const activePage = document.querySelector('.device-page.active');
  if (!activePage) return {error: 'no active page'};
  const left = activePage.querySelector('.hk-split-left');
  const right = activePage.querySelector('.hk-split-right');
  if (!left) return {error: 'no .hk-split-left'};
  if (!right) return {error: 'no .hk-split-right'};
  const lr = left.getBoundingClientRect();
  const rr = right.getBoundingClientRect();
  return {
    leftExists: true,
    rightExists: true,
    leftW: lr.width,
    leftH: lr.height,
    rightW: rr.width,
    rightH: rr.height,
    leftRight: lr.right,
    rightLeft: rr.left,
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertTrue(result["leftExists"])
            self.assertTrue(result["rightExists"])
            self.assertGreater(result["leftW"], 0, "hk-split-left has zero width")
            self.assertGreater(result["leftH"], 0, "hk-split-left has zero height")
            self.assertGreater(result["rightW"], 0, "hk-split-right has zero width")
            self.assertGreater(result["rightH"], 0, "hk-split-right has zero height")
            self.assertLessEqual(
                result["leftRight"],
                result["rightLeft"] + 5,
                msg=f"left zone right edge ({result['leftRight']}) should be <= right zone left edge ({result['rightLeft']}) + 5px gap tolerance",
            )
        finally:
            page.close()
            server.stop()

    def test_hk_split_right_frame_vars_are_set(self):
        page, server = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const activePage = document.querySelector('.device-page.active');
  if (!activePage) return {error: 'no active page'};
  const right = activePage.querySelector('.hk-split-right');
  if (!right) return {error: 'no .hk-split-right'};
  const cs = getComputedStyle(right);
  const frameW = cs.getPropertyValue('--frame-w').trim();
  const frameH = cs.getPropertyValue('--frame-h').trim();
  return {frameW, frameH};
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            frame_w = result["frameW"]
            frame_h = result["frameH"]
            self.assertTrue(
                frame_w.endswith("px"),
                msg=f"--frame-w should end in 'px', got: {frame_w!r}",
            )
            self.assertTrue(
                frame_h.endswith("px"),
                msg=f"--frame-h should end in 'px', got: {frame_h!r}",
            )
            self.assertGreater(
                float(frame_w.replace("px", "")),
                0,
                msg=f"--frame-w should be > 0, got: {frame_w!r}",
            )
            self.assertGreater(
                float(frame_h.replace("px", "")),
                0,
                msg=f"--frame-h should be > 0, got: {frame_h!r}",
            )
        finally:
            page.close()
            server.stop()

    def test_hk_btn_wrap_elements_are_non_zero(self):
        page, server = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const activePage = document.querySelector('.device-page.active');
  if (!activePage) return {error: 'no active page'};
  const right = activePage.querySelector('.hk-split-right');
  if (!right) return {error: 'no .hk-split-right'};
  const wraps = Array.from(right.querySelectorAll('.hk-btn-wrap'));
  if (wraps.length === 0) return {error: 'no .hk-btn-wrap elements in .hk-split-right'};
  const collapsed = wraps.filter(el => {
    const r = el.getBoundingClientRect();
    return r.width <= 0 || r.height <= 0;
  });
  return {
    total: wraps.length,
    collapsed: collapsed.length,
    collapsedClasses: collapsed.map(el => el.className),
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertGreater(result["total"], 0, ".hk-btn-wrap count should be > 0")
            self.assertEqual(
                result["collapsed"],
                0,
                msg=f"{result['collapsed']} of {result['total']} .hk-btn-wrap elements are 0x0: {result['collapsedClasses']}",
            )
        finally:
            page.close()
            server.stop()

    def test_canvas_has_data_hk_model_t4x(self):
        page, server = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const canvas = document.getElementById('rtiDeviceCanvas');
  if (!canvas) return {error: 'no #rtiDeviceCanvas'};
  return {
    hkModel: canvas.getAttribute('data-hk-model'),
    hkDesignW: canvas.getAttribute('data-hk-design-w'),
    hkDesignH: canvas.getAttribute('data-hk-design-h'),
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertEqual(result["hkModel"], "t4x", msg=f"data-hk-model should be 't4x', got {result['hkModel']!r}")
            self.assertEqual(result["hkDesignW"], "608", msg=f"data-hk-design-w should be '608', got {result['hkDesignW']!r}")
            self.assertEqual(result["hkDesignH"], "732", msg=f"data-hk-design-h should be '732', got {result['hkDesignH']!r}")
        finally:
            page.close()
            server.stop()

    def test_hard_key_template_boxes_are_not_stroked(self):
        page, server = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const activePage = document.querySelector('.device-page.active');
  if (!activePage) return {error: 'no active page'};
  const right = activePage.querySelector('.hk-split-right');
  if (!right) return {error: 'no .hk-split-right'};
  const box = right.querySelector('.box');
  if (!box) return {error: 'no template .box'};
  const cs = getComputedStyle(box);
  return {
    borderTopWidth: cs.borderTopWidth,
    borderTopStyle: cs.borderTopStyle,
    borderTopColor: cs.borderTopColor,
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertEqual(result["borderTopWidth"], "0px")
            self.assertEqual(result["borderTopStyle"], "none")
        finally:
            page.close()
            server.stop()

    def test_hard_key_buttons_use_testing_chrome(self):
        page, server = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const activePage = document.querySelector('.device-page.active');
  if (!activePage) return {error: 'no active page'};
  const btn = activePage.querySelector('.hk-split-right .hk-btn-wrap .test-btn');
  if (!btn) return {error: 'no hard-key .test-btn'};
  const cs = getComputedStyle(btn);
  return {
    bg: cs.backgroundColor,
    hasInsetShadow: cs.boxShadow !== 'none',
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertNotEqual(result["bg"], "rgba(0, 0, 0, 0)")
            self.assertTrue(result["hasInsetShadow"], msg="expected inset trim/border shadow on hard-key testing buttons")
        finally:
            page.close()
            server.stop()

    def test_device_and_touch_rings_use_box_shadow_not_gray_border(self):
        page, server = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const canvas = document.getElementById('rtiDeviceCanvas');
  if (!canvas) return {error: 'no #rtiDeviceCanvas'};
  const touch = document.querySelector('.hk-touch-stack');
  if (!touch) return {error: 'no .hk-touch-stack'};
  const c = getComputedStyle(canvas);
  const t = getComputedStyle(touch);
  return {
    canvasBorderW: c.borderTopWidth,
    canvasShadow: c.boxShadow,
    touchBorderW: t.borderTopWidth,
    touchShadow: t.boxShadow,
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertEqual(result["canvasBorderW"], "0px")
            self.assertNotEqual(result["canvasShadow"], "none")
            self.assertEqual(result["touchBorderW"], "0px")
            self.assertNotEqual(result["touchShadow"], "none")
        finally:
            page.close()
            server.stop()


if __name__ == "__main__":
    unittest.main()
