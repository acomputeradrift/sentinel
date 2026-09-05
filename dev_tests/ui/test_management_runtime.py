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

    def test_management_page_create_list_copy_open(self):
        from playwright.sync_api import expect

        page = self._browser.new_page()
        state: dict[str, object] = {
            "clients": [],
            "projects": [],
            "technicians": [],
            "tech_links": [],
        }

        def fulfill_json(route, body, status=200):
            route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

        def handle_clients(route, request):
            if request.method == "GET":
                fulfill_json(route, state["clients"])
                return
            data = json.loads(request.post_data or "{}")
            client = {"clientId": "client-1", "name": data.get("name") or "Acme", "createdAtUtc": "2026-03-21T00:00:00Z"}
            state["clients"] = [client]
            fulfill_json(route, client)

        def handle_projects(route, request):
            if request.method == "GET":
                fulfill_json(route, state["projects"])
                return
            data = json.loads(request.post_data or "{}")
            proj = {
                "projectId": "proj-1",
                "clientId": "client-1",
                "name": data.get("name") or "Job One",
                "status": "READY",
                "createdAtUtc": "2026-03-21T00:00:00Z",
            }
            state["projects"] = [proj]
            fulfill_json(route, proj)

        def handle_technicians(route, request):
            if request.method == "GET":
                fulfill_json(
                    route,
                    {"companyId": "company-1", "companyName": "Jamie", "technicians": state["technicians"]},
                )
                return
            data = json.loads(request.post_data or "{}")
            tech = {
                "technicianId": "tech-1",
                "companyId": "company-1",
                "name": data.get("name") or "Alex",
                "createdAtUtc": "2026-03-21T00:00:00Z",
            }
            state["technicians"] = [tech]
            fulfill_json(route, tech)

        def handle_tech_links(route, request):
            path = request.url.split("?")[0]
            if request.method == "GET":
                fulfill_json(route, state["tech_links"])
                return
            if request.method == "POST" and path.endswith("/tech-links"):
                data = json.loads(request.post_data or "{}")
                if state["tech_links"]:
                    fulfill_json(route, state["tech_links"][0])
                    return
                link = {
                    "techLinkId": "tl-1",
                    "technicianId": "tech-1",
                    "name": data.get("name") or "Alex",
                    "label": data.get("name") or "Alex",
                    "createdAtUtc": "2026-03-21T00:01:00Z",
                    "issuedAtUtc": "2026-03-21T00:01:00Z",
                    "techUrl": "/testing/token-persist-1",
                }
                state["tech_links"] = [link]
                fulfill_json(route, link)
                return
            route.fulfill(status=405, body="method not allowed")

        page.route("**/api/v1/commissioning/clients", handle_clients)
        page.route("**/api/v1/commissioning/clients/*/projects", handle_projects)
        page.route("**/api/v1/commissioning/technicians", handle_technicians)
        page.route("**/api/v1/commissioning/projects/*/tech-links**", handle_tech_links)

        url = f"{self._static.base_url}/src/sentinel/ui/management/index.html"
        page.goto(url)
        expect(page.get_by_role("heading", name="Sentinel Management")).to_be_visible()

        page.locator("#clientSelect").select_option(value="__new_client__")
        page.locator("#newClientName").fill("Acme")
        page.locator("#newClientSubmit").click()
        expect(page.locator("#clientSelect")).to_have_value("client-1")

        page.locator("#projectSelect").select_option(value="__new_project__")
        page.locator("#newProjectName").fill("Job One")
        page.locator("#newProjectSubmit").click()
        expect(page.locator("#projectSelect")).to_have_value("proj-1")

        page.locator("#newTechnicianName").fill("Alex")
        page.locator("#createTechnicianBtn").click()
        expect(page.locator("#technicianRoster")).to_contain_text("Alex")

        page.locator("#techLinkName").fill("Alex")
        page.locator("#issueTechLinkBtn").click()
        expect(page.get_by_test_id("tech-url")).to_contain_text("/testing/token-persist-1")
        expect(page.get_by_role("button", name="Copy")).to_be_visible()
        expect(page.get_by_role("button", name="Open")).to_be_visible()
        expect(page.get_by_role("button", name="Rotate")).to_be_visible()
        expect(page.get_by_role("button", name="Revoke")).to_be_visible()

        page.locator("#techLinkName").fill("Alex")
        page.locator("#issueTechLinkBtn").click()
        expect(page.locator("[data-testid='tech-url']")).to_have_count(1)
        page.close()


if __name__ == "__main__":
    unittest.main()
