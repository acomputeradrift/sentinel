import json
import socket
import sys
import threading
import time
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
            "projects_by_client": {},
            "last_upload_content_type": None,
            "last_upload_body_contains": None,
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
                    "name": data.get("name", ""),
                    "createdAtUtc": "2026-03-21T00:00:00Z",
                    "status": "EMPTY",
                    "activeUploadId": None,
                    "activeExtractionRunId": None,
                    "activeGenerationRunId": None,
                    "activeTechLinkIds": [],
                }
                state["projects_by_client"][client_id] = [proj]
                fulfill_json(route, proj)
                return
            route.fulfill(status=405, body="method not allowed")

        def handle_upload(route, request):
            headers = {k.lower(): v for k, v in request.headers.items()}
            ct = headers.get("content-type", "")
            state["last_upload_content_type"] = ct
            body = request.post_data_buffer or b""
            state["last_upload_body_contains"] = b"TEST - System Manager v11.3.apex" in body
            fulfill_json(
                route,
                {
                    "uploadId": "upload-1",
                    "projectId": "proj-1",
                    "receivedAtUtc": "2026-03-21T00:00:00Z",
                    "originalFilename": "TEST - System Manager v11.3.apex",
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
                    "extractionRun": {"extractionRunId": "ex-1", "projectId": "proj-1", "uploadId": "upload-1", "status": "SUCCEEDED"},
                    "generationRun": {"generationRunId": "gen-1", "projectId": "proj-1", "extractionRunId": "ex-1", "status": "SUCCEEDED"},
                },
            )

        def handle_tech_links(route, request):
            self.assertEqual(request.method, "POST")
            fulfill_json(route, {"techLinkId": "tl-1", "techUrl": "/testing/token-abc"})

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

        page.route("**/api/v1/commissioning/clients", handle_clients)
        page.route("**/api/v1/commissioning/clients/*/projects", handle_projects_create_and_list)
        page.route("**/api/v1/commissioning/projects/*/uploads", handle_upload)
        page.route("**/api/v1/commissioning/projects/*/regenerate", handle_regenerate)
        page.route("**/api/v1/commissioning/projects/*/tech-links", handle_tech_links)
        page.route("**/api/v1/commissioning/projects/*/progress", handle_progress)

        url = f"{self._static.base_url}/src/sentinel/ui/commissioning/index.html"
        page.goto(url)

        expect(page.get_by_role("heading", name="Commissioning Console")).to_be_visible()

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
        self.assertIsNotNone(state["last_upload_content_type"])
        self.assertIn("multipart/form-data", str(state["last_upload_content_type"]))
        self.assertEqual(state["last_upload_body_contains"], True)

        page.get_by_role("button", name="Regenerate").click()
        expect(page.get_by_test_id("regen-status")).to_contain_text("gen-1")

        page.get_by_label("Tech label").fill("Onsite Tech")
        page.get_by_role("button", name="Create tech link").click()
        expect(page.get_by_test_id("tech-url")).to_contain_text("/testing/token-abc")

        page.get_by_role("button", name="Refresh progress").click()
        expect(page.get_by_test_id("progress")).to_contain_text("30%")

        page.close()
