import unittest
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class _CaptureServer:
    def __init__(self, *, html_by_path: dict[str, str], post_mode: str = "ok") -> None:
        self._html_by_path = html_by_path
        self._post_mode = post_mode  # "ok" | "error"
        self.posts: list[dict] = []
        self._last_by_target_key: dict[str, dict[str, object]] = {}
        self._fixed_last_tested_at_utc = "2026-03-21T00:00:00Z"
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args, **_kwargs):  # noqa: ANN001
                return

            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path.startswith("/api/v1/testing/") and parsed.path.endswith("/target-status"):
                    qs = parse_qs(parsed.query or "")
                    target_key = (qs.get("targetKey") or [""])[0]
                    rec = outer._last_by_target_key.get(str(target_key or ""))
                    outcome = str(rec.get("outcome")) if rec else "UNTESTED"
                    note = rec.get("failNote") if rec else None
                    last_at = outer._fixed_last_tested_at_utc if rec else None
                    payload = {"targetKey": target_key, "currentOutcome": outcome, "lastTestedAtUtc": last_at, "lastFailNote": note}
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(payload).encode("utf-8"))
                    return

                html = outer._html_by_path.get(parsed.path)
                if html is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("content-length") or 0)
                body = self.rfile.read(length) if length else b""
                payload = json.loads(body.decode("utf-8") or "{}")
                outer.posts.append({"path": self.path, "payload": payload})
                try:
                    target = payload.get("target") or {}
                    target_key = str(target.get("targetKey") or "")
                    if target_key:
                        outer._last_by_target_key[target_key] = {
                            "outcome": str(payload.get("outcome") or ""),
                            "failNote": payload.get("failNote"),
                        }
                except Exception:
                    pass
                if outer._post_mode == "error":
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"error": {"code": "UNITTEST_ERROR", "message": "Unit test forced failure", "details": {}}}).encode("utf-8")
                    )
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return int(self._server.server_address[1])

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None


class TestingResultPostingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:  # pragma: no cover
            raise unittest.SkipTest("playwright is not installed") from e

        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()

    def _wait_for_posts(self, server: _CaptureServer, *, min_posts: int = 1, timeout_s: float = 3.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if len(server.posts) >= min_posts:
                return
            time.sleep(0.05)
        self.fail(f"Expected at least {min_posts} POST(s), got {len(server.posts)}")

    def _wait_for_status_contains(self, page, text: str, *, timeout_s: float = 3.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                status = page.locator("#postStatus").inner_text()
            except Exception:
                status = ""
            if text in (status or ""):
                return
            time.sleep(0.05)
        self.fail(f"Expected #postStatus to contain {text!r}")

    def _wait_for_row_status_contains(self, page, row_index: int, text: str, *, timeout_s: float = 3.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                status = page.locator("#rows .row").nth(row_index).locator(".row-status").inner_text()
            except Exception:
                status = ""
            if text in (status or ""):
                return
            time.sleep(0.05)
        self.fail(f"Expected row {row_index} .row-status to contain {text!r}")

    def test_event_pass_posts_result(self):
        from sentinel.generation.render_core import render_project_home_html, load_json

        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        project_data = {
            "source": {"file": "UnitTest.apex"},
            "events": {
                "system": [
                    {
                        "diagnostics": {"eventId": 126},
                        "userFacing": {"description": "Test Event", "testTargets": {"Trigger": True}},
                    }
                ],
                "driver": [],
            },
            "devices": [],
        }
        html = render_project_home_html(project_data, app_ui, "unittest")

        token = "techToken123"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click("button.section-toggle[data-target='system-events']")
            page.click(".event-row.test-btn")
            page.click("#rows .row .actions button")  # first "Pass"
            self._wait_for_posts(server, min_posts=1)
            self._wait_for_status_contains(page, "Saved")
            self._wait_for_row_status_contains(page, 0, "PASS")
            self._wait_for_row_status_contains(page, 0, "2026-03-21T00:00:00Z")
            posted = server.posts[0]["payload"]
            self.assertEqual(posted["outcome"], "PASS")
            self.assertEqual(posted["target"]["kind"], "EVENT")
            self.assertEqual(posted["target"]["targetKey"], "event:126:Trigger")
        finally:
            server.stop()

    def test_button_pass_posts_result(self):
        from sentinel.generation.render_core import render_single_device_html, load_json

        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        project_data = {
            "source": {"file": "UnitTest.apex"},
            "devices": [
                {
                    "userFacing": {
                        "displayName": "Device A",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": False, "resolution": {"width": 0, "height": 0}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Layer 1",
                                        "layerOrder": 0,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "hardButtons": [],
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "BTN-1", "text": "Button 1", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {"portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}}},
                                                    },
                                                    "testTargets": {"text": False, "macros": True, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "resolvedPageLink": {"targetPageId": None},
                                                }
                                            ],
                                        },
                                        "viewports": [],
                                    }
                                ],
                            }
                        ],
                    },
                    "diagnostics": {
                        "deviceId": 81,
                        "pages": [
                            {
                                "pageId": 513,
                                "pageName": "Home",
                                "uiItems": [{"buttonId": 48551}],
                                "buttons": [{"buttonId": 48551, "buttonTagName": "BTN-1", "identifiers": {"text": "Button 1"}, "testTargets": {}}],
                                "viewports": [],
                            }
                        ],
                    },
                }
            ],
        }

        html = render_single_device_html(project_data, app_ui, "unittest", device_index=0)

        token = "techToken456"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")
            page.click("#rows .row .actions button")  # first "Pass"
            self._wait_for_posts(server, min_posts=1)
            self._wait_for_status_contains(page, "Saved")
            self._wait_for_row_status_contains(page, 0, "PASS")
            self._wait_for_row_status_contains(page, 0, "2026-03-21T00:00:00Z")
            posted = server.posts[0]["payload"]
            self.assertEqual(posted["outcome"], "PASS")
            self.assertEqual(posted["target"]["kind"], "BUTTON")
            self.assertEqual(posted["target"]["targetKey"], "btn:81:513:48551:Macro")
        finally:
            server.stop()

    def test_button_fail_requires_note_enables_button(self):
        from sentinel.generation.render_core import render_single_device_html, load_json

        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        project_data = {
            "source": {"file": "UnitTest.apex"},
            "devices": [
                {
                    "userFacing": {
                        "displayName": "Device A",
                        "deviceUI": {
                            "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                            "landscape": {"supported": False, "resolution": {"width": 0, "height": 0}},
                        },
                        "pages": [
                            {
                                "pageName": "Home",
                                "layers": [
                                    {
                                        "layerName": "Layer 1",
                                        "layerOrder": 0,
                                        "buttonCategories": {
                                            "screenLabels": [],
                                            "hardButtons": [],
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "BTN-1", "text": "Button 1", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {"portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}}},
                                                    },
                                                    "testTargets": {"text": False, "macros": True, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "resolvedPageLink": {"targetPageId": None},
                                                }
                                            ],
                                        },
                                        "viewports": [],
                                    }
                                ],
                            }
                        ],
                    },
                    "diagnostics": {
                        "deviceId": 81,
                        "pages": [
                            {
                                "pageId": 513,
                                "pageName": "Home",
                                "uiItems": [{"buttonId": 48551}],
                                "buttons": [{"buttonId": 48551, "buttonTagName": "BTN-1", "identifiers": {"text": "Button 1"}, "testTargets": {}}],
                                "viewports": [],
                            }
                        ],
                    },
                }
            ],
        }

        html = render_single_device_html(project_data, app_ui, "unittest", device_index=0)

        token = "techTokenFail"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")

            fail_btn = page.locator("#rows .row .actions button").nth(1)
            self.assertTrue(fail_btn.is_disabled())

            page.fill("#rows .row textarea", "Broken macro")
            self.assertFalse(fail_btn.is_disabled())

            fail_btn.click()
            self._wait_for_posts(server, min_posts=1)
            self._wait_for_status_contains(page, "Saved")
            self._wait_for_row_status_contains(page, 0, "FAIL")
            self._wait_for_row_status_contains(page, 0, "2026-03-21T00:00:00Z")
            posted = server.posts[0]["payload"]
            self.assertEqual(posted["outcome"], "FAIL")
            self.assertEqual(posted["failNote"], "Broken macro")
        finally:
            server.stop()

    def test_event_post_failure_shows_error(self):
        from sentinel.generation.render_core import render_project_home_html, load_json

        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        project_data = {
            "source": {"file": "UnitTest.apex"},
            "events": {
                "system": [
                    {
                        "diagnostics": {"eventId": 126},
                        "userFacing": {"description": "Test Event", "testTargets": {"Trigger": True}},
                    }
                ],
                "driver": [],
            },
            "devices": [],
        }
        html = render_project_home_html(project_data, app_ui, "unittest")

        token = "techToken789"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html}, post_mode="error")
        port = server.start()
        try:
            page = self._browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click("button.section-toggle[data-target='system-events']")
            page.click(".event-row.test-btn")
            page.click("#rows .row .actions button")  # first "Pass"
            self._wait_for_posts(server, min_posts=1)
            self._wait_for_status_contains(page, "UNITTEST_ERROR")
        finally:
            server.stop()
