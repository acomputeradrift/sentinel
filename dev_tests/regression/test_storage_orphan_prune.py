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


class StorageOrphanPruneTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("DATABASE_URL", None)

    def test_prune_orphan_upload_dirs_removes_empty_and_unknown(self):
        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            live_id = "live-project"
            live_dir = pipeline._project_upload_dir(projectId=live_id)
            live_dir.mkdir(parents=True)
            (live_dir / "keep.apex").write_bytes(b"apex")

            empty_live = pipeline._project_upload_dir(projectId="empty-live")
            empty_live.mkdir(parents=True)

            orphan_empty = pipeline._project_upload_dir(projectId="orphan-empty")
            orphan_empty.mkdir(parents=True)

            orphan_file = pipeline._project_upload_dir(projectId="orphan-file")
            orphan_file.mkdir(parents=True)
            (orphan_file / "dead.apex").write_bytes(b"old")

            removed = pipeline.prune_orphan_upload_dirs(keep_project_ids={live_id, "empty-live"})
            self.assertTrue(live_dir.exists())
            self.assertTrue((live_dir / "keep.apex").exists())
            self.assertFalse(empty_live.exists())
            self.assertFalse(orphan_empty.exists())
            self.assertFalse(orphan_file.exists())
            self.assertIn("empty-live", removed)
            self.assertIn("orphan-empty", removed)
            self.assertIn("orphan-file", removed)
            self.assertNotIn(live_id, removed)

    def test_prune_orphan_generated_dirs_keeps_live_project_and_staging(self):
        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            live_id = "live-project"
            live_dir = pipeline._project_out_dir(projectId=live_id)
            live_dir.mkdir(parents=True)
            (live_dir / "home.html").write_text("<html></html>", encoding="utf-8")

            staging = pipeline._generated_root() / ".staging"
            staging.mkdir(parents=True)
            (staging / "in-flight.txt").write_text("busy", encoding="utf-8")

            orphan = pipeline._project_out_dir(projectId="dead-job")
            orphan.mkdir(parents=True)
            (orphan / "old.html").write_text("<html></html>", encoding="utf-8")

            removed = pipeline.prune_orphan_generated_dirs(keep_project_ids={live_id})
            self.assertTrue(live_dir.exists())
            self.assertTrue(staging.exists())
            self.assertTrue((staging / "in-flight.txt").exists())
            self.assertFalse(orphan.exists())
            self.assertEqual(removed, ["dead-job"])

    def test_retire_project_generated_removes_html_tree_only(self):
        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            project_id = "retire-me"
            out_dir = pipeline._project_out_dir(projectId=project_id)
            out_dir.mkdir(parents=True)
            (out_dir / "page.html").write_text("<html></html>", encoding="utf-8")
            upload_dir = pipeline._project_upload_dir(projectId=project_id)
            upload_dir.mkdir(parents=True)
            (upload_dir / "keep.apex").write_bytes(b"apex")

            self.assertTrue(pipeline.retire_project_generated(projectId=project_id))
            self.assertFalse(out_dir.exists())
            self.assertTrue((upload_dir / "keep.apex").exists())
            self.assertFalse(pipeline.retire_project_generated(projectId=project_id))

    def test_successful_regenerate_keeps_one_upload_row_and_file(self):
        TestClient = _require_fastapi()
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            from sentinel.server.app.main import create_app
            from sentinel.server.api import commissioning as commissioning_api
            from sentinel.server.services.repositories import InMemoryRepository

            app = create_app(repo=InMemoryRepository())
            client = TestClient(app)
            c = client.post("/api/v1/commissioning/clients", json={"name": "Regen One Client"}).json()
            p = client.post(
                f"/api/v1/commissioning/clients/{c['clientId']}/projects",
                json={"name": "Regen One Job"},
            ).json()
            project_id = p["projectId"]
            apex_path = Path(td) / "sample.apex"
            apex_path.write_bytes(b"apex-bytes")

            def _ok_regenerate(*, projectId: str, apex_path: Path, phase_hook=None, client_name: str = "", project_name: str = ""):
                return {
                    "projectId": projectId,
                    "outDir": str(Path(td) / "generated" / projectId),
                    "projectData": "x.json",
                }

            last_id = None
            with mock.patch.object(commissioning_api.pipeline, "regenerate_project", side_effect=_ok_regenerate):
                for name in ("one.apex", "two.apex", "three.apex"):
                    with apex_path.open("rb") as f:
                        up = client.post(
                            f"/api/v1/commissioning/projects/{project_id}/uploads",
                            files={"apex": (name, f, "application/octet-stream")},
                        )
                    self.assertEqual(up.status_code, 200, up.text)
                    last_id = up.json()["uploadId"]
                    regen = client.post(
                        f"/api/v1/commissioning/projects/{project_id}/regenerate",
                        json={"uploadId": last_id},
                    )
                    self.assertEqual(regen.status_code, 200, regen.text)

            upload_dir = Path(os.environ["SENTINEL_UPLOAD_ROOT"]) / project_id
            self.assertEqual(list(upload_dir.glob("*.apex")), [upload_dir / f"{last_id}__three.apex"])
            rows = app.state.repo.list_uploads_for_project(projectId=project_id)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].uploadId, last_id)

    def test_post_uploads_prunes_to_one_file_and_one_row(self):
        TestClient = _require_fastapi()
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            from sentinel.server.app.main import create_app
            from sentinel.server.services.repositories import InMemoryRepository

            app = create_app(repo=InMemoryRepository())
            client = TestClient(app)
            c = client.post("/api/v1/commissioning/clients", json={"name": "Upload Prune Client"}).json()
            p = client.post(
                f"/api/v1/commissioning/clients/{c['clientId']}/projects",
                json={"name": "Upload Prune Job"},
            ).json()
            project_id = p["projectId"]
            apex_path = Path(td) / "sample.apex"
            apex_path.write_bytes(b"apex-bytes")

            last_id = None
            for name in ("one.apex", "two.apex", "three.apex"):
                with apex_path.open("rb") as f:
                    up = client.post(
                        f"/api/v1/commissioning/projects/{project_id}/uploads",
                        files={"apex": (name, f, "application/octet-stream")},
                    )
                self.assertEqual(up.status_code, 200, up.text)
                last_id = up.json()["uploadId"]

            upload_dir = Path(os.environ["SENTINEL_UPLOAD_ROOT"]) / project_id
            self.assertEqual(list(upload_dir.glob("*.apex")), [upload_dir / f"{last_id}__three.apex"])
            rows = app.state.repo.list_uploads_for_project(projectId=project_id)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].uploadId, last_id)

    def test_failed_generate_prunes_and_keeps_previous_active(self):
        TestClient = _require_fastapi()
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            from sentinel.server.app.main import create_app
            from sentinel.server.api import commissioning as commissioning_api
            from sentinel.server.services.repositories import InMemoryRepository

            app = create_app(repo=InMemoryRepository())
            client = TestClient(app)
            c = client.post("/api/v1/commissioning/clients", json={"name": "Fail Prune Client"}).json()
            p = client.post(
                f"/api/v1/commissioning/clients/{c['clientId']}/projects",
                json={"name": "Fail Prune Job"},
            ).json()
            project_id = p["projectId"]
            apex_path = Path(td) / "sample.apex"
            apex_path.write_bytes(b"apex-bytes")

            def _ok_regenerate(*, projectId: str, apex_path: Path, phase_hook=None, client_name: str = "", project_name: str = ""):
                if callable(phase_hook):
                    phase_hook("extracting", 100)
                    phase_hook("generating", 100)
                return {
                    "projectId": projectId,
                    "outDir": str(Path(td) / "generated" / projectId),
                    "projectData": "x.json",
                }

            with apex_path.open("rb") as f:
                with mock.patch.object(
                    commissioning_api.pipeline, "regenerate_project", side_effect=_ok_regenerate
                ):
                    first = client.post(
                        f"/api/v1/commissioning/projects/{project_id}/upload-and-regenerate",
                        files={"apex": ("good.apex", f, "application/octet-stream")},
                    )
            self.assertEqual(first.status_code, 200, first.text)
            first_id = first.json()["uploadId"]

            with apex_path.open("rb") as f:
                with mock.patch.object(
                    commissioning_api.pipeline, "regenerate_project", side_effect=RuntimeError("boom")
                ):
                    bad = client.post(
                        f"/api/v1/commissioning/projects/{project_id}/upload-and-regenerate",
                        files={"apex": ("bad.apex", f, "application/octet-stream")},
                    )
            self.assertEqual(bad.status_code, 500, bad.text)

            rows = app.state.repo.list_uploads_for_project(projectId=project_id)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].uploadId, first_id)
            active = app.state.repo.get_project_active_upload(projectId=project_id)
            self.assertIsNotNone(active)
            assert active is not None
            self.assertEqual(active.uploadId, first_id)
            upload_dir = Path(os.environ["SENTINEL_UPLOAD_ROOT"]) / project_id
            apex_files = list(upload_dir.glob("*.apex"))
            self.assertEqual(len(apex_files), 1)
            self.assertEqual(apex_files[0].name, f"{first_id}__good.apex")

    def test_prune_retention_sweeps_orphan_generated_and_empty_uploads(self):
        from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID
        from sentinel.server.services.repositories import InMemoryRepository
        from sentinel.server.services import pipeline

        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")
            repo = InMemoryRepository()
            client = repo.create_client(userId=COMMISSIONING_STUB_USER_ID, name="Sweep Client")
            project = repo.create_project(
                userId=COMMISSIONING_STUB_USER_ID, clientId=client.clientId, name="Sweep Job"
            )
            keep_path = pipeline.save_upload(
                projectId=project.projectId,
                uploadId="u1",
                filename="keep.apex",
                content=b"apex",
            )
            repo.record_upload(
                projectId=project.projectId,
                uploadId="u1",
                originalFilename="keep.apex",
                storagePath=str(keep_path),
            )
            repo.record_upload(
                projectId=project.projectId,
                uploadId="u0",
                originalFilename="old.apex",
                storagePath=str(keep_path.parent / "u0__old.apex"),
            )
            (keep_path.parent / "u0__old.apex").write_bytes(b"old")

            empty = pipeline._project_upload_dir(projectId="orphan-empty")
            empty.mkdir(parents=True)
            orphan_gen = pipeline._project_out_dir(projectId="orphan-html")
            orphan_gen.mkdir(parents=True)
            (orphan_gen / "old.html").write_text("<html></html>", encoding="utf-8")

            repo.prune_project_upload_retention(
                projectId=project.projectId,
                activeUploadId="u1",
                activeStoragePath=str(keep_path),
            )
            self.assertEqual([u.uploadId for u in repo.list_uploads_for_project(projectId=project.projectId)], ["u1"])
            self.assertFalse(empty.exists())
            self.assertFalse(orphan_gen.exists())
            self.assertTrue(keep_path.exists())


if __name__ == "__main__":
    unittest.main()
