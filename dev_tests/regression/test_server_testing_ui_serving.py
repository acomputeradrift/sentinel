import os
import tempfile
import unittest
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed")
    return TestClient


class TestingUiServingTest(unittest.TestCase):
    def test_testing_ui_serves_project_home_and_files(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = td

            from sentinel.server.app.main import create_app

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
            tech_token = link["techUrl"].split("/testing/")[1]

            project_dir = Path(td) / p["projectId"]
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "unittest__project-home.html").write_text(
                "<!doctype html><html><head><meta charset='utf-8'><title>Home</title></head>"
                "<body><a href='device.html'>Device</a></body></html>",
                encoding="utf-8",
            )
            (project_dir / "device.html").write_text("<!doctype html><html><body>Device</body></html>", encoding="utf-8")

            r = client.get(f"/testing/{tech_token}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("<base href=\"/testing/" + tech_token + "/files/\">", r.text)
            self.assertIn("<title>Home</title>", r.text)

            f = client.get(f"/testing/{tech_token}/files/device.html")
            self.assertEqual(f.status_code, 200)
            self.assertIn("Device", f.text)

    def test_testing_ui_serves_newest_project_home_by_mtime(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = td

            from sentinel.server.app.main import create_app

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
            tech_token = link["techUrl"].split("/testing/")[1]

            project_dir = Path(td) / p["projectId"]
            project_dir.mkdir(parents=True, exist_ok=True)

            older = project_dir / "aaa__project-home.html"
            newer = project_dir / "zzz__project-home.html"
            older.write_text("<!doctype html><html><head><title>OLDER</title></head><body></body></html>", encoding="utf-8")
            newer.write_text("<!doctype html><html><head><title>NEWER</title></head><body></body></html>", encoding="utf-8")

            now = int(time.time())
            os.utime(older, (now - 10, now - 10))
            os.utime(newer, (now, now))

            r = client.get(f"/testing/{tech_token}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("<title>NEWER</title>", r.text)

    def test_testing_ui_payload_mode_serves_project_home_when_manifest_exists(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = td

            from sentinel.server.app.main import create_app

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
            tech_token = link["techUrl"].split("/testing/")[1]

            project_dir = Path(td) / p["projectId"]
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "unittest__project-manifest.json").write_text(
                '{"format":"sentinel-testing-payload-v1","projectStem":"unittest","devices":[]}',
                encoding="utf-8",
            )
            (project_dir / "unittest__project-home.html").write_text(
                "<!doctype html><html><head><meta charset='utf-8'><title>Home</title></head>"
                "<body><a href='device.html'>Device</a></body></html>",
                encoding="utf-8",
            )

            r = client.get(f"/testing/{tech_token}?runtime=payload")
            self.assertEqual(r.status_code, 200)
            self.assertIn("<title>Home</title>", r.text)
            self.assertIn("Device", r.text)
            self.assertIn("/testing/" + tech_token + "/files/", r.text)

    def test_testing_ui_payload_mode_handles_missing_manifest(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = td

            from sentinel.server.app.main import create_app

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
            tech_token = link["techUrl"].split("/testing/")[1]

            r = client.get(f"/testing/{tech_token}?runtime=payload")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Payload has not been generated yet", r.text)

    def test_testing_ui_shell_mode_serves_static_device_shell_and_default_stays_runtime_generated(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = td

            from sentinel.server.app.main import create_app

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
            tech_token = link["techUrl"].split("/testing/")[1]

            project_dir = Path(td) / p["projectId"]
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "unittest__project-home.html").write_text(
                "<!doctype html><html><head><meta charset='utf-8'><title>Home</title></head>"
                "<body><a id='d' href='unittest__device-demo-0.html'>Device</a></body></html>",
                encoding="utf-8",
            )
            device_file = project_dir / "unittest__device-demo-0.html"
            device_file.write_text(
                "<!doctype html><html><head><meta charset='utf-8'><title>Old Runtime Device</title></head><body>"
                "<div class='app-ui-controls top-controls' id='topControls'><div></div><div class='header'>Device A - Page 1</div><div></div></div>"
                "<div class='rti-device-canvas' id='rtiDeviceCanvas'><div class='device-page active' data-page-index='0'><div class='btn-wrap'>BTN</div></div></div>"
                "<script>const PAGE_STATE=[{\"deviceName\":\"Device A\",\"pageName\":\"Page 1\",\"layers\":[{\"key\":\"layer-0\",\"name\":\"Main\"},{\"key\":\"layer-1\",\"name\":\"Overlay\"}],\"vpFrames\":[]}];"
                "const ORIENTATION_STATE={\"current\":\"portrait\",\"options\":[\"portrait\"]};"
                "const ZOOM_DEFAULT=125;</script>"
                "</body></html>",
                encoding="utf-8",
            )

            default_r = client.get(f"/testing/{tech_token}/files/{device_file.name}")
            self.assertEqual(default_r.status_code, 200)
            self.assertIn("id='topControls'", default_r.text)
            self.assertNotIn('name="sentinel-runtime-mode" content="shell"', default_r.text)
            self.assertEqual(default_r.headers.get("x-sentinel-runtime-mode"), "default")

            shell_r = client.get(f"/testing/{tech_token}/files/{device_file.name}?runtime=shell")
            self.assertEqual(shell_r.status_code, 200)
            self.assertIn('name="sentinel-runtime-mode" content="shell"', shell_r.text)
            self.assertIn('id="topControlsStatic"', shell_r.text)
            self.assertIn('id="deviceViewControlsCanvas"', shell_r.text)
            self.assertIn('id="deviceLayerControlsCanvas"', shell_r.text)
            self.assertIn('id="rtiUsableCanvas"', shell_r.text)
            self.assertIn("/commissioning/project_device_static_layout.css", shell_r.text)
            self.assertIn(f'href="/testing/{tech_token}?runtime=shell"', shell_r.text)
            self.assertIn('data-shell-phase="2"', shell_r.text)
            self.assertIn("const st=", shell_r.text)
            self.assertIn("rtiDeviceContent", shell_r.text)
            self.assertNotIn("OLD_RUNTIME", shell_r.text)
            self.assertEqual(shell_r.headers.get("x-sentinel-runtime-mode"), "shell")

    def test_testing_ui_shell_mode_home_keeps_runtime_shell_on_device_navigation_links(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = td

            from sentinel.server.app.main import create_app

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            link = client.post(f"/api/v1/commissioning/projects/{p['projectId']}/tech-links", json={"label": "Onsite"}).json()
            tech_token = link["techUrl"].split("/testing/")[1]

            project_dir = Path(td) / p["projectId"]
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "unittest__project-home.html").write_text(
                "<!doctype html><html><head><meta charset='utf-8'><title>Home</title></head>"
                "<body><a id='d1' href='unittest__device-demo-0.html'>Device</a></body></html>",
                encoding="utf-8",
            )

            shell_home = client.get(f"/testing/{tech_token}?runtime=shell")
            self.assertEqual(shell_home.status_code, 200)
            self.assertIn("u.searchParams.set('runtime','shell')", shell_home.text)
            self.assertIn("var base=(document.baseURI", shell_home.text)
            self.assertIn("new URL(href,base)", shell_home.text)
            self.assertNotIn("new URL(href,window.location.href)", shell_home.text)
            self.assertEqual(shell_home.headers.get("x-sentinel-runtime-mode"), "shell")

