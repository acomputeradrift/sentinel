import os
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock


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
            repo = app.state.repo

            regen = client.post(f"/api/v1/commissioning/projects/{project_id}/regenerate", json={"uploadId": upload_id})
            self.assertEqual(regen.status_code, 200)
            self.assertIn("activeUpload", regen.json())
            self.assertEqual((regen.json()["activeUpload"] or {}).get("uploadId"), upload_id)

            out_dir = Path(os.environ["SENTINEL_GENERATED_ROOT"]) / project_id
            homes = list(out_dir.glob("*__project-home.html"))
            self.assertTrue(homes, "Expected a project home HTML file.")
            active = repo.get_project_active_upload(projectId=project_id)
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.uploadId, upload_id)
            self.assertEqual(active.originalFilename, "sample.apex")

    def test_active_upload_pointer_changes_only_on_successful_regeneration(self):
        TestClient = _require_fastapi()

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")

            from sentinel.server.app.main import create_app
            from sentinel.server.api import commissioning as commissioning_api

            app = create_app()
            client = TestClient(app)

            c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
            p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
            project_id = p["projectId"]

            apex_path = Path(td) / "sample.apex"
            _write_test_apex(apex_path)

            with apex_path.open("rb") as f:
                up1 = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/uploads",
                    files={"apex": ("sample.apex", f, "application/octet-stream")},
                )
            self.assertEqual(up1.status_code, 200)
            upload_1 = up1.json()["uploadId"]
            ok = client.post(f"/api/v1/commissioning/projects/{project_id}/regenerate", json={"uploadId": upload_1})
            self.assertEqual(ok.status_code, 200)

            repo = app.state.repo
            snap1 = repo.get_project_active_upload(projectId=project_id)
            self.assertIsNotNone(snap1)
            assert snap1 is not None
            self.assertEqual(snap1.uploadId, upload_1)

            with apex_path.open("rb") as f:
                up2 = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/uploads",
                    files={"apex": ("sample2.apex", f, "application/octet-stream")},
                )
            self.assertEqual(up2.status_code, 200)
            upload_2 = up2.json()["uploadId"]

            with mock.patch.object(commissioning_api.pipeline, "regenerate_project", side_effect=RuntimeError("boom")):
                bad = client.post(f"/api/v1/commissioning/projects/{project_id}/regenerate", json={"uploadId": upload_2})
            self.assertEqual(bad.status_code, 500)

            snap2 = repo.get_project_active_upload(projectId=project_id)
            self.assertIsNotNone(snap2)
            assert snap2 is not None
            self.assertEqual(snap2.uploadId, upload_1)
