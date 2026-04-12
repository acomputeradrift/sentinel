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

from sentinel.generation.render_core import render_single_device_html


def _oriented_ui(*, top: int, left: int, height: int, width: int, font_size: int = 14) -> dict:
    return {
        "fontSize": font_size,
        "orientations": {
            "portrait": {"visible": True, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
            "landscape": {"visible": True, "coordinates": {"top": top, "left": left, "height": height, "width": width}},
        },
    }


class ProjectDeviceStaticLayoutRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest("playwright is not installed") from exc
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

    def _write_fixture_html(self) -> tuple[Path, Path]:
        project_data = {
            "devices": [
                {
                    "userFacing": {
                        "displayName": "Runtime Static Device",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": True, "resolution": {"width": 854, "height": 480}},
                        },
                        "pages": [
                            {
                                "pageName": "Page 1",
                                "layers": [
                                    {
                                        "layerName": "Layer 1",
                                        "layerOrder": 0,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "hardButtons": [],
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "Button A", "text": "Button A", "buttonType": None},
                                                    "buttonUI": _oriented_ui(top=120, left=90, height=60, width=220),
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
                                                }
                                            ],
                                        },
                                        "viewports": [],
                                    }
                                ],
                                "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []},
                                "viewports": [],
                            },
                            {
                                "pageName": "Page 2",
                                "layers": [
                                    {
                                        "layerName": "Layer 2",
                                        "layerOrder": 0,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "hardButtons": [],
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "Button B", "text": "Button B", "buttonType": None},
                                                    "buttonUI": _oriented_ui(top=220, left=110, height=60, width=220),
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
                                                }
                                            ],
                                        },
                                        "viewports": [],
                                    }
                                ],
                                "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []},
                                "viewports": [],
                            },
                        ],
                    },
                    "diagnostics": {"deviceId": 1, "pages": [{"pageId": 1, "pageName": "Page 1"}, {"pageId": 2, "pageName": "Page 2"}]},
                }
            ]
        }
        app_ui = {
            "layout": {
                "appCanvas": {"mode": "browser-viewport"},
                "appUIControls": {"top": 52, "bottom": 32, "left": 240, "right": 240},
                "rtiCanvas": {"deriveFromAppCanvas": True},
                "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.25},
            },
            "header": {"enabled": True, "titleTemplate": "{deviceName} - {pageName}", "placement": "top"},
            "appNavigation": {"enabled": True, "pageLinks": {"enabled": True}},
            "zoomControls": {"enabled": True},
            "viewportNavigation": {"enabled": True},
            "testingPopup": {"enabled": True},
            "buttonPresentation": {"fallbackFontSize": 12, "scaleRtiDerivedFontSizes": True},
            "state": {},
            "layerPanel": {"enabled": True},
        }

        source_html = render_single_device_html(project_data, app_ui, project_stem="runtime_test_project", device_index=0)
        tmp_dir = Path(tempfile.mkdtemp(prefix="sentinel-static-layout-"))
        source_path = tmp_dir / "source_runtime.html"
        source_path.write_text(source_html, encoding="utf-8")

        shell_template = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "project_device_static_layout.html"
        shell_css = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "project_device_static_layout.css"
        shell_path = tmp_dir / "shell_runtime.html"
        css_path = tmp_dir / "project_device_static_layout.css"

        css_path.write_text(shell_css.read_text(encoding="utf-8"), encoding="utf-8")
        shell_doc = shell_template.read_text(encoding="utf-8")
        shell_doc = shell_doc.replace(
            "</head>",
            '<meta name="sentinel-shell-source" content="/source_runtime.html"></head>',
            1,
        )
        shell_path.write_text(shell_doc, encoding="utf-8")
        return shell_path, tmp_dir

    def _open_shell_page(self):
        shell_path, root_dir = self._write_fixture_html()
        server = self._StaticServer(root_dir)
        server.start()
        page = self._browser.new_page()
        page.goto(f"{server.base_url}/{shell_path.name}", wait_until="domcontentloaded")
        page.wait_for_selector("#rtiDeviceContent .device-page.active .test-btn")
        return page, server

    def test_temporary_background_colors_removed_from_shell_regions(self):
        page, server = self._open_shell_page()
        try:
            colors = page.evaluate(
                """
() => {
  const ids = ['deviceHeaderCanvas','deviceFooterCanvas','deviceViewControlsCanvas','deviceLayerControlsCanvas','rtiUsableCanvas'];
  const out = {};
  ids.forEach((id) => {
    const el = document.getElementById(id);
    out[id] = getComputedStyle(el).backgroundColor;
  });
  return out;
}
"""
            )
            for key, value in colors.items():
                if value != "rgba(0, 0, 0, 0)":
                    raise AssertionError(f"Expected transparent background for {key}, got {value}")
        finally:
            page.close()
            server.stop()

    def test_text_zoom_changes_active_page_text_without_device_resize(self):
        page, server = self._open_shell_page()
        try:
            before = page.evaluate(
                """
() => {
  const active = document.querySelector('#rtiDeviceContent .device-page.active .test-btn');
  const canvas = document.getElementById('rtiDeviceCanvas');
  return {
    font: parseFloat(getComputedStyle(active).fontSize || '0'),
    width: canvas.getBoundingClientRect().width,
    height: canvas.getBoundingClientRect().height
  };
}
"""
            )
            page.click('[data-control="text-zoom-inc"][data-variant="full"]')
            page.wait_for_timeout(120)
            after = page.evaluate(
                """
() => {
  const active = document.querySelector('#rtiDeviceContent .device-page.active .test-btn');
  const canvas = document.getElementById('rtiDeviceCanvas');
  return {
    font: parseFloat(getComputedStyle(active).fontSize || '0'),
    width: canvas.getBoundingClientRect().width,
    height: canvas.getBoundingClientRect().height
  };
}
"""
            )
            self.assertGreater(after["font"], before["font"])
            self.assertAlmostEqual(after["width"], before["width"], delta=0.5)
            self.assertAlmostEqual(after["height"], before["height"], delta=0.5)
        finally:
            page.close()
            server.stop()

    def test_minimized_device_controls_use_same_behavior_as_full_controls(self):
        page, server = self._open_shell_page()
        try:
            before_full = page.locator('[data-control="device-zoom-reset"][data-variant="full"]').inner_text().strip()
            page.click(".deviceControlsToggleLeft")
            page.click('[data-control="device-zoom-inc"][data-variant="mini"]')
            page.wait_for_timeout(120)
            after_full = page.locator('[data-control="device-zoom-reset"][data-variant="full"]').inner_text().strip()
            after_mini = page.locator('[data-control="device-zoom-reset"][data-variant="mini"]').inner_text().strip()
            self.assertNotEqual(before_full, after_full)
            self.assertEqual(after_full, after_mini)
        finally:
            page.close()
            server.stop()

    def test_orientation_active_state_is_synced_for_full_and_minimized_controls(self):
        page, server = self._open_shell_page()
        try:
            page.click(".deviceControlsToggleLeft")
            page.click('[data-control="orientation-portrait"][data-variant="mini"]')
            page.wait_for_timeout(120)
            state = page.evaluate(
                """
() => {
  const pick = (sel) => document.querySelector(sel)?.classList.contains('active') || false;
  return {
    fullPortrait: pick('[data-control="orientation-portrait"][data-variant="full"]'),
    fullLandscape: pick('[data-control="orientation-landscape"][data-variant="full"]'),
    miniPortrait: pick('[data-control="orientation-portrait"][data-variant="mini"]'),
    miniLandscape: pick('[data-control="orientation-landscape"][data-variant="mini"]'),
  };
}
"""
            )
            self.assertTrue(state["fullPortrait"])
            self.assertTrue(state["miniPortrait"])
            self.assertFalse(state["fullLandscape"])
            self.assertFalse(state["miniLandscape"])
        finally:
            page.close()
            server.stop()


if __name__ == "__main__":
    unittest.main()
