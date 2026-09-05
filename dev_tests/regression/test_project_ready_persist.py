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


class ProjectReadyPersistTest(unittest.TestCase):
    def test_generation_success_persists_ready_and_survives_reread(self):
        TestClient = _require_fastapi()
        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")

            original_regen = pipeline.regenerate_project

            def _regen_stub(*, projectId: str, apex_path: Path, phase_hook=None, client_name: str = "", project_name: str = "") -> dict:  # noqa: ARG001
                if callable(phase_hook):
                    phase_hook("extracting", 100)
                    phase_hook("generating", 100)
                out_dir = Path(td) / "generated" / projectId
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "Job_project_data.json").write_text(
                    '{"events":{"system":[],"driver":[]},"devices":[]}',
                    encoding="utf-8",
                )
                return {"projectId": projectId, "outDir": str(out_dir), "projectData": "stub"}

            pipeline.regenerate_project = _regen_stub  # type: ignore[assignment]
            try:
                from sentinel.server.app.main import create_app
                from sentinel.server.services.repositories import InMemoryRepository

                repo = InMemoryRepository()
                app = create_app(repo=repo)
                client = TestClient(app)
                c = client.post("/api/v1/commissioning/clients", json={"name": "Ready Client"}).json()
                p = client.post(
                    f"/api/v1/commissioning/clients/{c['clientId']}/projects",
                    json={"name": "Ready Job"},
                ).json()
                self.assertEqual(p["status"], "EMPTY")
                project_id = p["projectId"]

                up = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/upload-and-regenerate",
                    files={"apex": ("Job v1.apex", b"not-a-real-apex", "application/octet-stream")},
                )
                self.assertEqual(up.status_code, 200, up.text)

                stored = repo.get_project(projectId=project_id)
                self.assertIsNotNone(stored)
                self.assertEqual(stored.status, "READY")

                listed = client.get(f"/api/v1/commissioning/clients/{c['clientId']}/projects").json()
                self.assertEqual(len(listed), 1)
                self.assertEqual(listed[0]["status"], "READY")
            finally:
                pipeline.regenerate_project = original_regen  # type: ignore[assignment]

    def test_existing_generated_artifacts_are_ready_after_restart(self):
        TestClient = _require_fastapi()
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            from sentinel.server.app.main import create_app
            from sentinel.server.services.repositories import InMemoryRepository

            repo = InMemoryRepository()
            app = create_app(repo=repo)
            client = TestClient(app)
            c = client.post("/api/v1/commissioning/clients", json={"name": "Restart Client"}).json()
            p = client.post(
                f"/api/v1/commissioning/clients/{c['clientId']}/projects",
                json={"name": "Restart Job"},
            ).json()
            project_id = p["projectId"]
            self.assertEqual(p["status"], "EMPTY")

            out_dir = Path(td) / "generated" / project_id
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "Restart Job_project_data.json").write_text(
                '{"events":{"system":[],"driver":[]},"devices":[]}',
                encoding="utf-8",
            )

            stored = repo.get_project(projectId=project_id)
            self.assertEqual(stored.status, "READY")
            listed = client.get(f"/api/v1/commissioning/clients/{c['clientId']}/projects").json()
            self.assertEqual(listed[0]["status"], "READY")


if __name__ == "__main__":
    unittest.main()
