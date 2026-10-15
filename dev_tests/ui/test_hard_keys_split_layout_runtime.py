"""Playwright runtime UI test: T4x hard-key split layout renders both zones side-by-side."""
import shutil
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


def _isr2_project_data() -> dict:
    """Minimal synthetic project_data that triggers ISR-2 split-layout rendering."""
    hk_buttons = [
        _make_hard_key_button(1, "Power"),
        _make_hard_key_button(2, "Mute"),
        _make_hard_key_button(3, "Menu"),
    ]
    hk_slots = [
        {"buttonId": 1, "slotKey": 128},
        {"buttonId": 2, "slotKey": 129},
        {"buttonId": 3, "slotKey": 131},
    ]
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "ISR-2 Test Device",
                    "productModel": "isr2",
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

    def _render_and_serve(self, project_data: dict | None = None):
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
        project_data = project_data or _t4x_project_data()
        html = render_single_device_html(
            project_data,
            app_ui,
            project_stem="hk_split_layout_test",
            device_index=0,
        )
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-hk-split-"))
        html_path = tmp_dir / "hk_split_test.html"
        html_path.write_text(html, encoding="utf-8")

        server = self._StaticServer(tmp_dir)
        server.start()
        page = self._browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})
        page.goto(f"{server.base_url}/{html_path.name}", wait_until="domcontentloaded")
        page.wait_for_selector("#rtiDeviceCanvas", state="attached", timeout=5000)
        page.wait_for_selector(".device-page.active", state="attached", timeout=5000)
        page.wait_for_timeout(600)
        return page, server, tmp_dir

    def test_hk_split_zones_exist_and_are_visible(self):
        page, server, tmp_dir = self._render_and_serve()
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
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_hk_split_right_frame_vars_are_set(self):
        page, server, tmp_dir = self._render_and_serve()
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
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_hk_btn_wrap_elements_are_non_zero(self):
        page, server, tmp_dir = self._render_and_serve()
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
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_canvas_has_data_hk_model_t4x(self):
        page, server, tmp_dir = self._render_and_serve()
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
            self.assertEqual(result["hkDesignW"], "551", msg=f"data-hk-design-w should be '551', got {result['hkDesignW']!r}")
            self.assertEqual(result["hkDesignH"], "679", msg=f"data-hk-design-h should be '679', got {result['hkDesignH']!r}")
        finally:
            page.close()
            server.stop()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_traced_frame_is_filled_grey(self):
        page, server, tmp_dir = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const activePage = document.querySelector('.device-page.active');
  if (!activePage) return {error: 'no active page'};
  const frame = activePage.querySelector('.hk-traced-frame');
  if (!frame) return {error: 'no .hk-traced-frame'};
  const cs = getComputedStyle(frame);
  return {
    background: cs.backgroundColor,
    borderTopWidth: cs.borderTopWidth,
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertEqual(result["background"], "rgb(54, 55, 57)")
            self.assertEqual(result["borderTopWidth"], "3px")
        finally:
            page.close()
            server.stop()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_hard_key_buttons_use_testing_chrome(self):
        page, server, tmp_dir = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const activePage = document.querySelector('.device-page.active');
  if (!activePage) return {error: 'no active page'};
  const btn = activePage.querySelector('.hk-split-right .hk-traced:not(.hk-traced-hit) .test-btn');
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
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_hk_outer_canvas_has_no_ring_touch_and_hard_key_columns_have_rings(self):
        """Hard-key mode: no outer #rtiDeviceCanvas ring; touch column ring; traced frame carries the strip ring."""
        page, server, tmp_dir = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const canvas = document.getElementById('rtiDeviceCanvas');
  if (!canvas) return {error: 'no #rtiDeviceCanvas'};
  const touch = document.querySelector('.hk-touch-stack');
  if (!touch) return {error: 'no .hk-touch-stack'};
  const right = document.querySelector('.hk-split-right');
  if (!right) return {error: 'no .hk-split-right'};
  const frame = right.querySelector('.hk-traced-frame');
  if (!frame) return {error: 'no .hk-traced-frame'};
  const c = getComputedStyle(canvas);
  const t = getComputedStyle(touch);
  const r = getComputedStyle(right);
  const frameCs = getComputedStyle(frame);
  return {
    canvasBorderW: c.borderTopWidth,
    canvasShadow: c.boxShadow,
    touchBorderW: t.borderTopWidth,
    touchShadow: t.boxShadow,
    rightShadow: r.boxShadow,
    frameBorderW: frameCs.borderTopWidth,
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertEqual(result["canvasBorderW"], "0px")
            self.assertEqual(result["canvasShadow"], "none")
            self.assertEqual(result["touchBorderW"], "0px")
            self.assertNotEqual(result["touchShadow"], "none")
            self.assertEqual(result["rightShadow"], "none")
            self.assertEqual(result["frameBorderW"], "3px")
        finally:
            page.close()
            server.stop()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_traced_frame_wraps_the_stage(self):
        page, server, tmp_dir = self._render_and_serve()
        try:
            result = page.evaluate(
                """
() => {
  const frame = document.querySelector('.hk-traced-frame');
  const stage = document.querySelector('.hk-traced-stage');
  if (!frame || !stage) return {error: 'missing traced strip'};
  const fr = frame.getBoundingClientRect();
  const st = stage.getBoundingClientRect();
  const tol = 2.5;
  return {
    frameW: fr.width,
    frameH: fr.height,
    stageW: st.width,
    stageH: st.height,
    errW: Math.abs(fr.width - st.width),
    errH: Math.abs(fr.height - st.height),
    tol,
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertGreater(result["frameW"], 0)
            self.assertGreater(result["frameH"], 0)
            # Content-box frame: the 3px ring sits outside the stage on each edge.
            self.assertAlmostEqual(result["frameW"] - result["stageW"], 6, delta=result["tol"])
            self.assertAlmostEqual(result["frameH"] - result["stageH"], 6, delta=result["tol"])
        finally:
            page.close()
            server.stop()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_hk_columns_center_on_quarter_lines_of_rti_canvas(self):
        page, server, tmp_dir = self._render_and_serve(project_data=_isr2_project_data())
        try:
            result = page.evaluate(
                """
() => {
  const rti = document.getElementById('rtiCanvas');
  const activePage = document.querySelector('.device-page.active');
  const left = activePage?.querySelector('.hk-split-left');
  const right = activePage?.querySelector('.hk-split-right');
  if (!rti || !left || !right) return {error: 'missing nodes'};
  const w = rti.clientWidth;
  const lr = left.getBoundingClientRect();
  const rr = right.getBoundingClientRect();
  const rt = rti.getBoundingClientRect();
  const touchCx = (lr.left - rt.left) + lr.width / 2;
  const hkCx = (rr.left - rt.left) + rr.width / 2;
  return {
    usableW: w,
    touchCenterX: touchCx,
    hkCenterX: hkCx,
    targetTouch: 0.25 * w,
    targetHk: 0.75 * w,
    touchErr: Math.abs(touchCx - 0.25 * w),
    hkErr: Math.abs(hkCx - 0.75 * w),
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertLessEqual(result["touchErr"], 2.5, msg=result)
            self.assertLessEqual(result["hkErr"], 2.5, msg=result)
        finally:
            page.close()
            server.stop()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_isr2_hard_key_layout_fits_inside_rti_canvas(self):
        page, server, tmp_dir = self._render_and_serve(project_data=_isr2_project_data())
        try:
            result = page.evaluate(
                """
() => {
  const rti = document.getElementById('rtiCanvas');
  const device = document.getElementById('rtiDeviceCanvas');
  const activePage = document.querySelector('.device-page.active');
  if (!rti || !device || !activePage) return {error: 'missing layout roots'};
  const margin = 20;
  const ur = rti.getBoundingClientRect();
  const innerTop = ur.top + margin;
  const innerBottom = ur.bottom - margin;
  const innerLeft = ur.left + margin;
  const innerRight = ur.right - margin;
  const samples = [];
  let overflowCount = 0;
  const nodes = [
    activePage.querySelector('.hk-touch-stack'),
    activePage.querySelector('.hk-traced-stage'),
  ].filter(Boolean);
  nodes.forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return;
    const over =
      r.top < innerTop - 2 ||
      r.left < innerLeft - 2 ||
      r.bottom > innerBottom + 2 ||
      r.right > innerRight + 2;
    if (over) {
      overflowCount += 1;
      if (samples.length < 6) {
        samples.push({
          cls: el.className,
          top: r.top,
          bottom: r.bottom,
          innerTop,
          innerBottom,
        });
      }
    }
  });
  return {
    hkModel: device.getAttribute('data-hk-model'),
    deviceH: device.getBoundingClientRect().height,
    touchH: activePage.querySelector('.hk-touch-stack')?.getBoundingClientRect().height || 0,
    overflowCount,
    samples,
  };
}
"""
            )
            self.assertNotIn("error", result, msg=result.get("error", ""))
            self.assertEqual(result["hkModel"], "isr2")
            self.assertGreaterEqual(result["deviceH"], result["touchH"])
            self.assertEqual(
                result["overflowCount"],
                0,
                msg=f"ISR-2 layout overflow inside rtiCanvas margin: {result['samples']}",
            )
        finally:
            page.close()
            server.stop()
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
