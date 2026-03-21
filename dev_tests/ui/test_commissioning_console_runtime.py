import json
import socket
import sys
import tempfile
import threading
import time
import re
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


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
        host, port = sock.getsockname()
        sock.close()

        self._httpd = ThreadingHTTPServer((host, port), Handler)
        self.base_url = f"http://{host}:{port}"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                s = socket.create_connection((host, port), timeout=0.2)
                s.close()
                return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("Static server failed to start.")

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


class CommissioningConsoleRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as e:
            raise unittest.SkipTest(
                "Playwright is not installed in the current Python environment. "
                "Install it in the active venv, e.g. `python -m pip install playwright` "
                "and ensure browsers are available (typically `python -m playwright install chromium`)."
            ) from e

        cls._static = _StaticServer(ROOT)
        cls._static.start()

        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()
            cls._static.stop()

    def test_commissioning_ui_drives_core_mvp_flow(self):
        from playwright.sync_api import expect

        page = self._browser.new_page()

        state: dict[str, object] = {
            "clients": [],
            "clients_by_id": {},
            "projects_by_client": {},
            "projects_by_id": {},
            "tech_links_by_project": {},
            "last_upload_content_type": None,
            "expected_upload_filename": "TEST - System Manager v11.3.apex",
            "last_upload_body_contains_expected": None,
            "upload_counter": 0,
            "tech_link_counter": 0,
            "tech_link_revoke_counter": 0,
        }

        def fulfill_json(route, payload, status: int = 200):
            route.fulfill(
                status=status,
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload),
            )

        def handle_clients(route, request):
            if request.method == "GET":
                fulfill_json(route, state["clients"])
                return
            if request.method == "POST":
                data = json.loads(request.post_data or "{}")
                client = {"clientId": "client-1", "name": data.get("name", ""), "createdAtUtc": "2026-03-21T00:00:00Z"}
                state["clients"] = [client]
                state["clients_by_id"]["client-1"] = client
                state["projects_by_client"]["client-1"] = []
                fulfill_json(route, client)
                return
            route.fulfill(status=405, body="method not allowed")

        def handle_projects_create_and_list(route, request):
            parts = request.url.split("/commissioning/clients/")[-1].split("/projects")
            client_id = parts[0].strip("/")
            if request.method == "GET":
                fulfill_json(route, state["projects_by_client"].get(client_id, []))
                return
            if request.method == "POST":
                data = json.loads(request.post_data or "{}")
                proj = {
                    "projectId": "proj-1",
                    "clientId": client_id,
                    "clientName": state["clients_by_id"].get(client_id, {}).get("name", ""),
                    "name": data.get("name", ""),
                    "createdAtUtc": "2026-03-21T00:00:00Z",
                    "status": "EMPTY",
                    "activeUploadId": None,
                    "activeExtractionRunId": None,
                    "activeGenerationRunId": None,
                    "activeTechLinkIds": [],
                }
                state["projects_by_client"][client_id] = [proj]
                state["projects_by_id"][proj["projectId"]] = proj
                state["tech_links_by_project"][proj["projectId"]] = []
                fulfill_json(route, proj)
                return
            route.fulfill(status=405, body="method not allowed")

        def handle_project_detail(route, request):
            project_id = request.url.split("/commissioning/projects/")[-1].split("?")[0].strip("/")
            if request.method != "GET":
                route.fulfill(status=405, body="method not allowed")
                return
            proj = dict(state["projects_by_id"].get(project_id, {}))
            if not proj:
                route.fulfill(status=404, body="not found")
                return
            active_links = [link for link in state["tech_links_by_project"].get(project_id, []) if not link.get("revokedAtUtc")]
            proj["activeTechLinks"] = active_links
            proj["lastGeneratedFilename"] = state.get("expected_upload_filename")
            fulfill_json(route, proj)

        def handle_upload(route, request):
            headers = {k.lower(): v for k, v in request.headers.items()}
            ct = headers.get("content-type", "")
            state["last_upload_content_type"] = ct
            body = request.post_data_buffer or b""
            expected = str(state.get("expected_upload_filename") or "")
            state["last_upload_body_contains_expected"] = expected.encode("utf-8") in body
            state["upload_counter"] = int(state.get("upload_counter") or 0) + 1
            upload_id = f"upload-{state['upload_counter']}"
            fulfill_json(
                route,
                {
                    "uploadId": upload_id,
                    "projectId": "proj-1",
                    "receivedAtUtc": "2026-03-21T00:00:00Z",
                    "originalFilename": expected,
                    "sha256": "deadbeef",
                    "bytes": len(body),
                    "contentType": "application/octet-stream",
                },
            )

        def handle_regenerate(route, request):
            self.assertEqual(request.method, "POST")
            data = json.loads(request.post_data or "{}")
            self.assertEqual(data.get("uploadId"), "upload-1")
            fulfill_json(
                route,
                {
                    "projectId": "proj-1",
                    "status": "READY",
                },
            )

        def handle_tech_links(route, request):
            path = request.url.split("?")[0]
            project_id = path.split("/commissioning/projects/")[-1].split("/tech-links")[0].strip("/")

            if request.method == "GET":
                active_links = [link for link in state["tech_links_by_project"].get(project_id, []) if not link.get("revokedAtUtc")]
                fulfill_json(route, active_links)
                return

            if request.method == "POST" and path.endswith("/tech-links"):
                data = json.loads(request.post_data or "{}")
                state["tech_link_counter"] = int(state.get("tech_link_counter") or 0) + 1
                tech_link_id = f"tl-{state['tech_link_counter']}"
                link = {
                    "techLinkId": tech_link_id,
                    "label": data.get("label") or "Onsite Tech",
                    "techUrl": "/testing/token-abc",
                    "revokedAtUtc": None,
                }
                state["tech_links_by_project"].setdefault(project_id, []).append(link)
                proj = state["projects_by_id"].get(project_id)
                if proj is not None:
                    proj["activeTechLinkIds"] = [item["techLinkId"] for item in state["tech_links_by_project"][project_id] if not item.get("revokedAtUtc")]
                fulfill_json(route, {"techLinkId": tech_link_id, "techUrl": link["techUrl"], "label": link["label"]})
                return

            if request.method in {"DELETE", "POST"} and "/tech-links/" in path:
                suffix = path.split("/tech-links/", 1)[1]
                tech_link_id = suffix.split("/")[0]
                links = state["tech_links_by_project"].get(project_id, [])
                for link in links:
                    if link.get("techLinkId") == tech_link_id and not link.get("revokedAtUtc"):
                        state["tech_link_revoke_counter"] = int(state.get("tech_link_revoke_counter") or 0) + 1
                        link["revokedAtUtc"] = f"2026-03-21T00:0{state['tech_link_revoke_counter']}:00Z"
                        break
                proj = state["projects_by_id"].get(project_id)
                if proj is not None:
                    proj["activeTechLinkIds"] = [item["techLinkId"] for item in links if not item.get("revokedAtUtc")]
                route.fulfill(status=204, body="")
                return

            route.fulfill(status=405, body="method not allowed")

        def handle_progress(route, request):
            self.assertEqual(request.method, "GET")
            fulfill_json(
                route,
                {
                    "projectId": "proj-1",
                    "asOfGenerationRunId": "gen-1",
                    "counts": {"totalTargets": 10, "testedTargets": 3, "pass": 2, "fail": 1, "untested": 7, "percentComplete": 0.3},
                    "lastTestedAtUtc": "2026-03-21T00:00:00Z",
                    "eventSections": {
                        "system": {"counts": {"totalTargets": 4, "testedTargets": 1, "pass": 1, "fail": 0, "untested": 3, "percentComplete": 0.25}, "lastTestedAtUtc": "2026-03-21T00:00:00Z"},
                        "driver": {"counts": {"totalTargets": 2, "testedTargets": 0, "pass": 0, "fail": 0, "untested": 2, "percentComplete": 0.0}, "lastTestedAtUtc": None},
                    },
                    "devices": [],
                },
            )

        def handle_fails(route, request):
            self.assertEqual(request.method, "GET")
            fulfill_json(
                route,
                [
                    {
                        "targetKey": "btn:81:513:48551:Macro",
                        "currentOutcome": "FAIL",
                        "lastTestedAtUtc": "2026-03-21T00:00:00Z",
                        "lastFailNote": "Macro did not run",
                        "recordedBy": {"role": "TECHNICIAN", "actorId": None},
                    },
                    {
                        "targetKey": "event:126:Trigger",
                        "currentOutcome": "FAIL",
                        "lastTestedAtUtc": "2026-03-20T23:00:00Z",
                        "lastFailNote": "Trigger not firing",
                        "recordedBy": {"role": "TECHNICIAN", "actorId": None},
                    },
                ],
            )

        def handle_events(route, request):
            self.assertEqual(request.method, "GET")
            route.fulfill(
                status=200,
                headers={"Content-Type": "text/event-stream; charset=utf-8"},
                body=(
                    "event: test_result\n"
                    "data: "
                    + json.dumps(
                        {
                            "tsUtc": "2026-03-21T00:00:01Z",
                            "type": "test_result",
                            "data": {
                                "recordedAtUtc": "2026-03-21T00:00:01Z",
                                "targetKey": "btn:81:513:48551:Macro",
                                "targetName": "Macro",
                                "outcome": "PASS",
                                "refs": {"deviceName": "Device A", "pageName": "Home", "buttonName": "Button 1"},
                            },
                        }
                    )
                    + "\n\n"
                ),
            )

        page.route("**/api/v1/commissioning/clients", handle_clients)
        page.route("**/api/v1/commissioning/clients/*/projects", handle_projects_create_and_list)
        page.route("**/api/v1/commissioning/projects/*", handle_project_detail)
        page.route("**/api/v1/commissioning/projects/*/uploads", handle_upload)
        page.route("**/api/v1/commissioning/projects/*/regenerate", handle_regenerate)
        page.route("**/api/v1/commissioning/projects/*/tech-links**", handle_tech_links)
        page.route("**/api/v1/commissioning/projects/*/progress", handle_progress)
        page.route("**/api/v1/commissioning/projects/*/fails", handle_fails)
        page.route("**/api/v1/commissioning/projects/*/events", handle_events)

        url = f"{self._static.base_url}/src/sentinel/ui/commissioning/index.html"
        page.goto(url)

        expect(page.get_by_role("heading", name="Commissioning Console")).to_be_visible()

        # Shell + tabs
        expect(page.get_by_role("button", name="Manage")).to_be_visible()
        expect(page.get_by_role("button", name="Commission")).to_be_visible()
        expect(page.get_by_role("button", name="Diagnostics")).to_be_visible()
        expect(page.get_by_role("button", name=re.compile("refresh", re.I))).to_have_count(0)
        expect(page.get_by_role("heading", name="Sentinel Console")).to_be_visible()
        expect(page.locator("#panel-manage")).to_be_visible()
        expect(page.locator("#panel-manage").get_by_role("heading", name="Upload + Regenerate")).to_be_visible()

        # Manage must not render Progress/Fails sections.
        expect(page.locator("#panel-manage [data-testid='progress']")).to_have_count(0)
        expect(page.locator("#panel-manage [data-testid='fails-count']")).to_have_count(0)
        expect(page.locator("#panel-manage [data-testid='fails-list']")).to_have_count(0)

        page.get_by_label("New client name").fill("Client A")
        page.get_by_role("button", name="Create client").click()
        expect(page.get_by_label("Client", exact=True)).to_have_value("client-1")

        page.get_by_label("New project name").fill("Project 1")
        page.get_by_role("button", name="Create project").click()
        expect(page.get_by_label("Project", exact=True)).to_have_value("proj-1")

        apex_path = ROOT / "Assets" / "TEST - System Manager v11.3.apex"
        self.assertTrue(apex_path.exists(), f"Missing apex fixture: {apex_path}")
        page.set_input_files("input[type=file][name=apex]", str(apex_path))
        page.get_by_role("button", name="Upload .apex").click()
        expect(page.get_by_test_id("upload-status")).to_contain_text("upload-1")
        expect(page.locator("#panel-manage")).to_contain_text("Last generated")
        expect(page.locator("#panel-manage")).to_contain_text(apex_path.name)
        self.assertIsNotNone(state["last_upload_content_type"])
        self.assertIn("multipart/form-data", str(state["last_upload_content_type"]))
        self.assertEqual(state["last_upload_body_contains_expected"], True)

        expect(page.get_by_role("button", name="Regenerate")).to_have_count(0)

        page.get_by_label("Tech label").fill("Onsite Tech")
        expect(page.get_by_role("button", name="Create tech link")).to_be_enabled()
        page.get_by_role("button", name="Create tech link").click()
        expect(page.get_by_test_id("tech-url")).to_contain_text("/testing/token-abc")
        expect(page.get_by_text("Onsite Tech")).to_be_visible()
        expect(page.get_by_role("button", name="Revoke")).to_be_visible()
        page.get_by_role("button", name="Revoke").click()
        expect(page.get_by_text("Onsite Tech")).to_have_count(0)

        # Tab switching
        page.get_by_role("button", name="Commission").click()
        expect(page.locator("#panel-commission")).to_be_visible()
        expect(page.locator("#panel-commission")).to_contain_text("Client A")
        expect(page.locator("#panel-commission")).to_contain_text("Project 1")
        expect(page.get_by_test_id("commission-kpi-complete")).to_be_visible()
        expect(page.get_by_test_id("commission-kpi-tested")).to_be_visible()
        expect(page.get_by_test_id("commission-kpi-untested")).to_be_visible()
        expect(page.get_by_test_id("commission-activity")).to_be_visible()
        expect(page.locator("#commissionActivityBody tr")).to_have_count(1)
        expect(page.locator("#commissionActivityBody")).to_contain_text("Device A")
        expect(page.locator("#commissionActivityBody")).to_contain_text("Home")
        expect(page.locator("#commissionActivityBody")).to_contain_text("Button 1")
        expect(page.locator("#commissionActivityBody")).to_contain_text("Macro")
        expect(page.locator("#commissionActivityBody")).to_contain_text("PASS")

        page.get_by_role("button", name="Diagnostics").click()
        expect(page.locator("#panel-diagnostics")).to_be_visible()
        expect(page.locator("#panel-diagnostics")).to_contain_text("Client A")
        expect(page.locator("#panel-diagnostics")).to_contain_text("Project 1")
        expect(page.get_by_role("heading", name="Diagnostics")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Tag")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Timestamp")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Device")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Page Name")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Button Name")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Scope")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Test Target")).to_be_visible()
        expect(page.get_by_role("columnheader", name="Resolved Data")).to_be_visible()
        diag_header_bg = page.locator("#diagnosticsTaskTable th").first.evaluate("el => getComputedStyle(el).backgroundColor")
        self.assertEqual(diag_header_bg, "rgb(23, 123, 181)")
        diag_timestamp_width = page.locator("#diagnosticsTaskTable th").nth(1).evaluate(
            "el => el.getBoundingClientRect().width"
        )
        self.assertLess(diag_timestamp_width, 140)
        page.get_by_role("button", name="Manage").click()
        expect(page.locator("#panel-manage")).to_be_visible()

        # Upload a completely different file name (should warn).
        with tempfile.TemporaryDirectory() as td:
            other_path = Path(td) / "Completely Different Project v1.0.apex"
            other_path.write_bytes(apex_path.read_bytes())
            state["expected_upload_filename"] = other_path.name
            page.set_input_files("input[type=file][name=apex]", str(other_path))
            page.get_by_role("button", name="Upload .apex").click()
            expect(page.get_by_test_id("upload-status")).to_contain_text("upload-2")
            expect(page.get_by_test_id("upload-status")).to_contain_text("WARNING")
            expect(page.get_by_test_id("upload-status")).to_contain_text("Previous:")
            expect(page.get_by_test_id("upload-status")).to_contain_text("New:")

        page.close()
