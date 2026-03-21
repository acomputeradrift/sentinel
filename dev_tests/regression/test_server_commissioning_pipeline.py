import os
import tempfile
import unittest
from pathlib import Path
import sys


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


def _write_test_apex(path: Path) -> None:
    from dev_tests.integration.test_scripts import create_test_apex

    create_test_apex(path)


class CommissioningPipelineTest(unittest.TestCase):
    def test_upload_then_regenerate_writes_generated_html(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")

            from sentinel.server.app.main import create_app

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            project_id = p["projectId"]

            apex_path = Path(td) / "sample.apex"
            _write_test_apex(apex_path)

            with apex_path.open("rb") as f:
                up = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/uploads",
                    files={"apex": ("sample.apex", f, "application/octet-stream")},
                )
            self.assertEqual(up.status_code, 200)
            upload_id = up.json()["uploadId"]

            regen = client.post(f"/api/v1/commissioning/projects/{project_id}/regenerate", json={"uploadId": upload_id})
            self.assertEqual(regen.status_code, 200)

            out_dir = Path(os.environ["SENTINEL_GENERATED_ROOT"]) / project_id
            homes = list(out_dir.glob("*__project-home.html"))
            self.assertTrue(homes, "Expected a project home HTML file.")
