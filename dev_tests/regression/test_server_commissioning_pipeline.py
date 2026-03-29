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
    def test_upload_and_regenerate_contract_includes_phase_event_type(self):
        api_file = ROOT / "src" / "sentinel" / "server" / "api" / "commissioning.py"
        text = api_file.read_text(encoding="utf-8")
        self.assertIn('"type": "generation_phase"', text)
        self.assertIn('"percent": percent', text)
        self.assertIn("phase_hook=", text)
        self.assertIn('status="READY"', text)

    def test_commissioning_ui_handles_generation_phase_status(self):
        ui_file = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "commissioning.js"
        text = ui_file.read_text(encoding="utf-8")
        self.assertIn("generation_phase", text)
        self.assertIn("Extracting...", text)
        self.assertIn("Generating...", text)
        self.assertIn("setProgress($(\"uploadProgress\"), pct)", text)
        self.assertIn("setStatus($(\"uploadProgressLabel\"), \"Uploading...\")", text)
        index_file = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "index.html"
        self.assertIn(">Load File<", index_file.read_text(encoding="utf-8"))

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

    def test_upload_and_regenerate_publishes_phase_events_before_ready(self):
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

            published: list[dict] = []

            class _FakeBroker:
                def publish(self, *, projectId: str, event: dict) -> None:
                    published.append({"projectId": projectId, "event": dict(event or {})})
                def publish_transient(self, *, projectId: str, event: dict) -> None:
                    published.append({"projectId": projectId, "event": dict(event or {})})

            def _fake_regenerate(*, projectId: str, apex_path: Path, phase_hook=None):
                if callable(phase_hook):
                    phase_hook("extracting", 10)
                    phase_hook("extracting", 100)
                    phase_hook("generating", 50)
                    phase_hook("generating", 100)
                return {"projectId": projectId, "outDir": str(Path(td) / "generated" / projectId), "projectData": "x.json"}

            with apex_path.open("rb") as f:
                with mock.patch.object(commissioning_api, "_broker", return_value=_FakeBroker()):
                    with mock.patch.object(commissioning_api.pipeline, "regenerate_project", side_effect=_fake_regenerate):
                        resp = client.post(
                            f"/api/v1/commissioning/projects/{project_id}/upload-and-regenerate",
                            files={"apex": ("sample.apex", f, "application/octet-stream")},
                        )

            self.assertEqual(resp.status_code, 200)
            statuses = [
                str((row.get("event") or {}).get("status") or "")
                for row in published
                if str((row.get("event") or {}).get("type") or "") in {"generation_phase", "generation"}
            ]
            self.assertGreaterEqual(len(statuses), 5)
            self.assertEqual(statuses[:4], ["EXTRACTING", "EXTRACTING", "GENERATING", "GENERATING"])
            self.assertEqual(statuses[-1], "READY")
            percents = [
                (row.get("event") or {}).get("percent")
                for row in published
                if str((row.get("event") or {}).get("type") or "") == "generation_phase"
            ]
            self.assertEqual(percents, [10, 100, 50, 100, 100])

    def test_second_regenerate_replaces_old_generated_artifacts(self):
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
                up1 = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/uploads",
                    files={"apex": ("sample.apex", f, "application/octet-stream")},
                )
            self.assertEqual(up1.status_code, 200)
            upload_1 = up1.json()["uploadId"]
            regen1 = client.post(f"/api/v1/commissioning/projects/{project_id}/regenerate", json={"uploadId": upload_1})
            self.assertEqual(regen1.status_code, 200)

            out_dir = Path(os.environ["SENTINEL_GENERATED_ROOT"]) / project_id
            homes_1 = list(out_dir.glob("*__project-home.html"))
            data_1 = list(out_dir.glob("*_project_data.json"))
            self.assertEqual(len(homes_1), 1)
            self.assertEqual(len(data_1), 1)
            first_home = homes_1[0]
            first_data = data_1[0]

            with apex_path.open("rb") as f:
                up2 = client.post(
                    f"/api/v1/commissioning/projects/{project_id}/uploads",
                    files={"apex": ("sample2.apex", f, "application/octet-stream")},
                )
            self.assertEqual(up2.status_code, 200)
            upload_2 = up2.json()["uploadId"]
            regen2 = client.post(f"/api/v1/commissioning/projects/{project_id}/regenerate", json={"uploadId": upload_2})
            self.assertEqual(regen2.status_code, 200)

            homes_2 = list(out_dir.glob("*__project-home.html"))
            data_2 = list(out_dir.glob("*_project_data.json"))
            self.assertEqual(len(homes_2), 1)
            self.assertEqual(len(data_2), 1)
            self.assertFalse(first_home.exists(), "Old project-home artifact should be removed after regenerate.")
            self.assertFalse(first_data.exists(), "Old project-data artifact should be removed after regenerate.")

    def test_regenerate_does_not_delete_foreign_stage_directories(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")

            from sentinel.server.services import pipeline

            project_id = "proj-1"
            out_dir = Path(os.environ["SENTINEL_GENERATED_ROOT"]) / project_id
            out_dir.mkdir(parents=True, exist_ok=True)
            foreign_stage = out_dir / ".stage-foreign-active"
            foreign_stage.mkdir(parents=True, exist_ok=True)
            foreign_marker = foreign_stage / "marker.txt"
            foreign_marker.write_text("active", encoding="utf-8")

            apex_path = Path(td) / "sample.apex"
            apex_path.write_bytes(b"apex")

            def _fake_run(*, args, cwd, env, phase_hook=None):
                out_idx = args.index("--out-dir")
                stage_dir = Path(args[out_idx + 1])
                script = Path(args[1]).name
                if script == "extract_project_data.py":
                    (stage_dir / "sample_project_data.json").write_text("{}", encoding="utf-8")
                elif script == "generate_html.py":
                    (stage_dir / "sample_project_data__project-home.html").write_text("<html></html>", encoding="utf-8")
                    (stage_dir / "sample_project_data__project-manifest.json").write_text("{}", encoding="utf-8")
                    (stage_dir / "sample_project_data__device-0-test.html").write_text("<html></html>", encoding="utf-8")
                    (stage_dir / "sample_project_data__device-0-test__payload.json").write_text("{}", encoding="utf-8")
                return "", ""

            with mock.patch.object(pipeline, "_run_subprocess_with_progress", side_effect=_fake_run):
                result = pipeline.regenerate_project(projectId=project_id, apex_path=apex_path)

            self.assertTrue((out_dir / "sample_project_data__project-home.html").exists())
            self.assertEqual(result.get("projectId"), project_id)
            self.assertTrue(foreign_stage.exists(), "Foreign in-flight stage dir should not be removed.")
            self.assertTrue(foreign_marker.exists(), "Foreign stage contents should remain intact.")

    def test_regenerate_uses_short_staging_path_not_nested_under_project_dir(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["SENTINEL_GENERATED_ROOT"] = str(Path(td) / "generated")
            os.environ["SENTINEL_UPLOAD_ROOT"] = str(Path(td) / "uploads")

            from sentinel.server.services import pipeline

            project_id = "proj-2"
            apex_path = Path(td) / "sample.apex"
            apex_path.write_bytes(b"apex")

            staged_out_dirs: list[Path] = []

            def _fake_run(*, args, cwd, env, phase_hook=None):
                out_idx = args.index("--out-dir")
                stage_dir = Path(args[out_idx + 1])
                staged_out_dirs.append(stage_dir)
                script = Path(args[1]).name
                if script == "extract_project_data.py":
                    (stage_dir / "sample_project_data.json").write_text("{}", encoding="utf-8")
                elif script == "generate_html.py":
                    (stage_dir / "sample_project_data__project-home.html").write_text("<html></html>", encoding="utf-8")
                    (stage_dir / "sample_project_data__project-manifest.json").write_text("{}", encoding="utf-8")
                    (stage_dir / "sample_project_data__device-0-test.html").write_text("<html></html>", encoding="utf-8")
                    (stage_dir / "sample_project_data__device-0-test__payload.json").write_text("{}", encoding="utf-8")
                return "", ""

            with mock.patch.object(pipeline, "_run_subprocess_with_progress", side_effect=_fake_run):
                pipeline.regenerate_project(projectId=project_id, apex_path=apex_path)

            project_out = (Path(os.environ["SENTINEL_GENERATED_ROOT"]) / project_id).resolve()
            self.assertGreaterEqual(len(staged_out_dirs), 2)
            for stage_dir in staged_out_dirs:
                self.assertNotEqual(
                    stage_dir.resolve().parent,
                    project_out,
                    "Staging dir must not be nested under project output dir to avoid long-path failures.",
                )
