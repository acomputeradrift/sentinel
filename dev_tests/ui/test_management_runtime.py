import json
import socket
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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


class ManagementRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            from playwright.sync_api import expect, sync_playwright
        except ModuleNotFoundError as e:
            raise unittest.SkipTest("Playwright is not installed.") from e

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

    def test_management_is_only_active_links_grouped_by_user(self):
        from playwright.sync_api import expect

        page = self._browser.new_page()
        state: dict[str, object] = {
            "links": [
                {
                    "techLinkId": "tl-acme",
                    "projectId": "proj-acme",
                    "clientName": "Acme",
                    "projectName": "Acme Job",
                    "ownerUserId": "user-jamie",
                    "ownerName": "Jamie",
                    "name": "Alex",
                    "techUrl": "/testing/token-acme",
                    "issuedAtUtc": "2026-03-21T00:01:00Z",
                },
                {
                    "techLinkId": "tl-other",
                    "projectId": "proj-other",
                    "clientName": "Other Co",
                    "projectName": "Other Job",
                    "ownerUserId": "user-other",
                    "ownerName": "Other",
                    "name": "Sam",
                    "techUrl": "/testing/token-other",
                    "issuedAtUtc": "2026-03-21T00:02:00Z",
                },
            ],
            "revoked": [],
        }

        def fulfill_json(route, body, status=200):
            route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

        def handle_all_links(route, request):
            path = request.url.split("?")[0]
            if request.method == "GET" and path.endswith("/tech-links"):
                fulfill_json(route, state["links"])
                return
            if request.method == "POST" and path.endswith("/revoke"):
                tech_link_id = path.rstrip("/").split("/tech-links/")[-1].split("/")[0]
                state["revoked"].append(tech_link_id)
                state["links"] = [row for row in state["links"] if row["techLinkId"] != tech_link_id]
                fulfill_json(route, {"techLinkId": tech_link_id, "revoked": True})
                return
            route.fulfill(status=405, body="method not allowed")

        page.route("**/api/v1/commissioning/tech-links**", handle_all_links)

        url = f"{self._static.base_url}/src/sentinel/ui/management/index.html"
        page.goto(url)
        expect(page.get_by_role("heading", name="Sentinel Management")).to_be_visible()
        expect(page.get_by_role("heading", name="Active tech links")).to_be_visible()
        expect(page.get_by_role("heading", name="Context")).to_have_count(0)
        expect(page.get_by_role("heading", name="Technicians")).to_have_count(0)
        expect(page.get_by_role("heading", name="Start new test pass")).to_have_count(0)
        expect(page.get_by_role("heading", name="Reports")).to_have_count(0)
        expect(page.locator("#clientSelect")).to_have_count(0)

        users = page.get_by_test_id("tech-link-user")
        expect(users).to_have_count(2)
        expect(users.nth(0)).to_have_text("Jamie")
        expect(users.nth(1)).to_have_text("Other")
        jamie = page.locator(".user-group").filter(has_text="Jamie")
        other = page.locator(".user-group").filter(has_text="Other")
        expect(jamie).to_contain_text("Acme")
        expect(jamie).to_contain_text("Alex")
        expect(jamie).to_contain_text("/testing/token-acme")
        expect(other).to_contain_text("Other Co")
        expect(other).to_contain_text("Sam")

        other.get_by_role("button", name="Revoke").click()
        expect(page.get_by_test_id("tech-link-user")).to_have_count(1)
        expect(page.locator("#allTechLinksByUser")).to_contain_text("Jamie")
        expect(page.locator("#allTechLinksByUser")).not_to_contain_text("Other Co")
        self.assertEqual(state["revoked"], ["tl-other"])
        page.close()
