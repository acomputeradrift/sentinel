import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class ProjectDeviceStaticShellRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from playwright.sync_api import sync_playwright

        cls._pw = sync_playwright().start()
        cls._browser = cls._pw.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._browser.close()
        finally:
            cls._pw.stop()

    def test_shell_runtime_device_page_renders_phase1_static_areas(self):
        from fastapi.testclient import TestClient
        from sentinel.server.app.main import create_app

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = td

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
            tech_token = link["techUrl"].split("/testing/")[1]

            project_dir = Path(td) / p["projectId"]
            project_dir.mkdir(parents=True, exist_ok=True)
            device_name = "unittest__device-demo-0.html"
            (project_dir / device_name).write_text(
                "<!doctype html><html><head><meta charset='utf-8'><title>Old Runtime Device</title></head><body>OLD_RUNTIME</body></html>",
                encoding="utf-8",
            )

            r = client.get(f"/testing/{tech_token}/files/{device_name}?runtime=shell")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers.get("x-sentinel-runtime-mode"), "shell")

            page = self._browser.new_page(viewport={"width": 1400, "height": 900})
            try:
                page.set_content(r.text, wait_until="domcontentloaded")
                self.assertEqual(page.locator("meta[name='sentinel-runtime-mode'][content='shell']").count(), 1)
                self.assertEqual(page.locator("#topControlsStatic").count(), 1)
                self.assertEqual(page.locator("#deviceHeaderCanvas").count(), 1)
                self.assertEqual(page.locator("#deviceViewControlsCanvas").count(), 1)
                self.assertEqual(page.locator("#deviceLayerControlsCanvas").count(), 1)
                self.assertEqual(page.locator("#rtiUsableCanvas").count(), 1)
                self.assertEqual(page.locator("#deviceFooterCanvas").count(), 1)
                self.assertEqual(page.locator("#topControls").count(), 0)
                self.assertEqual(page.locator("#rtiCanvas").count(), 0)

                home_href = page.locator(".project-home-link").first.get_attribute("href") or ""
                self.assertIn(f"/testing/{tech_token}?runtime=shell", home_href)
            finally:
                page.close()

