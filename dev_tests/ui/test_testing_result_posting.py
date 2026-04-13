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

    def _wait_for_status_hidden(self, page, *, timeout_s: float = 3.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                hidden = bool(page.locator("#postStatus").evaluate("el => el.hasAttribute('hidden')"))
            except Exception:
                hidden = False
            if hidden:
                return
            time.sleep(0.05)
        self.fail("Expected #postStatus to be hidden")

    def _wait_for_row_status_contains(self, page, row_index: int, text: str, *, timeout_s: float = 3.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        target = str(text or "").strip().upper()
        while time.time() < deadline:
            try:
                row = page.locator("#rows .row").nth(row_index)
                if target == "PASS":
                    pass_cls = row.locator(".actions button").nth(0).get_attribute("class") or ""
                    if "is-pass-active" in pass_cls:
                        return
                    time.sleep(0.05)
                    continue
                if target == "FAIL":
                    fail_cls = row.locator(".actions button").nth(1).get_attribute("class") or ""
                    if "is-fail-active" in fail_cls:
                        return
                    time.sleep(0.05)
                    continue
                status = row.inner_text()
            except Exception:
                status = ""
            if text in (status or ""):
                return
            time.sleep(0.05)
        self.fail(f"Expected row {row_index} to contain {text!r}")

    def _wait_for_row_last_test_exact(self, page, row_index: int, text: str, *, timeout_s: float = 3.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                value = page.locator("#rows .row").nth(row_index).locator(".row-last-test").inner_text()
            except Exception:
                value = ""
            if (value or "").strip() == text:
                return
            time.sleep(0.05)
        self.fail(f"Expected row {row_index} .row-last-test to equal {text!r}")

    def _wait_for_row_last_test_contains(self, page, row_index: int, text: str, *, timeout_s: float = 3.0) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                value = page.locator("#rows .row").nth(row_index).locator(".row-last-test").inner_text()
            except Exception:
                value = ""
            if text in (value or ""):
                return
            time.sleep(0.05)
        self.fail(f"Expected row {row_index} .row-last-test to contain {text!r}")

    def _wait_for_row_button_state(  # noqa: ANN001
        self, page, row_index: int, *, pass_active: bool, fail_active: bool, timeout_s: float = 3.0
    ) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                pass_cls = page.locator("#rows .row").nth(row_index).locator(".actions button").nth(0).get_attribute("class") or ""
                fail_cls = page.locator("#rows .row").nth(row_index).locator(".actions button").nth(1).get_attribute("class") or ""
            except Exception:
                pass_cls = ""
                fail_cls = ""
            pass_ok = ("is-pass-active" in pass_cls) == bool(pass_active)
            fail_ok = ("is-fail-active" in fail_cls) == bool(fail_active)
            if pass_ok and fail_ok:
                return
            time.sleep(0.05)
        self.fail(
            f"Expected row {row_index} pass/fail active flags to be pass={pass_active} fail={fail_active}; "
            f"got passCls={pass_cls!r} failCls={fail_cls!r}"
        )

    def _assert_ws_helpers_present(self, html: str) -> None:
        self.assertIn("function buildTargetPayload", html)
        self.assertIn("function _connectTechWs", html)
        self.assertEqual(html.count("function _connectTechWs"), 1, "Expected a single _connectTechWs definition")
        self.assertIn("lastAppliedSeq", html)
        self.assertIn("sync.request", html)
        self.assertNotIn("await fetch(", html, "HTML should not contain top-level await fetch fallback")

    def _install_fake_ws(self, page) -> None:  # noqa: ANN001
        page.add_init_script(
            """
(() => {
  const outbox = [];
  const sockets = [];
  class FakeWebSocket {
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      sockets.push(this);
      setTimeout(() => {
        this.readyState = 1;
        if (this.onopen) this.onopen({});
        try {
          const raw = sessionStorage.getItem("__ws_open_messages");
          if (raw) {
            const msgs = JSON.parse(raw);
            sessionStorage.removeItem("__ws_open_messages");
            if (Array.isArray(msgs)) {
              msgs.forEach((msg) => {
                const payload = (typeof msg === "string") ? msg : JSON.stringify(msg);
                if (this.onmessage) this.onmessage({ data: payload });
              });
            }
          }
        } catch (_e) {}
      }, 0);
    }
    send(data) {
      try {
        outbox.push(JSON.parse(data));
      } catch (_e) {
        outbox.push(data);
      }
    }
    close() {
      this.readyState = 3;
      if (this.onclose) this.onclose({});
    }
  }
  window.__wsOutbox = outbox;
  window.__emitWs = (msg) => {
    const payload = (typeof msg === "string") ? msg : JSON.stringify(msg);
    sockets.forEach(ws => {
      if (ws.onmessage) ws.onmessage({ data: payload });
    });
  };
  window.WebSocket = FakeWebSocket;
})();
"""
        )

    def _wait_for_ws_outbox(self, page, *, min_posts: int = 1, timeout_s: float = 3.0, include_sync: bool = False) -> None:  # noqa: ANN001
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                if include_sync:
                    count = page.evaluate("window.__wsOutbox ? window.__wsOutbox.length : 0")
                else:
                    count = page.evaluate(
                        "window.__wsOutbox ? window.__wsOutbox.filter(x => !(x && typeof x === 'object' && x.type === 'sync.request')).length : 0"
                    )
            except Exception:
                count = 0
            if count >= min_posts:
                return
            time.sleep(0.05)
        self.fail(f"Expected at least {min_posts} WS send(s).")

    def _ws_payload(self, page, index: int = 0, include_sync: bool = False):  # noqa: ANN001
        if include_sync:
            return page.evaluate(f"window.__wsOutbox[{index}]")
        return page.evaluate(
            f"(window.__wsOutbox || []).filter(x => !(x && typeof x === 'object' && x.type === 'sync.request'))[{index}]"
        )

    def _wait_for_log_contains(self, logs: list[str], text: str, *, timeout_s: float = 3.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if any(text in (line or "") for line in logs):
                return
            time.sleep(0.05)
        self.fail(f"Expected console log containing {text!r}")

    def _wait_for_log_contains_all(self, logs: list[str], tokens: list[str], *, timeout_s: float = 3.0) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            for line in logs:
                if all(tok in (line or "") for tok in tokens):
                    return
            time.sleep(0.05)
        self.fail(f"Expected console log containing all tokens {tokens!r}")

    def test_event_pass_posts_result(self):
        from sentinel.generation.render_core import render_project_home_html, load_json

        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        expected_scope = {"scopeType": "UNITTEST", "scopeId": "S-1"}
        expected_resolved = {"driver": {"id": 123, "name": "Demo"}, "commands": [{"id": 1, "name": "PowerOn"}]}
        project_data = {
            "source": {"file": "UnitTest.apex"},
            "events": {
                "system": [
                    {
                        "diagnostics": {"eventId": 126, "scope": expected_scope, "resolvedData": expected_resolved},
                        "userFacing": {"description": "Test Event", "testTargets": {"Trigger": True}},
                    }
                ],
                "driver": [],
            },
            "devices": [],
        }
        html = render_project_home_html(project_data, app_ui, "unittest")
        self._assert_ws_helpers_present(html)

        token = "techToken123"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            logs: list[str] = []
            page.on("console", lambda msg: logs.append(msg.text))
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click("button.section-toggle[data-target='system-events']")
            page.click(".btn-wrap--home-event .test-btn")
            page.click("#rows .row .actions button")  # first "Pass"
            self._wait_for_ws_outbox(page, min_posts=1)
            self._wait_for_log_contains(logs, "[tech-ws] send")
            self._wait_for_log_contains_all(logs, ["[tech-ws]", "send", "test_result.submit"])
            sent = self._ws_payload(page)
            self.assertEqual(sent["outcome"], "PASS")
            self.assertEqual(sent["target"]["kind"], "EVENT")
            self.assertEqual(sent["target"]["targetKey"], "event:126:Trigger")
            self.assertEqual(sent["target"]["refs"]["scope"], expected_scope)
            self.assertEqual(sent["target"]["refs"]["resolvedData"], expected_resolved)
            page.evaluate(
                """
(payload) => window.__emitWs({
  type: "test_result",
  projectId: "proj-1",
  recordedAtUtc: "2026-03-21T00:00:00Z",
  targetKey: payload.target.targetKey,
  outcome: payload.outcome,
  targetName: payload.target.targetName,
  kind: payload.target.kind,
  refs: payload.target.refs
})
""",
                sent,
            )
            self._wait_for_status_hidden(page)
            self._wait_for_row_status_contains(page, 0, "PASS")
            self._wait_for_row_last_test_exact(page, 0, "Last Test: 2026-03-21 00:00:00Z")
            self._wait_for_row_button_state(page, 0, pass_active=True, fail_active=False)
        finally:
            server.stop()

    def test_snapshot_rehydrates_pass_and_fail_after_reload(self):
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
                                                    "testTargets": {
                                                        "text": True,
                                                        "macros": False,
                                                        "macroSteps": False,
                                                        "variables": {},
                                                        "pageLink": {"enabled": True, "targetPageId": 514},
                                                    },
                                                    "resolvedPageLink": {"targetPageId": 514},
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
        self._assert_ws_helpers_present(html)

        token = "techTokenSnapshot"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")

            pass_btn = page.locator("#rows .row .actions button").nth(0)
            pass_btn.click()
            self._wait_for_ws_outbox(page, min_posts=1)
            sent_pass = self._ws_payload(page, 0)

            snapshot_payload = {
                "type": "testing_snapshot",
                "results": [
                    {
                        "targetKey": sent_pass["target"]["targetKey"],
                        "outcome": "PASS",
                        "recordedAtUtc": "2026-03-25T10:00:00Z",
                    },
                    {
                        "targetKey": "btn:81:513:48551:PageLink",
                        "outcome": "FAIL",
                        "recordedAtUtc": "2026-03-25T10:00:01Z",
                        "failNote": "Page link broken",
                    },
                ],
            }
            page.evaluate("(payload) => sessionStorage.setItem('__ws_open_messages', JSON.stringify([payload]))", snapshot_payload)
            page.reload()
            page.click(".btn-wrap .test-btn")
            self._wait_for_row_status_contains(page, 0, "PASS")
            self._wait_for_row_last_test_exact(page, 0, "Last Test: 2026-03-25 10:00:00Z")
            self._wait_for_row_status_contains(page, 1, "FAIL")
            self._wait_for_row_last_test_exact(page, 1, "Last Test: 2026-03-25 10:00:01Z")
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
        self._assert_ws_helpers_present(html)

        token = "techToken456"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")
            page.click("#rows .row .actions button")  # first "Pass"
            self._wait_for_ws_outbox(page, min_posts=1)
            sent = self._ws_payload(page)
            self.assertEqual(sent["outcome"], "PASS")
            self.assertEqual(sent["target"]["kind"], "BUTTON")
            self.assertEqual(sent["target"]["targetKey"], "btn:81:513:48551:Macro")
            page.evaluate(
                """
(payload) => window.__emitWs({
  type: "test_result",
  projectId: "proj-1",
  recordedAtUtc: "2026-03-21T00:00:00Z",
  targetKey: payload.target.targetKey,
  outcome: payload.outcome,
  targetName: payload.target.targetName,
  kind: payload.target.kind,
  refs: payload.target.refs
})
""",
                sent,
            )
            self._wait_for_status_hidden(page)
            self._wait_for_row_status_contains(page, 0, "PASS")
            self._wait_for_row_last_test_exact(page, 0, "Last Test: 2026-03-21 00:00:00Z")
        finally:
            server.stop()

    def test_graphics_only_button_posts_graphics_identity(self):
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
                                                    "buttonIdentity": {"buttonTagName": "", "text": "", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {
                                                            "portrait": {
                                                                "visible": True,
                                                                "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120},
                                                            }
                                                        },
                                                    },
                                                    "testTargets": {
                                                        "text": False,
                                                        "macros": False,
                                                        "macroSteps": False,
                                                        "variables": {},
                                                        "graphics": {"bitmap": True, "icon": False},
                                                        "pageLink": False,
                                                    },
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
                                "buttons": [{"buttonId": 48551, "buttonTagName": "", "identifiers": {"text": ""}, "testTargets": {}}],
                                "viewports": [],
                            }
                        ],
                    },
                }
            ],
        }

        html = render_single_device_html(project_data, app_ui, "unittest", device_index=0)
        token = "techTokenGraphicsIdentity"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")

            self.assertTrue(page.locator("#pt").inner_text().endswith("Graphics"))

            page.click("#rows .row .actions button")  # first "Pass"
            self._wait_for_ws_outbox(page, min_posts=1)
            sent = self._ws_payload(page)
            self.assertEqual(sent["target"]["targetName"], "Bitmap")
            self.assertEqual(sent["target"]["refs"].get("buttonName"), "Graphics")
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
        self._assert_ws_helpers_present(html)

        token = "techTokenFail"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")

            fail_btn = page.locator("#rows .row .actions button").nth(1)
            self.assertTrue(fail_btn.is_disabled())

            page.fill("#rows .row textarea", "Broken macro")
            self.assertFalse(fail_btn.is_disabled())

            fail_btn.click()
            self._wait_for_ws_outbox(page, min_posts=1)
            sent = self._ws_payload(page)
            self.assertEqual(sent["outcome"], "FAIL")
            self.assertEqual(sent["failNote"], "Broken macro")
            page.evaluate(
                """
(payload) => window.__emitWs({
  type: "test_result",
  projectId: "proj-1",
  recordedAtUtc: "2026-03-21T00:00:00Z",
  targetKey: payload.target.targetKey,
  outcome: payload.outcome,
  targetName: payload.target.targetName,
  kind: payload.target.kind,
  refs: payload.target.refs,
  failNote: payload.failNote
})
""",
                sent,
            )
            self._wait_for_status_hidden(page)
            self._wait_for_row_status_contains(page, 0, "FAIL")
            self._wait_for_row_last_test_exact(page, 0, "Last Test: 2026-03-21 00:00:00Z")
            self._wait_for_row_button_state(page, 0, pass_active=False, fail_active=True)
        finally:
            server.stop()

    def test_button_pass_status_persists_after_reopen(self):
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
        self._assert_ws_helpers_present(html)

        token = "techTokenPersist"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")
            page.click("#rows .row .actions button")
            self._wait_for_ws_outbox(page, min_posts=1)
            sent = self._ws_payload(page)
            page.evaluate(
                """
(payload) => window.__emitWs({
  type: "test_result",
  projectId: "proj-1",
  recordedAtUtc: "2026-03-21T00:00:00Z",
  targetKey: payload.target.targetKey,
  outcome: payload.outcome,
  targetName: payload.target.targetName,
  kind: payload.target.kind,
  refs: payload.target.refs
})
""",
                sent,
            )
            self._wait_for_status_hidden(page)
            page.click("#close")
            page.click(".btn-wrap .test-btn")
            self._wait_for_row_status_contains(page, 0, "PASS")
            self._wait_for_row_last_test_exact(page, 0, "Last Test: 2026-03-21 00:00:00Z")
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
        self._assert_ws_helpers_present(html)

        token = "techToken789"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html}, post_mode="error")
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click("button.section-toggle[data-target='system-events']")
            page.click(".btn-wrap--home-event .test-btn")
            page.click("#rows .row .actions button")  # first "Pass"
            self._wait_for_ws_outbox(page, min_posts=1)
            page.evaluate(
                "window.__emitWs({type:'error', code:'UNITTEST_ERROR', message:'Unit test forced failure'})"
            )
            self._wait_for_row_last_test_contains(page, 0, "Error: UNITTEST_ERROR")
            self._wait_for_status_hidden(page)
        finally:
            server.stop()

    def test_button_pass_posts_scope_based_tt2_key_when_apex_scope_source_present(self):
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
                                                    "apexScopeSource": {
                                                        "page": {"pageId": 513, "roomId": 23, "sourceDeviceId": 74, "rtiAddress": 2},
                                                        "layer": {"layerId": 300, "sharedLayerId": 700, "roomId": 23, "sourceId": 74},
                                                        "button": {"buttonId": 48551, "buttonTagId": 20},
                                                        "bindings": {"macroIds": [3122], "variableIds": [], "macroStepIds": [5921], "pageLinkId": None},
                                                    },
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
        self._assert_ws_helpers_present(html)

        token = "techTokenScopeTt2"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")
            page.click("#rows .row .actions button")
            self._wait_for_ws_outbox(page, min_posts=1)
            sent = self._ws_payload(page)
            self.assertEqual(sent["outcome"], "PASS")
            self.assertEqual(sent["target"]["targetKey"], "tt2:2:ROOM:23:74:20:macro:3122:Macro")
        finally:
            server.stop()

    def test_pass_all_posts_pass_for_each_target_and_rows_show_last_test(self):
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
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}}
                                                        },
                                                    },
                                                    "testTargets": {
                                                        "text": True,
                                                        "macros": False,
                                                        "macroSteps": False,
                                                        "variables": {},
                                                        "pageLink": {"enabled": True, "targetPageId": 514},
                                                    },
                                                    "resolvedPageLink": {"targetPageId": 514},
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
        self._assert_ws_helpers_present(html)

        token = "techTokenPassAll"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page()
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")

            self.assertEqual(page.locator("#passAll").count(), 1, "Expected Pass All button in popup header")
            page.click("#passAll")
            self._wait_for_ws_outbox(page, min_posts=1)

            sent0 = self._ws_payload(page, 0)
            page.evaluate(
                """
(payload) => window.__emitWs({
  type: "test_result",
  projectId: "proj-1",
  recordedAtUtc: "2026-03-30T01:02:03Z",
  targetKey: payload.target.targetKey,
  outcome: payload.outcome,
  targetName: payload.target.targetName,
  kind: payload.target.kind,
  refs: payload.target.refs
})
""",
                sent0,
            )
            self._wait_for_ws_outbox(page, min_posts=2)
            sent1 = self._ws_payload(page, 1)
            self.assertEqual(sent0["outcome"], "PASS")
            self.assertEqual(sent1["outcome"], "PASS")
            self.assertNotEqual(sent0["target"]["targetKey"], sent1["target"]["targetKey"])

            page.evaluate(
                """
([a,b]) => {
  window.__emitWs({
    type: "test_result",
    projectId: "proj-1",
    recordedAtUtc: "2026-03-30T01:02:03Z",
    targetKey: a.target.targetKey,
    outcome: a.outcome,
    targetName: a.target.targetName,
    kind: a.target.kind,
    refs: a.target.refs
  });
  window.__emitWs({
    type: "test_result",
    projectId: "proj-1",
    recordedAtUtc: "2026-03-30T01:02:04Z",
    targetKey: b.target.targetKey,
    outcome: b.outcome,
    targetName: b.target.targetName,
    kind: b.target.kind,
    refs: b.target.refs
  });
}
""",
                [sent0, sent1],
            )
            self._wait_for_row_status_contains(page, 0, "PASS")
            self._wait_for_row_last_test_exact(page, 0, "Last Test: 2026-03-30 01:02:03Z")
            self._wait_for_row_button_state(page, 0, pass_active=True, fail_active=False)
            self._wait_for_row_status_contains(page, 1, "PASS")
            self._wait_for_row_last_test_exact(page, 1, "Last Test: 2026-03-30 01:02:04Z")
            self._wait_for_row_button_state(page, 1, pass_active=True, fail_active=False)
        finally:
            server.stop()

    def test_testing_popup_uses_stable_hidden_until_hover_scroll_contract(self):
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
                        "pages": [],
                    },
                    "diagnostics": {"deviceId": 81, "pages": []},
                }
            ],
        }

        html = render_single_device_html(project_data, app_ui, "unittest", device_index=0)
        self.assertIn(".rows-scroll{", html)
        self.assertIn("scrollbar-width:thin", html)
        self.assertIn("scrollbar-color:transparent transparent", html)
        self.assertIn("scrollbar-gutter:stable overlay", html)
        self.assertIn(".rows-scroll.scroll-hover:hover{scrollbar-color:#a9bccd transparent;}", html)

    def test_close_button_right_edge_aligns_with_group_box_right_edge(self):
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
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}}
                                                        },
                                                    },
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}, "pageLink": False},
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
        token = "techTokenCloseAlign"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page(viewport={"width": 1400, "height": 900})
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")
            alignment = page.evaluate(
                """
() => {
  const row = document.querySelector('#rows .row');
  const closeBtn = document.getElementById('close');
  if (!row || !closeBtn) return null;
  const rr = row.getBoundingClientRect();
  const cr = closeBtn.getBoundingClientRect();
  return { rowRight: rr.right, closeRight: cr.right, delta: Math.abs(rr.right - cr.right) };
}
"""
            )
            self.assertIsNotNone(alignment)
            self.assertLessEqual(float(alignment["delta"]), 1.0, alignment)
        finally:
            server.stop()

    def test_close_button_has_12px_gap_below_group_box(self):
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
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}}
                                                        },
                                                    },
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}, "pageLink": False},
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
        token = "techTokenCloseGap"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page(viewport={"width": 1400, "height": 900})
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.click(".btn-wrap .test-btn")
            spacing = page.evaluate(
                """
() => {
  const row = document.querySelector('#rows .row:last-child');
  const closeBtn = document.getElementById('close');
  if (!row || !closeBtn) return null;
  const rr = row.getBoundingClientRect();
  const cr = closeBtn.getBoundingClientRect();
  return { gap: Math.round(cr.top - rr.bottom) };
}
"""
            )
            self.assertIsNotNone(spacing)
            self.assertEqual(int(spacing["gap"]), 12, spacing)
        finally:
            server.stop()

    def test_popup_grows_with_targets_until_max_then_rows_scroll(self):
        from sentinel.generation.render_core import render_single_device_html, load_json

        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        many_vars = {
            "Text": True,
            "Reversed": True,
            "Inactive": True,
            "Visible": True,
            "Value": True,
            "State": True,
            "Command": True,
            "Image": True,
            "List": True,
        }
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
                                                    "buttonIdentity": {"buttonTagName": "BTN-SMALL", "text": "Small", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}}
                                                        },
                                                    },
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "resolvedPageLink": {"targetPageId": None},
                                                },
                                                {
                                                    "buttonIdentity": {"buttonTagName": "BTN-LARGE", "text": "Large", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 70, "left": 10, "height": 44, "width": 120}}
                                                        },
                                                    },
                                                    "testTargets": {
                                                        "text": True,
                                                        "macros": True,
                                                        "macroSteps": True,
                                                        "variables": many_vars,
                                                        "graphics": {"bitmap": True, "icon": True},
                                                        "pageLink": {"enabled": True, "targetPageId": 514},
                                                    },
                                                    "resolvedPageLink": {"targetPageId": 514},
                                                },
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
                                "uiItems": [{"buttonId": 48551}, {"buttonId": 48552}],
                                "buttons": [
                                    {"buttonId": 48551, "buttonTagName": "BTN-SMALL", "identifiers": {"text": "Small"}, "testTargets": {}},
                                    {"buttonId": 48552, "buttonTagName": "BTN-LARGE", "identifiers": {"text": "Large"}, "testTargets": {}},
                                ],
                                "viewports": [],
                            }
                        ],
                    },
                }
            ],
        }

        html = render_single_device_html(project_data, app_ui, "unittest", device_index=0)
        token = "techTokenPopupSizing"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page(viewport={"width": 1400, "height": 900})
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")

            page.locator(".btn-wrap .test-btn").nth(0).click()
            small = page.evaluate(
                """
() => {
  const pop = document.querySelector('#ov .pop');
  const rows = document.getElementById('rows');
  if (!pop || !rows) return null;
  const r = pop.getBoundingClientRect();
  return {
    popHeight: r.height,
    top: r.top,
    bottomSpace: window.innerHeight - r.bottom,
    rowsScrollable: rows.scrollHeight > rows.clientHeight + 1
  };
}
"""
            )
            page.click("#close")

            page.locator(".btn-wrap .test-btn").nth(1).click()
            large = page.evaluate(
                """
() => {
  const pop = document.querySelector('#ov .pop');
  const rows = document.getElementById('rows');
  if (!pop || !rows) return null;
  const r = pop.getBoundingClientRect();
  return {
    popHeight: r.height,
    top: r.top,
    bottomSpace: window.innerHeight - r.bottom,
    rowsScrollable: rows.scrollHeight > rows.clientHeight + 1
  };
}
"""
            )

            self.assertIsNotNone(small)
            self.assertIsNotNone(large)
            self.assertGreater(float(large["popHeight"]), float(small["popHeight"]), {"small": small, "large": large})
            self.assertTrue(bool(large["rowsScrollable"]), {"small": small, "large": large})
            self.assertLessEqual(abs(float(large["top"]) - float(large["bottomSpace"])), 1.0, {"small": small, "large": large})
        finally:
            server.stop()

    def test_button_visual_state_contract_category_fill_trim_link_and_counts(self):
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
                                            "screenLabels": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "LBL-1", "text": "Label One", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 80, "left": 10, "height": 18, "width": 24}}
                                                        },
                                                    },
                                                    "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "resolvedPageLink": {"targetPageId": None},
                                                }
                                            ],
                                            "hardButtons": [],
                                            "screenButtons": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "BTN-1", "text": "Button One", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 10, "left": 10, "height": 44, "width": 120}}
                                                        },
                                                    },
                                                    "testTargets": {
                                                        "text": False,
                                                        "macros": True,
                                                        "macroSteps": False,
                                                        "variables": {},
                                                        "pageLink": {"enabled": True, "targetPageId": 514},
                                                    },
                                                    "resolvedPageLink": {"targetPageId": 514},
                                                }
                                            ],
                                            "uiItems": [
                                                {
                                                    "buttonIdentity": {"buttonTagName": "UI-1", "text": "Ui Item", "buttonType": None},
                                                    "buttonUI": {
                                                        "fontSize": 10,
                                                        "orientations": {
                                                            "portrait": {"visible": True, "coordinates": {"top": 120, "left": 10, "height": 44, "width": 120}}
                                                        },
                                                    },
                                                    "testTargets": {"text": False, "macros": False, "macroSteps": False, "variables": {}, "pageLink": False},
                                                    "resolvedPageLink": {"targetPageId": None},
                                                }
                                            ],
                                        },
                                        "viewports": [],
                                    }
                                ],
                            },
                            {"pageName": "Other", "layers": [{"layerName": "Layer 1", "layerOrder": 0, "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": [], "uiItems": []}, "viewports": []}]},
                        ],
                    },
                    "diagnostics": {
                        "deviceId": 81,
                        "pages": [
                            {
                                "pageId": 513,
                                "pageName": "Home",
                                "uiItems": [],
                                "buttons": [
                                    {"buttonId": 48551, "buttonTagName": "BTN-1", "identifiers": {"text": "Button One"}, "testTargets": {}},
                                    {"buttonId": 48552, "buttonTagName": "LBL-1", "identifiers": {"text": "Label One"}, "testTargets": {}},
                                    {"buttonId": 48553, "buttonTagName": "UI-1", "identifiers": {"text": "Ui Item"}, "testTargets": {}},
                                ],
                                "viewports": [],
                            },
                            {"pageId": 514, "pageName": "Other", "uiItems": [], "buttons": [], "viewports": []},
                        ],
                    },
                }
            ],
        }

        html = render_single_device_html(project_data, app_ui, "unittest", device_index=0)
        token = "techTokenVisualContract"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page(viewport={"width": 1400, "height": 900})
            self._install_fake_ws(page)
            snapshot_payload = {
                "type": "testing_snapshot",
                "results": [
                    {"targetKey": "btn:81:513:48551:Macro", "outcome": "PASS", "recordedAtUtc": "2026-03-30T01:02:03Z"},
                    {"targetKey": "btn:81:513:48551:PageLink", "outcome": "FAIL", "recordedAtUtc": "2026-03-30T01:02:04Z"},
                    {"targetKey": "btn:81:513:48552:Text", "outcome": "FAIL", "recordedAtUtc": "2026-03-30T01:02:05Z"},
                ],
            }
            page.add_init_script(
                f"""
(() => {{
  try {{ sessionStorage.setItem("__ws_open_messages", JSON.stringify([{json.dumps(snapshot_payload)}])); }} catch (_e) {{}}
}})();
"""
            )
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.wait_for_timeout(120)
            visual = page.evaluate(
                """
() => {
  const byTag = (tag) => document.querySelector(`.btn-wrap[data-button-tag="${tag}"]`);
  const styleOfButton = (el) => {
    const btn = el ? el.querySelector(".test-btn") : null;
    const cs = btn ? getComputedStyle(btn) : null;
    const count = el ? el.querySelector(".btn-pass-total") : null;
    const countCs = count ? getComputedStyle(count) : null;
    const link = el ? el.querySelector(".page-link-hit") : null;
    const linkCs = link ? getComputedStyle(link) : null;
    return {
      bg: cs ? cs.backgroundColor : "",
      trim: cs ? cs.getPropertyValue("--btn-state-trim-color").trim() : "",
      countText: count ? count.textContent : "",
      countDisplay: countCs ? countCs.display : "",
      countVisibility: countCs ? countCs.visibility : "",
      linkOpacity: linkCs ? linkCs.opacity : "",
      linkPointerEvents: linkCs ? linkCs.pointerEvents : "",
      btnText: btn ? btn.textContent : "",
    };
  };
  return {
    btn1: styleOfButton(byTag("BTN-1")),
    lbl1: styleOfButton(byTag("LBL-1")),
    ui1: styleOfButton(byTag("UI-1")),
  };
}
"""
            )
            self.assertEqual(visual["btn1"]["bg"], "rgb(44, 111, 183)")
            self.assertIn(visual["btn1"]["trim"], ("rgb(239, 68, 68)", "#ef4444"))
            self.assertEqual(visual["btn1"]["countText"].strip(), "1/2")
            self.assertEqual(visual["btn1"]["countDisplay"], "block")
            self.assertEqual(visual["btn1"]["countVisibility"], "visible")
            self.assertEqual(visual["btn1"]["linkOpacity"], "1")
            self.assertEqual(visual["btn1"]["linkPointerEvents"], "auto")
            self.assertEqual(visual["btn1"]["btnText"].strip(), "Button One")

            self.assertEqual(visual["lbl1"]["bg"], "rgb(88, 88, 90)")
            self.assertIn(visual["lbl1"]["trim"], ("rgb(239, 68, 68)", "#ef4444"))
            self.assertEqual(visual["lbl1"]["countText"].strip(), "0/1")
            self.assertIn(visual["lbl1"]["countDisplay"], ("none", "block"))
            self.assertEqual(visual["lbl1"]["countVisibility"], "hidden")
            self.assertEqual(visual["lbl1"]["btnText"].strip(), "Label One")

            self.assertEqual(visual["ui1"]["bg"], "rgb(167, 169, 172)")
            self.assertIn(visual["ui1"]["trim"], ("transparent", "rgba(0, 0, 0, 0)"))
            self.assertEqual(visual["ui1"]["countText"].strip(), "")
            self.assertEqual(visual["ui1"]["btnText"].strip(), "Ui Item")
        finally:
            server.stop()

    def test_viewport_popup_post_uses_canonical_target_key_with_page_context(self):
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
                                        "buttonCategories": {"screenLabels": [], "hardButtons": [], "screenButtons": []},
                                        "viewports": [
                                            {
                                                "viewportIdentity": {"viewportButtonId": 990},
                                                "viewportUI": {
                                                    "navigationMode": "page",
                                                    "orientations": {
                                                        "portrait": {
                                                            "visible": True,
                                                            "coordinates": {"top": 80, "left": 20, "height": 300, "width": 420},
                                                        }
                                                    },
                                                },
                                                "layers": [
                                                    {
                                                        "layerName": "Viewport Layer",
                                                        "layerOrder": 0,
                                                        "frames": [
                                                            {
                                                                "frameId": 0,
                                                                "buttonCategories": {
                                                                    "screenLabels": [],
                                                                    "hardButtons": [],
                                                                    "screenButtons": [
                                                                        {
                                                                            "buttonIdentity": {
                                                                                "buttonTagName": "ALL-OFF",
                                                                                "text": "All Off",
                                                                                "buttonType": None,
                                                                            },
                                                                            "buttonUI": {
                                                                                "fontSize": 10,
                                                                                "orientations": {
                                                                                    "portrait": {
                                                                                        "visible": True,
                                                                                        "coordinates": {
                                                                                            "top": 12,
                                                                                            "left": 12,
                                                                                            "height": 50,
                                                                                            "width": 240,
                                                                                        },
                                                                                    }
                                                                                },
                                                                            },
                                                                            "testTargets": {
                                                                                "text": True,
                                                                                "macros": False,
                                                                                "macroSteps": True,
                                                                                "variables": {},
                                                                                "graphics": {"bitmap": True, "icon": True},
                                                                            },
                                                                        }
                                                                    ],
                                                                },
                                                            }
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
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
                                "uiItems": [],
                                "buttons": [],
                                "viewports": [
                                    {
                                        "viewportButtonId": 990,
                                        "frames": [
                                            {
                                                "frameId": 0,
                                                "buttons": [
                                                    {
                                                        "buttonId": 48551,
                                                        "buttonTagName": "ALL-OFF",
                                                        "identifiers": {"text": "All Off"},
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                }
            ],
        }

        html = render_single_device_html(project_data, app_ui, "unittest", device_index=0)
        token = "techTokenViewportCanonical"
        server = _CaptureServer(html_by_path={f"/testing/{token}": html})
        port = server.start()
        try:
            page = self._browser.new_page(viewport={"width": 1400, "height": 900})
            self._install_fake_ws(page)
            page.goto(f"http://127.0.0.1:{port}/testing/{token}")
            page.locator(".vp-box").first.click()
            page.locator(".vp-popup-stage .btn-wrap.vp-btn .test-btn").first.click()
            page.locator("#rows .row .actions button").first.click()
            self._wait_for_ws_outbox(page, min_posts=1)
            sent = self._ws_payload(page)
            self.assertEqual(sent["outcome"], "PASS")
            self.assertEqual(sent["target"]["targetKey"], "vpbtn:81:513:990:48551:Text")
        finally:
            server.stop()
