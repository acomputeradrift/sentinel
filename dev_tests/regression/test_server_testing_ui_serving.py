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

    def test_testing_ui_payload_mode_serves_shell_and_manifest(self):
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

            r = client.get(f"/testing/{tech_token}?runtime=payload")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Sentinel Testing Runtime", r.text)
            self.assertIn("/testing/" + tech_token + "/files/", r.text)
            self.assertIn("unittest__project-manifest.json", r.text)

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

